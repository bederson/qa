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

var waiting = false;

$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}
	
	if (phase != PHASE_CASCADE) {
		redirectToPhase(question_id, phase);
		return;
	}
		
	initChannel();
	initEventHandlers();
	
	$("#page_content").show();
	saveAndGetNextJob();
});

function saveAndGetNextJob(jobToSave) {	
	var data = {
		"client_id" : client_id,
		"question_id" : question_id
	}
	
	if (isDefined(jobToSave)) {
		data["job"] = $.toJSON(jobToSave);
	}
	
	$("#loading_icon").show();
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
	waiting = false;
		
	// show results
	if (results.complete == 1) {
		resultsReady();
	}
	// step 1: suggest categories
	else if (results.step == 1) {
		updateUIForStep1(results);
	}
	// step 2: select best category
	else if (results.step == 2) {
		updateUIForStep2(results);
	}
	// step 3/4: do categories fit
	// step 5/6: do subsequent categories fit
	else if (results.step >= 3) {
		updateUIForStep3(results);
	}
	else {
		updateTitleArea(results);
		$("#task_area").html("Not implemented yet");
	}
}

function updateTitleArea(results) {
	$("#step").html("Step " + results.step + " of " + num_steps);
	$("#msg").html("");

	if (results.step == 1) {
		$("#title").html("Suggest Categories");
		$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");
	}
	else if (results.step == 2) {
		$("#title").html("Select Best Category");
		$("#help").html("Pick the one category that best fits this note.");
	}
	else if (results.step >= 3 && results.step <= 6) {
		var stepPhase = results.step == 3 || results.step == 5 ? 1 : 2;
		$("#title").html("Check " + (results.step>4 ? "Subsequent " : "") + "Categories (Phase " + stepPhase + ")");
		$("#help").html("Select whether or not each category fits this note.");
	}
	else {
		$("#title").html("");
		$("#help").html("");
	}
}

// step 1: suggest categories
function updateUIForStep1(results) {
	updateTitleArea(results);
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length > 0) {
			var taskHtml = "";
			for (var i=0; i<tasks.length; i++) {
				var task = tasks[i];				
				taskHtml += "<div class='largespaceafter'>";
				taskHtml += "<div class='green_highlight smallspaceafter'>" + task.idea + "</div>";
				taskHtml += "<input class='suggested_category' id='category_"+task.id+"' type='text' value='' size='30'>";
				taskHtml += "</div>\n";
			}
			taskHtml += "<input id='submit_btn' type='button' value='Submit Categories'> ";
			taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
			$("#task_area").html(taskHtml);
			$("#submit_btn").on("click", { tasks : tasks }, function(event) {
				submitStep1(event.data.tasks);
			});
		}
		else {
			updateStatus(results);
		}
	}
	else {
		$("#warning").html(results.msg);
	}
}

function submitStep1(tasks) {
	var job = [];
	var skipCount = 0;
	$(".suggested_category").each(function() {
		var textbox = $(this);
		var textbox_id = textbox.attr("id");
		var task_id = textbox_id.replace("category_","");
		var suggested_category = textbox.val();
		job.push({ id: task_id, suggested_category: suggested_category });	
		if (suggested_category == "") {
			skipCount++;
		}
	});
		
	if (skipCount > 2) {
		$("#warning").html("You may only skip 2 notes");
		return;
	}
	
	saveAndGetNextJob(job);
}

// step 2: select best category
function updateUIForStep2(results) {
	updateTitleArea(results);
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length == 1) {
			var task = tasks[0];
			var taskHtml = "";
			taskHtml += "<div class='largespaceafter'>";
			taskHtml += "<div class='green_highlight largespaceafter'>" + task.idea + "</div>";
			taskHtml += "<div class='note smallspaceafter'>Best?</div>";
			for (var i=0; i<task.suggested_categories.length; i++) {
				var radioBoxId = "category_rb_"+i;
				taskHtml += "<div class='spaceafter'>";
				taskHtml += "<input type='radio' name='suggested_category' value='" + i + "'>";
				taskHtml += task.suggested_categories[i];
				taskHtml += "</div>";
			}
			if (task.suggested_categories.length > 0) {
				taskHtml += "<div class='spaceafter'>";
				taskHtml += "<input type='radio' name='suggested_category' value='-1'>";
				taskHtml += "None of the above";
				taskHtml += "</div>";
			}
			taskHtml += "</div>\n";
			taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
			taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
			$("#task_area").html(taskHtml);
			$("#submit_btn").on("click", { task : task }, function(event) {
				submitStep2(event.data.task);
			});
		}
		else {
			updateStatus(results);
		}
	}
	else {
		$("#warning").html(results.msg);
	}
}

function submitStep2(task) {
	var bestCategoryIndex = $("input:radio[name=suggested_category]:checked").val();
	if (!bestCategoryIndex) {
		$("#warning").html("Please select the best category");
		return;
	}
	
	var job = [];
	var bestCategory = bestCategoryIndex != -1 ? task.suggested_categories[bestCategoryIndex] : ""
	job.push({ id: task.id, best_category: bestCategory });
	saveAndGetNextJob(job);
}

// steps 3-4: do categories fit (initial set)
// steps 5-6: do categories fit (subsequent set)
function updateUIForStep3(results) {
	updateTitleArea(results);
	if (results.status == 1) {
		var tasks = results.job;
		if (tasks.length > 0) {
			var taskHtml = "";
			for (var i=0; i<tasks.length; i++) {
				var task = tasks[i];
				if (i==0) {
					taskHtml += "<div class='green_highlight largespaceafter'>";
					taskHtml += task.idea;
					taskHtml += "</div>";
					taskHtml += "<div class='small'>Fits?</div>";
					taskHtml += "<table class='spaceafter'>";
					taskHtml += "<tr>";
					taskHtml += "<td class='note' style='text-align:center'>Y</td>";
					taskHtml += "<td class='note' style='text-align:center'>N</td>";
					taskHtml += "<td>&nbsp;</td>";
					taskHtml += "</tr>\n";
				}
				taskHtml += "<tr>";
				taskHtml += "<td><input type='radio' class='category_fit' name='category_fit_"+task.id+"' value='1'></td>";
				taskHtml += "<td><input type='radio' class='catgetory_fit' name='category_fit_"+task.id+"' value='0'></td>";
				taskHtml += "<td>" + task.category + "</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "</table>";
			taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
			taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
			$("#task_area").html(taskHtml);
			$("#submit_btn").on("click", { tasks: tasks }, function(event) {
				submitStep3(event.data.tasks);
			});
		}
		else {
			updateStatus(results);
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
		$("#warning").html("Please indicate whether each category fits or not");
		return;
	}
	
	saveAndGetNextJob(job);
}

function updateStatus(results) {
	if (results.complete == 1) {
		resultsReady();
	}
	else {
		waitForNextStep(results);
	}
}

function waitForNextStep(results) {
	updateTitleArea(results);
	var taskHtml = "You have completed all your tasks for this step.<br/>";
	taskHtml += "The next step will begin once everyone finishes their tasks.<br/><br/>";
	taskHtml += "Please wait ...";
	$("#task_area").html(taskHtml);
	waiting = true;
}

// cascade complete
function resultsReady() {
	$("#title").html("Categories Complete");
	$("#help").html("");
	$("#msg").html("");
	var html = "The categories have been created for this question.</br>";
	html += "<div class='spaceabove spaceafter'><input id='results_btn' type='button' value='View results'></div>";
	$("#task_area").html(html);
	
	$("#results_btn").click(function() {
		redirectToResultsPage(question_id);
	});
}

function initEventHandlers() {
	onResize();
	$(window).resize(function() {
		onResize();
	});

	$("#admin_button").click(function() {
		redirectToAdminPage(question_id);
	});
	
	$("#next_task_button").click(function() {
		saveAndGetNextJob();
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

function handleDisable(data) {
	$("#msg").html("Question has been disabled");
	$("#page_content").hide();
}

function handlePhase(data) {
	window.location.reload();
}

function handleStep(data) {
	if (waiting) {
		updateTitleArea(data);
		var html = "";
		if (data.step == 1 && data.iteration > 1) {
			html += "<div class='yellow_highlight'>";
			html += "Several notes were not categorized on the first pass.<br/>";
			html += "Let's try one more time to categorize them.";
			html += "</div>";
		}
		else {
			html += "This step has started.<br/>";
		}
		html += "<div class='spaceabove spaceafter'><input id='next_task_button' type='button' value='Get task'></div>";
		$("#task_area").html(html);
		
		$('#next_task_button').click(function() {
			saveAndGetNextJob();
		});
	}
}

function handleMoreJobs(data) {
	if (waiting) {
		var html = "A few more tasks have become available for this step.<br/>";
		html += "Check to see if there are any you can help complete.";
		html += "<div class='spaceabove spaceafter'><input id='next_task_button' type='button' value='Get task'></div>";
		$("#task_area").html(html);
		
		$('#next_task_button').click(function() {
			saveAndGetNextJob();
		});
	}
}

function handleResults(data) {
	resultsReady();
}