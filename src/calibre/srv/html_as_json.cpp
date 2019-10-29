/*
 * html_as_json.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <Python.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>
#include <string>

typedef struct {
    PyObject_HEAD
    /* Type-specific fields go here. */
	PyObject *buf;
	size_t used;
	std::vector<std::string> *nsmap;
} Serializer;


static void
dealloc(Serializer* self)
{
	Py_CLEAR(self->buf);
	if (self->nsmap) delete self->nsmap;
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
alloc(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    Serializer *self;

    self = (Serializer *)type->tp_alloc(type, 0);
	if (self != NULL) {
		self->used = 0;
		self->buf = NULL;
		self->nsmap = new (std::nothrow) std::vector<std::string>();
		if (!self->nsmap) { PyErr_NoMemory(); dealloc(self); self = NULL; }
	}
    return (PyObject *)self;
}


static inline bool
ensure_space(Serializer *self, size_t amt) {
	size_t required = amt + self->used;
	if (!self->buf) {
		self->buf = PyBytes_FromStringAndSize(NULL, std::max(required, static_cast<size_t>(128u * 1024u)));
		if (!self->buf) return false;
		return true;
	}

	if (required > static_cast<size_t>(PyBytes_GET_SIZE(self->buf))) {
		if (_PyBytes_Resize(&(self->buf), std::max(required, static_cast<size_t>(2 * PyBytes_GET_SIZE(self->buf)))) != 0) return false;
	}
	return true;
}

static bool
write_data(Serializer *self, const char *data, size_t sz) {
	if (!ensure_space(self, sz)) return false;
	memcpy(PyBytes_AS_STRING(self->buf) + self->used, data, sz);
	self->used += sz;
	return true;
}

#define write_str_literal(self, x) write_data(self, x, sizeof(x)-1)

#define UTF8_ACCEPT 0
#define UTF8_REJECT 1

static const uint8_t utf8d[] = {
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 00..1f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 20..3f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 40..5f
  0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0, // 60..7f
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9, // 80..9f
  7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7,7, // a0..bf
  8,8,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2, // c0..df
  0xa,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x3,0x4,0x3,0x3, // e0..ef
  0xb,0x6,0x6,0x6,0x5,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8,0x8, // f0..ff
  0x0,0x1,0x2,0x3,0x5,0x8,0x7,0x1,0x1,0x1,0x4,0x6,0x1,0x1,0x1,0x1, // s0..s0
  1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,1,1,1,1,1,0,1,0,1,1,1,1,1,1, // s1..s2
  1,2,1,1,1,1,1,2,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1, // s3..s4
  1,2,1,1,1,1,1,1,1,2,1,1,1,1,1,1,1,1,1,1,1,1,1,3,1,3,1,1,1,1,1,1, // s5..s6
  1,3,1,1,1,1,1,3,1,3,1,1,1,1,1,1,1,3,1,1,1,1,1,1,1,1,1,1,1,1,1,1, // s7..s8
};

static inline void
utf8_decode_(uint32_t* state, uint32_t* codep, uint8_t byte) {
  /* Comes from http://bjoern.hoehrmann.de/utf-8/decoder/dfa/
   * Copyright (c) 2008-2009 Bjoern Hoehrmann <bjoern@hoehrmann.de>
   * Used under license: https://opensource.org/licenses/MIT
   */
  uint32_t type = utf8d[byte];

  *codep = (*state != UTF8_ACCEPT) ?
    (byte & 0x3fu) | (*codep << 6) :
    (0xff >> type) & (byte);

  *state = utf8d[256 + *state*16 + type];
}

static inline unsigned
utf8_read_char(const char *s, uint32_t *codep) {
	unsigned len = 0;
	uint32_t state = UTF8_ACCEPT;
	while(true) {
		utf8_decode_(&state, codep, s[len++]);
		if (state == UTF8_ACCEPT) break;
		else if (state == UTF8_REJECT) { return 0; }
	}
	return len;
}

static inline void
to_surrogate_pair(uint32_t unicode, uint16_t *uc, uint16_t *lc) {
	uint32_t n = unicode - 0x10000;
	*uc = ((n >> 10) & 0x3FF) | 0xD800;
	*lc = (n & 0x3FF) | 0xDC00;
}

static inline unsigned
write_hex16(char *out, uint16_t val) {
	static const char *hex = "0123456789ABCDEF";

	*out++ = hex[(val >> 12) & 0xF];
	*out++ = hex[(val >> 8)  & 0xF];
	*out++ = hex[(val >> 4)  & 0xF];
	*out++ = hex[ val        & 0xF];

	return 4;
}


static bool
write_string_as_json(Serializer *self, const char *str)
{
	const char *s = str;
	if (!ensure_space(self, 32)) return false;
	char *b = PyBytes_AS_STRING(self->buf) + self->used;

	*b++ = '"';
	while (*s != 0) {
		unsigned char c = *s++;

		/* Encode the next character, and write it to b. */
		switch (c) {
			case '"':
				*b++ = '\\';
				*b++ = '"';
				break;
			case '\\':
				*b++ = '\\';
				*b++ = '\\';
				break;
			case '\b':
				*b++ = '\\';
				*b++ = 'b';
				break;
			case '\f':
				*b++ = '\\';
				*b++ = 'f';
				break;
			case '\n':
				*b++ = '\\';
				*b++ = 'n';
				break;
			case '\r':
				*b++ = '\\';
				*b++ = 'r';
				break;
			case '\t':
				*b++ = '\\';
				*b++ = 't';
				break;
			default: {
				s--;
				uint32_t unicode;
				unsigned len = utf8_read_char(s, &unicode);
				if (len == 0) s++;
				else if (c < 0x1F) {
					/* Encode using \u.... */
					s += len;
					if (unicode <= 0xFFFF) {
						*b++ = '\\';
						*b++ = 'u';
						b += write_hex16(b, unicode);
					} else {
						/* Produce a surrogate pair. */
						uint16_t uc, lc;
						to_surrogate_pair(unicode, &uc, &lc);
						*b++ = '\\';
						*b++ = 'u';
						b += write_hex16(b, uc);
						*b++ = '\\';
						*b++ = 'u';
						b += write_hex16(b, lc);
					}
				} else {
					/* Write the character directly. */
					while (len-- > 0) *b++ = *s++;
				}

				break;
			}
		}

		/*
		 * Update self to know about the new bytes,
		 * and set up b to write another encoded character.
		 */
		self->used = b - PyBytes_AS_STRING(self->buf);
		if (!ensure_space(self, 32)) return false;
		b = PyBytes_AS_STRING(self->buf) + self->used;
	}
	*b++ = '"';
	self->used = b - PyBytes_AS_STRING(self->buf);
	return true;
}


static PyObject*
pywrite(Serializer *self, PyObject *arg) {
	const char *data;
	size_t sz;
	PyObject *temp = NULL;
	if (PyBytes_Check(arg)) {
		data = PyBytes_AS_STRING(arg);
		sz = PyBytes_GET_SIZE(arg);
	} else if (PyUnicode_Check(arg)) {
#if PY_MAJOR_VERSION > 2
		Py_ssize_t ssz;
		data = PyUnicode_AsUTF8AndSize(arg, &ssz);
		sz = ssz;
		if (data == NULL) return NULL;
#else
		temp = PyUnicode_AsUTF8String(arg);
		if (temp == NULL) return NULL;
		data = PyBytes_AS_STRING(temp);
		sz = PyBytes_GET_SIZE(temp);
#endif
	} else {
		PyErr_SetString(PyExc_TypeError, "A unicode or bytes object expected");
		return NULL;
	}
	bool ok = write_data(self, data, sz);
	Py_CLEAR(temp);
	if (!ok) return NULL;
	Py_RETURN_NONE;
}

static inline bool
namespaces_are_equal(const char *a, const char *b, size_t len) {
	for (size_t i = 0; i < len; i++) {
		if (a[i] != b[i]) return false;
		if (!b[i]) return true;
	}
	return true;
}

static inline int
namespace_index(Serializer *self, const char *ns, size_t nslen) {
	for (size_t i = 0; i < self->nsmap->size(); i++) {
		if (namespaces_are_equal((*self->nsmap)[i].c_str(), ns, nslen)) return i;
	}
	self->nsmap->push_back(std::string(ns, nslen));
	return self->nsmap->size() - 1;
}

static bool
write_attr(Serializer *self, PyObject *args) {
	const char *attr, *val;
#if PY_MAJOR_VERSION > 2
	if (!PyArg_ParseTuple(args, "ss", &attr, &val)) return false;
#else
	if (!PyArg_ParseTuple(args, "eses", "UTF-8", &attr, "UTF-8", &val)) return false;
#endif
	const char *b = strrchr(attr, '}');
	const char *attr_name = attr;
	int nsindex = -1;
	if (b) {
		nsindex = namespace_index(self, attr + 1, b - attr - 1);
		attr_name = b + 1;
	}
	if (!write_str_literal(self, "[")) goto end;
	if (!write_string_as_json(self, attr_name)) goto end;
	if (!write_str_literal(self, ",")) goto end;
	if (!write_string_as_json(self, val)) goto end;
	if (nsindex > -1) {
		char buf[32];
		write_data(self, buf, snprintf(buf, sizeof(buf), ",%d", nsindex));
	}
	if (!write_str_literal(self, "]")) goto end;

end:
#if PY_MAJOR_VERSION < 3
	PyMem_Free(attr); PyMem_Free(val);
#endif
	return PyErr_Occurred() ? false : true;
}

static PyObject*
start_tag(Serializer *self, PyObject *args) {
	const char *tag, *text, *tail;
	PyObject *items;
#if PY_MAJOR_VERSION > 2
	if (!PyArg_ParseTuple(args, "zzzO!", &tag, &text, &tail, &PyList_Type, &items)) return NULL;
#else
	if (!PyArg_ParseTuple(args, "etetetO!", "UTF-8", &tag, "UTF-8", &text, "UTF-8", &tail, &PyList_Type, &items)) return NULL;
#endif
	Py_ssize_t num_attrs = PyList_Size(items);
	const char *b = strrchr(tag, '}');
	const char *tag_name = tag;
	int nsindex = -1;
	if (b) {
		nsindex = namespace_index(self, tag + 1, b - tag - 1);
		tag_name = b + 1;
	}
	if (!write_str_literal(self, "{\"n\":")) goto end;
	if (!write_string_as_json(self, tag_name)) goto end;
	if (nsindex > -1) {
		char buf[32];
		write_data(self, buf, snprintf(buf, sizeof(buf), ",\"s\":%d", nsindex));
	}
	if (text) {
		if (!write_str_literal(self, ",\"x\":")) goto end;
		if (!write_string_as_json(self, text)) goto end;
	}
	if (tail) {
		if (!write_str_literal(self, ",\"l\":")) goto end;
		if (!write_string_as_json(self, tail)) goto end;
	}
	if (num_attrs > 0) {
		if (!write_str_literal(self, ",\"a\":[")) goto end;
		for (Py_ssize_t i = 0; i < num_attrs; i++) {
			if (i) { if (!write_str_literal(self, ",")) goto end; }
			if (!write_attr(self, PyList_GET_ITEM(items, i))) goto end;
		}
		if (!write_str_literal(self, "]")) goto end;
	}

end:
#if PY_MAJOR_VERSION < 3
	PyMem_Free(tag); PyMem_Free(text); PyMem_Free(tail);
#endif
	if (PyErr_Occurred()) return NULL;
	Py_RETURN_NONE;
}

static PyObject*
add_comment(Serializer *self, PyObject *args) {
	const char *text, *tail, *type;
#if PY_MAJOR_VERSION > 2
	if (!PyArg_ParseTuple(args, "zzs", &text, &tail, &type)) return NULL;
#else
	if (!PyArg_ParseTuple(args, "etets", "UTF-8", &text, "UTF-8", &tail, &type)) return NULL;
#endif
	if (!write_str_literal(self, "{\"s\":")) goto end;
	if (!write_string_as_json(self, type)) goto end;
	if (text) {
		if (!write_str_literal(self, ",\"x\":")) goto end;
		if (!write_string_as_json(self, text)) goto end;
	}
	if (tail) {
		if (!write_str_literal(self, ",\"l\":")) goto end;
		if (!write_string_as_json(self, tail)) goto end;
	}
	if (!write_str_literal(self, "}")) goto end;
end:
#if PY_MAJOR_VERSION < 3
	PyMem_Free(text); PyMem_Free(tail);
#endif
	if (PyErr_Occurred()) return NULL;
	Py_RETURN_NONE;
}

static PyObject*
add_nsmap(Serializer *self, PyObject *args) {
	(void)args;
	if (!write_str_literal(self, "[")) return NULL;
	bool is_first = true;
	for (auto x : *self->nsmap) {
		if (is_first) is_first = false;
		else if (!write_str_literal(self, ",")) return NULL;
		if (!write_string_as_json(self, x.c_str())) return NULL;
	}
	if (!write_str_literal(self, "]")) return NULL;
	Py_RETURN_NONE;
}

static PyObject*
done(Serializer *self, PyObject *arg) {
	(void)arg;
	if (!self->buf) return PyBytes_FromString("");
	if (_PyBytes_Resize(&self->buf, self->used) != 0) return NULL;
	PyObject *ans = self->buf;
	self->buf = NULL;
	self->used = 0;
	self->nsmap->clear();
	return ans;
}

// Boilerplate {{{
static PyMethodDef Serializer_methods[] = {
    {"start_tag", (PyCFunction)start_tag, METH_VARARGS,
     "Start serializing a tag"
    },
    {"add_comment", (PyCFunction)add_comment, METH_VARARGS,
     "Add a comment"
    },
    {"write", (PyCFunction)pywrite, METH_O,
     "Write the specified unicode or bytes object"
    },
    {"add_nsmap", (PyCFunction)add_nsmap, METH_NOARGS,
     "Add the namespace map"
    },
    {"done", (PyCFunction)done, METH_NOARGS,
     "Get the serialized output"
    },
    {NULL}  /* Sentinel */
};

PyTypeObject SerializerType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "html_as_json.Serializer",
    /* tp_basicsize      */ sizeof(Serializer),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)dealloc,
    /* tp_print          */ 0,
    /* tp_getattr        */ 0,
    /* tp_setattr        */ 0,
    /* tp_compare        */ 0,
    /* tp_repr           */ 0,
    /* tp_as_number      */ 0,
    /* tp_as_sequence    */ 0,
    /* tp_as_mapping     */ 0,
    /* tp_hash           */ 0,
    /* tp_call           */ 0,
    /* tp_str            */ 0,
    /* tp_getattro       */ 0,
    /* tp_setattro       */ 0,
    /* tp_as_buffer      */ 0,
    /* tp_flags          */ Py_TPFLAGS_DEFAULT,
    /* tp_doc            */ "Serializer",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ Serializer_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ 0,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ alloc,
};

static char doc[] = "Serialize HTML as JSON efficiently";
static PyMethodDef methods[] = {
    {NULL}  /* Sentinel */
};

#if PY_MAJOR_VERSION >= 3
#define INITERROR return NULL
#define INITMODULE PyModule_Create(&module)
static struct PyModuleDef module = {
    /* m_base     */ PyModuleDef_HEAD_INIT,
    /* m_name     */ "html_as_json",
    /* m_doc      */ doc,
    /* m_size     */ -1,
    /* m_methods  */ methods,
    /* m_slots    */ 0,
    /* m_traverse */ 0,
    /* m_clear    */ 0,
    /* m_free     */ 0,
};
CALIBRE_MODINIT_FUNC PyInit_html_as_json(void) {
#else
#define INITERROR return
#define INITMODULE Py_InitModule3("html_as_json", methods, doc)
CALIBRE_MODINIT_FUNC inithtml_as_json(void) {
#endif

    PyObject* m;

    if (PyType_Ready(&SerializerType) < 0) {
        INITERROR;
    }


    m = INITMODULE;
    if (m == NULL) {
        INITERROR;
    }

    PyModule_AddObject(m, "Serializer", (PyObject *)&SerializerType);


#if PY_MAJOR_VERSION >= 3
    return m;
#endif
}
// }}}
