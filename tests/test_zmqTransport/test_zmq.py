#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
require("mock")
require("pyzmq")
import unittest
import sys
import os
import time
import cothread
import socket
from cothread import coselect
import zmq
import logging
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock


class ZmqWrapper(object):

    def __init__(self, addr, timeout=1, bind=True):
        self.ctx = zmq.Context()
        if bind:
            self.sock = self.ctx.socket(zmq.ROUTER)
            #self.sock.setsockopt(zmq.LINGER, int(timeout*1000))
            self.sock.bind(addr)
        else:
            self.sock = self.ctx.socket(zmq.DEALER)
            self.sock.connect(addr)
        self.timeout = timeout
        self.outq = cothread.EventQueue()

    def event_loop(self):
        while True:
            self.outq.Signal(self.recv_multipart())

    def send_multipart(self, msg):
        # print hex(id(self)), "Send", msg
        self.sock.send_multipart(msg)

    def recv_multipart(self):
        poll = coselect.POLLIN | coselect.POLLOUT
        while True:
            try:
                ret = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                # print hex(id(self)), "Recv", ret
                return ret
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            if not coselect.poll_list([(self.sock.fd, poll)], self.timeout):
                raise Exception("Timed out")

    def close(self):
        self.sock.close()
        self.ctx.destroy()


class ZmqTest(unittest.TestCase):

    def test_close(self):
        for i in range(10):
            self.s = ZmqWrapper("ipc:///tmp/sock.ipc", 0.1)
            start = time.time()
            s = cothread.Spawn(self.s.recv_multipart, raise_on_wait=True)
            cothread.Sleep(0.01)
            self.s.close()
            try:
                s.Wait(0.1)
            except zmq.ZMQError, e:
                self.assertIn(e.errno, [zmq.ENOTSOCK, zmq.ENOTSUP])
            else:
                self.fail("Didn't get right exception")
            end = time.time()
            self.assertLess(end - start, 0.05)

    def fast_recv(self, s):
        start = time.time()
        msg = s.outq.Wait(0.2)
        end = time.time()
        self.assertLess(end - start, 0.05)
        return msg

    def test_recv(self):
        s = ZmqWrapper("ipc:///tmp/sock.ipc", 0.1)
        sp = cothread.Spawn(s.event_loop, raise_on_wait=True)
        c = ZmqWrapper("ipc:///tmp/sock.ipc", 0.1, bind=False)
        cp = cothread.Spawn(c.event_loop, raise_on_wait=True)
        for i in range(1000):
            c.send_multipart(["sub1"])
            c.send_multipart(["sub2"])
            cid, msg = self.fast_recv(s)
            self.assertEqual(msg, "sub1")
            c.send_multipart(["call1"])
            self.assertEqual(self.fast_recv(s)[1], "sub2")
            self.assertEqual(self.fast_recv(s)[1], "call1")
            s.send_multipart([cid, "ret1"])
            self.assertEqual(self.fast_recv(c), ["ret1"])
            s.send_multipart([cid, "val1"])
            s.send_multipart([cid, "val2"])
            c.send_multipart(["call2"])
            s.send_multipart([cid, "val3"])
            self.assertEqual(self.fast_recv(s)[1], "call2")
            self.assertEqual(self.fast_recv(c), ["val1"])
            self.assertEqual(self.fast_recv(c), ["val2"])
            self.assertEqual(self.fast_recv(c), ["val3"])
        s.close()
        c.close()
        self.assertRaises(zmq.ZMQError, sp.Wait, 0.1)
        self.assertRaises(zmq.ZMQError, cp.Wait, 0.1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
