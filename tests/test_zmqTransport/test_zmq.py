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
#logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock


class ZmqWrapper(object):
    def __init__(self, addr, timeout=1):
        self.ctx = zmq.Context()
        self.sock = self.ctx.socket(zmq.ROUTER)
        #self.sock.setsockopt(zmq.LINGER, int(timeout*1000))
        self.sock.bind(addr)
        self.timeout = timeout

    def fileno(self):
        """Needed so that we can co-operatively poll socket"""
        return self.sock.fd
    
    def recv(self):
        poll = coselect.POLLIN
        while True:
            try:
                ret = self.sock.recv_multipart(flags=zmq.NOBLOCK)
                return ret
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            if not coselect.poll_list([(self, poll)], self.timeout):
                raise Exception("Timed out")
    
    def close(self):
        self.ctx.destroy()
        
class ZmqTest(unittest.TestCase):

    def test_close(self):
        for i in range(10):
            self.s = ZmqWrapper("ipc:///tmp/sock.ipc", 0.1)
            start = time.time()
            s = cothread.Spawn(self.s.recv, raise_on_wait=True)
            cothread.Sleep(0.01)
            self.s.close()
            self.assertRaises(zmq.ZMQError, s.Wait, 0.1)
            end = time.time()
            self.assertLess(end-start, 0.05)


if __name__ == '__main__':
    unittest.main(verbosity=2)
