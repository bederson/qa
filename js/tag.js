// Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
// University of Maryland
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
// 
//     http://www.apache.org/licenses/LICENSE-2.0
// 
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

var mytags = [];

$(function() {
	initChannel();
	initEventHandlers();

	onResize();
	$(window).resize(function() {
		onResize();
	});
	
	if (!logged_in) {
		disableInput("Please log in to submit a response");
		return;
	}

	$("#taganswer").focus();
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "phase",
		"question_id": question_id
	}
	$.getJSON("/query", data, function(requests) {
		if (requests.phase == 2) {
			enableInput();
		} else {
			disableInput("Not currently accepting new submissions");
		}
	});

	displayTags();
	displayIdeas();
});

function initEventHandlers() {
	$("#submit").click(function() {
		submitTag();
	});

	$("#taganswer").on("keydown", function(evt) {
		// Return
		if (evt.keyCode == 13) {
			submitTag();
		}
	});
	$("#taganswer").keyup(function() {
		updateRemainingChars();
	});

	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href="/admin?question_id=" + question_id;
	});
}

// Shouldn't have to enableInput, but Firefox strangely caches state of elements.
// Without explicitly enabling input, Firefox will remain disabled after phase change - even on reload
function enableInput() {
	$("#taganswer").removeAttr("disabled");
	$("#submit").removeAttr("disabled");
	$("#taganswer").val("");
	$("#taganswer").focus();
}

function disableInput(msg) {
	$("#taganswer").attr("disabled", "disabled");
	$("#submit").attr("disabled", "disabled");
	$("#taganswer").val(msg);
}

function submitTag() {
	var tag = $("#taganswer").val().trim();
	if (tag.length == 0) {
		// Don't submit blank tags
		return;
	}
	if (mytags.indexOf(tag) != -1) {
		// Whoops - tag already in list
		$("#thankyou").css("display", "none");
		$("#nodups").css("display", "inline");
		$("#taganswer").select();
		return;
	}
	mytags.push(tag);

	var question_id = getURLParameter("question_id");
	var data = {
		"client_id": client_id,
		"tag": tag,
		"cluster_index": cluster_index,
		"question_id": question_id
	};
	$.post("/newtag", data);

	$("#thankyou").css("display", "inline");
	$("#nodups").css("display", "none");
	$("#taganswer").val("");
	$("#taganswer").focus();
	updateRemainingChars();
	
	$("#newtags").append("<li>" + tag);
}

function onResize() {
	var padding = 40;

	if (jQuery.browser.mobile) {
		var width = $(window).width() - padding;
	} else {
		var targetWidth = 500;
		var width = targetWidth;
		if ($(window).width() < (targetWidth + padding)) {
			width = $(window).width() - padding;
		}
	}

	$("#qcontainer").width(width);
	$("#taganswer").width(width - 6);
}

function updateRemainingChars() {
	var maxChars = 50;
	var box = $("#taganswer");
	var text = box.val();
	if (text.length > maxChars) {
		text = text.slice(0, maxChars);
		box.val(text);
	}
	var msg = (maxChars - text.length) + " chars left";
	$("#charlimit").html(msg);
}

function displayTags() {
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "mytags",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		var tags = results.tags;
		var html = "My tags:<br><ul>";
		for (i in tags) {
			var tag = tags[i];
			mytags.push(tag);
			html += "<li>" + tag
		}
		html += "<div id='newtags'></div>";
		html += "</ul>";
		$("#mytags").html(html);
	});
}

function displayIdeas() {
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas", 
		"cluster_index": cluster_index,
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		var html = "Notes:<br><ul>";
		for (i in results) {
			var idea = results[i].idea;
			html += "<li>" + idea
		}
		html += "</ul>";
		$("#clusteredIdeas").html(html);
	});
}

/////////////////////////
// Channel support
/////////////////////////
function handleNew(data) {
	// Ignore it
}

function handleRefresh(data) {
	window.location.reload();
}

function handlePhase(data) {
	window.location.reload();
}

function handleTag(data) {
	// Ignore it
}