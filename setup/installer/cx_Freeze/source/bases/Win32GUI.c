//-----------------------------------------------------------------------------
// Win32GUI.c
//   Main routine for frozen programs written for the Win32 GUI subsystem.
//-----------------------------------------------------------------------------

#include <Python.h>
#include <windows.h>

//-----------------------------------------------------------------------------
// FatalError()
//   Handle a fatal error.
//-----------------------------------------------------------------------------
static int FatalError(
    char *a_Message)                    // message to display
{
    MessageBox(NULL, a_Message, "cx_Freeze Fatal Error", MB_ICONERROR);
    Py_Finalize();
    return -1;
}


//-----------------------------------------------------------------------------
// StringifyObject()
//   Stringify a Python object.
//-----------------------------------------------------------------------------
static char *StringifyObject(
    PyObject *object,                   // object to stringify
    PyObject **stringRep)               // string representation
{
    if (object) {
        *stringRep = PyObject_Str(object);
        if (*stringRep)
            return PyString_AS_STRING(*stringRep);
        return "Unable to stringify";
    }

    // object is NULL
    *stringRep = NULL;
    return "None";
}


//-----------------------------------------------------------------------------
// FatalPythonErrorNoTraceback()
//   Handle a fatal Python error without traceback.
//-----------------------------------------------------------------------------
static int FatalPythonErrorNoTraceback(
    PyObject *origType,                 // exception type
    PyObject *origValue,                // exception value
    char *message)                      // message to display
{
    PyObject *typeStrRep, *valueStrRep, *origTypeStrRep, *origValueStrRep;
    char *totalMessage, *typeStr, *valueStr, *origTypeStr, *origValueStr;
    PyObject *type, *value, *traceback;
    int totalMessageLength;
    char *messageFormat;

    // fetch error and string representations of the error
    PyErr_Fetch(&type, &value, &traceback);
    origTypeStr = StringifyObject(origType, &origTypeStrRep);
    origValueStr = StringifyObject(origValue, &origValueStrRep);
    typeStr = StringifyObject(type, &typeStrRep);
    valueStr = StringifyObject(value, &valueStrRep);

    // fill out the message to be displayed
    messageFormat = "Type: %s\nValue: %s\nOther Type: %s\nOtherValue: %s\n%s";
    totalMessageLength = strlen(origTypeStr) + strlen(origValueStr) +
            strlen(typeStr) + strlen(valueStr) + strlen(message) +
            strlen(messageFormat) + 1;
    totalMessage = malloc(totalMessageLength);
    if (!totalMessage)
        return FatalError("Out of memory!");
    sprintf(totalMessage, messageFormat, typeStr, valueStr, origTypeStr,
            origValueStr, message);

    // display the message
    MessageBox(NULL, totalMessage,
            "cx_Freeze: Python error in main script (traceback unavailable)",
            MB_ICONERROR);
    free(totalMessage);
    return -1;
}


//-----------------------------------------------------------------------------
// ArgumentValue()
//   Return a suitable argument value by replacing NULL with Py_None.
//-----------------------------------------------------------------------------
static PyObject *ArgumentValue(
    PyObject *object)                   // argument to massage
{
    if (object) {
        Py_INCREF(object);
        return object;
    }
    Py_INCREF(Py_None);
    return Py_None;
}


//-----------------------------------------------------------------------------
// HandleSystemExitException()
//   Handles a system exit exception differently. If an integer value is passed
// through then that becomes the exit value; otherwise the string value of the
// value passed through is displayed in a message box.
//-----------------------------------------------------------------------------
static void HandleSystemExitException()
{
    PyObject *type, *value, *traceback, *valueStr;
    int exitCode = 0;
    char *message;

    PyErr_Fetch(&type, &value, &traceback);
    if (PyInstance_Check(value)) {
        PyObject *code = PyObject_GetAttrString(value, "code");
        if (code) {
            Py_DECREF(value);
            value = code;
            if (value == Py_None)
                Py_Exit(0);
        }
    }
    if (PyInt_Check(value))
        exitCode = PyInt_AsLong(value);
    else {
        message = StringifyObject(value, &valueStr);
        MessageBox(NULL, message, "cx_Freeze: Application Terminated",
                MB_ICONERROR);
        Py_XDECREF(valueStr);
        exitCode = 1;
    }
    Py_Exit(exitCode);
}


//-----------------------------------------------------------------------------
// FatalScriptError()
//   Handle a fatal Python error with traceback.
//-----------------------------------------------------------------------------
static int FatalScriptError()
{
    PyObject *type, *value, *traceback, *argsTuple, *module, *method, *result;
    int tracebackLength, i;
    char *tracebackStr;

    // if a system exception, handle it specially
    if (PyErr_ExceptionMatches(PyExc_SystemExit))
        HandleSystemExitException();

    // get the exception details
    PyErr_Fetch(&type, &value, &traceback);

    // import the traceback module
    module = PyImport_ImportModule("traceback");
    if (!module)
        return FatalPythonErrorNoTraceback(type, value,
                "Cannot import traceback module.");

    // get the format_exception method
    method = PyObject_GetAttrString(module, "format_exception");
    Py_DECREF(module);
    if (!method)
        return FatalPythonErrorNoTraceback(type, value,
              "Cannot get format_exception method.");

    // create a tuple for the arguments
    argsTuple = PyTuple_New(3);
    if (!argsTuple) {
        Py_DECREF(method);
        return FatalPythonErrorNoTraceback(type, value,
                "Cannot create arguments tuple for traceback.");
    }
    PyTuple_SET_ITEM(argsTuple, 0, ArgumentValue(type));
    PyTuple_SET_ITEM(argsTuple, 1, ArgumentValue(value));
    PyTuple_SET_ITEM(argsTuple, 2, ArgumentValue(traceback));

    // call the format_exception method
    result = PyObject_CallObject(method, argsTuple);
    Py_DECREF(method);
    Py_DECREF(argsTuple);
    if (!result)
        return FatalPythonErrorNoTraceback(type, value,
                "Failed calling format_exception method.");

    // determine length of string representation of formatted traceback
    tracebackLength = 1;
    for (i = 0; i < PyList_GET_SIZE(result); i++)
        tracebackLength += PyString_GET_SIZE(PyList_GET_ITEM(result, i));

    // create a string representation of the formatted traceback
    tracebackStr = malloc(tracebackLength);
    if (!tracebackStr) {
        Py_DECREF(result);
        return FatalError("Out of memory!");
    }
    tracebackStr[0] = '\0';
    for (i = 0; i < PyList_GET_SIZE(result); i++)
        strcat(tracebackStr, PyString_AS_STRING(PyList_GET_ITEM(result, i)));
    Py_DECREF(result);

    // bring up the error
    MessageBox(NULL, tracebackStr, "cx_Freeze: Python error in main script",
            MB_ICONERROR);
    Py_Finalize();
    return 1;
}


#include "Common.c"


//-----------------------------------------------------------------------------
// WinMain()
//   Main routine for the executable in Windows.
//-----------------------------------------------------------------------------
int WINAPI WinMain(
    HINSTANCE instance,                 // handle to application
    HINSTANCE prevInstance,             // previous handle to application
    LPSTR commandLine,                  // command line
    int showFlag)                       // show flag
{
    const char *fileName;

    // initialize Python
    Py_NoSiteFlag = 1;
    Py_FrozenFlag = 1;
    Py_IgnoreEnvironmentFlag = 1;
    Py_SetPythonHome("");
    Py_SetProgramName(__argv[0]);
    fileName = Py_GetProgramFullPath();
    Py_Initialize();
    PySys_SetArgv(__argc, __argv);

    // do the work
    if (ExecuteScript(fileName) < 0)
        return 1;

    // terminate Python
    Py_Finalize();
    return 0;
}

