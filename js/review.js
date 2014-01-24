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
var stats = null;

$(document).ready(function() {
	onResize();
	$(window).resize(function() {
		onResize();
	});

	if ($("#msg").html()) {
		return;
	}
		
	waitForJobToLoad();
	$("#page_content").show();
	
	var data = {
		"review_id" : review_id,
		"reviewer_id" : reviewer_id
	};
	
	$.post("/review_init", data, function(results) {
		if (results.status == 0) {
			showWarningMessage(results.msg);
			return;
		}
				
		var questionCount = 0;
		var completedQuestionCount = 0;
		for (questionId in results.stats) {
			var incompleteCount = results.stats[questionId].incomplete;
			var completeCount = results.stats[questionId].complete;
			if (incompleteCount == 0) {
				completedQuestionCount++;
			}
			questionCount++;
		}
		
		stats = {};
		stats["question_stats"] = results.stats;
		stats["question_count"] = questionCount;
		stats["completed_question_count"] = completedQuestionCount;
	
		saveAndRequestNewJob();
	}, "json");
});

function saveAndRequestNewJob(tasksToSave) {
	var data = {
		"review_id" : review_id,
		"reviewer_id" : reviewer_id
	}
		
	if (isDefined(tasksToSave)) {
		data["job"] = $.toJSON({
			"question_id" : assignedJob["question_id"],
			"tasks" : tasksToSave		
		});
	}

	assignedJob = null;
	waitForJobToLoad();
	
	$.post("/review_job", data, function(results) {
		if (results.status == 0) {
			showWarningMessage(results.msg);
			return;
		}
				
		var justFinishedPreviousQuestion = false;
		if (results.saved_job) {
			stats["question_stats"][results.saved_job.question_id].complete += results.saved_job.task_count;
			stats["question_stats"][results.saved_job.question_id].incomplete -= results.saved_job.task_count;
			if (stats["question_stats"][results.saved_job.question_id].incomplete == 0) {
				stats["completed_question_count"]++;
				justFinishedPreviousQuestion = true;
			}
		}
			
		assignedJob = results.job;
		var startReview = !results.saved_job && assignedJob!=null;
		var startNewQuestion = justFinishedPreviousQuestion && assignedJob!=null;

		if (startReview) {
			startUI();
		}
		else if (startNewQuestion) {
			startUI(assignedJob.question_id);
		}
		else if (assignedJob) {
			reviewUI();
		}
		else {
			finishedUI();
		}
	}, "json");
}

function startUI(questionId) {
	setTitle(stats["question_count"] == 1 ? "Review Question" : "Review Questions", "");
	$("#task_title").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	$("#instructions").hide();
	
	var taskHtml = "";
	if (isUndefined(questionId)) {
		taskHtml += "<p>You have been assigned <strong>" + stats["question_count"] + "</strong> ";
		taskHtml += stats["question_count"] == 1 ? "question " : "questions ";
		taskHtml += "to review.</p>\n";
		taskHtml += "<p class='note'>Each question has several responses, and categories have been created for the responses. ";
		taskHtml += "You will be asked to rate how well each response fits these categories, "
		taskHtml += "and how well a group of responses (as a whole) fits a specific category.</p>"; 
	}
	else {
		taskHtml += "<p>You have finished reviewing <strong>"+ stats["completed_question_count"] + "</strong> of <strong>" + stats["question_count"] + "</strong> questions.</p>";
	}
	
	taskHtml += "<table class='largespacebelow'>\n";
	taskHtml += "<tr>";
	taskHtml += "<td>&nbsp;</td>";
	taskHtml += "<td class='small'>Complete</td>";
	taskHtml += "</tr>\n";
	
	// questions are not performed in order they appear in question_stats
	// so questions should be presented in the following order: completed, in progress, not started
	var questionIndex = 1;
	var completePercentages = [];
		
	// completed questions
	for (var question_id in stats["question_stats"]) {
		var incompleteCount = stats["question_stats"][question_id].incomplete;
		if (incompleteCount == 0) {
			taskHtml += "<tr>";
			taskHtml += "<td>Question " + questionIndex + "</td>";
			taskHtml += "<td style='text-align:right'>100%</td>";
			taskHtml += "</tr>\n";
			questionIndex++;
			completePercentages.push(100);
		}
	}

	// in progress question
	for (var questionId in stats["question_stats"]) {
		var completeCount = stats["question_stats"][questionId].complete;
		var incompleteCount = stats["question_stats"][questionId].incomplete;
		if (completeCount > 0 && incompleteCount > 0) {
			var percentComplete = getPercentComplete(questionId);
			taskHtml += "<tr>";
			taskHtml += "<td>Question " + questionIndex + "</td>";
			taskHtml += "<td style='text-align:right'>" + percentComplete + "%</td>";
			taskHtml += "</tr>\n";
			questionIndex++;
			completePercentages.push(percentComplete);		
		}
	}	

	// not started questions
	for (var questionId in stats["question_stats"]) {
		var completeCount = stats["question_stats"][questionId].complete;
		if (completeCount == 0) {
			taskHtml += "<tr>";
			taskHtml += "<td>Question " + questionIndex + "</td>";
			taskHtml += "<td style='text-align:right'>0%</td>";
			taskHtml += "</tr>\n";
			questionIndex++;
			completePercentages.push(0);
		}
	}	
	
	currentQuestionIndex = stats["completed_question_count"];
	var startLabel = completePercentages[currentQuestionIndex] == 0 ? "Start" : "Continue";
	if (stats["question_count"] > 1) {
		startLabel += " Question " + (currentQuestionIndex+1);
	}
	
	taskHtml += "</table>\n";
	taskHtml += "<input id='start_btn' type='button' value='" + startLabel + "'>";
	$("#task_area").html(taskHtml);
	$("#start_btn").on("click", {}, function(event) {
		reviewUI();
	});		
}

function reviewUI() {
	var questionIndex = stats["completed_question_count"] + 1;
	var title = "Question " + (stats["question_count"]>1 ? questionIndex + " of "+ stats["question_count"] : "");
	var subtitle = stats["question_stats"][assignedJob.question_id].question_text;
	setTitle(title, subtitle, assignedJob.question_id);
	$("#task_title").html("Rate Categories");
	$("#task_help").html("Rate how well this response fits each category.");
	$("#task_warning").html("");
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			if (i==0) {
				taskHtml += "<div class='green_highlight largespacebelow'>";
				taskHtml += task.idea;
				taskHtml += "<input type='hidden' id='idea_id' value='"+task.idea_id+"'>";
				taskHtml += "</div>";
				taskHtml += "<table class='spacebelow'>";
				taskHtml += "<tr>";
				taskHtml += "<td class='small' colspan='5'>Fit Rating</td>";
				taskHtml += "<td class='small'>Category</td>";
				taskHtml += "</tr>\n";
				taskHtml += "<tr>";
				taskHtml += "<td class='note'>1</td>";
				taskHtml += "<td class='note'>2</td>";
				taskHtml += "<td class='note'>3</td>";
				taskHtml += "<td class='note'>4</td>";
				taskHtml += "<td class='note'>5</td>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "<tr>";
			taskHtml += "<td><input type='radio' class='category_fit' name='category_fit_"+task.id+"' value='1'></td>";
			taskHtml += "<td><input type='radio' class='catgetory_fit' name='category_fit_"+task.id+"' value='2'></td>";
			taskHtml += "<td><input type='radio' class='category_fit' name='category_fit_"+task.id+"' value='3'></td>";
			taskHtml += "<td><input type='radio' class='catgetory_fit' name='category_fit_"+task.id+"' value='4'></td>";
			taskHtml += "<td><input type='radio' class='category_fit' name='category_fit_"+task.id+"' value='5'></td>";
			taskHtml += "<td>" + task.category + "</td>";
			taskHtml += "</tr>\n";
		}
		taskHtml += "</table>";
		taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitRatings();
		});		
		
		$("#instructions").show();
	}
}

function submitRatings() {
	var tasks = [];	
	var idea_id = $("#idea_id").val();
	$("input:radio").each(function() {
		var rb = $(this);
		if (rb.is(":checked")) {
			var rb_name = rb.attr("name");
			var task_id = rb_name.replace("category_fit_","");
			var category = getTaskAttribute(task_id, "category")
			tasks.push({ id: task_id, idea_id: idea_id, category: category, fit_rating: parseInt(rb.val()) });
		}
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#task_warning").html("Please indicate whether each category fits or not");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function finishedUI() {
	setTitle("Review Complete", "");
	$("#task_title").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	var taskHtml = "<p>Thank you! You have finished reviewing the questions assigned to you.</p>";
	$("#task_area").html(taskHtml);
	$("#instructions").hide();
}
	
function waitForJobToLoad() {
	setTitle("Review Question", "");
	$("#task_title").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	$("#task_area").html("Loading next job ...<br/><img id='loading_icon' src='/images/loading.gif' />");
	$("#instructions").hide();
	
}

function showWarningMessage(warning) {
	setTitle("Review Question", "");
	$("#task_title").html("");
	$("#task_help").html("");
	$("#task_warning").html(warning);
	$("#task_area").html("");
	$("#instructions").hide();
}

function setTitle(title, subtitle, questionId) {
	$("#title").html(title);
	$("#subtitle").html(subtitle);
	$("#percent_complete").html(isDefined(questionId) ? getPercentComplete(questionId) + "% complete" : "");
}

function getPercentComplete(questionId) {
	var percentComplete = 0;
	if (stats) {
		var completeCount = stats["question_stats"][questionId].complete;
		var incompleteCount = stats["question_stats"][questionId].incomplete;
		if (completeCount > 0 && incompleteCount > 0) {
			percentComplete = Math.floor((completeCount / (completeCount + incompleteCount)) * 100);
		}
	}
	return percentComplete;
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