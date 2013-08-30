/*
 * recycle.c
 * Copyright (C) 2013 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "Windows.h"
#include "Shellapi.h"
/* #include <wchar.h> */

int wmain(int argc, wchar_t *argv[ ]) {
    wchar_t buf[512] = {0};
    SHFILEOPSTRUCTW op = {0};
    if (argc != 2) return 1;
    if (wcsnlen_s(argv[1], 512) > 510) return 1;
    if (wcscpy_s(buf, 512, argv[1]) != 0) return 1; 

    op.wFunc = FO_DELETE;
    op.pFrom = buf;
    op.pTo = NULL;
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOCONFIRMMKDIR | FOF_NOERRORUI | FOF_SILENT | FOF_RENAMEONCOLLISION;

    /* wprintf(L"%ls\n", buf); */
    return SHFileOperationW(&op);
}


