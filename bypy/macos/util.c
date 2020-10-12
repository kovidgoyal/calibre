#include "util.h"
#include "../run-python.h"
#include <CoreFoundation/CoreFoundation.h>
#include <mach-o/dyld.h>

#define EXPORT __attribute__((visibility("default")))

#define EXE "@executable_path/.."

static const char *env_vars[] = { ENV_VARS };
static const char *env_var_vals[] = { ENV_VAR_VALS };

static void
set_env_vars(const char* contents_path) {
    char buf[3*PATH_MAX];
    const char *env_var, *val;

	for (size_t i = 0; i < arraysz(env_vars); i++) {
        env_var = env_vars[i]; val = env_var_vals[i];
        if (strstr(val, EXE) == val && strlen(val) >= sizeof(EXE)) {
			snprintf(buf, sizeof(buf) - 1, "%s%s", contents_path, val + sizeof(EXE) - 1);
            setenv(env_var, buf, 1);
        } else
            setenv(env_var, val, 1);
    }
    return;
}

static void
get_paths(char *path) {
	decode_char_buf(path, interpreter_data.exe_path);
    for (unsigned i = 0; i < 3; i++) {
        char *t = rindex(path, '/');
        if (t == NULL) fatal("Failed to determine bundle path.");
        *t = '\0';
    }
    if (strstr(path, "/calibre.app/Contents/") != NULL) {
        // We are one of the duplicate executables created to workaround codesign's limitations
        for (unsigned i = 0; i < 2; i++) {
            char *t = rindex(path, '/');
            if (t == NULL) fatal("Failed to resolve bundle path in dummy executable");
            *t = '\0';
        }
    }
#define cat_literal(func, path, literal) func(path, literal, arraysz(literal) - 1)
	cat_literal(strncat, path, "/Contents");
	set_env_vars(path);
	decode_char_buf(path, interpreter_data.bundle_resource_path);
#define set_path(which, fmt, ...) swprintf(interpreter_data.which, arraysz(interpreter_data.which), fmt, interpreter_data.bundle_resource_path, __VA_ARGS__)
	set_path(python_home_path, L"%ls/Resources/Python", NULL);
    set_path(frameworks_path,  L"%ls/Frameworks", NULL);
    set_path(python_lib_path,  L"%ls/Resources/Python/lib/python%d.%d", PY_VERSION_MAJOR, PY_VERSION_MINOR);
	set_path(extensions_path,  L"%ls/Frameworks/plugins", NULL);
	set_path(resources_path,   L"%ls/Resources/resources", NULL);
	set_path(executables_path, L"%ls/MacOS", NULL);
#undef set_path
	cat_literal(wcsncat, interpreter_data.bundle_resource_path, L"/Resources");
#undef cat_literal
}

EXPORT
void
run(const wchar_t *program, const wchar_t *module, const wchar_t *function, bool gui_app, int argc, char * const *argv, char* exe_path) {
    interpreter_data.argc = argc;
    interpreter_data.argv = argv;
    interpreter_data.basename = program; interpreter_data.module = module; interpreter_data.function = function;
    pre_initialize_interpreter(gui_app);
	get_paths(exe_path);
	run_interpreter();
}
