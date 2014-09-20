/* For Unicode version 7.0.0 */

#include "_regex_unicode.h"

#define RE_BLANK_MASK ((1 << RE_PROP_ZL) | (1 << RE_PROP_ZP))
#define RE_GRAPH_MASK ((1 << RE_PROP_CC) | (1 << RE_PROP_CS) | (1 << RE_PROP_CN))
#define RE_WORD_MASK (RE_PROP_M_MASK | (1 << RE_PROP_ND) | (1 << RE_PROP_PC))

typedef struct RE_AllCases {
    RE_INT32 diffs[RE_MAX_CASES - 1];
} RE_AllCases;

typedef struct RE_FullCaseFolding {
    RE_INT32 diff;
    RE_UINT16 codepoints[RE_MAX_FOLDED - 1];
} RE_FullCaseFolding;

/* strings. */

char* re_strings[] = {
    "-1/2",
    "0",
    "1",
    "1/10",
    "1/16",
    "1/2",
    "1/3",
    "1/4",
    "1/5",
    "1/6",
    "1/7",
    "1/8",
    "1/9",
    "10",
    "100",
    "1000",
    "10000",
    "100000",
    "1000000",
    "100000000",
    "10000000000",
    "1000000000000",
    "103",
    "107",
    "11",
    "11/2",
    "118",
    "12",
    "122",
    "129",
    "13",
    "13/2",
    "130",
    "132",
    "133",
    "14",
    "15",
    "15/2",
    "16",
    "17",
    "17/2",
    "18",
    "19",
    "2",
    "2/3",
    "2/5",
    "20",
    "200",
    "2000",
    "20000",
    "202",
    "21",
    "214",
    "216",
    "216000",
    "218",
    "22",
    "220",
    "222",
    "224",
    "226",
    "228",
    "23",
    "230",
    "232",
    "233",
    "234",
    "24",
    "240",
    "25",
    "26",
    "27",
    "28",
    "29",
    "3",
    "3/16",
    "3/2",
    "3/4",
    "3/5",
    "3/8",
    "30",
    "300",
    "3000",
    "30000",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "4",
    "4/5",
    "40",
    "400",
    "4000",
    "40000",
    "41",
    "42",
    "43",
    "432000",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "5",
    "5/2",
    "5/6",
    "5/8",
    "50",
    "500",
    "5000",
    "50000",
    "6",
    "60",
    "600",
    "6000",
    "60000",
    "7",
    "7/2",
    "7/8",
    "70",
    "700",
    "7000",
    "70000",
    "8",
    "80",
    "800",
    "8000",
    "80000",
    "84",
    "9",
    "9/2",
    "90",
    "900",
    "9000",
    "90000",
    "91",
    "A",
    "ABOVE",
    "ABOVELEFT",
    "ABOVERIGHT",
    "AEGEANNUMBERS",
    "AGHB",
    "AHEX",
    "AI",
    "AIN",
    "AL",
    "ALAPH",
    "ALCHEMICAL",
    "ALCHEMICALSYMBOLS",
    "ALEF",
    "ALETTER",
    "ALNUM",
    "ALPHA",
    "ALPHABETIC",
    "ALPHABETICPF",
    "ALPHABETICPRESENTATIONFORMS",
    "ALPHANUMERIC",
    "AMBIGUOUS",
    "AN",
    "ANCIENTGREEKMUSIC",
    "ANCIENTGREEKMUSICALNOTATION",
    "ANCIENTGREEKNUMBERS",
    "ANCIENTSYMBOLS",
    "ANY",
    "AR",
    "ARAB",
    "ARABIC",
    "ARABICEXTA",
    "ARABICEXTENDEDA",
    "ARABICLETTER",
    "ARABICMATH",
    "ARABICMATHEMATICALALPHABETICSYMBOLS",
    "ARABICNUMBER",
    "ARABICPFA",
    "ARABICPFB",
    "ARABICPRESENTATIONFORMSA",
    "ARABICPRESENTATIONFORMSB",
    "ARABICSUP",
    "ARABICSUPPLEMENT",
    "ARMENIAN",
    "ARMI",
    "ARMN",
    "ARROWS",
    "ASCII",
    "ASCIIHEXDIGIT",
    "ASSIGNED",
    "AT",
    "ATA",
    "ATAR",
    "ATB",
    "ATBL",
    "ATERM",
    "ATTACHEDABOVE",
    "ATTACHEDABOVERIGHT",
    "ATTACHEDBELOW",
    "ATTACHEDBELOWLEFT",
    "AVAGRAHA",
    "AVESTAN",
    "AVST",
    "B",
    "B2",
    "BA",
    "BALI",
    "BALINESE",
    "BAMU",
    "BAMUM",
    "BAMUMSUP",
    "BAMUMSUPPLEMENT",
    "BASICLATIN",
    "BASS",
    "BASSAVAH",
    "BATAK",
    "BATK",
    "BB",
    "BC",
    "BEH",
    "BELOW",
    "BELOWLEFT",
    "BELOWRIGHT",
    "BENG",
    "BENGALI",
    "BETH",
    "BIDIC",
    "BIDICLASS",
    "BIDICONTROL",
    "BIDIM",
    "BIDIMIRRORED",
    "BINDU",
    "BK",
    "BL",
    "BLANK",
    "BLK",
    "BLOCK",
    "BLOCKELEMENTS",
    "BN",
    "BOPO",
    "BOPOMOFO",
    "BOPOMOFOEXT",
    "BOPOMOFOEXTENDED",
    "BOTTOM",
    "BOTTOMANDRIGHT",
    "BOUNDARYNEUTRAL",
    "BOXDRAWING",
    "BR",
    "BRAH",
    "BRAHMI",
    "BRAHMIJOININGNUMBER",
    "BRAI",
    "BRAILLE",
    "BRAILLEPATTERNS",
    "BREAKAFTER",
    "BREAKBEFORE",
    "BREAKBOTH",
    "BREAKSYMBOLS",
    "BUGI",
    "BUGINESE",
    "BUHD",
    "BUHID",
    "BURUSHASKIYEHBARREE",
    "BYZANTINEMUSIC",
    "BYZANTINEMUSICALSYMBOLS",
    "C",
    "C&",
    "CAKM",
    "CAN",
    "CANADIANABORIGINAL",
    "CANADIANSYLLABICS",
    "CANONICAL",
    "CANONICALCOMBININGCLASS",
    "CANS",
    "CANTILLATIONMARK",
    "CARI",
    "CARIAN",
    "CARRIAGERETURN",
    "CASED",
    "CASEDLETTER",
    "CASEIGNORABLE",
    "CAUCASIANALBANIAN",
    "CB",
    "CC",
    "CCC",
    "CCC10",
    "CCC103",
    "CCC107",
    "CCC11",
    "CCC118",
    "CCC12",
    "CCC122",
    "CCC129",
    "CCC13",
    "CCC130",
    "CCC132",
    "CCC133",
    "CCC14",
    "CCC15",
    "CCC16",
    "CCC17",
    "CCC18",
    "CCC19",
    "CCC20",
    "CCC21",
    "CCC22",
    "CCC23",
    "CCC24",
    "CCC25",
    "CCC26",
    "CCC27",
    "CCC28",
    "CCC29",
    "CCC30",
    "CCC31",
    "CCC32",
    "CCC33",
    "CCC34",
    "CCC35",
    "CCC36",
    "CCC84",
    "CCC91",
    "CF",
    "CHAKMA",
    "CHAM",
    "CHANGESWHENCASEFOLDED",
    "CHANGESWHENCASEMAPPED",
    "CHANGESWHENLOWERCASED",
    "CHANGESWHENTITLECASED",
    "CHANGESWHENUPPERCASED",
    "CHER",
    "CHEROKEE",
    "CI",
    "CIRCLE",
    "CJ",
    "CJK",
    "CJKCOMPAT",
    "CJKCOMPATFORMS",
    "CJKCOMPATIBILITY",
    "CJKCOMPATIBILITYFORMS",
    "CJKCOMPATIBILITYIDEOGRAPHS",
    "CJKCOMPATIBILITYIDEOGRAPHSSUPPLEMENT",
    "CJKCOMPATIDEOGRAPHS",
    "CJKCOMPATIDEOGRAPHSSUP",
    "CJKEXTA",
    "CJKEXTB",
    "CJKEXTC",
    "CJKEXTD",
    "CJKRADICALSSUP",
    "CJKRADICALSSUPPLEMENT",
    "CJKSTROKES",
    "CJKSYMBOLS",
    "CJKSYMBOLSANDPUNCTUATION",
    "CJKUNIFIEDIDEOGRAPHS",
    "CJKUNIFIEDIDEOGRAPHSEXTENSIONA",
    "CJKUNIFIEDIDEOGRAPHSEXTENSIONB",
    "CJKUNIFIEDIDEOGRAPHSEXTENSIONC",
    "CJKUNIFIEDIDEOGRAPHSEXTENSIOND",
    "CL",
    "CLOSE",
    "CLOSEPARENTHESIS",
    "CLOSEPUNCTUATION",
    "CM",
    "CN",
    "CNTRL",
    "CO",
    "COM",
    "COMBININGDIACRITICALMARKS",
    "COMBININGDIACRITICALMARKSEXTENDED",
    "COMBININGDIACRITICALMARKSFORSYMBOLS",
    "COMBININGDIACRITICALMARKSSUPPLEMENT",
    "COMBININGHALFMARKS",
    "COMBININGMARK",
    "COMBININGMARKSFORSYMBOLS",
    "COMMON",
    "COMMONINDICNUMBERFORMS",
    "COMMONSEPARATOR",
    "COMPAT",
    "COMPATJAMO",
    "COMPLEXCONTEXT",
    "CONDITIONALJAPANESESTARTER",
    "CONNECTORPUNCTUATION",
    "CONSONANT",
    "CONSONANTDEAD",
    "CONSONANTFINAL",
    "CONSONANTHEADLETTER",
    "CONSONANTMEDIAL",
    "CONSONANTPLACEHOLDER",
    "CONSONANTPRECEDINGREPHA",
    "CONSONANTSUBJOINED",
    "CONSONANTSUCCEEDINGREPHA",
    "CONTINGENTBREAK",
    "CONTROL",
    "CONTROLPICTURES",
    "COPT",
    "COPTIC",
    "COPTICEPACTNUMBERS",
    "COUNTINGROD",
    "COUNTINGRODNUMERALS",
    "CP",
    "CPRT",
    "CR",
    "CS",
    "CUNEIFORM",
    "CUNEIFORMNUMBERS",
    "CUNEIFORMNUMBERSANDPUNCTUATION",
    "CURRENCYSYMBOL",
    "CURRENCYSYMBOLS",
    "CWCF",
    "CWCM",
    "CWL",
    "CWT",
    "CWU",
    "CYPRIOT",
    "CYPRIOTSYLLABARY",
    "CYRILLIC",
    "CYRILLICEXTA",
    "CYRILLICEXTB",
    "CYRILLICEXTENDEDA",
    "CYRILLICEXTENDEDB",
    "CYRILLICSUP",
    "CYRILLICSUPPLEMENT",
    "CYRILLICSUPPLEMENTARY",
    "CYRL",
    "D",
    "DA",
    "DAL",
    "DALATHRISH",
    "DASH",
    "DASHPUNCTUATION",
    "DB",
    "DE",
    "DECIMAL",
    "DECIMALNUMBER",
    "DECOMPOSITIONTYPE",
    "DEFAULTIGNORABLECODEPOINT",
    "DEP",
    "DEPRECATED",
    "DESERET",
    "DEVA",
    "DEVANAGARI",
    "DEVANAGARIEXT",
    "DEVANAGARIEXTENDED",
    "DI",
    "DIA",
    "DIACRITIC",
    "DIACRITICALS",
    "DIACRITICALSEXT",
    "DIACRITICALSFORSYMBOLS",
    "DIACRITICALSSUP",
    "DIGIT",
    "DINGBATS",
    "DOMINO",
    "DOMINOTILES",
    "DOUBLEABOVE",
    "DOUBLEBELOW",
    "DOUBLEQUOTE",
    "DQ",
    "DSRT",
    "DT",
    "DUALJOINING",
    "DUPL",
    "DUPLOYAN",
    "E",
    "EA",
    "EASTASIANWIDTH",
    "EGYP",
    "EGYPTIANHIEROGLYPHS",
    "ELBA",
    "ELBASAN",
    "EMOTICONS",
    "EN",
    "ENC",
    "ENCLOSEDALPHANUM",
    "ENCLOSEDALPHANUMERICS",
    "ENCLOSEDALPHANUMERICSUPPLEMENT",
    "ENCLOSEDALPHANUMSUP",
    "ENCLOSEDCJK",
    "ENCLOSEDCJKLETTERSANDMONTHS",
    "ENCLOSEDIDEOGRAPHICSUP",
    "ENCLOSEDIDEOGRAPHICSUPPLEMENT",
    "ENCLOSINGMARK",
    "ES",
    "ET",
    "ETHI",
    "ETHIOPIC",
    "ETHIOPICEXT",
    "ETHIOPICEXTA",
    "ETHIOPICEXTENDED",
    "ETHIOPICEXTENDEDA",
    "ETHIOPICSUP",
    "ETHIOPICSUPPLEMENT",
    "EUROPEANNUMBER",
    "EUROPEANSEPARATOR",
    "EUROPEANTERMINATOR",
    "EX",
    "EXCLAMATION",
    "EXT",
    "EXTEND",
    "EXTENDER",
    "EXTENDNUMLET",
    "F",
    "FALSE",
    "FARSIYEH",
    "FE",
    "FEH",
    "FIN",
    "FINAL",
    "FINALPUNCTUATION",
    "FINALSEMKATH",
    "FIRSTSTRONGISOLATE",
    "FO",
    "FONT",
    "FORMAT",
    "FRA",
    "FRACTION",
    "FSI",
    "FULLWIDTH",
    "GAF",
    "GAMAL",
    "GC",
    "GCB",
    "GEMINATIONMARK",
    "GENERALCATEGORY",
    "GENERALPUNCTUATION",
    "GEOMETRICSHAPES",
    "GEOMETRICSHAPESEXT",
    "GEOMETRICSHAPESEXTENDED",
    "GEOR",
    "GEORGIAN",
    "GEORGIANSUP",
    "GEORGIANSUPPLEMENT",
    "GL",
    "GLAG",
    "GLAGOLITIC",
    "GLUE",
    "GOTH",
    "GOTHIC",
    "GRAN",
    "GRANTHA",
    "GRAPH",
    "GRAPHEMEBASE",
    "GRAPHEMECLUSTERBREAK",
    "GRAPHEMEEXTEND",
    "GRAPHEMELINK",
    "GRBASE",
    "GREEK",
    "GREEKANDCOPTIC",
    "GREEKEXT",
    "GREEKEXTENDED",
    "GREK",
    "GREXT",
    "GRLINK",
    "GUJARATI",
    "GUJR",
    "GURMUKHI",
    "GURU",
    "H",
    "H2",
    "H3",
    "HAH",
    "HALFANDFULLFORMS",
    "HALFMARKS",
    "HALFWIDTH",
    "HALFWIDTHANDFULLWIDTHFORMS",
    "HAMZAONHEHGOAL",
    "HAN",
    "HANG",
    "HANGUL",
    "HANGULCOMPATIBILITYJAMO",
    "HANGULJAMO",
    "HANGULJAMOEXTENDEDA",
    "HANGULJAMOEXTENDEDB",
    "HANGULSYLLABLES",
    "HANGULSYLLABLETYPE",
    "HANI",
    "HANO",
    "HANUNOO",
    "HE",
    "HEBR",
    "HEBREW",
    "HEBREWLETTER",
    "HEH",
    "HEHGOAL",
    "HETH",
    "HEX",
    "HEXDIGIT",
    "HIGHPRIVATEUSESURROGATES",
    "HIGHPUSURROGATES",
    "HIGHSURROGATES",
    "HIRA",
    "HIRAGANA",
    "HL",
    "HMNG",
    "HRKT",
    "HST",
    "HY",
    "HYPHEN",
    "ID",
    "IDC",
    "IDCONTINUE",
    "IDEO",
    "IDEOGRAPHIC",
    "IDEOGRAPHICDESCRIPTIONCHARACTERS",
    "IDS",
    "IDSB",
    "IDSBINARYOPERATOR",
    "IDST",
    "IDSTART",
    "IDSTRINARYOPERATOR",
    "IMPERIALARAMAIC",
    "IN",
    "INDICMATRACATEGORY",
    "INDICNUMBERFORMS",
    "INDICSYLLABICCATEGORY",
    "INFIXNUMERIC",
    "INHERITED",
    "INIT",
    "INITIAL",
    "INITIALPUNCTUATION",
    "INMC",
    "INSC",
    "INSCRIPTIONALPAHLAVI",
    "INSCRIPTIONALPARTHIAN",
    "INSEPARABLE",
    "INSEPERABLE",
    "INVISIBLESTACKER",
    "IOTASUBSCRIPT",
    "IPAEXT",
    "IPAEXTENSIONS",
    "IS",
    "ISO",
    "ISOLATED",
    "ITAL",
    "JAMO",
    "JAMOEXTA",
    "JAMOEXTB",
    "JAVA",
    "JAVANESE",
    "JG",
    "JL",
    "JOINC",
    "JOINCAUSING",
    "JOINCONTROL",
    "JOINER",
    "JOININGGROUP",
    "JOININGTYPE",
    "JT",
    "JV",
    "KA",
    "KAF",
    "KAITHI",
    "KALI",
    "KANA",
    "KANASUP",
    "KANASUPPLEMENT",
    "KANAVOICING",
    "KANBUN",
    "KANGXI",
    "KANGXIRADICALS",
    "KANNADA",
    "KAPH",
    "KATAKANA",
    "KATAKANAEXT",
    "KATAKANAORHIRAGANA",
    "KATAKANAPHONETICEXTENSIONS",
    "KAYAHLI",
    "KHAPH",
    "KHAR",
    "KHAROSHTHI",
    "KHMER",
    "KHMERSYMBOLS",
    "KHMR",
    "KHOJ",
    "KHOJKI",
    "KHUDAWADI",
    "KNDA",
    "KNOTTEDHEH",
    "KTHI",
    "KV",
    "L",
    "L&",
    "LAM",
    "LAMADH",
    "LANA",
    "LAO",
    "LAOO",
    "LATIN",
    "LATIN1",
    "LATIN1SUP",
    "LATIN1SUPPLEMENT",
    "LATINEXTA",
    "LATINEXTADDITIONAL",
    "LATINEXTB",
    "LATINEXTC",
    "LATINEXTD",
    "LATINEXTE",
    "LATINEXTENDEDA",
    "LATINEXTENDEDADDITIONAL",
    "LATINEXTENDEDB",
    "LATINEXTENDEDC",
    "LATINEXTENDEDD",
    "LATINEXTENDEDE",
    "LATN",
    "LB",
    "LC",
    "LE",
    "LEADINGJAMO",
    "LEFT",
    "LEFTANDRIGHT",
    "LEFTJOINING",
    "LEFTTORIGHT",
    "LEFTTORIGHTEMBEDDING",
    "LEFTTORIGHTISOLATE",
    "LEFTTORIGHTOVERRIDE",
    "LEPC",
    "LEPCHA",
    "LETTER",
    "LETTERLIKESYMBOLS",
    "LETTERNUMBER",
    "LF",
    "LIMB",
    "LIMBU",
    "LINA",
    "LINB",
    "LINEARA",
    "LINEARB",
    "LINEARBIDEOGRAMS",
    "LINEARBSYLLABARY",
    "LINEBREAK",
    "LINEFEED",
    "LINESEPARATOR",
    "LISU",
    "LL",
    "LM",
    "LO",
    "LOE",
    "LOGICALORDEREXCEPTION",
    "LOWER",
    "LOWERCASE",
    "LOWERCASELETTER",
    "LOWSURROGATES",
    "LRE",
    "LRI",
    "LRO",
    "LT",
    "LU",
    "LV",
    "LVSYLLABLE",
    "LVT",
    "LVTSYLLABLE",
    "LYCI",
    "LYCIAN",
    "LYDI",
    "LYDIAN",
    "M",
    "M&",
    "MAHAJANI",
    "MAHJ",
    "MAHJONG",
    "MAHJONGTILES",
    "MALAYALAM",
    "MAND",
    "MANDAIC",
    "MANDATORYBREAK",
    "MANI",
    "MANICHAEAN",
    "MANICHAEANALEPH",
    "MANICHAEANAYIN",
    "MANICHAEANBETH",
    "MANICHAEANDALETH",
    "MANICHAEANDHAMEDH",
    "MANICHAEANFIVE",
    "MANICHAEANGIMEL",
    "MANICHAEANHETH",
    "MANICHAEANHUNDRED",
    "MANICHAEANKAPH",
    "MANICHAEANLAMEDH",
    "MANICHAEANMEM",
    "MANICHAEANNUN",
    "MANICHAEANONE",
    "MANICHAEANPE",
    "MANICHAEANQOPH",
    "MANICHAEANRESH",
    "MANICHAEANSADHE",
    "MANICHAEANSAMEKH",
    "MANICHAEANTAW",
    "MANICHAEANTEN",
    "MANICHAEANTETH",
    "MANICHAEANTHAMEDH",
    "MANICHAEANTWENTY",
    "MANICHAEANWAW",
    "MANICHAEANYODH",
    "MANICHAEANZAYIN",
    "MARK",
    "MATH",
    "MATHALPHANUM",
    "MATHEMATICALALPHANUMERICSYMBOLS",
    "MATHEMATICALOPERATORS",
    "MATHOPERATORS",
    "MATHSYMBOL",
    "MB",
    "MC",
    "ME",
    "MED",
    "MEDIAL",
    "MEEM",
    "MEETEIMAYEK",
    "MEETEIMAYEKEXT",
    "MEETEIMAYEKEXTENSIONS",
    "MEND",
    "MENDEKIKAKUI",
    "MERC",
    "MERO",
    "MEROITICCURSIVE",
    "MEROITICHIEROGLYPHS",
    "MIAO",
    "MIDLETTER",
    "MIDNUM",
    "MIDNUMLET",
    "MIM",
    "MISCARROWS",
    "MISCELLANEOUSMATHEMATICALSYMBOLSA",
    "MISCELLANEOUSMATHEMATICALSYMBOLSB",
    "MISCELLANEOUSSYMBOLS",
    "MISCELLANEOUSSYMBOLSANDARROWS",
    "MISCELLANEOUSSYMBOLSANDPICTOGRAPHS",
    "MISCELLANEOUSTECHNICAL",
    "MISCMATHSYMBOLSA",
    "MISCMATHSYMBOLSB",
    "MISCPICTOGRAPHS",
    "MISCSYMBOLS",
    "MISCTECHNICAL",
    "ML",
    "MLYM",
    "MN",
    "MODI",
    "MODIFIERLETTER",
    "MODIFIERLETTERS",
    "MODIFIERSYMBOL",
    "MODIFIERTONELETTERS",
    "MODIFYINGLETTER",
    "MONG",
    "MONGOLIAN",
    "MRO",
    "MROO",
    "MTEI",
    "MUSIC",
    "MUSICALSYMBOLS",
    "MYANMAR",
    "MYANMAREXTA",
    "MYANMAREXTB",
    "MYANMAREXTENDEDA",
    "MYANMAREXTENDEDB",
    "MYMR",
    "N",
    "N&",
    "NA",
    "NABATAEAN",
    "NAN",
    "NAR",
    "NARB",
    "NARROW",
    "NB",
    "NBAT",
    "NCHAR",
    "ND",
    "NEUTRAL",
    "NEWLINE",
    "NEWTAILUE",
    "NEXTLINE",
    "NK",
    "NKO",
    "NKOO",
    "NL",
    "NO",
    "NOBLOCK",
    "NOBREAK",
    "NOJOININGGROUP",
    "NONCHARACTERCODEPOINT",
    "NONE",
    "NONJOINER",
    "NONJOINING",
    "NONSPACINGMARK",
    "NONSTARTER",
    "NOON",
    "NOTAPPLICABLE",
    "NOTREORDERED",
    "NR",
    "NS",
    "NSM",
    "NT",
    "NU",
    "NUKTA",
    "NUMBER",
    "NUMBERFORMS",
    "NUMBERJOINER",
    "NUMERIC",
    "NUMERICTYPE",
    "NUMERICVALUE",
    "NUN",
    "NV",
    "NYA",
    "OALPHA",
    "OCR",
    "ODI",
    "OGAM",
    "OGHAM",
    "OGREXT",
    "OIDC",
    "OIDS",
    "OLCHIKI",
    "OLCK",
    "OLDITALIC",
    "OLDNORTHARABIAN",
    "OLDPERMIC",
    "OLDPERSIAN",
    "OLDSOUTHARABIAN",
    "OLDTURKIC",
    "OLETTER",
    "OLOWER",
    "OMATH",
    "ON",
    "OP",
    "OPENPUNCTUATION",
    "OPTICALCHARACTERRECOGNITION",
    "ORIYA",
    "ORKH",
    "ORNAMENTALDINGBATS",
    "ORYA",
    "OSMA",
    "OSMANYA",
    "OTHER",
    "OTHERALPHABETIC",
    "OTHERDEFAULTIGNORABLECODEPOINT",
    "OTHERGRAPHEMEEXTEND",
    "OTHERIDCONTINUE",
    "OTHERIDSTART",
    "OTHERLETTER",
    "OTHERLOWERCASE",
    "OTHERMATH",
    "OTHERNEUTRAL",
    "OTHERNUMBER",
    "OTHERPUNCTUATION",
    "OTHERSYMBOL",
    "OTHERUPPERCASE",
    "OUPPER",
    "OV",
    "OVERLAY",
    "OVERSTRUCK",
    "P",
    "P&",
    "PAHAWHHMONG",
    "PALM",
    "PALMYRENE",
    "PARAGRAPHSEPARATOR",
    "PATSYN",
    "PATTERNSYNTAX",
    "PATTERNWHITESPACE",
    "PATWS",
    "PAUC",
    "PAUCINHAU",
    "PC",
    "PD",
    "PDF",
    "PDI",
    "PE",
    "PERM",
    "PF",
    "PHAG",
    "PHAGSPA",
    "PHAISTOS",
    "PHAISTOSDISC",
    "PHLI",
    "PHLP",
    "PHNX",
    "PHOENICIAN",
    "PHONETICEXT",
    "PHONETICEXTENSIONS",
    "PHONETICEXTENSIONSSUPPLEMENT",
    "PHONETICEXTSUP",
    "PI",
    "PLAYINGCARDS",
    "PLRD",
    "PO",
    "POPDIRECTIONALFORMAT",
    "POPDIRECTIONALISOLATE",
    "POSTFIXNUMERIC",
    "PP",
    "PR",
    "PREFIXNUMERIC",
    "PREPEND",
    "PRINT",
    "PRIVATEUSE",
    "PRIVATEUSEAREA",
    "PRTI",
    "PS",
    "PSALTERPAHLAVI",
    "PUA",
    "PUNCT",
    "PUNCTUATION",
    "PUREKILLER",
    "QAAC",
    "QAAI",
    "QAF",
    "QAPH",
    "QMARK",
    "QU",
    "QUOTATION",
    "QUOTATIONMARK",
    "R",
    "RADICAL",
    "REGIONALINDICATOR",
    "REGISTERSHIFTER",
    "REH",
    "REJANG",
    "REVERSEDPE",
    "RI",
    "RIGHT",
    "RIGHTJOINING",
    "RIGHTTOLEFT",
    "RIGHTTOLEFTEMBEDDING",
    "RIGHTTOLEFTISOLATE",
    "RIGHTTOLEFTOVERRIDE",
    "RJNG",
    "RLE",
    "RLI",
    "RLO",
    "ROHINGYAYEH",
    "RUMI",
    "RUMINUMERALSYMBOLS",
    "RUNIC",
    "RUNR",
    "S",
    "S&",
    "SA",
    "SAD",
    "SADHE",
    "SAMARITAN",
    "SAMR",
    "SARB",
    "SAUR",
    "SAURASHTRA",
    "SB",
    "SC",
    "SCONTINUE",
    "SCRIPT",
    "SD",
    "SE",
    "SEEN",
    "SEGMENTSEPARATOR",
    "SEMKATH",
    "SENTENCEBREAK",
    "SEP",
    "SEPARATOR",
    "SG",
    "SHARADA",
    "SHAVIAN",
    "SHAW",
    "SHIN",
    "SHORTHANDFORMATCONTROLS",
    "SHRD",
    "SIDD",
    "SIDDHAM",
    "SIND",
    "SINGLEQUOTE",
    "SINH",
    "SINHALA",
    "SINHALAARCHAICNUMBERS",
    "SK",
    "SM",
    "SMALL",
    "SMALLFORMS",
    "SMALLFORMVARIANTS",
    "SML",
    "SO",
    "SOFTDOTTED",
    "SORA",
    "SORASOMPENG",
    "SP",
    "SPACE",
    "SPACESEPARATOR",
    "SPACINGMARK",
    "SPACINGMODIFIERLETTERS",
    "SPECIALS",
    "SQ",
    "SQR",
    "SQUARE",
    "ST",
    "STERM",
    "STRAIGHTWAW",
    "SUB",
    "SUND",
    "SUNDANESE",
    "SUNDANESESUP",
    "SUNDANESESUPPLEMENT",
    "SUP",
    "SUPARROWSA",
    "SUPARROWSB",
    "SUPARROWSC",
    "SUPER",
    "SUPERANDSUB",
    "SUPERSCRIPTSANDSUBSCRIPTS",
    "SUPMATHOPERATORS",
    "SUPPLEMENTALARROWSA",
    "SUPPLEMENTALARROWSB",
    "SUPPLEMENTALARROWSC",
    "SUPPLEMENTALMATHEMATICALOPERATORS",
    "SUPPLEMENTALPUNCTUATION",
    "SUPPLEMENTARYPRIVATEUSEAREAA",
    "SUPPLEMENTARYPRIVATEUSEAREAB",
    "SUPPUAA",
    "SUPPUAB",
    "SUPPUNCTUATION",
    "SURROGATE",
    "SWASHKAF",
    "SY",
    "SYLO",
    "SYLOTINAGRI",
    "SYMBOL",
    "SYRC",
    "SYRIAC",
    "SYRIACWAW",
    "T",
    "TAGALOG",
    "TAGB",
    "TAGBANWA",
    "TAGS",
    "TAH",
    "TAILE",
    "TAITHAM",
    "TAIVIET",
    "TAIXUANJING",
    "TAIXUANJINGSYMBOLS",
    "TAKR",
    "TAKRI",
    "TALE",
    "TALU",
    "TAMIL",
    "TAML",
    "TAVT",
    "TAW",
    "TEHMARBUTA",
    "TEHMARBUTAGOAL",
    "TELU",
    "TELUGU",
    "TERM",
    "TERMINALPUNCTUATION",
    "TETH",
    "TFNG",
    "TGLG",
    "THAA",
    "THAANA",
    "THAI",
    "TIBETAN",
    "TIBT",
    "TIFINAGH",
    "TIRH",
    "TIRHUTA",
    "TITLECASELETTER",
    "TONELETTER",
    "TONEMARK",
    "TOP",
    "TOPANDBOTTOM",
    "TOPANDBOTTOMANDRIGHT",
    "TOPANDLEFT",
    "TOPANDLEFTANDRIGHT",
    "TOPANDRIGHT",
    "TRAILINGJAMO",
    "TRANSPARENT",
    "TRANSPORTANDMAP",
    "TRANSPORTANDMAPSYMBOLS",
    "TRUE",
    "U",
    "UCAS",
    "UCASEXT",
    "UGAR",
    "UGARITIC",
    "UIDEO",
    "UNASSIGNED",
    "UNIFIEDCANADIANABORIGINALSYLLABICS",
    "UNIFIEDCANADIANABORIGINALSYLLABICSEXTENDED",
    "UNIFIEDIDEOGRAPH",
    "UNKNOWN",
    "UP",
    "UPPER",
    "UPPERCASE",
    "UPPERCASELETTER",
    "V",
    "VAI",
    "VAII",
    "VARIATIONSELECTOR",
    "VARIATIONSELECTORS",
    "VARIATIONSELECTORSSUPPLEMENT",
    "VEDICEXT",
    "VEDICEXTENSIONS",
    "VERT",
    "VERTICAL",
    "VERTICALFORMS",
    "VIRAMA",
    "VISARGA",
    "VISUALORDERLEFT",
    "VOWEL",
    "VOWELDEPENDENT",
    "VOWELINDEPENDENT",
    "VOWELJAMO",
    "VR",
    "VS",
    "VSSUP",
    "W",
    "WARA",
    "WARANGCITI",
    "WAW",
    "WB",
    "WHITESPACE",
    "WIDE",
    "WJ",
    "WORD",
    "WORDBREAK",
    "WORDJOINER",
    "WS",
    "WSPACE",
    "XDIGIT",
    "XIDC",
    "XIDCONTINUE",
    "XIDS",
    "XIDSTART",
    "XPEO",
    "XSUX",
    "XX",
    "Y",
    "YEH",
    "YEHBARREE",
    "YEHWITHTAIL",
    "YES",
    "YI",
    "YIII",
    "YIJING",
    "YIJINGHEXAGRAMSYMBOLS",
    "YIRADICALS",
    "YISYLLABLES",
    "YUDH",
    "YUDHHE",
    "Z",
    "Z&",
    "ZAIN",
    "ZHAIN",
    "ZINH",
    "ZL",
    "ZP",
    "ZS",
    "ZW",
    "ZWSPACE",
    "ZYYY",
    "ZZZZ",
};

/* strings: 11780 bytes. */

/* properties. */

RE_Property re_properties[] = {
    { 525,  0,  0},
    { 522,  0,  0},
    { 238,  1,  1},
    { 237,  1,  1},
    {1048,  2,  2},
    {1046,  2,  2},
    {1220,  3,  3},
    {1215,  3,  3},
    { 544,  4,  4},
    { 523,  4,  4},
    {1054,  5,  5},
    {1045,  5,  5},
    { 797,  6,  6},
    { 159,  7,  6},
    { 158,  7,  6},
    { 741,  8,  6},
    { 740,  8,  6},
    {1188,  9,  6},
    {1187,  9,  6},
    { 280, 10,  6},
    { 282, 11,  6},
    { 334, 11,  6},
    { 329, 12,  6},
    { 412, 12,  6},
    { 331, 13,  6},
    { 414, 13,  6},
    { 330, 14,  6},
    { 413, 14,  6},
    { 327, 15,  6},
    { 410, 15,  6},
    { 328, 16,  6},
    { 411, 16,  6},
    { 610, 17,  6},
    { 606, 17,  6},
    { 602, 18,  6},
    { 601, 18,  6},
    {1228, 19,  6},
    {1227, 19,  6},
    {1226, 20,  6},
    {1225, 20,  6},
    { 437, 21,  6},
    { 445, 21,  6},
    { 545, 22,  6},
    { 553, 22,  6},
    { 543, 23,  6},
    { 547, 23,  6},
    { 546, 24,  6},
    { 554, 24,  6},
    {1216, 25,  6},
    {1223, 25,  6},
    {1082, 25,  6},
    { 230, 26,  6},
    { 228, 26,  6},
    { 645, 27,  6},
    { 643, 27,  6},
    { 430, 28,  6},
    { 599, 29,  6},
    {1011, 30,  6},
    {1008, 30,  6},
    {1149, 31,  6},
    {1148, 31,  6},
    { 942, 32,  6},
    { 923, 32,  6},
    { 588, 33,  6},
    { 587, 33,  6},
    { 190, 34,  6},
    { 148, 34,  6},
    { 935, 35,  6},
    { 905, 35,  6},
    { 604, 36,  6},
    { 603, 36,  6},
    { 447, 37,  6},
    { 446, 37,  6},
    { 501, 38,  6},
    { 499, 38,  6},
    { 941, 39,  6},
    { 922, 39,  6},
    { 947, 40,  6},
    { 948, 40,  6},
    { 881, 41,  6},
    { 867, 41,  6},
    { 937, 42,  6},
    { 910, 42,  6},
    { 608, 43,  6},
    { 607, 43,  6},
    { 611, 44,  6},
    { 609, 44,  6},
    {1013, 45,  6},
    {1184, 46,  6},
    {1180, 46,  6},
    { 936, 47,  6},
    { 907, 47,  6},
    { 439, 48,  6},
    { 438, 48,  6},
    {1078, 49,  6},
    {1049, 49,  6},
    { 739, 50,  6},
    { 738, 50,  6},
    { 939, 51,  6},
    { 912, 51,  6},
    { 938, 52,  6},
    { 911, 52,  6},
    {1091, 53,  6},
    {1193, 54,  6},
    {1209, 54,  6},
    { 960, 55,  6},
    { 961, 55,  6},
    { 959, 56,  6},
    { 958, 56,  6},
    { 576, 57,  7},
    { 597, 57,  7},
    { 229, 58,  8},
    { 220, 58,  8},
    { 274, 59,  9},
    { 286, 59,  9},
    { 436, 60, 10},
    { 461, 60, 10},
    { 467, 61, 11},
    { 466, 61, 11},
    { 647, 62, 12},
    { 641, 62, 12},
    { 648, 63, 13},
    { 649, 63, 13},
    { 731, 64, 14},
    { 706, 64, 14},
    { 900, 65, 15},
    { 893, 65, 15},
    { 901, 66, 16},
    { 903, 66, 16},
    { 232, 67,  6},
    { 231, 67,  6},
    { 614, 68, 17},
    { 622, 68, 17},
    { 616, 69, 18},
    { 623, 69, 18},
    { 162, 70,  6},
    { 157, 70,  6},
    { 169, 71,  6},
    { 236, 72,  6},
    { 542, 73,  6},
    { 994, 74,  6},
    {1219, 75,  6},
    {1224, 76,  6},
};

/* properties: 572 bytes. */

/* property values. */

RE_PropertyValue re_property_values[] = {
    {1181,  0,   0},
    { 365,  0,   0},
    {1189,  0,   1},
    { 748,  0,   1},
    { 742,  0,   2},
    { 735,  0,   2},
    {1161,  0,   3},
    { 747,  0,   3},
    { 839,  0,   4},
    { 736,  0,   4},
    { 940,  0,   5},
    { 737,  0,   5},
    { 885,  0,   6},
    { 837,  0,   6},
    { 483,  0,   7},
    { 805,  0,   7},
    {1084,  0,   8},
    { 804,  0,   8},
    { 435,  0,   9},
    { 868,  0,   9},
    { 452,  0,   9},
    { 721,  0,  10},
    { 876,  0,  10},
    { 944,  0,  11},
    { 877,  0,  11},
    {1083,  0,  12},
    {1252,  0,  12},
    { 733,  0,  13},
    {1250,  0,  13},
    { 957,  0,  14},
    {1251,  0,  14},
    { 394,  0,  15},
    { 285,  0,  15},
    { 366,  0,  15},
    { 515,  0,  16},
    { 324,  0,  16},
    { 995,  0,  17},
    { 367,  0,  17},
    {1116,  0,  18},
    { 404,  0,  18},
    { 431,  0,  19},
    { 965,  0,  19},
    { 926,  0,  20},
    { 998,  0,  20},
    { 363,  0,  21},
    { 968,  0,  21},
    { 383,  0,  22},
    { 964,  0,  22},
    { 945,  0,  23},
    { 986,  0,  23},
    { 802,  0,  24},
    {1072,  0,  24},
    { 408,  0,  25},
    {1046,  0,  25},
    { 841,  0,  26},
    {1071,  0,  26},
    { 946,  0,  27},
    {1077,  0,  27},
    { 621,  0,  28},
    { 983,  0,  28},
    { 510,  0,  29},
    { 970,  0,  29},
    { 934,  0,  30},
    { 267,  0,  30},
    { 268,  0,  30},
    { 719,  0,  31},
    { 682,  0,  31},
    { 683,  0,  31},
    { 796,  0,  32},
    { 757,  0,  32},
    { 374,  0,  32},
    { 758,  0,  32},
    { 896,  0,  33},
    { 857,  0,  33},
    { 858,  0,  33},
    {1002,  0,  34},
    { 952,  0,  34},
    {1001,  0,  34},
    { 953,  0,  34},
    {1121,  0,  35},
    {1035,  0,  35},
    {1036,  0,  35},
    {1056,  0,  36},
    {1245,  0,  36},
    {1246,  0,  36},
    { 281,  0,  37},
    { 707,  0,  37},
    { 191,  0,  38},
    { 878,  1,   0},
    { 865,  1,   0},
    { 214,  1,   1},
    { 189,  1,   1},
    { 692,  1,   2},
    { 691,  1,   2},
    { 690,  1,   2},
    { 699,  1,   3},
    { 693,  1,   3},
    { 701,  1,   4},
    { 695,  1,   4},
    { 631,  1,   5},
    { 630,  1,   5},
    {1085,  1,   6},
    { 840,  1,   6},
    { 369,  1,   7},
    { 448,  1,   7},
    { 549,  1,   8},
    { 548,  1,   8},
    { 417,  1,   9},
    { 423,  1,  10},
    { 422,  1,  10},
    { 424,  1,  10},
    { 185,  1,  11},
    { 582,  1,  12},
    { 172,  1,  13},
    {1123,  1,  14},
    { 184,  1,  15},
    { 183,  1,  15},
    {1154,  1,  16},
    { 874,  1,  17},
    {1040,  1,  18},
    { 765,  1,  19},
    { 174,  1,  20},
    { 173,  1,  20},
    { 442,  1,  21},
    { 226,  1,  22},
    { 557,  1,  23},
    { 555,  1,  24},
    { 928,  1,  25},
    {1140,  1,  26},
    {1147,  1,  27},
    { 662,  1,  28},
    { 763,  1,  29},
    {1069,  1,  30},
    {1155,  1,  31},
    { 687,  1,  32},
    {1156,  1,  33},
    { 851,  1,  34},
    { 531,  1,  35},
    { 572,  1,  36},
    { 636,  1,  36},
    { 487,  1,  37},
    { 493,  1,  38},
    { 492,  1,  38},
    { 333,  1,  39},
    {1182,  1,  40},
    {1176,  1,  40},
    { 272,  1,  40},
    { 909,  1,  41},
    {1033,  1,  42},
    {1126,  1,  43},
    { 579,  1,  44},
    { 263,  1,  45},
    {1128,  1,  46},
    { 672,  1,  47},
    { 845,  1,  48},
    {1183,  1,  49},
    {1177,  1,  49},
    { 724,  1,  50},
    {1131,  1,  51},
    { 871,  1,  52},
    { 673,  1,  53},
    { 261,  1,  54},
    {1132,  1,  55},
    { 370,  1,  56},
    { 449,  1,  56},
    { 209,  1,  57},
    {1095,  1,  58},
    { 217,  1,  59},
    { 718,  1,  60},
    { 913,  1,  61},
    {1097,  1,  62},
    {1096,  1,  62},
    {1197,  1,  63},
    {1196,  1,  63},
    { 980,  1,  64},
    { 979,  1,  64},
    { 981,  1,  65},
    { 982,  1,  65},
    { 372,  1,  66},
    { 451,  1,  66},
    { 700,  1,  67},
    { 694,  1,  67},
    { 551,  1,  68},
    { 550,  1,  68},
    { 526,  1,  69},
    {1002,  1,  69},
    {1104,  1,  70},
    {1103,  1,  70},
    { 409,  1,  71},
    { 371,  1,  72},
    { 450,  1,  72},
    { 375,  1,  72},
    { 720,  1,  73},
    { 897,  1,  74},
    { 188,  1,  75},
    { 800,  1,  76},
    { 801,  1,  76},
    { 829,  1,  77},
    { 834,  1,  77},
    { 395,  1,  78},
    { 927,  1,  79},
    { 906,  1,  79},
    { 476,  1,  80},
    { 475,  1,  80},
    { 248,  1,  81},
    { 239,  1,  82},
    { 527,  1,  83},
    { 826,  1,  84},
    { 833,  1,  84},
    { 453,  1,  85},
    { 824,  1,  86},
    { 830,  1,  86},
    {1106,  1,  87},
    {1099,  1,  87},
    { 255,  1,  88},
    { 254,  1,  88},
    {1107,  1,  89},
    {1100,  1,  89},
    { 825,  1,  90},
    { 831,  1,  90},
    {1109,  1,  91},
    {1105,  1,  91},
    { 827,  1,  92},
    { 823,  1,  92},
    { 536,  1,  93},
    { 702,  1,  94},
    { 696,  1,  94},
    { 397,  1,  95},
    { 533,  1,  96},
    { 532,  1,  96},
    {1158,  1,  97},
    { 490,  1,  98},
    { 488,  1,  98},
    { 420,  1,  99},
    { 418,  1,  99},
    {1110,  1, 100},
    {1115,  1, 100},
    { 351,  1, 101},
    { 350,  1, 101},
    { 661,  1, 102},
    { 660,  1, 102},
    { 605,  1, 103},
    { 601,  1, 103},
    { 354,  1, 104},
    { 353,  1, 104},
    { 593,  1, 105},
    { 664,  1, 106},
    { 242,  1, 107},
    { 571,  1, 108},
    { 380,  1, 108},
    { 659,  1, 109},
    { 244,  1, 110},
    { 243,  1, 110},
    { 352,  1, 111},
    { 667,  1, 112},
    { 665,  1, 112},
    { 480,  1, 113},
    { 479,  1, 113},
    { 340,  1, 114},
    { 338,  1, 114},
    { 356,  1, 115},
    { 346,  1, 115},
    {1240,  1, 116},
    {1239,  1, 116},
    { 355,  1, 117},
    { 337,  1, 117},
    {1242,  1, 118},
    {1241,  1, 119},
    { 734,  1, 120},
    {1191,  1, 121},
    { 421,  1, 122},
    { 419,  1, 122},
    { 211,  1, 123},
    { 842,  1, 124},
    { 703,  1, 125},
    { 697,  1, 125},
    {1120,  1, 126},
    { 377,  1, 127},
    { 615,  1, 127},
    { 972,  1, 128},
    {1044,  1, 129},
    { 444,  1, 130},
    { 443,  1, 130},
    { 668,  1, 131},
    {1017,  1, 132},
    { 573,  1, 133},
    { 637,  1, 133},
    { 640,  1, 134},
    { 855,  1, 135},
    { 853,  1, 135},
    { 326,  1, 136},
    { 854,  1, 137},
    { 852,  1, 137},
    {1133,  1, 138},
    { 811,  1, 139},
    { 810,  1, 139},
    { 491,  1, 140},
    { 489,  1, 140},
    { 704,  1, 141},
    { 698,  1, 141},
    { 809,  1, 142},
    { 575,  1, 143},
    { 570,  1, 143},
    { 574,  1, 144},
    { 638,  1, 144},
    { 591,  1, 145},
    { 589,  1, 146},
    { 590,  1, 146},
    { 743,  1, 147},
    { 996,  1, 148},
    {1000,  1, 148},
    { 995,  1, 148},
    { 342,  1, 149},
    { 344,  1, 149},
    { 161,  1, 150},
    { 160,  1, 150},
    { 181,  1, 151},
    { 179,  1, 151},
    {1194,  1, 152},
    {1209,  1, 152},
    {1200,  1, 153},
    { 373,  1, 154},
    { 564,  1, 154},
    { 341,  1, 155},
    { 339,  1, 155},
    {1075,  1, 156},
    {1074,  1, 156},
    { 182,  1, 157},
    { 180,  1, 157},
    { 566,  1, 158},
    { 563,  1, 158},
    {1086,  1, 159},
    { 730,  1, 160},
    { 729,  1, 161},
    { 146,  1, 162},
    { 167,  1, 163},
    { 168,  1, 164},
    { 974,  1, 165},
    { 973,  1, 165},
    { 754,  1, 166},
    { 278,  1, 167},
    { 398,  1, 168},
    { 915,  1, 169},
    { 539,  1, 170},
    { 917,  1, 171},
    {1179,  1, 172},
    { 918,  1, 173},
    { 440,  1, 174},
    {1059,  1, 175},
    { 933,  1, 176},
    { 471,  1, 177},
    { 283,  1, 178},
    { 727,  1, 179},
    { 416,  1, 180},
    { 612,  1, 181},
    { 956,  1, 182},
    { 860,  1, 183},
    { 978,  1, 184},
    { 756,  1, 185},
    { 817,  1, 186},
    { 816,  1, 187},
    { 671,  1, 188},
    { 919,  1, 189},
    { 916,  1, 190},
    { 768,  1, 191},
    { 203,  1, 192},
    { 625,  1, 193},
    { 624,  1, 194},
    { 999,  1, 195},
    { 920,  1, 196},
    {1032,  1, 197},
    {1031,  1, 197},
    { 251,  1, 198},
    { 653,  1, 199},
    {1080,  1, 200},
    { 325,  1, 201},
    { 759,  1, 202},
    {1058,  1, 203},
    {1070,  1, 204},
    { 676,  1, 205},
    { 677,  1, 206},
    { 541,  1, 207},
    {1160,  1, 208},
    {1065,  1, 209},
    { 838,  1, 210},
    {1137,  1, 211},
    {1213,  1, 212},
    { 963,  1, 213},
    { 405,  1, 214},
    { 407,  1, 215},
    { 406,  1, 215},
    { 469,  1, 216},
    { 213,  1, 217},
    { 212,  1, 217},
    { 846,  1, 218},
    { 216,  1, 219},
    { 954,  1, 220},
    { 818,  1, 221},
    { 657,  1, 222},
    { 656,  1, 222},
    { 464,  1, 223},
    {1062,  1, 224},
    { 266,  1, 225},
    { 265,  1, 225},
    { 850,  1, 226},
    { 849,  1, 226},
    { 166,  1, 227},
    { 165,  1, 227},
    {1135,  1, 228},
    {1134,  1, 228},
    { 400,  1, 229},
    { 399,  1, 229},
    { 799,  1, 230},
    { 798,  1, 230},
    { 813,  1, 231},
    { 177,  1, 232},
    { 176,  1, 232},
    { 762,  1, 233},
    { 761,  1, 233},
    { 455,  1, 234},
    { 454,  1, 234},
    { 984,  1, 235},
    { 477,  1, 236},
    { 478,  1, 236},
    { 482,  1, 237},
    { 481,  1, 237},
    { 828,  1, 238},
    { 832,  1, 238},
    { 472,  1, 239},
    { 930,  1, 240},
    {1173,  1, 241},
    {1172,  1, 241},
    { 154,  1, 242},
    { 153,  1, 242},
    { 529,  1, 243},
    { 528,  1, 243},
    {1108,  1, 244},
    {1101,  1, 244},
    { 357,  1, 245},
    { 347,  1, 245},
    { 358,  1, 246},
    { 348,  1, 246},
    { 359,  1, 247},
    { 349,  1, 247},
    { 343,  1, 248},
    { 345,  1, 248},
    {1129,  1, 249},
    {1195,  1, 250},
    {1210,  1, 250},
    {1111,  1, 251},
    {1113,  1, 251},
    {1112,  1, 252},
    {1114,  1, 252},
    {1185,  2,   0},
    {1256,  2,   0},
    { 376,  2,   1},
    {1255,  2,   1},
    { 689,  2,   2},
    { 705,  2,   2},
    { 548,  2,   3},
    { 552,  2,   3},
    { 417,  2,   4},
    { 425,  2,   4},
    { 185,  2,   5},
    { 187,  2,   5},
    { 582,  2,   6},
    { 581,  2,   6},
    { 172,  2,   7},
    { 171,  2,   7},
    {1123,  2,   8},
    {1122,  2,   8},
    {1154,  2,   9},
    {1153,  2,   9},
    { 442,  2,  10},
    { 441,  2,  10},
    { 226,  2,  11},
    { 225,  2,  11},
    { 557,  2,  12},
    { 558,  2,  12},
    { 555,  2,  13},
    { 556,  2,  13},
    { 928,  2,  14},
    { 931,  2,  14},
    {1140,  2,  15},
    {1141,  2,  15},
    {1147,  2,  16},
    {1146,  2,  16},
    { 662,  2,  17},
    { 678,  2,  17},
    { 763,  2,  18},
    { 836,  2,  18},
    {1069,  2,  19},
    {1068,  2,  19},
    {1155,  2,  20},
    { 687,  2,  21},
    { 688,  2,  21},
    {1156,  2,  22},
    {1157,  2,  22},
    { 851,  2,  23},
    { 856,  2,  23},
    { 531,  2,  24},
    { 530,  2,  24},
    { 570,  2,  25},
    { 569,  2,  25},
    { 487,  2,  26},
    { 486,  2,  26},
    { 333,  2,  27},
    { 332,  2,  27},
    { 271,  2,  28},
    { 275,  2,  28},
    { 909,  2,  29},
    { 908,  2,  29},
    {1033,  2,  30},
    {1034,  2,  30},
    { 672,  2,  31},
    { 674,  2,  31},
    { 845,  2,  32},
    { 844,  2,  32},
    { 593,  2,  33},
    { 592,  2,  33},
    { 664,  2,  34},
    { 655,  2,  34},
    { 242,  2,  35},
    { 241,  2,  35},
    { 568,  2,  36},
    { 577,  2,  36},
    {1237,  2,  37},
    {1238,  2,  37},
    { 915,  2,  38},
    { 635,  2,  38},
    { 539,  2,  39},
    { 538,  2,  39},
    { 440,  2,  40},
    { 460,  2,  40},
    { 618,  2,  41},
    {1249,  2,  41},
    {1005,  2,  41},
    {1126,  2,  42},
    {1152,  2,  42},
    { 579,  2,  43},
    { 578,  2,  43},
    { 263,  2,  44},
    { 262,  2,  44},
    {1128,  2,  45},
    {1127,  2,  45},
    { 724,  2,  46},
    { 723,  2,  46},
    {1131,  2,  47},
    {1138,  2,  47},
    { 728,  2,  48},
    { 726,  2,  48},
    {1179,  2,  49},
    {1178,  2,  49},
    {1059,  2,  50},
    {1060,  2,  50},
    { 933,  2,  51},
    { 932,  2,  51},
    { 415,  2,  52},
    { 402,  2,  52},
    { 254,  2,  53},
    { 253,  2,  53},
    { 261,  2,  54},
    { 260,  2,  54},
    { 397,  2,  55},
    { 396,  2,  55},
    {1004,  2,  55},
    { 871,  2,  56},
    {1139,  2,  56},
    { 536,  2,  57},
    { 535,  2,  57},
    {1158,  2,  58},
    {1151,  2,  58},
    {1120,  2,  59},
    {1119,  2,  59},
    { 918,  2,  60},
    {1229,  2,  60},
    { 671,  2,  61},
    { 670,  2,  61},
    { 209,  2,  62},
    { 208,  2,  62},
    { 405,  2,  63},
    {1230,  2,  63},
    { 978,  2,  64},
    { 977,  2,  64},
    { 972,  2,  65},
    { 971,  2,  65},
    { 874,  2,  66},
    { 875,  2,  66},
    {1095,  2,  67},
    {1094,  2,  67},
    { 718,  2,  68},
    { 717,  2,  68},
    { 913,  2,  69},
    { 914,  2,  69},
    {1191,  2,  70},
    {1192,  2,  70},
    {1044,  2,  71},
    {1043,  2,  71},
    { 668,  2,  72},
    { 654,  2,  72},
    {1017,  2,  73},
    {1026,  2,  73},
    { 754,  2,  74},
    { 753,  2,  74},
    { 278,  2,  75},
    { 277,  2,  75},
    { 756,  2,  76},
    { 755,  2,  76},
    { 326,  2,  77},
    {1132,  2,  78},
    { 686,  2,  78},
    {1133,  2,  79},
    {1142,  2,  79},
    { 203,  2,  80},
    { 204,  2,  80},
    { 469,  2,  81},
    { 468,  2,  81},
    {1040,  2,  82},
    {1041,  2,  82},
    { 734,  2,  83},
    { 211,  2,  84},
    { 210,  2,  84},
    { 640,  2,  85},
    { 639,  2,  85},
    { 809,  2,  86},
    { 848,  2,  86},
    { 612,  2,  87},
    { 186,  2,  87},
    { 919,  2,  88},
    {1042,  2,  88},
    { 625,  2,  89},
    { 997,  2,  89},
    { 624,  2,  90},
    { 975,  2,  90},
    { 920,  2,  91},
    { 929,  2,  91},
    { 653,  2,  92},
    { 680,  2,  92},
    { 217,  2,  93},
    { 218,  2,  93},
    { 251,  2,  94},
    { 250,  2,  94},
    { 765,  2,  95},
    { 764,  2,  95},
    { 325,  2,  96},
    { 269,  2,  96},
    { 816,  2,  97},
    { 814,  2,  97},
    { 817,  2,  98},
    { 815,  2,  98},
    { 818,  2,  99},
    { 985,  2,  99},
    {1058,  2, 100},
    {1063,  2, 100},
    {1080,  2, 101},
    {1079,  2, 101},
    {1137,  2, 102},
    {1136,  2, 102},
    { 283,  2, 103},
    { 147,  2, 103},
    { 216,  2, 104},
    { 215,  2, 104},
    { 464,  2, 105},
    { 463,  2, 105},
    { 471,  2, 106},
    { 470,  2, 106},
    { 541,  2, 107},
    { 540,  2, 107},
    { 954,  2, 108},
    { 595,  2, 108},
    { 676,  2, 109},
    { 675,  2, 109},
    { 727,  2, 110},
    { 725,  2, 110},
    { 759,  2, 111},
    { 760,  2, 111},
    { 768,  2, 112},
    { 767,  2, 112},
    { 813,  2, 113},
    { 812,  2, 113},
    { 838,  2, 114},
    { 846,  2, 115},
    { 847,  2, 115},
    { 916,  2, 116},
    { 863,  2, 116},
    { 860,  2, 117},
    { 866,  2, 117},
    { 956,  2, 118},
    { 955,  2, 118},
    { 963,  2, 119},
    { 962,  2, 119},
    { 917,  2, 120},
    { 969,  2, 120},
    { 999,  2, 121},
    { 976,  2, 121},
    {1065,  2, 122},
    {1064,  2, 122},
    { 677,  2, 123},
    {1066,  2, 123},
    {1160,  2, 124},
    {1159,  2, 124},
    {1213,  2, 125},
    {1212,  2, 125},
    { 666,  2, 126},
    { 596,  2, 126},
    { 934,  3,   0},
    {1231,  3,   0},
    { 458,  3,   1},
    { 459,  3,   1},
    {1067,  3,   2},
    {1087,  3,   2},
    { 583,  3,   3},
    { 594,  3,   3},
    { 403,  3,   4},
    { 722,  3,   5},
    { 870,  3,   6},
    { 876,  3,   6},
    { 500,  3,   7},
    {1014,  3,   8},
    {1019,  3,   8},
    { 515,  3,   9},
    { 513,  3,   9},
    { 664,  3,  10},
    { 651,  3,  10},
    { 156,  3,  11},
    { 708,  3,  11},
    { 819,  3,  12},
    { 835,  3,  12},
    { 820,  3,  13},
    { 837,  3,  13},
    { 821,  3,  14},
    { 803,  3,  14},
    { 899,  3,  15},
    { 894,  3,  15},
    { 502,  3,  16},
    { 497,  3,  16},
    { 934,  4,   0},
    {1231,  4,   0},
    { 403,  4,   1},
    { 722,  4,   2},
    { 394,  4,   3},
    { 365,  4,   3},
    { 500,  4,   4},
    { 497,  4,   4},
    {1014,  4,   5},
    {1019,  4,   5},
    {1084,  4,   6},
    {1072,  4,   6},
    { 682,  4,   7},
    {1190,  4,   8},
    {1125,  4,   9},
    { 749,  4,  10},
    { 751,  4,  11},
    { 993,  4,  12},
    { 990,  4,  12},
    { 934,  5,   0},
    {1231,  5,   0},
    { 403,  5,   1},
    { 722,  5,   2},
    { 500,  5,   3},
    { 497,  5,   3},
    {1055,  5,   4},
    {1050,  5,   4},
    { 515,  5,   5},
    { 513,  5,   5},
    {1081,  5,   6},
    { 740,  5,   7},
    { 737,  5,   7},
    {1187,  5,   8},
    {1186,  5,   8},
    { 921,  5,   9},
    { 708,  5,   9},
    { 899,  5,  10},
    { 894,  5,  10},
    { 197,  5,  11},
    { 192,  5,  11},
    {1091,  5,  12},
    {1090,  5,  12},
    { 361,  5,  13},
    { 360,  5,  13},
    {1047,  5,  14},
    {1046,  5,  14},
    { 877,  6,   0},
    { 857,  6,   0},
    { 503,  6,   0},
    { 504,  6,   0},
    {1236,  6,   1},
    {1232,  6,   1},
    {1125,  6,   1},
    {1174,  6,   1},
    { 888,  7,   0},
    { 859,  7,   0},
    { 709,  7,   1},
    { 682,  7,   1},
    {1207,  7,   2},
    {1190,  7,   2},
    {1170,  7,   3},
    {1125,  7,   3},
    { 750,  7,   4},
    { 749,  7,   4},
    { 752,  7,   5},
    { 751,  7,   5},
    { 713,  8,   0},
    { 682,  8,   0},
    {1022,  8,   1},
    {1012,  8,   1},
    { 494,  8,   2},
    { 473,  8,   2},
    { 495,  8,   3},
    { 484,  8,   3},
    { 496,  8,   4},
    { 485,  8,   4},
    { 178,  8,   5},
    { 164,  8,   5},
    { 378,  8,   6},
    { 404,  8,   6},
    { 957,  8,   7},
    { 205,  8,   7},
    {1052,  8,   8},
    {1035,  8,   8},
    {1216,  8,   9},
    {1222,  8,   9},
    { 943,  8,  10},
    { 924,  8,  10},
    { 247,  8,  11},
    { 240,  8,  11},
    { 885,  8,  12},
    { 892,  8,  12},
    { 175,  8,  13},
    { 151,  8,  13},
    { 716,  8,  14},
    { 746,  8,  14},
    {1025,  8,  15},
    {1029,  8,  15},
    { 714,  8,  16},
    { 744,  8,  16},
    {1023,  8,  17},
    {1027,  8,  17},
    { 987,  8,  18},
    { 966,  8,  18},
    { 715,  8,  19},
    { 745,  8,  19},
    {1024,  8,  20},
    {1028,  8,  20},
    { 512,  8,  21},
    { 518,  8,  21},
    { 988,  8,  22},
    { 967,  8,  22},
    { 889,  9,   0},
    {   1,  9,   0},
    { 890,  9,   0},
    { 950,  9,   1},
    {   2,  9,   1},
    { 949,  9,   1},
    { 895,  9,   2},
    { 122,  9,   2},
    { 873,  9,   2},
    { 658,  9,   3},
    { 129,  9,   3},
    { 681,  9,   3},
    {1201,  9,   4},
    { 135,  9,   4},
    {1208,  9,   4},
    { 287,  9,   5},
    {  13,  9,   5},
    { 290,  9,   6},
    {  24,  9,   6},
    { 292,  9,   7},
    {  27,  9,   7},
    { 295,  9,   8},
    {  30,  9,   8},
    { 299,  9,   9},
    {  35,  9,   9},
    { 300,  9,  10},
    {  36,  9,  10},
    { 301,  9,  11},
    {  38,  9,  11},
    { 302,  9,  12},
    {  39,  9,  12},
    { 303,  9,  13},
    {  41,  9,  13},
    { 304,  9,  14},
    {  42,  9,  14},
    { 305,  9,  15},
    {  46,  9,  15},
    { 306,  9,  16},
    {  51,  9,  16},
    { 307,  9,  17},
    {  56,  9,  17},
    { 308,  9,  18},
    {  62,  9,  18},
    { 309,  9,  19},
    {  67,  9,  19},
    { 310,  9,  20},
    {  69,  9,  20},
    { 311,  9,  21},
    {  70,  9,  21},
    { 312,  9,  22},
    {  71,  9,  22},
    { 313,  9,  23},
    {  72,  9,  23},
    { 314,  9,  24},
    {  73,  9,  24},
    { 315,  9,  25},
    {  80,  9,  25},
    { 316,  9,  26},
    {  84,  9,  26},
    { 317,  9,  27},
    {  85,  9,  27},
    { 318,  9,  28},
    {  86,  9,  28},
    { 319,  9,  29},
    {  87,  9,  29},
    { 320,  9,  30},
    {  88,  9,  30},
    { 321,  9,  31},
    {  89,  9,  31},
    { 322,  9,  32},
    { 134,  9,  32},
    { 323,  9,  33},
    { 141,  9,  33},
    { 288,  9,  34},
    {  22,  9,  34},
    { 289,  9,  35},
    {  23,  9,  35},
    { 291,  9,  36},
    {  26,  9,  36},
    { 293,  9,  37},
    {  28,  9,  37},
    { 294,  9,  38},
    {  29,  9,  38},
    { 296,  9,  39},
    {  32,  9,  39},
    { 297,  9,  40},
    {  33,  9,  40},
    { 200,  9,  41},
    {  50,  9,  41},
    { 195,  9,  41},
    { 198,  9,  42},
    {  52,  9,  42},
    { 193,  9,  42},
    { 199,  9,  43},
    {  53,  9,  43},
    { 194,  9,  43},
    { 223,  9,  44},
    {  55,  9,  44},
    { 235,  9,  44},
    { 222,  9,  45},
    {  57,  9,  45},
    { 205,  9,  45},
    { 224,  9,  46},
    {  58,  9,  46},
    { 249,  9,  46},
    { 710,  9,  47},
    {  59,  9,  47},
    { 682,  9,  47},
    {1020,  9,  48},
    {  60,  9,  48},
    {1012,  9,  48},
    { 144,  9,  49},
    {  61,  9,  49},
    { 151,  9,  49},
    { 143,  9,  50},
    {  63,  9,  50},
    { 142,  9,  50},
    { 145,  9,  51},
    {  64,  9,  51},
    { 170,  9,  51},
    { 457,  9,  52},
    {  65,  9,  52},
    { 432,  9,  52},
    { 456,  9,  53},
    {  66,  9,  53},
    { 427,  9,  53},
    { 629,  9,  54},
    {  68,  9,  54},
    { 632,  9,  54},
    { 298,  9,  55},
    {  34,  9,  55},
    { 201,  9,  56},
    {  47,  9,  56},
    { 196,  9,  56},
    { 882, 10,   0},
    { 273, 10,   1},
    { 270, 10,   1},
    { 379, 10,   2},
    { 368, 10,   2},
    { 514, 10,   3},
    { 879, 10,   4},
    { 865, 10,   4},
    { 620, 10,   5},
    { 619, 10,   5},
    { 807, 10,   6},
    { 806, 10,   6},
    { 509, 10,   7},
    { 508, 10,   7},
    { 634, 10,   8},
    { 633, 10,   8},
    { 335, 10,   9},
    { 474, 10,   9},
    {1102, 10,  10},
    {1098, 10,  10},
    {1093, 10,  11},
    {1199, 10,  12},
    {1198, 10,  12},
    {1217, 10,  13},
    { 864, 10,  14},
    { 862, 10,  14},
    {1073, 10,  15},
    {1076, 10,  15},
    {1089, 10,  16},
    {1088, 10,  16},
    { 517, 10,  17},
    { 516, 10,  17},
    { 869, 11,   0},
    { 857, 11,   0},
    { 163, 11,   1},
    { 142, 11,   1},
    { 565, 11,   2},
    { 559, 11,   2},
    {1217, 11,   3},
    {1211, 11,   3},
    { 519, 11,   4},
    { 503, 11,   4},
    { 864, 11,   5},
    { 859, 11,   5},
    { 880, 12,   0},
    { 150, 12,   1},
    { 152, 12,   2},
    { 155, 12,   3},
    { 221, 12,   4},
    { 227, 12,   5},
    { 428, 12,   6},
    { 429, 12,   7},
    { 465, 12,   8},
    { 507, 12,   9},
    { 511, 12,  10},
    { 520, 12,  11},
    { 521, 12,  12},
    { 562, 12,  13},
    { 567, 12,  14},
    {1145, 12,  14},
    { 580, 12,  15},
    { 584, 12,  16},
    { 585, 12,  17},
    { 586, 12,  18},
    { 652, 12,  19},
    { 663, 12,  20},
    { 679, 12,  21},
    { 684, 12,  22},
    { 685, 12,  23},
    { 808, 12,  24},
    { 822, 12,  25},
    { 887, 12,  26},
    { 902, 12,  27},
    { 968, 12,  28},
    {1006, 12,  29},
    {1007, 12,  30},
    {1016, 12,  31},
    {1018, 12,  32},
    {1038, 12,  33},
    {1039, 12,  34},
    {1051, 12,  35},
    {1053, 12,  36},
    {1061, 12,  37},
    {1117, 12,  38},
    {1130, 12,  39},
    {1143, 12,  40},
    {1144, 12,  41},
    {1150, 12,  42},
    {1214, 12,  43},
    {1124, 12,  44},
    {1233, 12,  45},
    {1234, 12,  46},
    {1235, 12,  47},
    {1243, 12,  48},
    {1244, 12,  49},
    {1247, 12,  50},
    {1248, 12,  51},
    { 669, 12,  52},
    { 506, 12,  53},
    { 264, 12,  54},
    { 505, 12,  55},
    { 904, 12,  56},
    {1030, 12,  57},
    {1092, 12,  58},
    { 769, 12,  59},
    { 770, 12,  60},
    { 771, 12,  61},
    { 772, 12,  62},
    { 773, 12,  63},
    { 774, 12,  64},
    { 775, 12,  65},
    { 776, 12,  66},
    { 777, 12,  67},
    { 778, 12,  68},
    { 779, 12,  69},
    { 780, 12,  70},
    { 781, 12,  71},
    { 782, 12,  72},
    { 783, 12,  73},
    { 784, 12,  74},
    { 785, 12,  75},
    { 786, 12,  76},
    { 787, 12,  77},
    { 788, 12,  78},
    { 789, 12,  79},
    { 790, 12,  80},
    { 791, 12,  81},
    { 792, 12,  82},
    { 793, 12,  83},
    { 794, 12,  84},
    { 795, 12,  85},
    { 884, 13,   0},
    {1175, 13,   0},
    { 644, 13,   1},
    { 267, 13,   1},
    { 462, 13,   2},
    { 426, 13,   2},
    {1021, 13,   3},
    {1012, 13,   3},
    { 712, 13,   4},
    { 682, 13,   4},
    {1171, 13,   5},
    {1125, 13,   5},
    {1185, 14,   0},
    {1231, 14,   0},
    { 926, 14,   1},
    { 925, 14,   1},
    { 363, 14,   2},
    { 360, 14,   2},
    {1010, 14,   3},
    {1009, 14,   3},
    { 537, 14,   4},
    { 534, 14,   4},
    { 886, 14,   5},
    { 891, 14,   5},
    { 498, 14,   6},
    { 497, 14,   6},
    { 259, 14,   7},
    {1118, 14,   7},
    { 617, 14,   8},
    { 632, 14,   8},
    { 992, 14,   9},
    { 991, 14,   9},
    { 989, 14,  10},
    { 986, 14,  10},
    { 899, 14,  11},
    { 894, 14,  11},
    { 159, 14,  12},
    { 151, 14,  12},
    { 604, 14,  13},
    { 600, 14,  13},
    { 626, 14,  14},
    { 613, 14,  14},
    { 627, 14,  14},
    { 599, 14,  15},
    { 598, 14,  15},
    { 374, 14,  16},
    { 364, 14,  16},
    { 257, 14,  17},
    { 219, 14,  17},
    { 256, 14,  18},
    { 207, 14,  18},
    {1082, 14,  19},
    {1081, 14,  19},
    { 766, 14,  20},
    { 234, 14,  20},
    { 279, 14,  21},
    { 403, 14,  21},
    { 732, 14,  22},
    { 722, 14,  22},
    { 393, 14,  23},
    { 284, 14,  23},
    { 381, 14,  24},
    {1037, 14,  24},
    { 163, 14,  25},
    { 149, 14,  25},
    { 258, 14,  26},
    { 206, 14,  26},
    {1116, 14,  27},
    {1057, 14,  27},
    {1254, 14,  28},
    {1253, 14,  28},
    { 872, 14,  29},
    { 876, 14,  29},
    {1221, 14,  30},
    {1218, 14,  30},
    { 642, 14,  31},
    { 650, 14,  32},
    { 649, 14,  33},
    { 560, 14,  34},
    { 561, 14,  35},
    { 362, 14,  36},
    { 401, 14,  36},
    { 583, 14,  37},
    { 594, 14,  37},
    { 382, 14,  38},
    { 336, 14,  38},
    {1014, 14,  39},
    {1019, 14,  39},
    { 882, 15,   0},
    { 899, 15,   1},
    { 894, 15,   1},
    { 452, 15,   2},
    { 445, 15,   2},
    { 434, 15,   3},
    { 433, 15,   3},
    { 861, 16,   0},
    {   0, 16,   1},
    {   1, 16,   2},
    {   4, 16,   3},
    {   3, 16,   4},
    {  12, 16,   5},
    {  11, 16,   6},
    {  10, 16,   7},
    {   9, 16,   8},
    {  75, 16,   9},
    {   8, 16,  10},
    {   7, 16,  11},
    {   6, 16,  12},
    {  79, 16,  13},
    {  45, 16,  14},
    {   5, 16,  15},
    {  78, 16,  16},
    { 112, 16,  17},
    {  44, 16,  18},
    {  77, 16,  19},
    {  94, 16,  20},
    { 111, 16,  21},
    { 124, 16,  22},
    {   2, 16,  23},
    {  76, 16,  24},
    {  43, 16,  25},
    { 110, 16,  26},
    {  74, 16,  27},
    { 123, 16,  28},
    {  93, 16,  29},
    { 136, 16,  30},
    { 109, 16,  31},
    {  25, 16,  32},
    { 117, 16,  33},
    {  31, 16,  34},
    { 122, 16,  35},
    {  37, 16,  36},
    { 129, 16,  37},
    {  40, 16,  38},
    { 135, 16,  39},
    {  13, 16,  40},
    {  24, 16,  41},
    {  27, 16,  42},
    {  30, 16,  43},
    {  35, 16,  44},
    {  36, 16,  45},
    {  38, 16,  46},
    {  39, 16,  47},
    {  41, 16,  48},
    {  42, 16,  49},
    {  46, 16,  50},
    {  51, 16,  51},
    {  56, 16,  52},
    {  62, 16,  53},
    {  67, 16,  54},
    {  69, 16,  55},
    {  70, 16,  56},
    {  71, 16,  57},
    {  72, 16,  58},
    {  73, 16,  59},
    {  80, 16,  60},
    {  84, 16,  61},
    {  85, 16,  62},
    {  86, 16,  63},
    {  87, 16,  64},
    {  88, 16,  65},
    {  89, 16,  66},
    {  90, 16,  67},
    {  91, 16,  68},
    {  92, 16,  69},
    {  95, 16,  70},
    {  99, 16,  71},
    { 100, 16,  72},
    { 101, 16,  73},
    { 103, 16,  74},
    { 104, 16,  75},
    { 105, 16,  76},
    { 106, 16,  77},
    { 107, 16,  78},
    { 108, 16,  79},
    { 113, 16,  80},
    { 118, 16,  81},
    { 125, 16,  82},
    { 130, 16,  83},
    { 137, 16,  84},
    {  14, 16,  85},
    {  47, 16,  86},
    {  81, 16,  87},
    {  96, 16,  88},
    { 114, 16,  89},
    { 119, 16,  90},
    { 126, 16,  91},
    { 131, 16,  92},
    { 138, 16,  93},
    {  15, 16,  94},
    {  48, 16,  95},
    {  82, 16,  96},
    {  97, 16,  97},
    { 115, 16,  98},
    { 120, 16,  99},
    { 127, 16, 100},
    { 132, 16, 101},
    { 139, 16, 102},
    {  16, 16, 103},
    {  49, 16, 104},
    {  83, 16, 105},
    {  98, 16, 106},
    { 116, 16, 107},
    { 121, 16, 108},
    { 128, 16, 109},
    { 133, 16, 110},
    { 140, 16, 111},
    {  17, 16, 112},
    {  54, 16, 113},
    { 102, 16, 114},
    {  18, 16, 115},
    {  19, 16, 116},
    {  20, 16, 117},
    {  21, 16, 118},
    { 859, 17,   0},
    {1020, 17,   1},
    { 710, 17,   2},
    {1203, 17,   3},
    { 711, 17,   4},
    {1164, 17,   5},
    { 245, 17,   6},
    {1165, 17,   7},
    {1169, 17,   8},
    {1167, 17,   9},
    {1168, 17,  10},
    { 246, 17,  11},
    {1166, 17,  12},
    { 951, 17,  13},
    { 934, 18,   0},
    { 233, 18,   1},
    {1202, 18,   2},
    { 202, 18,   3},
    { 895, 18,   4},
    {1201, 18,   5},
    {1003, 18,   6},
    { 628, 18,   7},
    {1206, 18,   8},
    {1205, 18,   9},
    {1204, 18,  10},
    { 389, 18,  11},
    { 384, 18,  12},
    { 385, 18,  13},
    { 390, 18,  14},
    { 392, 18,  15},
    { 391, 18,  16},
    { 388, 18,  17},
    { 386, 18,  18},
    { 387, 18,  19},
    { 843, 18,  20},
    {1162, 18,  21},
    {1163, 18,  22},
    { 524, 18,  23},
    { 276, 18,  24},
    {1015, 18,  25},
    { 883, 18,  26},
    { 646, 18,  27},
    { 898, 18,  28},
    { 896, 18,  29},
    { 252, 18,  30},
};

/* property values: 5488 bytes. */

/* Codepoints which expand on full case-folding. */

RE_UINT16 re_expand_on_folding[] = {
      223,   304,   329,   496,   912,   944,  1415,  7830,
     7831,  7832,  7833,  7834,  7838,  8016,  8018,  8020,
     8022,  8064,  8065,  8066,  8067,  8068,  8069,  8070,
     8071,  8072,  8073,  8074,  8075,  8076,  8077,  8078,
     8079,  8080,  8081,  8082,  8083,  8084,  8085,  8086,
     8087,  8088,  8089,  8090,  8091,  8092,  8093,  8094,
     8095,  8096,  8097,  8098,  8099,  8100,  8101,  8102,
     8103,  8104,  8105,  8106,  8107,  8108,  8109,  8110,
     8111,  8114,  8115,  8116,  8118,  8119,  8124,  8130,
     8131,  8132,  8134,  8135,  8140,  8146,  8147,  8150,
     8151,  8162,  8163,  8164,  8166,  8167,  8178,  8179,
     8180,  8182,  8183,  8188, 64256, 64257, 64258, 64259,
    64260, 64261, 64262, 64275, 64276, 64277, 64278, 64279,
};

/* expand_on_folding: 208 bytes. */

/* General_Category. */

static RE_UINT8 re_general_category_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  6,  7,  5,  5,  8,  9, 10,
    11, 12, 13, 14, 15, 15, 16, 15, 15, 15, 15, 17, 15, 18, 19, 20,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 21, 22, 15, 15, 15, 23,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    24, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 25,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 25,
};

static RE_UINT8 re_general_category_stage_2[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,
     32,  33,  34,  34,  35,  36,  37,  38,  39,  34,  34,  34,  40,  41,  42,  43,
     44,  45,  46,  47,  48,  49,  50,  51,  52,  53,  54,  55,  56,  57,  58,  59,
     60,  61,  62,  63,  64,  64,  65,  66,  67,  68,  69,  70,  71,  69,  72,  73,
     69,  69,  64,  74,  64,  64,  75,  76,  77,  78,  79,  80,  81,  82,  69,  83,
     84,  85,  86,  87,  88,  89,  69,  69,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  90,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  91,
     92,  34,  34,  34,  34,  34,  34,  34,  34,  93,  34,  34,  94,  95,  96,  97,
     98,  99, 100, 101, 102, 103, 104, 105,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 106,
    107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
    108, 108,  34,  34, 109, 110, 111, 112,  34,  34, 113, 114, 115, 116, 117, 118,
    119, 120, 121, 122, 123, 124, 125, 126, 127, 128, 129, 123,  34,  34, 130, 123,
    131, 132, 133, 134, 135, 136, 137, 138, 139, 123, 123, 123, 140, 123, 123, 123,
    141, 142, 143, 144, 145, 146, 147, 123, 123, 148, 123, 149, 150, 151, 123, 123,
    123, 152, 123, 123, 123, 153, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34,  34,  34,  34, 154, 155, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34,  34,  34,  34,  34, 156, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34, 157, 158, 159, 160, 123, 123, 123, 123, 123, 123, 161, 162,
    163, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 164, 165, 123, 123, 123, 123, 123, 123,
     69, 166, 167, 168, 169, 123, 170, 123, 171, 172, 173, 174, 175, 176, 177, 178,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34, 179, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 180, 181, 123, 123,
    182, 183, 184, 185, 186, 123, 187, 188,  69, 189, 190, 191, 192, 193, 194, 195,
    196, 197, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 198,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 199,  34,
    200, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34, 200, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    201, 123, 202, 203, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 204,
};

static RE_UINT16 re_general_category_stage_3[] = {
      0,   0,   1,   2,   3,   4,   5,   6,   0,   0,   7,   8,   9,  10,  11,  12,
     13,  13,  13,  14,  15,  13,  13,  16,  17,  18,  19,  20,  21,  22,  13,  23,
     13,  13,  13,  24,  25,  11,  11,  11,  11,  26,  11,  27,  28,  29,  30,  31,
     32,  32,  32,  32,  32,  32,  32,  33,  34,  35,  36,  11,  37,  38,  13,  39,
      9,   9,   9,  11,  11,  11,  13,  13,  40,  13,  13,  13,  41,  13,  13,  13,
     13,  13,  13,  42,   9,  43,  44,  11,  45,  46,  32,  47,  48,  49,  50,  51,
     52,  53,  49,  49,  54,  32,  55,  56,  49,  49,  49,  49,  49,  57,  58,  59,
     60,  61,  49,  32,  62,  49,  49,  49,  49,  49,  63,  64,  65,  49,  66,  67,
     49,  68,  69,  70,  49,  71,  72,  72,  72,  72,  49,  73,  72,  72,  74,  32,
     75,  49,  49,  76,  77,  78,  79,  80,  81,  82,  83,  84,  85,  86,  87,  88,
     89,  82,  83,  90,  91,  92,  93,  94,  95,  96,  83,  97,  98,  99,  87, 100,
    101,  82,  83, 102, 103, 104,  87, 105, 106, 107, 108, 109, 110, 111,  93, 112,
    113, 114,  83, 115, 116, 117,  87, 118, 119, 114,  83, 120, 121, 122,  87, 123,
    119, 114,  49, 124, 125, 126,  87, 127, 128, 129,  49, 130, 131, 132,  93, 133,
    134,  49,  49, 135, 136, 137,  72,  72, 138, 139, 140, 141, 142, 143,  72,  72,
    144, 145, 146, 147, 148,  49, 149, 150, 151, 152,  32, 153, 154, 155,  72,  72,
     49,  49, 156, 157, 158, 159, 160, 161, 162, 163,   9,   9, 164,  49,  49, 165,
     49,  49,  49,  49,  49,  49,  49,  49,  49,  49,  49,  49, 166, 167,  49,  49,
    166,  49,  49, 168, 169, 170,  49,  49,  49, 169,  49,  49,  49, 171, 172, 173,
     49, 174,  49,  49,  49,  49,  49, 175, 176,  49,  49,  49,  49,  49,  49,  49,
     49,  49,  49,  49,  49,  49, 177,  49, 178, 179,  49,  49,  49,  49, 180, 181,
    182, 183,  49, 184,  49, 185, 182, 186,  49,  49,  49, 187, 188, 189, 190, 191,
    192, 190,  49,  49, 193,  49,  49, 194,  49,  49, 195,  49,  49,  49,  49, 196,
     49, 197, 198, 199, 200,  49, 201, 175,  49,  49, 202, 203, 204, 205, 206, 206,
     49, 207,  49,  49,  49, 208, 209, 210, 190, 190, 211, 212,  72,  72,  72,  72,
    213,  49,  49, 214, 215, 158, 216, 217, 218,  49, 219,  65,  49,  49, 220, 221,
     49,  49, 222, 223, 224,  65,  49, 225,  72,  72,  72,  72, 226, 227, 228, 229,
     11,  11, 230,  27,  27,  27, 231, 232,  11, 233,  27,  27,  32,  32,  32, 234,
     13,  13,  13,  13,  13,  13,  13,  13,  13, 235,  13,  13,  13,  13,  13,  13,
    236, 237, 236, 236, 237, 238, 236, 239, 240, 240, 240, 241, 242, 243, 244, 245,
    246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257,  72, 258, 259, 260,
    261, 262, 263, 264, 265, 266, 267, 267, 268, 269, 270, 206, 271, 272, 206, 273,
    274, 274, 274, 274, 274, 274, 274, 274, 275, 206, 276, 206, 206, 206, 206, 277,
    206, 278, 274, 279, 206, 280, 281, 282, 206, 206, 283,  72, 282,  72, 266, 266,
    266, 284, 206, 206, 206, 206, 285, 266, 206, 206, 206, 206, 206, 206, 206, 206,
    206, 206, 206, 286, 287, 206, 206, 288, 206, 206, 206, 206, 206, 206, 289, 206,
    206, 206, 206, 206, 206, 206, 290, 291, 266, 292, 206, 206, 293, 274, 294, 274,
    295, 296, 274, 274, 274, 297, 274, 298, 206, 206, 206, 274, 299, 206, 206, 300,
    206, 301, 206, 302, 303, 304,  72,  72,   9,   9, 305,  11,  11, 306, 307, 308,
     13,  13,  13,  13,  13,  13, 309, 310,  11,  11, 311,  49,  49,  49, 312, 313,
     49, 314, 315, 315, 315, 315,  32,  32, 316, 317, 318, 319, 320,  72,  72,  72,
    206, 321, 206, 206, 206, 206, 206, 322, 206, 206, 206, 206, 206, 323,  72, 324,
    325, 326, 327, 328, 134,  49,  49,  49,  49, 329, 176,  49,  49,  49,  49, 330,
    331,  49, 201, 134,  49,  49,  49,  49, 197, 332,  49,  50, 206, 206, 322,  49,
    206, 333, 334, 206, 335, 336, 206, 206, 334, 206, 206, 336, 206, 206, 206, 333,
     49,  49,  49, 196, 206, 206, 206, 206,  49,  49,  49,  49, 149,  72,  72,  72,
     49, 337,  49,  49,  49,  49,  49,  49, 149, 206, 206, 206, 283,  49,  49, 225,
    338,  49, 339,  72,  13,  13, 340, 341,  13, 342,  49,  49,  49,  49, 343, 344,
     31, 345, 346, 347,  13,  13,  13, 348, 349, 350, 351, 352,  72,  72,  72, 353,
    354,  49, 355, 356,  49,  49,  49, 357, 358,  49,  49, 359, 360, 190,  32, 361,
     65,  49, 362,  49, 363, 364,  49, 149,  75,  49,  49, 365, 366, 367, 368, 369,
     49,  49, 370, 371, 372, 373,  49, 374,  49,  49,  49, 375, 376, 377, 378, 379,
    380, 381, 315,  11,  11, 382, 383,  72,  72,  72,  72,  72,  49,  49, 384, 190,
     49,  49, 385,  49, 386,  49,  49, 202, 387, 387, 387, 387, 387, 387, 387, 387,
    388, 388, 388, 388, 388, 388, 388, 388,  49,  49,  49,  49,  49,  49, 201,  49,
     49,  49,  49,  49,  49, 389,  72,  72, 390, 391, 392, 393, 394,  49,  49,  49,
     49,  49,  49, 395, 396, 397,  49,  49,  49,  49,  49, 398,  72,  49,  49,  49,
     49, 399,  49,  49, 194,  72,  72, 400,  32, 401, 402, 403, 404, 405, 406, 407,
     49,  49,  49,  49,  49,  49,  49, 408, 409,   2,   3,   4,   5, 410, 411, 412,
     49, 413,  49, 197, 414, 415, 416, 417, 418,  49, 170, 419, 201, 201,  72,  72,
     49,  49,  49,  49,  49,  49,  49,  50, 420, 266, 266, 421, 267, 267, 267, 422,
    423, 324, 424,  72,  72, 206, 206, 425,  72,  72,  72,  72,  72,  72,  72,  72,
     49, 149,  49,  49,  49,  99, 426, 427,  49,  49, 428,  49, 429,  49,  49, 430,
     49, 431,  49,  49, 432, 433,  72,  72,   9,   9, 434,  11,  11,  49,  49,  49,
     49, 201, 190,  72,  72,  72,  72,  72,  49,  49, 194,  49,  49,  49, 435,  72,
     49,  49,  49, 314,  49, 196, 194,  72, 436,  49,  49, 437,  49, 438,  49, 439,
     49, 197, 440,  72,  72,  72,  72,  72,  49, 441,  49, 442,  72,  72,  72,  72,
     49,  49,  49, 443,  72,  72,  72,  72, 444, 445,  49, 446, 447, 448,  49, 449,
     49, 450,  72,  72, 451,  49, 452, 453,  49,  49,  49, 454,  49, 455,  49, 456,
     49, 457, 458,  72,  72,  72,  72,  72,  49,  49,  49,  49, 459,  72,  72,  72,
     72,  72,  72,  72,  72,  72, 266, 460, 461,  49,  49, 462, 463, 464, 465, 466,
    218,  49,  49, 467, 468,  49, 459, 190, 469,  49, 470, 471, 472,  49,  49, 473,
    218,  49,  49, 474, 475, 476, 477, 478,  49,  96, 479, 480,  72,  72,  72,  72,
     72,  72,  72,  49,  49, 481, 482, 190, 101,  82,  83,  97, 483, 484, 485, 486,
     49,  49,  49, 487, 488, 190,  72,  72,  49,  49, 489, 490, 491,  72,  72,  72,
     49,  49,  49, 492, 493, 190,  72,  72,  49,  49, 494, 495, 190,  72,  72,  72,
     72,  72,   9,   9,  11,  11, 146, 496,  72,  72,  72,  72,  49,  49,  49, 459,
     49, 459,  72,  72,  72,  72,  72,  72, 267, 267, 267, 267, 267, 267, 497, 498,
     49,  49, 197,  72,  72,  72,  72,  72,  49,  49,  49, 459,  49, 197, 367,  72,
     72,  72,  72,  72,  72,  49, 201, 499,  49,  49,  49, 500, 501, 502, 503, 504,
     49,  72,  72,  72,  72,  72,  72,  72,  49,  49,  49,  49, 175, 505, 203, 506,
    466, 507,  72,  72,  72,  72,  72,  72, 508,  72,  72,  72,  72,  72,  72,  72,
     49,  49,  49,  49,  49,  49,  50, 149, 459, 509, 510,  72,  72,  72,  72,  72,
    206, 206, 206, 206, 206, 206, 206, 323, 206, 206, 511, 206, 206, 206, 512, 513,
    514, 206, 515, 206, 206, 516,  72,  72, 206, 206, 206, 206, 517,  72,  72,  72,
    206, 206, 206, 206, 206, 283, 266, 518,   9, 519,  11, 520, 521, 522, 236,   9,
    523, 524, 525, 526, 527,   9, 519,  11, 528, 529,  11, 530, 531, 532, 533,   9,
    534,  11,   9, 519,  11, 520, 521,  11, 236,   9, 523, 533,   9, 534,  11,   9,
    519,  11, 535,   9, 536, 537, 538, 539,  11, 540,   9, 541, 542, 543, 544,  11,
    545,   9, 546,  11, 547, 548, 548, 548,  49,  49,  49,  49, 549, 550,  72,  72,
    551,  49, 552, 553, 554, 555, 556, 557, 558, 202, 559, 202,  72,  72,  72, 560,
    206, 206, 324, 206, 206, 206, 206, 206, 206, 322, 333, 561, 561, 561, 206, 323,
    173, 206, 333, 206, 206, 206, 324, 206, 206, 282,  72,  72,  72,  72, 562, 206,
    563, 206, 206, 282, 564, 304,  72,  72, 206, 206, 565, 206, 206, 206, 206, 516,
    206, 206, 206, 206, 333, 566, 206, 567, 206, 206, 206, 206, 206, 206, 206, 333,
    206, 206, 206, 206, 282, 206, 206, 321, 206, 206, 568, 206, 206, 206, 206, 206,
    206, 206, 206, 206, 569, 206, 206, 206, 206, 206, 206, 206, 206,  72, 565, 322,
    206, 206, 206, 206, 206, 206, 206, 322, 206, 206, 206, 206, 206, 570,  72,  72,
    324, 206, 206, 206, 567, 174, 206, 206, 567, 206, 516,  72,  72,  72,  72,  72,
     49,  49,  49,  49,  49, 314,  72,  72,  49,  49,  49, 175,  49,  49,  49,  49,
     49, 201,  72,  72,  72,  72,  72,  72, 571,  72, 572, 572, 572, 572, 572, 572,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  72,
    388, 388, 388, 388, 388, 388, 388, 573,
};

static RE_UINT8 re_general_category_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   2,   4,   5,   6,   2,
      7,   7,   7,   7,   7,   2,   8,   9,  10,  11,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  12,  13,  14,  15,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16,  16,  16,  17,  18,  19,   1,  20,  20,  21,  22,  23,  24,  25,
     26,  27,  15,   2,  28,  29,  27,  30,  11,  11,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  31,  11,  11,  11,  32,  16,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16,  33,  16,  16,  16,  16,  32,  32,  32,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  34,  34,  34,  34,  34,  34,  34,  34,  16,  32,  32,  32,
     32,  32,  32,  32,  11,  34,  34,  16,  34,  32,  32,  11,  34,  11,  16,  11,
     11,  34,  32,  11,  32,  16,  11,  34,  32,  32,  32,  11,  34,  16,  32,  11,
     34,  11,  34,  34,  32,  35,  32,  16,  36,  36,  37,  34,  38,  37,  34,  34,
     34,  34,  34,  34,  34,  34,  16,  32,  34,  38,  32,  11,  32,  32,  32,  32,
     32,  32,  16,  16,  16,  11,  34,  32,  34,  34,  11,  32,  32,  32,  32,  32,
     16,  16,  39,  16,  16,  16,  16,  16,  40,  40,  40,  40,  40,  40,  40,  40,
     40,  41,  41,  40,  40,  40,  40,  40,  40,  41,  41,  41,  41,  41,  41,  41,
     40,  40,  42,  41,  41,  41,  42,  42,  41,  41,  41,  41,  41,  41,  41,  41,
     43,  43,  43,  43,  43,  43,  43,  43,  32,  32,  42,  32,  44,  45,  16,  10,
     44,  44,  41,  46,  11,  47,  47,  11,  34,  11,  11,  11,  11,  11,  11,  11,
     11,  48,  11,  11,  11,  11,  16,  16,  16,  16,  16,  16,  16,  16,  16,  34,
     16,  11,  32,  16,  32,  32,  32,  32,  16,  16,  32,  49,  34,  32,  34,  11,
     32,  50,  43,  43,  51,  32,  32,  32,  11,  34,  34,  34,  34,  34,  34,  16,
     48,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  47,  52,   2,   2,   2,
     53,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  54,  55,  56,  57,
     58,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  59,
     60,  61,  43,  60,  44,  44,  44,  44,  36,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  62,  44,  44,  36,  63,  64,  44,  44,  44,  44,  44,
     65,  65,  65,   8,   9,  66,   2,  67,  43,  43,  43,  43,  43,  61,  68,   2,
     69,  36,  36,  36,  36,  70,  43,  43,   7,   7,   7,   7,   7,   2,   2,  36,
     71,  36,  36,  36,  36,  36,  36,  36,  36,  36,  72,  43,  43,  43,  73,  50,
     43,  43,  74,  75,  76,  43,  43,  36,   7,   7,   7,   7,   7,  36,  77,  78,
      2,   2,   2,   2,   2,   2,   2,  79,  70,  36,  36,  36,  36,  36,  36,  36,
     43,  43,  43,  43,  43,  80,  81,  36,  36,  36,  36,  43,  43,  43,  43,  43,
     71,  44,  44,  44,  44,  44,  44,  44,   7,   7,   7,   7,   7,  36,  36,  36,
     36,  36,  36,  36,  36,  70,  43,  43,  43,  43,  40,  21,   2,  82,  44,  44,
     36,  36,  36,  43,  43,  75,  43,  43,  43,  43,  75,  43,  75,  43,  43,  44,
      2,   2,   2,   2,   2,   2,   2,  64,  36,  36,  36,  36,  70,  43,  44,  64,
     44,  44,  44,  44,  44,  44,  44,  44,  36,  62,  44,  44,  44,  44,  44,  44,
     44,  44,  43,  43,  43,  43,  43,  43,  43,  83,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  83,  71,  84,  85,  43,  43,  43,  83,  84,  85,  84,
     70,  43,  43,  43,  36,  36,  36,  36,  36,  43,   2,   7,   7,   7,   7,   7,
     86,  36,  36,  36,  36,  36,  36,  36,  70,  84,  81,  36,  36,  36,  62,  81,
     62,  81,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  62,  36,  36,  36,
     62,  62,  44,  36,  36,  44,  71,  84,  85,  43,  80,  87,  88,  87,  85,  62,
     44,  44,  44,  87,  44,  44,  36,  81,  36,  43,  44,   7,   7,   7,   7,   7,
     36,  20,  27,  27,  27,  57,  44,  44,  58,  83,  81,  36,  36,  62,  44,  81,
     62,  36,  81,  62,  36,  44,  80,  84,  85,  80,  44,  58,  80,  58,  43,  44,
     58,  44,  44,  44,  81,  36,  62,  62,  44,  44,  44,   7,   7,   7,   7,   7,
     43,  36,  70,  44,  44,  44,  44,  44,  58,  83,  81,  36,  36,  36,  36,  81,
     36,  81,  36,  36,  36,  36,  36,  36,  62,  36,  81,  36,  36,  44,  71,  84,
     85,  43,  43,  58,  83,  87,  85,  44,  62,  44,  44,  44,  44,  44,  44,  44,
     66,  44,  44,  44,  44,  44,  44,  44,  58,  84,  81,  36,  36,  36,  62,  81,
     62,  36,  81,  36,  36,  44,  71,  85,  85,  43,  80,  87,  88,  87,  85,  44,
     44,  44,  44,  83,  44,  44,  36,  81,  78,  27,  27,  27,  44,  44,  44,  44,
     44,  71,  81,  36,  36,  62,  44,  36,  62,  36,  36,  44,  81,  62,  62,  36,
     44,  81,  62,  44,  36,  62,  44,  36,  36,  36,  36,  36,  36,  44,  44,  84,
     83,  88,  44,  84,  88,  84,  85,  44,  62,  44,  44,  87,  44,  44,  44,  44,
     27,  89,  67,  67,  57,  90,  44,  44,  83,  84,  81,  36,  36,  36,  62,  36,
     62,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  44,  81,  43,
     83,  84,  88,  43,  80,  43,  43,  44,  44,  44,  58,  80,  36,  44,  44,  44,
     44,  44,  44,  44,  27,  27,  27,  89,  58,  84,  81,  36,  36,  36,  62,  36,
     36,  36,  81,  36,  36,  44,  71,  85,  84,  84,  88,  83,  88,  84,  43,  44,
     44,  44,  87,  88,  44,  44,  44,  62,  81,  62,  44,  44,  44,  44,  44,  44,
     36,  36,  36,  36,  36,  62,  81,  84,  85,  43,  80,  84,  88,  84,  85,  62,
     44,  44,  44,  87,  44,  44,  44,  44,  27,  27,  27,  44,  56,  36,  36,  36,
     44,  84,  81,  36,  36,  36,  36,  36,  36,  36,  36,  62,  44,  36,  36,  36,
     36,  81,  36,  36,  36,  36,  81,  44,  36,  36,  36,  62,  44,  80,  44,  87,
     84,  43,  80,  80,  84,  84,  84,  84,  44,  84,  64,  44,  44,  44,  44,  44,
     81,  36,  36,  36,  36,  36,  36,  36,  70,  36,  43,  43,  43,  80,  44,  91,
     36,  36,  36,  75,  43,  43,  43,  61,   7,   7,   7,   7,   7,   2,  44,  44,
     81,  62,  62,  81,  62,  62,  81,  44,  44,  44,  36,  36,  81,  36,  36,  36,
     81,  36,  81,  81,  44,  36,  81,  36,  70,  36,  43,  43,  43,  58,  71,  44,
     36,  36,  62,  82,  43,  43,  43,  44,   7,   7,   7,   7,   7,  44,  36,  36,
     77,  67,   2,   2,   2,   2,   2,   2,   2,  92,  92,  67,  43,  67,  67,  67,
      7,   7,   7,   7,   7,  27,  27,  27,  27,  27,  50,  50,  50,   4,   4,  84,
     36,  36,  36,  36,  81,  36,  36,  36,  36,  36,  36,  36,  36,  36,  62,  44,
     58,  43,  43,  43,  43,  43,  43,  83,  43,  43,  61,  43,  36,  36,  70,  43,
     43,  43,  43,  43,  58,  43,  43,  43,  43,  43,  43,  43,  43,  43,  80,  67,
     67,  67,  67,  76,  67,  67,  90,  67,   2,   2,  92,  67,  21,  64,  44,  44,
     36,  36,  36,  36,  36,  93,  85,  43,  83,  43,  43,  43,  85,  83,  85,  71,
      7,   7,   7,   7,   7,   2,   2,   2,  36,  36,  36,  84,  43,  36,  36,  43,
     71,  84,  94,  93,  84,  84,  84,  36,  70,  43,  71,  36,  36,  36,  36,  36,
     36,  83,  85,  83,  84,  84,  85,  93,   7,   7,   7,   7,   7,  84,  85,  67,
     11,  11,  11,  48,  44,  44,  48,  44,  36,  36,  36,  36,  36,  63,  69,  36,
     36,  36,  36,  36,  62,  36,  36,  44,  36,  36,  36,  62,  62,  36,  36,  44,
     62,  36,  36,  44,  36,  36,  36,  62,  62,  36,  36,  44,  36,  36,  36,  36,
     36,  36,  36,  62,  36,  36,  36,  36,  36,  36,  36,  36,  36,  62,  58,  43,
      2,   2,   2,   2,  95,  27,  27,  27,  27,  27,  27,  27,  27,  27,  96,  44,
     67,  67,  67,  67,  67,  44,  44,  44,  36,  36,  62,  44,  44,  44,  44,  44,
     97,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  63,  72,
     98,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  99, 100,  44,
     36,  36,  36,  36,  36,  63,   2, 101, 102,  36,  36,  36,  62,  44,  44,  44,
     36,  36,  36,  36,  36,  36,  62,  36,  36,  43,  80,  44,  44,  44,  44,  44,
     36,  43,  61,  64,  44,  44,  44,  44,  36,  43,  44,  44,  44,  44,  44,  44,
     62,  43,  44,  44,  44,  44,  44,  44,  36,  36,  43,  85,  43,  43,  43,  84,
     84,  84,  84,  83,  85,  43,  43,  43,  43,  43,   2,  86,   2,  66,  70,  44,
      7,   7,   7,   7,   7,  44,  44,  44,  27,  27,  27,  27,  27,  44,  44,  44,
      2,   2,   2, 103,   2,  60,  43,  68,  36, 104,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  44,  44,  44,  44,  36,  36,  36,  36,  70,  62,  44,  44,
     36,  36,  36,  44,  44,  44,  44,  44,  36,  36,  36,  36,  36,  36,  36,  62,
     43,  83,  84,  85,  83,  84,  44,  44,  84,  83,  84,  84,  85,  43,  44,  44,
     90,  44,   2,   7,   7,   7,   7,   7,  36,  36,  36,  36,  36,  36,  36,  44,
     36,  36,  36,  36,  36,  36,  44,  44,  84,  84,  84,  84,  84,  84,  84,  84,
     94,  36,  36,  36,  84,  44,  44,  44,   7,   7,   7,   7,   7,  96,  44,  67,
     67,  67,  67,  67,  67,  67,  67,  67,  36,  36,  36,  70,  83,  85,  44,   2,
     36,  36,  93,  83,  43,  43,  43,  80,  83,  83,  85,  43,  43,  43,  83,  84,
     84,  85,  43,  43,  43,  43,  80,  58,   2,   2,   2,  86,   2,   2,   2,  44,
     43,  43,  43,  43,  43,  43,  43, 105,  43,  43,  94,  36,  36,  36,  36,  36,
     36,  36,  83,  43,  43,  83,  83,  84,  84,  83,  94,  36,  36,  36,  44,  44,
     92,  67,  67,  67,  67,  50,  43,  43,  43,  43,  67,  67,  67,  67,  90,  44,
     43,  94,  36,  36,  36,  36,  36,  36,  93,  43,  43,  84,  43,  85,  43,  36,
     36,  36,  36,  83,  43,  84,  85,  85,  43,  84,  44,  44,  44,  44,   2,   2,
     36,  36,  84,  84,  84,  84,  43,  43,  43,  43,  84,  43,  44,  54,   2,   2,
      7,   7,   7,   7,   7,  44,  81,  36,  36,  36,  36,  36,  40,  40,  40,   2,
      2,   2,   2,   2,  44,  44,  44,  44,  43,  61,  43,  43,  43,  43,  43,  43,
     83,  43,  43,  43,  71,  36,  70,  36,  36,  84,  71,  62,  43,  44,  44,  44,
     16,  16,  16,  16,  16,  16,  40,  40,  40,  40,  40,  40,  40,  45,  16,  16,
     16,  16,  16,  16,  45,  16,  16,  16,  16,  16,  16,  16,  16, 106,  40,  40,
     43,  43,  43,  44,  44,  44,  43,  43,  32,  32,  32,  16,  16,  16,  16,  32,
     16,  16,  16,  16,  11,  11,  11,  11,  16,  16,  16,  44,  11,  11,  11,  44,
     16,  16,  16,  16,  48,  48,  48,  48,  16,  16,  16,  16,  16,  16,  16,  44,
     16,  16,  16,  16, 107, 107, 107, 107,  16,  16, 108,  16,  11,  11, 109, 110,
     41,  16, 108,  16,  11,  11, 109,  41,  16,  16,  44,  16,  11,  11, 111,  41,
     16,  16,  16,  16,  11,  11, 112,  41,  44,  16, 108,  16,  11,  11, 109, 113,
    114, 114, 114, 114, 114, 115,  65,  65, 116, 116, 116,   2, 117, 118, 117, 118,
      2,   2,   2,   2, 119,  65,  65, 120,   2,   2,   2,   2, 121, 122,   2, 123,
    124,   2, 125, 126,   2,   2,   2,   2,   2,   9, 124,   2,   2,   2,   2, 127,
     65,  65,  68,  65,  65,  65,  65,  65, 128,  44,  27,  27,  27,   8, 125, 129,
     27,  27,  27,  27,  27,   8, 125, 100,  40,  40,  40,  40,  40,  40,  82,  44,
     20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  44,
     43,  43,  43,  43,  43,  43, 130,  51, 131,  51, 131,  43,  43,  43,  43,  43,
     80,  44,  44,  44,  44,  44,  44,  44,  67, 132,  67, 133,  67,  34,  11,  16,
     11,  32, 133,  67,  49,  11,  11,  67,  67,  67, 132, 132, 132,  11,  11, 134,
     11,  11,  35,  36,  39,  67,  16,  11,   8,   8,  49,  16,  16,  26,  67, 135,
     27,  27,  27,  27,  27,  27,  27,  27, 101, 101, 101, 101, 101, 101, 101, 101,
    101, 136, 137, 101, 138,  44,  44,  44,   8,   8, 139,  67,  67,   8,  67,  67,
    139,  26,  67, 139,  67,  67,  67, 139,  67,  67,  67,  67,  67,  67,  67,   8,
     67, 139, 139,  67,  67,  67,  67,  67,  67,  67,   8,   8,   8,   8,   8,   8,
      8,   8,   8,   8,   8,   8,   8,   8,  67,  67,  67,  67,   4,   4,  67,  67,
      8,  67,  67,  67, 140, 141,  67,  67,  67,  67,  67,  67,  67,  67, 139,  67,
     67,  67,  67,  67,  67,  26,   8,   8,   8,   8,  67,  67,  67,  67,  67,  67,
     67,  67,  67,  67,  67,  67,   8,   8,   8,  67,  67,  67,  67,  67,  67,  67,
     67,  67,  67,  67,  67,  90,  44,  44,  67,  67,  67,  90,  44,  44,  44,  44,
     27,  27,  27,  27,  27,  27,  67,  67,  67,  67,  67,  67,  67,  27,  27,  27,
     67,  67,  67,  26,  67,  67,  67,  67,  26,  67,  67,  67,  67,  67,  67,  67,
     67,  67,  67,  67,   8,   8,   8,   8,  67,  67,  67,  67,  67,  67,  67,  26,
     67,  67,  67,  67,   4,   4,   4,   4,   4,   4,   4,  27,  27,  27,  27,  27,
     27,  27,  67,  67,  67,  67,  67,  67,   8,   8, 125, 142,   8,   8,   8,   8,
      8,   8,   8,   4,   4,   4,   4,   4,   8, 125, 143, 143, 143, 143, 143, 143,
    143, 143, 143, 143, 142,   8,   8,   8,   8,   8,   8,   8,   4,   4,   8,   8,
      8,   8,   8,   8,   8,   8,   4,   8,   8,   8, 139,  26,   8,   8, 139,  67,
     67,  67,  44,  67,  67,  67,  67,  67,  67,  67,  67,  44,  67,  67,  67,  67,
     67,  67,  67,  67,  67,  44,  56,  67,  67,  67,  67,  67,  90,  67,  67,  67,
     67,  44,  44,  44,  44,  44,  44,  44,  11,  11,  11,  11,  11,  11,  11,  47,
     16,  16,  16,  16,  16,  16,  16, 108,  32,  11,  32,  34,  34,  34,  34,  11,
     32,  32,  34,  16,  16,  16,  40,  11,  32,  32, 135,  67,  67, 133,  34, 144,
     43,  32,  44,  44,  54,   2,  95,   2,  16,  16,  16,  53,  44,  44,  53,  44,
     36,  36,  36,  36,  44,  44,  44,  52,  64,  44,  44,  44,  44,  44,  44,  58,
     36,  36,  36,  62,  44,  44,  44,  44,  36,  36,  36,  62,  36,  36,  36,  62,
      2, 117, 117,   2, 121, 122, 117,   2,   2,   2,   2,   6,   2, 103, 117,   2,
    117,   4,   4,   4,   4,   2,   2,  86,   2,   2,   2,   2,   2, 116,   2,   2,
    103, 145,  44,  44,  44,  44,  44,  44,  67,  67,  67,  67,  67,  56,  67,  67,
     67,  67,  44,  44,  44,  44,  44,  44,  67,  67,  67,  44,  44,  44,  44,  44,
     67,  67,  67,  67,  67,  67,  44,  44,   1,   2, 146, 147,   4,   4,   4,   4,
      4,  67,   4,   4,   4,   4, 148, 149, 150, 101, 101, 101, 101,  43,  43,  84,
    151,  40,  40,  67, 101, 152,  63,  67,  36,  36,  36,  62,  58, 153, 154,  69,
     36,  36,  36,  36,  36,  63,  40,  69,  44,  44,  81,  36,  36,  36,  36,  36,
     67,  27,  27,  67,  67,  67,  67,  67,  67,  67,  67,  67,  67,  67,  67,  90,
     27,  27,  27,  27,  27,  67,  67,  67,  67,  67,  67,  67,  27,  27,  27,  27,
    155,  27,  27,  27,  27,  27,  27,  27,  36,  36, 104,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36, 156,   2,   7,   7,   7,   7,   7,  36,  44,  44,
     32,  32,  32,  32,  32,  32,  32,  70,  51, 157,  43,  43,  43,  43,  43,  86,
     32,  32,  32,  32,  32,  32,  40,  58,  36,  36,  36, 101, 101, 101, 101, 101,
     43,   2,   2,   2,  44,  44,  44,  44,  41,  41,  41, 154,  40,  40,  40,  40,
     41,  32,  32,  32,  32,  32,  32,  32,  16,  32,  32,  32,  32,  32,  32,  32,
     45,  16,  16,  16,  34,  34,  34,  32,  32,  32,  32,  32,  42, 158,  34, 108,
     32,  32,  16,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  11,  11,  44,
     11,  44,  44,  44,  44,  44,  44,  44,  44,  44,  44,  81,  40,  35,  36,  36,
     36,  71,  36,  71,  36,  70,  36,  36,  36,  93,  85,  83,  67,  67,  44,  44,
     27,  27,  27,  67, 159,  44,  44,  44,  36,  36,   2,   2,  44,  44,  44,  44,
     84,  36,  36,  36,  36,  36,  36,  36,  36,  36,  84,  84,  84,  84,  84,  84,
     84,  84,  80,  44,  44,  44,  44,   2,  43,  36,  36,  36,   2,  72,  44,  44,
     36,  36,  36,  43,  43,  43,  43,   2,  36,  36,  36,  70,  43,  43,  43,  43,
     43,  84,  44,  44,  44,  44,  44,  54,  36,  70,  84,  43,  43,  84,  83,  84,
    160,   2,   2,   2,   2,   2,   2,  52,   7,   7,   7,   7,   7,  44,  44,   2,
     36,  36,  70,  69,  36,  36,  36,  36,   7,   7,   7,   7,   7,  36,  36,  62,
     36,  36,  36,  36,  70,  43,  43,  83,  85,  83,  85,  80,  44,  44,  44,  44,
     36,  70,  36,  36,  36,  36,  83,  44,   7,   7,   7,   7,   7,  44,   2,   2,
     69,  36,  36,  77,  67,  93,  83,  36,  71,  43,  71,  70,  71,  36,  36,  43,
     70,  62,  44,  44,  44,  44,  44,  44,  44,  44,  44,  44,  44,  81, 104,   2,
     36,  36,  36,  36,  36,  93,  43,  84,   2, 104, 161,  80,  44,  44,  44,  44,
     81,  36,  36,  62,  81,  36,  36,  62,  81,  36,  36,  62,  44,  44,  44,  44,
     16,  16,  16,  16,  16, 110,  40,  40,  44,  44,  16,  44,  44,  44,  44,  44,
     36,  93,  85,  84,  83, 160,  85,  44,  36,  36,  44,  44,  44,  44,  44,  44,
     36,  36,  36,  62,  44,  81,  36,  36, 162, 162, 162, 162, 162, 162, 162, 162,
    163, 163, 163, 163, 163, 163, 163, 163,  36,  36,  36,  36,  36,  44,  44,  44,
     16,  16,  16, 108,  44,  44,  44,  44,  44,  53,  16,  16,  44,  44,  81,  71,
     36,  36,  36,  36, 164,  36,  36,  36,  36,  36,  36,  62,  36,  36,  62,  62,
     36,  81,  62,  36,  36,  36,  36,  36,  36,  41,  41,  41,  41,  41,  41,  41,
     41,  44,  44,  44,  44,  44,  44,  44,  44,  81,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  36, 143,  44,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36, 159,  44,   2,   2,   2, 165, 126,  44,  44,  44,
     43,  43,  43,  43,  43,  43,  43,  44,   6, 166, 167, 143, 143, 143, 143, 143,
    143, 143, 126, 165, 126,   2, 123, 168,   2,  64,   2,   2, 148, 143, 143, 126,
      2, 169,   8, 170,  66,   2,  44,  44,  36,  36,  62,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  62,  79,  54,   2,   3,   2,   4,   5,   6,   2,
     16,  16,  16,  16,  16,  17,  18, 125, 126,   4,   2,  36,  36,  36,  36,  36,
     69,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  40,
     44,  36,  36,  36,  44,  36,  36,  36,  44,  36,  36,  36,  44,  36,  62,  44,
     20, 171,  57, 172,  26,   8, 139,  90,  44,  44,  44,  44,  79,  65,  67,  44,
     36,  36,  36,  36,  36,  36,  81,  36,  36,  36,  36,  36,  36,  62,  36,  81,
      2,  64,  44, 173,  27,  27,  27,  27,  27,  27,  44,  56,  67,  67,  67,  67,
    101, 101, 138,  27,  89,  67,  67,  67,  67,  67,  67,  67,  67,  27,  90,  44,
     90,  44,  44,  44,  44,  44,  44,  44,  67,  67,  67,  67,  67,  67,  50,  44,
    174,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,  44,  44,
     27,  27,  44,  44,  44,  44,  44,  44, 147,  36,  36,  36,  36, 175,  44,  44,
     36,  36,  36,  43,  43,  80,  44,  44,  36,  36,  36,  36,  36,  36,  36,  54,
     36,  36,  44,  44,  36,  36,  36,  36, 176, 101, 101,  44,  44,  44,  44,  44,
     11,  11,  11,  11,  16,  16,  16,  16,  36,  36,  44,  44,  44,  44,  44,  54,
     36,  36,  36,  44,  62,  36,  36,  36,  36,  36,  36,  81,  62,  44,  62,  81,
     36,  36,  36,  54,  27,  27,  27,  27,  36,  36,  36,  77, 155,  27,  27,  27,
     44,  44,  44, 173,  27,  27,  27,  27,  36,  36,  36,  27,  27,  27,  44,  54,
     36,  36,  36,  36,  36,  44,  44,  54,  36,  36,  36,  36,  44,  44,  44,  36,
     70,  43,  58,  80,  44,  44,  43,  43,  36,  36,  81,  36,  81,  36,  36,  36,
     36,  36,  44,  44,  43,  80,  44,  58,  27,  27,  27,  27,  44,  44,  44,  44,
      2,   2,   2,   2,  64,  44,  44,  44,  36,  36,  36,  36,  36,  36, 177,  30,
     36,  36,  36,  36,  36,  36, 177,  27,  36,  36,  36,  36,  78,  36,  36,  36,
     36,  36,  70,  80,  44, 173,  27,  27,   2,   2,   2,  64,  44,  44,  44,  44,
     36,  36,  36,  44,  54,   2,   2,   2,  36,  36,  36,  44,  27,  27,  27,  27,
     36,  62,  44,  44,  27,  27,  27,  27,  36,  44,  44,  44,  54,   2,  64,  44,
     44,  44,  44,  44, 173,  27,  27,  27,  36,  36,  36,  36,  62,  44,  44,  44,
     27,  27,  27,  27,  27,  27,  27,  96,  85,  94,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  43,  43,  43,  43,  43,  43,  43,  61,   2,   2,   2,  44,
     44,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,   7,   7,   7,   7,   7,
     44,  44,  44,  44,  44,  44,  44,  58,  84,  85,  43,  83,  85,  61, 178,   2,
      2,  44,  44,  44,  44,  44,  44,  44,  43,  71,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  70,  43,  43,  85,  43,  43,  43,  80,   7,   7,   7,   7,   7,
      2,   2,  44,  44,  44,  44,  44,  44,  36,  70,   2,  62,  44,  44,  44,  44,
     36,  93,  84,  43,  43,  43,  43,  83,  94,  36,  63,   2,  64,  44,  54,  44,
      7,   7,   7,   7,   7,  62,  44,  44, 173,  27,  27,  27,  27,  27,  27,  27,
     27,  27,  96,  44,  44,  44,  44,  44,  36,  36,  36,  36,  36,  36,  84,  85,
     43,  84,  83,  43,   2,   2,   2,  44,  36,  36,  36,  36,  36,  36,  36,  70,
     84,  85,  43,  43,  43,  80,  44,  44,  83,  84,  88,  87,  88,  87,  84,  44,
     44,  44,  44,  87,  44,  44,  81,  36,  36,  84,  44,  43,  43,  43,  80,  44,
     43,  43,  80,  44,  44,  44,  44,  44,  84,  85,  43,  43,  83,  83,  84,  85,
     83,  43,  36,  72,  44,  44,  44,  44,  36,  36,  36,  36,  36,  36,  36,  93,
     84,  43,  43,  44,  84,  84,  43,  85,  61,   2,   2,   2,   2,  44,  44,  44,
     84,  85,  43,  43,  43,  83,  85,  85,  61,   2,  62,  44,  44,  44,  44,  44,
     36,  36,  36,  36,  36,  70,  85,  84,  43,  43,  43,  85,  44,  44,  44,  44,
     27,  96,  44,  44,  44,  44,  44,  81, 101, 101, 101, 101, 101, 101, 101, 175,
      2,   2,  64,  44,  44,  44,  44,  44,  43,  43,  61,  44,  44,  44,  44,  44,
     43,  43,  43,  61,   2,   2,  67,  67,  40,  40,  92,  44,  44,  44,  44,  44,
      7,   7,   7,   7,   7, 173,  27,  27,  27,  81,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  44,  44,  81,  36,  93,  84,  84,  84,  84,  84,  84,  84,
     84,  84,  84,  84,  84,  84,  84,  88,  43,  74,  40,  40,  40,  40,  40,  40,
     36,  44,  44,  44,  44,  44,  44,  44,  36,  36,  36,  36,  36,  44,  50,  61,
     65,  65,  44,  44,  44,  44,  44,  44,  67,  67,  67,  90,  56,  67,  67,  67,
     67,  67, 179,  85,  43,  67, 179,  84,  84, 180,  65,  65,  65, 181,  43,  43,
     43,  76,  50,  43,  43,  43,  67,  67,  67,  67,  67,  67,  67,  43,  43,  67,
     67,  67,  67,  67,  67,  67,  67,  44,  67,  43,  76,  44,  44,  44,  44,  44,
     27,  44,  44,  44,  44,  44,  44,  44,  11,  11,  11,  11,  11,  16,  16,  16,
     16,  16,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  16,
     16,  16, 108,  16,  16,  16,  16,  16,  11,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16,  16,  16,  16,  47,  11,  44,  47,  48,  47,  48,  11,  47,  11,
     11,  11,  11,  16,  16,  53,  53,  16,  16,  16,  53,  16,  16,  16,  16,  16,
     16,  16,  11,  48,  11,  47,  48,  11,  11,  11,  47,  11,  11,  11,  47,  16,
     16,  16,  16,  16,  11,  48,  11,  47,  11,  11,  47,  47,  44,  11,  11,  11,
     47,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  11,  11,
     11,  11,  11,  16,  16,  16,  16,  16,  16,  16,  16,  44,  11,  11,  11,  11,
     31,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  33,  16,  16,
     16,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  31,  16,  16,
     16,  16,  33,  16,  16,  16,  11,  11,  11,  11,  31,  16,  16,  16,  16,  16,
     16,  16,  16,  16,  16,  16,  16,  33,  16,  16,  16,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  11,  11,  31,  16,  16,  16,  16,  33,  16,  16,  16,
     11,  11,  11,  11,  31,  16,  16,  16,  16,  33,  16,  16,  16,  32,  44,   7,
      7,   7,   7,   7,   7,   7,   7,   7,  36,  36,  62, 173,  27,  27,  27,  27,
     43,  43,  43,  80,  44,  44,  44,  44,  36,  36,  81,  36,  36,  36,  36,  36,
     81,  62,  62,  81,  81,  36,  36,  36,  36,  62,  36,  36,  81,  81,  44,  44,
     44,  62,  44,  81,  81,  81,  81,  36,  81,  62,  62,  81,  81,  81,  81,  81,
     81,  62,  62,  81,  36,  62,  36,  36,  36,  62,  36,  36,  81,  36,  62,  62,
     36,  36,  36,  36,  36,  81,  36,  36,  81,  36,  81,  36,  36,  81,  36,  36,
      8,  44,  44,  44,  44,  44,  44,  44,  56,  67,  67,  67,  67,  67,  67,  67,
     44,  44,  44,  67,  67,  67,  67,  67,  67,  90,  44,  44,  44,  44,  44,  44,
     67,  67,  67,  67,  90,  44,  44,  44,  67,  67,  67,  67,  67,  67,  90,  44,
     44,  44,  67,  67,  67,  67,  67,  67,  67,  67,  67,  67,  44,  44,  44,  44,
     67,  67,  56,  67,  67,  67,  67,  67,  67,  90,  56,  67,  67,  67,  67,  67,
     67,  67,  90,  44,  44,  44,  44,  44,  79,  44,  44,  44,  44,  44,  44,  44,
     65,  65,  65,  65,  65,  65,  65,  65, 163, 163, 163, 163, 163, 163, 163,  44,
};

static RE_UINT8 re_general_category_stage_5[] = {
    15, 15, 12, 23, 23, 23, 25, 23, 20, 21, 23, 24, 23, 19,  9,  9,
    24, 24, 24, 23, 23,  1,  1,  1,  1, 20, 23, 21, 26, 22, 26,  2,
     2,  2,  2, 20, 24, 21, 24, 15, 25, 25, 27, 23, 26, 27,  5, 28,
    24, 16, 27, 26, 27, 24, 11, 11, 26, 11,  5, 29, 11, 23,  1, 24,
     1,  2,  2, 24,  2,  1,  2,  5,  5,  5,  1,  3,  3,  2,  5,  2,
     4,  4, 26, 26,  4, 26,  6,  6,  0,  0,  4,  2,  1, 23,  1,  0,
     0,  1, 24,  1, 27,  6,  7,  7,  0,  4,  0,  2,  0, 23, 19,  0,
     0, 27, 27, 25,  0,  6, 19,  6, 23,  6,  6, 23,  5,  0,  5, 23,
    23,  0, 16, 16, 23, 25, 27, 27, 16,  0,  4,  5,  5,  6,  6,  5,
    23,  5,  6, 16,  6,  4,  4,  6,  6, 27,  5, 27, 27,  5,  0, 16,
     6,  0,  0,  5,  4,  0,  6,  8,  8,  8,  8,  6, 23,  4,  0,  8,
     8,  0, 11, 27, 27,  0,  0, 25, 23, 27,  5,  8,  8,  5, 23, 11,
    11,  0, 19,  5, 12,  5,  5, 20, 21,  0, 10, 10, 10,  5, 19, 23,
     5,  4,  7,  0,  2,  4,  3,  3,  2,  0,  3, 26,  2, 26,  0, 26,
     1, 26, 26,  0, 12, 12, 12, 16, 19, 19, 28, 29, 20, 28, 13, 14,
    16, 12, 23, 28, 29, 23, 23, 22, 22, 23, 24, 20, 21, 23, 23, 12,
    11,  4, 21,  4,  6,  7,  7,  6,  1, 27, 27,  1, 27,  2,  2, 27,
    10,  1,  2, 10, 10, 11, 24, 27, 27, 20, 21, 27, 21, 24, 21, 20,
     2,  6, 20,  0, 27,  4,  5, 10, 19, 20, 21, 21, 27, 10, 19,  4,
    10,  4,  6, 26, 26,  4, 27, 11,  4, 23,  7, 23, 26,  1, 25, 27,
     8, 23,  4,  8, 18, 18, 17, 17,  5, 24, 23, 20, 19, 22, 22, 20,
    22, 22, 24, 19, 24,  0, 24, 26, 25,  0,  0, 11,  6, 11, 10,  0,
    23, 10,  5, 11, 23, 16, 27,  8,  8, 16, 16,  6,
};

/* General_Category: 9340 bytes. */

RE_UINT32 re_get_general_category(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_general_category_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_general_category_stage_2[pos + f] << 3;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_general_category_stage_3[pos + f] << 3;
    f = code >> 1;
    code ^= f << 1;
    pos = (RE_UINT32)re_general_category_stage_4[pos + f] << 1;
    value = re_general_category_stage_5[pos + code];

    return value;
}

/* Block. */

static RE_UINT8 re_block_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  5,  6,  7,  7,  8,  9, 10,
    11, 12, 13, 14, 15, 15, 16, 15, 15, 15, 15, 17, 15, 18, 19, 20,
    21, 21, 21, 21, 21, 21, 21, 21, 21, 21, 22, 23, 15, 15, 15, 24,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    25, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26, 26,
    27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27,
};

static RE_UINT8 re_block_stage_2[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   8,   9,  10,  11,  11,  12,  13,
     14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  28,
     29,  30,  31,  31,  32,  32,  32,  33,  34,  34,  34,  34,  34,  35,  36,  37,
     38,  39,  40,  41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  50,  51,  51,
     52,  53,  54,  55,  56,  56,  57,  57,  58,  59,  60,  61,  62,  62,  63,  64,
     65,  65,  66,  67,  68,  68,  69,  69,  70,  71,  72,  73,  74,  75,  76,  77,
     78,  79,  80,  81,  82,  82,  83,  83,  84,  84,  84,  84,  84,  84,  84,  84,
     84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,
     84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,
     84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  85,  86,  86,  86,  86,
     86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,
     86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,
     87,  87,  87,  87,  87,  87,  87,  87,  87,  88,  89,  89,  90,  91,  92,  93,
     94,  95,  96,  97,  98,  99, 100, 101, 102, 102, 102, 102, 102, 102, 102, 102,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 103,
    104, 104, 104, 104, 104, 104, 104, 105, 106, 106, 106, 106, 106, 106, 106, 106,
    107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107,
    107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107,
    107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107,
    107, 107, 108, 108, 108, 108, 109, 110, 110, 110, 110, 110, 111, 112, 113, 114,
    115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 119, 126, 126, 126, 119,
    127, 128, 129, 130, 131, 132, 133, 134, 135, 119, 119, 119, 136, 119, 119, 119,
    137, 138, 139, 140, 141, 142, 143, 119, 119, 144, 119, 145, 146, 147, 119, 119,
    119, 148, 119, 119, 119, 149, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    150, 150, 150, 150, 150, 150, 150, 150, 151, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    152, 152, 152, 152, 152, 152, 152, 152, 153, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    154, 154, 154, 154, 155, 156, 157, 158, 119, 119, 119, 119, 119, 119, 159, 160,
    161, 161, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 162, 163, 119, 119, 119, 119, 119, 119,
    164, 164, 165, 165, 166, 119, 167, 119, 168, 168, 168, 168, 168, 168, 168, 168,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    169, 170, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 171, 171, 119, 119,
    172, 173, 174, 174, 175, 175, 176, 176, 176, 176, 176, 176, 177, 178, 179, 180,
    181, 181, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182,
    182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182,
    182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 182, 183, 184, 184,
    184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184,
    184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 184, 185, 186,
    187, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    188, 188, 188, 188, 189, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    190, 119, 191, 192, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193,
    193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193, 193,
    194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194,
    194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194, 194,
};

static RE_UINT8 re_block_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,   1,   1,
      2,   2,   2,   2,   2,   2,   2,   2,   3,   3,   3,   3,   3,   3,   3,   3,
      3,   3,   3,   3,   3,   4,   4,   4,   4,   4,   4,   5,   5,   5,   5,   5,
      6,   6,   6,   6,   6,   6,   6,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      8,   8,   8,   8,   8,   8,   8,   8,   9,   9,   9,  10,  10,  10,  10,  10,
     10,  11,  11,  11,  11,  11,  11,  11,  12,  12,  12,  12,  12,  12,  12,  12,
     13,  13,  13,  13,  13,  14,  14,  14,  15,  15,  15,  15,  16,  16,  16,  16,
     17,  17,  17,  17,  18,  18,  19,  19,  19,  19,  20,  20,  20,  20,  20,  20,
     21,  21,  21,  21,  21,  21,  21,  21,  22,  22,  22,  22,  22,  22,  22,  22,
     23,  23,  23,  23,  23,  23,  23,  23,  24,  24,  24,  24,  24,  24,  24,  24,
     25,  25,  25,  25,  25,  25,  25,  25,  26,  26,  26,  26,  26,  26,  26,  26,
     27,  27,  27,  27,  27,  27,  27,  27,  28,  28,  28,  28,  28,  28,  28,  28,
     29,  29,  29,  29,  29,  29,  29,  29,  30,  30,  30,  30,  30,  30,  30,  30,
     31,  31,  31,  31,  31,  31,  31,  31,  32,  32,  32,  32,  32,  32,  32,  32,
     33,  33,  33,  33,  33,  33,  33,  33,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  35,  35,  35,  35,  35,  35,  36,  36,  36,  36,  36,  36,  36,  36,
     37,  37,  37,  37,  37,  37,  37,  37,  38,  38,  39,  39,  39,  39,  39,  39,
     40,  40,  40,  40,  40,  40,  40,  40,  41,  41,  42,  42,  42,  42,  42,  42,
     43,  43,  44,  44,  45,  45,  46,  46,  47,  47,  47,  47,  47,  47,  47,  47,
     48,  48,  48,  48,  48,  48,  48,  48,  48,  48,  48,  49,  49,  49,  49,  49,
     50,  50,  50,  50,  50,  51,  51,  51,  52,  52,  52,  52,  52,  52,  53,  53,
     54,  54,  55,  55,  55,  55,  55,  55,  55,  55,  55,  56,  56,  56,  56,  56,
     57,  57,  57,  57,  57,  57,  57,  57,  58,  58,  58,  58,  59,  59,  59,  59,
     60,  60,  60,  60,  60,  61,  61,  61,  19,  19,  19,  19,  62,  63,  63,  63,
     64,  64,  64,  64,  64,  64,  64,  64,  65,  65,  65,  65,  66,  66,  66,  66,
     67,  67,  67,  67,  67,  67,  67,  67,  68,  68,  68,  68,  68,  68,  68,  68,
     69,  69,  69,  69,  69,  69,  69,  70,  70,  70,  71,  71,  71,  72,  72,  72,
     73,  73,  73,  73,  73,  74,  74,  74,  74,  75,  75,  75,  75,  75,  75,  75,
     76,  76,  76,  76,  76,  76,  76,  76,  77,  77,  77,  77,  77,  77,  77,  77,
     78,  78,  78,  78,  79,  79,  80,  80,  80,  80,  80,  80,  80,  80,  80,  80,
     81,  81,  81,  81,  81,  81,  81,  81,  82,  82,  83,  83,  83,  83,  83,  83,
     84,  84,  84,  84,  84,  84,  84,  84,  85,  85,  85,  85,  85,  85,  85,  85,
     85,  85,  85,  85,  86,  86,  86,  87,  88,  88,  88,  88,  88,  88,  88,  88,
     89,  89,  89,  89,  89,  89,  89,  89,  90,  90,  90,  90,  90,  90,  90,  90,
     91,  91,  91,  91,  91,  91,  91,  91,  92,  92,  92,  92,  92,  92,  92,  92,
     93,  93,  93,  93,  93,  93,  94,  94,  95,  95,  95,  95,  95,  95,  95,  95,
     96,  96,  96,  97,  97,  97,  97,  97,  98,  98,  98,  98,  98,  98,  99,  99,
    100, 100, 100, 100, 100, 100, 100, 100, 101, 101, 101, 101, 101, 101, 101, 101,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102,  19, 103,
    104, 104, 104, 104, 105, 105, 105, 105, 105, 105, 106, 106, 106, 106, 106, 106,
    107, 107, 107, 108, 108, 108, 108, 108, 108, 109, 110, 110, 111, 111, 111, 112,
    113, 113, 113, 113, 113, 113, 113, 113, 114, 114, 114, 114, 114, 114, 114, 114,
    115, 115, 115, 115, 115, 115, 115, 115, 115, 115, 115, 115, 116, 116, 116, 116,
    117, 117, 117, 117, 117, 117, 117, 117, 118, 118, 118, 118, 118, 118, 118, 118,
    118, 119, 119, 119, 119, 120, 120, 120, 121, 121, 121, 121, 121, 121, 121, 121,
    121, 121, 121, 121, 122, 122, 122, 122, 122, 122, 123, 123, 123, 123, 123, 123,
    124, 124, 125, 125, 125, 125, 125, 125, 125, 125, 125, 125, 125, 125, 125, 125,
    126, 126, 126, 127, 128, 128, 128, 128, 129, 129, 129, 129, 129, 129, 130, 130,
    131, 131, 131, 132, 132, 132, 133, 133, 134, 134, 134, 134, 134, 134, 135, 135,
    136, 136, 136, 136, 136, 136, 137, 137, 138, 138, 138, 138, 138, 138, 139, 139,
    140, 140, 140, 141, 141, 141, 141,  19,  19,  19,  19,  19, 142, 142, 142, 142,
    143, 143, 143, 143, 143, 143, 143, 143, 143, 143, 143, 144, 144, 144, 144, 144,
    145, 145, 145, 145, 145, 145, 145, 145, 146, 146, 146, 146, 146, 146, 146, 146,
    147, 147, 147, 147, 147, 147, 147, 147, 148, 148, 148, 148, 148, 148, 148, 148,
    149, 149, 149, 149, 149, 149, 149, 149, 150, 150, 150, 150, 150, 151, 151, 151,
    151, 151, 151, 151, 151, 151, 151, 151, 152, 153, 154, 155, 155, 156, 156, 157,
    157, 157, 157, 157, 157, 157, 157, 157, 158, 158, 158, 158, 158, 158, 158, 158,
    158, 158, 158, 158, 158, 158, 158, 159, 160, 160, 160, 160, 160, 160, 160, 160,
    161, 161, 161, 161, 161, 161, 161, 161, 162, 162, 162, 162, 163, 163, 163, 163,
    163, 164, 164, 164, 164, 165, 165, 165,  19,  19,  19,  19,  19,  19,  19,  19,
    166, 166, 167, 167, 167, 167, 168, 168, 169, 169, 169, 170, 170, 171, 171, 171,
    172, 172, 173, 173, 173, 173,  19,  19, 174, 174, 174, 174, 174, 175, 175, 175,
    176, 176, 176,  19,  19,  19,  19,  19, 177, 177, 177, 178, 178, 178, 178,  19,
    179, 179, 179, 179, 179, 179, 179, 179, 180, 180, 180, 180, 181, 181, 182, 182,
    183, 183, 183,  19,  19,  19,  19,  19, 184, 184, 185, 185,  19,  19,  19,  19,
    186, 186, 187, 187, 187, 187, 187, 187, 188, 188, 188, 188, 188, 188, 189, 189,
    190, 190,  19,  19, 191, 191, 191, 191, 192, 192, 192, 192, 193, 193, 194, 194,
    195, 195, 195,  19,  19,  19,  19,  19, 196, 196, 196, 196, 196,  19,  19,  19,
     19,  19,  19,  19,  19,  19, 197, 197, 198, 198, 198, 198, 198, 198, 198, 198,
    199, 199, 199, 199, 199, 200, 200, 200, 201, 201, 201, 201, 201, 202, 202, 202,
    203, 203, 203, 203, 203, 203, 204, 204, 205, 205, 205, 205, 205,  19,  19,  19,
     19,  19,  19, 206, 206, 206, 206, 206, 207, 207, 207, 207, 207, 207, 207, 207,
    208, 208, 208, 208, 208, 208,  19,  19, 209, 209, 209, 209, 209, 209, 209, 209,
    210, 210, 210, 210, 210, 210,  19,  19, 211, 211, 211, 211, 211,  19,  19,  19,
     19,  19, 212, 212, 212, 212, 212, 212,  19,  19,  19,  19, 213, 213, 213, 213,
    214, 214, 214, 214, 214, 214, 214, 214, 215, 215, 215, 215, 215, 215, 215, 215,
    216, 216, 216, 216, 216, 216, 216, 216, 216, 216, 216,  19,  19,  19,  19,  19,
    217, 217, 217, 217, 217, 217, 217, 217, 217, 217, 217, 217, 218, 218, 218,  19,
     19,  19,  19,  19,  19, 219, 219, 219, 220, 220, 220, 220, 220, 220, 220, 220,
    220,  19,  19,  19,  19,  19,  19,  19, 221, 221, 221, 221, 221, 221, 221, 221,
    221, 221,  19,  19,  19,  19,  19,  19, 222, 222, 222, 222, 222, 222, 222, 222,
    223, 223, 223, 223, 223, 223, 223, 223, 223, 223, 224,  19,  19,  19,  19,  19,
    225, 225, 225, 225, 225, 225, 225, 225, 226, 226, 226, 226, 226, 226, 226, 226,
    227, 227, 227, 227, 227,  19,  19,  19, 228, 228, 228, 228, 228, 228, 229, 229,
    230, 230, 230, 230, 230, 230, 230, 230, 231, 231, 231, 231, 231, 231, 231, 231,
    231, 231, 231, 231, 231, 231,  19,  19, 232, 232, 232, 232, 232, 232, 232, 232,
    233, 233, 233, 234, 234, 234, 234, 234, 234, 234, 235, 235, 235, 235, 235, 235,
    236, 236, 236, 236, 236, 236, 236, 236, 237, 237, 237, 237, 237, 237, 237, 237,
    238, 238, 238, 238, 238, 238, 238, 238, 239, 239, 239, 239, 239, 240, 240, 240,
    241, 241, 241, 241, 241, 241, 241, 241, 242, 242, 242, 242, 242, 242, 242, 242,
    243, 243, 243, 243, 243, 243, 243, 243, 244, 244, 244, 244, 244, 244, 244, 244,
    245, 245, 245, 245, 245, 245, 245, 245, 245, 245, 245, 245, 245, 245,  19,  19,
    246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 247, 247, 247, 247,
    247, 247, 247, 247, 247, 247, 247, 247, 247, 247,  19,  19,  19,  19,  19,  19,
    248, 248, 248, 248, 248, 248, 248, 248, 248, 248,  19,  19,  19,  19,  19,  19,
    249, 249, 249, 249, 249, 249, 249, 249, 250, 250, 250, 250, 250, 250, 250, 250,
    250, 250, 250, 250, 250, 250, 250,  19, 251, 251, 251, 251, 251, 251, 251, 251,
    252, 252, 252, 252, 252, 252, 252, 252,
};

static RE_UINT8 re_block_stage_4[] = {
      0,   0,   0,   0,   1,   1,   1,   1,   2,   2,   2,   2,   3,   3,   3,   3,
      4,   4,   4,   4,   5,   5,   5,   5,   6,   6,   6,   6,   7,   7,   7,   7,
      8,   8,   8,   8,   9,   9,   9,   9,  10,  10,  10,  10,  11,  11,  11,  11,
     12,  12,  12,  12,  13,  13,  13,  13,  14,  14,  14,  14,  15,  15,  15,  15,
     16,  16,  16,  16,  17,  17,  17,  17,  18,  18,  18,  18,  19,  19,  19,  19,
     20,  20,  20,  20,  21,  21,  21,  21,  22,  22,  22,  22,  23,  23,  23,  23,
     24,  24,  24,  24,  25,  25,  25,  25,  26,  26,  26,  26,  27,  27,  27,  27,
     28,  28,  28,  28,  29,  29,  29,  29,  30,  30,  30,  30,  31,  31,  31,  31,
     32,  32,  32,  32,  33,  33,  33,  33,  34,  34,  34,  34,  35,  35,  35,  35,
     36,  36,  36,  36,  37,  37,  37,  37,  38,  38,  38,  38,  39,  39,  39,  39,
     40,  40,  40,  40,  41,  41,  41,  41,  42,  42,  42,  42,  43,  43,  43,  43,
     44,  44,  44,  44,  45,  45,  45,  45,  46,  46,  46,  46,  47,  47,  47,  47,
     48,  48,  48,  48,  49,  49,  49,  49,  50,  50,  50,  50,  51,  51,  51,  51,
     52,  52,  52,  52,  53,  53,  53,  53,  54,  54,  54,  54,  55,  55,  55,  55,
     56,  56,  56,  56,  57,  57,  57,  57,  58,  58,  58,  58,  59,  59,  59,  59,
     60,  60,  60,  60,  61,  61,  61,  61,  62,  62,  62,  62,  63,  63,  63,  63,
     64,  64,  64,  64,  65,  65,  65,  65,  66,  66,  66,  66,  67,  67,  67,  67,
     68,  68,  68,  68,  69,  69,  69,  69,  70,  70,  70,  70,  71,  71,  71,  71,
     72,  72,  72,  72,  73,  73,  73,  73,  74,  74,  74,  74,  75,  75,  75,  75,
     76,  76,  76,  76,  77,  77,  77,  77,  78,  78,  78,  78,  79,  79,  79,  79,
     80,  80,  80,  80,  81,  81,  81,  81,  82,  82,  82,  82,  83,  83,  83,  83,
     84,  84,  84,  84,  85,  85,  85,  85,  86,  86,  86,  86,  87,  87,  87,  87,
     88,  88,  88,  88,  89,  89,  89,  89,  90,  90,  90,  90,  91,  91,  91,  91,
     92,  92,  92,  92,  93,  93,  93,  93,  94,  94,  94,  94,  95,  95,  95,  95,
     96,  96,  96,  96,  97,  97,  97,  97,  98,  98,  98,  98,  99,  99,  99,  99,
    100, 100, 100, 100, 101, 101, 101, 101, 102, 102, 102, 102, 103, 103, 103, 103,
    104, 104, 104, 104, 105, 105, 105, 105, 106, 106, 106, 106, 107, 107, 107, 107,
    108, 108, 108, 108, 109, 109, 109, 109, 110, 110, 110, 110, 111, 111, 111, 111,
    112, 112, 112, 112, 113, 113, 113, 113, 114, 114, 114, 114, 115, 115, 115, 115,
    116, 116, 116, 116, 117, 117, 117, 117, 118, 118, 118, 118, 119, 119, 119, 119,
    120, 120, 120, 120, 121, 121, 121, 121, 122, 122, 122, 122, 123, 123, 123, 123,
    124, 124, 124, 124, 125, 125, 125, 125, 126, 126, 126, 126, 127, 127, 127, 127,
    128, 128, 128, 128, 129, 129, 129, 129, 130, 130, 130, 130, 131, 131, 131, 131,
    132, 132, 132, 132, 133, 133, 133, 133, 134, 134, 134, 134, 135, 135, 135, 135,
    136, 136, 136, 136, 137, 137, 137, 137, 138, 138, 138, 138, 139, 139, 139, 139,
    140, 140, 140, 140, 141, 141, 141, 141, 142, 142, 142, 142, 143, 143, 143, 143,
    144, 144, 144, 144, 145, 145, 145, 145, 146, 146, 146, 146, 147, 147, 147, 147,
    148, 148, 148, 148, 149, 149, 149, 149, 150, 150, 150, 150, 151, 151, 151, 151,
    152, 152, 152, 152, 153, 153, 153, 153, 154, 154, 154, 154, 155, 155, 155, 155,
    156, 156, 156, 156, 157, 157, 157, 157, 158, 158, 158, 158, 159, 159, 159, 159,
    160, 160, 160, 160, 161, 161, 161, 161, 162, 162, 162, 162, 163, 163, 163, 163,
    164, 164, 164, 164, 165, 165, 165, 165, 166, 166, 166, 166, 167, 167, 167, 167,
    168, 168, 168, 168, 169, 169, 169, 169, 170, 170, 170, 170, 171, 171, 171, 171,
    172, 172, 172, 172, 173, 173, 173, 173, 174, 174, 174, 174, 175, 175, 175, 175,
    176, 176, 176, 176, 177, 177, 177, 177, 178, 178, 178, 178, 179, 179, 179, 179,
    180, 180, 180, 180, 181, 181, 181, 181, 182, 182, 182, 182, 183, 183, 183, 183,
    184, 184, 184, 184, 185, 185, 185, 185, 186, 186, 186, 186, 187, 187, 187, 187,
    188, 188, 188, 188, 189, 189, 189, 189, 190, 190, 190, 190, 191, 191, 191, 191,
    192, 192, 192, 192, 193, 193, 193, 193, 194, 194, 194, 194, 195, 195, 195, 195,
    196, 196, 196, 196, 197, 197, 197, 197, 198, 198, 198, 198, 199, 199, 199, 199,
    200, 200, 200, 200, 201, 201, 201, 201, 202, 202, 202, 202, 203, 203, 203, 203,
    204, 204, 204, 204, 205, 205, 205, 205, 206, 206, 206, 206, 207, 207, 207, 207,
    208, 208, 208, 208, 209, 209, 209, 209, 210, 210, 210, 210, 211, 211, 211, 211,
    212, 212, 212, 212, 213, 213, 213, 213, 214, 214, 214, 214, 215, 215, 215, 215,
    216, 216, 216, 216, 217, 217, 217, 217, 218, 218, 218, 218, 219, 219, 219, 219,
    220, 220, 220, 220, 221, 221, 221, 221, 222, 222, 222, 222, 223, 223, 223, 223,
    224, 224, 224, 224, 225, 225, 225, 225, 226, 226, 226, 226, 227, 227, 227, 227,
    228, 228, 228, 228, 229, 229, 229, 229, 230, 230, 230, 230, 231, 231, 231, 231,
    232, 232, 232, 232, 233, 233, 233, 233, 234, 234, 234, 234, 235, 235, 235, 235,
    236, 236, 236, 236, 237, 237, 237, 237, 238, 238, 238, 238, 239, 239, 239, 239,
    240, 240, 240, 240, 241, 241, 241, 241, 242, 242, 242, 242, 243, 243, 243, 243,
    244, 244, 244, 244, 245, 245, 245, 245, 246, 246, 246, 246, 247, 247, 247, 247,
    248, 248, 248, 248, 249, 249, 249, 249, 250, 250, 250, 250, 251, 251, 251, 251,
    252, 252, 252, 252,
};

static RE_UINT8 re_block_stage_5[] = {
      1,   1,   1,   1,   2,   2,   2,   2,   3,   3,   3,   3,   4,   4,   4,   4,
      5,   5,   5,   5,   6,   6,   6,   6,   7,   7,   7,   7,   8,   8,   8,   8,
      9,   9,   9,   9,  10,  10,  10,  10,  11,  11,  11,  11,  12,  12,  12,  12,
     13,  13,  13,  13,  14,  14,  14,  14,  15,  15,  15,  15,  16,  16,  16,  16,
     17,  17,  17,  17,  18,  18,  18,  18,  19,  19,  19,  19,   0,   0,   0,   0,
     20,  20,  20,  20,  21,  21,  21,  21,  22,  22,  22,  22,  23,  23,  23,  23,
     24,  24,  24,  24,  25,  25,  25,  25,  26,  26,  26,  26,  27,  27,  27,  27,
     28,  28,  28,  28,  29,  29,  29,  29,  30,  30,  30,  30,  31,  31,  31,  31,
     32,  32,  32,  32,  33,  33,  33,  33,  34,  34,  34,  34,  35,  35,  35,  35,
     36,  36,  36,  36,  37,  37,  37,  37,  38,  38,  38,  38,  39,  39,  39,  39,
     40,  40,  40,  40,  41,  41,  41,  41,  42,  42,  42,  42,  43,  43,  43,  43,
     44,  44,  44,  44,  45,  45,  45,  45,  46,  46,  46,  46,  47,  47,  47,  47,
     48,  48,  48,  48,  49,  49,  49,  49,  50,  50,  50,  50,  51,  51,  51,  51,
     52,  52,  52,  52,  53,  53,  53,  53,  54,  54,  54,  54,  55,  55,  55,  55,
     56,  56,  56,  56,  57,  57,  57,  57,  58,  58,  58,  58,  59,  59,  59,  59,
     60,  60,  60,  60,  61,  61,  61,  61,  62,  62,  62,  62,  63,  63,  63,  63,
     64,  64,  64,  64,  65,  65,  65,  65,  66,  66,  66,  66,  67,  67,  67,  67,
     68,  68,  68,  68,  69,  69,  69,  69,  70,  70,  70,  70,  71,  71,  71,  71,
     72,  72,  72,  72,  73,  73,  73,  73,  74,  74,  74,  74,  75,  75,  75,  75,
     76,  76,  76,  76,  77,  77,  77,  77,  78,  78,  78,  78,  79,  79,  79,  79,
     80,  80,  80,  80,  81,  81,  81,  81,  82,  82,  82,  82,  83,  83,  83,  83,
     84,  84,  84,  84,  85,  85,  85,  85,  86,  86,  86,  86,  87,  87,  87,  87,
     88,  88,  88,  88,  89,  89,  89,  89,  90,  90,  90,  90,  91,  91,  91,  91,
     92,  92,  92,  92,  93,  93,  93,  93,  94,  94,  94,  94,  95,  95,  95,  95,
     96,  96,  96,  96,  97,  97,  97,  97,  98,  98,  98,  98,  99,  99,  99,  99,
    100, 100, 100, 100, 101, 101, 101, 101, 102, 102, 102, 102, 103, 103, 103, 103,
    104, 104, 104, 104, 105, 105, 105, 105, 106, 106, 106, 106, 107, 107, 107, 107,
    108, 108, 108, 108, 109, 109, 109, 109, 110, 110, 110, 110, 111, 111, 111, 111,
    112, 112, 112, 112, 113, 113, 113, 113, 114, 114, 114, 114, 115, 115, 115, 115,
    116, 116, 116, 116, 117, 117, 117, 117, 118, 118, 118, 118, 119, 119, 119, 119,
    120, 120, 120, 120, 121, 121, 121, 121, 122, 122, 122, 122, 123, 123, 123, 123,
    124, 124, 124, 124, 125, 125, 125, 125, 126, 126, 126, 126, 127, 127, 127, 127,
    128, 128, 128, 128, 129, 129, 129, 129, 130, 130, 130, 130, 131, 131, 131, 131,
    132, 132, 132, 132, 133, 133, 133, 133, 134, 134, 134, 134, 135, 135, 135, 135,
    136, 136, 136, 136, 137, 137, 137, 137, 138, 138, 138, 138, 139, 139, 139, 139,
    140, 140, 140, 140, 141, 141, 141, 141, 142, 142, 142, 142, 143, 143, 143, 143,
    144, 144, 144, 144, 145, 145, 145, 145, 146, 146, 146, 146, 147, 147, 147, 147,
    148, 148, 148, 148, 149, 149, 149, 149, 150, 150, 150, 150, 151, 151, 151, 151,
    152, 152, 152, 152, 153, 153, 153, 153, 154, 154, 154, 154, 155, 155, 155, 155,
    156, 156, 156, 156, 157, 157, 157, 157, 158, 158, 158, 158, 159, 159, 159, 159,
    160, 160, 160, 160, 161, 161, 161, 161, 162, 162, 162, 162, 163, 163, 163, 163,
    164, 164, 164, 164, 165, 165, 165, 165, 166, 166, 166, 166, 167, 167, 167, 167,
    168, 168, 168, 168, 169, 169, 169, 169, 170, 170, 170, 170, 171, 171, 171, 171,
    172, 172, 172, 172, 173, 173, 173, 173, 174, 174, 174, 174, 175, 175, 175, 175,
    176, 176, 176, 176, 177, 177, 177, 177, 178, 178, 178, 178, 179, 179, 179, 179,
    180, 180, 180, 180, 181, 181, 181, 181, 182, 182, 182, 182, 183, 183, 183, 183,
    184, 184, 184, 184, 185, 185, 185, 185, 186, 186, 186, 186, 187, 187, 187, 187,
    188, 188, 188, 188, 189, 189, 189, 189, 190, 190, 190, 190, 191, 191, 191, 191,
    192, 192, 192, 192, 193, 193, 193, 193, 194, 194, 194, 194, 195, 195, 195, 195,
    196, 196, 196, 196, 197, 197, 197, 197, 198, 198, 198, 198, 199, 199, 199, 199,
    200, 200, 200, 200, 201, 201, 201, 201, 202, 202, 202, 202, 203, 203, 203, 203,
    204, 204, 204, 204, 205, 205, 205, 205, 206, 206, 206, 206, 207, 207, 207, 207,
    208, 208, 208, 208, 209, 209, 209, 209, 210, 210, 210, 210, 211, 211, 211, 211,
    212, 212, 212, 212, 213, 213, 213, 213, 214, 214, 214, 214, 215, 215, 215, 215,
    216, 216, 216, 216, 217, 217, 217, 217, 218, 218, 218, 218, 219, 219, 219, 219,
    220, 220, 220, 220, 221, 221, 221, 221, 222, 222, 222, 222, 223, 223, 223, 223,
    224, 224, 224, 224, 225, 225, 225, 225, 226, 226, 226, 226, 227, 227, 227, 227,
    228, 228, 228, 228, 229, 229, 229, 229, 230, 230, 230, 230, 231, 231, 231, 231,
    232, 232, 232, 232, 233, 233, 233, 233, 234, 234, 234, 234, 235, 235, 235, 235,
    236, 236, 236, 236, 237, 237, 237, 237, 238, 238, 238, 238, 239, 239, 239, 239,
    240, 240, 240, 240, 241, 241, 241, 241, 242, 242, 242, 242, 243, 243, 243, 243,
    244, 244, 244, 244, 245, 245, 245, 245, 246, 246, 246, 246, 247, 247, 247, 247,
    248, 248, 248, 248, 249, 249, 249, 249, 250, 250, 250, 250, 251, 251, 251, 251,
    252, 252, 252, 252,
};

/* Block: 4752 bytes. */

RE_UINT32 re_get_block(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_block_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_block_stage_2[pos + f] << 3;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_block_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_block_stage_4[pos + f] << 2;
    value = re_block_stage_5[pos + code];

    return value;
}

/* Script. */

static RE_UINT8 re_script_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  6,  7,  8,  8,  9, 10, 11,
    12, 13, 14, 15, 10, 10, 16, 10, 10, 10, 10, 17, 10, 18, 19, 20,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 21, 22, 10, 10, 10, 23,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    24, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
};

static RE_UINT8 re_script_stage_2[] = {
      0,   1,   2,   2,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,
     14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,
     30,  31,  32,  32,  33,  34,  35,  36,  37,  37,  37,  37,  37,  38,  39,  40,
     41,  42,  43,  44,  45,  46,  47,  48,  49,  50,  51,  52,   2,   2,  53,  54,
     55,  56,  57,  58,  59,  59,  59,  60,  61,  59,  59,  59,  59,  59,  59,  59,
     62,  62,  59,  59,  59,  59,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,
     73,  74,  75,  76,  77,  78,  79,  59,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  80,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  81,
     82,  82,  82,  82,  82,  82,  82,  82,  82,  83,  84,  84,  85,  86,  87,  88,
     89,  90,  91,  92,  93,  94,  95,  96,  32,  32,  32,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  97,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  71,  71,  99, 100, 101, 102, 103, 103, 104, 105, 106, 107, 108, 109,
    110, 111, 112, 113,  98, 114, 115, 116, 117, 118, 119,  98, 120, 120, 121,  98,
    122, 123, 124, 125, 126, 127, 128, 129, 130,  98,  98,  98, 131,  98,  98,  98,
    132, 133, 134, 135, 136, 137, 138,  98,  98, 139,  98, 140, 141, 142,  98,  98,
     98, 143,  98,  98,  98, 144,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    145, 145, 145, 145, 145, 145, 145, 146, 147,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    148, 148, 148, 148, 148, 148, 148, 148, 149,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    150, 150, 150, 150, 151, 152, 153, 154,  98,  98,  98,  98,  98,  98, 155, 156,
    157,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98, 158, 159,  98,  98,  98,  98,  98,  98,
     59, 160, 161, 162, 163,  98, 164,  98, 165, 166, 167,  59,  59, 168,  59, 169,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    170, 171,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98, 172, 173,  98,  98,
    174, 175, 176, 177, 178,  98, 179, 180,  59, 181, 182, 183, 184, 185, 186, 187,
    188, 189,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71, 190,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71, 191,  71,
    192,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     71,  71,  71,  71, 192,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    193,  98, 194, 195,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
};

static RE_UINT16 re_script_stage_3[] = {
      0,   0,   0,   0,   1,   2,   1,   2,   0,   0,   3,   3,   4,   5,   4,   5,
      4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   6,   0,   0,   7,   0,
      8,   8,   8,   8,   8,   8,   8,   9,  10,  11,  12,  11,  11,  11,  13,  11,
     14,  14,  14,  14,  14,  14,  14,  14,  15,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  16,  17,  18,  16,  17,  19,  20,  21,  21,  22,  21,  23,  24,
     25,  26,  27,  27,  28,  29,  30,  31,  27,  27,  27,  27,  27,  32,  27,  27,
     33,  34,  34,  34,  35,  27,  27,  27,  36,  36,  36,  37,  38,  38,  38,  39,
     40,  40,  41,  42,  43,  44,  45,  45,  45,  45,  27,  46,  45,  45,  47,  27,
     48,  48,  48,  48,  48,  49,  50,  48,  51,  52,  53,  54,  55,  56,  57,  58,
     59,  60,  61,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,
     75,  76,  77,  78,  79,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,
     91,  92,  93,  94,  95,  96,  97,  98,  99, 100, 101, 102, 103, 104, 105, 106,
    107, 108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122,
    123, 124, 124, 125, 124, 126,  45,  45, 127, 128, 129, 130, 131, 132,  45,  45,
    133, 133, 133, 133, 134, 133, 135, 136, 133, 134, 133, 137, 137, 138,  45,  45,
    139, 139, 139, 139, 139, 139, 139, 139, 139, 139, 140, 140, 141, 140, 140, 142,
    143, 143, 143, 143, 143, 143, 143, 143, 144, 144, 144, 144, 145, 146, 144, 144,
    145, 144, 144, 147, 148, 149, 144, 144, 144, 148, 144, 144, 144, 150, 144, 151,
    144, 152, 153, 153, 153, 153, 153, 154, 155, 155, 155, 155, 155, 155, 155, 155,
    156, 157, 158, 158, 158, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168,
    169, 169, 169, 169, 169, 170, 171, 171, 172, 173, 174, 174, 174, 174, 174, 175,
    174, 174, 176, 155, 155, 155, 155, 177, 178, 179, 180, 180, 181, 182, 183, 184,
    185, 185, 186, 185, 187, 188, 169, 169, 189, 190, 191, 191, 191, 192, 191, 193,
    194, 194, 195, 196,  45,  45,  45,  45, 197, 197, 197, 197, 198, 197, 197, 199,
    200, 200, 200, 200, 201, 201, 201, 202, 203, 203, 203, 204, 205, 206, 206, 206,
     45,  45,  45,  45, 207, 208, 209, 210,   4,   4, 211,   4,   4, 212, 213, 214,
      4,   4,   4, 215,   8,   8,   8, 216,  11, 217,  11,  11, 217, 218,  11, 219,
     11,  11,  11, 220, 220, 221,  11, 222, 223,   0,   0,   0,   0,   0, 224, 225,
    226, 227,   0, 228,  45,   8,   8, 229,   0,   0, 230, 231, 232,   0,   4,   4,
    233,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 234,   0,   0, 235,  45, 234,  45,   0,   0,
    236, 236, 236, 236, 236, 236, 236, 236,   0,   0,   0,   0,   0,   0,   0, 237,
      0, 238,   0, 239, 240, 241,  45,  45, 242, 242, 243, 242, 242, 243,   4,   4,
    244, 244, 244, 244, 244, 244, 244, 245, 140, 140, 141, 246, 246, 246, 247, 248,
    144, 249, 250, 250, 250, 250,  14,  14,   0,   0,   0,   0, 251,  45,  45,  45,
    252, 253, 252, 252, 252, 252, 252, 254, 252, 252, 252, 252, 252, 252, 252, 252,
    252, 252, 252, 252, 252, 255,  45, 256, 257,   0, 258, 259, 260, 261, 261, 261,
    261, 262, 263, 264, 264, 264, 264, 265, 266, 267, 268, 269, 143, 143, 143, 143,
    270,   0, 267, 271,   0,   0, 272, 264, 143, 270,   0,   0,   0,   0, 143, 273,
      0,   0,   0,   0,   0, 264, 264, 274, 264, 264, 264, 264, 264, 275,   0,   0,
    252, 252, 252, 255,   0,   0,   0,   0, 252, 252, 252, 252, 276,  45,  45,  45,
    277, 277, 277, 277, 277, 277, 277, 277, 278, 277, 277, 277, 279, 280, 280, 280,
    281, 281, 281, 281, 281, 281, 281, 281, 281, 281, 282,  45,  14,  14,  14,  14,
     14, 283, 284, 284, 284, 284, 284, 285,   0,   0, 286,   4,   4,   4,   4,   4,
    287,   4, 288, 289,  45,  45,  45, 290, 291, 291, 292, 293, 294, 294, 294, 295,
    296, 296, 296, 296, 297, 298,  48, 299, 300, 300, 301, 302, 302, 303, 143, 304,
    305, 305, 305, 305, 306, 307, 139, 308, 309, 309, 309, 310, 311, 312, 139, 139,
    313, 313, 313, 313, 314, 315, 316, 317, 318, 319, 250,   4,   4, 320, 321,  45,
     45,  45,  45,  45, 316, 316, 322, 323, 143, 143, 324, 143, 325, 143, 143, 326,
     45,  45,  45,  45,  45,  45,  45,  45, 252, 252, 252, 252, 252, 252, 327, 252,
    252, 252, 252, 252, 252, 328,  45,  45, 329, 330,  21, 331, 332,  27,  27,  27,
     27,  27,  27,  27, 333, 334,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,
     27,  27,  27, 335,  45,  27,  27,  27,  27, 336,  27,  27, 337,  45,  45, 338,
      8, 293, 339,   0,   0, 340, 341, 342,  27,  27,  27,  27,  27,  27,  27, 343,
    344,   0,   1,   2,   1,   2, 345, 263, 264, 346, 143, 270, 347, 348, 349, 350,
    351, 352, 353, 354, 355, 355,  45,  45, 352, 352, 352, 352, 352, 352, 352, 356,
    357,   0,   0, 358,  11,  11,  11,  11, 359, 256, 360,  45,  45,   0,   0, 361,
    362, 363, 364, 364, 364, 365, 366, 256, 367, 367, 368, 369, 370, 371, 371, 372,
    373, 374, 375, 375, 376, 377,  45,  45, 378, 378, 378, 378, 378, 379, 379, 379,
    380, 381, 382,  45,  45,  45,  45,  45, 383, 383, 384, 385, 385, 385, 386,  45,
    387, 387, 387, 387, 387, 387, 387, 387, 387, 387, 387, 388, 387, 389, 390,  45,
    391, 392, 392, 393, 394, 395, 396, 396, 397, 398, 399,  45,  45,  45,  45,  45,
    400, 401, 402, 403,  45,  45,  45,  45, 404, 404, 405, 406,  45,  45,  45,  45,
    407, 408, 409, 410, 411, 412, 413, 413, 414, 414,  45,  45, 415, 415, 416, 417,
    418, 418, 418, 419, 420, 421, 422, 423, 424, 425, 426,  45,  45,  45,  45,  45,
    427, 427, 427, 427, 428,  45,  45,  45,  45,  45,  45,  45,  45,  45,  27, 429,
    430, 430, 430, 430, 431, 432, 430, 433, 434, 434, 434, 434, 435, 436, 437, 438,
    439, 439, 439, 440, 441, 442, 442, 443, 444, 444, 444, 444, 445, 446, 447, 448,
    449, 450, 449, 451,  45,  45,  45,  45,  45,  45,  45, 452, 452, 452, 453, 454,
    455, 456, 457, 458, 459, 460, 461, 462, 463, 463, 463, 463, 464, 465,  45,  45,
    466, 466, 466, 467, 468,  45,  45,  45, 469, 469, 469, 469, 470, 471,  45,  45,
    472, 472, 472, 473, 474,  45,  45,  45,  45,  45, 475, 475, 475, 475, 475, 476,
     45,  45,  45,  45, 477, 477, 477, 478, 479, 479, 479, 479, 479, 479, 479, 479,
    479, 480,  45,  45,  45,  45,  45,  45, 479, 479, 479, 479, 479, 479, 481, 482,
    483, 483, 483, 483, 483, 483, 483, 483, 483, 483, 484,  45,  45,  45,  45,  45,
    284, 284, 284, 284, 284, 284, 284, 284, 284, 284, 284, 485, 486, 487, 488,  45,
     45,  45,  45,  45,  45, 489, 490, 491, 492, 492, 492, 492, 493, 494, 495, 496,
    492,  45,  45,  45,  45,  45,  45,  45, 497, 497, 497, 497, 498, 497, 497, 499,
    500, 497,  45,  45,  45,  45,  45,  45, 501,  45,  45,  45,  45,  45,  45,  45,
    502, 502, 502, 502, 502, 502, 503, 504, 505, 506, 272,  45,  45,  45,  45,  45,
      0,   0,   0,   0,   0,   0,   0, 507,   0,   0, 508,   0,   0,   0, 509, 510,
    511,   0, 512,   0,   0, 228,  45,  45,  11,  11,  11,  11, 513,  45,  45,  45,
      0,   0,   0,   0,   0, 235,   0, 241,   0,   0,   0,   0,   0, 224,   0,   0,
      0, 514, 515, 516, 517,   0,   0,   0, 518, 519,   0, 520, 521, 522,   0,   0,
      0,   0, 238,   0,   0,   0,   0,   0,   0,   0,   0,   0, 523,   0,   0,   0,
    524, 524, 524, 524, 524, 524, 524, 524, 524, 524, 524, 524, 525, 526,  45,  45,
    527,  27, 528, 529, 530, 531, 532, 533, 534, 535, 536, 535,  45,  45,  45, 333,
      0,   0, 256,   0,   0,   0,   0,   0,   0, 272, 226, 344, 344, 344,   0, 507,
    537,   0, 226,   0,   0,   0, 256,   0,   0, 234,  45,  45,  45,  45, 538,   0,
    539,   0,   0, 234, 540, 241,  45,  45,   0,   0, 537,   0,   0,   0,   0, 228,
      0,   0,   0,   0, 226, 541,   0, 542,   0,   0,   0,   0,   0,   0,   0, 226,
      0,   0,   0,   0, 234,   0,   0, 543,   0,   0, 517,   0,   0,   0,   0,   0,
      0,   0,   0,   0, 544,   0,   0,   0,   0,   0,   0,   0,   0,  45, 537, 272,
      0,   0,   0,   0,   0,   0,   0, 272,   0,   0,   0,   0,   0, 545,  45,  45,
    256,   0,   0,   0, 542, 293,   0,   0, 542,   0, 228,  45,  45,  45,  45,  45,
    252, 252, 252, 252, 252, 546,  45,  45, 252, 252, 252, 547, 252, 252, 252, 252,
    252, 327,  45,  45,  45,  45,  45,  45, 548,  45,   0,   0,   0,   0,   0,   0,
      8,   8,   8,   8,   8,   8,   8,   8,   8,   8,   8,   8,   8,   8,   8,  45,
};

static RE_UINT16 re_script_stage_4[] = {
      0,   0,   0,   0,   1,   2,   2,   2,   2,   2,   3,   0,   0,   0,   4,   0,
      2,   2,   2,   2,   2,   3,   2,   2,   2,   2,   5,   0,   2,   5,   6,   0,
      7,   7,   7,   7,   8,   9,  10,  11,  12,  13,  14,  15,   8,   8,   8,   8,
     16,   8,   8,   8,  17,  18,  18,  18,  19,  19,  19,  19,  19,  20,  19,  19,
     21,  22,  22,  22,  22,  22,  22,  22,  22,  23,  21,  22,  22,  22,  24,  21,
     25,  26,  26,  26,  26,  26,  26,  26,  26,  26,  12,  12,  26,  26,  27,  12,
     26,  28,  12,  12,  29,  30,  29,  31,  29,  29,  32,  33,  29,  29,  29,  29,
     31,  29,  34,   7,   7,  35,  29,  29,   0,   0,  36,  29,  37,  29,  29,  29,
     29,  29,  29,  30,  38,  38,  38,  39,  38,  38,  38,  38,  38,  38,  40,  41,
     42,  42,  42,  42,  43,  12,  12,  12,  44,  44,  44,  44,  44,  44,  45,  12,
     46,  46,  46,  46,  46,  46,  46,  47,  46,  46,  46,  48,  49,  49,  49,  49,
     49,  49,  49,  50,  12,  12,  12,  12,  51,  12,  12,  12,  12,  29,  29,  29,
     52,  52,  52,  52,  53,  52,  52,  52,  52,  54,  52,  52,  55,  56,  55,  57,
     57,  55,  55,  55,  55,  55,  58,  55,  59,  60,  61,  55,  55,  57,  57,  62,
     12,  63,  12,  64,  55,  60,  55,  55,  55,  55,  55,  12,  65,  65,  66,  67,
     68,  69,  69,  69,  69,  69,  70,  69,  70,  71,  72,  70,  66,  67,  68,  72,
     73,  12,  65,  74,  12,  75,  69,  69,  69,  72,  12,  12,  76,  76,  77,  78,
     78,  77,  77,  77,  77,  77,  79,  77,  79,  76,  80,  77,  77,  78,  78,  80,
     81,  12,  12,  12,  77,  82,  77,  77,  80,  12,  12,  12,  83,  83,  84,  85,
     85,  84,  84,  84,  84,  84,  86,  84,  86,  83,  87,  84,  84,  85,  85,  87,
     12,  88,  12,  89,  84,  88,  84,  84,  84,  84,  12,  12,  90,  91,  92,  90,
     93,  94,  95,  93,  96,  97,  92,  90,  98,  98,  94,  90,  92,  90,  93,  94,
     97,  96,  12,  12,  12,  90,  98,  98,  98,  98,  92,  12,  99, 100,  99, 101,
    101,  99,  99,  99,  99,  99, 101,  99,  99,  99, 102, 100,  99, 101, 101, 102,
     12, 103, 102,  12,  99, 104,  99,  99,  12,  12,  99,  99, 105, 105, 106, 107,
    107, 106, 106, 106, 106, 106, 107, 106, 106, 105, 108, 106, 106, 107, 107, 108,
     12, 109,  12, 110, 106, 111, 106, 106, 109,  12,  12,  12, 112, 112, 113, 114,
    114, 113, 113, 113, 113, 113, 113, 113, 113, 113, 115, 112, 113, 114, 114, 115,
     12, 116,  12,  12, 113, 117, 113, 113, 113, 118, 112, 113, 119, 120, 121, 121,
    121, 122, 119, 121, 121, 121, 121, 121, 123, 121, 121, 124, 121, 122, 125, 126,
    121, 127, 121, 121,  12, 119, 121, 121, 119, 128,  12,  12, 129, 130, 130, 130,
    130, 130, 130, 130, 130, 130, 131, 132, 130, 130, 130,  12, 133, 134, 135, 136,
     12, 137, 138, 137, 138, 139, 140, 138, 137, 137, 141, 142, 137, 135, 137, 142,
    137, 137, 142, 137, 143, 143, 143, 143, 143, 143, 144, 143, 143, 143, 143, 145,
    144, 143, 143, 143, 143, 143, 143, 146, 143, 147, 148,  12, 149, 149, 149, 149,
    150, 150, 150, 150, 150, 151,  12, 152, 150, 150, 153, 150, 154, 154, 154, 154,
    155, 155, 155, 155, 155, 155, 156, 157, 155, 158, 156, 157, 156, 157, 155, 158,
    156, 157, 155, 155, 155, 158, 155, 155, 155, 155, 158, 159, 155, 155, 155, 160,
    155, 155, 157,  12, 161, 161, 161, 161, 161, 162,  12,  12, 163, 163, 163, 163,
    164, 164, 164, 164, 164, 164, 164, 165, 166, 166, 166, 166, 166, 166, 167, 168,
    166, 166, 169,  12, 170, 170, 170, 171, 170, 172,  12,  12, 173, 173, 173, 173,
    173, 174,  12,  12, 175, 175, 175, 175, 175,  12,  12,  12, 176, 176, 176, 177,
    177,  12,  12,  12, 178, 178, 178, 178, 178, 178, 178, 179, 178, 178, 179,  12,
    180, 181, 182, 183, 182, 182, 184,  12, 182, 182, 182, 182, 182, 182,  12,  12,
    182, 182, 183,  12, 163, 185,  12,  12, 186, 186, 186, 186, 186, 186, 186, 187,
    186, 186, 186,  12, 188, 186, 186, 186, 189, 189, 189, 189, 189, 189, 189, 190,
    189, 191,  12,  12, 192, 192, 192, 192, 192, 192, 192,  12, 192, 192, 193,  12,
    192, 192, 194, 195, 196, 196, 196, 196, 196, 196, 196, 197, 198, 198, 198, 198,
    198, 198, 198, 199, 198, 198, 198, 200, 198, 198, 201,  12, 198, 198, 198, 201,
      7,   7,   7, 202, 203, 203, 203, 203, 203, 203, 203,  12, 203, 203, 203, 204,
    205, 205, 205, 205, 206, 206, 206, 206, 206,  12,  12, 206, 207, 207, 207, 207,
    207, 207, 208, 207, 207, 207, 209, 210, 211, 211, 211, 211, 205, 205,  12,  12,
    212,   7,   7,   7, 213,   7, 214, 215,   0, 216, 217,  12,   2, 218, 219,   2,
      2,   2,   2, 220, 221, 218, 222,   2,   2,   2, 223,   2,   2,   2,   2, 224,
      7, 217,  12,   7,   8, 225,   8, 225,   8,   8, 226, 226,   8,   8,   8, 225,
      8,  15,   8,   8,   8,  10,   8, 227,  10,  15,   8,  14,   0,   0,   0, 228,
      0, 229,   0,   0, 230,   0,   0, 231,   0,   0,   0, 232,   2,   2,   2, 233,
      0,   0,   0, 234, 235,  12,  12,  12,   0, 236, 237,   0,   4,   0,   0,   0,
      0,   0,   0,   4,   2,   2, 238,  12,   0,   0, 232,  12,   0, 232,  12,  12,
    239, 239, 239, 239,   0, 240,   0,   0,   0, 234,   0,   0,   0,   0, 234, 241,
      0,   0, 229,   0, 234,  12,  12,  12, 242, 242, 242, 242, 242, 242, 242, 243,
     18,  18,  18,  18,  18,  12, 244,  18, 245, 245, 245, 245, 245, 245,  12, 246,
    247,  12,  12, 246, 155, 158,  12,  12, 155, 158, 155, 158, 232,  12,  12,  12,
    248, 248, 248, 248, 248, 248, 249, 248, 248,  12,  12,  12, 248, 250,  12,  12,
      0,   0,   0,  12,   0, 251,   0,   0, 252, 248, 253, 254,   0,   0, 248,   0,
    255, 256, 256, 256, 256, 256, 256, 256, 256, 257, 258, 259, 260, 261, 261, 261,
    261, 261, 261, 261, 261, 261, 262, 260,  12, 263, 264, 264, 264, 264, 264, 264,
    264, 264, 264, 265, 266, 154, 154, 154, 154, 154, 154, 267, 264, 264, 268,  12,
      0,  12,  12,  12, 154, 154, 154, 269, 261, 261, 261, 270, 261, 261,   0,   0,
    248, 248, 248, 271, 272, 272, 272, 272, 272, 272, 272, 273, 272, 274,  12,  12,
    275, 275, 275, 275, 276, 276, 276, 276, 276, 276, 276,  12,  19,  19,  19, 277,
    278, 278, 278, 278, 278, 278,  12,  12, 237,   2,   2,   2,   2,   2, 231, 279,
      2,   2,   2, 280, 280,  12,  12,  12,  12, 281,   2,   2, 282, 282, 282, 282,
    282, 282, 282,  12,   0,   0, 234,  12, 283, 283, 283, 283, 283, 283,  12,  12,
    284, 284, 284, 284, 284, 285,  12, 286, 284, 284, 287,  12,  52,  52,  52,  12,
    288, 288, 288, 288, 288, 288, 288, 289, 290, 290, 290, 290, 290,  12,  12, 291,
    154, 154, 154, 292, 293, 293, 293, 293, 293, 293, 293, 294, 293, 293, 295, 296,
    149, 149, 149, 297, 298, 298, 298, 298, 298, 299,  12,  12, 298, 298, 298, 300,
    298, 298, 300, 298, 301, 301, 301, 301, 302,  12,  12,  12,  12,  12, 303, 301,
    304, 304, 304, 304, 304, 305,  12,  12, 159, 158, 159, 158, 159, 158,  12,  12,
      2,   2,   3,   2,  12, 306,  12,  12, 304, 304, 304, 307, 304, 304, 307,  12,
    154,  12,  12,  12, 154, 267, 308, 154, 154, 154, 154,  12, 248, 248, 248, 250,
    248, 248, 250,  12,   2, 279,  12,  12, 309,  22,  12,  25,  26,  27,  26, 310,
    311, 312,  26,  26, 313,  12,  12,  12, 314,  29,  29,  29,  29,  29,  29, 315,
    316,  29,  29,  29,  29,  29,  12,  12,  29,  29,  29, 313,   7,   7,   7, 217,
    232,   0,   0,   0,   0, 232,   0,  12,  29, 317,  29,  29,  29,  29,  29, 318,
    241,   0,   0,   0,   0, 319, 261, 261, 261, 261, 261, 320, 321, 154, 321, 154,
    321, 154, 321, 292,   0, 232,   0, 232,  12,  12, 241, 234, 322, 322, 322, 323,
    322, 322, 322, 322, 322, 324, 322, 322, 322, 322, 324, 325, 322, 322, 322, 326,
    322, 322, 324,  12, 232, 132,   0,   0,   0, 132,   0,   0,   8,   8,   8, 327,
    327,  12,  12,  12,   0,   0,   0, 328, 329, 329, 329, 329, 329, 329, 329, 330,
    331, 331, 331, 331, 332,  12,  12,  12, 214,   0,   0,   0, 333, 333, 333, 333,
    333,  12,  12,  12, 334, 334, 334, 334, 334, 334, 335,  12, 336, 336, 336, 336,
    336, 336, 337,  12, 338, 338, 338, 338, 338, 338, 338, 339, 340, 340, 340, 340,
    340,  12, 340, 340, 340, 341,  12,  12, 342, 342, 342, 342, 343, 343, 343, 343,
    344, 344, 344, 344, 344, 344, 344, 345, 344, 344, 345,  12, 346, 346, 346, 346,
    346, 346,  12,  12, 347, 347, 347, 347, 347,  12,  12, 348, 349, 349, 349, 349,
    349, 350,  12,  12, 349, 351,  12,  12, 349, 349,  12,  12, 352, 353, 354, 352,
    352, 352, 352, 352, 352, 355, 356, 357, 358, 358, 358, 358, 358, 359, 358, 358,
    360, 360, 360, 360, 361, 361, 361, 361, 361, 361, 361, 362,  12, 363, 361, 361,
    364, 364, 364, 364, 364, 364, 364, 365, 366, 366, 366, 366, 366, 366, 367, 368,
    369, 369, 369, 369, 370, 370, 370, 370, 370, 370,  12, 371, 372, 373,  12, 372,
    372, 374, 374, 372, 372, 372, 372, 372, 372,  12, 375, 376, 372, 372,  12,  12,
    372, 372, 377,  12, 378, 378, 378, 378, 379, 379, 379, 379, 380, 380, 380, 380,
    380, 381, 382, 380, 380, 381,  12,  12, 383, 383, 383, 383, 383, 384, 385, 383,
    386, 386, 386, 386, 386, 387, 386, 386, 388, 388, 388, 388, 389,  12, 388, 388,
    390, 390, 390, 390, 391,  12, 392, 393,  12,  12, 392, 390, 394, 394, 394, 394,
    394, 394, 395,  12,  29,  29,  29,  51, 396, 396, 396, 396, 396, 396, 396, 397,
    398, 396, 396, 396,  12,  12,  12, 399, 400, 400, 400, 400, 401,  12,  12,  12,
    402, 402, 402, 402, 402, 402, 403,  12, 402, 402, 404,  12, 405, 405, 405, 405,
    405, 406, 405, 405, 405,  12,  12,  12, 407, 407, 407, 407, 407, 408,  12,  12,
    409, 409, 409, 409, 409, 409, 410, 411, 409, 409, 412,  12, 120, 121, 121, 121,
    121, 128,  12,  12, 413, 413, 413, 413, 414, 413, 413, 413, 413, 413, 413, 415,
    416, 416, 416, 416, 416, 416, 417,  12, 416, 416, 418,  12, 419, 419, 420, 421,
    421, 420, 420, 420, 420, 420, 422, 420, 422, 419, 423, 420, 420, 421, 421, 423,
     12, 424,  12, 419, 420, 425, 420, 426, 420, 426,  12,  12, 427, 427, 427, 427,
    427, 427,  12,  12, 427, 427, 428,  12, 429, 429, 429, 429, 429, 430, 429, 429,
    429, 429, 430,  12, 431, 431, 431, 431, 431, 432,  12,  12, 431, 431, 433,  12,
    434, 434, 434, 434, 434, 434,  12,  12, 434, 434, 435,  12, 436, 436, 436, 436,
    437,  12,  12, 438, 439, 439, 439, 439, 439, 439, 440,  12, 441, 441, 441, 441,
    441, 441, 442,  12, 441, 441, 441, 443, 441, 442,  12,  12, 444, 444, 444, 444,
    444, 444, 444, 445, 278, 278, 446,  12, 447, 447, 447, 447, 447, 447, 447, 448,
    447, 447, 449, 450, 451, 451, 451, 451, 451, 451, 451, 452, 451, 452,  12,  12,
    453, 453, 453, 453, 453, 454,  12,  12, 453, 453, 455, 453, 455, 453, 453, 453,
    453, 453,  12, 456, 457, 457, 457, 457, 457, 458,  12,  12, 457, 457, 457, 459,
     12,  12,  12, 460, 461,  12,  12,  12, 462, 462, 462, 462, 462, 462, 463,  12,
    462, 462, 462, 464, 462, 462, 464,  12, 462, 462, 465, 462,   0, 234,  12,  12,
      0, 232, 241,   0,   0, 466, 228,   0,   0,   0, 466,   7, 212, 467,   7,   0,
      0,   0, 468, 228,   8, 225,  12,  12,   0,   0,   0, 229, 469, 470, 241, 229,
      0,   0, 471, 241,   0, 241,   0,   0,   0, 471, 232, 241,   0, 229,   0, 229,
      0,   0, 471, 232,   0, 472, 240,   0, 229,   0,   0,   0,   0,   0,   0, 240,
    473, 473, 473, 473, 473, 474, 473, 473, 473, 475,  12,  12,  29, 476,  29,  29,
    477, 478, 476,  29,  51,  29, 479,  12, 480, 314, 479, 476, 477, 478, 479, 479,
    477, 478,  51,  29,  51,  29, 476, 481,  29,  29, 482,  29,  29,  29,  29,  12,
    476, 476, 482,  29,   0,   0,   0, 483,  12, 240,   0,   0, 484,  12,  12,  12,
      0,   0, 483,  12,  12,   0,   0,   0,   0,   0,  12,  12,   0,   0, 471,   0,
    232, 241,   0,   0,   0, 483,  12,  12, 248, 485,  12,  12, 248, 271,  12,  12,
    486,  12,  12,  12,
};

static RE_UINT8 re_script_stage_5[] = {
      1,   1,   1,   1,   1,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   1,
      1,   1,   2,   1,   2,   1,   1,   1,   1,   1,  35,  35,  41,  41,  41,  41,
      3,   3,   3,   3,   1,   3,   3,   3,   0,   0,   3,   3,   3,   3,   1,   3,
      0,   0,   0,   0,   3,   1,   3,   1,   3,   3,   3,   0,   3,   0,   3,   3,
      3,   3,   0,   3,   3,   3,  55,  55,  55,  55,  55,  55,   4,   4,   4,   4,
      4,  41,  41,   4,   0,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   0,
      0,   1,   5,   0,   0,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   0,
      6,   0,   0,   0,   7,   7,   7,   7,   7,   1,   7,   7,   1,   7,   7,   7,
      7,   7,   7,   1,   1,   0,   7,   1,   7,   7,   7,  41,  41,  41,   7,   7,
      1,   1,   7,   7,  41,   7,   7,   7,   8,   8,   8,   8,   8,   8,   0,   8,
      8,   8,   8,   0,   0,   8,   8,   8,   9,   9,   9,   9,   9,   9,   0,   0,
     66,  66,  66,  66,  66,  66,  66,   0,  82,  82,  82,  82,  82,  82,   0,   0,
     82,  82,  82,   0,  95,  95,  95,  95,   0,   0,  95,   0,   7,   7,   7,   0,
     10,  10,  10,  10,  10,  41,  41,  10,   1,   1,  10,  10,  11,  11,  11,  11,
      0,  11,  11,  11,  11,   0,   0,  11,  11,   0,  11,  11,  11,   0,  11,   0,
      0,   0,  11,  11,  11,  11,   0,   0,  11,  11,  11,   0,   0,   0,   0,  11,
     11,  11,   0,  11,   0,  12,  12,  12,  12,  12,  12,   0,   0,   0,   0,  12,
     12,   0,   0,  12,  12,  12,  12,  12,  12,   0,  12,  12,   0,  12,  12,   0,
     12,  12,   0,   0,   0,  12,   0,   0,  12,   0,  12,   0,   0,   0,  12,  12,
      0,  13,  13,  13,  13,  13,  13,  13,  13,  13,   0,  13,  13,   0,  13,  13,
     13,  13,   0,   0,  13,   0,   0,   0,   0,   0,  13,  13,   0,  14,  14,  14,
     14,  14,  14,  14,  14,   0,   0,  14,  14,   0,  14,  14,  14,  14,   0,   0,
      0,   0,  14,  14,  14,  14,   0,  14,   0,   0,  15,  15,   0,  15,  15,  15,
     15,  15,  15,   0,  15,   0,  15,  15,  15,  15,   0,   0,   0,  15,  15,   0,
      0,   0,   0,  15,  15,   0,   0,   0,  15,  15,  15,  15,  16,  16,  16,  16,
      0,  16,  16,  16,  16,   0,  16,  16,  16,  16,   0,   0,   0,  16,  16,   0,
      0,   0,  16,  16,   0,  17,  17,  17,  17,  17,  17,  17,  17,   0,  17,  17,
     17,  17,   0,   0,   0,  17,  17,   0,   0,   0,  17,   0,   0,   0,  17,  17,
      0,  18,  18,  18,  18,  18,  18,  18,  18,   0,  18,  18,  18,  18,  18,   0,
      0,   0,   0,  18,   0,   0,  18,  18,  18,  18,   0,   0,   0,   0,  19,  19,
      0,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,   0,  19,  19,   0,  19,
      0,  19,   0,   0,   0,   0,  19,   0,   0,   0,   0,  19,  19,   0,  19,   0,
     19,   0,   0,   0,   0,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,   0,
      0,   0,   0,   1,   0,  21,  21,   0,  21,   0,   0,  21,  21,   0,  21,   0,
      0,  21,   0,   0,  21,  21,  21,  21,   0,  21,  21,  21,   0,  21,   0,  21,
      0,   0,  21,  21,  21,  21,   0,  21,  21,  21,   0,   0,  22,  22,  22,  22,
      0,  22,  22,  22,  22,   0,   0,   0,  22,   0,  22,  22,  22,   1,   1,   1,
      1,  22,  22,   0,  23,  23,  23,  23,  24,  24,  24,  24,  24,  24,   0,  24,
      0,  24,   0,   0,  24,  24,  24,   1,  25,  25,  25,  25,  26,  26,  26,  26,
     26,   0,  26,  26,  26,  26,   0,   0,  26,  26,  26,   0,   0,  26,  26,  26,
     26,   0,   0,   0,  27,  27,  27,  27,  27,   0,   0,   0,  28,  28,  28,  28,
     29,  29,  29,  29,  29,   0,   0,   0,  30,  30,  30,  30,  30,  30,  30,   1,
      1,   1,  30,  30,  30,   0,   0,   0,  42,  42,  42,  42,  42,   0,  42,  42,
     42,   0,   0,   0,  43,  43,  43,  43,  43,   1,   1,   0,  44,  44,  44,  44,
     45,  45,  45,  45,  45,   0,  45,  45,  31,  31,  31,  31,  31,  31,   0,   0,
     32,  32,   1,   1,  32,   1,  32,  32,  32,  32,  32,  32,  32,  32,  32,   0,
     32,  32,   0,   0,  28,  28,   0,   0,  46,  46,  46,  46,  46,  46,  46,   0,
     46,   0,   0,   0,  47,  47,  47,  47,  47,  47,   0,   0,  47,   0,   0,   0,
     56,  56,  56,  56,  56,  56,   0,   0,  56,  56,  56,   0,   0,   0,  56,  56,
     54,  54,  54,  54,   0,   0,  54,  54,  78,  78,  78,  78,  78,  78,  78,   0,
     78,   0,   0,  78,  78,  78,   0,   0,  41,  41,  41,   0,  62,  62,  62,  62,
     62,   0,   0,   0,  67,  67,  67,  67,  93,  93,  93,  93,  68,  68,  68,  68,
      0,   0,   0,  68,  68,  68,   0,   0,   0,  68,  68,  68,  69,  69,  69,  69,
     41,  41,  41,   1,  41,   1,  41,  41,  41,   1,   1,   1,   1,  41,   1,   1,
     41,   1,   1,   0,  41,  41,   0,   0,   2,   2,   3,   3,   3,   3,   3,   4,
      2,   3,   3,   3,   3,   3,   2,   2,   3,   3,   3,   2,   4,   2,   2,   2,
      2,   2,   2,   3,   3,   3,   0,   0,   0,   3,   0,   3,   0,   3,   3,   3,
     41,  41,   1,   1,   1,   0,   1,   1,   1,   2,   0,   0,   1,   1,   1,   2,
      1,   1,   1,   0,   2,   0,   0,   0,   1,   1,   0,   0,  41,   0,   0,   0,
      1,   1,   3,   1,   1,   1,   2,   2,   2,   1,   0,   0,  53,  53,  53,  53,
      0,   0,   1,   1,   0,   1,   1,   1,  57,  57,  57,  57,  57,  57,  57,   0,
      0,  55,  55,  55,  58,  58,  58,  58,   0,   0,   0,  58,  58,   0,   0,   0,
     36,  36,  36,  36,  36,  36,   0,  36,  36,  36,   0,   0,   1,  36,   1,  36,
      1,  36,  36,  36,  36,  36,  41,  41,  41,  41,  25,  25,   0,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,   0,   0,  41,  41,   1,   1,  33,  33,  33,
      1,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,   1,   0,  35,  35,  35,
     35,  35,  35,  35,  35,  35,   0,   0,   0,  25,  25,  25,  25,  25,  25,   0,
     35,  35,  35,   0,  25,  25,  25,   1,  34,  34,  34,   0,  36,   0,   0,   0,
     37,  37,  37,  37,  37,   0,   0,   0,  37,  37,  37,   0,  83,  83,  83,  83,
     70,  70,  70,  70,   4,   4,   0,   4,  84,  84,  84,  84,   2,   2,   2,   0,
      2,   2,   0,   0,   0,   0,   0,   2,  59,  59,  59,  59,  65,  65,  65,  65,
     71,  71,  71,  71,  71,   0,   0,   0,   0,   0,  71,  71,  71,  71,   0,   0,
     72,  72,  72,  72,  72,  72,   1,  72,  73,  73,  73,  73,   0,   0,   0,  73,
     25,   0,   0,   0,  85,  85,  85,  85,  85,  85,   0,   1,  85,  85,   0,   0,
      0,   0,  85,  85,  23,  23,  23,   0,  77,  77,  77,  77,  77,  77,  77,   0,
     77,  77,   0,   0,  79,  79,  79,  79,  79,  79,  79,   0,   0,   0,   0,  79,
     86,  86,  86,  86,  86,  86,  86,   0,   2,   3,   0,   0,  86,  86,   0,   0,
      0,   0,   0,  25,   0,   0,   0,   5,   6,   0,   6,   0,   6,   6,   0,   6,
      6,   0,   6,   6,   7,   7,   0,   0,   0,   0,   0,   7,   7,   7,   1,   1,
      0,   0,   7,   7,   7,   0,   7,   7,   7,   0,   0,   1,   1,   1,  34,  34,
     34,  34,   1,   1,   0,   0,  25,  25,  48,  48,  48,  48,   0,  48,  48,  48,
     48,  48,  48,   0,  48,  48,   0,  48,  48,  48,   0,   0,   3,   0,   0,   0,
      1,  41,   0,   0,  74,  74,  74,  74,  74,   0,   0,   0,  75,  75,  75,  75,
     75,   0,   0,   0,  38,  38,  38,  38,  39,  39,  39,  39,  39,  39,  39,   0,
    120, 120, 120, 120, 120, 120, 120,   0,  49,  49,  49,  49,  49,  49,   0,  49,
     60,  60,  60,  60,  60,  60,   0,   0,  40,  40,  40,  40,  50,  50,  50,  50,
     51,  51,  51,  51,  51,  51,   0,   0, 106, 106, 106, 106, 103, 103, 103, 103,
      0,   0,   0, 103, 110, 110, 110, 110, 110, 110, 110,   0, 110, 110,   0,   0,
     52,  52,  52,  52,  52,  52,   0,   0,  52,   0,  52,  52,  52,  52,   0,  52,
     52,   0,   0,   0,  52,   0,   0,  52,  87,  87,  87,  87,  87,  87,   0,  87,
    118, 118, 118, 118, 117, 117, 117, 117, 117, 117, 117,   0,   0,   0,   0, 117,
     64,  64,  64,  64,   0,   0,   0,  64,  76,  76,  76,  76,  76,  76,   0,   0,
      0,   0,   0,  76,  98,  98,  98,  98,  97,  97,  97,  97,   0,   0,  97,  97,
     61,  61,  61,  61,   0,  61,  61,   0,   0,  61,  61,  61,  61,  61,  61,   0,
      0,   0,   0,  61,  61,   0,   0,   0,  88,  88,  88,  88, 116, 116, 116, 116,
    112, 112, 112, 112, 112, 112, 112,   0,   0,   0,   0, 112,  80,  80,  80,  80,
     80,  80,   0,   0,   0,  80,  80,  80,  89,  89,  89,  89,  89,  89,   0,   0,
     90,  90,  90,  90,  90,  90,  90,   0, 121, 121, 121, 121, 121, 121,   0,   0,
      0, 121, 121, 121, 121,   0,   0,   0,  91,  91,  91,  91,  91,   0,   0,   0,
     94,  94,  94,  94,  94,  94,   0,   0,   0,   0,  94,  94,   0,   0,   0,  94,
     92,  92,  92,  92,  92,  92,   0,   0, 101, 101, 101, 101, 101,   0,   0,   0,
    101, 101,   0,   0,  96,  96,  96,  96,  96,   0,  96,  96, 111, 111, 111, 111,
    111, 111, 111,   0, 100, 100, 100, 100, 100,   0,   0,   0,   0, 100,   0,   0,
    100, 100, 100,   0, 109, 109, 109, 109, 109, 109,   0, 109, 109, 109,   0,   0,
    123, 123, 123, 123, 123, 123, 123,   0, 123, 123,   0,   0,   0, 107, 107, 107,
    107, 107, 107, 107, 107,   0,   0, 107, 107,   0, 107, 107, 107, 107,   0,   0,
      0,   0,   0, 107,   0,   0, 107, 107, 107,   0,   0,   0, 124, 124, 124, 124,
    124, 124,   0,   0, 122, 122, 122, 122, 122, 122,   0,   0, 114, 114, 114, 114,
    114,   0,   0,   0, 114, 114,   0,   0, 102, 102, 102, 102, 102, 102,   0,   0,
    125, 125, 125, 125, 125, 125, 125,   0,   0,   0,   0, 125, 119, 119, 119, 119,
    119,   0,   0,   0,  63,  63,  63,  63,  63,   0,   0,   0,  63,  63,  63,   0,
     81,  81,  81,  81,  81,  81,  81,   0,  84,   0,   0,   0, 115, 115, 115, 115,
    115, 115, 115,   0, 115, 115,   0,   0,   0,   0, 115, 115, 104, 104, 104, 104,
    104, 104,   0,   0, 108, 108, 108, 108, 108, 108,   0,   0, 108, 108,   0, 108,
      0, 108, 108, 108,  99,  99,  99,  99,  99,   0,   0,   0,  99,  99,  99,   0,
      0,   0,   0,  99,  34,  33,   0,   0, 105, 105, 105, 105, 105, 105, 105,   0,
    105,   0,   0,   0, 105, 105,   0,   0,   1,   1,   1,  41,   1,  41,  41,  41,
      1,   1,  41,  41,   0,   0,   1,   0,   0,   1,   1,   0,   1,   1,   0,   1,
      1,   0,   1,   0, 113, 113, 113, 113, 113,   0,   0, 113, 113, 113, 113,   0,
      0,   7,   7,   7,   0,   7,   7,   0,   7,   0,   0,   7,   0,   7,   0,   7,
      0,   0,   7,   0,   7,   0,   7,   0,   7,   7,   0,   7,   1,   0,   0,   0,
     33,   1,   1,   0,  36,  36,  36,   0,   0,   1,   0,   0,
};

/* Script: 10548 bytes. */

RE_UINT32 re_get_script(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_script_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_script_stage_2[pos + f] << 3;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_script_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_script_stage_4[pos + f] << 2;
    value = re_script_stage_5[pos + code];

    return value;
}

/* Word_Break. */

static RE_UINT8 re_word_break_stage_1[] = {
     0,  1,  2,  3,  4,  4,  4,  4,  4,  4,  5,  6,  6,  7,  4,  8,
     9, 10, 11, 12,  4,  4, 13,  4,  4,  4,  4, 14,  4, 15, 16, 17,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
    18,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
};

static RE_UINT8 re_word_break_stage_2[] = {
      0,   1,   2,   2,   2,   3,   4,   5,   2,   6,   7,   8,   9,  10,  11,  12,
     13,  14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,
     29,  30,   2,   2,  31,  32,  33,  34,  35,   2,   2,   2,  36,  37,  38,  39,
     40,  41,  42,  43,  44,  45,  46,  47,  48,  49,   2,  50,   2,   2,  51,  52,
     53,  54,  55,  56,  57,  57,  57,  57,  57,  58,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  59,  60,  61,  62,  63,  57,  57,  57,
     64,  65,  66,  67,  57,  68,  69,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
      2,   2,   2,   2,   2,   2,   2,   2,   2,  70,   2,   2,  71,  72,  73,  74,
     75,  76,  77,  78,  79,  80,  81,  82,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  83,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  84,  85,   2,   2,  86,  87,  88,  89,  90,  91,
     92,  93,  94,  95,  57,  96,  97,  98,   2,  99, 100,  57,   2,   2, 101,  57,
    102, 103, 104, 105, 106, 107, 108, 109, 110,  57,  57,  57,  57,  57,  57,  57,
    111, 112, 113, 114, 115, 116, 117,  57,  57, 118,  57, 119, 120, 121,  57,  57,
     57, 122,  57,  57,  57, 123,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
      2,   2,   2,   2,   2,   2,   2, 124, 125,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
      2,   2,   2,   2,   2,   2,   2,   2, 126,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
      2,   2,   2,   2, 127, 128, 129, 130,  57,  57,  57,  57,  57,  57, 131, 132,
    133,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57, 134, 135,  57,  57,  57,  57,  57,  57,
     57,  57, 136, 137, 138,  57,  57,  57, 139, 140, 141,   2,   2, 142, 143, 144,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
      2, 145,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57, 146, 147,  57,  57,
     57,  57, 148, 149,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
    150,  57, 151, 152,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
     57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,  57,
};

static RE_UINT8 re_word_break_stage_3[] = {
      0,   1,   0,   0,   2,   3,   4,   5,   6,   7,   7,   8,   6,   7,   7,   9,
     10,   0,   0,   0,   0,  11,  12,  13,   7,   7,  14,   7,   7,   7,  14,   7,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,   7,   7,  15,   7,  16,   0,  17,  18,   0,   0,
     19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  20,  21,
     22,  23,   7,   7,  24,   7,   7,   7,   7,   7,   7,   7,   7,   7,  25,   7,
     26,  27,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,   6,   7,   7,   7,  14,  28,   6,   7,   7,   7,
      7,  29,  30,  19,  19,  19,  19,  31,  32,   0,  33,  33,  33,  34,  35,   0,
     36,  37,  19,  38,   7,   7,   7,   7,   7,  39,  19,  19,   4,  40,  41,   7,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  42,  43,  44,  45,   4,  46,
      0,  47,  48,   7,   7,   7,  19,  19,  19,  49,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,  50,  19,  51,   0,   4,  52,   7,   7,   7,  39,  53,  54,
      7,   7,  50,  55,  56,  57,   0,   0,   7,   7,   7,  58,   0,   0,   0,   0,
      0,   0,   0,   0,   7,   7,   9,   0,   0,   0,   0,   0,  59,  19,  19,  19,
     60,   7,   7,   7,   7,   7,   7,  61,  19,  19,  62,   7,  63,   4,   6,   7,
     64,  65,  66,   7,   7,  67,  68,  69,  70,  71,  72,  73,  63,   4,  74,   0,
     75,  76,  66,   7,   7,  67,  77,  78,  79,  80,  81,  82,  83,   4,  84,   0,
     75,  25,  24,   7,   7,  67,  85,  69,  31,  86,  87,   0,  63,   4,   0,   0,
     75,  65,  66,   7,   7,  67,  85,  69,  70,  80,  88,  73,  63,   4,  28,   0,
     89,  90,  91,  92,  93,  90,   7,  94,  95,  96,  97,   0,  83,   4,   0,   0,
     98,  20,  67,   7,   7,  67,   7,  99, 100,  96, 101,  74,  63,   4,   0,   0,
     75,  20,  67,   7,   7,  67, 102,  69, 100,  96, 101, 103,  63,   4, 104,   0,
     75,  20,  67,   7,   7,   7,   7, 105, 100, 106,  72,   0,  63,   4,   0, 107,
    108,   7,  14, 107,   7,   7,  24, 109,  14, 110, 111,  19,  83,   4, 112,   0,
      0,   0,   0,   0,   0,   0, 113, 114,  72, 115,   4, 116,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 113, 117,   0, 118,   4, 116,   0,   0,   0,   0,
     87,   0,   0, 119,   4, 116, 120, 121,   7,   6,   7,   7,   7,  17,  30,  19,
    100, 122,  19,  30,  19,  19,  19, 123, 124,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 125,  19, 115,   4, 116,  88, 126, 127, 118, 128,   0,
    129,  31,   4, 130,   7,   7,   7,   7,  25, 131,   7,   7,   7,   7,   7, 132,
      7,   7,   7,   7,   7,   7,   7,   7,   7,  91,  14,  91,   7,   7,   7,   7,
      7,  91,   7,   7,   7,   7,  91,  14,  91,   7,  14,   7,   7,   7,   7,   7,
      7,   7,  91,   7,   7,   7,   7,   7,   7,   7,   7, 133,   0,   0,   0,   0,
      7,   7,   0,   0,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  17,   0,
      6,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  65,   7,   7,
      6,   7,   7,   9,   7,   7,   7,   7,   7,   7,   7,   7,   7,  90,   7,  87,
      7,  20, 134,   0,   7,   7, 134,   0,   7,   7, 135,   0,   7,  20, 136,   0,
      0,   0,   0,   0,   0,   0,  59,  19,  19,  19, 137, 138,   4, 116,   0,   0,
      0, 139,   4, 116,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   0,
      7,   7,   7,   7,   7, 140,   7,   7,   7,   7,   7,   7,   7,   7, 141,   0,
      7,   7,   7,  14,  19, 137,  19, 137,  83,   4,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  19,  19, 142, 119,   4, 116,   0,   0,   0,   0,
      7,   7, 143, 137,   0,   0,   0,   0,   0,   0, 144, 115,  19,  19,  19,  70,
      4, 116,   4, 116,   0,   0,  19, 115,   0,   0,   0,   0,   0,   0,   0,   0,
    145,   7,   7,   7,   7,   7, 146,  19, 145, 147,   4, 116,   0, 125, 137,   0,
    148,   7,   7,   7,  62, 149,   4,  52,   7,   7,   7,   7,  50,  19, 137,   0,
      7,   7,   7,   7, 146,  19,  19,   0,   4, 150,   4,  52,   7,   7,   7, 141,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 151,  19,  19, 152, 153, 119,
      7,   7,   7,   7,   7,   7,   7,   7,  19,  19,  19,  19,  19,  19, 118,  59,
      7,   7, 141, 141,   7,   7,   7,   7, 141, 141,   7, 154,   7,   7,   7, 141,
      7,   7,   7,   7,   7,   7,  20, 155, 156,  17, 157, 147,   7,  17, 156,  17,
      0, 158,   0, 159, 160, 161,   0, 162, 163,   0, 164,   0, 165, 166,  28, 167,
      0,   0,   7,  17,   0,   0,   0,   0,   0,   0,  19,  19,  19,  19, 142,   0,
    168, 107, 109, 169,  18, 170,   7, 171, 172, 173,   0,   0,   7,   7,   7,   7,
      7,  87,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 174,   7,   7,   7,   7,   7,   7,  74,   0,   0,
      7,   7,   7,   7,   7,  14,   7,   7,   7,   7,   7,  14,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  17, 175, 176,   0,
      7,   7,   7,   7,  25, 131,   7,   7,   7,   7,   7,   7,   7, 167,   0,  72,
      7,   7,  14,   0,  14,  14,  14,  14,  14,  14,  14,  14,  19,  19,  19,  19,
      0,   0,   0,   0,   0, 167,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    131,   0,   0,   0,   0, 129, 177,  93,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0, 178, 179, 179, 179, 179, 179, 179, 179, 179, 179, 179, 179, 180,
    172,   7,   7,   7,   7, 141,   6,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      7,  14,   0,   0,   7,   7,   7,   9,   0,   0,   0,   0,   0,   0, 179, 179,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 179, 179, 179, 179, 179, 181,
    179, 179, 179, 179, 179, 179, 179, 179, 179, 179, 179,   0,   0,   0,   0,   0,
      7,  17,   0,   0,   0,   0,   0,   0,   0,   0,   7,   7,   7,   7,   7, 141,
      7,  17,   7,   7,   4, 182,   0,   0,   7,   7,   7,   7,   7, 143, 151, 183,
      7,   7,   7, 184,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7, 119,   0,
      0,   0, 167,   7, 107,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      7, 185,   7,   7,   7, 141,  74,   0,   0,   0,   0,   0,   0,   0, 167,   7,
    186, 187,   7,   7,  39,   0,   0,   0,   7,   7,   7,   7,   7,   7, 147,   0,
     27,   7,   7,   7,   7,   7, 146,  19, 123,   0,   4, 116,  19,  19,  27, 188,
      4,  52,   7,   7,  50, 118,   7,   7, 143,  19, 137,   0,   7,   7,   7,  17,
     60,   7,   7,   7,   7,   7,  39,  19, 142, 167,   4, 116, 138,   0,   4, 116,
      7,   7,   7,   7,   7,  62, 115,   0, 187, 189,   4, 116,   0,   0,   0, 190,
      0,   0,   0,   0,   0,   0, 127, 191,  81,   0,   0,   0,   7,  39, 192,   0,
    193, 193, 193,   0,  14,  14,   7,   7,   7,   7,   7, 132, 194,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   7,   7,   7,   7,  39, 195,   4, 116,
      7,   7,   7,   7, 147,   0,   7,   7,  14, 196,   7,   7,   7,   7,   7, 147,
     14,   0, 196, 197,  33, 198, 199, 200, 201,  33,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,  74,   0,   0,   0, 196,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,   7, 141,   0,   0,   7,   7,   7,   7,   7,   7,
      7,   7, 107,   7,   7,   7,   7,   7,   7,   0,   0,   0,   0,   0,   7, 147,
     19,  19, 202,   0,  19, 118, 203,   0,   0, 204, 205,   0,   0,   0,  20,   7,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7, 206,
    207,   3,   0, 208,   6,   7,   7,   8,   6,   7,   7,   9, 209, 179, 179, 179,
    179, 179, 179, 210,   7,   7,   7,  14, 107, 107, 107, 211,   0,   0,   0, 212,
      7, 102,   7,   7,  14,   7,   7, 213,   7, 141,   7, 141,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   9,
      0,   0,   0,   0,   0,   0,   0,   0,   7,   7,   7,   7,   7,   7,  17,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 138,
      7,   7,   7,  17,   7,   7,   7,   7,   7,   7,  87,   0, 142,   0,   0,   0,
      7,   7,   7,   7,   0,   0,   7,   7,   7,   9,   7,   7,   7,   7,  50, 114,
      7,   7,   7, 141,   7,   7,   7,   7, 147,   7, 169,   0,   0,   0,   0,   0,
      7,   7,   7, 141,   4, 116,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   0,   7,   7,   7,   7,   7,   7, 147,   0,   0,   0,
      7,   7,   7,   7,   7,   7,  14,   0,   7,   7, 141,   0,   7,   0,   0,   0,
    141,  67,   7,   7,   7,   7,  25, 214,   7,   7, 141,   0,   7,   7,  14,   0,
      7,   7,   7,  14,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7, 141,   0,   7,   7,   7,  74,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7, 174,   0,   0,   0,   0,   0,   0,   0,   0,
    215,  59, 102,   6,   7,   7, 147,  79,   0,   0,   0,   0,   7,   7,   7,  17,
      7,   7,   7,  17,   0,   0,   0,   0,   7,   6,   7,   7, 216,   0,   0,   0,
      7,   7,   7,   7,   7,   7, 141,   0,   7,   7, 141,   0,   7,   7,   9,   0,
      7,   7,  74,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,   7,  87,   0,   0,   0,   0,   0,   0,
    148,   7,   7,   7,   7,   7,   7,  19, 115,   0,   0,   0,  83,   4,   0,  72,
    148,   7,   7,   7,   7,   7,  19, 217,   0,   0,   7,   7,   7,  87,   4, 116,
    148,   7,   7,   7, 143,  19, 218,   4,   0,   0,   7,   7,   7,   7, 219,   0,
    148,   7,   7,   7,   7,   7,  39,  19, 220,   0,   4, 221,   0,   0,   0,   0,
      7,   7,  24,   7,   7, 146,  19,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   7,   7,   7,   7,   7, 143,  19, 114,   4, 116,
     75,  65,  66,   7,   7,  67,  85,  69,  70,  80,  72, 172, 222, 123, 123,   0,
      7,   7,   7,   7,   7,   7,  19,  19, 223,   0,   4, 116,   0,   0,   0,   0,
      7,   7,   7,   7,   7, 143, 118,  19, 142,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,  19,  19, 224,   0,   4, 116,   0,   0,   0,   0,
      7,   7,   7,   7,   7,  39,  19,   0,   4, 116,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   7,   7,   7,   7,   7,   7,   7,   7,   4, 116,   0, 167,
      0,   0,   0,   0,   0,   0,   0,   0,   7,   7,   7,   7,   7,   7,   7,  87,
      7,   7,   7,  87,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  14,   0,   0,
      7,   7,   7,   7,   7,  14,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,  87,   7,   7,   7,  14,   4, 116,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   7,   7,   7, 141, 123,   0,
      7,   7,   7,   7,   7,   7, 115,   0, 147,   0,   4, 116, 196,   7,   7, 172,
      7,   7,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,  17,   0,  62,  19,  19,  19,  19, 115,
      0,  72, 148,   7,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    225,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   9,   7,  17,
      7,  87,   7, 226, 227,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 144, 228, 229, 230,
    231, 137,   0,   0,   0, 232,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0, 233,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  20,   7,   7,   7,   7,   7,
      7,   7,   7,  20, 234, 235,   7, 236, 102,   7,   7,   7,   7,   7,   7,   7,
     25, 237,  20,  20,   7,   7,   7, 238, 155, 107,  67,   7,   7,   7,   7,   7,
      7,   7,   7,   7, 141,   7,   7,   7,  67,   7,   7, 132,   7,   7,   7, 132,
      7,   7,  20,   7,   7,   7,  20,   7,   7,  14,   7,   7,   7,  14,   7,   7,
      7,  67,   7,   7,   7,  67,   7,   7, 132, 239,   4,   4,   4,   4,   4,   4,
      7,   7,   7,   7,   7,   7,   7,   7,  17,   0, 115,   0,   0,   0,   0,   0,
    102,   7,   7,   7, 240,   6, 132, 241, 168, 242, 240, 154, 240, 132, 132,  82,
      7,  24,   7, 147, 243,  24,   7, 147,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   7,   7,   7,  74,   7,   7,   7,  74,   7,   7,
      7,  74,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 244, 245, 245, 245,
    246,   0,   0,   0, 166, 166, 166, 166, 166, 166, 166, 166, 166, 166, 166, 166,
     19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,
     19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,   0,   0,
};

static RE_UINT8 re_word_break_stage_4[] = {
      0,   0,   1,   2,   3,   4,   0,   5,   6,   6,   7,   0,   8,   9,   9,   9,
     10,  11,  10,   0,   0,  12,  13,  14,   0,  15,  13,   0,   9,  10,  16,  17,
     16,  18,   9,  19,   0,  20,  21,  21,   9,  22,  17,  23,   0,  24,  10,  22,
     25,   9,   9,  25,  26,  21,  27,   9,  28,   0,  29,   0,  30,  21,  21,  31,
     32,  31,  33,  33,  34,   0,  35,  36,  37,  38,   0,  39,  40,  41,  42,  21,
     43,  44,  45,   9,   9,  46,  21,  47,  21,  48,  49,  27,  50,  51,   0,  52,
     53,   9,  40,   8,   9,  54,  55,   0,  50,   9,  21,  16,  56,   0,  57,  21,
     21,  58,  58,  59,  58,   0,   0,  21,  21,   9,  54,  60,  58,  21,  54,  61,
     58,   8,   9,  51,  51,   9,  22,   9,  20,  17,  16,  60,  21,  62,  62,  63,
      0,  64,   0,  25,  16,   0,  30,   8,  10,  65,  22,  66,  16,  49,  40,  64,
     62,  59,  67,   0,   8,  20,   0,  61,  27,  68,  22,   8,  31,  59,  19,   0,
      0,  69,  70,   8,  10,  17,  22,  16,  66,  22,  65,  19,  16,  69,  40,  69,
     49,  59,  19,  64,  21,   8,  16,  46,  21,  49,   0,  32,   9,   8,   0,  13,
     66,   0,  10,  46,  49,  63,  17,   9,  69,   8,   9,  28,  71,  64,  21,  72,
     69,   0,  67,  21,  40,   0,  21,  40,  73,   0,  31,  74,  21,  59,  59,   0,
      0,  75,  67,  69,   9,  58,  21,  74,   0,  71,  64,  21,  59,  69,  49,  62,
     30,  74,  69,  21,  76,  59,   0,  28,  10,   9,  10,  30,  54,  74,  54,   0,
     77,   0,  21,   0,   0,  67,  64,  78,  79,   0,   9,  16,  74,   0,   9,  42,
      0,  30,  21,  45,   9,  21,   9,   0,  80,   9,  21,  27,  73,   8,  40,  21,
     45,  53,  54,  81,  82,  82,   9,  20,  17,  22,   9,  17,   0,  83,  84,   0,
      0,  85,  86,  87,   0,  11,  88,  89,   0,  88,  37,  90,  37,  37,   0,  65,
     13,  65,   8,  16,  22,  25,  16,   9,   0,   8,  16,  13,   0,  17,  65,  42,
     27,   0,  91,  92,  93,  94,  95,  95,  96,  95,  95,  96,  50,   0,  21,  97,
      9,  26,  51,  10,  98,  98,  42,   9,  65,   0,   9,  59,  64,  59,  74,  69,
     17,  99,   8,  10,   0,  16,  40,  59,  65,   9,   0, 100, 101,  33,  33,  34,
     33, 102, 103, 101, 104,  89,  11,  88,   0, 105,   5, 106,   9, 107,   0, 108,
    109,   0,   0, 110,  95, 111,  17,  19, 112,   0,  10,  25,  19,  51,  58,  32,
      9,  99,  40,  14,  21, 113,  42,  13,  45,  19, 114,   0,  54,  69,  21,  25,
     74,  19,  94,   0,  16,  32,  37,   0,  59,  30, 115,  37, 116,  21,  40,  30,
     69,  59,  69,  74,  13,  66,   8,  22,  25,   8,  10,   8,  25,  10,   9,  61,
     66,  51,  82,   0,  82,   8,   8,   8,   0, 117, 118, 118,  14,   0,
};

static RE_UINT8 re_word_break_stage_5[] = {
     0,  0,  0,  0,  0,  0,  5,  6,  6,  4,  0,  0,  0,  0,  1,  0,
     0,  0,  0,  2, 13,  0, 14,  0, 15, 15, 15, 15, 15, 15, 12, 13,
     0, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,  0,  0,  0,  0, 16,
     0,  6,  0,  0,  0,  0, 11,  0,  0,  9,  0,  0,  0, 11,  0, 12,
    11, 11,  0,  0,  0,  0, 11, 11,  0,  0,  0, 12, 11,  0,  0,  0,
    11,  0, 11,  0,  7,  7,  7,  7, 11,  0, 11, 11, 11, 11, 13, 11,
     0,  0, 11, 12, 11, 11,  0, 11, 11, 11,  0,  7,  7,  7, 11, 11,
     0, 11,  0,  0,  0, 13,  0,  0,  0,  7,  7,  7,  7,  7,  0,  7,
     0,  7,  7,  0,  3,  3,  3,  3,  3,  3,  3,  0,  3,  3,  3, 11,
    12,  0,  0,  0,  9,  9,  9,  9,  9,  9,  0,  0, 13, 13,  0,  0,
     7,  7,  7,  0,  9,  0,  0,  0, 11, 11, 11,  7, 15, 15,  0, 15,
    13,  0, 11, 11,  7, 11, 11, 11,  0, 11,  7,  7,  7,  9,  0,  7,
     7, 11, 11,  7,  7,  0,  7,  7, 15, 15, 11, 11, 11,  0,  0, 11,
     0,  0,  0,  9, 11,  7, 11, 11, 11, 11,  7,  7,  7, 11,  0,  0,
    13,  0, 11,  0,  7,  7, 11,  7, 11,  7,  7,  7,  7,  7,  0,  0,
     7, 11,  7,  7,  0,  0, 15, 15,  7,  0,  0,  7,  7,  7, 11,  0,
     0,  0,  0,  7,  0,  0,  0, 11,  0, 11, 11,  0,  0,  7,  0,  0,
    11,  7,  0,  0,  0,  0,  7,  7,  0,  0,  7, 11,  0,  0,  7,  0,
     7,  0,  7,  0, 15, 15,  0,  0,  7,  0,  0,  0,  0,  7,  0,  7,
    15, 15,  7,  7, 11,  0,  7,  7,  7,  7,  9,  0, 11,  7, 11,  0,
     7,  7,  7, 11,  7, 11, 11,  0,  0, 11,  0, 11,  7,  7,  9,  9,
    14, 14,  0,  0, 14,  0,  0, 12,  6,  6,  9,  9,  9,  9,  9,  0,
    16,  0,  0,  0, 13,  0,  0,  0,  9,  0,  9,  9,  0, 10, 10, 10,
    10, 10,  0,  0,  0,  7,  7, 10, 10,  0,  0,  0, 10, 10, 10, 10,
    10, 10, 10,  0,  7,  7,  0, 11, 11, 11,  7, 11, 11,  7,  7,  0,
     0,  3,  7,  3,  3,  0,  3,  3,  3,  0,  3,  0,  3,  3,  0,  3,
    13,  0,  0, 12,  0, 16, 16, 16, 13, 12,  0,  0, 11,  0,  0,  9,
     0,  0,  0, 14,  0,  0, 12, 13,  0,  0, 10, 10, 10, 10,  7,  7,
     0,  9,  9,  9,  7,  0, 15, 15, 15, 15, 11,  0,  7,  7,  7,  9,
     9,  9,  9,  7,  0,  0,  8,  8,  8,  8,  8,  8,
};

/* Word_Break: 4298 bytes. */

RE_UINT32 re_get_word_break(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_word_break_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_word_break_stage_2[pos + f] << 4;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_word_break_stage_3[pos + f] << 1;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_word_break_stage_4[pos + f] << 2;
    value = re_word_break_stage_5[pos + code];

    return value;
}

/* Grapheme_Cluster_Break. */

static RE_UINT8 re_grapheme_cluster_break_stage_1[] = {
     0,  1,  2,  2,  2,  3,  4,  5,  6,  2,  2,  7,  2,  8,  9, 10,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
    11,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,
};

static RE_UINT8 re_grapheme_cluster_break_stage_2[] = {
     0,  1,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
    15, 16,  1, 17,  1,  1,  1, 18, 19, 20, 21, 22, 23, 24,  1,  1,
    25,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 26, 27,  1,  1,
    28,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 29,  1, 30, 31, 32, 33, 34, 35, 36, 37,
    38, 39, 40, 34, 35, 36, 37, 38, 39, 40, 34, 35, 36, 37, 38, 39,
    40, 34, 35, 36, 37, 38, 39, 40, 34, 35, 36, 37, 38, 39, 40, 34,
    35, 36, 37, 38, 39, 40, 34, 41, 42, 42, 42, 42, 42, 42, 42, 42,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 43,  1,  1, 44, 45,
     1, 46, 47, 48,  1,  1,  1,  1,  1,  1, 49,  1,  1,  1,  1,  1,
    50, 51, 52, 53, 54, 55, 56,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 57, 58,  1,  1,  1, 59,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 60,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1, 61, 62,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 63,  1,  1,  1,  1,  1,  1,  1,
     1, 64,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    42, 65, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42, 42,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_grapheme_cluster_break_stage_3[] = {
      0,   1,   2,   2,   2,   2,   2,   3,   1,   1,   4,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      5,   5,   5,   5,   5,   5,   5,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   6,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   7,   5,   8,   9,   2,   2,   2,
     10,  11,   2,   2,  12,   5,   2,  13,   2,   2,   2,   2,   2,  14,  15,   2,
      3,  16,   2,   5,  17,   2,   2,   2,   2,   2,  18,  13,   2,   2,  12,  19,
      2,  20,  21,   2,   2,  22,   2,   2,   2,   2,   2,   2,   2,   2,  23,   5,
     24,   2,   2,  25,  26,  27,  28,   2,  29,   2,   2,  30,  31,  32,  28,   2,
     33,   2,   2,  34,  35,  16,   2,  36,  33,   2,   2,  34,  37,   2,  28,   2,
     29,   2,   2,  38,  31,  39,  28,   2,  40,   2,   2,  41,  42,  32,   2,   2,
     43,   2,   2,  44,  45,  46,  28,   2,  29,   2,   2,  47,  48,  46,  28,   2,
     29,   2,   2,  41,  49,  32,  28,   2,  50,   2,   2,   2,  51,  52,   2,  50,
      2,   2,   2,  53,  54,   2,   2,   2,   2,   2,   2,  55,  56,   2,   2,   2,
      2,  57,   2,  58,   2,   2,   2,  59,  60,  61,   5,  62,  63,   2,   2,   2,
      2,   2,  64,  65,   2,  66,  13,  67,  68,  69,   2,   2,   2,   2,   2,   2,
     70,  70,  70,  70,  70,  70,  71,  71,  71,  71,  72,  73,  73,  73,  73,  73,
      2,   2,   2,   2,   2,  64,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,  74,   2,  74,   2,  28,   2,  28,   2,   2,   2,  75,  76,  77,   2,   2,
     78,   2,   2,   2,   2,   2,   2,   2,   2,   2,  79,   2,   2,   2,   2,   2,
      2,   2,  80,  81,   2,   2,   2,   2,   2,   2,   2,  82,   2,   2,   2,   2,
      2,  83,   2,   2,   2,  84,  85,  86,   2,   2,   2,  87,   2,   2,   2,   2,
     88,   2,   2,  89,  90,   2,  12,  19,  91,   2,  92,   2,   2,   2,  93,  94,
      2,   2,  95,  96,   2,   2,   2,   2,   2,   2,   2,   2,   2,  97,  98,  99,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   5,   5,   5, 100,
    101,   2, 102,   2,   2,   2,   1,   2,   2,   2,   2,   2,   2,   5,   5,  13,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 103, 104,
      2,   2,   2,   2,   2,   2,   2, 103,   2,   2,   2,   2,   2,   2,   5,   5,
      2,   2, 105,   2,   2,   2,   2,   2,   2, 106,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2, 103, 107,   2, 103,   2,   2,   2,   2,   2, 104,
    108,   2, 109,   2,   2,   2,   2,   2, 110,   2,   2, 111, 112,   2,   5, 104,
      2,   2, 113,   2, 114,  94,  70, 115,  24,   2,   2, 116, 117,   2, 118,   2,
      2,   2, 119, 120, 121,   2,   2, 122,   2,   2,   2, 123,  16,   2, 124, 125,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 126,   2,
    127, 128, 129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 131, 129, 127, 128,
    129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 131, 129, 127, 128, 129, 130,
    129, 131, 129, 127, 128, 129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 131,
    129, 127, 128, 129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 131, 129, 127,
    128, 129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 131, 129, 127, 128, 129,
    130, 129, 131, 129, 127, 128, 129, 130, 129, 131, 129, 127, 128, 129, 130, 129,
    131, 129, 127, 128, 129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 131, 129,
    129, 130, 129, 131, 129, 127, 128, 129, 130, 129, 132,  71, 133,  73,  73, 134,
      1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      2, 135,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      5,   2, 136,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   3,
      2,   2,   2,   2,   2,   2,   2,   2,   2,  44,   2,   2,   2,   2,   2, 137,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  69,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  13,   2,
      2,   2,   2,   2,   2,   2,   2, 138,   2,   2,   2,   2,   2,   2,   2,   2,
    139,   2,   2, 140,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  46,   2,
    141,   2,   2, 142, 143,   2,   2, 103,  91,   2,   2, 144,   2,   2,   2,   2,
    145,   2, 146, 147,   2,   2,   2, 148,  91,   2,   2, 149, 117,   2,   2,   2,
      2,   2, 150, 151,   2,   2,   2,   2,   2,   2,   2,   2,   2, 103, 152,   2,
     29,   2,   2,  30, 153,  32, 154, 147,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 155, 156,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 103, 157,  13,   2,   2,   2,
      2,   2,   2, 158,  13,   2,   2,   2,   2,   2, 159, 160,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 147,
      2,   2,   2, 143,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2, 161, 162, 163, 103, 145,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2, 164, 165,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2, 166, 167, 168,   2, 169,   2,   2,   2,   2,   2,
      2,   2,   2,   2,  74,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 143,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 170, 171,
      5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   1,
};

static RE_UINT8 re_grapheme_cluster_break_stage_4[] = {
     0,  0,  1,  2,  0,  0,  0,  0,  3,  3,  3,  3,  3,  3,  3,  4,
     3,  3,  3,  5,  6,  6,  6,  6,  7,  6,  8,  3,  9,  6,  6,  6,
     6,  6,  6, 10, 11, 10,  3,  3,  0, 12,  3,  3,  6,  6, 13, 14,
     3,  3,  7,  6, 15,  3,  3,  3,  3, 16,  6, 17,  6, 18, 19,  8,
    20,  3,  3,  3,  6,  6, 13,  3,  3, 16,  6,  6,  6,  3,  3,  3,
     3, 16, 10,  6,  6,  9,  9,  8,  3,  3,  9,  3,  3,  6,  6,  6,
    21,  3,  3,  3,  3,  3, 22, 23, 24,  6, 25, 26,  9,  6,  3,  3,
    16,  3,  3,  3, 27,  3,  3,  3,  3,  3,  3, 28, 24, 29, 30, 31,
     3,  7,  3,  3, 32,  3,  3,  3,  3,  3,  3, 23, 33,  7, 18,  8,
     8, 20,  3,  3, 24, 10, 34, 31,  3,  3,  3, 19,  3, 16,  3,  3,
    35,  3,  3,  3,  3,  3,  3, 22, 36, 37, 38, 31, 25,  3,  3,  3,
     3,  3,  3, 16, 25, 39, 19,  8,  3, 11,  3,  3,  3,  3,  3, 40,
    41, 42, 38,  8, 24, 23, 38, 31, 37,  3,  3,  3,  3,  3, 35,  7,
    43, 44, 45, 46, 47,  6, 13,  3,  3,  7,  6, 13, 47,  6, 10, 15,
     3,  3,  6,  8,  3,  3,  8,  3,  3, 48, 20, 37,  9,  6,  6, 21,
     6, 19,  3,  9,  6,  6,  9,  6,  6,  6,  6, 15,  3, 35,  3,  3,
     3,  3,  3,  9, 49,  6, 32, 33,  3, 37,  8, 16,  9, 15,  3,  3,
    35, 33,  3, 20,  3,  3,  3, 20, 50, 50, 50, 50, 51, 51, 51, 51,
    51, 51, 52, 52, 52, 52, 52, 52, 16, 15,  3,  3,  3, 53,  6, 54,
    45, 41, 24,  6,  6,  3,  3, 20,  3,  3,  7, 55,  3,  3, 20,  3,
    21, 46, 25,  3, 41, 45, 24,  3,  3, 56, 57,  3,  3,  7, 58,  3,
     3, 59,  6, 13, 44,  9,  6, 25, 46,  6,  6, 18,  6,  6,  6, 13,
     6, 60,  3,  3,  3, 49, 21, 25, 41, 60,  3,  3, 61,  3,  3,  3,
    62, 54, 53,  8,  3, 22, 54, 63, 54,  3,  3,  3,  3, 45, 45,  6,
     6, 43,  3,  3, 13,  6,  6,  6, 49,  6, 15, 20, 37, 15,  8,  3,
     6,  8,  3,  6,  3,  3,  4, 64,  3,  3,  0, 65,  3,  3,  3,  7,
     8,  3,  3,  3,  3,  3, 16,  6,  3,  3, 11,  3, 13,  6,  6,  8,
    35, 35,  7,  3, 66, 67,  3,  3, 68,  3,  3,  3,  3, 45, 45, 45,
    45, 15,  3,  3,  3, 16,  6,  8,  3,  7,  6,  6, 50, 50, 50, 69,
     7, 43, 54, 25, 60,  3,  3,  3,  3, 20,  3,  3,  3,  3,  9, 21,
    67, 33,  3,  3,  7,  3,  3, 70,  3,  3,  3, 15, 19, 18, 15, 16,
     3,  3, 66, 54,  3, 71,  3,  3, 66, 26, 36, 31, 72, 73, 73, 73,
    73, 73, 73, 72, 73, 73, 73, 73, 73, 73, 72, 73, 73, 72, 73, 73,
    73,  3,  3,  3, 51, 74, 75, 52, 52, 52, 52,  3,  3,  3,  3, 35,
     6,  6,  6,  8,  0,  0,  0,  3,  3, 16, 13,  3,  9, 11,  3,  6,
     3,  3, 13,  7, 76,  3,  3,  3,  3,  3,  6,  6,  6, 13,  3,  3,
    46, 21, 33,  5, 13,  3,  3,  3,  3,  7,  6, 24,  6, 15,  3,  3,
     7,  3,  3,  3, 66, 43,  6, 21,  3,  3,  3, 46, 54, 49,  3,  3,
    46,  6, 13,  3, 25, 30, 30, 68, 37, 16,  6, 15, 58,  6, 77, 63,
    49,  3,  3,  3, 43,  8, 45, 53, 46,  6, 21, 63,  3,  3,  7, 26,
     6, 53,  3,  3, 56, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 78,
     3,  3,  3, 11,  0,  3,  3,  3,  3, 79,  8, 62, 80,  0, 81,  6,
    13,  9,  6,  3,  3,  3, 16,  8,  3, 82, 83, 83, 83, 83, 83, 83,
};

static RE_UINT8 re_grapheme_cluster_break_stage_5[] = {
     3,  3,  3,  3,  3,  3,  2,  3,  3,  1,  3,  3,  0,  0,  0,  0,
     0,  0,  0,  3,  0,  3,  0,  0,  4,  4,  4,  4,  0,  0,  0,  4,
     4,  4,  0,  0,  0,  4,  4,  4,  4,  4,  0,  4,  0,  4,  4,  0,
     3,  3,  0,  0,  4,  4,  4,  0,  3,  0,  0,  0,  4,  0,  0,  0,
     0,  0,  4,  4,  4,  3,  0,  4,  4,  0,  0,  4,  4,  0,  4,  4,
     0,  4,  0,  0,  4,  4,  4,  6,  0,  0,  4,  6,  4,  0,  6,  6,
     6,  4,  4,  4,  4,  6,  6,  6,  6,  4,  6,  6,  0,  4,  6,  6,
     4,  0,  4,  6,  4,  0,  0,  6,  6,  0,  0,  6,  6,  4,  0,  0,
     0,  4,  4,  6,  6,  4,  4,  0,  4,  6,  0,  6,  0,  0,  4,  0,
     4,  6,  6,  0,  0,  0,  6,  6,  6,  0,  6,  6,  6,  0,  4,  4,
     4,  0,  6,  4,  6,  6,  4,  6,  6,  0,  4,  6,  6,  6,  4,  4,
     4,  0,  4,  0,  6,  6,  6,  6,  6,  6,  6,  4,  0,  4,  0,  6,
     0,  4,  0,  4,  4,  6,  4,  4,  7,  7,  7,  7,  8,  8,  8,  8,
     9,  9,  9,  9,  4,  4,  6,  4,  4,  4,  6,  6,  4,  4,  3,  0,
     0,  6,  6,  6,  0,  0,  6,  0,  4,  6,  6,  4,  0,  6,  4,  6,
     6,  0,  0,  0,  4,  4,  6,  0,  0,  6,  4,  4,  6,  4,  6,  4,
     4,  4,  3,  3,  3,  3,  3,  0,  0,  0,  0,  6,  6,  4,  4,  6,
     6,  6,  0,  0,  7,  0,  0,  0,  4,  6,  0,  0,  0,  6,  4,  0,
    10, 11, 11, 11, 11, 11, 11, 11,  8,  8,  8,  0,  0,  0,  0,  9,
     6,  4,  6,  0,  4,  6,  4,  6,  6,  6,  6,  0,  0,  4,  6,  4,
     4,  4,  4,  3,  3,  3,  3,  4,  0,  0,  5,  5,  5,  5,  5,  5,
};

/* Grapheme_Cluster_Break: 2600 bytes. */

RE_UINT32 re_get_grapheme_cluster_break(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_grapheme_cluster_break_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_grapheme_cluster_break_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_grapheme_cluster_break_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_grapheme_cluster_break_stage_4[pos + f] << 2;
    value = re_grapheme_cluster_break_stage_5[pos + code];

    return value;
}

/* Sentence_Break. */

static RE_UINT8 re_sentence_break_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  6,  7,  5,  5,  8,  9, 10,
    11, 12, 13, 14,  9,  9, 15,  9,  9,  9,  9, 16,  9, 17, 18, 19,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 20, 21,  9,  9,  9, 22,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
    23,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
};

static RE_UINT8 re_sentence_break_stage_2[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,  17,  18,  19,  20,  17,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,
     31,  32,  33,  34,  35,  33,  33,  36,  33,  37,  33,  33,  38,  39,  40,  33,
     41,  42,  33,  33,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  43,  17,  17,
     17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  44,
     17,  17,  17,  17,  45,  17,  46,  47,  48,  49,  50,  51,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17,  52,  33,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  33,  17,  53,  54,  17,  55,  56,  57,
     58,  59,  60,  61,  62,  63,  17,  64,  65,  66,  67,  68,  69,  33,  33,  33,
     70,  71,  72,  73,  74,  75,  76,  33,  77,  33,  78,  33,  33,  33,  33,  33,
     17,  17,  17,  79,  80,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     17,  17,  17,  17,  81,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  17,  17,  82,  83,  33,  33,  33,  84,
     85,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  86,  33,  33,  33,
     33,  87,  88,  33,  89,  90,  91,  92,  33,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  93,  33,  33,  33,  33,  33,  94,  33,
     33,  95,  33,  33,  33,  33,  96,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     17,  17,  17,  17,  17,  17,  97,  17,  17,  17,  17,  17,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17,  98,  99,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  17,  17,  99,  33,  33,  33,  33,  33,
    100, 101,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
};

static RE_UINT16 re_sentence_break_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
      8,  16,  17,  18,  19,  20,  21,  22,  23,  23,  23,  24,  25,  26,  27,  28,
     29,  30,  18,   8,  31,   8,  32,   8,   8,  33,  34,  35,  36,  37,  38,  39,
     40,  41,  42,  43,  41,  41,  44,  45,  46,  47,  48,  41,  41,  49,  50,  51,
     52,  53,  54,  55,  55,  56,  55,  57,  58,  59,  60,  61,  62,  63,  64,  65,
     66,  67,  68,  69,  70,  71,  72,  73,  74,  71,  75,  76,  77,  78,  79,  80,
     81,  82,  83,  73,  84,  85,  86,  87,  84,  88,  89,  90,  91,  92,  93,  94,
     95,  96,  97,  55,  98,  99, 100,  55, 101, 102, 103, 104, 105, 106, 107,  55,
     41, 108, 109, 110, 111,  29, 112, 113,  41,  41,  41,  41,  41,  41,  41,  41,
     41,  41, 114,  41, 115, 116, 117,  41, 118,  41, 119, 120, 121,  41,  41, 122,
     95,  41,  41,  41,  41,  41,  41,  41,  41,  41,  41, 123, 124,  41,  41, 125,
    126, 127, 128, 129,  41, 130, 131, 132, 133,  41,  41, 134,  41, 135,  41, 136,
    137, 138, 139, 140,  41, 141, 142,  55, 143,  41, 144, 145, 146, 147,  55,  55,
    148, 130, 149, 150, 151, 152,  41, 153,  41, 154, 155, 156,  55,  55, 157, 158,
     18,  18,  18,  18,  18,  18,  23, 159,   8,   8,   8,   8, 160,   8,   8,   8,
    161, 162, 163, 164, 162, 165, 166, 167, 168, 169, 170, 171, 172,  55, 173, 174,
    175, 176, 177,  30, 178,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,
    179, 180,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55, 181,  30, 182,
     55,  55, 183, 184,  55,  55, 185, 186,  55,  55,  55,  55, 187,  55, 188, 189,
     29, 190, 191, 192,   8,   8,   8, 193,  18, 194,  41, 195, 196, 197, 197,  23,
    198, 199, 200,  55,  55,  55,  55,  55, 201, 202,  95,  41, 203,  95,  41, 113,
    204, 205,  41,  41, 206, 207,  55, 208,  41,  41,  41,  41,  41, 136,  55,  55,
     41,  41,  41,  41,  41,  41, 209,  55,  41,  41,  41,  41, 209,  55, 208, 210,
    211, 212,   8, 213, 214,  41,  41, 215, 216, 217,   8, 218, 219, 220,  55, 221,
    222, 223,  41, 224, 225, 130, 226, 227,  50, 228, 229, 230,  58, 231, 232, 233,
     41, 234, 235, 236,  41, 237, 238, 239, 240, 241, 242, 243,  55,  55,  41, 244,
     41,  41,  41,  41,  41, 245, 246, 247,  41,  41,  41, 248,  41,  41, 249,  55,
    250, 251, 252,  41,  41, 253, 254,  41,  41, 255, 208,  41, 256,  41, 257, 258,
    259, 260, 261, 262,  41,  41,  41, 263, 264,   2, 265, 266, 267, 137, 268, 269,
    270, 271, 272,  55,  41,  41,  41, 207,  55,  55,  41, 122,  55,  55,  55, 273,
     55,  55,  55,  55, 230,  41, 274, 275,  41, 208, 276, 277, 278,  41, 279,  55,
     29, 280, 281,  41, 278, 132,  55,  55,  41, 282,  41, 283,  55,  55,  55,  55,
     41, 196, 136, 257,  55,  55,  55,  55, 284, 285, 136, 196, 137,  55,  55,  55,
    136, 249,  55,  55,  41, 286,  55,  55, 287, 288, 289, 230, 230,  55, 103, 290,
     41, 136, 136,  56, 253,  55,  55,  55,  41,  41, 291,  55,  55,  55,  55,  55,
    151, 292, 293, 294, 151, 295, 296, 297, 151, 298, 299, 300, 151, 231, 301,  55,
    302, 303,  55,  55,  55, 208, 304, 305,  74,  71, 306, 307,  55,  55,  55,  55,
     55,  55,  55,  55,  41,  47, 308,  55,  55,  55,  55,  55,  41, 309, 310,  55,
     41,  47, 311,  55,  41, 312, 132,  55,  55,  55,  55,  55,  55,  29,  18, 313,
     55,  55,  55,  55,  55,  55,  41, 314,  41,  41,  41,  41, 314,  55,  55,  55,
     41,  41,  41, 206,  55,  55,  55,  55,  41, 206,  55,  55,  55,  55,  55,  55,
     41, 314, 137, 315,  55,  55, 208, 316,  41, 317, 318, 319, 121,  55,  55,  55,
     41,  41, 320, 321, 322,  55,  55,  55, 323,  55,  55,  55,  55,  55,  55,  55,
     41,  41,  41, 324, 325, 326,  55,  55,  55,  55,  55, 327, 328, 329,  55,  55,
     55,  55, 330,  55,  55,  55,  55,  55, 331, 332, 333, 334, 335, 336, 337, 338,
    339, 340, 341, 342, 343, 331, 332, 344, 334, 345, 346, 347, 338, 348, 349, 350,
    351, 352, 353, 190, 354, 355, 356, 357,  41,  41,  41,  41,  41,  41, 358,  55,
    359, 360, 361, 362, 363, 364,  55,  55,  55, 365, 366, 366, 367,  55,  55,  55,
     55,  55,  55, 368,  55,  55,  55,  55,  41,  41,  41,  41,  41,  41, 196,  55,
     41, 122,  41,  41,  41,  41,  41,  41, 278,  55,  55,  55,  55,  55,  55,  55,
    369, 370, 370, 370,  55,  55,  55,  55,  23,  23,  23,  23,  23,  23,  23, 371,
};

static RE_UINT8 re_sentence_break_stage_4[] = {
      0,   0,   1,   2,   0,   0,   0,   0,   3,   4,   5,   6,   7,   7,   8,   9,
     10,  11,  11,  11,  11,  11,  12,  13,  14,  15,  15,  15,  15,  15,  16,  13,
      0,  17,   0,   0,   0,   0,   0,   0,  18,   0,  19,  20,   0,  21,  19,   0,
     11,  11,  11,  11,  11,  22,  11,  23,  15,  15,  15,  15,  15,  24,  15,  15,
     25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  26,  26,
     26,  26,  27,  25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  25,  28,  29,
     30,  31,  32,  33,  28,  31,  34,  28,  25,  31,  29,  31,  32,  26,  35,  34,
     36,  28,  31,  26,  26,  26,  26,  27,  25,  25,  25,  25,  30,  31,  25,  25,
     25,  25,  25,  25,  25,  15,  33,  30,  26,  23,  25,  25,  15,  15,  15,  15,
     15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  37,  15,  15,
     15,  15,  15,  15,  15,  15,  38,  36,  39,  40,  36,  36,  41,   0,   0,   0,
     15,  42,   0,  43,   0,   0,   0,   0,  44,  44,  44,  44,  44,  44,  44,  44,
     44,  44,  44,  44,  25,  45,  46,  47,   0,  48,  22,  49,  32,  11,  11,  11,
     50,  11,  11,  15,  15,  15,  15,  15,  15,  15,  15,  51,  33,  34,  25,  25,
     25,  25,  25,  25,  15,  52,  30,  32,  11,  11,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  15,  15,  15,  15,  53,  44,  54,  25,  25,  25,  25,  25,
     28,  26,  26,  29,  25,  25,  25,  25,  25,  25,  25,  25,  10,  11,  11,  11,
     11,  11,  11,  11,  11,  22,  55,  56,  14,  15,  15,  15,  15,  15,  15,  15,
     15,  15,  57,   0,  58,  44,  44,  44,  44,  44,  44,  44,  44,  44,  44,  59,
     60,  59,   0,   0,  36,  36,  36,  36,  36,  36,  61,   0,  36,   0,   0,   0,
     62,  63,   0,  64,  44,  44,  65,  66,  36,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  67,  44,  44,  44,  44,  44,   7,   7,  68,  69,  70,  36,  36,  36,
     36,  36,  36,  36,  36,  71,  44,  72,  44,  73,  74,  75,   7,   7,  76,  77,
     78,   0,   0,  79,  80,  36,  36,  36,  36,  36,  36,  36,  44,  44,  44,  44,
     44,  44,  65,  81,  36,  36,  36,  36,  36,  82,  44,  44,  83,   0,   0,   0,
      7,   7,  76,  36,  36,  36,  36,  36,  36,  36,  67,  44,  44,  41,  84,   0,
     36,  36,  36,  36,  36,  82,  85,  44,  44,  86,  86,  87,   0,   0,   0,   0,
     36,  36,  36,  36,  36,  36,  86,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     36,  36,  36,  36,  61,   0,   0,   0,   0,  44,  44,  44,  44,  44,  44,  44,
     44,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  82,  88,
     44,  44,  44,  44,  86,  44,  36,  36,  82,  89,   7,   7,  81,  36,  36,  36,
     86,  81,  36,  77,  77,  36,  36,  36,  36,  36,  90,  36,  43,  40,  41,  88,
     44,  91,  91,  92,   0,  93,   0,  94,  82,  95,   7,   7,  41,   0,   0,   0,
     58,  81,  61,  96,  77,  36,  36,  36,  36,  36,  90,  36,  90,  97,  41,  74,
     65,  93,  91,  87,  98,   0,  81,  43,   0,  95,   7,   7,  75,  99,   0,   0,
     58,  81,  36,  94,  94,  36,  36,  36,  36,  36,  90,  36,  90,  81,  41,  88,
     44,  59,  59,  87, 100,   0,   0,   0,  82,  95,   7,   7,   0,   0,   0,   0,
     58,  81,  36,  77,  77,  36,  36,  36,  44,  91,  91,  87,   0, 101,   0,  94,
     82,  95,   7,   7,  55,   0,   0,   0, 102,  81,  61,  40,  90,  41,  97,  90,
     96, 100,  61,  40,  36,  36,  41, 101,  65, 101,  74,  87, 100,  93,   0,   0,
      0,  95,   7,   7,   0,   0,   0,   0,  44,  81,  36,  90,  90,  36,  36,  36,
     36,  36,  90,  36,  36,  36,  41, 103,  44,  74,  74,  87,   0,  60,  41,   0,
     58,  81,  36,  90,  90,  36,  36,  36,  36,  36,  90,  36,  36,  81,  41,  88,
     44,  74,  74,  87,   0,  60,   0, 104,  82,  95,   7,   7,  97,   0,   0,   0,
     36,  36,  36,  36,  36,  36,  61, 103,  44,  74,  74,  92,   0,  93,   0,   0,
     82,  95,   7,   7,   0,   0,  40,  36, 101,  81,  36,  36,  36,  61,  40,  36,
     36,  36,  36,  36,  94,  36,  36,  55,  36,  61, 105,  93,  44, 106,  44,  44,
      0,  95,   7,   7, 101,   0,   0,   0,  81,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  80,  44,  65,   0,  36,  67,  44,  65,   7,   7, 107,   0,
     97,  77,  43,  55,   0,  36,  81,  36,  81, 108,  40,  81,  80,  44,  59,  83,
     36,  43,  44,  87,   7,   7, 107,  36, 100,   0,   0,   0,   0,   0,  87,   0,
      7,   7, 107,   0,   0, 109, 110, 111,  36,  36,  81,  36,  36,  36,  36,  36,
     36,  36,  36, 100,  58,  44,  44,  44,  44,  74,  36,  86,  44,  44,  58,  44,
     44,  44,  44,  44,  44,  44,  44, 112,   0, 105,   0,   0,   0,   0,   0,   0,
     36,  36,  67,  44,  44,  44,  44, 113,   7,   7, 114,   0,  36,  82,  75,  82,
     88,  73,  44,  75,  86,  70,  36,  36,  82,  44,  44,  85,   7,   7, 115,  87,
     11,  50,   0, 116,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  61,  36,
     36,  36,  90,  41,  36,  61,  90,  41,  36,  36,  90,  41,  36,  36,  36,  36,
     36,  36,  36,  36,  90,  41,  36,  61,  90,  41,  36,  36,  36,  61,  36,  36,
     36,  36,  36,  36,  90,  41,  36,  36,  36,  36,  36,  36,  36,  36,  61,  58,
    117,   9, 118,   0,   0,   0,   0,   0,  36,  36,  36,  36,   0,   0,   0,   0,
     36,  36,  36,  36,  36, 100,   0,   0,  36,  36,  36, 119,  36,  36,  36,  36,
    120,  36,  36,  36,  36,  36, 121, 122,  36,  36,  61,  40,  36,  36, 100,   0,
     36,  36,  36,  90,  82, 112,   0,   0,  36,  36,  36,  36,  82, 123,   0,   0,
     36,  36,  36,  36,  82,   0,   0,   0,  36,  36,  36,  90, 124,   0,   0,   0,
     36,  36,  36,  36,  36,  44,  44,  44,  44,  44,  44,  44,  44,  96,   0,  99,
      7,   7, 107,   0,   0,   0,   0,   0, 125,   0, 126, 127,   7,   7, 107,   0,
     36,  36,  36,  36,  36,  36,   0,   0,  36,  36, 128,   0,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  41,   0,   0,  36,  36,  36,  36,  36,  36,  36,  61,
     44,  44,  44,   0,  44,  44,  44,   0,   0,  89,   7,   7,  36,  36,  36,  36,
     36,  36,  36,  41,  36, 100,   0,   0,  36,  36,  36,   0,  44,  44,  44,  44,
     70,  36,  87,   0,   7,   7, 107,   0,  36,  36,  36,  36,  36,  67,  44,   0,
     36,  36,  36,  36,  36,  86,  44,  65,  44,  44,  44,  44,  44,  44,  44,  91,
      7,   7, 107,   0,   7,   7, 107,   0,   0,  96, 129,   0,  44,  44,  44,  65,
     44,  70,  36,  36,  36,  36,  36,  36,  44,  70,  36,   0,   7,   7, 114, 130,
      0,   0,  93,  44,  44,   0,   0,   0, 113,  36,  36,  36,  36,  36,  36,  36,
     86,  44,  44,  75,   7,   7,  76,  36,  36,  82,  44,  44,  44,   0,   0,   0,
     36,  44,  44,  44,  44,  44,   9, 118,   7,   7, 107,  81,   7,   7,  76,  36,
     36,  36,  36,  36,  36,  36,  36, 131,   0,   0,   0,   0,  65,  44,  44,  44,
     44,  44,  70,  80,  82, 132,  87,   0,  44,  44,  44,  44,  44,  87,   0,  44,
     25,  25,  25,  25,  25,  34,  15,  27,  15,  15,  11,  11,  15,  39,  11, 133,
     15,  15,  11,  11,  15,  15,  11,  11,  15,  39,  11, 133,  15,  15, 134, 134,
     15,  15,  11,  11,  15,  15,  15,  39,  15,  15,  11,  11,  15, 135,  11, 136,
     46, 135,  11, 137,  15,  46,  11,   0,  15,  15,  11, 137,  46, 135,  11, 137,
    138, 138, 139, 140, 141, 142, 143, 143,   0, 144, 145, 146,   0,   0, 147, 148,
      0, 149, 148,   0,   0,   0,   0, 150,  62, 151,  62,  62,  21,   0,   0, 152,
      0,   0,   0, 147,  15,  15,  15,  42,   0,   0,   0,   0,  44,  44,  44,  44,
     44,  44,  44,  44, 112,   0,   0,   0,  48, 153, 154, 155,  23, 116,  10, 133,
      0, 156,  49, 157,  11,  38, 158,  33,   0, 159,  39, 160,   0,   0,   0,   0,
    161,  38, 100,   0,   0,   0,   0,   0,   0,   0, 143,   0,   0,   0,   0,   0,
      0,   0, 147,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 162,  11,  11,
     15,  15,  39,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4, 143,
    122,   0, 143, 143, 143,   5,   0,   0,   0, 147,   0,   0,   0,   0,   0,   0,
      0, 163, 143, 143,   0,   0,   0,   0,   4, 143, 143, 143, 143, 143, 122,   0,
      0,   0,   0,   0,   0,   0, 143,   0,   0,   0,   0,   0,   0,   0,   0,   5,
     11,  11,  11,  22,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  24,
     31, 164,  26,  32,  25,  29,  15,  33,  25,  42, 153, 165,  54,   0,   0,   0,
     15, 166,   0,  21,  36,  36,  36,  36,  36,  36,   0,  96,   0,   0,   0,  93,
     36,  36,  36,  36,  36,  61,   0,   0,  36,  61,  36,  61,  36,  61,  36,  61,
    143, 143, 143,   5,   0,   0,   0,   5, 143, 143,   5, 167,   0,   0,   0, 118,
    168,   0,   0,   0,   0,   0,   0,   0, 169,  81, 143, 143,   5, 143, 143, 170,
     81,  36,  82,  44,  81,  41,  36, 100,  36,  36,  36,  36,  36,  61,  60,  81,
      0,  81,  36,  36,  36,  36,  36,  36,  36,  36,  36,  41,  81,  36,  36,  36,
     36,  36,  36,  61,   0,   0,   0,   0,  36,  36,  36,  36,  36,  36,  61,   0,
      0,   0,   0,   0,  36,  36,  36,  36,  36,  36,  36, 100,   0,   0,   0,   0,
     36,  36,  36,  36,  36,  36,  36, 171,  36,  36,  36, 172,  36,  36,  36,  36,
      7,   7,  76,   0,   0,   0,   0,   0,  25,  25,  25, 173,  65,  44,  44, 174,
     25,  25,  25,  25,  25,  25,  25, 175,  36,  36,  36,  36, 176,   9,   0,   0,
      0,   0,   0,   0,   0,  96,  36,  36, 177,  25,  25,  25,  27,  25,  25,  25,
     25,  25,  25,  25,  15,  15,  26,  30,  25,  25, 178, 179,  25,  27,  25,  25,
     25,  25,  31, 133, 133,   0,   0,   0,   0,   0,   0,   0,   0,  96, 180,  36,
    181, 181,  67,  36,  36,  36,  36,  36,  67,  44,   0,   0,   0,   0,   0,   0,
     36,  36,  36,  36,  36, 130,   0,   0,  75,  36,  36,  36,  36,  36,  36,  36,
     44, 112,   0, 130,   7,   7, 107,   0,  44,  44,  44,  44,  75,  36,  96,   0,
     36,  82,  44, 176,  36,  36,  36,  36,  36,  67,  44,  44,  44,   0,   0,   0,
     36,  36,  36,  36,  36,  36,  36, 100,  36,  36,  36,  36,  67,  44,  44,  44,
    112,   0, 148,  96,   7,   7, 107,   0,  36,  80,  36,  36,   7,   7,  76,  61,
     36,  36,  86,  44,  44,  65,   0,   0,  67,  36,  36,  87,   7,   7, 107, 182,
     36,  36,  36,  36,  36,  61, 183,  75,  36,  36,  36,  36,  88,  73,  70,  82,
    128,   0,   0,   0,   0,   0,  96,  41,  36,  36,  67,  44, 184, 185,   0,   0,
     81,  61,  81,  61,  81,  61,   0,   0,  36,  61,  36,  61,  15,  15,  15,  15,
     15,  15,  15,  15,  15,  15,  24,  15,   0,  39,   0,   0,   0,   0,   0,   0,
     67,  44, 186,  87,   7,   7, 107,   0,  36,   0,   0,   0,  36,  36,  36,  36,
     36,  61,  96,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,   0,
     36,  36,  36,  41,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  41,   0,
     15,  24,   0,   0, 187,  15,   0, 188,  36,  36,  90,  36,  36,  61,  36,  43,
     94,  90,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  41,   0,   0,   0,
      0,   0,   0,   0,  96,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36, 189,
     36,  36,  36,  36,  40,  36,  36,  36,  36,  36,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  36,  36,  36,   0,  44,  44,  44,  44, 190,   4, 122,   0,
     44,  44,  44,  87, 191, 170, 143, 143, 143, 192, 122,   0,   6, 193, 194, 195,
    141,   0,   0,   0,  36,  90,  36,  36,  36,  36,  36,  36,  36,  36,  36, 196,
     57,   0,   5,   6,   0,   0, 197,   9,  14,  15,  15,  15,  15,  15,  16, 198,
    199, 200,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  82,
     40,  36,  40,  36,  40,  36,  40, 100,   0,   0,   0,   0,   0,   0, 201,   0,
     36,  36,  36,  81,  36,  36,  36,  36,  36,  61,  36,  36,  36,  36,  61,  94,
     36,  36,  36,  41,  36,  36,  36,  41,   0,   0,   0,   0,   0,   0,   0,  98,
     36,  36,  36,  36, 100,   0,   0,   0, 112,   0,   0,   0,   0,   0,   0,   0,
     36,  36,  61,   0,  36,  36,  36,  36,  36,  36,  36,  36,  36,  82,  65,   0,
     36,  36,  36,  36,  36,  36,  36,  41,  36,   0,  36,  36,  81,  41,   0,   0,
     11,  11,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  36,  36,  36,  36,
     36,  36,   0,   0,  36,  36,  36,  36,  36,   0,   0,   0,   0,   0,   0,   0,
     36,  41,  90,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  94, 100,  77,
     36,  36,  36,  36,  36,  36,   0,  40,  86,  60,   0,  44,  36,  81,  81,  36,
     36,  36,  36,  36,  36,   0,  65,  93,   0,   0,   0,   0,   0, 130,   0,   0,
     36, 185,   0,   0,   0,   0,   0,   0,  36,  36, 100,   0,   0,   0,   0,   0,
     36,  36,  36,  36,  36,  36,  44,  44,  44, 186, 118,   0,   0,   0,   0,   0,
      0,  95,   7,   7,   0,   0,   0,  93,  36,  36,  36,  36,  44,  44,  65, 202,
    148,   0,   0,   0,  36,  36,  36,  36,  36,  36, 100,   0,   7,   7, 107,   0,
     36,  67,  44,  44,  44, 203,   7,   7, 182,   0,   0,   0,  36,  36,  36,  36,
     36,  36,  36,  36,  67, 104,   0,   0,  70, 204,   0,  57,   7,   7, 205,   0,
     36,  36,  36,  36,  94,  36,  36,  36,  36,  36,  36,  44,  44,  44, 206, 118,
     36,  36,  36,  36,  36,  36,  36,  67,  44,  44,  65,   0,   7,   7, 107,   0,
     44,  91,  91,  87,   0,  93,   0,  81,  82, 101,  44, 112,  44, 112,   0,   0,
     44,  94,   0,   0,   7,   7, 107,   0,  36,  36,  36,  67,  44,  87,  44,  44,
    207,   0,  57,   0,   0,   0,   0,   0, 123, 100,   0,   0,   7,   7, 107,   0,
     36,  36,  67,  44,  44,  44,   0,   0,   7,   7, 107,   0,   0,   0,   0,  96,
     36,  36,  36,  36,  36,  36, 100,   0,   7,   7, 107, 130,   0,   0,   0,   0,
     36,  36,  36,  41,  44, 208,   0,   0,  36,  36,  36,  36,  44, 186, 118,   0,
     36, 118,   0,   0,   7,   7, 107,   0,  96,  36,  36,  36,  36,  36,   0,  81,
     36, 100,   0,   0,  86,  44,  44,  44,  44,  44,  44,  44,  44,  44,  44,  65,
      0,   0,   0,  93, 113,  36,  36,  36,  41,   0,   0,   0,   0,   0,   0,   0,
     36,  36,  61,   0,  36,  36,  36, 100,  36,  36, 100,   0,  36,  36,  41, 209,
     62,   0,   0,   0,   0,   0,   0,   0,   0,  58,  87,  58, 210,  62, 211,  44,
     65,  58,  44,   0,   0,   0,   0,   0,   0,   0, 101,  87,   0,   0,   0,   0,
    101, 112,   0,   0,   0,   0,   0,   0,  11,  11,  11,  11,  11,  11, 155,  15,
     15,  15,  15,  15,  15,  11,  11,  11,  11,  11,  11, 155,  15, 135,  15,  15,
     15,  15,  11,  11,  11,  11,  11,  11, 155,  15,  15,  15,  15,  15,  15,  49,
     48, 212,  10,  49,  11, 155, 166,  14,  15,  14,  15,  15,  11,  11,  11,  11,
     11,  11, 155,  15,  15,  15,  15,  15,  15,  50,  22,  10,  11,  49,  11, 213,
     15,  15,  15,  15,  15,  15,  50,  22,  11, 156, 162,  11, 213,  15,  15,  15,
     15,  15,  15,  11,  11,  11,  11,  11,  11, 155,  15,  15,  15,  15,  15,  15,
     11,  11,  11, 155,  15,  15,  15,  15, 155,  15,  15,  15,  15,  15,  15,  11,
     11,  11,  11,  11,  11, 155,  15,  15,  15,  15,  15,  15,  11,  11,  11,  11,
     15,  39,  11,  11,  11,  11,  11,  11, 213,  15,  15,  15,  15,  15,  24,  15,
     33,  11,  11,  11,  11,  11,  22,  15,  15,  15,  15,  15,  15, 135,  15,  11,
     11,  11,  11,  11,  11, 213,  15,  15,  15,  15,  15,  24,  15,  33,  11,  11,
     15,  15, 135,  15,  11,  11,  11,  11,  11,  11, 213,  15,  15,  15,  15,  15,
     24,  15,  27,  95,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
     36, 100,   0,   0,  44,  65,   0,   0,  36,  81,  36,  36,  36,  36,  36,  36,
     97,  77,  81,  36,  61,  36, 108,   0, 104,  96, 108,  81,  97,  77, 108, 108,
     97,  77,  61,  36,  61,  36,  81,  43,  36,  36,  94,  36,  36,  36,  36,   0,
     81,  81,  94,  36,  36,  36,  36,   0,   0,   0,   0,   0,  11,  11,  11,  11,
     11,  11, 133,   0,  11,  11,  11,  11,  11,  11, 133,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 163, 122,   0,  20,   0,   0,   0,   0,   0,   0,   0,
     62,  62,  62,  62,  62,  62,  62,  62,  44,  44,  44,  44,   0,   0,   0,   0,
};

static RE_UINT8 re_sentence_break_stage_5[] = {
     0,  0,  0,  0,  0,  6,  2,  6,  6,  1,  0,  0,  6, 12, 13,  0,
     0,  0,  0, 13, 13, 13,  0,  0, 14, 14, 11,  0, 10, 10, 10, 10,
    10, 10, 14,  0,  0,  0,  0, 12,  0,  8,  8,  8,  8,  8,  8,  8,
     8,  8,  8, 13,  0, 13,  0,  0,  0,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7, 13,  0,  4,  0,  0,  6,  0,  0,  0,  0,  0,  7, 13,
     0,  5,  0,  0,  0,  7,  0,  0,  8,  8,  8,  0,  8,  8,  8,  7,
     7,  7,  7,  0,  8,  7,  8,  7,  7,  8,  7,  8,  7,  7,  8,  7,
     8,  8,  7,  8,  7,  8,  7,  7,  7,  8,  8,  7,  8,  7,  8,  8,
     7,  8,  8,  8,  7,  7,  8,  8,  8,  7,  7,  7,  8,  7,  7,  9,
     9,  9,  9,  9,  9,  7,  7,  7,  7,  9,  9,  9,  7,  7,  0,  0,
     0,  0,  9,  9,  9,  9,  0,  0,  7,  0,  0,  0,  9,  0,  9,  0,
     3,  3,  3,  3,  9,  0,  8,  7,  0,  0,  7,  7,  7,  7,  0,  8,
     0,  0,  8,  0,  8,  0,  8,  8,  8,  8,  0,  8,  7,  7,  7,  8,
     8,  7,  0,  8,  8,  7,  0,  3,  3,  3,  8,  7,  0,  9,  0,  0,
     0, 14,  0,  0,  0, 12,  0,  0,  0,  3,  3,  3,  3,  3,  0,  3,
     0,  3,  3,  0,  9,  9,  9,  0,  5,  5,  5,  5,  5,  5,  0,  0,
    14, 14,  0,  0,  3,  3,  3,  0,  5,  0,  0, 12,  9,  9,  9,  3,
    10, 10,  0, 10, 10,  0,  9,  9,  3,  9,  9,  9, 12,  9,  3,  3,
     3,  5,  0,  3,  3,  9,  9,  3,  3,  0,  3,  3,  3,  3,  9,  9,
    10, 10,  9,  9,  9,  0,  0,  9, 12, 12, 12,  0,  0,  0,  0,  5,
     9,  3,  9,  9,  0,  9,  9,  9,  9,  9,  3,  3,  3,  9,  0,  0,
    14, 12,  9,  0,  3,  3,  9,  3,  9,  3,  3,  3,  3,  3,  0,  0,
     3,  9,  3,  3, 12, 12, 10, 10,  9,  0,  9,  9,  3,  0,  0,  3,
     3,  3,  9,  0,  0,  0,  0,  3,  9,  9,  0,  9,  0,  0, 10, 10,
     0,  0,  0,  9,  0,  9,  9,  0,  0,  3,  0,  0,  9,  3,  0,  0,
     9,  0,  0,  0,  0,  0,  3,  3,  0,  0,  3,  9,  0,  9,  3,  3,
     0,  0,  9,  0,  0,  0,  3,  0,  3,  0,  3,  0, 10, 10,  0,  0,
     0,  9,  0,  9,  0,  3,  0,  3,  0,  3, 13, 13, 13, 13,  3,  3,
     3,  0,  0,  0,  3,  3,  3,  9, 10, 10, 12, 12, 10, 10,  3,  3,
     0,  8,  0,  0,  0,  0, 12,  0, 12,  0,  0,  0,  9,  0, 12,  9,
     6,  9,  9,  9,  9,  9,  9, 13, 13,  0,  0,  0,  3, 12, 12,  0,
     9,  0,  3,  3,  0,  0, 14, 12, 14, 12,  0,  3,  3,  3,  5,  0,
     9,  3,  9,  0, 12, 12, 12, 12,  0,  0, 12, 12,  9,  9, 12, 12,
     3,  9,  9,  0,  8,  8,  0,  0,  0,  8,  0,  8,  7,  0,  7,  7,
     8,  0,  7,  0,  8,  0,  0,  0,  6,  6,  6,  6,  6,  6,  6,  5,
     3,  3,  5,  5,  0,  0,  0, 14, 14,  0,  0,  0, 13, 13, 13, 13,
    11,  0,  0,  0,  4,  4,  5,  5,  5,  5,  5,  6,  0, 13, 13,  0,
    12, 12,  0,  0,  0, 13, 13, 12,  0,  0,  0,  6,  5,  0,  5,  5,
     0, 13, 13,  7,  0,  0,  0,  8,  0,  0,  7,  8,  8,  8,  7,  7,
     8,  0,  8,  0,  8,  8,  0,  7,  9,  7,  0,  0,  0,  8,  7,  7,
     0,  0,  7,  0,  9,  9,  9,  8,  0,  0,  8,  8,  0,  0, 13, 13,
     8,  7,  7,  8,  7,  8,  7,  3,  7,  7,  0,  7,  0,  0, 12,  9,
     0,  0, 13,  0,  6, 14, 12,  0,  0, 13, 13, 13,  9,  9,  0, 12,
     9,  0, 12, 12,  8,  7,  9,  3,  3,  3,  0,  9,  7,  7,  0,  3,
     3,  3,  0, 12,  0,  0,  8,  7,  9,  0,  0,  8,  7,  8,  7,  0,
     7,  7,  7,  9,  9,  9,  3,  9,  0, 12, 12, 12,  0,  0,  9,  3,
    12, 12,  9,  9,  9,  3,  3,  0,  3,  3,  3, 12,  0,  0,  0,  7,
     0,  9,  3,  9,  9,  9, 13, 13, 14, 14,  0, 14,  0, 14, 14,  0,
    13,  0,  0, 13,  0, 14, 12, 12, 14, 13, 13, 13, 13, 13, 13,  0,
     9,  0,  0,  5,  0,  0, 14,  0,  0, 13,  0, 13, 13, 12, 13, 13,
    14,  0,  9,  9,  0,  5,  5,  5,  0,  5, 12, 12,  3,  0, 10, 10,
     9, 12, 12,  0, 10, 10,  9,  0, 12, 12,  0, 12,  3,  0, 12, 12,
     3, 12,  0,  0,  0,  3,  3, 12,  3,  3,  3,  5,  5,  5,  5,  3,
     0,  8,  8,  0,  8,  0,  7,  7,
};

/* Sentence_Break: 6120 bytes. */

RE_UINT32 re_get_sentence_break(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_sentence_break_stage_1[f] << 4;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_sentence_break_stage_2[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_sentence_break_stage_3[pos + f] << 3;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_sentence_break_stage_4[pos + f] << 2;
    value = re_sentence_break_stage_5[pos + code];

    return value;
}

/* Math. */

static RE_UINT8 re_math_stage_1[] = {
    0, 1, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2,
};

static RE_UINT8 re_math_stage_2[] = {
    0, 1, 1, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 4,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 5, 1, 1, 6, 1, 1,
};

static RE_UINT8 re_math_stage_3[] = {
     0,  1,  1,  2,  1,  1,  3,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     4,  5,  6,  7,  1,  8,  9, 10,  1,  6,  6, 11,  1,  1,  1,  1,
     1,  1,  1, 12,  1,  1, 13, 14,  1,  1,  1,  1, 15, 16, 17, 18,
     1,  1,  1,  1,  1,  1, 19,  1,
};

static RE_UINT8 re_math_stage_4[] = {
     0,  1,  2,  3,  0,  4,  5,  5,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  6,  7,  8,  0,  0,  0,  0,  0,  0,  0,
     9, 10, 11, 12, 13,  0, 14, 15, 16, 17, 18,  0, 19, 20, 21, 22,
    23, 23, 23, 23, 23, 23, 23, 23, 24, 25,  0, 26, 27, 28, 29, 30,
     0,  0,  0,  0,  0, 31, 32, 33, 34,  0, 35, 36,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 23, 23,  0, 19, 37,  0,  0,  0,  0,  0,
     0, 38,  0,  0,  0,  0,  0,  0,  0,  0,  0, 39,  0,  0,  0,  0,
     1,  3,  3,  0,  0,  0,  0, 40, 23, 23, 41, 23, 42, 43, 44, 23,
    45, 46, 47, 23, 23, 23, 23, 23, 23, 23, 23, 23, 23, 48, 23, 23,
    23, 23, 23, 23, 23, 23, 49, 23, 44, 50, 51, 52, 53, 54,  0, 55,
};

static RE_UINT8 re_math_stage_5[] = {
      0,   0,   0,   0,   0,   8,   0, 112,   0,   0,   0,  64,   0,   0,   0,  80,
      0,  16,   2,   0,   0,   0, 128,   0,   0,   0,  39,   0,   0,   0, 115,   0,
    192,   1,   0,   0,   0,   0,  64,   0,   0,   0,  28,   0,  17,   0,   4,   0,
     30,   0,   0, 124,   0, 124,   0,   0,   0,   0, 255,  31,  98, 248,   0,   0,
    132, 252,  47,  63,  16, 179, 251, 241, 255,  11,   0,   0,   0,   0, 255, 255,
    255, 126, 195, 240, 255, 255, 255,  47,  48,   0, 240, 255, 255, 255, 255, 255,
      0,  15,   0,   0,   3,   0,   0,   0,   0,   0,   0,  16,   0,   0,   0, 248,
    255, 255, 191,   0,   0,   0,   1, 240,   7,   0,   0,   0,   3, 192, 255, 240,
    195, 140,  15,   0, 148,  31,   0, 255,  96,   0,   0,   0,   5,   0,   0,   0,
     15, 224,   0,   0, 159,  31,   0,   0,   0,   2,   0,   0, 126,   1,   0,   0,
      4,  30,   0,   0, 255, 255, 223, 255, 255, 255, 255, 223, 100, 222, 255, 235,
    239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,  95, 252, 253, 255,
     63, 255, 255, 255, 255, 207, 255, 255, 150, 254, 247,  10, 132, 234, 150, 170,
    150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,   0,   0,   3,   0,
};

/* Math: 538 bytes. */

RE_UINT32 re_get_math(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_math_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_math_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_math_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_math_stage_4[pos + f] << 5;
    pos += code;
    value = (re_math_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Alphabetic. */

static RE_UINT8 re_alphabetic_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3,
};

static RE_UINT8 re_alphabetic_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 26, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 27,  7, 28, 29, 13, 13, 13, 13, 13, 13, 13, 30,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_alphabetic_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 32, 31, 31, 31, 31, 31, 31, 31, 33, 34, 35, 31,
    36, 37, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 38,  1,  1,  1,  1,  1,  1,  1,  1,  1, 39,
     1,  1,  1,  1, 40,  1, 41, 42, 43, 44, 45, 46,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 47, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 48, 49,  1, 50, 51, 52, 53, 54, 55, 56, 57, 58,  1, 59,
    60, 61, 62, 63, 64, 31, 31, 31, 65, 66, 67, 68, 69, 70, 71, 31,
    72, 31, 73, 31, 31, 31, 31, 31,  1,  1,  1, 74, 75, 31, 31, 31,
     1,  1,  1,  1, 76, 31, 31, 31,  1,  1, 77, 78, 31, 31, 31, 79,
    80, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 81, 31, 31, 31,
    31, 31, 31, 31, 82, 83, 84, 85, 86, 31, 31, 31, 31, 31, 87, 31,
    31, 88, 31, 31, 31, 31, 31, 31,  1,  1,  1,  1,  1,  1, 89,  1,
     1,  1,  1,  1,  1,  1,  1, 90, 91, 31, 31, 31, 31, 31, 31, 31,
     1,  1, 91, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_alphabetic_stage_4[] = {
      0,   0,   1,   1,   0,   2,   3,   3,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   5,   6,   0,   0,   7,   8,   9,  10,   4,  11,
      4,   4,   4,   4,  12,   4,   4,   4,   4,  13,  14,  15,  16,  17,  18,  19,
     20,   4,  21,  22,   4,   4,  23,  24,  25,   4,  26,   4,   4,  27,  28,  29,
     30,  31,  32,   0,   0,  33,   0,  34,   4,  35,  36,  37,  38,  39,  40,  41,
     42,  43,  44,  45,  46,  47,  48,  49,  50,  47,  51,  52,  53,  54,  55,   0,
     56,  57,  58,  49,  59,  60,  61,  62,  59,  63,  64,  65,  66,  67,  68,  69,
     15,  70,  71,   0,  72,  73,  74,   0,  75,   0,  76,  77,  78,  79,   0,   0,
      4,  80,  25,  81,  82,   4,  83,  84,   4,   4,  85,   4,  86,  87,  88,   4,
     89,   4,  90,   0,  91,   4,   4,  92,  15,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,  93,   1,   4,   4,  94,  95,  96,  96,  97,   4,  98,  99,   0,
      0,   4,   4, 100,   4, 101,   4, 102, 103, 104,  25, 105,   4, 106, 107,   0,
    108,   4, 103, 109,   0, 110,   0,   0,   4, 111, 112,   0,   4, 113,   4, 114,
      4, 102, 115, 116,   0,   0,   0, 117,   4,   4,   4,   4,   4,   4,   0, 118,
    119,   4, 120, 116,   4, 121, 122, 123,   0,   0,   0, 124, 125,   0,   0,   0,
    126, 127, 128,   4, 129,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 130,   4, 107,   4, 131, 103,   4,   4,   4,   4, 132,
      4,  83,   4, 133, 134, 135, 135,   4,   0, 136,   0,   0,   0,   0,   0,   0,
    137, 138,  15,   4, 139,  15,   4,  84, 140, 141,   4,   4, 142,  70,   0,  25,
      4,   4,   4,   4,   4, 102,   0,   0,   4,   4,   4,   4,   4,   4,  31,   0,
      4,   4,   4,   4,  31,   0,  25, 116, 143, 144,   4, 145, 146,   4,   4,  91,
    147, 148,   4,   4, 149, 150,   0, 147, 151,  16,   4,  96,   4,   4,  49, 152,
     28, 101,  33,  79,   4, 153, 136, 154,   4, 134, 155, 156,   4, 103, 157, 158,
    159, 160,  84, 161,   0,   0,   4, 162,   4,   4,   4,   4,   4, 163, 164, 108,
      4,   4,   4, 165,   4,   4, 166,   0, 167, 168, 169,   4,   4,  27, 170,   4,
      4, 116,  25,   4, 171,   4,  16, 172,   0,   0,   0, 173,   4,   4,   4,  79,
      0,   1,   1, 174,   4, 103, 175,   0, 176, 177, 178,   0,   4,   4,   4,  70,
      0,   0,   4,  92,   0,   0,   0,   0,   0,   0,   0,   0,  79,   4, 179,   0,
      4,  25, 101,  70, 116,   4, 180,   0,   4,   4,   4,   4, 116,   0,   0,   0,
      4, 181,   4,  49,   0,   0,   0,   0,   4, 134, 102,  16,   0,   0,   0,   0,
    182, 183, 102, 134, 103,   0,   0,   0, 102, 166,   0,   0,   4, 184,   0,   0,
    185,  96,   0,  79,  79,   0,  76, 186,   4, 102, 102,  33,  27,   0,   0,   0,
      4,   4, 129,   0,   0,   0,   0,   0,   4,   4, 187,   0, 148,  32,  25, 129,
      4,  33,  25, 188,   4,   4, 189,   0, 190, 191,   0,   0,   0,  25,   4, 129,
     50,  47, 192,  49,   0,   0,   0,   0,   0,   0,   0,   0,   4,   4, 193,   0,
      0,   0,   0,   0,   4, 194,   0,   0,   4, 103, 195,   0,   4, 102,   0,   0,
      0,   0,   0,   0,   0,   4,   4, 196,   0,   0,   0,   0,   0,   0,   4,  32,
      4,   4,   4,   4,  32,   0,   0,   0,   4,   4,   4, 142,   0,   0,   0,   0,
      4, 142,   0,   0,   0,   0,   0,   0,   4,  32, 103,   0,   0,   0,  25, 155,
      4, 134,  49, 197,  91,   0,   0,   0,   4,   4, 198, 103, 170,   0,   0,   0,
    199,   0,   0,   0,   0,   0,   0,   0,   4,   4,   4, 200, 201,   0,   0,   0,
      4,   4, 202,   4, 203, 204, 205,   4, 206, 207, 208,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4, 209, 210,  84, 202, 202, 131, 131, 211, 211, 212,   0,
      4,   4,   4,   4,   4,   4, 186,   0, 205, 213, 214, 215, 216, 217,   0,   0,
      0,  25, 218, 218, 107,   0,   0,   0,   4,   4,   4,   4,   4,   4, 134,   0,
      4,  92,   4,   4,   4,   4,   4,   4, 116,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_alphabetic_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,  32,   0,   0,   0,
      0,   0, 223, 188,  64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,
      3, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255,
    255,   0,   0,   0,   0,   0, 255, 191, 182,   0, 255, 255, 255,   7,   7,   0,
      0,   0, 255,   7, 255, 255, 255, 254,   0, 192, 255, 255, 255, 255, 239,  31,
    254, 225,   0, 156,   0,   0, 255, 255,   0, 224, 255, 255, 255, 255,   3,   0,
      0, 252, 255, 255, 255,   7,  48,   4, 255, 255, 255, 252, 255,  31,   0,   0,
    255, 255, 255,   1, 255, 255,   7,   0, 240,   3, 255, 255, 255, 255, 255, 239,
    255, 223, 225, 255,  15,   0, 254, 255, 239, 159, 249, 255, 255, 253, 197, 227,
    159,  89, 128, 176,  15,   0,   3,   0, 238, 135, 249, 255, 255, 253, 109, 195,
    135,  25,   2,  94,   0,   0,  63,   0, 238, 191, 251, 255, 255, 253, 237, 227,
    191,  27,   1,   0,  15,   0,   0,   0, 238, 159, 249, 255, 159,  25, 192, 176,
     15,   0,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195, 199,  29, 129,   0,
    239, 223, 253, 255, 255, 253, 255, 227, 223,  29,  96,   3, 238, 223, 253, 255,
    255, 253, 239, 227, 223,  29,  96,  64,  15,   0,   6,   0, 255, 255, 255, 231,
    223,  93, 128,   0,  15,   0,   0, 252, 236, 255, 127, 252, 255, 255, 251,  47,
    127, 128,  95, 255,   0,   0,  12,   0, 255, 255, 255,   7, 127,  32,   0,   0,
    150,  37, 240, 254, 174, 236, 255,  59,  95,  32,   0, 240,   1,   0,   0,   0,
    255, 254, 255, 255, 255,  31, 254, 255,   3, 255, 255, 254, 255, 255, 255,  31,
    255, 255, 127, 249, 231, 193, 255, 255, 127,  64,   0,  48, 191,  32, 255, 255,
    255, 255, 255, 247, 255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,
     61, 255, 127, 255, 255, 255,  61, 255, 255, 255, 255, 135, 255, 255,   0,   0,
    255, 255,  31,   0, 255, 159, 255, 255, 255, 199, 255,   1, 255, 223,  15,   0,
    255, 255,  15,   0, 255, 223,  13,   0, 255, 255, 207, 255, 255,   1, 128,  16,
    255, 255, 255,   0, 255,   7, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127,
    255,  15, 255,   1, 255,  63,  31,   0, 255,  15, 255, 255, 255,   3,   0,   0,
    255, 255, 255,  15, 254, 255,  31,   0, 128,   0,   0,   0, 255, 255, 239, 255,
    239,  15,   0,   0, 255, 243,   0, 252, 191, 255,   3,   0,   0, 224,   0, 252,
    255, 255, 255,  63,   0, 222, 111,   0, 128, 255,  31,   0, 255, 255,  63,  63,
     63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   2, 128,   0,   0, 255,  31, 132, 252,  47,  62,  80, 189, 255, 243,
    224,  67,   0,   0, 255,   1,   0,   0,   0,   0, 192, 255, 255, 127, 255, 255,
     31, 120,  12,   0, 255, 128,   0,   0, 255, 255, 127,   0, 127, 127, 127, 127,
      0, 128,   0,   0, 224,   0,   0,   0, 254,   3,  62,  31, 255, 255, 127, 224,
    224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31, 255, 255,
      0,  12,   0,   0, 255, 127, 240, 143, 255, 255, 255, 191,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 121, 255, 255, 255,  63,   3,   0, 187, 247, 255, 255,
      0,   0, 252,   8, 255, 255, 247, 255, 223, 255,   0, 124, 255,  63,   0,   0,
    255, 255, 127, 196,   5,   0,   0,  56, 255, 255,  60,   0, 126, 126, 126,   0,
    127, 127, 255, 255,  48,   0,   0,   0, 255,   7,   0,   0,  15,   0, 255, 255,
    127, 248, 255, 255, 255,  63, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224,
    255, 253, 127,  95, 219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,
      0,   0, 255,  15,   0,   0, 223, 255, 192, 255, 255, 255, 252, 252, 252,  28,
    255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63, 255, 255,   1,   0,
     15, 255,  62,   0, 255,   0, 255, 255,  63, 253, 255, 255, 255, 255, 191, 145,
    255, 255, 255, 192, 111, 240, 239, 254,  31,   0,   0,   0,  63,   0,   0,   0,
    255, 255,  71,   0,  30,   0,   0,   4, 255, 255, 251, 255, 255, 255, 159,   0,
    159,  25, 128, 224, 179,   0,   0,   0, 255, 255,  63, 127,  17,   0,   0,   0,
      0,   0,   0, 128, 248, 255, 255, 224,  31,   0, 255, 255,   3,   0,   0,   0,
    255,   7, 255,  31, 255,   1, 255,  67, 255, 255, 223, 255, 255, 255, 255, 223,
    100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,
     95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247, 255, 253, 255, 255,
    247,  15,   0,   0, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94,
    255, 251, 255,  15, 238, 251, 255,  15, 255,   3, 255, 255,
};

/* Alphabetic: 2005 bytes. */

RE_UINT32 re_get_alphabetic(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_alphabetic_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_alphabetic_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_alphabetic_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_alphabetic_stage_4[pos + f] << 5;
    pos += code;
    value = (re_alphabetic_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Lowercase. */

static RE_UINT8 re_lowercase_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_lowercase_stage_2[] = {
     0,  1,  1,  2,  3,  4,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  5,  6,  1,  1,  1,  1,  1,  1,  1,  1,  1,  7,
     8,  1,  1,  9,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 10,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_lowercase_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  7,  8,  9, 10, 11,  6,  6, 12,  6,  6,  6,
     6,  6,  6,  6, 13, 14,  6,  6,  6,  6,  6,  6,  6,  6, 15, 16,
     6,  6,  6, 17,  6,  6,  6,  6,  6,  6,  6, 18,  6,  6,  6, 19,
     6,  6,  6,  6, 20,  6,  6,  6, 21,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6, 22, 23, 24, 25,
};

static RE_UINT8 re_lowercase_stage_4[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
     5, 13, 14, 15, 16, 17, 18, 19,  0,  0, 20, 21, 22, 23, 24, 25,
     0, 26, 15,  5, 27,  5, 28,  5,  5, 29,  0, 30, 31,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 15, 15, 15, 15, 15, 15,  0,  0,
     5,  5,  5,  5, 32,  5,  5,  5, 33, 34, 35, 36, 34, 37, 38, 39,
     0,  0,  0, 40, 41,  0,  0,  0, 42, 43, 44, 26, 45,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 26, 46,  0, 26, 47, 48,  5,  5,  5, 49,
    15, 50,  0,  0,  0,  0,  0,  0,  0,  0,  5, 51, 52,  0,  0,  0,
     0, 53,  5, 54, 55, 56,  0, 57,  0, 26, 58, 59,  0,  0,  0,  0,
    60,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,
     0, 61, 62,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 15,  0,
    63, 64, 65, 31, 66, 67, 68, 69, 70, 71, 72, 73, 74, 63, 64, 75,
    31, 66, 76, 62, 69, 77, 78, 79, 80, 76, 81, 26, 82, 69, 83,  0,
};

static RE_UINT8 re_lowercase_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4,   0,   0,   0, 128,
    255, 255, 127, 255, 170, 170, 170, 170, 170, 170, 170,  85,  85, 171, 170, 170,
    170, 170, 170, 212,  41,  49,  36,  78,  42,  45,  81, 230,  64,  82,  85, 181,
    170, 170,  41, 170, 170, 170, 250, 147, 133, 170, 255, 255, 255, 255, 255, 255,
    255, 255, 239, 255, 255, 255, 255,   1,   3,   0,   0,   0,  31,   0,   0,   0,
     32,   0,   0,   0,   0,   0, 138,  60,   0,   0,   1,   0,   0, 240, 255, 255,
    255, 127, 227, 170, 170, 170,  47,  25,   0,   0, 255, 255,   2, 168, 170, 170,
     84, 213, 170, 170, 170, 170,   0,   0, 254, 255, 255, 255, 255,   0,   0,   0,
    170, 170, 234, 191, 255,   0,  63,   0, 255,   0, 255,   0,  63,   0, 255,   0,
    255,   0, 255,  63, 255,   0, 223,  64, 220,   0, 207,   0, 255,   0, 220,   0,
      0,   0,   2, 128,   0,   0, 255,  31,   0, 196,   8,   0,   0, 128,  16,  50,
    192,  67,   0,   0,  16,   0,   0,   0, 255,   3,   0,   0, 255, 255, 255, 127,
     98,  21, 218,  63,  26,  80,   8,   0, 191,  32,   0,   0, 170,  42,   0,   0,
    170, 170, 170,  58, 168, 170, 171, 170, 170, 170, 255, 149, 170,  80, 186, 170,
    170,   2,   0,   0,   0,   0,   0,   7, 255, 255, 255, 247,  48,   0,   0,   0,
    127,   0, 248,   0,   0, 255, 255, 255, 255, 255,   0,   0,   0,   0,   0, 252,
    255, 255,  15,   0,   0, 192, 223, 255, 252, 255, 255,  15,   0,   0, 192, 235,
    239, 255,   0,   0,   0, 252, 255, 255,  15,   0,   0, 192, 255, 255, 255,   0,
      0,   0, 252, 255, 255,  15,   0,   0, 192, 255, 255, 255,   0, 192, 255, 255,
      0,   0, 192, 255,  63,   0,   0,   0, 252, 255, 255, 247,   3,   0,   0, 240,
    255, 255, 223,  15, 255, 127,  63,   0, 255, 253,   0,   0, 247,  11,   0,   0,
};

/* Lowercase: 745 bytes. */

RE_UINT32 re_get_lowercase(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_lowercase_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_lowercase_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_lowercase_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_lowercase_stage_4[pos + f] << 5;
    pos += code;
    value = (re_lowercase_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Uppercase. */

static RE_UINT8 re_uppercase_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_uppercase_stage_2[] = {
     0,  1,  2,  3,  4,  5,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  6,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  7,
     8,  1,  1,  9,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 10,  1,  1,  1, 11,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_uppercase_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9,
     6, 10,  6,  6, 11,  6,  6,  6,  6,  6,  6,  6, 12,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 13, 14,  6,  6,  6,  6,  6,  6,  6, 15,
     6,  6,  6,  6, 16,  6,  6,  6, 17,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6, 18, 19, 20, 21,  6, 22,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_uppercase_stage_4[] = {
     0,  0,  1,  0,  0,  0,  2,  0,  3,  4,  5,  6,  7,  8,  9, 10,
     3, 11, 12,  0,  0,  0,  0,  0,  0,  0,  0, 13, 14, 15, 16, 17,
    18, 19,  0,  3, 20,  3, 21,  3,  3, 22, 23,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18, 24,  0,
     3,  3,  3,  3, 25,  3,  3,  3, 26, 27, 28, 29,  0, 30, 31, 32,
    33, 34, 35, 19, 36,  0,  0,  0,  0,  0,  0,  0,  0, 37, 19,  0,
    18, 38,  0, 39,  3,  3,  3, 40,  0,  0,  3, 41, 42,  0,  0,  0,
     0, 43,  3, 44, 45, 46,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,
    18, 47,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18,  0,  0,
    48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 48, 49, 50,
    51, 61, 62, 54, 55, 51, 63, 64, 65, 66, 37, 38, 54, 67, 68,  0,
     0, 54, 69, 69, 55,  0,  0,  0,
};

static RE_UINT8 re_uppercase_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7, 255, 255, 127, 127,  85,  85,  85,  85,
     85,  85,  85, 170, 170,  84,  85,  85,  85,  85,  85,  43, 214, 206, 219, 177,
    213, 210, 174,  17, 144, 164, 170,  74,  85,  85, 210,  85,  85,  85,   5, 108,
    122,  85,   0,   0,   0,   0,  69, 128,  64, 215, 254, 255, 251,  15,   0,   0,
      0, 128,  28,  85,  85,  85, 144, 230, 255, 255, 255, 255, 255, 255,   0,   0,
      1,  84,  85,  85, 171,  42,  85,  85,  85,  85, 254, 255, 255, 255, 127,   0,
    191,  32,   0,   0,  85,  85,  21,  64,   0, 255,   0,  63,   0, 255,   0, 255,
      0,  63,   0, 170,   0, 255,   0,   0,   0,   0,   0,  15,   0,  15,   0,  15,
      0,  31,   0,  15, 132,  56,  39,  62,  80,  61,  15, 192,  32,   0,   0,   0,
      8,   0,   0,   0,   0,   0, 192, 255, 255, 127,   0,   0, 157, 234,  37, 192,
      5,  40,   4,   0,  85,  21,   0,   0,  85,  85,  85,   5,  84,  85,  84,  85,
     85,  85,   0, 106,  85,  40,  69,  85,  85,  61,   3,   0, 255,   0,   0,   0,
    255, 255, 255,   3,   0,   0, 240, 255, 255,  63,   0,   0,   0, 255, 255, 255,
      3,   0,   0, 208, 100, 222,  63,   0,   0,   0, 255, 255, 255,   3,   0,   0,
    176, 231, 223,  31,   0,   0,   0, 123,  95, 252,   1,   0,   0, 240, 255, 255,
     63,   0,   0,   0,   3,   0,   0, 240, 255, 255,  63,   0,   1,   0,   0,   0,
    252, 255, 255,   7,   0,   0,   0, 240, 255, 255,  31,   0, 255,   1,   0,   0,
      0,   4,   0,   0, 255,   3, 255, 255,
};

/* Uppercase: 673 bytes. */

RE_UINT32 re_get_uppercase(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_uppercase_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_uppercase_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_uppercase_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_uppercase_stage_4[pos + f] << 5;
    pos += code;
    value = (re_uppercase_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Cased. */

static RE_UINT8 re_cased_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_cased_stage_2[] = {
     0,  1,  2,  3,  4,  5,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  6,  7,  1,  1,  1,  1,  1,  1,  1,  1,  1,  8,
     9,  1,  1, 10,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 11,  1,  1,  1, 12,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_cased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9, 10,
    11, 12,  6,  6, 13,  6,  6,  6,  6,  6,  6,  6, 14, 15,  6,  6,
     6,  6,  6,  6,  6,  6, 16, 17,  6,  6,  6, 18,  6,  6,  6,  6,
     6,  6,  6, 19,  6,  6,  6, 20,  6,  6,  6,  6, 21,  6,  6,  6,
    22,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 23, 24, 25, 26,
     6, 27,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_cased_stage_4[] = {
     0,  0,  1,  1,  0,  2,  3,  3,  4,  4,  4,  4,  4,  5,  6,  4,
     4,  4,  4,  4,  7,  8,  9, 10,  0,  0, 11, 12, 13, 14,  4, 15,
     4,  4,  4,  4, 16,  4,  4,  4,  4, 17, 18, 19, 20,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  4, 21,  0,
     4,  4,  4,  4,  4,  4,  0,  0,  4,  4,  4,  4,  4,  4,  4,  4,
    22,  4, 23, 24,  4, 25, 26, 27,  0,  0,  0, 28, 29,  0,  0,  0,
    30, 31, 32,  4, 33,  0,  0,  0,  0,  0,  0,  0,  0, 34,  4, 35,
     4, 36, 37,  4,  4,  4,  4, 38,  4, 21,  0,  0,  0,  0,  0,  0,
     0,  0,  4, 39, 24,  0,  0,  0,  0, 40,  4,  4, 41, 42,  0, 43,
     0, 44,  5, 45,  0,  0,  0,  0, 46,  0,  0,  0,  0,  0,  0,  0,
     0,  1,  1,  0,  0,  0,  0,  0,  4,  4, 47,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  4,  4,  0,  4,  4, 48,  4, 49, 50, 51,  4,
    52, 53, 54,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4, 55, 56,  5,
    48, 48, 36, 36, 57, 57, 58,  0,  0, 44, 59, 59, 35,  0,  0,  0,
};

static RE_UINT8 re_cased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 255, 255, 255, 247, 240, 255, 255, 255, 255, 255, 239, 255,
    255, 255, 255,   1,   3,   0,   0,   0,  31,   0,   0,   0,  32,   0,   0,   0,
      0,   0, 207, 188,  64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,
      3, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   0, 254, 255, 255, 255,
    255,   0,   0,   0, 191,  32,   0,   0, 255, 255,  63,  63,  63,  63, 255, 170,
    255, 255, 255,  63, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   2, 128,   0,   0, 255,  31, 132, 252,  47,  62,  80, 189,  31, 242,
    224,  67,   0,   0,  24,   0,   0,   0,   0,   0, 192, 255, 255,   3,   0,   0,
    255, 127, 255, 255, 255, 255, 255, 127,  31, 120,  12,   0, 255,  63,   0,   0,
    252, 255, 255, 255, 255, 120, 255, 255, 255,  63,   3,   0,   0,   0,   0,   7,
      0,   0, 255, 255,  48,   0,   0,   0, 127,   0, 248,   0, 255, 255,   0,   0,
    255, 255, 223, 255, 255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255,
    191, 231, 223, 223, 255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255,
    253, 255, 255, 247, 255, 253, 255, 255, 247,  15,   0,   0, 255,   3, 255, 255,
};

/* Cased: 681 bytes. */

RE_UINT32 re_get_cased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_cased_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_cased_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_cased_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_cased_stage_4[pos + f] << 5;
    pos += code;
    value = (re_cased_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Case_Ignorable. */

static RE_UINT8 re_case_ignorable_stage_1[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 4, 4, 4,
    4, 4,
};

static RE_UINT8 re_case_ignorable_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  8,  9,  7,  7,  7,  7,  7,  7,  7,  7,  7, 10,
    11, 12, 13,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7, 14,  7,  7,
     7,  7,  7,  7,  7,  7,  7, 15,  7,  7, 16,  7,  7, 17,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
    18,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
};

static RE_UINT8 re_case_ignorable_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1,  1, 17,  1,  1,  1, 18, 19, 20, 21, 22, 23, 24,  1, 25,
    26,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 27, 28, 29,  1,
    30,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    31,  1,  1,  1, 32,  1, 33, 34, 35, 36, 37, 38,  1,  1,  1,  1,
     1,  1,  1, 39,  1,  1, 40, 41,  1, 42, 43, 44,  1,  1,  1,  1,
     1,  1, 45,  1,  1,  1,  1,  1, 46, 47, 48, 49, 50, 51, 52,  1,
     1,  1, 53, 54,  1,  1,  1, 55,  1,  1,  1,  1, 56,  1,  1,  1,
     1, 57, 58,  1,  1,  1,  1,  1, 59,  1,  1,  1,  1,  1,  1,  1,
    60, 61,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_case_ignorable_stage_4[] = {
      0,   1,   2,   3,   0,   4,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   5,   6,   6,   6,   6,   6,   7,   8,   0,   0,   0,
      0,   0,   0,   0,   9,   0,   0,   0,   0,   0,  10,   0,  11,  12,  13,  14,
     15,   0,  16,  17,   0,   0,  18,  19,  20,   5,  21,   0,   0,  22,   0,  23,
     24,  25,  26,   0,   0,   0,   0,  27,  28,  29,  30,  31,  32,  33,  34,  35,
     36,  33,  37,  38,  36,  33,  39,  35,  32,  40,  41,  35,  42,   0,  43,   0,
      3,  44,  45,  35,  32,  40,  46,  35,  32,   0,  34,  35,   0,   0,  47,   0,
      0,  48,  49,   0,   0,  50,  51,   0,  52,  53,   0,  54,  55,  56,  57,   0,
      0,  58,  59,  60,  61,   0,   0,  33,   0,   0,  62,   0,   0,   0,   0,   0,
     63,  63,  64,  64,   0,  65,  66,   0,  67,   0,  68,   0,   0,  69,   0,   0,
      0,  70,   0,   0,   0,   0,   0,   0,  71,   0,  72,  73,   0,  74,   0,   0,
     75,  76,  42,  77,  78,  79,   0,  80,   0,  81,   0,  82,   0,   0,  83,  84,
      0,  85,   6,  86,  87,   6,   6,  88,   0,   0,   0,   0,   0,  89,  90,  91,
     92,  93,   0,  94,  95,   0,   5,  96,   0,   0,   0,  97,   0,   0,   0,  98,
      0,   0,   0,  99,   0,   0,   0,   6,   0, 100,   0,   0,   0,   0,   0,   0,
    101, 102,   0,   0, 103,   0,   0, 104, 105,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  82, 106,   0,   0, 107, 108,   0,   0, 109,
      6,  78,   0,  17, 110,   0,   0,  52, 111, 112,   0,   0,   0,   0, 113, 114,
      0, 115, 116,   0,  28, 117, 100, 112,   0, 118, 119, 120,   0, 121, 122, 123,
      0,   0,  87,   0,   0,   0,   0, 124,   2,   0,   0,   0,   0, 125,  78,   0,
    126,  25, 127,   0,   0,   0,   0, 128,   1,   2,   3,  17,  44,   0,   0, 129,
      0,   0,   0,   0,   0,   0,   0, 130,   0,   0,   0,   0,   0,   0,   0,   3,
      0,   0,   0, 131,   0,   0,   0,   0, 132, 133,   0,   0,   0,   0,   0, 112,
     32, 134, 135, 128,  78, 136,   0,   0,  28, 137,   0, 138,  78, 139,   0,   0,
      0, 140,   0,   0,   0,   0, 128, 141,  32,  33,   3, 142,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 143, 144,   0,   0,   0,   0,   0,   0, 145,   3,   0,
      0, 146,   3,   0,   0, 147,   0,   0,   0,   0,   0,   0,   0,   0,   0, 148,
      0, 149,  75,   0,   0,   0,   0,   0,   0,   0,   0,   0, 150,   0,   0,   0,
      0,   0,   0,   0, 151,  75,   0,   0,   0,   0,   0, 152, 153, 154,   0,   0,
      0,   0, 155,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 149,   0,
     32,   6,   6,   6,   0,   0,   0,   0,   6,   6,   6,   6,   6,   6,   6, 156,
};

static RE_UINT8 re_case_ignorable_stage_5[] = {
      0,   0,   0,   0, 128,  64,   0,   4,   0,   0,   0,  64,   1,   0,   0,   0,
      0, 161, 144,   1,   0,   0, 255, 255, 255, 255, 255, 255, 255, 255,  48,   4,
    176,   0,   0,   0, 248,   3,   0,   0,   0,   0,   0,   2,   0,   0, 254, 255,
    255, 255, 255, 191, 182,   0,   0,   0,   0,   0,  16,   0,  63,   0, 255,  23,
      1, 248, 255, 255,   0,   0,   1,   0,   0,   0, 192, 191, 255,  61,   0,   0,
      0, 128,   2,   0, 255,   7,   0,   0, 192, 255,   1,   0,   0, 248,  63,   4,
      0,   0, 192, 255, 255,  63,   0,   0,   0,   0,   0,  14, 240, 255, 255, 255,
      7,   0,   0,   0,   0,   0,   0,  20, 254,  33, 254,   0,  12,   0,   2,   0,
      2,   0,   0,   0,   0,   0,   0,  16,  30,  32,   0,   0,  12,   0,   0,   0,
      6,   0,   0,   0, 134,  57,   2,   0,   0,   0,  35,   0, 190,  33,   0,   0,
      0,   0,   0, 144,  30,  32,  64,   0,   4,   0,   0,   0,   1,  32,   0,   0,
      0,   0,   0, 192, 193,  61,  96,   0,  64,  48,   0,   0,   0,   4,  92,   0,
      0,   0, 242,   7, 192, 127,   0,   0,   0,   0, 242,  27,  64,  63,   0,   0,
      0,   0,   0,   3,   0,   0, 160,   2,   0,   0, 254, 127, 223, 224, 255, 254,
    255, 255, 255,  31,  64,   0,   0,   0,   0, 224, 253, 102,   0,   0,   0, 195,
      1,   0,  30,   0, 100,  32,   0,  32,   0,   0,   0, 224,   0,   0,  28,   0,
      0,   0,  12,   0,   0,   0, 176,  63,  64, 254, 143,  32,   0, 120,   0,   0,
      8,   0,   0,   0,   0,   2,   0,   0, 135,   1,   4,  14,   0,   0, 128,   9,
      0,   0,  64, 127, 229,  31, 248, 159, 128,   0, 255, 127,  15,   0,   0,   0,
      0,   0, 208,  23,   0, 248,  15,   0,   3,   0,   0,   0,  60,  59,   0,   0,
     64, 163,   3,   0,   0, 240, 207,   0,   0,   0,   0,  63,   0,   0, 247, 255,
    253,  33,  16,   3,   0, 240, 255, 255, 255,   7,   0,   1,   0,   0,   0, 248,
    255, 255,  63, 240,   0,   0,   0, 160,   3, 224,   0, 224,   0, 224,   0,  96,
      0, 248,   0,   3, 144, 124,   0,   0, 223, 255,   2, 128,   0,   0, 255,  31,
    255, 255,   1,   0,   0,   0,   0,  48,   0, 128,   3,   0,   0, 128,   0, 128,
      0, 128,   0,   0,  32,   0,   0,   0,   0,  60,  62,   8,   0,   0,   0, 126,
      0,   0,   0, 112,   0,   0,  32,   0,   0,  16,   0,   0,   0, 128, 247, 191,
      0,   0,   0, 176,   0,   0,   3,   0,   0,   7,   0,   0,  68,   8,   0,   0,
     96,   0,   0,   0,  16,   0,   0,   0, 255, 255,   3,   0, 192,  63,   0,   0,
    128, 255,   3,   0,   0,   0, 200,  19,   0, 126, 102,   0,   8,  16,   0,   0,
      0,   0,   1,  16,   0,   0, 157, 193,   2,   0,   0,  32,   0,  48,  88,   0,
     32,  33,   0,   0,   0,   0, 252, 255, 255, 255,   8,   0,   0,   0,  36,   0,
      0,   0,   0, 128,   8,   0,   0,  14,   0,   0,   0,  32,   0,   0, 192,   7,
    110, 240,   0,   0,   0,   0,   0, 135,   0,   0,   0, 255, 127,   0,   0,   0,
      0,   0, 120,  38, 128, 239,  31,   0,   0,   0,   8,   0,   0,   0, 192, 127,
      0, 128, 211,   0, 248,   7,   0,   0, 192,  31,  31,   0,   0,   0, 248, 133,
     13,   0,   0,   0,   0,   0,  60, 176,   0,   0, 248, 167,   0,  40, 191,   0,
      0,   0,  31,   0,   0,   0, 127,   0,   0, 128, 255, 255,   0,   0,   0,  96,
    128,   3, 248, 255, 231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0,
    255, 255,   0,   0,
};

/* Case_Ignorable: 1406 bytes. */

RE_UINT32 re_get_case_ignorable(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_case_ignorable_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_case_ignorable_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_case_ignorable_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_case_ignorable_stage_4[pos + f] << 5;
    pos += code;
    value = (re_case_ignorable_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Changes_When_Lowercased. */

static RE_UINT8 re_changes_when_lowercased_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3,
};

static RE_UINT8 re_changes_when_lowercased_stage_2[] = {
    0, 1, 2, 3, 4, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 7,
    8, 1, 1, 9, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_changes_when_lowercased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9,
     6, 10,  6,  6, 11,  6,  6,  6,  6,  6,  6,  6, 12,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 13, 14,  6,  6,  6,  6,  6,  6,  6, 15,
     6,  6,  6,  6, 16,  6,  6,  6, 17,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_lowercased_stage_4[] = {
     0,  0,  1,  0,  0,  0,  2,  0,  3,  4,  5,  6,  7,  8,  9, 10,
     3, 11, 12,  0,  0,  0,  0,  0,  0,  0,  0, 13, 14, 15, 16, 17,
    18, 19,  0,  3, 20,  3, 21,  3,  3, 22, 23,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18, 24,  0,
     3,  3,  3,  3, 25,  3,  3,  3, 26, 27, 28, 29, 27, 30, 31, 32,
     0, 33,  0, 19, 34,  0,  0,  0,  0,  0,  0,  0,  0, 35, 19,  0,
    18, 36,  0, 37,  3,  3,  3, 38,  0,  0,  3, 39, 40,  0,  0,  0,
     0, 41,  3, 42, 43, 44,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,
    18, 45,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18,  0,  0,
};

static RE_UINT8 re_changes_when_lowercased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7, 255, 255, 127, 127,  85,  85,  85,  85,
     85,  85,  85, 170, 170,  84,  85,  85,  85,  85,  85,  43, 214, 206, 219, 177,
    213, 210, 174,  17, 176, 173, 170,  74,  85,  85, 214,  85,  85,  85,   5, 108,
    122,  85,   0,   0,   0,   0,  69, 128,  64, 215, 254, 255, 251,  15,   0,   0,
      0, 128,   0,  85,  85,  85, 144, 230, 255, 255, 255, 255, 255, 255,   0,   0,
      1,  84,  85,  85, 171,  42,  85,  85,  85,  85, 254, 255, 255, 255, 127,   0,
    191,  32,   0,   0,  85,  85,  21,  64,   0, 255,   0,  63,   0, 255,   0, 255,
      0,  63,   0, 170,   0, 255,   0,   0,   0, 255,   0,  31,   0,  31,   0,  15,
      0,  31,   0,  31,  64,  12,   4,   0,   8,   0,   0,   0,   0,   0, 192, 255,
    255, 127,   0,   0, 157, 234,  37, 192,   5,  40,   4,   0,  85,  21,   0,   0,
     85,  85,  85,   5,  84,  85,  84,  85,  85,  85,   0, 106,  85,  40,  69,  85,
     85,  61,   3,   0, 255,   0,   0,   0,
};

/* Changes_When_Lowercased: 506 bytes. */

RE_UINT32 re_get_changes_when_lowercased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_changes_when_lowercased_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_changes_when_lowercased_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_changes_when_lowercased_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_changes_when_lowercased_stage_4[pos + f] << 5;
    pos += code;
    value = (re_changes_when_lowercased_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Changes_When_Uppercased. */

static RE_UINT8 re_changes_when_uppercased_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3,
};

static RE_UINT8 re_changes_when_uppercased_stage_2[] = {
    0, 1, 1, 2, 3, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6,
    7, 1, 1, 8, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_changes_when_uppercased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  7,  8,  9,  6, 10,  6,  6, 11,  6,  6,  6,
     6,  6,  6,  6, 12, 13,  6,  6,  6,  6,  6,  6,  6,  6, 14, 15,
     6,  6,  6, 16,  6,  6,  6, 17,  6,  6,  6,  6, 18,  6,  6,  6,
    19,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_uppercased_stage_4[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
     5, 13, 14, 15, 16,  0,  0,  0,  0,  0, 17, 18, 19, 20, 21, 22,
     0, 23, 24,  5, 25,  5, 26,  5,  5, 27,  0, 28, 29,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 30,  0,  0,  0,  0,
     5,  5,  5,  5, 31,  5,  5,  5, 32, 33, 34, 35, 24, 36, 37, 38,
     0,  0, 39, 23, 40,  0,  0,  0,  0,  0,  0,  0,  0,  0, 23, 41,
     0, 23, 42, 43,  5,  5,  5, 44, 24, 45,  0,  0,  0,  0,  0,  0,
     0,  0,  5, 46, 47,  0,  0,  0,  0, 48,  5, 49, 50, 51,  0,  0,
    52,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,
     0, 53, 54,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 24,  0,
};

static RE_UINT8 re_changes_when_uppercased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0,   0,   0,   0, 128,
    255, 255, 127, 255, 170, 170, 170, 170, 170, 170, 170,  84,  85, 171, 170, 170,
    170, 170, 170, 212,  41,  17,  36,  70,  42,  33,  81, 162,  96,  91,  85, 181,
    170, 170,  45, 170, 168, 170,  10, 144, 133, 170, 223,  26, 107, 155,  38,  32,
    137,  31,   4,  64,  32,   0,   0,   0,   0,   0, 138,  56,   0,   0,   1,   0,
      0, 240, 255, 255, 255, 127, 227, 170, 170, 170,  47,   9,   0,   0, 255, 255,
    255, 255, 255, 255,   2, 168, 170, 170,  84, 213, 170, 170, 170, 170,   0,   0,
    254, 255, 255, 255, 255,   0,   0,   0,   0,   0,   0,  34, 170, 170, 234,  15,
    255,   0,  63,   0, 255,   0, 255,   0,  63,   0, 255,   0, 255,   0, 255,  63,
    255, 255, 223,  80, 220,  16, 207,   0, 255,   0, 220,  16,   0,  64,   0,   0,
     16,   0,   0,   0, 255,   3,   0,   0, 255, 255, 255, 127,  98,  21,  72,   0,
     10,  80,   8,   0, 191,  32,   0,   0, 170,  42,   0,   0, 170, 170, 170,  10,
    168, 170, 168, 170, 170, 170,   0, 148, 170,  16, 138, 170, 170,   2,   0,   0,
    127,   0, 248,   0,   0, 255, 255, 255, 255, 255,   0,   0,
};

/* Changes_When_Uppercased: 550 bytes. */

RE_UINT32 re_get_changes_when_uppercased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_changes_when_uppercased_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_changes_when_uppercased_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_changes_when_uppercased_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_changes_when_uppercased_stage_4[pos + f] << 5;
    pos += code;
    value = (re_changes_when_uppercased_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Changes_When_Titlecased. */

static RE_UINT8 re_changes_when_titlecased_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3,
};

static RE_UINT8 re_changes_when_titlecased_stage_2[] = {
    0, 1, 1, 2, 3, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6,
    7, 1, 1, 8, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_changes_when_titlecased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  7,  8,  9,  6, 10,  6,  6, 11,  6,  6,  6,
     6,  6,  6,  6, 12, 13,  6,  6,  6,  6,  6,  6,  6,  6, 14, 15,
     6,  6,  6, 16,  6,  6,  6, 17,  6,  6,  6,  6, 18,  6,  6,  6,
    19,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_titlecased_stage_4[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
     5, 13, 14, 15, 16,  0,  0,  0,  0,  0, 17, 18, 19, 20, 21, 22,
     0, 23, 24,  5, 25,  5, 26,  5,  5, 27,  0, 28, 29,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 30,  0,  0,  0,  0,
     5,  5,  5,  5, 31,  5,  5,  5, 32, 33, 34, 35, 33, 36, 37, 38,
     0,  0, 39, 23, 40,  0,  0,  0,  0,  0,  0,  0,  0,  0, 23, 41,
     0, 23, 42, 43,  5,  5,  5, 44, 24, 45,  0,  0,  0,  0,  0,  0,
     0,  0,  5, 46, 47,  0,  0,  0,  0, 48,  5, 49, 50, 51,  0,  0,
    52,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,
     0, 53, 54,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 24,  0,
};

static RE_UINT8 re_changes_when_titlecased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0,   0,   0,   0, 128,
    255, 255, 127, 255, 170, 170, 170, 170, 170, 170, 170,  84,  85, 171, 170, 170,
    170, 170, 170, 212,  41,  17,  36,  70,  42,  33,  81, 162, 208,  86,  85, 181,
    170, 170,  43, 170, 168, 170,  10, 144, 133, 170, 223,  26, 107, 155,  38,  32,
    137,  31,   4,  64,  32,   0,   0,   0,   0,   0, 138,  56,   0,   0,   1,   0,
      0, 240, 255, 255, 255, 127, 227, 170, 170, 170,  47,   9,   0,   0, 255, 255,
    255, 255, 255, 255,   2, 168, 170, 170,  84, 213, 170, 170, 170, 170,   0,   0,
    254, 255, 255, 255, 255,   0,   0,   0,   0,   0,   0,  34, 170, 170, 234,  15,
    255,   0,  63,   0, 255,   0, 255,   0,  63,   0, 255,   0, 255,   0, 255,  63,
    255,   0, 223,  64, 220,   0, 207,   0, 255,   0, 220,   0,   0,  64,   0,   0,
     16,   0,   0,   0, 255,   3,   0,   0, 255, 255, 255, 127,  98,  21,  72,   0,
     10,  80,   8,   0, 191,  32,   0,   0, 170,  42,   0,   0, 170, 170, 170,  10,
    168, 170, 168, 170, 170, 170,   0, 148, 170,  16, 138, 170, 170,   2,   0,   0,
    127,   0, 248,   0,   0, 255, 255, 255, 255, 255,   0,   0,
};

/* Changes_When_Titlecased: 550 bytes. */

RE_UINT32 re_get_changes_when_titlecased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_changes_when_titlecased_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_changes_when_titlecased_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_changes_when_titlecased_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_changes_when_titlecased_stage_4[pos + f] << 5;
    pos += code;
    value = (re_changes_when_titlecased_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Changes_When_Casefolded. */

static RE_UINT8 re_changes_when_casefolded_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3,
};

static RE_UINT8 re_changes_when_casefolded_stage_2[] = {
    0, 1, 2, 3, 4, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 7,
    8, 1, 1, 9, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_changes_when_casefolded_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9,
     6, 10,  6,  6, 11,  6,  6,  6,  6,  6,  6,  6, 12,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 13, 14,  6,  6,  6, 15,  6,  6,  6, 16,
     6,  6,  6,  6, 17,  6,  6,  6, 18,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_casefolded_stage_4[] = {
     0,  0,  1,  0,  0,  2,  3,  0,  4,  5,  6,  7,  8,  9, 10, 11,
     4, 12, 13,  0,  0,  0,  0,  0,  0,  0, 14, 15, 16, 17, 18, 19,
    20, 21,  0,  4, 22,  4, 23,  4,  4, 24, 25,  0, 26,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 20, 27,  0,
     4,  4,  4,  4, 28,  4,  4,  4, 29, 30, 31, 32, 20, 33, 34, 35,
     0, 36,  0, 21, 37,  0,  0,  0,  0,  0,  0,  0,  0, 38, 21,  0,
    20, 39,  0, 40,  4,  4,  4, 41,  0,  0,  4, 42, 43,  0,  0,  0,
     0, 44,  4, 45, 46, 47,  0,  0, 48,  0,  0,  0,  0,  0,  0,  0,
     0,  1,  0,  0,  0,  0,  0,  0, 20, 49,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 20,  0,  0,
};

static RE_UINT8 re_changes_when_casefolded_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0, 255, 255, 127, 255,
     85,  85,  85,  85,  85,  85,  85, 170, 170,  86,  85,  85,  85,  85,  85, 171,
    214, 206, 219, 177, 213, 210, 174,  17, 176, 173, 170,  74,  85,  85, 214,  85,
     85,  85,   5, 108, 122,  85,   0,   0,  32,   0,   0,   0,   0,   0,  69, 128,
     64, 215, 254, 255, 251,  15,   0,   0,   4, 128,  99,  85,  85,  85, 179, 230,
    255, 255, 255, 255, 255, 255,   0,   0,   1,  84,  85,  85, 171,  42,  85,  85,
     85,  85, 254, 255, 255, 255, 127,   0, 128,   0,   0,   0, 191,  32,   0,   0,
     85,  85,  21,  76,   0, 255,   0,  63,   0, 255,   0, 255,   0,  63,   0, 170,
      0, 255,   0,   0, 255, 255, 156,  31, 156,  31,   0,  15,   0,  31, 156,  31,
     64,  12,   4,   0,   8,   0,   0,   0,   0,   0, 192, 255, 255, 127,   0,   0,
    157, 234,  37, 192,   5,  40,   4,   0,  85,  21,   0,   0,  85,  85,  85,   5,
     84,  85,  84,  85,  85,  85,   0, 106,  85,  40,  69,  85,  85,  61,   3,   0,
    127,   0, 248,   0, 255,   0,   0,   0,
};

/* Changes_When_Casefolded: 530 bytes. */

RE_UINT32 re_get_changes_when_casefolded(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_changes_when_casefolded_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_changes_when_casefolded_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_changes_when_casefolded_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_changes_when_casefolded_stage_4[pos + f] << 5;
    pos += code;
    value = (re_changes_when_casefolded_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Changes_When_Casemapped. */

static RE_UINT8 re_changes_when_casemapped_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3,
};

static RE_UINT8 re_changes_when_casemapped_stage_2[] = {
    0, 1, 2, 3, 4, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 7,
    8, 1, 1, 9, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_changes_when_casemapped_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9, 10,
     6, 11,  6,  6, 12,  6,  6,  6,  6,  6,  6,  6, 13, 14,  6,  6,
     6,  6,  6,  6,  6,  6, 15, 16,  6,  6,  6, 17,  6,  6,  6, 18,
     6,  6,  6,  6, 19,  6,  6,  6, 20,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_casemapped_stage_4[] = {
     0,  0,  1,  1,  0,  2,  3,  3,  4,  5,  4,  4,  6,  7,  8,  4,
     4,  9, 10, 11, 12,  0,  0,  0,  0,  0, 13, 14, 15, 16, 17, 18,
     4,  4,  4,  4, 19,  4,  4,  4,  4, 20, 21, 22, 23,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  4, 24,  0,
     0,  0,  0, 25,  0,  0,  0,  0,  4,  4,  4,  4, 26,  4,  4,  4,
    27,  4, 28, 29,  4, 30, 31, 32,  0, 33, 34,  4, 35,  0,  0,  0,
     0,  0,  0,  0,  0, 36,  4, 37,  4, 38, 39, 40,  4,  4,  4, 41,
     4, 24,  0,  0,  0,  0,  0,  0,  0,  0,  4, 42, 43,  0,  0,  0,
     0, 44,  4, 45, 46, 47,  0,  0, 48,  0,  0,  0,  0,  0,  0,  0,
     0,  1,  1,  0,  0,  0,  0,  0,  4,  4, 49,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  4,  4,  0,
};

static RE_UINT8 re_changes_when_casemapped_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0, 255, 255, 127, 255,
    255, 255, 255, 255, 255, 255, 255, 254, 255, 223, 255, 247, 255, 243, 255, 179,
    240, 255, 255, 255, 253, 255,  15, 252, 255, 255, 223,  26, 107, 155,  38,  32,
    137,  31,   4,  64,  32,   0,   0,   0,   0,   0, 207, 184,  64, 215, 255, 255,
    251, 255, 255, 255, 255, 255, 227, 255, 255, 255, 191, 239,   3, 252, 255, 255,
    255, 255, 254, 255, 255, 255, 127,   0, 254, 255, 255, 255, 255,   0,   0,   0,
    191,  32,   0,   0,   0,   0,   0,  34, 255, 255, 255,  79, 255, 255,  63,  63,
     63,  63, 255, 170, 255, 255, 255,  63, 255, 255, 223,  95, 220,  31, 207,  15,
    255,  31, 220,  31,  64,  12,   4,   0,   0,  64,   0,   0,  24,   0,   0,   0,
      0,   0, 192, 255, 255,   3,   0,   0, 255, 127, 255, 255, 255, 255, 255, 127,
    255, 255, 109, 192,  15, 120,  12,   0, 255,  63,   0,   0, 255, 255, 255,  15,
    252, 255, 252, 255, 255, 255,   0, 254, 255,  56, 207, 255, 255,  63,   3,   0,
    127,   0, 248,   0, 255, 255,   0,   0,
};

/* Changes_When_Casemapped: 546 bytes. */

RE_UINT32 re_get_changes_when_casemapped(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_changes_when_casemapped_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_changes_when_casemapped_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_changes_when_casemapped_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_changes_when_casemapped_stage_4[pos + f] << 5;
    pos += code;
    value = (re_changes_when_casemapped_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* ID_Start. */

static RE_UINT8 re_id_start_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3,
};

static RE_UINT8 re_id_start_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 26,  7, 27, 28, 13, 13, 13, 13, 13, 13, 13, 29,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_id_start_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 32, 33, 31, 31,
    34, 35, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 36,  1,  1,  1,  1,  1,  1,  1,  1,  1, 37,
     1,  1,  1,  1, 38,  1, 39, 40, 41, 42, 43, 44,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 45, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 46, 47,  1, 48, 49, 50, 51, 52, 53, 54, 55, 56,  1, 57,
    58, 59, 60, 61, 62, 31, 31, 31, 63, 64, 65, 66, 67, 68, 69, 31,
    70, 31, 71, 31, 31, 31, 31, 31,  1,  1,  1, 72, 73, 31, 31, 31,
     1,  1,  1,  1, 74, 31, 31, 31,  1,  1, 75, 76, 31, 31, 31, 77,
    78, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 79, 31, 31, 31,
    31, 31, 31, 31, 80, 81, 82, 83, 84, 31, 31, 31, 31, 31, 85, 31,
     1,  1,  1,  1,  1,  1, 86,  1,  1,  1,  1,  1,  1,  1,  1, 87,
    88, 31, 31, 31, 31, 31, 31, 31,  1,  1, 88, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_id_start_stage_4[] = {
      0,   0,   1,   1,   0,   2,   3,   3,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   5,   6,   0,   0,   0,   7,   8,   9,   4,  10,
      4,   4,   4,   4,  11,   4,   4,   4,   4,  12,  13,  14,  15,   0,  16,  17,
      0,   4,  18,  19,   4,   4,  20,  21,  22,  23,  24,   4,   4,  25,  26,  27,
     28,  29,  30,   0,   0,  31,   0,   0,  32,  33,  34,  35,  36,  37,  38,  39,
     40,  41,  42,  43,  44,  45,  46,  47,  48,  45,  49,  50,  51,  52,  46,   0,
     53,  54,  55,  47,  53,  56,  57,  58,  53,  59,  60,  61,  62,  63,  64,   0,
     14,  65,  64,   0,  66,  67,  68,   0,  69,   0,  70,  71,  72,   0,   0,   0,
      4,  73,  74,  75,  76,   4,  77,  78,   4,   4,  79,   4,  80,  81,  82,   4,
     83,   4,  84,   0,  23,   4,   4,  85,  14,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,  86,   1,   4,   4,  87,  88,  89,  89,  90,   4,  91,  92,   0,
      0,   4,   4,  93,   4,  94,   4,  95,  96,   0,  16,  97,   4,  98,  99,   0,
    100,   4,  85,   0,   0, 101,   0,   0, 102,  91, 103,   0, 104, 105,   4, 106,
      4, 107, 108, 109,   0,   0,   0, 110,   4,   4,   4,   4,   4,   4,   0,   0,
    111,   4, 112, 109,   4, 113, 114, 115,   0,   0,   0, 116, 117,   0,   0,   0,
    118, 119, 120,   4, 121,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      4, 122,  96,   4,   4,   4,   4, 123,   4,  77,   4, 124, 100, 125, 125,   0,
    126, 127,  14,   4, 128,  14,   4,  78, 102, 129,   4,   4, 130,  84,   0,  16,
      4,   4,   4,   4,   4,  95,   0,   0,   4,   4,   4,   4,   4,   4,  71,   0,
      4,   4,   4,   4,  71,   0,  16, 109, 131, 132,   4, 133, 109,   4,   4,  23,
    134, 135,   4,   4, 136, 137,   0, 134, 138, 139,   4,  91, 135,  91,   0, 140,
     26, 141,  64, 142,  32,  31, 143, 144,   4, 121, 145, 146,   4, 147, 148, 149,
    150, 151,  78, 152,   0,   0,   4, 139,   4,   4,   4,   4,   4, 153, 154, 155,
      4,   4,   4, 156,   4,   4, 157,   0, 158, 159, 160,   4,   4,  89, 161,   4,
      4, 109,  16,   4, 162,   4,  15, 163,   0,   0,   0, 164,   4,   4,   4, 142,
      0,   1,   1, 165,   4,  96, 166,   0, 167, 168, 169,   0,   4,   4,   4,  84,
      0,   0,   4,  85,   0,   0,   0,   0,   0,   0,   0,   0, 142,   4, 170,   0,
      4,  16, 171,  95, 109,   4, 172,   0,   4,   4,   4,   4, 109,   0,   0,   0,
      4, 173,   4, 107,   0,   0,   0,   0,   4, 100,  95,  15,   0,   0,   0,   0,
    174, 175,  95, 100,  96,   0,   0,   0,  95, 157,   0,   0,   4, 176,   0,   0,
    177,  91,   0, 142, 142,   0,  70, 178,   4,  95,  95,  31,  89,   0,   0,   0,
      4,   4, 121,   0,   0,   0,   0,   0, 104,  93,   0,   0, 104,  23,  16, 121,
    104,  64,  16, 179, 104,  31, 180,   0, 181,  98,   0,   0,   0,  16,  96,   0,
     48,  45, 182,  47,   0,   0,   0,   0,   0,   0,   0,   0,   4,  23, 183,   0,
      0,   0,   0,   0,   4, 130,   0,   0,   4,  23, 184,   0,   4,  18,   0,   0,
      0,   0,   0,   0,   0,   4,   4, 185,   0,   0,   0,   0,   0,   0,   4,  30,
      4,   4,   4,   4,  30,   0,   0,   0,   4,   4,   4, 130,   0,   0,   0,   0,
      4, 130,   0,   0,   0,   0,   0,   0,   4,  30,  96,   0,   0,   0,  16, 186,
      4,  23, 107, 187,  23,   0,   0,   0,   4,   4, 188,   0, 161,   0,   0,   0,
     47,   0,   0,   0,   0,   0,   0,   0,   4,   4,   4, 189, 190,   0,   0,   0,
      4,   4, 191,   4, 192, 193, 194,   4, 195, 196, 197,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4, 198, 199,  78, 191, 191, 122, 122, 200, 200, 145,   0,
      4,   4,   4,   4,   4,   4, 178,   0, 194, 201, 202, 203, 204, 205,   0,   0,
      4,   4,   4,   4,   4,   4, 100,   0,   4,  85,   4,   4,   4,   4,   4,   4,
    109,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_id_start_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,   0,   0, 223, 188,
     64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,   3, 252, 255, 255,
    255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255, 255,   0,   0,   0,
      0,   0, 255, 255, 255,   7,   7,   0, 255,   7,   0,   0,   0, 192, 254, 255,
    255, 255,  47,   0,  96, 192,   0, 156,   0,   0, 253, 255, 255, 255,   0,   0,
      0, 224, 255, 255,  63,   0,   2,   0,   0, 252, 255, 255, 255,   7,  48,   4,
    255, 255,  63,   4,  16,   1,   0,   0, 255, 255, 255,   1, 255, 255,   7,   0,
    240, 255, 255, 255, 255, 255, 255,  35,   0,   0,   1, 255,   3,   0, 254, 255,
    225, 159, 249, 255, 255, 253, 197,  35,   0,  64,   0, 176,   3,   0,   3,   0,
    224, 135, 249, 255, 255, 253, 109,   3,   0,   0,   0,  94,   0,   0,  28,   0,
    224, 191, 251, 255, 255, 253, 237,  35,   0,   0,   1,   0,   3,   0,   0,   0,
    224, 159, 249, 255,   0,   0,   0, 176,   3,   0,   2,   0, 232, 199,  61, 214,
     24, 199, 255,   3, 224, 223, 253, 255, 255, 253, 255,  35,   0,   0,   0,   3,
    255, 253, 239,  35,   0,   0,   0,  64,   3,   0,   6,   0, 255, 255, 255,  39,
      0,  64,   0,   0,   3,   0,   0, 252, 224, 255, 127, 252, 255, 255, 251,  47,
    127,   0,   0,   0, 255, 255,  13,   0, 150,  37, 240, 254, 174, 236,  13,  32,
     95,   0,   0, 240,   1,   0,   0,   0, 255, 254, 255, 255, 255,  31,   0,   0,
      0,  31,   0,   0, 255,   7,   0, 128,   0,   0,  63,  60,  98, 192, 225, 255,
      3,  64,   0,   0, 191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61,
    255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255,
    255, 255, 255,   7, 255, 255,  31,   0, 255, 159, 255, 255, 255, 199, 255,   1,
    255, 223,   3,   0, 255, 255,   3,   0, 255, 223,   1,   0, 255, 255,  15,   0,
      0,   0, 128,  16, 255, 255, 255,   0, 255,   5, 255, 255, 255, 255,  63,   0,
    255, 255, 255, 127, 255,  63,  31,   0, 255,  15,   0,   0, 254,   0,   0,   0,
    255, 255, 127,   0, 128,   0,   0,   0, 224, 255, 255, 255, 224,  15,   0,   0,
    248, 255, 255, 255,   1, 192,   0, 252,  63,   0,   0,   0,  15,   0,   0,   0,
      0, 224,   0, 252, 255, 255, 255,  63,   0, 222,  99,   0, 255, 255,  63,  63,
     63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   2, 128,   0,   0, 255,  31, 132, 252,  47,  63,  80, 253, 255, 243,
    224,  67,   0,   0, 255,   1,   0,   0, 255, 127, 255, 255,  31, 120,  12,   0,
    255, 128,   0,   0, 127, 127, 127, 127, 224,   0,   0,   0, 254,   3,  62,  31,
    255, 255, 127, 248, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31, 255, 255,
      0,  12,   0,   0, 255, 127,   0, 128,   0,   0, 128, 255, 252, 255, 255, 255,
    255, 121, 255, 255, 255,  63,   3,   0, 187, 247, 255, 255,   7,   0,   0,   0,
      0,   0, 252,   8,  63,   0, 255, 255, 255, 255, 255,  31,   0, 128,   0,   0,
    223, 255,   0, 124, 247,  15,   0,   0, 255, 255, 127, 196, 255, 255,  98,  62,
      5,   0,   0,  56, 255,   7,  28,   0, 126, 126, 126,   0, 127, 127, 255, 255,
     48,   0,   0,   0,  15,   0, 255, 255, 127, 248, 255, 255, 255, 255, 255,  15,
    255,  63, 255, 255, 255, 255, 255,   3, 127,   0, 248, 160, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,
      0,   0, 223, 255, 192, 255, 255, 255, 252, 252, 252,  28, 255, 239, 255, 255,
    127, 255, 255, 183, 255,  63, 255,  63, 255, 255,   1,   0, 255,   7, 255, 255,
     15, 255,  62,   0, 255,   0, 255, 255,  63, 253, 255, 255, 255, 255, 191, 145,
    255, 255, 255, 192,   1,   0, 239, 254,  31,   0,   0,   0, 255, 255,  71,   0,
     30,   0,   0,   4, 255, 255, 251, 255,   0,   0,   0, 224, 176,   0,   0,   0,
     16,   0,   0,   0,   0,   0,   0, 128, 255,  63,   0,   0, 248, 255, 255, 224,
     31,   0,   1,   0, 255,   7, 255,  31, 255,   1, 255,   3, 255, 255, 223, 255,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    255, 253, 255, 255, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94,
    255, 251, 255,  15, 238, 251, 255,  15,
};

/* ID_Start: 1921 bytes. */

RE_UINT32 re_get_id_start(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_id_start_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_id_start_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_id_start_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_id_start_stage_4[pos + f] << 5;
    pos += code;
    value = (re_id_start_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* ID_Continue. */

static RE_UINT8 re_id_continue_stage_1[] = {
    0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6, 6,
    6, 6,
};

static RE_UINT8 re_id_continue_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 26,  7, 27, 28, 13, 13, 13, 13, 13, 13, 13, 29,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    30, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_id_continue_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 32, 33, 31, 31,
    34, 35, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 36,  1,  1,  1,  1,  1,  1,  1,  1,  1, 37,
     1,  1,  1,  1, 38,  1, 39, 40, 41, 42, 43, 44,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 45, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 46, 47,  1, 48, 49, 50, 51, 52, 53, 54, 55, 56,  1, 57,
    58, 59, 60, 61, 62, 31, 31, 31, 63, 64, 65, 66, 67, 68, 69, 31,
    70, 31, 71, 31, 31, 31, 31, 31,  1,  1,  1, 72, 73, 31, 31, 31,
     1,  1,  1,  1, 74, 31, 31, 31,  1,  1, 75, 76, 31, 31, 31, 77,
    78, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 79, 31, 31, 31,
    31, 80, 81, 31, 82, 83, 84, 85, 86, 31, 31, 31, 31, 31, 87, 31,
     1,  1,  1,  1,  1,  1, 88,  1,  1,  1,  1,  1,  1,  1,  1, 89,
    90, 31, 31, 31, 31, 31, 31, 31,  1,  1, 90, 31, 31, 31, 31, 31,
    31, 91, 31, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_id_continue_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   7,   8,   6,   6,   6,   9,  10,  11,   6,  12,
      6,   6,   6,   6,  13,   6,   6,   6,   6,  14,  15,  16,  17,  18,  19,  20,
     21,   6,   6,  22,   6,   6,  23,  24,  25,   6,  26,   6,   6,  27,   6,  28,
      6,  29,  30,   0,   0,  31,   0,  32,   6,   6,   6,  33,  34,  35,  36,  37,
     38,  39,  40,  41,  42,  43,  44,  45,  46,  43,  47,  48,  49,  50,  51,  52,
     53,  54,  55,  45,  56,  57,  58,  59,  56,  60,  61,  62,  63,  64,  65,  66,
     16,  67,  68,   0,  69,  70,  71,   0,  72,  73,  74,  75,  76,  77,  78,   0,
      6,   6,  79,   6,  80,   6,  81,  82,   6,   6,  83,   6,  84,  85,  86,   6,
     87,   6,  60,  88,  89,   6,   6,  90,  16,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,  91,   3,   6,   6,  92,  93,  90,  94,  95,   6,   6,  96,  97,
     98,   6,   6,  99,   6, 100,   6, 101, 102, 103, 104, 105,   6, 106, 107,   0,
     30,   6, 102, 108, 109, 110,   0,   0,   6,   6, 111, 112,   6,   6,   6,  94,
      6,  99, 113,  80,   0,   0, 114, 115,   6,   6,   6,   6,   6,   6,   6, 116,
    117,   6, 118,  80,   6, 119, 120, 121,   0, 122, 123, 124, 125,   0, 125, 126,
    127, 128, 129,   6, 130,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6, 131, 102,   6,   6,   6,   6, 132,   6,  81,   6, 133, 134, 135, 135,   6,
    136, 137,  16,   6, 138,  16,   6,  82, 139, 140,   6,   6, 141,  67,   0,  25,
      6,   6,   6,   6,   6, 101,   0,   0,   6,   6,   6,   6,   6,   6, 142,   0,
      6,   6,   6,   6, 142,   0,  25,  80, 143, 144,   6, 145,  18,   6,   6,  27,
    146, 147,   6,   6, 148, 149,   0, 146,   6, 150,   6,  94,   6,   6, 151, 152,
      6, 153,  94,  77,   6,   6, 154, 102,   6, 134, 155, 156,   6,   6, 157, 158,
    159, 160,  82, 161,   0,   0,   6, 162,   6,   6,   6,   6,   6, 163, 164,  30,
      6,   6,   6, 153,   6,   6, 165,   0, 166, 167, 168,   6,   6,  27, 169,   6,
      6,  80,  25,   6, 170,   6, 150, 171,  89, 172, 173, 174,   6,   6,   6,  77,
      1,   2,   3, 104,   6, 102, 175,   0, 176, 177, 178,   0,   6,   6,   6,  67,
      0,   0,   6,  90,   0,   0,   0, 179,   0,   0,   0,   0,  77,   6, 180, 181,
      6,  25, 100,  67,  80,   6, 182,   0,   6,   6,   6,   6,  80,  97,   0,   0,
      6, 183,   6, 184,   0,   0,   0,   0,   6, 134, 101, 150,   0,   0,   0,   0,
    185, 186, 101, 134, 102,   0,   0,   0, 101, 165,   0,   0,   6, 187,   0,   0,
    188, 189,   0,  77,  77,   0,  74, 190,   6, 101, 101,  31,  27,   0,   0,   0,
      6,   6, 130,   0,   0,   0,   0,   0,   6,   6, 190, 191,   6,  67,  25, 192,
      6, 193,  25, 194,   6,   6, 195,   0, 196,  99,   0,   0,   0,  25,   6, 197,
     46,  43, 198, 199,   0,   0,   0,   0,   0,   0,   0,   0,   6,   6, 200,   0,
      0,   0,   0,   0,   6, 201, 181,   0,   6,   6, 202,   0,   6,  99,  97,   0,
      0,   0,   0,   0,   0,   6,   6, 203,   0,   0,   0,   0,   0,   0,   6, 204,
      6,   6,   6,   6, 204,   0,   0,   0,   6,   6,   6, 141,   0,   0,   0,   0,
      6, 141,   0,   0,   0,   0,   0,   0,   6, 204, 102,  97,   0,   0,  25, 105,
      6, 134, 205, 206,  89,   0,   0,   0,   6,   6, 207, 102, 208,   0,   0,   0,
    209,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6, 210, 211,   0,   0,   0,
      0,   0,   0, 212, 213, 214,   0,   0,   0,   0, 215,   0,   0,   0,   0,   0,
      6,   6, 193,   6, 216, 217, 218,   6, 219, 220, 221,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6, 222, 223,  82, 193, 193, 131, 131, 224, 224, 225,   6,
      6,   6,   6,   6,   6,   6, 226,   0, 218, 227, 228, 229, 230, 231,   0,   0,
      6,   6,   6,   6,   6,   6, 134,   0,   6,  90,   6,   6,   6,   6,   6,   6,
     80,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6,   6,   6,   6,   6,  89,
};

static RE_UINT8 re_id_continue_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255, 135, 254, 255, 255,   7,
      0,   4, 160,   4, 255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,
     31,  80,   0,   0, 255, 255, 223, 188, 192, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255, 251, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2,
    254, 255, 255, 255, 255,   0, 254, 255, 255, 255, 255, 191, 182,   0, 255, 255,
    255,   7,   7,   0,   0,   0, 255,   7, 255, 195, 255, 255, 255, 255, 239, 159,
    255, 253, 255, 159,   0,   0, 255, 255, 255, 231, 255, 255, 255, 255,   3,   0,
    255, 255,  63,   4, 255,  63,   0,   0, 255, 255, 255,  15, 255, 255,   7,   0,
    240, 255, 255, 255, 207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 211,
    135,  57,   2,  94, 192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 243,
    191,  59,   1,   0, 207, 255,   0,   0, 238, 159, 249, 255, 159,  57, 192, 176,
    207, 255,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0,
    192, 255,   0,   0, 239, 223, 253, 255, 255, 253, 255, 227, 223,  61,  96,   3,
    238, 223, 253, 255, 255, 253, 239, 243, 223,  61,  96,  64, 207, 255,   6,   0,
    255, 255, 255, 231, 223, 125, 128,   0, 207, 255,   0, 252, 236, 255, 127, 252,
    255, 255, 251,  47, 127, 132,  95, 255, 192, 255,  12,   0, 255, 255, 255,   7,
    255, 127, 255,   3, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63, 255, 243,
      1,   0,   0,   3, 255,   3, 160, 194, 255, 254, 255, 255, 255,  31, 254, 255,
    223, 255, 255, 254, 255, 255, 255,  31,  64,   0,   0,   0, 255,   3, 255, 255,
    255, 255, 255,  63, 191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61,
    255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255,
      0, 254,   3,   0, 255, 255,   0,   0, 255, 255,  31,   0, 255, 159, 255, 255,
    255, 199, 255,   1, 255, 223,  31,   0, 255, 255,  15,   0, 255, 223,  13,   0,
    255, 255, 143,  48, 255,   3,   0,   0,   0,  56, 255,   3, 255, 255, 255,   0,
    255,   7, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  15, 255,  15,
    192, 255, 255, 255, 255,  63,  31,   0, 255,  15, 255, 255, 255,   3, 255,   7,
    255, 255, 255, 159, 255,   3, 255,   3, 128,   0, 255,  63, 255,  15, 255,   3,
      0, 248,  15,   0, 255, 227, 255, 255,   0,   0, 247, 255, 255, 255, 127,   3,
    255, 255,  63, 240, 255, 255,  63,  63,  63,  63, 255, 170, 255, 255, 223,  95,
    220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   0, 128,   1,   0,  16,   0,
      0,   0,   2, 128,   0,   0, 255,  31, 226, 255,   1,   0, 132, 252,  47,  63,
     80, 253, 255, 243, 224,  67,   0,   0, 255,   1,   0,   0, 255, 127, 255, 255,
     31, 248,  15,   0, 255, 128,   0, 128, 255, 255, 127,   0, 127, 127, 127, 127,
    224,   0,   0,   0, 254, 255,  62,  31, 255, 255, 127, 254, 224, 255, 255, 255,
    255,  63, 254, 255, 255, 127,   0,   0, 255,  31,   0,   0, 255,  31, 255, 255,
    255,  15,   0,   0, 255, 255, 240, 191,   0,   0, 128, 255, 252, 255, 255, 255,
    255, 121, 255, 255, 255,  63,   3,   0, 255,   0,   0,   0,  31,   0, 255,   3,
    255, 255, 255,   8, 255,  63, 255, 255,   1, 128, 255,   3, 255,  63, 255,   3,
    255, 255, 127, 252,   7,   0,   0,  56, 255, 255, 124,   0, 126, 126, 126,   0,
    127, 127, 255, 255,  48,   0,   0,   0, 255,  55, 255,   3,  15,   0, 255, 255,
    127, 248, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,
    255,  63,  24,   0,   0, 224,   0,   0,   0,   0, 223, 255, 252, 252, 252,  28,
    255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,   0,   0,   0,  32,
    255, 255,   1,   0,   1,   0,   0,   0,  15, 255,  62,   0, 255,   0, 255, 255,
     15,   0,   0,   0,  63, 253, 255, 255, 255, 255, 191, 145, 255, 255, 255, 192,
    111, 240, 239, 254, 255, 255,  15, 135, 127,   0,   0,   0, 192, 255,   0, 128,
    255,   1, 255,   3, 255, 255, 223, 255, 255, 255,  79,   0,  31,   0, 255,   7,
    255, 255, 251, 255, 255,   7, 255,   3, 159,  57, 128, 224, 207,  31,  31,   0,
    191,   0, 255,   3, 255, 255,  63, 255,  17,   0, 255,   3, 255,   3,   0, 128,
    255, 255, 255,   1,  15,   0, 255,   3, 248, 255, 255, 224,  31,   0, 255, 255,
      0, 128, 255, 255,   3,   0,   0,   0, 255,   7, 255,  31, 255,   1, 255,  99,
    224, 227,   7, 248, 231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    255, 253, 255, 255, 247, 207, 255, 255,  31,   0, 127,   0, 150, 254, 247,  10,
    132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
};

/* ID_Continue: 2074 bytes. */

RE_UINT32 re_get_id_continue(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_id_continue_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_id_continue_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_id_continue_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_id_continue_stage_4[pos + f] << 5;
    pos += code;
    value = (re_id_continue_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* XID_Start. */

static RE_UINT8 re_xid_start_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3,
};

static RE_UINT8 re_xid_start_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 26,  7, 27, 28, 13, 13, 13, 13, 13, 13, 13, 29,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_xid_start_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 32, 33, 31, 31,
    34, 35, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 36,  1,  1,  1,  1,  1,  1,  1,  1,  1, 37,
     1,  1,  1,  1, 38,  1, 39, 40, 41, 42, 43, 44,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 45, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,  1, 58,
    59, 60, 61, 62, 63, 31, 31, 31, 64, 65, 66, 67, 68, 69, 70, 31,
    71, 31, 72, 31, 31, 31, 31, 31,  1,  1,  1, 73, 74, 31, 31, 31,
     1,  1,  1,  1, 75, 31, 31, 31,  1,  1, 76, 77, 31, 31, 31, 78,
    79, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 80, 31, 31, 31,
    31, 31, 31, 31, 81, 82, 83, 84, 85, 31, 31, 31, 31, 31, 86, 31,
     1,  1,  1,  1,  1,  1, 87,  1,  1,  1,  1,  1,  1,  1,  1, 88,
    89, 31, 31, 31, 31, 31, 31, 31,  1,  1, 89, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_xid_start_stage_4[] = {
      0,   0,   1,   1,   0,   2,   3,   3,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   5,   6,   0,   0,   0,   7,   8,   9,   4,  10,
      4,   4,   4,   4,  11,   4,   4,   4,   4,  12,  13,  14,  15,   0,  16,  17,
      0,   4,  18,  19,   4,   4,  20,  21,  22,  23,  24,   4,   4,  25,  26,  27,
     28,  29,  30,   0,   0,  31,   0,   0,  32,  33,  34,  35,  36,  37,  38,  39,
     40,  41,  42,  43,  44,  45,  46,  47,  48,  45,  49,  50,  51,  52,  46,   0,
     53,  54,  55,  47,  53,  56,  57,  58,  53,  59,  60,  61,  62,  63,  64,   0,
     14,  65,  64,   0,  66,  67,  68,   0,  69,   0,  70,  71,  72,   0,   0,   0,
      4,  73,  74,  75,  76,   4,  77,  78,   4,   4,  79,   4,  80,  81,  82,   4,
     83,   4,  84,   0,  23,   4,   4,  85,  14,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,  86,   1,   4,   4,  87,  88,  89,  89,  90,   4,  91,  92,   0,
      0,   4,   4,  93,   4,  94,   4,  95,  96,   0,  16,  97,   4,  98,  99,   0,
    100,   4,  85,   0,   0, 101,   0,   0, 102,  91, 103,   0, 104, 105,   4, 106,
      4, 107, 108, 109,   0,   0,   0, 110,   4,   4,   4,   4,   4,   4,   0,   0,
    111,   4, 112, 109,   4, 113, 114, 115,   0,   0,   0, 116, 117,   0,   0,   0,
    118, 119, 120,   4, 121,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      4, 122,  96,   4,   4,   4,   4, 123,   4,  77,   4, 124, 100, 125, 125,   0,
    126, 127,  14,   4, 128,  14,   4,  78, 102, 129,   4,   4, 130,  84,   0,  16,
      4,   4,   4,   4,   4,  95,   0,   0,   4,   4,   4,   4,   4,   4,  71,   0,
      4,   4,   4,   4,  71,   0,  16, 109, 131, 132,   4, 133, 109,   4,   4,  23,
    134, 135,   4,   4, 136, 137,   0, 134, 138, 139,   4,  91, 135,  91,   0, 140,
     26, 141,  64, 142,  32,  31, 143, 144,   4, 121, 145, 146,   4, 147, 148, 149,
    150, 151,  78, 152,   0,   0,   4, 139,   4,   4,   4,   4,   4, 153, 154, 155,
      4,   4,   4, 156,   4,   4, 157,   0, 158, 159, 160,   4,   4,  89, 161,   4,
      4,   4, 109,  32,   4,   4,   4,   4,   4, 109,  16,   4, 162,   4,  15, 163,
      0,   0,   0, 164,   4,   4,   4, 142,   0,   1,   1, 165, 109,  96, 166,   0,
    167, 168, 169,   0,   4,   4,   4,  84,   0,   0,   4,  85,   0,   0,   0,   0,
      0,   0,   0,   0, 142,   4, 170,   0,   4,  16, 171,  95, 109,   4, 172,   0,
      4,   4,   4,   4, 109,   0,   0,   0,   4, 173,   4, 107,   0,   0,   0,   0,
      4, 100,  95,  15,   0,   0,   0,   0, 174, 175,  95, 100,  96,   0,   0,   0,
     95, 157,   0,   0,   4, 176,   0,   0, 177,  91,   0, 142, 142,   0,  70, 178,
      4,  95,  95,  31,  89,   0,   0,   0,   4,   4, 121,   0,   0,   0,   0,   0,
    104,  93,   0,   0, 104,  23,  16, 121, 104,  64,  16, 179, 104,  31, 180,   0,
    181,  98,   0,   0,   0,  16,  96,   0,  48,  45, 182,  47,   0,   0,   0,   0,
      0,   0,   0,   0,   4,  23, 183,   0,   0,   0,   0,   0,   4, 130,   0,   0,
      4,  23, 184,   0,   4,  18,   0,   0,   0,   0,   0,   0,   0,   4,   4, 185,
      0,   0,   0,   0,   0,   0,   4,  30,   4,   4,   4,   4,  30,   0,   0,   0,
      4,   4,   4, 130,   0,   0,   0,   0,   4, 130,   0,   0,   0,   0,   0,   0,
      4,  30,  96,   0,   0,   0,  16, 186,   4,  23, 107, 187,  23,   0,   0,   0,
      4,   4, 188,   0, 161,   0,   0,   0,  47,   0,   0,   0,   0,   0,   0,   0,
      4,   4,   4, 189, 190,   0,   0,   0,   4,   4, 191,   4, 192, 193, 194,   4,
    195, 196, 197,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4, 198, 199,  78,
    191, 191, 122, 122, 200, 200, 145,   0,   4,   4,   4,   4,   4,   4, 178,   0,
    194, 201, 202, 203, 204, 205,   0,   0,   4,   4,   4,   4,   4,   4, 100,   0,
      4,  85,   4,   4,   4,   4,   4,   4, 109,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_xid_start_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,   0,   0, 223, 184,
     64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,   3, 252, 255, 255,
    255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255, 255,   0,   0,   0,
      0,   0, 255, 255, 255,   7,   7,   0, 255,   7,   0,   0,   0, 192, 254, 255,
    255, 255,  47,   0,  96, 192,   0, 156,   0,   0, 253, 255, 255, 255,   0,   0,
      0, 224, 255, 255,  63,   0,   2,   0,   0, 252, 255, 255, 255,   7,  48,   4,
    255, 255,  63,   4,  16,   1,   0,   0, 255, 255, 255,   1, 255, 255,   7,   0,
    240, 255, 255, 255, 255, 255, 255,  35,   0,   0,   1, 255,   3,   0, 254, 255,
    225, 159, 249, 255, 255, 253, 197,  35,   0,  64,   0, 176,   3,   0,   3,   0,
    224, 135, 249, 255, 255, 253, 109,   3,   0,   0,   0,  94,   0,   0,  28,   0,
    224, 191, 251, 255, 255, 253, 237,  35,   0,   0,   1,   0,   3,   0,   0,   0,
    224, 159, 249, 255,   0,   0,   0, 176,   3,   0,   2,   0, 232, 199,  61, 214,
     24, 199, 255,   3, 224, 223, 253, 255, 255, 253, 255,  35,   0,   0,   0,   3,
    255, 253, 239,  35,   0,   0,   0,  64,   3,   0,   6,   0, 255, 255, 255,  39,
      0,  64,   0,   0,   3,   0,   0, 252, 224, 255, 127, 252, 255, 255, 251,  47,
    127,   0,   0,   0, 255, 255,   5,   0, 150,  37, 240, 254, 174, 236,   5,  32,
     95,   0,   0, 240,   1,   0,   0,   0, 255, 254, 255, 255, 255,  31,   0,   0,
      0,  31,   0,   0, 255,   7,   0, 128,   0,   0,  63,  60,  98, 192, 225, 255,
      3,  64,   0,   0, 191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61,
    255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255,
    255, 255, 255,   7, 255, 255,  31,   0, 255, 159, 255, 255, 255, 199, 255,   1,
    255, 223,   3,   0, 255, 255,   3,   0, 255, 223,   1,   0, 255, 255,  15,   0,
      0,   0, 128,  16, 255, 255, 255,   0, 255,   5, 255, 255, 255, 255,  63,   0,
    255, 255, 255, 127, 255,  63,  31,   0, 255,  15,   0,   0, 254,   0,   0,   0,
    255, 255, 127,   0, 128,   0,   0,   0, 224, 255, 255, 255, 224,  15,   0,   0,
    248, 255, 255, 255,   1, 192,   0, 252,  63,   0,   0,   0,  15,   0,   0,   0,
      0, 224,   0, 252, 255, 255, 255,  63,   0, 222,  99,   0, 255, 255,  63,  63,
     63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   2, 128,   0,   0, 255,  31, 132, 252,  47,  63,  80, 253, 255, 243,
    224,  67,   0,   0, 255,   1,   0,   0, 255, 127, 255, 255,  31, 120,  12,   0,
    255, 128,   0,   0, 127, 127, 127, 127, 224,   0,   0,   0, 254,   3,  62,  31,
    255, 255, 127, 224, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31, 255, 255,
      0,  12,   0,   0, 255, 127,   0, 128,   0,   0, 128, 255, 252, 255, 255, 255,
    255, 121, 255, 255, 255,  63,   3,   0, 187, 247, 255, 255,   7,   0,   0,   0,
      0,   0, 252,   8,  63,   0, 255, 255, 255, 255, 255,  31,   0, 128,   0,   0,
    223, 255,   0, 124, 247,  15,   0,   0, 255, 255, 127, 196, 255, 255,  98,  62,
      5,   0,   0,  56, 255,   7,  28,   0, 126, 126, 126,   0, 127, 127, 255, 255,
     48,   0,   0,   0,  15,   0, 255, 255, 127, 248, 255, 255, 255, 255, 255,  15,
    255,  63, 255, 255, 255, 255, 255,   3, 127,   0, 248, 160, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,   3,
      0,   0, 138, 170, 192, 255, 255, 255, 252, 252, 252,  28, 255, 239, 255, 255,
    127, 255, 255, 183, 255,  63, 255,  63, 255, 255,   1,   0, 255,   7, 255, 255,
     15, 255,  62,   0, 255,   0, 255, 255,  63, 253, 255, 255, 255, 255, 191, 145,
    255, 255, 255, 192,   1,   0, 239, 254,  31,   0,   0,   0, 255, 255,  71,   0,
     30,   0,   0,   4, 255, 255, 251, 255,   0,   0,   0, 224, 176,   0,   0,   0,
     16,   0,   0,   0,   0,   0,   0, 128, 255,  63,   0,   0, 248, 255, 255, 224,
     31,   0,   1,   0, 255,   7, 255,  31, 255,   1, 255,   3, 255, 255, 223, 255,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    255, 253, 255, 255, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94,
    255, 251, 255,  15, 238, 251, 255,  15,
};

/* XID_Start: 1929 bytes. */

RE_UINT32 re_get_xid_start(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_xid_start_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_xid_start_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_xid_start_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_xid_start_stage_4[pos + f] << 5;
    pos += code;
    value = (re_xid_start_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* XID_Continue. */

static RE_UINT8 re_xid_continue_stage_1[] = {
    0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6, 6,
    6, 6,
};

static RE_UINT8 re_xid_continue_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 26,  7, 27, 28, 13, 13, 13, 13, 13, 13, 13, 29,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    30, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_xid_continue_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 32, 33, 31, 31,
    34, 35, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 36,  1,  1,  1,  1,  1,  1,  1,  1,  1, 37,
     1,  1,  1,  1, 38,  1, 39, 40, 41, 42, 43, 44,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 45, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57,  1, 58,
    59, 60, 61, 62, 63, 31, 31, 31, 64, 65, 66, 67, 68, 69, 70, 31,
    71, 31, 72, 31, 31, 31, 31, 31,  1,  1,  1, 73, 74, 31, 31, 31,
     1,  1,  1,  1, 75, 31, 31, 31,  1,  1, 76, 77, 31, 31, 31, 78,
    79, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 80, 31, 31, 31,
    31, 81, 82, 31, 83, 84, 85, 86, 87, 31, 31, 31, 31, 31, 88, 31,
     1,  1,  1,  1,  1,  1, 89,  1,  1,  1,  1,  1,  1,  1,  1, 90,
    91, 31, 31, 31, 31, 31, 31, 31,  1,  1, 91, 31, 31, 31, 31, 31,
    31, 92, 31, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_xid_continue_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   7,   8,   6,   6,   6,   9,  10,  11,   6,  12,
      6,   6,   6,   6,  13,   6,   6,   6,   6,  14,  15,  16,  17,  18,  19,  20,
     21,   6,   6,  22,   6,   6,  23,  24,  25,   6,  26,   6,   6,  27,   6,  28,
      6,  29,  30,   0,   0,  31,   0,  32,   6,   6,   6,  33,  34,  35,  36,  37,
     38,  39,  40,  41,  42,  43,  44,  45,  46,  43,  47,  48,  49,  50,  51,  52,
     53,  54,  55,  45,  56,  57,  58,  59,  56,  60,  61,  62,  63,  64,  65,  66,
     16,  67,  68,   0,  69,  70,  71,   0,  72,  73,  74,  75,  76,  77,  78,   0,
      6,   6,  79,   6,  80,   6,  81,  82,   6,   6,  83,   6,  84,  85,  86,   6,
     87,   6,  60,  88,  89,   6,   6,  90,  16,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,  91,   3,   6,   6,  92,  93,  90,  94,  95,   6,   6,  96,  97,
     98,   6,   6,  99,   6, 100,   6, 101, 102, 103, 104, 105,   6, 106, 107,   0,
     30,   6, 102, 108, 109, 110,   0,   0,   6,   6, 111, 112,   6,   6,   6,  94,
      6,  99, 113,  80,   0,   0, 114, 115,   6,   6,   6,   6,   6,   6,   6, 116,
    117,   6, 118,  80,   6, 119, 120, 121,   0, 122, 123, 124, 125,   0, 125, 126,
    127, 128, 129,   6, 130,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6, 131, 102,   6,   6,   6,   6, 132,   6,  81,   6, 133, 134, 135, 135,   6,
    136, 137,  16,   6, 138,  16,   6,  82, 139, 140,   6,   6, 141,  67,   0,  25,
      6,   6,   6,   6,   6, 101,   0,   0,   6,   6,   6,   6,   6,   6, 142,   0,
      6,   6,   6,   6, 142,   0,  25,  80, 143, 144,   6, 145,  18,   6,   6,  27,
    146, 147,   6,   6, 148, 149,   0, 146,   6, 150,   6,  94,   6,   6, 151, 152,
      6, 153,  94,  77,   6,   6, 154, 102,   6, 134, 155, 156,   6,   6, 157, 158,
    159, 160,  82, 161,   0,   0,   6, 162,   6,   6,   6,   6,   6, 163, 164,  30,
      6,   6,   6, 153,   6,   6, 165,   0, 166, 167, 168,   6,   6,  27, 169,   6,
      6,   6,  80,  32,   6,   6,   6,   6,   6,  80,  25,   6, 170,   6, 150,   1,
     89, 171, 172, 173,   6,   6,   6,  77,   1,   2,   3, 104,   6, 102, 174,   0,
    175, 176, 177,   0,   6,   6,   6,  67,   0,   0,   6,  90,   0,   0,   0, 178,
      0,   0,   0,   0,  77,   6, 179, 180,   6,  25, 100,  67,  80,   6, 181,   0,
      6,   6,   6,   6,  80,  97,   0,   0,   6, 182,   6, 183,   0,   0,   0,   0,
      6, 134, 101, 150,   0,   0,   0,   0, 184, 185, 101, 134, 102,   0,   0,   0,
    101, 165,   0,   0,   6, 186,   0,   0, 187, 188,   0,  77,  77,   0,  74, 189,
      6, 101, 101,  31,  27,   0,   0,   0,   6,   6, 130,   0,   0,   0,   0,   0,
      6,   6, 189, 190,   6,  67,  25, 191,   6, 192,  25, 193,   6,   6, 194,   0,
    195,  99,   0,   0,   0,  25,   6, 196,  46,  43, 197, 198,   0,   0,   0,   0,
      0,   0,   0,   0,   6,   6, 199,   0,   0,   0,   0,   0,   6, 200, 180,   0,
      6,   6, 201,   0,   6,  99,  97,   0,   0,   0,   0,   0,   0,   6,   6, 202,
      0,   0,   0,   0,   0,   0,   6, 203,   6,   6,   6,   6, 203,   0,   0,   0,
      6,   6,   6, 141,   0,   0,   0,   0,   6, 141,   0,   0,   0,   0,   0,   0,
      6, 203, 102,  97,   0,   0,  25, 105,   6, 134, 204, 205,  89,   0,   0,   0,
      6,   6, 206, 102, 207,   0,   0,   0, 208,   0,   0,   0,   0,   0,   0,   0,
      6,   6,   6, 209, 210,   0,   0,   0,   0,   0,   0, 211, 212, 213,   0,   0,
      0,   0, 214,   0,   0,   0,   0,   0,   6,   6, 192,   6, 215, 216, 217,   6,
    218, 219, 220,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6, 221, 222,  82,
    192, 192, 131, 131, 223, 223, 224,   6,   6,   6,   6,   6,   6,   6, 225,   0,
    217, 226, 227, 228, 229, 230,   0,   0,   6,   6,   6,   6,   6,   6, 134,   0,
      6,  90,   6,   6,   6,   6,   6,   6,  80,   0,   0,   0,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6,   6,  89,
};

static RE_UINT8 re_xid_continue_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255, 135, 254, 255, 255,   7,
      0,   4, 160,   4, 255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,
     31,  80,   0,   0, 255, 255, 223, 184, 192, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255, 251, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2,
    254, 255, 255, 255, 255,   0, 254, 255, 255, 255, 255, 191, 182,   0, 255, 255,
    255,   7,   7,   0,   0,   0, 255,   7, 255, 195, 255, 255, 255, 255, 239, 159,
    255, 253, 255, 159,   0,   0, 255, 255, 255, 231, 255, 255, 255, 255,   3,   0,
    255, 255,  63,   4, 255,  63,   0,   0, 255, 255, 255,  15, 255, 255,   7,   0,
    240, 255, 255, 255, 207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 211,
    135,  57,   2,  94, 192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 243,
    191,  59,   1,   0, 207, 255,   0,   0, 238, 159, 249, 255, 159,  57, 192, 176,
    207, 255,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0,
    192, 255,   0,   0, 239, 223, 253, 255, 255, 253, 255, 227, 223,  61,  96,   3,
    238, 223, 253, 255, 255, 253, 239, 243, 223,  61,  96,  64, 207, 255,   6,   0,
    255, 255, 255, 231, 223, 125, 128,   0, 207, 255,   0, 252, 236, 255, 127, 252,
    255, 255, 251,  47, 127, 132,  95, 255, 192, 255,  12,   0, 255, 255, 255,   7,
    255, 127, 255,   3, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63, 255, 243,
      1,   0,   0,   3, 255,   3, 160, 194, 255, 254, 255, 255, 255,  31, 254, 255,
    223, 255, 255, 254, 255, 255, 255,  31,  64,   0,   0,   0, 255,   3, 255, 255,
    255, 255, 255,  63, 191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61,
    255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255,
      0, 254,   3,   0, 255, 255,   0,   0, 255, 255,  31,   0, 255, 159, 255, 255,
    255, 199, 255,   1, 255, 223,  31,   0, 255, 255,  15,   0, 255, 223,  13,   0,
    255, 255, 143,  48, 255,   3,   0,   0,   0,  56, 255,   3, 255, 255, 255,   0,
    255,   7, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  15, 255,  15,
    192, 255, 255, 255, 255,  63,  31,   0, 255,  15, 255, 255, 255,   3, 255,   7,
    255, 255, 255, 159, 255,   3, 255,   3, 128,   0, 255,  63, 255,  15, 255,   3,
      0, 248,  15,   0, 255, 227, 255, 255,   0,   0, 247, 255, 255, 255, 127,   3,
    255, 255,  63, 240, 255, 255,  63,  63,  63,  63, 255, 170, 255, 255, 223,  95,
    220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   0, 128,   1,   0,  16,   0,
      0,   0,   2, 128,   0,   0, 255,  31, 226, 255,   1,   0, 132, 252,  47,  63,
     80, 253, 255, 243, 224,  67,   0,   0, 255,   1,   0,   0, 255, 127, 255, 255,
     31, 248,  15,   0, 255, 128,   0, 128, 255, 255, 127,   0, 127, 127, 127, 127,
    224,   0,   0,   0, 254, 255,  62,  31, 255, 255, 127, 230, 224, 255, 255, 255,
    255,  63, 254, 255, 255, 127,   0,   0, 255,  31,   0,   0, 255,  31, 255, 255,
    255,  15,   0,   0, 255, 255, 240, 191,   0,   0, 128, 255, 252, 255, 255, 255,
    255, 121, 255, 255, 255,  63,   3,   0, 255,   0,   0,   0,  31,   0, 255,   3,
    255, 255, 255,   8, 255,  63, 255, 255,   1, 128, 255,   3, 255,  63, 255,   3,
    255, 255, 127, 252,   7,   0,   0,  56, 255, 255, 124,   0, 126, 126, 126,   0,
    127, 127, 255, 255,  48,   0,   0,   0, 255,  55, 255,   3,  15,   0, 255, 255,
    127, 248, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255, 255,  63,  24,   0,
      0, 224,   0,   0,   0,   0, 138, 170, 252, 252, 252,  28, 255, 239, 255, 255,
    127, 255, 255, 183, 255,  63, 255,  63,   0,   0,   0,  32, 255, 255,   1,   0,
      1,   0,   0,   0,  15, 255,  62,   0, 255,   0, 255, 255,  15,   0,   0,   0,
     63, 253, 255, 255, 255, 255, 191, 145, 255, 255, 255, 192, 111, 240, 239, 254,
    255, 255,  15, 135, 127,   0,   0,   0, 192, 255,   0, 128, 255,   1, 255,   3,
    255, 255, 223, 255, 255, 255,  79,   0,  31,   0, 255,   7, 255, 255, 251, 255,
    255,   7, 255,   3, 159,  57, 128, 224, 207,  31,  31,   0, 191,   0, 255,   3,
    255, 255,  63, 255,  17,   0, 255,   3, 255,   3,   0, 128, 255, 255, 255,   1,
     15,   0, 255,   3, 248, 255, 255, 224,  31,   0, 255, 255,   0, 128, 255, 255,
      3,   0,   0,   0, 255,   7, 255,  31, 255,   1, 255,  99, 224, 227,   7, 248,
    231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0, 255, 255, 255, 223,
    100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,
     95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247, 255, 253, 255, 255,
    247, 207, 255, 255,  31,   0, 127,   0, 150, 254, 247,  10, 132, 234, 150, 170,
    150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
};

/* XID_Continue: 2078 bytes. */

RE_UINT32 re_get_xid_continue(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_xid_continue_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_xid_continue_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_xid_continue_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_xid_continue_stage_4[pos + f] << 5;
    pos += code;
    value = (re_xid_continue_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Default_Ignorable_Code_Point. */

static RE_UINT8 re_default_ignorable_code_point_stage_1[] = {
    0, 1, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 2, 2, 2,
    2, 2,
};

static RE_UINT8 re_default_ignorable_code_point_stage_2[] = {
    0, 1, 2, 3, 4, 1, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 7, 1, 1, 8, 1, 1, 1, 1, 1,
    9, 9, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_default_ignorable_code_point_stage_3[] = {
     0,  1,  1,  2,  1,  1,  3,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  4,  1,  1,  1,  1,  1,  5,  6,  1,  1,  1,  1,  1,  1,  1,
     7,  1,  1,  1,  1,  1,  1,  1,  1,  8,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  9, 10,  1,  1,  1,  1, 11,  1,  1,  1,
     1, 12,  1,  1,  1,  1,  1,  1, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_default_ignorable_code_point_stage_4[] = {
     0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  2,  0,  0,  0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  4,  5,  0,  0,  0,  0,  0,  0,  0,  0,  0,  6,  0,  0,
     7,  0,  0,  0,  0,  0,  0,  0,  8,  9,  0, 10,  0,  0,  0,  0,
     0,  0,  0, 11,  0,  0,  0,  0, 10,  0,  0,  0,  0,  0,  0,  4,
     0,  0,  0,  0,  0,  5,  0, 12,  0,  0,  0,  0,  0, 13,  0,  0,
     0,  0,  0, 14,  0,  0,  0,  0, 15, 15, 15, 15, 15, 15, 15, 15,
};

static RE_UINT8 re_default_ignorable_code_point_stage_5[] = {
      0,   0,   0,   0,   0,  32,   0,   0,   0, 128,   0,   0,   0,   0,   0,  16,
      0,   0,   0, 128,   1,   0,   0,   0,   0,   0,  48,   0,   0, 120,   0,   0,
      0, 248,   0,   0,   0, 124,   0,   0, 255, 255,   0,   0,  16,   0,   0,   0,
      0,   0, 255,   1,  15,   0,   0,   0,   0,   0, 248,   7, 255, 255, 255, 255,
};

/* Default_Ignorable_Code_Point: 370 bytes. */

RE_UINT32 re_get_default_ignorable_code_point(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_default_ignorable_code_point_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_default_ignorable_code_point_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_default_ignorable_code_point_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_default_ignorable_code_point_stage_4[pos + f] << 5;
    pos += code;
    value = (re_default_ignorable_code_point_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Grapheme_Extend. */

static RE_UINT8 re_grapheme_extend_stage_1[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 4, 4, 4,
    4, 4,
};

static RE_UINT8 re_grapheme_extend_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  8,  9,  7,  7,  7,  7,  7,  7,  7,  7,  7, 10,
    11, 12, 13,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7, 14,  7,  7,
     7,  7,  7,  7,  7,  7,  7, 15,  7,  7, 16,  7,  7, 17,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
    18,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
};

static RE_UINT8 re_grapheme_extend_stage_3[] = {
     0,  0,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,
    14,  0,  0, 15,  0,  0,  0, 16, 17, 18, 19, 20, 21, 22,  0,  0,
    23,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 24, 25,  0,  0,
    26,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 27,  0, 28, 29, 30, 31,  0,  0,  0,  0,
     0,  0,  0, 32,  0,  0, 33, 34,  0, 35, 36, 37,  0,  0,  0,  0,
     0,  0, 38,  0,  0,  0,  0,  0, 39, 40, 41, 42, 43, 44, 45,  0,
     0,  0, 46, 47,  0,  0,  0, 48,  0,  0,  0,  0, 49,  0,  0,  0,
     0, 50, 51,  0,  0,  0,  0,  0, 52,  0,  0,  0,  0,  0,  0,  0,
     0, 53,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_grapheme_extend_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   2,   0,   0,   0,   0,
      0,   0,   0,   0,   3,   0,   0,   0,   0,   0,   0,   0,   4,   5,   6,   0,
      7,   0,   8,   9,   0,   0,  10,  11,  12,  13,  14,   0,   0,  15,   0,  16,
     17,  18,  19,   0,   0,   0,   0,  20,  21,  22,  23,  24,  25,  26,  27,  24,
     28,  29,  30,  31,  28,  29,  32,  24,  25,  33,  34,  24,  35,  36,  37,   0,
     38,  39,  40,  24,  25,  41,  42,  24,  25,  36,  27,  24,   0,   0,  43,   0,
      0,  44,  45,   0,   0,  46,  47,   0,  48,  49,   0,  50,  51,  52,  53,   0,
      0,  54,  55,  56,  57,   0,   0,   0,   0,   0,  58,   0,   0,   0,   0,   0,
     59,  59,  60,  60,   0,  61,  62,   0,  63,   0,   0,   0,   0,  64,   0,   0,
      0,  65,   0,   0,   0,   0,   0,   0,  66,   0,  67,  68,   0,  69,   0,   0,
     70,  71,  35,  16,  72,  73,   0,  74,   0,  75,   0,   0,   0,   0,  76,  77,
      0,   0,   0,   0,   0,   0,   1,  78,  79,   0,   0,   0,   0,   0,  13,  80,
      0,   0,   0,   0,   0,   0,   0,  81,   0,   0,   0,  82,   0,   0,   0,   1,
      0,  83,   0,   0,  84,   0,   0,   0,   0,   0,   0,  85,  82,   0,   0,  86,
     87,  88,   0,   0,   0,   0,  89,  90,   0,  91,  92,   0,  21,  93,   0,  94,
      0,  95,  96,  29,   0,  97,  25,  98,   0,   0,   0,   0,   0,   0,   0,  99,
     36,   0,   0,   0,   0,   0,   0,   0,   2, 100,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  39,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 101,
      0,   0,   0,   0,   0,   0,   0,  38,   0,   0,   0, 102,   0,   0,   0,   0,
    103, 104,   0,   0,   0,   0,   0,  88,  25, 105, 106,  82,  72, 107,   0,   0,
     21, 108,   0, 109,  72, 110,   0,   0,   0, 111,   0,   0,   0,   0,  82, 112,
     25,  26, 113, 114,   0,   0,   0,   0,   0,   0,   0,   0,   0, 115, 116,   0,
      0,   0,   0,   0,   0, 117,  38,   0,   0, 118,  38,   0,   0, 119,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 120,   0, 121,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0, 122,   0,   0,   0,   0,   0,   0,   0, 123,   0,   0,   0,
      0,   0,   0, 124, 125, 126,   0,   0,   0,   0, 127,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 121,   0,   1,   1,   1,   1,   1,   1,   1,   2,
};

static RE_UINT8 re_grapheme_extend_stage_5[] = {
      0,   0,   0,   0, 255, 255, 255, 255, 255, 255,   0,   0, 248,   3,   0,   0,
      0,   0, 254, 255, 255, 255, 255, 191, 182,   0,   0,   0,   0,   0, 255,   7,
      0, 248, 255, 255,   0,   0,   1,   0,   0,   0, 192, 159, 159,  61,   0,   0,
      0,   0,   2,   0,   0,   0, 255, 255, 255,   7,   0,   0, 192, 255,   1,   0,
      0, 248,  15,   0,   0,   0, 192, 251, 239,  62,   0,   0,   0,   0,   0,  14,
    240, 255, 255, 255,   7,   0,   0,   0,   0,   0,   0,  20, 254,  33, 254,   0,
     12,   0,   0,   0,   2,   0,   0,   0,   0,   0,   0,  80,  30,  32, 128,   0,
      6,   0,   0,   0,   0,   0,   0,  16, 134,  57,   2,   0,   0,   0,  35,   0,
    190,  33,   0,   0,   0,   0,   0, 208,  30,  32, 192,   0,   4,   0,   0,   0,
      0,   0,   0,  64,   1,  32, 128,   0,   1,   0,   0,   0,   0,   0,   0, 192,
    193,  61,  96,   0,   0,   0,   0, 144,  68,  48,  96,   0,   0, 132,  92, 128,
      0,   0, 242,   7, 128, 127,   0,   0,   0,   0, 242,  27,   0,  63,   0,   0,
      0,   0,   0,   3,   0,   0, 160,   2,   0,   0, 254, 127, 223, 224, 255, 254,
    255, 255, 255,  31,  64,   0,   0,   0,   0, 224, 253, 102,   0,   0,   0, 195,
      1,   0,  30,   0, 100,  32,   0,  32,   0,   0,   0, 224,   0,   0,  28,   0,
      0,   0,  12,   0,   0,   0, 176,  63,  64, 254,  15,  32,   0,  56,   0,   0,
      0,   2,   0,   0, 135,   1,   4,  14,   0,   0, 128,   9,   0,   0,  64, 127,
    229,  31, 248, 159,   0,   0, 255, 127,  15,   0,   0,   0,   0,   0, 208,  23,
      3,   0,   0,   0,  60,  59,   0,   0,  64, 163,   3,   0,   0, 240, 207,   0,
      0,   0, 247, 255, 253,  33,  16,   3, 255, 255,  63, 240,   0,  48,   0,   0,
    255, 255,   1,   0,   0, 128,   3,   0,   0,   0,   0, 128,   0, 252,   0,   0,
      0,   0,   0,   6,   0, 128, 247,  63,   0,   0,   3,   0,  68,   8,   0,   0,
     96,   0,   0,   0,  16,   0,   0,   0, 255, 255,   3,   0, 192,  63,   0,   0,
    128, 255,   3,   0,   0,   0, 200,  19,  32,   0,   0,   0,   0, 126, 102,   0,
      8,  16,   0,   0,   0,   0, 157, 193,   0,  48,  64,   0,  32,  33,   0,   0,
    255,  63,   0,   0,   0,   0,   0,  32,   0,   0, 192,   7, 110, 240,   0,   0,
      0,   0,   0, 135,   0,   0,   0, 255, 127,   0,   0,   0,   0,   0, 120,   6,
    128, 239,  31,   0,   0,   0,   8,   0,   0,   0, 192, 127,   0, 128, 211,   0,
    248,   7,   0,   0,   1,   0, 128,   0, 192,  31,  31,   0,   0,   0, 249, 165,
     13,   0,   0,   0,   0, 128,  60, 176,   0,   0, 248, 167,   0,  40, 191,   0,
      0,   0,  31,   0,   0,   0, 127,   0,   0, 128,   7,   0,   0,   0,   0,  96,
    160, 195,   7, 248, 231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0,
};

/* Grapheme_Extend: 1226 bytes. */

RE_UINT32 re_get_grapheme_extend(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_grapheme_extend_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_grapheme_extend_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_grapheme_extend_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_grapheme_extend_stage_4[pos + f] << 5;
    pos += code;
    value = (re_grapheme_extend_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Grapheme_Base. */

static RE_UINT8 re_grapheme_base_stage_1[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 10, 12, 13, 14,
     3,  3,  3,  3,  3, 15, 10, 16, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10,
};

static RE_UINT8 re_grapheme_base_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 10, 10, 19, 20, 21, 22, 23, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 24, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 25,
    10, 10, 26, 27, 28, 29, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 30, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 32, 33, 34, 35,
    36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 31, 31,
    10, 50, 51, 31, 31, 31, 31, 31, 10, 10, 52, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 10, 53, 31, 54, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 55, 31, 31, 31, 31, 31, 56, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 57, 58, 59, 60, 31, 31, 31, 31,
    31, 31, 31, 31, 61, 31, 31, 62, 63, 64, 65, 66, 67, 31, 31, 31,
    10, 10, 10, 68, 10, 10, 10, 10, 10, 10, 10, 69, 70, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 10, 70, 31, 31,
};

static RE_UINT8 re_grapheme_base_stage_3[] = {
      0,   1,   2,   3,   3,   3,   3,   3,   3,   3,   3,   3,   4,   5,   6,   3,
      3,   3,   7,   3,   8,   9,  10,  11,  12,  13,   3,  14,  15,  16,  17,  18,
     19,  20,  21,   4,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,  32,  33,
     34,  35,  36,  37,  38,  39,  40,  41,  42,  43,  44,  45,  46,  47,  48,  49,
     50,  51,  52,  53,   3,   3,   3,   3,   3,  54,  55,  56,  57,  58,  59,  60,
      3,   3,   3,   3,   3,   3,   3,   3,   3,   3,  61,  62,  63,  64,  65,  66,
     67,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,   4,  78,  79,  80,  81,
     82,  83,   4,  84,   3,   3,   3,   4,   3,   3,   3,   3,  85,  86,  87,  88,
     89,  90,  91,   4,   3,   3,  92,   3,   3,   3,   3,   3,   3,   3,   3,  93,
     94,  95,   3,   3,   3,   3,   3,   3,   3,   3,   3,   3,   3,  96,  97,  98,
     99, 100,   3, 101, 102, 103, 104, 105,   3, 106, 107, 108,   3,   3,   3, 109,
    110, 111, 112,   3, 113,   3, 114, 115, 100,   3,   3,   1,   3,   3,   3,   3,
      3,   3,   3,   3,   3,   3,  70,   3,   3,   3,   3,   3,   3,   3,   3, 116,
      3,   3, 117, 118,   3,   3,   3,   3, 119, 120, 121, 122,   3,   3, 123, 124,
    125,  68,   3, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136,   4, 137,
      3,   3,   3,   3,   3,   3, 115, 138,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   3,   3,   3,   3,   3, 139,   3, 140, 141, 142,   3, 143,
      3,   3,   3,   3,   3, 144, 145, 146, 147, 148,   3, 149, 111,   3, 150, 151,
    152, 153,   3,  93, 154,   3, 155, 156,   4,   4,  61, 157, 115, 158, 159, 160,
      3,   3, 161,   4, 162, 163,   4,   4,   3,   3,   3,   3, 164, 165,   4,   4,
    166, 167, 168,   4, 169,   4, 170,   4, 171, 172, 173, 174, 175, 176, 177,   4,
      3, 178,   4,   4,   4,   4,   4,   4,   4, 179,   4,   4,   4,   4,   4,   4,
    180, 181, 182, 183, 184, 185, 186, 187, 188,   4, 189, 190, 191, 192,   4,   4,
      4,   4, 193, 194,   4,   4, 195, 196, 197, 198, 199, 200,   4,   4,   4,   4,
      4,   4,   0, 201,   4,   4,   4,   4,   4,   4,   4,  62,   4,   4,   4,   4,
      3,   3,   3,   3,   3,   3, 202,   4,   3, 203,   4,   4,   4,   4,   4,   4,
    204,   4,   4,   4,   4,   4,   4,   4,  62, 205,   4, 206, 207, 208, 209,   4,
      4,   4,   4,   4,   3, 210, 211,   4, 212,   4,   4,   4,   4,   4,   4,   4,
      3, 213, 214,   4,   4,   4,   4,   4,   3,   3,   3,  70, 215, 216, 217, 218,
      3, 219,   4,   4,   3, 220,   4,   4,   3, 221, 222, 223, 224, 225,   3,   3,
      3,   3, 226,   3,   3,   3,   3, 227,   3,   3,   3, 228,   4,   4,   4,   4,
    229, 230, 231, 232,   4,   4,   4,   4,  73,   3, 233, 234, 235,  73, 236, 237,
    238, 239,   4,   4, 240, 241,   3, 242,   3,   3,   3,   1,   3, 243, 244,   3,
      3, 245,   3, 246,   3, 108,   3, 247, 248, 249, 250,   4,   4,   4,   4,   4,
      3,   3,   3, 251,   3,   3,   3,   3,   3,   3,   3,   3,  60,   3,   3,   3,
    218,   4,   4,   4,   4,   4,   4,   4,
};

static RE_UINT8 re_grapheme_base_stage_4[] = {
      0,   0,   1,   1,   1,   1,   1,   2,   0,   0,   3,   1,   1,   1,   1,   1,
      0,   0,   0,   0,   0,   0,   0,   4,   5,   1,   6,   1,   7,   1,   1,   1,
      1,   1,   1,   8,   1,   9,   8,   1,  10,   0,   0,  11,  12,   1,  13,  14,
     15,  16,   1,   1,  13,   0,   1,   8,   1,  17,  18,   1,  19,  20,   1,   0,
     21,   1,   1,   1,   1,   1,  22,  23,   1,   1,  13,  24,   1,  25,  26,   2,
      1,  27,   0,   0,   0,   0,   1,  28,  29,   1,   1,  30,  31,  32,  33,   1,
     34,  35,  36,  37,  38,  39,  40,  41,  42,  35,  36,  43,  44,  45,  15,  46,
     47,   6,  36,  48,  49,  44,  40,  50,  51,  35,  36,  52,  53,  39,  40,  54,
     55,  56,  57,  58,  59,  44,  15,  13,  60,  20,  36,  61,  62,  63,  40,  64,
     65,  20,  36,  66,  67,  11,  40,  68,  65,  20,   1,  69,  70,   0,  40,  71,
     72,  73,   1,  74,  75,  76,  15,  46,   8,   1,   1,  77,  78,  41,   0,   0,
     79,  80,  81,  82,  83,  84,   0,   0,   1,   4,   1,  85,  86,   1,  87,  88,
     89,   0,   0,  90,  91,  13,   0,   0,   1,   1,  87,  92,   1,  93,   8,  94,
     95,   3,   1,   1,  96,   1,   1,   1,  97,  98,   1,   1,  97,   1,   1,  99,
    100, 101,   1,   1,   1, 100,   1,   1,   1,  13,   1,  87,   1, 102,   1,   1,
      1,   1,   1,  14,   1,  87,   1,   1,   1,   1,   1, 103,   3,  50,   1, 104,
      1,  50,   3,  44,   1,   1,   1, 105, 106, 107, 102, 102,  13, 102,   1,   1,
      1,   1,   1,  54,   1,   1, 108,   1,   1,   1,   1,  22,   1,   2, 109, 110,
    111,   1,  19,  14,   1,   1,  41,   1, 102, 112,   1,   1,   1, 113,   1,   1,
      1, 114, 115,  28, 102, 102,  19,   0, 116,   1,   1, 117, 118,   1,  13, 107,
    119,   1, 120,   1,   1,   1, 121, 122,   1,   1,  41, 123, 124,   1,   1,   1,
     54, 125, 126, 127,   1, 128,   1,   1, 128, 129,   1,  19,   1,   1,   1, 130,
    130, 131,   1, 132,  13,   1, 133,   1,   1,   1,   0,  33,   2,  87,   1,  19,
    102,   1,   1,   1,   1,   1,   1,  13,   1,   1,  75,   0,  13,   0,   1,   1,
      1,   1,   1, 134,   1, 135,   1, 124,  36,  50,   0,   0,   1,   1,   2,   1,
      1,   2,   1,   1,   1,   1,   2, 136,   1,   1,  96,   1,   1,   1, 133,  44,
      1,  75, 137, 137, 137, 137,   0,   0,  28,   0,   0,   0,   1, 138,   1,   1,
      1,   1,   1, 139,   1,  22,   0,  41,   1,   1, 102,   1,   8,   1,   1,   1,
      1, 140,   1,   1, 141,   1,  19,   8,   2,   1,   1,  13,   1,   1, 139,   1,
     87,   0,   0,   0,  87,   1,   1,   1,  75,   1,   1,   1,   1,   1,  41,   0,
      1,   1,   2, 142,   1,  19,   1,   1,   1,   1,   1, 143,   2,   1,  19,  50,
      0,   0,   0, 144, 145,   1, 146, 102, 147, 102,   0, 148,   1,   1, 149,   1,
     75, 150,   1,  87,  29,   1,   1, 151, 152, 153, 130,   2,   1,   1, 154, 155,
    156,  84,   1, 157,   1,   1,   1, 158, 159, 160, 161,  22, 162, 163, 137,   1,
      1,   1, 164,   0,   1,   1, 165, 102, 140,   1,   1,  41,   1,   1,  19,   1,
      1, 102,   0,   0,  75, 166,   1, 167, 168,   1,   1,   1,  50,  29,   1,   1,
      0,   1,   1,   1,   1, 119,   1,   1,  54,   0,   0,  19,   0, 102,   0,   1,
      1, 169, 170, 130,   1,   1,   1,  87,   1,  19,   1,   2, 171, 172, 137, 173,
    157,   1, 101, 174,  19,  19,   0,   0, 175,   1,   1, 176,  87,  41,  44,   0,
      0,   1,   1,  87,   1,  44,   8,  41,  13,   1,   1,  22,   1, 152,   1,   1,
    177,  22,   0,   0,   1,  19, 102,   0,   1,   1,  54,   1,   1,   1, 178,   0,
      1,   1,   1,  75,   1,  22,  54,   0, 179,   1,   1, 180,   1, 181,   1,   1,
      1,   2, 144,   0,   1, 182,   1,  58,   1,   1,   1, 183,  44, 184,   1, 139,
     54, 103,   1,   1,   1,   1,   0,   0,   1,   1, 185,  75,   1,   1,   1,  71,
      1, 135,   1, 186,   1, 187, 188,   0, 103,   0,   0,   0,   0,   0,   1,   2,
     20,   1,   1,  54, 189, 119,   1,   0, 119,   1,   1, 190,  50,   1, 103, 102,
     29,   1, 191,  15, 139,   1,   1, 192, 119,   1,   1, 193, 194,  13,   8,  14,
      1,   6,   2, 195,   0,   0,   0,   1,   1,   2,  28, 102,  51,  35,  36, 196,
    197,  21, 139,   0,   1,   1,   1, 198, 199, 102,   0,   0,   1,   1,   2, 200,
    201,   0,   0,   0,   1,   1,   1, 202,  62, 102,   0,   0,   1,   1, 203, 204,
    102,   0,   0,   0,   1,   1,   1, 205,   1, 103,   0,   0,   1,   1,   2,  14,
      1,   1,   2,   0,   1,   2, 153,   0,   0,   1,  19, 206,   1,   1,   1, 144,
     22, 138,   6, 207,   1,   0,   0,   0,  14,   1,   1,   2,   0,  29,   0,   0,
     50,   0,   0,   0,   1,   1,  13,  87, 103, 208,   0,   0,   1,   1,   9,   1,
      1,   1, 209,   0, 210,   1, 153,   1,   1,  19,   0,   0, 211,   0,   0,   0,
      1,  75,   1,  50,   1, 130,   1,   1,   1,   3, 212,  30, 213,   1,   1,   1,
    214, 215,   1, 216, 217,  20,   1,   1,   1,   1, 135,   1, 161,   1,   1,   1,
    218,   0,   0,   0, 213,   1, 219, 220, 221, 222, 223, 224, 138,  41, 225,  41,
      0,   0,   0,  50,   1, 139,   2,   8,   8,   8,   1,  22,  87,   1,   2,   1,
      1,  13,   0,   0,   0,   0,  15,   1,  28,   1,   1,  13, 103,  50,   0,   0,
      1,   1,  87,   1,   1,   1,   1,  19,   2, 116,   1,  54,  13,   1,   1, 138,
      1,   1, 213,   1, 226,   1,   1,   1,   1,   0,  87, 139,   1,  14,   0,   0,
     41,   1,   1,   1,  54, 102,   1,   1,  54,   1,  19,   0,   1,  75,   0,   0,
};

static RE_UINT8 re_grapheme_base_stage_5[] = {
      0,   0, 255, 255, 255, 127, 255, 223, 255, 252, 240, 215, 251, 255,   7, 252,
    254, 255, 127, 254, 255, 230,   0,  64,  73,   0, 255,   7,  31,   0, 192, 255,
      0, 200,  63,  64,  96, 194, 255,  63, 253, 255,   0, 224,  63,   0,   2,   0,
    240,   7,  63,   4,  16,   1, 255,  65,   7,   0, 248, 255, 255, 235,   1, 222,
      1, 255, 243, 255, 237, 159, 249, 255, 255, 253, 197, 163, 129,  89,   0, 176,
    195, 255, 255,  15, 232, 135, 109, 195,   1,   0,   0,  94,  28,   0, 232, 191,
    237, 227,   1,  26,   3,   0, 236, 159, 237,  35, 129,  25, 255,   0, 232, 199,
     61, 214,  24, 199, 255, 131, 198,  29, 238, 223, 255,  35,  30,   0,   0,   3,
      0, 255, 236, 223, 239,  99, 155,  13,   6,   0, 255, 167, 193,  93,  63, 254,
    236, 255, 127, 252, 251,  47, 127,   0,   3, 127,  13, 128, 127, 128, 150,  37,
    240, 254, 174, 236,  13,  32,  95,   0, 255, 243,  95, 253, 255, 254, 255,  31,
      0, 128,  32,  31,   0, 192, 191, 223,   2, 153, 255,  60, 225, 255, 155, 223,
    191,  32, 255,  61, 127,  61,  61, 127,  61, 255, 127, 255, 255,   3, 255,   1,
     99,   0,  79, 192, 191,   1, 240,  31, 255,   5, 120,  14, 251,   1, 241, 255,
    255, 199, 127, 198, 191,   0,  26, 224, 240, 255,  47, 232, 251,  15, 252, 255,
    195, 196, 191,  92,  12, 240,  48, 248, 255, 227,   8,   0,   2, 222, 111,   0,
     63,  63, 255, 170, 223, 255, 207, 239, 220, 127, 255, 128, 207, 255,  63, 255,
     12, 254, 127, 127, 255, 251,  15,   0, 127, 248, 224, 255,   8, 192, 252,   0,
    128, 255, 187, 247, 159,  15,  15, 192, 252,  15,  63, 192,  12, 128,  55, 236,
    255, 191, 255, 195, 255, 129,  25,   0, 247,  47, 255, 239,  98,  62,   5,   0,
      0, 248, 255, 207, 126, 126, 126,   0,  48,   0, 223,  30, 248, 160, 127,  95,
    219, 255, 247, 255, 127,  15, 252, 252, 252,  28,   0,  48, 255, 183, 135, 255,
    143, 255,  15, 255,  15, 128,  63, 253, 191, 145, 191, 255, 255, 143, 255, 192,
    239, 254,  31, 248,   7, 255,   3,  30,   0, 254, 128,  63, 135, 217, 127,  16,
    119,   0,  63, 128, 255,  33,  44,  63, 237, 163, 158,  57,   6,  90, 242,   0,
      3,  79, 254,   3,   7,  88, 255, 215,  64,   0,   7, 128,  32,   0, 255, 224,
    255, 147,  95,  60,  24, 240,  35,   0, 100, 222, 239, 255, 191, 231, 223, 223,
    255, 123,  95, 252, 159, 255, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247,
    247,  94, 238, 251, 231, 255,
};

/* Grapheme_Base: 2438 bytes. */

RE_UINT32 re_get_grapheme_base(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_grapheme_base_stage_1[f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_grapheme_base_stage_2[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_grapheme_base_stage_3[pos + f] << 2;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_grapheme_base_stage_4[pos + f] << 4;
    pos += code;
    value = (re_grapheme_base_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Grapheme_Link. */

static RE_UINT8 re_grapheme_link_stage_1[] = {
    0, 1, 2, 1, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1,
};

static RE_UINT8 re_grapheme_link_stage_2[] = {
     0,  0,  1,  2,  3,  4,  5,  0,  0,  0,  0,  6,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  7,  0,  0,  0,  0,  0,
     0,  0,  8,  0,  9, 10,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_grapheme_link_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  2,  3,  0,  0,  4,  5,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  6,  7,  0,  0,  0,  0,  8,  0,  9, 10,
     0,  0, 11,  0,  0,  0,  0,  0, 12,  9, 13, 14,  0, 15,  0, 16,
     0,  0,  0,  0, 17,  0,  0,  0, 18, 19, 20, 14, 21, 22,  1,  0,
     0, 23,  0, 17, 17, 24,  0,  0,
};

static RE_UINT8 re_grapheme_link_stage_4[] = {
     0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  2,  0,  0,  3,  0,  0,
     4,  0,  0,  0,  0,  5,  0,  0,  6,  6,  0,  0,  0,  0,  7,  0,
     0,  0,  0,  8,  0,  0,  4,  0,  0,  9,  0, 10,  0,  0,  0, 11,
    12,  0,  0,  0,  0,  0, 13,  0,  0,  0,  8,  0,  0,  0,  0, 14,
     0,  0,  0,  1,  0, 11,  0,  0,  0,  0, 12, 11,  0, 15,  0,  0,
     0, 16,  0,  0,  0, 17,  0,  0,  0,  0,  0,  2,  0,  0, 18,  0,
     0, 14,  0,  0,
};

static RE_UINT8 re_grapheme_link_stage_5[] = {
      0,   0,   0,   0,   0,  32,   0,   0,   0,   4,   0,   0,   0,   0,   0,   4,
     16,   0,   0,   0,   0,   0,   0,   6,   0,   0,  16,   0,   0,   0,   4,   0,
      1,   0,   0,   0,   0,  12,   0,   0,   0,   0,  12,   0,   0,   0,   0, 128,
     64,   0,   0,   0,   0,   0,   8,   0,   0,   0,  64,   0,   0,   0,   0,   2,
      0,   0,  24,   0,   0,   0,  32,   0,   4,   0,   0,   0,
};

/* Grapheme_Link: 396 bytes. */

RE_UINT32 re_get_grapheme_link(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 14;
    code = ch ^ (f << 14);
    pos = (RE_UINT32)re_grapheme_link_stage_1[f] << 4;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_grapheme_link_stage_2[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_grapheme_link_stage_3[pos + f] << 2;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_grapheme_link_stage_4[pos + f] << 5;
    pos += code;
    value = (re_grapheme_link_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* White_Space. */

static RE_UINT8 re_white_space_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_white_space_stage_2[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_white_space_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1,
    3, 1, 1, 1, 1, 1, 1, 1, 4, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_white_space_stage_4[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 3, 1, 1, 1, 1, 1, 4, 5, 1, 1, 1, 1, 1, 1,
    3, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_white_space_stage_5[] = {
      0,  62,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     32,   0,   0,   0,   1,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,
    255,   7,   0,   0,   0, 131,   0,   0,   0,   0,   0, 128,   0,   0,   0,   0,
};

/* White_Space: 169 bytes. */

RE_UINT32 re_get_white_space(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_white_space_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_white_space_stage_2[pos + f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_white_space_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_white_space_stage_4[pos + f] << 6;
    pos += code;
    value = (re_white_space_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Bidi_Control. */

static RE_UINT8 re_bidi_control_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_bidi_control_stage_2[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_bidi_control_stage_3[] = {
    0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    2, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_bidi_control_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
    2, 3, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_bidi_control_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  16,   0,   0,   0,   0,
      0, 192,   0,   0,   0, 124,   0,   0,   0,   0,   0,   0, 192,   3,   0,   0,
};

/* Bidi_Control: 129 bytes. */

RE_UINT32 re_get_bidi_control(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_bidi_control_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_bidi_control_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_bidi_control_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_bidi_control_stage_4[pos + f] << 6;
    pos += code;
    value = (re_bidi_control_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Join_Control. */

static RE_UINT8 re_join_control_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_join_control_stage_2[] = {
    0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_join_control_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_join_control_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_join_control_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0, 48,  0,  0,  0,  0,  0,  0,
};

/* Join_Control: 97 bytes. */

RE_UINT32 re_get_join_control(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_join_control_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_join_control_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_join_control_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_join_control_stage_4[pos + f] << 6;
    pos += code;
    value = (re_join_control_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Dash. */

static RE_UINT8 re_dash_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_dash_stage_2[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
};

static RE_UINT8 re_dash_stage_3[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 3, 1, 4, 1, 1, 1,
    5, 6, 1, 1, 1, 1, 1, 7, 8, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 9,
};

static RE_UINT8 re_dash_stage_4[] = {
     0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  2,  1,  3,  1,  1,  1,  1,  1,  1,  1,
     4,  1,  1,  1,  1,  1,  1,  1,  5,  6,  7,  1,  1,  1,  1,  1,
     8,  1,  1,  1,  1,  1,  1,  1,  9,  3,  1,  1,  1,  1,  1,  1,
    10,  1, 11,  1,  1,  1,  1,  1, 12, 13,  1,  1, 14,  1,  1,  1,
};

static RE_UINT8 re_dash_stage_5[] = {
      0,   0,   0,   0,   0,  32,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   4,   0,   0,   0,   0,   0,  64,   1,   0,   0,   0,   0,   0,   0,   0,
     64,   0,   0,   0,   0,   0,   0,   0,   0,   0,  63,   0,   0,   0,   0,   0,
      0,   0,   8,   0,   0,   0,   0,   8,   0,   8,   0,   0,   0,   0,   0,   0,
      0,   0,   4,   0,   0,   0,   0,   0,   0,   0, 128,   4,   0,   0,   0,  12,
      0,   0,   0,  16,   0,   0,   1,   0,   0,   0,   0,   0,   1,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   6,   0,   0,   0,   0,   1,   8,   0,   0,   0,
      0,  32,   0,   0,   0,   0,   0,   0,
};

/* Dash: 297 bytes. */

RE_UINT32 re_get_dash(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_dash_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_dash_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_dash_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_dash_stage_4[pos + f] << 6;
    pos += code;
    value = (re_dash_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Hyphen. */

static RE_UINT8 re_hyphen_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_hyphen_stage_2[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
};

static RE_UINT8 re_hyphen_stage_3[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 1, 1, 1,
    4, 1, 1, 1, 1, 1, 1, 5, 6, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 7,
};

static RE_UINT8 re_hyphen_stage_4[] = {
    0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2, 1, 3, 1, 1, 1, 1, 1, 1, 1,
    4, 1, 1, 1, 1, 1, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 6, 1, 1, 1, 1, 1, 7, 1, 1, 8, 9, 1, 1,
};

static RE_UINT8 re_hyphen_stage_5[] = {
      0,   0,   0,   0,   0,  32,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   4,   0,   0,   0,   0,   0,   0,  64,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   3,   0,   0,   0,   0,   0,   0,   0, 128,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   8,   0,   0,   0,   0,   8,   0,   0,   0,
      0,  32,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  32,   0,   0,   0,
};

/* Hyphen: 241 bytes. */

RE_UINT32 re_get_hyphen(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_hyphen_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_hyphen_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_hyphen_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_hyphen_stage_4[pos + f] << 6;
    pos += code;
    value = (re_hyphen_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Quotation_Mark. */

static RE_UINT8 re_quotation_mark_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_quotation_mark_stage_2[] = {
    0, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 4,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_quotation_mark_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 1, 1, 1, 1, 1, 1, 3, 4, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 5,
};

static RE_UINT8 re_quotation_mark_stage_4[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    3, 1, 1, 1, 1, 1, 1, 1, 1, 4, 1, 1, 1, 1, 1, 1,
    5, 1, 1, 1, 1, 1, 1, 1, 1, 6, 1, 1, 7, 8, 1, 1,
};

static RE_UINT8 re_quotation_mark_stage_5[] = {
      0,   0,   0,   0, 132,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   8,   0,   8,   0,   0,   0, 255,   0,   0,   0,   6,
      4,   0,   0,   0,   0,   0,   0,   0,   0, 240,   0, 224,   0,   0,   0,   0,
     30,   0,   0,   0,   0,   0,   0,   0, 132,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  12,   0,   0,   0,
};

/* Quotation_Mark: 209 bytes. */

RE_UINT32 re_get_quotation_mark(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_quotation_mark_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_quotation_mark_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_quotation_mark_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_quotation_mark_stage_4[pos + f] << 6;
    pos += code;
    value = (re_quotation_mark_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Terminal_Punctuation. */

static RE_UINT8 re_terminal_punctuation_stage_1[] = {
    0, 1, 2, 3, 4, 5, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1,
};

static RE_UINT8 re_terminal_punctuation_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  9, 10, 11,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9, 12, 13,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 14,
    15,  9, 16,  9, 17, 18,  9,  9,  9, 19,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 20,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 21,
};

static RE_UINT8 re_terminal_punctuation_stage_3[] = {
     0,  1,  1,  1,  1,  1,  2,  3,  1,  1,  1,  4,  5,  6,  7,  8,
     9,  1, 10,  1,  1,  1,  1,  1,  1,  1,  1,  1, 11,  1, 12,  1,
    13,  1,  1,  1,  1,  1, 14,  1,  1,  1,  1,  1, 15, 16, 17, 18,
    19,  1, 20,  1,  1, 21, 22,  1, 23,  1,  1,  1,  1,  1,  1,  1,
    24,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1, 25,  1,  1,  1, 26,  1,  1,  1,  1,  1,  1,  1,
     1, 27,  1,  1, 28, 29,  1,  1, 30, 31, 32, 33, 34, 35,  1, 36,
     1,  1,  1,  1, 37,  1, 38,  1,  1,  1,  1,  1,  1,  1,  1, 39,
    40,  1, 41,  1, 42, 43, 44, 45, 46, 47, 48, 49, 50,  1,  1,  1,
     1,  1,  1, 51, 52,  1,  1,  1, 53,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1, 54, 55, 56,  1,  1, 41,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_terminal_punctuation_stage_4[] = {
     0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,  3,  0,  0,  0,
     4,  0,  5,  0,  6,  0,  0,  0,  0,  0,  7,  0,  8,  0,  0,  0,
     0,  0,  0,  9,  0, 10,  2,  0,  0,  0,  0, 11,  0,  0, 12,  0,
    13,  0,  0,  0,  0,  0, 14,  0,  0,  0,  0, 15,  0,  0,  0, 16,
     0,  0,  0, 17,  0, 18,  0,  0,  0,  0, 19,  0, 20,  0,  0,  0,
     0,  0, 11,  0,  0, 21,  0,  0,  0,  0, 22,  0,  0, 23,  0, 24,
     0, 25, 26,  0,  0, 27, 28,  0, 29,  0,  0,  0,  0,  0,  0, 24,
    30,  0,  0,  0,  0,  0,  0, 31,  0,  0,  0, 32,  0,  0, 33,  0,
     0, 34,  0,  0,  0,  0, 26,  0,  0,  0, 35,  0,  0,  0, 36, 37,
     0,  0,  0, 38,  0,  0, 39,  0,  1,  0,  0, 40, 36,  0, 41,  0,
     0,  0, 42,  0, 36,  0,  0,  0,  0,  0, 32,  0,  0,  0,  0, 43,
     0, 44,  0,  0, 45,  0,  0,  0,  0,  0, 46,  0,  0, 24, 47,  0,
     0,  0, 48,  0,  0,  0, 49,  0,  0, 50,  0,  0,  0,  0, 51,  0,
     0,  0, 29,  0,  0,  0,  0, 52,  0,  0,  0, 33,  0,  0,  0, 53,
     0, 54, 55,  0,
};

static RE_UINT8 re_terminal_punctuation_stage_5[] = {
      0,   0,   0,   0,   2,  80,   0, 140,   0,   0,   0,  64, 128,   0,   0,   0,
      0,   2,   0,   0,   8,   0,   0,   0,   0,  16,   0, 136,   0,   0,  16,   0,
    255,  23,   0,   0,   0,   0,   0,   3,   0,   0, 255, 127,  48,   0,   0,   0,
      0,   0,   0,  12,   0, 225,   7,   0,   0,  12,   0,   0, 254,   1,   0,   0,
      0,  96,   0,   0,   0,  56,   0,   0,   0,   0,  96,   0,   0,   0, 112,   4,
     60,   3,   0,   0,   0,  15,   0,   0,   0,   0,   0, 236,   0,   0,   0, 248,
      0,   0,   0, 192,   0,   0,   0,  48, 128,   3,   0,   0,   0,  64,   0,  16,
      2,   0,   0,   0,   6,   0,   0,   0,   0, 224,   0,   0,   0,   0, 248,   0,
      0,   0, 192,   0,   0, 192,   0,   0,   0, 128,   0,   0,   0,   0,   0, 224,
      0,   0,   0, 128,   0,   0,   3,   0,   0,   8,   0,   0,   0,   0, 247,   0,
     18,   0,   0,   0,   0,   0,   1,   0,   0,   0, 128,   0,   0,   0,  63,   0,
      0,   0,   0, 252,   0,   0,   0,  30, 128,  63,   0,   0,   3,   0,   0,   0,
     14,   0,   0,   0,  96,  32,   0,   0,   0,   0,   0,  31,  60,   2,   0,   0,
      0,   0,  31,   0,   0,   0,  32,   0,   0,   0, 128,   3,  16,   0,   0,   0,
};

/* Terminal_Punctuation: 808 bytes. */

RE_UINT32 re_get_terminal_punctuation(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 14;
    code = ch ^ (f << 14);
    pos = (RE_UINT32)re_terminal_punctuation_stage_1[f] << 4;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_terminal_punctuation_stage_2[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_terminal_punctuation_stage_3[pos + f] << 2;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_terminal_punctuation_stage_4[pos + f] << 5;
    pos += code;
    value = (re_terminal_punctuation_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_Math. */

static RE_UINT8 re_other_math_stage_1[] = {
    0, 1, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2,
};

static RE_UINT8 re_other_math_stage_2[] = {
    0, 1, 1, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 4,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 5, 1, 1, 6, 1, 1,
};

static RE_UINT8 re_other_math_stage_3[] = {
     0,  1,  1,  2,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     3,  4,  1,  5,  1,  6,  7,  8,  1,  9,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 10, 11,  1,  1,  1,  1, 12, 13, 14, 15,
     1,  1,  1,  1,  1,  1, 16,  1,
};

static RE_UINT8 re_other_math_stage_4[] = {
     0,  0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  2,  3,  4,  5,  6,  7,  8,  0,  9, 10,
    11, 12, 13,  0, 14, 15, 16, 17, 18,  0,  0,  0,  0, 19, 20, 21,
     0,  0,  0,  0,  0, 22, 23, 24, 25,  0, 26, 27,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 25, 28,  0,  0,  0,  0, 29,  0, 30, 31,
     0,  0,  0, 32,  0,  0,  0,  0,  0, 33,  0,  0,  0,  0,  0,  0,
    34, 34, 35, 34, 36, 37, 38, 34, 39, 40, 41, 34, 34, 34, 34, 34,
    34, 34, 34, 34, 34, 42, 43, 44, 35, 35, 45, 45, 46, 46, 47, 34,
    38, 48, 49, 50, 51, 52,  0,  0,
};

static RE_UINT8 re_other_math_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,  64,   0,   0,  39,   0,   0,   0,  51,   0,
      0,   0,  64,   0,   0,   0,  28,   0,   1,   0,   0,   0,  30,   0,   0,  96,
      0,  96,   0,   0,   0,   0, 255,  31,  98, 248,   0,   0, 132, 252,  47,  62,
     16, 179, 251, 241, 224,   3,   0,   0,   0,   0, 224, 243, 182,  62, 195, 240,
    255,  63, 235,  47,  48,   0,   0,   0,   0,  15,   0,   0,   0,   0, 176,   0,
      0,   0,   1,   0,   4,   0,   0,   0,   3, 192, 127, 240, 193, 140,  15,   0,
    148,  31,   0,   0,  96,   0,   0,   0,   5,   0,   0,   0,  15,  96,   0,   0,
    192, 255,   0,   0, 248, 255, 255,   1,   0,   0,   0,  15,   0,   0,   0,  48,
     10,   1,   0,   0,   0,   0,   0,  80, 255, 255, 255, 255, 255, 255, 223, 255,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    255, 255, 255, 247, 255, 127, 255, 255, 255, 253, 255, 255, 247, 207, 255, 255,
    150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15,
    238, 251, 255,  15,
};

/* Other_Math: 502 bytes. */

RE_UINT32 re_get_other_math(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_other_math_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_other_math_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_other_math_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_other_math_stage_4[pos + f] << 5;
    pos += code;
    value = (re_other_math_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Hex_Digit. */

static RE_UINT8 re_hex_digit_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_hex_digit_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_hex_digit_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 2,
};

static RE_UINT8 re_hex_digit_stage_4[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2, 1,
};

static RE_UINT8 re_hex_digit_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 126,   0,   0,   0, 126,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0, 255,   3, 126,   0,   0,   0, 126,   0,   0,   0,   0,   0,   0,   0,
};

/* Hex_Digit: 129 bytes. */

RE_UINT32 re_get_hex_digit(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_hex_digit_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_hex_digit_stage_2[pos + f] << 3;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_hex_digit_stage_3[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_hex_digit_stage_4[pos + f] << 7;
    pos += code;
    value = (re_hex_digit_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* ASCII_Hex_Digit. */

static RE_UINT8 re_ascii_hex_digit_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_ascii_hex_digit_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_ascii_hex_digit_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_ascii_hex_digit_stage_4[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_ascii_hex_digit_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 126,   0,   0,   0, 126,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
};

/* ASCII_Hex_Digit: 97 bytes. */

RE_UINT32 re_get_ascii_hex_digit(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_ascii_hex_digit_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_ascii_hex_digit_stage_2[pos + f] << 3;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_ascii_hex_digit_stage_3[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_ascii_hex_digit_stage_4[pos + f] << 7;
    pos += code;
    value = (re_ascii_hex_digit_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_Alphabetic. */

static RE_UINT8 re_other_alphabetic_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_other_alphabetic_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  7,  8,  6,  6,  6,  6,  6,  6,  6,  6,  6,  9,
    10, 11, 12,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 13,  6,  6,
     6,  6,  6,  6,  6,  6,  6, 14,  6,  6,  6,  6,  6,  6, 15,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_other_alphabetic_stage_3[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
    13,  0,  0, 14,  0,  0,  0, 15, 16, 17, 18, 19, 20, 21,  0,  0,
     0,  0,  0,  0, 22,  0,  0,  0,  0,  0,  0,  0,  0, 23,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 24,  0,
    25, 26, 27, 28,  0,  0,  0,  0,  0,  0,  0, 29,  0,  0,  0,  0,
     0,  0,  0, 30,  0,  0,  0,  0,  0,  0, 31,  0,  0,  0,  0,  0,
    32, 33, 34, 35, 36, 37, 38,  0,  0,  0,  0, 39,  0,  0,  0, 40,
     0,  0,  0,  0, 41,  0,  0,  0,  0, 42,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_other_alphabetic_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  2,  3,  0,  4,  0,  5,  6,  0,  0,  7,  8,
     9, 10,  0,  0,  0, 11,  0,  0, 12, 13,  0,  0,  0,  0,  0, 14,
    15, 16, 17, 18, 19, 20, 21, 18, 19, 20, 22, 23, 19, 20, 24, 18,
    19, 20, 25, 18, 26, 20, 27,  0, 15, 20, 28, 18, 19, 20, 28, 18,
    19, 20, 29, 18, 18,  0, 30, 31,  0, 32, 33,  0,  0, 34, 33,  0,
     0,  0,  0, 35, 36, 37,  0,  0,  0, 38, 39, 40, 41,  0,  0,  0,
     0,  0, 42,  0,  0,  0,  0,  0, 31, 31, 31, 31,  0, 43, 44,  0,
     0,  0,  0,  0,  0, 45,  0,  0,  0, 46,  0,  0,  0, 10, 47,  0,
    48,  0, 49, 50,  0,  0,  0,  0, 51, 52, 15,  0, 53, 54,  0, 55,
     0, 56,  0,  0,  0,  0,  0, 31,  0,  0,  0,  0,  0,  0,  0, 57,
     0,  0,  0,  0,  0, 43, 58, 59,  0,  0,  0,  0,  0,  0,  0, 58,
     0,  0,  0, 60, 42,  0,  0,  0,  0, 61,  0,  0, 62, 63, 15,  0,
     0, 64, 65,  0, 15, 63,  0,  0,  0, 66, 67,  0,  0, 68,  0, 69,
     0,  0,  0,  0,  0,  0,  0, 70, 71,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 72,  0,  0,  0,  0, 73,  0,  0,  0,  0,  0,  0,  0,
    53, 74, 75,  0, 26, 76,  0,  0, 53, 65,  0,  0, 53, 77,  0,  0,
     0, 78,  0,  0,  0,  0, 42, 44, 19, 20, 21, 18,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 10, 62,  0,  0,  0,  0,  0,  0, 79,  0,  0,
     0, 80, 81,  0,  0, 82,  0,  0,  0, 83,  0,  0,  0,  0,  0,  0,
     0,  0, 35, 84,  0,  0,  0,  0,  0,  0,  0,  0, 71,  0,  0,  0,
     0, 10, 85, 85, 59,  0,  0,  0,
};

static RE_UINT8 re_other_alphabetic_stage_5[] = {
      0,   0,   0,   0,  32,   0,   0,   0,   0,   0, 255, 191, 182,   0,   0,   0,
      0,   0, 255,   7,   0, 248, 255, 254,   0,   0,   1,   0,   0,   0, 192,  31,
    158,  33,   0,   0,   0,   0,   2,   0,   0,   0, 255, 255, 192, 255,   1,   0,
      0,   0, 192, 248, 239,  30,   0,   0, 240,   3, 255, 255,  15,   0,   0,   0,
      0,   0,   0, 204, 255, 223, 224,   0,  12,   0,   0,   0,  14,   0,   0,   0,
      0,   0,   0, 192, 159,  25, 128,   0, 135,  25,   2,   0,   0,   0,  35,   0,
    191,  27,   0,   0, 159,  25, 192,   0,   4,   0,   0,   0, 199,  29, 128,   0,
    223,  29,  96,   0, 223,  29, 128,   0,   0, 128,  95, 255,   0,   0,  12,   0,
      0,   0, 242,   7,   0,  32,   0,   0,   0,   0, 242,  27,   0,   0, 254, 255,
      3, 224, 255, 254, 255, 255, 255,  31,   0, 248, 127, 121,   0,   0, 192, 195,
    133,   1,  30,   0, 124,   0,   0,  48,   0,   0,   0, 128,   0,   0, 192, 255,
    255,   1,   0,   0,   0,   2,   0,   0, 255,  15, 255,   1,   1,   3,   0,   0,
      0,   0, 128,  15,   0,   0, 224, 127, 254, 255,  31,   0,  31,   0,   0,   0,
      0,   0, 224, 255,   7,   0,   0,   0, 254,  51,   0,   0, 128, 255,   3,   0,
    240, 255,  63,   0, 128, 255,  31,   0, 255, 255, 255, 255, 255,   3,   0,   0,
      0,   0, 240,  15, 248,   0,   0,   0,   3,   0,   0,   0,   0,   0, 240, 255,
    192,   7,   0,   0, 128, 255,   7,   0,   0, 254, 127,   0,   8,  48,   0,   0,
      0,   0, 157,  65,   0, 248,  32,   0, 248,   7,   0,   0,   0,   0,   0,  64,
      0,   0, 192,   7, 110, 240,   0,   0,   0,   0,   0, 255,  63,   0,   0,   0,
      0,   0, 255,   1,   0,   0, 248, 255,   0, 240, 159,   0,   0, 128,  63, 127,
      0,   0, 255, 127,   1,   0,   0,   0,   0, 248,  63,   0,   0,   0, 127,   0,
    255, 255, 255, 127, 255,   3, 255, 255,
};

/* Other_Alphabetic: 929 bytes. */

RE_UINT32 re_get_other_alphabetic(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_alphabetic_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_other_alphabetic_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_other_alphabetic_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_other_alphabetic_stage_4[pos + f] << 5;
    pos += code;
    value = (re_other_alphabetic_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Ideographic. */

static RE_UINT8 re_ideographic_stage_1[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_ideographic_stage_2[] = {
    0, 0, 0, 1, 2, 3, 3, 3, 3, 4, 0, 0, 0, 0, 0, 5,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 6, 7, 0, 0, 0, 8,
};

static RE_UINT8 re_ideographic_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 4, 0, 0, 0, 0, 5, 6, 0, 0,
    2, 2, 2, 7, 2, 2, 2, 2, 2, 2, 2, 8, 9, 0, 0, 0,
    0, 0, 0, 0, 2, 9, 0, 0,
};

static RE_UINT8 re_ideographic_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 0,
    2, 2, 2, 2, 2, 2, 2, 4, 0, 0, 0, 0, 2, 2, 2, 2,
    2, 5, 2, 6, 0, 0, 0, 0, 2, 2, 2, 7, 2, 2, 2, 2,
    2, 2, 2, 2, 8, 2, 2, 2, 9, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_ideographic_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0, 192,   0,   0,   0, 254,   3,   0,   7,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,  63,   0,
    255,  31,   0,   0,   0,   0,   0,   0, 255, 255, 255, 255, 255,  63, 255, 255,
    255, 255, 255,   3,   0,   0,   0,   0, 255, 255, 127,   0,   0,   0,   0,   0,
    255, 255, 255, 255, 255, 255,  31,   0, 255, 255, 255,  63,   0,   0,   0,   0,
};

/* Ideographic: 297 bytes. */

RE_UINT32 re_get_ideographic(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_ideographic_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_ideographic_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_ideographic_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_ideographic_stage_4[pos + f] << 6;
    pos += code;
    value = (re_ideographic_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Diacritic. */

static RE_UINT8 re_diacritic_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_diacritic_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  7,  8,  4,  4,  4,  4,  4,  4,  4,  4,  4,  9,
    10, 11, 12,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4, 13,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4, 14,  4,  4, 15,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
};

static RE_UINT8 re_diacritic_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1,  1,  1,  1,  1,  1, 17,  1, 18, 19, 20, 21, 22,  1, 23,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 24,  1, 25,  1,
    26,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 27, 28,
    29, 30, 31, 32,  1,  1,  1,  1,  1,  1,  1, 33,  1,  1, 34, 35,
     1,  1, 36,  1,  1,  1,  1,  1,  1,  1, 37,  1,  1,  1,  1,  1,
    38, 39, 40, 41, 42, 43, 44,  1,  1,  1, 45,  1,  1,  1,  1, 46,
     1, 47,  1,  1,  1,  1,  1,  1, 48,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_diacritic_stage_4[] = {
     0,  0,  1,  2,  0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  4,  5,  5,  5,  5,  6,  7,  8,  0,  0,  0,
     0,  0,  0,  0,  9,  0,  0,  0,  0,  0, 10,  0, 11, 12, 13,  0,
     0,  0, 14,  0,  0,  0, 15, 16,  0,  4, 17,  0,  0, 18,  0, 19,
    20,  0,  0,  0,  0,  0,  0, 21,  0, 22, 23, 24,  0, 22, 25,  0,
     0, 22, 25,  0,  0, 22, 25,  0,  0, 22, 25,  0,  0,  0, 25,  0,
     0,  0, 25,  0,  0, 22, 25,  0,  0,  0, 25,  0,  0,  0, 26,  0,
     0,  0, 27,  0,  0,  0, 28,  0, 20, 29,  0,  0, 30,  0, 31,  0,
     0, 32,  0,  0, 33,  0,  0,  0,  0,  0,  0,  0,  0,  0, 34,  0,
     0, 35,  0,  0,  0,  0,  0,  0,  0,  0,  0, 36,  0, 37,  0,  0,
     0, 38, 39, 40,  0, 41,  0,  0,  0, 42,  0, 43,  0,  0,  4, 44,
     0, 45,  5, 17,  0,  0, 46, 47,  0,  0,  0,  0,  0, 48, 49, 50,
     0,  0,  0,  0,  0,  0,  0, 51,  0, 52,  0,  0,  0,  0,  0,  0,
     0, 53,  0,  0, 54,  0,  0, 22,  0,  0,  0, 55, 56,  0,  0, 57,
    58, 59,  0,  0, 60,  0,  0, 20,  0,  0,  0,  0,  0,  0, 39, 61,
     0, 62, 63,  0,  0, 63,  2, 64,  0,  0,  0, 65,  0, 15, 66, 67,
     0,  0, 68,  0,  0,  0,  0, 69,  1,  0,  0,  0,  0,  0,  0,  0,
     0, 70,  0,  0,  0,  0,  0,  0,  0,  1,  2, 71, 72,  0,  0, 73,
     0,  0,  0,  0,  0,  0,  0,  2,  0,  0,  0,  0,  0,  0,  0, 74,
     0,  0,  0,  0,  0, 75,  0,  0,  0, 76,  0, 63,  0,  0,  2,  0,
     0, 77,  0,  0,  0,  0,  0, 78,  0, 22, 25, 79,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 80,  0,  0,  0,  0,  0,  0, 15,  2,  0,
     0, 15,  0,  0,  0, 42,  0,  0,  0,  0,  0,  0,  0,  0,  0, 81,
     0,  0,  0,  0, 82,  0,  0,  0,  0,  0,  0, 83, 84, 85,  0,  0,
     0,  0,  0,  0,  0,  0, 86,  0,
};

static RE_UINT8 re_diacritic_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,  64,   1,   0,   0,   0,   0, 129, 144,   1,
      0,   0, 255, 255, 255, 255, 255, 255, 255, 127, 255, 224,   7,   0,  48,   4,
     48,   0,   0,   0, 248,   0,   0,   0,   0,   0,   0,   2,   0,   0, 254, 255,
    251, 255, 255, 191,  22,   0,   0,   0,   0, 248, 135,   1,   0,   0,   0, 128,
     97,  28,   0,   0, 255,   7,   0,   0, 192, 255,   1,   0,   0, 248,  63,   0,
      0,   0,   0,   3, 240, 255, 255, 127,   0,   0,   0,  16,   0,  32,  30,   0,
      0,   0,   2,   0,   0,  32,   0,   0,   0,   4,   0,   0, 128,  95,   0,   0,
      0,  31,   0,   0,   0,   0, 160, 194, 220,   0,   0,   0,  64,   0,   0,   0,
      0,   0, 128,   6, 128, 191,   0,  12,   0, 254,  15,  32,   0,   0,   0,  14,
      0,   0, 224, 159,   0,   0, 255,  63,   0,   0,  16,   0,  16,   0,   0,   0,
      0, 248,  15,   0,   0,  12,   0,   0,   0,   0, 192,   0,   0,   0,   0,  63,
    255,  33,  16,   3,   0, 240, 255, 255, 240, 255,   0,   0,   0,   0,  32, 224,
      0,   0,   0, 160,   3, 224,   0, 224,   0, 224,   0,  96,   0, 128,   3,   0,
      0, 128,   0,   0,   0, 252,   0,   0,   0,   0,   0,  30,   0, 128,   0, 176,
      0,   0,   0,  48,   0,   0,   3,   0,   0,   0, 128, 255,   3,   0,   0,   0,
      0,   1,   0,   0, 255, 255,   3,   0,   0, 120,   0,   0,   0,   0,   8,   0,
     32,   0,   0,   0,   0,   0,   0,  56,   7,   0,   0,   0,   0,   0,  64,   0,
      0,   0,   0, 248,   0,  48,   0,   0, 255,  63,   0,   0,   0,   0,   1,   0,
      0,   0,   0, 192,   8,   0,   0,   0,  96,   0,   0,   0,   0,   0,   0,   6,
      0,   0,  24,   0,   0,   0,  96,   0,   0,   6,   0,   0, 192,  31,  31,   0,
     12,   0,   0,   0,   0,   0,  31,   0,   0, 128, 255, 255, 128, 227,   7, 248,
    231,  15,   0,   0,   0,  60,   0,   0,   0,   0, 127,   0,
};

/* Diacritic: 981 bytes. */

RE_UINT32 re_get_diacritic(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_diacritic_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_diacritic_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_diacritic_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_diacritic_stage_4[pos + f] << 5;
    pos += code;
    value = (re_diacritic_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Extender. */

static RE_UINT8 re_extender_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3,
};

static RE_UINT8 re_extender_stage_2[] = {
    0, 1, 2, 3, 2, 2, 4, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 5, 6, 2, 2, 2, 2, 2, 2, 2, 2, 2, 7,
    2, 2, 8, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 9, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_extender_stage_3[] = {
     0,  1,  2,  1,  1,  1,  3,  4,  1,  1,  1,  1,  1,  1,  5,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  6,  1,  7,  1,  8,  1,  1,  1,
     9,  1,  1,  1,  1,  1,  1,  1, 10,  1,  1,  1,  1,  1, 11,  1,
     1, 12, 13,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 14,
     1,  1,  1, 15,  1, 16,  1,  1,  1,  1,  1, 17,  1,  1,  1,  1,
};

static RE_UINT8 re_extender_stage_4[] = {
     0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  2,  0,  0,  0,  3,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  4,  0,  0,  5,  0,  0,  0,  5,  0,
     6,  0,  7,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  8,  0,  0,
     0,  9,  0, 10,  0,  0,  0,  0, 11, 12,  0,  0, 13,  0,  0, 14,
    15,  0,  0,  0,  0,  0,  0,  0, 16,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 17,  5,  0,  0,  0, 18,  0,  0, 19, 20,
     0,  0,  0, 18,  0,  0,  0,  0,  0,  0, 19,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 21,  0,  0,  0, 22,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_extender_stage_5[] = {
      0,   0,   0,   0,   0,   0, 128,   0,   0,   0,   3,   0,   1,   0,   0,   0,
      0,   0,   0,   4,  64,   0,   0,   0,   0,   4,   0,   0,   8,   0,   0,   0,
    128,   0,   0,   0,   0,   0,  64,   0,   0,   0,   0,   8,  32,   0,   0,   0,
      0,   0,  62,   0,   0,   0,   0,  96,   0,   0,   0, 112,   0,   0,  32,   0,
      0,  16,   0,   0,   0, 128,   0,   0,   0,   0,   1,   0,   0,   0,   0,  32,
      0,   0,  24,   0, 192,   1,   0,   0,  12,   0,   0,   0,
};

/* Extender: 414 bytes. */

RE_UINT32 re_get_extender(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_extender_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_extender_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_extender_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_extender_stage_4[pos + f] << 5;
    pos += code;
    value = (re_extender_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_Lowercase. */

static RE_UINT8 re_other_lowercase_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_other_lowercase_stage_2[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
};

static RE_UINT8 re_other_lowercase_stage_3[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2,
    4, 2, 5, 2, 2, 2, 6, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 7, 2, 8, 2, 2,
};

static RE_UINT8 re_other_lowercase_stage_4[] = {
     0,  0,  1,  0,  0,  0,  0,  0,  0,  0,  2,  3,  0,  4,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  5,  6,  7,  0,
     0,  8,  9,  0,  0, 10,  0,  0,  0,  0,  0, 11,  0,  0,  0,  0,
     0, 12,  0,  0,  0,  0,  0,  0,  0,  0, 13,  0,  0, 14,  0, 15,
     0,  0,  0,  0,  0, 16,  0,  0,
};

static RE_UINT8 re_other_lowercase_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4,   0,   4,
      0,   0,   0,   0,   0,   0, 255,   1,   3,   0,   0,   0,  31,   0,   0,   0,
     32,   0,   0,   0,   0,   0,   0,   4,   0,   0,   0,   0,   0, 240, 255, 255,
    255, 255, 255, 255, 255,   7,   0,   1,   0,   0,   0, 248, 255, 255, 255, 255,
      0,   0,   0,   0,   0,   0,   2, 128,   0,   0, 255,  31,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 255, 255,   0,   0, 255, 255, 255,   3,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  48,   0,   0,   0,  48,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,   0,   3,
      0,   0,   0, 240,   0,   0,   0,   0,
};

/* Other_Lowercase: 297 bytes. */

RE_UINT32 re_get_other_lowercase(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_lowercase_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_other_lowercase_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_other_lowercase_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_other_lowercase_stage_4[pos + f] << 6;
    pos += code;
    value = (re_other_lowercase_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_Uppercase. */

static RE_UINT8 re_other_uppercase_stage_1[] = {
    0, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1,
};

static RE_UINT8 re_other_uppercase_stage_2[] = {
    0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0,
};

static RE_UINT8 re_other_uppercase_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 0, 0, 0,
    0, 3, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_uppercase_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 2, 1, 0, 0, 3, 4, 4, 5, 0, 0, 0,
};

static RE_UINT8 re_other_uppercase_stage_5[] = {
      0,   0,   0,   0, 255, 255,   0,   0,   0,   0, 192, 255,   0,   0, 255, 255,
    255,   3, 255, 255, 255,   3,   0,   0,
};

/* Other_Uppercase: 162 bytes. */

RE_UINT32 re_get_other_uppercase(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_other_uppercase_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_other_uppercase_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_other_uppercase_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_other_uppercase_stage_4[pos + f] << 5;
    pos += code;
    value = (re_other_uppercase_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Noncharacter_Code_Point. */

static RE_UINT8 re_noncharacter_code_point_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_noncharacter_code_point_stage_2[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2,
};

static RE_UINT8 re_noncharacter_code_point_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2,
    0, 0, 0, 0, 0, 0, 0, 2,
};

static RE_UINT8 re_noncharacter_code_point_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
    0, 0, 0, 0, 0, 0, 0, 2,
};

static RE_UINT8 re_noncharacter_code_point_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 255, 255, 255, 255,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 192,
};

/* Noncharacter_Code_Point: 121 bytes. */

RE_UINT32 re_get_noncharacter_code_point(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_noncharacter_code_point_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_noncharacter_code_point_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_noncharacter_code_point_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_noncharacter_code_point_stage_4[pos + f] << 6;
    pos += code;
    value = (re_noncharacter_code_point_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_Grapheme_Extend. */

static RE_UINT8 re_other_grapheme_extend_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_other_grapheme_extend_stage_2[] = {
    0, 1, 2, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 4,
    1, 5, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 6, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_other_grapheme_extend_stage_3[] = {
    0, 0, 0, 0, 1, 2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    4, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 6, 0, 7, 8, 0, 0, 0, 0, 0,
    9, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_grapheme_extend_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  2,
     0,  0,  0,  0,  1,  2,  1,  2,  0,  0,  0,  3,  1,  2,  0,  4,
     5,  0,  0,  0,  0,  0,  0,  0,  6,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  7,  0,  0,  0,  0,  0,  1,  2,  0,  0,
     0,  0,  8,  0,  0,  0,  9,  0,  0,  0,  0,  0,  0, 10,  0,  0,
};

static RE_UINT8 re_other_grapheme_extend_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  64,
      0,   0, 128,   0,   0,   0,   0,   0,   4,   0,  96,   0,   0,   0,   0,   0,
      0, 128,   0, 128,   0,   0,   0,   0,   0,  48,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 192,   0,   0,   0,   0,   0, 192,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   1,  32,   0,   0,   0,   0,   0, 128,   0,   0,
      0,   0,   0,   0,  32, 192,   7,   0,
};

/* Other_Grapheme_Extend: 289 bytes. */

RE_UINT32 re_get_other_grapheme_extend(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_grapheme_extend_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_other_grapheme_extend_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_other_grapheme_extend_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_other_grapheme_extend_stage_4[pos + f] << 6;
    pos += code;
    value = (re_other_grapheme_extend_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* IDS_Binary_Operator. */

static RE_UINT8 re_ids_binary_operator_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_ids_binary_operator_stage_2[] = {
    0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_ids_binary_operator_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
};

static RE_UINT8 re_ids_binary_operator_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
};

static RE_UINT8 re_ids_binary_operator_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 243,  15,
};

/* IDS_Binary_Operator: 97 bytes. */

RE_UINT32 re_get_ids_binary_operator(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_ids_binary_operator_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_ids_binary_operator_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_ids_binary_operator_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_ids_binary_operator_stage_4[pos + f] << 6;
    pos += code;
    value = (re_ids_binary_operator_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* IDS_Trinary_Operator. */

static RE_UINT8 re_ids_trinary_operator_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_ids_trinary_operator_stage_2[] = {
    0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_ids_trinary_operator_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
};

static RE_UINT8 re_ids_trinary_operator_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
};

static RE_UINT8 re_ids_trinary_operator_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 12,  0,
};

/* IDS_Trinary_Operator: 97 bytes. */

RE_UINT32 re_get_ids_trinary_operator(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_ids_trinary_operator_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_ids_trinary_operator_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_ids_trinary_operator_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_ids_trinary_operator_stage_4[pos + f] << 6;
    pos += code;
    value = (re_ids_trinary_operator_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Radical. */

static RE_UINT8 re_radical_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_radical_stage_2[] = {
    0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_radical_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
};

static RE_UINT8 re_radical_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 1, 2, 2, 3, 2, 2, 2, 2, 2, 2, 4, 0,
};

static RE_UINT8 re_radical_stage_5[] = {
      0,   0,   0,   0, 255, 255, 255, 251, 255, 255, 255, 255, 255, 255,  15,   0,
    255, 255,  63,   0,
};

/* Radical: 117 bytes. */

RE_UINT32 re_get_radical(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_radical_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_radical_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_radical_stage_3[pos + f] << 4;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_radical_stage_4[pos + f] << 5;
    pos += code;
    value = (re_radical_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Unified_Ideograph. */

static RE_UINT8 re_unified_ideograph_stage_1[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_unified_ideograph_stage_2[] = {
    0, 0, 0, 1, 2, 3, 3, 3, 3, 4, 0, 0, 0, 0, 0, 5,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 6, 7, 0, 0, 0, 0,
};

static RE_UINT8 re_unified_ideograph_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 3, 0, 0, 0, 0, 0, 4, 0, 0,
    1, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1, 6, 7, 0, 0, 0,
};

static RE_UINT8 re_unified_ideograph_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2, 0, 1, 1, 1, 1, 1, 1, 1, 3,
    4, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 5, 1, 1, 1, 1,
    1, 1, 1, 1, 6, 1, 1, 1, 7, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_unified_ideograph_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255,  63,   0, 255,  31,   0,   0,   0,   0,   0,   0,
      0, 192,  26, 128, 154,   3,   0,   0, 255, 255, 127,   0,   0,   0,   0,   0,
    255, 255, 255, 255, 255, 255,  31,   0, 255, 255, 255,  63,   0,   0,   0,   0,
};

/* Unified_Ideograph: 257 bytes. */

RE_UINT32 re_get_unified_ideograph(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_unified_ideograph_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_unified_ideograph_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_unified_ideograph_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_unified_ideograph_stage_4[pos + f] << 6;
    pos += code;
    value = (re_unified_ideograph_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_Default_Ignorable_Code_Point. */

static RE_UINT8 re_other_default_ignorable_code_point_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1,
    1,
};

static RE_UINT8 re_other_default_ignorable_code_point_stage_2[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    6, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
};

static RE_UINT8 re_other_default_ignorable_code_point_stage_3[] = {
    0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0, 3, 0, 0, 0, 0,
    4, 0, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 6,
    7, 8, 8, 8, 8, 8, 8, 8,
};

static RE_UINT8 re_other_default_ignorable_code_point_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,
     0,  0,  0,  0,  0,  2,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,
     0,  4,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  5,  0,  0,
     0,  0,  0,  0,  0,  0,  6,  7,  8,  0,  9,  9,  0,  0,  0, 10,
     9,  9,  9,  9,  9,  9,  9,  9,
};

static RE_UINT8 re_other_default_ignorable_code_point_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0, 128,   0,   0,   0,   0,   0,   0,
      0,   0,   0, 128,   1,   0,   0,   0,   0,   0,   0,   0,   0,   0,  48,   0,
      0,   0,   0,   0,  32,   0,   0,   0,   0,   0,   0,   0,  16,   0,   0,   0,
      0,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,   0,   0, 255,   1,
    253, 255, 255, 255,   0,   0,   0,   0, 255, 255, 255, 255, 255, 255, 255, 255,
      0,   0,   0,   0,   0,   0, 255, 255,
};

/* Other_Default_Ignorable_Code_Point: 281 bytes. */

RE_UINT32 re_get_other_default_ignorable_code_point(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_default_ignorable_code_point_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_other_default_ignorable_code_point_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_other_default_ignorable_code_point_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_other_default_ignorable_code_point_stage_4[pos + f] << 6;
    pos += code;
    value = (re_other_default_ignorable_code_point_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Deprecated. */

static RE_UINT8 re_deprecated_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1,
    1, 1,
};

static RE_UINT8 re_deprecated_stage_2[] = {
    0, 1, 2, 3, 4, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    5, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
};

static RE_UINT8 re_deprecated_stage_3[] = {
    0, 1, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 3,
    0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 0, 0,
    5, 0, 0, 6, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_deprecated_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0,
    0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0,
    0, 6, 0, 0, 0, 0, 0, 0, 7, 8, 8, 8, 0, 0, 0, 0,
};

static RE_UINT8 re_deprecated_stage_5[] = {
      0,   0,   0,   0,   0,   2,   0,   0,   0,   0,   8,   0,   0,   0, 128,   2,
     24,   0,   0,   0,   0, 252,   0,   0,   0,   6,   0,   0,   2,   0,   0,   0,
    255, 255, 255, 255,
};

/* Deprecated: 230 bytes. */

RE_UINT32 re_get_deprecated(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_deprecated_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_deprecated_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_deprecated_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_deprecated_stage_4[pos + f] << 5;
    pos += code;
    value = (re_deprecated_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Soft_Dotted. */

static RE_UINT8 re_soft_dotted_stage_1[] = {
    0, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1,
};

static RE_UINT8 re_soft_dotted_stage_2[] = {
    0, 1, 1, 2, 3, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 5, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_soft_dotted_stage_3[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
     5,  5,  5,  5,  5,  6,  7,  5,  8,  9,  5,  5,  5,  5,  5,  5,
     5,  5,  5,  5, 10,  5,  5,  5,  5,  5,  5,  5, 11, 12, 13,  5,
};

static RE_UINT8 re_soft_dotted_stage_4[] = {
     0,  0,  0,  1,  0,  0,  0,  0,  0,  2,  0,  0,  0,  0,  0,  0,
     0,  0,  3,  4,  5,  6,  0,  0,  0,  0,  0,  0,  0,  0,  0,  7,
     0,  0,  8,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  9, 10, 11,  0,  0,  0, 12,  0,  0,  0,  0, 13,  0,
     0,  0,  0, 14,  0,  0,  0,  0,  0,  0, 15,  0,  0,  0,  0,  0,
     0,  0,  0, 16,  0,  0,  0,  0,  0, 17, 18,  0, 19, 20,  0, 21,
     0, 22, 23,  0, 24,  0, 17, 18,  0, 19, 20,  0, 21,  0,  0,  0,
};

static RE_UINT8 re_soft_dotted_stage_5[] = {
      0,   0,   0,   0,   0,   6,   0,   0,   0, 128,   0,   0,   0,   2,   0,   0,
      0,   1,   0,   0,   0,   0,   0,  32,   0,   0,   4,   0,   0,   0,   8,   0,
      0,   0,  64,   1,   4,   0,   0,   0,   0,   0,  64,   0,  16,   1,   0,   0,
      0,  32,   0,   0,   0,   8,   0,   0,   0,   0,   2,   0,   0,   3,   0,   0,
      0,   0,   0,  16,  12,   0,   0,   0,   0,   0, 192,   0,   0,  12,   0,   0,
      0,   0,   0, 192,   0,   0,  12,   0, 192,   0,   0,   0,   0,   0,   0,  12,
      0, 192,   0,   0,
};

/* Soft_Dotted: 342 bytes. */

RE_UINT32 re_get_soft_dotted(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_soft_dotted_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_soft_dotted_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_soft_dotted_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_soft_dotted_stage_4[pos + f] << 5;
    pos += code;
    value = (re_soft_dotted_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Logical_Order_Exception. */

static RE_UINT8 re_logical_order_exception_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_logical_order_exception_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_logical_order_exception_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 2, 0, 0,
};

static RE_UINT8 re_logical_order_exception_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0,
    0, 0, 2, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_logical_order_exception_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0, 31,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 96, 26,
};

/* Logical_Order_Exception: 121 bytes. */

RE_UINT32 re_get_logical_order_exception(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_logical_order_exception_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_logical_order_exception_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_logical_order_exception_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_logical_order_exception_stage_4[pos + f] << 6;
    pos += code;
    value = (re_logical_order_exception_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_ID_Start. */

static RE_UINT8 re_other_id_start_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_other_id_start_stage_2[] = {
    0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_id_start_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    1, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_id_start_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0,
    0, 0, 2, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_id_start_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0, 64,  0,  0,
     0,  0,  0, 24,  0,  0,  0,  0,
};

/* Other_ID_Start: 113 bytes. */

RE_UINT32 re_get_other_id_start(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_id_start_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_other_id_start_stage_2[pos + f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_other_id_start_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_other_id_start_stage_4[pos + f] << 6;
    pos += code;
    value = (re_other_id_start_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Other_ID_Continue. */

static RE_UINT8 re_other_id_continue_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_other_id_continue_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_other_id_continue_stage_3[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 3, 2, 2, 4, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_other_id_continue_stage_4[] = {
    0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 4,
};

static RE_UINT8 re_other_id_continue_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 128,   0,
    128,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 254,   3,   0,
      0,   0,   0,   4,   0,   0,   0,   0,
};

/* Other_ID_Continue: 145 bytes. */

RE_UINT32 re_get_other_id_continue(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_id_continue_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_other_id_continue_stage_2[pos + f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_other_id_continue_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_other_id_continue_stage_4[pos + f] << 6;
    pos += code;
    value = (re_other_id_continue_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* STerm. */

static RE_UINT8 re_sterm_stage_1[] = {
    0, 1, 2, 3, 4, 5, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1,
};

static RE_UINT8 re_sterm_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  3,  3,  9, 10,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3, 11, 12,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3, 13,
     3,  3, 14,  3, 15, 16,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3, 17,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3, 18,
};

static RE_UINT8 re_sterm_stage_3[] = {
     0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  3,  4,  5,  6,
     1,  1,  7,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     8,  1,  1,  1,  1,  1,  9,  1,  1,  1,  1,  1, 10,  1, 11,  1,
    12,  1, 13,  1,  1, 14, 15,  1, 16,  1,  1,  1,  1,  1,  1,  1,
    17,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 18,  1,  1,  1,
    19,  1,  1,  1,  1,  1,  1,  1,  1, 20,  1,  1, 21, 22,  1,  1,
    23, 24, 25, 26, 27, 28,  1, 29,  1,  1,  1,  1, 30,  1, 31,  1,
     1,  1,  1,  1, 32,  1,  1,  1, 33, 34, 35, 36, 37,  1,  1,  1,
     1,  1,  1, 38, 39,  1,  1,  1,  1,  1,  1,  1, 40, 41, 42,  1,
     1,  3,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_sterm_stage_4[] = {
     0,  1,  0,  0,  0,  0,  0,  0,  2,  0,  0,  0,  3,  0,  0,  0,
     0,  0,  4,  0,  5,  0,  0,  0,  0,  0,  0,  6,  0,  0,  0,  7,
     0,  0,  8,  0,  0,  0,  0,  9,  0,  0,  0, 10,  0, 11,  0,  0,
    12,  0,  0,  0,  0,  0,  7,  0,  0, 13,  0,  0,  0,  0, 14,  0,
     0, 15,  0, 16,  0, 17, 18,  0,  0, 19,  0,  0, 20,  0,  0,  0,
     0,  0,  0,  3, 21,  0,  0,  0,  0,  0,  0, 22,  0,  0,  0, 23,
     0,  0, 21,  0,  0, 24,  0,  0,  0,  0, 25,  0,  0,  0, 26,  0,
     0,  0,  0, 27,  0,  0,  0, 28,  0,  0, 29,  0,  1,  0,  0, 30,
     0,  0, 23,  0,  0,  0, 31,  0,  0, 16, 32,  0,  0,  0, 33,  0,
     0,  0, 34,  0,  0, 35,  0,  0,  0,  0, 36,  0,  0,  0, 37,  0,
     0,  0,  0, 21,  0,  0,  0, 38,  0, 39, 40,  0,
};

static RE_UINT8 re_sterm_stage_5[] = {
      0,   0,   0,   0,   2,  64,   0, 128,   0,   2,   0,   0,   0,   0,   0, 128,
      0,   0,  16,   0,   7,   0,   0,   0,   0,   0,   0,   2,  48,   0,   0,   0,
      0,  12,   0,   0, 132,   1,   0,   0,   0,  64,   0,   0,   0,   0,  96,   0,
      8,   2,   0,   0,   0,  15,   0,   0,   0,   0,   0, 204,   0,   0,   0,  24,
      0,   0,   0, 192,   0,   0,   0,  48, 128,   3,   0,   0,   0,  64,   0,  16,
      4,   0,   0,   0,   0, 192,   0,   0,   0,   0, 136,   0,   0,   0, 192,   0,
      0, 128,   0,   0,   0,   3,   0,   0,   0,   0,   0, 224,   0,   0,   3,   0,
      0,   8,   0,   0,   0,   0, 196,   0,   2,   0,   0,   0, 128,   1,   0,   0,
      3,   0,   0,   0,  14,   0,   0,   0,  96,  32,   0,   0,   0,   0,   0,  27,
     12,   2,   0,   0,   6,   0,   0,   0,   0,   0,  32,   0,   0,   0, 128,   1,
     16,   0,   0,   0,
};

/* STerm: 668 bytes. */

RE_UINT32 re_get_sterm(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 14;
    code = ch ^ (f << 14);
    pos = (RE_UINT32)re_sterm_stage_1[f] << 4;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_sterm_stage_2[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_sterm_stage_3[pos + f] << 2;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_sterm_stage_4[pos + f] << 5;
    pos += code;
    value = (re_sterm_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Variation_Selector. */

static RE_UINT8 re_variation_selector_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1,
    1,
};

static RE_UINT8 re_variation_selector_stage_2[] = {
    0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_variation_selector_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 2, 3, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_variation_selector_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0,
    2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 4,
};

static RE_UINT8 re_variation_selector_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,  56,   0,   0,   0,   0,   0,   0,
    255, 255,   0,   0,   0,   0,   0,   0, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255,   0,   0,
};

/* Variation_Selector: 169 bytes. */

RE_UINT32 re_get_variation_selector(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_variation_selector_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_variation_selector_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_variation_selector_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_variation_selector_stage_4[pos + f] << 6;
    pos += code;
    value = (re_variation_selector_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Pattern_White_Space. */

static RE_UINT8 re_pattern_white_space_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_pattern_white_space_stage_2[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_pattern_white_space_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_pattern_white_space_stage_4[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    3, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_pattern_white_space_stage_5[] = {
      0,  62,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     32,   0,   0,   0,   0,   0,   0,   0,   0, 192,   0,   0,   0,   3,   0,   0,
};

/* Pattern_White_Space: 129 bytes. */

RE_UINT32 re_get_pattern_white_space(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_pattern_white_space_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_pattern_white_space_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_pattern_white_space_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_pattern_white_space_stage_4[pos + f] << 6;
    pos += code;
    value = (re_pattern_white_space_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Pattern_Syntax. */

static RE_UINT8 re_pattern_syntax_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_pattern_syntax_stage_2[] = {
    0, 1, 1, 1, 2, 3, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 5,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_pattern_syntax_stage_3[] = {
     0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     2,  3,  4,  4,  5,  4,  4,  6,  4,  4,  4,  4,  1,  1,  7,  1,
     8,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  9, 10,  1,
};

static RE_UINT8 re_pattern_syntax_stage_4[] = {
     0,  1,  2,  2,  0,  3,  4,  4,  0,  0,  0,  0,  0,  0,  0,  0,
     5,  6,  7,  0,  0,  0,  0,  0,  0,  0,  0,  0,  5,  8,  8,  8,
     8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  0,  0,  0,  0,  0,
     8,  8,  8,  9, 10,  8,  8,  8,  8,  8,  8,  8,  0,  0,  0,  0,
    11, 12,  0,  0,  0,  0,  0,  0,  0, 13,  0,  0,  0,  0,  0,  0,
     0,  0, 14,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_pattern_syntax_stage_5[] = {
      0,   0,   0,   0, 254, 255,   0, 252,   1,   0,   0, 120, 254,  90,  67, 136,
      0,   0, 128,   0,   0,   0, 255, 255, 255,   0, 255, 127, 254, 255, 239, 127,
    255, 255, 255, 255, 255, 255,  63,   0,   0,   0, 240, 255,  14, 255, 255, 255,
      1,   0,   1,   0,   0,   0,   0, 192,  96,   0,   0,   0,
};

/* Pattern_Syntax: 277 bytes. */

RE_UINT32 re_get_pattern_syntax(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_pattern_syntax_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_pattern_syntax_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_pattern_syntax_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_pattern_syntax_stage_4[pos + f] << 5;
    pos += code;
    value = (re_pattern_syntax_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Hangul_Syllable_Type. */

static RE_UINT8 re_hangul_syllable_type_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_hangul_syllable_type_stage_2[] = {
    0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 2, 3, 4, 5, 6, 7, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_hangul_syllable_type_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  1,  2,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  3,  0,  0,  0,  0,  0,  4,  5,  6,  7,  8,  9, 10,  4,
     5,  6,  7,  8,  9, 10,  4,  5,  6,  7,  8,  9, 10,  4,  5,  6,
     7,  8,  9, 10,  4,  5,  6,  7,  8,  9, 10,  4,  5,  6,  7,  8,
     9, 10,  4,  5,  6,  7,  8,  9, 10,  4,  5,  6,  7,  8,  9, 10,
     4,  5,  6,  7,  8,  9, 10,  4,  5,  6,  7,  8,  9, 10,  4,  5,
     6,  7,  8,  9, 10,  4,  5,  6,  7,  8,  9, 10,  4,  5,  6, 11,
};

static RE_UINT8 re_hangul_syllable_type_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  4,
     5,  6,  6,  7,  6,  6,  6,  5,  6,  6,  7,  6,  6,  6,  5,  6,
     6,  7,  6,  6,  6,  5,  6,  6,  7,  6,  6,  6,  5,  6,  6,  7,
     6,  6,  6,  5,  6,  6,  7,  6,  6,  6,  5,  6,  6,  7,  6,  6,
     6,  5,  6,  6,  7,  6,  6,  6,  5,  6,  6,  7,  6,  6,  6,  5,
     6,  6,  7,  6,  6,  6,  5,  6,  6,  7,  6,  6,  6,  5,  6,  6,
     7,  6,  6,  6,  5,  6,  6,  7,  6,  6,  6,  5,  6,  6,  7,  6,
     6,  6,  5,  6,  6,  7,  6,  6,  6,  5,  6,  6,  7,  6,  6,  6,
     6,  5,  6,  6,  8,  0,  2,  2,  9, 10,  3,  3,  3,  3,  3, 11,
};

static RE_UINT8 re_hangul_syllable_type_stage_5[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3,
    1, 1, 1, 1, 1, 0, 0, 0, 4, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 4, 5, 5, 5,
    5, 5, 5, 5, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 0,
    0, 0, 0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0,
};

/* Hangul_Syllable_Type: 497 bytes. */

RE_UINT32 re_get_hangul_syllable_type(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_hangul_syllable_type_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_hangul_syllable_type_stage_2[pos + f] << 4;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_hangul_syllable_type_stage_3[pos + f] << 4;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_hangul_syllable_type_stage_4[pos + f] << 3;
    value = re_hangul_syllable_type_stage_5[pos + code];

    return value;
}

/* Bidi_Class. */

static RE_UINT8 re_bidi_class_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  5,  6,  5,  5,  5,  5,  7,
     8,  9,  5,  5,  5,  5, 10,  5,  5,  5,  5, 11,  5, 12, 13, 14,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
    16,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
};

static RE_UINT8 re_bidi_class_stage_2[] = {
      0,   1,   2,   2,   2,   3,   4,   5,   2,   6,   2,   7,   8,   9,  10,  11,
     12,  13,  14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  29,   2,   2,   2,   2,  30,  31,  32,   2,   2,   2,   2,  33,  34,  35,
     36,  37,  38,  39,  40,  41,  42,  43,  44,  45,   2,  46,   2,   2,   2,  47,
     48,  49,  50,  51,  52,  53,  54,  55,  56,  57,  53,  53,  53,  58,  53,  53,
      2,   2,  53,  53,  53,  53,  59,  60,   2,  61,  62,  63,  64,  65,  53,  66,
     67,  68,   2,  69,  70,  71,  72,  73,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  74,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,  75,   2,   2,  76,  77,  78,  79,
     80,  81,  82,  83,  84,  85,   2,  86,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,  87,  88,  88,  88,  89,  90,  91,  92,  93,  94,
      2,   2,  95,  96,   2,  97,  98,   2,   2,   2,   2,   2,   2,   2,   2,   2,
     99,  99, 100,  99, 101, 102, 103,  99,  99,  99,  99,  99, 104,  99,  99,  99,
    105, 106, 107, 108, 109, 110, 111,   2,   2, 112,   2, 113, 114, 115,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2, 116, 117,   2,   2,   2,   2,   2,   2,   2,   2, 118,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2, 119,   2,   2,   2,   2,   2,   2,
      2,   2, 120, 121, 122,   2, 123,   2,   2,   2,   2,   2,   2, 124, 125, 126,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
     99, 127,  99,  99,  99,  99,  99,  99,  99,  99,  99,  99,  88, 128,  99,  99,
    129, 130, 131,   2,   2,   2, 132, 133,  53, 134, 135, 136, 137, 138, 139, 140,
    141, 142,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 143,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 143,
    144, 144, 145, 146, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144,
    144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144, 144,
};

static RE_UINT8 re_bidi_class_stage_3[] = {
      0,   1,   2,   3,   4,   5,   4,   6,   7,   8,   9,  10,  11,  12,  11,  12,
     11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  13,  14,  14,  15,  16,
     17,  17,  17,  17,  17,  17,  17,  18,  19,  11,  11,  11,  11,  11,  11,  20,
     21,  11,  11,  11,  11,  11,  11,  11,  22,  23,  17,  24,  25,  26,  26,  26,
     27,  28,  29,  29,  30,  17,  31,  32,  29,  29,  29,  29,  29,  33,  34,  35,
     29,  36,  29,  17,  28,  29,  29,  29,  29,  29,  37,  32,  26,  26,  38,  39,
     26,  40,  41,  26,  26,  42,  26,  26,  26,  26,  29,  29,  29,  29,  43,  17,
     44,  11,  11,  45,  46,  47,  48,  11,  49,  11,  11,  50,  51,  11,  48,  52,
     53,  11,  11,  50,  54,  49,  11,  55,  53,  11,  11,  50,  56,  11,  48,  57,
     49,  11,  11,  58,  51,  59,  48,  11,  60,  11,  11,  11,  61,  11,  11,  62,
     63,  11,  11,  64,  65,  66,  48,  67,  49,  11,  11,  50,  68,  11,  48,  11,
     49,  11,  11,  11,  51,  11,  48,  11,  11,  11,  11,  11,  69,  70,  11,  11,
     11,  11,  11,  71,  72,  11,  11,  11,  11,  11,  11,  73,  74,  11,  11,  11,
     11,  75,  11,  76,  11,  11,  11,  77,  78,  79,  17,  80,  59,  11,  11,  11,
     11,  11,  81,  82,  11,  83,  63,  84,  85,  86,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  81,  11,  11,  11,  87,  11,  11,  11,  11,  11,  11,
      4,  11,  11,  11,  11,  11,  11,  11,  88,  89,  11,  11,  11,  11,  11,  11,
     11,  90,  11,  90,  11,  48,  11,  48,  11,  11,  11,  91,  92,  93,  11,  87,
     94,  11,  11,  11,  11,  11,  11,  11,  11,  11,  95,  11,  11,  11,  11,  11,
     11,  11,  96,  97,  98,  11,  11,  11,  11,  11,  11,  11,  11,  99,  16,  16,
     11, 100,  11,  11,  11, 101, 102, 103,  11,  11,  11, 104,  11,  11,  11,  11,
    105,  11,  11, 106,  60,  11, 107, 105, 108,  11, 109,  11,  11,  11, 110, 108,
     11,  11, 111, 112,  11,  11,  11,  11,  11,  11,  11,  11,  11, 113, 114, 115,
     11,  11,  11,  11,  17,  17,  17, 116,  11,  11,  11, 117, 118, 119, 119, 120,
    121,  16, 122, 123, 124, 125, 126, 127, 128,  11, 129, 129, 129,  17,  17,  63,
    130, 131, 132, 133, 134,  16,  11,  11, 135,  16,  16,  16,  16,  16,  16,  16,
     16, 136,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16, 137,  11,  11,  11,   5,  16, 138,  16,  16,  16,  16,  16, 139,
     16,  16, 140,  11, 139,  11,  16,  16, 141, 142,  11,  11,  11,  11, 143,  16,
     16,  16, 144,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16, 145,
     16, 146,  16, 147, 148, 149,  11,  11,  11,  11,  11,  11,  11,  11, 150, 151,
     11,  11,  11,  11,  11,  11,  11, 152,  11,  11,  11,  11,  11,  11,  17,  17,
     16,  16,  16,  16, 153,  11,  11,  11,  16, 154,  16,  16,  16,  16,  16, 155,
     16,  16,  16,  16,  16, 137,  11, 156, 157,  16, 158, 159,  11,  11,  11,  11,
     11, 160,   4,  11,  11,  11,  11, 161,  11,  11,  11,  11,  16,  16, 155,  11,
     11, 120,  11,  11,  11,  16,  11, 162,  11,  11,  11, 163, 164,  11,  11,  11,
     11,  11,  11,  11,  11,  11,  11, 165,  11,  11,  11,  11,  11,  99,  11, 166,
     11,  11,  11,  11,  16,  16,  16,  16,  11,  16,  16,  16, 140,  11,  11,  11,
    119,  11,  11,  11,  11,  11, 152, 167,  11, 152,  11,  11,  11,  11,  11, 108,
     16,  16, 149,  11,  11,  11,  11,  11, 168,  11,  11,  11,  11,  11,  11,  11,
    169,  11, 170, 171,  11,  11,  11, 172,  11,  11,  11,  11, 173,  11,  17, 108,
     11,  11, 174,  11, 175, 108,  11,  11,  44,  11,  11, 176,  11,  11, 177,  11,
     11,  11, 178, 179, 180,  11,  11,  50,  11,  11,  11, 181,  49,  11,  68,  59,
     11,  11,  11,  11,  11,  11, 182,  11,  11, 183, 184,  26,  26,  29,  29,  29,
     29,  29,  29,  29,  29,  29,  29,  29,  29,  29,  29, 185,  29,  29,  29,  29,
     29,  29,  29,  29,  29,   8,   8, 186,  17,  87, 187,  16,  16, 188, 189,  29,
     29,  29,  29,  29,  29,  29,  29, 190, 191,   3,   4,   5,   4,   5, 137,  11,
     11,  11,  11,  11,  11,  11, 192, 193, 194,  11,  11,  11,  16,  16,  16,  16,
    195, 156,   4,  11,  11,  11,  11,  86,  11,  11,  11,  11,  11,  11, 196, 142,
     11,  11,  11,  11,  11,  11,  11, 197,  26,  26,  26,  26,  26,  26,  26,  26,
     26, 198,  26,  26,  26,  26,  26,  26, 199,  26,  26, 200,  26,  26,  26,  26,
     26,  26,  26,  26,  26,  26, 201,  26,  26,  26,  26, 202,  26,  26,  26,  26,
     26,  26,  26,  26,  26,  26, 203, 204,  49,  11,  11, 205, 206,  14, 137, 152,
    108,  11,  11, 207,  11,  11,  11,  11,  44,  11, 208, 209,  11,  11,  11, 210,
    108,  11,  11, 211,  11,  11,  11,  11,  11,  11, 152, 212,  11,  11,  11,  11,
     11,  11,  11,  11,  11, 152, 213,  11,  49,  11,  11,  50,  63,  11, 214, 209,
     11,  11,  11, 215, 216,  11,  11,  11,  11,  11,  11, 217,  63,  11,  11,  11,
     11,  11,  11, 218,  63,  11,  11,  11,  11,  11, 219, 220,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  11,  11, 209,  11,  11,  11, 206,  11,  11,  11,  11,
    152,  44,  11,  11,  11,  11,  11,  11,  11, 221, 222,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  11, 223, 224, 225,  11, 226,  11,  11,  11,  11,  11,
     16,  16,  16,  16, 227,  11,  11,  11,  16,  16,  16,  16,  16, 140,  11,  11,
     11,  11,  11,  11,  11, 161,  11,  11,  11, 228,  11,  11, 166,  11,  11,  11,
    135,  11,  11,  11, 229, 230, 230, 230,  26,  26,  26,  26,  26, 231,  26,  26,
     29,  29,  29,  29,  29,  29,  29, 232,  16,  16, 156,  16,  16,  16,  16,  16,
     16, 155, 233, 163, 163, 163,  16, 137, 234,  11,  11,  11,  11,  11, 133,  11,
     16,  16, 195,  16,  16,  16,  16, 235,  16,  16,  16,  16, 233, 236,  16, 237,
     16,  16,  16,  16,  16,  16,  16, 233,  16,  16,  16,  16, 139,  16,  16, 154,
     16,  16, 238,  16,  16,  16,  16,  16,  16,  16,  16,  16, 239,  16,  16,  16,
     16,  16,  16,  16,  16,  11, 195, 155,  16,  16,  16,  16,  16,  16,  16, 155,
     16,  16,  16,  16,  16, 240,  11,  11, 156,  16,  16,  16, 237,  87,  16,  16,
    237,  16, 235,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11, 241,
      8,   8,   8,   8,   8,   8,   8,   8,  17,  17,  17,  17,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17,   8,
};

static RE_UINT8 re_bidi_class_stage_4[] = {
      0,   0,   1,   2,   0,   0,   0,   3,   4,   5,   6,   7,   8,   8,   9,  10,
     11,  12,  12,  12,  12,  12,  13,  10,  12,  12,  13,  14,   0,  15,   0,   0,
      0,   0,   0,   0,  16,   5,  17,  18,  19,  20,  21,  10,  12,  12,  12,  12,
     12,  13,  12,  12,  12,  12,  22,  12,  23,  10,  10,  10,  12,  24,  10,  17,
     10,  10,  10,  10,  25,  25,  25,  25,  12,  26,  12,  27,  12,  17,  12,  12,
     12,  27,  12,  12,  28,  25,  29,  12,  12,  12,  27,  30,  31,  25,  25,  25,
     25,  25,  25,  32,  33,  32,  34,  34,  34,  34,  34,  34,  35,  36,  37,  38,
     25,  25,  39,  40,  40,  40,  40,  40,  40,  40,  41,  25,  35,  35,  42,  43,
     44,  40,  40,  40,  40,  45,  25,  46,  25,  47,  48,  49,   8,   8,  50,  40,
     51,  40,  40,  40,  40,  45,  25,  25,  34,  34,  52,  25,  25,  53,  54,  34,
     34,  55,  32,  25,  25,  31,  31,  56,  34,  34,  31,  34,  40,  25,  25,  25,
     57,  12,  12,  12,  12,  12,  58,  59,  60,  25,  59,  61,  60,  25,  12,  12,
     62,  12,  12,  12,  61,  12,  12,  12,  12,  12,  12,  59,  60,  59,  12,  61,
     63,  12,  64,  12,  65,  12,  12,  12,  65,  28,  66,  29,  29,  61,  12,  12,
     60,  67,  59,  61,  68,  12,  12,  12,  12,  12,  12,  66,  12,  58,  12,  12,
     58,  12,  12,  12,  59,  12,  12,  61,  13,  10,  69,  12,  59,  12,  12,  12,
     12,  12,  12,  62,  59,  62,  70,  29,  12,  65,  12,  12,  12,  12,  10,  71,
     12,  12,  12,  29,  12,  12,  58,  12,  62,  72,  12,  12,  61,  25,  57,  64,
     12,  28,  25,  57,  61,  25,  67,  59,  12,  12,  25,  29,  12,  12,  29,  12,
     12,  73,  74,  26,  60,  25,  25,  57,  25,  70,  12,  60,  25,  25,  60,  25,
     25,  25,  25,  59,  12,  12,  12,  60,  70,  25,  65,  65,  12,  12,  29,  62,
     60,  59,  12,  12,  58,  65,  12,  61,  12,  12,  12,  61,  10,  10,  26,  12,
     75,  12,  12,  12,  12,  12,  13,  11,  62,  59,  12,  12,  12,  67,  25,  29,
     12,  58,  60,  25,  25,  12,  64,  61,  10,  10,  76,  77,  12,  12,  61,  12,
     57,  28,  59,  12,  58,  12,  60,  12,  11,  26,  12,  12,  12,  12,  12,  23,
     12,  28,  66,  12,  12,  58,  25,  57,  72,  60,  25,  59,  28,  25,  25,  66,
     25,  25,  25,  57,  25,  12,  12,  12,  12,  70,  57,  59,  12,  12,  28,  25,
     29,  12,  12,  12,  62,  29,  67,  29,  12,  58,  29,  73,  12,  12,  12,  25,
     25,  62,  12,  12,  57,  25,  25,  25,  70,  25,  59,  61,  12,  59,  29,  12,
     25,  29,  12,  25,  12,  12,  12,  78,  26,  12,  12,  24,  12,  12,  12,  24,
     12,  12,  12,  22,  79,  79,  80,  81,  10,  10,  82,  83,  84,  85,  10,  10,
     10,  86,  10,  10,  10,  10,  10,  87,   0,  88,  89,   0,  90,   8,  91,  71,
      8,   8,  91,  71,  84,  84,  84,  84,  17,  71,  26,  12,  12,  20,  11,  23,
     10,  78,  92,  93,  12,  12,  23,  12,  10,  11,  23,  26,  12,  12,  92,  12,
     94,  10,  10,  10,  10,  26,  12,  12,  10,  20,  10,  10,  10,  10,  71,  12,
     10,  71,  12,  12,  10,  10,   8,   8,   8,   8,   8,  12,  12,  12,  23,  10,
     10,  10,  10,  24,  10,  23,  10,  10,  10,  26,  10,  10,  10,  10,  26,  24,
     10,  10,  20,  10,  26,  12,  12,  12,  12,  24,  71,  28,  29,  12,  24,  10,
     12,  12,  12,  28,  71,  12,  12,  12,  10,  10,  17,  10,  10,  12,  12,  12,
     10,  10,  10,  12,  95,  11,  10,  10,  11,  12,  62,  29,  11,  23,  12,  24,
     12,  12,  96,  11,  12,  12,  13,  12,  12,  12,  12,  71,  24,  10,  10,  10,
     12,  12,  12,  10,  12,  13,  71,  12,  12,  12,  12,  13,  97,  25,  25,  98,
     12,  12,  11,  12,  58,  58,  28,  12,  12,  65,  10,  12,  12,  12,  99,  12,
     12,  10,  12,  12,  12,  59,  12,  12,  12,  62,  25,  29,  12,  28,  25,  25,
     28,  62,  29,  59,  12,  61,  12,  12,  12,  12,  60,  57,  65,  65,  12,  12,
     28,  12,  12,  59,  70,  66,  59,  62,  12,  61,  59,  61,  12,  12,  12, 100,
     34,  34, 101,  34,  40,  40,  40, 102,  40,  40,  40, 103,  25,  25,  25,  29,
    104, 105,  10, 106, 107,  71, 108,  12,  40,  40,  40, 109,  30,   5,   6,   7,
      5, 110,  10,  71,   0,   0, 111, 112,  92,  12,  12,  12,  10,  10,  10,  11,
    113,   8,   8,   8,  12,  62,  57,  12,  34,  34,  34, 114,  31,  33,  34,  25,
     34,  34, 115,  52,  34,  33,  34,  34,  34,  34, 116,  10,  35,  35,  35,  35,
     35,  35,  35, 117,  12,  12,  25,  25,  25,  57,  12,  12,  28,  57,  65,  12,
     12,  28,  25,  60,  25,  59,  12,  12,  28,  12,  12,  12,  12,  62,  25,  57,
     29,  70,  12,  12,  28,  25,  57,  12,  12,  62,  25,  59,  28,  25,  72,  28,
     70,  12,  12,  12,  62,  29,  12,  67,  28,  25,  57,  73,  12,  12,  28,  61,
     25,  67,  12,  12,  12,  12,  12,  65,   0,  12,  12,  12,  12,  28,  29,  12,
    118,   0, 119,  25,  57,  60,  25,  12,  12,  12,  62,  29, 120, 121,  12,  12,
     12,  92,  12,  12,  13,  12,  12, 122,   8,   8,   8,   8,  25, 115,  34,  34,
    123,  40,  40,  40,  10,  10,  10,  71,   8,   8, 124,  11,  10,  10,  10,  26,
     12,  10,  10,  10,  10,  10,  12,  12,  10,  24,  10,  10,  71,  24,  10,  10,
     10,  11,  12,  12,  12,  12,  12, 125,
};

static RE_UINT8 re_bidi_class_stage_5[] = {
    11, 11, 11, 11, 11,  8,  7,  8,  9,  7, 11, 11,  7,  7,  7,  8,
     9, 10, 10,  4,  4,  4, 10, 10, 10, 10, 10,  3,  6,  3,  6,  6,
     2,  2,  2,  2,  2,  2,  6, 10, 10, 10, 10, 10, 10,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 10, 10, 10, 10, 11, 11,  7, 11, 11,
     6, 10,  4,  4, 10, 10,  0, 10, 10, 11, 10, 10,  4,  4,  2,  2,
    10,  0, 10, 10, 10,  2,  0, 10,  0, 10, 10,  0,  0,  0, 10, 10,
     0, 10, 10, 10, 12, 12, 12, 12, 10, 10,  0,  0,  0,  0, 10,  0,
     0,  0,  0, 12, 12, 12,  0,  0,  0, 10, 10,  4,  1, 12, 12, 12,
    12, 12,  1, 12,  1, 12, 12,  1,  1,  1,  1,  1,  5,  5,  5,  5,
     5,  5, 10, 10, 13,  4,  4, 13,  6, 13, 10, 10, 12, 12, 12, 13,
    13, 13, 13, 13, 13, 13, 13, 12,  5,  5,  4,  5,  5, 13, 13, 13,
    12, 13, 13, 13, 13, 13, 12, 12, 12,  5, 10, 12, 12, 13, 13, 12,
    12, 10, 12, 12, 12, 12, 13, 13,  2,  2, 13, 13, 13, 12, 13, 13,
     1,  1,  1, 12,  1,  1, 10, 10, 10, 10,  1,  1,  1,  1, 12, 12,
    12, 12,  1,  1, 12, 12, 12,  0,  0,  0, 12,  0, 12,  0,  0,  0,
     0, 12, 12, 12,  0, 12,  0,  0,  0,  0, 12, 12,  0,  0,  4,  4,
     0,  0,  0,  4,  0, 12, 12,  0, 12,  0,  0, 12, 12, 12,  0, 12,
     0,  4,  0,  0, 10,  4, 10,  0, 12,  0, 12, 12, 10, 10, 10,  0,
    12,  0, 12,  0,  0, 12,  0, 12,  0, 12, 10, 10,  9,  0,  0,  0,
    10, 10, 10, 12, 12, 12, 11,  0,  0, 10,  0, 10,  9,  9,  9,  9,
     9,  9,  9, 11, 11, 11,  0,  1,  9,  7, 16, 17, 18, 14, 15,  6,
     4,  4,  4,  4,  4, 10, 10, 10,  6, 10, 10, 10, 10, 10, 10,  9,
    11, 11, 19, 20, 21, 22, 11, 11,  2,  0,  0,  0,  2,  2,  3,  3,
     0, 10,  0,  0,  0,  0,  4,  0, 10, 10,  3,  4,  9, 10, 10, 10,
     0, 12, 12, 10, 12, 12, 12, 10, 12, 12, 10, 10,  4,  4,  0,  0,
     0,  1, 12,  1,  1,  3,  1,  1, 13, 13, 10, 10, 13, 10, 13, 13,
     6, 10,  6,  0, 10,  6, 10, 10, 10, 10, 10,  4, 10, 10,  3,  3,
    10,  4,  4, 10, 13, 13, 13, 11, 10,  4,  4,  0, 11, 10, 10, 10,
    10, 10, 11, 11, 12,  2,  2,  2,  1,  1,  1, 10, 12, 12, 12,  1,
     1, 10, 10, 10,  5,  5,  5,  1,  0,  0,  0, 11, 11, 11, 11, 12,
    10, 10, 12, 12, 12, 10,  0,  0,  0,  0,  2,  2, 10, 10, 13, 13,
     2,  2,  2, 10,  0,  0, 11, 11,
};

/* Bidi_Class: 3464 bytes. */

RE_UINT32 re_get_bidi_class(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_bidi_class_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_bidi_class_stage_2[pos + f] << 3;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_bidi_class_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_bidi_class_stage_4[pos + f] << 2;
    value = re_bidi_class_stage_5[pos + code];

    return value;
}

/* Canonical_Combining_Class. */

static RE_UINT8 re_canonical_combining_class_stage_1[] = {
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 6, 2, 7, 8, 9,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_canonical_combining_class_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  0, 10, 11, 12, 13,  0,
    14,  0,  0,  0,  0,  0, 15,  0, 16,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 17, 18, 19,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 20,  0, 21,
    22, 23,  0,  0,  0, 24,  0,  0, 25, 26, 27, 28,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 29,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 30,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 31, 32,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 33,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_canonical_combining_class_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  3,  4,  0,  0,  0,  0,
     0,  0,  0,  0,  5,  0,  0,  0,  0,  0,  0,  0,  6,  7,  8,  0,
     9,  0, 10, 11,  0,  0, 12, 13, 14, 15, 16,  0,  0,  0,  0, 17,
    18, 19, 20,  0,  0,  0,  0, 21,  0, 22, 23,  0,  0, 22, 24,  0,
     0, 22, 24,  0,  0, 22, 24,  0,  0, 22, 24,  0,  0,  0, 24,  0,
     0,  0, 25,  0,  0, 22, 24,  0,  0,  0, 24,  0,  0,  0, 26,  0,
     0, 27, 28,  0,  0, 29, 30,  0, 31, 32,  0, 33, 34,  0, 35,  0,
     0, 36,  0,  0, 37,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 38,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 39, 39,  0,  0,  0,  0, 40,  0,
     0,  0,  0,  0,  0, 41,  0,  0,  0, 42,  0,  0,  0,  0,  0,  0,
    43,  0,  0, 44,  0, 45,  0,  0,  0, 46, 47, 48,  0, 49,  0, 50,
     0, 51,  0,  0,  0,  0, 52, 53,  0,  0,  0,  0,  0,  0, 54, 55,
     0,  0,  0,  0,  0,  0, 56, 57,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 58,  0,  0,  0, 59,  0,  0,  0, 60,
     0, 61,  0,  0, 62,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 63, 64,  0,  0, 65,  0,  0,  0,  0,  0,  0,  0,  0,
    66,  0,  0,  0,  0,  0, 47, 67,  0, 68, 69,  0,  0, 70, 71,  0,
     0,  0,  0,  0,  0, 72, 73, 74,  0,  0,  0,  0,  0,  0,  0, 24,
     0,  0,  0,  0,  0,  0,  0,  0, 75,  0,  0,  0,  0,  0,  0,  0,
     0, 76,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 77,
     0,  0,  0,  0,  0,  0,  0, 78,  0,  0,  0, 79,  0,  0,  0,  0,
    80, 81,  0,  0,  0,  0,  0, 82,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0, 66, 59,  0, 83,  0,  0, 84, 85,  0, 70,  0,  0, 71,  0,
     0, 86,  0,  0,  0,  0,  0, 87,  0, 22, 24, 88,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 89,  0,  0,  0,  0,  0,  0, 59, 90,  0,
     0, 59,  0,  0,  0, 91,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 92,  0, 93,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 94,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 95, 96, 97,  0,  0,
     0,  0, 98,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 99,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_canonical_combining_class_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   2,   3,   4,
      5,   6,   7,   4,   4,   8,   9,  10,   1,  11,  12,  13,  14,  15,  16,  17,
     18,   1,   1,   1,   0,   0,   0,   0,  19,   1,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  20,  21,  22,   1,  23,   4,  21,  24,  25,  26,  27,  28,
     29,  30,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   1,  31,   0,
      0,   0,  32,  33,  34,  35,   1,  36,   0,   0,   0,   0,  37,   0,   0,   0,
      0,   0,   0,   0,   0,  38,   1,  39,  14,  39,  40,  41,   0,   0,   0,   0,
      0,   0,   0,   0,  42,   0,   0,   0,   0,   0,   0,   0,  43,  36,  44,  45,
     21,  45,  46,   0,   0,   0,   0,   0,   0,   0,  19,   1,  21,   0,   0,   0,
      0,   0,   0,   0,   0,  38,  47,   1,   1,  48,  48,  49,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  50,   0,   0,  21,  43,  51,  52,  21,  35,   1,
      0,   0,   0,   0,   0,   0,   0,  53,   0,   0,   0,  54,  55,  56,   0,   0,
      0,   0,   0,  54,   0,   0,   0,   0,   0,   0,   0,  54,   0,  57,   0,   0,
      0,   0,  58,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  59,   0,
      0,   0,  60,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  61,   0,
      0,   0,  62,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  63,   0,
      0,   0,   0,   0,   0,  64,  65,   0,   0,   0,   0,   0,  66,  67,  68,  69,
     70,  71,   0,   0,   0,   0,   0,   0,   0,  72,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  73,  74,   0,   0,   0,   0,  75,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  48,   0,   0,   0,   0,   0,  76,   0,   0,
      0,   0,   0,   0,  58,   0,   0,  77,   0,   0,  78,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  79,   0,   0,   0,   0,   0,   0,  19,  80,   0,
     76,   0,   0,   0,   0,  48,   1,  81,   0,   0,   0,   0,   1,  51,  15,  41,
      0,   0,   0,   0,   0,  53,   0,   0,   0,  76,   0,   0,   0,   0,   0,   0,
      0,   0,  19,  10,   1,   0,   0,   0,   0,   0,  82,   0,   0,   0,   0,   0,
      0,  83,   0,   0,  82,   0,   0,   0,   0,   0,   0,   0,   0,  73,   0,   0,
      0,   0,   0,   0,  84,   9,  12,   4,  85,   8,  86,  75,   0,  56,  49,   0,
     21,   1,  21,  87,  88,   1,   1,   1,   1,   1,   1,   1,   1,  49,   0,  89,
      0,   0,   0,   0,  90,   1,  91,  56,  77,  92,  93,   4,  56,   0,   0,   0,
      0,   0,   0,  19,  49,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  94,
      1,   1,   1,   1,   1,   1,   1,   1,   0,   0,  95,  96,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  97,   0,   0,   0,   0,  19,   0,   1,   1,  49,
      0,   0,   0,   0,   0,   0,   0,  19,   0,   0,   0,   0,  49,   0,   0,   0,
      0,  58,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,  49,   0,   0,   0,
      0,   0,  98,  63,   0,   0,   0,   0,   0,   0,   0,   0,  94,   0,   0,   0,
      0,   0,   0,   0,  73,   0,   0,   0,  76,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  99, 100,  56,  38,  77,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  58,   0,   0,   0,   0,   0,   0,   0,   0,   0, 101,
      1,  14,   4,  63,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  75,
     80,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  38,  84,   0,
      0,   0,   0, 102,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 103,  94,
      0, 104,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 105,   0,
     84,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  94,  76,   0,   0,
      0,   0,   0,   0,   0, 105,   0,   0,   0,   0, 106,   0,   0,   0,   0,   0,
      0,  38,   1,  56,   1,  56,   0,   0, 107,   0,   0,   0,   0,   0,   0,   0,
     53,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 107,   0,   0,
      0,   0,   0,   0,   8,  86,   0,   0,   0,   0,   0,   0,   1,  84,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 108,   0, 109, 110, 111, 112,   0,  98,   4,
    113,  48,  23,   0,   0,   0,   0,   0,   0,   0,  38,  49,   0,   0,   0,   0,
     38,  56,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4, 113,   0,   0,
};

static RE_UINT8 re_canonical_combining_class_stage_5[] = {
     0,  0,  0,  0, 50, 50, 50, 50, 50, 51, 45, 45, 45, 45, 51, 43,
    45, 45, 45, 45, 45, 41, 41, 45, 45, 45, 45, 41, 41, 45, 45, 45,
     1,  1,  1,  1,  1, 45, 45, 45, 45, 50, 50, 50, 50, 54, 50, 45,
    45, 45, 50, 50, 50, 45, 45,  0, 50, 50, 50, 45, 45, 45, 45, 50,
    51, 45, 45, 50, 52, 53, 53, 52, 53, 53, 52, 50,  0,  0,  0, 50,
     0, 45, 50, 50, 50, 50, 45, 50, 50, 50, 46, 45, 50, 50, 45, 45,
    50, 46, 49, 50,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 14, 15,
    16, 17,  0, 18,  0, 19, 20,  0, 50, 45,  0, 13, 25, 26, 27,  0,
     0,  0,  0, 22, 23, 24, 25, 26, 27, 28, 29, 50, 50, 45, 45, 50,
    45, 50, 50, 45, 30,  0,  0,  0,  0,  0, 50, 50, 50,  0,  0, 50,
    50,  0, 45, 50, 50, 45,  0,  0,  0, 31,  0,  0, 50, 45, 50, 50,
    45, 45, 50, 45, 45, 50, 45, 50, 45, 50, 50,  0, 50, 50,  0, 50,
     0, 50, 50, 50, 50, 50,  0,  0,  0, 45, 45, 45, 50, 45, 45, 45,
    22, 23, 24, 50,  2,  0,  0,  0,  0,  4,  0,  0,  0, 50, 45, 50,
    50,  0,  0,  0,  0, 32, 33,  0,  0,  0,  4,  0, 34, 34,  4,  0,
    35, 35, 35, 35, 36, 36,  0,  0, 37, 37, 37, 37, 45, 45,  0,  0,
     0, 45,  0, 45,  0, 43,  0,  0,  0, 38, 39,  0, 40,  0,  0,  0,
     0,  0, 39, 39, 39, 39,  0,  0, 39,  0, 50, 50,  4,  0, 50, 50,
     0,  0, 45,  0,  0,  0,  0,  2,  0,  4,  4,  0,  0, 45,  0,  0,
     4,  0,  0,  0,  0, 50,  0,  0,  0, 49,  0,  0,  0, 46, 50, 45,
    45,  0,  0,  0, 50,  0,  0, 45,  0,  0,  4,  4,  0,  0,  2,  0,
    50, 50, 50,  0, 50,  0,  1,  1,  1,  0,  0,  0, 50, 53, 42, 45,
    41, 50, 50, 50, 52, 45, 50, 45, 50, 50,  1,  1,  1,  1,  1, 50,
     0,  1,  1, 50, 45, 50,  1,  1,  0,  0,  0,  4,  0,  0, 44, 49,
    51, 46, 47, 47,  0,  3,  3,  0,  0,  0,  0, 45, 50,  0, 50, 50,
    45,  0,  0, 50,  0,  0, 21,  0,  0, 45,  0, 50, 50,  1, 45,  0,
     0, 50, 45,  0,  0,  4,  2,  0,  0,  2,  4,  0,  0,  0,  4,  2,
     0,  0,  1,  0,  0, 43, 43,  1,  1,  1,  0,  0,  0, 48, 43, 43,
    43, 43, 43,  0, 45, 45, 45,  0,
};

/* Canonical_Combining_Class: 2096 bytes. */

RE_UINT32 re_get_canonical_combining_class(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_canonical_combining_class_stage_1[f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_canonical_combining_class_stage_2[pos + f] << 4;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_canonical_combining_class_stage_3[pos + f] << 3;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_canonical_combining_class_stage_4[pos + f] << 2;
    value = re_canonical_combining_class_stage_5[pos + code];

    return value;
}

/* Decomposition_Type. */

static RE_UINT8 re_decomposition_type_stage_1[] = {
    0, 1, 2, 2, 2, 3, 4, 5, 6, 2, 2, 2, 2, 2, 7, 8,
    2, 2, 2, 2, 2, 2, 2, 9, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_decomposition_type_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  9, 10, 11, 12, 13, 14,
    15,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7, 16,  7, 17, 18, 19,
    20, 21, 22, 23, 24,  7,  7,  7,  7,  7, 25,  7, 26, 27, 28, 29,
    30, 31, 32, 33,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7, 34, 35,  7,  7,  7, 36, 37, 37, 37, 37,
    37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37,
    37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37, 37,
    37, 37, 37, 37, 37, 37, 37, 38,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7, 37, 39, 40, 41, 42, 43, 44,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
    45, 46,  7, 47, 48, 49,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7, 50,  7,  7, 51, 52, 53, 54,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7, 55,  7,
     7, 56, 57,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7, 37, 37, 58,  7,  7,  7,  7,  7,
};

static RE_UINT8 re_decomposition_type_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   4,   3,   5,
      6,   7,   8,   9,  10,  11,   8,  12,   0,   0,  13,  14,  15,  16,  17,  18,
      6,  19,  20,  21,   0,   0,   0,   0,   0,   0,   0,  22,   0,  23,  24,   0,
      0,   0,   0,   0,  25,   0,   0,  26,  27,  14,  28,  14,  29,  30,   0,  31,
     32,  33,   0,  33,   0,  32,   0,  34,   0,   0,   0,   0,  35,  36,  37,  38,
      0,   0,   0,   0,   0,   0,   0,   0,  39,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  40,   0,   0,   0,   0,  41,   0,   0,   0,   0,  42,  43,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  33,  44,   0,  45,   0,   0,   0,   0,   0,   0,  46,  47,   0,   0,
      0,   0,   0,  48,   0,  49,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  50,  51,   0,   0,   0,  52,   0,   0,  53,   0,   0,   0,
      0,   0,   0,   0,  54,   0,   0,   0,   0,   0,   0,   0,  55,   0,   0,   0,
      0,   0,   0,   0,  53,   0,   0,   0,   0,   0,   0,   0,   0,  56,   0,   0,
      0,   0,   0,  57,   0,   0,   0,   0,   0,   0,   0,  57,   0,  58,   0,   0,
     59,   0,   0,   0,  60,  61,  33,  62,  63,  60,  61,  33,   0,   0,   0,   0,
      0,   0,  64,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  65,
     66,  67,   0,  68,  69,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  70,  71,  72,  73,  74,  75,   0,  76,  73,  73,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6,   6,   6,   6,  77,   6,   6,   6,   6,   6,  78,
      6,  79,   6,   6,  79,  80,   6,  81,   6,   6,   6,  82,  83,  84,   6,  85,
     86,  87,  88,  89,  90,  91,   0,  92,  93,  94,  95,   0,   0,   0,   0,   0,
     96,  97,  98,  99, 100, 101, 102, 102, 103, 104, 105,   0, 106,   0,   0,   0,
    107,   0, 108, 109, 110,   0, 111, 112, 112,   0, 113,   0,   0,   0, 114,   0,
      0,   0, 115,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 116, 117, 102, 102, 102, 118, 116, 116, 119,   0,
    120,   0,   0,   0,   0,   0,   0, 121,   0,   0,   0,   0,   0, 122,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 123,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 124,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0, 125,   0,   0,   0,   0,   0,  57,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 126,   0,   0,
    127,   0,   0, 128, 129, 130, 131, 132,   0, 133, 129, 130, 131, 132,   0, 134,
      0,   0,   0, 135, 102, 102, 102, 102, 136, 137,   0,   0,   0,   0,   0,   0,
    102, 136, 102, 102, 138, 139, 116, 140, 116, 116, 116, 116, 141, 116, 116, 140,
    142, 142, 142, 142, 142, 143, 102, 144, 142, 142, 142, 142, 142, 142, 102, 145,
      0,   0,   0,   0,   0,   0,   0,   0,   0, 146,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 147,   0,   0,   0,   0,   0,   0,   0, 148,
      0,   0,   0,   0,   0, 149,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   6,   6,   6,   6,  21,   0,   0,   0,   0,   0,
     81, 150, 151,   6,   6,   6,  81,   6,   6,   6,   6,   6,   6,  78,   0,   0,
    152, 153, 154, 155, 156, 157, 158, 158, 159, 158, 160, 161,   0, 162, 163, 164,
    165, 165, 165, 165, 165, 165, 166, 167, 167, 168, 169, 169, 169, 170, 171, 172,
    165, 173, 174, 175,   0, 176, 177, 178, 179, 180, 167, 181, 182,   0,   0, 183,
      0, 184,   0, 185, 186, 187, 188, 189, 190, 191, 192, 193, 194, 194, 195, 196,
    197, 198, 198, 198, 198, 198, 199, 200, 200, 200, 200, 201, 202, 203, 204,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0, 205, 206,   0,   0,   0,   0,   0,
      0,   0, 207,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  46,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 208,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 104,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 207, 209,   0,   0,   0,   0, 210,  14,   0,   0,   0,
    211, 211, 211, 211, 211, 212, 211, 211, 211, 213, 214, 215, 216, 211, 211, 211,
    217, 218, 211, 219, 220, 221, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211,
    211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 222, 211, 211, 211, 211, 211,
    211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 223, 211, 211, 211,
    216, 211, 224, 225, 226, 227, 228, 229, 230, 231, 232, 231,   0,   0,   0,   0,
    233, 102, 234, 142, 142,   0, 235,   0,   0, 236,   0,   0,   0,   0,   0,   0,
    237, 142, 142, 238, 239, 240,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6,  81,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_decomposition_type_stage_4[] = {
      0,   0,   0,   0,   1,   0,   2,   3,   4,   5,   6,   7,   8,   9,   8,   8,
     10,  11,  10,  12,  10,  11,  10,   9,   8,   8,   8,   8,  13,   8,   8,   8,
      8,  12,   8,   8,  14,   8,  10,  15,  16,   8,  17,   8,  12,   8,   8,   8,
      8,   8,   8,  15,  12,   0,   0,  18,  19,   0,   0,   0,   0,  20,  20,  21,
      8,   8,   8,  22,   8,  13,   8,   8,  23,  12,   8,   8,   8,   8,   8,  13,
      0,  13,   8,   8,   8,   0,   0,   0,  24,  24,  25,   0,   0,   0,  20,   5,
     24,  25,   0,   0,   9,  19,   0,   0,   0,  19,  26,  27,   0,  21,  11,  22,
      0,   0,  13,   8,   0,   0,  13,  11,  28,  29,   0,   0,  30,   5,  31,   0,
      9,  18,   0,  11,   0,   0,  32,   0,   0,  13,   0,   0,  33,   0,   0,   0,
      8,  13,  13,   8,  13,   8,  13,   8,   8,  12,  12,   0,   0,   3,   0,   0,
     13,  11,   0,   0,   0,  34,  35,   0,  36,   0,   0,   0,  18,   0,   0,   0,
     32,  19,   0,   0,   0,   0,   8,   8,   0,   0,  18,  19,   0,   0,   0,   9,
     18,  27,   0,   0,   0,   0,  10,  27,   0,   0,  37,  19,   0,   0,   0,  12,
      0,  19,   0,   0,   0,   0,  13,  19,   0,   0,  19,   0,  19,  18,  22,   0,
      0,   0,  27,  11,   3,   0,   0,   0,   0,   0,   0,   5,   0,   0,   0,   1,
     18,   0,   0,  32,  27,  18,   0,  19,  18,  38,  17,   0,  32,   0,   0,   0,
      0,  27,   0,   0,   0,   0,   0,  25,   0,  27,  36,  36,  27,   0,   0,   0,
      0,   0,  18,  32,   9,   0,   0,   0,   0,   0,   0,  39,  24,  24,  39,  24,
     24,  24,  24,  40,  24,  24,  24,  24,  41,  42,  43,   0,   0,   0,  25,   0,
      0,   0,  44,  24,   8,   8,  45,   0,   8,   8,  12,   0,   8,  12,   8,  12,
      8,   8,  46,  46,   8,   8,   8,  12,   8,  22,   8,  47,  21,  22,   8,   8,
      8,  13,   8,  10,  13,  22,   8,  48,  49,  50,  30,   0,  51,   3,   0,   0,
      0,  30,   0,  52,   3,  53,   0,  54,   0,   3,   5,   0,   0,   3,   0,   3,
     55,  24,  24,  24,  42,  42,  42,  43,  42,  42,  42,  56,   0,   0,  35,   0,
     57,  34,  58,  59,  59,  60,  61,  62,  63,  64,  65,  66,  66,  67,  68,  59,
     69,  61,  62,   0,  70,  70,  70,  70,  20,  20,  20,  20,   0,   0,  71,   0,
      0,   0,  13,   0,   0,   0,   0,  27,   0,   0,   0,  10,   0,  19,  32,  19,
      0,  36,   0,  72,  35,   0,   0,   0,  32,  37,  32,   0,  36,   0,   0,  10,
     12,  12,  12,   0,   0,   0,   0,   8,   8,   0,  13,  12,   0,   0,  33,   0,
     73,  73,  73,  73,  73,  20,  20,  20,  20,  74,  73,  73,  73,  73,  75,   0,
      0,   0,   0,  35,   0,  30,   0,   0,   0,   0,   0,  19,   0,   0,   0,  76,
      0,   0,   0,  44,   0,   0,   0,   3,  20,   5,   0,   0,  77,   0,   0,   0,
      0,  26,  30,   0,   0,   0,   0,  36,  36,  36,  36,  36,  36,  46,  32,   0,
      9,  22,  33,  12,   0,  19,   3,  78,   0,  37,  11,  79,  34,  20,  20,  20,
     20,  20,  20,  30,   4,  24,  24,  24,  20,  73,   0,   0,  80,  73,  73,  73,
     73,  73,  73,  75,  20,  20,  20,  81,  81,  81,  81,  81,  81,  81,  20,  20,
     82,  81,  81,  81,  20,  20,  20,  83,   0,   0,   0,  55,  25,   0,   0,   0,
      0,   0,  55,   0,   0,   0,   0,  24,  36,  10,   8,  11,  36,  33,  13,   8,
     20,  30,   0,   0,   3,  20,   0,  46,  59,  59,  84,   8,   8,  11,   8,  36,
      9,  22,   8,  15,  85,  86,  86,  86,  86,  86,  86,  86,  86,  85,  85,  85,
     87,  85,  86,  86,  88,   0,   0,   0,  89,  90,  91,  92,  85,  87,  86,  85,
     85,  85,  93,  87,  94,  94,  94,  94,  94,  95,  95,  95,  95,  95,  95,  95,
     95,  96,  97,  97,  97,  97,  97,  97,  97,  97,  97,  98,  99,  99,  99,  99,
     99, 100,  94,  94, 101,  95,  95,  95,  95,  95,  95, 102,  97,  99,  99, 103,
    104,  97, 105, 106, 107, 105, 108, 105, 104,  96,  95, 105,  96, 109, 110,  97,
    111, 106, 112, 105,  95, 106, 113,  95,  96, 106,   0,   0,  94,  94,  94, 114,
    115, 115, 116,   0, 115, 115, 115, 115, 115, 117, 118,  20, 119, 120, 120, 120,
    120, 119, 120,   0, 121, 122, 123, 123, 124,  91, 125, 126,  90, 125, 127, 127,
    127, 127, 126,  91, 125, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 126,
    125, 126,  91, 128, 129, 130, 130, 130, 130, 130, 130, 130, 131, 132, 132, 132,
    132, 132, 132, 132, 132, 132, 132, 133, 134, 132, 134, 132, 134, 132, 134, 135,
    130, 136, 132, 133,   0,   0,  27,  19,   0,   0,  18,   0,   0,   0,   0,  13,
      0,   0,  18,  36,   8,  19,   0,   0,   0,   0,  18,   8,  59,  59,  59,  59,
     59, 137,  59,  59,  59,  59,  59, 137, 138, 139,  61, 137,  59,  59,  66,  61,
     59,  61,  59,  59,  59,  66, 140,  61,  59, 137,  59, 137,  59,  59,  66, 140,
     59, 141, 142,  59, 137,  59,  59,  59,  59,  62,  59,  59,  59,  59,  59, 142,
    139, 143,  61,  59, 140,  59, 144,   0, 138, 145, 144,  61, 139, 143, 144, 144,
    139, 143, 140,  59, 140,  59,  61, 141,  59,  59,  66,  59,  59,  59,  59,   0,
     61,  61,  66,  59,  20,  20,  30,   0,  20,  20, 146,  75,   0,   0,   4,   0,
    147,   0,   0,   0, 148,   0,   0,   0,  81,  81, 148,   0,  20,  20,  35,   0,
    149,   0,   0,   0,
};

static RE_UINT8 re_decomposition_type_stage_5[] = {
     0,  0,  0,  0,  4,  0,  0,  0,  2,  0, 10,  0,  0,  0,  0,  2,
     0,  0, 10, 10,  2,  2,  0,  0,  2, 10, 10,  0, 17, 17, 17,  0,
     1,  1,  1,  1,  1,  1,  0,  1,  0,  1,  1,  1,  1,  1,  1,  0,
     1,  1,  0,  0,  0,  0,  1,  1,  1,  0,  2,  2,  1,  1,  1,  2,
     2,  0,  0,  1,  1,  2,  0,  0,  0,  0,  0,  1,  1,  0,  0,  0,
     2,  2,  2,  2,  2,  1,  1,  1,  1,  0,  1,  1,  1,  2,  2,  2,
    10, 10, 10, 10, 10,  0,  0,  0,  0,  0,  2,  0,  0,  0,  1,  0,
     2,  2,  2,  1,  1,  2,  2,  0,  2,  2,  2,  0,  0,  2,  0,  0,
     0,  1,  0,  0,  0,  1,  1,  0,  0,  2,  2,  2,  2,  0,  0,  0,
     1,  0,  1,  0,  1,  0,  0,  1,  0,  1,  1,  2, 10, 10, 10,  0,
    10, 10,  0, 10, 10, 10, 11, 11, 11, 11, 11, 11, 11, 11, 11,  0,
     0,  0,  0, 10,  1,  1,  2,  1,  0,  1,  0,  1,  1,  2,  1,  2,
     1,  1,  2,  0,  1,  1,  2,  2,  2,  2,  2,  4,  0,  4,  0,  0,
     0,  0,  0,  4,  2,  0,  2,  2,  2,  0,  2,  0, 10, 10,  0,  0,
    11,  0,  0,  0,  2,  2,  3,  2,  0,  2,  3,  3,  3,  3,  3,  3,
     0,  3,  2,  0,  0,  3,  3,  3,  3,  3,  0,  0, 10,  2, 10,  0,
     3,  0,  1,  0,  3,  0,  1,  1,  3,  3,  0,  3,  3,  2,  2,  2,
     2,  3,  0,  2,  3,  0,  0,  0, 17, 17, 17, 17,  0, 17,  0,  0,
     2,  2,  0,  2,  9,  9,  9,  9,  2,  2,  9,  9,  9,  9,  9,  0,
    11, 10,  0,  0, 13,  0,  0,  0,  2,  0,  1, 12,  0,  0,  1, 12,
    16,  9,  9,  9, 16, 16, 16, 16,  2, 16, 16, 16,  2,  2,  2, 16,
     3,  3,  1,  1,  8,  7,  8,  7,  5,  6,  8,  7,  8,  7,  5,  6,
     8,  7,  0,  0,  0,  0,  0,  8,  7,  5,  6,  8,  7,  8,  7,  8,
     7,  8,  8,  7,  5,  8,  7,  5,  8,  8,  8,  8,  7,  7,  7,  7,
     7,  7,  7,  5,  5,  5,  5,  5,  5,  5,  5,  6,  6,  6,  6,  6,
     6,  8,  8,  8,  8,  7,  7,  7,  7,  5,  5,  5,  7,  8,  0,  0,
     5,  7,  5,  5,  7,  5,  7,  7,  5,  5,  7,  7,  5,  5,  7,  5,
     5,  7,  7,  5,  7,  7,  5,  7,  5,  5,  5,  7,  0,  0,  5,  5,
     5,  7,  7,  7,  5,  7,  5,  7,  8,  0,  0,  0, 12, 12, 12, 12,
    12, 12,  0,  0, 12,  0,  0, 12, 12,  2,  2,  2, 15, 15, 15,  0,
    15, 15, 15, 15,  8,  6,  8,  0,  8,  0,  8,  6,  8,  6,  8,  6,
     8,  8,  7,  8,  7,  8,  7,  5,  6,  8,  7,  8,  6,  8,  7,  5,
     7,  0,  0,  0,  0, 13, 13, 13, 13, 13, 13, 13, 13, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14,  0,  0,  0, 14, 14, 14,  0,  0,  0,
    13, 13, 13,  0,  3,  0,  3,  3,  0,  0,  3,  0,  0,  3,  3,  0,
     3,  3,  3,  0,  3,  0,  3,  0,  0,  0,  3,  3,  3,  0,  0,  3,
     0,  3,  0,  3,  0,  0,  0,  3,  2,  2,  2,  9, 16,  0,  0,  0,
    16, 16, 16,  0,  9,  9,  0,  0,
};

/* Decomposition_Type: 2964 bytes. */

RE_UINT32 re_get_decomposition_type(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_decomposition_type_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_decomposition_type_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_decomposition_type_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_decomposition_type_stage_4[pos + f] << 2;
    value = re_decomposition_type_stage_5[pos + code];

    return value;
}

/* East_Asian_Width. */

static RE_UINT8 re_east_asian_width_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  5,  6,  5,  5,  7,  8,  9,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 10, 10, 10, 12,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 13,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 13,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    14, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
     8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8, 15,
     8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8, 15,
};

static RE_UINT8 re_east_asian_width_stage_2[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
     5,  6,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
     7,  8,  9, 10, 11, 12, 13, 14,  5, 15,  5, 16,  5,  5, 17, 18,
    19, 20, 21, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 23, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 24,  5,  5,  5,  5, 25,  5,  5, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 26,  5,  5,  5,  5,  5,  5,  5,  5,
    27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27,
    27, 27, 27, 27, 27, 27, 27, 27, 27, 22, 22,  5,  5,  5, 28, 29,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
    30,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
     5, 31, 32,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 33,
     5, 34,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
    27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 35,
};

static RE_UINT8 re_east_asian_width_stage_3[] = {
     0,  0,  1,  1,  1,  1,  1,  2,  0,  0,  3,  4,  5,  6,  7,  8,
     9, 10, 11, 12, 13, 14, 11,  0,  0,  0,  0,  0, 15, 16,  0,  0,
     0,  0,  0,  0,  0,  9,  9,  0,  0,  0,  0,  0, 17, 18,  0,  0,
    19, 19, 19, 19, 19, 19, 19,  0,  0, 20, 21, 20, 21,  0,  0,  0,
     9, 19, 19, 19, 19,  9,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    22, 22, 22, 22, 22, 22,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0, 23, 24, 25,  0,  0,  0, 26, 27,  0, 28,  0,  0,  0,  0,  0,
    29, 30, 31,  0,  0, 32, 33, 34, 35, 34,  0, 36,  0, 37, 38,  0,
    39, 40, 41, 42, 43, 44, 45,  0, 46, 47, 48, 49,  0,  0,  0,  0,
     0, 44, 50,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 19, 19, 19, 19, 19, 19, 19, 19, 51, 19,
    19, 19, 19, 19, 33, 19, 19, 52, 19, 53, 21, 54, 55, 56, 57,  0,
    58, 59,  0,  0, 60,  0, 61,  0,  0, 62,  0, 62, 63, 19, 64, 19,
     0,  0,  0, 65,  0, 38,  0, 66,  0,  0,  0,  0,  0,  0, 67,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 68,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 69,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 22, 70, 22, 22, 22, 22, 22, 71,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 72,  0, 73,
    74, 22, 22, 75, 76, 22, 22, 22, 22, 77, 22, 22, 22, 22, 22, 22,
    78, 22, 79, 76, 22, 22, 22, 22, 75, 22, 22, 80, 22, 22, 71, 22,
    22, 75, 22, 22, 81, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 75,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,  0,  0,  0,  0,
    22, 22, 22, 22, 22, 22, 22, 22, 82, 22, 22, 22, 83,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 22, 82,  0,  0,  0,  0,  0,  0,  0,  0,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 71,  0,  0,  0,  0,  0,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 84,  0, 22, 22, 85, 86,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    87, 88, 88, 88, 88, 88, 89, 90, 90, 90, 90, 91, 92, 93, 94, 65,
    95,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    96, 19, 97, 19, 19, 19, 34, 19, 19, 96,  0,  0,  0,  0,  0,  0,
    98, 22, 22, 80, 99, 95,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 79,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,  0,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 97,
};

static RE_UINT8 re_east_asian_width_stage_4[] = {
     0,  0,  0,  0,  1,  1,  1,  1,  1,  1,  1,  2,  3,  4,  5,  6,
     7,  8,  9,  7,  0, 10,  0,  0, 11, 12, 11, 13, 14, 10,  9, 14,
     8, 12,  9,  5, 15,  0,  0,  0, 16,  0, 12,  0,  0, 13, 12,  0,
    17,  0, 11, 12,  9, 11,  7, 15, 13,  0,  0,  0,  0,  0,  0, 10,
     5,  5,  5, 11,  0, 18, 17, 15, 11,  0,  7, 16,  7,  7,  7,  7,
    17,  7,  7,  7, 19,  7, 14,  0, 20, 20, 20, 20, 18,  9, 14, 14,
     9,  7,  0,  0,  8, 15, 12, 10,  0, 11,  0, 12, 17, 11,  0,  0,
     0,  0, 21, 11, 12, 15, 15,  0, 12, 10,  0,  0, 22, 10, 12,  0,
    12, 11, 12,  9,  7,  7,  7,  0,  7,  7, 14,  0,  0,  0, 15,  0,
     0,  0, 14,  0, 10, 11,  0,  0,  0, 12,  0,  0,  8, 12, 18, 12,
    15, 15, 10, 17, 18, 16,  7,  5,  0,  7,  0, 14,  0,  0, 11, 11,
    10,  0,  0,  0, 14,  7, 13, 13, 13, 13,  0,  0,  0, 15, 15,  0,
     0, 15,  0,  0,  0,  0,  0, 12,  0,  0, 23,  0,  7,  7, 19,  7,
     7,  0,  0,  0, 13, 14,  0,  0, 13, 13,  0, 14, 14, 13, 18, 13,
    14,  0,  0,  0, 13, 14,  0, 12,  0, 22, 15, 13,  0, 14,  0,  5,
     5,  0,  0,  0, 19, 19,  9, 19,  0,  0,  0, 13,  0,  7,  7, 19,
    19,  0,  7,  7,  0,  0,  0, 15,  0, 13,  7,  7,  0, 24,  1, 25,
     0, 26,  0,  0,  0, 17, 14,  0, 20, 20, 27, 20, 20,  0,  0,  0,
    20, 28,  0,  0, 20, 20, 20,  0, 29, 20, 20, 20, 20, 20, 20, 30,
    31, 20, 20, 20, 20, 30, 31, 20,  0, 31, 20, 20, 20, 20, 20, 28,
    20, 20, 30,  0, 20, 20,  7,  7, 20, 20, 20, 32, 20, 30,  0,  0,
    20, 20, 28,  0, 30, 20, 20, 20, 20, 30, 20,  0, 33, 34, 34, 34,
    34, 34, 34, 34, 35, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 37,
    38, 36, 38, 36, 38, 36, 38, 39, 34, 40, 36, 37, 28,  0,  0,  0,
     7,  7,  9,  0,  7,  7,  7, 14, 30,  0,  0,  0, 20, 20, 32,  0,
};

static RE_UINT8 re_east_asian_width_stage_5[] = {
    0, 0, 0, 0, 5, 5, 5, 5, 5, 5, 5, 0, 0, 1, 5, 5,
    1, 5, 5, 1, 1, 0, 1, 0, 5, 1, 1, 5, 1, 1, 1, 1,
    1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0,
    0, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0,
    0, 1, 0, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1,
    3, 3, 3, 3, 0, 2, 0, 0, 0, 1, 1, 0, 0, 3, 3, 0,
    0, 0, 5, 5, 5, 5, 0, 0, 0, 5, 5, 0, 3, 3, 0, 3,
    3, 3, 0, 0, 4, 3, 3, 3, 3, 3, 3, 0, 0, 3, 3, 3,
    3, 0, 0, 0, 0, 4, 4, 4, 4, 4, 4, 4, 4, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 0,
    4, 4, 4, 0,
};

/* East_Asian_Width: 1668 bytes. */

RE_UINT32 re_get_east_asian_width(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_east_asian_width_stage_1[f] << 4;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_east_asian_width_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_east_asian_width_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_east_asian_width_stage_4[pos + f] << 2;
    value = re_east_asian_width_stage_5[pos + code];

    return value;
}

/* Joining_Group. */

static RE_UINT8 re_joining_group_stage_1[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1,
};

static RE_UINT8 re_joining_group_stage_2[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_joining_group_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 0,
    0, 4, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_joining_group_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  1,  2,  3,  4,  5,  6,  0,  0,  0,  7,  8,  9,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,  0,  0, 21,  0, 22,
     0,  0, 23, 24, 25, 26,  0,  0,  0, 27, 28, 29, 30, 31, 32, 33,
     0,  0,  0,  0, 34, 35, 36,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 37, 38, 39, 40, 41, 42,  0,  0,
};

static RE_UINT8 re_joining_group_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0, 45,  0,  3,  3, 43,  3, 45,  3,
     4, 41,  4,  4, 13, 13, 13,  6,  6, 31, 31, 35, 35, 33, 33, 39,
    39,  1,  1, 11, 11, 55, 55, 55,  0,  9, 29, 19, 22, 24, 26, 16,
    43, 45, 45,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  4, 29,
     0,  3,  3,  3,  0,  3, 43, 43, 45,  4,  4,  4,  4,  4,  4,  4,
     4, 13, 13, 13, 13, 13, 13, 13,  6,  6,  6,  6,  6,  6,  6,  6,
     6, 31, 31, 31, 31, 31, 31, 31, 31, 31, 35, 35, 35, 33, 33, 39,
     1,  9,  9,  9,  9,  9,  9, 29, 29, 11, 38, 11, 19, 19, 19, 11,
    11, 11, 11, 11, 11, 22, 22, 22, 22, 26, 26, 26, 26, 56, 21, 13,
    41, 17, 17, 14, 43, 43, 43, 43, 43, 43, 43, 43, 55, 47, 55, 43,
    45, 45, 46, 46,  0, 41,  0,  0,  0,  0,  0,  0,  0,  0,  6, 31,
     0,  0, 35, 33,  1,  0,  0, 21,  2,  0,  5, 12, 12,  7,  7, 15,
    44, 50, 18, 42, 42, 48, 49, 20, 23, 25, 27, 36, 10,  8, 28, 32,
    34, 30,  7, 37, 40,  5, 12,  7,  0,  0,  0,  0,  0, 51, 52, 53,
     4,  4,  4,  4,  4,  4,  4, 13, 13,  6,  6, 31, 35,  1,  1,  1,
     9,  9, 11, 11, 11, 24, 24, 26, 26, 26, 22, 31, 31, 35, 13, 13,
    35, 31, 13,  3,  3, 55, 55, 45, 43, 43, 54, 54, 13, 35, 35, 19,
     4,  4, 13, 39,  9, 29, 22, 24, 45, 45, 31, 43, 57,  0,  6, 33,
    11, 58, 31,  0,  0,  0,  0,  0, 59, 61, 61, 65, 65, 62,  0, 83,
     0, 85, 85,  0,  0, 66, 80, 84, 68, 68, 68, 69, 63, 81, 70, 71,
    77, 60, 60, 73, 73, 76, 74, 74, 74, 75,  0,  0, 78,  0,  0,  0,
     0,  0,  0, 72, 64, 79, 82, 67,
};

/* Joining_Group: 586 bytes. */

RE_UINT32 re_get_joining_group(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_joining_group_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_joining_group_stage_2[pos + f] << 4;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_joining_group_stage_3[pos + f] << 4;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_joining_group_stage_4[pos + f] << 3;
    value = re_joining_group_stage_5[pos + code];

    return value;
}

/* Joining_Type. */

static RE_UINT8 re_joining_type_stage_1[] = {
     0,  1,  2,  2,  2,  3,  2,  4,  5,  2,  2,  6,  2,  7,  8,  9,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
    10,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,
};

static RE_UINT8 re_joining_type_stage_2[] = {
     0,  1,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14,
    15,  1,  1, 16,  1,  1,  1, 17, 18, 19, 20, 21, 22, 23,  1,  1,
    24,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 25, 26,  1,  1,
    27,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 28,  1, 29, 30, 31, 32,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 33,  1,  1, 34, 35,
     1, 36, 37, 38,  1,  1,  1,  1,  1,  1, 39, 40,  1,  1,  1,  1,
    41, 42, 43, 44, 45, 46, 47,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 48, 49,  1,  1,  1, 50,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 51,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1, 52, 53,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 54,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    55, 56,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_joining_type_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      2,   2,   2,   2,   2,   2,   2,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   3,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   4,   2,   5,   6,   0,   0,   0,
      0,   7,   8,   9,  10,   2,  11,  12,  13,  14,  15,  15,  16,  17,  18,  19,
     20,  21,  22,   2,  23,  24,  25,  26,   0,   0,  27,  28,  29,  15,  30,  31,
      0,  32,  33,   0,  34,  35,   0,   0,   0,   0,  36,  37,   0,   0,  38,   2,
     39,   0,   0,  40,  41,  42,  43,   0,  44,   0,   0,  45,  46,   0,  43,   0,
     47,   0,   0,  45,  48,  44,   0,  49,  47,   0,   0,  45,  50,   0,  43,   0,
     44,   0,   0,  51,  46,  52,  43,   0,  53,   0,   0,   0,  54,   0,   0,   0,
     28,   0,   0,  55,  56,  57,  43,   0,  44,   0,   0,  51,  58,   0,  43,   0,
     44,   0,   0,   0,  46,   0,  43,   0,   0,   0,   0,   0,  59,  60,   0,   0,
      0,   0,   0,  61,  62,   0,   0,   0,   0,   0,   0,  63,  64,   0,   0,   0,
      0,  65,   0,  66,   0,   0,   0,  67,  68,  69,   2,  70,  52,   0,   0,   0,
      0,   0,  71,  72,   0,  73,  28,  74,  75,   1,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  71,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,  76,   0,  76,   0,  43,   0,  43,   0,   0,   0,  77,  78,  79,   0,   0,
     80,   0,  15,  15,  15,  15,  15,  81,  82,  15,  83,   0,   0,   0,   0,   0,
      0,   0,  84,  85,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,  86,   0,   0,   0,  87,  88,  89,   0,   0,   0,  90,   0,   0,   0,   0,
     91,   0,   0,  92,  53,   0,  93,  91,  94,   0,  95,   0,   0,   0,  96,  94,
      0,   0,  97,  98,   0,   0,   0,   0,   0,   0,   0,   0,   0,  99, 100, 101,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   2,   2,   2, 102,
    103,   0, 104,   0,   0,   0, 105,   0,   0,   0,   0,   0,   0,   2,   2,  28,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  20,  94,
      0,   0,   0,   0,   0,   0,   0,  20,   0,   0,   0,   0,   0,   0,   2,   2,
      0,   0, 106,   0,   0,   0,   0,   0,   0, 107,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  20, 108,   0,  20,   0,   0,   0,   0,   0,  94,
    109,   0,  57,   0,  15,  15,  15, 110,   0,   0,   0,   0, 111,   0,   2,  94,
      0,   0, 112,   0, 113,  94,   0,   0,  39,   0,   0, 114,   0,   0, 115,   0,
      0,   0, 116, 117, 118,   0,   0,  45,   0,   0,   0, 119,  44,   0, 120,  52,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 121,   0,
      0, 122,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      2,   0, 123,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  20,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 124,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  28,   0,
      0,   0,   0,   0,   0,   0,   0, 125,   0,   0,   0,   0,   0,   0,   0,   0,
    126,   0,   0, 127,   0,   0,   0,   0,   0,   0,   0,   0, 128, 129, 130,   0,
      0,   0,   0,   0,   0,   0,   0,   0, 131, 132, 133,   0,   0,   0,   0,   0,
     44,   0,   0, 134, 135,   0,   0,  20,  94,   0,   0, 136,   0,   0,   0,   0,
     39,   0, 137, 138,   0,   0,   0, 139,  94,   0,   0, 140,   0,   0,   0,   0,
      0,   0,  20, 141,   0,   0,   0,   0,   0,   0,   0,   0,   0,  20, 142,   0,
     44,   0,   0,  45,  28,   0, 143, 138,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 144, 145,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 146,  28,   0,   0,   0,
      0,   0,   0, 147,  28,   0,   0,   0,   0,   0, 148, 149,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 138,
      0,   0,   0, 135,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  20,  39,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0, 150,  91,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 151, 152, 153,   0, 106,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  76,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 135,   0,   0,
     44,   0,   2,   2,   2,   2,   2,   2,   0,   0,   0,   0,   0,   0,   0,   0,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   0,
};

static RE_UINT8 re_joining_type_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  1,  2,  2,  2,  2,  3,  2,  4,  0,
     5,  2,  2,  2,  2,  2,  2,  6,  7,  6,  0,  0,  2,  2,  8,  9,
    10, 11, 12, 13, 14, 15, 15, 15, 16, 15, 17,  2,  0,  0,  0, 18,
    19, 20, 15, 15, 15, 15, 21, 21, 21, 21, 22, 15, 15, 15, 15, 15,
    23, 21, 21, 24, 25, 26,  2, 27,  2, 27, 28, 29,  0,  0, 18, 30,
     0,  0,  0,  3, 31, 32, 22, 33, 15, 15, 34, 23,  2,  2,  8, 35,
    15, 15, 32, 15, 15, 15, 13, 36, 24, 36, 22, 15,  0, 37,  2,  2,
     9,  0,  0,  0,  0,  0, 18, 15, 15, 15, 38,  2,  2,  0, 39,  0,
     0, 37,  6,  2,  2,  5,  5,  4, 36, 33, 12, 13, 15, 40,  5,  0,
    15, 15, 25, 41, 42,  0,  0,  0,  0,  2,  2,  2,  8,  0,  0,  0,
     0,  0, 43,  9,  5,  2,  9,  1,  5,  2,  0,  0, 37,  0,  0,  0,
     1,  0,  0,  0,  0,  0,  0,  9,  5,  9,  0,  1,  7,  0,  0,  0,
     7,  3, 27,  4,  4,  1,  0,  0,  5,  6,  9,  1,  0,  0,  0, 27,
     0, 43,  0,  0, 43,  0,  0,  0,  9,  0,  0,  1,  0,  0,  0, 37,
     9, 37, 28,  4,  0,  7,  0,  0,  0, 43,  0,  4,  0,  0, 43,  0,
    37, 44,  0,  0,  1,  2,  8,  0,  0,  3,  2,  8,  1,  2,  6,  9,
     0,  0,  2,  4,  0,  0,  4,  0,  0, 45,  1,  0,  5,  2,  2,  8,
     2, 28,  0,  5,  2,  2,  5,  2,  2,  2,  2,  9,  0,  0,  0,  5,
    28,  2,  7,  7,  0,  0,  4, 37,  5,  9,  0,  0, 43,  7,  0,  1,
    37,  9,  0,  0,  0,  6,  2,  4,  0, 43,  5,  2,  2,  0,  0,  1,
     0, 46, 47,  4, 15, 15,  0,  0,  0, 46, 15, 15, 15, 15, 48,  0,
     8,  3,  9,  0, 43,  0,  5,  0,  0,  3, 27,  0,  0, 43,  2,  8,
    44,  5,  2,  9,  3,  2,  2, 27,  2,  2,  2,  8,  2,  0,  0,  0,
     0, 28,  8,  9,  0,  0,  3,  2,  4,  0,  0,  0, 37,  4,  6,  4,
     0, 43,  4, 45,  0,  0,  0,  2,  2, 37,  0,  0,  8,  2,  2,  2,
    28,  2,  9,  1,  0,  9,  4,  0,  2,  4,  0,  2,  0,  0,  3, 49,
     0,  0, 37,  8,  2,  9, 37,  2,  0,  0, 37,  4,  0,  0,  7,  0,
     8,  2,  2,  4, 43, 43,  3,  0, 50,  0,  0,  0,  0,  9,  0,  0,
     0, 37,  2,  4,  0,  3,  2,  2,  3, 37,  4,  9,  0,  1,  0,  0,
     0,  0,  5,  8,  7,  7,  0,  0,  3,  0,  0,  9, 28, 27,  9, 37,
     0,  0,  0,  4,  0,  1,  9,  1,  0,  0,  0, 43,  2,  2,  2,  4,
     0,  0,  5,  0,  0, 37,  8,  0,  5,  7,  0,  2,  0,  0,  8,  3,
    15, 51, 52, 53, 14, 54, 15, 12, 55, 56, 46, 13, 24, 22, 12, 57,
    55,  0,  0,  0,  0,  0, 20, 58,  0,  0,  2,  2,  2,  8,  0,  0,
     3,  8,  7,  1,  0,  3,  2,  5,  2,  9,  0,  0,  3,  0,  0,  0,
     0, 37,  2,  8,  4, 28,  0,  0,  3,  2,  8,  0,  0, 37,  2,  9,
     3,  2, 44,  3, 28,  0,  0,  0, 37,  4,  0,  6,  3,  2,  8, 45,
     0,  0,  3,  1,  2,  6,  0,  0,  0,  0,  0,  7,  0,  3,  4,  0,
     3,  2,  2,  2,  8,  5,  2,  0,
};

static RE_UINT8 re_joining_type_stage_5[] = {
    0, 0, 0, 0, 0, 5, 0, 0, 5, 5, 5, 5, 0, 0, 0, 5,
    5, 5, 0, 0, 0, 5, 5, 5, 5, 5, 0, 5, 0, 5, 5, 0,
    5, 5, 5, 0, 5, 0, 0, 0, 2, 0, 3, 3, 3, 3, 2, 3,
    2, 3, 2, 2, 2, 2, 2, 3, 3, 3, 3, 2, 2, 2, 2, 2,
    1, 2, 2, 2, 3, 2, 2, 5, 0, 0, 2, 2, 5, 3, 3, 3,
    0, 3, 3, 3, 3, 3, 3, 3, 3, 3, 2, 2, 3, 2, 2, 3,
    2, 3, 2, 3, 2, 2, 3, 3, 0, 3, 5, 5, 5, 0, 0, 5,
    5, 0, 5, 5, 5, 5, 3, 3, 2, 0, 0, 2, 3, 5, 2, 2,
    2, 3, 3, 3, 2, 2, 3, 2, 3, 2, 3, 2, 0, 3, 2, 2,
    3, 2, 2, 2, 0, 0, 5, 5, 2, 2, 2, 5, 0, 0, 1, 0,
    3, 2, 0, 0, 3, 0, 3, 2, 2, 3, 3, 0, 0, 0, 5, 0,
    5, 0, 5, 0, 0, 5, 0, 5, 0, 0, 0, 2, 0, 0, 1, 5,
    2, 5, 2, 0, 0, 1, 5, 5, 2, 2, 4, 0, 2, 3, 0, 3,
    0, 3, 3, 0, 0, 4, 3, 3, 2, 2, 2, 4, 2, 3, 0, 0,
    3, 5, 5, 0, 3, 2, 3, 3, 3, 2, 2, 0,
};

/* Joining_Type: 2252 bytes. */

RE_UINT32 re_get_joining_type(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_joining_type_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_joining_type_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_joining_type_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_joining_type_stage_4[pos + f] << 2;
    value = re_joining_type_stage_5[pos + code];

    return value;
}

/* Line_Break. */

static RE_UINT8 re_line_break_stage_1[] = {
     0,  1,  2,  3,  4,  5,  5,  5,  5,  5,  6,  7,  8,  9, 10, 11,
    12, 13, 14, 15, 10, 10, 16, 10, 10, 10, 10, 17, 10, 18, 19, 20,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 21,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 21,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    22, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
};

static RE_UINT8 re_line_break_stage_2[] = {
      0,   1,   2,   2,   2,   3,   4,   5,   2,   6,   7,   8,   9,  10,  11,  12,
     13,  14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,
     29,  30,  31,  32,  33,  34,  35,  36,  37,   2,   2,   2,   2,  38,  39,  40,
     41,  42,  43,  44,  45,  46,  47,  48,  49,  50,   2,  51,   2,   2,  52,  53,
     54,  55,  56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,  68,  69,
      2,   2,   2,  70,   2,   2,  71,  72,  73,  74,  75,  76,  77,  78,  79,  80,
     81,  82,  83,  84,  85,  86,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  87,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     88,  79,  79,  79,  79,  79,  79,  79,  79,  89,   2,   2,  90,  91,   2,  92,
     93,  94,  95,  96,  97,  98,  99, 100, 101, 102, 103, 104, 105, 106, 107, 101,
    102, 103, 104, 105, 106, 107, 101, 102, 103, 104, 105, 106, 107, 101, 102, 103,
    104, 105, 106, 107, 101, 102, 103, 104, 105, 106, 107, 101, 102, 103, 104, 105,
    106, 107, 101, 102, 103, 104, 105, 106, 107, 101, 102, 103, 104, 105, 106, 107,
    101, 102, 103, 104, 105, 106, 107, 101, 102, 103, 104, 105, 106, 107, 101, 102,
    103, 104, 105, 106, 107, 101, 102, 103, 104, 105, 106, 107, 101, 102, 103, 108,
    109, 109, 109, 109, 109, 109, 109, 109, 109, 109, 109, 109, 109, 109, 109, 109,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110,  79,  79,  79,  79, 111, 112,   2,   2, 113, 114, 115, 116, 117, 118,
    119, 120, 121, 122, 110, 123, 124, 125,   2, 126, 127, 110,   2,   2, 128, 110,
    129, 130, 131, 132, 133, 134, 135, 136, 137, 110, 110, 110, 138, 110, 110, 110,
    139, 140, 141, 142, 143, 144, 145, 110, 110, 146, 110, 147, 148, 149, 110, 110,
    110, 150, 110, 110, 110, 151, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2,   2,   2,   2,   2,   2,   2, 152, 153, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2,   2,   2,   2, 154, 155, 156,   2, 157, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2,   2,   2,   2, 158, 159, 160, 161, 110, 110, 110, 110, 110, 110, 162, 163,
    164, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 165, 166, 110, 110, 110, 110, 110, 110,
      2, 167, 168, 169, 170, 110, 171, 110, 172, 173, 174,   2,   2, 175,   2, 176,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2, 177, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 178, 179, 110, 110,
    180, 181, 182, 183, 184, 110, 185, 186,  79, 187, 188, 189, 190, 191, 192, 193,
    194, 195, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79, 196,
    197, 110, 198, 199, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
};

static RE_UINT16 re_line_break_stage_3[] = {
      0,   1,   2,   3,   4,   5,   4,   6,   7,   1,   8,   9,   4,  10,   4,  10,
      4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,  11,  12,   4,   4,
      1,   1,   1,   1,  13,  14,  15,  16,  17,   4,  18,   4,   4,   4,   4,   4,
     19,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,  20,   4,  21,  20,   4,
     22,  23,   1,  24,  25,  26,  27,  28,  29,  30,   4,   4,  31,   1,  32,  33,
      4,   4,   4,   4,   4,  34,  35,  36,  37,  38,   4,   1,  39,   4,   4,   4,
      4,   4,  40,  41,  36,   4,  31,  42,   4,  43,  44,  45,   4,  46,  47,  47,
     47,  47,   4,  48,  47,  47,  49,   1,  50,   4,   4,  51,   1,  52,  53,   4,
     54,  55,  56,  57,  58,  59,  60,  61,  62,  55,  56,  63,  64,  65,  66,  67,
     68,  18,  56,  69,  70,  71,  60,  72,  73,  55,  56,  69,  74,  75,  60,  76,
     77,  78,  79,  80,  81,  82,  66,  83,  84,  85,  56,  86,  87,  88,  60,  89,
     90,  85,  56,  91,  87,  92,  60,  93,  90,  85,   4,  94,  95,  96,  60,  97,
     98,  99,   4, 100, 101, 102,  66, 103, 104, 105, 105, 106, 107, 108,  47,  47,
    109, 110, 111, 112, 113, 114,  47,  47, 115, 116,  36, 117, 118,   4, 119, 120,
    121, 122,   1, 123, 124, 125,  47,  47, 105, 105, 105, 105, 126, 105, 105, 105,
    105, 127,   4,   4, 128,   4,   4,   4, 129, 129, 129, 129, 129, 129, 130, 130,
    130, 130, 131, 132, 132, 132, 132, 132,   4,   4,   4,   4, 133, 134,   4,   4,
    133,   4,   4, 135, 136, 137,   4,   4,   4, 136,   4,   4,   4, 138, 139, 119,
      4, 140,   4,   4,   4,   4,   4, 141, 142,   4,   4,   4,   4,   4,   4,   4,
    142, 143,   4,   4,   4,   4, 144, 145, 146, 147,   4, 148,   4, 149, 146, 150,
    105, 105, 105, 105, 105, 151, 152, 140, 153, 152,   4,   4,   4,   4,   4,  76,
      4,   4, 154,   4,   4,   4,   4, 155,   4,  45, 156, 156, 157, 105, 158, 159,
    105, 105, 160, 105, 161, 162,   4,   4,   4, 163, 105, 105, 105, 164, 105, 165,
    152, 152, 158, 166,  47,  47,  47,  47, 167,   4,   4, 168, 169, 170, 171, 172,
    173,   4, 174,  36,   4,   4,  40, 175,   4,   4, 168, 176, 177,  36,   4, 178,
     47,  47,  47,  47,  76, 179, 180, 181,   4,   4,   4,   4,   1,   1,   1, 182,
      4, 183,   4,   4, 183, 184,   4, 185,   4,   4,   4, 186, 186, 187,   4, 188,
    189, 190, 191, 192, 193, 194, 195, 196, 197, 119, 198, 199, 200,   1,   1, 201,
    202, 203, 204,   4,   4, 205, 206, 207, 208, 207,   4,   4,   4, 209,   4,   4,
    210, 211, 212, 213, 214, 215, 216,   4, 217, 218, 219, 220,   4,   4,   4,   4,
    221, 222, 223,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4, 224,
      4,   4, 225,  47, 226,  47, 227, 227, 227, 227, 227, 227, 227, 227, 227, 228,
    227, 227, 227, 227, 206, 227, 227, 229, 227, 230, 231, 232, 233, 234, 235,   4,
    236, 237,   4, 238, 239,   4, 240, 241,   4, 242,   4, 243, 244, 245, 246, 247,
    248,   4,   4,   4,   4, 249, 250, 251, 227, 252,   4,   4, 253,   4, 254,   4,
    255, 256,   4,   4,   4, 221,   4, 257,   4,   4,   4,   4,   4, 258,   4, 259,
      4, 260,   4, 261,  56, 262,  47,  47,   4,   4,  45,   4,   4,  45,   4,   4,
      4,   4,   4,   4,   4,   4, 263, 264,   4,   4, 128,   4,   4,   4, 265, 266,
      4, 225, 267, 267, 267, 267,   1,   1, 268, 269, 270, 271, 272,  47,  47,  47,
    273, 274, 273, 273, 273, 273, 273, 275, 273, 273, 273, 273, 273, 273, 273, 273,
    273, 273, 273, 273, 273, 276,  47, 277, 278, 279, 280, 281, 282, 273, 283, 273,
    284, 285, 286, 273, 283, 273, 284, 287, 288, 273, 289, 290, 273, 273, 273, 273,
    291, 273, 273, 292, 273, 273, 275, 293, 273, 291, 273, 273, 294, 273, 273, 273,
    273, 273, 273, 273, 273, 273, 273, 291, 273, 273, 273, 273,   4,   4,   4,   4,
    273, 295, 273, 273, 273, 273, 273, 273, 296, 273, 273, 273, 297,   4,   4, 178,
    298,   4, 299,  47,   4,   4, 263, 300,   4, 301,   4,   4,   4,   4,   4, 302,
     45,   4, 185, 262,  47,  47,  47, 303, 304,   4, 305, 306,   4,   4,   4, 307,
    308,   4,   4, 168, 309, 152,   1, 310,  36,   4, 311,   4, 312, 313, 129, 314,
     50,   4,   4, 315, 316, 317, 105, 318,   4,   4, 319, 320, 321, 322, 105, 105,
    105, 105, 105, 105, 323, 324,  31, 325, 326, 327, 267,   4,   4,   4, 328,  47,
     47,  47,  47,  47,   4,   4, 329, 152, 330, 331, 332, 333, 332, 334, 332, 330,
    331, 332, 333, 332, 334, 332, 330, 331, 332, 333, 332, 334, 332, 330, 331, 332,
    333, 332, 334, 332, 330, 331, 332, 333, 332, 334, 332, 330, 331, 332, 333, 332,
    334, 332, 330, 331, 332, 333, 332, 334, 332, 330, 331, 332, 333, 332, 334, 332,
    333, 332, 335, 130, 336, 132, 132, 337, 338, 338, 338, 338, 338, 338, 338, 338,
     47,  47,  47,  47,  47,  47,  47,  47, 225, 339, 340, 341, 342,   4,   4,   4,
      4,   4,   4,   4, 262, 343,   4,   4,   4,   4,   4, 344,  47,   4,   4,   4,
      4, 345,   4,   4,  76,  47,  47, 346,   1, 347, 348, 349, 350, 351, 352, 186,
      4,   4,   4,   4,   4,   4,   4, 353, 354, 355, 273, 356, 273, 357, 358, 359,
      4, 360,   4,  45, 361, 362, 363, 364, 365,   4, 137, 366, 185, 185,  47,  47,
      4,   4,   4,   4,   4,   4,   4, 226, 367,   4,   4, 368,   4,   4,   4,   4,
    119, 369,  71,  47,  47,   4,   4, 370,   4, 119,   4,   4,   4,  71,  33, 369,
      4,   4, 371,   4, 226,   4,   4, 372,   4, 373,   4,   4, 374, 375,  47,  47,
      4, 185, 152,  47,  47,  47,  47,  47,   4,   4,  76,   4,   4,   4, 376,  47,
      4,   4,   4, 225,   4, 155,  76,  47, 377,   4,   4, 378,   4, 379,   4,   4,
      4,  45, 303,  47,  47,  47,  47,  47,   4, 380,   4, 381,  47,  47,  47,  47,
      4,   4,   4, 382,  47,  47,  47,  47, 383, 384,   4, 385,  76, 386,   4,   4,
      4,   4,  47,  47,   4,   4, 387, 388,   4,   4,   4, 389,   4, 260,   4, 390,
      4, 391, 392,  47,  47,  47,  47,  47,   4,   4,   4,   4, 145,  47,  47,  47,
     47,  47,  47,  47,  47,  47,   4,  45, 173,   4,   4, 393, 394, 345, 395, 396,
    173,   4,   4, 397, 398,   4, 145, 152, 173,   4, 312, 399, 400,   4,   4, 401,
    173,   4,   4, 315, 402, 403,  20, 141,   4,  18, 404, 405,  47,  47,  47,  47,
     47,  47,  47,   4,   4, 263, 406, 152,  73,  55,  56,  69,  74, 407, 408, 409,
      4,   4,   4,   1, 410, 152,  47,  47,   4,   4, 263, 411, 412,  47,  47,  47,
      4,   4,   4,   1, 413, 152,  47,  47,   4,   4,  31, 414, 152,  47,  47,  47,
     47,  47,   4,   4,   4,   4,  36, 415,  47,  47,  47,  47,   4,   4,   4, 145,
      4, 145,  47,  47,  47,  47,  47,  47,   4,   4,   4,   4,   4,   4,  45, 416,
      4,   4,   4,   4,   4, 417,   4,   4, 418,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   4, 419,   4,   4,  45,  47,  47,  47,  47,  47,
      4,   4,   4, 145,   4,  45, 420,  47,  47,  47,  47,  47,  47,   4, 185, 421,
      4,   4,   4, 422, 423, 424,  18, 425,   4,  47,  47,  47,  47,  47,  47,  47,
      4,   4,   4,   4, 141, 426,   1, 166, 396, 173,  47,  47,  47,  47,  47,  47,
    427,  47,  47,  47,  47,  47,  47,  47,   4,   4,   4,   4,   4,   4, 226, 119,
    145, 428, 429,  47,  47,  47,  47,  47,   4,   4,   4,   4,   4,   4,   4, 155,
      4,   4,  21,   4,   4,   4, 430,   1, 431,   4, 432,   4,   4, 185,  47,  47,
      4,   4,   4,   4, 433,  47,  47,  47,   4,   4,   4,   4,   4, 225,   4, 262,
      4,   4,   4,   4,   4, 186,   4,   4,   4, 146, 434, 435, 436,   4,   4,   4,
    437, 438,   4, 439, 440,  85,   4,   4,   4,   4, 260,   4,   4,   4,   4,   4,
      4,   4,   4,   4, 441, 442, 442, 442,   4,   4,   4,   4, 443, 320,  47,  47,
    436,   4, 444, 445, 446, 447, 448, 449, 450, 369, 451, 369,  47,  47,  47, 262,
    273, 273, 277, 273, 273, 273, 273, 273, 273, 275, 291, 290, 290, 290, 273, 276,
    452, 227, 453, 227, 227, 227, 454, 227, 227, 455,  47,  47,  47,  47, 456, 457,
    458, 273, 273, 292, 459, 427,  47,  47, 273, 273, 296, 273, 273, 273, 273, 289,
    273, 460, 273, 461, 291, 462, 273, 463, 273, 273, 464, 465, 273, 273, 273, 291,
    466, 467, 468, 469, 470, 273, 273, 274, 273, 273, 471, 273, 273, 472, 273, 473,
    273, 273, 273, 273, 474,   4,   4, 475, 273, 273, 273, 273, 273,  47, 296, 275,
      4,   4,   4,   4,   4,   4,   4, 371,   4,   4,   4,   4,   4, 141,  47,  47,
    369,   4,   4,   4,  76, 140,   4,   4,  76,   4, 185,  47,  47,  47,  47,  47,
    273, 273, 273, 273, 273, 273, 273, 289, 476,  47,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,  47,
};

static RE_UINT8 re_line_break_stage_4[] = {
      0,   0,   0,   0,   1,   2,   3,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      4,   5,   6,   7,   8,   9,  10,  11,  12,  12,  12,  12,  12,  13,  14,  15,
     14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  16,  17,  14,
     14,  14,  14,  14,  14,  16,  18,  19,   0,   0,  20,   0,   0,   0,   0,   0,
     21,  22,  23,  24,  25,  26,  27,  14,  22,  28,  29,  28,  28,  26,  28,  30,
     14,  14,  14,  24,  14,  14,  14,  14,  14,  14,  14,  24,  31,  28,  31,  14,
     25,  14,  14,  14,  28,  28,  24,  32,   0,   0,   0,   0,   0,   0,   0,  33,
      0,   0,   0,   0,   0,   0,  34,  34,  34,  35,   0,   0,   0,   0,   0,   0,
     14,  14,  14,  14,  36,  14,  14,  37,  36,  36,  14,  14,  14,  38,  38,  14,
     14,  39,  14,  14,  14,  14,  14,  14,  14,  19,   0,   0,   0,  14,  14,  14,
     39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  38,  39,  14,  14,  14,
     14,  14,  14,  14,  40,  41,  39,   9,  42,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  43,  19,  44,   0,  45,  36,  36,  36,  36,
     46,  46,  46,  46,  46,  46,  46,  46,  46,  46,  46,  46,  46,  47,  36,  36,
     46,  48,  38,  36,  36,  36,  36,  36,  14,  14,  14,  14,  49,  50,  13,  14,
      0,   0,   0,   0,   0,  51,  52,  53,  14,  14,  14,  14,  14,  19,   0,   0,
     12,  12,  12,  12,  12,  54,  55,  14,  44,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  56,   0,   0,   0,  44,  19,   0,   0,  44,  19,  44,   0,   0,  14,
     12,  12,  12,  12,  12,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  39,
     19,  14,  14,  14,  14,  14,  14,  14,   0,   0,   0,   0,   0,  52,  39,  14,
     14,  14,  14,   0,   0,   0,   0,   0,  44,  36,  36,  36,  36,  36,  36,  36,
      0,   0,  14,  14,  57,  38,  36,  36,  14,  14,  14,   0,   0,  19,   0,   0,
      0,   0,  19,   0,  19,   0,   0,  36,  14,  14,  14,  14,  14,  14,  14,  38,
     14,  14,  14,  14,  19,   0,  36,  38,  36,  36,  36,  36,  36,  36,  36,  36,
     14,  38,  36,  36,  36,  36,  36,  36,  36,  36,   0,   0,   0,   0,   0,   0,
      0,   0,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,   0,  44,   0,
     19,   0,   0,   0,  14,  14,  14,  14,  14,   0,  58,  12,  12,  12,  12,  12,
     19,   0,  39,  14,  14,  14,  38,  39,  38,  39,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  38,  14,  14,  14,  38,  38,  36,  14,  14,  36,  44,   0,
      0,   0,  52,  42,  52,  42,   0,  38,  36,  36,  36,  42,  36,  36,  14,  39,
     14,   0,  36,  12,  12,  12,  12,  12,  14,  50,  14,  14,  49,   9,  36,  36,
     42,   0,  39,  14,  14,  38,  36,  39,  38,  14,  39,  38,  14,  36,  52,   0,
      0,  52,  36,  42,  52,  42,   0,  36,  42,  36,  36,  36,  39,  14,  38,  38,
     36,  36,  36,  12,  12,  12,  12,  12,   0,  14,  19,  36,  36,  36,  36,  36,
     42,   0,  39,  14,  14,  14,  14,  39,  38,  14,  39,  14,  14,  36,  44,   0,
      0,   0,   0,  42,   0,  42,   0,  36,  38,  36,  36,  36,  36,  36,  36,  36,
      9,  36,  36,  36,  36,  36,  36,  36,  42,   0,  39,  14,  14,  14,  38,  39,
      0,   0,  52,  42,  52,  42,   0,  36,  36,  36,  36,   0,  36,  36,  14,  39,
     14,  14,  14,  14,  36,  36,  36,  36,  36,  44,  39,  14,  14,  38,  36,  14,
     38,  14,  14,  36,  39,  38,  38,  14,  36,  39,  38,  36,  14,  38,  36,  14,
     14,  14,  14,  14,  14,  36,  36,   0,   0,  52,  36,   0,  52,   0,   0,  36,
     38,  36,  36,  42,  36,  36,  36,  36,  14,  14,  14,  14,   9,  38,  36,  36,
      0,   0,  39,  14,  14,  14,  38,  14,  38,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  36,  39,   0,   0,   0,  52,   0,  52,   0,   0,  36,
     36,  36,  42,  52,  14,  36,  36,  36,  36,  36,  36,  36,  14,  14,  14,  14,
     42,   0,  39,  14,  14,  14,  38,  14,  14,  14,  39,  14,  14,  36,  44,   0,
     36,  36,  42,  52,  36,  36,  36,  38,  39,  38,  36,  36,  36,  36,  36,  36,
     14,  14,  14,  14,  14,  38,  39,   0,   0,   0,  52,   0,  52,   0,   0,  38,
     36,  36,  36,  42,  36,  36,  36,  36,  14,  14,  14,  36,  59,  14,  14,  14,
     36,   0,  39,  14,  14,  14,  14,  14,  14,  14,  14,  38,  36,  14,  14,  14,
     14,  39,  14,  14,  14,  14,  39,  36,  14,  14,  14,  38,  36,  52,  36,  42,
      0,   0,  52,  52,   0,   0,   0,   0,  36,   0,  38,  36,  36,  36,  36,  36,
     60,  61,  61,  61,  61,  61,  61,  61,  61,  61,  61,  61,  61,  61,  61,  61,
     61,  61,  61,  61,  61,  62,  36,  63,  61,  61,  61,  61,  61,  61,  61,  64,
     12,  12,  12,  12,  12,  58,  36,  36,  60,  62,  62,  60,  62,  62,  60,  36,
     36,  36,  61,  61,  60,  61,  61,  61,  60,  61,  60,  60,  36,  61,  60,  61,
     61,  61,  61,  61,  61,  60,  61,  36,  61,  61,  62,  62,  61,  61,  61,  36,
     12,  12,  12,  12,  12,  36,  61,  61,  32,  65,  29,  65,  66,  67,  68,  53,
     53,  69,  56,  14,   0,  14,  14,  14,  14,  14,  43,  19,  19,  70,  70,   0,
     14,  14,  14,  14,  39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  38,  36,
     42,   0,   0,   0,   0,   0,   0,   1,   0,   0,   1,   0,  14,  14,  19,   0,
      0,   0,   0,   0,  42,   0,   0,   0,   0,   0,   0,   0,   0,   0,  52,  58,
     14,  14,  14,  44,  14,  14,  38,  14,  65,  71,  14,  14,  72,  73,  36,  36,
     12,  12,  12,  12,  12,  58,  14,  14,  12,  12,  12,  12,  12,  61,  61,  61,
     14,  14,  14,  39,  36,  36,  39,  36,  74,  74,  74,  74,  74,  74,  74,  74,
     75,  75,  75,  75,  75,  75,  75,  75,  75,  75,  75,  75,  76,  76,  76,  76,
     76,  76,  76,  76,  76,  76,  76,  76,  14,  14,  14,  14,  38,  14,  14,  36,
     14,  14,  14,  38,  38,  14,  14,  36,  38,  14,  14,  36,  14,  14,  14,  38,
     38,  14,  14,  36,  14,  14,  14,  14,  14,  14,  14,  38,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  38,  42,   0,  27,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  36,  36,  36,  14,  14,  38,  36,  36,  36,  36,  36,
     77,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  16,  78,  36,
     14,  14,  14,  14,  14,  27,  58,  14,  14,  14,  14,  14,  38,  36,  36,  36,
     14,  14,  14,  14,  14,  14,  38,  14,  14,   0,  52,  36,  36,  36,  36,  36,
     14,   0,   1,  41,  36,  36,  36,  36,  14,   0,  36,  36,  36,  36,  36,  36,
     38,   0,  36,  36,  36,  36,  36,  36,  61,  61,  58,  79,  77,  80,  61,  36,
     12,  12,  12,  12,  12,  36,  36,  36,  14,  53,  58,  29,  53,  19,   0,  73,
     14,  14,  14,  14,  19,  38,  36,  36,  14,  14,  14,  36,  36,  36,  36,  36,
      0,   0,   0,   0,   0,   0,  36,  36,  38,  36,  53,  12,  12,  12,  12,  12,
     61,  61,  61,  61,  61,  61,  61,  36,  61,  61,  62,  36,  36,  36,  36,  36,
     61,  61,  61,  61,  61,  61,  36,  36,  61,  61,  61,  61,  61,  36,  36,  36,
     12,  12,  12,  12,  12,  62,  36,  61,  14,  14,  14,  19,   0,   0,  36,  14,
     61,  61,  61,  61,  61,  61,  61,  62,  61,  61,  61,  61,  61,  61,  62,  42,
      0,   0,   0,   0,   0,   0,   0,  52,   0,   0,  44,  14,  14,  14,  14,  14,
     14,  14,   0,   0,   0,   0,   0,   0,   0,   0,  44,  14,  14,  14,  36,  36,
     12,  12,  12,  12,  12,  58,  27,  58,  77,  14,  14,  14,  14,  19,   0,   0,
      0,   0,  14,  14,  14,  14,  38,  36,   0,  44,  14,  14,  14,  14,  14,  14,
     19,   0,   0,   0,   0,   0,   0,  14,   0,   0,  36,  36,  36,  36,  14,  14,
      0,   0,   0,   0,  36,  81,  58,  58,  12,  12,  12,  12,  12,  36,  39,  14,
     14,  14,  14,  14,  14,  14,  14,  58,   0,  44,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  44,  14,  19,  14,  14,   0,  44,  38,   0,  36,  36,  36,
      0,   0,   0,  36,  36,  36,   0,   0,  14,  14,  14,  36,  14,  14,  14,  36,
     14,  14,  14,  14,  39,  39,  39,  39,  14,  14,  14,  14,  14,  14,  14,  36,
     14,  14,  38,  14,  14,  14,  14,  14,  14,  14,  36,  14,  14,  14,  39,  14,
     36,  14,  38,  14,  14,  14,  32,  38,  58,  58,  58,  82,  58,  83,   0,   0,
     82,  58,  84,  25,  85,  86,  85,  86,  28,  14,  87,  88,  89,   0,   0,  33,
     50,  50,  50,  50,   7,  90,  91,  14,  14,  14,  92,  93,  91,  14,  14,  14,
     14,  14,  14,  77,  58,  58,  27,  58,  94,  14,  38,   0,   0,   0,   0,   0,
     14,  36,  25,  14,  14,  14,  16,  95,  24,  28,  25,  14,  14,  14,  16,  78,
     23,  23,  23,   6,  23,  23,  23,  23,  23,  23,  23,  22,  23,   6,  23,  23,
     23,  23,  23,  23,  23,  23,  23,  23,  52,  36,  36,  36,  36,  36,  36,  36,
     14,  49,  24,  14,  49,  14,  14,  14,  14,  24,  14,  96,  14,  14,  14,  14,
     24,  25,  14,  14,  14,  24,  14,  14,  14,  14,  28,  14,  14,  24,  14,  25,
     28,  28,  28,  28,  28,  28,  14,  14,  28,  28,  28,  28,  28,  14,  14,  14,
     14,  14,  14,  14,  24,  36,  36,  36,  14,  25,  25,  14,  14,  14,  14,  14,
     25,  28,  14,  24,  25,  24,  14,  24,  24,  23,  24,  14,  14,  25,  24,  28,
     25,  24,  24,  24,  28,  28,  25,  25,  14,  14,  28,  28,  14,  14,  28,  14,
     14,  14,  14,  14,  25,  14,  25,  14,  14,  25,  14,  14,  14,  14,  14,  14,
     28,  14,  28,  28,  14,  28,  14,  28,  14,  28,  14,  28,  14,  14,  14,  14,
     14,  14,  24,  14,  24,  14,  14,  14,  14,  14,  24,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  14,  24,  14,  14,  14,  14,  70,  70,  14,  14,
     14,  25,  14,  14,  14,  97,  14,  14,  14,  14,  14,  14,  16,  98,  14,  14,
     97,  97,  14,  14,  14,  38,  36,  36,  14,  14,  14,  38,  36,  36,  36,  36,
     14,  14,  14,  14,  14,  38,  36,  36,  28,  28,  28,  28,  28,  28,  28,  28,
     28,  28,  28,  28,  28,  28,  28,  25,  28,  28,  25,  14,  14,  14,  14,  14,
     14,  28,  28,  14,  14,  14,  14,  14,  28,  24,  28,  28,  28,  14,  14,  14,
     14,  28,  14,  28,  14,  14,  28,  14,  28,  14,  14,  28,  25,  24,  14,  28,
     28,  14,  14,  14,  14,  14,  14,  14,  14,  28,  28,  14,  14,  14,  14,  24,
     97,  97,  24,  25,  24,  14,  14,  28,  14,  14,  97,  28,  99,  97,  97,  97,
     14,  14,  14,  14, 100,  97,  14,  14,  25,  25,  14,  14,  14,  14,  14,  14,
     28,  24,  28,  24, 101,  25,  28,  24,  14,  14,  14,  14,  14,  14,  14, 100,
     14,  14,  14,  14,  14,  14,  14,  28,  14,  14,  14,  14,  14,  14, 100,  97,
     97,  97,  97,  97, 101,  28, 102, 100,  97, 102, 101,  28,  97,  28, 101, 102,
     97,  24,  14,  14,  28, 101,  28,  28, 102,  97,  97, 102,  97, 101, 102,  97,
     97,  97,  99,  14,  97,  97,  97,  14,  14,  14,  14,  24,  14,   7,  85,  85,
      5,  53,  14,  14,  70,  70,  70,  70,  70,  70,  70,  28,  28,  28,  28,  28,
     28,  28,  14,  14,  14,  14,  14,  14,  14,  14,  16,  98,  14,  14,  14,  14,
     14,  14,  14,  70,  70,  70,  70,  70,  14,  16, 103, 103, 103, 103, 103, 103,
    103, 103, 103, 103,  98,  14,  14,  14,  14,  14,  14,  14,  14,  14,  70,  14,
     14,  14,  24,  28,  28,  14,  14,  14,  14,  14,  36,  14,  14,  14,  14,  14,
     14,  14,  14,  36,  14,  14,  14,  14,  14,  14,  14,  14,  14,  36,  39,  14,
     14,  36,  36,  36,  36,  36,  36,  36,  14,  14,  14,  14,  14,  14,  14,  19,
      0,  14,  36,  36, 104,  58,  77, 105,  14,  14,  14,  14,  36,  36,  36,  39,
     41,  36,  36,  36,  36,  36,  36,  42,  14,  14,  14,  38,  14,  14,  14,  38,
     85,  85,  85,  85,  85,  85,  85,  58,  58,  58,  58,  27, 106,  14,  85,  14,
     85,  70,  70,  70,  70,  58,  58,  56,  58,  27,  77,  14,  14, 107,  58,  77,
     58, 108,  36,  36,  36,  36,  36,  36,  97,  97,  97,  97,  97,  97,  97,  97,
     97,  97,  97,  97,  97, 109,  97,  97,  97,  97,  36,  36,  36,  36,  36,  36,
     97,  97,  97,  36,  36,  36,  36,  36,  97,  97,  97,  97,  97,  97,  36,  36,
     18, 110, 111,  97,  70,  70,  70,  70,  70,  97,  70,  70,  70,  70, 112, 113,
     97,  97,  97,  97,  97,   0,   0,   0,  97,  97, 114,  97,  97, 111, 115,  97,
    116, 117, 117, 117, 117,  97,  97,  97,  97, 117,  97,  97,  97,  97,  97,  97,
     97, 117, 117, 117,  97,  97,  97, 118,  97,  97, 117, 119,  42, 120,  91, 115,
    121, 117, 117, 117, 117,  97,  97,  97,  97,  97, 117, 118,  97, 111, 122, 115,
     36,  36, 109,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  36,
    109,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97, 123,
     97,  97,  97,  97,  97, 123,  36,  36, 124, 124, 124, 124, 124, 124, 124, 124,
     97,  97,  97,  97,  28,  28,  28,  28,  97,  97, 111,  97,  97,  97,  97,  97,
     97,  97,  97,  97,  97,  97, 123,  36,  97,  97,  97, 123,  36,  36,  36,  36,
     14,  14,  14,  14,  14,  14,  27, 105,  12,  12,  12,  12,  12,  14,  36,  36,
      0,  44,   0,   0,   0,   0,   0,  14,  14,  14,  14,  14,  14,  14,  14,  42,
      0,  27,  58,  58,  36,  36,  36,  36,  36,  36,  36,  39,  14,  14,  14,  14,
     14,  44,  14,  44,  14,  19,  14,  14,  14,  19,   0,   0,  14,  14,  36,  36,
     14,  14,  14,  14, 125,  36,  36,  36,  14,  14,  65,  53,  36,  36,  36,  36,
      0,  14,  14,  14,  14,  14,  14,  14,   0,   0,  52,  36,  36,  36,  36,  58,
      0,  14,  14,  14,  14,  14,  36,  36,  14,  14,  14,   0,   0,   0,   0,  58,
     14,  14,  14,  19,   0,   0,   0,   0,   0,   0,  36,  36,  36,  36,  36,  39,
     74,  74,  74,  74,  74,  74, 126,  36,  14,  19,   0,   0,   0,   0,   0,   0,
     44,  14,  14,  27,  58,  14,  14,  39,  12,  12,  12,  12,  12,  36,  36,  14,
     12,  12,  12,  12,  12,  61,  61,  62,  14,  14,  14,  14,  19,   0,   0,   0,
      0,   0,   0,  52,  36,  36,  36,  36,  14,  19,  14,  14,  14,  14,   0,  36,
     12,  12,  12,  12,  12,  36,  27,  58,  61,  62,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  60,  61,  61,  58,  14,  19,  52,  36,  36,  36,  36,
     39,  14,  14,  38,  39,  14,  14,  38,  39,  14,  14,  38,  36,  36,  36,  36,
     36,  36,  14,  36,  36,  36,  36,  36,  14,  19,   0,   0,   0,   1,   0,  36,
    127, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 127, 128,
    128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 128, 127, 128, 128, 128,
    128, 128, 127, 128, 128, 128, 128, 128, 128, 128,  36,  36,  36,  36,  36,  36,
     75,  75,  75, 129,  36, 130,  76,  76,  76,  76,  76,  76,  76,  76,  36,  36,
    131, 131, 131, 131, 131, 131, 131, 131,  36,  39,  14,  14,  36,  36, 132, 133,
     46,  46,  46,  46,  48,  46,  46,  46,  46,  46,  46,  47,  46,  46,  47,  47,
     46, 132,  47,  46,  46,  46,  46,  46,  36,  39,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  14, 103,  36,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  14, 125,  36, 134, 135,  57, 136, 137,  36,  36,  36,
      0,   0,   0,   0,   0,   0,   0,  36,  97,  97, 138, 103, 103, 103, 103, 103,
    103, 103, 110, 138, 110,  97,  97,  97, 110,  78,  91,  53, 138, 103, 103, 110,
     97,  97,  97, 123, 139, 140,  36,  36,  14,  14,  14,  14,  14,  14,  38, 141,
    104,  97,   6,  97,  70,  97, 110, 110,  97,  97,  97,  97,  97,  91,  97, 142,
     97,  97,  97,  97,  97, 138, 143,  97,  97,  97,  97,  97,  97, 138, 143, 138,
    113,  70,  93, 144, 124, 124, 124, 124, 145,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  14,  91,  36,  14,  14,  14,  36,  14,  14,  14,
     36,  14,  14,  14,  36,  14,  38,  36,  22,  97, 139, 146,  14,  14,  14,  38,
     36,  36,  36,  36,  42,   0, 147,  36,  14,  14,  14,  14,  14,  14,  39,  14,
     14,  14,  14,  14,  14,  38,  14,  39,  58,  41,  36,  39,  14,  14,  14,  14,
     14,  14,  36,  39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  36,  36,
     14,  14,  14,  14,  14,  14,  19,  36,  14,  14,  36,  36,  36,  36,  36,  36,
     14,  14,  14,   0,   0,  52,  36,  36,  14,  14,  14,  14,  14,  14,  14,  81,
     14,  14,  36,  36,  14,  14,  14,  14,  77,  14,  14,  36,  36,  36,  36,  36,
     14,  14,  36,  36,  36,  36,  36,  39,  14,  14,  14,  36,  38,  14,  14,  14,
     14,  14,  14,  39,  38,  36,  38,  39,  14,  14,  14,  81,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  36,  81,  14,  14,  14,  14,  14,  36,  36,  39,
     14,  14,  14,  14,  36,  36,  36,  14,  19,   0,  42,  52,  36,  36,   0,   0,
     14,  14,  39,  14,  39,  14,  14,  14,  14,  14,  36,  36,   0,  52,  36,  42,
     58,  58,  58,  58,  38,  36,  36,  36,  14,  14,  19,  52,  36,  39,  14,  14,
     58,  58,  58, 148,  36,  36,  36,  36,  14,  14,  14,  36,  81,  58,  58,  58,
     14,  38,  36,  36,  14,  14,  14,  14,  14,  36,  36,  36,  39,  14,  38,  36,
     36,  36,  36,  36,  39,  14,  14,  14,  14,  14,  14,  14,   0,   0,   0,   0,
      0,   0,   0,   1,  77,  14,  14,  36,  14,  14,  14,  12,  12,  12,  12,  12,
     36,  36,  36,  36,  36,  36,  36,  42,   0,   0,   0,   0,   0,  44,  14,  58,
     58,  36,  36,  36,  36,  36,  36,  36,   0,   0,  52,  12,  12,  12,  12,  12,
     58,  58,  36,  36,  36,  36,  36,  36,  14,  19,  32,  38,  36,  36,  36,  36,
     44,  14,  27,  77,  41,  36,  39,  36,  12,  12,  12,  12,  12,  38,  36,  36,
     14,  14,  14,  14,  14,  14,   0,   0,   0,   0,   0,   0,  58,  27,  77,  36,
      0,   0,   0,   0,   0,  52,  36,  36,  36,  36,  36,  42,  36,  36,  39,  14,
     14,   0,  36,   0,   0,   0,  52,  36,   0,   0,  52,  36,  36,  36,  36,  36,
      0,   0,  14,  14,  36,  36,  36,  36,   0,   0,   0,  36,   0,   0,   0,   0,
    149,  58,  53,  14,  27,  36,  36,  36,   1,  77,  38,  36,  36,  36,  36,  36,
      0,   0,   0,   0,  36,  36,  36,  36,  14,  38,  36,  36,  36,  36,  36,  39,
     58,  58,  41,  36,  36,  36,  36,  36,  14,  14,  14,  14, 150,  70, 113,  14,
     14,  98,  14,  70,  70,  14,  14,  14,  14,  14,  14,  14,  16, 113,  14,  14,
     12,  12,  12,  12,  12,  36,  36,  58,   0,   0,   1,  36,  36,  36,  36,  36,
      0,   0,   0,   1,  58,  14,  14,  14,  14,  14,  77,  36,  36,  36,  36,  36,
     12,  12,  12,  12,  12,  39,  14,  14,  14,  14,  14,  14,  36,  36,  39,  14,
     19,   0,   0,   0,   0,   0,   0,   0,  97,  36,  36,  36,  36,  36,  36,  36,
     14,  14,  14,  14,  14,  36,  19,   1,   0,   0,  36,  36,  36,  36,  36,  36,
     14,  14,  19,   0,   0,  14,  19,   0,   0,  44,  19,   0,   0,   0,  14,  14,
     14,  14,  14,  14,  14,   0,   0,  14,  14,   0,  44,  36,  36,  36,  36,  36,
     36,  38,  39,  38,  39,  14,  38,  14,  14,  14,  14,  14,  14,  39,  39,  14,
     14,  14,  39,  14,  14,  14,  14,  14,  14,  14,  14,  39,  14,  38,  39,  14,
     14,  14,  38,  14,  14,  14,  38,  14,  14,  14,  14,  14,  14,  39,  14,  38,
     14,  14,  38,  38,  36,  14,  14,  14,  14,  14,  14,  14,  14,  14,  36,  12,
     12,  12,  12,  12,  12,  12,  12,  12,  14,  14,  38,  39,  14,  14,  14,  14,
     39,  38,  38,  39,  39,  14,  14,  14,  14,  38,  14,  14,  39,  39,  36,  36,
     36,  38,  36,  39,  39,  39,  39,  14,  39,  38,  38,  39,  39,  39,  39,  39,
     39,  38,  38,  39,  14,  38,  14,  14,  14,  38,  14,  14,  39,  14,  38,  38,
     14,  14,  14,  14,  14,  39,  14,  14,  39,  14,  39,  14,  14,  39,  14,  14,
     28,  28,  28,  28,  28,  28, 151,  36,  28,  28,  28,  28,  28,  28,  28,  38,
     28,  28,  28,  28,  28,  14,  36,  36,  28,  28,  28,  28,  28, 151,  36,  36,
     36,  36,  36, 152, 152, 152, 152, 152, 152, 152, 152, 152, 152, 152, 152, 152,
     97, 123,  36,  36,  36,  36,  36,  36,  97,  97,  97,  97, 123,  36,  36,  36,
     97,  97,  97,  97,  97,  97,  14,  97,  97,  97,  99, 100,  97,  97, 100,  97,
     36,  36,  97,  97,  97,  97,  97,  97,  97,  97,  97,  97,  36,  36,  36,  36,
    100, 100, 100,  97,  97,  97,  97,  99,  99, 100,  97,  97,  97,  97,  97,  97,
     14,  14,  14, 100,  97,  97,  97,  97,  97,  97,  97,  99,  14,  14,  14,  14,
     14,  14, 100,  97,  97,  97,  97,  97,  97,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14, 123,  36,  36,  97,  97, 109,  97,  97,  97,  97,  97,
     97,  97,  14,  14,  14,  14,  97,  97,  97,  97,  14,  14,  14,  97,  97,  97,
     97, 123, 109,  97,  97,  97,  97,  97,  14,  14,  14,  85, 153,  91,  14,  14,
     42,  36,  36,  36,  36,  36,  36,  36,
};

static RE_UINT8 re_line_break_stage_5[] = {
    16, 16, 16, 18, 22, 20, 20, 21, 19,  6,  3, 12,  9, 10, 12,  3,
     1, 36, 12,  9,  8, 15,  8,  7, 11, 11,  8,  8, 12, 12, 12,  6,
    12,  1,  9, 36, 18,  2, 12, 16, 16, 29,  4,  1, 10,  9,  9,  9,
    12, 25, 25, 12, 25,  3, 12, 18, 25, 25, 17, 12, 25,  1, 17, 25,
    12, 17, 16,  4,  4,  4,  4, 16,  0,  0,  8, 12, 12,  0,  0, 12,
     0,  8, 18,  0,  0, 16, 18, 16, 16, 12,  6, 16, 37, 37, 37,  0,
    37, 12, 12, 10, 10, 10, 16,  6, 16,  0,  6,  6, 10, 11, 11, 12,
     6, 12,  8,  6, 18, 18,  0, 10,  0, 24, 24, 24, 24,  0,  0,  9,
    24, 12, 17, 17,  4, 17, 17, 18,  4,  6,  4, 12,  1,  2, 18, 17,
    12,  4,  4,  0, 31, 31, 32, 32, 33, 33, 18, 12,  2,  0,  5, 24,
    18,  9,  0, 18, 18,  4, 18, 28, 26, 25,  3,  3,  1,  3, 14, 14,
    14, 18, 20, 20,  3, 25,  5,  5,  8,  1,  2,  5, 30, 12,  2, 25,
     9, 12, 13, 13,  2, 12, 13, 12, 12, 13, 13, 25, 25, 13,  2,  1,
     0,  6,  6, 18,  1, 18, 26, 26,  1,  0,  0, 13,  2, 13, 13,  5,
     5,  1,  2,  2, 13, 16,  5, 13,  0, 38, 13, 38, 38, 13, 38,  0,
    16,  5,  5, 38, 38,  5, 13,  0, 38, 38, 10, 12, 31,  0, 34, 35,
    35, 35, 32,  0,  0, 33, 27, 27,  0, 37, 16, 37,  8,  2,  2,  8,
     6,  1,  2, 14, 13,  1, 13,  9, 10, 13,  0, 30, 13,  6, 13,  2,
    12, 38, 38, 12,  9,  0, 23, 25, 14,  0, 16, 17,  1,  1, 25,  0,
    39, 39,  3,  5,
};

/* Line_Break: 8332 bytes. */

RE_UINT32 re_get_line_break(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_line_break_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_line_break_stage_2[pos + f] << 3;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_line_break_stage_3[pos + f] << 3;
    f = code >> 1;
    code ^= f << 1;
    pos = (RE_UINT32)re_line_break_stage_4[pos + f] << 1;
    value = re_line_break_stage_5[pos + code];

    return value;
}

/* Numeric_Type. */

static RE_UINT8 re_numeric_type_stage_1[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 11, 11, 11, 12,
    13, 14, 15, 11, 11, 11, 16, 11, 11, 11, 11, 11, 11, 17, 18, 19,
    20, 11, 21, 22, 11, 11, 23, 11, 11, 11, 11, 11, 11, 11, 11, 24,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
};

static RE_UINT8 re_numeric_type_stage_2[] = {
     0,  1,  1,  1,  1,  1,  2,  3,  1,  4,  5,  6,  7,  8,  9, 10,
    11,  1,  1, 12,  1,  1, 13, 14, 15, 16, 17, 18, 19,  1,  1,  1,
    20, 21,  1,  1, 22,  1,  1, 23,  1,  1,  1,  1, 24,  1,  1,  1,
    25, 26, 27,  1, 28,  1,  1,  1, 29,  1,  1, 30,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 31, 32,
     1, 33,  1, 34,  1,  1, 35,  1, 36,  1,  1,  1,  1,  1, 37, 38,
     1,  1, 39, 40,  1,  1,  1, 41,  1,  1,  1,  1,  1,  1,  1, 42,
     1,  1,  1, 43,  1,  1, 44,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    45,  1,  1,  1, 46,  1,  1,  1,  1,  1,  1,  1, 47, 48,  1,  1,
     1,  1,  1,  1,  1,  1, 49,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 50,  1, 51, 52, 53, 54,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1, 55,  1,  1,  1,  1,  1, 15,
     1, 56, 57, 58, 59,  1,  1,  1, 60, 61, 62, 63,  1,  1, 64,  1,
    65, 66, 54,  1, 67,  1, 68,  1, 69,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1, 70,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 71, 72,  1,  1,  1,  1,
     1,  1,  1, 73,  1,  1,  1, 74,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 75,  1,  1,  1,  1,  1,  1,  1,
     1, 76,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    77, 78,  1,  1,  1,  1,  1,  1,  1, 79, 80, 81,  1,  1,  1,  1,
     1,  1,  1, 82,  1,  1,  1,  1,  1, 83,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 84,  1,  1,  1,  1,
     1,  1, 85,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 82,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_numeric_type_stage_3[] = {
     0,  1,  0,  0,  0,  2,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  3,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,  3,  0,
     0,  0,  0,  4,  0,  0,  0,  5,  0,  0,  0,  4,  0,  0,  0,  4,
     0,  0,  0,  6,  0,  0,  0,  7,  0,  0,  0,  8,  0,  0,  0,  4,
     0,  0,  0,  9,  0,  0,  0,  4,  0,  0,  1,  0,  0,  0,  1,  0,
     0, 10,  0,  0,  0,  0,  0,  0,  0,  0,  3,  0,  1,  0,  0,  0,
     0,  0,  0, 11,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 12,
     0,  0,  0,  0,  0,  0,  0, 13,  1,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  4,  0,  0,  0, 14,  0,  0,  0,  0,  0, 15,  0,  0,  0,
     0,  0,  1,  0,  0,  1,  0,  0,  0,  0, 15,  0,  0,  0,  0,  0,
     0,  0,  0, 16, 17,  0,  0,  0,  0,  0, 18, 19, 20,  0,  0,  0,
     0,  0,  0, 21, 22,  0,  0, 23,  0,  0,  0, 24, 25,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 26, 27, 28,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 29,  0,  0,  0,  0, 30, 31,  0, 30, 32,  0,  0,
    33,  0,  0,  0, 34,  0,  0,  0,  0, 35,  0,  0,  0,  0,  0,  0,
     0,  0, 36,  0,  0,  0,  0,  0, 37,  0, 26,  0, 38, 39, 40, 41,
    36,  0,  0, 42,  0,  0,  0,  0, 43,  0, 44, 45,  0,  0,  0,  0,
     0,  0, 46,  0,  0,  0, 47,  0,  0,  0,  0,  0,  0,  0, 48,  0,
     0,  0,  0,  0,  0,  0,  0, 49,  0,  0,  0, 50,  0,  0,  0, 51,
    52,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 53,
     0,  0, 54,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 55,  0,
    44,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 56,  0,  0,  0,
     0,  0,  0, 53,  0,  0,  0,  0,  0,  0,  0,  0, 44,  0,  0,  0,
     0, 54,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 57,  0,  0,
     0, 42,  0,  0,  0,  0,  0,  0,  0, 58, 59, 60,  0,  0,  0, 56,
     0,  3,  0,  0,  0,  0,  0, 61,  0, 62,  0,  0,  0,  0,  1,  0,
     3,  0,  0,  0,  0,  0,  1,  1,  0,  0,  1,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0, 63,  0, 55, 64, 26,
    65, 66, 19, 67, 68,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 69,
     0, 70, 71,  0,  0,  0, 72,  0,  0,  0,  0,  0,  0,  3,  0,  0,
     0,  0, 73, 74,  0, 75,  0,  0, 76,  0,  0,  0,  0,  0,  0,  0,
     0,  0, 77, 78, 79,  0,  0, 80,  0,  0, 73, 73,  0, 81,  0,  0,
     0,  0,  0, 82,  0,  0,  0,  0,  0,  0, 83, 84,  0,  0,  0,  1,
     0, 85,  0,  0,  0,  0,  1, 86,  0,  0,  0,  0,  0,  0,  1,  0,
     0,  0,  1,  0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  0, 87,
    19, 19, 19, 88,  0,  0,  0,  0,  0,  0,  0,  3,  0,  0,  0,  0,
     0,  0, 89, 90,  0,  0,  0,  0,  0,  0,  0, 91,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 92, 93,  0,  0,  0,  0,  0,  0, 75,  0,
    94,  0,  0,  0,  0,  0,  0,  0, 58,  0,  0, 43,  0,  0,  0, 95,
     0, 58,  0,  0,  0,  0,  0,  0,  0, 35,  0,  0, 96,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 97, 98,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 42,  0,  0,  0,  0,  0,  0,  0, 60,  0,  0,  0,
    48,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 36,  0,  0,  0,  0,
};

static RE_UINT8 re_numeric_type_stage_4[] = {
     0,  0,  0,  0,  0,  0,  1,  2,  0,  0,  3,  4,  1,  2,  0,  0,
     5,  1,  0,  0,  5,  1,  6,  7,  5,  1,  8,  0,  5,  1,  9,  0,
     5,  1,  0, 10,  5,  1, 11,  0,  1, 12, 13,  0,  0, 14, 15, 16,
     0, 17, 18,  0,  1,  2, 19,  7,  0,  0,  1, 20,  1,  2,  1,  2,
     0,  0, 21, 22, 23, 22,  0,  0,  0,  0, 19, 19, 19, 19, 19, 19,
    24,  7,  0,  0, 23, 25, 26, 27, 19, 23, 25, 13,  0, 28, 29, 30,
     0,  0, 31, 32, 23, 33, 34,  0,  0,  0,  0, 35, 36,  0,  0,  0,
    37,  7,  0,  9,  0,  0, 38,  0, 19,  7,  0,  0,  0, 19, 37, 19,
     0,  0, 37, 19, 35,  0,  0,  0, 39,  0,  0,  0,  0, 40,  0,  0,
     0, 35,  0,  0, 41, 42,  0,  0,  0, 43, 44,  0,  0,  0,  0, 36,
    18,  0,  0, 36,  0, 18,  0,  0,  0,  0, 18,  0, 43,  0,  0,  0,
    45,  0,  0,  0,  0, 46,  0,  0, 47, 43,  0,  0, 48,  0,  0,  0,
     0,  0,  0, 39,  0,  0, 42, 42,  0,  0,  0, 40,  0,  0,  0, 17,
     0, 49, 18,  0,  0,  0,  0, 45,  0, 43,  0,  0,  0,  0, 40,  0,
     0,  0, 45,  0,  0, 45, 39,  0, 42,  0,  0,  0, 45, 43,  0,  0,
     0,  0,  0, 18, 17, 19,  0,  0,  0,  0, 11,  0,  0, 39, 39, 18,
     0,  0, 50,  0, 36, 19, 19, 19, 19, 19, 13,  0, 19, 19, 19, 18,
     0, 51,  0,  0, 37, 19, 19, 13, 13,  0,  0,  0, 42, 40,  0,  0,
     0,  0, 52,  0,  0,  0,  0, 19,  0,  0,  0, 37, 36, 19,  0,  0,
     0,  0, 17, 13, 53,  0,  0,  0,  0,  0,  0, 54,  0,  0,  0, 55,
     0, 56,  0,  0,  0, 37,  0,  0, 23, 25, 19, 10,  0,  0, 57, 58,
    59,  1,  0,  0,  0,  0,  5,  1, 37, 19, 16,  0,  1, 12,  9,  0,
    19, 10,  0,  0,  0,  0,  1, 60,  7,  0,  0,  0, 19, 19,  7,  0,
     0,  5,  1,  1,  1,  1,  1,  1, 23, 61,  0,  0, 40,  0,  0,  0,
    39, 43,  0, 43,  0, 40,  0, 35,  0,  0,  0, 42,
};

static RE_UINT8 re_numeric_type_stage_5[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0,
    0, 2, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 3, 3,
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,
    1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 0,
    3, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0,
    0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1,
    1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
    3, 3, 2, 0, 0, 0, 0, 0, 2, 0, 0, 0, 2, 2, 2, 2,
    2, 2, 0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2,
    1, 1, 1, 0, 0, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1,
    0, 0, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 1, 2, 0, 0, 0, 0, 0, 0, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 1, 2, 1, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1,
    0, 0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0,
    0, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 1,
    0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0,
    0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0,
    0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 1, 1, 0, 0,
    0, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 0,
    0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,
    0, 1, 1, 1, 1, 1, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1,
    0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3,
    3, 3, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 0, 0, 0,
};

/* Numeric_Type: 2252 bytes. */

RE_UINT32 re_get_numeric_type(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_numeric_type_stage_1[f] << 4;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_numeric_type_stage_2[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_numeric_type_stage_3[pos + f] << 2;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_numeric_type_stage_4[pos + f] << 3;
    value = re_numeric_type_stage_5[pos + code];

    return value;
}

/* Numeric_Value. */

static RE_UINT8 re_numeric_value_stage_1[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 11, 11, 11, 12,
    13, 14, 15, 11, 11, 11, 16, 11, 11, 11, 11, 11, 11, 17, 18, 19,
    20, 11, 21, 22, 11, 11, 23, 11, 11, 11, 11, 11, 11, 11, 11, 24,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11, 11,
};

static RE_UINT8 re_numeric_value_stage_2[] = {
     0,  1,  1,  1,  1,  1,  2,  3,  1,  4,  5,  6,  7,  8,  9, 10,
    11,  1,  1, 12,  1,  1, 13, 14, 15, 16, 17, 18, 19,  1,  1,  1,
    20, 21,  1,  1, 22,  1,  1, 23,  1,  1,  1,  1, 24,  1,  1,  1,
    25, 26, 27,  1, 28,  1,  1,  1, 29,  1,  1, 30,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 31, 32,
     1, 33,  1, 34,  1,  1, 35,  1, 36,  1,  1,  1,  1,  1, 37, 38,
     1,  1, 39, 40,  1,  1,  1, 41,  1,  1,  1,  1,  1,  1,  1, 42,
     1,  1,  1, 43,  1,  1, 44,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    45,  1,  1,  1, 46,  1,  1,  1,  1,  1,  1,  1, 47, 48,  1,  1,
     1,  1,  1,  1,  1,  1, 49,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 50,  1, 51, 52, 53, 54,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1, 55,  1,  1,  1,  1,  1, 15,
     1, 56, 57, 58, 59,  1,  1,  1, 60, 61, 62, 63,  1,  1, 64,  1,
    65, 66, 54,  1, 67,  1, 68,  1, 69,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1, 70,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 71, 72,  1,  1,  1,  1,
     1,  1,  1, 73,  1,  1,  1, 74,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 75,  1,  1,  1,  1,  1,  1,  1,
     1, 76,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    77, 78,  1,  1,  1,  1,  1,  1,  1, 79, 80, 81,  1,  1,  1,  1,
     1,  1,  1, 82,  1,  1,  1,  1,  1, 83,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 84,  1,  1,  1,  1,
     1,  1, 85,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 86,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_numeric_value_stage_3[] = {
      0,   1,   0,   0,   0,   2,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   3,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   3,   0,
      0,   0,   0,   4,   0,   0,   0,   5,   0,   0,   0,   4,   0,   0,   0,   4,
      0,   0,   0,   6,   0,   0,   0,   7,   0,   0,   0,   8,   0,   0,   0,   4,
      0,   0,   0,   9,   0,   0,   0,   4,   0,   0,   1,   0,   0,   0,   1,   0,
      0,  10,   0,   0,   0,   0,   0,   0,   0,   0,   3,   0,   1,   0,   0,   0,
      0,   0,   0,  11,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  12,
      0,   0,   0,   0,   0,   0,   0,  13,   1,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   4,   0,   0,   0,  14,   0,   0,   0,   0,   0,  13,   0,   0,   0,
      0,   0,   1,   0,   0,   1,   0,   0,   0,   0,  13,   0,   0,   0,   0,   0,
      0,   0,   0,  15,   3,   0,   0,   0,   0,   0,  16,  17,  18,   0,   0,   0,
      0,   0,   0,  19,  20,   0,   0,  21,   0,   0,   0,  22,  23,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  24,  25,  26,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  27,   0,   0,   0,   0,  28,  29,   0,  28,  30,   0,   0,
     31,   0,   0,   0,  32,   0,   0,   0,   0,  33,   0,   0,   0,   0,   0,   0,
      0,   0,  34,   0,   0,   0,   0,   0,  35,   0,  36,   0,  37,  38,  39,  40,
     41,   0,   0,  42,   0,   0,   0,   0,  43,   0,  44,  45,   0,   0,   0,   0,
      0,   0,  46,   0,   0,   0,  47,   0,   0,   0,   0,   0,   0,   0,  48,   0,
      0,   0,   0,   0,   0,   0,   0,  49,   0,   0,   0,  50,   0,   0,   0,  51,
     52,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  53,
      0,   0,  54,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  55,   0,
     56,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  57,   0,   0,   0,
      0,   0,   0,  58,   0,   0,   0,   0,   0,   0,   0,   0,  59,   0,   0,   0,
      0,  60,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  61,   0,   0,
      0,  62,   0,   0,   0,   0,   0,   0,   0,  63,  64,  65,   0,   0,   0,  66,
      0,   3,   0,   0,   0,   0,   0,  67,   0,  68,   0,   0,   0,   0,   1,   0,
      3,   0,   0,   0,   0,   0,   1,   1,   0,   0,   1,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   1,   0,   0,   0,  69,   0,  70,  71,  72,
     73,  74,  75,  76,  77,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  78,
      0,  79,  80,   0,   0,   0,  81,   0,   0,   0,   0,   0,   0,   3,   0,   0,
      0,   0,  82,  83,   0,  84,   0,   0,  85,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  86,  87,  88,   0,   0,  89,   0,   0,  90,  90,   0,  91,   0,   0,
      0,   0,   0,  92,   0,   0,   0,   0,   0,   0,  93,  94,   0,   0,   0,   1,
      0,  95,   0,   0,   0,   0,   1,  96,   0,   0,   0,   0,   0,   0,   1,   0,
      0,   0,   1,   0,   0,   0,   3,   0,   0,   0,   0,   0,   0,   0,   0,  97,
     98,  99, 100, 101,   0,   0,   0,   0,   0,   0,   0,   3,   0,   0,   0,   0,
      0,   0, 102, 103,   0,   0,   0,   0,   0,   0,   0, 104,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 105, 106,   0,   0,   0,   0,   0,   0, 107,   0,
    108,   0,   0,   0,   0,   0,   0,   0, 109,   0,   0, 110,   0,   0,   0, 111,
      0, 112,   0,   0,   0,   0,   0,   0,   0, 113,   0,   0, 114,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 115, 116,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  62,   0,   0,   0,   0,   0,   0,   0, 117,   0,   0,   0,
    118,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 119,   0,   0,   0,   0,
      0,   0,   0,   0, 120,   0,   0,   0,
};

static RE_UINT8 re_numeric_value_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   0,
      0,   0,   0,   0,   4,   0,   5,   6,   1,   2,   3,   0,   0,   0,   0,   0,
      0,   7,   8,   9,   0,   0,   0,   0,   0,   7,   8,   9,   0,  10,  11,   0,
      0,   7,   8,   9,  12,  13,   0,   0,   0,   7,   8,   9,  14,   0,   0,   0,
      0,   7,   8,   9,   0,   0,   1,  15,   0,   7,   8,   9,  16,  17,   0,   0,
      1,   2,  18,  19,  20,   0,   0,   0,   0,   0,  21,   2,  22,  23,  24,  25,
      0,   0,   0,  26,  27,   0,   0,   0,   1,   2,   3,   0,   1,   2,   3,   0,
      0,   0,   0,   0,   1,   2,  28,   0,   0,   0,   0,   0,  29,   2,   3,   0,
      0,   0,   0,   0,  30,  31,  32,  33,  34,  35,  36,  37,  34,  35,  36,  37,
     38,  39,  40,   0,   0,   0,   0,   0,  34,  35,  36,  41,  42,  34,  35,  36,
     41,  42,  34,  35,  36,  41,  42,   0,   0,   0,  43,  44,  45,  46,   2,  47,
      0,   0,   0,   0,   0,  48,  49,  50,  34,  35,  51,  49,  50,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  52,   0,  53,   0,   0,   0,   0,   0,   0,
     21,   2,   3,   0,   0,   0,  54,   0,   0,   0,   0,   0,  48,  55,   0,   0,
     34,  35,  56,   0,   0,   0,   0,   0,   0,   0,  57,  58,  59,  60,  61,  62,
      0,   0,   0,   0,  63,  64,  65,  66,   0,  67,   0,   0,   0,   0,   0,   0,
     68,   0,   0,   0,   0,   0,   0,   0,   0,   0,  69,   0,   0,   0,   0,   0,
      0,   0,   0,  70,   0,   0,   0,   0,  71,  72,  73,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  74,   0,   0,   0,  75,   0,  76,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  77,  78,   0,   0,   0,   0,   0,   0,  79,
      0,   0,  80,   0,   0,   0,   0,   0,   0,   0,   0,  67,   0,   0,   0,   0,
      0,   0,   0,   0,  81,   0,   0,   0,   0,  82,   0,   0,   0,   0,   0,   0,
      0,  83,   0,   0,   0,   0,   0,   0,   0,   0,  84,  85,   0,   0,   0,   0,
     86,  87,   0,  88,   0,   0,   0,   0,  89,  80,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  90,   0,   0,   0,   0,   0,   5,   0,   5,   0,
      0,   0,   0,   0,   0,   0,  91,   0,   0,   0,   0,   0,   0,   0,   0,  92,
      0,   0,   0,  15,  75,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  93,
      0,   0,   0,  94,   0,   0,   0,   0,   0,   0,   0,   0,  95,   0,   0,   0,
      0,  95,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  96,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  97,   0,  98,   0,   0,   0,   0,   0,   0,
      0,   0,   0,  25,   0,   0,   0,   0,   0,   0,   0,  99,  68,   0,   0,   0,
      0,   0,   0,   0,  75,   0,   0,   0, 100,   0,   0,   0,   0,   0,   0,   0,
      0, 101,   0,  81,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 102,   0,
      0,   0,   0,   0,   0, 103,   0,   0,   0,  48,  49, 104,   0,   0,   0,   0,
      0,   0,   0,   0, 105, 106,   0,   0,   0,   0, 107,   0, 108,   0,  75,   0,
      0,   0,   0,   0, 103,   0,   0,   0,   0,   0,   0,   0, 109,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 110,   0, 111,   8,   9,  57,  58, 112, 113,
    114, 115, 116, 117, 118,   0,   0,   0, 119, 120, 121, 122, 123, 124, 125, 126,
    127, 128, 129, 130, 122, 131, 132,   0,   0,   0, 133,   0,   0,   0,   0,   0,
     21,   2,  22,  23,  24, 134, 135,   0, 136,   0,   0,   0,   0,   0,   0,   0,
    137,   0, 138,   0,   0,   0,   0,   0,   0,   0,   0,   0, 139, 140,   0,   0,
      0,   0,   0,   0,   0,   0, 141, 142,   0,   0,   0,   0,   0,   0,  21, 143,
      0, 111, 144, 145,   0,   0,   0,   0,   0,   0,   0,   0,   0, 146, 147,   0,
     34, 148,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 149,
      0,   0,   0,   0,   0,   0,   0, 150,   0,   0, 111, 145,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  34, 148,   0,   0,  21, 151,   0,   0,   0,   0,
     34,  35, 152, 153, 154, 155, 156, 157,   0,   0,   0,   0,  48,  49,  50, 158,
    159, 160,   8,   9,   0,   0,   0,   0,   0,   0,   0,   0,   0,   7,   8,   9,
     21,   2,  22,  23,  24, 161,   0,   0,   1,   2,  22,  23, 162,   0,   0,   0,
      8,   9,  49, 163,  35, 164,   2, 165, 166, 167,   9, 168, 169, 168, 170, 171,
    172, 173, 174, 175, 144, 176, 177, 178, 179, 180, 181, 182,   0,   0,   0,   0,
      0,   0,   0,   0,   1,   2, 183, 184, 185,   0,   0,   0,   0,   0,   0,   0,
     34,  35, 152, 153, 186,   0,   0,   0,   0,   0,   0,   7,   8,   9,   1,   2,
    187,   8,   9,   1,   2, 187,   8,   9,   0, 111,   8,   9,   0,   0,   0,   0,
    188,  49, 104,  29,   0,   0,   0,   0,  70,   0,   0,   0,   0,   0,   0,   0,
      0, 189,   0,   0,   0,   0,   0,   0,  98,   0,   0,   0,   0,   0,   0,   0,
     67,   0,   0,   0,   0,   0,   0,   0,   0,   0,  91,   0,   0,   0,   0,   0,
    190,   0,   0,  88,   0,   0,   0,  88,   0,   0, 101,   0,   0,   0,   0,  73,
      0,   0,   0,   0,   0,   0,  73,   0,   0,   0,   0,   0,   0,   0,  80,   0,
      0,   0,   0,   0,   0,   0, 107,   0,   0,   0,   0, 191,   0,   0,   0,   0,
      0,   0,   0,   0, 192,   0,   0,   0,
};

static RE_UINT8 re_numeric_value_stage_5[] = {
      0,   0,   0,   0,   2,  23,  25,  27,  29,  31,  33,  35,  37,  39,   0,   0,
      0,   0,  25,  27,   0,  23,   0,   0,  11,  15,  19,   0,   0,   0,   2,  23,
     25,  27,  29,  31,  33,  35,  37,  39,   3,   6,   9,  11,  19,  46,   0,   0,
      0,   0,  11,  15,  19,   3,   6,   9,  40,  85,  94,   0,  23,  25,  27,   0,
     40,  85,  94,  11,  15,  19,   0,   0,  37,  39,  15,  24,  26,  28,  30,  32,
     34,  36,  38,   1,   0,  23,  25,  27,  37,  39,  40,  50,  60,  70,  80,  81,
     82,  83,  84,  85, 103,   0,   0,   0,   0,   0,  47,  48,  49,   0,   0,   0,
     37,  39,  23,   0,   2,   0,   0,   0,   7,   5,   4,  12,  18,  10,  14,  16,
     20,   8,  21,   6,  13,  17,  22,  23,  23,  25,  27,  29,  31,  33,  35,  37,
     39,  40,  41,  42,  80,  85,  89,  94,  94,  98, 103,   0,   0,  33,  80, 107,
    112,   2,   0,   0,  43,  44,  45,  46,  47,  48,  49,  50,   0,   0,   2,  41,
     42,  43,  44,  45,  46,  47,  48,  49,  50,  23,  25,  27,  37,  39,  40,   2,
      0,   0,  23,  25,  27,  29,  31,  33,  35,  37,  39,  40,  39,  40,  23,  25,
      0,  15,   0,   0,   0,   0,   0,   2,  40,  50,  60,   0,  27,  29,   0,   0,
     39,  40,   0,   0,  40,  50,  60,  70,  80,  81,  82,  83,   0,  51,  52,  53,
     54,  55,  56,  57,  58,  59,  60,  61,  62,  63,  64,  65,   0,  66,  67,  68,
     69,  70,  71,  72,  73,  74,  75,  76,  77,  78,  79,  80,   0,  31,   0,   0,
      0,   0,   0,  25,   0,   0,  31,   0,   0,  35,   0,   0,  23,   0,   0,  35,
      0,   0,   0, 103,   0,  27,   0,   0,   0,  39,   0,   0,  25,   0,   0,   0,
     31,   0,  29,   0,   0,   0,   0, 116,  40,   0,   0,   0,   0,   0,   0,  94,
     27,   0,   0,   0,  85,   0,   0,   0, 116,   0,   0,   0,   0,   0, 118,   0,
      0,  25,   0,  37,   0,  33,   0,   0,   0,  40,   0,  94,  50,  60,   0,   0,
     70,   0,   0,   0,   0,  27,  27,  27,   0,   0,   0,  29,   0,   0,  23,   0,
      0,   0,  39,  50,   0,   0,  40,   0,  37,   0,   0,   0,   0,   0,  35,   0,
      0,   0,  39,   0,   0,   0,  85,   0,   0,   0,  29,   0,   0,   0,  25,   0,
      0,  94,   0,   0,   0,   0,  33,   0,  33,   0,   0,   0,   0,   0,   2,   0,
     35,  37,  39,   2,  11,  15,  19,   3,   6,   9,   0,   0,   0,   0,   0,  27,
      0,   0,   0,  40,   0,  33,   0,  33,   0,  40,   0,   0,   0,   0,   0,  23,
     84,  85,  86,  87,  88,  89,  90,  91,  92,  93,  94,  95,  96,  97,  98,  99,
    100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111,  11,  15,  23,  31,
     80,  89,  98, 107,  31,  40,  80,  85,  89,  94,  98,  31,  40,  80,  85,  89,
     94, 103, 107,  40,  23,  23,  23,  25,  25,  25,  25,  31,  40,  40,  40,  40,
     40,  60,  80,  80,  80,  80,  85,  87,  89,  89,  89,  89,  80,  15,  15,  18,
     19,   0,   0,   0,   0,   0,   2,  11,  86,  87,  88,  89,  90,  91,  92,  93,
     23,  31,  40,  80,   0,  84,   0,   0,   0,   0,  93,   0,   0,  23,  25,  40,
     50,  85,   0,   0,  23,  25,  27,  40,  50,  85,  94, 103,  29,  31,  40,  50,
     25,  27,  29,  29,  31,  40,  50,  85,   0,   0,  23,  40,  50,  85,  25,  27,
     40,  50,  85,  94,   0,  23,  80,   0,   0,  23,  40,  50,  29,  40,  50,  85,
     39,  40,  50,  60,  70,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,
     91,  92,  93,  15,  11,  12,  18,   0,  50,  60,  70,  80,  81,  82,  83,  84,
     85,  94,   2,  23,  94,   0,   0,   0,  82,  83,  84,   0,  35,  37,  39,  29,
     39,  23,  25,  27,  37,  39,  23,  25,  27,  29,  31,  25,  27,  27,  29,  31,
     23,  25,  27,  27,  29,  31, 113, 114,  29,  31,  27,  27,  29,  29,  29,  29,
     33,  35,  35,  35,  37,  37,  39,  39,  39,  39,  25,  27,  29,  31,  33,  23,
     31,  31,  25,  27,  23,  25,  12,  18,  21,  12,  18,   6,  11,   8,  11,  11,
     15,  12,  18,  70,  80,  29,  31,  33,  35,  37,  39,   0,  37,  39,   0,  40,
     85, 103, 115, 116, 117, 118,   0,   0,  83,  84,   0,   0,  37,  39,   2,  23,
      2,   2,  23,  25,  29,   0,   0,   0,   0,   0,   0,  60,   0,  29,   0,   0,
     39,   0,   0,   0,
};

/* Numeric_Value: 3108 bytes. */

RE_UINT32 re_get_numeric_value(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_numeric_value_stage_1[f] << 4;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_numeric_value_stage_2[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_numeric_value_stage_3[pos + f] << 3;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_numeric_value_stage_4[pos + f] << 2;
    value = re_numeric_value_stage_5[pos + code];

    return value;
}

/* Bidi_Mirrored. */

static RE_UINT8 re_bidi_mirrored_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_bidi_mirrored_stage_2[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 6, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
};

static RE_UINT8 re_bidi_mirrored_stage_3[] = {
     0,  1,  1,  1,  1,  1,  1,  2,  1,  1,  1,  3,  1,  1,  1,  1,
     4,  5,  1,  6,  7,  8,  1,  9, 10,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 11,
     1,  1,  1, 12,  1,  1,  1,  1,
};

static RE_UINT8 re_bidi_mirrored_stage_4[] = {
     0,  1,  2,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  4,  3,  3,  3,  3,  3,  5,  3,  3,  3,  3,  3,
     6,  7,  8,  3,  3,  9,  3,  3, 10, 11, 12, 13, 14,  3,  3,  3,
     3,  3,  3,  3,  3, 15,  3, 16,  3,  3,  3,  3,  3,  3, 17, 18,
    19, 20, 21, 22,  3,  3,  3,  3, 23,  3,  3,  3,  3,  3,  3,  3,
    24,  3,  3,  3,  3,  3,  3,  3,  3, 25,  3,  3, 26, 27,  3,  3,
     3,  3,  3, 28, 29, 30, 31, 32,
};

static RE_UINT8 re_bidi_mirrored_stage_5[] = {
      0,   0,   0,   0,   0,   3,   0,  80,   0,   0,   0,  40,   0,   0,   0,  40,
      0,   0,   0,   0,   0,   8,   0,   8,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  60,   0,   0,   0,  24,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   6,  96,   0,   0,   0,   0,   0,   0,  96,
      0,  96,   0,   0,   0,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,
     30,  63,  98, 188,  87, 248,  15, 250, 255,  31,  60, 128, 245, 207, 255, 255,
    255, 159,   7,   1, 204, 255, 255, 193,   0,  62, 195, 255, 255,  63, 255, 255,
      0,  15,   0,   0,   3,   6,   0,   0,   0,   0,   0,   0,   0, 255,  63,   0,
    121,  59, 120, 112, 252, 255,   0,   0, 248, 255, 255, 249, 255, 255,   0,   1,
     63, 194,  55,  31,  58,   3, 240,  51,   0, 252, 255, 223,  83, 122,  48, 112,
      0,   0, 128,   1,  48, 188,  25, 254, 255, 255, 255, 255, 207, 191, 255, 255,
    255, 255, 127,  80, 124, 112, 136,  47,  60,  54,   0,  48, 255,   3,   0,   0,
      0, 255, 243,  15,   0,   0,   0,   0,   0,   0,   0, 126,  48,   0,   0,   0,
      0,   3,   0,  80,   0,   0,   0,  40,   0,   0,   0, 168,  13,   0,   0,   0,
      0,   0,   0,   8,   0,   0,   0,   0,   0,   0,  32,   0,   0,   0,   0,   0,
      0, 128,   0,   0,   0,   0,   0,   0,   0,   2,   0,   0,   0,   0,   0,   0,
      8,   0,   0,   0,   0,   0,   0,   0,
};

/* Bidi_Mirrored: 489 bytes. */

RE_UINT32 re_get_bidi_mirrored(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_bidi_mirrored_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_bidi_mirrored_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_bidi_mirrored_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_bidi_mirrored_stage_4[pos + f] << 6;
    pos += code;
    value = (re_bidi_mirrored_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Indic_Matra_Category. */

static RE_UINT8 re_indic_matra_category_stage_1[] = {
    0, 1, 1, 1, 1, 2, 1, 1, 3, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_indic_matra_category_stage_2[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  3,  4,  5,  6,  7,
     8,  0,  0,  0,  0,  0,  0,  9,  0, 10, 11, 12, 13,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 14, 15, 16, 17,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18,  0,  0,  0,  0,  0,
    19, 20, 21, 22, 23, 24, 25,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_indic_matra_category_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  1,  2,  3,  4,  0,  0,  0,  0,  5,  6,  7,  4,  0,
     0,  0,  0,  5,  8,  0,  0,  9,  0,  0,  0,  5, 10,  0,  4,  0,
     0,  0,  0, 11, 12, 13,  4,  0,  0,  0,  0, 14, 15,  7,  0,  0,
     0,  0,  0, 16, 17, 18,  4,  0,  0,  0,  0, 11, 19, 20,  4,  0,
     0,  0,  0, 14, 21,  7,  4,  0,  0,  0,  0,  0, 22, 23,  0, 24,
     0,  0,  0, 25, 26,  0,  0,  0,  0,  0,  0, 27, 28,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 29, 30,  0,  0,  0,  0,  0,  0,  0,
     0,  0, 31, 32,  0, 33, 34, 35, 36, 37,  0,  0,  0,  0,  0,  0,
     0, 38,  0, 38,  0, 39,  0, 39,  0,  0,  0, 40, 41, 42,  0,  0,
     0,  0, 43,  0,  0,  0,  0,  0,  0,  0,  0, 44, 45,  0,  0,  0,
     0, 46,  0,  0,  0, 47, 48, 49,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 50, 51,  0,  0,  0,  0,  0, 52,  0,  0,  0, 53, 24,
     0,  0, 54, 55,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    56,  0, 57,  0,  0,  0,  0,  0,  0,  0,  0, 58, 59,  0,  0,  0,
     0,  0,  0,  0, 60, 61,  0,  0,  0,  0,  0, 62, 63,  0,  0,  0,
     0,  0, 64, 65,  0,  0,  0,  0,  0,  0,  0, 66,  0,  0, 67,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 68,  0,
    69,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 70, 71,  0,  0,  0,  0,  0,  0, 72,  0,  0,  0,  0,
     0,  0, 73, 74,  0,  0,  0,  0,  0,  0,  0, 75, 45,  0,  0,  0,
     0,  0, 76, 77,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 78,  0,
     0,  0,  0, 14, 79,  7, 24,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 80, 81,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 82, 83,  0,  0,  0,  0,
     0,  0,  0, 84,  0,  0,  0,  0,  0,  0, 85, 71,  0,  0,  0,  0,
};

static RE_UINT8 re_indic_matra_category_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  2,
     3,  4,  5,  6,  1,  7,  3,  8,  0,  0,  9,  4,  0,  0,  0,  0,
     0,  4,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  2,
     3,  4, 10, 11, 12, 13, 14,  0,  0,  0,  0, 15,  0,  0,  0,  0,
     3, 10,  0,  9, 16,  9, 17,  0,  9,  0,  0,  0,  0,  0,  0,  0,
     3,  4,  5,  9, 18, 15,  3,  0,  0,  0,  0,  0,  0,  0,  0, 19,
     3,  4, 10, 11, 20, 13, 21,  0,  0,  0,  0, 18,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  7, 17, 10,  0, 22, 12, 23, 24,  0,
     0,  0,  0,  0,  0,  0,  0,  6,  1,  7, 25,  6, 26,  6,  6,  0,
     0,  0,  9, 10,  0,  0,  0,  0, 27,  7, 25, 18, 28, 29,  6,  0,
     0,  0, 15, 25,  0,  0,  0,  0,  7,  3, 10, 22, 12, 23, 24,  0,
     0,  0,  0,  0,  0, 16,  0, 15,  7,  6, 10, 10,  2, 30, 31, 32,
     0,  7,  0,  0,  0,  0,  0,  0, 19,  7,  6,  6,  4, 10,  0,  0,
    33, 33, 34,  9,  0,  0,  0, 16, 19,  7,  6,  6,  4,  9,  0,  0,
    33, 33, 35,  0,  0,  0,  0,  0, 36, 37,  4, 38, 38,  6,  6,  0,
    37,  0, 10,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 15, 19, 17,
    39,  6,  6,  0,  0, 16,  0,  0,  0,  0,  0,  7,  4,  0,  0,  0,
     0, 25,  0, 15, 25,  0,  0,  0,  9,  6, 16,  0,  0,  0,  0,  0,
     0, 15, 40, 16,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 19,  0,
     0, 17, 10,  0,  0,  0,  0,  0,  0, 17,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 19,  6, 17,  4, 41, 42, 22, 23,  0, 19,  6,  6,  6,
     6,  9,  0,  0,  0,  0,  0,  0,  6, 43, 44, 45, 16,  0,  0,  0,
     7,  7,  2, 22,  7,  8,  7,  7, 25,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  9, 39, 19,  0,  0,  0,  0, 11,  0,  0,  0,  0,  0,
    15,  1, 19,  6, 17,  5, 43, 22, 22, 40, 16,  0,  0,  0,  0,  0,
     0,  0, 15,  6,  4, 46, 47, 22, 23, 18, 25,  0,  0,  0,  0,  0,
     0,  0, 17,  8,  6, 25,  0,  0,  0,  0,  0, 15,  6,  7, 19, 19,
     0,  0,  0,  2, 48,  7, 10,  0,  0,  0, 22,  0,  0,  0,  0,  0,
     0,  0,  0, 16,  0,  0,  0,  0,  0, 15,  3,  1,  0,  0,  0,  0,
     0,  0, 15,  7,  7,  7,  7,  7,  7,  7, 10,  0,  0,  0,  0,  0,
     0,  0,  0, 36,  4, 17,  4, 10,  0, 15,  0,  0,  0,  0,  0,  0,
     0,  0,  7,  6,  4, 22, 16,  0, 49,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  9,  6, 17, 50, 40, 10, 12,  0,  0,  0,  0,  0,
     1,  6, 51, 52, 53, 54, 34, 16,  0,  0,  0,  0,  0, 11,  5,  8,
     0, 15, 19,  7, 43, 25, 36,  0, 55,  4,  9, 56,  0,  0, 10,  0,
     0,  0,  0,  0,  6,  6,  4,  4,  4,  6,  6, 16,  0,  0,  0,  0,
     2,  3,  5,  1,  3,  0,  0,  0,  0,  0,  0,  9,  6,  4, 40, 38,
    17, 10, 16,  0,  0,  0,  0,  0,  0, 15,  8,  4,  4,  4,  6, 18,
     0,  0,  0,  0,  0,  0,  7,  3,  6, 29, 15,  9,  0,  0,  0,  0,
     2,  3,  5,  6, 16, 10,  0,  0,  1,  7, 25, 11, 12, 13, 32,  0,
     2,  3,  4,  4, 39, 57, 32, 58,  0, 10,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 15,  8,  4,  4,  0, 48, 31,  0, 36,
     7,  3,  4,  4,  5,  1, 25, 36,  0,  0,  0,  0,  0,  0,  9,  8,
};

static RE_UINT8 re_indic_matra_category_stage_5[] = {
     0,  0,  5,  1,  1,  2,  1,  6,  6,  6,  6,  5,  5,  5,  1,  1,
     2,  1,  0,  5,  6,  0,  0,  2,  2,  0,  0,  4,  4,  6,  0,  1,
     5,  0,  5,  6,  5,  8,  1,  5,  9,  0, 10,  6,  2,  2,  4,  4,
     4,  5,  1,  0,  7,  0,  8,  1,  8,  0,  8,  8,  9,  2,  4, 10,
     4,  1,  3,  3,  3,  1,  3,  0,  0,  6,  5,  7,  7,  7,  6,  2,
     2,  5,  9, 10,  4,  2,  6,  1,  1,  8,  8,  5,  6, 11,  7, 12,
     2,  9, 11,  0,  5,  2,  6,  3,  3,  5,  5,  3,  1,  3,  0, 13,
    13,  0,  5,  9,  4,  0,
};

/* Indic_Matra_Category: 1486 bytes. */

RE_UINT32 re_get_indic_matra_category(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_indic_matra_category_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_indic_matra_category_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_indic_matra_category_stage_3[pos + f] << 3;
    f = code >> 1;
    code ^= f << 1;
    pos = (RE_UINT32)re_indic_matra_category_stage_4[pos + f] << 1;
    value = re_indic_matra_category_stage_5[pos + code];

    return value;
}

/* Indic_Syllabic_Category. */

static RE_UINT8 re_indic_syllabic_category_stage_1[] = {
    0, 1, 2, 2, 2, 3, 2, 2, 4, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_indic_syllabic_category_stage_2[] = {
     0,  1,  1,  1,  1,  1,  1,  1,  1,  2,  3,  4,  5,  6,  7,  8,
     9,  1,  1,  1,  1,  1,  1, 10,  1, 11, 12, 13, 14,  1,  1,  1,
    15,  1,  1,  1,  1, 16,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 17, 18, 19, 20,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 21,  1,  1,  1,  1,  1,
    22, 23, 24, 25, 26, 27, 28,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_indic_syllabic_category_stage_3[] = {
      0,   0,   1,   2,   0,   0,   0,   0,   0,   0,   3,   0,   0,   4,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,  16,  17,  18,  11,  19,
     20,  14,  15,  21,  22,  23,  24,  25,  26,  27,  15,  28,  29,   0,  11,   0,
     13,  14,  15,  28,  30,  31,  11,  32,  33,  34,  35,  36,  37,  38,  24,   0,
     39,  40,  15,  41,  42,  43,  11,   0,  44,  40,  15,  45,  42,  46,  11,   0,
     44,  40,   7,  47,  48,  38,  11,  49,  50,  51,   7,  52,  53,  54,  24,  55,
     56,   7,  57,  58,  59,   2,   0,   0,  60,  61,  62,  63,  64,  65,   0,   0,
      0,   0,  66,  67,  68,   7,  69,  70,  71,  72,  73,  74,   0,   0,   0,   0,
      7,   7,  75,  76,  77,  78,  79,  80,  81,  82,   0,   0,   0,   0,   0,   0,
     83,  84,  85,  84,  85,  86,  83,  87,   7,   7,  88,  89,  90,  91,   2,   0,
     92,  57,  93,  94,  24,   7,  95,  96,   7,   7,  97,  98,  99,   2,   0,   0,
      7, 100,   7,   7, 101, 102, 103, 104,   2,   2,   0,   0,   0,   0,   0,   0,
    105,  85,   7, 106, 107,   2,   0,   0, 108,   7, 109, 110,   7,   7, 111, 112,
      7,   7, 113, 114, 115,   0,   0,   0,   0,   0,   0,   0,   0, 116, 117, 118,
    119, 120,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 121,   0,   0,   0,
    122,   7, 123,   0,   7, 124, 125, 126, 127, 128,   7, 129, 130,   2, 131, 132,
    133,   7, 134,   7, 135, 136,   0,   0, 137,   7,   7, 138, 139,   2, 140, 141,
    142,   7, 143, 144, 145,   2,   7, 146,   7,   7,   7, 147, 148,   0, 149, 150,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 151, 152, 153,   2,
    154, 155,   7, 156, 157,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    158,  85,   7, 159, 160, 161, 162, 163, 164,   7,   7, 165,   0,   0,   0,   0,
    166,   7, 167, 168,   0, 169,   7, 170, 171, 172,   7, 173, 174,   2, 175, 176,
    177, 178, 179, 180,   0,   0,   0,   0,   0,   0,   0, 181,   7, 182, 183,   2,
     13,  14,  15,  28,  30,  38, 184, 185,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0, 186,   7,   7, 187, 188,   2,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0, 189,   7, 190, 191, 192,   0,   0,   0,
    189,   7,   7, 193,   0,   2,   0,   0, 181,   7, 194, 195,   2,   0,   0,   0,
};

static RE_UINT8 re_indic_syllabic_category_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   1,   2,   2,   3,   0,   4,   0,   0,   0,
      0,   5,   0,   0,   6,   7,   7,   7,   7,   8,   9,   9,   9,   9,   9,   9,
      9,   9,  10,  11,  12,  12,  12,  13,  14,  15,   9,   9,  16,  17,   2,   2,
     18,   7,   9,   9,  19,  20,   7,  21,  21,   8,   9,   9,   9,   9,  22,   9,
     23,  24,  25,  11,  12,  26,  26,  27,   0,  28,   0,  29,  25,   0,   0,   0,
     19,  20,  30,  31,  22,  32,  25,  33,  34,  28,  26,  35,   0,   0,  36,  23,
      0,  17,   2,   2,  37,  38,   0,   0,  19,  20,   7,  39,  39,   8,   9,   9,
     22,  36,  25,  11,  12,  40,  40,  35,  12,  26,  26,  35,   0,  41,   0,  29,
     42,   0,   0,   0,  43,  20,  30,  18,  44,  45,  32,  22,  46,  47,  48,  24,
      9,   9,  25,  41,  34,  41,  49,  35,   0,  28,   0,   0,   6,  20,   7,  44,
     44,   8,   9,   9,   9,   9,  25,  50,  12,  49,  49,  35,   0,  51,  25,   0,
     19,  20,   7,  44,   9,  36,  25,  11,   0,  51,   0,  52,   9,   9,  48,  50,
     12,  49,  49,  53,   0,   0,  54,  55,  56,  20,   7,   7,   7,  30,  24,   9,
     29,   9,   9,  42,   9,  48,  57,  28,  12,  58,  12,  12,  41,   0,   0,   0,
     36,   9,   9,   9,   9,   9,   9,  48,  12,  12,  59,   0,  12,  40,  60,  61,
     32,  62,  23,  42,   0,   9,  36,   9,  36,  63,  24,  32,  12,  12,  40,  64,
     12,  65,  60,  66,   2,   2,   3,   9,   2,   2,   2,   2,   2,   0,   0,   0,
      9,   9,  36,   9,   9,   9,   9,  47,  15,  12,  12,  67,  68,  69,  70,  71,
     72,  72,  73,  72,  72,  72,  72,  72,  72,  72,  72,  74,  75,   7,  76,  12,
     12,  77,  78,  79,   2,   2,   3,  80,  81,  16,  82,  83,  84,  85,  86,  87,
     88,  89,   9,   9,  90,  91,  60,  92,   2,   2,  93,  94,  95,   9,   9,  22,
     10,  96,   0,   0,  95,   9,   9,   9,  10,   0,   0,   0,  97,   0,   0,   0,
     98,   7,   7,   7,   7,  41,  12,  12,  12,  67,  99, 100, 101,   0,   0, 102,
    103,   9,   9,   9,  12,  12, 104,   0, 105, 106, 107,   0, 108, 109, 109, 110,
    111, 112,   0,   0,   9,   9,   9,   0,  12,  12,  12,  12, 113, 106, 114,   0,
      9, 115,  12,   0,   9,   9,   9,  75,  95, 116, 106, 117, 118,  12,  12,  12,
     12,  86, 114,   0, 119, 120,   7,   7,   9, 121,  12,  12,  12, 122,   9,   0,
    123,   7, 124,   9, 125,  12, 126, 127,   2,   2, 128, 129,   9, 130,  12,  12,
    131,   0,   0,   0,   9, 132,  12, 113, 106, 133,   0,   0,   2,   2,   3,  36,
    134,  60,  60,  60, 114,   0,   0,   0, 135, 136,   0,   0,   0,   0,   0, 137,
    138,   4,   0,   0,   0,   0,   0,   4,  39, 139, 140,   9, 115,  12,   0,   0,
      9,   9,   9, 141, 142, 143, 144,   9, 145,   0,   0,   0, 146,   7,   7,   7,
    124,   9,   9,   9,   9, 147,  12,  12,  12, 148,   0,   0, 149, 149, 149, 149,
    150,   0,   0,   0,   2,   2, 151,   9, 141, 109, 152, 114,   9, 115,  12, 153,
    154,   0,   0,   0, 155,   7,   8,  95, 156,  12,  12, 157, 148,   0,   0,   0,
      9,  62,   9,   9,   2,   2, 151,  48,   7, 124,   9,   9,   9,   9,  88,  12,
    158, 159,   0,   0, 106, 106, 106, 160,  36,   0, 161,  87,  12,  12,  12,  91,
    162,   0,   0,   0, 124,   9, 115,  12,   0, 163,   0,   0,   9,   9,   9,  81,
    164,   9, 165, 106, 166,  12,  34, 167,  88,  51,   0, 168,   9,  36,  36,   9,
      9,   0,   0, 169,   2,   2,   0,   0, 170,  20,   7,   7,   9,   9,  12,  12,
     12, 171,   0,   0, 172, 173, 173, 173, 173, 174,   2,   2,   0,   0,   0, 175,
    176,   7,   7,   8,  12,  12, 177,   0, 176,  95,   9,   9,   9, 115,  12,  12,
    178, 179,   2,   2, 109, 180,   9,   9, 156,   0,   0,   0, 176,   7,   7,   7,
      8,   9,   9,   9, 115,  12,  12,  12, 181,   0,   0,   0, 182,   2,   2,   2,
      2, 183,   0,   0,   7,   7,   9,   9,  29,   9,   9,   9,   9,   9,   9,  12,
     12, 184,   0,   0,   7,   7, 124,   9,   9,   9,   9, 140,  12,  12, 185,   0,
     16, 186, 149, 187, 149, 187,   0,   0,  20,   7,   7,  95,  12,  12,  12, 188,
    189, 102,   0,   0,   7,   7,   7, 124,   9,   9,   9, 115,  12,  94,  12, 190,
    191,   0,   0,   0,  12,  12,  12, 192,   9,   9, 140, 193,  12, 194,   0,   0,
};

static RE_UINT8 re_indic_syllabic_category_stage_5[] = {
     0,  0,  0,  0,  0, 11,  0,  0, 29, 29, 29, 29, 29, 29,  0,  0,
    11,  0,  0,  0,  0,  0,  0, 11,  1,  1,  1,  2,  8,  8,  8,  8,
     8, 12, 12, 12, 12, 12, 12, 12, 12, 12,  9,  9,  4,  3,  9,  9,
     9,  9,  9,  9,  9,  5,  9,  9,  0, 22, 22,  0,  0,  9,  9,  9,
     8,  8,  9,  9,  0,  0, 29, 29,  0,  0,  8,  8,  0,  1,  1,  2,
     0,  8,  8,  8,  8,  0,  0,  8, 12,  0, 12, 12, 12,  0, 12,  0,
     0,  0, 12, 12, 12, 12,  0,  0,  9,  0,  0,  9,  9,  5, 13,  0,
     0,  0,  0,  9, 12, 12,  0, 12,  8,  8,  8,  0,  0,  0,  0,  8,
     0, 12, 12,  0,  4,  0,  9,  9,  9,  9,  9,  0,  9,  5,  0,  0,
     0, 12, 12, 12,  1, 23, 11, 11,  0, 17,  0,  0,  8,  8,  0,  8,
     9,  9,  0,  9,  0,  0,  9,  9,  0, 12,  0,  0,  0,  0,  1, 20,
     8,  0,  8,  8,  8, 12,  0,  0,  0,  0,  0, 12, 12,  0,  0,  0,
    12, 12, 12,  0,  9,  0,  9,  9,  0,  3,  9,  9,  0,  9,  9,  0,
     0,  0, 12,  0,  9,  5, 14,  0,  0,  0, 13, 13, 13, 13, 13, 13,
     0,  0,  1,  2,  0,  0,  5,  0,  9,  0,  9,  0,  9,  9,  6,  0,
    22, 22, 22, 22,  0,  1,  6,  0, 12,  0,  0, 12,  0, 12,  0, 12,
    17, 17,  0,  0,  9,  0,  0,  0,  0,  1,  0,  0,  9,  9,  1,  2,
     9,  9,  1,  1,  6,  3,  0,  0, 19, 19, 19, 19, 19, 16, 16, 16,
    16, 16, 16, 16,  0, 16, 16, 16, 16,  0,  0,  0, 12,  8,  8,  8,
     8,  8,  8,  9,  9,  9,  1, 22,  2,  7,  6, 17, 17, 17, 17, 12,
     0,  0, 11,  0, 12, 12,  8,  8,  9,  9, 12, 12, 12, 12, 17, 17,
    17, 12,  9, 22, 22, 12, 12,  9,  9, 22, 22, 22, 22, 22, 12, 12,
    12,  9,  9,  9,  9, 12, 12, 12, 12, 12, 17,  9,  9,  9,  9, 22,
    22, 22, 12, 22, 29, 29, 22, 22,  9,  9,  0,  0,  8,  8,  8, 12,
     6,  0,  0,  0, 12,  0,  9,  9, 12, 12, 12,  8,  9, 25, 25, 25,
    15,  0,  0,  0,  0,  6,  7,  0,  3,  0,  0,  0, 11, 12, 12, 12,
     9, 16, 16, 16, 18, 18,  1, 18, 18, 18, 18, 18, 18,  0,  0,  0,
    12, 12, 12, 10, 10, 10, 10, 10, 10, 10,  0,  0, 21, 21, 21, 21,
    21,  0,  0,  0,  9, 18, 18, 18, 22, 22,  0,  0, 12, 12, 12,  9,
    12, 17, 17, 18, 18, 18, 18,  0,  7,  9,  9,  9,  1,  1,  1, 15,
     2,  8,  8,  8,  4,  9,  9,  9,  5, 12, 12, 12,  1, 15,  2,  8,
     8,  8, 12, 12, 12, 16, 16, 16,  9,  9,  6,  7, 16, 16, 12, 12,
    29, 29,  3, 12, 12, 12, 18, 18,  8,  8,  4,  9, 18, 18,  6,  6,
    16, 16,  9,  9,  1,  1,  0,  4, 22, 22, 22,  0,  0,  0,  2,  2,
    22,  0,  0,  0, 26, 27,  0,  0,  0,  0, 11, 11,  8,  8,  6, 12,
    12, 12, 12,  1, 12, 12, 10, 10, 10, 10, 12, 12, 12, 12, 10, 16,
    16, 12, 12, 12, 12, 16, 12,  1,  1,  2,  8,  8, 18,  9,  9,  9,
     5,  0,  0,  0, 24, 24, 24, 24, 24, 24,  0,  0, 29, 29, 12, 12,
    10, 10, 10, 22,  9,  9,  9, 18, 18, 18, 18,  6,  1,  1, 15,  2,
    12, 12, 12,  4,  9, 16, 17, 17,  9,  9,  9, 17, 17, 17, 17,  0,
    18, 18,  0,  0,  0,  0, 12, 22, 21, 22, 21,  0,  0,  2,  7,  0,
    12,  8, 12, 12, 12, 12, 12, 18, 18, 18, 18,  9, 22,  6,  0,  0,
     9,  0,  1,  2,  0,  0,  0,  7,  1,  1,  2,  0,  9,  9,  5,  0,
     0,  0, 30, 30, 30, 30, 30, 30, 30, 30, 29, 29,  0,  0,  0, 28,
     1,  1,  2,  8,  9,  5,  4,  0,  9,  9,  9,  7,  6,  0, 29, 29,
    10, 12, 12, 12,  5,  3,  0,  0,  0, 29, 29, 29, 29,  0,  0,  0,
     1,  5,  4, 23,  9,  4,  6,  0,  0,  0, 24, 24, 24,  0,  0,  0,
     9,  9,  9,  1,  1,  2,  5,  4,  1,  1,  2,  5,  4,  0,  0,  0,
     9,  1,  2,  5,  2,  9,  9,  9,  9,  9,  5,  4,
};

/* Indic_Syllabic_Category: 2324 bytes. */

RE_UINT32 re_get_indic_syllabic_category(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_indic_syllabic_category_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_indic_syllabic_category_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_indic_syllabic_category_stage_3[pos + f] << 2;
    f = code >> 2;
    code ^= f << 2;
    pos = (RE_UINT32)re_indic_syllabic_category_stage_4[pos + f] << 2;
    value = re_indic_syllabic_category_stage_5[pos + code];

    return value;
}

/* Alphanumeric. */

static RE_UINT8 re_alphanumeric_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3,
};

static RE_UINT8 re_alphanumeric_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 26, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 27,  7, 28, 29, 13, 13, 13, 13, 13, 13, 13, 30,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_alphanumeric_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 32, 31, 31, 31, 31, 31, 31, 31, 33, 34, 35, 31,
    36, 37, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 38,  1,  1,  1,  1,  1,  1,  1,  1,  1, 39,
     1,  1,  1,  1, 40,  1, 41, 42, 43, 44, 45, 46,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 47, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 48, 49,  1, 50, 51, 52, 53, 54, 55, 56, 57, 58,  1, 59,
    60, 61, 62, 63, 64, 31, 31, 31, 65, 66, 67, 68, 69, 70, 71, 31,
    72, 31, 73, 31, 31, 31, 31, 31,  1,  1,  1, 74, 75, 31, 31, 31,
     1,  1,  1,  1, 76, 31, 31, 31,  1,  1, 77, 78, 31, 31, 31, 79,
    80, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 81, 31, 31, 31,
    31, 31, 31, 31, 82, 83, 84, 85, 86, 31, 31, 31, 31, 31, 87, 31,
    31, 88, 31, 31, 31, 31, 31, 31,  1,  1,  1,  1,  1,  1, 89,  1,
     1,  1,  1,  1,  1,  1,  1, 90, 91, 31, 31, 31, 31, 31, 31, 31,
     1,  1, 91, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_alphanumeric_stage_4[] = {
      0,   1,   2,   2,   0,   3,   4,   4,   5,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5,   5,   6,   7,   0,   0,   8,   9,  10,  11,   5,  12,
      5,   5,   5,   5,  13,   5,   5,   5,   5,  14,  15,  16,  17,  18,  19,  20,
     21,   5,  22,  23,   5,   5,  24,  25,  26,   5,  27,   5,   5,  28,   5,  29,
     30,  31,  32,   0,   0,  33,   0,  34,   5,  35,  36,  37,  38,  39,  40,  41,
     42,  43,  44,  45,  46,  47,  48,  49,  50,  47,  51,  52,  53,  54,  55,  56,
     57,  58,  59,  49,  60,  61,  62,  63,  60,  64,  65,  66,  67,  68,  69,  70,
     16,  71,  72,   0,  73,  74,  75,   0,  76,  77,  78,  79,  80,  81,   0,   0,
      5,  82,  83,  84,  85,   5,  86,  87,   5,   5,  88,   5,  89,  90,  91,   5,
     92,   5,  93,   0,  94,   5,   5,  95,  16,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,  96,   2,   5,   5,  97,  98,  99,  99, 100,   5, 101, 102,  77,
      1,   5,   5, 103,   5, 104,   5, 105, 106, 107, 108, 109,   5, 110, 111,   0,
    112,   5, 106, 113, 111, 114,   0,   0,   5, 115, 116,   0,   5, 117,   5, 118,
      5, 105, 119, 120,   0,   0,   0, 121,   5,   5,   5,   5,   5,   5,   0, 122,
    123,   5, 124, 120,   5, 125, 126, 127,   0,   0,   0, 128, 129,   0,   0,   0,
    130, 131, 132,   5, 133,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 134,   5,  77,   5, 135, 106,   5,   5,   5,   5, 136,
      5,  86,   5, 137, 138, 139, 139,   5,   0, 140,   0,   0,   0,   0,   0,   0,
    141, 142,  16,   5, 143,  16,   5,  87, 144, 145,   5,   5, 146,  71,   0,  26,
      5,   5,   5,   5,   5, 105,   0,   0,   5,   5,   5,   5,   5,   5,  31,   0,
      5,   5,   5,   5,  31,   0,  26, 120, 147, 148,   5, 149, 150,   5,   5,  94,
    151, 152,   5,   5, 153, 154,   0, 151, 155,  17,   5,  99,   5,   5, 156, 157,
      5, 104,  33,  81,   5, 158, 159, 160,   5, 138, 161, 162,   5, 106, 163, 164,
    165, 166,  87, 167,   0,   0,   5, 168,   5,   5,   5,   5,   5, 169, 170, 112,
      5,   5,   5, 171,   5,   5, 172,   0, 173, 174, 175,   5,   5,  28, 176,   5,
      5, 120,  26,   5, 177,   5,  17, 178,   0,   0,   0, 179,   5,   5,   5,  81,
      1,   2,   2, 108,   5, 106, 180,   0, 181, 182, 183,   0,   5,   5,   5,  71,
      0,   0,   5,  95,   0,   0,   0,   0,   0,   0,   0,   0,  81,   5, 184,   0,
      5,  26, 104,  71, 120,   5, 185,   0,   5,   5,   5,   5, 120,  77,   0,   0,
      5, 186,   5, 187,   0,   0,   0,   0,   5, 138, 105,  17,   0,   0,   0,   0,
    188, 189, 105, 138, 106,   0,   0,   0, 105, 172,   0,   0,   5, 190,   0,   0,
    191,  99,   0,  81,  81,   0,  78, 192,   5, 105, 105,  33,  28,   0,   0,   0,
      5,   5, 133,   0,   0,   0,   0,   0,   5,   5, 193,  56, 152,  32,  26, 194,
      5, 195,  26, 196,   5,   5, 197,   0, 198, 199,   0,   0,   0,  26,   5, 194,
     50,  47, 200, 187,   0,   0,   0,   0,   0,   0,   0,   0,   5,   5, 201,   0,
      0,   0,   0,   0,   5, 202,   0,   0,   5, 106, 203,   0,   5, 105,  77,   0,
      0,   0,   0,   0,   0,   5,   5, 204,   0,   0,   0,   0,   0,   0,   5,  32,
      5,   5,   5,   5,  32,   0,   0,   0,   5,   5,   5, 146,   0,   0,   0,   0,
      5, 146,   0,   0,   0,   0,   0,   0,   5,  32, 106,  77,   0,   0,  26, 205,
      5, 138, 156, 206,  94,   0,   0,   0,   5,   5, 207, 106, 176,   0,   0,   0,
    208,   0,   0,   0,   0,   0,   0,   0,   5,   5,   5, 209, 210,   0,   0,   0,
      5,   5, 211,   5, 212, 213, 214,   5, 215, 216, 217,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5, 218, 219,  87, 211, 211, 135, 135, 220, 220, 221,   5,
      5,   5,   5,   5,   5,   5, 192,   0, 214, 222, 223, 224, 225, 226,   0,   0,
      0,  26,  83,  83,  77,   0,   0,   0,   5,   5,   5,   5,   5,   5, 138,   0,
      5,  95,   5,   5,   5,   5,   5,   5, 120,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_alphanumeric_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255,   7,   0,   4,  32,   4,
    255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,
     32,   0,   0,   0,   0,   0, 223, 188,  64, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255,   3, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2,
    254, 255, 255, 255, 255,   0,   0,   0,   0,   0, 255, 191, 182,   0, 255, 255,
    255,   7,   7,   0,   0,   0, 255,   7, 255, 255, 255, 254, 255, 195, 255, 255,
    255, 255, 239,  31, 254, 225, 255, 159,   0,   0, 255, 255,   0, 224, 255, 255,
    255, 255,   3,   0, 255,   7,  48,   4, 255, 255, 255, 252, 255,  31,   0,   0,
    255, 255, 255,   1, 255, 255,   7,   0, 240,   3, 255, 255, 255, 255, 255, 239,
    255, 223, 225, 255, 207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 227,
    159,  89, 128, 176, 207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 195,
    135,  25,   2,  94, 192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 227,
    191,  27,   1,   0, 207, 255,   0,   0, 238, 159, 249, 255, 159,  25, 192, 176,
    207, 255,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195, 199,  29, 129,   0,
    192, 255,   0,   0, 239, 223, 253, 255, 255, 253, 255, 227, 223,  29,  96,   3,
    238, 223, 253, 255, 255, 253, 239, 227, 223,  29,  96,  64, 207, 255,   6,   0,
    255, 255, 255, 231, 223,  93, 128,   0, 207, 255,   0, 252, 236, 255, 127, 252,
    255, 255, 251,  47, 127, 128,  95, 255, 192, 255,  12,   0, 255, 255, 255,   7,
    127,  32, 255,   3, 150,  37, 240, 254, 174, 236, 255,  59,  95,  32, 255, 243,
      1,   0,   0,   0, 255,   3,   0,   0, 255, 254, 255, 255, 255,  31, 254, 255,
      3, 255, 255, 254, 255, 255, 255,  31, 255, 255, 127, 249, 255,   3, 255, 255,
    231, 193, 255, 255, 127,  64, 255,  51, 191,  32, 255, 255, 255, 255, 255, 247,
    255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255,
    255, 255,  61, 255, 255, 255, 255, 135, 255, 255,   0,   0, 255, 255,  31,   0,
    255, 159, 255, 255, 255, 199, 255,   1, 255, 223,  15,   0, 255, 255,  15,   0,
    255, 223,  13,   0, 255, 255, 207, 255, 255,   1, 128,  16, 255, 255, 255,   0,
    255,   7, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  15, 255,   1,
    192, 255, 255, 255, 255,  63,  31,   0, 255,  15, 255, 255, 255,   3, 255,   3,
    255, 255, 255,  15, 254, 255,  31,   0, 128,   0,   0,   0, 255, 255, 239, 255,
    239,  15, 255,   3, 255, 243, 255, 255, 191, 255,   3,   0, 255, 227, 255, 255,
    255, 255, 255,  63,   0, 222, 111,   0, 128, 255,  31,   0, 255, 255,  63,  63,
     63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   2, 128,   0,   0, 255,  31, 132, 252,  47,  62,  80, 189, 255, 243,
    224,  67,   0,   0, 255,   1,   0,   0,   0,   0, 192, 255, 255, 127, 255, 255,
     31, 120,  12,   0, 255, 128,   0,   0, 255, 255, 127,   0, 127, 127, 127, 127,
      0, 128,   0,   0, 224,   0,   0,   0, 254,   3,  62,  31, 255, 255, 127, 224,
    224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31, 255, 255,
    255,  15,   0,   0, 255, 127, 240, 143, 255, 255, 255, 191,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 121, 255, 255, 255,  63,   3,   0, 187, 247, 255, 255,
     15,   0, 255,   3,   0,   0, 252,   8, 255, 255, 247, 255,   0, 128, 255,   3,
    223, 255, 255, 127, 255,  63, 255,   3, 255, 255, 127, 196,   5,   0,   0,  56,
    255, 255,  60,   0, 126, 126, 126,   0, 127, 127, 255, 255,  48,   0,   0,   0,
    255,   7, 255,   3,  15,   0, 255, 255, 127, 248, 255, 255, 255,  63, 255, 255,
    255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95, 219, 255, 255, 255,
      0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,   0,   0, 223, 255,
    252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,
    255, 255,   1,   0,  15, 255,  62,   0, 255,   0, 255, 255,  15,   0,   0,   0,
     63, 253, 255, 255, 255, 255, 191, 145, 255, 255, 255, 192, 111, 240, 239, 254,
     31,   0,   0,   0,  63,   0,   0,   0, 255,   1, 255,   3, 255, 255, 199, 255,
    255, 255,  71,   0,  30,   0, 255,   7, 255, 255, 251, 255, 255, 255, 159,   0,
    159,  25, 128, 224, 179,   0, 255,   3, 255, 255,  63, 127,  17,   0, 255,   3,
    255,   3,   0, 128, 255,  63,   0,   0, 248, 255, 255, 224,  31,   0, 255, 255,
      3,   0,   0,   0, 255,   7, 255,  31, 255,   1, 255,  67, 255, 255, 223, 255,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    255, 253, 255, 255, 247, 207, 255, 255, 150, 254, 247,  10, 132, 234, 150, 170,
    150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
};

/* Alphanumeric: 2037 bytes. */

RE_UINT32 re_get_alphanumeric(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_alphanumeric_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_alphanumeric_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_alphanumeric_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_alphanumeric_stage_4[pos + f] << 5;
    pos += code;
    value = (re_alphanumeric_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Any. */

RE_UINT32 re_get_any(RE_UINT32 ch) {
    return 1;
}

/* Blank. */

static RE_UINT8 re_blank_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_blank_stage_2[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_blank_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1,
    3, 1, 1, 1, 1, 1, 1, 1, 4, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_blank_stage_4[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 3, 1, 1, 1, 1, 1, 4, 5, 1, 1, 1, 1, 1, 1,
    3, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_blank_stage_5[] = {
      0,   2,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   1,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   0,
    255,   7,   0,   0,   0, 128,   0,   0,   0,   0,   0, 128,   0,   0,   0,   0,
};

/* Blank: 169 bytes. */

RE_UINT32 re_get_blank(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_blank_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_blank_stage_2[pos + f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_blank_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_blank_stage_4[pos + f] << 6;
    pos += code;
    value = (re_blank_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Graph. */

static RE_UINT8 re_graph_stage_1[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 10, 12, 13, 14,
     3,  3,  3,  3,  3, 15, 10, 16, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    17, 10, 10, 10, 10, 10, 10, 10,  3,  3,  3,  3,  3,  3,  3, 18,
     3,  3,  3,  3,  3,  3,  3, 18,
};

static RE_UINT8 re_graph_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 10, 10, 19, 20, 21, 22, 23, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 24, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 25,
    10, 10, 26, 27, 28, 29, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 30, 31, 31, 31, 31,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 32, 33, 34,
    35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 31, 31,
    10, 49, 50, 31, 31, 31, 31, 31, 10, 10, 51, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 10, 52, 31, 53, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 54, 31, 31, 31, 31, 31, 55, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 56, 57, 58, 59, 31, 31, 31, 31,
    31, 31, 31, 31, 60, 31, 31, 61, 62, 63, 64, 65, 66, 31, 31, 31,
    10, 10, 10, 67, 10, 10, 10, 10, 10, 10, 10, 68, 69, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 10, 69, 31, 31,
    70, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 71,
};

static RE_UINT8 re_graph_stage_3[] = {
      0,   1,   0,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   3,   4,   2,
      2,   2,   2,   2,   5,   6,   7,   8,   9,   2,   2,   2,  10,  11,  12,  13,
     14,  15,  16,  17,   2,   2,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,   2,  40,  41,  42,
      2,   2,   2,  43,   2,   2,   2,   2,   2,  44,  45,  46,  47,  48,  49,  50,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  51,  52,  53,  54,   2,  55,
     56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,   2,  68,   2,  69,
     70,  71,  67,  72,   2,   2,   2,  73,   2,   2,   2,   2,  74,  75,  76,  77,
     78,  79,  80,  81,   2,   2,  82,   2,   2,   2,   2,   2,   2,   2,   2,  13,
     83,  84,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  85,  86,  87,
     88,  89,   2,  90,  91,  92,  93,  94,   2,  95,  96,  97,   2,   2,   2,  98,
     99,  99, 100,   2, 101,   2, 102, 103,  89,   2,   2,   1,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,  59,   2,   2,   2,   2,   2,   2,   2,   2, 104,
      2,   2, 105, 106,   2,   2,   2,   2, 107,   2, 108,  57,   2,   2, 109, 110,
    111,  57,   2, 112,   2, 113,   2, 114, 115, 116,   2, 117, 118, 119,  67, 120,
      2,   2,   2,   2,   2,   2, 103, 121,  67,  67,  67,  67,  67,  67,  67,  67,
      2, 122,   2, 123, 124, 125,   2, 126,   2,   2,   2,   2,   2, 127, 128, 129,
    130, 131,   2, 132,  99,   2,   1, 133, 134, 135,   2,  13, 136,   2, 137, 138,
     67,  67, 139, 140, 103, 141, 108, 142,   2,   2, 143,  67, 144, 145,  67,  67,
      2,   2,   2,   2, 115, 146,  67,  67, 147, 148, 149,  67, 150,  67, 151,  67,
    152, 153, 154, 155, 156, 157, 158,  67,   2, 159,  67,  67,  67,  67,  67,  67,
     67, 160,  67,  67,  67,  67,  67,  67,   2, 161,   2, 162,  76, 163,   2, 164,
    165,  67, 166, 167,  24, 168,  67,  67,  67,  67,   2, 169,  67,  67, 170, 171,
      2, 172,  57, 171,  67,  67,  67,  67,  67,  67, 173, 174,  67,  67,  67,  67,
     67,  67,  67,  52,  67,  67,  67,  67,   2,   2,   2,   2,   2,   2, 175,  67,
      2, 176,  67,  67,  67,  67,  67,  67, 177,  67,  67,  67,  67,  67,  67,  67,
     52, 178,  67, 179,   2, 180, 181,  67,  67,  67,  67,  67,   2, 182, 183,  67,
    184,  67,  67,  67,  67,  67,  67,  67,   2, 185, 186,  67,  67,  67,  67,  67,
      2,   2,   2,  59, 187,   2,   2, 188,   2, 189,  67,  67,   2, 190,  67,  67,
      2, 191, 192, 193, 194, 195,   2,   2,   2,   2, 196,   2,   2,   2,   2, 197,
      2,   2,   2, 198,  67,  67,  67,  67, 199, 200, 201, 202,  67,  67,  67,  67,
     62,   2, 203, 204, 205,  62, 206, 207, 208, 209,  67,  67, 210, 211,   2, 212,
      2,   2,   2,   1,   2, 213, 214,   2,   2, 215,   2, 216,   2,  97,   2, 217,
    218, 219, 220,  67,  67,  67,  67,  67,   2,   2,   2, 221,   2,   2,   2,   2,
      2,   2,   2,   2,  50,   2,   2,   2, 188,  67,  67,  67,  67,  67,  67,  67,
    222,   2,  67,  67,   2,   2,   2, 223,   2,   2,   2,   2,   2,   2,   2, 211,
};

static RE_UINT8 re_graph_stage_4[] = {
      0,   0,   1,   2,   2,   2,   2,   3,   2,   2,   2,   2,   2,   2,   2,   4,
      5,   2,   6,   2,   2,   2,   2,   1,   2,   7,   1,   2,   8,   1,   2,   2,
      9,   2,  10,  11,   2,  12,   2,   2,  13,   2,   2,   2,  14,   2,   2,   2,
      2,   2,   2,  15,   2,   2,   2,  10,   2,   2,  16,   3,   2,  17,   0,   0,
      0,   0,   2,  18,   0,   0,  19,   2,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  21,  22,  29,  30,  31,  32,  33,  34,   6,  22,  35,  36,  37,  26,  15,
     38,  21,  22,  35,  39,  40,  26,   9,  41,  42,  43,  44,  45,  46,  32,  10,
     47,  48,  22,  49,  50,  51,  26,  52,  53,  48,  22,  54,  50,  55,  26,  56,
     53,  48,   2,  14,  57,  58,  26,  59,  60,  61,   2,  62,  63,  64,  32,  65,
      1,   2,   2,  66,   2,  27,   0,   0,  67,  68,  69,  70,  71,  72,   0,   0,
     73,   2,  74,   1,   2,  73,   2,  12,  12,  10,   0,   0,  75,   2,   2,   2,
     76,  77,   2,   2,  76,   2,   2,  78,  79,  80,   2,   2,   2,  79,   2,   2,
      2,  14,   2,  74,   2,  81,   2,   2,   2,   2,   2,  11,   1,  74,   2,   2,
      2,   2,   2,  82,  12,  11,   2,  83,   2,  84,  12,  85,   2,  16,  81,  81,
      3,  81,   2,   2,   2,   2,   2,   9,   2,   2,  10,   2,   2,   2,   2,  33,
      2,   3,  27,  27,  86,   2,  16,  11,   2,   2,  27,   2,  81,  87,   2,   2,
      2,  88,   2,   2,   2,   3,   2,  89,  81,  81,  16,   3,   0,   0,   0,   0,
     27,   2,   2,  74,   2,   2,   2,  90,   2,   2,   2,  91,  49,   2,   2,   2,
      9,   2,   2,  92,   2,   2,   2,  93,   2,  94,   2,   2,  94,  95,   2,  16,
      2,   2,   2,  96,  96,  97,   2,  98,  99,   2, 100,   2,   2,   3,  96, 101,
      3,  74,   2,  16,   0,   2,   2,  37,  81,   2,   2,   2,   2,   2,  83,   0,
     10,   0,   2,   2,   2,   2,   2,  26,   2, 102,   2,  49,  22,  15,   0,   0,
      2,   2,   3,   2,   2,   3,   2,   2,   2,   2,   2, 103,   2,   2,  75,   2,
      2,   2, 104, 105,   2,  83, 106, 106, 106, 106,   2,   2,  18,   0,   0,   0,
      2, 107,   2,   2,   2,   2,   2,  84,   2,  33,   0,  27,   1,   2,   2,   2,
      2,   7,   2,   2, 108,   2,  16,   1,   3,   2,   2,  10,   2,   2,  84,   2,
     74,   0,   0,   0,  74,   2,   2,   2,  83,   2,   2,   2,   2,   2,  27,   0,
      2,  13,   2,   2,   3,   2,  16,  15,   0,   0,   0, 109,   2,   2,  27,  81,
    110,  81,   2,  27,   2, 111,   2,  74,  13,  44,   2,   3,   2,   2,   2,  83,
     16,  72,   2,   2,  18,  99,   2,  83, 112, 113, 106,   2,   2,   2, 114,   0,
      2,   2,  16,  81, 115,   2,   2,  27,   2,   2,  16,   2,   2,  81,   0,   0,
     83, 116,   2, 117, 118,   2,   2,   2,  15, 119,   2,   2,   0,   2,   2,   2,
      2, 120,   2,   2,   9,   0,   0,  16,   2,  81,  16,   2,   2, 121, 122,  96,
      2,   2,   2,  89, 123, 124, 106, 125, 126,   2,  80, 127,  16,  16,   0,   0,
    128,   2,   2, 129,  74,  27,  37,   0,   0,   2,   2,  16,   2,  74,   2,   2,
      2,  37,   2,  27,  10,   2,   2,  10, 130,  33,   0,   0,   2,  16,  81,   0,
      2,   2,   9,   2,   2,   2, 111,   0,   2,  33,   9,   0, 131,   2,   2, 132,
      2, 133,   2,   2,   2,   3, 109,   0,   2, 134,   2, 135,   2,   2,   2, 136,
    137, 138,   2, 139,   9,  82,   2,   2,   2,   2,   0,   0,   2,   2, 115,  83,
      2,   2,   2,  59,   2, 102,   2, 140,   2, 141, 142,   0,  82,   0,   0,   0,
      0,   0,   2,   3,  16, 120,   2, 143,  15,   2,  82,  81,  84,   2,   2,  83,
    144,  10,   1,  11,   2,   6,   2,  16,   0,   0,   0,   2,   2,   2,  10,  81,
     39, 145, 146,  11,   9,  81,   0,   0,   2,   2,   2, 102,  81,   0,   0,   0,
     11,  81,   0,   0,   0,   0,   2,   2,   2,   2,   2, 147,   2,  82,   0,   0,
      2,   2,   3,  11,   2,   2,   3,   0,   2,   3,  44,   0,   0,   2,  16,  33,
     33, 107,   6, 148,   2,   0,   0,   0,  11,   2,   2,   3, 143,   2,   0,   0,
     15,   0,   0,   0,   2,   2,  10,  74,  82,  72,  84,   0,   2,   2,   7,   2,
      2,  16,   0,   0,  33,   0,   0,   0,   2,  83,   2,  15,   2,  96,   2,   2,
      2,  12, 149, 150, 151,   2,   2,   2, 152, 153,   2, 154, 155,  48,   2,   2,
      2,   2, 102,   2,  88,   2,   2,   2, 156,  83,   0,   0, 151,   2, 157, 158,
    159, 160, 161, 162, 107,  27, 163,  27,   0,   0,   0,  15,   2,  84,   3,   1,
      1,   1,   2,  33,  74,   2,   3,   2,   2,  10,   0,   0,   0,   0,  32,   2,
     18,   2,   2,  10,  82,  15,   0,   0,   2,   2,  74,   2,   2,   2,   2,  16,
      3,  19,   2,   9,  10,   2,   2, 107,   2,   2, 151,   2, 164,   2,   2,   2,
      2,   0,  74,  84,   2,  11,   0,   0,  27,   2,   2,   2,   9,  81,   2,   2,
      9,   2,  16,   0,   2,  83,   0,   0, 165,   0,   2,   2,   2,   2,   2,   0,
};

static RE_UINT8 re_graph_stage_5[] = {
      0,   0, 254, 255, 255, 255, 255, 127, 255, 252, 240, 215, 251, 255, 127, 254,
    255, 230, 255,   0, 255,   7,  31,   0, 255, 223, 255, 191, 255, 231,   3,   0,
    255,  63, 255,  79,   7,   0, 240, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255, 255,  15, 238, 135, 109, 211, 135,  57,   2,  94,
    192, 255,  63,   0, 238, 191, 237, 243, 191,  59,   1,   0, 238, 159, 159,  57,
    192, 176, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0, 239, 223,
    253, 255, 255, 227, 223,  61,  96,   3,   0, 255, 238, 223, 239, 243,  96,  64,
      6,   0, 223, 125, 128,   0,  63, 254, 236, 255, 127, 252, 251,  47, 127, 132,
     95, 255,  28,   0, 255, 135, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63,
    255, 243, 255, 254, 255,  31, 191,  32, 255,  61, 127,  61,  61, 127,  61, 255,
    127, 255, 255,   3, 255,   1, 127,   0,  15,   0,  13,   0, 241, 255, 255, 199,
    255, 207, 255, 159,  15, 240, 255, 248, 127,   3,  63, 240,  63,  63, 255, 170,
    223, 255, 207, 239, 220, 127,   0, 248, 255, 124, 243, 255,  63, 255,  15, 254,
    255, 128,   1, 128, 127, 127, 255, 251, 224, 255, 128, 255,  31, 192,  15, 128,
    126, 126, 126,   0,  48,   0, 127, 248, 248, 224, 127,  95, 219, 255, 248, 255,
    252, 255, 247, 255, 127,  15, 252, 252, 252,  28,   0,  62, 255, 239, 255, 183,
    135, 255, 143, 255,  15, 255,  63, 253, 191, 145, 191, 255, 255, 143, 255, 131,
    255, 192, 111, 240, 239, 254,  15, 135,   7, 255,   3,  30,   0, 254,   0, 128,
    255,  33, 128, 224, 207,  31,   7, 128, 255, 224, 100, 222, 255, 235, 239, 255,
    191, 231, 223, 223, 255, 123,  95, 252, 159, 255, 150, 254, 247,  10, 132, 234,
    150, 170, 150, 247, 247,  94, 238, 251, 231, 255,   2,   0,
};

/* Graph: 2244 bytes. */

RE_UINT32 re_get_graph(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_graph_stage_1[f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_graph_stage_2[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_graph_stage_3[pos + f] << 2;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_graph_stage_4[pos + f] << 4;
    pos += code;
    value = (re_graph_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Print. */

static RE_UINT8 re_print_stage_1[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 10, 12, 13, 14,
     3,  3,  3,  3,  3, 15, 10, 16, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    17, 10, 10, 10, 10, 10, 10, 10,  3,  3,  3,  3,  3,  3,  3, 18,
     3,  3,  3,  3,  3,  3,  3, 18,
};

static RE_UINT8 re_print_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 10, 10, 19, 20, 21, 22, 23, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 24, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 25,
    10, 10, 26, 27, 28, 29, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 30, 31, 31, 31, 31,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 32, 33, 34,
    35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 31, 31,
    10, 49, 50, 31, 31, 31, 31, 31, 10, 10, 51, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 10, 52, 31, 53, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 54, 31, 31, 31, 31, 31, 55, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 56, 57, 58, 59, 31, 31, 31, 31,
    31, 31, 31, 31, 60, 31, 31, 61, 62, 63, 64, 65, 66, 31, 31, 31,
    10, 10, 10, 67, 10, 10, 10, 10, 10, 10, 10, 68, 69, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 10, 69, 31, 31,
    70, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 71,
};

static RE_UINT8 re_print_stage_3[] = {
      0,   1,   0,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   3,   4,   2,
      2,   2,   2,   2,   5,   6,   7,   8,   9,   2,   2,   2,  10,  11,  12,  13,
     14,  15,  16,  17,   2,   2,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,   2,  40,  41,  42,
      2,   2,   2,  43,   2,   2,   2,   2,   2,  44,  45,  46,  47,  48,  49,  50,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  51,  52,  53,  54,   2,  55,
     56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,   2,  68,   2,  69,
     70,  71,  67,  72,   2,   2,   2,  73,   2,   2,   2,   2,  74,  75,  76,  77,
     78,  79,  80,  81,   2,   2,  82,   2,   2,   2,   2,   2,   2,   2,   2,  13,
     83,  84,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  85,  86,  87,
     88,  89,   2,  90,  91,  92,  93,  94,   2,  95,  96,  97,   2,   2,   2,  98,
      2,  99, 100,   2, 101,   2, 102, 103,  89,   2,   2,   1,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,  59,   2,   2,   2,   2,   2,   2,   2,   2, 104,
      2,   2, 105, 106,   2,   2,   2,   2, 107,   2, 108,  57,   2,   2, 109, 110,
    111,  57,   2, 112,   2, 113,   2, 114, 115, 116,   2, 117, 118, 119,  67, 120,
      2,   2,   2,   2,   2,   2, 103, 121,  67,  67,  67,  67,  67,  67,  67,  67,
      2, 122,   2, 123, 124, 125,   2, 126,   2,   2,   2,   2,   2, 127, 128, 129,
    130, 131,   2, 132,  99,   2,   1, 133, 134, 135,   2,  13, 136,   2, 137, 138,
     67,  67,  51, 139, 103, 140, 108, 141,   2,   2, 142,  67, 143, 144,  67,  67,
      2,   2,   2,   2, 115, 145,  67,  67, 146, 147, 148,  67, 149,  67, 150,  67,
    151, 152, 153, 154, 155, 156, 157,  67,   2, 158,  67,  67,  67,  67,  67,  67,
     67, 159,  67,  67,  67,  67,  67,  67,   2, 160,   2, 161,  76, 162,   2, 163,
    164,  67, 165, 166,  24, 167,  67,  67,  67,  67,   2, 168,  67,  67, 169, 170,
      2, 171,  57, 170,  67,  67,  67,  67,  67,  67,   0, 172,  67,  67,  67,  67,
     67,  67,  67,  52,  67,  67,  67,  67,   2,   2,   2,   2,   2,   2, 173,  67,
      2, 174,  67,  67,  67,  67,  67,  67, 175,  67,  67,  67,  67,  67,  67,  67,
     52, 176,  67, 177,   2, 178, 179,  67,  67,  67,  67,  67,   2, 180, 181,  67,
    182,  67,  67,  67,  67,  67,  67,  67,   2, 183, 184,  67,  67,  67,  67,  67,
      2,   2,   2,  59, 185,   2,   2, 186,   2, 187,  67,  67,   2, 188,  67,  67,
      2, 189, 190, 191, 192, 193,   2,   2,   2,   2, 194,   2,   2,   2,   2, 195,
      2,   2,   2, 196,  67,  67,  67,  67, 197, 198, 199, 200,  67,  67,  67,  67,
     62,   2, 201, 202, 203,  62, 204, 205, 206, 207,  67,  67, 208, 209,   2, 210,
      2,   2,   2,   1,   2, 211, 212,   2,   2, 213,   2, 214,   2,  97,   2, 215,
    216, 217, 218,  67,  67,  67,  67,  67,   2,   2,   2, 219,   2,   2,   2,   2,
      2,   2,   2,   2,  50,   2,   2,   2, 186,  67,  67,  67,  67,  67,  67,  67,
    220,   2,  67,  67,   2,   2,   2, 221,   2,   2,   2,   2,   2,   2,   2, 209,
};

static RE_UINT8 re_print_stage_4[] = {
      0,   0,   1,   1,   1,   1,   1,   2,   1,   1,   1,   1,   1,   1,   1,   3,
      4,   1,   5,   1,   1,   1,   1,   6,   1,   7,   6,   1,   8,   6,   1,   1,
      9,   1,  10,  11,   1,  12,   1,   1,  13,   1,   1,   1,  14,   1,   1,   1,
      1,   1,   1,  15,   1,   1,   1,  10,   1,   1,  16,   2,   1,  17,   0,   0,
      0,   0,   1,  18,   0,   0,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  21,  22,  29,  30,  31,  32,  33,  34,   5,  22,  35,  36,  37,  26,  15,
     38,  21,  22,  35,  39,  40,  26,   9,  41,  42,  43,  44,  45,  46,  32,  10,
     47,  48,  22,  49,  50,  51,  26,  52,  53,  48,  22,  54,  50,  55,  26,  56,
     53,  48,   1,  14,  57,  58,  26,  59,  60,  61,   1,  62,  63,  64,  32,  65,
      6,   1,   1,  66,   1,  27,   0,   0,  67,  68,  69,  70,  71,  72,   0,   0,
     73,   1,  74,   6,   1,  73,   1,  12,  12,  10,   0,   0,  75,   1,   1,   1,
     76,  77,   1,   1,  76,   1,   1,  78,  79,  80,   1,   1,   1,  79,   1,   1,
      1,  14,   1,  74,   1,  81,   1,   1,   1,   1,   1,  11,   1,  74,   1,   1,
      1,   1,   1,  82,  12,  11,   1,  83,   1,  84,  12,  85,   1,  16,  81,  81,
      2,  81,   1,   1,   1,   1,   1,   9,   1,   1,  10,   1,   1,   1,   1,  33,
      1,   2,  27,  27,  86,   1,  16,  11,   1,   1,  27,   1,  81,  87,   1,   1,
      1,  88,   1,   1,   1,   2,   1,  89,  81,  81,  16,   2,   0,   0,   0,   0,
     27,   1,   1,  74,   1,   1,   1,  90,   1,   1,   1,  91,  49,   1,   1,   1,
      9,   1,   1,  92,   1,   1,   1,  93,   1,  94,   1,   1,  94,  95,   1,  16,
      1,   1,   1,  96,  96,  97,   1,  98,   1,   1,   3,   1,   1,   1,  96,  99,
      2,  74,   1,  16,   0,   1,   1,  37,  81,   1,   1,   1,   1,   1,  83,   0,
     10,   0,   1,   1,   1,   1,   1,  26,   1, 100,   1,  49,  22,  15,   0,   0,
      1,   1,   2,   1,   1,   2,   1,   1,   1,   1,   1, 101,   1,   1,  75,   1,
      1,   1, 102, 103,   1,  83, 104, 104, 104, 104,   1,   1,  18,   0,   0,   0,
      1, 105,   1,   1,   1,   1,   1,  84,   1,  33,   0,  27,   6,   1,   1,   1,
      1,   7,   1,   1, 106,   1,  16,   6,   2,   1,   1,  10,   1,   1,  84,   1,
     74,   0,   0,   0,  74,   1,   1,   1,  83,   1,   1,   1,   1,   1,  27,   0,
      1,  13,   1,   1,   2,   1,  16,  15,   0,   0,   0, 107,   1,   1,  27,  81,
    108,  81,   1,  27,   1, 109,   1,  74,  13,  44,   1,   2,   1,   1,   1,  83,
     16,  72,   1,   1,  18, 110,   1,  83, 111, 112, 104,   1,   1,   1, 113,   0,
      1,   1,  16,  81, 114,   1,   1,  27,   1,   1,  16,   1,   1,  81,   0,   0,
     83, 115,   1, 116, 117,   1,   1,   1,  15, 118,   1,   1,   0,   1,   1,   1,
      1, 119,   1,   1,   9,   0,   0,  16,   1,  81,  16,   1,   1, 120, 121,  96,
      1,   1,   1,  89, 122, 123, 104, 124, 125,   1,  80, 126,  16,  16,   0,   0,
    127,   1,   1, 128,  74,  27,  37,   0,   0,   1,   1,  16,   1,  37,   1,  27,
     10,   1,   1,  10, 129,  33,   0,   0,   1,  16,  81,   0,   1,   1,   9,   1,
      1,   1, 109,   0,   1,  33,   9,   0, 130,   1,   1, 131,   1, 132,   1,   1,
      1,   2, 107,   0,   1, 133,   1, 134,   1,   1,   1, 135, 136, 137,   1, 138,
      9,  82,   1,   1,   1,   1,   0,   0,   1,   1, 114,  83,   1,   1,   1,  59,
      1, 100,   1, 139,   1, 140, 141,   0,  82,   0,   0,   0,   0,   0,   1,   2,
     16, 119,   1, 142,  15,   1,  82,  81,  84,   1,   1,  83, 143,  10,   6,  11,
      1,   5,   1,  16,   0,   0,   0,   1,   1,   1,  10,  81,  39, 144, 145,  11,
      9,  81,   0,   0,   1,   1,   1, 100,  81,   0,   0,   0,  11,  81,   0,   0,
      1,   1,   1, 146,   1,  82,   0,   0,   1,   1,   2,  11,   1,   1,   2,   0,
      1,   2,  44,   0,   0,   1,  16,  33,  33, 105,   5, 147,   1,   0,   0,   0,
     11,   1,   1,   2, 142,   1,   0,   0,  15,   0,   0,   0,   1,   1,  10,  74,
     82,  72,  84,   0,   1,   1,   7,   1,   1,  16,   0,   0,  33,   0,   0,   0,
      1,  83,   1,  15,   1,  96,   1,   1,   1,  12, 148, 149, 150,   1,   1,   1,
    151, 152,   1, 153, 154,  48,   1,   1,   1,   1, 100,   1,  88,   1,   1,   1,
    155,  83,   0,   0, 150,   1, 156, 157, 158, 159, 160, 161, 105,  27, 162,  27,
      0,   0,   0,  15,   1,  84,   2,   6,   6,   6,   1,  33,  74,   1,   2,   1,
      1,  10,   0,   0,   0,   0,  32,   1,  18,   1,   1,  10,  82,  15,   0,   0,
      1,   1,  74,   1,   1,   1,   1,  16,   2,  19,   1,   9,  10,   1,   1, 105,
      1,   1, 150,   1, 163,   1,   1,   1,   1,   0,  74,  84,   1,  11,   0,   0,
     27,   1,   1,   1,   9,  81,   1,   1,   9,   1,  16,   0,   1,  83,   0,   0,
    164,   0,   1,   1,   1,   1,   1,   0,
};

static RE_UINT8 re_print_stage_5[] = {
      0,   0, 255, 255, 255, 127, 255, 252, 240, 215, 251, 255, 254, 255, 127, 254,
    255, 230, 255,   0, 255,   7,  31,   0, 255, 223, 255, 191, 255, 231,   3,   0,
    255,  63, 255,  79,   7,   0, 240, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255, 255,  15, 238, 135, 109, 211, 135,  57,   2,  94,
    192, 255,  63,   0, 238, 191, 237, 243, 191,  59,   1,   0, 238, 159, 159,  57,
    192, 176, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0, 239, 223,
    253, 255, 255, 227, 223,  61,  96,   3,   0, 255, 238, 223, 239, 243,  96,  64,
      6,   0, 223, 125, 128,   0,  63, 254, 236, 255, 127, 252, 251,  47, 127, 132,
     95, 255,  28,   0, 255, 135, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63,
    255, 243, 255, 254, 255,  31, 191,  32, 255,  61, 127,  61,  61, 127,  61, 255,
    127, 255, 255,   3, 255,   1, 127,   0,  15,   0,  13,   0, 241, 255, 255, 199,
    255, 207, 255, 159,  15, 240, 255, 248, 127,   3,  63, 240,  63,  63, 255, 170,
    223, 255, 207, 239, 220, 127, 243, 255,  63, 255,  15, 254, 255, 128,   1, 128,
    127, 127, 255, 251, 224, 255, 128, 255,  31, 192,  15, 128,   0, 248, 126, 126,
    126,   0,  48,   0, 127, 248, 248, 224, 127,  95, 219, 255, 248, 255, 252, 255,
    247, 255, 127,  15, 252, 252, 252,  28,   0,  62, 255, 239, 255, 183, 135, 255,
    143, 255,  15, 255,  63, 253, 191, 145, 191, 255, 255, 143, 255, 131, 255, 192,
    111, 240, 239, 254,  15, 135,   7, 255,   3,  30,   0, 254,   0, 128, 255,  33,
    128, 224, 207,  31,   7, 128, 255, 224, 100, 222, 255, 235, 239, 255, 191, 231,
    223, 223, 255, 123,  95, 252, 159, 255, 150, 254, 247,  10, 132, 234, 150, 170,
    150, 247, 247,  94, 238, 251, 231, 255,   2,   0,
};

/* Print: 2234 bytes. */

RE_UINT32 re_get_print(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_print_stage_1[f] << 4;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_print_stage_2[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_print_stage_3[pos + f] << 2;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_print_stage_4[pos + f] << 4;
    pos += code;
    value = (re_print_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Word. */

static RE_UINT8 re_word_stage_1[] = {
    0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6, 6,
    6, 6,
};

static RE_UINT8 re_word_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 13, 13, 13, 13, 13, 21, 13, 13,
    13, 13, 13, 13, 13, 13, 22, 23, 13, 13, 24, 13, 13, 25, 26, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 27,  7, 28, 29, 13, 13, 13, 13, 13, 13, 13, 30,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    31, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_word_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1, 17, 18, 19,  1, 20, 21, 22, 23, 24, 25, 26, 27,  1, 28,
    29, 30, 31, 31, 32, 31, 31, 31, 31, 31, 31, 31, 33, 34, 35, 31,
    36, 37, 31, 31,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 38,  1,  1,  1,  1,  1,  1,  1,  1,  1, 39,
     1,  1,  1,  1, 40,  1, 41, 42, 43, 44, 45, 46,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 47, 31, 31, 31, 31, 31, 31, 31, 31,
    31,  1, 48, 49,  1, 50, 51, 52, 53, 54, 55, 56, 57, 58,  1, 59,
    60, 61, 62, 63, 64, 31, 31, 31, 65, 66, 67, 68, 69, 70, 71, 31,
    72, 31, 73, 31, 31, 31, 31, 31,  1,  1,  1, 74, 75, 31, 31, 31,
     1,  1,  1,  1, 76, 31, 31, 31,  1,  1, 77, 78, 31, 31, 31, 79,
    80, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 81, 31, 31, 31,
    31, 82, 83, 31, 84, 85, 86, 87, 88, 31, 31, 31, 31, 31, 89, 31,
    31, 90, 31, 31, 31, 31, 31, 31,  1,  1,  1,  1,  1,  1, 91,  1,
     1,  1,  1,  1,  1,  1,  1, 92, 93, 31, 31, 31, 31, 31, 31, 31,
     1,  1, 93, 31, 31, 31, 31, 31, 31, 94, 31, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_word_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   7,   8,   6,   6,   6,   9,  10,  11,   6,  12,
      6,   6,   6,   6,  11,   6,   6,   6,   6,  13,  14,  15,  16,  17,  18,  19,
     20,   6,   6,  21,   6,   6,  22,  23,  24,   6,  25,   6,   6,  26,   6,  27,
      6,  28,  29,   0,   0,  30,   0,  31,   6,   6,   6,  32,  33,  34,  35,  36,
     37,  38,  39,  40,  41,  42,  43,  44,  45,  42,  46,  47,  48,  49,  50,  51,
     52,  53,  54,  44,  55,  56,  57,  58,  55,  59,  60,  61,  62,  63,  64,  65,
     15,  66,  67,   0,  68,  69,  70,   0,  71,  72,  73,  74,  75,  76,  77,   0,
      6,   6,  78,   6,  79,   6,  80,  81,   6,   6,  82,   6,  83,  84,  85,   6,
     86,   6,  59,   0,  87,   6,   6,  88,  15,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,  89,   3,   6,   6,  90,  91,  88,  92,  93,   6,   6,  94,  95,
     96,   6,   6,  97,   6,  98,   6,  99, 100, 101, 102, 103,   6, 104, 105,   0,
     29,   6, 100, 106, 105, 107,   0,   0,   6,   6, 108, 109,   6,   6,   6,  92,
      6,  97, 110,  79,   0,   0, 111, 112,   6,   6,   6,   6,   6,   6,   6, 113,
    114,   6, 115,  79,   6, 116, 117, 118, 119, 120, 121, 122, 123,   0,  24, 124,
    125, 126, 127,   6, 128,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 129,   6,  95,   6, 130, 100,   6,   6,   6,   6, 131,
      6,  80,   6, 132, 133, 134, 134,   6,   0, 135,   0,   0,   0,   0,   0,   0,
    136, 137,  15,   6, 138,  15,   6,  81, 139, 140,   6,   6, 141,  66,   0,  24,
      6,   6,   6,   6,   6,  99,   0,   0,   6,   6,   6,   6,   6,   6, 142,   0,
      6,   6,   6,   6, 142,   0,  24,  79, 143, 144,   6, 145,  17,   6,   6,  26,
    146, 147,   6,   6, 148, 149,   0, 146,   6, 150,   6,  92,   6,   6, 151, 152,
      6, 153,  92,  76,   6,   6, 154, 100,   6, 133, 155, 156,   6,   6, 157, 158,
    159, 160,  81, 161,   0,   0,   6, 162,   6,   6,   6,   6,   6, 163, 164,  29,
      6,   6,   6, 153,   6,   6, 165,   0, 166, 167, 168,   6,   6,  26, 169,   6,
      6,  79,  24,   6, 170,   6, 150, 171,  87, 172, 173, 174,   6,   6,   6,  76,
      1,   2,   3, 102,   6, 100, 175,   0, 176, 177, 178,   0,   6,   6,   6,  66,
      0,   0,   6,  88,   0,   0,   0, 179,   0,   0,   0,   0,  76,   6, 124, 180,
      6,  24,  98,  66,  79,   6, 181,   0,   6,   6,   6,   6,  79,  95,   0,   0,
      6, 182,   6, 183,   0,   0,   0,   0,   6, 133,  99, 150,   0,   0,   0,   0,
    184, 185,  99, 133, 100,   0,   0,   0,  99, 165,   0,   0,   6, 186,   0,   0,
    187, 188,   0,  76,  76,   0,  73, 189,   6,  99,  99,  30,  26,   0,   0,   0,
      6,   6, 128,   0,   0,   0,   0,   0,   6,   6, 189, 190,   6,  66,  24, 191,
      6, 192,  24, 193,   6,   6, 194,   0, 195,  97,   0,   0,   0,  24,   6, 196,
     45,  42, 197, 198,   0,   0,   0,   0,   0,   0,   0,   0,   6,   6, 199,   0,
      0,   0,   0,   0,   6, 200, 180,   0,   6,   6, 201,   0,   6,  97,  95,   0,
      0,   0,   0,   0,   0,   6,   6, 202,   0,   0,   0,   0,   0,   0,   6, 203,
      6,   6,   6,   6, 203,   0,   0,   0,   6,   6,   6, 141,   0,   0,   0,   0,
      6, 141,   0,   0,   0,   0,   0,   0,   6, 203, 100,  95,   0,   0,  24, 103,
      6, 133, 204, 205,  87,   0,   0,   0,   6,   6, 206, 100, 207,   0,   0,   0,
    208,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6, 209, 210,   0,   0,   0,
      0,   0,   0, 211, 212, 213,   0,   0,   0,   0, 214,   0,   0,   0,   0,   0,
      6,   6, 192,   6, 215, 216, 217,   6, 218, 219, 220,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6, 221, 222,  81, 192, 192, 130, 130, 223, 223, 224,   6,
      6,   6,   6,   6,   6,   6, 225,   0, 217, 226, 227, 228, 229, 230,   0,   0,
      0,  24,  78,  78,  95,   0,   0,   0,   6,   6,   6,   6,   6,   6, 133,   0,
      6,  88,   6,   6,   6,   6,   6,   6,  79,   0,   0,   0,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6,   6,  87,
};

static RE_UINT8 re_word_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255, 135, 254, 255, 255,   7,
      0,   4,  32,   4, 255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,
     31,  80,   0,   0, 255, 255, 223, 188,  64, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255, 255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255,
    255,   0, 254, 255, 255, 255, 255, 191, 182,   0, 255, 255, 255,   7,   7,   0,
      0,   0, 255,   7, 255, 195, 255, 255, 255, 255, 239, 159, 255, 253, 255, 159,
      0,   0, 255, 255, 255, 231, 255, 255, 255, 255,   3,   0, 255, 255,  63,   4,
    255,  63,   0,   0, 255, 255, 255,  15, 255, 255,   7,   0, 240, 255, 255, 255,
    207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 243, 159, 121, 128, 176,
    207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 211, 135,  57,   2,  94,
    192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 243, 191,  59,   1,   0,
    207, 255,   0,   0, 238, 159, 249, 255, 159,  57, 192, 176, 207, 255,   2,   0,
    236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0, 192, 255,   0,   0,
    239, 223, 253, 255, 255, 253, 255, 227, 223,  61,  96,   3, 238, 223, 253, 255,
    255, 253, 239, 243, 223,  61,  96,  64, 207, 255,   6,   0, 255, 255, 255, 231,
    223, 125, 128,   0, 207, 255,   0, 252, 236, 255, 127, 252, 255, 255, 251,  47,
    127, 132,  95, 255, 192, 255,  12,   0, 255, 255, 255,   7, 255, 127, 255,   3,
    150,  37, 240, 254, 174, 236, 255,  59,  95,  63, 255, 243,   1,   0,   0,   3,
    255,   3, 160, 194, 255, 254, 255, 255, 255,  31, 254, 255, 223, 255, 255, 254,
    255, 255, 255,  31,  64,   0,   0,   0, 255,   3, 255, 255, 255, 255, 255,  63,
    191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61, 255,  61, 255, 255,
    255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255, 255, 255,   0,   0,
    255, 255,  31,   0, 255, 159, 255, 255, 255, 199, 255,   1, 255, 223,  31,   0,
    255, 255,  15,   0, 255, 223,  13,   0, 255, 255, 143,  48, 255,   3,   0,   0,
      0,  56, 255,   3, 255, 255, 255,   0, 255,   7, 255, 255, 255, 255,  63,   0,
    255, 255, 255, 127, 255,  15, 255,  15, 192, 255, 255, 255, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3, 255,   3, 255, 255, 255, 159, 128,   0, 255, 127,
    255,  15, 255,   3,   0, 248,  15,   0, 255, 227, 255, 255,   0,   0, 247, 255,
    255, 255, 127,   3, 255, 255,  63, 240, 255, 255,  63,  63,  63,  63, 255, 170,
    255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,   0,  48,   0,   0,
      0,   0,   0, 128,   1,   0,  16,   0,   0,   0,   2, 128,   0,   0, 255,  31,
    255, 255,   1,   0, 132, 252,  47,  62,  80, 189, 255, 243, 224,  67,   0,   0,
    255,   1,   0,   0,   0,   0, 192, 255, 255, 127, 255, 255,  31, 248,  15,   0,
    255, 128,   0, 128, 255, 255, 127,   0, 127, 127, 127, 127,   0, 128,   0,   0,
    224,   0,   0,   0, 254, 255,  62,  31, 255, 255, 127, 230, 224, 255, 255, 255,
    255,  63, 254, 255, 255, 127,   0,   0, 255,  31,   0,   0, 255,  31, 255, 255,
    255,  15,   0,   0, 255, 255, 247, 191,   0,   0, 128, 255, 252, 255, 255, 255,
    255, 121, 255, 255, 255,  63,   3,   0, 255,   0,   0,   0,  31,   0, 255,   3,
    255, 255, 255,   8, 255,  63, 255, 255,   1, 128, 255,   3, 255,  63, 255,   3,
    255, 255, 127, 252,   7,   0,   0,  56, 255, 255, 124,   0, 126, 126, 126,   0,
    127, 127, 255, 255,  48,   0,   0,   0, 255,  55, 255,   3,  15,   0, 255, 255,
    127, 248, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,
    255,  63,  24,   0,   0, 224,   0,   0,   0,   0, 223, 255, 252, 252, 252,  28,
    255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,   0,   0,   0,  32,
      1,   0,   0,   0,  15, 255,  62,   0, 255,   0, 255, 255,  15,   0,   0,   0,
     63, 253, 255, 255, 255, 255, 191, 145, 255, 255, 255, 192, 111, 240, 239, 254,
    255, 255,  15, 135, 127,   0,   0,   0, 192, 255,   0, 128, 255,   1, 255,   3,
    255, 255, 223, 255, 255, 255,  79,   0,  31,   0, 255,   7, 255, 255, 251, 255,
    255,   7, 255,   3, 159,  57, 128, 224, 207,  31,  31,   0, 191,   0, 255,   3,
    255, 255,  63, 255,  17,   0, 255,   3, 255,   3,   0, 128, 255, 255, 255,   1,
     15,   0, 255,   3, 248, 255, 255, 224,  31,   0, 255, 255,   0, 128, 255, 255,
      3,   0,   0,   0, 255,   7, 255,  31, 255,   1, 255,  99, 224, 227,   7, 248,
    231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0, 255, 255, 255, 223,
    100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,
     95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247, 255, 253, 255, 255,
    247, 207, 255, 255,  31,   0, 127,   0, 150, 254, 247,  10, 132, 234, 150, 170,
    150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
};

/* Word: 2102 bytes. */

RE_UINT32 re_get_word(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_word_stage_1[f] << 4;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_word_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_word_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_word_stage_4[pos + f] << 5;
    pos += code;
    value = (re_word_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* XDigit. */

static RE_UINT8 re_xdigit_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_xdigit_stage_2[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 2, 2, 2, 4,
    5, 6, 2, 2, 2, 2, 7, 2, 2, 2, 2, 2, 2, 8, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_xdigit_stage_3[] = {
     0,  1,  1,  1,  1,  1,  2,  3,  1,  4,  4,  4,  4,  4,  5,  6,
     7,  1,  1,  1,  1,  1,  1,  8,  9, 10, 11, 12, 13,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  6,  1, 14, 15, 16, 17,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 18,
     1,  1,  1,  1, 19,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    20, 21, 17,  1, 14,  1, 22,  1,  8,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 23, 16,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 24,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_xdigit_stage_4[] = {
     0,  1,  2,  2,  2,  2,  2,  2,  2,  3,  2,  0,  2,  2,  2,  4,
     2,  5,  2,  5,  2,  6,  2,  6,  3,  2,  2,  2,  2,  4,  6,  2,
     2,  2,  2,  3,  6,  2,  2,  2,  2,  7,  2,  6,  2,  2,  8,  2,
     2,  6,  0,  2,  2,  8,  2,  2,  2,  2,  2,  6,  4,  2,  2,  9,
     2,  6,  2,  2,  2,  2,  2,  0, 10, 11,  2,  2,  2,  2,  3,  2,
     2,  5,  2,  0, 12,  2,  2,  6,  2,  6,  2,  4,  2,  3,  2,  2,
     2,  2,  2, 13,
};

static RE_UINT8 re_xdigit_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 126,   0,   0,   0, 126,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 255,   3,   0,   0,
    255,   3,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 192, 255,   0,   0,
      0,   0, 255,   3,   0,   0,   0,   0, 192, 255,   0,   0,   0,   0,   0,   0,
    255,   3, 255,   3,   0,   0,   0,   0,   0,   0, 255,   3,   0,   0, 255,   3,
      0,   0, 255,   3, 126,   0,   0,   0, 126,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 192, 255,   0, 192, 255, 255, 255, 255, 255, 255,
};

/* XDigit: 421 bytes. */

RE_UINT32 re_get_xdigit(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_xdigit_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_xdigit_stage_2[pos + f] << 4;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_xdigit_stage_3[pos + f] << 2;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_xdigit_stage_4[pos + f] << 6;
    pos += code;
    value = (re_xdigit_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* All_Cases. */

static RE_UINT8 re_all_cases_stage_1[] = {
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_all_cases_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9, 10,
     6, 11,  6,  6, 12,  6,  6,  6,  6,  6,  6,  6, 13, 14,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 15, 16,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 17,  6,  6,  6, 18,
     6,  6,  6,  6, 19,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_all_cases_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   4,   5,   6,   7,   8,
      0,   0,   0,   0,   0,   0,   9,   0,  10,  11,  12,  13,  14,  15,  16,  17,
     18,  18,  18,  18,  18,  18,  19,  20,  21,  22,  18,  18,  18,  18,  18,  23,
     24,  25,  26,  27,  28,  29,  30,  31,  32,  33,  21,  34,  18,  18,  35,  18,
     18,  18,  18,  18,  36,  18,  37,  38,  39,  18,  40,  41,  42,  43,  44,  45,
     46,  47,  48,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  49,   0,   0,   0,   0,   0,  50,  51,
     52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  62,  18,  18,  18,  63,  64,
     65,  65,  11,  11,  11,  11,  15,  15,  15,  15,  66,  66,  18,  18,  18,  18,
     67,  68,  18,  18,  18,  18,  18,  18,  69,  70,  18,  18,  18,  18,  18,  18,
     18,  18,  18,  18,  18,   0,  71,  72,  72,  72,  73,   0,  74,  75,  75,  75,
     76,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  77,  77,  77,  77,  78,  79,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  80,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  81,  18,  18,  18,
     18,  18,  82,  83,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,
     84,  85,  86,  87,  84,  85,  84,  85,  86,  87,  88,  89,  84,  85,  90,  91,
     84,  85,  84,  85,  84,  85,  92,  93,  94,  95,  96,  97,  98,  99,  94, 100,
      0,   0,   0,   0, 101, 102, 103,   0,   0, 104,   0,   0, 105, 105, 106, 106,
    107,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 108, 109, 109, 109, 110, 110, 110, 111,   0,   0,
     72,  72,  72,  72,  72,  73,  75,  75,  75,  75,  75,  76, 112, 113, 114, 115,
     18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  37, 116, 117,   0,
    118, 118, 118, 118, 119, 120,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  18,  18,  18,  18,  18,  82,   0,   0,
     18,  18,  18,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  68,  18,  68,  18,  18,  18,  18,  18,  18,  18,   0, 121,
     18, 122,  37,   0,  18, 123,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    124,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   1,  11,  11,   4,   5,  15,  15,   8,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    125, 125, 125, 125, 125, 126, 126, 126, 126, 126,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_all_cases_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,   1,
      1,   2,   1,   3,   1,   1,   1,   1,   1,   1,   1,   4,   1,   1,   1,   1,
      1,   1,   1,   0,   0,   0,   0,   0,   0,   5,   5,   5,   5,   5,   5,   5,
      5,   6,   5,   7,   5,   5,   5,   5,   5,   5,   5,   8,   5,   5,   5,   5,
      5,   5,   5,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   9,   0,   0,
      1,   1,   1,   1,   1,  10,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,   0,   1,   1,   1,   1,   1,   1,   1,  11,
      5,   5,   5,   5,   5,  12,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5,   5,   5,   0,   5,   5,   5,   5,   5,   5,   5,  13,
     14,  15,  14,  15,  14,  15,  14,  15,  16,  17,  14,  15,  14,  15,  14,  15,
      0,  14,  15,  14,  15,  14,  15,  14,  15,  14,  15,  14,  15,  14,  15,  14,
     15,   0,  14,  15,  14,  15,  14,  15,  18,  14,  15,  14,  15,  14,  15,  19,
     20,  21,  14,  15,  14,  15,  22,  14,  15,  23,  23,  14,  15,   0,  24,  25,
     26,  14,  15,  23,  27,  28,  29,  30,  14,  15,  31,   0,  29,  32,  33,  34,
     14,  15,  14,  15,  14,  15,  35,  14,  15,  35,   0,   0,  14,  15,  35,  14,
     15,  36,  36,  14,  15,  14,  15,  37,  14,  15,   0,   0,  14,  15,   0,  38,
      0,   0,   0,   0,  39,  40,  41,  39,  40,  41,  39,  40,  41,  14,  15,  14,
     15,  14,  15,  14,  15,  42,  14,  15,   0,  39,  40,  41,  14,  15,  43,  44,
     45,   0,  14,  15,  14,  15,  14,  15,  14,  15,  14,  15,   0,   0,   0,   0,
      0,   0,  46,  14,  15,  47,  48,  49,  49,  14,  15,  50,  51,  52,  14,  15,
     53,  54,  55,  56,  57,   0,  58,  58,   0,  59,   0,  60,   0,   0,   0,   0,
     58,   0,   0,  61,   0,  62,  63,   0,  64,  65,   0,  66,   0,   0,   0,  65,
      0,  67,  68,   0,   0,  69,   0,   0,   0,   0,   0,   0,   0,  70,   0,   0,
     71,   0,   0,  71,   0,   0,   0,   0,  71,  72,  73,  73,  74,   0,   0,   0,
      0,   0,  75,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  76,   0,   0,
     14,  15,  14,  15,   0,   0,  14,  15,   0,   0,   0,  33,  33,  33,   0,   0,
      0,   0,   0,   0,   0,   0,  77,   0,  78,  78,  78,   0,  79,   0,  80,  80,
     81,   1,  82,   1,   1,  83,   1,   1,  84,  85,  86,   1,  87,   1,   1,   1,
     88,  89,   0,  90,   1,   1,  91,   1,   1,  92,   1,   1,  93,  94,  94,  94,
     95,   5,  96,   5,   5,  97,   5,   5,  98,  99, 100,   5, 101,   5,   5,   5,
    102, 103, 104, 105,   5,   5, 106,   5,   5, 107,   5,   5, 108, 109, 109, 110,
    111, 112,   0,   0,   0, 113, 114, 115, 116, 117, 118,   0, 119, 120,   0,  14,
     15, 121,  14,  15,   0,  45,  45,  45, 122, 122, 122, 122, 122, 122, 122, 122,
    123, 123, 123, 123, 123, 123, 123, 123,  14,  15,   0,   0,   0,   0,   0,   0,
      0,   0,  14,  15,  14,  15,  14,  15, 124,  14,  15,  14,  15,  14,  15,  14,
     15,  14,  15,  14,  15,  14,  15, 125,   0, 126, 126, 126, 126, 126, 126, 126,
    126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126,   0,
      0, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127, 127,
    127, 127, 127, 127, 127, 127, 127,   0, 128, 128, 128, 128, 128, 128, 128, 128,
    128, 128, 128, 128, 128, 128,   0, 128,   0,   0,   0,   0,   0, 128,   0,   0,
      0, 129,   0,   0,   0, 130,   0,   0, 131, 132,  14,  15,  14,  15,  14,  15,
     14,  15,  14,  15,  14,  15,   0,   0,   0,   0,   0, 133,   0,   0, 134,   0,
    110, 110, 110, 110, 110, 110, 110, 110, 115, 115, 115, 115, 115, 115, 115, 115,
    110, 110, 110, 110, 110, 110,   0,   0, 115, 115, 115, 115, 115, 115,   0,   0,
      0, 110,   0, 110,   0, 110,   0, 110,   0, 115,   0, 115,   0, 115,   0, 115,
    135, 135, 136, 136, 136, 136, 137, 137, 138, 138, 139, 139, 140, 140,   0,   0,
    110, 110,   0, 141,   0,   0,   0,   0, 115, 115, 142, 142, 143,   0, 144,   0,
      0,   0,   0, 141,   0,   0,   0,   0, 145, 145, 145, 145, 143,   0,   0,   0,
    110, 110,   0, 146,   0,   0,   0,   0, 115, 115, 147, 147,   0,   0,   0,   0,
    110, 110,   0, 148,   0, 118,   0,   0, 115, 115, 149, 149, 121,   0,   0,   0,
    150, 150, 151, 151, 143,   0,   0,   0,   0,   0,   0,   0,   0,   0, 152,   0,
      0,   0, 153, 154,   0,   0,   0,   0,   0,   0, 155,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 156,   0, 157, 157, 157, 157, 157, 157, 157, 157,
    158, 158, 158, 158, 158, 158, 158, 158,   0,   0,   0,  14,  15,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 159, 159, 159, 159, 159, 159, 159, 159, 159, 159,
    160, 160, 160, 160, 160, 160, 160, 160, 160, 160,   0,   0,   0,   0,   0,   0,
     14,  15, 161, 162, 163, 164, 165,  14,  15,  14,  15,  14,  15, 166, 167, 168,
    169,   0,  14,  15,   0,  14,  15,   0,   0,   0,   0,   0,   0,   0, 170, 170,
      0,   0,   0,  14,  15,  14,  15,   0,   0,   0,  14,  15,   0,   0,   0,   0,
    171, 171, 171, 171, 171, 171, 171, 171, 171, 171, 171, 171, 171, 171,   0, 171,
      0,   0,   0,   0,   0, 171,   0,   0,   0,  14,  15,  14,  15, 172,  14,  15,
      0,   0,   0,  14,  15, 173,   0,   0,  14,  15, 174,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  14,  15,   0, 175, 175, 175, 175, 175, 175, 175, 175,
    176, 176, 176, 176, 176, 176, 176, 176,
};

/* All_Cases: 1984 bytes. */

static RE_AllCases re_all_cases_table[] = {
    {{     0,     0,     0}},
    {{    32,     0,     0}},
    {{    32,   232,     0}},
    {{    32,  8415,     0}},
    {{    32,   300,     0}},
    {{   -32,     0,     0}},
    {{   -32,   199,     0}},
    {{   -32,  8383,     0}},
    {{   -32,   268,     0}},
    {{   743,   775,     0}},
    {{    32,  8294,     0}},
    {{  7615,     0,     0}},
    {{   -32,  8262,     0}},
    {{   121,     0,     0}},
    {{     1,     0,     0}},
    {{    -1,     0,     0}},
    {{  -199,     0,     0}},
    {{  -232,     0,     0}},
    {{  -121,     0,     0}},
    {{  -300,  -268,     0}},
    {{   195,     0,     0}},
    {{   210,     0,     0}},
    {{   206,     0,     0}},
    {{   205,     0,     0}},
    {{    79,     0,     0}},
    {{   202,     0,     0}},
    {{   203,     0,     0}},
    {{   207,     0,     0}},
    {{    97,     0,     0}},
    {{   211,     0,     0}},
    {{   209,     0,     0}},
    {{   163,     0,     0}},
    {{   213,     0,     0}},
    {{   130,     0,     0}},
    {{   214,     0,     0}},
    {{   218,     0,     0}},
    {{   217,     0,     0}},
    {{   219,     0,     0}},
    {{    56,     0,     0}},
    {{     1,     2,     0}},
    {{    -1,     1,     0}},
    {{    -2,    -1,     0}},
    {{   -79,     0,     0}},
    {{   -97,     0,     0}},
    {{   -56,     0,     0}},
    {{  -130,     0,     0}},
    {{ 10795,     0,     0}},
    {{  -163,     0,     0}},
    {{ 10792,     0,     0}},
    {{ 10815,     0,     0}},
    {{  -195,     0,     0}},
    {{    69,     0,     0}},
    {{    71,     0,     0}},
    {{ 10783,     0,     0}},
    {{ 10780,     0,     0}},
    {{ 10782,     0,     0}},
    {{  -210,     0,     0}},
    {{  -206,     0,     0}},
    {{  -205,     0,     0}},
    {{  -202,     0,     0}},
    {{  -203,     0,     0}},
    {{  -207,     0,     0}},
    {{ 42280,     0,     0}},
    {{ 42308,     0,     0}},
    {{  -209,     0,     0}},
    {{  -211,     0,     0}},
    {{ 10743,     0,     0}},
    {{ 10749,     0,     0}},
    {{  -213,     0,     0}},
    {{  -214,     0,     0}},
    {{ 10727,     0,     0}},
    {{  -218,     0,     0}},
    {{   -69,     0,     0}},
    {{  -217,     0,     0}},
    {{   -71,     0,     0}},
    {{  -219,     0,     0}},
    {{    84,   116,  7289}},
    {{    38,     0,     0}},
    {{    37,     0,     0}},
    {{    64,     0,     0}},
    {{    63,     0,     0}},
    {{  7235,     0,     0}},
    {{    32,    62,     0}},
    {{    32,    96,     0}},
    {{    32,    57,    92}},
    {{   -84,    32,  7205}},
    {{    32,    86,     0}},
    {{  -743,    32,     0}},
    {{    32,    54,     0}},
    {{    32,    80,     0}},
    {{    31,    32,     0}},
    {{    32,    47,     0}},
    {{    32,  7549,     0}},
    {{   -38,     0,     0}},
    {{   -37,     0,     0}},
    {{  7219,     0,     0}},
    {{   -32,    30,     0}},
    {{   -32,    64,     0}},
    {{   -32,    25,    60}},
    {{  -116,   -32,  7173}},
    {{   -32,    54,     0}},
    {{  -775,   -32,     0}},
    {{   -32,    22,     0}},
    {{   -32,    48,     0}},
    {{   -31,     1,     0}},
    {{   -32,    -1,     0}},
    {{   -32,    15,     0}},
    {{   -32,  7517,     0}},
    {{   -64,     0,     0}},
    {{   -63,     0,     0}},
    {{     8,     0,     0}},
    {{   -62,   -30,     0}},
    {{   -57,   -25,    35}},
    {{   -47,   -15,     0}},
    {{   -54,   -22,     0}},
    {{    -8,     0,     0}},
    {{   -86,   -54,     0}},
    {{   -80,   -48,     0}},
    {{     7,     0,     0}},
    {{   -92,   -60,   -35}},
    {{   -96,   -64,     0}},
    {{    -7,     0,     0}},
    {{    80,     0,     0}},
    {{   -80,     0,     0}},
    {{    15,     0,     0}},
    {{   -15,     0,     0}},
    {{    48,     0,     0}},
    {{   -48,     0,     0}},
    {{  7264,     0,     0}},
    {{ 35332,     0,     0}},
    {{  3814,     0,     0}},
    {{     1,    59,     0}},
    {{    -1,    58,     0}},
    {{   -59,   -58,     0}},
    {{ -7615,     0,     0}},
    {{    74,     0,     0}},
    {{    86,     0,     0}},
    {{   100,     0,     0}},
    {{   128,     0,     0}},
    {{   112,     0,     0}},
    {{   126,     0,     0}},
    {{     9,     0,     0}},
    {{   -74,     0,     0}},
    {{    -9,     0,     0}},
    {{ -7289, -7205, -7173}},
    {{   -86,     0,     0}},
    {{ -7235,     0,     0}},
    {{  -100,     0,     0}},
    {{ -7219,     0,     0}},
    {{  -112,     0,     0}},
    {{  -128,     0,     0}},
    {{  -126,     0,     0}},
    {{ -7549, -7517,     0}},
    {{ -8415, -8383,     0}},
    {{ -8294, -8262,     0}},
    {{    28,     0,     0}},
    {{   -28,     0,     0}},
    {{    16,     0,     0}},
    {{   -16,     0,     0}},
    {{    26,     0,     0}},
    {{   -26,     0,     0}},
    {{-10743,     0,     0}},
    {{ -3814,     0,     0}},
    {{-10727,     0,     0}},
    {{-10795,     0,     0}},
    {{-10792,     0,     0}},
    {{-10780,     0,     0}},
    {{-10749,     0,     0}},
    {{-10783,     0,     0}},
    {{-10782,     0,     0}},
    {{-10815,     0,     0}},
    {{ -7264,     0,     0}},
    {{-35332,     0,     0}},
    {{-42280,     0,     0}},
    {{-42308,     0,     0}},
    {{    40,     0,     0}},
    {{   -40,     0,     0}},
};

/* All_Cases: 2124 bytes. */

int re_get_all_cases(RE_UINT32 ch, RE_UINT32* codepoints) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;
    RE_AllCases* all_cases;
    int count;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_all_cases_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_all_cases_stage_2[pos + f] << 5;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_all_cases_stage_3[pos + f] << 3;
    value = re_all_cases_stage_4[pos + code];

    all_cases = &re_all_cases_table[value];

    codepoints[0] = ch;
    count = 1;

    while (count < RE_MAX_CASES && all_cases->diffs[count - 1] != 0) {
        codepoints[count] = (RE_UINT32)((RE_INT32)ch + all_cases->diffs[count -
          1]);
        ++count;
    }

    return count;
}

/* Simple_Case_Folding. */

static RE_UINT8 re_simple_case_folding_stage_1[] = {
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_simple_case_folding_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9,
     6, 10,  6,  6, 11,  6,  6,  6,  6,  6,  6,  6, 12,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 13, 14,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 15,
     6,  6,  6,  6, 16,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_simple_case_folding_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  2,  3,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  4,  0,  2,  2,  5,  5,  0,  0,  0,  0,
     6,  6,  6,  6,  6,  6,  7,  8,  8,  7,  6,  6,  6,  6,  6,  9,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19,  8, 20,  6,  6, 21,  6,
     6,  6,  6,  6, 22,  6, 23, 24, 25,  6,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 26,  0,  0,  0,  0,  0, 27,  0,
    28, 29,  1,  2, 30, 31,  0,  0, 32, 33, 34,  6,  6,  6, 35, 36,
    37, 37,  2,  2,  2,  2,  0,  0,  0,  0,  0,  0,  6,  6,  6,  6,
    38,  7,  6,  6,  6,  6,  6,  6, 39, 40,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  0, 41, 42, 42, 42, 43,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 44, 44, 44, 44, 45, 46,  0,  0,  0,  0,  0,  0,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6, 47, 48,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     0, 49,  0, 50,  0, 49,  0, 49,  0, 50,  0, 51,  0, 49,  0,  0,
     0, 49,  0, 49,  0, 49,  0, 52,  0, 53,  0, 54,  0, 55,  0, 56,
     0,  0,  0,  0, 57, 58, 59,  0,  0,  0,  0,  0, 60, 60,  0,  0,
    61,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 62, 63, 63, 63,  0,  0,  0,  0,  0,  0,
    42, 42, 42, 42, 42, 43,  0,  0,  0,  0,  0,  0, 64, 65, 66, 67,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 23, 68, 32,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  6,  6,  6,  6,  6, 47,  0,  0,
     6,  6,  6,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  7,  6,  7,  6,  6,  6,  6,  6,  6,  6,  0, 69,
     6, 70, 23,  0,  6, 71,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  1,  2,  2,  3,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    72, 72, 72, 72, 72,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_simple_case_folding_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  2,  0,  0,  1,  1,  1,  1,  1,  1,  1,  0,
     3,  0,  3,  0,  3,  0,  3,  0,  0,  0,  3,  0,  3,  0,  3,  0,
     0,  3,  0,  3,  0,  3,  0,  3,  4,  3,  0,  3,  0,  3,  0,  5,
     0,  6,  3,  0,  3,  0,  7,  3,  0,  8,  8,  3,  0,  0,  9, 10,
    11,  3,  0,  8, 12,  0, 13, 14,  3,  0,  0,  0, 13, 15,  0, 16,
     3,  0,  3,  0,  3,  0, 17,  3,  0, 17,  0,  0,  3,  0, 17,  3,
     0, 18, 18,  3,  0,  3,  0, 19,  3,  0,  0,  0,  3,  0,  0,  0,
     0,  0,  0,  0, 20,  3,  0, 20,  3,  0, 20,  3,  0,  3,  0,  3,
     0,  3,  0,  3,  0,  0,  3,  0,  0, 20,  3,  0,  3,  0, 21, 22,
    23,  0,  3,  0,  3,  0,  3,  0,  3,  0,  3,  0,  0,  0,  0,  0,
     0,  0, 24,  3,  0, 25, 26,  0,  0,  3,  0, 27, 28, 29,  3,  0,
     0,  0,  0,  0,  0, 30,  0,  0,  3,  0,  3,  0,  0,  0,  3,  0,
     0,  0,  0,  0,  0,  0, 31,  0, 32, 32, 32,  0, 33,  0, 34, 34,
     1,  1,  0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  0,  0,  0,  0,
     0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 35,
    36, 37,  0,  0,  0, 38, 39,  0, 40, 41,  0,  0, 42, 43,  0,  3,
     0, 44,  3,  0,  0, 23, 23, 23, 45, 45, 45, 45, 45, 45, 45, 45,
     3,  0,  0,  0,  0,  0,  0,  0, 46,  3,  0,  3,  0,  3,  0,  3,
     0,  3,  0,  3,  0,  3,  0,  0,  0, 47, 47, 47, 47, 47, 47, 47,
    47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47,  0,
    48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48,  0, 48,
     0,  0,  0,  0,  0, 48,  0,  0,  3,  0,  3,  0,  3,  0,  0,  0,
     0,  0,  0, 49,  0,  0, 50,  0, 51, 51, 51, 51, 51, 51, 51, 51,
    51, 51, 51, 51, 51, 51,  0,  0,  0, 51,  0, 51,  0, 51,  0, 51,
    51, 51, 52, 52, 53,  0, 54,  0, 55, 55, 55, 55, 53,  0,  0,  0,
    51, 51, 56, 56,  0,  0,  0,  0, 51, 51, 57, 57, 44,  0,  0,  0,
    58, 58, 59, 59, 53,  0,  0,  0,  0,  0,  0,  0,  0,  0, 60,  0,
     0,  0, 61, 62,  0,  0,  0,  0,  0,  0, 63,  0,  0,  0,  0,  0,
    64, 64, 64, 64, 64, 64, 64, 64,  0,  0,  0,  3,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 65, 65, 65, 65, 65, 65, 65, 65, 65, 65,
     3,  0, 66, 67, 68,  0,  0,  3,  0,  3,  0,  3,  0, 69, 70, 71,
    72,  0,  3,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  0, 73, 73,
     0,  0,  0,  3,  0,  3,  0,  0,  0,  3,  0,  3,  0, 74,  3,  0,
     0,  0,  0,  3,  0, 75,  0,  0,  3,  0, 76,  0,  0,  0,  0,  0,
    77, 77, 77, 77, 77, 77, 77, 77,
};

/* Simple_Case_Folding: 1456 bytes. */

static RE_INT32 re_simple_case_folding_table[] = {
         0,
        32,
       775,
         1,
      -121,
      -268,
       210,
       206,
       205,
        79,
       202,
       203,
       207,
       211,
       209,
       213,
       214,
       218,
       217,
       219,
         2,
       -97,
       -56,
      -130,
     10795,
      -163,
     10792,
      -195,
        69,
        71,
       116,
        38,
        37,
        64,
        63,
         8,
       -30,
       -25,
       -15,
       -22,
       -54,
       -48,
       -60,
       -64,
        -7,
        80,
        15,
        48,
      7264,
       -58,
     -7615,
        -8,
       -74,
        -9,
     -7173,
       -86,
      -100,
      -112,
      -128,
      -126,
     -7517,
     -8383,
     -8262,
        28,
        16,
        26,
    -10743,
     -3814,
    -10727,
    -10780,
    -10749,
    -10783,
    -10782,
    -10815,
    -35332,
    -42280,
    -42308,
        40,
};

/* Simple_Case_Folding: 312 bytes. */

RE_UINT32 re_get_simple_case_folding(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;
    RE_INT32 diff;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_simple_case_folding_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_simple_case_folding_stage_2[pos + f] << 5;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_simple_case_folding_stage_3[pos + f] << 3;
    value = re_simple_case_folding_stage_4[pos + code];

    diff = re_simple_case_folding_table[value];

    return (RE_UINT32)((RE_INT32)ch + diff);
}

/* Full_Case_Folding. */

static RE_UINT8 re_full_case_folding_stage_1[] = {
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_full_case_folding_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9,
     6, 10,  6,  6, 11,  6,  6,  6,  6,  6,  6,  6, 12,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 13, 14,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 15,  6,  6,  6, 16,
     6,  6,  6,  6, 17,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_full_case_folding_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  2,  3,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  4,  0,  2,  2,  5,  6,  0,  0,  0,  0,
     7,  7,  7,  7,  7,  7,  8,  9,  9, 10,  7,  7,  7,  7,  7, 11,
    12, 13, 14, 15, 16, 17, 18, 19, 20, 21,  9, 22,  7,  7, 23,  7,
     7,  7,  7,  7, 24,  7, 25, 26, 27,  7,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 28,  0,  0,  0,  0,  0, 29,  0,
    30, 31, 32,  2, 33, 34, 35,  0, 36, 37, 38,  7,  7,  7, 39, 40,
    41, 41,  2,  2,  2,  2,  0,  0,  0,  0,  0,  0,  7,  7,  7,  7,
    42, 43,  7,  7,  7,  7,  7,  7, 44, 45,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  0, 46, 47, 47, 47, 48,  0,  0,  0,  0,  0,
    49,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 50, 50, 50, 50, 51, 52,  0,  0,  0,  0,  0,  0,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7, 53, 54,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     0, 55,  0, 56,  0, 55,  0, 55,  0, 56, 57, 58,  0, 55,  0,  0,
    59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74,
     0,  0,  0,  0, 75, 76, 77,  0,  0,  0,  0,  0, 78, 78,  0,  0,
    79,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 80, 81, 81, 81,  0,  0,  0,  0,  0,  0,
    47, 47, 47, 47, 47, 48,  0,  0,  0,  0,  0,  0, 82, 83, 84, 85,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7, 25, 86, 36,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  7,  7,  7,  7,  7, 87,  0,  0,
     7,  7,  7,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 43,  7, 43,  7,  7,  7,  7,  7,  7,  7,  0, 88,
     7, 89, 25,  0,  7, 90,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    91,  0, 92,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  1,  2,  2,  3,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    93, 93, 93, 93, 93,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_full_case_folding_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   2,   0,   0,   1,   1,   1,   1,   1,   1,   1,   0,
      1,   1,   1,   1,   1,   1,   1,   3,   4,   0,   4,   0,   4,   0,   4,   0,
      5,   0,   4,   0,   4,   0,   4,   0,   0,   4,   0,   4,   0,   4,   0,   4,
      0,   6,   4,   0,   4,   0,   4,   0,   7,   4,   0,   4,   0,   4,   0,   8,
      0,   9,   4,   0,   4,   0,  10,   4,   0,  11,  11,   4,   0,   0,  12,  13,
     14,   4,   0,  11,  15,   0,  16,  17,   4,   0,   0,   0,  16,  18,   0,  19,
      4,   0,   4,   0,   4,   0,  20,   4,   0,  20,   0,   0,   4,   0,  20,   4,
      0,  21,  21,   4,   0,   4,   0,  22,   4,   0,   0,   0,   4,   0,   0,   0,
      0,   0,   0,   0,  23,   4,   0,  23,   4,   0,  23,   4,   0,   4,   0,   4,
      0,   4,   0,   4,   0,   0,   4,   0,  24,  23,   4,   0,   4,   0,  25,  26,
     27,   0,   4,   0,   4,   0,   4,   0,   4,   0,   4,   0,   0,   0,   0,   0,
      0,   0,  28,   4,   0,  29,  30,   0,   0,   4,   0,  31,  32,  33,   4,   0,
      0,   0,   0,   0,   0,  34,   0,   0,   4,   0,   4,   0,   0,   0,   4,   0,
      0,   0,   0,   0,   0,   0,  35,   0,  36,  36,  36,   0,  37,   0,  38,  38,
     39,   1,   1,   1,   1,   1,   1,   1,   1,   1,   0,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   0,   0,   0,   0,  40,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   4,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  41,
     42,  43,   0,   0,   0,  44,  45,   0,  46,  47,   0,   0,  48,  49,   0,   4,
      0,  50,   4,   0,   0,  27,  27,  27,  51,  51,  51,  51,  51,  51,  51,  51,
      4,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4,   0,   4,   0,   4,   0,
     52,   4,   0,   4,   0,   4,   0,   4,   0,   4,   0,   4,   0,   4,   0,   0,
      0,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,
     53,  53,  53,  53,  53,  53,  53,   0,   0,   0,   0,   0,   0,   0,   0,  54,
     55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,   0,  55,
      0,   0,   0,   0,   0,  55,   0,   0,   4,   0,   4,   0,   4,   0,  56,  57,
     58,  59,  60,  61,   0,   0,  62,   0,  63,  63,  63,  63,  63,  63,  63,  63,
     63,  63,  63,  63,  63,  63,   0,   0,  64,   0,  65,   0,  66,   0,  67,   0,
      0,  63,   0,  63,   0,  63,   0,  63,  68,  68,  68,  68,  68,  68,  68,  68,
     69,  69,  69,  69,  69,  69,  69,  69,  70,  70,  70,  70,  70,  70,  70,  70,
     71,  71,  71,  71,  71,  71,  71,  71,  72,  72,  72,  72,  72,  72,  72,  72,
     73,  73,  73,  73,  73,  73,  73,  73,   0,   0,  74,  75,  76,   0,  77,  78,
     63,  63,  79,  79,  80,   0,  81,   0,   0,   0,  82,  83,  84,   0,  85,  86,
     87,  87,  87,  87,  88,   0,   0,   0,   0,   0,  89,  90,   0,   0,  91,  92,
     63,  63,  93,  93,   0,   0,   0,   0,   0,   0,  94,  95,  96,   0,  97,  98,
     63,  63,  99,  99,  50,   0,   0,   0,   0,   0, 100, 101, 102,   0, 103, 104,
    105, 105, 106, 106, 107,   0,   0,   0,   0,   0,   0,   0,   0,   0, 108,   0,
      0,   0, 109, 110,   0,   0,   0,   0,   0,   0, 111,   0,   0,   0,   0,   0,
    112, 112, 112, 112, 112, 112, 112, 112,   0,   0,   0,   4,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 113, 113, 113, 113, 113, 113, 113, 113, 113, 113,
      4,   0, 114, 115, 116,   0,   0,   4,   0,   4,   0,   4,   0, 117, 118, 119,
    120,   0,   4,   0,   0,   4,   0,   0,   0,   0,   0,   0,   0,   0, 121, 121,
      0,   0,   0,   4,   0,   4,   0,   0,   4,   0,   4,   0,   4,   0,   0,   0,
      0,   4,   0,   4,   0, 122,   4,   0,   0,   0,   0,   4,   0, 123,   0,   0,
      4,   0, 124,   0,   0,   0,   0,   0, 125, 126, 127, 128, 129, 130, 131,   0,
      0,   0,   0, 132, 133, 134, 135, 136, 137, 137, 137, 137, 137, 137, 137, 137,
};

/* Full_Case_Folding: 1656 bytes. */

static RE_FullCaseFolding re_full_case_folding_table[] = {
    {     0, {   0,   0}},
    {    32, {   0,   0}},
    {   775, {   0,   0}},
    {  -108, { 115,   0}},
    {     1, {   0,   0}},
    {  -199, { 775,   0}},
    {   371, { 110,   0}},
    {  -121, {   0,   0}},
    {  -268, {   0,   0}},
    {   210, {   0,   0}},
    {   206, {   0,   0}},
    {   205, {   0,   0}},
    {    79, {   0,   0}},
    {   202, {   0,   0}},
    {   203, {   0,   0}},
    {   207, {   0,   0}},
    {   211, {   0,   0}},
    {   209, {   0,   0}},
    {   213, {   0,   0}},
    {   214, {   0,   0}},
    {   218, {   0,   0}},
    {   217, {   0,   0}},
    {   219, {   0,   0}},
    {     2, {   0,   0}},
    {  -390, { 780,   0}},
    {   -97, {   0,   0}},
    {   -56, {   0,   0}},
    {  -130, {   0,   0}},
    { 10795, {   0,   0}},
    {  -163, {   0,   0}},
    { 10792, {   0,   0}},
    {  -195, {   0,   0}},
    {    69, {   0,   0}},
    {    71, {   0,   0}},
    {   116, {   0,   0}},
    {    38, {   0,   0}},
    {    37, {   0,   0}},
    {    64, {   0,   0}},
    {    63, {   0,   0}},
    {    41, { 776, 769}},
    {    21, { 776, 769}},
    {     8, {   0,   0}},
    {   -30, {   0,   0}},
    {   -25, {   0,   0}},
    {   -15, {   0,   0}},
    {   -22, {   0,   0}},
    {   -54, {   0,   0}},
    {   -48, {   0,   0}},
    {   -60, {   0,   0}},
    {   -64, {   0,   0}},
    {    -7, {   0,   0}},
    {    80, {   0,   0}},
    {    15, {   0,   0}},
    {    48, {   0,   0}},
    {   -34, {1410,   0}},
    {  7264, {   0,   0}},
    { -7726, { 817,   0}},
    { -7715, { 776,   0}},
    { -7713, { 778,   0}},
    { -7712, { 778,   0}},
    { -7737, { 702,   0}},
    {   -58, {   0,   0}},
    { -7723, { 115,   0}},
    {    -8, {   0,   0}},
    { -7051, { 787,   0}},
    { -7053, { 787, 768}},
    { -7055, { 787, 769}},
    { -7057, { 787, 834}},
    {  -128, { 953,   0}},
    {  -136, { 953,   0}},
    {  -112, { 953,   0}},
    {  -120, { 953,   0}},
    {   -64, { 953,   0}},
    {   -72, { 953,   0}},
    {   -66, { 953,   0}},
    { -7170, { 953,   0}},
    { -7176, { 953,   0}},
    { -7173, { 834,   0}},
    { -7174, { 834, 953}},
    {   -74, {   0,   0}},
    { -7179, { 953,   0}},
    { -7173, {   0,   0}},
    {   -78, { 953,   0}},
    { -7180, { 953,   0}},
    { -7190, { 953,   0}},
    { -7183, { 834,   0}},
    { -7184, { 834, 953}},
    {   -86, {   0,   0}},
    { -7189, { 953,   0}},
    { -7193, { 776, 768}},
    { -7194, { 776, 769}},
    { -7197, { 834,   0}},
    { -7198, { 776, 834}},
    {  -100, {   0,   0}},
    { -7197, { 776, 768}},
    { -7198, { 776, 769}},
    { -7203, { 787,   0}},
    { -7201, { 834,   0}},
    { -7202, { 776, 834}},
    {  -112, {   0,   0}},
    {  -118, { 953,   0}},
    { -7210, { 953,   0}},
    { -7206, { 953,   0}},
    { -7213, { 834,   0}},
    { -7214, { 834, 953}},
    {  -128, {   0,   0}},
    {  -126, {   0,   0}},
    { -7219, { 953,   0}},
    { -7517, {   0,   0}},
    { -8383, {   0,   0}},
    { -8262, {   0,   0}},
    {    28, {   0,   0}},
    {    16, {   0,   0}},
    {    26, {   0,   0}},
    {-10743, {   0,   0}},
    { -3814, {   0,   0}},
    {-10727, {   0,   0}},
    {-10780, {   0,   0}},
    {-10749, {   0,   0}},
    {-10783, {   0,   0}},
    {-10782, {   0,   0}},
    {-10815, {   0,   0}},
    {-35332, {   0,   0}},
    {-42280, {   0,   0}},
    {-42308, {   0,   0}},
    {-64154, { 102,   0}},
    {-64155, { 105,   0}},
    {-64156, { 108,   0}},
    {-64157, { 102, 105}},
    {-64158, { 102, 108}},
    {-64146, { 116,   0}},
    {-64147, { 116,   0}},
    {-62879, {1398,   0}},
    {-62880, {1381,   0}},
    {-62881, {1387,   0}},
    {-62872, {1398,   0}},
    {-62883, {1389,   0}},
    {    40, {   0,   0}},
};

/* Full_Case_Folding: 1104 bytes. */

int re_get_full_case_folding(RE_UINT32 ch, RE_UINT32* codepoints) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;
    RE_FullCaseFolding* case_folding;
    int count;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_full_case_folding_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_full_case_folding_stage_2[pos + f] << 5;
    f = code >> 3;
    code ^= f << 3;
    pos = (RE_UINT32)re_full_case_folding_stage_3[pos + f] << 3;
    value = re_full_case_folding_stage_4[pos + code];

    case_folding = &re_full_case_folding_table[value];

    codepoints[0] = (RE_UINT32)((RE_INT32)ch + case_folding->diff);
    count = 1;

    while (count < RE_MAX_FOLDED && case_folding->codepoints[count - 1] != 0) {
        codepoints[count] = case_folding->codepoints[count - 1];
        ++count;
    }

    return count;
}

/* Property function table. */

RE_GetPropertyFunc re_get_property[] = {
    re_get_general_category,
    re_get_block,
    re_get_script,
    re_get_word_break,
    re_get_grapheme_cluster_break,
    re_get_sentence_break,
    re_get_math,
    re_get_alphabetic,
    re_get_lowercase,
    re_get_uppercase,
    re_get_cased,
    re_get_case_ignorable,
    re_get_changes_when_lowercased,
    re_get_changes_when_uppercased,
    re_get_changes_when_titlecased,
    re_get_changes_when_casefolded,
    re_get_changes_when_casemapped,
    re_get_id_start,
    re_get_id_continue,
    re_get_xid_start,
    re_get_xid_continue,
    re_get_default_ignorable_code_point,
    re_get_grapheme_extend,
    re_get_grapheme_base,
    re_get_grapheme_link,
    re_get_white_space,
    re_get_bidi_control,
    re_get_join_control,
    re_get_dash,
    re_get_hyphen,
    re_get_quotation_mark,
    re_get_terminal_punctuation,
    re_get_other_math,
    re_get_hex_digit,
    re_get_ascii_hex_digit,
    re_get_other_alphabetic,
    re_get_ideographic,
    re_get_diacritic,
    re_get_extender,
    re_get_other_lowercase,
    re_get_other_uppercase,
    re_get_noncharacter_code_point,
    re_get_other_grapheme_extend,
    re_get_ids_binary_operator,
    re_get_ids_trinary_operator,
    re_get_radical,
    re_get_unified_ideograph,
    re_get_other_default_ignorable_code_point,
    re_get_deprecated,
    re_get_soft_dotted,
    re_get_logical_order_exception,
    re_get_other_id_start,
    re_get_other_id_continue,
    re_get_sterm,
    re_get_variation_selector,
    re_get_pattern_white_space,
    re_get_pattern_syntax,
    re_get_hangul_syllable_type,
    re_get_bidi_class,
    re_get_canonical_combining_class,
    re_get_decomposition_type,
    re_get_east_asian_width,
    re_get_joining_group,
    re_get_joining_type,
    re_get_line_break,
    re_get_numeric_type,
    re_get_numeric_value,
    re_get_bidi_mirrored,
    re_get_indic_matra_category,
    re_get_indic_syllabic_category,
    re_get_alphanumeric,
    re_get_any,
    re_get_blank,
    re_get_graph,
    re_get_print,
    re_get_word,
    re_get_xdigit,
};
