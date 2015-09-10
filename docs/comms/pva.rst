pvData over pvAccess
====================

The structure of the device as specified in V4 normative types language is this::

    Device :=
    structure
        string      name                // Name of the device
        string[]    tags                // Interfaces it supports
        union       any                 // Any other members must be        
            Method      method          // callable methods
            NTAttribute attribute       // or attributes
        string      descriptor  : opt   // Description of the device
    
    Method :=
    structure
        string          name                // Name of the method
        bool            allowed             // Can it be run at the moment
        NTAttributes[]  args        : opt   // value is the default value
                                            // tags = ["required"] if required
        string          descriptor  : opt
        
    NTAttribute :=
    structure
        string    name             
        any       value            
        string[]  tags          : opt   
        string    descriptor    : opt
        alarm_t   alarm         : opt
        time_t    timeStamp     : opt
     
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
