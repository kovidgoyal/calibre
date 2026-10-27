/*
 * color.c
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 *
 * Fast parsers for CSS color values.
 *
 * tinycss_parse_color_string() implements tinycss.color3.parse_color_string()
 * (CSS 3 colors). Inputs that use rarely seen syntax (escapes, non-ASCII
 * characters, unterminated comments or functions, very long integers) return
 * NotImplemented so that the caller can fall back to the pure python
 * implementation.
 *
 * tinycss_parse_css4_color_string() implements CSS Color Module Level 4
 * https://www.w3.org/TR/css-color-4/ converting all colors to sRGB.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "color.h"

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

typedef struct {
    const char *name;
    unsigned char r, g, b;
} ColorKeyword;

// Sorted by name, must match BASIC_COLOR_KEYWORDS and EXTENDED_COLOR_KEYWORDS in color3.py
static const ColorKeyword color_keywords[] = {
    {"aliceblue", 240, 248, 255},
    {"antiquewhite", 250, 235, 215},
    {"aqua", 0, 255, 255},
    {"aquamarine", 127, 255, 212},
    {"azure", 240, 255, 255},
    {"beige", 245, 245, 220},
    {"bisque", 255, 228, 196},
    {"black", 0, 0, 0},
    {"blanchedalmond", 255, 235, 205},
    {"blue", 0, 0, 255},
    {"blueviolet", 138, 43, 226},
    {"brown", 165, 42, 42},
    {"burlywood", 222, 184, 135},
    {"cadetblue", 95, 158, 160},
    {"chartreuse", 127, 255, 0},
    {"chocolate", 210, 105, 30},
    {"coral", 255, 127, 80},
    {"cornflowerblue", 100, 149, 237},
    {"cornsilk", 255, 248, 220},
    {"crimson", 220, 20, 60},
    {"cyan", 0, 255, 255},
    {"darkblue", 0, 0, 139},
    {"darkcyan", 0, 139, 139},
    {"darkgoldenrod", 184, 134, 11},
    {"darkgray", 169, 169, 169},
    {"darkgreen", 0, 100, 0},
    {"darkgrey", 169, 169, 169},
    {"darkkhaki", 189, 183, 107},
    {"darkmagenta", 139, 0, 139},
    {"darkolivegreen", 85, 107, 47},
    {"darkorange", 255, 140, 0},
    {"darkorchid", 153, 50, 204},
    {"darkred", 139, 0, 0},
    {"darksalmon", 233, 150, 122},
    {"darkseagreen", 143, 188, 143},
    {"darkslateblue", 72, 61, 139},
    {"darkslategray", 47, 79, 79},
    {"darkslategrey", 47, 79, 79},
    {"darkturquoise", 0, 206, 209},
    {"darkviolet", 148, 0, 211},
    {"deeppink", 255, 20, 147},
    {"deepskyblue", 0, 191, 255},
    {"dimgray", 105, 105, 105},
    {"dimgrey", 105, 105, 105},
    {"dodgerblue", 30, 144, 255},
    {"firebrick", 178, 34, 34},
    {"floralwhite", 255, 250, 240},
    {"forestgreen", 34, 139, 34},
    {"fuchsia", 255, 0, 255},
    {"gainsboro", 220, 220, 220},
    {"ghostwhite", 248, 248, 255},
    {"gold", 255, 215, 0},
    {"goldenrod", 218, 165, 32},
    {"gray", 128, 128, 128},
    {"green", 0, 128, 0},
    {"greenyellow", 173, 255, 47},
    {"grey", 128, 128, 128},
    {"honeydew", 240, 255, 240},
    {"hotpink", 255, 105, 180},
    {"indianred", 205, 92, 92},
    {"indigo", 75, 0, 130},
    {"ivory", 255, 255, 240},
    {"khaki", 240, 230, 140},
    {"lavender", 230, 230, 250},
    {"lavenderblush", 255, 240, 245},
    {"lawngreen", 124, 252, 0},
    {"lemonchiffon", 255, 250, 205},
    {"lightblue", 173, 216, 230},
    {"lightcoral", 240, 128, 128},
    {"lightcyan", 224, 255, 255},
    {"lightgoldenrodyellow", 250, 250, 210},
    {"lightgray", 211, 211, 211},
    {"lightgreen", 144, 238, 144},
    {"lightgrey", 211, 211, 211},
    {"lightpink", 255, 182, 193},
    {"lightsalmon", 255, 160, 122},
    {"lightseagreen", 32, 178, 170},
    {"lightskyblue", 135, 206, 250},
    {"lightslategray", 119, 136, 153},
    {"lightslategrey", 119, 136, 153},
    {"lightsteelblue", 176, 196, 222},
    {"lightyellow", 255, 255, 224},
    {"lime", 0, 255, 0},
    {"limegreen", 50, 205, 50},
    {"linen", 250, 240, 230},
    {"magenta", 255, 0, 255},
    {"maroon", 128, 0, 0},
    {"mediumaquamarine", 102, 205, 170},
    {"mediumblue", 0, 0, 205},
    {"mediumorchid", 186, 85, 211},
    {"mediumpurple", 147, 112, 219},
    {"mediumseagreen", 60, 179, 113},
    {"mediumslateblue", 123, 104, 238},
    {"mediumspringgreen", 0, 250, 154},
    {"mediumturquoise", 72, 209, 204},
    {"mediumvioletred", 199, 21, 133},
    {"midnightblue", 25, 25, 112},
    {"mintcream", 245, 255, 250},
    {"mistyrose", 255, 228, 225},
    {"moccasin", 255, 228, 181},
    {"navajowhite", 255, 222, 173},
    {"navy", 0, 0, 128},
    {"oldlace", 253, 245, 230},
    {"olive", 128, 128, 0},
    {"olivedrab", 107, 142, 35},
    {"orange", 255, 165, 0},
    {"orangered", 255, 69, 0},
    {"orchid", 218, 112, 214},
    {"palegoldenrod", 238, 232, 170},
    {"palegreen", 152, 251, 152},
    {"paleturquoise", 175, 238, 238},
    {"palevioletred", 219, 112, 147},
    {"papayawhip", 255, 239, 213},
    {"peachpuff", 255, 218, 185},
    {"peru", 205, 133, 63},
    {"pink", 255, 192, 203},
    {"plum", 221, 160, 221},
    {"powderblue", 176, 224, 230},
    {"purple", 128, 0, 128},
    {"red", 255, 0, 0},
    {"rosybrown", 188, 143, 143},
    {"royalblue", 65, 105, 225},
    {"saddlebrown", 139, 69, 19},
    {"salmon", 250, 128, 114},
    {"sandybrown", 244, 164, 96},
    {"seagreen", 46, 139, 87},
    {"seashell", 255, 245, 238},
    {"sienna", 160, 82, 45},
    {"silver", 192, 192, 192},
    {"skyblue", 135, 206, 235},
    {"slateblue", 106, 90, 205},
    {"slategray", 112, 128, 144},
    {"slategrey", 112, 128, 144},
    {"snow", 255, 250, 250},
    {"springgreen", 0, 255, 127},
    {"steelblue", 70, 130, 180},
    {"tan", 210, 180, 140},
    {"teal", 0, 128, 128},
    {"thistle", 216, 191, 216},
    {"tomato", 255, 99, 71},
    {"turquoise", 64, 224, 208},
    {"violet", 238, 130, 238},
    {"wheat", 245, 222, 179},
    {"white", 255, 255, 255},
    {"whitesmoke", 245, 245, 245},
    {"yellow", 255, 255, 0},
    {"yellowgreen", 154, 205, 50},
};

typedef enum { INTEGER, NUMBER, PERCENTAGE } NumberType;

typedef struct {
    NumberType type;
    double value;
} Arg;

typedef enum { PARSE_OK, PARSE_INVALID, PARSE_FALLBACK } ParseResult;

typedef struct {
    const Py_UCS1 *s;
    Py_ssize_t pos, len;
    bool css4;
} Parser;

static inline bool
is_css_space(Py_UCS1 ch) {
    return ch == ' ' || ch == '\t' || ch == '\n' || ch == '\r' || ch == '\f';
}

static inline bool
is_nmchar(Py_UCS1 ch) {
    return ch == '_' || ch == '-' || ('a' <= ch && ch <= 'z') || ('A' <= ch && ch <= 'Z') || ('0' <= ch && ch <= '9');
}

static inline bool
is_digit(Py_UCS1 ch) {
    return '0' <= ch && ch <= '9';
}

static inline int
hex_value(Py_UCS1 ch) {
    if ('0' <= ch && ch <= '9') return ch - '0';
    if ('a' <= ch && ch <= 'f') return ch - 'a' + 10;
    if ('A' <= ch && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

static inline Py_UCS1
peek(const Parser *p, Py_ssize_t offset) {
    return p->pos + offset < p->len ? p->s[p->pos + offset] : 0;
}

// Skip comments and, if allow_space, whitespace
static ParseResult
skip_ignorable(Parser *p, bool allow_space) {
    while (p->pos < p->len) {
        Py_UCS1 ch = p->s[p->pos];
        if (allow_space && is_css_space(ch)) {
            p->pos++;
            continue;
        }
        if (ch == '/' && peek(p, 1) == '*') {
            const Py_UCS1 *end = NULL;
            for (Py_ssize_t i = p->pos + 2; i + 1 < p->len; i++) {
                if (p->s[i] == '*' && p->s[i + 1] == '/') {
                    end = p->s + i;
                    break;
                }
            }
            if (end == NULL) {
                // unterminated comment, in CSS 4 it extends to the end of the input
                if (!p->css4) return PARSE_FALLBACK;
                p->pos = p->len;
                break;
            }
            p->pos = end - p->s + 2;
            continue;
        }
        break;
    }
    return PARSE_OK;
}

// Only comments may follow the color token at the top level
static ParseResult
check_at_end(Parser *p) {
    ParseResult r = skip_ignorable(p, false);
    if (r != PARSE_OK) return r;
    return p->pos == p->len ? PARSE_OK : PARSE_INVALID;
}

static int
compare_keyword(const void *key, const void *item) {
    return strcmp((const char *)key, ((const ColorKeyword *)item)->name);
}

// Implements the num macro from the tinycss tokenizer: [-+]?(?:[0-9]*\.[0-9]+|[0-9]+)
static ParseResult
parse_number_arg(Parser *p, Arg *arg) {
    Py_ssize_t start = p->pos, digits = 0;
    bool is_float = false;
    char buf[64];
    if (peek(p, 0) == '+' || peek(p, 0) == '-') p->pos++;
    while (is_digit(peek(p, 0))) {
        p->pos++;
        digits++;
    }
    if (peek(p, 0) == '.' && is_digit(peek(p, 1))) {
        is_float = true;
        p->pos++;
        while (is_digit(peek(p, 0))) {
            p->pos++;
            digits++;
        }
    }
    if (!digits) return PARSE_INVALID;
    Py_ssize_t sz = p->pos - start;
    // Python ints are arbitrary precision, avoid differences in rounding
    if (sz >= (Py_ssize_t)sizeof(buf) || (!is_float && digits > 15)) return PARSE_FALLBACK;
    memcpy(buf, p->s + start, sz);
    buf[sz] = 0;
    arg->value = strtod(buf, NULL);
    if (peek(p, 0) == '%') {
        p->pos++;
        arg->type = PERCENTAGE;
    } else arg->type = is_float ? NUMBER : INTEGER;
    return PARSE_OK;
}

// Translated from hsl_to_rgb() in color3.py
static double
hue_to_rgb(double m1, double m2, double h) {
    if (h < 0) h += 1;
    if (h > 1) h -= 1;
    if (h * 6 < 1) return m1 + (m2 - m1) * h * 6;
    if (h * 2 < 1) return m2;
    if (h * 3 < 2) return m1 + (m2 - m1) * (2. / 3 - h) * 6;
    return m1;
}

static double
clip01(double x) {
    return fmin(1, fmax(0, x));
}

// saturation and lightness are fractions, CSS 4 does not clamp them, the resulting
// out of gamut colors are clipped at the end like any others
static void
hsl_to_rgb_unclamped(double hue, double saturation, double lightness, double *r, double *g, double *b) {
    // Python semantics for modulo, result has the sign of the divisor
    hue = fmod(hue / 360, 1.0);
    if (hue < 0) hue += 1.0;
    double m2 = lightness <= 0.5 ? lightness * (saturation + 1) : lightness + saturation - lightness * saturation;
    double m1 = lightness * 2 - m2;
    *r = hue_to_rgb(m1, m2, hue + 1. / 3);
    *g = hue_to_rgb(m1, m2, hue);
    *b = hue_to_rgb(m1, m2, hue - 1. / 3);
}

static void
hsl_to_rgb(double hue, double saturation, double lightness, double *r, double *g, double *b) {
    hsl_to_rgb_unclamped(hue, clip01(saturation / 100), clip01(lightness / 100), r, g, b);
}

static ParseResult
parse_function(Parser *p, const char *name, double rgba[4]) {
    bool is_rgb, has_alpha;
    if (strcmp(name, "rgb") == 0) {
        is_rgb = true;
        has_alpha = false;
    } else if (strcmp(name, "rgba") == 0) {
        is_rgb = true;
        has_alpha = true;
    } else if (strcmp(name, "hsl") == 0) {
        is_rgb = false;
        has_alpha = false;
    } else if (strcmp(name, "hsla") == 0) {
        is_rgb = false;
        has_alpha = true;
    } else return PARSE_INVALID;
    Arg args[4];
    unsigned nargs = 0;
    ParseResult r;
    p->pos++; // skip (
    while (true) {
        if ((r = skip_ignorable(p, true)) != PARSE_OK) return r;
        if (p->pos >= p->len) return PARSE_FALLBACK; // unterminated function
        if (nargs >= arraysz(args)) return PARSE_INVALID;
        if ((r = parse_number_arg(p, &args[nargs++])) != PARSE_OK) return r;
        if ((r = skip_ignorable(p, true)) != PARSE_OK) return r;
        if (p->pos >= p->len) return PARSE_FALLBACK; // unterminated function
        Py_UCS1 ch = p->s[p->pos++];
        if (ch == ')') break;
        if (ch != ',') return PARSE_INVALID;
    }
    if ((r = check_at_end(p)) != PARSE_OK) return r;
    if (nargs != (has_alpha ? 4u : 3u)) return PARSE_INVALID;
    if (has_alpha) {
        if (args[3].type == PERCENTAGE) return PARSE_INVALID;
        rgba[3] = clip01(args[3].value);
    } else rgba[3] = 1;
    if (is_rgb) {
        double divisor;
        if (args[0].type == INTEGER && args[1].type == INTEGER && args[2].type == INTEGER) divisor = 255;
        else if (args[0].type == PERCENTAGE && args[1].type == PERCENTAGE && args[2].type == PERCENTAGE) divisor = 100;
        else return PARSE_INVALID;
        for (unsigned i = 0; i < 3; i++) rgba[i] = args[i].value / divisor;
    } else {
        if (args[0].type != INTEGER || args[1].type != PERCENTAGE || args[2].type != PERCENTAGE) return PARSE_INVALID;
        hsl_to_rgb(args[0].value, args[1].value, args[2].value, rgba, rgba + 1, rgba + 2);
    }
    return PARSE_OK;
}

static ParseResult
parse_hash(Parser *p, double rgba[4]) {
    Py_ssize_t start = ++p->pos;
    while (p->pos < p->len && is_nmchar(p->s[p->pos])) p->pos++;
    Py_ssize_t n = p->pos - start;
    ParseResult r = check_at_end(p);
    if (r != PARSE_OK) return r;
    if (n != 3 && n != 6) return PARSE_INVALID;
    int vals[6];
    for (Py_ssize_t i = 0; i < n; i++) {
        if ((vals[i] = hex_value(p->s[start + i])) < 0) return PARSE_INVALID;
    }
    for (unsigned i = 0; i < 3; i++) {
        int v = n == 3 ? vals[i] * 17 : vals[2 * i] * 16 + vals[2 * i + 1];
        rgba[i] = v / 255.;
    }
    rgba[3] = 1;
    return PARSE_OK;
}

PyObject *
tinycss_parse_color_string(PyObject *self, PyObject *src) {
    (void)self;
    if (!PyUnicode_Check(src)) {
        PyErr_SetString(PyExc_TypeError, "parse_color_string() argument must be a str");
        return NULL;
    }
    Py_ssize_t len = PyUnicode_GET_LENGTH(src);
    if (!PyUnicode_IS_ASCII(src)) Py_RETURN_NOTIMPLEMENTED;
    const Py_UCS1 *data = PyUnicode_1BYTE_DATA(src);
    if (memchr(data, '\\', len) != NULL) Py_RETURN_NOTIMPLEMENTED;
    // Same as str.strip()
    Py_ssize_t start = 0;
    while (start < len && Py_UNICODE_ISSPACE(data[start])) start++;
    while (len > start && Py_UNICODE_ISSPACE(data[len - 1])) len--;
    Parser p = {.s = data, .pos = start, .len = len};
    double rgba[4];
    ParseResult r = skip_ignorable(&p, false);
    if (r == PARSE_OK) {
        Py_UCS1 ch = peek(&p, 0);
        if (ch == '#') r = parse_hash(&p, rgba);
        else if (ch == '-' || ch == '_' || ('a' <= ch && ch <= 'z') || ('A' <= ch && ch <= 'Z')) {
            char name[32];
            Py_ssize_t nstart = p.pos;
            while (p.pos < p.len && is_nmchar(p.s[p.pos])) p.pos++;
            Py_ssize_t n = p.pos - nstart;
            if (n >= (Py_ssize_t)sizeof(name)) r = PARSE_INVALID; // longer than any keyword
            else {
                for (Py_ssize_t i = 0; i < n; i++) name[i] = (char)Py_TOLOWER(p.s[nstart + i]);
                name[n] = 0;
                if (peek(&p, 0) == '(') r = parse_function(&p, name, rgba);
                else if ((r = check_at_end(&p)) == PARSE_OK) {
                    if (strcmp(name, "currentcolor") == 0) return PyUnicode_FromString("currentColor");
                    if (strcmp(name, "transparent") == 0) {
                        rgba[0] = rgba[1] = rgba[2] = rgba[3] = 0;
                    } else {
                        const ColorKeyword *kw = bsearch(name, color_keywords, arraysz(color_keywords), sizeof(color_keywords[0]), compare_keyword);
                        if (kw == NULL) r = PARSE_INVALID;
                        else {
                            rgba[0] = kw->r / 255.;
                            rgba[1] = kw->g / 255.;
                            rgba[2] = kw->b / 255.;
                            rgba[3] = 1;
                        }
                    }
                }
            }
        } else r = PARSE_INVALID;
    }
    switch (r) {
        case PARSE_OK: return Py_BuildValue("dddd", rgba[0], rgba[1], rgba[2], rgba[3]);
        case PARSE_INVALID: Py_RETURN_NONE;
        case PARSE_FALLBACK: break;
    }
    Py_RETURN_NOTIMPLEMENTED;
}

// CSS Color Module Level 4 {{{

typedef enum { C_NUMBER, C_PERCENTAGE, C_DIMENSION, C_IDENT, C_COMMA, C_SLASH } ComponentType;

typedef struct {
    ComponentType type;
    double value;
    char name[16]; // lowercased unit for C_DIMENSION or name for C_IDENT
} Component;

typedef enum { HUE, PERCENT_OR_NUMBER, NUMBER_ONLY, PERCENT_ONLY } ComponentKind;

#define MAX_COMPONENTS 16

static bool
read_name(Parser *p, char *buf, size_t bufsz) {
    Py_ssize_t start = p->pos;
    while (p->pos < p->len && is_nmchar(p->s[p->pos])) p->pos++;
    Py_ssize_t n = p->pos - start;
    if (n < 1 || (size_t)n >= bufsz) return false;
    for (Py_ssize_t i = 0; i < n; i++) buf[i] = (char)Py_TOLOWER(p->s[start + i]);
    buf[n] = 0;
    return true;
}

static inline bool
is_name_start(Py_UCS1 ch) {
    return ch == '-' || ch == '_' || ('a' <= ch && ch <= 'z') || ('A' <= ch && ch <= 'Z');
}

// Implements the number token from CSS Syntax Level 3, followed by an optional % or unit
static ParseResult
parse_css4_number(Parser *p, Component *c) {
    Py_ssize_t start = p->pos, digits = 0;
    char buf[128];
    if (peek(p, 0) == '+' || peek(p, 0) == '-') p->pos++;
    while (is_digit(peek(p, 0))) {
        p->pos++;
        digits++;
    }
    if (peek(p, 0) == '.' && is_digit(peek(p, 1))) {
        p->pos++;
        while (is_digit(peek(p, 0))) {
            p->pos++;
            digits++;
        }
    }
    if (!digits) return PARSE_INVALID;
    Py_UCS1 e = peek(p, 0);
    if (e == 'e' || e == 'E') {
        if (is_digit(peek(p, 1))) p->pos++;
        else if ((peek(p, 1) == '+' || peek(p, 1) == '-') && is_digit(peek(p, 2))) p->pos += 2;
        while (is_digit(peek(p, 0))) p->pos++;
    }
    Py_ssize_t sz = p->pos - start;
    if (sz >= (Py_ssize_t)sizeof(buf)) return PARSE_INVALID;
    memcpy(buf, p->s + start, sz);
    buf[sz] = 0;
    c->value = strtod(buf, NULL);
    if (!isfinite(c->value)) return PARSE_INVALID;
    if (peek(p, 0) == '%') {
        p->pos++;
        c->type = C_PERCENTAGE;
    } else if (is_name_start(peek(p, 0))) {
        if (!read_name(p, c->name, sizeof(c->name))) return PARSE_INVALID;
        c->type = C_DIMENSION;
    } else c->type = C_NUMBER;
    return PARSE_OK;
}

// Tokenize the arguments of a color function, the parser must be positioned after the (
static ParseResult
tokenize_css4_args(Parser *p, Component *components, unsigned *count) {
    unsigned n = 0;
    while (true) {
        skip_ignorable(p, true);
        if (p->pos >= p->len) break; // EOF closes the function
        Py_UCS1 ch = p->s[p->pos];
        if (ch == ')') {
            p->pos++;
            break;
        }
        if (n >= MAX_COMPONENTS) return PARSE_INVALID;
        Component *c = components + n++;
        if (ch == ',') {
            c->type = C_COMMA;
            p->pos++;
        } else if (ch == '/') {
            c->type = C_SLASH;
            p->pos++;
        } else if (is_digit(ch) || ch == '.' || ch == '+' || (ch == '-' && (is_digit(peek(p, 1)) || peek(p, 1) == '.'))) {
            if (parse_css4_number(p, c) != PARSE_OK) return PARSE_INVALID;
        } else if (is_name_start(ch)) {
            if (!read_name(p, c->name, sizeof(c->name))) return PARSE_INVALID;
            if (peek(p, 0) == '(') return PARSE_INVALID; // nested functions such as calc() or var()
            c->type = C_IDENT;
        } else return PARSE_INVALID;
    }
    *count = n;
    return PARSE_OK;
}

static inline bool
is_none(const Component *c) {
    return c->type == C_IDENT && strcmp(c->name, "none") == 0;
}

// Resolve a component to a number. Percentages are scaled so that 100% == pct_ref.
// Hues are returned in degrees.
static bool
resolve_component(const Component *c, ComponentKind kind, double pct_ref, bool allow_none, double *ans) {
    if (is_none(c)) {
        *ans = 0;
        return allow_none;
    }
    switch (c->type) {
        case C_NUMBER:
            if (kind == PERCENT_ONLY) return false;
            *ans = c->value;
            return true;
        case C_PERCENTAGE:
            if (kind == NUMBER_ONLY || kind == HUE) return false;
            *ans = c->value / 100. * pct_ref;
            return true;
        case C_DIMENSION:
            if (kind != HUE) return false;
            if (strcmp(c->name, "deg") == 0) *ans = c->value;
            else if (strcmp(c->name, "grad") == 0) *ans = c->value * 0.9;
            else if (strcmp(c->name, "rad") == 0) *ans = c->value * 180. / M_PI;
            else if (strcmp(c->name, "turn") == 0) *ans = c->value * 360.;
            else return false;
            return true;
        default: return false;
    }
}

static bool
resolve_alpha(const Component *c, bool allow_none, double *ans) {
    if (!resolve_component(c, PERCENT_OR_NUMBER, 1, allow_none, ans)) return false;
    *ans = clip01(*ans);
    return true;
}

static void
mat3_mul(const double m[3][3], const double v[3], double out[3]) {
    for (unsigned i = 0; i < 3; i++) out[i] = m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2];
}

// Matrices and transfer functions from the sample code in the CSS Color 4 specification
static const double XYZ_D65_to_lin_sRGB[3][3] = {
    {12831. / 3959., -329. / 214., -1974. / 3959.},
    {-851781. / 878810., 1648619. / 878810., 36519. / 878810.},
    {705. / 12673., -2585. / 12673., 705. / 667.},
};
static const double D50_to_D65[3][3] = {
    {0.955473421488075, -0.02309845494876471, 0.06325924320057072},
    {-0.0283697093338637, 1.0099953980813041, 0.021041441191917323},
    {0.012314014864481998, -0.020507649298898964, 1.330365926242124},
};
static const double lin_P3_to_XYZ[3][3] = {
    {608311. / 1250200., 189793. / 714400., 198249. / 1000160.},
    {35783. / 156275., 247089. / 357200., 198249. / 2500400.},
    {0., 32229. / 714400., 5220557. / 5000800.},
};
static const double lin_a98rgb_to_XYZ[3][3] = {
    {573536. / 994567., 263643. / 1420810., 187206. / 994567.},
    {591459. / 1989134., 6239551. / 9945670., 374412. / 4972835.},
    {53769. / 1989134., 351524. / 4972835., 4929758. / 4972835.},
};
static const double lin_ProPhoto_to_XYZ_D50[3][3] = {
    {0.79776664490064230, 0.13518129740053308, 0.03134773412839220},
    {0.28807482881940130, 0.71183523424187300, 0.00008993693872564},
    {0.0, 0.0, 0.82510460251046020},
};
static const double lin_2020_to_XYZ[3][3] = {
    {63426534. / 99577255., 20160776. / 139408157., 47086771. / 278816314.},
    {26158966. / 99577255., 472592308. / 697040785., 8267143. / 139408157.},
    {0., 19567812. / 697040785., 295819943. / 278816314.},
};
static const double OKLab_to_LMS[3][3] = {
    {1.0, 0.3963377773761749, 0.2158037573099136},
    {1.0, -0.1055613458156586, -0.0638541728258133},
    {1.0, -0.0894841775298119, -1.2914855480194092},
};
static const double LMS_to_XYZ[3][3] = {
    {1.2268798758459243, -0.5578149944602171, 0.2813910456659647},
    {-0.0405757452148008, 1.1122868032803170, -0.0717110580655164},
    {-0.0763729366746601, -0.4214933324022432, 1.5869240198367816},
};

static double
srgb_to_linear(double v) {
    double a = fabs(v);
    return a <= 0.04045 ? v / 12.92 : copysign(pow((a + 0.055) / 1.055, 2.4), v);
}

static double
linear_to_srgb(double v) {
    double a = fabs(v);
    return a > 0.0031308 ? copysign(1.055 * pow(a, 1 / 2.4) - 0.055, v) : 12.92 * v;
}

static double
a98_to_linear(double v) {
    return copysign(pow(fabs(v), 563. / 256.), v);
}

static double
prophoto_to_linear(double v) {
    double a = fabs(v);
    return a <= 16. / 512. ? v / 16. : copysign(pow(a, 1.8), v);
}

static double
rec2020_to_linear(double v) {
    const double alpha = 1.09929682680944, beta = 0.018053968510807;
    double a = fabs(v);
    return a < beta * 4.5 ? v / 4.5 : copysign(pow((a + alpha - 1) / alpha, 1 / 0.45), v);
}

static void
xyz_d65_to_srgb(const double xyz[3], double rgba[4]) {
    double lin[3];
    mat3_mul(XYZ_D65_to_lin_sRGB, xyz, lin);
    for (unsigned i = 0; i < 3; i++) rgba[i] = linear_to_srgb(lin[i]);
}

static void
xyz_d50_to_srgb(const double xyz[3], double rgba[4]) {
    double d65[3];
    mat3_mul(D50_to_D65, xyz, d65);
    xyz_d65_to_srgb(d65, rgba);
}

static void
lab_to_srgb(double L, double a, double b, double rgba[4]) {
    const double kappa = 24389. / 27., epsilon = 216. / 24389.;
    const double white[3] = {0.3457 / 0.3585, 1.0, (1.0 - 0.3457 - 0.3585) / 0.3585};
    double f1 = (L + 16) / 116, f0 = a / 500 + f1, f2 = f1 - b / 200;
    double xyz[3] = {
        f0 * f0 * f0 > epsilon ? f0 * f0 * f0 : (116 * f0 - 16) / kappa,
        L > kappa * epsilon ? f1 * f1 * f1 : L / kappa,
        f2 * f2 * f2 > epsilon ? f2 * f2 * f2 : (116 * f2 - 16) / kappa,
    };
    for (unsigned i = 0; i < 3; i++) xyz[i] *= white[i];
    xyz_d50_to_srgb(xyz, rgba);
}

static void
oklab_to_srgb(double L, double a, double b, double rgba[4]) {
    double lab[3] = {L, a, b}, lms[3], xyz[3];
    mat3_mul(OKLab_to_LMS, lab, lms);
    for (unsigned i = 0; i < 3; i++) lms[i] = lms[i] * lms[i] * lms[i];
    mat3_mul(LMS_to_XYZ, lms, xyz);
    xyz_d65_to_srgb(xyz, rgba);
}

static bool
predefined_space_to_srgb(const char *space, const double c[3], double rgba[4]) {
    double lin[3], xyz[3];
    double (*transfer)(double) = NULL;
    const double (*matrix)[3] = NULL;
    bool d50 = false;
    if (strcmp(space, "srgb") == 0) {
        for (unsigned i = 0; i < 3; i++) rgba[i] = c[i];
        return true;
    }
    if (strcmp(space, "srgb-linear") == 0) {
        for (unsigned i = 0; i < 3; i++) rgba[i] = linear_to_srgb(c[i]);
        return true;
    }
    if (strcmp(space, "xyz") == 0 || strcmp(space, "xyz-d65") == 0) {
        xyz_d65_to_srgb(c, rgba);
        return true;
    }
    if (strcmp(space, "xyz-d50") == 0) {
        xyz_d50_to_srgb(c, rgba);
        return true;
    }
    if (strcmp(space, "display-p3") == 0) {
        transfer = srgb_to_linear;
        matrix = lin_P3_to_XYZ;
    } else if (strcmp(space, "a98-rgb") == 0) {
        transfer = a98_to_linear;
        matrix = lin_a98rgb_to_XYZ;
    } else if (strcmp(space, "prophoto-rgb") == 0) {
        transfer = prophoto_to_linear;
        matrix = lin_ProPhoto_to_XYZ_D50;
        d50 = true;
    } else if (strcmp(space, "rec2020") == 0) {
        transfer = rec2020_to_linear;
        matrix = lin_2020_to_XYZ;
    } else return false;
    for (unsigned i = 0; i < 3; i++) lin[i] = transfer(c[i]);
    mat3_mul(matrix, lin, xyz);
    if (d50) xyz_d50_to_srgb(xyz, rgba);
    else xyz_d65_to_srgb(xyz, rgba);
    return true;
}

static void
hwb_to_rgb(double hue, double white, double black, double rgba[4]) {
    if (white + black >= 1) {
        rgba[0] = rgba[1] = rgba[2] = white / (white + black);
        return;
    }
    hsl_to_rgb_unclamped(hue, 1, 0.5, rgba, rgba + 1, rgba + 2);
    for (unsigned i = 0; i < 3; i++) rgba[i] = rgba[i] * (1 - white - black) + white;
}

typedef enum { F_RGB, F_HSL, F_HWB, F_LAB, F_LCH, F_OKLAB, F_OKLCH, F_COLOR } ColorFunction;

static ParseResult
parse_css4_function(Parser *p, const char *name, double rgba[4]) {
    ColorFunction func;
    if (strcmp(name, "rgb") == 0 || strcmp(name, "rgba") == 0) func = F_RGB;
    else if (strcmp(name, "hsl") == 0 || strcmp(name, "hsla") == 0) func = F_HSL;
    else if (strcmp(name, "hwb") == 0) func = F_HWB;
    else if (strcmp(name, "lab") == 0) func = F_LAB;
    else if (strcmp(name, "lch") == 0) func = F_LCH;
    else if (strcmp(name, "oklab") == 0) func = F_OKLAB;
    else if (strcmp(name, "oklch") == 0) func = F_OKLCH;
    else if (strcmp(name, "color") == 0) func = F_COLOR;
    else return PARSE_INVALID;
    p->pos++; // skip (
    Component tokens[MAX_COMPONENTS];
    unsigned ntokens = 0;
    if (tokenize_css4_args(p, tokens, &ntokens) != PARSE_OK) return PARSE_INVALID;
    skip_ignorable(p, true);
    if (p->pos != p->len) return PARSE_INVALID;

    // Split into the channel components and the optional alpha
    const Component *channels[4], *alpha = NULL;
    unsigned nchannels = 0;
    bool legacy = ntokens > 1 && tokens[1].type == C_COMMA;
    if (legacy) {
        // rgb(r, g, b[, a]) and hsl(h, s, l[, a])
        if (func != F_RGB && func != F_HSL) return PARSE_INVALID;
        if (ntokens != 5 && ntokens != 7) return PARSE_INVALID;
        for (unsigned i = 0; i < ntokens; i++) {
            if ((i % 2 == 1) != (tokens[i].type == C_COMMA)) return PARSE_INVALID;
            if (i % 2 == 0) {
                if (tokens[i].type == C_IDENT || tokens[i].type == C_SLASH) return PARSE_INVALID; // none is not allowed
                if (i < 6) channels[nchannels++] = tokens + i;
                else alpha = tokens + i;
            }
        }
    } else {
        unsigned i = 0;
        for (; i < ntokens && tokens[i].type != C_SLASH; i++) {
            if (tokens[i].type == C_COMMA || nchannels >= arraysz(channels)) return PARSE_INVALID;
            channels[nchannels++] = tokens + i;
        }
        if (i < ntokens) {
            // tokens[i] is the slash
            if (ntokens != i + 2 || tokens[i + 1].type == C_COMMA || tokens[i + 1].type == C_SLASH) return PARSE_INVALID;
            alpha = tokens + i + 1;
        }
    }
    rgba[3] = 1;
    if (alpha != NULL && !resolve_alpha(alpha, !legacy, rgba + 3)) return PARSE_INVALID;

    const char *space = NULL;
    if (func == F_COLOR) {
        if (nchannels < 1 || channels[0]->type != C_IDENT) return PARSE_INVALID;
        space = channels[0]->name;
        memmove(channels, channels + 1, (--nchannels) * sizeof(channels[0]));
    }
    if (nchannels != 3) return PARSE_INVALID;
    const bool allow_none = !legacy;
    double c[3];
#define R(idx, kind, ref) \
    if (!resolve_component(channels[idx], kind, ref, allow_none, c + idx)) return PARSE_INVALID;
    switch (func) {
        case F_RGB:
            if (legacy) {
                // All three must be numbers or all three must be percentages
                ComponentType t = channels[0]->type;
                if ((t != C_NUMBER && t != C_PERCENTAGE) || channels[1]->type != t || channels[2]->type != t) return PARSE_INVALID;
            }
            for (unsigned i = 0; i < 3; i++) {
                R(i, PERCENT_OR_NUMBER, 255);
                rgba[i] = c[i] / 255;
            }
            break;
        case F_HSL:
            R(0, HUE, 0);
            R(1, legacy ? PERCENT_ONLY : PERCENT_OR_NUMBER, 100);
            R(2, legacy ? PERCENT_ONLY : PERCENT_OR_NUMBER, 100);
            // negative saturation is clamped to zero at parse time
            hsl_to_rgb_unclamped(c[0], fmax(0, c[1]) / 100, c[2] / 100, rgba, rgba + 1, rgba + 2);
            break;
        case F_HWB:
            R(0, HUE, 0);
            R(1, PERCENT_OR_NUMBER, 100);
            R(2, PERCENT_OR_NUMBER, 100);
            hwb_to_rgb(c[0], c[1] / 100, c[2] / 100, rgba);
            break;
        case F_LAB:
            R(0, PERCENT_OR_NUMBER, 100);
            R(1, PERCENT_OR_NUMBER, 125);
            R(2, PERCENT_OR_NUMBER, 125);
            lab_to_srgb(fmin(100, fmax(0, c[0])), c[1], c[2], rgba);
            break;
        case F_LCH: {
            R(0, PERCENT_OR_NUMBER, 100);
            R(1, PERCENT_OR_NUMBER, 150);
            R(2, HUE, 0);
            double chroma = fmax(0, c[1]), h = c[2] * M_PI / 180.;
            lab_to_srgb(fmin(100, fmax(0, c[0])), chroma * cos(h), chroma * sin(h), rgba);
        } break;
        case F_OKLAB:
            R(0, PERCENT_OR_NUMBER, 1);
            R(1, PERCENT_OR_NUMBER, 0.4);
            R(2, PERCENT_OR_NUMBER, 0.4);
            oklab_to_srgb(clip01(c[0]), c[1], c[2], rgba);
            break;
        case F_OKLCH: {
            R(0, PERCENT_OR_NUMBER, 1);
            R(1, PERCENT_OR_NUMBER, 0.4);
            R(2, HUE, 0);
            double chroma = fmax(0, c[1]), h = c[2] * M_PI / 180.;
            oklab_to_srgb(clip01(c[0]), chroma * cos(h), chroma * sin(h), rgba);
        } break;
        case F_COLOR:
            for (unsigned i = 0; i < 3; i++) { R(i, PERCENT_OR_NUMBER, 1); }
            if (!predefined_space_to_srgb(space, c, rgba)) return PARSE_INVALID;
            break;
    }
#undef R
    return PARSE_OK;
}

static ParseResult
parse_css4_hash(Parser *p, double rgba[4]) {
    Py_ssize_t start = ++p->pos;
    while (p->pos < p->len && is_nmchar(p->s[p->pos])) p->pos++;
    Py_ssize_t n = p->pos - start;
    skip_ignorable(p, true);
    if (p->pos != p->len) return PARSE_INVALID;
    if (n != 3 && n != 4 && n != 6 && n != 8) return PARSE_INVALID;
    int vals[8];
    for (Py_ssize_t i = 0; i < n; i++) {
        if ((vals[i] = hex_value(p->s[start + i])) < 0) return PARSE_INVALID;
    }
    bool short_form = n < 6;
    rgba[3] = 1;
    for (unsigned i = 0; i < (unsigned)(short_form ? n : n / 2); i++) {
        int v = short_form ? vals[i] * 17 : vals[2 * i] * 16 + vals[2 * i + 1];
        rgba[i] = v / 255.;
    }
    return PARSE_OK;
}

PyObject *
tinycss_parse_css4_color_string(PyObject *self, PyObject *src) {
    (void)self;
    if (!PyUnicode_Check(src)) {
        PyErr_SetString(PyExc_TypeError, "parse_css4_color_string() argument must be a str");
        return NULL;
    }
    // No valid color contains escapes or non-ASCII characters
    if (!PyUnicode_IS_ASCII(src)) Py_RETURN_NONE;
    Py_ssize_t len = PyUnicode_GET_LENGTH(src);
    const Py_UCS1 *data = PyUnicode_1BYTE_DATA(src);
    if (memchr(data, '\\', len) != NULL) Py_RETURN_NONE;
    Parser p = {.s = data, .pos = 0, .len = len, .css4 = true};
    double rgba[4];
    ParseResult r = PARSE_INVALID;
    skip_ignorable(&p, true);
    Py_UCS1 ch = peek(&p, 0);
    if (ch == '#') r = parse_css4_hash(&p, rgba);
    else if (is_name_start(ch)) {
        char name[32];
        if (read_name(&p, name, sizeof(name))) {
            if (peek(&p, 0) == '(') r = parse_css4_function(&p, name, rgba);
            else {
                skip_ignorable(&p, true);
                if (p.pos == p.len) {
                    if (strcmp(name, "currentcolor") == 0) return PyUnicode_FromString("currentColor");
                    r = PARSE_OK;
                    if (strcmp(name, "transparent") == 0) {
                        rgba[0] = rgba[1] = rgba[2] = rgba[3] = 0;
                    } else if (strcmp(name, "rebeccapurple") == 0) {
                        rgba[0] = 102 / 255.;
                        rgba[1] = 51 / 255.;
                        rgba[2] = 153 / 255.;
                        rgba[3] = 1;
                    } else {
                        const ColorKeyword *kw = bsearch(name, color_keywords, arraysz(color_keywords), sizeof(color_keywords[0]), compare_keyword);
                        if (kw == NULL) r = PARSE_INVALID;
                        else {
                            rgba[0] = kw->r / 255.;
                            rgba[1] = kw->g / 255.;
                            rgba[2] = kw->b / 255.;
                            rgba[3] = 1;
                        }
                    }
                }
            }
        }
    }
    if (r != PARSE_OK) Py_RETURN_NONE;
    // Colors outside the sRGB gamut are clipped
    return Py_BuildValue("dddd", clip01(rgba[0]), clip01(rgba[1]), clip01(rgba[2]), clip01(rgba[3]));
}
// }}}
