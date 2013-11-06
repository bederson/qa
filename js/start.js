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

$(function() {	
	initEventHandlers();
	
	if ($("#msg").html()) {
		return;
	}
	
	$("#page_content").show();
});

function initEventHandlers() {
	// called when page is first loaded
	// do not add any event handlers for objects that are created/destroyed dynamically
	
	$("#admin_button").click(function() {
		redirectToAdminPage(question_id);
	});
}