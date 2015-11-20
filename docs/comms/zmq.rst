.. highlight:: javascript
.. module:: malcolm.zmqComms

JSON over ZeroMQ
================

This is the simplest protocol, using JSON encoded strings which are sent over
ZeroMQ sockets. An implementation is supplied in the :module:`zmqComms` module.

There are 3 roles supported by the zmqComms module, illustrated by the diagram
below:

.. image:: images/malcolm_zmq.png

ZmqDeviceClient
---------------
This role is fulfilled by the :class:`ZmqDeviceClient` class as well as the ???
Java class. It is responsible for interacting with a named malcolm device,
providing methods for the client to:

- call methods, either just returning the return code, or returning an iterator
  that can gives intermediate status updates
- get parameters, from the entire structure of the device down to individually
  named fields
- subscribe to changes in named parameters

It does this by:

- serializing the `request_json`_
- sending them over a ZeroMQ DEALER that is connected to the
  `ZmqMalcolmRouter`_ device facing socket
- listening for replies over that same socket
- deserializing the `response_json`_
- yielding status updates, returning values and raising errors as appropriate

Each client should make sure that it sends data at least once every 10 seconds.
This keeps the TCP connection alive and verifies that both the client and
router are still alive. A malcolm.ping() method is provided for this purpose.

ZmqMalcolmRouter
----------------
This role is fulfilled by the :class:`ZmqMalcolmRouter` class. It is responsible
for routing `ZmqDeviceClient`_ requests to the correct `ZmqDeviceWrapper`_, and
routing the responses back again. It also has some general methods that allow
the client to query the currently available devices. It does this by using two
sockets, a client facing ZeroMQ ROUTER socket and a device facing ZeroMQ ROUTER
socket.

The client facing socket:

- deserializes the `request_json`_
- if it is a general method, then it acts on it and returns the correct `response_json`_
- if it is for a registered device, then it routes it the to correct `ZmqDeviceWrapper`_
- otherwise it returns an `error_json`_

The device facing socket:

- deserializes the `response_json`_

It also makes sure that both the clients and devices produce data once every 10 seconds,
marking them as disconnected and informing the interested parties if so.

ZmqDeviceWrapper
----------------
This role is fulfilled by the :class:`ZmqDeviceWrapper` class. It is responsible
for translating `ZmqDeviceClient`_ requests into :class:`malcolm.core.Device`
function calls, returning the relevant status updates, return codes and error
messages. It does this by:

- waiting for `request_json`_, deserializing it when it arrives
- if it is a `get_json`_ then serializing the requested parameter and sending it back
- if it is a `call_json`_ then calling the requested method, sending `value_json`_
  for status updates, `return_json`_ if a function returns normally, and
  `error_json`_ if it raises an error

request_json
------------
Can be one of:

- `call_json`_ to call a method of a device endpoint
- `get_json`_ to get the structure/value of an endpoint
- `subscribe_json`_ to subscribe to changes in the structure/value of an endpoint
- `unsubscribe_json`_ to request cancellation of a subscription

response_json
-------------
Can be one of:

- `value_json`_ for notifications of changes to a subscribed endpoint
- `return_json`_ for return values (including None) from calls, gets and subscribes
- `error_json`_ for raised errors

call_json
---------
- type = "Call"
- id = ``<int id to appear in responses>``
- endpoint = ``<name of device>``
- method = ``<name of method>``
- args (optional)

  - ``<arg1name>`` = ``<arg1value>``
  - ``<arg2name>`` = ``<arg2value>``

.. container:: toggle

    .. container:: header

        **Example**: Call::
        
            zebra.configure(PC_BIT_CAP=1, PC_TSPRE="ms", positions = [
                ("y", VDouble, np.repeat(np.arange(6, 9), 5) * 0.1, 'mm'),
                ("x", VDouble, np.tile(np.arange(5), 3) * 0.1, 'mm'),
            ])

    .. include:: zmqExamples/call_zebra_configure


get_json
--------
- type = "Get"
- id = ``<int id to appear in responses>``
- endpoint = ``<name of device>`` or ``<name of device>.<name of method>``

.. container:: toggle

    .. container:: header

        **Example**: Get the list of all available device names:

    .. include:: zmqExamples/get_DirectoryService_Device_instances

.. container:: toggle

    .. container:: header

        **Example**: Get the stateMachine status from zebra:

    .. include:: zmqExamples/get_zebra_status

.. container:: toggle

    .. container:: header

        **Example**: Get the entire "zebra1" structure:
        
    .. include:: zmqExamples/get_zebra

subscribe_json
--------------
- type = "Subscribe"
- id = ``<int id to appear in responses>``
- endpoint = ``<name of device>`` or ``<name of device>.<name of method>``

.. container:: toggle

    .. container:: header

        **Example**: Subscribe to changes in zebra stateMachine status:

    .. include:: zmqExamples/subscribe_zebra_status

unsubscribe_json
----------------
- type = "Unsubscribe"
- id = ``<int id provided to subscribe>``

.. container:: toggle

    .. container:: header

        **Example**: Unsubscribe an existing subscription:

    .. include:: zmqExamples/unsubscribe_zebra_status
    
value_json
----------
- type = "Value"
- id = ``<int id in response to>``
- val = ``<endpoint structure/value>``

.. container:: toggle

    .. container:: header

        **Example**: A status update from zebra1:

    .. include:: zmqExamples/value_zebra_status

return_json
-----------
- type = "Return"
- id = ``<int id in response to>``
- val = ``<return value structure>``

.. container:: toggle

    .. container:: header

        **Example**: Get the list of all available device names:

    .. code-block:: javascript

    .. include:: zmqExamples/return_DirectoryService_Device_instances

.. container:: toggle

    .. container:: header

        **Example**: Getting the last status message from "zebra1":

    .. include:: zmqExamples/return_zebra_status

.. container:: toggle

    .. container:: header

        **Example**: Getting the entire "zebra1" structure:

    .. code-block:: javascript

    .. include:: zmqExamples/return_zebra

        
error_json
----------
- type = "Return"
- id = ``<int id in response to>``
- message = ``<error message>``

.. container:: toggle

    .. container:: header

        **Example**: Trying to get endpoint on a non-existant device "foo":

    .. include:: zmqExamples/error_foo
