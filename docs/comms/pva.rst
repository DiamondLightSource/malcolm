pvData over pvAccess
====================

The structure of the Device as specified in V4 normative types language is this::

    Device :=
    structure
        string        name               // Name of the device
        string        descriptor   : opt // Description of the device
        string[]      tags         : opt // Tags for device if any, e.g. "instance:RunnableDevice"
        Method[]      methods      : opt // Methods this device supports if any
        NTAttribute[] attributes   : opt // Attributes that form arguments for methods/readbacks if any
    
    Method :=
    structure
        string        name               // Name of the method
        NTAttribute[] arguments    : opt // value is the default value
                                         // tags = ["argument:required"] if required
        string[]      valid_states : opt // StateMachine states this method is valid in
        string        descriptor   : opt // Docstring of method

    // And standard types unchanged from the Normative Types document
    
    NTAttribute :=
    structure
        string    name                   // Name of attribute
        any       value                  // Current value
        string[]  tags          : opt    // e.g. "display:readback"
        string    descriptor    : opt    // Description of attribute
        alarm_t   alarm         : opt    // Alarm status
        time_t    timeStamp     : opt    // When attribute last changed
     
    alarm_t :=
    structure
        int severity
        int status
        string message
     
    time_t :=
    structure
        long secondsPastEpoch
        int  nanoseconds
        int  userTag

I would like to have a number of servers, each of which hosts a number of these devices.
The client can then create proxies to these objects which set monitors on the structures
and allow RPC methods to be called.

This allows me to produce a distributed object model, where I can expose some high level
scriptable objects to the end user, that in turn talk to some lower level objects that
talk directly to hardware. The objects can be in the same process, on the same machine,
or on different machines, and it should make no difference.

The high level objects I would expect to be written in Python, while the lower level
objects should be written in C++ (although they are currently in Python talking CA to
V3 IOCs).
