pvData over pvAccess
====================

The structure of the device as specified in V4 normative types language is this::

    StateMachine :=
    structure
        structure[] methods           // client side events that will trigger state transitions
            string          name       
            int[]           valid_states
            string          pv           : opt // this is the pv that provides the RPC service
            NTAttributes[]  args         : opt // value is the default value
            string          descriptor   : opt
        structure status
            string      message
            enum        state
            time_t      timeStamp
        NTAttributes[]  attributes
         
    where
      
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