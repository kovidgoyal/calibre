// For questions about the Tamil hyphenation patterns
// ask Santhosh Thottingal (santhosh dot thottingal at gmail dot com)
Hyphenator.languages['ta'] = {
	leftmin : 2,
	rightmin : 2,
	shortestPattern : 1,
	longestPattern : 2,
	specialChars : "அஆஇஈஉஊஎஏஐஒஓஔாிீுூெேைொோௌகஙசஜஞடணதநபமயரறலளழவஷஸஹ்னஂஃௗ",
	patterns : {
		2 : "ா1ி1ீ1ு1ூ1ெ1ே1ை1ொ1ோ1ௌ11க1ங1ச1ஜ1ஞ1ட1ண1த1ந1ப1ம1ய1ர1ற1ல1ள1ழ1வ1ஷ1ஸ1ஹ",
		3 : "1அ11ஆ11இ11ஈ11உ11ஊ11எ11ஏ11ஐ11ஒ11ஓ11ஔ12ஂ12ஃ12ௗ12்1",
		4 : "2க்12ங்12ச்12ஞ்12ட்12ண்12த்12ன்12ந்12ப்12ம்12ய்12ர்12ற்12ல்12ள்12ழ்12வ்12ஷ்12ஸ்12ஹ்1"
	}
};
