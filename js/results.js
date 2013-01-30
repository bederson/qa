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
	// Initialization goes here
	initChannel();
});

function displayIdeas(ideas) {
	var html = "Ideas loading ..."; 
	$("#clusteredIdeas").html(html);
	
	$.getJSON("/query", {}, displayIdeasImpl);
}

function displayIdeasImpl(data) {
	var clusters = data.ideas;
	var mobile = getURLParameter("mobile") == "true";

	var html = "";
	for (var i in clusters) {
		var cluster = clusters[i];
		html += "<h2>Cluster #" + (parseInt(i)+1) + "</h2>";
		html += "<table style='width: 100%'><tr>";
		html += "<td style='width: 50%'>";
		html += "<ul>"
		for (var j in cluster) {
			var idea = cluster[j];
			html += "<li>" + idea;
			numIdeas += 1;
		}
		html += "</ul></td>";
		if (!mobile) {
			var cloudid = "cloud" + i;
			html += "<td style='width: 50%'><div id='" + cloudid + "'></div></td>";
		}
		html += "</tr><table>"
	}

	updateNumIdeas();

	$("#clusteredIdeas").html(html);

	if (!mobile) {
		for (var i in clusters) {
			var cluster = clusters[i];
			var cloudid = "cloud" + i;
			var height = $("#" + cloudid).parent().height();
			$("#" + cloudid).height(height);
			displayCloud(cloudid, cluster);
		}
	}
}

function addIdea(idea) {
	$("#unclusteredIdeas").prepend("<li>" + idea);
	numIdeas += 1;
	updateNumIdeas();
}

function updateNumIdeas() {
	var label = "thought";
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
		var words = cluster[j].split(" ");
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
function handleNew(data) {
//	console.log("NEW message received");
	var text = data.text;
	
	addIdea(text);
}