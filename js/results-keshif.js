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

var OFFLINE = false;
var MIN_RESULTS_WIDTH = 700;

var question = null;
var categorizedIdeas = [];
var uncategorizedIdeas = [];
var numIdeas = 0;
var categoryCounts = {};
    		
var singleCategoryOnly = false;
var showOnlyInCategories = {};
var subcategories = [];

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

function adjustSize() {
	var top = $("#ideas").position().top;
	var height = $(window).height()-top-10;
	var width = $(window).width()-10;
	if (width < MIN_RESULTS_WIDTH) width = MIN_RESULTS_WIDTH;
	$("#ideas").height(height);
	$("#ideas").width(width);
}

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
		displayResults();
	});
}

function loadResults() {	
	var question_id = getURLParameter("question_id");
	var data = {
		"request": "ideas",
		"group_by": "category",
		"question_id": question_id,
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		categorizedIdeas = results.categorized;
		uncategorizedIdeas = results.uncategorized;
		numIdeas = results.count;
		displayResults();
	});
}	

function displayResults() {
	updateResultsForDisplay();
	initKeshif();
}

function updateResultsForDisplay() {
categoryCounts = {};
	for (var i=0; i<categorizedIdeas.length; i++) {
		var category = categorizedIdeas[i].category;
		var ideas = categorizedIdeas[i].ideas;
		categoryCounts[category] = ideas.length;
	}
					
	// find category that item should be displayed in if only displayed in a *single* category
	showOnlyInCategories = {};
	for (var i=0; i<categorizedIdeas.length; i++) {
		var category = categorizedIdeas[i].category;
		var ideas = categorizedIdeas[i].ideas;
		for (var j=0; j<ideas.length; j++) {
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
				
	displayedCategories = {};
	for (var i=0; i<categorizedIdeas.length; i++) {
		var categoryGroup = categorizedIdeas[i];
		var category = categoryGroup.category;
		var categoryIdeas = categoryGroup.ideas;
		var categorySubcategories = isDefined(categoryGroup.subcategories) ? categoryGroup.subcategories : [];
		var categorySameAs = categoryGroup.same_as;
			
		var count = 0;
		for (var j=0; j<categoryIdeas.length; j++) {
			var skip = false;
			var idea = categoryIdeas[j];
			var alsoIn = isDefined(idea.also_in) ? idea.also_in : [];
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
}

function initKeshif() { 
	var data = {};
	for (var i in displayedCategories) {
		var category = displayedCategories[i].category;
		var ideas = displayedCategories[i].ideas;
		addIdeasToCategory(category, ideas, data);
	}
	addIdeasToCategory("NONE", uncategorizedIdeas, data);
				
	$("#ideas").html("");	       
	kshf.init({
	    facetTitle: question.question,
	    domID : "#ideas",
	    itemName : " responses",
	    categoryTextWidth: 150,
	    dirRoot: "/js/keshif/",
	    source : {
            sheets : [ 
                { name: "ideas", data: data.ideaData },
                { name: "fits", data: data.fitData },
                { name: "users", data: data.userData },
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
    		 	ideaText = ideaText.replace(/[,:;.?]/g, "")
				var words = ideaText.split(" ");
    		 	for (var j=0; j<words.length; j++) {
    		 		var word = words[j];
    		 		if (word != "" && !isStopWord(word)) {
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
            sortOpts : [
                {   name: 'Student ID',
                    width: 85,
                    value: function(idea) { return idea.data[ideasCol.user_id]; }
                }
            ],
            contentFunc : function(idea) {
                var cats = idea.data[ideasCol.categories];
                var str = "";
                str += "<div class='iteminfo iteminfo_0'>"+idea.data[ideasCol.idea]+"</div>";
                str += "<div class='iteminfo iteminfo_1'>";
                str += (cats.length==1 && cats[0]=="NONE") ? "Uncategorized" : "Categories: " + cats.join(", ");
                str += "</div>";
                return str;
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
		var authorIdentity = isDefined(ideas[i].author_identity) ? ideas[i].author : ideas[i].author;
				
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
// Language and Stemming
//=================================================================================

function isStopWord(word) {
	var stopWordsSet = isStopWord._stopWordsSet;
	if (isUndefined(stopWordsSet)) {
		var stopWordsSet = {};
		var numStopWords = STOP_WORDS.length;
		for(var i=0; i<numStopWords; i++) {
			stopWordsSet[STOP_WORDS[i].toLowerCase()] = true;
		}
		isStopWord._stopWordsSet = stopWordsSet;
	}
	return isDefined(stopWordsSet[word.toLowerCase()]);
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	// TODO/FIX!
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