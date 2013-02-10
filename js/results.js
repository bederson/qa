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

var OFFLINE = false;					// For offline debugging

var numIdeas = 0;
var MAX_CLOUD_HEIGHT = 800;
var maxChartRows = 10;
var tag_hists = [];
var show_tags_in_charts = [];
var phase = 0;

// Reason for this combination of google chart and jquery:
// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
if (OFFLINE) {
	$(function() {
		init();
	});	
} else {
	google.setOnLoadCallback(function() {
		$(function() {
			init();
		});
	});
}

function init() {
	initChannel();
	initEventHandlers();

	if (jQuery.browser.mobile) {
		$("#admin_buttons").css("display", "none");
	}

	var question_id = getURLParameter("question_id");
	$("#idea_link").attr("href", "/idea?question_id=" + question_id);

	var data = {
		"request": "phase",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		phase = results.phase;
		displayIdeas();
		if (results.phase == 2) {
			$("#start_tagging").css("display", "inline");
		}
	});	
}

function initEventHandlers() {
	$("#numclusters").change(function() {
		var label = "Create " + $(this).val() + " clusters";
		$("#clusterbutton").val(label);
	});
	
	$("#clusterbutton").click(function() {
		var question_id = getURLParameter("question_id");
		var num_clusters = $("#numclusters").val();
		var data = {
			"client_id": client_id,
			"num_clusters": num_clusters,
			"question_id": question_id
		};
		$.post("/cluster", data, function() {
			window.location.reload();
		});
	})

	$("#hide_ideas_button").data("toggle", "hide");
	$("#hide_ideas_button").click(function() {
		if ($(this).data("toggle") == "hide") {
			$(".ideas").css("display", "none");
			$(this).val("Show ideas");
			$(this).data("toggle", "show");
		} else {
			$(".ideas").css("display", "inline");
			$(this).val("Hide ideas");
			$(this).data("toggle", "hide");
		}
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

function displayIdeas(ideas) {
	var html = "Ideas loading ..."; 
	$("#clusteredIdeas").html(html);

	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas",
		"question_id": question_id
	};
	$.getJSON("/query", data, displayIdeasImpl);
}

function displayIdeasImpl(clusters) {
	var html = "";
	for (var i in clusters) {
		var cluster = clusters[i];
		var clusterName = cluster.name;
		var ideas = cluster.ideas;
		html += "<h2>" + clusterName + "</h2>";
		html += "<table style='width: 100%'><tr>";
		html += "<td style='width: 50%'>";
		html += "<div class='ideas'>";
		html += "<ul>"
		for (var j in ideas) {
			var idea = ideas[j].idea;
			html += "<li>" + idea;
			html += "<br>" + "<span class='author'>&nbsp;&nbsp;&nbsp;&nbsp;-- " + ideas[j].author + "</span>";
			numIdeas += 1;
		}
		html += "</ul>"
		html += "</div>";
		html += "</td>";
		if (!jQuery.browser.mobile) {
			var divid = "vis" + cluster.id;
			var controlid = "control" + cluster.id;
			html += "<td style='width: 50%' valign='top'><div id='" + divid + "'></div><div id='" + controlid + "'</div></td>";
		}
		html += "</tr></table>"
	}

	$("#clusteredIdeas").html(html);
	updateNumIdeas();
	
	if (!jQuery.browser.mobile) {
		if (phase < 2) {
			for (var i in clusters) {
				var cluster = clusters[i];
				var ideas = cluster.ideas;
				var cloudid = "vis" + cluster.id;
				var height = $("#" + cloudid).parent().height();
				if (height > MAX_CLOUD_HEIGHT) {
					height = MAX_CLOUD_HEIGHT;
				}
				$("#" + cloudid).height(height);
				displayCloud(cloudid, ideas);
			}
		} else {
			displayTagControls(clusters);
			displayTags();
		}
	}
}

function createIdea(idea) {
	var html = "<li>" + idea.text;
	html += "<br>" + "<span class='author'>&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author + "</span><br>";
	$("#unclusteredIdeas").prepend(html);
	numIdeas += 1;
	updateNumIdeas();
}

function updateNumIdeas() {
	var label = "note";
	var overviewStr = "<h1>";
	if (numIdeas == 0) {
		overviewStr += "No " + label + "s yet";
	} else if (numIdeas == 1) {
		overviewStr += "1 " + label;
	} else {
		overviewStr += numIdeas + " " + label + "s";
	}
	overviewStr += "</h1>";

	$("#ideaOverview").html(overviewStr);
}

//=================================================================================
// Cloud Display
//=================================================================================

function displayCloud(cloudid, cluster) {
	var weights = {};
	for (var j in cluster) {
		var words = cluster[j].words;
		for (var k in words) {
			var word = words[k].trim().toLowerCase();
			word = word.replace(/[\.,-\/#!$%\^&\*;:{}=\-_'`~()]/g, "");
			if (!isStopWord(word)) {
				if (word.length > 2) {
					if (word in weights) {
						weights[word] += 1;
					} else {
						weights[word] = 1;
					}
				}
			}
		}
	}

	var word_list = [];
	var i = 0;
	for (var word in weights) {
		var item = {text: word, weight: weights[word]};
		word_list[i] = item;
		i += 1;
	}

	$("#" + cloudid).jQCloud(word_list);
}

//=================================================================================
// Tag Chart Display
//=================================================================================
function displayTags() {
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "tags",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		processTags(results);
		drawCharts();
	});
}

function processTags(data) {
	var tags = data.tags;
	// Initialize data structures
	for (var i=0; i<data.num_clusters; i++) {
		tag_hists[i] = {};
	}
	// Process tags to fill data structures
	for (var i in tags) {
		var tag = tags[i].tag;
		var cluster = tags[i].cluster;
		createTag(tag, cluster);
	}
}

function createTag(tag, cluster) {
	if (tag in tag_hists[cluster]) {
		tag_hists[cluster][tag] += 1;
	} else {
		tag_hists[cluster][tag] = 1
	}
}

function displayTagControls(clusters) {
	for (var i in clusters) {
		show_tags_in_charts[i] = false;

		var controlid = "control" + i;
		var showTagID = "showtag" + i;
		var html = "<div style='margin-left:200px;'><input id='" + showTagID + "' type='button' value='Show tags'></div>";
		$("#" + controlid).append(html);
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
		var chartid = "vis" + i;
		var hist = tag_hists[i];

		// Create the data table.
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
		rows.sort(function(a, b) {
			return(b[1] - a[1]);
		});

		if (rows.length > 0) {
			if (OFFLINE) {
				var html = "<ul>";
				for (var j in rows) {
					var row = rows[j];
					html += "<li>" + row[0] + " (" + row[1] + ")";
				}
				html += "</ul>";
				$("#" + chartid).html(html);
			} else {
				var data = new google.visualization.DataTable();
				data.addColumn('string', 'Tag');
				data.addColumn('number', 'Tags');
				data.addRows(rows.splice(0, maxChartRows));
				// Set chart options
				var options = {
					'title': 'Tag distribution',
					'width': 600,
					'height': 300,
					'backgroundColor': '#d8e9a6',
					'fontSize': 20,
					'chartArea': {
						'left': 200,
						'right': 20,
					},
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
	}
}

//=================================================================================
// Language and Stemming
//=================================================================================

var STOP_WORDS = [ "a", "all", "am", "an", "and", "been", "by", "for", "has", "in", "is", "or", "said", "the", "that", "was", "were", "with" ];

function isStopWord(word) {
	var stopWordsSet = isStopWord._stopWordsSet;
	if (isUndefined(stopWordsSet)) {
		var stopWordsSet = {};
		var numStopWords = STOP_WORDS.length;
		for(var i=0; i<numStopWords; i++) {
			stopWordsSet[STOP_WORDS[i]] = true;
		}
		isStopWord._stopWordsSet = stopWordsSet;
	}
	return isDefined(stopWordsSet[word]);
}

function getWordStem(word) {
	var stemCache = getWordStem._stemCache;
	if (isUndefined(getWordStem.stemCache)) {
		stemCache = getWordStem._stemCache = {};
	}
	var stem = stemCache[word];

	if (isUndefined(stem)) {
		var snowballStemmer = getWordStem._snowballStemmer;
		if (isUndefined(snowballStemmer)) {
			snowballStemmer = getWordStem._snowballStemmer = new Snowball("english");
		}
		snowballStemmer.setCurrent(word);
		snowballStemmer.stem();
		stem = snowballStemmer.getCurrent();
		stemCache[word] = stem;
	}
	return stem;
}

/////////////////////////
// Channel support
/////////////////////////
function handleNew(idea) {
	createIdea(idea);
}

function handleRefresh(data) {
	window.location.reload();
}

function handlePhase(data) {
	window.location.reload();
}

function handleTag(data) {
	displayTags();
}