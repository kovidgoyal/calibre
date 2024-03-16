/*
 * launcher.c
 * Copyright (C) 2014 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#define PY_SSIZE_T_CLEAN
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <libgen.h>
#include <stdlib.h>
#include <unistd.h>

#define PATHLEN 1023

#define SET(x, y) if (setenv(x, y, 1) != 0) { fprintf(stderr, "Failed to set environment variable with error: %s\n", strerror(errno)); return 1; }

int main(int argc, char **argv) {
    static char buf[PATHLEN+1] = {0}, lib[PATHLEN+1] = {0}, base[PATHLEN+1] = {0}, exe[PATHLEN+1] = {0}, *ldp = NULL;

    if (readlink("/proc/self/exe", buf, PATHLEN) == -1) {
        fprintf(stderr, "Failed to read path of executable with error: %s\n", strerror(errno));
        return 1;
    }
    strncpy(lib, buf, PATHLEN);
    strncpy(base, dirname(lib), PATHLEN);
    int ret = snprintf(exe, PATHLEN, "%s/bin/%s", base, basename(buf));
    if (ret < 0 || ret > (PATHLEN-2)) { fprintf(stderr, "Path to executable too long: %s/bin/%s", base, basename(buf)); return 1; }
    memset(lib, 0, PATHLEN);
    ret = snprintf(lib, PATHLEN, "%s/lib", base);
    if (ret < 0 || ret > (PATHLEN-2)) { fprintf(stderr, "Path to lib too long: %s/lib", base); return 1; }

    SET("CALIBRE_QT_PREFIX", base)

    memset(buf, 0, PATHLEN);
    ldp = getenv("LD_LIBRARY_PATH");
    if (ldp == NULL) strncpy(buf, lib, PATHLEN);
    else {
        ret = snprintf(buf, PATHLEN, "%s:%s", lib, ldp);
        if (ret < 0 || ret > (PATHLEN-2)) { fprintf(stderr, "LD_LIBRARY_PATH too long: %s:%s", lib, ldp); return 1; }
    }
    SET("LD_LIBRARY_PATH", buf)
    ret = snprintf(buf, PATHLEN, "%s/ossl-modules", lib);
    if (ret < 0 || ret > (PATHLEN-2)) { fprintf(stderr, "OPENSSL_MODULES too long: %s/ossl-modules", lib); return 1; }
    SET("OPENSSL_MODULES", buf)

    argv[0] = exe;
    if (execv(exe, argv) == -1) {
        fprintf(stderr, "Failed to execute binary: %s with error: %s\n", exe, strerror(errno));
        return 1;
    }

    return 0;
}
