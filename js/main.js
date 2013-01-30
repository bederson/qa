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
	initEventHandlers();
	initChannel();

	$("#submit").click(function() {
		var idea = $("#answer").val();
		var data = {
			"client_id": client_id,
			"idea": idea
		};
		$.post("/new", data, function() {
			$("#thankyou").css("display", "inline");
			$("#answer").val("");
			$("#answer").focus();
			updateRemainingChars();
		});
	});

	if (!logged_in) {
		$("#answer").attr("disabled", "disabled");
		$("#submit").attr("disabled", "disabled");
		$("#answer").focus();
	}

	onResize();
	$(window).resize(function() {
		onResize();
	});
});

function initEventHandlers() {
	$("#answer").keyup(function() {
		updateRemainingChars();
	});
}

function updateRemainingChars() {
	var maxChars = 500;
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

	$("#qcontainer").width(width);
	$("#answer").width(width - 6);
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