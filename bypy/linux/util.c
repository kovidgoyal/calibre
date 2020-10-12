#include "util.h"
#include "../run-python.h"

static char exe_path_char[PATH_MAX];

static void
get_paths() {
	char linkname[256]; /* /proc/<pid>/exe */
    wchar_t *p;
	pid_t pid;
	int ret;

	pid = getpid();

	if (snprintf(linkname, sizeof(linkname), "/proc/%i/exe", pid) < 0) {
		/* This should only happen on large word systems. I'm not sure
		   what the proper response is here.
		   Since it really is an assert-like condition, aborting the
		   program seems to be in order. */
        fatal("PID too large");
    }

	ret = readlink(linkname, exe_path_char, sizeof(exe_path_char));
	if (ret == -1) fatal("Failed to read exe path from: %s", exe_path_char);
	if ((size_t)ret >= sizeof(exe_path_char)) fatal("exe path buffer too small.");
	exe_path_char[ret] = 0;
    decode_char_buf(exe_path_char, interpreter_data.exe_path);

    p = wcsrchr(interpreter_data.exe_path, '/');
    if (p == NULL) fatal("No path separators in executable path: %s", exe_path_char);
    wcsncat(interpreter_data.python_home_path, interpreter_data.exe_path, p - interpreter_data.exe_path);
    p = wcsrchr(interpreter_data.python_home_path, '/');
    if (p == NULL) fatal("Only one path separator in executable path: %s", exe_path_char);
    *p = 0;
    size_t home_len = p - interpreter_data.python_home_path;
    if (home_len == 0) fatal("base directory empty");
    wcsncat(interpreter_data.executables_path, interpreter_data.python_home_path, home_len);

    swprintf(interpreter_data.python_lib_path, arraysz(interpreter_data.python_lib_path), L"%ls/lib/python%d.%d", interpreter_data.python_home_path, PY_VERSION_MAJOR, PY_VERSION_MINOR);
    swprintf(interpreter_data.resources_path, arraysz(interpreter_data.resources_path), L"%ls/resources", interpreter_data.python_home_path);
    swprintf(interpreter_data.extensions_path, arraysz(interpreter_data.extensions_path), L"%ls/lib/calibre-extensions", interpreter_data.python_home_path);
}

void
execute_python_entrypoint(int argc, char * const *argv, const wchar_t *basename, const wchar_t *module, const wchar_t *function, const bool gui_app) {
    interpreter_data.argc = argc;
    interpreter_data.argv = argv;
    interpreter_data.basename = basename; interpreter_data.module = module; interpreter_data.function = function;
    pre_initialize_interpreter(gui_app);
    get_paths();
    run_interpreter();
}
