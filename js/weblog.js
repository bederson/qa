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

var offsets = [ null ];
var offsetIndex = 0;

$(document).ready(function() {	
	initEventHandlers();
	
	if ($("#msg").html()) {
		return;
	}
	
	loadWebLog();
	$("#page_content").show();
});

function loadWebLog() {
	$("#web_log").html("Loading ...");
	var data = offsets[offsetIndex] != null ? { "offset" : offsets[offsetIndex] } : {};
	$.post("/load_web_log", data, function(result) {
		if (result.status == 1) {
			var html = "<h2 class='spacebelow'>Cascade Requests</h2>\n";
			html += "<a class='small noline prev_link' href='/web_log'> &laquo; PREV</a> <a class='small noline next_link' href='/web_log'>NEXT &raquo;</a>\n";
			if (result.log.length == 0) {
				html += "<div style='padding:8px'>";
				html += "No requests found";
				html += "</div>";
			}
			else {
				for (i in result.log) {
					var request = result.log[i];
					var highlight = request.was_loading_request || request.pending_time > 0 || request.latency > 3;
					html += highlight ? "<div class='discuss_highlight' style='padding:8px; margin-bottom:8px'>" : "<div style='padding:8px'>";					
					html += request.timestamp + "<br/>";
					//html += request.ip + "<br/>";
					//html += request.method + "<br/>";
					html += request.resource + "<br/>";
					html += "<span class='note'>";
					//html += "start_time = " + request.start_time +", end_time = " + request.end_time + ", latency = " + request.latency;
					html += "latency = " + request.latency;
					html += request.pending_time > 0 ? ", pending = " + request.pending_time : "";
					//html += ", start_time = " + request.start_time +", end_time = " + request.end_time
					html += "<br/>";
					html += request.was_loading_request ? "LOADING REQUEST</br>" : "";
					html += "</span>";
					html += "</div>";
				}
				html += "<a class='small noline prev_link' href='/web_log'> &laquo; PREV</a> <a class='small noline next_link' href='/web_log'>NEXT &raquo;</a><br/>\n";
			}
			$("#web_log").html(html);

			if (result.offset && offsetIndex == offsets.length-1) {
				offsets.push(result.offset);
			}
			
			showHide($(".prev_link"), offsetIndex >= 1);
			$(".prev_link").click(function() {
				offsetIndex--;
				loadWebLog();
				return false;
			});

			showHide($(".next_link"), offsetIndex < offsets.length-1);			
			$(".next_link").click(function() {
				offsetIndex++;
				loadWebLog();
				return false;
			});
		}
	}, "json");
}

function initEventHandlers() {
	// called when page is first loaded
	// do not add any event handlers for objects that are created/destroyed dynamically
	
	$("#admin_button").click(function() {
		redirectToAdminPage();
	});
	
	$("#days").change(function() {
		day = $("#days").val();
		loadWebLog();
	});
}