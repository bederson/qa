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

// TODO: #msg vs #warning; order of checks

$(document).ready(function() {
	initChannel();
	initEventHandlers();

	if (!logged_in) {
		$("#warning").html("Please log in");
		return;
	}
			
	if (!question_id) {
		$("#warning").html("Question code required");
		return;
	}
		
	if (phase != PHASE_CASCADE) {
		redirectToPhase(phase, question_id);
		return;
	}

	getJob(question_id);
});

function getJob(question_id) {	
	var data = {
		"client_id": client_id,
		"question_id": question_id
	};
	$.post("/cascade_job", data, function(results) {
		updateUI(results);
	}, "json");
}

function updateUI(results) {
	$("#step").html("Step " + results.step + " of 5");
	if (results.step == 1) {
		updateUIForStep1(results);
	}
	else if (results.step == 2) {
		updateUIForStep2(results);
	}
	else {
		$("#task_area").html("Not implemented yet");
	}
}

// step 1: create categories
function updateUIForStep1(results) {
	step1Ideas = [];
	$("#title").html("Create Categories");
	$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");
	if (results.status == 1) {
		var assignment = results.assignment;
		if (assignment && assignment.task) {
			var ideas = assignment.task.ideas;
			var taskHtml = "";
			for (var i=0; i<ideas.length; i++) {
				var idea = ideas[i];
				taskHtml += "<div class=\"largespaceafter\">";
				taskHtml += idea.text + " ";
				taskHtml += "<input id=\"category_"+(i+1)+"\" type=\"text\"/ value=\"\">";
				taskHtml += "</div>\n";
			}
			taskHtml += "<input id=\"num_categories\" type=\"hidden\" value=\"" + ideas.length + "\">";
			taskHtml += "<input id=\"submit_categories_btn\" type=\"button\" value=\"Submit Categories\">";
			$("#task_area").html(taskHtml);
			$("#submit_categories_btn").on("click", { assignment: assignment }, function(event) {
				submitStep1(event.data.assignment);
			});
		}
		else {
			taskHtml = "All tasks for this step have been assigned.<br/>";
			taskHtml += "Please wait for next step to begin.";
			$("#task_area").html(taskHtml);
		}
	}
	else {
		$("#warning").html(results.msg);
	}
}

function submitStep1(assignment) {
	var data = {
		"client_id" : client_id,
		"question_id" : question_id,
		"assignment_id" : assignment.id,
		"num_categories" : parseInt($("#num_categories").val())
	}
	
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

// step 2: select best category
function updateUIForStep2(results) {
	step1Ideas = [];
	$("#title").html("Select Best Category");
	$("#help").html("Vote for the category that you think best fits the note.");
	if (results.status == 1) {
		var assignment = results.assignment
		if (assignment && assignment.task) {
			var taskHtml = "";
			taskHtml += "<div class=\"largespaceafter\">";
			taskHtml += "<div class=\"spaceafter\">" + assignment.task.idea.text + "</div>";
			for (var i=0; i<assignment.task.categories.length; i++) {
				var radioBoxId = "category_rb_"+i;
				taskHtml += "<div class=\"spaceafter\">";
				taskHtml += "<div style=\"float:left;\"><input type=\"radio\" id=\"" + radioBoxId + "\" name=\"suggested_category\" value=\""+i+"\"></div>";
				taskHtml += "<div style=\"float:left; margin-left:5px; width:93%\"><label for=\"" + radioBoxId + "\">" + assignment.task.categories[i] + "</label></div>";
				taskHtml += "<div style=\"clear:both\"></div>";
				taskHtml += "</div>";
			}
			taskHtml += "</div>\n";
			taskHtml += "<input id=\"submit_vote_btn\" type=\"button\" value=\"Submit Vote\">";
			$("#task_area").html(taskHtml);
			$("#submit_vote_btn").on("click", { assignment: assignment }, function(event) {
				submitStep2(event.data.assignment);
			});
		}
		else {
			taskHtml = "All tasks for this step have been assigned.<br/>";
			taskHtml += "Please wait for next step to begin.";
			$("#task_area").html(taskHtml);
		}
	}
	else {
		$("#warning").html(results.msg);
	}
}

function submitStep2(assignment) {
	var bestCategoryIndex = $("input:radio[name=suggested_category]:checked").val();
	if (!bestCategoryIndex) {
		$("#warning").html("Please select an item");
		return;
	}
	
	var data = {
		"client_id" : client_id,
		"question_id" : question_id,
		"assignment_id" : assignment.id,
		"best_category_index" : bestCategoryIndex
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
		redirectToAdminPage(question_id);
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
	$(".white_box").width(width);
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