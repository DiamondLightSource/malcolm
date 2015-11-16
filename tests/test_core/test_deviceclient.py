#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.alarm import Alarm
from malcolm.core.runnabledevice import DState
from malcolm.core.vtype import VInt
require("mock")
require("cothread")
import unittest
import sys
import os
import time
import cothread
import logging
from mock import MagicMock, call
#logging.basicConfig(level=logging.DEBUG)

# logging.basicConfig()
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.deviceclient import DeviceClient
from malcolm.core.transport import SType


class DeviceTest(unittest.TestCase):

    def setUp(self):
        self.sock = MagicMock()
        self.d = DeviceClient("D", self.sock)
        self.assertEqual(self.sock.mock_calls, [])

    def test_run_calls_right_things(self):
        def side_effect(response, typ, kwargs):
            self.post = response
            response(SType.Return, value={})
        self.sock.request.side_effect = side_effect
        self.d.loop_run()
        self.assertEqual(len(self.sock.mock_calls), 1)
        self.sock.request.assert_called_once_with(
            self.post, SType.Get, dict(endpoint="D"))

    def test_attribute_monitors(self):
        def side_effect(post, typ, kwargs):
            if kwargs["endpoint"] == "D":
                self.post = post
                bit = dict(type=VInt, descriptor="Desc", value=3,
                           alarm=Alarm.ok().to_dict(), timeStamp=43.2)
                post(SType.Return, value=dict(attributes=dict(bit=bit)))
            elif kwargs["endpoint"] == "D.attributes.bit":
                self.spost = post
        self.sock.request.side_effect = side_effect
        self.d.loop_run()
        self.assertEqual(len(self.sock.mock_calls), 2)
        self.assertEqual(self.sock.request.call_args_list[0], call(
            self.post, SType.Get, dict(endpoint="D")))
        self.assertEqual(self.sock.request.call_args_list[1], call(
            self.spost, SType.Subscribe, dict(endpoint="D.attributes.bit")))
        self.assertEqual(self.d.bit, 3)
        self.assertEqual(type(self.d.attributes["bit"].typ), VInt)
        self.assertEqual(self.d.attributes["bit"].descriptor, "Desc")
        self.assertEqual(self.d.attributes["bit"].value, 3)
        self.assertEqual(self.d.attributes["bit"].alarm, Alarm.ok())
        self.assertEqual(self.d.attributes["bit"].timeStamp, 43.2)

    def test_methods(self):
        def side_effect(response, typ, kwargs):
            self.post = response
            if typ == SType.Get and kwargs["endpoint"] == "D":
                run = dict(descriptor="Run")
                response(SType.Return, value=dict(methods=dict(run=run)))
            elif kwargs["method"] == "run":
                response(SType.Return, value=99)
            else:
                print kwargs
        self.sock.request.side_effect = side_effect
        self.d.loop_run()
        self.assertEqual(len(self.sock.mock_calls), 1)
        self.sock.request.assert_called_once_with(
            self.post, SType.Get, dict(endpoint="D"))
        self.assertIn("run", dir(self.d))
        self.sock.request.reset_mock()
        self.assertEqual(self.d.run(), 99)
        self.sock.request.assert_called_once_with(
            self.post, SType.Call, dict(endpoint="D", method="run", arguments={}))

    def test_sm(self):
        def side_effect(post, typ, kwargs):
            if kwargs["endpoint"] == "D":
                self.post = post
                sm = dict(
                    state="Running", states=[d.name for d in DState], message="foo", timeStamp=43.2)
                post(SType.Return, value=dict(stateMachine=sm))
            elif kwargs["endpoint"] == "D.stateMachine":
                self.spost = post
        self.sock.request.side_effect = side_effect
        self.d.loop_run()
        self.assertEqual(len(self.sock.mock_calls), 2)
        self.assertEqual(self.sock.request.call_args_list[0], call(
            self.post, SType.Get, dict(endpoint="D")))
        self.assertEqual(self.sock.request.call_args_list[1], call(
            self.spost, SType.Subscribe, dict(endpoint="D.stateMachine")))
        self.assertEqual(self.d.stateMachine.state, DState.Running)
        self.assertEqual(self.d.stateMachine.message, "foo")
        self.assertEqual(self.d.stateMachine.timeStamp, 43.2)

    def tearDown(self):
        msgs = []

        def log_debug(msg):
            msgs.append(msg)

        self.d.log_debug = log_debug
        self.d = None
        self.assertEqual(msgs, ['Garbage collecting loop',
                                'Stopping loop',
                                'Waiting for loop to finish',
                                "Loop finished",
                                'Loop garbage collected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
