/*
 * html_as_json.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>
#include <stack>
#include <string>
#include <memory>

struct PyObjectDeleter {
    void operator()(PyObject *obj) {
        Py_XDECREF(obj);
    }
};
// unique_ptr that uses Py_XDECREF as the destructor function.
typedef std::unique_ptr<PyObject, PyObjectDeleter> pyunique_ptr;


#define write_str_literal(x) this->write_data(x, sizeof(x)-1)

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


static inline bool
namespaces_are_equal(const char *a, const char *b, size_t len) {
	for (size_t i = 0; i < len; i++) {
		if (a[i] != b[i]) return false;
		if (!b[i]) return true;
	}
	return true;
}

class StringOrNone {
	PyObject *orig;
	const char *data;
public:
	StringOrNone(PyObject *x) : orig(x), data(0) {
		if (x && x != Py_None) {
			if (PyUnicode_Check(x)) {
				this->data = PyUnicode_AsUTF8(x);
			} else if (PyBytes_Check(x)) { this->data = PyBytes_AS_STRING(x); }
		}
	}
	~StringOrNone() {
		Py_CLEAR(this->orig);
	}
	void incref() { Py_XINCREF(this->orig); }
	PyObject* get() { return this->orig; }
	const char *c_str() { return this->data; }
	explicit operator bool() { return this->orig ? true : false; }
};

class Serializer {
	PyObject *buf = NULL;
	size_t used = 0;
	std::vector<std::string> nsmap;

	bool
	ensure_space(size_t amt) {
		size_t required = amt + this->used;
		if (!this->buf) {
			this->buf = PyBytes_FromStringAndSize(NULL, std::max(required, static_cast<size_t>(128u * 1024u)));
			if (!this->buf) return false;
			return true;
		}

		if (required > static_cast<size_t>(PyBytes_GET_SIZE(this->buf))) {
			if (_PyBytes_Resize(&(this->buf), std::max(
					required, static_cast<size_t>(2 * PyBytes_GET_SIZE(this->buf)))) != 0) return false;
		}
		return true;
	}

	bool
	write_data(const char *data, size_t sz) {
		if (!this->ensure_space(sz)) return false;
		memcpy(PyBytes_AS_STRING(this->buf) + this->used, data, sz);
		this->used += sz;
		return true;
	}

	bool
	write_string_as_json(const char *str) {
		const char *s = str;
		if (!this->ensure_space(32)) return false;
		char *b = PyBytes_AS_STRING(this->buf) + this->used;

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
			this->used = b - PyBytes_AS_STRING(this->buf);
			if (!this->ensure_space(32)) return false;
			b = PyBytes_AS_STRING(this->buf) + this->used;
		}
		*b++ = '"';
		this->used = b - PyBytes_AS_STRING(this->buf);
		return true;
	}

	inline int
	namespace_index(const char *ns, size_t nslen) {
		for (size_t i = 0; i < this->nsmap.size(); i++) {
			if (namespaces_are_equal(this->nsmap[i].c_str(), ns, nslen)) return (int)i;
		}
		this->nsmap.push_back(std::string(ns, nslen));
		return ((int)(this->nsmap.size())) - 1;
	}

	bool
	add_comment(const char *text, const char *tail, const char *type) {
		if (!write_str_literal("{\"s\":")) return false;
		if (!this->write_string_as_json(type)) return false;
		if (text) {
			if (!write_str_literal(",\"x\":")) return false;
			if (!this->write_string_as_json(text)) return false;
		}
		if (tail) {
			if (!write_str_literal(",\"l\":")) return false;
			if (!this->write_string_as_json(tail)) return false;
		}
		if (!write_str_literal("}")) return false;
		return true;
	}

	bool
	write_attr(PyObject *args) {
		StringOrNone a(PyTuple_GET_ITEM(args, 0)), v(PyTuple_GET_ITEM(args, 1));
		a.incref(); v.incref();
		if (!a || !v) return false;
		const char *attr = a.c_str(), *val = v.c_str();
		const char *b = strrchr(attr, '}');
		const char *attr_name = attr;
		int nsindex = -1;
		if (b) {
			nsindex = this->namespace_index(attr + 1, b - attr - 1);
			attr_name = b + 1;
		}
		if (!write_str_literal("[")) return false;
		if (!this->write_string_as_json(attr_name)) return false;
		if (!write_str_literal(",")) return false;
		if (!this->write_string_as_json(val)) return false;
		if (nsindex > -1) {
			char buf[32];
			this->write_data(buf, snprintf(buf, sizeof(buf), ",%d", nsindex));
		}
		if (!write_str_literal("]")) return false;

		return true;
	}


	bool
	start_tag(const char *tag, const char *text, const char *tail, PyObject *items) {
		if (!PyList_Check(items)) { PyErr_SetString(PyExc_TypeError, "attrs of a tag must be a list"); return false; }
		Py_ssize_t num_attrs = PyList_Size(items);
		const char *b = strrchr(tag, '}');
		const char *tag_name = tag;
		int nsindex = -1;
		if (b) {
			nsindex = this->namespace_index(tag + 1, b - tag - 1);
			tag_name = b + 1;
		}
		if (!write_str_literal("{\"n\":")) return false;
		if (!this->write_string_as_json(tag_name)) return false;
		if (nsindex > 0) {
			char buf[32];
			this->write_data(buf, snprintf(buf, sizeof(buf), ",\"s\":%d", nsindex));
		}
		if (text) {
			if (!write_str_literal(",\"x\":")) return false;
			if (!this->write_string_as_json(text)) return false;
		}
		if (tail) {
			if (!write_str_literal(",\"l\":")) return false;
			if (!this->write_string_as_json(tail)) return false;
		}
		if (num_attrs > 0) {
			if (!write_str_literal(",\"a\":[")) return false;
			for (Py_ssize_t i = 0; i < num_attrs; i++) {
				if (i) { if (!write_str_literal(",")) return false; }
				if (!this->write_attr(PyList_GET_ITEM(items, i))) return false;
			}
			if (!write_str_literal("]")) return false;
		}

		return true;
	}

	bool
	add_nsmap() {
		if (!write_str_literal("[")) return false;
		bool is_first = true;
		for (auto x : this->nsmap) {
			if (is_first) is_first = false;
			else if (!write_str_literal(",")) return false;
			if (!this->write_string_as_json(x.c_str())) return false;
		}
		if (!write_str_literal("]")) return false;
		return true;
	}

public:
	Serializer() = default;
	~Serializer() {
		Py_CLEAR(this->buf);
	}

	PyObject*
	serialize(PyObject *args) {
		PyObject *root, *Comment;
		if (!PyArg_ParseTuple(args, "OO", &root, &Comment)) return NULL;
		std::stack<pyunique_ptr> stack;
		std::vector<pyunique_ptr> children;
		Py_INCREF(root);
		stack.push(pyunique_ptr(root));
		write_str_literal("{\"version\":1,\"tree\":");

		while(!stack.empty()) {
			pyunique_ptr e(std::move(stack.top()));
			stack.pop();
			PyObject *elem = e.get();
			if (PyBytes_CheckExact(elem)) {
				if (!this->write_data(PyBytes_AS_STRING(elem), PyBytes_GET_SIZE(elem))) return NULL;
				continue;
			}
			StringOrNone tag(PyObject_GetAttrString(elem, "tag"));
			StringOrNone text(PyObject_GetAttrString(elem, "text")), tail(PyObject_GetAttrString(elem, "tail"));
			if (!tag || PyCallable_Check(tag.get())) {
				const char *type = (tag && tag.get() == Comment) ? "c" : "o";
				if (!this->add_comment(text.c_str(), tail.c_str(), type)) return NULL;
			} else {
				pyunique_ptr attrs(PyObject_CallMethod(elem, (char*)"items", NULL));
				if (!attrs) return NULL;
				if (!this->start_tag(tag.c_str(), text.c_str(), tail.c_str(), attrs.get())) return NULL;
				pyunique_ptr iterator(PyObject_GetIter(elem));
				if (!iterator) return NULL;
				children.clear();
				while(true) {
					PyObject *child = PyIter_Next(iterator.get());
					if (!child) { if (PyErr_Occurred()) return NULL; break; }
					children.push_back(pyunique_ptr(child));
				}
				if (children.size() > 0) {
#define push_literal(x) { \
	PyObject *lt = PyBytes_FromStringAndSize(x, sizeof(x) - 1); \
	if (!lt) return NULL; \
	stack.push(pyunique_ptr(lt));}
					if (!write_str_literal(",\"c\":[")) return NULL;
					push_literal("]}");
					for (size_t i = children.size(); i-- > 0;) {
						stack.push(std::move(children[i]));
						if (i != 0) push_literal(",");
					}
#undef push_literal
				} else if (!write_str_literal("}")) return NULL;
			}
		}
		if (!write_str_literal(",\"ns_map\":")) return NULL;
		if (!this->add_nsmap()) return NULL;
		if (!write_str_literal("}")) return NULL;

		if (_PyBytes_Resize(&this->buf, this->used) != 0) return NULL;
		PyObject *ans = this->buf;
		this->buf = NULL;
		this->used = 0;
		this->nsmap.clear();
		return ans;
	}
};


static PyObject*
serialize(PyObject *self, PyObject *args) {
	(void)self;
	try {
		Serializer s;
		return s.serialize(args);
    } catch(const std::exception & err) {
        PyErr_Format(PyExc_ValueError, "An error occurred while trying to serialize to JSON: %s", err.what());
        return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to serialize to JSON");
        return NULL;
    }
}

// Boilerplate {{{
static char doc[] = "Serialize HTML as JSON efficiently";
static PyMethodDef methods[] = {
    {"serialize", (PyCFunction)serialize, METH_VARARGS,
     "Serialize the provided lxml tree to JSON"
    },
    {NULL}  /* Sentinel */
};
static int
exec_module(PyObject *mod) { return 0; }

static PyModuleDef_Slot slots[] = { {Py_mod_exec, (void*)exec_module}, {0, NULL} };

static struct PyModuleDef module_def = {PyModuleDef_HEAD_INIT};

CALIBRE_MODINIT_FUNC PyInit_html_as_json(void) {
	module_def.m_name = "html_as_json";
	module_def.m_slots = slots;
	module_def.m_doc = doc;
	module_def.m_methods = methods;
	return PyModuleDef_Init(&module_def);
}
