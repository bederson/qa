// Copyright 2014 Ben Bederson - http://www.cs.umd.edu/~bederson
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

var OFFLINE = false;

var SHOW_TAGCLOUDS = true;
var MIN_TAGCLOUD_ITEM_COUNT = 5;
var MAX_CLOUD_HEIGHT = 800;
var DEFAULT_IDEA_INDENT = 20; // pixels

var SORT_BY_NAME = "name";
var SORT_BY_COUNT = "count";

var DEFAULT_SHOW_SUBCATEGORIES = false;
var DEFAULT_SHOW_IN_SINGLE_CATEGORY = true;
var DEFAULT_SHOW_DISCUSS_ONLY = false;
var HIGHLIGHT_DISCUSS = true;

var showSubcategories = DEFAULT_SHOW_SUBCATEGORIES;
var showInSingleCategory = DEFAULT_SHOW_IN_SINGLE_CATEGORY;
var showDiscussOnly = DEFAULT_SHOW_DISCUSS_ONLY;

var primaryCategories = {};
var subcategories = [];
var hasSubcategories = false;
var hasAlsoIn = false;

var question = null;
var categorizedIdeas = [];
var uncategorizedIdeas = [];
var numIdeas = 0;
var displayedCategories = {};
var categoryCounts = {};
var adminStats = null;
var isQuestionAuthor = false;
   
$(document).ready(function() {
	$("#nest_categories_cb").prop("checked", showSubcategories);
	$("#single_category_cb").prop("checked", showInSingleCategory);
	$("#discuss_only_cb").prop("checked", showDiscussOnly);
	
	initEventHandlers();

	if ($("#msg").html()) {
		return;
	}

	initChannel(onChannelOpen);
		
	// will only be shown for instructor
	// for questions that are not finished yet
	if (SHOW_START_URL_BY_DEFAULT) {
		$("#start_url_area").show();
	}
	else {
		$("#show_start_url").show();
	}
	
	$("#page_content").show();
});

function onChannelOpen() {
	loadResults();
		
	if (!jQuery.browser.mobile) {
		$("#admin_buttons").show();
	}
	
	$("#admin_button").click(function() {
		redirectToAdminPage(question_id);
	});
	
	$("#sort_by").change(function() {	
		displayIdeas();
	});
		
	$("#nest_categories_cb").click(function() {
		showSubcategories = $(this).is(":checked");
		initDisplayCategories();
		displayIdeas();
	});
		
	$("#single_category_cb").click(function() {
		showInSingleCategory = $(this).is(":checked");
		initDisplayCategories();
		displayIdeas();
	});

	$("#discuss_only_cb").click(function() {
		showDiscussOnly = $(this).is(":checked");
		displayIdeas();
	});
}
	
function loadResults() {	
	var test = getURLParameter("test");

	var data = {
		"request": "ideas",
		"group_by": "category",
		"question_id": question_id,
		"discuss": SHOW_DISCUSS_BUTTONS ? "1" : "0",
		"test": test!=null && test=="1" ? "1" : "0"
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		categorizedIdeas = results.categorized;
		uncategorizedIdeas = results.uncategorized;
		numIdeas = results.count;
		isQuestionAuthor = results.is_question_author;
		updateStatus();

		// initialize discussion flags
		initDiscussFlags(results.discuss_flags, true, false, onClickDiscuss);
				
		// initialize category counts and master list of subcategories
		categoryCounts = {};
		subcategories = [];
		for (var i in categorizedIdeas) {
			var category = categorizedIdeas[i].category;
			var categoryIdeas = categorizedIdeas[i].ideas;
			var categorySubcategories = categorizedIdeas[i].subcategories;
			categoryCounts[category] = categoryIdeas.length;
			for (var j in categorySubcategories) {
				var subcategory = categorySubcategories[j];
				if ($.inArray(subcategory, subcategories) == -1) {
					subcategories.push(subcategory);
				} 
			}
		}	
		hasSubcategories = subcategories.length > 0;
		
		// initialize data structure used to display results
		initDisplayCategories();
			
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
	newIdeaHtml += "<div id='new_ideas'></div>";
	newIdeaHtml += "</td>";
	newIdeaHtml += "</tr>";
	newIdeaHtml += "</table>";
			
	// added hide + fadeIn because html change was "jumpy" otherwise
	$("#ideas").hide();			
	$("#ideas").html(newIdeaHtml + html).fadeIn("fast");
	initIdeaHandlers();
	
	// show/hide controls
	// initialize after writing idea html since some status variables updated while writing
	var hasCategories = categorizedIdeas.length > 0;
	showHide($("#sort_control"), hasCategories);
	showHide($("#nest_categories_control"), hasSubcategories);
	showHide($("#single_category_control"), hasAlsoIn);
	showHide($("#discuss_only_control"), true); // TODO/FIX: check if any discuss flags
	$("#display_control_area").show();

	// BEHAVIOR: only display tag clouds when cascade is complete and categories expanded	
	drawClouds(sortIndices);

	// TOOD/FIX	
	// need to test w/ subcategories
	// test behavior when only discuss items shown
	// better open/close images
	$(".category_title").click(function() {
		var categoryContent = $(this).next();
		if (categoryContent.is(':visible')) {
			collapse($(this));
		}
		else {
			// expand category and any subcategories too
			var parentDiv = $(this).parent();
			parentDiv.find(".category_title").each(function(index) {
				expand($(this));
			});
		}
	});
}

function categoryGroupAsHtml(categoryGroup, id) {
	var category = categoryGroup.category;
	var ideas = categoryGroup.ideas;
	var sameAs = isDefined(categoryGroup.sameas) ? "Similar to: "+categoryGroup.sameas : "";
	var categoryCount = categoryGroup.count;	
	var hiddenCount = 0;
	
	// check if currently collapsed or expanded (could have been a subcategory previously)
	var categoryExpanded = true;
	var categoryDiv = $("#category_"+id);
	var subcategoryDiv = $(".subcategory").first(); // do not have way to get exact subcategory
	if (categoryDiv.length) {
		categoryExpanded = categoryDiv.children(".category_responses").is(":visible");
	}
	else if (subcategoryDiv.length) {
		categoryExpanded = subcategoryDiv.children(".category_responses").is(":visible");
	}
	
	var html = "";
	if (categoryCount > 0) {
		html += "<table style='width: 100%'>";
		html += "<tr>";
		html += "<td style='width: 50%'>";
		
		// an empty category means the items have not been categorized yet
		html += "<div id='category_"+id+"' class='category'>";
		if (category != "") {
			html += "<div class='category_title spaceabove spacebelow'>";
			html += "<img class='category_open_close' src='" + (categoryExpanded ? "/images/arrow-down.gif" : "/images/arrow-up.gif") +"' /> "; 	
			html += category + "&nbsp;<span class='note'>(" + categoryCount + ") " + sameAs + "</span>";
			html += "</div>";		
		}
		html += "<div class='category_responses' " + (!categoryExpanded ? "style='display:none'": "") + ">";
		for (var i in ideas) {
			html += ideaAsHtml(ideas[i], id, null, category != "" ? DEFAULT_IDEA_INDENT : 0);
			if (showDiscussOnly && getDiscussFlagCount(ideas[i].id) == 0) {
				hiddenCount++;
			}
		}
		html += "</div>";
		html += "</div>";
		
		if (showSubcategories && isDefined(categoryGroup.subcategories) && categoryGroup.subcategories.length > 0) {
			for (var i in categoryGroup.subcategories) {
				var subcategoryGroup = categoryGroup.subcategories[i];
				var subcategory = subcategoryGroup.category;
				var subcategoryIdeas = subcategoryGroup.ideas;
				var subcategorySameAs = subcategoryGroup.sameas ? "Similar to: "+subcategoryGroup.sameas : "";	
				var subcategoryCount = subcategoryGroup.count;
		
				// check if currently collapsed or expanded
				var subcategoryExpanded = categoryExpanded;
				var subcategoryDiv = $("#subcategory_"+i+".category_" + id);
				if (subcategoryDiv.length) {
					subcategoryExpanded = subcategoryDiv.children(".category_responses").is(":visible");
				}
	
				var customStyles = "style='margin-left:" + (DEFAULT_IDEA_INDENT+10) + "px'";
				html += "<div id='subcategory_" + i + "' class='subcategory category_" + id + "'>";
				html += "<div class='category_title spaceabove spacebelow' " + customStyles + ">";
				html += "<img class='category_open_close' src='" + (subcategoryExpanded ? "/images/arrow-down.gif" : "/images/arrow-up.gif") +"' /> "; 	
				html += subcategory + "&nbsp;<span class='note'>(" + subcategoryCount + ") " + subcategorySameAs + "</span>";				
				html += "</div>";
				html += "<div class='category_responses' " + (!subcategoryExpanded ? "style='display:none'": "") + ">";
				for (var j in subcategoryIdeas) {
					html += ideaAsHtml(subcategoryIdeas[j], id, category, (DEFAULT_IDEA_INDENT*2)+10);
					html += "<div style='clear:both'></div>";
					if (showDiscussOnly && getDiscussFlagCount(subcategoryIdeas[j].id) == 0) {
						hiddenCount++;
					}
				}
				html += "</div>";
				html += "</div>";
				html += "<div style='clear:both'></div>";
			}
		}	
		
		var hiddenIdeasExist = showDiscussOnly && hiddenCount > 0;
		var hiddenMessage = "<span class=\"note\"><em>Responses not flagged to discuss are hidden</em></span>";
		html += "<div id='category_" + id + "_ellipses" + "' style='" + (!hiddenIdeasExist ? "display:none;" : "") +"color:#888; margin-left: " + (DEFAULT_IDEA_INDENT+10) + "px'><span title='" + hiddenMessage + "'>...</span></div>";
							
		html += "</td>";
		if (!jQuery.browser.mobile) {
			html += "<td style='width: 50%' valign='top'>";
			html += "<div id='cloud_"+id+"' class='cloud'></div>";
			html += "</td>";
		}
		html += "</tr>";
		html += "</table>";
		html += "</div>";
	}
		
	return html;
}
				
function ideaAsHtml(idea, rootCategoryId, parent, indent) {
	parent = isDefined(parent) ? parent : null;
	indent = isDefined(indent) ? indent : 0;
	
	var discussCount = getDiscussFlagCount(idea.id);
	var hideIdea = showDiscussOnly && discussCount == 0;
	
	var alsoIn = idea.also_in ? $.extend(true, [], idea.also_in) : [];
	if (alsoIn.length > 0) {
		var alsoInParentIndex = alsoIn.indexOf(parent);
		if (alsoInParentIndex != -1) {
			alsoIn.splice(alsoInParentIndex, 1);
		}
	}
	if (alsoIn.length > 0) {
		hasAlsoIn = true;
	}
	
	var highlightClass = HIGHLIGHT_DISCUSS && getDiscussFlagCount(idea.id) > 0 ? " discuss_highlight" : "";
	var html = "<div class='left idea idea_" + idea.id + " category_" + rootCategoryId + highlightClass + "' style='margin-left:"+indent+"px;"
	html += hideIdea ? "display:none" : "";
	html += "'>";	
	html += discussButtonHtml(idea.id);
	html += "<div style='margin-left:40px;'>";
	html += idea.idea;

	if (idea.author) {
		html += "</br>";
		html += "<span class='author'>";
		html += "-- "; 
		html += getUserHtml(idea.author, idea.author_identity);
		html += "</span>";
	}
	
	html += "</div>";
	html += "</div>";
	return html;	
}

function expand(categoryTitleDiv) {
	var categoryImg = $(categoryTitleDiv).children(".category_open_close");
	var categoryContent = $(categoryTitleDiv).next();
	categoryImg.attr("src", "/images/arrow-down.gif");
	categoryContent.fadeIn("fast", function() {
		showHideClouds();
	});
}

function expandAll() {
	$(".category_open_close").attr("src", "/images/arrow-down.gif");
	$(".category_responses").show();
	$(".cloud").show();
}

function collapse(categoryTitleDiv) {
	var categoryImg = $(categoryTitleDiv).children(".category_open_close");
	var categoryContent = $(categoryTitleDiv).next();
	categoryImg.attr("src", "/images/arrow-up.gif");
	categoryContent.fadeOut("fast", function() {
		showHideClouds();
	});	
}

function collapseAll() {
	$(".category_open_close").attr("src", "/images/arrow-up.gif");
	$(".category_responses").hide();
	$(".cloud").hide();
}

function initIdeaHandlers(ideaId) {
	// init discuss button tooltips, event handlers
	if (question.active) {
		initDiscussButtons(question.id, client_id, ideaId);
	}
	
	// init any other tooltips in idea
	$('[title!=""]').qtip({ 
		style: { 
			tip: { corner: true }, 
			classes: 'qtip-rounded tooltip' 
		}
	});
	
	$("#expand_all_link").click(function() {
		expandAll();
	});
	
	$("#collapse_all_link").click(function() {
		collapseAll();
	});
}

function updateStats() {
	var stats = [];

	// number of ideas
	var stat = numIdeas == 0 ? "No notes yet" : (numIdeas == 1 ? "1 response" : numIdeas + " responses");
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
		stats.push(uncategorizedIdeas.length + (uncategorizedIdeas.length == 1? " uncategorized response" : " uncategorized responses"));
	}
		
	var html = stats.length > 0 ? "(" + stats.join(", ") + ")" : ""
	$("#question_stats").html(html);
}

function getUserHtml(displayName, realIdentity, customClass) {
	var realIdentity = isDefined(realIdentity) && realIdentity != null ? realIdentity : "";
	var html = "<span";
	html += isDefined(customClass) ? " class='" + customClass + "'" : "";
	var isIdentityHidden = realIdentity != "" && realIdentity != displayName;
	if (isIdentityHidden) {
		html += " title='" + realIdentity + "' ";
	}
	html += ">" + displayName + (isIdentityHidden ? "*" : "") + "</span>";
	return html;
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

function isCategoryFullyExpanded(categoryId) {
	var isFullyExpanded = $("#category_"+categoryId).children(".category_responses").is(":visible");
	$(".subcategory").each(function(index) {
		if ($(this).hasClass("category_"+categoryId)) {
			if (!$(this).children(".category_responses").is(":visible")) {
				isFullyExpanded = false;
				return false;
			}
		}
	});
	return isFullyExpanded;
}

//=================================================================================
// Cloud Display
//=================================================================================

function showHideClouds() {
	$(".category").each(function() {
		var categoryId = $(this).attr("id").replace("category_","");
		var isFullyExpanded = isCategoryFullyExpanded(categoryId);
		showHide($("#cloud_"+categoryId), isFullyExpanded);
	});
}

function drawClouds(sortIndices) {
	if (SHOW_TAGCLOUDS && question.cascade_complete && !jQuery.browser.mobile) {
		for (var i=0; i<sortIndices.length; i++) {
			var j = sortIndices[i];
			var category = displayedCategories[j].category;
			var ideas = displayedCategories[j].ideas;
			var isRootCategory = !showSubcategories || ($.inArray(category, subcategories) == -1);			
			if (isRootCategory) {
				var isFullyExpanded = isCategoryFullyExpanded(j);
				showHide($("#cloud_"+j), isFullyExpanded);
				displayCloud(displayedCategories[j].ideas.concat(displayedCategories[j].moreideas), j);
			}
		}
		
		if (uncategorizedIdeas.length > 0) {
			displayCloud(uncategorizedIdeas, categorizedIdeas.length+1);
		}
	}
}

// TODO: improve css for div.jqcloud
function displayCloud(group, id) {
	var div = $("#cloud_"+id);
	
	// do not show tag clouds for groups with < MIN_TAGCLOUD_ITEM_COUNT items
	// or if only discuss items shown
	if (group.length < MIN_TAGCLOUD_ITEM_COUNT || showDiscussOnly) {
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

//=================================================================================
// Results Data Structures
//=================================================================================

function initDisplayCategories() {
	// initialize primary categories for ideas where a primary category is where
	// an item should be displayed in if it can only be displayed in a *single* category
	initPrimaryCategories();
		
	displayedCategories = {};
	for (var i in categorizedIdeas) {
		var categoryGroup = categorizedIdeas[i];
		var category = categoryGroup.category;
		var categoryIdeas = categoryGroup.ideas;
		var categorySubcategories = isDefined(categoryGroup.subcategories) ? categoryGroup.subcategories : [];
		var categorySameAs = categoryGroup.same_as;
		
		var isRootCategory = !showSubcategories || $.inArray(category, subcategories) == -1;		
		if (isRootCategory) {
			var count = 0;
			for (var j in categoryIdeas) {
				var idea = categoryIdeas[j];
				
				// skip if displaying subcategories and this idea is in a subcategory
				var skip = false;
				var alsoIn = isDefined(idea.also_in) ? idea.also_in : [];
				if (showSubcategories && alsoIn.length > 0 && categorySubcategories.length > 0) {
					var isIdeaInSubcategory = intersection(alsoIn, categorySubcategories).length > 0;
					skip = isIdeaInSubcategory;
				}
			
				// skip if only displaying idea in single category and this is not the primary category
				if (showInSingleCategory && isDefined(primaryCategories[idea.id]) && primaryCategories[idea.id] != category) {
					skip = true;
				}

				// add idea to root category
				if (!skip) {
					if (isUndefined(displayedCategories[i])) {
						// ideas + moreideas = unique list of ideas contained in root category
						// moreideas is a list of ideas from subcategories that are not in the root category
						displayedCategories[i] = { "category": category, "ideas": [], "moreideas": [], "subcategories": [], "sameas": categorySameAs, "count": 0 };
					}
					displayedCategories[i]["ideas"].push(idea);
					displayedCategories[i]["count"]++;
					count++;
				}
			}
		}
		
		// display subcategories (if any)
		if (isRootCategory && showSubcategories) {
			var subcategoryIndex = 0;
			for (var j=0; j<categorySubcategories.length; j++) {
				// check if subcategory found
				// if not, it may have already been merged with another category (if it is a duplicate)
				var subcategoryGroup = getCategoryGroup(categorySubcategories[j]);
				if (subcategoryGroup) {
					var subcategory = subcategoryGroup.category;
					var subcategoryIdeas = subcategoryGroup.ideas;
					var subcategorySameAs = subcategoryGroup.same_as;
					var count = 0;
					for (var k=0; k<subcategoryIdeas.length; k++) {
						var subcategoryIdea = subcategoryIdeas[k];
						
						// skip adding this idea to this subcategory if ideas are only to be shown in one category,
						// and this subcategory is not the primary category for this idea
						var skip = showInSingleCategory && isDefined(primaryCategories[subcategoryIdea.id]) && (primaryCategories[subcategoryIdea.id] != subcategory);
						
						// add this idea to this subcategory
						if (!skip) {
							// add subcategory idea to moreideas if not in ideas already										
							if (!doesIdeaListContain(displayedCategories[i]["ideas"], subcategoryIdea)) {
								displayedCategories[i]["moreideas"].push(subcategoryIdea);	
							}
							// update total count for root category
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
	return displayedCategories;
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
	for (var i=0; i<sortTuples.length; i++) {
		sortIndices.push(sortTuples[i][0]);
	}
	return sortIndices;
}

function initPrimaryCategories() {
	// find primary categories for ideas that appear in multiple categories
	// ideas only in single category not included
	primaryCategories = {};
	for (var i=0; i<categorizedIdeas.length; i++) {
		var category = categorizedIdeas[i].category;
		var ideas = categorizedIdeas[i].ideas;
		for (var j=0; j<ideas.length; j++) {
			var idea = ideas[j];
			if (isUndefined(primaryCategories[idea.id])) {
				var ideaAlsoIn = idea.also_in ? $.extend(true, [], idea.also_in) : [];
				if (ideaAlsoIn.length > 0) {
					// if this idea is in other categories, add this category to list
					ideaAlsoIn.push(category);
						
					// find subcategories this idea is in
					var ideaSubcategories = subcategories.length > 0 ? intersection(ideaAlsoIn, subcategories) : [];
							
					// find primary category for this idea
					// * if idea is in a subcategory, pick the smallest one
					// * otherwise, pick the smallest root category
					// TODO/FIX: consider whether primary category should be smallest or largest
					// TODO/FIX: priority should be given to categories with the most fit votes (if k2>1)
					var primaryCategory = null;					
					if (ideaSubcategories.length > 0) {
						var minMaxSubcategories = getMinMaxCategories(ideaSubcategories);
						primaryCategory = minMaxSubcategories.min;
					}
					else {
						var ideaRootCategories = ideaSubcategories.length > 0 ? difference(ideaAlsoIn, ideaSubcategories) : ideaAlsoIn;
						var minMaxRootCategories = getMinMaxCategories(ideaRootCategories);
						primaryCategory =  minMaxRootCategories.min;
					}
					primaryCategories[idea.id] = primaryCategory;
				}
			}			
		}
	}
	return primaryCategories;
}

function getMinMaxCategories(categories) {
	var minCategory = null;
	var maxCategory = null;
	for (var i=0; i<categories.length; i++) {
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

function getCategoryGroup(category) {
	var group = null;
	for (var i=0; i<categorizedIdeas.length; i++) {
		if (categorizedIdeas[i].category == category) {
			group = categorizedIdeas[i];
			break;
		}
	}
	return group;
}

function doesIdeaListContain(ideaList, idea) {
	var found = false;
	for (var i=0; i<ideaList.length; i++) {
		if (ideaList[i].id == idea.id) {
			found = true;
			break;
		}
	}
	return found;
}

function initEventHandlers() {
	$("#hide_start_url").click(function() {
		$("#start_url_area").hide();
		$("#show_start_url").show();
		return false;
	});

	$("#show_start_url").click(function() {
		$("#show_start_url").hide();
		$("#start_url_area").show();
		return false;
	});
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	var idea = data.idea;
	uncategorizedIdeas.push(idea);
	numIdeas++;
	var newHtml = ideaAsHtml(idea, categorizedIdeas.length+1);
	$("#new_ideas").html(newHtml + $("#new_ideas").html());
	initIdeaHandlers(idea.id);
	updateStats();
}

function handleEnable(data) {
	question.active = 1;
	// TODO: would be better to only update data that has changed
	window.location.reload();
}

function handleDisable(data) {
	question.active = 0;
	// TODO: would be better to only update data that has changed
	window.location.reload();
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

function handleDiscussIdea(data) {
	if (data.flag.question_id == question.id) {
		addRemoveDiscussFlag(data.flag, data.op == "discuss_idea");
	}
}

function onClickDiscuss(questionId, ideaId, add) {
	if (questionId == question.id) {
		var ideaSelector = $(".idea_"+ideaId);
		var count = getDiscussFlagCount(ideaId);
		
		if (HIGHLIGHT_DISCUSS) {
			if (count > 0 && !ideaSelector.hasClass("discuss_highlight")) {
				ideaSelector.addClass("discuss_highlight");
			}
			else if (count == 0) {
				ideaSelector.removeClass("discuss_highlight");
			}
		}
		
		if (showDiscussOnly) {
			showHide(ideaSelector, count>0);
			ideaSelector.each(function() {
				var categoryClass = null;
				var ideaClasses = $(this).attr('class').split(' ');
				for (var i in ideaClasses) {
					if (ideaClasses[i].indexOf("category_") != -1) {
						categoryClass = ideaClasses[i]; 
						break;
					}
				}
				
				if (categoryClass) {
					var visibleCount = $("."+categoryClass+":visible").length;
					var hiddenCount = $("."+categoryClass+":hidden").length;
					showHide($("#"+categoryClass+"_ellipses"), hiddenCount > 0);
				}
			});
		}
	}
}

function handleLogout(data) {
	redirectToLogout(question_id);
}