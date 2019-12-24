#pragma once
#include <wchar.h>
#include <stdbool.h>

void run(const wchar_t *program, const wchar_t *module, const wchar_t *function, bool is_gui, int argc, char * const *argv, char* exe_path);
