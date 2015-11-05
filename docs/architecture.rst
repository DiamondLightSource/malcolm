Architecture
============

Describe the concepts of StateMachine, Device, RunnableDevice, PausableDevice
and when you would use them. Introduce the basic state machine

State Machine
-------------

Copy from the WP4 design specification

ConfigurableDevice
------------------

.. uml::

    !include docs/stateMachineDefs.iuml

    state canAbort {
        Configuring --> Idle : Changes [done]        
    }        

RunnableDevice
--------------

.. uml::

    !include docs/stateMachineDefs.iuml

    state canAbort {
        Configuring --> Ready : Changes [done]

        state Ready <<Rest>>        
        Ready --> Ready : Changes [not done]
        Ready --> Idle : Changes [done]
        Ready --> Running : Run
        Ready --> Configuring : Config
        
        Running --> Running : Changes [not done]
        Running --> Ready : Changes [partially done]
        Running --> Idle : Changes \n [all done]
    }    


PausableDevice
--------------

.. uml::
    
    !include docs/stateMachineDefs.iuml

    state canAbort {
        Configuring --> Ready : Changes [done]
        
        state Ready <<Rest>>        
        Ready --> Ready : Changes [not done]
        Ready --> Idle : Changes [done]
        Ready --> Running : Run
        Ready --> Rewinding : Rewind
        Ready --> Configuring : Config
        
        Running --> Running : Changes [not done]
        Running --> Ready : Changes [partially done]
        Running --> Idle : Changes [all done]
        Running --> Rewinding: Rewind
        
        Rewinding --> Rewinding : Changes [not done]
        Rewinding --> Ready : Changes [done & wasReady]
        Rewinding --> Paused : Changes [done & wasPaused]
        
        Paused --> Paused : Changes
        Paused --> Running : Run
        Paused --> Rewinding : Rewind
    }    



Device Methods
--------------

Add the sub state diagrams for each method

General Methods
---------------

Include the malcolm.* methods

Status updates, Attribute readbacks and Method introspection
------------------------------------------------------------

Including the process diagram
