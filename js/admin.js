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
		if (phase == 0) {
			set_phase(1);
		} else {
			set_phase(0);
		}
	});
	$("#p1button").click(function() {
		set_phase(1);
	});
	$("#p2button").click(function() {
		set_phase(2);
	});
	$("#p3button").click(function() {
		set_phase(3);
	});
	$("#p4button").click(function() {
		set_phase(4);
	});
	$("#p5button").click(function() {
		set_phase(5);
	});
	$("#newq_button").click(function() {
		createQuestion();
	});
	$("#num_notes_to_tag_per_person").blur(function() {
		set_num_notes_to_tag_per_person($("#num_notes_to_tag_per_person").val());
	});
	$("#num_notes_to_compare_per_person").blur(function() {
		set_compare_notes_options($("#num_notes_to_compare_per_person").val(), $("#num_notes_for_comparison").val());
	});
	$("#num_notes_for_comparison").blur(function() {
		set_compare_notes_options($("#num_notes_to_compare_per_person").val(), $("#num_notes_for_comparison").val());
	});
	
	$(".cascade_option").blur(function() {
		set_cascade_options($("#cascade_k").val(), $("#cascade_m").val(), $("#cascade_t").val());
	});
}

function set_phase(new_phase) {	
	if (new_phase == PHASE_TAG_BY_CLUSTER && num_clusters==0) {
		alert('Clusters must be created before tagging by cluster can be enabled. Go to the Results page to create clusters.');
		return;
	}
	
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

function set_num_notes_to_tag_per_person(num_notes) {
	var question_id = getURLParameter("question_id");
	var data = {
		"client_id": client_id,
		"num_notes_to_tag_per_person": num_notes,
		"question_id": question_id
	};
	$.post("/set_num_notes_to_tag_per_person", data);
}

function set_compare_notes_options(num_notes, num_comparison_notes) {
	var question_id = getURLParameter("question_id");
	var data = {
		"client_id": client_id,
		"num_notes_to_compare_per_person": num_notes,
		"num_notes_for_comparison": num_comparison_notes,
		"question_id": question_id
	};
	$.post("/set_compare_notes_options", data);
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
		html += num_ideas + " notes, ";
		html += num_tags_by_cluster + " tags on clusters, ";
		html += num_tags_by_idea + " tags on notes, ";
		html += num_similar_ideas + " similar notes<br/>";
		html += "<br/>";
		$("#question").html(html);
		
		$("#tagbycluster_link").attr("href", "/tag?question_id=" + question_id);
		$("#tagbynote_link").attr("href", "/tag?question_id=" + question_id);
		$("#comparebysimilarity_link").attr("href", "/similar?question_id=" + question_id);
		$("#cascade_link").attr("href", "/cascade?question_id=" + question_id);
		$("#notes_link").attr("href", "/idea?question_id=" + question_id);
		$("#results_link").attr("href", "/results?question_id=" + question_id);
		$("#num_notes_to_tag_per_person").val(num_notes_to_tag_per_person);
		$("#num_notes_to_compare_per_person").val(num_notes_to_compare_per_person);
		$("#num_notes_for_comparison").val(num_notes_for_comparison);
		$("#cascade_k").val(cascade_k);
		$("#cascade_m").val(cascade_m);
		$("#cascade_t").val(cascade_t);
	
		$("#question_buttons").css("display", "table");
		updateButtons();
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
	if (questions.length == 0) {
		$("#questions_heading").css("display", "none");
	} else {
		var html = "<ul>";
		for (var i in questions) {
			html += '<li id="question_'+questions[i].question_id+'"></li>';
		}
		html += "</ul>";
		$("#questions").html(html);

		for (var i in questions) {
			updateQuestionListItem(questions[i]);
		}
	}
}

function updateQuestionListItem(question) {
	var html = "<a href='/admin?question_id=" + question.question_id + "'>" + question.title + "</a> <span class='note'>#"+question.question_id+"</span>";
	html += "&nbsp;&nbsp;&nbsp;&nbsp;<a id=edit_question href='javascript:editQuestion(" + question.question_id + ")'>[edit]</a>";
	html += "&nbsp;&nbsp;&nbsp;&nbsp;<a id=delete_question href='javascript:deleteQuestion(" + question.question_id + ")'>[delete]</a>";
	html += "<br>";
	html += question.question;
	if (question.nickname_authentication) {
		html += '<br/><span class="note"><em>Nickname authentication</em></span>';
	}
	html += '<br/><em><span id="question_'+question.question_id+'_phase" class="note">'+phaseToString(question.phase)+'</em></span>';
	$("#question_"+question.question_id).html(html);
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
			window.location.href = "/admin?question_id=" + result.question_id
			updateButtons();
		}, "json");
	}
}

function editQuestion(question_id) {
	$("#newq_info").html("");
	data = {
		"request": "question",
		"question_id": question_id
	}
	$.getJSON("/query", data, function(results) {
		$("#newq_title").val(results.title);
		$("#newq_question").val(results.question);
		$("#newq_nickname_authentication").attr("checked", results.nickname_authentication);
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

function updateButtons() {
	var enableTaggingByCluster = num_clusters > 0;
	if (phase == 0) {
		$("#p0button").val("Enable question");
		$("#p1button").val("Note entry disabled");
		$("#p2button").val("Tagging by cluster disabled");
		$("#p3button").val("Tagging by note disabled");
		$("#p4button").val("Comparing by similarity disabled");
		$("#p5button").val("Cascade disabled");
		$("#p1button").attr("disabled", "disabled");
		$("#p2button").attr("disabled", "disabled");
		$("#p3button").attr("disabled", "disabled");
		$("#p4button").attr("disabled", "disabled");
		$("#p5button").attr("disabled", "disabled");
		$("#tagsbycluster_msg").html("");
	} else {
		$("#p0button").val("Disable question");
		$("#p1button").val("Enable adding of notes");
		$("#p2button").val("Enable tagging by cluster");
		$("#p3button").val("Enable tagging by note");
		$("#p4button").val("Enable comparing by similarity");
		$("#p5button").val("Enable Cascade");
		$("#p1button").removeAttr("disabled");
		$("#p2button").removeAttr("disabled");
		$("#p3button").removeAttr("disabled");
		$("#p4button").removeAttr("disabled");
		$("#p5button").removeAttr("disabled");
		
		if (!enableTaggingByCluster) {
			var question_id = getURLParameter("question_id");
			$("#tagsbycluster_msg").html('Must <a class="warning" href="/results?question_id='+question_id+'">create clusters</a> first');
		}
		
		if (phase == 1) {
			$("#p1button").val("Note entry enabled");
			$("#p1button").attr("disabled", "disabled");
		} else if (phase == PHASE_TAG_BY_CLUSTER) {
			$("#p2button").val("Tagging by cluster enabled");
			$("#p2button").attr("disabled", "disabled");
		} else if (phase == PHASE_TAG_BY_NOTE) {
			$("#p3button").val("Tagging by note enabled");
			$("#p3button").attr("disabled", "disabled");
		} else if (phase == PHASE_COMPARE_BY_SIMILARITY) {
			$("#p4button").val("Comparing by similarity enabled");
			$("#p4button").attr("disabled", "disabled");
		} else if (phase == PHASE_CASCADE) {
			$("#p5button").val("Cascade enabled");
			$("#p5button").attr("disabled", "disabled");
		}
	}
}