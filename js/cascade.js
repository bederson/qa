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
	else if (results.step == 3) {
		updateUIForStep3(results);
	}
	else {
		$("#title").html("");
		$("#help").html("");
		$("#task_area").html("Not implemented yet");
	}
}

// step 1: suggest categories
function updateUIForStep1(results) {
	$("#title").html("Suggest Categories");
	$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length > 0) {
			var taskHtml = "";
			for (var i=0; i<tasks.length; i++) {
				var task = tasks[i];
				taskHtml += "<div class=\"largespaceafter\">";
				taskHtml += task.idea + "<br/>";
				taskHtml += "<input class=\"suggested_category\" id=\"category_"+task.id+"\" type=\"text\"/ value=\"\">";
				taskHtml += "</div>\n";
			}
			taskHtml += "<input id=\"submit_btn\" type=\"button\" value=\"Submit Categories\">";
			$("#task_area").html(taskHtml);
			$("#submit_btn").click(function(event) {
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
	$("#help").html("Vote for the category that you think best fits this note.");
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length == 1) {
			var task = tasks[0];
			var taskHtml = "";
			taskHtml += "<div class=\"largespaceafter\">";
			taskHtml += "<div class=\"green_highlight spaceafter\">" + task.idea + "</div>";
			for (var i=0; i<task.suggested_categories.length; i++) {
				var radioBoxId = "category_rb_"+i;
				taskHtml += "<div class=\"spaceafter\">";
				taskHtml += "<input type=\"radio\" name=\"suggested_category\" value=\"" + i + "\">";
				taskHtml += task.suggested_categories[i];
				taskHtml += "</div>";
			}
			if (task.suggested_categories.length > 0) {
				taskHtml += "<div class=\"spaceafter\">";
				taskHtml += "<input type=\"radio\" name=\"suggested_category\" value=\"-1\">";
				taskHtml += "None of the above";
				taskHtml += "</div>";
			}
			taskHtml += "</div>\n";
			taskHtml += "<input id=\"submit_btn\" type=\"button\" value=\"Submit Vote\">";
			$("#task_area").html(taskHtml);
			$("#submit_btn").on("click", { task : task }, function(event) {
				submitStep2(event.data.task);
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

function submitStep2(task) {
	var bestCategoryIndex = $("input:radio[name=suggested_category]:checked").val();
	if (!bestCategoryIndex) {
		$("#warning").html("Please select an item");
		return;
	}
	
	var job = [];
	var bestCategory = bestCategoryIndex != -1 ? task.suggested_categories[bestCategoryIndex] : ""
	job.push({ id: task.id, best_category: bestCategory });	
		
	var data = {
		"client_id" : client_id,
		"question_id" : question_id,
		"step" : 2,
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

// step 3: do categories fit
function updateUIForStep3(results) {
	$("#title").html("Check Categories");
	$("#help").html("Select whether or not these categories fit this note.");
	$("#msg").html("");
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length > 0) {
			var taskHtml = "";
			for (var i=0; i<tasks.length; i++) {
				var task = tasks[i];
				if (i==0) {
					taskHtml += "<div class=\"green_highlight spaceafter\">";
					taskHtml += task.idea;
					taskHtml += "</div>";
					taskHtml += "<table class=\"spaceafter\">";
					taskHtml += "<tr>";
					taskHtml += "<td class=\"small\" style=\"text-align:center;\">Y</td>";
					taskHtml += "<td class=\"small\" style=\"text-align:center;\">N</td>";
					taskHtml += "<td>&nbsp;</td>";
					taskHtml += "</tr>\n";
				}
				taskHtml += "<tr>";
				taskHtml += "<td><input type=\"radio\" class=\"category_fit\" name=\"category_fit_"+task.id+"\" value=\"1\"></td>";
				taskHtml += "<td><input type=\"radio\" class=\"catgetory_fit\" name=\"category_fit_"+task.id+"\" value=\"0\"></td>";
				taskHtml += "<td>" + task.category + "</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "</table>";
			taskHtml += "<input id=\"submit_btn\" type=\"button\" value=\"Submit\">";
			$("#task_area").html(taskHtml);
			$("#submit_btn").on("click", { tasks: tasks }, function(event) {
				submitStep3(event.data.tasks);
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

function submitStep3(tasks) {
	var job = [];	
	$("input:radio").each(function() {
		var rb = $(this);
		if (rb.is(":checked")) {
			var rb_name = rb.attr("name");
			var task_id = rb_name.replace("category_fit_","");
			job.push({ id: task_id, fit: rb.val() == "1" ? 1 : 0 });	
		}
	});

	if (tasks.length!=job.length) {
		$("#msg").html("Please indicate whether each category fits or not");
		return;
	}
	
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