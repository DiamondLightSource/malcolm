window.onload = function() {
    
    var socket;
    var channel;
    var id;
   
    
    // Connect to the socket
    function connect(server) {
        socket = new WebSocket(server);
        testSocket();
    }
    
    function close() {
        socket.close(); // Close socket
        socket.onclose = function(e) { closeSocket(e) };
    }
    
    function waitForConnection(callback) {
        setTimeout(
            function(){
                if (socket.readyState === 1) {
                    callback();
                    return;
                } else {
                    waitForConnection(callback);
                }
        },5);
    };
    
    
    
    //Delays sending a message until the socket connection is established
    function sendMessage(message) {
        waitForConnection(function(){
           socket.send(message); 
        });
    };
    
    // Subscribe
    function subscribe(idSub, channelSub) {
        var message = '{"type" : "Subscribe", "id" : ' + idSub + ', "endpoint" : "' + channelSub + '"}';
        sendMessage(message); // Sends the message through socket
        socket.onmessage = function(e) { newMessage(e) };
    };
    
    // Get
    function get(idSub, channelSub) {
        var message = '{"type" : "Get", "id" : ' + idSub + ', "endpoint" : "' + channelSub + '"}';
        sendMessage(message); // Sends the message through socket
        socket.onmessage = function(e) { newMessage(e) };
    };    
    
    // Unsubscribe
   function unsubscribe(idUn) {
        var message = '{"type" : "Unsubscribe", "id" : ' + idUn + '}';
        sendMessage(message);
    };
    
    
    function testSocket() {
      socket.onopen = function(e) { openSocket(e) };
      socket.onerror = function(e) { error(e) };
    };
   
   
    // Message received
   function newMessage (event) {
       var response = JSON.parse(event.data);
       displayNewMessage(response);
    };
    
    // Log errors to the console
    function error (error) {
        console.log('WebSocket Error: ' + error);
    };
      
    // Pause
    function pause (idP) {
        var message = '{"message":"pause","id": ' + idP + '}';
        sendMessage(message);
    };
    
    // Resume
    function resume (idR) {
        var message = '{"message" : "resume", "id" : ' + idR + '}';
        sendMessage(message);
    };

 

/*************************
 * 
 * Front end
 * 
 *************************/
    
     // References to elements on the page
    var form = document.getElementById('message-form');
    var serverField = document.getElementById('server');
    var channelField = document.getElementById('channel');
    var idField = document.getElementById('idNum');
    var result = document.getElementById('results');
    var details = document.getElementById('details');
    var subscriptionList = document.getElementById('subscriptions');
    var connectBtn = document.getElementById('connect');
    var disconnectBtn = document.getElementById('disconnect');
    var subscribeBtn = document.getElementById('subscribe');
    var getBtn = document.getElementById('get');
    var pauseBtn = document.getElementById('pause');
    var resumeBtn = document.getElementById('resume');
    var unsubscribeBtn = document.getElementById('unsubscribe');
    var clearBtn = document.getElementById('clear');
    
    var filterBtn = document.getElementById('filter');
    var showAllBtn = document.getElementById('showAll');
    var filter = 'none';
    
    
    var currentId = 0;
    var channelList = [];
    var resultsInfo = []; // Contains JSON
    var results = [];
    var resultsFiltered = [];
    var resultsInfoFiltered = [];
    
    
    // Automatically set socket address
    serverField.value = "ws://" + window.location.host + "/ws";
    
    
    // Trigger socket connection when button is clicked
    connectBtn.onclick = function(e) {
        e.preventDefault();
        connect(serverField.value);
        return false;
    };
    
    
    // Trigger socket close when disconnet button is clicked
    disconnectBtn.onclick = function(e) {
        e.preventDefault();
        close();
        return false;
    };
    
    
    // Subscribe
    subscribeBtn.onclick = function(e) {
        // Break into two calls of other functions--format message and update UI
        channel = channelField.value;
        id = idField.value;
        subscribe(id, channel);
        currentId++;
        idField.value = currentId;
        
        var newSubscription = document.createElement('option'); // New subscription to be added to sub list
        newSubscription.className = 'open';
        subscriptionList.appendChild(newSubscription);
        newSubscription.appendChild(document.createTextNode('id: ' + id + ', channel: ' + channel));
        channelList.unshift(channel);
        subscriptionList.selectedIndex = id;
        
        resultsInfoFiltered.push([]); //creates new array for filtered info
        resultsFiltered.push([]);
    };
    
    // Get
    getBtn.onclick = function(e) {
        channel = channelField.value;
        id = idField.value;
        get(id, channel);
    };    
    
    // Unsubscribe
    unsubscribeBtn.onclick = function(e) {
        id = subscriptionList.selectedIndex;
        channel = channelList[channelList.length - id - 1];
        unsubscribe(id);
        if (filter == id || filter == 'none') {
            result.innerHTML = '<option>Unsubscribe: ' + channel + ', ' + id + '</option>' + result.innerHTML;
        }
        
        results.unshift('Unsubscribe: ' + channel + ', ' + id);
        resultsFiltered[id].unshift('Unsubscribe: ' + channel + ', ' + id);
        
        resultsInfo.unshift('Unsubscribe: ' + channel + ', ' + id);
        resultsInfoFiltered[id].unshift('Unsubscribe: ' + channel + ', ' + id);
        subscriptionList.childNodes[id].className = 'unsubscribed'; // Strikethrough
    };
    
    
     // Message received
    function displayNewMessage (response) {
        var previouslySelected = result.selectedIndex;
        var value;
        var filterValue;
        if (response.type === "Error") {
            if (filter = 'none') { // Print error to display
                var errorNotification = document.createElement('option');
                result.insertBefore(errorNotification, result.childNodes[0]); 
                errorNotification.appendChild(document.createTextNode('Error'));
            }
            resultsInfo.unshift('<div><pre>' + JSON.stringify(response, null, '     ') + '</pre></div>');
            results.unshift('Error');
            resultsFiltered[response.id].unshift('Error');
            resultsInfoFiltered[response.id].unshift('<div><pre>' + JSON.stringify(response, null, '     ') + '</pre></div>');
            return;
        }
        if (response.type === "connection") { // Successful subscription
            if (filter === 'none') { // New subscription added to results window 
                var subscriptionNotification = document.createElement('option');
                result.insertBefore(subscriptionNotification, result.childNodes[0]); 
                subscriptionNotification.appendChild(document.createTextNode('Subscribed: ' + channel + ', ' + id));
            }
            results.unshift('Subscribed: ' + channel + ', ' + id);
            resultsInfo.unshift('<div><pre>' + JSON.stringify(response, null, '     ') + '</pre></div>');
            resultsFiltered[response.id].unshift('Subscribed: ' + channel + ', ' + id);
            resultsInfoFiltered[response.id].unshift('<div><pre>' + JSON.stringify(response, null, '     ') + '</pre></div>');
            return;
        }
        else if (response.type === "Value" || response.type === "Return") {
            if (!response.hasOwnProperty('value')) {
                filterValue = 'None';            
            } else if (response.value.hasOwnProperty('type') && response.value.type.name === "VTable") {
                filterValue = 'table';
            } else if (response.value.hasOwnProperty('value')) {
                filterValue = filterValue = response.value.value;
            } else {
                filterValue = 'value';
            }
            value = '<option>' + filterValue + '</option>';
            resultsInfo.unshift('<div><pre>' + JSON.stringify(response, null, '     ') + '</pre></div>');
            results.unshift(filterValue);
            if (response.type === "Value") {
                resultsFiltered[response.id].unshift(filterValue);
                resultsInfoFiltered[response.id].unshift('<div><pre>' + JSON.stringify(response, null, '     ') + '</pre></div>');
            }
        }
        if (filter === 'none' || filter == response.id) { // Print event to display immediately
            result.innerHTML = value + result.innerHTML; 
            result.selectedIndex = previouslySelected + 1;
        }
    };
    
    // Updates connection status
   function openSocket (event) {
       result.innerHTML = '<option class="open">Connected</option>' + result.innerHTML;
       resultsInfo.unshift('Connected to ' + serverField.value);
       idField.value = currentId;
       subscriptionList.innerHTML = '';
    };
    
    
        // Updates the connection status when socket is closed
    function closeSocket(event) {
        result.innerHTML = '<option class="closed">Disconnected</option>' + result.innerHTML;
        resultsInfo.unshift('Disconnected from ' + socket.URL);
        currentId = 0;
    };
    
    subscriptionList.onchange = function(e) {
        var index = subscriptionList.selectedIndex;
        channel = channelList[index];
        id = index;
    };
    
    // Pause
    pauseBtn.onclick = function(e) {
        pause(id);
        if (filter == id || filter == 'none') {
            result.innerHTML = '<option>Pause: ' + channel + ', ' + id +'</option>' + result.innerHTML;
        }
        results.unshift('Pause: ' + channel + ', ' + id);
        resultsInfo.unshift('Channel: ' + channel + ', id: ' + id + ' paused');
        resultsFiltered[id].unshift('Pause: ' + channel + ', ' + id);
        resultsInfoFiltered[id].unshift('Channel: ' + channel + ', id: ' + id + ' paused');
        subscriptionList.childNodes[id].className = 'closed';
    };
    
    // Resume
    resumeBtn.onclick = function(e) {
        resume(id);
        if (filter == id || filter == 'none') {
            result.innerHTML = '<option>Resume: ' + channel + ', ' + id +'</option>' + result.innerHTML;
        }
        results.unshift('Resume: ' + channel + ', ' + id);
        resultsInfo.unshift('Channel: ' + channel + ', id: ' + id + ' resumed');
        resultsFiltered[id].unshift('Resume: ' + channel + ', ' + id);
        resultsInfoFiltered[id].unshift('Channel: ' + channel + ', id: ' + id + ' resumed');
        subscriptionList.childNodes[id].className = 'open';
    };
    
    // Clears event info
    clearBtn.onclick = function(e) {
        result.innerHTML= "";
        details.innerHTML = "";
    }

    // Displays details for selected event
    result.onchange = function(e) {
        var i = result.selectedIndex;
        if (filter == 'none') {
            details.innerHTML = resultsInfo[i];
        }
        else {
            details.innerHTML = resultsInfoFiltered[filter][i];
        }
    };
    
    filterBtn.onclick = function(e) {
        filter = id;
        result.innerHTML = '';
        for (var i = resultsFiltered[filter].length - 1; i >= 0; --i) {
            var event = document.createElement('option');
            result.insertBefore(event, result.childNodes[0]); 
            event.appendChild(document.createTextNode(resultsFiltered[filter][i]));
        }
    }
    
    showAllBtn.onclick = function(e) {
        filter = 'none';
        result.innerHTML = '';
        for (var i = results.length - 1; i >= 0; --i) {
            var event = document.createElement('option');
            result.insertBefore(event, result.childNodes[0]); 
            event.appendChild(document.createTextNode(results[i]));
        }
    }
    

}
