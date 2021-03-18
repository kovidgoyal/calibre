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
#include <functional>

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

class python_error : public std::runtime_error {
	public:
		python_error(const char *msg) : std::runtime_error(msg) {}
};

class pyobject_raii {
	private:
		PyObject *handle;
		pyobject_raii( const pyobject_raii & ) ;
		pyobject_raii & operator=( const pyobject_raii & ) ;

	public:
		pyobject_raii() : handle(NULL) {}
		pyobject_raii(PyObject* h) : handle(h) {}

		~pyobject_raii() { Py_CLEAR(handle); }

		PyObject *ptr() { return handle; }
		void set_ptr(PyObject *val) { handle = val; }
		PyObject **address() { return &handle; }
		explicit operator bool() const { return handle != NULL; }
        PyObject *detach() { PyObject *ans = handle; handle = NULL; return ans; }
};



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
		size_t out_pos;

        void clear() {
            type = TokenType::whitespace;
            text.clear();
            unit_at = 0;
        }

    public:
        Token() :
			type(TokenType::whitespace), text(), unit_at(0), out_pos(0) {
				text.reserve(16);
			}

        Token(const TokenType type, const char32_t ch, size_t out_pos) :
			type(type), text(), unit_at(0), out_pos(out_pos) {
				text.reserve(16);
				text.push_back(ch);
			}

        Token(const Token& other) :
			type(other.type), text(other.text), unit_at(other.unit_at), out_pos(other.out_pos) {} // copy constructor

        Token(Token&& other) :
			type(other.type), text(std::move(other.text)), unit_at(other.unit_at), out_pos(other.out_pos) {} // move constructor

        Token& operator=(const Token& other) { // copy assignment
			type = other.type; text = other.text; unit_at = other.unit_at; out_pos = other.out_pos; return *this;
		}

        Token& operator=(Token&& other) { // move assignment
			type = other.type; text = std::move(other.text); unit_at = other.unit_at; out_pos = other.out_pos; return *this;
		}

		void reset() {
			text.clear(); unit_at = 0; out_pos = 0; type = TokenType::whitespace;
		}

        void set_type(const TokenType q) { type = q; }
		void set_output_position(const size_t val) { out_pos = val; }
        bool is_type(const TokenType q) const { return type == q; }
        bool is_delimiter(const char32_t ch) const { return type == TokenType::delimiter && text.size() == 1 && text[0] == ch; }
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

		bool is_keyword_case_insensitive(const char *lowercase_text) const {
			return type == TokenType::ident && text_equals_case_insensitive(lowercase_text);
		}

        void trim_trailing_whitespace() {
            while(text.size() && is_whitespace(text.back())) text.pop_back();
        }

		bool is_significant() const {
			switch(type) {
				case TokenType::whitespace:
				case TokenType::comment:
				case TokenType::cdo:
				case TokenType::cdc:
					return false;
				default:
					return true;
			}
		}

		PyObject* text_as_python_string() const {
			PyObject *ans = PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, text.data(), text.size());
			if (ans == NULL) throw python_error("Failed to convert token value to python unicode object");
			return ans;
		}

		void set_text_from_python_string(const PyObject* src) {
			if (PyUnicode_READY(src) != 0) throw python_error("Failed to set token value from unicode object as readying the unicode obect failed");
			text.clear();
			int kind = PyUnicode_KIND(src); void *data = PyUnicode_DATA(src);
			for (Py_ssize_t i = 0; i < PyUnicode_GET_LENGTH(src); i++) text.push_back(PyUnicode_READ(kind, data, i));
		}
};

class TokenQueue {
    private:
        std::stack<Token> pool;
        std::vector<Token> queue;
        std::u32string out;
		pyobject_raii url_callback;

        void new_token(const TokenType type, const char32_t ch = 0) {
            if (pool.empty()) queue.emplace_back(type, ch, current_output_position());
            else {
                queue.push_back(std::move(pool.top())); pool.pop();
                queue.back().set_type(type);
                queue.back().set_output_position(current_output_position());
                if (ch) queue.back().add_char(ch);
            }
        }

		size_t current_output_position() const { return out.size(); }

        void add_char_of_type(const TokenType type, const char32_t ch) {
            if (!queue.empty() && queue.back().is_type(type)) queue.back().add_char(ch);
            else new_token(type, ch);
        }

		void return_tokens_to_pool() {
			while (queue.size()) {
				queue.back().reset();
				pool.push(std::move(queue.back()));
				queue.pop_back();
			}
		}

		const Token* leading_token_of_type(TokenType q) const {
			for (const auto& tok : queue) {
				if (tok.is_significant()) {
					return tok.is_type(q) ? &tok : NULL;
				}
			}
			return NULL;
		}

		Token* leading_token_of_type(TokenType q) {
			for (auto& tok : queue) {
				if (tok.is_significant()) {
					return tok.is_type(q) ? &tok : NULL;
				}
			}
			return NULL;
		}

		bool process_urls(const TokenType type = TokenType::url) {
			bool changed = false;
			if (url_callback) {
				for (auto& tok : queue) {
					if (tok.is_type(type)) {
						pyobject_raii url(tok.text_as_python_string());
						pyobject_raii new_url(PyObject_CallFunctionObjArgs(url_callback.ptr(), url.ptr(), NULL));
						if (!new_url) { PyErr_Print(); }
						else {
							if (PyUnicode_Check(new_url.ptr()) && new_url.ptr() != url.ptr()) {
								tok.set_text_from_python_string(new_url.ptr());
								changed = true;
							}
						}
					}
				}
			}
			return changed;
		}

		bool process_declaration() {
			bool changed = false;
			bool colon_found = false, key_found = false;
			std::function<bool(std::vector<Token>::iterator)> process_values;

			for (auto it = queue.begin(); it < queue.end(); it++) {
				if (!it->is_significant()) continue;
				if (key_found) {
					if (colon_found) {
						if (process_values) process_values(it);
						break;
					} else {
						if (!it->is_delimiter(':')) break;  // no colon found
						colon_found = true;
					}
				} else {
					if (it->is_type(TokenType::ident)) {
						key_found = true;
						if (it->text_equals_case_insensitive("font") || it->text_equals_case_insensitive("font-size")) {
							process_values = std::bind(&TokenQueue::process_font_sizes, this, std::placeholders::_1);
						}
					} else break;  // no property key found
				}
			}
			return changed;
		}

		bool process_font_sizes(std::vector<Token>::iterator) {
			bool changed = false;
			return changed;
		}

    public:
        TokenQueue(const size_t src_sz, PyObject *url_callback=NULL) : pool(), queue(), out(), url_callback(url_callback) { out.reserve(src_sz * 2); }

		void rewind_output() { out.pop_back(); }

        void write_to_output(const char32_t what) { out.push_back(what); }

		void swap_result_to(std::u32string &result) { out.swap(result); }

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

		void commit_tokens(const char32_t flush_char) {
			bool changed = false;
			if (flush_char == ';') {
				const Token *att = leading_token_of_type(TokenType::at_keyword);
				if (process_urls()) changed = true;
				if (att) {
					if (att->text_equals_case_insensitive("import")) {
						if (process_urls(TokenType::string)) changed = true;
					}
				} else {
					if (process_declaration()) changed = true;
				}
			} else if (flush_char == '{') {
				if (process_urls()) changed = true;
				const Token *att = leading_token_of_type(TokenType::at_keyword);
				if (att && att->text_equals_case_insensitive("import")) {
					if (process_urls(TokenType::string)) changed = true;
				}
			} else {
				if (process_declaration()) changed = true;
			}
			return_tokens_to_pool();
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
        size_t escape_buf_pos;
        TokenQueue token_queue;
        InputStream input;

        bool declarations_allowed() const { return block_types.top()[DECLARATIONS_ALLOWED]; }
        bool at_rules_allowed() const { return block_types.top()[AT_RULES_ALLOWED]; }
        bool qualified_rules_allowed() const { return block_types.top()[QUALIFIED_RULES_ALLOWED]; }

        // testing stream contents {{{
        void rewind_output() { token_queue.rewind_output(); }
        void write_to_output(const char32_t what) { token_queue.write_to_output(what); }
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

        // at_keyword {{{
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
                case ',':
                case ':':
                    token_queue.add_delimiter(ch);
                    break;
                case ';':
				case '{':
				case '}':
                    token_queue.add_delimiter(ch);
					token_queue.commit_tokens(ch);
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
            escape_buf_pos(0), token_queue(src_sz), input(src, src_sz)
        {
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
			token_queue.swap_result_to(result);
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
    } catch (python_error &ex) {
        return NULL;
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
