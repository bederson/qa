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

$(document).ready(function() {
	if (!logged_in) {
		$("#msg").html("Please log in with a Google account to create/edit your own questions");
		return;
	}

	question_id = getURLParameter("question_id");
	if (!question_id || question!="") {	
		initEventHandlers();
		updateButtons();
		displayModes();
		displayQuestions();	
		$("#admin_area").show();
	}
});

function initEventHandlers() {
	$("#p0button").click(function() {
		if (phase == PHASE_DISABLED) {
			set_phase(PHASE_NOTES);
		} else {
			set_phase(PHASE_DISABLED);
		}
	});
	$("#p1button").click(function() {
		set_phase(PHASE_NOTES);
	});
	$("#p5button").click(function() {
		set_phase(PHASE_CASCADE);
	});
	$("#newq_button").click(function() {
		createQuestion();
	});
	$(".cascade_option").blur(function() {
		set_cascade_options($("#cascade_k").val(), $("#cascade_m").val(), $("#cascade_t").val());
	});
}

function set_phase(new_phase) {	
	var question_id = getURLParameter("question_id");
	var data = {
		"client_id": client_id,
		"phase": new_phase,
		"question_id": question_id
	};
	
	$.post("/set_phase", data, function() {
		phase = new_phase;
		updateButtons();
		$("#question_"+data.question_id+"_phase").html(phaseToString(new_phase));
	});
}

function set_cascade_options(k, m, t) {
	var question_id = getURLParameter("question_id");
	var data = {
		"client_id": client_id,
		"question_id": question_id,
		"cascade_k": k,
		"cascade_m": m,
		"cascade_t": t
	};
	$.post("/set_cascade_options", data);
}

function displayModes() {
	var question_id = getURLParameter("question_id");
	if (isDefined(question_id)) {
		var html = "";
		html += "<strong>Question Code: " + question_id + "</strong><br/>";
		html += "Title: " + title + "<br/>";
		html += "Question: " + question + "<br/>";
		html += "<div id=\"stats\">&nbsp;</div><br/>";
		$("#question").html(html);
		
		// get question stats
		displayQuestionStats(question_id);
		
		$("#notes_link").attr("href", getPhaseUrl(question_id, PHASE_NOTES));
		$("#cascade_link").attr("href", getPhaseUrl(question_id, PHASE_CASCADE));
		$("#cascade_k").val(cascade_k);
		$("#cascade_m").val(cascade_m);
		$("#cascade_t").val(cascade_t);
		$("#results_link").attr("href", "/results?question_id=" + question_id);

		$("#question_buttons").css("display", "table");
		updateButtons();
	}
}

function displayQuestions() {
	$.getJSON("/query", { "request": "questions" }, function(results) {
		if (results.questions.length == 0) {
			$("#questions_heading").css("display", "none");
		} else {
			var html = "<ul>";
			for (var i in results.questions) {
				var question = results.questions[i];
				html += '<li id="question_'+question.id+'"></li>';
			}
			html += "</ul>";
			$("#questions").html(html);
			
			for (var i in results.questions) {
				var question = results.questions[i];
				updateQuestionListItem(question);
			}
		}
	});	
}

function displayQuestionStats(question_id) {
	data = {
		"request": "stats",
		"question_id": question_id
	}
	$.getJSON("/query", data, function(results) {
		var html = results["num_ideas"] + " notes";
		$("#stats").html(html);
	});	
}

function updateQuestionListItem(question) {
	var html = "<a href='" + getAdminPageUrl(question.id) + "'>" + question.title + "</a> <span class='note'>#"+question.id+"</span>";
	html += "&nbsp;&nbsp;&nbsp;&nbsp;<a id=edit_question href='javascript:editQuestion(" + question.id + ")'>[edit]</a>";
	html += "&nbsp;&nbsp;&nbsp;&nbsp;<a id=delete_question href='javascript:deleteQuestion(" + question.id + ")'>[delete]</a>";
	html += "<br>";
	html += question.question;
	if (question.nickname_authentication) {
		html += '<br/><span class="note"><em>Nickname authentication</em></span>';
	}
	html += '<br/><em><span id="question_'+question.id+'_phase" class="note">'+phaseToString(question.phase)+'</em></span>';
	$("#question_"+question.id).html(html);
}

function createQuestion() {
	var title = $("#newq_title").val();
	var question = $("#newq_question").val();
	
	if (!title || !question) {
		$("#newq_info").html("Title and question required");
	}
	else if (isDefined($("#newq_button").data("question_id"))) {
		// Edit question
		var data = {
			"client_id": client_id,
			"title": title,
			"question": question,
			"nickname_authentication": $("#newq_nickname_authentication").is(":checked") ? "1" : "0",
			"question_id": $("#newq_button").data("question_id")
		};
		$.post("/editquestion", data, function(result) {
			if (result.status == 0) {
				$("#newq_info").html(result.msg);
				return;
			}
			updateQuestionListItem(result.question);
		}, "json");
	} else {
		// Create new question
		var data = {
			"client_id": client_id,
			"title": title,
			"question": question,
			"nickname_authentication": $("#newq_nickname_authentication").is(":checked") ? "1" : "0"			
		};
		$.post("/newquestion", data, function(result) {
			if (result.status == 0) {
				$("#newq_info").html(result.msg);
				return;
			}
			redirectToAdminPage(result.question_id);
		}, "json");
	}
}

function editQuestion(question_id) {
	// TODO: load question info from memory, no need to go back to db
	$("#newq_info").html("");
	data = {
		"request": "question",
		"question_id": question_id
	}
	$.getJSON("/query", data, function(results) {
		$("#newq_title").val(results.title);
		$("#newq_question").val(results.question);
		$("#newq_nickname_authentication").prop("checked", results.nickname_authentication==1);
		$("#newq_button").val("Update question");
		$("#newq_button").data("question_id", question_id);
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
			"Delete all data": function() {
				deleteQuestionImpl(question_id);
				$(this).dialog( "close" );
			},
			Cancel: function() {
				$(this).dialog( "close" );
			}
		}
	});
}

function deleteQuestionImpl(question_id) {
	var data = {
		"client_id": client_id,
		"question_id": question_id
	};
	$.post("/delete", data, function(result) {
		redirectToAdminPage();
	});
}

function updateButtons() {
	if (phase == PHASE_DISABLED) {
		$("#p0button").val("Enable question");
		$("#p1button").val("Note entry disabled");
		$("#p5button").val("Cascade disabled");
		$("#p1button").attr("disabled", "disabled");
		$("#p5button").attr("disabled", "disabled");
	} else {
		$("#p0button").val("Disable question");
		$("#p1button").val("Enable adding of notes");
		$("#p5button").val("Enable Cascade");
		$("#p1button").removeAttr("disabled");
		$("#p5button").removeAttr("disabled");
		
		if (phase == PHASE_NOTES) {
			$("#p1button").val("Note entry enabled");
			$("#p1button").attr("disabled", "disabled");
		} else if (phase == PHASE_CASCADE) {
			$("#p5button").val("Cascade enabled");
			$("#p5button").attr("disabled", "disabled");
		}
	}
}