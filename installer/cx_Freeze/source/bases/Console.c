//-----------------------------------------------------------------------------
// Console.c
//   Main routine for frozen programs which run in a console.
//-----------------------------------------------------------------------------

#include <Python.h>
#ifdef __WIN32__
#include <windows.h>
#endif

//-----------------------------------------------------------------------------
// FatalError()
//   Prints a fatal error.
//-----------------------------------------------------------------------------
static int FatalError(
    const char *message)                // message to print
{
    PyErr_Print();
    Py_FatalError(message);
    return -1;
}


//-----------------------------------------------------------------------------
// FatalScriptError()
//   Prints a fatal error in the initialization script.
//-----------------------------------------------------------------------------
static int FatalScriptError(void)
{
    PyErr_Print();
    return -1;
}


#include "Common.c"


//-----------------------------------------------------------------------------
// main()
//   Main routine for frozen programs.
//-----------------------------------------------------------------------------
int main(int argc, char **argv)
{
    const char *fileName;
    char *encoding;

    // initialize Python
    Py_NoSiteFlag = 1;
    Py_FrozenFlag = 1;
    Py_IgnoreEnvironmentFlag = 1;

    encoding = getenv("PYTHONIOENCODING");
    if (encoding != NULL) { 
        Py_FileSystemDefaultEncoding = strndup(encoding, 100);
    }

    Py_SetPythonHome("");
    Py_SetProgramName(argv[0]);
    fileName = Py_GetProgramFullPath();

    Py_Initialize();
    PySys_SetArgv(argc, argv);


    // do the work
    if (ExecuteScript(fileName) < 0)
        return 1;

    Py_Finalize();
    return 0;
}

