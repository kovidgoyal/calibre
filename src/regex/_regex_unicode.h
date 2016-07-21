typedef unsigned char RE_UINT8;
typedef signed char RE_INT8;
typedef unsigned short RE_UINT16;
typedef signed short RE_INT16;
typedef unsigned int RE_UINT32;
typedef signed int RE_INT32;

typedef unsigned char BOOL;
enum {FALSE, TRUE};

#define RE_ASCII_MAX 0x7F
#define RE_LOCALE_MAX 0xFF
#define RE_UNICODE_MAX 0x10FFFF

#define RE_MAX_CASES 4
#define RE_MAX_FOLDED 3

typedef struct RE_Property {
    RE_UINT16 name;
    RE_UINT8 id;
    RE_UINT8 value_set;
} RE_Property;

typedef struct RE_PropertyValue {
    RE_UINT16 name;
    RE_UINT8 value_set;
    RE_UINT16 id;
} RE_PropertyValue;

typedef RE_UINT32 (*RE_GetPropertyFunc)(RE_UINT32 ch);

#define RE_PROP_GC 0x0
#define RE_PROP_CASED 0xA
#define RE_PROP_UPPERCASE 0x9
#define RE_PROP_LOWERCASE 0x8

#define RE_PROP_C 30
#define RE_PROP_L 31
#define RE_PROP_M 32
#define RE_PROP_N 33
#define RE_PROP_P 34
#define RE_PROP_S 35
#define RE_PROP_Z 36
#define RE_PROP_ASSIGNED 38
#define RE_PROP_CASEDLETTER 37

#define RE_PROP_CN 0
#define RE_PROP_LU 1
#define RE_PROP_LL 2
#define RE_PROP_LT 3
#define RE_PROP_LM 4
#define RE_PROP_LO 5
#define RE_PROP_MN 6
#define RE_PROP_ME 7
#define RE_PROP_MC 8
#define RE_PROP_ND 9
#define RE_PROP_NL 10
#define RE_PROP_NO 11
#define RE_PROP_ZS 12
#define RE_PROP_ZL 13
#define RE_PROP_ZP 14
#define RE_PROP_CC 15
#define RE_PROP_CF 16
#define RE_PROP_CO 17
#define RE_PROP_CS 18
#define RE_PROP_PD 19
#define RE_PROP_PS 20
#define RE_PROP_PE 21
#define RE_PROP_PC 22
#define RE_PROP_PO 23
#define RE_PROP_SM 24
#define RE_PROP_SC 25
#define RE_PROP_SK 26
#define RE_PROP_SO 27
#define RE_PROP_PI 28
#define RE_PROP_PF 29

#define RE_PROP_C_MASK 0x00078001
#define RE_PROP_L_MASK 0x0000003E
#define RE_PROP_M_MASK 0x000001C0
#define RE_PROP_N_MASK 0x00000E00
#define RE_PROP_P_MASK 0x30F80000
#define RE_PROP_S_MASK 0x0F000000
#define RE_PROP_Z_MASK 0x00007000

#define RE_PROP_ALNUM 0x470001
#define RE_PROP_ALPHA 0x070001
#define RE_PROP_ANY 0x480001
#define RE_PROP_ASCII 0x010001
#define RE_PROP_BLANK 0x490001
#define RE_PROP_CNTRL 0x00000F
#define RE_PROP_DIGIT 0x000009
#define RE_PROP_GRAPH 0x4A0001
#define RE_PROP_LOWER 0x080001
#define RE_PROP_PRINT 0x4B0001
#define RE_PROP_SPACE 0x190001
#define RE_PROP_UPPER 0x090001
#define RE_PROP_WORD 0x4C0001
#define RE_PROP_XDIGIT 0x4D0001
#define RE_PROP_POSIX_ALNUM 0x4F0001
#define RE_PROP_POSIX_DIGIT 0x4E0001
#define RE_PROP_POSIX_PUNCT 0x500001
#define RE_PROP_POSIX_XDIGIT 0x510001

#define RE_BREAK_OTHER 0
#define RE_BREAK_DOUBLEQUOTE 1
#define RE_BREAK_SINGLEQUOTE 2
#define RE_BREAK_HEBREWLETTER 3
#define RE_BREAK_CR 4
#define RE_BREAK_LF 5
#define RE_BREAK_NEWLINE 6
#define RE_BREAK_EXTEND 7
#define RE_BREAK_REGIONALINDICATOR 8
#define RE_BREAK_FORMAT 9
#define RE_BREAK_KATAKANA 10
#define RE_BREAK_ALETTER 11
#define RE_BREAK_MIDLETTER 12
#define RE_BREAK_MIDNUM 13
#define RE_BREAK_MIDNUMLET 14
#define RE_BREAK_NUMERIC 15
#define RE_BREAK_EXTENDNUMLET 16
#define RE_BREAK_EBASE 17
#define RE_BREAK_EMODIFIER 18
#define RE_BREAK_ZWJ 19
#define RE_BREAK_GLUEAFTERZWJ 20
#define RE_BREAK_EBASEGAZ 21

#define RE_GBREAK_OTHER 0
#define RE_GBREAK_PREPEND 1
#define RE_GBREAK_CR 2
#define RE_GBREAK_LF 3
#define RE_GBREAK_CONTROL 4
#define RE_GBREAK_EXTEND 5
#define RE_GBREAK_REGIONALINDICATOR 6
#define RE_GBREAK_SPACINGMARK 7
#define RE_GBREAK_L 8
#define RE_GBREAK_V 9
#define RE_GBREAK_T 10
#define RE_GBREAK_LV 11
#define RE_GBREAK_LVT 12
#define RE_GBREAK_EBASE 13
#define RE_GBREAK_EMODIFIER 14
#define RE_GBREAK_ZWJ 15
#define RE_GBREAK_GLUEAFTERZWJ 16
#define RE_GBREAK_EBASEGAZ 17

extern char* re_strings[1336];
extern RE_Property re_properties[150];
extern RE_PropertyValue re_property_values[1469];
extern RE_UINT16 re_expand_on_folding[104];
extern RE_GetPropertyFunc re_get_property[82];

RE_UINT32 re_get_general_category(RE_UINT32 ch);
RE_UINT32 re_get_block(RE_UINT32 ch);
RE_UINT32 re_get_script(RE_UINT32 ch);
RE_UINT32 re_get_word_break(RE_UINT32 ch);
RE_UINT32 re_get_grapheme_cluster_break(RE_UINT32 ch);
RE_UINT32 re_get_sentence_break(RE_UINT32 ch);
RE_UINT32 re_get_math(RE_UINT32 ch);
RE_UINT32 re_get_alphabetic(RE_UINT32 ch);
RE_UINT32 re_get_lowercase(RE_UINT32 ch);
RE_UINT32 re_get_uppercase(RE_UINT32 ch);
RE_UINT32 re_get_cased(RE_UINT32 ch);
RE_UINT32 re_get_case_ignorable(RE_UINT32 ch);
RE_UINT32 re_get_changes_when_lowercased(RE_UINT32 ch);
RE_UINT32 re_get_changes_when_uppercased(RE_UINT32 ch);
RE_UINT32 re_get_changes_when_titlecased(RE_UINT32 ch);
RE_UINT32 re_get_changes_when_casefolded(RE_UINT32 ch);
RE_UINT32 re_get_changes_when_casemapped(RE_UINT32 ch);
RE_UINT32 re_get_id_start(RE_UINT32 ch);
RE_UINT32 re_get_id_continue(RE_UINT32 ch);
RE_UINT32 re_get_xid_start(RE_UINT32 ch);
RE_UINT32 re_get_xid_continue(RE_UINT32 ch);
RE_UINT32 re_get_default_ignorable_code_point(RE_UINT32 ch);
RE_UINT32 re_get_grapheme_extend(RE_UINT32 ch);
RE_UINT32 re_get_grapheme_base(RE_UINT32 ch);
RE_UINT32 re_get_grapheme_link(RE_UINT32 ch);
RE_UINT32 re_get_white_space(RE_UINT32 ch);
RE_UINT32 re_get_bidi_control(RE_UINT32 ch);
RE_UINT32 re_get_join_control(RE_UINT32 ch);
RE_UINT32 re_get_dash(RE_UINT32 ch);
RE_UINT32 re_get_hyphen(RE_UINT32 ch);
RE_UINT32 re_get_quotation_mark(RE_UINT32 ch);
RE_UINT32 re_get_terminal_punctuation(RE_UINT32 ch);
RE_UINT32 re_get_other_math(RE_UINT32 ch);
RE_UINT32 re_get_hex_digit(RE_UINT32 ch);
RE_UINT32 re_get_ascii_hex_digit(RE_UINT32 ch);
RE_UINT32 re_get_other_alphabetic(RE_UINT32 ch);
RE_UINT32 re_get_ideographic(RE_UINT32 ch);
RE_UINT32 re_get_diacritic(RE_UINT32 ch);
RE_UINT32 re_get_extender(RE_UINT32 ch);
RE_UINT32 re_get_other_lowercase(RE_UINT32 ch);
RE_UINT32 re_get_other_uppercase(RE_UINT32 ch);
RE_UINT32 re_get_noncharacter_code_point(RE_UINT32 ch);
RE_UINT32 re_get_other_grapheme_extend(RE_UINT32 ch);
RE_UINT32 re_get_ids_binary_operator(RE_UINT32 ch);
RE_UINT32 re_get_ids_trinary_operator(RE_UINT32 ch);
RE_UINT32 re_get_radical(RE_UINT32 ch);
RE_UINT32 re_get_unified_ideograph(RE_UINT32 ch);
RE_UINT32 re_get_other_default_ignorable_code_point(RE_UINT32 ch);
RE_UINT32 re_get_deprecated(RE_UINT32 ch);
RE_UINT32 re_get_soft_dotted(RE_UINT32 ch);
RE_UINT32 re_get_logical_order_exception(RE_UINT32 ch);
RE_UINT32 re_get_other_id_start(RE_UINT32 ch);
RE_UINT32 re_get_other_id_continue(RE_UINT32 ch);
RE_UINT32 re_get_sentence_terminal(RE_UINT32 ch);
RE_UINT32 re_get_variation_selector(RE_UINT32 ch);
RE_UINT32 re_get_pattern_white_space(RE_UINT32 ch);
RE_UINT32 re_get_pattern_syntax(RE_UINT32 ch);
RE_UINT32 re_get_prepended_concatenation_mark(RE_UINT32 ch);
RE_UINT32 re_get_hangul_syllable_type(RE_UINT32 ch);
RE_UINT32 re_get_bidi_class(RE_UINT32 ch);
RE_UINT32 re_get_canonical_combining_class(RE_UINT32 ch);
RE_UINT32 re_get_decomposition_type(RE_UINT32 ch);
RE_UINT32 re_get_east_asian_width(RE_UINT32 ch);
RE_UINT32 re_get_joining_group(RE_UINT32 ch);
RE_UINT32 re_get_joining_type(RE_UINT32 ch);
RE_UINT32 re_get_line_break(RE_UINT32 ch);
RE_UINT32 re_get_numeric_type(RE_UINT32 ch);
RE_UINT32 re_get_numeric_value(RE_UINT32 ch);
RE_UINT32 re_get_bidi_mirrored(RE_UINT32 ch);
RE_UINT32 re_get_indic_positional_category(RE_UINT32 ch);
RE_UINT32 re_get_indic_syllabic_category(RE_UINT32 ch);
RE_UINT32 re_get_alphanumeric(RE_UINT32 ch);
RE_UINT32 re_get_any(RE_UINT32 ch);
RE_UINT32 re_get_blank(RE_UINT32 ch);
RE_UINT32 re_get_graph(RE_UINT32 ch);
RE_UINT32 re_get_print(RE_UINT32 ch);
RE_UINT32 re_get_word(RE_UINT32 ch);
RE_UINT32 re_get_xdigit(RE_UINT32 ch);
RE_UINT32 re_get_posix_digit(RE_UINT32 ch);
RE_UINT32 re_get_posix_alnum(RE_UINT32 ch);
RE_UINT32 re_get_posix_punct(RE_UINT32 ch);
RE_UINT32 re_get_posix_xdigit(RE_UINT32 ch);
int re_get_all_cases(RE_UINT32 ch, RE_UINT32* codepoints);
RE_UINT32 re_get_simple_case_folding(RE_UINT32 ch);
int re_get_full_case_folding(RE_UINT32 ch, RE_UINT32* codepoints);
