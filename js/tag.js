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

var mytags = [];

$(function() {
	initChannel();
	initEventHandlers();
	
	if (!question_id) {
		$("#warning").html("Question code required");
		return;
	}
	
	if (phase != PHASE_TAG_BY_CLUSTER && phase != PHASE_TAG_BY_NOTE) {
		redirectToPhase(phase, question_id);
		return;
	}

	if (!logged_in) {
		disableInput("Please log in");
		return;
	}
	
	$("#tagbox").focus();
	if (phase == PHASE_TAG_BY_CLUSTER) {
		enableInput();
		updateDisplayForTagsPerCluster();
	} else if (phase == PHASE_TAG_BY_NOTE) {
		if ((idea_id == "-1") || (num_notes_tagged > num_notes_to_tag)) {
			tagsPerIdeaFinished();
		} else {
			enableInput();
			updateDisplayForTagsPerIdea();
		}
	}
});

function initEventHandlers() {
	onResize();
	$(window).resize(function() {
		onResize();
	});
	
	$("#submit").click(function() {
		submitTag();
	});
	$("#tagbox").on("keydown", function(evt) {
		if (evt.keyCode == 13) {		// Return
			submitTag();
		}
	});
	$("#tagbox").keyup(function() {
		updateRemainingChars();
	});

	$("#admin_button").click(function() {
		window.location.href="/admin?question_id=" + question_id;
	});
}

// Shouldn't have to enableInput, but Firefox strangely caches state of elements.
// Without explicitly enabling input, Firefox will remain disabled after phase change - even on reload
function enableInput() {
	$("#tagbox").removeAttr("disabled");
	$("#submit").removeAttr("disabled");
	$("#tagbox").val("");
	$("#tagbox").focus();
}

function disableInput(msg) {
	$("#tagbox").attr("disabled", "disabled");
	$("#submit").attr("disabled", "disabled");
	$("#tagbox").val(msg);
}

function submitTag() {
	var tag = $("#tagbox").val().trim();
	if (tag.length == 0) {
		// Don't submit blank tags
		return;
	}
	if (mytags.indexOf(tag) != -1) {
		// Whoops - tag already in list
		$("#thankyou").css("display", "none");
		$("#nodups").css("display", "inline");
		$("#tagbox").select();
		setTimeout(function() {
			$("#nodups").fadeOut("slow");
		}, 2000);
		return;
	}
	mytags.push(tag);

	var data = {
		"client_id": client_id,
		"tag": tag,
		"cluster_id": cluster_id,
		"idea_id": idea_id,
		"question_id": question_id
	};
	if (phase == PHASE_TAG_BY_CLUSTER) {
		$.post("/newclustertag", data);
	} else {
		$.post("/newideatag", data);
	}

	$("#thankyou").css("display", "inline");
	$("#nodups").css("display", "none");
	$("#tagbox").val("");
	$("#tagbox").focus();
	setTimeout(function() {
		$("#thankyou").fadeOut("slow");
	}, 2000);
	updateRemainingChars();

	displayTags(mytags);
}

function onResize() {
	var padding = 40;

	if (jQuery.browser.mobile) {
		var width = $(window).width() - padding;
	} else {
		var targetWidth = 500;
		var width = targetWidth;
		if ($(window).width() < (targetWidth + padding)) {
			width = $(window).width() - padding;
		}
	}

	$(".qcontainer").width(width);
	$("#tagbox").width(width - 6);
}

function updateRemainingChars() {
	var maxChars = 50;
	var box = $("#tagbox");
	var text = box.val();
	if (text.length > maxChars) {
		text = text.slice(0, maxChars);
		box.val(text);
	}
	var msg = (maxChars - text.length) + " chars left";
	$("#charlimit").html(msg);
}

function displayTags(tags) {
	var html = "";
	if (tags.length > 0) {
		$("#notags").css("display", "none");
		html += "My tags:<br><ul>";
		for (var i in tags) {
			var tag = tags[i];
			html += "<li>" + tag
		}
		html += "<div id='newtags'></div>";
		html += "</ul>";
		$("#mytags").html(html);
	}
}

/////////////////////////////////////////////
// Tagging per cluster
/////////////////////////////////////////////
function updateDisplayForTagsPerCluster() {
	$("#question").html("Please enter 1 or 2 words that best characterize these notes.")
	displayTagsPerCluster();
	displayIdeasPerCluster();
}

function displayTagsPerCluster() {
	var data = {
		"request": "myclustertags",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		for (var i in results.tags) {
			mytags.push(results.tags[i]);
		}
		displayTags(results.tags);
	});
}

function displayIdeasPerCluster() {
	var data = {
		"request": "ideasbycluster", 
		"cluster_id": cluster_id,
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		var html = "Notes:<br><ul>";
		for (i in results) {
			var idea = results[i].idea;
			html += "<li>" + idea
		}
		html += "</ul>";
		$("#clusteredIdeas").html(html);
	});
}

/////////////////////////////////////////////
// Tagging per idea
/////////////////////////////////////////////
function updateDisplayForTagsPerIdea() {
	$("#question").html("Enter 1 or 2 words that best characterize the note.")
	
	var html = "<br><br>";
	html += "This is note #" + num_notes_tagged + " out of " + num_notes_to_tag + ".<br>";
	if (num_notes_tagged < num_notes_to_tag) {
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
		var data = {
			"question_id": question_id
		};
		$.getJSON("/getideaassignment", data, function(results) {
			window.location.reload();
		});
	});
	
	displayTagsPerIdea();
	displayIdeasPerIdea();
}

function displayTagsPerIdea() {
	var data = {
		"request": "myideatags",
		"question_id": question_id,
		"idea_id": idea_id
	};
	$.getJSON("/query", data, function(results) {
		for (var i in results.tags) {
			mytags.push(results.tags[i]);
		}
		displayTags(results.tags);
	});
}

function displayIdeasPerIdea() {
	if (idea_id > 0) {
		var data = {
			"request": "idea", 
			"idea_id": idea_id,
		};
		$.getJSON("/query", data, function(results) {
			data = {
				"request": "question",
				"question_id": question_id
			}
			$.getJSON("/query", data, function(results2) {
				var html = "";
				html += "<b>The question:</b> " + results2.question + "<br><br>";
				html += "<b>The note:</b> &quot;";
				html += results.idea;
				html += "&quot;";
				$("#clusteredIdeas").html(html);
			});
		});
	}
}

function tagsPerIdeaFinished() {
	var url = "/results?question_id=" + question_id;

	var html = "<h1>Tagging complete</h1>";
	html += "Thank you!";
	html += "<br><br>";
	html += "You can see all the <a href='" + url + "'>tags so far</a>.";
	
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