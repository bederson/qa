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

$(function() {	
	if (!logged_in) {
		enableDisable($("#admin_button"), false);
		$("#admin_help").show();
	}
	else {
		initChannel();
	}
	
	$("#code_box").on("keydown", function(evt) {
		if (evt.keyCode == 13) {		// Return key
			loginToQuestion();
		}
	});
	
	$("#go_button").click(function() {
		loginToQuestion();
	});

	$("#admin_button").click(function() {
		redirectToAdminPage();
	});
	
	$("#code_box").focus();
});

function loginToQuestion() {
	$("#msg").html("");
	var question_id = $("#code_box").val();	
	if (question_id.length==0) {
		showInfoMessage("Please enter code");
		$("#code_box").focus();
		return;
	}
	
	var data = {
		"request": "question",
		"question_id": question_id
	};
	$.post("/question_login", data, function(results) {
		if (results.status == 0) {
			showInfoMessage(results.msg);
			$("code_box").focus();
			return;
		}
		
		window.location.href = results.url;
		
	}, "json");	
}

function showInfoMessage(msg) {
	$("#info").html(msg);
	$("#info").show();
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	// ignore
}

function handleEnable(data) {
	// ignore
}

function handleDisable(data) {
	// ignore
}

function handlePhase(data) {
	// ignore
}

function handleNickname(data) {
	// ignore
}

function handleStep(data) {
	// ignore
}

function handleResults(data) {
	// ignore
}

function handleLogout(data) {
	redirectToLogout();
}