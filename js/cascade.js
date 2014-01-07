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

var CREATE_OWN_CATEGORY = "Create category, or select one";

// overrides setting in utils.js
// TODO/FIX: improve how count label is displayed in discuss buttons (shown on results page, but not cascade pages)
var SHOW_DISCUSS_BUTTONS = true;

$(document).ready(function() {
	onResize();
	initEventHandlers();

	if ($("#msg").html()) {
		return;
	}
		
	initChannel(onChannelOpen);
	
	// will only be shown for instructor
	// for questions that are not finished yet
	if (SHOW_START_URL_BY_DEFAULT) {
		$("#start_url_area").show();
	}
	else {
		$("#show_start_url").show();
	}
	
	$("#page_content").show();
});

function onChannelOpen() {
	// new job sent via message so must
	// wait for channel to open before
	// requesting first job	
	//saveAndRequestNewJob();
	
	// TODO/FIX/HACK: Safari started missing initial 
	// job message unless a time delay was inserted
	waitForJobToLoad();
	setTimeout(function() {
		saveAndRequestNewJob(); 
	},500);
}

function saveAndRequestNewJob(tasksToSave) {
	var data = {
		"client_id" : client_id,
		"question_id" : question_id,
		"waiting" : waiting ? "1" : "0",
		"discuss" : SHOW_DISCUSS_BUTTONS ? "1" : "0"
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
	
	// verify categories marked as fitting
	else if (assignedJob.type == VERIFY_CATEGORY) {
		fitCategoryUI();
	};
}

function suggestCategoryUI() {
	$("#title").html("Suggest Categories");
	$("#help").html("Suggest a category for each response.<br/>If you can not think of a good category, skip that response.");	
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];				
			taskHtml += "<div class='largespacebelow'>";
			taskHtml += "<div class='green_highlight smallspacebelow'>";
			taskHtml += discussButtonHtml(task.idea_id) + " ";
			taskHtml += SHOW_DISCUSS_BUTTONS ? "<div style='margin-left:30px'>" : "";
			taskHtml += task.idea;
			taskHtml += SHOW_DISCUSS_BUTTONS ?"</div>" : "";
			taskHtml += "</div>";
			taskHtml += "<input class='suggested_category' id='category_"+task.id+"' type='text' value='' size='30'>";
			taskHtml += "<input type='hidden' id='idea_"+task.id+"' value='"+task.idea_id+"'>";
			taskHtml += "</div>\n";
		}
		taskHtml += "<input id='submit_btn' type='button' value='Submit Categories'> ";
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";
					
		var categorySuggestions = [];	
		if (assignedJob.categories.length > 0) {
			taskHtml += "<div class='green_highlight spaceabove'>";
			taskHtml += "<div class='smallspacebelow'>Suggested By Others</div>";
			taskHtml += "<div id='suggested_categories'>";
			taskHtml += "<ul class='nospaceabove smallspacebelow'>";
			for (var i=0; i<assignedJob.categories.length; i++) {
				taskHtml += "<li class='small'>" + assignedJob.categories[i] + "</li>";	
			}
			taskHtml += "</ul>";
			taskHtml += "</div>";
			taskHtml += "</div>";
			
			categorySuggestions.push({ label: CREATE_OWN_CATEGORY, value: "" });
			for (var i=0; i<assignedJob.categories.length; i++) {
				var category = assignedJob.categories[i];
				categorySuggestions.push({ label: category, value: category });
			}
		}
		
		$("#task_area").html(taskHtml);
		
		$(".suggested_category").autocomplete({
			source: categorySuggestions,
			delay: 0,
			minLength: 0
		});
		
		$(".suggested_category").each(function(index) {
			var ac = $(this).data("ui-autocomplete");
			if (ac) {
				ac._renderItem = function(ul, item) {
					var htmlLabel = item.label;
					htmlLabel = htmlLabel.replace("<", "&lt;");
					htmlLabel = htmlLabel.replace(">", "&gt;");
					if (item.label == CREATE_OWN_CATEGORY) {
						htmlLabel = "<span class='help'>" + htmlLabel + "</span>";
					}
					return $("<li>")
						.data('item.autocomplete', item)
						.append($("<a>").html(htmlLabel))
						.appendTo(ul);
				};
			}
		});
		
		$(".suggested_category").click(function(event) {
			$(this).autocomplete("search", "");
		});
			
		$("#submit_btn").on("click", {}, function(event) {
			submitSuggestedCategories();
		});
				
		initDiscussButtons(question_id, client_id);
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
		$("#warning").html("You may only skip 2 responses");
		return;
	}
	
	saveAndRequestNewJob(tasks);
}

function bestCategoryUI() {
	$("#title").html("Select Best Category");
	$("#help").html("Pick the one category that best fits this response.");
	var tasks = assignedJob.tasks;
	if (tasks.length == 1) {
		var task = tasks[0];
		var taskHtml = "";
		taskHtml += "<div class='largespacebelow'>";
		taskHtml += "<div class='green_highlight largespacebelow'>";
		taskHtml += discussButtonHtml(task.idea_id) + " ";
		taskHtml += SHOW_DISCUSS_BUTTONS ? "<div style='margin-left:30px'>" : "";
		taskHtml += task.idea;
		taskHtml += SHOW_DISCUSS_BUTTONS ? "</div>" : "";
		taskHtml += "</div>";
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
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";		
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", { task : task }, function(event) {
			submitBestCategory(event.data.task);
		});
		
		initDiscussButtons(question_id, client_id);
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
	$("#help").html("Indicate whether or not each category pair are equivalent (i.e., have the exact same meaning).");
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			if (i==0) {
				taskHtml += "<table class='spacebelow'>";
				taskHtml += "<tr>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "<td><span class='small'>Equivalent?</span></td>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "<tr>";
			taskHtml += "<td>" + task.category1 + "</td>";
			taskHtml += "<td style='text-align:center'>&nbsp;<input type='checkbox' class='categories_equal' name='category_equal_"+task.id+"' value='1'>&nbsp;</td>";
			taskHtml += "<td>" + task.category2 + "</td>";
			taskHtml += "</tr>\n";
		}
		taskHtml += "</table>";
		taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitEqualCategories();
		});
	}
}

function submitEqualCategories() {
	var tasks = [];	
	$("input:checkbox").each(function() {
		var cb = $(this);
		var cb_name = cb.attr("name");
		var task_id = cb_name.replace("category_equal_","");
		tasks.push({ id: task_id, equal: cb.is(":checked") ? 1 : 0 });
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#warning").html("Please indicate whether or not each pair category pair are duplicates");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function fitCategoryUI() {
	$("#title").html("Match Categories");
	$("#help").html("Select whether or not each category fits this response.");
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			if (i==0) {
				taskHtml += "<div class='green_highlight largespacebelow'>";
				taskHtml += discussButtonHtml(task.idea_id);
				taskHtml += SHOW_DISCUSS_BUTTONS ? "<div style='margin-left:30px'>" : "";
				taskHtml += task.idea;
				taskHtml += SHOW_DISCUSS_BUTTONS ? "</div>" : "";
				taskHtml += "<input type='hidden' id='idea_id' value='"+task.idea_id+"'>";
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
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitFitCategories();
		});
		
		initDiscussButtons(question_id, client_id);
	}
}

function submitFitCategories() {
	var tasks = [];	
	var idea_id = $("#idea_id").val();
	$("input:radio").each(function() {
		var rb = $(this);
		if (rb.is(":checked")) {
			var rb_name = rb.attr("name");
			var task_id = rb_name.replace("category_fit_","");
			var category = getTaskAttribute(task_id, "category")
			tasks.push({ id: task_id, idea_id: idea_id, category: category, fit: rb.val() == "1" ? 1 : 0 });
		}
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#warning").html("Please indicate whether each category fits or not");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function getTaskAttribute(taskId, attribute) {
	var value = null;
	if (assignedJob) {
		for (var i=0; i<assignedJob.tasks.length; i++) {
			var task = assignedJob.tasks[i];
			if (task.id == taskId) {
				value = task[attribute];
				break;
			}
		}
	}
	return value;
}

function waitForJobToLoad() {
	$("#title").html("Loading next job ...");
	$("#help").html("");
	$("#task_area").html("<img id='loading_icon' src='/images/loading.gif' />");
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
		if (user_id != -1) {
			unloadPage(getAdminPageUrl(question_id));
		}
		else {
			redirectToAdminPage(question_id);
		}
	});
	
	$(".xparty_link").click(function() {
		if (user_id != -1) {
			unloadPage($(this).attr("href"));
			return false;
		}
		else {
			return true;
		}
	});
	
	$("#hide_start_url").click(function() {
		$("#start_url_area").hide();
		$("#show_start_url").show();
		return false;
	});

	$("#show_start_url").click(function() {
		$("#show_start_url").hide();
		$("#start_url_area").show();
		return false;
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
		if (assignedJob) {
			// do not show counts in discuss buttons or user lists (when moused over)
			initDiscussFlags(assignedJob.discuss_flags, false, false);
		}
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