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

// TODOs
// * highlight categories
// * make NONE category always on bottom
// * make list of words smaller
// * show popup when user mouses over discuss
// * allow user to click on discuss button

var OFFLINE = false;
var MIN_RESULTS_WIDTH = 700;

var question = null;
var categorizedIdeas = [];
var uncategorizedIdeas = [];
var numIdeas = 0;
var displayedCategories = {};
var categoryCounts = {};
	
var DISPLAY_SUBCATEGORIES = false;
var subcategories = [];
var showSubcategories = false;
var hasSubcategories = false;

var DISPLAY_ITEM_IN_SINGLE_CATEGORY = true;		
var singleCategoryOnly = false;
var primaryCategories = {};

// Keshif
var ideasCol;
var fitsCol;
var usersCol;

$(document).ready(function() {
	if ($("#msg").html()) {
		return;
	}
	
	initChannel(onChannelOpen);	
	$("#page_content").show();
});

function onChannelOpen() {
	adjustSize();	
	$(window).resize(function() {
		adjustSize();
		kshf.updateLayout();
	});

	loadResults();
		
	if (!jQuery.browser.mobile) {
		$("#admin_buttons").show();
	}
	
	$("#admin_button").click(function() {
		var question_id = getURLParameter("question_id");
		redirectToAdminPage(question_id);
	});
	
	$("#single_category_cb").click(function() {
		singleCategoryOnly = $(this).is(":checked");
		initDisplayCategories();
		displayIdeas();
	});
}

function adjustSize() {
	var top = $("#ideas").position().top;
	var height = $(window).height()-top-10;
	var width = $(window).width()-10;
	if (width < MIN_RESULTS_WIDTH) width = MIN_RESULTS_WIDTH;
	$("#ideas").height(height);
	$("#ideas").width(width);
}

function loadResults() {	
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas",
		"group_by": "category",
		"question_id": question_id,
		"discuss": SHOW_DISCUSS_BUTTONS ? "1" : "0",
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		categorizedIdeas = results.categorized;
		uncategorizedIdeas = results.uncategorized;
		numIdeas = results.count;
	
		// initialize discussion flags
		initDiscussFlags(results.discuss_flags, true);
		
		// initialize category counts
		categoryCounts = {};
		for (var i=0; i<categorizedIdeas.length; i++) {
			var category = categorizedIdeas[i].category;
			var categoryIdeas = categorizedIdeas[i].ideas;
			categoryCounts[category] = categoryIdeas.length;
		}

		// initialize data structure used to display results
		initDisplayCategories();

		displayIdeas();
	});
}	

function displayIdeas() {
	initKeshif();
	initDiscussButtons(question.id, client_id);
	$('[title!=""]').qtip({ style: "tooltip" });
}

function initKeshif() { 
	var data = {};
	for (var i in displayedCategories) {
		var category = displayedCategories[i].category;
		var ideas = displayedCategories[i].ideas;
		addIdeasToCategory(category, ideas, data);
	}
	addIdeasToCategory("NONE", uncategorizedIdeas, data);
		
	var userSortOption = {   
		name: 'User',
        width: 80,
        label: function(idea) {
            var userId = idea.data[ideasCol.user_id];
        	var user = kshf.dt_id.users[userId].data;
        	var html = "<div style='text-align:left; margin-left:15px'>";
        	html += getUserHtml(user[usersCol.nickname], user[usersCol.authenticated_nickname], "");
        	html += "</div>";
        	return html;
        },
        value: function(idea) { 
        	var userId = idea.data[ideasCol.user_id];
        	var user = kshf.dt_id.users[userId].data;
        	return user[usersCol.nickname];
       	},
       	value_type: "string"
     };
     
     var discussSortOption = {
		name: 'Discuss',
        width: 80,
        label: function(idea) {
        	var ideaId = idea.data[ideasCol.id];
        	return discussButtonHtml(ideaId, "width:100%; margin-left:auto; margin-right:auto;");
		},
        value: function(idea) {
            var ideaId = idea.data[ideasCol.id];
            return getDiscussFlagCount(ideaId);
        },
        value_type: "number"
    };
    
    var personalDiscussSortOption = {
		name: 'Personal Discuss',
        width: 80,
        label: function(idea) {
        	var ideaId = idea.data[ideasCol.id];
		    return discussButtonHtml(ideaId);
		},
        value: function(idea) {
            var ideaId = idea.data[ideasCol.id];
			return isPersonalDiscussIdea(ideaId) ? getDiscussFlagCount(ideaId) : 0;
        }
    };
    
    var sortOpts = [];
    if (numKeys(discussFlags) > 0) {
    	sortOpts.push(discussSortOption);
    	if (personalDiscussIdeas.length > 0) {
    		//sortOpts.push(personalDiscussSortOption);
    	}
    }
    sortOpts.push(userSortOption);
                			
	$("#ideas").html("");	       
	kshf.init({
	    facetTitle: question.question,
	    domID : "#ideas",
	    itemName : " responses",
	    categoryTextWidth: 150,
	    dirRoot: "/js/keshif/",
	    showDataSource: false,
	    source : {
            sheets : [ 
                { name: "ideas", data: data.ideaData },
                { name: "fits", data: data.fitData },
                { name: "users", data: data.userData }
            ]
	    },
	    loadedCb: function() {  
	    	ideasCol = kshf.dt_ColNames.ideas;
	    	ideasCol.words = 4;
	    	ideasCol.categories = 5;
    		fitsCol = kshf.dt_ColNames.fits;
    		usersCol = kshf.dt_ColNames.users;
    		
    		for (var i=0; i<kshf.dt.ideas.length; i++) {
    		 	var ideaId = kshf.dt.ideas[i].data[ideasCol.id];
    		 	var ideaText = kshf.dt.ideas[i].data[ideasCol.idea];
				var words = ideaText.split(" ");
    		 	for (var j=0; j<words.length; j++) {
    		 		var word = cleanWord(words[j]);
    		 		if (word!="" && !isStopWord(word)) {
				    	if (!kshf.dt_id.ideas[ideaId].data[ideasCol.words]) { 
				    		kshf.dt_id.ideas[ideaId].data[ideasCol.words] = []; 
				    	}
				        kshf.dt_id.ideas[ideaId].data[ideasCol.words].push(word);
			        }
		       	}
            }
            
	        for (var i=0; i<kshf.dt.fits.length; i++) {
                var fit = kshf.dt.fits[i];
                var ideaId = fit.data[fitsCol.idea_id];
                var cat = fit.data[fitsCol.category];
    			if (!kshf.dt_id.ideas[ideaId].data[ideasCol.categories]) { 
    				kshf.dt_id.ideas[ideaId].data[ideasCol.categories] = []; 
    			}
                if (kshf.dt_id.ideas[ideaId].data[ideasCol.categories].indexOf(cat)===-1) {
                	kshf.dt_id.ideas[ideaId].data[ideasCol.categories].push(cat);
                }
            }
	    },
	    charts: [
	        {
                facetTitle: "Categories",
                catItemMap : function(idea) {
                    return idea.data[ideasCol.categories];
                },
                filter: { rowConj: 'in category' },
            },
            {
                facetTitle: "Words",
                catItemMap : function(idea) {
                	return idea.data[ideasCol.words];
                },
                filter: { rowConj: 'contains word' },
            },
            {
                facetTitle: "Students",
                catItemMap : function(idea) {
                    var userId = idea.data[ideasCol.user_id];
                    var userData = kshf.dt_id.users[userId].data;
                    return userData[usersCol.nickname];
                },
                filter: { rowConj: 'by author' },
            }
	    ],
	    list: {
            sortOpts : sortOpts,
            contentFunc : function(idea) {
	            var userId = idea.data[ideasCol.user_id];
	        	var user = kshf.dt_id.users[userId].data;
                var cats = idea.data[ideasCol.categories];
                var html = "<div class='iteminfo iteminfo_0'>" + idea.data[ideasCol.idea] + "</div>";
                html += "<div class='iteminfo iteminfo_1'>submitted by ";            
				html += getUserHtml(user[usersCol.nickname], user[usersCol.authenticated_nickname], "");
				html += "</div>";
                html += "<div class='iteminfo iteminfo_2' style='margin-bottom:8px'>";
                html += (cats.length==1 && cats[0]=="NONE") ? "Uncategorized" : cats.join(", ");
                html += "</div>";
                return html;
            }
        }
	});
}

function addIdeasToCategory(category, ideas, data) {
	if (!("ideaData" in data)) {
		data.ideas = {};
		data.users = {};
		data.ideaData = [];
		data.ideaData.push([ "id", "idea", "user_id" ]);
		data.userData = [];		
		data.userData.push([ "id", "authenticated_nickname", "nickname" ]);
		data.fitData = [];
		data.fitData.push([ "idea_id", "category", "user_id" ]);
	}
	
	for (var i=0; i<ideas.length; i++) {
		var userId = ideas[i].user_id;
		var ideaId = ideas[i].id;
		var idea = ideas[i].idea;
		var author = ideas[i].author;
		var authorIdentity = isDefined(ideas[i].author_identity) && ideas[i].author_identity!=null ? ideas[i].author_identity : ideas[i].author;
				
		if (!(ideaId in data.ideas)) { 
			data.ideas[ideaId] = [ ideaId, idea, userId ];
			data.ideaData.push(data.ideas[ideaId]);
		}
			
		if (!(userId in data.users)) {
			data.users[userId] = [ userId, authorIdentity, author ];
			data.userData.push(data.users[userId]);
		}
			
		data.fitData.push([ ideaId, category, userId ]);
	}
}

function initDisplayCategories() {
	// initialize primary categories for ideas where a primary category is where
	// an item should be displayed in if it can only be displayed in a *single* category
	initPrimaryCategories();
							
	displayedCategories = {};
	for (var i=0; i<categorizedIdeas.length; i++) {
		var categoryGroup = categorizedIdeas[i];
		var category = categoryGroup.category;
		var categoryIdeas = categoryGroup.ideas;
		var categorySubcategories = isDefined(categoryGroup.subcategories) ? categoryGroup.subcategories : [];
		var categorySameAs = categoryGroup.same_as;
		
		var isRootCategory = !showSubcategories || $.inArray(category, subcategories) == -1;		
		if (isRootCategory) {
			var count = 0;
			for (var j=0; j<categoryIdeas.length; j++) {
				var idea = categoryIdeas[j];
				
				// skip if displaying subcategories and this idea is in a subcategory
				var skip = false;
				var alsoIn = isDefined(idea.also_in) ? idea.also_in : [];
				if (showSubcategories && alsoIn.length > 0 && categorySubcategories.length > 0) {
					var isIdeaInSubcategory = intersection(alsoIn, categorySubcategories).length > 0;
					skip = isIdeaInSubcategory;
				}
			
				// skip if only displaying idea in single category and this is not the primary category
				if (singleCategoryOnly && isDefined(primaryCategories[idea.id]) && primaryCategories[idea.id] != category) {
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
	}
}

function initPrimaryCategories() {
	// find primary categories for ideas that appear in multiple categories
	// ideas only in single category not included
	primaryCategories = {};
	if (DISPLAY_ITEM_IN_SINGLE_CATEGORY) {		
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

function getUserHtml(displayName, realIdentity, customClass) {
	var realIdentity = isDefined(realIdentity) && realIdentity!=null ? realIdentity : "";
	var html = "<span";
	html += isDefined(customClass) ? " class='" + customClass + "'" : "";
	var isIdentityHidden = realIdentity != "" && realIdentity != displayName;
	if (isIdentityHidden) {
		html += " title='" + realIdentity + "' ";
	}
	html += ">" + displayName + (isIdentityHidden ? "*" : "") + "</span>";
	return html;
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	// TODO/FIX: support dynamic adding of new ideas
	//addIdea(data.idea);
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