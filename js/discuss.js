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

var SHOW_DISCUSS_BUTTONS = true;
var DISCUSS_BUTTON_NO_HIGHLIGHT = "/images/discuss.png";
var DISCUSS_BUTTON_HIGHLIGHT = "/images/discuss-highlight.png";

var discussFlags = {};
var personalDiscussIdeas = [];
var showFlagCount = false;
var showUserList = false;

function initDiscussFlags(flags, showCount, showUsers) {
	if (!SHOW_DISCUSS_BUTTONS) {
		return;
	}
	
	discussFlags = {};		
	personalDiscussIdeas = [];
	showFlagCount = isDefined(showCount) ? showCount : false;
	showUserList = isDefined(showUsers) ? showUsers : false;
	
	for (var i in flags) {
		addDiscussFlag(flags[i]);
	}
}

function initDiscussButtons(questionId, clientId, ideaId) {
	if (!SHOW_DISCUSS_BUTTONS) {
		return;
	}
	
	buttonSelector = isDefined(ideaId) ? ".discuss_idea_"+ideaId+"_button" : ".discuss_idea_button";

	// TOOD/FIX: tooltip does not display in Keshif, and click function not called either
	$(buttonSelector).qtip({
		content: {
			text: function(event, api) {
				var buttonId = $(this).attr("name");
				var tokens = buttonId.split("_");
				var ideaId = parseInt(tokens[2]);
				return discussTooltipHtml(ideaId);
			}
		},
		style: {
			tip: { corner: true },
			classes: 'qtip-rounded tooltip'
		}
	});
	
	$(buttonSelector).click(function() {
		var buttonId = $(this).attr("name");
		var tokens = buttonId.split("_");
		var ideaId = parseInt(tokens[2]);
		var isPersonal = isPersonalDiscussIdea(ideaId);

		var data = {
			"client_id": clientId,
			"question_id": questionId,
			"idea_id" : ideaId,
			"add" : !isPersonal ? "1" : "0"
		};
		$.post("/discuss_idea", data, function(result) {
			if (result.status == 1) {
				addRemoveDiscussFlag(result.flag, data.add=="1");
				$(".discuss_idea_"+result.flag.idea_id+"_button").attr("src", data.add=="1" ? DISCUSS_BUTTON_HIGHLIGHT : DISCUSS_BUTTON_NO_HIGHLIGHT);
			}
		}, "json");
	});
	
	// TODO/FIX: need different highlight image for hover
	/*			
	$(buttonSelector).hover(
		function() {
			var buttonImage = $(this).attr("src");
			var newButtonImage = (buttonImage == DISCUSS_BUTTON_NO_HIGHLIGHT) ? DISCUSS_BUTTON_HIGHLIGHT : DISCUSS_BUTTON_NO_HIGHLIGHT;
			$(this).attr("src", newButtonImage);
		}, 
		function() {
			var buttonId = $(this).attr("name");
			var tokens = buttonId.split("_");
			var ideaId = parseInt(tokens[2]);
			var isPersonal = isPersonalDiscussIdea(ideaId);
			$(this).attr("src", isPersonal ? DISCUSS_BUTTON_HIGHLIGHT : DISCUSS_BUTTON_NO_HIGHLIGHT);
		}
	);
	*/
}

function discussButtonHtml(ideaId, customCss) {
	if (!SHOW_DISCUSS_BUTTONS) {
		return "";
	}
		
	customCss = isDefined(customCss) ? "style='"+customCss+"'" : ""
	var isPersonal = isPersonalDiscussIdea(ideaId);
	var buttonImage = isPersonal ? DISCUSS_BUTTON_HIGHLIGHT : DISCUSS_BUTTON_NO_HIGHLIGHT;
	var html = "<div class='image' " + customCss + ">";
	html += "<img name='discuss_idea_"+ideaId+"_button' class='discuss_idea_"+ideaId+"_button discuss_idea_button' src='"+buttonImage+"' style='vertical-align:middle' /> ";
	if (showFlagCount) {
		var count = getDiscussFlagCount(ideaId);
		html += "<div name='discuss_idea_"+ideaId+"_count' class='discuss_idea_"+ideaId+"_count image_text'>";
		html += count > 0 ? "+" + count : "";
		html += "</div> ";
	}
	html += "</div>";
	return html;
}

function discussTooltipHtml(ideaId) {
	var userListHtml = "";
	if (showUserList) {
		var userList = [];
		if (isDefined(discussFlags[ideaId])) {
			for (var i=0; i<discussFlags[ideaId].length; i++) {
				var nameHtml = discussUserHtml(discussFlags[ideaId][i].user_nickname, discussFlags[ideaId][i].user_identity);
				userList.push(nameHtml);
			}
		}	
			
		if (userList.length > 0) {
			userListHtml += "Flagged by:<br/>";
			userListHtml += userList.join("<br/>");
		}
	}

	var isPersonal = isPersonalDiscussIdea(ideaId);
	var tooltip = "<span class='note'>";
	tooltip += !isPersonal ? "<em>Click to flag for discussion</em><br/>" : "";
	tooltip += showUserList ? userListHtml : (isPersonal ? "<em>Click to unflag for discussion</em>" : "");
	tooltip += "</span>";
	return tooltip;
}

function discussUserHtml(displayName, realIdentity, customClass) {
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

function updateDiscussIdea(ideaId) {
	var tooltip = discussTooltipHtml(ideaId);
	var qapi = $(".discuss_idea_"+ideaId+"_button").qtip('api');
	qapi.set('content.text', tooltip);
	if (showFlagCount) {
		var count = getDiscussFlagCount(ideaId);
		var countLabel = count > 0 ? "+" + count : "";
		$(".discuss_idea_"+ideaId+"_count").html(countLabel);
	}
}

function addRemoveDiscussFlag(flag, add) {
	if (add) {
		addDiscussFlag(flag);
	}
	else {
		removeDiscussFlag(flag);
	}
	updateDiscussIdea(flag.idea_id);
}
	
function addDiscussFlag(flag) {
	if (isUndefined(discussFlags[flag.idea_id])) {
		discussFlags[flag.idea_id] = [];
	}
	discussFlags[flag.idea_id].push(flag);

	if (flag.user_id == user_id) {
		var isPersonalFlag = flag.user_id == user_id;
		if (isPersonalFlag && $.inArray(flag.idea_id, personalDiscussIdeas) == -1) {
			personalDiscussIdeas.push(flag.idea_id);
		}
	}
}

function removeDiscussFlag(flag) {
	if (isDefined(discussFlags[flag.idea_id])) {
		for (var i=0; i<discussFlags[flag.idea_id].length; i++) {
			if (discussFlags[flag.idea_id][i].user_id == flag.user_id) {
				discussFlags[flag.idea_id].splice(i, 1);
				if (discussFlags[flag.idea_id].length == 0) {
					delete discussFlags[flag.idea_id];
				}
				break;
			}
		}
	}	

	if (flag.user_id == user_id) {
		var index = personalDiscussIdeas.indexOf(flag.idea_id);
		if (index != -1) {
			personalDiscussIdeas.splice(index, 1);
		}
	}
}

function getDiscussFlagCount(ideaId) {
	return isDefined(discussFlags[ideaId]) ? discussFlags[ideaId].length : 0;
}

function isPersonalDiscussIdea(ideaId) {
	return $.inArray(ideaId, personalDiscussIdeas) != -1;
}