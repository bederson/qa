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

// BEHAVIOR: A user compares a selected note with a set of other notes,
// and must select the most similar note.  The number of tasks
// presented to the user is defined by num_notes_to_compare. 
// A page refresh or another visit allows the user to get another 
// set of tasks (if available and while the instructor has this phase enabled).
//
// LIMITATION: The server attempts to select a random note, not previously assigned 
// to the user. If a note is not found within x tries, the user will be
// told that no assignments are currently available.

$(document).ready(function() {
	initChannel();
	initEventHandlers();

	if (!logged_in) {
		$("#warning").html("Please log in to compare notes");
		return;
	}
	
	question_id = getURLParameter("question_id");
	if (!question_id) {
		$("#warning").html("Question code required");
		return;
	}
		
	if (phase == -1) {
		$("#warning").html("Invalid question code");
		return;
	}
	
	if (phase != PHASE_COMPARE_BY_SIMILARITY) {
		$("#warning").html("Not currently comparing notes by similarity");
		return;
	}
	
	current_note = 1;
	updateUI();
});

function initEventHandlers() {
	onResize();
	$(window).resize(function() {
		onResize();
	});

	$("#admin_button").click(function() {
		window.location.href="/admin?question_id=" + question_id;
	});
		
	$("#submit").click(function() {
		saveComparison();
	});

	$("#skip_button").click(function() {
		if (current_note == num_notes_to_compare) {
			current_note = 0;
			updateUI();
		}
		else {
			updateAssignment();
		}
	});
}

function updateUI() {
	var isFinished = current_note == 0;	
	if (isFinished) {
		var url = "/results?question_id=" + question_id;
		var html = "<h1>Comparison complete</h1>";
		html += "Thank you!";
		html += "<br/><br/>";
		html += "You can see all the <a href='" + url + "'>similar notes so far</a>.";
		$(".qcontainer").html(html);
	}
	
	// BEHAVIOR: This may also happen if server does not retrieve random idea within
	// max number of tries
	else if (!current_assignment) {
		var url = "/results?question_id=" + question_id;
		var html = "<h1>Time to Compare Notes</h1>";
		html += "No assignments are currently available.";
		html += "<br/><br/>";
		html += "You can see all the <a href='" + url + "'>similar notes so far</a>.";
		$(".qcontainer").html(html);
	}
	
	else {
		$("#selected_note").html(current_assignment.idea.text);		
		var html = "";
		for (var i=0; i<current_assignment.compare_to.length; i++) {
			html += "<div class=\"smallspaceafter\"><input type=\"radio\" name=\"compare_to\" value=\""+i+"\">" + current_assignment.compare_to[i].text + "</div>";
		}
		$("#compare_to_notes").html(html);
	
		// next note area
		var isLastNote = current_note == num_notes_to_compare;
		var html = "This is note #" + current_note + " out of " + num_notes_to_compare + ".<br/>";
		$("#next_note").html(html);
		
		$("#taskarea").show();
	}
}

function saveComparison() {
	var similarTo = $("input:radio[name=compare_to]:checked").val();
	if (!similarTo) {
		$("#warning").html("Please select a similar note.");
		return;
	}
	
	updateAssignment(similarTo);
}

function updateAssignment(similarToIndex) {
	enableDisable($("#submit"), false);
	enableDisable($("#skip_button"), false);
	
	var data = {
		"question_id" : question_id,
		"request_new" : current_note < num_notes_to_compare ? "1" : "0"
	}
	
	if (isDefined(similarToIndex)) {
		data["idea"] = current_assignment.idea.id;
		data["similar_idea"] = current_assignment.compare_to[similarToIndex].id;		
	}
	
	$.post("/similar_idea", data, function(results) {
		if (results.status == 0) {
			$("#warning").html(results.msg);
		}
		else {
			$("#warning").html("");
			current_note = current_note < num_notes_to_compare ? current_note + 1 : 0;
			current_assignment = results.assignment;
			updateUI();
		}
		enableDisable($("#submit"), true);
		enableDisable($("#skip_button"), true);
	}, "json");
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
	$(".qcontainer").width(width);
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
	window.location.reload();
}

function handleTag(data) {
	// Ignore it
}

function handleNickname(data) {
	// Ignore it
}