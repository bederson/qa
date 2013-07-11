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
		
	$("#p0button").click(function() {
		var question = getSelectedQuestion();
		setPhase(question.phase == PHASE_DISABLED ? PHASE_NOTES : PHASE_DISABLED);
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
	html += "<a href='javascript:deleteQuestion(" + question.id + ")'>[delete]</a><br/>";
	html += question.question + "<br/>";
	if (question.nickname_authentication) {
		html += '<span class="note"><em>Nickname authentication</em></span><br/>';
	}
	html += '<em><span class="note">'+phaseToString(question.phase)+'</em></span>';
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
		
	$("#notes_link").attr("href", getPhaseUrl(question.id, PHASE_NOTES));
	$("#cascade_link").attr("href", getPhaseUrl(question.id, PHASE_CASCADE));
	$("#cascade_k").val(question.cascade_k);
	$("#cascade_m").val(question.cascade_m);
	$("#cascade_t").val(question.cascade_t);
	$("#results_link").attr("href", "/results?question_id=" + question.id);
	
	if (question.phase == PHASE_DISABLED) {
		$("#p0button").val("Enable question");
		$("#p1button").val("Note entry disabled");
		$("#p2button").val("Cascade disabled");
		$(".cascade_option").attr("disabled", "disabled");
	} 
	else {
		$("#p0button").val("Disable question");
		$("#p1button").val(question.phase == PHASE_NOTES ? "Note entry enabled" : "Enable note entry");
		$("#p2button").val(question.phase == PHASE_CASCADE ? "Cascade enabled" : "Enable Cascade");
		if (question.phase == PHASE_CASCADE) {
			$(".cascade_option").attr("disabled", "disabled");
		}
		else {
			$(".cascade_option").removeAttr("disabled");
		}
	}
	
	enableDisable($("#p1button"), question.phase != PHASE_DISABLED && question.phase != PHASE_NOTES);
	enableDisable($("#p2button"), question.phase != PHASE_DISABLED && question.phase != PHASE_CASCADE)

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
				question.num_ideas = results["num_ideas"];
				question.num_users = results["num_users"];
				if (isSelectedQuestion(question.id)) {
					displayQuestionStats(question);
				}
			}
		});
	}
}

function displayQuestionStats(question) {
	var numIdeas = question.num_ideas;
	var numUsers = question.num_users;
	var html = numIdeas + " notes, "+ numUsers + " users";
	$("#stats").html(html);
	
	// TODO: incomplete
	//$("#notes_stats").html(numIdeas + " notes");
	//$("#cascade_stats").html("Step " + question.cascade_step + " in progress");
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
		alert("Cascade options not changed. Question not found");
		return;
	}
	
	var data = {
		"client_id": client_id,
		"question_id": question.id,
		"cascade_k": $("#cascade_k").val(),
		"cascade_m": $("#cascade_m").val(),
		"cascade_t": $("#cascade_t").val()
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