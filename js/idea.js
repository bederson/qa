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

var ideas = [];
var done = false;
SHOW_IDEAS_WHEN_DONE = true;

$(function() {
	$("#title").html(title);
	$("#question").html(question);
	
	if ($("#msg").html()) {
		disableInput();
		onResize();
		return;
	}
	
	if (phase != PHASE_NOTES) {
		redirectToPhase(question_id, phase);
		return;
	}

	initChannel();
	initEventHandlers();	
	
	$("#answer").focus();		
	if (change_nickname_allowed) {
		updateNicknameArea();
	}
});

// Shouldn't have to enableInput, but Firefox strangely caches state of elements.
// Without explicitly enabling input, Firefox will remain disabled after phase change - even on reload
function enableInput() {
	$("#answer").removeAttr("disabled");
	$("#submit").removeAttr("disabled");
	$("#answer").val("");
	$("#answer").focus();
	$("#nickname_area").show();
}

function disableInput(msg) {
	enableDisable($("#answer"), false);
	enableDisable($("#submit"), false);
	$("#answer").val("Not currently accepting new submissions");
	$("#nickname_area").hide();
}

function initEventHandlers() {
	onResize();
	$(window).resize(function() {
		onResize();
	});
	
	$("#submit").click(function() {
		enableDisable($("#submit"), false);
		var idea = $("#answer").val();		
		if (idea.length == "") {
			enableDisable($("#submit"), true);
			return;
		}
		
		var data = {
			"client_id": client_id,
			"idea": idea,
			"question_id": question_id
		};
		$.post("/new_idea", data, function(result) {
			if (result.status == 0) {
				$("#msg").html(result.msg);
				return;
			}
			enableDisable($("#submit"), true);
			$("#thankyou").show();
			$("#results_link").attr("href", "/results?question_id=" + question_id);
			$("#answer").val("");
			$("#answer").focus();
			updateRemainingChars();
		}, "json");
	});
	
	$("#answer").keyup(function() {
		updateRemainingChars();
	});

	$("#done_button").click(function() {
		var data = {
			"client_id": client_id,
			"question_id": question_id
		};
		$.post("/ideas_done", data, function(result) {
			if (result.status == 0) {
				$("#msg").html(result.msg);
				return;
			}
			done = true;
			var html = '<h1 id="title" class="largespaceafter">Add Answers</h1>';
			html += "Please wait for others to finish.<br/></br>";
			$("#answer_box").html(html);
			$("#nickname_area").hide();
			if (SHOW_IDEAS_WHEN_DONE) {
				$("#ideas").show();
				loadIdeas();
			}
		}, "json");
	});
	
	$("#admin_button").click(function() {	
		redirectToAdminPage(question_id);
	});
}

function updateRemainingChars() {
	var text = $("#answer").val();
	if (text.length > MAX_CHARS) {
		text = text.slice(0, MAX_CHARS);
		$(this).val(text);
	}
	var msg = (MAX_CHARS - text.length) + " chars left";
	$("#charlimit").html(msg);
}

function onResize() {
	var padding = 40;

	if (jQuery.browser.mobile) {
		var width = $(window).width() - padding;
	} else {
		var targetWidth = 600;
		var width = targetWidth;
		if ($(window).width() < (targetWidth + padding)) {
			width = $(window).width() - padding;
		}
	}

	$("#box_area").width(width);
}

function updateNicknameArea() {
	if (phase == 1) {
		var html = '<div class="header spacebelow">Nickname</div>';
		html += user_nickname + " " + '<input id="change_nickname1" type="submit" value="Change">';
		html += '<div class="help">';
	    html += 'Nickname displayed with all your entries for this question';
	    html += '</div>';
		$("#nickname_area").html(html);
			
		$("#change_nickname1").click(function() {
			var html = '<div class="header spacebelow">Nickname</div>';
			html +=  '<input id="nickname" value="' + user_nickname + '"> <input id="change_nickname2" type="submit" value="Change">';
			html += '<div class="help">';
	    	html += 'Nickname displayed with all your entries for this question';
	    	html += '<div id="nickname_msg" class="warning"></div>';
	    	html += '</div>';
			$("#nickname_area").html(html);
			$("#change_nickname2").prop("disabled", true);
			
			$("#nickname").keyup(function() {
				$("#change_nickname2").prop("disabled", false);
			});
			
			$("#change_nickname2").click(function() {
				var nickname = $("#nickname").val();
				var data = {
					"client_id": client_id,
					"question_id": question_id,
					"nickname": nickname
				};
				$.post("/nickname", data, function(result) {
					if (result.status == 0) {
						$("#nickname_msg").html(result.msg);
						return;
					}
					user_nickname = result.user.nickname;
					updateNicknameArea();
				}, "json");
			});
		});

		$("#nickname_area").show();
	}
}

function loadIdeas() {	
	// TODO/FIX: request all ideas in single array (not separated by categories!)
	var data = {
		"request": "ideas",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		ideas = results.ideas;
		var html = "<ul id='idea_list'>";
		for (var i in ideas) {
			var idea = ideas[i];
			html += ideaAsHtml(idea);
		}
		html += "</ul>"
		$("#ideas").html(html);
	});
}

function addIdea(idea) {
	ideas.push(idea);
	var html = ideaAsHtml(idea);
	$("#idea_list").prepend(html);
}

function ideaAsHtml(idea) {
	var html = "<li>";
	html += idea.idea + "<br/>";
	html += "<span class='author'";
	var realIdentity = isDefined(idea.author_identity) ? idea.author_identity : "";
	var isIdentityHidden = realIdentity != "" && realIdentity != idea.author;
	if (isIdentityHidden) {
		html += " title='" + realIdentity + "' ";
	}
	html += ">&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author + (isIdentityHidden?"*":"") + "</span>";
	html += "</li>";
	return html;	
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	if (SHOW_IDEAS_WHEN_DONE && done) {
		addIdea(data.idea);
	}
}

function handleEnable(data) {
	$("#msg").html("");
	enableInput();
}

function handleDisable(data) {
	$("#msg").html("Question has been disabled");
	disableInput();
}

function handlePhase(data) {
	window.location.reload();
}

function handleLogout(data) {
	redirectToLogout(question_id);
}