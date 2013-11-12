/* Secret Labs' Regular Expression Engine
 *
 * regular expression matching engine
 *
 * partial history:
 * 1999-10-24 fl   created (based on existing template matcher code)
 * 2000-03-06 fl   first alpha, sort of
 * 2000-08-01 fl   fixes for 1.6b1
 * 2000-08-07 fl   use PyOS_CheckStack() if available
 * 2000-09-20 fl   added expand method
 * 2001-03-20 fl   lots of fixes for 2.1b2
 * 2001-04-15 fl   export copyright as Python attribute, not global
 * 2001-04-28 fl   added __copy__ methods (work in progress)
 * 2001-05-14 fl   fixes for 1.5.2 compatibility
 * 2001-07-01 fl   added BIGCHARSET support (from Martin von Loewis)
 * 2001-10-18 fl   fixed group reset issue (from Matthew Mueller)
 * 2001-10-20 fl   added split primitive; reenable unicode for 1.6/2.0/2.1
 * 2001-10-21 fl   added sub/subn primitive
 * 2001-10-24 fl   added finditer primitive (for 2.2 only)
 * 2001-12-07 fl   fixed memory leak in sub/subn (Guido van Rossum)
 * 2002-11-09 fl   fixed empty sub/subn return type
 * 2003-04-18 mvl  fully support 4-byte codes
 * 2003-10-17 gn   implemented non recursive scheme
 * 2009-07-26 mrab completely re-designed matcher code
 * 2011-11-18 mrab added support for PEP 393 strings
 *
 * Copyright (c) 1997-2001 by Secret Labs AB.  All rights reserved.
 *
 * This version of the SRE library can be redistributed under CNRI's
 * Python 1.6 license.  For any other use, please contact Secret Labs
 * AB (info@pythonware.com).
 *
 * Portions of this engine have been developed in cooperation with
 * CNRI.  Hewlett-Packard provided funding for 1.6 integration and
 * other compatibility work.
 */

/* #define VERBOSE */

#if defined(VERBOSE)
#define TRACE(X) printf X;
#else
#define TRACE(X)
#endif

#include "Python.h"
#include "structmember.h" /* offsetof */
#include <ctype.h>
#include "_regex.h"
#include "pyport.h"
#include "pythread.h"

#define RE_MIN(X, Y) ((X) <= (Y) ? (X) : (Y))
#define RE_MAX(X, Y) ((X) >= (Y) ? (X) : (Y))

#if PY_VERSION_HEX < 0x02060000
#if SIZEOF_SIZE_T == SIZEOF_LONG_LONG
#define T_PYSSIZET T_LONGLONG
#elif SIZEOF_SIZE_T == SIZEOF_LONG
#define T_PYSSIZET T_LONG
#else
#error size_t is the same size as neither LONG nor LONGLONG
#endif

#endif
typedef unsigned char Py_UCS1;
typedef unsigned short Py_UCS2;

typedef RE_UINT32 RE_CODE;

/* Case-sensitive letters in the General Category. */
#define RE_PROP_GC_LU ((RE_PROP_GC << 16) | RE_PROP_LU)
#define RE_PROP_GC_LL ((RE_PROP_GC << 16) | RE_PROP_LL)
#define RE_PROP_GC_LT ((RE_PROP_GC << 16) | RE_PROP_LT)

/* Unlimited repeat count. */
#define RE_UNLIMITED (~(RE_CODE)0)

/* The status of a node. */
typedef unsigned short RE_STATUS_T;

/* Whether to match concurrently, i.e. release the GIL while matching. */
#define RE_CONC_NO 0
#define RE_CONC_YES 1
#define RE_CONC_DEFAULT 2

/* Flags for the kind of 'sub' call: 'sub', 'subn', 'subf', 'subfn'. */
#define RE_SUB  0x0
#define RE_SUBN 0x1
#if PY_VERSION_HEX >= 0x02060000
#define RE_SUBF 0x2
#endif

/* The name of this module, minus the leading underscore. */
#define RE_MODULE "regex"
#define RE_MODULE_UPPER "REGEX"

/* Error codes. */
#define RE_ERROR_SUCCESS 1 /* Successful match. */
#define RE_ERROR_FAILURE 0 /* Unsuccessful match. */
#define RE_ERROR_ILLEGAL -1 /* Illegal code. */
#define RE_ERROR_INTERNAL -2 /* Internal error. */
#define RE_ERROR_CONCURRENT -3 /* "concurrent" invalid. */
#define RE_ERROR_MEMORY -9 /* Out of memory. */
#define RE_ERROR_INTERRUPTED -10 /* Signal handler raised exception. */
#define RE_ERROR_REPLACEMENT -11 /* Invalid replacement string. */
#define RE_ERROR_INVALID_GROUP_REF -12 /* Invalid group reference. */
#define RE_ERROR_GROUP_INDEX_TYPE -13 /* Group index type error. */
#define RE_ERROR_NO_SUCH_GROUP -14 /* No such group. */
#define RE_ERROR_INDEX -15 /* String index. */
#define RE_ERROR_BACKTRACKING -16 /* Too much backtracking. */
#define RE_ERROR_NOT_STRING -17 /* Not a string. */
#define RE_ERROR_NOT_UNICODE -18 /* Not a Unicode string. */

/* The number of backtrack entries per allocated block. */
#define RE_BACKTRACK_BLOCK_SIZE 64

/* The maximum number of backtrack entries to allocate. */
#define RE_MAX_BACKTRACK_ALLOC (1024 * 1024)

/* The initial maximum capacity of the guard block. */
#define RE_INIT_GUARDS_BLOCK_SIZE 16

/* The initial maximum capacity of the node list. */
#define RE_INIT_NODE_LIST_SIZE 16

/* The size increment for various allocation lists. */
#define RE_LIST_SIZE_INC 16

/* The initial maximum capacity of the capture groups. */
#define RE_INIT_CAPTURE_SIZE 16

/* Node bitflags. */
#define RE_POSITIVE_OP 0x1
#define RE_ZEROWIDTH_OP 0x2
#define RE_FUZZY_OP 0x4
#define RE_REVERSE_OP 0x8
#define RE_REQUIRED_OP 0x10

/* Guards against further matching can occur at the start of the body and the
 * tail of a repeat containing a repeat.
 */
#define RE_STATUS_BODY 0x1
#define RE_STATUS_TAIL 0x2

/* Whether a guard is added depends on whether there's a repeat in the body of
 * the repeat or a group reference in the body or tail of the repeat.
 */
#define RE_STATUS_NEITHER 0x0
#define RE_STATUS_REPEAT 0x4
#define RE_STATUS_LIMITED 0x8
#define RE_STATUS_REF 0x10
#define RE_STATUS_VISITED_AG 0x20
#define RE_STATUS_VISITED_REP 0x40

/* Whether a string node has been initialised for fast searching. */
#define RE_STATUS_FAST_INIT 0x80

/* Whether a node us being used. (Additional nodes may be created while the
 * pattern is being built.
 */
#define RE_STATUS_USED 0x100

/* Whether a node is a string node. */
#define RE_STATUS_STRING 0x200

/* Whether a repeat node is within another repeat. */
#define RE_STATUS_INNER 0x400

/* Various flags stored in a node status member. */
#define RE_STATUS_SHIFT 11

#define RE_STATUS_FUZZY (RE_FUZZY_OP << RE_STATUS_SHIFT)
#define RE_STATUS_REVERSE (RE_REVERSE_OP << RE_STATUS_SHIFT)
#define RE_STATUS_REQUIRED (RE_REQUIRED_OP << RE_STATUS_SHIFT)

/* The different error types for fuzzy matching. */
#define RE_FUZZY_SUB 0
#define RE_FUZZY_INS 1
#define RE_FUZZY_DEL 2
#define RE_FUZZY_ERR 3
#define RE_FUZZY_COUNT 3

#define RE_FUZZY_THRESHOLD 10

/* The various values in a FUZZY node. */
#define RE_FUZZY_VAL_MAX_SUB 1
#define RE_FUZZY_VAL_MAX_INS 2
#define RE_FUZZY_VAL_MAX_DEL 3
#define RE_FUZZY_VAL_MAX_ERR 4
#define RE_FUZZY_VAL_SUB_COST 5
#define RE_FUZZY_VAL_INS_COST 6
#define RE_FUZZY_VAL_DEL_COST 7
#define RE_FUZZY_VAL_MAX_COST 8

#define RE_FUZZY_VAL_MAX_BASE 1
#define RE_FUZZY_VAL_COST_BASE 5

/* The various values in a END_FUZZY node. */
#define RE_FUZZY_VAL_MIN_SUB 1
#define RE_FUZZY_VAL_MIN_INS 2
#define RE_FUZZY_VAL_MIN_DEL 3
#define RE_FUZZY_VAL_MIN_ERR 4

/* The flags which will be set for full Unicode case folding. */
#define RE_FULL_CASE_FOLDING (RE_FLAG_UNICODE | RE_FLAG_FULLCASE | RE_FLAG_IGNORECASE)

/* The shortest string prefix for which we'll use a fast string search. */
#define RE_MIN_FAST_LENGTH 5

static char copyright[] =
    " RE 2.3.0 Copyright (c) 1997-2002 by Secret Labs AB ";

/* The exception to raise on error. */
static PyObject* error_exception;

/* The dictionary of Unicode properties. */
static PyObject* property_dict;

typedef struct RE_State* RE_StatePtr;

/* Handlers for ASCII, locale and Unicode. */
typedef struct RE_EncodingTable {
    BOOL (*has_property)(RE_CODE property, Py_UCS4 ch);
    Py_UCS4 (*lower)(Py_UCS4 ch);
    Py_UCS4 (*upper)(Py_UCS4 ch);
    Py_UCS4 (*title)(Py_UCS4 ch);
    BOOL (*at_boundary)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_word_start)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_word_end)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_default_boundary)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_default_word_start)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_default_word_end)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_grapheme_boundary)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*is_line_sep)(Py_UCS4 ch);
    BOOL (*at_line_start)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*at_line_end)(RE_StatePtr state, Py_ssize_t text_pos);
    BOOL (*possible_turkic)(Py_UCS4 ch);
    int (*all_cases)(Py_UCS4 ch, Py_UCS4* codepoints);
    Py_UCS4 (*simple_case_fold)(Py_UCS4 ch);
    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
    int (*all_turkic_i)(Py_UCS4 ch, Py_UCS4* cases);
} RE_EncodingTable;

/* Position within the regex and text. */
typedef struct RE_Position {
    struct RE_Node* node;
    Py_ssize_t text_pos;
} RE_Position;

/* Info about fuzzy matching. */
typedef struct RE_FuzzyInfo {
    struct RE_Node* node;
    size_t counts[RE_FUZZY_COUNT + 1]; /* Add 1 for total errors. */
    size_t total_cost;
} RE_FuzzyInfo;

/* Storage for backtrack data. */
typedef struct RE_BacktrackData {
    union {
        struct {
            size_t capture_change;
            BOOL too_few_errors;
        } atomic;
        struct {
            RE_Position position;
        } branch;
        struct {
            RE_FuzzyInfo fuzzy_info;
            Py_ssize_t text_pos;
            RE_UINT32 index;
        } fuzzy;
        struct {
            RE_Position position;
            Py_ssize_t count;
            struct RE_Node* fuzzy_node;
            BOOL too_few_errors;
        } fuzzy_insert;
        struct {
            RE_Position position;
            RE_INT8 fuzzy_type;
            RE_INT8 step;
        } fuzzy_one;
        struct {
            RE_Position position;
            Py_ssize_t string_pos;
            size_t string_len;
            RE_INT8 fuzzy_type;
            RE_INT8 folded_pos;
            RE_INT8 folded_len;
            RE_INT8 gfolded_pos;
            RE_INT8 gfolded_len;
            RE_INT8 step;
        } fuzzy_string;
        struct {
            RE_Position position;
            RE_INT8 fuzzy_type;
        } fuzzy_zero;
        struct {
            Py_ssize_t text_pos;
            Py_ssize_t current_capture;
            RE_UINT32 private_index;
            RE_UINT32 public_index;
            BOOL capture;
        } group;
        struct {
            struct RE_Node* node;
            size_t capture_change;
        } group_call;
        struct {
            size_t capture_change;
            BOOL too_few_errors;
        } lookaround;
        struct {
            RE_Position position;
            Py_ssize_t text_pos;
            size_t count;
            Py_ssize_t start;
            size_t capture_change;
            RE_UINT32 index;
        } repeat;
        struct {
            size_t* capture_counts;
        } saved;
    };
    RE_UINT8 op;
} RE_BacktrackData;

/* Storage for backtrack data is allocated in blocks for speed. */
typedef struct RE_BacktrackBlock {
    RE_BacktrackData items[RE_BACKTRACK_BLOCK_SIZE];
    struct RE_BacktrackBlock* previous;
    struct RE_BacktrackBlock* next;
    size_t capacity;
    size_t count;
} RE_BacktrackBlock;

/* Storage for saved groups. */
typedef struct RE_SavedGroups {
    struct RE_SavedGroups* previous;
    struct RE_SavedGroups* next;
    struct RE_GroupSpan* spans;
    size_t* counts;
} RE_SavedGroups;

/* Storage for info around a recursive by 'basic'match'. */
typedef struct RE_Info {
    RE_BacktrackBlock* current_backtrack_block;
    size_t backtrack_count;
    RE_SavedGroups* current_saved_groups;
    size_t captures_count;
    struct RE_GroupCallFrame* current_group_call_frame;
    BOOL must_advance;
} RE_Info;

/* Storage for the next node. */
typedef struct RE_NextNode {
    struct RE_Node* node;
    struct RE_Node* test;
    struct RE_Node* match_next;
    Py_ssize_t match_step;
} RE_NextNode;

/* A pattern node. */
typedef struct RE_Node {
    RE_NextNode next_1;
    union {
        struct {
            RE_NextNode next_2;
        } nonstring;
        struct {
            /* Used only if (node->status & RE_STATUS_STRING) is true. */
            Py_ssize_t* bad_character_offset;
            Py_ssize_t* good_suffix_offset;
        } string;
    };
    Py_ssize_t step;
    size_t value_count;
    RE_CODE* values;
    RE_STATUS_T status;
    RE_UINT8 op;
    BOOL match;
} RE_Node;

/* Info about a group's span. */
typedef struct RE_GroupSpan {
    Py_ssize_t start;
    Py_ssize_t end;
} RE_GroupSpan;

/* Span of a guard (inclusive range). */
typedef struct RE_GuardSpan {
    Py_ssize_t low;
    Py_ssize_t high;
    BOOL protect;
} RE_GuardSpan;

/* Spans guarded against further matching. */
typedef struct RE_GuardList {
    size_t capacity;
    size_t count;
    RE_GuardSpan* spans;
    Py_ssize_t last_text_pos;
    size_t last_low;
} RE_GuardList;

/* Info about a group in a context. */
typedef struct RE_GroupData {
    RE_GroupSpan span;
    size_t capture_count;
    size_t capture_capacity;
    Py_ssize_t current_capture;
    RE_GroupSpan* captures;
} RE_GroupData;

/* Info about a repeat. */
typedef struct RE_RepeatData {
    RE_GuardList body_guard_list;
    RE_GuardList tail_guard_list;
    size_t count;
    Py_ssize_t start;
    size_t capture_change;
} RE_RepeatData;

/* Storage for saved repeats. */
typedef struct RE_SavedRepeats {
    struct RE_SavedRepeats* previous;
    struct RE_SavedRepeats* next;
    RE_RepeatData* repeats;
} RE_SavedRepeats;

/* Guards for fuzzy sections. */
typedef struct RE_FuzzyGuards {
    RE_GuardList body_guard_list;
    RE_GuardList tail_guard_list;
} RE_FuzzyGuards;

/* Info about a capture group. */
typedef struct RE_GroupInfo {
    Py_ssize_t end_index;
    RE_Node* node;
    BOOL referenced;
    BOOL has_name;
    BOOL called;
} RE_GroupInfo;

/* Info about a call_ref. */
typedef struct RE_CallRefInfo {
    RE_Node* node;
    BOOL defined;
    BOOL used;
} RE_CallRefInfo;

/* Info about a repeat. */
typedef struct RE_RepeatInfo {
    RE_STATUS_T status;
} RE_RepeatInfo;

/* Stack frame for a group call. */
typedef struct RE_GroupCallFrame {
    struct RE_GroupCallFrame* previous;
    struct RE_GroupCallFrame* next;
    RE_Node* node;
    RE_GroupData* groups;
    RE_RepeatData* repeats;
} RE_GroupCallFrame;

/* Info about a string argument. */
typedef struct RE_StringInfo {
#if PY_VERSION_HEX >= 0x02060000
    Py_buffer view; /* View of the string if it's a buffer object. */
#endif
    void* characters; /* Pointer to the characters of the string. */
    Py_ssize_t length; /* Length of the string. */
    Py_ssize_t charsize; /* Size of the characters in the string. */
    BOOL is_unicode; /* Whether the string is Unicode. */
    BOOL should_release; /* Whether the buffer should be released. */
} RE_StringInfo;

/* Info about where the next match was found, starting from a certain search
 * position. This is used when a pattern starts with a BRANCH.
 */
#define MAX_SEARCH_POSITIONS 7

typedef struct {
    Py_ssize_t start_pos;
    Py_ssize_t match_pos;
} RE_SearchPosition;

/* The state object used during matching. */
typedef struct RE_State {
    struct PatternObject* pattern; /* Parent PatternObject. */
    /* Info about the string being matched. */
    PyObject* string;
#if PY_VERSION_HEX >= 0x02060000
    Py_buffer view; /* View of the string if it's a buffer object. */
#endif
    Py_ssize_t charsize;
    void* text;
    Py_ssize_t text_length;
    /* The slice of the string being searched. */
    Py_ssize_t slice_start;
    Py_ssize_t slice_end;
    /* Info about the capture groups. */
    RE_GroupData* groups;
    Py_ssize_t lastindex;
    Py_ssize_t lastgroup;
    /* Info about the repeats. */
    RE_RepeatData* repeats;
    Py_ssize_t search_anchor; /* Where the last match finished. */
    Py_ssize_t match_pos; /* The start position of the match. */
    Py_ssize_t text_pos; /* The current position of the match. */
    Py_ssize_t final_newline; /* The index of newline at end of string, or -1. */
    Py_ssize_t final_line_sep; /* The index of line separator at end of string, or -1. */
    /* Storage for backtrack info. */
    RE_BacktrackBlock backtrack_block;
    RE_BacktrackBlock* current_backtrack_block;
    size_t backtrack_allocated;
    RE_BacktrackData* backtrack;
    /* Storage for saved capture groups. */
    RE_SavedGroups* first_saved_groups;
    RE_SavedGroups* current_saved_groups;
    RE_SavedRepeats* first_saved_repeats;
    RE_SavedRepeats* current_saved_repeats;
    size_t min_width; /* The minimum width of the string to match (assuming it's not a fuzzy pattern). */
    RE_EncodingTable* encoding; /* The 'encoding' of the string being searched. */
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void (*set_char_at)(void* text, Py_ssize_t pos, Py_UCS4 ch);
    void* (*point_to)(void* text, Py_ssize_t pos);
    PyThread_type_lock lock; /* A lock for accessing the state across threads. */
    RE_FuzzyInfo fuzzy_info; /* Info about fuzzy matching. */
    RE_FuzzyGuards* fuzzy_guards; /* The guards for a fuzzy match. */
    size_t total_errors; /* The total number of errors of a fuzzy match. */
    size_t total_cost; /* The total cost of a fuzzy match. */
    size_t max_cost; /* The maximum permitted fuzzy cost. */
    /* The group call stack. */
    RE_GroupCallFrame* first_group_call_frame;
    RE_GroupCallFrame* current_group_call_frame;
    RE_GuardList* group_call_guard_list;
    RE_SearchPosition search_positions[MAX_SEARCH_POSITIONS]; /* Where the search matches next. */
    size_t capture_change; /* Incremented every time a captive group changes. */
    Py_ssize_t req_pos; /* The position where the required string matched. */
    Py_ssize_t req_end; /* The end position where the required string matched. */
    RE_UINT16 iterations; /* The number of iterations the matching engine has performed since checking for KeyboardInterrupt. */
    BOOL is_unicode; /* Whether the string to be matched is Unicode. */
    BOOL should_release; /* Whether the buffer should be released. */
    BOOL overlapped; /* Whether the matches can be overlapped. */
    BOOL reverse; /* Whether it's a reverse pattern. */
    BOOL visible_captures; /* Whether the 'captures' method will be visible. */
    BOOL zero_width; /* Whether to enable the correct handling of zero-width matches. */
    BOOL must_advance; /* Whether the end of the match must advance past its start. */
    BOOL is_multithreaded; /* Whether to release the GIL while matching. */
    BOOL too_few_errors; /* Whether there were too few fuzzy errors. */
    BOOL match_all; /* Whether to match all of the string ('fullmatch'). */
} RE_State;

/* Storage for the regex state and thread state.
 *
 * Scanner objects can sometimes be shared across threads, which means that
 * their RE_State structs are also shared. This isn't safe when the GIL is
 * released, so in such instances we have a lock (mutex) in the RE_State struct
 * to protect it during matching. We also need a thread-safe place to store the
 * thread state when releasing the GIL.
 */
typedef struct RE_SafeState {
    RE_State* re_state;
    PyThreadState* thread_state;
} RE_SafeState;

/* The PatternObject created from a regular expression. */
typedef struct PatternObject {
    PyObject_HEAD
    PyObject* pattern; /* Pattern source (or None). */
    RE_CODE flags; /* Flags used when compiling pattern source. */
    PyObject* weakreflist; /* List of weak references */
    /* Nodes into which the regular expression is compiled. */
    RE_Node* start_node;
    RE_Node* start_test;
    size_t true_group_count; /* The true number of capture groups. */
    size_t public_group_count; /* The number of public capture groups. */
    size_t repeat_count; /* The number of repeats. */
    Py_ssize_t group_end_index; /* The number of group closures. */
    PyObject* groupindex;
    PyObject* indexgroup;
    PyObject* named_lists;
    PyObject* named_list_indexes;
    /* Storage for the pattern nodes. */
    size_t node_capacity;
    size_t node_count;
    RE_Node** node_list;
    /* Info about the capture groups. */
    size_t group_info_capacity;
    RE_GroupInfo* group_info;
    /* Info about the call_refs. */
    size_t call_ref_info_capacity;
    size_t call_ref_info_count;
    RE_CallRefInfo* call_ref_info;
    Py_ssize_t pattern_call_ref;
    /* Info about the repeats. */
    size_t repeat_info_capacity;
    RE_RepeatInfo* repeat_info;
    size_t min_width; /* The minimum width of the string to match (assuming it isn't a fuzzy pattern). */
    RE_EncodingTable* encoding; /* Encoding handlers. */
    RE_GroupData* groups_storage;
    RE_RepeatData* repeats_storage;
    size_t fuzzy_count; /* The number of fuzzy sections. */
    Py_ssize_t req_offset; /* The offset to the required string. */
    RE_Node* req_string; /* The required string. */
    BOOL is_fuzzy; /* Whether it's a fuzzy pattern. */
    BOOL do_search_start; /* Whether to do an initial search. */
    BOOL recursive; /* Whether the entire pattern is recursive. */
} PatternObject;

/* The MatchObject created when a match is found. */
typedef struct MatchObject {
    PyObject_HEAD
    PyObject* string; /* Link to the target string or NULL if detached. */
    PyObject* substring; /* Link to (a substring of) the target string. */
    Py_ssize_t substring_offset; /* Offset into the target string. */
    PatternObject* pattern; /* Link to the regex (pattern) object. */
    Py_ssize_t pos; /* Start of current slice. */
    Py_ssize_t endpos; /* End of current slice. */
    Py_ssize_t match_start; /* Start of matched slice. */
    Py_ssize_t match_end; /* End of matched slice. */
    Py_ssize_t lastindex; /* Last group seen by the engine (-1 if none). */
    Py_ssize_t lastgroup; /* Last named group seen by the engine (-1 if none). */
    size_t group_count; /* The number of groups. */
    RE_GroupData* groups; /* The capture groups. */
    PyObject* regs;
} MatchObject;

/* The ScannerObject. */
typedef struct ScannerObject {
    PyObject_HEAD
    PatternObject* pattern;
    RE_State state;
    int status;
} ScannerObject;

/* The SplitterObject. */
typedef struct SplitterObject {
    PyObject_HEAD
    PatternObject* pattern;
    RE_State state;
    Py_ssize_t maxsplit;
    Py_ssize_t last_pos;
    Py_ssize_t split_count;
    Py_ssize_t index;
    int status;
} SplitterObject;

/* Info used when compiling a pattern to nodes. */
typedef struct RE_CompileArgs {
    RE_CODE* code; /* The start of the compiled pattern. */
    RE_CODE* end_code; /* The end of the compiled pattern. */
    PatternObject* pattern; /* The pattern object. */
    size_t min_width; /* The minimum width of the string to match (assuming it isn't a fuzzy pattern). */
    RE_Node* start; /* The start node. */
    RE_Node* end; /* The end node. */
    size_t repeat_depth; /* The nesting depth of the repeat. */
    BOOL forward; /* Whether it's a forward (not reverse) pattern. */
    BOOL visible_captures; /* Whether all of the captures will be visible. */
    BOOL has_captures; /* Whether the pattern has capture groups. */
    BOOL is_fuzzy; /* Whether the pattern (or some part of it) is fuzzy. */
    BOOL within_fuzzy; /* Whether the subpattern is within a fuzzy section. */
} RE_CompileArgs;

/* The string slices which will be concatenated to make the result string of
 * the 'sub' method.
 *
 * This allows us to avoid creating a list of slices if there of fewer than 2
 * of them. Empty strings aren't recorded, so if 'list' and 'item' are both
 * NULL then the result is an empty string.
 */
typedef struct JoinInfo {
    PyObject* list; /* The list of slices if there are more than 2 of them. */
    PyObject* item; /* The slice if there is only 1 of them. */
    BOOL reversed; /* Whether the slices have been found in reverse order. */
    BOOL is_unicode; /* Whether the string is Unicode. */
} JoinInfo;

typedef struct {
    RE_Node* new_node;
    Py_ssize_t new_text_pos;
    Py_ssize_t limit;
    Py_ssize_t new_string_pos;
    int step;
    int new_folded_pos;
    int folded_len;
    int new_gfolded_pos;
    int new_group_pos;
    int fuzzy_type;
    BOOL permit_insertion;
} RE_FuzzyData;

/* Function types for getting info from a MatchObject. */
typedef PyObject* (*RE_GetByIndexFunc)(MatchObject* self, Py_ssize_t index);

Py_LOCAL_INLINE(Py_ssize_t) abs_ssize_t(Py_ssize_t x) {
    return x >= 0 ? x : -x;
}

/* Gets a character at the given position assuming 1 byte per character. */
static Py_UCS4 bytes1_char_at(void* text, Py_ssize_t pos) {
    return *((Py_UCS1*)text + pos);
}

/* Sets a character at the given position assuming 1 byte per character. */
static void bytes1_set_char_at(void* text, Py_ssize_t pos, Py_UCS4 ch) {
    *((Py_UCS1*)text + pos) = (Py_UCS1)ch;
}

/* Gets a pointer to the character at the given position assuming 1 byte per
 * character.
 */
static void* bytes1_point_to(void* text, Py_ssize_t pos) {
    return (Py_UCS1*)text + pos;
}

/* Gets a character at the given position assuming 2 bytes per character. */
static Py_UCS4 bytes2_char_at(void* text, Py_ssize_t pos) {
    return *((Py_UCS2*)text + pos);
}

/* Sets a character at the given position assuming 2 bytes per character. */
static void bytes2_set_char_at(void* text, Py_ssize_t pos, Py_UCS4 ch) {
    *((Py_UCS2*)text + pos) = (Py_UCS2)ch;
}

/* Gets a pointer to the character at the given position assuming 2 bytes per
 * character.
 */
static void* bytes2_point_to(void* text, Py_ssize_t pos) {
    return (Py_UCS2*)text + pos;
}

/* Gets a character at the given position assuming 4 bytes per character. */
static Py_UCS4 bytes4_char_at(void* text, Py_ssize_t pos) {
    return *((Py_UCS4*)text + pos);
}

/* Sets a character at the given position assuming 4 bytes per character. */
static void bytes4_set_char_at(void* text, Py_ssize_t pos, Py_UCS4 ch) {
    *((Py_UCS4*)text + pos) = (Py_UCS4)ch;
}

/* Gets a pointer to the character at the given position assuming 4 bytes per
 * character.
 */
static void* bytes4_point_to(void* text, Py_ssize_t pos) {
    return (Py_UCS4*)text + pos;
}

/* Default for whether the current text position is on a boundary. */
static BOOL at_boundary_always(RE_State* state, Py_ssize_t text_pos) {
    return TRUE;
}

/* ASCII-specific. */

static BOOL unicode_has_property(RE_CODE property, Py_UCS4 ch);

/* Checks whether a character has the given property. */
static BOOL ascii_has_property(RE_CODE property, Py_UCS4 ch) {
    if (ch > RE_ASCII_MAX) {
        /* Outside the ASCII range. */
        RE_UINT32 value;

        value = property & 0xFFFF;

        return value == 0;
    }

    return unicode_has_property(property, ch);
}

/* Converts a character to lowercase. */
static Py_UCS4 ascii_lower(Py_UCS4 ch) {
    if (ch > RE_ASCII_MAX || !re_get_uppercase(ch))
        return ch;

    return ch ^ 0x20;
}

/* Converts a character to uppercase. */
static Py_UCS4 ascii_upper(Py_UCS4 ch) {
    if (ch > RE_ASCII_MAX || !re_get_lowercase(ch))
        return ch;

    return ch ^ 0x20;
}

/* Checks whether the current text position is on a word boundary. */
static BOOL ascii_at_boundary(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && ascii_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && ascii_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return before != after;
}

/* Checks whether the current text position is at the start of a word. */
static BOOL ascii_at_word_start(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && ascii_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && ascii_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return !before && after;
}

/* Checks whether the current text position is at the end of a word. */
static BOOL ascii_at_word_end(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && ascii_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && ascii_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return before && !after;
}

/* Checks whether a character is a line separator. */
static BOOL ascii_is_line_sep(Py_UCS4 ch) {
    return 0x0A <= ch && ch <= 0x0D;
}

/* Checks whether the current text position is at the start of a line. */
static BOOL ascii_at_line_start(RE_State* state, Py_ssize_t text_pos) {
    Py_UCS4 ch;

    if (text_pos == 0)
        return TRUE;

    ch = state->char_at(state->text, text_pos - 1);

    if (ch == 0x0D)
        /* No line break inside CRLF. */
        return text_pos >= state->text_length || state->char_at(state->text,
          text_pos) != 0x0A;

    return 0x0A <= ch && ch <= 0x0D;
}

/* Checks whether the current text position is at the end of a line. */
static BOOL ascii_at_line_end(RE_State* state, Py_ssize_t text_pos) {
    Py_UCS4 ch;

    if (text_pos >= state->text_length)
        return TRUE;

    ch = state->char_at(state->text, text_pos);

    if (ch == 0x0A)
        /* No line break inside CRLF. */
        return text_pos >= 1 || state->char_at(state->text, text_pos - 1) !=
          0x0D;

    return 0x0A <= ch && ch <= 0x0D;
}

/* Checks whether a character could be Turkic (variants of I/i). For ASCII, it
 * won't be.
 */
static BOOL ascii_possible_turkic(Py_UCS4 ch) {
    return FALSE;
}

/* Gets all the cases of a character. */
static int ascii_all_cases(Py_UCS4 ch, Py_UCS4* codepoints) {
    int count;

    count = 0;

    codepoints[count++] = ch;

    if (('A' <= ch && ch <= 'Z') || ('a' <= ch && ch <= 'z'))
        /* It's a letter, so add the other case. */
        codepoints[count++] = ch ^ 0x20;

    return count;
}

/* Returns a character with its case folded. */
static Py_UCS4 ascii_simple_case_fold(Py_UCS4 ch) {
    if ('A' <= ch && ch <= 'Z')
        /* Uppercase folds to lowercase. */
        return ch ^ 0x20;

    return ch;
}

/* Returns a character with its case folded. */
static int ascii_full_case_fold(Py_UCS4 ch, Py_UCS4* folded) {
    if ('A' <= ch && ch <= 'Z')
        /* Uppercase folds to lowercase. */
        folded[0] = ch ^ 0x20;
    else
        folded[0] = ch;

    return 1;
}

/* Gets all the case variants of Turkic 'I'. The given character will be listed
 * first.
 */
static int ascii_all_turkic_i(Py_UCS4 ch, Py_UCS4* cases) {
    int count;

    count = 0;

    cases[count++] = ch;

    if (ch != 'I')
        cases[count++] = 'I';

    if (ch != 'i')
        cases[count++] = 'i';

    return count;
}

/* The handlers for ASCII characters. */
static RE_EncodingTable ascii_encoding = {
    ascii_has_property,
    ascii_lower,
    ascii_upper,
    ascii_upper, /* For ASCII, titlecase is the same as uppercase. */
    ascii_at_boundary,
    ascii_at_word_start,
    ascii_at_word_end,
    ascii_at_boundary, /* No special "default word boundary" for ASCII. */
    ascii_at_word_start, /* No special "default start of word" for ASCII. */
    ascii_at_word_end, /* No special "default end of a word" for ASCII. */
    at_boundary_always, /* No special "grapheme boundary" for ASCII. */
    ascii_is_line_sep,
    ascii_at_line_start,
    ascii_at_line_end,
    ascii_possible_turkic,
    ascii_all_cases,
    ascii_simple_case_fold,
    ascii_full_case_fold,
    ascii_all_turkic_i,
};

/* Locale-specific. */

/* Checks whether a character has the given property. */
static BOOL locale_has_property(RE_CODE property, Py_UCS4 ch) {
    RE_UINT32 value;
    RE_UINT32 v;

    value = property & 0xFFFF;

    if (ch > RE_LOCALE_MAX)
        /* Outside the locale range. */
        return value == 0;

    switch (property >> 16) {
    case RE_PROP_ALNUM >> 16:
        v = isalnum(ch) != 0;
        break;
    case RE_PROP_ALPHA >> 16:
        v = isalpha(ch) != 0;
        break;
    case RE_PROP_ANY >> 16:
        v = 1;
        break;
    case RE_PROP_ASCII >> 16:
        v = ch <= RE_ASCII_MAX;
        break;
    case RE_PROP_ASSIGNED >> 16:
        v = ch <= RE_LOCALE_MAX;
        break;
    case RE_PROP_BLANK >> 16:
        v = ch == '\t' || ch == ' ';
        break;
    case RE_PROP_GC:
        switch (property) {
        case RE_PROP_CNTRL:
            v = iscntrl(ch) ? value : 0xFFFF;
            break;
        case RE_PROP_DIGIT:
            v = isdigit(ch) ? value : 0xFFFF;
            break;
        case RE_PROP_GC_LL:
            v = islower(ch) ? value : 0xFFFF;
            break;
        case RE_PROP_GC_LU:
            v = isupper(ch) ? value : 0xFFFF;
            break;
        case RE_PROP_PUNCT:
            v = ispunct(ch) ? value : 0xFFFF;
            break;
        default:
            v = 0xFFFF;
            break;
        }
        break;
    case RE_PROP_GRAPH >> 16:
        v = isgraph(ch) != 0;
        break;
    case RE_PROP_LOWER >> 16:
        v = islower(ch) != 0;
        break;
    case RE_PROP_PRINT >> 16:
        v = isprint(ch) != 0;
        break;
    case RE_PROP_SPACE >> 16:
        v = isspace(ch) != 0;
        break;
    case RE_PROP_UPPER >> 16:
        v = isupper(ch) != 0;
        break;
    case RE_PROP_WORD >> 16:
        v = ch == '_' || isalnum(ch) != 0;
        break;
    case RE_PROP_XDIGIT >> 16:
        v = re_get_hex_digit(ch) != 0;
        break;
    default:
        v = 0;
        break;
    }

    return v == value;
}

/* Converts a character to lowercase. */
static Py_UCS4 locale_lower(Py_UCS4 ch) {
    if (ch > RE_LOCALE_MAX)
        return ch;

    return tolower(ch);
}

/* Converts a character to uppercase. */
static Py_UCS4 locale_upper(Py_UCS4 ch) {
    if (ch > RE_LOCALE_MAX)
        return ch;

    return toupper(ch);
}

/* Checks whether the current text position is on a word boundary. */
static BOOL locale_at_boundary(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && locale_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && locale_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return before != after;
}

/* Checks whether the current text position is at the start of a word. */
static BOOL locale_at_word_start(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && locale_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && locale_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return !before && after;
}

/* Checks whether the current text position is at the end of a word. */
static BOOL locale_at_word_end(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && locale_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && locale_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return before && !after;
}

/* Checks whether a character could be Turkic (variants of I/i). */
static BOOL locale_possible_turkic(Py_UCS4 ch) {
    return toupper(ch) == 'I' || tolower(ch) == 'i';
}

/* Gets all the cases of a character. */
static int locale_all_cases(Py_UCS4 ch, Py_UCS4* codepoints) {
    int count;
    Py_UCS4 other;

    count = 0;

    codepoints[count++] = ch;

    other = toupper(ch);
    if (other != ch)
        codepoints[count++] = other;

    other = tolower(ch);
    if (other != ch)
        codepoints[count++] = other;

    return count;
}

/* Returns a character with its case folded. */
static Py_UCS4 locale_simple_case_fold(Py_UCS4 ch) {
    if (ch <= RE_LOCALE_MAX)
        return tolower(ch);

    return ch;
}

/* Returns a character with its case folded. */
static int locale_full_case_fold(Py_UCS4 ch, Py_UCS4* folded) {
    if (ch <= RE_LOCALE_MAX)
        folded[0] = tolower(ch);
    else
        folded[0] = ch;

    return 1;
}

/* Gets all the case variants of Turkic 'I'. The given character will be listed
 * first.
 */
static int locale_all_turkic_i(Py_UCS4 ch, Py_UCS4* cases) {
    int count;
    Py_UCS4 other;

    count = 0;

    cases[count++] = ch;

    if (ch != 'I')
        cases[count++] = 'I';

    if (ch != 'i')
        cases[count++] = 'i';

    /* Uppercase 'i' will be either dotted (Turkic) or dotless (non-Turkic). */
    other = toupper('i');
    if (other != ch && other != 'I')
        cases[count++] = other;

    /* Lowercase 'I' will be either dotless (Turkic) or dotted (non-Turkic). */
    other = tolower('I');
    if (other != ch && other != 'i')
        cases[count++] = other;

    return count;
}

/* The handlers for locale characters. */
static RE_EncodingTable locale_encoding = {
    locale_has_property,
    locale_lower,
    locale_upper,
    locale_upper, /* For locale, titlecase is the same as uppercase. */
    locale_at_boundary,
    locale_at_word_start,
    locale_at_word_end,
    locale_at_boundary, /* No special "default word boundary" for locale. */
    locale_at_word_start, /* No special "default start of a word" for locale. */
    locale_at_word_end, /* No special "default end of a word" for locale. */
    at_boundary_always, /* No special "grapheme boundary" for locale. */
    ascii_is_line_sep, /* Assume locale line separators are same as ASCII. */
    ascii_at_line_start, /* Assume locale line separators are same as ASCII. */
    ascii_at_line_end, /* Assume locale line separators are same as ASCII. */
    locale_possible_turkic,
    locale_all_cases,
    locale_simple_case_fold,
    locale_full_case_fold,
    locale_all_turkic_i,
};

/* Unicode-specific. */

/* Checks whether a Unicode character has the given property. */
static BOOL unicode_has_property(RE_CODE property, Py_UCS4 ch) {
    RE_UINT32 prop;
    RE_UINT32 value;
    RE_UINT32 v;

    prop = property >> 16;
    if (prop >= sizeof(re_get_property) / sizeof(re_get_property[0]))
        return FALSE;

    value = property & 0xFFFF;
    v = re_get_property[prop](ch);

    if (v == value)
        return TRUE;

    if (prop == RE_PROP_GC) {
        switch (value) {
        case RE_PROP_C:
            return (RE_PROP_C_MASK & (1 << v)) != 0;
        case RE_PROP_L:
            return (RE_PROP_L_MASK & (1 << v)) != 0;
        case RE_PROP_M:
            return (RE_PROP_M_MASK & (1 << v)) != 0;
        case RE_PROP_N:
            return (RE_PROP_N_MASK & (1 << v)) != 0;
        case RE_PROP_P:
            return (RE_PROP_P_MASK & (1 << v)) != 0;
        case RE_PROP_S:
            return (RE_PROP_S_MASK & (1 << v)) != 0;
        case RE_PROP_Z:
            return (RE_PROP_Z_MASK & (1 << v)) != 0;
        }
    }

    return FALSE;
}

/* Converts a Unicode character to lowercase. */
static Py_UCS4 unicode_lower(Py_UCS4 ch) {
    return Py_UNICODE_TOLOWER((Py_UCS4)ch);
}

/* Converts a Unicode character to uppercase. */
static Py_UCS4 unicode_upper(Py_UCS4 ch) {
    return Py_UNICODE_TOUPPER((Py_UCS4)ch);
}

/* Converts a Unicode character to titlecase. */
static Py_UCS4 unicode_title(Py_UCS4 ch) {
    return Py_UNICODE_TOTITLE((Py_UCS4)ch);
}

/* Checks whether the current text position is on a word boundary. */
static BOOL unicode_at_boundary(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && unicode_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && unicode_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return before != after;
}

/* Checks whether the current text position is at the start of a word. */
static BOOL unicode_at_word_start(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && unicode_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && unicode_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return !before && after;
}

/* Checks whether the current text position is at the end of a word. */
static BOOL unicode_at_word_end(RE_State* state, Py_ssize_t text_pos) {
    BOOL before;
    BOOL after;

    before = text_pos > 0 && unicode_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos - 1));
    after = text_pos < state->text_length && unicode_has_property(RE_PROP_WORD,
      state->char_at(state->text, text_pos));

    return before && !after;
}

/* Checks whether a character is a Unicode vowel.
 *
 * Only a limited number are treated as vowels.
 */
Py_LOCAL_INLINE(BOOL) is_unicode_vowel(Py_UCS4 ch) {
    switch (unicode_lower(ch)) {
    case 'a': case 0xE0: case 0xE1: case 0xE2:
    case 'e': case 0xE8: case 0xE9: case 0xEA:
    case 'i': case 0xEC: case 0xED: case 0xEE:
    case 'o': case 0xF2: case 0xF3: case 0xF4:
    case 'u': case 0xF9: case 0xFA: case 0xFB:
        return TRUE;
    default:
        return FALSE;
    }
}

/* Checks whether the current text position is on a default word boundary.
 *
 * The rules are defined here:
 * http://www.unicode.org/reports/tr29/#Default_Word_Boundaries
 */
static BOOL unicode_at_default_boundary(RE_State* state, Py_ssize_t text_pos) {
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    int prop;
    int prop_m1;
    Py_ssize_t pos_m1;
    Py_ssize_t pos_m2;
    int prop_m2;
    Py_ssize_t pos_p0;
    int prop_p0;
    Py_ssize_t pos_p1;
    int prop_p1;

    /* Break at the start and end of the text. */
    if (text_pos <= 0 || text_pos >= state->text_length)
        return TRUE;

    char_at = state->char_at;
    text = state->text;

    prop = (int)re_get_word_break(char_at(text, text_pos));
    prop_m1 = (int)re_get_word_break(char_at(text, text_pos - 1));

    /* Don't break within CRLF. */
    if (prop_m1 == RE_BREAK_CR && prop == RE_BREAK_LF)
        return FALSE;

    /* Otherwise break before and after Newlines (including CR and LF). */
    if (prop_m1 == RE_BREAK_NEWLINE || prop_m1 == RE_BREAK_CR || prop_m1 ==
      RE_BREAK_LF || prop == RE_BREAK_NEWLINE || prop == RE_BREAK_CR || prop ==
      RE_BREAK_LF)
        return TRUE;

    /* Get the property of the previous character. */
    pos_m1 = text_pos - 1;
    prop_m1 = RE_BREAK_OTHER;
    while (pos_m1 >= 0) {
        prop_m1 = (int)re_get_word_break(char_at(text, pos_m1));
        if (prop_m1 != RE_BREAK_EXTEND && prop_m1 != RE_BREAK_FORMAT)
            break;

        --pos_m1;
    }

    /* Get the property of the preceding character. */
    pos_m2 = pos_m1 - 1;
    prop_m2 = RE_BREAK_OTHER;
    while (pos_m2 >= 0) {
        prop_m2 = (int)re_get_word_break(char_at(text, pos_m2));
        if (prop_m2 != RE_BREAK_EXTEND && prop_m2 != RE_BREAK_FORMAT)
            break;

        --pos_m2;
    }

    /* Get the property of the next character. */
    pos_p0 = text_pos;
    prop_p0 = prop;
    while (pos_p0 < state->text_length) {
        prop_p0 = (int)re_get_word_break(char_at(text, pos_p0));
        if (prop_p0 != RE_BREAK_EXTEND && prop_p0 != RE_BREAK_FORMAT)
            break;

        ++pos_p0;
    }

    /* Get the property of the following character. */
    pos_p1 = pos_p0 + 1;
    prop_p1 = RE_BREAK_OTHER;
    while (pos_p1 < state->text_length) {
        prop_p1 = (int)re_get_word_break(char_at(text, pos_p1));
        if (prop_p1 != RE_BREAK_EXTEND && prop_p1 != RE_BREAK_FORMAT)
            break;

        ++pos_p1;
    }

    /* Don't break between most letters. */
    if ((prop_m1 == RE_BREAK_ALETTER || prop_m1 == RE_BREAK_HEBREWLETTER) &&
      (prop_p0 == RE_BREAK_ALETTER || prop_p0 == RE_BREAK_HEBREWLETTER))
        return FALSE;

    /* Break between apostrophe and vowels (French, Italian). */
    if (pos_m1 >= 0 && char_at(text, pos_m1) == '\'' &&
      is_unicode_vowel(char_at(text, text_pos)))
        return TRUE;

    /* Don't break letters across certain punctuation. */
    if ((prop_m1 == RE_BREAK_ALETTER || prop_m1 == RE_BREAK_HEBREWLETTER) &&
      (prop_p0 == RE_BREAK_MIDLETTER || prop_p0 == RE_BREAK_MIDNUMLET ||
      prop_p0 == RE_BREAK_SINGLEQUOTE) && (prop_p1 == RE_BREAK_ALETTER ||
      prop_p1 == RE_BREAK_HEBREWLETTER))
        return FALSE;
    if ((prop_m2 == RE_BREAK_ALETTER || prop_m2 == RE_BREAK_HEBREWLETTER) &&
      (prop_m1 == RE_BREAK_MIDLETTER || prop_m1 == RE_BREAK_MIDNUMLET ||
      prop_m1 == RE_BREAK_SINGLEQUOTE) && (prop_p0 == RE_BREAK_ALETTER ||
      prop_p0 == RE_BREAK_HEBREWLETTER))
        return FALSE;
    if (prop_m1 == RE_BREAK_HEBREWLETTER && prop_p0 == RE_BREAK_SINGLEQUOTE)
        return FALSE;
    if (prop_m1 == RE_BREAK_HEBREWLETTER && prop_p0 == RE_BREAK_DOUBLEQUOTE &&
      prop_p1 == RE_BREAK_HEBREWLETTER)
        return FALSE;
    if (prop_m2 == RE_BREAK_HEBREWLETTER && prop_m1 == RE_BREAK_DOUBLEQUOTE &&
      prop_p0 == RE_BREAK_HEBREWLETTER)
        return FALSE;

    /* Don't break within sequences of digits, or digits adjacent to letters
     * ("3a", or "A3").
     */
    if (prop_m1 == RE_BREAK_NUMERIC && prop_p0 == RE_BREAK_NUMERIC)
        return FALSE;
    if ((prop_m1 == RE_BREAK_ALETTER || prop_m1 == RE_BREAK_HEBREWLETTER) &&
      prop_p0 == RE_BREAK_NUMERIC)
        return FALSE;
    if (prop_m1 == RE_BREAK_NUMERIC && (prop_p0 == RE_BREAK_ALETTER || prop_p0
      == RE_BREAK_HEBREWLETTER))
        return FALSE;

    /* Don't break within sequences, such as "3.2" or "3,456.789". */
    if (prop_m2 == RE_BREAK_NUMERIC && (prop_m1 == RE_BREAK_MIDNUM || prop_m1
      == RE_BREAK_MIDNUMLET || prop_m1 == RE_BREAK_SINGLEQUOTE) && prop_p0 ==
      RE_BREAK_NUMERIC)
        return FALSE;
    if (prop_m1 == RE_BREAK_NUMERIC && (prop_p0 == RE_BREAK_MIDNUM || prop_p0
      == RE_BREAK_MIDNUMLET || prop_p0 == RE_BREAK_SINGLEQUOTE) && prop_p1 ==
      RE_BREAK_NUMERIC)
        return FALSE;

    /* Don't break between Katakana. */
    if (prop_m1 == RE_BREAK_KATAKANA && prop_p0 == RE_BREAK_KATAKANA)
        return FALSE;

    /* Don't break from extenders. */
    if ((prop_m1 == RE_BREAK_ALETTER || prop_m1 == RE_BREAK_HEBREWLETTER ||
      prop_m1 == RE_BREAK_NUMERIC || prop_m1 == RE_BREAK_KATAKANA || prop_m1 ==
      RE_BREAK_EXTENDNUMLET) && prop_p0 == RE_BREAK_EXTENDNUMLET)
        return FALSE;
    if (prop_m1 == RE_BREAK_EXTENDNUMLET && (prop_p0 == RE_BREAK_ALETTER ||
      prop_p0 == RE_BREAK_HEBREWLETTER || prop_p0 == RE_BREAK_NUMERIC ||
      prop_p0 == RE_BREAK_KATAKANA))
        return FALSE;

    /* Don't break between regional indicator symbols. */
    if (prop_m1 == RE_BREAK_REGIONALINDICATOR && prop_p0 ==
      RE_BREAK_REGIONALINDICATOR)
        return FALSE;

    /* Otherwise, break everywhere (including around ideographs). */
    return TRUE;
}

/* Checks whether the current text position is at the start/end of a word. */
Py_LOCAL_INLINE(BOOL) unicode_at_default_word_start_or_end(RE_State* state,
  Py_ssize_t text_pos, BOOL at_start) {
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    BOOL before;
    BOOL after;
    Py_UCS4 char_0;
    Py_UCS4 char_m1;
    int prop;
    int prop_m1;
    Py_ssize_t pos_m1;
    Py_UCS4 char_p1;
    Py_ssize_t pos_p1;
    int prop_p1;
    Py_ssize_t pos_m2;
    Py_UCS4 char_m2;
    int prop_m2;

    char_at = state->char_at;
    text = state->text;

    /* At the start or end of the text. */
    if (text_pos <= 0 || text_pos >= state->text_length) {
        before = text_pos > 0 && unicode_has_property(RE_PROP_WORD,
          char_at(state->text, text_pos - 1));
        after = text_pos < state->text_length &&
          unicode_has_property(RE_PROP_WORD, char_at(state->text, text_pos));

        return before != at_start && after == at_start;
    }

    char_0 = char_at(state->text, text_pos);
    char_m1 = char_at(state->text, text_pos - 1);
    prop = (int)re_get_word_break(char_0);
    prop_m1 = (int)re_get_word_break(char_m1);

    /* No break within CRLF. */
    if (prop_m1 == RE_BREAK_CR && prop == RE_BREAK_LF)
        return FALSE;

    /* Break before and after Newlines (including CR and LF). */
    if (prop_m1 == RE_BREAK_NEWLINE || prop_m1 == RE_BREAK_CR || prop_m1 ==
      RE_BREAK_LF || prop == RE_BREAK_NEWLINE || prop == RE_BREAK_CR || prop ==
      RE_BREAK_LF) {
        before = unicode_has_property(RE_PROP_WORD, char_m1);
        after = unicode_has_property(RE_PROP_WORD, char_0);

        return before != at_start && after == at_start;
    }

    /* No break just before Format or Extend characters. */
    if (prop == RE_BREAK_EXTEND || prop == RE_BREAK_FORMAT)
        return FALSE;

    /* Get the property of the previous character. */
    pos_m1 = text_pos - 1;
    prop_m1 = RE_BREAK_OTHER;
    while (pos_m1 >= 0) {
        char_m1 = char_at(text, pos_m1);
        prop_m1 = (int)re_get_word_break(char_m1);
        if (prop_m1 != RE_BREAK_EXTEND && prop_m1 != RE_BREAK_FORMAT)
            break;
        --pos_m1;
    }

    /* No break between most letters. */
    if (prop_m1 == RE_BREAK_ALETTER && prop == RE_BREAK_ALETTER)
        return FALSE;

    if (pos_m1 >= 0 && char_m1 == '\'' && is_unicode_vowel(char_0))
        return TRUE;

    pos_p1 = text_pos + 1;
    prop_p1 = RE_BREAK_OTHER;
    while (pos_p1 < state->text_length) {
        char_p1 = char_at(text, pos_p1);
        prop_p1 = (int)re_get_word_break(char_p1);
        if (prop_p1 != RE_BREAK_EXTEND && prop_p1 != RE_BREAK_FORMAT)
            break;
        --pos_p1;
    }

    /* No break letters across certain punctuation. */
    if (prop_m1 == RE_BREAK_ALETTER && (prop == RE_BREAK_MIDLETTER || prop ==
      RE_BREAK_MIDNUMLET) && prop_p1 == RE_BREAK_ALETTER)
        return FALSE;

    pos_m2 = pos_m1 - 1;
    prop_m2 = RE_BREAK_OTHER;
    while (pos_m2 >= 0) {
        char_m2 = char_at(text, pos_m2);
        prop_m2 = (int)re_get_word_break(char_m2);
        if (prop_m2 != RE_BREAK_EXTEND && prop_m1 != RE_BREAK_FORMAT)
            break;
        --pos_m2;
    }

    if (prop_m2 == RE_BREAK_ALETTER && (prop_m1 == RE_BREAK_MIDLETTER ||
      prop_m1 == RE_BREAK_MIDNUMLET) && prop == RE_BREAK_ALETTER)
        return FALSE;

    /* No break within sequences of digits, or digits adjacent to letters
     * ("3a", or "A3").
     */
    if ((prop_m1 == RE_BREAK_NUMERIC || prop_m1 == RE_BREAK_ALETTER) && prop ==
      RE_BREAK_NUMERIC)
        return FALSE;

    if (prop_m1 == RE_BREAK_NUMERIC && prop == RE_BREAK_ALETTER)
        return FALSE;

    /* No break within sequences, such as "3.2" or "3,456.789". */
    if (prop_m2 == RE_BREAK_NUMERIC && (prop_m1 == RE_BREAK_MIDNUM || prop_m1
      == RE_BREAK_MIDNUMLET) && prop == RE_BREAK_NUMERIC)
        return FALSE;

    if (prop_m1 == RE_BREAK_NUMERIC && (prop == RE_BREAK_MIDNUM || prop ==
      RE_BREAK_MIDNUMLET) && prop_p1 == RE_BREAK_NUMERIC)
        return FALSE;

    /* No break between Katakana. */
    if (prop_m1 == RE_BREAK_KATAKANA && prop == RE_BREAK_KATAKANA)
        return FALSE;

    /* No break from extenders. */
    if ((prop_m1 == RE_BREAK_ALETTER || prop_m1 == RE_BREAK_NUMERIC || prop_m1
      == RE_BREAK_KATAKANA || prop_m1 == RE_BREAK_EXTENDNUMLET) && prop ==
      RE_BREAK_EXTENDNUMLET)
        return FALSE;

    if (prop_m1 == RE_BREAK_EXTENDNUMLET && (prop == RE_BREAK_ALETTER || prop
      == RE_BREAK_NUMERIC || prop == RE_BREAK_KATAKANA))
        return FALSE;

    /* Otherwise, break everywhere (including around ideographs). */
    before = unicode_has_property(RE_PROP_WORD, char_m1);
    after = unicode_has_property(RE_PROP_WORD, char_0);

    return before != at_start && after == at_start;
}

/* Checks whether the current text position is at the start of a word. */
static BOOL unicode_at_default_word_start(RE_State* state, Py_ssize_t text_pos)
  {
    return unicode_at_default_word_start_or_end(state, text_pos, TRUE);
}

/* Checks whether the current text position is at the end of a word. */
static BOOL unicode_at_default_word_end(RE_State* state, Py_ssize_t text_pos) {
    return unicode_at_default_word_start_or_end(state, text_pos, FALSE);
}

/* Checks whether the current text position is on a grapheme boundary.
 *
 * The rules are defined here:
 * http://www.unicode.org/reports/tr29/#Grapheme_Cluster_Boundaries
 */
static BOOL unicode_at_grapheme_boundary(RE_State* state, Py_ssize_t text_pos)
  {
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    int prop;
    int prop_m1;

    /* Break at the start and end of the text. */
    if (text_pos <= 0 || text_pos >= state->text_length)
        return TRUE;

    char_at = state->char_at;
    text = state->text;

    prop = (int)re_get_grapheme_cluster_break(char_at(text, text_pos));
    prop_m1 = (int)re_get_grapheme_cluster_break(char_at(text, text_pos - 1));

    /* Don't break within CRLF. */
    if (prop_m1 == RE_GBREAK_CR && prop == RE_GBREAK_LF)
        return FALSE;

    /* Otherwise break before and after controls (including CR and LF). */
    if (prop_m1 == RE_GBREAK_CONTROL || prop_m1 == RE_GBREAK_CR || prop_m1 ==
      RE_GBREAK_LF || prop == RE_GBREAK_CONTROL || prop == RE_GBREAK_CR || prop
      == RE_GBREAK_LF)
        return TRUE;

    /* Don't break Hangul syllable sequences. */
    if (prop_m1 == RE_GBREAK_L && (prop == RE_GBREAK_L || prop == RE_GBREAK_V
      || prop == RE_GBREAK_LV || prop == RE_GBREAK_LVT))
        return FALSE;
    if ((prop_m1 == RE_GBREAK_LV || prop_m1 == RE_GBREAK_V) && (prop ==
      RE_GBREAK_V || prop == RE_GBREAK_T))
        return FALSE;
    if ((prop_m1 == RE_GBREAK_LVT || prop_m1 == RE_GBREAK_T) && (prop ==
      RE_GBREAK_T))
        return FALSE;

    /* Don't break between regional indicator symbols. */
    if (prop_m1 == RE_GBREAK_REGIONALINDICATOR && prop ==
      RE_GBREAK_REGIONALINDICATOR)
        return FALSE;

    /* Don't break just before Extend characters. */
    if (prop == RE_GBREAK_EXTEND)
        return FALSE;

    /* Don't break before SpacingMarks, or after Prepend characters. */
    if (prop == RE_GBREAK_SPACINGMARK)
        return FALSE;

    if (prop_m1 == RE_GBREAK_PREPEND)
        return FALSE;

    /* Otherwise, break everywhere. */
    return TRUE;
}

/* Checks whether a character is a line separator. */
static BOOL unicode_is_line_sep(Py_UCS4 ch) {
    return (0x0A <= ch && ch <= 0x0D) || ch == 0x85 || ch == 0x2028 || ch ==
      0x2029;
}

/* Checks whether the current text position is at the start of a line. */
static BOOL unicode_at_line_start(RE_State* state, Py_ssize_t text_pos) {
    Py_UCS4 ch;

    if (text_pos == 0)
        return TRUE;

    ch = state->char_at(state->text, text_pos - 1);

    if (ch == 0x0D)
        /* No line break inside CRLF. */
        return text_pos >= state->text_length || state->char_at(state->text,
          text_pos) != 0x0A;

    return (0x0A <= ch && ch <= 0x0D) || ch == 0x85 || ch == 0x2028 || ch ==
      0x2029;
}

/* Checks whether the current text position is at the end of a line. */
static BOOL unicode_at_line_end(RE_State* state, Py_ssize_t text_pos) {
    Py_UCS4 ch;

    if (text_pos >= state->text_length)
        return TRUE;

    ch = state->char_at(state->text, text_pos);

    if (ch == 0x0A)
        /* No line break inside CRLF. */
        return text_pos >= 1 || state->char_at(state->text, text_pos - 1) !=
          0x0D;

    return (0x0A <= ch && ch <= 0x0D) || ch == 0x85 || ch == 0x2028 || ch ==
      0x2029;
}

/* Checks whether a character could be Turkic (variants of I/i). */
static BOOL unicode_possible_turkic(Py_UCS4 ch) {
    return ch == 'I' || ch == 'i' || ch == 0x0130 || ch == 0x0131;
}

/* Gets all the cases of a character. */
static int unicode_all_cases(Py_UCS4 ch, Py_UCS4* codepoints) {
    return re_get_all_cases(ch, codepoints);
}

/* Returns a character with its case folded, unless it could be Turkic
 * (variants of I/i).
 */
static Py_UCS4 unicode_simple_case_fold(Py_UCS4 ch) {
    /* Is it a possible Turkic character? If so, pass it through unchanged. */
    if (ch == 'I' || ch == 'i' || ch == 0x0130 || ch == 0x0131)
        return ch;

    return (Py_UCS4)re_get_simple_case_folding(ch);
}

/* Returns a character with its case folded, unless it could be Turkic
 * (variants of I/i).
 */
static int unicode_full_case_fold(Py_UCS4 ch, Py_UCS4* folded) {
    /* Is it a possible Turkic character? If so, pass it through unchanged. */
    if (ch == 'I' || ch == 'i' || ch == 0x0130 || ch == 0x0131) {
        folded[0] = ch;
        return 1;
    }

    return re_get_full_case_folding(ch, folded);
}

/* Gets all the case variants of Turkic 'I'. */
static int unicode_all_turkic_i(Py_UCS4 ch, Py_UCS4* cases) {
    int count;

    count = 0;

    cases[count++] = ch;

    if (ch != 'I')
        cases[count++] = 'I';

    if (ch != 'i')
        cases[count++] = 'i';

    if (ch != 0x130)
        cases[count++] = 0x130;

    if (ch != 0x131)
        cases[count++] = 0x131;

    return count;

}

/* The handlers for Unicode characters. */
static RE_EncodingTable unicode_encoding = {
    unicode_has_property,
    unicode_lower,
    unicode_upper,
    unicode_title,
    unicode_at_boundary,
    unicode_at_word_start,
    unicode_at_word_end,
    unicode_at_default_boundary,
    unicode_at_default_word_start,
    unicode_at_default_word_end,
    unicode_at_grapheme_boundary,
    unicode_is_line_sep,
    unicode_at_line_start,
    unicode_at_line_end,
    unicode_possible_turkic,
    unicode_all_cases,
    unicode_simple_case_fold,
    unicode_full_case_fold,
    unicode_all_turkic_i,
};

Py_LOCAL_INLINE(PyObject*) get_object(char* module_name, char* object_name);

/* Sets the error message. */
Py_LOCAL_INLINE(void) set_error(int status, PyObject* object) {
    TRACE(("<<set_error>>\n"))

    if (!error_exception)
        error_exception = get_object("_" RE_MODULE "_core", "error");

    switch (status) {
    case RE_ERROR_BACKTRACKING:
        PyErr_SetString(error_exception, "too much backtracking");
        break;
    case RE_ERROR_CONCURRENT:
        PyErr_SetString(PyExc_ValueError, "concurrent not int or None");
        break;
    case RE_ERROR_GROUP_INDEX_TYPE:
        if (object)
            PyErr_Format(PyExc_TypeError,
              "group indices must be integers or strings, not %.200s",
              object->ob_type->tp_name);
        else
            PyErr_Format(PyExc_TypeError,
              "group indices must be integers or strings");
        break;
    case RE_ERROR_ILLEGAL:
        PyErr_SetString(PyExc_RuntimeError, "invalid RE code");
        break;
    case RE_ERROR_INDEX:
        PyErr_SetString(PyExc_TypeError, "string indices must be integers");
        break;
    case RE_ERROR_INTERRUPTED:
        /* An exception has already been raised, so let it fly. */
        break;
    case RE_ERROR_INVALID_GROUP_REF:
        PyErr_SetString(error_exception, "invalid group reference");
        break;
    case RE_ERROR_MEMORY:
        PyErr_NoMemory();
        break;
    case RE_ERROR_NOT_STRING:
        PyErr_Format(PyExc_TypeError, "expected string instance, %.200s found",
          object->ob_type->tp_name);
        break;
    case RE_ERROR_NOT_UNICODE:
        PyErr_Format(PyExc_TypeError,
          "expected unicode instance, %.200s found", object->ob_type->tp_name);
        break;
    case RE_ERROR_NO_SUCH_GROUP:
        PyErr_SetString(PyExc_IndexError, "no such group");
        break;
    case RE_ERROR_REPLACEMENT:
        PyErr_SetString(error_exception, "invalid replacement");
        break;
    default:
        /* Other error codes indicate compiler/engine bugs. */
        PyErr_SetString(PyExc_RuntimeError,
          "internal error in regular expression engine");
        break;
    }
}

/* Allocates memory.
 *
 * Sets the Python error handler and returns NULL if the allocation fails.
 */
Py_LOCAL_INLINE(void*) re_alloc(size_t size) {
    void* new_ptr;

    new_ptr = PyMem_Malloc(size);
    if (!new_ptr)
        set_error(RE_ERROR_MEMORY, NULL);

    return new_ptr;
}

/* Reallocates memory.
 *
 * Sets the Python error handler and returns NULL if the reallocation fails.
 */
Py_LOCAL_INLINE(void*) re_realloc(void* ptr, size_t size) {
    void* new_ptr;

    new_ptr = PyMem_Realloc(ptr, size);
    if (!new_ptr)
        set_error(RE_ERROR_MEMORY, NULL);

    return new_ptr;
}

/* Deallocates memory. */
Py_LOCAL_INLINE(void) re_dealloc(void* ptr) {
    PyMem_Free(ptr);
}

/* Releases the GIL if multithreading is enabled. */
Py_LOCAL_INLINE(void) release_GIL(RE_SafeState* safe_state) {
    if (safe_state->re_state->is_multithreaded)
        safe_state->thread_state = PyEval_SaveThread();
}

/* Acquires the GIL if multithreading is enabled. */
Py_LOCAL_INLINE(void) acquire_GIL(RE_SafeState* safe_state) {
    if (safe_state->re_state->is_multithreaded)
        PyEval_RestoreThread(safe_state->thread_state);
}

/* Allocates memory, holding the GIL during the allocation.
 *
 * Sets the Python error handler and returns NULL if the allocation fails.
 */
Py_LOCAL_INLINE(void*) safe_alloc(RE_SafeState* safe_state, size_t size) {
    void* new_ptr;

    acquire_GIL(safe_state);

    new_ptr = re_alloc(size);

    release_GIL(safe_state);

    return new_ptr;
}

/* Reallocates memory, holding the GIL during the reallocation.
 *
 * Sets the Python error handler and returns NULL if the reallocation fails.
 */
Py_LOCAL_INLINE(void*) safe_realloc(RE_SafeState* safe_state, void* ptr, size_t
  size) {
    void* new_ptr;

    acquire_GIL(safe_state);

    new_ptr = re_realloc(ptr, size);

    release_GIL(safe_state);

    return new_ptr;
}

/* Deallocates memory, holding the GIL during the deallocation. */
Py_LOCAL_INLINE(void) safe_dealloc(RE_SafeState* safe_state, void* ptr) {
    acquire_GIL(safe_state);

    re_dealloc(ptr);

    release_GIL(safe_state);
}

/* Checks for KeyboardInterrupt, holding the GIL during the check. */
Py_LOCAL_INLINE(BOOL) safe_check_signals(RE_SafeState* safe_state) {
    BOOL result;

    acquire_GIL(safe_state);

    result = (BOOL)PyErr_CheckSignals();

    release_GIL(safe_state);

    return result;
}

/* Checks whether a character is in a range. */
Py_LOCAL_INLINE(BOOL) in_range(Py_UCS4 lower, Py_UCS4 upper, Py_UCS4 ch) {
    return lower <= ch && ch <= upper;
}

/* Checks whether 2 characters are the same, ignoring case. */
static BOOL same_char_ign(RE_EncodingTable* encoding, Py_UCS4 ch1, Py_UCS4 ch2)
  {
    Py_UCS4 cases[RE_MAX_CASES];
    int count;
    int i;

    if (ch1 == ch2)
        return TRUE;

    count = encoding->all_cases(ch1, cases);

    for (i = 1; i < count; i++) {
        if (cases[i] == ch2)
            return TRUE;
    }

    return FALSE;
}

/* Checks whether a character has or hasn't the given property, ignoring case.
 */
Py_LOCAL_INLINE(BOOL) has_property_ign(RE_EncodingTable* encoding, RE_CODE
  property, Py_UCS4 ch) {
    RE_UINT32 prop;

    prop = property >> 16;

    /* We need to do special handling of case-sensitive properties according to
     * the 'encoding'.
     */
    if (encoding == &unicode_encoding) {
        /* We are working with Unicode. */
        if (property == RE_PROP_GC_LU || property == RE_PROP_GC_LL || property
          == RE_PROP_GC_LT) {
            RE_UINT32 value;

            value = re_get_general_category(ch);

            return value == RE_PROP_LU || value == RE_PROP_LL || value ==
              RE_PROP_LT;
        } else if (prop == RE_PROP_UPPERCASE || prop == RE_PROP_LOWERCASE)
            return (BOOL)re_get_cased(ch);

        /* The property is case-insensitive. */
        return unicode_has_property(property, ch);
    } else if (encoding == &ascii_encoding) {
        /* We are working with ASCII. */
        if (property == RE_PROP_GC_LU || property == RE_PROP_GC_LL || property
          == RE_PROP_GC_LT) {
            RE_UINT32 value;

            value = re_get_general_category(ch);

            return value == RE_PROP_LU || value == RE_PROP_LL || value ==
              RE_PROP_LT;
        } else if (prop == RE_PROP_UPPERCASE || prop == RE_PROP_LOWERCASE)
            return (BOOL)re_get_cased(ch);

        /* The property is case-insensitive. */
        return ascii_has_property(property, ch);
    } else {
        /* We are working with Locale. */
        if (property == RE_PROP_GC_LU || property == RE_PROP_GC_LL || property
          == RE_PROP_GC_LT)
            return (isupper(ch) || islower(ch)) != 0;
        else if (prop == RE_PROP_UPPERCASE || prop == RE_PROP_LOWERCASE)
            return (isupper(ch) || islower(ch)) != 0;

        /* The property is case-insensitive. */
        return locale_has_property(property, ch);
    }
}

/* Checks whether a character is in a range, ignoring case. */
Py_LOCAL_INLINE(BOOL) in_range_ign(RE_EncodingTable* encoding, Py_UCS4 lower,
  Py_UCS4 upper, Py_UCS4 ch) {
    Py_UCS4 cases[RE_MAX_CASES];
    int count;
    int i;

    count = encoding->all_cases(ch, cases);

    for (i = 0; i < count; i++) {
        if (in_range(lower, upper, cases[i]))
            return TRUE;
    }

    return FALSE;
}

Py_LOCAL_INLINE(BOOL) in_set_diff(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch);
Py_LOCAL_INLINE(BOOL) in_set_inter(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch);
Py_LOCAL_INLINE(BOOL) in_set_sym_diff(RE_EncodingTable* encoding, RE_Node*
  node, Py_UCS4 ch);
Py_LOCAL_INLINE(BOOL) in_set_union(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch);

/* Checks whether a character matches a set member. */
Py_LOCAL_INLINE(BOOL) matches_member(RE_EncodingTable* encoding, RE_Node*
  member, Py_UCS4 ch) {
    switch (member->op) {
    case RE_OP_CHARACTER:
        /* values are: char_code */
        TRACE(("%s %d %d\n", re_op_text[member->op], member->match,
          member->values[0]))
        return ch == member->values[0];
    case RE_OP_PROPERTY:
        /* values are: property */
        TRACE(("%s %d %d\n", re_op_text[member->op], member->match,
          member->values[0]))
        return encoding->has_property(member->values[0], ch);
    case RE_OP_RANGE:
        /* values are: lower, upper */
        TRACE(("%s %d %d %d\n", re_op_text[member->op], member->match,
          member->values[0], member->values[1]))
        return in_range(member->values[0], member->values[1], ch);
    case RE_OP_SET_DIFF:
        TRACE(("%s\n", re_op_text[member->op]))
        return in_set_diff(encoding, member, ch);
    case RE_OP_SET_INTER:
        TRACE(("%s\n", re_op_text[member->op]))
        return in_set_inter(encoding, member, ch);
    case RE_OP_SET_SYM_DIFF:
        TRACE(("%s\n", re_op_text[member->op]))
        return in_set_sym_diff(encoding, member, ch);
    case RE_OP_SET_UNION:
        TRACE(("%s\n", re_op_text[member->op]))
        return in_set_union(encoding, member, ch);
    case RE_OP_STRING:
    {
        /* values are: char_code, char_code, ... */
        size_t i;
        TRACE(("%s %d %d\n", re_op_text[member->op], member->match,
          member->value_count))

        for (i = 0; i < member->value_count; i++) {
            if (ch == member->values[i])
                return TRUE;
        }
        return FALSE;
    }
    default:
        return FALSE;
    }
}

/* Checks whether a character matches a set member, ignoring case. */
Py_LOCAL_INLINE(BOOL) matches_member_ign(RE_EncodingTable* encoding, RE_Node*
  member, int case_count, Py_UCS4* cases) {
    int i;

    for (i = 0; i < case_count; i++) {
        switch (member->op) {
        case RE_OP_CHARACTER:
            /* values are: char_code */
            TRACE(("%s %d %d\n", re_op_text[member->op], member->match,
              member->values[0]))
            if (cases[i] == member->values[0])
                return TRUE;
            break;
        case RE_OP_PROPERTY:
            /* values are: property */
            TRACE(("%s %d %d\n", re_op_text[member->op], member->match,
              member->values[0]))
            if (encoding->has_property(member->values[0], cases[i]))
                return TRUE;
            break;
        case RE_OP_RANGE:
            /* values are: lower, upper */
            TRACE(("%s %d %d %d\n", re_op_text[member->op], member->match,
              member->values[0], member->values[1]))
            if (in_range(member->values[0], member->values[1], cases[i]))
                return TRUE;
            break;
        case RE_OP_SET_DIFF:
            TRACE(("%s\n", re_op_text[member->op]))
            if (in_set_diff(encoding, member, cases[i]))
                return TRUE;
            break;
        case RE_OP_SET_INTER:
            TRACE(("%s\n", re_op_text[member->op]))
            if (in_set_inter(encoding, member, cases[i]))
                return TRUE;
            break;
        case RE_OP_SET_SYM_DIFF:
            TRACE(("%s\n", re_op_text[member->op]))
            if (in_set_sym_diff(encoding, member, cases[i]))
                return TRUE;
            break;
        case RE_OP_SET_UNION:
            TRACE(("%s\n", re_op_text[member->op]))
            if (in_set_union(encoding, member, cases[i]))
                return TRUE;
            break;
        case RE_OP_STRING:
        {
            size_t j;
            TRACE(("%s %d %d\n", re_op_text[member->op], member->match,
              member->value_count))

            for (j = 0; j < member->value_count; j++) {
                if (cases[i] == member->values[j])
                    return TRUE;
            }
            break;
        }
        default:
            return TRUE;
        }
    }

    return FALSE;
}

/* Checks whether a character is in a set difference. */
Py_LOCAL_INLINE(BOOL) in_set_diff(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch) {
    RE_Node* member;

    member = node->nonstring.next_2.node;

    if (matches_member(encoding, member, ch) != member->match)
        return FALSE;

    member = member->next_1.node;

    while (member) {
        if (matches_member(encoding, member, ch) == member->match)
            return FALSE;

        member = member->next_1.node;
    }

    return TRUE;
}

/* Checks whether a character is in a set difference, ignoring case. */
Py_LOCAL_INLINE(BOOL) in_set_diff_ign(RE_EncodingTable* encoding, RE_Node*
  node, int case_count, Py_UCS4* cases) {
    RE_Node* member;

    member = node->nonstring.next_2.node;

    if (matches_member_ign(encoding, member, case_count, cases) !=
      member->match)
        return FALSE;

    member = member->next_1.node;

    while (member) {
        if (matches_member_ign(encoding, member, case_count, cases) ==
          member->match)
            return FALSE;

        member = member->next_1.node;
    }

    return TRUE;
}

/* Checks whether a character is in a set intersection. */
Py_LOCAL_INLINE(BOOL) in_set_inter(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch) {
    RE_Node* member;

    member = node->nonstring.next_2.node;

    while (member) {
        if (matches_member(encoding, member, ch) != member->match)
            return FALSE;

        member = member->next_1.node;
    }

    return TRUE;
}

/* Checks whether a character is in a set intersection, ignoring case. */
Py_LOCAL_INLINE(BOOL) in_set_inter_ign(RE_EncodingTable* encoding, RE_Node*
  node, int case_count, Py_UCS4* cases) {
    RE_Node* member;

    member = node->nonstring.next_2.node;

    while (member) {
        if (matches_member_ign(encoding, member, case_count, cases) !=
          member->match)
            return FALSE;

        member = member->next_1.node;
    }

    return TRUE;
}

/* Checks whether a character is in a set symmetric difference. */
Py_LOCAL_INLINE(BOOL) in_set_sym_diff(RE_EncodingTable* encoding, RE_Node*
  node, Py_UCS4 ch) {
    RE_Node* member;
    BOOL result;

    member = node->nonstring.next_2.node;

    result = FALSE;

    while (member) {
        if (matches_member(encoding, member, ch) == member->match)
            result = !result;

        member = member->next_1.node;
    }

    return result;
}

/* Checks whether a character is in a set symmetric difference, ignoring case.
 */
Py_LOCAL_INLINE(BOOL) in_set_sym_diff_ign(RE_EncodingTable* encoding, RE_Node*
  node, int case_count, Py_UCS4* cases) {
    RE_Node* member;
    BOOL result;

    member = node->nonstring.next_2.node;

    result = FALSE;

    while (member) {
        if (matches_member_ign(encoding, member, case_count, cases) ==
          member->match)
            result = !result;

        member = member->next_1.node;
    }

    return result;
}

/* Checks whether a character is in a set union. */
Py_LOCAL_INLINE(BOOL) in_set_union(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch) {
    RE_Node* member;

    member = node->nonstring.next_2.node;

    while (member) {
        if (matches_member(encoding, member, ch) == member->match)
            return TRUE;

        member = member->next_1.node;
    }

    return FALSE;
}

/* Checks whether a character is in a set union, ignoring case. */
Py_LOCAL_INLINE(BOOL) in_set_union_ign(RE_EncodingTable* encoding, RE_Node*
  node, int case_count, Py_UCS4* cases) {
    RE_Node* member;

    member = node->nonstring.next_2.node;

    while (member) {
        if (matches_member_ign(encoding, member, case_count, cases) ==
          member->match)
            return TRUE;

        member = member->next_1.node;
    }

    return FALSE;
}

/* Checks whether a character is in a set. */
Py_LOCAL_INLINE(BOOL) in_set(RE_EncodingTable* encoding, RE_Node* node, Py_UCS4
  ch) {
    switch (node->op) {
    case RE_OP_SET_DIFF:
    case RE_OP_SET_DIFF_REV:
        return in_set_diff(encoding, node, ch);
    case RE_OP_SET_INTER:
    case RE_OP_SET_INTER_REV:
        return in_set_inter(encoding, node, ch);
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_SYM_DIFF_REV:
        return in_set_sym_diff(encoding, node, ch);
    case RE_OP_SET_UNION:
    case RE_OP_SET_UNION_REV:
        return in_set_union(encoding, node, ch);
    }

    return FALSE;
}

/* Checks whether a character is in a set, ignoring case. */
Py_LOCAL_INLINE(BOOL) in_set_ign(RE_EncodingTable* encoding, RE_Node* node,
  Py_UCS4 ch) {
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    case_count = encoding->all_cases(ch, cases);

    switch (node->op) {
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_DIFF_IGN_REV:
        return in_set_diff_ign(encoding, node, case_count, cases);
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_INTER_IGN_REV:
        return in_set_inter_ign(encoding, node, case_count, cases);
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
        return in_set_sym_diff_ign(encoding, node, case_count, cases);
    case RE_OP_SET_UNION_IGN:
    case RE_OP_SET_UNION_IGN_REV:
        return in_set_union_ign(encoding, node, case_count, cases);
    }

    return FALSE;
}

/* Resets a guard list. */
Py_LOCAL_INLINE(void) reset_guard_list(RE_GuardList* guard_list) {
    guard_list->count = 0;
    guard_list->last_text_pos = -1;
}

/* Initialises the state for a match. */
Py_LOCAL_INLINE(void) init_match(RE_State* state) {
    size_t i;

    /* Reset the backtrack. */
    state->current_backtrack_block = &state->backtrack_block;
    state->current_backtrack_block->count = 0;
    state->current_saved_groups = state->first_saved_groups;
    state->backtrack = NULL;
    state->search_anchor = state->text_pos;
    state->match_pos = state->text_pos;

    /* Reset the guards for the repeats. */
    for (i = 0; i < state->pattern->repeat_count; i++) {
        reset_guard_list(&state->repeats[i].body_guard_list);
        reset_guard_list(&state->repeats[i].tail_guard_list);
    }

    /* Reset the guards for the fuzzy sections. */
    for (i = 0; i < state->pattern->fuzzy_count; i++) {
        reset_guard_list(&state->fuzzy_guards[i].body_guard_list);
        reset_guard_list(&state->fuzzy_guards[i].tail_guard_list);
    }

    for (i = 0; i < state->pattern->true_group_count; i++) {
        RE_GroupData* group;

        group = &state->groups[i];
        group->span.start = -1;
        group->span.end = -1;
        group->capture_count = 0;
        group->current_capture = -1;
    }

    /* Reset the guards for the group calls. */
    for (i = 0; i < state->pattern->call_ref_info_count; i++)
        reset_guard_list(&state->group_call_guard_list[i]);

    /* Clear the counts and cost for matching. */
    memset(state->fuzzy_info.counts, 0, sizeof(state->fuzzy_info.counts));
    state->fuzzy_info.total_cost = 0;
    state->total_errors = 0;
    state->total_cost = 0;
    state->too_few_errors = FALSE;
    state->capture_change = 0;
    state->iterations = 0;
}

/* Adds a new backtrack entry. */
Py_LOCAL_INLINE(BOOL) add_backtrack(RE_SafeState* safe_state, RE_UINT8 op) {
    RE_State* state;
    RE_BacktrackBlock* current;

    state = safe_state->re_state;

    current = state->current_backtrack_block;
    if (current->count >= current->capacity) {
        if (!current->next) {
            RE_BacktrackBlock* next;

            /* Is there too much backtracking? */
            if (state->backtrack_allocated >= RE_MAX_BACKTRACK_ALLOC)
                return FALSE;

            next = (RE_BacktrackBlock*)safe_alloc(safe_state,
              sizeof(RE_BacktrackBlock));
            if (!next)
                return FALSE;

            next->previous = current;
            next->next = NULL;
            next->capacity = RE_BACKTRACK_BLOCK_SIZE;
            current->next = next;

            state->backtrack_allocated += RE_BACKTRACK_BLOCK_SIZE;
        }

        current = current->next;
        current->count = 0;
        state->current_backtrack_block = current;
    }

    state->backtrack = &current->items[current->count++];
    state->backtrack->op = op;

    return TRUE;
}

/* Gets the last backtrack entry.
 *
 * It'll never be called when there are _no_ entries.
 */
Py_LOCAL_INLINE(RE_BacktrackData*) last_backtrack(RE_State* state) {
    RE_BacktrackBlock* current;

    current = state->current_backtrack_block;
    state->backtrack = &current->items[current->count - 1];

    return state->backtrack;
}

/* Discards the last backtrack entry.
 *
 * It'll never be called to discard the _only_ entry.
 */
Py_LOCAL_INLINE(void) discard_backtrack(RE_State* state) {
    RE_BacktrackBlock* current;

    current = state->current_backtrack_block;
    --current->count;
    if (current->count == 0 && current->previous)
        state->current_backtrack_block = current->previous;
}

/* Copies a repeat guard list. */
Py_LOCAL_INLINE(BOOL) copy_guard_data(RE_SafeState* safe_state, RE_GuardList*
  dst, RE_GuardList* src) {
    if (dst->capacity < src->count) {
        RE_GuardSpan* new_spans;

        if (!safe_state)
            return FALSE;

        dst->capacity = src->count;
        new_spans = (RE_GuardSpan*)safe_realloc(safe_state, dst->spans,
          dst->capacity * sizeof(RE_GuardSpan));
        if (!new_spans)
            return FALSE;

        dst->spans = new_spans;
    }

    dst->count = src->count;
    memmove(dst->spans, src->spans, dst->count * sizeof(RE_GuardSpan));

    dst->last_text_pos = -1;

    return TRUE;
}

/* Copies a repeat. */
Py_LOCAL_INLINE(BOOL) copy_repeat_data(RE_SafeState* safe_state, RE_RepeatData*
  dst, RE_RepeatData* src) {
    if (!copy_guard_data(safe_state, &dst->body_guard_list,
      &src->body_guard_list) || !copy_guard_data(safe_state,
      &dst->tail_guard_list, &src->tail_guard_list)) {
        safe_dealloc(safe_state, dst->body_guard_list.spans);
        safe_dealloc(safe_state, dst->tail_guard_list.spans);

        return FALSE;
    }

    dst->count = src->count;
    dst->start = src->start;
    dst->capture_change = src->capture_change;

    return TRUE;
}

/* Pushes a return node onto the group call stack. */
Py_LOCAL_INLINE(BOOL) push_group_return(RE_SafeState* safe_state, RE_Node*
  return_node) {
    RE_State* state;
    PatternObject* pattern;
    RE_GroupCallFrame* frame;

    state = safe_state->re_state;
    pattern = state->pattern;

    if (state->current_group_call_frame &&
      state->current_group_call_frame->next)
        /* Advance to the next allocated frame. */
        frame = state->current_group_call_frame->next;
    else if (!state->current_group_call_frame && state->first_group_call_frame)
        /* Advance to the first allocated frame. */
        frame = state->first_group_call_frame;
    else {
        /* Create a new frame. */
        frame = (RE_GroupCallFrame*)safe_alloc(safe_state,
          sizeof(RE_GroupCallFrame));
        if (!frame)
            return FALSE;

        frame->groups = (RE_GroupData*)safe_alloc(safe_state,
          pattern->true_group_count * sizeof(RE_GroupData));
        frame->repeats = (RE_RepeatData*)safe_alloc(safe_state,
          pattern->repeat_count * sizeof(RE_RepeatData));
        if (!frame->groups || !frame->repeats) {
            safe_dealloc(safe_state, frame->groups);
            safe_dealloc(safe_state, frame->repeats);
            safe_dealloc(safe_state, frame);

            return FALSE;
        }

        memset(frame->groups, 0, pattern->true_group_count *
          sizeof(RE_GroupData));
        memset(frame->repeats, 0, pattern->repeat_count *
          sizeof(RE_RepeatData));

        frame->previous = state->current_group_call_frame;
        frame->next = NULL;

        if (frame->previous)
            frame->previous->next = frame;
        else
            state->first_group_call_frame = frame;
    }

    frame->node = return_node;

    /* Push the groups and guards. */
    if (return_node) {
        size_t g;
        size_t r;

        for (g = 0; g < pattern->true_group_count; g++) {
            frame->groups[g].span = state->groups[g].span;
            frame->groups[g].current_capture =
              state->groups[g].current_capture;
        }

        for (r = 0; r < pattern->repeat_count; r++) {
            if (!copy_repeat_data(safe_state, &frame->repeats[r],
              &state->repeats[r]))
                return FALSE;
        }
    }

    state->current_group_call_frame = frame;

    return TRUE;
}

/* Pops a return node from the group call stack. */
Py_LOCAL_INLINE(RE_Node*) pop_group_return(RE_State* state) {
    RE_GroupCallFrame* frame;

    frame = state->current_group_call_frame;

    /* Pop the groups and repeats. */
    if (frame->node) {
        PatternObject* pattern;
        size_t g;
        size_t r;

        pattern = state->pattern;

        for (g = 0; g < pattern->true_group_count; g++) {
            state->groups[g].span = frame->groups[g].span;
            state->groups[g].current_capture =
              frame->groups[g].current_capture;
        }

        for (r = 0; r < pattern->repeat_count; r++)
            copy_repeat_data(NULL, &state->repeats[r], &frame->repeats[r]);
    }

    /* Withdraw to previous frame. */
    state->current_group_call_frame = frame->previous;

    return frame->node;
}

/* Returns the return node from the top of the group call stack. */
Py_LOCAL_INLINE(RE_Node*) top_group_return(RE_State* state) {
    RE_GroupCallFrame* frame;

    frame = state->current_group_call_frame;

    return frame->node;
}

/* Checks whether the node is a firstset. */
Py_LOCAL_INLINE(BOOL) is_firstset(RE_Node* node) {
    if (node->step != 0)
        return FALSE;

    switch (node->op) {
    case RE_OP_ANY:
    case RE_OP_ANY_ALL:
    case RE_OP_ANY_ALL_REV:
    case RE_OP_ANY_REV:
    case RE_OP_ANY_U:
    case RE_OP_ANY_U_REV:
    case RE_OP_CHARACTER:
    case RE_OP_CHARACTER_IGN:
    case RE_OP_CHARACTER_IGN_REV:
    case RE_OP_CHARACTER_REV:
    case RE_OP_PROPERTY:
    case RE_OP_PROPERTY_IGN:
    case RE_OP_PROPERTY_IGN_REV:
    case RE_OP_PROPERTY_REV:
    case RE_OP_RANGE:
    case RE_OP_RANGE_IGN:
    case RE_OP_RANGE_IGN_REV:
    case RE_OP_RANGE_REV:
    case RE_OP_SET_DIFF:
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_DIFF_IGN_REV:
    case RE_OP_SET_DIFF_REV:
    case RE_OP_SET_INTER:
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION:
    case RE_OP_SET_UNION_IGN:
    case RE_OP_SET_UNION_IGN_REV:
    case RE_OP_SET_UNION_REV:
        return TRUE;
    default:
        return FALSE;
    }
}

/* Locates the start node for testing ahead. */
Py_LOCAL_INLINE(RE_Node*) locate_test_start(RE_Node* node) {
    for (;;) {
        switch (node->op) {
        case RE_OP_BOUNDARY:
            switch (node->next_1.node->op) {
            case RE_OP_STRING:
            case RE_OP_STRING_FLD:
            case RE_OP_STRING_FLD_REV:
            case RE_OP_STRING_IGN:
            case RE_OP_STRING_IGN_REV:
            case RE_OP_STRING_REV:
                return node->next_1.node;
            default:
                return node;
            }
        case RE_OP_CALL_REF:
        case RE_OP_END_GROUP:
        case RE_OP_START_GROUP:
            node = node->next_1.node;
            break;
        case RE_OP_GREEDY_REPEAT:
        case RE_OP_LAZY_REPEAT:
            if (node->values[1] == 0)
                return node;
            node = node->next_1.node;
            break;
        case RE_OP_GREEDY_REPEAT_ONE:
        case RE_OP_LAZY_REPEAT_ONE:
            if (node->values[1] == 0)
                return node;
            return node->nonstring.next_2.node;
        case RE_OP_LOOKAROUND:
            node = node->next_1.node;
            break;
        default:
            if (is_firstset(node)) {
                switch (node->next_1.node->op) {
                case RE_OP_END_OF_STRING:
                case RE_OP_START_OF_STRING:
                    return node->next_1.node;
                }
            }

            return node;
        }
    }
}

/* Checks whether a character matches any of a set of case characters. */
Py_LOCAL_INLINE(BOOL) any_case(Py_UCS4 ch, int case_count, Py_UCS4* cases) {
    int i;

    for (i = 0; i < case_count; i++) {
        if (ch == cases[i])
            return TRUE;
    }

    return FALSE;
}

/* Matches many ANYs. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_ANY(RE_State* state, Py_ssize_t
  text_pos, Py_ssize_t limit, BOOL match) {
    void* text;

    text = state->text;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && (text_ptr[0] != '\n') == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && (text_ptr[0] != '\n') == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && (text_ptr[0] != '\n') == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many ANYs backwards. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_ANY_REV(RE_State* state, Py_ssize_t
  text_pos, Py_ssize_t limit, BOOL match) {
    void* text;

    text = state->text;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && (text_ptr[-1] != '\n') == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && (text_ptr[-1] != '\n') == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && (text_ptr[-1] != '\n') == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many ANY_Us. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_ANY_U(RE_State* state, Py_ssize_t
  text_pos, Py_ssize_t limit, BOOL match) {
    BOOL (*is_line_sep)(Py_UCS4 ch);
    void* text;

    is_line_sep = state->encoding->is_line_sep;
    text = state->text;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && is_line_sep(text_ptr[0]) != match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && is_line_sep(text_ptr[0]) != match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && is_line_sep(text_ptr[0]) != match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many ANY_Us backwards. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_ANY_U_REV(RE_State* state, Py_ssize_t
  text_pos, Py_ssize_t limit, BOOL match) {
    BOOL (*is_line_sep)(Py_UCS4 ch);
    void* text;

    is_line_sep = state->encoding->is_line_sep;
    text = state->text;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && is_line_sep(text_ptr[-1]) != match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && is_line_sep(text_ptr[-1]) != match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && is_line_sep(text_ptr[-1]) != match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many CHARACTERs. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_CHARACTER(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    Py_UCS4 ch;

    text = state->text;
    match = node->match == match;
    ch = node->values[0];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && (text_ptr[0] == ch) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && (text_ptr[0] == ch) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && (text_ptr[0] == ch) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many CHARACTERs, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_CHARACTER_IGN(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    text = state->text;
    match = node->match == match;
    case_count = state->encoding->all_cases(node->values[0], cases);

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && any_case(text_ptr[0], case_count, cases)
          == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && any_case(text_ptr[0], case_count, cases)
          == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && any_case(text_ptr[0], case_count, cases)
          == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many CHARACTERs backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_CHARACTER_IGN_REV(RE_State* state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    text = state->text;
    match = node->match == match;
    case_count = state->encoding->all_cases(node->values[0], cases);

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && any_case(text_ptr[-1], case_count,
          cases) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && any_case(text_ptr[-1], case_count,
          cases) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && any_case(text_ptr[-1], case_count,
          cases) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many CHARACTERs backwards. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_CHARACTER_REV(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    Py_UCS4 ch;

    text = state->text;
    match = node->match == match;
    ch = node->values[0];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && (text_ptr[-1] == ch) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && (text_ptr[-1] == ch) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && (text_ptr[-1] == ch) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many PROPERTYs. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_PROPERTY(RE_State* state, RE_Node* node,
  Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    BOOL (*has_property)(RE_CODE property, Py_UCS4 ch);
    RE_CODE property;

    text = state->text;
    match = node->match == match;
    has_property = state->encoding->has_property;
    property = node->values[0];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && has_property(property, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && has_property(property, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && has_property(property, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many PROPERTYs, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_PROPERTY_IGN(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;
    RE_CODE property;

    text = state->text;
    match = node->match == match;
    encoding = state->encoding;
    property = node->values[0];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && has_property_ign(encoding, property,
          text_ptr[0]) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && has_property_ign(encoding, property,
          text_ptr[0]) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && has_property_ign(encoding, property,
          text_ptr[0]) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many PROPERTYs backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_PROPERTY_IGN_REV(RE_State* state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;
    RE_CODE property;

    text = state->text;
    match = node->match == match;
    encoding = state->encoding;
    property = node->values[0];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && has_property_ign(encoding, property,
          text_ptr[-1]) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && has_property_ign(encoding, property,
          text_ptr[-1]) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && has_property_ign(encoding, property,
          text_ptr[-1]) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many PROPERTYs backwards. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_PROPERTY_REV(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    BOOL (*has_property)(RE_CODE property, Py_UCS4 ch);
    RE_CODE property;

    text = state->text;
    match = node->match == match;
    has_property = state->encoding->has_property;
    property = node->values[0];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && has_property(property, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && has_property(property, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && has_property(property, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many RANGEs. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_RANGE(RE_State* state, RE_Node* node,
  Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    Py_UCS4 lower;
    Py_UCS4 upper;

    text = state->text;
    match = node->match == match;
    lower = node->values[0];
    upper = node->values[1];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && in_range(lower, upper, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && in_range(lower, upper, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && in_range(lower, upper, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many RANGEs, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_RANGE_IGN(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;
    Py_UCS4 lower;
    Py_UCS4 upper;

    text = state->text;
    encoding = state->encoding;
    match = node->match == match;
    lower = node->values[0];
    upper = node->values[1];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && in_range_ign(encoding, lower, upper,
          text_ptr[0]) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && in_range_ign(encoding, lower, upper,
          text_ptr[0]) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && in_range_ign(encoding, lower, upper,
          text_ptr[0]) == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many RANGEs backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_RANGE_IGN_REV(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;
    Py_UCS4 lower;
    Py_UCS4 upper;

    text = state->text;
    encoding = state->encoding;
    match = node->match == match;
    lower = node->values[0];
    upper = node->values[1];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && in_range_ign(encoding, lower, upper,
          text_ptr[-1]) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && in_range_ign(encoding, lower, upper,
          text_ptr[-1]) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && in_range_ign(encoding, lower, upper,
          text_ptr[-1]) == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many RANGEs backwards. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_RANGE_REV(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    Py_UCS4 lower;
    Py_UCS4 upper;

    text = state->text;
    match = node->match == match;
    lower = node->values[0];
    upper = node->values[1];

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && in_range(lower, upper, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && in_range(lower, upper, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && in_range(lower, upper, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many SETs. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_SET(RE_State* state, RE_Node* node,
  Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;

    text = state->text;
    match = node->match == match;
    encoding = state->encoding;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && in_set(encoding, node, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && in_set(encoding, node, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && in_set(encoding, node, text_ptr[0]) ==
          match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many SETs, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_SET_IGN(RE_State* state, RE_Node* node,
  Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;

    text = state->text;
    match = node->match == match;
    encoding = state->encoding;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr < limit_ptr && in_set_ign(encoding, node, text_ptr[0])
          == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr < limit_ptr && in_set_ign(encoding, node, text_ptr[0])
          == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr < limit_ptr && in_set_ign(encoding, node, text_ptr[0])
          == match)
            ++text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many SETs backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_SET_IGN_REV(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;

    text = state->text;
    match = node->match == match;
    encoding = state->encoding;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && in_set_ign(encoding, node, text_ptr[-1])
          == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && in_set_ign(encoding, node, text_ptr[-1])
          == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && in_set_ign(encoding, node, text_ptr[-1])
          == match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Matches many SETs backwards. */
Py_LOCAL_INLINE(Py_ssize_t) match_many_SET_REV(RE_State* state, RE_Node* node,
  Py_ssize_t text_pos, Py_ssize_t limit, BOOL match) {
    void* text;
    RE_EncodingTable* encoding;

    text = state->text;
    match = node->match == match;
    encoding = state->encoding;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr > limit_ptr && in_set(encoding, node, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS1*)text;
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr > limit_ptr && in_set(encoding, node, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS2*)text;
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr > limit_ptr && in_set(encoding, node, text_ptr[-1]) ==
          match)
            --text_ptr;

        text_pos = text_ptr - (Py_UCS4*)text;
        break;
    }
    }

    return text_pos;
}

/* Counts a repeated character pattern. */
Py_LOCAL_INLINE(size_t) count_one(RE_State* state, RE_Node* node, Py_ssize_t
  text_pos, size_t max_count) {
    if (max_count < 1)
        return 0;

    switch (node->op) {
    case RE_OP_ANY:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_ANY(state, text_pos, text_pos + max_count, TRUE) -
          text_pos;
    case RE_OP_ANY_ALL:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return max_count;
    case RE_OP_ANY_ALL_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return max_count;
    case RE_OP_ANY_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_ANY_REV(state, text_pos, text_pos -
          max_count, TRUE);
    case RE_OP_ANY_U:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_ANY_U(state, text_pos, text_pos + max_count, TRUE) -
          text_pos;
    case RE_OP_ANY_U_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_ANY_U_REV(state, text_pos, text_pos -
          max_count, TRUE);
    case RE_OP_CHARACTER:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_CHARACTER(state, node, text_pos, text_pos +
          max_count, TRUE) - text_pos;
    case RE_OP_CHARACTER_IGN:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_CHARACTER_IGN(state, node, text_pos, text_pos +
          max_count, TRUE) - text_pos;
    case RE_OP_CHARACTER_IGN_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_CHARACTER_IGN_REV(state, node, text_pos,
          text_pos - max_count, TRUE);
    case RE_OP_CHARACTER_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_CHARACTER_REV(state, node, text_pos,
          text_pos - max_count, TRUE);
    case RE_OP_PROPERTY:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_PROPERTY(state, node, text_pos, text_pos + max_count,
          TRUE) - text_pos;
    case RE_OP_PROPERTY_IGN:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_PROPERTY_IGN(state, node, text_pos, text_pos +
          max_count, TRUE) - text_pos;
    case RE_OP_PROPERTY_IGN_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_PROPERTY_IGN_REV(state, node, text_pos,
          text_pos - max_count, TRUE);
    case RE_OP_PROPERTY_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_PROPERTY_REV(state, node, text_pos,
          text_pos - max_count, TRUE);
    case RE_OP_RANGE:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_RANGE(state, node, text_pos, text_pos + max_count,
          TRUE) - text_pos;
    case RE_OP_RANGE_IGN:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_RANGE_IGN(state, node, text_pos, text_pos +
          max_count, TRUE) - text_pos;
    case RE_OP_RANGE_IGN_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_RANGE_IGN_REV(state, node, text_pos,
          text_pos - max_count, TRUE);
    case RE_OP_RANGE_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_RANGE_REV(state, node, text_pos, text_pos
          - max_count, TRUE);
    case RE_OP_SET_DIFF:
    case RE_OP_SET_INTER:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_UNION:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_SET(state, node, text_pos, text_pos + max_count,
          TRUE) - text_pos;
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_UNION_IGN:
        max_count = RE_MIN(max_count, (size_t)(state->slice_end - text_pos));

        return match_many_SET_IGN(state, node, text_pos, text_pos + max_count,
          TRUE) - text_pos;
    case RE_OP_SET_DIFF_IGN_REV:
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_UNION_IGN_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_SET_IGN_REV(state, node, text_pos,
          text_pos - max_count, TRUE);
    case RE_OP_SET_DIFF_REV:
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION_REV:
        max_count = RE_MIN(max_count, (size_t)(text_pos - state->slice_start));

        return text_pos - match_many_SET_REV(state, node, text_pos, text_pos -
          max_count, TRUE);
    }

    return 0;
}

/* Tries to match a character pattern. */
Py_LOCAL_INLINE(BOOL) match_one(RE_State* state, RE_Node* node, Py_ssize_t
  text_pos) {
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;

    char_at = state->char_at;
    text = state->text;

    switch (node->op) {
    case RE_OP_ANY:
        return text_pos < state->slice_end && char_at(text, text_pos) != '\n';
    case RE_OP_ANY_ALL:
        return text_pos < state->slice_end;
    case RE_OP_ANY_ALL_REV:
        return text_pos > state->slice_start;
    case RE_OP_ANY_REV:
        return text_pos > state->slice_start && char_at(text, text_pos - 1) !=
          '\n';
    case RE_OP_ANY_U:
        return text_pos < state->slice_end &&
          !state->encoding->is_line_sep(char_at(text, text_pos));
    case RE_OP_ANY_U_REV:
        return text_pos > state->slice_start &&
          !state->encoding->is_line_sep(char_at(text, text_pos - 1));
    case RE_OP_CHARACTER:
        return text_pos < state->slice_end && (char_at(text, text_pos) ==
          node->values[0]) == node->match;
    case RE_OP_CHARACTER_IGN:
        return text_pos < state->slice_end && same_char_ign(state->encoding,
          char_at(text, text_pos), node->values[0]) == node->match;
    case RE_OP_CHARACTER_IGN_REV:
        return text_pos > state->slice_start && same_char_ign(state->encoding,
          char_at(text, text_pos - 1), node->values[0]) == node->match;
    case RE_OP_CHARACTER_REV:
        return text_pos > state->slice_start && (char_at(text, text_pos - 1) ==
          node->values[0]) == node->match;
    case RE_OP_PROPERTY:
        return text_pos < state->slice_end &&
          state->encoding->has_property(node->values[0], char_at(text,
          text_pos)) == node->match;
    case RE_OP_PROPERTY_IGN:
        return text_pos < state->slice_end && has_property_ign(state->encoding,
          node->values[0], char_at(text, text_pos)) == node->match;
    case RE_OP_PROPERTY_IGN_REV:
        return text_pos > state->slice_start &&
          has_property_ign(state->encoding, node->values[0], char_at(text,
          text_pos - 1)) == node->match;
    case RE_OP_PROPERTY_REV:
        return text_pos > state->slice_start &&
          state->encoding->has_property(node->values[0], char_at(text, text_pos
          - 1)) == node->match;
    case RE_OP_RANGE:
        return text_pos < state->slice_end && in_range(node->values[0],
          node->values[1], char_at(text, text_pos)) == node->match;
    case RE_OP_RANGE_IGN:
        return text_pos < state->slice_end && in_range_ign(state->encoding,
          node->values[0], node->values[1], char_at(text, text_pos)) ==
          node->match;
    case RE_OP_RANGE_IGN_REV:
        return text_pos > state->slice_start && in_range_ign(state->encoding,
          node->values[0], node->values[1], char_at(text, text_pos - 1)) ==
          node->match;
    case RE_OP_RANGE_REV:
        return text_pos > state->slice_start && in_range(node->values[0],
          node->values[1], char_at(text, text_pos - 1)) == node->match;
    case RE_OP_SET_DIFF:
    case RE_OP_SET_INTER:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_UNION:
        return text_pos < state->slice_end && in_set(state->encoding, node,
          char_at(text, text_pos)) == node->match;
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_UNION_IGN:
        return text_pos < state->slice_end && in_set_ign(state->encoding, node,
          char_at(text, text_pos)) == node->match;
    case RE_OP_SET_DIFF_IGN_REV:
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_UNION_IGN_REV:
        return text_pos > state->slice_start && in_set_ign(state->encoding,
          node, char_at(text, text_pos - 1)) == node->match;
    case RE_OP_SET_DIFF_REV:
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION_REV:
        return text_pos > state->slice_start && in_set(state->encoding, node,
          char_at(text, text_pos - 1)) == node->match;
    }

    return FALSE;
}

/* Performs a simple string search. */
Py_LOCAL_INLINE(Py_ssize_t) simple_string_search(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit) {
    void* text;
    size_t length;
    RE_CODE* values;
    Py_UCS4 first_char;

    text = state->text;
    length = node->value_count;
    values = node->values;
    first_char = values[0];
    limit -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr <= limit_ptr) {
            if (text_ptr[0] == first_char) {
                size_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS1*)text;
            }

            ++text_ptr;
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr <= limit_ptr) {
            if (text_ptr[0] == first_char) {
                size_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS2*)text;
            }

            ++text_ptr;
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr <= limit_ptr) {
            if (text_ptr[0] == first_char) {
                size_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS4*)text;
            }

            ++text_ptr;
        }
        break;
    }
    }

    return -1;
}

/* Performs a simple string search, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) simple_string_search_ign(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit) {
    void* text;
    size_t length;
    RE_CODE* values;
    RE_EncodingTable* encoding;
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    text = state->text;
    length = node->value_count;
    values = node->values;
    encoding = state->encoding;
    case_count = encoding->all_cases(values[0], cases);
    limit -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr <= limit_ptr) {
            if (any_case(text_ptr[0], case_count, cases)) {
                size_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding, text_ptr[pos],
                  values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS1*)text;
            }

            ++text_ptr;
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr <= limit_ptr) {
            if (any_case(text_ptr[0], case_count, cases)) {
                size_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding, text_ptr[pos],
                  values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS2*)text;
            }

            ++text_ptr;
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr <= limit_ptr) {
            if (any_case(text_ptr[0], case_count, cases)) {
                size_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding, text_ptr[pos],
                  values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS4*)text;
            }

            ++text_ptr;
        }
        break;
    }
    }

    return -1;
}

/* Performs a simple string search backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) simple_string_search_ign_rev(RE_State* state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit) {
    void* text;
    size_t length;
    RE_CODE* values;
    RE_EncodingTable* encoding;
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    text = state->text;
    length = node->value_count;
    values = node->values;
    encoding = state->encoding;
    case_count = encoding->all_cases(values[0], cases);
    text_pos -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr >= limit_ptr) {
            if (any_case(text_ptr[0], case_count, cases)) {
                size_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding, text_ptr[pos],
                  values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS1*)text + length;
            }

            --text_ptr;
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr >= limit_ptr) {
            if (any_case(text_ptr[0], case_count, cases)) {
                size_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding, text_ptr[pos],
                  values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS2*)text + length;
            }

            --text_ptr;
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr >= limit_ptr) {
            if (any_case(text_ptr[0], case_count, cases)) {
                size_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding, text_ptr[pos],
                  values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS4*)text + length;
            }

            --text_ptr;
        }
        break;
    }
    }

    return -1;
}

/* Performs a simple string search backwards. */
Py_LOCAL_INLINE(Py_ssize_t) simple_string_search_rev(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit) {
    void* text;
    size_t length;
    RE_CODE* values;
    Py_UCS4 first_char;

    text = state->text;
    length = node->value_count;
    values = node->values;
    first_char = values[0];
    text_pos -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr >= limit_ptr) {
            if (text_ptr[0] == first_char) {
                size_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS1*)text + length;
            }

            --text_ptr;
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr >= limit_ptr) {
            if (text_ptr[0] == first_char) {
                size_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS2*)text + length;
            }

            --text_ptr;
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr >= limit_ptr) {
            if (text_ptr[0] == first_char) {
                size_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS4*)text + length;
            }

            --text_ptr;
        }
        break;
    }
    }

    return -1;
}

/* Performs a Boyer-Moore fast string search. */
Py_LOCAL_INLINE(Py_ssize_t) fast_string_search(RE_State* state, RE_Node* node,
  Py_ssize_t text_pos, Py_ssize_t limit) {
    void* text;
    Py_ssize_t length;
    RE_CODE* values;
    Py_ssize_t* bad_character_offset;
    Py_ssize_t* good_suffix_offset;
    Py_ssize_t last_pos;
    Py_UCS4 check_char;

    text = state->text;
    length = (Py_ssize_t)node->value_count;
    values = node->values;
    good_suffix_offset = node->string.good_suffix_offset;
    bad_character_offset = node->string.bad_character_offset;
    last_pos = length - 1;
    check_char = values[last_pos];
    limit -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr <= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[last_pos];
            if (ch == check_char) {
                Py_ssize_t pos;

                pos = last_pos - 1;
                while (pos >= 0 && text_ptr[pos] == values[pos])
                    --pos;

                if (pos < 0)
                    return text_ptr - (Py_UCS1*)text;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr <= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[last_pos];
            if (ch == check_char) {
                Py_ssize_t pos;

                pos = last_pos - 1;
                while (pos >= 0 && text_ptr[pos] == values[pos])
                    --pos;

                if (pos < 0)
                    return text_ptr - (Py_UCS2*)text;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr <= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[last_pos];
            if (ch == check_char) {
                Py_ssize_t pos;

                pos = last_pos - 1;
                while (pos >= 0 && text_ptr[pos] == values[pos])
                    --pos;

                if (pos < 0)
                    return text_ptr - (Py_UCS4*)text;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    }

    return -1;
}

/* Performs a Boyer-Moore fast string search, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) fast_string_search_ign(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit) {
    RE_EncodingTable* encoding;
    void* text;
    Py_ssize_t length;
    RE_CODE* values;
    Py_ssize_t* bad_character_offset;
    Py_ssize_t* good_suffix_offset;
    Py_ssize_t last_pos;
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    encoding = state->encoding;
    text = state->text;
    length = (Py_ssize_t)node->value_count;
    values = node->values;
    good_suffix_offset = node->string.good_suffix_offset;
    bad_character_offset = node->string.bad_character_offset;
    last_pos = length - 1;
    case_count = encoding->all_cases(values[last_pos], cases);
    limit -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr <= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[last_pos];
            if (any_case(ch, case_count, cases)) {
                Py_ssize_t pos;

                pos = last_pos - 1;
                while (pos >= 0 && same_char_ign(encoding,
                   text_ptr[pos], values[pos]))
                    --pos;

                if (pos < 0)
                    return text_ptr - (Py_UCS1*)text;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr <= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[last_pos];
            if (any_case(ch, case_count, cases)) {
                Py_ssize_t pos;

                pos = last_pos - 1;
                while (pos >= 0 && same_char_ign(encoding,
                   text_ptr[pos], values[pos]))
                    --pos;

                if (pos < 0)
                    return text_ptr - (Py_UCS2*)text;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr <= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[last_pos];
            if (any_case(ch, case_count, cases)) {
                Py_ssize_t pos;

                pos = last_pos - 1;
                while (pos >= 0 && same_char_ign(encoding,
                   text_ptr[pos], values[pos]))
                    --pos;

                if (pos < 0)
                    return text_ptr - (Py_UCS4*)text;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    }

    return -1;
}

/* Performs a Boyer-Moore fast string search backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) fast_string_search_ign_rev(RE_State* state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit) {
    RE_EncodingTable* encoding;
    void* text;
    Py_ssize_t length;
    RE_CODE* values;
    Py_ssize_t* bad_character_offset;
    Py_ssize_t* good_suffix_offset;
    Py_UCS4 cases[RE_MAX_CASES];
    int case_count;

    encoding = state->encoding;
    text = state->text;
    length = (Py_ssize_t)node->value_count;
    values = node->values;
    good_suffix_offset = node->string.good_suffix_offset;
    bad_character_offset = node->string.bad_character_offset;
    case_count = encoding->all_cases(values[0], cases);
    text_pos -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr >= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[0];
            if (any_case(ch, case_count, cases)) {
                Py_ssize_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding,
                   text_ptr[pos], values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS1*)text + length;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr >= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[0];
            if (any_case(ch, case_count, cases)) {
                Py_ssize_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding,
                   text_ptr[pos], values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS2*)text + length;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr >= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[0];
            if (any_case(ch, case_count, cases)) {
                Py_ssize_t pos;

                pos = 1;
                while (pos < length && same_char_ign(encoding,
                   text_ptr[pos], values[pos]))
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS4*)text + length;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    }

    return -1;
}

/* Performs a Boyer-Moore fast string search backwards. */
Py_LOCAL_INLINE(Py_ssize_t) fast_string_search_rev(RE_State* state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit) {
    void* text;
    Py_ssize_t length;
    RE_CODE* values;
    Py_ssize_t* bad_character_offset;
    Py_ssize_t* good_suffix_offset;
    Py_UCS4 check_char;

    text = state->text;
    length = (Py_ssize_t)node->value_count;
    values = node->values;
    good_suffix_offset = node->string.good_suffix_offset;
    bad_character_offset = node->string.bad_character_offset;
    check_char = values[0];
    text_pos -= length;

    switch (state->charsize) {
    case 1:
    {
        Py_UCS1* text_ptr;
        Py_UCS1* limit_ptr;

        text_ptr = (Py_UCS1*)text + text_pos;
        limit_ptr = (Py_UCS1*)text + limit;

        while (text_ptr >= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[0];
            if (ch == check_char) {
                Py_ssize_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS1*)text + length;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 2:
    {
        Py_UCS2* text_ptr;
        Py_UCS2* limit_ptr;

        text_ptr = (Py_UCS2*)text + text_pos;
        limit_ptr = (Py_UCS2*)text + limit;

        while (text_ptr >= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[0];
            if (ch == check_char) {
                Py_ssize_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS2*)text + length;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    case 4:
    {
        Py_UCS4* text_ptr;
        Py_UCS4* limit_ptr;

        text_ptr = (Py_UCS4*)text + text_pos;
        limit_ptr = (Py_UCS4*)text + limit;

        while (text_ptr >= limit_ptr) {
            Py_UCS4 ch;

            ch = text_ptr[0];
            if (ch == check_char) {
                Py_ssize_t pos;

                pos = 1;
                while (pos < length && text_ptr[pos] == values[pos])
                    ++pos;

                if (pos >= length)
                    return text_ptr - (Py_UCS4*)text + length;

                text_ptr += good_suffix_offset[pos];
            } else
                text_ptr += bad_character_offset[ch & 0xFF];
        }
        break;
    }
    }

    return -1;
}

/* Check whether 2 characters are the same. */
static BOOL same_char(RE_EncodingTable* encoding, Py_UCS4 ch1, Py_UCS4 ch2) {
    return ch1 == ch2;
}

/* Build the tables for a Boyer-Moore fast string search. */
Py_LOCAL_INLINE(BOOL) build_fast_tables(RE_EncodingTable* encoding, RE_Node*
  node, BOOL ignore) {
    Py_ssize_t length;
    RE_CODE* values;
    Py_ssize_t* bad;
    Py_ssize_t* good;
    Py_UCS4 ch;
    Py_ssize_t last_pos;
    Py_ssize_t pos;
    BOOL (*is_same_char)(RE_EncodingTable* encoding, Py_UCS4 ch1, Py_UCS4 ch2);
    Py_ssize_t suffix_len;
    BOOL saved_start;
    Py_ssize_t s;
    Py_ssize_t i;
    Py_ssize_t s_start;
    Py_UCS4 codepoints[RE_MAX_CASES];

    length = (Py_ssize_t)node->value_count;

    if (length < RE_MIN_FAST_LENGTH)
        return TRUE;

    values = node->values;
    bad = (Py_ssize_t*)re_alloc(256 * sizeof(bad[0]));
    good = (Py_ssize_t*)re_alloc(length * sizeof(good[0]));

    if (!bad || !good) {
        re_dealloc(bad);
        re_dealloc(good);

        return FALSE;
    }

    for (ch = 0; ch < 0x100; ch++)
        bad[ch] = length;

    last_pos = length - 1;

    for (pos = 0; pos < last_pos; pos++) {
        Py_ssize_t offset;

        offset = last_pos - pos;
        ch = values[pos];
        if (ignore) {
            int count;
            int i;

            count = encoding->all_cases(ch, codepoints);

            for (i = 0; i < count; i++)
                bad[codepoints[i] & 0xFF] = offset;
        } else
            bad[ch & 0xFF] = offset;
    }

    is_same_char = ignore ? same_char_ign : same_char;

    suffix_len = 2;
    pos = length - suffix_len;
    saved_start = FALSE;
    s = pos - 1;
    i = suffix_len - 1;
    s_start = s;
    while (pos >= 0) {
        /* Look for another occurrence of the suffix. */
        while (i > 0) {
            /* Have we dropped off the end of the string? */
            if (s + i < 0)
                break;

            if (is_same_char(encoding, values[s + i], values[pos + i]))
                /* It still matches. */
                --i;
            else {
                /* Start again further along. */
                --s;
                i = suffix_len - 1;
            }
        }

        if (s >= 0 && is_same_char(encoding, values[s], values[pos])) {
            /* We haven't dropped off the end of the string, and the suffix has
             * matched this far, so this is a good starting point for the next
             * iteration.
             */
            --s;
            if (!saved_start) {
                s_start = s;
                saved_start = TRUE;
            }
        } else {
            /* Calculate the suffix offset. */
            good[pos] = pos - s;

            /* Extend the suffix and start searching for _this_ one. */
            --pos;
            ++suffix_len;

            /* Where's a good place to start searching? */
            if (saved_start) {
                s = s_start;
                saved_start = FALSE;
            } else
                --s;

            /* Can we short-circuit the searching? */
            if (s < 0)
                break;
        }

        i = suffix_len - 1;
    }

    /* Fill-in any remaining entries. */
    while (pos >= 0) {
        good[pos] = pos - s;
        --pos;
        --s;
    }

    node->string.bad_character_offset = bad;
    node->string.good_suffix_offset = good;

    return TRUE;
}

/* Build the tables for a Boyer-Moore fast string search backwards. */
Py_LOCAL_INLINE(BOOL) build_fast_tables_rev(RE_EncodingTable* encoding,
  RE_Node* node, BOOL ignore) {
    Py_ssize_t length;
    RE_CODE* values;
    Py_ssize_t* bad;
    Py_ssize_t* good;
    Py_UCS4 ch;
    Py_ssize_t last_pos;
    Py_ssize_t pos;
    BOOL (*is_same_char)(RE_EncodingTable* encoding, Py_UCS4 ch1, Py_UCS4 ch2);
    Py_ssize_t suffix_len;
    BOOL saved_start;
    Py_ssize_t s;
    Py_ssize_t i;
    Py_ssize_t s_start;
    Py_UCS4 codepoints[RE_MAX_CASES];

    length = (Py_ssize_t)node->value_count;

    if (length < RE_MIN_FAST_LENGTH)
        return TRUE;

    values = node->values;
    bad = (Py_ssize_t*)re_alloc(256 * sizeof(bad[0]));
    good = (Py_ssize_t*)re_alloc(length * sizeof(good[0]));

    if (!bad || !good) {
        re_dealloc(bad);
        re_dealloc(good);

        return FALSE;
    }

    for (ch = 0; ch < 0x100; ch++)
        bad[ch] = -length;

    last_pos = length - 1;

    for (pos = last_pos; pos > 0; pos--) {
        Py_ssize_t offset;

        offset = -pos;
        ch = values[pos];
        if (ignore) {
            int count;
            int i;

            count = encoding->all_cases(ch, codepoints);

            for (i = 0; i < count; i++)
                bad[codepoints[i] & 0xFF] = offset;
        } else
            bad[ch & 0xFF] = offset;
    }

    is_same_char = ignore ? same_char_ign : same_char;

    suffix_len = 2;
    pos = suffix_len - 1;
    saved_start = FALSE;
    s = pos + 1;
    i = suffix_len - 1;
    s_start = s;
    while (pos < length) {
        /* Look for another occurrence of the suffix. */
        while (i > 0) {
            /* Have we dropped off the end of the string? */
            if (s - i >= length)
                break;

            if (is_same_char(encoding, values[s - i], values[pos - i]))
                /* It still matches. */
                --i;
            else {
                /* Start again further along. */
                ++s;
                i = suffix_len - 1;
            }
        }

        if (s < length && is_same_char(encoding, values[s], values[pos])) {
            /* We haven't dropped off the end of the string, and the suffix has
             * matched this far, so this is a good starting point for the next
             * iteration.
             */
            ++s;
            if (!saved_start) {
                s_start = s;
                saved_start = TRUE;
            }
        } else {
            /* Calculate the suffix offset. */
            good[pos] = pos - s;

            /* Extend the suffix and start searching for _this_ one. */
            ++pos;
            ++suffix_len;

            /* Where's a good place to start searching? */
            if (saved_start) {
                s = s_start;
                saved_start = FALSE;
            } else
                ++s;

            /* Can we short-circuit the searching? */
            if (s >= length)
                break;
        }

        i = suffix_len - 1;
    }

    /* Fill-in any remaining entries. */
    while (pos < length) {
        good[pos] = pos - s;
        ++pos;
        ++s;
    }

    node->string.bad_character_offset = bad;
    node->string.good_suffix_offset = good;

    return TRUE;
}

/* Performs a string search. */
Py_LOCAL_INLINE(Py_ssize_t) string_search(RE_SafeState* safe_state, RE_Node*
  node, Py_ssize_t text_pos, Py_ssize_t limit) {
    RE_State* state;
    Py_ssize_t found_pos;

    state = safe_state->re_state;

    /* Can the string fit the available space? */
    if (text_pos + (Py_ssize_t)node->value_count > limit)
        return -1;

    /* Has the node been initialised for fast searching, if necessary? */
    if (!(node->status & RE_STATUS_FAST_INIT)) {
        /* Ideally the pattern should immutable and shareable across threads.
         * Internally, however, it isn't. For safety we need to hold the GIL.
         */
        acquire_GIL(safe_state);

        /* Double-check because of multithreading. */
        if (!(node->status & RE_STATUS_FAST_INIT)) {
            build_fast_tables(state->encoding, node, FALSE);
            node->status |= RE_STATUS_FAST_INIT;
        }

        release_GIL(safe_state);
    }

    if (node->string.bad_character_offset)
        found_pos = fast_string_search(state, node, text_pos, limit);
    else
        found_pos = simple_string_search(state, node, text_pos, limit);

    return found_pos;
}

/* Performs a string search, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) string_search_fld(RE_SafeState* safe_state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit, Py_ssize_t* new_pos) {
    RE_State* state;
    RE_EncodingTable* encoding;
    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    RE_CODE* values;
    Py_ssize_t start_pos;
    int folded_pos;
    int folded_len;
    Py_ssize_t length;
    Py_ssize_t string_pos;
    Py_UCS4 folded[RE_MAX_FOLDED];
    int case_count;
    Py_UCS4 cases[RE_MAX_CASES];

    state = safe_state->re_state;
    encoding = state->encoding;
    full_case_fold = encoding->full_case_fold;
    char_at = state->char_at;
    text = state->text;

    values = node->values;
    start_pos = text_pos;
    folded_pos = 0;
    folded_len = 0;
    length = node->value_count;
    string_pos = 0;

    /* We'll special-case the first character of the string. */
    case_count = encoding->all_cases(values[0], cases);

    while (string_pos < length || folded_pos < folded_len) {
        if (folded_pos >= folded_len) {
fetch:
            if (text_pos >= limit)
                return -1;

            folded_len = full_case_fold(char_at(text, text_pos), folded);
            folded_pos = 0;
        }

        if (string_pos == 0) {
            int i;

            for (i = 0; i < case_count; i++) {
                if (folded[0] == cases[i])
                    goto match;
            }

            ++start_pos;
            text_pos = start_pos;
            goto fetch;
        } else if (same_char_ign(encoding, values[string_pos],
          folded[folded_pos])) {
match:
            ++string_pos;
            ++folded_pos;

            if (folded_pos >= folded_len)
                ++text_pos;
        } else {
            ++start_pos;
            text_pos = start_pos;
            folded_pos = 0;
            folded_len = 0;
            string_pos = 0;
        }
    }

    if (new_pos)
        *new_pos = text_pos;

    return start_pos;
}

/* Performs a string search backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) string_search_fld_rev(RE_SafeState* safe_state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit, Py_ssize_t* new_pos) {
    RE_State* state;
    RE_EncodingTable* encoding;
    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    RE_CODE* values;
    Py_ssize_t start_pos;
    int folded_pos;
    int folded_len;
    Py_ssize_t length;
    Py_ssize_t string_pos;
    Py_UCS4 folded[RE_MAX_FOLDED];
    int case_count;
    Py_UCS4 cases[RE_MAX_CASES];

    state = safe_state->re_state;
    encoding = state->encoding;
    full_case_fold = encoding->full_case_fold;
    char_at = state->char_at;
    text = state->text;

    values = node->values;
    start_pos = text_pos;
    folded_pos = 0;
    folded_len = 0;
    length = node->value_count;
    string_pos = length;

    /* We'll special-case the last character of the string. */
    case_count = encoding->all_cases(values[length - 1], cases);

    while (string_pos > 0 || folded_pos > 0) {
        if (folded_pos <= 0) {
fetch:
            if (text_pos <= limit)
                return -1;

            folded_len = full_case_fold(char_at(text, text_pos - 1), folded);
            folded_pos = folded_len;
        }

        if (string_pos == length) {
            int i;

            for (i = 0; i < case_count; i++) {
                if (folded[folded_len - 1] == cases[i])
                    goto match;
            }

            --start_pos;
            text_pos = start_pos;
            goto fetch;
        } else if (same_char_ign(encoding, values[string_pos - 1],
          folded[folded_pos - 1])) {
match:
            --string_pos;
            --folded_pos;

            if (folded_pos <= 0)
                --text_pos;
        } else {
            --start_pos;
            text_pos = start_pos;
            folded_pos = 0;
            folded_len = 0;
            string_pos = length;
        }
    }

    if (new_pos)
        *new_pos = text_pos;

    return start_pos;
}

/* Performs a string search, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) string_search_ign(RE_SafeState* safe_state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit) {
    RE_State* state;
    Py_ssize_t found_pos;

    state = safe_state->re_state;

    /* Can the string fit the available space? */
    if (text_pos + (Py_ssize_t)node->value_count > limit)
        return -1;

    /* Has the node been initialised for fast searching, if necessary? */
    if (!(node->status & RE_STATUS_FAST_INIT)) {
        /* Ideally the pattern should immutable and shareable across threads.
         * Internally, however, it isn't. For safety we need to hold the GIL.
         */
        acquire_GIL(safe_state);

        /* Double-check because of multithreading. */
        if (!(node->status & RE_STATUS_FAST_INIT)) {
            build_fast_tables(state->encoding, node, TRUE);
            node->status |= RE_STATUS_FAST_INIT;
        }

        release_GIL(safe_state);
    }

    if (node->string.bad_character_offset)
        found_pos = fast_string_search_ign(state, node, text_pos, limit);
    else
        found_pos = simple_string_search_ign(state, node, text_pos, limit);

    return found_pos;
}

/* Performs a string search backwards, ignoring case. */
Py_LOCAL_INLINE(Py_ssize_t) string_search_ign_rev(RE_SafeState* safe_state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit) {
    RE_State* state;
    Py_ssize_t found_pos;

    state = safe_state->re_state;

    /* Can the string fit the available space? */
    if (text_pos - (Py_ssize_t)node->value_count < limit)
        return -1;

    /* Has the node been initialised for fast searching, if necessary? */
    if (!(node->status & RE_STATUS_FAST_INIT)) {
        /* Ideally the pattern should immutable and shareable across threads.
         * Internally, however, it isn't. For safety we need to hold the GIL.
         */
        acquire_GIL(safe_state);

        /* Double-check because of multithreading. */
        if (!(node->status & RE_STATUS_FAST_INIT)) {
            build_fast_tables_rev(state->encoding, node, TRUE);
            node->status |= RE_STATUS_FAST_INIT;
        }

        release_GIL(safe_state);
    }

    if (node->string.bad_character_offset)
        found_pos = fast_string_search_ign_rev(state, node, text_pos, limit);
    else
        found_pos = simple_string_search_ign_rev(state, node, text_pos, limit);

    return found_pos;
}

/* Performs a string search backwards. */
Py_LOCAL_INLINE(Py_ssize_t) string_search_rev(RE_SafeState* safe_state,
  RE_Node* node, Py_ssize_t text_pos, Py_ssize_t limit) {
    RE_State* state;
    Py_ssize_t found_pos;

    state = safe_state->re_state;

    /* Can the string fit the available space? */
    if (text_pos - (Py_ssize_t)node->value_count < limit)
        return -1;

    /* Has the node been initialised for fast searching, if necessary? */
    if (!(node->status & RE_STATUS_FAST_INIT)) {
        /* Ideally the pattern should immutable and shareable across threads.
         * Internally, however, it isn't. For safety we need to hold the GIL.
         */
        acquire_GIL(safe_state);

        /* Double-check because of multithreading. */
        if (!(node->status & RE_STATUS_FAST_INIT)) {
            build_fast_tables_rev(state->encoding, node, FALSE);
            node->status |= RE_STATUS_FAST_INIT;
        }

        release_GIL(safe_state);
    }

    if (node->string.bad_character_offset)
        found_pos = fast_string_search_rev(state, node, text_pos, limit);
    else
        found_pos = simple_string_search_rev(state, node, text_pos, limit);

    return found_pos;
}

/* Returns how many characters there could be before full case-folding. */
Py_LOCAL_INLINE(size_t) possible_unfolded_length(size_t length) {
    if (length == 0)
        return 0;

    if (length < RE_MAX_FOLDED)
        return 1;

    return length / RE_MAX_FOLDED;
}

/* Tries a match at the current text position.
 *
 * Returns TRUE and the next node and text position if the match succeeds.
 */
Py_LOCAL_INLINE(BOOL) try_match(RE_State* state, RE_NextNode* next, Py_ssize_t
  text_pos, RE_Position* next_position) {
    RE_Node* test;
    void* text;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);

    test = next->test;

    if (test->status & RE_STATUS_FUZZY) {
        next_position->node = next->node;
        next_position->text_pos = text_pos;
        return TRUE;
    }

    text = state->text;
    char_at = state->char_at;

    switch (test->op) {
    case RE_OP_ANY: /* Any character, except a newline. */
        if (text_pos >= state->slice_end || char_at(text, text_pos) == '\n')
            return FALSE;
        break;
    case RE_OP_ANY_ALL: /* Any character at all. */
        if (text_pos >= state->slice_end)
            return FALSE;
        break;
    case RE_OP_ANY_ALL_REV: /* Any character at all. */
        if (text_pos <= state->slice_start)
            return FALSE;
        break;
    case RE_OP_ANY_REV: /* Any character, except a newline. */
        if (text_pos <= state->slice_start || char_at(text, text_pos - 1) ==
          '\n')
            return FALSE;
        break;
    case RE_OP_ANY_U: /* Any character, except a line separator. */
        if (text_pos >= state->slice_end ||
          state->encoding->is_line_sep(char_at(text, text_pos)))
            return FALSE;
        break;
    case RE_OP_ANY_U_REV: /* Any character, except a line separator. */
        if (text_pos <= state->slice_start ||
          state->encoding->is_line_sep(char_at(text, text_pos - 1)))
            return FALSE;
        break;
    case RE_OP_BOUNDARY: /* At a word boundary. */
        if (state->encoding->at_boundary(state, text_pos) != test->match)
            return FALSE;
        break;
    case RE_OP_BRANCH: /* 2-way branch. */
        if (!try_match(state, &test->next_1, text_pos, next_position) &&
          !try_match(state, &test->nonstring.next_2, text_pos, next_position))
            return FALSE;
        break;
    case RE_OP_CHARACTER: /* A character literal. */
        if (text_pos >= state->slice_end || (char_at(text, text_pos) ==
          test->values[0]) != test->match)
            return FALSE;
        break;
    case RE_OP_CHARACTER_IGN: /* A character literal, ignoring case. */
        if (text_pos >= state->slice_end || same_char_ign(state->encoding,
          char_at(text, text_pos), test->values[0]) != test->match)
            return FALSE;
        break;
    case RE_OP_CHARACTER_IGN_REV: /* A character literal, ignoring case. */
        if (text_pos <= state->slice_start || same_char_ign(state->encoding,
          char_at(text, text_pos - 1), test->values[0]) != test->match)
            return FALSE;
        break;
    case RE_OP_CHARACTER_REV: /* A character literal. */
        if (text_pos <= state->slice_start || (char_at(text, text_pos - 1) ==
          test->values[0]) != test->match)
            return FALSE;
        break;
    case RE_OP_DEFAULT_BOUNDARY: /* At a default word boundary. */
        if (state->encoding->at_default_boundary(state, text_pos) !=
          test->match)
            return FALSE;
        break;
    case RE_OP_DEFAULT_END_OF_WORD: /* At a default end of a word. */
        if (state->encoding->at_default_word_end(state, text_pos) !=
          test->match)
            return FALSE;
        break;
    case RE_OP_DEFAULT_START_OF_WORD: /* At a default start of a word. */
        if (state->encoding->at_default_word_start(state, text_pos) !=
          test->match)
            return FALSE;
        break;
    case RE_OP_END_OF_LINE: /* At the end of a line. */
        if (text_pos != state->text_length && char_at(text, text_pos) != '\n')
            return FALSE;
        break;
    case RE_OP_END_OF_LINE_U: /* At the end of a line. */
        if (!state->encoding->at_line_end(state, text_pos))
            return FALSE;
        break;
    case RE_OP_END_OF_STRING: /* At the end of the string. */
        if (text_pos != state->text_length)
            return FALSE;
        break;
    case RE_OP_END_OF_STRING_LINE: /* At the end of the string or the final newline. */
        if (text_pos != state->text_length && text_pos != state->final_newline)
            return FALSE;
        break;
    case RE_OP_END_OF_STRING_LINE_U: /* At the end of the string or the final newline. */
        if (text_pos != state->text_length && text_pos !=
          state->final_line_sep)
            return FALSE;
        break;
    case RE_OP_END_OF_WORD: /* At end of a word. */
        if (state->encoding->at_word_end(state, text_pos) != test->match)
            return FALSE;
        break;
    case RE_OP_GRAPHEME_BOUNDARY: /* At a grapheme boundary. */
        if (state->encoding->at_grapheme_boundary(state, text_pos) !=
          test->match)
            return FALSE;
        break;
    case RE_OP_PROPERTY: /* A character property. */
        /* values are: property */
        if (text_pos >= state->slice_end ||
          state->encoding->has_property(test->values[0], char_at(text,
          text_pos)) != test->match)
            return FALSE;
        break;
    case RE_OP_PROPERTY_IGN: /* A character property, ignoring case. */
        /* values are: property */
        if (text_pos >= state->slice_end || !has_property_ign(state->encoding,
          test->values[0], char_at(text, text_pos)) != test->match)
            return FALSE;
        break;
    case RE_OP_PROPERTY_IGN_REV: /* A character property, ignoring case. */
        /* values are: property */
        if (text_pos <= state->slice_start ||
          !has_property_ign(state->encoding, test->values[0], char_at(text,
          text_pos - 1)) != test->match)
            return FALSE;
        break;
    case RE_OP_PROPERTY_REV: /* A character property. */
        /* values are: property */
        if (text_pos <= state->slice_start ||
          state->encoding->has_property(test->values[0], char_at(text, text_pos
          - 1)) != test->match)
            return FALSE;
        break;
    case RE_OP_RANGE: /* A range. */
        /* values are: range */
        if (text_pos >= state->slice_end || in_range(test->values[0],
          test->values[1], char_at(text, text_pos)) != test->match)
            return FALSE;
        break;
    case RE_OP_RANGE_IGN: /* A range, ignoring case. */
        /* values are: range */
        if (text_pos >= state->slice_end || in_range_ign(state->encoding,
          test->values[0], test->values[1], char_at(text, text_pos)) !=
          test->match)
            return FALSE;
        break;
    case RE_OP_RANGE_IGN_REV: /* A range, ignoring case. */
        /* values are: range */
        if (text_pos <= state->slice_start || in_range_ign(state->encoding,
          test->values[0], test->values[1], char_at(text, text_pos - 1)) !=
          test->match)
            return FALSE;
        break;
    case RE_OP_RANGE_REV: /* A range. */
        /* values are: range */
        if (text_pos <= state->slice_start || in_range(test->values[0],
          test->values[1], char_at(text, text_pos - 1)) != test->match)
            return FALSE;
        break;
    case RE_OP_SEARCH_ANCHOR: /* At the start of the search. */
        if (text_pos != state->search_anchor)
            return FALSE;
        break;
    case RE_OP_SET_DIFF: /* Character set. */
    case RE_OP_SET_INTER:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_UNION:
        if (text_pos >= state->slice_end || in_set(state->encoding, test,
          char_at(text, text_pos)) != test->match)
            return FALSE;
        break;
    case RE_OP_SET_DIFF_IGN: /* Character set, ignoring case. */
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_UNION_IGN:
        if (text_pos >= state->slice_end || in_set_ign(state->encoding, test,
          char_at(text, text_pos)) != test->match)
            return FALSE;
        break;
    case RE_OP_SET_DIFF_IGN_REV: /* Character set, ignoring case. */
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_UNION_IGN_REV:
        if (text_pos <= state->slice_start || in_set_ign(state->encoding, test,
          char_at(text, text_pos - 1)) != test->match)
            return FALSE;
        break;
    case RE_OP_SET_DIFF_REV: /* Character set. */
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION_REV:
        if (text_pos <= state->slice_start || in_set(state->encoding, test,
          char_at(text, text_pos - 1)) != test->match)
            return FALSE;
        break;
    case RE_OP_START_OF_LINE: /* At the start of a line. */
        if (text_pos != 0 && char_at(text, text_pos - 1) != '\n')
            return FALSE;
        break;
    case RE_OP_START_OF_LINE_U: /* At the start of a line. */
        if (!state->encoding->at_line_start(state, text_pos))
            return FALSE;
        break;
    case RE_OP_START_OF_STRING: /* At the start of the string. */
        if (text_pos != 0)
            return FALSE;
        break;
    case RE_OP_START_OF_WORD: /* At start of a word. */
        if (state->encoding->at_word_start(state, text_pos) != test->match)
            return FALSE;
        break;
    case RE_OP_STRING: /* A string literal. */
    {
        size_t length;
        size_t available;
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        RE_CODE* values;
        size_t i;

        length = test->value_count;
        available = state->slice_end - text_pos;
        if (length > available)
            return FALSE;

        char_at = state->char_at;
        values = test->values;

        for (i = 0; i < length; i++) {
            if (char_at(text, text_pos + i) != values[i])
                return FALSE;
        }
        break;
    }
    case RE_OP_STRING_FLD: /* A string literal, ignoring case. */
    {
        size_t length;
        Py_ssize_t available;
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        RE_EncodingTable* encoding;
        int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
        Py_ssize_t pos;
        size_t string_pos;
        RE_CODE* values;
        int folded_len;
        int folded_pos;
        Py_UCS4 folded[RE_MAX_FOLDED];

        length = test->value_count;
        available = state->slice_end - text_pos;
        if ((Py_ssize_t)possible_unfolded_length(length) > available)
            return FALSE;

        char_at = state->char_at;
        encoding = state->encoding;
        full_case_fold = encoding->full_case_fold;
        pos = text_pos;
        string_pos = 0;
        values = test->values;
        folded_len = 0;
        folded_pos = 0;

        while (string_pos < length) {
            if (folded_pos >= folded_len) {
                if (pos >= state->slice_end)
                    return FALSE;

                folded_len = full_case_fold(char_at(text, pos), folded);
                folded_pos = 0;
            }

            if (!same_char_ign(encoding, folded[folded_pos],
              values[string_pos]))
                return FALSE;

            ++string_pos;
            ++folded_pos;

            if (folded_pos >= folded_len)
                ++pos;
        }

        if (folded_pos < folded_len)
            return FALSE;

        next_position->node = next->match_next;
        if (next->match_step == 0)
            next_position->text_pos = text_pos;
        else
            next_position->text_pos = pos;

        return TRUE;
    }
    case RE_OP_STRING_FLD_REV: /* A string literal, ignoring case. */
    {
        size_t length;
        Py_ssize_t available;
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        RE_EncodingTable* encoding;
        int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
        Py_ssize_t pos;
        size_t string_pos;
        RE_CODE* values;
        int folded_len;
        int folded_pos;
        Py_UCS4 folded[RE_MAX_FOLDED];

        length = test->value_count;
        available = text_pos - state->slice_start;
        if ((Py_ssize_t)possible_unfolded_length(length) > available)
            return FALSE;

        char_at = state->char_at;
        encoding = state->encoding;
        full_case_fold = encoding->full_case_fold;
        pos = text_pos;
        string_pos = length;
        values = test->values;
        folded_len = 0;
        folded_pos = folded_len;

        while (string_pos > 0) {
            if (folded_pos <= 0) {
                if (pos <= state->slice_start)
                    return FALSE;

                folded_len = full_case_fold(char_at(text, pos - 1), folded);
                folded_pos = folded_len;
            }

            if (!same_char_ign(encoding, folded[folded_pos - 1],
              values[string_pos - 1]))
                return FALSE;

            --string_pos;
            --folded_pos;

            if (folded_pos <= 0)
                --pos;
        }

        if (folded_pos > 0)
            return FALSE;

        next_position->node = next->match_next;
        if (next->match_step == 0)
            next_position->text_pos = text_pos;
        else
            next_position->text_pos = pos;

        return TRUE;
    }
    case RE_OP_STRING_IGN: /* A string literal, ignoring case. */
    {
        size_t length;
        size_t available;
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        RE_EncodingTable* encoding;
        RE_CODE* values;
        size_t i;

        length = test->value_count;
        available = state->slice_end - text_pos;
        if (length > available)
            return FALSE;

        char_at = state->char_at;
        encoding = state->encoding;
        values = test->values;

        for (i = 0; i < length; i++) {
            if (!same_char_ign(encoding, char_at(text, text_pos + i),
              values[i]))
                return FALSE;
        }
        break;
    }
    case RE_OP_STRING_IGN_REV: /* A string literal, ignoring case. */
    {
        size_t length;
        size_t available;
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        RE_EncodingTable* encoding;
        RE_CODE* values;
        size_t i;

        length = test->value_count;
        available = text_pos - state->slice_start;
        if (length > available)
            return FALSE;

        char_at = state->char_at;
        encoding = state->encoding;
        values = test->values;
        text_pos -= length;

        for (i = 0; i < length; i++) {
            if (!same_char_ign(encoding, char_at(text, text_pos + i),
              values[i]))
                return FALSE;
        }

        text_pos += length;
        break;
    }
    case RE_OP_STRING_REV: /* A string literal. */
    {
        size_t length;
        size_t available;
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        RE_CODE* values;
        size_t i;

        length = test->value_count;
        available = text_pos - state->slice_start;
        if (length > available)
            return FALSE;

        char_at = state->char_at;
        values = test->values;
        text_pos -= length;

        for (i = 0; i < length; i++) {
            if (char_at(text, text_pos + i) != values[i])
                return FALSE;
        }

        text_pos += length;
        break;
    }
    default:
        next_position->node = next->node;
        next_position->text_pos = text_pos;
        return TRUE;
    }

    next_position->node = next->match_next;
    next_position->text_pos = text_pos + next->match_step;

    return TRUE;
}

Py_LOCAL_INLINE(BOOL) search_start(RE_SafeState* safe_state, RE_NextNode* next,
  RE_Position* new_position, int search_index);

/* Searches for the start of a match. */
Py_LOCAL_INLINE(BOOL) search_start(RE_SafeState* safe_state, RE_NextNode* next,
  RE_Position* new_position, int search_index) {
    RE_State* state;
    Py_ssize_t text_pos;
    RE_Node* test;
    RE_Node* node;
    Py_ssize_t start_pos;
    Py_ssize_t step;
    Py_ssize_t limit;
    RE_SearchPosition* info;

    state = safe_state->re_state;

    start_pos = state->text_pos;
    TRACE(("<<search_start>> at %d\n", start_pos))

    test = next->test;
    node = next->node;

    if (state->reverse) {
        if (start_pos < state->slice_start)
            return FALSE;

        limit = state->slice_start;
        step = -1;
    } else {
        if (start_pos > state->slice_end)
            return FALSE;

        limit = state->slice_end;
        step = 1;
    }

    if (test->status & RE_STATUS_FUZZY) {
        /* Don't call 'search_start' again. */
        state->pattern->do_search_start = FALSE;

        state->match_pos = start_pos;
        new_position->node = node;
        new_position->text_pos = start_pos;

        return TRUE;
    }

again:
    if (!state->pattern->is_fuzzy) {
        if (state->reverse) {
            if (start_pos - (Py_ssize_t)state->min_width < limit)
                return FALSE;
        } else {
            if (start_pos + (Py_ssize_t)state->min_width > limit)
                return FALSE;
        }
    }

    if (search_index < MAX_SEARCH_POSITIONS) {
        info = &state->search_positions[search_index];
        if (state->reverse) {
            if (info->start_pos >= 0 && info->start_pos >= start_pos &&
              start_pos >= info->match_pos) {

                state->match_pos = info->match_pos;

                new_position->text_pos = state->match_pos;
                new_position->node = node;

                return TRUE;
            }
        } else {
            if (info->start_pos >= 0 && info->start_pos <= start_pos &&
              start_pos <= info->match_pos) {

                state->match_pos = info->match_pos;

                new_position->text_pos = state->match_pos;
                new_position->node = node;

                return TRUE;
            }
        }
    } else
        info = NULL;

    switch (test->op) {
    case RE_OP_ANY: /* Any character, except a newline. */
        start_pos = match_many_ANY(state, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_ANY_ALL: /* Any character at all. */
        break;
    case RE_OP_ANY_ALL_REV: /* Any character at all backwards. */
        break;
    case RE_OP_ANY_REV: /* Any character backwards, except a newline. */
        start_pos = match_many_ANY_REV(state, start_pos, limit, FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_ANY_U: /* Any character, except a line separator. */
        start_pos = match_many_ANY_U(state, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_ANY_U_REV: /* Any character backwards, except a line separator. */
        start_pos = match_many_ANY_U_REV(state, start_pos, limit, FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_BOUNDARY: /* At a word boundary. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_boundary)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_boundary = state->encoding->at_boundary;

        for (;;) {
            if (at_boundary(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_CHARACTER: /* A character literal. */
        start_pos = match_many_CHARACTER(state, test, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_CHARACTER_IGN: /* A character literal, ignoring case. */
        start_pos = match_many_CHARACTER_IGN(state, test, start_pos, limit,
          FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_CHARACTER_IGN_REV: /* A character literal backwards, ignoring case. */
        start_pos = match_many_CHARACTER_IGN_REV(state, test, start_pos, limit,
          FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_CHARACTER_REV: /* A character literal backwards. */
        start_pos = match_many_CHARACTER_REV(state, test, start_pos, limit,
          FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_DEFAULT_BOUNDARY: /* At a default word boundary. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_default_boundary)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_default_boundary = state->encoding->at_default_boundary;

        for (;;) {
            if (at_default_boundary(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_DEFAULT_END_OF_WORD: /* At a default end of a word. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_default_word_end)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_default_word_end = state->encoding->at_default_word_end;

        for (;;) {
            if (at_default_word_end(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_DEFAULT_START_OF_WORD: /* At a default start of a word. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_default_word_start)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_default_word_start = state->encoding->at_default_word_start;

        for (;;) {
            if (at_default_word_start(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_END_OF_LINE: /* At the end of a line. */
    {
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        void* text;
        Py_ssize_t step;

        char_at = state->char_at;
        text = state->text;
        text_pos = start_pos;
        step = state->reverse ? -1 : 1;

        for (;;) {
            if (text_pos == state->text_length || char_at(text, text_pos) ==
              '\n')
                break;
            if (text_pos == limit)
                return FALSE;
            text_pos += step;
        }

        start_pos = text_pos;
        break;
    }
    case RE_OP_END_OF_STRING: /* At the end of the string. */
        if (state->reverse) {
            if (start_pos != state->text_length)
                return FALSE;
        } else {
            if (state->slice_end != state->text_length)
                return FALSE;
        }

        start_pos = state->text_length;
        break;
    case RE_OP_END_OF_STRING_LINE: /* At end of string or final newline. */
        if (state->reverse) {
            if (start_pos >= state->text_length)
                start_pos = state->text_length;
            else if (start_pos >= state->final_newline)
                start_pos = state->final_newline;
            else
                return FALSE;

            if (start_pos < state->slice_start)
                return FALSE;
        } else {
            if (start_pos <= state->final_newline)
                start_pos = state->final_newline;
            else if (start_pos <= state->text_length)
                start_pos = state->text_length;
            else
                return FALSE;

            if (start_pos > state->slice_end)
                return FALSE;
        }
        break;
    case RE_OP_END_OF_WORD: /* At end of a word. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_word_end)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_word_end = state->encoding->at_word_end;

        for (;;) {
            if (at_word_end(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_GRAPHEME_BOUNDARY: /* At a grapheme boundary. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_boundary)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_boundary = state->encoding->at_grapheme_boundary;

        for (;;) {
            if (at_boundary(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_PROPERTY: /* A character property. */
        start_pos = match_many_PROPERTY(state, test, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_PROPERTY_IGN: /* A character property, ignoring case. */
        start_pos = match_many_PROPERTY_IGN(state, test, start_pos, limit,
          FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_PROPERTY_IGN_REV: /* A character property backwards, ignoring case. */
        start_pos = match_many_PROPERTY_IGN_REV(state, test, start_pos, limit,
          FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_PROPERTY_REV: /* A character property backwards. */
        start_pos = match_many_PROPERTY_REV(state, test, start_pos, limit,
          FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_RANGE: /* A range. */
        start_pos = match_many_RANGE(state, test, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_RANGE_IGN: /* A range, ignoring case. */
        start_pos = match_many_RANGE_IGN(state, test, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_RANGE_IGN_REV: /* A range backwards, ignoring case. */
        start_pos = match_many_RANGE_IGN_REV(state, test, start_pos, limit,
          FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_RANGE_REV: /* A range backwards. */
        start_pos = match_many_RANGE_REV(state, test, start_pos, limit, FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_SEARCH_ANCHOR: /* At the start of the search. */
        if (state->reverse) {
            if (start_pos < state->search_anchor)
                return FALSE;
        } else {
            if (start_pos > state->search_anchor)
                return FALSE;
        }

        start_pos = state->search_anchor;
        break;
    case RE_OP_SET_DIFF: /* A set. */
    case RE_OP_SET_INTER:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_UNION:
        start_pos = match_many_SET(state, test, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_SET_DIFF_IGN: /* A set, ignoring case. */
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_UNION_IGN:
        start_pos = match_many_SET_IGN(state, test, start_pos, limit, FALSE);
        if (start_pos >= limit)
            return FALSE;
        break;
    case RE_OP_SET_DIFF_IGN_REV: /* A set backwards, ignoring case. */
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_UNION_IGN_REV:
        start_pos = match_many_SET_IGN_REV(state, test, start_pos, limit,
          FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_SET_DIFF_REV: /* A set backwards. */
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION_REV:
        start_pos = match_many_SET_REV(state, test, start_pos, limit, FALSE);
        if (start_pos <= limit)
            return FALSE;
        break;
    case RE_OP_START_OF_LINE: /* At the start of a line. */
    {
        Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
        void* text;
        Py_ssize_t step;
        Py_ssize_t text_pos;

        char_at = state->char_at;
        text = state->text;
        step = state->reverse ? -1 : 1;
        text_pos = start_pos - 1;

        --limit;

        for (;;) {
            if (text_pos < 0 || char_at(text, text_pos) == '\n')
                break;
            if (text_pos == limit)
                return FALSE;
            text_pos += step;
        }

        ++text_pos;
        ++limit;

        start_pos = text_pos;
        break;
    }
    case RE_OP_START_OF_STRING: /* At the start of the string. */
        if (state->reverse) {
            if (state->slice_start != 0)
                return FALSE;
        } else {
            if (start_pos != 0)
                return FALSE;
        }

        start_pos = 0;
        break;
    case RE_OP_START_OF_WORD: /* At start of a word. */
    {
        BOOL match;
        Py_ssize_t step;
        BOOL (*at_word_start)(RE_State* state, Py_ssize_t start_pos);

        match = test->match;
        step = state->reverse ? -1 : 1;
        at_word_start = state->encoding->at_word_start;

        for (;;) {
            if (at_word_start(state, start_pos) == match)
                break;
            if (start_pos == limit)
                return FALSE;
            start_pos += step;
        }
        break;
    }
    case RE_OP_STRING: /* A string literal. */
        if (!(test->status & RE_STATUS_REQUIRED) || start_pos !=
          state->req_pos) {
            start_pos = string_search(safe_state, test, start_pos, limit);
            if (start_pos < 0)
                return FALSE;
        }
        break;
    case RE_OP_STRING_FLD: /* A string literal, ignoring case. */
    {
        Py_ssize_t new_pos;

        if ((test->status & RE_STATUS_REQUIRED) && start_pos == state->req_pos)
          new_pos = state->req_end;
        else
            start_pos = string_search_fld(safe_state, test, start_pos,
              state->slice_end, &new_pos);
        if (start_pos < 0)
            return FALSE;

        /* Can we look further ahead? */
        if (test == node) {
            if (test->next_1.node && !try_match(state, &test->next_1, new_pos,
              new_position)) {
                ++start_pos;

                if (state->reverse) {
                    if (start_pos < state->slice_start)
                        return FALSE;
                } else {
                    if (start_pos > state->slice_end)
                        return FALSE;
                }

                goto again;
            }

            /* It's a possible match. */
            state->match_pos = start_pos;

            return TRUE;
        }
        break;
    }
    case RE_OP_STRING_FLD_REV: /* A string literal backwards, ignoring case. */
    {
        Py_ssize_t new_pos;

        if ((test->status & RE_STATUS_REQUIRED) && start_pos == state->req_pos)
          new_pos = state->req_end;
        else
            start_pos = string_search_fld_rev(safe_state, test, start_pos,
              state->slice_start, &new_pos);
        if (start_pos < 0)
            return FALSE;

        /* Can we look further ahead? */
        if (test == node) {
            if (test->next_1.node && !try_match(state, &test->next_1, new_pos,
              new_position)) {
                --start_pos;

                if (state->reverse) {
                    if (start_pos < state->slice_start)
                        return FALSE;
                } else {
                    if (start_pos > state->slice_end)
                        return FALSE;
                }

                goto again;
            }

            /* It's a possible match. */
            state->match_pos = start_pos;

            return TRUE;
        }
        break;
    }
    case RE_OP_STRING_IGN: /* A string literal, ignoring case. */
        if (!(test->status & RE_STATUS_REQUIRED) || start_pos !=
          state->req_pos) {
            start_pos = string_search_ign(safe_state, test, start_pos, limit);
            if (start_pos < 0)
                return FALSE;
        }
        break;
    case RE_OP_STRING_IGN_REV: /* A string literal backwards, ignoring case. */
        if (!(test->status & RE_STATUS_REQUIRED) || start_pos !=
          state->req_pos) {
            start_pos = string_search_ign_rev(safe_state, test, start_pos,
              limit);
            if (start_pos < 0)
                return FALSE;
        }
        break;
    case RE_OP_STRING_REV: /* A string literal backwards. */
        if (!(test->status & RE_STATUS_REQUIRED) || start_pos !=
          state->req_pos) {
            start_pos = string_search_rev(safe_state, test, start_pos, limit);
            if (start_pos < 0)
                return FALSE;
        }
        break;
    default:
        /* Don't call 'search_start' again. */
        state->pattern->do_search_start = FALSE;

        state->match_pos = start_pos;
        new_position->node = node;
        new_position->text_pos = start_pos;
        return TRUE;
    }

    text_pos = start_pos;

    /* Can we look further ahead? */
    if (test == node) {
        text_pos += test->step;

        if (test->next_1.node && !try_match(state, &test->next_1, text_pos,
          new_position)) {
            start_pos += step;

            if (state->reverse) {
                if (start_pos < state->slice_start)
                    return FALSE;
            } else {
                if (start_pos > state->slice_end)
                    return FALSE;
            }

            goto again;
        }
    } else {
        new_position->node = node;
        new_position->text_pos = start_pos;
    }

    /* It's a possible match. */
    state->match_pos = start_pos;

    if (info) {
        info->start_pos = state->text_pos;
        info->match_pos = state->match_pos;
    }

    return TRUE;
}

/* Saves a capture group. */
Py_LOCAL_INLINE(BOOL) save_capture(RE_SafeState* safe_state, size_t
  private_index, size_t public_index) {
    RE_State* state;
    RE_GroupData* private_group;
    RE_GroupData* public_group;

    state = safe_state->re_state;

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    private_group = &state->groups[private_index - 1];
    public_group = &state->groups[public_index - 1];

    /* Will the repeated captures ever be visible? */
    if (!state->visible_captures) {
        public_group->captures[0] = private_group->span;
        public_group->capture_count = 1;

        return TRUE;
    }

    if (public_group->capture_count >= public_group->capture_capacity) {
        size_t new_capacity;
        RE_GroupSpan* new_captures;

        new_capacity = public_group->capture_capacity * 2;
        new_capacity = RE_MAX(new_capacity, RE_INIT_CAPTURE_SIZE);
        new_captures = (RE_GroupSpan*)safe_realloc(safe_state,
           public_group->captures,new_capacity * sizeof(RE_GroupSpan));
        if (!new_captures)
            return FALSE;

        public_group->captures = new_captures;
        public_group->capture_capacity = new_capacity;
    }

    public_group->captures[public_group->capture_count++] =
      private_group->span;

    return TRUE;
}

/* Unsaves a capture group. */
Py_LOCAL_INLINE(void) unsave_capture(RE_State* state, size_t private_index,
  size_t public_index) {
    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    if (state->groups[public_index - 1].capture_count > 0)
        --state->groups[public_index - 1].capture_count;
}

/* Pushes the groups for backtracking. */
Py_LOCAL_INLINE(BOOL) push_groups(RE_SafeState* safe_state) {
    RE_State* state;
    size_t group_count;
    RE_SavedGroups* current;
    size_t g;

    state = safe_state->re_state;

    group_count = state->pattern->true_group_count;
    if (group_count == 0)
        return TRUE;

    current = state->current_saved_groups;

    if (current && current->next)
        current = current->next;
    else if (!current && state->first_saved_groups)
        current = state->first_saved_groups;
    else {
        RE_SavedGroups* new_block;

        new_block = (RE_SavedGroups*)safe_alloc(safe_state,
          sizeof(RE_SavedGroups));
        if (!new_block)
            return FALSE;

        new_block->spans = (RE_GroupSpan*)safe_alloc(safe_state, group_count *
          sizeof(RE_GroupSpan));
        new_block->counts = (size_t*)safe_alloc(safe_state, group_count *
          sizeof(size_t));
        if (!new_block->spans || !new_block->counts) {
            safe_dealloc(safe_state, new_block->spans);
            safe_dealloc(safe_state, new_block->counts);
            safe_dealloc(safe_state, new_block);
            return FALSE;
        }

        new_block->previous = current;
        new_block->next = NULL;

        if (new_block->previous)
            new_block->previous->next = new_block;
        else
            state->first_saved_groups = new_block;

        current = new_block;
    }

    for (g = 0; g < group_count; g++) {
        current->spans[g] = state->groups[g].span;
        current->counts[g] = state->groups[g].capture_count;
    }

    state->current_saved_groups = current;

    return TRUE;
}

/* Pops the groups for backtracking. */
Py_LOCAL_INLINE(void) pop_groups(RE_State* state) {
    size_t group_count;
    RE_SavedGroups* current;
    size_t g;

    group_count = state->pattern->true_group_count;
    if (group_count == 0)
        return;

    current = state->current_saved_groups;

    for (g = 0; g < group_count; g++) {
        state->groups[g].span = current->spans[g];
        state->groups[g].capture_count = current->counts[g];
    }

    state->current_saved_groups = current->previous;
}

/* Drops the groups for backtracking. */
Py_LOCAL_INLINE(void) drop_groups(RE_State* state) {
    if (state->pattern->true_group_count != 0)
        state->current_saved_groups = state->current_saved_groups->previous;
}

/* Pushes the repeats for backtracking. */
Py_LOCAL_INLINE(BOOL) push_repeats(RE_SafeState* safe_state) {
    RE_State* state;
    PatternObject* pattern;
    Py_ssize_t repeat_count;
    RE_SavedRepeats* current;
    Py_ssize_t r;

    state = safe_state->re_state;
    pattern = state->pattern;

    repeat_count = pattern->repeat_count;
    if (repeat_count == 0)
        return TRUE;

    current = state->current_saved_repeats;

    if (current && current->next)
        current = current->next;
    else if (!current && state->first_saved_repeats)
        current = state->first_saved_repeats;
    else {
        RE_SavedRepeats* new_block;

        new_block = (RE_SavedRepeats*)safe_alloc(safe_state,
          sizeof(RE_SavedRepeats));
        if (!new_block)
            return FALSE;

        memset(new_block, 0, sizeof(RE_SavedRepeats));

        new_block->repeats = (RE_RepeatData*)safe_alloc(safe_state,
          repeat_count * sizeof(RE_RepeatData));
        if (!new_block->repeats) {
            safe_dealloc(safe_state, new_block);
            return FALSE;
        }

        memset(new_block->repeats, 0, repeat_count * sizeof(RE_RepeatData));

        new_block->previous = current;
        new_block->next = NULL;

        if (new_block->previous)
            new_block->previous->next = new_block;
        else
            state->first_saved_repeats = new_block;

        current = new_block;
    }

    for (r = 0; r < repeat_count; r++) {
        if (!copy_repeat_data(safe_state, &current->repeats[r],
          &state->repeats[r]))
            return FALSE;
    }

    state->current_saved_repeats = current;

    return TRUE;
}

/* Pops the repeats for backtracking. */
Py_LOCAL_INLINE(void) pop_repeats(RE_State* state) {
    PatternObject* pattern;
    Py_ssize_t repeat_count;
    RE_SavedRepeats* current;
    Py_ssize_t r;

    pattern = state->pattern;

    repeat_count = pattern->repeat_count;
    if (repeat_count == 0)
        return;

    current = state->current_saved_repeats;

    for (r = 0; r < repeat_count; r++)
        copy_repeat_data(NULL, &state->repeats[r], &current->repeats[r]);

    state->current_saved_repeats = current->previous;
}

/* Saves state info before a recusive call by 'basic_match'. */
Py_LOCAL_INLINE(void) save_info(RE_State* state, RE_Info* info) {
    info->current_backtrack_block = state->current_backtrack_block;
    info->backtrack_count = info->current_backtrack_block->count;
    info->current_saved_groups = state->current_saved_groups;
    info->must_advance = state->must_advance;
    info->current_group_call_frame = state->current_group_call_frame;
}

/* Restores state info after a recusive call by 'basic_match'. */
Py_LOCAL_INLINE(void) restore_info(RE_State* state, RE_Info* info) {
    state->current_group_call_frame = info->current_group_call_frame;
    state->must_advance = info->must_advance;
    state->current_saved_groups = info->current_saved_groups;
    info->current_backtrack_block->count = info->backtrack_count;
    state->current_backtrack_block = info->current_backtrack_block;
}

/* Inserts a new span in a guard list. */
Py_LOCAL_INLINE(BOOL) insert_guard_span(RE_SafeState* safe_state, RE_GuardList*
  guard_list, Py_ssize_t index) {
    size_t n;

    if (guard_list->count >= guard_list->capacity) {
        size_t new_capacity;
        RE_GuardSpan* new_spans;

        new_capacity = guard_list->capacity * 2;
        if (new_capacity == 0)
            new_capacity = RE_INIT_GUARDS_BLOCK_SIZE;
        new_spans = (RE_GuardSpan*)safe_realloc(safe_state, guard_list->spans,
          new_capacity * sizeof(RE_GuardSpan));
        if (!new_spans)
            return FALSE;

        guard_list->capacity = new_capacity;
        guard_list->spans = new_spans;
    }

    n = guard_list->count - index;
    if (n > 0)
        memmove(guard_list->spans + index + 1, guard_list->spans + index, n *
          sizeof(RE_GuardSpan));
    ++guard_list->count;

    return TRUE;
}

/* Deletes a span in a guard list. */
Py_LOCAL_INLINE(void) delete_guard_span(RE_GuardList* guard_list, Py_ssize_t
  index) {
    size_t n;

    n = guard_list->count - index - 1;
    if (n > 0)
        memmove(guard_list->spans + index, guard_list->spans + index + 1, n *
          sizeof(RE_GuardSpan));
    --guard_list->count;
}

/* Checks whether a position is guarded against further matching. */
Py_LOCAL_INLINE(BOOL) is_guarded(RE_GuardList* guard_list, Py_ssize_t text_pos)
  {
    size_t low;
    size_t high;

    /* Is this position in the guard list? */
    low = 0;
    high = guard_list->count;
    while (low < high) {
        size_t mid;
        RE_GuardSpan* span;

        mid = (low + high) / 2;
        span = &guard_list->spans[mid];
        if (text_pos < span->low)
            high = mid;
        else if (text_pos > span->high)
            low = mid + 1;
        else
            return span->protect;
    }

    guard_list->last_text_pos = text_pos;
    guard_list->last_low = low;

    return FALSE;
}

/* Guards a position against further matching. */
Py_LOCAL_INLINE(BOOL) guard(RE_SafeState* safe_state, RE_GuardList* guard_list,
  Py_ssize_t text_pos, BOOL protect) {
    size_t low;
    size_t high;

    /* Where should be new position be added? */
    if (text_pos == guard_list->last_text_pos)
        low = guard_list->last_low;
    else {
        low = 0;
        high = guard_list->count;
        while (low < high) {
            size_t mid;
            RE_GuardSpan* span;

            mid = (low + high) / 2;
            span = &guard_list->spans[mid];
            if (text_pos < span->low)
                high = mid;
            else if (text_pos > span->high)
                low = mid + 1;
            else
                return TRUE;
        }
    }

    /* Add the position to the guard list. */
    if (low > 0 && guard_list->spans[low - 1].high + 1 == text_pos &&
      guard_list->spans[low - 1].protect == protect) {
        /* The new position is just above this span. */
        if (low < guard_list->count && guard_list->spans[low].low - 1 ==
          text_pos && guard_list->spans[low].protect == protect) {
            /* The new position joins 2 spans */
            guard_list->spans[low - 1].high = guard_list->spans[low].high;
            delete_guard_span(guard_list, low);
        } else
            /* Extend the span. */
            guard_list->spans[low - 1].high = text_pos;
    } else if (low < guard_list->count && guard_list->spans[low].low - 1 ==
      text_pos && guard_list->spans[low].protect == protect)
        /* The new position is just below this span. */
        /* Extend the span. */
        guard_list->spans[low].low = text_pos;
    else {
        /* Insert a new span. */
        if (!insert_guard_span(safe_state, guard_list, low))
            return FALSE;
        guard_list->spans[low].low = text_pos;
        guard_list->spans[low].high = text_pos;
        guard_list->spans[low].protect = protect;
    }

    guard_list->last_text_pos = -1;

    return TRUE;
}

/* Guards a position against further matching for a repeat. */
Py_LOCAL_INLINE(BOOL) guard_repeat(RE_SafeState* safe_state, size_t index,
  Py_ssize_t text_pos, RE_STATUS_T guard_type, BOOL protect) {
    RE_State* state;
    RE_GuardList* guard_list;

    state = safe_state->re_state;

    /* Is a guard active here? */
    if (!(state->pattern->repeat_info[index].status & guard_type))
        return TRUE;

    /* Which guard list? */
    if (guard_type & RE_STATUS_BODY)
        guard_list = &state->repeats[index].body_guard_list;
    else
        guard_list = &state->repeats[index].tail_guard_list;

    return guard(safe_state, guard_list, text_pos, protect);
}

/* Checks whether a position is guarded against further matching for a repeat.
 */
Py_LOCAL_INLINE(BOOL) is_repeat_guarded(RE_SafeState* safe_state, size_t index,
  Py_ssize_t text_pos, RE_STATUS_T guard_type) {
    RE_State* state;
    RE_GuardList* guard_list;

    state = safe_state->re_state;

    /* Is a guard active here? */
    if (!(state->pattern->repeat_info[index].status & guard_type))
        return FALSE;

    /* Which guard list? */
    if (guard_type == RE_STATUS_BODY)
        guard_list = &state->repeats[index].body_guard_list;
    else
        guard_list = &state->repeats[index].tail_guard_list;

    return is_guarded(guard_list, text_pos);
}

/* Resets the guards inside atomic subpatterns and lookarounds. */
Py_LOCAL_INLINE(void) reset_guards(RE_State* state, RE_CODE* values) {
    PatternObject* pattern;
    size_t repeat_count;

    pattern = state->pattern;
    repeat_count = (size_t)pattern->repeat_count;

    if (values) {
        size_t i;

        for (i = 1; i <= values[0]; i++) {
            size_t index;

            index = values[i];

            if (index < repeat_count) {
                reset_guard_list(&state->repeats[index].body_guard_list);
                reset_guard_list(&state->repeats[index].tail_guard_list);
            } else {
                index -= repeat_count;

                reset_guard_list(&state->fuzzy_guards[index].body_guard_list);
                reset_guard_list(&state->fuzzy_guards[index].tail_guard_list);
            }
        }
    } else {
        size_t index;
        size_t fuzzy_count;

        for (index = 0; index < repeat_count; index++) {
            reset_guard_list(&state->repeats[index].body_guard_list);
            reset_guard_list(&state->repeats[index].tail_guard_list);
        }

        fuzzy_count = pattern->fuzzy_count;

        for (index = 0; index < fuzzy_count; index++) {
            reset_guard_list(&state->fuzzy_guards[index].body_guard_list);
            reset_guard_list(&state->fuzzy_guards[index].tail_guard_list);
        }
    }
}

/* Builds a Unicode string. */
Py_LOCAL_INLINE(PyObject*) build_unicode_value(void* buffer, Py_ssize_t len,
  Py_ssize_t buffer_charsize) {
    return PyUnicode_FromUnicode(buffer, len);
}

/* Builds a bytestring. Returns NULL if any member is too wide. */
Py_LOCAL_INLINE(PyObject*) build_bytes_value(void* buffer, Py_ssize_t len,
  Py_ssize_t buffer_charsize)
{
    Py_UCS1* byte_buffer;
    Py_ssize_t i;
    PyObject* result;

    if (buffer_charsize == 1)
        return Py_BuildValue("s#", buffer, len);

    byte_buffer = re_alloc(len);
    if (!byte_buffer)
        return NULL;

    for (i = 0; i < len; i++) {
        Py_UCS2 c = ((Py_UCS2*)buffer)[i];
        if (c > 0xFF)
            goto too_wide;

        byte_buffer[i] = (Py_UCS1)c;
    }

    result = Py_BuildValue("s#", byte_buffer, len);

    re_dealloc(byte_buffer);

    return result;

too_wide:
    re_dealloc(byte_buffer);

    return NULL;
}

/* Looks for a string in a string set, ignoring case. */
Py_LOCAL_INLINE(int) string_set_contains_ign(RE_State* state, PyObject*
  string_set, void* buffer, Py_ssize_t index, Py_ssize_t len, Py_ssize_t
  buffer_charsize) {
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void (*set_char_at)(void* text, Py_ssize_t pos, Py_UCS4 ch);
    RE_EncodingTable* encoding;
    BOOL (*possible_turkic)(Py_UCS4 ch);
    Py_UCS4 codepoints[4];

    switch (buffer_charsize) {
    case 1:
        char_at = bytes1_char_at;
        set_char_at = bytes1_set_char_at;
        break;
    case 2:
        char_at = bytes2_char_at;
        set_char_at = bytes2_set_char_at;
        break;
    case 4:
        char_at = bytes4_char_at;
        set_char_at = bytes4_set_char_at;
        break;
    default:
        char_at = bytes1_char_at;
        set_char_at = bytes1_set_char_at;
        break;
    }

    encoding = state->encoding;
    possible_turkic = encoding->possible_turkic;

    /* Look for a possible Turkic 'I'. */
    while (index < len && !possible_turkic(char_at(buffer, index)))
        ++index;

    if (index < len) {
        /* Possible Turkic 'I'. */
        int count;
        int i;

        /* Try all the alternatives to the 'I'. */
        count = encoding->all_turkic_i(char_at(buffer, index), codepoints);

        for (i = 0; i < count; i++) {
            int status;

            set_char_at(buffer, index, codepoints[i]);

            /* Recurse for the remainder of the string. */
            status = string_set_contains_ign(state, string_set, buffer, index +
              1, len, buffer_charsize);
            if (status != 0)
                return status;
        }

        return 0;
    } else {
        /* No Turkic 'I'. */
        PyObject* string;
        int status;

        if (state->is_unicode)
            string = build_unicode_value(buffer, len, buffer_charsize);
        else
            string = build_bytes_value(buffer, len, buffer_charsize);
        if (!string)
            return RE_ERROR_MEMORY;

        status = PySet_Contains(string_set, string);
        Py_DECREF(string);

        return status;
    }
}

/* Tries to match a string at the current position with a member of a string
 * set, ignoring case, for a forwards or reverse search.
 */
Py_LOCAL_INLINE(int) string_set_match_ign_fwdrev(RE_SafeState* safe_state,
  RE_Node* node, BOOL reverse) {
    Py_ssize_t index;
    Py_ssize_t min_len;
    Py_ssize_t max_len;
    RE_State* state;
    Py_ssize_t available;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    Py_ssize_t text_pos;
    RE_EncodingTable* encoding;
    Py_UCS4 (*simple_case_fold)(Py_UCS4 ch);
    Py_ssize_t folded_charsize;
    void (*set_char_at)(void* text, Py_ssize_t pos, Py_UCS4 ch);
    void* folded;
    PyObject* string_set;
    int status;
    Py_ssize_t len;

    index = node->values[0];
    min_len = (Py_ssize_t)node->values[1];
    max_len = (Py_ssize_t)node->values[2];

    state = safe_state->re_state;

    available = reverse ? state->text_pos - state->slice_start :
      state->slice_end - state->text_pos;

    if (min_len > available)
        /* Too few characters for any match. */
        return 0;

    max_len = RE_MIN(max_len, available);

    char_at = state->char_at;
    text = state->text;
    text_pos = state->text_pos;
    encoding = state->encoding;
    simple_case_fold = encoding->simple_case_fold;

    acquire_GIL(safe_state);

    /* The folded string will have the same width as the original string. */
    folded_charsize = state->charsize;

    switch (folded_charsize) {
    case 1:
        set_char_at = bytes1_set_char_at;
        break;
    case 2:
        set_char_at = bytes2_set_char_at;
        break;
    case 4:
        set_char_at = bytes4_set_char_at;
        break;
    default:
        return 0;
    }

    /* Allocate a buffer for the folded string. */
    folded = re_alloc(max_len * folded_charsize);
    if (!folded)
        goto error;

    /* Fetch the string set. */
    string_set = PyList_GET_ITEM(state->pattern->named_list_indexes, index);
    if (!string_set)
        goto error;

    status = 0;

    /* Attempt matches for a decreasing length. */
    for (len = max_len; status == 0 && len >= min_len; len--) {
        Py_ssize_t offset;
        Py_ssize_t inc_len;
        int i;

        if (reverse) {
            offset = -len;
            inc_len = -len;
        } else {
            offset = 0;
            inc_len = len;
        }

        for (i = 0; i < len; i++) {
            Py_UCS4 ch;

            ch = simple_case_fold(char_at(text, text_pos + offset + i));
            set_char_at(folded, i, ch);
        }

        status = string_set_contains_ign(state, string_set, folded, 0, len,
          folded_charsize);

        if (status == 1)
            /* Advance past the match. */
            state->text_pos += inc_len;
     }

    re_dealloc(folded);

    release_GIL(safe_state);

    return status;

error:
    re_dealloc(folded);

    release_GIL(safe_state);

    return RE_ERROR_INTERNAL;
}

/* Tries to match a string at the current position with a member of a string
 * set.
 */
Py_LOCAL_INLINE(int) string_set_match(RE_SafeState* safe_state, RE_Node* node)
  {
    Py_ssize_t index;
    Py_ssize_t min_len;
    Py_ssize_t max_len;
    RE_State* state;
    Py_ssize_t available;
    void* (*point_to)(void* text, Py_ssize_t pos);
    void* text;
    Py_ssize_t text_pos;
    PyObject* string_set;
    int status;
    Py_ssize_t len;

    index = node->values[0];
    min_len = (Py_ssize_t)node->values[1];
    max_len = (Py_ssize_t)node->values[2];

    state = safe_state->re_state;

    available = state->slice_end - state->text_pos;
    if (min_len > available)
        /* Too few characters for any match. */
        return 0;

    max_len = RE_MIN(max_len, available);

    point_to = state->point_to;
    text = state->text;
    text_pos = state->text_pos;

    acquire_GIL(safe_state);

    /* Fetch the string set. */
    string_set = PyList_GET_ITEM(state->pattern->named_list_indexes, index);
    if (!string_set)
        goto error;

    status = 0;

    /* Attempt matches for a decreasing length. */
    for (len = max_len; status == 0 && len >= min_len; len--) {
        PyObject* string;

        if (state->is_unicode)
            string = build_unicode_value(point_to(text, text_pos), len,
              state->charsize);
        else
            string = build_bytes_value(point_to(text, text_pos), len,
              state->charsize);
        if (!string)
            goto error;

        status = PySet_Contains(string_set, string);
        Py_DECREF(string);

        if (status == 1)
            /* Advance past the match. */
            state->text_pos += len;
    }

    release_GIL(safe_state);

    return status;

error:
    release_GIL(safe_state);

    return RE_ERROR_INTERNAL;
}

/* Tries to match a string at the current position with a member of a string
 * set, ignoring case.
 */
Py_LOCAL_INLINE(int) string_set_match_fld(RE_SafeState* safe_state, RE_Node*
  node) {
    Py_ssize_t index;
    Py_ssize_t min_len;
    Py_ssize_t max_len;
    RE_State* state;
    Py_ssize_t available;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    Py_ssize_t text_pos;
    RE_EncodingTable* encoding;
    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
    Py_ssize_t buf_size;
    Py_ssize_t folded_charsize;
    void (*set_char_at)(void* text, Py_ssize_t pos, Py_UCS4 ch);
    void* folded;
    PyObject* string_set;
    int status;
    Py_ssize_t end_fetch;
    Py_ssize_t len;
    Py_UCS4 codepoints[RE_MAX_FOLDED];

    index = node->values[0];
    min_len = (Py_ssize_t)node->values[1];
    max_len = (Py_ssize_t)node->values[2];

    state = safe_state->re_state;

    available = state->slice_end - state->text_pos;
    if ((Py_ssize_t)possible_unfolded_length(min_len) > available)
        /* Too few characters for any match. */
        return 0;

    char_at = state->char_at;
    text = state->text;
    text_pos = state->text_pos;
    encoding = state->encoding;
    full_case_fold = encoding->full_case_fold;

    /* The folded string will have the same width as the original string. */
    folded_charsize = state->charsize;

    switch (folded_charsize) {
    case 1:
        set_char_at = bytes1_set_char_at;
        break;
    case 2:
        set_char_at = bytes2_set_char_at;
        break;
    case 4:
        set_char_at = bytes4_set_char_at;
        break;
    default:
        return 0;
    }

    acquire_GIL(safe_state);

    /* Allocate a buffer for the folded string, plus a little extra. */
    buf_size = max_len + RE_MAX_FOLDED;
    folded = re_alloc(buf_size * folded_charsize);
    if (!folded)
        goto error;

    /* Fetch the string set. */
    string_set = PyList_GET_ITEM(state->pattern->named_list_indexes, index);
    if (!string_set)
        goto error;

    status = 0;

    /* Attempt matches for a decreasing length. */
    end_fetch = text_pos + max_len;

    for (len = max_len; status == 0 && len >= min_len; len--) {
        Py_ssize_t pos;
        int folded_len;

        pos = text_pos;
        folded_len = 0;

        /* Fetch until we have enough characters. */
        while (pos < end_fetch && folded_len < len) {
            int count;
            int i;

            count = full_case_fold(char_at(text, pos), codepoints);

            for (i = 0; i < count; i++) {
                Py_UCS4 ch;

                ch = codepoints[i];
                set_char_at(folded, folded_len + i, ch);
            }

            folded_len += count;

            ++pos;
        }

        /* Do we have an acceptable number? */
        if (min_len <= folded_len && folded_len <= len) {
            status = string_set_contains_ign(state, string_set, folded, 0,
              folded_len, folded_charsize);

            if (status == 1)
                /* Advance past the match. */
                state->text_pos = pos;
        }

        /* If we got fewer than expected, next time we want still fewer. */
        len = RE_MIN(len, folded_len);

        /* Fetch one fewer next time. */
        end_fetch = pos - 1;
    }

    re_dealloc(folded);

    release_GIL(safe_state);

    return status;

error:
    re_dealloc(folded);

    release_GIL(safe_state);

    return RE_ERROR_INTERNAL;
}

/* Tries to match a string at the current position with a member of a string
 * set, ignoring case.
 */
Py_LOCAL_INLINE(int) string_set_match_fld_rev(RE_SafeState* safe_state,
  RE_Node* node) {
    Py_ssize_t index;
    Py_ssize_t min_len;
    Py_ssize_t max_len;
    RE_State* state;
    Py_ssize_t available;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    void* text;
    Py_ssize_t text_pos;
    RE_EncodingTable* encoding;
    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
    Py_ssize_t buf_size;
    Py_ssize_t folded_charsize;
    void (*set_char_at)(void* text, Py_ssize_t pos, Py_UCS4 ch);
    void* (*point_to)(void* text, Py_ssize_t pos);
    void* folded;
    PyObject* string_set;
    int status;
    Py_ssize_t end_fetch;
    Py_ssize_t len;
    Py_UCS4 codepoints[RE_MAX_FOLDED];

    index = node->values[0];
    min_len = (Py_ssize_t)node->values[1];
    max_len = (Py_ssize_t)node->values[2];

    state = safe_state->re_state;

    available = state->text_pos - state->slice_start;
    if ((Py_ssize_t)possible_unfolded_length(min_len) > available)
        /* Too few characters for any match. */
        return 0;

    char_at = state->char_at;
    text = state->text;
    text_pos = state->text_pos;
    encoding = state->encoding;
    full_case_fold = encoding->full_case_fold;

    /* The folded string will have the same width as the original string. */
    folded_charsize = state->charsize;

    switch (folded_charsize) {
    case 1:
        set_char_at = bytes1_set_char_at;
        point_to = bytes1_point_to;
        break;
    case 2:
        set_char_at = bytes2_set_char_at;
        point_to = bytes2_point_to;
        break;
    case 4:
        set_char_at = bytes4_set_char_at;
        point_to = bytes4_point_to;
        break;
    default:
        return 0;
    }

    acquire_GIL(safe_state);

    /* Allocate a buffer for the folded string, plus a little extra. */
    buf_size = max_len + RE_MAX_FOLDED;
    folded = re_alloc(buf_size * folded_charsize);
    if (!folded)
        goto error;

    /* Fetch the string set. */
    string_set = PyList_GET_ITEM(state->pattern->named_list_indexes, index);
    if (!string_set)
        goto error;

    status = 0;

    /* Attempt matches for a decreasing length. */
    end_fetch = text_pos - max_len;

    for (len = max_len; status == 0 && len >= min_len; len--) {
        Py_ssize_t pos;
        int folded_len;

        pos = text_pos;
        folded_len = 0;

        /* Fetch until we have enough characters. */
        while (pos > end_fetch && folded_len < len) {
            int count;
            int i;

            count = full_case_fold(char_at(text, pos - 1), codepoints);

            folded_len += count;

            for (i = 0; i < count; i++) {
                Py_UCS4 ch;

                ch = codepoints[i];
                set_char_at(folded, buf_size - folded_len + i, ch);
            }

            --pos;
        }

        /* Do we have an acceptable number? */
        if (min_len <= folded_len && folded_len <= len) {
            status = string_set_contains_ign(state, string_set,
              point_to(folded, buf_size - len), 0, folded_len,
              folded_charsize);

            if (status == 1)
                /* Advance past the match. */
                state->text_pos = pos;
        }

        /* If we got fewer than expected, next time we want still fewer. */
        len = RE_MIN(len, folded_len);

        /* Fetch one fewer next time. */
        end_fetch = pos + 1;
    }

    re_dealloc(folded);

    release_GIL(safe_state);

    return status;

error:
    re_dealloc(folded);

    release_GIL(safe_state);

    return RE_ERROR_INTERNAL;
}

/* Tries to match a string at the current position with a member of a string
 * set, ignoring case, for a forwards search.
 */
Py_LOCAL_INLINE(int) string_set_match_ign(RE_SafeState* safe_state, RE_Node*
  node) {
    return string_set_match_ign_fwdrev(safe_state, node, FALSE);
}

/* Tries to match a string at the current position with a member of a string
 * set, ignoring case, for a reverse search.
 */
Py_LOCAL_INLINE(int) string_set_match_ign_rev(RE_SafeState* safe_state,
  RE_Node* node) {
    return string_set_match_ign_fwdrev(safe_state, node, TRUE);
}

/* Tries to match a string at the current position with a member of a string
 * set.
 */
Py_LOCAL_INLINE(int) string_set_match_rev(RE_SafeState* safe_state, RE_Node*
  node) {
    Py_ssize_t index;
    Py_ssize_t min_len;
    Py_ssize_t max_len;
    RE_State* state;
    Py_ssize_t available;
    void* (*point_to)(void* text, Py_ssize_t pos);
    void* text;
    Py_ssize_t text_pos;
    PyObject* string_set;
    int status;
    Py_ssize_t len;

    index = node->values[0];
    min_len = (Py_ssize_t)node->values[1];
    max_len = (Py_ssize_t)node->values[2];

    state = safe_state->re_state;

    available = state->text_pos - state->slice_start;
    if (min_len > available)
        /* Too few characters for any match. */
        return 0;

    max_len = RE_MIN(max_len, available);

    point_to = state->point_to;
    text = state->text;
    text_pos = state->text_pos;

    acquire_GIL(safe_state);

    /* Fetch the string set. */
    string_set = PyList_GET_ITEM(state->pattern->named_list_indexes, index);
    if (!string_set)
        goto error;

    status = 0;

    /* Attempt matches for a decreasing length. */
    for (len = max_len; status == 0 && len >= min_len; len--) {
        PyObject* string;

        if (state->is_unicode)
            string = build_unicode_value(point_to(text, text_pos - len), len,
              state->charsize);
        else
            string = build_bytes_value(point_to(text, text_pos - len), len,
              state->charsize);
        if (!string)
            goto error;

        status = PySet_Contains(string_set, string);
        Py_DECREF(string);

        if (status == 1)
            /* Advance past the match. */
            state->text_pos -= len;
    }

    release_GIL(safe_state);

    return status;

error:
    release_GIL(safe_state);

    return RE_ERROR_INTERNAL;
}

/* Checks whether any additional fuzzy error is permitted. */
Py_LOCAL_INLINE(BOOL) any_error_permitted(RE_State* state) {
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    return fuzzy_info->total_cost <= values[RE_FUZZY_VAL_MAX_COST] &&
      fuzzy_info->counts[RE_FUZZY_ERR] < values[RE_FUZZY_VAL_MAX_ERR] &&
      state->total_cost <= state->max_cost;
}

/* Checks whether this additional fuzzy error is permitted. */
Py_LOCAL_INLINE(BOOL) this_error_permitted(RE_State* state, int fuzzy_type) {
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    return fuzzy_info->total_cost + values[RE_FUZZY_VAL_COST_BASE + fuzzy_type]
      <= values[RE_FUZZY_VAL_MAX_COST] && fuzzy_info->counts[fuzzy_type] <
      values[RE_FUZZY_VAL_MAX_BASE + fuzzy_type] && state->total_cost +
      values[RE_FUZZY_VAL_COST_BASE + fuzzy_type] <= state->max_cost;
}

Py_LOCAL_INLINE(BOOL) next_fuzzy_match_one(RE_State* state, RE_FuzzyData* data)
  {
    Py_ssize_t new_pos;

    if (this_error_permitted(state, data->fuzzy_type)) {
        switch (data->fuzzy_type) {
        case RE_FUZZY_DEL:
            /* Could a character at text_pos have been deleted? */
            data->new_node = data->new_node->next_1.node;
            return TRUE;
        case RE_FUZZY_INS:
            /* Could the character at text_pos have been inserted? */
            new_pos = data->new_text_pos + data->step;
            if (data->permit_insertion && state->slice_start <= new_pos &&
              new_pos <= state->slice_end) {
                data->new_text_pos = new_pos;
                return TRUE;
            }
            break;
        case RE_FUZZY_SUB:
            /* Could the character at text_pos have been substituted? */
            new_pos = data->new_text_pos + data->step;
            if (state->slice_start <= new_pos && new_pos <= state->slice_end) {
                data->new_text_pos = new_pos;
                data->new_node = data->new_node->next_1.node;
                return TRUE;
            }
            break;
        }
    }

    return FALSE;
}

/* Tries a fuzzy match of a single-character item. */
Py_LOCAL_INLINE(BOOL) fuzzy_match_one(RE_SafeState* safe_state, BOOL search,
  Py_ssize_t* text_pos, RE_Node** node, int step) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;

    if (!any_error_permitted(state)) {
        *node = NULL;
        return TRUE;
    }

    data.new_text_pos = *text_pos;
    data.new_node = *node;
    data.step = step;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || data.new_text_pos !=
      state->search_anchor;

    for (data.fuzzy_type = 0; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_one(state, &data))
            goto found;
    }

    *node = NULL;
    return TRUE;

found:
    if (!add_backtrack(safe_state, (*node)->op))
        return FALSE;
    bt_data = state->backtrack;
    bt_data->fuzzy_one.position.text_pos = *text_pos;
    bt_data->fuzzy_one.position.node = *node;
    bt_data->fuzzy_one.fuzzy_type = (RE_INT8)data.fuzzy_type;
    bt_data->fuzzy_one.step = (RE_INT8)step;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = data.new_text_pos;
    *node = data.new_node;

    return TRUE;
}

/* Retries a fuzzy match of a single-character item. */
Py_LOCAL_INLINE(BOOL) retry_fuzzy_match_one(RE_SafeState* safe_state, BOOL
  search, Py_ssize_t* text_pos, RE_Node** node) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;
    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    bt_data = state->backtrack;
    data.new_text_pos = bt_data->fuzzy_one.position.text_pos;
    data.new_node = bt_data->fuzzy_one.position.node;
    data.fuzzy_type = bt_data->fuzzy_one.fuzzy_type;
    data.step = bt_data->fuzzy_one.step;

    --fuzzy_info->counts[data.fuzzy_type];
    --fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    --state->total_errors;
    state->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || data.new_text_pos !=
      state->search_anchor;

    for (++data.fuzzy_type; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_one(state, &data))
            goto found;
    }

    discard_backtrack(state);
    *node = NULL;
    return TRUE;

found:
    bt_data->fuzzy_one.fuzzy_type = (RE_INT8)data.fuzzy_type;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = data.new_text_pos;
    *node = data.new_node;

    return TRUE;
}

Py_LOCAL_INLINE(BOOL) next_fuzzy_match_zero(RE_State* state, RE_FuzzyData*
  data) {
    if (this_error_permitted(state, data->fuzzy_type)) {
        switch (data->fuzzy_type) {
        case RE_FUZZY_DEL:
            /* Could a character at text_pos have been deleted? */
            data->new_node = data->new_node->next_1.node;
            return TRUE;
        case RE_FUZZY_INS:
            /* Could the character at text_pos have been inserted? */
            if (data->permit_insertion && data->new_text_pos != data->limit) {
                data->new_text_pos += data->step;
                return TRUE;
            }
            break;
        case RE_FUZZY_SUB:
            /* Could the character at text_pos have been substituted? */
            if (data->new_text_pos != data->limit) {
                data->new_node = data->new_node->next_1.node;
                return TRUE;
            }
            break;
        }
    }

    return FALSE;
}

/* Tries a fuzzy match of a zero-width item. */
Py_LOCAL_INLINE(BOOL) fuzzy_match_zero(RE_SafeState* safe_state, BOOL search,
  Py_ssize_t* text_pos, RE_Node** node) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;

    if (!any_error_permitted(state)) {
        *node = NULL;
        return TRUE;
    }

    data.new_text_pos = *text_pos;
    data.new_node = *node;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    if (data.new_node->status & RE_STATUS_REVERSE) {
        data.step = -1;
        data.limit = state->slice_start;
    } else {
        data.step = 1;
        data.limit = state->slice_end;
    }

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || data.new_text_pos !=
      state->search_anchor;

    for (data.fuzzy_type = 0; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_zero(state, &data))
            goto found;
    }

    *node = NULL;
    return TRUE;

found:
    if (!add_backtrack(safe_state, (*node)->op))
        return FALSE;
    bt_data = state->backtrack;
    bt_data->fuzzy_zero.position.text_pos = *text_pos;
    bt_data->fuzzy_zero.position.node = *node;
    bt_data->fuzzy_zero.fuzzy_type = (RE_INT8)data.fuzzy_type;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = data.new_text_pos;
    *node = data.new_node;

    return TRUE;
}

/* Retries a fuzzy match of a zero-width item. */
Py_LOCAL_INLINE(BOOL) retry_fuzzy_match_zero(RE_SafeState* safe_state, BOOL
  search, Py_ssize_t* text_pos, RE_Node** node) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;
    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    bt_data = state->backtrack;
    data.new_text_pos = bt_data->fuzzy_zero.position.text_pos;
    data.new_node = bt_data->fuzzy_zero.position.node;
    data.fuzzy_type = bt_data->fuzzy_zero.fuzzy_type;

    if (data.new_node->status & RE_STATUS_REVERSE) {
        data.step = -1;
        data.limit = state->slice_start;
    } else {
        data.step = 1;
        data.limit = state->slice_end;
    }

    if (data.fuzzy_type >= 0) {
        --fuzzy_info->counts[data.fuzzy_type];
        --fuzzy_info->counts[RE_FUZZY_ERR];
        fuzzy_info->total_cost -= values[RE_FUZZY_VAL_COST_BASE +
          data.fuzzy_type];
        --state->total_errors;
        state->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    }

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || data.new_text_pos !=
      state->search_anchor;

    for (++data.fuzzy_type; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_zero(state, &data))
            goto found;
    }

    discard_backtrack(state);
    *node = NULL;
    return TRUE;

found:
    bt_data->fuzzy_zero.fuzzy_type = (RE_INT8)data.fuzzy_type;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = data.new_text_pos;
    *node = data.new_node;

    return TRUE;
}

/* Tries a fuzzy insertion. */
Py_LOCAL_INLINE(BOOL) fuzzy_insert(RE_SafeState* safe_state, Py_ssize_t
  text_pos, RE_Node* node) {
    RE_State* state;
    RE_BacktrackData* bt_data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;

    state = safe_state->re_state;

    /* No insertion or deletion. */
    if (!add_backtrack(safe_state, node->op))
        return FALSE;
    bt_data = state->backtrack;
    bt_data->fuzzy_insert.position.text_pos = text_pos;
    bt_data->fuzzy_insert.position.node = node;
    bt_data->fuzzy_insert.count = 0;
    bt_data->fuzzy_insert.too_few_errors = state->too_few_errors;
    bt_data->fuzzy_insert.fuzzy_node = node; /* END_FUZZY node. */

    /* Check whether there are too few errors. */
    fuzzy_info = &state->fuzzy_info;

    /* The node in this case is the END_FUZZY node. */
    values = node->values;

    if (fuzzy_info->counts[RE_FUZZY_DEL] < values[RE_FUZZY_VAL_MIN_DEL] ||
      fuzzy_info->counts[RE_FUZZY_INS] < values[RE_FUZZY_VAL_MIN_INS] ||
      fuzzy_info->counts[RE_FUZZY_SUB] < values[RE_FUZZY_VAL_MIN_SUB] ||
      fuzzy_info->counts[RE_FUZZY_ERR] < values[RE_FUZZY_VAL_MIN_ERR])
      state->too_few_errors = TRUE;

    return TRUE;
}

/* Retries a fuzzy insertion. */
Py_LOCAL_INLINE(BOOL) retry_fuzzy_insert(RE_SafeState* safe_state, Py_ssize_t*
  text_pos, RE_Node** node) {
    RE_State* state;
    RE_FuzzyInfo* fuzzy_info;
    RE_BacktrackData* bt_data;
    Py_ssize_t new_text_pos;
    RE_Node* new_node;
    int step;
    Py_ssize_t limit;
    RE_Node* fuzzy_node;
    RE_CODE* values;

    state = safe_state->re_state;
    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    bt_data = state->backtrack;
    new_text_pos = bt_data->fuzzy_insert.position.text_pos;
    new_node = bt_data->fuzzy_insert.position.node;

    if (new_node->status & RE_STATUS_REVERSE) {
        step = -1;
        limit = state->slice_start;
    } else {
        step = 1;
        limit = state->slice_end;
    }

    /* Could the character at text_pos have been inserted? */
    if (!this_error_permitted(state, RE_FUZZY_INS) || new_text_pos == limit) {
        Py_ssize_t count;

        count = bt_data->fuzzy_insert.count;

        fuzzy_info->counts[RE_FUZZY_INS] -= count;
        fuzzy_info->counts[RE_FUZZY_ERR] -= count;
        fuzzy_info->total_cost -= values[RE_FUZZY_VAL_INS_COST] * count;
        state->total_errors -= count;
        state->total_cost -= values[RE_FUZZY_VAL_INS_COST] * count;
        state->too_few_errors = bt_data->fuzzy_insert.too_few_errors;

        discard_backtrack(state);
        *node = NULL;
        return TRUE;
    }

    ++bt_data->fuzzy_insert.count;

    ++fuzzy_info->counts[RE_FUZZY_INS];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_INS_COST];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_INS_COST];

    /* Check whether there are too few errors. */
    state->too_few_errors = bt_data->fuzzy_insert.too_few_errors;
    fuzzy_node = bt_data->fuzzy_insert.fuzzy_node; /* END_FUZZY node. */
    values = fuzzy_node->values;
    if (fuzzy_info->counts[RE_FUZZY_DEL] < values[RE_FUZZY_VAL_MIN_DEL] ||
      fuzzy_info->counts[RE_FUZZY_INS] < values[RE_FUZZY_VAL_MIN_INS] ||
      fuzzy_info->counts[RE_FUZZY_SUB] < values[RE_FUZZY_VAL_MIN_SUB] ||
      fuzzy_info->counts[RE_FUZZY_ERR] < values[RE_FUZZY_VAL_MIN_ERR])
      state->too_few_errors = TRUE;

    *text_pos = new_text_pos + step * bt_data->fuzzy_insert.count;
    *node = new_node;

    return TRUE;
}

Py_LOCAL_INLINE(BOOL) next_fuzzy_match_string(RE_State* state, RE_FuzzyData*
  data) {
    Py_ssize_t new_pos;

    if (this_error_permitted(state, data->fuzzy_type)) {
        switch (data->fuzzy_type) {
        case RE_FUZZY_DEL:
            /* Could a character at text_pos have been deleted? */
            data->new_string_pos += data->step;
            return TRUE;
        case RE_FUZZY_INS:
            /* Could the character at text_pos have been inserted? */
            new_pos = data->new_text_pos + data->step;
            if (data->permit_insertion && state->slice_start <= new_pos &&
              new_pos <= state->slice_end) {
                data->new_text_pos = new_pos;
                return TRUE;
            }
            break;
        case RE_FUZZY_SUB:
            /* Could the character at text_pos have been substituted? */
            new_pos = data->new_text_pos + data->step;
            if (state->slice_start <= new_pos && new_pos <= state->slice_end) {
                data->new_text_pos = new_pos;
                data->new_string_pos += data->step;
                return TRUE;
            }
            break;
        }
    }

    return FALSE;
}

/* Tries a fuzzy match of a string. */
Py_LOCAL_INLINE(BOOL) fuzzy_match_string(RE_SafeState* safe_state, BOOL search,
  Py_ssize_t* text_pos, RE_Node* node, Py_ssize_t* string_pos, BOOL* matched,
  int step) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;

    if (!any_error_permitted(state)) {
        *matched = FALSE;
        return TRUE;
    }

    data.new_text_pos = *text_pos;
    data.new_string_pos = *string_pos;
    data.step = step;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || data.new_text_pos !=
      state->search_anchor;

    for (data.fuzzy_type = 0; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_string(state, &data))
            goto found;
    }

    *matched = FALSE;
    return TRUE;

found:
    if (!add_backtrack(safe_state, node->op))
        return FALSE;
    bt_data = state->backtrack;
    bt_data->fuzzy_string.position.text_pos = *text_pos;
    bt_data->fuzzy_string.position.node = node;
    bt_data->fuzzy_string.string_pos = *string_pos;
    bt_data->fuzzy_string.fuzzy_type = (RE_INT8)data.fuzzy_type;
    bt_data->fuzzy_string.step = (RE_INT8)step;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = data.new_text_pos;
    *string_pos = data.new_string_pos;
    *matched = TRUE;

    return TRUE;
}

/* Retries a fuzzy match of a string. */
Py_LOCAL_INLINE(BOOL) retry_fuzzy_match_string(RE_SafeState* safe_state, BOOL
  search, Py_ssize_t* text_pos, RE_Node** node, Py_ssize_t* string_pos, BOOL*
  matched) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;
    RE_Node* new_node;

    state = safe_state->re_state;
    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    bt_data = state->backtrack;
    data.new_text_pos = bt_data->fuzzy_string.position.text_pos;
    new_node = bt_data->fuzzy_string.position.node;
    data.new_string_pos = bt_data->fuzzy_string.string_pos;
    data.fuzzy_type = bt_data->fuzzy_string.fuzzy_type;
    data.step = bt_data->fuzzy_string.step;

    --fuzzy_info->counts[data.fuzzy_type];
    --fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    --state->total_errors;
    state->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || data.new_text_pos !=
      state->search_anchor;

    for (++data.fuzzy_type; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_string(state, &data))
            goto found;
    }

    discard_backtrack(state);
    *matched = FALSE;
    return TRUE;

found:
    bt_data->fuzzy_string.fuzzy_type = (RE_INT8)data.fuzzy_type;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = data.new_text_pos;
    *node = new_node;
    *string_pos = data.new_string_pos;
    *matched = TRUE;

    return TRUE;
}

Py_LOCAL_INLINE(BOOL) next_fuzzy_match_string_fld(RE_State* state,
  RE_FuzzyData* data) {
    int new_pos;

    if (this_error_permitted(state, data->fuzzy_type)) {
        switch (data->fuzzy_type) {
        case RE_FUZZY_DEL:
            /* Could a character at text_pos have been deleted? */
            data->new_string_pos += data->step;
            return TRUE;
        case RE_FUZZY_INS:
            /* Could the character at text_pos have been inserted? */
            new_pos = data->new_folded_pos + data->step;
            if (data->permit_insertion && 0 <= new_pos && new_pos <=
              data->folded_len) {
                data->new_folded_pos = new_pos;
                return TRUE;
            }
            break;
        case RE_FUZZY_SUB:
            /* Could the character at text_pos have been substituted? */
            new_pos = data->new_folded_pos + data->step;
            if (0 <= new_pos && new_pos <= data->folded_len) {
                data->new_folded_pos = new_pos;
                data->new_string_pos += data->step;
                return TRUE;
            }
            break;
        }
    }

    return FALSE;
}

/* Tries a fuzzy match of a string, ignoring case. */
Py_LOCAL_INLINE(BOOL) fuzzy_match_string_fld(RE_SafeState* safe_state, BOOL
  search, Py_ssize_t* text_pos, RE_Node* node, Py_ssize_t* string_pos, int*
  folded_pos, int folded_len, BOOL* matched, int step) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    Py_ssize_t new_text_pos;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;

    if (!any_error_permitted(state)) {
        *matched = FALSE;
        return TRUE;
    }

    new_text_pos = *text_pos;
    data.new_string_pos = *string_pos;
    data.new_folded_pos = *folded_pos;
    data.folded_len = folded_len;
    data.step = step;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || new_text_pos != state->search_anchor;
    if (step > 0)
        data.permit_insertion |= data.new_folded_pos != 0;
    else
        data.permit_insertion |= data.new_folded_pos != folded_len;

    for (data.fuzzy_type = 0; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_string_fld(state, &data))
            goto found;
    }

    *matched = FALSE;
    return TRUE;

found:
    if (!add_backtrack(safe_state, node->op))
        return FALSE;
    bt_data = state->backtrack;
    bt_data->fuzzy_string.position.text_pos = *text_pos;
    bt_data->fuzzy_string.position.node = node;
    bt_data->fuzzy_string.string_pos = *string_pos;
    bt_data->fuzzy_string.folded_pos = (RE_INT8)(*folded_pos);
    bt_data->fuzzy_string.folded_len = (RE_INT8)folded_len;
    bt_data->fuzzy_string.fuzzy_type = (RE_INT8)data.fuzzy_type;
    bt_data->fuzzy_string.step = (RE_INT8)step;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = new_text_pos;
    *string_pos = data.new_string_pos;
    *folded_pos = data.new_folded_pos;
    *matched = TRUE;

    return TRUE;
}

/* Retries a fuzzy match of a string, ignoring case. */
Py_LOCAL_INLINE(BOOL) retry_fuzzy_match_string_fld(RE_SafeState* safe_state,
  BOOL search, Py_ssize_t* text_pos, RE_Node** node, Py_ssize_t* string_pos,
  int* folded_pos, BOOL* matched) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;
    Py_ssize_t new_text_pos;
    RE_Node* new_node;

    state = safe_state->re_state;
    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    bt_data = state->backtrack;
    new_text_pos = bt_data->fuzzy_string.position.text_pos;
    new_node = bt_data->fuzzy_string.position.node;
    data.new_string_pos = bt_data->fuzzy_string.string_pos;
    data.new_folded_pos = bt_data->fuzzy_string.folded_pos;
    data.fuzzy_type = bt_data->fuzzy_string.fuzzy_type;
    data.step = bt_data->fuzzy_string.step;

    --fuzzy_info->counts[data.fuzzy_type];
    --fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    --state->total_errors;
    state->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || new_text_pos != state->search_anchor;
    if (data.step > 0)
        data.permit_insertion |= data.new_folded_pos != 0;
    else
        data.permit_insertion |= data.new_folded_pos !=
          bt_data->fuzzy_string.folded_len;

    for (++data.fuzzy_type; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_string_fld(state, &data))
            goto found;
    }

    discard_backtrack(state);
    *matched = FALSE;
    return TRUE;

found:
    bt_data->fuzzy_string.fuzzy_type = (RE_INT8)data.fuzzy_type;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = new_text_pos;
    *node = new_node;
    *string_pos = data.new_string_pos;
    *folded_pos = data.new_folded_pos;
    *matched = TRUE;

    return TRUE;
}

Py_LOCAL_INLINE(BOOL) next_fuzzy_match_string_fld2(RE_State* state,
  RE_FuzzyData* data) {
    int new_pos;

    if (this_error_permitted(state, data->fuzzy_type)) {
        switch (data->fuzzy_type) {
        case RE_FUZZY_DEL:
            /* Could a character at text_pos have been deleted? */
            data->new_gfolded_pos += data->step;
            return TRUE;
        case RE_FUZZY_INS:
            /* Could the character at text_pos have been inserted? */
            new_pos = data->new_folded_pos + data->step;
            if (data->permit_insertion && 0 <= new_pos && new_pos <=
              data->folded_len) {
                data->new_folded_pos = new_pos;
                return TRUE;
            }
            break;
        case RE_FUZZY_SUB:
            /* Could the character at text_pos have been substituted? */
            new_pos = data->new_folded_pos + data->step;
            if (0 <= new_pos && new_pos <= data->folded_len) {
                data->new_folded_pos = new_pos;
                data->new_gfolded_pos += data->step;
                return TRUE;
            }
            break;
        }
    }

    return FALSE;
}

/* Tries a fuzzy match of a group reference, ignoring case. */
Py_LOCAL_INLINE(BOOL) fuzzy_match_string_fld2(RE_SafeState* safe_state, BOOL
  search, Py_ssize_t* text_pos, RE_Node* node, int* folded_pos, int folded_len,
  Py_ssize_t* group_pos, int* gfolded_pos, int gfolded_len, BOOL* matched, int
  step) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    Py_ssize_t new_text_pos;
    Py_ssize_t new_group_pos;
    RE_BacktrackData* bt_data;

    state = safe_state->re_state;

    if (!any_error_permitted(state)) {
        *matched = FALSE;
        return TRUE;
    }

    new_text_pos = *text_pos;
    data.new_folded_pos = *folded_pos;
    data.folded_len = folded_len;
    new_group_pos = *group_pos;
    data.new_gfolded_pos = *gfolded_pos;
    data.step = step;

    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || new_text_pos != state->search_anchor;
    if (step > 0)
        data.permit_insertion |= data.new_folded_pos != 0;
    else
        data.permit_insertion |= data.new_folded_pos != folded_len;

    for (data.fuzzy_type = 0; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_string_fld2(state, &data))
            goto found;
    }

    *matched = FALSE;
    return TRUE;

found:
    if (!add_backtrack(safe_state, node->op))
        return FALSE;
    bt_data = state->backtrack;
    bt_data->fuzzy_string.position.text_pos = *text_pos;
    bt_data->fuzzy_string.position.node = node;
    bt_data->fuzzy_string.string_pos = *group_pos;
    bt_data->fuzzy_string.folded_pos = (RE_INT8)(*folded_pos);
    bt_data->fuzzy_string.folded_len = (RE_INT8)folded_len;
    bt_data->fuzzy_string.gfolded_pos = (RE_INT8)(*gfolded_pos);
    bt_data->fuzzy_string.gfolded_len = (RE_INT8)gfolded_len;
    bt_data->fuzzy_string.fuzzy_type = (RE_INT8)data.fuzzy_type;
    bt_data->fuzzy_string.step = (RE_INT8)step;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = new_text_pos;
    *group_pos = new_group_pos;
    *folded_pos = data.new_folded_pos;
    *gfolded_pos = data.new_gfolded_pos;
    *matched = TRUE;

    return TRUE;
}

/* Retries a fuzzy match of a group reference, ignoring case. */
Py_LOCAL_INLINE(BOOL) retry_fuzzy_match_string_fld2(RE_SafeState* safe_state,
  BOOL search, Py_ssize_t* text_pos, RE_Node** node, int* folded_pos,
  Py_ssize_t* group_pos, int* gfolded_pos, BOOL* matched) {
    RE_State* state;
    RE_FuzzyData data;
    RE_FuzzyInfo* fuzzy_info;
    RE_CODE* values;
    RE_BacktrackData* bt_data;
    Py_ssize_t new_text_pos;
    Py_ssize_t new_group_pos;
    RE_Node* new_node;

    state = safe_state->re_state;
    fuzzy_info = &state->fuzzy_info;
    values = fuzzy_info->node->values;

    bt_data = state->backtrack;
    new_text_pos = bt_data->fuzzy_string.position.text_pos;
    new_node = bt_data->fuzzy_string.position.node;
    new_group_pos = bt_data->fuzzy_string.string_pos;
    data.new_folded_pos = bt_data->fuzzy_string.folded_pos;
    data.new_gfolded_pos = bt_data->fuzzy_string.gfolded_pos;
    data.fuzzy_type = bt_data->fuzzy_string.fuzzy_type;
    data.step = bt_data->fuzzy_string.step;

    --fuzzy_info->counts[data.fuzzy_type];
    --fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    --state->total_errors;
    state->total_cost -= values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    /* Permit insertion except initially when searching (it's better just to
     * start searching one character later).
     */
    data.permit_insertion = !search || new_text_pos != state->search_anchor ||
      data.new_folded_pos != bt_data->fuzzy_string.folded_len;

    for (++data.fuzzy_type; data.fuzzy_type < RE_FUZZY_COUNT;
      data.fuzzy_type++) {
        if (next_fuzzy_match_string_fld2(state, &data))
            goto found;
    }

    discard_backtrack(state);
    *matched = FALSE;
    return TRUE;

found:
    bt_data->fuzzy_string.fuzzy_type = (RE_INT8)data.fuzzy_type;

    ++fuzzy_info->counts[data.fuzzy_type];
    ++fuzzy_info->counts[RE_FUZZY_ERR];
    fuzzy_info->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];
    ++state->total_errors;
    state->total_cost += values[RE_FUZZY_VAL_COST_BASE + data.fuzzy_type];

    *text_pos = new_text_pos;
    *node = new_node;
    *group_pos = new_group_pos;
    *folded_pos = data.new_folded_pos;
    *gfolded_pos = data.new_gfolded_pos;
    *matched = TRUE;

    return TRUE;
}

/* Locates the required string, if there's one. */
Py_LOCAL_INLINE(Py_ssize_t) locate_required_string(RE_SafeState* safe_state) {
    RE_State* state;
    PatternObject* pattern;
    Py_ssize_t found_pos;
    Py_ssize_t end_pos;

    state = safe_state->re_state;
    pattern = state->pattern;

    /* We haven't matched the required string yet. */
    state->req_pos = -1;

    if (!pattern->req_string)
        /* There isn't a required string, so start matching from the current
         * position.
         */
        return state->text_pos;

    /* Search for the required string and calculate where to start matching. */
    switch (pattern->req_string->op) {
    case RE_OP_STRING:
        found_pos = string_search(safe_state, pattern->req_string,
          state->text_pos, state->slice_end);
        if (found_pos < 0)
            /* The required string wasn't found. */
            return -1;

        /* Record where the required string matched. */
        state->req_pos = found_pos;
        state->req_end = found_pos + pattern->req_string->value_count;

        if (pattern->req_offset >= 0) {
            /* Step back from the required string to where we should start
             * matching.
             */
            found_pos -= pattern->req_offset;
            if (found_pos >= state->text_pos)
                return found_pos;
        }
        break;
    case RE_OP_STRING_FLD:
        found_pos = string_search_fld(safe_state, pattern->req_string,
          state->text_pos, state->slice_end, &end_pos);
        if (found_pos < 0)
            /* The required string wasn't found. */
            return -1;

        /* Record where the required string matched. */
        state->req_pos = found_pos;
        state->req_end = end_pos;

        if (pattern->req_offset >= 0) {
            /* Step back from the required string to where we should start
             * matching.
             */
            found_pos -= pattern->req_offset;
            if (found_pos >= state->text_pos)
                return found_pos;
        }
        break;
    case RE_OP_STRING_FLD_REV:
        found_pos = string_search_fld_rev(safe_state, pattern->req_string,
          state->text_pos, state->slice_start, &end_pos);
        if (found_pos < 0)
            /* The required string wasn't found. */
            return -1;

        /* Record where the required string matched. */
        state->req_pos = found_pos;
        state->req_end = end_pos;

        if (pattern->req_offset >= 0) {
            /* Step back from the required string to where we should start
             * matching.
             */
            found_pos += pattern->req_offset;
            if (found_pos <= state->text_pos)
                return found_pos;
        }
        break;
    case RE_OP_STRING_IGN:
        found_pos = string_search_ign(safe_state, pattern->req_string,
          state->text_pos, state->slice_end);
        if (found_pos < 0)
            /* The required string wasn't found. */
            return -1;

        /* Record where the required string matched. */
        state->req_pos = found_pos;
        state->req_end = found_pos + pattern->req_string->value_count;

        if (pattern->req_offset >= 0) {
            /* Step back from the required string to where we should start
             * matching.
             */
            found_pos -= pattern->req_offset;
            if (found_pos >= state->text_pos)
                return found_pos;
        }
        break;
    case RE_OP_STRING_IGN_REV:
        found_pos = string_search_ign_rev(safe_state, pattern->req_string,
          state->text_pos, state->slice_start);
        if (found_pos < 0)
            /* The required string wasn't found. */
            return -1;

        /* Record where the required string matched. */
        state->req_pos = found_pos;
        state->req_end = found_pos - pattern->req_string->value_count;

        if (pattern->req_offset >= 0) {
            /* Step back from the required string to where we should start
             * matching.
             */
            found_pos += pattern->req_offset;
            if (found_pos <= state->text_pos)
                return found_pos;
        }
        break;
    case RE_OP_STRING_REV:
        found_pos = string_search_rev(safe_state, pattern->req_string,
          state->text_pos, state->slice_start);
        if (found_pos < 0)
            /* The required string wasn't found. */
            return -1;

        /* Record where the required string matched. */
        state->req_pos = found_pos;
        state->req_end = found_pos - pattern->req_string->value_count;

        if (pattern->req_offset >= 0) {
            /* Step back from the required string to where we should start
             * matching.
             */
            found_pos += pattern->req_offset;
            if (found_pos <= state->text_pos)
                return found_pos;
        }
        break;
    }

    /* Start matching from the current position. */
    return state->text_pos;
}

/* Performs a depth-first match or search from the context. */
Py_LOCAL_INLINE(int) basic_match(RE_SafeState* safe_state, RE_Node* start_node,
  BOOL search, BOOL recursive_call) {
    RE_State* state;
    Py_ssize_t slice_start;
    Py_ssize_t slice_end;
    Py_ssize_t text_pos;
    RE_EncodingTable* encoding;
    PatternObject* pattern;
    Py_ssize_t text_length;
    RE_NextNode start_pair;
    void* text;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    BOOL (*has_property)(RE_CODE property, Py_UCS4 ch);
    Py_ssize_t pattern_step; /* The overall step of the pattern (forwards or backwards). */
    Py_ssize_t string_pos;
    BOOL do_search_start;
    Py_ssize_t found_pos;
    int folded_pos;
    int gfolded_pos;
    RE_Node* node;
    TRACE(("<<basic_match>>\n"))

    state = safe_state->re_state;

    slice_start = state->slice_start;
    slice_end = state->slice_end;
    text_pos = state->text_pos;

    encoding = state->encoding;

    pattern = state->pattern;

    text_length = state->text_length;

    /* Look beyond any initial group node. */
    start_pair.node = start_node;
    if (recursive_call)
        start_pair.test = locate_test_start(start_node);
    else
        start_pair.test = pattern->start_test;

    /* Is the pattern anchored to the start or end of the string? */
    switch (start_pair.test->op) {
    case RE_OP_END_OF_STRING:
        if (state->reverse) {
            /* Searching backwards. */
            if (text_pos != text_length)
                return RE_ERROR_FAILURE;

            /* Don't bother to search further because it's anchored. */
            search = FALSE;
        }
        break;
    case RE_OP_START_OF_STRING:
        if (!state->reverse) {
            /* Searching forwards. */
            if (text_pos != 0)
                return RE_ERROR_FAILURE;

            /* Don't bother to search further because it's anchored. */
            search = FALSE;
        }
        break;
    }

    text = state->text;
    char_at = state->char_at;
    has_property = encoding->has_property;
    pattern_step = state->reverse ? -1 : 1;
    string_pos = -1;
    do_search_start = pattern->do_search_start;

    /* Add a backtrack entry for failure. */
    if (!add_backtrack(safe_state, RE_OP_FAILURE))
        return RE_ERROR_BACKTRACKING;

start_match:
    /* If we're searching, advance along the string until there could be a
     * match.
     */
    if (pattern->pattern_call_ref >= 0) {
        RE_GuardList* guard_list;

        guard_list = &state->group_call_guard_list[pattern->pattern_call_ref];
        guard_list->count = 0;
        guard_list->last_text_pos = -1;
    }

    /* Locate the required string, if there's one, unless this is a recursive
     * call of 'basic_match'.
     */
    if (!pattern->req_string || recursive_call)
        found_pos = state->text_pos;
    else {
        found_pos = locate_required_string(safe_state);
        if (found_pos < 0)
            return RE_ERROR_FAILURE;
    }

    if (search) {
        state->text_pos = found_pos;

        if (do_search_start) {
            RE_Position new_position;

next_match_1:
            /* 'search_start' will clear 'do_search_start' if it can't perform
             * a fast search for the next possible match. This enables us to
             * avoid the overhead of the call subsequently.
             */
            if (!search_start(safe_state, &start_pair, &new_position, 0))
                return RE_ERROR_FAILURE;

            node = new_position.node;
            text_pos = new_position.text_pos;

            if (node->op == RE_OP_SUCCESS) {
                /* Must the match advance past its start? */
                if (text_pos != state->search_anchor || !state->must_advance) {
                    state->text_pos = text_pos;
                    return RE_ERROR_SUCCESS;
                }

                state->text_pos = state->match_pos + pattern_step;
                goto next_match_1;
            }

            /* 'do_search_start' may have been cleared. */
            do_search_start = pattern->do_search_start;
        } else {
            /* Avoiding 'search_start', which we've found can't perform a fast
             * search for the next possible match.
             */
            node = start_node;
            text_pos = state->text_pos;

next_match_2:
            if (state->reverse) {
                if (text_pos < slice_start)
                    return RE_ERROR_FAILURE;
            } else {
                if (text_pos > slice_end)
                    return RE_ERROR_FAILURE;
            }

            state->match_pos = text_pos;

            if (node->op == RE_OP_SUCCESS) {
                /* Must the match advance past its start? */
                if (text_pos != state->search_anchor || !state->must_advance) {
                    BOOL success;

                    if (state->match_all && !recursive_call) {
                        /* We want to match all of the slice. */
                        if (state->reverse)
                            success = text_pos == slice_start;
                        else
                            success = text_pos == slice_end;
                    } else
                        success = TRUE;

                    if (success) {
                        state->text_pos = text_pos;
                        return RE_ERROR_SUCCESS;
                    }
                }

                text_pos = state->match_pos + pattern_step;
                goto next_match_2;
            }
        }
    } else {
        /* The start position is anchored to the current position. */
        if (found_pos != state->text_pos)
            return RE_ERROR_FAILURE;

        node = start_node;
    }

advance:
    /* The main matching loop. */
    for (;;) {
        TRACE(("%d|", text_pos))

        /* Should we abort the matching? */
        ++state->iterations;

        if (state->iterations == 0 && safe_check_signals(safe_state))
            return RE_ERROR_INTERRUPTED;

        switch (node->op) {
        case RE_OP_ANY: /* Any character, except a newline. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos < slice_end && char_at(text, text_pos) != '\n') {
                ++text_pos;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_ANY_ALL: /* Any character at all. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos < slice_end) {
                ++text_pos;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_ANY_ALL_REV: /* Any character at all backwards. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos > slice_start) {
                --text_pos;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_ANY_REV: /* Any character backwards, except a newline. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos > slice_start && char_at(text, text_pos - 1) != '\n')
              {
                --text_pos;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_ANY_U: /* Any character, except a line separator. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos < slice_end &&
              !state->encoding->is_line_sep(char_at(text, text_pos))) {
                ++text_pos;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_ANY_U_REV: /* Any character backwards, except a line separator. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos > slice_start &&
              !state->encoding->is_line_sep(char_at(text, text_pos - 1))) {
                --text_pos;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_ATOMIC: /* Atomic subpattern. */
        {
            RE_Info info;
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            if (!add_backtrack(safe_state, RE_OP_ATOMIC))
                return RE_ERROR_BACKTRACKING;
            state->backtrack->atomic.too_few_errors = state->too_few_errors;
            state->backtrack->atomic.capture_change = state->capture_change;

            /* Save the groups. */
            if (!push_groups(safe_state))
                return RE_ERROR_MEMORY;

            save_info(state, &info);

            state->text_pos = text_pos;
            state->must_advance = FALSE;

            status = basic_match(safe_state, node->nonstring.next_2.node,
              FALSE, TRUE);
            if (status < 0)
                return status;

            reset_guards(state, node->values);

            restore_info(state, &info);

            if (status != RE_ERROR_SUCCESS)
                goto backtrack;

            node = node->next_1.node;
            text_pos = state->text_pos;
            break;
        }
        case RE_OP_BOUNDARY: /* At a word boundary. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_boundary(state, text_pos) == node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_BRANCH: /* 2-way branch. */
        {
            RE_Position next_position;
            TRACE(("%s\n", re_op_text[node->op]))

            if (try_match(state, &node->next_1, text_pos, &next_position)) {
                if (!add_backtrack(safe_state, RE_OP_BRANCH))
                    return RE_ERROR_BACKTRACKING;
                state->backtrack->branch.position.node =
                  node->nonstring.next_2.node;
                state->backtrack->branch.position.text_pos = text_pos;

                node = next_position.node;
                text_pos = next_position.text_pos;
            } else
                node = node->nonstring.next_2.node;
            break;
        }
        case RE_OP_CALL_REF: /* A group call reference. */
        {
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            if (!push_group_return(safe_state, NULL))
                return RE_ERROR_MEMORY;

            if (!add_backtrack(safe_state, RE_OP_CALL_REF))
                return RE_ERROR_BACKTRACKING;

            node = node->next_1.node;
            break;
        }
        case RE_OP_CHARACTER: /* A character literal. */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos < slice_end && (char_at(text, text_pos) ==
              node->values[0]) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_CHARACTER_IGN: /* A character literal, ignoring case. */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos < slice_end && same_char_ign(encoding, char_at(text,
              text_pos), node->values[0]) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_CHARACTER_IGN_REV: /* A character literal backwards, ignoring case. */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos > slice_start && same_char_ign(encoding, char_at(text,
              text_pos - 1), node->values[0]) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_CHARACTER_REV: /* A character literal backwards. */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos > slice_start && (char_at(text, text_pos - 1) ==
              node->values[0]) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_DEFAULT_BOUNDARY: /* At a default word boundary. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_default_boundary(state, text_pos) == node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_DEFAULT_END_OF_WORD: /* At a default end of a word. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_default_word_end(state, text_pos) == node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_DEFAULT_START_OF_WORD: /* At a default start of a word. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_default_word_start(state, text_pos) ==
              node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_END_FUZZY: /* End of fuzzy matching. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (!fuzzy_insert(safe_state, text_pos, node))
                return RE_ERROR_BACKTRACKING;

            /* If there were too few errors, in the fuzzy section, try again.
             */
            if (state->too_few_errors) {
                state->too_few_errors = FALSE;
                goto backtrack;
            }

            node = node->next_1.node;
            break;
        case RE_OP_END_GREEDY_REPEAT: /* End of a greedy repeat. */
        {
            RE_CODE index;
            RE_RepeatData* rp_data;
            BOOL changed;
            BOOL try_body;
            RE_Position next_body_position;
            BOOL try_tail;
            RE_Position next_tail_position;
            RE_BacktrackData* bt_data;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Repeat indexes are 0-based. */
            index = node->values[0];
            rp_data = &state->repeats[index];

            /* The body has matched successfully at this position. */
            if (!guard_repeat(safe_state, index, rp_data->start,
              RE_STATUS_BODY, FALSE))
                return RE_ERROR_MEMORY;

            ++rp_data->count;

            /* Have we advanced through the text or has a capture group change?
             */
            changed = rp_data->capture_change != state->capture_change ||
              text_pos != rp_data->start;

            /* The counts are of type size_t, so the format needs to specify
             * that.
             */
            TRACE(("min is %" PY_FORMAT_SIZE_T "u, max is %" PY_FORMAT_SIZE_T
              "u, count is %" PY_FORMAT_SIZE_T "u\n", node->values[1],
              node->values[2], rp_data->count))

            /* Could the body or tail match? */
            try_body = changed && (rp_data->count < node->values[2] ||
              ~node->values[2] == 0) && !is_repeat_guarded(safe_state, index,
              text_pos, RE_STATUS_BODY) && try_match(state, &node->next_1,
              text_pos, &next_body_position);
            try_tail = (!changed || rp_data->count >= node->values[1]) &&
              !is_repeat_guarded(safe_state, index, text_pos, RE_STATUS_TAIL)
              && try_match(state, &node->nonstring.next_2, text_pos,
              &next_tail_position);
            if (!try_body && !try_tail) {
                /* Neither the body nor the tail could match. */
                --rp_data->count;
                goto backtrack;
            }

            /* Record info in case we backtrack into the body. */
            if (!add_backtrack(safe_state, RE_OP_BODY_END))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->repeat.index = index;
            bt_data->repeat.count = rp_data->count - 1;
            bt_data->repeat.start = rp_data->start;
            bt_data->repeat.capture_change = rp_data->capture_change;

            if (try_body) {
                if (try_tail) {
                    /* Both the body and the tail could match, but the body
                     * takes precedence. If the body fails to match then we
                     * want to try the tail before backtracking further.
                     */

                    /* Record backtracking info for matching the tail. */
                    if (!add_backtrack(safe_state, RE_OP_MATCH_TAIL))
                        return RE_ERROR_BACKTRACKING;
                    bt_data = state->backtrack;
                    bt_data->repeat.position = next_tail_position;
                    bt_data->repeat.index = index;
                    bt_data->repeat.count = rp_data->count;
                    bt_data->repeat.start = rp_data->start;
                    bt_data->repeat.capture_change = rp_data->capture_change;
                    bt_data->repeat.text_pos = text_pos;
                }

                /* Record backtracking info in case the body fails to match. */
                if (!add_backtrack(safe_state, RE_OP_BODY_START))
                    return RE_ERROR_BACKTRACKING;
                bt_data = state->backtrack;
                bt_data->repeat.index = index;
                bt_data->repeat.text_pos = text_pos;

                rp_data->capture_change = state->capture_change;
                rp_data->start = text_pos;

                /* Advance into the body. */
                node = next_body_position.node;
                text_pos = next_body_position.text_pos;
            } else {
                /* Only the tail could match. */

                /* Advance into the tail. */
                node = next_tail_position.node;
                text_pos = next_tail_position.text_pos;
            }
            break;
        }
        case RE_OP_END_GROUP: /* End of a capture group. */
        {
            RE_CODE private_index;
            RE_CODE public_index;
            RE_GroupData* group;
            RE_BacktrackData* bt_data;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[1]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             */
            private_index = node->values[0];
            public_index = node->values[1];
            group = &state->groups[private_index - 1];

            if (!add_backtrack(safe_state, RE_OP_END_GROUP))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->group.private_index = private_index;
            bt_data->group.public_index = public_index;
            bt_data->group.text_pos = group->span.end;
            bt_data->group.capture = (BOOL)node->values[2];
            bt_data->group.current_capture = group->current_capture;

            if (pattern->group_info[private_index - 1].referenced &&
              group->span.end != text_pos)
                ++state->capture_change;
            group->span.end = text_pos;

            /* Save the capture? */
            if (node->values[2]) {
                group->current_capture = group->capture_count;
                if (!save_capture(safe_state, private_index, public_index))
                    return RE_ERROR_MEMORY;
            }

            node = node->next_1.node;
            break;
        }
        case RE_OP_END_LAZY_REPEAT: /* End of a lazy repeat. */
        {
            RE_CODE index;
            RE_RepeatData* rp_data;
            BOOL changed;
            BOOL try_body;
            RE_Position next_body_position;
            BOOL try_tail;
            RE_Position next_tail_position;
            RE_BacktrackData* bt_data;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Repeat indexes are 0-based. */
            index = node->values[0];
            rp_data = &state->repeats[index];

            /* The body has matched successfully at this position. */
            if (!guard_repeat(safe_state, index, rp_data->start,
              RE_STATUS_BODY, FALSE))
                return RE_ERROR_MEMORY;

            ++rp_data->count;

            /* Have we advanced through the text or has a capture group change?
             */
            changed = rp_data->capture_change != state->capture_change ||
              text_pos != rp_data->start;

            /* The counts are of type size_t, so the format needs to specify
             * that.
             */
            TRACE(("min is %" PY_FORMAT_SIZE_T "u, max is %" PY_FORMAT_SIZE_T
              "u, count is %" PY_FORMAT_SIZE_T "u\n", node->values[1],
              node->values[2], rp_data->count))

            /* Could the body or tail match? */
            try_body = changed && (rp_data->count < node->values[2] ||
              ~node->values[2] == 0) && !is_repeat_guarded(safe_state, index,
              text_pos, RE_STATUS_BODY) && try_match(state, &node->next_1,
              text_pos, &next_body_position);
            try_tail = (!changed || rp_data->count >= node->values[1]) &&
              try_match(state, &node->nonstring.next_2, text_pos,
              &next_tail_position);
            if (!try_body && !try_tail) {
                /* Neither the body nor the tail could match. */
                --rp_data->count;
                goto backtrack;
            }

            /* Record info in case we backtrack into the body. */
            if (!add_backtrack(safe_state, RE_OP_BODY_END))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->repeat.index = index;
            bt_data->repeat.count = rp_data->count - 1;
            bt_data->repeat.start = rp_data->start;
            bt_data->repeat.capture_change = rp_data->capture_change;

            if (try_body) {
                if (try_tail) {
                    /* Both the body and the tail could match, but the tail
                     * takes precedence. If the tail fails to match then we
                     * want to try the body before backtracking further.
                     */

                    /* Record backtracking info for matching the body. */
                    if (!add_backtrack(safe_state, RE_OP_MATCH_BODY))
                        return RE_ERROR_BACKTRACKING;
                    bt_data = state->backtrack;
                    bt_data->repeat.position = next_body_position;
                    bt_data->repeat.index = index;
                    bt_data->repeat.count = rp_data->count;
                    bt_data->repeat.start = rp_data->start;
                    bt_data->repeat.capture_change = rp_data->capture_change;
                    bt_data->repeat.text_pos = text_pos;

                    /* Advance into the tail. */
                    node = next_tail_position.node;
                    text_pos = next_tail_position.text_pos;
                } else {
                    /* Only the body could match. */

                    /* Record backtracking info in case the body fails to
                     * match.
                     */
                    if (!add_backtrack(safe_state, RE_OP_BODY_START))
                        return RE_ERROR_BACKTRACKING;
                    bt_data = state->backtrack;
                    bt_data->repeat.index = index;
                    bt_data->repeat.text_pos = text_pos;

                    rp_data->capture_change = state->capture_change;
                    rp_data->start = text_pos;

                    /* Advance into the body. */
                    node = next_body_position.node;
                    text_pos = next_body_position.text_pos;
                }
            } else {
                /* Only the tail could match. */

                /* Advance into the tail. */
                node = next_tail_position.node;
                text_pos = next_tail_position.text_pos;
            }
            break;
        }
        case RE_OP_END_OF_LINE: /* At the end of a line. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == text_length || char_at(text, text_pos) == '\n')
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_END_OF_LINE_U: /* At the end of a line. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (encoding->at_line_end(state, text_pos))
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_END_OF_STRING: /* At the end of the string. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == text_length)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_END_OF_STRING_LINE: /* At end of string or final newline. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == text_length || text_pos == state->final_newline)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_END_OF_STRING_LINE_U: /* At end of string or final newline. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == text_length || text_pos == state->final_line_sep)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_END_OF_WORD: /* At end of a word. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_word_end(state, text_pos) == node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_FUZZY: /* Fuzzy matching. */
        {
            RE_FuzzyInfo* fuzzy_info;
            RE_BacktrackData* bt_data;
            TRACE(("%s\n", re_op_text[node->op]))

            fuzzy_info = &state->fuzzy_info;

            /* Save the current fuzzy info. */
            if (!add_backtrack(safe_state, RE_OP_FUZZY))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            memmove(&bt_data->fuzzy.fuzzy_info, fuzzy_info,
              sizeof(RE_FuzzyInfo));
            bt_data->fuzzy.index = node->values[0];
            bt_data->fuzzy.text_pos = text_pos;

            /* Initialise the new fuzzy info. */
            memset(fuzzy_info->counts, 0, 4 * sizeof(fuzzy_info->counts[0]));
            fuzzy_info->total_cost = 0;
            fuzzy_info->node = node;

            node = node->next_1.node;
            break;
        }
        case RE_OP_GRAPHEME_BOUNDARY: /* At a grapheme boundary. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_grapheme_boundary(state, text_pos) == node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_GREEDY_REPEAT: /* Greedy repeat. */
        {
            RE_CODE index;
            RE_RepeatData* rp_data;
            RE_BacktrackData* bt_data;
            BOOL try_body;
            RE_Position next_body_position;
            BOOL try_tail;
            RE_Position next_tail_position;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Repeat indexes are 0-based. */
            index = node->values[0];
            rp_data = &state->repeats[index];

            /* We might need to backtrack into the head, so save the current
             * repeat.
             */
            if (!add_backtrack(safe_state, RE_OP_GREEDY_REPEAT))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->repeat.index = index;
            bt_data->repeat.count = rp_data->count;
            bt_data->repeat.start = rp_data->start;
            bt_data->repeat.capture_change = rp_data->capture_change;
            bt_data->repeat.text_pos = text_pos;

            /* Initialise the new repeat. */
            rp_data->count = 0;
            rp_data->start = text_pos;
            rp_data->capture_change = state->capture_change;

            /* Could the body or tail match? */
            try_body = node->values[2] > 0 && !is_repeat_guarded(safe_state,
              index, text_pos, RE_STATUS_BODY) && try_match(state,
              &node->next_1, text_pos, &next_body_position);
            try_tail = node->values[1] == 0 && try_match(state,
              &node->nonstring.next_2, text_pos, &next_tail_position);
            if (!try_body && !try_tail)
                /* Neither the body nor the tail could match. */
                goto backtrack;

            if (try_body) {
                if (try_tail) {
                    /* Both the body and the tail could match, but the body
                     * takes precedence. If the body fails to match then we
                     * want to try the tail before backtracking further.
                     */

                    /* Record backtracking info for matching the tail. */
                    if (!add_backtrack(safe_state, RE_OP_MATCH_TAIL))
                        return RE_ERROR_BACKTRACKING;
                    bt_data = state->backtrack;
                    bt_data->repeat.position = next_tail_position;
                    bt_data->repeat.index = index;
                    bt_data->repeat.count = rp_data->count;
                    bt_data->repeat.start = rp_data->start;
                    bt_data->repeat.capture_change = rp_data->capture_change;
                    bt_data->repeat.text_pos = text_pos;
                }

                /* Advance into the body. */
                node = next_body_position.node;
                text_pos = next_body_position.text_pos;
            } else {
                /* Only the tail could match. */

                /* Advance into the tail. */
                node = next_tail_position.node;
                text_pos = next_tail_position.text_pos;
            }
            break;
        }
        case RE_OP_GREEDY_REPEAT_ONE: /* Greedy repeat for one character. */
        {
            RE_CODE index;
            RE_RepeatData* rp_data;
            size_t count;
            BOOL match;
            RE_BacktrackData* bt_data;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Repeat indexes are 0-based. */
            index = node->values[0];
            rp_data = &state->repeats[index];

            if (is_repeat_guarded(safe_state, index, text_pos, RE_STATUS_BODY))
                goto backtrack;

            /* Count how many times the character repeats, up to the maximum.
             */
            count = count_one(state, node->nonstring.next_2.node, text_pos,
              (size_t)node->values[2]);

            /* Unmatch until it's not guarded. */
            match = FALSE;
            for (;;) {
                if (count < node->values[1])
                    /* The number of repeats is below the minimum. */
                    break;

                if (!is_repeat_guarded(safe_state, index, text_pos +
                  (Py_ssize_t)count * node->step, RE_STATUS_TAIL)) {
                    /* It's not guarded at this position. */
                    match = TRUE;
                    break;
                }

                if (count == 0)
                    break;

                --count;
            }

            if (!match) {
                /* The repeat has failed to match at this position. */
                if (!guard_repeat(safe_state, index, text_pos, RE_STATUS_BODY,
                  TRUE))
                    return RE_ERROR_MEMORY;
                goto backtrack;
            }

            /* Record the backtracking info. */
            if (!add_backtrack(safe_state, RE_OP_GREEDY_REPEAT_ONE))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->repeat.position.node = node;
            bt_data->repeat.index = index;
            bt_data->repeat.text_pos = rp_data->start;
            bt_data->repeat.count = rp_data->count;

            rp_data->start = text_pos;
            rp_data->count = count;

            /* Advance into the tail. */
            text_pos += (Py_ssize_t)count * node->step;
            node = node->next_1.node;
            break;
        }
        case RE_OP_GROUP_CALL: /* Group call. */
        {
            RE_CODE index;
            size_t g;
            size_t r;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            index = node->values[0];

            /* Save the capture groups and repeat guards. */
            if (!push_group_return(safe_state, node->next_1.node))
                return RE_ERROR_MEMORY;

            /* Clear the capture groups for the group call. They'll be restored
             * on return.
             */
            for (g = 0; g < state->pattern->true_group_count; g++) {
                RE_GroupData* group;

                group = &state->groups[g];
                group->span.start = -1;
                group->span.end = -1;
                group->current_capture = -1;
            }

            /* Clear the repeat guards for the group call. They'll be restored
             * on return.
             */
            for (r = 0; r < state->pattern->repeat_count; r++) {
                RE_RepeatData* repeat;

                repeat = &state->repeats[r];
                repeat->body_guard_list.count = 0;
                repeat->body_guard_list.last_text_pos = -1;
                repeat->tail_guard_list.count = 0;
                repeat->tail_guard_list.last_text_pos = -1;
            }

            /* Call a group, skipping its CALL_REF node. */
            node = pattern->call_ref_info[index].node->next_1.node;

            if (!add_backtrack(safe_state, RE_OP_GROUP_CALL))
                return RE_ERROR_BACKTRACKING;
            break;
        }
        case RE_OP_GROUP_EXISTS: /* Capture group exists. */
        {
            RE_GroupData* group;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture >= 0)
                node = node->next_1.node;
            else
                node = node->nonstring.next_2.node;
            break;
        }
        case RE_OP_GROUP_RETURN: /* Group return. */
        {
            RE_Node* return_node;
            RE_BacktrackData* bt_data;
            TRACE(("%s\n", re_op_text[node->op]))

            return_node = top_group_return(state);

            if (!add_backtrack(safe_state, RE_OP_GROUP_RETURN))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->group_call.node = return_node;
            bt_data->group_call.capture_change = state->capture_change;

            if (return_node) {
                /* The group was called. */
                node = return_node;

                /* Save the groups. */
                if (!push_groups(safe_state))
                    return RE_ERROR_MEMORY;

                /* Save the repeats. */
                if (!push_repeats(safe_state))
                    return RE_ERROR_MEMORY;
            } else
                /* The group was not called. */
                node = node->next_1.node;

            pop_group_return(state);
            break;
        }
        case RE_OP_LAZY_REPEAT: /* Lazy repeat. */
        {
            RE_CODE index;
            RE_RepeatData* rp_data;
            RE_BacktrackData* bt_data;
            BOOL try_body;
            RE_Position next_body_position;
            BOOL try_tail;
            RE_Position next_tail_position;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Repeat indexes are 0-based. */
            index = node->values[0];
            rp_data = &state->repeats[index];

            /* We might need to backtrack into the head, so save the current
             * repeat.
             */
            if (!add_backtrack(safe_state, RE_OP_LAZY_REPEAT))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->repeat.index = index;
            bt_data->repeat.count = rp_data->count;
            bt_data->repeat.start = rp_data->start;
            bt_data->repeat.capture_change = rp_data->capture_change;
            bt_data->repeat.text_pos = text_pos;

            /* Initialise the new repeat. */
            rp_data->count = 0;
            rp_data->start = text_pos;
            rp_data->capture_change = state->capture_change;

            /* Could the body or tail match? */
            try_body = node->values[2] > 0 && !is_repeat_guarded(safe_state,
              index, text_pos, RE_STATUS_BODY) && try_match(state,
              &node->next_1, text_pos, &next_body_position);
            try_tail = node->values[1] == 0 && try_match(state,
              &node->nonstring.next_2, text_pos, &next_tail_position);
            if (!try_body && !try_tail)
                /* Neither the body nor the tail could match. */
                goto backtrack;

            if (try_body) {
                if (try_tail) {
                    /* Both the body and the tail could match, but the tail
                     * takes precedence. If the tail fails to match then we
                     * want to try the body before backtracking further.
                     */

                    /* Record backtracking info for matching the tail. */
                    if (!add_backtrack(safe_state, RE_OP_MATCH_BODY))
                        return RE_ERROR_BACKTRACKING;
                    bt_data = state->backtrack;
                    bt_data->repeat.position = next_body_position;
                    bt_data->repeat.index = index;
                    bt_data->repeat.count = rp_data->count;
                    bt_data->repeat.start = rp_data->start;
                    bt_data->repeat.capture_change = rp_data->capture_change;
                    bt_data->repeat.text_pos = text_pos;

                    /* Advance into the tail. */
                    node = next_tail_position.node;
                    text_pos = next_tail_position.text_pos;
                } else {
                    /* Advance into the body. */
                    node = next_body_position.node;
                    text_pos = next_body_position.text_pos;
                }
            } else {
                /* Only the tail could match. */

                /* Advance into the tail. */
                node = next_tail_position.node;
                text_pos = next_tail_position.text_pos;
            }
            break;
        }
        case RE_OP_LAZY_REPEAT_ONE: /* Lazy repeat for one character. */
        {
            RE_CODE index;
            RE_RepeatData* rp_data;
            size_t count;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Repeat indexes are 0-based. */
            index = node->values[0];
            rp_data = &state->repeats[index];

            if (is_repeat_guarded(safe_state, index, text_pos, RE_STATUS_BODY))
                goto backtrack;

            /* Count how many times the character repeats, up to the minimum.
             */
            count = count_one(state, node->nonstring.next_2.node, text_pos,
              (size_t)node->values[1]);

            /* Have we matched at least the minimum? */
            if (count < node->values[1]) {
                /* The repeat has failed to match at this position. */
                if (!guard_repeat(safe_state, index, text_pos, RE_STATUS_BODY,
                  TRUE))
                    return RE_ERROR_MEMORY;
                goto backtrack;
            }

            if (count < node->values[2]) {
                /* The match is shorter than the maximum, so we might need to
                 * backtrack the repeat to consume more.
                 */
                RE_BacktrackData* bt_data;

                /* Get the offset to the repeat values in the context. */
                rp_data = &state->repeats[index];
                if (!add_backtrack(safe_state, RE_OP_LAZY_REPEAT_ONE))
                    return RE_ERROR_BACKTRACKING;
                bt_data = state->backtrack;
                bt_data->repeat.position.node = node;
                bt_data->repeat.index = index;
                bt_data->repeat.text_pos = rp_data->start;
                bt_data->repeat.count = rp_data->count;

                rp_data->start = text_pos;
                rp_data->count = count;
            }

            /* Advance into the tail. */
            text_pos += (Py_ssize_t)count * node->step;
            node = node->next_1.node;
            break;
        }
        case RE_OP_LOOKAROUND: /* Lookaround. */
        {
            RE_Info info;
            size_t capture_change;
            BOOL too_few_errors;
            int status;
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            /* Save the groups. */
            if (!push_groups(safe_state))
                return RE_ERROR_MEMORY;

            capture_change = state->capture_change;

            /* Save the other info. */
            save_info(state, &info);

            state->slice_start = 0;
            state->slice_end = text_length;
            state->text_pos = text_pos;
            state->must_advance = FALSE;

            too_few_errors = state->too_few_errors;

            status = basic_match(safe_state, node->nonstring.next_2.node,
              FALSE, TRUE);
            if (status < 0)
                return status;

            reset_guards(state, node->values + 1);

            state->slice_end = slice_end;
            state->slice_start = slice_start;

            /* Restore the other info. */
            restore_info(state, &info);

            if (node->match) {
                /* It's a positive lookaround. */
                if (status == RE_ERROR_SUCCESS) {
                    /* It succeeded, so the groups and certain flags may have
                     * changed.
                     */
                    if (!add_backtrack(safe_state, RE_OP_LOOKAROUND))
                        return RE_ERROR_BACKTRACKING;

                    /* We'll restore the groups and flags on backtracking. */
                    state->backtrack->lookaround.too_few_errors =
                      too_few_errors;
                    state->backtrack->lookaround.capture_change =
                      capture_change;
                } else {
                    /* It failed, so the groups and certain flags haven't
                     * changed.
                     */
                    drop_groups(state);
                    goto backtrack;
                }
            } else {
                /* It's a negative lookaround. */
                if (status == RE_ERROR_SUCCESS) {
                    /* It succeeded, so the groups and certain flags may have
                     * changed. We need to restore them.
                     */
                    pop_groups(state);
                    state->too_few_errors = too_few_errors;
                    state->capture_change = capture_change;
                    goto backtrack;
                } else
                    /* It failed, so the groups and certain flags haven't
                     * changed.
                     */
                    drop_groups(state);
            }

            node = node->next_1.node;
            break;
        }
        case RE_OP_PROPERTY: /* A property. */
            /* values are: property */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos < slice_end && has_property(node->values[0],
              char_at(text, text_pos)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_PROPERTY_IGN: /* A property, ignoring case. */
            /* values are: property */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos < slice_end && has_property_ign(encoding,
              node->values[0], char_at(text, text_pos)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_PROPERTY_IGN_REV: /* A property backwards, ignoring case. */
            /* values are: property */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos > slice_start && has_property_ign(encoding,
              node->values[0], char_at(text, text_pos - 1)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_PROPERTY_REV: /* A property backwards. */
            /* values are: property */
            TRACE(("%s %d %d\n", re_op_text[node->op], node->match,
              node->values[0]))

            if (text_pos > slice_start && has_property(node->values[0],
              char_at(text, text_pos - 1)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_RANGE: /* A range. */
            /* values are: lower, upper */
            TRACE(("%s %d %d %d\n", re_op_text[node->op], node->match,
              node->values[0], node->values[1]))

            if (text_pos < slice_end && in_range(node->values[0],
              node->values[1], char_at(text, text_pos)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_RANGE_IGN: /* A range, ignoring case. */
            /* values are: lower, upper */
            TRACE(("%s %d %d %d\n", re_op_text[node->op], node->match,
              node->values[0], node->values[1]))

            if (text_pos < slice_end && in_range_ign(encoding, node->values[0],
              node->values[1], char_at(text, text_pos)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_RANGE_IGN_REV: /* A range backwards, ignoring case. */
            /* values are: lower, upper */
            TRACE(("%s %d %d %d\n", re_op_text[node->op], node->match,
              node->values[0], node->values[1]))

            if (text_pos > slice_start && in_range_ign(encoding,
              node->values[0], node->values[1], char_at(text, text_pos - 1)) ==
              node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_RANGE_REV: /* A range backwards. */
            /* values are: lower, upper */
            TRACE(("%s %d %d %d\n", re_op_text[node->op], node->match,
              node->values[0], node->values[1]))

            if (text_pos > slice_start && in_range(node->values[0],
              node->values[1], char_at(text, text_pos - 1)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_REF_GROUP: /* Reference to a capture group. */
        {
            RE_GroupData* group;
            RE_GroupSpan* span;
            Py_ssize_t available;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */

            /* Did the group capture anything? */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture < 0)
                goto backtrack;

            span = &group->captures[group->current_capture];

            /* Are there enough characters? */
            available = state->slice_end - text_pos;
            if (!(node->status & RE_STATUS_FUZZY) && span->end - span->start >
              available)
                goto backtrack;

            if (string_pos < 0)
                string_pos = span->start;

            /* Try comparing. */
            while (string_pos < span->end) {
                if (text_pos < slice_end && char_at(text, text_pos) ==
                  char_at(text, string_pos)) {
                    ++string_pos;
                    ++text_pos;
                } else if (node->status & RE_STATUS_FUZZY) {
                    BOOL matched;

                    if (!fuzzy_match_string(safe_state, search, &text_pos,
                      node, &string_pos, &matched, 1))
                        return RE_ERROR_BACKTRACKING;
                    if (!matched) {
                        string_pos = -1;
                        goto backtrack;
                    }
                } else {
                    string_pos = -1;
                    goto backtrack;
                }
            }

            string_pos = -1;

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_REF_GROUP_FLD: /* Reference to a capture group, ignoring case. */
        {
            RE_GroupData* group;
            RE_GroupSpan* span;
            int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
            int folded_len;
            int gfolded_len;
            Py_UCS4 folded[RE_MAX_FOLDED];
            Py_UCS4 gfolded[RE_MAX_FOLDED];
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */

            /* Did the group capture anything? */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture < 0)
                goto backtrack;

            span = &group->captures[group->current_capture];

            full_case_fold = encoding->full_case_fold;

            if (string_pos < 0) {
                string_pos = span->start;
                folded_pos = 0;
                folded_len = 0;
                gfolded_pos = 0;
                gfolded_len = 0;
            } else {
                folded_len = full_case_fold(char_at(text, text_pos), folded);
                gfolded_len = full_case_fold(char_at(text, string_pos),
                  gfolded);
            }

            /* Try comparing. */
            while (string_pos < span->end) {
                /* Case-fold at current position in text. */
                if (folded_pos >= folded_len) {
                    if (text_pos < slice_end)
                        folded_len = full_case_fold(char_at(text, text_pos),
                          folded);
                    else
                        folded_len = 0;
                    folded_pos = 0;
                }

                /* Case-fold at current position in group. */
                if (gfolded_pos >= gfolded_len) {
                    gfolded_len = full_case_fold(char_at(text, string_pos),
                      gfolded);
                    gfolded_pos = 0;
                }

                if (folded_pos < folded_len && folded[folded_pos] ==
                  gfolded[gfolded_pos]) {
                    ++folded_pos;
                    ++gfolded_pos;
                } else if (node->status & RE_STATUS_FUZZY) {
                    BOOL matched;

                    if (!fuzzy_match_string_fld2(safe_state, search, &text_pos,
                      node, &folded_pos, folded_len, &string_pos, &gfolded_pos,
                      gfolded_len, &matched, 1))
                        return RE_ERROR_BACKTRACKING;
                    if (!matched) {
                        string_pos = -1;
                        goto backtrack;
                    }
                } else {
                    string_pos = -1;
                    goto backtrack;
                }

                if (folded_pos >= folded_len && folded_len > 0)
                    ++text_pos;

                if (gfolded_pos >= gfolded_len)
                    ++string_pos;
            }

            string_pos = -1;

            if (folded_pos < folded_len || gfolded_pos < gfolded_len)
                goto backtrack;

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_REF_GROUP_FLD_REV: /* Reference to a capture group, ignoring case. */
        {
            RE_GroupData* group;
            RE_GroupSpan* span;
            int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
            int folded_len;
            int gfolded_len;
            Py_UCS4 folded[RE_MAX_FOLDED];
            Py_UCS4 gfolded[RE_MAX_FOLDED];
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */

            /* Did the group capture anything? */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture < 0)
                goto backtrack;

            span = &group->captures[group->current_capture];

            full_case_fold = encoding->full_case_fold;

            if (string_pos < 0) {
                string_pos = span->end;
                folded_pos = 0;
                folded_len = 0;
                gfolded_pos = 0;
                gfolded_len = 0;
            } else {
                folded_len = full_case_fold(char_at(text, text_pos - 1),
                  folded);
                gfolded_len = full_case_fold(char_at(text, string_pos - 1),
                  gfolded);
            }

            /* Try comparing. */
            while (string_pos > span->start) {
                /* Case-fold at current position in text. */
                if (folded_pos <= 0) {
                    if (text_pos > slice_start)
                        folded_len = full_case_fold(char_at(text, text_pos -
                          1), folded);
                    else
                        folded_len = 0;
                    folded_pos = folded_len;
                }

                /* Case-fold at current position in group. */
                if (gfolded_pos <= 0) {
                    gfolded_len = full_case_fold(char_at(text, string_pos - 1),
                      gfolded);
                    gfolded_pos = gfolded_len;
                }

                if (folded_pos > 0 && folded[folded_pos - 1] ==
                  gfolded[gfolded_pos - 1]) {
                    --folded_pos;
                    --gfolded_pos;
                } else if (node->status & RE_STATUS_FUZZY) {
                    BOOL matched;

                    if (!fuzzy_match_string_fld2(safe_state, search, &text_pos,
                      node, &folded_pos, folded_len, &string_pos, &gfolded_pos,
                      gfolded_len, &matched, -1))
                        return RE_ERROR_BACKTRACKING;
                    if (!matched) {
                        string_pos = -1;
                        goto backtrack;
                    }
                } else {
                    string_pos = -1;
                    goto backtrack;
                }

                if (folded_pos <= 0 && folded_len > 0)
                    --text_pos;

                if (gfolded_pos <= 0)
                    --string_pos;
            }

            string_pos = -1;

            if (folded_pos > 0 || gfolded_pos > 0)
                goto backtrack;

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_REF_GROUP_IGN: /* Reference to a capture group, ignoring case. */
        {
            RE_GroupData* group;
            RE_GroupSpan* span;
            Py_ssize_t available;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */

            /* Did the group capture anything? */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture < 0)
                goto backtrack;

            span = &group->captures[group->current_capture];

            /* Are there enough characters? */
            available = state->slice_end - text_pos;
            if (!(node->status & RE_STATUS_FUZZY) && span->end - span->start >
              available)
                goto backtrack;

            if (string_pos < 0)
                string_pos = span->start;

            /* Try comparing. */
            while (string_pos < span->end) {
                if (text_pos < slice_end && same_char_ign(encoding,
                  char_at(text, text_pos), char_at(text, string_pos))) {
                    ++string_pos;
                    ++text_pos;
                } else if (node->status & RE_STATUS_FUZZY) {
                    BOOL matched;

                    if (!fuzzy_match_string(safe_state, search, &text_pos,
                      node, &string_pos, &matched, 1))
                        return RE_ERROR_BACKTRACKING;
                    if (!matched) {
                        string_pos = -1;
                        goto backtrack;
                    }
                } else {
                    string_pos = -1;
                    goto backtrack;
                }
            }

            string_pos = -1;

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_REF_GROUP_IGN_REV: /* Reference to a capture group, ignoring case. */
        {
            RE_GroupData* group;
            RE_GroupSpan* span;
            Py_ssize_t available;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */

            /* Did the group capture anything? */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture < 0)
                goto backtrack;

            span = &group->captures[group->current_capture];

            /* Are there enough characters? */
            available = text_pos - state->slice_start;
            if (!(node->status & RE_STATUS_FUZZY) && span->end - span->start >
              available)
                goto backtrack;

            if (string_pos < 0)
                string_pos = span->end;

            /* Try comparing. */
            while (string_pos > span->start) {
                if (text_pos > slice_start && same_char_ign(encoding,
                  char_at(text, text_pos - 1), char_at(text, string_pos - 1)))
                  {
                    --string_pos;
                    --text_pos;
                } else if (node->status & RE_STATUS_FUZZY) {
                    BOOL matched;

                    if (!fuzzy_match_string(safe_state, search, &text_pos,
                      node, &string_pos, &matched, -1))
                        return RE_ERROR_BACKTRACKING;
                    if (!matched) {
                        string_pos = -1;
                        goto backtrack;
                    }
                } else {
                    string_pos = -1;
                    goto backtrack;
                }
            }

            string_pos = -1;

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_REF_GROUP_REV: /* Reference to a capture group. */
        {
            RE_GroupData* group;
            RE_GroupSpan* span;
            Py_ssize_t available;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             *
             * Check whether the captured text, if any, exists at this position
             * in the string.
             */

            /* Did the group capture anything? */
            group = &state->groups[node->values[0] - 1];
            if (group->current_capture < 0)
                goto backtrack;

            span = &group->captures[group->current_capture];

            /* Are there enough characters? */
            available = text_pos - state->slice_start;
            if (!(node->status & RE_STATUS_FUZZY) && span->end - span->start >
              available)
                goto backtrack;

            if (string_pos < 0)
                string_pos = span->end;

            /* Try comparing. */
            while (string_pos > span->start) {
                if (text_pos > slice_start && char_at(text, text_pos - 1) ==
                  char_at(text, string_pos - 1)) {
                    --string_pos;
                    --text_pos;
                } else if (node->status & RE_STATUS_FUZZY) {
                    BOOL matched;

                    if (!fuzzy_match_string(safe_state, search, &text_pos,
                      node, &string_pos, &matched, -1))
                        return RE_ERROR_BACKTRACKING;
                    if (!matched) {
                        string_pos = -1;
                        goto backtrack;
                    }
                } else {
                    string_pos = -1;
                    goto backtrack;
                }
            }

            string_pos = -1;

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_SEARCH_ANCHOR: /* At the start of the search. */
            TRACE(("%s %d\n", re_op_text[node->op], node->values[0]))

            if (text_pos == state->search_anchor)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_SET_DIFF: /* Character set. */
        case RE_OP_SET_INTER:
        case RE_OP_SET_SYM_DIFF:
        case RE_OP_SET_UNION:
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (text_pos < slice_end && in_set(encoding, node, char_at(text,
              text_pos)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_SET_DIFF_IGN: /* Character set, ignoring case. */
        case RE_OP_SET_INTER_IGN:
        case RE_OP_SET_SYM_DIFF_IGN:
        case RE_OP_SET_UNION_IGN:
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (text_pos < slice_end && in_set_ign(encoding, node,
              char_at(text, text_pos)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, 1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_SET_DIFF_IGN_REV: /* Character set, ignoring case. */
        case RE_OP_SET_INTER_IGN_REV:
        case RE_OP_SET_SYM_DIFF_IGN_REV:
        case RE_OP_SET_UNION_IGN_REV:
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (text_pos > slice_start && in_set_ign(encoding, node,
              char_at(text, text_pos - 1)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_SET_DIFF_REV: /* Character set. */
        case RE_OP_SET_INTER_REV:
        case RE_OP_SET_SYM_DIFF_REV:
        case RE_OP_SET_UNION_REV:
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (text_pos > slice_start && in_set(encoding, node, char_at(text,
              text_pos - 1)) == node->match) {
                text_pos += node->step;
                node = node->next_1.node;
            } else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_one(safe_state, search, &text_pos, &node, -1))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_START_GROUP: /* Start of a capture group. */
        {
            RE_CODE private_index;
            RE_CODE public_index;
            RE_GroupData* group;
            RE_BacktrackData* bt_data;
            TRACE(("%s %d\n", re_op_text[node->op], node->values[1]))

            /* Capture group indexes are 1-based (excluding group 0, which is
             * the entire matched string).
             */
            private_index = node->values[0];
            public_index = node->values[1];
            group = &state->groups[private_index - 1];

            if (!add_backtrack(safe_state, RE_OP_START_GROUP))
                return RE_ERROR_BACKTRACKING;
            bt_data = state->backtrack;
            bt_data->group.private_index = private_index;
            bt_data->group.public_index = public_index;
            bt_data->group.text_pos = group->span.start;
            bt_data->group.capture = (BOOL)node->values[2];
            bt_data->group.current_capture = group->current_capture;

            if (pattern->group_info[private_index - 1].referenced &&
              group->span.start != text_pos)
                ++state->capture_change;
            group->span.start = text_pos;

            /* Save the capture? */
            if (node->values[2]) {
                group->current_capture = group->capture_count;
                if (!save_capture(safe_state, private_index, public_index))
                    return RE_ERROR_MEMORY;
            }

            node = node->next_1.node;
            break;
        }
        case RE_OP_START_OF_LINE: /* At the start of a line. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == 0 || char_at(text, text_pos - 1) == '\n')
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_START_OF_LINE_U: /* At the start of a line. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (encoding->at_line_start(state, text_pos))
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_START_OF_STRING: /* At the start of the string. */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == 0)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_START_OF_WORD: /* At start of a word. */
            TRACE(("%s %d\n", re_op_text[node->op], node->match))

            if (encoding->at_word_start(state, text_pos) == node->match)
                node = node->next_1.node;
            else if (node->status & RE_STATUS_FUZZY) {
                if (!fuzzy_match_zero(safe_state, search, &text_pos, &node))
                    return RE_ERROR_BACKTRACKING;
                if (!node)
                    goto backtrack;
            } else
                goto backtrack;
            break;
        case RE_OP_STRING: /* A string literal. */
        {
            Py_ssize_t length;
            Py_ssize_t available;
            RE_CODE* values;
            TRACE(("%s %d\n", re_op_text[node->op], node->value_count))

            if ((node->status & RE_STATUS_REQUIRED) && text_pos ==
              state->req_pos && string_pos < 0)
                text_pos = state->req_end;
            else {
                /* Are there enough characters to match? */
                length = node->value_count;
                available = slice_end - text_pos;
                if (length > available && !(node->status & RE_STATUS_FUZZY))
                    goto backtrack;

                if (string_pos < 0)
                    string_pos = 0;

                values = node->values;

                /* Try comparing. */
                while (string_pos < length) {
                    if (text_pos < slice_end && char_at(text, text_pos) ==
                      values[string_pos]) {
                        ++string_pos;
                        ++text_pos;
                    } else if (node->status & RE_STATUS_FUZZY) {
                        BOOL matched;

                        if (!fuzzy_match_string(safe_state, search, &text_pos,
                          node, &string_pos, &matched, 1))
                            return RE_ERROR_BACKTRACKING;
                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }
                    } else {
                        string_pos = -1;
                        goto backtrack;
                    }
                }

                string_pos = -1;
            }

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_FLD: /* A string literal, ignoring case. */
        {
            Py_ssize_t length;
            Py_ssize_t available;
            int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
            RE_CODE* values;
            int folded_len;
            Py_UCS4 folded[RE_MAX_FOLDED];
            TRACE(("%s %d\n", re_op_text[node->op], node->value_count))

            if ((node->status & RE_STATUS_REQUIRED) && text_pos ==
              state->req_pos && string_pos < 0)
                text_pos = state->req_end;
            else {
                /* Are there enough characters to match? */
                length = node->value_count;
                available = slice_end - text_pos;
                if ((Py_ssize_t)possible_unfolded_length(length) > available &&
                  !(node->status & RE_STATUS_FUZZY))
                    goto backtrack;

                full_case_fold = encoding->full_case_fold;

                if (string_pos < 0) {
                    string_pos = 0;
                    folded_pos = 0;
                    folded_len = 0;
                } else {
                    folded_len = full_case_fold(char_at(text, text_pos),
                      folded);
                    if (folded_pos >= folded_len) {
                        if (text_pos >= slice_end)
                            goto backtrack;

                        ++text_pos;
                        folded_pos = 0;
                        folded_len = 0;
                    }
                }

                values = node->values;

                /* Try comparing. */
                while (string_pos < length) {
                    if (folded_pos >= folded_len) {
                        folded_len = full_case_fold(char_at(text, text_pos),
                          folded);
                        folded_pos = 0;
                    }

                    if (same_char_ign(encoding, folded[folded_pos],
                      values[string_pos])) {
                        ++string_pos;
                        ++folded_pos;

                        if (folded_pos >= folded_len)
                            ++text_pos;
                    } else if (node->status & RE_STATUS_FUZZY) {
                        BOOL matched;

                        if (!fuzzy_match_string_fld(safe_state, search,
                          &text_pos, node, &string_pos, &folded_pos,
                          folded_len, &matched, 1))
                            return RE_ERROR_BACKTRACKING;
                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }

                        if (folded_pos >= folded_len)
                            ++text_pos;
                    } else {
                        string_pos = -1;
                        goto backtrack;
                    }
                }

                if (node->status & RE_STATUS_FUZZY) {
                    while (folded_pos < folded_len) {
                        BOOL matched;

                        if (!fuzzy_match_string_fld(safe_state, search,
                          &text_pos, node, &string_pos, &folded_pos,
                          folded_len, &matched, 1))
                            return RE_ERROR_BACKTRACKING;

                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }

                        if (folded_pos >= folded_len)
                            ++text_pos;
                    }
                }

                if (folded_pos < folded_len) {
                    string_pos = -1;
                    goto backtrack;
                }

                string_pos = -1;
            }

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_FLD_REV: /* A string literal, ignoring case. */
        {
            Py_ssize_t length;
            Py_ssize_t available;
            int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
            RE_CODE* values;
            int folded_len;
            Py_UCS4 folded[RE_MAX_FOLDED];
            TRACE(("%s %d\n", re_op_text[node->op], node->value_count))

            if ((node->status & RE_STATUS_REQUIRED) && text_pos ==
              state->req_pos && string_pos < 0)
                text_pos = state->req_end;
            else {
                /* Are there enough characters to match? */
                length = node->value_count;
                available = text_pos - slice_start;
                if ((Py_ssize_t)possible_unfolded_length(length) > available &&
                  !(node->status & RE_STATUS_FUZZY))
                    goto backtrack;

                full_case_fold = encoding->full_case_fold;

                if (string_pos < 0) {
                    string_pos = length;
                    folded_pos = 0;
                    folded_len = 0;
                } else {
                    folded_len = full_case_fold(char_at(text, text_pos - 1),
                      folded);
                    if (folded_pos <= 0) {
                        if (text_pos <= slice_start)
                            goto backtrack;

                        --text_pos;
                        folded_pos = 0;
                        folded_len = 0;
                    }
                }

                values = node->values;

                /* Try comparing. */
                while (string_pos > 0) {
                    if (folded_pos <= 0) {
                        folded_len = full_case_fold(char_at(text, text_pos -
                          1), folded);
                        folded_pos = folded_len;
                    }

                    if (same_char_ign(encoding, folded[folded_pos - 1],
                      values[string_pos - 1])) {
                        --string_pos;
                        --folded_pos;

                        if (folded_pos <= 0)
                            --text_pos;
                    } else if (node->status & RE_STATUS_FUZZY) {
                        BOOL matched;

                        if (!fuzzy_match_string_fld(safe_state, search,
                          &text_pos, node, &string_pos, &folded_pos,
                          folded_len, &matched, -1))
                            return RE_ERROR_BACKTRACKING;
                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }

                        if (folded_pos <= 0)
                            --text_pos;
                    } else {
                        string_pos = -1;
                        goto backtrack;
                    }
                }

                if (node->status & RE_STATUS_FUZZY) {
                    while (folded_pos > 0) {
                        BOOL matched;

                        if (!fuzzy_match_string_fld(safe_state, search,
                          &text_pos, node, &string_pos, &folded_pos,
                          folded_len, &matched, -1))
                            return RE_ERROR_BACKTRACKING;

                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }

                        if (folded_pos <= 0)
                            --text_pos;
                    }
                }

                if (folded_pos > 0) {
                    string_pos = -1;
                    goto backtrack;
                }

                string_pos = -1;
            }

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_IGN: /* A string literal, ignoring case. */
        {
            Py_ssize_t length;
            Py_ssize_t available;
            RE_CODE* values;
            TRACE(("%s %d\n", re_op_text[node->op], node->value_count))

            if ((node->status & RE_STATUS_REQUIRED) && text_pos ==
              state->req_pos && string_pos < 0)
                text_pos = state->req_end;
            else {
                /* Are there enough characters to match? */
                length = node->value_count;
                available = slice_end - text_pos;
                if (length > available && !(node->status & RE_STATUS_FUZZY))
                    goto backtrack;

                if (string_pos < 0)
                    string_pos = 0;

                values = node->values;

                /* Try comparing. */
                while (string_pos < length) {
                    if (text_pos < slice_end && same_char_ign(encoding,
                      char_at(text, text_pos), values[string_pos])) {
                        ++string_pos;
                        ++text_pos;
                    } else if (node->status & RE_STATUS_FUZZY) {
                        BOOL matched;

                        if (!fuzzy_match_string(safe_state, search, &text_pos,
                          node, &string_pos, &matched, 1))
                            return RE_ERROR_BACKTRACKING;
                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }
                    } else {
                        string_pos = -1;
                        goto backtrack;
                    }
                }

                string_pos = -1;
            }

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_IGN_REV: /* A string literal, ignoring case. */
        {
            Py_ssize_t length;
            Py_ssize_t available;
            RE_CODE* values;
            TRACE(("%s %d\n", re_op_text[node->op], node->value_count))

            if ((node->status & RE_STATUS_REQUIRED) && text_pos ==
              state->req_pos && string_pos < 0)
                text_pos = state->req_end;
            else {
                /* Are there enough characters to match? */
                length = node->value_count;
                available = text_pos - slice_start;
                if (length > available && !(node->status & RE_STATUS_FUZZY))
                    goto backtrack;

                if (string_pos < 0)
                    string_pos = length;

                values = node->values;

                /* Try comparing. */
                while (string_pos > 0) {
                    if (text_pos > slice_start && same_char_ign(encoding,
                      char_at(text, text_pos - 1), values[string_pos - 1])) {
                        --string_pos;
                        --text_pos;
                    } else if (node->status & RE_STATUS_FUZZY) {
                        BOOL matched;

                        if (!fuzzy_match_string(safe_state, search, &text_pos,
                          node, &string_pos, &matched, -1))
                            return RE_ERROR_BACKTRACKING;
                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }
                    } else {
                        string_pos = -1;
                        goto backtrack;
                    }
                }

                string_pos = -1;
            }

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_REV: /* A string literal. */
        {
            Py_ssize_t length;
            Py_ssize_t available;
            RE_CODE* values;
            TRACE(("%s %d\n", re_op_text[node->op], node->value_count))

            if ((node->status & RE_STATUS_REQUIRED) && text_pos ==
              state->req_pos && string_pos < 0)
                text_pos = state->req_end;
            else {
                /* Are there enough characters to match? */
                length = node->value_count;
                available = text_pos - slice_start;
                if (length > available && !(node->status & RE_STATUS_FUZZY))
                    goto backtrack;

                if (string_pos < 0)
                    string_pos = length;

                values = node->values;

                /* Try comparing. */
                while (string_pos > 0) {
                    if (text_pos > slice_start && char_at(text, text_pos - 1)
                      == values[string_pos - 1]) {
                        --string_pos;
                        --text_pos;
                    } else if (node->status & RE_STATUS_FUZZY) {
                        BOOL matched;

                        if (!fuzzy_match_string(safe_state, search, &text_pos,
                          node, &string_pos, &matched, -1))
                            return RE_ERROR_BACKTRACKING;
                        if (!matched) {
                            string_pos = -1;
                            goto backtrack;
                        }
                    } else {
                        string_pos = -1;
                        goto backtrack;
                    }
                }

                string_pos = -1;
            }

            /* Successful match. */
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_SET: /* Member of a string set. */
        {
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            state->text_pos = text_pos;
            status = string_set_match(safe_state, node);
            if (status < 0)
                return status;
            if (status == 0)
                goto backtrack;
            text_pos = state->text_pos;
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_SET_FLD: /* Member of a string set, ignoring case. */
        {
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            state->text_pos = text_pos;
            status = string_set_match_fld(safe_state, node);
            if (status < 0)
                return status;
            if (status == 0)
                goto backtrack;
            text_pos = state->text_pos;
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_SET_FLD_REV: /* Member of a string set, ignoring case. */
        {
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            state->text_pos = text_pos;
            status = string_set_match_fld_rev(safe_state, node);
            if (status < 0)
                return status;
            if (status == 0)
                goto backtrack;
            text_pos = state->text_pos;
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_SET_IGN: /* Member of a string set, ignoring case. */
        {
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            state->text_pos = text_pos;
            status = string_set_match_ign(safe_state, node);
            if (status < 0)
                return status;
            if (status == 0)
                goto backtrack;
            text_pos = state->text_pos;
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_SET_IGN_REV: /* Member of a string set, ignoring case. */
        {
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            state->text_pos = text_pos;
            status = string_set_match_ign_rev(safe_state, node);
            if (status < 0)
                return status;
            if (status == 0)
                goto backtrack;
            text_pos = state->text_pos;
            node = node->next_1.node;
            break;
        }
        case RE_OP_STRING_SET_REV: /* Member of a string set. */
        {
            int status;
            TRACE(("%s\n", re_op_text[node->op]))

            state->text_pos = text_pos;
            status = string_set_match_rev(safe_state, node);
            if (status < 0)
                return status;
            if (status == 0)
                goto backtrack;
            text_pos = state->text_pos;
            node = node->next_1.node;
            break;
        }
        case RE_OP_SUCCESS: /* Success. */
            /* Must the match advance past its start? */
            TRACE(("%s\n", re_op_text[node->op]))

            if (text_pos == state->search_anchor && state->must_advance)
                goto backtrack;

            if (state->match_all && !recursive_call) {
                /* We want to match all of the slice. */
                if (state->reverse) {
                    if (text_pos != slice_start)
                        goto backtrack;
                } else {
                    if (text_pos != slice_end)
                        goto backtrack;
                }
            }

            state->text_pos = text_pos;
            return RE_ERROR_SUCCESS;
        default: /* Illegal opcode! */
            TRACE(("UNKNOWN OP %d\n", node->op))
            return RE_ERROR_ILLEGAL;
        }
    }

backtrack:
    for (;;) {
        RE_BacktrackData* bt_data;
        TRACE(("BACKTRACK "))

        /* Should we abort the matching? */
        ++state->iterations;

        if (state->iterations == 0 && safe_check_signals(safe_state))
            return RE_ERROR_INTERRUPTED;

        bt_data = last_backtrack(state);

        switch (bt_data->op) {
        case RE_OP_ANY: /* Any character, except a newline. */
        case RE_OP_ANY_ALL: /* Any character at all. */
        case RE_OP_ANY_ALL_REV: /* Any character at all. */
        case RE_OP_ANY_REV: /* Any character, except a newline. */
        case RE_OP_ANY_U: /* Any character, except a line separator. */
        case RE_OP_ANY_U_REV: /* Any character, except a line separator. */
        case RE_OP_CHARACTER: /* A character literal. */
        case RE_OP_CHARACTER_IGN: /* A character literal, ignoring case. */
        case RE_OP_CHARACTER_IGN_REV: /* A character literal, ignoring case. */
        case RE_OP_CHARACTER_REV: /* A character literal. */
        case RE_OP_PROPERTY: /* A property. */
        case RE_OP_PROPERTY_IGN: /* A property, ignoring case. */
        case RE_OP_PROPERTY_IGN_REV: /* A property, ignoring case. */
        case RE_OP_PROPERTY_REV: /* A property. */
        case RE_OP_RANGE: /* A range. */
        case RE_OP_RANGE_IGN: /* A range, ignoring case. */
        case RE_OP_RANGE_IGN_REV: /* A range, ignoring case. */
        case RE_OP_RANGE_REV: /* A range. */
        case RE_OP_SET_DIFF: /* Character set. */
        case RE_OP_SET_DIFF_IGN: /* Character set, ignoring case. */
        case RE_OP_SET_DIFF_IGN_REV: /* Character set, ignoring case. */
        case RE_OP_SET_DIFF_REV: /* Character set. */
        case RE_OP_SET_INTER: /* Character set. */
        case RE_OP_SET_INTER_IGN: /* Character set, ignoring case. */
        case RE_OP_SET_INTER_IGN_REV: /* Character set, ignoring case. */
        case RE_OP_SET_INTER_REV: /* Character set. */
        case RE_OP_SET_SYM_DIFF: /* Character set. */
        case RE_OP_SET_SYM_DIFF_IGN: /* Character set, ignoring case. */
        case RE_OP_SET_SYM_DIFF_IGN_REV: /* Character set, ignoring case. */
        case RE_OP_SET_SYM_DIFF_REV: /* Character set. */
        case RE_OP_SET_UNION: /* Character set. */
        case RE_OP_SET_UNION_IGN: /* Character set, ignoring case. */
        case RE_OP_SET_UNION_IGN_REV: /* Character set, ignoring case. */
        case RE_OP_SET_UNION_REV: /* Character set. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            if (!retry_fuzzy_match_one(safe_state, search, &text_pos, &node))
                return RE_ERROR_BACKTRACKING;
            if (node)
                goto advance;
            break;
        case RE_OP_ATOMIC: /* Atomic subpattern. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            /* Restore the groups and certain flags and then backtrack. */
            pop_groups(state);
            state->too_few_errors = bt_data->atomic.too_few_errors;
            state->capture_change = bt_data->atomic.capture_change;
            discard_backtrack(state);
            break;
        case RE_OP_BODY_END:
        {
            RE_RepeatData* rp_data;
            TRACE(("%s %d\n", re_op_text[bt_data->op], bt_data->repeat.index))

            /* We're backtracking into the body. */
            rp_data = &state->repeats[bt_data->repeat.index];

            /* Restore the repeat info. */
            rp_data->count = bt_data->repeat.count;
            rp_data->start = bt_data->repeat.start;
            rp_data->capture_change = bt_data->repeat.capture_change;

            discard_backtrack(state);
            break;
        }
        case RE_OP_BODY_START:
        {
            TRACE(("%s %d\n", re_op_text[bt_data->op], bt_data->repeat.index))

            /* The body may have failed to match at this position. */
            if (!guard_repeat(safe_state, bt_data->repeat.index,
              bt_data->repeat.text_pos, RE_STATUS_BODY, TRUE))
                return RE_ERROR_MEMORY;

            discard_backtrack(state);
            break;
        }
        case RE_OP_BOUNDARY: /* At a word boundary. */
        case RE_OP_DEFAULT_BOUNDARY: /* At a default word boundary. */
        case RE_OP_DEFAULT_END_OF_WORD: /* At a default end of a word. */
        case RE_OP_DEFAULT_START_OF_WORD: /* At a default start of a word. */
        case RE_OP_END_OF_LINE: /* At the end of a line. */
        case RE_OP_END_OF_LINE_U: /* At the end of a line. */
        case RE_OP_END_OF_STRING: /* At the end of the string. */
        case RE_OP_END_OF_STRING_LINE: /* At end of string or final newline. */
        case RE_OP_END_OF_STRING_LINE_U: /* At end of string or final newline. */
        case RE_OP_END_OF_WORD: /* At end of a word. */
        case RE_OP_GRAPHEME_BOUNDARY: /* At a grapheme boundary. */
        case RE_OP_SEARCH_ANCHOR: /* At the start of the search. */
        case RE_OP_START_OF_LINE: /* At the start of a line. */
        case RE_OP_START_OF_LINE_U: /* At the start of a line. */
        case RE_OP_START_OF_STRING: /* At the start of the string. */
        case RE_OP_START_OF_WORD: /* At start of a word. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            if (!retry_fuzzy_match_zero(safe_state, search, &text_pos, &node))
                return RE_ERROR_BACKTRACKING;
            if (node)
                goto advance;
            break;
        case RE_OP_BRANCH: /* 2-way branch. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            node = bt_data->branch.position.node;
            text_pos = bt_data->branch.position.text_pos;
            discard_backtrack(state);
            goto advance;
        case RE_OP_CALL_REF: /* A group call ref. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            pop_group_return(state);
            discard_backtrack(state);
            break;
        case RE_OP_END_FUZZY: /* End of fuzzy matching. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            /* We need to retry the fuzzy match. */
            if (!retry_fuzzy_insert(safe_state, &text_pos, &node))
                return RE_ERROR_BACKTRACKING;

            /* If there were too few errors, in the fuzzy section, try again.
             */
            if (state->too_few_errors) {
                state->too_few_errors = FALSE;
                goto backtrack;
            }

            if (node) {
                node = node->next_1.node;
                goto advance;
            }
            break;
        case RE_OP_END_GROUP: /* End of a capture group. */
        {
            RE_CODE private_index;
            RE_GroupData* group;
            TRACE(("%s %d\n", re_op_text[bt_data->op],
              bt_data->group.public_index))

            private_index = bt_data->group.private_index;
            group = &state->groups[private_index - 1];

            /* Unsave the capture? */
            if (bt_data->group.capture)
                unsave_capture(state, bt_data->group.private_index,
                  bt_data->group.public_index);

            if (pattern->group_info[private_index - 1].referenced &&
              group->span.end != bt_data->group.text_pos)
                --state->capture_change;
            group->span.end = bt_data->group.text_pos;
            group->current_capture = bt_data->group.current_capture;

            discard_backtrack(state);
            break;
        }
        case RE_OP_FAILURE:
        {
            Py_ssize_t end_pos;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            /* Do we have to advance? */
            if (!search)
                return RE_ERROR_FAILURE;

            /* Can we advance? */
            text_pos = state->match_pos;
            end_pos = state->reverse ? slice_start : slice_end;
            if (text_pos == end_pos)
                return RE_ERROR_FAILURE;

            /* Skip over any repeated leading characters. */
            switch (start_node->op) {
            case RE_OP_GREEDY_REPEAT_ONE:
            case RE_OP_LAZY_REPEAT_ONE:
            {
                size_t count;

                /* How many characters did the repeat actually match? */
                count = count_one(state, start_node->nonstring.next_2.node,
                  text_pos, (size_t)start_node->values[2]);

                /* If it's fewer than the maximum then skip over those
                 * characters.
                 */
                if (count < start_node->values[2])
                    text_pos += (Py_ssize_t)count * pattern_step;
                break;
            }
            }

            /* Advance and try to match again. */
            state->text_pos = text_pos + pattern_step;

            goto start_match;
        }
        case RE_OP_FUZZY: /* Fuzzy matching. */
        {
            RE_FuzzyInfo* fuzzy_info;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            /* Restore the previous fuzzy info. */
            fuzzy_info = &state->fuzzy_info;
            memmove(fuzzy_info, &bt_data->fuzzy.fuzzy_info,
               sizeof(RE_FuzzyInfo));

            discard_backtrack(state);
            break;
        }
        case RE_OP_GREEDY_REPEAT: /* Greedy repeat. */
        case RE_OP_LAZY_REPEAT: /* Lazy repeat. */
        {
            RE_RepeatData* rp_data;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            /* The repeat failed to match. */
            rp_data = &state->repeats[bt_data->repeat.index];

            /* The body may have failed to match at this position. */
            if (!guard_repeat(safe_state, bt_data->repeat.index,
              bt_data->repeat.text_pos, RE_STATUS_BODY, TRUE))
                return RE_ERROR_MEMORY;

            /* Restore the previous repeat. */
            rp_data->count = bt_data->repeat.count;
            rp_data->start = bt_data->repeat.start;
            rp_data->capture_change = bt_data->repeat.capture_change;

            discard_backtrack(state);
            break;
        }
        case RE_OP_GREEDY_REPEAT_ONE: /* Greedy repeat for one character. */
        {
            RE_RepeatData* rp_data;
            size_t count;
            Py_ssize_t step;
            Py_ssize_t pos;
            Py_ssize_t limit;
            RE_Node* test;
            BOOL match;
            BOOL m;
            size_t index;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            node = bt_data->repeat.position.node;

            rp_data = &state->repeats[bt_data->repeat.index];

            /* Unmatch one character at a time until the tail could match or we
             * have reached the minimum.
             */
            text_pos = rp_data->start;

            count = rp_data->count;
            step = node->step;
            pos = text_pos + (Py_ssize_t)count * step;
            limit = text_pos + (Py_ssize_t)node->values[1] * step;

            /* The tail failed to match at this position. */
            if (!guard_repeat(safe_state, bt_data->repeat.index, pos,
              RE_STATUS_TAIL, TRUE))
                return RE_ERROR_MEMORY;

            if (count == node->values[1]) {
                /* We've backtracked the repeat as far as we can. */
                rp_data->start = bt_data->repeat.text_pos;
                rp_data->count = bt_data->repeat.count;
                discard_backtrack(state);
                break;
            }

            test = node->next_1.test;

            m = test->match;
            index = node->values[0];

            match = FALSE;

            if (test->status & RE_STATUS_FUZZY) {
                for (;;) {
                    RE_Position next_position;

                    pos -= step;

                    if (try_match(state, &node->next_1, pos, &next_position) &&
                      !is_repeat_guarded(safe_state, index, pos,
                      RE_STATUS_TAIL)) {
                        match = TRUE;
                        break;
                    }

                    if (pos == limit)
                        break;
                }
            } else {
                /* A repeated single-character match is often followed by a
                 * literal, so checking specially for it can be a good
                 * optimisation when working with long strings.
                 */
                switch (test->op) {
                case RE_OP_CHARACTER:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MAX(limit, slice_start + 1);

                    for (;;) {
                        if (pos <= limit)
                            break;

                        --pos;

                        if ((char_at(text, pos) == ch) == m &&
                          !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_CHARACTER_IGN:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MAX(limit, slice_start + 1);

                    for (;;) {
                        if (pos <= limit)
                            break;

                        --pos;

                        if (same_char_ign(encoding, char_at(text, pos), ch) ==
                          m && !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_CHARACTER_IGN_REV:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MIN(limit, slice_end - 1);

                    for (;;) {
                        if (pos >= limit)
                            break;

                        ++pos;

                        if (same_char_ign(encoding, char_at(text, pos - 1), ch)
                          == m && !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_CHARACTER_REV:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MIN(limit, slice_end - 1);

                    for (;;) {
                        if (pos >= limit)
                            break;

                        ++pos;

                        if ((char_at(text, pos - 1) == ch) == m &&
                          !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    pos = RE_MIN(pos, slice_end - length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos < limit)
                            break;

                        found = string_search_rev(safe_state, test, pos +
                          length, limit);
                        if (found < 0)
                            break;

                        pos = found - length;

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        --pos;
                    }
                    break;
                }
                case RE_OP_STRING_FLD:
                {
                    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
                    size_t folded_length;
                    size_t i;
                    Py_UCS4 folded[RE_MAX_FOLDED];

                    full_case_fold = encoding->full_case_fold;

                    folded_length = 0;
                    for (i = 0; i < test->value_count; i++)
                        folded_length += full_case_fold(test->values[i],
                          folded);

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    pos = RE_MIN(pos, slice_end - (Py_ssize_t)folded_length);

                    for (;;) {
                        Py_ssize_t found;
                        Py_ssize_t new_pos;

                        if (pos < limit)
                            break;

                        found = string_search_fld_rev(safe_state, test, pos +
                          folded_length, limit, &new_pos);
                        if (found < 0)
                            break;

                        pos = found - folded_length;

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        --pos;
                    }
                    break;
                }
                case RE_OP_STRING_FLD_REV:
                {
                    int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
                    size_t folded_length;
                    size_t i;
                    Py_UCS4 folded[RE_MAX_FOLDED];

                    full_case_fold = encoding->full_case_fold;

                    folded_length = 0;
                    for (i = 0; i < test->value_count; i++)
                        folded_length += full_case_fold(test->values[i],
                          folded);

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    pos = RE_MAX(pos, slice_start + (Py_ssize_t)folded_length);

                    for (;;) {
                        Py_ssize_t found;
                        Py_ssize_t new_pos;

                        if (pos > limit)
                            break;

                        found = string_search_fld(safe_state, test, pos -
                          folded_length, limit, &new_pos);
                        if (found < 0)
                            break;

                        pos = found + folded_length;

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        ++pos;
                    }
                    break;
                }
                case RE_OP_STRING_IGN:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    pos = RE_MIN(pos, slice_end - length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos < limit)
                            break;

                        found = string_search_ign_rev(safe_state, test, pos +
                          length, limit);
                        if (found < 0)
                            break;

                        pos = found - length;

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        --pos;
                    }
                    break;
                }
                case RE_OP_STRING_IGN_REV:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    pos = RE_MAX(pos, slice_start + length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos > limit)
                            break;

                        found = string_search_ign(safe_state, test, pos -
                          length, limit);
                        if (found < 0)
                            break;

                        pos = found + length;

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        ++pos;
                    }
                    break;
                }
                case RE_OP_STRING_REV:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    pos = RE_MAX(pos, slice_start + length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos > limit)
                            break;

                        found = string_search(safe_state, test, pos - length,
                          limit);
                        if (found < 0)
                            break;

                        pos = found + length;

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        ++pos;
                    }
                    break;
                }
                default:
                    for (;;) {
                        RE_Position next_position;

                        pos -= step;

                        if (try_match(state, &node->next_1, pos,
                          &next_position) && !is_repeat_guarded(safe_state,
                          index, pos, RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        if (pos == limit)
                            break;
                    }
                    break;
                }
            }

            if (match) {
                count = abs_ssize_t(pos - text_pos);

                /* The tail could match. */
                if (count > node->values[1])
                    /* The match is longer than the minimum, so we might need
                     * to backtrack the repeat again to consume less.
                     */
                    rp_data->count = count;
                else {
                    /* We've reached or passed the minimum, so we won't need to
                     * backtrack the repeat again.
                     */
                    rp_data->start = bt_data->repeat.text_pos;
                    rp_data->count = bt_data->repeat.count;
                    discard_backtrack(state);

                    /* Have we passed the minimum? */
                    if (count < node->values[1])
                        goto backtrack;
                }

                node = node->next_1.node;
                text_pos = pos;
                goto advance;
            } else {
                /* We've backtracked the repeat as far as we can. */
                rp_data->start = bt_data->repeat.text_pos;
                rp_data->count = bt_data->repeat.count;
                discard_backtrack(state);
            }
            break;
        }
        case RE_OP_GROUP_CALL: /* Group call. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            pop_group_return(state);
            discard_backtrack(state);
            break;
        case RE_OP_GROUP_RETURN: /* Group return. */
        {
            RE_Node* return_node;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            return_node = bt_data->group_call.node;

            push_group_return(safe_state, return_node);

            if (return_node) {
                /* Restore the groups. */
                pop_groups(state);
                state->capture_change = bt_data->group_call.capture_change;

                /* Restore the repeats. */
                pop_repeats(state);
            }

            discard_backtrack(state);
            break;
        }
        case RE_OP_LAZY_REPEAT_ONE: /* Lazy repeat for one character. */
        {
            RE_RepeatData* rp_data;
            size_t count;
            Py_ssize_t step;
            Py_ssize_t pos;
            size_t available;
            size_t max_count;
            Py_ssize_t limit;
            RE_Node* repeated;
            RE_Node* test;
            BOOL match;
            BOOL m;
            size_t index;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            node = bt_data->repeat.position.node;

            rp_data = &state->repeats[bt_data->repeat.index];

            /* Match one character at a time until the tail could match or we
             * have reached the maximum.
             */
            text_pos = rp_data->start;
            count = rp_data->count;

            step = node->step;
            pos = text_pos + (Py_ssize_t)count * step;
            available = step > 0 ? slice_end - text_pos : text_pos -
              slice_start;
            max_count = RE_MIN(node->values[2], available);
            limit = text_pos + (Py_ssize_t)max_count * step;

            repeated = node->nonstring.next_2.node;

            test = node->next_1.test;

            m = test->match;
            index = node->values[0];

            match = FALSE;

            if (test->status & RE_STATUS_FUZZY) {
                for (;;) {
                    RE_Position next_position;

                    if (!match_one(state, repeated, pos))
                        break;

                    pos += step;

                    if (try_match(state, &node->next_1, pos, &next_position) &&
                      !is_repeat_guarded(safe_state, index, pos,
                      RE_STATUS_TAIL)) {
                        match = TRUE;
                        break;
                    }

                    if (pos == limit)
                        break;
                }
            } else {
                /* A repeated single-character match is often followed by a
                 * literal, so checking specially for it can be a good
                 * optimisation when working with long strings.
                 */
                switch (test->op) {
                case RE_OP_CHARACTER:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MIN(limit, slice_end - 1);

                    for (;;) {
                        if (pos >= limit)
                            break;

                        if (!match_one(state, repeated, pos))
                            break;

                        ++pos;

                        if ((char_at(text, pos) == ch) == m &&
                          !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_CHARACTER_IGN:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MIN(limit, slice_end - 1);

                    for (;;) {
                        if (pos >= limit)
                            break;

                        if (!match_one(state, repeated, pos))
                            break;

                        ++pos;

                        if (same_char_ign(encoding, char_at(text, pos), ch) ==
                          m && !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_CHARACTER_IGN_REV:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MAX(limit, slice_start + 1);

                    for (;;) {
                        if (pos <= limit)
                            break;

                        if (!match_one(state, repeated, pos))
                            break;

                        --pos;

                        if (same_char_ign(encoding, char_at(text, pos - 1), ch)
                          == m && !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_CHARACTER_REV:
                {
                    Py_UCS4 ch;

                    ch = test->values[0];

                    /* The tail is a character. We don't want to go off the end
                     * of the slice.
                     */
                    limit = RE_MAX(limit, slice_start + 1);

                    for (;;) {
                        if (pos <= limit)
                            break;

                        if (!match_one(state, repeated, pos))
                            break;

                        --pos;

                        if ((char_at(text, pos - 1) == ch) == m &&
                          !is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    limit = RE_MIN(limit, slice_end - length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos >= limit)
                            break;

                        /* Look for the tail string. */
                        found = string_search(safe_state, test, pos + 1, limit
                          + length);
                        if (found < 0)
                            break;

                        if (repeated->op == RE_OP_ANY_ALL)
                            /* Anything can precede the tail. */
                            pos = found;
                        else {
                            /* Check that what precedes the tail will match. */
                            while (pos != found && match_one(state, repeated,
                              pos))
                                ++pos;

                            if (pos != found)
                                /* Something preceding the tail didn't match.
                                 */
                                break;
                        }

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING_FLD:
                {
                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    limit = RE_MIN(limit, slice_end);

                    for (;;) {
                        Py_ssize_t found;
                        Py_ssize_t new_pos;

                        if (pos >= limit)
                            break;

                        /* Look for the tail string. */
                        found = string_search_fld(safe_state, test, pos + 1,
                          limit, &new_pos);
                        if (found < 0)
                            break;

                        if (repeated->op == RE_OP_ANY_ALL)
                            /* Anything can precede the tail. */
                            pos = found;
                        else {
                            /* Check that what precedes the tail will match. */
                            while (pos != found && match_one(state, repeated,
                              pos))
                                ++pos;

                            if (pos != found)
                                /* Something preceding the tail didn't match.
                                 */
                                break;
                        }

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING_FLD_REV:
                {
                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    limit = RE_MIN(limit, slice_start);

                    for (;;) {
                        Py_ssize_t found;
                        Py_ssize_t new_pos;

                        if (pos <= limit)
                            break;

                        /* Look for the tail string. */
                        found = string_search_fld_rev(safe_state, test, pos -
                          1, limit, &new_pos);
                        if (found < 0)
                            break;

                        if (repeated->op == RE_OP_ANY_ALL)
                            /* Anything can precede the tail. */
                            pos = found;
                        else {
                            /* Check that what precedes the tail will match. */
                            while (pos != found && match_one(state, repeated,
                              pos))
                                --pos;

                            if (pos != found)
                                /* Something preceding the tail didn't match.
                                 */
                                break;
                        }

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING_IGN:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    limit = RE_MIN(limit, slice_end - length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos >= limit)
                            break;

                        /* Look for the tail string. */
                        found = string_search_ign(safe_state, test, pos + 1,
                          limit + length);
                        if (found < 0)
                            break;

                        if (repeated->op == RE_OP_ANY_ALL)
                            /* Anything can precede the tail. */
                            pos = found;
                        else {
                            /* Check that what precedes the tail will match. */
                            while (pos != found && match_one(state, repeated,
                              pos))
                                ++pos;

                            if (pos != found)
                                /* Something preceding the tail didn't match.
                                 */
                                break;
                        }

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING_IGN_REV:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    limit = RE_MAX(limit, slice_start + length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos <= limit)
                            break;

                        /* Look for the tail string. */
                        found = string_search_ign_rev(safe_state, test, pos -
                          1, limit - length);
                        if (found < 0)
                            break;

                        if (repeated->op == RE_OP_ANY_ALL)
                            /* Anything can precede the tail. */
                            pos = found;
                        else {
                            /* Check that what precedes the tail will match. */
                            while (pos != found && match_one(state, repeated,
                              pos))
                                --pos;

                            if (pos != found)
                                /* Something preceding the tail didn't match.
                                 */
                                break;
                        }

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                case RE_OP_STRING_REV:
                {
                    Py_ssize_t length;

                    length = test->value_count;

                    /* The tail is a string. We don't want to go off the end of
                     * the slice.
                     */
                    limit = RE_MAX(limit, slice_start + length);

                    for (;;) {
                        Py_ssize_t found;

                        if (pos <= limit)
                            break;

                        /* Look for the tail string. */
                        found = string_search_rev(safe_state, test, pos - 1,
                          limit - length);
                        if (found < 0)
                            break;

                        if (repeated->op == RE_OP_ANY_ALL)
                            /* Anything can precede the tail. */
                            pos = found;
                        else {
                            /* Check that what precedes the tail will match. */
                            while (pos != found && match_one(state, repeated,
                              pos))
                                --pos;

                            if (pos != found)
                                /* Something preceding the tail didn't match.
                                 */
                                break;
                        }

                        if (!is_repeat_guarded(safe_state, index, pos,
                          RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }
                    }
                    break;
                }
                default:
                    for (;;) {
                        RE_Position next_position;

                        if (!match_one(state, repeated, pos))
                            break;

                        pos += step;

                        if (try_match(state, &node->next_1, pos,
                          &next_position) && !is_repeat_guarded(safe_state,
                          index, pos, RE_STATUS_TAIL)) {
                            match = TRUE;
                            break;
                        }

                        if (pos == limit)
                            break;
                    }
                    break;
                }
            }

            if (match) {
                /* The tail could match. */
                count = abs_ssize_t(pos - text_pos);
                text_pos = pos;

                if (count < max_count) {
                    /* The match is shorter than the maximum, so we might need
                     * to backtrack the repeat again to consume more.
                     */
                    rp_data->count = count;
                } else {
                    /* We've reached or passed the maximum, so we won't need to
                     * backtrack the repeat again.
                     */
                    rp_data->start = bt_data->repeat.text_pos;
                    rp_data->count = bt_data->repeat.count;
                    discard_backtrack(state);

                    /* Have we passed the maximum? */
                    if (count > max_count)
                        goto backtrack;
                }

                node = node->next_1.node;
                goto advance;
            } else {
                /* The tail couldn't match. */
                rp_data->start = bt_data->repeat.text_pos;
                rp_data->count = bt_data->repeat.count;
                discard_backtrack(state);
            }
            break;
        }
        case RE_OP_LOOKAROUND: /* Lookaround. */
            TRACE(("%s\n", re_op_text[bt_data->op]))

            /* Restore the groups and certain flags and then backtrack. */
            pop_groups(state);
            state->too_few_errors = bt_data->lookaround.too_few_errors;
            state->capture_change = bt_data->lookaround.capture_change;
            discard_backtrack(state);
            break;
        case RE_OP_MATCH_BODY:
        {
            RE_RepeatData* rp_data;
            TRACE(("%s %d\n", re_op_text[bt_data->op], bt_data->repeat.index))

            /* We want to match the body. */
            rp_data = &state->repeats[bt_data->repeat.index];

            /* Restore the repeat info. */
            rp_data->count = bt_data->repeat.count;
            rp_data->start = bt_data->repeat.start;
            rp_data->capture_change = bt_data->repeat.capture_change;

            /* Record backtracking info in case the body fails to match. */
            bt_data->op = RE_OP_BODY_START;

            /* Advance into the body. */
            node = bt_data->repeat.position.node;
            text_pos = bt_data->repeat.position.text_pos;
            goto advance;
        }
        case RE_OP_MATCH_TAIL:
        {
            RE_RepeatData* rp_data;
            TRACE(("%s %d\n", re_op_text[bt_data->op], bt_data->repeat.index))

            /* We want to match the tail. */
            rp_data = &state->repeats[bt_data->repeat.index];

            /* Restore the repeat info. */
            rp_data->count = bt_data->repeat.count;
            rp_data->start = bt_data->repeat.start;
            rp_data->capture_change = bt_data->repeat.capture_change;

            /* Advance into the tail. */
            node = bt_data->repeat.position.node;
            text_pos = bt_data->repeat.position.text_pos;

            discard_backtrack(state);
            goto advance;
        }
        case RE_OP_REF_GROUP: /* Reference to a capture group. */
        case RE_OP_REF_GROUP_IGN: /* Reference to a capture group, ignoring case. */
        case RE_OP_REF_GROUP_IGN_REV: /* Reference to a capture group backwards, ignoring case. */
        case RE_OP_REF_GROUP_REV: /* Reference to a capture group backwards. */
        case RE_OP_STRING: /* A string literal. */
        case RE_OP_STRING_IGN: /* A string literal, ignoring case. */
        case RE_OP_STRING_IGN_REV: /* A string literal backwards, ignoring case. */
        case RE_OP_STRING_REV: /* A string literal backwards. */
        {
            BOOL matched;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            if (!retry_fuzzy_match_string(safe_state, search, &text_pos, &node,
              &string_pos, &matched))
                return RE_ERROR_BACKTRACKING;
            if (matched)
                goto advance;
            string_pos = -1;
            break;
        }
        case RE_OP_REF_GROUP_FLD: /* Reference to a capture group, ignoring case. */
        case RE_OP_REF_GROUP_FLD_REV: /* Reference to a capture group backwards, ignoring case. */
        {
            BOOL matched;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            if (!retry_fuzzy_match_string_fld2(safe_state, search, &text_pos,
              &node, &folded_pos, &string_pos, &gfolded_pos, &matched))
                return RE_ERROR_BACKTRACKING;
            if (matched)
                goto advance;
            string_pos = -1;
            break;
        }
        case RE_OP_START_GROUP: /* Start of a capture group. */
        {
            RE_CODE private_index;
            RE_GroupData* group;
            TRACE(("%s %d\n", re_op_text[bt_data->op],
              bt_data->group.public_index))

            private_index = bt_data->group.private_index;
            group = &state->groups[private_index - 1];

            /* Unsave the capture? */
            if (bt_data->group.capture)
                unsave_capture(state, bt_data->group.private_index,
                  bt_data->group.public_index);

            if (pattern->group_info[private_index - 1].referenced &&
              group->span.start != bt_data->group.text_pos)
                --state->capture_change;
            group->span.start = bt_data->group.text_pos;
            group->current_capture = bt_data->group.current_capture;

            discard_backtrack(state);
            break;
        }
        case RE_OP_STRING_FLD: /* A string literal, ignoring case. */
        case RE_OP_STRING_FLD_REV: /* A string literal backwards, ignoring case. */
        {
            BOOL matched;
            TRACE(("%s\n", re_op_text[bt_data->op]))

            if (!retry_fuzzy_match_string_fld(safe_state, search, &text_pos,
              &node, &string_pos, &folded_pos, &matched))
                return RE_ERROR_BACKTRACKING;
            if (matched)
                goto advance;
            string_pos = -1;
            break;
        }
        default:
            TRACE(("UNKNOWN OP %d\n", bt_data->op))
            return RE_ERROR_ILLEGAL;
        }
    }
}

/* Saves group data for fuzzy matching. */
Py_LOCAL_INLINE(RE_GroupData*) save_groups(RE_SafeState* safe_state,
  RE_GroupData* saved_groups) {
    RE_State* state;
    PatternObject* pattern;
    size_t g;

    /* Re-acquire the GIL. */
    acquire_GIL(safe_state);

    state = safe_state->re_state;
    pattern = state->pattern;

    if (!saved_groups) {
        saved_groups = (RE_GroupData*)re_alloc(pattern->true_group_count *
          sizeof(RE_GroupData));
        if (!saved_groups)
            goto error;

        memset(saved_groups, 0, pattern->true_group_count *
          sizeof(RE_GroupData));
    }

    for (g = 0; g < pattern->true_group_count; g++) {
        RE_GroupData* orig;
        RE_GroupData* copy;

        orig = &state->groups[g];
        copy = &saved_groups[g];

        copy->span = orig->span;

        if (orig->capture_count > copy->capture_capacity) {
            RE_GroupSpan* cap_copy;

            cap_copy = (RE_GroupSpan*)re_realloc(copy->captures,
              orig->capture_count * sizeof(RE_GroupSpan));
            if (!cap_copy)
                goto error;

            copy->capture_capacity = orig->capture_count;
            copy->captures = cap_copy;
        }

        copy->capture_count = orig->capture_count;
        Py_MEMCPY(copy->captures, orig->captures, orig->capture_count *
          sizeof(RE_GroupSpan));
    }

    /* Release the GIL. */
    release_GIL(safe_state);

    return saved_groups;

error:
    if (saved_groups) {
        for (g = 0; g < pattern->true_group_count; g++)
            re_dealloc(saved_groups[g].captures);

        re_dealloc(saved_groups);
    }

    /* Release the GIL. */
    release_GIL(safe_state);

    return NULL;
}

/* Restores group data for fuzzy matching. */
Py_LOCAL_INLINE(void) restore_groups(RE_SafeState* safe_state, RE_GroupData*
  saved_groups) {
    RE_State* state;
    PatternObject* pattern;
    size_t g;

    /* Re-acquire the GIL. */
    acquire_GIL(safe_state);

    state = safe_state->re_state;
    pattern = state->pattern;

    for (g = 0; g < pattern->true_group_count; g++)
        re_dealloc(state->groups[g].captures);

    Py_MEMCPY(state->groups, saved_groups, pattern->true_group_count *
      sizeof(RE_GroupData));

    re_dealloc(saved_groups);

    /* Release the GIL. */
    release_GIL(safe_state);
}

/* Discards group data for fuzzy matching. */
Py_LOCAL_INLINE(void) discard_groups(RE_SafeState* safe_state, RE_GroupData*
  saved_groups) {
    RE_State* state;
    PatternObject* pattern;
    size_t g;

    /* Re-acquire the GIL. */
    acquire_GIL(safe_state);

    state = safe_state->re_state;
    pattern = state->pattern;

    for (g = 0; g < pattern->true_group_count; g++)
        re_dealloc(saved_groups[g].captures);

    re_dealloc(saved_groups);

    /* Release the GIL. */
    release_GIL(safe_state);
}

/* Performs a match or search from the current text position.
 *
 * The state can sometimes be shared across threads. In such instances there's
 * a lock (mutex) on it. The lock is held for the duration of matching.
 */
Py_LOCAL_INLINE(int) do_match(RE_SafeState* safe_state, BOOL search) {
    RE_State* state;
    PatternObject* pattern;
    size_t available;
    BOOL get_best;
    BOOL enhance_match;
    BOOL must_advance;
    RE_GroupData* best_groups;
    Py_ssize_t best_match_pos;
    Py_ssize_t best_text_pos = 0; /* Initialise to stop compiler warning. */
    int status;
    Py_ssize_t slice_start;
    Py_ssize_t slice_end;
    TRACE(("<<do_match>>\n"))

    state = safe_state->re_state;
    pattern = state->pattern;

    /* Release the GIL. */
    release_GIL(safe_state);

    /* Is there enough to search? */
    if (state->reverse) {
        if (state->text_pos < state->slice_start) {
            acquire_GIL(safe_state);
            return FALSE;
        }

        available = state->text_pos - state->slice_start;
    } else {
        if (state->text_pos > state->slice_end) {
            acquire_GIL(safe_state);
            return FALSE;
        }

        available = state->slice_end - state->text_pos;
    }

    get_best = (pattern->flags & RE_FLAG_BESTMATCH) != 0;
    enhance_match = (pattern->flags & RE_FLAG_ENHANCEMATCH) != 0 && !get_best;

    /* The maximum permitted cost. */
    state->max_cost = pattern->is_fuzzy ? RE_UNLIMITED : 0;

    best_groups = NULL;

    best_match_pos = state->text_pos;
    must_advance = state->must_advance;

    slice_start = state->slice_start;
    slice_end = state->slice_end;

    for (;;) {
        /* If there's a better match, it won't start earlier in the string than
         * the current best match, so there's no need to start earlier than
         * that match.
         */
        state->text_pos = best_match_pos;
        state->must_advance = must_advance;

        /* Initialise the state. */
        init_match(state);

        status = RE_ERROR_SUCCESS;
        if (state->max_cost == 0) {
            /* An exact match. */
            if (available < state->min_width || (available == 0 &&
              state->must_advance))
                status = RE_ERROR_FAILURE;
        }

        if (status == RE_ERROR_SUCCESS)
            status = basic_match(safe_state, state->pattern->start_node,
              search, FALSE);

        /* Has an error occurred? */
        if (status < 0)
            break;

        if (status == RE_ERROR_FAILURE || (status == RE_ERROR_SUCCESS &&
          state->total_cost == 0))
            break;

        if (!get_best && !enhance_match)
            break;

        if (!get_best && state->text_pos == state->match_pos)
            /* We want the first match. The match is already zero-width, so the
             * cost can't get any lower (because the fit can't get any better).
             */
            break;

        if (best_groups) {
            BOOL same;
            size_t g;

            /* Did we get the same match as the best so far? */
            same = state->match_pos == best_match_pos && state->text_pos ==
              best_text_pos;
            for (g = 0; same && g < pattern->public_group_count; g++) {
                same = state->groups[g].span.start == best_groups[g].span.start
                  && state->groups[g].span.end == best_groups[g].span.end;
            }

            if (same)
                break;
        }

        /* Save the best result so far. */
        best_groups = save_groups(safe_state, best_groups);
        if (!best_groups) {
            status = RE_ERROR_MEMORY;
            break;
        }

        best_match_pos = state->match_pos;
        best_text_pos = state->text_pos;

        if (state->max_cost == 0)
            break;

        /* Reduce the maximum permitted cost and try again. */
        state->max_cost = state->total_cost - 1;

        if (enhance_match) {
            if (state->reverse) {
                state->slice_start = state->text_pos;
                state->slice_end = state->match_pos;
            } else {
                state->slice_start = state->match_pos;
                state->slice_end = state->text_pos;
            }
        }
    }

    state->slice_start = slice_start;
    state->slice_end = slice_end;

    if (best_groups) {
        if (status == RE_ERROR_SUCCESS && state->total_cost == 0)
            /* We have a perfect match, so the previous best match. */
            discard_groups(safe_state, best_groups);
        else {
            /* Restore the previous best match. */
            status = RE_ERROR_SUCCESS;

            state->match_pos = best_match_pos;
            state->text_pos = best_text_pos;

            restore_groups(safe_state, best_groups);
        }
    }

    if (status == RE_ERROR_SUCCESS) {
        Py_ssize_t max_end_index;
        PatternObject* pattern;
        RE_GroupInfo* group_info;
        size_t g;

        /* Store the results. */
        state->lastindex = -1;
        state->lastgroup = -1;
        max_end_index = -1;

        /* Store the capture groups. */
        pattern = state->pattern;
        group_info = pattern->group_info;
        for (g = 0; g < pattern->public_group_count; g++) {
            RE_GroupSpan* span;

            span = &state->groups[g].span;
            /* The string positions are of type Py_ssize_t, so the format needs
             * to specify that.
             */
            TRACE(("group %d from %" PY_FORMAT_SIZE_T "d to %" PY_FORMAT_SIZE_T
              "d\n", g + 1, span->start, span->end))

            if (span->start >= 0 && span->end >= 0 && group_info[g].end_index >
              max_end_index) {
                max_end_index = group_info[g].end_index;
                state->lastindex = g + 1;
                if (group_info[g].has_name)
                    state->lastgroup = g + 1;
            }
        }
    }

    /* Re-acquire the GIL. */
    acquire_GIL(safe_state);

    if (status < 0 && !PyErr_Occurred())
        set_error(status, NULL);

    return status;
}

/* Gets a string from a Python object.
 *
 * If the function returns true and str_info->should_release is true then it's
 * the responsibility of the caller to release the buffer when it's no longer
 * needed.
 */
Py_LOCAL_INLINE(BOOL) get_string(PyObject* string, RE_StringInfo* str_info) {
    /* Given a Python object, return a data pointer, a length (in characters),
     * and a character size. Return FALSE if the object is not a string (or not
     * compatible).
     */
    PyBufferProcs* buffer;
    Py_ssize_t bytes;
    Py_ssize_t size;

    /* Unicode objects do not support the buffer API. So, get the data directly
     * instead.
     */
    if (PyUnicode_Check(string)) {
        /* Unicode strings doesn't always support the buffer interface. */
        str_info->characters = (void*)PyUnicode_AS_DATA(string);
        str_info->length = PyUnicode_GET_SIZE(string);
        str_info->charsize = sizeof(Py_UNICODE);
        str_info->is_unicode = TRUE;
        str_info->should_release = FALSE;
        return TRUE;
    }

    /* Get pointer to string buffer. */
#if PY_VERSION_HEX >= 0x02060000
    buffer = Py_TYPE(string)->tp_as_buffer;
    str_info->view.len = -1;
#else
    buffer = string->ob_type->tp_as_buffer;
#endif

    if (!buffer) {
        PyErr_SetString(PyExc_TypeError, "expected string or buffer");
        return FALSE;
    }

#if PY_VERSION_HEX >= 0x02060000
    if (buffer->bf_getbuffer && (*buffer->bf_getbuffer)(string,
      &str_info->view, PyBUF_SIMPLE) >= 0)
        /* It's a new-style buffer. */
        str_info->should_release = TRUE;
    else
#endif
    if (buffer->bf_getreadbuffer && buffer->bf_getsegcount &&
      buffer->bf_getsegcount(string, NULL) == 1)
        /* It's an old-style buffer. */
        str_info->should_release = FALSE;
    else {
        PyErr_SetString(PyExc_TypeError, "expected string or buffer");
        return FALSE;
    }

    /* Determine buffer size. */
#if PY_VERSION_HEX >= 0x02060000
    if (str_info->should_release) {
        /* It's a new-style buffer. */
        bytes = str_info->view.len;
        str_info->characters = str_info->view.buf;

        if (str_info->characters == NULL) {
            PyBuffer_Release(&str_info->view);
            PyErr_SetString(PyExc_ValueError, "buffer is NULL");
            return FALSE;
        }
    } else
#endif
        /* It's an old-style buffer. */
        bytes = buffer->bf_getreadbuffer(string, 0, &str_info->characters);

    if (bytes < 0) {
#if PY_VERSION_HEX >= 0x02060000
        if (str_info->should_release)
            PyBuffer_Release(&str_info->view);
#endif
        PyErr_SetString(PyExc_TypeError, "buffer has negative size");
        return FALSE;
    }

    /* Determine character size. */
    size = PyObject_Size(string);

    if (PyString_Check(string) || bytes == size)
        str_info->charsize = 1;
    else {
#if PY_VERSION_HEX >= 0x02060000
        if (str_info->should_release)
            PyBuffer_Release(&str_info->view);
#endif
        PyErr_SetString(PyExc_TypeError, "buffer size mismatch");
        return FALSE;
    }

    str_info->length = size;
    str_info->is_unicode = FALSE;

    return TRUE;
}

/* Deallocates the groups storage. */
Py_LOCAL_INLINE(void) dealloc_groups(RE_GroupData* groups, size_t group_count)
  {
    size_t g;

    if (!groups)
        return;

    for (g = 0; g < group_count; g++)
        re_dealloc(groups[g].captures);

    re_dealloc(groups);
}

/* Initialises a state object. */
Py_LOCAL_INLINE(BOOL) state_init_2(RE_State* state, PatternObject* pattern,
  PyObject* string, RE_StringInfo* str_info, Py_ssize_t start, Py_ssize_t end,
  BOOL overlapped, int concurrent, BOOL use_lock, BOOL visible_captures, BOOL
  match_all) {
    Py_ssize_t final_pos;
    int i;

    state->groups = NULL;
    state->repeats = NULL;
    state->visible_captures = visible_captures;
    state->match_all = match_all;
    state->backtrack_block.previous = NULL;
    state->backtrack_block.next = NULL;
    state->backtrack_block.capacity = RE_BACKTRACK_BLOCK_SIZE;
    state->backtrack_allocated = RE_BACKTRACK_BLOCK_SIZE;
    state->first_saved_groups = NULL;
    state->current_saved_groups = NULL;
    state->first_saved_repeats = NULL;
    state->current_saved_repeats = NULL;
    state->lock = NULL;
    state->fuzzy_guards = NULL;
    state->first_group_call_frame = NULL;
    state->current_group_call_frame = NULL;
    state->group_call_guard_list = NULL;

    /* The call guards used by recursive patterns. */
    if (pattern->call_ref_info_count > 0) {
        state->group_call_guard_list =
          (RE_GuardList*)re_alloc(pattern->call_ref_info_count *
          sizeof(RE_GuardList));
        if (!state->group_call_guard_list)
            goto error;
        memset(state->group_call_guard_list, 0, pattern->call_ref_info_count *
          sizeof(RE_GuardList));
    }

    /* The capture groups. */
    if (pattern->true_group_count) {
        size_t g;

        if (pattern->groups_storage) {
            state->groups = pattern->groups_storage;
            pattern->groups_storage = NULL;
        } else {
            state->groups = (RE_GroupData*)re_alloc(pattern->true_group_count *
              sizeof(RE_GroupData));
            if (!state->groups)
                goto error;
            memset(state->groups, 0, pattern->true_group_count *
              sizeof(RE_GroupData));

            for (g = 0; g < pattern->true_group_count; g++) {
                RE_GroupSpan* captures;

                captures = (RE_GroupSpan*)re_alloc(sizeof(RE_GroupSpan));
                if (!captures) {
                    size_t i;

                    for (i = 0; i < g; i++)
                        re_dealloc(state->groups[i].captures);

                    goto error;
                }

                state->groups[g].captures = captures;
                state->groups[g].capture_capacity = 1;
            }
        }
    }

    /* Adjust boundaries. */
    if (start < 0)
        start += str_info->length;
    if (start < 0)
        start = 0;
    else if (start > str_info->length)
        start = str_info->length;

    if (end < 0)
        end += str_info->length;
    if (end < 0)
        end = 0;
    else if (end > str_info->length)
        end = str_info->length;

    state->overlapped = overlapped;
    state->min_width = pattern->min_width;

    /* Initialise the getters and setters for the character size. */
    state->charsize = str_info->charsize;
    state->is_unicode = str_info->is_unicode;

#if PY_VERSION_HEX >= 0x02060000
    /* Are we using a buffer object? If so, we need to copy the info. */
    state->should_release = str_info->should_release;
    if (state->should_release)
        state->view = str_info->view;

#endif
    switch (state->charsize) {
    case 1:
        state->char_at = bytes1_char_at;
        state->set_char_at = bytes1_set_char_at;
        state->point_to = bytes1_point_to;
        break;
    case 2:
        state->char_at = bytes2_char_at;
        state->set_char_at = bytes2_set_char_at;
        state->point_to = bytes2_point_to;
        break;
    case 4:
        state->char_at = bytes4_char_at;
        state->set_char_at = bytes4_set_char_at;
        state->point_to = bytes4_point_to;
        break;
    default:
        goto error;
    }

    state->encoding = pattern->encoding;

    /* The state object contains a reference to the string and also a pointer
     * to its contents.
     *
     * The documentation says that the end of the slice behaves like the end of
     * the string.
     */
    state->text = str_info->characters;
    state->text_length = end;

    state->reverse = (pattern->flags & RE_FLAG_REVERSE) != 0;

    state->slice_start = start;
    state->slice_end = state->text_length;
    state->text_pos = state->reverse ? state->slice_end : state->slice_start;

    /* Point to the final newline and line separator if it's at the end of the
     * string, otherwise just -1.
     */
    state->final_newline = -1;
    state->final_line_sep = -1;
    final_pos = state->text_length - 1;
    if (final_pos >= 0) {
        Py_UCS4 ch;

        ch = state->char_at(state->text, final_pos);
        if (ch == 0x0A) {
            /* The string ends with LF. */
            state->final_newline = final_pos;
            state->final_line_sep = final_pos;

            /* Does the string end with CR/LF? */
            --final_pos;
            if (final_pos >= 0 && state->char_at(state->text, final_pos) ==
              0x0D)
                state->final_line_sep = final_pos;
        } else {
            /* The string doesn't end with LF, but it could be another kind of
             * line separator.
             */
            if (state->encoding->is_line_sep(ch))
                state->final_line_sep = final_pos;
        }
    }

    /* If the 'new' behaviour is enabled then split correctly on zero-width
     * matches.
     */
    state->zero_width = (pattern->flags & RE_FLAG_VERSION1) != 0;
    state->must_advance = FALSE;

    state->pattern = pattern;
    state->string = string;

    if (pattern->repeat_count) {
        if (pattern->repeats_storage) {
            state->repeats = pattern->repeats_storage;
            pattern->repeats_storage = NULL;
        } else {
            state->repeats = (RE_RepeatData*)re_alloc(pattern->repeat_count *
              sizeof(RE_RepeatData));
            if (!state->repeats)
                goto error;
            memset(state->repeats, 0, pattern->repeat_count *
              sizeof(RE_RepeatData));
        }
    }

    if (pattern->fuzzy_count) {
        state->fuzzy_guards = (RE_FuzzyGuards*)re_alloc(pattern->fuzzy_count *
          sizeof(RE_FuzzyGuards));
        if (!state->fuzzy_guards)
            goto error;
        memset(state->fuzzy_guards, 0, pattern->fuzzy_count *
          sizeof(RE_FuzzyGuards));
    }

    Py_INCREF(state->pattern);
    Py_INCREF(state->string);

    /* Multithreading is allowed during matching when explicitly enabled or on
     * immutable strings.
     */
    switch (concurrent) {
    case RE_CONC_NO:
        state->is_multithreaded = FALSE;
        break;
    case RE_CONC_YES:
        state->is_multithreaded = TRUE;
        break;
    default:
        state->is_multithreaded = PyUnicode_Check(string) ||
          PyString_Check(string);
        break;
    }

    /* A state struct can sometimes be shared across threads. In such
     * instances, if multithreading is enabled we need to protect the state
     * with a lock (mutex) during matching.
     */
    if (state->is_multithreaded && use_lock)
        state->lock = PyThread_allocate_lock();

    for (i = 0; i < MAX_SEARCH_POSITIONS; i++)
        state->search_positions[i].start_pos = -1;

    return TRUE;

error:
    re_dealloc(state->group_call_guard_list);
    re_dealloc(state->repeats);
    dealloc_groups(state->groups, pattern->true_group_count);
    re_dealloc(state->fuzzy_guards);
    state->repeats = NULL;
    state->groups = NULL;
    state->fuzzy_guards = NULL;
    return FALSE;
}

#if PY_VERSION_HEX >= 0x02060000
/* Releases the string's buffer, if necessary. */
Py_LOCAL_INLINE(void) release_buffer(RE_StringInfo* str_info) {
    if (str_info->should_release)
        PyBuffer_Release(&str_info->view);
}

#endif
/* Initialises a state object. */
Py_LOCAL_INLINE(BOOL) state_init(RE_State* state, PatternObject* pattern,
  PyObject* string, Py_ssize_t start, Py_ssize_t end, BOOL overlapped, int
  concurrent, BOOL use_lock, BOOL visible_captures, BOOL match_all) {
    RE_StringInfo str_info;

    /* Get the string to search or match. */
    if (!get_string(string, &str_info))
        return FALSE;

    /* If we fail to initialise the state then we need to release the buffer if
     * the string is a buffer object.
     */
    if (!state_init_2(state, pattern, string, &str_info, start, end,
      overlapped, concurrent, use_lock, visible_captures, match_all)) {
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        return FALSE;
    }

    /* The state has been initialised successfully, so now the state has the
     * responsibility of releasing the buffer if the string is a buffer object.
     */
    return TRUE;
}

/* Deallocates repeat data. */
Py_LOCAL_INLINE(void) dealloc_repeats(RE_RepeatData* repeats, Py_ssize_t
  repeat_count) {
    Py_ssize_t i;

    if (!repeats)
        return;

    for (i = 0; i < repeat_count; i++) {
        re_dealloc(repeats[i].body_guard_list.spans);
        re_dealloc(repeats[i].tail_guard_list.spans);
    }

    re_dealloc(repeats);
}

/* Deallocates fuzzy guards. */
Py_LOCAL_INLINE(void) dealloc_fuzzy_guards(RE_FuzzyGuards* guards, Py_ssize_t
  fuzzy_count) {
    Py_ssize_t i;

    if (!guards)
        return;

    for (i = 0; i < fuzzy_count; i++) {
        re_dealloc(guards[i].body_guard_list.spans);
        re_dealloc(guards[i].tail_guard_list.spans);
    }

    re_dealloc(guards);
}

/* Finalises a state object, discarding its contents. */
Py_LOCAL_INLINE(void) state_fini(RE_State* state) {
    RE_BacktrackBlock* current;
    PatternObject* pattern;
    RE_SavedGroups* saved_groups;
    RE_SavedRepeats* saved_repeats;
    RE_GroupCallFrame* frame;
    size_t i;

    /* Discard the lock (mutex) if there's one. */
    if (state->lock)
        PyThread_free_lock(state->lock);

    /* Deallocate the backtrack blocks. */
    current = state->backtrack_block.next;
    while (current) {
        RE_BacktrackBlock* next;

        next = current->next;
        re_dealloc(current);
        state->backtrack_allocated -= RE_BACKTRACK_BLOCK_SIZE;
        current = next;
    }

    pattern = state->pattern;

    saved_groups = state->first_saved_groups;
    while (saved_groups) {
        RE_SavedGroups* next;

        next = saved_groups->next;
        re_dealloc(saved_groups->spans);
        re_dealloc(saved_groups->counts);
        re_dealloc(saved_groups);
        saved_groups = next;
    }

    saved_repeats = state->first_saved_repeats;
    while (saved_repeats) {
        RE_SavedRepeats* next;

        next = saved_repeats->next;

        dealloc_repeats(saved_repeats->repeats, pattern->repeat_count);

        re_dealloc(saved_repeats);
        saved_repeats = next;
    }

    if (pattern->groups_storage)
        dealloc_groups(state->groups, pattern->true_group_count);
    else
        pattern->groups_storage = state->groups;

    if (pattern->repeats_storage)
        dealloc_repeats(state->repeats, pattern->repeat_count);
    else
        pattern->repeats_storage = state->repeats;

    frame = state->first_group_call_frame;
    while (frame) {
        RE_GroupCallFrame* next;

        next = frame->next;

        dealloc_groups(frame->groups, pattern->true_group_count);
        dealloc_repeats(frame->repeats, pattern->repeat_count);

        re_dealloc(frame);
        frame = next;
    }

    for (i = 0; i < pattern->call_ref_info_count; i++)
        re_dealloc(state->group_call_guard_list[i].spans);

    if (state->group_call_guard_list)
        re_dealloc(state->group_call_guard_list);

    if (state->fuzzy_guards)
        dealloc_fuzzy_guards(state->fuzzy_guards, pattern->fuzzy_count);

    Py_DECREF(state->pattern);
    Py_DECREF(state->string);
#if PY_VERSION_HEX >= 0x02060000

    if (state->should_release)
        PyBuffer_Release(&state->view);
#endif
}

/* Converts a string index to an integer.
 *
 * If the index is None then the default will be returned.
 */
Py_LOCAL_INLINE(Py_ssize_t) as_string_index(PyObject* obj, Py_ssize_t def) {
    Py_ssize_t value;

    if (obj == Py_None)
        return def;

    value = PyInt_AsSsize_t(obj);
    if (value != -1 || !PyErr_Occurred())
        return value;

    PyErr_Clear();

    value = PyLong_AsLong(obj);
    if (value != -1 || !PyErr_Occurred())
        return value;

    set_error(RE_ERROR_INDEX, NULL);
    return 0;
}

/* Deallocates a MatchObject. */
static void match_dealloc(PyObject* self_) {
    MatchObject* self;

    self = (MatchObject*)self_;

    Py_XDECREF(self->string);
    Py_XDECREF(self->substring);
    Py_DECREF(self->pattern);
    if (self->groups)
        re_dealloc(self->groups);
    Py_XDECREF(self->regs);
    PyObject_DEL(self);
}

/* Gets a slice from a string. */
Py_LOCAL_INLINE(PyObject*) get_slice(PyObject* string, Py_ssize_t start,
  Py_ssize_t end) {
    return PySequence_GetSlice(string, start, end);
}

/* Gets a MatchObject's group by integer index. */
Py_LOCAL_INLINE(PyObject*) match_get_group_by_index(MatchObject* self,
  Py_ssize_t index, PyObject* def) {
    RE_GroupSpan* span;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0)
        return get_slice(self->substring, self->match_start -
          self->substring_offset, self->match_end - self->substring_offset);

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    span = &self->groups[index - 1].span;

    if (span->start < 0 || span->end < 0) {
        /* Return default value if the string or group is undefined. */
        Py_INCREF(def);
        return def;
    }

    return get_slice(self->substring, span->start - self->substring_offset,
      span->end - self->substring_offset);
}

/* Gets a MatchObject's start by integer index. */
static PyObject* match_get_start_by_index(MatchObject* self, Py_ssize_t index)
  {
    RE_GroupSpan* span;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0)
        return Py_BuildValue("n", self->match_start);

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    span = &self->groups[index - 1].span;
    return Py_BuildValue("n", span->start);
}

/* Gets a MatchObject's starts by integer index. */
static PyObject* match_get_starts_by_index(MatchObject* self, Py_ssize_t index)
  {
    RE_GroupData* group;
    PyObject* result;
    PyObject* item;
    size_t i;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0) {
        result = PyList_New(1);
        if (!result)
            return NULL;

        item = Py_BuildValue("n", self->match_start);
        if (!item)
            goto error;
        PyList_SET_ITEM(result, 0, item);

        return result;
    }

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    group = &self->groups[index - 1];

    result = PyList_New(group->capture_count);
    if (!result)
        return NULL;

    for (i = 0; i < group->capture_count; i++) {
        item = Py_BuildValue("n", group->captures[i].start);
        if (!item)
            goto error;
        PyList_SET_ITEM(result, i, item);
    }

    return result;

error:
    Py_DECREF(result);
    return NULL;
}

/* Gets a MatchObject's end by integer index. */
static PyObject* match_get_end_by_index(MatchObject* self, Py_ssize_t index) {
    RE_GroupSpan* span;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0)
        return Py_BuildValue("n", self->match_end);

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    span = &self->groups[index - 1].span;
    return Py_BuildValue("n", span->end);
}

/* Gets a MatchObject's ends by integer index. */
static PyObject* match_get_ends_by_index(MatchObject* self, Py_ssize_t index) {
    RE_GroupData* group;
    PyObject* result;
    PyObject* item;
    size_t i;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0) {
        result = PyList_New(1);
        if (!result)
            return NULL;

        item = Py_BuildValue("n", self->match_end);
        if (!item)
            goto error;
        PyList_SET_ITEM(result, 0, item);

        return result;
    }

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    group = &self->groups[index - 1];

    result = PyList_New(group->capture_count);
    if (!result)
        return NULL;

    for (i = 0; i < group->capture_count; i++) {
        item = Py_BuildValue("n", group->captures[i].end);
        if (!item)
            goto error;
        PyList_SET_ITEM(result, i, item);
    }

    return result;

error:
    Py_DECREF(result);
    return NULL;
}

/* Gets a MatchObject's span by integer index. */
static PyObject* match_get_span_by_index(MatchObject* self, Py_ssize_t index) {
    RE_GroupSpan* span;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0)
        return Py_BuildValue("nn", self->match_start, self->match_end);

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    span = &self->groups[index - 1].span;
    return Py_BuildValue("nn", span->start, span->end);
}

/* Gets a MatchObject's spans by integer index. */
static PyObject* match_get_spans_by_index(MatchObject* self, Py_ssize_t index)
  {
    RE_GroupData* group;
    PyObject* result;
    PyObject* item;
    size_t i;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0) {
        result = PyList_New(1);
        if (!result)
            return NULL;

        item = Py_BuildValue("nn", self->match_start, self->match_end);
        if (!item)
            goto error;
        PyList_SET_ITEM(result, 0, item);

        return result;
    }

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    group = &self->groups[index - 1];

    result = PyList_New(group->capture_count);
    if (!result)
        return NULL;

    for (i = 0; i < group->capture_count; i++) {
        item = Py_BuildValue("nn", group->captures[i].start,
          group->captures[i].end);
        if (!item)
            goto error;
        PyList_SET_ITEM(result, i, item);
    }

    return result;

error:
    Py_DECREF(result);
    return NULL;
}

/* Gets a MatchObject's captures by integer index. */
static PyObject* match_get_captures_by_index(MatchObject* self, Py_ssize_t
  index) {
    RE_GroupData* group;
    PyObject* result;
    PyObject* slice;
    size_t i;

    if (index < 0 || index > (Py_ssize_t)self->group_count) {
        /* Raise error if we were given a bad group number. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }

    if (index == 0) {
        result = PyList_New(1);
        if (!result)
            return NULL;

        slice = get_slice(self->substring, self->match_start -
          self->substring_offset, self->match_end - self->substring_offset);
        if (!slice)
            goto error;
        PyList_SET_ITEM(result, 0, slice);

        return result;
    }

    /* Capture group indexes are 1-based (excluding group 0, which is the
     * entire matched string).
     */
    group = &self->groups[index - 1];

    result = PyList_New(group->capture_count);
    if (!result)
        return NULL;

    for (i = 0; i < group->capture_count; i++) {
        slice = get_slice(self->substring, group->captures[i].start -
          self->substring_offset, group->captures[i].end -
          self->substring_offset);
        if (!slice)
            goto error;
        PyList_SET_ITEM(result, i, slice);
    }

    return result;

error:
    Py_DECREF(result);
    return NULL;
}

/* Converts a group index to an integer. */
Py_LOCAL_INLINE(Py_ssize_t) as_group_index(PyObject* obj) {
    Py_ssize_t value;

    value = PyInt_AsSsize_t(obj);
    if (value != -1 || !PyErr_Occurred())
        return value;

    PyErr_Clear();

    value = PyLong_AsLong(obj);
    if (value != -1 || !PyErr_Occurred())
        return value;

    set_error(RE_ERROR_INDEX, NULL);
    return -1;
}

/* Gets a MatchObject's group index.
 *
 * The supplied index can be an integer or a string (group name) object.
 */
Py_LOCAL_INLINE(Py_ssize_t) match_get_group_index(MatchObject* self, PyObject*
  index, BOOL allow_neg) {
    Py_ssize_t group;

    /* Is the index an integer? */
    group = as_group_index(index);
    if (group != -1 || !PyErr_Occurred()) {
        Py_ssize_t min_group = 0;

        /* Adjust negative indices where valid and allowed. */
        if (group < 0 && allow_neg) {
            group += (Py_ssize_t)self->group_count + 1;
            min_group = 1;
        }

        if (min_group <= group && group <= (Py_ssize_t)self->group_count)
            return group;

        return -1;
    }

    /* The index might be a group name. */
    if (self->pattern->groupindex) {
        /* Look up the name. */
        PyErr_Clear();

        index = PyObject_GetItem(self->pattern->groupindex, index);
        if (index) {
            /* Check that we have an integer. */
            group = as_group_index(index);
            Py_DECREF(index);
            if (group != -1 || !PyErr_Occurred())
                return group;
        }
    }

    PyErr_Clear();
    return -1;
}

/* Gets a MatchObject's group by object index. */
Py_LOCAL_INLINE(PyObject*) match_get_group(MatchObject* self, PyObject* index,
  PyObject* def, BOOL allow_neg) {
    /* Check that the index is an integer or a string. */
    if (PyInt_Check(index) || PyLong_Check(index) || PyUnicode_Check(index) ||
      PyString_Check(index))
        return match_get_group_by_index(self, match_get_group_index(self,
          index, allow_neg), def);

    set_error(RE_ERROR_GROUP_INDEX_TYPE, index);
    return NULL;
}

/* Gets info from a MatchObject by object index. */
static PyObject* get_by_arg(MatchObject* self, PyObject* index,
  RE_GetByIndexFunc get_by_index) {
    /* Check that the index is an integer or a string. */
    if (PyInt_Check(index) || PyLong_Check(index) || PyUnicode_Check(index) ||
      PyString_Check(index))
        return get_by_index(self, match_get_group_index(self, index, FALSE));

    set_error(RE_ERROR_GROUP_INDEX_TYPE, index);
    return NULL;
}

/* MatchObject's 'group' method. */
static PyObject* match_group(MatchObject* self, PyObject* args) {
    Py_ssize_t size;
    PyObject* result;
    Py_ssize_t i;

    size = PyTuple_GET_SIZE(args);

    switch (size) {
    case 0:
        /* group() */
        result = match_get_group_by_index(self, 0, Py_None);
        break;
    case 1:
        /* group(x) */
        result = match_get_group(self, PyTuple_GET_ITEM(args, 0), Py_None,
          FALSE);
        break;
    default:
        /* group(x, y, z, ...) */
        /* Fetch multiple items. */
        result = PyTuple_New(size);
        if (!result)
            return NULL;
        for (i = 0; i < size; i++) {
            PyObject* item = match_get_group(self, PyTuple_GET_ITEM(args, i),
              Py_None, FALSE);
            if (!item) {
                Py_DECREF(result);
                return NULL;
            }
            PyTuple_SET_ITEM(result, i, item);
        }
        break;
    }
    return result;
}

/* Generic method for getting info from a MatchObject. */
static PyObject* get_from_match(MatchObject* self, PyObject* args,
  RE_GetByIndexFunc get_by_index) {
    Py_ssize_t size;
    PyObject* result;
    Py_ssize_t i;

    size = PyTuple_GET_SIZE(args);

    switch (size) {
    case 0:
        /* get() */
        result = get_by_index(self, 0);
        break;
    case 1:
        /* get(x) */
        result = get_by_arg(self, PyTuple_GET_ITEM(args, 0), get_by_index);
        break;
    default:
        /* get(x, y, z, ...) */
        /* Fetch multiple items. */
        result = PyTuple_New(size);
        if (!result)
            return NULL;
        for (i = 0; i < size; i++) {
            PyObject* item = get_by_arg(self, PyTuple_GET_ITEM(args, i),
              get_by_index);
            if (!item) {
                Py_DECREF(result);
                return NULL;
            }
            PyTuple_SET_ITEM(result, i, item);
        }
        break;
    }
    return result;
}

/* MatchObject's 'start' method. */
static PyObject* match_start(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_start_by_index);
}

/* MatchObject's 'starts' method. */
static PyObject* match_starts(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_starts_by_index);
}

/* MatchObject's 'end' method. */
static PyObject* match_end(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_end_by_index);
}

/* MatchObject's 'ends' method. */
static PyObject* match_ends(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_ends_by_index);
}

/* MatchObject's 'span' method. */
static PyObject* match_span(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_span_by_index);
}

/* MatchObject's 'spans' method. */
static PyObject* match_spans(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_spans_by_index);
}

/* MatchObject's 'captures' method. */
static PyObject* match_captures(MatchObject* self, PyObject* args) {
    return get_from_match(self, args, match_get_captures_by_index);
}

/* MatchObject's 'groups' method. */
static PyObject* match_groups(MatchObject* self, PyObject* args, PyObject*
  kwargs) {
    PyObject* result;
    size_t g;

    PyObject* def = Py_None;
    static char* kwlist[] = { "default", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O:groups", kwlist, &def))
        return NULL;

    result = PyTuple_New(self->group_count);
    if (!result)
        return NULL;

    /* Group 0 is the entire matched portion of the string. */
    for (g = 0; g < self->group_count; g++) {
        PyObject* item;
        item = match_get_group_by_index(self, g + 1, def);
        if (!item) {
            Py_DECREF(result);
            return NULL;
        }
        PyTuple_SET_ITEM(result, g, item);
    }

    return result;
}

/* MatchObject's 'groupdict' method. */
static PyObject* match_groupdict(MatchObject* self, PyObject* args, PyObject*
  kwargs) {
    PyObject* result;
    PyObject* keys;
    Py_ssize_t g;

    PyObject* def = Py_None;
    static char* kwlist[] = { "default", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "|O:groupdict", kwlist,
      &def))
        return NULL;

    result = PyDict_New();
    if (!result || !self->pattern->groupindex)
        return result;

    keys = PyMapping_Keys(self->pattern->groupindex);
    if (!keys)
        goto failed;

    for (g = 0; g < PyList_GET_SIZE(keys); g++) {
        PyObject* key;
        PyObject* value;
        int status;

        key = PyList_GET_ITEM(keys, g);
        if (!key)
            goto failed;
        value = match_get_group(self, key, def, FALSE);
        if (!value) {
            Py_DECREF(key);
            goto failed;
        }
        status = PyDict_SetItem(result, key, value);
        Py_DECREF(value);
        if (status < 0)
            goto failed;
    }

    Py_DECREF(keys);

    return result;

failed:
    Py_XDECREF(keys);
    Py_DECREF(result);
    return NULL;
}

/* MatchObject's 'capturesdict' method. */
static PyObject* match_capturesdict(MatchObject* self) {
    PyObject* result;
    PyObject* keys;
    Py_ssize_t g;

    result = PyDict_New();
    if (!result || !self->pattern->groupindex)
        return result;

    keys = PyMapping_Keys(self->pattern->groupindex);
    if (!keys)
        goto failed;

    for (g = 0; g < PyList_GET_SIZE(keys); g++) {
        PyObject* key;
        Py_ssize_t group;
        PyObject* captures;
        int status;

        key = PyList_GET_ITEM(keys, g);
        if (!key)
            goto failed;
        group = match_get_group_index(self, key, FALSE);
        if (group < 0) {
            Py_DECREF(key);
            goto failed;
        }
        captures = match_get_captures_by_index(self, group);
        if (!captures) {
            Py_DECREF(key);
            goto failed;
        }
        status = PyDict_SetItem(result, key, captures);
        Py_DECREF(captures);
        if (status < 0)
            goto failed;
    }

    Py_DECREF(keys);

    return result;

failed:
    Py_XDECREF(keys);
    Py_DECREF(result);
    return NULL;
}

/* Gets a Python object by name from a named module. */
Py_LOCAL_INLINE(PyObject*) get_object(char* module_name, char* object_name) {
    PyObject* module;
    PyObject* object;

    module = PyImport_ImportModule(module_name);
    if (!module)
        return NULL;

    object = PyObject_GetAttrString(module, object_name);
    Py_DECREF(module);

    return object;
}

/* Calls a function in a module. */
Py_LOCAL_INLINE(PyObject*) call(char* module_name, char* function_name,
  PyObject* args) {
    PyObject* function;
    PyObject* result;

    if (!args)
        return NULL;

    function = get_object(module_name, function_name);
    if (!function)
        return NULL;

    result = PyObject_CallObject(function, args);
    Py_DECREF(function);
    Py_DECREF(args);

    return result;
}

/* Gets a replacement item from the replacement list.
 *
 * The replacement item could be a string literal or a group.
 */
Py_LOCAL_INLINE(PyObject*) get_match_replacement(MatchObject* self, PyObject*
  item, Py_ssize_t group_count) {
    Py_ssize_t index;

    if (PyUnicode_Check(item) || PyString_Check(item)) {
        /* It's a literal, which can be added directly to the list. */
        Py_INCREF(item);
        return item;
    }

    /* Is it a group reference? */
    index = as_group_index(item);
    if (index == -1 && PyErr_Occurred()) {
        /* Not a group either! */
        set_error(RE_ERROR_REPLACEMENT, NULL);
        return NULL;
    }

    if (index == 0) {
        /* The entire matched portion of the string. */
        return get_slice(self->substring, self->match_start -
          self->substring_offset, self->match_end - self->substring_offset);
    } else if (index >= 1 && index <= group_count) {
        /* A group. If it didn't match then return None instead. */
        RE_GroupData* group;

        group = &self->groups[index - 1];

        if (group->capture_count > 0)
            return get_slice(self->substring, group->span.start -
              self->substring_offset, group->span.end -
              self->substring_offset);
        else {
            Py_INCREF(Py_None);
            return Py_None;
        }
    } else {
        /* No such group. */
        set_error(RE_ERROR_NO_SUCH_GROUP, NULL);
        return NULL;
    }
}

/* Adds an item to be joined. */
Py_LOCAL_INLINE(int) add_item(JoinInfo* join_info, PyObject* item) {
    PyObject* new_item;
    int status;

    if (join_info->is_unicode) {
        if (PyUnicode_Check(item)) {
            new_item = item;
            Py_INCREF(new_item);
        } else {
            new_item = PyUnicode_FromObject(item);
            if (!new_item) {
                set_error(RE_ERROR_NOT_UNICODE, item);
                return RE_ERROR_NOT_UNICODE;
            }
        }
    } else {
        if (PyString_Check(item)) {
            new_item = item;
            Py_INCREF(new_item);
        } else {
            new_item = PyUnicode_FromObject(item);
            if (!new_item) {
                set_error(RE_ERROR_NOT_STRING, item);
                return RE_ERROR_NOT_STRING;
            }
        }
    }

    /* If the list already exists then just add the item to it. */
    if (join_info->list) {
        status = PyList_Append(join_info->list, new_item);
        if (status < 0)
            goto error;

        Py_DECREF(new_item);
        return status;
    }

    /* If we already have an item then we now have 2(!) and we need to put them
     * into a list.
     */
    if (join_info->item) {
        join_info->list = PyList_New(2);
        if (!join_info->list) {
            status = RE_ERROR_MEMORY;
            goto error;
        }

        PyList_SET_ITEM(join_info->list, 0, join_info->item);
        join_info->item = NULL;

        PyList_SET_ITEM(join_info->list, 1, new_item);
        return 0;
    }

    /* This is the first item. */
    join_info->item = new_item;

    return 0;

error:
    Py_DECREF(new_item);
    Py_XDECREF(join_info->list);
    Py_XDECREF(join_info->item);
    set_error(status, NULL);
    return status;
}

/* Joins together a list of strings for pattern_subx. */
Py_LOCAL_INLINE(PyObject*) join_list_info(JoinInfo* join_info) {
    /* If the list already exists then just do the join. */
    if (join_info->list) {
        PyObject* joiner;
        PyObject* result;

        if (join_info->reversed)
            /* The list needs to be reversed before being joined. */
            PyList_Reverse(join_info->list);

        if (join_info->is_unicode)
        {
            /* Concatenate the Unicode strings. */
            joiner = PyUnicode_FromUnicode(NULL, 0);
            if (!joiner) {
                Py_DECREF(join_info->list);
                return NULL;
            }

            result = PyUnicode_Join(joiner, join_info->list);
        } else {
            joiner = PyString_FromString("");
            if (!joiner) {
                Py_DECREF(join_info->list);
                return NULL;
            }

            /* Concatenate the bytestrings. */
            result = _PyString_Join(joiner, join_info->list);
        }

        Py_DECREF(joiner);
        Py_DECREF(join_info->list);

        return result;
    }

    /* If we have only 1 item, so we'll just return it. */
    if (join_info->item)
        return join_info->item;

    /* There are no items, so return an empty string. */
    if (join_info->is_unicode)
        return PyUnicode_FromUnicode(NULL, 0);
    else
        return PyString_FromString("");
}

/* Checks whether a string replacement is a literal.
 *
 * To keep it simple we'll say that a literal is a string which can be used
 * as-is.
 *
 * Returns its length if it is a literal, otherwise -1.
 */
Py_LOCAL_INLINE(Py_ssize_t) check_replacement_string(PyObject* str_replacement,
  char special_char) {
    RE_StringInfo str_info;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    Py_ssize_t pos;

    if (!get_string(str_replacement, &str_info))
        return -1;

    switch (str_info.charsize) {
    case 1:
        char_at = bytes1_char_at;
        break;
    case 2:
        char_at = bytes2_char_at;
        break;
    case 4:
        char_at = bytes4_char_at;
        break;
    default:
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);
#endif
        return -1;
    }

    for (pos = 0; pos < str_info.length; pos++) {
        if (char_at(str_info.characters, pos) == special_char) {
#if PY_VERSION_HEX >= 0x02060000
            release_buffer(&str_info);

#endif
            return -1;
        }
    }

#if PY_VERSION_HEX >= 0x02060000
    release_buffer(&str_info);

#endif
    return str_info.length;
}

/* MatchObject's 'expand' method. */
static PyObject* match_expand(MatchObject* self, PyObject* str_template) {
    Py_ssize_t literal_length;
    PyObject* replacement;
    JoinInfo join_info;
    Py_ssize_t size;
    Py_ssize_t i;

    /* Is the template just a literal? */
    literal_length = check_replacement_string(str_template, '\\');
    if (literal_length >= 0) {
        /* It's a literal. */
        Py_INCREF(str_template);
        return str_template;
    }

    /* Hand the template to the template compiler. */
    replacement = call(RE_MODULE, "_compile_replacement_helper",
      PyTuple_Pack(2, self->pattern, str_template));
    if (!replacement)
        return NULL;

    join_info.list = NULL;
    join_info.item = NULL;
    join_info.reversed = FALSE;
    join_info.is_unicode = PyUnicode_Check(self->string);

    /* Add each part of the template to the list. */
    size = PyList_GET_SIZE(replacement);
    for (i = 0; i < size; i++) {
        PyObject* item;
        PyObject* str_item;

        item = PyList_GET_ITEM(replacement, i);
        str_item = get_match_replacement(self, item, self->group_count);
        if (!str_item)
            goto error;

        /* Add to the list. */
        if (str_item == Py_None)
            Py_DECREF(str_item);
        else {
            int status;

            status = add_item(&join_info, str_item);
            Py_DECREF(str_item);
            if (status < 0)
                goto error;
        }
    }

    Py_DECREF(replacement);

    /* Convert the list to a single string (also cleans up join_info). */
    return join_list_info(&join_info);

error:
    Py_XDECREF(join_info.list);
    Py_XDECREF(join_info.item);
    Py_DECREF(replacement);
    return NULL;
}

#if PY_VERSION_HEX >= 0x02060000
/* Gets a MatchObject's group dictionary. */
static PyObject* match_get_group_dict(MatchObject* self) {
    PyObject* result;
    PyObject* keys;
    Py_ssize_t g;

    result = PyDict_New();
    if (!result || !self->pattern->groupindex)
        return result;

    keys = PyMapping_Keys(self->pattern->groupindex);
    if (!keys)
        goto failed;

    for (g = 0; g < PyList_GET_SIZE(keys); g++) {
        int status;
        PyObject* key;
        PyObject* value;
        key = PyList_GET_ITEM(keys, g);
        if (!key)
            goto failed;
        value = match_get_group(self, key, Py_None, FALSE);
        if (!value) {
            Py_DECREF(key);
            goto failed;
        }
        status = PyDict_SetItem(result, key, value);
        Py_DECREF(value);
        if (status < 0)
            goto failed;
    }

    Py_DECREF(keys);

    return result;

failed:
    Py_XDECREF(keys);
    Py_DECREF(result);
    return NULL;
}

/* MatchObject's 'expandf' method. */
static PyObject* match_expandf(MatchObject* self, PyObject* str_template) {
    PyObject* format_func;
    PyObject* args = NULL;
    size_t g;
    PyObject* kwargs = NULL;
    PyObject* result;

    format_func = PyObject_GetAttrString(str_template, "format");
    if (!format_func)
        return NULL;

    args = PyTuple_New(self->group_count + 1);
    if (!args)
        goto error;

    for (g = 0; g < self->group_count + 1; g++)
        PyTuple_SetItem(args, g, match_get_group_by_index(self, g, Py_None));

    kwargs = match_get_group_dict(self);
    if (!kwargs)
        goto error;

    result = PyObject_Call(format_func, args, kwargs);
    Py_DECREF(kwargs);
    Py_DECREF(args);
    Py_DECREF(format_func);

    return result;

error:
    Py_XDECREF(args);
    Py_DECREF(format_func);
    return NULL;
}

#endif
Py_LOCAL_INLINE(PyObject*) make_match_copy(MatchObject* self);

/* MatchObject's '__copy__' method. */
static PyObject* match_copy(MatchObject* self, PyObject *unused) {
    return make_match_copy(self);
}

/* MatchObject's '__deepcopy__' method. */
static PyObject* match_deepcopy(MatchObject* self, PyObject* memo) {
    return make_match_copy(self);
}

/* MatchObject's 'regs' attribute. */
static PyObject* match_regs(MatchObject* self) {
    PyObject* regs;
    PyObject* item;
    size_t g;

    regs = PyTuple_New(self->group_count + 1);
    if (!regs)
        return NULL;

    item = Py_BuildValue("nn", self->match_start, self->match_end);
    if (!item) {
        Py_DECREF(regs);
        return NULL;
    }
    PyTuple_SET_ITEM(regs, 0, item);

    for (g = 0; g < self->group_count; g++) {
        RE_GroupSpan* span;

        span = &self->groups[g].span;
        item = Py_BuildValue("nn", span->start, span->end);
        if (!item) {
            Py_DECREF(regs);
            return NULL;
        }
        PyTuple_SET_ITEM(regs, g + 1, item);
    }

    Py_INCREF(regs);
    self->regs = regs;

    return regs;
}

/* MatchObject's slice method. */
Py_LOCAL_INLINE(PyObject*) match_get_group_slice(MatchObject* self, PyObject*
  slice) {
    Py_ssize_t start;
    Py_ssize_t end;
    Py_ssize_t step;
    Py_ssize_t slice_length;

    if (PySlice_GetIndicesEx((PySliceObject*)slice, self->group_count + 1,
      &start, &end, &step, &slice_length) < 0)
        return NULL;

    if (slice_length <= 0)
        return PyTuple_New(0);
    else {
        PyObject* result;
        Py_ssize_t cur;
        Py_ssize_t i;

        result = PyTuple_New(slice_length);
        if (!result)
            return NULL;

        cur = start;
        for (i = 0; i < slice_length; i++) {
            PyTuple_SetItem(result, i, match_get_group_by_index(self, cur,
              Py_None));
            cur += step;
        }

        return result;
    }
}

/* MatchObject's length method. */
static Py_ssize_t match_length(MatchObject* self) {
    return self->group_count + 1;
}

/* MatchObject's '__getitem__' method. */
static PyObject* match_getitem(MatchObject* self, PyObject* item) {
    if (PySlice_Check(item))
        return match_get_group_slice(self, item);

    return match_get_group(self, item, Py_None, TRUE);
}

/* Determines the portion of the target string which is covered by the group
 * captures.
 */
Py_LOCAL_INLINE(void) determine_target_substring(MatchObject* match,
  Py_ssize_t* slice_start, Py_ssize_t* slice_end) {
    Py_ssize_t start;
    Py_ssize_t end;
    size_t g;

    start = match->pos;
    end = match->endpos;

    for (g = 0; g < match->group_count; g++) {
        RE_GroupSpan* span;
        size_t c;

        span = &match->groups[g].span;
        if (span->start >= 0 && span->start < start)
            start = span->start;
        if (span->end >= 0 && span->end > end)
            end = span->end;

        for (c = 0; c < match->groups[g].capture_count; c++) {
            RE_GroupSpan* span;

            span = match->groups[g].captures;
            if (span->start >= 0 && span->start < start)
                start = span->start;
            if (span->end >= 0 && span->end > end)
                end = span->end;
        }
    }

    *slice_start = start;
    *slice_end = end;
}

/* MatchObject's 'detach_string' method. */
static PyObject* match_detach_string(MatchObject* self, PyObject* unused) {
    if (self->string) {
        Py_ssize_t start;
        Py_ssize_t end;
        PyObject* substring;

        determine_target_substring(self, &start, &end);

        substring = get_slice(self->string, start, end);
        if (substring) {
            Py_XDECREF(self->substring);
            self->substring = substring;
            self->substring_offset = start;

            Py_XDECREF(self->string);
            self->string = NULL;
        }
    }

    Py_INCREF(Py_None);
    return Py_None;
}

/* The documentation of a MatchObject. */
PyDoc_STRVAR(match_group_doc,
    "group([group1, ...]) --> string or tuple of strings.\n\
    Return one or more subgroups of the match.  If there is a single argument,\n\
    the result is a single string, or None if the group did not contribute to\n\
    the match; if there are multiple arguments, the result is a tuple with one\n\
    item per argument; if there are no arguments, the whole match is returned.\n\
    Group 0 is the whole match.");

PyDoc_STRVAR(match_start_doc,
    "start([group1, ...]) --> int or tuple of ints.\n\
    Return the index of the start of one or more subgroups of the match.  If\n\
    there is a single argument, the result is an index, or -1 if the group did\n\
    not contribute to the match; if there are multiple arguments, the result is\n\
    a tuple with one item per argument; if there are no arguments, the index of\n\
    the start of the whole match is returned.  Group 0 is the whole match.");

PyDoc_STRVAR(match_end_doc,
    "end([group1, ...]) --> int or tuple of ints.\n\
    Return the index of the end of one or more subgroups of the match.  If there\n\
    is a single argument, the result is an index, or -1 if the group did not\n\
    contribute to the match; if there are multiple arguments, the result is a\n\
    tuple with one item per argument; if there are no arguments, the index of\n\
    the end of the whole match is returned.  Group 0 is the whole match.");

PyDoc_STRVAR(match_span_doc,
    "span([group1, ...]) --> 2-tuple of int or tuple of 2-tuple of ints.\n\
    Return the span (a 2-tuple of the indices of the start and end) of one or\n\
    more subgroups of the match.  If there is a single argument, the result is a\n\
    span, or (-1, -1) if the group did not contribute to the match; if there are\n\
    multiple arguments, the result is a tuple with one item per argument; if\n\
    there are no arguments, the span of the whole match is returned.  Group 0 is\n\
    the whole match.");

PyDoc_STRVAR(match_groups_doc,
    "groups(default=None) --> tuple of strings.\n\
    Return a tuple containing all the subgroups of the match.  The argument is\n\
    the default for groups that did not participate in the match.");

PyDoc_STRVAR(match_groupdict_doc,
    "groupdict(default=None) --> dict.\n\
    Return a dictionary containing all the named subgroups of the match, keyed\n\
    by the subgroup name.  The argument is the value to be given for groups that\n\
    did not participate in the match.");

PyDoc_STRVAR(match_capturesdict_doc,
    "capturesdict() --> dict.\n\
    Return a dictionary containing the captures of all the named subgroups of the\n\
    match, keyed by the subgroup name.");

PyDoc_STRVAR(match_expand_doc,
    "expand(template) --> string.\n\
    Return the string obtained by doing backslash substitution on the template,\n\
    as done by the sub() method.");

#if PY_VERSION_HEX >= 0x02060000
PyDoc_STRVAR(match_expandf_doc,
    "expandf(format) --> string.\n\
    Return the string obtained by using the format, as done by the subf()\n\
    method.");

#endif
PyDoc_STRVAR(match_captures_doc,
    "captures([group1, ...]) --> list of strings or tuple of list of strings.\n\
    Return the captures of one or more subgroups of the match.  If there is a\n\
    single argument, the result is a list of strings; if there are multiple\n\
    arguments, the result is a tuple of lists with one item per argument; if\n\
    there are no arguments, the captures of the whole match is returned.  Group\n\
    0 is the whole match.");

PyDoc_STRVAR(match_starts_doc,
    "starts([group1, ...]) --> list of ints or tuple of list of ints.\n\
    Return the indices of the starts of the captures of one or more subgroups of\n\
    the match.  If there is a single argument, the result is a list of indices;\n\
    if there are multiple arguments, the result is a tuple of lists with one\n\
    item per argument; if there are no arguments, the indices of the starts of\n\
    the captures of the whole match is returned.  Group 0 is the whole match.");

PyDoc_STRVAR(match_ends_doc,
    "ends([group1, ...]) --> list of ints or tuple of list of ints.\n\
    Return the indices of the ends of the captures of one or more subgroups of\n\
    the match.  If there is a single argument, the result is a list of indices;\n\
    if there are multiple arguments, the result is a tuple of lists with one\n\
    item per argument; if there are no arguments, the indices of the ends of the\n\
    captures of the whole match is returned.  Group 0 is the whole match.");

PyDoc_STRVAR(match_spans_doc,
    "spans([group1, ...]) --> list of 2-tuple of ints or tuple of list of 2-tuple of ints.\n\
    Return the spans (a 2-tuple of the indices of the start and end) of the\n\
    captures of one or more subgroups of the match.  If there is a single\n\
    argument, the result is a list of spans; if there are multiple arguments,\n\
    the result is a tuple of lists with one item per argument; if there are no\n\
    arguments, the spans of the captures of the whole match is returned.  Group\n\
    0 is the whole match.");

PyDoc_STRVAR(match_detach_string_doc,
    "detach_string()\n\
    Detaches the target string from the match object. The 'string' attribute\n\
    will become None.");

/* MatchObject's methods. */
static PyMethodDef match_methods[] = {
    {"group", (PyCFunction)match_group, METH_VARARGS, match_group_doc},
    {"start", (PyCFunction)match_start, METH_VARARGS, match_start_doc},
    {"end", (PyCFunction)match_end, METH_VARARGS, match_end_doc},
    {"span", (PyCFunction)match_span, METH_VARARGS, match_span_doc},
    {"groups", (PyCFunction)match_groups, METH_VARARGS|METH_KEYWORDS,
      match_groups_doc},
    {"groupdict", (PyCFunction)match_groupdict, METH_VARARGS|METH_KEYWORDS,
      match_groupdict_doc},
    {"capturesdict", (PyCFunction)match_capturesdict, METH_NOARGS,
      match_capturesdict_doc},
    {"expand", (PyCFunction)match_expand, METH_O, match_expand_doc},
#if PY_VERSION_HEX >= 0x02060000
    {"expandf", (PyCFunction)match_expandf, METH_O, match_expandf_doc},
#endif
    {"captures", (PyCFunction)match_captures, METH_VARARGS,
      match_captures_doc},
    {"starts", (PyCFunction)match_starts, METH_VARARGS, match_starts_doc},
    {"ends", (PyCFunction)match_ends, METH_VARARGS, match_ends_doc},
    {"spans", (PyCFunction)match_spans, METH_VARARGS, match_spans_doc},
    {"detach_string", (PyCFunction)match_detach_string, METH_NOARGS,
      match_detach_string_doc},
    {"__copy__", (PyCFunction)match_copy, METH_NOARGS},
    {"__deepcopy__", (PyCFunction)match_deepcopy, METH_O},
    {"__getitem__", (PyCFunction)match_getitem, METH_O|METH_COEXIST},
    {NULL, NULL}
};

PyDoc_STRVAR(match_doc, "Match object");

/* MatchObject's 'lastindex' attribute. */
static PyObject* match_lastindex(PyObject* self_) {
    MatchObject* self;

    self = (MatchObject*)self_;

    if (self->lastindex >= 0)
        return Py_BuildValue("n", self->lastindex);

    Py_INCREF(Py_None);
    return Py_None;
}

/* MatchObject's 'lastgroup' attribute. */
static PyObject* match_lastgroup(PyObject* self_) {
    MatchObject* self;

    self = (MatchObject*)self_;

    if (self->pattern->indexgroup && self->lastgroup >= 0) {
        PyObject* index = Py_BuildValue("n", self->lastgroup);
        PyObject* result = PyDict_GetItem(self->pattern->indexgroup, index);
        Py_DECREF(index);
        if (result) {
            Py_INCREF(result);
            return result;
        }
        PyErr_Clear();
    }

    Py_INCREF(Py_None);
    return Py_None;
}

/* MatchObject's 'string' attribute. */
static PyObject* match_string(PyObject* self_) {
    MatchObject* self;

    self = (MatchObject*)self_;

    if (self->string) {
        Py_INCREF(self->string);
        return self->string;
    } else {
        Py_INCREF(Py_None);
        return Py_None;
    }
}

static PyGetSetDef match_getset[] = {
    {"lastindex", (getter)match_lastindex, (setter)NULL,
      "The group number of the last matched capturing group, or None."},
    {"lastgroup", (getter)match_lastgroup, (setter)NULL,
      "The name of the last matched capturing group, or None."},
    {"regs", (getter)match_regs, (setter)NULL,
      "A tuple of the spans of the capturing groups."},
    {"string", (getter)match_string, (setter)NULL,
      "The string that was searched, or None if it has been detached."},
    {NULL}  /* Sentinel */
};

static PyMemberDef match_members[] = {
    {"re", T_OBJECT, offsetof(MatchObject, pattern), READONLY,
      "The regex object that produced this match object."},
    {"pos", T_PYSSIZET, offsetof(MatchObject, pos), READONLY,
      "The position at which the regex engine starting searching."},
    {"endpos", T_PYSSIZET, offsetof(MatchObject, endpos), READONLY,
      "The final position beyond which the regex engine won't search."},
    {NULL}  /* Sentinel */
};

static PyMappingMethods match_as_mapping = {
    (lenfunc)match_length,       /* mp_length */
    (binaryfunc)match_getitem,   /* mp_subscript */
    0,                           /* mp_ass_subscript */
};

static PyTypeObject Match_Type = {
    PyObject_HEAD_INIT(NULL)
    0,
    "_" RE_MODULE "." "Match",
    sizeof(MatchObject)
};

/* Copies the groups. */
Py_LOCAL_INLINE(RE_GroupData*) copy_groups(RE_GroupData* groups, Py_ssize_t
  group_count) {
    Py_ssize_t span_count;
    Py_ssize_t g;
    RE_GroupData* groups_copy;
    RE_GroupSpan* spans_copy;
    Py_ssize_t offset;

    /* Calculate the total size of the group info. */
    span_count = 0;
    for (g = 0; g < group_count; g++)
        span_count += groups[g].capture_count;

    /* Allocate the storage for the group info in a single block. */
    groups_copy = (RE_GroupData*)re_alloc(group_count * sizeof(RE_GroupData) +
      span_count * sizeof(RE_GroupSpan));
    if (!groups_copy)
        return NULL;

    /* The storage for the spans comes after the other group info. */
    spans_copy = (RE_GroupSpan*)&groups_copy[group_count];

    /* There's no need to initialise the spans info. */
    memset(groups_copy, 0, group_count * sizeof(RE_GroupData));

    offset = 0;
    for (g = 0; g < group_count; g++) {
        RE_GroupData* orig;
        RE_GroupData* copy;

        orig = &groups[g];
        copy = &groups_copy[g];
        copy->span = orig->span;

        copy->captures = &spans_copy[offset];
        offset += orig->capture_count;

        if (orig->capture_count > 0) {
            Py_MEMCPY(copy->captures, orig->captures, orig->capture_count *
              sizeof(RE_GroupSpan));
            copy->capture_capacity = orig->capture_count;
            copy->capture_count = orig->capture_count;
        }
    }

    return groups_copy;
}

/* Makes a copy of a MatchObject. */
Py_LOCAL_INLINE(PyObject*) make_match_copy(MatchObject* self) {
    MatchObject* match;

    if (!self->string) {
        /* The target string has been detached, so the MatchObject is now
         * immutable.
         */
        Py_INCREF(self);
        return (PyObject*)self;
    }

    /* Create a MatchObject. */
    match = PyObject_NEW(MatchObject, &Match_Type);
    if (!match)
        return NULL;

    match->string = self->string;
    match->substring = self->substring;
    match->substring_offset = self->substring_offset;
    match->pattern = self->pattern;
    match->regs = self->regs;
    Py_INCREF(match->string);
    Py_INCREF(match->substring);
    Py_INCREF(match->pattern);

    /* Copy the groups to the MatchObject. */
    if (self->group_count > 0) {
        match->groups = copy_groups(self->groups, self->group_count);
        if (!match->groups) {
            Py_DECREF(match);
            return NULL;
        }
    } else
        match->groups = NULL;

    match->group_count = self->group_count;

    match->pos = self->pos;
    match->endpos = self->endpos;

    match->match_start = self->match_start;
    match->match_end = self->match_end;

    match->lastindex = match->lastindex;
    match->lastgroup = match->lastgroup;

    return (PyObject*)match;
}

/* Creates a new MatchObject. */
Py_LOCAL_INLINE(PyObject*) pattern_new_match(PatternObject* pattern, RE_State*
  state, int status) {
    /* Create MatchObject (from state object). */
    if (status > 0) {
        MatchObject* match;

        /* Create a MatchObject. */
        match = PyObject_NEW(MatchObject, &Match_Type);
        if (!match)
            return NULL;

        match->string = state->string;
        match->substring = state->string;
        match->substring_offset = 0;
        match->pattern = pattern;
        match->regs = NULL;
        Py_INCREF(match->string);
        Py_INCREF(match->substring);
        Py_INCREF(match->pattern);

        /* Copy the groups to the MatchObject. */
        if (pattern->public_group_count > 0) {
            match->groups = copy_groups(state->groups,
              pattern->public_group_count);
            if (!match->groups) {
                Py_DECREF(match);
                return NULL;
            }
        } else
            match->groups = NULL;

        match->group_count = pattern->public_group_count;

        match->pos = state->slice_start;
        match->endpos = state->slice_end;

        if (state->reverse) {
            match->match_start = state->text_pos;
            match->match_end = state->match_pos;
        } else {
            match->match_start = state->match_pos;
            match->match_end = state->text_pos;
        }

        match->lastindex = state->lastindex;
        match->lastgroup = state->lastgroup;

        return (PyObject*)match;
    } else if (status == 0) {
        /* No match. */
        Py_INCREF(Py_None);
        return Py_None;
    } else {
        /* Internal error. */
        set_error(status, NULL);
        return NULL;
    }
}

/* Gets the text of a capture group from a state. */
Py_LOCAL_INLINE(PyObject*) state_get_group(RE_State* state, Py_ssize_t index,
  PyObject* string, BOOL empty) {
    RE_GroupData* group;
    Py_ssize_t start;
    Py_ssize_t end;

    group = &state->groups[index - 1];

    if (string != Py_None && index >= 1 && index <=
      (Py_ssize_t)state->pattern->public_group_count && group->capture_count >
      0) {
        start = group->span.start;
        end = group->span.end;
    } else {
        if (empty)
            /* Want an empty string. */
            start = end = 0;
        else {
            Py_INCREF(Py_None);
            return Py_None;
        }
    }

    return get_slice(string, start, end);
}

/* Acquires the lock (mutex) on the state if there's one.
 *
 * It also increments the owner's refcount just to ensure that it won't be
 * destroyed by another thread.
 */
Py_LOCAL_INLINE(void) acquire_state_lock(PyObject* owner, RE_SafeState*
  safe_state) {
    RE_State* state;

    state = safe_state->re_state;

    if (state->lock) {
        /* In order to avoid deadlock we need to release the GIL while trying
         * to acquire the lock.
         */
        Py_INCREF(owner);
        if (!PyThread_acquire_lock(state->lock, 0)) {
            release_GIL(safe_state);
            PyThread_acquire_lock(state->lock, 1);
            acquire_GIL(safe_state);
        }
    }
}

/* Releases the lock (mutex) on the state if there's one.
 *
 * It also decrements the owner's refcount, which was incremented when the lock
 * was acquired.
 */
Py_LOCAL_INLINE(void) release_state_lock(PyObject* owner, RE_SafeState*
  safe_state) {
    RE_State* state;

    state = safe_state->re_state;

    if (state->lock) {
        PyThread_release_lock(state->lock);
        Py_DECREF(owner);
    }
}

/* Implements the functionality of ScanObject's search and match methods. */
static PyObject* scanner_search_or_match(ScannerObject* self, BOOL search) {
    RE_State* state;
    RE_SafeState safe_state;
    PyObject* match;

    state = &self->state;

    /* Initialise the "safe state" structure. */
    safe_state.re_state = state;
    safe_state.thread_state = NULL;

    /* Acquire the state lock in case we're sharing the scanner object across
     * threads.
     */
    acquire_state_lock((PyObject*)self, &safe_state);

    if (self->status == 0) {
        /* No match. */
        release_state_lock((PyObject*)self, &safe_state);
        Py_INCREF(Py_None);
        return Py_None;
    } else if (self->status < 0) {
        /* Internal error. */
        release_state_lock((PyObject*)self, &safe_state);
        set_error(self->status, NULL);
        return NULL;
    }

    /* Look for another match. */
    self->status = do_match(&safe_state, search);
    if (self->status < 0) {
        /* Internal error. */
        release_state_lock((PyObject*)self, &safe_state);
        return NULL;
    }

    /* Create the match object. */
    match = pattern_new_match(self->pattern, state, self->status);

    if (search && state->overlapped) {
        /* Advance one character. */
        Py_ssize_t step;

        step = state->reverse ? -1 : 1;
        state->text_pos = state->match_pos + step;
        state->must_advance = FALSE;
    } else
        /* Continue from where we left off, but don't allow 2 contiguous
         * zero-width matches.
         */
        state->must_advance = state->text_pos == state->match_pos;

    /* Release the state lock. */
    release_state_lock((PyObject*)self, &safe_state);

    return match;
}

/* ScannerObject's 'match' method. */
static PyObject* scanner_match(ScannerObject* self, PyObject* unused) {
    return scanner_search_or_match(self, FALSE);
}

/* ScannerObject's 'search' method. */
static PyObject* scanner_search(ScannerObject* self, PyObject *unused) {
    return scanner_search_or_match(self, TRUE);
}

/* ScannerObject's 'next' method. */
static PyObject* scanner_next(PyObject* self) {
    PyObject* match;

    match = scanner_search((ScannerObject*)self, NULL);

    if (match == Py_None) {
        /* No match. */
        Py_DECREF(Py_None);
        PyErr_SetNone(PyExc_StopIteration);
        return NULL;
    }

    return match;
}

/* Returns an iterator for a ScannerObject.
 *
 * The iterator is actually the ScannerObject itself.
 */
static PyObject* scanner_iter(PyObject* self) {
    Py_INCREF(self);
    return self;
}

/* Gets the next result from a scanner iterator. */
static PyObject* scanner_iternext(PyObject* self) {
    PyObject* match;

    match = scanner_search((ScannerObject*)self, NULL);

    if (match == Py_None) {
        /* No match. */
        Py_DECREF(match);
        return NULL;
    }

    return match;
}

/* Makes a copy of a ScannerObject.
 *
 * It actually doesn't make a copy, just returns the original object.
 */
Py_LOCAL_INLINE(PyObject*) make_scanner_copy(ScannerObject* self) {
    Py_INCREF(self);
    return (PyObject*)self;
}

/* ScannerObject's '__copy__' method. */
static PyObject* scanner_copy(ScannerObject* self, PyObject *unused) {
    return make_scanner_copy(self);
}

/* ScannerObject's '__deepcopy__' method. */
static PyObject* scanner_deepcopy(ScannerObject* self, PyObject* memo) {
    return make_scanner_copy(self);
}

/* The documentation of a ScannerObject. */
PyDoc_STRVAR(scanner_match_doc,
    "match() --> MatchObject or None.\n\
    Match at the current position in the string.");

PyDoc_STRVAR(scanner_search_doc,
    "search() --> MatchObject or None.\n\
    Search from the current position in the string.");

/* ScannerObject's methods. */
static PyMethodDef scanner_methods[] = {
    {"next", (PyCFunction)scanner_next, METH_NOARGS},
    {"match", (PyCFunction)scanner_match, METH_NOARGS, scanner_match_doc},
    {"search", (PyCFunction)scanner_search, METH_NOARGS, scanner_search_doc},
    {"__copy__", (PyCFunction)scanner_copy, METH_NOARGS},
    {"__deepcopy__", (PyCFunction)scanner_deepcopy, METH_O},
    {NULL, NULL}
};

PyDoc_STRVAR(scanner_doc, "Scanner object");

/* Deallocates a ScannerObject. */
static void scanner_dealloc(PyObject* self_) {
    ScannerObject* self;

    self = (ScannerObject*)self_;

    state_fini(&self->state);
    Py_DECREF(self->pattern);
    PyObject_DEL(self);
}

static PyMemberDef scanner_members[] = {
    {"pattern", T_OBJECT, offsetof(ScannerObject, pattern), READONLY,
      "The regex object that produced this scanner object."},
    {NULL}  /* Sentinel */
};

static PyTypeObject Scanner_Type = {
    PyObject_HEAD_INIT(NULL)
    0,
    "_" RE_MODULE "." "Scanner",
    sizeof(ScannerObject)
};

/* Decodes a 'concurrent' argument. */
Py_LOCAL_INLINE(int) decode_concurrent(PyObject* concurrent) {
    Py_ssize_t value;

    if (concurrent == Py_None)
        return RE_CONC_DEFAULT;

    value = PyLong_AsLong(concurrent);
    if (value == -1 && PyErr_Occurred()) {
        set_error(RE_ERROR_CONCURRENT, NULL);
        return -1;
    }

    return value ? RE_CONC_YES : RE_CONC_NO;
}

/* Creates a new ScannerObject. */
static PyObject* pattern_scanner(PatternObject* pattern, PyObject* args,
  PyObject* kwargs) {
    /* Create search state object. */
    ScannerObject* self;
    Py_ssize_t start;
    Py_ssize_t end;
    int conc;

    PyObject* string;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    Py_ssize_t overlapped = FALSE;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "string", "pos", "endpos", "overlapped",
      "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOnO:scanner", kwlist,
      &string, &pos, &endpos, &overlapped, &concurrent))
        return NULL;

    start = as_string_index(pos, 0);
    if (start == -1 && PyErr_Occurred())
        return NULL;

    end = as_string_index(endpos, PY_SSIZE_T_MAX);
    if (end == -1 && PyErr_Occurred())
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    /* Create a scanner object. */
    self = PyObject_NEW(ScannerObject, &Scanner_Type);
    if (!self)
        return NULL;

    self->pattern = pattern;
    Py_INCREF(self->pattern);

    /* The MatchObject, and therefore repeated captures, will be visible. */
    if (!state_init(&self->state, pattern, string, start, end, overlapped != 0,
      conc, TRUE, TRUE, FALSE)) {
        PyObject_DEL(self);
        return NULL;
    }

    self->status = 1;

    return (PyObject*) self;
}

/* Performs the split for the SplitterObject. */
static PyObject* next_split_part(SplitterObject* self) {
    RE_State* state;
    RE_SafeState safe_state;
    PyObject* result = NULL; /* Initialise to stop compiler warning. */

    state = &self->state;

    /* Initialise the "safe state" structure. */
    safe_state.re_state = state;
    safe_state.thread_state = NULL;

    /* Acquire the state lock in case we're sharing the splitter object across
     * threads.
     */
    acquire_state_lock((PyObject*)self, &safe_state);

    if (self->status == 0) {
        /* Finished. */
        release_state_lock((PyObject*)self, &safe_state);
        result = Py_False;
        Py_INCREF(result);
        return result;
    } else if (self->status < 0) {
        /* Internal error. */
        release_state_lock((PyObject*)self, &safe_state);
        set_error(self->status, NULL);
        return NULL;
    }

    if (self->index == 0) {
        if (self->split_count < self->maxsplit) {
            Py_ssize_t step;
            Py_ssize_t end_pos;

            if (state->reverse) {
                step = -1;
                end_pos = state->slice_start;
            } else {
                step = 1;
                end_pos = state->slice_end;
            }

retry:
            self->status = do_match(&safe_state, TRUE);
            if (self->status < 0)
                goto error;

            if (self->status == RE_ERROR_SUCCESS) {
                if (!state->zero_width) {
                    /* The current behaviour is to advance one character if the
                     * split was zero-width. Unfortunately, this can give an
                     * incorrect result. GvR wants this behaviour to be
                     * retained so as not to break any existing software which
                     * might rely on it. The correct behaviour is enabled by
                     * setting the 'new' flag.
                     */
                     if (state->text_pos == state->match_pos) {
                         if (self->last_pos == end_pos)
                             goto no_match;

                         /* Advance one character. */
                         state->text_pos += step;
                         state->must_advance = FALSE;
                         goto retry;
                     }
                }

                ++self->split_count;

                /* Get segment before this match. */
                if (state->reverse)
                    result = get_slice(state->string, state->match_pos,
                      self->last_pos);
                else
                    result = get_slice(state->string, self->last_pos,
                      state->match_pos);
                if (!result)
                    goto error;

                self->last_pos = state->text_pos;

                /* The correct behaviour is to reject a zero-width match just
                 * after a split point. The current behaviour is to advance one
                 * character if the match was zero-width. Unfortunately, this
                 * can give an incorrect result. GvR wants this behaviour to be
                 * retained so as not to break any existing software which
                 * might rely on it. The correct behaviour is enabled by
                 * setting the 'new' flag.
                 */
                if (state->zero_width)
                    /* Continue from where we left off, but don't allow a
                     * contiguous zero-width match.
                     */
                    state->must_advance = TRUE;
                else {
                    if (state->text_pos == state->match_pos)
                        /* Advance one character. */
                        state->text_pos += step;

                    state->must_advance = FALSE;
                }
            }
        } else
            goto no_match;

        if (self->status == RE_ERROR_FAILURE) {
no_match:
            /* Get segment following last match (even if empty). */
            if (state->reverse)
                result = get_slice(state->string, 0, self->last_pos);
            else
                result = get_slice(state->string, self->last_pos,
                  state->text_length);
            if (!result)
                goto error;
        }
    } else {
        /* Add group. */
        result = state_get_group(state, self->index, state->string, FALSE);
        if (!result)
            goto error;
    }

    ++self->index;
    if (self->index > (Py_ssize_t)state->pattern->public_group_count)
        self->index = 0;

    /* Release the state lock. */
    release_state_lock((PyObject*)self, &safe_state);

    return result;

error:
    /* Release the state lock. */
    release_state_lock((PyObject*)self, &safe_state);

    return NULL;
}

/* SplitterObject's 'split' method. */
static PyObject* splitter_split(SplitterObject* self, PyObject *unused) {
    PyObject* result;

    result = next_split_part(self);

    if (result == Py_False) {
        /* The sentinel. */
        Py_DECREF(Py_False);
        Py_INCREF(Py_None);
        return Py_None;
    }

    return result;
}

/* SplitterObject's 'next' method. */
static PyObject* splitter_next(PyObject* self) {
    PyObject* result;

    result = next_split_part((SplitterObject*)self);

    if (result == Py_False) {
        /* No match. */
        Py_DECREF(Py_False);
        PyErr_SetNone(PyExc_StopIteration);
        return NULL;
    }

    return result;
}

/* Returns an iterator for a SplitterObject.
 *
 * The iterator is actually the SplitterObject itself.
 */
static PyObject* splitter_iter(PyObject* self) {
    Py_INCREF(self);
    return self;
}

/* Gets the next result from a splitter iterator. */
static PyObject* splitter_iternext(PyObject* self) {
    PyObject* result;

    result = next_split_part((SplitterObject*)self);

    if (result == Py_False) {
        /* No match. */
        Py_DECREF(result);
        return NULL;
    }

    return result;
}

/* Makes a copy of a SplitterObject.
 *
 * It actually doesn't make a copy, just returns the original object.
 */
Py_LOCAL_INLINE(PyObject*) make_splitter_copy(SplitterObject* self) {
    Py_INCREF(self);
    return (PyObject*)self;
}

/* SplitterObject's '__copy__' method. */
static PyObject* splitter_copy(SplitterObject* self, PyObject *unused) {
    return make_splitter_copy(self);
}

/* SplitterObject's '__deepcopy__' method. */
static PyObject* splitter_deepcopy(SplitterObject* self, PyObject* memo) {
    return make_splitter_copy(self);
}

/* The documentation of a SplitterObject. */
PyDoc_STRVAR(splitter_split_doc,
    "split() --> string or None.\n\
    Return the next part of the split string.");

/* SplitterObject's methods. */
static PyMethodDef splitter_methods[] = {
    {"next", (PyCFunction)splitter_next, METH_NOARGS},
    {"split", (PyCFunction)splitter_split, METH_NOARGS, splitter_split_doc},
    {"__copy__", (PyCFunction)splitter_copy, METH_NOARGS},
    {"__deepcopy__", (PyCFunction)splitter_deepcopy, METH_O},
    {NULL, NULL}
};

PyDoc_STRVAR(splitter_doc, "Splitter object");

/* Deallocates a SplitterObject. */
static void splitter_dealloc(PyObject* self_) {
    SplitterObject* self;

    self = (SplitterObject*)self_;

    state_fini(&self->state);
    Py_DECREF(self->pattern);
    PyObject_DEL(self);
}

static PyMemberDef splitter_members[] = {
    {"pattern", T_OBJECT, offsetof(SplitterObject, pattern), READONLY,
      "The regex object that produced this splitter object."},
    {NULL}  /* Sentinel */
};

static PyTypeObject Splitter_Type = {
    PyObject_HEAD_INIT(NULL)
    0,
    "_" RE_MODULE "." "Splitter",
    sizeof(SplitterObject)
};

/* Creates a new SplitterObject. */
static PyObject* pattern_splitter(PatternObject* pattern, PyObject* args,
  PyObject* kwargs) {
    /* Create split state object. */
    int conc;
    SplitterObject* self;
    RE_State* state;

    PyObject* string;
    Py_ssize_t maxsplit = 0;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "string", "maxsplit", "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|nO:splitter", kwlist,
      &string, &maxsplit, &concurrent))
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    /* Create a splitter object. */
    self = PyObject_NEW(SplitterObject, &Splitter_Type);
    if (!self)
        return NULL;

    self->pattern = pattern;
    Py_INCREF(self->pattern);

    if (maxsplit == 0)
        maxsplit = PY_SSIZE_T_MAX;

    state = &self->state;

    /* The MatchObject, and therefore repeated captures, will not be visible.
     */
    if (!state_init(state, pattern, string, 0, PY_SSIZE_T_MAX, FALSE, conc,
      TRUE, FALSE, FALSE)) {
        PyObject_DEL(self);
        return NULL;
    }

    self->maxsplit = maxsplit;
    self->last_pos = state->reverse ? state->text_length : 0;
    self->split_count = 0;
    self->index = 0;
    self->status = 1;

    return (PyObject*) self;
}

/* Implements the functionality of PatternObject's search and match methods. */
static PyObject* pattern_search_or_match(PatternObject* self, PyObject* args,
  PyObject* kwargs, char* args_desc, BOOL search, BOOL match_all) {
    Py_ssize_t start;
    Py_ssize_t end;
    int conc;
    RE_State state;
    RE_SafeState safe_state;
    int status;
    PyObject* match;

    PyObject* string;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "string", "pos", "endpos", "concurrent", NULL };
    /* When working with a short string, such as a line from a file, the
     * relative cost of PyArg_ParseTupleAndKeywords can be significant, and
     * it's worth not using it when there are only positional arguments.
     */
    Py_ssize_t arg_count;
    if (args && !kwargs && PyTuple_CheckExact(args))
        arg_count = PyTuple_GET_SIZE(args);
    else
        arg_count = -1;

    if (1 <= arg_count && arg_count <= 4) {
        string = PyTuple_GET_ITEM(args, 0);
        if (arg_count >= 2)
            pos = PyTuple_GET_ITEM(args, 1);
        if (arg_count >= 3)
            endpos = PyTuple_GET_ITEM(args, 2);
        if (arg_count >= 4)
            concurrent = PyTuple_GET_ITEM(args, 3);
    } else if (!PyArg_ParseTupleAndKeywords(args, kwargs, args_desc, kwlist,
      &string, &pos, &endpos, &concurrent))
        return NULL;

    start = as_string_index(pos, 0);
    if (start == -1 && PyErr_Occurred())
        return NULL;

    end = as_string_index(endpos, PY_SSIZE_T_MAX);
    if (end == -1 && PyErr_Occurred())
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    /* The MatchObject, and therefore repeated captures, will be visible. */
    if (!state_init(&state, self, string, start, end, FALSE, conc, FALSE, TRUE,
      match_all))
        return NULL;

    /* Initialise the "safe state" structure. */
    safe_state.re_state = &state;
    safe_state.thread_state = NULL;

    status = do_match(&safe_state, search);
    if (status < 0) {
        state_fini(&state);
        return NULL;
    }

    /* Create the match object. */
    match = pattern_new_match(self, &state, status);

    state_fini(&state);

    return match;
}

/* PatternObject's 'match' method. */
static PyObject* pattern_match(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    return pattern_search_or_match(self, args, kwargs, "O|OOO:match", FALSE,
      FALSE);
}

/* PatternObject's 'fullmatch' method. */
static PyObject* pattern_fullmatch(PatternObject* self, PyObject* args,
  PyObject* kwargs) {
    return pattern_search_or_match(self, args, kwargs, "O|OOO:fullmatch",
      FALSE, TRUE);
}

/* PatternObject's 'search' method. */
static PyObject* pattern_search(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    return pattern_search_or_match(self, args, kwargs, "O|OOO:search", TRUE,
      FALSE);
}

/* Gets the limits of the matching. */
Py_LOCAL_INLINE(BOOL) get_limits(PyObject* pos, PyObject* endpos, Py_ssize_t
  length, Py_ssize_t* start, Py_ssize_t* end) {
    Py_ssize_t s;
    Py_ssize_t e;

    s = as_string_index(pos, 0);
    if (s == -1 && PyErr_Occurred())
        return FALSE;

    e = as_string_index(endpos, PY_SSIZE_T_MAX);
    if (e == -1 && PyErr_Occurred())
        return FALSE;

    /* Adjust boundaries. */
    if (s < 0)
        s += length;
    if (s < 0)
        s = 0;
    else if (s > length)
        s = length;

    if (e < 0)
        e += length;
    if (e < 0)
        e = 0;
    else if (e > length)
        e = length;

    *start = s;
    *end = e;

    return TRUE;
}

/* Gets a replacement item from the replacement list.
 *
 * The replacement item could be a string literal or a group.
 *
 * It can return None to represent an empty string.
 */
Py_LOCAL_INLINE(PyObject*) get_sub_replacement(PyObject* item, PyObject*
  string, RE_State* state, Py_ssize_t group_count) {
    Py_ssize_t index;

    if (PyUnicode_CheckExact(item) || PyString_CheckExact(item)) {
        /* It's a literal, which can be added directly to the list. */
        Py_INCREF(item);
        return item;
    }

    /* Is it a group reference? */
    index = as_group_index(item);
    if (index == -1 && PyErr_Occurred()) {
        /* Not a group either! */
        set_error(RE_ERROR_REPLACEMENT, NULL);
        return NULL;
    }

    if (index == 0) {
        /* The entire matched portion of the string. */
        if (state->match_pos == state->text_pos) {
            /* Return None for "". */
            Py_INCREF(Py_None);
            return Py_None;
        }

        if (state->reverse)
            return get_slice(string, state->text_pos, state->match_pos);
        else
            return get_slice(string, state->match_pos, state->text_pos);
    } else if (1 <= index && index <= group_count) {
        /* A group. */
        RE_GroupData* group;

        group = &state->groups[index - 1];

        if (group->capture_count == 0 && group->span.start != group->span.end)
          {
            /* The group didn't match or is "", so return None for "". */
            Py_INCREF(Py_None);
            return Py_None;
        }

        return get_slice(string, group->span.start, group->span.end);
    } else {
        /* No such group. */
        set_error(RE_ERROR_INVALID_GROUP_REF, NULL);
        return NULL;
    }
}

/* PatternObject's 'subx' method. */
Py_LOCAL_INLINE(PyObject*) pattern_subx(PatternObject* self, PyObject*
  str_template, PyObject* string, Py_ssize_t maxsub, int sub_type, PyObject*
  pos, PyObject* endpos, int concurrent) {
    RE_StringInfo str_info;
    Py_ssize_t start;
    Py_ssize_t end;
    BOOL is_callable = FALSE;
    BOOL is_literal = FALSE;
    BOOL is_template = FALSE;
    PyObject* replacement = NULL;
#if PY_VERSION_HEX >= 0x02060000
    BOOL is_format = FALSE;
#endif
    RE_State state;
    RE_SafeState safe_state;
    JoinInfo join_info;
    Py_ssize_t sub_count;
    Py_ssize_t last_pos;
    PyObject* item;
    Py_ssize_t end_pos;

    /* Get the string. */
    if (!get_string(string, &str_info))
        return NULL;

    /* Get the limits of the search. */
    if (!get_limits(pos, endpos, str_info.length, &start, &end)) {
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        return NULL;
    }

    /* If the pattern is too long for the string, then take a shortcut, unless
     * it's a fuzzy pattern.
     */
    if (!self->is_fuzzy && (Py_ssize_t)self->min_width > end - start) {
        PyObject* result;

        Py_INCREF(string);

        if (sub_type & RE_SUBN)
            result = Py_BuildValue("Nn", string, 0);
        else
            result = string;

#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        return result;
    }

    if (maxsub == 0)
        maxsub = PY_SSIZE_T_MAX;

    /* sub/subn takes either a function or a string template. */
    if (PyCallable_Check(str_template)) {
        /* It's callable. */
        is_callable = TRUE;

        replacement = str_template;
        Py_INCREF(replacement);
#if PY_VERSION_HEX >= 0x02060000
    } else if (sub_type & RE_SUBF) {
        /* Is it a literal format?
         *
         * To keep it simple we'll say that a literal is a string which can be
         * used as-is, so no placeholders.
         */
        Py_ssize_t literal_length;

        literal_length = check_replacement_string(str_template, '{');
        if (literal_length > 0) {
            /* It's a literal. */
            is_literal = TRUE;

            replacement = str_template;
            Py_INCREF(replacement);
        } else if (literal_length < 0) {
            /* It isn't a literal, so get the 'format' method. */
            is_format = TRUE;

            replacement = PyObject_GetAttrString(str_template, "format");
            if (!replacement) {
                release_buffer(&str_info);
                return NULL;
            }
        }
#endif
    } else {
        /* Is it a literal template?
         *
         * To keep it simple we'll say that a literal is a string which can be
         * used as-is, so no backslashes.
         */
        Py_ssize_t literal_length;

        literal_length = check_replacement_string(str_template, '\\');
        if (literal_length > 0) {
            /* It's a literal. */
            is_literal = TRUE;

            replacement = str_template;
            Py_INCREF(replacement);
        } else if (literal_length < 0 ) {
            /* It isn't a literal, so hand it over to the template compiler. */
            is_template = TRUE;

            replacement = call(RE_MODULE, "_compile_replacement_helper",
              PyTuple_Pack(2, self, str_template));
            if (!replacement) {
#if PY_VERSION_HEX >= 0x02060000
                release_buffer(&str_info);

#endif
                return NULL;
            }
        }
    }

    /* The MatchObject, and therefore repeated captures, will be visible only
     * if the replacement is callable.
     */
    if (!state_init_2(&state, self, string, &str_info, start, end, FALSE,
      concurrent, FALSE, is_callable, FALSE)) {
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        Py_XDECREF(replacement);
        return NULL;
    }

    /* Initialise the "safe state" structure. */
    safe_state.re_state = &state;
    safe_state.thread_state = NULL;

    join_info.item = NULL;
    join_info.list = NULL;
    join_info.reversed = state.reverse;
    join_info.is_unicode = PyUnicode_Check(string);

    sub_count = 0;
    last_pos = state.reverse ? state.text_length : 0;
    while (sub_count < maxsub) {
        int status;

        status = do_match(&safe_state, TRUE);
        if (status < 0)
            goto error;

        if (status == 0)
            break;

        /* Append the segment before this match. */
        if (state.match_pos != last_pos) {
            if (state.reverse)
                item = get_slice(string, state.match_pos, last_pos);
            else
                item = get_slice(string, last_pos, state.match_pos);
            if (!item)
                goto error;

            /* Add to the list. */
            status = add_item(&join_info, item);
            Py_DECREF(item);
            if (status < 0)
                goto error;
        }

        /* Add this match. */
        if (is_literal) {
            /* The replacement is a literal string. */
            status = add_item(&join_info, replacement);
            if (status < 0)
                goto error;
#if PY_VERSION_HEX >= 0x02060000
        } else if (is_format) {
            /* The replacement is a format string. */
            MatchObject* match;
            PyObject* args;
            size_t g;
            PyObject* kwargs;

            /* We need to create the arguments for the 'format' method. We'll
             * start by creating a MatchObject.
             */
            match = (MatchObject*)pattern_new_match(self, &state, 1);
            if (!match)
                goto error;

            /* The args are a tuple of the capture group matches. */
            args = PyTuple_New(state.pattern->public_group_count + 1);
            if (!args) {
                Py_DECREF(match);
                goto error;
            }

            for (g = 0; g < state.pattern->public_group_count + 1; g++)
                PyTuple_SetItem(args, g, match_get_group_by_index(match, g,
                  Py_None));

            /* The kwargs are a dict of the named capture group matches. */
            kwargs = match_get_group_dict(match);
            if (!kwargs) {
                Py_DECREF(args);
                Py_DECREF(match);
                goto error;
            }

            /* Call the 'format' method. */
            item = PyObject_Call(replacement, args, kwargs);
            Py_DECREF(kwargs);
            Py_DECREF(args);
            Py_DECREF(match);
            if (!item)
                goto error;

            /* Add the result to the list. */
            status = add_item(&join_info, item);
            Py_DECREF(item);
            if (status < 0)
                goto error;
#endif
        } else if (is_template) {
            /* The replacement is a list template. */
            Py_ssize_t size;
            Py_ssize_t i;

            /* Add each part of the template to the list. */
            size = PyList_GET_SIZE(replacement);
            for (i = 0; i < size; i++) {
                PyObject* item;
                PyObject* str_item;

                item = PyList_GET_ITEM(replacement, i);
                str_item = get_sub_replacement(item, string, &state,
                  self->public_group_count);
                if (!str_item)
                    goto error;

                /* Add the result to the list. */
                if (str_item == Py_None)
                    /* None for "". */
                    Py_DECREF(str_item);
                else {
                    status = add_item(&join_info, str_item);
                    Py_DECREF(str_item);
                    if (status < 0)
                        goto error;
                }
            }
        } else if (is_callable) {
            /* Pass a MatchObject to the replacement function. */
            PyObject* match;
            PyObject* args;

            /* We need to create a MatchObject to pass to the replacement
             * function.
             */
            match = pattern_new_match(self, &state, 1);
            if (!match)
                goto error;

            /* The args for the replacement function. */
            args = PyTuple_Pack(1, match);
            if (!args) {
                Py_DECREF(match);
                goto error;
            }

            /* Call the replacement function. */
            item = PyObject_CallObject(replacement, args);
            Py_DECREF(args);
            Py_DECREF(match);
            if (!item)
                goto error;

            /* Add the result to the list. */
            status = add_item(&join_info, item);
            Py_DECREF(item);
            if (status < 0)
                goto error;
        }

        ++sub_count;

        /* Continue from where we left off, but don't allow 2 contiguous
         * zero-width matches.
         */
        state.must_advance = state.match_pos == state.text_pos;
        last_pos = state.text_pos;
    }

    /* Get the segment following the last match. We use 'length' instead of
     * 'text_length' because the latter is truncated to 'slice_end', a
     * documented idiosyncracy of the 're' module.
     */
    end_pos = state.reverse ? 0 : str_info.length;
    if (last_pos != end_pos) {
        int status;

        /* The segment is part of the original string. */
        if (state.reverse)
            item = get_slice(string, 0, last_pos);
        else
            item = get_slice(string, last_pos, str_info.length);
        if (!item)
            goto error;
        status = add_item(&join_info, item);
        Py_DECREF(item);
        if (status < 0)
            goto error;
    }

    Py_XDECREF(replacement);

    /* Convert the list to a single string (also cleans up join_info). */
    item = join_list_info(&join_info);

    state_fini(&state);

    if (!item)
        return NULL;

    if (sub_type & RE_SUBN)
        return Py_BuildValue("Nn", item, sub_count);

    return item;

error:
    Py_XDECREF(join_info.list);
    Py_XDECREF(join_info.item);
    state_fini(&state);
    Py_XDECREF(replacement);
    return NULL;
}

/* PatternObject's 'sub' method. */
static PyObject* pattern_sub(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    int conc;

    PyObject* replacement;
    PyObject* string;
    Py_ssize_t count = 0;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "repl", "string", "count", "pos", "endpos",
      "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|nOOO:sub", kwlist,
      &replacement, &string, &count, &pos, &endpos, &concurrent))
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    return pattern_subx(self, replacement, string, count, RE_SUB, pos, endpos,
      conc);
}

#if PY_VERSION_HEX >= 0x02060000
/* PatternObject's 'subf' method. */
static PyObject* pattern_subf(PatternObject* self, PyObject* args, PyObject*
  kwargs)
 {
    int conc;

    PyObject* format;
    PyObject* string;
    Py_ssize_t count = 0;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "format", "string", "count", "pos", "endpos",
      "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|nOOO:sub", kwlist,
      &format, &string, &count, &pos, &endpos, &concurrent))
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    return pattern_subx(self, format, string, count, RE_SUBF, pos, endpos,
      conc);
}

#endif
/* PatternObject's 'subn' method. */
static PyObject* pattern_subn(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    int conc;

    PyObject* replacement;
    PyObject* string;
    Py_ssize_t count = 0;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "repl", "string", "count", "pos", "endpos",
      "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|nOOO:subn", kwlist,
      &replacement, &string, &count, &pos, &endpos, &concurrent))
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    return pattern_subx(self, replacement, string, count, RE_SUBN, pos, endpos,
      conc);
}

#if PY_VERSION_HEX >= 0x02060000
/* PatternObject's 'subfn' method. */
static PyObject* pattern_subfn(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    int conc;

    PyObject* format;
    PyObject* string;
    Py_ssize_t count = 0;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "format", "string", "count", "pos", "endpos",
      "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "OO|nOOO:subn", kwlist,
      &format, &string, &count, &pos, &endpos, &concurrent))
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    return pattern_subx(self, format, string, count, RE_SUBF | RE_SUBN, pos,
      endpos, conc);
}

#endif
/* PatternObject's 'split' method. */
static PyObject* pattern_split(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    int conc;

    RE_State state;
    RE_SafeState safe_state;
    PyObject* list;
    PyObject* item;
    int status;
    Py_ssize_t split_count;
    size_t g;
    Py_ssize_t start_pos;
    Py_ssize_t end_pos;
    Py_ssize_t step;
    Py_ssize_t last_pos;

    PyObject* string;
    Py_ssize_t maxsplit = 0;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "string", "maxsplit", "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|nO:split", kwlist,
      &string, &maxsplit, &concurrent))
        return NULL;

    if (maxsplit == 0)
        maxsplit = PY_SSIZE_T_MAX;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    /* The MatchObject, and therefore repeated captures, will not be visible.
     */
    if (!state_init(&state, self, string, 0, PY_SSIZE_T_MAX, FALSE, conc,
      FALSE, FALSE, FALSE))
        return NULL;

    /* Initialise the "safe state" structure. */
    safe_state.re_state = &state;
    safe_state.thread_state = NULL;

    list = PyList_New(0);
    if (!list) {
        state_fini(&state);
        return NULL;
    }

    split_count = 0;
    if (state.reverse) {
        start_pos = state.text_length;
        end_pos = 0;
        step = -1;
    } else {
        start_pos = 0;
        end_pos = state.text_length;
        step = 1;
    }

    last_pos = start_pos;
    while (split_count < maxsplit) {
        status = do_match(&safe_state, TRUE);
        if (status < 0)
            goto error;

        if (status == 0)
            /* No more matches. */
            break;

        if (!state.zero_width) {
            /* The current behaviour is to advance one character if the split
             * was zero-width. Unfortunately, this can give an incorrect
             * result. GvR wants this behaviour to be retained so as not to
             * break any existing software which might rely on it. The correct
             * behaviour is enabled by setting the 'new' flag.
             */
            if (state.text_pos == state.match_pos) {
                if (last_pos == end_pos)
                    break;

                /* Advance one character. */
                state.text_pos += step;
                state.must_advance = FALSE;
                continue;
            }
        }

        /* Get segment before this match. */
        if (state.reverse)
            item = get_slice(string, state.match_pos, last_pos);
        else
            item = get_slice(string, last_pos, state.match_pos);
        if (!item)
            goto error;
        status = PyList_Append(list, item);
        Py_DECREF(item);
        if (status < 0)
            goto error;

        /* Add groups (if any). */
        for (g = 1; g <= self->public_group_count; g++) {
            item = state_get_group(&state, g, string, FALSE);
            if (!item)
                goto error;
            status = PyList_Append(list, item);
            Py_DECREF(item);
            if (status < 0)
                goto error;
        }

        ++split_count;
        last_pos = state.text_pos;

        /* The correct behaviour is to reject a zero-width match just after a
         * split point. The current behaviour is to advance one character if
         * the match was zero-width. Unfortunately, this can give an incorrect
         * result. GvR wants this behaviour to be retained so as not to break
         * any existing software which might rely on it. The correct behaviour
         * is enabled by setting the 'new' flag.
         */
        if (state.zero_width)
            /* Continue from where we left off, but don't allow a contiguous
             * zero-width match.
             */
            state.must_advance = TRUE;
        else {
            if (state.text_pos == state.match_pos)
                /* Advance one character. */
                state.text_pos += step;

            state.must_advance = FALSE;
        }
    }

    /* Get segment following last match (even if empty). */
    if (state.reverse)
        item = get_slice(string, 0, last_pos);
    else
        item = get_slice(string, last_pos, state.text_length);
    if (!item)
        goto error;
    status = PyList_Append(list, item);
    Py_DECREF(item);
    if (status < 0)
        goto error;

    state_fini(&state);

    return list;

error:
    Py_DECREF(list);
    state_fini(&state);
    return NULL;
}

/* PatternObject's 'splititer' method. */
static PyObject* pattern_splititer(PatternObject* pattern, PyObject* args,
  PyObject* kwargs) {
    return pattern_splitter(pattern, args, kwargs);
}

/* PatternObject's 'findall' method. */
static PyObject* pattern_findall(PatternObject* self, PyObject* args, PyObject*
  kwargs) {
    Py_ssize_t start;
    Py_ssize_t end;
    RE_State state;
    int conc;
    RE_SafeState safe_state;
    PyObject* list;
    Py_ssize_t step;
    int status;
    size_t g;
    Py_ssize_t b;
    Py_ssize_t e;

    PyObject* string;
    PyObject* pos = Py_None;
    PyObject* endpos = Py_None;
    Py_ssize_t overlapped = FALSE;
    PyObject* concurrent = Py_None;
    static char* kwlist[] = { "string", "pos", "endpos", "overlapped",
      "concurrent", NULL };
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|OOnO:findall", kwlist,
      &string, &pos, &endpos, &overlapped, &concurrent))
        return NULL;

    start = as_string_index(pos, 0);
    if (start == -1 && PyErr_Occurred())
        return NULL;

    end = as_string_index(endpos, PY_SSIZE_T_MAX);
    if (end == -1 && PyErr_Occurred())
        return NULL;

    conc = decode_concurrent(concurrent);
    if (conc < 0)
        return NULL;

    /* The MatchObject, and therefore repeated captures, will not be visible.
     */
    if (!state_init(&state, self, string, start, end, overlapped != 0, conc,
      FALSE, FALSE, FALSE))
        return NULL;

    /* Initialise the "safe state" structure. */
    safe_state.re_state = &state;
    safe_state.thread_state = NULL;

    list = PyList_New(0);
    if (!list) {
        state_fini(&state);
        return NULL;
    }

    step = state.reverse ? -1 : 1;
    while (state.slice_start <= state.text_pos && state.text_pos <=
      state.slice_end) {
        PyObject* item;

        status = do_match(&safe_state, TRUE);
        if (status < 0)
            goto error;

        if (status == 0)
            break;

        /* Don't bother to build a MatchObject. */
        switch (self->public_group_count) {
        case 0:
            if (state.reverse) {
                b = state.text_pos;
                e = state.match_pos;
            } else {
                b = state.match_pos;
                e = state.text_pos;
            }
            item = get_slice(string, b, e);
            if (!item)
                goto error;
            break;
        case 1:
            item = state_get_group(&state, 1, string, TRUE);
            if (!item)
                goto error;
            break;
        default:
            item = PyTuple_New(self->public_group_count);
            if (!item)
                goto error;
            for (g = 0; g < self->public_group_count; g++) {
                PyObject* o = state_get_group(&state, g + 1, string, TRUE);
                if (!o) {
                    Py_DECREF(item);
                    goto error;
                }
                PyTuple_SET_ITEM(item, g, o);
            }
            break;
        }

        status = PyList_Append(list, item);
        Py_DECREF(item);
        if (status < 0)
            goto error;

        if (state.overlapped) {
            /* Advance one character. */
            state.text_pos = state.match_pos + step;
            state.must_advance = FALSE;
        } else
            /* Continue from where we left off, but don't allow 2 contiguous
             * zero-width matches.
             */
            state.must_advance = state.text_pos == state.match_pos;
    }

    state_fini(&state);

    return list;

error:
    Py_DECREF(list);
    state_fini(&state);
    return NULL;
}

/* PatternObject's 'finditer' method. */
static PyObject* pattern_finditer(PatternObject* pattern, PyObject* args,
  PyObject* kwargs) {
    return pattern_scanner(pattern, args, kwargs);
}

/* Makes a copy of a PatternObject. */
Py_LOCAL_INLINE(PyObject*) make_pattern_copy(PatternObject* self) {
    Py_INCREF(self);
    return (PyObject*)self;
}

/* PatternObject's '__copy__' method. */
static PyObject* pattern_copy(PatternObject* self, PyObject *unused) {
    return make_pattern_copy(self);
}

/* PatternObject's '__deepcopy__' method. */
static PyObject* pattern_deepcopy(PatternObject* self, PyObject* memo) {
    return make_pattern_copy(self);
}

/* The documentation of a PatternObject. */
PyDoc_STRVAR(pattern_match_doc,
    "match(string, pos=None, endpos=None, concurrent=None) --> MatchObject or None.\n\
    Match zero or more characters at the beginning of the string.");

PyDoc_STRVAR(pattern_fullmatch_doc,
    "fullmatch(string, pos=None, endpos=None, concurrent=None) --> MatchObject or None.\n\
    Match zero or more characters against all of the string.");

PyDoc_STRVAR(pattern_search_doc,
    "search(string, pos=None, endpos=None, concurrent=None) --> MatchObject or None.\n\
    Search through string looking for a match, and return a corresponding\n\
    match object instance.  Return None if no match is found.");

PyDoc_STRVAR(pattern_sub_doc,
    "sub(repl, string, count=0, flags=0, pos=None, endpos=None, concurrent=None) --> newstring\n\
    Return the string obtained by replacing the leftmost (or rightmost with a\n\
    reverse pattern) non-overlapping occurrences of pattern in string by the\n\
    replacement repl.");

#if PY_VERSION_HEX >= 0x02060000
PyDoc_STRVAR(pattern_subf_doc,
    "subf(format, string, count=0, flags=0, pos=None, endpos=None, concurrent=None) --> newstring\n\
    Return the string obtained by replacing the leftmost (or rightmost with a\n\
    reverse pattern) non-overlapping occurrences of pattern in string by the\n\
    replacement format.");

#endif
PyDoc_STRVAR(pattern_subn_doc,
    "subn(repl, string, count=0, flags=0, pos=None, endpos=None, concurrent=None) --> (newstring, number of subs)\n\
    Return the tuple (new_string, number_of_subs_made) found by replacing the\n\
    leftmost (or rightmost with a reverse pattern) non-overlapping occurrences\n\
    of pattern with the replacement repl.");

#if PY_VERSION_HEX >= 0x02060000
PyDoc_STRVAR(pattern_subfn_doc,
    "subfn(format, string, count=0, flags=0, pos=None, endpos=None, concurrent=None) --> (newstring, number of subs)\n\
    Return the tuple (new_string, number_of_subs_made) found by replacing the\n\
    leftmost (or rightmost with a reverse pattern) non-overlapping occurrences\n\
    of pattern with the replacement format.");

#endif
PyDoc_STRVAR(pattern_split_doc,
    "split(string, string, maxsplit=0, concurrent=None) --> list.\n\
    Split string by the occurrences of pattern.");

PyDoc_STRVAR(pattern_splititer_doc,
    "splititer(string, maxsplit=0, concurrent=None) --> iterator.\n\
    Return an iterator yielding the parts of a split string.");

PyDoc_STRVAR(pattern_findall_doc,
    "findall(string, pos=None, endpos=None, overlapped=False, concurrent=None) --> list.\n\
    Return a list of all matches of pattern in string.  The matches may be\n\
    overlapped if overlapped is True.");

PyDoc_STRVAR(pattern_finditer_doc,
    "finditer(string, pos=None, endpos=None, overlapped=False, concurrent=None) --> iterator.\n\
    Return an iterator over all matches for the RE pattern in string.  The\n\
    matches may be overlapped if overlapped is True.  For each match, the\n\
    iterator returns a MatchObject.");

PyDoc_STRVAR(pattern_scanner_doc,
    "scanner(string, pos=None, endpos=None, overlapped=False, concurrent=None) --> scanner.\n\
    Return an scanner for the RE pattern in string.  The matches may be overlapped\n\
    if overlapped is True.");

/* The methods of a PatternObject. */
static PyMethodDef pattern_methods[] = {
    {"match", (PyCFunction)pattern_match, METH_VARARGS|METH_KEYWORDS,
      pattern_match_doc},
    {"fullmatch", (PyCFunction)pattern_fullmatch, METH_VARARGS|METH_KEYWORDS,
      pattern_fullmatch_doc},
    {"search", (PyCFunction)pattern_search, METH_VARARGS|METH_KEYWORDS,
      pattern_search_doc},
    {"sub", (PyCFunction)pattern_sub, METH_VARARGS|METH_KEYWORDS,
      pattern_sub_doc},
#if PY_VERSION_HEX >= 0x02060000
    {"subf", (PyCFunction)pattern_subf, METH_VARARGS|METH_KEYWORDS,
      pattern_subf_doc},
#endif
    {"subn", (PyCFunction)pattern_subn, METH_VARARGS|METH_KEYWORDS,
      pattern_subn_doc},
#if PY_VERSION_HEX >= 0x02060000
    {"subfn", (PyCFunction)pattern_subfn, METH_VARARGS|METH_KEYWORDS,
      pattern_subfn_doc},
#endif
    {"split", (PyCFunction)pattern_split, METH_VARARGS|METH_KEYWORDS,
      pattern_split_doc},
    {"splititer", (PyCFunction)pattern_splititer, METH_VARARGS|METH_KEYWORDS,
      pattern_splititer_doc},
    {"findall", (PyCFunction)pattern_findall, METH_VARARGS|METH_KEYWORDS,
      pattern_findall_doc},
    {"finditer", (PyCFunction)pattern_finditer, METH_VARARGS|METH_KEYWORDS,
      pattern_finditer_doc},
    {"scanner", (PyCFunction)pattern_scanner, METH_VARARGS|METH_KEYWORDS,
      pattern_scanner_doc},
    {"__copy__", (PyCFunction)pattern_copy, METH_NOARGS},
    {"__deepcopy__", (PyCFunction)pattern_deepcopy, METH_O},
    {NULL, NULL}
};

PyDoc_STRVAR(pattern_doc, "Compiled regex object");

/* Deallocates a PatternObject. */
static void pattern_dealloc(PyObject* self_) {
    PatternObject* self;
    size_t i;

    self = (PatternObject*)self_;

    /* Discard the nodes. */
    for (i = 0; i < self->node_count; i++) {
        RE_Node* node;

        node = self->node_list[i];
        re_dealloc(node->values);
        if (node->status & RE_STATUS_STRING) {
            re_dealloc(node->string.bad_character_offset);
            re_dealloc(node->string.good_suffix_offset);
        }
        re_dealloc(node);
    }
    re_dealloc(self->node_list);

    /* Discard the group info. */
    re_dealloc(self->group_info);

    /* Discard the call_ref info. */
    re_dealloc(self->call_ref_info);

    /* Discard the repeat info. */
    re_dealloc(self->repeat_info);

    dealloc_groups(self->groups_storage, self->true_group_count);

    dealloc_repeats(self->repeats_storage, self->repeat_count);

    if (self->weakreflist)
        PyObject_ClearWeakRefs((PyObject*)self);
    Py_XDECREF(self->pattern);
    Py_XDECREF(self->groupindex);
    Py_XDECREF(self->indexgroup);
    Py_DECREF(self->named_lists);
    Py_DECREF(self->named_list_indexes);
    PyObject_DEL(self);
}

typedef struct RE_FlagName {
    char* name;
    int value;
} RE_FlagName;

/* We won't bother about the A flag in Python 2. */
static RE_FlagName flag_names[] = {
    {"B", RE_FLAG_BESTMATCH},
    {"D", RE_FLAG_DEBUG},
    {"S", RE_FLAG_DOTALL},
    {"F", RE_FLAG_FULLCASE},
    {"I", RE_FLAG_IGNORECASE},
    {"L", RE_FLAG_LOCALE},
    {"M", RE_FLAG_MULTILINE},
    {"R", RE_FLAG_REVERSE},
    {"T", RE_FLAG_TEMPLATE},
    {"U", RE_FLAG_UNICODE},
    {"X", RE_FLAG_VERBOSE},
    {"V0", RE_FLAG_VERSION0},
    {"V1", RE_FLAG_VERSION1},
    {"W", RE_FLAG_WORD},
};

/* Appends a string to a list. */
Py_LOCAL_INLINE(BOOL) append_string(PyObject* list, char* string) {
    PyObject* item;
    int status;

    item = Py_BuildValue("s", string);
    if (!item)
        return FALSE;

    status = PyList_Append(list, item);
    Py_DECREF(item);
    if (status < 0)
        return FALSE;

    return TRUE;
}

/* PatternObject's '__repr__' method. */
static PyObject* pattern_repr(PyObject* self_) {
    PatternObject* self;
    PyObject* list;
    PyObject* item;
    int status;
    int flag_count;
    Py_ssize_t i;
    PyObject *key;
    PyObject *value;
    PyObject* separator;
    PyObject* result;

    self = (PatternObject*)self_;

    list = PyList_New(0);
    if (!list)
        return NULL;

    if (!append_string(list, "regex.Regex("))
        goto error;

    item = PyObject_Repr(self->pattern);
    if (!item)
        goto error;

    status = PyList_Append(list, item);
    Py_DECREF(item);
    if (status < 0)
        goto error;

    flag_count = 0;
    for (i = 0; i < sizeof(flag_names) / sizeof(flag_names[0]); i++) {
        if (self->flags & flag_names[i].value) {
            if (flag_count == 0) {
                if (!append_string(list, ", flags="))
                    goto error;
            } else {
                if (!append_string(list, " | "))
                    goto error;
            }

            if (!append_string(list, "regex."))
                goto error;

            if (!append_string(list, flag_names[i].name))
                goto error;

            ++flag_count;
        }
    }

    i = 0;
    while (PyDict_Next(self->named_lists, &i, &key, &value)) {
        if (!append_string(list, ", "))
            goto error;

        status = PyList_Append(list, key);
        if (status < 0)
            goto error;

        item = PyObject_Repr(value);
        if (!item)
            goto error;

        if (!append_string(list, "="))
            goto error;

        status = PyList_Append(list, item);
        Py_DECREF(item);
        if (status < 0)
            goto error;
    }

    if (!append_string(list, ")"))
        goto error;

    separator = Py_BuildValue("s", "");
    if (!separator)
        goto error;

    result = PyUnicode_Join(separator, list);
    Py_DECREF(separator);

    Py_DECREF(list);

    return result;

error:
    Py_DECREF(list);
    return NULL;
}

/* PatternObject's 'groupindex' method. */
static PyObject* pattern_groupindex(PyObject* self_) {
    PatternObject* self;

    self = (PatternObject*)self_;

    return PyDict_Copy(self->groupindex);
}

static PyGetSetDef pattern_getset[] = {
    {"groupindex", (getter)pattern_groupindex, (setter)NULL,
      "A dictionary mapping group names to group numbers."},
    {NULL}  /* Sentinel */
};

static PyMemberDef pattern_members[] = {
    {"pattern", T_OBJECT, offsetof(PatternObject, pattern), READONLY,
      "The pattern string from which the regex object was compiled."},
    {"flags", T_PYSSIZET, offsetof(PatternObject, flags), READONLY,
      "The regex matching flags."},
    {"groups", T_PYSSIZET, offsetof(PatternObject, public_group_count),
      READONLY, "The number of capturing groups in the pattern."},
    {"named_lists", T_OBJECT, offsetof(PatternObject, named_lists), READONLY,
      "The named lists used by the regex."},
    {NULL}  /* Sentinel */
};

static PyTypeObject Pattern_Type = {
    PyObject_HEAD_INIT(NULL)
    0,
    "_" RE_MODULE "." "Pattern",
    sizeof(PatternObject)
};

/* Building the nodes is made simpler by allowing branches to have a single
 * exit. These need to be removed.
 */
Py_LOCAL_INLINE(void) skip_one_way_branches(PatternObject* pattern) {
    BOOL modified;

    /* If a node refers to a 1-way branch then make the former refer to the
     * latter's destination. Repeat until they're all done.
     */
    do {
        size_t i;

        modified = FALSE;

        for (i = 0; i < pattern->node_count; i++) {
            RE_Node* node;
            RE_Node* next;

            node = pattern->node_list[i];

            /* Check the first destination. */
            next = node->next_1.node;
            if (next && next->op == RE_OP_BRANCH &&
              !next->nonstring.next_2.node) {
                node->next_1.node = next->next_1.node;
                modified = TRUE;
            }

            /* Check the second destination. */
            next = node->nonstring.next_2.node;
            if (next && next->op == RE_OP_BRANCH &&
              !next->nonstring.next_2.node) {
                node->nonstring.next_2.node = next->next_1.node;
                modified = TRUE;
            }
        }
    } while (modified);

    /* The start node might be a 1-way branch. Skip over it because it'll be
     * removed. It might even be the first in a chain.
     */
    while (pattern->start_node->op == RE_OP_BRANCH &&
      !pattern->start_node->nonstring.next_2.node)
        pattern->start_node = pattern->start_node->next_1.node;
}

/* Adds guards to repeats which are followed by a reference to a group.
 *
 * Returns whether a guard was added for a node at or after the given node.
 */
Py_LOCAL_INLINE(RE_STATUS_T) add_repeat_guards(PatternObject* pattern, RE_Node*
  node) {
    RE_STATUS_T result;

    result = RE_STATUS_NEITHER;

    for (;;) {
        if (node->status & RE_STATUS_VISITED_AG)
            return node->status & (RE_STATUS_REPEAT | RE_STATUS_REF);

        switch (node->op) {
        case RE_OP_ATOMIC:
        case RE_OP_LOOKAROUND:
        {
            RE_STATUS_T body_result;
            RE_STATUS_T tail_result;
            RE_STATUS_T status;

            body_result = add_repeat_guards(pattern,
              node->nonstring.next_2.node);
            tail_result = add_repeat_guards(pattern, node->next_1.node);
            status = (RE_STATUS_T)RE_MAX(RE_MAX(result, body_result),
              tail_result);
            node->status = RE_STATUS_VISITED_AG | status;
            return status;
        }
        case RE_OP_BRANCH:
        {
            RE_STATUS_T branch_1_result;
            RE_STATUS_T branch_2_result;
            RE_STATUS_T status;

            branch_1_result = add_repeat_guards(pattern, node->next_1.node);
            branch_2_result = add_repeat_guards(pattern,
              node->nonstring.next_2.node);
            status = (RE_STATUS_T)RE_MAX(RE_MAX(result, branch_1_result),
              branch_2_result);
            node->status = RE_STATUS_VISITED_AG | status;
            return status;
        }
        case RE_OP_END_GREEDY_REPEAT:
        case RE_OP_END_LAZY_REPEAT:
            node->status |= RE_STATUS_VISITED_AG;
            return result;
        case RE_OP_GREEDY_REPEAT:
        case RE_OP_LAZY_REPEAT:
        {
            BOOL limited;
            RE_STATUS_T body_result;
            RE_STATUS_T tail_result;
            RE_RepeatInfo* repeat_info;
            RE_STATUS_T status;

            limited = node->values[2] != RE_UNLIMITED;
            if (limited)
                body_result = RE_STATUS_LIMITED;
            else
                body_result = add_repeat_guards(pattern, node->next_1.node);
            tail_result = add_repeat_guards(pattern,
              node->nonstring.next_2.node);

            repeat_info = &pattern->repeat_info[node->values[0]];
            if (body_result != RE_STATUS_REF)
                repeat_info->status |= RE_STATUS_BODY;
            if (tail_result != RE_STATUS_REF)
                repeat_info->status |= RE_STATUS_TAIL;
            if (limited)
                result = (RE_STATUS_T)RE_MAX(result, RE_STATUS_LIMITED);
            else
                result = (RE_STATUS_T)RE_MAX(result, RE_STATUS_REPEAT);
            status = (RE_STATUS_T)RE_MAX(RE_MAX(result, body_result),
              tail_result);
            node->status |= RE_STATUS_VISITED_AG | status;
            return status;
        }
        case RE_OP_GREEDY_REPEAT_ONE:
        case RE_OP_LAZY_REPEAT_ONE:
        {
            BOOL limited;
            RE_STATUS_T tail_result;
            RE_RepeatInfo* repeat_info;
            RE_STATUS_T status;

            limited = node->values[2] != RE_UNLIMITED;
            tail_result = add_repeat_guards(pattern, node->next_1.node);

            repeat_info = &pattern->repeat_info[node->values[0]];
            repeat_info->status |= RE_STATUS_BODY;
            if (tail_result != RE_STATUS_REF)
                repeat_info->status |= RE_STATUS_TAIL;
            if (limited)
                result = (RE_STATUS_T)RE_MAX(result, RE_STATUS_LIMITED);
            else
                result = (RE_STATUS_T)RE_MAX(result, RE_STATUS_REPEAT);
            status = (RE_STATUS_T)RE_MAX(RE_MAX(result, RE_STATUS_REPEAT),
              tail_result);
            node->status = RE_STATUS_VISITED_AG | status;
            return status;
        }
        case RE_OP_GROUP_EXISTS:
        {
            RE_STATUS_T branch_1_result;
            RE_STATUS_T branch_2_result;
            RE_STATUS_T status;

            branch_1_result = add_repeat_guards(pattern, node->next_1.node);
            branch_2_result = add_repeat_guards(pattern,
              node->nonstring.next_2.node);
            status = (RE_STATUS_T)RE_MAX(RE_MAX(RE_MAX(result,
              branch_1_result), branch_2_result), RE_STATUS_REF);
            node->status = RE_STATUS_VISITED_AG | status;
            return status;
        }
        case RE_OP_GROUP_CALL:
        case RE_OP_REF_GROUP:
        case RE_OP_REF_GROUP_FLD:
        case RE_OP_REF_GROUP_FLD_REV:
        case RE_OP_REF_GROUP_IGN:
        case RE_OP_REF_GROUP_IGN_REV:
        case RE_OP_REF_GROUP_REV:
            result = RE_STATUS_REF;
            node = node->next_1.node;
            break;
        case RE_OP_SUCCESS:
            node->status = RE_STATUS_VISITED_AG | result;
            return result;
        default:
            node = node->next_1.node;
            break;
        }
    }
}

/* Adds an index to a node's values unless it's already present.
 *
 * 'offset' is the offset of the index count within the values.
 */
Py_LOCAL_INLINE(BOOL) add_index(RE_Node* node, size_t offset, RE_CODE index) {
    size_t index_count;
    size_t first_index;
    size_t i;
    RE_CODE* new_values;

    if (!node)
        return TRUE;

    index_count = node->values[offset];
    first_index = offset + 1;

    /* Is the index already present? */
    for (i = 0; i < index_count; i++) {
        if (node->values[first_index + i] == index)
            return TRUE;
    }

    /* Allocate more space for the new index. */
    new_values = re_realloc(node->values, (node->value_count + 1) *
      sizeof(RE_CODE));
    if (!new_values)
        return FALSE;

    ++node->value_count;
    node->values = new_values;

    node->values[first_index + node->values[offset]++] = index;

    return TRUE;
}

/* Records the index of every repeat and fuzzy section within atomic
 * subpatterns and lookarounds.
 */
Py_LOCAL_INLINE(BOOL) record_subpattern_repeats_and_fuzzy_sections(RE_Node*
  parent_node, size_t offset, size_t repeat_count, RE_Node* node) {
    while (node) {
        if (node->status & RE_STATUS_VISITED_REP)
            return TRUE;

        node->status |= RE_STATUS_VISITED_REP;

        switch (node->op) {
        case RE_OP_ATOMIC:
            if (!record_subpattern_repeats_and_fuzzy_sections(node, 0,
              repeat_count, node->nonstring.next_2.node))
                return FALSE;
            node = node->next_1.node;
            break;
        case RE_OP_BRANCH:
            if (!record_subpattern_repeats_and_fuzzy_sections(parent_node,
              offset, repeat_count, node->next_1.node))
                return FALSE;
            node = node->nonstring.next_2.node;
            break;
        case RE_OP_END_FUZZY:
            node = node->next_1.node;
            break;
        case RE_OP_END_GREEDY_REPEAT:
        case RE_OP_END_LAZY_REPEAT:
            return TRUE;
        case RE_OP_FUZZY:
            /* Record the fuzzy index. */
            if (!add_index(parent_node, offset, (RE_CODE)repeat_count +
              node->values[0]))
                return FALSE;
            node = node->next_1.node;
            break;
        case RE_OP_GREEDY_REPEAT:
        case RE_OP_LAZY_REPEAT:
            /* Record the repeat index. */
            if (!add_index(parent_node, offset, node->values[0]))
                return FALSE;
            if (!record_subpattern_repeats_and_fuzzy_sections(parent_node,
              offset, repeat_count, node->next_1.node))
                return FALSE;
            node = node->nonstring.next_2.node;
            break;
        case RE_OP_GREEDY_REPEAT_ONE:
        case RE_OP_LAZY_REPEAT_ONE:
            /* Record the repeat index. */
            if (!add_index(parent_node, offset, node->values[0]))
                return FALSE;
            node = node->next_1.node;
            break;
        case RE_OP_GROUP_EXISTS:
            if (!record_subpattern_repeats_and_fuzzy_sections(parent_node,
              offset, repeat_count, node->next_1.node))
                return FALSE;
            node = node->nonstring.next_2.node;
            break;
        case RE_OP_LOOKAROUND:
            if (!record_subpattern_repeats_and_fuzzy_sections(node, 1,
              repeat_count, node->nonstring.next_2.node))
                return FALSE;
            node = node->next_1.node;
            break;
        default:
            node = node->next_1.node;
            break;
        }
    }

    return TRUE;
}

/* Marks nodes which are being used as used. */
Py_LOCAL_INLINE(void) use_nodes(RE_Node* node) {
    while (node && !(node->status & RE_STATUS_USED)) {
        node->status |= RE_STATUS_USED;
        if (!(node->status & RE_STATUS_STRING)) {
            if (node->nonstring.next_2.node)
                use_nodes(node->nonstring.next_2.node);
        }
        node = node->next_1.node;
    }
}

/* Discards any unused nodes.
 *
 * Optimising the nodes might result in some nodes no longer being used.
 */
Py_LOCAL_INLINE(void) discard_unused_nodes(PatternObject* pattern) {
    size_t new_count;
    size_t i;

    /* Mark the nodes which are being used. */
    use_nodes(pattern->start_node);

    for (i = 0; i < pattern->call_ref_info_capacity; i++)
        use_nodes(pattern->call_ref_info[i].node);

    new_count = 0;
    for (i = 0; i < pattern->node_count; i++) {
        RE_Node* node;

        node = pattern->node_list[i];
        if (node->status & RE_STATUS_USED)
            pattern->node_list[new_count++] = node;
        else {
            re_dealloc(node->values);
            if (node->status & RE_STATUS_STRING) {
                re_dealloc(node->string.bad_character_offset);
                re_dealloc(node->string.good_suffix_offset);
            }
            re_dealloc(node);
        }
    }

    pattern->node_count = new_count;
}

/* Marks all the group which are named. */
Py_LOCAL_INLINE(BOOL) mark_named_groups(PatternObject* pattern) {
    size_t i;

    for (i = 0; i < pattern->public_group_count; i++) {
        RE_GroupInfo* group_info;
        PyObject* index;

        group_info = &pattern->group_info[i];
        index = Py_BuildValue("n", i + 1);
        if (!index)
            return FALSE;
        group_info->has_name = (BOOL)PyDict_Contains(pattern->indexgroup,
          index);
        Py_DECREF(index);
    }

    return TRUE;
}

/* Gets the test node.
 *
 * The test node lets the matcher look ahead in the pattern, allowing it to
 * avoid the cost of housekeeping, only to find that what follows doesn't match
 * anyway.
 */
Py_LOCAL_INLINE(void) set_test_node(RE_NextNode* next) {
    RE_Node* node = next->node;
    RE_Node* test;

    next->test = node;
    next->match_next = node;
    next->match_step = 0;

    if (!node)
        return;

    test = node;
    while (test->op == RE_OP_END_GROUP || test->op == RE_OP_START_GROUP)
        test = test->next_1.node;

    next->test = test;

    if (test != node)
        return;

    switch (test->op) {
    case RE_OP_ANY:
    case RE_OP_ANY_ALL:
    case RE_OP_ANY_ALL_REV:
    case RE_OP_ANY_REV:
    case RE_OP_ANY_U:
    case RE_OP_ANY_U_REV:
    case RE_OP_BOUNDARY:
    case RE_OP_CHARACTER:
    case RE_OP_CHARACTER_IGN:
    case RE_OP_CHARACTER_IGN_REV:
    case RE_OP_CHARACTER_REV:
    case RE_OP_DEFAULT_BOUNDARY:
    case RE_OP_DEFAULT_END_OF_WORD:
    case RE_OP_DEFAULT_START_OF_WORD:
    case RE_OP_END_OF_LINE:
    case RE_OP_END_OF_LINE_U:
    case RE_OP_END_OF_STRING:
    case RE_OP_END_OF_STRING_LINE:
    case RE_OP_END_OF_STRING_LINE_U:
    case RE_OP_END_OF_WORD:
    case RE_OP_GRAPHEME_BOUNDARY:
    case RE_OP_PROPERTY:
    case RE_OP_PROPERTY_IGN:
    case RE_OP_PROPERTY_IGN_REV:
    case RE_OP_PROPERTY_REV:
    case RE_OP_RANGE:
    case RE_OP_RANGE_IGN:
    case RE_OP_RANGE_IGN_REV:
    case RE_OP_RANGE_REV:
    case RE_OP_SEARCH_ANCHOR:
    case RE_OP_SET_DIFF:
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_DIFF_IGN_REV:
    case RE_OP_SET_DIFF_REV:
    case RE_OP_SET_INTER:
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION:
    case RE_OP_SET_UNION_IGN:
    case RE_OP_SET_UNION_IGN_REV:
    case RE_OP_SET_UNION_REV:
    case RE_OP_START_OF_LINE:
    case RE_OP_START_OF_LINE_U:
    case RE_OP_START_OF_STRING:
    case RE_OP_START_OF_WORD:
    case RE_OP_STRING:
    case RE_OP_STRING_FLD:
    case RE_OP_STRING_FLD_REV:
    case RE_OP_STRING_IGN:
    case RE_OP_STRING_IGN_REV:
    case RE_OP_STRING_REV:
        next->match_next = test->next_1.node;
        next->match_step = test->step;
        break;
    case RE_OP_GREEDY_REPEAT_ONE:
    case RE_OP_LAZY_REPEAT_ONE:
        if (test->values[1] > 0)
            next->test = test;
        break;
    }
}

/* Sets the test nodes. */
Py_LOCAL_INLINE(void) set_test_nodes(PatternObject* pattern) {
    RE_Node** node_list;
    size_t i;

    node_list = pattern->node_list;
    for (i = 0; i < pattern->node_count; i++) {
        RE_Node* node;

        node = node_list[i];
        set_test_node(&node->next_1);
        if (!(node->status & RE_STATUS_STRING))
            set_test_node(&node->nonstring.next_2);
    }
}

/* Optimises the pattern. */
Py_LOCAL_INLINE(BOOL) optimise_pattern(PatternObject* pattern) {
    size_t i;

    /* Building the nodes is made simpler by allowing branches to have a single
     * exit. These need to be removed.
     */
    skip_one_way_branches(pattern);

    /* Add position guards for repeat bodies containing a reference to a group
     * or repeat tails followed at some point by a reference to a group.
     */
    add_repeat_guards(pattern, pattern->start_node);

    /* Record the index of repeats and fuzzy sections within the body of atomic
     * and lookaround nodes.
     */
    if (!record_subpattern_repeats_and_fuzzy_sections(NULL, 0,
      pattern->repeat_count, pattern->start_node))
        return FALSE;

    for (i = 0; i < pattern->call_ref_info_count; i++) {
        RE_Node* node;

        node = pattern->call_ref_info[i].node;
        if (!record_subpattern_repeats_and_fuzzy_sections(NULL, 0,
          pattern->repeat_count, node))
            return FALSE;
    }

    /* Discard any unused nodes. */
    discard_unused_nodes(pattern);

    /* Set the test nodes. */
    set_test_nodes(pattern);

    /* Mark all the group that are named. */
    if (!mark_named_groups(pattern))
        return FALSE;

    return TRUE;
}

/* Creates a new pattern node. */
Py_LOCAL_INLINE(RE_Node*) create_node(PatternObject* pattern, RE_UINT8 op,
  RE_CODE flags, Py_ssize_t step, size_t value_count) {
    RE_Node* node;

    node = (RE_Node*)re_alloc(sizeof(*node));
    if (!node)
        return NULL;
    memset(node, 0, sizeof(RE_Node));

    node->value_count = value_count;
    if (node->value_count > 0) {
        node->values = (RE_CODE*)re_alloc(node->value_count * sizeof(RE_CODE));
        if (!node->values)
            goto error;
    } else
        node->values = NULL;

    node->op = op;
    node->match = (flags & RE_POSITIVE_OP) != 0;
    node->status = (RE_STATUS_T)(flags << RE_STATUS_SHIFT);
    node->step = step;

    /* Ensure that there's enough storage to record the new node. */
    if (pattern->node_count >= pattern->node_capacity) {
        RE_Node** new_node_list;

        pattern->node_capacity *= 2;
        if (pattern->node_capacity == 0)
            pattern->node_capacity = RE_INIT_NODE_LIST_SIZE;
        new_node_list = (RE_Node**)re_realloc(pattern->node_list,
          pattern->node_capacity * sizeof(RE_Node*));
        if (!new_node_list)
            goto error;
        pattern->node_list = new_node_list;
    }

    /* Record the new node. */
    pattern->node_list[pattern->node_count++] = node;

    return node;

error:
    re_dealloc(node->values);
    re_dealloc(node);
    return NULL;
}

/* Adds a node as a next node for another node. */
Py_LOCAL_INLINE(void) add_node(RE_Node* node_1, RE_Node* node_2) {
    if (!node_1->next_1.node)
        node_1->next_1.node = node_2;
    else
        node_1->nonstring.next_2.node = node_2;
}

/* Ensures that the entry for a group's details actually exists. */
Py_LOCAL_INLINE(BOOL) ensure_group(PatternObject* pattern, RE_CODE group) {
    size_t old_capacity;
    size_t new_capacity;
    RE_GroupInfo* new_group_info;

    if (group <= pattern->true_group_count)
        /* We already have an entry for the group. */
        return TRUE;

    /* Increase the storage capacity to include the new entry if it's
     * insufficient.
     */
    old_capacity = pattern->group_info_capacity;
    new_capacity = pattern->group_info_capacity;
    while (group > new_capacity)
        new_capacity += RE_LIST_SIZE_INC;

    if (new_capacity > old_capacity) {
        new_group_info = (RE_GroupInfo*)re_realloc(pattern->group_info,
          new_capacity * sizeof(RE_GroupInfo));
        if (!new_group_info)
            return FALSE;
        memset(new_group_info + old_capacity, 0, (new_capacity - old_capacity)
          * sizeof(RE_GroupInfo));

        pattern->group_info = new_group_info;
        pattern->group_info_capacity = new_capacity;
    }

    pattern->true_group_count = group;

    return TRUE;
}

/* Records that there's a reference to a group. */
Py_LOCAL_INLINE(BOOL) record_ref_group(PatternObject* pattern, RE_CODE group) {
    if (!ensure_group(pattern, group))
        return FALSE;

    pattern->group_info[group - 1].referenced = TRUE;

    return TRUE;
}

/* Records that there's a new group. */
Py_LOCAL_INLINE(BOOL) record_group(PatternObject* pattern, RE_CODE group,
  RE_Node* node) {
    if (!ensure_group(pattern, group))
        return FALSE;

    if (group >= 1) {
        RE_GroupInfo* info;

        info = &pattern->group_info[group - 1];
        info->end_index = pattern->true_group_count;
        info->node = node;
    }

    return TRUE;
}

/* Records that a group has closed. */
Py_LOCAL_INLINE(void) record_group_end(PatternObject* pattern, RE_CODE group) {
    if (group >= 1)
        pattern->group_info[group - 1].end_index = ++pattern->group_end_index;
}

/* Ensures that the entry for a call_ref's details actually exists. */
Py_LOCAL_INLINE(BOOL) ensure_call_ref(PatternObject* pattern, RE_CODE call_ref)
  {
    size_t old_capacity;
    size_t new_capacity;
    RE_CallRefInfo* new_call_ref_info;

    if (call_ref < pattern->call_ref_info_count)
        /* We already have an entry for the call_ref. */
        return TRUE;

    /* Increase the storage capacity to include the new entry if it's
     * insufficient.
     */
    old_capacity = pattern->call_ref_info_capacity;
    new_capacity = pattern->call_ref_info_capacity;
    while (call_ref >= new_capacity)
        new_capacity += RE_LIST_SIZE_INC;

    if (new_capacity > old_capacity) {
        new_call_ref_info = (RE_CallRefInfo*)re_realloc(pattern->call_ref_info,
          new_capacity * sizeof(RE_CallRefInfo));
        if (!new_call_ref_info)
            return FALSE;
        memset(new_call_ref_info + old_capacity, 0, (new_capacity -
          old_capacity) * sizeof(RE_CallRefInfo));

        pattern->call_ref_info = new_call_ref_info;
        pattern->call_ref_info_capacity = new_capacity;
    }

    pattern->call_ref_info_count = 1 + call_ref;

    return TRUE;
}

/* Records that a call_ref is defined. */
Py_LOCAL_INLINE(BOOL) record_call_ref_defined(PatternObject* pattern, RE_CODE
  call_ref, RE_Node* node) {
    if (!ensure_call_ref(pattern, call_ref))
        return FALSE;

    pattern->call_ref_info[call_ref].defined = TRUE;
    pattern->call_ref_info[call_ref].node = node;

    return TRUE;
}

/* Records that a call_ref is used. */
Py_LOCAL_INLINE(BOOL) record_call_ref_used(PatternObject* pattern, RE_CODE
  call_ref) {
    if (!ensure_call_ref(pattern, call_ref))
        return FALSE;

    pattern->call_ref_info[call_ref].used = TRUE;

    return TRUE;
}

/* Checks whether a node matches one and only one character. */
Py_LOCAL_INLINE(BOOL) sequence_matches_one(RE_Node* node) {
    while (node->op == RE_OP_BRANCH && !node->nonstring.next_2.node)
        node = node->next_1.node;

    if (node->next_1.node || (node->status & RE_STATUS_FUZZY))
        return FALSE;

    switch (node->op) {
    case RE_OP_ANY:
    case RE_OP_ANY_ALL:
    case RE_OP_ANY_ALL_REV:
    case RE_OP_ANY_REV:
    case RE_OP_ANY_U:
    case RE_OP_ANY_U_REV:
    case RE_OP_CHARACTER:
    case RE_OP_CHARACTER_IGN:
    case RE_OP_CHARACTER_IGN_REV:
    case RE_OP_CHARACTER_REV:
    case RE_OP_PROPERTY:
    case RE_OP_PROPERTY_IGN:
    case RE_OP_PROPERTY_IGN_REV:
    case RE_OP_PROPERTY_REV:
    case RE_OP_RANGE:
    case RE_OP_RANGE_IGN:
    case RE_OP_RANGE_IGN_REV:
    case RE_OP_RANGE_REV:
    case RE_OP_SET_DIFF:
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_DIFF_IGN_REV:
    case RE_OP_SET_DIFF_REV:
    case RE_OP_SET_INTER:
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION:
    case RE_OP_SET_UNION_IGN:
    case RE_OP_SET_UNION_REV:
        return TRUE;
    default:
        return FALSE;
    }
}

/* Records a repeat. */
Py_LOCAL_INLINE(BOOL) record_repeat(PatternObject* pattern, size_t index,
  size_t repeat_depth) {
    size_t old_capacity;
    size_t new_capacity;

    /* Increase the storage capacity to include the new entry if it's
     * insufficient.
     */
    old_capacity = pattern->repeat_info_capacity;
    new_capacity = pattern->repeat_info_capacity;
    while (index >= new_capacity)
        new_capacity += RE_LIST_SIZE_INC;

    if (new_capacity > old_capacity) {
        RE_RepeatInfo* new_repeat_info;

        new_repeat_info = (RE_RepeatInfo*)re_realloc(pattern->repeat_info,
          new_capacity * sizeof(RE_RepeatInfo));
        if (!new_repeat_info)
            return FALSE;
        memset(new_repeat_info + old_capacity, 0, (new_capacity - old_capacity)
          * sizeof(RE_RepeatInfo));

        pattern->repeat_info = new_repeat_info;
        pattern->repeat_info_capacity = new_capacity;
    }

    if (index >= pattern->repeat_count)
        pattern->repeat_count = index + 1;

    if (repeat_depth > 0)
        pattern->repeat_info[index].status |= RE_STATUS_INNER;

    return TRUE;
}

Py_LOCAL_INLINE(Py_ssize_t) get_step(RE_CODE op) {
    switch (op) {
    case RE_OP_ANY:
    case RE_OP_ANY_ALL:
    case RE_OP_ANY_U:
    case RE_OP_CHARACTER:
    case RE_OP_CHARACTER_IGN:
    case RE_OP_PROPERTY:
    case RE_OP_PROPERTY_IGN:
    case RE_OP_RANGE:
    case RE_OP_RANGE_IGN:
    case RE_OP_SET_DIFF:
    case RE_OP_SET_DIFF_IGN:
    case RE_OP_SET_INTER:
    case RE_OP_SET_INTER_IGN:
    case RE_OP_SET_SYM_DIFF:
    case RE_OP_SET_SYM_DIFF_IGN:
    case RE_OP_SET_UNION:
    case RE_OP_SET_UNION_IGN:
    case RE_OP_STRING:
    case RE_OP_STRING_FLD:
    case RE_OP_STRING_IGN:
         return 1;
    case RE_OP_ANY_ALL_REV:
    case RE_OP_ANY_REV:
    case RE_OP_ANY_U_REV:
    case RE_OP_CHARACTER_IGN_REV:
    case RE_OP_CHARACTER_REV:
    case RE_OP_PROPERTY_IGN_REV:
    case RE_OP_PROPERTY_REV:
    case RE_OP_RANGE_IGN_REV:
    case RE_OP_RANGE_REV:
    case RE_OP_SET_DIFF_IGN_REV:
    case RE_OP_SET_DIFF_REV:
    case RE_OP_SET_INTER_IGN_REV:
    case RE_OP_SET_INTER_REV:
    case RE_OP_SET_SYM_DIFF_IGN_REV:
    case RE_OP_SET_SYM_DIFF_REV:
    case RE_OP_SET_UNION_IGN_REV:
    case RE_OP_SET_UNION_REV:
    case RE_OP_STRING_FLD_REV:
    case RE_OP_STRING_IGN_REV:
    case RE_OP_STRING_REV:
        return -1;
    }

    return 0;
}

Py_LOCAL_INLINE(int) build_sequence(RE_CompileArgs* args);

/* Builds an ANY node. */
Py_LOCAL_INLINE(int) build_ANY(RE_CompileArgs* args) {
    RE_UINT8 op;
    RE_CODE flags;
    Py_ssize_t step;
    RE_Node* node;

    /* codes: opcode, flags. */
    if (args->code + 1 > args->end_code)
        return RE_ERROR_ILLEGAL;

    op = (RE_UINT8)args->code[0];
    flags = args->code[1];

    step = get_step(op);

    /* Create the node. */
    node = create_node(args->pattern, op, flags, step, 0);
    if (!node)
        return RE_ERROR_MEMORY;

    args->code += 2;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    ++args->min_width;

    return RE_ERROR_SUCCESS;
}

/* Builds a FUZZY node. */
Py_LOCAL_INLINE(int) build_FUZZY(RE_CompileArgs* args) {
    RE_CODE flags;
    RE_Node* start_node;
    RE_Node* end_node;
    RE_CODE index;
    RE_CompileArgs subargs;
    int status;

    /* codes: opcode, flags, constraints, sequence, end. */
    if (args->code + 13 > args->end_code)
        return RE_ERROR_ILLEGAL;

    flags = args->code[1];

    /* Create nodes for the start and end of the fuzzy sequence. */
    start_node = create_node(args->pattern, RE_OP_FUZZY, flags, 0, 9);
    end_node = create_node(args->pattern, RE_OP_END_FUZZY, flags, 0, 5);
    if (!start_node || !end_node)
        return RE_ERROR_MEMORY;

    index = (RE_CODE)args->pattern->fuzzy_count++;
    start_node->values[0] = index;
    end_node->values[0] = index;

    /* The constraints consist of 4 pairs of limits and the cost equation. */
    end_node->values[RE_FUZZY_VAL_MIN_DEL] = args->code[2]; /* Deletion minimum. */
    end_node->values[RE_FUZZY_VAL_MIN_INS] = args->code[4]; /* Insertion minimum. */
    end_node->values[RE_FUZZY_VAL_MIN_SUB] = args->code[6]; /* Substitution minimum. */
    end_node->values[RE_FUZZY_VAL_MIN_ERR] = args->code[8]; /* Error minimum. */

    start_node->values[RE_FUZZY_VAL_MAX_DEL] = args->code[3]; /* Deletion maximum. */
    start_node->values[RE_FUZZY_VAL_MAX_INS] = args->code[5]; /* Insertion maximum. */
    start_node->values[RE_FUZZY_VAL_MAX_SUB] = args->code[7]; /* Substitution maximum. */
    start_node->values[RE_FUZZY_VAL_MAX_ERR] = args->code[9]; /* Error maximum. */

    start_node->values[RE_FUZZY_VAL_DEL_COST] = args->code[10]; /* Deletion cost. */
    start_node->values[RE_FUZZY_VAL_INS_COST] = args->code[11]; /* Insertion cost. */
    start_node->values[RE_FUZZY_VAL_SUB_COST] = args->code[12]; /* Substitution cost. */
    start_node->values[RE_FUZZY_VAL_MAX_COST] = args->code[13]; /* Total cost. */

    args->code += 14;

    subargs = *args;
    subargs.has_captures = FALSE;
    subargs.is_fuzzy = TRUE;
    subargs.within_fuzzy = TRUE;

    /* Compile the sequence and check that we've reached the end of the
     * subpattern.
     */
    status = build_sequence(&subargs);
    if (status != RE_ERROR_SUCCESS)
        return status;

    if (subargs.code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    args->code = subargs.code;
    args->min_width = subargs.min_width;
    args->has_captures |= subargs.has_captures;

    ++args->code;

    /* Append the fuzzy sequence. */
    add_node(args->end, start_node);
    add_node(start_node, subargs.start);
    add_node(subargs.end, end_node);
    args->end = end_node;

    args->is_fuzzy = TRUE;

    return RE_ERROR_SUCCESS;
}

/* Builds an ATOMIC node. */
Py_LOCAL_INLINE(int) build_ATOMIC(RE_CompileArgs* args) {
    RE_Node* atomic_node;
    RE_CompileArgs subargs;
    RE_Node* success_node;
    int status;

    /* codes: opcode, sequence, end. */
    if (args->code + 1 > args->end_code)
        return RE_ERROR_ILLEGAL;

    atomic_node = create_node(args->pattern, RE_OP_ATOMIC, 0, 0, 1);
    if (!atomic_node)
        return RE_ERROR_MEMORY;

    /* The number of repeat indexes. */
    atomic_node->values[0] = 0;

    ++args->code;

    subargs = *args;
    subargs.has_captures = FALSE;
    subargs.is_fuzzy = FALSE;

    /* Compile the sequence and check that we've reached the end of the
     * subpattern.
     */
    status = build_sequence(&subargs);
    if (status != RE_ERROR_SUCCESS)
        return status;

    if (subargs.code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    /* Create the success node to terminate the subpattern. */
    success_node = create_node(subargs.pattern, RE_OP_SUCCESS, 0, 0, 0);
    if (!success_node)
        return RE_ERROR_MEMORY;

    /* Append the SUCCESS node. */
    add_node(subargs.end, success_node);

    /* Insert the subpattern. */
    atomic_node->nonstring.next_2.node = subargs.start;

    args->code = subargs.code;
    args->min_width = subargs.min_width;
    args->has_captures |= subargs.has_captures;
    args->is_fuzzy |= subargs.is_fuzzy;

    ++args->code;

    /* Append the node. */
    add_node(args->end, atomic_node);
    args->end = atomic_node;

    return RE_ERROR_SUCCESS;
}

/* Builds a BOUNDARY node. */
Py_LOCAL_INLINE(int) build_BOUNDARY(RE_CompileArgs* args) {
    RE_UINT8 op;
    RE_CODE flags;
    RE_Node* node;

    /* codes: opcode, flags. */
    if (args->code + 1 > args->end_code)
        return RE_ERROR_ILLEGAL;

    op = (RE_UINT8)args->code[0];
    flags = args->code[1];

    args->code += 2;

    /* Create the node. */
    node = create_node(args->pattern, op, flags, 0, 0);
    if (!node)
        return RE_ERROR_MEMORY;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    return RE_ERROR_SUCCESS;
}

/* Builds a BRANCH node. */
Py_LOCAL_INLINE(int) build_BRANCH(RE_CompileArgs* args) {
    RE_Node* branch_node;
    RE_Node* join_node;
    size_t smallest_min_width;
    RE_CompileArgs subargs;
    int status;

    /* codes: opcode, branch, next, branch, end. */
    if (args->code + 2 > args->end_code)
        return RE_ERROR_ILLEGAL;

    /* Create nodes for the start and end of the branch sequence. */
    branch_node = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
    join_node = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
    if (!branch_node || !join_node)
        return RE_ERROR_MEMORY;

    /* Append the node. */
    add_node(args->end, branch_node);
    args->end = join_node;

    smallest_min_width = ~(size_t)0;

    subargs = *args;

    /* A branch in the regular expression is compiled into a series of 2-way
     * branches.
     */
    do {
        RE_Node* next_branch_node;

        /* Skip over the 'BRANCH' or 'NEXT' opcode. */
        ++subargs.code;

        /* Compile the sequence until the next 'BRANCH' or 'NEXT' opcode. */
        subargs.min_width = 0;
        subargs.has_captures = FALSE;
        subargs.is_fuzzy = FALSE;
        status = build_sequence(&subargs);
        if (status != RE_ERROR_SUCCESS)
            return status;

        smallest_min_width = RE_MIN(smallest_min_width, subargs.min_width);

        args->has_captures |= subargs.has_captures;
        args->is_fuzzy |= subargs.is_fuzzy;

        /* Append the sequence. */
        add_node(branch_node, subargs.start);
        add_node(subargs.end, join_node);

        /* Create a start node for the next sequence and append it. */
        next_branch_node = create_node(subargs.pattern, RE_OP_BRANCH, 0, 0, 0);
        if (!next_branch_node)
            return RE_ERROR_MEMORY;

        add_node(branch_node, next_branch_node);
        branch_node = next_branch_node;
    } while (subargs.code < subargs.end_code && subargs.code[0] == RE_OP_NEXT);

    /* We should have reached the end of the branch. */
    if (subargs.code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    args->code = subargs.code;

    ++args->code;
    args->min_width += smallest_min_width;

    return RE_ERROR_SUCCESS;
}

/* Builds a CALL_REF node. */
Py_LOCAL_INLINE(int) build_CALL_REF(RE_CompileArgs* args) {
    RE_CODE call_ref;
    RE_Node* start_node;
    RE_Node* end_node;
    RE_CompileArgs subargs;
    int status;

    /* codes: opcode, call_ref. */
    if (args->code + 1 > args->end_code)
        return RE_ERROR_ILLEGAL;

    call_ref = args->code[1];

    args->code += 2;

    /* Create nodes for the start and end of the subpattern. */
    start_node = create_node(args->pattern, RE_OP_CALL_REF, 0, 0, 1);
    end_node = create_node(args->pattern, RE_OP_GROUP_RETURN, 0, 0, 0);
    if (!start_node || !end_node)
        return RE_ERROR_MEMORY;

    start_node->values[0] = call_ref;

    /* Compile the sequence and check that we've reached the end of the
     * subpattern.
     */
    subargs = *args;
    subargs.has_captures = FALSE;
    subargs.is_fuzzy = FALSE;
    status = build_sequence(&subargs);
    if (status != RE_ERROR_SUCCESS)
        return status;

    if (subargs.code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    args->code = subargs.code;
    args->min_width = subargs.min_width;
    args->has_captures |= subargs.has_captures;
    args->is_fuzzy |= subargs.is_fuzzy;

    ++args->code;

    /* Record that we defined a call_ref. */
    if (!record_call_ref_defined(args->pattern, call_ref, start_node))
        return RE_ERROR_MEMORY;

    /* Append the node. */
    add_node(args->end, start_node);
    add_node(start_node, subargs.start);
    add_node(subargs.end, end_node);
    args->end = end_node;

    return RE_ERROR_SUCCESS;
}

/* Builds a CHARACTER or PROPERTY node. */
Py_LOCAL_INLINE(int) build_CHARACTER_or_PROPERTY(RE_CompileArgs* args) {
    RE_UINT8 op;
    RE_CODE flags;
    Py_ssize_t step;
    RE_Node* node;

    /* codes: opcode, flags, value. */
    if (args->code + 2 > args->end_code)
        return RE_ERROR_ILLEGAL;

    op = (RE_UINT8)args->code[0];
    flags = args->code[1];

    step = get_step(op);

    if (flags & RE_ZEROWIDTH_OP)
        step = 0;

    /* Create the node. */
    node = create_node(args->pattern, op, flags, step, 1);
    if (!node)
        return RE_ERROR_MEMORY;

    node->values[0] = args->code[2];

    args->code += 3;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    if (step != 0)
        ++args->min_width;

    return RE_ERROR_SUCCESS;
}

/* Builds a GROUP node. */
Py_LOCAL_INLINE(int) build_GROUP(RE_CompileArgs* args) {
    RE_CODE private_group;
    RE_CODE public_group;
    RE_Node* start_node;
    RE_Node* end_node;
    RE_CompileArgs subargs;
    int status;

    /* codes: opcode, private_group, public_group. */
    if (args->code + 2 > args->end_code)
        return RE_ERROR_ILLEGAL;

    private_group = args->code[1];
    public_group = args->code[2];

    args->code += 3;

    /* Create nodes for the start and end of the capture group. */
    start_node = create_node(args->pattern, args->forward ? RE_OP_START_GROUP :
      RE_OP_END_GROUP, 0, 0, 3);
    end_node = create_node(args->pattern, args->forward ? RE_OP_END_GROUP :
      RE_OP_START_GROUP, 0, 0, 3);
    if (!start_node || !end_node)
        return RE_ERROR_MEMORY;

    start_node->values[0] = private_group;
    end_node->values[0] = private_group;
    start_node->values[1] = public_group;
    end_node->values[1] = public_group;

    /* Signal that the capture should be saved when it's complete. */
    start_node->values[2] = 0;
    end_node->values[2] = 1;

    /* Record that we have a new capture group. */
    if (!record_group(args->pattern, private_group, start_node))
        return RE_ERROR_MEMORY;

    /* Compile the sequence and check that we've reached the end of the capture
     * group.
     */
    subargs = *args;
    subargs.has_captures = FALSE;
    subargs.is_fuzzy = FALSE;
    status = build_sequence(&subargs);
    if (status != RE_ERROR_SUCCESS)
        return status;

    if (subargs.code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    args->code = subargs.code;
    args->min_width = subargs.min_width;
    args->has_captures |= subargs.has_captures || subargs.visible_captures;
    args->is_fuzzy |= subargs.is_fuzzy;

    ++args->code;

    /* Record that the capture group has closed. */
    record_group_end(args->pattern, private_group);

    /* Append the capture group. */
    add_node(args->end, start_node);
    add_node(start_node, subargs.start);
    add_node(subargs.end, end_node);
    args->end = end_node;

    return RE_ERROR_SUCCESS;
}

/* Builds a GROUP_CALL node. */
Py_LOCAL_INLINE(int) build_GROUP_CALL(RE_CompileArgs* args) {
    RE_CODE call_ref;
    RE_Node* node;

    /* codes: opcode, call_ref. */
    if (args->code + 1 > args->end_code)
        return RE_ERROR_ILLEGAL;

    call_ref = args->code[1];

    /* Create the node. */
    node = create_node(args->pattern, RE_OP_GROUP_CALL, 0, 0, 1);
    if (!node)
        return RE_ERROR_MEMORY;

    node->values[0] = call_ref;

    args->code += 2;

    /* Record that we used a call_ref. */
    if (!record_call_ref_used(args->pattern, call_ref))
        return RE_ERROR_MEMORY;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    return RE_ERROR_SUCCESS;
}

/* Builds a GROUP_EXISTS node. */
Py_LOCAL_INLINE(int) build_GROUP_EXISTS(RE_CompileArgs* args) {
    RE_CODE group;
    RE_Node* start_node;
    RE_Node* end_node;
    RE_CompileArgs subargs;
    size_t min_width;
    int status;

    /* codes: opcode, sequence, next, sequence, end. */
    if (args->code + 2 > args->end_code)
        return RE_ERROR_ILLEGAL;

    group = args->code[1];

    args->code += 2;

    /* Create nodes for the start and end of the structure. */
    start_node = create_node(args->pattern, RE_OP_GROUP_EXISTS, 0, 0, 1);
    end_node = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
    if (!start_node || !end_node)
        return RE_ERROR_MEMORY;

    start_node->values[0] = group;

    subargs = *args;
    subargs.min_width = 0;
    subargs.has_captures = FALSE;
    subargs.is_fuzzy = FALSE;
    status = build_sequence(&subargs);
    if (status != RE_ERROR_SUCCESS)
        return status;

    args->code = subargs.code;
    args->has_captures |= subargs.has_captures;
    args->is_fuzzy |= subargs.is_fuzzy;

    min_width = subargs.min_width;

    /* Append the start node. */
    add_node(args->end, start_node);
    add_node(start_node, subargs.start);
    add_node(subargs.end, end_node);

    if (args->code[0] == RE_OP_NEXT) {
        ++args->code;

        subargs.code = args->code;
        subargs.min_width = 0;
        subargs.has_captures = FALSE;
        subargs.is_fuzzy = FALSE;
        status = build_sequence(&subargs);
        if (status != RE_ERROR_SUCCESS)
            return status;

        args->code = subargs.code;
        args->has_captures |= subargs.has_captures;
        args->is_fuzzy |= subargs.is_fuzzy;

        min_width = RE_MIN(min_width, subargs.min_width);

        add_node(start_node, subargs.start);
        add_node(subargs.end, end_node);
    } else {
        add_node(start_node, end_node);

        min_width = 0;
    }

    args->min_width += min_width;

    if (args->code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    ++args->code;

    args->end = end_node;

    return RE_ERROR_SUCCESS;
}

/* Builds a LOOKAROUND node. */
Py_LOCAL_INLINE(int) build_LOOKAROUND(RE_CompileArgs* args) {
    RE_CODE flags;
    BOOL forward;
    RE_Node* lookaround_node;
    RE_Node* success_node;
    RE_CompileArgs subargs;
    int status;

    /* codes: opcode, flags, forward, sequence, end. */
    if (args->code + 3 > args->end_code)
        return RE_ERROR_ILLEGAL;

    flags = args->code[1];
    forward = (BOOL)args->code[2];

    /* Create a node for the lookaround. */
    lookaround_node = create_node(args->pattern, RE_OP_LOOKAROUND, flags, 0,
      2);
    if (!lookaround_node)
        return RE_ERROR_MEMORY;

    /* The number of repeat indexes. */
    lookaround_node->values[1] = 0;

    args->code += 3;

    /* Compile the sequence and check that we've reached the end of the
     * subpattern.
     */
    subargs = *args;
    subargs.forward = forward;
    subargs.has_captures = FALSE;
    subargs.is_fuzzy = FALSE;
    status = build_sequence(&subargs);
    if (status != RE_ERROR_SUCCESS)
        return status;

    lookaround_node->values[0] = subargs.has_captures;

    if (subargs.code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    args->code = subargs.code;
    args->has_captures |= subargs.has_captures;
    args->is_fuzzy |= subargs.is_fuzzy;
    ++args->code;

    /* Create the 'SUCCESS' node and append it to the subpattern. */
    success_node = create_node(args->pattern, RE_OP_SUCCESS, 0, 0, 0);
    if (!success_node)
        return RE_ERROR_MEMORY;

    /* Append the SUCCESS node. */
    add_node(subargs.end, success_node);

    /* Insert the subpattern into the node. */
    lookaround_node->nonstring.next_2.node = subargs.start;

    /* Append the lookaround. */
    add_node(args->end, lookaround_node);
    args->end = lookaround_node;

    return RE_ERROR_SUCCESS;
}

/* Builds a RANGE node. */
Py_LOCAL_INLINE(int) build_RANGE(RE_CompileArgs* args) {
    RE_UINT8 op;
    RE_CODE flags;
    Py_ssize_t step;
    RE_Node* node;

    /* codes: opcode, flags, lower, upper. */
    if (args->code + 3 > args->end_code)
        return RE_ERROR_ILLEGAL;

    op = (RE_UINT8)args->code[0];
    flags = args->code[1];

    step = get_step(op);

    if (flags & RE_ZEROWIDTH_OP)
        step = 0;

    /* Create the node. */
    node = create_node(args->pattern, op, flags, step, 2);
    if (!node)
        return RE_ERROR_MEMORY;

    node->values[0] = args->code[2];
    node->values[1] = args->code[3];

    args->code += 4;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    if (step != 0)
        ++args->min_width;

    return RE_ERROR_SUCCESS;
}

/* Builds a REF_GROUP node. */
Py_LOCAL_INLINE(int) build_REF_GROUP(RE_CompileArgs* args) {
    RE_CODE flags;
    RE_CODE group;
    RE_Node* node;

    /* codes: opcode, flags, group. */
    if (args->code + 2 > args->end_code)
        return RE_ERROR_ILLEGAL;

    flags = args->code[1];
    group = args->code[2];
    node = create_node(args->pattern, (RE_UINT8)args->code[0], flags, 0, 1);
    if (!node)
        return RE_ERROR_MEMORY;

    node->values[0] = group;

    args->code += 3;

    /* Record that we have a reference to a group. */
    if (!record_ref_group(args->pattern, group))
        return RE_ERROR_MEMORY;

    /* Append the reference. */
    add_node(args->end, node);
    args->end = node;

    return RE_ERROR_SUCCESS;
}

/* Builds a REPEAT node. */
Py_LOCAL_INLINE(int) build_REPEAT(RE_CompileArgs* args) {
    BOOL greedy;
    RE_CODE min_count;
    RE_CODE max_count;
    int status;

    /* codes: opcode, min_count, max_count, sequence, end. */
    if (args->code + 3 > args->end_code)
        return RE_ERROR_ILLEGAL;

    /* This includes special cases such as optional items, which we'll check
     * for and treat specially. They don't need repeat counts, which helps us
     * avoid unnecessary work when matching.
     */
    greedy = args->code[0] == RE_OP_GREEDY_REPEAT;
    min_count = args->code[1];
    max_count = args->code[2];
    if (min_count > max_count)
        return RE_ERROR_ILLEGAL;

    args->code += 3;

    if (min_count == 0 && max_count == 1) {
        /* Optional sequence. */
        RE_Node* branch_node;
        RE_Node* join_node;
        RE_CompileArgs subargs;

        /* Create the start and end nodes. */
        branch_node = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
        join_node = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
        if (!branch_node || !join_node)
            return RE_ERROR_MEMORY;

        /* Compile the sequence and check that we've reached the end of it. */
        subargs = *args;
        subargs.has_captures = FALSE;
        subargs.is_fuzzy = FALSE;
        status = build_sequence(&subargs);
        if (status != RE_ERROR_SUCCESS)
            return status;

        if (subargs.code[0] != RE_OP_END)
            return RE_ERROR_ILLEGAL;

        args->code = subargs.code;
        args->has_captures |= subargs.has_captures;
        args->is_fuzzy |= subargs.is_fuzzy;

        ++args->code;

        if (greedy) {
            /* It's a greedy option. */
            add_node(branch_node, subargs.start);
            add_node(branch_node, join_node);
        } else {
            /* It's a lazy option. */
            add_node(branch_node, join_node);
            add_node(branch_node, subargs.start);
        }
        add_node(subargs.end, join_node);

        /* Append the optional sequence. */
        add_node(args->end, branch_node);
        args->end = join_node;
    } else if (min_count == 1 && max_count == 1) {
        /* Singly-repeated sequence. */
        RE_CompileArgs subargs;

        subargs = *args;
        subargs.has_captures = FALSE;
        subargs.is_fuzzy = FALSE;
        status = build_sequence(&subargs);
        if (status != RE_ERROR_SUCCESS)
            return status;

        if (subargs.code[0] != RE_OP_END)
            return RE_ERROR_ILLEGAL;

        args->code = subargs.code;
        args->min_width = subargs.min_width;
        args->has_captures |= subargs.has_captures;
        args->is_fuzzy |= subargs.is_fuzzy;

        ++args->code;

        /* Append the sequence. */
        add_node(args->end, subargs.start);
        args->end = subargs.end;
    } else {
        RE_CODE index;
        RE_Node* repeat_node;
        RE_CompileArgs subargs;

        index = (RE_CODE)args->pattern->repeat_count;

        /* Create the nodes for the repeat. */
        repeat_node = create_node(args->pattern, greedy ? RE_OP_GREEDY_REPEAT :
          RE_OP_LAZY_REPEAT, 0, args->forward ? 1 : -1, 4);
        if (!repeat_node || !record_repeat(args->pattern, index,
          args->repeat_depth))
            return RE_ERROR_MEMORY;

        repeat_node->values[0] = index;
        repeat_node->values[1] = min_count;
        repeat_node->values[2] = max_count;
        repeat_node->values[3] = args->forward;

        if (args->within_fuzzy)
            args->pattern->repeat_info[index].status |= RE_STATUS_BODY;

        /* Compile the 'body' and check that we've reached the end of it. */
        subargs = *args;
        subargs.min_width = 0;
        subargs.visible_captures = TRUE;
        subargs.has_captures = FALSE;
        subargs.is_fuzzy = FALSE;
        ++subargs.repeat_depth;
        status = build_sequence(&subargs);
        if (status != RE_ERROR_SUCCESS)
            return status;

        if (subargs.code[0] != RE_OP_END)
            return RE_ERROR_ILLEGAL;

        args->code = subargs.code;
        args->min_width += min_count * subargs.min_width;
        args->has_captures |= subargs.has_captures;
        args->is_fuzzy |= subargs.is_fuzzy;

        ++args->code;

        /* Is it a repeat of something which will match a single character?
         *
         * If it's in a fuzzy section then it won't be optimised as a
         * single-character repeat.
         */
        if (sequence_matches_one(subargs.start)) {
            repeat_node->op = greedy ? RE_OP_GREEDY_REPEAT_ONE :
              RE_OP_LAZY_REPEAT_ONE;

            /* Append the new sequence. */
            add_node(args->end, repeat_node);
            repeat_node->nonstring.next_2.node = subargs.start;
            args->end = repeat_node;
        } else {
            RE_Node* end_repeat_node;
            RE_Node* end_node;

            end_repeat_node = create_node(args->pattern, greedy ?
              RE_OP_END_GREEDY_REPEAT : RE_OP_END_LAZY_REPEAT, 0, args->forward
              ? 1 : -1, 4);
            if (!end_repeat_node)
                return RE_ERROR_MEMORY;

            end_repeat_node->values[0] = repeat_node->values[0];
            end_repeat_node->values[1] = repeat_node->values[1];
            end_repeat_node->values[2] = repeat_node->values[2];
            end_repeat_node->values[3] = args->forward;

            end_node = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
            if (!end_node)
                return RE_ERROR_MEMORY;

            /* Append the new sequence. */
            add_node(args->end, repeat_node);
            add_node(repeat_node, subargs.start);
            add_node(repeat_node, end_node);
            add_node(subargs.end, end_repeat_node);
            add_node(end_repeat_node, subargs.start);
            add_node(end_repeat_node, end_node);
            args->end = end_node;
        }
    }

    return RE_ERROR_SUCCESS;
}

/* Builds a STRING node. */
Py_LOCAL_INLINE(int) build_STRING(RE_CompileArgs* args, BOOL is_charset) {
    RE_CODE flags;
    RE_CODE length;
    RE_UINT8 op;
    Py_ssize_t step;
    RE_Node* node;
    RE_CODE i;

    /* codes: opcode, flags, length, characters. */
    flags = args->code[1];
    length = args->code[2];
    if (args->code + 3 + length > args->end_code)
        return RE_ERROR_ILLEGAL;

    op = (RE_UINT8)args->code[0];

    step = get_step(op);

    /* Create the node. */
    node = create_node(args->pattern, op, flags, step * (Py_ssize_t)length,
      length);
    if (!node)
        return RE_ERROR_MEMORY;
    if (!is_charset)
        node->status |= RE_STATUS_STRING;

    for (i = 0; i < length; i++)
        node->values[i] = args->code[3 + i];

    args->code += 3 + length;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    /* Because of full case-folding, one character in the text could match
     * multiple characters in the pattern.
     */
    if (op == RE_OP_STRING_FLD || op == RE_OP_STRING_FLD_REV)
        args->min_width += possible_unfolded_length(length);
    else
        args->min_width += length;

    return RE_ERROR_SUCCESS;
}

/* Builds a SET node. */
Py_LOCAL_INLINE(int) build_SET(RE_CompileArgs* args) {
    RE_UINT8 op;
    RE_CODE flags;
    Py_ssize_t step;
    RE_Node* node;
    size_t saved_min_width;
    int status;

    /* codes: opcode, flags, members. */
    op = (RE_UINT8)args->code[0];
    flags = args->code[1];

    step = get_step(op);

    if (flags & RE_ZEROWIDTH_OP)
        step = 0;

    node = create_node(args->pattern, op, flags, step, 0);
    if (!node)
        return RE_ERROR_MEMORY;

    args->code += 2;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    saved_min_width = args->min_width;

    /* Compile the character set. */
    do {
        switch (args->code[0]) {
        case RE_OP_CHARACTER:
        case RE_OP_PROPERTY:
            status = build_CHARACTER_or_PROPERTY(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_RANGE:
            status = build_RANGE(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_SET_DIFF:
        case RE_OP_SET_INTER:
        case RE_OP_SET_SYM_DIFF:
        case RE_OP_SET_UNION:
            status = build_SET(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_STRING:
            /* A set of characters. */
            if (!build_STRING(args, TRUE))
                return FALSE;
            break;
        default:
            /* Illegal opcode for a character set. */
            return RE_ERROR_ILLEGAL;
        }
    } while (args->code < args->end_code && args->code[0] != RE_OP_END);

    /* Check that we've reached the end correctly. (The last opcode should be
     * 'END'.)
     */
    if (args->code >= args->end_code || args->code[0] != RE_OP_END)
        return RE_ERROR_ILLEGAL;

    ++args->code;

    /* At this point the set's members are in the main sequence. They need to
     * be moved out-of-line.
     */
    node->nonstring.next_2.node = node->next_1.node;
    node->next_1.node = NULL;
    args->end = node;

    args->min_width = saved_min_width;

    if (step != 0)
        ++args->min_width;

    return RE_ERROR_SUCCESS;
}

/* Builds a STRING_SET node. */
Py_LOCAL_INLINE(int) build_STRING_SET(RE_CompileArgs* args) {
    RE_CODE index;
    RE_CODE min_len;
    RE_CODE max_len;
    RE_Node* node;

    /* codes: opcode, index, min_len, max_len. */
    if (args->code + 3 > args->end_code)
        return RE_ERROR_ILLEGAL;

    index = args->code[1];
    min_len = args->code[2];
    max_len = args->code[3];
    node = create_node(args->pattern, (RE_UINT8)args->code[0], 0, 0, 3);
    if (!node)
        return RE_ERROR_MEMORY;

    node->values[0] = index;
    node->values[1] = min_len;
    node->values[2] = max_len;

    args->code += 4;

    /* Append the reference. */
    add_node(args->end, node);
    args->end = node;

    return RE_ERROR_SUCCESS;
}

/* Builds a SUCCESS node . */
Py_LOCAL_INLINE(int) build_SUCCESS(RE_CompileArgs* args) {
    RE_Node* node;
    /* code: opcode. */

    /* Create the node. */
    node = create_node(args->pattern, RE_OP_SUCCESS, 0, 0, 0);
    if (!node)
        return RE_ERROR_MEMORY;

    ++args->code;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    return RE_ERROR_SUCCESS;
}

/* Builds a zero-width node. */
Py_LOCAL_INLINE(int) build_zerowidth(RE_CompileArgs* args) {
    RE_CODE flags;
    RE_Node* node;

    /* codes: opcode, flags. */
    if (args->code + 1 > args->end_code)
        return RE_ERROR_ILLEGAL;

    flags = args->code[1];

    /* Create the node. */
    node = create_node(args->pattern, (RE_UINT8)args->code[0], flags, 0, 0);
    if (!node)
        return RE_ERROR_MEMORY;

    args->code += 2;

    /* Append the node. */
    add_node(args->end, node);
    args->end = node;

    return RE_ERROR_SUCCESS;
}

/* Builds a sequence of nodes from regular expression code. */
Py_LOCAL_INLINE(int) build_sequence(RE_CompileArgs* args) {
    int status;

    /* Guarantee that there's something to attach to. */
    args->start = create_node(args->pattern, RE_OP_BRANCH, 0, 0, 0);
    args->end = args->start;

    /* The sequence should end with an opcode we don't understand. If it
     * doesn't then the code is illegal.
     */
    while (args->code < args->end_code) {
        /* The following code groups opcodes by format, not function. */
        switch (args->code[0]) {
        case RE_OP_ANY:
        case RE_OP_ANY_ALL:
        case RE_OP_ANY_ALL_REV:
        case RE_OP_ANY_REV:
        case RE_OP_ANY_U:
        case RE_OP_ANY_U_REV:
            /* A simple opcode with no trailing codewords and width of 1. */
            status = build_ANY(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_ATOMIC:
            /* An atomic sequence. */
            status = build_ATOMIC(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_BOUNDARY:
        case RE_OP_DEFAULT_BOUNDARY:
        case RE_OP_DEFAULT_END_OF_WORD:
        case RE_OP_DEFAULT_START_OF_WORD:
        case RE_OP_END_OF_WORD:
        case RE_OP_GRAPHEME_BOUNDARY:
        case RE_OP_START_OF_WORD:
            /* A word or grapheme boundary. */
            status = build_BOUNDARY(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_BRANCH:
            /* A 2-way branch. */
            status = build_BRANCH(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_CALL_REF:
            /* A group call ref. */
            status = build_CALL_REF(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_CHARACTER:
        case RE_OP_CHARACTER_IGN:
        case RE_OP_CHARACTER_IGN_REV:
        case RE_OP_CHARACTER_REV:
        case RE_OP_PROPERTY:
        case RE_OP_PROPERTY_IGN:
        case RE_OP_PROPERTY_IGN_REV:
        case RE_OP_PROPERTY_REV:
            /* A character literal or a property. */
            status = build_CHARACTER_or_PROPERTY(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_END_OF_LINE:
        case RE_OP_END_OF_LINE_U:
        case RE_OP_END_OF_STRING:
        case RE_OP_END_OF_STRING_LINE:
        case RE_OP_END_OF_STRING_LINE_U:
        case RE_OP_SEARCH_ANCHOR:
        case RE_OP_START_OF_LINE:
        case RE_OP_START_OF_LINE_U:
        case RE_OP_START_OF_STRING:
            /* A simple opcode with no trailing codewords and width of 0. */
            status = build_zerowidth(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_FUZZY:
            /* A fuzzy sequence. */
            status = build_FUZZY(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_GREEDY_REPEAT:
        case RE_OP_LAZY_REPEAT:
            /* A repeated sequence. */
            status = build_REPEAT(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_GROUP:
            /* A capture group. */
            status = build_GROUP(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_GROUP_CALL:
            /* A group call. */
            status = build_GROUP_CALL(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_GROUP_EXISTS:
            /* A conditional sequence. */
            status = build_GROUP_EXISTS(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_LOOKAROUND:
            /* A lookaround. */
            status = build_LOOKAROUND(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_RANGE:
        case RE_OP_RANGE_IGN:
        case RE_OP_RANGE_IGN_REV:
        case RE_OP_RANGE_REV:
            /* A range. */
            status = build_RANGE(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_REF_GROUP:
        case RE_OP_REF_GROUP_FLD:
        case RE_OP_REF_GROUP_FLD_REV:
        case RE_OP_REF_GROUP_IGN:
        case RE_OP_REF_GROUP_IGN_REV:
        case RE_OP_REF_GROUP_REV:
            /* A reference to a group. */
            status = build_REF_GROUP(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_SET_DIFF:
        case RE_OP_SET_DIFF_IGN:
        case RE_OP_SET_DIFF_IGN_REV:
        case RE_OP_SET_DIFF_REV:
        case RE_OP_SET_INTER:
        case RE_OP_SET_INTER_IGN:
        case RE_OP_SET_INTER_IGN_REV:
        case RE_OP_SET_INTER_REV:
        case RE_OP_SET_SYM_DIFF:
        case RE_OP_SET_SYM_DIFF_IGN:
        case RE_OP_SET_SYM_DIFF_IGN_REV:
        case RE_OP_SET_SYM_DIFF_REV:
        case RE_OP_SET_UNION:
        case RE_OP_SET_UNION_IGN:
        case RE_OP_SET_UNION_IGN_REV:
        case RE_OP_SET_UNION_REV:
            /* A set. */
            status = build_SET(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_STRING:
        case RE_OP_STRING_FLD:
        case RE_OP_STRING_FLD_REV:
        case RE_OP_STRING_IGN:
        case RE_OP_STRING_IGN_REV:
        case RE_OP_STRING_REV:
            /* A string literal. */
            if (!build_STRING(args, FALSE))
                return FALSE;
            break;
        case RE_OP_STRING_SET:
        case RE_OP_STRING_SET_FLD:
        case RE_OP_STRING_SET_FLD_REV:
        case RE_OP_STRING_SET_IGN:
        case RE_OP_STRING_SET_IGN_REV:
        case RE_OP_STRING_SET_REV:
            /* A reference to a list. */
            status = build_STRING_SET(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        case RE_OP_SUCCESS:
            /* Success. */
            status = build_SUCCESS(args);
            if (status != RE_ERROR_SUCCESS)
                return status;
            break;
        default:
            /* We've found an opcode which we don't recognise. We'll leave it
             * for the caller.
             */
            return RE_ERROR_SUCCESS;
        }
    }

    /* If we're here then we should be at the end of the code, otherwise we
     * have an error.
     */
    return args->code == args->end_code;
}

/* Compiles the regular expression code to 'nodes'.
 *
 * Various details about the regular expression are discovered during
 * compilation and stored in the PatternObject.
 */
Py_LOCAL_INLINE(BOOL) compile_to_nodes(RE_CODE* code, RE_CODE* end_code,
  PatternObject* pattern) {
    RE_CompileArgs args;
    int status;

    /* Compile a regex sequence and then check that we've reached the end
     * correctly. (The last opcode should be 'SUCCESS'.)
     *
     * If successful, 'start' and 'end' will point to the start and end nodes
     * of the compiled sequence.
     */
    args.code = code;
    args.end_code = end_code;
    args.pattern = pattern;
    args.forward = (pattern->flags & RE_FLAG_REVERSE) == 0;
    args.min_width = 0;
    args.visible_captures = FALSE;
    args.has_captures = FALSE;
    args.repeat_depth = 0;
    args.is_fuzzy = FALSE;
    args.within_fuzzy = FALSE;
    status = build_sequence(&args);
    if (status == RE_ERROR_ILLEGAL)
        set_error(RE_ERROR_ILLEGAL, NULL);

    if (status != RE_ERROR_SUCCESS)
        return FALSE;

    pattern->min_width = args.min_width;
    pattern->is_fuzzy = args.is_fuzzy;
    pattern->do_search_start = TRUE;
    pattern->start_node = args.start;

    /* Optimise the pattern. */
    if (!optimise_pattern(pattern))
        return FALSE;

    pattern->start_test = locate_test_start(pattern->start_node);

    /* Get the call_ref for the entire pattern, if any. */
    if (pattern->start_node->op == RE_OP_CALL_REF)
        pattern->pattern_call_ref = pattern->start_node->values[0];
    else
        pattern->pattern_call_ref = -1;

    return TRUE;
}

/* Gets the required characters for a regex.
 *
 * In the event of an error, it just pretends that there are no required
 * characters.
 */
Py_LOCAL_INLINE(void) get_required_chars(PyObject* required_chars, RE_CODE**
  req_chars, Py_ssize_t* req_length) {
    Py_ssize_t len;
    RE_CODE* chars;
    Py_ssize_t i;

    *req_chars = NULL;
    *req_length = 0;

    len = PyTuple_GET_SIZE(required_chars);
    if (len < 1 || PyErr_Occurred()) {
        PyErr_Clear();
        return;
    }

    chars = (RE_CODE*)re_alloc(len * sizeof(RE_CODE));
    if (!chars)
        goto error;

    for (i = 0; i < len; i++) {
        PyObject* o = PyTuple_GET_ITEM(required_chars, i);
        size_t value;

        value = PyLong_AsUnsignedLong(o);
        if (value == -1 && PyErr_Occurred())
            goto error;

        chars[i] = (RE_CODE)value;
        if (chars[i] != value)
            goto error;
    }

    *req_chars = chars;
    *req_length = len;

    return;

error:
    PyErr_Clear();
    re_dealloc(chars);
}

/* Makes a STRING node. */
Py_LOCAL_INLINE(RE_Node*) make_STRING_node(PatternObject* pattern, RE_UINT8 op,
  Py_ssize_t length, RE_CODE* chars) {
    Py_ssize_t step;
    RE_Node* node;
    Py_ssize_t i;

    step = get_step(op);

    /* Create the node. */
    node = create_node(pattern, op, 0, step * length, length);
    if (!node)
        return NULL;

    node->status |= RE_STATUS_STRING;

    for (i = 0; i < length; i++)
        node->values[i] = chars[i];

    return node;
}

/* Compiles regular expression code to a PatternObject.
 *
 * The regular expression code is provided as a list and is then compiled to
 * 'nodes'. Various details about the regular expression are discovered during
 * compilation and stored in the PatternObject.
 */
static PyObject* re_compile(PyObject* self_, PyObject* args) {
    PyObject* pattern;
    Py_ssize_t flags = 0;
    PyObject* code_list;
    PyObject* groupindex;
    PyObject* indexgroup;
    PyObject* named_lists;
    PyObject* named_list_indexes;
    Py_ssize_t req_offset;
    PyObject* required_chars;
    Py_ssize_t req_length;
    RE_CODE* req_chars;
    Py_ssize_t req_flags;
    Py_ssize_t public_group_count;
    Py_ssize_t code_len;
    RE_CODE* code;
    Py_ssize_t i;
    PatternObject* self;
    BOOL ascii;
    BOOL locale;
    BOOL unicode;
    BOOL ok;

    if (!PyArg_ParseTuple(args, "OnOOOOOnOnn:re_compile", &pattern, &flags,
      &code_list, &groupindex, &indexgroup, &named_lists, &named_list_indexes,
      &req_offset, &required_chars, &req_flags, &public_group_count))
        return NULL;

    /* Read the regex code. */
    code_len = PyList_GET_SIZE(code_list);
    code = (RE_CODE*)re_alloc(code_len * sizeof(RE_CODE));
    if (!code)
        return NULL;

    for (i = 0; i < code_len; i++) {
        PyObject* o = PyList_GET_ITEM(code_list, i);
        size_t value;

        value = PyLong_AsUnsignedLong(o);
        if (value == -1 && PyErr_Occurred())
            goto error;

        code[i] = (RE_CODE)value;
        if (code[i] != value)
            goto error;
    }

    /* Get the required characters. */
    get_required_chars(required_chars, &req_chars, &req_length);

    /* Create the PatternObject. */
    self = PyObject_NEW(PatternObject, &Pattern_Type);
    if (!self) {
        set_error(RE_ERROR_MEMORY, NULL);
        re_dealloc(req_chars);
        re_dealloc(code);
        return NULL;
    }

    /* Initialise the PatternObject. */
    self->pattern = pattern;
    self->flags = (RE_CODE)flags;
    self->weakreflist = NULL;
    self->start_node = NULL;
    self->repeat_count = 0;
    self->true_group_count = 0;
    self->public_group_count = public_group_count;
    self->group_end_index = 0;
    self->groupindex = groupindex;
    self->indexgroup = indexgroup;
    self->named_lists = named_lists;
    self->named_list_indexes = named_list_indexes;
    self->node_capacity = 0;
    self->node_count = 0;
    self->node_list = NULL;
    self->group_info_capacity = 0;
    self->group_info = NULL;
    self->call_ref_info_capacity = 0;
    self->call_ref_info_count = 0;
    self->call_ref_info = NULL;
    self->repeat_info_capacity = 0;
    self->repeat_info = NULL;
    self->groups_storage = NULL;
    self->repeats_storage = NULL;
    self->fuzzy_count = 0;
    self->recursive = FALSE;
    self->req_offset = req_offset;
    self->req_string = NULL;
    Py_INCREF(self->pattern);
    Py_INCREF(self->groupindex);
    Py_INCREF(self->indexgroup);
    Py_INCREF(self->named_lists);
    Py_INCREF(self->named_list_indexes);

    /* Initialise the character encoding. */
    unicode = (flags & RE_FLAG_UNICODE) != 0;
    locale = (flags & RE_FLAG_LOCALE) != 0;
    ascii = (flags & RE_FLAG_ASCII) != 0;
    if (!unicode && !locale && !ascii) {
        if (PyString_Check(self->pattern))
            ascii = RE_FLAG_ASCII;
        else
            unicode = RE_FLAG_UNICODE;
    }
    if (unicode)
        self->encoding = &unicode_encoding;
    else if (locale)
        self->encoding = &locale_encoding;
    else if (ascii)
        self->encoding = &ascii_encoding;

    /* Compile the regular expression code to nodes. */
    ok = compile_to_nodes(code, code + code_len, self);

    /* We no longer need the regular expression code. */
    re_dealloc(code);

    if (!ok) {
        Py_DECREF(self);
        re_dealloc(req_chars);
        return NULL;
    }

    /* Make a node for the required string, if there's one. */
    if (req_chars) {
        /* Remove the FULLCASE flag if it's not a Unicode pattern. */
        if (!(self->flags & RE_FLAG_UNICODE))
            req_flags &= ~RE_FLAG_FULLCASE;

        if (self->flags & RE_FLAG_REVERSE) {
            switch (req_flags) {
            case 0:
                self->req_string = make_STRING_node(self, RE_OP_STRING_REV,
                  req_length, req_chars);
                break;
            case RE_FLAG_IGNORECASE | RE_FLAG_FULLCASE:
                self->req_string = make_STRING_node(self, RE_OP_STRING_FLD_REV,
                  req_length, req_chars);
                break;
            case RE_FLAG_IGNORECASE:
                self->req_string = make_STRING_node(self, RE_OP_STRING_IGN_REV,
                  req_length, req_chars);
                break;
            }
        } else {
            switch (req_flags) {
            case 0:
                self->req_string = make_STRING_node(self, RE_OP_STRING,
                  req_length, req_chars);
                break;
            case RE_FLAG_IGNORECASE | RE_FLAG_FULLCASE:
                self->req_string = make_STRING_node(self, RE_OP_STRING_FLD,
                  req_length, req_chars);
                break;
            case RE_FLAG_IGNORECASE:
                self->req_string = make_STRING_node(self, RE_OP_STRING_IGN,
                  req_length, req_chars);
                break;
            }
        }

        re_dealloc(req_chars);
    }

    return (PyObject*)self;

error:
    re_dealloc(code);
    set_error(RE_ERROR_ILLEGAL, NULL);
    return NULL;
}

/* Gets the size of the codewords. */
static PyObject* get_code_size(PyObject* self, PyObject* unused) {
    return Py_BuildValue("n", sizeof(RE_CODE));
}

/* Gets the property dict. */
static PyObject* get_properties(PyObject* self_, PyObject* args) {
    Py_INCREF(property_dict);

    return property_dict;
}

/* Folds the case of a string. */
static PyObject* fold_case(PyObject* self_, PyObject* args) {
    RE_StringInfo str_info;
    Py_UCS4 (*char_at)(void* text, Py_ssize_t pos);
    Py_ssize_t folded_charsize;
    void (*set_char_at)(void* text, Py_ssize_t pos, Py_UCS4 ch);
    RE_EncodingTable* encoding;
    Py_ssize_t buf_size;
    void* folded;
    Py_ssize_t folded_len;
    PyObject* result;

    Py_ssize_t flags;
    PyObject* string;
    if (!PyArg_ParseTuple(args, "nO:fold_case", &flags, &string))
        return NULL;

    if (!(flags & RE_FLAG_IGNORECASE)) {
        Py_INCREF(string);
        return string;
    }

    /* Get the string. */
    if (!get_string(string, &str_info))
        return NULL;

    /* Get the function for reading from the original string. */
    switch (str_info.charsize) {
    case 1:
        char_at = bytes1_char_at;
        break;
    case 2:
        char_at = bytes2_char_at;
        break;
    case 4:
        char_at = bytes4_char_at;
        break;
    default:
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        return NULL;
    }

    /* What's the encoding? */
    if (flags & RE_FLAG_UNICODE)
        encoding = &unicode_encoding;
    else if (flags & RE_FLAG_LOCALE)
        encoding = &locale_encoding;
    else if (flags & RE_FLAG_ASCII)
        encoding = &ascii_encoding;
    else
        encoding = &unicode_encoding;

    /* The folded string will have the same width as the original string. */
    folded_charsize = str_info.charsize;

    /* Get the function for writing to the folded string. */
    switch (folded_charsize) {
    case 1:
        set_char_at = bytes1_set_char_at;
        break;
    case 2:
        set_char_at = bytes2_set_char_at;
        break;
    case 4:
        set_char_at = bytes4_set_char_at;
        break;
    default:
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        return NULL;
    }

    /* Allocate a buffer for the folded string. */
    if (flags & RE_FLAG_FULLCASE)
        /* When using full case-folding with Unicode, some single codepoints
         * are transformed to sequences of codepoints.
         */
        buf_size = str_info.length * RE_MAX_FOLDED;
    else
        buf_size = str_info.length;

    folded = re_alloc(buf_size * folded_charsize);
    if (!folded) {
#if PY_VERSION_HEX >= 0x02060000
        release_buffer(&str_info);

#endif
        return NULL;
    }

    /* Fold the case of the string. */
    folded_len = 0;

    if (flags & RE_FLAG_FULLCASE) {
        /* Full case-folding. */
        int (*full_case_fold)(Py_UCS4 ch, Py_UCS4* folded);
        Py_ssize_t i;
        Py_UCS4 codepoints[RE_MAX_FOLDED];

        full_case_fold = encoding->full_case_fold;

        for (i = 0; i < str_info.length; i++) {
            int count;
            int j;

            count = full_case_fold(char_at(str_info.characters, i),
              codepoints);
            for (j = 0; j < count; j++)
                set_char_at(folded, folded_len + j, codepoints[j]);

            folded_len += count;
        }
    } else {
        /* Simple case-folding. */
        Py_UCS4 (*simple_case_fold)(Py_UCS4 ch);
        Py_ssize_t i;

        simple_case_fold = encoding->simple_case_fold;

        for (i = 0; i < str_info.length; i++) {
            Py_UCS4 ch;

            ch = simple_case_fold(char_at(str_info.characters, i));
            set_char_at(folded, i, ch);
        }

        folded_len = str_info.length;
    }

    /* Build the result string. */
    if (str_info.is_unicode)
        result = build_unicode_value(folded, folded_len, folded_charsize);
    else
        result = build_bytes_value(folded, folded_len, folded_charsize);

    re_dealloc(folded);

#if PY_VERSION_HEX >= 0x02060000
    /* Release the original string's buffer. */
    release_buffer(&str_info);

#endif
    return result;
}

/* Returns a tuple of the Unicode characters which expand on full case-folding.
 */
static PyObject* get_expand_on_folding(PyObject* self, PyObject* unused) {
    int count;
    int i;
    PyObject* result;

    /* How many characters are there? */
    count = sizeof(re_expand_on_folding) / sizeof(re_expand_on_folding[0]);

    /* Put all the characters in a tuple. */
    result = PyTuple_New(count);
    if (!result)
        goto error;

    for (i = 0; i < count; i++) {
        Py_UNICODE codepoint;
        PyObject* item;

        codepoint = re_expand_on_folding[i];

        item = build_unicode_value(&codepoint, 1, sizeof(codepoint));
        if (!item)
            goto error;

        PyTuple_SetItem(result, i, item);
    }

    return result;

error:
    Py_XDECREF(result);

    return NULL;
}

/* Returns whether a character has a given value for a Unicode property. */
static PyObject* has_property_value(PyObject* self_, PyObject* args) {
    BOOL v;

    Py_ssize_t property_value;
    Py_ssize_t character;
    if (!PyArg_ParseTuple(args, "nn:has_property_value", &property_value,
      &character))
        return NULL;

    v = unicode_has_property((RE_CODE)property_value, (Py_UCS4)character) ? 1 :
      0;

    return Py_BuildValue("n", v);
}

/* Returns a list all the simple cases of a character.
 *
 * If full case-folding is turned on and the character also expands on full
 * case-folding, a None is appended to the list.
 */
static PyObject* get_all_cases(PyObject* self_, PyObject* args) {
    RE_EncodingTable* encoding;
    int count;
    Py_UCS4 cases[RE_MAX_CASES];
    Py_UCS4 folded[RE_MAX_FOLDED];
    PyObject* result;
    int i;

    Py_ssize_t flags;
    Py_ssize_t character;
    if (!PyArg_ParseTuple(args, "nn:get_all_cases", &flags, &character))
        return NULL;

    /* What's the encoding? */
    if (flags & RE_FLAG_UNICODE)
        encoding = &unicode_encoding;
    else if (flags & RE_FLAG_LOCALE)
        encoding = &locale_encoding;
    else if (flags & RE_FLAG_ASCII)
        encoding = &ascii_encoding;
    else
        encoding = &ascii_encoding;

    /* Get all the simple cases. */
    count = encoding->all_cases((Py_UCS4)character, cases);

    result = PyList_New(count);
    if (!result)
        goto error;

    for (i = 0; i < count; i++) {
        PyObject* item;

        item = Py_BuildValue("n", cases[i]);
        if (!item)
            goto error;

        PyList_SetItem(result, i, item);
    }

    /* If the character also expands on full case-folding, append a None. */
    if ((flags & RE_FULL_CASE_FOLDING) == RE_FULL_CASE_FOLDING) {
        count = encoding->full_case_fold((Py_UCS4)character, folded);
        if (count > 1)
            PyList_Append(result, Py_None);
    }

    return result;

error:
    Py_XDECREF(result);

    return NULL;
}

/* The table of the module's functions. */
static PyMethodDef _functions[] = {
    {"compile", (PyCFunction)re_compile, METH_VARARGS},
    {"get_code_size", (PyCFunction)get_code_size, METH_NOARGS},
    {"get_properties", (PyCFunction)get_properties, METH_VARARGS},
    {"fold_case", (PyCFunction)fold_case, METH_VARARGS},
    {"get_expand_on_folding", (PyCFunction)get_expand_on_folding, METH_NOARGS},
    {"has_property_value", (PyCFunction)has_property_value, METH_VARARGS},
    {"get_all_cases", (PyCFunction)get_all_cases, METH_VARARGS},
    {NULL, NULL}
};

/* Initialises the property dictionary. */
static BOOL init_property_dict(void) {
    int value_set_count;
    int i;
    PyObject** value_dicts;

    property_dict = NULL;

    /* How many value sets are there? */
    value_set_count = 0;

    for (i = 0; i < sizeof(re_property_values) / sizeof(re_property_values[0]);
      i++) {
        RE_PropertyValue* value;

        value = &re_property_values[i];
        if (value->value_set >= value_set_count)
            value_set_count = value->value_set + 1;
    }

    /* Quick references for the value sets. */
    value_dicts = (PyObject**)re_alloc(value_set_count *
      sizeof(value_dicts[0]));
    if (!value_dicts)
        return FALSE;

    memset(value_dicts, 0, value_set_count * sizeof(value_dicts[0]));

    /* Build the property values dictionaries. */
    for (i = 0; i < sizeof(re_property_values) / sizeof(re_property_values[0]);
      i++) {
        RE_PropertyValue* value;
        PyObject* v;

        value = &re_property_values[i];
        if (!value_dicts[value->value_set]) {
            value_dicts[value->value_set] = PyDict_New();
            if (!value_dicts[value->value_set])
                goto error;
        }

        v = Py_BuildValue("i", value->id);
        if (!v)
            goto error;

        PyDict_SetItemString(value_dicts[value->value_set],
          re_strings[value->name], v);
    }

    /* Build the property dictionary. */
    property_dict = PyDict_New();
    if (!property_dict)
        goto error;

    for (i = 0; i < sizeof(re_properties) / sizeof(re_properties[0]); i++) {
        RE_Property* property;
        PyObject* v;

        property = &re_properties[i];
        v = Py_BuildValue("iO", property->id,
          value_dicts[property->value_set]);
        if (!v)
            goto error;

        PyDict_SetItemString(property_dict, re_strings[property->name], v);
    }

    /* DECREF the value sets. Any unused ones will be deallocated. */
    for (i = 0; i < value_set_count; i++)
        Py_XDECREF(value_dicts[i]);

    re_dealloc(value_dicts);

    return TRUE;

error:
    Py_XDECREF(property_dict);

    /* DECREF the value sets. */
    for (i = 0; i < value_set_count; i++)
        Py_XDECREF(value_dicts[i]);

    re_dealloc(value_dicts);

    return FALSE;
}

/* Initialises the module. */
PyMODINIT_FUNC init_regex(void) {
    PyObject* m;
    PyObject* d;
    PyObject* x;
#if defined(VERBOSE)
    /* Unbuffered in case it crashes! */
    setvbuf(stdout, NULL, _IONBF, 0);
#endif

    /* Initialise Pattern_Type. */
    Pattern_Type.tp_dealloc = pattern_dealloc;
    Pattern_Type.tp_repr = pattern_repr;
    Pattern_Type.tp_flags = Py_TPFLAGS_HAVE_WEAKREFS;
    Pattern_Type.tp_doc = pattern_doc;
    Pattern_Type.tp_weaklistoffset = offsetof(PatternObject, weakreflist);
    Pattern_Type.tp_methods = pattern_methods;
    Pattern_Type.tp_members = pattern_members;
    Pattern_Type.tp_getset = pattern_getset;

    /* Initialise Match_Type. */
    Match_Type.tp_dealloc = match_dealloc;
    Match_Type.tp_as_mapping = &match_as_mapping;
    Match_Type.tp_flags = Py_TPFLAGS_DEFAULT;
    Match_Type.tp_doc = match_doc;
    Match_Type.tp_methods = match_methods;
    Match_Type.tp_members = match_members;
    Match_Type.tp_getset = match_getset;

    /* Initialise Scanner_Type. */
    Scanner_Type.tp_dealloc = scanner_dealloc;
    Scanner_Type.tp_flags = Py_TPFLAGS_DEFAULT;
    Scanner_Type.tp_doc = scanner_doc;
    Scanner_Type.tp_iter = scanner_iter;
    Scanner_Type.tp_iternext = scanner_iternext;
    Scanner_Type.tp_methods = scanner_methods;
    Scanner_Type.tp_members = scanner_members;

    /* Initialise Splitter_Type. */
    Splitter_Type.tp_dealloc = splitter_dealloc;
    Splitter_Type.tp_flags = Py_TPFLAGS_DEFAULT;
    Splitter_Type.tp_doc = splitter_doc;
    Splitter_Type.tp_iter = splitter_iter;
    Splitter_Type.tp_iternext = splitter_iternext;
    Splitter_Type.tp_methods = splitter_methods;
    Splitter_Type.tp_members = splitter_members;

    /* Initialize object types */
    if (PyType_Ready(&Pattern_Type) < 0)
        return;
    if (PyType_Ready(&Match_Type) < 0)
        return;
    if (PyType_Ready(&Scanner_Type) < 0)
        return;
    if (PyType_Ready(&Splitter_Type) < 0)
        return;

    error_exception = NULL;

    m = Py_InitModule("_" RE_MODULE, _functions);
    if (!m)
        return;

    d = PyModule_GetDict(m);

    x = PyInt_FromLong(RE_MAGIC);
    if (x) {
        PyDict_SetItemString(d, "MAGIC", x);
        Py_DECREF(x);
    }

    x = PyInt_FromLong(sizeof(RE_CODE));
    if (x) {
        PyDict_SetItemString(d, "CODE_SIZE", x);
        Py_DECREF(x);
    }

    x = PyString_FromString(copyright);
    if (x) {
        PyDict_SetItemString(d, "copyright", x);
        Py_DECREF(x);
    }

    /* Initialise the property dictionary. */
    if (!init_property_dict())
        return;
}

/* vim:ts=4:sw=4:et */
