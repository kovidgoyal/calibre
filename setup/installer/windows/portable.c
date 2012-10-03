#ifndef UNICODE
#define UNICODE
#endif 

#ifndef _UNICODE
#define _UNICODE
#endif 


#include <windows.h>
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

void launch_calibre(LPCTSTR exe, LPCTSTR config_dir) {
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

    ZeroMemory( &si, sizeof(si) );
    si.cb = sizeof(si);
    ZeroMemory( &pi, sizeof(pi) );

    fSuccess = CreateProcess(exe, NULL,
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


int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow)
{
    LPTSTR app_dir, config_dir, exe, library_dir, too_long;

    app_dir = get_app_dir();
    config_dir = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));
    exe = (LPTSTR)calloc(BUFSIZE, sizeof(TCHAR));

    _sntprintf_s(config_dir, BUFSIZE, _TRUNCATE, _T("%sCalibre Settings"), app_dir);
    _sntprintf_s(exe, BUFSIZE, _TRUNCATE, _T("%sCalibre\\calibre.exe"), app_dir);

    launch_calibre(exe, config_dir);

    free(app_dir); free(config_dir); free(exe); 

    return 0;
}


