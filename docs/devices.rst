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
* 1 thread per Socket as we currently have, but add device sockets
* 1 thread for CA (change)
* Device statemachine handled by Process thread (inspiration from sched.scheduler)

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

* self.listen(device, suffix="", initial_value=False)
* will make device put (SEvent.Changes, device.name, changes=dict()) onto self.process.q
  and setup self.process to post these changes to any blocked Methods
* if initial_value = True then get (SEvent.Value, device.name, value=device.to_dict()) onto
  self.process.q

Subscriptions should be owned by the sockets and should be called like this:
* self.listen(device, suffix="", initial_value=True) but will put things on self.q
  not self.process.q

Need to make Base.to_dict() recurse...

This should mean that we can do Tango and EPICS V4 by listening to Process devices, and
when they appear or disappear then destroying or creating our own devices

Add fancy things in setattr to see if we are setting
Attributes or _private variables

Can add a whole bunch of fancy things to ipython here:
http://www.esrf.eu/computing/cs/tango/tango_doc/kernel_doc/pytango/latest/itango.html#itango-highlights

Remember that __init__ needs to support internal python types as well, so only allow
a server to create it if its been decorated.

And also that we need to be able to dynamically create configure() methods. Or maybe we
don't. It's all to do with access to attributes from outside the class triggering
set_attribute for the attribute.

Need to think about:

* Setting read-only Attribute from inside:
  - self.connected.update(True)
  - self.connected = True calls self.write_attribute("connected", True) which fails
* Setting read-only PVAttributes from CA:
  - PVAttribute should do Attribute.update(self.connected, value)
  - PVAttribute.update() should fail
* Setting write PVAttribute from inside:
  - self.exposure.set_pv(0.1)
* Setting write Attribute from outside:
  - self.exposure = 0.1
  - calls self.write_attribute("exposure", 0.1) which calls self.configure(exposure=0.1, period=self.period...)
* Getting attribute
  - attr = self.attributes["exposure"]
  - val = self.exposure
  - calls self.read_attribute("exposure") which returns self.attributes["exposure"].value

ca can be a Device with custom attributes, so that when we monitor them they get created

rename wrap_method to publish_method

add an action VType
add units to VTypes
add display and control ranges to VTypes

Websockets:

wsgiref fileserver:
http://blog.client9.com/2008/11/23/minimal-http-file-server-in-python.html
https://github.com/chrisrossi/wsgi-tutorial/blob/master/example2/fileserver.py
http://probablyprogramming.com/2008/06/26/building-a-python-web-application-part-1
http://eflorenzano.com/blog/2009/01/08/writing-blazing-fast-infinitely-scalable-pure-wsgi/

call ws.once() when we have polled and found it ready. This will then call message_received()

For the state transition functions, we should have an event_handler that's always
called and gets to consume the event or pass it on. Then maybe:

* do_run
* do_rewind
* do_abort

All of these should start in the -ing state, and return the final state

Finally we have the Methods

* configure
* run
* pause

These should take the lock (where needed), then call the do_ function, catching
StateException and setting