// For questions about the Malayalam hyphenation patterns
// ask Santhosh Thottingal (santhosh dot thottingal at gmail dot com)
Hyphenator.languages['ml'] = {
	leftmin : 2,
	rightmin : 2,
	shortestPattern : 1,
	longestPattern : 3,
	specialChars : unescape("അആഇഈഉഊഋൠഌൡഎഏഐഒഓഔാിീുൂൃെേൈൊോൌൗകഖഗഘങചഛജഝഞടഠഡഢണതഥദധനപഫബഭമയരറലളഴവശഷസഹഃം്ൺൻർൽൾൿ%u200D"),
	patterns : {
		2 : "ാ1ി1ീ1ു1ൂ1ൃ1െ1േ1ൈ1ൊ1ോ1ൌ1ൗ11ക1ഖ1ഗ1ഘ1ങ1ച1ഛ1ജ1ഝ1ഞ1ട1ഠ1ഡ1ഢ1ണ1ത1ഥ1ദ1ധ1ന1പ1ഫ1ബ1ഭ1മ1യ1ര1റ1ല1ള1ഴ1വ1ശ1ഷ1സ1ഹ2ൺ2ൻ2ർ2ൽ2ൾ2ൿ",
        3 : "1അ11ആ11ഇ11ഈ11ഉ11ഊ11ഋ11ൠ11ഌ11ൡ11എ11ഏ11ഐ11ഒ11ഓ11ഔ12ഃ12ം12്2ന്2ര്2ള്2ല്2ക്2ണ്2",
		4 : unescape("2ന്%u200D2ര്%u200D2ല്%u200D2ള്%u200D2ണ്%u200D2ക്%u200D")
	}
};
