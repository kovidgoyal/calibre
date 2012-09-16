#ifndef UNICODE
#define UNICODE
#endif 

#ifndef _UNICODE
#define _UNICODE
#endif 


#include <windows.h>
#include <Shlwapi.h>
#include <tchar.h>
#include <wchar.h>
#include <stdio.h>

#define BUFSIZE 4096

void show_error(LPCTSTR msg) {
    MessageBeep(MB_ICONERROR);
    MessageBox(NULL, msg, _T("Error"), MB_OK|MB_ICONERROR);
}

void show_detailed_error(LPCTSTR preamble, LPCTSTR msg, int code) {
    LPTSTR buf;
    buf = (LPTSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(TCHAR)*
            (_tcslen(msg) + _tcslen(preamble) + 80));

    _sntprintf_s(buf, 
        LocalSize(buf) / sizeof(TCHAR), _TRUNCATE,
        _T("%s\r\n  %s (Error Code: %d)\r\n"), 
        preamble, msg, code);

    show_error(buf);
    LocalFree(buf);
}

void show_last_error_crt(LPCTSTR preamble) {
    TCHAR buf[BUFSIZE];
    int err = 0;

    _get_errno(&err);
    _tcserror_s(buf, BUFSIZE, err);
    show_detailed_error(preamble, buf, err);
}

void show_last_error(LPCTSTR preamble) {
    TCHAR *msg = NULL;
    DWORD dw = GetLastError(); 

    FormatMessage(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | 
        FORMAT_MESSAGE_FROM_SYSTEM |
        FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        dw,
        MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
        (LPTSTR)&msg,
        0, NULL );

    show_detailed_error(preamble, msg, (int)dw);
}


LPTSTR get_app_dir() {
    LPTSTR buf, buf2, buf3;
    DWORD sz;
    TCHAR drive[4] = _T("\0\0\0");
    errno_t err;

    buf = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));
    buf2 = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));
    buf3 = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));

    sz = GetModuleFileName(NULL, buf, BUFSIZE);

    if (sz == 0 || sz > BUFSIZE-1) {
        show_error(_T("Failed to get path to calibre-portable.exe"));
        ExitProcess(1);
    }

    err = _tsplitpath_s(buf, drive, 4, buf2, BUFSIZE, NULL, 0, NULL, 0);

    if (err != 0) {
        show_last_error_crt(_T("Failed to split path to calibre-portable.exe"));
        ExitProcess(1);
    }

    _sntprintf_s(buf3, BUFSIZE-1, _TRUNCATE, _T("%s%s"), drive, buf2);
    free(buf); free(buf2);
    return buf3;
}

void launch_calibre(LPCTSTR exe, LPCTSTR config_dir, LPCTSTR library_dir) {
    DWORD dwFlags=0;
    STARTUPINFO si;
    PROCESS_INFORMATION pi;
    BOOL fSuccess; 
    TCHAR cmdline[BUFSIZE];

    if (! SetEnvironmentVariable(_T("CALIBRE_CONFIG_DIRECTORY"), config_dir)) {
        show_last_error(_T("Failed to set environment variables"));
        ExitProcess(1);
    }

    if (! SetEnvironmentVariable(_T("CALIBRE_PORTABLE_BUILD"), exe)) {
        show_last_error(_T("Failed to set environment variables"));
        ExitProcess(1);
    }

    dwFlags = CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP;
    _sntprintf_s(cmdline, BUFSIZE, _TRUNCATE, _T(" \"--with-library=%s\""), library_dir);

    ZeroMemory( &si, sizeof(si) );
    si.cb = sizeof(si);
    ZeroMemory( &pi, sizeof(pi) );

    fSuccess = CreateProcess(exe, cmdline,
        NULL,           // Process handle not inheritable
        NULL,           // Thread handle not inheritable
        FALSE,          // Set handle inheritance to FALSE
        dwFlags,        // Creation flags http://msdn.microsoft.com/en-us/library/ms684863(v=vs.85).aspx
        NULL,           // Use parent's environment block
        NULL,           // Use parent's starting directory 
        &si,            // Pointer to STARTUPINFO structure
        &pi             // Pointer to PROCESS_INFORMATION structure
    );

    if (fSuccess == 0) {
        show_last_error(_T("Failed to launch the calibre program"));
    }

    // Close process and thread handles.
    CloseHandle( pi.hProcess );
    CloseHandle( pi.hThread );

}

static BOOL is_dots(LPCTSTR name) {
    return _tcscmp(name, _T(".")) == 0 || _tcscmp(name, _T("..")) == 0;
}

static void find_calibre_library(LPTSTR library_dir) {
    TCHAR base[BUFSIZE] = {0}, buf[BUFSIZE] = {0};
    WIN32_FIND_DATA fdFile; 
    HANDLE hFind = NULL;

    _sntprintf_s(buf, BUFSIZE, _TRUNCATE, _T("%s\\metadata.db"), base);

    if (PathFileExists(buf)) return; // Calibre Library/metadata.db exists, we use it

    _tcscpy(base, library_dir);
    PathRemoveFileSpec(base);

    _sntprintf_s(buf, BUFSIZE, _TRUNCATE, _T("%s\\*"), base);

    // Look for some other folder that contains a metadata.db file inside the Calibre Portable folder
    if((hFind = FindFirstFileEx(buf, FindExInfoStandard, &fdFile, FindExSearchLimitToDirectories, NULL, 0)) 
            != INVALID_HANDLE_VALUE) {
        do {
            if(is_dots(fdFile.cFileName)) continue;

            if(fdFile.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
                _sntprintf_s(buf, BUFSIZE, _TRUNCATE, _T("%s\\%s\\metadata.db"), base, fdFile.cFileName);
                if (PathFileExists(buf)) {
                    // some dir/metadata.db exists, we use it as the library
                    PathRemoveFileSpec(buf);
                    _tcscpy(library_dir, buf);
                    FindClose(hFind);
                    return;
                }
            } 
        } while(FindNextFile(hFind, &fdFile));
        FindClose(hFind);
    }

}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow)
{
    LPTSTR app_dir, config_dir, exe, library_dir, too_long;

    app_dir = get_app_dir();
    config_dir = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));
    library_dir = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));
    exe = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));

    _sntprintf_s(config_dir, BUFSIZE, _TRUNCATE, _T("%sCalibre Settings"), app_dir);
    _sntprintf_s(exe, BUFSIZE, _TRUNCATE, _T("%sCalibre\\calibre.exe"), app_dir);
    _sntprintf_s(library_dir, BUFSIZE, _TRUNCATE, _T("%sCalibre Library"), app_dir);

    find_calibre_library(library_dir);

    if ( _tcscnlen(library_dir, BUFSIZE) <= 74 ) {
        launch_calibre(exe, config_dir, library_dir);
    } else {
        too_long = (LPTSTR)calloc(BUFSIZE+300, sizeof(TCHAR));
        _sntprintf_s(too_long, BUFSIZE+300, _TRUNCATE, 
                _T("Path to Calibre Portable (%s) too long. Must be less than 59 characters."), app_dir);

        show_error(too_long);
    }

    free(app_dir); free(config_dir); free(exe); free(library_dir);

    return 0;
}


