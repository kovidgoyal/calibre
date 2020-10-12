#pragma once

#define UNICODE

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

#define OOM exit(report_error("Out of memory", EXIT_FAILURE))
#define True 1
#define False 0
#include <wchar.h>
#include <stdbool.h>

void execute_python_entrypoint(int argc, char * const *argv, const wchar_t *basename,
        const wchar_t *module, const wchar_t *function, const bool gui_app);
