// Copyright 2014 Ben Bederson - http://www.cs.umd.edu/~bederson
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
	google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': initReview });
	
});

function initReview() {
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
}

function saveAndRequestNewJob(tasksToSave) {
	var data = {
		"review_id" : review_id,
		"reviewer_id" : reviewer_id
	}
		
	if (isDefined(tasksToSave)) {
		data["job"] = $.toJSON({
			"question_id" : assignedJob["question_id"],
			"tasks" : tasksToSave,
			"type" : assignedJob.type	
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
		var startCategoryGroupTasks = results.saved_job && results.job && results.saved_job["type"] == REVIEW_RESPONSE_FIT && results.job["type"] == REVIEW_CATEGORY_GROUP;
		if (startReview) {
			startUI();
		}
		else if (startNewQuestion) {
			startUI(assignedJob.question_id);
		}
		else if (assignedJob) {
			reviewUI(startCategoryGroupTasks);
		}
		else {
			finishedUI();
		}
	}, "json");
}

function startUI(questionId) {
	setTitle("<span class='mediumheading'>" + (stats["question_count"] == 1 ? "Review Question" : "Review Questions") + "</span>", "");
	$("#task_description").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	$("#instructions").html("");
	
	var taskHtml = "";
	if (isUndefined(questionId)) {
		taskHtml += "<p>You have been assigned <strong>" + stats["question_count"] + "</strong> ";
		taskHtml += stats["question_count"] == 1 ? "question " : "questions ";
		taskHtml += "to review.</p>\n";

		taskHtml += "<p class='note'>";
		taskHtml += "A group of users submitted responses to a question. ";
		taskHtml += "Then, they grouped the responses into categories. ";		
		taskHtml += "You will be rating how well each response fits a category, "
		taskHtml += "and how well a group of responses fits a category as a whole. ";
		taskHtml += "Instructions will be provided with each task.";
		taskHtml += "</p>"; 
	}
	else {
		var incompleteQuestionCount = stats["question_count"] - stats["completed_question_count"]
		taskHtml += "<p>";
		taskHtml += "You have finished reviewing Question " + stats["completed_question_count"] + ".</br>";
		if (incompleteQuestionCount > 0) {
			taskHtml += "You have <strong>"+ incompleteQuestionCount + "</strong> " + (incompleteQuestionCount == 1 ? "question" : "questions") + " remaining to review.";
		}
		taskHtml += "</p>";
	}
	
	progress = getReviewProgress();
	taskHtml += progress.html;
		
	currentQuestionIndex = stats["completed_question_count"];
	var startLabel = progress.complete_percent[currentQuestionIndex] == 0 ? "Start" : "Continue";
	if (stats["question_count"] > 1) {
		startLabel += " Question " + (currentQuestionIndex+1);
	}
		
	taskHtml += "<input id='start_btn' type='button' value='" + startLabel + "'>";
	$("#task_area").html(taskHtml);
	$("#start_btn").on("click", {}, function(event) {
		reviewUI();
	});		
}

function getReviewProgress() {
	var html = "<table class='largespacebelow'>\n";
	html += "<tr>";
	html += "<td>&nbsp;</td>";
	html += "<td class='small'>Complete</td>";
	html += "<td>&nbsp;</td>";
	html += "</tr>\n";
	
	// questions are not performed in order they appear in question_stats
	// so questions should be presented in the following order: completed, in progress, not started
	var questionIndex = 1;
	var completePercentages = [];
		
	// completed questions
	for (var question_id in stats["question_stats"]) {
		var incompleteCount = stats["question_stats"][question_id].incomplete;
		if (incompleteCount == 0) {
			html += "<tr>";
			html += "<td>Question " + questionIndex + "</td>";
			html += "<td style='text-align:right'>100%</td>";
			html += "<td>&nbsp;&nbsp;<span class='small'><a class='noline' href='/review/" + review_id + "r" + reviewer_id + "' onclick='showResultsUI("+question_id+"); return false;'>View Your Ratings</a></span></td>";
			html += "</tr>\n";
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
			html += "<tr>";
			html += "<td>Question " + questionIndex + "</td>";
			html += "<td style='text-align:right'>" + percentComplete + "%</td>";
			html += "<td>&nbsp;</td>";
			html += "</tr>\n";
			questionIndex++;
			completePercentages.push(percentComplete);		
		}
	}	

	// not started questions
	for (var questionId in stats["question_stats"]) {
		var completeCount = stats["question_stats"][questionId].complete;
		if (completeCount == 0) {
			html += "<tr>";
			html += "<td>Question " + questionIndex + "</td>";
			html += "<td style='text-align:right'>0%</td>";
			html += "<td>&nbsp;</td>";
			html += "</tr>\n";
			questionIndex++;
			completePercentages.push(0);
		}
	}	

	html += "</table>\n";
	return { "html": html, "complete_percent": completePercentages };
}

function reviewUI(startCategoryGroupTasks) {
	if (!assignedJob) {
		return;
	}
		
	if (assignedJob.type == REVIEW_RESPONSE_FIT) {
		reviewResponseFitUI();
	}
	else if (assignedJob.type == REVIEW_CATEGORY_GROUP) {
		startCategoryGroupTasks = isDefined(startCategoryGroupTasks) ? startCategoryGroupTasks : false;
		reviewCategoryGroupUI(startCategoryGroupTasks);
	}
	else {
		alert("Unknown job type");
	}
}

function reviewResponseFitUI() {
	var questionIndex = stats["completed_question_count"] + 1;
	var title = "Question " + (stats["question_count"]>1 ? questionIndex + " of "+ stats["question_count"] : "");
	var subtitle = "<span class='mediumheading'>" + stats["question_stats"][assignedJob.question_id].question_text + "</span>";
	setTitle(title, subtitle, assignedJob.question_id);
	$("#task_description").html("<div class='spaceabove'>Rate how well each category fits this response.</div>");
	$("#task_help").html("");
	$("#task_warning").html("");
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var taskHtml = "";
		for (var i=0; i<tasks.length; i++) {
			var task = tasks[i];
			var response = capitalizeFirst(task.idea);
			var category = capitalizeFirst(task.category);
			if (i==0) {
				taskHtml += "<div class='green_highlight largespacebelow'>";
				taskHtml += response;
				taskHtml += "<input type='hidden' id='idea_id' value='"+task.idea_id+"'>";
				taskHtml += "</div>";
				taskHtml += "<table class='spacebelow'>";
				taskHtml += "<tr>";
				taskHtml += "<td class='small' colspan='5'>Fit Rating <span id='rating_tooltip' class='rating note' style='border:1px solid #888; padding-left:3px; padding-right:3px'>?</span></td>";
				taskHtml += "<td class='small'>Category</td>";
				taskHtml += "</tr>\n";
				taskHtml += "<tr>";
				taskHtml += "<td><span id='rating_tooltip_1' class='rating note'>1</span></td>";
				taskHtml += "<td><span id='rating_tooltip_2' class='rating note'>2</span></td>";
				taskHtml += "<td><span id='rating_tooltip_3' class='rating note'>3</span></td>";
				taskHtml += "<td><span id='rating_tooltip_4' class='rating note'>4</span></td>";
				taskHtml += "<td><span id='rating_tooltip_5' class='rating note'>5</span></td>";
				taskHtml += "<td>&nbsp;</td>";
				taskHtml += "</tr>\n";
			}
			taskHtml += "<tr>";
			taskHtml += "<td><input type='radio' name='category_fit_"+task.id+"' value='1'></td>";
			taskHtml += "<td><input type='radio' name='category_fit_"+task.id+"' value='2'></td>";
			taskHtml += "<td><input type='radio' name='category_fit_"+task.id+"' value='3'></td>";
			taskHtml += "<td><input type='radio' name='category_fit_"+task.id+"' value='4'></td>";
			taskHtml += "<td><input type='radio' name='category_fit_"+task.id+"' value='5'></td>";
			taskHtml += "<td>" + category + "</td>";
			taskHtml += "</tr>\n";
		}
		taskHtml += "</table>";
		taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		$("#submit_btn").on("click", {}, function(event) {
			submitFitRatings();
		});		
		
		$(".rating").qtip({
			content: {
				text: function(event, api) {
					var html = "Fit Rating:<br/>";
					var tooltipId = $(this).attr("id");
					if (tooltipId == "rating_tooltip") {
						for (var i=1; i<=5; i++) {
							html += getCategoryFitDefinition(i, true, true);
							html += "<br/>";
						}
						html += "<br/>";
						html += "<em>More details and examples below</em>";
					}
					else {
						rating = parseInt(tooltipId.replace("rating_tooltip_", ""));
						html = getCategoryFitDefinition(rating, false, true); 
					}
					return html
				}
			},
			style: {
				tip: { corner: true },
				classes: 'qtip-rounded tooltip2'
			}
		});
		
		$(".rating").hover(
			function() {
				var tooltipId = $(this).attr("id");
				if (tooltipId == "rating_tooltip") {
					$(this).css('background-color', '#e9f3cc');
				}
			},
			function () {
				$(this).css('background-color', '');
			}
		);
			
		$("#instructions").html(getCategoryFitInstructions());
	}
}

function submitFitRatings() {
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
		$("#task_warning").html("Please rate each category");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function reviewCategoryGroupUI(startTasks) {

	var questionIndex = stats["completed_question_count"] + 1;
	var title = "Question " + (stats["question_count"]>1 ? questionIndex + " of "+ stats["question_count"] : "");
	var subtitle = "<span class='mediumheading'>" + stats["question_stats"][assignedJob.question_id].question_text + "</span>";
	setTitle(title, subtitle, assignedJob.question_id);
		
	if (startTasks) {
		$("#task_description").html("");
		$("#task_help").html("");
		$("#task_warning").html("");		
		var taskHtml = "<p>You have finished rating how well individual responses fit categories for this question.</p>";
		taskHtml += "<p>Now you will rate how well groups of responses fit categories as a whole.</p>";
		taskHtml += "<input id='continue_btn' type='button' value='Continue'>";
		$("#task_area").html(taskHtml);
		$("#continue_btn").on("click", {}, function(event) {
			reviewCategoryGroupUI(false);
		});		
		return;
	}
	
	$("#task_description").html("Rate how well the responses below fit this category, as a whole.");
	$("#task_help").html("");
	$("#task_warning").html("");
	
	var tasks = assignedJob.tasks;
	if (tasks.length > 0) {
		var task = tasks[0];
		var category = capitalizeFirst(task.category);
		var taskHtml = "<div class='green_highlight largespacebelow'>";
		taskHtml += category;
		taskHtml += "</div>";
		taskHtml += "<table class='spacebelow'>";
		taskHtml += "<tr>";
		taskHtml += "<td class='small' colspan='5'>Group Rating <span id='rating_tooltip' class='rating note' style='border:1px solid #888; padding-left:3px; padding-right:3px'>?</span></td>";
		taskHtml += "</tr>\n";
		taskHtml += "<tr>";
		taskHtml += "<td class='note'><span id='rating_tooltip_1' class='rating note'>1</span></td>";
		taskHtml += "<td class='note'><span id='rating_tooltip_2' class='rating note'>2</span></td>";
		taskHtml += "<td class='note'><span id='rating_tooltip_3' class='rating note'>3</span></td>";
		taskHtml += "<td class='note'><span id='rating_tooltip_4' class='rating note'>4</span></td>";
		taskHtml += "<td class='note'><span id='rating_tooltip_5' class='rating note'>5</span></td>";
		taskHtml += "</tr>\n";
		taskHtml += "<tr>";
		taskHtml += "<td><input type='radio' name='group_rating_"+task.id+"' value='1'></td>";
		taskHtml += "<td><input type='radio' name='group_rating_"+task.id+"' value='2'></td>";
		taskHtml += "<td><input type='radio' name='group_rating_"+task.id+"' value='3'></td>";
		taskHtml += "<td><input type='radio' name='group_rating_"+task.id+"' value='4'></td>";
		taskHtml += "<td><input type='radio' name='group_rating_"+task.id+"' value='5'></td>";
		taskHtml += "</tr>\n";
		taskHtml += "</table>";
		taskHtml += "<div class='largespacebelow'>\n";
		taskHtml += "<span class='small'>Responses:</span><br/>\n";
		for (var i=0; i<task.ideas.length; i++) {
			var response = capitalizeFirst(task.ideas[i]);
			taskHtml += "<p class='smallspaceabove smallspacebelow'>" + response + "</p>\n";
		}
		taskHtml += "</div>\n";
		taskHtml += "<input id='submit_btn' type='button' value='Submit'> ";
		taskHtml += "<img id='loading_icon' src='/images/loading.gif' style='display:none'/>";
		$("#task_area").html(taskHtml);
		
		$("#submit_btn").on("click", {}, function(event) {
			submitGroupRatings();
		});	
		
		$("#instructions").html(getGroupFitInstructions());
	}
	
	$(".rating").qtip({
			content: {
				text: function(event, api) {
					var html = "Group Rating:<br/>";
					var tooltipId = $(this).attr("id");
					if (tooltipId == "rating_tooltip") {
						for (var i=1; i<=5; i++) {
							html += getGroupFitDefinition(i, true, true);
							html += "<br/>";
						}
						html += "<br/>";
						html += "<em>More details below</em>";
					}
					else {
						rating = parseInt(tooltipId.replace("rating_tooltip_", ""));
						html = getGroupFitDefinition(rating, false, true); 
					}
					return html
				}
			},
			style: {
				tip: { corner: true },
				classes: 'qtip-rounded tooltip2'
			}
		});
		
		$(".rating").hover(
			function() {
				var tooltipId = $(this).attr("id");
				if (tooltipId == "rating_tooltip") {
					$(this).css('background-color', '#e9f3cc');
				}
			},
			function () {
				$(this).css('background-color', '');
			}
		);
}

function submitGroupRatings() {
	var tasks = [];	
	var idea_id = $("#idea_id").val();
	$("input:radio").each(function() {
		var rb = $(this);
		if (rb.is(":checked")) {
			var rb_name = rb.attr("name");
			var task_id = rb_name.replace("group_rating_","");
			var category = getTaskAttribute(task_id, "category")
			tasks.push({ id: task_id, category: category, group_rating: parseInt(rb.val()) });
		}
	});

	if (tasks.length!=assignedJob.tasks.length) {
		$("#task_warning").html("Please rate this category");
		return;
	}
	saveAndRequestNewJob(tasks);
}

function showResultsUI(questionId) {
	var title = "Question";
	var subtitle = "<span class='mediumheading'>" + stats["question_stats"][questionId].question_text + "</span>";
	setTitle(title, subtitle, questionId);
	$("#task_description").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	$("#task_area").html("Loading results ...<br/><img id='loading_icon' src='/images/loading.gif' />");
	$("#instructions").html("");
		
	var data = {
		"question_id" : questionId,
		"review_id" : review_id,
		"reviewer_id" : reviewer_id
	};
	
	$.post("/load_review_results", data, function(results) {
		if (results.status == 0) {
			showWarningMessage(results.msg);
			return;
		}
				
		var sortedCategories = [];
		for (var category in results.results) {
			sortedCategories.push(category);
		}
		sortedCategories.sort(function(s1, s2) {
			var s1lower = s1.toLowerCase();
			var s2lower = s2.toLowerCase();
			return s1lower > s2lower ? 1 : (s1lower < s2lower ? -1 : 0);
		});
			
		var taskHtml = "";
		taskHtml += "<div style='float:left' class='mediumheading'>Your Ratings</div>";
		taskHtml += "<div class='note' style='float:right'><a href='/review/"+review_id+"r"+reviewer_id+"'>Return to overview</a></div>";
		taskHtml += "<div style='clear:both'></div>";
		taskHtml += "<div id='chart' class='largespacebelow'></div>";
		var chartData = [];
		chartData.push([ 'Category', 'Individual Responses', 'Response Group' ]);		
		for (var i=0; i<sortedCategories.length; i++) {
			var categoryGroup = results.results[sortedCategories[i]];
			var category = capitalizeFirst(sortedCategories[i]);
			var ideas = categoryGroup.ideas;
			var groupRating = categoryGroup.rating;
			var fitRatingSum = 0;
			var fitRatingCount = 0;

			taskHtml += "<div class='green_highlight spacebelow'>";
			taskHtml += "<span class='note'>(" + groupRating + ")</span> " + category;
			taskHtml += "</div>\n";
			taskHtml += "<table class='largespacebelow'>";
			for (var j=0; j<ideas.length; j++) {
				var ideaText = capitalizeFirst(ideas[j].idea);
				var fitRating = ideas[j].rating;
				taskHtml += "<tr>";
				taskHtml += "<td class='padbottom'>&nbsp;<span class='note'>(" + (fitRating != -1 ? fitRating : "-") + ")</span></td>";
				taskHtml += "<td>&nbsp;" + ideaText + "</td>";
				taskHtml += "</tr>\n";
				fitRatingSum += fitRating != -1 ? fitRating : 0;
				fitRatingCount += fitRating != -1? 1 : 0;
			}
			taskHtml += "</table>\n";

			var averageFitRating = fitRatingSum / fitRatingCount;
			chartData.push([category, averageFitRating, groupRating]);
		}
		$("#task_area").html(taskHtml);
		drawBarChart('chart', chartData);	
	}, "json");
}

function finishedUI() {
	progress = getReviewProgress();
	setTitle("<span class='mediumheading'>Review Complete</span>", "");
	$("#task_description").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	var taskHtml = "<p>Thank you! You have finished reviewing all of the questions assigned to you.</p>";
	taskHtml += progress.html;
	taskHtml += "<p class='note'>Questions? Email <a href='mailto:rose@cs.umd.edu'>rose@cs.umd.edu</a></p>";
	$("#task_area").html(taskHtml);
	$("#instructions").html("");
}
	
function waitForJobToLoad() {
	setTitle("<span class='mediumheading'>Review Question</span>", "");
	$("#task_description").html("");
	$("#task_help").html("");
	$("#task_warning").html("");
	$("#task_area").html("Loading next job ...<br/><img id='loading_icon' src='/images/loading.gif' />");
	$("#instructions").html("");
}

function showWarningMessage(warning) {
	setTitle("<span class='mediumheading'>Review Question</span>", "");
	$("#task_description").html("");
	$("#task_help").html("");
	$("#task_warning").html(warning);
	$("#task_area").html("");
	$("#instructions").html("");
}

function setTitle(title, subtitle, questionId) {
	$("#title").html(title);
	$("#subtitle").html(subtitle);
	$("#complete_status").html(isDefined(questionId) ? getPercentComplete(questionId) + "% complete" : "");
}

function getPercentComplete(questionId) {
	var percentComplete = 0;
	if (stats) {	
		var completeCount = stats["question_stats"][questionId].complete;
		var incompleteCount = stats["question_stats"][questionId].incomplete;
		if (completeCount > 0) {
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

function getCategoryFitInstructions() {
	var html = '<p>Fit Ratings</p>';
	html += '<table style="border-collapse: collapse">';
	for (var i=1; i<=5; i++) {
		html += '<tr>';
		html += '<td><strong>' + i + '&nbsp;&nbsp;</strong</td>';
		html += '<td style="padding-bottom:8px">' + getCategoryFitDefinition(i, false, false) + '</td>';
		html == '</tr>';
	}
	html += '</table>';
	return html;
}

function getCategoryFitDefinition(rating, short, includeRating) {
	var short = isDefined(short) ? short : false;
	var includeRating = isDefined(includeRating) ? includeRating : true;
	
	var shortDesc = "";
	var longDesc = "";
	var example = "";
	if (rating == 1) {
		shortDesc = 'definitely does not fit';
		longDesc = 'I think this category definitely does not fit this response';
		example = 'What is your favorite food?<br/>';
		example += 'Response: pizza<br/>';
		example += 'Category: dessert';
	}
	else if (rating == 2) {
		shortDesc = 'probably does not fit';
		longDesc = 'I this this category probably does not fit this response but I can understand how it might';
		example = 'What do you wish campus would have?<br/>';
		example += 'Response: shopping mall<br/>';
		example += 'Category: food<br/>';
		example += '<em>a shopping mall can have food</em>';
	}
	else if (rating == 3) {
		shortDesc = 'neutral';
		longDesc = 'my reasons for thinking this category fits or does not fit this response are about the same';
		example = 'What do you like to drink?<br/>';
		example += 'Response: wine<br/>';
		example += 'Category: healthy<br/>';
		example += '<em>there may be some health benefits to drinking wine, but too much can be bad</em>';
	}
	else if (rating == 4) {
		shortDesc = 'probably fits';
		longDesc = 'I think this category probably fits this response but I can understand how it might not';
		example = 'What is your favorite food?<br/>';
		example += 'Response: fruit<br/>';
		example += 'Category: dessert<br/>';
		example += '<em>I consider fruit a dessert but not everyone may</em>';
	}
	else if (rating == 5) {
		shortDesc = 'definitely fits';
		longDesc = 'I think this category definitely fits this response';
		example = 'What is your favorite food?<br/>';
		example += 'Response: pizza<br/>';
		example += 'Category: fast food';
	}
	
	var html = "";
	if (short) {
		html = (includeRating ? rating + " - " : "") + shortDesc;
	}
	else {
		html = "<div class='smallspacebelow'>";
		html += '<strong>' + (includeRating ? rating + " - ": "") + shortDesc + '</strong><br/>';
		html += longDesc
		html += '</div>';
		html += '<div class="grey">' + example + '</div>';
	}
		
	return html;
}

function getGroupFitInstructions() {
	var html = '<p>Group Ratings</p>';
	html += '<table style="border-collapse: collapse">';
	for (var i=1; i<=5; i++) {
		html += '<tr>';
		html += '<td><strong>' + i + '&nbsp;&nbsp;</strong</td>';
		html += '<td style="padding-bottom:8px">' + getGroupFitDefinition(i, false, false) + '</td>';
		html == '</tr>';
	}
	html += '</table>';
	return html;
}

function getGroupFitDefinition(rating, short, includeRating) {
	var short = isDefined(short) ? short : false;
	var includeRating = isDefined(includeRating) ? includeRating : true;
	
	var shortDesc = "";
	var longDesc = "";
	if (rating == 1) {
		shortDesc = 'Very poor';
		longDesc = 'these responses fit this category very poorly';
	}
	else if (rating == 2) {
		shortDesc = 'Poor';
		longDesc = 'these responses fit this category poorly';
	}
	else if (rating == 3) {
		shortDesc = 'Fair';
		longDesc = 'these responses fits this category somewhat';
	}
	else if (rating == 4) {
		shortDesc = 'Good';
		longDesc = 'these responses fit this category pretty well';
	}
	else if (rating == 5) {
		shortDesc = 'Very good';
		longDesc = 'these responses fit this category very well';
	}
	
	var html = "";
	if (short) {
		html = (includeRating ? rating + " - " : "") + shortDesc;
	}
	else {
		html = "<div class='smallspacebelow'>";
		html += '<strong>' + (includeRating ? rating + " - ": "") + shortDesc + '</strong>, ' + longDesc;
		html += '</div>';
	}
		
	return html;
}

function drawBarChart(divId, data) {
	var dataTable = google.visualization.arrayToDataTable(data, false);
	var options = {  
		height: 250,
		chartArea: { width: '95%', left: 30, top: 20, height: 175 }, 
		series: [ { color: '#75A3FF' }, { color: '#476BB2' }],
		legend: { position: 'bottom', maxLines: 1 },
		vAxis: { ticks: [0,1,2,3,4,5] },
		hAxis: { maxTextLines: 2 }
	};
	var chart = new google.visualization.ColumnChart(document.getElementById(divId));
	chart.draw(dataTable, options);
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