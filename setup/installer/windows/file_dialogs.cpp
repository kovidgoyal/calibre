/*
 * file_dialogs.c
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <Windows.h>
#include <Shobjidl.h>
#include <stdio.h>
#include <string.h>

#define PRINTERR(x) fprintf(stderr, x); fflush(stderr);
#define REPORTERR(x) { PRINTERR(x); ret = 1; goto error; }
#define CALLCOM(x, err) hr = x; if(FAILED(hr)) REPORTERR(err)

int show_dialog(HWND parent, bool save_dialog, LPWSTR title) {
	int ret = 0;
	IFileDialog *pfd = NULL;
	IShellItem *psiResult = NULL;
	DWORD dwFlags;
	HRESULT hr = S_OK;
	hr = CoInitialize(NULL);
	if (FAILED(hr)) { PRINTERR("Failed to initialize COM"); return 1; }

	CALLCOM(CoCreateInstance(CLSID_FileOpenDialog, NULL, CLSCTX_INPROC_SERVER, (save_dialog ? IID_IFileSaveDialog : IID_IFileOpenDialog), reinterpret_cast<LPVOID*>(&pfd)), "Failed to create COM object for file dialog")
	CALLCOM(pfd->GetOptions(&dwFlags), "Failed to get options")
	dwFlags |= FOS_FORCEFILESYSTEM;
	CALLCOM(pfd->SetOptions(dwFlags), "Failed to set options")
	if (title != NULL) { CALLCOM(pfd->SetTitle(title), "Failed to set title") }
	hr = pfd->Show(parent);
	if (hr == HRESULT_FROM_WIN32(ERROR_CANCELLED)) goto error;
	if (FAILED(hr)) REPORTERR("Failed to show dialog")

	CALLCOM(pfd->GetResult(&psiResult), "Failed to get dialog result")

error:
	if(pfd) pfd->Release();
	CoUninitialize();
	return ret;
}

bool read_bytes(size_t sz, char* buf, bool allow_incomplete=false) {
	char *ptr = buf, *limit = buf + sz;
	while(limit > ptr && !feof(stdin) && !ferror(stdin)) {
		ptr += fread(ptr, 1, limit - ptr, stdin);
	}
	if (ferror(stdin)) { PRINTERR("Failed to read from stdin!"); return false; }
	if (ptr - buf != sz) { if (!allow_incomplete) PRINTERR("Truncated input!"); return false; }
	return true;
}

bool from_utf8(size_t sz, const char *src, LPWSTR* ans) {
	int asz = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, src, (int)sz, NULL, 0);
	if (!asz) { PRINTERR("Failed to get size of UTF-8 string"); return false; }
	*ans = (LPWSTR)calloc(asz+1, sizeof(wchar_t));
	if(*ans == NULL) { PRINTERR("Out of memory!"); return false; }
	asz = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, src, (int)sz, *ans, asz);
	if (!asz) { PRINTERR("Failed to convert UTF-8 string"); return false; }
	return true;
}

static char* rsbuf = NULL;

bool read_string(unsigned short sz, LPWSTR* ans) {
	if(rsbuf == NULL) {
		rsbuf = (char*)calloc(65537, sizeof(char));
		if(rsbuf == NULL) { PRINTERR("Out of memory!"); return false; }
	}
	memset(rsbuf, 0, 65537);
	if (!read_bytes(sz, rsbuf)) return false;
	if (!from_utf8(sz, rsbuf, ans)) return false;
	return true;
}

#define READ(x, y) if (!read_bytes((x), (y))) return 1;
#define CHECK_KEY(x) (key_size == sizeof(x) - 1 && memcmp(buf, x, sizeof(x) - 1) == 0)
#define READSTR(x) READ(sizeof(unsigned short), buf); if(!read_string(*((unsigned short*)buf), &x)) return 1;

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow) {
	char buf[257];
	size_t key_size = 0;
	HWND parent = NULL;
	bool save_dialog = false;
	unsigned short len = 0;
	LPWSTR title = NULL;

	while(!feof(stdin)) {
		memset(buf, 0, sizeof(buf));
		if(!read_bytes(1, buf, true)) { if (feof(stdin)) break; return 1;}
		key_size = (size_t)buf[0];
		READ(key_size, buf);
		if CHECK_KEY("HWND") {
			READ(sizeof(HWND), buf);
			if (sizeof(HWND) == 8) parent = (HWND)*((__int64*)buf);
			else if (sizeof(HWND) == 4) parent = (HWND)*((__int32*)buf);
			else { fprintf(stderr, "Unknown pointer size: %d", sizeof(HWND)); fflush(stderr); return 1;}
		}

		else if CHECK_KEY("TITLE") { READSTR(title) }

		else {
			PRINTERR("Unknown key");
			return 1;
		}
	}

	return show_dialog(parent, save_dialog, title);
}
