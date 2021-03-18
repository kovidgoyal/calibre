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
#include <frozen/unordered_map.h>
#include <frozen/string.h>

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

static inline bool
is_printable_ascii(char32_t ch) {
	return ch >= ' ' && ch <= '~';
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

typedef long long integer_type;

class ParsedNumber {
	public:
		bool is_integer;
		integer_type integer_value;
		double float_value;
		ParsedNumber(integer_type val) : is_integer(true), integer_value(val), float_value(0) {}
		ParsedNumber(double val) : is_integer(false), integer_value(0), float_value(val) {}
};

static const double base_font_size = 16.0, dpi = 96.0, pt_to_px = dpi / 72.0, pt_to_rem = pt_to_px / base_font_size;

static double
convert_font_size(double val, double factor) {
	return (factor == 0.0) ? val / base_font_size : (val * factor * pt_to_rem);
}

static integer_type
ipow(integer_type base, integer_type exp) {
    integer_type result = 1;
    while(true) {
        if (exp & 1) result *= base;
        exp >>= 1;
        if (!exp) break;
        base *= base;
    }
    return result;
}

template <typename T>
static integer_type
parse_integer(const T &src, const size_t first, size_t last) {
	integer_type ans = 0, base = 1;
    while(true) {
		integer_type digit = src[last] - '0';
		ans += digit * base;
        if (last == first) break;
        last--;
        base *= 10;
    }
    return ans;
}

template <typename T>
static ParsedNumber
parse_css_number(const T &src) {
	int sign = 1, exponent_sign = 1;
	integer_type integer_part = 0, fractional_part = 0, exponent_part = 0;
	unsigned num_of_fractional_digits = 0;
	size_t first_digit = 0, last_digit = 0;
	const size_t src_sz = src.size();
	size_t pos = 0;
#define read_sign(which) { if (pos < src_sz && (src[pos] == '+' || src[pos] == '-')) { if (src[pos++] == '-') which = -1; }}
#define read_integer(which) { \
	if (pos < src_sz && is_digit(src[pos])) { \
		first_digit = pos; \
		while (pos + 1 < src_sz && is_digit(src[pos+1])) pos++; \
		last_digit = pos++; \
		which = parse_integer<T>(src, first_digit, last_digit); \
	}}
	read_sign(sign);
	read_integer(integer_part);
	if (pos < src_sz && src[pos] == '.') {
		pos++;
		read_integer(fractional_part);
		if (fractional_part) num_of_fractional_digits = last_digit - first_digit + 1;
	}
	if (pos < src_sz && (src[pos] == 'e' || src[pos] == 'E')) {
        pos++;
		read_sign(exponent_sign);
		read_integer(exponent_part);
	}
	if (fractional_part || (exponent_part && exponent_sign == -1)) {
		double ans = integer_part;
		if (fractional_part) ans += ((double) fractional_part) / ((double)(ipow(10, num_of_fractional_digits)));
		if (exponent_part) {
			if (exponent_sign == -1) ans /= (double)ipow(10, exponent_part);
			else ans *= ipow(10, exponent_part);
		}
		return ParsedNumber(sign * ans);
	}
	return ParsedNumber(sign * integer_part * ipow(10, exponent_part));
#undef read_sign
#undef read_integer
}

enum class PropertyType : unsigned int {
	font_size, page_break, non_standard_writing_mode
};

constexpr auto known_properties = frozen::make_unordered_map<frozen::string, PropertyType>({
		{"font-size", PropertyType::font_size},
		{"font", PropertyType::font_size},

		{"page-break-before", PropertyType::page_break},
		{"page-break-after", PropertyType::page_break},
		{"page-break-inside", PropertyType::page_break},

		{"-webkit-writing-mode", PropertyType::non_standard_writing_mode},
		{"-epub-writing-mode", PropertyType::non_standard_writing_mode},
});

constexpr auto font_size_keywords = frozen::make_unordered_map<frozen::string, frozen::string>({
		{"xx-small", "0.5rem"},
		{"x-small", "0.625rem"},
		{"small", "0.8rem"},
		{"medium", "1rem"},
		{"large", "1.125rem"},
		{"x-large", "1.5rem"},
		{"xx-large", "2rem"},
		{"xxx-large", "2.55rem"}
});

constexpr auto absolute_length_units = frozen::make_unordered_map<frozen::string, double>({
	{"mm", 2.8346456693},
	{"cm", 28.346456693},
	{"in", 72},
	{"pc", 12},
	{"q", 0.708661417325},
	{"px", 0.0},
	{"pt", 1.0}
});


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
};


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

		TokenType get_type() const { return type; }
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

		bool text_as_ascii_lowercase(std::string &scratch) {
			scratch.clear();
			for (auto ch : text) {
				if (is_printable_ascii(ch)) {
					if ('A' <= ch && ch <= 'Z') ch += 'a' - 'A';
					scratch.push_back(ch);
				} else return false;
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

		PyObject* get_text() const {
			PyObject *ans = PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, text.data(), text.size());
			if (ans == NULL) throw python_error("Failed to convert token value to python unicode object");
			return ans;
		}

		void erase_text_substring(size_t pos, size_t len) {
			text.replace(pos, len, (size_t)0u, 0);
		}

		void set_text(const PyObject* src) {
			if (PyUnicode_READY(src) != 0) throw python_error("Failed to set token value from unicode object as readying the unicode obect failed");
			text.clear();
			int kind = PyUnicode_KIND(src); void *data = PyUnicode_DATA(src);
			for (Py_ssize_t i = 0; i < PyUnicode_GET_LENGTH(src); i++) text.push_back(PyUnicode_READ(kind, data, i));
		}

		void set_text(const char* src) {
			text.clear();
			while(*src) text.push_back(*(src++));
		}

		void set_text(const frozen::string &src) {
			text.clear();
			for (size_t i = 0; i < src.size(); i++) text.push_back(src[i]);
		}

		bool parse_dimension(std::string &scratch) {
			if (!text_as_ascii_lowercase(scratch)) return false;
		}

};

class TokenQueue {
    private:
        std::stack<Token> pool;
        std::vector<Token> queue;
        std::u32string out;
		std::string scratch, scratch2;
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
						pyobject_raii url(tok.get_text());
						pyobject_raii new_url(PyObject_CallFunctionObjArgs(url_callback.ptr(), url.ptr(), NULL));
						if (!new_url) { PyErr_Print(); }
						else {
							if (PyUnicode_Check(new_url.ptr()) && new_url.ptr() != url.ptr()) {
								tok.set_text(new_url.ptr());
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
			bool colon_found = false, key_found = false, keep_going = true;
			std::function<bool(std::vector<Token>::iterator)> process_values;

			for (auto it = queue.begin(); keep_going && it < queue.end(); it++) {
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
						if (!it->text_as_ascii_lowercase(scratch)) break; // not a printable ascii property name
						frozen::string property_name(scratch.data(), scratch.size());
						auto pit = known_properties.find(property_name);
						if (pit == known_properties.end()) break; // not a known property
						switch(pit->second) {
							case PropertyType::font_size:
								process_values = std::bind(&TokenQueue::process_font_sizes, this, std::placeholders::_1);
								break;
							case PropertyType::page_break:
								it->erase_text_substring(0, 5);
								changed = true; keep_going = false;
								break;
							case PropertyType::non_standard_writing_mode:
								it->set_text("writing-mode");
								changed = true; keep_going = false;
								break;
						}
					} else break;  // no property key found
				}
			}
			return changed;
		}

		bool process_font_sizes(std::vector<Token>::iterator it) {
			bool changed = false;
			for (; it < queue.end(); it++) {
				switch (it->get_type()) {
					case TokenType::ident:
						if (it->text_as_ascii_lowercase(scratch2)) {
							frozen::string key(scratch2.data(), scratch2.size());
							auto fsm = font_size_keywords.find(key);
							if (fsm != font_size_keywords.end()) {
								it->set_text(fsm->second);
								changed = true;
							}
						}
						break;
					case TokenType::dimension:
						break;
					default:
						break;
				}
			}
			return changed;
		}

    public:
        TokenQueue(const size_t src_sz, PyObject *url_callback=NULL) :
			pool(), queue(), out(), scratch(), scratch2(), url_callback(url_callback) {
				out.reserve(src_sz * 2); scratch.reserve(16); scratch2.reserve(16);
			}

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

#define handle_exceptions(msg) \
	catch (std::bad_alloc &ex) { \
        return PyErr_NoMemory(); \
    } catch (python_error &ex) { \
        return NULL; \
    } catch (std::exception &ex) { \
        PyErr_SetString(PyExc_Exception, ex.what()); \
        return NULL; \
    } catch (...) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return NULL; \
    }


static PyObject*
transform_properties(const char32_t *src, size_t src_sz, bool is_declaration) {
    try {
        std::u32string result;
        Parser parser(src, src_sz, is_declaration);
        parser.parse(result);
        return PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, result.data(), result.size());
    } handle_exceptions("Unknown error while parsing CSS");
}

static PyObject*
parse_css_number_python(PyObject *self, PyObject *src) {
	if (!PyUnicode_Check(src)) { PyErr_SetString(PyExc_TypeError, "Unicode string required"); return NULL; }
    if (PyUnicode_READY(src) != 0) { return NULL; }
	try {
		std::u32string text;
		text.reserve(PyUnicode_GET_LENGTH(src));
		int kind = PyUnicode_KIND(src); void *data = PyUnicode_DATA(src);
		for (Py_ssize_t i = 0; i < PyUnicode_GET_LENGTH(src); i++) text.push_back(PyUnicode_READ(kind, data, i));

		ParsedNumber ans = parse_css_number<std::u32string>(text);
		if (ans.is_integer) return PyLong_FromLongLong(ans.integer_value);
		return PyFloat_FromDouble(ans.float_value);
	} handle_exceptions("Unknown error while parsing CSS number");
}

#undef handle_exceptions
static PyMethodDef methods[] = {
    {"parse_css_number", parse_css_number_python, METH_O,
     "Parse a CSS number form a string"
    },
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
