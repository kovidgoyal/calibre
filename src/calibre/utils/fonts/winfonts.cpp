/*
:mod:`winfont` -- Pythonic interface to Windows font api
============================================================

.. module:: winfonts
    :platform: All
    :synopsis: Pythonic interface to the windows font routines

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2009

*/

#define _UNICODE
#define UNICODE
#define PY_SSIZE_T_CLEAN
#include <Windows.h>
#include <Strsafe.h>
#include <Python.h>
#include <new>

// Utils {{{
static wchar_t* unicode_to_wchar(PyObject *o) {
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

static PyObject* wchar_to_unicode(const wchar_t *o) {
    PyObject *ans;
    if (o == NULL) return NULL;
    ans = PyUnicode_FromWideChar(o, wcslen(o));
    if (ans == NULL) PyErr_NoMemory();
    return ans;
}

// }}}

// Enumerate font families {{{
struct EnumData {
    HDC hdc;
    PyObject *families;
};


static PyObject* logfont_to_dict(const ENUMLOGFONTEX *lf, const TEXTMETRIC *tm, DWORD font_type, HDC hdc) {
    PyObject *name, *full_name, *style, *script;
    LOGFONT f = lf->elfLogFont;

    name = wchar_to_unicode(f.lfFaceName);
    full_name = wchar_to_unicode(lf->elfFullName);
    style = wchar_to_unicode(lf->elfStyle);
    script = wchar_to_unicode(lf->elfScript);
    
    return Py_BuildValue("{s:N, s:N, s:N, s:N, s:O, s:O, s:O, s:O, s:l}",
        "name", name,
        "full_name", full_name,
        "style", style,
        "script", script,
        "is_truetype", (font_type & TRUETYPE_FONTTYPE) ? Py_True : Py_False,
        "is_italic", (tm->tmItalic != 0) ? Py_True : Py_False,
        "is_underlined", (tm->tmUnderlined != 0) ? Py_True : Py_False,
        "is_strikeout", (tm->tmStruckOut != 0) ? Py_True : Py_False,
        "weight", tm->tmWeight
    );
}

static int CALLBACK find_families_callback(const ENUMLOGFONTEX *lpelfe, const TEXTMETRIC *lpntme, DWORD font_type, LPARAM lParam) {
    struct EnumData *enum_data = reinterpret_cast<struct EnumData*>(lParam);
    PyObject *font = logfont_to_dict(lpelfe, lpntme, font_type, enum_data->hdc);
    if (font == NULL) return 0;
    PyList_Append(enum_data->families, font);

	return 1;
}

static PyObject* enum_font_families(PyObject *self, PyObject *args) {
    LOGFONTW logfont;
	HDC hdc;
    PyObject *families;
    struct EnumData enum_data;

	families = PyList_New(0);
    if (families == NULL) return PyErr_NoMemory();
    SecureZeroMemory(&logfont, sizeof(logfont));

    logfont.lfCharSet = DEFAULT_CHARSET;
    logfont.lfFaceName[0] = L'\0';

    hdc = GetDC(NULL);
    enum_data.hdc = hdc;
    enum_data.families = families;

    EnumFontFamiliesExW(hdc, &logfont, (FONTENUMPROC)find_families_callback,
					(LPARAM)(&enum_data), 0);
    ReleaseDC(NULL, hdc);

	return families;
}

// }}}

// font_data() {{{
static PyObject* font_data(PyObject *self, PyObject *args) {
    PyObject *ans = NULL, *italic, *pyname;
    LOGFONTW lf;
	HDC hdc;
    LONG weight;
    LPWSTR family = NULL;
	HGDIOBJ old_font = NULL;
    HFONT hf;
    DWORD sz;
    char *buf;

    SecureZeroMemory(&lf, sizeof(lf));

    if (!PyArg_ParseTuple(args, "OOl", &pyname, &italic, &weight)) return NULL;

    family = unicode_to_wchar(pyname);
    if (family == NULL) { Py_DECREF(ans); return NULL; }
    StringCchCopyW(lf.lfFaceName, LF_FACESIZE, family);
    free(family);

    lf.lfItalic = (PyObject_IsTrue(italic)) ? 1 : 0;
    lf.lfWeight = weight;
    lf.lfOutPrecision = OUT_TT_ONLY_PRECIS;

    hdc = GetDC(NULL);

    if ( (hf = CreateFontIndirect(&lf)) != NULL) {

        if ( (old_font = SelectObject(hdc, hf)) != NULL ) {
            sz = GetFontData(hdc, 0, 0, NULL, 0);
            if (sz != GDI_ERROR) {
                buf = (char*)calloc(sz, sizeof(char));

                if (buf != NULL) {
                    if (GetFontData(hdc, 0, 0, buf, sz) != GDI_ERROR) {
                        ans = PyBytes_FromStringAndSize(buf, sz);
                        if (ans == NULL) PyErr_NoMemory();
                    } else PyErr_SetString(PyExc_ValueError, "GDI Error");
                    free(buf);
                } else PyErr_NoMemory();
            } else PyErr_SetString(PyExc_ValueError, "GDI Error");

            SelectObject(hdc, old_font);
        } else PyErr_SetFromWindowsErr(0);
        DeleteObject(hf);
    } else PyErr_SetFromWindowsErr(0);

    ReleaseDC(NULL, hdc);

    return ans;
}
// }}}

static PyObject* add_font(PyObject *self, PyObject *args) {
    char *data;
    Py_ssize_t sz;
    DWORD num = 0;

    if (!PyArg_ParseTuple(args, "s#", &data, &sz)) return NULL;

    AddFontMemResourceEx(data, (DWORD)sz, NULL, &num);

    return Py_BuildValue("k", num);
}

static PyObject* add_system_font(PyObject *self, PyObject *args) {
    PyObject *name;
    LPWSTR path;
    int num;

    if (!PyArg_ParseTuple(args, "O", &name)) return NULL;
    path = unicode_to_wchar(name);
    if (path == NULL) return NULL;

    num = AddFontResource(path);
    if (num > 0)
        SendMessage(HWND_BROADCAST, WM_FONTCHANGE, 0, 0);
    free(path);
    return Py_BuildValue("i", num);
}

static PyObject* remove_system_font(PyObject *self, PyObject *args) {
    PyObject *name, *ok = Py_False;
    LPWSTR path;

    if (!PyArg_ParseTuple(args, "O", &name)) return NULL;
    path = unicode_to_wchar(name);
    if (path == NULL) return NULL;

    if (RemoveFontResource(path)) {
        SendMessage(HWND_BROADCAST, WM_FONTCHANGE, 0, 0);
        ok = Py_True;
    }
    free(path);
    return Py_BuildValue("O", ok);
}

static 
PyMethodDef winfonts_methods[] = {
    {"enum_font_families", enum_font_families, METH_VARARGS,
    "enum_font_families()\n\n"
        "Enumerate all regular (not italic/bold/etc. variants) font families on the system. Note there will be multiple entries for every family (corresponding to each charset of the font)."
    },

    {"font_data", font_data, METH_VARARGS,
    "font_data(family_name, italic, weight)\n\n"
        "Return the raw font data for the specified font."
    },

    {"add_font", add_font, METH_VARARGS,
    "add_font(data)\n\n"
        "Add the font(s) in the data (bytestring) to windows. Added fonts are always private. Returns the number of fonts added."
    },

    {"add_system_font", add_system_font, METH_VARARGS,
    "add_system_font(data)\n\n"
        "Add the font(s) in the specified file to the system font tables."
    },

    {"remove_system_font", remove_system_font, METH_VARARGS,
    "remove_system_font(data)\n\n"
        "Remove the font(s) in the specified file from the system font tables."
    },

    {NULL, NULL, 0, NULL}
};


CALIBRE_MODINIT_FUNC
initwinfonts(void) {
    PyObject *m;
    m = Py_InitModule3(
            "winfonts", winfonts_methods,
            "Windows font API"
    );
    if (m == NULL) return;

    PyModule_AddIntMacro(m, FW_DONTCARE);
    PyModule_AddIntMacro(m, FW_THIN);
    PyModule_AddIntMacro(m, FW_EXTRALIGHT);
    PyModule_AddIntMacro(m, FW_ULTRALIGHT);
    PyModule_AddIntMacro(m, FW_LIGHT);
    PyModule_AddIntMacro(m, FW_NORMAL);
    PyModule_AddIntMacro(m, FW_REGULAR);
    PyModule_AddIntMacro(m, FW_MEDIUM);
    PyModule_AddIntMacro(m, FW_SEMIBOLD);
    PyModule_AddIntMacro(m, FW_DEMIBOLD);
    PyModule_AddIntMacro(m, FW_BOLD);
    PyModule_AddIntMacro(m, FW_EXTRABOLD);
    PyModule_AddIntMacro(m, FW_ULTRABOLD);
    PyModule_AddIntMacro(m, FW_HEAVY);
    PyModule_AddIntMacro(m, FW_BLACK);
}

