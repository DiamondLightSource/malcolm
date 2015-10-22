#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
import collections
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
            self.sock.bind(addr)
        else:
            self.sock = self.ctx.socket(zmq.DEALER)
            self.sock.connect(addr)
        self.sendsig_r, self.sendsig_w = os.pipe()
        self.timeout = timeout
        self.outq = cothread.EventQueue()
        self.event_list = [(self.sock.fd, coselect.POLLIN),
                           (self.sendsig_r, coselect.POLLIN)]
        self.poll_list = coselect.poll_list

    def event_loop(self):
        while True:
            ret = self.recv_multipart(timeout=None)
            self.outq.Signal(ret)

    def send_multipart(self, msg, timeout=None):
        # Tell our event loop to recheck recv
        self.sock.send_multipart(msg)
        os.write(self.sendsig_w, "-")

    def recv_multipart(self, timeout=None):
        start = time.time()
        if timeout is None:
            timeout = self.timeout
        while True:
            try:
                msg = self.sock.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.ZMQError as error:
                if error.errno == zmq.EAGAIN:
                    if timeout:
                        t = start + self.timeout - time.time()
                    else:
                        t = None
                    ready = self.poll_list(self.event_list, t)
                    if not ready:
                        raise zmq.ZMQError(
                            zmq.ETIMEDOUT, 'Timeout waiting for socket')
                    elif ready[0][0] == self.sendsig_r:
                        # clear send pipe
                        os.read(self.sendsig_r, 1)
                elif error.errno in [zmq.ENOTSOCK, zmq.ENOTSUP]:
                    raise StopIteration
                else:
                    raise
            else:
                # sys.stdout.write("Got message {}\n".format(msg))
                # sys.stdout.flush()
                return msg

    def close(self):
        os.write(self.sendsig_w, "-")
        self.sock.close()
        self.ctx.destroy()


class ZmqTestNew(unittest.TestCase):

    def test_close(self):
        for i in range(10):
            self.s = ZmqWrapper("ipc:///tmp/sock.ipc", 0.1)
            start = time.time()
            s = cothread.Spawn(self.s.event_loop, raise_on_wait=True)
            cothread.Sleep(0.01)
            self.s.close()
            self.assertRaises(StopIteration, s.Wait, 0.1)
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
        self.assertRaises(StopIteration, sp.Wait, 0.1)
        self.assertRaises(StopIteration, cp.Wait, 0.1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
