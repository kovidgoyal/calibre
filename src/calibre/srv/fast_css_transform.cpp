/*
 * fast_css_transform.cpp
 * Copyright (C) 2021 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

// See https://www.w3.org/TR/css-syntax-3

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
#include <iostream>
#include <string>
#include <functional>
#include <locale>
#include <codecvt>
#include <frozen/unordered_map.h>
#include <frozen/string.h>
#include "../utils/cpp_binding.h"
#define STB_SPRINTF_IMPLEMENTATION
#include "../utils/stb_sprintf.h"

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
is_hex_digit(char32_t ch) {
    return ('0' <= ch && ch <= '9') || ('a' <= ch && ch <= 'f') || ('A' <= ch && ch <= 'F');
}

static inline bool
is_letter(char32_t ch) {
    return ('a' <= ch && ch <= 'z') || ('A' <= ch && ch <= 'Z');
}

static inline bool
is_digit(char32_t ch) {
    return '0' <= ch && ch <= '9';
}

static inline bool
is_name_start(char32_t ch) {
    return is_letter(ch) || ch == '_' || ch >= 0x80;
}

static inline bool
is_name_body(char32_t ch) {
    return is_name_start(ch) || is_digit(ch) || ch == '-';
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

// Parse numbers {{{

typedef long long integer_type;

class ParsedNumber {
	public:
		bool is_integer;
		integer_type integer_value;
		double float_value;
		ParsedNumber(integer_type val) : is_integer(true), integer_value(val), float_value(0) {}
		ParsedNumber(double val) : is_integer(false), integer_value(0), float_value(val) {}
        double as_double() const { return is_integer ? (double)integer_value : float_value; }
};

static const double base_font_size = 16.0, dpi = 96.0, pt_to_px = dpi / 72.0, pt_to_rem = pt_to_px / base_font_size;

static double
convert_font_size(double val, double factor) {
	return (factor == 0.0) ? (val / base_font_size) : (val * factor * pt_to_rem);
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
parse_css_number(const T &src, size_t limit = 0) {
	int sign = 1, exponent_sign = 1;
	integer_type integer_part = 0, fractional_part = 0, exponent_part = 0;
	size_t num_of_fractional_digits = 0;
	size_t first_digit = 0, last_digit = 0;
	const size_t src_sz = limit ? limit : src.size();
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
		double ans = (double)integer_part;
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
// }}}

enum class PropertyType : unsigned int {
	font_size, page_break, non_standard_writing_mode
};

constexpr static const auto known_properties = frozen::make_unordered_map<frozen::string, PropertyType>({
		{"font-size", PropertyType::font_size},
		{"font", PropertyType::font_size},

		{"page-break-before", PropertyType::page_break},
		{"page-break-after", PropertyType::page_break},
		{"page-break-inside", PropertyType::page_break},

		{"-webkit-writing-mode", PropertyType::non_standard_writing_mode},
		{"-epub-writing-mode", PropertyType::non_standard_writing_mode},
});

constexpr static const auto font_size_keywords = frozen::make_unordered_map<frozen::string, frozen::string>({
		{"xx-small", "0.5rem"},
		{"x-small", "0.625rem"},
		{"small", "0.8rem"},
		{"medium", "1rem"},
		{"large", "1.125rem"},
		{"x-large", "1.5rem"},
		{"xx-large", "2rem"},
		{"xxx-large", "2.55rem"}
});

constexpr static const auto absolute_length_units = frozen::make_unordered_map<frozen::string, double>({
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
    at_keyword,
    hash,
    string,
    url,
    function_start,
    number,
    dimension,
    cdo,
    cdc
};


class Token {
    enum class NameSerializeState : unsigned { start, one_hyphen, body };

    private:
        TokenType type;
        std::u32string text;
        size_t unit_at, out_pos;

        void clear() {
            type = TokenType::whitespace;
            text.clear();
            unit_at = 0;
        }

        void serialize_escaped_char(const char32_t ch, std::u32string &out) const {
            out.push_back('\\');
            if (is_whitespace(ch) || is_hex_digit(ch)) {
                char buf[8];
                int num = stbsp_snprintf(buf, sizeof(buf), "%x ", (unsigned int)ch);
                if (num > 0) {
                    out.resize(out.size() + num);
                    for (int i = 0; i < num; i++) out[i + out.size() - num] = buf[i];
                } else throw std::logic_error("Failed to convert character to hexadecimal escape");
            } else out.push_back(ch);
        }

        void serialize_ident(std::u32string &out) const {
            NameSerializeState state = NameSerializeState::start;
            for (const auto ch : text) {
                switch(state) {
                    case NameSerializeState::start:
                        if (is_name_start(ch)) { out.push_back(ch); state = NameSerializeState::body; }
                        else if (ch == '-') { out.push_back(ch); state = NameSerializeState::one_hyphen; }
                        else throw std::logic_error("Unable to serialize ident because of invalid start character");
                        break;
                    case NameSerializeState::one_hyphen:
                        if (is_name_start(ch) || ch == '-') { out.push_back(ch); state = NameSerializeState::body; }
                        else serialize_escaped_char(ch, out);
                        break;
                    case NameSerializeState::body:
                        if (is_name_body(ch)) out.push_back(ch);
                        else serialize_escaped_char(ch, out);
                        break;
                }
            }
        }

        void serialize_hash(std::u32string &out) const {
            for (const auto ch : text) {
                if (is_name_body(ch)) out.push_back(ch);
                else serialize_escaped_char(ch, out);
            }
        }

        void serialize_string(std::u32string &out) const {
            const char32_t delim = text.find('"') == std::u32string::npos ? '"' : '\'';
            out.push_back(delim);
            for (const auto ch : text) {
                if (ch == '\n') out.append({'\\', '\n'});
                else if (ch == delim || ch == '\\') serialize_escaped_char(ch, out);
                else out.push_back(ch);
            }
            out.push_back(delim);
        }

    public:
        Token() :
			type(TokenType::whitespace), text(), unit_at(0), out_pos(0) {
				text.reserve(16);
			}

        Token(const TokenType type, const char32_t ch, size_t out_pos = 0) :
			type(type), text(), unit_at(0), out_pos(out_pos) {
				text.reserve(16);
				if (ch) text.push_back(ch);
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
        size_t get_output_position() const { return out_pos; }
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
			scratch.resize(text.size());
            size_t i = 0;
			for (auto ch : text) {
				if (is_printable_ascii(ch)) {
					if ('A' <= ch && ch <= 'Z') ch += 'a' - 'A';
					scratch[i++] = (char)ch;
				} else return false;
			}
            scratch.resize(i);
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
				case TokenType::cdo:
				case TokenType::cdc:
					return false;
				default:
					return true;
			}
		}

		bool is_property_terminator() const {
			switch(type) {
				case TokenType::whitespace:
					return text.size() > 0 && text.find_first_of('\n') != std::string::npos;
				case TokenType::delimiter:
					return text.size() == 1 && (text[0] == ';' || text[0] == '}');
				default:
					return false;
			}
		}

		PyObject* get_text_as_python() const {
			PyObject *ans = PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, text.data(), text.size());
			if (ans == NULL) throw python_error("Failed to convert token value to python unicode object");
			return ans;
		}

        const std::u32string& get_text() const {
            return text;
        }

        const char* type_name() const {
#define n(x) case TokenType::x: return #x;
            switch(type) {
                n(whitespace); n(cdo); n(cdc); n(ident); n(string); n(number);
                n(function_start); n(dimension); n(url); n(delimiter); n(at_keyword); n(hash);
            }
#undef n
        }

		void erase_text_substring(size_t pos, size_t len) {
			text.replace(pos, len, (size_t)0u, 0);
		}

		void prepend(const char32_t *src) {
			text.insert(0, src);
		}

		void set_text(const PyObject* src) {
			if (PyUnicode_READY(src) != 0) throw python_error("Failed to set token value from unicode object as readying the unicode object failed");
			int kind = PyUnicode_KIND(src); void *data = PyUnicode_DATA(src);
            text.resize(PyUnicode_GET_LENGTH(src));
			for (Py_ssize_t i = 0; i < PyUnicode_GET_LENGTH(src); i++) text[i] = PyUnicode_READ(kind, data, i);
		}

		void set_text(const char32_t *src) {
            text = src;
		}

		void set_text(const frozen::string &src) {
            text.resize(src.size());
            for (size_t i = 0; i < text.size(); i++) text[i] = src[i];
		}

        void set_text(const std::string &src) {
            text.resize(src.size());
            for (size_t i = 0; i < text.size(); i++) text[i] = src[i];
        }

        void set_ascii_text(const char *txt, int sz) {
            text.resize(sz);
            for (int i = 0; i < sz; i++) text[i] = txt[i];
        }

        bool convert_absolute_font_size(std::string &scratch) {
            if (!unit_at || !text_as_ascii_lowercase(scratch)) return false;
            frozen::string unit(scratch.data() + unit_at, scratch.size() - unit_at);
            auto lit = absolute_length_units.find(unit);
            if (lit == absolute_length_units.end()) return false;
            double val = parse_css_number<std::string>(scratch, unit_at).as_double();
            double new_val = convert_font_size(val, lit->second);
            if (val == new_val) return false;
            char txt[128];
            // stbsp_snprintf is locale independent unlike std::snprintf
            int num = stbsp_snprintf(txt, sizeof(txt), "%grem", new_val);
            if (num <= 0) throw std::runtime_error("Failed to format font size");
            set_ascii_text(txt, num);
            return true;
        }

        void serialize(std::u32string &out) const {
            out.reserve(text.size() + 8);
            switch (type) {
                case TokenType::whitespace:
                case TokenType::delimiter:
                    out.append(text);
                    break;
                case TokenType::ident:
                    serialize_ident(out);
                    break;
                case TokenType::at_keyword:
                    out.push_back('@');
                    serialize_ident(out);
                    break;
                case TokenType::hash:
                    out.push_back('#');
                    serialize_hash(out);
                    break;
                case TokenType::string:
                    serialize_string(out);
                    break;
                case TokenType::url:
                    out.append({'u', 'r', 'l', '('});
                    serialize_string(out);
                    out.push_back(')');
                    break;
                case TokenType::function_start:
                    serialize_ident(out);
                    out.push_back('(');
                    break;
                case TokenType::number:
                case TokenType::dimension:
                    out.append(text);
                    break;
                case TokenType::cdo:
                    out.append({'<', '!', '-', '-'});
                    break;
                case TokenType::cdc:
                    out.append({'-', '-', '>'});
                    break;
            }
        }

        friend std::ostream& operator<<(std::ostream& os, const Token& tok);
};

std::ostream& operator<<(std::ostream& os, const Token& tok) {
    std::u32string rep;
    std::wstring_convert<std::codecvt_utf8<char32_t>, char32_t> cv;
    tok.serialize(rep);
    os << cv.to_bytes(rep);
    return os;
}


class TokenQueue {
    private:
        std::stack<Token> pool;
        std::vector<Token> queue;
        std::u32string out;
		std::string scratch, scratch2;
		pyobject_raii url_callback;

		size_t current_output_position() const { return out.size(); }

        void new_token(const TokenType type, const char32_t ch = 0) {
            if (pool.empty()) queue.emplace_back(type, ch, current_output_position());
            else {
                queue.push_back(std::move(pool.top())); pool.pop();
                queue.back().set_type(type);
                queue.back().set_output_position(current_output_position());
                if (ch) queue.back().add_char(ch);
            }
        }

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
						pyobject_raii url(tok.get_text_as_python());
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
						if (process_values && process_values(it)) changed = true;;
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
							case PropertyType::page_break: {
								it->erase_text_substring(0, 5);
								size_t pos = std::distance(queue.begin(), it);
								std::vector<Token> copies;
								copies.reserve(queue.size() + 2);
								while (it < queue.end() && !it->is_property_terminator()) { copies.push_back(*(it++)); }
								if (copies.size()) {
									copies.emplace_back(TokenType::delimiter, ';');
									copies.emplace_back(TokenType::whitespace, ' ');
									queue.insert(queue.begin() + pos, std::make_move_iterator(copies.begin()), std::make_move_iterator(copies.end()));
									size_t idx = pos + copies.size();
									queue[idx].prepend(U"-webkit-column-");
								}
								changed = true; keep_going = false;
							}
								break;
							case PropertyType::non_standard_writing_mode:
								it->set_text(U"writing-mode");
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
                                it->set_type(TokenType::dimension);
								changed = true;
							}
						}
						break;
					case TokenType::dimension:
                        if (it->convert_absolute_font_size(scratch2)) changed = true;
						break;
					default:
						break;
				}
			}
			return changed;
		}

    public:
        TokenQueue(const size_t src_sz, PyObject *url_callback_pointer=NULL) :
			pool(), queue(), out(), scratch(), scratch2(), url_callback(url_callback_pointer) {
				out.reserve(src_sz * 2); scratch.reserve(16); scratch2.reserve(16);
				Py_XINCREF(url_callback.ptr());
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

        void add_hash() { new_token(TokenType::hash); }

        void add_at_keyword() { new_token(TokenType::at_keyword); }

        void add_number(const char32_t ch) { new_token(TokenType::number, ch); }

        void add_ident(const char32_t ch) { new_token(TokenType::ident, ch); }

        void add_cdc() { new_token(TokenType::cdc); }
        void add_cdo() { new_token(TokenType::cdo); }

        void mark_unit() {
            if (queue.empty()) throw std::logic_error("Attempting to mark unit with no token present");
            queue.back().mark_unit();
            queue.back().set_type(TokenType::dimension);
        }

        void trim_trailing_whitespace() {
            if (!queue.empty()) queue.back().trim_trailing_whitespace();
        }

        bool starts_with_at_keyword() const { return leading_token_of_type(TokenType::at_keyword) != NULL; }

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
				if (process_urls()) changed = true;
				if (process_declaration()) changed = true;
			}
            if (changed && queue.size()) {
                const size_t pos = queue[0].get_output_position();
                out.resize(pos ? pos - 1: 0);
                for (auto tok : queue) tok.serialize(out);
            }
			return_tokens_to_pool();
		}
};

class Parser {
    private:
        enum class ParseState : unsigned {
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

        class InputStream { // {{{
            private:
                int kind;
                void *data;
                const size_t src_sz;
                size_t pos;

                char32_t read(size_t i) const { return PyUnicode_READ(kind, data, i); }

                char32_t peek_one(size_t at, unsigned *consumed) const {
                    if (at >= src_sz) { *consumed = 0; return 0; }
                    *consumed = 1;
                    char32_t ch = read(at);
                    if (ch == 0xc) ch = '\n';
                    else if (ch == '\r') {
                        ch = '\n';
                        if (at + 1 < src_sz && read(at + 1) == '\n') *consumed = 2;
                    }
                    else if (ch == 0 || is_surrogate(ch)) ch = 0xfffd;
                    return ch;
                }

            public:
                InputStream(PyObject *src) : kind(PyUnicode_KIND(src)), data(PyUnicode_DATA(src)), src_sz(PyUnicode_GET_LENGTH(src)), pos(0) { }

                char32_t next() {
                    unsigned last_step_size;
                    char32_t ans = peek_one(pos, &last_step_size);
                    pos += last_step_size;
                    return ans;
                }

                void rewind() {
                    if (!pos) throw std::logic_error("Cannot rewind already at start of stream");
                    pos -= (read(pos-1) == '\n' && pos >= 2 && read(pos-2) == '\r') ? 2 : 1;
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
        }; // end InputStream }}}

        class BlockTypeFlags : public std::bitset<4> { // {{{
            enum class Fields : unsigned {
                declarations_allowed, qualified_rules_allowed, at_rules_allowed, top_level
            };
            public:
                BlockTypeFlags(bool declarations_allowed=true, bool qualified_rules_allowed=false, bool at_rules_allowed=false, bool top_level=false) : std::bitset<4>() {
                    set((unsigned)Fields::declarations_allowed, declarations_allowed);
                    set((unsigned)Fields::qualified_rules_allowed, qualified_rules_allowed);
                    set((unsigned)Fields::at_rules_allowed, at_rules_allowed);
                    set((unsigned)Fields::top_level, top_level);
                }

#define PROP(which) \
                void set_##which(bool allowed = true) { set((unsigned)Fields::which, allowed); } \
                bool which() const { return (*this)[(unsigned)Fields::which]; }

                PROP(declarations_allowed)
                PROP(qualified_rules_allowed)
                PROP(at_rules_allowed)
                PROP(top_level)
#undef PROP
        }; // }}}

        char32_t ch, end_string_with, prev_ch;
        std::stack<BlockTypeFlags> block_types;
        std::stack<ParseState> states;
        char escape_buf[16];
        unsigned escape_buf_pos;
        TokenQueue token_queue;
        InputStream input;

        // block types {{{
        bool declarations_allowed() const { return block_types.top().declarations_allowed(); }
        bool qualified_rules_allowed() const { return block_types.top().qualified_rules_allowed(); }
        bool at_rules_allowed() const { return block_types.top().at_rules_allowed(); }
        bool is_top_level() const { return block_types.top().top_level(); }
        void push_block_type(bool declarations_allowed=true, bool qualified_rules_allowed=false, bool at_rules_allowed=false, bool top_level=false) {
            block_types.emplace(declarations_allowed, qualified_rules_allowed, at_rules_allowed, top_level);
        }
        void pop_block_type() { if (block_types.size() > 1) block_types.pop(); }
        // }}}

        // testing stream contents {{{
        void pop_state() { if (states.size() > 1) states.pop(); }
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
                if (ch == '\n') { reconsume(); pop_state(); return; }
                if (!is_hex_digit(ch)) {
                    pop_state();
                    token_queue.add_char(ch);
                    return;
                }
                escape_buf[escape_buf_pos++] = (char)ch;
                return;
            }
            if (is_hex_digit(ch) && escape_buf_pos < 6) { escape_buf[escape_buf_pos++] = (char)ch; return; }
            if (is_whitespace(ch)) return;  // a single whitespace character is absorbed into escape
            reconsume();
            pop_state();
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
            else if (ch == end_string_with) pop_state();
            else token_queue.add_char(ch);
        } // }}}

        // comment {{{
        void enter_comment_mode() {
            states.push(ParseState::comment);
        }

        void handle_comment() {
            if (ch == '/' && prev_ch == '*') pop_state();
        } // }}}

        // hash {{{
        void enter_hash_mode() {
            states.push(ParseState::hash);
            token_queue.add_hash();
        }

        void handle_name() {
            if (is_name(ch)) token_queue.add_char(ch);
            else if (has_valid_escape()) enter_escape_mode();
            else if (starting_comment()) enter_comment_mode();
            else {
                reconsume();
                pop_state();
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
            if (is_digit(ch) || (ch == '.' && is_digit(peek()))) { token_queue.add_char(ch); return; }
            if (starting_comment()) { enter_comment_mode(); return; }
            if ((ch == 'e' || ch == 'E')) {
                char32_t next = peek();
                if (is_digit(next) || ((next == '+' || next == '-') && is_digit(peek(1)))) {
                    token_queue.add_char(input.next()); token_queue.add_char(input.next());
                    pop_state();
                    enter_digits_mode();
                    return;
                }
            }
            reconsume();
            pop_state();
            if (has_identifier_next()) { enter_dimension_mode(); }
        }  // }}}

        // digits {{{
        void enter_digits_mode() {
            states.push(ParseState::digits);
        }

        void handle_digits() {
            if (is_digit(ch)) { token_queue.add_char(ch); }
            else if (starting_comment()) enter_comment_mode();
            else {
                reconsume();
                pop_state();
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
            if (starting_comment()) { enter_comment_mode(); return; }
            reconsume();
            pop_state();
        } // }}}

        // ident {{{
        void enter_ident_mode(const char32_t starting_ch = 0) {
            token_queue.add_ident(starting_ch);
            states.push(ParseState::ident);
        }

        void handle_ident() {
            if (is_name(ch)) { token_queue.add_char(ch); return; }
            if (has_valid_escape()) { enter_escape_mode(); return; }
            if (starting_comment()) { enter_comment_mode(); return; }
            pop_state();
            if (ch == '(') {
                if (token_queue.current_token_text_equals_case_insensitive("url")) enter_url_start_mode();
                else token_queue.make_function_start();
            } else reconsume();
        } // }}}

        // url {{{
        void enter_url_start_mode() {
            token_queue.make_function_start(true);
            states.push(ParseState::url_start);
        }

        void handle_url_start() {
            if (is_whitespace(ch)) return;
            if (starting_string()) { pop_state(); end_string_with = ch; states.push(ParseState::url_string); return; }
            if (ch == ')') { pop_state(); return; }
            if (starting_comment()) { enter_comment_mode(); return; }
            pop_state(); states.push(ParseState::url);
            token_queue.add_char(ch);
        }

        void handle_url_string() {
            handle_string();
            if (states.top() != ParseState::url_string && states.top() != ParseState::escape) states.push(ParseState::url_after_string);
        }

        void handle_url_after_string() {
            if (starting_comment()) { enter_comment_mode(); return; }
            if (!is_whitespace(ch)) exit_url_mode();
        }

        void handle_url() {
            if (ch == '\\' && has_valid_escape()) enter_escape_mode();
            else if (ch == ')') exit_url_mode(true);
            else if (starting_comment()) enter_comment_mode();
            else token_queue.add_char(ch);
        }

        void exit_url_mode(bool trim=false) {
            pop_state();
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
                    token_queue.add_delimiter(ch);
					token_queue.commit_tokens(ch);
                    break;
				case '{':
                    if (at_rules_allowed() || qualified_rules_allowed()) {
                        const bool is_at_rule = token_queue.starts_with_at_keyword();
                        push_block_type(true, is_at_rule, is_at_rule);
                    }
                    token_queue.add_delimiter(ch);
					token_queue.commit_tokens(ch);
                    break;
				case '}':
                    pop_block_type();
                    token_queue.add_delimiter(ch);
					token_queue.commit_tokens(ch);
                    break;
                case '+':
                    if (is_digit(peek()) || (peek() == '.' && is_digit(peek(1)))) { enter_number_mode(); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '-':
                    if (is_digit(peek()) || (peek() == '.' && is_digit(peek(1)))) { enter_number_mode(); }
                    else if (is_top_level() && peek() == '-' && peek(1) == '>') { token_queue.add_cdc(); write_to_output(input.next()); write_to_output(input.next()); }
                    else if (has_identifier()) { enter_ident_mode(ch); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '.':
                    if (is_digit(peek())) { enter_number_mode(); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '<':
                    if (is_top_level() && peek() == '!' && peek(1) == '-' && peek(2) == '-') { token_queue.add_cdo(); write_to_output(input.next()); write_to_output(input.next()); }
                    else token_queue.add_delimiter(ch);
                    break;
                case '@':
                    if (at_rules_allowed() && has_identifier_next()) enter_at_keyword();
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
                case ParseState::normal:
                    handle_normal(); break;
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
            }
            prev_ch = ch;
        }


    public:
        Parser(PyObject *src, PyObject *url_callback = NULL, const bool is_declaration = false) :
            ch(0), end_string_with('"'), prev_ch(0), block_types(), states(), escape_buf(),
            escape_buf_pos(0), token_queue(PyUnicode_GET_LENGTH(src), url_callback), input(src)
        {
            if (is_declaration) push_block_type(); else push_block_type(true, true, true, true);
            states.push(ParseState::normal);
        }

        void parse(std::u32string &result) {
            while (true) {
                ch = input.next();
                if (!ch) break;
                dispatch_current_char();
            }
            token_queue.commit_tokens(';');
			token_queue.swap_result_to(result);
        }

};

#define handle_exceptions(msg) \
	catch (std::bad_alloc &ex) { \
        (void)ex; \
        return PyErr_NoMemory(); \
    } catch (python_error &ex) { \
        (void)ex; \
        return NULL; \
    } catch (std::exception &ex) { \
        PyErr_SetString(PyExc_Exception, ex.what()); \
        return NULL; \
    } catch (...) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return NULL; \
    }


static PyObject*
transform_properties(PyObject *src, PyObject *url_callback = NULL, bool is_declaration = false) {
    try {
        std::u32string result;
        Parser parser(src, url_callback, is_declaration);
        parser.parse(result);
        return PyUnicode_FromKindAndData(PyUnicode_4BYTE_KIND, result.data(), result.size());
    } handle_exceptions("Unknown error while parsing CSS");
}

static PyObject*
transform_properties_python(PyObject *self, PyObject *args, PyObject *kw) {
    static const char* kwlist[] = {"src", "url_callback", "is_declaration", NULL};
    PyObject *raw, *url_callback = NULL; int is_declaration = 0;
    if (!PyArg_ParseTupleAndKeywords(args, kw, "U|Op", (char**)kwlist, &raw, &url_callback, &is_declaration)) return NULL;
    if (url_callback == Py_None) url_callback = NULL;
    if (url_callback && !PyCallable_Check(url_callback)) { PyErr_SetString(PyExc_TypeError, "url_callback must be a callable"); return NULL; }
    if (PyUnicode_READY(raw) != 0) return NULL;
    PyObject *result = transform_properties(raw, url_callback, is_declaration);
    return result;
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
     "Parse a CSS number from a string"
    },
    {"transform_properties", (PyCFunction)transform_properties_python, METH_VARARGS | METH_KEYWORDS,
     "Transform a CSS stylesheet or declaration"
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
