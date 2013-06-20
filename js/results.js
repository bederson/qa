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

var SHOW_TAGCLOUDS = true;
var MAX_CLOUD_HEIGHT = 800;
var OFFLINE = false;				// For offline debugging

var question = null;
var ideas = []
   
$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}

	// TODO: when should channel be created
	initChannel();
		
	$("#page_content").show();
	loadQuestion();
	
	if (!jQuery.browser.mobile) {
		$("#admin_buttons").show();
	}
	
	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		redirectToAdminPage(question_id);
	});
});

function loadQuestion() {	
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		ideas = results.ideas;
		
		if (question.phase == PHASE_NOTES) {
			$("#note").show();
			$("#idea_link").attr("href", getPhaseUrl(question.id, PHASE_NOTES));
		}
		
		if (OFFLINE) {
			displayIdeas();
		}
		else {
			// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
			google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': displayIdeas });
		}
	});
}

function displayIdeas() {	
	var html = "<table style='width: 100%'><tr>";
	html += "<td style='width: 50%'>";
	html += "<ul id=\"idea_list\">";
	for (var i in ideas) {
		html += ideaAsHtml(ideas[i]);
	}
	html += "</ul>"
	html += "</td>";
	
	if (!jQuery.browser.mobile) {
		html += "<td style='width: 50%' valign='top'><div id='cloud'></div></td>";
	}
	html += "</tr></table>";
	$("#ideas").html(html);
	updateNumIdeas();
		
	// BEHAVIOR: tag cloud only displayed when notes no longer being added
	if (SHOW_TAGCLOUDS && question.phase != PHASE_NOTES && !jQuery.browser.mobile) {
		displayCloud();
	}
		
	$(document).tooltip({position:{my: "left+15 center", at:"right center"}});	
}

function addIdea(idea) {
	ideas.push(idea);
	var html = ideaAsHtml(idea);
	$("#idea_list").prepend(html);
	updateNumIdeas();
}

function ideaAsHtml(idea) {
	var html = "<li>";
	html += idea.idea + "<br/>";
	html += "<span class='author'";
	var realIdentity = isDefined(idea.author_identity) ? idea.author_identity : "";
	var isIdentityHidden = realIdentity != "" && realIdentity != idea.author;
	if (isIdentityHidden) {
		html += "title='" + realIdentity + "' ";
	}
	html += ">&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author + (isIdentityHidden?"*":"") + "</span>";
	html += "</li>";
	return html;	
}
function updateNumIdeas() {
	var numIdeas = ideas.length;
	var html = "(";
	if (numIdeas == 0) {
		html += "No notes yet";
	} else if (numIdeas == 1) {
		html += "1 note";
	} else {
		html += numIdeas + " notes";
	}
	html += ")";
	$("#num_ideas").html(html);
}

//=================================================================================
// Cloud Display
//=================================================================================

function displayCloud() {
	var div = $("#cloud");
	var height = div.parent().height();
	if (height > MAX_CLOUD_HEIGHT) {
		height = MAX_CLOUD_HEIGHT;
	}
	div.height(height);
				
	var weights = {};
	for (var i in ideas) {
		var words = ideas[i].idea.split(" ");
		for (var j in words) {
			var word = words[j].trim().toLowerCase();
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

	var i = 0;
	var wordList = [];
	for (var word in weights) {
		var item = { text: word, weight: weights[word] };
		wordList[i] = item;
		i += 1;
	}

	div.jQCloud(wordList);
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
function handleNew(data) {
	addIdea(data.idea);
}

function handleRefresh(data) {
	window.location.reload();
}

function handlePhase(data) {
	window.location.reload();
}

function handleTag(data) {
}

function handleNickname(data) {
	// TODO: would be better to only refresh changed data
	window.location.reload();
}