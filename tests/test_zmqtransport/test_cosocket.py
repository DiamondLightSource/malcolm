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
import time
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock
from cothread import cosocket


class SockWrapper(object):

    def __init__(self, addr, timeout=1, bind=True):
        self.bind = bind
        if bind:
            self.sock_l = cosocket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock_l.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock_l.bind(addr)
            self.sock_l.listen(1)
        else:
            self.sock = cosocket.socket()
            self.sock.connect(addr)
            # Don't wait for a full buffer before sending
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        self.timeout = timeout
        self.outq = cothread.EventQueue()

    def event_loop(self):
        if self.bind:
            self.sock, _ = self.sock_l.accept()
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        buf = ''
        while True:
            ret = self.recv_multipart()
            if not ret:
                break
            buf += ret
            while "\n" in buf:
                msg, buf = buf.split("\n", 1)
                self.outq.Signal(msg)

    def send_multipart(self, msg):
        #print hex(id(self)), "Send", repr(msg)
        self.sock.send(msg + "\n")

    def recv_multipart(self):
        msg = self.sock.recv(1024)
        #print hex(id(self)), "Recv", repr(msg)
        return msg

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


class CosocketTest(unittest.TestCase):

    def fast_recv(self, s):
        start = time.time()
        msg = s.outq.Wait(0.1)
        end = time.time()
        self.assertLess(end - start, 0.05)
        return msg

    def test_recv(self):
        addr = 8888
        s = SockWrapper(("", addr), 0.1)
        c = SockWrapper(("localhost", addr), 0.1, bind=False)
        sp = cothread.Spawn(s.event_loop, raise_on_wait=True)
        cp = cothread.Spawn(c.event_loop, raise_on_wait=True)
        for i in range(1000):
            c.send_multipart("sub1")
            c.send_multipart("sub2")
            self.assertEqual(self.fast_recv(s), "sub1")
            c.send_multipart("call1")
            self.assertEqual(self.fast_recv(s), "sub2")
            end = time.time()
            self.assertEqual(self.fast_recv(s), "call1")
            s.send_multipart("ret1")
            self.assertEqual(self.fast_recv(c), "ret1")
            s.send_multipart("val1")
            s.send_multipart("val2")
            c.send_multipart("call2")
            s.send_multipart("val3")
            self.assertEqual(self.fast_recv(s), "call2")
            self.assertEqual(self.fast_recv(c), "val1")
            self.assertEqual(self.fast_recv(c), "val2")
            self.assertEqual(self.fast_recv(c), "val3")
        s.close()
        c.close()
        sp.Wait(0.1)
        cp.Wait(0.1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
