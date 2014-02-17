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
var NONE_CATEGORY_LABEL = "NONE";

var SORT_BY_NAME = "name";
var SORT_BY_COUNT = "count";

var DEFAULT_SHOW_SUBCATEGORIES = false;
var DEFAULT_SHOW_IN_SINGLE_CATEGORY = true;
var DEFAULT_SHOW_DISCUSS_ONLY = false;

var EXPANDED_IMAGE = "/images/control_down.png";
var COLLAPSED_IMAGE = "/images/control_right.png"

var showSubcategories = DEFAULT_SHOW_SUBCATEGORIES;
var showInSingleCategory = DEFAULT_SHOW_IN_SINGLE_CATEGORY;
var showDiscussOnly = DEFAULT_SHOW_DISCUSS_ONLY;

var hasIdeasInMultipleCategories = false;
var primaryCategories = {};
var subcategories = [];
var ideasToDiscuss = [];
var ideaAuthors = {};

var question = null;
var categoryGroups = [];
var uncategorizedIdeas = [];
var numIdeas = 0;
var displayedCategories = {};
var uncategorizedCategory = {};
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
		
	$("#expand_all_link").click(function() {
		expandAll();
	});
	
	$("#collapse_all_link").click(function() {
		collapseAll();
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
		// if show discuss only, force all categories to be expanded
		showDiscussOnly = $(this).is(":checked");
		displayIdeas(showDiscussOnly);
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
		categoryGroups = results.categorized;
		uncategorizedIdeas = results.uncategorized;
		numIdeas = results.count;
		isQuestionAuthor = results.is_question_author;
		$("#inactive").html(!question.active ? "INACTIVE" : "");
		
		// initialize discussion flags
		initDiscussFlags(results.discuss_flags, true, false, onClickDiscuss);
				
		// initialize category counts and master list of subcategories
		categoryCounts = {};
		subcategories = [];
		for (var i in categoryGroups) {
			var category = categoryGroups[i].category;
			var categoryIdeas = categoryGroups[i].ideas;
			var categorySubcategories = categoryGroups[i].subcategories;
			categoryCounts[category] = categoryIdeas.length;
			for (var j in categorySubcategories) {
				var subcategory = categorySubcategories[j];
				if ($.inArray(subcategory, subcategories) == -1) {
					subcategories.push(subcategory);
				} 
			}
		}			
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

function displayIdeas(forceAllExpanded) {
	forceAllExpanded = isDefined(forceAllExpanded) ? forceAllExpanded : false;
		
	// init data collection: ideas marked to discuss, response authors
	ideasToDiscuss = [];
	ideaAuthors = {};

	// categorized html
	// TODO: sort subcategories
	var html = "";
	var sortIndices = getSortIndices();
	for (var i=0; i<sortIndices.length; i++) {
		var index = sortIndices[i];
		html += categoryGroupAsHtml(displayedCategories[index], index, forceAllExpanded);
	}
	
	// uncategorized html
	if (uncategorizedIdeas.length > 0) {
		html += categoryGroupAsHtml(uncategorizedCategory, categoryGroups.length, forceAllExpanded);
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
	
	// update stats
	updateStats();
	
	// show/hide controls
	// initialize after writing idea html since some status variables updated while writing
	var inProgress = question.active && !question.cascade_complete;
	var hasIdeas = numIdeas > 0;
	var hasCategories = categoryGroups.length > 0;
	var hasSubcategories = subcategories.length > 0;
	var hasIdeasToDiscuss = ideasToDiscuss.length > 0;
	$("#idea_link").attr("href", getNotesPageUrl(question.id));
	showHide($("#idea_link_area"), inProgress);
	showHide($("#expand_collapse_controls"), hasCategories);
	showHide($("#sort_control"), hasCategories);
	showHide($("#nest_categories_control"), hasSubcategories);
	showHide($("#single_category_control"), hasIdeasInMultipleCategories);
	showHide($("#discuss_only_control"), hasIdeas);
	enableDisableDiscussOption(hasIdeasToDiscuss);
	showHide($("#display_control_area"), hasIdeas);

	// BEHAVIOR: only display tag clouds when categories expanded
	drawClouds(sortIndices);

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

function updateStats() {
	var numAuthors = numKeys(ideaAuthors);
	var html = numIdeas > 0 ? numIdeas + (numIdeas == 1 ? " response" : " responses") : "No responses yet";
	html += numAuthors > 0 ? " from " + numAuthors + (numAuthors == 1 ? " author" : " authors") : "";
	if (showDiscussOnly) {
		html += " <strong class='small grey'>** ONLY RESPONSES TO DISCUSS SHOWN **";
	}
	$("#question_stats").html(html);
}

function categoryGroupAsHtml(categoryGroup, id, forceExpanded) {
	forceExpanded = isDefined(forceExpanded) ? forceExpanded : false;

	var category = categoryGroup.category;
	var categoryLabel = category != NONE_CATEGORY_LABEL ? capitalizeFirst(category) : category;
	var ideas = categoryGroup.ideas;
	var sameAs = isDefined(categoryGroup.same_as) && categoryGroup.same_as.length > 0 ? "Similar to: "+forAll(categoryGroup.same_as, capitalizeFirst).join(", ") : "";
	var categoryCount = categoryGroup.count;
	var discussIdeaCount = isDefined(categoryGroup.discuss_count) ? categoryGroup.discuss_count : 0;	
 
	// check if currently collapsed or expanded (could have been a subcategory previously)
	var categoryExpanded = true;
	if (!forceExpanded) {
		var categoryDiv = $("#category_"+id);
		var subcategoryDiv = $(".subcategory").first(); // do not have way to get exact subcategory
		if (categoryDiv.length) {
			categoryExpanded = categoryDiv.children(".category_responses").is(":visible");
		}
		else if (subcategoryDiv.length) {
			categoryExpanded = subcategoryDiv.children(".category_responses").is(":visible");
		}
	}
	
	var html = "<table style='width:100%'>";
	html += "<tr>";
	html += "<td style='width:50%'>";
	if (categoryCount > 0) {		
		var ideasHtml = "<div class='category_responses spacebelow' " + (!categoryExpanded ? "style='display:none'": "") + ">";
		for (var i in ideas) {
			ideasHtml += ideaAsHtml(ideas[i], id, null, category != "" ? DEFAULT_IDEA_INDENT : 0);
		}
		ideasHtml += "<div style='clear:both'></div>";
		ideasHtml += "</div>";
		
		// an empty category means the items have not been categorized yet
		html += "<div id='category_"+id+"' class='category'>";
		if (categoryGroups.length > 0) {
			// TODO/FIX: would prefer to hide overflow and add ellipses but need to convert layout to use divs			
			var countHtml = !showDiscussOnly ? categoryCount : discussIdeaCount;
			html += "<div class='category_title spacebelow'>";
			html += "<img class='category_open_close' src='" + (categoryExpanded ? EXPANDED_IMAGE : COLLAPSED_IMAGE) +"' /> ";
			html += "<span style='font-weight: bold !important; font-size: 1.0em;'>" + categoryLabel + "</span> "; 	
			html += "<span class='note'>(<span class='count'>" + countHtml + "</span>)</span> ";
			html += "<span class='note'>" + sameAs + "</span>";
			html += "</div>";
		}
		html += ideasHtml;
		html += "</div>";
		
		if (showSubcategories && isDefined(categoryGroup.subcategories) && categoryGroup.subcategories.length > 0) {
			var sortIndicesForSubcategories = getSortIndices(categoryGroup.subcategories);
			for (var i in sortIndicesForSubcategories) {
				var index = sortIndicesForSubcategories[i];
				var subcategoryGroup = categoryGroup.subcategories[index];
				var subcategory = subcategoryGroup.category;
				var subcategoryLabel = capitalizeFirst(subcategoryGroup.category);
				var subcategoryIdeas = subcategoryGroup.ideas;
				var subcategorySameAs = subcategoryGroup.same_as.length > 0 ? "Similar to: "+forAll(subcategoryGroup.same_as, capitalizeFirst).join(", ") : "";	
				var subcategoryCount = subcategoryGroup.count;
				var subcategoryDiscussCount = 0;
		
				// check if currently collapsed or expanded
				var subcategoryExpanded = categoryExpanded;
				if (!forceExpanded) {
					var subcategoryDiv = $("#subcategory_"+i+".category_" + id);
					if (subcategoryDiv.length) {
						subcategoryExpanded = subcategoryDiv.children(".category_responses").is(":visible");
					}
				}
	
				var ideasHtml = "<div class='category_responses' " + (!subcategoryExpanded ? "style='display:none'": "") + ">";
				for (var j in subcategoryIdeas) {				
					ideasHtml += ideaAsHtml(subcategoryIdeas[j], id, category, (DEFAULT_IDEA_INDENT*2)+10);
					ideasHtml += "<div style='clear:both'></div>";
					subcategoryDiscussCount += getDiscussFlagCount(subcategoryIdeas[j].id) > 0 ? 1 : 0;
				}
				ideasHtml += "</div>";
				
				// TODO/FIX: would prefer to hide overflow and add ellipses but need to convert layout to use divs		
				var customStyles = "style='margin-left:" + (DEFAULT_IDEA_INDENT+10) + "px'";
				var countHtml = !showDiscussOnly ? subcategoryCount : subcategoryDiscussCount;
				html += "<div id='subcategory_" + i + "' class='subcategory category_" + id + "'>";
				html += "<div class='category_title spaceabove spacebelow' " + customStyles + ">";
				html += "<img class='category_open_close' src='" + (subcategoryExpanded ? EXPANDED_IMAGE : COLLAPSED_IMAGE) +"' /> "; 	
				html += "<span style='font-weight: bold; font-size:1.0em'>" + subcategoryLabel + "</span> ";
				html += "<span class='note'>(<span class='count'>" + countHtml + "</span>)</span> ";
				html += "<span class='note'>" + subcategorySameAs + "</span>";
				html += "</div>";
				html += ideasHtml;
				html += "</div>";
			}
		}				
		html += "</td>";
		
		html += "<td style='width:50%'>";
		html += "<div id='cloud_"+id+"' class='cloud'></div>";
		html += "</td>";
		
		html += "</tr>";
		html += "</table>";
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
		hasIdeasInMultipleCategories = true;
	}
	
	if (discussCount > 0 && $.inArray(idea.id, ideasToDiscuss) == -1) {
		ideasToDiscuss.push(idea.id);
	}
	
	var highlightClass = getDiscussFlagCount(idea.id) > 0 ? " discuss_highlight" : "";
	var html = "<div class='left idea idea_" + idea.id + " category_" + rootCategoryId + highlightClass + "' style='margin-left:"+indent+"px;";
	html += hideIdea ? "display:none" : "";
	html += "'>";	
	html += discussButtonHtml(idea.id);
	html += "<div style='margin-left:40px;'>";
	html += capitalizeFirst(idea.idea);

	if (idea.author) {
		// only display author if authentication used
		if (question.authentication_type != NO_AUTHENTICATION) {
			html += "</br>";
			html += "<span class='author'>";
			html += "-- "; 
			html += getUserHtml(idea.author, idea.author_identity);
			html += "</span>";
		}
		
		if (!(idea.user_id in ideaAuthors)) {
			ideaAuthors[idea.user_id] = { "author": idea.author, "author_identity": idea.author_identity };
		}
	}

	html += "</div>";
	html += "</div>";
	return html;	
}

function expand(categoryTitleDiv) {
	var categoryDiv = categoryTitleDiv.parent();
	var categoryImg = categoryTitleDiv.children(".category_open_close");
	var categoryContent = categoryDiv.children(".category_responses");
	categoryImg.attr("src", EXPANDED_IMAGE);
	categoryContent.fadeIn("fast", function() {
		var categoryId = getCategoryId(categoryDiv);
		if (categoryId) {
			drawCloud(categoryId);
		}
	});
}

function expandAll() {
	$(".category_open_close").attr("src", EXPANDED_IMAGE);
	$(".category_responses").show();
	drawClouds(getSortIndices());
}

function collapse(categoryTitleDiv) {
	var categoryDiv = categoryTitleDiv.parent();
	var categoryDivId = categoryDiv.attr("id");
	var categoryImg = categoryTitleDiv.children(".category_open_close");
	var categoryContent = categoryDiv.children(".category_responses");
	categoryImg.attr("src", COLLAPSED_IMAGE);
	categoryContent.fadeOut("fast", function() {
		var categoryId = getCategoryId(categoryDiv);
		if (categoryId) {
			$("#cloud_"+categoryId).hide();
		}
	});
	
	$("."+categoryDivId+".subcategory").each(function(index) {
		var subcategoryImg = $(this).find(".category_open_close");
		var subcategoryContent = $(this).find(".category_responses");
		subcategoryImg.attr("src", COLLAPSED_IMAGE);
		subcategoryContent.fadeOut("fast");
	});
}

function collapseAll() {
	$(".category_open_close").attr("src", COLLAPSED_IMAGE);
	$(".category_responses").hide();
	$(".cloud").hide();
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

function isRootCategoryDiv(div) {
	var divId = div.attr("id");
	return divId && divId.indexOf("category_") == 0;
}

function isUncategorizedCategoryDiv(div) {
	var categoryId = getCategoryId(div);
	return categoryId && parseInt(categoryId)==categoryGroups.length;
}

function isSubcategoryDiv(div) {
	var divId = div.attr("id");
	return divId && divId.indexOf("subcategory_") == 0;
}

function getCategoryId(div) {
	categoryId = null;
	if (isRootCategoryDiv(div)) {
		var divId = div.attr("id");
		categoryId = divId.replace("category_", "");
	}
	else if (isSubcategoryDiv(div)) {
		var divClasses = div.attr("class").split(" ");
		for (var i=0; i<divClasses.length; i++) {
			if (divClasses[i].indexOf("category_") == 0) {
				categoryId = divClasses[i].replace("category_", "");
				break;
			}
		}
	}
	return categoryId;
}

function getSubcategoryId(div) {
	subcategoryId = null;
	if (isSubcategoryDiv(div)) {
		var divId = div.attr("id");
		subcategoryId = divId.replace("subcategory_", "");
	}
	return subcategoryId;
}

function enableDisableDiscussOption(enable) {
	if (enable) {
		enableDisable($("#discuss_only_cb"), true);
		$("#discuss_only_control").removeClass("disabled");
		
	}
	else {
		enableDisable($("#discuss_only_cb"), false);
		if (!$("#discuss_only_control").hasClass("disabled")) {
			$("#discuss_only_control").addClass("disabled");
		}
	}
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
}

//=================================================================================
// Cloud Display
//=================================================================================

function drawClouds(sortIndices) {
	for (var i=0; i<sortIndices.length; i++) {
		var j = sortIndices[i];
		drawCloud(j);
	}
		
	if (uncategorizedIdeas.length > 0) {
		drawCloud(categoryGroups.length);
	}		
}

function drawCloud(categoryId) {
	if (SHOW_TAGCLOUDS && question.cascade_complete && !jQuery.browser.mobile) {
		var categoryId = parseInt(categoryId);
		if (categoryId < categoryGroups.length) {
			var category = displayedCategories[categoryId].category;
			var ideas = displayedCategories[categoryId].ideas;
			var isRootCategory = !showSubcategories || ($.inArray(category, subcategories) == -1);			
			if (isRootCategory) {
				displayCloud(displayedCategories[categoryId].ideas.concat(displayedCategories[categoryId].moreideas), categoryId);
			}
		}
		else if (categoryId == categoryGroups.length) {
			displayCloud(uncategorizedIdeas, categoryId);
		}
	}
	
}

// TODO: improve css for div.jqcloud
function displayCloud(group, id) {
	
	// create tag clouds for groups that are fully expanded, have >= MIN_TAGCLOUD_ITEM_COUNT items, 
	// and items are not filtered (discuss only)
	var wordList = [];
	var isFullyExpanded = isCategoryFullyExpanded(id);
	if (isFullyExpanded && group.length >= MIN_TAGCLOUD_ITEM_COUNT && !showDiscussOnly) {					
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
		for (var word in weights) {
			var item = { text: word, weight: weights[word] };
			wordList[i] = item;
			i += 1;
		}
	}

	// remove old jQCloud (if any) before creating new one
	var div = $("#cloud_"+id);
	var parent = div.parent();
	parent.html("<div id='cloud_"+id+"' class='cloud'></div>");
	div = $("#cloud_"+id);
	
	if (wordList.length > 0) {
		var height = div.parent().height();
		if (height > MAX_CLOUD_HEIGHT) {
			height = MAX_CLOUD_HEIGHT;
		}
		div.height(height);
		
		div.jQCloud(wordList);
		div.show();
	}
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
	for (var i in categoryGroups) {
		var categoryGroup = categoryGroups[i];
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
						displayedCategories[i] = { "category": category, "ideas": [], "moreideas": [], "subcategories": [], "same_as": categorySameAs, "count": 0, "discuss_count": 0 };
					}
					displayedCategories[i]["ideas"].push(idea);
					displayedCategories[i]["count"]++;
					displayedCategories[i]["discuss_count"] += getDiscussFlagCount(idea.id) > 0 ? 1 : 0;
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
							displayedCategories[i]["discuss_count"] += getDiscussFlagCount(subcategoryIdea.id) > 0 ? 1 : 0;
	
							// initialize subcategory
							if (count == 0) {	
								displayedCategories[i]["subcategories"].push({ "category":subcategory, "ideas":[], "same_as":subcategorySameAs, "count":0, "discuss_count":0 })
							}
							
							// update subcategory
							displayedCategories[i]["subcategories"][subcategoryIndex]["ideas"].push(subcategoryIdea);
							displayedCategories[i]["subcategories"][subcategoryIndex]["count"]++;
							displayedCategories[i]["subcategories"][subcategoryIndex]["discuss_count"] += getDiscussFlagCount(subcategoryIdea.id) > 0 ? 1 : 0;
							count++;
						}
					}
					subcategoryIndex++;
				}
			}
		}
	}
	
	uncategorizedCategory = { "category": NONE_CATEGORY_LABEL, "ideas": uncategorizedIdeas, "moreideas": [], "subcategories": [], "same_as": [], "count": uncategorizedIdeas.length, "discuss_count": 0 };
	for (var i in uncategorizedIdeas) {
		var idea = uncategorizedIdeas[i];	
		uncategorizedCategory["discuss_count"] += getDiscussFlagCount(idea.id) > 0 ? 1 : 0;
	}
}

function getSortIndices(categoriesToSort) {
	// TODO/FIX: uncategorized items (if any) are not included in sort indices
	var categoriesToSort = isDefined(categoriesToSort) ? categoriesToSort : displayedCategories;
	var sortBy = $("#sort_by").val();
	var sortTuples = [];
	
	if (sortBy == SORT_BY_NAME) {
		for (var i in categoriesToSort) {
			var sortValue = categoriesToSort[i].category;
			sortTuples.push([i, sortValue]);
		}
		sortTuplesAscending(sortTuples);
	}
	
	// SORT_BY_COUNT is default
	else {
		for (var i in categoriesToSort) {
			var sortValue = showDiscussOnly ? categoriesToSort[i].discuss_count : categoriesToSort[i].count;
			sortTuples.push([i, sortValue]);
		}
		sortTuplesDescending(sortTuples);
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
	for (var i=0; i<categoryGroups.length; i++) {
		var category = categoryGroups[i].category;
		var ideas = categoryGroups[i].ideas;
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
	for (var i=0; i<categoryGroups.length; i++) {
		if (categoryGroups[i].category == category) {
			group = categoryGroups[i];
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
	uncategorizedCategory["count"]++;
	numIdeas++;
	var newHtml = ideaAsHtml(idea, categoryGroups.length+1);
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
		var newIdeaToDiscuss = false;
		var removeIdeaToDiscuss = false;
		
		if (count > 0) {
			 if (!ideaSelector.hasClass("discuss_highlight")) {
				ideaSelector.addClass("discuss_highlight");
			}
			var index = ideasToDiscuss.indexOf(ideaId);
			if (index == -1) {
				newIdeaToDiscuss = true;
				ideasToDiscuss.push(ideaId);
				enableDisableDiscussOption(ideasToDiscuss.length > 0);
				updateDiscussCount(ideaId, 1);
			}
		}
		else if (count == 0) {
			ideaSelector.removeClass("discuss_highlight");
			var index = ideasToDiscuss.indexOf(ideaId);
			if (index != -1) {
				removeIdeaToDiscuss = true;
				ideasToDiscuss.splice(index, 1);
				enableDisableDiscussOption(ideasToDiscuss.length > 0);
				updateDiscussCount(ideaId, -1);
				if (ideasToDiscuss == 0) {
					showDiscussOnly = false;
					// click event not triggered because checkbox disabled
					// when no ideas to discuss
					$("#discuss_only_cb").prop("checked", showDiscussOnly);
					displayIdeas();
				}
			}
		}
		
		if (showDiscussOnly) {		
			showHide(ideaSelector, count>0);
		}
		
		updateStats();
	}
}

function updateDiscussCount(ideaId, inc) {
	$(".idea_"+ideaId).each(function(index) {
		var parentDiv = $(this).parent().parent();
		var categoryId = parseInt(getCategoryId(parentDiv));
		var subcategoryId = parseInt(getSubcategoryId(parentDiv));
		var count = 0;
		if (categoryId in displayedCategories) {
			displayedCategories[categoryId]["discuss_count"] += inc;
			count = displayedCategories[categoryId]["discuss_count"];
			onChangeDiscussCount($("#category_"+categoryId), count);
			if (subcategoryId) {
				displayedCategories[categoryId]["subcategories"][subcategoryId]["discuss_count"] += inc;
				count = displayedCategories[categoryId]["subcategories"][subcategoryId]["discuss_count"]
				onChangeDiscussCount($("subcategory_"+subcategoryId), count);
			}	
		}
		else {
			uncategorizedCategory["discuss_count"] += inc;
			count = uncategorizedCategory["discuss_count"];
			onChangeDiscussCount($("#category_"+categoryId), count);
		}
	});	
}

function onChangeDiscussCount(categoryDiv, count) {
	if (showDiscussOnly) {
		categoryDiv.find(".category_title").find(".count").html(count);
		
		// updating sort based on discuss count is
		// confusing from user perspective since
		// order may change while they are looking
		// at results
		//var sortBy = $("#sort_by").val();
		//if (sortBy == SORT_BY_COUNT) {
		//	displayIdeas();
		//}
	}
}

function handleLogout(data) {
	redirectToLogout(question_id);
}