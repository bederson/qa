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

// Cascade Job Count Estimates
// (no longer using all steps but good for reference)
// Step 1 (suggest categories): 		Math.ceil(m/t) * k
// Step 2 (best categories): 			m * k
// Step 3 (fit categories):	 			m * Math.ceil(C/t) * k2; C = Math.ceil(1.5 * m)	(estimate)
// Step 4 (verify categories):  		m * k2
// Step 5 (fit categories subsequent)	(n-m) * Math.ceil(C/t) * k2; C = Math.ceil(0.33 * m) (estimate)

var questions = [];

$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}
	
	selected_question_id = selected_question_id !="" ? selected_question_id : null;
	
	var authenticationOptions = {};
	authenticationOptions[NO_AUTHENTICATION] = "No authentication required";
	authenticationOptions[GOOGLE_AUTHENTICATION] = "Google authentication";
	// More testing needed before enabling
	//authenticationOptions[NICKNAME_AUTHENTICATION] = "Nickname authentication";
	$.each(authenticationOptions, function(key, value) {
		$("#newq_authentication").append($("<option></option>").attr("value", key).text(value));
	});
	
	initChannel(onChannelOpen);
	$("#page_content").show();
});

function onChannelOpen() {
	loadQuestions();
	
	$("#newq_button").click(function() {
		createEditQuestion();
	});
		
	$("#active_cb").click(function() {
		var active = $(this).is(":checked") ? 1 : 0;
		setActive(active);
	});
	
	$("#create_categories_button").click(function() {
		createCategories();
	});
	
	$("#create_categories2_button").click(function() {
		createTestCategories();
	});

	// regenerate categories
	$("#create_categories3_button").click(function() {
		createCategories();
	});
}

function updateQuestionUI(question_id) {
	var index = getQuestionIndex(question_id);
	if (index != -1) {
		if (isSelectedQuestion(question_id)) {
			displaySelectedQuestion();
		}
		displayQuestionItem(questions[index])		
	}
}

//==============================================================
// Question List UI
//==============================================================

function loadQuestions() {
	$.getJSON("/query", { "request": "questions" }, function(results) {
		questions = [];
		for (i in results.questions) {
			addQuestion(results.questions[i]);
		}
		displayQuestionsList();
		if (selected_question_id) {
			selectQuestion(selected_question_id);
		}
	});	
}

function displayQuestionsList() {
	var html = "";
	if (questions.length == 0) {
		html = "<p>None</p>";
	}
	else {
		html += "<ul>";
		for (var i in questions) {
			html += '<li id="question_'+questions[i].id+'" style=\"margin-bottom:10px\">';
			html += getQuestionItemHtml(questions[i]);
			html += '</li>';
		}
		html += "</ul>";
	}
	$("#question_list").html(html);
}

function displayQuestionItem(question) {
	var html = getQuestionItemHtml(question);
	$("#question_"+question.id).html(html);
}

function getQuestionItemHtml(question) {
	var html = "<a href='javascript:selectQuestion(" + question.id + ")'>" + question.title + "</a> ";
	html += "<span class='note'>#"+question.id+"</span>&nbsp;&nbsp;&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:editQuestionForm(" + question.id + ")'>[edit]</a>&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:deleteQuestionData(" + question.id + ")'>[delete data]</a>&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:downloadQuestion(" + question.id + ")'>[download]</a>&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:deleteQuestion(" + question.id + ")'>[delete]</a>";
	if (isRunningOnLocalServer() || (isRunningOnTestServer() && dev_user)) {
		html += "&nbsp;&nbsp;||&nbsp;&nbsp;";
		html += "<a class='small' href='javascript:copyQuestion(" + question.id + ")'>[duplicate]</a>";
	}
	html += "<br/>";
	html += question.question + "<br/>";
	html += isDefined(question.author) ? "<em>" + question.author + "</em><br/>" : "";
	
	if (question.authentication_type == GOOGLE_AUTHENTICATION) {
		html += '<span class="note"><em>Google authentication required</em></span><br/>';
	}
	else if (question.authentication_type == NICKNAME_AUTHENTICATION) {
		html += '<span class="note"><em>Nickname authentication required</em></span><br/>';
	}
	
	if (!question.active) {
		html += '<span class="note"><em>Inactive</em></span><br/>';
	}
	
	if (question.cascade_complete) {
		html += "<span class='note'><em>Categories created</em></span>";
	}
	return html;
}

function downloadQuestion(question_id) {
	window.location.href = "/download_question?question_id="+question_id+"&utc_offset_minutes="+(new Date()).getTimezoneOffset()
}

function deleteQuestionData(question_id) {
	$("#delete_data_confirm").css("display", "inline");
	$("#delete_data_confirm").dialog({
		resizable: false,
		width: 300,
		height: 240,
		modal: true,
		buttons: {
			"Delete data": function() {
				var data = {
					"client_id": client_id,
					"question_id": question_id,
					"data_only" : true
				};
				$.post("/delete_question", data, function(result) {
					if (result.status == 1) {
						question = initQuestionStats(result.question);
						question.cascade_complete = 0;
						var index = getQuestionIndex(question_id);
						questions[index] = question;
						updateQuestionUI(question.id);
					}
				}, "json");
				$(this).dialog("close");
			},
			Cancel: function() {
				$(this).dialog("close");
			}
		}
	});
}

function deleteQuestion(question_id) {
	$("#delete_confirm").css("display", "inline");
	$("#delete_confirm").dialog({
		resizable: false,
		width: 300,
		height: 240,
		modal: true,
		buttons: {
			"Delete question": function() {
				var data = {
					"client_id": client_id,
					"question_id": question_id
				};
				$.post("/delete_question", data, function(result) {
					var deletedIndex = getQuestionIndex(question_id);
					if (deletedIndex != -1) {
						questions.splice(deletedIndex, 1);
						displayQuestionsList();
						if (isSelectedQuestion(question_id)) {
							selectQuestion(null);
						}
						createQuestionForm();
					}
				}, "json");
				$(this).dialog("close");
			},
			Cancel: function() {
				$(this).dialog("close");
			}
		}
	});
}

function copyQuestion(question_id) {
	var data = {
		"client_id": client_id,
		"question_id": question_id
	};
	$.post("/copy_question", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		
		addQuestion(result.new_question, true);
		displayQuestionsList();
		selectQuestion(result.new_question.id);
	}, "json");
}

//==============================================================
// Selected Question UI
//==============================================================

function selectQuestion(question_id) {
	selected_question_id = question_id;
	if (selected_question_id) {
		displaySelectedQuestion();
	}
	else {
		$("#selected_question").hide();
	}
}

function displaySelectedQuestion() {
	var question = getSelectedQuestion();
	if (!question) {
		$("#selected_question").hide();
		return;
	}
	
	var html = "<h2 class='spacebelow'>Selected question:</h2>";
	html += "<strong>" + question.title + "</strong> <span class='note'>#" + question.id + "</span> <span id='inactive' class='small warning'></span><br/>";
	html += question.question + "<br/>";
	html += "<div id='user_stats' class='small largespacebelow'>&nbsp;</div>";
	$("#question").html(html);
		
	loadStats(question);
	
	$("#inactive").html(!question.active ? "INACTIVE" : "");
	$("#active_cb").prop("checked", question.active);
	$("#start_link").attr("href", getStartPageUrl(question.id));
	$("#idea_link").attr("href", getNotesPageUrl(question.id));
	$("#results_link").attr("href", getResultsPageUrl(question.id));
	$("#selected_question").show();
}

function loadStats() {
	var question = getSelectedQuestion();
	if (!question) {
		return;
	}
	
	var data = {
		"request": "stats",
		"question_id": question.id
	}
	$.getJSON("/query", data, function(results) {
		var question = getQuestion(results.question_id);
		if (question) {
			question.idea_count = results["idea_count"];
			question.idea_user_count = results["idea_user_count"];
			question.active_user_count = results["active_user_count"];
			question.cascade_stats = results["cascade_stats"];
			onStatsLoaded(question);
		}
	});
}

function onStatsLoaded(question) {
	if (isSelectedQuestion(question.id)) {
		displayStats(question);
	}
}

function displayStats(question) {
	var html = "<div id='idea_count' style='font-size:24px;text-align:center'></div>";
	html += "<div id='idea_count_label' style='font-size:11px;text-align:center' class='spacebelow'></div>";      
	html += "<div id='category_count' style='font-size:24px;text-align:center'></div>";
	html += "<div id='category_count_label' style='font-size:11px;text-align:center' class='spacebelow'></div>"; 
	html += "<div style='font-size:24px;text-align:center'><span id='percent_complete'></span>%</div>";
	html += "<div style='font-size:11px;text-align:center' class='spacebelow'>COMPLETE</div>";
	html += "<div id='cascade_notes'></div>";
	$("#status").html(html);
	
	updateUserCount(question);
	updateIdeaCount(question);
	updateCategoryCount(question);
	updateCategoryStatus(question);
}

function updateUserCount(question) {
	var activeUserCount = question.active_user_count;
	$("#user_stats").html("("+activeUserCount + (activeUserCount!=1 ? " active users" : " active user")+")");
}

function updateIdeaCount(question) {
    $("#idea_count").html(question.idea_count);
    $("#idea_count_label").html(question.idea_count != 1 ? "RESPONSES" : "RESPONSE");
    showHideCreateCategoryButton(question);
}

function updateCategoryCount(question) {
	var categoryCount = question.cascade_complete ? question.cascade_stats["category_count"] : 0;
    $("#category_count").html(categoryCount);
    $("#category_count_label").html(categoryCount != 1 ? "CATEGORIES" : "CATEGORY");
}

function updateCategoryStatus(question) {
	updatePercentComplete(question);	
	updateCategoryCount(question);
	showHideCreateCategoryButton(question);

	var html = "";
	if (question.cascade_complete) {
		html += "<div class='note' style='text-align:center'>";
		html += question.cascade_stats["cascade_user_count"] + (question.cascade_stats["cascade_user_count"]==1 ? "&nbsp;user" : "&nbsp;users");
		if (question.cascade_stats["uncategorized_count"] > 0) {
			html += ", " + question.cascade_stats["uncategorized_count"] + "&nbsp;uncategorized";
		}
		html += "</div>";
	}
	if (question.cascade_k != 0) {
		html += "<div class='note' style='text-align:center'>k=" + question.cascade_k + ", k2=" + question.cascade_k2 + ", m=" + question.cascade_m + "%</div>";
	}
	$("#cascade_notes").html(html);	
}

function updatePercentComplete(question) {
    var percentComplete = 0;  
    if (question.cascade_complete) {
    	percentComplete = 100;
    }
    else {
    	var completedFitCount = question.cascade_stats["completed_fit_count"];
    	//var totalFitCount = question.cascade_stats["category_count"] * question.idea_count * question.cascade_k2;
    	var totalFitCount = question.cascade_stats["total_fit_count"];
    	var completedVerifyCount = question.cascade_stats["completed_verify_count"];
    	var totalVerifyCount = question.cascade_stats["total_verify_count"];

		var completedCount = completedFitCount + completedVerifyCount;
		var totalCount = totalFitCount + totalVerifyCount;
    	percentComplete = totalCount > 0 ? Math.floor((completedCount / totalCount)*100) : 0;

    }
    $("#percent_complete").html(percentComplete);
}

function createCategories() {
	var question = getSelectedQuestion();
	if (!question) {
		return;
	}
	var data = {
		"client_id": client_id,
		"question_id": question.id
	};
	$.post("/generate_categories", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		redirectToResultsPage(result.question_id);		
	}, "json");
}

function createTestCategories() {
	var question = getSelectedQuestion();
	if (!question) {
		return;
	}
	var data = {
		"client_id": client_id,
		"question_id": question.id
	};
	$.post("/generate_test_categories", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		redirectToTestResultsPage(result.question_id);		
	}, "json");
}
    
function showHideCreateCategoryButton(question) {
	if (!question.cascade_complete) {
		enableDisable($("#create_categories_button"), question.idea_count > 0);
		$("#create_categories_button").show();
		$("#create_categories2_button").hide();
	}
	else {
		$("#create_categories_button").hide();
		// FOR TESTING ONLY: create_categories2_button allows categories to be regenerated to a secondary set of tables
		// FOR TESTING ONLY: create_categories3_button allows existing categories to be regenerated
		if (isRunningOnTestServer() && dev_user) {
			//$("#create_categories2_button").show();
		    //$("#create_categories3_button").show();
		}
	}
}

function setActive(active) {
	var question = getSelectedQuestion();
	if (!question) {
		return;
	}
	var data = {
		"client_id": client_id,
		"question_id": question.id,
		"active": active
	};
	$.post("/set_active", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		
		var index = getQuestionIndex(result.question.id);
		questions[index].active = result.question.active;
		updateQuestionUI(result.question.id);			
	}, "json");
}

//==============================================================
// Create / Edit Question Form
//==============================================================

function createEditQuestion() {
	var title = $("#newq_title").val();
	var questionText = $("#newq_question").val();
	var authenticationType = parseInt($("#newq_authentication").val());
	
	if (!title || !questionText) {
		$("#newq_info").html("Title and question required");
	}
	
	else {
		var data = {
			"client_id": client_id,
			"title": title,
			"question": questionText,
			"authentication_type": authenticationType
		};
			
		// edit existing question
		if (isDefined($("#newq_button").data("question_id"))) {
			data["question_id"] = $("#newq_button").data("question_id");
			$.post("/edit_question", data, function(result) {
				if (result.status == 0) {
					$("#newq_info").html(result.msg);
					return;
				}
				var index = getQuestionIndex(result.question.id);
				questions[index].title = result.question.title;
				questions[index].question = result.question.question;
				questions[index].authentication_type = result.question.authentication_type;
				updateQuestionUI(result.question.id);
				createQuestionForm();
			}, "json");
		}
		
		// create new question
		else {
			$.post("/new_question", data, function(result) {
				if (result.status == 0) {
					$("#newq_info").html(result.msg);
					return;
				}
				addQuestion(result.question, true);
				displayQuestionsList();
				selectQuestion(result.question.id);
				createQuestionForm();			
			}, "json");
		}
	}
}

function createQuestionForm() {
	$("#newq_info").html("");
	$("#newq_title").val("");
	$("#newq_question").val("");
	$("#newq_authentication").val(""+NO_AUTHENTICATION);
	$("#newq_button").val("Create new question");
	$("#newq_button").removeData("question_id");
}

function editQuestionForm(question_id) {
	var question = getQuestion(question_id);
	if (question) {
		$("#newq_info").html("");
		$("#newq_title").val(question.title);
		$("#newq_question").val(question.question);
		$("#newq_authentication").val(""+question.authentication_type);
		$("#newq_button").val("Update question");
		$("#newq_button").data("question_id", question.id);
	}
}

//==============================================================
// Questions
//==============================================================

function getQuestionIndex(question_id) {
	var index = -1;
	if (question_id) {
		for (var i in questions) {
			if (questions[i].id == question_id) {
				index = i;
				break;
			}
		}
	}
	return index;	
}

function getQuestion(question_id) {
	var question = null;
	var index = getQuestionIndex(question_id);
	return index != -1 ? questions[index] : null;
}

function getSelectedQuestion() {
	return selected_question_id ? getQuestion(selected_question_id) : null;
}

function isSelectedQuestion(question_id) {
	return selected_question_id && selected_question_id == question_id;
}

function addQuestion(question, addToFront) {
	addToFront = isDefined(addToFront) ? addToFront : false;
	question = initQuestionStats(question);
	if (addToFront) {
		questions.unshift(question);
	}
	else {
		questions.push(question);
	}
}

function initQuestionStats(question) {
	question.active_user_count = isDefined(question.active_user_count) ? question.active_user_count : 0;
	question.idea_count = isDefined(question.idea_count) ? question.idea_count : 0;
	question.idea_user_count = isDefined(question.idea_user_count) ? question.idea_user_count : 0;
	question.cascade_stats = isDefined(question.cascade_stats) ? question.cascade_stats : {};
	question.cascade_stats["category_count"] = 0;
	question.cascade_stats["completed_fit_count"] = 0;
	question.cascade_stats["total_fit_count"] = 0;
	question.cascade_stats["completed_verify_count"] = 0;
	question.cascade_stats["total_verify_count"] = 0;
	return question;
}

//==============================================================
// Channel support
//==============================================================

function handleIdea(data) {
	var question = getSelectedQuestion();
	if (question && data.idea.question_id==question.id) {
		question.idea_count++;
		updateIdeaCount(question);
		// only needed if used idea count to estimate number of fit jobs	
		//updatePercentComplete(question);
	}
}

function handleCategory(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_stats["category_count"]++;	
		updatePercentComplete(question);
	}
}

function handleFitComplete(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_stats["completed_fit_count"] += data.count;	
		updatePercentComplete(question);
	}
}

function handleVerifyComplete(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_stats["completed_verify_count"] += data.count;	
		updatePercentComplete(question);
	}
}

function handleMoreJobs(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		// currently only called when there are more fit and verify jobs
		// but could change in the future
		if (data.fit_count > 0 || data.verify_count > 0) {
			question.cascade_stats["total_fit_count"] += data.fit_count;	
			question.cascade_stats["total_verify_count"] += data.verify_count;	
			updatePercentComplete(question);
		}
	}
}

function handleResults(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_complete = 1;
		question.cascade_stats = data.cascade_stats;
		updateCategoryStatus(question);
		displayQuestionItem(question);
	}
}

function handleStudentLogin(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.active_user_count++;
		updateUserCount(question);
	}	
}

function handleStudentLogout(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.active_user_count--;
		updateUserCount(question);
	}
}

function handleLogout(data) {
	redirectToLogout();
}