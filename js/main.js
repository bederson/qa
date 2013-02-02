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

	onResize();
	$(window).resize(function() {
		onResize();
	});

	if (!logged_in) {
		disableInput("Please log in to submit a response");
		return;
	}

	$("#answer").focus();	
	$.getJSON("/query", {request: "phase"}, function(data) {
		if (data.phase != 1) {
			disableInput("Not currently accepting new submissions");
		}
		if (data.phase == 2) {
			$("#tag_button").css("display", "inline");
		}
	});
});

function disableInput(msg) {
	$("#answer").attr("disabled", "disabled");
	$("#submit").attr("disabled", "disabled");
	$("#answer").val(msg);
}

function initEventHandlers() {
	$("#submit").click(function() {
		var idea = $("#answer").val();
		var data = {
			"client_id": client_id,
			"idea": idea
		};
		$.post("/new", data, function() {
			$("#thankyou").css("display", "inline");
			$("#answer").val("");
			$("#answer").focus();
			updateRemainingChars();
		});
	});

	$("#answer").keyup(function() {
		updateRemainingChars();
	});

	$("#admin_button").click(function() {
		window.location.href="/admin";
	});
	$("#tag_button").click(function() {
		window.location.href="/tag";
	});
}

function updateRemainingChars() {
	var maxChars = 250;
	var text = $("#answer").val();
	if (text.length > maxChars) {
		text = text.slice(0, maxChars);
		$(this).val(text);
	}
	var msg = (maxChars - text.length) + " chars left";
	$("#charlimit").html(msg);
}

function onResize() {
	var padding = 40;

	if (jQuery.browser.mobile) {
		var width = $(window).width() - padding;
	} else {
		var targetWidth = 600;
		var width = targetWidth;
		if ($(window).width() < (targetWidth + padding)) {
			width = $(window).width() - padding;
		}
	}

	$("#qcontainer").width(width);
	$("#answer").width(width - 6);
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

function handleTag(data) {
	// Ignore it
}