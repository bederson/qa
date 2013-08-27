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
});

function loadQuestions() {
	$.getJSON("/query", { "request": "questions" }, function(results) {
		questions = results.questions;
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
			calculateCascadeOptions(question);
						
			if (isSelectedQuestion(question.id)) {
				displaySelectedQuestion(question);
			}
		}
	});
}

function displayStats(question) {
	displayQuestionStats(question);
	displayCascadeStats(question);
}

function displayQuestionStats(question) {
	var ideaCount = isDefined(question.idea_count) ? question.idea_count : 0;
	var userCount = isDefined(question.user_count) ? question.user_count : 0;
	var activeUserCount = isDefined(question.active_user_count) ? question.active_user_count : 0;
	var stats = [];
	stats.push(ideaCount + (ideaCount!=1 ? " notes" : " note"));
	stats.push(userCount + (userCount!=1 ? " users" : " user"));
	stats.push(activeUserCount + (activeUserCount!=1 ? " active users" : " active user"));
	$("#question_stats").html("("+stats.join(", ")+")");
}

function displayCascadeStats(question) {
    var m = Math.min(question.idea_count, question.cascade_m);
    var n = question.idea_count;
    var k = question.cascade_k;
    var k2 = question.cascade_k2;
    var t = question.cascade_t;
    var workerCount = getCascadeWorkerCount(question);
    
	var title = "";
    var cascade_job_counts = [];
    var cascade_step_durations = [];
    
    // if cascade not complete, estimate cascade job info
    if (!question.cascade_complete) {
    	title = "Cascade Estimates";
    	// step 1
    	var count = Math.ceil(m/t) * k;
    	cascade_job_counts.push(count);
    
    	// step 2
    	count = m * k;
    	cascade_job_counts.push(m * k);
    
    	// step 3
    	var C = Math.ceil(1.5 * m); 	// estimate
    	count = m * Math.ceil(C/t) * k2;
    	cascade_job_counts.push(count);

    	// step 4
    	count = !skip_verify ? m * k2 : 0;
    	cascade_job_counts.push(count);

    	// step 5
    	C = Math.ceil(0.33 * m); 		// estimate - smaller than in step 3
    	count = (n-m) * Math.ceil(C/t) * k2;
    	cascade_job_counts.push(count);
    	
    	for (var i=0; i<cascade_job_counts.length; i++) {
    		var stepDuration = workerCount > 0 ? Math.ceil(cascade_job_counts[i] / workerCount) * TIME_REQUIRED_PER_CASCADE_JOB : 0;
			cascade_step_durations.push(stepDuration);
    	}
    }
    else {
    	title = "Cascade Stats";
    	if (question.cascade_stats != null) {
    		for (var i=0; i<max_cascade_steps; i++) {
    			cascade_job_counts.push(question.cascade_stats["step"+(i+1)+"_job_count"]);
    			cascade_step_durations.push(question.cascade_stats["step"+(i+1)+"_duration"]);
    		}
    	}
    }
    
	var html = "<strong>" + title + "</strong><br/>";
	html += "<table class='smallpadbottom' style='margin-bottom:0px'>";
	var totalJobCount = 0;
	var completionTime = 0;
	for (var i=0; i<cascade_job_counts.length; i++) {
		var step = i+1;
		var jobCount = cascade_job_counts[i];
		totalJobCount += jobCount;
		var stepDuration = cascade_step_durations[i];
		completionTime += stepDuration;
		html += "<tr>";
		html += "<td>Step&nbsp;" + step + "</td>";
		html += "<td>" + (jobCount > 0 ? jobCount + (jobCount > 1 ? "&nbsp;jobs" : "&nbsp;job") : "-") + "</td>";
		html += "<td>" + toHHMMSS(stepDuration) + "</td>";
		// TODO: update stats w/ new process
		//html += "<td>" + (isStepComplete ? "<img src='/images/check.png'/>" : (isCurrentStep ? "<img src='/images/left-arrow.png'/>" : "&nbsp;")) + "</td>";
		html += "</tr>";
	}
		
	html += "<tr>";
	html += "<td><strong>TOTAL</strong></td>";
	html += "<td>" + (totalJobCount > 0 ? totalJobCount + "&nbsp;jobs" : "-") + "</td>";
	html += "<td>" + toHHMMSS(completionTime) + "</td>";
	//html += "<td>" + (question.cascade_complete ? "<img src='/images/check.png'/>" : "&nbsp;") + "</td>";
	html += "</tr>";
		
	// jobs per user
	if (workerCount > 1 && totalJobCount > 0) {
		html += "<tr>";
		html += "<td>&nbsp;</td>";
		html += "<td>" + Math.ceil(totalJobCount/workerCount) + " jobs/user</td>";
		html += "</tr>";
	}

	html += "</table>";

	// link to results		
	if (question.cascade_complete) {
		html += "<div class='green_highlight'>";
		html += "<a href='/results?question_id=" + question.id + "'>View results</a>";
		html += "</div>";
	}
		
	// note about cascade estimates
	if (!question.cascade_complete) {
		if (question.idea_count > 0) {
			html += "<div class='note'>";
			html += "Estimates assume " + question.idea_count + (question.idea_count > 1 ? "&nbsp;notes" : "&nbsp;note");
			html += ", " + Math.ceil(Math.min(question.idea_count,question.cascade_m) * 1.5) + "&nbsp;best&nbsp;categories";
			if (workerCount > 0) {
				html += ", " + workerCount + (workerCount > 1 ? "&nbsp;users" : "&nbsp;user");
				html += ", " + TIME_REQUIRED_PER_CASCADE_JOB + "&nbsp;seconds per job"; 
			}
			html += "</div>";
		}
	}
	else if (question.cascade_stats != null) {
		html += "<div class='note'>";
		html += "Cascade performed";
		html += " on " + question.cascade_stats["idea_count"] + (question.cascade_stats["idea_count"] > 1 ? "&nbsp;notes" : "&nbsp;note");
		html += " by " + question.cascade_stats["user_count"] + (question.cascade_stats["user_count"] > 1 ? "&nbsp;users" : "&nbsp;user");
		if (question.cascade_stats["iteration_count"] > 1) {
			html += " in " + question.cascade_stats["iteration_count"] + "&nbsp;iterations";
		}
		html += "; " + question.cascade_stats["category_count"] + (question.cascade_stats["category_count"] > 1 ? "&nbsp;categories" : "&nbsp;category") + " created";
		if (question.cascade_stats["uncategorized_count"] > 0) {
			html += " (" + question.cascade_stats["uncategorized_count"] + "&nbsp;uncategorized)";
		}
		html += "</div>";
	}
	
	if (totalJobCount > 0 || question.cascade_complete) {
		html += "<div class='note'>k=" + question.cascade_k + ", k2=" + question.cascade_k2 + ", m=" + question.cascade_m + ", t=" + question.cascade_t + "</div>"; 
	}
	
	$("#cascade_stats").html(html);	
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

function calculateCascadeOptions(question, forceUpdate) {	
	forceUpdate = isDefined(forceUpdate) ? forceUpdate : false;
	
	// use values stored in db if cascade complete
	if (question.cascade_complete) {
		return;
	}
	
	// TODO / FIX: set cascade options, send to server, do NOT change once set
	
	if (question.idea_count == 0) {
		return;
	}
	
	var cascade_m = Math.ceil(question.idea_count / 2);
	var cascade_p = 80;
	var cascade_t = 3;

	var workerCount = getCascadeWorkerCount(question);
	var ideasPerWorker = question.idea_count / workerCount;
	
	if (workerCount == 1) {
		cascade_k = 1;
		cascade_k2 = 1;
	}
	else if (ideasPerWorker >= 3.5) {
		cascade_k = 1;
		cascade_k2 = 1;
	}
	
	else if (ideasPerWorker >= 0.5) {
		cascade_k = 2;
		cascade_k2 = 1;
	}
	else {
		cascade_k = 3;
		cascade_k2 = 2;
	}

	question.cascade_k = cascade_k;
	question.cascade_k2 = cascade_k2;
	question.cascade_m = cascade_m;
	question.cascade_p = cascade_p;
	question.cascade_t = cascade_t;
}

function getCascadeWorkerCount(question) {
	// assume admin is going to perform Cascade tasks if no active users
	return question.active_user_count > 0 ? question.active_user_count : 1;
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
				questions.push(result.question);
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
						var index = getQuestionIndex(question_id);
						questions[index] = result.question;
						if (isSelectedQuestion(question_id)) {
							displaySelectedQuestion();
						}
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

function displayQuestion(question_id) {
	var index = getQuestionIndex(question_id);
	if (index != -1) {
		if (isSelectedQuestion(question_id)) {
			displaySelectedQuestion();
		}
		displayQuestionItem(questions[index])		
	}
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

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	var question = getSelectedQuestion();
	if (question && data.idea.question_id==question.id) {
		question.idea_count++;
		
		calculateCascadeOptions(question);
		displayStats(question);
	}
}

function handleIdeasDone(data) {
	// ignore
}

function handleResults(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.cascade_complete = 1;
		question.cascade_stats = data.cascade_stats;
		displayCascadeStats(question);
		displayQuestionItem(question);
	}
}

function handleStudentLogin(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.active_user_count++;
		if (data.is_new) {
			question.user_count++;
			calculateCascadeOptions(question);
		}
		displayStats(question);
	}	
}

function handleStudentLogout(data) {
	var question = getSelectedQuestion();
	if (question && data.question_id==question.id) {
		question.active_user_count--;
		calculateCascadeOptions(question);
		displayStats(question);
	}
}

function handleLogout(data) {
	redirectToLogout();
}