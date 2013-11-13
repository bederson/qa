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

var SHOW_IDEA_LIST = false;
var ideas = [];

$(document).ready(function() {
	onResize();
	initEventHandlers();
		
	if ($("#msg").html()) {
		disableUI();
		return;
	}
	
	initChannel(onChannelOpen);
	
	// will only be shown for instructor
	// for questions that are not finished yet
	if (SHOW_START_URL_BY_DEFAULT) {
		$("#start_url_area").show();
	}
	else {
		$("#show_start_url").show();
	}	
});

function onChannelOpen() {
	if (cascade_complete) {
		$("#msg").html("This question is complete. <a class='warning' href='"+getResultsPageUrl(question_id)+"'>View results</a>");
		disableUI();
	}	
	else {
		updateUI();
	}
}

function updateUI(enable) {
	var enable = isDefined(enable) ? enable : (isDefined(question_active) && question_active);
	enableDisable($("#answer"), enable);
	enableDisable($("#submit"), enable);
	enableDisable($("#done"), enable);
	if (!$("#msg").html()) {
		$("#msg").html(!enable ? "Question has been disabled" : "");
	}
	$("#answer").val(!enable ? "Not currently accepting new submissions" : "");	
	
	if (enable) {		
		$("#answer").focus();
		if (change_nickname_allowed) {
			displayNicknameArea();
		}
		if (SHOW_IDEA_LIST) {
			displayIdeas();
		}
	}
	else {
		$("#nickname_area").hide();
		$("#ideas").hide();
	}	
}

function disableUI() {
	updateUI(false);
}

function submitIdea() {
	var idea = $("#answer").val();
	if (idea.length == "") {
		return;		
	}

	enableDisable($("#submit"), false);
	$("#loading_icon").show();
	
	var data = {
		"client_id": client_id,
		"idea": idea,
		"question_id": question_id
	};
	$.post("/new_idea", data, function(result) {
		enableDisable($("#submit"), true);
		if (result.status == 0) {
			$("#msg").html(result.msg);
			return;
		}
		$("#answer").val("");
		$("#answer").focus();
		updateRemainingChars();
		$("#loading_icon").hide();
		$("#thankyou").show();
	}, "json");
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

function displayNicknameArea(editableNickname) {
	editableNickname = isDefined(editableNickname) ? editableNickname : false;
	var submitId = !editableNickname ? "change_nickname1" : "change_nickname2";
	var html = '<div class="header spacebelow">Nickname</div>';
	html += editableNickname ? '<input id="nickname" value="' + user_nickname + '"> ' : user_nickname + ' ';
	html += '<input id="' + submitId + '" type="submit" value="Change">';
	html += '<div class="help">';
	html += 'Your nickname will be displayed with your responses';
	html += '<div id="nickname_msg" class="warning"></div>';
	html += '</div>';
	$("#nickname_area").html(html);
	
	if (!editableNickname) {
		$("#"+submitId).click(function() {
			var submitId2 = displayNicknameArea(true);
			enableDisable($("#"+submitId2), false);
				
			$("#nickname").keyup(function() {
				enableDisable($("#"+submitId2), true);
			});
		});
	}
		
	else {	
		$("#"+submitId).click(function() {
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
				if (result.authentication_type != GOOGLE_AUTHENTICATION) {
					$("#user_login").html(user_nickname);
				}
				displayNicknameArea();
			}, "json");
		});  
	} 

	$("#nickname_area").show();
	return submitId;
}

function displayIdeas() {	
	var data = {
		"request": "ideas",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		ideas = results.ideas;
		var html = "<h2>Responses</h2>";
		html += "<ul id='idea_list'>";
		for (var i in ideas) {
			var idea = ideas[i];
			html += ideaAsHtml(idea);
		}
		html += "</ul>"
		$("#ideas").html(html);
		$("#ideas").show();
		$(document).tooltip({position:{my: "left+15 center", at:"right center"}});
	});
}

function ideaAsHtml(idea) {
	var html = "<li>";
	html += idea.idea + "<br/>";
	html += "<span class='author'";
	var realIdentity = isDefined(idea.author_identity) && idea.author_identity!=null ? idea.author_identity : "";
	var isIdentityHidden = realIdentity != "" && realIdentity != idea.author;
	if (isIdentityHidden) {
		html += " title='" + realIdentity + "' ";
	}
	html += ">&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author + (isIdentityHidden?"*":"") + "</span>";
	html += "</li>";
	return html;	
}

function displayNewIdea(idea) {
	ideas.push(idea);
	var html = ideaAsHtml(idea);
	$("#idea_list").prepend(html);
}

function initEventHandlers() {
	// called when page is first loaded
	// do not add any event handlers for objects that are created/destroyed dynamically
	
	$(window).resize(function() {
		onResize();
	});
	
	$("#submit").click(function() {
		submitIdea();
	});
	
	$("#answer").keyup(function() {
		updateRemainingChars();
	});

	$("#done").click(function() {
		redirectToCascadePage(question_id);
	});
	
	$("#admin_button").click(function() {	
		redirectToAdminPage(question_id);
	});
	
	$("#hide_start_url").click(function() {
		$("#start_url_area").hide();
		$("#show_start_url").show();
		return false;
	});

	$("#show_start_url").click(function() {
		$("#show_start_url").hide();
		$("#start_url_area").show();
		return false;
	});
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

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	if (SHOW_IDEA_LIST) {
		displayNewIdea(data.idea);
	}
}

function handleEnable(data) {
	question_active = true;
	updateUI();
}

function handleDisable(data) {
	question_active = false;
	updateUI();
}

function handleLogout(data) {
	redirectToLogout(question_id);
}