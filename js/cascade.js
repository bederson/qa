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
	if ($("#msg").html()) {
		return;
	}
	
	initChannel();
	initEventHandlers();
		
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

// step 1: suggest categories
function updateUIForStep1(results) {
	step1Ideas = [];
	$("#title").html("Suggest Categories");
	$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length > 0) {
			var taskHtml = "";
			for (var i=0; i<tasks.length; i++) {
				var task = tasks[i];
				taskHtml += "<div class=\"largespaceafter\">";
				taskHtml += task.idea + " ";
				taskHtml += "<input class=\"suggested_category\" id=\"category_"+task.id+"\" type=\"text\"/ value=\"\">";
				taskHtml += "</div>\n";
			}
			taskHtml += "<input id=\"submit_categories_btn\" type=\"button\" value=\"Submit Categories\">";
			$("#task_area").html(taskHtml);
			$("#submit_categories_btn").click(function(event) {
				submitStep1();
			});
		}
		else {
			taskHtml = "You have completed all tasks for this step.<br/>";
			taskHtml += "Please wait for next step to begin.";
			$("#task_area").html(taskHtml);
		}
	}
	else {
		$("#warning").html(results.msg);
	}
}

function submitStep1() {
	var job = [];
	$(".suggested_category").each(function() {
		var textbox = $(this);
		var textbox_id = textbox.attr("id");
		var task_id = textbox_id.replace("category_","");
		job.push({ id: task_id, suggested_category: textbox.val() });	
	});
		
	var data = {
		"client_id" : client_id,
		"question_id" : question_id,
		"step" : 1,
		"job" : $.toJSON(job)
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
	$("#title").html("Select Best Category");
	$("#help").html("Vote for the category that you think best fits the note.");
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length == 1) {
			var task = tasks[0];
			var taskHtml = "";
			taskHtml += "<div class=\"largespaceafter\">";
			taskHtml += "<div class=\"spaceafter\">" + task.idea + "</div>";
			alert(task.suggested_categories);
			for (var i=0; i<task.suggested_categories.length; i++) {
				var radioBoxId = "category_rb_"+i;
				taskHtml += "<div class=\"spaceafter\">";
				taskHtml += "<div style=\"float:left;\"><input type=\"radio\" id=\"" + radioBoxId + "\" name=\"suggested_category\" value=\""+i+"\"></div>";
				taskHtml += "<div style=\"float:left; margin-left:5px; width:93%\"><label for=\"" + radioBoxId + "\">" + task.categories[i] + "</label></div>";
				taskHtml += "<div style=\"clear:both\"></div>";
				taskHtml += "</div>";
			}
			taskHtml += "</div>\n";
			taskHtml += "<input id=\"submit_vote_btn\" type=\"button\" value=\"Submit Vote\">";
			$("#task_area").html(taskHtml);
			$("#submit_vote_btn").click(function(event) {
				submitStep2();
			});
		}
		else {
			taskHtml = "You have completed all task for this step.<br/>";
			taskHtml += "Please wait for next step to begin.";
			$("#task_area").html(taskHtml);
		}
	}
	else {
		$("#warning").html(results.msg);
	}
}

function submitStep2() {
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

function handleStep(data) {
	alert("cascade step changed!");
	window.location.reload();
}