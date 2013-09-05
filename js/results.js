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
var MIN_TAGCLOUD_ITEM_COUNT = 7;
var MAX_CLOUD_HEIGHT = 800;
var OFFLINE = false;				// For offline debugging

var SORT_BY_NAME = "name";
var SORT_BY_COUNT = "count";
var sortIndices = {};

var question = null;
var categorizedIdeas = [];
var uncategorizedIdeas = [];
var numIdeas = 0;
var expandCategories = true;
var adminStats = null;
   
$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}

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
	
	$("#sort_by").change(function() {
		displayIdeas();
	});
	
	$("#expand_categories_cb").click(function() {
		expandCategories = $(this).is(":checked");
		displayIdeas();
	});
});

function loadQuestion() {	
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas",
		"group_by": "category",
		"question_id": question_id
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		categorizedIdeas = results.categorized;
		uncategorizedIdeas = results.uncategorized;
		numIdeas = results.count;
		createSortIndices();
		updateStatus();
		
		if (OFFLINE) {
			displayIdeas();
		}
		else {
			// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
			google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': displayIdeas });
		}
	});
}

function sortBy(categoryGroups, sort) {	
	sort = isDefined(sort) ? sort : "category";
	var sortedGroups = [];
	if (sort == "frequency") {
		var categoryCounts = [];
		for (var i in categoryGroups) {
			categoryCounts.push([i, categoryGroups[i].ideas.length]);
		}
		
		// sort from largest to smallest
		categoryCounts.sort(function(group1, group2) {
			count1 = group1[1];
			count2 = group2[1];
			return count1 > count2 ? -1 : (count1 < count2 ? 1 : 0);
		});
			
		for (i in categoryCounts) {
			var categoryIndex = categoryCounts[i][0];
			sortedGroups.push(categoryGroups[categoryIndex]);
		}
	}
	else {
		var categoryNames = [];
		for (var i in categoryGroups) {
			categoryNames.push([i, categoryGroups[i].category]);
		}
		
		categoryNames.sort(function(group1,  group2) {
			name1 = group1[1];
			name2 = group2[1];
			return name1 < name2 ? -1 : (name1 > name2 ? 1 : 0);
		});
			
		for (i in categoryNames) {
			var categoryIndex = categoryNames[i][0];
			sortedGroups.push(categoryGroups[categoryIndex]);
		}
	}
	return sortedGroups;
}

function createSortIndices() {
	var categoryTuples = [];
	var frequencyTuples = [];
	for (var i in categorizedIdeas) {
		categoryTuples.push([i, categorizedIdeas[i].category]);
		frequencyTuples.push([i, categorizedIdeas[i].ideas.length]);
	}
	sortTuplesAscending(categoryTuples);
	sortTuplesDescending(frequencyTuples);
	
	sortIndices[SORT_BY_NAME] = [];
	sortIndices[SORT_BY_COUNT] = [];
	for (var i in categorizedIdeas) {
		sortIndices[SORT_BY_NAME].push(categoryTuples[i][0]);
		sortIndices[SORT_BY_COUNT].push(frequencyTuples[i][0]);
	}
}

function updateStatus() {
	$("#inactive").html(!question.active ? "INACTIVE" : "");
	if (question.active && !question.cascade_complete) {
		$("#idea_link").attr("href", getNotesPageUrl(question.id));
		$("#idea_link_area").show();
	}
	else {
		$("#idea_link_area").hide();
	}
}

function displayIdeas() {
	var html = "";
	var sortBy = $("#sort_by").val();
	for (var j in sortIndices[sortBy]) {
		var i = sortIndices[sortBy][j];
		var category = categorizedIdeas[i].category;
		var categoryIdeas = categorizedIdeas[i].ideas;
		var sameAs = categorizedIdeas[i].same_as ? "Similar to: "+categorizedIdeas[i].same_as : "";
		html += "<strong>" + category + "</strong> <span class='note'>("+categoryIdeas.length+") " + sameAs + "</span><br/>";
		if (expandCategories) {
			html += ideaGroupAsHtml(categoryIdeas, i+1);
		}
	}
	
	if (uncategorizedIdeas.length > 0) {
		if (question.cascade_complete) {
			html += "<strong>NONE</strong> <span class='note'>("+uncategorizedIdeas.length+")</span><br/>";
		}
		if (expandCategories) {
			html += ideaGroupAsHtml(uncategorizedIdeas, categorizedIdeas.length+1);
		}
	}
	
	$("#ideas").html(html);
	updateStats();
	
	if (categorizedIdeas.length>0) {
		$("#display_control_area").show();
	}
		
	// BEHAVIOR: only display tag clouds when cascade is complete
	if (SHOW_TAGCLOUDS && question.cascade_complete && !jQuery.browser.mobile) {
		for (var i in categorizedIdeas) {
			displayCloud(categorizedIdeas[i].ideas, i+1);
		}
		
		if (uncategorizedIdeas.length > 0) {
			displayCloud(uncategorizedIdeas, categorizedIdeas.length+1);
		}
	}
		
	$(document).tooltip({position:{my: "left+15 center", at:"right center"}});	
}

function ideaGroupAsHtml(group, id) {
	var html = "<table style='width: 100%'><tr>";
	html += "<td style='width: 50%'>";
	html += "<ul id=\"idea_list\">";
	for (var i in group) {
		var idea = group[i];
		html += ideaAsHtml(idea);
	}
	html += "</ul>"
	html += "</td>";
	
	if (!jQuery.browser.mobile) {
		html += "<td style='width: 50%' valign='top'><div id='cloud"+id+"' class='cloud'></div></td>";
	}
	html += "</tr></table>";
	return html;
}

function addIdea(idea) {
	uncategorizedIdeas.push(idea);
	numIdeas++;
	var html = ideaAsHtml(idea);
	$("#idea_list").prepend(html);
	updateStats();
}

function ideaAsHtml(idea) {
	var html = "<li>";
	html += idea.idea;
	if (idea.also_in) {
		html += "<br/><span class='note'>Also in: " + idea.also_in + "</span>";
	}
	html += "<br/>";
	html += "<span class='author'";
	var realIdentity = isDefined(idea.author_identity) ? idea.author_identity : "";
	var isIdentityHidden = realIdentity != "" && realIdentity != idea.author;
	if (isIdentityHidden) {
		html += " title='" + realIdentity + "' ";
	}
	html += ">&nbsp;&nbsp;&nbsp;&nbsp;-- " + idea.author + (isIdentityHidden?"*":"") + "</span>";
	html += "</li>";
	return html;	
}

function updateStats() {
	var stats = [];

	// number of ideas
	var stat = numIdeas == 0 ? "No notes yet" : (numIdeas == 1 ? "1 note" : numIdeas + " notes");
	stats.push(stat);
	
	// number of categories (if any)
	if (categorizedIdeas.length>0) {
		stats.push(categorizedIdeas.length + (categorizedIdeas.length == 1 ? " category" : " categories"));
	}
	
	// number of uncategorized ideas (if any)
	if (categorizedIdeas.length>0 && uncategorizedIdeas.length > 0) {
		stats.push(uncategorizedIdeas.length + (uncategorizedIdeas.length == 1? " uncategorized note" : " uncategorized notes"));
	}
		
	var html = stats.length > 0 ? "(" + stats.join(", ") + ")" : ""
	$("#question_stats").html(html);
}

//=================================================================================
// Cloud Display
//=================================================================================

// TODO: improve css for div.jqcloud
function displayCloud(group, id) {
	var div = $("#cloud"+id);
	
	// do not show tag clouds for groups with < MIN_TAGCLOUD_ITEM_COUNT items
	if (group.length < MIN_TAGCLOUD_ITEM_COUNT) {
		div.html("");
		return;
	}
	
	var height = div.parent().height();
	if (height > MAX_CLOUD_HEIGHT) {
		height = MAX_CLOUD_HEIGHT;
	}
	div.height(height);
				
	var weights = {};
	for (var i in group) {
		var words = group[i].idea.split(" ");
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

var STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "are", "as", "at", "be", "been", "being", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "here", "his", "how", "if", "in", "into", "is", "it", "its", "of", "on", "only", "or", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];

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
function handleIdea(data) {
	addIdea(data.idea);
}

function handleEnable(data) {
	question.active = 1;
	updateStatus();
}

function handleDisable(data) {
	question.active = 0;
	updateStats();
}

function handleNickname(data) {
	// TODO: would be better to only update data that has changed
	window.location.reload();
}

function handleResults(data) {
	question.cascade_complete = 1;
	question.cascade_stats = data.cascade_stats;
	window.location.reload();
}

function handleLogout(data) {
	var question_id = getURLParameter("question_id");
	redirectToLogout(question_id);
}