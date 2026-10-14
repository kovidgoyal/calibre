/*
 * html_entities.cpp
 * Copyright (C) 2024 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#define UNICODE
#define _UNICODE
#include <Python.h>
#include <stdbool.h>
#include "html_entities.h"

unsigned int
encode_utf8(uint32_t ch, char *dest) {
    if (ch < 0x80) {        // only lower 7 bits can be 1
        dest[0] = (char)ch; // 0xxxxxxx
        return 1;
    }
    if (ch < 0x800) {                 // only lower 11 bits can be 1
        dest[0] = (ch >> 6) | 0xC0;   // 110xxxxx
        dest[1] = (ch & 0x3F) | 0x80; // 10xxxxxx
        return 2;
    }
    if (ch < 0x10000) {                      // only lower 16 bits can be 1
        dest[0] = (ch >> 12) | 0xE0;         // 1110xxxx
        dest[1] = ((ch >> 6) & 0x3F) | 0x80; // 10xxxxxx
        dest[2] = (ch & 0x3F) | 0x80;        // 10xxxxxx
        return 3;
    }
    if (ch < 0x110000) {                      // only lower 21 bits can be 1
        dest[0] = (ch >> 18) | 0xF0;          // 11110xxx
        dest[1] = ((ch >> 12) & 0x3F) | 0x80; // 10xxxxxx
        dest[2] = ((ch >> 6) & 0x3F) | 0x80;  // 10xxxxxx
        dest[3] = (ch & 0x3F) | 0x80;         // 10xxxxxx
        return 4;
    }
    return 0;
}

static uint32_t
parse_base10_integer(const char *input, size_t sz, bool *ok) {
    uint32_t ans = 0;
    *ok = true;
    for (size_t i = 0; i < sz; i++) {
        char ch = input[i];
        if (ch < '0' || ch > '9') {
            *ok = false;
            return 0;
        }
        uint32_t digit = ch - '0';
        ans = ans * 10 + digit;
    }
    return ans;
}

static uint32_t
parse_base16_integer(const char *input, size_t sz, bool *ok) {
    uint32_t ans = 0;
    *ok = true;
    for (size_t i = 0; i < sz; i++) {
        char ch = input[i];
        uint32_t digit;
        if ('a' <= ch && ch <= 'f') digit = 10 + ch - 'a';
        else if ('A' <= ch && ch <= 'F') digit = 10 + ch - 'A';
        else {
            if (ch < '0' || ch > '9') {
                *ok = false;
                return 0;
            }
            digit = ch - '0';
        }
        ans = ans * 16 + digit;
    }
    return ans;
}

static bool
is_xml_unsafe(uint32_t codepoint) {
    return codepoint == '<' || codepoint == '>' || codepoint == '&' || codepoint == '"' || codepoint == '\'';
}

// Largest number of bytes convert_entity() can write: four for a numeric
// entity, or the UTF-8 length of the longest named entity value.
#define MAX_ENTITY_OUTPUT 32

static int
convert_entity(const char *entity, const size_t elen, char *output, bool keep_xml_entities) {
    if (entity[0] == '#') {
        if (elen < 2) return -1;
        uint32_t codepoint = 0;
        bool ok = false;
        if (entity[1] == 'x' || entity[1] == 'X') {
            if (elen > 2) codepoint = parse_base16_integer(entity + 2, elen - 2, &ok);
        } else {
            codepoint = parse_base10_integer(entity + 1, elen - 1, &ok);
        }
        if (!ok || (keep_xml_entities && is_xml_unsafe(codepoint))) return -1;
        return codepoint ? encode_utf8(codepoint, output) : 0;
    }
    const struct html_entity *s = in_word_set(entity, elen);
    if (!s) return -1;
    size_t ans = strlen(s->val);
    if (ans > MAX_ENTITY_OUTPUT) return -1;
    if (keep_xml_entities && ans == 1 && is_xml_unsafe(s->val[0])) return -1;
    memcpy(output, s->val, ans);
    return ans;
}

typedef struct {
    char *data;
    size_t pos, capacity;
} Output;

// Decoding an entity can produce more bytes than the entity itself (for
// example &nGt; is five bytes and decodes to six), so the output buffer must
// be grown on demand rather than sized from the input.
static bool
ensure_space(Output *o, size_t extra) {
    if (o->capacity - o->pos >= extra) return true;
    size_t needed = o->pos + extra;
    if (needed < o->pos) return false;
    size_t new_capacity = o->capacity > SIZE_MAX / 2 ? SIZE_MAX : o->capacity * 2;
    if (new_capacity < needed) new_capacity = needed;
    char *d = realloc(o->data, new_capacity);
    if (!d) return false;
    o->data = d;
    o->capacity = new_capacity;
    return true;
}

static bool
write_output(Output *o, const char *src, size_t sz) {
    if (!ensure_space(o, sz)) return false;
    memcpy(o->data + o->pos, src, sz);
    o->pos += sz;
    return true;
}

static bool
add_entity(const char *entity, const size_t elen, Output *o, bool keep_xml_entities) {
    char buf[MAX_ENTITY_OUTPUT];
    int ans;
    if (elen > 64 || elen < 3 || (ans = convert_entity(entity + 1, elen - 2, buf, keep_xml_entities)) < 0) return write_output(o, entity, elen);
    return write_output(o, buf, ans);
}


static bool
process_entity(const char *input, size_t input_sz, Output *o, size_t *consumed, bool keep_xml_entities) {
    size_t input_pos = 1; // ignore leading &
    while (input_pos < input_sz) {
        char ch = input[input_pos++];
        if (('a' <= ch && ch <= 'z') || ('A' <= ch && ch <= 'Z') || ('0' <= ch && ch <= '9') || (ch == '#' && input_pos == 2))
            ;
        else if (ch == ';') {
            *consumed = input_pos;
            return add_entity(input, input_pos, o, keep_xml_entities);
        } else break;
    }
    *consumed = input_pos;
    return write_output(o, input, input_pos);
}

static bool
replace(const char *input, size_t input_sz, Output *o, int keep_xml_entities) {
    size_t input_pos = 0;
    while (input_pos < input_sz) {
        const char *p = (const char *)memchr(input + input_pos, '&', input_sz - input_pos);
        if (p) {
            size_t before_amp = p - (input + input_pos), consumed = 0;
            if (!write_output(o, input + input_pos, before_amp)) return false;
            input_pos += before_amp;
            if (!process_entity(p, input_sz - input_pos, o, &consumed, keep_xml_entities)) return false;
            input_pos += consumed;
        } else {
            if (!write_output(o, input + input_pos, input_sz - input_pos)) return false;
            input_pos = input_sz;
        }
    }
    return true;
}

static PyObject *
replace_all_entities(PyObject *self, PyObject *const *args, Py_ssize_t nargs) {
    if (nargs < 1) {
        PyErr_SetString(PyExc_TypeError, "Must specify string tp process");
        return NULL;
    }
    const char *input = NULL;
    Py_ssize_t input_sz = 0;
    int keep_xml_entities = false;
    if (PyUnicode_Check(args[0])) {
        input = PyUnicode_AsUTF8AndSize(args[0], &input_sz);
        if (!input) return NULL;
    } else if (PyBytes_Check(args[0])) {
        input = PyBytes_AS_STRING(args[0]);
        input_sz = PyBytes_GET_SIZE(args[0]);
    } else {
        PyErr_SetString(PyExc_TypeError, "string must be unicode object or UTF-8 encoded bytes");
        return NULL;
    }
    if (nargs > 1) {
        keep_xml_entities = PyObject_IsTrue(args[1]);
        if (keep_xml_entities < 0) return NULL;
    }
    // Room for a few expanding entities up front, the buffer grows if more are needed
    Output o = {.capacity = (size_t)input_sz + 64};
    o.data = malloc(o.capacity);
    if (!o.data) { return PyErr_NoMemory(); }
    bool ok;
    Py_BEGIN_ALLOW_THREADS ok = replace(input, input_sz, &o, keep_xml_entities);
    Py_END_ALLOW_THREADS PyObject *retval;
    if (!ok) retval = PyErr_NoMemory();
    else if (!o.pos) retval = Py_NewRef(args[0]);
    else if (PyUnicode_Check(args[0])) retval = PyUnicode_FromStringAndSize(o.data, o.pos);
    else retval = PyBytes_FromStringAndSize(o.data, o.pos);
    free(o.data);
    return retval;
}

static PyMethodDef methods[] = {
    {"replace_all_entities", (PyCFunction)replace_all_entities, METH_FASTCALL, "Replace all entities in the specified string"}, {NULL, NULL, 0, NULL}};

static int
exec_module(PyObject *m) {
    return 0;
}

CALIBRE_MODINIT_FUNC
PyInit_fast_html_entities(void) {
    static PyModuleDef_Slot slots[] = {{Py_mod_exec, (void *)exec_module}, {0, NULL}};
    static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

    module_def.m_name = "fast_html_entities";
    module_def.m_doc = "Fast conversion of HTML entities";
    module_def.m_methods = methods;
    module_def.m_slots = slots;
    return PyModuleDef_Init(&module_def);
}
