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

	onResize();
	$(window).resize(function() {
		onResize();
	});

	if (!logged_in) {
		disableInput("Please log in to submit a response");
		return;
	}

	$("#answer").focus();
	var question_id = getURLParameter("question_id");

	$("#title").html(title);
	$("#question").html(question);

	if (phase == 1) {
		enableInput();
	} else {
		disableInput("Not currently accepting new submissions");
	}
	if ((phase == PHASE_TAG_BY_CLUSTER) || (phase == PHASE_TAG_BY_NOTE)) {
		$("#start_tagging").css("display", "inline");
	}
	
	updateNicknameArea();
});

// Shouldn't have to enableInput, but Firefox strangely caches state of elements.
// Without explicitly enabling input, Firefox will remain disabled after phase change - even on reload
function enableInput() {
	$("#answer").removeAttr("disabled");
	$("#submit").removeAttr("disabled");
	$("#answer").val("");
	$("#answer").focus();
}

function disableInput(msg) {
	$("#answer").attr("disabled", "disabled");
	$("#submit").attr("disabled", "disabled");
	$("#answer").val(msg);
}

function initEventHandlers() {
	$("#submit").click(function() {
		$("#submit").attr("disabled", "disabled");
		var question_id = getURLParameter("question_id");
		var idea = $("#answer").val();
		var data = {
			"client_id": client_id,
			"idea": idea,
			"question_id": question_id
		};
		$.post("/newidea", data, function() {
			$("#submit").removeAttr("disabled");
			$("#thankyou").css("display", "inline");
			$("#results_link").attr("href", "/results?question_id=" + question_id);
			$("#answer").val("");
			$("#answer").focus();
			updateRemainingChars();
		});
	});

	$("#answer").keyup(function() {
		updateRemainingChars();
	});

	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href="/admin?question_id=" + question_id;
	});
	
	$("#tag_button").click(function() {
		var question_id = getURLParameter("question_id");
		window.location.href="/tag?question_id=" + question_id;
	});
}

function updateRemainingChars() {
	var maxChars = 250;
	var text = $("#answer").val();
	if (text.length > maxChars) {
		text = text.slice(0, maxChars);
		$(this).val(text);
	}
	var msg = (maxChars - text.length) + " chars left";
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

	$(".qcontainer").width(width);
	$("#answer").width(width - 6);
}

function updateNicknameArea() {
	var html = '<div class="header spacebelow">Nickname</div>';
	if (user_nickname != "") {
		html += user_nickname + " " + '<input id="delete_nickname" type="submit" value="Remove">';
		html += '<div class="help">';
	    html += 'Nickname displayed with all your entries for this question';
	    html += '</div>';
	    $("#nickname_area").html(html);
	    $("#user_display_name").html(user_nickname);
	    
		$("#delete_nickname").unbind("click");
		$("#delete_nickname").click(function() {
			var question_id = getURLParameter("question_id");
			var data = {
				"client_id": client_id,
				"question_id": question_id
			};
			$.post("/deletenickname", data, function(event) {
				if (event.msg != "") {
					$("#nickname_msg").html(event.msg);
				}
				else {
					user_nickname = "";
					updateNicknameArea();
				}
			});
		});
	}
	else {
	    html += '<div class="help">';
	    html += 'Enter the nickname to display with all your entries for this question. By default, your user id will be used.';
	    html += '</div>';
	    html += '<input id="nickname" value=""><br>';
	    html += '<input id="submit_nickname" type="submit" value="Submit">';
	    html += '<div id="nickname_msg" class="warning"></div>';
	    $("#nickname_area").html(html);
	    $("#user_display_name").html(user_login);
	    
	   	$("#submit_nickname").unbind("click");
		$("#submit_nickname").click(function() {
			$("#submit_nickname").attr("disabled", "disabled");
			var question_id = getURLParameter("question_id");
			var nickname = $("#nickname").val();
			var data = {
				"client_id": client_id,
				"question_id": question_id,
				"nickname": nickname
			};
			$.post("/newnickname", data, function(event) {
				$("#submit_nickname").removeAttr("disabled");
				if (event.msg != "") {
					$("#nickname_msg").html(event.msg);
				}
				else {
					user_nickname = nickname;
					updateNicknameArea();
				}
			});
		});
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
	window.location.reload();
}

function handleTag(data) {
	// Ignore it
}