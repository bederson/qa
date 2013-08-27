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

// TODO: remove step from variable names

var waiting = false;
var assignedJob = null;

$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}
			
	initChannel();
	initEventHandlers();
	
	$("#page_content").show();
	saveAndGetNextJob();
});

function saveAndGetNextJob(tasksToSave) {	
	var data = {
		"client_id" : client_id,
		"question_id" : question_id
	};
	
	if (isDefined(tasksToSave)) {
		data["job"] = $.toJSON({
			"tasks" : tasksToSave,
			"type" : assignedJob.type
		});
	}
	
	$("#loading_icon").show();
	
	$.post("/cascade_job", data, function(results) {
		assignedJob = null;
		if (results.status == 0) {
			$("#warning").html(results.msg);
		}
		else {
			$("#warning").html("");
			assignedJob = results.job;
			updateUI(results.cascade_complete);
		}
	}, "json");
}

function updateUI(complete) {
	waiting = false;
		
	// show results
	if (complete == 1) {
		resultsReady();
	}
	
	// if no job, wait for next one to become available
	else if (!assignedJob) {
		waitForNextJob();
	}
		
	// suggest categories
	else if (assignedJob.type == SUGGEST_CATEGORY) {
		updateUIForStep1();
	}
	
	// select best category
	else if (assignedJob.type == BEST_CATEGORY) {
		updateUIForStep2();
	}
	
	// do categories fit
	// do subsequent categories fit
	else if (assignedJob.type == MATCH_CATEGORY || assignedJob.type == VERIFY_CATEGORY) {
		updateUIForStep3();
	}
	
	else {
		updateTitleArea();
		$("#task_area").html("Not implemented yet");
	}
}

function updateTitleArea() {
	$("#msg").html("");

	if (!assignedJob) {
		$("#title").html("Create Categories");
		$("#help").html("");
	}
	else if (assignedJob.type == SUGGEST_CATEGORY) {
		$("#title").html("Suggest Categories");
		$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");
	}
	else if (assignedJob.type == BEST_CATEGORY) {
		$("#title").html("Select Best Category");
		$("#help").html("Pick the one category that best fits this note.");
	}
	else if (assignedJob.type == MATCH_CATEGORY) {
		$("#title").html("Match Categories");
		$("#help").html("Select whether or not each category fits this note.");
	}
	else if (assignedJob.type == VERIFY_CATEGORY) {
		$("#title").html("Verify Categories");
		$("#help").html("Select whether or not each category fits this note.");
	}
	// TODO: make sure additional categories matched (if any)
	else {
		$("#title").html("");
		$("#help").html("");
	}
}

// step 1: suggest categories
function updateUIForStep1() {
	updateTitleArea();
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];				
			taskHtml += "<div class='largespacebelow'>";
			taskHtml += "<div class='green_highlight smallspacebelow'>" + task.idea + "</div>";
			taskHtml += "<input class='suggested_category' id='category_"+task.id+"' type='text' value='' size='30'>";
			taskHtml += "</div>\n";
		}
		taskHtml += "<input id='submit_btn' type='button' value='Submit Categories'> ";
		taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitStep1();
		});
	}
}

function submitStep1() {
	var tasks = [];
	var skipCount = 0;
	$(".suggested_category").each(function() {
		var textbox = $(this);
		var textbox_id = textbox.attr("id");
		var task_id = textbox_id.replace("category_","");
		var suggested_category = textbox.val();
		tasks.push({ id: task_id, suggested_category: suggested_category });	
		if (suggested_category == "") {
			skipCount++;
		}
	});
		
	if (skipCount > 2) {
		$("#warning").html("You may only skip 2 notes");
		return;
	}
	
	saveAndGetNextJob(tasks);
}

// step 2: select best category
function updateUIForStep2() {
	updateTitleArea();
	var tasks = assignedJob.tasks;
	if (tasks.length == 1) {
		var task = tasks[0];
		var taskHtml = "";
		taskHtml += "<div class='largespacebelow'>";
		taskHtml += "<div class='green_highlight largespacebelow'>" + task.idea + "</div>";
		taskHtml += "<div class='note smallspacebelow'>Best?</div>";
		for (var i=0; i<task.suggested_categories.length; i++) {
			var radioBoxId = "category_rb_"+i;
			taskHtml += "<div class='spacebelow'>";
			taskHtml += "<input type='radio' name='suggested_category' value='" + i + "'>";
			taskHtml += task.suggested_categories[i];
			taskHtml += "</div>";
		}
		if (task.suggested_categories.length > 0) {
			taskHtml += "<div class='spacebelow'>";
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
}

function submitStep2(task) {
	var bestCategoryIndex = $("input:radio[name=suggested_category]:checked").val();
	if (!bestCategoryIndex) {
		$("#warning").html("Please select the best category");
		return;
	}
	
	var tasks = [];
	var bestCategory = bestCategoryIndex != -1 ? task.suggested_categories[bestCategoryIndex] : ""
	tasks.push({ id: task.id, best_category: bestCategory });
	saveAndGetNextJob(tasks);
}

// step 3: match categories (initial set)
// step 4: verify categories (initial set)
// step 5: match categories (subsequent set)
function updateUIForStep3() {
	updateTitleArea();
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			if (i==0) {
				taskHtml += "<div class='green_highlight largespacebelow'>";
				taskHtml += task.idea;
				taskHtml += "</div>";
				taskHtml += "<div class='small'>Fits?</div>";
				taskHtml += "<table class='spacebelow'>";
				taskHtml += "<tr>";
				taskHtml += "<td class='note' style='text-align:center'>Y</td>";
				taskHtml += "<td class='note' style='text-align:center'>N</td>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "<tr>";
			taskHtml += "<td><input type='radio' class='category_fit' name='category_fit_"+task.id+"' value='1'></td>";
			taskHtml += "<td><input type='radio' class='catgetory_fit' name='category_fit_"+task.id+"' value='0' checked='checked'></td>";
			taskHtml += "<td>" + task.category + "</td>";
			taskHtml += "</tr>\n";
		}
		taskHtml += "</table>";
		taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
		taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitStep3();
		});
	}
}

// TODO: rename functions

function submitStep3() {
	var tasks = [];	
	$("input:radio").each(function() {
		var rb = $(this);
		if (rb.is(":checked")) {
			var rb_name = rb.attr("name");
			var task_id = rb_name.replace("category_fit_","");
			tasks.push({ id: task_id, fit: rb.val() == "1" ? 1 : 0 });	
		}
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#warning").html("Please indicate whether each category fits or not");
		return;
	}
	
	saveAndGetNextJob(tasks);
}

function cancelCascadeJob() {
	if (assignedJob.length > 0) {
		var data = {
			"client_id" : client_id,
			"question_id" : question_id,
			"job" : $.toJSON(assignedJob)
		}
		$.post("/cancel_cascade_job", data);
	}
}

function waitForNextJob() {
	updateTitleArea();
	var taskHtml = "Please wait until more jobs become available. ";
	///taskHtml += "<img id='loading_icon' src='images/loading.gif' />";
	$("#task_area").html(taskHtml);
	waiting = true;
}

// cascade complete
function resultsReady() {
	// TODO: automatically go to results page
	$("#step").html("&nbsp;");
	$("#title").html("Categories Complete");
	$("#help").html("");
	$("#msg").html("");
	var html = "The categories have been created for this question.</br>";
	html += "<div class='spaceabove spacebelow'><input id='results_btn' type='button' value='View results'></div>";
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
	
	$("#login_logout_link").click(function() {
		if (logged_in) {
			cancelCascadeJob();
			return true;
		}
	});
	
	// if a user closes the window/tab or browses to another url
	// before they submit their job, notify the server
	$(window).on('beforeunload', function() {
		cancelCascadeJob();
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
	$("#box_area").width(width);
}

/////////////////////////
// Channel support
/////////////////////////

function handleDisable(data) {
	$("#msg").html("Question has been disabled");
	$("#page_content").hide();
}

function handleIdea(data) {
	if (waiting) {
		saveAndGetNextJob();
	}
}

function handleMoreJobs(data) {
	if (waiting) {
		var html = "A few more tasks have become available for this step.<br/>";
		html += "Check to see if there are any you can help complete.";
		html += "<div class='spaceabove spacebelow'><input id='next_task_button' type='button' value='Get task'></div>";
		$("#task_area").html(html);
		
		$('#next_task_button').click(function() {
			saveAndGetNextJob();
		});
	}
}

function handleResults(data) {
	resultsReady();
}

function handleLogout(data) {
	cancelCascadeJob();
	redirectToLogout(question_id);
}