#include "util.h"
#include <stdlib.h>
#include <libproc.h>
#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <stdio.h>

#define fatal(...) { fprintf(stderr, __VA_ARGS__); exit(EXIT_FAILURE); }
#define arraysz(x) (sizeof(x)/sizeof(x[0]))


// These variables must be filled in before compiling
static const char *ENV_VARS[] = { /*ENV_VARS*/ NULL };
static const char *ENV_VAR_VALS[] = { /*ENV_VAR_VALS*/ NULL};
static char PROGRAM[] = "**PROGRAM**";
static const char MODULE[] = "**MODULE**";
static const char FUNCTION[] = "**FUNCTION**";
static const char PYVER[] = "**PYVER**";


int
main(int argc, char* const *argv, const char **envp) {
    char pathbuf[PROC_PIDPATHINFO_MAXSIZE], realpath_buf[PROC_PIDPATHINFO_MAXSIZE * 5];
    pid_t pid = getpid();
    int ret = proc_pidpath(pid, pathbuf, arraysz(pathbuf));
    if (ret <= 0) fatal("failed to get executable path for current pid with error: %s", strerror(errno));
    char *path = realpath(pathbuf, realpath_buf);
    if (path == NULL) fatal("failed to get realpath for executable path with error: %s", strerror(errno));
    // We re-exec using an absolute path because the Qt WebEngine sandbox does not work
    // when running via symlink
	const int is_gui = **IS_GUI**;
    if (!is_gui && strcmp(PROGRAM, "calibre-parallel") != 0 && strcmp(argv[0], path) != 0) {
        char* new_argv[1024] = {0};
        new_argv[0] = path;
        for (int i = 1; i < argc && i < arraysz(new_argv) - 1; i++) new_argv[i] = argv[i];
        execv(path, new_argv);
    }

    return run(ENV_VARS, ENV_VAR_VALS, PROGRAM, MODULE, FUNCTION, PYVER, is_gui, argc, argv, envp, path);
}
