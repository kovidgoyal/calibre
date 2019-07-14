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


static bool
used_fonts_in_page(PdfPage *page, PyObject *ans) {
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

extern "C" {
PyObject*
list_fonts(PDFDoc *self, PyObject *args) {
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
                    long long stream_len = 0;
                    pyunique_ptr descendant_font, stream_ref;
                    if (descriptor) {
                        const PdfObject *ff = descriptor->GetIndirectKey("FontFile");
                        if (!ff) ff = descriptor->GetIndirectKey("FontFile2");
                        if (!ff) ff = descriptor->GetIndirectKey("FontFile3");
                        if (ff) {
                            stream_ref.reset(ref_as_tuple(ff->Reference()));
                            if (!stream_ref) return NULL;
                            const PdfStream *stream = ff->GetStream();
                            if (stream) stream_len = stream->GetLength();
                        }
                    } else if (dict.HasKey("DescendantFonts")) {
                        const PdfArray &df = dict.GetKey("DescendantFonts")->GetArray();
                        descendant_font.reset(ref_as_tuple(df[0].GetReference()));
                        if (!descendant_font) return NULL;
                    }
#define V(x) (x ? x.get() : Py_None)
                    pyunique_ptr d(Py_BuildValue(
                            "{ss ss s(kk) sL sO sO}",
                            "BaseFont", name.c_str(),
                            "Subtype", subtype.c_str(),
                            "Reference", num, generation,
                            "Length", stream_len,
                            "DescendantFont", V(descendant_font),
                            "StreamRef", V(stream_ref)
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
            if (!used_fonts_in_page(page, ans.get())) return NULL;
        } catch (const PdfError &err) { continue; }
    }
    return ans.release();
}

}
