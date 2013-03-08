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
				var question_id = getURLParameter("question_id");
				var nickname = $("#nickname").val();
				var data = {
					"client_id": client_id,
					"question_id": question_id,
					"nickname": nickname
				};
				$.post("/newnickname", data, function(event) {
					if (event.msg != "") {
						$("#nickname_msg").html(event.msg);
					}
					else {
						user_nickname = event.nickname;
						updateNicknameArea();
					}
				});
			});
		});

		$("#nickname_area").show();
	    //$("#user_display_name").html(user_login);
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

function handleNickname(data) {
	// Ignore it
}