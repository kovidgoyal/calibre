/*
 * launcher.c
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <libgen.h>
#include <stdlib.h>

#define PATHLEN 1023

int main(int argc, char **argv) {
    static char buf[PATHLEN+1] = {0}, lib[PATHLEN+1] = {0}, base[PATHLEN+1] = {0}, exe[PATHLEN+1] = {0}, *ldp = NULL;

    if (readlink("/proc/self/exe", buf, PATHLEN) == -1) {
        fprintf(stderr, "Failed to read path of executable with error: %s\n", strerror(errno));
        return 1;
    }
    strncpy(lib, buf, PATHLEN);
    strncpy(base, dirname(lib), PATHLEN);
    snprintf(exe, PATHLEN, "%s/bin/%s", base, basename(buf));
    memset(lib, 0, PATHLEN);
    snprintf(lib, PATHLEN, "%s/lib", base);

    /* qt-at-spi causes crashes and performance issues in various distros, so disable it */
    if (setenv("QT_ACCESSIBILITY", "0", 1) != 0) {
        fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno));
        return 1;
    }

    if (setenv("MAGICK_HOME", base, 1) != 0) {
        fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno));
        return 1;
    }
    memset(buf, 0, PATHLEN); snprintf(buf, PATHLEN, "%s/%s/config", lib, MAGICK_BASE);
    if (setenv("MAGICK_CONFIGURE_PATH", buf, 1) != 0) {
        fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno));
        return 1;
    }
    memset(buf, 0, PATHLEN); snprintf(buf, PATHLEN, "%s/%s/modules-Q16/coders", lib, MAGICK_BASE);
    if (setenv("MAGICK_CODER_MODULE_PATH", buf, 1) != 0) {
        fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno));
        return 1;
    }
    memset(buf, 0, PATHLEN); snprintf(buf, PATHLEN, "%s/%s/modules-Q16/filters", lib, MAGICK_BASE);
    if (setenv("MAGICK_CODER_FILTER_PATH", buf, 1) != 0) {
        fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno));
        return 1;
    }

    memset(buf, 0, PATHLEN);
    ldp = getenv("LD_LIBRARY_PATH");
    if (ldp == NULL) strncpy(buf, lib, PATHLEN);
    else snprintf(buf, PATHLEN, "%s:%s", lib, ldp);
    if (setenv("LD_LIBRARY_PATH", buf, 1) != 0) {
        fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno));
        return 1;
    }

    argv[0] = exe;
    if (execv(exe, argv) == -1) {
        fprintf(stderr, "Failed to execute binary: %s with error: %s\n", exe, strerror(errno));
        return 1;
    }

    return 0;
}



