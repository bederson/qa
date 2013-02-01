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

var numIdeas = 0;

$(function() {
	initChannel();
	initEventHandlers();

	if (jQuery.browser.mobile) {
		$("#admin_buttons").css("display", "none");
	}
	
	displayIdeas();
});

function initEventHandlers() {
	$("#numclusters").change(function() {
		var label = "Create " + $(this).val() + " clusters";
		$("#clusterbutton").val(label);
	});
	$("#clusterbutton").click(function() {
		var num_clusters = $("#numclusters").val();
		var data = {
			"client_id": client_id,
			"num_clusters": num_clusters
		};
		$.post("/cluster", data, function() {
			window.location.reload();
		});
	})

	$("#admin_button").click(function() {
		window.location.href="/admin";
	});
}

function displayIdeas(ideas) {
	var html = "Ideas loading ..."; 
	$("#clusteredIdeas").html(html);
	
	$.getJSON("/query", {request: "ideas"}, displayIdeasImpl);
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
		html += "<ul>"
		for (var j in ideas) {
			var idea = ideas[j].idea;
			html += "<li>" + idea;
			html += "<br>" + "<span class='author'>&nbsp;&nbsp;&nbsp;&nbsp;-- " + ideas[j].author + "</span>";
			numIdeas += 1;
		}
		html += "</ul></td>";
		if (!jQuery.browser.mobile) {
			var cloudid = "cloud" + i;
			html += "<td style='width: 50%'><div id='" + cloudid + "'></div></td>";
		}
		html += "</tr><table>"
	}

	updateNumIdeas();

	$("#clusteredIdeas").html(html);

	if (!jQuery.browser.mobile) {
		for (var i in clusters) {
			var cluster = clusters[i];
			var ideas = cluster.ideas;
			var cloudid = "cloud" + i;
			var height = $("#" + cloudid).parent().height();
			$("#" + cloudid).height(height);
			displayCloud(cloudid, ideas);
		}
	}
}

function addIdea(idea) {
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

function displayCloud(cloudid, cluster) {
	var weights = {};
	for (var j in cluster) {
		var words = cluster[j].words;
		for (var k in words) {
			var word = words[k].trim();
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
// Language and Stemming
//=================================================================================

var STOP_WORDS = [ "a", "am", "an", "and", "been", "by", "in", "is", "or", "the", "was", "were" ];

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
	addIdea(idea);
}

function handleRefresh(data) {
	window.location.reload();
}

function handlePhase(data) {
	// Ignore it
}

function handleTag(data) {
	// Ignore it
}