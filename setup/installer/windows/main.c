/*
 * Copyright 2009 Kovid Goyal
 */

#include "util.h"

#ifdef GUI_APP

int WINAPI                                                                                                      
wWinMain(HINSTANCE Inst, HINSTANCE PrevInst,
    wchar_t *CmdLine, int CmdShow) {

    wchar_t *stdout_redirect, *stderr_redirect, basename[50];

    set_gui_app((char)1);

    MultiByteToWideChar(CP_UTF8, 0, BASENAME, -1, basename, 50);

    stdout_redirect = redirect_out_stream(basename, (char)1);
    stderr_redirect = redirect_out_stream(basename, (char)0);

	execute_python_entrypoint(BASENAME, MODULE, FUNCTION,
					stdout_redirect, stderr_redirect);

    if (stdout != NULL) fclose(stdout);
    if (stderr != NULL) fclose(stderr);

    DeleteFile(stdout_redirect);
    DeleteFile(stderr_redirect);

    return 0; // This should really be returning the value set in the WM_QUIT message, but I cannot be bothered figuring out how to get that.
}

#else


int wmain(int argc, wchar_t *argv) {
    int ret = 0;
    set_gui_app((char)0);
	ret = execute_python_entrypoint(BASENAME, MODULE, FUNCTION, NULL, NULL);

    return ret;
}

#endif
