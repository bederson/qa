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
	displayModes();
});

function initEventHandlers() {
	$("#p0button").click(function() {
		set_phase(0);
	});
	$("#p1button").click(function() {
		set_phase(1);
	});
	$("#p2button").click(function() {
		set_phase(2);
	});
	$("#results_button").click(function() {
		window.location.href = "/results";
	});
	$("#tags_button").click(function() {
		window.location.href = "/tags";
	});
}

function set_phase(phase) {
	var data = {
		"client_id": client_id,
		"phase": phase
	};
	$.post("/set_phase", data, function() {
		window.location.reload();
	});
}

function displayModes() {
	$.getJSON("/query", {request: "phase"}, function(data) {
		phase = parseInt(data.phase);
		if (phase == 0) {
			$("#p0button").attr("disabled", "disabled");
		} else if (phase == 1) {
			$("#p1button").attr("disabled", "disabled");
		} else if (phase == 2) {
			$("#p2button").attr("disabled", "disabled");
		}
	});
}