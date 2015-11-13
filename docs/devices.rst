Design process for devices
==========================

Some interest on using the client from Jython, so need to think about C
extensions. Maybe we should refactor using threads instead of cothreads?

Think it's probably best to use multiprocessing.ThreadPool:
http://stackoverflow.com/questions/3033952/python-thread-pool-similar-to-the-multiprocessing-pool

Debatable whether we need 1 or 2 threads per device (one for function requests, one for
stateMachine, or 1 to do both).

Now I think it's better to have the following:
* 1 thread for Process as we currently have
* A thread pool for the process for calling functions, similar to currently
* 1 thread per Socket as we currently have
* 1 thread for CA (change)
* Device statemachine handled by Process thread

If we wrap this all up so we have 3 primitives, following the primitive API
* Task (cothread.Spawn, Queue.Thread) with __del__ behaviour
* Queue (cothread.EventQueue, threading.Queue)
* Lock (cothread.Event, threading.Lock)

We will also make a simple threadpool from these primitives

We can then use the threading builtins, or manufacture cothread
ones that look similar. Let's not use multiprocessing as we can start multiple
processes manually and it will allow us to use Jython

We should also refactor so that listeners require an input queue to push onto,
and push (name, changes) instead of calling arbitrary functions

So we should make it so that any Method only calls threadsafe functions, we can
do this by taking the Lock before running a function, and letting report_wait
release it.

We need 2 objects for the Process:
* Process class with q. This receives all events and fans them out to:
* DeviceManager. This manages all running methods and idle tasks for all devices,
  unblocking Methods when changes occur, etc.

Listener API:
* self.listen(device, suffix="")
* will make device put (SEvent.Changes, device.name, changes=dict()) onto self.process.q
  and setup self.process to post these changes to any blocked Methods

Subscriptions should be owned by the sockets and should be called like this:
* self.listen(device, suffix="") but will put things on self.q not self.process.q

This should mean that we can do Tango and EPICS V4 by listening to Process devices, and
when they appear or disappear then destroying or creating our own devices

Add fancy things in setattr to see if we are setting
Attributes or _private variables

Can add a whole bunch of fancy things to ipython here:
http://www.esrf.eu/computing/cs/tango/tango_doc/kernel_doc/pytango/latest/itango.html#itango-highlights

