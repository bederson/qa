//===================================================
// Constants
//===================================================

// authentication types (for students)
var NO_AUTHENTICATION = 0
var GOOGLE_AUTHENTICATION = 1
var NICKNAME_AUTHENTICATION = 2

// job types
var SUGGEST_CATEGORY = 1;
var BEST_CATEGORY = 2;
var EQUAL_CATEGORY = 3;
var FIT_CATEGORY = 4;
var VERIFY_CATEGORY = 5;

var TIME_REQUIRED_PER_CASCADE_JOB = 20;  // estimate in seconds
var MAX_CHARS = 125; // max characters per response

var SHOW_START_URL_BY_DEFAULT = false;

var STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "any", "are", "as", "at", "be", "been", "being", "but", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "her", "here", "him", "his", "how", "I", "if", "in", "into", "is", "it", "its", "just", "my", "of", "on", "only", "or", "our", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "this", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];

/**
 * jQuery.browser.mobile (http://detectmobilebrowser.com/)
 * jQuery.browser.mobile will be true if the browser is a mobile device
 **/
(function(a){(jQuery.browser=jQuery.browser||{}).mobile=/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i.test(a.substr(0,4))})(navigator.userAgent||navigator.vendor||window.opera);

//===================================================
// Channels
//===================================================

function initChannel(onCustomOpened) {
	// console.log("initChannel - token: '" + token + "'");
	if (token != "") {
		channel = new goog.appengine.Channel(token);
		socket = channel.open();
		socket.onopen = isDefined(onCustomOpened) ? onCustomOpened : onOpened;
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
	//console.log(dataObj.op);
	
	if (dataObj.op == "newidea" && typeof window.handleIdea == 'function') {
		handleIdea(dataObj);
	}
	else if (dataObj.op == "enable" && typeof window.handleEnable == 'function') {
		handleEnable(dataObj); 
	}
	else if (dataObj.op == "disable" && typeof window.handleDisable == 'function') {
		handleDisable(dataObj); 
	}
	else if (dataObj.op == "job" && typeof window.handleJob == 'function') {
		handleJob(dataObj)
	}
	else if (dataObj.op == "morejobs" && typeof window.handleMoreJobs == 'function') {
		handleMoreJobs(dataObj);
	}
	else if (dataObj.op == "newcategory" && typeof window.handleCategory == 'function') {
		handleCategory(dataObj);
	}
	else if (dataObj.op == "fitcomplete" && typeof window.handleFitComplete == 'function') {
		handleFitComplete(dataObj);
	}
	else if (dataObj.op == "verifycomplete" && typeof window.handleVerifyComplete == 'function') {
		handleVerifyComplete(dataObj);
	}
	else if (dataObj.op == "moreverifyjobs" && typeof window.handleMoreVerifyJobs == 'function') {
		handleMoreVerifyJobs(dataObj);
	}
	else if (dataObj.op == "categories" && typeof window.handleResults == 'function') {
		handleResults(dataObj);
	}	
	else if ((dataObj.op == "discuss_idea" || dataObj.op == "remove_discuss_idea") && typeof window.handleDiscussIdea == 'function') {
		handleDiscussIdea(dataObj);
	}
	else if (dataObj.op == "nickname" && typeof window.handleNickname == 'function') {
		handleNickname(dataObj);
	}	
	else if (dataObj.op == "student_login" && typeof window.handleStudentLogin == 'function') {
		handleStudentLogin(dataObj);
	}	
	else if (dataObj.op == "student_logout" && typeof window.handleStudentLogout == 'function') {
		handleStudentLogout(dataObj);
	}	
	else if (dataObj.op == "logout" && typeof window.handleLogout == 'function') {
		handleLogout(dataObj);
	}
}

onError = function(error) {
	console.log("Channel ERROR: ");
	console.log(error);
}

onClose = function() {
}

//===================================================
// Page Urls
//===================================================

function isRunningOnLocalServer() {
	var url = ""+window.location.href;
	return url.indexOf("http://localhost:8080") != -1;
}

function isRunningOnTestServer() {
	var url = ""+window.location.href;
	return url.indexOf("http://localhost:8080") != -1 || url.indexOf("http://qa-umd-test.appspot.com") != -1 || url.indexOf("http://xparty-test.appspot.com") != -1;
}

function redirectToHome() {
	window.location.href = "/";
}

function getStartPageUrl(question_id) {
    var url = "/start";
	url += isDefined(question_id) ? "/" + question_id : ""
	return url;
}

function getNotesPageUrl(question_id) {
    var url = "/idea";
	url += isDefined(question_id) ? "/" + question_id : ""
	return url;
}

function getCascadePageUrl(question_id) {
    var url = "/cascade";
    url += isDefined(question_id) ? "/" + question_id : ""
	return url;
}

function getResultsPageUrl(question_id) {
	var url = "/results";
	url += isDefined(question_id) ? "/" + question_id : ""
	return url;
}

function getTestResultsPageUrl(question_id) {
	var url = "/results";
	url += isDefined(question_id) ? "/" + question_id : ""
	if (isDefined(question_id)) {
		url += "?test=1"
	}
	return url;
}
 
function getAdminPageUrl(question_id) {
	var url = "/admin";
	url += isDefined(question_id) ? "/" + question_id : ""
	return url;
}

function getLogoutUrl(question_id) {
	var url = "/logout";
	url += isDefined(question_id) ? "/" + question_id : ""
	return url;
}

function redirectToCascadePage(question_id) {
	window.location.href = getCascadePageUrl(question_id);
}

function redirectToResultsPage(question_id) {
	window.location.href = getResultsPageUrl(question_id);
}

function redirectToTestResultsPage(question_id) {
	window.location.href = getTestResultsPageUrl(question_id);
}

function redirectToAdminPage(question_id) {
	window.location.href = getAdminPageUrl(question_id);
}

function redirectToLogout(question_id) {
	window.location.href = getLogoutUrl(question_id);
}

function getURLParameter(name) {
    return decodeURIComponent((new RegExp('[?|&|#]' + name + '=' + '([^&;]+?)(&|#|;|$)').exec(window.location.search)||[,""])[1].replace(/\+/g, '%20'))||null;
}

//=================================================================================
// Language and Stemming
//=================================================================================

function cleanWord(word) {
	var word = word.trim();
	word = word.replace(/[\.,-\/#!$%\^&\*;:{}=\-_'`~()"@+|<>?]/g, "");
	return word;
}

function isStopWord(word) {
	word = word.toLowerCase();
	return $.inArray(word, STOP_WORDS) != -1;
}

//===================================================
// Existence Functions
//===================================================

function isDefined(obj) {
    return !isUndefined(obj);
}

function isUndefined(obj) {
    return typeof(obj) == "undefined" || obj == null;
}

function isFunction(func) {
    return isDefined(func) && typeof(func) == "function";
}

//===================================================
// Misc
//===================================================

function numKeys(a1) {
	var count = 0;
	for (var key in a1) {
		count++;
	}
	return count;
}

function intersection(a1, a2) {
	var intersect = [];
	for (var i = 0; i < a1.length; i++) {
    	if (a2.indexOf(a1[i]) !== -1) {
        	intersect.push(a1[i]);
    	}
	}
	return intersect;
}

function difference(a1, a2) {
	// assumes a2 is subset of a1
	var diff = $(a2).not(a1).get();
	return diff;
}

function sortTuplesAscending(tuples) {		
	tuples.sort(function(tuple1, tuple2) {
		value1 = tuple1[1];
		value2 = tuple2[1];
		return value1 < value2 ? -1 : (value1 > value2 ? 1 : 0);
	});
	return tuples;
}

function sortTuplesDescending(tuples) {		
	tuples.sort(function(tuple1, tuple2) {
		value1 = tuple1[1];
		value2 = tuple2[1];
		return value1 > value2 ? -1 : (value1 < value2 ? 1 : 0);
	});
	return tuples;
}

function showHide(obj, show) {
	if (show) {
		obj.show();
	}
	else {
		obj.hide();
	}
}

function enableDisable(obj, enable) {
	if (enable) {
		obj.removeAttr("disabled");
	}
	else {
		obj.attr("disabled", "disabled");
	}
}

function toHHMMSS(str) {
	var hhmmss = "-";
	if (str) {
    	var sec_num = parseInt(str, 10);
    	var hours   = Math.floor(sec_num / 3600);
    	var minutes = Math.floor((sec_num - (hours * 3600)) / 60);
    	var seconds = sec_num - (hours * 3600) - (minutes * 60);

    	if (hours   < 10) {hours   = "0"+hours;}
    	if (minutes < 10) {minutes = "0"+minutes;}
    	if (seconds < 10) {seconds = "0"+seconds;}
    	hhmmss = hours+':'+minutes+':'+seconds;
    }
    return hhmmss;
}

var entityMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': '&quot;',
    "'": '&#39;',
    "/": '&#x2F;'
  };

function escapeHtml(string) {
    return String(string).replace(/[&<>"'\/]/g, function (s) {
        return entityMap[s];
    });
}

function unescapeHtml(string) {
	var s = new String(string);
    for (var char in entityMap) {
    	var re = new RegExp(entityMap[char], "g");
    	s = s.replace(re, char); 
    }
    return s;
}