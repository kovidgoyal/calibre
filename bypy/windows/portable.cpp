/*
 * portable.cpp
 * Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#ifndef UNICODE
#define UNICODE
#endif

#ifndef _UNICODE
#define _UNICODE
#endif

#include <Windows.h>
#include <tchar.h>
#include <wchar.h>
#include <stdio.h>
#include <string>
#include <stdlib.h>

#define BUFSIZE 4096


// error handling {{{
static void
show_error(LPCWSTR msg) {
    MessageBeep(MB_ICONERROR);
    MessageBoxW(NULL, msg, L"Error", MB_OK|MB_ICONERROR);
}

static void
show_detailed_error(LPCWSTR preamble, LPCWSTR msg, int code) {
    LPTSTR buf;
    buf = (LPTSTR)LocalAlloc(LMEM_ZEROINIT, sizeof(TCHAR)*
            (_tcslen(msg) + _tcslen(preamble) + 80));

    _snwprintf_s(buf,
        LocalSize(buf) / sizeof(TCHAR), _TRUNCATE,
        L"%s\r\n  %s (Error Code: %d)\r\n",
        preamble, msg, code);

    show_error(buf);
    LocalFree(buf);
}

static void
show_last_error_crt(LPCWSTR preamble) {
    TCHAR buf[BUFSIZE];
    int err = 0;

    _get_errno(&err);
    _tcserror_s(buf, BUFSIZE, err);
    show_detailed_error(preamble, buf, err);
}

static void
show_last_error(LPCWSTR preamble) {
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


// }}}



static bool
get_app_dir(std::wstring& ans, std::wstring& exe_name) {
    DWORD sz;
    static wchar_t drive[_MAX_DRIVE] = {0};
    static wchar_t buf[BUFSIZE] = {0}, dirpath[_MAX_DIR] = {0}, fname[_MAX_FNAME] = {0}, ext[_MAX_EXT] = {0};

    sz = GetModuleFileName(NULL, buf, BUFSIZE);

    if (sz == 0 || sz > BUFSIZE-1) {
        show_error(L"Failed to get path to portable launcher");
        return false;
    }

    errno_t err = _wsplitpath_s(buf, drive, _MAX_DRIVE, dirpath, _MAX_DIR, fname, _MAX_FNAME, ext, _MAX_EXT);

    if (err != 0) {
        show_last_error_crt(L"Failed to split path to portable launcher");
        return false;
    }
    ans.append(drive); ans.append(dirpath);
    if (ans.length() > 58) {
        std::wstring msg;
        msg.append(L"Path to Calibre Portable (");
        msg.append(ans);
        msg.append(L") too long. Must be less than 59 characters.");
        show_error(msg.c_str());
        return false;
	}
    exe_name.append(fname);
    exe_name.erase(exe_name.length() - sizeof("portable"), sizeof("portable"));
    exe_name.append(ext);
    return true;
}


static void
quote_argv(const std::wstring& arg, std::wstring& cmd_line) {
    if (!arg.empty() && arg.find_first_of(L" \t\n\v\"") == arg.npos) {
        cmd_line.append(arg);
        return;
    }
    cmd_line.push_back(L'"');

    for (auto iterator = arg.begin() ; ; ++iterator) {
        unsigned num_back_slashes = 0;

        while (iterator != arg.end() && *iterator == L'\\') {
            ++iterator;
            ++num_back_slashes;
        }

        if (iterator == arg.end()) {

            //
            // Escape all backslashes, but let the terminating
            // double quotation mark we add below be interpreted
            // as a metacharacter.
            //

            cmd_line.append (num_back_slashes * 2, L'\\');
            break;
        }
        else if (*iterator == L'"') {

            //
            // Escape all backslashes and the following
            // double quotation mark.
            //

            cmd_line.append (num_back_slashes * 2 + 1, L'\\');
            cmd_line.push_back (*iterator);
        }
        else {

            //
            // Backslashes aren't special here.
            //

            cmd_line.append (num_back_slashes, L'\\');
            cmd_line.push_back (*iterator);
        }
    }

    cmd_line.push_back (L'"');
}

static int
launch_exe(LPCWSTR exe_path, const std::wstring &cmd_line, LPCWSTR config_dir) {
    DWORD dwFlags=0;
    STARTUPINFO si;
    PROCESS_INFORMATION pi;
    if (cmd_line.length() > BUFSIZE - 4) {
        show_error(L"Path to executable in portable folder too long.");
        return 1;
    }

    if (!SetEnvironmentVariableW(L"CALIBRE_CONFIG_DIRECTORY", config_dir)) {
        show_last_error(L"Failed to set environment variables");
        return 1;
    }

    if (!SetEnvironmentVariableW(L"CALIBRE_PORTABLE_BUILD", exe_path)) {
        show_last_error(L"Failed to set environment variables");
        return 1;
    }

    dwFlags = CREATE_UNICODE_ENVIRONMENT | CREATE_NEW_PROCESS_GROUP;

    ZeroMemory( &si, sizeof(si) );
    si.cb = sizeof(si);
    ZeroMemory( &pi, sizeof(pi) );
    static wchar_t mutable_cmdline[BUFSIZE] = {0};
    cmd_line.copy(mutable_cmdline, BUFSIZE-1);

    if (!CreateProcess(NULL, mutable_cmdline,
        NULL,           // Process handle not inheritable
        NULL,           // Thread handle not inheritable
        FALSE,          // Set handle inheritance to FALSE
        dwFlags,        // Creation flags http://msdn.microsoft.com/en-us/library/ms684863(v=vs.85).aspx
        NULL,           // Use parent's environment block
        NULL,           // Use parent's starting directory
        &si,            // Pointer to STARTUPINFO structure
        &pi             // Pointer to PROCESS_INFORMATION structure
    )) {
        std::wstring message(L"Failed to launch: ");
        message.append(mutable_cmdline);
        show_last_error(message.c_str());
    }

    // Close process and thread handles.
    CloseHandle( pi.hProcess );
    CloseHandle( pi.hThread );
    return 0;
}


int WINAPI
wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR orig_cmd_line, int nCmdShow) {
    std::wstring exe, config_dir, cmd_line, application_dir, exe_name;

    if (!get_app_dir(application_dir, exe_name)) return 1;
    config_dir.append(application_dir); config_dir.append(L"Calibre Settings");
    exe.append(application_dir); exe.append(L"Calibre\\"); exe.append(exe_name);

    int argc;
    wchar_t **argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    if (argv == NULL) {
        show_last_error(L"Failed to convert cmdline to argv array");
        return 1;
    }
    quote_argv(exe, cmd_line);
    for (int i = 1; i < argc; i++) {
        std::wstring arg(argv[i]);
        cmd_line.push_back(L' ');
        quote_argv(arg, cmd_line);
    }
    LocalFree(argv);
    return launch_exe(exe.c_str(), cmd_line.c_str(), config_dir.c_str());
}
