$(function() {
	$("#submit").click(function() {
		var idea = $("#answer").val();
		var data = {
			"idea": idea
		};
		$.post("/submit", data, function() {
			window.location ="/?thanks=true";
		});
	});
});

function displayIdeas(ideas) {
	var html = "Ideas loading ..."; 
	$("#ideas").html(html);
	
	$.getJSON("/query", {}, displayIdeasImpl);
}

function displayIdeasImpl(data) {
	var clusters = data.ideas;

	var numIdeas = 0;
	var html = "";
	for (var i in clusters) {
		var cluster = clusters[i];
		html += "<h2>Cluster #" + (parseInt(i)+1) + "</h2>";
		html += "<table style='width: 100%'><tr>";
		html += "<td style='width: 50%'>";
		html += "<ul>"
		for (var j in cluster) {
			var idea = cluster[j];
			html += "<li>" + idea;
			numIdeas += 1;
		}
		html += "</ul></td>";
		var cloudid = "cloud" + i;
		html += "<td style='width: 50%'><div id='" + cloudid + "' style='height: 100px;'>cloud goes here</div></td>";
		html += "</tr><table>"
	}

	var label = "thought";
	var overviewStr = "<h1>";
	if (numIdeas == 0) {
		overviewStr += "No " + label + "s yet";
	} else if (numIdeas == 1) {
		overviewStr += "1 " + label;
	} else {
		overviewStr += numIdeas + " " + label + "s";
	}
	overviewStr += "</h1>";

	$("#ideaOverview").html(overviewStr);
	$("#ideas").html(html);

	for (var i in clusters) {
		var cluster = clusters[i];
		var cloudid = "cloud" + i
		displayCloud(cloudid, cluster);
	}
}

function displayCloud(cloudid, cluster) {
	var weights = {};
	// for (var i in clusters) {
	// 	var cluster = clusters[i];
		for (var j in cluster) {
			var words = cluster[j].split(" ");
			for (var k in words) {
				var word = words[k].trim();
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
//	}

	var word_list = [];
	var i = 0;
	for (var word in weights) {
		var item = {text: word, weight: weights[word]};
		word_list[i] = item;
		i += 1;
	}

	$("#" + cloudid).jQCloud(word_list);
}

//=================================================================================
// Language and Stemming
//=================================================================================

var STOP_WORDS = [ "a", "am", "an", "and", "been", "by", "in", "is", "or", "the", "was", "were" ];

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

//=================================================================================
// Utilities
//=================================================================================

function normalizeSpacing(s) {
	return s.replace(/\s+/g, " ").trim();
}

function isDefined(obj) {
    return !isUndefined(obj);
}

function isUndefined(obj) {
    return typeof(obj) == "undefined";
}