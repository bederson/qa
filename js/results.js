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
var tag_cluster_hists = {};
var tag_idea_hists = {}
var similar_idea_hists = {}
var show_tags_in_charts = {};
    
$(document).ready(function() {
	if (!logged_in) {
		$("#msg").html("Please log in to view results");
		return;
	}

	var question_id = getURLParameter("question_id");
	if (!question_id) {
		$("#msg").html("Question code required");
		return;
	}
	
	$("#num_clusters_slider").slider({ min:0, max:11, value:6});
	
	initChannel();
	initEventHandlers();

	if (jQuery.browser.mobile) {
		$("#admin_buttons").css("display", "none");
	}

	if ((phase == PHASE_TAG_BY_CLUSTER) || (phase == PHASE_TAG_BY_NOTE)) {
		$("#start_tagging").css("display", "inline");
	}
	else if (phase == PHASE_COMPARE_BY_SIMILARITY) {
		// xx TBD
	}
	
	$("#idea_link").attr("href", "/idea?question_id=" + question_id);
	
	if (OFFLINE) {
		displayIdeas();
	}
	else {
		// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
		google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': displayIdeas });
	}
});

function initEventHandlers() {
	$("#num_clusters_slider").on("slide", function() {
		var num_clusters = $(this).slider("value");
		var label = "Create " + num_clusters + " clusters";
		$("#cluster_button").val(label);
	});
	
	$("#cluster_button").click(function() {
		var question_id = getURLParameter("question_id");
		var num_clusters = $("#num_cluster_values").slider("value");
		var data = {
			"client_id": client_id,
			"num_clusters": num_clusters,
			"question_id": question_id
		};
		$.post("/cluster", data, function() {
			window.location.reload();
		});
	})

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

function displayIdeasImpl(results) {
	var html = "";
	for (var i in results) {
		var cluster = results[i];
		var clusterName = cluster.name;
		var ideas = cluster.ideas;
		tag_cluster_hists[cluster.id] = {};
		html += "<h2>" + clusterName + "</h2>";
		html += "<table style='width: 100%'><tr>";
		html += "<td style='width: 50%'>";
		html += "<div class='ideas'>";
		html += "<ul>"
		for (var j in ideas) {
			var idea = ideas[j].idea;
			tag_idea_hists[ideas[j].idea_id] = {};
			var tagsid = "tags" + ideas[j].idea_id;
			similar_idea_hists[ideas[j].idea_id] = {};
			var similarid = "similar" + ideas[j].idea_id;
			html += "<li>" + idea;
			html += "<br>" + "<span ";
			var identityHidden = ideas[j].author.user_identity != "" && ideas[j].author.user_identity != ideas[j].author.nickname;
			if (identityHidden) {
				html += "title='" + ideas[j].author.user_identity + "' ";
			}
			html += "class='author'>&nbsp;&nbsp;&nbsp;&nbsp;-- " + ideas[j].author.nickname + (identityHidden?"*":"") + "</span>";
			html += "<span id='" + tagsid + "' class='tags'></span>";
			html += "<span id='" + similarid + "' class='tags'></span>";
			numIdeas += 1;
		}
		html += "</ul>"
		html += "</div>";
		html += "</td>";
		if (!jQuery.browser.mobile && (phase != PHASE_TAG_BY_NOTE)) {
			var divid = "vis" + cluster.id;
			var controlid = "control" + cluster.id;
			html += "<td style='width: 50%' valign='top'><div id='" + divid + "'></div><div id='" + controlid + "'</div></td>";
		}
		html += "</tr></table>"
	}
	$("#clusteredIdeas").html(html);
	updateNumIdeas();
	
	if (!jQuery.browser.mobile) {
		if ((phase == PHASE_DISABLED) || (phase == PHASE_NOTES)) {
			for (var i in results) {
				var cluster = results[i];
				var ideas = cluster.ideas;
				var cloudid = "vis" + cluster.id;
				var height = $("#" + cloudid).parent().height();
				if (height > MAX_CLOUD_HEIGHT) {
					height = MAX_CLOUD_HEIGHT;
				}
				$("#" + cloudid).height(height);
				displayCloud(cloudid, ideas);
			}
		} else if (phase == PHASE_TAG_BY_CLUSTER) {
			displayTagControls(results);
			displayClusterTags();
		} else if (phase == PHASE_TAG_BY_NOTE) {
			displayIdeaTags();
		} else if (phase == PHASE_COMPARE_BY_SIMILARITY) {
			displaySimilarIdeas();
		}
	}
	
	$(document).tooltip({position:{my: "left+15 center", at:"right center"}});
	
}

function createIdea(idea) {
	var html = "<li>" + idea.text;
	html += "<br>" + "<span class='author'>&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author.nickname + "</span><br>";
	$("#unclusteredIdeas").prepend(html);
	numIdeas += 1;
	updateNumIdeas();
}

function updateNumIdeas() {
	var question_id = getURLParameter("question_id");
	var label = "note";
	var overviewStr = "<h1>Code: " + question_id + " (";
	if (numIdeas == 0) {
		overviewStr += "No " + label + "s yet";
	} else if (numIdeas == 1) {
		overviewStr += "1 " + label;
	} else {
		overviewStr += numIdeas + " " + label + "s";
	}
	overviewStr += ")</h1>";
	$("#ideaOverview").html(overviewStr);

	$("#ideaOverview").append("Question: " + question);
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
// Idea Tags Display
//=================================================================================
function displayIdeaTags() {
	// Initialize tag counts
	for (tag in tag_idea_hists) {
		tag_idea_hists[tag] = {};
	}
	
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideatags",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		processIdeaTags(results);
		drawIdeaTags();
	});	
}

function processIdeaTags(data) {
	var tags = data.tags;
	// Process tags to fill data structures
	for (var i in tags) {
		var tag = tags[i].tag;
		var idea_id = tags[i].idea_id;
		createIdeaTag(tag, idea_id);
	}
}

function createIdeaTag(tag, idea_id) {
	if (tag in tag_idea_hists[idea_id]) {
		tag_idea_hists[idea_id][tag] += 1;
	} else {
		tag_idea_hists[idea_id][tag] = 1
	}
}

function drawIdeaTags() {
	for (var i in tag_idea_hists) {
		var chartid = "tags" + i;
		var hist = tag_idea_hists[i];

		// Create the data table.
		var rows = [];
		var max = 0;
		for (item in hist) {
			rows.push([item, hist[item]]);
		}
		rows.sort(function(a, b) {
			return(b[1] - a[1]);
		});

		if (rows.length > 0) {
			var html = "<br>&nbsp;&nbsp;&nbsp;&nbsp;Tags: ";
			for (j in rows) {
				if (j > 0) {
					html += ", ";
				}
				var row = rows[j];
				html += row[0] + " (" + row[1] + ")";
			}
			$("#" + chartid).html(html);
		}
	}
}

//=================================================================================
// Similar Ideas Display
//=================================================================================
function displaySimilarIdeas() {
	// Initialize counts
	for (idea_id in similar_idea_hists) {
		similar_idea_hists[idea_id] = {};
	}
		
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "similarideas",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		processSimilarIdeas(results);
		drawSimilarIdeas();
	});	
}

function processSimilarIdeas(data) {	
	var similar_ideas = data.ideas;
	for (var i in similar_ideas) {
		var idea = similar_ideas[i].idea;
		var similar_to = similar_ideas[i].similar;
		createSimilarIdea(similar_to.text, idea.id);
	}
}

function createSimilarIdea(similar, idea_id) {
	if (similar in similar_idea_hists[idea_id]) {
		similar_idea_hists[idea_id][similar] += 1;
	} else {
		similar_idea_hists[idea_id][similar] = 1
	}
}

function drawSimilarIdeas() {
	for (var idea_id in similar_idea_hists) {
		// Create the data table.
		var rows = [];
		var max = 0;
		var hist = similar_idea_hists[idea_id];
		for (item in hist) {
			rows.push([item, hist[item]]);
		}
		rows.sort(function(a, b) {
			return(b[1] - a[1]);
		});

		if (rows.length > 0) {
			var html = "<br/>&nbsp;&nbsp;&nbsp;&nbsp;Similar: ";
			for (j in rows) {
				if (j > 0) {
					html += ", ";
				}
				var row = rows[j];
				html += row[0] + " (" + row[1] + ")";
			}
			$("#similar" + idea_id).html(html);
		}
	}
}

//=================================================================================
// Cluster Tag Chart Display
//=================================================================================
function displayClusterTags() {
	// Initialize tag counts
	for (tag in tag_cluster_hists) {
		tag_cluster_hists[tag] = {};
	}
	
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "clustertags",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		processClusterTags(results);
		drawCharts();
	});
}

function processClusterTags(data) {
	var tags = data.tags;
	// Process tags to fill data structures
	for (var i in tags) {
		var tag = tags[i].tag;
		var cluster = tags[i].cluster;
		createClusterTag(tag, cluster);
	}
}

function createClusterTag(tag, cluster) {
	if (tag in tag_cluster_hists[cluster]) {
		tag_cluster_hists[cluster][tag] += 1;
	} else {
		tag_cluster_hists[cluster][tag] = 1
	}
}

function displayTagControls(clusters) {
	for (var i in clusters) {
		var id = clusters[i].id;
		show_tags_in_charts[id] = false;
		var controlid = "control" + id;
		var showTagID = "showtag" + id;
		var html = "<div style='margin-left:200px;'><input id='" + showTagID + "' type='button' value='Show tags'></div>";
		$("#" + controlid).append(html);
		$("#" + showTagID).data("cluster", id);
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
	for (var i in tag_cluster_hists) {
		var chartid = "vis" + i;
		var hist = tag_cluster_hists[i];

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
					'backgroundColor': $("body").css("background-color"),
					'fontSize': 20,
					'chartArea': {
						'left': 190,
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
	if (phase == PHASE_TAG_BY_CLUSTER) {
		displayClusterTags();
	} else if (phase == PHASE_TAG_BY_NOTE) {
		displayIdeaTags();
	} else if (phase == PHASE_COMPARE_BY_SIMILARITY) {
		displaySimilarIdeas();
	}
}

function handleNickname(data) {
	// TODO: would be better to only refresh changed data
	window.location.reload();
}