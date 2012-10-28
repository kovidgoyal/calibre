/*
:mod:`fontconfig` -- Pythonic interface to fontconfig
=====================================================

.. module:: fontconfig
    :platform: All
    :synopsis: Pythonic interface to the fontconfig library

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2009

*/

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdio.h>
#include <string.h>
#include <fontconfig.h>

static PyObject *
fontconfig_initialize(PyObject *self, PyObject *args) {
    FcChar8 *path;
    FcBool ok;
    FcConfig *config;
    PyThreadState *_save;

    if (!PyArg_ParseTuple(args, "z", &path))
		return NULL;
    if (path == NULL) {
        _save = PyEval_SaveThread();
        ok = FcInit();
        PyEval_RestoreThread(_save);
    } else {
        config = FcConfigCreate();
        if (config == NULL) return PyErr_NoMemory();
        _save = PyEval_SaveThread();
        ok = FcConfigParseAndLoad(config, path, FcTrue);
        if (ok) ok = FcConfigBuildFonts(config);
        if (ok) ok = FcConfigSetCurrent(config);
        PyEval_RestoreThread(_save);
        if (!ok) return PyErr_NoMemory();     
        ok = 1;
    }
    if (ok) Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static PyObject*
fontconfig_add_font_dir(PyObject *self, PyObject *args) {
    FcChar8 *path;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (FcConfigAppFontAddDir(NULL, path))
        Py_RETURN_TRUE;
    Py_RETURN_FALSE;
}

static void
fontconfig_cleanup_find(FcPattern *p, FcObjectSet *oset, FcFontSet *fs) {
    if (p != NULL) FcPatternDestroy(p);
    if (oset != NULL) FcObjectSetDestroy(oset);
    if (fs != NULL) FcFontSetDestroy(fs);
}


static PyObject *
fontconfig_find_font_families(PyObject *self, PyObject *args) {
    int i; 
    size_t flen;
    char *ext;
    Py_ssize_t l, j, extlen;
    FcBool ok;
    FcPattern *pat, *temp;
    FcObjectSet *oset;
    FcFontSet *fs;
    FcValue v, w;
    PyObject *ans, *exts, *t;

    ans = PyList_New(0);
    fs = NULL; oset = NULL; pat = NULL;

    if (ans == NULL) return PyErr_NoMemory();

    if (!PyArg_ParseTuple(args, "O", &exts))
		return NULL;

    if (!PySequence_Check(exts)) { 
        PyErr_SetString(PyExc_ValueError, "Must pass sequence of extensions");
        return NULL;
    }
    l = PySequence_Size(exts);


    pat = FcPatternCreate();
    if (pat == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 

    oset = FcObjectSetCreate();
    if (oset == NULL)  { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_FILE))  { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_FAMILY)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 

    fs = FcFontList(FcConfigGetCurrent(), pat, oset);
    if (fs == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 

    for (i = 0; i < fs->nfont; i++) {
        temp = fs->fonts[i];

        if (temp == NULL) continue;
        if (FcPatternGet(temp, FC_FILE, 0, &v) != FcResultMatch) continue;

        if (v.type == FcTypeString) {
            flen = strlen((char *)v.u.s);
            ok = FcFalse;
            if (l == 0) ok = FcTrue;
            for ( j = 0; j < l && !ok; j++) {
                ext = PyBytes_AS_STRING(PySequence_ITEM(exts, j));
                extlen = PyBytes_GET_SIZE(PySequence_ITEM(exts, j));
                ok = flen > extlen && extlen > 0 && 
                    PyOS_strnicmp(ext, ((char *)v.u.s) + (flen - extlen), extlen) == 0;
            }

            if (ok) {
                if (FcPatternGet(temp, FC_FAMILY, 0, &w) != FcResultMatch) continue;
                if (w.type != FcTypeString) continue;
                t = PyString_FromString((char *)w.u.s);
                if (t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
                if (PyList_Append(ans, t) != 0)
                    { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
            }
        }

    }
    fontconfig_cleanup_find(pat, oset, fs);
    Py_INCREF(ans);
    return ans;
}

static PyObject *
fontconfig_files_for_family(PyObject *self, PyObject *args) {
    char *family; int i;
    FcPattern *pat, *tp;
    FcObjectSet *oset;
    FcFontSet *fs;
    FcValue file, weight, fullname, style, slant, family2, width;
    PyObject *ans, *temp;

    if (!PyArg_ParseTuple(args, "es", "UTF-8", &family))
		return NULL;

    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    fs = NULL; oset = NULL; pat = NULL;

    pat = FcPatternBuild(0, FC_FAMILY, FcTypeString, family, (char *) 0);
    if (pat == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    PyMem_Free(family); family = NULL;

    oset = FcObjectSetCreate();
    if (oset == NULL)  { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_FILE))  { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_STYLE)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_SLANT)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_WEIGHT)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_WIDTH)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_FAMILY)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    if (!FcObjectSetAdd(oset, FC_FULLNAME)) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 

    fs = FcFontList(FcConfigGetCurrent(), pat, oset);
    if (fs == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 

    for (i = 0; i < fs->nfont; i++) {
        tp = fs->fonts[i];

        if (tp == NULL) continue;
        if (FcPatternGet(tp, FC_FILE, 0, &file) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_STYLE, 0, &style) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_WEIGHT, 0, &weight) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_WIDTH, 0, &width) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_SLANT, 0, &slant) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_FAMILY, 0, &family2) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_FULLNAME, 0, &fullname) != FcResultMatch) continue;

        temp = Py_BuildValue("{s:s, s:s, s:s, s:s, s:l, s:l, s:l}",
                "fullname", (char*)fullname.u.s,
                "path", (char*)file.u.s,
                "style", (char*)style.u.s,
                "family", (char*)family2.u.s,
                "weight", (long)weight.u.i,
                "slant", (long)slant.u.i,
                "width", (long)width.u.i
        );
        if (temp == NULL) { fontconfig_cleanup_find(pat, oset, fs); return NULL; }
        if (PyList_Append(ans, temp) != 0)
            { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
    }
    fontconfig_cleanup_find(pat, oset, fs);
    Py_INCREF(ans);
    return ans;
}

static PyObject *
fontconfig_match(PyObject *self, PyObject *args) {
    FcChar8 *namespec; int i;
    FcPattern *pat, *tp;
    FcObjectSet *oset;
    FcFontSet *fs, *fs2;
    FcValue file, weight, fullname, style, slant, family;
    FcResult res;
    PyObject *ans, *temp, *t, *all, *verbose;

    if (!PyArg_ParseTuple(args, "sOO", &namespec, &all, &verbose))
		return NULL;

    ans = PyList_New(0);
    if (ans == NULL) return PyErr_NoMemory();

    fs = NULL; oset = NULL; pat = NULL; fs2 = NULL;

    pat = FcNameParse(namespec);
    if (pat == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
    if (PyObject_IsTrue(verbose)) FcPatternPrint(pat);

    if (!FcConfigSubstitute(FcConfigGetCurrent(), pat, FcMatchPattern)) 
        { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); } 
    FcDefaultSubstitute(pat);

    fs = FcFontSetCreate();
    if (fs == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
    if (PyObject_IsTrue(all)) {
        fs2 = FcFontSort(FcConfigGetCurrent(), pat, FcTrue, NULL, &res);
        if (fs2 == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }

        for (i = 0; i < fs2->nfont; i++) {
            tp = fs2->fonts[i];
            if (tp == NULL) continue;
            tp = FcFontRenderPrepare(FcConfigGetCurrent(), pat, tp);
            if (tp == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
            if (!FcFontSetAdd(fs, tp)) 
                { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        }
        if (fs2 != NULL) FcFontSetDestroy(fs2);
    } else {
        tp = FcFontMatch(FcConfigGetCurrent(), pat, &res);
        if (tp == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        if (!FcFontSetAdd(fs, tp)) 
            { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
    }

    for (i = 0; i < fs->nfont; i++) {
        tp = fs->fonts[i];
        if (tp == NULL) continue;
        if (FcPatternGet(tp, FC_FILE, 0, &file) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_STYLE, 0, &style) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_WEIGHT, 0, &weight) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_SLANT, 0, &slant) != FcResultMatch) continue;
        if (FcPatternGet(tp, FC_FAMILY, 0, &family) != FcResultMatch) continue;
        if (FcPatternGet(tp, "fullname", 0, &fullname) != FcResultMatch) continue;

        temp = PyTuple_New(6);
        if(temp == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        t = PyBytes_FromString((char *)fullname.u.s);
        if(t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(temp, 0, t);
        t = PyBytes_FromString((char *)file.u.s);
        if(t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(temp, 1, t);
        t = PyBytes_FromString((char *)style.u.s);
        if(t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(temp, 2, t);
        t = PyBytes_FromString((char *)family.u.s);
        if(t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(temp, 3, t);
        t = PyInt_FromLong((long)weight.u.i);
        if(t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(temp, 4, t);
        t = PyInt_FromLong((long)slant.u.i);
        if(t == NULL) { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(temp, 5, t);
        if (PyList_Append(ans, temp) != 0)
            { fontconfig_cleanup_find(pat, oset, fs); return PyErr_NoMemory(); }

    }
    fontconfig_cleanup_find(pat, oset, fs);
    Py_INCREF(ans);
    return ans;
}



static 
PyMethodDef fontconfig_methods[] = {
    {"initialize", fontconfig_initialize, METH_VARARGS,
    "initialize(path_to_config_file)\n\n"
    		"Initialize the library. If path to config file is specified it is used instead of the "
            "default configuration. Returns True iff the initialization succeeded."
    },

    {"find_font_families", fontconfig_find_font_families, METH_VARARGS,
    "find_font_families(allowed_extensions)\n\n"
    		"Find all font families on the system for fonts of the specified types. If no "
            "types are specified all font families are returned."
    },

    {"files_for_family", fontconfig_files_for_family, METH_VARARGS,
    "files_for_family(family, normalize)\n\n"
    		"Find all the variants in the font family `family`. "
            "Returns a list of tuples. Each tuple is of the form "
            "(fullname, path, style, family, weight, slant). "
    },

    {"match", fontconfig_match, METH_VARARGS,
    "match(namespec,all,verbose)\n\n"
    		"Find all system fonts that match namespec, in decreasing order "
            "of closeness. "
            "Returns a list of tuples. Each tuple is of the form "
            "(fullname, path, style, family, weight, slant). "

    },

    {"add_font_dir", fontconfig_add_font_dir, METH_VARARGS,
    "add_font_dir(path_to_dir)\n\n"
    		"Add the fonts in the specified directory to the list of application specific fonts."
    },

    {NULL, NULL, 0, NULL}
};



PyMODINIT_FUNC
initfontconfig(void) {
    PyObject *m;
    m = Py_InitModule3(
            "fontconfig", fontconfig_methods,
            "Find fonts."
    );
    if (m == NULL) return;

    PyModule_AddIntMacro(m, FC_WEIGHT_THIN);
    PyModule_AddIntMacro(m, FC_WEIGHT_EXTRALIGHT);
    PyModule_AddIntMacro(m, FC_WEIGHT_ULTRALIGHT);
    PyModule_AddIntMacro(m, FC_WEIGHT_LIGHT);
    PyModule_AddIntMacro(m, FC_WEIGHT_BOOK);
    PyModule_AddIntMacro(m, FC_WEIGHT_REGULAR);
    PyModule_AddIntMacro(m, FC_WEIGHT_NORMAL);
    PyModule_AddIntMacro(m, FC_WEIGHT_MEDIUM);
    PyModule_AddIntMacro(m, FC_WEIGHT_DEMIBOLD);
    PyModule_AddIntMacro(m, FC_WEIGHT_SEMIBOLD);
    PyModule_AddIntMacro(m, FC_WEIGHT_BOLD);
    PyModule_AddIntMacro(m, FC_WEIGHT_EXTRABOLD);
    PyModule_AddIntMacro(m, FC_WEIGHT_ULTRABOLD);
    PyModule_AddIntMacro(m, FC_WEIGHT_BLACK);
    PyModule_AddIntMacro(m, FC_WEIGHT_HEAVY);
    PyModule_AddIntMacro(m, FC_WEIGHT_EXTRABLACK);
    PyModule_AddIntMacro(m, FC_WEIGHT_ULTRABLACK);

    PyModule_AddIntMacro(m, FC_SLANT_ROMAN);
    PyModule_AddIntMacro(m, FC_SLANT_ITALIC);
    PyModule_AddIntMacro(m, FC_SLANT_OBLIQUE);

    PyModule_AddIntMacro(m, FC_WIDTH_ULTRACONDENSED);
    PyModule_AddIntMacro(m, FC_WIDTH_EXTRACONDENSED);
    PyModule_AddIntMacro(m, FC_WIDTH_CONDENSED);
    PyModule_AddIntMacro(m, FC_WIDTH_SEMICONDENSED);
    PyModule_AddIntMacro(m, FC_WIDTH_NORMAL);
    PyModule_AddIntMacro(m, FC_WIDTH_SEMIEXPANDED);
    PyModule_AddIntMacro(m, FC_WIDTH_EXPANDED);
    PyModule_AddIntMacro(m, FC_WIDTH_EXTRAEXPANDED);
    PyModule_AddIntMacro(m, FC_WIDTH_ULTRAEXPANDED);

#
}

