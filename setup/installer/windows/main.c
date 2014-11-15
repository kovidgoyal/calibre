/*
 * Copyright 2009 Kovid Goyal
 */

#include "util.h"

#ifdef GUI_APP

int WINAPI                                                                                                      
wWinMain(HINSTANCE Inst, HINSTANCE PrevInst, wchar_t *CmdLine, int CmdShow) {
    set_gui_app((char)1);

    // Redirect stdout and stderr to NUL so that python does not fail writing to them
    redirect_out_stream(stdout);
    redirect_out_stream(stderr);

	execute_python_entrypoint(BASENAME, MODULE, FUNCTION);


    return 0; // This should really be returning the value set in the WM_QUIT message, but I cannot be bothered figuring out how to get that.
}

#else


int wmain(int argc, wchar_t *argv) {
    int ret = 0;
    set_gui_app((char)0);
	ret = execute_python_entrypoint(BASENAME, MODULE, FUNCTION);

    return ret;
}

#endif
