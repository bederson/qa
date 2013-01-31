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

var tag_hists = [];

$(function() {
	initChannel();
	initEventHandlers();
	displayTags()
});

function initEventHandlers() {
	$("#admin_button").click(function() {
		window.location.href="/admin";
	});
}

function displayTags() {
	$.getJSON("/query", {request: "tags"}, function(data) {
		processTags(data);
		displayTagsImpl();
	});
}

function processTags(data) {
	var tags = data.tags;
	for (var i=1; i<=data.num_clusters; i++) {
		tag_hists[i] = {};
	}
	for (var i in tags) {
		var tag = tags[i].tag;
		var cluster = tags[i].cluster;
		addTag(tag, cluster);
	}
}

function addTag(tag, cluster) {
	if (tag in tag_hists[cluster]) {
		tag_hists[cluster][tag] += 1;
	} else {
		tag_hists[cluster][tag] = 1
	}
}

function displayTagsImpl() {
	var html = "";
	for (var i in tag_hists) {
		html += "<h2>Cluster #" + i + "</h2><ul>";
		var hist = tag_hists[i];
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
	// Ignore it
}

function handleTag(data) {
	addTag(data.tag, data.cluster_index);
	displayTagsImpl();
}