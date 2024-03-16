/*
 * impose.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <sstream>
#include <string>

using namespace pdf;

static void
impose_page(PdfMemDocument *doc, unsigned int dest_page_num, unsigned int src_page_num) {
    auto &src_page = doc->GetPages().GetPageAt(src_page_num);
    auto xobj = doc->CreateXObjectForm(src_page.GetMediaBox(), "HeaderFooter");
    xobj->FillFromPage(src_page);
    auto &dest = doc->GetPages().GetPageAt(dest_page_num);
    dest.GetOrCreateResources().AddResource("XObject", xobj->GetIdentifier(), xobj->GetObject().GetIndirectReference());
    // prepend the header footer xobject to the stream. This means header/footer is drawn first then the contents, which works
    // since chromium does not draw in margin areas. The reverse, i.e. appending, does not work with older WebEngine before Qt 6.5.
    PdfContents *contents = dest.GetContents();
    std::ostringstream s;
    s << "q\n1 0 0 1 0 0 cm\n/" << xobj->GetIdentifier().GetString() << " Do\nQ\n" << contents->GetCopy();
    contents->Reset();
    contents->GetStreamForAppending().SetData(s.str());
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
