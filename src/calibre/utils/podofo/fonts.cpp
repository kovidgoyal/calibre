/*
 * fonts.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <iostream>
#include <memory>
#include <stack>

using namespace pdf;

static inline PyObject*
ref_as_tuple(const PdfReference &ref) {
    unsigned long num = ref.ObjectNumber(), generation = ref.GenerationNumber();
    return Py_BuildValue("kk", num, generation);
}

static inline PdfObject*
get_font_file(PdfObject *descriptor) {
    PdfDictionary *dict;
    PdfObject *ff = NULL;
    if (descriptor->TryGetDictionary(dict)) {
        ff = dict->FindKey("FontFile");
        if (!ff) ff = dict->FindKey("FontFile2");
        if (!ff) ff = dict->FindKey("FontFile3");
    }
    return ff;
}

static inline const PdfObject*
get_font_file(const PdfObject *descriptor) {
    const PdfDictionary *dict;
    const PdfObject *ff = NULL;
    if (descriptor->TryGetDictionary(dict)) {
        ff = dict->FindKey("FontFile");
        if (!ff) ff = dict->FindKey("FontFile2");
        if (!ff) ff = dict->FindKey("FontFile3");
    }
    return ff;
}


static inline void
remove_font(PdfIndirectObjectList &objects, PdfObject *font) {
    PdfDictionary *dict;
    if (font->TryGetDictionary(dict)) {
        PdfObject *descriptor = dict->FindKey("FontDescriptor");
        if (descriptor) {
            const PdfObject *ff = get_font_file(descriptor);
            if (ff) objects.RemoveObject(object_as_reference(ff)).reset();
            objects.RemoveObject(object_as_reference(descriptor)).reset();
        }
    }
    objects.RemoveObject(object_as_reference(font)).reset();
}

static void
used_fonts_in_canvas(const PdfCanvas &canvas, unordered_reference_set &ans) {
    PdfPostScriptTokenizer tokenizer;
    PdfCanvasInputDevice input(canvas);
    bool in_text_block = false;
    PdfPostScriptTokenType contents_type;
    PdfVariant var;
    std::stack<PdfVariant> stack;
    const PdfDictionary &resources = canvas.GetResources()->GetDictionary();
    if (!resources.HasKey("Font")) return;
    const PdfDictionary &fonts_dict = resources.GetKey("Font")->GetDictionary();
    std::string_view keyword;

    while (tokenizer.TryReadNext(input, contents_type, keyword, var)) {
        if (contents_type == PdfPostScriptTokenType::Variant) stack.push(var);
        if (contents_type != PdfPostScriptTokenType::Keyword) continue;
        const char *token = keyword.data();
        if (strcmp(token, "BT") == 0) {
            in_text_block = true;
            continue;
        } else if (strcmp(token, "ET") == 0) {
            in_text_block = false;
            continue;
        }
        if (!in_text_block) continue;
        if (strcmp(token, "Tf") == 0) {
            stack.pop();
            if (stack.size() > 0 && stack.top().IsName()) {
                const PdfName &reference_name = stack.top().GetName();
                const PdfObject *f = fonts_dict.GetKey(reference_name);
                if (f) ans.insert(object_as_reference(f));
            }
        }
    }
    return;
}

static PyObject*
convert_w_array(const PdfArray &w) {
    pyunique_ptr ans(PyList_New(0));
    if (!ans) return NULL;
    for (PdfArray::const_iterator it = w.begin(); it != w.end(); it++) {
        pyunique_ptr item;
        if ((*it).IsArray()) {
            item.reset(convert_w_array((*it).GetArray()));
        } else if ((*it).IsRealStrict()) {
            item.reset(PyFloat_FromDouble((*it).GetReal()));
        } else if ((*it).IsNumber()) {
            item.reset(PyLong_FromLongLong((long long)(*it).GetNumber()));
        } else PyErr_SetString(PyExc_ValueError, "Unknown datatype in w array");
        if (!item) return NULL;
        if (PyList_Append(ans.get(), item.get()) != 0) return NULL;
    }
    return ans.release();
}

static PyObject*
list_fonts(PDFDoc *self, PyObject *args) {
    int get_font_data = 0;
    if (!PyArg_ParseTuple(args, "|i", &get_font_data)) return NULL;
    pyunique_ptr ans(PyList_New(0));
    if (!ans) return NULL;
    const PdfIndirectObjectList &objects = self->doc->GetObjects();
    for (auto &it : objects) {
        if (it->IsDictionary()) {
            const PdfDictionary &dict = it->GetDictionary();
            if (dictionary_has_key_name(dict, PdfName::KeyType, "Font") && dict.HasKey("BaseFont")) {
                const std::string &name = dict.GetKey("BaseFont")->GetName().GetString();
                const std::string &subtype = dict.GetKey(PdfName::KeySubtype)->GetName().GetString();
                const PdfReference &ref = object_as_reference(it);
                unsigned long num = ref.ObjectNumber(), generation = ref.GenerationNumber();
                const PdfObject *descriptor = dict.FindKey("FontDescriptor");
                pyunique_ptr descendant_font, stream_ref, encoding, w, w2;
                PyBytesOutputStream stream_data, to_unicode, cid_gid_map;
                if (dict.HasKey("W")) {
                    w.reset(convert_w_array(dict.GetKey("W")->GetArray()));
                    if (!w) return NULL;
                }
                if (dict.HasKey("W2")) {
                    w2.reset(convert_w_array(dict.GetKey("W2")->GetArray()));
                    if (!w2) return NULL;
                }
                if (dict.HasKey("Encoding") && dict.GetKey("Encoding")->IsName()) {
                    encoding.reset(PyUnicode_FromString(dict.GetKey("Encoding")->GetName().GetString().c_str()));
                    if (!encoding) return NULL;
                }
				if (dict.HasKey("CIDToGIDMap") && (!dict.GetKey("CIDToGIDMap")->IsName() || strcmp(dict.GetKey("CIDToGIDMap")->GetName().GetString().c_str(), "Identity") != 0)) {
					const PdfObjectStream *stream = dict.GetKey("CIDToGIDMap")->GetStream();
					if (stream) stream->CopyToSafe(cid_gid_map);
				}
                if (descriptor) {
                    const PdfObject *ff = get_font_file(descriptor);
                    if (ff) {
                        stream_ref.reset(ref_as_tuple(object_as_reference(ff)));
                        if (!stream_ref) return NULL;
                        const PdfObjectStream *stream = ff->GetStream();
                        if (stream && get_font_data) {
                            stream->CopyToSafe(stream_data);
                        }
                    }
                } else if (dict.HasKey("DescendantFonts")) {
                    const PdfArray &df = dict.GetKey("DescendantFonts")->GetArray();
                    descendant_font.reset(ref_as_tuple(object_as_reference(df[0])));
                    if (!descendant_font) return NULL;
                    if (get_font_data && dict.HasKey("ToUnicode")) {
                        const PdfReference &uref = object_as_reference(dict.GetKey("ToUnicode"));
                        PdfObject *t = objects.GetObject(uref);
                        if (t) {
                            PdfObjectStream *stream = t->GetStream();
                            if (stream) stream->CopyToSafe(to_unicode);
                        }
                    }
                }
#define V(x) (x ? x.get() : Py_None)
                pyunique_ptr d(Py_BuildValue(
                        "{ss ss s(kk) sO sO sO sO sO sO sO sO}",
                        "BaseFont", name.c_str(),
                        "Subtype", subtype.c_str(),
                        "Reference", num, generation,
                        "Data", V(stream_data),
                        "DescendantFont", V(descendant_font),
                        "StreamRef", V(stream_ref),
                        "Encoding", V(encoding),
                        "ToUnicode", V(to_unicode),
                        "W", V(w), "W2", V(w2),
						"CIDToGIDMap", V(cid_gid_map)
                ));
#undef V
                if (!d) { return NULL; }
                if (PyList_Append(ans.get(), d.get()) != 0) return NULL;
            }
        }
    }
    return ans.release();
}

typedef std::unordered_map<PdfReference, unsigned long, PdfReferenceHasher> charprocs_usage_map;

static PyObject*
remove_unused_fonts(PDFDoc *self, PyObject *args) {
    unsigned long count = 0;
    unordered_reference_set used_fonts;
    // Look in Pages
    PdfPageCollection *pages = &self->doc->GetPages();
    for (unsigned i = 0; i < pages->GetCount(); i++) {
        used_fonts_in_canvas(self->doc->GetPages().GetPageAt(i), used_fonts);
    }
    // Look in XObjects
    PdfIndirectObjectList &objects = self->doc->GetObjects();
    for (PdfObject *k : objects) {
        if (k->IsDictionary()) {
            const PdfDictionary &dict = k->GetDictionary();
            if (dictionary_has_key_name(dict, PdfName::KeyType, "XObject") && dictionary_has_key_name(dict, PdfName::KeySubtype, "Form")) {
                std::unique_ptr<PdfXObjectForm> xo;
                if (PdfXObject::TryCreateFromObject<PdfXObjectForm>(*k, xo)) used_fonts_in_canvas(*xo, used_fonts);
            }
        }
    }
    unordered_reference_set all_fonts;
    unordered_reference_set type3_fonts;
    charprocs_usage_map charprocs_usage;
    for (auto &k : objects) {
        if (k->IsDictionary()) {
            const PdfDictionary &dict = k->GetDictionary();
            if (dictionary_has_key_name(dict, PdfName::KeyType, "Font")) {
                const std::string &font_type = dict.GetKey(PdfName::KeySubtype)->GetName().GetString();
                if (font_type == "Type0") {
                    all_fonts.insert(object_as_reference(k));
                } else if (font_type == "Type3") {
                    all_fonts.insert(object_as_reference(k));
                    type3_fonts.insert(object_as_reference(k));
                    for (auto &x : dict.GetKey("CharProcs")->GetDictionary()) {
                        const PdfReference &ref = object_as_reference(x.second);
                        if (charprocs_usage.find(ref) == charprocs_usage.end()) charprocs_usage[ref] = 1;
                        else charprocs_usage[ref] += 1;
                    }
                }
            }
        }
    }

    for (auto &ref : all_fonts) {
        if (used_fonts.find(ref) == used_fonts.end()) {
            PdfObject *font = objects.GetObject(ref);
            if (font) {
                count++;
                PdfDictionary *dict;
                if (font->TryGetDictionary(dict)) {
                if (type3_fonts.find(ref) != type3_fonts.end()) {
                    for (auto &x : dict->FindKey("CharProcs")->GetDictionary()) {
                        charprocs_usage[object_as_reference(x.second)] -= 1;
                    }
                } else {
                    for (auto &x : dict->FindKey("DescendantFonts")->GetArray()) {
                        PdfObject *dfont = objects.GetObject(object_as_reference(x));
                        if (dfont) remove_font(objects, dfont);
                    }
                }}
                remove_font(objects, font);
            }
        }
    }

    for (auto &x : charprocs_usage) {
        if (x.second == 0u) {
            objects.RemoveObject(x.first).reset();
        }
    }

    return Py_BuildValue("k", count);
}

PyObject*
replace_font_data(PDFDoc *self, PyObject *args) {
    const char *data; Py_ssize_t sz;
    unsigned long num, gen;
    if (!PyArg_ParseTuple(args, "y#kk", &data, &sz, &num, &gen)) return NULL;
    const PdfIndirectObjectList &objects = self->doc->GetObjects();
    PdfObject *font = objects.GetObject(PdfReference(num, static_cast<uint16_t>(gen)));
    if (!font) { PyErr_SetString(PyExc_KeyError, "No font with the specified reference found"); return NULL; }
    PdfDictionary *dict;
    if (!font->TryGetDictionary(dict)) { PyErr_SetString(PyExc_ValueError, "Font does not have a descriptor"); return NULL; }
    PdfObject *descriptor = dict->FindKey("FontDescriptor");
    if (!descriptor) { PyErr_SetString(PyExc_ValueError, "Font does not have a descriptor"); return NULL; }
    PdfObject *ff = get_font_file(descriptor);
    PdfObjectStream *stream = ff->GetStream();
    stream->SetData(bufferview(data, sz));
    Py_RETURN_NONE;
}

PyObject*
merge_fonts(PDFDoc *self, PyObject *args) {
    const char *data; Py_ssize_t sz;
	PyObject *references;
    if (!PyArg_ParseTuple(args, "y#O!", &data, &sz, &PyTuple_Type, &references)) return NULL;
    PdfIndirectObjectList &objects = self->doc->GetObjects();
	PdfObject *font_file = NULL;
    PdfDictionary *dict;
	for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(references); i++) {
		unsigned long num, gen;
		if (!PyArg_ParseTuple(PyTuple_GET_ITEM(references, i), "kk", &num, &gen)) return NULL;
		PdfObject *font = objects.GetObject(PdfReference(num, static_cast<uint16_t>(gen)));
		if (!font) { PyErr_SetString(PyExc_KeyError, "No font with the specified reference found"); return NULL; }

		PdfObject *dobj = NULL;
        if (font->TryGetDictionary(dict)) { dobj = dict->FindKey("FontDescriptor"); }
		if (!dobj) { PyErr_SetString(PyExc_ValueError, "Font does not have a descriptor"); return NULL; }
		if (!dobj->IsDictionary()) { PyErr_SetString(PyExc_ValueError, "Font does not have a dictionary descriptor"); return NULL; }
        PdfDictionary &descriptor = dobj->GetDictionary();
		const char *font_file_key = NULL;
		PdfObject *ff = NULL;
        if ((ff = descriptor.FindKey("FontFile"))) { font_file_key = "FontFile"; }
        else if ((ff = descriptor.FindKey("FontFile2"))) { font_file_key = "FontFile2"; }
        else if ((ff = descriptor.FindKey("FontFile3"))) { font_file_key = "FontFile3"; }
        else { PyErr_SetString(PyExc_ValueError, "Font descriptor does not have file data"); return NULL; }
		if (i == 0) {
			font_file = ff;
			PdfObjectStream *stream = ff->GetStream();
			stream->SetData(bufferview(data, sz));
		} else {
			objects.RemoveObject(object_as_reference(ff)).reset();
			descriptor.AddKey(font_file_key, object_as_reference(font_file));
		}
	}
	Py_RETURN_NONE;
}

class CharProc {
    charbuff buf;
    PdfReference ref;
    CharProc( const CharProc & ) ;
    CharProc & operator=( const CharProc & ) ;

    public:
        CharProc(const PdfReference &reference, const PdfObject *o) : buf(), ref(reference) {
            const PdfObjectStream *stream = o->GetStream();
            buf = stream->GetCopySafe();
        }
        CharProc(CharProc &&other) noexcept :
            buf(std::move(other.buf)), ref(other.ref) {
            other.buf = charbuff();
        }
        CharProc& operator=(CharProc &&other) noexcept {
            buf = std::move(other.buf); other.buf = charbuff(); ref = other.ref;
            return *this;
        }
        bool operator==(const CharProc &other) const noexcept {
            return buf.size() == other.buf.size() && memcmp(buf.data(), other.buf.data(), buf.size()) == 0;
        }
        std::size_t hash() const noexcept { return buf.size(); }
        const PdfReference& reference() const noexcept { return ref; }
};

struct CharProcHasher {
    std::size_t operator()(const CharProc& k) const { return k.hash(); }
};

typedef std::unordered_map<CharProc, std::vector<PdfReference>, CharProcHasher> char_proc_reference_map;

static PyObject*
dedup_type3_fonts(PDFDoc *self, PyObject *args) {
    unsigned long count = 0;
    unordered_reference_set all_char_procs;
    unordered_reference_set all_type3_fonts;
    char_proc_reference_map cp_map;

    PdfIndirectObjectList &objects = self->doc->GetObjects();
    for (auto &k : objects) {
        if (!k->IsDictionary()) continue;
        const PdfDictionary &dict = k->GetDictionary();
        if (dictionary_has_key_name(dict, PdfName::KeyType, "Font")) {
            const std::string &font_type = dict.GetKey(PdfName::KeySubtype)->GetName().GetString();
            if (font_type == "Type3") {
                all_type3_fonts.insert(object_as_reference(k));
                for (auto &x : dict.GetKey("CharProcs")->GetDictionary()) {
                    const PdfReference &ref = object_as_reference(x.second);
                    const PdfObject *cpobj = objects.GetObject(ref);
                    if (!cpobj || !cpobj->HasStream()) continue;
                    CharProc cp(ref, cpobj);
                    auto it = cp_map.find(cp);
                    if (it == cp_map.end()) {
                        std::vector<PdfReference> vals;
                        cp_map.insert(std::make_pair(std::move(cp), std::move(vals)));
                    } else (*it).second.push_back(ref);
                }
            }
        }
    }
    std::unordered_map<PdfReference, PdfReference, PdfReferenceHasher> ref_map;
    for (auto &x : cp_map) {
        if (x.second.size() > 0) {
            const PdfReference &canonical_ref = x.first.reference();
            for (auto &ref : x.second) {
                if (ref != canonical_ref) {
                    ref_map[ref] = x.first.reference();
                    objects.RemoveObject(ref).reset();
                    count++;
                }
            }
        }
    }
    if (count > 0) {
        for (auto &ref : all_type3_fonts) {
            PdfObject *font = objects.GetObject(ref);
            PdfDictionary *d;
            if (!font->TryGetDictionary(d)) continue;
            PdfDictionary dict = d->FindKey("CharProcs")->GetDictionary();
            PdfDictionary new_dict = PdfDictionary(dict);
            bool changed = false;
            for (auto &k : dict) {
                auto it = ref_map.find(object_as_reference(k.second));
                if (it != ref_map.end()) {
                    new_dict.AddKey(k.first, (*it).second);
                    changed = true;
                }
            }
            if (changed) font->GetDictionary().AddKey("CharProcs", new_dict);
        }
    }
    return Py_BuildValue("k", count);
}

PYWRAP(list_fonts)
PYWRAP(merge_fonts)
PYWRAP(remove_unused_fonts)
PYWRAP(dedup_type3_fonts)
PYWRAP(replace_font_data)
