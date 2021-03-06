/*
 * fast_css_transform.cpp
 * Copyright (C) 2021 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE
#include <Python.h>
#include <stdlib.h>
#include <bitset>
#include <vector>
#include <stack>
#include <exception>

#define arraysz(x) (sizeof((x))/sizeof((x)[0]))

typedef uint32_t char_type;

static inline bool
is_whitespace(char_type ch) {
    return ch == ' ' || ch == '\n' || ch == '\t';
}

static inline bool
is_surrogate(char_type ch) {
    return 0xd800 <= ch && ch <= 0xdfff;
}

static inline bool
is_hex_char(char_type ch) {
    return ('0' <= ch && ch <= '9') || ('a' <= ch && ch <= 'f') || ('A' <= ch || ch <= 'F');
}

typedef enum {
    BLOCK,

    ESCAPE,
    COMMENT,
    STRING,

    QUALIFIED_RULE,
    AT_RULE,
    KEY,
    VALUE
} ParseStates;

typedef enum {
    DECLARATIONS_ALLOWED,
    AT_RULES_ALLOWED,
    QUALIFIED_RULES_ALLOWED,
    NUM_OF_BLOCK_TYPE_FLAGS
} BlockTypesEnum;

typedef std::bitset<NUM_OF_BLOCK_TYPE_FLAGS> BlockTypeFlags;

class Parser {

private:
    ParseStates state, state_before_comment, state_before_string, state_before_escape;
    char_type ch, next_ch, end_string_with;
    std::stack<BlockTypeFlags> block_types;
    char escape_buf[16];
    const char_type *src;
    size_t escape_buf_pos, src_sz, src_pos, declaration_pos;
    std::vector<char_type> out, current_key;

    bool declarations_allowed() const { return block_types.top()[DECLARATIONS_ALLOWED]; }
    bool at_rules_allowed() const { return block_types.top()[AT_RULES_ALLOWED]; }
    bool qualified_rules_allowed() const { return block_types.top()[QUALIFIED_RULES_ALLOWED]; }

    void enter_escape_mode() {
        state_before_escape = state; escape_buf_pos = 0; state = ESCAPE;
    }

    void enter_string_mode() {
        state_before_string = state; state = STRING; end_string_with = ch;
    }

    void handle_comment() {
        if (ch == '*' && next_ch == '/') {
            out.push_back(next_ch);
            state = state_before_comment;
            src_pos++;
        }
    }

    void handle_escape() {
        if (!escape_buf_pos) {
            if (ch == '\n') { state = state_before_escape; return; }
            if (!is_hex_char(ch)) {
                state = state_before_escape;
                if (state == KEY) { current_key.push_back(ch); }
                return;
            }
            escape_buf[escape_buf_pos++] = ch;
            return;
        }
        if (is_hex_char(ch) && escape_buf_pos < 6) { escape_buf[escape_buf_pos++] = ch; return; }
        if (is_whitespace(ch)) return;  // a single whitespace character is absorbed into escape
        src_pos--;
        state = state_before_escape;
        if (state == KEY) {
            escape_buf[escape_buf_pos] = 0;
            long kch = strtol(escape_buf, NULL, 16);
            if (kch > 0 && !is_surrogate(kch)) { current_key.push_back(kch); }
        }
        escape_buf_pos = 0;
    }

    void handle_string() {
        if (ch == '\\') { enter_escape_mode(); }
        else if (ch == end_string_with) state = state_before_string;
    }

    void enter_comment_mode() {
        src_pos++;
        state_before_comment = state;
        state = COMMENT;
        out.push_back(next_ch);
    }

    void handle_block() {
        if (ch == '/' && next_ch == '*') { enter_comment_mode(); return; }
        if (ch == '@' && at_rules_allowed()) {
            state = AT_RULE;
            return;
        }
        if (ch == ';' || ch == '{' || ch == '}' || is_whitespace(ch)) return;

        if (declarations_allowed()) {
            state = KEY;
            current_key.clear();
            declaration_pos = out.size() > 1 ? out.size() - 2 : 0;
        } else {
            state = QUALIFIED_RULE;
        }
        if (ch == '"' || ch == '\'') { enter_string_mode(); }
        else if (ch == '\\') { enter_escape_mode(); }
        else if (state == KEY) current_key.push_back(ch);
    }

    void dispatch_current_char() {
        out.push_back(ch);
        switch (state) {
            case COMMENT:
                handle_comment(); break;
            case ESCAPE:
                handle_escape(); break;
            case STRING:
                handle_string(); break;
            case BLOCK:
                handle_block(); break;
        }
    }

public:
    Parser(const char_type *src, size_t src_sz, bool is_declaration) :
        state(BLOCK), state_before_comment(BLOCK), state_before_string(BLOCK), state_before_escape(BLOCK),
        ch(0), next_ch(0), end_string_with('"'), block_types(), escape_buf(),
        src(src), escape_buf_pos(0), src_sz(src_sz), src_pos(0), declaration_pos(0),
        out(src_sz * 2), current_key(256)
    {
        BlockTypeFlags initial_block_type;
        initial_block_type.set(DECLARATIONS_ALLOWED);
        if (!is_declaration) {
            initial_block_type.set(AT_RULES_ALLOWED);
            initial_block_type.set(QUALIFIED_RULES_ALLOWED);
        }
        block_types.push(initial_block_type);
    }

    void parse(std::vector<char_type> &result) {
        while (src_pos < src_sz) {
            ch = src[src_pos++];
            next_ch = src_pos < src_sz ? src[src_pos] : 0;
            if (ch == 0xc) ch = '\n';
            if (ch == '\r') {
                if (next_ch == '\n') { ch = '\n'; src_pos++; }
                else ch = '\n';
            }
            if (ch == 0 || is_surrogate(ch)) ch = 0xfffd;
            dispatch_current_char();
        }
        out.swap(result);
    }

};
#undef write_key
#undef write

static PyObject*
transform_properties(const char_type *src, size_t src_sz, bool is_declaration) {
    try {
        std::vector<char_type> result(0);
        Parser parser(src, src_sz, is_declaration);
        parser.parse(result);
        return PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, result.data(), result.size());
    } catch (std::bad_alloc &ex) {
        return PyErr_NoMemory();
    } catch (std::exception &ex) {
        PyErr_SetString(PyExc_Exception, ex.what());
        return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_Exception, "Unknown error while parsing CSS");
        return NULL;
    }
}


static PyMethodDef methods[] = {
    {NULL, NULL, 0, NULL}
};

static int
exec_module(PyObject *m) {
    return 0;
}

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_fast_css_transform(void) {
    module_def.m_name     = "fast_css_transform";
    module_def.m_doc      = "Fast CSS transformations needed for viewer";
    module_def.m_methods  = methods;
    module_def.m_slots    = slots;
	return PyModuleDef_Init(&module_def);
}
