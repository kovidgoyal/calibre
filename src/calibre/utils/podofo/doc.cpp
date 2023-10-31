/*
 * doc.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <algorithm>
#include <new>

using namespace pdf;

// Constructor/destructor {{{
static void
PDFDoc_dealloc(PDFDoc* self)
{
    if (self->doc != NULL) delete self->doc;
    Py_CLEAR(self->load_buffer_ref);
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
		self->doc->LoadFromBuffer(bufferview(buffer, size));
        Py_CLEAR(self->load_buffer_ref);
        self->load_buffer_ref = args;
        Py_INCREF(args);
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
            self->doc->Save(buffer, save_options);
        } catch(const PdfError & err) {
            podofo_set_exception(err);
            return NULL;
        }
    } else return NULL;

    Py_RETURN_NONE;
}

class BytesOutputDevice : public OutputStreamDevice {
    private:
        pyunique_ptr bytes;
        size_t written;
    public:
        BytesOutputDevice() : bytes(), written(0) { SetAccess(DeviceAccess::Write); }
        size_t GetLength() const { return written; }
        size_t GetPosition() const { return written; }
        size_t capacity() const { return bytes ? PyBytes_GET_SIZE(bytes.get()) : 0; }
        bool Eof() const { return false; }

        void writeBuffer(const char* src, size_t src_sz) {
            if (written + src_sz > capacity()) {
                PyObject* old = bytes.release();
                static const size_t initial_capacity = 1024 * 1024;
                if (old) {
                    if (_PyBytes_Resize(&old, std::max(written + src_sz, 2 * std::max(capacity(), initial_capacity))) != 0) {
                        throw std::bad_alloc();
                    }
                } else {
                    old = PyBytes_FromStringAndSize(NULL, std::max(written + src_sz, initial_capacity));
                    if (!old) throw std::bad_alloc();
                }
                bytes.reset(old);
            }
            if (bytes) {
                memcpy(PyBytes_AS_STRING(bytes.get()) + written, src, src_sz);
                written += src_sz;
            }
        }

        void Flush() { }
        PyObject* Release() {
            auto ans = bytes.release();
            _PyBytes_Resize(&ans, written);
            written = 0;
            return ans;
        }
};

static PyObject *
PDFDoc_write(PDFDoc *self, PyObject *args) {
    PyObject *ans;
    BytesOutputDevice d;

    try {
        self->doc->Save(d, save_options);
        return d.Release();
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
    try {
        auto& objects = self->doc->GetObjects();
        for (auto obj : objects) {
            auto stream = obj->GetStream();
            if (stream == nullptr) continue;
            try {
                try {
                    stream->Unwrap();
                } catch (PdfError& e) {
                    if (e.GetCode() != PdfErrorCode::Flate) throw e;
                }
            }
            catch (PdfError& e) {
                if (e.GetCode() != PdfErrorCode::UnsupportedFilter) throw e;
            }
        }
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    Py_RETURN_NONE;
}


// }}}

// extract_first_page() {{{
static PyObject *
PDFDoc_extract_first_page(PDFDoc *self, PyObject *args) {
    try {
        auto pages = &self->doc->GetPages();
        while (pages->GetCount() > 1) pages->RemovePageAt(1);
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
        count = self->doc->GetPages().GetCount();
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
                 if( ( obj_type && obj_type->IsName() && ( obj_type->GetName().GetString() == "XObject" ) ) ||
                        ( obj_sub_type && obj_sub_type->IsName() && ( obj_sub_type->GetName().GetString() == "Image" ) ) ) count++;
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
    unsigned int page, count = 1;
    if (PyArg_ParseTuple(args, "I|I", &page, &count)) {
        try {
            auto &pages = self->doc->GetPages();
            while (count-- > 0) pages.RemovePageAt(page - 1);
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
			auto page = get_page(self->doc, pagenum-1);
            if (!page) { PyErr_Format(PyExc_ValueError, "page number %d not found in PDF file", pagenum); return NULL; }
			Rect rect;
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
			return Py_BuildValue("dddd", rect.GetLeft(), rect.GetBottom(), rect.Width, rect.Height);
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
			PdfPage* page = get_page(self->doc, pagenum-1);
            if (!page) { PyErr_Format(PyExc_ValueError, "page number %d not found in PDF file", pagenum); return NULL; }
			Rect rect(left, bottom, width, height);
			PdfArray box;
			rect.ToArray(box);
			page->GetObject().GetDictionary().AddKey(PdfName(which), box);
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
        self->doc->GetPages().InsertDocumentPageAt(to - 1, *self->doc, from - 1);
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    Py_RETURN_NONE;
} // }}}

// append() {{{

static PyObject *
PDFDoc_append(PDFDoc *self, PyObject *args) {
    class AppendPagesData {
        public:
            const PdfPage *src_page;
            PdfPage *dest_page;
            PdfReference dest_page_parent;
            AppendPagesData(const PdfPage &src, PdfPage &dest) {
                src_page = &src;
                dest_page = &dest;
                dest_page_parent = dest.GetDictionary().GetKeyAs<PdfReference>("Parent");
            }
    };
    class MapReferences : public std::unordered_map<PdfReference, PdfObject*> {
        public:
            void apply(PdfObject &parent) {
                switch(parent.GetDataType()) {
                    case PdfDataType::Dictionary:
                        for (auto& pair : parent.GetDictionary()) {
                            apply(pair.second );
                        }
                        break;
                    case PdfDataType::Array:
                        for (auto& child : parent.GetArray())  apply(child);
                        break;
                    case PdfDataType::Reference:
                        if (auto search = find(parent.GetReference()); search != end()) {
                            parent.SetReference(search->second->GetIndirectReference());
                        }
                        break;
                    default:
                        break;
                }
            }
    };

    static const PdfName inheritableAttributes[] = {
        PdfName("Resources"),
        PdfName("MediaBox"),
        PdfName("CropBox"),
        PdfName("Rotate"),
        PdfName::KeyNull
    };
    PdfMemDocument *dest = self->doc;
    std::vector<const PdfMemDocument*> docs(PyTuple_GET_SIZE(args));
    for (Py_ssize_t i = 0; i < PyTuple_GET_SIZE(args); i++) {
        PyObject *doc = PyTuple_GET_ITEM(args, i);
        int typ = PyObject_IsInstance(doc, (PyObject*)&PDFDocType);
        if (typ == -1) return NULL;
        if (typ == 0) { PyErr_SetString(PyExc_TypeError, "You must pass a PDFDoc instance to this method"); return NULL; }
        docs[i] = ((PDFDoc*)doc)->doc;
    }

    PyThreadState *_save; _save = PyEval_SaveThread();
    try {
        unsigned total_pages_to_append = 0;
        for (auto src : docs)  total_pages_to_append += src->GetPages().GetCount();
        unsigned base_page_index = dest->GetPages().GetCount();
        dest->GetPages().CreatePagesAt(base_page_index, total_pages_to_append, Rect());
        for (auto src : docs) {
            MapReferences ref_map;
            std::vector<AppendPagesData> pages;
            // append pages first
            for (unsigned i = 0; i < src->GetPages().GetCount(); i++) {
                const auto& src_page = src->GetPages().GetPageAt(i);
                auto& dest_page = dest->GetPages().GetPageAt(base_page_index++);
                pages.emplace_back(src_page, dest_page);
                dest_page.GetObject() = src_page.GetObject();
                dest_page.GetDictionary().RemoveKey("Resource");
                dest_page.GetDictionary().RemoveKey("Parent");
                ref_map[src_page.GetObject().GetIndirectReference()] = &dest_page.GetObject();
            }
            // append all remaining objects
            for (const auto& obj : src->GetObjects()) {
                if (obj->IsIndirect() && ref_map.find(obj->GetIndirectReference()) == ref_map.end()) {
                    auto copied_obj = &dest->GetObjects().CreateObject(*obj);
                    ref_map[obj->GetIndirectReference()] = copied_obj;
                }
            }
            // fix references in appended objects
            for (auto& elem : ref_map) ref_map.apply(*elem.second);
            // fixup all pages
            for (auto& x : pages) {
                auto& src_page = *x.src_page;
                auto& dest_page = *x.dest_page;
                dest_page.GetDictionary().AddKey("Parent", x.dest_page_parent);
                // Set the page contents
                if (auto key = src_page.GetDictionary().GetKeyAs<PdfReference>(PdfName::KeyContents); key.IsIndirect()) {
                    if (auto search = ref_map.find(key); search != ref_map.end()) {
                        dest_page.GetOrCreateContents().Reset(search->second);
                    }
                }
                // ensure the contents is not NULL to prevent segfaults in other code that assumes it
                dest_page.GetOrCreateContents();

                // Set the page resources
                if (src_page.GetResources() != nullptr) {
                    const auto &src_resources = src_page.GetResources()->GetDictionary();
                    dest_page.GetOrCreateResources().GetDictionary() = src_resources;
                    ref_map.apply(dest_page.GetResources()->GetObject());
                } else dest_page.GetOrCreateResources();

                // Copy inherited properties
                auto inherited = inheritableAttributes;
                while (!inherited->IsNull()) {
                    auto attribute = src_page.GetDictionary().FindKeyParent(*inherited);
                    if (attribute != nullptr) {
                        PdfObject attributeCopy(*attribute);
                        ref_map.apply(attributeCopy);
                        dest_page.GetDictionary().AddKey(*inherited, attributeCopy);
                    }
                    inherited++;
                }
            }
        }
    } catch (const PdfError & err) {
        PyEval_RestoreThread(_save);
        podofo_set_exception(err);
        return NULL;
    } catch (std::exception & err) {
        PyEval_RestoreThread(_save);
        PyErr_Format(PyExc_ValueError, "An error occurred while trying to append pages: %s", err.what());
        return NULL;
    }
    PyEval_RestoreThread(_save);
    Py_RETURN_NONE;
} // }}}

// insert_existing_page() {{{
static PyObject *
PDFDoc_insert_existing_page(PDFDoc *self, PyObject *args) {
    PDFDoc *src_doc;
    int src_page = 0, at = 0;

    if (!PyArg_ParseTuple(args, "O!|ii", &PDFDocType, &src_doc, &src_page, &at)) return NULL;

    try {
        self->doc->GetPages().InsertDocumentPageAt(at, *src_doc->doc, src_page);
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
        Rect r(left, bottom, width, height);
        PdfArray o;
        r.ToArray(o);
        self->doc->GetPages().GetPageAt(num).GetObject().GetDictionary().AddKey(PdfName(box), o);
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
    try {
        auto obj = self->doc->GetCatalog().GetDictionary().FindKey("Metadata");
        if (obj == nullptr) Py_RETURN_NONE;
        auto stream = obj->GetStream();
        if (stream == nullptr) Py_RETURN_NONE;
        std::string s;
        StringStreamDevice ouput(s);
        stream->CopyTo(ouput);
        return PyBytes_FromStringAndSize(s.data(), s.size());
    } catch(const PdfError & err) {
        podofo_set_exception(err); return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to read the XML metadata"); return NULL;
    }
    Py_RETURN_NONE;
} // }}}

// add_image_page() {{{
static PyObject *
PDFDoc_add_image_page(PDFDoc *self, PyObject *args) {
    const char *image_data; Py_ssize_t image_data_sz;
    double page_x, page_y, page_width, page_height;
    double image_x, image_y, image_canvas_width, image_canvas_height;
    unsigned int page_num = 1; int preserve_aspect_ratio = 1;
    if (!PyArg_ParseTuple(args, "y#dddddddd|Ip", &image_data, &image_data_sz, &page_x, &page_y, &page_width, &page_height, &image_x, &image_y, &image_canvas_width, &image_canvas_height, &page_num, &preserve_aspect_ratio)) return NULL;
    auto img = self->doc->CreateImage();
    img->LoadFromBuffer(bufferview(image_data, image_data_sz));
    auto &page = self->doc->GetPages().CreatePageAt(page_num-1, Rect(page_x, page_y, page_width, page_height));
    PdfPainter painter;
    painter.SetCanvas(page);
    auto scaling_x = image_canvas_width, scaling_y = image_canvas_height;
    if (preserve_aspect_ratio) {
        auto page_ar = page_width / page_height, img_ar = img->GetRect().Width / img->GetRect().Height;
        if (page_ar > img_ar) {
            scaling_x = img_ar * image_canvas_height;
            image_x = (image_canvas_width - scaling_x) / 2.;
        } else if (page_ar < img_ar) {
            scaling_y = image_canvas_width / img_ar;
            image_y = (image_canvas_height - scaling_y) / 2.;
        }
    }
    painter.DrawImage(*img, image_x, image_y, scaling_x / img->GetRect().Width, scaling_y / img->GetRect().Height);
    painter.FinishDrawing();
    return Py_BuildValue("dd", img->GetRect().Width, img->GetRect().Height);
}
// }}}

// set_xmp_metadata() {{{
static PyObject *
PDFDoc_set_xmp_metadata(PDFDoc *self, PyObject *args) {
    const char *raw = NULL;
    Py_ssize_t len = 0;
    if (!PyArg_ParseTuple(args, "y#", &raw, &len)) return NULL;
    try {
        auto& metadata = self->doc->GetCatalog().GetOrCreateMetadataObject();
        auto& stream = metadata.GetOrCreateStream();
        stream.SetData(std::string_view(raw, len), true);
        metadata.GetDictionary().RemoveKey(PdfName::KeyFilter);
    } catch(const PdfError & err) {
        podofo_set_exception(err); return NULL;
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to set the XML metadata"); return NULL;
    }

    Py_RETURN_NONE;
} // }}}

// extract_anchors() {{{
static PyObject *
PDFDoc_extract_anchors(PDFDoc *self, PyObject *args) {
    PyObject *ans = PyDict_New();
	if (ans == NULL) return NULL;
    try {
        const PdfObject *dests_ref = self->doc->GetCatalog().GetDictionary().GetKey("Dests");
        auto& pages = self->doc->GetPages();
        if (dests_ref && dests_ref->IsReference()) {
            const PdfObject *dests_obj = self->doc->GetObjects().GetObject(object_as_reference(dests_ref));
            if (dests_obj && dests_obj->IsDictionary()) {
                const PdfDictionary &dests = dests_obj->GetDictionary();
                for (auto itres: dests) {
                    if (itres.second.IsArray()) {
                        const PdfArray &dest = itres.second.GetArray();
                        // see section 8.2 of PDF spec for different types of destination arrays
                        // but chromium apparently generates only [page /XYZ left top zoom] type arrays
                        if (dest.GetSize() > 4 && dest[1].IsName() && dest[1].GetName().GetString() == "XYZ") {
                            const PdfPage *page = get_page(pages, object_as_reference(dest[0]));
                            if (page) {
                                unsigned int pagenum = page->GetPageNumber();
                                double left = dest[2].GetReal(), top = dest[3].GetReal();
                                long long zoom = dest[4].GetNumber();
                                const std::string &anchor = itres.first.GetString();
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
    } catch(const PdfError & err) {
        podofo_set_exception(err);
    } catch (...) {
        PyErr_SetString(PyExc_ValueError, "An unknown error occurred while trying to set the box");
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
    const std::string &uri = uo->GetString().GetString();
    pyunique_ptr ret(PyObject_CallObject(alter_callback, Py_BuildValue("(N)", PyUnicode_DecodeUTF8(uri.c_str(), uri.length(), "replace"))));
    if (!ret) { return; }
    if (PyTuple_Check(ret.get()) && PyTuple_GET_SIZE(ret.get()) == 4) {
        int pagenum; double left, top, zoom;
        if (PyArg_ParseTuple(ret.get(), "iddd", &pagenum, &left, &top, &zoom)) {
            const PdfPage *page = get_page(self->doc, pagenum - 1);
            if (page == NULL) {
                PyErr_Format(PyExc_ValueError, "No page number %d in the PDF file of %d pages", pagenum, self->doc->GetPages().GetCount());
                return;
            }
                link.RemoveKey("A");
                PdfDestination dest(*page, left, top, zoom);
                dest.AddToDictionary(link);
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
        border.Add(int64_t(16)); border.Add(int64_t(16)); border.Add(int64_t(1));
		link_color.Add(1.); link_color.Add(0.); link_color.Add(0.);
        std::vector<PdfReference> links;
        for (auto &it : self->doc->GetObjects()) {
            PdfDictionary *link;
			if(it->TryGetDictionary(link)) {
				if (dictionary_has_key_name(*link, PdfName::KeyType, "Annot") && dictionary_has_key_name(*link, PdfName::KeySubtype, "Link")) {
                    PdfObject *akey; PdfDictionary *A;
					if ((akey = link->GetKey("A")) && akey->TryGetDictionary(A)) {
						if (dictionary_has_key_name(*A, PdfName::KeyType, "Action") && dictionary_has_key_name(*A, "S", "URI")) {
							PdfObject *uo = A->GetKey("URI");
							if (uo && uo->IsString()) {
                                links.push_back(object_as_reference(it));
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
    unsigned long pages = self->doc->GetPages().GetCount();
    PyObject *ans = PyLong_FromUnsignedLong(pages);
    if (ans != NULL) Py_INCREF(ans);
    return ans;
}

static PyObject *
PDFDoc_version_getter(PDFDoc *self, void *closure) {
    PdfVersion version;
    try {
        version = self->doc->GetMetadata().GetPdfVersion();
    } catch(const PdfError & err) {
        podofo_set_exception(err);
        return NULL;
    }
    switch(version) {
        case PdfVersion::V1_0:
            return PyUnicode_FromString("1.0");
        case PdfVersion::V1_1:
            return PyUnicode_FromString("1.1");
        case PdfVersion::V1_2:
            return PyUnicode_FromString("1.2");
        case PdfVersion::V1_3:
            return PyUnicode_FromString("1.3");
        case PdfVersion::V1_4:
            return PyUnicode_FromString("1.4");
        case PdfVersion::V1_5:
            return PyUnicode_FromString("1.5");
        case PdfVersion::V1_6:
            return PyUnicode_FromString("1.6");
        case PdfVersion::V1_7:
            return PyUnicode_FromString("1.7");
        case PdfVersion::V2_0:
            return PyUnicode_FromString("2.0");
        case PdfVersion::Unknown:
            return PyUnicode_FromString("");
    }
    return PyUnicode_FromString("");
}

static PdfDictionary&
get_or_create_info(PDFDoc *self) {
    PdfObject *info = self->doc->GetTrailer().GetDictionary().FindKey("Info");
    if (info && info->IsDictionary()) return info->GetDictionary();
    info = &self->doc->GetObjects().CreateDictionaryObject();
    self->doc->GetTrailer().GetDictionary().AddKeyIndirect("Info", *info);
    return info->GetDictionary();
}

static inline PyObject*
string_metadata_getter(PDFDoc *self, const std::string_view name) {
    auto info = get_or_create_info(self);
    auto obj = info.FindKey(name);
    const PdfString* str;
    return (obj == nullptr || !obj->TryGetString(str)) ?  PyUnicode_FromString("") : podofo_convert_pdfstring(*str);
}


static PyObject *
PDFDoc_title_getter(PDFDoc *self, void *closure) {
    return string_metadata_getter(self, "Title");
}

static PyObject *
PDFDoc_author_getter(PDFDoc *self, void *closure) {
    return string_metadata_getter(self, "Author");
}

static PyObject *
PDFDoc_subject_getter(PDFDoc *self, void *closure) {
    return string_metadata_getter(self, "Subject");
}

static PyObject *
PDFDoc_keywords_getter(PDFDoc *self, void *closure) {
    return string_metadata_getter(self, "Keywords");
}

static PyObject *
PDFDoc_creator_getter(PDFDoc *self, void *closure) {
    return string_metadata_getter(self, "Creator");
}

static PyObject *
PDFDoc_producer_getter(PDFDoc *self, void *closure) {
    return string_metadata_getter(self, "Producer");
}

static inline int
string_metadata_setter(PDFDoc *self, const std::string_view name, PyObject *val) {
    if (!PyUnicode_Check(val)) { PyErr_SetString(PyExc_TypeError, "Must use unicode to set metadata"); return -1;  }
    auto& info = get_or_create_info(self);
    const char *raw; Py_ssize_t sz;
    raw = PyUnicode_AsUTF8AndSize(val, &sz);
    if (sz == 0) info.RemoveKey(name);
    else info.AddKey(name, PdfString(std::string_view(raw, sz)));
    return 0;
}


static int
PDFDoc_title_setter(PDFDoc *self, PyObject *val, void *closure) {
    try {
        return string_metadata_setter(self, "Title", val);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return -1;
    }
}

static int
PDFDoc_author_setter(PDFDoc *self, PyObject *val, void *closure) {
    try {
        return string_metadata_setter(self, "Author", val);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return -1;
    }
}

static int
PDFDoc_subject_setter(PDFDoc *self, PyObject *val, void *closure) {
    try {
        return string_metadata_setter(self, "Subject", val);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return -1;
    }
}

static int
PDFDoc_keywords_setter(PDFDoc *self, PyObject *val, void *closure) {
    try {
        return string_metadata_setter(self, "Keywords", val);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return -1;
    }
}

static int
PDFDoc_creator_setter(PDFDoc *self, PyObject *val, void *closure) {
    try {
        return string_metadata_setter(self, "Creator", val);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return -1;
    }
}

static int
PDFDoc_producer_setter(PDFDoc *self, PyObject *val, void *closure) {
    try {
        return string_metadata_setter(self, "Producer", val);
	} catch(const PdfError & err) {
		podofo_set_exception(err);
		return -1;
    }
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
    {"add_image_page", (PyCFunction)PDFDoc_add_image_page, METH_VARARGS,
     "add_image_page(image_data, page_idx=0) -> Add the specified image as a full page image, will use the size of the first existing page as page size."
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
