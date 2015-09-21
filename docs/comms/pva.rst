pvData over pvAccess
====================

The structure of the device as specified in V4 normative types language is this::

    Device :=
    structure
        string        name               // Name of the device
        string        descriptor   : opt // Description of the device
        string[]      tags         : opt // Tags for device if any, e.g. "instance:RunnableDevice"
        Method[]      methods      : opt // Methods this device supports if any
        StateMachine  stateMachine : opt // Statemachine if device has one
        NTAttribute[] attributes   : opt // Attributes that form arguments for methods/readbacks if any
    
    Method :=
    structure
        string        name               // Name of the method
        NTAttribute[] arguments    : opt // value is the default value
                                         // tags = ["argument:required"] if required
        string[]      valid_states : opt // StateMachine states this method is valid in
        string        descriptor   : opt // Docstring of method
    
    StateMachine :=
    structure
        string        message            // Status message for info
        string        state              // State of the machine
        string[]      states             // List of all possible states of this machine
        time_t        timeStamp          // Timestamp of last transition (even if no change in state/message)
    
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
