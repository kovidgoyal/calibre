#include "util.h"
#include <stdlib.h>

// These variables must be filled in before compiling
static const char *ENV_VARS[] = { /*ENV_VARS*/ NULL };
static const char *ENV_VAR_VALS[] = { /*ENV_VAR_VALS*/ NULL};
static char PROGRAM[] = "**PROGRAM**";
static const char MODULE[] = "**MODULE**";
static const char FUNCTION[] = "**FUNCTION**";
static const char PYVER[] = "**PYVER**";


int 
main(int argc, const char **argv, const char **envp) {
    return run(ENV_VARS, ENV_VAR_VALS, PROGRAM, MODULE, FUNCTION, PYVER, argc, argv, envp);
}

