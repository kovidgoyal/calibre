#pragma once

#define UNICODE

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#define OOM exit(report_error("Out of memory", EXIT_FAILURE))
#define True 1
#define False 0
typedef int bool;

void set_gui_app(bool yes);

int execute_python_entrypoint(int argc, char **argv, const char *basename,
        const char *module, const char *function,
        char *outr, char *errr);
