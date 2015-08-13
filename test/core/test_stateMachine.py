#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("cothread")
from enum import Enum
import unittest
import sys
import os
import cothread
#import logging
#logging.basicConfig(level=logging.DEBUG)
import time
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.stateMachine import StateMachine


class VState(Enum):
    State1, State2, Err = range(3)


class VEvent(Enum):
    Event1, Event2 = range(2)


class StateMachineTest(unittest.TestCase):

    def setUp(self):
        self.sm = StateMachine("SM", VState.State1, VState.Err)
        self.reset_cb_lists()
    
    def reset_cb_lists(self):
        self.states = []
        self.timeStamps = []
        self.messages = []
        self.changes = []

    def callback(self, status, changes=None):
        self.states.append(status.state)
        self.timeStamps.append(status.timeStamp.to_time())
        self.messages.append(status.message)
        self.changes.append(changes)     

    def test_state1_2_transition_works(self):
        trans = MagicMock(return_value=VState.State2)
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState)
        self.sm.start_event_loop()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)
        trans.assert_called_once_with(VEvent.Event1)

    def test_transition_with_no_return_gives_only_registered_state(self):
        trans = MagicMock(return_value=None)
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState.State2)
        self.sm.start_event_loop()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)
        trans.assert_called_once_with(VEvent.Event1)

    @patch("malcolm.core.stateMachine.log.warning")
    def test_trans_with_no_return_and_mult_states_fails(self, mock_warning):
        trans = MagicMock(return_value=None)
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState)
        self.sm.start_event_loop()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.Err)
        trans.assert_called_once_with(VEvent.Event1)
        mock_warning.assert_called_once_with(
            'SM: Returned state None in response to event VEvent.Event1 is not one of the registered states [<VState.State1: 0>, <VState.State2: 1>, <VState.Err: 2>]')

    @patch("malcolm.core.stateMachine.log.warning")
    def test_transition_with_no_matching_func(self, mock_warning):
        trans = MagicMock(return_value=None)
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState.State2)
        self.sm.start_event_loop()
        self.sm.post(VEvent.Event2)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State1)
        self.assertFalse(trans.called)
        mock_warning.assert_called_once_with(
            'SM: in state VState.State1 has no transition functions registered for event VEvent.Event2')
        mock_warning.reset_mock()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)
        self.assertFalse(mock_warning.called)

    def test_2_transitions_works(self):
        self.test_state1_2_transition_works()
        trans2 = MagicMock(return_value=VState.State1)
        self.sm.transition(VState.State2, VEvent.Event2, trans2, VState)
        self.sm.post(VEvent.Event2)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State1)
        trans2.assert_called_once_with(VEvent.Event2)

    @patch("malcolm.core.stateMachine.log.error")
    def test_raising_error_notifies_status(self, mock_error):
        self.test_state1_2_transition_works()
        trans2 = MagicMock(side_effect=ValueError("My Error Message"))
        self.sm.transition(VState.State2, VEvent.Event2, trans2, VState.State1)
        self.sm.add_listener(self.callback)
        self.sm.post(VEvent.Event2)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.Err)
        self.assertEquals(self.states, [VState.Err])
        self.assertEquals(self.messages, ["My Error Message"])
        mock_error.assert_called_once_with(
            "SM: event VEvent.Event2 caused error ValueError('My Error Message',) in transition func")

    def test_None_transition_func_returns_single_state(self):
        self.sm.transition(VState.State1, VEvent.Event1, None, VState.State2)
        self.sm.start_event_loop()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)

    def test_None_transition_func_with_mult_states_fails(self):
        self.assertRaises(
            AssertionError, self.sm.transition, VState.State1, VEvent.Event1, None,
            VState)

    def test_want_changes_works(self):        
        self.sm.add_listener(self.callback, changes=True)
        self.i = 0
        def trans(event):
            self.i += 1
            if self.i == 1:
                # Change message
                self.sm.status_message("Message")                
                return VState.State1
            elif self.i == 2:
                # No change
                return VState.State1
            elif self.i == 3:
                # State change
                return VState.State2
        
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState)
        self.sm.start_event_loop()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.changes, [["message", "timeStamp"]])
        self.assertEquals(self.states, [VState.State1])
        self.assertEquals(self.messages, ["Message"])
        self.assertAlmostEquals(self.timeStamps[0], time.time(), delta=0.01)
        self.reset_cb_lists()       
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.changes, [["timeStamp"]])
        self.assertEquals(self.states, [VState.State1])
        self.assertEquals(self.messages, ["Message"])
        self.assertAlmostEquals(self.timeStamps[0], time.time(), delta=0.01)
        self.reset_cb_lists()  
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.changes, [["state", "message", "timeStamp"]])
        self.assertEquals(self.states, [VState.State2])
        self.assertEquals(self.messages, ["State change"])
        self.assertAlmostEquals(self.timeStamps[0], time.time(), delta=0.01)
        self.reset_cb_lists()  

    def test_listener_works(self):
        self.sm.add_listener(self.callback)
        self.test_2_transitions_works()
        for i, state in enumerate((VState.State2, VState.State1)):
            self.assertEquals(self.states[i], state)
            self.assertEquals(self.messages[i], "State change")

    def test_waiting_for_single_state(self):
        self.sm.transition(VState.State1, VEvent.Event1, None, VState.State2)
        self.sm.start_event_loop()
        start = time.time()

        def post_msg1():
            cothread.Sleep(0.1)
            self.sm.post(VEvent.Event1)
        cothread.Spawn(post_msg1)
        self.sm.wait_for_transition(VState.State2)
        end = time.time()
        self.assertAlmostEqual(start + 0.1, end, delta=0.01)

if __name__ == '__main__':
    unittest.main(verbosity=2)
