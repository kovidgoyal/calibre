/**
 * Copyright 2009 Kovid Goyal <kovid@kovidgoyal.net>
 * License: GNU GPL v2+
 */



#ifndef PDF2XML
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#endif

#include "reflow.h"

using namespace std;
using namespace calibre_reflow;

#ifndef PDF2XML

extern "C" {

    static PyObject *
    pdfreflow_reflow(PyObject *self, PyObject *args) {
        char *pdfdata;
        Py_ssize_t size;

        if (!PyArg_ParseTuple(args, "s#", &pdfdata, &size))
            return NULL;

        try {
            Reflow reflow(pdfdata, static_cast<std::ifstream::pos_type>(size));
            reflow.render();
        } catch (std::exception &e) {
            PyErr_SetString(PyExc_RuntimeError, e.what()); return NULL;
        } catch (...) {
            PyErr_SetString(PyExc_RuntimeError,
                    "Unknown exception raised while rendering PDF"); return NULL;
        }

        Py_RETURN_NONE;
    }

    static PyObject *
    pdfreflow_get_metadata(PyObject *self, PyObject *args) {
        char *pdfdata;
        Py_ssize_t size;
        map<string,string> info;
        PyObject *cover;
        PyObject *ans = PyDict_New();

        if (!ans) return PyErr_NoMemory();

        if (!PyArg_ParseTuple(args, "s#O", &pdfdata, &size, &cover))
            return NULL;

        Reflow *reflow = NULL;
        try {
            reflow = new Reflow(pdfdata, size);
            info = reflow->get_info();
            if (PyObject_IsTrue(cover)) {
                if (reflow->numpages() > 0) {
                    vector<char> *data = reflow->render_first_page();
                    if (data && data->size() > 0) {
                        PyObject *d = PyBytes_FromStringAndSize(&((*data)[0]), data->size());
                        delete data;
                        if (d == NULL) {delete reflow; return PyErr_NoMemory();}
                        if (PyDict_SetItemString(ans, "cover", d) == -1) {delete reflow; return NULL;}
                        Py_XDECREF(d);
                    }
                } else {
                    if (PyDict_SetItemString(ans, "cover", Py_None) == -1) {delete reflow; return NULL;}
                }
            }
        } catch (std::exception &e) {
            PyErr_SetString(PyExc_RuntimeError, e.what()); delete reflow; return NULL;
        } catch (...) {
            PyErr_SetString(PyExc_RuntimeError,
                    "Unknown exception raised while getting metadata from PDF"); delete reflow; return NULL;
        }
        delete reflow; reflow = NULL;


        for (map<string,string>::const_iterator it = info.begin() ; it != info.end(); it++ ) {
            PyObject *key = PyUnicode_Decode((*it).first.c_str(), (*it).first.size(), "UTF-8", "replace");
            if (!key) return NULL;
            PyObject *val = PyUnicode_Decode((*it).second.c_str(), (*it).second.size(), "UTF-8", "replace");
            if (!val) return NULL;
            if (PyDict_SetItem(ans, key, val) == -1) return NULL;
            Py_XDECREF(key); Py_XDECREF(val);
        }
        return ans;
    }

    static PyObject *
    pdfreflow_get_numpages(PyObject *self, PyObject *args) {
        char *pdfdata;
        int num = 0;
        Py_ssize_t size;
        map<string,string> info;

        if (!PyArg_ParseTuple(args, "s#", &pdfdata, &size))
            return NULL;

        Reflow *reflow = NULL;
        try {
            reflow = new Reflow(pdfdata, size);
            num = reflow->numpages();
        } catch (std::exception &e) {
            PyErr_SetString(PyExc_RuntimeError, e.what()); delete reflow; return NULL;
        } catch (...) {
            PyErr_SetString(PyExc_RuntimeError,
                    "Unknown exception raised while getting metadata from PDF"); delete reflow; return NULL;
        }

        delete reflow; reflow = NULL;
        return Py_BuildValue("i", num);
    }


    static PyObject *
    pdfreflow_set_metadata(PyObject *self, PyObject *args) {
        char *pdfdata;
        Py_ssize_t size;
        PyObject *info;

        if (!PyArg_ParseTuple(args, "s#O", &pdfdata, &size, &info))
            return NULL;

        if (!PyDict_Check(info)) {
            PyErr_SetString(PyExc_ValueError, "Info object must be a dictionary.");
            return NULL;
        }

        char Title[10] = "Title", Author[10] = "Author", Keywords[10] = "Keywords";
        char *keys[3] = { Title, Author, Keywords };
        map<char *, char *> pinfo;
        PyObject *val = NULL, *utf8 = NULL;

        for (int i = 0; i < 3; i++) {
            val = PyDict_GetItemString(info, keys[i]);
            if (!val || !PyUnicode_Check(val)) continue;
            utf8 = PyUnicode_AsUTF8String(val);
            if (!utf8) continue;
            pinfo[keys[i]] = PyString_AS_STRING(utf8);
        }

        PyObject *ans = NULL;
        try {
            Reflow reflow(pdfdata, static_cast<std::ifstream::pos_type>(size));
            if (reflow.is_locked()) {
                PyErr_SetString(PyExc_ValueError, "Setting metadata not possible in encrypeted PDFs");
                return NULL;
            }
            string result = reflow.set_info(pinfo);
            ans = PyString_FromStringAndSize(result.c_str(), result.size());
        } catch (std::exception &e) {
            PyErr_SetString(PyExc_RuntimeError, e.what()); return NULL;
        } catch (...) {
            PyErr_SetString(PyExc_RuntimeError,
                    "Unknown exception raised while getting metadata from PDF"); return NULL;
        }
        return ans;
    }

    static 
    PyMethodDef pdfreflow_methods[] = {
        {"reflow", pdfreflow_reflow, METH_VARARGS,
        "reflow(pdf_data)\n\n"
                "Reflow the specified PDF."
        },
        {"get_metadata", pdfreflow_get_metadata, METH_VARARGS,
        "get_metadata(pdf_data, cover)\n\n"
                "Get metadata and (optionally) cover from the specified PDF."
        },
        {"set_metadata", pdfreflow_set_metadata, METH_VARARGS,
        "get_metadata(info_dict)\n\n"
                "Set metadata in the specified PDF. Currently broken."
        },
        {"get_numpages", pdfreflow_get_numpages, METH_VARARGS,
        "get_numpages(pdf_data)\n\n"
                "Get number of pages in the PDF."
        },

        {NULL, NULL, 0, NULL}
    };


    PyMODINIT_FUNC
    initpdfreflow(void) 
    {
        PyObject* m;

        m = Py_InitModule3("pdfreflow", pdfreflow_methods,
                        "Reflow a PDF file");

        if (m == NULL) return;

    }
}


#else

int main(int argc, char **argv) {
    char *memblock;
    ifstream::pos_type size;
    int ret = 0;
    map<string,string> info;
    Reflow *reflow = NULL;


    if (argc != 2)  {
        cerr << "Usage: " << argv[0] << " file.pdf" << endl;
        return 1;
    }

    ifstream file (argv[1], ios::in|ios::binary|ios::ate);
    if (file.is_open()) {
        size = file.tellg();
        memblock = new char[size];
        file.seekg (0, ios::beg);
        file.read (memblock, size);
        file.close();
    } else {
        cerr << "Unable to read from: " << argv[1] << endl;
        return 1;
    }

    try {
        reflow = new Reflow(memblock, size);
        info = reflow->get_info();
        for (map<string,string>::const_iterator it = info.begin() ; it != info.end(); it++ ) {
            cout << (*it).first << " : " << (*it).second << endl;
        }
        //reflow->render();
        vector<char> *data = reflow->render_first_page();
        ofstream file("cover.png", ios::binary);
        file.write(&((*data)[0]), data->size());
        delete data;
        file.close();
    } catch(exception &e) {
        cerr << e.what() << endl;
        ret = 1;
    }
    delete reflow;
    delete[] memblock;
    return ret;
}
#endif
