/*
 * doc.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <iostream>

using namespace pdf;

// Constructor/destructor {{{
static void
PDFDoc_dealloc(PDFDoc* self)
{
    if (self->doc != NULL) delete self->doc;
    Py_TYPE(self)->tp_free((PyObject*)self);
}

static PyObject *
PDFDoc_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    PDFDoc *self;

    self = (PDFDoc *)type->tp_alloc(type, 0);
    if (self != NULL) {
        self->doc = new PdfMemDocument();
        if (self->doc == NULL) { Py_DECREF(self); return NULL; }
    }

    return (PyObject *)self;
}
// }}}

// Loading/Opening of PDF files {{{
static PyObject *
PDFDoc_load(PDFDoc *self, PyObject *args) {
    char *buffer; Py_ssize_t size;

    if (!PyArg_ParseTuple(args, "y#", &buffer, &size)) return NULL;

	try {
#if PODOFO_VERSION <= 0x000905
		self->doc->Load(buffer, (long)size);
#else
		self->doc->LoadFromBuffer(buffer, (long)size);
#endif
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return NULL;
	}

    Py_RETURN_NONE;
}

static PyObject *
PDFDoc_open(PDFDoc *self, PyObject *args) {
    char *fname;
#ifdef _WIN32
#define ENCODING "mbcs"
#else
#define ENCODING "utf-8"
#endif
    if (!PyArg_ParseTuple(args, "es", ENCODING, &fname)) return NULL;
#undef ENCODING
	try {
		self->doc->Load(fname);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		PyMem_Free(fname);
		return NULL;
	}
	PyMem_Free(fname);

    Py_RETURN_NONE;
}
// }}}

// Saving/writing of PDF files {{{
static PyObject *
PDFDoc_save(PDFDoc *self, PyObject *args) {
    char *buffer;

    if (PyArg_ParseTuple(args, "s", &buffer)) {
        try {
            self->doc->Write(buffer);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
}

static PyObject *
PDFDoc_write(PDFDoc *self, PyObject *args) {
    PyObject *ans;

    try {
        PdfRefCountedBuffer buffer(1*1024*1024);
        PdfOutputDevice out(&buffer);
        self->doc->Write(&out);
        ans = PyBytes_FromStringAndSize(buffer.GetBuffer(), out.Tell());
        if (ans == NULL) PyErr_NoMemory();
    } catch(const PdfError &err) {
        podofo_set_exception(err);
        return NULL;
    } catch (...) {
        return PyErr_NoMemory();
    }

    return ans;
}

static PyObject *
PDFDoc_save_to_fileobj(PDFDoc *self, PyObject *args) {
    PyObject *f;

    if (!PyArg_ParseTuple(args, "O", &f)) return NULL;
    return write_doc(self->doc, f);
}

static PyObject *
PDFDoc_uncompress_pdf(PDFDoc *self, PyObject *args) {
    for (auto &it : self->doc->GetObjects()) {
        if(it->HasStream()) {
            PdfMemStream* stream = dynamic_cast<PdfMemStream*>(it->GetStream());
            stream->Uncompress();
        }
    }
    Py_RETURN_NONE;
}


// }}}

// extract_first_page() {{{
static PyObject *
PDFDoc_extract_first_page(PDFDoc *self, PyObject *args) {
    try {
        while (self->doc->GetPageCount() > 1) self->doc->GetPagesTree()->DeletePage(1);
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    Py_RETURN_NONE;
}
// }}}

// page_count() {{{
static PyObject *
PDFDoc_page_count(PDFDoc *self, PyObject *args) {
    int count;
    try {
        count = self->doc->GetPageCount();
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    return Py_BuildValue("i", count);
} // }}}

// image_count() {{{
static PyObject *
PDFDoc_image_count(PDFDoc *self, PyObject *args) {
    int count = 0;
    const PdfObject* obj_type = NULL;
    const PdfObject* obj_sub_type = NULL;
    try {
         for (auto &it : self->doc->GetObjects()) {
             if( it->IsDictionary() ) {
                 obj_type = it->GetDictionary().GetKey( PdfName::KeyType );
                 obj_sub_type = it->GetDictionary().GetKey( PdfName::KeySubtype );
                 if( ( obj_type && obj_type->IsName() && ( obj_type->GetName().GetName() == "XObject" ) ) ||
                        ( obj_sub_type && obj_sub_type->IsName() && ( obj_sub_type->GetName().GetName() == "Image" ) ) ) count++;
             }
         }
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    return Py_BuildValue("i", count);
} // }}}

// delete_page() {{{
static PyObject *
PDFDoc_delete_pages(PDFDoc *self, PyObject *args) {
    int page = 0, count = 1;
    if (PyArg_ParseTuple(args, "i|i", &page, &count)) {
        try {
            self->doc->DeletePages(page - 1, count);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
} // }}}

// get_page_box() {{{
static PyObject *
PDFDoc_get_page_box(PDFDoc *self, PyObject *args) {
    int pagenum = 0;
	const char *which;
    if (PyArg_ParseTuple(args, "si", &which, &pagenum)) {
        try {
			PdfPagesTree* tree = self->doc->GetPagesTree();
			PdfPage* page = tree->GetPage(pagenum - 1);
			if (!page) { PyErr_Format(PyExc_ValueError, "page number %d not found in PDF file", pagenum); return NULL; }
			PdfRect rect;
			if (strcmp(which, "MediaBox") == 0) {
				rect = page->GetMediaBox();
			} else if (strcmp(which, "CropBox") == 0) {
				rect = page->GetCropBox();
			} else if (strcmp(which, "TrimBox") == 0) {
				rect = page->GetTrimBox();
			} else if (strcmp(which, "BleedBox") == 0) {
				rect = page->GetBleedBox();
			} else if (strcmp(which, "ArtBox") == 0) {
				rect = page->GetArtBox();
			} else {
				PyErr_Format(PyExc_KeyError, "%s is not a known box", which);
				return NULL;
			}
			return Py_BuildValue("dddd", rect.GetLeft(), rect.GetBottom(), rect.GetWidth(), rect.GetHeight());
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
} // }}}

// set_page_box() {{{
static PyObject *
PDFDoc_set_page_box(PDFDoc *self, PyObject *args) {
    int pagenum = 0;
	double left, bottom, width, height;
	const char *which;
    if (PyArg_ParseTuple(args, "sidddd", &which, &pagenum, &left, &bottom, &width, &height)) {
        try {
			PdfPagesTree* tree = self->doc->GetPagesTree();
			PdfPage* page = tree->GetPage(pagenum - 1);
			if (!page) { PyErr_Format(PyExc_ValueError, "page number %d not found in PDF file", pagenum); return NULL; }
			PdfRect rect(left, bottom, width, height);
			PdfObject box;
			rect.ToVariant(box);
			page->GetObject()->GetDictionary().AddKey(PdfName(which), box);
			Py_RETURN_NONE;
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
} // }}}

// copy_page() {{{
static PyObject *
PDFDoc_copy_page(PDFDoc *self, PyObject *args) {
    int from = 0, to = 0;
    if (!PyArg_ParseTuple(args, "ii", &from, &to)) return NULL;
    try {
        PdfPagesTree* tree = self->doc->GetPagesTree();
        PdfPage* page = tree->GetPage(from - 1);
        tree->InsertPage(to - 1, page);
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    Py_RETURN_NONE;
} // }}}

// append() {{{
static PyObject *
PDFDoc_append(PDFDoc *self, PyObject *args) {
    PyObject *doc;
    int typ;

    if (!PyArg_ParseTuple(args, "O", &doc)) return NULL;

    typ = PyObject_IsInstance(doc, (PyObject*)&PDFDocType);
    if (typ == -1) return NULL;
    if (typ == 0) { PyErr_SetString(PyExc_TypeError, "You must pass a PDFDoc instance to this method"); return NULL; }

    try {
        self->doc->Append(*((PDFDoc*)doc)->doc, true);
    } catch (const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }

    Py_RETURN_NONE;
} // }}}

// insert_existing_page() {{{
static PyObject *
PDFDoc_insert_existing_page(PDFDoc *self, PyObject *args) {
    PDFDoc *src_doc;
    int src_page = 0, at = 0;

    if (!PyArg_ParseTuple(args, "O!|ii", &PDFDocType, &src_doc, &src_page, &at)) return NULL;

    try {
        self->doc->InsertExistingPageAt(*src_doc->doc, src_page, at);
    } catch (const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }

    Py_RETURN_NONE;
} // }}}

// set_box() {{{
static PyObject *
PDFDoc_set_box(PDFDoc *self, PyObject *args) {
    int num = 0;
    double left, bottom, width, height;
    char *box;
    if (!PyArg_ParseTuple(args, "isdddd", &num, &box, &left, &bottom, &width, &height)) return NULL;

    try {
        PdfRect r(left, bottom, width, height);
        PdfObject o;
        r.ToVariant(o);
        self->doc->GetPage(num)->GetObject()->GetDictionary().AddKey(PdfName(box), o);
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to set the box");
        return NULL;
    }

    Py_RETURN_NONE;
} // }}}

// get_xmp_metadata() {{{
static PyObject *
PDFDoc_get_xmp_metadata(PDFDoc *self, PyObject *args) {
    PoDoFo::PdfObject *metadata = NULL;
    PoDoFo::PdfStream *str = NULL;
    PoDoFo::pdf_long len = 0;
	char *buf = NULL;
    PyObject *ans = NULL;

    try {
        if ((metadata = self->doc->GetMetadata()) != NULL) {
            if ((str = metadata->GetStream()) != NULL) {
                str->GetFilteredCopy(&buf, &len);
                if (buf != NULL) {
                    Py_ssize_t psz = len;
                    ans = Py_BuildValue("y#", buf, psz);
                    free(buf); buf = NULL;
                    if (ans == NULL) goto error;
                }
            }
        }
    } catch(const PdfError & err) {
        podofo_set_exception(err); goto error;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to read the XML metadata"); goto error;
    }

    if (ans != NULL) return ans;
    Py_RETURN_NONE;
error:
    return NULL;
} // }}}

// set_xmp_metadata() {{{
static PyObject *
PDFDoc_set_xmp_metadata(PDFDoc *self, PyObject *args) {
    const char *raw = NULL;
    Py_ssize_t len = 0;
    PoDoFo::PdfObject *metadata = NULL, *catalog = NULL;
    PoDoFo::PdfStream *str = NULL;
    TVecFilters compressed(1);
    compressed[0] = ePdfFilter_FlateDecode;

    if (!PyArg_ParseTuple(args, "y#", &raw, &len)) return NULL;
    try {
        if ((metadata = self->doc->GetMetadata()) != NULL) {
            if ((str = metadata->GetStream()) == NULL) { PyErr_NoMemory(); goto error; }
            str->Set(raw, len, compressed);
        } else {
            if ((catalog = self->doc->GetCatalog()) == NULL) { PyErr_SetString(PyExc_ValueError, "Cannot set XML metadata as this document has no catalog"); goto error; }
            if ((metadata = self->doc->GetObjects().CreateObject("Metadata")) == NULL) { PyErr_NoMemory(); goto error; }
            if ((str = metadata->GetStream()) == NULL) { PyErr_NoMemory(); goto error; }
            metadata->GetDictionary().AddKey(PoDoFo::PdfName("Subtype"), PoDoFo::PdfName("XML"));
            str->Set(raw, len, compressed);
            catalog->GetDictionary().AddKey(PoDoFo::PdfName("Metadata"), metadata->Reference());
        }
    } catch(const PdfError & err) {
        podofo_set_exception(err); goto error;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to set the XML metadata");
        goto error;
    }

    Py_RETURN_NONE;
error:
    return NULL;

} // }}}

// extract_anchors() {{{
static PyObject *
PDFDoc_extract_anchors(PDFDoc *self, PyObject *args) {
    const PdfObject* catalog = NULL;
    PyObject *ans = PyDict_New();
	if (ans == NULL) return NULL;
    try {
		if ((catalog = self->doc->GetCatalog()) != NULL) {
			const PdfObject *dests_ref = catalog->GetDictionary().GetKey("Dests");
			PdfPagesTree *tree = self->doc->GetPagesTree();
			if (dests_ref && dests_ref->IsReference()) {
				const PdfObject *dests_obj = self->doc->GetObjects().GetObject(dests_ref->GetReference());
				if (dests_obj && dests_obj->IsDictionary()) {
					const PdfDictionary &dests = dests_obj->GetDictionary();
					const TKeyMap &keys = dests.GetKeys();
					for (TCIKeyMap itres = keys.begin(); itres != keys.end(); ++itres) {
						if (itres->second->IsArray()) {
							const PdfArray &dest = itres->second->GetArray();
							// see section 8.2 of PDF spec for different types of destination arrays
							// but chromium apparently generates only [page /XYZ left top zoom] type arrays
							if (dest.GetSize() > 4 && dest[1].IsName() && dest[1].GetName().GetName() == "XYZ") {
								const PdfPage *page = tree->GetPage(dest[0].GetReference());
								if (page) {
									unsigned int pagenum = page->GetPageNumber();
									double left = dest[2].GetReal(), top = dest[3].GetReal();
									long long zoom = dest[4].GetNumber();
									const std::string &anchor = itres->first.GetName();
									PyObject *key = PyUnicode_DecodeUTF8(anchor.c_str(), anchor.length(), "replace");
									PyObject *tuple = Py_BuildValue("IddL", pagenum, left, top, zoom);
									if (!tuple || !key) { break; }
									int ret = PyDict_SetItem(ans, key, tuple);
									Py_DECREF(key); Py_DECREF(tuple);
									if (ret != 0) break;
								}
							}
						}
					}
				}
			}
		}
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        Py_CLEAR(ans);
        return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to set the box");
        Py_CLEAR(ans);
        return NULL;
    }
    if (PyErr_Occurred()) { Py_CLEAR(ans); return NULL; }
    return ans;
} // }}}

// alter_links() {{{

static void
alter_link(PDFDoc *self, PdfDictionary &link, PyObject *alter_callback, bool mark_links, PdfArray &border, PdfArray &link_color) {
    if (mark_links) {
        link.AddKey("Border", border);
        link.AddKey("C", link_color);
    }
    PdfDictionary &A = link.GetKey("A")->GetDictionary();
    PdfObject *uo = A.GetKey("URI");
    const std::string &uri = uo->GetString().GetStringUtf8();
    pyunique_ptr ret(PyObject_CallObject(alter_callback, Py_BuildValue("(N)", PyUnicode_DecodeUTF8(uri.c_str(), uri.length(), "replace"))));
    if (!ret) { return; }
    if (PyTuple_Check(ret.get()) && PyTuple_GET_SIZE(ret.get()) == 4) {
        int pagenum; double left, top, zoom;
        if (PyArg_ParseTuple(ret.get(), "iddd", &pagenum, &left, &top, &zoom)) {
            PdfPage *page = NULL;
            try {
                page = self->doc->GetPage(pagenum - 1);
            } catch(const PdfError &err) {
                (void)err;
                PyErr_Format(PyExc_ValueError, "No page number %d in the PDF file of %d pages", pagenum, self->doc->GetPageCount());
                return ;
            }
            if (page) {
                PdfDestination dest(page, left, top, zoom);
                link.RemoveKey("A");
                dest.AddToDictionary(link);
            }
        }
    }

}

static PyObject *
PDFDoc_alter_links(PDFDoc *self, PyObject *args) {
    int count = 0;
	PyObject *alter_callback, *py_mark_links;
	if (!PyArg_ParseTuple(args, "OO", &alter_callback, &py_mark_links)) return NULL;
	bool mark_links = PyObject_IsTrue(py_mark_links);
    try {
		PdfArray border, link_color;
		border.push_back((PoDoFo::pdf_int64)16); border.push_back((PoDoFo::pdf_int64)16); border.push_back((PoDoFo::pdf_int64)1);
		link_color.push_back(1.); link_color.push_back(0.); link_color.push_back(0.);
        std::vector<PdfReference> links;
        for (auto &it : self->doc->GetObjects()) {
			if(it->IsDictionary()) {
				PdfDictionary &link = it->GetDictionary();
				if (dictionary_has_key_name(link, PdfName::KeyType, "Annot") && dictionary_has_key_name(link, PdfName::KeySubtype, "Link")) {
					if (link.HasKey("A") && link.GetKey("A")->IsDictionary()) {
						PdfDictionary &A = link.GetKey("A")->GetDictionary();
						if (dictionary_has_key_name(A, PdfName::KeyType, "Action") && dictionary_has_key_name(A, "S", "URI")) {
							PdfObject *uo = A.GetKey("URI");
							if (uo && uo->IsString()) {
                                links.push_back(it->Reference());
							}
						}
					}
				}
			}
		}
        for (auto const & ref: links) {
            PdfObject *lo = self->doc->GetObjects().GetObject(ref);
            if (lo) {
                alter_link(self, lo->GetDictionary(), alter_callback, mark_links, border, link_color);
                if (PyErr_Occurred()) return NULL;
            }
        }
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    } catch(const std::exception & err) {
        PyErr_Format(PyExc_ValueError, "An error occurred while trying to alter links: %s", err.what());
        return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to alter links");
        return NULL;
    }
    return Py_BuildValue("i", count);
} // }}}

// Properties {{{

static PyObject *
PDFDoc_pages_getter(PDFDoc *self, void *closure) {
    int pages = self->doc->GetPageCount();
    PyObject *ans = PyLong_FromLong(static_cast<long>(pages));
    if (ans != NULL) Py_INCREF(ans);
    return ans;
}

static PyObject *
PDFDoc_version_getter(PDFDoc *self, void *closure) {
    int version;
    try {
        version = self->doc->GetPdfVersion();
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    switch(version) {
        case ePdfVersion_1_0:
            return Py_BuildValue("s", "1.0");
        case ePdfVersion_1_1:
            return Py_BuildValue("s", "1.1");
        case ePdfVersion_1_2:
            return Py_BuildValue("s", "1.2");
        case ePdfVersion_1_3:
            return Py_BuildValue("s", "1.3");
        case ePdfVersion_1_4:
            return Py_BuildValue("s", "1.4");
        case ePdfVersion_1_5:
            return Py_BuildValue("s", "1.5");
        case ePdfVersion_1_6:
            return Py_BuildValue("s", "1.6");
        case ePdfVersion_1_7:
            return Py_BuildValue("s", "1.7");
        default:
            return Py_BuildValue("");
    }
    return Py_BuildValue("");
}


static PyObject *
PDFDoc_getter(PDFDoc *self, int field)
{
    PdfString s;
    PdfInfo *info = self->doc->GetInfo();
    if (info == NULL) {
        PyErr_SetString(PyExc_Exception, "You must first load a PDF Document");
        return NULL;
    }
    switch (field) {
        case 0:
            s = info->GetTitle(); break;
        case 1:
            s = info->GetAuthor(); break;
        case 2:
            s = info->GetSubject(); break;
        case 3:
            s = info->GetKeywords(); break;
        case 4:
            s = info->GetCreator(); break;
        case 5:
            s = info->GetProducer(); break;
        default:
            PyErr_SetString(PyExc_Exception, "Bad field");
            return NULL;
    }

    return podofo_convert_pdfstring(s);
}

static int
PDFDoc_setter(PDFDoc *self, PyObject *val, int field) {
    if (val == NULL || !PyUnicode_Check(val)) {
        PyErr_SetString(PyExc_ValueError, "Must use unicode objects to set metadata");
        return -1;
    }
    PdfInfo *info = self->doc->GetInfo();
    if (!info) { PyErr_SetString(Error, "You must first load a PDF Document"); return -1; }
    const PdfString s = podofo_convert_pystring(val);

    switch (field) {
        case 0:
            info->SetTitle(s); break;
        case 1:
            info->SetAuthor(s); break;
        case 2:
            info->SetSubject(s); break;
        case 3:
            info->SetKeywords(s); break;
        case 4:
            info->SetCreator(s); break;
        case 5:
            info->SetProducer(s); break;
        default:
            PyErr_SetString(Error, "Bad field");
            return -1;
    }

    return 0;
}

static PyObject *
PDFDoc_title_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 0);
}
static PyObject *
PDFDoc_author_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 1);
}
static PyObject *
PDFDoc_subject_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 2);
}
static PyObject *
PDFDoc_keywords_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 3);
}
static PyObject *
PDFDoc_creator_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 4);
}
static PyObject *
PDFDoc_producer_getter(PDFDoc *self, void *closure) {
    return  PDFDoc_getter(self, 5);
}
static int
PDFDoc_title_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 0);
}
static int
PDFDoc_author_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 1);
}
static int
PDFDoc_subject_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 2);
}
static int
PDFDoc_keywords_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 3);
}
static int
PDFDoc_creator_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 4);
}
static int
PDFDoc_producer_setter(PDFDoc *self, PyObject *val, void *closure) {
    return  PDFDoc_setter(self, val, 5);
}

static PyGetSetDef PDFDoc_getsetters[] = {
    {(char *)"title",
     (getter)PDFDoc_title_getter, (setter)PDFDoc_title_setter,
     (char *)"Document title",
     NULL},
    {(char *)"author",
     (getter)PDFDoc_author_getter, (setter)PDFDoc_author_setter,
     (char *)"Document author",
     NULL},
    {(char *)"subject",
     (getter)PDFDoc_subject_getter, (setter)PDFDoc_subject_setter,
     (char *)"Document subject",
     NULL},
    {(char *)"keywords",
     (getter)PDFDoc_keywords_getter, (setter)PDFDoc_keywords_setter,
     (char *)"Document keywords",
     NULL},
    {(char *)"creator",
     (getter)PDFDoc_creator_getter, (setter)PDFDoc_creator_setter,
     (char *)"Document creator",
     NULL},
    {(char *)"producer",
     (getter)PDFDoc_producer_getter, (setter)PDFDoc_producer_setter,
     (char *)"Document producer",
     NULL},
    {(char *)"pages",
     (getter)PDFDoc_pages_getter, NULL,
     (char *)"Number of pages in document (read only)",
     NULL},
    {(char *)"version",
     (getter)PDFDoc_version_getter, NULL,
     (char *)"The PDF version (read only)",
     NULL},

    {NULL}  /* Sentinel */
};


// }}}

static PyMethodDef PDFDoc_methods[] = {
    {"load", (PyCFunction)PDFDoc_load, METH_VARARGS,
     "Load a PDF document from a byte buffer (string)"
    },
    {"open", (PyCFunction)PDFDoc_open, METH_VARARGS,
     "Load a PDF document from a file path (string)"
    },
    {"save", (PyCFunction)PDFDoc_save, METH_VARARGS,
     "Save the PDF document to a path on disk"
    },
    {"write", (PyCFunction)PDFDoc_write, METH_VARARGS,
     "Return the PDF document as a bytestring."
    },
    {"save_to_fileobj", (PyCFunction)PDFDoc_save_to_fileobj, METH_VARARGS,
     "Write the PDF document to the soecified file-like object."
    },
    {"uncompress", (PyCFunction)PDFDoc_uncompress_pdf, METH_NOARGS,
     "Uncompress the PDF"
    },
    {"extract_first_page", (PyCFunction)PDFDoc_extract_first_page, METH_VARARGS,
     "extract_first_page() -> Remove all but the first page."
    },
    {"page_count", (PyCFunction)PDFDoc_page_count, METH_VARARGS,
     "page_count() -> Number of pages in the PDF."
    },
    {"image_count", (PyCFunction)PDFDoc_image_count, METH_VARARGS,
     "image_count() -> Number of images in the PDF."
    },
    {"extract_anchors", (PyCFunction)PDFDoc_extract_anchors, METH_VARARGS,
     "extract_anchors() -> Extract information about links in the document."
    },
    {"alter_links", (PyCFunction)PDFDoc_alter_links, METH_VARARGS,
     "alter_links() -> Change links in the document."
    },
    {"list_fonts", (PyCFunction)py_list_fonts, METH_VARARGS,
     "list_fonts() -> Get list of fonts in document"
    },
    {"remove_unused_fonts", (PyCFunction)py_remove_unused_fonts, METH_NOARGS,
     "remove_unused_fonts() -> Remove unused font objects."
    },
    {"merge_fonts", (PyCFunction)py_merge_fonts, METH_VARARGS,
     "merge_fonts() -> Merge the specified fonts."
    },
    {"replace_font_data", (PyCFunction)py_replace_font_data, METH_VARARGS,
     "replace_font_data() -> Replace the data stream for the specified font."
    },
    {"dedup_type3_fonts", (PyCFunction)py_dedup_type3_fonts, METH_VARARGS,
     "dedup_type3_fonts() -> De-duplicate repeated glyphs in Type3 fonts"
    },
    {"impose", (PyCFunction)py_impose, METH_VARARGS,
     "impose() -> impose pages onto each other"
    },
    {"dedup_images", (PyCFunction)py_dedup_images, METH_VARARGS,
     "dedup_images() -> Remove duplicated images"
    },
    {"delete_pages", (PyCFunction)PDFDoc_delete_pages, METH_VARARGS,
     "delete_page(page_num, count=1) -> Delete the specified pages from the pdf."
    },
    {"get_page_box", (PyCFunction)PDFDoc_get_page_box, METH_VARARGS,
     "get_page_box(which, page_num) -> Get the specified box for the specified page as (left, bottom, width, height) in pts"
    },
    {"set_page_box", (PyCFunction)PDFDoc_set_page_box, METH_VARARGS,
     "set_page_box(which, page_num, left, bottom, width, height) -> Set the specified box (in pts) for the specified page."
    },
    {"copy_page", (PyCFunction)PDFDoc_copy_page, METH_VARARGS,
     "copy_page(from, to) -> Copy the specified page."
    },
    {"append", (PyCFunction)PDFDoc_append, METH_VARARGS,
     "append(doc) -> Append doc (which must be a PDFDoc) to this document."
    },
    {"insert_existing_page", (PyCFunction)PDFDoc_insert_existing_page, METH_VARARGS,
     "insert_existing_page(src_doc, src_page, at) -> Insert the page src_page from src_doc at index: at."
    },
    {"set_box", (PyCFunction)PDFDoc_set_box, METH_VARARGS,
     "set_box(page_num, box, left, bottom, width, height) -> Set the PDF bounding box for the page numbered nu, box must be one of: MediaBox, CropBox, TrimBox, BleedBox, ArtBox. The numbers are interpreted as pts."
    },
    {"create_outline", (PyCFunction)py_create_outline, METH_VARARGS,
     "create_outline(title, pagenum) -> Create an outline, return the first outline item."
    },
    {"get_outline", (PyCFunction)py_get_outline, METH_NOARGS,
     "get_outline() -> Get the outline if any in the PDF file."
    },
    {"get_xmp_metadata", (PyCFunction)PDFDoc_get_xmp_metadata, METH_VARARGS,
     "get_xmp_metadata(raw) -> Get the XMP metadata as raw bytes"
    },
    {"set_xmp_metadata", (PyCFunction)PDFDoc_set_xmp_metadata, METH_VARARGS,
     "set_xmp_metadata(raw) -> Set the XMP metadata to the raw bytes (which must be a valid XML packet)"
    },

    {NULL}  /* Sentinel */
};

// Type definition {{{
PyTypeObject pdf::PDFDocType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "podofo.PDFDoc",
    /* tp_basicsize      */ sizeof(PDFDoc),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor)PDFDoc_dealloc,
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
    /* tp_doc            */ "PDF Documents",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ PDFDoc_methods,
    /* tp_members        */ 0,
    /* tp_getset         */ PDFDoc_getsetters,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ PDFDoc_new,
};
// }}}
