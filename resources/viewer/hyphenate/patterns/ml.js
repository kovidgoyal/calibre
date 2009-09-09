// For questions about the Malayalam hyphenation patterns
// ask Santhosh Thottingal (santhosh dot thottingal at gmail dot com)
Hyphenator.languages.ml = {
	leftmin : 2,
	rightmin : 2,
	shortestPattern : 1,
	longestPattern : 3,
	specialChars : unescape('ആഅഇഈഉഊഋഎഏഐഒഔകഗഖഘങചഛജഝഞടഠഡഢണതഥദധനപഫബഭമയരലവശഷസഹളഴറിീാുൂൃെേൊാോൈൌൗ്ഃം%u200D'),
	patterns : {
		2 : 'അ1ആ1ഇ1ഈ1ഉ1ഊ1ഋ1എ1ഏ1ഐ1ഒ1ഔ1ി1ാ1ീ1ു1ൂ1ൃ1െ1േ1ൊ1ോ1ൌ1ൗ1്2ഃ1ം11ക1ഗ1ഖ1ഘ1ങ1ച1ഛ1ജ1ഝ1ഞ1ട1ഠ1ഡ1ഢ1ണ1ത1ഥ1ദ1ധ1ന1പ1ഫ1ബ1ഭ1മ1യ1ര1ല1വ1ശ1ഷ1സ1ഹ1ള1ഴ1റ',
		3 : '2ഃ12ം1',
		4 : unescape('2ന്%u200D2ര്%u200D2ല്%u200D2ള്%u200D2ണ്%u200D')
	}
};
