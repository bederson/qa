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

var OFFLINE = false;				// For offline debugging

var SHOW_TAGCLOUDS = true;
var MIN_TAGCLOUD_ITEM_COUNT = 7;
var MAX_CLOUD_HEIGHT = 800;

var SORT_BY_NAME = "name";
var SORT_BY_COUNT = "count";
var sortIndices = {};

var DISPLAY_SUBCATEGORIES = true;
var showSubcategories = false;
var subcategories = [];
var hasSubcategories = false;

var DISPLAY_ITEM_IN_SINGLE_CATEGORY = true;
var singleCategoryOnly = true;
var multipleIdeaLocations = {};

var question = null;
var categorizedIdeas = [];
var displayedCategoryIdeas = {};
var numIdeas = 0;
var showExpanded = true;
var hasAlsoIn = false;
var adminStats = null;
   
$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}

	initChannel(onChannelOpen);
	$("#page_content").show();
});

function onChannelOpen() {
	loadResults();
	
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
		showExpanded = $(this).is(":checked");
		displayIdeas();
	});
	
	$("#nest_categories_cb").click(function() {
		showSubcategories = $(this).is(":checked");
		createSortIndices();
		displayIdeas();
	});
	
	$("#also_in_cb").click(function() {
		showHideAlsoIn();
	});
	
	$("#single_category_cb").click(function() {
		singleCategoryOnly = $(this).is(":checked");
		createSortIndices();
		displayIdeas();
	});
}

function loadResults() {	
	var question_id = getURLParameter("question_id");
	var test = getURLParameter("test");

	var data = {
		"request": "ideas",
		"group_by": "category",
		"question_id": question_id,
		"test": test!=null && test=="1" ? "1" : "0"
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		categorizedIdeas = results.categorized;
		uncategorizedIdeas = results.uncategorized;
		numIdeas = results.count;
		
		// create list of subcategories
		if (DISPLAY_SUBCATEGORIES) {
			subcategories = [];
			for (var i in categorizedIdeas) {
				subcategoriesForCategory = categorizedIdeas[i].subcategories;
				if (subcategories.length > 0) {
					hasSubcategories = true;
				}
				for (var j in subcategoriesForCategory) {
					var subcategory = subcategoriesForCategory[j];
					if ($.inArray(subcategory, subcategories) == -1) {
						subcategories.push(subcategory);
					} 
				}
			}
		}
		
		// flag single category that item should be displayed in
		if (DISPLAY_ITEM_IN_SINGLE_CATEGORY) {
			var categoryCounts = {};
			for (var i in categorizedIdeas) {
				var category = categorizedIdeas[i].category;
				var ideas = categorizedIdeas[i].ideas;
				categoryCounts[category] = ideas.length;
			}
		
			multipleIdeaLocations = {};
			for (var i in categorizedIdeas) {
				var category = categorizedIdeas[i].category;
				var ideas = categorizedIdeas[i].ideas;
				for (var j in ideas) {
					var idea = ideas[j];
					if (isUndefined(multipleIdeaLocations[idea.id])) {
						var ideaSubcategories = [];
						var ideaRootCategories = [];
					    var alsoIn = idea.also_in ? $.extend(true, [], idea.also_in) : [];
						if (alsoIn.length > 0) {
							alsoIn.push(category);
							if (subcategories.length > 0) {
								ideaSubcategories = intersection(alsoIn, subcategories);
							}
							ideaRootCategories = ideaSubcategories.length > 0 ? difference(alsoIn, ideaSubcategories) : alsoIn;
							
							var showInCategory = null;
							if (ideaSubcategories.length > 0) {
								var smallestSubcategory = null;
								var largestSubcategory = null;
								for (var k in ideaSubcategories) {
									var subcategory = ideaSubcategories[k];
									if (!smallestSubcategory || (categoryCounts[subcategory] < categoryCounts[smallestSubcategory])) {
										smallestSubcategory = subcategory;
									}	
									if (!largestSubcategory || (categoryCounts[subcategory] > categoryCounts[largestSubcategory])) {
										largestSubcategory = subcategory;
									}								
								}
								showInCategory =  smallestSubcategory;
							}
							else {
								var smallestRootCategory = null;
								var largestRootCategory = null;
								for (var k in ideaRootCategories) {
									var rootCategory = ideaRootCategories[k];
									if (!smallestRootCategory || (categoryCounts[rootCategory] < categoryCounts[smallestRootCategory])) {
										smallestRootCategory = rootCategory;
									}
									if (!largestRootCategory || (categoryCounts[rootCategory] > categoryCounts[largestRootCategory])) {
										largestRootCategory = rootCategory;
									}										
								}
								showInCategory =  smallestRootCategory;
							}
							multipleIdeaLocations[idea.id] = { "subcategories": ideaSubcategories, "rootcategories": ideaRootCategories, "showin": showInCategory };
						}
					}			
				}
			}
		}
		
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

function createSortIndices() {
	var categoryTuples = [];
	var frequencyTuples = [];
	for (var i in categorizedIdeas) {
		var isSubcategory = DISPLAY_SUBCATEGORIES && showSubcategories && $.inArray(categorizedIdeas[i].category, subcategories) != -1;
		if (!isSubcategory) {
			categoryTuples.push([i, categorizedIdeas[i].category]);
			frequencyTuples.push([i, categorizedIdeas[i].ideas.length]);
		}
	}
	sortTuplesAscending(categoryTuples);
	sortTuplesDescending(frequencyTuples);
	
	sortIndices[SORT_BY_NAME] = [];
	sortIndices[SORT_BY_COUNT] = [];
	for (var i in categoryTuples) {
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
		html += categoryGroupAsHtml(categorizedIdeas[i], i+1);
	}
	
	if (uncategorizedIdeas.length > 0) {
		html += categoryGroupAsHtml({ category: "NONE", ideas: uncategorizedIdeas }, categorizedIdeas.length+1);
	}
	
	var newIdeaHtml = "<table style='width:100%'>";
	newIdeaHtml += "<tr>";
	newIdeaHtml += "<td style='width:50%'>";
	newIdeaHtml += "<ul id='new_ideas'></ul>";
	newIdeaHtml += "</td>";
	newIdeaHtml += "</tr>";
	newIdeaHtml += "</table>";
	$("#ideas").html(newIdeaHtml + html);
	updateStats();
	
	if (categorizedIdeas.length>0) {
		if (hasAlsoIn) {
			$("#also_in_control").show();
			$("#single_category_control").show();
			showHideAlsoIn();
		}
		else {
			$("#also_in_control").hide();
			$("#single_category_control").hide();
		}
		if (hasSubcategories) {
			$("#nest_categories_control").show();
		}
		else {
			$("#nest_categories_control").hide();
		}
		$("#display_control_area").show();
	}	
		
	// BEHAVIOR: only display tag clouds when cascade is complete and categories expanded
	if (SHOW_TAGCLOUDS && showExpanded && question.cascade_complete && !jQuery.browser.mobile) {
		for (var i in sortIndices[sortBy]) {
			var j = sortIndices[sortBy][i];
			var category = categorizedIdeas[j].category;
			var ideas = categorizedIdeas[j].ideas;
			var isSubcategory = DISPLAY_SUBCATEGORIES && showSubcategories && $.inArray(category, subcategories) != -1;
			if (!isSubcategory) {
				displayCloud(displayedCategoryIdeas[j+1], j+1);
			}
		}
		
		if (uncategorizedIdeas.length > 0) {
			displayCloud(uncategorizedIdeas, categorizedIdeas.length+1);
		}
	}
		
	$(document).tooltip({position:{my: "left+15 center", at:"right center"}});	
}

function categoryGroupAsHtml(categoryGroup, id) {
	var category = categoryGroup.category;
	var ideas = categoryGroup.ideas;
	var subcategories = isDefined(categoryGroup.subcategories) ? categoryGroup.subcategories : [];
	var sameAs = categoryGroup.same_as ? "Similar to: "+categoryGroup.same_as : "";
	
	// if a category has subcategories, the count needs to be adjusted since
	// some items in subcategories might not be marked as "fitting" the parent category
	var categoryCount = 0; 
	
	displayedCategoryIdeas[id] = [];
	var ideaHtml = "";
	for (var i in ideas) {
		var skip = false;
		var idea = ideas[i];
		var alsoIn = isDefined(idea.also_in) ? idea.also_in : [];
		if (DISPLAY_SUBCATEGORIES && showSubcategories && alsoIn.length > 0 && subcategories.length > 0) {
			isIdeaInSubcategory = intersection(alsoIn, subcategories).length > 0;
			skip = isIdeaInSubcategory;
		}
	
		if (singleCategoryOnly && isDefined(multipleIdeaLocations[idea.id]) && multipleIdeaLocations[idea.id].showin != category) {
			skip = true;
		}
			
		if (!skip) {
			displayedCategoryIdeas[id].push(idea);
			ideaHtml += ideaAsHtml(idea);
			categoryCount++;
		}
	}

	var subcategoryHtml = "";	
	if (DISPLAY_SUBCATEGORIES && showSubcategories) {
		for (var i in subcategories) {
			var subcategoryGroup = getCategory(subcategories[i]);
			var subcategory = subcategoryGroup.category;
			var subcategoryIdeas = subcategoryGroup.ideas;
			var subcategorySameAs = subcategoryGroup.same_as ? "Similar to: "+subcategoryGroup.same_as : "";	
			var subcategoryCount = 0;

			var subcategoryItemHtml = "";		
			for (var j in subcategoryGroup.ideas) {
				var skip = false;
				var subcategoryIdea = subcategoryIdeas[j];
				if (singleCategoryOnly && isDefined(multipleIdeaLocations[subcategoryIdea.id]) && multipleIdeaLocations[subcategoryIdea.id].showin != subcategory) {
					skip = true;
				}
		
				if (!skip) {
					if (!singleCategoryOnly && i>0) {
						if (!doesIdeaListContain(displayedCategoryIdeas[id], subcategoryIdea)) {
							displayedCategoryIdeas[id].push(subcategoryIdea);
						}
					}
					else {
						displayedCategoryIdeas[id].push(subcategoryIdea);
					}
					subcategoryItemHtml += ideaAsHtml(subcategoryIdea, category);
					subcategoryCount++;
				}
			}
			categoryCount += subcategoryCount;

			if (subcategoryCount > 0) {
				subcategoryHtml += "<li style='margin-top:3px'>";
				subcategoryHtml += "<strong>" + subcategory + "</strong>&nbsp;<span class='note'>("+subcategoryCount+") " + subcategorySameAs + "</span><br/>";
				if (showExpanded) {
					subcategoryHtml += "<ul class='subcategory_list'>";
					subcategoryHtml += subcategoryItemHtml;
					subcategoryHtml += "</ul>";
				}
				subcategoryHtml += "</li>";
			}
		}
	}
	
	var html = "";
	if (categoryCount > 0) {
		html += "<table style='width: 100%'><tr>";
		html += "<td style='width: 50%'>";
		html += "<strong>" + category + "</strong>&nbsp;<span class='note'>("+categoryCount+") " + sameAs + "</span><br/>";
		if (showExpanded) {
			html += "<ul class='category_list'>";
			html += ideaHtml;
			html += subcategoryHtml;
			html += "</ul>";
		}
		else if (subcategoryHtml != "") {
			html += "<ul class='category_list'>";
			html += subcategoryHtml;
			html += "</ul>";
		}
	
		html += "</td>";
		
		if (!jQuery.browser.mobile) {
			html += "<td style='width: 50%' valign='top'><div id='cloud"+id+"' class='cloud'></div></td>";
		}
		html += "</tr></table>";
	}
	return html;
}

function doesIdeaListContain(ideaList, idea) {
	var found = false;
	for (var i in ideaList) {
		if (ideaList[i].id == idea.id) {
			found = true;
			break;
		}
	}
	return found;
}

function showHideAlsoIn() {
	var showAlsoIn = $("#also_in_cb").is(":checked");
	if (showAlsoIn) {
		$(".also_in").show();
	}
	else {
		$(".also_in").hide();
	}
}

function getCategory(category) {
	var match = null;
	for (var i in categorizedIdeas) {
		if (categorizedIdeas[i].category == category) {
			match = categorizedIdeas[i];
			break;
		}
	}
	return match;
}

function addIdea(idea) {
	uncategorizedIdeas.push(idea);
	numIdeas++;
	var html = ideaAsHtml(idea);
	$("#new_ideas").prepend(html);
	updateStats();
}

function ideaAsHtml(idea, parent) {
	var alsoIn = idea.also_in ? $.extend(true, [], idea.also_in) : [];
	var parent = isDefined(parent) ? parent : null;
	if (alsoIn.length>0) {
		var alsoInIndex = alsoIn.indexOf(parent);
		if (alsoInIndex != -1) {
			alsoIn.splice(alsoInIndex, 1);
		}
	}
		
	var html = "<li>";
	html += idea.idea;
	if (alsoIn.length>0) {
		hasAlsoIn = true;
		html += "<span class='note also_in' style='display:none'><br/>Also in: " + alsoIn.join(", ") + "</span>";
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

var STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "here", "his", "how", "if", "in", "into", "is", "it", "its", "of", "on", "only", "or", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "this", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];

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