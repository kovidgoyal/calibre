// For questions about the Bengali hyphenation patterns
// ask Santhosh Thottingal (santhosh dot thottingal at gmail dot com)
Hyphenator.languages['bn'] = {
	leftmin : 2,
	rightmin : 2,
	shortestPattern : 1,
	longestPattern : 1,
	specialChars : unescape("আঅইঈউঊঋএঐঔকগখঘঙচছজঝঞটঠডঢণতথদধনপফবভমযরলশষসহিীাুূৃোোৈৌৗ্ঃং%u200D"),
	patterns : {
		2 : "অ1আ1ই1ঈ1উ1ঊ1ঋ1এ1ঐ1ঔ1ি1া1ী1ু1ৃ1ে1ো1ৌ1ৗ1্2ঃ1ং11ক1গ1খ1ঘ1ঙ1চ1ছ1জ1ঝ1ঞ1ট1ঠ1ড1ঢ1ণ1ত1থ1দ1ধ1ন1প1ফ1ব1ভ1ম1য1র1ল1শ1ষ1স1হ",
		3 : "2ঃ12ং1"
	}
};
