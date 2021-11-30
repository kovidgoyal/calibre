#define PY_SSIZE_T_CLEAN
#include "util.h"
#include <stdlib.h>
#include <libproc.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>

#define fatal(...) { fprintf(stderr, __VA_ARGS__); exit(EXIT_FAILURE); }
#define arraysz(x) (sizeof(x)/sizeof(x[0]))

int
main(int argc, char * const *argv) {
    char pathbuf[PROC_PIDPATHINFO_MAXSIZE], realpath_buf[PROC_PIDPATHINFO_MAXSIZE * 5];
    pid_t pid = getpid();
    int ret = proc_pidpath(pid, pathbuf, arraysz(pathbuf));
    if (ret <= 0) fatal("failed to get executable path for current pid with error: %s", strerror(errno));
    char *path = realpath(pathbuf, realpath_buf);
    if (path == NULL) fatal("failed to get realpath for executable path with error: %s", strerror(errno));
    // We re-exec using an absolute path because the Qt WebEngine sandbox does not work
    // when running via symlink
    if (!IS_GUI && wcscmp(PROGRAM, L"calibre-parallel") != 0 && strcmp(argv[0], path) != 0) {
        char* new_argv[1024] = {0};
        new_argv[0] = path;
        for (int i = 1; i < argc && i < arraysz(new_argv) - 1; i++) new_argv[i] = argv[i];
        execv(path, new_argv);
    }
    run(PROGRAM, MODULE, FUNCTION, IS_GUI, argc, argv, path);
	return 0;
}
