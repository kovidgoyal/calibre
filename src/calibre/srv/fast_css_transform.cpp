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
#include <stdexcept>
#include <string>

// character classes {{{
static inline bool
is_whitespace(char32_t ch) {
    return ch == ' ' || ch == '\n' || ch == '\t';
}

static inline bool
is_surrogate(char32_t ch) {
    return 0xd800 <= ch && ch <= 0xdfff;
}

static inline bool
is_hex_char(char32_t ch) {
    return ('0' <= ch && ch <= '9') || ('a' <= ch && ch <= 'f') || ('A' <= ch || ch <= 'F');
}

static inline bool
is_letter(char32_t ch) {
    return ('a' <= ch && ch <= 'z') || ('A' <= ch && ch <= 'Z');
}

static inline bool
is_name_start(char32_t ch) {
    return is_letter(ch) || ch == '_' || ch >= 0x80;
}

static inline bool
is_digit(char32_t ch) {
    return '0' <= ch && ch <= '9';
}

static inline bool
is_name(char32_t ch) {
    return is_name_start(ch) || is_digit(ch) || ch == '-';
}
// }}}

enum class TokenType : unsigned int {
    whitespace,
    delimiter,
    ident,
    function,
    at_keyword,
    hash,
    string,
    url,
    function_start,
    number,
    dimension,
    percentage,
    comment,
    cdo,
    cdc
} TokenTypes;


class Token {
    private:
        TokenType type;
        std::u32string text;
        unsigned unit_at;

        void clear() {
            type = TokenType::whitespace;
            text.clear();
            unit_at = 0;
        }

    public:
        Token() : type(TokenType::whitespace), text(), unit_at(0) { text.reserve(16); }
        Token(const TokenType type, const char32_t ch) : type(type), text(), unit_at(0) { text.reserve(16); text.push_back(ch); }
        Token(const Token& other) : type(other.type), text(other.text), unit_at(other.unit_at) {} // copy constructor
        Token(Token&& other) : type(other.type), text(std::move(other.text)), unit_at(other.unit_at) {} // move constructor
        Token& operator=(const Token& other) { type = other.type; text = other.text; unit_at = other.unit_at; return *this; } // copy assignment
        Token& operator=(Token&& other) { type = other.type; text = std::move(other.text); unit_at = other.unit_at; return *this; } // move assignment

        void set_type(const TokenType q) { type = q; }
        bool is_type(const TokenType q) const { return type == q; }
        void add_char(const char32_t ch) { text.push_back(ch); }
        void mark_unit() { unit_at = text.size(); }
        void clear_text() { text.clear(); }

        bool text_equals_case_insensitive(const char *lowercase_text) const {
            const char32_t* str = text.c_str();
            const unsigned char* q = reinterpret_cast<const unsigned char*>(lowercase_text);
            static const char delta = 'a' - 'A';
            for (unsigned i = 0; ; i++) {
                if (!str[i]) return q[i] ? false : true;
                if (!q[i]) return false;
                if (str[i] != q[i] && str[i] + delta != q[i]) return false;
            }
            return true;
        }

        void trim_trailing_whitespace() {
            while(text.size() && is_whitespace(text.back())) text.pop_back();
        }
};

class TokenQueue {
    private:
        std::stack<Token> pool;
        std::vector<Token> queue;

        void new_token(const TokenType type, const char32_t ch = 0) {
            if (pool.empty()) queue.emplace_back(type, ch);
            else {
                queue.push_back(std::move(pool.top())); pool.pop();
                queue.back().set_type(type);
                if (ch) queue.back().add_char(ch);
            }
        }

        void add_char_of_type(const TokenType type, const char32_t ch) {
            if (!queue.empty() && queue.back().is_type(type)) queue.back().add_char(ch);
            else new_token(type, ch);
        }
    public:
        TokenQueue() : pool(), queue() {}

        bool current_token_text_equals_case_insensitive(const char *lowercase_text) const {
            if (queue.empty()) return false;
            return queue.back().text_equals_case_insensitive(lowercase_text);
        }

        void add_whitespace(const char32_t ch) { add_char_of_type(TokenType::whitespace, ch); }

        void start_string() {
            if (queue.empty() || !queue.back().is_type(TokenType::string)) new_token(TokenType::string);
        }

        void add_comment(const char32_t ch) {
            new_token(TokenType::comment, ch);
        }

        void add_char(const char32_t ch) {
            if (queue.empty()) throw std::logic_error("Attempting to add char to non-existent token");
            queue.back().add_char(ch);
        }

        void make_function_start(bool is_url = false) {
            if (queue.empty()) throw std::logic_error("Attempting to make function start with non-existent token");
            queue.back().set_type(is_url ? TokenType::url : TokenType::function_start);
            if (is_url) queue.back().clear_text();
        }

        void add_delimiter(const char32_t ch) { new_token(TokenType::delimiter, ch); }

        void add_hash() { new_token(TokenType::hash, '#'); }

        void add_at_keyword() { new_token(TokenType::at_keyword, '@'); }

        void add_number(const char32_t ch) { new_token(TokenType::number, ch); }

        void add_ident(const char32_t ch) { new_token(TokenType::ident, ch); }

        void add_cdc() { new_token(TokenType::cdc, '-'); queue.back().add_char('-'); queue.back().add_char('>'); }
        void add_cdo() { new_token(TokenType::cdo, '<'); queue.back().add_char('-'); queue.back().add_char('-'); }

        void mark_unit() {
            if (queue.empty()) throw std::logic_error("Attempting to mark unit with no token present");
            queue.back().mark_unit();
            queue.back().set_type(TokenType::dimension);
        }

        void trim_trailing_whitespace() {
            if (!queue.empty()) queue.back().trim_trailing_whitespace();
        }
};

enum class ParseState : unsigned int {
    normal,
    escape,
    comment,
    string,
    hash,
    number,
    digits,
    dimension,
    ident,
    url, url_start, url_string, url_after_string,
    at_keyword,
};

typedef enum {
    DECLARATIONS_ALLOWED,
    AT_RULES_ALLOWED,
    QUALIFIED_RULES_ALLOWED,
    NUM_OF_BLOCK_TYPE_FLAGS
} BlockTypesEnum;

typedef std::bitset<NUM_OF_BLOCK_TYPE_FLAGS> BlockTypeFlags;

class InputStream {
    private:
        const char32_t *src;
        size_t pos;
        const size_t src_sz;

        char32_t peek_one(size_t at, unsigned *consumed) const {
            if (at >= src_sz) { *consumed = 0; return 0; }
            *consumed = 1;
            char32_t ch = src[at];
            if (ch == 0xc) ch = '\n';
            else if (ch == '\r') {
                ch = '\n';
                if (at + 1 < src_sz && src[at + 1] == '\n') *consumed = 2;
            }
            else if (ch == 0 || is_surrogate(ch)) ch = 0xfffd;
            return ch;
        }

    public:
        InputStream(const char32_t *src, size_t sz) : src(src), pos(0), src_sz(sz) { }

        char32_t next() {
            unsigned last_step_size;
            char32_t ans = peek_one(pos, &last_step_size);
            pos += last_step_size;
            return ans;
        }

        void rewind() {
            if (!pos) throw std::logic_error("Cannot rewind already at start of stream");
            pos -= (src[pos-1] == '\n' && pos >= 2 && src[pos-2] == '\r') ? 2 : 1;
        }

        char32_t peek(unsigned amt = 0) const {
            char32_t ans = 0;
            size_t at = pos;
            unsigned consumed;
            while(true) {
                ans = peek_one(at, &consumed);
                if (!amt || !ans) break;
                at += consumed;
                amt--;
            }
            return ans;
        }
}; // end InputStream

class Parser {

    private:
        char32_t ch, end_string_with, prev_ch;
        std::stack<BlockTypeFlags> block_types;
        std::stack<ParseState> states;
        char escape_buf[16];
        size_t escape_buf_pos, declaration_pos;
        std::u32string out;
        TokenQueue token_queue;
        InputStream input;

        bool declarations_allowed() const { return block_types.top()[DECLARATIONS_ALLOWED]; }
        bool at_rules_allowed() const { return block_types.top()[AT_RULES_ALLOWED]; }
        bool qualified_rules_allowed() const { return block_types.top()[QUALIFIED_RULES_ALLOWED]; }

        // testing stream contents {{{
        void rewind_output() { out.pop_back(); }
        void write_to_output(const char32_t what) { out.push_back(what); }
        void reconsume() { input.rewind(); rewind_output(); }

        char32_t peek(int which = 0) const { return which < 0 ? ch : input.peek(which); }

        bool starting_comment() const { return ch == '/' && peek() == '*'; }

        bool starting_string() const { return ch == '"' || ch == '\''; }

        bool has_valid_escape_next(int offset=0) const {
            if (peek(offset) != '\\') return false;
            char32_t second = peek(offset + 1);
            return second > 0 && second != '\n';
        }

        bool has_valid_escape() const { return has_valid_escape_next(-1); }

        bool has_identifier_next(int offset = 0) const {
            char32_t first = peek(offset);
            switch(first) {
                case 0:
                    return false;
                case '\\':
                    return has_valid_escape_next(offset);
                case '-': {
                    char32_t second = peek(offset + 1);
                    if (is_name_start(second) || second == '-') return true;
                    if (second == '\\') {
                        char32_t third = peek(offset + 2);
                        return third > 0 && third != '\n';
                    }
                    return false;
                }
                default:
                    return is_name_start(first);
            }
        }

        bool has_identifier() const { return has_identifier_next(-1); }
        // }}}

        // escape {{{
        void enter_escape_mode() {
            states.push(ParseState::escape);
            escape_buf_pos = 0;
        }

        void handle_escape() {
            if (!escape_buf_pos) {
                if (ch == '\n') { reconsume(); states.pop(); return; }
                if (!is_hex_char(ch)) {
                    states.pop();
                    token_queue.add_char(ch);
                    return;
                }
                escape_buf[escape_buf_pos++] = ch;
                return;
            }
            if (is_hex_char(ch) && escape_buf_pos < 6) { escape_buf[escape_buf_pos++] = ch; return; }
            if (is_whitespace(ch)) return;  // a single whitespace character is absorbed into escape
            reconsume();
            states.pop();
            escape_buf[escape_buf_pos] = 0;
            long kch = strtol(escape_buf, NULL, 16);
            if (kch > 0 && !is_surrogate(kch)) token_queue.add_char(kch);
            escape_buf_pos = 0;
        }
        // }}}

        // string {{{
        void enter_string_mode() {
            states.push(ParseState::string);
            end_string_with = ch;
            token_queue.start_string();
        }

        void handle_string() {
            if (ch == '\\') {
                if (peek() == '\n') input.next();
                else enter_escape_mode();
            }
            else if (ch == end_string_with) states.pop();
            else token_queue.add_char(ch);
        } // }}}

        // comment {{{
        void enter_comment_mode() {
            states.push(ParseState::comment);
            token_queue.add_comment(ch);
        }

        void handle_comment() {
            token_queue.add_char(ch);
            if (ch == '/' && prev_ch == '*') states.pop();
        } // }}}

        // hash {{{
        void enter_hash_mode() {
            states.push(ParseState::hash);
            token_queue.add_hash();
        }

        void handle_name() {
            if (is_name(ch)) token_queue.add_char(ch);
            else if (has_valid_escape()) enter_escape_mode();
            else {
                reconsume();
                states.pop();
            }
        }

        void handle_hash() {
            handle_name();
        } // }}}

        // number {{{
        void enter_number_mode() {
            states.push(ParseState::number);
            token_queue.add_number(ch);
        }

        void handle_number() {
            if (is_digit(ch)) { token_queue.add_char(ch); return; }
            if (ch == '.' && is_digit(peek())) { states.pop(); enter_digits_mode(); return; }
            if ((ch == 'e' || ch == 'E')) {
                char32_t next = peek();
                if (is_digit(next) || ((next == '+' || next == '-') && is_digit(peek(1)))) {
                    token_queue.add_char(input.next()); token_queue.add_char(input.next());
                    states.pop();
                    enter_digits_mode();
                    return;
                }
            }
            reconsume();
            states.pop();
            if (has_identifier_next()) { enter_dimension_mode(); }
        }  // }}}

        // digits {{{
        void enter_digits_mode() {
            states.push(ParseState::digits);
        }

        void handle_digits() {
            if (is_digit(ch)) { token_queue.add_char(ch); }
            else {
                reconsume();
                states.pop();
                if (has_identifier_next()) { enter_dimension_mode(); }
            }
        } // }}}

        // dimension {{{
        void enter_dimension_mode() {
            token_queue.mark_unit();
            states.push(ParseState::dimension);
        }

        void handle_dimension() {
            if (is_name(ch)) { token_queue.add_char(ch); return; }
            if (has_valid_escape()) { enter_escape_mode(); return; }
            reconsume();
            states.pop();
        } // }}}

        // ident {{{
        void enter_ident_mode(const char32_t starting_ch = 0) {
            token_queue.add_ident(starting_ch);
            states.push(ParseState::ident);
        }

        void handle_ident() {
            if (is_name(ch)) { token_queue.add_char(ch); return; }
            if (has_valid_escape()) { enter_escape_mode(); return; }
            if (ch == '(') {
                if (token_queue.current_token_text_equals_case_insensitive("url")) {
                    enter_url_start_mode();
                }
                else token_queue.make_function_start();
                return;
            }
            reconsume();
            states.pop();
        } // }}}

        // url {{{
        void enter_url_start_mode() {
            token_queue.make_function_start(true);
            states.push(ParseState::url_start);
        }

        void handle_url_start() {
            if (is_whitespace(ch)) return;
            if (starting_string()) { states.pop(); end_string_with = ch; states.push(ParseState::url_string); return; }
            if (ch == ')') { states.pop(); return; }
            states.pop(); states.push(ParseState::url);
        }

        void handle_url_string() {
            handle_string();
            if (states.top() != ParseState::url_string && states.top() != ParseState::escape) states.push(ParseState::url_after_string);
        }

        void handle_url_after_string() {
            if (!is_whitespace(ch)) exit_url_mode();
        }

        void handle_url() {
            if (has_valid_escape()) enter_escape_mode();
            else if (ch == ')') exit_url_mode(true);
        }

        void exit_url_mode(bool trim=false) {
            states.pop();
            if (trim) token_queue.trim_trailing_whitespace();
        }
        // }}}

        // hash {{{
        void enter_at_keyword() {
            states.push(ParseState::at_keyword);
            token_queue.add_at_keyword();
        }

        void handle_at_keyword() {
            handle_name();
        } // }}}

        void handle_normal() {
            if (starting_comment()) { enter_comment_mode(); return; }
            if (is_whitespace(ch)) { token_queue.add_whitespace(ch); return; }
            if (is_digit(ch)) { enter_number_mode(); return; }
            if (is_name_start(ch)) { enter_ident_mode(ch); return; }
            switch (ch) {
                case '"':
                case '\'':
                    enter_string_mode();
                    break;
                case '#':
                    if (is_name(peek()) || has_valid_escape_next()) {
                        enter_hash_mode();
                    } else token_queue.add_delimiter(ch);
                    break;
                case '(':
                case ')':
                case '[':
                case ']':
                case '{':
                case '}':
                case ',':
                case ':':
                case ';':
                    token_queue.add_delimiter(ch);
                    break;
                case '+':
                    if (is_digit(peek()) || (peek() == '.' && is_digit(peek(1)))) { enter_number_mode(); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '-':
                    if (is_digit(peek()) || (peek() == '.' && is_digit(peek(1)))) { enter_number_mode(); }
                    else if (peek() == '-' && peek(1) == '>') { token_queue.add_cdc(); write_to_output(input.next()); write_to_output(input.next()); }
                    else if (has_identifier()) { enter_ident_mode(ch); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '.':
                    if (is_digit(peek())) { enter_number_mode(); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '<':
                    if (peek() == '-' && peek(1) == '-') { token_queue.add_cdo(); write_to_output(input.next()); write_to_output(input.next()); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '@':
                    if (has_identifier_next()) enter_at_keyword();
                    else token_queue.add_delimiter(ch);
                    break;
                case '\\':
                    if (has_valid_escape()) { enter_ident_mode(); enter_escape_mode(); }
                    else token_queue.add_delimiter(ch);
                    break;
                default:
                    token_queue.add_delimiter(ch);
                    break;
            }
        }

        void dispatch_current_char() {
            write_to_output(ch);
            switch (states.top()) {
                case ParseState::comment:
                    handle_comment(); break;
                case ParseState::escape:
                    handle_escape(); break;
                case ParseState::string:
                    handle_string(); break;
                case ParseState::hash:
                    handle_hash(); break;
                case ParseState::number:
                    handle_number(); break;
                case ParseState::digits:
                    handle_digits(); break;
                case ParseState::dimension:
                    handle_dimension(); break;
                case ParseState::ident:
                    handle_ident(); break;
                case ParseState::url_start:
                    handle_url_start(); break;
                case ParseState::url_string:
                    handle_url_string(); break;
                case ParseState::url:
                    handle_url(); break;
                case ParseState::url_after_string:
                    handle_url_after_string(); break;
                case ParseState::at_keyword:
                    handle_at_keyword(); break;
                case ParseState::normal:
                    handle_normal(); break;
            }
            prev_ch = ch;
        }


    public:
        Parser(const char32_t *src, const size_t src_sz, const bool is_declaration) :
            ch(0), end_string_with('"'), prev_ch(0), block_types(), states(), escape_buf(),
            escape_buf_pos(0), declaration_pos(0),
            out(), token_queue(), input(src, src_sz)
        {
            out.reserve(src_sz * 2);
            BlockTypeFlags initial_block_type;
            initial_block_type.set(DECLARATIONS_ALLOWED);
            if (!is_declaration) {
                initial_block_type.set(AT_RULES_ALLOWED);
                initial_block_type.set(QUALIFIED_RULES_ALLOWED);
            }
            block_types.push(initial_block_type);
        }

        void parse(std::u32string &result) {
            while (true) {
                ch = input.next();
                if (!ch) break;
                dispatch_current_char();
            }
            out.swap(result);
        }

};

static PyObject*
transform_properties(const char32_t *src, size_t src_sz, bool is_declaration) {
    try {
        std::u32string result;
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
