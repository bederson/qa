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
	displayTags()
});

function initEventHandlers() {
}

function displayTags() {
	$.getJSON("/query", {request: "tags"}, function(data) {
		var hists = processTags(data);
		displayTagsImpl(hists);
	});
}

function processTags(data) {
	var tags = data.tags;
	var hists = [];
	for (var i=1; i<=data.num_clusters; i++) {
		hists[i] = {};
	}
	for (var i in tags) {
		var tag = tags[i].tag;
		var cluster = tags[i].cluster;
		if (tag in hists[cluster]) {
			hists[cluster][tag] += 1;
		} else {
			hists[cluster][tag] = 1
		}
	}
	
	return hists;
}

function displayTagsImpl(hists) {
	var html = "";
	for (var i in hists) {
		html += "<h2>Cluster #" + i + "</h2><ul>";
		var hist = hists[i];
		for (item in hist) {
			html += "<li>" + item + " (" + hist[item] + ")";
		}
		html += "</ul>";
	}
	$("#tags").html(html);
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