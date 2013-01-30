function getURLParameter(name) {
	return decodeURI(
		(RegExp(name + '=' + '(.+?)(&|$)').exec(window.location.search)||[,null])[1]
	);
}

function isDefined(obj) {
    return !isUndefined(obj);
}

function isUndefined(obj) {
    return ((typeof(obj) == "undefined") || (obj == "null"));
}

/////////////////////////
// Channel support
/////////////////////////

function initChannel() {
//	console.log("initChannel - token: '" + token + "'");
	if (token != "") {
		channel = new goog.appengine.Channel(token);
		socket = channel.open();
		socket.onopen = onOpened;
		socket.onmessage = onMessage;
		socket.onerror = onError;
		socket.onclose = onClose;
	}
}

onOpened = function() {
}

onMessage = function(message) {
	var data = message.data;
	dataObj = jQuery.parseJSON(data);
//	console.log(dataObj);
	
	if (dataObj.op == "new") {
		handleNew(dataObj);
	}
}

onError = function(error) {
	console.log("Channel ERROR: ");
	console.log(error);
}

onClose = function() {
}