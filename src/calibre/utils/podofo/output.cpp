/*
 * output.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"

using namespace PoDoFo;

#define NUKE(x) { Py_XDECREF(x); x = NULL; }
#define PODOFO_RAISE_ERROR(code) throw ::PoDoFo::PdfError(code, __FILE__, __LINE__)


class MyOutputDevice : public OutputStreamDevice {

    private:
        PyObject *tell_func;
        PyObject *seek_func;
        PyObject *read_func;
        PyObject *write_func;
        PyObject *flush_func;
        size_t written;

        void update_written() {
            size_t pos;
            pos = GetPosition();
            if (pos > written) written = pos;
        }

    public:
        MyOutputDevice(PyObject *file) : tell_func(0), seek_func(0), read_func(0), write_func(0), flush_func(0), written(0) {
            SetAccess(DeviceAccess::Write);
#define GA(f, a) { if((f = PyObject_GetAttrString(file, a)) == NULL) throw std::exception(); }
            GA(tell_func, "tell");
            GA(seek_func, "seek");
            GA(read_func, "read");
            GA(write_func, "write");
            GA(flush_func, "flush");
        }
        ~MyOutputDevice() {
            NUKE(tell_func); NUKE(seek_func); NUKE(read_func); NUKE(write_func); NUKE(flush_func);
        }

        size_t GetLength() const { return written; }

        long PrintVLen(const char* pszFormat, va_list args) {

            if( !pszFormat ) { PODOFO_RAISE_ERROR(PdfErrorCode::InvalidHandle); }

#ifdef _MSC_VER
            return _vscprintf(pszFormat, args) + 1;
#else
            return vsnprintf(NULL, 0, pszFormat, args) + 1;
#endif
        }

        void PrintV( const char* pszFormat, long lBytes, va_list args ) {
            char *buf;
            int res;

            if( !pszFormat ) { PODOFO_RAISE_ERROR(PdfErrorCode::InvalidHandle); }

            buf = new (std::nothrow) char[lBytes+1];
            if (buf == NULL) { PyErr_NoMemory(); throw std::exception(); }

            // Note: PyOS_vsnprintf produces broken output on windows
            res = vsnprintf(buf, lBytes, pszFormat, args);

            if (res < 0) {
                PyErr_SetString(PyExc_Exception, "Something bad happened while calling vsnprintf");
                delete[] buf;
                throw std::exception();
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
            PyObject *ret, *temp;
            char *buf = NULL;
            Py_ssize_t len = 0;

            if ((temp = PyLong_FromSize_t(lLen)) == NULL) throw std::exception();
            ret = PyObject_CallFunctionObjArgs(read_func, temp, NULL);
            NUKE(temp);
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

            throw std::exception();

        }

        void Seek(size_t offset) {
            PyObject *ret, *temp;
            if ((temp = PyLong_FromSize_t(offset)) == NULL) throw std::exception();
            ret = PyObject_CallFunctionObjArgs(seek_func, temp, NULL);
            NUKE(temp);
            if (ret == NULL) {
                if (PyErr_Occurred() == NULL)
                    PyErr_SetString(PyExc_Exception, "Failed to seek in python file object");
                throw std::exception();
            }
            Py_DECREF(ret);
        }

        size_t GetPosition() const {
            PyObject *ret;
            unsigned long ans;

            ret = PyObject_CallFunctionObjArgs(tell_func, NULL);
            if (ret == NULL) {
                if (PyErr_Occurred() == NULL)
                    PyErr_SetString(PyExc_Exception, "Failed to call tell() on python file object");
                throw std::exception();
            }
            if (!PyNumber_Check(ret)) {
                Py_DECREF(ret);
                PyErr_SetString(PyExc_Exception, "tell() method did not return a number");
                throw std::exception();
            }
            ans = PyLong_AsUnsignedLongMask(ret);
            Py_DECREF(ret);
            if (PyErr_Occurred() != NULL) throw std::exception();

            return static_cast<size_t>(ans);
        }

        bool Eof() const { return false; }

        void writeBuffer(const char* pBuffer, size_t lLen) {
            PyObject *ret, *temp = NULL;

            temp = PyBytes_FromStringAndSize(pBuffer, static_cast<Py_ssize_t>(lLen));
            if (temp == NULL) throw std::exception();

            ret = PyObject_CallFunctionObjArgs(write_func, temp, NULL);
            NUKE(temp);

            if (ret == NULL) {
                if (PyErr_Occurred() == NULL)
                    PyErr_SetString(PyExc_Exception, "Failed to call write() on python file object");
                throw std::exception();
            }
            Py_DECREF(ret);
            update_written();
        }

        void Flush() {
            Py_XDECREF(PyObject_CallFunctionObjArgs(flush_func, NULL));
        }

};


PyObject* pdf::write_doc(PdfMemDocument *doc, PyObject *f) {
    MyOutputDevice d(f);

    try {
        doc->Save(d, save_options);
        d.Flush();
    } catch(const PdfError & err) {
        podofo_set_exception(err); return NULL;
    } catch (...) {
        if (PyErr_Occurred() == NULL)
            PyErr_SetString(PyExc_Exception, "An unknown error occurred while trying to write the pdf to the file object");
        return NULL;
    }

    Py_RETURN_NONE;
}
