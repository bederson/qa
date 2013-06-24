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
	$("#nickname").focus();
	initEventHandlers();
});

function initEventHandlers() {
	$("#nickname").on("keydown", function(e) {
		if (e.keyCode == 13) {
			submit();
		}
	});
	
	$("#login_button").click(function() {
		submit();
	});
}

function submit() {
	var question_id = getURLParameter("question_id");
	var nickname = $("#nickname").val();

	if (isUndefined(question_id)) {
		$("#msg").html("Question code not found");
	}
		
	else if (nickname.length == 0) {
		$("#msg").html("Please enter nickname");
	}
	
	else {
		var data = {
			"question_id" : question_id,
			"nickname" : nickname
		};
		$.post("/login", data, function(results) {
			if (results.status == 0) {
				$("#msg").html(results.msg);
				return;
			}
			
			window.location.href = results.url;
		}, "json");
	}
}