/*
 * fonts.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <iostream>

using namespace pdf;
using namespace std;

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
                    const string &name = dict.GetKey("BaseFont")->GetName().GetName();
                    const string &subtype = dict.GetKey(PdfName::KeySubtype)->GetName().GetName();
                    const PdfReference &ref = (*it)->Reference();
                    unsigned long num = ref.ObjectNumber(), generation = ref.GenerationNumber();
                    const PdfObject *descriptor = (*it)->GetIndirectKey("FontDescriptor");
                    long long stream_len = 0;
                    if (descriptor) {
                        const PdfObject *ff = descriptor->GetIndirectKey("FontFile");
                        if (!ff) ff = descriptor->GetIndirectKey("FontFile2");
                        if (!ff) ff = descriptor->GetIndirectKey("FontFile3");
                        const PdfStream *stream = ff->GetStream();
                        if (stream) stream_len = stream->GetLength();
                    }
                    pyunique_ptr d(Py_BuildValue(
                            "{sssss(kk)sL}",
                            "BaseFont", name.c_str(),
                            "Subtype", subtype.c_str(),
                            "Reference", num, generation,
                            "Length", stream_len));
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
}
