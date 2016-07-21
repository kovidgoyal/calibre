/* For Unicode version 9.0.0 */

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
    "1/12",
    "1/16",
    "1/160",
    "1/2",
    "1/20",
    "1/3",
    "1/4",
    "1/40",
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
    "11/12",
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
    "200000",
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
    "3/20",
    "3/4",
    "3/5",
    "3/8",
    "3/80",
    "30",
    "300",
    "3000",
    "30000",
    "300000",
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
    "400000",
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
    "5/12",
    "5/2",
    "5/6",
    "5/8",
    "50",
    "500",
    "5000",
    "50000",
    "500000",
    "6",
    "60",
    "600",
    "6000",
    "60000",
    "600000",
    "7",
    "7/12",
    "7/2",
    "7/8",
    "70",
    "700",
    "7000",
    "70000",
    "700000",
    "8",
    "80",
    "800",
    "8000",
    "80000",
    "800000",
    "84",
    "9",
    "9/2",
    "90",
    "900",
    "9000",
    "90000",
    "900000",
    "91",
    "A",
    "ABOVE",
    "ABOVELEFT",
    "ABOVERIGHT",
    "ADLAM",
    "ADLM",
    "AEGEANNUMBERS",
    "AFRICANFEH",
    "AFRICANNOON",
    "AFRICANQAF",
    "AGHB",
    "AHEX",
    "AHOM",
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
    "ANATOLIANHIEROGLYPHS",
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
    "BHAIKSUKI",
    "BHKS",
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
    "CHEROKEESUP",
    "CHEROKEESUPPLEMENT",
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
    "CJKEXTE",
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
    "CJKUNIFIEDIDEOGRAPHSEXTENSIONE",
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
    "CONSONANTKILLER",
    "CONSONANTMEDIAL",
    "CONSONANTPLACEHOLDER",
    "CONSONANTPRECEDINGREPHA",
    "CONSONANTPREFIXED",
    "CONSONANTSUBJOINED",
    "CONSONANTSUCCEEDINGREPHA",
    "CONSONANTWITHSTACKER",
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
    "CYRILLICEXTC",
    "CYRILLICEXTENDEDA",
    "CYRILLICEXTENDEDB",
    "CYRILLICEXTENDEDC",
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
    "EARLYDYNASTICCUNEIFORM",
    "EASTASIANWIDTH",
    "EB",
    "EBASE",
    "EBASEGAZ",
    "EBG",
    "EGYP",
    "EGYPTIANHIEROGLYPHS",
    "ELBA",
    "ELBASAN",
    "EM",
    "EMODIFIER",
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
    "GAZ",
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
    "GLAGOLITICSUP",
    "GLAGOLITICSUPPLEMENT",
    "GLUE",
    "GLUEAFTERZWJ",
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
    "HATR",
    "HATRAN",
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
    "HLUW",
    "HMNG",
    "HRKT",
    "HST",
    "HUNG",
    "HY",
    "HYPHEN",
    "ID",
    "IDC",
    "IDCONTINUE",
    "IDEO",
    "IDEOGRAPHIC",
    "IDEOGRAPHICDESCRIPTIONCHARACTERS",
    "IDEOGRAPHICSYMBOLS",
    "IDEOGRAPHICSYMBOLSANDPUNCTUATION",
    "IDS",
    "IDSB",
    "IDSBINARYOPERATOR",
    "IDST",
    "IDSTART",
    "IDSTRINARYOPERATOR",
    "IMPERIALARAMAIC",
    "IN",
    "INDICNUMBERFORMS",
    "INDICPOSITIONALCATEGORY",
    "INDICSYLLABICCATEGORY",
    "INFIXNUMERIC",
    "INHERITED",
    "INIT",
    "INITIAL",
    "INITIALPUNCTUATION",
    "INPC",
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
    "MARC",
    "MARCHEN",
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
    "MONGOLIANSUP",
    "MONGOLIANSUPPLEMENT",
    "MRO",
    "MROO",
    "MTEI",
    "MULT",
    "MULTANI",
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
    "NEWA",
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
    "OLDHUNGARIAN",
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
    "OSAGE",
    "OSGE",
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
    "PCM",
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
    "POSIXALNUM",
    "POSIXDIGIT",
    "POSIXPUNCT",
    "POSIXXDIGIT",
    "POSTFIXNUMERIC",
    "PP",
    "PR",
    "PREFIXNUMERIC",
    "PREPEND",
    "PREPENDEDCONCATENATIONMARK",
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
    "SENTENCETERMINAL",
    "SEP",
    "SEPARATOR",
    "SG",
    "SGNW",
    "SHARADA",
    "SHAVIAN",
    "SHAW",
    "SHIN",
    "SHORTHANDFORMATCONTROLS",
    "SHRD",
    "SIDD",
    "SIDDHAM",
    "SIGNWRITING",
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
    "SUPPLEMENTALSYMBOLSANDPICTOGRAPHS",
    "SUPPLEMENTARYPRIVATEUSEAREAA",
    "SUPPLEMENTARYPRIVATEUSEAREAB",
    "SUPPUAA",
    "SUPPUAB",
    "SUPPUNCTUATION",
    "SUPSYMBOLSANDPICTOGRAPHS",
    "SURROGATE",
    "SUTTONSIGNWRITING",
    "SWASHKAF",
    "SY",
    "SYLLABLEMODIFIER",
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
    "TANG",
    "TANGUT",
    "TANGUTCOMPONENTS",
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
    "ZWJ",
    "ZWSPACE",
    "ZYYY",
    "ZZZZ",
};

/* strings: 12639 bytes. */

/* properties. */

RE_Property re_properties[] = {
    { 568,  0,  0},
    { 565,  0,  0},
    { 264,  1,  1},
    { 263,  1,  1},
    {1116,  2,  2},
    {1114,  2,  2},
    {1298,  3,  3},
    {1293,  3,  3},
    { 590,  4,  4},
    { 566,  4,  4},
    {1122,  5,  5},
    {1113,  5,  5},
    { 851,  6,  6},
    { 182,  7,  6},
    { 181,  7,  6},
    { 793,  8,  6},
    { 792,  8,  6},
    {1266,  9,  6},
    {1265,  9,  6},
    { 306, 10,  6},
    { 308, 11,  6},
    { 362, 11,  6},
    { 355, 12,  6},
    { 445, 12,  6},
    { 357, 13,  6},
    { 447, 13,  6},
    { 356, 14,  6},
    { 446, 14,  6},
    { 353, 15,  6},
    { 443, 15,  6},
    { 354, 16,  6},
    { 444, 16,  6},
    { 662, 17,  6},
    { 658, 17,  6},
    { 652, 18,  6},
    { 651, 18,  6},
    {1306, 19,  6},
    {1305, 19,  6},
    {1304, 20,  6},
    {1303, 20,  6},
    { 472, 21,  6},
    { 480, 21,  6},
    { 591, 22,  6},
    { 599, 22,  6},
    { 589, 23,  6},
    { 593, 23,  6},
    { 592, 24,  6},
    { 600, 24,  6},
    {1294, 25,  6},
    {1301, 25,  6},
    {1153, 25,  6},
    { 256, 26,  6},
    { 254, 26,  6},
    { 697, 27,  6},
    { 695, 27,  6},
    { 465, 28,  6},
    { 649, 29,  6},
    {1079, 30,  6},
    {1076, 30,  6},
    {1227, 31,  6},
    {1226, 31,  6},
    {1004, 32,  6},
    { 983, 32,  6},
    { 636, 33,  6},
    { 635, 33,  6},
    { 214, 34,  6},
    { 170, 34,  6},
    { 997, 35,  6},
    { 964, 35,  6},
    { 654, 36,  6},
    { 653, 36,  6},
    { 482, 37,  6},
    { 481, 37,  6},
    { 543, 38,  6},
    { 541, 38,  6},
    {1003, 39,  6},
    { 982, 39,  6},
    {1009, 40,  6},
    {1010, 40,  6},
    { 940, 41,  6},
    { 925, 41,  6},
    { 999, 42,  6},
    { 969, 42,  6},
    { 660, 43,  6},
    { 659, 43,  6},
    { 663, 44,  6},
    { 661, 44,  6},
    {1081, 45,  6},
    {1262, 46,  6},
    {1258, 46,  6},
    { 998, 47,  6},
    { 966, 47,  6},
    { 474, 48,  6},
    { 473, 48,  6},
    {1149, 49,  6},
    {1117, 49,  6},
    { 791, 50,  6},
    { 790, 50,  6},
    {1001, 51,  6},
    { 971, 51,  6},
    {1000, 52,  6},
    { 970, 52,  6},
    {1123, 53,  6},
    {1162, 53,  6},
    {1271, 54,  6},
    {1287, 54,  6},
    {1022, 55,  6},
    {1023, 55,  6},
    {1021, 56,  6},
    {1020, 56,  6},
    {1061, 57,  6},
    {1027, 57,  6},
    { 622, 58,  7},
    { 646, 58,  7},
    { 255, 59,  8},
    { 244, 59,  8},
    { 300, 60,  9},
    { 312, 60,  9},
    { 471, 61, 10},
    { 496, 61, 10},
    { 503, 62, 11},
    { 501, 62, 11},
    { 699, 63, 12},
    { 693, 63, 12},
    { 700, 64, 13},
    { 701, 64, 13},
    { 783, 65, 14},
    { 758, 65, 14},
    { 959, 66, 15},
    { 952, 66, 15},
    { 960, 67, 16},
    { 962, 67, 16},
    { 258, 68,  6},
    { 257, 68,  6},
    { 667, 69, 17},
    { 674, 69, 17},
    { 668, 70, 18},
    { 675, 70, 18},
    { 185, 71,  6},
    { 180, 71,  6},
    { 193, 72,  6},
    { 262, 73,  6},
    { 588, 74,  6},
    {1062, 75,  6},
    {1297, 76,  6},
    {1302, 77,  6},
    {1053, 78,  6},
    {1052, 79,  6},
    {1054, 80,  6},
    {1055, 81,  6},
};

/* properties: 600 bytes. */

/* property values. */

RE_PropertyValue re_property_values[] = {
    {1259,  0,   0},
    { 395,  0,   0},
    {1267,  0,   1},
    { 800,  0,   1},
    { 794,  0,   2},
    { 787,  0,   2},
    {1239,  0,   3},
    { 799,  0,   3},
    { 893,  0,   4},
    { 788,  0,   4},
    {1002,  0,   5},
    { 789,  0,   5},
    { 944,  0,   6},
    { 891,  0,   6},
    { 525,  0,   7},
    { 859,  0,   7},
    {1155,  0,   8},
    { 858,  0,   8},
    { 470,  0,   9},
    { 926,  0,   9},
    { 487,  0,   9},
    { 773,  0,  10},
    { 935,  0,  10},
    {1006,  0,  11},
    { 936,  0,  11},
    {1154,  0,  12},
    {1330,  0,  12},
    { 785,  0,  13},
    {1328,  0,  13},
    {1019,  0,  14},
    {1329,  0,  14},
    { 427,  0,  15},
    { 311,  0,  15},
    { 396,  0,  15},
    { 557,  0,  16},
    { 350,  0,  16},
    {1063,  0,  17},
    { 397,  0,  17},
    {1189,  0,  18},
    { 437,  0,  18},
    { 466,  0,  19},
    {1028,  0,  19},
    { 986,  0,  20},
    {1066,  0,  20},
    { 393,  0,  21},
    {1031,  0,  21},
    { 413,  0,  22},
    {1026,  0,  22},
    {1007,  0,  23},
    {1049,  0,  23},
    { 856,  0,  24},
    {1143,  0,  24},
    { 441,  0,  25},
    {1114,  0,  25},
    { 895,  0,  26},
    {1142,  0,  26},
    {1008,  0,  27},
    {1148,  0,  27},
    { 673,  0,  28},
    {1046,  0,  28},
    { 552,  0,  29},
    {1033,  0,  29},
    { 996,  0,  30},
    { 293,  0,  30},
    { 294,  0,  30},
    { 771,  0,  31},
    { 734,  0,  31},
    { 735,  0,  31},
    { 850,  0,  32},
    { 809,  0,  32},
    { 404,  0,  32},
    { 810,  0,  32},
    { 955,  0,  33},
    { 915,  0,  33},
    { 916,  0,  33},
    {1070,  0,  34},
    {1014,  0,  34},
    {1069,  0,  34},
    {1015,  0,  34},
    {1196,  0,  35},
    {1103,  0,  35},
    {1104,  0,  35},
    {1125,  0,  36},
    {1323,  0,  36},
    {1324,  0,  36},
    { 307,  0,  37},
    { 759,  0,  37},
    { 215,  0,  38},
    { 937,  1,   0},
    { 923,  1,   0},
    { 238,  1,   1},
    { 213,  1,   1},
    { 744,  1,   2},
    { 743,  1,   2},
    { 742,  1,   2},
    { 751,  1,   3},
    { 745,  1,   3},
    { 753,  1,   4},
    { 747,  1,   4},
    { 683,  1,   5},
    { 682,  1,   5},
    {1156,  1,   6},
    { 894,  1,   6},
    { 399,  1,   7},
    { 483,  1,   7},
    { 595,  1,   8},
    { 594,  1,   8},
    { 450,  1,   9},
    { 458,  1,  10},
    { 457,  1,  10},
    { 459,  1,  10},
    { 209,  1,  11},
    { 630,  1,  12},
    { 196,  1,  13},
    {1198,  1,  14},
    { 208,  1,  15},
    { 207,  1,  15},
    {1232,  1,  16},
    { 933,  1,  17},
    {1108,  1,  18},
    { 817,  1,  19},
    { 198,  1,  20},
    { 197,  1,  20},
    { 477,  1,  21},
    { 250,  1,  22},
    { 603,  1,  23},
    { 601,  1,  24},
    { 988,  1,  25},
    {1215,  1,  26},
    {1225,  1,  27},
    { 714,  1,  28},
    { 815,  1,  29},
    {1140,  1,  30},
    {1233,  1,  31},
    { 739,  1,  32},
    {1234,  1,  33},
    { 909,  1,  34},
    { 574,  1,  35},
    { 618,  1,  36},
    { 688,  1,  36},
    { 529,  1,  37},
    { 535,  1,  38},
    { 534,  1,  38},
    { 359,  1,  39},
    {1260,  1,  40},
    {1254,  1,  40},
    { 298,  1,  40},
    { 968,  1,  41},
    {1101,  1,  42},
    {1201,  1,  43},
    { 625,  1,  44},
    { 289,  1,  45},
    {1203,  1,  46},
    { 724,  1,  47},
    { 899,  1,  48},
    {1261,  1,  49},
    {1255,  1,  49},
    { 776,  1,  50},
    {1206,  1,  51},
    { 930,  1,  52},
    { 725,  1,  53},
    { 287,  1,  54},
    {1207,  1,  55},
    { 400,  1,  56},
    { 484,  1,  56},
    { 233,  1,  57},
    {1166,  1,  58},
    { 241,  1,  59},
    { 770,  1,  60},
    { 972,  1,  61},
    { 456,  1,  62},
    { 453,  1,  62},
    {1168,  1,  63},
    {1167,  1,  63},
    {1275,  1,  64},
    {1274,  1,  64},
    {1043,  1,  65},
    {1042,  1,  65},
    {1044,  1,  66},
    {1045,  1,  66},
    { 402,  1,  67},
    { 486,  1,  67},
    { 752,  1,  68},
    { 746,  1,  68},
    { 597,  1,  69},
    { 596,  1,  69},
    { 569,  1,  70},
    {1070,  1,  70},
    {1175,  1,  71},
    {1174,  1,  71},
    { 442,  1,  72},
    { 401,  1,  73},
    { 485,  1,  73},
    { 405,  1,  73},
    { 772,  1,  74},
    { 956,  1,  75},
    { 212,  1,  76},
    { 854,  1,  77},
    { 855,  1,  77},
    { 883,  1,  78},
    { 888,  1,  78},
    { 428,  1,  79},
    { 987,  1,  80},
    { 965,  1,  80},
    { 518,  1,  81},
    { 517,  1,  81},
    { 274,  1,  82},
    { 265,  1,  83},
    { 570,  1,  84},
    { 880,  1,  85},
    { 887,  1,  85},
    { 488,  1,  86},
    { 878,  1,  87},
    { 884,  1,  87},
    {1177,  1,  88},
    {1170,  1,  88},
    { 281,  1,  89},
    { 280,  1,  89},
    {1178,  1,  90},
    {1171,  1,  90},
    { 879,  1,  91},
    { 885,  1,  91},
    {1180,  1,  92},
    {1176,  1,  92},
    { 881,  1,  93},
    { 877,  1,  93},
    { 579,  1,  94},
    { 754,  1,  95},
    { 748,  1,  95},
    { 430,  1,  96},
    { 576,  1,  97},
    { 575,  1,  97},
    {1236,  1,  98},
    { 532,  1,  99},
    { 530,  1,  99},
    { 454,  1, 100},
    { 451,  1, 100},
    {1181,  1, 101},
    {1187,  1, 101},
    { 380,  1, 102},
    { 379,  1, 102},
    { 713,  1, 103},
    { 712,  1, 103},
    { 655,  1, 104},
    { 651,  1, 104},
    { 383,  1, 105},
    { 382,  1, 105},
    { 641,  1, 106},
    { 716,  1, 107},
    { 268,  1, 108},
    { 617,  1, 109},
    { 410,  1, 109},
    { 711,  1, 110},
    { 270,  1, 111},
    { 269,  1, 111},
    { 381,  1, 112},
    { 719,  1, 113},
    { 717,  1, 113},
    { 522,  1, 114},
    { 521,  1, 114},
    { 368,  1, 115},
    { 366,  1, 115},
    { 385,  1, 116},
    { 374,  1, 116},
    {1318,  1, 117},
    {1317,  1, 117},
    { 384,  1, 118},
    { 365,  1, 118},
    {1320,  1, 119},
    {1319,  1, 120},
    { 786,  1, 121},
    {1269,  1, 122},
    { 455,  1, 123},
    { 452,  1, 123},
    { 235,  1, 124},
    { 896,  1, 125},
    { 755,  1, 126},
    { 749,  1, 126},
    {1195,  1, 127},
    { 407,  1, 128},
    { 666,  1, 128},
    {1035,  1, 129},
    {1112,  1, 130},
    { 479,  1, 131},
    { 478,  1, 131},
    { 720,  1, 132},
    {1085,  1, 133},
    { 619,  1, 134},
    { 689,  1, 134},
    { 692,  1, 135},
    { 913,  1, 136},
    { 911,  1, 136},
    { 352,  1, 137},
    { 912,  1, 138},
    { 910,  1, 138},
    {1208,  1, 139},
    { 865,  1, 140},
    { 864,  1, 140},
    { 533,  1, 141},
    { 531,  1, 141},
    { 756,  1, 142},
    { 750,  1, 142},
    { 361,  1, 143},
    { 360,  1, 143},
    { 863,  1, 144},
    { 621,  1, 145},
    { 616,  1, 145},
    { 620,  1, 146},
    { 690,  1, 146},
    { 639,  1, 147},
    { 637,  1, 148},
    { 638,  1, 148},
    { 795,  1, 149},
    {1064,  1, 150},
    {1068,  1, 150},
    {1063,  1, 150},
    { 370,  1, 151},
    { 372,  1, 151},
    { 184,  1, 152},
    { 183,  1, 152},
    { 205,  1, 153},
    { 203,  1, 153},
    {1272,  1, 154},
    {1287,  1, 154},
    {1278,  1, 155},
    { 403,  1, 156},
    { 610,  1, 156},
    { 369,  1, 157},
    { 367,  1, 157},
    {1146,  1, 158},
    {1145,  1, 158},
    { 206,  1, 159},
    { 204,  1, 159},
    { 612,  1, 160},
    { 609,  1, 160},
    {1157,  1, 161},
    { 782,  1, 162},
    { 781,  1, 163},
    { 165,  1, 164},
    { 191,  1, 165},
    { 192,  1, 166},
    {1037,  1, 167},
    {1036,  1, 167},
    { 806,  1, 168},
    { 304,  1, 169},
    { 431,  1, 170},
    { 975,  1, 171},
    { 585,  1, 172},
    { 977,  1, 173},
    {1257,  1, 174},
    { 978,  1, 175},
    { 475,  1, 176},
    {1129,  1, 177},
    { 995,  1, 178},
    { 992,  1, 179},
    { 511,  1, 180},
    { 309,  1, 181},
    { 779,  1, 182},
    { 449,  1, 183},
    { 664,  1, 184},
    {1018,  1, 185},
    { 918,  1, 186},
    { 627,  1, 187},
    {1041,  1, 188},
    { 808,  1, 189},
    { 871,  1, 190},
    { 870,  1, 191},
    { 723,  1, 192},
    { 979,  1, 193},
    { 976,  1, 194},
    { 820,  1, 195},
    { 227,  1, 196},
    { 677,  1, 197},
    { 676,  1, 198},
    {1067,  1, 199},
    { 980,  1, 200},
    { 974,  1, 201},
    {1100,  1, 202},
    {1099,  1, 202},
    { 277,  1, 203},
    { 705,  1, 204},
    {1151,  1, 205},
    { 351,  1, 206},
    { 811,  1, 207},
    {1128,  1, 208},
    {1141,  1, 209},
    { 728,  1, 210},
    { 906,  1, 211},
    { 729,  1, 212},
    { 587,  1, 213},
    { 928,  1, 214},
    {1238,  1, 215},
    {1135,  1, 216},
    { 892,  1, 217},
    { 901,  1, 218},
    { 900,  1, 218},
    {1212,  1, 219},
    { 171,  1, 220},
    {1291,  1, 221},
    {1025,  1, 222},
    { 252,  1, 223},
    { 849,  1, 224},
    { 438,  1, 225},
    { 440,  1, 226},
    { 439,  1, 226},
    { 502,  1, 227},
    { 509,  1, 228},
    { 188,  1, 229},
    { 237,  1, 230},
    { 236,  1, 230},
    { 902,  1, 231},
    { 240,  1, 232},
    {1016,  1, 233},
    { 872,  1, 234},
    { 657,  1, 235},
    { 656,  1, 235},
    {1218,  1, 236},
    {1219,  1, 237},
    { 709,  1, 238},
    { 708,  1, 238},
    { 499,  1, 239},
    {1132,  1, 240},
    { 292,  1, 241},
    { 291,  1, 241},
    { 908,  1, 242},
    { 907,  1, 242},
    { 190,  1, 243},
    { 189,  1, 243},
    {1210,  1, 244},
    {1209,  1, 244},
    { 433,  1, 245},
    { 432,  1, 245},
    { 853,  1, 246},
    { 852,  1, 246},
    {1190,  1, 247},
    { 581,  1, 248},
    { 580,  1, 248},
    { 867,  1, 249},
    { 163,  1, 250},
    { 201,  1, 251},
    { 200,  1, 251},
    { 814,  1, 252},
    { 813,  1, 252},
    { 490,  1, 253},
    { 489,  1, 253},
    {1047,  1, 254},
    { 519,  1, 255},
    { 520,  1, 255},
    { 524,  1, 256},
    { 523,  1, 256},
    { 882,  1, 257},
    { 886,  1, 257},
    { 514,  1, 258},
    { 990,  1, 259},
    {1251,  1, 260},
    {1250,  1, 260},
    { 177,  1, 261},
    { 176,  1, 261},
    { 572,  1, 262},
    { 571,  1, 262},
    {1179,  1, 263},
    {1172,  1, 263},
    {1182,  1, 264},
    {1188,  1, 264},
    { 386,  1, 265},
    { 375,  1, 265},
    { 387,  1, 266},
    { 376,  1, 266},
    { 388,  1, 267},
    { 377,  1, 267},
    { 389,  1, 268},
    { 378,  1, 268},
    { 371,  1, 269},
    { 373,  1, 269},
    {1204,  1, 270},
    {1273,  1, 271},
    {1288,  1, 271},
    {1183,  1, 272},
    {1185,  1, 272},
    {1184,  1, 273},
    {1186,  1, 273},
    {1263,  2,   0},
    {1335,  2,   0},
    { 406,  2,   1},
    {1334,  2,   1},
    { 741,  2,   2},
    { 757,  2,   2},
    { 594,  2,   3},
    { 598,  2,   3},
    { 450,  2,   4},
    { 460,  2,   4},
    { 209,  2,   5},
    { 211,  2,   5},
    { 630,  2,   6},
    { 629,  2,   6},
    { 196,  2,   7},
    { 195,  2,   7},
    {1198,  2,   8},
    {1197,  2,   8},
    {1232,  2,   9},
    {1231,  2,   9},
    { 477,  2,  10},
    { 476,  2,  10},
    { 250,  2,  11},
    { 249,  2,  11},
    { 603,  2,  12},
    { 604,  2,  12},
    { 601,  2,  13},
    { 602,  2,  13},
    { 988,  2,  14},
    { 991,  2,  14},
    {1215,  2,  15},
    {1216,  2,  15},
    {1225,  2,  16},
    {1224,  2,  16},
    { 714,  2,  17},
    { 730,  2,  17},
    { 815,  2,  18},
    { 890,  2,  18},
    {1140,  2,  19},
    {1139,  2,  19},
    {1233,  2,  20},
    { 739,  2,  21},
    { 740,  2,  21},
    {1234,  2,  22},
    {1235,  2,  22},
    { 909,  2,  23},
    { 914,  2,  23},
    { 574,  2,  24},
    { 573,  2,  24},
    { 616,  2,  25},
    { 615,  2,  25},
    { 529,  2,  26},
    { 528,  2,  26},
    { 359,  2,  27},
    { 358,  2,  27},
    { 297,  2,  28},
    { 301,  2,  28},
    { 968,  2,  29},
    { 967,  2,  29},
    {1101,  2,  30},
    {1102,  2,  30},
    { 724,  2,  31},
    { 726,  2,  31},
    { 899,  2,  32},
    { 898,  2,  32},
    { 641,  2,  33},
    { 640,  2,  33},
    { 716,  2,  34},
    { 707,  2,  34},
    { 268,  2,  35},
    { 267,  2,  35},
    { 614,  2,  36},
    { 623,  2,  36},
    {1315,  2,  37},
    {1316,  2,  37},
    { 975,  2,  38},
    { 687,  2,  38},
    { 585,  2,  39},
    { 584,  2,  39},
    { 475,  2,  40},
    { 495,  2,  40},
    { 670,  2,  41},
    {1327,  2,  41},
    {1073,  2,  41},
    {1201,  2,  42},
    {1230,  2,  42},
    { 625,  2,  43},
    { 624,  2,  43},
    { 289,  2,  44},
    { 288,  2,  44},
    {1203,  2,  45},
    {1202,  2,  45},
    { 776,  2,  46},
    { 775,  2,  46},
    {1206,  2,  47},
    {1213,  2,  47},
    { 780,  2,  48},
    { 778,  2,  48},
    {1257,  2,  49},
    {1256,  2,  49},
    {1129,  2,  50},
    {1130,  2,  50},
    { 995,  2,  51},
    { 994,  2,  51},
    { 448,  2,  52},
    { 435,  2,  52},
    { 280,  2,  53},
    { 279,  2,  53},
    { 287,  2,  54},
    { 286,  2,  54},
    { 430,  2,  55},
    { 429,  2,  55},
    {1072,  2,  55},
    { 930,  2,  56},
    {1214,  2,  56},
    { 579,  2,  57},
    { 578,  2,  57},
    {1236,  2,  58},
    {1229,  2,  58},
    {1195,  2,  59},
    {1194,  2,  59},
    { 978,  2,  60},
    {1307,  2,  60},
    { 723,  2,  61},
    { 722,  2,  61},
    { 233,  2,  62},
    { 232,  2,  62},
    { 438,  2,  63},
    {1308,  2,  63},
    {1041,  2,  64},
    {1040,  2,  64},
    {1035,  2,  65},
    {1034,  2,  65},
    { 933,  2,  66},
    { 934,  2,  66},
    {1166,  2,  67},
    {1165,  2,  67},
    { 770,  2,  68},
    { 769,  2,  68},
    { 972,  2,  69},
    { 973,  2,  69},
    {1269,  2,  70},
    {1270,  2,  70},
    {1112,  2,  71},
    {1111,  2,  71},
    { 720,  2,  72},
    { 706,  2,  72},
    {1085,  2,  73},
    {1094,  2,  73},
    { 806,  2,  74},
    { 805,  2,  74},
    { 304,  2,  75},
    { 303,  2,  75},
    { 808,  2,  76},
    { 807,  2,  76},
    { 352,  2,  77},
    {1207,  2,  78},
    { 738,  2,  78},
    {1208,  2,  79},
    {1220,  2,  79},
    { 227,  2,  80},
    { 228,  2,  80},
    { 509,  2,  81},
    { 508,  2,  81},
    {1108,  2,  82},
    {1109,  2,  82},
    { 786,  2,  83},
    { 235,  2,  84},
    { 234,  2,  84},
    { 692,  2,  85},
    { 691,  2,  85},
    { 863,  2,  86},
    { 904,  2,  86},
    { 664,  2,  87},
    { 210,  2,  87},
    { 979,  2,  88},
    {1110,  2,  88},
    { 677,  2,  89},
    {1065,  2,  89},
    { 676,  2,  90},
    {1038,  2,  90},
    { 980,  2,  91},
    { 989,  2,  91},
    { 705,  2,  92},
    { 732,  2,  92},
    { 241,  2,  93},
    { 242,  2,  93},
    { 277,  2,  94},
    { 276,  2,  94},
    { 817,  2,  95},
    { 816,  2,  95},
    { 351,  2,  96},
    { 295,  2,  96},
    { 870,  2,  97},
    { 868,  2,  97},
    { 871,  2,  98},
    { 869,  2,  98},
    { 872,  2,  99},
    {1048,  2,  99},
    {1128,  2, 100},
    {1133,  2, 100},
    {1151,  2, 101},
    {1150,  2, 101},
    {1212,  2, 102},
    {1211,  2, 102},
    { 309,  2, 103},
    { 169,  2, 103},
    { 240,  2, 104},
    { 239,  2, 104},
    { 499,  2, 105},
    { 498,  2, 105},
    { 511,  2, 106},
    { 510,  2, 106},
    { 587,  2, 107},
    { 586,  2, 107},
    {1016,  2, 108},
    { 644,  2, 108},
    { 728,  2, 109},
    { 727,  2, 109},
    { 779,  2, 110},
    { 777,  2, 110},
    { 811,  2, 111},
    { 812,  2, 111},
    { 820,  2, 112},
    { 819,  2, 112},
    { 867,  2, 113},
    { 866,  2, 113},
    { 892,  2, 114},
    { 902,  2, 115},
    { 903,  2, 115},
    { 976,  2, 116},
    { 921,  2, 116},
    { 918,  2, 117},
    { 924,  2, 117},
    {1018,  2, 118},
    {1017,  2, 118},
    {1025,  2, 119},
    {1024,  2, 119},
    { 977,  2, 120},
    {1032,  2, 120},
    {1067,  2, 121},
    {1039,  2, 121},
    {1135,  2, 122},
    {1134,  2, 122},
    { 729,  2, 123},
    {1137,  2, 123},
    {1238,  2, 124},
    {1237,  2, 124},
    {1291,  2, 125},
    {1290,  2, 125},
    { 171,  2, 126},
    { 188,  2, 127},
    { 643,  2, 127},
    { 627,  2, 128},
    { 626,  2, 128},
    { 906,  2, 129},
    { 905,  2, 129},
    { 974,  2, 130},
    { 647,  2, 130},
    {1136,  2, 131},
    {1127,  2, 131},
    { 163,  2, 132},
    { 164,  2, 132},
    { 252,  2, 133},
    { 253,  2, 133},
    { 849,  2, 134},
    { 848,  2, 134},
    { 928,  2, 135},
    { 992,  2, 136},
    { 993,  2, 136},
    {1218,  2, 137},
    {1217,  2, 137},
    { 718,  2, 138},
    { 645,  2, 138},
    { 996,  3,   0},
    {1309,  3,   0},
    { 493,  3,   1},
    { 494,  3,   1},
    {1138,  3,   2},
    {1158,  3,   2},
    { 631,  3,   3},
    { 642,  3,   3},
    { 436,  3,   4},
    { 774,  3,   5},
    { 929,  3,   6},
    { 935,  3,   6},
    { 542,  3,   7},
    {1082,  3,   8},
    {1087,  3,   8},
    { 557,  3,   9},
    { 555,  3,   9},
    { 716,  3,  10},
    { 703,  3,  10},
    { 179,  3,  11},
    { 760,  3,  11},
    { 873,  3,  12},
    { 889,  3,  12},
    { 874,  3,  13},
    { 891,  3,  13},
    { 875,  3,  14},
    { 857,  3,  14},
    { 958,  3,  15},
    { 953,  3,  15},
    { 544,  3,  16},
    { 539,  3,  16},
    { 505,  3,  17},
    { 504,  3,  17},
    { 513,  3,  18},
    { 512,  3,  18},
    {1332,  3,  19},
    { 583,  3,  20},
    { 564,  3,  20},
    { 506,  3,  21},
    { 507,  3,  21},
    { 996,  4,   0},
    {1309,  4,   0},
    {1060,  4,   1},
    {1057,  4,   1},
    { 436,  4,   2},
    { 774,  4,   3},
    { 427,  4,   4},
    { 395,  4,   4},
    { 542,  4,   5},
    { 539,  4,   5},
    {1082,  4,   6},
    {1087,  4,   6},
    {1155,  4,   7},
    {1143,  4,   7},
    { 734,  4,   8},
    {1268,  4,   9},
    {1200,  4,  10},
    { 801,  4,  11},
    { 803,  4,  12},
    { 505,  4,  13},
    { 504,  4,  13},
    { 513,  4,  14},
    { 512,  4,  14},
    {1332,  4,  15},
    { 583,  4,  16},
    { 564,  4,  16},
    { 506,  4,  17},
    { 507,  4,  17},
    { 996,  5,   0},
    {1309,  5,   0},
    { 436,  5,   1},
    { 774,  5,   2},
    { 542,  5,   3},
    { 539,  5,   3},
    {1124,  5,   4},
    {1118,  5,   4},
    { 557,  5,   5},
    { 555,  5,   5},
    {1152,  5,   6},
    { 792,  5,   7},
    { 789,  5,   7},
    {1265,  5,   8},
    {1264,  5,   8},
    { 981,  5,   9},
    { 760,  5,   9},
    { 958,  5,  10},
    { 953,  5,  10},
    { 221,  5,  11},
    { 216,  5,  11},
    {1162,  5,  12},
    {1161,  5,  12},
    { 391,  5,  13},
    { 390,  5,  13},
    {1115,  5,  14},
    {1114,  5,  14},
    { 936,  6,   0},
    { 915,  6,   0},
    { 545,  6,   0},
    { 546,  6,   0},
    {1314,  6,   1},
    {1310,  6,   1},
    {1200,  6,   1},
    {1252,  6,   1},
    { 947,  7,   0},
    { 917,  7,   0},
    { 761,  7,   1},
    { 734,  7,   1},
    {1285,  7,   2},
    {1268,  7,   2},
    {1248,  7,   3},
    {1200,  7,   3},
    { 802,  7,   4},
    { 801,  7,   4},
    { 804,  7,   5},
    { 803,  7,   5},
    { 765,  8,   0},
    { 734,  8,   0},
    {1090,  8,   1},
    {1080,  8,   1},
    { 536,  8,   2},
    { 515,  8,   2},
    { 537,  8,   3},
    { 526,  8,   3},
    { 538,  8,   4},
    { 527,  8,   4},
    { 202,  8,   5},
    { 187,  8,   5},
    { 408,  8,   6},
    { 437,  8,   6},
    {1019,  8,   7},
    { 229,  8,   7},
    {1120,  8,   8},
    {1103,  8,   8},
    {1294,  8,   9},
    {1300,  8,   9},
    {1005,  8,  10},
    { 984,  8,  10},
    { 273,  8,  11},
    { 266,  8,  11},
    { 944,  8,  12},
    { 951,  8,  12},
    { 199,  8,  13},
    { 174,  8,  13},
    { 768,  8,  14},
    { 798,  8,  14},
    {1093,  8,  15},
    {1097,  8,  15},
    { 766,  8,  16},
    { 796,  8,  16},
    {1091,  8,  17},
    {1095,  8,  17},
    {1050,  8,  18},
    {1029,  8,  18},
    { 767,  8,  19},
    { 797,  8,  19},
    {1092,  8,  20},
    {1096,  8,  20},
    { 554,  8,  21},
    { 560,  8,  21},
    {1051,  8,  22},
    {1030,  8,  22},
    { 948,  9,   0},
    {   1,  9,   0},
    { 949,  9,   0},
    {1012,  9,   1},
    {   2,  9,   1},
    {1011,  9,   1},
    { 954,  9,   2},
    { 135,  9,   2},
    { 932,  9,   2},
    { 710,  9,   3},
    { 144,  9,   3},
    { 733,  9,   3},
    {1279,  9,   4},
    { 151,  9,   4},
    {1286,  9,   4},
    { 313,  9,   5},
    {  17,  9,   5},
    { 316,  9,   6},
    {  28,  9,   6},
    { 318,  9,   7},
    {  32,  9,   7},
    { 321,  9,   8},
    {  35,  9,   8},
    { 325,  9,   9},
    {  40,  9,   9},
    { 326,  9,  10},
    {  41,  9,  10},
    { 327,  9,  11},
    {  43,  9,  11},
    { 328,  9,  12},
    {  44,  9,  12},
    { 329,  9,  13},
    {  46,  9,  13},
    { 330,  9,  14},
    {  47,  9,  14},
    { 331,  9,  15},
    {  51,  9,  15},
    { 332,  9,  16},
    {  57,  9,  16},
    { 333,  9,  17},
    {  62,  9,  17},
    { 334,  9,  18},
    {  68,  9,  18},
    { 335,  9,  19},
    {  73,  9,  19},
    { 336,  9,  20},
    {  75,  9,  20},
    { 337,  9,  21},
    {  76,  9,  21},
    { 338,  9,  22},
    {  77,  9,  22},
    { 339,  9,  23},
    {  78,  9,  23},
    { 340,  9,  24},
    {  79,  9,  24},
    { 341,  9,  25},
    {  88,  9,  25},
    { 342,  9,  26},
    {  93,  9,  26},
    { 343,  9,  27},
    {  94,  9,  27},
    { 344,  9,  28},
    {  95,  9,  28},
    { 345,  9,  29},
    {  96,  9,  29},
    { 346,  9,  30},
    {  97,  9,  30},
    { 347,  9,  31},
    {  98,  9,  31},
    { 348,  9,  32},
    { 150,  9,  32},
    { 349,  9,  33},
    { 158,  9,  33},
    { 314,  9,  34},
    {  26,  9,  34},
    { 315,  9,  35},
    {  27,  9,  35},
    { 317,  9,  36},
    {  31,  9,  36},
    { 319,  9,  37},
    {  33,  9,  37},
    { 320,  9,  38},
    {  34,  9,  38},
    { 322,  9,  39},
    {  37,  9,  39},
    { 323,  9,  40},
    {  38,  9,  40},
    { 224,  9,  41},
    {  56,  9,  41},
    { 219,  9,  41},
    { 222,  9,  42},
    {  58,  9,  42},
    { 217,  9,  42},
    { 223,  9,  43},
    {  59,  9,  43},
    { 218,  9,  43},
    { 247,  9,  44},
    {  61,  9,  44},
    { 261,  9,  44},
    { 246,  9,  45},
    {  63,  9,  45},
    { 229,  9,  45},
    { 248,  9,  46},
    {  64,  9,  46},
    { 275,  9,  46},
    { 762,  9,  47},
    {  65,  9,  47},
    { 734,  9,  47},
    {1088,  9,  48},
    {  66,  9,  48},
    {1080,  9,  48},
    { 161,  9,  49},
    {  67,  9,  49},
    { 174,  9,  49},
    { 160,  9,  50},
    {  69,  9,  50},
    { 159,  9,  50},
    { 162,  9,  51},
    {  70,  9,  51},
    { 194,  9,  51},
    { 492,  9,  52},
    {  71,  9,  52},
    { 467,  9,  52},
    { 491,  9,  53},
    {  72,  9,  53},
    { 462,  9,  53},
    { 681,  9,  54},
    {  74,  9,  54},
    { 684,  9,  54},
    { 324,  9,  55},
    {  39,  9,  55},
    { 225,  9,  56},
    {  52,  9,  56},
    { 220,  9,  56},
    { 941, 10,   0},
    { 299, 10,   1},
    { 296, 10,   1},
    { 409, 10,   2},
    { 398, 10,   2},
    { 556, 10,   3},
    { 938, 10,   4},
    { 923, 10,   4},
    { 672, 10,   5},
    { 671, 10,   5},
    { 861, 10,   6},
    { 860, 10,   6},
    { 551, 10,   7},
    { 550, 10,   7},
    { 686, 10,   8},
    { 685, 10,   8},
    { 363, 10,   9},
    { 516, 10,   9},
    {1173, 10,  10},
    {1169, 10,  10},
    {1164, 10,  11},
    {1277, 10,  12},
    {1276, 10,  12},
    {1295, 10,  13},
    { 922, 10,  14},
    { 920, 10,  14},
    {1144, 10,  15},
    {1147, 10,  15},
    {1160, 10,  16},
    {1159, 10,  16},
    { 559, 10,  17},
    { 558, 10,  17},
    { 927, 11,   0},
    { 915, 11,   0},
    { 186, 11,   1},
    { 159, 11,   1},
    { 611, 11,   2},
    { 605, 11,   2},
    {1295, 11,   3},
    {1289, 11,   3},
    { 561, 11,   4},
    { 545, 11,   4},
    { 922, 11,   5},
    { 917, 11,   5},
    { 939, 12,   0},
    { 173, 12,   1},
    { 175, 12,   2},
    { 178, 12,   3},
    { 245, 12,   4},
    { 251, 12,   5},
    { 463, 12,   6},
    { 464, 12,   7},
    { 500, 12,   8},
    { 549, 12,   9},
    { 553, 12,  10},
    { 562, 12,  11},
    { 563, 12,  12},
    { 608, 12,  13},
    { 613, 12,  14},
    {1223, 12,  14},
    { 628, 12,  15},
    { 632, 12,  16},
    { 633, 12,  17},
    { 634, 12,  18},
    { 704, 12,  19},
    { 715, 12,  20},
    { 731, 12,  21},
    { 736, 12,  22},
    { 737, 12,  23},
    { 862, 12,  24},
    { 876, 12,  25},
    { 946, 12,  26},
    { 961, 12,  27},
    {1031, 12,  28},
    {1074, 12,  29},
    {1075, 12,  30},
    {1084, 12,  31},
    {1086, 12,  32},
    {1106, 12,  33},
    {1107, 12,  34},
    {1119, 12,  35},
    {1121, 12,  36},
    {1131, 12,  37},
    {1191, 12,  38},
    {1205, 12,  39},
    {1221, 12,  40},
    {1222, 12,  41},
    {1228, 12,  42},
    {1292, 12,  43},
    {1199, 12,  44},
    {1311, 12,  45},
    {1312, 12,  46},
    {1313, 12,  47},
    {1321, 12,  48},
    {1322, 12,  49},
    {1325, 12,  50},
    {1326, 12,  51},
    { 721, 12,  52},
    { 548, 12,  53},
    { 290, 12,  54},
    { 547, 12,  55},
    { 963, 12,  56},
    {1098, 12,  57},
    {1163, 12,  58},
    { 821, 12,  59},
    { 822, 12,  60},
    { 823, 12,  61},
    { 824, 12,  62},
    { 825, 12,  63},
    { 826, 12,  64},
    { 827, 12,  65},
    { 828, 12,  66},
    { 829, 12,  67},
    { 830, 12,  68},
    { 831, 12,  69},
    { 832, 12,  70},
    { 833, 12,  71},
    { 834, 12,  72},
    { 835, 12,  73},
    { 836, 12,  74},
    { 837, 12,  75},
    { 838, 12,  76},
    { 839, 12,  77},
    { 840, 12,  78},
    { 841, 12,  79},
    { 842, 12,  80},
    { 843, 12,  81},
    { 844, 12,  82},
    { 845, 12,  83},
    { 846, 12,  84},
    { 847, 12,  85},
    { 166, 12,  86},
    { 168, 12,  87},
    { 167, 12,  88},
    { 943, 13,   0},
    {1253, 13,   0},
    { 696, 13,   1},
    { 293, 13,   1},
    { 497, 13,   2},
    { 461, 13,   2},
    {1089, 13,   3},
    {1080, 13,   3},
    { 764, 13,   4},
    { 734, 13,   4},
    {1249, 13,   5},
    {1200, 13,   5},
    {1263, 14,   0},
    {1309, 14,   0},
    { 986, 14,   1},
    { 985, 14,   1},
    { 393, 14,   2},
    { 390, 14,   2},
    {1078, 14,   3},
    {1077, 14,   3},
    { 582, 14,   4},
    { 577, 14,   4},
    { 945, 14,   5},
    { 950, 14,   5},
    { 540, 14,   6},
    { 539, 14,   6},
    { 285, 14,   7},
    {1192, 14,   7},
    { 669, 14,   8},
    { 684, 14,   8},
    {1059, 14,   9},
    {1058, 14,   9},
    {1056, 14,  10},
    {1049, 14,  10},
    { 958, 14,  11},
    { 953, 14,  11},
    { 182, 14,  12},
    { 174, 14,  12},
    { 654, 14,  13},
    { 650, 14,  13},
    { 678, 14,  14},
    { 665, 14,  14},
    { 679, 14,  14},
    { 649, 14,  15},
    { 648, 14,  15},
    { 404, 14,  16},
    { 394, 14,  16},
    { 283, 14,  17},
    { 243, 14,  17},
    { 282, 14,  18},
    { 231, 14,  18},
    {1153, 14,  19},
    {1152, 14,  19},
    { 818, 14,  20},
    { 260, 14,  20},
    { 305, 14,  21},
    { 436, 14,  21},
    { 784, 14,  22},
    { 774, 14,  22},
    { 426, 14,  23},
    { 310, 14,  23},
    { 411, 14,  24},
    {1105, 14,  24},
    { 186, 14,  25},
    { 172, 14,  25},
    { 284, 14,  26},
    { 230, 14,  26},
    {1189, 14,  27},
    {1126, 14,  27},
    {1333, 14,  28},
    {1331, 14,  28},
    { 931, 14,  29},
    { 935, 14,  29},
    {1299, 14,  30},
    {1296, 14,  30},
    { 694, 14,  31},
    { 702, 14,  32},
    { 701, 14,  33},
    { 606, 14,  34},
    { 607, 14,  35},
    { 392, 14,  36},
    { 434, 14,  36},
    { 631, 14,  37},
    { 642, 14,  37},
    { 412, 14,  38},
    { 364, 14,  38},
    {1082, 14,  39},
    {1087, 14,  39},
    { 505, 14,  40},
    { 504, 14,  40},
    { 513, 14,  41},
    { 512, 14,  41},
    {1332, 14,  42},
    { 941, 15,   0},
    { 958, 15,   1},
    { 953, 15,   1},
    { 487, 15,   2},
    { 480, 15,   2},
    { 469, 15,   3},
    { 468, 15,   3},
    { 919, 16,   0},
    {   0, 16,   1},
    {   1, 16,   2},
    {   6, 16,   3},
    {  11, 16,   4},
    {  87, 16,   5},
    {   8, 16,   6},
    {   5, 16,   7},
    {   4, 16,   8},
    {   3, 16,   9},
    {  16, 16,  10},
    {  15, 16,  11},
    {  14, 16,  12},
    {  83, 16,  13},
    {  13, 16,  14},
    {  81, 16,  15},
    {  12, 16,  16},
    {  10, 16,  17},
    {   9, 16,  18},
    {  86, 16,  19},
    {  50, 16,  20},
    { 120, 16,  21},
    {   7, 16,  22},
    { 136, 16,  23},
    {  85, 16,  24},
    { 123, 16,  25},
    {  49, 16,  26},
    {  84, 16,  27},
    { 103, 16,  28},
    { 122, 16,  29},
    { 138, 16,  30},
    {  29, 16,  31},
    {   2, 16,  32},
    {  82, 16,  33},
    {  48, 16,  34},
    { 121, 16,  35},
    {  80, 16,  36},
    { 137, 16,  37},
    { 102, 16,  38},
    { 152, 16,  39},
    { 119, 16,  40},
    {  30, 16,  41},
    { 129, 16,  42},
    {  36, 16,  43},
    { 135, 16,  44},
    {  42, 16,  45},
    { 144, 16,  46},
    {  45, 16,  47},
    { 151, 16,  48},
    {  17, 16,  49},
    {  28, 16,  50},
    {  32, 16,  51},
    {  35, 16,  52},
    {  40, 16,  53},
    {  41, 16,  54},
    {  43, 16,  55},
    {  44, 16,  56},
    {  46, 16,  57},
    {  47, 16,  58},
    {  51, 16,  59},
    {  57, 16,  60},
    {  62, 16,  61},
    {  68, 16,  62},
    {  73, 16,  63},
    {  75, 16,  64},
    {  76, 16,  65},
    {  77, 16,  66},
    {  78, 16,  67},
    {  79, 16,  68},
    {  88, 16,  69},
    {  93, 16,  70},
    {  94, 16,  71},
    {  95, 16,  72},
    {  96, 16,  73},
    {  97, 16,  74},
    {  98, 16,  75},
    {  99, 16,  76},
    { 100, 16,  77},
    { 101, 16,  78},
    { 104, 16,  79},
    { 109, 16,  80},
    { 110, 16,  81},
    { 111, 16,  82},
    { 113, 16,  83},
    { 114, 16,  84},
    { 115, 16,  85},
    { 116, 16,  86},
    { 117, 16,  87},
    { 118, 16,  88},
    { 124, 16,  89},
    { 130, 16,  90},
    { 139, 16,  91},
    { 145, 16,  92},
    { 153, 16,  93},
    {  18, 16,  94},
    {  52, 16,  95},
    {  89, 16,  96},
    { 105, 16,  97},
    { 125, 16,  98},
    { 131, 16,  99},
    { 140, 16, 100},
    { 146, 16, 101},
    { 154, 16, 102},
    {  19, 16, 103},
    {  53, 16, 104},
    {  90, 16, 105},
    { 106, 16, 106},
    { 126, 16, 107},
    { 132, 16, 108},
    { 141, 16, 109},
    { 147, 16, 110},
    { 155, 16, 111},
    {  20, 16, 112},
    {  54, 16, 113},
    {  91, 16, 114},
    { 107, 16, 115},
    { 127, 16, 116},
    { 133, 16, 117},
    { 142, 16, 118},
    { 148, 16, 119},
    { 156, 16, 120},
    {  21, 16, 121},
    {  55, 16, 122},
    {  60, 16, 123},
    {  92, 16, 124},
    { 108, 16, 125},
    { 112, 16, 126},
    { 128, 16, 127},
    { 134, 16, 128},
    { 143, 16, 129},
    { 149, 16, 130},
    { 157, 16, 131},
    {  22, 16, 132},
    {  23, 16, 133},
    {  24, 16, 134},
    {  25, 16, 135},
    { 917, 17,   0},
    {1088, 17,   1},
    { 762, 17,   2},
    {1281, 17,   3},
    { 763, 17,   4},
    {1242, 17,   5},
    { 271, 17,   6},
    {1243, 17,   7},
    {1247, 17,   8},
    {1245, 17,   9},
    {1246, 17,  10},
    { 272, 17,  11},
    {1244, 17,  12},
    {1013, 17,  13},
    { 996, 18,   0},
    { 259, 18,   1},
    {1280, 18,   2},
    { 226, 18,   3},
    { 954, 18,   4},
    {1279, 18,   5},
    {1071, 18,   6},
    { 680, 18,   7},
    {1284, 18,   8},
    {1283, 18,   9},
    {1282, 18,  10},
    { 420, 18,  11},
    { 414, 18,  12},
    { 415, 18,  13},
    { 425, 18,  14},
    { 422, 18,  15},
    { 421, 18,  16},
    { 424, 18,  17},
    { 423, 18,  18},
    { 419, 18,  19},
    { 416, 18,  20},
    { 417, 18,  21},
    { 897, 18,  22},
    {1240, 18,  23},
    {1241, 18,  24},
    { 567, 18,  25},
    { 302, 18,  26},
    {1083, 18,  27},
    {1193, 18,  28},
    { 418, 18,  29},
    { 942, 18,  30},
    { 698, 18,  31},
    { 957, 18,  32},
    { 955, 18,  33},
    { 278, 18,  34},
};

/* property values: 5876 bytes. */

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
    11, 12, 13, 14, 15, 16, 17,  5, 18, 16, 16, 19, 16, 20, 21, 22,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 23, 24, 25, 16, 16, 26,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
    27, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16, 16,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 28,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 28,
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
    131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 123, 123, 141, 123, 123, 123,
    142, 143, 144, 145, 146, 147, 148, 123, 149, 150, 123, 151, 152, 153, 154, 123,
    123, 155, 123, 123, 123, 156, 123, 123, 157, 158, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34,  34,  34,  34, 159, 160,  34, 161, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34,  34,  34,  34,  34, 162, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123,  34,  34,  34,  34, 163, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34, 164, 165, 166, 167, 123, 123, 123, 123, 123, 123, 168, 169,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 170,
     34,  34,  34,  34,  34, 171, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    172, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 173, 174, 123, 123, 123, 123, 123, 123,
     69, 175, 176, 177, 178, 123, 179, 123, 180, 181, 182, 183, 184, 185, 186, 187,
     69,  69,  69,  69, 188, 189, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    190, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34, 191, 192, 123, 123, 123, 123, 123, 123, 123, 123, 123, 193, 194, 123, 123,
    195, 196, 197, 198, 199, 123,  69, 200,  69,  69,  69,  69,  69, 201, 202, 203,
    204, 205, 206, 207, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 208,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 209,  34,
    210,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34,  34, 211, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
     34,  34,  34,  34, 212, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    213, 123, 214, 215, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123, 123,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108,
    108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 108, 216,
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
     49,  68,  69,  70,  49,  71,  72,  72,  72,  72,  49,  73,  72,  74,  75,  32,
     76,  49,  49,  77,  78,  79,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,
     90,  83,  84,  91,  92,  93,  94,  95,  96,  97,  84,  98,  99, 100,  88, 101,
    102,  83,  84, 103, 104, 105,  88, 106, 107, 108, 109, 110, 111, 112,  94, 113,
    114, 115,  84, 116, 117, 118,  88, 119, 120, 115,  84, 121, 122, 123,  88, 124,
    125, 115,  49, 126, 127, 128,  88, 129, 130, 131,  49, 132, 133, 134,  94, 135,
    136,  49,  49, 137, 138, 139,  72,  72, 140, 141, 142, 143, 144, 145,  72,  72,
    146, 147, 148, 149, 150,  49, 151, 152, 153, 154,  32, 155, 156, 157,  72,  72,
     49,  49, 158, 159, 160, 161, 162, 163, 164, 165,   9,   9, 166,  49,  49, 167,
     49,  49,  49,  49,  49,  49,  49,  49,  49,  49,  49,  49, 168, 169,  49,  49,
    168,  49,  49, 170, 171, 172,  49,  49,  49, 171,  49,  49,  49, 173, 174, 175,
     49, 176,   9,   9,   9,   9,   9, 177, 178,  49,  49,  49,  49,  49,  49,  49,
     49,  49,  49,  49,  49,  49, 179,  49, 180, 181,  49,  49,  49,  49, 182, 183,
    184, 185,  49, 186,  49, 187, 184, 188,  49,  49,  49, 189, 190, 191, 192, 193,
    194, 192,  49,  49, 195,  49,  49, 196, 197,  49, 198,  49,  49,  49,  49, 199,
     49, 200, 201, 202, 203,  49, 204, 205,  49,  49, 206,  49, 207, 208, 209, 209,
     49, 210,  49,  49,  49, 211, 212, 213, 192, 192, 214, 215,  72,  72,  72,  72,
    216,  49,  49, 217, 218, 160, 219, 220, 221,  49, 222,  65,  49,  49, 223, 224,
     49,  49, 225, 226, 227,  65,  49, 228, 229,  72,  72,  72, 230, 231, 232, 233,
     11,  11, 234,  27,  27,  27, 235, 236,  11, 237,  27,  27,  32,  32,  32, 238,
     13,  13,  13,  13,  13,  13,  13,  13,  13, 239,  13,  13,  13,  13,  13,  13,
    240, 241, 240, 240, 241, 242, 240, 243, 244, 244, 244, 245, 246, 247, 248, 249,
    250, 251, 252, 253, 254, 255, 256, 257, 258, 259, 260, 261,  72, 262, 263, 264,
    265, 266, 267, 268, 269, 270, 271, 271, 272, 273, 274, 209, 275, 276, 209, 277,
    278, 278, 278, 278, 278, 278, 278, 278, 279, 209, 280, 209, 209, 209, 209, 281,
    209, 282, 278, 283, 209, 284, 285, 286, 209, 209, 287,  72, 288,  72, 270, 270,
    270, 289, 209, 209, 209, 209, 290, 270, 209, 209, 209, 209, 209, 209, 209, 209,
    209, 209, 209, 291, 292, 209, 209, 293, 209, 209, 209, 209, 209, 209, 294, 209,
    209, 209, 209, 209, 209, 209, 295, 296, 270, 297, 209, 209, 298, 278, 299, 278,
    300, 301, 278, 278, 278, 302, 278, 303, 209, 209, 209, 278, 304, 209, 209, 305,
    209, 306, 209, 307, 308, 309, 310,  72,   9,   9, 311,  11,  11, 312, 313, 314,
     13,  13,  13,  13,  13,  13, 315, 316,  11,  11, 317,  49,  49,  49, 318, 319,
     49, 320, 321, 321, 321, 321,  32,  32, 322, 323, 324, 325, 326,  72,  72,  72,
    209, 327, 209, 209, 209, 209, 209, 328, 209, 209, 209, 209, 209, 329,  72, 330,
    331, 332, 333, 334, 136,  49,  49,  49,  49, 335, 178,  49,  49,  49,  49, 336,
    337,  49, 204, 136,  49,  49,  49,  49, 200, 338,  49,  50, 209, 209, 328,  49,
    209, 286, 339, 209, 340, 341, 209, 209, 339, 209, 209, 341, 209, 209, 209, 286,
     49,  49,  49, 199, 209, 209, 209, 209,  49,  49,  49,  49,  49, 199,  72,  72,
     49, 342,  49,  49,  49,  49,  49,  49, 151, 209, 209, 209, 287,  49,  49, 228,
    343,  49, 344,  72,  13,  13, 345, 346,  13, 347,  49,  49,  49,  49, 348, 349,
     31, 350, 351, 352,  13,  13,  13, 353, 354, 355, 356, 357,  72,  72,  72, 358,
    359,  49, 360, 361,  49,  49,  49, 362, 363,  49,  49, 364, 365, 192,  32, 366,
     65,  49, 367,  49, 368, 369,  49, 151,  76,  49,  49, 370, 371, 372, 373, 374,
     49,  49, 375, 376, 377, 378,  49, 379,  49,  49,  49, 380, 381, 382, 383, 384,
    385, 386, 321,  11,  11, 387, 388,  11,  11,  11,  11,  11,  49,  49, 389, 192,
     49,  49, 390,  49, 391,  49,  49, 206, 392, 392, 392, 392, 392, 392, 392, 392,
    393, 393, 393, 393, 393, 393, 393, 393,  49,  49,  49,  49,  49,  49, 204,  49,
     49,  49,  49,  49,  49, 207,  72,  72, 394, 395, 396, 397, 398,  49,  49,  49,
     49,  49,  49, 399, 400, 401,  49,  49,  49,  49,  49, 402,  72,  49,  49,  49,
     49, 403,  49,  49, 196,  72,  72, 404,  32, 405,  32, 406, 407, 408, 409, 410,
     49,  49,  49,  49,  49,  49,  49, 411, 412,   2,   3,   4,   5, 413, 414, 415,
     49, 416,  49, 200, 417, 418, 419, 420, 421,  49, 172, 422, 204, 204,  72,  72,
     49,  49,  49,  49,  49,  49,  49,  50, 423, 270, 270, 424, 271, 271, 271, 425,
    426, 330, 427,  72,  72, 209, 209, 428,  72,  72,  72,  72,  72,  72,  72,  72,
     49, 151,  49,  49,  49, 100, 429, 430,  49,  49, 431,  49, 432,  49,  49, 433,
     49, 434,  49,  49, 435, 436,  72,  72,   9,   9, 437,  11,  11,  49,  49,  49,
     49, 204, 192,   9,   9, 438,  11, 439,  49,  49, 196,  49,  49,  49, 440,  72,
     49,  49,  49, 320,  49, 199, 196,  72, 441,  49,  49, 442,  49, 443,  49, 444,
     49, 200, 445,  72,  72,  72,  49, 446,  49, 447,  49, 448,  72,  72,  72,  72,
     49,  49,  49, 449, 270, 450, 270, 270, 451, 452,  49, 453, 454, 455,  49, 456,
     49, 457,  72,  72, 458,  49, 459, 460,  49,  49,  49, 461,  49, 462,  49, 463,
     49, 464, 465,  72,  72,  72,  72,  72,  49,  49,  49,  49, 466,  72,  72,  72,
      9,   9,   9, 467,  11,  11,  11, 468,  72,  72,  72,  72,  72,  72, 270, 469,
    470,  49,  49, 471, 472, 450, 473, 474, 221,  49,  49, 475, 476,  49, 466, 192,
    477,  49, 478, 479, 480,  49,  49, 481, 221,  49,  49, 482, 483, 484, 485, 486,
     49,  97, 487, 488,  72,  72,  72,  72, 489, 490, 491,  49,  49, 492, 493, 192,
    494,  83,  84,  98, 495, 496, 497, 498,  49,  49,  49, 499, 500, 501,  72,  72,
     49,  49,  49, 502, 503, 192,  72,  72,  49,  49, 504, 505, 506, 507,  72,  72,
     49,  49,  49, 508, 509, 192, 510,  72,  49,  49, 511, 512, 192,  72,  72,  72,
     49, 513, 514, 515,  72,  72,  72,  72,  72,  72,   9,   9,  11,  11, 148, 516,
     72,  72,  72,  72,  49,  49,  49, 466,  84,  49, 504, 517, 518, 148, 175, 519,
     49, 520, 521, 522,  72,  72,  72,  72,  49, 207,  72,  72,  72,  72,  72,  72,
    271, 271, 271, 271, 271, 271, 523, 524,  49,  49,  49,  49, 390,  72,  72,  72,
     49,  49, 200,  72,  72,  72,  72,  72,  49,  49,  49,  49, 320,  72,  72,  72,
     49,  49,  49, 466,  49, 200, 372,  72,  72,  72,  72,  72,  72,  49, 204, 525,
     49,  49,  49, 526, 527, 528, 529, 530,  49,  72,  72,  72,  72,  72,  72,  72,
     49,  49,  49,  49, 205, 531, 532, 533, 474, 534,  72,  72,  72,  72, 535,  72,
     49,  49,  49,  49,  49,  49, 151,  72,  49,  49,  49,  49,  49,  49,  49, 536,
    537,  72,  72,  72,  72,  72,  72,  72,  49,  49,  49,  49,  49,  49,  50, 151,
    466, 538, 539,  72,  72,  72,  72,  72, 209, 209, 209, 209, 209, 209, 209, 329,
    209, 209, 540, 209, 209, 209, 541, 542, 543, 209, 544, 209, 209, 209, 545,  72,
    209, 209, 209, 209, 546,  72,  72,  72, 209, 209, 209, 209, 209, 287, 270, 547,
      9, 548,  11, 549, 550, 551, 240,   9, 552, 553, 554, 555, 556,   9, 548,  11,
    557, 558,  11, 559, 560, 561, 562,   9, 563,  11,   9, 548,  11, 549, 550,  11,
    240,   9, 552, 562,   9, 563,  11,   9, 548,  11, 564,   9, 565, 566, 567, 568,
     11, 569,   9, 570, 571, 572, 573,  11, 574,   9, 575,  11, 576, 577, 577, 577,
     32,  32,  32, 578,  32,  32, 579, 580, 581, 582,  46,  72,  72,  72,  72,  72,
    583, 584, 585,  72,  72,  72,  72,  72,  49,  49,  49,  49, 586, 587,  72,  72,
      9,   9, 552,  11, 588, 372,  72,  72, 589,  49, 590, 591, 592, 593, 594, 595,
    596, 206, 597, 206,  72,  72,  72, 598, 209, 209, 330, 209, 209, 209, 209, 209,
    209, 328, 286, 599, 599, 599, 209, 329, 175, 209, 286, 209, 209, 209, 330, 209,
    209, 209, 600,  72,  72,  72, 601, 209, 602, 209, 209, 330, 545, 309,  72,  72,
    209, 209, 209, 209, 209, 209, 209, 603, 209, 209, 209, 209, 209, 602, 600, 287,
    209, 209, 209, 209, 209, 209, 209, 328, 209, 209, 209, 209, 209, 604,  72,  72,
    330, 209, 209, 209, 605, 176, 209, 209, 605, 209, 606,  72,  72,  72,  72,  72,
     72, 286, 605, 607, 330, 286,  72,  72, 209, 309,  72,  72, 427,  72,  72,  72,
     49,  49,  49,  49,  49, 320,  72,  72,  49,  49,  49, 205,  49,  49,  49,  49,
     49, 204,  49,  49,  49,  49,  49,  49,  49,  49, 537,  72,  72,  72,  72,  72,
     49, 204,  72,  72,  72,  72,  72,  72, 608,  72, 609, 609, 609, 609, 609, 609,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  72,
    393, 393, 393, 393, 393, 393, 393, 610,
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
     44,  44,  44,  44,  44,  44,  44,  44,  36,  36,  62,  36,  36,  36,  36,  44,
     44,  44,  43,  43,  43,  43,  43,  43,  43,  83,  43,  43,  43,  43,  43,  43,
     43,  84,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  84,  71,  85,
     86,  43,  43,  43,  84,  85,  86,  85,  70,  43,  43,  43,  36,  36,  36,  36,
     36,  43,   2,   7,   7,   7,   7,   7,  87,  36,  36,  36,  36,  36,  36,  36,
     70,  85,  81,  36,  36,  36,  62,  81,  62,  81,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  62,  36,  36,  36,  62,  62,  44,  36,  36,  44,  71,  85,
     86,  43,  80,  88,  89,  88,  86,  62,  44,  44,  44,  88,  44,  44,  36,  81,
     36,  43,  44,   7,   7,   7,   7,   7,  36,  20,  27,  27,  27,  57,  44,  44,
     58,  84,  81,  36,  36,  62,  44,  81,  62,  36,  81,  62,  36,  44,  80,  85,
     86,  80,  44,  58,  80,  58,  43,  44,  58,  44,  44,  44,  81,  36,  62,  62,
     44,  44,  44,   7,   7,   7,   7,   7,  43,  36,  70,  44,  44,  44,  44,  44,
     58,  84,  81,  36,  36,  36,  36,  81,  36,  81,  36,  36,  36,  36,  36,  36,
     62,  36,  81,  36,  36,  44,  71,  85,  86,  43,  43,  58,  84,  88,  86,  44,
     62,  44,  44,  44,  44,  44,  44,  44,  66,  44,  44,  44,  81,  44,  44,  44,
     58,  85,  81,  36,  36,  36,  62,  81,  62,  36,  81,  36,  36,  44,  71,  86,
     86,  43,  80,  88,  89,  88,  86,  44,  44,  44,  44,  84,  44,  44,  36,  81,
     78,  27,  27,  27,  44,  44,  44,  44,  44,  71,  81,  36,  36,  62,  44,  36,
     62,  36,  36,  44,  81,  62,  62,  36,  44,  81,  62,  44,  36,  62,  44,  36,
     36,  36,  36,  36,  36,  44,  44,  85,  84,  89,  44,  85,  89,  85,  86,  44,
     62,  44,  44,  88,  44,  44,  44,  44,  27,  90,  67,  67,  57,  91,  44,  44,
     84,  85,  81,  36,  36,  36,  62,  36,  62,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  44,  81,  43,  84,  85,  89,  43,  80,  43,  43,  44,
     44,  44,  58,  80,  36,  62,  44,  44,  44,  44,  44,  44,  27,  27,  27,  90,
     70,  85,  81,  36,  36,  36,  62,  36,  36,  36,  81,  36,  36,  44,  71,  86,
     85,  85,  89,  84,  89,  85,  43,  44,  44,  44,  88,  89,  44,  44,  44,  62,
     81,  62,  44,  44,  44,  44,  44,  44,  58,  85,  81,  36,  36,  36,  62,  36,
     36,  36,  36,  36,  36,  62,  81,  85,  86,  43,  80,  85,  89,  85,  86,  77,
     44,  44,  36,  92,  27,  27,  27,  93,  27,  27,  27,  27,  90,  36,  36,  36,
     44,  85,  81,  36,  36,  36,  36,  36,  36,  36,  36,  62,  44,  36,  36,  36,
     36,  81,  36,  36,  36,  36,  81,  44,  36,  36,  36,  62,  44,  80,  44,  88,
     85,  43,  80,  80,  85,  85,  85,  85,  44,  85,  64,  44,  44,  44,  44,  44,
     81,  36,  36,  36,  36,  36,  36,  36,  70,  36,  43,  43,  43,  80,  44,  94,
     36,  36,  36,  75,  43,  43,  43,  61,   7,   7,   7,   7,   7,   2,  44,  44,
     81,  62,  62,  81,  62,  62,  81,  44,  44,  44,  36,  36,  81,  36,  36,  36,
     81,  36,  81,  81,  44,  36,  81,  36,  70,  36,  43,  43,  43,  58,  71,  44,
     36,  36,  62,  82,  43,  43,  43,  44,   7,   7,   7,   7,   7,  44,  36,  36,
     77,  67,   2,   2,   2,   2,   2,   2,   2,  95,  95,  67,  43,  67,  67,  67,
      7,   7,   7,   7,   7,  27,  27,  27,  27,  27,  50,  50,  50,   4,   4,  85,
     36,  36,  36,  36,  81,  36,  36,  36,  36,  36,  36,  36,  36,  36,  62,  44,
     58,  43,  43,  43,  43,  43,  43,  84,  43,  43,  61,  43,  36,  36,  70,  43,
     43,  43,  43,  43,  58,  43,  43,  43,  43,  43,  43,  43,  43,  43,  80,  67,
     67,  67,  67,  76,  67,  67,  91,  67,   2,   2,  95,  67,  21,  64,  44,  44,
     36,  36,  36,  36,  36,  92,  86,  43,  84,  43,  43,  43,  86,  84,  86,  71,
      7,   7,   7,   7,   7,   2,   2,   2,  36,  36,  36,  85,  43,  36,  36,  43,
     71,  85,  96,  92,  85,  85,  85,  36,  70,  43,  71,  36,  36,  36,  36,  36,
     36,  84,  86,  84,  85,  85,  86,  92,   7,   7,   7,   7,   7,  85,  86,  67,
     11,  11,  11,  48,  44,  44,  48,  44,  36,  36,  36,  36,  36,  63,  69,  36,
     36,  36,  36,  36,  62,  36,  36,  44,  36,  36,  36,  62,  62,  36,  36,  44,
     62,  36,  36,  44,  36,  36,  36,  62,  62,  36,  36,  44,  36,  36,  36,  36,
     36,  36,  36,  62,  36,  36,  36,  36,  36,  36,  36,  36,  36,  62,  58,  43,
      2,   2,   2,   2,  97,  27,  27,  27,  27,  27,  27,  27,  27,  27,  98,  44,
     67,  67,  67,  67,  67,  44,  44,  44,  11,  11,  11,  44,  16,  16,  16,  44,
     99,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  63,  72,
    100,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36, 101, 102,  44,
     36,  36,  36,  36,  36,  63,   2, 103, 104,  36,  36,  36,  62,  44,  44,  44,
     36,  36,  36,  36,  36,  36,  62,  36,  36,  43,  80,  44,  44,  44,  44,  44,
     36,  43,  61,  64,  44,  44,  44,  44,  36,  43,  44,  44,  44,  44,  44,  44,
     62,  43,  44,  44,  44,  44,  44,  44,  36,  36,  43,  86,  43,  43,  43,  85,
     85,  85,  85,  84,  86,  43,  43,  43,  43,  43,   2,  87,   2,  66,  70,  44,
      7,   7,   7,   7,   7,  44,  44,  44,  27,  27,  27,  27,  27,  44,  44,  44,
      2,   2,   2, 105,   2,  60,  43,  68,  36, 106,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  44,  44,  44,  44,  36,  36,  70,  71,  36,  36,  36,  36,
     36,  36,  36,  36,  70,  62,  44,  44,  36,  36,  36,  44,  44,  44,  44,  44,
     36,  36,  36,  36,  36,  36,  36,  62,  43,  84,  85,  86,  84,  85,  44,  44,
     85,  84,  85,  85,  86,  43,  44,  44,  91,  44,   2,   7,   7,   7,   7,   7,
     36,  36,  36,  36,  36,  36,  36,  44,  36,  36,  62,  44,  44,  44,  44,  44,
     36,  36,  36,  36,  36,  36,  44,  44,  36,  36,  36,  36,  36,  44,  44,  44,
      7,   7,   7,   7,   7,  98,  44,  67,  67,  67,  67,  67,  67,  67,  67,  67,
     36,  36,  36,  70,  84,  86,  44,   2,  36,  36,  92,  84,  43,  43,  43,  80,
     84,  84,  86,  43,  43,  43,  84,  85,  85,  86,  43,  43,  43,  43,  80,  58,
      2,   2,   2,  87,   2,   2,   2,  44,  43,  43,  43,  43,  43,  43,  43, 107,
     43,  43,  96,  36,  36,  36,  36,  36,  36,  36,  84,  43,  43,  84,  84,  85,
     85,  84,  96,  36,  36,  36,  44,  44,  95,  67,  67,  67,  67,  50,  43,  43,
     43,  43,  67,  67,  67,  67,  91,  44,  43,  96,  36,  36,  36,  36,  36,  36,
     92,  43,  43,  85,  43,  86,  43,  36,  36,  36,  36,  84,  43,  85,  86,  86,
     43,  85,  44,  44,  44,  44,   2,   2,  36,  36,  85,  85,  85,  85,  43,  43,
     43,  43,  85,  43,  44,  54,   2,   2,   7,   7,   7,   7,   7,  44,  81,  36,
     36,  36,  36,  36,  40,  40,  40,   2,  16,  16,  16,  16, 108,  44,  44,  44,
      2,   2,   2,   2,  44,  44,  44,  44,  43,  61,  43,  43,  43,  43,  43,  43,
     84,  43,  43,  43,  71,  36,  70,  36,  36,  85,  71,  62,  43,  44,  44,  44,
     16,  16,  16,  16,  16,  16,  40,  40,  40,  40,  40,  40,  40,  45,  16,  16,
     16,  16,  16,  16,  45,  16,  16,  16,  16,  16,  16,  16,  16, 109,  40,  40,
     43,  43,  43,  44,  44,  58,  43,  43,  32,  32,  32,  16,  16,  16,  16,  32,
     16,  16,  16,  16,  11,  11,  11,  11,  16,  16,  16,  44,  11,  11,  11,  44,
     16,  16,  16,  16,  48,  48,  48,  48,  16,  16,  16,  16,  16,  16,  16,  44,
     16,  16,  16,  16, 110, 110, 110, 110,  16,  16, 108,  16,  11,  11, 111, 112,
     41,  16, 108,  16,  11,  11, 111,  41,  16,  16,  44,  16,  11,  11, 113,  41,
     16,  16,  16,  16,  11,  11, 114,  41,  44,  16, 108,  16,  11,  11, 111, 115,
    116, 116, 116, 116, 116, 117,  65,  65, 118, 118, 118,   2, 119, 120, 119, 120,
      2,   2,   2,   2, 121,  65,  65, 122,   2,   2,   2,   2, 123, 124,   2, 125,
    126,   2, 127, 128,   2,   2,   2,   2,   2,   9, 126,   2,   2,   2,   2, 129,
     65,  65,  68,  65,  65,  65,  65,  65, 130,  44,  27,  27,  27,   8, 127, 131,
     27,  27,  27,  27,  27,   8, 127, 102,  40,  40,  40,  40,  40,  40,  82,  44,
     20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20,  20, 132,
     43,  43,  43,  43,  43,  43, 133,  51, 134,  51, 134,  43,  43,  43,  43,  43,
     80,  44,  44,  44,  44,  44,  44,  44,  67, 135,  67, 136,  67,  34,  11,  16,
     11,  32, 136,  67,  49,  11,  11,  67,  67,  67, 135, 135, 135,  11,  11, 137,
     11,  11,  35,  36,  39,  67,  16,  11,   8,   8,  49,  16,  16,  26,  67, 138,
     27,  27,  27,  27,  27,  27,  27,  27, 103, 103, 103, 103, 103, 103, 103, 103,
    103, 139, 140, 103, 141,  67,  44,  44,   8,   8, 142,  67,  67,   8,  67,  67,
    142,  26,  67, 142,  67,  67,  67, 142,  67,  67,  67,  67,  67,  67,  67,   8,
     67, 142, 142,  67,  67,  67,  67,  67,  67,  67,   8,   8,   8,   8,   8,   8,
      8,   8,   8,   8,   8,   8,   8,   8,  67,  67,  67,  67,   4,   4,  67,  67,
      8,  67,  67,  67, 143, 144,  67,  67,  67,  67,  67,  67,  67,  67, 142,  67,
     67,  67,  67,  67,  67,  26,   8,   8,   8,   8,  67,  67,  67,  67,  67,  67,
     67,  67,  67,  67,  67,  67,   8,   8,   8,  67,  67,  67,  67,  67,  67,  67,
     67,  67,  67,  67,  67,  67,  67,  91,  67,  67,  67,  91,  44,  44,  44,  44,
     67,  67,  67,  67,  67,  91,  44,  44,  27,  27,  27,  27,  27,  27,  67,  67,
     67,  67,  67,  67,  67,  27,  27,  27,  67,  67,  67,  26,  67,  67,  67,  67,
     26,  67,  67,  67,  67,  67,  67,  67,  67,  67,  67,  67,   8,   8,   8,   8,
     67,  67,  67,  67,  67,  67,  67,  26,  67,  67,  67,  67,   4,   4,   4,   4,
      4,   4,   4,  27,  27,  27,  27,  27,  27,  27,  67,  67,  67,  67,  67,  67,
      8,   8, 127, 145,   8,   8,   8,   8,   8,   8,   8,   4,   4,   4,   4,   4,
      8, 127, 146, 146, 146, 146, 146, 146, 146, 146, 146, 146, 145,   8,   8,   8,
      8,   8,   8,   8,   4,   4,   8,   8,   8,   8,   8,   8,   8,   8,   4,   8,
      8,   8, 142,  26,   8,   8, 142,  67,  67,  67,  44,  67,  67,  67,  67,  67,
     67,  67,  67,  44,  67,  67,  67,  67,  67,  67,  67,  67,  67,  44,  56,  67,
     67,  67,  67,  67,  91,  67,  67,  67,  67,  44,  44,  44,  44,  44,  44,  44,
     44,  44,  44,  44,  44,  44,  67,  67,  11,  11,  11,  11,  11,  11,  11,  47,
     16,  16,  16,  16,  16,  16,  16, 108,  32,  11,  32,  34,  34,  34,  34,  11,
     32,  32,  34,  16,  16,  16,  40,  11,  32,  32, 138,  67,  67, 136,  34, 147,
     43,  32,  44,  44,  54,   2,  97,   2,  16,  16,  16,  53,  44,  44,  53,  44,
     36,  36,  36,  36,  44,  44,  44,  52,  64,  44,  44,  44,  44,  44,  44,  58,
     36,  36,  36,  62,  44,  44,  44,  44,  36,  36,  36,  62,  36,  36,  36,  62,
      2, 119, 119,   2, 123, 124, 119,   2,   2,   2,   2,   6,   2, 105, 119,   2,
    119,   4,   4,   4,   4,   2,   2,  87,   2,   2,   2,   2,   2, 118,   2,   2,
    105, 148,  64,  44,  44,  44,  44,  44,  67,  67,  67,  67,  67,  56,  67,  67,
     67,  67,  44,  44,  44,  44,  44,  44,  67,  67,  67,  44,  44,  44,  44,  44,
     67,  67,  67,  67,  67,  67,  44,  44,   1,   2, 149, 150,   4,   4,   4,   4,
      4,  67,   4,   4,   4,   4, 151, 152, 153, 103, 103, 103, 103,  43,  43,  85,
    154,  40,  40,  67, 103, 155,  63,  67,  36,  36,  36,  62,  58, 156, 157,  69,
     36,  36,  36,  36,  36,  63,  40,  69,  44,  44,  81,  36,  36,  36,  36,  36,
     67,  27,  27,  67,  67,  67,  67,  67,  27,  27,  27,  27,  27,  67,  67,  67,
     67,  67,  67,  67,  27,  27,  27,  27, 158,  27,  27,  27,  27,  27,  27,  27,
     36,  36, 106,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36, 159,   2,
      7,   7,   7,   7,   7,  36,  44,  44,  32,  32,  32,  32,  32,  32,  32,  70,
     51, 160,  43,  43,  43,  43,  43,  87,  32,  32,  32,  32,  32,  32,  40,  43,
     36,  36,  36, 103, 103, 103, 103, 103,  43,   2,   2,   2,  44,  44,  44,  44,
     41,  41,  41, 157,  40,  40,  40,  40,  41,  32,  32,  32,  32,  32,  32,  32,
     16,  32,  32,  32,  32,  32,  32,  32,  45,  16,  16,  16,  34,  34,  34,  32,
     32,  32,  32,  32,  42, 161,  34,  35,  32,  32,  16,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  32,  11,  11,  47,  11,  11,  32,  32,  44,  44,  44,  44,
     44,  44,  44,  81,  40,  35,  36,  36,  36,  71,  36,  71,  36,  70,  36,  36,
     36,  92,  86,  84,  67,  67,  44,  44,  27,  27,  27,  67, 162,  44,  44,  44,
     36,  36,   2,   2,  44,  44,  44,  44,  85,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  85,  85,  85,  85,  85,  85,  85,  85,  43,  44,  44,  44,  44,   2,
     43,  36,  36,  36,   2,  72,  72,  44,  36,  36,  36,  43,  43,  43,  43,   2,
     36,  36,  36,  70,  43,  43,  43,  43,  43,  85,  44,  44,  44,  44,  44,  54,
     36,  70,  85,  43,  43,  85,  84,  85, 163,   2,   2,   2,   2,   2,   2,  52,
      7,   7,   7,   7,   7,  44,  44,   2,  36,  36,  70,  69,  36,  36,  36,  36,
      7,   7,   7,   7,   7,  36,  36,  62,  36,  36,  36,  36,  70,  43,  43,  84,
     86,  84,  86,  80,  44,  44,  44,  44,  36,  70,  36,  36,  36,  36,  84,  44,
      7,   7,   7,   7,   7,  44,   2,   2,  69,  36,  36,  77,  67,  92,  84,  36,
     71,  43,  71,  70,  71,  36,  36,  43,  70,  62,  44,  44,  44,  44,  44,  44,
     44,  44,  44,  44,  44,  81, 106,   2,  36,  36,  36,  36,  36,  92,  43,  85,
      2, 106, 164,  80,  44,  44,  44,  44,  81,  36,  36,  62,  81,  36,  36,  62,
     81,  36,  36,  62,  44,  44,  44,  44,  16,  16,  16,  16,  16, 112,  40,  40,
     16,  16,  16,  44,  44,  44,  44,  44,  36,  92,  86,  85,  84, 163,  86,  44,
     36,  36,  44,  44,  44,  44,  44,  44,  36,  36,  36,  62,  44,  81,  36,  36,
    165, 165, 165, 165, 165, 165, 165, 165, 166, 166, 166, 166, 166, 166, 166, 166,
     16,  16,  16, 108,  44,  44,  44,  44,  44,  53,  16,  16,  44,  44,  81,  71,
     36,  36,  36,  36, 167,  36,  36,  36,  36,  36,  36,  62,  36,  36,  62,  62,
     36,  81,  62,  36,  36,  36,  36,  36,  36,  41,  41,  41,  41,  41,  41,  41,
     41,  44,  44,  44,  44,  44,  44,  44,  44,  81,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  36, 146,  44,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36, 162,  44,   2,   2,   2, 168, 128,  44,  44,  44,
      6, 169, 170, 146, 146, 146, 146, 146, 146, 146, 128, 168, 128,   2, 125, 171,
      2,  64,   2,   2, 151, 146, 146, 128,   2, 172,   8, 173,  66,   2,  44,  44,
     36,  36,  62,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  62,  79,
     54,   2,   3,   2,   4,   5,   6,   2,  16,  16,  16,  16,  16,  17,  18, 127,
    128,   4,   2,  36,  36,  36,  36,  36,  69,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  36,  40,  44,  36,  36,  36,  44,  36,  36,  36,
     44,  36,  36,  36,  44,  36,  62,  44,  20, 174,  57, 132,  26,   8, 142,  91,
     44,  44,  44,  44,  79,  65,  67,  44,  36,  36,  36,  36,  36,  36,  81,  36,
     36,  36,  36,  36,  36,  62,  36,  81,   2,  64,  44, 175,  27,  27,  27,  27,
     27,  27,  44,  56,  67,  67,  67,  67, 103, 103, 141,  27,  90,  67,  67,  67,
     67,  67,  67,  67,  67,  27,  67,  91,  91,  44,  44,  44,  44,  44,  44,  44,
     67,  67,  67,  67,  67,  67,  50,  44, 176,  27,  27,  27,  27,  27,  27,  27,
     27,  27,  27,  27,  27,  27,  44,  44,  27,  27,  44,  44,  44,  44,  44,  44,
    150,  36,  36,  36,  36, 177,  44,  44,  36,  36,  36,  43,  43,  80,  44,  44,
     36,  36,  36,  36,  36,  36,  36,  54,  36,  36,  44,  44,  36,  36,  36,  36,
    178, 103, 103,  44,  44,  44,  44,  44,  11,  11,  11,  11,  16,  16,  16,  16,
     11,  11,  44,  44,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  44,  44,
     36,  36,  44,  44,  44,  44,  44,  54,  36,  36,  36,  44,  62,  36,  36,  36,
     36,  36,  36,  81,  62,  44,  62,  81,  36,  36,  36,  54,  27,  27,  27,  27,
     36,  36,  36,  77, 158,  27,  27,  27,  44,  44,  44, 175,  27,  27,  27,  27,
     36,  62,  36,  44,  44, 175,  27,  27,  36,  36,  36,  27,  27,  27,  44,  54,
     36,  36,  36,  36,  36,  44,  44,  54,  36,  36,  36,  36,  44,  44,  27,  36,
     44,  27,  27,  27,  27,  27,  27,  27,  70,  43,  58,  80,  44,  44,  43,  43,
     36,  36,  81,  36,  81,  36,  36,  36,  36,  36,  44,  44,  43,  80,  44,  58,
     27,  27,  27,  27,  44,  44,  44,  44,   2,   2,   2,   2,  64,  44,  44,  44,
     36,  36,  36,  36,  36,  36, 179,  30,  36,  36,  36,  36,  36,  36, 179,  27,
     36,  36,  36,  36,  78,  36,  36,  36,  36,  36,  70,  80,  44, 175,  27,  27,
      2,   2,   2,  64,  44,  44,  44,  44,  36,  36,  36,  44,  54,   2,   2,   2,
     36,  36,  36,  44,  27,  27,  27,  27,  36,  62,  44,  44,  27,  27,  27,  27,
     36,  44,  44,  44,  54,   2,  64,  44,  44,  44,  44,  44, 175,  27,  27,  27,
     36,  36,  36,  36,  62,  44,  44,  44,  11,  47,  44,  44,  44,  44,  44,  44,
     16, 108,  44,  44,  44,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,  98,
     86,  96,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  43,  43,  43,  43,
     43,  43,  43,  61,   2,   2,   2,  44,  27,  27,  27,   7,   7,   7,   7,   7,
     44,  44,  44,  44,  44,  44,  44,  58,  85,  86,  43,  84,  86,  61, 180,   2,
      2,  44,  44,  44,  44,  44,  44,  44,  43,  71,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  70,  43,  43,  86,  43,  43,  43,  80,   7,   7,   7,   7,   7,
      2,   2,  44,  44,  44,  44,  44,  44,  36,  70,   2,  62,  44,  44,  44,  44,
     36,  92,  85,  43,  43,  43,  43,  84,  96,  36,  63,   2,   2,  43,  61,  44,
      7,   7,   7,   7,   7,  63,  63,   2, 175,  27,  27,  27,  27,  27,  27,  27,
     27,  27,  98,  44,  44,  44,  44,  44,  36,  36,  36,  36,  36,  36,  85,  86,
     43,  85,  84,  43,   2,   2,   2,  80,  36,  36,  36,  62,  62,  36,  36,  81,
     36,  36,  36,  36,  36,  36,  36,  81,  36,  36,  36,  36,  63,  44,  44,  44,
     36,  36,  36,  36,  36,  36,  36,  70,  85,  86,  43,  43,  43,  80,  44,  44,
     43,  85,  81,  36,  36,  36,  62,  81,  84,  85,  89,  88,  89,  88,  85,  44,
     62,  44,  44,  88,  44,  44,  81,  36,  36,  85,  44,  43,  43,  43,  80,  44,
     43,  43,  80,  44,  44,  44,  44,  44,  36,  36,  92,  85,  43,  43,  43,  43,
     85,  43,  84,  71,  36,  63,   2,   2,   7,   7,   7,   7,   7,  54,  54,  44,
     85,  86,  43,  43,  84,  84,  85,  86,  84,  43,  36,  72,  44,  44,  44,  44,
     36,  36,  36,  36,  36,  36,  36,  92,  85,  43,  43,  44,  85,  85,  43,  86,
     61,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  36,  36,  43,  44,
     85,  86,  43,  43,  43,  84,  86,  86,  61,   2,  62,  44,  44,  44,  44,  44,
      2,   2,   2,   2,   2,   2,  64,  44,  36,  36,  36,  36,  36,  70,  86,  85,
     43,  43,  43,  86,  44,  44,  44,  44,  36,  36,  36,  36,  36,  44,  58,  43,
     85,  43,  43,  86,  43,  43,  44,  44,   7,   7,   7,   7,   7,  27,   2,  95,
     27,  98,  44,  44,  44,  44,  44,  81,  43,  43,  43,  80,  43,  43,  43,  86,
     63,   2,   2,  44,  44,  44,  44,  44,   2,  36,  36,  36,  36,  36,  36,  36,
     44,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  43,  88,  43,  43,  43,
     84,  43,  86,  80,  44,  44,  44,  44, 103, 103, 103, 103, 103, 103, 103, 177,
      2,   2,  64,  44,  44,  44,  44,  44,  43,  43,  61,  44,  44,  44,  44,  44,
     43,  43,  43,  61,   2,   2,  67,  67,  40,  40,  95,  44,  44,  44,  44,  44,
      7,   7,   7,   7,   7, 175,  27,  27,  27,  81,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  44,  44,  81,  36,  92,  85,  85,  85,  85,  85,  85,  85,
     85,  85,  85,  85,  85,  85,  85,  85,  85,  85,  85,  85,  85,  85,  85,  89,
     43,  74,  40,  40,  40,  40,  40,  40,  82,  44,  44,  44,  44,  44,  44,  44,
     36,  62,  44,  44,  44,  44,  44,  44,  36,  44,  44,  44,  44,  44,  44,  44,
     36,  36,  36,  36,  36,  44,  50,  61,  65,  65,  44,  44,  44,  44,  44,  44,
     67,  67,  67,  91,  56,  67,  67,  67,  67,  67, 181,  86,  43,  67, 181,  85,
     85, 182,  65,  65,  65,  83,  43,  43,  43,  76,  50,  43,  43,  43,  67,  67,
     67,  67,  67,  67,  67,  43,  43,  67,  67,  67,  67,  67,  91,  44,  44,  44,
     67,  43,  76,  44,  44,  44,  44,  44,  27,  44,  44,  44,  44,  44,  44,  44,
     11,  11,  11,  11,  11,  16,  16,  16,  16,  16,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  11,  11,  16,  16,  16, 108,  16,  16,  16,  16,  16,
     11,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  47,  11,
     44,  47,  48,  47,  48,  11,  47,  11,  11,  11,  11,  16,  16,  53,  53,  16,
     16,  16,  53,  16,  16,  16,  16,  16,  16,  16,  11,  48,  11,  47,  48,  11,
     11,  11,  47,  11,  11,  11,  47,  16,  16,  16,  16,  16,  11,  48,  11,  47,
     11,  11,  47,  47,  44,  11,  11,  11,  47,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16,  16,  16,  16,  11,  11,  11,  11,  11,  16,  16,  16,  16,  16,
     16,  16,  16,  44,  11,  11,  11,  11,  31,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16,  16,  16,  33,  16,  16,  16,  11,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  31,  16,  16,  16,  16,  33,  16,  16,  16,  11,  11,
     11,  11,  31,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  33,
     16,  16,  16,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  31,
     16,  16,  16,  16,  33,  16,  16,  16,  11,  11,  11,  11,  31,  16,  16,  16,
     16,  33,  16,  16,  16,  32,  44,   7,   7,   7,   7,   7,   7,   7,   7,   7,
     43,  43,  43,  76,  67,  50,  43,  43,  43,  43,  43,  43,  43,  43,  76,  67,
     67,  67,  50,  67,  67,  67,  67,  67,  67,  67,  76,  21,   2,   2,  44,  44,
     44,  44,  44,  44,  44,  58,  43,  43,  43,  43,  43,  80,  43,  43,  43,  43,
     43,  43,  43,  43,  80,  58,  43,  43,  43,  58,  80,  43,  43,  80,  44,  44,
     36,  36,  62, 175,  27,  27,  27,  27,  43,  43,  43,  80,  44,  44,  44,  44,
     16,  16,  43,  43,  43,  80,  44,  44,  36,  36,  81,  36,  36,  36,  36,  36,
     81,  62,  62,  81,  81,  36,  36,  36,  36,  62,  36,  36,  81,  81,  44,  44,
     44,  62,  44,  81,  81,  81,  81,  36,  81,  62,  62,  81,  81,  81,  81,  81,
     81,  62,  62,  81,  36,  62,  36,  36,  36,  62,  36,  36,  81,  36,  62,  62,
     36,  36,  36,  36,  36,  81,  36,  36,  81,  36,  81,  36,  36,  81,  36,  36,
      8,  44,  44,  44,  44,  44,  44,  44,  56,  67,  67,  67,  67,  67,  67,  67,
     67,  67,  67,  67,  67,  67,  91,  44,  44,  44,  44,  67,  67,  67,  67,  67,
     67,  91,  44,  44,  44,  44,  44,  44,  67,  67,  67,  67,  67,  25,  41,  41,
     67,  67,  91,  44,  44,  44,  44,  44,  67,  67,  67,  67,  44,  44,  44,  44,
     67,  67,  67,  67,  67,  67,  67,  44,  91,  56,  67,  67,  67,  67,  67,  91,
     79,  44,  44,  44,  44,  44,  44,  44,  65,  65,  65,  65,  65,  65,  65,  65,
    166, 166, 166, 166, 166, 166, 166,  44,
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
     6,  0,  0,  5,  4,  0, 16,  6,  6,  8,  8,  8,  8,  6, 23,  4,
     0,  8,  8,  0, 11, 27, 27,  0,  5,  8, 11,  5,  0, 25, 23, 27,
     8,  5, 23, 11, 11,  0, 19,  5, 12,  5,  5, 20, 21,  0, 10, 10,
    10,  5, 19, 23,  5,  4,  7,  0,  2,  0,  2,  4,  3,  3,  3, 26,
     2, 26,  0, 26,  1, 26, 26,  0, 12, 12, 12, 16, 19, 19, 28, 29,
    20, 28, 13, 14, 16, 12, 23, 28, 29, 23, 23, 22, 22, 23, 24, 20,
    21, 23, 23, 12, 11,  4, 21,  4, 25,  0,  6,  7,  7,  6,  1, 27,
    27,  1, 27,  2,  2, 27, 10,  1,  2, 10, 10, 11, 24, 27, 27, 20,
    21, 27, 21, 24, 21, 20,  2,  6, 20, 23, 27,  4,  5, 10, 19, 20,
    21, 21, 27, 10, 19,  4, 10,  4,  6, 26, 26,  4, 27, 11,  4, 23,
     7, 23, 26,  1, 25, 27,  8, 23,  4,  8, 18, 18, 17, 17,  5, 24,
    23, 20, 19, 22, 22, 20, 22, 22, 24, 19, 24,  0, 24, 26,  0, 11,
     6, 11, 10,  0, 23, 10,  5, 11, 23, 16, 27,  8,  8, 16,
};

/* General_Category: 9926 bytes. */

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
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9, 10, 11, 12, 12, 12, 12, 13, 14, 15, 15, 15, 16,
    17, 18, 19, 20, 21, 22, 23, 22, 24, 22, 22, 22, 22, 25, 26, 26,
    26, 27, 22, 22, 22, 22, 28, 29, 22, 22, 30, 31, 32, 33, 34, 35,
    36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36, 36,
    36, 36, 36, 36, 37, 38, 39, 40, 41, 42, 22, 22, 22, 22, 22, 43,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    44, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22,
    45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45,
    45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45, 45,
    46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46,
    46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46, 46,
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
     84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  84,  85,  86,  86,  86,  86,
     86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,
     87,  87,  87,  87,  87,  87,  87,  87,  87,  88,  89,  89,  90,  91,  92,  93,
     94,  95,  96,  97,  98,  99, 100, 101, 102, 102, 102, 102, 102, 102, 102, 102,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102,
    102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 102, 103,
    104, 104, 104, 104, 104, 104, 104, 105, 106, 106, 106, 106, 106, 106, 106, 106,
    107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107, 107,
    107, 107, 108, 108, 108, 108, 109, 110, 110, 110, 110, 110, 111, 112, 113, 114,
    115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 119, 126, 126, 126, 119,
    127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 119, 119, 137, 119, 119, 119,
    138, 139, 140, 141, 142, 143, 144, 119, 145, 146, 119, 147, 148, 149, 150, 119,
    119, 151, 119, 119, 119, 152, 119, 119, 153, 154, 119, 119, 119, 119, 119, 119,
    155, 155, 155, 155, 155, 155, 155, 155, 156, 157, 158, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    159, 159, 159, 159, 159, 159, 159, 159, 160, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 161, 161, 161, 161, 161, 119, 119, 119,
    162, 162, 162, 162, 163, 164, 165, 166, 119, 119, 119, 119, 119, 119, 167, 168,
    169, 169, 169, 169, 169, 169, 169, 169, 169, 169, 169, 169, 169, 169, 169, 169,
    170, 170, 170, 170, 170, 170, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    171, 171, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 119, 119, 119, 119, 119, 119, 119, 172, 173, 119, 119, 119, 119, 119, 119,
    174, 174, 175, 175, 176, 119, 177, 119, 178, 178, 178, 178, 178, 178, 178, 178,
    179, 179, 179, 179, 179, 180, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    181, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    182, 183, 184, 119, 119, 119, 119, 119, 119, 119, 119, 119, 185, 185, 119, 119,
    186, 187, 188, 188, 189, 189, 190, 190, 190, 190, 190, 190, 191, 192, 193, 194,
    195, 195, 196, 196, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197,
    197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 197, 198, 199, 199,
    199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199,
    199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 199, 200, 201,
    202, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203,
    203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203,
    203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 203, 204, 119, 119,
    205, 205, 205, 205, 206, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    207, 119, 208, 209, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119, 119,
    210, 210, 210, 210, 210, 210, 210, 210, 210, 210, 210, 210, 210, 210, 210, 210,
    211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211, 211,
};

static RE_UINT16 re_block_stage_3[] = {
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
     60,  60,  60,  60,  60,  61,  61,  61,  62,  19,  19,  19,  63,  64,  64,  64,
     65,  65,  65,  65,  65,  65,  65,  65,  66,  66,  66,  66,  67,  67,  67,  67,
     68,  68,  68,  68,  68,  68,  68,  68,  69,  69,  69,  69,  69,  69,  69,  69,
     70,  70,  70,  70,  70,  70,  70,  71,  71,  71,  72,  72,  72,  73,  73,  73,
     74,  74,  74,  74,  74,  75,  75,  75,  75,  76,  76,  76,  76,  76,  76,  76,
     77,  77,  77,  77,  77,  77,  77,  77,  78,  78,  78,  78,  78,  78,  78,  78,
     79,  79,  79,  79,  80,  80,  81,  81,  81,  81,  81,  81,  81,  81,  81,  81,
     82,  82,  82,  82,  82,  82,  82,  82,  83,  83,  84,  84,  84,  84,  84,  84,
     85,  85,  85,  85,  85,  85,  85,  85,  86,  86,  86,  86,  86,  86,  86,  86,
     86,  86,  86,  86,  87,  87,  87,  88,  89,  89,  89,  89,  89,  89,  89,  89,
     90,  90,  90,  90,  90,  90,  90,  90,  91,  91,  91,  91,  91,  91,  91,  91,
     92,  92,  92,  92,  92,  92,  92,  92,  93,  93,  93,  93,  93,  93,  93,  93,
     94,  94,  94,  94,  94,  94,  95,  95,  96,  96,  96,  96,  96,  96,  96,  96,
     97,  97,  97,  98,  98,  98,  98,  98,  99,  99,  99,  99,  99,  99, 100, 100,
    101, 101, 101, 101, 101, 101, 101, 101, 102, 102, 102, 102, 102, 102, 102, 102,
    103, 103, 103, 103, 103, 103, 103, 103, 103, 103, 103, 103, 103, 103,  19, 104,
    105, 105, 105, 105, 106, 106, 106, 106, 106, 106, 107, 107, 107, 107, 107, 107,
    108, 108, 108, 109, 109, 109, 109, 109, 109, 110, 111, 111, 112, 112, 112, 113,
    114, 114, 114, 114, 114, 114, 114, 114, 115, 115, 115, 115, 115, 115, 115, 115,
    116, 116, 116, 116, 116, 116, 116, 116, 116, 116, 116, 116, 117, 117, 117, 117,
    118, 118, 118, 118, 118, 118, 118, 118, 119, 119, 119, 119, 119, 119, 119, 119,
    119, 120, 120, 120, 120, 121, 121, 121, 122, 122, 122, 122, 122, 122, 122, 122,
    122, 122, 122, 122, 123, 123, 123, 123, 123, 123, 124, 124, 124, 124, 124, 124,
    125, 125, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126, 126,
    127, 127, 127, 128, 129, 129, 129, 129, 130, 130, 130, 130, 130, 130, 131, 131,
    132, 132, 132, 133, 133, 133, 134, 134, 135, 135, 135, 135, 135, 135, 136, 136,
    137, 137, 137, 137, 137, 137, 138, 138, 139, 139, 139, 139, 139, 139, 140, 140,
    141, 141, 141, 142, 142, 142, 142, 143, 143, 143, 143, 143, 144, 144, 144, 144,
    145, 145, 145, 145, 145, 145, 145, 145, 145, 145, 145, 146, 146, 146, 146, 146,
    147, 147, 147, 147, 147, 147, 147, 147, 148, 148, 148, 148, 148, 148, 148, 148,
    149, 149, 149, 149, 149, 149, 149, 149, 150, 150, 150, 150, 150, 150, 150, 150,
    151, 151, 151, 151, 151, 151, 151, 151, 152, 152, 152, 152, 152, 153, 153, 153,
    153, 153, 153, 153, 153, 153, 153, 153, 154, 155, 156, 157, 157, 158, 158, 159,
    159, 159, 159, 159, 159, 159, 159, 159, 160, 160, 160, 160, 160, 160, 160, 160,
    160, 160, 160, 160, 160, 160, 160, 161, 162, 162, 162, 162, 162, 162, 162, 162,
    163, 163, 163, 163, 163, 163, 163, 163, 164, 164, 164, 164, 165, 165, 165, 165,
    165, 166, 166, 166, 166, 167, 167, 167,  19,  19,  19,  19,  19,  19,  19,  19,
    168, 168, 169, 169, 169, 169, 170, 170, 171, 171, 171, 172, 172, 173, 173, 173,
    174, 174, 175, 175, 175, 175,  19,  19, 176, 176, 176, 176, 176, 177, 177, 177,
    178, 178, 178, 179, 179, 179, 179, 179, 180, 180, 180, 181, 181, 181, 181,  19,
    182, 182, 182, 182, 182, 182, 182, 182, 183, 183, 183, 183, 184, 184, 185, 185,
    186, 186, 186,  19,  19,  19, 187, 187, 188, 188, 189, 189,  19,  19,  19,  19,
    190, 190, 191, 191, 191, 191, 191, 191, 192, 192, 192, 192, 192, 192, 193, 193,
    194, 194,  19,  19, 195, 195, 195, 195, 196, 196, 196, 196, 197, 197, 198, 198,
    199, 199, 199,  19,  19,  19,  19,  19, 200, 200, 200, 200, 200,  19,  19,  19,
    201, 201, 201, 201, 201, 201, 201, 201,  19,  19,  19,  19,  19,  19, 202, 202,
    203, 203, 203, 203, 203, 203, 203, 203, 204, 204, 204, 204, 204, 205, 205, 205,
    206, 206, 206, 206, 206, 207, 207, 207, 208, 208, 208, 208, 208, 208, 209, 209,
    210, 210, 210, 210, 210,  19,  19,  19, 211, 211, 211, 212, 212, 212, 212, 212,
    213, 213, 213, 213, 213, 213, 213, 213, 214, 214, 214, 214, 214, 214, 214, 214,
    215, 215, 215, 215, 215, 215,  19,  19, 216, 216, 216, 216, 216, 216, 216, 216,
    217, 217, 217, 217, 217, 217, 218, 218, 219, 219, 219, 219, 219,  19,  19,  19,
    220, 220, 220, 220,  19,  19,  19,  19,  19,  19, 221, 221, 221, 221, 221, 221,
     19,  19,  19,  19, 222, 222, 222, 222, 223, 223, 223, 223, 223, 223, 223, 224,
    224, 224, 224, 224,  19,  19,  19,  19, 225, 225, 225, 225, 225, 225, 225, 225,
    226, 226, 226, 226, 226, 226, 226, 226, 227, 227, 227, 227, 227, 227, 227, 227,
    227, 227, 227, 227, 227,  19,  19,  19, 228, 228, 228, 228, 228, 228, 228, 228,
    228, 228, 228,  19,  19,  19,  19,  19, 229, 229, 229, 229, 229, 229, 229, 229,
    230, 230, 230, 230, 230, 230, 230, 230, 230, 230, 230, 230, 231, 231, 231,  19,
     19,  19,  19,  19,  19, 232, 232, 232, 233, 233, 233, 233, 233, 233, 233, 233,
    233,  19,  19,  19,  19,  19,  19,  19, 234, 234, 234, 234, 234, 234, 234, 234,
    234, 234,  19,  19,  19,  19, 235, 235, 236, 236, 236, 236, 236, 236, 236, 236,
    237, 237, 237, 237, 237, 237, 237, 237, 238, 238, 238, 238, 238, 238, 238, 238,
    239, 239, 239, 239, 239, 239, 239, 239, 239, 239, 240,  19,  19,  19,  19,  19,
    241, 241, 241, 241, 241, 241, 241, 241, 242, 242, 242, 242, 242, 242, 242, 242,
    243, 243, 243, 243, 243,  19,  19,  19, 244, 244, 244, 244, 244, 244, 245, 245,
    246, 246, 246, 246, 246, 246, 246, 246, 247, 247, 247, 247, 247, 247, 247, 247,
    247, 247, 247,  19,  19,  19,  19,  19, 248, 248, 248,  19,  19,  19,  19,  19,
    249, 249, 249, 249, 249, 249, 249, 249, 249, 249, 249, 249, 249, 249,  19,  19,
    250, 250, 250, 250, 250, 250,  19,  19, 251, 251, 251, 251, 251, 251, 251, 251,
    252, 252, 252, 253, 253, 253, 253, 253, 253, 253, 254, 254, 254, 254, 254, 254,
    255, 255, 255, 255, 255, 255, 255, 255, 256, 256, 256, 256, 256, 256, 256, 256,
    257, 257, 257, 257, 257, 257, 257, 257, 258, 258, 258, 258, 258, 259, 259, 259,
    260, 260, 260, 260, 260, 260, 260, 260, 261, 261, 261, 261, 261, 261, 261, 261,
    262, 262, 262, 262, 262, 262, 262, 262, 263, 263, 263, 263, 263, 263, 263, 263,
    264, 264, 264, 264, 264, 264, 264, 264, 265, 265, 265, 265, 265, 265, 265, 265,
    265, 265, 265, 265, 265, 265,  19,  19, 266, 266, 266, 266, 266, 266, 266, 266,
    266, 266, 266, 266, 267, 267, 267, 267, 267, 267, 267, 267, 267, 267, 267, 267,
    267, 267, 268, 268, 268, 268, 268, 268, 268, 268, 268, 268, 268, 268, 268, 268,
    268, 268, 268,  19,  19,  19,  19,  19, 269, 269, 269, 269, 269, 269, 269, 269,
    269, 269,  19,  19,  19,  19,  19,  19, 270, 270, 270, 270, 270, 270, 270, 270,
    271, 271, 271, 271, 271, 271, 271, 271, 271, 271, 271, 271, 271, 271, 271,  19,
    272, 272, 272, 272, 272, 272, 272, 272, 273, 273, 273, 273, 273, 273, 273, 273,
};

static RE_UINT16 re_block_stage_4[] = {
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
    252, 252, 252, 252, 253, 253, 253, 253, 254, 254, 254, 254, 255, 255, 255, 255,
    256, 256, 256, 256, 257, 257, 257, 257, 258, 258, 258, 258, 259, 259, 259, 259,
    260, 260, 260, 260, 261, 261, 261, 261, 262, 262, 262, 262, 263, 263, 263, 263,
    264, 264, 264, 264, 265, 265, 265, 265, 266, 266, 266, 266, 267, 267, 267, 267,
    268, 268, 268, 268, 269, 269, 269, 269, 270, 270, 270, 270, 271, 271, 271, 271,
    272, 272, 272, 272, 273, 273, 273, 273,
};

static RE_UINT16 re_block_stage_5[] = {
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
    252, 252, 252, 252, 253, 253, 253, 253, 254, 254, 254, 254, 255, 255, 255, 255,
    256, 256, 256, 256, 257, 257, 257, 257, 258, 258, 258, 258, 259, 259, 259, 259,
    260, 260, 260, 260, 261, 261, 261, 261, 262, 262, 262, 262, 263, 263, 263, 263,
    264, 264, 264, 264, 265, 265, 265, 265, 266, 266, 266, 266, 267, 267, 267, 267,
    268, 268, 268, 268, 269, 269, 269, 269, 270, 270, 270, 270, 271, 271, 271, 271,
    272, 272, 272, 272, 273, 273, 273, 273,
};

/* Block: 9072 bytes. */

RE_UINT32 re_get_block(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 11;
    code = ch ^ (f << 11);
    pos = (RE_UINT32)re_block_stage_1[f] << 4;
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
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11, 12, 12, 12, 12, 13, 14, 14, 14, 14, 15,
    16, 17, 18, 19, 20, 14, 21, 14, 22, 14, 14, 14, 14, 23, 24, 24,
    25, 26, 14, 14, 14, 14, 27, 28, 14, 14, 29, 30, 31, 32, 33, 34,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 35,  7, 36, 37,  7, 38, 14, 14, 14, 14, 14, 39,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    40, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14,
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
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  80,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  81,
     82,  82,  82,  82,  82,  82,  82,  82,  82,  83,  84,  84,  85,  86,  87,  88,
     89,  90,  91,  92,  93,  94,  95,  96,  32,  32,  32,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,
     32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  32,  97,
     98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  71,  71,  99, 100, 101, 102, 103, 103, 104, 105, 106, 107, 108, 109,
    110, 111, 112, 113,  98, 114, 115, 116, 117, 118, 119,  98, 120, 120, 121,  98,
    122, 123, 124, 125, 126, 127, 128, 129, 130, 131,  98,  98, 132,  98,  98,  98,
    133, 134, 135, 136, 137, 138, 139,  98, 140, 141,  98, 142, 143, 144, 145,  98,
     98, 146,  98,  98,  98, 147,  98,  98, 148, 149,  98,  98,  98,  98,  98,  98,
    150, 150, 150, 150, 150, 150, 150, 151, 152, 150, 153,  98,  98,  98,  98,  98,
    154, 154, 154, 154, 154, 154, 154, 154, 155,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98, 156, 156, 156, 156, 157,  98,  98,  98,
    158, 158, 158, 158, 159, 160, 161, 162,  98,  98,  98,  98,  98,  98, 163, 164,
    165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165,
    165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 165, 166,
    165, 165, 165, 165, 165, 167,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    168,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  98, 169, 170,  98,  98,  98,  98,  98,  98,
     59, 171, 172, 173, 174,  98, 175,  98, 176, 177, 178,  59,  59, 179,  59, 180,
    181, 181, 181, 181, 181, 182,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    183,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    184, 185, 186,  98,  98,  98,  98,  98,  98,  98,  98,  98, 187, 188,  98,  98,
    189, 190, 191, 192, 193,  98,  59,  59,  59,  59,  59,  59,  59, 194, 195, 196,
    197, 198, 199, 200,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71, 201,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71, 202,  71,
    203,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,
     71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71,  71, 204,  98,  98,
     71,  71,  71,  71, 205,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
    206,  98, 207, 208,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,
};

static RE_UINT16 re_script_stage_3[] = {
      0,   0,   0,   0,   1,   2,   1,   2,   0,   0,   3,   3,   4,   5,   4,   5,
      4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   6,   0,   0,   7,   0,
      8,   8,   8,   8,   8,   8,   8,   9,  10,  11,  12,  11,  11,  11,  13,  11,
     14,  14,  14,  14,  14,  14,  14,  14,  15,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  16,  17,  18,  16,  17,  19,  20,  21,  21,  22,  21,  23,  24,
     25,  26,  27,  27,  28,  29,  27,  30,  27,  27,  27,  27,  27,  31,  27,  27,
     32,  33,  33,  33,  34,  27,  27,  27,  35,  35,  35,  36,  37,  37,  37,  38,
     39,  39,  40,  41,  42,  43,  44,  44,  44,  44,  27,  45,  44,  46,  47,  27,
     48,  48,  48,  48,  48,  49,  50,  48,  51,  52,  53,  54,  55,  56,  57,  58,
     59,  60,  61,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,
     75,  76,  77,  78,  79,  80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,
     91,  92,  93,  94,  95,  96,  97,  98,  99, 100, 101, 102, 103, 104, 105, 106,
    107, 108, 109, 110, 111, 112, 113, 109, 114, 115, 116, 117, 118, 119, 120, 121,
    122, 123, 123, 124, 123, 125,  44,  44, 126, 127, 128, 129, 130, 131,  44,  44,
    132, 132, 132, 132, 133, 132, 134, 135, 132, 133, 132, 136, 136, 137,  44,  44,
    138, 138, 138, 138, 138, 138, 138, 138, 138, 138, 139, 139, 140, 139, 139, 141,
    142, 142, 142, 142, 142, 142, 142, 142, 143, 143, 143, 143, 144, 145, 143, 143,
    144, 143, 143, 146, 147, 148, 143, 143, 143, 147, 143, 143, 143, 149, 143, 150,
    143, 151, 152, 152, 152, 152, 152, 153, 154, 154, 154, 154, 154, 154, 154, 154,
    155, 156, 157, 157, 157, 157, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167,
    168, 168, 168, 168, 168, 169, 170, 170, 171, 172, 173, 173, 173, 173, 173, 174,
    173, 173, 175, 154, 154, 154, 154, 176, 177, 178, 179, 179, 180, 181, 182, 183,
    184, 184, 185, 184, 186, 187, 168, 168, 188, 189, 190, 190, 190, 191, 190, 192,
    193, 193, 194, 195,  44,  44,  44,  44, 196, 196, 196, 196, 197, 196, 196, 198,
    199, 199, 199, 199, 200, 200, 200, 201, 202, 202, 202, 203, 204, 205, 205, 205,
    206,  44,  44,  44, 207, 208, 209, 210,   4,   4, 211,   4,   4, 212, 213, 214,
      4,   4,   4, 215,   8,   8,   8, 216,  11, 217,  11,  11, 217, 218,  11, 219,
     11,  11,  11, 220, 220, 221,  11, 222, 223,   0,   0,   0,   0,   0, 224, 225,
    226, 227,   0, 226,  44,   8,   8, 228,   0,   0, 229, 230, 231,   0,   4,   4,
    232,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 226,   0,   0, 233,  44, 234,  44,   0,   0,
    235, 235, 235, 235, 235, 235, 235, 235,   0,   0,   0,   0,   0,   0,   0, 236,
      0, 237,   0, 238, 239, 240, 241,  44, 242, 242, 243, 242, 242, 243,   4,   4,
    244, 244, 244, 244, 244, 244, 244, 245, 139, 139, 140, 246, 246, 246, 247, 248,
    143, 249, 250, 250, 250, 250,  14,  14,   0,   0,   0,   0, 251,  44,  44,  44,
    252, 253, 252, 252, 252, 252, 252, 254, 252, 252, 252, 252, 252, 252, 252, 252,
    252, 252, 252, 252, 252, 255,  44, 256, 257,   0, 258, 259, 260, 261, 261, 261,
    261, 262, 263, 264, 264, 264, 264, 265, 266, 267, 268, 269, 142, 142, 142, 142,
    270,   0, 267, 271,   0,   0, 272, 264, 142, 270,   0,   0,   0,   0, 142, 273,
      0,   0,   0,   0,   0, 264, 264, 274, 264, 264, 264, 264, 264, 275,   0,   0,
    252, 252, 252, 255,   0,   0,   0,   0, 252, 252, 252, 252, 252, 255,  44,  44,
    276, 276, 276, 276, 276, 276, 276, 276, 277, 276, 276, 276, 278, 279, 279, 279,
    280, 280, 280, 280, 280, 280, 280, 280, 280, 280, 281,  44,  14,  14,  14,  14,
     14,  14, 282, 282, 282, 282, 282, 283,   0,   0, 284,   4,   4,   4,   4,   4,
    285,   4, 286, 287,  44,  44,  44, 288, 289, 289, 290, 291, 292, 292, 292, 293,
    294, 294, 294, 294, 295, 296,  48, 297, 298, 298, 299, 300, 300, 301, 142, 302,
    303, 303, 303, 303, 304, 305, 138, 306, 307, 307, 307, 308, 309, 310, 138, 138,
    311, 311, 311, 311, 312, 313, 314, 315, 316, 317, 250,   4,   4, 318, 319, 152,
    152, 152, 152, 152, 314, 314, 320, 321, 142, 142, 322, 142, 323, 142, 142, 324,
     44,  44,  44,  44,  44,  44,  44,  44, 252, 252, 252, 252, 252, 252, 325, 252,
    252, 252, 252, 252, 252, 326,  44,  44, 327, 328,  21, 329, 330,  27,  27,  27,
     27,  27,  27,  27, 331, 332,  27,  27,  27,  27,  27,  27,  27,  27,  27,  27,
     27,  27,  27, 333,  44,  27,  27,  27,  27, 334,  27,  27, 335,  44,  44, 336,
      8, 291, 337,   0,   0, 338, 339, 340,  27,  27,  27,  27,  27,  27,  27, 341,
    342,   0,   1,   2,   1,   2, 343, 263, 264, 344, 142, 270, 345, 346, 347, 348,
    349, 350, 351, 352, 353, 353,  44,  44, 350, 350, 350, 350, 350, 350, 350, 354,
    355,   0,   0, 356,  11,  11,  11,  11, 357, 256, 358,  44,  44,   0,   0, 359,
    360, 361, 362, 362, 362, 363, 364, 256, 365, 365, 366, 367, 368, 369, 369, 370,
    371, 372, 373, 373, 374, 375,  44,  44, 376, 376, 376, 376, 376, 377, 377, 377,
    378, 379, 380, 381, 381, 382, 381, 383, 384, 384, 385, 386, 386, 386, 387,  44,
    388, 388, 388, 388, 388, 388, 388, 388, 388, 388, 388, 389, 388, 390, 391,  44,
    392, 393, 393, 394, 395, 396, 397, 397, 398, 399, 400,  44,  44,  44, 401, 402,
    403, 404, 405, 406,  44,  44,  44,  44, 407, 407, 408, 409, 408, 410, 408, 408,
    411, 412, 413, 414, 415, 416, 417, 417, 418, 418,  44,  44, 419, 419, 420, 421,
    422, 422, 422, 423, 424, 425, 426, 427, 428, 429, 430,  44,  44,  44,  44,  44,
    431, 431, 431, 431, 432,  44,  44,  44, 433, 433, 433, 434, 433, 433, 433, 435,
     44,  44,  44,  44,  44,  44,  27, 436, 437, 437, 437, 437, 438, 439, 437, 440,
    441, 441, 441, 441, 442, 443, 444, 445, 446, 446, 446, 447, 448, 449, 449, 450,
    451, 451, 451, 451, 452, 451, 453, 454, 455, 456, 455, 457,  44,  44,  44,  44,
    458, 459, 460, 461, 461, 461, 462, 463, 464, 465, 466, 467, 468, 469, 470, 471,
    472, 472, 472, 472, 472, 473,  44,  44, 474, 474, 474, 474, 475, 476,  44,  44,
    477, 477, 477, 478, 477, 479,  44,  44, 480, 480, 480, 480, 481, 482, 483,  44,
    484, 484, 484, 485, 486,  44,  44,  44, 487, 488, 489, 487,  44,  44,  44,  44,
     44,  44, 490, 490, 490, 490, 490, 491,  44,  44,  44,  44, 492, 492, 492, 493,
    494, 495, 495, 496, 497, 495, 498, 499, 499, 500, 501, 502,  44,  44,  44,  44,
    503, 503, 503, 503, 503, 503, 503, 503, 503, 504,  44,  44,  44,  44,  44,  44,
    503, 503, 503, 503, 503, 503, 505, 506, 503, 503, 503, 503, 507,  44,  44,  44,
    508, 508, 508, 508, 508, 508, 508, 508, 508, 508, 509,  44,  44,  44,  44,  44,
    510, 510, 510, 510, 510, 510, 510, 510, 510, 510, 510, 510, 511,  44,  44,  44,
    282, 282, 282, 282, 282, 282, 282, 282, 282, 282, 282, 512, 513, 514, 515,  44,
     44,  44,  44,  44,  44, 516, 517, 518, 519, 519, 519, 519, 520, 521, 522, 523,
    519,  44,  44,  44,  44,  44,  44,  44, 524, 524, 524, 524, 525, 524, 524, 526,
    527, 524,  44,  44,  44,  44, 528,  44, 529, 529, 529, 529, 529, 529, 529, 529,
    529, 529, 529, 529, 529, 529, 530,  44, 529, 529, 529, 529, 529, 529, 529, 531,
    532,  44,  44,  44,  44,  44,  44,  44, 533, 533, 533, 533, 533, 533, 534, 535,
    536, 537, 272,  44,  44,  44,  44,  44,   0,   0,   0,   0,   0,   0,   0, 538,
      0,   0, 539,   0,   0,   0, 540, 541, 542,   0, 543,   0,   0,   0, 544,  44,
     11,  11,  11,  11, 545,  44,  44,  44,   0,   0,   0,   0,   0, 233,   0, 240,
      0,   0,   0,   0,   0, 224,   0,   0,   0, 546, 547, 548, 549,   0,   0,   0,
    550, 551,   0, 552, 553, 554,   0,   0,   0,   0, 237,   0,   0,   0,   0,   0,
      0,   0,   0,   0, 555,   0,   0,   0, 556, 556, 556, 556, 556, 556, 556, 556,
    557, 558, 559,  44,  44,  44,  44,  44, 560, 561, 562,  44,  44,  44,  44,  44,
    563, 563, 563, 563, 563, 563, 563, 563, 563, 563, 563, 563, 564, 565,  44,  44,
    566, 566, 566, 566, 567, 568,  44,  44, 569,  27, 570, 571, 572, 573, 574, 575,
    576, 577, 578, 577,  44,  44,  44, 331,   0,   0, 256,   0,   0,   0,   0,   0,
      0, 272, 226, 342, 342, 342,   0, 538, 579,   0, 226,   0,   0,   0, 256,   0,
      0,   0, 579,  44,  44,  44, 580,   0, 581,   0,   0, 256, 544, 240,  44,  44,
      0,   0,   0,   0,   0, 582, 579, 233,   0,   0,   0,   0,   0,   0,   0, 272,
      0,   0,   0,   0,   0, 251,  44,  44, 256,   0,   0,   0, 583, 291,   0,   0,
    583,   0, 584,  44,  44,  44,  44,  44,  44, 226, 583, 585, 256, 226,  44,  44,
      0, 240,  44,  44, 586,  44,  44,  44, 252, 252, 252, 252, 252, 587,  44,  44,
    252, 252, 252, 588, 252, 252, 252, 252, 252, 325, 252, 252, 252, 252, 252, 252,
    252, 252, 589,  44,  44,  44,  44,  44, 252, 325,  44,  44,  44,  44,  44,  44,
    590,  44,   0,   0,   0,   0,   0,   0,   8,   8,   8,   8,   8,   8,   8,   8,
      8,   8,   8,   8,   8,   8,   8,  44,
};

static RE_UINT16 re_script_stage_4[] = {
      0,   0,   0,   0,   1,   2,   2,   2,   2,   2,   3,   0,   0,   0,   4,   0,
      2,   2,   2,   2,   2,   3,   2,   2,   2,   2,   5,   0,   2,   5,   6,   0,
      7,   7,   7,   7,   8,   9,  10,  11,  12,  13,  14,  15,   8,   8,   8,   8,
     16,   8,   8,   8,  17,  18,  18,  18,  19,  19,  19,  19,  19,  20,  19,  19,
     21,  22,  22,  22,  22,  22,  22,  22,  22,  23,  21,  22,  22,  22,  24,  21,
     25,  26,  26,  26,  26,  26,  26,  26,  26,  26,  12,  12,  26,  26,  27,  12,
     26,  28,  12,  12,  29,  30,  29,  31,  29,  29,  32,  33,  29,  29,  29,  29,
     31,  29,  34,   7,   7,  35,  29,  29,  36,  29,  29,  29,  29,  29,  29,  30,
     37,  37,  37,  38,  37,  37,  37,  37,  37,  37,  39,  40,  41,  41,  41,  41,
     42,  12,  12,  12,  43,  43,  43,  43,  43,  43,  44,  12,  45,  45,  45,  45,
     45,  45,  45,  46,  45,  45,  45,  47,  48,  48,  48,  48,  48,  48,  48,  49,
     12,  12,  12,  12,  29,  50,  29,  51,  12,  29,  29,  29,  52,  29,  29,  29,
     53,  53,  53,  53,  54,  53,  53,  53,  53,  55,  53,  53,  56,  57,  56,  58,
     58,  56,  56,  56,  56,  56,  59,  56,  60,  61,  62,  56,  56,  58,  58,  63,
     12,  64,  12,  65,  56,  61,  56,  56,  56,  56,  56,  12,  66,  66,  67,  68,
     69,  70,  70,  70,  70,  70,  71,  70,  71,  72,  73,  71,  67,  68,  69,  73,
     74,  12,  66,  75,  12,  76,  70,  70,  70,  73,  12,  12,  77,  77,  78,  79,
     79,  78,  78,  78,  78,  78,  80,  78,  80,  77,  81,  78,  78,  79,  79,  81,
     82,  12,  12,  12,  78,  83,  78,  78,  81,  12,  84,  12,  85,  85,  86,  87,
     87,  86,  86,  86,  86,  86,  88,  86,  88,  85,  89,  86,  86,  87,  87,  89,
     12,  90,  12,  91,  86,  90,  86,  86,  86,  86,  12,  12,  92,  93,  94,  92,
     95,  96,  97,  95,  98,  99,  94,  92, 100, 100,  96,  92,  94,  92,  95,  96,
     99,  98,  12,  12,  12,  92, 100, 100, 100, 100,  94,  12, 101, 102, 101, 103,
    103, 101, 101, 101, 101, 101, 103, 101, 101, 101, 104, 102, 101, 103, 103, 104,
     12, 105, 106,  12, 101, 107, 101, 101,  12,  12, 101, 101, 108, 109, 108, 110,
    110, 108, 108, 108, 108, 108, 110, 108, 108, 109, 111, 108, 108, 110, 110, 111,
     12, 112,  12, 113, 108, 114, 108, 108, 112,  12,  12,  12, 115, 115, 116, 117,
    117, 116, 116, 116, 116, 116, 116, 116, 116, 116, 118, 115, 116, 117, 117, 116,
     12, 116, 116, 116, 116, 119, 116, 116, 120, 121, 122, 122, 122, 123, 120, 122,
    122, 122, 122, 122, 124, 122, 122, 125, 122, 123, 126, 127, 122, 128, 122, 122,
     12, 120, 122, 122, 120, 129,  12,  12, 130, 131, 131, 131, 131, 131, 131, 131,
    131, 131, 132, 133, 131, 131, 131,  12, 134, 135, 136, 137,  12, 138, 139, 138,
    139, 140, 141, 139, 138, 138, 142, 143, 138, 136, 138, 143, 138, 138, 143, 138,
    144, 144, 144, 144, 144, 144, 145, 144, 144, 144, 144, 146, 145, 144, 144, 144,
    144, 144, 144, 147, 144, 148, 149,  12, 150, 150, 150, 150, 151, 151, 151, 151,
    151, 152,  12, 153, 151, 151, 154, 151, 155, 155, 155, 155, 156, 156, 156, 156,
    156, 156, 157, 158, 156, 159, 157, 158, 157, 158, 156, 159, 157, 158, 156, 156,
    156, 159, 156, 156, 156, 156, 159, 160, 156, 156, 156, 161, 156, 156, 158,  12,
    162, 162, 162, 162, 162, 163, 162, 163, 164, 164, 164, 164, 165, 165, 165, 165,
    165, 165, 165, 166, 167, 167, 167, 167, 167, 167, 168, 169, 167, 167, 170,  12,
    171, 171, 171, 172, 171, 173,  12,  12, 174, 174, 174, 174, 174, 175,  12,  12,
    176, 176, 176, 176, 176,  12,  12,  12, 177, 177, 177, 178, 178,  12,  12,  12,
    179, 179, 179, 179, 179, 179, 179, 180, 179, 179, 180,  12, 181, 182, 183, 184,
    183, 183, 185,  12, 183, 183, 183, 183, 183, 183,  12,  12, 183, 183, 184,  12,
    164, 186,  12,  12, 187, 187, 187, 187, 187, 187, 187, 188, 187, 187, 187,  12,
    189, 187, 187, 187, 190, 190, 190, 190, 190, 190, 190, 191, 190, 192,  12,  12,
    193, 193, 193, 193, 193, 193, 193,  12, 193, 193, 194,  12, 193, 193, 195, 196,
    197, 197, 197, 197, 197, 197, 197, 198, 199, 199, 199, 199, 199, 199, 199, 200,
    199, 199, 199, 201, 199, 199, 202,  12, 199, 199, 199, 202,   7,   7,   7, 203,
    204, 204, 204, 204, 204, 204, 204,  12, 204, 204, 204, 205, 206, 206, 206, 206,
    207, 207, 207, 207, 207,  12,  12, 207, 208, 208, 208, 208, 208, 208, 209, 208,
    208, 208, 210, 211, 212, 212, 212, 212,  19,  19, 213,  12, 206, 206,  12,  12,
    214,   7,   7,   7, 215,   7, 216, 217,   0, 218, 219,  12,   2, 220, 221,   2,
      2,   2,   2, 222, 223, 220, 224,   2,   2,   2, 225,   2,   2,   2,   2, 226,
      7, 219, 227,   7,   8, 228,   8, 228,   8,   8, 229, 229,   8,   8,   8, 228,
      8,  15,   8,   8,   8,  10,   8, 230,  10,  15,   8,  14,   0,   0,   0, 231,
      0, 232,   0,   0, 233,   0,   0, 234,   0,   0,   0, 235,   2,   2,   2, 236,
    237,  12,  12,  12,   0, 238, 239,   0,   4,   0,   0,   0,   0,   0,   0,   4,
      2,   2,   5,  12,   0, 235,  12,  12,   0,   0, 235,  12, 240, 240, 240, 240,
      0, 241,   0,   0,   0, 242,   0,   0,   0,   0, 242, 243,   0,   0, 232,   0,
    242,  12,  12,  12,  12,  12,  12,   0, 244, 244, 244, 244, 244, 244, 244, 245,
     18,  18,  18,  18,  18,  12, 246,  18, 247, 247, 247, 247, 247, 247,  12, 248,
    249,  12,  12, 248, 156, 159,  12,  12, 156, 159, 156, 159,   0, 250,  12,  12,
    251, 251, 251, 251, 251, 251, 252, 251, 251,  12,  12,  12, 251, 253,  12,  12,
      0,   0,   0,  12,   0, 254,   0,   0, 255, 251, 256, 257,   0,   0, 251,   0,
    258, 259, 259, 259, 259, 259, 259, 259, 259, 260, 261, 262, 263, 264, 264, 264,
    264, 264, 264, 264, 264, 264, 265, 263,  12, 266, 267, 267, 267, 267, 267, 267,
    267, 267, 267, 268, 269, 155, 155, 155, 155, 155, 155, 270, 267, 267, 271,  12,
      0,  12,  12,  12, 155, 155, 155, 272, 264, 264, 264, 273, 264, 264,   0,   0,
    274, 274, 274, 274, 274, 274, 274, 275, 274, 276,  12,  12, 277, 277, 277, 277,
    278, 278, 278, 278, 278, 278, 278,  12, 279, 279, 279, 279, 279, 279,  12,  12,
    239,   2,   2,   2,   2,   2, 234,   2,   2,   2,   2, 280,   2,   2,  12,  12,
     12, 281,   2,   2, 282, 282, 282, 282, 282, 282, 282,  12,   0,   0, 242,  12,
    283, 283, 283, 283, 283, 283,  12,  12, 284, 284, 284, 284, 284, 285,  12, 286,
    284, 284, 285,  12,  53,  53,  53, 287, 288, 288, 288, 288, 288, 288, 288, 289,
    290, 290, 290, 290, 290,  12,  12, 291, 155, 155, 155, 292, 293, 293, 293, 293,
    293, 293, 293, 294, 293, 293, 295, 296, 150, 150, 150, 297, 298, 298, 298, 298,
    298, 299,  12,  12, 298, 298, 298, 300, 298, 298, 300, 298, 301, 301, 301, 301,
    302,  12,  12,  12,  12,  12, 303, 301, 304, 304, 304, 304, 304, 305,  12,  12,
    160, 159, 160, 159, 160, 159,  12,  12,   2,   2,   3,   2,   2, 306,  12,  12,
    304, 304, 304, 307, 304, 304, 307,  12, 155,  12,  12,  12, 155, 270, 308, 155,
    155, 155, 155,  12, 251, 251, 251, 253, 251, 251, 253,  12,   2, 280,  12,  12,
    309,  22,  12,  25,  26,  27,  26, 310, 311, 312,  26,  26,  51,  12,  12,  12,
    313,  29,  29,  29,  29,  29,  29, 314, 315,  29,  29,  29,  29,  29,  12,  12,
     29,  29,  29,  51,   7,   7,   7, 316, 235,   0,   0,   0,   0, 235,   0,  12,
     29,  50,  29,  29,  29,  29,  29, 317, 243,   0,   0,   0,   0, 318, 264, 264,
    264, 264, 264, 319, 320, 155, 320, 155, 320, 155, 320, 292,   0, 235,   0, 235,
     12,  12, 243, 242, 321, 321, 321, 322, 321, 321, 321, 321, 321, 323, 321, 321,
    321, 321, 323, 324, 321, 321, 321, 325, 321, 321, 323,  12, 235, 133,   0,   0,
      0, 133,   0,   0,   8,   8,   8,  14, 326,  12,  12,  12,   0,   0,   0, 327,
    328, 328, 328, 328, 328, 328, 328, 329, 330, 330, 330, 330, 331,  12,  12,  12,
    216,   0,   0,   0, 332, 332, 332, 332, 332,  12,  12,  12, 333, 333, 333, 333,
    333, 333, 334,  12, 335, 335, 335, 335, 335, 335, 336,  12, 337, 337, 337, 337,
    337, 337, 337, 338, 339, 339, 339, 339, 339,  12, 339, 339, 339, 340,  12,  12,
    341, 341, 341, 341, 342, 342, 342, 342, 343, 343, 343, 343, 343, 343, 343, 344,
    343, 343, 344,  12, 345, 345, 345, 345, 345,  12, 345, 345, 345, 345, 345,  12,
    346, 346, 346, 346, 346, 346,  12,  12, 347, 347, 347, 347, 347,  12,  12, 348,
    349, 349, 349, 349, 349, 350,  12,  12, 349, 351,  12,  12, 349, 349,  12,  12,
    352, 353, 354, 352, 352, 352, 352, 352, 352, 355, 356, 357, 358, 358, 358, 358,
    358, 359, 358, 358, 360, 360, 360, 360, 361, 361, 361, 361, 361, 361, 361, 362,
     12, 363, 361, 361, 364, 364, 364, 364, 365, 366, 367, 364, 368, 368, 368, 368,
    368, 368, 368, 369, 370, 370, 370, 370, 370, 370, 371, 372, 373, 373, 373, 373,
    374, 374, 374, 374, 374, 374,  12, 374, 375, 374, 374, 374, 376, 377,  12, 376,
    376, 378, 378, 376, 376, 376, 376, 376, 376,  12, 379, 380, 376, 376,  12,  12,
    376, 376, 381,  12, 382, 382, 382, 382, 383, 383, 383, 383, 384, 384, 384, 384,
    384, 385, 386, 384, 384, 385,  12,  12, 387, 387, 387, 387, 387, 388, 389, 387,
    390, 390, 390, 390, 390, 391, 390, 390, 392, 392, 392, 392, 393,  12, 392, 392,
    394, 394, 394, 394, 395,  12, 396, 397,  12,  12, 396, 394, 398, 398, 398, 398,
    398, 398, 399,  12, 400, 400, 400, 400, 401,  12,  12,  12, 401,  12, 402, 400,
     29,  29,  29, 403, 404, 404, 404, 404, 404, 404, 404, 405, 406, 404, 404, 404,
     12,  12,  12, 407, 408, 408, 408, 408, 409,  12,  12,  12, 410, 410, 410, 410,
    410, 410, 411,  12, 410, 410, 412,  12, 413, 413, 413, 413, 413, 414, 413, 413,
    413,  12,  12,  12, 415, 415, 415, 415, 415, 416,  12,  12, 417, 417, 417, 417,
    417, 417, 417, 418, 121, 122, 122, 122, 122, 129,  12,  12, 419, 419, 419, 419,
    420, 419, 419, 419, 419, 419, 419, 421, 422, 423, 424, 425, 422, 422, 422, 425,
    422, 422, 426,  12, 427, 427, 427, 427, 427, 427, 428,  12, 427, 427, 429,  12,
    430, 431, 430, 432, 432, 430, 430, 430, 430, 430, 433, 430, 433, 431, 434, 430,
    430, 432, 432, 434, 435, 436,  12, 431, 430, 437, 430, 435, 430, 435,  12,  12,
    438, 438, 438, 438, 438, 438, 439, 440, 441, 441, 441, 441, 441, 441,  12,  12,
    441, 441, 442,  12, 443, 443, 443, 443, 443, 444, 443, 443, 443, 443, 443, 444,
    445, 445, 445, 445, 445, 446,  12,  12, 445, 445, 447,  12, 183, 183, 183, 448,
    449, 449, 449, 449, 449, 449,  12,  12, 449, 449, 450,  12, 451, 451, 451, 451,
    451, 451, 452, 453, 451, 451, 451,  12, 454, 454, 454, 454, 455,  12,  12, 456,
    457, 457, 457, 457, 457, 457, 458,  12, 459, 459, 460, 459, 459, 459, 459, 459,
    459, 461, 459, 459, 459, 462,  12,  12, 459, 459, 459, 463, 464, 464, 464, 464,
    465, 464, 464, 464, 464, 464, 466, 464, 464, 467,  12,  12, 468, 468, 468, 468,
    468, 468, 469,  12, 468, 468, 468, 470, 468, 471,  12,  12, 468,  12,  12,  12,
    472, 472, 472, 472, 472, 472, 472, 473, 474, 474, 474, 474, 474, 475,  12,  12,
    279, 279, 476,  12, 477, 477, 477, 477, 477, 477, 477, 478, 477, 477, 479, 480,
    481, 481, 481, 481, 481, 481, 481, 482, 481, 482,  12,  12, 483, 483, 483, 483,
    483, 484,  12,  12, 483, 483, 485, 483, 485, 483, 483, 483, 483, 483,  12, 486,
    487, 487, 487, 487, 487, 488,  12,  12, 487, 487, 487, 489,  12,  12,  12, 490,
    491,  12,  12,  12, 492, 492, 492, 492, 492, 492, 492, 491, 493,  12,  12,  12,
    494,  12,  12,  12, 495, 495, 495, 495, 495, 495, 496,  12, 495, 495, 495, 497,
    495, 495, 497,  12, 495, 495, 498, 495,   0, 242,  12,  12,   0, 235, 243,   0,
      0, 499, 231,   0,   0,   0, 499,   7, 214, 500,   7,   0,   0,   0, 501, 231,
      0,   0, 250,  12,   8, 228,  12,  12,   0,   0,   0, 232, 502, 503, 243, 232,
      0,   0, 504, 243,   0, 243,   0,   0,   0, 504, 235, 243,   0, 232,   0, 232,
      0,   0, 504, 235,   0, 505, 241,   0, 232,   0,   0,   0,   0,   0,   0, 241,
    506, 506, 506, 506, 506, 506, 506,  12,  12,  12, 507, 506, 508, 506, 506, 506,
    244, 245, 244, 244, 244, 244, 509, 244, 510, 511, 245,  12, 512, 512, 512, 512,
    512, 513, 512, 512, 512, 514,  12,  12, 515, 515, 515, 515, 515, 515, 516,  12,
    515, 515, 517, 518,  29, 519,  29,  29, 520, 521, 519,  29, 403,  29, 522,  12,
    523, 313, 522, 519, 520, 521, 522, 522, 520, 521, 403,  29, 403,  29, 519, 524,
     29,  29, 525,  29,  29,  29,  29,  12, 519, 519, 525,  29,   0,   0,   0, 250,
     12, 241,   0,   0, 526,  12,  12,  12, 235,  12,  12,  12,   0,   0,  12,  12,
      0,   0,   0, 242, 527,   0,   0, 235, 250,  12,  12,  12, 251, 528,  12,  12,
    251, 529,  12,  12, 253,  12,  12,  12, 530,  12,  12,  12,
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
     41,   7,   7,   7,   8,   8,   8,   8,   8,   8,   0,   8,   8,   8,   8,   0,
      0,   8,   8,   8,   9,   9,   9,   9,   9,   9,   0,   0,  66,  66,  66,  66,
     66,  66,  66,   0,  82,  82,  82,  82,  82,  82,   0,   0,  82,  82,  82,   0,
     95,  95,  95,  95,   0,   0,  95,   0,   7,   0,   7,   7,   7,   7,   0,   0,
      7,   7,   1,   7,  10,  10,  10,  10,  10,  41,  41,  10,   1,   1,  10,  10,
     11,  11,  11,  11,   0,  11,  11,  11,  11,   0,   0,  11,  11,   0,  11,  11,
     11,   0,  11,   0,   0,   0,  11,  11,  11,  11,   0,   0,  11,  11,  11,   0,
      0,   0,   0,  11,  11,  11,   0,  11,   0,  12,  12,  12,  12,  12,  12,   0,
      0,   0,   0,  12,  12,   0,   0,  12,  12,  12,  12,  12,  12,   0,  12,  12,
      0,  12,  12,   0,  12,  12,   0,   0,   0,  12,   0,   0,  12,   0,  12,   0,
      0,   0,  12,  12,   0,  13,  13,  13,  13,  13,  13,  13,  13,  13,   0,  13,
     13,   0,  13,  13,  13,  13,   0,   0,  13,   0,   0,   0,   0,   0,  13,  13,
      0,  13,   0,   0,   0,  14,  14,  14,  14,  14,  14,  14,  14,   0,   0,  14,
     14,   0,  14,  14,  14,  14,   0,   0,   0,   0,  14,  14,  14,  14,   0,  14,
      0,   0,  15,  15,   0,  15,  15,  15,  15,  15,  15,   0,  15,   0,  15,  15,
     15,  15,   0,   0,   0,  15,  15,   0,   0,   0,   0,  15,  15,   0,   0,   0,
     15,  15,  15,  15,  16,  16,  16,  16,   0,  16,  16,  16,  16,   0,  16,  16,
     16,  16,   0,   0,   0,  16,  16,   0,  16,  16,  16,   0,   0,   0,  16,  16,
     17,  17,  17,  17,   0,  17,  17,  17,  17,   0,  17,  17,  17,  17,   0,   0,
      0,  17,  17,   0,   0,   0,  17,   0,   0,   0,  17,  17,   0,  18,  18,  18,
     18,  18,  18,  18,  18,   0,  18,  18,  18,  18,  18,   0,   0,   0,  18,  18,
      0,   0,  19,  19,   0,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,   0,
     19,  19,   0,  19,   0,  19,   0,   0,   0,   0,  19,   0,   0,   0,   0,  19,
     19,   0,  19,   0,  19,   0,   0,   0,   0,  20,  20,  20,  20,  20,  20,  20,
     20,  20,  20,   0,   0,   0,   0,   1,   0,  21,  21,   0,  21,   0,   0,  21,
     21,   0,  21,   0,   0,  21,   0,   0,  21,  21,  21,  21,   0,  21,  21,  21,
      0,  21,   0,  21,   0,   0,  21,  21,  21,  21,   0,  21,  21,  21,   0,   0,
     22,  22,  22,  22,   0,  22,  22,  22,  22,   0,   0,   0,  22,   0,  22,  22,
     22,   1,   1,   1,   1,  22,  22,   0,  23,  23,  23,  23,  24,  24,  24,  24,
     24,  24,   0,  24,   0,  24,   0,   0,  24,  24,  24,   1,  25,  25,  25,  25,
     26,  26,  26,  26,  26,   0,  26,  26,  26,  26,   0,   0,  26,  26,  26,   0,
      0,  26,  26,  26,  26,   0,   0,   0,  27,  27,  27,  27,  27,  27,   0,   0,
     28,  28,  28,  28,  29,  29,  29,  29,  29,   0,   0,   0,  30,  30,  30,  30,
     30,  30,  30,   1,   1,   1,  30,  30,  30,   0,   0,   0,  42,  42,  42,  42,
     42,   0,  42,  42,  42,   0,   0,   0,  43,  43,  43,  43,  43,   1,   1,   0,
     44,  44,  44,  44,  45,  45,  45,  45,  45,   0,  45,  45,  31,  31,  31,  31,
     31,  31,   0,   0,  32,  32,   1,   1,  32,   1,  32,  32,  32,  32,  32,  32,
     32,  32,  32,   0,  32,  32,   0,   0,  28,  28,   0,   0,  46,  46,  46,  46,
     46,  46,  46,   0,  46,   0,   0,   0,  47,  47,  47,  47,  47,  47,   0,   0,
     47,   0,   0,   0,  56,  56,  56,  56,  56,  56,   0,   0,  56,  56,  56,   0,
      0,   0,  56,  56,  54,  54,  54,  54,   0,   0,  54,  54,  78,  78,  78,  78,
     78,  78,  78,   0,  78,   0,   0,  78,  78,  78,   0,   0,  41,  41,  41,   0,
     62,  62,  62,  62,  62,   0,   0,   0,  67,  67,  67,  67,  93,  93,  93,  93,
     68,  68,  68,  68,   0,   0,   0,  68,  68,  68,   0,   0,   0,  68,  68,  68,
     69,  69,  69,  69,   4,   0,   0,   0,  41,  41,  41,   1,  41,   1,  41,  41,
     41,   1,   1,   1,   1,  41,   1,   1,  41,   1,   1,   0,  41,  41,   0,   0,
      2,   2,   3,   3,   3,   3,   3,   4,   2,   3,   3,   3,   3,   3,   2,   2,
      3,   3,   3,   2,   4,   2,   2,   2,   2,   2,   2,   3,   0,   0,   0,  41,
      3,   3,   0,   0,   0,   3,   0,   3,   0,   3,   3,   3,  41,  41,   1,   1,
      1,   0,   1,   1,   1,   2,   0,   0,   1,   1,   1,   2,   1,   1,   1,   0,
      2,   0,   0,   0,  41,   0,   0,   0,   1,   1,   3,   1,   1,   1,   2,   2,
     53,  53,  53,  53,   0,   0,   1,   1,   1,   1,   0,   0,   0,   1,   1,   1,
     57,  57,  57,  57,  57,  57,  57,   0,   0,  55,  55,  55,  58,  58,  58,  58,
      0,   0,   0,  58,  58,   0,   0,   0,   1,   0,   0,   0,  36,  36,  36,  36,
     36,  36,   0,  36,  36,  36,   0,   0,   1,  36,   1,  36,   1,  36,  36,  36,
     36,  36,  41,  41,  41,  41,  25,  25,   0,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,   0,   0,  41,  41,   1,   1,  33,  33,  33,   1,  34,  34,  34,
     34,  34,  34,  34,  34,  34,  34,   1,   0,  35,  35,  35,  35,  35,  35,  35,
     35,  35,   0,   0,   0,  25,  25,  25,  25,  25,  25,   0,  35,  35,  35,   0,
     25,  25,  25,   1,  34,  34,  34,   0,  37,  37,  37,  37,  37,   0,   0,   0,
     37,  37,  37,   0,  83,  83,  83,  83,  70,  70,  70,  70,  84,  84,  84,  84,
      2,   2,   2,   0,   0,   0,   0,   2,  59,  59,  59,  59,  65,  65,  65,  65,
     71,  71,  71,  71,  71,  71,   0,   0,   0,   0,  71,  71,  10,  10,   0,   0,
     72,  72,  72,  72,  72,  72,   1,  72,  73,  73,  73,  73,   0,   0,   0,  73,
     25,   0,   0,   0,  85,  85,  85,  85,  85,  85,   0,   1,  85,  85,   0,   0,
      0,   0,  85,  85,  23,  23,  23,   0,  77,  77,  77,  77,  77,  77,  77,   0,
     77,  77,   0,   0,  79,  79,  79,  79,  79,  79,  79,   0,   0,   0,   0,  79,
     86,  86,  86,  86,  86,  86,  86,   0,   2,   3,   0,   0,  86,  86,   0,   0,
      0,   0,   0,  25,   0,   0,   0,   5,   6,   0,   6,   0,   6,   6,   0,   6,
      6,   0,   6,   6,   0,   0,   0,   7,   7,   7,   1,   1,   0,   0,   7,   7,
     41,  41,   4,   4,   7,   0,   0,   1,   1,   1,  34,  34,  34,  34,   1,   1,
      0,   0,  25,  25,  48,  48,  48,  48,   0,  48,  48,  48,  48,  48,  48,   0,
     48,  48,   0,  48,  48,  48,   0,   0,   3,   0,   0,   0,   1,  41,   0,   0,
     74,  74,  74,  74,  74,   0,   0,   0,  75,  75,  75,  75,  75,   0,   0,   0,
     38,  38,  38,  38,  39,  39,  39,  39,  39,  39,  39,   0, 120, 120, 120, 120,
    120, 120, 120,   0,  49,  49,  49,  49,  49,  49,   0,  49,  60,  60,  60,  60,
     60,  60,   0,   0,  40,  40,  40,  40,  50,  50,  50,  50,  51,  51,  51,  51,
     51,  51,   0,   0, 136, 136, 136, 136, 106, 106, 106, 106, 103, 103, 103, 103,
      0,   0,   0, 103, 110, 110, 110, 110, 110, 110, 110,   0, 110, 110,   0,   0,
     52,  52,  52,  52,  52,  52,   0,   0,  52,   0,  52,  52,  52,  52,   0,  52,
     52,   0,   0,   0,  52,   0,   0,  52,  87,  87,  87,  87,  87,  87,   0,  87,
    118, 118, 118, 118, 117, 117, 117, 117, 117, 117, 117,   0,   0,   0,   0, 117,
    128, 128, 128, 128, 128, 128, 128,   0, 128, 128,   0,   0,   0,   0,   0, 128,
     64,  64,  64,  64,   0,   0,   0,  64,  76,  76,  76,  76,  76,  76,   0,   0,
      0,   0,   0,  76,  98,  98,  98,  98,  97,  97,  97,  97,   0,   0,  97,  97,
     61,  61,  61,  61,   0,  61,  61,   0,   0,  61,  61,  61,  61,  61,  61,   0,
      0,   0,   0,  61,  61,   0,   0,   0,  88,  88,  88,  88, 116, 116, 116, 116,
    112, 112, 112, 112, 112, 112, 112,   0,   0,   0,   0, 112,  80,  80,  80,  80,
     80,  80,   0,   0,   0,  80,  80,  80,  89,  89,  89,  89,  89,  89,   0,   0,
     90,  90,  90,  90,  90,  90,  90,   0, 121, 121, 121, 121, 121, 121,   0,   0,
      0, 121, 121, 121, 121,   0,   0,   0,  91,  91,  91,  91,  91,   0,   0,   0,
    130, 130, 130, 130, 130, 130, 130,   0,   0,   0, 130, 130,   7,   7,   7,   0,
     94,  94,  94,  94,  94,  94,   0,   0,   0,   0,  94,  94,   0,   0,   0,  94,
     92,  92,  92,  92,  92,  92,   0,   0, 101, 101, 101, 101, 101,   0,   0,   0,
    101, 101,   0,   0,  96,  96,  96,  96,  96,   0,  96,  96, 111, 111, 111, 111,
    111, 111, 111,   0, 100, 100, 100, 100, 100, 100,   0,   0, 109, 109, 109, 109,
    109, 109,   0, 109, 109, 109, 109,   0, 129, 129, 129, 129, 129, 129, 129,   0,
    129,   0, 129, 129, 129, 129,   0, 129, 129, 129,   0,   0, 123, 123, 123, 123,
    123, 123, 123,   0, 123, 123,   0,   0, 107, 107, 107, 107,   0, 107, 107, 107,
    107,   0,   0, 107, 107,   0, 107, 107, 107, 107,   0,   0, 107,   0,   0,   0,
      0,   0,   0, 107,   0,   0, 107, 107, 135, 135, 135, 135, 135, 135,   0, 135,
      0, 135,   0,   0, 124, 124, 124, 124, 124, 124,   0,   0, 122, 122, 122, 122,
    122, 122,   0,   0, 114, 114, 114, 114, 114,   0,   0,   0, 114, 114,   0,   0,
     32,   0,   0,   0, 102, 102, 102, 102, 102, 102,   0,   0, 126, 126, 126, 126,
    126, 126,   0,   0,   0, 126, 126, 126, 125, 125, 125, 125, 125, 125, 125,   0,
      0,   0,   0, 125, 119, 119, 119, 119, 119,   0,   0,   0, 133, 133, 133, 133,
    133,   0, 133, 133, 133, 133, 133,   0, 133, 133,   0,   0, 133,   0,   0,   0,
    134, 134, 134, 134,   0,   0, 134, 134,   0, 134, 134, 134, 134, 134, 134,   0,
     63,  63,  63,  63,  63,  63,   0,   0,  63,  63,  63,   0,  63,   0,   0,   0,
     81,  81,  81,  81,  81,  81,  81,   0, 127, 127, 127, 127, 127, 127, 127,   0,
     84,   0,   0,   0, 115, 115, 115, 115, 115, 115, 115,   0, 115, 115,   0,   0,
      0,   0, 115, 115, 104, 104, 104, 104, 104, 104,   0,   0, 108, 108, 108, 108,
    108, 108,   0,   0, 108, 108,   0, 108,   0, 108, 108, 108,  99,  99,  99,  99,
     99,   0,   0,   0,  99,  99,  99,   0,   0,   0,   0,  99, 137,   0,   0,   0,
    137, 137, 137, 137, 137, 137, 137,   0,  34,  33,   0,   0, 105, 105, 105, 105,
    105, 105, 105,   0, 105,   0,   0,   0, 105, 105,   0,   0,   1,   1,   1,  41,
      1,  41,  41,  41,   1,   1,  41,  41,   0,   0,   1,   0,   0,   1,   1,   0,
      1,   1,   0,   1,   1,   0,   1,   0, 131, 131, 131, 131,   0,   0,   0, 131,
      0, 131, 131, 131,  57,   0,   0,  57,  57,  57,   0,  57,  57,   0,  57,  57,
    113, 113, 113, 113, 113,   0,   0, 113, 113, 113, 113,   0, 132, 132, 132, 132,
    132, 132, 132,   0, 132, 132,   0,   0,   0,   0, 132, 132,   0,   7,   7,   7,
      0,   7,   7,   0,   7,   0,   0,   7,   0,   7,   0,   7,   0,   0,   7,   0,
      7,   0,   7,   0,   7,   7,   0,   7,  33,   1,   1,   0,   1,   0,   0,   1,
     36,  36,  36,   0,  36,   0,   0,   0,   0,   1,   0,   0,
};

/* Script: 11396 bytes. */

RE_UINT32 re_get_script(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 11;
    code = ch ^ (f << 11);
    pos = (RE_UINT32)re_script_stage_1[f] << 4;
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
     0,  1,  2,  2,  2,  3,  4,  5,  6,  7,  8,  9,  2, 10, 11, 12,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
    13,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,
};

static RE_UINT8 re_word_break_stage_2[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  32,  31,  33,  34,  31,  31,  31,  31,  35,  36,  37,  31,
     38,  39,  40,  41,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
      1,   1,   1,   1,  42,   1,  43,  44,  45,  46,  47,  48,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  49,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  50,   1,  51,  52,  53,
     54,  55,  56,  57,  58,  59,   1,  60,  61,  62,  63,  64,  65,  31,  31,  31,
     66,  67,  68,  69,  70,  71,  72,  73,  74,  31,  75,  31,  76,  31,  31,  31,
      1,   1,   1,  77,  78,  79,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
      1,   1,   1,   1,  80,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,   1,   1,  81,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,   1,   1,  82,  83,  31,  31,  31,  84,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     85,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  86,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  87,  88,  31,  89,  90,  91,  92,  31,  31,  93,  31,  31,  31,  31,  31,
     94,  31,  31,  31,  31,  31,  31,  31,  95,  96,  31,  31,  31,  31,  97,  31,
     31,  98,  31,  99, 100, 101, 102,  31,  31, 103,  31,  31,  31,  31,  31,  31,
    104, 105,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,
};

static RE_UINT16 re_word_break_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   6,   7,   7,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,   8,   9,  10,  10,  10,  11,  12,  13,   7,  14,
      7,   7,   7,   7,  15,   7,   7,   7,   7,  16,  17,  18,  19,  20,  21,  22,
     23,   7,  24,  25,   7,   7,  26,  27,  28,  29,  30,   7,   7,  31,  32,  33,
     34,  35,  36,  37,  37,  38,  39,  40,  41,  42,  43,  44,  45,  46,  47,  48,
     49,  50,  51,  52,  53,  54,  55,  56,  57,  54,  58,  59,  60,  61,  62,  63,
     64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,  78,  79,
     37,  80,  81,  37,  37,  82,  83,  37,  84,  85,  86,  87,  88,  89,  90,  37,
     37,  91,  92,  93,  94,   7,  95,  96,   7,   7,  97,   7,  98,  99, 100,   7,
    101,   7, 102,  37, 103,   7,   7, 104,  18,   7,   7,   7,   7,   7,   7,   7,
      7,   7,   7, 105,   3,   7,   7, 106, 107, 108, 109, 110,  37,  39, 111, 112,
    113,   7,   7, 114, 115, 116,   7, 117, 118, 119,  63,  37,  37,  37, 120,  37,
    121,  37, 122, 123, 124, 125,  37,  37, 126, 127, 128, 129, 130, 131,   7, 132,
      7, 133, 134, 135, 136,  37, 137, 138,   7,   7,   7,   7,   7,   7,  10, 139,
    104,   7, 140, 135,   7, 141, 142, 143, 144, 145, 146, 147, 148,  37, 149, 150,
    151, 152, 153,   7, 136,  37,  37,  37,  37,  37,  37,  37,  37,  37,  37,  37,
     37,  37,  37,  37,  37, 154,   7, 155, 156,  37,  37,  37,  37,  37,  37, 157,
    158,  37,  37, 159,  37,  37,  37,  37,   7, 160, 118,   7,   7,   7,   7, 161,
      7,  95,   7, 162, 163, 164, 164,  10,  37, 165,  37,  37,  37,  37,  37,  37,
    166, 167,  37,  37, 168, 169, 169, 170, 171, 172,   7,   7, 173, 174,  37, 175,
     37,  37,  37,  37,  37,  37, 175, 176, 169, 169, 177,  37,  37,  37,  37,  37,
      7,   7,   7,   7, 178,  37, 179, 135, 180, 181,   7, 182, 183,   7,   7, 184,
    185, 186,   7,   7, 187, 188,  37, 185, 189, 190,   7, 191, 192, 127, 193, 194,
     32, 195, 196, 197,  41, 198, 199, 200,   7, 201, 202, 203,  37, 204, 205, 206,
    207, 208,  96, 209,   7,   7,   7, 210,   7,   7,   7,   7,   7, 211, 212, 213,
    214, 215, 216,   7,   7, 217, 218,   7,   7, 135, 179,   7, 219,   7, 220, 221,
    222, 223, 224, 225,   7,   7,   7, 226, 227,   2,   3, 228, 229, 118, 230, 231,
    232, 233, 234,  37,   7,   7,   7, 174,  37,  37,   7, 235,  37,  37,  37, 236,
     37,  37,  37,  37, 197,   7, 237, 238,   7, 179, 239, 240, 135,   7, 241,  37,
      7,   7,   7,   7, 135, 242, 243, 213,   7, 244,   7, 245,  37,  37,  37,  37,
      7, 163, 117, 220,  37,  37,  37,  37, 246, 247, 117, 163, 118,  37,  37, 248,
    117, 249,  37,  37,   7, 250,  37,  37, 251, 252,  37, 197, 197,  37,  86, 253,
      7, 117, 117, 254, 217,  37,  37,  37,   7,   7, 136,  37,   7, 254,   7, 254,
    130, 255, 256, 257, 130, 258, 179, 259, 130, 260, 179, 261, 130, 198, 262,  37,
    263, 264,  37,  37, 265, 266, 267, 268, 269,  54, 270, 271,  37,  37,  37,  37,
      7, 272, 273,  37,   7,  29, 274,  37,  37,  37,  37,  37,   7, 275, 276,  37,
      7,  29, 277,  37,   7, 278, 112,  37, 279, 280,  37,  37,  37,  37,  37,  37,
     37,  37,  37,  37,  37,   7,   7, 281,  37,  37,  37,  37,  37,  37,   7, 282,
    283, 284, 285, 286, 287, 288,  37,  37,   7,   7,   7,   7, 249,  37,  37,  37,
      7,   7,   7, 173,   7,   7,   7,   7,   7,   7, 245,  37,  37,  37,  37,  37,
      7, 173,  37,  37,  37,  37,  37,  37,   7,   7, 289,  37,  37,  37,  37,  37,
      7, 282, 118, 112,  37,  37, 179, 290,   7, 291, 292, 293, 103,  37,  37,  37,
      7,   7, 294, 295, 296,  37,  37, 297, 298,  37,  37,  37,  37,  37,  37,  37,
      7,   7,   7, 299, 300, 301,  37,  37,  37,  37,  37, 302, 303, 304,  37,  37,
     37,  37, 305,  37,  37,  37,  37,  37,   7,   7, 306,   7, 307, 308, 309,   7,
    310, 311, 312,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7, 313, 314,  96,
    306, 306, 160, 160, 283, 283, 315, 316,  10, 317,  10, 318, 319, 320,  37,  37,
    321, 322,  37,  37,  37,  37,  37,  37,   7,   7,   7,   7,   7,   7, 323,  37,
      7,   7, 324,  37,  37,  37,  37,  37, 309, 325, 326, 327, 328, 329,  37,  37,
     37, 179, 330, 330, 155,  37,  37, 331,  37,  37,  37,  37, 332,  37, 333, 334,
     37,  37, 335, 336, 337, 338,  37,  37,  37,  37,  37, 339, 340,  37,  37, 341,
     37,  37, 342,  37,  37, 343, 344,  37, 345, 346,  37,  37,  37,  37,  37,  37,
    347,  10,  10,  10,  37,  37,  37,  37,  10,  10,  10,  10,  10,  10,  10, 348,
};

static RE_UINT8 re_word_break_stage_4[] = {
      0,   0,   1,   2,   0,   0,   0,   0,   3,   4,   0,   5,   6,   6,   7,   0,
      8,   9,   9,   9,   9,   9,  10,  11,   8,   9,   9,   9,   9,   9,  10,   0,
      0,  12,   0,   0,   0,   0,   0,   0,   0,   0,  13,  14,   0,  15,  13,   0,
      9,   9,   9,   9,   9,  10,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,
     16,  17,   9,   9,  16,  18,   0,   0,   9,  19,   0,  20,   0,   0,   0,   0,
     21,  21,  21,  21,  21,  21,  21,  21,  21,  21,  21,  21,   9,  22,  17,  23,
      0,  24,  10,  22,   9,   9,   9,   9,  25,   9,   9,   9,   9,   9,   9,   9,
      9,   9,   9,   9,   9,  25,   9,   9,  26,  21,  27,   9,   9,   9,   9,   9,
      9,   9,   9,   9,   8,   9,   9,   9,   9,   9,   9,   9,   9,  10,  28,   0,
      8,   9,   9,   9,   9,   9,   9,   9,   9,   9,  29,   0,  30,  21,  21,  21,
     21,  21,  21,  21,  21,  21,  21,  31,  32,  31,   0,   0,  33,  33,  33,  33,
     33,  33,  34,   0,  35,  36,   0,   0,  37,  38,   0,  39,  21,  21,  40,  41,
      9,   9,  42,  21,  21,  21,  21,  21,   6,   6,  43,  44,  45,   9,   9,   9,
      9,   9,   9,   9,   9,  46,  21,  47,  21,  48,  49,  27,   6,   6,  50,  51,
      0,   0,   0,  52,  53,   9,   9,   9,   9,   9,   9,   9,  21,  21,  21,  21,
     21,  21,  40,   8,   9,   9,   9,   9,   9,  54,  21,  21,  55,   0,   0,   0,
      6,   6,  50,   9,   9,   9,   9,   9,   9,   9,  42,  21,  21,  16,  56,   0,
      9,   9,   9,   9,   9,  54,  57,  21,  21,  58,  58,  59,   0,   0,   0,   0,
      9,   9,   9,   9,   9,   9,  58,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      9,   9,   9,   9,   9,  22,   9,  16,   0,   0,   0,   0,   0,  21,  21,  21,
     60,  21,  21,  21,  21,  21,  21,  21,  21,   9,   9,   9,   9,   9,   9,   9,
      9,   9,   9,   9,   9,   9,  54,  61,  21,  21,  21,  21,  58,  21,   9,   9,
     54,  62,   6,   6,   8,   9,   9,   9,  58,   8,   9,  51,  51,   9,   9,   9,
      9,   9,  22,   9,  20,  17,  16,  61,  21,  63,  63,  64,   0,  65,   0,  25,
     54,  62,   6,   6,  16,   0,   0,   0,  30,   8,  10,  66,  51,   9,   9,   9,
      9,   9,  22,   9,  22,  67,  16,  49,  40,  65,  63,  59,  68,   0,   8,  20,
      0,  62,   6,   6,  27,  69,   0,   0,  30,   8,   9,  25,  25,   9,   9,   9,
      9,   9,  22,   9,  22,   8,  16,  61,  21,  31,  31,  59,  19,   0,   0,   0,
     54,  62,   6,   6,   0,   0,  28,   0,  30,   8,   9,  51,  51,   9,   9,   9,
     21,  63,  63,  59,   0,  70,   0,  25,  54,  62,   6,   6,  28,   0,   0,   0,
     71,   8,  10,  17,  22,  16,  67,  22,  66,  19,  10,  17,   9,   9,  16,  70,
     40,  70,  49,  59,  19,  65,   0,   0,   0,  62,   6,   6,   0,   0,   0,   0,
     21,   8,   9,  22,  22,   9,   9,   9,   9,   9,  22,   9,   9,   9,  16,  46,
     21,  49,  49,  59,   0,  32,  10,   0,  54,  62,   6,   6,   0,   0,   0,   0,
     58,   8,   9,  22,  22,   9,   9,   9,   9,   9,  22,   9,   9,   8,  16,  61,
     21,  49,  49,  59,   0,  32,   0,  13,  54,  62,   6,   6,  67,   0,   0,   0,
     30,   8,   9,  22,  22,   9,   9,   9,   9,   9,   9,   9,   9,   9,  10,  46,
     21,  49,  49,  64,   0,  42,   0,  66,  54,  62,   6,   6,   0,   0,  17,   9,
     70,   8,   9,   9,   9,  10,  17,   9,   9,   9,   9,   9,  25,   9,   9,  28,
      9,  10,  72,  65,  21,  73,  21,  21,   0,  62,   6,   6,  70,   0,   0,   0,
      0,   0,   0,   0,  68,  21,  40,   0,   0,  65,  21,  40,   6,   6,  74,   0,
      0,   0,   0,   0,  68,  21,  31,  75,   0,   0,  21,  59,   6,   6,  74,   0,
     19,   0,   0,   0,   0,   0,  59,   0,   6,   6,  74,   0,   0,  76,  68,  70,
      9,   9,   8,   9,   9,   9,   9,   9,   9,   9,   9,  19,  30,  21,  21,  21,
     21,  49,   9,  58,  21,  21,  30,  21,  21,  21,  21,  21,  21,  21,  21,  75,
      0,  72,   0,   0,   0,   0,   0,   0,   0,   0,  65,  21,  21,  21,  21,  40,
      6,   6,  74,   0,   0,  70,  59,  70,  49,  63,  21,  59,  30,  75,   0,   0,
     70,  21,  21,  31,   6,   6,  77,  59,   9,  25,   0,  28,   9,   9,   9,   9,
      9,   9,   9,   9,   9,   9,  10,   9,   9,   9,  22,  16,   9,  10,  22,  16,
      9,   9,  22,  16,   9,   9,   9,   9,   9,   9,   9,   9,  22,  16,   9,  10,
     22,  16,   9,   9,   9,  10,   9,   9,   9,   9,   9,   9,  22,  16,   9,   9,
      9,   9,   9,   9,   9,   9,  10,  30,   9,   9,   9,   9,   0,   0,   0,   0,
      9,   9,   9,   9,   9,  16,   9,  16,   9,   9,   9,  51,   9,   9,   9,   9,
      9,   9,  10,  17,   9,   9,  19,   0,   9,   9,   9,  22,  54,  75,   0,   0,
      9,   9,   9,   9,  54,  75,   0,   0,   9,   9,   9,   9,  54,   0,   0,   0,
      9,   9,   9,  22,  78,   0,   0,   0,  21,  21,  21,  21,  21,   0,   0,  68,
      6,   6,  74,   0,   0,   0,   0,   0,   0,   0,  65,  79,   6,   6,  74,   0,
      9,   9,   9,   9,   9,   9,   0,   0,   9,  80,   9,   9,   9,   9,   9,   9,
      9,   9,  81,   0,   9,   9,   9,   9,   9,   9,   9,   9,   9,  16,   0,   0,
      9,   9,   9,   9,   9,   9,   9,  10,  21,  21,  21,   0,  21,  21,  21,   0,
      0,   0,   0,   0,   6,   6,  74,   0,   9,   9,   9,   9,   9,  42,  21,   0,
      0,   0,   0,   0,   0,  30,  21,  40,  21,  21,  21,  21,  21,  21,  21,  63,
      6,   6,  74,   0,   6,   6,  74,   0,   0,   0,   0,   0,  21,  21,  21,  40,
     21,  45,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,  21,  21,  21,
     21,  45,   9,   0,   6,   6,  74,   0,   0,   0,  65,  21,  21,   0,   0,   0,
     82,   9,   9,   9,   9,   9,   9,   9,  58,  21,  21,  27,   6,   6,  50,   9,
      9,  54,  21,  21,  21,   0,   0,   0,   9,  21,  21,  21,  21,  21,   0,   0,
      6,   6,  74,   8,   6,   6,  50,   9,   9,   9,   9,   9,   9,   9,   9,  16,
      9,   9,  19,   0,   0,   0,   0,   0,   0,   0,   0,   0,  40,  21,  21,  21,
     21,  21,  45,  53,  54,  83,  59,   0,  21,  21,  21,  21,  21,  59,  65,  21,
      9,  16,   9,  16,   9,   9,  84,  84,   9,   9,   9,   9,   9,  22,   9,  20,
     17,  22,   9,  19,   9,  17,   9,   0,   9,   9,   9,  19,  17,  22,   9,  19,
      0,   0,   0,  85,   0,   0,  86,   0,   0,  87,  88,  89,   0,   0,   0,  11,
     90,  91,   0,   0,   0,  90,   0,   0,  37,  92,  37,  37,  28,   0,   0,  66,
      0,   0,   0,   0,   9,   9,   9,  19,   0,   0,   0,   0,  21,  21,  21,  21,
     21,  21,  21,  21,  75,   0,   0,   0,  13,  66,  17,   9,   9,  28,   8,  16,
      0,  20,  22,  25,   9,   9,  16,   9,   0,   8,  16,  13,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  17,   9,   9,   9,   9,  16,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  93,   0,   0,   0,   0,   0,   0,  93,   0,
      0,   0,  94,  95,   0,   0,   0,   0,   0,  96,   0,   0,   0,   0,   0,   0,
      9,   9,   9,  10,   9,   9,   9,   9,   9,  19,  66,  42,  27,   0,   0,   0,
      9,   9,   0,  66,   0,   0,   0,  65,   9,   9,   9,   9,   9,  10,   0,   0,
      9,  10,   9,  10,   9,  10,   9,  10,   0,   0,   0,  66,   0,   0,   0,   0,
      0,  28,   0,   0,   0,   0,   0,   0,   0,   0,  70,  21,  97,  98,  66,  19,
      0,   0,   0,   0,   0,   0,  99, 100, 101, 101, 101, 101, 101, 101, 101, 101,
    101, 101, 101, 101, 101, 101, 102, 101,   0,   8,   9,   9,   9,   9,   9,   9,
      9,   9,   9,  16,   8,   9,   9,   9,   9,   9,   9,  10,   0,   0,   0,   0,
      9,   9,   9,   9,   9,   9,  10,   0,   0,   0,   0,   0, 101, 101, 101, 101,
    101, 101, 101, 101, 101, 101, 101, 102, 101, 101, 101, 101, 101, 101,   0,   0,
      9,   9,   9,  19,   0,   0,   0,   0,   0,   0,   0,   0,   9,   9,   9,   9,
      9,   9,   9,  19,   9,   9,   9,   9,   6,   6,  50,   0,   0,   0,   0,   0,
      9,   9,   9,  42,  40,  21,  21, 103,   9,   9,   9,   9,   9,   9,   9,  54,
      9,   9,   9,   9,  59,   0,   0,   0,   0,   0,   0,   0,   0,  66,   9,   9,
     17,   9,   9,   9,   9,   9,   9,   9,   9,   9,  51,   9,   9,   9,   9,   9,
      9,   9,   9,  10,   9,   9,   0,   0, 104, 104,  42,   9,   9,   9,   9,   9,
     42,  21,   0,   0,   0,   0,   0,   0,   9,   9,   9,   9,   9,   0,   0,   0,
     27,   9,   9,   9,   9,   9,   9,   9,  21,  59,   0,   0,   6,   6,  74,   0,
     21,  21,  21,  21,  27,   9,  66,  28,   9,  54,  21,  59,   9,   9,   9,   9,
      9,  42,  21,  21,  21,   0,   0,   0,   9,   9,   9,   9,   9,   9,   9,  19,
      9,   9,   9,   9,  42,  21,  21,  21,  75,   0,   0,  66,   6,   6,  74,   0,
      0,  68,   0,   0,   6,   6,  74,   0,   9,   9,  58,  21,  21,  40,   0,   0,
     42,   9,   9,  59,   6,   6,  74,   0,   0,   0,   0,   0,   0,   0,  65,  59,
      0,   0,   0,   0,  49,  63,  75,  70,  68,   0,   0,   0,   0,   0,   0,   0,
      9,   9,  42,  21,  17, 105,   0,   0,   8,  10,   8,  10,   8,  10,   0,   0,
      9,  10,   9,  10,   9,   9,   9,   9,   9,  16,   0,   0,   9,   9,   9,   9,
     42,  21,  40,  59,   6,   6,  74,   0,   9,   0,   0,   0,   9,   9,   9,   9,
      9,  10,  66,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,   0,
      9,  10,   0,   0,  66,   9,   0, 106,  33,  33, 107,  33,  33,  34,  33, 108,
    109, 107,  33,  33,   9,   9,   9,   9,   9,   9,   9,   9,  16,   0,   0,   0,
      0,   0,   0,   0,  66,   9,   9,   9,   9,   9,   9,   9,  17,   9,   9,   9,
      9,   9,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   9,   9,   9,   0,
     21,  21,  21,  21, 110,  91,   0,   0,  21,  21,  21,  21,  11,  90,   0,   0,
      0,   0,   0, 111,   5, 112,   0,   0,   0,   0,   0,   0,   9,  22,   9,   9,
      9,   9,   9,   9,   9,   9,   9, 113,   0, 114,   0,   5,   0,   0, 115,   0,
      0, 116, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 101, 117,
     17,   9,  17,   9,  17,   9,  17,  19,   0,   0,   0,   0,   0,   0, 118,   0,
      9,   9,   9,   8,   9,   9,   9,   9,   9,  10,   9,   9,   9,   9,  10,  25,
      9,   9,   9,  16,   9,   9,   9,  16,   9,   9,   9,   9,   9,  19,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  68,   9,   9,   9,   9,  19,   0,   0,   0,
     75,   0,   0,   0,   0,   0,   0,   0,   9,   9,  10,   0,   9,   9,   9,   9,
      9,   9,   9,   9,   9,  54,  40,   0,   9,   0,   9,   9,   8,  16,   0,   0,
      6,   6,  74,   0,   9,   9,   9,   9,   9,   9,   9,   9,   9,   0,   9,   9,
      9,   9,   0,   0,   9,   9,   9,   9,   9,   0,   0,   0,   0,   0,   0,   0,
      9,  16,  22,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,  25,  19,  51,
      9,   9,   9,   9,  10,  16,   0,   0,   9,   9,   9,   9,   9,   9,  16,   0,
      9,   9,   9,   9,   9,   9,   0,  17,  58,  32,   0,  21,   9,   8,   8,   9,
      9,   9,   9,   9,   9,   0,  40,  65,   9, 105,   0,   0,   0,   0,   0,   0,
      9,   9,   9,   9,  10,   0,   0,   0,   9,   9,   9,   9,   9,   9,  21,  21,
     21,  40,   0,   0,   0,   0,   0,   0,   0,  62,   6,   6,   0,   0,   0,  65,
      9,   9,   9,   9,  21,  21,  40,  14,   9,   9,  19,   0,   6,   6,  74,   0,
      9,  42,  21,  21,  21, 119,   6,   6,   9,   9,   9,   9,  42,  13,   0,   0,
     45,  19,  70,  75,   6,   6, 120,  19,   9,   9,   9,   9,  25,   9,   9,   9,
      9,   9,   9,  21,  21,  21,   0,  72,   9,  10,  22,  25,   9,   9,   9,  25,
      9,   9,  19,   0,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,   9,  42,
     21,  21,  40,   0,   6,   6,  74,   0,  21,   8,   9,  51,  51,   9,   9,   9,
     21,  63,  63,  59,  19,  65,   0,   8,  54,  70,  21,  75,  21,  75,   0,   0,
      9,   9,   9,   9,   9,  58,  21,  21,  21,  82,  10,   0,   6,   6,  74,   0,
     21,  25,   0,   0,   6,   6,  74,   0,   9,   9,   9,  42,  21,  59,  21,  21,
     75,   0,   0,   0,   0,   0,   9,  59,  75,  19,   0,   0,   6,   6,  74,   0,
      9,   9,  42,  21,  21,  21,   0,   0,   0,   0,   0,   0,   0,   0,   0,  30,
     21,  21,  21,   0,   6,   6,  74,   0,   6,   6,  74,   0,   0,   0,   0,  66,
      9,   9,   9,   9,   9,   9,  19,   0,   9,   9,  22,   9,   9,   9,   9,   9,
      9,   9,   9,  42,  21,  40,  21,  21,  19,   0,   0,   0,   6,   6,  74,   0,
      0,   0,   0,   0,  17,   9,   9,   9,   9,   9,   9,   9,  70,  21,  21,  21,
     21,  21,  30,  21,  21,  40,   0,   0,   9,  10,   0,   0,   0,   0,   0,   0,
      9,   9,   9,  16,  21,  75,   0,   0,   9,   9,   9,   9,  21,  40,   0,   0,
      9,   0,   0,   0,   6,   6,  74,   0,  66,   9,   9,   9,   9,   9,   0,   8,
      9,  19,   0,   0,  58,  21,  21,  21,  21,  21,  21,  21,  21,  21,  21,  40,
      0,   0,   0,  65,  82,   9,   9,   9,  19,   0,   0,   0,   0,   0,   0,   0,
    100,   0,   0,   0,   0,   0,   0,   0,   9,   9,  10,   0,   9,   9,   9,  19,
      9,   9,  19,   0,   9,   9,  16,  32,  37,   0,   0,   0,   0,   0,   0,   0,
      0,  30,  59,  30, 121,  37, 122,  21,  40,  30,  21,   0,   0,   0,   0,   0,
      0,   0,  70,  59,   0,   0,   0,   0,  70,  75,   0,   0,   0,   0,   0,   0,
      9,   9,   9,   9,   9,  22,   9,   9,   9,   9,   9,   9,   9,   9,   9,  22,
     13,  67,   8,  22,   9,   9,  25,   8,   9,   8,   9,   9,   9,   9,   9,   9,
      9,  25,  10,   8,   9,  22,   9,  22,   9,   9,   9,   9,   9,   9,  25,  10,
      9,  20,  17,   9,  22,   9,   9,   9,   9,  16,   9,   9,   9,   9,   9,   9,
     22,   9,   9,   9,   9,   9,  10,   9,  10,   9,   9,  62,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   6,   6,  21,  21,  21,  21,  21,  40,  65,  21,
     21,  21,  21,  75,   0,  68,   0,   0,   0,  75,   0,   0,   0,   0,  65,  21,
     30,  21,  21,  21,   0,   0,   0,   0,  21,  40,  21,  21,  21,  21,  63,  21,
     31,  49,  40,   0,   0,   0,   0,   0,   9,  19,   0,   0,  21,  40,   0,   0,
      9,  21,  40,   0,   6,   6,  74,   0,  67,  51,   8,   9,  10,   9,  84,   0,
     13,  66,  84,   8,  67,  51,  84,  84,  67,  51,  10,   9,  10,   9,   8,  20,
      9,   9,  25,   9,   9,   9,   9,   0,   8,   8,  25,   9,   9,   9,   9,   0,
      9,   9,  16,   0,   9,   9,   9,   9,   0, 123, 124, 124, 124, 124, 124, 124,
      0,  93,   0,   0,   0,   0,   0,   0, 125, 126,  94,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 127, 128,  94,  94, 129, 129, 126,   0,   0,   0,
      0, 130, 131, 132, 129, 129, 126, 126, 133, 133, 134,   0,   0,   0,   0,   0,
      0,   0, 132,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  93, 132,   0,
      0,   0,   0,   0, 126, 135,   0,   0,   0,   0,  96,   0,   0,   0,   0,   0,
      0, 133, 125, 129,   0,   0,   0,   0, 125,   0,   0,   0,   0, 136,   0,   0,
    126,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 129, 136,
      0, 132,   0,   0, 137, 129,  95, 136,  14,   0,   0,   0,   0,   0,   0,   0,
     21,  21,  21,  21,   0,   0,   0,   0,
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
     7,  7,  9,  7,  7, 11,  7,  7,  0,  0, 15, 15,  7,  0,  0,  7,
     7,  7, 11,  0,  0,  0,  0,  7,  0,  0,  0, 11,  0, 11, 11,  0,
     0,  7,  0,  0, 11,  7,  0,  0,  0,  0,  7,  7,  0,  0,  7, 11,
     0,  0,  7,  0,  7,  0,  7,  0, 15, 15,  0,  0,  7,  0,  0,  0,
     0,  7,  0,  7, 15, 15,  7,  7, 11,  0,  7,  7,  7,  7,  9,  0,
    11,  7,  7, 11, 11,  7, 11,  0,  7,  7,  7, 11,  7, 11, 11,  0,
     0, 11,  0, 11,  7, 19,  9,  9, 14, 14,  0,  0, 14,  0,  0, 12,
     6,  6,  9,  9,  9,  9,  9, 16, 16,  0,  0,  0, 13,  0,  0,  0,
     9,  0,  9,  9,  0, 17,  0,  0,  0,  0, 17, 17, 17, 17,  0,  0,
    20,  0,  0,  0,  0, 10, 10, 10, 10, 10,  0,  0,  0,  7,  7, 10,
    10,  0,  0,  0, 10, 10, 10, 10, 10, 10, 10,  0,  7,  7,  0, 11,
    11, 11,  7, 11, 11,  7,  7,  0,  0,  3,  7,  3,  3,  0,  3,  3,
     3,  0,  3,  0,  3,  3,  0,  3, 13,  0,  0, 12,  0, 16, 16, 16,
    13, 12,  0,  0, 11,  0,  0,  9,  0,  0,  0, 14,  0,  0, 12, 13,
     0,  0, 10, 10, 10, 10,  7,  7,  0,  9,  9,  9,  7,  0, 15, 15,
    15, 15, 11,  0,  7,  7,  7,  9,  9,  9,  9,  7,  0,  0,  8,  8,
     8,  8,  8,  8,  0,  0,  0, 17, 17,  0,  0,  0,  0,  0,  0, 18,
    18, 18, 18, 18, 17, 17, 17, 17,  0,  0, 21, 21, 21, 21,  0,  0,
     0,  0, 17,  0,  0, 17, 17, 17,  0,  0,  0, 20,  0, 17, 17,  0,
    17, 17, 17,  0, 17,  0,  0, 17,
};

/* Word_Break: 5624 bytes. */

RE_UINT32 re_get_word_break(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_word_break_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_word_break_stage_2[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_word_break_stage_3[pos + f] << 3;
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
    25,  1,  1,  1,  1,  1, 26, 27,  1,  1,  1,  1, 28, 29,  1,  1,
    30,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 31,  1, 32, 33, 34, 35, 36, 37, 38, 39,
    40, 41, 42, 36, 37, 38, 39, 40, 41, 42, 36, 37, 38, 39, 40, 41,
    42, 36, 37, 38, 39, 40, 41, 42, 36, 37, 38, 39, 40, 41, 42, 36,
    37, 38, 39, 40, 41, 42, 36, 43, 44, 44, 44, 44, 44, 44, 44, 44,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 45,  1,  1, 46, 47,
     1, 48, 49, 50,  1,  1,  1,  1,  1,  1, 51,  1,  1,  1,  1,  1,
    52, 53, 54, 55, 56, 57, 58, 59,  1,  1,  1,  1, 60,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 61, 62,  1,  1,  1, 63,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 64,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1, 65, 66,  1,  1,  1,  1,  1,  1,  1, 67,  1,  1,  1,  1,  1,
    68,  1,  1,  1,  1,  1,  1,  1, 69, 70,  1,  1,  1,  1,  1,  1,
     1, 71,  1, 72, 73, 74, 75,  1,  1, 76,  1,  1,  1,  1,  1,  1,
    77, 78, 44, 44, 44, 44, 44, 44, 44, 44, 44, 44, 44, 44, 44, 44,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_grapheme_cluster_break_stage_3[] = {
      0,   1,   2,   2,   2,   2,   2,   3,   1,   1,   4,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      5,   5,   5,   5,   5,   5,   5,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   6,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   7,   5,   8,   9,   2,   2,   2,
     10,  11,   2,   2,  12,   5,   2,  13,   2,   2,   2,   2,   2,  14,  15,   2,
     16,  17,   2,   5,  18,   2,   2,   2,   2,   2,  19,  13,   2,   2,  12,  20,
      2,  21,  22,   2,   2,  23,   2,   2,   2,   2,   2,   2,   2,  24,  25,   5,
     26,   2,   2,  27,  28,  29,  30,   2,  31,   2,   2,  32,  33,  34,  30,   2,
     35,   2,   2,  36,  37,  17,   2,  38,  35,   2,   2,  36,  39,   2,  30,   2,
     31,   2,   2,  40,  33,  41,  30,   2,  42,   2,   2,  43,  44,  34,   2,   2,
     45,   2,   2,  46,  47,  48,  30,   2,  31,   2,   2,  49,  50,  48,  30,   2,
     31,   2,   2,  43,  51,  34,  30,   2,  52,   2,   2,   2,  53,  54,   2,  52,
      2,   2,   2,  55,  56,   2,   2,   2,   2,   2,   2,  57,  58,   2,   2,   2,
      2,  59,   2,  60,   2,   2,   2,  61,  62,  63,   5,  64,  65,   2,   2,   2,
      2,   2,  66,  67,   2,  68,  13,  69,  70,  71,   2,   2,   2,   2,   2,   2,
     72,  72,  72,  72,  72,  72,  73,  73,  73,  73,  74,  75,  75,  75,  75,  75,
      2,   2,   2,   2,   2,  66,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,  76,   2,  76,   2,  30,   2,  30,   2,   2,   2,  77,  78,  79,   2,   2,
     80,   2,   2,   2,   2,   2,   2,   2,  48,   2,  81,   2,   2,   2,   2,   2,
      2,   2,  82,  83,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,  84,   2,   2,   2,  85,  86,  87,   2,   2,   2,  88,   2,   2,   2,   2,
     89,   2,   2,  90,  91,   2,  12,  20,  92,   2,  93,   2,   2,   2,  94,  95,
      2,   2,  96,  97,   2,   2,   2,   2,   2,   2,   2,   2,   2,  98,  99, 100,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   5,   5,   5, 101,
    102,   2, 103,   2,   2,   2,   1,   2,   2,   2,   2,   2,   2,   5,   5,  13,
      2, 104,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 105,
    106,   2,   2,   2,   2,   2, 107,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 108, 109,
      2,   2,   2,   2,   2,   2,   2, 108,   2,   2,   2,   2,   2,   2,   5,   5,
      2,   2, 110,   2,   2,   2,   2,   2,   2, 111,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2, 108, 112,   2,  46,   2,   2,   2,   2,   2, 109,
    113,   2, 114,   2,   2,   2,   2,   2, 115,   2,   2, 116, 117,   2,   5, 109,
      2,   2, 118,   2, 119,  95,  72, 120,  26,   2,   2, 121, 122,   2, 123,   2,
      2,   2, 124, 125, 126,   2,   2, 127,   2,   2,   2, 128,  17,   2, 129, 130,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 131,   2,
    132, 133, 134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 136, 134, 132, 133,
    134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 136, 134, 132, 133, 134, 135,
    134, 136, 134, 132, 133, 134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 136,
    134, 132, 133, 134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 136, 134, 132,
    133, 134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 136, 134, 132, 133, 134,
    135, 134, 136, 134, 132, 133, 134, 135, 134, 136, 134, 132, 133, 134, 135, 134,
    136, 134, 132, 133, 134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 136, 134,
    134, 135, 134, 136, 134, 132, 133, 134, 135, 134, 137,  73, 138,  75,  75, 139,
      1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      2, 140,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      5,   2,   5,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   3,
      2,   2,   2,   2,   2,   2,   2,   2,   2,  46,   2,   2,   2,   2,   2, 141,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  71,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  13,   2,
      2,   2,   2,   2,   2,   2,   2, 142,   2,   2,   2,   2,   2,   2,   2,   2,
    143,   2,   2, 144,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  48,   2,
    145,   2,   2, 146, 147,   2,   2, 108,  92,   2,   2, 148,   2,   2,   2,   2,
    149,   2, 150, 151,   2,   2,   2, 152,  92,   2,   2, 153, 154,   2,   2,   2,
      2,   2, 155, 156,   2,   2,   2,   2,   2,   2,   2,   2,   2, 108, 157,   2,
     95,   2,   2,  32, 158,  34, 159, 151,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2, 160, 161,   2,   2,   2,   2,   2,   2, 162, 163,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 108, 164,  13, 165,   2,   2,
      2,   2,   2, 166,  13,   2,   2,   2,   2,   2, 167, 168,   2,   2,   2,   2,
      2,  66, 169,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2, 170, 171,   2,   2,   2,   2,   2, 172, 173, 174,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 151,
      2,   2,   2, 147,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2, 175, 176, 177, 108, 149,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2, 178, 179,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2, 180, 181, 182,   2, 183,   2,   2,   2,   2,   2,
      2,   2,   2,   2,  76,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      5,   5,   5, 184,   5,   5,  64, 123, 185,  12,   7,   2,   2,   2,   2,   2,
    186, 187, 188,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 147,   2,   2,
      2,   2,   2,   2, 189,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 190, 191,
      2,   2,   2,   2,   2,   2,   2,   2, 192,   2,   2,   2, 193,   2,   2, 194,
      2,   2,   2,   2, 195, 196, 197, 198, 199,   2, 200,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2, 201,   2, 202,   2,   2,   2,   2, 203,   2,
      2,   2,   2,   2, 204,   2,   2,   2,   2,   2, 205, 206, 196,   2,   2,   2,
      2, 207, 208, 209,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      1,   1,   5,   5,   5,   5,   5,   5,   1,   1,   1,   1,   1,   1,   1,   1,
      5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   5,   1,
};

static RE_UINT8 re_grapheme_cluster_break_stage_4[] = {
      0,   0,   1,   2,   0,   0,   0,   0,   3,   3,   3,   3,   3,   3,   3,   4,
      3,   3,   3,   5,   6,   6,   6,   6,   7,   6,   8,   3,   9,   6,   6,   6,
      6,   6,   6,  10,  11,  10,   3,   3,  12,  13,   3,   3,   6,   6,  14,  15,
      3,   3,   7,   6,  16,   3,   3,   3,   3,  17,   6,  18,   6,  19,  20,   8,
      3,   3,   3,  21,  22,   3,   3,   3,   6,   6,  14,   3,   3,  17,   6,   6,
      6,   3,   3,   3,   3,  17,  10,   6,   6,   9,   9,   8,   3,   3,   9,   3,
      3,   6,   6,   6,  23,   6,   6,   6,  24,   3,   3,   3,   3,   3,  25,  26,
     27,   6,  28,  29,   9,   6,   3,   3,  17,   3,   3,   3,  30,   3,   3,   3,
      3,   3,   3,  31,  27,  32,  33,  34,   3,   7,   3,   3,  35,   3,   3,   3,
      3,   3,   3,  26,  36,   7,  19,   8,   8,  22,   3,   3,  27,  10,  37,  34,
      3,   3,   3,  20,   3,  17,   3,   3,  38,   3,   3,   3,   3,   3,   3,  25,
     39,  40,  41,  34,  28,   3,   3,   3,   3,   3,   3,  17,  28,  42,  20,   8,
      3,  11,   3,   3,   3,   3,   3,  43,  44,  45,  41,   8,  27,  26,  41,  46,
     40,   3,   3,   3,   3,   3,  38,   7,  47,  48,  49,  50,  51,   6,  14,   3,
      3,   7,   6,  14,  51,   6,  10,  16,   3,   3,   6,   8,   3,   3,   8,   3,
      3,  52,  22,  40,   9,   6,   6,  24,   6,  20,   3,   9,   6,   6,   9,   6,
      6,   6,   6,  16,   3,  38,   3,   3,   3,   3,   3,   9,  53,   6,  35,  36,
      3,  40,   8,  17,   9,  16,   3,   3,  38,  36,   3,  22,   3,   3,   3,  22,
     54,  54,  54,  54,  55,  55,  55,  55,  55,  55,  56,  56,  56,  56,  56,  56,
     17,  16,   3,   3,   3,  57,   6,  58,  49,  44,  27,   6,   6,   3,   3,  22,
      3,   3,   7,  59,   3,   3,  22,   3,  24,  50,  28,   3,  44,  49,  27,   3,
      3,   7,  60,   3,   3,  61,   6,  14,  48,   9,   6,  28,  50,   6,   6,  19,
      6,   6,   6,  14,   6,  62,   3,   3,   3,  53,  24,  28,  44,  62,   3,   3,
     63,   3,   3,   3,  64,  58,  57,   8,   3,  25,  58,  65,  58,   3,   3,   3,
      3,  49,  49,   6,   6,  47,   3,   3,  14,   6,   6,   6,  53,   6,  16,  22,
     40,  16,   8,   3,   6,   8,   7,   6,   3,   3,   4,  66,   3,   3,   0,  67,
      3,   3,   3,  68,   3,   3,  68,   3,   3,   3,  69,  70,   3,  71,   3,   3,
      3,   3,   3,   7,   8,   3,   3,   3,   3,   3,  17,   6,   3,   3,  11,   3,
     14,   6,   6,   8,  38,  38,   7,   3,  72,  73,   3,   3,  74,   3,   3,   3,
      3,  49,  49,  49,  49,   8,   3,   3,   3,  17,   6,   8,   3,   7,   6,   6,
     54,  54,  54,  75,   7,  47,  58,  28,  62,   3,   3,   3,   3,  22,   3,   3,
      3,   3,   9,  24,  73,  36,   3,   3,   7,   3,   3,  76,   3,   3,   3,  16,
     20,  19,  16,  17,   3,   3,  72,  58,   3,  77,   3,   3,  72,  29,  39,  34,
     78,  79,  79,  79,  79,  79,  79,  78,  79,  79,  79,  79,  79,  79,  78,  79,
     79,  78,  79,  79,  79,   3,   3,   3,  55,  80,  81,  56,  56,  56,  56,   3,
      3,   3,   3,  38,   0,   0,   0,   3,   3,  17,  14,   3,   9,  11,   3,   6,
      3,   3,  14,   7,  82,   3,   3,   3,   3,   3,   6,   6,   6,  14,   3,   3,
     50,  24,  36,  83,  14,   3,   3,   3,   3,   7,   6,  27,   6,  16,   3,   3,
      7,   3,   3,   3,  72,  47,   6,  24,  84,   3,  17,  16,   3,   3,   3,  50,
     58,  53,   3,  38,  50,   6,  14,   3,  28,  33,  33,  74,  40,  17,   6,  16,
      3,  85,   6,   6,  47,  86,   3,   3,  60,   6,  87,  65,  53,   3,   3,   3,
     47,   8,  49,  57,   3,   3,   3,   8,  50,   6,  24,  65,   3,   3,   7,  29,
      6,  57,   3,   3,  47,  57,   6,   3,   3,   3,   3,  72,   6,  14,   6,  57,
     17,   6,   6,   6,   6,   6,  64,   6,  53,  36,   3,   3,  85,  49,  49,  49,
     49,  49,  49,  49,  49,  49,  49,  88,   3,   3,   3,  11,   0,   3,   3,   3,
      3,  89,   8,  64,  90,   0,  91,   6,  14,   9,   6,   3,   3,   3,  17,   8,
      6,  14,   7,   6,   3,  16,   3,   3,   6,  14,   6,   6,   6,   6,  19,   6,
     10,  20,  14,   3,   3,   6,  14,   3,   3,  92,  93,  93,  93,  93,  93,  93,
      3,  68,   3,   3,  94,  95,  69,   3,   3,   3,  96,  97,  69,  69,  98,  98,
     95,   3,   3,   3,   3,  99, 100, 101,  98,  98,  95,  95, 102, 102, 103,   3,
      3,   3, 101,   3,   3,  68, 101,   3,  95, 104,   3,   3,   3,   3,  71,   3,
      3, 102,  94,  98,  94,   3,   3,   3,   3, 105,   3,   3,   3,   3,  98, 105,
      3, 101,   3,   3, 106,  98,  70, 105,
};

static RE_UINT8 re_grapheme_cluster_break_stage_5[] = {
     4,  4,  4,  4,  4,  4,  3,  4,  4,  2,  4,  4,  0,  0,  0,  0,
     0,  0,  0,  4,  0,  4,  0,  0,  5,  5,  5,  5,  0,  0,  0,  5,
     5,  5,  0,  0,  0,  5,  5,  5,  5,  5,  0,  5,  0,  5,  5,  0,
     1,  1,  1,  1,  1,  1,  0,  0,  5,  5,  5,  0,  4,  0,  0,  0,
     5,  0,  0,  0,  0,  0,  5,  5,  5,  1,  0,  5,  5,  0,  0,  5,
     5,  0,  5,  5,  0,  0,  0,  1,  0,  5,  0,  0,  5,  5,  1,  5,
     5,  5,  5,  7,  0,  0,  5,  7,  5,  0,  7,  7,  7,  5,  5,  5,
     5,  7,  7,  7,  7,  5,  7,  7,  0,  5,  7,  7,  5,  0,  5,  7,
     5,  0,  0,  7,  7,  0,  0,  7,  7,  5,  0,  0,  0,  5,  5,  7,
     7,  5,  5,  0,  5,  7,  0,  7,  0,  0,  5,  0,  5,  7,  7,  0,
     0,  0,  7,  7,  7,  0,  7,  7,  7,  0,  5,  5,  5,  0,  7,  5,
     7,  7,  5,  7,  7,  0,  5,  7,  7,  5,  1,  0,  7,  7,  5,  5,
     5,  0,  5,  0,  7,  7,  7,  7,  7,  7,  7,  5,  0,  5,  0,  7,
     0,  5,  0,  5,  5,  7,  5,  5,  8,  8,  8,  8,  9,  9,  9,  9,
    10, 10, 10, 10,  5,  5,  7,  5,  5,  5,  7,  7,  5,  5,  4,  0,
     5,  7,  7,  5,  0,  7,  5,  7,  7,  0,  0,  0,  5,  5,  7,  0,
     0,  7,  5,  5,  7,  5,  7,  5,  5, 15,  4,  4,  4,  4,  4,  0,
     0, 13,  0,  0,  0,  0, 13, 13, 13, 13,  0,  0, 16,  0,  0,  0,
     0,  0,  0,  7,  7,  5,  5,  7,  7,  7,  0,  0,  8,  0,  0,  0,
     5,  7,  0,  0,  0,  7,  5,  0, 11, 12, 12, 12, 12, 12, 12, 12,
     9,  9,  9,  0,  0,  0,  0, 10,  7,  5,  7,  0,  0,  1,  0,  0,
     7,  0,  1,  1,  0,  7,  7,  7,  5,  7,  5,  0,  5,  7,  5,  7,
     7,  7,  7,  0,  0,  5,  7,  5,  5,  5,  5,  4,  4,  4,  4,  5,
     0,  0,  6,  6,  6,  6,  6,  6,  0,  0,  0, 13, 13,  0,  0,  0,
     0,  0,  0, 14, 14, 14, 14, 14, 13, 13, 13, 13,  0,  0, 17, 17,
    17, 17,  0,  0,  0,  0, 13,  0,  0, 13, 13, 13,  0,  0,  0, 16,
     0, 13, 13,  0, 13, 13, 13,  0, 13,  0,  0, 13,
};

/* Grapheme_Cluster_Break: 3052 bytes. */

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
    11, 12, 13, 14, 15,  9, 16,  5, 17,  9,  9, 18,  9, 19, 20, 21,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 22, 23, 24,  9,  9, 25,
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
    26,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
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
     70,  71,  72,  73,  74,  75,  76,  77,  78,  33,  79,  33,  80,  33,  33,  33,
     17,  17,  17,  81,  82,  83,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     17,  17,  17,  17,  84,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  17,  17,  85,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  17,  17,  86,  87,  33,  33,  33,  88,
     17,  17,  17,  17,  17,  17,  17,  89,  17,  17,  90,  33,  33,  33,  33,  33,
     91,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  92,  33,  33,  33,
     33,  93,  94,  33,  95,  96,  97,  98,  33,  33,  99,  33,  33,  33,  33,  33,
    100,  33,  33,  33,  33,  33,  33,  33, 101, 102,  33,  33,  33,  33, 103,  33,
     33, 104,  33,  33,  33,  33, 105,  33,  33,  33,  33,  33,  33,  33,  33,  33,
     17,  17,  17,  17,  17,  17, 106,  17,  17,  17,  17,  17,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17, 107, 108,  17,  17,  17,  17,  17,  17,  17,
     17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17,  17, 109,  33,
     33,  33,  33,  33,  33,  33,  33,  33,  17,  17, 110,  33,  33,  33,  33,  33,
    111, 112,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,  33,
};

static RE_UINT16 re_sentence_break_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
      8,  16,  17,  18,  19,  20,  21,  22,  23,  23,  23,  24,  25,  26,  27,  28,
     29,  30,  18,   8,  31,   8,  32,   8,   8,  33,  34,  35,  36,  37,  38,  39,
     40,  41,  42,  43,  41,  41,  44,  45,  46,  47,  48,  41,  41,  49,  50,  51,
     52,  53,  54,  55,  55,  56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,
     67,  68,  69,  70,  71,  72,  73,  74,  75,  72,  76,  77,  78,  79,  80,  81,
     82,  83,  84,  85,  86,  87,  88,  89,  90,  91,  92,  93,  94,  95,  96,  97,
     98,  99, 100,  55, 101, 102, 103,  55, 104, 105, 106, 107, 108, 109, 110,  55,
     41, 111, 112, 113, 114,  29, 115, 116,  41,  41,  41,  41,  41,  41,  41,  41,
     41,  41, 117,  41, 118, 119, 120,  41, 121,  41, 122, 123, 124,  29,  29, 125,
     98,  41,  41,  41,  41,  41,  41,  41,  41,  41,  41, 126, 127,  41,  41, 128,
    129, 130, 131, 132,  41, 133, 134, 135, 136,  41,  41, 137, 138, 139,  41, 140,
    141, 142, 143, 144,  41, 145, 146,  55, 147,  41, 148, 149, 150, 151,  55,  55,
    152, 133, 153, 154, 155, 156,  41, 157,  41, 158, 159, 160, 161,  55, 162, 163,
     18,  18,  18,  18,  18,  18,  23, 164,   8,   8,   8,   8, 165,   8,   8,   8,
    166, 167, 168, 169, 167, 170, 171, 172, 173, 174, 175, 176, 177,  55, 178, 179,
    180, 181, 182,  30, 183,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,
    184, 185,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55,  55, 186,  30, 187,
     55,  55, 188, 189,  55,  55, 190, 191,  55,  55,  55,  55, 192,  55, 193, 194,
     29, 195, 196, 197,   8,   8,   8, 198,  18, 199,  41, 200, 201, 202, 202,  23,
    203, 204, 205,  55,  55,  55,  55,  55, 206, 207,  98,  41, 208,  98,  41, 116,
    209, 210,  41,  41, 211, 212,  55, 213,  41,  41,  41,  41,  41, 140,  55,  55,
     41,  41,  41,  41,  41,  41, 140,  55,  41,  41,  41,  41, 214,  55, 213, 215,
    216, 217,   8, 218, 219,  41,  41, 220, 221, 222,   8, 223, 224, 225,  55, 226,
    227, 228,  41, 229, 230, 133, 231, 232,  50, 233, 234, 235,  59, 236, 237, 238,
     41, 239, 240, 241,  41, 242, 243, 244, 245, 246, 247, 248,  18,  18,  41, 249,
     41,  41,  41,  41,  41, 250, 251, 252,  41,  41,  41, 253,  41,  41, 254,  55,
    255, 256, 257,  41,  41, 258, 259,  41,  41, 260, 213,  41, 261,  41, 262, 263,
    264, 265, 266, 267,  41,  41,  41, 268, 269,   2, 270, 271, 272, 141, 273, 274,
    275, 276, 277,  55,  41,  41,  41, 212,  55,  55,  41, 278,  55,  55,  55, 279,
     55,  55,  55,  55, 235,  41, 280, 281,  41, 213, 282, 283, 284,  41, 285,  55,
     29, 286, 287,  41, 284, 288, 289, 290,  41, 291,  41, 292,  55,  55,  55,  55,
     41, 201, 140, 262,  55,  55,  55,  55, 293, 294, 140, 201, 141,  55,  55, 295,
    140, 254,  55,  55,  41, 296,  55,  55, 297, 298, 299, 235, 235,  55, 106, 300,
     41, 140, 140, 301, 258,  55,  55,  55,  41,  41, 302,  55,  29, 303,  18, 304,
    155, 305, 306, 307, 155, 308, 309, 310, 155, 311, 312, 313, 155, 236, 314,  55,
    315, 316,  55,  55, 317, 318, 319, 320, 321,  72, 322, 323,  55,  55,  55,  55,
     41, 324, 325,  55,  41,  47, 326,  55,  55,  55,  55,  55,  41, 327, 328,  55,
     41,  47, 329,  55,  41, 330, 135,  55, 331, 332,  55,  55,  55,  55,  55,  55,
     55,  55,  55,  55,  55,  29,  18, 333,  55,  55,  55,  55,  55,  55,  41, 334,
    335, 336, 337, 338, 339, 340,  55,  55,  41,  41,  41,  41, 254,  55,  55,  55,
     41,  41,  41, 211,  41,  41,  41,  41,  41,  41, 292,  55,  55,  55,  55,  55,
     41, 211,  55,  55,  55,  55,  55,  55,  41,  41, 341,  55,  55,  55,  55,  55,
     41, 334, 141, 342,  55,  55, 213, 343,  41, 344, 345, 346, 124,  55,  55,  55,
     41,  41, 347, 348, 349,  55,  55, 350,  41,  41,  41,  41,  41,  41,  41, 214,
     41,  41,  41,  41,  41,  41,  41, 301, 351,  55,  55,  55,  55,  55,  55,  55,
     41,  41,  41, 352, 353, 354,  55,  55,  55,  55,  55, 355, 356, 357,  55,  55,
     55,  55, 358,  55,  55,  55,  55,  55, 359, 360, 361, 362, 363, 364, 365, 366,
    367, 368, 369, 370, 371, 359, 360, 372, 362, 373, 374, 375, 366, 376, 377, 378,
    379, 380, 381, 195, 382, 383, 384, 385,  23, 386,  23, 387, 388, 389,  55,  55,
    390, 391,  55,  55,  55,  55,  55,  55,  41,  41,  41,  41,  41,  41, 392,  55,
     29, 393, 394,  55,  55,  55,  55,  55, 395, 396, 397, 398, 399, 400,  55,  55,
     55, 401, 402, 402, 403,  55,  55,  55,  55,  55,  55, 404,  55,  55,  55,  55,
     41,  41,  41,  41,  41,  41, 201,  55,  41, 278,  41,  41,  41,  41,  41,  41,
    284,  41,  41,  41,  41,  41,  41,  41,  41,  41,  41,  41,  41, 351,  55,  55,
    284,  55,  55,  55,  55,  55,  55,  55, 405,  23,  23,  23,  55,  55,  55,  55,
     23,  23,  23,  23,  23,  23,  23, 406,
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
     36,  36,  36,  36,  36,  88,  36,  41,   0,   0,   0,   0,   0,  44,  44,  44,
     89,  44,  44,  44,  44,  44,  44,  44,  44,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  82,  90,  44,  44,  44,  44,  86,  44,  36,  36,
     82,  91,   7,   7,  81,  36,  36,  36,  86,  81,  36,  77,  77,  36,  36,  36,
     36,  36,  88,  36,  43,  40,  41,  90,  44,  92,  92,  93,   0,  94,   0,  95,
     82,  96,   7,   7,  41,   0,   0,   0,  58,  81,  61,  97,  77,  36,  36,  36,
     36,  36,  88,  36,  88,  98,  41,  74,  65,  94,  92,  87,  99,   0,  81,  43,
      0,  96,   7,   7,  75, 100,   0,   0,  58,  81,  36,  95,  95,  36,  36,  36,
     36,  36,  88,  36,  88,  81,  41,  90,  44,  59,  59,  87, 101,   0,   0,   0,
     82,  96,   7,   7,   0,   0,  55,   0,  58,  81,  36,  77,  77,  36,  36,  36,
     44,  92,  92,  87,   0, 102,   0,  95,  82,  96,   7,   7,  55,   0,   0,   0,
    103,  81,  61,  40,  88,  41,  98,  88,  97, 101,  61,  40,  36,  36,  41, 102,
     65, 102,  74,  87, 101,  94,   0,   0,   0,  96,   7,   7,   0,   0,   0,   0,
     44,  81,  36,  88,  88,  36,  36,  36,  36,  36,  88,  36,  36,  36,  41, 104,
     44,  74,  74,  87,   0,  60,  61,   0,  82,  96,   7,   7,   0,   0,   0,   0,
     86,  81,  36,  88,  88,  36,  36,  36,  36,  36,  88,  36,  36,  81,  41,  90,
     44,  74,  74,  87,   0,  60,   0, 105,  82,  96,   7,   7,  98,   0,   0,   0,
     58,  81,  36,  88,  88,  36,  36,  36,  36,  36,  36,  36,  36,  36,  61, 104,
     44,  74,  74,  93,   0,  67,   0,  97,  82,  96,   7,   7,   0,   0,  40,  36,
    102,  81,  36,  36,  36,  61,  40,  36,  36,  36,  36,  36,  95,  36,  36,  55,
     36,  61, 106,  94,  44, 107,  44,  44,   0,  96,   7,   7, 102,   0,   0,   0,
     81,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  80,  44,  65,   0,
     36,  67,  44,  65,   7,   7, 108,   0,  98,  77,  43,  55,   0,  36,  81,  36,
     81, 109,  40,  81,  80,  44,  59,  83,  36,  43,  44,  87,   7,   7, 108,  36,
    101,   0,   0,   0,   0,   0,  87,   0,   7,   7, 108,   0,   0, 110, 111, 112,
     36,  36,  81,  36,  36,  36,  36,  36,  36,  36,  36, 101,  58,  44,  44,  44,
     44,  74,  36,  86,  44,  44,  58,  44,  44,  44,  44,  44,  44,  44,  44, 113,
      0, 106,   0,   0,   0,   0,   0,   0,  36,  36,  67,  44,  44,  44,  44, 114,
      7,   7, 115,   0,  36,  82,  75,  82,  90,  73,  44,  75,  86,  70,  36,  36,
     82,  44,  44,  85,   7,   7, 116,  87,  11,  50,   0, 117,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  61,  36,  36,  36,  88,  41,  36,  61,  88,  41,
     36,  36,  88,  41,  36,  36,  36,  36,  36,  36,  36,  36,  88,  41,  36,  61,
     88,  41,  36,  36,  36,  61,  36,  36,  36,  36,  36,  36,  88,  41,  36,  36,
     36,  36,  36,  36,  36,  36,  61,  58, 118,   9, 119,   0,   0,   0,   0,   0,
     36,  36,  36,  36,   0,   0,   0,   0,  11,  11,  11,  11,  11, 120,  15,  39,
     36,  36,  36, 121,  36,  36,  36,  36, 122,  36,  36,  36,  36,  36, 123, 124,
     36,  36,  61,  40,  36,  36, 101,   0,  36,  36,  36,  88,  82, 113,   0,   0,
     36,  36,  36,  36,  82, 125,   0,   0,  36,  36,  36,  36,  82,   0,   0,   0,
     36,  36,  36,  88, 126,   0,   0,   0,  36,  36,  36,  36,  36,  44,  44,  44,
     44,  44,  44,  44,  44,  97,   0, 100,   7,   7, 108,   0,   0,   0,   0,   0,
    127,   0, 128, 129,   7,   7, 108,   0,  36,  36,  36,  36,  36,  36,   0,   0,
     36, 130,  36,  36,  36,  36,  36,  36,  36,  36, 131,   0,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  41,   0,   0,  36,  36,  36,  36,  36,  36,  36,  61,
     44,  44,  44,   0,  44,  44,  44,   0,   0,  91,   7,   7,  36,  36,  36,  36,
     36,  36,  36,  41,  36, 101,   0,   0,  36,  36,  36,   0,  36,  36,  36,  36,
     36,  36,  41,   0,   7,   7, 108,   0,  36,  36,  36,  36,  36,  67,  44,   0,
     36,  36,  36,  36,  36,  86,  44,  65,  44,  44,  44,  44,  44,  44,  44,  92,
      7,   7, 108,   0,   7,   7, 108,   0,   0,  97, 132,   0,  44,  44,  44,  65,
     44,  70,  36,  36,  36,  36,  36,  36,  44,  70,  36,   0,   7,   7, 115, 133,
      0,   0,  94,  44,  44,   0,   0,   0, 114,  36,  36,  36,  36,  36,  36,  36,
     86,  44,  44,  75,   7,   7,  76,  36,  36,  82,  44,  44,  44,   0,   0,   0,
     36,  44,  44,  44,  44,  44,   9, 119,   7,   7, 108,  81,   7,   7,  76,  36,
     36,  36,  36,  36,  36,  36,  36, 134,  15,  15,  42,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  65,  44,  44,  44,  44,  44,  70,  80,  82, 135,  87,   0,
     44,  44,  44,  44,  44,  87,  94,  44,  25,  25,  25,  25,  25,  34,  15,  27,
     15,  15,  11,  11,  15,  39,  11, 120,  15,  15,  11,  11,  15,  15,  11,  11,
     15,  39,  11, 120,  15,  15, 136, 136,  15,  15,  11,  11,  15,  15,  15,  39,
     15,  15,  11,  11,  15, 137,  11, 138,  46, 137,  11, 139,  15,  46,  11,   0,
     15,  15,  11, 139,  46, 137,  11, 139, 140, 140, 141, 142, 143, 144, 145, 145,
      0, 146, 147, 148,   0,   0, 149, 150,   0, 151, 150,   0,   0,   0,   0, 152,
     62, 153,  62,  62,  21,   0,   0, 154,   0,   0,   0, 149,  15,  15,  15,  42,
      0,   0,   0,   0,  44,  44,  44,  44,  44,  44,  44,  44, 113,   0,   0,   0,
     48, 155, 156, 157,  23, 117,  10, 120,   0, 158,  49, 159,  11,  38, 160,  33,
      0, 161,  39, 162,   0,   0,   0,   0, 163,  38, 101,   0,   0,   0,   0,   0,
      0,   0, 145,   0,   0,   0,   0,   0,   0,   0, 149,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 164,  11,  11,  15,  15,  39,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   4, 145, 124,   0, 145, 145, 145,   5,   0,   0,
      0, 149,   0,   0,   0,   0,   0,   0,   0, 165, 145, 145,   0,   0,   0,   0,
      4, 145, 145, 145, 145, 145, 124,   0,   0,   0,   0,   0,   0,   0, 145,   0,
      0,   0,   0,   0,   0,   0,   0,   5,  11,  11,  11,  22,  15,  15,  15,  15,
     15,  15,  15,  15,  15,  15,  15,  24,  31, 166,  26,  32,  25,  29,  15,  33,
     25,  42, 155, 167,  54,   0,   0,   0,  15, 168,   0,  21,  36,  36,  36,  36,
     36,  36,   0,  97,   0,   0,   0,  94,  36,  36,  36,  36,  36,  61,   0,   0,
     36,  61,  36,  61,  36,  61,  36,  61, 145, 145, 145,   5,   0,   0,   0,   5,
    145, 145,   5, 169,   0,   0,   0, 119, 170,   0,   0,   0,   0,   0,   0,   0,
    171,  81, 145, 145,   5, 145, 145, 172,  81,  36,  82,  44,  81,  41,  36, 101,
     36,  36,  36,  36,  36,  61,  60,  81,   0,  81,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  41,  81,  36,  36,  36,  36,  36,  36,  61,   0,   0,   0,   0,
     36,  36,  36,  36,  36,  36,  61,   0,   0,   0,   0,   0,  36,  36,  36,  36,
     36,  36,  36, 101,   0,   0,   0,   0,  36,  36,  36,  36,  36,  36,  36, 173,
     36,  36,  36, 174,  36,  36,  36,  36,   7,   7,  76,   0,   0,   0,   0,   0,
     25,  25,  25, 175,  65,  44,  44, 176,  25,  25,  25,  25,  25,  25,  25, 177,
     36,  36,  36,  36, 178,   9,   0,   0,   0,   0,   0,   0,   0,  97,  36,  36,
    179,  25,  25,  25,  27,  25,  25,  25,  25,  25,  25,  25,  15,  15,  26,  30,
     25,  25, 180, 181,  25,  27,  25,  25,  25,  25,  31,  22,  11,  25,   0,   0,
      0,   0,   0,   0,   0,  97, 182,  36, 183, 183,  67,  36,  36,  36,  36,  36,
     67,  44,   0,   0,   0,   0,   0,   0,  36,  36,  36,  36,  36, 133,   0,   0,
     75,  36,  36,  36,  36,  36,  36,  36,  44,  87,   0, 133,   7,   7, 108,   0,
     44,  44,  44,  44,  75,  36,  97,  55,  36,  82,  44, 178,  36,  36,  36,  36,
     36,  67,  44,  44,  44,   0,   0,   0,  36,  36,  36,  36,  36,  36,  36, 101,
     36,  36,  36,  36,  67,  44,  44,  44, 113,   0, 150,  97,   7,   7, 108,   0,
     36,  80,  36,  36,   7,   7,  76,  61,  36,  36,  86,  44,  44,  65,   0,   0,
     67,  36,  36,  87,   7,   7, 108, 184,  36,  36,  36,  36,  36,  61, 185,  75,
     36,  36,  36,  36,  90,  73,  70,  82, 131,   0,   0,   0,   0,   0,  97,  41,
     36,  36,  67,  44, 186, 187,   0,   0,  81,  61,  81,  61,  81,  61,   0,   0,
     36,  61,  36,  61,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  24,  15,
     15,  39,   0,   0,  15,  15,  15,  15,  67,  44, 188,  87,   7,   7, 108,   0,
     36,   0,   0,   0,  36,  36,  36,  36,  36,  61,  97,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  36,   0,  36,  36,  36,  41,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  41,   0,  15,  24,   0,   0, 189,  15,   0, 190,
     36,  36,  88,  36,  36,  61,  36,  43,  95,  88,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  41,   0,   0,   0,   0,   0,   0,   0,  97,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  36, 191,  36,  36,  36,  36,  40,  36,  36,  36,
     36,  36,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  36,  36,  36,   0,
     44,  44,  44,  44, 192,   4, 124,   0,  44,  44,  44,  44, 193, 172, 145, 145,
    145, 194, 124,   0,   6, 195, 196, 197, 143,   0,   0,   0,  36,  88,  36,  36,
     36,  36,  36,  36,  36,  36,  36, 198,  57,   0,   5,   6,   0,   0, 199,   9,
     14,  15,  15,  15,  15,  15,  16, 200, 201, 202,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  36,  82,  40,  36,  40,  36,  40,  36,  40, 101,
      0,   0,   0,   0,   0,   0, 203,   0,  36,  36,  36,  81,  36,  36,  36,  36,
     36,  61,  36,  36,  36,  36,  61,  95,  36,  36,  36,  41,  36,  36,  36,  41,
     36,  36,  36,  36,  36, 101,   0,   0,   0,   0,   0,   0,   0,   0,   0,  99,
     36,  36,  36,  36, 101,   0,   0,   0, 113,   0,   0,   0,   0,   0,   0,   0,
     36,  36,  61,   0,  36,  36,  36,  36,  36,  36,  36,  36,  36,  82,  65,   0,
     36,  36,  36,  36,  36,  36,  36,  41,  36,   0,  36,  36,  81,  41,   0,   0,
     11,  11,  15,  15,  15,  15,  15,  15,  15,  15,  15,  15,  36,  36,  36,  36,
      7,   7, 108,   0,  11,  11,  11,  11,  11,  11,  11,  11,  11,   0,  15,  15,
     15,  15,  15,  15,  15,  15,  15,   0,  36,  36,   0,   0,  36,  36,  36,  36,
     36,   0,   0,   0,   0,   0,   0,   0,  36,  41,  88,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  95, 101,  77,  36,  36,  36,  36,  61,  41,   0,   0,
     36,  36,  36,  36,  36,  36,   0,  40,  86,  60,   0,  44,  36,  81,  81,  36,
     36,  36,  36,  36,  36,   0,  65,  94,   0,   0,   0,   0,   0, 133,   0,   0,
     36, 187,   0,   0,   0,   0,   0,   0,  36,  36,  36,  36,  61,   0,   0,   0,
     36,  36, 101,   0,   0,   0,   0,   0,  11,  11,  11,  11,  22,   0,   0,   0,
     15,  15,  15,  15,  24,   0,   0,   0,  36,  36,  36,  36,  36,  36,  44,  44,
     44, 188, 119,   0,   0,   0,   0,   0,   0,  96,   7,   7,   0,   0,   0,  94,
     36,  36,  36,  36,  44,  44,  65, 204, 150,   0,   0,   0,  36,  36,  36,  36,
     36,  36, 101,   0,   7,   7, 108,   0,  36,  67,  44,  44,  44, 205,   7,   7,
    184,   0,   0,   0,  36,  36,  36,  36,  36,  36,  36,  36,  67, 105,   0,   0,
     70, 206, 102, 207,   7,   7, 208, 174,  36,  36,  36,  36,  95,  36,  36,  36,
     36,  36,  36,  44,  44,  44, 209, 210,  36,  61,  88,  95,  36,  36,  36,  95,
     36,  36, 211,   0,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  36,  67,
     44,  44,  65,   0,   7,   7, 108,   0,  44,  81,  36,  77,  77,  36,  36,  36,
     44,  92,  92,  87, 101,  94,   0,  81,  82, 102,  44, 113,  44, 113,   0,   0,
     36,  36,  36,  36,  36,  86,  44,  44,  44, 114, 212, 119,   7,   7, 108,   0,
     44,  95,   0,   0,   7,   7, 108,   0,  36,  36,  36,  67,  44,  87,  44,  44,
    213,   0, 184, 132, 132, 132,  36,  87, 125, 101,   0,   0,   7,   7, 108,   0,
     36,  36,  67,  44,  44,  44,   0,   0,  36,  36,  36,  36,  36,  36,  41,  58,
     44,  44,  44,   0,   7,   7, 108,  78,   7,   7, 108,   0,   0,   0,   0,  97,
     36,  36,  36,  36,  36,  36, 101,   0,  36,  36,  88,  36,  36,  36,  36,  36,
     36,  36,  36,  67,  44,  65,  44,  44, 206,   0,   0,   0,   7,   7, 108,   0,
      0,   0,   0,   0,  40,  36,  36,  36,  36,  36,  36,  36, 102,  44,  44,  44,
     44,  44,  58,  44,  44,  65,   0,   0,  36,  61,   0,   0,   0,   0,   0,   0,
      7,   7, 108, 133,   0,   0,   0,   0,  36,  36,  36,  41,  44, 207,   0,   0,
     36,  36,  36,  36,  44, 188, 119,   0,  36, 119,   0,   0,   7,   7, 108,   0,
     97,  36,  36,  36,  36,  36,   0,  81,  36, 101,   0,   0,  86,  44,  44,  44,
     44,  44,  44,  44,  44,  44,  44,  65,   0,   0,   0,  94, 114,  36,  36,  36,
    101,   0,   0,   0,   0,   0,   0,   0,  41,   0,   0,   0,   0,   0,   0,   0,
     36,  36,  61,   0,  36,  36,  36, 101,  36,  36, 101,   0,  36,  36,  41, 214,
     62,   0,   0,   0,   0,   0,   0,   0,   0,  58,  87,  58, 215,  62, 216,  44,
     65,  58,  44,   0,   0,   0,   0,   0,   0,   0, 102,  87,   0,   0,   0,   0,
    102, 113,   0,   0,   0,   0,   0,   0,  11,  11,  11,  11,  11,  11, 157,  15,
     15,  15,  15,  15,  15,  11,  11,  11,  11,  11,  11, 157,  15, 137,  15,  15,
     15,  15,  11,  11,  11,  11,  11,  11, 157,  15,  15,  15,  15,  15,  15,  49,
     48, 217,  10,  49,  11, 157, 168,  14,  15,  14,  15,  15,  11,  11,  11,  11,
     11,  11, 157,  15,  15,  15,  15,  15,  15,  50,  22,  10,  11,  49,  11, 218,
     15,  15,  15,  15,  15,  15,  50,  22,  11, 158, 164,  11, 218,  15,  15,  15,
     15,  15,  15,  11,  11,  11,  11,  11,  11, 157,  15,  15,  15,  15,  15,  15,
     11,  11,  11, 157,  15,  15,  15,  15, 157,  15,  15,  15,  15,  15,  15,  11,
     11,  11,  11,  11,  11, 157,  15,  15,  15,  15,  15,  15,  11,  11,  11,  11,
     15,  39,  11,  11,  11,  11,  11,  11, 218,  15,  15,  15,  15,  15,  24,  15,
     33,  11,  11,  11,  11,  11,  22,  15,  15,  15,  15,  15,  15, 137,  15,  11,
     11,  11,  11,  11,  11, 218,  15,  15,  15,  15,  15,  24,  15,  33,  11,  11,
     15,  15, 137,  15,  11,  11,  11,  11,  11,  11, 218,  15,  15,  15,  15,  15,
     24,  15,  27,  96,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
     44,  44,  44,  44,  44,  65,  94,  44,  44,  44,  44, 113,   0,  99,   0,   0,
      0, 113, 119,   0,   0,   0,  94,  44,  58,  44,  44,  44,   0,   0,   0,   0,
     44,  65,  44,  44,  44,  44,  92,  44,  59,  74,  65,   0,   0,   0,   0,   0,
     36, 101,   0,   0,  44,  65,   0,   0, 157,  15,  15,  15,  15,  15,  15,  15,
     15,  44,  65,   0,   7,   7, 108,   0,  36,  81,  36,  36,  36,  36,  36,  36,
     98,  77,  81,  36,  61,  36, 109,   0, 105,  97, 109,  81,  98,  77, 109, 109,
     98,  77,  61,  36,  61,  36,  81,  43,  36,  36,  95,  36,  36,  36,  36,   0,
     81,  81,  95,  36,  36,  36,  36,   0,   0,   0,   0,   0,  11,  11,  11,  11,
     11,  11, 120,   0,  11,  11,  11,  11,  11,  11, 120,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 165, 124,   0,  20,   0,   0,   0,   0,   0,   0,   0,
     44,  44,  44,  44,   0,   0,   0,   0,
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
     9,  0,  9,  9,  3,  3,  5,  3,  3,  9,  3,  3, 12, 12, 10, 10,
     3,  0,  0,  3,  3,  3,  9,  0,  0,  0,  0,  3,  9,  9,  0,  9,
     0,  0, 10, 10,  0,  0,  0,  9,  0,  9,  9,  0,  0,  3,  0,  0,
     9,  3,  0,  0,  9,  0,  0,  0,  0,  0,  3,  3,  0,  0,  3,  9,
     0,  9,  3,  3,  0,  0,  9,  0,  0,  0,  3,  0,  3,  0,  3,  0,
    10, 10,  0,  0,  0,  9,  0,  9,  0,  3,  0,  3,  0,  3, 13, 13,
    13, 13,  3,  3,  3,  0,  0,  0,  3,  3,  3,  9, 10, 10, 12, 12,
    10, 10,  3,  3,  0,  8,  0,  0,  0,  0, 12,  0, 12,  0,  0,  0,
     8,  8,  0,  0,  9,  0, 12,  9,  6,  9,  9,  9,  9,  9,  9, 13,
    13,  0,  0,  0,  3, 12, 12,  0,  9,  0,  3,  3,  0,  0, 14, 12,
    14, 12,  0,  3,  3,  3,  5,  0,  9,  3,  3,  9,  9,  3,  9,  0,
    12, 12, 12, 12,  0,  0, 12, 12,  9,  9, 12, 12,  3,  9,  9,  0,
     0,  8,  0,  8,  7,  0,  7,  7,  8,  0,  7,  0,  8,  0,  0,  0,
     6,  6,  6,  6,  6,  6,  6,  5,  3,  3,  5,  5,  0,  0,  0, 14,
    14,  0,  0,  0, 13, 13, 13, 13, 11,  0,  0,  0,  4,  4,  5,  5,
     5,  5,  5,  6,  0, 13, 13,  0, 12, 12,  0,  0,  0, 13, 13, 12,
     0,  0,  0,  6,  5,  0,  5,  5,  0, 13, 13,  7,  0,  0,  0,  8,
     0,  0,  7,  8,  8,  8,  7,  7,  8,  0,  8,  0,  8,  8,  0,  7,
     9,  7,  0,  0,  0,  8,  7,  7,  0,  0,  7,  0,  9,  9,  9,  8,
     0,  0,  8,  8,  0,  0, 13, 13,  8,  7,  7,  8,  7,  8,  7,  3,
     7,  7,  0,  7,  0,  0, 12,  9,  0,  0, 13,  0,  6, 14, 12,  0,
     0, 13, 13, 13,  9,  9,  0, 12,  9,  0, 12, 12,  8,  7,  9,  3,
     3,  3,  0,  9,  7,  7,  3,  3,  3,  3,  0, 12,  0,  0,  8,  7,
     9,  0,  0,  8,  7,  8,  7,  9,  7,  7,  7,  9,  9,  9,  3,  9,
     0, 12, 12, 12,  0,  0,  9,  3, 12, 12,  9,  9,  9,  3,  3,  0,
     3,  3,  3, 12,  0,  0,  0,  7,  0,  9,  3,  9,  9,  9, 13, 13,
    14, 14,  0, 14,  0, 14, 14,  0, 13,  0,  0, 13,  0, 14, 12, 12,
    14, 13, 13, 13, 13, 13, 13,  0,  9,  0,  0,  5,  0,  0, 14,  0,
     0, 13,  0, 13, 13, 12, 13, 13, 14,  0,  9,  9,  0,  5,  5,  5,
     0,  5, 12, 12,  3,  0, 10, 10,  9, 12, 12,  0,  3, 12,  0,  0,
    10, 10,  9,  0, 12, 12,  0, 12, 12,  0,  3,  0,  9, 12,  0,  0,
     9,  9,  9, 12,  3,  0, 12, 12,  0,  3,  3, 12,  3,  3,  3,  5,
     5,  5,  5,  3,  0,  8,  8,  0,  8,  0,  7,  7,
};

/* Sentence_Break: 6644 bytes. */

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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 13, 28, 29, 30, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 31,  7, 32, 33,  7, 34, 13, 13, 13, 13, 13, 35,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_alphabetic_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  32,  31,  31,  31,  31,  31,  31,  31,  33,  34,  35,  31,
     36,  37,  31,  31,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  38,   1,   1,   1,   1,   1,   1,   1,   1,   1,  39,
      1,   1,   1,   1,  40,   1,  41,  42,  43,  44,  45,  46,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  47,  31,  31,  31,  31,  31,  31,  31,  31,
     31,   1,  48,  49,   1,  50,  51,  52,  53,  54,  55,  56,  57,  58,   1,  59,
     60,  61,  62,  63,  64,  31,  31,  31,  65,  66,  67,  68,  69,  70,  71,  72,
     73,  31,  74,  31,  75,  31,  31,  31,   1,   1,   1,  76,  77,  78,  31,  31,
      1,   1,   1,   1,  79,  31,  31,  31,  31,  31,  31,  31,   1,   1,  80,  31,
      1,   1,  81,  82,  31,  31,  31,  83,   1,   1,   1,   1,   1,   1,   1,  84,
      1,   1,  85,  31,  31,  31,  31,  31,  86,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  87,  31,  31,  31,  31,  31,  31,  31,  88,  89,  90,  91,
     92,  31,  31,  31,  31,  31,  31,  31,  93,  94,  31,  31,  31,  31,  95,  31,
     31,  96,  31,  31,  31,  31,  31,  31,   1,   1,   1,   1,   1,   1,  97,   1,
      1,   1,   1,   1,   1,   1,   1,  98,  99,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1, 100,  31,   1,   1, 101,  31,  31,  31,  31,  31,
};

static RE_UINT8 re_alphabetic_stage_4[] = {
      0,   0,   1,   1,   0,   2,   3,   3,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   5,   6,   0,   0,   7,   8,   9,  10,   4,  11,
      4,   4,   4,   4,  12,   4,   4,   4,   4,  13,  14,  15,  16,  17,  18,  19,
     20,   4,  21,  22,   4,   4,  23,  24,  25,   4,  26,   4,   4,  27,  28,  29,
     30,  31,  32,   0,   0,  33,  34,  35,   4,  36,  37,  38,  39,  40,  41,  42,
     43,  44,  45,  46,  47,  48,  49,  50,  51,  48,  52,  53,  54,  55,  56,   0,
     57,  58,  59,  60,  57,  61,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,
     15,  72,  73,   0,  74,  75,  76,   0,  77,   0,  78,  79,  80,  81,   0,   0,
      4,  82,  25,  83,  84,   4,  85,  86,   4,   4,  87,   4,  88,  89,  90,   4,
     91,   4,  92,   0,  93,   4,   4,  94,  15,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,  95,   1,   4,   4,  96,  97,  98,  98,  99,   4, 100, 101,   0,
      0,   4,   4, 102,   4, 103,   4, 104, 105, 106,  25, 107,   4, 108, 109,   0,
    110,   4, 105, 111,   0, 112,   0,   0,   4, 113, 114,   0,   4, 115,   4, 116,
      4, 104, 117, 118, 119,   0,   0, 120,   4,   4,   4,   4,   4,   4,   0, 121,
     94,   4, 122, 118,   4, 123, 124, 125,   0,   0,   0, 126, 127,   0,   0,   0,
    128, 129, 130,   4, 119,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 131,   4, 109,   4, 132, 105,   4,   4,   4,   4, 133,
      4,  85,   4, 134, 135, 136, 136,   4,   0, 137,   0,   0,   0,   0,   0,   0,
    138, 139,  15,   4, 140,  15,   4,  86, 141, 142,   4,   4, 143,  72,   0,  25,
      4,   4,   4,   4,   4, 104,   0,   0,   4,   4,   4,   4,   4,   4, 104,   0,
      4,   4,   4,   4,  31,   0,  25, 118, 144, 145,   4, 146,   4,   4,   4,  93,
    147, 148,   4,   4, 149, 150,   0, 147, 151,  16,   4,  98,   4,   4, 152, 153,
     28, 103, 154,  81,   4, 155, 137, 156,   4, 135, 157, 158,   4, 105, 159, 160,
    161, 162,  86, 163,   4,   4,   4, 164,   4,   4,   4,   4,   4, 165, 166, 110,
      4,   4,   4, 167,   4,   4, 168,   0, 169, 170, 171,   4,   4,  27, 172,   4,
      4, 118,  25,   4, 173,   4,  16, 174,   0,   0,   0, 175,   4,   4,   4,  81,
      0,   1,   1, 176,   4, 105, 177,   0, 178, 179, 180,   0,   4,   4,   4,  72,
      0,   0,   4, 181,   0,   0,   0,   0,   0,   0,   0,   0,  81,   4, 182,   0,
      4,  25, 103,  72, 118,   4, 183,   0,   4,   4,   4,   4, 118,  25, 184, 110,
      4, 185,   4,  60,   0,   0,   0,   0,   4, 135, 104,  16,   0,   0,   0,   0,
    186, 187, 104, 135, 105,   0,   0, 188, 104, 168,   0,   0,   4, 189,   0,   0,
    190,  98,   0,  81,  81,   0,  78, 191,   4, 104, 104, 154,  27,   0,   0,   0,
      4,   4, 119,   0,   4, 154,   4, 154,   4,   4, 192,   0, 148,  32,  25, 119,
      4, 154,  25, 193,   4,   4, 194,   0, 195, 196,   0,   0, 197, 198,   4, 119,
     39,  48, 199,  60,   0,   0,   0,   0,   4,   4, 200,   0,   4,   4, 201,   0,
      0,   0,   0,   0,   4, 202, 203,   0,   4, 105, 204,   0,   4, 104,   0,   0,
    205, 164,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4,   4, 206,
      0,   0,   0,   0,   0,   0,   4,  32, 207, 208,  77, 209, 173, 210,   0,   0,
      4,   4,   4,   4, 168,   0,   0,   0,   4,   4,   4, 143,   4,   4,   4,   4,
      4,   4,  60,   0,   0,   0,   0,   0,   4, 143,   0,   0,   0,   0,   0,   0,
      4,   4, 211,   0,   0,   0,   0,   0,   4,  32, 105,   0,   0,   0,  25, 157,
      4, 135,  60, 212,  93,   0,   0,   0,   4,   4, 213, 105, 172,   0,   0,  77,
      4,   4,   4,   4,   4,   4,   4,  31,   4,   4,   4,   4,   4,   4,   4, 154,
    214,   0,   0,   0,   0,   0,   0,   0,   4,   4,   4, 215, 216,   0,   0,   0,
      4,   4, 217,   4, 218, 219, 220,   4, 221, 222, 223,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4, 224, 225,  86, 217, 217, 132, 132, 207, 207, 226,   0,
    227, 228,   0,   0,   0,   0,   0,   0,   4,   4,   4,   4,   4,   4, 191,   0,
      4,   4, 229,   0,   0,   0,   0,   0, 220, 230, 231, 232, 233, 234,   0,   0,
      0,  25, 235, 235, 109,   0,   0,   0,   4,   4,   4,   4,   4,   4, 135,   0,
      4, 181,   4,   4,   4,   4,   4,   4, 118,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4, 214,   0,   0, 118,   0,   0,   0,   0,   0,   0,   0,
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
    255, 255, 255,   1, 255, 255, 223,  63,   0,   0, 240, 255, 248,   3, 255, 255,
    255, 255, 255, 239, 255, 223, 225, 255,  15,   0, 254, 255, 239, 159, 249, 255,
    255, 253, 197, 227, 159,  89, 128, 176,  15,   0,   3,   0, 238, 135, 249, 255,
    255, 253, 109, 195, 135,  25,   2,  94,   0,   0,  63,   0, 238, 191, 251, 255,
    255, 253, 237, 227, 191,  27,   1,   0,  15,   0,   0,   2, 238, 159, 249, 255,
    159,  25, 192, 176,  15,   0,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195,
    199,  29, 129,   0, 239, 223, 253, 255, 255, 253, 255, 227, 223,  29,  96,   7,
     15,   0,   0,   0, 255, 253, 239, 227, 223,  29,  96,  64,  15,   0,   6,   0,
    238, 223, 253, 255, 255, 255, 255, 231, 223,  93, 240, 128,  15,   0,   0, 252,
    236, 255, 127, 252, 255, 255, 251,  47, 127, 128,  95, 255,   0,   0,  12,   0,
    255, 255, 255,   7, 127,  32,   0,   0, 150,  37, 240, 254, 174, 236, 255,  59,
     95,  32,   0, 240,   1,   0,   0,   0, 255, 254, 255, 255, 255,  31, 254, 255,
      3, 255, 255, 254, 255, 255, 255,  31, 255, 255, 127, 249, 231, 193, 255, 255,
    127,  64,   0,  48, 191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61,
    255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255,
    255, 255, 255, 135, 255, 255,   0,   0, 255, 255,  63,  63, 255, 159, 255, 255,
    255, 199, 255,   1, 255, 223,  15,   0, 255, 255,  15,   0, 255, 223,  13,   0,
    255, 255, 207, 255, 255,   1, 128,  16, 255, 255, 255,   0, 255,   7, 255, 255,
    255, 255,  63,   0, 255, 255, 255, 127, 255,  15, 255,   1, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3,   0,   0, 255, 255, 255,  15, 254, 255,  31,   0,
    128,   0,   0,   0, 255, 255, 239, 255, 239,  15,   0,   0, 255, 243,   0, 252,
    191, 255,   3,   0,   0, 224,   0, 252, 255, 255, 255,  63, 255,   1,   0,   0,
      0, 222, 111,   0, 128, 255,  31,   0,  63,  63, 255, 170, 255, 255, 223,  95,
    220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   2, 128,   0,   0, 255,  31,
    132, 252,  47,  62,  80, 189, 255, 243, 224,  67,   0,   0,   0,   0, 192, 255,
    255, 127, 255, 255,  31, 120,  12,   0, 255, 128,   0,   0, 255, 255, 127,   0,
    127, 127, 127, 127,   0, 128,   0,   0, 224,   0,   0,   0, 254,   3,  62,  31,
    255, 255, 127, 224, 224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0,
    255,  31, 255, 255,   0,  12,   0,   0, 255, 127, 240, 143,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0, 187, 247, 255, 255,
     47,   0,   0,   0,   0,   0, 252,  40, 255, 255,   7,   0, 255, 255, 247, 255,
    223, 255,   0, 124, 255,  63,   0,   0, 255, 255, 127, 196,   5,   0,   0,  56,
    255, 255,  60,   0, 126, 126, 126,   0, 127, 127, 255, 255,  63,   0, 255, 255,
    255,   7,   0,   0,  15,   0, 255, 255, 127, 248, 255, 255, 255,  63, 255, 255,
    255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95, 219, 255, 255, 255,
      0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,   0,   0, 223, 255,
    192, 255, 255, 255, 252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183,
    255,  63, 255,  63, 255, 255,  31,   0, 255, 255,   1,   0,  15, 255,  62,   0,
    255, 255,  15, 255, 255,   0, 255, 255,  63, 253, 255, 255, 255, 255, 191, 145,
    255, 255,  55,   0, 255, 255, 255, 192, 111, 240, 239, 254,  31,   0,   0,   0,
     63,   0,   0,   0, 255, 255,  71,   0,  30,   0,   0,  20, 255, 255, 251, 255,
    255, 255, 159,  64, 127, 189, 255, 191, 255,   1, 255, 255, 159,  25, 129, 224,
    187,   7,   0,   0, 179,   0,   0,   0, 255, 255,  63, 127,   0,   0,   0,  63,
     17,   0,   0,   0, 255, 255, 255, 227,   0,   0,   0, 128, 255, 253, 255, 255,
    255, 255, 127, 127,   0,   0, 252, 255, 255, 254, 127,   0, 127,   0,   0,   0,
    248, 255, 255, 224,  31,   0, 255, 255,   3,   0,   0,   0, 255,   7, 255,  31,
    255,   1, 255,  67, 255, 255, 223, 255, 255, 255, 255, 223, 100, 222, 255, 235,
    239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,  95, 252, 253, 255,
     63, 255, 255, 255, 253, 255, 255, 247, 247,  15,   0,   0, 127, 255, 255, 249,
    219,   7,   0,   0, 143,   0,   0,   0, 150, 254, 247,  10, 132, 234, 150, 170,
    150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15, 255,   3, 255, 255,
};

/* Alphabetic: 2193 bytes. */

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
     0,  1,  2,  3,  4,  5,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  6,  7,  1,  1,  1,  1,  1,  1,  1,  1,  1,  8,
     9, 10,  1, 11,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 12,  1,  1, 13,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_lowercase_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  7,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9, 10, 11,
    12, 13,  6,  6, 14,  6,  6,  6,  6,  6,  6,  6, 15, 16,  6,  6,
     6,  6,  6,  6,  6,  6, 17, 18,  6,  6,  6, 19,  6,  6,  6,  6,
     6,  6,  6, 20,  6,  6,  6, 21,  6,  6,  6,  6, 22,  6,  6,  6,
     6,  6,  6,  6, 23,  6,  6,  6, 24,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6, 25, 26, 27, 28,  6, 29,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_lowercase_stage_4[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
     5, 13, 14, 15, 16, 17, 18, 19,  0,  0, 20, 21, 22, 23, 24, 25,
     0, 26, 15,  5, 27,  5, 28,  5,  5, 29,  0, 30, 31,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 32,
     0,  0,  0,  0, 33,  0,  0,  0, 15, 15, 15, 15, 15, 15,  0,  0,
     5,  5,  5,  5, 34,  5,  5,  5, 35, 36, 37, 38, 36, 39, 40, 41,
     0,  0,  0, 42, 43,  0,  0,  0, 44, 45, 46, 26, 47,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 26, 48,  0, 26, 49, 50,  5,  5,  5, 51,
    15, 52,  0,  0,  0,  0,  0,  0,  0,  0,  5, 53, 54,  0,  0,  0,
     0, 55,  5, 56, 57, 58,  0, 59,  0, 26, 60, 61, 15, 15,  0,  0,
    62,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,
     0, 63, 64,  0,  0,  0, 65, 66,  0,  0,  0,  0,  0,  0, 15, 67,
     0,  0,  0,  0,  0,  0, 15,  0, 68, 69, 70, 31, 71, 72, 73, 74,
    75, 76, 77, 78, 79, 68, 69, 80, 31, 71, 81, 64, 74, 82, 83, 84,
    85, 81, 86, 26, 87, 74, 88,  0,  0, 89, 90,  0,  0,  0,  0,  0,
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
      0,   0,   0,  63, 255,   1,   0,   0, 170, 170, 234, 191, 255,   0,  63,   0,
    255,   0, 255,   0,  63,   0, 255,   0, 255,   0, 255,  63, 255,   0, 223,  64,
    220,   0, 207,   0, 255,   0, 220,   0,   0,   0,   2, 128,   0,   0, 255,  31,
      0, 196,   8,   0,   0, 128,  16,  50, 192,  67,   0,   0,  16,   0,   0,   0,
    255,   3,   0,   0, 255, 255, 255, 127,  98,  21, 218,  63,  26,  80,   8,   0,
    191,  32,   0,   0, 170,  42,   0,   0, 170, 170, 170,  58, 168, 170, 171, 170,
    170, 170, 255, 149, 170,  80, 186, 170, 170,   2, 160,   0,   0,   0,   0,   7,
    255, 255, 255, 247,  63,   0, 255, 255, 127,   0, 248,   0,   0, 255, 255, 255,
    255, 255,   0,   0,   0,   0,   0, 255, 255, 255, 255,  15, 255, 255,   7,   0,
      0,   0,   0, 252, 255, 255,  15,   0,   0, 192, 223, 255, 252, 255, 255,  15,
      0,   0, 192, 235, 239, 255,   0,   0,   0, 252, 255, 255,  15,   0,   0, 192,
    255, 255, 255,   0,   0,   0, 252, 255, 255,  15,   0,   0, 192, 255, 255, 255,
      0, 192, 255, 255,   0,   0, 192, 255,  63,   0,   0,   0, 252, 255, 255, 247,
      3,   0,   0, 240, 255, 255, 223,  15, 255, 127,  63,   0, 255, 253,   0,   0,
    247,  11,   0,   0, 252, 255, 255, 255,  15,   0,   0,   0,
};

/* Lowercase: 829 bytes. */

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
     8,  9,  1, 10,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 11,  1,  1, 12, 13,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_uppercase_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  9, 10,
     6, 11,  6,  6, 12,  6,  6,  6,  6,  6,  6,  6, 13,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 14, 15,  6,  6,  6,  6,  6,  6,  6, 16,
     6,  6,  6,  6, 17,  6,  6,  6,  6,  6,  6,  6, 18,  6,  6,  6,
    19,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 20, 21, 22, 23,
     6, 24,  6,  6,  6,  6,  6,  6,  6, 25,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_uppercase_stage_4[] = {
     0,  0,  1,  0,  0,  0,  2,  0,  3,  4,  5,  6,  7,  8,  9, 10,
     3, 11, 12,  0,  0,  0,  0,  0,  0,  0,  0, 13, 14, 15, 16, 17,
    18, 19,  0,  3, 20,  3, 21,  3,  3, 22, 23,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18, 24,  0,
     0,  0,  0,  0,  0, 18, 18, 25,  3,  3,  3,  3, 26,  3,  3,  3,
    27, 28, 29, 30,  0, 31, 32, 33, 34, 35, 36, 19, 37,  0,  0,  0,
     0,  0,  0,  0,  0, 38, 19,  0, 18, 39,  0, 40,  3,  3,  3, 41,
     0,  0,  3, 42, 43,  0,  0,  0,  0, 44,  3, 45, 46, 47,  0,  0,
     0,  1,  0,  0,  0,  0,  0,  0, 18, 48,  0,  0,  0, 49, 50,  0,
     0,  0,  0,  0, 18, 51,  0,  0,  0,  0,  0,  0,  0, 18,  0,  0,
    52, 53, 54, 55, 56, 57, 49, 58, 59, 60, 61, 62, 63, 52, 53, 54,
    55, 64, 25, 49, 58, 55, 65, 66, 67, 68, 38, 39, 49, 69, 70,  0,
    18, 71,  0,  0,  0,  0,  0,  0,  0, 49, 72, 72, 58,  0,  0,  0,
};

static RE_UINT8 re_uppercase_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7, 255, 255, 127, 127,  85,  85,  85,  85,
     85,  85,  85, 170, 170,  84,  85,  85,  85,  85,  85,  43, 214, 206, 219, 177,
    213, 210, 174,  17, 144, 164, 170,  74,  85,  85, 210,  85,  85,  85,   5, 108,
    122,  85,   0,   0,   0,   0,  69, 128,  64, 215, 254, 255, 251,  15,   0,   0,
      0, 128,  28,  85,  85,  85, 144, 230, 255, 255, 255, 255, 255, 255,   0,   0,
      1,  84,  85,  85, 171,  42,  85,  85,  85,  85, 254, 255, 255, 255, 127,   0,
    191,  32,   0,   0, 255, 255,  63,   0,  85,  85,  21,  64,   0, 255,   0,  63,
      0, 255,   0, 255,   0,  63,   0, 170,   0, 255,   0,   0,   0,   0,   0,  15,
      0,  15,   0,  15,   0,  31,   0,  15, 132,  56,  39,  62,  80,  61,  15, 192,
     32,   0,   0,   0,   8,   0,   0,   0,   0,   0, 192, 255, 255, 127,   0,   0,
    157, 234,  37, 192,   5,  40,   4,   0,  85,  21,   0,   0,  85,  85,  85,   5,
     84,  85,  84,  85,  85,  85,   0, 106,  85,  40,  69,  85,  85, 125,  95,   0,
    255,   0,   0,   0,   0,   0, 255, 255, 255, 255,  15,   0, 255, 255,   7,   0,
    255, 255, 255,   3,   0,   0, 240, 255, 255,  63,   0,   0,   0, 255, 255, 255,
      3,   0,   0, 208, 100, 222,  63,   0, 255,   3,   0,   0, 176, 231, 223,  31,
      0,   0,   0, 123,  95, 252,   1,   0,   0, 240, 255, 255,  63,   0,   0,   0,
      3,   0,   0, 240,   1,   0,   0,   0, 252, 255, 255,   7,   0,   0,   0, 240,
    255, 255,  31,   0, 255,   1,   0,   0,   0,   4,   0,   0,   3,   0,   0,   0,
    255,   3, 255, 255,
};

/* Uppercase: 725 bytes. */

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
    0, 1, 2, 3, 4, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1,
};

static RE_UINT8 re_cased_stage_2[] = {
     0,  1,  2,  2,  3,  2,  2,  4,  5,  6,  2,  7,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  8,  9,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2, 10, 11,
     2, 12,  2, 13,  2,  2, 14,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2, 15,  2,  2,  2,  2, 16,  2, 17,  2,  2,  2,
};

static RE_UINT8 re_cased_stage_3[] = {
     0,  1,  2,  3,  2,  4,  5,  6,  2,  7,  8,  9, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 11, 10, 10, 10, 10, 10, 12,
    10, 13,  2, 14,  2,  2, 15, 16, 17, 18, 19, 20, 10, 10, 10, 10,
    10, 21, 10, 10, 10, 10, 10, 10, 22, 23, 24, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 25, 26, 27, 28, 10, 10, 10, 10, 10, 10, 29, 14,
    10, 10, 10, 10, 10, 10, 30, 10, 10, 10, 10, 10, 10, 10, 31, 10,
    32, 33, 10, 10, 10, 10, 10, 10, 10, 34, 10, 10, 10, 10, 10, 10,
    10, 35, 10, 10, 10, 10, 10, 10, 36, 37, 38,  2,  2, 39, 40, 41,
    10, 10, 42, 10, 10, 10, 10, 10, 10, 10, 43, 44, 10, 10, 10, 10,
};

static RE_UINT8 re_cased_stage_4[] = {
     0,  0,  1,  1,  0,  2,  3,  3,  4,  4,  4,  4,  4,  5,  6,  4,
     7,  8,  9, 10,  0,  0, 11, 12, 13, 14,  4, 15, 16,  4,  4,  4,
     4, 17, 18, 19, 20,  0,  0,  0,  0,  0,  0,  0,  0,  4, 21,  0,
     0,  4,  4, 22, 23,  0,  0,  0,  4,  4,  0,  0, 22,  4, 24, 25,
     4, 26, 27, 28,  0,  0,  0, 29, 30,  0,  0,  0, 31, 32, 33,  4,
    34,  0,  0,  0,  0, 35,  4, 36,  4, 37, 38,  4,  4,  4,  4, 39,
     4, 21,  0,  0,  0,  0,  4, 40, 25,  0,  0,  0,  0, 41,  4,  4,
    42, 43,  0, 44,  0, 45,  5, 46, 47,  0,  0,  0,  0,  1,  1,  0,
     4,  4, 48,  0,  0, 45, 49, 50,  4, 51,  4, 51,  0,  4,  4,  0,
     4,  4, 52,  4, 53, 54, 55,  4, 56, 57, 58,  4,  4, 59, 60,  5,
    52, 52, 37, 37, 61, 61, 62,  0,  4,  4, 63,  0,  0, 45, 64, 64,
    36,  0,  0,  0,
};

static RE_UINT8 re_cased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 255, 255, 255, 247, 240, 255, 255, 255, 255, 255, 239, 255,
    255, 255, 255,   1,   3,   0,   0,   0,  31,   0,   0,   0,  32,   0,   0,   0,
      0,   0, 207, 188,  64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,
      3, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   0, 254, 255, 255, 255,
    255,   0,   0,   0, 191,  32,   0,   0, 255, 255,  63,  63, 255,   1,   0,   0,
     63,  63, 255, 170, 255, 255, 255,  63, 255, 255, 223,  95, 220,  31, 207,  15,
    255,  31, 220,  31,   0,   0,   2, 128,   0,   0, 255,  31, 132, 252,  47,  62,
     80, 189,  31, 242, 224,  67,   0,   0,  24,   0,   0,   0,   0,   0, 192, 255,
    255,   3,   0,   0, 255, 127, 255, 255, 255, 255, 255, 127,  31, 120,  12,   0,
    255,  63,   0,   0, 252, 255, 255, 255, 255, 120, 255, 255, 255, 127, 255,   0,
      0,   0,   0,   7,   0,   0, 255, 255,  63,   0, 255, 255, 127,   0, 248,   0,
    255, 255,   0,   0, 255, 255,  15, 255, 255, 255, 255,  15, 255, 255,   7,   0,
    255, 255, 223, 255, 255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255,
    191, 231, 223, 223, 255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255,
    253, 255, 255, 247, 255, 253, 255, 255, 247,  15,   0,   0,  15,   0,   0,   0,
    255,   3, 255, 255,
};

/* Cased: 748 bytes. */

RE_UINT32 re_get_cased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 14;
    code = ch ^ (f << 14);
    pos = (RE_UINT32)re_cased_stage_1[f] << 4;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_cased_stage_2[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_cased_stage_3[pos + f] << 2;
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
    11, 12, 13, 14,  7,  7,  7,  7,  7,  7,  7,  7,  7, 15,  7,  7,
     7,  7,  7,  7,  7,  7,  7, 16,  7,  7, 17, 18, 19, 20, 21,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
    22,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
};

static RE_UINT8 re_case_ignorable_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1,  1, 17,  1,  1,  1, 18, 19, 20, 21, 22, 23, 24,  1, 25,
    26,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 27, 28, 29,  1,
    30,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    31,  1,  1,  1, 32,  1, 33, 34, 35, 36, 37, 38,  1,  1,  1,  1,
     1,  1,  1, 39,  1,  1, 40, 41,  1, 42, 43, 44,  1,  1,  1,  1,
     1,  1, 45,  1,  1,  1,  1,  1, 46, 47, 48, 49, 50, 51, 52, 53,
     1,  1,  1,  1, 54,  1,  1,  1,  1,  1, 55, 56,  1,  1,  1, 57,
     1,  1,  1,  1, 58,  1,  1,  1,  1, 59, 60,  1,  1,  1,  1,  1,
     1,  1, 61,  1,  1,  1,  1,  1, 62,  1,  1,  1,  1,  1,  1,  1,
    63, 64,  1,  1,  1,  1,  1,  1,  1,  1,  1, 65,  1,  1,  1,  1,
    66, 67,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_case_ignorable_stage_4[] = {
      0,   1,   2,   3,   0,   4,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   5,   6,   6,   6,   6,   6,   7,   8,   0,   0,   0,
      0,   0,   0,   0,   9,   0,   0,   0,   0,   0,  10,   0,  11,  12,  13,  14,
     15,   0,  16,  17,   0,   0,  18,  19,  20,   5,  21,   0,   0,  22,   0,  23,
     24,  25,  26,   0,   0,   0,  27,   6,  28,  29,  30,  31,  32,  33,  34,  35,
     36,  33,  37,  38,  36,  33,  39,  35,  32,  40,  41,  35,  42,   0,  43,   0,
      3,  44,  45,  35,  32,  40,  46,  35,  32,   0,  34,  35,   0,   0,  47,   0,
      0,  48,  49,   0,   0,  50,  51,   0,  52,  53,   0,  54,  55,  56,  57,   0,
      0,  58,  59,  60,  61,   0,   0,  33,   0,   0,  62,   0,   0,   0,   0,   0,
     63,  63,  64,  64,   0,  65,  66,   0,  67,   0,  68,   0,  69,  70,   0,   0,
      0,  71,   0,   0,   0,   0,   0,   0,  72,   0,  73,  74,   0,  75,   0,   0,
     76,  77,  42,  78,  79,  80,   0,  81,   0,  82,   0,  83,   0,   0,  84,  85,
      0,  86,   6,  87,  88,   6,   6,  89,   0,   0,   0,   0,   0,  90,  91,  92,
     93,  94,   0,  95,  96,   0,   5,  97,   0,   0,   0,  98,   0,   0,   0,  99,
      0,   0,   0, 100,   0,   0,   0,   6,   0, 101,   0,   0,   0,   0,   0,   0,
    102, 103,   0,   0, 104,   0,   0, 105, 106,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  83, 107,   0,   0, 108, 109,   0,   0, 110,
      6,  79,   0,  17, 111,   0,   0,  52, 112,  69,   0,   0,   0,   0, 113, 114,
      0, 115, 116,   0,  28, 117, 101,  69,   0, 118, 119, 120,   0, 121, 122, 123,
      0,   0,  88,   0,   0,   0,   0, 124,   2,   0,   0,   0,   0, 125,  79,   0,
    126, 127, 128,   0,   0,   0,   0, 129,   1,   2,   3,  17,  44,   0,   0, 130,
      0,   0,   0,   0,   0,   0,   0, 131,   0,   0,   0,   0,   0,   0,   0,   3,
      0,   0,   0, 132,   0,   0,   0,   0, 133, 134,   0,   0,   0,   0,   0,  69,
     32, 135, 136, 129,  79, 137,   0,   0,  28, 138,   0, 139,  79, 140, 141,   0,
      0, 142,   0,   0,   0,   0, 129, 143,  79,  33,   3, 144,   0,   0,   0,   0,
      0, 135, 145,   0,   0, 146, 147,   0,   0,   0,   0,   0,   0, 148, 149,   0,
      0, 150,   3,   0,   0, 151,   0,   0,  62, 152,   0,   0,   0,   0,   0,   0,
      0, 153,   0,   0, 125, 154,   0,   0,   0,   0,   0,   0,   0,   0,   0, 155,
      0, 156,  76,   0,   0,   0,   0,   0,   0,   0,   0,   0, 157,   0,   0,   3,
      0,   0,   0,   0, 158,  76,   0,   0,   0,   0,   0, 159, 160, 161,   0,   0,
      0,   0, 162,   0,   0,   0,   0,   0,   6, 163,   6, 164, 165, 166,   0,   0,
    167, 168,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 156,   0,
      0,   0, 169,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  88,
     32,   6,   6,   6,   0,   0,   0,   0,   6,   6,   6,   6,   6,   6,   6, 127,
};

static RE_UINT8 re_case_ignorable_stage_5[] = {
      0,   0,   0,   0, 128,  64,   0,   4,   0,   0,   0,  64,   1,   0,   0,   0,
      0, 161, 144,   1,   0,   0, 255, 255, 255, 255, 255, 255, 255, 255,  48,   4,
    176,   0,   0,   0, 248,   3,   0,   0,   0,   0,   0,   2,   0,   0, 254, 255,
    255, 255, 255, 191, 182,   0,   0,   0,   0,   0,  16,   0,  63,   0, 255,  23,
      1, 248, 255, 255,   0,   0,   1,   0,   0,   0, 192, 191, 255,  61,   0,   0,
      0, 128,   2,   0, 255,   7,   0,   0, 192, 255,   1,   0,   0, 248,  63,   4,
      0,   0, 192, 255, 255,  63,   0,   0,   0,   0,   0,  14,   0,   0, 240, 255,
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
      8,   0,   0,   0,  96,   0,   0,   0,   0,   2,   0,   0, 135,   1,   4,  14,
      0,   0, 128,   9,   0,   0,  64, 127, 229,  31, 248, 159, 128,   0, 255, 127,
     15,   0,   0,   0,   0,   0, 208,  23,   0, 248,  15,   0,   3,   0,   0,   0,
     60,  59,   0,   0,  64, 163,   3,   0,   0, 240, 207,   0,   0,   0,   0,  63,
      0,   0, 247, 255, 253,  33,  16,   3,   0, 240, 255, 255, 255,   7,   0,   1,
      0,   0,   0, 248, 255, 255,  63, 248,   0,   0,   0, 160,   3, 224,   0, 224,
      0, 224,   0,  96,   0, 248,   0,   3, 144, 124,   0,   0, 223, 255,   2, 128,
      0,   0, 255,  31, 255, 255,   1,   0,   0,   0,   0,  48,   0, 128,   3,   0,
      0, 128,   0, 128,   0, 128,   0,   0,  32,   0,   0,   0,   0,  60,  62,   8,
      0,   0,   0, 126,   0,   0,   0, 112,   0,   0,  32,   0,   0,  16,   0,   0,
      0, 128, 247, 191,   0,   0,   0, 240,   0,   0,   3,   0,   0,   7,   0,   0,
     68,   8,   0,   0,  48,   0,   0,   0, 255, 255,   3,   0, 192,  63,   0,   0,
    128, 255,   3,   0,   0,   0, 200,  19,   0, 126, 102,   0,   8,  16,   0,   0,
      0,   0,   1,  16,   0,   0, 157, 193,   2,   0,   0,  32,   0,  48,  88,   0,
     32,  33,   0,   0,   0,   0, 252, 255, 255, 255,   8,   0, 255, 255,   0,   0,
      0,   0,  36,   0,   0,   0,   0, 128,   8,   0,   0,  14,   0,   0,   0,  32,
      0,   0, 192,   7, 110, 240,   0,   0,   0,   0,   0, 135,   0,   0,   0, 255,
    127,   0,   0,   0,   0,   0, 120,  38, 128, 239,  31,   0,   0,   0,   8,   0,
      0,   0, 192, 127,   0,  28,   0,   0,   0, 128, 211,  64, 248,   7,   0,   0,
    192,  31,  31,   0,  92,   0,   0,   0,   0,   0, 248, 133,  13,   0,   0,   0,
      0,   0,  60, 176,   1,   0,   0,  48,   0,   0, 248, 167,   0,  40, 191,   0,
    188,  15,   0,   0,   0,   0, 127, 191, 255, 252, 109,   0,   0,   0,  31,   0,
      0,   0, 127,   0,   0, 128, 255, 255,   0,   0,   0,  96, 128,   3, 248, 255,
    231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0, 255, 255, 127, 248,
    255,  31,  32,   0,  16,   0,   0, 248, 254, 255,   0,   0, 127, 255, 255, 249,
    219,   7,   0,   0, 240,   7,   0,   0,
};

/* Case_Ignorable: 1538 bytes. */

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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_changes_when_lowercased_stage_2[] = {
     0,  1,  2,  3,  4,  5,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  6,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  7,
     8,  9,  1, 10,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 11,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_changes_when_lowercased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  9, 10,
     6, 11,  6,  6, 12,  6,  6,  6,  6,  6,  6,  6, 13,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 14, 15,  6,  6,  6,  6,  6,  6,  6, 16,
     6,  6,  6,  6, 17,  6,  6,  6,  6,  6,  6,  6, 18,  6,  6,  6,
    19,  6,  6,  6,  6,  6,  6,  6,  6, 20,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_lowercased_stage_4[] = {
     0,  0,  1,  0,  0,  0,  2,  0,  3,  4,  5,  6,  7,  8,  9, 10,
     3, 11, 12,  0,  0,  0,  0,  0,  0,  0,  0, 13, 14, 15, 16, 17,
    18, 19,  0,  3, 20,  3, 21,  3,  3, 22, 23,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18, 24,  0,
     0,  0,  0,  0,  0, 18, 18, 25,  3,  3,  3,  3, 26,  3,  3,  3,
    27, 28, 29, 30, 28, 31, 32, 33,  0, 34,  0, 19, 35,  0,  0,  0,
     0,  0,  0,  0,  0, 36, 19,  0, 18, 37,  0, 38,  3,  3,  3, 39,
     0,  0,  3, 40, 41,  0,  0,  0,  0, 42,  3, 43, 44, 45,  0,  0,
     0,  1,  0,  0,  0,  0,  0,  0, 18, 46,  0,  0,  0, 47, 48,  0,
     0,  0,  0,  0, 18, 49,  0,  0,  0,  0,  0,  0,  0, 18,  0,  0,
    18, 50,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_changes_when_lowercased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7, 255, 255, 127, 127,  85,  85,  85,  85,
     85,  85,  85, 170, 170,  84,  85,  85,  85,  85,  85,  43, 214, 206, 219, 177,
    213, 210, 174,  17, 176, 173, 170,  74,  85,  85, 214,  85,  85,  85,   5, 108,
    122,  85,   0,   0,   0,   0,  69, 128,  64, 215, 254, 255, 251,  15,   0,   0,
      0, 128,   0,  85,  85,  85, 144, 230, 255, 255, 255, 255, 255, 255,   0,   0,
      1,  84,  85,  85, 171,  42,  85,  85,  85,  85, 254, 255, 255, 255, 127,   0,
    191,  32,   0,   0, 255, 255,  63,   0,  85,  85,  21,  64,   0, 255,   0,  63,
      0, 255,   0, 255,   0,  63,   0, 170,   0, 255,   0,   0,   0, 255,   0,  31,
      0,  31,   0,  15,   0,  31,   0,  31,  64,  12,   4,   0,   8,   0,   0,   0,
      0,   0, 192, 255, 255, 127,   0,   0, 157, 234,  37, 192,   5,  40,   4,   0,
     85,  21,   0,   0,  85,  85,  85,   5,  84,  85,  84,  85,  85,  85,   0, 106,
     85,  40,  69,  85,  85, 125,  95,   0, 255,   0,   0,   0,   0,   0, 255, 255,
    255, 255,  15,   0, 255, 255,   7,   0,   3,   0,   0,   0,
};

/* Changes_When_Lowercased: 581 bytes. */

RE_UINT32 re_get_changes_when_lowercased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_changes_when_lowercased_stage_1[f] << 5;
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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_changes_when_uppercased_stage_2[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 3, 3, 5,
    6, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 8, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
};

static RE_UINT8 re_changes_when_uppercased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  7,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9, 10, 11,
     6, 12,  6,  6, 13,  6,  6,  6,  6,  6,  6,  6, 14, 15,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 16, 17,  6,  6,  6, 18,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 19,  6,  6,  6, 20,
     6,  6,  6,  6, 21,  6,  6,  6,  6,  6,  6,  6, 22,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 23,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 24,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_uppercased_stage_4[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
     5, 13, 14, 15, 16,  0,  0,  0,  0,  0, 17, 18, 19, 20, 21, 22,
     0, 23, 24,  5, 25,  5, 26,  5,  5, 27,  0, 28, 29,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 30,
     0,  0,  0,  0, 31,  0,  0,  0,  0,  0,  0, 32,  0,  0,  0,  0,
     5,  5,  5,  5, 33,  5,  5,  5, 34, 35, 36, 37, 24, 38, 39, 40,
     0,  0, 41, 23, 42,  0,  0,  0,  0,  0,  0,  0,  0,  0, 23, 43,
     0, 23, 44, 45,  5,  5,  5, 46, 24, 47,  0,  0,  0,  0,  0,  0,
     0,  0,  5, 48, 49,  0,  0,  0,  0, 50,  5, 51, 52, 53,  0,  0,
     0,  0, 54, 23, 24, 24,  0,  0, 55,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  1,  0,  0,  0,  0,  0,  0, 56, 57,  0,  0,  0, 58, 59,
     0,  0,  0,  0,  0,  0, 24, 60,  0,  0,  0,  0,  0,  0, 24,  0,
     0, 61, 62,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_changes_when_uppercased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0,   0,   0,   0, 128,
    255, 255, 127, 255, 170, 170, 170, 170, 170, 170, 170,  84,  85, 171, 170, 170,
    170, 170, 170, 212,  41,  17,  36,  70,  42,  33,  81, 162,  96,  91,  85, 181,
    170, 170,  45, 170, 168, 170,  10, 144, 133, 170, 223,  26, 107, 159,  38,  32,
    137,  31,   4,  96,  32,   0,   0,   0,   0,   0, 138,  56,   0,   0,   1,   0,
      0, 240, 255, 255, 255, 127, 227, 170, 170, 170,  47,   9,   0,   0, 255, 255,
    255, 255, 255, 255,   2, 168, 170, 170,  84, 213, 170, 170, 170, 170,   0,   0,
    254, 255, 255, 255, 255,   0,   0,   0,   0,   0,   0,  63, 255,   1,   0,   0,
      0,   0,   0,  34, 170, 170, 234,  15, 255,   0,  63,   0, 255,   0, 255,   0,
     63,   0, 255,   0, 255,   0, 255,  63, 255, 255, 223,  80, 220,  16, 207,   0,
    255,   0, 220,  16,   0,  64,   0,   0,  16,   0,   0,   0, 255,   3,   0,   0,
    255, 255, 255, 127,  98,  21,  72,   0,  10,  80,   8,   0, 191,  32,   0,   0,
    170,  42,   0,   0, 170, 170, 170,  10, 168, 170, 168, 170, 170, 170,   0, 148,
    170,  16, 138, 170, 170,   2, 160,   0,   0,   0,   8,   0, 127,   0, 248,   0,
      0, 255, 255, 255, 255, 255,   0,   0,   0,   0,   0, 255, 255, 255, 255,  15,
    255, 255,   7,   0, 252, 255, 255, 255,  15,   0,   0,   0,
};

/* Changes_When_Uppercased: 661 bytes. */

RE_UINT32 re_get_changes_when_uppercased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_changes_when_uppercased_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_changes_when_uppercased_stage_2[pos + f] << 4;
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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_changes_when_titlecased_stage_2[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 3, 3, 5,
    6, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 8, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
};

static RE_UINT8 re_changes_when_titlecased_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  7,  6,  6,  6,  6,  6,  6,  6,  6,  8,  9, 10, 11,
     6, 12,  6,  6, 13,  6,  6,  6,  6,  6,  6,  6, 14, 15,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 16, 17,  6,  6,  6, 18,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 19,  6,  6,  6, 20,
     6,  6,  6,  6, 21,  6,  6,  6,  6,  6,  6,  6, 22,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 23,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 24,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_titlecased_stage_4[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
     5, 13, 14, 15, 16,  0,  0,  0,  0,  0, 17, 18, 19, 20, 21, 22,
     0, 23, 24,  5, 25,  5, 26,  5,  5, 27,  0, 28, 29,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 30,
     0,  0,  0,  0, 31,  0,  0,  0,  0,  0,  0, 32,  0,  0,  0,  0,
     5,  5,  5,  5, 33,  5,  5,  5, 34, 35, 36, 37, 35, 38, 39, 40,
     0,  0, 41, 23, 42,  0,  0,  0,  0,  0,  0,  0,  0,  0, 23, 43,
     0, 23, 44, 45,  5,  5,  5, 46, 24, 47,  0,  0,  0,  0,  0,  0,
     0,  0,  5, 48, 49,  0,  0,  0,  0, 50,  5, 51, 52, 53,  0,  0,
     0,  0, 54, 23, 24, 24,  0,  0, 55,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  1,  0,  0,  0,  0,  0,  0, 56, 57,  0,  0,  0, 58, 59,
     0,  0,  0,  0,  0,  0, 24, 60,  0,  0,  0,  0,  0,  0, 24,  0,
     0, 61, 62,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_changes_when_titlecased_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0,   0,   0,   0, 128,
    255, 255, 127, 255, 170, 170, 170, 170, 170, 170, 170,  84,  85, 171, 170, 170,
    170, 170, 170, 212,  41,  17,  36,  70,  42,  33,  81, 162, 208,  86,  85, 181,
    170, 170,  43, 170, 168, 170,  10, 144, 133, 170, 223,  26, 107, 159,  38,  32,
    137,  31,   4,  96,  32,   0,   0,   0,   0,   0, 138,  56,   0,   0,   1,   0,
      0, 240, 255, 255, 255, 127, 227, 170, 170, 170,  47,   9,   0,   0, 255, 255,
    255, 255, 255, 255,   2, 168, 170, 170,  84, 213, 170, 170, 170, 170,   0,   0,
    254, 255, 255, 255, 255,   0,   0,   0,   0,   0,   0,  63, 255,   1,   0,   0,
      0,   0,   0,  34, 170, 170, 234,  15, 255,   0,  63,   0, 255,   0, 255,   0,
     63,   0, 255,   0, 255,   0, 255,  63, 255,   0, 223,  64, 220,   0, 207,   0,
    255,   0, 220,   0,   0,  64,   0,   0,  16,   0,   0,   0, 255,   3,   0,   0,
    255, 255, 255, 127,  98,  21,  72,   0,  10,  80,   8,   0, 191,  32,   0,   0,
    170,  42,   0,   0, 170, 170, 170,  10, 168, 170, 168, 170, 170, 170,   0, 148,
    170,  16, 138, 170, 170,   2, 160,   0,   0,   0,   8,   0, 127,   0, 248,   0,
      0, 255, 255, 255, 255, 255,   0,   0,   0,   0,   0, 255, 255, 255, 255,  15,
    255, 255,   7,   0, 252, 255, 255, 255,  15,   0,   0,   0,
};

/* Changes_When_Titlecased: 661 bytes. */

RE_UINT32 re_get_changes_when_titlecased(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_changes_when_titlecased_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_changes_when_titlecased_stage_2[pos + f] << 4;
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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_changes_when_casefolded_stage_2[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 3, 3, 5,
    6, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 8, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
};

static RE_UINT8 re_changes_when_casefolded_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  9,  6, 10, 11,
     6, 12,  6,  6, 13,  6,  6,  6,  6,  6,  6,  6, 14,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 15, 16,  6,  6,  6, 17,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 18,  6,  6,  6, 19,
     6,  6,  6,  6, 20,  6,  6,  6,  6,  6,  6,  6, 21,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 22,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 23,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_casefolded_stage_4[] = {
     0,  0,  1,  0,  0,  2,  3,  0,  4,  5,  6,  7,  8,  9, 10, 11,
     4, 12, 13,  0,  0,  0,  0,  0,  0,  0, 14, 15, 16, 17, 18, 19,
    20, 21,  0,  4, 22,  4, 23,  4,  4, 24, 25,  0, 26,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 20, 27,  0,
     0,  0,  0,  0,  0,  0,  0, 28,  0,  0,  0,  0, 29,  0,  0,  0,
     4,  4,  4,  4, 30,  4,  4,  4, 31, 32, 33, 34, 20, 35, 36, 37,
     0, 38,  0, 21, 39,  0,  0,  0,  0,  0,  0,  0,  0, 40, 21,  0,
    20, 41,  0, 42,  4,  4,  4, 43,  0,  0,  4, 44, 45,  0,  0,  0,
     0, 46,  4, 47, 48, 49,  0,  0,  0,  0,  0, 50, 20, 20,  0,  0,
    51,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,
    20, 52,  0,  0,  0, 50, 53,  0,  0,  0,  0,  0, 20, 54,  0,  0,
     0,  0,  0,  0,  0, 20,  0,  0, 20, 55,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_changes_when_casefolded_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0, 255, 255, 127, 255,
     85,  85,  85,  85,  85,  85,  85, 170, 170,  86,  85,  85,  85,  85,  85, 171,
    214, 206, 219, 177, 213, 210, 174,  17, 176, 173, 170,  74,  85,  85, 214,  85,
     85,  85,   5, 108, 122,  85,   0,   0,  32,   0,   0,   0,   0,   0,  69, 128,
     64, 215, 254, 255, 251,  15,   0,   0,   4, 128,  99,  85,  85,  85, 179, 230,
    255, 255, 255, 255, 255, 255,   0,   0,   1,  84,  85,  85, 171,  42,  85,  85,
     85,  85, 254, 255, 255, 255, 127,   0, 128,   0,   0,   0, 191,  32,   0,   0,
      0,   0,   0,  63, 255,   1,   0,   0,  85,  85,  21,  76,   0, 255,   0,  63,
      0, 255,   0, 255,   0,  63,   0, 170,   0, 255,   0,   0, 255, 255, 156,  31,
    156,  31,   0,  15,   0,  31, 156,  31,  64,  12,   4,   0,   8,   0,   0,   0,
      0,   0, 192, 255, 255, 127,   0,   0, 157, 234,  37, 192,   5,  40,   4,   0,
     85,  21,   0,   0,  85,  85,  85,   5,  84,  85,  84,  85,  85,  85,   0, 106,
     85,  40,  69,  85,  85, 125,  95,   0,   0,   0, 255, 255, 127,   0, 248,   0,
    255,   0,   0,   0, 255, 255,  15,   0, 255, 255,   7,   0,   3,   0,   0,   0,
};

/* Changes_When_Casefolded: 625 bytes. */

RE_UINT32 re_get_changes_when_casefolded(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_changes_when_casefolded_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_changes_when_casefolded_stage_2[pos + f] << 4;
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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_changes_when_casemapped_stage_2[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 4, 3, 3, 3, 3, 5,
    6, 7, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 8, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
};

static RE_UINT8 re_changes_when_casemapped_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  9, 10, 11, 12,
     6, 13,  6,  6, 14,  6,  6,  6,  6,  6,  6,  6, 15, 16,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 17, 18,  6,  6,  6, 19,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 20,  6,  6,  6, 21,
     6,  6,  6,  6, 22,  6,  6,  6,  6,  6,  6,  6, 23,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 24,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 25,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_changes_when_casemapped_stage_4[] = {
     0,  0,  1,  1,  0,  2,  3,  3,  4,  5,  4,  4,  6,  7,  8,  4,
     4,  9, 10, 11, 12,  0,  0,  0,  0,  0, 13, 14, 15, 16, 17, 18,
     4,  4,  4,  4, 19,  4,  4,  4,  4, 20, 21, 22, 23,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  4, 24,  0,
     0,  0,  0,  0,  0,  4,  4, 25,  0,  0,  0,  0, 26,  0,  0,  0,
     0,  0,  0, 27,  0,  0,  0,  0,  4,  4,  4,  4, 28,  4,  4,  4,
    25,  4, 29, 30,  4, 31, 32, 33,  0, 34, 35,  4, 36,  0,  0,  0,
     0,  0,  0,  0,  0, 37,  4, 38,  4, 39, 40, 41,  4,  4,  4, 42,
     4, 24,  0,  0,  0,  0,  0,  0,  0,  0,  4, 43, 44,  0,  0,  0,
     0, 45,  4, 46, 47, 48,  0,  0,  0,  0, 49, 50,  4,  4,  0,  0,
    51,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  0,  0,  0,  0,  0,
     4,  4, 52,  0,  0, 50, 53, 44,  0,  0,  0,  0,  4, 54,  4, 54,
     0,  0,  0,  0,  0,  4,  4,  0,  4,  4, 55,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_changes_when_casemapped_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   0,  32,   0, 255, 255, 127, 255,
    255, 255, 255, 255, 255, 255, 255, 254, 255, 223, 255, 247, 255, 243, 255, 179,
    240, 255, 255, 255, 253, 255,  15, 252, 255, 255, 223,  26, 107, 159,  38,  32,
    137,  31,   4,  96,  32,   0,   0,   0,   0,   0, 207, 184,  64, 215, 255, 255,
    251, 255, 255, 255, 255, 255, 227, 255, 255, 255, 191, 239,   3, 252, 255, 255,
    255, 255, 254, 255, 255, 255, 127,   0, 254, 255, 255, 255, 255,   0,   0,   0,
    191,  32,   0,   0, 255, 255,  63,  63, 255,   1,   0,   0,   0,   0,   0,  34,
    255, 255, 255,  79,  63,  63, 255, 170, 255, 255, 255,  63, 255, 255, 223,  95,
    220,  31, 207,  15, 255,  31, 220,  31,  64,  12,   4,   0,   0,  64,   0,   0,
     24,   0,   0,   0,   0,   0, 192, 255, 255,   3,   0,   0, 255, 127, 255, 255,
    255, 255, 255, 127, 255, 255, 109, 192,  15, 120,  12,   0, 255,  63,   0,   0,
    255, 255, 255,  15, 252, 255, 252, 255, 255, 255,   0, 254, 255,  56, 207, 255,
    255, 127, 255,   0,   0,   0,   8,   0,   0,   0, 255, 255, 127,   0, 248,   0,
    255, 255,   0,   0, 255, 255,  15, 255, 255, 255,   7,   0,  15,   0,   0,   0,
};

/* Changes_When_Casemapped: 641 bytes. */

RE_UINT32 re_get_changes_when_casemapped(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_changes_when_casemapped_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_changes_when_casemapped_stage_2[pos + f] << 4;
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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 13, 13, 28, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 29,  7, 30, 31,  7, 32, 13, 13, 13, 13, 13, 33,
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
    58, 59, 60, 61, 62, 31, 31, 31, 63, 64, 65, 66, 67, 68, 69, 70,
    71, 31, 72, 31, 73, 31, 31, 31,  1,  1,  1, 74, 75, 76, 31, 31,
     1,  1,  1,  1, 77, 31, 31, 31, 31, 31, 31, 31,  1,  1, 78, 31,
     1,  1, 79, 80, 31, 31, 31, 81,  1,  1,  1,  1,  1,  1,  1, 82,
     1,  1, 83, 31, 31, 31, 31, 31, 84, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 85, 31, 31, 31, 31, 31, 31, 31, 86, 87, 88, 89,
    90, 76, 31, 31, 31, 31, 91, 31,  1,  1,  1,  1,  1,  1, 92,  1,
     1,  1,  1,  1,  1,  1,  1, 93, 94,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 95, 31,  1,  1, 96, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_id_start_stage_4[] = {
      0,   0,   1,   1,   0,   2,   3,   3,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   5,   6,   0,   0,   0,   7,   8,   9,   4,  10,
      4,   4,   4,   4,  11,   4,   4,   4,   4,  12,  13,  14,  15,   0,  16,  17,
      0,   4,  18,  19,   4,   4,  20,  21,  22,  23,  24,   4,   4,  25,  26,  27,
     28,  29,  30,   0,   0,  31,   0,   0,  32,  33,  34,  35,  36,  37,  38,  39,
     40,  41,  42,  43,  44,  45,  46,  47,  48,  45,  49,  50,  51,  52,  46,   0,
     53,  54,  55,  56,  57,  58,  59,  60,  53,  61,  62,  63,  64,  65,  66,   0,
     14,  67,  66,   0,  68,  69,  70,   0,  71,   0,  72,  73,  74,   0,   0,   0,
      4,  75,  76,  77,  78,   4,  79,  80,   4,   4,  81,   4,  82,  83,  84,   4,
     85,   4,  86,   0,  23,   4,   4,  87,  14,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,  88,   1,   4,   4,  89,  90,  91,  91,  92,   4,  93,  94,   0,
      0,   4,   4,  95,   4,  96,   4,  97,  98,   0,  16,  99,   4, 100, 101,   0,
    102,   4, 103,   0,   0, 104,   0,   0, 105,  93, 106,   0, 107, 108,   4, 109,
      4, 110, 111, 112, 113,   0,   0, 114,   4,   4,   4,   4,   4,   4,   0,   0,
     87,   4, 115, 112,   4, 116, 117, 118,   0,   0,   0, 119, 120,   0,   0,   0,
    121, 122, 123,   4, 113,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      4, 124,  98,   4,   4,   4,   4, 125,   4,  79,   4, 126, 102, 127, 127,   0,
    128, 129,  14,   4, 130,  14,   4,  80, 105, 131,   4,   4, 132,  86,   0,  16,
      4,   4,   4,   4,   4,  97,   0,   0,   4,   4,   4,   4,   4,   4,  97,   0,
      4,   4,   4,   4,  73,   0,  16, 112, 133, 134,   4, 135, 112,   4,   4,  23,
    136, 137,   4,   4, 138, 139,   0, 136, 140, 141,   4,  93, 137,  93,   0, 142,
     26, 143,  66, 144,  32, 145, 146, 147,   4, 113, 148, 149,   4, 150, 151, 152,
    153, 154,  80, 143,   4,   4,   4, 141,   4,   4,   4,   4,   4, 155, 156, 157,
      4,   4,   4, 158,   4,   4, 159,   0, 160, 161, 162,   4,   4,  91, 163,   4,
      4, 112,  16,   4, 164,   4,  15, 165,   0,   0,   0, 166,   4,   4,   4, 144,
      0,   1,   1, 167,   4,  98, 168,   0, 169, 170, 171,   0,   4,   4,   4,  86,
      0,   0,   4, 103,   0,   0,   0,   0,   0,   0,   0,   0, 144,   4, 172,   0,
      4,  16, 173,  97, 112,   4, 174,   0,   4,   4,   4,   4, 112,  16, 175, 157,
      4, 176,   4, 110,   0,   0,   0,   0,   4, 102,  97,  15,   0,   0,   0,   0,
    177, 178,  97, 102,  98,   0,   0, 179,  97, 159,   0,   0,   4, 180,   0,   0,
    181,  93,   0, 144, 144,   0,  72, 182,   4,  97,  97, 145,  91,   0,   0,   0,
      4,   4, 113,   0,   4, 145,   4, 145, 107,  95,   0,   0, 107,  23,  16, 113,
    107,  66,  16, 183, 107, 145, 184,   0, 185, 186,   0,   0, 187, 188,  98,   0,
     48,  45, 189,  56,   0,   0,   0,   0,   4, 103, 190,   0,   4,  23, 191,   0,
      0,   0,   0,   0,   4, 132, 192,   0,   4,  23, 193,   0,   4,  18,   0,   0,
    159,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4,   4, 194,
      0,   0,   0,   0,   0,   0,   4,  30, 195, 132,  71, 196,  23,   0,   0,   0,
      4,   4,   4,   4, 159,   0,   0,   0,   4,   4,   4, 132,   4,   4,   4,   4,
      4,   4, 110,   0,   0,   0,   0,   0,   4, 132,   0,   0,   0,   0,   0,   0,
      4,   4,  66,   0,   0,   0,   0,   0,   4,  30,  98,   0,   0,   0,  16, 197,
      4,  23, 110, 198,  23,   0,   0,   0,   4,   4, 199,   0, 163,   0,   0,  71,
      4,   4,   4,   4,   4,   4,   4,  73,   4,   4,   4,   4,   4,   4,   4, 145,
     56,   0,   0,   0,   0,   0,   0,   0,   4,   4,   4, 200, 201,   0,   0,   0,
      4,   4, 202,   4, 203, 204, 205,   4, 206, 207, 208,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4, 209, 210,  80, 202, 202, 124, 124, 195, 195, 148,   0,
      4,   4,   4,   4,   4,   4, 182,   0, 205, 211, 212, 213, 214, 215,   0,   0,
      4,   4,   4,   4,   4,   4, 102,   0,   4, 103,   4,   4,   4,   4,   4,   4,
    112,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,  56,   0,   0,
    112,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_id_start_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,   0,   0, 223, 188,
     64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,   3, 252, 255, 255,
    255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255, 255,   0,   0,   0,
      0,   0, 255, 255, 255,   7,   7,   0, 255,   7,   0,   0,   0, 192, 254, 255,
    255, 255,  47,   0,  96, 192,   0, 156,   0,   0, 253, 255, 255, 255,   0,   0,
      0, 224, 255, 255,  63,   0,   2,   0,   0, 252, 255, 255, 255,   7,  48,   4,
    255, 255,  63,   4,  16,   1,   0,   0, 255, 255, 255,   1, 255, 255, 223,  63,
    240, 255, 255, 255, 255, 255, 255,  35,   0,   0,   1, 255,   3,   0, 254, 255,
    225, 159, 249, 255, 255, 253, 197,  35,   0,  64,   0, 176,   3,   0,   3,   0,
    224, 135, 249, 255, 255, 253, 109,   3,   0,   0,   0,  94,   0,   0,  28,   0,
    224, 191, 251, 255, 255, 253, 237,  35,   0,   0,   1,   0,   3,   0,   0,   2,
    224, 159, 249, 255,   0,   0,   0, 176,   3,   0,   2,   0, 232, 199,  61, 214,
     24, 199, 255,   3, 224, 223, 253, 255, 255, 253, 255,  35,   0,   0,   0,   7,
      3,   0,   0,   0, 225, 223, 253, 255, 255, 253, 239,  35,   0,   0,   0,  64,
      3,   0,   6,   0, 255, 255, 255,  39,   0,  64, 112, 128,   3,   0,   0, 252,
    224, 255, 127, 252, 255, 255, 251,  47, 127,   0,   0,   0, 255, 255,  13,   0,
    150,  37, 240, 254, 174, 236,  13,  32,  95,   0,   0, 240,   1,   0,   0,   0,
    255, 254, 255, 255, 255,  31,   0,   0,   0,  31,   0,   0, 255,   7,   0, 128,
      0,   0,  63,  60,  98, 192, 225, 255,   3,  64,   0,   0, 191,  32, 255, 255,
    255, 255, 255, 247, 255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,
     61, 255, 127, 255, 255, 255,  61, 255, 255, 255, 255,   7, 255, 255,  63,  63,
    255, 159, 255, 255, 255, 199, 255,   1, 255, 223,   3,   0, 255, 255,   3,   0,
    255, 223,   1,   0, 255, 255,  15,   0,   0,   0, 128,  16, 255, 255, 255,   0,
    255,   5, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3,   0,   0, 255, 255, 127,   0, 255, 255,  31,   0,
    128,   0,   0,   0, 224, 255, 255, 255, 224,  15,   0,   0, 248, 255, 255, 255,
      1, 192,   0, 252,  63,   0,   0,   0,  15,   0,   0,   0,   0, 224,   0, 252,
    255, 255, 255,  63, 255,   1,   0,   0,   0, 222,  99,   0,  63,  63, 255, 170,
    255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   2, 128,
      0,   0, 255,  31, 132, 252,  47,  63,  80, 253, 255, 243, 224,  67,   0,   0,
    255, 127, 255, 255,  31, 120,  12,   0, 255, 128,   0,   0, 127, 127, 127, 127,
    224,   0,   0,   0, 254,   3,  62,  31, 255, 255, 127, 248, 255,  63, 254, 255,
    255, 127,   0,   0, 255,  31, 255, 255,   0,  12,   0,   0, 255, 127,   0, 128,
      0,   0, 128, 255, 252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0,
    187, 247, 255, 255,   7,   0,   0,   0,   0,   0, 252,  40,  63,   0, 255, 255,
    255, 255, 255,  31, 255, 255,   7,   0,   0, 128,   0,   0, 223, 255,   0, 124,
    247,  15,   0,   0, 255, 255, 127, 196, 255, 255,  98,  62,   5,   0,   0,  56,
    255,   7,  28,   0, 126, 126, 126,   0, 127, 127, 255, 255,  15,   0, 255, 255,
    127, 248, 255, 255, 255, 255, 255,  15, 255,  63, 255, 255, 255, 255, 255,   3,
    127,   0, 248, 160, 255, 253, 127,  95, 219, 255, 255, 255,   0,   0, 248, 255,
    255, 255, 252, 255,   0,   0, 255,  15,   0,   0, 223, 255, 192, 255, 255, 255,
    252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,
    255, 255,   1,   0, 255,   7, 255, 255,  15, 255,  62,   0, 255, 255,  15, 255,
    255,   0, 255, 255,  63, 253, 255, 255, 255, 255, 191, 145, 255, 255,  55,   0,
    255, 255, 255, 192,   1,   0, 239, 254,  31,   0,   0,   0, 255, 255,  71,   0,
     30,   0,   0,  20, 255, 255, 251, 255, 255,  15,   0,   0, 127, 189, 255, 191,
    255,   1, 255, 255,   0,   0,   1, 224, 128,   7,   0,   0, 176,   0,   0,   0,
      0,   0,   0,  15,  16,   0,   0,   0,   0,   0,   0, 128, 255, 253, 255, 255,
      0,   0, 252, 255, 255,  63,   0,   0, 248, 255, 255, 224,  31,   0,   1,   0,
    255,   7, 255,  31, 255,   1, 255,   3, 255, 255, 223, 255, 255, 255, 255, 223,
    100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,
     95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247, 150, 254, 247,  10,
    132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
};

/* ID_Start: 2057 bytes. */

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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 28, 29, 30, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 31,  7, 32, 33,  7, 34, 13, 13, 13, 13, 13, 35,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    36, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_id_continue_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  32,  33,  31,  31,
     34,  35,  31,  31,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  36,   1,   1,   1,   1,   1,   1,   1,   1,   1,  37,
      1,   1,   1,   1,  38,   1,  39,  40,  41,  42,  43,  44,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  45,  31,  31,  31,  31,  31,  31,  31,  31,
     31,   1,  46,  47,   1,  48,  49,  50,  51,  52,  53,  54,  55,  56,   1,  57,
     58,  59,  60,  61,  62,  31,  31,  31,  63,  64,  65,  66,  67,  68,  69,  70,
     71,  31,  72,  31,  73,  31,  31,  31,   1,   1,   1,  74,  75,  76,  31,  31,
      1,   1,   1,   1,  77,  31,  31,  31,  31,  31,  31,  31,   1,   1,  78,  31,
      1,   1,  79,  80,  31,  31,  31,  81,   1,   1,   1,   1,   1,   1,   1,  82,
      1,   1,  83,  31,  31,  31,  31,  31,  84,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  85,  31,  31,  31,  31,  86,  87,  31,  88,  89,  90,  91,
     31,  31,  92,  31,  31,  31,  31,  31,  93,  31,  31,  31,  31,  31,  31,  31,
     94,  95,  31,  31,  31,  31,  96,  31,   1,   1,   1,   1,   1,   1,  97,   1,
      1,   1,   1,   1,   1,   1,   1,  98,  99,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1, 100,  31,   1,   1, 101,  31,  31,  31,  31,  31,
     31, 102,  31,  31,  31,  31,  31,  31,
};

static RE_UINT8 re_id_continue_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   7,   8,   6,   6,   6,   9,  10,  11,   6,  12,
      6,   6,   6,   6,  13,   6,   6,   6,   6,  14,  15,  16,  17,  18,  19,  20,
     21,   6,   6,  22,   6,   6,  23,  24,  25,   6,  26,   6,   6,  27,   6,  28,
      6,  29,  30,   0,   0,  31,  32,  11,   6,   6,   6,  33,  34,  35,  36,  37,
     38,  39,  40,  41,  42,  43,  44,  45,  46,  43,  47,  48,  49,  50,  51,  52,
     53,  54,  55,  56,  53,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,
     16,  68,  69,   0,  70,  71,  72,   0,  73,  74,  75,  76,  77,  78,  79,   0,
      6,   6,  80,   6,  81,   6,  82,  83,   6,   6,  84,   6,  85,  86,  87,   6,
     88,   6,  61,  89,  90,   6,   6,  91,  16,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,  92,   3,   6,   6,  93,  94,  95,  96,  97,   6,   6,  98,  99,
    100,   6,   6, 101,   6, 102,   6, 103, 104, 105, 106, 107,   6, 108, 109,   0,
     30,   6, 104, 110, 111, 112,   0,   0,   6,   6, 113, 114,   6,   6,   6,  96,
      6, 101, 115,  81, 116,   0, 117, 118,   6,   6,   6,   6,   6,   6,   6, 119,
     91,   6, 120,  81,   6, 121, 122, 123,   0, 124, 125, 126, 127,   0, 127, 128,
    129, 130, 131,   6, 116,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6, 132, 104,   6,   6,   6,   6, 133,   6,  82,   6, 134, 135, 136, 136,   6,
    137, 138,  16,   6, 139,  16,   6,  83, 140, 141,   6,   6, 142,  68,   0,  25,
      6,   6,   6,   6,   6, 103,   0,   0,   6,   6,   6,   6,   6,   6, 103,   0,
      6,   6,   6,   6, 143,   0,  25,  81, 144, 145,   6, 146,   6,   6,   6,  27,
    147, 148,   6,   6, 149, 150,   0, 147,   6, 151,   6,  96,   6,   6, 152, 153,
      6, 154,  96,  78,   6,   6, 155, 104,   6, 135, 156, 157,   6,   6, 158, 159,
    160, 161,  83, 162,   6,   6,   6, 163,   6,   6,   6,   6,   6, 164, 165,  30,
      6,   6,   6, 154,   6,   6, 166,   0, 167, 168, 169,   6,   6,  27, 170,   6,
      6,  81,  25,   6, 171,   6, 151, 172,  90, 173, 174, 175,   6,   6,   6,  78,
      1,   2,   3, 106,   6, 104, 176,   0, 177, 178, 179,   0,   6,   6,   6,  68,
      0,   0,   6,  95,   0,   0,   0, 180,   0,   0,   0,   0,  78,   6, 181, 182,
      6,  25, 102,  68,  81,   6, 183,   0,   6,   6,   6,   6,  81,  80, 184,  30,
      6, 185,   6, 186,   0,   0,   0,   0,   6, 135, 103, 151,   0,   0,   0,   0,
    187, 188, 103, 135, 104,   0,   0, 189, 103, 166,   0,   0,   6, 190,   0,   0,
    191, 192,   0,  78,  78,   0,  75, 193,   6, 103, 103, 194,  27,   0,   0,   0,
      6,   6, 116,   0,   6, 194,   6, 194,   6,   6, 193, 195,   6,  68,  25, 196,
      6, 197,  25, 198,   6,   6, 199,   0, 200, 201,   0,   0, 202, 203,   6, 204,
     34,  43, 205, 206,   0,   0,   0,   0,   6,   6, 204,   0,   6,   6, 207,   0,
      0,   0,   0,   0,   6, 208, 209,   0,   6,   6, 210,   0,   6, 101,  99,   0,
    211, 113,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   6,   6, 212,
      0,   0,   0,   0,   0,   0,   6, 213, 214,   5, 215, 216, 171, 217,   0,   0,
      6,   6,   6,   6, 166,   0,   0,   0,   6,   6,   6, 142,   6,   6,   6,   6,
      6,   6, 186,   0,   0,   0,   0,   0,   6, 142,   0,   0,   0,   0,   0,   0,
      6,   6, 193,   0,   0,   0,   0,   0,   6, 213, 104,  99,   0,   0,  25, 107,
      6, 135, 218, 219,  90,   0,   0,   0,   6,   6, 220, 104, 221,   0,   0, 182,
      6,   6,   6,   6,   6,   6,   6, 143,   6,   6,   6,   6,   6,   6,   6, 194,
    222,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6, 223, 224,   0,   0,   0,
      0,   0,   0, 225, 226, 227,   0,   0,   0,   0, 228,   0,   0,   0,   0,   0,
      6,   6, 197,   6, 229, 230, 231,   6, 232, 233, 234,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6, 235, 236,  83, 197, 197, 132, 132, 214, 214, 237,   6,
      6, 238,   6, 239, 240, 241,   0,   0, 242, 243,   0,   0,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6, 244,   0,   6,   6, 204,   0,   0,   0,   0,   0,
    231, 245, 246, 247, 248, 249,   0,   0,   6,   6,   6,   6,   6,   6, 135,   0,
      6,  95,   6,   6,   6,   6,   6,   6,  81,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6, 222,   0,   0,  81,   0,   0,   0,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6,   6,  90,
};

static RE_UINT8 re_id_continue_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255, 135, 254, 255, 255,   7,
      0,   4, 160,   4, 255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,
     31,  80,   0,   0, 255, 255, 223, 188, 192, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255, 251, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2,
    254, 255, 255, 255, 255,   0, 254, 255, 255, 255, 255, 191, 182,   0, 255, 255,
    255,   7,   7,   0,   0,   0, 255,   7, 255, 195, 255, 255, 255, 255, 239, 159,
    255, 253, 255, 159,   0,   0, 255, 255, 255, 231, 255, 255, 255, 255,   3,   0,
    255, 255,  63,   4, 255,  63,   0,   0, 255, 255, 255,  15, 255, 255, 223,  63,
      0,   0, 240, 255, 207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 211,
    135,  57,   2,  94, 192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 243,
    191,  59,   1,   0, 207, 255,   0,   2, 238, 159, 249, 255, 159,  57, 192, 176,
    207, 255,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0,
    192, 255,   0,   0, 239, 223, 253, 255, 255, 253, 255, 227, 223,  61,  96,   7,
    207, 255,   0,   0, 255, 253, 239, 243, 223,  61,  96,  64, 207, 255,   6,   0,
    238, 223, 253, 255, 255, 255, 255, 231, 223, 125, 240, 128, 207, 255,   0, 252,
    236, 255, 127, 252, 255, 255, 251,  47, 127, 132,  95, 255, 192, 255,  12,   0,
    255, 255, 255,   7, 255, 127, 255,   3, 150,  37, 240, 254, 174, 236, 255,  59,
     95,  63, 255, 243,   1,   0,   0,   3, 255,   3, 160, 194, 255, 254, 255, 255,
    255,  31, 254, 255, 223, 255, 255, 254, 255, 255, 255,  31,  64,   0,   0,   0,
    255,   3, 255, 255, 255, 255, 255,  63, 191,  32, 255, 255, 255, 255, 255, 247,
    255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255,
    255, 255,  61, 255,   0, 254,   3,   0, 255, 255,   0,   0, 255, 255,  63,  63,
    255, 159, 255, 255, 255, 199, 255,   1, 255, 223,  31,   0, 255, 255,  31,   0,
    255, 255,  15,   0, 255, 223,  13,   0, 255, 255, 143,  48, 255,   3,   0,   0,
      0,  56, 255,   3, 255, 255, 255,   0, 255,   7, 255, 255, 255, 255,  63,   0,
    255, 255, 255, 127, 255,  15, 255,  15, 192, 255, 255, 255, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3, 255,   7, 255, 255, 255, 159, 255,   3, 255,   3,
    128,   0, 255,  63, 255,  15, 255,   3,   0, 248,  15,   0, 255, 227, 255, 255,
    255,   1,   0,   0,   0,   0, 247, 255, 255, 255, 127,   3, 255, 255,  63, 248,
     63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   0, 128,   1,   0,  16,   0,   0,   0,   2, 128,   0,   0, 255,  31,
    226, 255,   1,   0, 132, 252,  47,  63,  80, 253, 255, 243, 224,  67,   0,   0,
    255, 127, 255, 255,  31, 248,  15,   0, 255, 128,   0, 128, 255, 255, 127,   0,
    127, 127, 127, 127, 224,   0,   0,   0, 254, 255,  62,  31, 255, 255, 127, 254,
    224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31,   0,   0,
    255,  31, 255, 255, 255,  15,   0,   0, 255, 255, 240, 191,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0, 255,   0,   0,   0,
     63,   0, 255,   3, 255, 255, 255,  40, 255,  63, 255, 255,   1, 128, 255,   3,
    255,  63, 255,   3, 255, 255, 127, 252,   7,   0,   0,  56, 255, 255, 124,   0,
    126, 126, 126,   0, 127, 127, 255, 255,  63,   0, 255, 255, 255,  55, 255,   3,
     15,   0, 255, 255, 127, 248, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224,
    255, 253, 127,  95, 219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,
      0,   0, 255,  15, 255, 255,  24,   0,   0, 224,   0,   0,   0,   0, 223, 255,
    252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,
      0,   0,   0,  32, 255, 255,   1,   0,   1,   0,   0,   0,  15, 255,  62,   0,
    255, 255,  15, 255, 255,   0, 255, 255,  15,   0,   0,   0,  63, 253, 255, 255,
    255, 255, 191, 145, 255, 255,  55,   0, 255, 255, 255, 192, 111, 240, 239, 254,
    255, 255,  15, 135, 127,   0,   0,   0, 255, 255,   7,   0, 192, 255,   0, 128,
    255,   1, 255,   3, 255, 255, 223, 255, 255, 255,  79,   0,  31,  28, 255,  23,
    255, 255, 251, 255, 255, 255, 255,  64, 127, 189, 255, 191, 255,   1, 255, 255,
    255,   7, 255,   3, 159,  57, 129, 224, 207,  31,  31,   0, 191,   0, 255,   3,
    255, 255,  63, 255,   1,   0,   0,  63,  17,   0, 255,   3, 255, 255, 255, 227,
    255,   3,   0, 128, 255, 255, 255,   1, 255, 253, 255, 255,   1,   0, 255,   3,
      0,   0, 252, 255, 255, 254, 127,   0,  15,   0, 255,   3, 248, 255, 255, 224,
     31,   0, 255, 255,   0, 128, 255, 255,   3,   0,   0,   0, 255,   7, 255,  31,
    255,   1, 255,  99, 224, 227,   7, 248, 231,  15,   0,   0,   0,  60,   0,   0,
     28,   0,   0,   0, 255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255,
    191, 231, 223, 223, 255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255,
    253, 255, 255, 247, 247, 207, 255, 255, 255, 255, 127, 248, 255,  31,  32,   0,
     16,   0,   0, 248, 254, 255,   0,   0, 127, 255, 255, 249, 219,   7,   0,   0,
     31,   0, 127,   0, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94,
    255, 251, 255,  15, 238, 251, 255,  15,
};

/* ID_Continue: 2282 bytes. */

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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 13, 13, 28, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 29,  7, 30, 31,  7, 32, 13, 13, 13, 13, 13, 33,
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
    59, 60, 61, 62, 63, 31, 31, 31, 64, 65, 66, 67, 68, 69, 70, 71,
    72, 31, 73, 31, 74, 31, 31, 31,  1,  1,  1, 75, 76, 77, 31, 31,
     1,  1,  1,  1, 78, 31, 31, 31, 31, 31, 31, 31,  1,  1, 79, 31,
     1,  1, 80, 81, 31, 31, 31, 82,  1,  1,  1,  1,  1,  1,  1, 83,
     1,  1, 84, 31, 31, 31, 31, 31, 85, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 86, 31, 31, 31, 31, 31, 31, 31, 87, 88, 89, 90,
    91, 77, 31, 31, 31, 31, 92, 31,  1,  1,  1,  1,  1,  1, 93,  1,
     1,  1,  1,  1,  1,  1,  1, 94, 95,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1, 96, 31,  1,  1, 97, 31, 31, 31, 31, 31,
};

static RE_UINT8 re_xid_start_stage_4[] = {
      0,   0,   1,   1,   0,   2,   3,   3,   4,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   5,   6,   0,   0,   0,   7,   8,   9,   4,  10,
      4,   4,   4,   4,  11,   4,   4,   4,   4,  12,  13,  14,  15,   0,  16,  17,
      0,   4,  18,  19,   4,   4,  20,  21,  22,  23,  24,   4,   4,  25,  26,  27,
     28,  29,  30,   0,   0,  31,   0,   0,  32,  33,  34,  35,  36,  37,  38,  39,
     40,  41,  42,  43,  44,  45,  46,  47,  48,  45,  49,  50,  51,  52,  46,   0,
     53,  54,  55,  56,  57,  58,  59,  60,  53,  61,  62,  63,  64,  65,  66,   0,
     14,  67,  66,   0,  68,  69,  70,   0,  71,   0,  72,  73,  74,   0,   0,   0,
      4,  75,  76,  77,  78,   4,  79,  80,   4,   4,  81,   4,  82,  83,  84,   4,
     85,   4,  86,   0,  23,   4,   4,  87,  14,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,  88,   1,   4,   4,  89,  90,  91,  91,  92,   4,  93,  94,   0,
      0,   4,   4,  95,   4,  96,   4,  97,  98,   0,  16,  99,   4, 100, 101,   0,
    102,   4, 103,   0,   0, 104,   0,   0, 105,  93, 106,   0, 107, 108,   4, 109,
      4, 110, 111, 112, 113,   0,   0, 114,   4,   4,   4,   4,   4,   4,   0,   0,
     87,   4, 115, 112,   4, 116, 117, 118,   0,   0,   0, 119, 120,   0,   0,   0,
    121, 122, 123,   4, 113,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      4, 124,  98,   4,   4,   4,   4, 125,   4,  79,   4, 126, 102, 127, 127,   0,
    128, 129,  14,   4, 130,  14,   4,  80, 105, 131,   4,   4, 132,  86,   0,  16,
      4,   4,   4,   4,   4,  97,   0,   0,   4,   4,   4,   4,   4,   4,  97,   0,
      4,   4,   4,   4,  73,   0,  16, 112, 133, 134,   4, 135, 112,   4,   4,  23,
    136, 137,   4,   4, 138, 139,   0, 136, 140, 141,   4,  93, 137,  93,   0, 142,
     26, 143,  66, 144,  32, 145, 146, 147,   4, 113, 148, 149,   4, 150, 151, 152,
    153, 154,  80, 143,   4,   4,   4, 141,   4,   4,   4,   4,   4, 155, 156, 157,
      4,   4,   4, 158,   4,   4, 159,   0, 160, 161, 162,   4,   4,  91, 163,   4,
      4,   4, 112,  32,   4,   4,   4,   4,   4, 112,  16,   4, 164,   4,  15, 165,
      0,   0,   0, 166,   4,   4,   4, 144,   0,   1,   1, 167, 112,  98, 168,   0,
    169, 170, 171,   0,   4,   4,   4,  86,   0,   0,   4, 103,   0,   0,   0,   0,
      0,   0,   0,   0, 144,   4, 172,   0,   4,  16, 173,  97, 112,   4, 174,   0,
      4,   4,   4,   4, 112,  16, 175, 157,   4, 176,   4, 110,   0,   0,   0,   0,
      4, 102,  97,  15,   0,   0,   0,   0, 177, 178,  97, 102,  98,   0,   0, 179,
     97, 159,   0,   0,   4, 180,   0,   0, 181,  93,   0, 144, 144,   0,  72, 182,
      4,  97,  97, 145,  91,   0,   0,   0,   4,   4, 113,   0,   4, 145,   4, 145,
    107,  95,   0,   0, 107,  23,  16, 113, 107,  66,  16, 183, 107, 145, 184,   0,
    185, 186,   0,   0, 187, 188,  98,   0,  48,  45, 189,  56,   0,   0,   0,   0,
      4, 103, 190,   0,   4,  23, 191,   0,   0,   0,   0,   0,   4, 132, 192,   0,
      4,  23, 193,   0,   4,  18,   0,   0, 159,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   4,   4, 194,   0,   0,   0,   0,   0,   0,   4,  30,
    195, 132,  71, 196,  23,   0,   0,   0,   4,   4,   4,   4, 159,   0,   0,   0,
      4,   4,   4, 132,   4,   4,   4,   4,   4,   4, 110,   0,   0,   0,   0,   0,
      4, 132,   0,   0,   0,   0,   0,   0,   4,   4,  66,   0,   0,   0,   0,   0,
      4,  30,  98,   0,   0,   0,  16, 197,   4,  23, 110, 198,  23,   0,   0,   0,
      4,   4, 199,   0, 163,   0,   0,  71,   4,   4,   4,   4,   4,   4,   4,  73,
      4,   4,   4,   4,   4,   4,   4, 145,  56,   0,   0,   0,   0,   0,   0,   0,
      4,   4,   4, 200, 201,   0,   0,   0,   4,   4, 202,   4, 203, 204, 205,   4,
    206, 207, 208,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4, 209, 210,  80,
    202, 202, 124, 124, 195, 195, 148,   0,   4,   4,   4,   4,   4,   4, 182,   0,
    205, 211, 212, 213, 214, 215,   0,   0,   4,   4,   4,   4,   4,   4, 102,   0,
      4, 103,   4,   4,   4,   4,   4,   4, 112,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,  56,   0,   0, 112,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_xid_start_stage_5[] = {
      0,   0,   0,   0, 254, 255, 255,   7,   0,   4,  32,   4, 255, 255, 127, 255,
    255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,   0,   0, 223, 184,
     64, 215, 255, 255, 251, 255, 255, 255, 255, 255, 191, 255,   3, 252, 255, 255,
    255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255, 255,   0,   0,   0,
      0,   0, 255, 255, 255,   7,   7,   0, 255,   7,   0,   0,   0, 192, 254, 255,
    255, 255,  47,   0,  96, 192,   0, 156,   0,   0, 253, 255, 255, 255,   0,   0,
      0, 224, 255, 255,  63,   0,   2,   0,   0, 252, 255, 255, 255,   7,  48,   4,
    255, 255,  63,   4,  16,   1,   0,   0, 255, 255, 255,   1, 255, 255, 223,  63,
    240, 255, 255, 255, 255, 255, 255,  35,   0,   0,   1, 255,   3,   0, 254, 255,
    225, 159, 249, 255, 255, 253, 197,  35,   0,  64,   0, 176,   3,   0,   3,   0,
    224, 135, 249, 255, 255, 253, 109,   3,   0,   0,   0,  94,   0,   0,  28,   0,
    224, 191, 251, 255, 255, 253, 237,  35,   0,   0,   1,   0,   3,   0,   0,   2,
    224, 159, 249, 255,   0,   0,   0, 176,   3,   0,   2,   0, 232, 199,  61, 214,
     24, 199, 255,   3, 224, 223, 253, 255, 255, 253, 255,  35,   0,   0,   0,   7,
      3,   0,   0,   0, 225, 223, 253, 255, 255, 253, 239,  35,   0,   0,   0,  64,
      3,   0,   6,   0, 255, 255, 255,  39,   0,  64, 112, 128,   3,   0,   0, 252,
    224, 255, 127, 252, 255, 255, 251,  47, 127,   0,   0,   0, 255, 255,   5,   0,
    150,  37, 240, 254, 174, 236,   5,  32,  95,   0,   0, 240,   1,   0,   0,   0,
    255, 254, 255, 255, 255,  31,   0,   0,   0,  31,   0,   0, 255,   7,   0, 128,
      0,   0,  63,  60,  98, 192, 225, 255,   3,  64,   0,   0, 191,  32, 255, 255,
    255, 255, 255, 247, 255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,
     61, 255, 127, 255, 255, 255,  61, 255, 255, 255, 255,   7, 255, 255,  63,  63,
    255, 159, 255, 255, 255, 199, 255,   1, 255, 223,   3,   0, 255, 255,   3,   0,
    255, 223,   1,   0, 255, 255,  15,   0,   0,   0, 128,  16, 255, 255, 255,   0,
    255,   5, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3,   0,   0, 255, 255, 127,   0, 255, 255,  31,   0,
    128,   0,   0,   0, 224, 255, 255, 255, 224,  15,   0,   0, 248, 255, 255, 255,
      1, 192,   0, 252,  63,   0,   0,   0,  15,   0,   0,   0,   0, 224,   0, 252,
    255, 255, 255,  63, 255,   1,   0,   0,   0, 222,  99,   0,  63,  63, 255, 170,
    255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   2, 128,
      0,   0, 255,  31, 132, 252,  47,  63,  80, 253, 255, 243, 224,  67,   0,   0,
    255, 127, 255, 255,  31, 120,  12,   0, 255, 128,   0,   0, 127, 127, 127, 127,
    224,   0,   0,   0, 254,   3,  62,  31, 255, 255, 127, 224, 255,  63, 254, 255,
    255, 127,   0,   0, 255,  31, 255, 255,   0,  12,   0,   0, 255, 127,   0, 128,
      0,   0, 128, 255, 252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0,
    187, 247, 255, 255,   7,   0,   0,   0,   0,   0, 252,  40,  63,   0, 255, 255,
    255, 255, 255,  31, 255, 255,   7,   0,   0, 128,   0,   0, 223, 255,   0, 124,
    247,  15,   0,   0, 255, 255, 127, 196, 255, 255,  98,  62,   5,   0,   0,  56,
    255,   7,  28,   0, 126, 126, 126,   0, 127, 127, 255, 255,  15,   0, 255, 255,
    127, 248, 255, 255, 255, 255, 255,  15, 255,  63, 255, 255, 255, 255, 255,   3,
    127,   0, 248, 160, 255, 253, 127,  95, 219, 255, 255, 255,   0,   0, 248, 255,
    255, 255, 252, 255,   0,   0, 255,   3,   0,   0, 138, 170, 192, 255, 255, 255,
    252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,
    255, 255,   1,   0, 255,   7, 255, 255,  15, 255,  62,   0, 255, 255,  15, 255,
    255,   0, 255, 255,  63, 253, 255, 255, 255, 255, 191, 145, 255, 255,  55,   0,
    255, 255, 255, 192,   1,   0, 239, 254,  31,   0,   0,   0, 255, 255,  71,   0,
     30,   0,   0,  20, 255, 255, 251, 255, 255,  15,   0,   0, 127, 189, 255, 191,
    255,   1, 255, 255,   0,   0,   1, 224, 128,   7,   0,   0, 176,   0,   0,   0,
      0,   0,   0,  15,  16,   0,   0,   0,   0,   0,   0, 128, 255, 253, 255, 255,
      0,   0, 252, 255, 255,  63,   0,   0, 248, 255, 255, 224,  31,   0,   1,   0,
    255,   7, 255,  31, 255,   1, 255,   3, 255, 255, 223, 255, 255, 255, 255, 223,
    100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,
     95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247, 150, 254, 247,  10,
    132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
};

/* XID_Start: 2065 bytes. */

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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 28, 29, 30, 13, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 31,  7, 32, 33,  7, 34, 13, 13, 13, 13, 13, 35,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    36, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_xid_continue_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  31,  31,  31,  31,  31,  31,  31,  31,  32,  33,  31,  31,
     34,  35,  31,  31,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  36,   1,   1,   1,   1,   1,   1,   1,   1,   1,  37,
      1,   1,   1,   1,  38,   1,  39,  40,  41,  42,  43,  44,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  45,  31,  31,  31,  31,  31,  31,  31,  31,
     31,   1,  46,  47,  48,  49,  50,  51,  52,  53,  54,  55,  56,  57,   1,  58,
     59,  60,  61,  62,  63,  31,  31,  31,  64,  65,  66,  67,  68,  69,  70,  71,
     72,  31,  73,  31,  74,  31,  31,  31,   1,   1,   1,  75,  76,  77,  31,  31,
      1,   1,   1,   1,  78,  31,  31,  31,  31,  31,  31,  31,   1,   1,  79,  31,
      1,   1,  80,  81,  31,  31,  31,  82,   1,   1,   1,   1,   1,   1,   1,  83,
      1,   1,  84,  31,  31,  31,  31,  31,  85,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  86,  31,  31,  31,  31,  87,  88,  31,  89,  90,  91,  92,
     31,  31,  93,  31,  31,  31,  31,  31,  94,  31,  31,  31,  31,  31,  31,  31,
     95,  96,  31,  31,  31,  31,  97,  31,   1,   1,   1,   1,   1,   1,  98,   1,
      1,   1,   1,   1,   1,   1,   1,  99, 100,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1, 101,  31,   1,   1, 102,  31,  31,  31,  31,  31,
     31, 103,  31,  31,  31,  31,  31,  31,
};

static RE_UINT8 re_xid_continue_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   7,   8,   6,   6,   6,   9,  10,  11,   6,  12,
      6,   6,   6,   6,  13,   6,   6,   6,   6,  14,  15,  16,  17,  18,  19,  20,
     21,   6,   6,  22,   6,   6,  23,  24,  25,   6,  26,   6,   6,  27,   6,  28,
      6,  29,  30,   0,   0,  31,  32,  11,   6,   6,   6,  33,  34,  35,  36,  37,
     38,  39,  40,  41,  42,  43,  44,  45,  46,  43,  47,  48,  49,  50,  51,  52,
     53,  54,  55,  56,  53,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,
     16,  68,  69,   0,  70,  71,  72,   0,  73,  74,  75,  76,  77,  78,  79,   0,
      6,   6,  80,   6,  81,   6,  82,  83,   6,   6,  84,   6,  85,  86,  87,   6,
     88,   6,  61,  89,  90,   6,   6,  91,  16,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,  92,   3,   6,   6,  93,  94,  95,  96,  97,   6,   6,  98,  99,
    100,   6,   6, 101,   6, 102,   6, 103, 104, 105, 106, 107,   6, 108, 109,   0,
     30,   6, 104, 110, 111, 112,   0,   0,   6,   6, 113, 114,   6,   6,   6,  96,
      6, 101, 115,  81, 116,   0, 117, 118,   6,   6,   6,   6,   6,   6,   6, 119,
     91,   6, 120,  81,   6, 121, 122, 123,   0, 124, 125, 126, 127,   0, 127, 128,
    129, 130, 131,   6, 116,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6, 132, 104,   6,   6,   6,   6, 133,   6,  82,   6, 134, 135, 136, 136,   6,
    137, 138,  16,   6, 139,  16,   6,  83, 140, 141,   6,   6, 142,  68,   0,  25,
      6,   6,   6,   6,   6, 103,   0,   0,   6,   6,   6,   6,   6,   6, 103,   0,
      6,   6,   6,   6, 143,   0,  25,  81, 144, 145,   6, 146,   6,   6,   6,  27,
    147, 148,   6,   6, 149, 150,   0, 147,   6, 151,   6,  96,   6,   6, 152, 153,
      6, 154,  96,  78,   6,   6, 155, 104,   6, 135, 156, 157,   6,   6, 158, 159,
    160, 161,  83, 162,   6,   6,   6, 163,   6,   6,   6,   6,   6, 164, 165,  30,
      6,   6,   6, 154,   6,   6, 166,   0, 167, 168, 169,   6,   6,  27, 170,   6,
      6,   6,  81, 171,   6,   6,   6,   6,   6,  81,  25,   6, 172,   6, 151,   1,
     90, 173, 174, 175,   6,   6,   6,  78,   1,   2,   3, 106,   6, 104, 176,   0,
    177, 178, 179,   0,   6,   6,   6,  68,   0,   0,   6,  95,   0,   0,   0, 180,
      0,   0,   0,   0,  78,   6, 181, 182,   6,  25, 102,  68,  81,   6, 183,   0,
      6,   6,   6,   6,  81,  80, 184,  30,   6, 185,   6, 186,   0,   0,   0,   0,
      6, 135, 103, 151,   0,   0,   0,   0, 187, 188, 103, 135, 104,   0,   0, 189,
    103, 166,   0,   0,   6, 190,   0,   0, 191, 192,   0,  78,  78,   0,  75, 193,
      6, 103, 103, 194,  27,   0,   0,   0,   6,   6, 116,   0,   6, 194,   6, 194,
      6,   6, 193, 195,   6,  68,  25, 196,   6, 197,  25, 198,   6,   6, 199,   0,
    200, 201,   0,   0, 202, 203,   6, 204,  34,  43, 205, 206,   0,   0,   0,   0,
      6,   6, 204,   0,   6,   6, 207,   0,   0,   0,   0,   0,   6, 208, 209,   0,
      6,   6, 210,   0,   6, 101,  99,   0, 211, 113,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   6,   6, 212,   0,   0,   0,   0,   0,   0,   6, 213,
    214,   5, 215, 216, 172, 217,   0,   0,   6,   6,   6,   6, 166,   0,   0,   0,
      6,   6,   6, 142,   6,   6,   6,   6,   6,   6, 186,   0,   0,   0,   0,   0,
      6, 142,   0,   0,   0,   0,   0,   0,   6,   6, 193,   0,   0,   0,   0,   0,
      6, 213, 104,  99,   0,   0,  25, 107,   6, 135, 218, 219,  90,   0,   0,   0,
      6,   6, 220, 104, 221,   0,   0, 182,   6,   6,   6,   6,   6,   6,   6, 143,
      6,   6,   6,   6,   6,   6,   6, 194, 222,   0,   0,   0,   0,   0,   0,   0,
      6,   6,   6, 223, 224,   0,   0,   0,   0,   0,   0, 225, 226, 227,   0,   0,
      0,   0, 228,   0,   0,   0,   0,   0,   6,   6, 197,   6, 229, 230, 231,   6,
    232, 233, 234,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6, 235, 236,  83,
    197, 197, 132, 132, 214, 214, 237,   6,   6, 238,   6, 239, 240, 241,   0,   0,
    242, 243,   0,   0,   0,   0,   0,   0,   6,   6,   6,   6,   6,   6, 244,   0,
      6,   6, 204,   0,   0,   0,   0,   0, 231, 245, 246, 247, 248, 249,   0,   0,
      6,   6,   6,   6,   6,   6, 135,   0,   6,  95,   6,   6,   6,   6,   6,   6,
     81,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6, 222,   0,   0,
     81,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6,   6,   6,   6,   6,  90,
};

static RE_UINT8 re_xid_continue_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255, 135, 254, 255, 255,   7,
      0,   4, 160,   4, 255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,
     31,  80,   0,   0, 255, 255, 223, 184, 192, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255, 251, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2,
    254, 255, 255, 255, 255,   0, 254, 255, 255, 255, 255, 191, 182,   0, 255, 255,
    255,   7,   7,   0,   0,   0, 255,   7, 255, 195, 255, 255, 255, 255, 239, 159,
    255, 253, 255, 159,   0,   0, 255, 255, 255, 231, 255, 255, 255, 255,   3,   0,
    255, 255,  63,   4, 255,  63,   0,   0, 255, 255, 255,  15, 255, 255, 223,  63,
      0,   0, 240, 255, 207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 211,
    135,  57,   2,  94, 192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 243,
    191,  59,   1,   0, 207, 255,   0,   2, 238, 159, 249, 255, 159,  57, 192, 176,
    207, 255,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0,
    192, 255,   0,   0, 239, 223, 253, 255, 255, 253, 255, 227, 223,  61,  96,   7,
    207, 255,   0,   0, 255, 253, 239, 243, 223,  61,  96,  64, 207, 255,   6,   0,
    238, 223, 253, 255, 255, 255, 255, 231, 223, 125, 240, 128, 207, 255,   0, 252,
    236, 255, 127, 252, 255, 255, 251,  47, 127, 132,  95, 255, 192, 255,  12,   0,
    255, 255, 255,   7, 255, 127, 255,   3, 150,  37, 240, 254, 174, 236, 255,  59,
     95,  63, 255, 243,   1,   0,   0,   3, 255,   3, 160, 194, 255, 254, 255, 255,
    255,  31, 254, 255, 223, 255, 255, 254, 255, 255, 255,  31,  64,   0,   0,   0,
    255,   3, 255, 255, 255, 255, 255,  63, 191,  32, 255, 255, 255, 255, 255, 247,
    255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255,
    255, 255,  61, 255,   0, 254,   3,   0, 255, 255,   0,   0, 255, 255,  63,  63,
    255, 159, 255, 255, 255, 199, 255,   1, 255, 223,  31,   0, 255, 255,  31,   0,
    255, 255,  15,   0, 255, 223,  13,   0, 255, 255, 143,  48, 255,   3,   0,   0,
      0,  56, 255,   3, 255, 255, 255,   0, 255,   7, 255, 255, 255, 255,  63,   0,
    255, 255, 255, 127, 255,  15, 255,  15, 192, 255, 255, 255, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3, 255,   7, 255, 255, 255, 159, 255,   3, 255,   3,
    128,   0, 255,  63, 255,  15, 255,   3,   0, 248,  15,   0, 255, 227, 255, 255,
    255,   1,   0,   0,   0,   0, 247, 255, 255, 255, 127,   3, 255, 255,  63, 248,
     63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,
      0,   0,   0, 128,   1,   0,  16,   0,   0,   0,   2, 128,   0,   0, 255,  31,
    226, 255,   1,   0, 132, 252,  47,  63,  80, 253, 255, 243, 224,  67,   0,   0,
    255, 127, 255, 255,  31, 248,  15,   0, 255, 128,   0, 128, 255, 255, 127,   0,
    127, 127, 127, 127, 224,   0,   0,   0, 254, 255,  62,  31, 255, 255, 127, 230,
    224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31,   0,   0,
    255,  31, 255, 255, 255,  15,   0,   0, 255, 255, 240, 191,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0, 255,   0,   0,   0,
     63,   0, 255,   3, 255, 255, 255,  40, 255,  63, 255, 255,   1, 128, 255,   3,
    255,  63, 255,   3, 255, 255, 127, 252,   7,   0,   0,  56, 255, 255, 124,   0,
    126, 126, 126,   0, 127, 127, 255, 255,  63,   0, 255, 255, 255,  55, 255,   3,
     15,   0, 255, 255, 127, 248, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224,
    255, 253, 127,  95, 219, 255, 255, 255,   0,   0, 248, 255, 240, 255, 255, 255,
    255, 255, 252, 255, 255, 255,  24,   0,   0, 224,   0,   0,   0,   0, 138, 170,
    252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,
      0,   0,   0,  32, 255, 255,   1,   0,   1,   0,   0,   0,  15, 255,  62,   0,
    255, 255,  15, 255, 255,   0, 255, 255,  15,   0,   0,   0,  63, 253, 255, 255,
    255, 255, 191, 145, 255, 255,  55,   0, 255, 255, 255, 192, 111, 240, 239, 254,
    255, 255,  15, 135, 127,   0,   0,   0, 255, 255,   7,   0, 192, 255,   0, 128,
    255,   1, 255,   3, 255, 255, 223, 255, 255, 255,  79,   0,  31,  28, 255,  23,
    255, 255, 251, 255, 255, 255, 255,  64, 127, 189, 255, 191, 255,   1, 255, 255,
    255,   7, 255,   3, 159,  57, 129, 224, 207,  31,  31,   0, 191,   0, 255,   3,
    255, 255,  63, 255,   1,   0,   0,  63,  17,   0, 255,   3, 255, 255, 255, 227,
    255,   3,   0, 128, 255, 255, 255,   1, 255, 253, 255, 255,   1,   0, 255,   3,
      0,   0, 252, 255, 255, 254, 127,   0,  15,   0, 255,   3, 248, 255, 255, 224,
     31,   0, 255, 255,   0, 128, 255, 255,   3,   0,   0,   0, 255,   7, 255,  31,
    255,   1, 255,  99, 224, 227,   7, 248, 231,  15,   0,   0,   0,  60,   0,   0,
     28,   0,   0,   0, 255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255,
    191, 231, 223, 223, 255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255,
    253, 255, 255, 247, 247, 207, 255, 255, 255, 255, 127, 248, 255,  31,  32,   0,
     16,   0,   0, 248, 254, 255,   0,   0, 127, 255, 255, 249, 219,   7,   0,   0,
     31,   0, 127,   0, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94,
    255, 251, 255,  15, 238, 251, 255,  15,
};

/* XID_Continue: 2290 bytes. */

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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2,
    2,
};

static RE_UINT8 re_grapheme_extend_stage_2[] = {
     0,  1,  2,  3,  4,  4,  4,  4,  4,  4,  5,  4,  4,  4,  4,  6,
     7,  8,  4,  4,  4,  4,  9,  4,  4,  4,  4, 10,  4, 11, 12,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
    13,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
};

static RE_UINT8 re_grapheme_extend_stage_3[] = {
     0,  0,  0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,
    14,  0,  0, 15,  0,  0,  0, 16, 17, 18, 19, 20, 21, 22,  0,  0,
    23,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 24, 25,  0,  0,
    26,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 27,  0, 28, 29, 30, 31,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 32,  0,  0, 33, 34,
     0, 35, 36, 37,  0,  0,  0,  0,  0,  0, 38,  0,  0,  0,  0,  0,
    39, 40, 41, 42, 43, 44, 45, 46,  0,  0,  0,  0, 47,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 48, 49,  0,  0,  0, 50,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 51,  0,  0,  0,
     0, 52, 53,  0,  0,  0,  0,  0,  0,  0, 54,  0,  0,  0,  0,  0,
    55,  0,  0,  0,  0,  0,  0,  0, 56, 57,  0,  0,  0,  0,  0,  0,
    58, 59,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_grapheme_extend_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   2,   0,   0,   0,   0,
      0,   0,   0,   0,   3,   0,   0,   0,   0,   0,   0,   0,   4,   5,   6,   0,
      7,   0,   8,   9,   0,   0,  10,  11,  12,  13,  14,   0,   0,  15,   0,  16,
     17,  18,  19,   0,   0,   0,  20,  21,  22,  23,  24,  25,  26,  27,  28,  25,
     29,  30,  31,  32,  29,  30,  33,  25,  26,  34,  35,  25,  36,  37,  38,   0,
     39,  40,  41,  25,  26,  42,  43,  25,  26,  37,  28,  25,   0,   0,  44,   0,
      0,  45,  46,   0,   0,  47,  48,   0,  49,  50,   0,  51,  52,  53,  54,   0,
      0,  55,  56,  57,  58,   0,   0,   0,   0,   0,  59,   0,   0,   0,   0,   0,
     60,  60,  61,  61,   0,  62,  63,   0,  64,   0,   0,   0,  65,  66,   0,   0,
      0,  67,   0,   0,   0,   0,   0,   0,  68,   0,  69,  70,   0,  71,   0,   0,
     72,  73,  36,  16,  74,  75,   0,  76,   0,  77,   0,   0,   0,   0,  78,  79,
      0,   0,   0,   0,   0,   0,   1,  80,  81,   0,   0,   0,   0,   0,  13,  82,
      0,   0,   0,   0,   0,   0,   0,  83,   0,   0,   0,  84,   0,   0,   0,   1,
      0,  85,   0,   0,  86,   0,   0,   0,   0,   0,   0,  87,  40,   0,   0,  88,
     89,  65,   0,   0,   0,   0,  90,  91,   0,  92,  93,   0,  22,  94,   0,  95,
      0,  96,  97,  30,   0,  98,  26,  99,   0,   0,   0,   0,   0,   0,   0, 100,
     37,   0,   0,   0,   0,   0,   0,   0,   2,   2,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  40,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 101,
      0,   0,   0,   0,   0,   0,   0,  39,   0,   0,   0, 102,   0,   0,   0,   0,
    103, 104,   0,   0,   0,   0,   0,  65,  26, 105, 106,  84,  74, 107,   0,   0,
     22, 108,   0, 109,  74, 110, 111,   0,   0, 112,   0,   0,   0,   0,  84, 113,
     74,  27, 114, 115,   0,   0,   0,   0,   0, 105, 116,   0,   0, 117, 118,   0,
      0,   0,   0,   0,   0, 119, 120,   0,   0, 121,  39,   0,   0, 122,   0,   0,
     59, 123,   0,   0,   0,   0,   0,   0,   0, 124,   0,   0, 125, 126,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 127,   0, 128,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0, 129,   0,   0,   0,   0,   0,   0,   0, 130,   0,   0,   0,
      0,   0,   0, 131, 132, 133,   0,   0,   0,   0, 134,   0,   0,   0,   0,   0,
      1, 135,   1, 136, 137, 138,   0,   0, 139, 140,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 128,   0,   0,   0, 141,   0,   0,   0,   0,   0,
      0,   1,   1,   1,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,   1,   2,
};

static RE_UINT8 re_grapheme_extend_stage_5[] = {
      0,   0,   0,   0, 255, 255, 255, 255, 255, 255,   0,   0, 248,   3,   0,   0,
      0,   0, 254, 255, 255, 255, 255, 191, 182,   0,   0,   0,   0,   0, 255,   7,
      0, 248, 255, 255,   0,   0,   1,   0,   0,   0, 192, 159, 159,  61,   0,   0,
      0,   0,   2,   0,   0,   0, 255, 255, 255,   7,   0,   0, 192, 255,   1,   0,
      0, 248,  15,   0,   0,   0, 192, 251, 239,  62,   0,   0,   0,   0,   0,  14,
      0,   0, 240, 255, 251, 255, 255, 255,   7,   0,   0,   0,   0,   0,   0,  20,
    254,  33, 254,   0,  12,   0,   0,   0,   2,   0,   0,   0,   0,   0,   0,  80,
     30,  32, 128,   0,   6,   0,   0,   0,   0,   0,   0,  16, 134,  57,   2,   0,
      0,   0,  35,   0, 190,  33,   0,   0,   0,   0,   0, 208,  30,  32, 192,   0,
      4,   0,   0,   0,   0,   0,   0,  64,   1,  32, 128,   0,   1,   0,   0,   0,
      0,   0,   0, 192, 193,  61,  96,   0,   0,   0,   0, 144,  68,  48,  96,   0,
      0, 132,  92, 128,   0,   0, 242,   7, 128, 127,   0,   0,   0,   0, 242,  27,
      0,  63,   0,   0,   0,   0,   0,   3,   0,   0, 160,   2,   0,   0, 254, 127,
    223, 224, 255, 254, 255, 255, 255,  31,  64,   0,   0,   0,   0, 224, 253, 102,
      0,   0,   0, 195,   1,   0,  30,   0, 100,  32,   0,  32,   0,   0,   0, 224,
      0,   0,  28,   0,   0,   0,  12,   0,   0,   0, 176,  63,  64, 254,  15,  32,
      0,  56,   0,   0,  96,   0,   0,   0,   0,   2,   0,   0, 135,   1,   4,  14,
      0,   0, 128,   9,   0,   0,  64, 127, 229,  31, 248, 159,   0,   0, 255, 127,
     15,   0,   0,   0,   0,   0, 208,  23,   3,   0,   0,   0,  60,  59,   0,   0,
     64, 163,   3,   0,   0, 240, 207,   0,   0,   0, 247, 255, 253,  33,  16,   3,
    255, 255,  63, 248,   0,  16,   0,   0, 255, 255,   1,   0,   0, 128,   3,   0,
      0,   0,   0, 128,   0, 252,   0,   0,   0,   0,   0,   6,   0, 128, 247,  63,
      0,   0,   3,   0,  68,   8,   0,   0,  48,   0,   0,   0, 255, 255,   3,   0,
    192,  63,   0,   0, 128, 255,   3,   0,   0,   0, 200,  19,  32,   0,   0,   0,
      0, 126, 102,   0,   8,  16,   0,   0,   0,   0, 157, 193,   0,  48,  64,   0,
     32,  33,   0,   0,   0,   0,   0,  32,   0,   0, 192,   7, 110, 240,   0,   0,
      0,   0,   0, 135,   0,   0,   0, 255, 127,   0,   0,   0,   0,   0, 120,   6,
    128, 239,  31,   0,   0,   0,   8,   0,   0,   0, 192, 127,   0,  28,   0,   0,
      0, 128, 211,  64, 248,   7,   0,   0,   1,   0, 128,   0, 192,  31,  31,   0,
     92,   0,   0,   0,   0,   0, 249, 165,  13,   0,   0,   0,   0, 128,  60, 176,
      1,   0,   0,  48,   0,   0, 248, 167,   0,  40, 191,   0, 188,  15,   0,   0,
      0,   0, 127, 191,   0,   0, 252, 255, 255, 252, 109,   0,   0,   0,  31,   0,
      0,   0, 127,   0,   0, 128,   7,   0,   0,   0,   0,  96, 160, 195,   7, 248,
    231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0, 255, 255, 127, 248,
    255,  31,  32,   0,  16,   0,   0, 248, 254, 255,   0,   0, 127, 255, 255, 249,
    219,   7,   0,   0, 240,   7,   0,   0,
};

/* Grapheme_Extend: 1353 bytes. */

RE_UINT32 re_get_grapheme_extend(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_grapheme_extend_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_grapheme_extend_stage_2[pos + f] << 4;
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
    0, 1, 2, 3, 4, 5, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
    6, 6,
};

static RE_UINT8 re_grapheme_base_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 13, 13,
    13, 13, 13, 14, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 15, 13, 16, 17, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 18, 19, 19, 19, 19, 19, 19, 19, 19, 20, 21,
    22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 19, 19, 13, 32, 19, 19,
    19, 33, 19, 19, 19, 19, 19, 19, 19, 19, 34, 35, 13, 13, 13, 13,
    13, 36, 37, 19, 19, 19, 19, 19, 19, 19, 19, 19, 38, 19, 19, 39,
    19, 19, 19, 19, 40, 41, 42, 19, 19, 19, 43, 44, 45, 46, 47, 19,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 48, 13, 13, 13, 49, 50, 13,
    13, 13, 13, 51, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 52, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
};

static RE_UINT8 re_grapheme_base_stage_3[] = {
      0,   1,   2,   2,   2,   2,   3,   4,   2,   5,   6,   7,   8,   9,  10,  11,
     12,  13,  14,  15,  16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  29,   2,   2,  30,  31,  32,  33,   2,   2,   2,   2,   2,  34,  35,  36,
     37,  38,  39,  40,  41,  42,  43,  44,  45,  46,   2,  47,   2,   2,  48,  49,
     50,  51,   2,  52,   2,   2,   2,  53,  54,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,  55,  56,  57,  58,  59,  60,  61,  62,   2,  63,
     64,  65,  66,  67,  68,  53,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,  69,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  70,
      2,  71,   2,   2,  72,  73,   2,  74,  75,  76,  77,  78,  79,  80,  81,  82,
      2,   2,   2,   2,   2,   2,   2,  83,  84,  84,  84,  84,  84,  84,  84,  84,
     84,  84,   2,   2,  85,  86,  87,  88,   2,   2,  89,  90,  91,  92,  93,  94,
     95,  96,  97,  98,  84,  99, 100, 101,   2, 102, 103,  84,   2,   2, 104,  84,
    105, 106, 107, 108, 109, 110, 111, 112, 113, 114,  84,  84, 115,  84,  84,  84,
    116, 117, 118, 119, 120, 121, 122,  84, 123, 124,  84, 125, 126, 127, 128,  84,
     84, 129,  84,  84,  84, 130,  84,  84, 131, 132,  84,  84,  84,  84,  84,  84,
      2,   2,   2,   2,   2,   2,   2, 133, 134,   2, 135,  84,  84,  84,  84,  84,
    136,  84,  84,  84,  84,  84,  84,  84,   2,   2,   2,   2, 137,  84,  84,  84,
      2,   2,   2,   2, 138, 139, 140, 141,  84,  84,  84,  84,  84,  84, 142, 143,
      2,   2,   2,   2,   2,   2,   2, 144,   2,   2,   2,   2,   2, 145,  84,  84,
    146,  84,  84,  84,  84,  84,  84,  84, 147, 148,  84,  84,  84,  84,  84,  84,
      2, 149, 150, 151, 152,  84, 153,  84, 154, 155, 156,   2,   2, 157,   2, 158,
      2,   2,   2,   2, 159, 160,  84,  84,   2, 161, 162,  84,  84,  84,  84,  84,
     84,  84,  84,  84, 163, 164,  84,  84, 165, 166, 167, 168, 169,  84,   2,   2,
      2,   2,   2,   2,   2, 170, 171, 172, 173, 174, 175, 176,  84,  84,  84,  84,
      2,   2,   2,   2,   2, 177,   2,   2,   2,   2,   2,   2,   2,   2, 178,   2,
    179,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 180,  84,  84,
      2,   2,   2,   2, 181,  84,  84,  84,
};

static RE_UINT8 re_grapheme_base_stage_4[] = {
      0,   0,   1,   1,   1,   1,   1,   2,   0,   0,   3,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,   1,   0,   0,   0,   0,   0,   0,   0,   4,
      5,   1,   6,   1,   1,   1,   1,   1,   7,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   8,   1,   9,   8,   1,  10,   0,   0,  11,  12,   1,  13,  14,
     15,  16,   1,   1,  13,   0,   1,   8,   1,   1,   1,   1,   1,  17,  18,   1,
     19,  20,   1,   0,  21,   1,   1,   1,   1,   1,  22,  23,   1,   1,  13,  24,
      1,  25,  26,   2,   1,  27,   0,   0,   0,   0,   1,  28,   0,   0,   0,   0,
     29,   1,   1,  30,  31,  32,  33,   1,  34,  35,  36,  37,  38,  39,  40,  41,
     42,  35,  36,  43,  44,  45,  15,  46,  47,   6,  36,  48,  49,  44,  40,  50,
     51,  35,  36,  52,  53,  39,  40,  54,  55,  56,  57,  58,  59,  44,  15,  13,
     60,  20,  36,  61,  62,  63,  40,  64,  65,  20,  36,  66,  67,  11,  40,  68,
     69,  20,   1,  70,  71,  72,  40,   1,  73,  74,   1,  75,  76,  77,  15,  46,
      8,   1,   1,  78,  79,  41,   0,   0,  80,  81,  82,  83,  84,  85,   0,   0,
      1,   4,   1,  86,  87,   1,  88,  89,  90,   0,   0,  91,  92,  13,   0,   0,
      1,   1,  88,  93,   1,  94,   8,  95,  96,   3,   1,   1,  97,   1,   1,   1,
      1,   1,   1,   1,  98,  99,   1,   1,  98,   1,   1, 100, 101, 102,   1,   1,
      1, 101,   1,   1,   1,  13,   1,  88,   1, 103,   1,   1,   1,   1,   1, 104,
      1,  88,   1,   1,   1,   1,   1, 105,   3, 106,   1, 107,   1, 106,   3,  44,
      1,   1,   1, 108, 109, 110, 103, 103,  13, 103,   1,   1,   1,   1,   1,  54,
    111,   1, 112,   1,   1,   1,   1,  22,   1,   2, 113, 114, 115,   1,  19,  14,
      1,   1,  41,   1, 103, 116,   1,   1,   1, 117,   1,   1,   1, 118, 119, 120,
    103, 103,  19,   0,   0,   0,   0,   0, 121,   1,   1, 122, 123,   1,  13, 110,
    124,   1, 125,   1,   1,   1, 126, 127,   1,   1,  41, 128, 129,   1,   1,   1,
    105,   0,   0,   0,  54, 130, 131, 132,   1,   1,   1,   1,   0,   0,   0,   0,
      1, 104,   1,   1, 104, 133,   1,  19,   1,   1,   1, 134, 134, 135,   1, 136,
     13,   1, 137,   1,   1,   1,   0,  33,   2,  88,   1,   2,   0,   0,   0,   0,
     41,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   2,
      1,   1,  76,   0,  13,   0,   1,   1,   1,   1,   1,   1,   1,   1,   1, 138,
      1, 139,   1, 129,  36, 106, 140,   0,   1,   1,   2,   1,   1,   2,   1,   1,
      1,   1,   1,   1,   1,   1,   2, 141,   1,   1,  97,   1,   1,   1, 137,  44,
      1,  76, 142, 142, 142, 142,   0,   0,   1,   1,   1,   1,  14,   0,   0,   0,
      1, 143,   1,   1,   1,   1,   1, 144,   1,   1,   1,   1,   1,  22,   0,  41,
      1,   1, 103,   1,   8,   1,   1,   1,   1, 145,   1,   1,   1,   1,   1,   1,
    146,   1,  19,   8,   1,   1,   1,   1,   2,   1,   1,  13,   1,   1, 144,   1,
      1,   2,   1,   1,   1,   1,   1,   1,   1,   1,   1,  22,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  22,   0,   0,  88,   1,   1,   1,  76,   1,   1,   1,
      1,   1,  41,   0,   1,   1,   2, 147,   1,  19,   1,   1,   1,   1,   1, 148,
      1,   1,   2,  54,   0,   0,   0, 149, 150,   1, 151, 103,   1,   1,   1,  54,
      1,   1,   1,   1, 152, 103,   0, 153,   1,   1, 154,   1,  76, 155,   1,  88,
     29,   1,   1, 156, 157, 158, 134,   2,   1,   1, 159, 160, 161,  85,   1, 162,
      1,   1,   1, 163, 164, 165, 166,  22, 167, 168, 142,   1,   1,   1,  22,   1,
      1,   1,   1,   1,   1,   1, 169, 103,   1,   1, 144,   1, 145,   1,   1,  41,
      0,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,  19,   1,
      1,   1,   1,   1,   1, 103,   0,   0,  76, 170,   1, 171, 172,   1,   1,   1,
      1,   1,   1,   1, 106,  29,   1,   1,   1,   1,   1,   1,   0,   1,   1,   1,
      1, 124,   1,   1,  54,   0,   0,  19,   0, 103,   0,   1,   1, 173, 174, 134,
      1,   1,   1,   1,   1,   1,   1,  88,   8,   1,   1,   1,   1,   1,   1,   1,
      1,  19,   1,   2, 175, 176, 142, 177, 162,   1, 102, 178,  19,  19,   0,   0,
      1,   1,   1,   1,   1,   1,   1,  13, 179,   1,   1, 180,   1,   1,   1,   1,
      2,  41,  44,   0,   0,   1,   1,  88,   1,  88,   1,   1,   1,  44,   8,  41,
      1,   1, 144,   1,  13,   1,   1,  22,   1, 157,   1,   1, 181,  22,   0,   0,
      1,  19, 103,   1,   1, 181,   1,  41,   1,   1,  54,   1,   1,   1, 182,   0,
      1,   1,   1,  76,   1,  22,  54,   0, 183,   1,   1, 184,   1, 185,   1,   1,
      1,   2, 149,   0,   0,   0,   1, 186,   1, 187,   1,  58,   0,   0,   0,   0,
      1,   1,   1, 188,   1, 124,   1,   1,  44, 189,   1, 144,  54, 105,   1,   1,
      1,   1,   0,   0,   1,   1, 190,  76,   1,   1,   1, 191,   1, 139,   1, 192,
      1, 193, 194,   0,   0,   0,   0,   0,   1,   1,   1,   1, 105,   0,   0,   0,
      1,   1,   1, 120,   1,   1,   1,   7,   0,   0,   0,   0,   0,   0,   1,   2,
     20,   1,   1,  54, 195, 124,   1,   0, 124,   1,   1, 196, 106,   1, 105, 103,
     29,   1, 197,  15, 144,   1,   1, 198, 124,   1,   1, 199,  61,   1,   8,  14,
      1,   6,   2, 200,   0,   0,   0,   0, 201, 157, 103,   1,   1,   2, 120, 103,
     51,  35,  36, 202, 203, 204, 144,   0,   1,   1,   1,  54, 205, 206,   0,   0,
      1,   1,   1, 207, 208, 103,   0,   0,   1,   1,   2, 209,   8,  41,   0,   0,
      1,   1,   1, 210,  62, 103,  88,   0,   1,   1, 211, 212, 103,   0,   0,   0,
      1, 103, 213,   1,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1, 214,
      0,   0,   0,   0,   1,   1,   1, 105,  36,   1,   1,  11,  22,   1,  88,   1,
      1,   0, 215, 216,   0,   0,   0,   0,   1, 103,   0,   0,   0,   0,   0,   0,
      1,   1,   1,   1,   1,   1,   2,  14,   1,   1,   1,   1, 144,   0,   0,   0,
      1,   1,   2,   0,   0,   0,   0,   0,   1,   1,   1,   1,  76,   0,   0,   0,
      1,   1,   1, 105,   1,   2, 158,   0,   0,   0,   0,   0,   0,   1,  19, 217,
      1,   1,   1, 149,  22, 143,   6, 218,   1,   0,   0,   0,   0,   0,   0,   0,
      1,   1,   1,   1,  14,   1,   1,   2,   0,  29,   0,   0,   0,   0,  44,   0,
      1,   1,   1,   1,   1,   1,  88,   0,   1,   1,   1,   1,   1,   1,   1, 120,
    106,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,  13,  88,
    105, 219,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1,   1,   1,   1,  22,
      1,   1,   9,   1,   1,   1, 220,   0, 221,   1, 158,   1,   1,   1, 105,   0,
      1,   1,   1,   1, 222,   0,   0,   0,   1,   1,   1,   1,   1,  76,   1, 106,
      1,   1,   1,   1,   1, 134,   1,   1,   1,   3, 223,  30, 224,   1,   1,   1,
    225, 226,   1, 227, 228,  20,   1,   1,   1,   1, 139,   1,   1,   1,   1,   1,
      1,   1,   1,   1, 166,   1,   1,   1,   0,   0,   0, 229,   0,   0,  21, 134,
    230,   0,   0,   0,   0,   0,   0,   0,   1,   1,   1,   1, 111,   0,   0,   0,
      1,   1,   1,   1, 144, 158,   0,   0, 224,   1, 231, 232, 233, 234, 235, 236,
    143,  41, 237,  41,   0,   0,   0, 106,   1,   1,  41,   1,   1,   1,   1,   1,
      1, 144,   2,   8,   8,   8,   1,  22,  88,   1,   2,   1,   1,   1,  41,   1,
      1,   1,  88,   0,   0,   0,  15,   1, 120,   1,   1,  41, 105, 106,   0,   0,
      1,   1,   1,   1,   1, 120,  88,  76,   1,   1,   1,   1,   1,   1,   1, 144,
      1,   1,   1,   1,   1,  14,   0,   0,  41,   1,   1,   1,  54, 103,   1,   1,
     54,   1,  19,   0,   0,   0,   0,   0,   0,   2,  54, 238,  41,   2,   0,   0,
      1, 106,   0,   0,  44,   0,   0,   0,   1,   1,   1,   1,   1,  76,   0,   0,
      1,   1,   1,  14,   1,   1,   1,   1,   1,  19,   1,   1,   1,   1,   1,   1,
      1,   1, 106,   0,   0,   0,   0,   0,   1,  19,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_grapheme_base_stage_5[] = {
      0,   0, 255, 255, 255, 127, 255, 223, 255, 252, 240, 215, 251, 255,   7, 252,
    254, 255, 127, 254, 255, 230,   0,  64,  73,   0, 255,   7,  31,   0, 192, 255,
      0, 200,  63,  64,  96, 194, 255,  63, 253, 255,   0, 224,  63,   0,   2,   0,
    240,   7,  63,   4,  16,   1, 255,  65, 223,  63, 248, 255, 255, 235,   1, 222,
      1, 255, 243, 255, 237, 159, 249, 255, 255, 253, 197, 163, 129,  89,   0, 176,
    195, 255, 255,  15, 232, 135, 109, 195,   1,   0,   0,  94,  28,   0, 232, 191,
    237, 227,   1,  26,   3,   2, 236, 159, 237,  35, 129,  25, 255,   0, 232, 199,
     61, 214,  24, 199, 255, 131, 198,  29, 238, 223, 255,  35,  30,   0,   0,   7,
      0, 255, 237, 223, 239,  99, 155,  13,   6,   0, 236, 223, 255, 167, 193, 221,
    112, 255, 236, 255, 127, 252, 251,  47, 127,   0,   3, 127,  13, 128, 127, 128,
    150,  37, 240, 254, 174, 236,  13,  32,  95,   0, 255, 243,  95, 253, 255, 254,
    255,  31,   0, 128,  32,  31,   0, 192, 191, 223,   2, 153, 255,  60, 225, 255,
    155, 223, 191,  32, 255,  61, 127,  61,  61, 127,  61, 255, 127, 255, 255,   3,
     63,  63, 255,   1,   3,   0,  99,   0,  79, 192, 191,   1, 240,  31, 159, 255,
    255,   5, 120,  14, 251,   1, 241, 255, 255, 199, 127, 198, 191,   0,  26, 224,
      7,   0, 240, 255,  47, 232, 251,  15, 252, 255, 195, 196, 191,  92,  12, 240,
     48, 248, 255, 227,   8,   0,   2, 222, 111,   0, 255, 170, 223, 255, 207, 239,
    220, 127, 255, 128, 207, 255,  63, 255,   0, 240,  12, 254, 127, 127, 255, 251,
     15,   0, 127, 248, 224, 255,   8, 192, 252,   0, 128, 255, 187, 247, 159,  15,
     15, 192, 252,  63,  63, 192,  12, 128,  55, 236, 255, 191, 255, 195, 255, 129,
     25,   0, 247,  47, 255, 239,  98,  62,   5,   0,   0, 248, 255, 207, 126, 126,
    126,   0, 223,  30, 248, 160, 127,  95, 219, 255, 247, 255, 127,  15, 252, 252,
    252,  28,   0,  48, 255, 183, 135, 255, 143, 255,  15, 255,  15, 128,  63, 253,
    191, 145, 191, 255,  55, 248, 255, 143, 255, 240, 239, 254,  31, 248,  63, 254,
      7, 255,   3,  30,   0, 254, 128,  63, 135, 217, 127,  16, 119,   0,  63, 128,
     44,  63, 127, 189, 237, 163, 158,  57,   1, 224, 163, 255, 255,  43,   6,  90,
    242,   0,   3,  79,   7,  88, 255, 215,  64,   0,  67,   0,   7, 128,   0,   2,
     18,   0,  32,   0, 255, 224, 255, 147,  95,  60,  24, 240,  35,   0, 100, 222,
    239, 255, 191, 231, 223, 223, 255, 123,  95, 252, 128,   7, 239,  15, 150, 254,
    247,  10, 132, 234, 150, 170, 150, 247, 247,  94, 238, 251, 249, 127,
};

/* Grapheme_Base: 2616 bytes. */

RE_UINT32 re_get_grapheme_base(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_grapheme_base_stage_1[f] << 5;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_grapheme_base_stage_2[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_grapheme_base_stage_3[pos + f] << 3;
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
     0,  0,  8,  0,  9, 10,  0, 11,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_grapheme_link_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  2,  3,  0,  0,  4,  5,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  6,  7,  0,  0,  0,  0,  8,  0,  9, 10,
     0,  0, 11,  0,  0,  0,  0,  0, 12,  9, 13, 14,  0, 15,  0, 16,
     0,  0,  0,  0, 17,  0,  0,  0, 18, 19, 20, 14, 21, 22,  1,  0,
    23, 23,  0, 17, 17, 24, 25,  0, 17,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_grapheme_link_stage_4[] = {
     0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  2,  0,  0,  3,  0,  0,
     4,  0,  0,  0,  0,  5,  0,  0,  6,  6,  0,  0,  0,  0,  7,  0,
     0,  0,  0,  8,  0,  0,  4,  0,  0,  9,  0, 10,  0,  0,  0, 11,
    12,  0,  0,  0,  0,  0, 13,  0,  0,  0,  8,  0,  0,  0,  0, 14,
     0,  0,  0,  1,  0, 11,  0,  0,  0,  0, 12, 11,  0, 15,  0,  0,
     0, 16,  0,  0,  0, 17,  0,  0,  0,  0,  0,  2,  0,  0, 18,  0,
     0, 14,  0,  0,  0, 19,  0,  0,
};

static RE_UINT8 re_grapheme_link_stage_5[] = {
      0,   0,   0,   0,   0,  32,   0,   0,   0,   4,   0,   0,   0,   0,   0,   4,
     16,   0,   0,   0,   0,   0,   0,   6,   0,   0,  16,   0,   0,   0,   4,   0,
      1,   0,   0,   0,   0,  12,   0,   0,   0,   0,  12,   0,   0,   0,   0, 128,
     64,   0,   0,   0,   0,   0,   8,   0,   0,   0,  64,   0,   0,   0,   0,   2,
      0,   0,  24,   0,   0,   0,  32,   0,   4,   0,   0,   0,   0,   8,   0,   0,
};

/* Grapheme_Link: 412 bytes. */

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
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4,
};

static RE_UINT8 re_terminal_punctuation_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9,  9, 10, 11,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9, 12, 13,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 14,
    15,  9, 16,  9, 17, 18,  9, 19,  9, 20,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 21,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9, 22,
     9,  9,  9,  9,  9,  9, 23,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
     9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,  9,
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
    40,  1, 41,  1, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51,  1,  1,
    52,  1,  1, 53, 54,  1, 55,  1, 56,  1,  1,  1,  1,  1,  1,  1,
    57,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 58, 59, 60,  1,
     1, 41,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 61,  1,  1,
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
     0,  0, 48,  0,  0,  0, 49,  0,  0, 50,  0,  0,  0,  4,  0,  0,
     0,  0, 51,  0,  0,  0, 52,  0,  0,  0, 29,  0,  0, 53,  0,  0,
     0,  0, 48, 54,  0,  0,  0, 55,  0,  0,  0, 33,  0,  0,  0, 56,
     0, 57, 58,  0, 59,  0,  0,  0,
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
     14,   0,   0,   0,  96,  32,   0, 192,   0,   0,   0,  31,   0,  56,   0,   8,
     60, 254, 255,   0,   0,   0,   0, 112,   0,   0,   2,   0,   0,   0,  31,   0,
      0,   0,  32,   0,   0,   0, 128,   3,  16,   0,   0,   0, 128,   7,   0,   0,
};

/* Terminal_Punctuation: 874 bytes. */

RE_UINT32 re_get_terminal_punctuation(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_terminal_punctuation_stage_1[f] << 5;
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
     0,  1,  2,  3,  3,  3,  3,  3,  3,  3,  4,  3,  3,  3,  3,  5,
     6,  7,  3,  3,  3,  3,  8,  3,  3,  3,  3,  9,  3,  3, 10, 11,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
};

static RE_UINT8 re_other_alphabetic_stage_3[] = {
     0,  0,  0,  1,  0,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12,
    13,  0,  0, 14,  0,  0,  0, 15, 16, 17, 18, 19, 20, 21,  0,  0,
     0,  0,  0,  0, 22,  0,  0,  0,  0,  0,  0,  0,  0, 23,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 24,  0, 25, 26, 27, 28,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 29,  0,  0,  0,  0,
     0,  0,  0, 30,  0,  0,  0,  0,  0,  0, 31,  0,  0,  0,  0,  0,
    32, 33, 34, 35, 36, 37, 38, 39,  0,  0,  0,  0, 40,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 41,  0,  0,  0, 42,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 43,  0,  0,  0,
    44,  0,  0,  0,  0,  0,  0,  0,  0, 45,  0,  0,  0,  0,  0,  0,
     0, 46,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_other_alphabetic_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  2,  3,  0,  4,  0,  5,  6,  0,  0,  7,  8,
     9, 10,  0,  0,  0, 11,  0,  0, 12, 13,  0,  0,  0,  0, 14, 15,
    16, 17, 18, 19, 20, 21, 22, 19, 20, 21, 23, 24, 20, 21, 25, 19,
    20, 21, 26, 19, 27, 21, 28,  0, 16, 21, 29, 19, 20, 21, 29, 19,
    20, 21, 30, 19, 19,  0, 31, 32,  0, 33, 34,  0,  0, 35, 34,  0,
     0,  0,  0, 36, 37, 38,  0,  0,  0, 39, 40, 41, 42,  0,  0,  0,
     0,  0, 43,  0,  0,  0,  0,  0, 32, 32, 32, 32,  0, 44, 45,  0,
     0,  0,  0,  0, 46, 47,  0,  0,  0, 48,  0,  0,  0,  0,  0,  0,
    49,  0, 50, 51,  0,  0,  0,  0, 52, 53, 16,  0, 54, 55,  0, 56,
     0, 57,  0,  0,  0,  0,  0, 32,  0,  0,  0,  0,  0,  0,  0, 58,
     0,  0,  0,  0,  0, 44, 59, 60,  0,  0,  0,  0,  0,  0,  0, 59,
     0,  0,  0, 61, 21,  0,  0,  0,  0, 62,  0,  0, 63, 14, 64,  0,
     0, 65, 66,  0, 16, 14,  0,  0,  0, 67, 68,  0,  0, 69,  0, 70,
     0,  0,  0,  0,  0,  0,  0, 71, 72,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0, 73,  0,  0,  0,  0, 74,  0,  0,  0,  0,  0,  0,  0,
    54, 75, 76,  0, 27, 77,  0,  0, 54, 66,  0,  0, 54, 78,  0,  0,
     0, 79,  0,  0,  0,  0, 43, 45, 16, 21, 22, 19,  0,  0,  0,  0,
     0, 53, 80,  0,  0, 10, 63,  0,  0,  0,  0,  0,  0, 81, 82,  0,
     0, 83, 84,  0,  0, 85,  0,  0, 86, 87,  0,  0,  0,  0,  0,  0,
     0, 88,  0,  0, 89, 90,  0,  0,  0, 91,  0,  0,  0,  0,  0,  0,
     0,  0, 36, 92,  0,  0,  0,  0,  0,  0,  0,  0, 72,  0,  0,  0,
    93, 94,  0,  0,  0,  0,  0,  0,  0,  0, 95,  0,  0,  0,  0,  0,
     0, 10, 96, 96, 60,  0,  0,  0,
};

static RE_UINT8 re_other_alphabetic_stage_5[] = {
      0,   0,   0,   0,  32,   0,   0,   0,   0,   0, 255, 191, 182,   0,   0,   0,
      0,   0, 255,   7,   0, 248, 255, 254,   0,   0,   1,   0,   0,   0, 192,  31,
    158,  33,   0,   0,   0,   0,   2,   0,   0,   0, 255, 255, 192, 255,   1,   0,
      0,   0, 192, 248, 239,  30,   0,   0,   0,   0, 240, 255, 248,   3, 255, 255,
     15,   0,   0,   0,   0,   0,   0, 204, 255, 223, 224,   0,  12,   0,   0,   0,
     14,   0,   0,   0,   0,   0,   0, 192, 159,  25, 128,   0, 135,  25,   2,   0,
      0,   0,  35,   0, 191,  27,   0,   0, 159,  25, 192,   0,   4,   0,   0,   0,
    199,  29, 128,   0, 223,  29,  96,   0, 223,  29, 128,   0,   0, 128,  95, 255,
      0,   0,  12,   0,   0,   0, 242,   7,   0,  32,   0,   0,   0,   0, 242,  27,
      0,   0, 254, 255,   3, 224, 255, 254, 255, 255, 255,  31,   0, 248, 127, 121,
      0,   0, 192, 195, 133,   1,  30,   0, 124,   0,   0,  48,   0,   0,   0, 128,
      0,   0, 192, 255, 255,   1,   0,   0,  96,   0,   0,   0,   0,   2,   0,   0,
    255,  15, 255,   1,   0,   0, 128,  15,   0,   0, 224, 127, 254, 255,  31,   0,
     31,   0,   0,   0,   0,   0, 224, 255,   7,   0,   0,   0, 254,  51,   0,   0,
    128, 255,   3,   0, 240, 255,  63,   0, 128, 255,  31,   0, 255, 255, 255, 255,
    255,   3,   0,   0,   0,   0, 240,  15, 248,   0,   0,   0,   3,   0,   0,   0,
     47,   0,   0,   0, 192,   7,   0,   0, 128, 255,   7,   0,   0, 254, 127,   0,
      8,  48,   0,   0,   0,   0, 157,  65,   0, 248,  32,   0, 248,   7,   0,   0,
      0,   0,   0,  64,   0,   0, 192,   7, 110, 240,   0,   0,   0,   0,   0, 255,
     63,   0,   0,   0,   0,   0, 255,   1,   0,   0, 248, 255,   0, 240, 159,  64,
     59,   0,   0,   0,   0, 128,  63, 127,   0,   0,   0,  48,   0,   0, 255, 127,
      1,   0,   0,   0,   0, 248,  63,   0,   0,   0,   0, 224, 255,   7,   0,   0,
      0, 128, 127, 127,   0,   0, 252, 255, 255, 254, 127,   0,   0,   0, 127,   0,
    255, 255, 255, 127, 127, 255, 255, 249, 219,   7,   0,   0, 128,   0,   0,   0,
    255,   3, 255, 255,
};

/* Other_Alphabetic: 1021 bytes. */

RE_UINT32 re_get_other_alphabetic(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_alphabetic_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_other_alphabetic_stage_2[pos + f] << 4;
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
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3,
};

static RE_UINT8 re_ideographic_stage_2[] = {
     0,  0,  0,  1,  2,  3,  3,  3,  3,  4,  0,  0,  0,  0,  0,  5,
     0,  0,  0,  0,  0,  0,  0,  3,  6,  0,  0,  0,  0,  0,  0,  0,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  7,  8,  9,  0,  0, 10,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_ideographic_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  3,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  4,  0,  0,  0,  0,  5,  6,  0,  0,
     2,  2,  2,  7,  2,  8,  0,  0,  2,  2,  2,  9,  2,  2,  2,  2,
     2,  2,  2, 10, 11,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2, 12,
     0,  0,  0,  0,  2, 13,  0,  0,
};

static RE_UINT8 re_ideographic_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,  0,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  3,  0,
     2,  2,  2,  2,  2,  2,  2,  4,  0,  0,  0,  0,  2,  2,  2,  2,
     2,  5,  2,  6,  0,  0,  0,  0,  2,  2,  2,  2,  2,  2,  2,  7,
     2,  2,  2,  8,  0,  0,  0,  0,  2,  2,  2,  9,  2,  2,  2,  2,
     2,  2,  2,  2, 10,  2,  2,  2, 11,  2,  2,  2,  2,  2,  2,  2,
     2,  2, 12,  0,  0,  0,  0,  0, 13,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_ideographic_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0, 192,   0,   0,   0, 254,   3,   0,   7,
    255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255, 255,  63,   0,
    255, 255,  63,   0,   0,   0,   0,   0, 255, 255, 255, 255, 255,  63, 255, 255,
    255, 255, 255,   3,   0,   0,   0,   0, 255, 255, 255, 255, 255,  31,   0,   0,
    255, 255, 255, 255, 255, 255,   7,   0, 255, 255, 127,   0,   0,   0,   0,   0,
    255, 255, 255, 255, 255, 255,  31,   0, 255, 255, 255,  63, 255, 255, 255, 255,
    255, 255, 255, 255,   3,   0,   0,   0, 255, 255, 255,  63,   0,   0,   0,   0,
};

/* Ideographic: 393 bytes. */

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
    10, 11, 12, 13,  4,  4,  4,  4,  4,  4,  4,  4,  4, 14,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4, 15,  4,  4, 16,  4,  4,
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
    38, 39, 40, 41, 42, 43, 44, 45,  1,  1,  1,  1, 46,  1,  1,  1,
     1,  1, 47,  1,  1,  1,  1, 48,  1, 49,  1,  1,  1,  1,  1,  1,
    50, 51,  1,  1,  1,  1,  1,  1,
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
     0,  0,  0,  0,  0, 75,  0,  0,  0, 76,  0, 63,  0,  0, 77,  0,
     0, 78,  0,  0,  0,  0,  0, 79,  0, 22, 25, 80,  0,  0,  0,  0,
     0,  0, 81,  0,  0,  0, 82,  0,  0,  0,  0,  0,  0, 15,  2,  0,
     0, 15,  0,  0,  0, 42,  0,  0,  0, 83,  0,  0,  0,  0,  0,  0,
     0, 15,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 84,
     0,  0,  0,  0, 85,  0,  0,  0,  0,  0,  0, 86, 87, 88,  0,  0,
     0,  0,  0,  0,  0,  0, 89,  0,  0,  0, 90,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_diacritic_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,  64,   1,   0,   0,   0,   0, 129, 144,   1,
      0,   0, 255, 255, 255, 255, 255, 255, 255, 127, 255, 224,   7,   0,  48,   4,
     48,   0,   0,   0, 248,   0,   0,   0,   0,   0,   0,   2,   0,   0, 254, 255,
    251, 255, 255, 191,  22,   0,   0,   0,   0, 248, 135,   1,   0,   0,   0, 128,
     97,  28,   0,   0, 255,   7,   0,   0, 192, 255,   1,   0,   0, 248,  63,   0,
      0,   0,   0,   3, 248, 255, 255, 127,   0,   0,   0,  16,   0,  32,  30,   0,
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
      0,   0,   0, 248,   0,  48,   0,   0, 255, 255,   0,   0,   0,   0,   1,   0,
      0,   0,   0, 192,   8,   0,   0,   0,  96,   0,   0,   0,   0,   0,   0,   6,
      0,   0,  24,   0,   1,  28,   0,   0,   0,   0,  96,   0,   0,   6,   0,   0,
    192,  31,  31,   0,  68,   0,   0,   0,  12,   0,   0,   0,   0,   8,   0,   0,
      0,   0,  31,   0,   0, 128, 255, 255, 128, 227,   7, 248, 231,  15,   0,   0,
      0,  60,   0,   0,   0,   0, 127,   0, 112,   7,   0,   0,
};

/* Diacritic: 1029 bytes. */

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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_extender_stage_2[] = {
     0,  1,  2,  3,  2,  2,  4,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  5,  6,  2,  2,  2,  2,  2,  2,  2,  2,  2,  7,
     2,  2,  8,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  9,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2, 10,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
     2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,  2,
};

static RE_UINT8 re_extender_stage_3[] = {
     0,  1,  2,  1,  1,  1,  3,  4,  1,  1,  1,  1,  1,  1,  5,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  6,  1,  7,  1,  8,  1,  1,  1,
     9,  1,  1,  1,  1,  1,  1,  1, 10,  1,  1,  1,  1,  1, 11,  1,
     1, 12, 13,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 14,
     1,  1,  1, 15,  1, 16,  1,  1,  1,  1,  1, 17,  1,  1,  1, 18,
     1, 19,  1,  1,  1,  1,  1,  1,
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
     0,  0,  0,  0,  0,  0,  0,  3,  0,  0, 23,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_extender_stage_5[] = {
      0,   0,   0,   0,   0,   0, 128,   0,   0,   0,   3,   0,   1,   0,   0,   0,
      0,   0,   0,   4,  64,   0,   0,   0,   0,   4,   0,   0,   8,   0,   0,   0,
    128,   0,   0,   0,   0,   0,  64,   0,   0,   0,   0,   8,  32,   0,   0,   0,
      0,   0,  62,   0,   0,   0,   0,  96,   0,   0,   0, 112,   0,   0,  32,   0,
      0,  16,   0,   0,   0, 128,   0,   0,   0,   0,   1,   0,   0,   0,   0,  32,
      0,   0,  24,   0, 192,   1,   0,   0,  12,   0,   0,   0, 112,   0,   0,   0,
};

/* Extender: 457 bytes. */

RE_UINT32 re_get_extender(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_extender_stage_1[f] << 5;
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
    0, 1, 1, 2, 3, 1, 1, 4, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1,
};

static RE_UINT8 re_other_grapheme_extend_stage_2[] = {
    0, 1, 0, 0, 2, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 5, 0, 0, 0, 0, 0,
    0, 0, 6, 0, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_grapheme_extend_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  2,  3,  4,  0,  0,
     5,  0,  0,  0,  0,  0,  0,  0,  6,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  7,  0,  0,  0,  8,  9, 10,  0,  0,
     0, 11,  0,  0,  0,  0,  0,  0, 12,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_other_grapheme_extend_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  0,
     0,  1,  2,  0,  0,  1,  2,  0,  0,  0,  0,  0,  0,  0,  3,  0,
     0,  1,  2,  0,  0,  0,  4,  0,  5,  0,  0,  0,  0,  0,  0,  0,
     0,  6,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  7,  0,  0,  0,
     0,  1,  2,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  8,  0,  0,
     0,  0,  0,  0,  0,  9,  0,  0,  0,  0,  0, 10,  0,  0,  0,  0,
     0, 11, 11, 11,  0,  0,  0,  0,
};

static RE_UINT8 re_other_grapheme_extend_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,  64,   0,   0, 128,   0,   4,   0,  96,   0,
      0, 128,   0, 128,   0,  16,   0,   0,   0, 192,   0,   0,   0,   0,   0, 192,
      0,   0,   1,  32,   0, 128,   0,   0,  32, 192,   7,   0, 255, 255, 255, 255,
};

/* Other_Grapheme_Extend: 332 bytes. */

RE_UINT32 re_get_other_grapheme_extend(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 14;
    code = ch ^ (f << 14);
    pos = (RE_UINT32)re_other_grapheme_extend_stage_1[f] << 3;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_other_grapheme_extend_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_other_grapheme_extend_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_other_grapheme_extend_stage_4[pos + f] << 5;
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
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 6, 7, 8, 0, 0, 0,
};

static RE_UINT8 re_unified_ideograph_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 3, 0, 0, 0, 0, 0, 4, 0, 0,
    1, 1, 1, 5, 1, 1, 1, 1, 1, 1, 1, 6, 7, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 8,
};

static RE_UINT8 re_unified_ideograph_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2, 0, 1, 1, 1, 1, 1, 1, 1, 3,
    4, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 5, 1, 1, 1, 1,
    1, 1, 1, 1, 6, 1, 1, 1, 7, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 8, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_unified_ideograph_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0, 255, 255, 255, 255, 255, 255, 255, 255,
    255, 255, 255, 255, 255, 255,  63,   0, 255, 255,  63,   0,   0,   0,   0,   0,
      0, 192,  26, 128, 154,   3,   0,   0, 255, 255, 127,   0,   0,   0,   0,   0,
    255, 255, 255, 255, 255, 255,  31,   0, 255, 255, 255,  63, 255, 255, 255, 255,
    255, 255, 255, 255,   3,   0,   0,   0,
};

/* Unified_Ideograph: 281 bytes. */

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
    0, 6, 0, 0, 0, 0, 0, 0, 7, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_deprecated_stage_5[] = {
      0,   0,   0,   0,   0,   2,   0,   0,   0,   0,   8,   0,   0,   0, 128,   2,
     24,   0,   0,   0,   0, 252,   0,   0,   0,   6,   0,   0,   2,   0,   0,   0,
};

/* Deprecated: 226 bytes. */

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
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 3, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
};

static RE_UINT8 re_logical_order_exception_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 2, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0,
};

static RE_UINT8 re_logical_order_exception_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 3, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_logical_order_exception_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,  31,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 224,   4,   0,   0,   0,   0,   0,   0,  96,  26,
};

/* Logical_Order_Exception: 145 bytes. */

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
    0, 1, 2, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_id_start_stage_3[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0,
    2, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_id_start_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_other_id_start_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0, 96,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  1,  0, 64,  0,  0,  0,  0,  0, 24,  0,  0,  0,  0,
};

/* Other_ID_Start: 145 bytes. */

RE_UINT32 re_get_other_id_start(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_other_id_start_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_other_id_start_stage_2[pos + f] << 3;
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

/* Sentence_Terminal. */

static RE_UINT8 re_sentence_terminal_stage_1[] = {
    0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4,
};

static RE_UINT8 re_sentence_terminal_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  3,  3,  9, 10,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3, 11, 12,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3, 13,
     3,  3, 14,  3, 15, 16,  3, 17,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3, 18,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3, 19,
     3,  3,  3,  3,  3,  3, 20,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
     3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,  3,
};

static RE_UINT8 re_sentence_terminal_stage_3[] = {
     0,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  2,  3,  4,  5,  6,
     1,  1,  7,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     8,  1,  1,  1,  1,  1,  9,  1,  1,  1,  1,  1, 10,  1, 11,  1,
    12,  1, 13,  1,  1, 14, 15,  1, 16,  1,  1,  1,  1,  1,  1,  1,
    17,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 18,  1,  1,  1,
    19,  1,  1,  1,  1,  1,  1,  1,  1, 20,  1,  1, 21, 22,  1,  1,
    23, 24, 25, 26, 27, 28,  1, 29,  1,  1,  1,  1, 30,  1, 31,  1,
     1,  1,  1,  1, 32,  1,  1,  1, 33, 34, 35, 36, 37, 38,  1,  1,
    39,  1,  1, 40, 41,  1, 42,  1, 41,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1, 43, 44, 45,  1,  1,  3,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 46,  1,  1,
};

static RE_UINT8 re_sentence_terminal_stage_4[] = {
     0,  1,  0,  0,  0,  0,  0,  0,  2,  0,  0,  0,  3,  0,  0,  0,
     0,  0,  4,  0,  5,  0,  0,  0,  0,  0,  0,  6,  0,  0,  0,  7,
     0,  0,  8,  0,  0,  0,  0,  9,  0,  0,  0, 10,  0, 11,  0,  0,
    12,  0,  0,  0,  0,  0,  7,  0,  0, 13,  0,  0,  0,  0, 14,  0,
     0, 15,  0, 16,  0, 17, 18,  0,  0, 19,  0,  0, 20,  0,  0,  0,
     0,  0,  0,  3, 21,  0,  0,  0,  0,  0,  0, 22,  0,  0,  0, 23,
     0,  0, 21,  0,  0, 24,  0,  0,  0,  0, 25,  0,  0,  0, 26,  0,
     0,  0,  0, 27,  0,  0,  0, 28,  0,  0, 29,  0,  1,  0,  0, 30,
     0,  0, 23,  0,  0,  0, 31,  0,  0, 16, 32,  0,  0,  0, 33,  0,
     0,  0, 34,  0,  0, 35,  0,  0,  0,  2,  0,  0,  0,  0, 36,  0,
     0,  0, 37,  0,  0,  0, 38,  0,  0, 39,  0,  0,  0,  0,  0, 21,
     0,  0,  0, 40,  0, 41, 42,  0, 43,  0,  0,  0,
};

static RE_UINT8 re_sentence_terminal_stage_5[] = {
      0,   0,   0,   0,   2,  64,   0, 128,   0,   2,   0,   0,   0,   0,   0, 128,
      0,   0,  16,   0,   7,   0,   0,   0,   0,   0,   0,   2,  48,   0,   0,   0,
      0,  12,   0,   0, 132,   1,   0,   0,   0,  64,   0,   0,   0,   0,  96,   0,
      8,   2,   0,   0,   0,  15,   0,   0,   0,   0,   0, 204,   0,   0,   0,  24,
      0,   0,   0, 192,   0,   0,   0,  48, 128,   3,   0,   0,   0,  64,   0,  16,
      4,   0,   0,   0,   0, 192,   0,   0,   0,   0, 136,   0,   0,   0, 192,   0,
      0, 128,   0,   0,   0,   3,   0,   0,   0,   0,   0, 224,   0,   0,   3,   0,
      0,   8,   0,   0,   0,   0, 196,   0,   2,   0,   0,   0, 128,   1,   0,   0,
      3,   0,   0,   0,  14,   0,   0,   0,  96,  32,   0, 192,   0,   0,   0,  27,
      0,  24,   0,   0,  12, 254, 255,   0,   6,   0,   0,   0,   0,   0,   0, 112,
      0,   0,  32,   0,   0,   0, 128,   1,  16,   0,   0,   0,   0,   1,   0,   0,
};

/* Sentence_Terminal: 726 bytes. */

RE_UINT32 re_get_sentence_terminal(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_sentence_terminal_stage_1[f] << 5;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_sentence_terminal_stage_2[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_sentence_terminal_stage_3[pos + f] << 2;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_sentence_terminal_stage_4[pos + f] << 5;
    pos += code;
    value = (re_sentence_terminal_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

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

/* Prepended_Concatenation_Mark. */

static RE_UINT8 re_prepended_concatenation_mark_stage_1[] = {
    0, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1,
};

static RE_UINT8 re_prepended_concatenation_mark_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 2, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_prepended_concatenation_mark_stage_3[] = {
    0, 0, 0, 1, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    3, 0, 0, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_prepended_concatenation_mark_stage_4[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 2, 3, 0, 0, 0,
    0, 0, 0, 4, 0, 0, 0, 0, 0, 0, 5, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_prepended_concatenation_mark_stage_5[] = {
      0,   0,   0,   0,   0,   0,   0,   0,  63,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,  32,   0,   0,   0,   0,   0, 128,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   4,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  32,
};

/* Prepended_Concatenation_Mark: 162 bytes. */

RE_UINT32 re_get_prepended_concatenation_mark(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_prepended_concatenation_mark_stage_1[f] << 3;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_prepended_concatenation_mark_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_prepended_concatenation_mark_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_prepended_concatenation_mark_stage_4[pos + f] << 6;
    pos += code;
    value = (re_prepended_concatenation_mark_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

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
    105, 106, 107, 108, 109, 110, 111,   2, 112, 113,   2, 114, 115, 116, 117,   2,
      2,   2,   2,   2,   2,   2,   2,   2, 118, 119,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2, 120, 121,   2,   2,   2,   2,   2,   2,   2,   2, 122,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2, 123,   2,   2,   2,   2,   2,   2,
      2,   2, 124, 125, 126,   2, 127,   2,   2,   2,   2,   2,   2, 128, 129, 130,
      2,   2,   2,   2, 131, 132,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
    133,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
     99, 134, 135,  99,  99,  99,  99,  99,  99,  99,  99,  99,  88, 136,  99,  99,
    137, 138, 139,   2,   2,   2,  53,  53,  53,  53,  53,  53,  53, 140, 141, 142,
    143, 144, 145, 146,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 147,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2, 147,
    148, 148, 149, 150, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148,
    148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148,
};

static RE_UINT8 re_bidi_class_stage_3[] = {
      0,   1,   2,   3,   4,   5,   4,   6,   7,   8,   9,  10,  11,  12,  11,  12,
     11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11,  13,  14,  14,  15,  16,
     17,  17,  17,  17,  17,  17,  17,  18,  19,  11,  11,  11,  11,  11,  11,  20,
     21,  11,  11,  11,  11,  11,  11,  11,  22,  23,  17,  24,  25,  26,  26,  26,
     27,  28,  29,  29,  30,  17,  31,  32,  29,  29,  29,  29,  29,  33,  34,  35,
     29,  36,  29,  17,  28,  29,  29,  29,  29,  29,  37,  32,  26,  26,  38,  39,
     26,  40,  41,  26,  26,  42,  26,  26,  26,  26,  29,  29,  29,  43,  44,  17,
     45,  11,  11,  46,  47,  48,  49,  11,  50,  11,  11,  51,  52,  11,  49,  53,
     54,  11,  11,  51,  55,  50,  11,  56,  54,  11,  11,  51,  57,  11,  49,  58,
     50,  11,  11,  59,  52,  60,  49,  11,  61,  11,  11,  11,  62,  11,  11,  63,
     64,  11,  11,  65,  66,  67,  49,  68,  50,  11,  11,  51,  69,  11,  49,  11,
     50,  11,  11,  11,  52,  11,  49,  11,  11,  11,  11,  11,  70,  71,  11,  11,
     11,  11,  11,  72,  73,  11,  11,  11,  11,  11,  11,  74,  75,  11,  11,  11,
     11,  76,  11,  77,  11,  11,  11,  78,  79,  80,  17,  81,  60,  11,  11,  11,
     11,  11,  82,  83,  11,  84,  64,  85,  86,  87,  11,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  82,  11,  11,  11,  88,  11,  11,  11,  11,  11,  11,
      4,  11,  11,  11,  11,  11,  11,  11,  89,  90,  11,  11,  11,  11,  11,  11,
     11,  91,  11,  91,  11,  49,  11,  49,  11,  11,  11,  92,  93,  94,  11,  88,
     95,  11,  11,  11,  11,  11,  11,  11,  67,  11,  96,  11,  11,  11,  11,  11,
     11,  11,  97,  98,  99,  11,  11,  11,  11,  11,  11,  11,  11, 100,  16,  16,
     11, 101,  11,  11,  11, 102, 103, 104,  11,  11,  11, 105,  11,  11,  11,  11,
    106,  11,  11, 107,  61,  11, 108, 106, 109,  11, 110,  11,  11,  11, 111, 109,
     11,  11, 112, 113,  11,  11,  11,  11,  11,  11,  11,  11,  11, 114, 115, 116,
     11,  11,  11,  11,  17,  17,  17, 117,  11,  11,  11, 118, 119, 120, 120, 121,
    122,  16, 123, 124, 125, 126, 127, 128, 129,  11, 130, 130, 130,  17,  17,  64,
    131, 132, 133, 134, 135,  16,  11,  11, 136,  16,  16,  16,  16,  16,  16,  16,
     16, 137,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,
     16,  16,  16, 138,  11,  11,  11,   5,  16, 139,  16,  16,  16,  16,  16, 140,
     16,  16, 141,  11, 142,  11,  16,  16, 143, 144,  11,  11,  11,  11, 145,  16,
     16,  16, 146,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16,  16, 147,
     16, 148,  16, 149, 150, 151, 152,  11,  11,  11,  11,  11,  11,  11, 153, 154,
     11,  11,  11,  11,  11,  11,  11, 155,  11,  11,  11,  11,  11,  11,  17,  17,
     16,  16,  16,  16, 156,  11,  11,  11,  16, 157,  16,  16,  16,  16,  16, 158,
     16,  16,  16,  16,  16, 138,  11, 159, 160,  16, 161, 162,  11,  11,  11,  11,
     11, 163,   4,  11,  11,  11,  11, 164,  11,  11,  11,  11,  16,  16, 158,  11,
     11, 121,  11,  11,  11,  16,  11, 165,  11,  11,  11, 166, 152,  11,  11,  11,
     11,  11,  11,  11,  11,  11,  11, 167,  11,  11,  11,  11,  11, 100,  11, 168,
     11,  11,  11,  11,  16,  16,  16,  16,  11,  16,  16,  16, 141,  11,  11,  11,
    120,  11,  11,  11,  11,  11, 155, 169,  11,  65,  11,  11,  11,  11,  11, 109,
     16,  16, 151,  11,  11,  11,  11,  11, 170,  11,  11,  11,  11,  11,  11,  11,
    171,  11, 172, 173,  11,  11,  11, 174,  11,  11,  11,  11, 175,  11,  17, 109,
     11,  11, 176,  11, 177, 109,  11,  11,  45,  11,  11, 178,  11,  11, 179,  11,
     11,  11, 180, 181, 182,  11,  11,  51,  11,  11,  11, 183,  50,  11,  69,  60,
     11,  11,  11,  11,  11,  11, 184,  11,  11, 185, 186,  26,  26,  29,  29,  29,
     29,  29,  29,  29,  29,  29,  29,  29,  29,  29,  29, 187,  29,  29,  29,  29,
     29,  29,  29,  29,  29,   8,   8, 188,  17,  88,  17,  16,  16, 189, 190,  29,
     29,  29,  29,  29,  29,  29,  29, 191, 192,   3,   4,   5,   4,   5, 138,  11,
     11,  11,  11,  11,  11,  11, 193, 194, 195,  11,  11,  11,  16,  16,  16,  16,
    196, 159,   4,  11,  11,  11,  11,  87,  11,  11,  11,  11,  11,  11, 197, 144,
     11,  11,  11,  11,  11,  11,  11, 198,  26,  26,  26,  26,  26,  26,  26,  26,
     26, 199,  26,  26,  26,  26,  26,  26, 200,  26,  26, 201,  26,  26,  26,  26,
     26,  26,  26,  26,  26,  26, 202,  26,  26,  26,  26, 203,  26,  26,  26,  26,
     26,  26,  26,  26,  26,  26, 204, 205,  50,  11,  11, 206, 207,  14, 138, 155,
    109,  11,  11, 208,  11,  11,  11,  11,  45,  11, 209, 210,  11,  11,  11, 211,
    109,  11,  11, 212, 213,  11,  11,  11,  11,  11, 155, 214,  11,  11,  11,  11,
     11,  11,  11,  11,  11, 155, 215,  11, 109,  11,  11,  51,  64,  11, 216, 210,
     11,  11,  11, 206,  71,  11,  11,  11,  11,  11,  11, 217, 218,  11,  11,  11,
     11,  11,  11, 219,  64,  69,  11,  11,  11,  11,  11, 220,  64,  11, 196,  11,
     11,  11, 221, 222,  11,  11,  11,  11,  11,  82, 223,  11,  11,  11,  11,  11,
     11,  11,  11, 224,  11,  11,  11,  11,  11, 225, 226, 227,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  11,  11, 210,  11,  11,  11, 207,  11,  11,  11,  11,
    155,  45,  11,  11,  11,  11,  11,  11,  11, 228, 229,  11,  11,  11,  11,  11,
     11,  11,  11,  11,  11,  11, 230, 231, 232,  11, 233,  11,  11,  11,  11,  11,
     16,  16,  16,  16, 234,  11,  11,  11,  16,  16,  16,  16,  16, 141,  11,  11,
     11,  11,  11,  11,  11, 164,  11,  11,  11, 235,  11,  11, 168,  11,  11,  11,
    236,  11,  11,  11, 237, 238, 238, 238,  17,  17,  17, 239,  17,  17,  81, 179,
    240, 108, 241,  11,  11,  11,  11,  11, 242, 243, 244,  11,  11,  11,  11,  11,
     26,  26,  26,  26,  26, 245,  26,  26,  26,  26,  26,  26, 246,  26,  26,  26,
     29,  29,  29,  29,  29,  29,  29, 247,  16,  16, 159,  16,  16,  16,  16,  16,
     16, 158, 140, 166, 166, 166,  16, 138, 248,  11,  11,  11,  11,  11, 134,  11,
     16,  16,  16,  16,  16, 249, 196, 141,  16,  16,  16,  16,  16,  16,  16, 158,
     16,  16,  16,  16,  16, 156,  11,  11, 159,  16,  16,  16, 250,  88,  16,  16,
    250,  16, 251,  11,  11,  11,  11,  11,  11, 140, 250, 252, 159, 140,  11,  11,
     16, 151,  11,  11,   4,  11,  11,  11,  11,  11,  11,  11,  11,  11,  11, 253,
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
     57,  25,  25,  25,  58,  12,  12,  12,  12,  12,  59,  60,  61,  25,  60,  62,
     61,  25,  12,  12,  63,  12,  12,  12,  62,  12,  12,  12,  12,  12,  12,  60,
     61,  60,  12,  62,  64,  12,  65,  12,  66,  12,  12,  12,  66,  28,  67,  29,
     29,  62,  12,  12,  61,  68,  60,  62,  69,  12,  12,  12,  12,  12,  12,  67,
     12,  59,  12,  12,  59,  12,  12,  12,  60,  12,  12,  62,  13,  10,  70,  12,
     60,  12,  12,  12,  12,  12,  12,  63,  60,  63,  71,  29,  12,  66,  12,  12,
     12,  12,  10,  72,  12,  12,  12,  29,  12,  12,  59,  12,  63,  73,  12,  12,
     62,  25,  58,  65,  12,  28,  25,  58,  62,  25,  68,  60,  12,  12,  25,  29,
     12,  12,  29,  12,  12,  74,  75,  26,  61,  25,  25,  58,  25,  71,  12,  61,
     25,  25,  61,  25,  25,  25,  25,  60,  12,  12,  12,  61,  71,  25,  66,  66,
     12,  12,  29,  63,  61,  60,  12,  12,  59,  66,  12,  62,  12,  12,  12,  62,
     10,  10,  26,  12,  76,  12,  12,  12,  12,  12,  13,  11,  63,  60,  12,  12,
     12,  68,  25,  29,  12,  59,  61,  25,  25,  12,  65,  62,  10,  10,  77,  78,
     12,  12,  62,  12,  58,  28,  60,  12,  59,  12,  61,  12,  11,  26,  12,  12,
     12,  12,  12,  23,  12,  28,  67,  12,  12,  59,  25,  58,  73,  61,  25,  60,
     28,  25,  25,  67,  25,  25,  25,  58,  25,  12,  12,  12,  12,  71,  58,  60,
     12,  12,  28,  25,  29,  12,  12,  12,  63,  29,  68,  29,  12,  59,  29,  74,
     12,  12,  12,  25,  25,  63,  12,  12,  58,  25,  25,  25,  71,  25,  60,  62,
     12,  60,  29,  12,  25,  29,  28,  25,  12,  12,  12,  79,  26,  12,  12,  24,
     12,  12,  12,  24,  12,  12,  12,  22,  80,  80,  81,  82,  10,  10,  83,  84,
     85,  86,  10,  10,  10,  87,  10,  10,  10,  10,  10,  88,   0,  89,  90,   0,
     91,   8,  92,  72,   8,   8,  92,  72,  85,  85,  85,  85,  17,  72,  26,  12,
     12,  20,  11,  23,  10,  79,  93,  94,  12,  12,  23,  12,  10,  11,  23,  26,
     12,  12,  24,  12,  95,  10,  10,  10,  10,  26,  12,  12,  10,  20,  10,  10,
     10,  10,  10,  72,  10,  72,  12,  12,  10,  10,  72,  12,  10,  10,   8,   8,
      8,   8,   8,  12,  12,  12,  23,  10,  10,  10,  10,  24,  10,  23,  10,  10,
     10,  26,  10,  10,  10,  10,  26,  24,  10,  10,  20,  10,  26,  12,  12,  12,
     12,  12,  12,  10,  12,  24,  72,  28,  29,  12,  24,  10,  12,  12,  12,  28,
     10,  11,  12,  12,  10,  10,  17,  10,  10,  12,  12,  12,  10,  10,  10,  12,
     96,  11,  10,  10,  11,  12,  63,  29,  11,  23,  12,  24,  12,  12,  97,  11,
     12,  12,  13,  12,  12,  12,  12,  72,  24,  10,  10,  10,  12,  13,  72,  12,
     12,  12,  12,  13,  98,  25,  25,  99,  12,  12,  11,  12,  59,  59,  28,  12,
     12,  66,  10,  12,  12,  12, 100,  12,  12,  10,  12,  12,  12,  29,  12,  12,
     12,  63,  25,  29,  12,  28,  25,  25,  28,  63,  29,  60,  12,  62,  12,  12,
     12,  12,  61,  58,  66,  66,  12,  12,  28,  12,  12,  60,  71,  67,  60,  63,
     12,  62,  60,  62,  12,  12,  12, 101,  34,  34, 102,  34,  40,  40,  40, 103,
     40,  40,  40, 104, 105, 106,  10, 107, 108,  72, 109,  12,  40,  40,  40, 110,
     30,   5,   6,   7,   5, 111,  10,  72,   0,   0, 112, 113,  93,  12,  12,  12,
     10,  10,  10,  11, 114,   8,   8,   8,  12,  63,  58,  12,  34,  34,  34, 115,
     31,  33,  34,  25,  34,  34, 116,  52,  34,  33,  34,  34,  34,  34, 117,  10,
     35,  35,  35,  35,  35,  35,  35, 118,  12,  12,  25,  25,  25,  58,  12,  12,
     28,  58,  66,  12,  12,  28,  25,  61,  25,  60,  12,  12,  28,  12,  12,  12,
     12,  63,  25,  58,  12,  12,  63,  60,  29,  71,  12,  59,  28,  25,  58,  12,
     12,  63,  25,  60,  28,  25,  73,  28,  71,  12,  12,  12,  63,  29,  12,  68,
     28,  25,  58,  74,  12,  12,  28,  62,  25,  68,  12,  12,  63,  68,  25,  12,
     25,  58,  25,  29,  63,  25,  25,  25,  25,  25,  63,  25,  71,  66,  12,  12,
     12,  12,  12,  66,   0,  12,  12,  12,  12,  28,  29,  12, 119,   0, 120,  25,
     58,  61,  25,  12,  12,  12,  63,  29, 121, 122,  12,  12,  12,  93,  12,  12,
     12,  12,  93,  12,  13,  12,  12, 123,   8,   8,   8,   8,  25,  58,  28,  25,
     12,  60,  12,  12,  61,  25,  25,  25,  25,  58,  25,  25,  25,  25,  67,  25,
     68,  71,  58,  12,  25, 116,  34,  34,  34,  25, 116,  34, 124,  40,  40,  40,
      8,   8, 125,  11,  72,  12,  12,  12,  10,  10,  12,  12,  10,  10,  10,  26,
    126,  10,  10,  72,  12,  12,  12, 127,
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
    12, 12,  1,  1, 12, 12,  5, 12, 12, 12, 12,  0,  0,  0, 12,  0,
    12,  0,  0,  0,  0, 12, 12, 12,  0, 12,  0,  0,  0,  0, 12, 12,
     0,  0,  4,  4,  0,  0,  0,  4,  0, 12, 12,  0, 12,  0,  0, 12,
    12, 12,  0, 12,  0,  4,  0,  0, 10,  4, 10,  0, 12,  0, 12, 12,
    10, 10, 10,  0, 12,  0, 12,  0,  0, 12,  0, 12,  0, 12, 10, 10,
     9,  0,  0,  0, 10, 10, 10, 12, 12, 12, 11,  0,  0, 10,  0, 10,
     9,  9,  9,  9,  9,  9,  9, 11, 11, 11,  0,  1,  9,  7, 16, 17,
    18, 14, 15,  6,  4,  4,  4,  4,  4, 10, 10, 10,  6, 10, 10, 10,
    10, 10, 10,  9, 11, 11, 19, 20, 21, 22, 11, 11,  2,  0,  0,  0,
     2,  2,  3,  3,  0, 10,  0,  0,  0,  0,  4,  0, 10, 10,  3,  4,
     9, 10, 10, 10,  0, 12, 12, 10, 12, 12, 12, 10, 12, 12, 10, 10,
     4,  4,  0,  0,  0,  1, 12,  1,  1,  3,  1,  1, 13, 13, 10, 10,
    13, 10, 13, 13,  6, 10,  6,  0, 10,  6, 10, 10, 10, 10, 10,  4,
    10, 10,  3,  3, 10,  4,  4, 10, 13, 13, 13, 11, 10,  4,  4,  0,
    11, 10, 10, 10, 10, 10, 11, 11, 12,  2,  2,  2,  1,  1,  1, 10,
    12, 12, 12,  1,  1, 10, 10, 10,  5,  5,  5,  1,  0,  0,  0, 11,
    11, 11, 11, 12, 10, 10, 12, 12, 12, 10,  0,  0,  0,  0,  2,  2,
    10, 10, 13, 13,  2,  2,  2, 10, 10,  0,  0, 10,  0,  0, 11, 11,
};

/* Bidi_Class: 3552 bytes. */

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
    22, 23,  0,  0,  0, 24,  0,  0, 25, 26, 27, 28,  0,  0, 29,  0,
     0,  0,  0,  0,  0, 30,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 31,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 32, 33,  0,  0,  0,  0,  0,  0,
    34,  0,  0,  0, 35,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_canonical_combining_class_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   4,   0,   0,   0,   0,
      0,   0,   0,   0,   5,   0,   0,   0,   0,   0,   0,   0,   6,   7,   8,   0,
      9,   0,  10,  11,   0,   0,  12,  13,  14,  15,  16,   0,   0,   0,   0,  17,
     18,  19,  20,   0,   0,   0,  21,  22,   0,  23,  24,   0,   0,  23,  25,   0,
      0,  23,  25,   0,   0,  23,  25,   0,   0,  23,  25,   0,   0,   0,  25,   0,
      0,   0,  26,   0,   0,  23,  25,   0,   0,   0,  25,   0,   0,   0,  27,   0,
      0,  28,  29,   0,   0,  30,  31,   0,  32,  33,   0,  34,  35,   0,  36,   0,
      0,  37,   0,   0,  38,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  39,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  40,  40,   0,   0,   0,   0,  41,   0,
      0,   0,   0,   0,   0,  42,   0,   0,   0,  43,   0,   0,   0,   0,   0,   0,
     44,   0,   0,  45,   0,  46,   0,   0,   0,  47,  48,  49,   0,  50,   0,  51,
      0,  52,   0,   0,   0,   0,  53,  54,   0,   0,   0,   0,   0,   0,  55,  56,
      0,   0,   0,   0,   0,   0,  57,  58,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  59,   0,   0,   0,  60,   0,   0,   0,  61,
      0,  62,   0,   0,  63,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,  64,  65,   0,   0,  66,   0,   0,   0,   0,   0,   0,   0,   0,
     67,   0,   0,   0,   0,   0,  48,  68,   0,  69,  70,   0,   0,  71,  72,   0,
      0,   0,   0,   0,   0,  73,  74,  75,   0,   0,   0,   0,   0,   0,   0,  25,
      0,   0,   0,   0,   0,   0,   0,   0,  76,   0,   0,   0,   0,   0,   0,   0,
      0,  77,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  78,
      0,   0,   0,   0,   0,   0,   0,  79,   0,   0,   0,  80,   0,   0,   0,   0,
     81,  82,   0,   0,   0,   0,   0,  83,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  67,  60,   0,  84,   0,   0,  85,  86,   0,  71,   0,   0,  87,   0,
      0,  88,   0,   0,   0,   0,   0,  89,   0,  23,  25,  90,   0,   0,   0,   0,
      0,   0,  91,   0,   0,   0,  92,   0,   0,   0,   0,   0,   0,  60,  93,   0,
      0,  60,   0,   0,   0,  94,   0,   0,   0,  95,   0,   0,   0,   0,   0,   0,
      0,  60,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  96,   0,  97,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  98,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  99, 100, 101,   0,   0,
      0,   0, 102,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    103, 104,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 105,   0,   0,   0, 106,   0,   0,   0,   0,   0,
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
      0,   0,   0,   0,   0,   0,  50,   0,   0,   0,   0,   0,   0,   1,   1,   1,
     51,  21,  43,  52,  53,  21,  35,   1,   0,   0,   0,   0,   0,   0,   0,  54,
      0,   0,   0,  55,  56,  57,   0,   0,   0,   0,   0,  55,   0,   0,   0,   0,
      0,   0,   0,  55,   0,  58,   0,   0,   0,   0,  59,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  60,   0,   0,   0,  61,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  62,   0,   0,   0,  63,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  64,   0,   0,   0,   0,   0,   0,  65,  66,   0,
      0,   0,   0,   0,  67,  68,  69,  70,  71,  72,   0,   0,   0,   0,   0,   0,
      0,  73,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  74,  75,   0,
      0,   0,   0,  76,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  48,
      0,   0,   0,   0,   0,  77,   0,   0,   0,   0,   0,   0,  59,   0,   0,  78,
      0,   0,  79,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  80,   0,
      0,   0,   0,   0,   0,  19,  81,   0,  77,   0,   0,   0,   0,  48,   1,  82,
      0,   0,   0,   0,   1,  52,  15,  41,   0,   0,   0,   0,   0,  54,   0,   0,
      0,  77,   0,   0,   0,   0,   0,   0,   0,   0,  19,  10,   1,   0,   0,   0,
      0,   0,  83,   0,   0,   0,   0,   0,   0,  84,   0,   0,  83,   0,   0,   0,
      0,   0,   0,   0,   0,  74,   0,   0,   0,   0,   0,   0,  85,   9,  12,   4,
     86,   8,  87,  76,   0,  57,  49,   0,  21,   1,  21,  88,  89,   1,   1,   1,
      1,   1,   1,   1,   1,  49,  19,  90,   0,   0,   0,   0,  91,   1,  92,  57,
     78,  93,  94,   4,  57,   0,   0,   0,   0,   0,   0,  19,  49,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  95,   1,   1,   1,   1,   1,   1,   1,   1,
      0,   0,  96,  97,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  98,   0,
      0,   0,   0,  19,   0,   1,   1,  49,   0,   0,   0,   0,   0,   0,   0,  38,
      0,   0,   0,   0,  49,   0,   0,   0,   0,  59,   0,   0,   0,   0,   0,   0,
      1,   1,   1,   1,  49,   0,   0,   0,   0,   0,  99,  64,   0,   0,   0,   0,
      0,   0,   0,   0,  95,   0,   0,   0,   0,   0,   0,   0,  74,   0,   0,   0,
     77,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 100, 101,  57,  38,
     78,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  59,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 102,   1,  14,   4,  12,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  76,  81,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  38,  85,   0,   0,   0,   0, 103,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 104,  95,   0, 105,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 106,   0,  85,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  95,  77,   0,   0,  77,   0,  84,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 106,   0,   0,   0,   0, 107,   0,   0,   0,   0,   0,
      0,  38,   1,  57,   1,  57,   0,   0,  59,  84,   0,   0,   0,   0,   0,   0,
    108,   0,   0,   0,   0,   0,   0,   0,  54,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 108,   0,   0,   0,   0,  95,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   8,  87,   0,   0,   0,   0,   0,   0,   1,  85,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 109,   0, 110, 111, 112, 113,   0,  99,   4,
    114,  48,  23,   0,   0,   0,   0,   0,   0,   0,  38,  49,   0,   0,   0,   0,
     38,  57,   0,   0,   0,   0,   0,   0,   1,  85,   1,   1,   1,   1,  39,   1,
     47, 100,  85,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4, 114,   0,   0,
      0,   1, 115,   0,   0,   0,   0,   0,
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
     0, 50, 50, 50, 50, 50,  0,  0,  0, 45, 45, 45, 50, 50,  0, 45,
    50, 45, 45, 45, 22, 23, 24, 50,  2,  0,  0,  0,  0,  4,  0,  0,
     0, 50, 45, 50, 50,  0,  0,  0,  0, 32, 33,  0,  0,  0,  4,  0,
    34, 34,  4,  0, 35, 35, 35, 35, 36, 36,  0,  0, 37, 37, 37, 37,
    45, 45,  0,  0,  0, 45,  0, 45,  0, 43,  0,  0,  0, 38, 39,  0,
    40,  0,  0,  0,  0,  0, 39, 39, 39, 39,  0,  0, 39,  0, 50, 50,
     4,  0, 50, 50,  0,  0, 45,  0,  0,  0,  0,  2,  0,  4,  4,  0,
     0, 45,  0,  0,  4,  0,  0,  0,  0, 50,  0,  0,  0, 49,  0,  0,
     0, 46, 50, 45, 45,  0,  0,  0, 50,  0,  0, 45,  0,  0,  4,  4,
     0,  0,  2,  0, 50, 50, 50,  0, 50,  0,  1,  1,  1,  0,  0,  0,
    50, 53, 42, 45, 41, 50, 50, 50, 52, 45, 50, 45, 50, 50,  1,  1,
     1,  1,  1, 50,  0,  1,  1, 50, 45, 50,  1,  1,  0,  0,  0,  4,
     0,  0, 44, 49, 51, 46, 47, 47,  0,  3,  3,  0,  0,  0,  0, 45,
    50,  0, 50, 50, 45,  0,  0, 50,  0,  0, 21,  0,  0, 45,  0, 50,
    50,  1, 45,  0,  0, 50, 45,  0,  0,  4,  2,  0,  0,  2,  4,  0,
     0,  0,  4,  2,  0,  0,  1,  0,  0, 43, 43,  1,  1,  1,  0,  0,
     0, 48, 43, 43, 43, 43, 43,  0, 45, 45, 45,  0, 50, 50,  2,  0,
};

/* Canonical_Combining_Class: 2192 bytes. */

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
    147,   0,   0,   0, 148,   0,   0,   0,  81,  81,  81,   0,  20,  20,  35,   0,
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
    10, 10, 10, 10, 10, 10, 11,  5, 12, 10, 10, 13, 10, 10, 10, 14,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 15,
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
    16, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
     8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8, 17,
     8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8,  8, 17,
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
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 30,
    22, 22, 22, 22, 22, 22, 22, 31, 22, 22, 32,  5,  5,  5,  5,  5,
    33,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
    34, 35, 36, 37, 38, 39, 40,  5,  5, 41,  5,  5,  5,  5,  5,  5,
    22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 22, 42,
     5, 43,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,
    27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 27, 44,
};

static RE_UINT8 re_east_asian_width_stage_3[] = {
      0,   0,   1,   1,   1,   1,   1,   2,   0,   0,   3,   4,   5,   6,   7,   8,
      9,  10,  11,  12,  13,  14,  11,   0,   0,   0,   0,   0,  15,  16,   0,   0,
      0,   0,   0,   0,   0,   9,   9,   0,   0,   0,   0,   0,  17,  18,   0,   0,
     19,  19,  19,  19,  19,  19,  19,   0,   0,  20,  21,  20,  21,   0,   0,   0,
      9,  19,  19,  19,  19,   9,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     22,  22,  22,  22,  22,  22,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,  23,  24,  25,   0,   0,   0,  26,  27,   0,  28,   0,   0,   0,   0,   0,
     29,  30,  31,   0,   0,  32,  33,  34,  35,  34,   0,  36,   0,  37,  38,   0,
     39,  40,  41,  42,  43,  44,  45,   0,  46,  47,  48,  49,   0,   0,   0,   0,
      0,  50,  51,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  52,  53,
      0,   0,   0,   0,   0,   0,  19,  19,  19,  19,  19,  19,  19,  19,  54,  19,
     19,  19,  19,  19,  33,  19,  19,  55,  19,  56,  21,  57,  58,  59,  60,  61,
     62,  63,   0,   0,  64,  65,  66,  67,   0,  68,  69,  70,  71,  72,  73,  74,
     75,   0,  76,  77,  78,  79,   0,  80,   0,  81,   0,  82,   0,   0,  83,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  84,   0,   0,   0,   0,   0,   0,   0,
      0,  85,   0,   0,   0,  86,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  22,  87,  22,  22,  22,  22,  22,  65,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  88,   0,  89,
     90,  22,  22,  91,  92,  22,  22,  22,  22,  93,  22,  22,  22,  22,  22,  22,
     94,  22,  95,  92,  22,  22,  22,  22,  91,  22,  22,  96,  22,  22,  65,  22,
     22,  91,  22,  22,  97,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  91,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,   0,   0,   0,   0,
     22,  22,  22,  22,  22,  22,  22,  22,  98,  22,  22,  22,  99,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  22,  98,   0,   0,   0,   0,   0,   0,   0,   0,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  65,   0,   0,   0,   0,   0,
     19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,
     19, 100,   0,  22,  22, 101, 102,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    103, 104, 104, 104, 104, 104, 105, 106, 106, 106, 106, 107, 108, 109, 110,  77,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 111,   0,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  98,   0,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22, 112,
    113,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    114,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  67,   0,   0,   0,
    115,  19, 116,  19,  19,  19,  34,  19, 117, 118, 119,   0,   0,   0,   0,   0,
    112,  22,  22,  89, 120, 113,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     22,  22, 121, 122,  22,  22,  22, 123,  22,  65,  22,  22, 124,  65,  22, 125,
     22,  22,  22,  91, 126,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22, 127,
     22,  22,  22,  95, 128,  22, 129, 130,   0, 131, 114,   0,   0,   0,   0, 132,
     22,  22,  22,  22,  22,   0,   0,   0,  22,  22,  22,  22, 133, 112,  85, 134,
      0,  91, 129, 135,  89,  91,   0,   0,  22, 113,   0,   0, 111,   0,   0,   0,
     22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  22,  95,
     19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,   0,
     19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19,  19, 116,
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
     0, 15,  0,  0,  0,  0,  0, 12, 10,  0, 23,  0,  0,  0, 24,  0,
     0,  0, 25, 26, 27,  0,  0,  0,  7,  7, 19,  7,  7,  0,  0,  0,
    13, 14,  0,  0, 13, 13,  0, 14, 14, 13, 18, 13, 14,  0,  0,  0,
    13, 14,  0, 12,  0,  0,  0, 24,  0, 22, 15, 13,  0, 28,  0,  5,
     5,  0, 20, 20, 20,  0,  0,  0, 19, 19,  9, 19,  0,  0,  0, 29,
    29,  0,  0, 13, 30,  0, 23,  0,  0,  0,  0, 31,  0, 32,  7, 33,
     7, 34,  7,  7, 19,  0, 33,  7, 35, 36, 33, 36,  0, 30, 23,  0,
     0,  0, 26,  0,  0,  0,  0, 15,  0,  0,  0, 37, 29, 38,  0,  0,
     0, 13,  7,  7,  0, 25,  0,  0, 26,  0,  0, 29,  0, 39,  1, 40,
     0, 41,  0,  0,  0,  0, 29, 26, 26, 42, 14,  0, 20, 20, 38, 20,
    20, 28,  0,  0, 20, 20, 20,  0, 43, 20, 20, 20, 20, 20, 20, 44,
    25, 20, 20, 20, 20, 44, 25, 20,  0, 25, 20, 20, 20, 20, 20, 28,
    20, 20, 44,  0, 20, 20,  7,  7, 20, 20, 20, 26, 20, 44,  0,  0,
    20, 20, 28,  0, 44, 20, 20, 20, 20, 44, 20,  0, 45, 46, 46, 46,
    46, 46, 46, 46, 47, 48, 48, 48, 48, 48, 48, 48, 48, 48, 48, 49,
    50, 48, 50, 48, 50, 48, 50, 51, 46, 52, 48, 49, 26,  0,  0,  0,
    44,  0,  0,  0, 28,  0,  0,  0,  0, 26,  0,  0,  7,  7,  9,  0,
     7,  7,  7, 14,  7,  7,  7, 33, 53, 20, 54,  7,  7,  7,  7, 11,
    20, 20, 26,  0, 26,  0,  0, 25, 20, 38, 20, 20, 20, 20, 20, 55,
    20, 20, 44, 29, 26, 26, 20, 20, 55, 20, 20, 20, 20, 20, 20, 27,
     0,  0, 29, 44, 20, 20,  0,  0,  0,  0, 56,  0,  0, 24,  0,  0,
     0,  0, 29, 20, 20, 28,  0, 26,  0, 44,  0,  0, 27, 20, 20, 44,
};

static RE_UINT8 re_east_asian_width_stage_5[] = {
    0, 0, 0, 0, 5, 5, 5, 5, 5, 5, 5, 0, 0, 1, 5, 5,
    1, 5, 5, 1, 1, 0, 1, 0, 5, 1, 1, 5, 1, 1, 1, 1,
    1, 0, 1, 1, 1, 1, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0,
    0, 0, 0, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0,
    0, 1, 0, 1, 0, 1, 1, 1, 1, 0, 0, 1, 1, 1, 0, 1,
    3, 3, 3, 3, 0, 2, 0, 0, 0, 1, 1, 0, 0, 0, 3, 3,
    0, 3, 3, 0, 0, 3, 3, 3, 3, 0, 0, 0, 3, 0, 0, 3,
    3, 3, 0, 0, 0, 0, 0, 3, 0, 3, 0, 0, 0, 3, 3, 1,
    3, 3, 1, 1, 1, 1, 3, 1, 3, 1, 1, 1, 1, 1, 3, 3,
    1, 3, 1, 1, 3, 0, 3, 0, 3, 3, 0, 3, 0, 0, 5, 5,
    5, 5, 0, 0, 0, 5, 5, 0, 0, 3, 1, 1, 4, 3, 3, 3,
    3, 3, 3, 0, 0, 4, 4, 4, 4, 4, 4, 4, 4, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 0, 0, 0, 2, 2, 2, 0, 0, 0,
    4, 4, 4, 0, 1, 3, 3, 3, 3, 3, 3, 1, 3, 0, 3, 3,
    0, 0, 3, 0,
};

/* East_Asian_Width: 2052 bytes. */

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
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    2, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_joining_group_stage_3[] = {
    0, 0, 0, 0, 0, 0, 1, 2, 3, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 0, 0,
};

static RE_UINT8 re_joining_group_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  1,  2,  3,  0,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13,
     0, 14, 15,  0, 16, 17, 18, 19,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 20, 21,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 22, 23, 24,  0,
};

static RE_UINT8 re_joining_group_stage_5[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    45,  0,  3,  3, 43,  3, 45,  3,  4, 41,  4,  4, 13, 13, 13,  6,
     6, 31, 31, 35, 35, 33, 33, 39, 39,  1,  1, 11, 11, 55, 55, 55,
     0,  9, 29, 19, 22, 24, 26, 16, 43, 45, 45,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  4, 29,
     0,  3,  3,  3,  0,  3, 43, 43, 45,  4,  4,  4,  4,  4,  4,  4,
     4, 13, 13, 13, 13, 13, 13, 13,  6,  6,  6,  6,  6,  6,  6,  6,
     6, 31, 31, 31, 31, 31, 31, 31, 31, 31, 35, 35, 35, 33, 33, 39,
     1,  9,  9,  9,  9,  9,  9, 29, 29, 11, 38, 11, 19, 19, 19, 11,
    11, 11, 11, 11, 11, 22, 22, 22, 22, 26, 26, 26, 26, 56, 21, 13,
    41, 17, 17, 14, 43, 43, 43, 43, 43, 43, 43, 43, 55, 47, 55, 43,
    45, 45, 46, 46,  0, 41,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  6, 31,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 35, 33,  1,  0,  0, 21,
     2,  0,  5, 12, 12,  7,  7, 15, 44, 50, 18, 42, 42, 48, 49, 20,
    23, 25, 27, 36, 10,  8, 28, 32, 34, 30,  7, 37, 40,  5, 12,  7,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 51, 52, 53,
     4,  4,  4,  4,  4,  4,  4, 13, 13,  6,  6, 31, 35,  1,  1,  1,
     9,  9, 11, 11, 11, 24, 24, 26, 26, 26, 22, 31, 31, 35, 13, 13,
    35, 31, 13,  3,  3, 55, 55, 45, 43, 43, 54, 54, 13, 35, 35, 19,
     4,  4, 13, 39,  9, 29, 22, 24, 45, 45, 31, 43, 57,  0,  6, 33,
    11, 58, 31,  1, 19,  0,  4,  4,  4, 31, 45, 86, 87, 88,  0,  0,
    59, 61, 61, 65, 65, 62,  0, 83,  0, 85, 85,  0,  0, 66, 80, 84,
    68, 68, 68, 69, 63, 81, 70, 71, 77, 60, 60, 73, 73, 76, 74, 74,
    74, 75,  0,  0, 78,  0,  0,  0,  0,  0,  0, 72, 64, 79, 82, 67,
};

/* Joining_Group: 586 bytes. */

RE_UINT32 re_get_joining_group(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 15;
    code = ch ^ (f << 15);
    pos = (RE_UINT32)re_joining_group_stage_1[f] << 3;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_joining_group_stage_2[pos + f] << 4;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_joining_group_stage_3[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_joining_group_stage_4[pos + f] << 4;
    value = re_joining_group_stage_5[pos + code];

    return value;
}

/* Joining_Type. */

static RE_UINT8 re_joining_type_stage_1[] = {
     0,  1,  2,  3,  4,  4,  4,  4,  4,  4,  5,  4,  4,  4,  4,  6,
     7,  8,  4,  4,  4,  4,  9,  4,  4,  4,  4, 10,  4, 11, 12,  4,
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
    13,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
};

static RE_UINT8 re_joining_type_stage_2[] = {
     0,  1,  0,  0,  0,  0,  2,  0,  0,  3,  0,  4,  5,  6,  7,  8,
     9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24,
    25, 26,  0,  0,  0,  0, 27,  0,  0,  0,  0,  0,  0,  0, 28, 29,
    30, 31, 32,  0, 33, 34, 35, 36, 37, 38,  0, 39,  0,  0,  0,  0,
    40, 41,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0, 42, 43, 44,  0,  0,  0,  0,
    45, 46,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 47, 48,  0,  0,
    49, 50, 51, 52, 53, 54,  0, 55,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 56,  0,  0,  0,  0,  0, 57, 43,  0, 58,
     0,  0,  0, 59,  0, 60, 61,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 62, 63,  0, 64,  0,  0,  0,  0,  0,  0,  0,  0,
    65, 66, 67, 68, 69, 70, 71,  0, 72, 73,  0, 74, 75, 76, 77,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 78, 79,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 80, 81,  0,  0,  0,  0,  0,  0,  0,  0, 82,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0, 83,  0,  0,  0,  0,  0,  0,
     0,  0, 84, 85, 86,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 87, 88,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    89,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0, 90, 91,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    92,  0, 93,  2,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
};

static RE_UINT8 re_joining_type_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   0,   0,   0,   0,   0,
      2,   2,   2,   2,   2,   2,   2,   0,   3,   0,   0,   0,   0,   0,   0,   0,
      0,   4,   2,   5,   6,   0,   0,   0,   0,   7,   8,   9,  10,   2,  11,  12,
     13,  14,  15,  15,  16,  17,  18,  19,  20,  21,  22,   2,  23,  24,  25,  26,
      0,   0,  27,  28,  29,  15,  30,  31,   0,  32,  33,   0,  34,  35,   0,   0,
      0,   0,  36,  37,   0,  38,  39,   2,  40,   0,   0,  41,  42,  43,  44,   0,
     45,   0,   0,  46,  47,   0,  44,   0,  48,   0,   0,  46,  49,  45,   0,  50,
     48,   0,   0,  46,  51,   0,  44,   0,  45,   0,   0,  52,  47,  53,  44,   0,
     54,   0,   0,   0,  55,   0,   0,   0,  28,   0,   0,  56,  57,  58,  44,   0,
     45,   0,   0,  52,  59,   0,  44,   0,  45,   0,   0,   0,  47,   0,  44,   0,
      0,   0,   0,   0,  60,  61,   0,   0,   0,   0,   0,  62,  63,   0,   0,   0,
      0,   0,   0,  64,  65,   0,   0,   0,   0,  66,   0,  67,   0,   0,   0,  68,
     69,  70,   2,  71,  53,   0,   0,   0,   0,   0,  72,  73,   0,  74,  28,  75,
     76,   1,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  72,   0,   0,
      0,  77,   0,  77,   0,  44,   0,  44,   0,   0,   0,  78,  79,  80,   0,   0,
     81,   0,  15,  15,  15,  15,  15,  82,  83,  15,  84,   0,   0,   0,   0,   0,
      0,   0,  85,  86,   0,   0,   0,   0,   0,  87,   0,   0,   0,  88,  89,  90,
      0,   0,   0,  91,   0,   0,   0,   0,  92,   0,   0,  93,  54,   0,  94,  92,
     95,   0,  96,   0,   0,   0,  97,  95,   0,   0,  98,  99,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 100, 101, 102,   0,   0,   0,   0,   2,   2,   2, 103,
    104,   0, 105,   0,   0,   0, 106,   0,   0,   0,   0,   0,   0,   2,   2,  28,
      0,   0,   0,   0,   0,   0,  20,  95,   0,   0,   0,   0,   0,   0,   0,  20,
      0,   0,   0,   0,   0,   0,   2,   2,   0,   0, 107,   0,   0,   0,   0,   0,
      0, 108,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  20, 109,
      0,  56,   0,   0,   0,   0,   0,  95, 110,   0,  58,   0,  15,  15,  15, 111,
      0,   0,   0,   0, 112,   0,   2,  95,   0,   0, 113,   0, 114,  95,   0,   0,
     40,   0,   0, 115,   0,   0, 116,   0,   0,   0, 117, 118, 119,   0,   0,  46,
      0,   0,   0, 120,  45,   0, 121,  53,   0,   0,   0,   0,   0,   0, 122,   0,
      0, 123,   0,   0,   0,   0,   0,   0,   2,   0,   2,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 124,   0,   0,   0,   0,   0,   0,   0,   1,
      0,   0,   0,   0,   0,   0,  28,   0,   0,   0,   0,   0,   0,   0,   0, 125,
    126,   0,   0, 127,   0,   0,   0,   0,   0,   0,   0,   0, 128, 129, 130,   0,
    131, 132, 133,   0,   0,   0,   0,   0,  45,   0,   0, 134, 135,   0,   0,  20,
     95,   0,   0, 136,   0,   0,   0,   0,  40,   0, 137, 138,   0,   0,   0, 139,
     95,   0,   0, 140, 141,   0,   0,   0,   0,   0,  20, 142,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  20, 143,   0,  95,   0,   0,  46,  28,   0, 144, 138,
      0,   0,   0, 134,  61,   0,   0,   0,   0,   0,   0, 145, 146,   0,   0,   0,
      0,   0,   0, 147,  28, 121,   0,   0,   0,   0,   0, 148,  28,   0,   0,   0,
      0,   0, 149, 150,   0,   0,   0,   0,   0,  72, 151,   0,   0,   0,   0,   0,
      0,   0,   0, 152,   0,   0,   0,   0,   0, 153, 154, 155,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 138,   0,   0,   0, 135,   0,   0,   0,   0,
     20,  40,   0,   0,   0,   0,   0,   0,   0, 156,  92,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 157, 158, 159,   0, 107,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  77,   0,   0,   0,   2,   2,   2, 160,   2,   2,  71, 116,
    161,  94,   4,   0,   0,   0,   0,   0, 162, 163, 164,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 135,   0,   0,  15,  15,  15,  15, 165,   0,   0,   0,
     45,   0,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,
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
     0, 37,  6,  2,  2,  5,  5,  4, 36, 25, 12, 15, 15, 40,  5,  0,
    15, 15, 25, 41, 42, 43, 12, 44,  0,  2,  2,  2,  6,  2,  2,  2,
     8,  0,  0,  0,  0,  0, 45,  9,  5,  2,  9,  1,  5,  2,  0,  0,
    37,  0,  0,  0,  1,  0,  0,  0,  0,  0,  0,  9,  5,  9,  0,  1,
     7,  0,  0,  0,  7,  3, 27,  4,  4,  1,  0,  0,  5,  6,  9,  1,
     0,  0,  0, 27,  0, 45,  0,  0, 45,  0,  0,  0,  9,  0,  0,  1,
     0,  0,  0, 37,  9, 37, 28,  4,  0,  7,  0,  0,  0, 45,  0,  4,
     0,  0, 45,  0, 37, 46,  0,  0,  1,  2,  8,  0,  0,  3,  2,  8,
     1,  2,  6,  9,  0,  0,  2,  4,  0,  0,  4,  0,  0, 47,  1,  0,
     5,  2,  2,  8,  2, 28,  0,  5,  2,  2,  5,  2,  2,  2,  2,  9,
     0,  0,  0,  5, 28,  2,  7,  7,  0,  0,  4, 37,  5,  9,  0,  0,
    45,  7,  0,  1, 37,  9,  0,  0,  0,  6,  2,  4,  0, 45,  5,  2,
     2,  0,  0,  1,  0, 48, 49,  4, 15, 15,  0,  0,  0, 50, 15, 15,
    15, 15, 51,  0,  8,  3,  9,  0, 45,  0,  5,  0,  0,  3, 27,  0,
     0, 45,  2,  8, 46,  5,  2,  9,  3,  2,  2, 27,  2,  2,  2,  8,
     2,  0,  0,  0,  0, 28,  8,  9,  0,  0,  3,  2,  4,  0,  0,  0,
    37,  4,  6,  4,  0, 45,  4, 47,  0,  0,  0,  2,  2, 37,  0,  0,
     8,  2,  2,  2, 28,  2,  9,  1,  0,  9,  4,  0,  2,  4,  3,  2,
     0,  0,  3, 52,  0,  0, 37,  8,  2,  9, 37,  2,  0,  0, 37,  4,
     0,  0,  7,  0,  8,  2,  2,  4, 45, 45,  3,  0, 53,  0,  0,  0,
     0,  4,  0,  0,  0, 37,  2,  4,  0,  3,  2,  2,  3, 37,  4,  9,
     0,  1,  0,  0,  0,  0,  5,  8,  7,  7,  0,  0,  3,  0,  0,  9,
    28, 27,  9, 37,  0,  0,  0,  4,  0,  1,  9,  1,  0,  0,  0, 45,
     0,  0,  5,  0,  0, 37,  8,  0,  5,  7,  0,  2,  0,  0,  8,  3,
    15, 54, 55, 56, 14, 57, 15, 12, 58, 59, 48, 13, 24, 22, 12, 60,
    58,  0,  0,  0,  0,  0, 20, 61,  0,  0,  2,  2,  2,  8,  0,  0,
     3,  8,  7,  1,  0,  3,  2,  5,  2,  9,  0,  0,  3,  0,  0,  0,
     0, 37,  2,  8,  0,  0, 37,  9,  4, 28,  0, 45,  3,  2,  8,  0,
     0, 37,  2,  9,  3,  2, 46,  3, 28,  0,  0,  0, 37,  4,  0,  6,
     3,  2,  8, 47,  0,  0,  3,  1,  2,  6,  0,  0, 37,  6,  2,  0,
     2,  8,  2,  6, 37,  2,  2,  2,  2,  2, 37,  2, 28,  7,  0,  0,
     0,  0,  0,  7,  0,  3,  4,  0,  3,  2,  2,  2,  8,  5,  2,  0,
     2,  8,  3,  2,  0,  9,  0,  0,  2,  8,  2,  2,  2,  2, 27,  2,
     6, 28,  8,  0, 15,  2,  8,  0,
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
    3, 2, 0, 0, 3, 0, 3, 2, 2, 3, 3, 2, 2, 0, 2, 2,
    2, 2, 0, 0, 0, 0, 5, 0, 5, 0, 5, 0, 0, 5, 0, 5,
    0, 0, 0, 2, 0, 0, 1, 5, 0, 5, 5, 2, 2, 5, 2, 0,
    0, 1, 5, 5, 2, 2, 4, 0, 2, 3, 0, 3, 0, 3, 3, 0,
    0, 4, 3, 3, 2, 2, 2, 4, 2, 3, 0, 0, 3, 5, 5, 0,
    3, 2, 3, 3, 3, 2, 2, 0,
};

/* Joining_Type: 2384 bytes. */

RE_UINT32 re_get_joining_type(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 12;
    code = ch ^ (f << 12);
    pos = (RE_UINT32)re_joining_type_stage_1[f] << 5;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_joining_type_stage_2[pos + f] << 3;
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
    12, 13, 14, 15, 16, 10, 17,  5, 18, 10, 10, 19, 10, 20, 21, 22,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 23,
     5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5,  5, 23,
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
    129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 110, 110, 139, 110, 110, 110,
    140, 141, 142, 143, 144, 145, 146, 110, 147, 148, 110, 149, 150, 151, 152, 110,
    110, 153, 110, 110, 110, 154, 110, 110, 155, 156, 110, 110, 110, 110, 110, 110,
      2,   2,   2,   2,   2,   2,   2, 157, 158,   2, 159, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2,   2,   2,   2, 160, 161, 162,   2, 163, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110,   2,   2,   2, 164, 165, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2,   2,   2,   2, 166, 167, 168, 169, 110, 110, 110, 110, 110, 110, 170, 171,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79, 172,
     79,  79,  79,  79,  79, 173, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    174, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    110, 110, 110, 110, 110, 110, 110, 110, 175, 176, 110, 110, 110, 110, 110, 110,
      2, 177, 178, 179, 180, 110, 181, 110, 182, 183, 184,   2,   2, 185,   2, 186,
      2,   2,   2,   2, 187, 188, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
    189, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
      2, 190, 191, 110, 110, 110, 110, 110, 110, 110, 110, 110, 192, 193, 110, 110,
     79,  79, 194, 195,  79,  79,  79, 196, 197, 198, 199, 200, 201, 202, 203, 204,
    205, 206, 207,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79, 208,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,
     79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79,  79, 208,
    209, 110, 210, 211, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110, 110,
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
     47,  47,   4,  48,  47,  49,  50,   1,  51,   4,   4,  52,   1,  53,  54,   4,
     55,  56,  57,  58,  59,  60,  61,  62,  63,  56,  57,  64,  65,  66,  67,  68,
     69,  18,  57,  70,  71,  72,  61,  73,  74,  56,  57,  70,  75,  76,  61,  77,
     78,  79,  80,  81,  82,  83,  67,  84,  85,  86,  57,  87,  88,  89,  61,  90,
     91,  86,  57,  92,  88,  93,  61,  94,  95,  86,   4,  96,  97,  98,  61,  99,
    100, 101,   4, 102, 103, 104,  67, 105, 106, 107, 107, 108, 109, 110,  47,  47,
    111, 112, 113, 114, 115, 116,  47,  47, 117, 118,  36, 119, 120,   4, 121, 122,
    123, 124,   1, 125, 126, 127,  47,  47, 107, 107, 107, 107, 128, 107, 107, 107,
    107, 129,   4,   4, 130,   4,   4,   4, 131, 131, 131, 131, 131, 131, 132, 132,
    132, 132, 133, 134, 134, 134, 134, 134,   4,   4,   4,   4, 135, 136,   4,   4,
    135,   4,   4, 137, 138, 139,   4,   4,   4, 138,   4,   4,   4, 140, 141, 121,
      4, 142,   4,   4,   4,   4,   4, 143, 144,   4,   4,   4,   4,   4,   4,   4,
    144, 145,   4,   4,   4,   4, 146, 147, 148, 149,   4, 150,   4, 151, 148, 152,
    107, 107, 107, 107, 107, 153, 154, 142, 155, 154,   4,   4,   4,   4,   4,  77,
    156,   4, 157,   4,   4,   4,   4, 158,   4,  45, 159, 159, 160, 107, 161, 162,
    107, 107, 163, 107, 164, 165,   4,   4,   4, 166, 107, 107, 107, 167, 107, 168,
    154, 154, 161, 169,  47,  47,  47,  47, 170,   4,   4, 171, 172, 173, 174, 175,
    176,   4, 177,  36,   4,   4,  40, 178,   4,   4, 171, 179, 180,  36,   4, 181,
    147,  47,  47,  47,  77, 182, 183, 184,   4,   4,   4,   4,   1,   1,   1, 185,
      4, 143,   4,   4, 143, 186,   4, 187,   4,   4,   4, 188, 188, 189,   4, 190,
    191, 192, 193, 194, 195, 196, 197, 198, 199, 121, 200, 201, 202,   1,   1, 203,
    204, 205, 206,   4,   4, 207, 208, 209, 210, 209,   4,   4,   4, 211,   4,   4,
    212, 213, 214, 215, 216, 217, 218,   4, 219, 220, 221, 222,   4,   4, 223,   4,
    224, 225, 226,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4,   4, 227,
      4,   4, 228,  47, 229,  47, 230, 230, 230, 230, 230, 230, 230, 230, 230, 231,
    230, 230, 230, 230, 208, 230, 230, 232, 230, 233, 234, 235, 236, 237, 238,   4,
    239, 240,   4, 241, 242,   4, 243, 244,   4, 245,   4, 246, 247, 248, 249, 250,
    251,   4,   4,   4,   4, 252, 253, 254, 230, 255,   4,   4, 256,   4, 257,   4,
    258, 259,   4,   4,   4, 224,   4, 260,   4,   4,   4,   4,   4, 261,   4, 262,
      4, 263,   4, 264,  57, 265, 266,  47,   4,   4,  45,   4,   4,  45,   4,   4,
      4,   4,   4,   4,   4,   4, 267, 268,   4,   4, 130,   4,   4,   4, 269, 270,
      4, 228, 271, 271, 271, 271,   1,   1, 272, 273, 274, 275, 276,  47,  47,  47,
    277, 278, 277, 277, 277, 277, 277, 279, 277, 277, 277, 277, 277, 277, 277, 277,
    277, 277, 277, 277, 277, 280,  47, 281, 282, 283, 284, 285, 286, 277, 287, 277,
    288, 289, 290, 277, 287, 277, 288, 291, 292, 277, 293, 294, 277, 277, 277, 277,
    295, 277, 277, 296, 277, 277, 279, 297, 277, 295, 277, 277, 298, 277, 277, 277,
    277, 277, 277, 277, 277, 277, 277, 295, 277, 277, 277, 277,   4,   4,   4,   4,
    277, 299, 277, 277, 277, 277, 277, 277, 300, 277, 277, 277, 301,   4,   4, 181,
    302,   4, 303,  47,   4,   4, 267, 304,   4, 305,   4,   4,   4,   4,   4, 306,
      4,   4,  45,  77,  47,  47,  47, 307, 308,   4, 309, 310,   4,   4,   4, 311,
    312,   4,   4, 171, 313, 154,   1, 314,  36,   4, 315,   4, 316, 317, 131, 318,
     51,   4,   4, 319, 320, 321, 107, 322,   4,   4, 323, 324, 325, 326, 107, 107,
    107, 107, 107, 107, 327, 328,  31, 329, 330, 331, 271,   4,   4,   4, 158,   4,
      4,   4,   4,   4,   4,   4, 332, 154, 333, 334, 335, 336, 335, 337, 335, 333,
    334, 335, 336, 335, 337, 335, 333, 334, 335, 336, 335, 337, 335, 333, 334, 335,
    336, 335, 337, 335, 333, 334, 335, 336, 335, 337, 335, 333, 334, 335, 336, 335,
    337, 335, 333, 334, 335, 336, 335, 337, 335, 333, 334, 335, 336, 335, 337, 335,
    336, 335, 338, 132, 339, 134, 134, 340, 341, 341, 341, 341, 341, 341, 341, 341,
     47,  47,  47,  47,  47,  47,  47,  47, 228, 342, 343, 344, 345,   4,   4,   4,
      4,   4,   4,   4, 265, 346,   4,   4,   4,   4,   4, 347,  47,   4,   4,   4,
      4, 348,   4,   4,  77,  47,  47, 349,   1, 350,   1, 351, 352, 353, 354, 188,
      4,   4,   4,   4,   4,   4,   4, 355, 356, 357, 277, 358, 277, 359, 360, 361,
    277, 362, 277, 295, 363, 364, 365, 366, 367,   4, 139, 368, 187, 187,  47,  47,
      4,   4,   4,   4,   4,   4,   4, 229, 369,   4,   4, 370,   4,   4,   4,   4,
     45, 371,  72,  47,  47,   4,   4, 372,   4, 121,   4,   4,   4,  72,  33, 371,
      4,   4, 373,   4, 229,   4,   4, 374,   4, 375,   4,   4, 376, 377,  47,  47,
      4, 187, 154,   4,   4, 376,   4, 371,   4,   4,  77,   4,   4,   4, 378,  47,
      4,   4,   4, 228,   4, 158,  77,  47, 379,   4,   4, 380,   4, 381,   4,   4,
      4,  45, 307,  47,  47,  47,   4, 382,   4, 383,   4, 384,  47,  47,  47,  47,
      4,   4,   4, 385,   4, 348,   4,   4, 386, 387,   4, 388,  77, 389,   4,   4,
      4,   4,  47,  47,   4,   4, 390, 391,   4,   4,   4, 392,   4, 263,   4, 393,
      4, 394, 395,  47,  47,  47,  47,  47,   4,   4,   4,   4, 147,  47,  47,  47,
      4,   4,   4, 396,   4,   4,   4, 397,  47,  47,  47,  47,  47,  47,   4,  45,
    176,   4,   4, 398, 399, 348, 400, 401, 176,   4,   4, 402, 403,   4, 147, 154,
    176,   4, 316, 404, 405,   4,   4, 406, 176,   4,   4, 319, 407, 408,  20, 409,
      4,  18, 410, 411,  47,  47,  47,  47, 412,  37, 413,   4,   4, 267, 414, 154,
    415,  56,  57,  70,  75, 416, 417, 418,   4,   4,   4, 419, 420, 421,  47,  47,
      4,   4,   4,   1, 422, 154,  47,  47,   4,   4, 267, 423, 424, 425,  47,  47,
      4,   4,   4,   1, 426, 154, 427,  47,   4,   4,  31, 428, 154,  47,  47,  47,
    107, 429, 163, 430,  47,  47,  47,  47,  47,  47,   4,   4,   4,   4,  36, 431,
     47,  47,  47,  47,   4,   4,   4, 147,  57,   4, 267, 432, 433,  36, 121, 434,
      4, 435, 124, 324,  47,  47,  47,  47,   4, 142,  47,  47,  47,  47,  47,  47,
      4,   4,   4,   4,   4,   4,  45, 436,   4,   4,   4,   4, 373,  47,  47,  47,
      4,   4,   4,   4,   4, 437,   4,   4, 438,   4,   4,   4,   4,   4,   4,   4,
      4,   4,   4,   4,   4,   4,   4, 439,   4,   4,  45,  47,  47,  47,  47,  47,
      4,   4,   4,   4, 440,   4,   4,   4,   4,   4,   4,   4, 228,  47,  47,  47,
      4,   4,   4, 147,   4,  45, 441,  47,  47,  47,  47,  47,  47,   4, 187, 442,
      4,   4,   4, 443, 444, 445,  18, 446,   4,  47,  47,  47,  47,  47,  47,  47,
      4,   4,   4,   4, 409, 447,   1, 169, 401, 176,  47,  47,  47,  47, 448,  47,
    277, 277, 277, 277, 277, 277, 300,  47, 277, 277, 277, 277, 277, 277, 277, 449,
    450,  47,  47,  47,  47,  47,  47,  47,   4,   4,   4,   4,   4,   4, 229, 121,
    147, 451, 452,  47,  47,  47,  47,  47,   4,   4,   4,   4,   4,   4,   4, 158,
      4,   4,  21,   4,   4,   4, 453,   1, 454,   4, 455,   4,   4,   4, 147,  47,
      4,   4,   4,   4, 456,  47,  47,  47,   4,   4,   4,   4,   4, 228,   4, 265,
      4,   4,   4,   4,   4, 188,   4,   4,   4, 148, 457, 458, 459,   4,   4,   4,
    460, 461,   4, 462, 463,  86,   4,   4,   4,   4, 263,   4,   4,   4,   4,   4,
      4,   4,   4,   4, 464, 465, 465, 465,   1,   1,   1, 466,   1,   1, 467, 468,
    469, 470,  23,  47,  47,  47,  47,  47, 432, 471, 472,  47,  47,  47,  47,  47,
      4,   4,   4,   4, 473, 324,  47,  47,   4,   4,   4,   4, 474, 475,  47,  47,
    459,   4, 476, 477, 478, 479, 480, 481, 482, 371, 483, 371,  47,  47,  47, 265,
    484, 230, 485, 230, 230, 230, 486, 230, 230, 230, 484, 277, 277, 277, 487, 488,
    489, 490, 277, 491, 492, 277, 277, 493, 277, 277, 277, 277, 494, 495, 496, 497,
    498, 277, 499, 500, 277, 277, 277, 277, 501, 502, 503, 504, 505, 277, 277, 506,
    277, 507, 277, 277, 277, 508, 277, 509, 277, 277, 277, 277, 510,   4,   4, 511,
    277, 277, 512, 513, 495, 277, 277, 277,   4,   4,   4,   4,   4,   4,   4, 514,
      4,   4,   4,   4,   4, 503, 277, 277, 515,   4,   4,   4, 516, 505,   4,   4,
    516,   4, 517, 277, 277, 277, 277, 277, 277, 518, 519, 520, 277, 277, 277, 277,
    277, 277, 277, 277, 277, 277, 277, 293, 521,  47,   1,   1,   1,   1,   1,   1,
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
     14,  14,  38,  14,  14,  14,  14,  36,  36,  36,   0,   0,   0,   0,   0,   0,
      0,  19,   0,   0,   0,   0,   0,   0,   0,   0,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,   0,  44,   0,  19,   0,   0,   0,  14,  14,  14,  14,
     14,   0,  58,  12,  12,  12,  12,  12,  19,   0,  39,  14,  14,  14,  38,  39,
     38,  39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  38,  14,  14,  14,
     38,  38,  36,  14,  14,  36,  44,   0,   0,   0,  52,  42,  52,  42,   0,  38,
     36,  36,  36,  42,  36,  36,  14,  39,  14,   0,  36,  12,  12,  12,  12,  12,
     14,  50,  14,  14,  49,   9,  36,  36,  42,   0,  39,  14,  14,  38,  36,  39,
     38,  14,  39,  38,  14,  36,  52,   0,   0,  52,  36,  42,  52,  42,   0,  36,
     42,  36,  36,  36,  39,  14,  38,  38,  36,  36,  36,  12,  12,  12,  12,  12,
      0,  14,  19,  36,  36,  36,  36,  36,  42,   0,  39,  14,  14,  14,  14,  39,
     38,  14,  39,  14,  14,  36,  44,   0,   0,   0,   0,  42,   0,  42,   0,  36,
     38,  36,  36,  36,  36,  36,  36,  36,   9,  36,  36,  36,  39,  36,  36,  36,
     42,   0,  39,  14,  14,  14,  38,  39,   0,   0,  52,  42,  52,  42,   0,  36,
     36,  36,  36,   0,  36,  36,  14,  39,  14,  14,  14,  14,  36,  36,  36,  36,
     36,  44,  39,  14,  14,  38,  36,  14,  38,  14,  14,  36,  39,  38,  38,  14,
     36,  39,  38,  36,  14,  38,  36,  14,  14,  14,  14,  14,  14,  36,  36,   0,
      0,  52,  36,   0,  52,   0,   0,  36,  38,  36,  36,  42,  36,  36,  36,  36,
     14,  14,  14,  14,   9,  38,  36,  36,   0,   0,  39,  14,  14,  14,  38,  14,
     38,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  36,  39,   0,
      0,   0,  52,   0,  52,   0,   0,  36,  36,  36,  42,  52,  14,  38,  36,  36,
     36,  36,  36,  36,  14,  14,  14,  14,  19,   0,  39,  14,  14,  14,  38,  14,
     14,  14,  39,  14,  14,  36,  44,   0,  36,  36,  42,  52,  36,  36,  36,  38,
     39,  38,  36,  36,  36,  36,  36,  36,  42,   0,  39,  14,  14,  14,  38,  14,
     14,  14,  14,  14,  14,  38,  39,   0,   0,   0,  52,   0,  52,   0,   0,  14,
     36,  36,  14,  19,  14,  14,  14,  14,  14,  14,  14,  14,  49,  14,  14,  14,
     36,   0,  39,  14,  14,  14,  14,  14,  14,  14,  14,  38,  36,  14,  14,  14,
     14,  39,  14,  14,  14,  14,  39,  36,  14,  14,  14,  38,  36,  52,  36,  42,
      0,   0,  52,  52,   0,   0,   0,   0,  36,   0,  38,  36,  36,  36,  36,  36,
     59,  60,  60,  60,  60,  60,  60,  60,  60,  60,  60,  60,  60,  60,  60,  60,
     60,  60,  60,  60,  60,  61,  36,  62,  60,  60,  60,  60,  60,  60,  60,  63,
     12,  12,  12,  12,  12,  58,  36,  36,  59,  61,  61,  59,  61,  61,  59,  36,
     36,  36,  60,  60,  59,  60,  60,  60,  59,  60,  59,  59,  36,  60,  59,  60,
     60,  60,  60,  60,  60,  59,  60,  36,  60,  60,  61,  61,  60,  60,  60,  36,
     12,  12,  12,  12,  12,  36,  60,  60,  32,  64,  29,  64,  65,  66,  67,  53,
     53,  68,  56,  14,   0,  14,  14,  14,  14,  14,  43,  19,  19,  69,  69,   0,
     14,  14,  14,  14,  39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  38,  36,
     42,   0,   0,   0,   0,   0,   0,   1,   0,   0,   1,   0,  14,  14,  19,   0,
      0,   0,   0,   0,  42,   0,   0,   0,   0,   0,   0,   0,   0,   0,  52,  58,
     14,  14,  14,  44,  14,  14,  38,  14,  64,  70,  14,  14,  71,  72,  36,  36,
     12,  12,  12,  12,  12,  58,  14,  14,  12,  12,  12,  12,  12,  60,  60,  60,
     14,  14,  14,  39,  36,  36,  39,  36,  73,  73,  73,  73,  73,  73,  73,  73,
     74,  74,  74,  74,  74,  74,  74,  74,  74,  74,  74,  74,  75,  75,  75,  75,
     75,  75,  75,  75,  75,  75,  75,  75,  14,  14,  14,  14,  38,  14,  14,  36,
     14,  14,  14,  38,  38,  14,  14,  36,  38,  14,  14,  36,  14,  14,  14,  38,
     38,  14,  14,  36,  14,  14,  14,  14,  14,  14,  14,  38,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  38,  42,   0,  27,  14,  14,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  36,  36,  36,  14,  14,  14,  36,  14,  14,  14,  36,
     76,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  16,  77,  36,
     14,  14,  14,  14,  14,  27,  58,  14,  14,  14,  14,  14,  38,  36,  36,  36,
     14,  14,  14,  14,  14,  14,  38,  14,  14,   0,  52,  36,  36,  36,  36,  36,
     14,   0,   1,  41,  36,  36,  36,  36,  14,   0,  36,  36,  36,  36,  36,  36,
     38,   0,  36,  36,  36,  36,  36,  36,  60,  60,  58,  78,  76,  79,  60,  36,
     12,  12,  12,  12,  12,  36,  36,  36,  14,  53,  58,  29,  53,  19,   0,  72,
     14,  14,  19,  44,  14,  14,  14,  14,  14,  14,  14,  14,  19,  38,  36,  36,
     14,  14,  14,  36,  36,  36,  36,  36,   0,   0,   0,   0,   0,   0,  36,  36,
     38,  36,  53,  12,  12,  12,  12,  12,  60,  60,  60,  60,  60,  60,  60,  36,
     60,  60,  61,  36,  36,  36,  36,  36,  60,  60,  60,  60,  60,  60,  36,  36,
     60,  60,  60,  60,  60,  36,  36,  36,  12,  12,  12,  12,  12,  61,  36,  60,
     14,  14,  14,  19,   0,   0,  36,  14,  60,  60,  60,  60,  60,  60,  60,  61,
     60,  60,  60,  60,  60,  60,  61,  42,   0,   0,   0,   0,   0,   0,   0,  52,
      0,   0,  44,  14,  14,  14,  14,  14,  14,  14,   0,   0,   0,   0,   0,   0,
      0,   0,  44,  14,  14,  14,  36,  36,  12,  12,  12,  12,  12,  58,  27,  58,
     76,  14,  14,  14,  14,  19,   0,   0,   0,   0,  14,  14,  14,  14,  38,  36,
      0,  44,  14,  14,  14,  14,  14,  14,  19,   0,   0,   0,   0,   0,   0,  14,
      0,   0,  36,  36,  36,  36,  14,  14,   0,   0,   0,   0,  36,  80,  58,  58,
     12,  12,  12,  12,  12,  36,  39,  14,  14,  14,  14,  14,  14,  14,  14,  58,
      0,  44,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  44,  14,  19,  14,
     14,   0,  44,  38,   0,  36,  36,  36,   0,   0,   0,  36,  36,  42,   0,   0,
     14,  14,  14,  14,  39,  39,  39,  39,  14,  14,  14,  14,  14,  14,  14,  36,
     14,  14,  38,  14,  14,  14,  14,  14,  14,  14,  36,  14,  14,  14,  39,  14,
     36,  14,  38,  14,  14,  14,  32,  38,  58,  58,  58,  81,  58,  82,  83,   0,
     81,  58,  84,  25,  85,  86,  85,  86,  28,  14,  87,  88,  89,   0,   0,  33,
     50,  50,  50,  50,   7,  90,  91,  14,  14,  14,  92,  93,  91,  14,  14,  14,
     14,  14,  14,  76,  58,  58,  27,  58,  94,  14,  38,   0,   0,   0,   0,   0,
     14,  36,  25,  14,  14,  14,  16,  95,  24,  28,  25,  14,  14,  14,  16,  77,
     23,  23,  23,   6,  23,  23,  23,  23,  23,  23,  23,  22,  23,   6,  23,  22,
     23,  23,  23,  23,  23,  23,  23,  23,  52,  36,  36,  36,  36,  36,  36,  36,
     14,  49,  24,  14,  49,  14,  14,  14,  14,  24,  14,  96,  14,  14,  14,  14,
     24,  25,  14,  14,  14,  24,  14,  14,  14,  14,  28,  14,  14,  24,  14,  25,
     28,  28,  28,  28,  28,  28,  14,  14,  28,  28,  28,  28,  28,  14,  14,  14,
     14,  14,  14,  14,  24,  14,  36,  36,  14,  25,  25,  14,  14,  14,  14,  14,
     25,  28,  14,  24,  25,  24,  14,  24,  24,  23,  24,  14,  14,  25,  24,  28,
     25,  24,  24,  24,  28,  28,  25,  25,  14,  14,  28,  28,  14,  14,  28,  14,
     14,  14,  14,  14,  25,  14,  25,  14,  14,  25,  14,  14,  14,  14,  14,  14,
     28,  14,  28,  28,  14,  28,  14,  28,  14,  28,  14,  28,  14,  14,  14,  14,
     14,  14,  24,  14,  24,  14,  14,  14,  14,  14,  24,  14,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  14,  24,  14,  14,  14,  14,  14,  14,  14,  97,
     14,  14,  14,  14,  69,  69,  14,  14,  14,  25,  14,  14,  14,  98,  14,  14,
     14,  14,  14,  14,  16,  99,  14,  14,  98,  98,  14,  14,  14,  14,  14,  38,
     14,  14,  14,  38,  36,  36,  36,  36,  14,  14,  14,  14,  14,  38,  36,  36,
     28,  28,  28,  28,  28,  28,  28,  28,  28,  28,  28,  28,  28,  28,  28,  25,
     28,  28,  25,  14,  14,  14,  14,  14,  14,  28,  28,  14,  14,  14,  14,  14,
     28,  24,  28,  28,  28,  14,  14,  14,  14,  28,  14,  28,  14,  14,  28,  14,
     28,  14,  14,  28,  25,  24,  14,  28,  28,  14,  14,  14,  14,  14,  14,  14,
     14,  28,  28,  14,  14,  14,  14,  24,  98,  98,  24,  25,  24,  14,  14,  28,
     14,  14,  98,  28, 100,  98, 101,  98,  14,  14,  14,  14, 102,  98,  14,  14,
     25,  25,  14,  14,  14,  14,  14,  14,  28,  24,  28,  24, 103,  25,  28,  24,
     14,  14,  14,  14,  14,  14,  14, 102,  14,  14,  14,  14,  14,  14,  14,  28,
     14,  14,  14,  14,  14,  14, 102,  98,  98,  98,  98,  98, 103,  28, 104, 102,
     98, 104, 103,  28,  98,  28, 103, 104,  98,  24,  14,  14,  28, 103,  28,  28,
    104,  98,  98, 104, 101, 103, 104,  98,  98,  98, 100,  14,  98, 105, 105,  14,
     14,  14,  14,  24,  14,   7,  85,  85,   5,  53, 100,  14,  69,  69,  69,  69,
     69,  69,  69,  28,  28,  28,  28,  28,  28,  28,  14,  14,  14,  14,  14,  14,
     14,  14,  16,  99,  14,  14,  14,  14,  14,  14,  14,  69,  69,  69,  69,  69,
     14,  16, 106, 106, 106, 106, 106, 106, 106, 106, 106, 106,  99,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  69,  14,  14,  14,  24,  28,  28,  14,  14,  14,
     14,  14,  36,  14,  14,  14,  14,  14,  14,  14,  14,  36,  14,  14,  14,  14,
     14,  14,  14,  14,  14,  36,  39,  14,  14,  36,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  36,  14,  14,  14,  14,  14,  14,  14,  14,  14,  19,
      0,  14,  36,  36, 107,  58,  76, 108,  14,  14,  14,  14,  36,  36,  36,  39,
     41,  36,  36,  36,  36,  36,  36,  42,  14,  14,  14,  38,  14,  14,  14,  38,
     85,  85,  85,  85,  85,  85,  85,  58,  58,  58,  58,  27, 109,  14,  85,  14,
     85,  69,  69,  69,  69,  58,  58,  56,  58,  27,  76,  14,  14, 110,  58,  76,
     58, 109,  41,  36,  36,  36,  36,  36,  98,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98, 111,  98,  98,  98,  98,  36,  36,  36,  36,  36,  36,
     98,  98,  98,  36,  36,  36,  36,  36,  98,  98,  98,  98,  98,  98,  36,  36,
     18, 112, 113,  98,  69,  69,  69,  69,  69,  98,  69,  69,  69,  69, 114, 115,
     98,  98,  98,  98,  98,   0,   0,   0,  98,  98, 116,  98,  98, 113, 117,  98,
    118, 119, 119, 119, 119,  98,  98,  98,  98, 119,  98,  98,  98,  98,  98,  98,
     98, 119, 119, 119,  98,  98,  98, 120,  98,  98, 119, 121,  42, 122,  91, 117,
    123, 119, 119, 119, 119,  98,  98,  98,  98,  98, 119, 120,  98, 113, 124, 117,
     36,  36, 111,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  36,
    111,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98,  98, 125,
     98,  98,  98,  98,  98, 125,  36,  36, 126, 126, 126, 126, 126, 126, 126, 126,
     98,  98,  98,  98,  28,  28,  28,  28,  98,  98, 113,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98, 125,  36,  98,  98,  98, 125,  36,  36,  36,  36,
     14,  14,  14,  14,  14,  14,  27, 108,  12,  12,  12,  12,  12,  14,  36,  36,
      0,  44,   0,   0,   0,   0,   0,  14,  14,  14,  14,  14,  14,  14,  14,   0,
      0,  27,  58,  58,  36,  36,  36,  36,  36,  36,  36,  39,  14,  14,  14,  14,
     14,  44,  14,  44,  14,  19,  14,  14,  14,  19,   0,   0,  14,  14,  36,  36,
     14,  14,  14,  14, 127,  36,  36,  36,  14,  14,  64,  53,  36,  36,  36,  36,
      0,  14,  14,  14,  14,  14,  14,  14,   0,   0,   0,  36,  36,  36,  36,  58,
      0,  14,  14,  14,  14,  14,  29,  36,  14,  14,  14,   0,   0,   0,   0,  58,
     14,  14,  14,  19,   0,   0,   0,   0,   0,   0,  36,  36,  36,  36,  36,  39,
     73,  73,  73,  73,  73,  73, 128,  36,  14,  19,   0,   0,   0,   0,   0,   0,
     44,  14,  14,  27,  58,  14,  14,  39,  12,  12,  12,  12,  12,  36,  36,  14,
     12,  12,  12,  12,  12,  60,  60,  61,  14,  14,  14,  14,  19,   0,   0,   0,
      0,   0,   0,  52,  36,  36,  36,  36,  14,  19,  14,  14,  14,  14,   0,  36,
     12,  12,  12,  12,  12,  36,  27,  58,  60,  61,  36,  36,  36,  36,  36,  36,
     36,  36,  36,  36,  36,  59,  60,  60,  58,  14,  19,  52,  36,  36,  36,  36,
     39,  14,  14,  38,  39,  14,  14,  38,  39,  14,  14,  38,  36,  36,  36,  36,
     14,  19,   0,   0,   0,   1,   0,  36, 129, 130, 130, 130, 130, 130, 130, 130,
    130, 130, 130, 130, 130, 130, 129, 130, 130, 130, 130, 130, 130, 130, 130, 130,
    130, 130, 130, 130, 129, 130, 130, 130, 130, 130, 129, 130, 130, 130, 130, 130,
    130, 130,  36,  36,  36,  36,  36,  36,  74,  74,  74, 131,  36, 132,  75,  75,
     75,  75,  75,  75,  75,  75,  36,  36, 133, 133, 133, 133, 133, 133, 133, 133,
     36,  39,  14,  14,  36,  36, 134, 135,  46,  46,  46,  46,  48,  46,  46,  46,
     46,  46,  46,  47,  46,  46,  47,  47,  46, 134,  47,  46,  46,  46,  46,  46,
     36,  39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14, 106,
     36,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14, 127,  36,
    136, 137,  57, 138, 139,  36,  36,  36,  98,  98, 140, 106, 106, 106, 106, 106,
    106, 106, 112, 140, 112,  98,  98,  98, 112,  77,  91,  53, 140, 106, 106, 112,
     98,  98,  98, 125, 141, 142,  36,  36,  14,  14,  14,  14,  14,  14,  38, 143,
    107,  98,   6,  98,  69,  98, 112, 112,  98,  98,  98,  98,  98,  91,  98, 144,
     98,  98,  98,  98,  98, 140, 145,  98,  98,  98,  98,  98,  98, 140, 145, 140,
    115,  69,  93, 119, 126, 126, 126, 126, 120,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  98,  91,  36,  98,  98,  98,  36,  98,  98,  98,
     36,  98,  98,  98,  36,  98, 125,  36,  22,  98, 141, 146,  14,  14,  14,  38,
     36,  36,  36,  36,  42,   0, 147,  36,  14,  14,  14,  14,  14,  14,  39,  14,
     14,  14,  14,  14,  14,  38,  14,  39,  58,  41,  36,  39,  14,  14,  14,  14,
     14,  14,  36,  39,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  36,  36,
     14,  14,  14,  14,  14,  14,  19,  36,  14,  14,  36,  36,  36,  36,  36,  36,
     14,  14,  14,   0,   0,  52,  36,  36,  14,  14,  14,  14,  14,  14,  14,  80,
     14,  14,  36,  36,  14,  14,  14,  14,  76,  14,  14,  36,  36,  36,  36,  36,
     14,  14,  36,  36,  36,  36,  36,  39,  14,  14,  14,  36,  38,  14,  14,  14,
     14,  14,  14,  39,  38,  36,  38,  39,  14,  14,  14,  80,  14,  14,  14,  14,
     14,  38,  14,  36,  36,  39,  14,  14,  14,  14,  14,  14,  14,  14,  36,  80,
     14,  14,  14,  14,  14,  36,  36,  39,  14,  14,  14,  14,  36,  36,  14,  14,
     19,   0,  42,  52,  36,  36,   0,   0,  14,  14,  39,  14,  39,  14,  14,  14,
     14,  14,  36,  36,   0,  52,  36,  42,  58,  58,  58,  58,  38,  36,  36,  36,
     14,  14,  19,  52,  36,  39,  14,  14,  58,  58,  58, 148,  36,  36,  36,  36,
     14,  14,  14,  36,  80,  58,  58,  58,  14,  38,  36,  36,  14,  14,  14,  14,
     14,  36,  36,  36,  39,  14,  38,  36,  36,  36,  36,  36,  39,  14,  14,  14,
     14,  38,  36,  36,  36,  36,  36,  36,  14,  38,  36,  36,  36,  14,  14,  14,
     14,  14,  14,  14,   0,   0,   0,   0,   0,   0,   0,   1,  76,  14,  14,  36,
     14,  14,  14,  12,  12,  12,  12,  12,  36,  36,  36,  36,  36,  36,  36,  42,
      0,   0,   0,   0,   0,  44,  14,  58,  58,  36,  36,  36,  36,  36,  36,  36,
      0,   0,  52,  12,  12,  12,  12,  12,  58,  58,  36,  36,  36,  36,  36,  36,
     14,  19,  32,  38,  36,  36,  36,  36,  44,  14,  27,  76,  76,   0,  44,  36,
     12,  12,  12,  12,  12,  32,  27,  58,  14,  14,  38,  36,  36,  36,  36,  36,
     14,  14,  14,  14,  14,  14,   0,   0,   0,   0,   0,   0,  58,  27,  76,  52,
     14,  14,  14,  38,  38,  14,  14,  39,  14,  14,  14,  14,  27,  36,  36,  36,
      0,   0,   0,   0,   0,  52,  36,  36,   0,   0,  39,  14,  14,  14,  38,  39,
     38,  36,  36,  42,  36,  36,  39,  14,  14,   0,  36,   0,   0,   0,  52,  36,
      0,   0,  52,  36,  36,  36,  36,  36,  14,  14,  19,   0,   0,   0,   0,   0,
      0,   0,   0,  44,  14,  27,  58,  76,  12,  12,  12,  12,  12,  80,  39,  36,
      0,   0,  14,  14,  36,  36,  36,  36,   0,   0,   0,  36,   0,   0,   0,   0,
    149,  58,  53,  14,  27,  58,  58,  58,  58,  58,  58,  58,  14,  14,   0,  36,
      1,  76,  38,  36,  36,  36,  36,  36,  64,  64,  64,  64,  64,  64, 150,  36,
      0,   0,   0,   0,  36,  36,  36,  36,  60,  60,  60,  60,  60,  36,  59,  60,
     12,  12,  12,  12,  12,  60,  58, 151,  14,  38,  36,  36,  36,  36,  36,  39,
      0,   0,   0,  52,   0,   0,   0,   0,  27,  58,  58,  36,  36,  36,  36,  36,
    152,  14,  14,  14,  14,  14,  14,  14,  36,   0,   0,   0,   0,   0,   0,   0,
     58,  58,  41,  36,  36,  36,  36,  36,  14,  14,  14,  14, 153,  69, 115,  14,
     14,  99,  14,  69,  69,  14,  14,  14,  14,  14,  14,  14,  16, 115,  14,  14,
     14,  14,  14,  14,  14,  14,  14,  69,  12,  12,  12,  12,  12,  36,  36,  58,
      0,   0,   1,  36,  36,  36,  36,  36,   0,   0,   0,   1,  58,  14,  14,  14,
     14,  14,  76,  36,  36,  36,  36,  36,  12,  12,  12,  12,  12,  39,  14,  14,
     14,  14,  14,  14,  36,  36,  39,  14,  19,   0,   0,   0,   0,   0,   0,   0,
    154,  36,  36,  36,  36,  36,  36,  36,  98, 125,  36,  36,  36,  36,  36,  36,
     98,  36,  36,  36,  36,  36,  36,  36,  14,  14,  14,  14,  14,  36,  19,   1,
      0,   0,  36,  36,  36,  36,  36,  36,  14,  14,  19,   0,   0,  14,  19,   0,
      0,  44,  19,   0,   0,   0,  14,  14,  14,  14,  14,  14,  14,   0,   0,  14,
     14,   0,  44,  36,  36,  36,  36,  36,  36,  38,  39,  38,  39,  14,  38,  14,
     14,  14,  14,  14,  14,  39,  39,  14,  14,  14,  39,  14,  14,  14,  14,  14,
     14,  14,  14,  39,  14,  38,  39,  14,  14,  14,  38,  14,  14,  14,  38,  14,
     14,  14,  14,  14,  14,  39,  14,  38,  14,  14,  38,  38,  36,  14,  14,  14,
     14,  14,  14,  14,  14,  14,  36,  12,  12,  12,  12,  12,  12,  12,  12,  12,
      0,   0,   0,  44,  14,  19,   0,   0,   0,   0,   0,   0,   0,   0,  44,  14,
     14,  14,  19,  14,  14,  14,  14,  14,  14,  14,  44,  27,  58,  76,  36,  36,
     36,  36,  36,  36,  36,  42,   0,   0,   0,   0,   0,   0,  52,  42,   0,   0,
      0,  42,  52,   0,   0,  52,  36,  36,  14,  14,  38,  39,  14,  14,  14,  14,
     14,  14,   0,   0,   0,  52,  36,  36,  12,  12,  12,  12,  12,  36,  36, 153,
     39,  38,  38,  39,  39,  14,  14,  14,  14,  38,  14,  14,  39,  39,  36,  36,
     36,  38,  36,  39,  39,  39,  39,  14,  39,  38,  38,  39,  39,  39,  39,  39,
     39,  38,  38,  39,  14,  38,  14,  14,  14,  38,  14,  14,  39,  14,  38,  38,
     14,  14,  14,  14,  14,  39,  14,  14,  39,  14,  39,  14,  14,  39,  14,  14,
     28,  28,  28,  28,  28,  28, 104,  98,  28,  28,  28,  28,  28,  28,  28, 102,
     28,  28,  28,  28,  28,  14,  98,  98,  98,  98,  98, 155, 155, 155, 155, 155,
    155, 155, 155, 155, 155, 155, 155, 155,  98,  98, 101,  98,  98,  98,  98,  98,
     98,  98,  98,  98,  98,  98,  14,  98,  98,  98, 100, 102,  98,  98, 102,  98,
     98, 101, 156,  98,  98, 105,  98,  98,  98,  98,  98,  98,  98, 157, 158, 158,
     98, 105,  98, 105, 105, 105, 105, 105, 156,  98,  98,  98,  98,  98,  98,  98,
     98,  98,  98, 105, 105,  98,  98, 156, 105, 105, 105, 105, 156,  98, 156,  98,
    101, 105, 101, 105,  98,  98,  98,  98, 102, 102, 102,  98,  98, 156,  98, 100,
    100, 102,  98,  98,  98,  98,  98,  98,  14,  14,  14, 102,  98,  98,  98,  98,
     98,  98,  98, 100,  14,  14,  14,  14,  14,  14, 102,  98,  98,  98,  98,  98,
     98,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  14,  98,  98,  98,
     98,  98, 101,  98,  98, 156,  98,  98, 156,  98, 101, 156,  98,  98,  98,  98,
     98,  98,  14,  14,  14,  14,  98,  98,  98,  98,  14,  14,  14,  98,  98,  98,
     98,  98, 101, 105,  98, 101, 105, 105,  14,  14,  14,  85, 159,  91,  14,  14,
     98, 101,  98,  98,  98,  98,  98,  98,  98,  98, 105, 156,  98,  98,  98,  98,
     14,  14,  98,  98,  98,  98,  98,  98,  14,  14,  14,  14,  14,  14,  98,  98,
     14,  14,  14,  14,  98,  98,  98,  98,  14,  14,  14,  14,  14,  14,  14,  98,
     98,  98,  98,  98, 105, 105, 105, 156,  98,  98,  98, 156,  98,  98,  98,  98,
    156, 101, 105, 105, 105,  98, 105, 156,  42,  36,  36,  36,  36,  36,  36,  36,
};

static RE_UINT8 re_line_break_stage_5[] = {
    16, 16, 16, 18, 22, 20, 20, 21, 19,  6,  3, 12,  9, 10, 12,  3,
     1, 36, 12,  9,  8, 15,  8,  7, 11, 11,  8,  8, 12, 12, 12,  6,
    12,  1,  9, 36, 18,  2, 12, 16, 16, 29,  4,  1, 10,  9,  9,  9,
    12, 25, 25, 12, 25,  3, 12, 18, 25, 25, 17, 12, 25,  1, 17, 25,
    12, 17, 16,  4,  4,  4,  4, 16,  0,  0,  8, 12, 12,  0,  0, 12,
     0,  8, 18,  0,  0, 16, 18, 16, 16, 12,  6, 16, 37, 37, 37,  0,
    37, 12, 12, 10, 10, 10, 16,  6, 16,  0,  6,  6, 10, 11, 11, 12,
     6, 12,  8,  6, 18, 18,  0, 24, 24, 24, 24,  0,  0,  9, 24, 12,
    17, 17,  4, 17, 17, 18,  4,  6,  4, 12,  1,  2, 18, 17, 12,  4,
     4,  0, 31, 31, 32, 32, 33, 33, 18, 12,  2,  0,  5, 24, 18,  9,
     0, 18, 18,  4, 18, 28, 16, 42, 26, 25,  3,  3,  1,  3, 14, 14,
    14, 18, 20, 20,  3, 25,  5,  5,  8,  1,  2,  5, 30, 12,  2, 25,
     9, 12, 12, 14, 13, 13,  2, 12, 13, 12, 13, 40, 12, 13, 13, 25,
    25, 13, 40, 40,  2,  1,  0,  6,  6, 18,  1, 18, 26, 26,  0, 13,
     2, 13, 13,  5,  5,  1,  2,  2, 13, 16,  5, 13,  0, 38, 13, 38,
    38, 13, 38,  0, 16,  5,  5, 38, 38,  5, 13,  0, 38, 38, 10, 12,
    31,  0, 34, 35, 35, 35, 32,  0,  0, 33, 27, 27,  0, 37, 16, 37,
     8,  2,  2,  8,  6,  1,  2, 14, 13,  1, 13,  9, 10, 13,  0, 30,
    13,  6, 13,  2,  9,  0, 23, 25, 14,  0, 16, 17, 17,  0, 18, 24,
    17,  6,  1,  1,  5,  0, 39, 39, 40, 13, 13, 41, 41, 41,  3,  5,
};

/* Line_Break: 8960 bytes. */

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
     1, 56, 57, 58, 59,  1,  1,  1, 60, 61, 62, 63, 64,  1, 65,  1,
    66, 67, 54,  1,  9,  1, 68, 69, 70,  1,  1,  1, 71,  1,  1,  1,
     1,  1,  1,  1, 72,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 73, 74,  1,  1,  1,  1,
     1,  1,  1, 75,  1,  1,  1, 76,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 77, 53,  1,  1,  1,  1,  1,  1,
     1, 78,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    79, 80,  1,  1,  1,  1,  1,  1,  1, 81, 82, 83,  1,  1,  1,  1,
     1,  1,  1, 84,  1,  1,  1,  1,  1, 85,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 86,  1,  1,  1,  1,
     1,  1, 87,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 84,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_numeric_type_stage_3[] = {
      0,   1,   0,   0,   0,   2,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   3,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   3,   0,
      0,   0,   0,   4,   0,   0,   0,   5,   0,   0,   0,   4,   0,   0,   0,   4,
      0,   0,   0,   6,   0,   0,   0,   7,   0,   0,   0,   8,   0,   0,   0,   4,
      0,   0,   9,  10,   0,   0,   0,   4,   0,   0,   1,   0,   0,   0,   1,   0,
      0,  11,   0,   0,   0,   0,   0,   0,   0,   0,   3,   0,   1,   0,   0,   0,
      0,   0,   0,  12,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  13,
      0,   0,   0,   0,   0,   0,   0,  14,   1,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   4,   0,   0,   0,  15,   0,   0,   0,   0,   0,  16,   0,   0,   0,
      0,   0,   1,   0,   0,   1,   0,   0,   0,   0,  16,   0,   0,   0,   0,   0,
      0,   0,   0,  17,  18,   0,   0,   0,   0,   0,  19,  20,  21,   0,   0,   0,
      0,   0,   0,  22,  23,   0,   0,  24,   0,   0,   0,  25,  26,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  27,  28,  29,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  30,   0,   0,   0,   0,  31,  32,   0,  31,  33,   0,   0,
     34,   0,   0,   0,  35,   0,   0,   0,   0,  36,   0,   0,   0,   0,   0,   0,
      0,   0,  37,   0,   0,   0,   0,   0,  38,   0,  27,   0,  39,  40,  41,  42,
     37,   0,   0,  43,   0,   0,   0,   0,  44,   0,  45,  46,   0,   0,   0,   0,
      0,   0,  47,   0,   0,   0,  48,   0,   0,   0,   0,   0,   0,   0,  49,   0,
      0,   0,   0,   0,   0,   0,   0,  50,   0,   0,   0,  51,   0,   0,   0,  52,
     53,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  54,
      0,   0,  55,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  56,   0,
     45,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  57,   0,   0,   0,
      0,   0,   0,  54,   0,   0,   0,   0,   0,   0,   0,   0,  45,   0,   0,   0,
      0,  55,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  58,   0,   0,
      0,  43,   0,   0,   0,   0,   0,   0,   0,  59,  60,  61,   0,   0,   0,  57,
      0,   3,   0,   0,   0,   0,   0,  62,   0,  63,   0,   0,   0,   0,   1,   0,
      3,   0,   0,   0,   0,   0,   1,   1,   0,   0,   1,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   1,   0,   0,   0,  64,   0,  56,  65,  27,
     66,  67,  20,  68,  69,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  70,
      0,  71,  72,   0,   0,   0,  73,   0,   0,   0,   0,   0,   0,   3,   0,   0,
      0,   0,  74,  75,   0,  76,   0,  77,  78,   0,   0,   0,   0,  79,  80,  20,
      0,   0,  81,  82,  83,   0,   0,  84,   0,   0,  74,  74,   0,  85,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  86,   0,   0,   0,  87,   0,   0,   0,   0,
      0,   0,  88,  89,   0,   0,   0,   1,   0,  90,   0,   0,   0,   0,   1,  91,
      0,   0,   1,   0,   0,   0,   3,   0,   0,  92,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  93,   0,   0,  94,  95,   0,   0,   0,   0,
     20,  20,  20,  96,   0,   0,   0,   0,   0,   0,   0,   3,   0,   0,   0,   0,
      0,   0,  97,  98,   0,   0,   0,   0,   0,   0,   0,  99,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 100, 101,   0,   0,   0,   0,   0,   0,  76,   0,
    102,   0,   0,   0,   0,   0,   0,   0,  59,   0,   0,  44,   0,   0,   0, 103,
      0,  59,   0,   0,   0,   0,   0,   0,   0,  36,   0,   0, 104,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 105, 106,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  43,   0,   0,   0,   0,   0,   0,   0,  61,   0,   0,   0,
     49,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  37,   0,   0,   0,   0,
};

static RE_UINT8 re_numeric_type_stage_4[] = {
     0,  0,  0,  0,  0,  0,  1,  2,  0,  0,  3,  4,  1,  2,  0,  0,
     5,  1,  0,  0,  5,  1,  6,  7,  5,  1,  8,  0,  5,  1,  9,  0,
     5,  1,  0, 10,  0,  0,  0, 10,  5,  1, 11, 12,  1, 13, 14,  0,
     0, 15, 16, 17,  0, 18, 12,  0,  1,  2, 11,  7,  0,  0,  1, 19,
     1,  2,  1,  2,  0,  0, 20, 21, 22, 21,  0,  0,  0,  0, 11, 11,
    11, 11, 11, 11, 23,  7,  0,  0, 22, 24, 25, 26, 11, 22, 24, 14,
     0, 27, 28, 29,  0,  0, 30, 31, 22, 32, 33,  0,  0,  0,  0, 34,
    35,  0,  0,  0, 36,  7,  0,  9,  0,  0, 37,  0, 11,  7,  0,  0,
     0, 11, 36, 11,  0,  0, 36, 11, 34,  0,  0,  0, 38,  0,  0,  0,
     0, 39,  0,  0,  0, 34,  0,  0, 40, 41,  0,  0,  0, 42, 43,  0,
     0,  0,  0, 35, 12,  0,  0, 35,  0, 12,  0,  0,  0,  0, 12,  0,
    42,  0,  0,  0, 44,  0,  0,  0,  0, 45,  0,  0, 46, 42,  0,  0,
    47,  0,  0,  0,  0,  0,  0, 38,  0,  0, 41, 41,  0,  0,  0, 39,
     0,  0,  0, 18,  0, 48, 12,  0,  0,  0,  0, 44,  0, 42,  0,  0,
     0,  0, 39,  0,  0,  0, 44,  0,  0, 44, 38,  0, 41,  0,  0,  0,
    44, 42,  0,  0,  0,  0,  0, 12, 18, 11,  0,  0,  0,  0, 49,  0,
     0, 38, 38, 12,  0,  0, 50,  0, 35, 11, 11, 11, 11, 11, 14,  0,
    11, 11, 11, 12,  0, 51,  0,  0, 36, 11, 11, 14, 14,  0,  0,  0,
    41, 39,  0,  0,  0,  0, 52,  0,  0,  0,  0, 11,  0,  0,  0, 36,
    35, 11,  0,  0,  0,  0,  0, 53,  0,  0, 18, 14,  0,  0,  0, 54,
    11, 11,  8, 11, 55,  0,  0,  0,  0,  0,  0, 56,  0,  0,  0, 57,
     0, 53,  0,  0,  0, 36,  0,  0,  0,  0,  0,  8, 22, 24, 11, 10,
     0,  0, 58, 59, 60,  1,  0,  0,  0,  0,  5,  1, 36, 11, 17,  0,
     0,  0,  1, 61,  1, 13,  9,  0,  0,  0,  1, 13, 11, 17,  0,  0,
    11, 10,  0,  0,  0,  0,  1, 62,  7,  0,  0,  0, 11, 11,  7,  0,
     0,  5,  1,  1,  1,  1,  1,  1, 22, 63,  0,  0, 39,  0,  0,  0,
    38, 42,  0, 42,  0, 39,  0, 34,  0,  0,  0, 41,
};

static RE_UINT8 re_numeric_type_stage_5[] = {
    0, 0, 0, 0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0,
    0, 2, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 3, 3,
    0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0,
    1, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 0, 0, 0, 0, 0, 0, 0, 3, 3, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 1, 1, 3, 3, 2, 0, 0, 0, 0, 0,
    2, 0, 0, 0, 2, 2, 2, 2, 2, 2, 0, 0, 0, 0, 0, 0,
    2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 0, 0, 1, 1, 1,
    2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 1, 1, 1, 0, 0, 2, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 2,
    0, 0, 0, 0, 0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1,
    2, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1,
    0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0,
    0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0,
    1, 0, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0,
    0, 0, 0, 0, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 0,
    0, 1, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 1, 0, 0, 0,
    0, 0, 0, 0, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 0,
    0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0,
    0, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1,
    0, 0, 0, 0, 1, 1, 0, 0, 2, 2, 2, 2, 1, 1, 1, 1,
    0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0, 0, 1, 1, 1,
    0, 0, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 3, 3, 3, 3, 1, 1, 0, 0, 0, 0,
    3, 3, 0, 1, 1, 1, 1, 1, 2, 2, 2, 1, 1, 0, 0, 0,
};

/* Numeric_Type: 2316 bytes. */

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
     1, 56, 57, 58, 59,  1,  1,  1, 60, 61, 62, 63, 64,  1, 65,  1,
    66, 67, 54,  1,  9,  1, 68, 69, 70,  1,  1,  1, 71,  1,  1,  1,
     1,  1,  1,  1, 72,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 73, 74,  1,  1,  1,  1,
     1,  1,  1, 75,  1,  1,  1, 76,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 77, 53,  1,  1,  1,  1,  1,  1,
     1, 78,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
    79, 80,  1,  1,  1,  1,  1,  1,  1, 81, 82, 83,  1,  1,  1,  1,
     1,  1,  1, 84,  1,  1,  1,  1,  1, 85,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 86,  1,  1,  1,  1,
     1,  1, 87,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 88,  1,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_numeric_value_stage_3[] = {
      0,   1,   0,   0,   0,   2,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   3,   0,   0,   0,   1,   0,   0,   0,   0,   0,   0,   3,   0,
      0,   0,   0,   4,   0,   0,   0,   5,   0,   0,   0,   4,   0,   0,   0,   4,
      0,   0,   0,   6,   0,   0,   0,   7,   0,   0,   0,   8,   0,   0,   0,   4,
      0,   0,   9,  10,   0,   0,   0,   4,   0,   0,   1,   0,   0,   0,   1,   0,
      0,  11,   0,   0,   0,   0,   0,   0,   0,   0,   3,   0,   1,   0,   0,   0,
      0,   0,   0,  12,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  13,
      0,   0,   0,   0,   0,   0,   0,  14,   1,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   4,   0,   0,   0,  15,   0,   0,   0,   0,   0,  14,   0,   0,   0,
      0,   0,   1,   0,   0,   1,   0,   0,   0,   0,  14,   0,   0,   0,   0,   0,
      0,   0,   0,  16,   3,   0,   0,   0,   0,   0,  17,  18,  19,   0,   0,   0,
      0,   0,   0,  20,  21,   0,   0,  22,   0,   0,   0,  23,  24,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  25,  26,  27,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  28,   0,   0,   0,   0,  29,  30,   0,  29,  31,   0,   0,
     32,   0,   0,   0,  33,   0,   0,   0,   0,  34,   0,   0,   0,   0,   0,   0,
      0,   0,  35,   0,   0,   0,   0,   0,  36,   0,  37,   0,  38,  39,  40,  41,
     42,   0,   0,  43,   0,   0,   0,   0,  44,   0,  45,  46,   0,   0,   0,   0,
      0,   0,  47,   0,   0,   0,  48,   0,   0,   0,   0,   0,   0,   0,  49,   0,
      0,   0,   0,   0,   0,   0,   0,  50,   0,   0,   0,  51,   0,   0,   0,  52,
     53,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  54,
      0,   0,  55,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  56,   0,
     57,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  58,   0,   0,   0,
      0,   0,   0,  59,   0,   0,   0,   0,   0,   0,   0,   0,  60,   0,   0,   0,
      0,  61,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  62,   0,   0,
      0,  63,   0,   0,   0,   0,   0,   0,   0,  64,  65,  66,   0,   0,   0,  67,
      0,   3,   0,   0,   0,   0,   0,  68,   0,  69,   0,   0,   0,   0,   1,   0,
      3,   0,   0,   0,   0,   0,   1,   1,   0,   0,   1,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   1,   0,   0,   0,  70,   0,  71,  72,  73,
     74,  75,  76,  77,  78,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  79,
      0,  80,  81,   0,   0,   0,  82,   0,   0,   0,   0,   0,   0,   3,   0,   0,
      0,   0,  83,  84,   0,  85,   0,  86,  87,   0,   0,   0,   0,  88,  89,  90,
      0,   0,  91,  92,  93,   0,   0,  94,   0,   0,  95,  95,   0,  96,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  97,   0,   0,   0,  98,   0,   0,   0,   0,
      0,   0,  99, 100,   0,   0,   0,   1,   0, 101,   0,   0,   0,   0,   1, 102,
      0,   0,   1,   0,   0,   0,   3,   0,   0, 103,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 104,   0,   0, 105, 106,   0,   0,   0,   0,
    107, 108, 109, 110,   0,   0,   0,   0,   0,   0,   0,   3,   0,   0,   0,   0,
      0,   0, 111, 112,   0,   0,   0,   0,   0,   0,   0, 113,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 114, 115,   0,   0,   0,   0,   0,   0, 116,   0,
    117,   0,   0,   0,   0,   0,   0,   0, 118,   0,   0, 119,   0,   0,   0, 120,
      0, 121,   0,   0,   0,   0,   0,   0,   0, 122,   0,   0, 123,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 124, 125,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  63,   0,   0,   0,   0,   0,   0,   0, 126,   0,   0,   0,
    127,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 128,   0,   0,   0,   0,
      0,   0,   0,   0, 129,   0,   0,   0,
};

static RE_UINT8 re_numeric_value_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   0,
      0,   0,   0,   0,   4,   0,   5,   6,   1,   2,   3,   0,   0,   0,   0,   0,
      0,   7,   8,   9,   0,   0,   0,   0,   0,   7,   8,   9,   0,  10,  11,   0,
      0,   7,   8,   9,  12,  13,   0,   0,   0,   7,   8,   9,  14,   0,   0,   0,
      0,   7,   8,   9,   0,   0,   1,  15,   0,   0,   0,   0,   0,   0,  16,  17,
      0,   7,   8,   9,  18,  19,  20,   0,   1,   2,  21,  22,  23,   0,   0,   0,
      0,   0,  24,   2,  25,  26,  27,  28,   0,   0,   0,  29,  30,   0,   0,   0,
      1,   2,   3,   0,   1,   2,   3,   0,   0,   0,   0,   0,   1,   2,  31,   0,
      0,   0,   0,   0,  32,   2,   3,   0,   0,   0,   0,   0,  33,  34,  35,  36,
     37,  38,  39,  40,  37,  38,  39,  40,  41,  42,  43,   0,   0,   0,   0,   0,
     37,  38,  39,  44,  45,  37,  38,  39,  44,  45,  37,  38,  39,  44,  45,   0,
      0,   0,  46,  47,  48,  49,   2,  50,   0,   0,   0,   0,   0,  51,  52,  53,
     37,  38,  54,  52,  53,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  55,
      0,  56,   0,   0,   0,   0,   0,   0,  24,   2,   3,   0,   0,   0,  57,   0,
      0,   0,   0,   0,  51,  58,   0,   0,  37,  38,  59,   0,   0,   0,   0,   0,
      0,   0,  60,  61,  62,  63,  64,  65,   0,   0,   0,   0,  66,  67,  68,  69,
      0,  70,   0,   0,   0,   0,   0,   0,  71,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  72,   0,   0,   0,   0,   0,   0,   0,   0,  73,   0,   0,   0,   0,
     74,  75,  76,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  77,
      0,   0,   0,  78,   0,  79,   0,   0,   0,   0,   0,   0,   0,   0,   0,  80,
     81,   0,   0,   0,   0,   0,   0,  82,   0,   0,  83,   0,   0,   0,   0,   0,
      0,   0,   0,  70,   0,   0,   0,   0,   0,   0,   0,   0,  84,   0,   0,   0,
      0,  85,   0,   0,   0,   0,   0,   0,   0,  86,   0,   0,   0,   0,   0,   0,
      0,   0,  87,  88,   0,   0,   0,   0,  89,  90,   0,  91,   0,   0,   0,   0,
     92,  83,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  93,   0,
      0,   0,   0,   0,   5,   0,   5,   0,   0,   0,   0,   0,   0,   0,  94,   0,
      0,   0,   0,   0,   0,   0,   0,  95,   0,   0,   0,  15,  78,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  96,   0,   0,   0,  97,   0,   0,   0,   0,
      0,   0,   0,   0,  98,   0,   0,   0,   0,  98,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,  99,   0,   0,   0,   0,   0,   0,   0,   0,   0, 100,
      0, 101,   0,   0,   0,   0,   0,   0,   0,   0,   0,  28,   0,   0,   0,   0,
      0,   0,   0, 102,  71,   0,   0,   0,   0,   0,   0,   0,  78,   0,   0,   0,
    103,   0,   0,   0,   0,   0,   0,   0,   0, 104,   0,  84,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 105,   0,   0,   0,   0,   0,   0, 106,   0,   0,
      0,  51,  52, 107,   0,   0,   0,   0,   0,   0,   0,   0, 108, 109,   0,   0,
      0,   0, 110,   0, 111,   0,  78,   0,   0,   0,   0,   0, 106,   0,   0,   0,
      0,   0,   0,   0, 112,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 113,
      0, 114,   8,   9,  60,  61, 115, 116, 117, 118, 119, 120, 121,   0,   0,   0,
    122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 125, 134, 135,   0,
      0,   0, 136,   0,   0,   0,   0,   0,  24,   2,  25,  26,  27, 137, 138,   0,
    139,   0,   0,   0,   0,   0,   0,   0, 140,   0, 141,   0,   0,   0,   0,   0,
      0,   0,   0,   0, 142, 143,   0,   0,   0,   0,   0,   0,   0,   0, 144, 145,
      0,   0,   0,   0,   0,   0,  24, 146,   0, 114, 147, 148,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 114, 148,   0,   0,   0,   0,   0, 149, 150,   0,
      0,   0,   0,   0,   0,   0,   0, 151,  37,  38, 152, 153, 154, 155, 156, 157,
    158, 159, 160, 161, 162, 163, 164, 165,  37, 166,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0, 167,   0,   0,   0,   0,   0,   0,   0, 168,
      0,   0, 114, 148,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  37, 166,
      0,   0,  24, 169,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 170, 171,
     37,  38, 152, 153, 172, 155, 173, 174,   0,   0,   0,   0,  51,  52,  53, 175,
    176, 177,   8,   9,   0,   0,   0,   0,   0,   0,   0,   0,   0,   7,   8,   9,
     24,   2,  25,  26,  27, 178,   0,   0,   0,   0,   0,   0,   1,   2,  25,   0,
      1,   2,  25,  26, 179,   0,   0,   0,   0,   0,   0,   0,   1,   2, 180,  52,
     53, 175, 176,  84,   0,   0,   0,   0,   8,   9,  52, 181,  38, 182,   2, 180,
    183, 184,   9, 185, 186, 185, 187, 188, 189, 190, 191, 192, 147, 193, 194, 195,
    196, 197, 198, 199,   0,   0,   0,   0,   0,   0,   0,   0,   1,   2, 200, 201,
    202,   0,   0,   0,   0,   0,   0,   0,  37,  38, 152, 153, 203,   0,   0,   0,
      0,   0,   0,   7,   8,   9,   1,   2, 204,   8,   9,   1,   2, 204,   8,   9,
      0, 114,   8,   9,   0,   0,   0,   0, 205,  52, 107,  32,   0,   0,   0,   0,
     73,   0,   0,   0,   0,   0,   0,   0,   0, 206,   0,   0,   0,   0,   0,   0,
    101,   0,   0,   0,   0,   0,   0,   0,  70,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  94,   0,   0,   0,   0,   0, 207,   0,   0,  91,   0,   0,   0,  91,
      0,   0, 104,   0,   0,   0,   0,  76,   0,   0,   0,   0,   0,   0,  76,   0,
      0,   0,   0,   0,   0,   0,  83,   0,   0,   0,   0,   0,   0,   0, 110,   0,
      0,   0,   0, 208,   0,   0,   0,   0,   0,   0,   0,   0, 209,   0,   0,   0,
};

static RE_UINT8 re_numeric_value_stage_5[] = {
      0,   0,   0,   0,   2,  32,  34,  36,  38,  40,  42,  44,  46,  48,   0,   0,
      0,   0,  34,  36,   0,  32,   0,   0,  17,  22,  27,   0,   0,   0,   2,  32,
     34,  36,  38,  40,  42,  44,  46,  48,   7,  11,  15,  17,  27,  55,   0,   0,
      0,   0,  17,  22,  27,   7,  11,  15,  49,  94, 103,   0,  32,  34,  36,   0,
      3,   4,   5,   6,   9,  13,  16,   0,  49,  94, 103,  17,  22,  27,   7,  11,
     15,   0,   0,   0,  46,  48,  22,  33,  35,  37,  39,  41,  43,  45,  47,   1,
      0,  32,  34,  36,  46,  48,  49,  59,  69,  79,  89,  90,  91,  92,  93,  94,
    112,   0,   0,   0,   0,   0,  56,  57,  58,   0,   0,   0,  46,  48,  32,   0,
      2,   0,   0,   0,  12,  10,   9,  18,  26,  16,  20,  24,  28,  14,  29,  11,
     19,  25,  30,  32,  32,  34,  36,  38,  40,  42,  44,  46,  48,  49,  50,  51,
     89,  94,  98, 103, 103, 107, 112,   0,   0,  42,  89, 116, 121,   2,   0,   0,
     52,  53,  54,  55,  56,  57,  58,  59,   0,   0,   2,  50,  51,  52,  53,  54,
     55,  56,  57,  58,  59,  32,  34,  36,  46,  48,  49,   2,   0,   0,  32,  34,
     36,  38,  40,  42,  44,  46,  48,  49,  48,  49,  32,  34,   0,  22,   0,   0,
      0,   0,   0,   2,  49,  59,  69,   0,  36,  38,   0,   0,  48,  49,   0,   0,
     49,  59,  69,  79,  89,  90,  91,  92,   0,  60,  61,  62,  63,  64,  65,  66,
     67,  68,  69,  70,  71,  72,  73,  74,   0,  75,  76,  77,  78,  79,  80,  81,
     82,  83,  84,  85,  86,  87,  88,  89,   0,  40,   0,   0,   0,   0,   0,  34,
      0,   0,  40,   0,   0,  44,   0,   0,  32,   0,   0,  44,   0,   0,   0, 112,
      0,  36,   0,   0,   0,  48,   0,   0,  34,   0,   0,   0,  40,   0,  38,   0,
      0,   0,   0, 133,  49,   0,   0,   0,   0,   0,   0, 103,  36,   0,   0,   0,
     94,   0,   0,   0, 133,   0,   0,   0,   0,   0, 135,   0,   0,  34,   0,  46,
      0,  42,   0,   0,   0,  49,   0, 103,  59,  69,   0,   0,  79,   0,   0,   0,
      0,  36,  36,  36,   0,   0,   0,  38,   0,   0,  32,   0,   0,   0,  48,  59,
      0,   0,  49,   0,  46,   0,   0,   0,   0,   0,  44,   0,   0,   0,  48,   0,
      0,   0,  94,   0,   0,   0,  38,   0,   0,   0,  34,   0,   0, 103,   0,   0,
      0,   0,  42,   0,  42,   0,   0,   0,   0,   0,   2,   0,  44,  46,  48,   2,
     17,  22,  27,   7,  11,  15,   0,   0,   0,   0,   0,  36,   0,   0,   0,  49,
      0,  42,   0,  42,   0,  49,   0,   0,   0,   0,   0,  32,  93,  94,  95,  96,
     97,  98,  99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112,
    113, 114, 115, 116, 117, 118, 119, 120,  17,  22,  32,  40,  89,  98, 107, 116,
     40,  49,  89,  94,  98, 103, 107,  40,  49,  89,  94,  98, 103, 112, 116,  49,
     32,  32,  32,  34,  34,  34,  34,  40,  49,  49,  49,  49,  49,  69,  89,  89,
     89,  89,  94,  96,  98,  98,  98,  98,  89,  22,  22,  26,  27,   0,   0,   0,
      0,   0,   2,  17,  95,  96,  97,  98,  99, 100, 101, 102,  32,  40,  49,  89,
      0,  93,   0,   0,   0,   0, 102,   0,   0,  32,  34,  49,  59,  94,   0,   0,
     32,  34,  36,  49,  59,  94, 103, 112,  38,  40,  49,  59,  34,  36,  38,  38,
     40,  49,  59,  94,   0,   0,  32,  49,  59,  94,  34,  36,  31,  22,   0,   0,
     48,  49,  59,  69,  79,  89,  90,  91,   0,   0,  94,  95,  96,  97,  98,  99,
    100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115,
    116, 117, 118, 119, 120, 121, 122, 124, 125, 127, 128, 129, 130, 131,   8,  14,
     17,  18,  21,  22,  23,  26,  27,  29,  49,  59,  94, 103,   0,  32,  89,   0,
      0,  32,  49,  59,  38,  49,  59,  94,   0,   0,  32,  40,  49,  89,  94, 103,
     92,  93,  94,  95, 100, 101, 102,  22,  17,  18,  26,   0,  59,  69,  79,  89,
     90,  91,  92,  93,  94, 103,   2,  32, 103,   0,   0,   0,  91,  92,  93,   0,
     46,  48,  32,  34,  44,  46,  48,  38,  48,  32,  34,  36,  36,  38,  40,  34,
     36,  36,  38,  40,  32,  34,  36,  36,  38,  40, 123, 126,  38,  40,  36,  36,
     38,  38,  38,  38,  42,  44,  44,  44,  46,  46,  48,  48,  48,  48,  34,  36,
     38,  40,  42,  32,  40,  40,  34,  36,  32,  34,  18,  26,  29,  18,  26,  11,
     17,  14,  17,  17,  22,  18,  26,  79,  89,  38,  40,  42,  44,  46,  48,   0,
     46,  48,   0,  49,  94, 112, 132, 133, 134, 135,   0,   0,  92,  93,   0,   0,
     46,  48,   2,  32,   2,   2,  32,  34,  38,   0,   0,   0,   0,   0,   0,  69,
      0,  38,   0,   0,  48,   0,   0,   0,
};

/* Numeric_Value: 3264 bytes. */

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

/* Indic_Positional_Category. */

static RE_UINT8 re_indic_positional_category_stage_1[] = {
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

static RE_UINT8 re_indic_positional_category_stage_2[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  3,  4,  5,  6,  7,
     8,  0,  0,  0,  0,  0,  0,  9,  0, 10, 11, 12, 13, 14,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 15, 16, 17, 18,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 19,  0,  0,  0,  0,  0,
    20, 21, 22, 23, 24, 25, 26, 27,  0,  0,  0,  0, 28,  0,  0,  0,
};

static RE_UINT8 re_indic_positional_category_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      1,   0,   0,   2,   3,   4,   5,   0,   6,   0,   0,   7,   8,   9,   5,   0,
     10,   0,   0,   7,  11,   0,   0,  12,  10,   0,   0,   7,  13,   0,   5,   0,
      6,   0,   0,  14,  15,  16,   5,   0,  17,   0,   0,  18,  19,   9,   0,   0,
     20,   0,   0,  21,  22,  23,   5,   0,   6,   0,   0,  14,  24,  25,   5,   0,
      6,   0,   0,  18,  26,   9,   5,   0,  27,   0,   0,   0,  28,  29,   0,  27,
      0,   0,   0,  30,  31,   0,   0,   0,   0,   0,   0,  32,  33,   0,   0,   0,
      0,  34,   0,  35,   0,   0,   0,  36,  37,  38,  39,  40,  41,   0,   0,   0,
      0,   0,  42,  43,   0,  44,  45,  46,  47,  48,   0,   0,   0,   0,   0,   0,
      0,  49,   0,  49,   0,  50,   0,  50,   0,   0,   0,  51,  52,  53,   0,   0,
      0,   0,  54,  55,   0,   0,   0,   0,   0,   0,   0,  56,  57,   0,   0,   0,
      0,  58,   0,   0,   0,  59,  60,  61,   0,   0,   0,   0,   0,   0,   0,   0,
     62,   0,   0,  63,  64,   0,  65,  66,  67,   0,  68,   0,   0,   0,  69,  70,
      0,   0,  71,  72,   0,   0,   0,   0,   0,   0,   0,   0,   0,  73,  74,  75,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  76,
     77,   0,  78,   0,   0,   0,   0,   0,  79,   0,   0,  80,  81,   0,  82,  83,
      0,   0,  84,   0,  85,  70,   0,   0,   1,   0,   0,  86,  87,   0,  88,   0,
      0,   0,  89,  90,  91,   0,   0,  92,   0,   0,   0,  93,  94,   0,  95,  96,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  97,   0,
     98,   0,   0,  99,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    100,   0,   0, 101, 102,   0,   0,   0,  67,   0,   0, 103,   0,   0,   0,   0,
    104,   0, 105, 106,   0,   0,   0, 107,  67,   0,   0, 108, 109,   0,   0,   0,
      0,   0, 110, 111,   0,   0,   0,   0,   0,   0,   0,   0,   0, 112, 113,   0,
      6,   0,   0,  18, 114,   9, 115, 116,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0, 117, 118,   0,   0,   0,   0,   0,   0, 119, 120,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 121, 122, 123, 124,   0,   0,
      0,   0,   0, 125, 126,   0,   0,   0,   0,   0, 127, 128,   0,   0,   0,   0,
      0, 129, 130,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0, 121, 131,   0,   0,   0,   0,   0, 132, 133, 134,   0,   0,   0,   0,
};

static RE_UINT8 re_indic_positional_category_stage_4[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  2,  3,  4,  5,  6,  7,  1,  2,  8,  5,  9,
    10,  7,  1,  6,  0,  0,  0,  0,  0,  6,  0,  0,  0,  0,  0,  0,
    10,  8,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  3,  4,
     5,  6,  3, 11, 12, 13, 14,  0,  0,  0,  0, 15,  0,  0,  0,  0,
    10,  2,  0,  0,  0,  0,  0,  0,  5,  3,  0, 10, 16, 10, 17,  0,
     1,  0, 18,  0,  0,  0,  0,  0,  5,  6,  7, 10, 19, 15,  5,  0,
     0,  0,  0,  0,  0,  0,  3, 20,  5,  6,  3, 11, 21, 13, 22,  0,
     0,  0,  0, 19,  0,  0,  0,  0,  0, 16,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  8,  2, 23,  0, 24, 12, 25, 26,  0,
     2,  8,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,
     2,  8, 23,  1, 27,  1,  1,  0,  0,  0, 10,  3,  0,  0,  0,  0,
    28,  8, 23, 19, 29, 30,  1,  0,  0,  0, 15, 23,  0,  0,  0,  0,
     8,  5,  3, 24, 12, 25, 26,  0,  0,  8,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 16,  0, 15,  8,  1,  3,  3,  4, 31, 32, 33,
    20,  8,  1,  1,  6,  3,  0,  0, 34, 34, 35, 10,  1,  1,  1, 16,
    20,  8,  1,  1,  6, 10,  3,  0, 34, 34, 36,  0,  1,  1,  1,  0,
     0,  0,  0,  0,  6,  0,  0,  0,  0,  0, 18, 18, 10,  0,  0,  4,
    18, 37,  6, 38, 38,  1,  1,  2, 37,  1,  3,  1,  0,  0, 18,  6,
     6,  6,  6,  6, 18,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  3,  0,  0,  0,  0,  3,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 15, 20, 17, 39,  1,  1, 17, 23,  2, 18,  3,
     0,  0,  0,  8,  6,  0,  0,  6,  3,  8, 23, 15,  8,  8,  8,  0,
    10,  1, 16,  0,  0,  0,  0,  0,  0, 40, 41,  2,  8,  8,  5, 15,
     0,  0,  0,  0,  0,  8, 20,  0,  0, 17,  3,  0,  0,  0,  0,  0,
     0, 17,  0,  0,  0,  0,  0,  0,  0,  0,  0, 20,  1, 17,  6, 42,
    43, 24, 25,  2, 20,  1,  1,  1,  1, 10,  0,  0,  0,  0, 10,  0,
     1, 40, 44, 45,  2,  8,  0,  0,  8, 40,  8,  8,  5, 17,  0,  0,
     8,  8, 46, 34,  8, 35,  8,  8, 23,  0,  0,  0,  8,  0,  0,  0,
     0,  0,  0, 10, 39, 20,  0,  0,  0,  0, 11, 40,  1, 17,  6,  3,
    15,  2, 20,  1, 17,  7, 40, 24, 24, 41,  1,  1,  1,  1, 16, 18,
     1,  1, 23,  0,  0,  0,  0,  0,  0,  0,  2,  1,  6, 47, 48, 24,
    25, 19, 23,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 10,  7,  1,
     1,  1,  0,  0,  0,  0,  0,  0,  1, 23,  0,  0,  0,  0,  0,  0,
    15,  6, 17,  9,  1, 23,  6,  0,  0,  0,  0,  2,  1,  8, 20, 20,
     1,  8,  0,  0,  0,  0,  0,  0,  0,  0,  8,  4, 49,  8,  7,  1,
     1,  1, 24, 17,  0,  0,  0,  0,  1, 16, 50,  6,  6,  1,  6,  6,
     2, 51, 51, 51, 52,  0, 18,  0,  0,  0, 16,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 10,  0,  0,  0,  0,  0, 16,  0, 10,  0,  0,
     0, 15,  5,  2,  0,  0,  0,  0,  8,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  8,  8,  8,  8,  8,  8,  8,  8,  7,  0,  0,  0,  0,  0,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0, 18,  6,  0,  0,  0,  0, 18,  6, 17,  6,  7,
     0, 10,  8,  1,  6, 24,  2,  8, 53,  0,  0,  0,  0,  0,  0,  0,
     0,  0, 10,  0,  0,  0,  0,  0,  0,  0,  0,  0, 10,  1, 17, 54,
    41, 40, 55,  3,  0,  0,  0,  0,  0, 10,  0,  0,  0,  0,  2,  0,
     0,  0,  0,  0,  0, 15,  2,  0,  2,  1, 56, 57, 58, 46, 35,  1,
    10,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 11,  7,  9,
     0,  0, 15,  0,  0,  0,  0,  0,  0, 15, 20,  8, 40, 23,  5,  0,
    59,  6, 10, 52,  0,  0,  6,  7,  0,  0,  0,  0, 17,  3,  0,  0,
    20, 23,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  6,  6,
     6,  1,  1, 16,  0,  0,  0,  0,  4,  5,  7,  2,  5,  3,  0,  0,
     1, 16,  0,  0,  0,  0,  0,  0,  0,  0,  0, 10,  1,  6, 41, 38,
    17,  3, 16,  0,  0,  0,  0,  0,  0, 18,  0,  0,  0,  0,  0,  0,
     0, 15,  9,  6,  6,  6,  1, 19, 23,  0,  0,  0,  0, 10,  3,  0,
     0,  0,  0,  0,  0,  0,  8,  5,  1, 30,  2,  1,  0,  0,  0, 16,
     0,  0,  0,  0,  0,  0,  0, 10,  4,  5,  7,  1, 17,  3,  0,  0,
     2,  8, 23, 11, 12, 13, 33,  0,  0,  8,  0,  1,  1,  1, 16,  0,
     1,  1, 16,  0,  0,  0,  0,  0,  0,  0, 15,  9,  6,  6,  6,  1,
     8,  7,  2,  3,  0,  0,  0,  0,  4,  5,  6,  6, 39, 60, 33, 26,
     2,  6,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 15,
     9,  6,  6,  0, 49, 32,  1,  5,  3,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  6,  0,  8,  5,  6,  6,  7,  2, 20,  5,
    16,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 10, 20,  9,
     6,  1,  1,  5,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 18, 10,
     8,  1,  6, 41,  7,  1,  0,  0,  1,  6,  6,  3,  1,  1,  1,  5,
     0,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 15,  6,  6,  6,
    39,  7, 20, 16,  0,  0,  0,  0,
};

static RE_UINT8 re_indic_positional_category_stage_5[] = {
     0,  0,  5,  5,  5,  1,  6,  0,  1,  2,  1,  6,  6,  6,  6,  5,
     1,  1,  2,  1,  0,  5,  0,  2,  2,  0,  0,  4,  4,  6,  0,  1,
     5,  0,  5,  6,  0,  6,  5,  8,  1,  5,  9,  0, 10,  6,  1,  0,
     2,  2,  4,  4,  4,  5,  7,  0,  8,  1,  8,  0,  8,  8,  9,  2,
     4, 10,  4,  1,  3,  3,  3,  1,  3,  0,  5,  7,  7,  7,  6,  2,
     6,  1,  2,  5,  9, 10,  4,  2,  1,  8,  8,  5,  1,  3,  6, 11,
     7, 12,  2,  9, 13,  6, 13, 13, 13,  0, 11,  0,  5,  2,  2,  6,
     6,  3,  3,  5,  5,  3,  0, 13,  5,  9,
};

/* Indic_Positional_Category: 1930 bytes. */

RE_UINT32 re_get_indic_positional_category(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 13;
    code = ch ^ (f << 13);
    pos = (RE_UINT32)re_indic_positional_category_stage_1[f] << 5;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_indic_positional_category_stage_2[pos + f] << 4;
    f = code >> 4;
    code ^= f << 4;
    pos = (RE_UINT32)re_indic_positional_category_stage_3[pos + f] << 3;
    f = code >> 1;
    code ^= f << 1;
    pos = (RE_UINT32)re_indic_positional_category_stage_4[pos + f] << 1;
    value = re_indic_positional_category_stage_5[pos + code];

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
     9,  1,  1,  1,  1,  1,  1, 10,  1, 11, 12, 13, 14, 15,  1,  1,
    16,  1,  1,  1,  1, 17,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1, 18, 19, 20, 21,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 22,  1,  1,  1,  1,  1,
    23, 24, 25, 26, 27, 28, 29, 30,  1,  1,  1,  1, 31,  1,  1,  1,
};

static RE_UINT8 re_indic_syllabic_category_stage_3[] = {
      0,   0,   1,   2,   0,   0,   0,   0,   0,   0,   3,   4,   0,   5,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      6,   7,   8,   9,  10,  11,  12,  13,  14,  15,  16,  17,  18,  19,  12,  20,
     21,  15,  16,  22,  23,  24,  25,  26,  27,  28,  16,  29,  30,   0,  12,  31,
     14,  15,  16,  29,  32,  33,  12,  34,  35,  36,  37,  38,  39,  40,  25,   0,
     41,  42,  16,  43,  44,  45,  12,   0,  46,  42,  16,  47,  44,  48,  12,  49,
     46,  42,   8,  50,  51,  52,  12,  53,  54,  55,   8,  56,  57,  58,  25,  59,
     60,   8,  61,  62,  63,   2,   0,   0,  64,  65,  66,  67,  68,  69,   0,   0,
      0,   0,  70,  71,  72,   8,  73,  74,  75,  76,  77,  78,  79,   0,   0,   0,
      8,   8,  80,  81,  82,  83,  84,  85,  86,  87,   0,   0,   0,   0,   0,   0,
     88,  89,  90,  89,  90,  91,  88,  92,   8,   8,  93,  94,  95,  96,   2,   0,
     97,  61,  98,  99,  25,   8, 100, 101,   8,   8, 102, 103, 104,   2,   0,   0,
      8, 105,   8,   8, 106, 107, 108, 109,   2,   2,   0,   0,   0,   0,   0,   0,
    110,  90,   8, 111, 112,   2,   0,   0, 113,   8, 114, 115,   8,   8, 116, 117,
      8,   8, 118, 119, 120,   0,   0,   0,   0,   0,   0,   0,   0, 121, 122, 123,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 124,
    125, 126,   0,   0,   0,   0,   0, 127, 128,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 129,   0,   0,   0,
    130,   8, 131,   0,   8, 132, 133, 134, 135, 136,   8, 137, 138,   2, 139, 122,
    140,   8, 141,   8, 142, 143,   0,   0, 144,   8,   8, 145, 146,   2, 147, 148,
    149,   8, 150, 151, 152,   2,   8, 153,   8,   8,   8, 154, 155,   0, 156, 157,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 158, 159, 160,   2,
    161, 162,   8, 163, 164,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    165,  90,   8, 166, 167, 168, 169, 170, 171,   8,   8, 172,   0,   0,   0,   0,
    173,   8, 174, 175,   0, 176,   8, 177, 178, 179,   8, 180, 181,   2, 182, 183,
    184, 185, 186, 187,   0,   0,   0,   0, 188, 189, 190, 191,   8, 192, 193,   2,
    194,  15,  16,  29,  32,  40, 195, 196,   0,   0,   0,   0,   0,   0,   0,   0,
    197,   8,   8, 198, 199,   2,   0,   0, 200,   8,   8, 201, 202,   2,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0, 197,   8, 203, 204, 205, 206,   0,   0,
    197,   8,   8, 207, 208,   2,   0,   0, 191,   8, 209, 210,   2,   0,   0,   0,
      8, 211, 212, 213,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    214,   8, 203, 215, 216,  70, 217, 218,   8, 219,  76, 220,   0,   0,   0,   0,
};

static RE_UINT8 re_indic_syllabic_category_stage_4[] = {
      0,   0,   0,   0,   0,   0,   0,   1,   2,   2,   3,   0,   4,   0,   0,   0,
      5,   0,   0,   0,   0,   6,   0,   0,   7,   8,   8,   8,   8,   9,  10,  10,
     10,  10,  10,  10,  10,  10,  11,  12,  13,  13,  13,  14,  15,  16,  10,  10,
     17,  18,   2,   2,  19,   8,  10,  10,  20,  21,   8,  22,  22,   9,  10,  10,
     10,  10,  23,  10,  24,  25,  26,  12,  13,  27,  27,  28,   0,  29,   0,  30,
     26,   0,   0,   0,  20,  21,  31,  32,  23,  33,  26,  34,  35,  29,  27,  36,
      0,   0,  37,  24,   0,  18,   2,   2,  38,  39,   0,   0,  20,  21,   8,  40,
     40,   9,  10,  10,  23,  37,  26,  12,  13,  41,  41,  36,   0,   0,  42,   0,
     13,  27,  27,  36,   0,  43,   0,  30,  42,   0,   0,   0,  44,  21,  31,  19,
     45,  46,  33,  23,  47,  48,  49,  25,  10,  10,  26,  43,  35,  43,  50,  36,
      0,  29,   0,   0,   7,  21,   8,  45,  45,   9,  10,  10,  10,  10,  26,  51,
     13,  50,  50,  36,   0,  52,  49,   0,  20,  21,   8,  45,  10,  37,  26,  12,
      0,  52,   0,  53,  54,   0,   0,   0,  10,  10,  49,  51,  13,  50,  50,  55,
      0,  56,   0,  32,   0,   0,  57,  58,  59,  21,   8,   8,   8,  31,  25,  10,
     30,  10,  10,  42,  10,  49,  60,  29,  13,  61,  13,  13,  43,   0,   0,   0,
     37,  10,  10,  10,  10,  10,  10,  49,  13,  13,  62,   0,  13,  41,  63,  64,
     33,  65,  24,  42,   0,  10,  37,  10,  37,  66,  25,  33,  13,  13,  41,  67,
     13,  68,  63,  69,   2,   2,   3,  10,   2,   2,   2,   2,   2,  70,  71,   0,
     10,  10,  37,  10,  10,  10,  10,  48,  16,  13,  13,  72,  73,  74,  75,  76,
     77,  77,  78,  77,  77,  77,  77,  77,  77,  77,  77,  79,   0,  80,   0,   0,
     81,   8,  82,  13,  13,  83,  84,  85,   2,   2,   3,  86,  87,  17,  88,  89,
     90,  91,  92,  93,  94,  95,  10,  10,  96,  97,  63,  98,   2,   2,  99, 100,
    101,  10,  10,  23,  11, 102,   0,   0, 101,  10,  10,  10,  11,   0,   0,   0,
    103,   0,   0,   0, 104,   8,   8,   8,   8,  43,  13,  13,  13,  72, 105, 106,
    107,   0,   0, 108, 109,  10,  10,  10,  13,  13, 110,   0, 111, 112, 113,   0,
    114, 115, 115, 116, 117, 118,   0,   0,  10,  10,  10,   0,  13,  13,  13,  13,
    119, 112, 120,   0,  10, 121,  13,   0,  10,  10,  10,  81, 101, 122, 112, 123,
    124,  13,  13,  13,  13,  92, 125, 126, 127, 128,   8,   8,  10, 129,  13,  13,
     13, 130,  10,   0, 131,   8, 132,  10, 133,  13, 134, 135,   2,   2, 136, 137,
     10, 138,  13,  13, 139,   0,   0,   0,  10, 140,  13, 119, 112, 141,   0,   0,
      2,   2,   3,  37, 142, 143, 143, 143, 144,   0,   0,   0, 145, 146, 144,   0,
      0,   0, 147,   0,   0,   0,   0, 148, 149,   4,   0,   0,   0, 150,   0,   0,
      5, 150,   0,   0,   0,   0,   0,   4,  40, 151, 152,  10, 121,  13,   0,   0,
     10,  10,  10, 153, 154, 155, 156,  10, 157,   0,   0,   0, 158,   8,   8,   8,
    132,  10,  10,  10,  10, 159,  13,  13,  13, 160,   0,   0, 143, 143, 143, 143,
      2,   2, 161,  10, 153, 115, 162, 120,  10, 121,  13, 163, 164,   0,   0,   0,
    165,   8,   9, 101, 166,  13,  13, 167, 168,   0,   0,   0,  10, 169,  10,  10,
      2,   2, 161,  49,   8, 132,  10,  10,  10,  10,  94,  13, 170, 171,   0,   0,
    112, 112, 112, 172,  37, 173, 174,  93,  13,  13,  13,  97, 175,   0,   0,   0,
    132,  10, 121,  13,   0, 176,   0,   0,  10,  10,  10,  87, 177,  10, 178, 112,
    179,  13,  35, 180,  94,  52,   0,  72,  10,  37,  37,  10,  10,   0, 181, 182,
      2,   2,   0,   0, 183, 184,   8,   8,  10,  10,  13,  13,  13, 185,   0,   0,
    186, 187, 187, 187, 187, 188,   2,   2,   0,   0,   0, 189, 190,   8,   8,   9,
     13,  13, 191,   0, 190, 101,  10,  10,  10, 121,  13,  13, 192, 193,   2,   2,
    115, 194,  10,  10, 166,   0,   0,   0, 190,   8,   8,   8,   9,  10,  10,  10,
    121,  13,  13,  13, 195,   0, 196,  68, 197,   2,   2,   2,   2, 198,   0,   0,
      8,   8,  10,  10,  30,  10,  10,  10,  10,  10,  10,  13,  13, 199,   0, 200,
      8,  49,  23,  30,  10,  10,  10,  30,  10,  10,  48,   0,   8,   8, 132,  10,
     10,  10,  10, 152,  13,  13, 201,   0,   7,  21,   8,  22,  17, 202, 143, 146,
    143, 146,   0,   0,   8,   8,   8, 132,  10,  94,  13,  13, 203, 204,   0,   0,
     21,   8,   8, 101,  13,  13,  13, 205, 206, 207,   0,   0,  10,  10,  10, 121,
     13, 100,  13, 208, 209,   0,   0,   0,   0,   0,   8, 100,  13,  13,  13, 210,
     68,   0,   0,   0,  10,  10, 152, 211,  13, 212,   0,   0,  10,  10,  26, 213,
     13,  13, 214,   0,   2,   2,   2,   0,   8,   8,  45, 132,  13,  35,  13, 208,
    207,   0,   0,   0,   2,   2,   2, 198,  25,  10,  10,  10, 215,  77,  77,  77,
     13, 216,   0,   0,
};

static RE_UINT8 re_indic_syllabic_category_stage_5[] = {
     0,  0,  0,  0,  0, 11,  0,  0, 33, 33, 33, 33, 33, 33,  0,  0,
    11,  0,  0,  0,  0,  0, 28, 28,  0,  0,  0, 11,  1,  1,  1,  2,
     8,  8,  8,  8,  8, 12, 12, 12, 12, 12, 12, 12, 12, 12,  9,  9,
     4,  3,  9,  9,  9,  9,  9,  9,  9,  5,  9,  9,  0, 26, 26,  0,
     0,  9,  9,  9,  8,  8,  9,  9,  0,  0, 33, 33,  0,  0,  8,  8,
     0,  1,  1,  2,  0,  8,  8,  8,  8,  0,  0,  8, 12,  0, 12, 12,
    12,  0, 12,  0,  0,  0, 12, 12, 12, 12,  0,  0,  9,  0,  0,  9,
     9,  5, 13,  0,  0,  0,  0,  9, 12, 12,  0, 12,  8,  8,  8,  0,
     0,  0,  0,  8,  0, 12, 12,  0,  4,  0,  9,  9,  9,  9,  9,  0,
     9,  5,  0,  0,  0, 12, 12, 12,  1, 25, 11, 11,  0, 19,  0,  0,
     8,  8,  0,  8,  9,  9,  0,  9,  0, 12,  0,  0,  0,  0,  9,  9,
     0,  0,  1, 22,  8,  0,  8,  8,  8, 12,  0,  0,  0,  0,  0, 12,
    12,  0,  0,  0, 12, 12, 12,  0,  9,  0,  9,  9,  0,  3,  9,  9,
     0,  9,  9,  0,  0,  0, 12,  0,  0, 14, 14,  0,  9,  5, 16,  0,
    13, 13, 13,  9,  0,  0, 13, 13, 13, 13, 13, 13,  0,  0,  1,  2,
     0,  0,  5,  0,  9,  0,  9,  0,  9,  9,  6,  0, 24, 24, 24, 24,
    29,  1,  6,  0, 12,  0,  0, 12,  0, 12,  0, 12, 19, 19,  0,  0,
     9,  0,  0,  0,  0,  1,  0,  0,  0, 28,  0, 28,  0,  4,  0,  0,
     9,  9,  1,  2,  9,  9,  1,  1,  6,  3,  0,  0, 21, 21, 21, 21,
    21, 18, 18, 18, 18, 18, 18, 18,  0, 18, 18, 18, 18,  0,  0,  0,
     0,  0, 28,  0, 12,  8,  8,  8,  8,  8,  8,  9,  9,  9,  1, 24,
     2,  7,  6, 19, 19, 19, 19, 12,  0,  0, 11,  0, 12, 12,  8,  8,
     9,  9, 12, 12, 12, 12, 19, 19, 19, 12,  9, 24, 24, 12, 12,  9,
     9, 24, 24, 24, 24, 24, 12, 12, 12,  9,  9,  9,  9, 12, 12, 12,
    12, 12, 19,  9,  9,  9,  9, 24, 24, 24, 12, 24, 33, 33, 24, 24,
     9,  9,  0,  0,  8,  8,  8, 12,  6,  0,  0,  0, 12,  0,  9,  9,
    12, 12, 12,  8,  9, 27, 27, 28, 17, 29, 28, 28, 28,  6,  7, 28,
     3, 28,  0,  0, 11, 12, 12, 12,  9, 18, 18, 18, 20, 20,  1, 20,
    20, 20, 20, 20, 20, 20,  9, 28, 12, 12, 12, 10, 10, 10, 10, 10,
    10, 10,  0,  0, 23, 23, 23, 23, 23,  0,  0,  0,  9, 20, 20, 20,
    24, 24,  0,  0, 12, 12, 12,  9, 12, 19, 19, 20, 20, 20, 20,  0,
     7,  9,  9,  9, 24, 24, 28, 28, 28,  0,  0, 28,  1,  1,  1, 17,
     2,  8,  8,  8,  4,  9,  9,  9,  5, 12, 12, 12,  1, 17,  2,  8,
     8,  8, 12, 12, 12, 18, 18, 18,  9,  9,  6,  7, 18, 18, 12, 12,
    33, 33,  3, 12, 12, 12, 20, 20,  8,  8,  4,  9, 20, 20,  6,  6,
    18, 18,  9,  9,  1,  1, 28,  4, 26, 26, 26,  0, 26, 26, 26, 26,
    26, 26,  0,  0,  0,  0,  2,  2, 26,  0,  0,  0,  0,  0,  0, 28,
    30, 31,  0,  0, 11, 11, 11, 11, 28,  0,  0,  0,  8,  8,  6, 12,
    12, 12, 12,  1, 12, 12, 10, 10, 10, 10, 12, 12, 12, 12, 10, 18,
    18, 12, 12, 12, 12, 18, 12,  1,  1,  2,  8,  8, 20,  9,  9,  9,
     5,  1,  0,  0, 33, 33, 12, 12, 10, 10, 10, 24,  9,  9,  9, 20,
    20, 20, 20,  6,  1,  1, 17,  2, 12, 12, 12,  4,  9, 18, 19, 19,
     5,  0,  0,  0, 12,  9,  0, 12,  9,  9,  9, 19, 19, 19, 19,  0,
    20, 20,  0,  0, 11, 11, 11,  0,  0,  0, 12, 24, 23, 24, 23,  0,
     0,  2,  7,  0, 12,  8, 12, 12, 12, 12, 12, 20, 20, 20, 20,  9,
    24,  6,  0,  0,  4,  4,  4,  0,  0,  0,  0,  7,  1,  1,  2, 14,
    14,  8,  8,  8,  9,  9,  5,  0,  0,  0, 34, 34, 34, 34, 34, 34,
    34, 34, 33, 33,  0,  0,  0, 32,  1,  1,  2,  8,  9,  5,  4,  0,
     9,  9,  9,  7,  6,  0, 33, 33, 10, 12, 12, 12,  5,  3, 15, 15,
     0,  0,  4,  9,  0, 33, 33, 33, 33,  0,  0,  0,  1,  5,  4, 25,
     0,  0, 26,  0,  9,  4,  6,  0,  0,  0, 26, 26,  9,  9,  5,  1,
     1,  2,  4,  3,  9,  9,  9,  1,  1,  2,  5,  4,  3,  0,  0,  0,
     1,  1,  2,  5,  4,  0,  0,  0,  9,  1,  2,  5,  2,  9,  9,  9,
     9,  9,  5,  4,  0, 19, 19, 19,  9,  9,  9,  6,  0,  0, 18, 18,
     9,  1,  1,  0,
};

/* Indic_Syllabic_Category: 2560 bytes. */

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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 13, 28, 29, 30, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 31,  7, 32, 33,  7, 34, 13, 13, 13, 13, 13, 35,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_alphanumeric_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  32,  31,  31,  31,  31,  31,  31,  31,  33,  34,  35,  31,
     36,  37,  31,  31,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  38,   1,   1,   1,   1,   1,   1,   1,   1,   1,  39,
      1,   1,   1,   1,  40,   1,  41,  42,  43,  44,  45,  46,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  47,  31,  31,  31,  31,  31,  31,  31,  31,
     31,   1,  48,  49,   1,  50,  51,  52,  53,  54,  55,  56,  57,  58,   1,  59,
     60,  61,  62,  63,  64,  31,  31,  31,  65,  66,  67,  68,  69,  70,  71,  72,
     73,  31,  74,  31,  75,  31,  31,  31,   1,   1,   1,  76,  77,  78,  31,  31,
      1,   1,   1,   1,  79,  31,  31,  31,  31,  31,  31,  31,   1,   1,  80,  31,
      1,   1,  81,  82,  31,  31,  31,  83,   1,   1,   1,   1,   1,   1,   1,  84,
      1,   1,  85,  31,  31,  31,  31,  31,  86,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  87,  31,  31,  31,  31,  31,  31,  31,  88,  89,  90,  91,
     92,  31,  31,  31,  31,  31,  31,  31,  93,  94,  31,  31,  31,  31,  95,  31,
     31,  96,  31,  31,  31,  31,  31,  31,   1,   1,   1,   1,   1,   1,  97,   1,
      1,   1,   1,   1,   1,   1,   1,  98,  99,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1, 100,  31,   1,   1, 101,  31,  31,  31,  31,  31,
};

static RE_UINT8 re_alphanumeric_stage_4[] = {
      0,   1,   2,   2,   0,   3,   4,   4,   5,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5,   5,   6,   7,   0,   0,   8,   9,  10,  11,   5,  12,
      5,   5,   5,   5,  13,   5,   5,   5,   5,  14,  15,  16,  17,  18,  19,  20,
     21,   5,  22,  23,   5,   5,  24,  25,  26,   5,  27,   5,   5,  28,   5,  29,
     30,  31,  32,   0,   0,  33,  34,  35,   5,  36,  37,  38,  39,  40,  41,  42,
     43,  44,  45,  46,  47,  48,  49,  50,  51,  48,  52,  53,  54,  55,  56,  57,
     58,  59,  60,  61,  58,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,
     16,  73,  74,   0,  75,  76,  77,   0,  78,  79,  80,  81,  82,  83,   0,   0,
      5,  84,  85,  86,  87,   5,  88,  89,   5,   5,  90,   5,  91,  92,  93,   5,
     94,   5,  95,   0,  96,   5,   5,  97,  16,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,  98,   2,   5,   5,  99, 100, 101, 101, 102,   5, 103, 104,  79,
      1,   5,   5, 105,   5, 106,   5, 107, 108, 109, 110, 111,   5, 112, 113,   0,
    114,   5, 108, 115, 113, 116,   0,   0,   5, 117, 118,   0,   5, 119,   5, 120,
      5, 107, 121, 122, 123,   0,   0, 124,   5,   5,   5,   5,   5,   5,   0, 125,
     97,   5, 126, 122,   5, 127, 128, 129,   0,   0,   0, 130, 131,   0,   0,   0,
    132, 133, 134,   5, 123,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 135,   5,  79,   5, 136, 108,   5,   5,   5,   5, 137,
      5,  88,   5, 138, 139, 140, 140,   5,   0, 141,   0,   0,   0,   0,   0,   0,
    142, 143,  16,   5, 144,  16,   5,  89, 145, 146,   5,   5, 147,  73,   0,  26,
      5,   5,   5,   5,   5, 107,   0,   0,   5,   5,   5,   5,   5,   5, 107,   0,
      5,   5,   5,   5,  31,   0,  26, 122, 148, 149,   5, 150,   5,   5,   5,  96,
    151, 152,   5,   5, 153, 154,   0, 151, 155,  17,   5, 101,   5,   5, 156, 157,
      5, 106, 158,  83,   5, 159, 160, 161,   5, 139, 162, 163,   5, 108, 164, 165,
    166, 167,  89, 168,   5,   5,   5, 169,   5,   5,   5,   5,   5, 170, 171, 114,
      5,   5,   5, 172,   5,   5, 173,   0, 174, 175, 176,   5,   5,  28, 177,   5,
      5, 122,  26,   5, 178,   5,  17, 179,   0,   0,   0, 180,   5,   5,   5,  83,
      1,   2,   2, 110,   5, 108, 181,   0, 182, 183, 184,   0,   5,   5,   5,  73,
      0,   0,   5, 185,   0,   0,   0,   0,   0,   0,   0,   0,  83,   5, 186,   0,
      5,  26, 106,  73, 122,   5, 187,   0,   5,   5,   5,   5, 122,  85, 188, 114,
      5, 189,   5, 190,   0,   0,   0,   0,   5, 139, 107,  17,   0,   0,   0,   0,
    191, 192, 107, 139, 108,   0,   0, 193, 107, 173,   0,   0,   5, 194,   0,   0,
    195, 101,   0,  83,  83,   0,  80, 196,   5, 107, 107, 158,  28,   0,   0,   0,
      5,   5, 123,   0,   5, 158,   5, 158,   5,   5, 197,  57, 152,  32,  26, 198,
      5, 199,  26, 200,   5,   5, 201,   0, 202, 203,   0,   0, 204, 205,   5, 198,
     39,  48, 206, 190,   0,   0,   0,   0,   5,   5, 207,   0,   5,   5, 208,   0,
      0,   0,   0,   0,   5, 209, 210,   0,   5, 108, 211,   0,   5, 107,  79,   0,
    212, 169,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   5,   5, 213,
      0,   0,   0,   0,   0,   0,   5,  32, 214, 215, 216, 217, 178, 218,   0,   0,
      5,   5,   5,   5, 173,   0,   0,   0,   5,   5,   5, 147,   5,   5,   5,   5,
      5,   5, 190,   0,   0,   0,   0,   0,   5, 147,   0,   0,   0,   0,   0,   0,
      5,   5, 219,   0,   0,   0,   0,   0,   5,  32, 108,  79,   0,   0,  26, 220,
      5, 139, 221, 222,  96,   0,   0,   0,   5,   5, 223, 108, 177,   0,   0,  78,
      5,   5,   5,   5,   5,   5,   5,  31,   5,   5,   5,   5,   5,   5,   5, 158,
    224,   0,   0,   0,   0,   0,   0,   0,   5,   5,   5, 225, 226,   0,   0,   0,
      5,   5, 227,   5, 228, 229, 230,   5, 231, 232, 233,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5, 234, 235,  89, 227, 227, 136, 136, 214, 214, 236,   5,
    237, 238,   0,   0,   0,   0,   0,   0,   5,   5,   5,   5,   5,   5, 196,   0,
      5,   5, 239,   0,   0,   0,   0,   0, 230, 240, 241, 242, 243, 244,   0,   0,
      0,  26,  85,  85,  79,   0,   0,   0,   5,   5,   5,   5,   5,   5, 139,   0,
      5, 185,   5,   5,   5,   5,   5,   5, 122,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5, 224,   0,   0, 122,   0,   0,   0,   0,   0,   0,   0,
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
    255, 255, 255,   1, 255, 255, 223,  63,   0,   0, 240, 255, 248,   3, 255, 255,
    255, 255, 255, 239, 255, 223, 225, 255, 207, 255, 254, 255, 239, 159, 249, 255,
    255, 253, 197, 227, 159,  89, 128, 176, 207, 255,   3,   0, 238, 135, 249, 255,
    255, 253, 109, 195, 135,  25,   2,  94, 192, 255,  63,   0, 238, 191, 251, 255,
    255, 253, 237, 227, 191,  27,   1,   0, 207, 255,   0,   2, 238, 159, 249, 255,
    159,  25, 192, 176, 207, 255,   2,   0, 236, 199,  61, 214,  24, 199, 255, 195,
    199,  29, 129,   0, 192, 255,   0,   0, 239, 223, 253, 255, 255, 253, 255, 227,
    223,  29,  96,   7, 207, 255,   0,   0, 255, 253, 239, 227, 223,  29,  96,  64,
    207, 255,   6,   0, 238, 223, 253, 255, 255, 255, 255, 231, 223,  93, 240, 128,
    207, 255,   0, 252, 236, 255, 127, 252, 255, 255, 251,  47, 127, 128,  95, 255,
    192, 255,  12,   0, 255, 255, 255,   7, 127,  32, 255,   3, 150,  37, 240, 254,
    174, 236, 255,  59,  95,  32, 255, 243,   1,   0,   0,   0, 255,   3,   0,   0,
    255, 254, 255, 255, 255,  31, 254, 255,   3, 255, 255, 254, 255, 255, 255,  31,
    255, 255, 127, 249, 255,   3, 255, 255, 231, 193, 255, 255, 127,  64, 255,  51,
    191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61, 255,  61, 255, 255,
    255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255, 255, 255, 255, 135,
    255, 255,   0,   0, 255, 255,  63,  63, 255, 159, 255, 255, 255, 199, 255,   1,
    255, 223,  15,   0, 255, 255,  15,   0, 255, 223,  13,   0, 255, 255, 207, 255,
    255,   1, 128,  16, 255, 255, 255,   0, 255,   7, 255, 255, 255, 255,  63,   0,
    255, 255, 255, 127, 255,  15, 255,   1, 192, 255, 255, 255, 255,  63,  31,   0,
    255,  15, 255, 255, 255,   3, 255,   3, 255, 255, 255,  15, 254, 255,  31,   0,
    128,   0,   0,   0, 255, 255, 239, 255, 239,  15, 255,   3, 255, 243, 255, 255,
    191, 255,   3,   0, 255, 227, 255, 255, 255, 255, 255,  63, 255,   1,   0,   0,
      0, 222, 111,   0, 128, 255,  31,   0,  63,  63, 255, 170, 255, 255, 223,  95,
    220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   2, 128,   0,   0, 255,  31,
    132, 252,  47,  62,  80, 189, 255, 243, 224,  67,   0,   0,   0,   0, 192, 255,
    255, 127, 255, 255,  31, 120,  12,   0, 255, 128,   0,   0, 255, 255, 127,   0,
    127, 127, 127, 127,   0, 128,   0,   0, 224,   0,   0,   0, 254,   3,  62,  31,
    255, 255, 127, 224, 224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0,
    255,  31, 255, 255, 255,  15,   0,   0, 255, 127, 240, 143,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0, 187, 247, 255, 255,
     47,   0, 255,   3,   0,   0, 252,  40, 255, 255,   7,   0, 255, 255, 247, 255,
      0, 128, 255,   3, 223, 255, 255, 127, 255,  63, 255,   3, 255, 255, 127, 196,
      5,   0,   0,  56, 255, 255,  60,   0, 126, 126, 126,   0, 127, 127, 255, 255,
     63,   0, 255, 255, 255,   7, 255,   3,  15,   0, 255, 255, 127, 248, 255, 255,
    255,  63, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,
      0,   0, 223, 255, 252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183,
    255,  63, 255,  63, 255, 255,  31,   0, 255, 255,   1,   0,  15, 255,  62,   0,
    255, 255,  15, 255, 255,   0, 255, 255,  15,   0,   0,   0,  63, 253, 255, 255,
    255, 255, 191, 145, 255, 255,  55,   0, 255, 255, 255, 192, 111, 240, 239, 254,
     31,   0,   0,   0,  63,   0,   0,   0, 255,   1, 255,   3, 255, 255, 199, 255,
    255, 255,  71,   0,  30,   0, 255,  23, 255, 255, 251, 255, 255, 255, 159,  64,
    127, 189, 255, 191, 255,   1, 255, 255, 159,  25, 129, 224, 187,   7, 255,   3,
    179,   0, 255,   3, 255, 255,  63, 127,   0,   0,   0,  63,  17,   0, 255,   3,
    255, 255, 255, 227, 255,   3,   0, 128, 255, 253, 255, 255, 255, 255, 127, 127,
      1,   0, 255,   3,   0,   0, 252, 255, 255, 254, 127,   0, 127,   0,   0,   0,
    255,  63,   0,   0,  15,   0, 255,   3, 248, 255, 255, 224,  31,   0, 255, 255,
      3,   0,   0,   0, 255,   7, 255,  31, 255,   1, 255,  67, 255, 255, 223, 255,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    247, 207, 255, 255, 127, 255, 255, 249, 219,   7,   0,   0, 143,   0, 255,   3,
    150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15,
    238, 251, 255,  15,
};

/* Alphanumeric: 2229 bytes. */

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
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
     3,  3,  3,  3,  3, 16, 17, 18, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    20, 19, 19, 19, 19, 19, 19, 19,  3,  3,  3,  3,  3,  3,  3, 21,
     3,  3,  3,  3,  3,  3,  3, 21,
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
    35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 31,
    10, 50, 51, 31, 31, 31, 31, 31, 10, 10, 52, 31, 31, 31, 31, 31,
    31, 31, 10, 53, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 10, 54, 31, 55, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 56, 10, 57, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 58, 31, 31, 31, 31, 31, 59, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 60, 61, 62, 63, 10, 64, 31, 31,
    65, 31, 31, 31, 66, 31, 31, 67, 68, 69, 10, 70, 71, 31, 31, 31,
    10, 10, 10, 72, 10, 10, 10, 10, 10, 10, 10, 73, 74, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 75, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 10, 76, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    77, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 78,
};

static RE_UINT8 re_graph_stage_3[] = {
      0,   1,   0,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   3,   4,   2,
      2,   2,   2,   2,   5,   6,   7,   8,   9,   2,   2,   2,  10,  11,  12,  13,
     14,  15,  16,  17,   2,   2,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,   2,  40,  41,  42,
      2,   2,   2,  43,   2,   2,   2,   2,   2,  44,  45,  46,  47,  48,  49,  50,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  51,  52,  53,  54,   2,  55,
     56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,   2,  68,   2,  69,
     70,  71,  72,  73,   2,   2,   2,  74,   2,   2,   2,   2,  75,  76,  77,  78,
     79,  80,  81,  82,   2,   2,  83,   2,   2,   2,   2,   2,   2,   2,   2,   1,
     84,  85,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  86,  87,  88,
     89,  90,   2,  91,  92,  93,  94,  95,   2,  96,  97,  98,   2,   2,   2,  99,
    100, 100, 101,   2, 102,   2, 103, 104,  90,   2,   2,   1,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,  59,   2,   2,   2,   2,   2,   2,   2,   2, 105,
      2,   2, 106, 107,   2,   2,   2,   2, 108,   2,   2,  57,   2,   2, 109, 110,
    111,  57,   2, 112,   2, 113,   2, 114, 115, 116,   2, 117, 118, 119,   2, 120,
      2,   2,   2,   2,   2,   2, 104, 121,  67,  67,  67,  67,  67,  67,  67,  67,
      2, 122,   2, 123, 124, 125,   2, 126,   2,   2,   2,   2,   2, 127, 128, 129,
     49, 130,   2, 131, 100,   2,   1, 132, 133, 134,   2,  13, 135,   2, 136, 137,
     67,  67, 138, 139, 104, 140, 141, 142,   2,   2, 143, 144, 145, 146,  67,  67,
      2,   2,   2,   2, 115, 147,  67,  67, 148, 149, 150, 151, 152,  67, 153, 128,
    154, 155, 156, 157, 158, 159, 160,  67,   2,  72, 161, 162,  67,  67,  67,  67,
     67, 163,  67,  67,  67,  67,  67,  67,   2, 164,   2, 165,  77, 166,   2, 167,
    168,  67, 169, 170, 171, 172,  67,  67,   2, 173,   2, 174,  67,  67, 175, 176,
      2, 177,  57, 178, 179,  67,  67,  67,  67,  67, 180, 181,  67,  67,  67,  67,
     67,  67,  67,  52,  67,  67,  67,  67, 182, 183, 184,  67,  67,  67,  67,  67,
      2,   2,   2,   2,   2,   2, 123,  67,   2, 185,   2,   2,   2, 186,  67,  67,
    187,  67,  67,  67,  67,  67,  67,  67,   2, 188,  67,  67,  67,  67,  67,  67,
     52, 189,  67, 190,   2, 191, 192,  67,  67,  67,  67,  67,   2, 193, 194, 195,
      2,   2,   2,   2,   2,   2,   2, 196,   2,   2,   2, 161,  67,  67,  67,  67,
    197,  67,  67,  67,  67,  67,  67,  67,   2, 198, 199,  67,  67,  67,  67,  67,
      2,   2,   2,  59, 200,   2,   2, 201,   2, 202,  67,  67,   2, 203,  67,  67,
      2, 204, 205, 206, 207, 208,   2,   2,   2,   2, 209,   2,   2,   2,   2, 210,
      2,   2, 211,  67,  67,  67,  67,  67, 212,  67,  67,  67,  67,  67,  67,  67,
      2,   2,   2, 213,   2, 214,  67,  67, 215, 216, 217, 218,  67,  67,  67,  67,
     62,   2, 219, 220, 221,  62, 196, 222, 223, 224,  67,  67,   2,   2,   2,   2,
      2,   2,   2, 225,   2,  98,   2, 226,  83, 227, 228,  67, 229, 230, 231, 232,
      2,   2,   2, 233,   2,   2,   2,   2,   2,   2,   2,   2, 234,   2,   2,   2,
    235,   2,   2,   2,   2,   2,   2,   2,   2,   2, 236,  67,  67,  67,  67,  67,
    176,  67,  67,  67,  67,  67,  67,  67, 237,   2,  67,  67,   2,   2,   2, 238,
      2,   2,   2,   2,   2,   2,   2, 239,
};

static RE_UINT8 re_graph_stage_4[] = {
      0,   0,   1,   2,   2,   2,   2,   3,   2,   2,   2,   2,   2,   2,   2,   4,
      5,   2,   6,   2,   2,   2,   2,   1,   2,   7,   1,   2,   8,   1,   2,   2,
      9,   2,  10,  11,   2,  12,   2,   2,  13,   2,   2,   2,  14,   2,   2,   2,
      2,   2,   2,  15,   2,   2,   2,  10,   2,   2,  16,   3,   2,  17,   0,   0,
      0,   0,   2,  18,   0,  19,   2,   2,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  21,  22,  29,  30,  31,  32,  33,  34,   6,  22,  35,  36,  37,  26,  38,
     39,  21,  22,  35,  40,  41,  26,   9,  42,  43,  44,  45,  46,  47,  32,  10,
     48,  49,  22,  50,  51,  52,  26,  53,  48,  49,  22,  54,  51,  55,  26,  56,
     57,  49,   2,  14,  58,  19,  26,   2,  59,  60,   2,  61,  62,  63,  32,  64,
      1,   2,   2,  65,   2,  27,   0,   0,  66,  67,  68,  69,  70,  71,   0,   0,
     72,   2,  73,   1,   2,  72,   2,  12,  12,  10,   0,   0,  74,   2,   2,   2,
     75,  76,   2,   2,  75,   2,   2,  77,  78,  79,   2,   2,   2,  78,   2,   2,
      2,  14,   2,  73,   2,  80,   2,   2,   2,   2,   2,  81,   1,  73,   2,   2,
      2,   2,   2,  82,  12,  11,   2,  83,   2,  84,  12,  85,   2,  16,  80,  80,
      3,  80,   2,   2,   2,   2,   2,   9,   2,   2,  10,   2,   2,   2,   2,  33,
      2,   3,  27,  27,  86,   2,  16,  11,   2,   2,  27,   2,  80,  87,   2,   2,
      2,  88,   2,   2,   2,   3,   2,  89,  80,  80,  16,   3,   0,   0,   0,   0,
     27,   2,   2,  73,   2,   2,   2,  90,   2,   2,   2,  91,  50,   2,   2,   2,
     82,   0,   0,   0,   9,   2,   2,  92,   2,   2,   2,  93,   2,  81,   2,   2,
     81,  94,   2,  16,   2,   2,   2,  95,  95,  96,   2,  97,  98,   2,  99,   2,
      2,   3,  95, 100,   3,  73,   2,   3,   0,   2,   2,  37,  27,   2,   2,   2,
      2,   2,  83,   0,  10,   0,   2,   2,   2,   2,   2,  26,   2, 101,   2,  50,
     22,  15, 102,   0,   2,   2,   3,   2,   2,   3,   2,   2,   2,   2,   2, 103,
      2,   2,  74,   2,   2,   2, 104, 105,   2,  83, 106, 106, 106, 106,   2,   2,
     11,   0,   0,   0,   2, 107,   2,   2,   2,   2,   2,  84,   2,  33,   0,  27,
      1,   2,   2,   2,   2,   7,   2,   2, 108,   2,  16,   1,   3,   2,   2,  10,
      2,   2,  84,   2,   2,  33,   0,   0,  73,   2,   2,   2,  83,   2,   2,   2,
      2,   2,  27,   0,   2,   2,   3,   9,   0,   0,   0, 109,   2,   2,  27,  80,
    110,  80,   2,  16,   2, 111,   2,  73,  13,  45,   2,   3,   2,   2,   2,  83,
     16,  71,   2,   2, 112,  98,   2,  83, 113, 114, 106,   2,   2,   2,  33,   2,
      2,   2,  16,  80, 115,   2,   2,  27,   2,   2,  16,   2,   2,  80,   0,   0,
     83, 116,   2, 117, 118,   2,   2,   2,  15, 119,   2,   2,   0,   2,   2,   2,
      2, 120,   2,   2,   9,   0,   0,  16,   2, 121, 122,  95,   2,   2,   2,  89,
    123, 124, 106, 125, 126,   2,  79, 127,  16,  16,   0,   0, 128,   2,   2, 129,
      3,  27,  37,   0,   0,   2,   2,  16,   2,  73,   2,   2,   2,  37,   2,  27,
     10,   2,   2,  10,   2,  13,   2,   2, 130,  33,   0,   0,   2,  16,  80,   2,
      2, 130,   2,  27,   2,   2,   9,   2,   2,   2, 111,   0,   2,  33,   9,   0,
    131,   2,   2, 132,   2, 133,   2,   2,   2,   3, 109,   0,   0,   0,   2, 134,
      2, 135,   2, 136,   2,   2,   2, 137, 138, 139,   2, 140,   9,  82,   2,   2,
      2,   2,   0,   0,   2,   2, 115,  83,   2,   2,   2, 141,   2, 101,   2, 142,
      2, 143, 144,   0,   2,   2,   2, 112,   2,   2,   2, 145,   0,   0,   2,   3,
     16, 120,   2, 146,  15,   2,  82,  80,  84,   2,   2,  83,  16,   2,   1,  11,
      2,   6,   2,   3, 147,  13,  80,   2,   2,   2,  10,  80,  20,  21,  22,  35,
     40, 148, 149,  11,   2, 150,   0,   0,   9,  80,   0,   0,   2,   2,   2, 101,
      2,  16,   0,   0,  11,  80,  73,   0,  80,   0,   0,   0,   2,  50,  27,   2,
      0,   0,   2,   2,   2,   2,   2, 151,  22,   2,   2,  79,  33,   2,  73,   2,
      2, 120,  72,  83,   2,   2,   3,  11,  84,   0,   0,   0,   2,   2,   3,   0,
     83,   0,   0,   0,   2,   3,  45,   0,   0,   2,  16,  33,  33, 107,   6, 152,
      2,   0,   0,   0,  11,   2,   2,   3, 146,   2,   0,   0,   0,   0,  37,   0,
      2,   2,  73,   0,  15,   0,   0,   0,   2,   2,  10,  73,  82,  71,  84,   0,
      2,   2,   7,   2,   2,   2,  82,   0,  33,   0,   0,   0,   2,  83,   2,  15,
      2,  95,   2,   2,   2,  12, 153, 154, 155,   2,   2,   2, 156, 157,   2, 158,
    159,  49,   2,   2,   2,   2, 101,   2,  88,   2,   2,   2,  27,  98,   1,   0,
     79, 160, 161,   0, 162,  83,   0,   0,  10,  45,   0,   0, 155,   2, 163, 164,
    165, 166, 167, 168, 107,  27, 169,  27,   0,   0,   0,  15,   2,  84,   3,   1,
      1,   1,   2,  33,  73,   2,   3,   2,   0,   0,  32,   2, 112,   2,   2,  27,
     82,  15,   0,   0,   2, 112,  73,  83,   2,  11,   0,   0,   9,  80,   2,   2,
      9,   2,  16,   0,   0,   3,   9, 170,  27,   3,   0,   0,   2,  15,   0,   0,
     37,   0,   0,   0,   2,  83,   0,   0,   2,   2,   2,  11,   2,  16,   2,   2,
      2,   2,  15,   0, 171,   0,   2,   2,   2,   2,   2,   0,   2,   2,   2,  16,
};

static RE_UINT8 re_graph_stage_5[] = {
      0,   0, 254, 255, 255, 255, 255, 127, 255, 252, 240, 215, 251, 255, 127, 254,
    255, 230, 255,   0, 255,   7,  31,   0, 255, 223, 255, 191, 255, 231,   3,   0,
    255,  63, 255,  79, 223,  63, 240, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255, 255,  15, 238, 135, 109, 211, 135,  57,   2,  94,
    192, 255,  63,   0, 238, 191, 237, 243, 191,  59,   1,   0,   3,   2, 238, 159,
    159,  57, 192, 176, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0,
    239, 223, 253, 255, 255, 227, 223,  61,  96,   7,   0, 255, 239, 243,  96,  64,
      6,   0, 238, 223, 223, 253, 236, 255, 127, 252, 251,  47, 127, 132,  95, 255,
     28,   0, 255, 135, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63, 255, 243,
    255, 254, 255,  31, 191,  32, 255,  61, 127,  61,  61, 127,  61, 255, 127, 255,
    255,   3,  63,  63, 255,   1, 127,   0,  15,   0,  13,   0, 241, 255, 255, 199,
    255, 207, 255, 159,  15, 240, 255, 248, 127,   3,  63, 248, 255, 170, 223, 255,
    207, 239, 220, 127,   0, 248, 255, 124, 243, 255,  63, 255,   0, 240,  15, 254,
    255, 128,   1, 128, 127, 127, 255, 251, 224, 255, 128, 255,  63, 192,  15, 128,
      7,   0, 126, 126, 126,   0, 127, 248, 248, 224, 127,  95, 219, 255, 248, 255,
    252, 255, 247, 255, 127,  15, 252, 252, 252,  28,   0,  62, 255, 239, 255, 183,
    135, 255, 143, 255,  15, 255,  63, 253, 191, 145, 191, 255,  55, 248, 255, 143,
    255, 131, 255, 240, 111, 240, 239, 254,  15, 135,  63, 254,   7, 255,   3,  30,
      0, 254,   7, 252,   0, 128, 127, 189, 129, 224, 207,  31, 255,  43,   7, 128,
    255, 224, 100, 222, 255, 235, 239, 255, 191, 231, 223, 223, 255, 123,  95, 252,
    255, 249, 219,   7, 159, 255, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247,
    247,  94, 238, 251, 249, 127,   2,   0,
};

/* Graph: 2424 bytes. */

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
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
     3,  3,  3,  3,  3, 16, 17, 18, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19, 19,
    20, 19, 19, 19, 19, 19, 19, 19,  3,  3,  3,  3,  3,  3,  3, 21,
     3,  3,  3,  3,  3,  3,  3, 21,
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
    35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 31,
    10, 50, 51, 31, 31, 31, 31, 31, 10, 10, 52, 31, 31, 31, 31, 31,
    31, 31, 10, 53, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 10, 54, 31, 55, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 56, 10, 57, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 58, 31, 31, 31, 31, 31, 59, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 60, 61, 62, 63, 10, 64, 31, 31,
    65, 31, 31, 31, 66, 31, 31, 67, 68, 69, 10, 70, 71, 31, 31, 31,
    10, 10, 10, 72, 10, 10, 10, 10, 10, 10, 10, 73, 74, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 75, 31, 31, 31, 31, 31, 31, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 10, 76, 31, 31,
    31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    77, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31, 31,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 78,
};

static RE_UINT8 re_print_stage_3[] = {
      0,   1,   0,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   3,   4,   2,
      2,   2,   2,   2,   5,   6,   7,   8,   9,   2,   2,   2,  10,  11,  12,  13,
     14,  15,  16,  17,   2,   2,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  29,  30,  31,  32,  33,  34,  35,  36,  37,  38,  39,   2,  40,  41,  42,
      2,   2,   2,  43,   2,   2,   2,   2,   2,  44,  45,  46,  47,  48,  49,  50,
      2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  51,  52,  53,  54,   2,  55,
     56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,  67,   2,  68,   2,  69,
     70,  71,  72,  73,   2,   2,   2,  74,   2,   2,   2,   2,  75,  76,  77,  78,
     79,  80,  81,  82,   2,   2,  83,   2,   2,   2,   2,   2,   2,   2,   2,   1,
     84,  85,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,   2,  86,  87,  88,
     89,  90,   2,  91,  92,  93,  94,  95,   2,  96,  97,  98,   2,   2,   2,  99,
      2, 100, 101,   2, 102,   2, 103, 104,  90,   2,   2,   1,   2,   2,   2,   2,
      2,   2,   2,   2,   2,   2,  59,   2,   2,   2,   2,   2,   2,   2,   2, 105,
      2,   2, 106, 107,   2,   2,   2,   2, 108,   2,   2,  57,   2,   2, 109, 110,
    111,  57,   2, 112,   2, 113,   2, 114, 115, 116,   2, 117, 118, 119,   2, 120,
      2,   2,   2,   2,   2,   2, 104, 121,  67,  67,  67,  67,  67,  67,  67,  67,
      2, 122,   2, 123, 124, 125,   2, 126,   2,   2,   2,   2,   2, 127, 128, 129,
     49, 130,   2, 131, 100,   2,   1, 132, 133, 134,   2,  13, 135,   2, 136, 137,
     67,  67,  51, 138, 104, 139, 140, 141,   2,   2, 142, 143, 144, 145,  67,  67,
      2,   2,   2,   2, 115, 146,  67,  67, 147, 148, 149, 150, 151,  67, 152, 128,
    153, 154, 155, 156, 157, 158, 159,  67,   2,  72, 160, 161,  67,  67,  67,  67,
     67, 162,  67,  67,  67,  67,  67,  67,   2, 163,   2, 164,  77, 165,   2, 166,
    167,  67, 168, 169, 170, 171,  67,  67,   2, 172,   2, 173,  67,  67, 174, 175,
      2, 176,  57, 177, 178,  67,  67,  67,  67,  67,   0, 179,  67,  67,  67,  67,
     67,  67,  67,  52,  67,  67,  67,  67, 180, 181, 182,  67,  67,  67,  67,  67,
      2,   2,   2,   2,   2,   2, 123,  67,   2, 183,   2,   2,   2, 184,  67,  67,
    185,  67,  67,  67,  67,  67,  67,  67,   2, 186,  67,  67,  67,  67,  67,  67,
     52, 187,  67, 188,   2, 189, 190,  67,  67,  67,  67,  67,   2, 191, 192, 193,
      2,   2,   2,   2,   2,   2,   2, 194,   2,   2,   2, 160,  67,  67,  67,  67,
    195,  67,  67,  67,  67,  67,  67,  67,   2, 196, 197,  67,  67,  67,  67,  67,
      2,   2,   2,  59, 198,   2,   2, 199,   2, 200,  67,  67,   2, 201,  67,  67,
      2, 202, 203, 204, 205, 206,   2,   2,   2,   2, 207,   2,   2,   2,   2, 208,
      2,   2, 209,  67,  67,  67,  67,  67, 210,  67,  67,  67,  67,  67,  67,  67,
      2,   2,   2, 211,   2, 212,  67,  67, 213, 214, 215, 216,  67,  67,  67,  67,
     62,   2, 217, 218, 219,  62, 194, 220, 221, 222,  67,  67,   2,   2,   2,   2,
      2,   2,   2, 223,   2,  98,   2, 224,  83, 225, 226,  67, 227, 228, 229, 230,
      2,   2,   2, 231,   2,   2,   2,   2,   2,   2,   2,   2, 232,   2,   2,   2,
    233,   2,   2,   2,   2,   2,   2,   2,   2,   2, 234,  67,  67,  67,  67,  67,
    175,  67,  67,  67,  67,  67,  67,  67, 235,   2,  67,  67,   2,   2,   2, 236,
      2,   2,   2,   2,   2,   2,   2, 237,
};

static RE_UINT8 re_print_stage_4[] = {
      0,   0,   1,   1,   1,   1,   1,   2,   1,   1,   1,   1,   1,   1,   1,   3,
      4,   1,   5,   1,   1,   1,   1,   6,   1,   7,   6,   1,   8,   6,   1,   1,
      9,   1,  10,  11,   1,  12,   1,   1,  13,   1,   1,   1,  14,   1,   1,   1,
      1,   1,   1,  15,   1,   1,   1,  10,   1,   1,  16,   2,   1,  17,   0,   0,
      0,   0,   1,  18,   0,  19,   1,   1,  20,  21,  22,  23,  24,  25,  26,  27,
     28,  21,  22,  29,  30,  31,  32,  33,  34,   5,  22,  35,  36,  37,  26,  38,
     39,  21,  22,  35,  40,  41,  26,   9,  42,  43,  44,  45,  46,  47,  32,  10,
     48,  49,  22,  50,  51,  52,  26,  53,  48,  49,  22,  54,  51,  55,  26,  56,
     57,  49,   1,  14,  58,  19,  26,   1,  59,  60,   1,  61,  62,  63,  32,  64,
      6,   1,   1,  65,   1,  27,   0,   0,  66,  67,  68,  69,  70,  71,   0,   0,
     72,   1,  73,   6,   1,  72,   1,  12,  12,  10,   0,   0,  74,   1,   1,   1,
     75,  76,   1,   1,  75,   1,   1,  77,  78,  79,   1,   1,   1,  78,   1,   1,
      1,  14,   1,  73,   1,  80,   1,   1,   1,   1,   1,  81,   1,  73,   1,   1,
      1,   1,   1,  82,  12,  11,   1,  83,   1,  84,  12,  85,   1,  16,  80,  80,
      2,  80,   1,   1,   1,   1,   1,   9,   1,   1,  10,   1,   1,   1,   1,  33,
      1,   2,  27,  27,  86,   1,  16,  11,   1,   1,  27,   1,  80,  87,   1,   1,
      1,  88,   1,   1,   1,   2,   1,  89,  80,  80,  16,   2,   0,   0,   0,   0,
     27,   1,   1,  73,   1,   1,   1,  90,   1,   1,   1,  91,  50,   1,   1,   1,
     82,   0,   0,   0,   9,   1,   1,  92,   1,   1,   1,  93,   1,  81,   1,   1,
     81,  94,   1,  16,   1,   1,   1,  95,  95,  96,   1,  97,   1,   1,   3,   1,
      1,   1,  95,  98,   2,  73,   1,   2,   0,   1,   1,  37,  27,   1,   1,   1,
      1,   1,  83,   0,  10,   0,   1,   1,   1,   1,   1,  26,   1,  99,   1,  50,
     22,  15, 100,   0,   1,   1,   2,   1,   1,   2,   1,   1,   1,   1,   1, 101,
      1,   1,  74,   1,   1,   1, 102, 103,   1,  83, 104, 104, 104, 104,   1,   1,
     11,   0,   0,   0,   1, 105,   1,   1,   1,   1,   1,  84,   1,  33,   0,  27,
      6,   1,   1,   1,   1,   7,   1,   1, 106,   1,  16,   6,   2,   1,   1,  10,
      1,   1,  84,   1,   1,  33,   0,   0,  73,   1,   1,   1,  83,   1,   1,   1,
      1,   1,  27,   0,   1,   1,   2,   9,   0,   0,   0, 107,   1,   1,  27,  80,
    108,  80,   1,  16,   1, 109,   1,  73,  13,  45,   1,   2,   1,   1,   1,  83,
     16,  71,   1,   1, 110, 111,   1,  83, 112, 113, 104,   1,   1,   1,  33,   1,
      1,   1,  16,  80, 114,   1,   1,  27,   1,   1,  16,   1,   1,  80,   0,   0,
     83, 115,   1, 116, 117,   1,   1,   1,  15, 118,   1,   1,   0,   1,   1,   1,
      1, 119,   1,   1,   9,   0,   0,  16,   1, 120, 121,  95,   1,   1,   1,  89,
    122, 123, 104, 124, 125,   1,  79, 126,  16,  16,   0,   0, 127,   1,   1, 128,
      2,  27,  37,   0,   0,   1,   1,  16,   1,  37,   1,  27,  10,   1,   1,  10,
      1,  13,   1,   1, 129,  33,   0,   0,   1,  16,  80,   1,   1, 129,   1,  27,
      1,   1,   9,   1,   1,   1, 109,   0,   1,  33,   9,   0, 130,   1,   1, 131,
      1, 132,   1,   1,   1,   2, 107,   0,   0,   0,   1, 133,   1, 134,   1, 135,
      1,   1,   1, 136, 137, 138,   1, 139,   9,  82,   1,   1,   1,   1,   0,   0,
      1,   1, 114,  83,   1,   1,   1, 140,   1,  99,   1, 141,   1, 142, 143,   0,
      1,   1,   1, 110,   1,   1,   1, 144,   0,   0,   1,   2,  16, 119,   1, 145,
     15,   1,  82,  80,  84,   1,   1,  83,  16,   1,   6,  11,   1,   5,   1,   2,
    146,  13,  80,   1,   1,   1,  10,  80,  20,  21,  22,  35,  40, 147, 148,  11,
      1, 149,   0,   0,   9,  80,   0,   0,   1,   1,   1,  99,   1,  16,   0,   0,
     11,  80,  73,   0,  80,   0,   0,   0,   1,  50,  27,   1,   1,   1,   1, 150,
     22,   1,   1,  79,  33,   1,  73,   1,   1, 119,  72,  83,   1,   1,   2,  11,
     84,   0,   0,   0,   1,   1,   2,   0,  83,   0,   0,   0,   1,   2,  45,   0,
      0,   1,  16,  33,  33, 105,   5, 151,   1,   0,   0,   0,  11,   1,   1,   2,
    145,   1,   0,   0,   0,   0,  37,   0,   1,   1,  73,   0,  15,   0,   0,   0,
      1,   1,  10,  73,  82,  71,  84,   0,   1,   1,   7,   1,   1,   1,  82,   0,
     33,   0,   0,   0,   1,  83,   1,  15,   1,  95,   1,   1,   1,  12, 152, 153,
    154,   1,   1,   1, 155, 156,   1, 157, 158,  49,   1,   1,   1,   1,  99,   1,
     88,   1,   1,   1,  27, 111,   6,   0,  79, 159, 160,   0, 161,  83,   0,   0,
     10,  45,   0,   0, 154,   1, 162, 163, 164, 165, 166, 167, 105,  27, 168,  27,
      0,   0,   0,  15,   1,  84,   2,   6,   6,   6,   1,  33,  73,   1,   2,   1,
      0,   0,  32,   1, 110,   1,   1,  27,  82,  15,   0,   0,   1, 110,  73,  83,
      1,  11,   0,   0,   9,  80,   1,   1,   9,   1,  16,   0,   0,   2,   9, 169,
     27,   2,   0,   0,   1,  15,   0,   0,  37,   0,   0,   0,   1,  83,   0,   0,
      1,   1,   1,  11,   1,  16,   1,   1,   1,   1,  15,   0, 170,   0,   1,   1,
      1,   1,   1,   0,   1,   1,   1,  16,
};

static RE_UINT8 re_print_stage_5[] = {
      0,   0, 255, 255, 255, 127, 255, 252, 240, 215, 251, 255, 254, 255, 127, 254,
    255, 230, 255,   0, 255,   7,  31,   0, 255, 223, 255, 191, 255, 231,   3,   0,
    255,  63, 255,  79, 223,  63, 240, 255, 239, 159, 249, 255, 255, 253, 197, 243,
    159, 121, 128, 176, 207, 255, 255,  15, 238, 135, 109, 211, 135,  57,   2,  94,
    192, 255,  63,   0, 238, 191, 237, 243, 191,  59,   1,   0,   3,   2, 238, 159,
    159,  57, 192, 176, 236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0,
    239, 223, 253, 255, 255, 227, 223,  61,  96,   7,   0, 255, 239, 243,  96,  64,
      6,   0, 238, 223, 223, 253, 236, 255, 127, 252, 251,  47, 127, 132,  95, 255,
     28,   0, 255, 135, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63, 255, 243,
    255, 254, 255,  31, 191,  32, 255,  61, 127,  61,  61, 127,  61, 255, 127, 255,
    255,   3,  63,  63, 255,   1, 127,   0,  15,   0,  13,   0, 241, 255, 255, 199,
    255, 207, 255, 159,  15, 240, 255, 248, 127,   3,  63, 248, 255, 170, 223, 255,
    207, 239, 220, 127, 243, 255,  63, 255,   0, 240,  15, 254, 255, 128,   1, 128,
    127, 127, 255, 251, 224, 255, 128, 255,  63, 192,  15, 128,   7,   0,   0, 248,
    126, 126, 126,   0, 127, 248, 248, 224, 127,  95, 219, 255, 248, 255, 252, 255,
    247, 255, 127,  15, 252, 252, 252,  28,   0,  62, 255, 239, 255, 183, 135, 255,
    143, 255,  15, 255,  63, 253, 191, 145, 191, 255,  55, 248, 255, 143, 255, 131,
    255, 240, 111, 240, 239, 254,  15, 135,  63, 254,   7, 255,   3,  30,   0, 254,
      7, 252,   0, 128, 127, 189, 129, 224, 207,  31, 255,  43,   7, 128, 255, 224,
    100, 222, 255, 235, 239, 255, 191, 231, 223, 223, 255, 123,  95, 252, 255, 249,
    219,   7, 159, 255, 150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94,
    238, 251, 249, 127,   2,   0,
};

/* Print: 2414 bytes. */

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
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 28, 29, 30, 31, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 32,  7, 33, 34,  7, 35, 13, 13, 13, 13, 13, 36,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    37, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_word_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  32,  31,  31,  31,  31,  31,  31,  31,  33,  34,  35,  31,
     36,  37,  31,  31,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  38,   1,   1,   1,   1,   1,   1,   1,   1,   1,  39,
      1,   1,   1,   1,  40,   1,  41,  42,  43,  44,  45,  46,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  47,  31,  31,  31,  31,  31,  31,  31,  31,
     31,   1,  48,  49,   1,  50,  51,  52,  53,  54,  55,  56,  57,  58,   1,  59,
     60,  61,  62,  63,  64,  31,  31,  31,  65,  66,  67,  68,  69,  70,  71,  72,
     73,  31,  74,  31,  75,  31,  31,  31,   1,   1,   1,  76,  77,  78,  31,  31,
      1,   1,   1,   1,  79,  31,  31,  31,  31,  31,  31,  31,   1,   1,  80,  31,
      1,   1,  81,  82,  31,  31,  31,  83,   1,   1,   1,   1,   1,   1,   1,  84,
      1,   1,  85,  31,  31,  31,  31,  31,  86,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  87,  31,  31,  31,  31,  88,  89,  31,  90,  91,  92,  93,
     31,  31,  94,  31,  31,  31,  31,  31,  95,  31,  31,  31,  31,  31,  31,  31,
     96,  97,  31,  31,  31,  31,  98,  31,  31,  99,  31,  31,  31,  31,  31,  31,
      1,   1,   1,   1,   1,   1, 100,   1,   1,   1,   1,   1,   1,   1,   1, 101,
    102,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1, 103,  31,
      1,   1, 104,  31,  31,  31,  31,  31,  31, 105,  31,  31,  31,  31,  31,  31,
};

static RE_UINT8 re_word_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   6,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6,   6,   7,   8,   6,   6,   6,   9,  10,  11,   6,  12,
      6,   6,   6,   6,  11,   6,   6,   6,   6,  13,  14,  15,  16,  17,  18,  19,
     20,   6,   6,  21,   6,   6,  22,  23,  24,   6,  25,   6,   6,  26,   6,  27,
      6,  28,  29,   0,   0,  30,  31,  11,   6,   6,   6,  32,  33,  34,  35,  36,
     37,  38,  39,  40,  41,  42,  43,  44,  45,  42,  46,  47,  48,  49,  50,  51,
     52,  53,  54,  55,  52,  56,  57,  58,  59,  60,  61,  62,  63,  64,  65,  66,
     15,  67,  68,   0,  69,  70,  71,   0,  72,  73,  74,  75,  76,  77,  78,   0,
      6,   6,  79,   6,  80,   6,  81,  82,   6,   6,  83,   6,  84,  85,  86,   6,
     87,   6,  60,   0,  88,   6,   6,  89,  15,   6,   6,   6,   6,   6,   6,   6,
      6,   6,   6,  90,   3,   6,   6,  91,  92,  93,  94,  95,   6,   6,  96,  97,
     98,   6,   6,  99,   6, 100,   6, 101, 102, 103, 104, 105,   6, 106, 107,   0,
     29,   6, 102, 108, 107, 109,   0,   0,   6,   6, 110, 111,   6,   6,   6,  94,
      6,  99, 112,  80, 113,   0, 114, 115,   6,   6,   6,   6,   6,   6,   6, 116,
     89,   6, 117,  80,   6, 118, 119, 120, 121, 122, 123, 124, 125,   0,  24, 126,
    127, 128, 129,   6, 113,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 130,   6,  97,   6, 131, 102,   6,   6,   6,   6, 132,
      6,  81,   6, 133, 134, 135, 135,   6,   0, 136,   0,   0,   0,   0,   0,   0,
    137, 138,  15,   6, 139,  15,   6,  82, 140, 141,   6,   6, 142,  67,   0,  24,
      6,   6,   6,   6,   6, 101,   0,   0,   6,   6,   6,   6,   6,   6, 101,   0,
      6,   6,   6,   6, 143,   0,  24,  80, 144, 145,   6, 146,   6,   6,   6,  26,
    147, 148,   6,   6, 149, 150,   0, 147,   6, 151,   6,  94,   6,   6, 152, 153,
      6, 154,  94,  77,   6,   6, 155, 102,   6, 134, 156, 157,   6,   6, 158, 159,
    160, 161,  82, 162,   6,   6,   6, 163,   6,   6,   6,   6,   6, 164, 165,  29,
      6,   6,   6, 154,   6,   6, 166,   0, 167, 168, 169,   6,   6,  26, 170,   6,
      6,  80,  24,   6, 171,   6, 151, 172,  88, 173, 174, 175,   6,   6,   6,  77,
      1,   2,   3, 104,   6, 102, 176,   0, 177, 178, 179,   0,   6,   6,   6,  67,
      0,   0,   6,  93,   0,   0,   0, 180,   0,   0,   0,   0,  77,   6, 126, 181,
      6,  24, 100,  67,  80,   6, 182,   0,   6,   6,   6,   6,  80,  79, 183,  29,
      6, 184,   6, 185,   0,   0,   0,   0,   6, 134, 101, 151,   0,   0,   0,   0,
    186, 187, 101, 134, 102,   0,   0, 188, 101, 166,   0,   0,   6, 189,   0,   0,
    190, 191,   0,  77,  77,   0,  74, 192,   6, 101, 101, 193,  26,   0,   0,   0,
      6,   6, 113,   0,   6, 193,   6, 193,   6,   6, 192, 194,   6,  67,  24, 195,
      6, 196,  24, 197,   6,   6, 198,   0, 199, 200,   0,   0, 201, 202,   6, 203,
     33,  42, 204, 205,   0,   0,   0,   0,   6,   6, 203,   0,   6,   6, 206,   0,
      0,   0,   0,   0,   6, 207, 208,   0,   6,   6, 209,   0,   6,  99,  97,   0,
    210, 110,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   6,   6, 211,
      0,   0,   0,   0,   0,   0,   6, 212, 213,   5, 214, 215, 171, 216,   0,   0,
      6,   6,   6,   6, 166,   0,   0,   0,   6,   6,   6, 142,   6,   6,   6,   6,
      6,   6, 185,   0,   0,   0,   0,   0,   6, 142,   0,   0,   0,   0,   0,   0,
      6,   6, 192,   0,   0,   0,   0,   0,   6, 212, 102,  97,   0,   0,  24, 105,
      6, 134, 217, 218,  88,   0,   0,   0,   6,   6, 219, 102, 220,   0,   0, 181,
      6,   6,   6,   6,   6,   6,   6, 143,   6,   6,   6,   6,   6,   6,   6, 193,
    221,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6, 222, 223,   0,   0,   0,
      0,   0,   0, 224, 225, 226,   0,   0,   0,   0, 227,   0,   0,   0,   0,   0,
      6,   6, 196,   6, 228, 229, 230,   6, 231, 232, 233,   6,   6,   6,   6,   6,
      6,   6,   6,   6,   6, 234, 235,  82, 196, 196, 131, 131, 213, 213, 236,   6,
      6, 237,   6, 238, 239, 240,   0,   0, 241, 242,   0,   0,   0,   0,   0,   0,
      6,   6,   6,   6,   6,   6, 243,   0,   6,   6, 203,   0,   0,   0,   0,   0,
    230, 244, 245, 246, 247, 248,   0,   0,   0,  24,  79,  79,  97,   0,   0,   0,
      6,   6,   6,   6,   6,   6, 134,   0,   6,  93,   6,   6,   6,   6,   6,   6,
     80,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6, 221,   0,   0,
     80,   0,   0,   0,   0,   0,   0,   0,   6,   6,   6,   6,   6,   6,   6,  88,
};

static RE_UINT8 re_word_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255, 135, 254, 255, 255,   7,
      0,   4,  32,   4, 255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,
     31,  80,   0,   0, 255, 255, 223, 188,  64, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255, 255, 255, 254, 255, 255, 255, 127,   2, 254, 255, 255, 255,
    255,   0, 254, 255, 255, 255, 255, 191, 182,   0, 255, 255, 255,   7,   7,   0,
      0,   0, 255,   7, 255, 195, 255, 255, 255, 255, 239, 159, 255, 253, 255, 159,
      0,   0, 255, 255, 255, 231, 255, 255, 255, 255,   3,   0, 255, 255,  63,   4,
    255,  63,   0,   0, 255, 255, 255,  15, 255, 255, 223,  63,   0,   0, 240, 255,
    207, 255, 254, 255, 239, 159, 249, 255, 255, 253, 197, 243, 159, 121, 128, 176,
    207, 255,   3,   0, 238, 135, 249, 255, 255, 253, 109, 211, 135,  57,   2,  94,
    192, 255,  63,   0, 238, 191, 251, 255, 255, 253, 237, 243, 191,  59,   1,   0,
    207, 255,   0,   2, 238, 159, 249, 255, 159,  57, 192, 176, 207, 255,   2,   0,
    236, 199,  61, 214,  24, 199, 255, 195, 199,  61, 129,   0, 192, 255,   0,   0,
    239, 223, 253, 255, 255, 253, 255, 227, 223,  61,  96,   7, 207, 255,   0,   0,
    255, 253, 239, 243, 223,  61,  96,  64, 207, 255,   6,   0, 238, 223, 253, 255,
    255, 255, 255, 231, 223, 125, 240, 128, 207, 255,   0, 252, 236, 255, 127, 252,
    255, 255, 251,  47, 127, 132,  95, 255, 192, 255,  12,   0, 255, 255, 255,   7,
    255, 127, 255,   3, 150,  37, 240, 254, 174, 236, 255,  59,  95,  63, 255, 243,
      1,   0,   0,   3, 255,   3, 160, 194, 255, 254, 255, 255, 255,  31, 254, 255,
    223, 255, 255, 254, 255, 255, 255,  31,  64,   0,   0,   0, 255,   3, 255, 255,
    255, 255, 255,  63, 191,  32, 255, 255, 255, 255, 255, 247, 255,  61, 127,  61,
    255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255, 255, 255,  61, 255,
    255, 255,   0,   0, 255, 255,  63,  63, 255, 159, 255, 255, 255, 199, 255,   1,
    255, 223,  31,   0, 255, 255,  31,   0, 255, 255,  15,   0, 255, 223,  13,   0,
    255, 255, 143,  48, 255,   3,   0,   0,   0,  56, 255,   3, 255, 255, 255,   0,
    255,   7, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  15, 255,  15,
    192, 255, 255, 255, 255,  63,  31,   0, 255,  15, 255, 255, 255,   3, 255,   3,
    255, 255, 255, 159, 128,   0, 255, 127, 255,  15, 255,   3,   0, 248,  15,   0,
    255, 227, 255, 255, 255,   1,   0,   0,   0,   0, 247, 255, 255, 255, 127,   3,
    255, 255,  63, 248,  63,  63, 255, 170, 255, 255, 223,  95, 220,  31, 207,  15,
    255,  31, 220,  31,   0,  48,   0,   0,   0,   0,   0, 128,   1,   0,  16,   0,
      0,   0,   2, 128,   0,   0, 255,  31, 255, 255,   1,   0, 132, 252,  47,  62,
     80, 189, 255, 243, 224,  67,   0,   0,   0,   0, 192, 255, 255, 127, 255, 255,
     31, 248,  15,   0, 255, 128,   0, 128, 255, 255, 127,   0, 127, 127, 127, 127,
      0, 128,   0,   0, 224,   0,   0,   0, 254, 255,  62,  31, 255, 255, 127, 230,
    224, 255, 255, 255, 255,  63, 254, 255, 255, 127,   0,   0, 255,  31,   0,   0,
    255,  31, 255, 255, 255,  15,   0,   0, 255, 255, 247, 191,   0,   0, 128, 255,
    252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0, 255,   0,   0,   0,
     63,   0, 255,   3, 255, 255, 255,  40, 255,  63, 255, 255,   1, 128, 255,   3,
    255,  63, 255,   3, 255, 255, 127, 252,   7,   0,   0,  56, 255, 255, 124,   0,
    126, 126, 126,   0, 127, 127, 255, 255,  63,   0, 255, 255, 255,  55, 255,   3,
     15,   0, 255, 255, 127, 248, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224,
    255, 253, 127,  95, 219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,
      0,   0, 255,  15, 255, 255,  24,   0,   0, 224,   0,   0,   0,   0, 223, 255,
    252, 252, 252,  28, 255, 239, 255, 255, 127, 255, 255, 183, 255,  63, 255,  63,
      0,   0,   0,  32,   1,   0,   0,   0,  15, 255,  62,   0, 255, 255,  15, 255,
    255,   0, 255, 255,  15,   0,   0,   0,  63, 253, 255, 255, 255, 255, 191, 145,
    255, 255,  55,   0, 255, 255, 255, 192, 111, 240, 239, 254, 255, 255,  15, 135,
    127,   0,   0,   0, 255, 255,   7,   0, 192, 255,   0, 128, 255,   1, 255,   3,
    255, 255, 223, 255, 255, 255,  79,   0,  31,  28, 255,  23, 255, 255, 251, 255,
    255, 255, 255,  64, 127, 189, 255, 191, 255,   1, 255, 255, 255,   7, 255,   3,
    159,  57, 129, 224, 207,  31,  31,   0, 191,   0, 255,   3, 255, 255,  63, 255,
      1,   0,   0,  63,  17,   0, 255,   3, 255, 255, 255, 227, 255,   3,   0, 128,
    255, 255, 255,   1, 255, 253, 255, 255,   1,   0, 255,   3,   0,   0, 252, 255,
    255, 254, 127,   0,  15,   0, 255,   3, 248, 255, 255, 224,  31,   0, 255, 255,
      0, 128, 255, 255,   3,   0,   0,   0, 255,   7, 255,  31, 255,   1, 255,  99,
    224, 227,   7, 248, 231,  15,   0,   0,   0,  60,   0,   0,  28,   0,   0,   0,
    255, 255, 255, 223, 100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223,
    255, 255, 255, 123,  95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247,
    247, 207, 255, 255, 255, 255, 127, 248, 255,  31,  32,   0,  16,   0,   0, 248,
    254, 255,   0,   0, 127, 255, 255, 249, 219,   7,   0,   0,  31,   0, 127,   0,
    150, 254, 247,  10, 132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15,
    238, 251, 255,  15,
};

/* Word: 2310 bytes. */

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
     0,  1,  2,  3,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  5,  6,  4,  4,  4,  4,  4,  4,  4,  4,  4,  7,
     8,  4,  9, 10,  4,  4,  4,  4,  4,  4,  4,  4,  4, 11,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4, 12,  4,  4, 13,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
     4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,
};

static RE_UINT8 re_xdigit_stage_3[] = {
     0,  1,  1,  1,  1,  1,  2,  3,  1,  4,  4,  4,  4,  4,  5,  6,
     7,  1,  1,  1,  1,  1,  1,  8,  9, 10, 11, 12, 13,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  6,  1,
    14, 15, 16, 17,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1, 18,
     1,  1,  1,  1, 19,  1,  1,  1, 20, 21, 17,  1,  5,  1, 22, 23,
     8,  1,  1,  1, 16,  1,  1,  1,  1,  1, 24, 16,  1,  1,  1,  1,
     1,  1,  1,  1,  1,  1,  1, 25,  1, 16,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_xdigit_stage_4[] = {
     0,  1,  2,  2,  2,  2,  2,  2,  2,  3,  2,  0,  2,  2,  2,  4,
     2,  5,  2,  5,  2,  6,  2,  6,  3,  2,  2,  2,  2,  4,  6,  2,
     2,  2,  2,  3,  6,  2,  2,  2,  2,  7,  2,  6,  2,  2,  8,  2,
     2,  6,  0,  2,  2,  8,  2,  2,  2,  2,  2,  6,  4,  2,  2,  9,
     2,  6,  2,  2,  2,  2,  2,  0, 10, 11,  2,  2,  2,  2,  3,  2,
     2,  5,  2,  0, 12,  2,  2,  6,  2,  6,  2,  4,  0,  2,  2,  2,
     2,  3,  2,  2,  2,  2,  2, 13,
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

/* XDigit: 441 bytes. */

RE_UINT32 re_get_xdigit(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_xdigit_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_xdigit_stage_2[pos + f] << 3;
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

/* Posix_Digit. */

static RE_UINT8 re_posix_digit_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_posix_digit_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_posix_digit_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_posix_digit_stage_4[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_posix_digit_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3,   0,   0,   0,   0,   0,   0,   0,   0,
};

/* Posix_Digit: 97 bytes. */

RE_UINT32 re_get_posix_digit(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_posix_digit_stage_1[f] << 4;
    f = code >> 12;
    code ^= f << 12;
    pos = (RE_UINT32)re_posix_digit_stage_2[pos + f] << 3;
    f = code >> 9;
    code ^= f << 9;
    pos = (RE_UINT32)re_posix_digit_stage_3[pos + f] << 3;
    f = code >> 6;
    code ^= f << 6;
    pos = (RE_UINT32)re_posix_digit_stage_4[pos + f] << 6;
    pos += code;
    value = (re_posix_digit_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Posix_AlNum. */

static RE_UINT8 re_posix_alnum_stage_1[] = {
    0, 1, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3,
};

static RE_UINT8 re_posix_alnum_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  9, 10, 11,  7,  7,  7,  7, 12, 13, 13, 13, 13, 14,
    15, 16, 17, 18, 19, 13, 20, 13, 21, 13, 13, 13, 13, 22,  7,  7,
    23, 24, 13, 13, 13, 13, 25, 26, 13, 13, 27, 13, 28, 29, 30, 13,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7, 31,  7, 32, 33,  7, 34, 13, 13, 13, 13, 13, 35,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13, 13,
};

static RE_UINT8 re_posix_alnum_stage_3[] = {
      0,   1,   2,   3,   4,   5,   6,   7,   8,   9,  10,  11,  12,  13,  14,  15,
     16,   1,  17,  18,  19,   1,  20,  21,  22,  23,  24,  25,  26,  27,   1,  28,
     29,  30,  31,  31,  32,  31,  31,  31,  31,  31,  31,  31,  33,  34,  35,  31,
     36,  37,  31,  31,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,  38,   1,   1,   1,   1,   1,   1,   1,   1,   1,  39,
      1,   1,   1,   1,  40,   1,  41,  42,  43,  44,  45,  46,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1,   1,  47,  31,  31,  31,  31,  31,  31,  31,  31,
     31,   1,  48,  49,   1,  50,  51,  52,  53,  54,  55,  56,  57,  58,   1,  59,
     60,  61,  62,  63,  64,  31,  31,  31,  65,  66,  67,  68,  69,  70,  71,  72,
     73,  31,  74,  31,  75,  31,  31,  31,   1,   1,   1,  76,  77,  78,  31,  31,
      1,   1,   1,   1,  79,  31,  31,  31,  31,  31,  31,  31,   1,   1,  80,  31,
      1,   1,  81,  82,  31,  31,  31,  83,   1,   1,   1,   1,   1,   1,   1,  84,
      1,   1,  85,  31,  31,  31,  31,  31,  86,  31,  31,  31,  31,  31,  31,  31,
     31,  31,  31,  31,  87,  31,  31,  31,  31,  31,  31,  31,  88,  89,  90,  91,
     92,  31,  31,  31,  31,  31,  31,  31,  93,  94,  31,  31,  31,  31,  95,  31,
     31,  96,  31,  31,  31,  31,  31,  31,   1,   1,   1,   1,   1,   1,  97,   1,
      1,   1,   1,   1,   1,   1,   1,  98,  99,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   1,   1,   1,   1, 100,  31,   1,   1, 101,  31,  31,  31,  31,  31,
};

static RE_UINT8 re_posix_alnum_stage_4[] = {
      0,   1,   2,   2,   0,   3,   4,   4,   5,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5,   5,   6,   7,   0,   0,   8,   9,  10,  11,   5,  12,
      5,   5,   5,   5,  13,   5,   5,   5,   5,  14,  15,  16,  17,  18,  19,  20,
     21,   5,  22,  23,   5,   5,  24,  25,  26,   5,  27,   5,   5,  28,  29,  30,
     31,  32,  33,   0,   0,  34,  35,  36,   5,  37,  38,  39,  40,  41,  42,  43,
     44,  45,  46,  47,  48,  49,  50,  51,  52,  49,  53,  54,  55,  56,  57,   0,
     58,  59,  60,  61,  58,  62,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,
     16,  73,  74,   0,  75,  76,  77,   0,  78,   0,  79,  80,  81,  82,   0,   0,
      5,  83,  26,  84,  85,   5,  86,  87,   5,   5,  88,   5,  89,  90,  91,   5,
     92,   5,  93,   0,  94,   5,   5,  95,  16,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,  96,   2,   5,   5,  97,  98,  99,  99, 100,   5, 101, 102,   0,
      0,   5,   5, 103,   5, 104,   5, 105, 106, 107,  26, 108,   5, 109, 110,   0,
    111,   5, 106, 112,   0, 113,   0,   0,   5, 114, 115,   0,   5, 116,   5, 117,
      5, 105, 118, 119, 120,   0,   0, 121,   5,   5,   5,   5,   5,   5,   0, 122,
     95,   5, 123, 119,   5, 124, 125, 126,   0,   0,   0, 127, 128,   0,   0,   0,
    129, 130, 131,   5, 120,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0, 132,   5, 110,   5, 133, 106,   5,   5,   5,   5, 134,
      5,  86,   5, 135, 136, 137, 137,   5,   0, 138,   0,   0,   0,   0,   0,   0,
    139, 140,  16,   5, 141,  16,   5,  87, 142, 143,   5,   5, 144,  73,   0,  26,
      5,   5,   5,   5,   5, 105,   0,   0,   5,   5,   5,   5,   5,   5, 105,   0,
      5,   5,   5,   5,  32,   0,  26, 119, 145, 146,   5, 147,   5,   5,   5,  94,
    148, 149,   5,   5, 150, 151,   0, 148, 152,  17,   5,  99,   5,   5, 153, 154,
     29, 104, 155,  82,   5, 156, 138, 157,   5, 136, 158, 159,   5, 106, 160, 161,
    162, 163,  87, 164,   5,   5,   5, 165,   5,   5,   5,   5,   5, 166, 167, 111,
      5,   5,   5, 168,   5,   5, 169,   0, 170, 171, 172,   5,   5,  28, 173,   5,
      5, 119,  26,   5, 174,   5,  17, 175,   0,   0,   0, 176,   5,   5,   5,  82,
      0,   2,   2, 177,   5, 106, 178,   0, 179, 180, 181,   0,   5,   5,   5,  73,
      0,   0,   5, 182,   0,   0,   0,   0,   0,   0,   0,   0,  82,   5, 183,   0,
      5,  26, 104,  73, 119,   5, 184,   0,   5,   5,   5,   5, 119,  26, 185, 111,
      5, 186,   5,  61,   0,   0,   0,   0,   5, 136, 105,  17,   0,   0,   0,   0,
    187, 188, 105, 136, 106,   0,   0, 189, 105, 169,   0,   0,   5, 190,   0,   0,
    191,  99,   0,  82,  82,   0,  79, 192,   5, 105, 105, 155,  28,   0,   0,   0,
      5,   5, 120,   0,   5, 155,   5, 155,   5,   5, 193,   0, 149,  33,  26, 120,
      5, 155,  26, 194,   5,   5, 195,   0, 196, 197,   0,   0, 198, 199,   5, 120,
     40,  49, 200,  61,   0,   0,   0,   0,   5,   5, 201,   0,   5,   5, 202,   0,
      0,   0,   0,   0,   5, 203, 204,   0,   5, 106, 205,   0,   5, 105,   0,   0,
    206, 165,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   5,   5, 207,
      0,   0,   0,   0,   0,   0,   5,  33, 208, 209,  78, 210, 174, 211,   0,   0,
      5,   5,   5,   5, 169,   0,   0,   0,   5,   5,   5, 144,   5,   5,   5,   5,
      5,   5,  61,   0,   0,   0,   0,   0,   5, 144,   0,   0,   0,   0,   0,   0,
      5,   5, 212,   0,   0,   0,   0,   0,   5,  33, 106,   0,   0,   0,  26, 158,
      5, 136,  61, 213,  94,   0,   0,   0,   5,   5, 214, 106, 173,   0,   0,  78,
      5,   5,   5,   5,   5,   5,   5,  32,   5,   5,   5,   5,   5,   5,   5, 155,
    215,   0,   0,   0,   0,   0,   0,   0,   5,   5,   5, 216, 217,   0,   0,   0,
      5,   5, 218,   5, 219, 220, 221,   5, 222, 223, 224,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5, 225, 226,  87, 218, 218, 133, 133, 208, 208, 227,   0,
    228, 229,   0,   0,   0,   0,   0,   0,   5,   5,   5,   5,   5,   5, 192,   0,
      5,   5, 230,   0,   0,   0,   0,   0, 221, 231, 232, 233, 234, 235,   0,   0,
      0,  26, 236, 236, 110,   0,   0,   0,   5,   5,   5,   5,   5,   5, 136,   0,
      5, 182,   5,   5,   5,   5,   5,   5, 119,   5,   5,   5,   5,   5,   5,   5,
      5,   5,   5,   5,   5, 215,   0,   0, 119,   0,   0,   0,   0,   0,   0,   0,
};

static RE_UINT8 re_posix_alnum_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 254, 255, 255,   7,   0,   4,  32,   4,
    255, 255, 127, 255, 255, 255, 255, 255, 195, 255,   3,   0,  31,  80,   0,   0,
     32,   0,   0,   0,   0,   0, 223, 188,  64, 215, 255, 255, 251, 255, 255, 255,
    255, 255, 191, 255,   3, 252, 255, 255, 255, 255, 254, 255, 255, 255, 127,   2,
    254, 255, 255, 255, 255,   0,   0,   0,   0,   0, 255, 191, 182,   0, 255, 255,
    255,   7,   7,   0,   0,   0, 255,   7, 255, 255, 255, 254,   0, 192, 255, 255,
    255, 255, 239,  31, 254, 225,   0, 156,   0,   0, 255, 255,   0, 224, 255, 255,
    255, 255,   3,   0,   0, 252, 255, 255, 255,   7,  48,   4, 255, 255, 255, 252,
    255,  31,   0,   0, 255, 255, 255,   1, 255, 255, 223,  63,   0,   0, 240, 255,
    248,   3, 255, 255, 255, 255, 255, 239, 255, 223, 225, 255,  15,   0, 254, 255,
    239, 159, 249, 255, 255, 253, 197, 227, 159,  89, 128, 176,  15,   0,   3,   0,
    238, 135, 249, 255, 255, 253, 109, 195, 135,  25,   2,  94,   0,   0,  63,   0,
    238, 191, 251, 255, 255, 253, 237, 227, 191,  27,   1,   0,  15,   0,   0,   2,
    238, 159, 249, 255, 159,  25, 192, 176,  15,   0,   2,   0, 236, 199,  61, 214,
     24, 199, 255, 195, 199,  29, 129,   0, 239, 223, 253, 255, 255, 253, 255, 227,
    223,  29,  96,   7,  15,   0,   0,   0, 255, 253, 239, 227, 223,  29,  96,  64,
     15,   0,   6,   0, 238, 223, 253, 255, 255, 255, 255, 231, 223,  93, 240, 128,
     15,   0,   0, 252, 236, 255, 127, 252, 255, 255, 251,  47, 127, 128,  95, 255,
      0,   0,  12,   0, 255, 255, 255,   7, 127,  32,   0,   0, 150,  37, 240, 254,
    174, 236, 255,  59,  95,  32,   0, 240,   1,   0,   0,   0, 255, 254, 255, 255,
    255,  31, 254, 255,   3, 255, 255, 254, 255, 255, 255,  31, 255, 255, 127, 249,
    231, 193, 255, 255, 127,  64,   0,  48, 191,  32, 255, 255, 255, 255, 255, 247,
    255,  61, 127,  61, 255,  61, 255, 255, 255, 255,  61, 127,  61, 255, 127, 255,
    255, 255,  61, 255, 255, 255, 255, 135, 255, 255,   0,   0, 255, 255,  63,  63,
    255, 159, 255, 255, 255, 199, 255,   1, 255, 223,  15,   0, 255, 255,  15,   0,
    255, 223,  13,   0, 255, 255, 207, 255, 255,   1, 128,  16, 255, 255, 255,   0,
    255,   7, 255, 255, 255, 255,  63,   0, 255, 255, 255, 127, 255,  15, 255,   1,
    255,  63,  31,   0, 255,  15, 255, 255, 255,   3,   0,   0, 255, 255, 255,  15,
    254, 255,  31,   0, 128,   0,   0,   0, 255, 255, 239, 255, 239,  15,   0,   0,
    255, 243,   0, 252, 191, 255,   3,   0,   0, 224,   0, 252, 255, 255, 255,  63,
    255,   1,   0,   0,   0, 222, 111,   0, 128, 255,  31,   0,  63,  63, 255, 170,
    255, 255, 223,  95, 220,  31, 207,  15, 255,  31, 220,  31,   0,   0,   2, 128,
      0,   0, 255,  31, 132, 252,  47,  62,  80, 189, 255, 243, 224,  67,   0,   0,
      0,   0, 192, 255, 255, 127, 255, 255,  31, 120,  12,   0, 255, 128,   0,   0,
    255, 255, 127,   0, 127, 127, 127, 127,   0, 128,   0,   0, 224,   0,   0,   0,
    254,   3,  62,  31, 255, 255, 127, 224, 224, 255, 255, 255, 255,  63, 254, 255,
    255, 127,   0,   0, 255,  31, 255, 255,   0,  12,   0,   0, 255, 127, 240, 143,
      0,   0, 128, 255, 252, 255, 255, 255, 255, 249, 255, 255, 255, 127, 255,   0,
    187, 247, 255, 255,  47,   0,   0,   0,   0,   0, 252,  40, 255, 255,   7,   0,
    255, 255, 247, 255, 223, 255,   0, 124, 255,  63,   0,   0, 255, 255, 127, 196,
      5,   0,   0,  56, 255, 255,  60,   0, 126, 126, 126,   0, 127, 127, 255, 255,
     63,   0, 255, 255, 255,   7,   0,   0,  15,   0, 255, 255, 127, 248, 255, 255,
    255,  63, 255, 255, 255, 255, 255,   3, 127,   0, 248, 224, 255, 253, 127,  95,
    219, 255, 255, 255,   0,   0, 248, 255, 255, 255, 252, 255,   0,   0, 255,  15,
      0,   0, 223, 255, 192, 255, 255, 255, 252, 252, 252,  28, 255, 239, 255, 255,
    127, 255, 255, 183, 255,  63, 255,  63, 255, 255,  31,   0, 255, 255,   1,   0,
     15, 255,  62,   0, 255, 255,  15, 255, 255,   0, 255, 255,  63, 253, 255, 255,
    255, 255, 191, 145, 255, 255,  55,   0, 255, 255, 255, 192, 111, 240, 239, 254,
     31,   0,   0,   0,  63,   0,   0,   0, 255, 255,  71,   0,  30,   0,   0,  20,
    255, 255, 251, 255, 255, 255, 159,  64, 127, 189, 255, 191, 255,   1, 255, 255,
    159,  25, 129, 224, 187,   7,   0,   0, 179,   0,   0,   0, 255, 255,  63, 127,
      0,   0,   0,  63,  17,   0,   0,   0, 255, 255, 255, 227,   0,   0,   0, 128,
    255, 253, 255, 255, 255, 255, 127, 127,   0,   0, 252, 255, 255, 254, 127,   0,
    127,   0,   0,   0, 248, 255, 255, 224,  31,   0, 255, 255,   3,   0,   0,   0,
    255,   7, 255,  31, 255,   1, 255,  67, 255, 255, 223, 255, 255, 255, 255, 223,
    100, 222, 255, 235, 239, 255, 255, 255, 191, 231, 223, 223, 255, 255, 255, 123,
     95, 252, 253, 255,  63, 255, 255, 255, 253, 255, 255, 247, 247,  15,   0,   0,
    127, 255, 255, 249, 219,   7,   0,   0, 143,   0,   0,   0, 150, 254, 247,  10,
    132, 234, 150, 170, 150, 247, 247,  94, 255, 251, 255,  15, 238, 251, 255,  15,
    255,   3, 255, 255,
};

/* Posix_AlNum: 2197 bytes. */

RE_UINT32 re_get_posix_alnum(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_posix_alnum_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_posix_alnum_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_posix_alnum_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_posix_alnum_stage_4[pos + f] << 5;
    pos += code;
    value = (re_posix_alnum_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Posix_Punct. */

static RE_UINT8 re_posix_punct_stage_1[] = {
    0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2,
};

static RE_UINT8 re_posix_punct_stage_2[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  7,  8,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  9, 10,  7,  7,  7,  7,  7,  7,  7,  7,  7, 11,
    12, 13, 14, 15, 16,  7,  7,  7,  7,  7,  7,  7,  7, 17,  7,  7,
     7,  7,  7,  7,  7,  7,  7, 18,  7,  7, 19, 20,  7, 21, 22, 23,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
     7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,  7,
};

static RE_UINT8 re_posix_punct_stage_3[] = {
     0,  1,  2,  3,  4,  5,  6,  7,  8,  9, 10, 11, 12, 13, 14, 15,
    16,  1,  1, 17, 18,  1, 19, 20, 21, 22, 23, 24, 25,  1,  1, 26,
    27, 28, 29, 30, 31, 29, 29, 32, 29, 29, 29, 33, 34, 35, 36, 37,
    38, 39, 40, 29,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  1, 41,  1,  1,  1,  1,  1,  1, 42,  1, 43, 44,
    45, 46, 47, 48,  1,  1,  1,  1,  1,  1,  1, 49,  1, 50, 51, 52,
     1, 53,  1, 54,  1, 55,  1,  1, 56, 57, 58, 59,  1,  1,  1,  1,
    60, 61, 62,  1, 63, 64, 65, 66,  1,  1,  1,  1, 67,  1,  1,  1,
     1,  1,  1,  1, 68,  1,  1,  1,  1,  1, 69, 70,  1,  1,  1,  1,
     1,  1,  1,  1, 71,  1,  1,  1, 72, 73, 74, 75,  1,  1, 76, 77,
    29, 29, 78,  1,  1,  1,  1,  1,  1, 79,  1,  1,  1,  1, 10,  1,
    80, 81, 82, 29, 29, 29, 83, 84, 85, 86,  1,  1,  1,  1,  1,  1,
};

static RE_UINT8 re_posix_punct_stage_4[] = {
      0,   1,   2,   3,   0,   4,   5,   5,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   6,   7,   0,   0,   0,   8,   9,   0,   0,  10,
      0,   0,   0,   0,  11,   0,   0,   0,   0,   0,  12,   0,  13,  14,  15,  16,
     17,   0,   0,  18,   0,   0,  19,  20,  21,   0,   0,   0,   0,   0,   0,  22,
      0,  23,  14,   0,   0,   0,   0,   0,   0,   0,   0,  24,   0,   0,   0,  25,
      0,   0,   0,   0,   0,   0,   0,  26,   0,   0,   0,  27,   0,   0,   0,  28,
      0,   0,   0,  29,   0,   0,   0,   0,   0,   0,  30,  31,   0,   0,   0,  32,
      0,  29,  33,   0,   0,   0,   0,   0,  34,  35,   0,   0,  36,  37,  38,   0,
      0,   0,  39,   0,  37,   0,   0,  40,   0,   0,   0,  41,  42,   0,   0,   0,
     43,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  44,  45,   0,   0,  46,
      0,  47,   0,   0,   0,   0,  48,   0,  49,   0,   0,   0,   0,   0,   0,   0,
      0,   0,  50,   0,   0,   0,  37,  51,  37,   0,   0,   0,   0,  52,   0,   0,
      0,   0,  12,  53,   0,   0,   0,  54,   0,  55,   0,  37,   0,   0,  56,   0,
      0,   0,   0,   0,   0,  57,  58,  59,  60,  61,  62,  63,  64,  62,   0,   0,
     65,  66,  67,   0,  68,  51,  51,  51,  51,  51,  51,  51,  51,  51,  51,  51,
     51,  51,  51,  51,  51,  51,  51,  62,  51,  69,  49,   0,  54,  70,   0,   0,
     51,  51,  51,  70,  71,  51,  51,  51,  51,  51,  51,  72,  73,  74,  75,  76,
      0,   0,   0,   0,   0,   0,   0,  77,   0,   0,   0,  27,   0,   0,   0,   0,
     51,  78,  79,   0,  80,  51,  51,  81,  51,  51,  51,  51,  51,  51,  70,  82,
     83,  84,   0,   0,  45,  43,   0,  40,   0,   0,   0,   0,  85,   0,  51,  86,
     62,  87,  88,  51,  87,  89,  51,  62,   0,   0,   0,   0,   0,   0,  51,  51,
      0,   0,   0,   0,  60,  51,  69,  37,  90,   0,   0,  91,   0,   0,   0,  92,
     93,  94,   0,   0,  95,   0,   0,   0,   0,  96,   0,  97,   0,   0,  98,  99,
      0,  98,  29,   0,   0,   0, 100,   0,   0,   0,  54, 101,   0,   0,  37,  26,
      0,   0,  40,   0,   0,   0,   0, 102,   0, 103,   0,   0,   0, 104,  94,   0,
      0,  37,   0,   0,   0,   0,   0, 105,  42,  60, 106, 107,   0,   0,   0,   0,
      1,   2,   2, 108,   0,   0,   0, 109, 110, 111,   0, 112, 113,  43,  60, 114,
      0,   0,   0,   0,  29,   0,  27,   0,   0,   0,   0,  30,   0,   0,   0,   0,
      0,   0,   5, 115,   0,   0,   0,   0,  29,  29,   0,   0,   0,   0,   0,   0,
      0,   0, 116,  29,   0,   0, 117, 118,   0, 112,   0,   0, 119,   0,   0,   0,
      0,   0, 120,   0,   0, 121,  94,   0,   0,   0,  86, 122,   0,   0, 123,   0,
      0, 124,   0,   0,   0, 103,   0,   0,   0,   0, 125,   0,   0,   0, 126,   0,
      0,   0,   0,   0,   0,   0, 127,   0,   0,   0, 128, 129,   0,   0,   0,   0,
      0,  54,   0,   0,   0,   0,   0,   0,   0,   0, 130,  26,   0,   0,   0,   0,
      0,   0,   0, 131,   0,   0,   0,   0,   0,   0,   0,  98,   0,   0,   0, 132,
      0, 111, 133,   0,   0,   0,   0,   0,   0,   0,   0,   0, 134,   0,   0,   0,
     51,  51,  51,  51,  51,  51,  51,  70,  51, 135,  51, 136, 137, 138,  51,  41,
     51,  51, 139,   0,   0,   0,   0,   0,  51,  51,  93,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 140,  40, 132, 132,  30,  30, 103, 103, 141,   0,
      0, 142,   0, 143, 144,   0,   0,   0,   0,   0,  37,   0,   0,   0,   0,   0,
     51, 145,  51,  51,  81, 146, 147,  70,  60, 148,  39, 149,  87, 129,   0, 150,
    151, 152, 153,   0,   0,   0,   0,   0,  51,  51,  51,  51,  51,  51, 154, 155,
     51,  51,  51,  81,  51,  51, 156,   0, 145,  51, 157,  51,  61,  21,   0,   0,
     23, 158, 159,   0, 160,   0,  43,   0,
};

static RE_UINT8 re_posix_punct_stage_5[] = {
      0,   0,   0,   0, 254, 255,   0, 252,   1,   0,   0, 248,   1,   0,   0, 120,
    254, 219, 211, 137,   0,   0, 128,   0,  60,   0, 252, 255, 224, 175, 255, 255,
      0,   0,  32,  64, 176,   0,   0,   0,   0,   0,  64,   0,   4,   0,   0,   0,
      0,   0,   0, 252,   0, 230,   0,   0,   0,   0,   0,  64,  73,   0,   0,   0,
      0,   0,  24,   0, 192, 255,   0, 200,   0,  60,   0,   0,   0,   0,  16,  64,
      0,   2,   0,  96, 255,  63,   0,   0,   0,   0, 192,   3,   0,   0, 255, 127,
     48,   0,   1,   0,   0,   0,  12,  12,   0,   0,   3,   0,   0,   0,   1,   0,
      0,   0, 248,   7,   0,   0,   0, 128,   0, 128,   0,   0,   0,   0,   0,   2,
      0,   0,  16,   0,   0, 128,   0,  12, 254, 255, 255, 252,   0,   0,  80,  61,
     32,   0,   0,   0,   0,   0,   0, 192, 191, 223, 255,   7,   0, 252,   0,   0,
      0,   0,   0,   8, 255,   1,   0,   0,   0,   0, 255,   3,   1,   0,   0,   0,
      0,  96,   0,   0,   0,   0,   0,  24,   0,  56,   0,   0,   0,   0,  96,   0,
      0,   0, 112,  15, 255,   7,   0,   0,  49,   0,   0,   0, 255, 255, 255, 255,
    127,  63,   0,   0, 255,   7, 240,  31,   0,   0,   0, 240,   0,   0,   0, 248,
    255,   0,   8,   0,   0,   0,   0, 160,   3, 224,   0, 224,   0, 224,   0,  96,
      0,   0, 255, 255, 255,   0, 255, 255, 255, 255, 255, 127,   0,   0,   0, 124,
      0, 124,   0,   0, 123,   3, 208, 193, 175,  66,   0,  12,  31, 188,   0,   0,
      0,  12, 255, 255, 127,   0,   0,   0, 255, 255,  63,   0,   0,   0, 240, 255,
    255, 255, 207, 255, 255, 255,  63, 255, 255, 255, 255, 227, 255, 253,   3,   0,
      0, 240,   0,   0, 224,   7,   0, 222, 255, 127, 255, 255,  31,   0,   0,   0,
    255, 255, 255, 251, 255, 255,  15,   0,   0,   0, 255,  15,  30, 255, 255, 255,
      1,   0, 193, 224,   0,   0, 195, 255,  15,   0,   0,   0,   0, 252, 255, 255,
    255,   0,   1,   0, 255, 255,   1,   0,   0, 224,   0,   0,   0,   0,   8,  64,
      0,   0, 252,   0, 255, 255, 127,   0,   3,   0,   0,   0,   0,   6,   0,   0,
      0,  15, 192,   3,   0,   0, 240,   0,   0, 192,   0,   0,   0,   0,   0,  23,
    254,  63,   0, 192,   0,   0, 128,   3,   0,   8,   0,   0,   0,   2,   0,   0,
      0,   0, 252, 255,   0,   0,   0,  48, 255, 255, 247, 255, 127,  15,   0,   0,
     63,   0,   0,   0, 127, 127,   0,  48,   7,   0,   0,   0,   0,   0, 128, 255,
      0,   0,   0, 254, 255, 115, 255,  15, 255, 255, 255,  31,   0,   0, 128,   1,
      0,   0, 255,   1,   0,   1,   0,   0,   0,   0, 127,   0,   0,   0,   0,  30,
    128,  63,   0,   0,   0,   0,   0, 216,   0,   0,  48,   0, 224,  35,   0, 232,
      0,   0,   0,  63,   0, 248,   0,  40,  64,   0,   0,   0, 254, 255, 255,   0,
     14,   0,   0,   0, 255,  31,   0,   0,  62,   0,   0,   0,   0,   0,  31,   0,
      0,   0,  32,   0,  48,   0,   0,   0,   0,   0,   0, 144, 127, 254, 255, 255,
     31,  28,   0,   0,  24, 240, 255, 255, 255, 195, 255, 255,  35,   0,   0,   0,
      2,   0,   0,   8,   8,   0,   0,   0,   0,   0, 128,   7,   0, 224, 223, 255,
    239,  15,   0,   0, 255,  15, 255, 255, 255, 127, 254, 255, 254, 255, 254, 255,
    255, 127,   0,   0,   0,  12,   0,   0, 192, 255, 255, 255,   7,   0, 255, 255,
    255, 255, 255,  15, 255,   1,   3,   0, 255, 255,   7,   0, 255,  31, 127,   0,
    255, 255,  31,   0, 255,   0, 255,   3, 255,   0, 249, 127, 255,  15, 255, 127,
    255, 255,   3,   0,
};

/* Posix_Punct: 1645 bytes. */

RE_UINT32 re_get_posix_punct(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_posix_punct_stage_1[f] << 5;
    f = code >> 11;
    code ^= f << 11;
    pos = (RE_UINT32)re_posix_punct_stage_2[pos + f] << 3;
    f = code >> 8;
    code ^= f << 8;
    pos = (RE_UINT32)re_posix_punct_stage_3[pos + f] << 3;
    f = code >> 5;
    code ^= f << 5;
    pos = (RE_UINT32)re_posix_punct_stage_4[pos + f] << 5;
    pos += code;
    value = (re_posix_punct_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* Posix_XDigit. */

static RE_UINT8 re_posix_xdigit_stage_1[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1,
};

static RE_UINT8 re_posix_xdigit_stage_2[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_posix_xdigit_stage_3[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_posix_xdigit_stage_4[] = {
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
};

static RE_UINT8 re_posix_xdigit_stage_5[] = {
      0,   0,   0,   0,   0,   0, 255,   3, 126,   0,   0,   0, 126,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
};

/* Posix_XDigit: 97 bytes. */

RE_UINT32 re_get_posix_xdigit(RE_UINT32 ch) {
    RE_UINT32 code;
    RE_UINT32 f;
    RE_UINT32 pos;
    RE_UINT32 value;

    f = ch >> 16;
    code = ch ^ (f << 16);
    pos = (RE_UINT32)re_posix_xdigit_stage_1[f] << 3;
    f = code >> 13;
    code ^= f << 13;
    pos = (RE_UINT32)re_posix_xdigit_stage_2[pos + f] << 3;
    f = code >> 10;
    code ^= f << 10;
    pos = (RE_UINT32)re_posix_xdigit_stage_3[pos + f] << 3;
    f = code >> 7;
    code ^= f << 7;
    pos = (RE_UINT32)re_posix_xdigit_stage_4[pos + f] << 7;
    pos += code;
    value = (re_posix_xdigit_stage_5[pos >> 3] >> (pos & 0x7)) & 0x1;

    return value;
}

/* All_Cases. */

static RE_UINT8 re_all_cases_stage_1[] = {
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 2, 2, 2, 2, 6,
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
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  9, 10, 11, 12,
     6, 13,  6,  6, 14,  6,  6,  6,  6,  6,  6,  6, 15, 16,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 17, 18,  6,  6,  6, 19,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 20,  6,  6,  6, 21,
     6,  6,  6,  6, 22,  6,  6,  6,  6,  6,  6,  6, 23,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 24,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 25,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_all_cases_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   3,   4,   5,   6,   7,   8,
      0,   0,   0,   0,   0,   0,   9,   0,  10,  11,  12,  13,  14,  15,  16,  17,
     18,  18,  18,  18,  18,  18,  19,  20,  21,  22,  18,  18,  18,  18,  18,  23,
     24,  25,  26,  27,  28,  29,  30,  31,  32,  33,  21,  34,  18,  18,  35,  18,
     18,  18,  18,  18,  36,  18,  37,  38,  39,  18,  40,  41,  42,  43,  44,  45,
     46,  47,  48,  49,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  50,   0,   0,   0,   0,   0,  51,  52,
     53,  54,  55,  56,  57,  58,  59,  60,  61,  62,  63,  18,  18,  18,  64,  65,
     66,  66,  67,  68,  69,  70,  71,  72,  73,  74,  75,  75,  76,  18,  18,  18,
     77,  78,  18,  18,  18,  18,  18,  18,  79,  80,  18,  18,  18,  18,  18,  18,
     18,  18,  18,  18,  18,  18,  81,  82,  82,  82,  83,   0,  84,  85,  85,  85,
     86,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  87,  87,  87,  87,  88,  89,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  90,  90,  90,  90,  90,  90,  90,  90,  90,  90,  91,  92,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     93,  94,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  95,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  96,  18,  18,  18,
     18,  18,  97,  98,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,
     99, 100,  91,  92,  99, 100,  99, 100,  91,  92, 101, 102,  99, 100, 103, 104,
     99, 100,  99, 100,  99, 100, 105, 106, 107, 108, 109, 110, 111, 112, 107, 113,
      0,   0,   0,   0, 114, 115, 116,   0,   0, 117,   0,   0, 118, 118, 119, 119,
    120,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 121, 122, 122, 122, 123, 123, 123, 124,   0,   0,
     82,  82,  82,  82,  82,  83,  85,  85,  85,  85,  85,  86, 125, 126, 127, 128,
     18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  18,  37, 129, 130,   0,
    131, 131, 131, 131, 132, 133,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  18, 134,  18,  18,  18,  97,   0,   0,
     18,  18,  18,  37,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  78,  18,  78,  18,  18,  18,  18,  18,  18,  18,   0, 135,
     18, 136,  51,  18,  18, 137, 138,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 139,   0,   0,   0, 140, 140,
    140, 140, 140, 140, 140, 140, 140, 140,   0,   0,   0,   0,   0,   0,   0,   0,
    141,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   1,  11,  11,   4,   5,  15,  15,   8,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    142, 142, 142, 142, 142, 143, 143, 143, 143, 143,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 142, 142, 142, 142, 144, 143, 143, 143, 143, 145,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    146, 146, 146, 146, 146, 146, 147,   0, 148, 148, 148, 148, 148, 148, 149,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  11,  11,  11,  11,  15,  15,  15,  15,   0,   0,   0,   0,
    150, 150, 150, 150, 151, 152, 152, 152, 153,   0,   0,   0,   0,   0,   0,   0,
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
     53,  54,  55,  56,  57,   0,  58,  58,   0,  59,   0,  60,  61,   0,   0,   0,
     58,  62,   0,  63,   0,  64,  65,   0,  66,  67,  65,  68,  69,   0,   0,  67,
      0,  70,  71,   0,   0,  72,   0,   0,   0,   0,   0,   0,   0,  73,   0,   0,
     74,   0,   0,  74,   0,   0,   0,  75,  74,  76,  77,  77,  78,   0,   0,   0,
      0,   0,  79,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  80,  81,   0,
      0,   0,   0,   0,   0,  82,   0,   0,  14,  15,  14,  15,   0,   0,  14,  15,
      0,   0,   0,  33,  33,  33,   0,  83,   0,   0,   0,   0,   0,   0,  84,   0,
     85,  85,  85,   0,  86,   0,  87,  87,  88,   1,  89,   1,   1,  90,   1,   1,
     91,  92,  93,   1,  94,   1,   1,   1,  95,  96,   0,  97,   1,   1,  98,   1,
      1,  99,   1,   1, 100, 101, 101, 101, 102,   5, 103,   5,   5, 104,   5,   5,
    105, 106, 107,   5, 108,   5,   5,   5, 109, 110, 111, 112,   5,   5, 113,   5,
      5, 114,   5,   5, 115, 116, 116, 117, 118, 119,   0,   0,   0, 120, 121, 122,
    123, 124, 125, 126, 127, 128,   0,  14,  15, 129,  14,  15,   0,  45,  45,  45,
    130, 130, 130, 130, 130, 130, 130, 130,   1,   1, 131,   1, 132,   1,   1,   1,
      1,   1,   1,   1,   1,   1, 133,   1,   1, 134, 135,   1,   1,   1,   1,   1,
      1,   1, 136,   1,   1,   1,   1,   1,   5,   5, 137,   5, 138,   5,   5,   5,
      5,   5,   5,   5,   5,   5, 139,   5,   5, 140, 141,   5,   5,   5,   5,   5,
      5,   5, 142,   5,   5,   5,   5,   5, 143, 143, 143, 143, 143, 143, 143, 143,
     14,  15, 144, 145,  14,  15,  14,  15,  14,  15,   0,   0,   0,   0,   0,   0,
      0,   0,  14,  15,  14,  15,  14,  15, 146,  14,  15,  14,  15,  14,  15,  14,
     15,  14,  15,  14,  15,  14,  15, 147,   0, 148, 148, 148, 148, 148, 148, 148,
    148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148, 148,   0,
      0, 149, 149, 149, 149, 149, 149, 149, 149, 149, 149, 149, 149, 149, 149, 149,
    149, 149, 149, 149, 149, 149, 149,   0, 150, 150, 150, 150, 150, 150, 150, 150,
    150, 150, 150, 150, 150, 150,   0, 150,   0,   0,   0,   0,   0, 150,   0,   0,
    151, 151, 151, 151, 151, 151, 151, 151, 117, 117, 117, 117, 117, 117,   0,   0,
    122, 122, 122, 122, 122, 122,   0,   0, 152, 153, 154, 155, 156, 157, 158, 159,
    160,   0,   0,   0,   0,   0,   0,   0,   0, 161,   0,   0,   0, 162,   0,   0,
    163, 164,  14,  15,  14,  15,  14,  15,  14,  15,  14,  15,  14,  15,   0,   0,
      0,   0,   0, 165,   0,   0, 166,   0, 117, 117, 117, 117, 117, 117, 117, 117,
    122, 122, 122, 122, 122, 122, 122, 122,   0, 117,   0, 117,   0, 117,   0, 117,
      0, 122,   0, 122,   0, 122,   0, 122, 167, 167, 168, 168, 168, 168, 169, 169,
    170, 170, 171, 171, 172, 172,   0,   0, 117, 117,   0, 173,   0,   0,   0,   0,
    122, 122, 174, 174, 175,   0, 176,   0,   0,   0,   0, 173,   0,   0,   0,   0,
    177, 177, 177, 177, 175,   0,   0,   0, 117, 117,   0, 178,   0,   0,   0,   0,
    122, 122, 179, 179,   0,   0,   0,   0, 117, 117,   0, 180,   0, 125,   0,   0,
    122, 122, 181, 181, 129,   0,   0,   0, 182, 182, 183, 183, 175,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 184,   0,   0,   0, 185, 186,   0,   0,   0,   0,
      0,   0, 187,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 188,   0,
    189, 189, 189, 189, 189, 189, 189, 189, 190, 190, 190, 190, 190, 190, 190, 190,
      0,   0,   0,  14,  15,   0,   0,   0,   0,   0,   0,   0,   0,   0, 191, 191,
    191, 191, 191, 191, 191, 191, 191, 191, 192, 192, 192, 192, 192, 192, 192, 192,
    192, 192,   0,   0,   0,   0,   0,   0,  14,  15, 193, 194, 195, 196, 197,  14,
     15,  14,  15,  14,  15, 198, 199, 200, 201,   0,  14,  15,   0,  14,  15,   0,
      0,   0,   0,   0,   0,   0, 202, 202,   0,   0,   0,  14,  15,  14,  15,   0,
      0,   0,  14,  15,   0,   0,   0,   0, 203, 203, 203, 203, 203, 203, 203, 203,
    203, 203, 203, 203, 203, 203,   0, 203,   0,   0,   0,   0,   0, 203,   0,   0,
     14,  15, 204, 205,  14,  15,  14,  15,   0,  14,  15,  14,  15, 206,  14,  15,
      0,   0,   0,  14,  15, 207,   0,   0,  14,  15, 208, 209, 210, 211, 208,   0,
    212, 213, 214, 215,  14,  15,  14,  15,   0,   0,   0, 216,   0,   0,   0,   0,
    217, 217, 217, 217, 217, 217, 217, 217,   0,   0,   0,   0,   0,  14,  15,   0,
    218, 218, 218, 218, 218, 218, 218, 218, 219, 219, 219, 219, 219, 219, 219, 219,
    218, 218, 218, 218,   0,   0,   0,   0, 219, 219, 219, 219,   0,   0,   0,   0,
     86,  86,  86,  86,  86,  86,  86,  86,  86,  86,  86,   0,   0,   0,   0,   0,
    115, 115, 115, 115, 115, 115, 115, 115, 115, 115, 115,   0,   0,   0,   0,   0,
    220, 220, 220, 220, 220, 220, 220, 220, 220, 220, 221, 221, 221, 221, 221, 221,
    221, 221, 221, 221, 221, 221, 221, 221, 221, 221, 221, 221,   0,   0,   0,   0,
};

/* All_Cases: 2424 bytes. */

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
    {{ 42319,     0,     0}},
    {{ 42315,     0,     0}},
    {{  -207,     0,     0}},
    {{ 42280,     0,     0}},
    {{ 42308,     0,     0}},
    {{  -209,     0,     0}},
    {{  -211,     0,     0}},
    {{ 10743,     0,     0}},
    {{ 42305,     0,     0}},
    {{ 10749,     0,     0}},
    {{  -213,     0,     0}},
    {{  -214,     0,     0}},
    {{ 10727,     0,     0}},
    {{  -218,     0,     0}},
    {{ 42282,     0,     0}},
    {{   -69,     0,     0}},
    {{  -217,     0,     0}},
    {{   -71,     0,     0}},
    {{  -219,     0,     0}},
    {{ 42261,     0,     0}},
    {{ 42258,     0,     0}},
    {{    84,   116,  7289}},
    {{   116,     0,     0}},
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
    {{  -116,     0,     0}},
    {{   -92,   -60,   -35}},
    {{   -96,   -64,     0}},
    {{    -7,     0,     0}},
    {{    80,     0,     0}},
    {{    32,  6254,     0}},
    {{    32,  6253,     0}},
    {{    32,  6244,     0}},
    {{    32,  6242,     0}},
    {{    32,  6242,  6243}},
    {{    32,  6236,     0}},
    {{   -32,  6222,     0}},
    {{   -32,  6221,     0}},
    {{   -32,  6212,     0}},
    {{   -32,  6210,     0}},
    {{   -32,  6210,  6211}},
    {{   -32,  6204,     0}},
    {{   -80,     0,     0}},
    {{     1,  6181,     0}},
    {{    -1,  6180,     0}},
    {{    15,     0,     0}},
    {{   -15,     0,     0}},
    {{    48,     0,     0}},
    {{   -48,     0,     0}},
    {{  7264,     0,     0}},
    {{ 38864,     0,     0}},
    {{ -6254, -6222,     0}},
    {{ -6253, -6221,     0}},
    {{ -6244, -6212,     0}},
    {{ -6242, -6210,     0}},
    {{ -6242, -6210,     1}},
    {{ -6243, -6211,    -1}},
    {{ -6236, -6204,     0}},
    {{ -6181, -6180,     0}},
    {{ 35266, 35267,     0}},
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
    {{-35266,     1,     0}},
    {{-35267,    -1,     0}},
    {{-35332,     0,     0}},
    {{-42280,     0,     0}},
    {{-42308,     0,     0}},
    {{-42319,     0,     0}},
    {{-42315,     0,     0}},
    {{-42305,     0,     0}},
    {{-42258,     0,     0}},
    {{-42282,     0,     0}},
    {{-42261,     0,     0}},
    {{   928,     0,     0}},
    {{  -928,     0,     0}},
    {{-38864,     0,     0}},
    {{    40,     0,     0}},
    {{   -40,     0,     0}},
    {{    34,     0,     0}},
    {{   -34,     0,     0}},
};

/* All_Cases: 2664 bytes. */

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
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 2, 2, 2, 2, 6,
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
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  9,  6, 10, 11,
     6, 12,  6,  6, 13,  6,  6,  6,  6,  6,  6,  6, 14,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 15, 16,  6,  6,  6, 17,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 18,
     6,  6,  6,  6, 19,  6,  6,  6,  6,  6,  6,  6, 20,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 21,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 22,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_simple_case_folding_stage_3[] = {
     0,  0,  0,  0,  0,  0,  0,  0,  1,  2,  2,  3,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  4,  0,  2,  2,  5,  5,  0,  0,  0,  0,
     6,  6,  6,  6,  6,  6,  7,  8,  8,  7,  6,  6,  6,  6,  6,  9,
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19,  8, 20,  6,  6, 21,  6,
     6,  6,  6,  6, 22,  6, 23, 24, 25,  6,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0, 26,  0,  0,  0,  0,  0, 27, 28,
    29, 30,  1,  2, 31, 32,  0,  0, 33, 34, 35,  6,  6,  6, 36, 37,
    38, 38,  2,  2,  2,  2,  0,  0,  0,  0,  0,  0,  6,  6,  6,  6,
    39,  7,  6,  6,  6,  6,  6,  6, 40, 41,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 42, 43, 43, 43, 44,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0, 45, 45, 45, 45, 46, 47,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 48,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    49, 50,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6, 51, 52,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     0, 53,  0, 48,  0, 53,  0, 53,  0, 48,  0, 54,  0, 53,  0,  0,
     0, 53,  0, 53,  0, 53,  0, 55,  0, 56,  0, 57,  0, 58,  0, 59,
     0,  0,  0,  0, 60, 61, 62,  0,  0,  0,  0,  0, 63, 63,  0,  0,
    64,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 65, 66, 66, 66,  0,  0,  0,  0,  0,  0,
    43, 43, 43, 43, 43, 44,  0,  0,  0,  0,  0,  0, 67, 68, 69, 70,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 23, 71, 33,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  6,  6,  6,  6,  6, 51,  0,  0,
     6,  6,  6, 23,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  7,  6,  7,  6,  6,  6,  6,  6,  6,  6,  0, 72,
     6, 73, 27,  6,  6, 74, 75,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 76, 76,
    76, 76, 76, 76, 76, 76, 76, 76,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  1,  2,  2,  3,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    77, 77, 77, 77, 77,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 77, 77, 77, 77, 78,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
    79, 79, 79, 79, 79, 79, 80,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  2,  2,  2,  2,  0,  0,  0,  0,  0,  0,  0,  0,
    81, 81, 81, 81, 82,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,
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
     0,  0,  0,  0,  0,  0,  0, 30,  0,  0,  0,  0,  0,  0, 31,  0,
    32, 32, 32,  0, 33,  0, 34, 34,  1,  1,  0,  1,  1,  1,  1,  1,
     1,  1,  1,  1,  0,  0,  0,  0,  0,  0,  3,  0,  0,  0,  0,  0,
     0,  0,  0,  0,  0,  0,  0, 35, 36, 37,  0,  0,  0, 38, 39,  0,
    40, 41,  0,  0, 42, 43,  0,  3,  0, 44,  3,  0,  0, 23, 23, 23,
    45, 45, 45, 45, 45, 45, 45, 45,  3,  0,  0,  0,  0,  0,  0,  0,
    46,  3,  0,  3,  0,  3,  0,  3,  0,  3,  0,  3,  0,  3,  0,  0,
     0, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47, 47,
    47, 47, 47, 47, 47, 47, 47,  0, 48, 48, 48, 48, 48, 48, 48, 48,
    48, 48, 48, 48, 48, 48,  0, 48,  0,  0,  0,  0,  0, 48,  0,  0,
    49, 49, 49, 49, 49, 49,  0,  0, 50, 51, 52, 53, 53, 54, 55, 56,
    57,  0,  0,  0,  0,  0,  0,  0,  3,  0,  3,  0,  3,  0,  0,  0,
     0,  0,  0, 58,  0,  0, 59,  0, 49, 49, 49, 49, 49, 49, 49, 49,
     0, 49,  0, 49,  0, 49,  0, 49, 49, 49, 60, 60, 61,  0, 62,  0,
    63, 63, 63, 63, 61,  0,  0,  0, 49, 49, 64, 64,  0,  0,  0,  0,
    49, 49, 65, 65, 44,  0,  0,  0, 66, 66, 67, 67, 61,  0,  0,  0,
     0,  0,  0,  0,  0,  0, 68,  0,  0,  0, 69, 70,  0,  0,  0,  0,
     0,  0, 71,  0,  0,  0,  0,  0, 72, 72, 72, 72, 72, 72, 72, 72,
     0,  0,  0,  3,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0, 73, 73,
    73, 73, 73, 73, 73, 73, 73, 73,  3,  0, 74, 75, 76,  0,  0,  3,
     0,  3,  0,  3,  0, 77, 78, 79, 80,  0,  3,  0,  0,  3,  0,  0,
     0,  0,  0,  0,  0,  0, 81, 81,  0,  0,  0,  3,  0,  3,  0,  0,
     0,  3,  0,  3,  0, 82,  3,  0,  0,  0,  0,  3,  0, 83,  0,  0,
     3,  0, 84, 85, 86, 87, 84,  0, 88, 89, 90, 91,  3,  0,  3,  0,
    92, 92, 92, 92, 92, 92, 92, 92, 93, 93, 93, 93, 93, 93, 93, 93,
    93, 93, 93, 93,  0,  0,  0,  0, 33, 33, 33, 33, 33, 33, 33, 33,
    33, 33, 33,  0,  0,  0,  0,  0, 94, 94, 94, 94, 94, 94, 94, 94,
    94, 94,  0,  0,  0,  0,  0,  0,
};

/* Simple_Case_Folding: 1760 bytes. */

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
        -8,
     -6222,
     -6221,
     -6212,
     -6210,
     -6211,
     -6204,
     -6180,
     35267,
       -58,
     -7615,
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
    -42319,
    -42315,
    -42305,
    -42258,
    -42282,
    -42261,
       928,
    -38864,
        40,
        34,
};

/* Simple_Case_Folding: 380 bytes. */

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
    0, 1, 2, 2, 2, 3, 2, 4, 5, 2, 2, 2, 2, 2, 2, 6,
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
     7,  6,  6,  8,  6,  6,  6,  6,  6,  6,  6,  6,  9,  6, 10, 11,
     6, 12,  6,  6, 13,  6,  6,  6,  6,  6,  6,  6, 14,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6, 15, 16,  6,  6,  6, 17,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6, 18,  6,  6,  6, 19,
     6,  6,  6,  6, 20,  6,  6,  6,  6,  6,  6,  6, 21,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6, 22,  6,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6, 23,  6,  6,  6,  6,  6,  6,
     6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,  6,
};

static RE_UINT8 re_full_case_folding_stage_3[] = {
      0,   0,   0,   0,   0,   0,   0,   0,   1,   2,   2,   3,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   4,   0,   2,   2,   5,   6,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   8,   9,   9,  10,   7,   7,   7,   7,   7,  11,
     12,  13,  14,  15,  16,  17,  18,  19,  20,  21,   9,  22,   7,   7,  23,   7,
      7,   7,   7,   7,  24,   7,  25,  26,  27,   7,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,  28,   0,   0,   0,   0,   0,  29,  30,
     31,  32,  33,   2,  34,  35,  36,   0,  37,  38,  39,   7,   7,   7,  40,  41,
     42,  42,   2,   2,   2,   2,   0,   0,   0,   0,   0,   0,   7,   7,   7,   7,
     43,  44,   7,   7,   7,   7,   7,   7,  45,  46,   7,   7,   7,   7,   7,   7,
      7,   7,   7,   7,   7,   7,  47,  48,  48,  48,  49,   0,   0,   0,   0,   0,
     50,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  51,  51,  51,  51,  52,  53,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  54,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     55,  56,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      7,   7,  57,  58,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,
      0,  59,   0,  54,   0,  59,   0,  59,   0,  54,  60,  61,   0,  59,   0,   0,
     62,  63,  64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,
      0,   0,   0,   0,  78,  79,  80,   0,   0,   0,   0,   0,  81,  81,   0,   0,
     82,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  83,  84,  84,  84,   0,   0,   0,   0,   0,   0,
     48,  48,  48,  48,  48,  49,   0,   0,   0,   0,   0,   0,  85,  86,  87,  88,
      7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,   7,  25,  89,  37,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   7,   7,   7,   7,   7,  90,   0,   0,
      7,   7,   7,  25,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,  44,   7,  44,   7,   7,   7,   7,   7,   7,   7,   0,  91,
      7,  92,  29,   7,   7,  93,  94,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,  95,  95,
     95,  95,  95,  95,  95,  95,  95,  95,   0,   0,   0,   0,   0,   0,   0,   0,
     96,   0,  97,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   1,   2,   2,   3,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
     98,  98,  98,  98,  98,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,  98,  98,  98,  98,  99,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
    100, 100, 100, 100, 100, 100, 101,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   2,   2,   2,   2,   0,   0,   0,   0,   0,   0,   0,   0,
    102, 102, 102, 102, 103,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
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
      0,   0,   0,   0,   0,   0,   0,  34,   0,   0,   0,   0,   0,   0,  35,   0,
     36,  36,  36,   0,  37,   0,  38,  38,  39,   1,   1,   1,   1,   1,   1,   1,
      1,   1,   0,   1,   1,   1,   1,   1,   1,   1,   1,   1,   0,   0,   0,   0,
     40,   0,   0,   0,   0,   0,   0,   0,   0,   0,   4,   0,   0,   0,   0,   0,
      0,   0,   0,   0,   0,   0,   0,  41,  42,  43,   0,   0,   0,  44,  45,   0,
     46,  47,   0,   0,  48,  49,   0,   4,   0,  50,   4,   0,   0,  27,  27,  27,
     51,  51,  51,  51,  51,  51,  51,  51,   4,   0,   0,   0,   0,   0,   0,   0,
      0,   0,   4,   0,   4,   0,   4,   0,  52,   4,   0,   4,   0,   4,   0,   4,
      0,   4,   0,   4,   0,   4,   0,   0,   0,  53,  53,  53,  53,  53,  53,  53,
     53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,  53,   0,
      0,   0,   0,   0,   0,   0,   0,  54,  55,  55,  55,  55,  55,  55,  55,  55,
     55,  55,  55,  55,  55,  55,   0,  55,   0,   0,   0,   0,   0,  55,   0,   0,
     56,  56,  56,  56,  56,  56,   0,   0,  57,  58,  59,  60,  60,  61,  62,  63,
     64,   0,   0,   0,   0,   0,   0,   0,   4,   0,   4,   0,   4,   0,  65,  66,
     67,  68,  69,  70,   0,   0,  71,   0,  56,  56,  56,  56,  56,  56,  56,  56,
     72,   0,  73,   0,  74,   0,  75,   0,   0,  56,   0,  56,   0,  56,   0,  56,
     76,  76,  76,  76,  76,  76,  76,  76,  77,  77,  77,  77,  77,  77,  77,  77,
     78,  78,  78,  78,  78,  78,  78,  78,  79,  79,  79,  79,  79,  79,  79,  79,
     80,  80,  80,  80,  80,  80,  80,  80,  81,  81,  81,  81,  81,  81,  81,  81,
      0,   0,  82,  83,  84,   0,  85,  86,  56,  56,  87,  87,  88,   0,  89,   0,
      0,   0,  90,  91,  92,   0,  93,  94,  95,  95,  95,  95,  96,   0,   0,   0,
      0,   0,  97,  98,   0,   0,  99, 100,  56,  56, 101, 101,   0,   0,   0,   0,
      0,   0, 102, 103, 104,   0, 105, 106,  56,  56, 107, 107,  50,   0,   0,   0,
      0,   0, 108, 109, 110,   0, 111, 112, 113, 113, 114, 114, 115,   0,   0,   0,
      0,   0,   0,   0,   0,   0, 116,   0,   0,   0, 117, 118,   0,   0,   0,   0,
      0,   0, 119,   0,   0,   0,   0,   0, 120, 120, 120, 120, 120, 120, 120, 120,
      0,   0,   0,   4,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0, 121, 121,
    121, 121, 121, 121, 121, 121, 121, 121,   4,   0, 122, 123, 124,   0,   0,   4,
      0,   4,   0,   4,   0, 125, 126, 127, 128,   0,   4,   0,   0,   4,   0,   0,
      0,   0,   0,   0,   0,   0, 129, 129,   0,   0,   0,   4,   0,   4,   0,   0,
      4,   0,   4,   0,   4,   0,   0,   0,   0,   4,   0,   4,   0, 130,   4,   0,
      0,   0,   0,   4,   0, 131,   0,   0,   4,   0, 132, 133, 134, 135, 132,   0,
    136, 137, 138, 139,   4,   0,   4,   0, 140, 140, 140, 140, 140, 140, 140, 140,
    141, 142, 143, 144, 145, 146, 147,   0,   0,   0,   0, 148, 149, 150, 151, 152,
    153, 153, 153, 153, 153, 153, 153, 153, 153, 153, 153, 153,   0,   0,   0,   0,
     37,  37,  37,  37,  37,  37,  37,  37,  37,  37,  37,   0,   0,   0,   0,   0,
    154, 154, 154, 154, 154, 154, 154, 154, 154, 154,   0,   0,   0,   0,   0,   0,
};

/* Full_Case_Folding: 1960 bytes. */

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
    {    -8, {   0,   0}},
    { -6222, {   0,   0}},
    { -6221, {   0,   0}},
    { -6212, {   0,   0}},
    { -6210, {   0,   0}},
    { -6211, {   0,   0}},
    { -6204, {   0,   0}},
    { -6180, {   0,   0}},
    { 35267, {   0,   0}},
    { -7726, { 817,   0}},
    { -7715, { 776,   0}},
    { -7713, { 778,   0}},
    { -7712, { 778,   0}},
    { -7737, { 702,   0}},
    {   -58, {   0,   0}},
    { -7723, { 115,   0}},
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
    {-42319, {   0,   0}},
    {-42315, {   0,   0}},
    {-42305, {   0,   0}},
    {-42258, {   0,   0}},
    {-42282, {   0,   0}},
    {-42261, {   0,   0}},
    {   928, {   0,   0}},
    {-38864, {   0,   0}},
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
    {    34, {   0,   0}},
};

/* Full_Case_Folding: 1240 bytes. */

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
    re_get_sentence_terminal,
    re_get_variation_selector,
    re_get_pattern_white_space,
    re_get_pattern_syntax,
    re_get_prepended_concatenation_mark,
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
    re_get_indic_positional_category,
    re_get_indic_syllabic_category,
    re_get_alphanumeric,
    re_get_any,
    re_get_blank,
    re_get_graph,
    re_get_print,
    re_get_word,
    re_get_xdigit,
    re_get_posix_digit,
    re_get_posix_alnum,
    re_get_posix_punct,
    re_get_posix_xdigit,
};
