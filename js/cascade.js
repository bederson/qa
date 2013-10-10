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

var assignedJob = null;
var loading = false;
var waiting = false;

$(document).ready(function() {
	onResize();
	initEventHandlers();

	if ($("#msg").html()) {
		return;
	}
		
	initChannel(onChannelOpen);	
	$("#page_content").show();
});

function onChannelOpen() {
	// new job sent via message so must
	// waiting for channel to open before
	// requesting first job	
	saveAndRequestNewJob();
}

function saveAndRequestNewJob(tasksToSave) {
	var data = {
		"client_id" : client_id,
		"question_id" : question_id,
		"waiting" : waiting ? "1" : "0"
	};
	if (isDefined(tasksToSave)) {
		data["job"] = $.toJSON({
			"tasks" : tasksToSave,
			"type" : assignedJob.type
		});
	}

	loading = true;
	assignedJob = null;
	waitForJobToLoad();
	
	$.post("/cascade_job", data, function(results) {
		if (results.status == 0) {
			$("#warning").html(results.msg);
			return;
		}

		// new job (if any) sent via "job" message		
		$("#warning").html("");
	}, "json");
}

function unloadPage(redirectUrl) {
	redirectUrl = isDefined(redirectUrl) ? redirectUrl : null;
	// if assigned job, cancel it before unloading page
	if (assignedJob) {
		var data = {
			"client_id" : client_id,
			"question_id" : question_id,
			"job" : $.toJSON(assignedJob)
		}
		$.post("/cancel_cascade_job", data, function(results) {
			if (redirectUrl) {
				window.location.href = redirectUrl;
			}
		}, "json");
	}
	else if (redirectUrl) {
		window.location.href = redirectUrl;
	}
}

function updateUI(complete) {		
	// show results
	if (complete == 1) {
		resultsReady();
	}
	
	// if no job, wait for one to become available
	else if (waiting) {
		waitForNextJob();
	}
	
	// if waiting for requested job
	else if (loading) {
		waitForJobToLoad();
	}
		
	// suggest categories
	else if (assignedJob.type == SUGGEST_CATEGORY) {
		suggestCategoryUI();
	}
	
	// select best category
	else if (assignedJob.type == BEST_CATEGORY) {
		bestCategoryUI();
	}

	// indicate if categories are equal to each other
	else if (assignedJob.type == EQUAL_CATEGORY) {
		equalCategoryUI();
	}
		
	// do categories fit
	else if (assignedJob.type == FIT_CATEGORY) {
		fitCategoryUI();
	}
}

function suggestCategoryUI() {
	$("#title").html("Suggest Categories");
	$("#help").html("Read the notes below and suggest a category for each one.<br/>If you can not think of a good category, skip that note.");	
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];				
			taskHtml += "<div class='largespacebelow'>";
			taskHtml += "<div class='green_highlight smallspacebelow'>" + task.idea + "</div>";
			taskHtml += "<input class='suggested_category' id='category_"+task.id+"' type='text' value='' size='30'>";
			taskHtml += "<input type='hidden' id='idea_"+task.id+"' value='"+task.idea_id+"'>";
			taskHtml += "</div>\n";
		}
		taskHtml += "<input id='submit_btn' type='button' value='Submit Categories'> ";
		taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitSuggestedCategories();
		});
	}
}

function submitSuggestedCategories() {
	var tasks = [];
	var skipCount = 0;
	$(".suggested_category").each(function() {
		var textbox = $(this);
		var textbox_id = textbox.attr("id");
		var task_id = textbox_id.replace("category_","");
		var idea_id = $("#idea_"+task_id).val();
		var suggested_category = textbox.val();
		tasks.push({ id: task_id, idea_id: idea_id, suggested_category: suggested_category });	
		if (suggested_category == "") {
			skipCount++;
		}
	});
		
	if (skipCount > 2) {
		$("#warning").html("You may only skip 2 notes");
		return;
	}
	
	saveAndRequestNewJob(tasks);
}

function bestCategoryUI() {
	$("#title").html("Select Best Category");
	$("#help").html("Pick the one category that best fits this note.");
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
			submitBestCategory(event.data.task);
		});
	}
}

function submitBestCategory(task) {
	var bestCategoryIndex = $("input:radio[name=suggested_category]:checked").val();
	if (!bestCategoryIndex) {
		$("#warning").html("Please select the best category");
		return;
	}

	var tasks = [];	
	var bestCategory = bestCategoryIndex != -1 ? task.suggested_categories[bestCategoryIndex] : ""
	tasks.push({ id: task.id, idea_id: task.idea_id, best_category: bestCategory });
	saveAndRequestNewJob(tasks);
}

function equalCategoryUI() {
	$("#title").html("Find Duplicate Categories");
	$("#help").html("Indicate whether or not each category pair are duplicates (i.e., have the exact same meaning).");
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			if (i==0) {
				taskHtml += "<table class='spacebelow'>";
				taskHtml += "<tr>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "<td><span class='small'>Duplicate?</span></td>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "<tr>";
			taskHtml += "<td>" + task.category1 + "</td>";
			taskHtml += "<td style='text-align:center'>&nbsp;<input type='radio' class='categories_equal' name='category_equal_"+task.id+"' value='1'>&nbsp;</td>";
			taskHtml += "<td>" + task.category2 + "</td>";
			taskHtml += "</tr>\n";
		}
		taskHtml += "</table>";
		taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
		taskHtml += "<img id='loading_icon' src='images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitEqualCategories();
		});
	}
}

function submitEqualCategories() {
	var tasks = [];	
	$("input:radio").each(function() {
		var rb = $(this);
		var rb_name = rb.attr("name");
		var task_id = rb_name.replace("category_equal_","");
		tasks.push({ id: task_id, equal: rb.is(":checked") ? 1 : 0 });
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#warning").html("Please indicate whether or not each pair category pair are duplicates");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function fitCategoryUI() {
	$("#title").html("Match Categories");
	$("#help").html("Select whether or not each category fits this note.");
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			if (i==0) {
				taskHtml += "<div class='green_highlight largespacebelow'>";
				taskHtml += task.idea;
				taskHtml += "<input type='hidden' id='idea_"+task.id+"' value='"+task.idea_id+"'>";
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
			submitFitCategories();
		});
	}
}

function submitFitCategories() {
	var tasks = [];	
	$("input:radio").each(function() {
		var rb = $(this);
		if (rb.is(":checked")) {
			var rb_name = rb.attr("name");
			var task_id = rb_name.replace("category_fit_","");
			var idea_id = $("#idea_"+task_id).val();
			tasks.push({ id: task_id, idea_id: idea_id, fit: rb.val() == "1" ? 1 : 0 });	
		}
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#warning").html("Please indicate whether each category fits or not");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function waitForJobToLoad() {
	$("#title").html("Loading next job ...");
	$("#help").html("");
	$("#task_area").html("<img id='loading_icon' src='images/loading.gif' />");
}

function waitForNextJob() {
	$("#title").html("Waiting ...");
	$("#help").html("");
	$("#task_area").html("Please wait until more jobs become available.");
}

function resultsReady() {
	redirectToResultsPage(question_id);
}

function initEventHandlers() {
	$(window).resize(function() {
		onResize();
	});

	$("#admin_button").click(function() {
		if (logged_in) {
			unloadPage(getAdminPageUrl(question_id));
		}
		else {
			redirectToAdminPage(question_id);
		}
	});
	
	$(".xparty_link").click(function() {
		if (logged_in) {
			unloadPage($(this).attr("href"));
			return false;
		}
		else {
			return true;
		}
	});
	
	// if a user closes the window/tab or browses to another url
	// before they submit their job, notify the server
	$(window).on('beforeunload', function() {
		unloadPage();
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

function handleJob(data) {
	if (loading) {
		assignedJob = data.job;
		loading = false;
		waiting = !assignedJob;
		updateUI(0);
	}
}

function handleMoreJobs(data) {
	if (waiting) {
		saveAndRequestNewJob();
	}
}

function handleResults(data) {
	resultsReady();
}

function handleLogout(data) {
	unloadPage(getLogoutUrl(question_id));
}