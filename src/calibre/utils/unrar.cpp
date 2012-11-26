/*
 * unrar.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define _UNICODE
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#ifndef RARDLL // Needed for syntastic
#define RARDLL
#endif

#include <rar.hpp>
#include <dll.hpp>
#include <errno.h>
#include <new>

static PyObject *UNRARError = NULL;

#ifndef _MSC_VER
static int wcscpy_s(wchar_t *dest, size_t sz, const wchar_t *src) {
    if (dest == NULL || src == NULL) return EINVAL;
    if (wcslen(src) >= sz) return ERANGE;
    wcscpy(dest, src);
    return 0;
}
#endif

static wchar_t *unicode_to_wchar(PyObject *o) {
    wchar_t *buf;
    Py_ssize_t len;
    if (o == NULL) return NULL;
    if (!PyUnicode_Check(o)) {PyErr_Format(PyExc_TypeError, "The python object must be a unicode object"); return NULL;}
    len = PyUnicode_GET_SIZE(o);
    buf = (wchar_t *)calloc(len+2, sizeof(wchar_t));
    if (buf == NULL) { PyErr_NoMemory(); return NULL; }
    len = PyUnicode_AsWideChar((PyUnicodeObject*)o, buf, len);
    if (len == -1) { free(buf); PyErr_Format(PyExc_TypeError, "Invalid python unicode object."); return NULL; }
    return buf;
}

static PyObject *wchar_to_unicode(const wchar_t *o) {
    PyObject *ans;
    if (o == NULL) return NULL;
    ans = PyUnicode_FromWideChar(o, wcslen(o));
    if (ans == NULL) PyErr_NoMemory();
    return ans;
}

class PyArchive : public Archive { // {{{
    public:
        PyArchive(PyObject *f, wchar_t *name, RAROptions *Cmd) : Archive(Cmd), file(f) { 
            Py_XINCREF(f);  
            wcscpy_s(FileNameW, NM, (wcslen(name) < NM-1) ? name : L"<stream>");
            if (wcstombs(FileName, FileNameW, NM-1) == (size_t)-1)
                memcpy(FileName, "<stream>", strlen("<stream>\0"));
        }

        ~PyArchive() { Py_XDECREF(file); }

        virtual bool is_archive() {
            return IsArchive(false);
        }

        virtual bool IsOpened() { return true; }

        virtual int DirectRead(void *data, size_t size) {
            // printf("direct read()\n");
            char *buf;
            Py_ssize_t sz = 0;
            int ret = 0;

            PyObject *res = PyObject_CallMethod(file, (char*)"read", (char*)"(k)", size);
            if (res == NULL) return -1;

            ret = PyBytes_AsStringAndSize(res, &buf, &sz);
            if (ret != -1) {
                memcpy(data, buf, (size_t)sz);
                ret = (int)sz;
            }
            Py_XDECREF(res);
            return ret;
        }

        virtual int Read(void *data, size_t size) {
            int ret = DirectRead(data, size);
            if (ret == -1) {
                ErrHandler.ReadError(FileName, FileNameW);
            }
            return ret;
        }

        virtual bool RawSeek(int64 offset, int method) {
            // printf("raw seek(%lld, %d)\n", offset, method);
            PyObject *res = PyObject_CallMethod(file, (char*)"seek", (char*)"Li", offset, method);
            if (res == NULL) return false;
            Py_XDECREF(res);
            return true;
        }

        virtual void Seek(int64 offset, int method) {
            if (!RawSeek(offset, method))
                ErrHandler.SeekError(FileName, FileNameW);
        }

        virtual bool Close() { return true; }

        virtual int64 Tell() {
            // printf("tell()\n");
            PyObject *res = PyObject_CallMethod(file, (char*)"tell", NULL);
            if (res == NULL) { 
                ErrHandler.SeekError(FileName, FileNameW);
            }
            Py_ssize_t pos = PyInt_AsSsize_t(res);
            Py_XDECREF(res);
            return (int64)pos;
        }

        virtual byte GetByte() {
            // printf("get byte()\n");
            byte b = 0;
            DirectRead(&b, 1);
            return b;
        }

        virtual int64 FileLength() {
            // printf("file length()\n");
            int64 pos = Tell();
            Seek(0, SEEK_END);
            int64 ans = Tell();
            Seek(pos, SEEK_SET);
            return ans;
        }

        virtual bool IsDevice() { return false; }

    private:
        PyObject *file;
}; // }}}

static 
PyMethodDef methods[] = {

    {NULL, NULL, 0, NULL}
};

// RARArchive object definition {{{
typedef struct {
    PyObject_HEAD
    // Type-specific fields go here.
    PyArchive *archive;
    PyObject *comment;
    int header_size;
    RAROptions Cmd;
    ComprDataIO DataIO;
    Unpack *Unp;
    size_t file_count;

} RARArchive;

static void
RAR_dealloc(RARArchive* self) {
    Py_XDECREF(self->comment); self->comment = NULL;

    if (self->Unp != NULL) { delete self->Unp; self->Unp = NULL; }

    if (self->archive != NULL) {
        self->archive->Close();
        delete self->archive;
        self->archive = NULL;
    }

    self->ob_type->tp_free((PyObject*)self);
}

static const char* unrar_callback_err = NULL;

static void handle_rar_error(RAR_EXIT errcode) {
    if (PyErr_Occurred()) return;
    if (unrar_callback_err != NULL) {
        PyErr_SetString(UNRARError, unrar_callback_err);
        unrar_callback_err = NULL;
        return;
    }

    const char *err = "UNKNOWN";
    switch (errcode) {
        case RARX_SUCCESS: err = "RARX_SUCCESS"; break;
        case RARX_WARNING: err = "RARX_WARNING"; break;
        case RARX_FATAL: err = "RARX_FATAL"; break;
        case RARX_CRC: err = "RARX_CRC"; break;
        case RARX_LOCK: err = "RARX_LOCK"; break;
        case RARX_WRITE: err = "RARX_WRITE"; break;
        case RARX_OPEN: err = "RARX_OPEN"; break;
        case RARX_USERERROR: err = "RARX_USERERROR"; break;
        case RARX_MEMORY: err = "RARX_MEMORY"; break;
        case RARX_CREATE: err = "RARX_CREATE"; break;
        case RARX_NOFILES: err = "RARX_NOFILES"; break;
        case RARX_USERBREAK: err = "RARX_USERBREAK"; break;
    }
    PyErr_Format(UNRARError, "RAR error code: %s", err);
}

static int CALLBACK callback(UINT msg, LPARAM data, LPARAM p1, LPARAM p2) {
    PyObject *c = (PyObject*)data, *ret;
    if (msg == UCM_PROCESSDATA) {
        ret = PyObject_CallMethod(c, (char*)"handle_data", (char*)"(s#)", (char*)p1, (size_t)p2);
        if (ret == NULL) return -1;
        Py_DECREF(ret);
        return 0;
    } else if (msg == UCM_NEEDPASSWORD || msg == UCM_NEEDPASSWORDW) {
        unrar_callback_err = "This archive is password protected.";
    } else if (msg == UCM_CHANGEVOLUME || msg == UCM_CHANGEVOLUMEW) {
        unrar_callback_err = "This is an unsupported multi-volume RAR archive.";
    }
    return -1;
}

static int
RAR_init(RARArchive *self, PyObject *args, PyObject *kwds) {
    PyObject *file, *name, *get_comment = Py_False, *pycallback;
    wchar_t *cname;

    if (!PyArg_ParseTuple(args, "OOO|O", &file, &name, &pycallback, &get_comment)) return -1;
    if (!PyObject_HasAttrString(file, "read") || !PyObject_HasAttrString(file, "seek") || !PyObject_HasAttrString(file, "tell")) {
        PyErr_SetString(PyExc_TypeError, "file must be a file like object");
        return -1;
    }
    cname = unicode_to_wchar(name);
    if (cname == NULL) return -1;

    self->Cmd.Callback = (UNRARCALLBACK)callback;
    self->Cmd.UserData = (LPARAM)pycallback;

    self->archive = new (std::nothrow) PyArchive(file, cname, &self->Cmd);
    if (self->archive == NULL) { PyErr_NoMemory(); return -1; }
    free(cname);

    self->DataIO.UnpArcSize=self->archive->FileLength();
    self->DataIO.UnpVolume=false;

    self->Unp = new (std::nothrow) Unpack(&self->DataIO);
    if (self->Unp == NULL) { PyErr_NoMemory(); return -1; }
    self->file_count = 0;

    try {
        self->Unp->Init();
        if (!self->archive->is_archive()) {
            if (!PyErr_Occurred()) 
                PyErr_SetString(UNRARError, "Not a RAR archive");
            return -1;
        }

        if (PyObject_IsTrue(get_comment)) {
            Array<byte> cdata;
            if (self->archive->GetComment(&cdata, NULL)) {
                self->comment = PyBytes_FromStringAndSize((const char*)&cdata[0], cdata.Size());
                if (self->comment == NULL) { PyErr_NoMemory(); return -1; }
            } else {
                self->comment = Py_None;
                Py_INCREF(self->comment);
            }

        } else {
            self->comment = Py_None;
            Py_INCREF(self->comment);
        }

    } catch (RAR_EXIT errcode) {
        handle_rar_error(errcode);
        return -1;
    } catch (std::bad_alloc) {
        if (!PyErr_Occurred()) 
            PyErr_NoMemory();
        return -1;
    }

    return 0;
}

// Properties {{{

// RARArchive.friendly_name {{{
static PyObject *
RAR_comment(RARArchive *self, void *closure) {
    Py_INCREF(self->comment); return self->comment;
} // }}}

static PyGetSetDef RAR_getsetters[] = {
    {(char *)"comment", 
     (getter)RAR_comment, NULL,
     (char *)"The RAR archive comment or None",
     NULL},

    {NULL}  /* Sentinel */
};
// }}}

static PyObject *
RAR_current_item(RARArchive *self, PyObject *args) {
    PyObject *filename = Py_None;
    try {
        self->header_size = (int) self->archive->SearchBlock(FILE_HEAD);

        if (self->header_size <= 0) {
            if (self->archive->Volume && self->archive->GetHeaderType() == ENDARC_HEAD &&
                    self->archive->EndArcHead.Flags & EARC_NEXT_VOLUME) {
                PyErr_SetString(UNRARError, "This is a multivolume RAR archive. Not supported.");
                return NULL;
            }
            if (self->archive->BrokenFileHeader) {
                PyErr_SetString(UNRARError, "This archive has a broken file header.");
                return NULL;
            }
            Py_RETURN_NONE;
        }

        if (self->archive->NewLhd.Flags & LHD_SPLIT_BEFORE) {
            PyErr_SetString(UNRARError, "This is a split RAR archive. Not supported.");
            return NULL;
        }
    } catch (RAR_EXIT errcode) {
        handle_rar_error(errcode);
        return NULL;
    } catch (std::bad_alloc) {
        if (!PyErr_Occurred()) 
            PyErr_NoMemory();
        return NULL;
    }

    FileHeader fh = self->archive->NewLhd;

    if (*(fh.FileNameW)) {
        filename = wchar_to_unicode(fh.FileNameW);
    } else {
        Py_INCREF(filename);
    }

    return Py_BuildValue("{s:s, s:s#, s:N, s:H, s:I, s:I, s:I, s:I, s:b, s:I, s:I, s:b, s:b, s:I, s:O, s:O, s:O, s:O}",
            "arcname", self->archive->FileName
            ,"filename", fh.FileName, fh.NameSize
            ,"filenamew", filename
            ,"flags", fh.Flags
            ,"pack_size", fh.PackSize
            ,"pack_size_high", fh.HighPackSize
            ,"unpack_size", fh.UnpSize
            ,"unpack_size_high", fh.HighUnpSize
            ,"host_os", fh.HostOS
            ,"file_crc", fh.FileCRC
            ,"file_time", fh.FileTime
            ,"unpack_ver", fh.UnpVer
            ,"method", fh.Method
            ,"file_attr", fh.FileAttr
            ,"is_directory", (self->archive->IsArcDir()) ? Py_True : Py_False
            ,"is_symlink", (IsLink(fh.FileAttr)) ? Py_True : Py_False
            ,"has_password", ((fh.Flags & LHD_PASSWORD) != 0) ? Py_True : Py_False
            ,"is_label", (self->archive->IsArcLabel()) ? Py_True : Py_False
    );

}

static File unrar_dummy_output = File();

static PyObject *
RAR_process_item(RARArchive *self, PyObject *args) {
    PyObject *extract = Py_False;

    if (!PyArg_ParseTuple(args, "|O", &extract)) return NULL;
    self->file_count++;
    try {
        if (PyObject_IsTrue(extract)) {
            if ((self->archive->NewLhd.Flags & LHD_PASSWORD) != 0) {
                PyErr_SetString(UNRARError, "This file is locked with a password.");
                return NULL;
            }
            self->DataIO.UnpVolume = false;
            self->DataIO.NextVolumeMissing=false;
            self->DataIO.CurUnpRead=0;
            self->DataIO.CurUnpWrite=0;
            self->DataIO.UnpFileCRC=self->archive->OldFormat ? 0 : 0xffffffff;
            self->DataIO.PackedCRC=0xffffffff;
            // self->DataIO.SetEncryption(0, NULL, NULL, false, self->archive->NewLhd.UnpVer>=36);
            self->DataIO.SetPackedSizeToRead(self->archive->NewLhd.FullPackSize);
            self->DataIO.SetFiles(self->archive, &unrar_dummy_output);
            self->DataIO.SetTestMode(false);
            self->DataIO.SetSkipUnpCRC(false);
            self->DataIO.SetTestMode(true); // We set this so that the Write method is not called on the output file by UnpWrite()
            self->Cmd.DllOpMode = RAR_EXTRACT;

            if (IsLink(self->archive->NewLhd.FileAttr)) {
                char LinkTarget[NM];
                int datasz = Min(self->archive->NewLhd.PackSize, NM-1);
                self->DataIO.UnpRead((byte *)LinkTarget, datasz);
                LinkTarget[datasz]=0;
                self->DataIO.UnpWrite((byte*)LinkTarget, datasz);
                self->archive->SeekToNext();
            } else if (self->archive->IsArcDir() || self->archive->NewLhd.FullUnpSize < 1) {
                self->archive->SeekToNext();
            } else {
                // Implementation from the ExtractCurrentFile() method in the unrar source code
                if (self->archive->NewLhd.Method == 0x30) {
                    Array<byte> Buffer(0x10000);
                    int64 DestUnpSize = self->archive->NewLhd.FullUnpSize;
                    uint Code = 0;
                    while (true)
                    {
                        Code = self->DataIO.UnpRead(&Buffer[0], Buffer.Size());
                        if (Code==0 || (int)Code==-1) break;
                        Code = (Code < DestUnpSize) ? Code:(uint)DestUnpSize;
                        self->DataIO.UnpWrite(&Buffer[0], Code);
                        if (DestUnpSize >= 0) DestUnpSize -= Code;
                    }
                } else {
                    self->Unp->SetDestSize(self->archive->NewLhd.FullUnpSize);
                    if (self->archive->NewLhd.UnpVer<=15)
                        self->Unp->DoUnpack(15,self->file_count>1 && self->archive->Solid);
                    else
                        self->Unp->DoUnpack(self->archive->NewLhd.UnpVer,(self->archive->NewLhd.Flags & LHD_SOLID)!=0);
                }
                self->archive->SeekToNext();
                bool ValidCRC = (self->archive->OldFormat && GET_UINT32(self->DataIO.UnpFileCRC)==GET_UINT32(self->archive->NewLhd.FileCRC)) ||
                    (!self->archive->OldFormat && GET_UINT32(self->DataIO.UnpFileCRC)==GET_UINT32(self->archive->NewLhd.FileCRC^0xffffffff));
                if (!ValidCRC) {
                    PyErr_SetString(UNRARError, "Invalid CRC for item");
                    return NULL;
                }
                // Comes from ProcessFile in dll.cpp
                while(self->archive->IsOpened() && self->archive->ReadHeader() != 0 && self->archive->GetHeaderType() == NEWSUB_HEAD) {
                    // Skip extra file information
                    self->archive->SeekToNext();
                }
                self->archive->Seek(self->archive->CurBlockPos, SEEK_SET);
            }
        } else {
            if (self->archive->Volume && self->archive->GetHeaderType() == FILE_HEAD && self->archive->NewLhd.Flags & LHD_SPLIT_AFTER) {
                PyErr_SetString(UNRARError, "This is a split RAR archive. Not supported.");
                return NULL;
            }
            self->archive->SeekToNext();
        }
    } catch(RAR_EXIT errcode) {
        handle_rar_error(errcode);
        return NULL;
    } catch (std::bad_alloc) {
        if (!PyErr_Occurred()) 
            PyErr_NoMemory();
        return NULL;
    }
    Py_RETURN_NONE;
}

static PyMethodDef RAR_methods[] = {
    {"current_item", (PyCFunction)RAR_current_item, METH_VARARGS,
     "current_item() -> Return the current item in this RAR file."
    },

    {"process_item", (PyCFunction)RAR_process_item, METH_VARARGS,
        "process_item(extract=False) -> Process the current item."
    },

    {NULL}  /* Sentinel */
};

static PyTypeObject RARArchiveType = { // {{{
    PyObject_HEAD_INIT(NULL)
    0,                         /*ob_size*/
    "unrar.RARArchive",            /*tp_name*/
    sizeof(RARArchive),      /*tp_basicsize*/
    0,                         /*tp_itemsize*/
    (destructor)RAR_dealloc, /*tp_dealloc*/
    0,                         /*tp_print*/
    0,                         /*tp_getattr*/
    0,                         /*tp_setattr*/
    0,                         /*tp_compare*/
    0,                         /*tp_repr*/
    0,                         /*tp_as_number*/
    0,                         /*tp_as_sequence*/
    0,                         /*tp_as_mapping*/
    0,                         /*tp_hash */
    0,                         /*tp_call*/
    0,                         /*tp_str*/
    0,                         /*tp_getattro*/
    0,                         /*tp_setattro*/
    0,                         /*tp_as_buffer*/
    Py_TPFLAGS_DEFAULT|Py_TPFLAGS_BASETYPE,        /*tp_flags*/
    "RARArchive",                  /* tp_doc */
    0,		               /* tp_traverse */
    0,		               /* tp_clear */
    0,		               /* tp_richcompare */
    0,		               /* tp_weaklistoffset */
    0,		               /* tp_iter */
    0,		               /* tp_iternext */
    RAR_methods,             /* tp_methods */
    0,             /* tp_members */
    RAR_getsetters,                         /* tp_getset */
    0,                         /* tp_base */
    0,                         /* tp_dict */
    0,                         /* tp_descr_get */
    0,                         /* tp_descr_set */
    0,                         /* tp_dictoffset */
    (initproc)RAR_init,      /* tp_init */
    0,                         /* tp_alloc */
    0,                 /* tp_new */
}; // }}}

// }}} End RARArchive


PyMODINIT_FUNC
initunrar(void) {
    PyObject *m;

    RARArchiveType.tp_new = PyType_GenericNew;
    if (PyType_Ready(&RARArchiveType) < 0)
        return;
 
    m = Py_InitModule3(
            "unrar", methods,
            "Support for reading RAR archives"
    );
    if (m == NULL) return;

    UNRARError = PyErr_NewException((char*)"unrar.UNRARError", NULL, NULL);
    if (UNRARError == NULL) return;
    PyModule_AddObject(m, "UNRARError", UNRARError);

    Py_INCREF(&RARArchiveType);
    PyModule_AddObject(m, "RARArchive", (PyObject *)&RARArchiveType);

} 



