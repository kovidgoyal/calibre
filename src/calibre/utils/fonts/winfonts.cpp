/*
:mod:`fontconfig` -- Pythonic interface to Windows font api
============================================================

.. module:: fontconfig
    :platform: All
    :synopsis: Pythonic interface to the fontconfig library

.. moduleauthor:: Kovid Goyal <kovid@kovidgoyal.net> Copyright 2009

*/

#define UNICODE
#include <Windows.h>
#include <strsafe.h>
#include <vector>

using namespace std;

vector<BYTE> *get_font_data(HDC hdc) {
    DWORD sz;
	vector<BYTE> *data;
	sz = GetFontData(hdc, 0, 0, NULL, 0);
	data = new vector<BYTE>(sz);
	if (GetFontData(hdc, 0, 0, &((*data)[0]), sz) == GDI_ERROR) {
		delete data; data = NULL;
	}
	return data;

}

BOOL is_font_embeddable(ENUMLOGFONTEX *lpelfe) {
	HDC hdc;
	HFONT font;
	HFONT old_font = NULL;
	UINT sz;
	size_t i;
	LPOUTLINETEXTMETRICW metrics;
	BOOL ans = TRUE;
    hdc = GetDC(NULL);
    font = CreateFontIndirect(&lpelfe->elfLogFont);
	if (font != NULL) {
		old_font = SelectObject(hdc, font);
		sz = GetOutlineTextMetrics(hdc, 0, NULL);
		metrics = new OUTLINETEXTMETRICW[sz];
		if ( GetOutlineTextMetrics(hdc, sz, metrics) != 0) {
		    for ( i = 0; i < sz; i++) {
				if (metrics[i].otmfsType & 0x01) {
				    wprintf_s(L"Not embeddable: %s\n", 	lpelfe->elfLogFont.lfFaceName);
				    ans = FALSE; break;
				}
			}
		} else ans = FALSE;
		delete[] metrics;	
		DeleteObject(font);
		SelectObject(hdc, old_font);
	} else ans = FALSE;
	ReleaseDC(NULL, hdc);
    return ans;
}

int CALLBACK find_families_callback (
        ENUMLOGFONTEX    *lpelfe,   /* pointer to logical-font data */
        NEWTEXTMETRICEX  *lpntme,   /* pointer to physical-font data */
        int              FontType,  /* type of font */
        LPARAM           lParam     /* a combo box HWND */
        ) {
    size_t i;
	LPWSTR tmp;
	vector<LPWSTR> *families = (vector<LPWSTR>*)lParam;

    if (FontType & TRUETYPE_FONTTYPE) {
		for (i = 0; i < families->size(); i++) {
		    if (lstrcmp(families->at(i), lpelfe->elfLogFont.lfFaceName) == 0)
				return 1;
		}
		tmp = new WCHAR[LF_FACESIZE];
		swprintf_s(tmp, LF_FACESIZE, L"%s",  lpelfe->elfLogFont.lfFaceName);
		families->push_back(tmp);
    }

	return 1;
}


vector<LPWSTR>* find_font_families(void) {
    LOGFONTW logfont;
	HDC hdc;
	vector<LPWSTR> *families;

	families = new vector<LPWSTR>();
    SecureZeroMemory(&logfont, sizeof(logfont));

    logfont.lfCharSet = DEFAULT_CHARSET;
    logfont.lfPitchAndFamily = VARIABLE_PITCH | FF_DONTCARE;
    StringCchCopyW(logfont.lfFaceName, 2, L"\0");

    hdc = GetDC(NULL);
    EnumFontFamiliesExW(hdc, &logfont, (FONTENUMPROC)find_families_callback,
					(LPARAM)(families), 0);

    ReleaseDC(NULL, hdc);

	return families;
}

inline void free_families_vector(vector<LPWSTR> *v) {
	for (size_t i = 0; i < v->size(); i++) delete[] v->at(i);
	delete v;
}

#ifdef TEST

int main(int argc, char **argv) {
    vector<LPWSTR> *all_families;
	size_t i;

    all_families = find_font_families();

	for (i = 0; i < all_families->size(); i++) 
		wprintf_s(L"%s\n", all_families->at(i));

	free_families_vector(all_families);

    HDC hdc = GetDC(NULL);
	HFONT font = CreateFont(72,0,0,0,0,0,0,0,0,0,0,0,0,L"Verdana");
	HFONT old_font = SelectObject(hdc, font);
	vector<BYTE> *data = get_font_data(hdc);
	DeleteObject(font);
	SelectObject(hdc, old_font);
	ReleaseDC(NULL, hdc);
	if (data != NULL) printf("\nyay: %d\n", data->size());
	delete data;

    return 0;
}
#else

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#

static 
PyMethodDef fontconfig_methods[] = {
    {"find_font_families", fontconfig_find_font_families, METH_VARARGS,
    "find_font_families(allowed_extensions)\n\n"
    		"Find all font families on the system for fonts of the specified types. If no "
            "types are specified all font families are returned."
    },


    {NULL, NULL, 0, NULL}
};


extern "C" {
PyMODINIT_FUNC
initfontconfig(void) {
    PyObject *m;
    m = Py_InitModule3(
            "fontconfig", fontconfig_methods,
            "Find fonts."
    );
    if (m == NULL) return;
}
}

#endif
