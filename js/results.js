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
var OFFLINE = false;					// For offline debugging

var numIdeas = 0;
   
$(document).ready(function() {
	if (!logged_in) {
		$("#msg").html("Please log in");
		return;
	}

	var question_id = getURLParameter("question_id");
	if (!question_id) {
		$("#msg").html("Question code required");
		return;
	}

	initChannel();
		
	$("#pagecontent").show();
	
	if (!jQuery.browser.mobile) {
		$("#admin_buttons").show();
	}
		
	if (phase == PHASE_NOTES) {
		$("#note").show();
		$("#idea_link").attr("href", getPhaseUrl(question_id, PHASE_NOTES));
	}
		
	if (OFFLINE) {
		displayIdeas();
	}
	else {
		// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
		google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': displayIdeas });
	}
	
	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		redirectToAdminPage(question_id);
	});
});

function displayIdeas(ideas) {
	var html = "Notes loading ..."; 
	$("#ideas").html(html);

	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		// TODO: only supports one group of ideas currently
		var groupNumber = 1;
		var html = ideasToHtml(results.ideas, groupNumber);
		$("#ideas").html(html);
		numIdeas = results.ideas.length;
		updateNumIdeas();
		
		// BEHAVIOR: tag cloud only displayed when notes no longer being added
		if (SHOW_TAGCLOUDS && phase != PHASE_NOTES && !jQuery.browser.mobile) {
			displayCloud("cloud" + groupNumber, results.ideas);
		}
		
		$(document).tooltip({position:{my: "left+15 center", at:"right center"}});	
	});
}

function ideasToHtml(ideas, groupNumber) {
	alert("hidden idea authors not handled yet");
	// TODO: for testing only
	var identityHidden = true;
	
	var html = "<table style='width: 100%'><tr>";
	html += "<td style='width: 50%'>";
	html += "<div class='ideas'>";
	html += "<ul>";
	for (var i in ideas) {
		var idea = ideas[i];
		// TODO: for testing only
		idea.userIdentity = "Jane Doe";
		html += "<li>";
		html += idea.idea + "<br/>";
		html += "<span class='author'";
		//var identityHidden = idea.author.user_identity != "" && idea.author.user_identity != idea.author;
		if (identityHidden) {
			html += "title='" + idea.userIdentity + "' ";
		}
		html += ">&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author + (identityHidden?"*":"") + "</span>";
		html += "</li>";
	}
	html += "</ul>"
	html += "</div>";
	html += "</td>";
	
	if (!jQuery.browser.mobile) {
		if (!isDefined(groupNumber)) groupNumber = 1;
		var divid = "cloud" + groupNumber;
		var controlid = "control" + groupNumber;
		html += "<td style='width: 50%' valign='top'><div id='" + divid + "'></div><div id='" + controlid + "'</div></td>";
	}
	html += "</tr></table>";
	return html;
}

function addIdea(idea) {
	// TODO: fix when user identity stuff fixed
	var html = "<li>" + idea.idea + "<br/>";
	html += "<span class='author'>&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author.nickname + "</span><br>";
	html += "</li>";
	$("#ideas").prepend(html);
	numIdeas += 1;
	updateNumIdeas();
}

function updateNumIdeas() {
	var html = "(";
	if (numIdeas == 0) {
		html += "No notes yet";
	} else if (numIdeas == 1) {
		html += "1 " + label;
	} else {
		html += numIdeas + " notes";
	}
	html += ")";
	$("#num_ideas").html(html);
}

//=================================================================================
// Cloud Display
//=================================================================================

function displayCloud(divId, ideas) {
	var height = $("#" + divId).parent().height();
	if (height > MAX_CLOUD_HEIGHT) {
		height = MAX_CLOUD_HEIGHT;
	}
	$("#" + divId).height(height);
				
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

	$("#" + divId).jQCloud(wordList);
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
	addIdea(idea);
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