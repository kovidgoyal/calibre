#pragma once

int run(const char **ENV_VARS, const char **ENV_VAR_VALS, char *PROGRAM,
        const char *MODULE, const char *FUNCTION, const char *PYVER, int IS_GUI,
        int argc, char *const *argv, const char **envp, char *full_exe_path);
