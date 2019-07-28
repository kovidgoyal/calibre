/*
 * impose.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace pdf;

static void
impose_page(PdfMemDocument *doc, unsigned long dest_page_num, unsigned long src_page_num) {
    PdfXObject *xobj = new PdfXObject(doc, src_page_num, "HeaderFooter");
    PdfPage *dest = doc->GetPage(dest_page_num);
    dest->AddResource(xobj->GetIdentifier(), xobj->GetObject()->Reference(), "XObject");
    PdfStream *stream = dest->GetContents()->GetStream();
    char *buffer = NULL; pdf_long sz;
    stream->GetFilteredCopy(&buffer, &sz);
    stream->BeginAppend();
    stream->Append("q\n1 0 0 1 0 0 cm\n/");
    stream->Append(xobj->GetIdentifier().GetName());
    stream->Append(" Do\nQ\n");
    stream->Append(buffer, sz);
    stream->EndAppend();
    podofo_free(buffer);
}

static PyObject*
impose(PDFDoc *self, PyObject *args) {
    unsigned long dest_page_num, src_page_num, count;
    if (!PyArg_ParseTuple(args, "kkk", &dest_page_num, &src_page_num, &count)) return NULL;
    for (unsigned long i = 0; i < count; i++) {
        impose_page(self->doc, dest_page_num - 1 + i, src_page_num - 1 + i);
    }
    self->doc->DeletePages(src_page_num - 1, count);
    Py_RETURN_NONE;
}

PYWRAP(impose)
