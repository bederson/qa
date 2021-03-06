/////////////////////////
// Constants
/////////////////////////
var PHASE_DISABLED = 0
var PHASE_NOTES = 1
var PHASE_TAG_BY_CLUSTER = 2
var PHASE_TAG_BY_NOTE = 3
var PHASE_COMPARE_BY_SIMILARITY = 4

function getURLParameter(name) {
	//return decodeURI(
	//	(RegExp(name + '=' + '(.+?)(&|$)').exec(window.location.search)||[,null])[1]
	//);
    return decodeURIComponent((new RegExp('[?|&|#]' + name + '=' + '([^&;]+?)(&|#|;|$)').exec(window.location.search)||[,""])[1].replace(/\+/g, '%20'))||null;
}

function isDefined(obj) {
    return !isUndefined(obj);
}

function isUndefined(obj) {
    return typeof(obj) == "undefined" || obj == null;
}

/**
 * jQuery.browser.mobile (http://detectmobilebrowser.com/)
 * jQuery.browser.mobile will be true if the browser is a mobile device
 **/
(function(a){(jQuery.browser=jQuery.browser||{}).mobile=/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i.test(a.substr(0,4))})(navigator.userAgent||navigator.vendor||window.opera);

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
	
	if (dataObj.op == "newidea") {
		handleNew(dataObj);
	} else 	if (dataObj.op == "newtag") {
		handleTag(dataObj);
	} else 	if (dataObj.op == "refresh") {
		handleRefresh(dataObj);
	} else 	if (dataObj.op == "phase") {
		handlePhase(dataObj);
	} else if (dataObj.op == "nickname") {
		handleNickname(dataObj);
	}
}

onError = function(error) {
	console.log("Channel ERROR: ");
	console.log(error);
}

onClose = function() {
}

enableDisable = function(obj, enable) {
	if (enable) {
		obj.removeAttr("disabled");
	}
	else {
		obj.attr("disabled", "disabled");
	}
}

function phaseToString(phase) {
	var str = "";
	switch(phase) {
		case PHASE_DISABLED:
			str = "Disabled";
			break;
		case PHASE_NOTES:
			str = "Note entry";
			break;
		case PHASE_TAG_BY_CLUSTER:
			str = "Tagging by cluster";
			break;
		case PHASE_TAG_BY_NOTE:
			str = "Tagging by note";
			break;
		case PHASE_COMPARE_BY_SIMILARITY:
			str = "Compare notes by similarity";
			break;
		default:
			str = "Unknown phase";
			break;
	}
	return str;
}