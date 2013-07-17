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
	
	$("#p1button").click(function() {
		setPhase(PHASE_NOTES);
	});
	
	$("#p2button").click(function() {
		enableCascade();
	});
		
	$(".cascade_option").blur(function() {
		setCascadeOptions();
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
	html += "<a href='javascript:editQuestionForm(" + question.id + ")'>[edit]</a>&nbsp;&nbsp;&nbsp;&nbsp;";
	html += "<a href='javascript:downloadQuestion(" + question.id + ")'>[download]</a>&nbsp;&nbsp;&nbsp;&nbsp;";
	html += "<a href='javascript:deleteQuestion(" + question.id + ")'>[delete]</a><br/>";
	html += question.question + "<br/>";
	if (question.nickname_authentication) {
		html += '<span class="note"><em>Nickname authentication</em></span><br/>';
	}
	if (!question.active) {
		html += '<span class="note"><em>Inactive</em></span><br/>';
	}
	else if (!question.cascade_complete) {
		html += '<span class="note"><em>'+phaseToString(question.phase)+'</em></span><br/>';
	}
	
	if (question.cascade_complete) {
		html += "<span class='note'><em>Categories created</em></span>";
	}
	return html;
}

function selectQuestion(question_id) {
	selected_question_id = question_id;
	displaySelectedQuestion();
}

function displaySelectedQuestion() {
	var question = getSelectedQuestion();
	if (!question) {
		$("#selected_question").hide();
		return;
	}
		
	var html = "<strong>Question Code: " + question.id + "</strong><br/>";
	html += "Title: " + question.title + "<br/>";
	html += "Question: " + question.question + "<br/>";
	html += "<div id=\"stats\">&nbsp;</div><br/>";
	$("#question").html(html);
		
	// get question stats
	updateQuestionStats();
	
	$("#active_cb").prop("checked", question.active);
	$("#notes_link").attr("href", getPhaseUrl(question.id, PHASE_NOTES));
	$("#cascade_link").attr("href", getPhaseUrl(question.id, PHASE_CASCADE));
	$("#cascade_k").val(question.cascade_k);
	$("#cascade_k2").val(question.cascade_k2);
	$("#cascade_m").val(question.cascade_m);
	$("#cascade_p").val(question.cascade_p);
	$("#cascade_t").val(question.cascade_t);
	$("#results_link").attr("href", "/results?question_id=" + question.id);
	
	enableDisable($("#p1button"), question.active && question.phase != PHASE_NOTES);
	enableDisable($("#p2button"), question.active && question.phase != PHASE_CASCADE);
	enableDisable($(".cascade_option"), question.active && question.phase != PHASE_CASCADE);

	$("#p1button").val(question.phase == PHASE_NOTES ? "Note entry enabled" : "Enable note entry");
	$("#p2button").val(question.phase == PHASE_CASCADE ? "Cascade enabled" : "Enable Cascade");
	
	$("#selected_question").show();
}

function updateQuestionStats() {
// BEHAVIOR: currently stats are only retrieved for each question once per page load
	var question = getSelectedQuestion();
	if (!question) {
		return;
	}
	
	if (isDefined(question.num_ideas)) {
		displayQuestionStats(question);
	}
	else {
		data = {
			"request": "stats",
			"question_id": question.id
		}
		$.getJSON("/query", data, function(results) {
			var question = getQuestion(results.question_id);
			if (question) {
				question.idea_count = results["idea_count"];
				question.user_count = results["user_count"];
				if (isSelectedQuestion(question.id)) {
					displayQuestionStats(question);
				}
			}
		});
	}
}

function displayQuestionStats(question) {
	var ideaCount = question.idea_count;
	var userCount = question.user_count;
	var html = ideaCount + " notes, "+ userCount + " users";
	$("#stats").html(html);
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
		
		updateQuestion(result.question.id, result.question);				
	}, "json");
}


function setPhase(phase) {
	var question = getSelectedQuestion();
	if (!question) {
		alert("Phase not changed. Question not found.");
		return;
	}
	var data = {
		"client_id": client_id,
		"question_id": question.id,
		"phase": phase
	};
	$.post("/set_phase", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		
		updateQuestion(result.question.id, result.question);				
	}, "json");
}

function enableCascade() {
	var question = getSelectedQuestion();
	if (question.cascade_step == 0) {
		setPhase(PHASE_CASCADE);
	}
	// warn user that any existing cascade data will be deleted
	// warning appears if cascade ever enabled before
	// does not currently check whether or not any cascade data actually exists
	else {
		$("#cascade_confirm").css("display", "inline");
		$("#cascade_confirm").dialog({
			resizable: false,
			width: 300,
			height: 240,
			modal: true,
			buttons: {
				"Delete Cascade data": function() {
					setPhase(PHASE_CASCADE);
					$(this).dialog("close");
				},
				Cancel: function() {
					$(this).dialog("close");
				}
			}
		});
	}
}
function setCascadeOptions() {
	var question = getSelectedQuestion();
	if (!question) {
		alert("Cascade options not changed. Question not found.");
		return;
	}
	
	var cascade_k = $("#cascade_k").val();
	var cascade_k2 = $("#cascade_k2").val();
	var cascade_m = $("#cascade_m").val();
	var cascade_p = $("#cascade_p").val();
	var cascade_t = $("#cascade_t").val();
	
	$("#msg").html("");
	
	var allNonEmpty = cascade_k != "" && cascade_k2 != "" && cascade_m != "" && cascade_p != "" && cascade_t != "";
	if (!allNonEmpty) {
		$("#msg").html("Cascade options not changed. Empty values not allowed.");
		return;
	}
	
	var allNumbers = !isNaN(cascade_k) && !isNaN(cascade_k2) && !isNaN(cascade_m) && !isNaN(cascade_p) && !isNaN(cascade_t);
	if (!allNumbers) {
		$("#msg").html("Cascade options not changed. All values must be numbers.");
		return;
	}
	
	var nonZeroValues = cascade_k > 0 && cascade_k2 > 0 && cascade_m > 0 && cascade_t > 0;
	if (!nonZeroValues) {
		$("#msg").html("Cascade options not changed. k, k2, m, and t must be greater than 0.");
		return;
	}
	
	if (cascade_p > 100) {
		$("#msg").html("Cascade options not changed. p must be between 0-100.");
		return;
	}

	var data = {
		"client_id": client_id,
		"question_id": question.id,
		"cascade_k": cascade_k,
		"cascade_k2": cascade_k2,
		"cascade_m": cascade_m,
		"cascade_p": cascade_p,
		"cascade_t": cascade_t
	};
	$.post("/set_cascade_options", data, function(result) {
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		updateQuestion(result.question.id, result.question);
	}, "json");
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
				updateQuestion(result.question.id, result.question);
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
				selectQuestion(result.question.id, true);	
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

function deleteQuestion(question_id) {
	$("#delete_confirm").css("display", "inline");
	$("#delete_confirm").dialog({
		resizable: false,
		width: 300,
		height: 240,
		modal: true,
		buttons: {
			"Delete all data": function() {
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

function updateQuestion(question_id, data) {
	var index = getQuestionIndex(question_id);
	if (index != -1) {
		questions[index] = data;
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