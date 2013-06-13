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
	
	getJob();
});

function getJob() {
	var data = {
		"question_id" : question_id
	}
	
	$.post("/cascade_job", data, function(results) {
		if (results.status == 0) {
			$("#warning").html(results.msg);
		}
		else {
			$("#warning").html("");
			updateUI(results);
		}
	}, "json");
}

function updateUI(results) {
	if (results.step == 1) {
		updateUIForStep1(results.assignment);
	}
	else {
		$("#task_area").html("Not implemented yet");
	}
}

// step 1: create categories
function updateUIForStep1(assignment) {
	step1Ideas = [];
	$("#title").html("Create Categories");
	$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");
	if (assignment && assignment.task) {
		var taskHtml = "";
		for (var i=0; i<assignment.task.ideas.length; i++) {
			var idea = assignment.task.ideas[i];
			taskHtml += "<div class=\"largespaceafter\">";
			taskHtml += idea.text + " ";
			taskHtml += "<input id=\"category_"+(i+1)+"\" type=\"text\"/ value=\"\">";
			taskHtml += "</div>\n";
		}
		taskHtml += "<input id=\"num_categories\" type=\"hidden\" value=\"" + assignment.task.ideas.length + "\">";
		taskHtml += "<input id=\"submit_categories_btn\" type=\"button\" value=\"Submit Categories\">";
		$("#task_area").html(taskHtml);
		$("#submit_categories_btn").on("click", {assignment: assignment}, function(event) {
			submitStep1(event.data.assignment);
		});
	}
	else {
		taskHtml = "All tasks for this step have been assigned.<br/>";
		taskHtml += "Please wait for next step to begin.";
		$("#task_area").html(taskHtml);
	}
}

function submitStep1(assignment) {
	var data = {
		"question_id" : question_id,
		"assignment_id" : assignment.id
	}
	
	data["num_categories"] = parseInt($("#num_categories").val());
	for (var i=0; i<data["num_categories"]; i++) {
		data["category_"+(i+1)] = $("#category_"+(i+1)).val();	
	}

	$.post("/cascade_job", data, function(results) {
		if (results.status == 0) {
			$("#warning").html(results.msg);
		}
		else {
			$("#warning").html("");
			updateUI(results);
		}
	}, "json");
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
	$(".step").width(width);
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