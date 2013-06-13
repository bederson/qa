// Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
// Anne Rose - http://www.cs.umd.edu/hcil/members/arose
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

$(document).ready(function() {
	initChannel();
	initEventHandlers();

	if (!logged_in) {
		$("#warning").html("Please log in");
		return;
	}
	
	question_id = getURLParameter("question_id");
	if (!question_id) {
		$("#warning").html("Question code required");
		return;
	}
		
	if (phase == -1) {
		$("#warning").html("Invalid question code");
		return;
	}
	
	if (phase != PHASE_CASCADE) {
		$("#warning").html("Not currently using Cascade");
		return;
	}
	
	getTask();
});

function getTask() {
	var data = {
		"question_id" : question_id
	}
	
	$.post("/cascade_step", data, function(results) {
		if (results.status == 0) {
			$("#warning").html(results.msg);
		}
		else {
			$("#warning").html("");
			//current_assignment = results.assignment;
			updateUI(results);
		}
	}, "json");
}

function updateUI(results) {
	// TODO: when step changed, need to notify other clients
	if (cascade_step == 1) {
		$("#title").html("Suggest Categories");
		$("#help").html("Read the ideas below and suggest a category you think each one belongs to");
		// TODO: need to return ideas
		$("#task_area").html("Not implemented yet");
	}
	else {
		$("#task_area").html("Not implemented yet");
	}
}

function initEventHandlers() {
	onResize();
	$(window).resize(function() {
		onResize();
	});

	$("#admin_button").click(function() {
		window.location.href="/admin?question_id=" + question_id;
	});
}

function onResize() {
	var padding = 40;
	if (jQuery.browser.mobile) {
		var width = $(window).width() - padding;
	} else {
		var targetWidth = 550;
		var width = targetWidth;
		if ($(window).width() < (targetWidth + padding)) {
			width = $(window).width() - padding;
		}
	}
	$(".qcontainer").width(width);
}

/////////////////////////
// Channel support
/////////////////////////
function handlePhase(data) {
	window.location.reload();
}

function handleStep(step) {
	window.location.reload();
}