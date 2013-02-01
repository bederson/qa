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
var show_tags_in_charts = [];

// Reason for this combination of google chart and jquery:
// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
google.setOnLoadCallback(function() {
	$(function() {
		initChannel();
		initEventHandlers();
		displayTags()
	});
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
		drawCharts();
	});
}

function processTags(data) {
	var tags = data.tags;
	for (var i=1; i<=data.num_clusters; i++) {
		tag_hists[i] = {};
		show_tags_in_charts[i] = false;
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
	$("#tags").html("");
	for (var i in tag_hists) {
		var chartid = "chart" + i;
		var html = "<h2>Cluster #" + i + "</h2><br>";
		html += "<div id='" + chartid + "'></div>";
		var showTagID = "showtag" + i;
		html += "<input id='" + showTagID + "' type='button' value='Show tags'>";
		html += "<br><br>";
		$("#tags").append(html);
		$("#" + showTagID).data("cluster", i);
		$("#" + showTagID).click(function(data) {
			var clusterNum = $(this).data("cluster");
			show_tags_in_charts[clusterNum] = true;
			drawCharts();
		});
	}
}

// Callback that creates and populates a data table,
// instantiates the chart, passes in the data and
// draws it.
function drawCharts() {
	for (var i in tag_hists) {
		var chartid = "chart" + i;
		var hist = tag_hists[i];

		// Create the data table.
		var data = new google.visualization.DataTable();
		data.addColumn('string', 'Tag');
		data.addColumn('number', 'Tags');
		var rows = [];
		var max = 0;
		for (item in hist) {
			if (hist[item] > max) max = hist[item];
			var tag_to_display = "";
			if (show_tags_in_charts[i]) {
				tag_to_display = item;
			}
			var row = [tag_to_display, hist[item]];
			rows.push(row);
		}
		data.addRows(rows);

		// Set chart options
		var options = {
			'title':'Tag distribution',
			'width':400,
			'height':300,
			'axisTitlesPosition': 'in',
			'backgroundColor': '#d8e9a6',
			'fontSize': 20,
			'hAxis': {
				'minValue': 0,
				'format': "##",
				'gridlines': {'count': (max + 1)},
			},
			'legend': {
				'position': 'none'
			}
		};

		// Instantiate and draw our chart, passing in some options.
		var chart = new google.visualization.BarChart(document.getElementById(chartid));
		chart.draw(data, options);
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
	// Ignore it
}

function handleTag(data) {
	addTag(data.tag, data.cluster_index);
	displayTagsImpl();
	drawCharts();
}