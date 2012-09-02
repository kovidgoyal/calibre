/*
 * output.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace PoDoFo;

class pyerr : public std::exception {
};

class OutputDevice : public PdfOutputDevice {

    private:
        PyObject *file;
        size_t written;

        void update_written() {
            size_t pos;
            pos = Tell();
            if (pos > written) written = pos;
        }

    public:
        OutputDevice(PyObject *f) : file(f), written(0) { Py_XINCREF(file); }
        ~OutputDevice() { Py_XDECREF(file); file = NULL; }

        size_t GetLength() const { return written; }

        long PrintVLen(const char* pszFormat, va_list args) {

            if( !pszFormat ) { PODOFO_RAISE_ERROR( ePdfError_InvalidHandle ); }

#ifdef _MSC_VER
            return _vscprintf(pszFormat, args);
#else
            char *buf;
            int res, len=1024;
            while(true) {
                buf = new (std::nothrow) char[len];
                if (buf == NULL) { PyErr_NoMemory(); throw pyerr(); }
                res = vsnprintf(buf, len, pszFormat, args);
                delete[] buf;
                if (res >= 0) return res + 1;
                len *= 2;
            }
#endif
        }

        void PrintV( const char* pszFormat, long lBytes, va_list args ) {
            char *buf;
            int res;

            if( !pszFormat ) { PODOFO_RAISE_ERROR( ePdfError_InvalidHandle ); }

            buf = new (std::nothrow) char[lBytes+1];
            if (buf == NULL) { PyErr_NoMemory(); throw pyerr(); }
            
            // Note: PyOS_vsnprintf produces broken output on windows
            res = vsnprintf(buf, lBytes, pszFormat, args);

            if (res < 0) {
                PyErr_SetString(PyExc_Exception, "Something bad happened while calling vsnprintf");
                delete[] buf;
                throw pyerr();
            }

            Write(buf, static_cast<size_t>(res));
            delete[] buf;
        }

        void Print( const char* pszFormat, ... )
        {
            va_list args;
            long lBytes;

            va_start( args, pszFormat );
            lBytes = PrintVLen(pszFormat, args);
            va_end( args );

            va_start( args, pszFormat );
            PrintV(pszFormat, lBytes, args);
            va_end( args );
        }

        size_t Read( char* pBuffer, size_t lLen ) {
            PyObject *ret;
            char *buf = NULL;
            Py_ssize_t len = 0;

            ret = PyObject_CallMethod(file, (char*)"read", (char*)"n", static_cast<Py_ssize_t>(lLen));
            if (ret != NULL) {
                if (PyBytes_AsStringAndSize(ret, &buf, &len) != -1) {
                    memcpy(pBuffer, buf, len);
                    Py_DECREF(ret);
                    return static_cast<size_t>(len);
                }
                Py_DECREF(ret);
            }

            if (PyErr_Occurred() == NULL)
                PyErr_SetString(PyExc_Exception, "Failed to read data from python file object");

            throw pyerr();

        }

        void Seek(size_t offset) {
            PyObject *ret;
            ret = PyObject_CallMethod(file, (char*)"seek", (char*)"n", static_cast<Py_ssize_t>(offset));
            if (ret == NULL) {
                if (PyErr_Occurred() == NULL)
                    PyErr_SetString(PyExc_Exception, "Failed to seek in python file object");
                throw pyerr();
            }
            Py_DECREF(ret);
        }

        size_t Tell() const {
            PyObject *ret;
            unsigned long ans;

            ret = PyObject_CallMethod(file, (char*)"tell", NULL);
            if (ret == NULL) {
                if (PyErr_Occurred() == NULL)
                    PyErr_SetString(PyExc_Exception, "Failed to call tell() on python file object");
                throw pyerr();
            }
            if (!PyNumber_Check(ret)) {
                Py_DECREF(ret);
                PyErr_SetString(PyExc_Exception, "tell() method did not return a number");
                throw pyerr();
            }
            ans = PyInt_AsUnsignedLongMask(ret);
            Py_DECREF(ret);
            if (PyErr_Occurred() != NULL) throw pyerr();

            return static_cast<size_t>(ans);
        }

        void Write(const char* pBuffer, size_t lLen) {
            PyObject *ret;

            ret = PyObject_CallMethod(file, (char*)"write", (char*)"s#", pBuffer, (int)lLen);
            if (ret == NULL) {
                if (PyErr_Occurred() == NULL)
                    PyErr_SetString(PyExc_Exception, "Failed to call write() on python file object");
                throw pyerr();
            }
            Py_DECREF(ret);
            update_written();
        }

        void Flush() {
            Py_XDECREF(PyObject_CallMethod(file, (char*)"flush", NULL));
        }

};


PyObject* pdf::write_doc(PdfMemDocument *doc, PyObject *f) {
    OutputDevice d(f);

    try {
        doc->Write(&d);
    } catch(const PdfError & err) {
        podofo_set_exception(err); return NULL;
    } catch (...) {
        if (PyErr_Occurred() == NULL) 
            PyErr_SetString(PyExc_Exception, "An unknown error occurred while trying to write the pdf to the file object");
        return NULL;
    }

    Py_RETURN_NONE;
}

