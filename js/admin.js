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
var selected_question_id = null;

$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}

	initChannel();
	
	if (jQuery.browser.mobile) {
		$(".stats").hide();
	}
		
	$("#page_content").show();	
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
	
});

function loadQuestions() {
	$.getJSON("/query", { "request": "questions" }, function(results) {
		questions = [];
		for (i in results.questions) {
			addQuestion(results.questions[i]);
		}
		displayQuestionsList();
		var question_id = getURLParameter("question_id");
		if (question_id) {
			selectQuestion(question_id);
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
	html += "<a class='small' href='javascript:editQuestionForm(" + question.id + ")'>[edit]</a>&nbsp;&nbsp;&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:deleteQuestionData(" + question.id + ")'>[delete data]</a>&nbsp;&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:downloadQuestion(" + question.id + ")'>[download]</a>&nbsp;&nbsp;&nbsp;&nbsp;";
	html += "<a class='small' href='javascript:deleteQuestion(" + question.id + ")'>[delete]</a><br/>";
	html += question.question + "<br/>";
	if (question.nickname_authentication) {
		html += '<span class="note"><em>Nickname authentication</em></span><br/>';
	}
	if (!question.active) {
		html += '<span class="note"><em>Inactive</em></span><br/>';
	}
	
	if (question.cascade_complete) {
		html += "<span class='note'><em>Categories created</em></span>";
	}
	return html;
}

function selectQuestion(question_id) {
	selected_question_id = question_id;
	if (question_id) {
		loadStats();
	}
	else {
		$("#selected_question").hide();
	}
}

function displayQuestion(question_id) {
	var index = getQuestionIndex(question_id);
	if (index != -1) {
		if (isSelectedQuestion(question_id)) {
			displaySelectedQuestion();
		}
		displayQuestionItem(questions[index])		
	}
}

function displaySelectedQuestion() {
	var question = getSelectedQuestion();
	if (!question) {
		$("#selected_question").hide();
		return;
	}
	
	var html = "<h2 class='spacebelow'>Selected question:</h2>";
	html += "<strong>" + question.title + "</strong> <span class='note'>#" + question.id + "</span><br/>";
	html += question.question + "<br/>";
	html += "<div id='question_stats' class='small largespacebelow'>&nbsp;</div>";
	$("#question").html(html);
		
	displayStats(question);
	
	$("#active_cb").prop("checked", question.active);
	$("#note_link").attr("href", getNotesPageUrl(question.id));
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
			question.user_count = results["user_count"];
			question.active_user_count = results["active_user_count"];
			question.cascade_stats = results["cascade_stats"];
			if (isSelectedQuestion(question.id)) {
				displaySelectedQuestion(question);
			}
		}
	});
}

function displayStats(question) {
	displayQuestionStats(question);
	displayCascadeProgress(question);
}

function displayQuestionStats(question) {
	var ideaCount = question.idea_count;
	var userCount = question.user_count;
	var activeUserCount = question.active_user_count;
	var stats = [];
	stats.push(ideaCount + (ideaCount!=1 ? " notes" : " note"));
	stats.push(userCount + (userCount!=1 ? " users" : " user"));
	stats.push(activeUserCount + (activeUserCount!=1 ? " active users" : " active user"));
	$("#question_stats").html("("+stats.join(", ")+")");
}

function displayCascadeProgress(question) {        
	var html = "<div class='smallspacebelow'><strong>Category Progress</strong></div>";
	html += "<div style='font-size:24px;text-align:center'><span id='percent_complete'></span>%</div>";
	html += "<div style='font-size:11px;text-align:center' class='spacebelow'>COMPLETE</div>";

	if (question.idea_count > 0) {		
		if (question.cascade_complete) {
			html += question.cascade_stats["idea_count"] + (question.cascade_stats["idea_count"] > 1 ? "&nbsp;notes" : "&nbsp;note") + "<br/>";
			html += question.cascade_stats["category_count"] + (question.cascade_stats["category_count"] > 1 ? "&nbsp;categories" : "&nbsp;category") + "<br/>";
			if (question.cascade_stats["uncategorized_count"] > 0) {
				html += question.cascade_stats["uncategorized_count"] + "&nbsp;uncategorized";
			}
		}
		html += "<div class='note'>k=" + question.cascade_k + ", k2=" + question.cascade_k2 + ", m=50%, s=" + question.cascade_s + ", t=" + question.cascade_t + "</div>";
	}
	else {
		html += "<div class='note' style='text-align:center'>NO NOTES ADDED YET</div>";		
	}
	$("#cascade_progress").html(html);	
	updatePercentComplete(question)
	
	if (!question.cascade_complete) {
		enableDisable($("#create_categories_button"), question.idea_count > 0);
		$("#create_categories_button").show();
	}
	else {
		$("#create_categories_button").hide();
	}
}

function updatePercentComplete(question) {
    // calculate percentage complete
    var percentComplete = 0;
    if (question.cascade_complete) {
    	percentComplete = 100;
    }
    else {
    	var jobsCompleted = question.cascade_stats["completed_fit_count"];
    	var totalJobCount = question.cascade_stats["category_count"] * question.idea_count * question.cascade_k2;
    	percentComplete = totalJobCount > 0 ? Math.floor((jobsCompleted / totalJobCount)*100) : 0;
    }
    $("#percent_complete").html(percentComplete);
}
    
function createEditQuestion() {
	var title = $("#newq_title").val();
	var questionText = $("#newq_question").val();
	
	if (!title || !questionText) {
		$("#newq_info").html("Title and question required");
	}
	
	else {
		var data = {
			"client_id": client_id,
			"title": title,
			"question": questionText,
			"nickname_authentication": $("#newq_nickname_authentication").is(":checked") ? "1" : "0"			
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
				questions[index].nickname_authentication = result.question.nickname_authentication;
				displayQuestion(result.question.id);
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
				addQuestion(result.question);
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
	$("#newq_nickname_authentication").prop("checked", false);
	$("#newq_button").val("Create new question");
	$("#newq_button").removeData("question_id");
}

function editQuestionForm(question_id) {
	var question = getQuestion(question_id);
	if (question) {
		$("#newq_info").html("");
		$("#newq_title").val(question.title);
		$("#newq_question").val(question.question);
		$("#newq_nickname_authentication").prop("checked", question.nickname_authentication);
		$("#newq_button").val("Update question");
		$("#newq_button").data("question_id", question.id);
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
		displayQuestion(result.question.id);			
	}, "json");
}

function downloadQuestion(question_id) {
	window.location = "/download_question?question_id="+question_id+"&utc_offset_minutes="+(new Date()).getTimezoneOffset()
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
						if (isSelectedQuestion(question_id)) {
							displaySelectedQuestion();
						}
						displayQuestionItem(result.question);
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

function createCategories() {
	var question = getSelectedQuestion();
	if (!question) {
		return;
	}
	var data = {
		"client_id": client_id,
		"question_id": question.id,
	};
	$.post("/generate_categories", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		redirectToResultsPage(result.question_id);		
	}, "json");
}

function getQuestion(question_id) {
	var question = null;
	var index = getQuestionIndex(question_id);
	return index != -1 ? questions[index] : null;
}

function addQuestion(question) {
	question = initQuestionStats(question);
	questions.push(question);
}

function initQuestionStats(question) {
	question.idea_count = isDefined(question.idea_count) ? question.idea_count : 0;
	question.user_count = isDefined(question.user_count) ? question.user_count : 0;
	question.active_user_count = isDefined(question.active_user_count) ? question.active_user_count : 0;
	question.cascade_stats = isDefined(question.cascade_stats) ? question.cascade_stats : {};
	question.cascade_stats["category_count"] = 0;
	question.cascade_stats["completed_fit_count"] = 0;
	return question;
}

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

function getSelectedQuestion() {
	return selected_question_id ? getQuestion(selected_question_id) : null;
}

function isSelectedQuestion(question_id) {
	return selected_question_id && selected_question_id == question_id;
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	var question = getSelectedQuestion();
	if (question && data.idea.question_id==question.id) {
		question.idea_count++;		
		displayStats(question);
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

function handleCascadeSettings(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_k = data.cascade_k;
		question.cascade_k2 = data.cascade_k2;
		question.cascade_m = data.cascade_m;
		question.cascade_s = data.cascade_s;
		question.cascade_t = data.cascade_t;
		displayCascadeProgress(question);
	}
}

function handleResults(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_complete = 1;
		question.cascade_stats = data.cascade_stats;
		displayCascadeProgress(question);
		displayQuestionItem(question);
	}
}

function handleStudentLogin(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.active_user_count++;
		if (data.is_new) {
			question.user_count++;
		}
		displayStats(question);
	}	
}

function handleStudentLogout(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.active_user_count--;
		displayStats(question);
	}
}

function handleLogout(data) {
	redirectToLogout();
}