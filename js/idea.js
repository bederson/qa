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
	var question_id = getURLParameter("question_id");

	var data = {
		"request": "question",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(data) {
		$("#title").html(data.title);
		$("#question").html(data.question);
	});

	var data = {
		"request": "phase",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(data) {
		if (data.phase == 1) {
			enableInput();
		} else {
			disableInput("Not currently accepting new submissions");
		}
		if (data.phase == 2) {
			$("#start_tagging").css("display", "inline");
		}
	});
});

// Shouldn't have to enableInput, but Firefox strangely caches state of elements.
// Without explicitly enabling input, Firefox will remain disabled after phase change - even on reload
function enableInput() {
	$("#answer").removeAttr("disabled");
	$("#submit").removeAttr("disabled");
	$("#answer").val("");
	$("#answer").focus();
}

function disableInput(msg) {
	$("#answer").attr("disabled", "disabled");
	$("#submit").attr("disabled", "disabled");
	$("#answer").val(msg);
}

function initEventHandlers() {
	$("#submit").click(function() {
		$("#submit").attr("disabled", "disabled");
		var question_id = getURLParameter("question_id");
		var idea = $("#answer").val();
		var data = {
			"client_id": client_id,
			"idea": idea,
			"question_id": question_id
		};
		$.post("/newidea", data, function() {
			$("#submit").removeAttr("disabled");
			$("#thankyou").css("display", "inline");
			$("#results_link").attr("href", "/results?question_id=" + question_id);
			$("#answer").val("");
			$("#answer").focus();
			updateRemainingChars();
		});
	});

	$("#answer").keyup(function() {
		updateRemainingChars();
	});

	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href="/admin?question_id=" + question_id;
	});
	$("#tag_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href="/tag?question_id=" + question_id;
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