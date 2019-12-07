/*
 * placeholder.c
 * Copyright (C) 2018 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <libproc.h>
#include <unistd.h>


int
main(int argc, char * const *argv, const char **envp) {
    int ret;
    pid_t pid;
    char pathbuf[PROC_PIDPATHINFO_MAXSIZE], realpath_buf[PROC_PIDPATHINFO_MAXSIZE * 5];

    pid = getpid();
    ret = proc_pidpath(pid, pathbuf, sizeof(pathbuf));
    if (ret <= 0) {
        perror("failed to get executable path for current pid with error");
        return 1;
    }
    char *path = realpath(pathbuf, realpath_buf);
    if (path == NULL) {
        perror("failed to get realpath for executable path with error");
        return 1;
    }
    char *t = rindex(path, '/');
    if (t == NULL) {
        fprintf(stderr, "No / in executable path: %s\n", path);
        return 1;
    }
    *(t + 1) = 0;
    snprintf(t + 1, sizeof(realpath_buf) - strlen(path), "%s/%s", REL_PATH, EXE_NAME);
    execv(path, argv);
}
