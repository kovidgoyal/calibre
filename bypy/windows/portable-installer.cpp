#ifndef UNICODE
#define UNICODE
#endif

#ifndef _UNICODE
#define _UNICODE
#endif

#include <Windows.h>
#include <Shlobj.h>
#include <Shlwapi.h>
#include <Shellapi.h>
#include <Psapi.h>
#include <wchar.h>
#include <stdio.h>
#include <io.h>
#include <sys/types.h>
#include <sys/stat.h>

#include <easylzma/decompress.h>
#include "XUnzip.h"

#define BUFSIZE 4096

// Error handling {{{

static void show_error(LPCWSTR msg) {
    MessageBeep(MB_ICONERROR);
    MessageBox(NULL, msg, L"Error", MB_OK|MB_ICONERROR);
}

static void show_detailed_error(LPCWSTR preamble, LPCWSTR msg, int code) {
    LPWSTR buf;
    buf = (LPWSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(WCHAR)*
            (wcslen(msg) + wcslen(preamble) + 80));

    _snwprintf_s(buf,
        LocalSize(buf) / sizeof(WCHAR), _TRUNCATE,
        L"%s\r\n  %s (Error Code: %d)\r\n",
        preamble, msg, code);

    show_error(buf);
    LocalFree(buf);
}

static void show_zip_error(LPCWSTR preamble, LPCWSTR msg, ZRESULT code) {
    LPWSTR buf;
    char msgbuf[1024] = {0};

    FormatZipMessage(code, msgbuf, 1024);

    buf = (LPWSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(WCHAR)*
            (wcslen(preamble) + wcslen(msg) + 1100));

    _snwprintf_s(buf,
        LocalSize(buf) / sizeof(WCHAR), _TRUNCATE,
        L"%s\r\n  %s (Error: %S)\r\n",
        preamble, msg, msgbuf);

    show_error(buf);
    LocalFree(buf);
}

static void show_last_error(LPCWSTR preamble) {
    WCHAR *msg = NULL;
    DWORD dw = GetLastError();

    FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER |
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        dw,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPWSTR)&msg,
        0, NULL );

    show_detailed_error(preamble, msg, (int)dw);
}

// }}}

// Load, decompress and extract data {{{

static BOOL load_data(LPVOID *data, DWORD *sz) {
    HRSRC rsrc;
    HGLOBAL h;

    rsrc = FindResourceW(NULL, L"extra", L"extra");
    if (rsrc == NULL) { show_last_error(L"Failed to find portable data in exe"); return false; }

    h = LoadResource(NULL, rsrc);
    if (h == NULL) { show_last_error(L"Failed to load portable data from exe"); return false; }

    *data = LockResource(h);
    if (*data == NULL) { show_last_error(L"Failed to lock portable data in exe"); return false; }

    *sz = SizeofResource(NULL, rsrc);
    if (sz == 0) { show_last_error(L"Failed to get size of portable data in exe"); return false; }

    return true;
}

static BOOL unzip(HZIP zipf, int nitems, IProgressDialog *pd) {
    int i = 0;
    ZRESULT res;
    ZIPENTRYW ze;

    for (i = 0; i < nitems; i++) {
        res = GetZipItem(zipf, i, &ze);
        if (res != ZR_OK) { show_zip_error(L"Failed to get zip item", L"", res); return false;}

        res = UnzipItem(zipf, i, ze.name, 0, ZIP_FILENAME);
        if (res != ZR_OK) { CloseZip(zipf); show_zip_error(L"Failed to extract zip item (is your disk full?):", ze.name, res); return false;}

        pd->SetLine(2, ze.name, true, NULL);
        pd->SetProgress(i, nitems);
    }

    CloseZip(zipf);

    return true;
}

static HANDLE temp_file(LPWSTR name) {
    UINT res;
    HANDLE h;

    res = GetTempFileNameW(L".", L"portable_data", 0, name);

    if (res == 0) { show_last_error(L"Failed to create temporary file to decompress portable data"); return INVALID_HANDLE_VALUE; }

    h = CreateFile(name, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) { show_last_error(L"Failed to open temp file to decompress portable data"); }
    return h;

}

struct DataStream
{
    const unsigned char *in_data;
    size_t in_len;

    HANDLE out;
    IProgressDialog *pd;
};

static int
input_callback(void *ctx, void *buf, size_t * size)
{
    size_t rd = 0;
    struct DataStream * ds = (struct DataStream *) ctx;

    rd = (ds->in_len < *size) ? ds->in_len : *size;

    if (rd > 0) {
        memcpy(buf, (void*) ds->in_data, rd);
        ds->in_data += rd;
        ds->in_len -= rd;
    }

    *size = rd;

    return 0;
}

static int output_error_shown = 0;

static size_t
output_callback(void *ctx, const void *buf, size_t size)
{
    struct DataStream * ds = (struct DataStream *) ctx;
    DWORD written = 0;

    if (size > 0) {
        if (!WriteFile(ds->out, buf, size, &written, NULL)) {
            show_last_error(L"Failed to write uncompressed data to temp file");
            output_error_shown = 1;
            return 0;
        }
        written = SetFilePointer(ds->out, 0, NULL, FILE_CURRENT);
        ds->pd->SetProgress(written, UNCOMPRESSED_SIZE);
    }

    return size;
}

static BOOL decompress(LPVOID src, DWORD src_sz, HANDLE out, IProgressDialog *pd) {
    elzma_decompress_handle h;
    struct DataStream ds;
    int rc;

    h = elzma_decompress_alloc();

    if (h == NULL) { show_error(L"Out of memory"); return false; }

    ds.in_data = (unsigned char*)src;
    ds.in_len = src_sz;
    ds.out = out;
    ds.pd = pd;

    rc = elzma_decompress_run(h, input_callback, (void *) &ds, output_callback,
            (void *) &ds, ELZMA_lzip);

    if (rc != ELZMA_E_OK) {
        if (!output_error_shown) show_detailed_error(L"Failed to decompress portable data", L"", rc);
        elzma_decompress_free(&h);
        return false;
    }

    elzma_decompress_free(&h);

    return true;
}

static BOOL extract(LPVOID cdata, DWORD csz) {
    HANDLE h;
    WCHAR tempnam[MAX_PATH+1] = {0};
    BOOL ret = true;
    HZIP zipf;
    ZIPENTRYW ze;
    ZRESULT res;
    int nitems;
    HRESULT hr;
    IProgressDialog *pd = NULL;

    hr = CoCreateInstance(CLSID_ProgressDialog, NULL,
            CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&pd));

    if (FAILED(hr)) { show_error(L"Failed to create progress dialog"); return false; }
    pd->SetTitle(L"Extracting Calibre Portable");
    pd->SetLine(1, L"Decompressing data...", true, NULL);

    h = temp_file(tempnam);
    if (h == INVALID_HANDLE_VALUE) return false;

    pd->StartProgressDialog(NULL, NULL, PROGDLG_NORMAL | PROGDLG_AUTOTIME | PROGDLG_NOCANCEL, NULL);
    if (!decompress(cdata, csz, h, pd)) { ret = false; goto end; }
    SetFilePointer(h, 0, NULL, FILE_BEGIN);
    zipf = OpenZip(h, 0, ZIP_HANDLE);
    if (zipf == 0) { show_last_error(L"Failed to open zipped portable data"); ret = false; goto end; }

    res = GetZipItem(zipf, -1, &ze);
    if (res != ZR_OK) { show_zip_error(L"Failed to get count of items in portable data", L"", res); ret = false; goto end;}
    nitems = ze.index;

    pd->SetLine(1, L"Copying files...", true, NULL);
    if (!unzip(zipf, nitems, pd)) { ret = false; goto end; }
end:
    pd->StopProgressDialog();
    pd->Release();
    CloseHandle(h);
    DeleteFile(tempnam);
    return ret;
}

// }}}

// Find calibre portable directory and install/upgrade into it {{{

static BOOL directory_exists( LPCWSTR path )
{
  if( _waccess_s( path, 0 ) == 0 )
  {
    struct _stat status;
    _wstat( path, &status );
    return (status.st_mode & S_IFDIR) != 0;
  }

  return FALSE;
}

static BOOL file_exists( LPCWSTR path )
{
  if( _waccess_s( path, 0 ) == 0 )
  {
    struct _stat status;
    _wstat( path, &status );
    return (status.st_mode & S_IFREG) != 0;
  }

  return FALSE;
}

static LPWSTR get_directory_from_user() {
    WCHAR name[MAX_PATH+1] = {0};
    LPWSTR path = NULL;
    PIDLIST_ABSOLUTE ret;

    path = (LPWSTR)calloc(2*MAX_PATH, sizeof(WCHAR));
    if (path == NULL) { show_error(L"Out of memory"); return NULL; }

    int image = 0;
    BROWSEINFO bi = { NULL, NULL, name,
        L"Select the folder where you want to install or update Calibre Portable",
        BIF_RETURNONLYFSDIRS | BIF_DONTGOBELOWDOMAIN | BIF_USENEWUI,
        NULL, NULL, image };

    ret = SHBrowseForFolder(&bi);
    if (ret == NULL) {
        return NULL;
    }

    if (!SHGetPathFromIDList(ret, path)) {
        show_detailed_error(L"The selected folder is not valid: ", name, 0);
        return NULL;
    }

    return path;

}

static bool is_dots(LPCWSTR name) {
    return wcscmp(name, L".") == 0 || wcscmp(name, L"..") == 0;
}

static bool rmtree(LPCWSTR path) {
    SHFILEOPSTRUCTW op;
    WCHAR buf[4*MAX_PATH + 2] = {0};

    if (GetFullPathName(path, 4*MAX_PATH, buf, NULL) == 0) return false;

    op.hwnd = NULL;
    op.wFunc = FO_DELETE;
    op.pFrom = buf;
    op.pTo = NULL;
    op.fFlags = FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT | FOF_NOCONFIRMMKDIR;
    op.fAnyOperationsAborted = false;
    op.hNameMappings = NULL;
    op.lpszProgressTitle = NULL;

    return SHFileOperationW(&op) == 0;
}

static BOOL find_portable_dir(LPCWSTR base, LPWSTR *result, BOOL *existing) {
    WCHAR buf[4*MAX_PATH] = {0};

    _snwprintf_s(buf, 4*MAX_PATH, _TRUNCATE, L"%s\\calibre-portable.exe", base);
    *existing = true;

    if (file_exists(buf)) {
        *result = _wcsdup(base);
        if (*result == NULL) { show_error(L"Out of memory"); return false; }
        return true;
    }

    WIN32_FIND_DATA fdFile;
    HANDLE hFind = NULL;
    _snwprintf_s(buf, 4*MAX_PATH, _TRUNCATE, L"%s\\*", base);

    if((hFind = FindFirstFileEx(buf, FindExInfoStandard, &fdFile, FindExSearchLimitToDirectories, NULL, 0)) != INVALID_HANDLE_VALUE) {
        do {
            if(is_dots(fdFile.cFileName)) continue;

            if(fdFile.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                _snwprintf_s(buf, 4*MAX_PATH, _TRUNCATE, L"%s\\%s\\calibre-portable.exe", base, fdFile.cFileName);
                if (file_exists(buf)) {
                    *result = _wcsdup(buf);
                    if (*result == NULL) { show_error(L"Out of memory"); return false; }
                    PathRemoveFileSpec(*result);
                    FindClose(hFind);
                    return true;
                }
            }
        } while(FindNextFile(hFind, &fdFile));
        FindClose(hFind);
    }

    *existing = false;
    _snwprintf_s(buf, 4*MAX_PATH, _TRUNCATE, L"%s\\Calibre Portable", base);
    if (!CreateDirectory(buf, NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        show_last_error(L"Failed to create Calibre Portable folder");
        return false;
    }
    *result = _wcsdup(buf);
    if (*result == NULL) { show_error(L"Out of memory"); return false; }

    return true;
}

static LPWSTR make_unpack_dir() {
    WCHAR buf[4*MAX_PATH] = {0};
    LPWSTR ans = NULL;

    if (directory_exists(L"_unpack_calibre_portable"))
        rmtree(L"_unpack_calibre_portable");

    if (!CreateDirectory(L"_unpack_calibre_portable", NULL) && GetLastError() != ERROR_ALREADY_EXISTS) {
        show_last_error(L"Failed to create temporary folder to unpack into");
        return ans;
    }

    if (!GetFullPathName(L"_unpack_calibre_portable", 4*MAX_PATH, buf, NULL)) {
        show_last_error(L"Failed to resolve path");
        return NULL;
    }

    ans = _wcsdup(buf);
    if (ans == NULL) show_error(L"Out of memory");
    return ans;

}

static BOOL move_program() {
    if (MoveFileEx(L"Calibre Portable\\calibre-portable.exe",
                L"..\\calibre-portable.exe", MOVEFILE_REPLACE_EXISTING) == 0) {
        show_last_error(L"Failed to move calibre-portable.exe, make sure calibre is not running");
        return false;
    }
    if (MoveFileEx(L"Calibre Portable\\ebook-viewer-portable.exe",
                L"..\\ebook-viewer-portable.exe", MOVEFILE_REPLACE_EXISTING) == 0) {
        show_last_error(L"Failed to move ebook-viewer-portable.exe, make sure calibre is not running");
        return false;
    }
    if (MoveFileEx(L"Calibre Portable\\ebook-edit-portable.exe",
                L"..\\ebook-edit-portable.exe", MOVEFILE_REPLACE_EXISTING) == 0) {
        show_last_error(L"Failed to move ebook-edit-portable.exe, make sure calibre is not running");
        return false;
    }

    if (directory_exists(L"..\\Calibre")) {
        if (!rmtree(L"..\\Calibre")) {
            show_error(L"Failed to delete the Calibre program folder. Make sure calibre is not running.");
            return false;
        }
    }

    if (MoveFileEx(L"Calibre Portable\\Calibre", L"..\\Calibre", 0) == 0) {
        Sleep(4000); // Sleep and try again
        if (MoveFileEx(L"Calibre Portable\\Calibre", L"..\\Calibre", 0) == 0) {
            show_last_error(L"Failed to move calibre program folder. This is usually caused by an antivirus program or a file sync program like DropBox. Turn them off temporarily and try again. Underlying error: ");
            return false;
        }
    }

    if (!directory_exists(L"..\\Calibre Library")) {
        MoveFileEx(L"Calibre Portable\\Calibre Library", L"..\\Calibre Library", 0);
    }

    if (!directory_exists(L"..\\Calibre Settings")) {
        MoveFileEx(L"Calibre Portable\\Calibre Settings", L"..\\Calibre Settings", 0);
    }

    return true;
}
// }}}

static BOOL ensure_not_running() {
    DWORD processes[4096], needed, num;
    unsigned int i;
    WCHAR name[4*MAX_PATH] = L"<unknown>";
    HANDLE h;
    DWORD len;
    LPWSTR fname = NULL;

    if ( !EnumProcesses( processes, sizeof(processes), &needed ) ) {
        return true;
    }
    num = needed / sizeof(DWORD);

    for (i = 0; i < num; i++) {
        if (processes[i] == 0) continue;
        h = OpenProcess( PROCESS_QUERY_INFORMATION, FALSE, processes[i] );
        if (h != NULL) {
            len = GetProcessImageFileNameW(h, name, 4*MAX_PATH);
            CloseHandle(h);
            if (len != 0) {
                name[len] = 0;
                fname = PathFindFileName(name);
                if (wcscmp(fname, L"calibre.exe") == 0) {
                    show_error(L"Calibre appears to be running on your computer. Please quit it before trying to install Calibre Portable.");
                    return false;
                }
            }
        }
    }

    return true;
}

static void launch_calibre() {
    STARTUPINFO si;
    PROCESS_INFORMATION pi;

    ZeroMemory( &si, sizeof(si) );
    si.cb = sizeof(si);
    ZeroMemory( &pi, sizeof(pi) );


    if (CreateProcess(_wcsdup(L"calibre-portable.exe"), NULL,
            NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP,
            NULL, NULL, &si, &pi)
            == 0) {
        show_last_error(L"Failed to launch calibre portable");
    }

    // Close process and thread handles.
    CloseHandle( pi.hProcess );
    CloseHandle( pi.hThread );

}

void makedirs(LPWSTR path) {
    WCHAR *p = path;
    while (*p) {
        if ((*p == L'\\' || *p == L'/') && p != path && *(p-1) != L':') {
            *p = 0;
            CreateDirectory(path, NULL);
            *p = L'\\';
        }
        p++;
    }
    CreateDirectory(path, NULL);
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow)
{
	(void)hPrevInstance; (void)pCmdLine; (void)nCmdShow;
    LPVOID cdata = NULL;
    DWORD csz = 0;
    int ret = 1, argc;
    HRESULT hr;
    LPWSTR tgt = NULL, dest = NULL, *argv, unpack_dir = NULL;
    BOOL existing = false, launch = false, automated = false;
    WCHAR buf[4*MAX_PATH] = {0}, mb_msg[4*MAX_PATH] = {0}, fdest[4*MAX_PATH] = {0};

    if (!load_data(&cdata, &csz)) return ret;

    hr = CoInitialize(NULL);
    if (FAILED(hr)) { show_error(L"Failed to initialize COM"); return ret; }

    // Get the target directory for installation
    argv = CommandLineToArgvW(GetCommandLine(), &argc);
    if (argv == NULL) { show_last_error(L"Failed to get command line"); return ret; }
    if (argc > 1) {
        tgt = argv[1];
        automated = true;
        if (!directory_exists(tgt)) {
            if (GetFullPathName(tgt, MAX_PATH*4, fdest, NULL) == 0) {
                show_last_error(L"Failed to resolve target folder");
                goto end;
            }
            makedirs(fdest);
        }

    } else {
        tgt = get_directory_from_user();
        if (tgt == NULL) goto end;
    }

    if (!directory_exists(tgt)) {
        show_detailed_error(L"The specified directory does not exist: ",
                tgt, 1);
        goto end;
    }

    // Ensure the path to Calibre Portable is not too long
    do {
        if (!find_portable_dir(tgt, &dest, &existing)) goto end;

        if (GetFullPathName(dest, MAX_PATH*4, fdest, NULL) == 0) {
            show_last_error(L"Failed to resolve target folder");
            goto end;
        }
        free(dest); dest = NULL;

        if (wcslen(fdest) > 58) {
            _snwprintf_s(buf, 4*MAX_PATH, _TRUNCATE,
                L"Path to Calibre Portable (%s) too long. Must be less than 59 characters.", fdest);
            if (!existing) RemoveDirectory(fdest);
            show_error(buf);
            tgt = get_directory_from_user();
            if (tgt == NULL) goto end;
        }
    } while (wcslen(fdest) > 58);

    // Confirm the user wants to upgrade
    if (existing && !automated) {
        _snwprintf_s(mb_msg, 4*MAX_PATH, _TRUNCATE,
            L"An existing install of Calibre Portable was found at %s. Do you want to upgrade it?",
            fdest);
        if (MessageBox(NULL, mb_msg,
                L"Upgrade Calibre Portable?", MB_ICONEXCLAMATION | MB_YESNO | MB_TOPMOST) != IDYES)
            goto end;
    }

    if (existing) {
        if (!ensure_not_running()) goto end;
    }

    // Make a temp dir to unpack into
    if (!SetCurrentDirectoryW(fdest)) { show_detailed_error(L"Failed to change to unzip directory: ", fdest, 0); goto end; }

    if ( (unpack_dir = make_unpack_dir()) == NULL ) goto end;
    if (!SetCurrentDirectoryW(unpack_dir)) { show_detailed_error(L"Failed to change to unpack directory: ", fdest, 0); goto end; }

    // Extract files
    if (!extract(cdata, csz)) goto end;

    // Move files from temp dir to the install dir
    if (!move_program()) goto end;

    ret = 0;
    if (!automated) {
        _snwprintf_s(mb_msg, 4*MAX_PATH, _TRUNCATE,
            L"Calibre Portable successfully installed to %s. Launch calibre?",
            fdest);
        launch = MessageBox(NULL, mb_msg,
            L"Success", MB_ICONINFORMATION | MB_YESNO | MB_TOPMOST) == IDYES;
    }

end:
    if (unpack_dir != NULL) { SetCurrentDirectoryW(L".."); rmtree(unpack_dir); free(unpack_dir); }
    CoUninitialize();
    if (launch) launch_calibre();
    return ret;
}
