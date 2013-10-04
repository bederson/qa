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

var question = null;
var categorizedIdeas = [];
var uncategorizedIdeas = [];
var numIdeas = 0;

var qCats = {};
   
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
		
		initKeshif();
		
		// FIX!
		//updateStatus();
			
		// FIX!
		//if (OFFLINE) {
		//	displayIdeas();
		//}
		//else {
		//	// http://stackoverflow.com/questions/556406/google-setonloadcallback-with-jquery-document-ready-is-it-ok-to-mix
		//	google.load('visualization', '1.0', { 'packages':['corechart'], 'callback': displayIdeas });
		//}
	});
}

function initKeshif() {
	kshf.init({
	    facetTitle: question.question,
	    domID : "#ideas",
	    itemName : " answers",
	    categoryTextWidth:186,
	    source : {
	    	gdocId : '0Ai6LdDWgaqgNdGEyX1BNOHlJS0hobmJaaHJfMGxSb0E',
            sheets : [ 
                {name:"ideas"},
                {name:"fits"},
                {name:"users"} 
            ]
	    },
	    loadedCb: function(){
	        for (var i=0; i<kshf.dt.fits.length; i++){
                var x=kshf.dt.fits[i];
                var idea_id= x.data[1];
                var cat= x.data[2];
                if(idea_id in qCats){
                    // if it already in the array, don't put it back
                    if(qCats[idea_id].indexOf(cat)!==-1) {
                        continue;
                    }
                    qCats[idea_id].push(cat);
                } else {
                    qCats[idea_id] = [cat];
                }
            }
	    },
	    charts: [
	        {
                facetTitle: "Categories",
                itemMapFunc : function(answer){ 
                    return qCats[answer.data[0]]; 
                },
                filter: { rowConj: 'of type' },
            },
            /*
            {
                facetTitle: "Tags",
                itemMapFunc : function(answer){ 
                    var words = answer.data[2].split(" ");
                    var newwords = [];
                    for(var i=0; i<words.length ; i++){
                        var w=words[i].toLowerCase();
                        if(stopWords[w]===undefined) {
                            newwords.push(w);
                        }
                    }
                    return newwords;
                },
                filter: { rowConj: 'of type' },
            },
            */
            {
                facetTitle: "Students",
                itemMapFunc : function(answer){ 
                    return kshf.dt_id.users[answer.data[1]].data[2];
                },
                catDispCountFix: 5,
                filter: { rowConj: 'of type' },
            }

	    ],
	    list: {
            sortOpts : [
                {   name: 'Student ID',
                    width: 75,
                    value: function(answer){ return answer.data[1]; }
                }
            ],
            contentFunc : function(d){
                var j;
                var str="";
                str+="<div class=\"iteminfo iteminfo_0\">"+d.data[2]+"</div>";
                str+="<div class=\"iteminfo iteminfo_1\">Group under: ";
                var cats = qCats[d.data[0]];
                if(cats===undefined) str+="none"; else
                for(var i=0;i<cats.length;i++){
                    str+=cats[i]+" , ";
                }
                str+="</div";
               return str;
            }
        }

	});
}

/////////////////////////
// Channel support
/////////////////////////
function handleIdea(data) {
	// FIX!
	//addIdea(data.idea);
}

function handleEnable(data) {
	question.active = 1;
	// FIX!
	//updateStatus();
}

function handleDisable(data) {
	question.active = 0;
	// FIX!
	//updateStatus();
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