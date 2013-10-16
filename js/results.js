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

var SHOW_DISCUSS_BUTTONS = false;
var SHOW_TAGCLOUDS = true;
var MIN_TAGCLOUD_ITEM_COUNT = 7;
var MAX_CLOUD_HEIGHT = 800;

var SORT_BY_NAME = "name";
var SORT_BY_COUNT = "count";

var DISPLAY_SUBCATEGORIES = true;
var subcategories = [];
var showSubcategories = false;
var hasSubcategories = false;

var DISPLAY_ITEM_IN_SINGLE_CATEGORY = true;
var singleCategoryOnly = false;
var showOnlyInCategories = {};

var showExpanded = true;
var showAlsoIn = false;
var hasAlsoIn = false;

var question = null;
var categorizedIdeas = [];
var uncategorizedIdeas = [];
var numIdeas = 0;
var displayedCategories = {};
var categoryCounts = {};
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
		updateDisplayCategories();
		displayIdeas();
	});
	
	$("#expand_categories_cb").click(function() {
		showExpanded = $(this).is(":checked");
		displayIdeas();
	});
	
	$("#nest_categories_cb").click(function() {
		showSubcategories = DISPLAY_SUBCATEGORIES && $(this).is(":checked");
		updateDisplayCategories();
		displayIdeas();
	});
	
	$("#also_in_cb").click(function() {
		showAlsoIn = $(this).is(":checked");
		showHide($(".also_in"), showAlsoIn);
	});
	
	$("#single_category_cb").click(function() {
		singleCategoryOnly = $(this).is(":checked");
		updateDisplayCategories();
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
		updateStatus();
		
		categoryCounts = {};
		for (var i in categorizedIdeas) {
			var category = categorizedIdeas[i].category;
			var ideas = categorizedIdeas[i].ideas;
			categoryCounts[category] = ideas.length;
		}
			
		// create list of subcategories
		if (DISPLAY_SUBCATEGORIES) {
			subcategories = [];
			for (var i in categorizedIdeas) {
				subcategoriesForCategory = categorizedIdeas[i].subcategories;
				for (var j in subcategoriesForCategory) {
					var subcategory = subcategoriesForCategory[j];
					if ($.inArray(subcategory, subcategories) == -1) {
						subcategories.push(subcategory);
					} 
				}
			}
			hasSubcategories = subcategories.length > 0;
		}
		
		// find category that item should be displayed in if only displayed in a *single* category
		if (DISPLAY_ITEM_IN_SINGLE_CATEGORY) {		
			showOnlyInCategories = {};
			for (var i in categorizedIdeas) {
				var category = categorizedIdeas[i].category;
				var ideas = categorizedIdeas[i].ideas;
				for (var j in ideas) {
					var idea = ideas[j];
					if (isUndefined(showOnlyInCategories[idea.id])) {
						var ideaSubcategories = [];
					    var ideaAlsoIn = idea.also_in ? $.extend(true, [], idea.also_in) : [];
						if (ideaAlsoIn.length > 0) {
							ideaAlsoIn.push(category);
							if (subcategories.length > 0) {
								ideaSubcategories = intersection(ideaAlsoIn, subcategories);
							}
							
							var showInCategory = null;							
							if (ideaSubcategories.length > 0) {
								var minMaxSubcategories = getMinMaxCategories(ideaSubcategories);
								// TODO/FIX: consider whether single category should be smallest or largest
								showInCategory = minMaxSubcategories.min;
							}
							else {
								var ideaRootCategories = ideaSubcategories.length > 0 ? difference(ideaAlsoIn, ideaSubcategories) : ideaAlsoIn;
								var minMaxRootCategories = getMinMaxCategories(ideaRootCategories);
								showInCategory =  minMaxRootCategories.min;
							}
							showOnlyInCategories[idea.id] = showInCategory;
						}
					}			
				}
			}
		}
		
		// update data structure used to display results
		updateDisplayCategories();
			
		if (OFFLINE) {
			displayIdeas();
		}
		else {
			// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
			google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': displayIdeas });
		}
	});
}

function updateDisplayCategories() {
	displayedCategories = {};
	for (var i in categorizedIdeas) {
		var categoryGroup = categorizedIdeas[i];
		var category = categoryGroup.category;
		var categoryIdeas = categoryGroup.ideas;
		var categorySubcategories = isDefined(categoryGroup.subcategories) ? categoryGroup.subcategories : [];
		var categorySameAs = categoryGroup.same_as;
		
		var isRootCategory = !showSubcategories || ($.inArray(category, subcategories) == -1);
		if (isRootCategory) {
			var count = 0;
			for (var j in categoryIdeas) {
				var skip = false;
				var idea = categoryIdeas[j];
				var alsoIn = isDefined(idea.also_in) ? idea.also_in : [];
				if (showSubcategories && alsoIn.length > 0 && categorySubcategories.length > 0) {
					isIdeaInSubcategory = intersection(alsoIn, categorySubcategories).length > 0;
					skip = isIdeaInSubcategory;
				}
			
				if (singleCategoryOnly && isDefined(showOnlyInCategories[idea.id]) && showOnlyInCategories[idea.id] != category) {
					skip = true;
				}
					
				if (!skip) {
					// initialize root category in displayedCategories
					// ideas + moreideas = unique list of ideas contained in root category
					if (isUndefined(displayedCategories[i])) {
						displayedCategories[i] = { "category":category, "ideas":[], "moreideas":[], "subcategories":[], "sameas":categorySameAs, "count":0 };
					}
					
					// update root category
					displayedCategories[i]["ideas"].push(idea);
					displayedCategories[i]["count"]++;
					count++;
				}
			}
		}
		
		// CHECK: added isRootCategory because subcategories not working correctly
		if (showSubcategories && isRootCategory) {
			var subcategoryIndex = 0;
			for (var j in categorySubcategories) {
				var subcategoryGroup = getCategory(categorySubcategories[j]);
				// check if subcategory found
				// if not, it may have already been merged with another category (if it is a duplicate)
				// if not, the category it was merged with will only be checked if it is also a subcategory of this category
				if (subcategoryGroup) {
					var subcategory = subcategoryGroup.category;
					var subcategoryIdeas = subcategoryGroup.ideas;
					var subcategorySameAs = subcategoryGroup.same_as;
					var count = 0;
					for (var k in subcategoryIdeas) {
						var subcategoryIdea = subcategoryIdeas[k];
						var skip = singleCategoryOnly && isDefined(showOnlyInCategories[subcategoryIdea.id]) && (showOnlyInCategories[subcategoryIdea.id] != subcategory);
						if (!skip) {
							// update root category	associated with subcategory										
							if (singleCategoryOnly || subcategoryIndex==0 || !doesIdeaListContain(displayedCategories[i]["ideas"], subcategoryIdea)) {
								displayedCategories[i]["moreideas"].push(subcategoryIdea);	
							}
							displayedCategories[i]["count"]++;
	
							// initialize subcategory
							if (count == 0) {	
								displayedCategories[i]["subcategories"].push({ "category":subcategory, "ideas":[], "sameas":subcategorySameAs, "count":0 })
							}
							
							// update subcategory
							displayedCategories[i]["subcategories"][subcategoryIndex]["ideas"].push(subcategoryIdea);
							displayedCategories[i]["subcategories"][subcategoryIndex]["count"]++;
							count++;
						}
					}
					subcategoryIndex++;
				}
			}
		}
	}
}

function getSortIndices(categoriesToSort) {
	var categoriesToSort = isDefined(categoriesToSort) ? categoriesToSort : displayedCategories;
	var sortBy = $("#sort_by").val();
	var sortTuples = [];
	for (var i in categoriesToSort) {
		var sortValue = sortBy == SORT_BY_NAME ? categoriesToSort[i].category : categoriesToSort[i].count;
		sortTuples.push([i, sortValue]);
	}
	
	if (sortBy == SORT_BY_COUNT) {
		sortTuplesDescending(sortTuples);
	}
	else {
		sortTuplesAscending(sortTuples);
	}
	
	var sortIndices = [];
	for (var i in sortTuples) {
		sortIndices.push(sortTuples[i][0]);
	}
	return sortIndices;
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
	// update question stats: # items, # categories, # uncategorized
	updateStats();
	
	// categorized html
	// TODO: sort subcategories
	var html = "";
	var sortIndices = getSortIndices();
	for (var i=0; i<sortIndices.length; i++) {
		var index = sortIndices[i];
		html += categoryGroupAsHtml(displayedCategories[index], index);
	}
	
	// uncategorized html
	if (uncategorizedIdeas.length > 0) {
		html += categoryGroupAsHtml({ category: categorizedIdeas.length > 0 ? "NONE" : "", ideas: uncategorizedIdeas, count: uncategorizedIdeas.length }, categorizedIdeas.length+1);
	}
	
	// new idea html
	var newIdeaHtml = "<table style='width:100%'>";
	newIdeaHtml += "<tr>";
	newIdeaHtml += "<td style='width:50%'>";
	newIdeaHtml += "<ul id='new_ideas' style='margin-bottom:0'></ul>";
	newIdeaHtml += "</td>";
	newIdeaHtml += "</tr>";
	newIdeaHtml += "</table>";
	$("#ideas").html(newIdeaHtml + html);
	
	// TODO: need to highlight image on mouseover
	//$(".discuss_idea_button").mouseover(function() {
	//	$(this).css('border', 'solid 1px black');
	//});

	//$(".discuss_idea_button").mouseout(function() {
	//	$(this).css('border', 'none');
	//});
		
	$(".discuss_idea_button").click(function() {
		var buttonId = $(this).attr("name");
		var tokens = buttonId.split("_");
		var ideaId = tokens[2];
		
		var data = {
			"client_id": client_id,
			"question_id": question.id,
			"idea_id" : ideaId
		};
		$.post("/discuss_idea", data, function(result) {
			if (result.status == 1) {
				// TODO/FIX: keep track of who marked to discuss vs. simple count
				$(".discuss_idea_"+ideaId+"_count").html("+" + result.count);
			}
		}, "json");
	});
	
	// show/hide controls
	if (categorizedIdeas.length>0) {
		showHide($("#also_in_control"), hasAlsoIn);
		showHide($("#single_category_control"), hasAlsoIn);
		showHide($("#nest_categories_control"), hasSubcategories);
		showHide($(".also_in"), showAlsoIn);
		$("#display_control_area").show();
	}	
		
	// BEHAVIOR: only display tag clouds when cascade is complete and categories expanded
	if (SHOW_TAGCLOUDS && showExpanded && question.cascade_complete && !jQuery.browser.mobile) {
		for (var i=0; i<sortIndices.length; i++) {
			var j = sortIndices[i];
			var category = displayedCategories[j].category;
			var ideas = displayedCategories[j].ideas;
			var isRootCategory = !showSubcategories || ($.inArray(category, subcategories) == -1);			
			if (isRootCategory) {
				displayCloud(displayedCategories[j].ideas.concat(displayedCategories[j].moreideas), j);
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
	var sameAs = isDefined(categoryGroup.sameas) ? "Similar to: "+categoryGroup.sameas : "";
	var categoryCount = categoryGroup.count;
	
	var html = "";
	if (categoryCount > 0) {
		html += "<table style='width: 100%'><tr>";
		html += "<td style='width: 50%'>";
		// an empty category means the items have not been categorized yet
		if (category != "") {
			html += "<strong>" + category + "</strong>&nbsp;<span class='note'>(" + categoryCount + ") " + sameAs + "</span><br/>";		
		}
		if (showExpanded) {
			html += "<ul" + (category == "" ? " style='margin-top:0px'" : "") + ">";
			for (var i in ideas) {
				html += ideaAsHtml(ideas[i]);
			}
		}
		
		if (showSubcategories && isDefined(categoryGroup.subcategories) && categoryGroup.subcategories.length > 0) {
			html += !showExpanded ? "<ul style='margin-top:5px'>" : "";
			for (var i in categoryGroup.subcategories) {
				var subcategoryGroup = categoryGroup.subcategories[i];
				var subcategory = subcategoryGroup.category;
				var subcategoryIdeas = subcategoryGroup.ideas;
				var subcategorySameAs = subcategoryGroup.sameas ? "Similar to: "+subcategoryGroup.sameas : "";	
				var subcategoryCount = subcategoryGroup.count;
		
				html += "<li style='margin-top:8px'>";
				html += "<strong>" + subcategory + "</strong>&nbsp;<span class='note'>(" + subcategoryCount + ") " + subcategorySameAs + "</span><br/>";
				if (showExpanded) {
					html += "<ul style='margin-top:15px'>";
					for (var j in subcategoryIdeas) {
						html += ideaAsHtml(subcategoryIdeas[j], category);
					}
					html += "</ul>";
				}
				html += "</li>";
			}
			html += !showExpanded ? "</ul>" : "";
		}

		if (showExpanded) {
			html += "</ul>";
		}
		html += "</td>";
		
		if (!jQuery.browser.mobile) {
			html += "<td style='width: 50%' valign='top'><div id='cloud"+id+"' class='cloud'></div></td>";
		}
		
		html += "</tr>";
		html += "</table>";
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
	if (SHOW_DISCUSS_BUTTONS) {
		html += "<img name='discuss_idea_"+idea.id+"_button' class='discuss_idea_button' src='/images/discuss.png' style='vertical-align:middle' /> ";
		html += "<span class='discuss_idea_"+idea.id+"_count note'>" + (idea.discuss > 0 ? "+" + idea.discuss : "") + "</span> ";
		html += " ";
	}
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
	var numCategories = 0;
	var numSubcategories = 0;
	for (var i in displayedCategories) {
		numCategories++;
		for (var j in displayedCategories[i]["subcategories"]) {
			numSubcategories++;
		}
	}
	numCategories += numSubcategories;
	
	if (numCategories>0) {
		stats.push(numCategories + (numCategories == 1 ? " category" : " categories"));
	}
	
	// number of uncategorized ideas (if any)
	if (categorizedIdeas.length>0 && uncategorizedIdeas.length > 0) {
		stats.push(uncategorizedIdeas.length + (uncategorizedIdeas.length == 1? " uncategorized note" : " uncategorized notes"));
	}
		
	var html = stats.length > 0 ? "(" + stats.join(", ") + ")" : ""
	$("#question_stats").html(html);
}

function getMinMaxCategories(categories) {
	var minCategory = null;
	var maxCategory = null;
	for (var i in categories) {
		var category = categories[i];
		if (!minCategory || (categoryCounts[category] < categoryCounts[minCategory])) {
			minCategory = category;
		}
		if (!maxCategory || (categoryCounts[category] > categoryCounts[maxCategory])) {
			maxCategory = category;
		}										
	}
	return { "min":minCategory, "max":maxCategory };
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
			var word = cleanWord(words[j]);
			if (word!="" && !isStopWord(word)) {
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
	updateStatus();
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