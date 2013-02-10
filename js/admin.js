// Copyright 2013 Ben Bederson - http://www.cs.umd.edu/~bederson
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

$(function() {
	initChannel();
	initEventHandlers();
	displayModes();
	displayQuestions();
});

function initEventHandlers() {
	$("#p0button").click(function() {
		set_phase(0);
	});
	$("#p1button").click(function() {
		set_phase(1);
	});
	$("#p2button").click(function() {
		set_phase(2);
	});
	$("#notes_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href = "/idea?question_id=" + question_id;
	});
	$("#tags_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href = "/tag?question_id=" + question_id;
	});
	$("#results_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href = "/results?question_id=" + question_id;
	});
	$("#newq_button").click(function() {
		var data = {
			"client_id": client_id,
			"title": $("#newq_title").val(),
			"question": $("#newq_question").val()
		};
		$.post("/newquestion", data, function(result) {
			if (parseInt(result.question_id) > 0) {
				window.location.href = "/admin?question_id=" + result.question_id;
			} else {
				$("#newq_info").html("Failed to create question - maybe it is too short.");
			}
		});
	})
}

function set_phase(phase) {
	var question_id = getURLParameter("question_id");
	var data = {
		"client_id": client_id,
		"phase": phase,
		"question_id": question_id
	};
	$.post("/set_phase", data);
	updateButtons(phase);
}

function displayModes() {
	var question_id = getURLParameter("question_id");
	if (isDefined(question_id)) {
		data = {
			"request": "question",
			"question_id": question_id
		};
		$.getJSON("/query", data, function(results) {
			var html = "Title: " + results.title + "<br>Question: " + results.question + "<br><br>";
			$("#question").html(html);
		});
		
		$("#phase_table").css("display", "table");
		data = {
			"request": "phase",
			"question_id": question_id
		};
		$.getJSON("/query", data, function(results) {
			phase = parseInt(results.phase);
			updateButtons(phase);
		});
	}
}

function displayQuestions() {
	data = {
		"request": "questions"
	};
	$.getJSON("/query", data, function(results) {
		displayQuestionsImpl(results)
	});	
}

function displayQuestionsImpl(results) {
	var questions = results.questions;
	var html = "<ul>";
	for (var i in questions) {
		var question = questions[i];
		html += "<li><a href='/admin?question_id=" + question.question_id + "'>" + question.title + "</a>";
		html += "&nbsp;&nbsp;&nbsp;&nbsp;<a id=delete_question href='javascript:deleteQuestion(" + question.question_id + ")'>[delete]</a>";
		html += "<br>";
		html += question.question;
	}
	html += "</ul>";
	$("#questions").html(html);
}

function deleteQuestion(question_id) {
	$("#delete_confirm").css("display", "inline");
	$("#delete_confirm").dialog({
		resizable: false,
		width: 300,
		height: 240,
		modal: true,
		buttons: {
			"Delete all items": function() {
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
		window.location.href="/admin";
	});
}

function updateButtons(phase) {
	$("#p0button").removeAttr("disabled");
	$("#p1button").removeAttr("disabled");
	$("#p2button").removeAttr("disabled");
	if (phase == 0) {
		$("#p0button").attr("disabled", "disabled");
	} else if (phase == 1) {
		$("#p1button").attr("disabled", "disabled");
	} else if (phase == 2) {
		$("#p2button").attr("disabled", "disabled");
	}
}

/////////////////////////
// Channel support
/////////////////////////
function handleNew(data) {
	// Ignore it
}

function handleRefresh(data) {
	// Ignore it
}

function handlePhase(data) {
	// Ignore it
}

function handleTag(data) {
	// Ignore it
}