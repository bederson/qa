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

	var data = {
		"request": "ideas_test",
		"question_id": question_id,
	};
	$.getJSON("/query", data, function(results) {
		question = results.question;
		ideas = results.ideas;
		initKeshif(results);
		
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

function initKeshif(data) {
	kshf.init({
	    facetTitle: question.question,
	    domID : "#ideas",
	    itemName : " responses",
	    categoryTextWidth:150,
	    source : {
            sheets : [ 
                { name: "ideas", data: data.ideas },
                { name: "fits", data: data.fits },
                { name: "users", data: data.users } 
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
            {
                facetTitle: "Words",
                itemMapFunc : function(answer){ 
                    var words = answer.data[2].split(" ");
                    var newwords = [];
                    for(var i=0; i<words.length ; i++){
                        var w=words[i].toLowerCase();
                        if(!isStopWord(w)) {
                            newwords.push(w);
                        }
                    }
                    return newwords;
                },
                catDispCountFix: 15,
                filter: { rowConj: 'of type' },
            },
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
                    width: 85,
                    value: function(answer){ return answer.data[1]; }
                    //value: function(answer){ return kshf.dt_id.users[answer.data[1]].data[2]; }
                }
            ],
            contentFunc : function(d){
                var cats = qCats[d.data[0]];
                var str="";
                str+="<div class='iteminfo iteminfo_0'>"+d.data[2]+"</div>";
                str+="<div class='iteminfo iteminfo_1'>Categories: ";
                str += isUndefined(cats) ? "none" : cats.join(", ");
                str+="</div";
               return str;
            }
        }
	});
}

//=================================================================================
// Language and Stemming
//=================================================================================

var STOP_WORDS = [ "a", "about", "all", "am", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by", "can", "did", "do", "for", "from", "get", "had", "has", "he", "here", "his", "how", "I", "if", "in", "into", "is", "it", "its", "of", "on", "only", "or", "put", "said", "she", "so", "some", "than", "that", "the", "them", "they", "their", "there", "this", "to", "was", "we", "went", "were", "what", "when", "where", "which", "who", "will", "with", "without", "you", "your" ];

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