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

$(function() {
	initChannel();
	initEventHandlers();

	if (logged_in) {
		$("#taganswer").focus();
	}

	$.getJSON("/query", {request: "phase"}, function(data) {
		if (data.phase != 2) {
			disableInput("Not currently accepting new submissions");
		}
	});

	onResize();
	$(window).resize(function() {
		onResize();
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
		window.location.href="/admin";
	});
}

function disableInput(msg) {
	$("#taganswer").attr("disabled", "disabled");
	$("#submit").attr("disabled", "disabled");
	$("#taganswer").val(msg);
}

function submitTag() {
	var tag = $("#taganswer").val();
	var data = {
		"client_id": client_id,
		"tag": tag,
		"cluster_index": cluster_index
	};
	$.post("/newtag", data);

	$("#thankyou").css("display", "inline");
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
	$.getJSON("/query", {request: "mytags"}, function(data) {
		var tags = data.tags;
		var html = "My tags:<br><ul>";
		for (i in tags) {
			var tag = tags[i];
			html += "<li>" + tag
		}
		html += "<div id='newtags'></div>";
		html += "</ul>";
		$("#mytags").html(html);
	});
}

function displayIdeas() {
	$.getJSON("/query", {request: "ideas", cluster_index: cluster_index}, function(data) {
		var html = "Notes:<br><ul>";
		for (i in data) {
			var idea = data[i].idea;
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
	// Ignore it
}

function handlePhase(data) {
	window.location.reload();
}