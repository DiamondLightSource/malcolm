#!/bin/env dls-python
from pkg_resources import require
import weakref
require("mock")
require("cothread")
from enum import Enum
import unittest
import sys
import os
import cothread
import logging
#logging.basicConfig(level=logging.DEBUG)
import time
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.stateMachine import StateMachine, HasStateMachine


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

    def callback(self, changes):
        for k, v in changes.items():
            pre, k = k.split(".")
            assert pre == "stateMachine"
            assert k in ("state", "timeStamp", "message")
            getattr(self, k + "s").append(v)

    def test_state1_2_transition_works(self):
        trans = MagicMock(return_value=(VState.State2, "mess"))
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState)
        self.sm.loop_run()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)
        trans.assert_called_once_with()

    def test_transition_with_no_return_gives_error(self):
        mock_exception = MagicMock()
        self.sm.log_exception = mock_exception
        trans = MagicMock(return_value=None)
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState.State2)
        self.sm.loop_run()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.Err)
        trans.assert_called_once_with()
        mock_exception.assert_called_once_with(
            'Handler raised error: Needed tuple or list of length 2, got None')

    def test_transition_with_no_matching_func(self):
        mock_info = MagicMock()
        self.sm.log_info = mock_info
        trans = MagicMock(return_value=(VState.State2, "Boo"))
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState.State2)
        self.sm.loop_run()
        self.sm.post(VEvent.Event2)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State1)
        self.assertFalse(trans.called)
        mock_info.assert_called_once_with(
            "No handler functions for event (<VState.State1: 0>, <VEvent.Event2: 1>)")
        mock_info.reset_mock()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)
        self.assertFalse(mock_info.called)

    def test_2_transitions_works(self):
        self.sm.transition(VState.State1, VEvent.Event1, None, VState.State2)
        trans2 = MagicMock(return_value=(VState.State1, None))
        self.sm.transition(VState.State2, VEvent.Event2, trans2, VState)
        self.sm.loop_run()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)
        self.assertEquals(self.sm.message, "State change")
        self.sm.post(VEvent.Event2)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State1)
        self.assertEquals(self.sm.message, "State change")
        trans2.assert_called_once_with()

    def test_raising_error_notifies_status(self):
        mock_exception = MagicMock()
        self.sm.log_exception = mock_exception
        c = HasStateMachine("C")
        trans = MagicMock(side_effect=ValueError("My Error Message"))
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState.State2)
        c.add_stateMachine(self.sm)
        c.add_listener(self.callback)
        c.loop_run()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.Err)
        self.assertEquals(self.states, [VState.Err])
        self.assertEquals(self.messages, ["My Error Message"])
        mock_exception.assert_called_once_with(
            'Handler raised error: My Error Message')
        mock_exception.reset_mock()
    
    def test_raising_exception_with_args(self):
        mock_exception = MagicMock()
        self.sm.log_exception = mock_exception
        trans = MagicMock(side_effect=ValueError("My Error Message"))
        self.sm.transition(VState.State1, VEvent.Event1, trans, VState.State2)
        self.sm.loop_run()
        self.sm.post(VEvent.Event1, 3, boo="foo")
        cothread.Yield()
        mock_exception.assert_called_once_with(
            "Handler (called with args=(3,), kwargs={'boo': 'foo'}) raised error: My Error Message")

    def test_None_transition_func_returns_single_state(self):
        self.sm.transition(VState.State1, VEvent.Event1, None, VState.State2)
        self.sm.loop_run()
        self.sm.post(VEvent.Event1)
        cothread.Yield()
        self.assertEquals(self.sm.state, VState.State2)

    def test_None_transition_func_with_mult_states_fails(self):
        self.assertRaises(
            AssertionError, self.sm.transition, VState.State1, VEvent.Event1, None,
            VState)

    def test_want_changes_works(self):
        c = HasStateMachine("C")
        self.i = 0

        def trans():
            self.i += 1
            if self.i == 1:
                # Change message
                return VState.State1, "Message"
            elif self.i == 2:
                # No change
                return VState.State1, "Message"
            elif self.i == 3:
                # State change
                return VState.State2, "Message"
            elif self.i == 4:
                # Both change
                return VState.State1, "New Message"

        self.sm.transition(VState, VEvent.Event1, trans, VState)
        c.add_stateMachine(self.sm)
        c.add_listener(self.callback)
        c.loop_run()
        t = self.sm.timeStamp

        def check_output(states, messages, t):
            self.reset_cb_lists()
            self.sm.post(VEvent.Event1)
            cothread.Yield()
            self.assertEquals(self.states, states)
            self.assertEquals(self.messages, messages)
            self.assertEqual(len(self.timeStamps), 1)
            self.assertNotEqual(self.timeStamps[0], t)
            return self.timeStamps[0]

        # Change message
        t = check_output([], ["Message"], t)
        # No change
        t = check_output([], [], t)
        # Change state
        t = check_output([VState.State2], [], t)
        # Change both
        t = check_output([VState.State1], ["New Message"], t)

    def test_waiting_for_single_state(self):
        c = HasStateMachine("C")
        self.sm.transition(VState.State1, VEvent.Event1, None, VState.State2)
        c.add_stateMachine(self.sm)
        c.loop_run()
        start = time.time()

        def post_msg1():
            cothread.Sleep(0.1)
            self.sm.post(VEvent.Event1)
        cothread.Spawn(post_msg1)
        c.wait_until(VState.State2, timeout=0.2)
        end = time.time()
        self.assertAlmostEqual(start + 0.1, end, delta=0.01)
        self.assertEqual(self.sm.state, VState.State2)

    def test_del_called_when_out_of_scope(self):
        class Container(HasStateMachine):
            def trans(self):
                cothread.Sleep(0.05)
                if self.stateMachine.state == VState.State1:
                    return VState.State2, "Toggle"
                else:
                    return VState.State1, "Toggle"

        c = Container("C")
        self.sm.transition(VState, VEvent.Event1, c.trans, VState)
        c.add_stateMachine(self.sm)
        c.add_listener(self.callback)
        c.loop_run()
        for i in range(5):
            self.sm.post(VEvent.Event1)
        self.sm = None
        cothread.Sleep(0.2)
        self.assertEqual(len(self.states), 3)
        del c
        cothread.Sleep(0.2)
        self.assertEqual(len(self.states), 3)

if __name__ == '__main__':
    unittest.main(verbosity=2)
