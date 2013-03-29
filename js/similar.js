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

var mytags = [];

$(function() {
	initChannel();
	initEventHandlers();

	var question_id = getURLParameter("question_id");
	
	if (!logged_in) {
		$("#taskmsg").html("Please log in to compare notes");
		return;
	}

	if (isUndefined(question_id)) {
		$("#taskmsg").html("Invalid question code");
		return;
	}
	
	if (phase != PHASE_COMPARE_BY_SIMILARITY) {
		$("#taskmsg").html("Not currently accepting new comparisons");
		return;
	}
	
	if ((idea_id == "-1") || (num_notes_compared > num_notes_to_compare)) {
		comparisonFinished();
	} else {
		updateDisplayForNotesToCompare();
	}
		
	$("#taskarea").show()	
});

function initEventHandlers() {
	onResize();
	$(window).resize(function() {
		onResize();
	});
	
	$("#submit").click(function() {
		submitComparison();
	});

	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href="/admin?question_id=" + question_id;
	});
}

function submitComparison() {
	var question_id = getURLParameter("question_id");
	if (phase == PHASE_COMPARE_BY_SIMILARITY) {
		// STILL TODO
	}

	//$("#thankyou").css("display", "inline");
	//setTimeout(function() {
	//	$("#thankyou").fadeOut("slow");
	//}, 2000);
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

/////////////////////////////////////////////
// Compare notes
/////////////////////////////////////////////
function updateDisplayForNotesToCompare() {
	var current_note_num = num_notes_compared+1;
	var html = "<br><br>";
	html += "This is note #" + current_note_num + " out of " + num_notes_to_compare + ".<br>";
	var moreToDo = current_note_num < num_notes_to_compare;
	if (moreToDo) {
		html += "To skip this OR go to the next note, ";
		var msg = "Next note";
	} else {
		html += "When you are done, "
		var msg = "finished!";
	}
	html += "click on ";
	html += "<input id='next_button' value='" + msg + "' type='button'></input>";
	html += "<br><br>";
	$("#next_note").html(html);
	
	$("#next_button").click(function() {
		var question_id = getURLParameter("question_id");
		var data = {
			"question_id": question_id,
			"complete": moreToDo ? "0" : "1"
		};
		$.getJSON("/getsimilarassignment", data, function(results) {
			window.location.reload();
		});
	});
	
	displaySimilarNotes();
}

function displaySimilarNotes() {
	var question_id = getURLParameter("question_id");
	// STILL TODO
}

function comparisonFinished(idea_id) {
	var question_id = getURLParameter("question_id");
	var url = "/results?question_id=" + question_id;
	
	var html = "<h1>Comparison complete</h1>";
	html += "Thank you!";
	html += "<br/><br/>";
	html += "You can see all the <a href='" + url + "'>similar notes so far</a>.";
	$(".qcontainer").html(html);
}

/////////////////////////
// Channel support
/////////////////////////
function handleNew(data) {
	// Ignore it
}

function handleRefresh(data) {
	window.location.reload();
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