/*
 * impose.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <string>

using namespace pdf;

static void
impose_page(PdfMemDocument *doc, unsigned int dest_page_num, unsigned int src_page_num) {
    auto xobj = doc->CreateXObjectForm(Rect(), "HeaderFooter");
    xobj->FillFromPage(doc->GetPages().GetPageAt(src_page_num));
    auto dest = &doc->GetPages().GetPageAt(dest_page_num);
    static unsigned counter = 0;
    dest->GetOrCreateResources().AddResource("XObject", "Imp"s + std::to_string(++counter), xobj->GetObject());
    auto data = "q\n1 0 0 1 0 0 cm\n/"s + xobj->GetIdentifier().GetEscapedName() + " Do\nQ\n"s;
    dest->GetOrCreateContents().GetStreamForAppending().SetData(data);
}

static PyObject*
impose(PDFDoc *self, PyObject *args) {
    unsigned long dest_page_num, src_page_num, count;
    if (!PyArg_ParseTuple(args, "kkk", &dest_page_num, &src_page_num, &count)) return NULL;
    for (unsigned long i = 0; i < count; i++) {
        impose_page(self->doc, dest_page_num - 1 + i, src_page_num - 1 + i);
    }
    auto& pages = self->doc->GetPages();
    while (count-- && src_page_num <= pages.GetCount()) pages.RemovePageAt(src_page_num - 1);
    Py_RETURN_NONE;
}

PYWRAP(impose)
