/*
 * fonts.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <iostream>
#include <stack>

using namespace pdf;

static inline PyObject*
ref_as_tuple(const PdfReference &ref) {
    unsigned long num = ref.ObjectNumber(), generation = ref.GenerationNumber();
    return Py_BuildValue("kk", num, generation);
}

static inline const PdfObject*
get_font_file(const PdfObject *descriptor) {
    PdfObject *ff = descriptor->GetIndirectKey("FontFile");
    if (!ff) ff = descriptor->GetIndirectKey("FontFile2");
    if (!ff) ff = descriptor->GetIndirectKey("FontFile3");
    return ff;
}

static void
remove_font(PdfVecObjects &objects, PdfObject *font) {
    PdfObject *descriptor = font->GetIndirectKey("FontDescriptor");
    if (descriptor) {
        const PdfObject *ff = get_font_file(descriptor);
        if (ff) delete objects.RemoveObject(ff->Reference());
        delete objects.RemoveObject(descriptor->Reference());
    }
    delete objects.RemoveObject(font->Reference());
}

static bool
used_fonts_in_page(PdfPage *page, int page_num, PyObject *ans) {
    PdfContentsTokenizer tokenizer(page);
    bool in_text_block = false;
    const char* token = NULL;
    EPdfContentsType contents_type;
    PdfVariant var;
    std::stack<PdfVariant> stack;

    while (tokenizer.ReadNext(contents_type, token, var)) {
        if (contents_type == ePdfContentsType_Variant) stack.push(var);
        if (contents_type != ePdfContentsType_Keyword) continue;
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
                PdfObject* font = page->GetFromResources("Font", reference_name);
                if (font) {
                    pyunique_ptr r(ref_as_tuple(font->Reference()));
                    if (!r) return false;
                    if (PySet_Add(ans, r.get()) != 0) return false;
                }
            }
        }
    }
    return true;
}

static PyObject*
convert_w_array(const PdfArray &w) {
    pyunique_ptr ans(PyList_New(0));
    if (!ans) return NULL;
    for (PdfArray::const_iterator it = w.begin(); it != w.end(); it++) {
        pyunique_ptr item;
        if ((*it).IsArray()) {
            item.reset(convert_w_array((*it).GetArray()));
        } else if ((*it).IsNumber()) {
            item.reset(PyLong_FromLongLong((long long)(*it).GetNumber()));
        } else if ((*it).IsReal()) {
            item.reset(PyFloat_FromDouble((*it).GetReal()));
        } else PyErr_SetString(PyExc_ValueError, "Unknown datatype in w array");
        if (!item) return NULL;
        if (PyList_Append(ans.get(), item.get()) != 0) return NULL;
    }
    return ans.release();
}

extern "C" {
PyObject*
list_fonts(PDFDoc *self, PyObject *args) {
    int get_font_data = 0;
    if (!PyArg_ParseTuple(args, "|i", &get_font_data)) return NULL;
    pyunique_ptr ans(PyList_New(0));
    if (!ans) return NULL;
    try {
        const PdfVecObjects &objects = self->doc->GetObjects();
        for (TCIVecObjects it = objects.begin(); it != objects.end(); it++) {
            if ((*it)->IsDictionary()) {
                const PdfDictionary &dict = (*it)->GetDictionary();
                if (dictionary_has_key_name(dict, PdfName::KeyType, "Font") && dict.HasKey("BaseFont")) {
                    const std::string &name = dict.GetKey("BaseFont")->GetName().GetName();
                    const std::string &subtype = dict.GetKey(PdfName::KeySubtype)->GetName().GetName();
                    const PdfReference &ref = (*it)->Reference();
                    unsigned long num = ref.ObjectNumber(), generation = ref.GenerationNumber();
                    const PdfObject *descriptor = (*it)->GetIndirectKey("FontDescriptor");
                    pyunique_ptr descendant_font, stream_ref, encoding, w, w2;
                    PyBytesOutputStream stream_data;
                    if (dict.HasKey("W")) {
                        w.reset(convert_w_array(dict.GetKey("W")->GetArray()));
                        if (!w) return NULL;
                    }
                    if (dict.HasKey("W2")) {
                        w2.reset(convert_w_array(dict.GetKey("W2")->GetArray()));
                        if (!w2) return NULL;
                    }
                    if (dict.HasKey("Encoding") && dict.GetKey("Encoding")->IsName()) {
                        encoding.reset(PyUnicode_FromString(dict.GetKey("Encoding")->GetName().GetName().c_str()));
                        if (!encoding) return NULL;
                    }
                    if (descriptor) {
                        const PdfObject *ff = get_font_file(descriptor);
                        if (ff) {
                            stream_ref.reset(ref_as_tuple(ff->Reference()));
                            if (!stream_ref) return NULL;
                            const PdfStream *stream = ff->GetStream();
                            if (stream && get_font_data) {
                                stream->GetFilteredCopy(&stream_data);
                            }
                        }
                    } else if (dict.HasKey("DescendantFonts")) {
                        const PdfArray &df = dict.GetKey("DescendantFonts")->GetArray();
                        descendant_font.reset(ref_as_tuple(df[0].GetReference()));
                        if (!descendant_font) return NULL;
                    }
#define V(x) (x ? x.get() : Py_None)
                    pyunique_ptr d(Py_BuildValue(
                            "{ss ss s(kk) sO sO sO sO sO sO}",
                            "BaseFont", name.c_str(),
                            "Subtype", subtype.c_str(),
                            "Reference", num, generation,
                            "Data", V(stream_data),
                            "DescendantFont", V(descendant_font),
                            "StreamRef", V(stream_ref),
                            "Encoding", V(encoding),
                            "W", V(w), "W2", V(w2)
                    ));
#undef V
                    if (!d) { return NULL; }
                    if (PyList_Append(ans.get(), d.get()) != 0) return NULL;
                }
            }
        }
    } catch (const PdfError &err) {
        podofo_set_exception(err);
        return NULL;
    }
    return ans.release();
}

PyObject*
used_fonts_in_page_range(PDFDoc *self, PyObject *args) {
    int first = 1, last = self->doc->GetPageCount();
    if (!PyArg_ParseTuple(args, "|ii", &first, &last)) return NULL;
    pyunique_ptr ans(PySet_New(NULL));
    if (!ans) return NULL;
    for (int i = first - 1; i < last; i++) {
        try {
            PdfPage *page = self->doc->GetPage(i);
            if (!used_fonts_in_page(page, i, ans.get())) return NULL;
        } catch (const PdfError &err) { continue; }
    }
    return ans.release();
}

PyObject*
remove_fonts(PDFDoc *self, PyObject *args) {
    PyObject *fonts;
    if (!PyArg_ParseTuple(args, "O!", &PyTuple_Type, &fonts)) return NULL;
    PdfVecObjects &objects = self->doc->GetObjects();
    for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(fonts); i++) {
        unsigned long num, gen;
        if (!PyArg_ParseTuple(PyTuple_GET_ITEM(fonts, i), "kk", &num, &gen)) return NULL;
        PdfReference ref(num, gen);
        PdfObject *font = objects.GetObject(ref);
        if (font) {
            remove_font(objects, font);
        }
    }
    Py_RETURN_NONE;
}

}
