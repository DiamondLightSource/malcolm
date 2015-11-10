Design process for devices
==========================

Ideas from Rob
--------------

Some interest on using the client from Jython, so need to think about C
extensions. Maybe we should refactor using threads instead of cothreads?

Think it's probably best to use multiprocessing.ThreadPool:
http://stackoverflow.com/questions/3033952/python-thread-pool-similar-to-the-multiprocessing-pool

Debatable whether we need 1 or 2 threads per device (one for function requests, one for
stateMachine, or 1 to do both).
