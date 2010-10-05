/* ***************************************************************************
This is the C language version of NameMapper.py.  See the comments and
DocStrings in NameMapper for details on the purpose and interface of this
module.

===============================================================================
$Id: _namemapper.c,v 1.34 2007/12/10 18:25:20 tavis_rudd Exp $
Authors: Tavis Rudd <tavis@damnsimple.com>
Version: $Revision: 1.34 $
Start Date: 2001/08/07
Last Revision Date: $Date: 2007/12/10 18:25:20 $
*/

/* *************************************************************************** */
#include <Python.h>
#include <string.h>
#include <stdlib.h>

#include "cheetah.h"

#ifdef __cplusplus
extern "C" {
#endif


static PyObject *NotFound;   /* locally-raised exception */
static PyObject *TooManyPeriods;   /* locally-raised exception */
static PyObject* pprintMod_pformat; /* used for exception formatting */


/* *************************************************************************** */
/* First the c versions of the functions */
/* *************************************************************************** */

static void setNotFoundException(char *key, PyObject *namespace)
{
    PyObject *exceptionStr = NULL;
    exceptionStr = PyUnicode_FromFormat("cannot find \'%s\'", key);
    PyErr_SetObject(NotFound, exceptionStr);
    Py_XDECREF(exceptionStr);
}

static int wrapInternalNotFoundException(char *fullName, PyObject *namespace)
{
    PyObject *excType, *excValue, *excTraceback, *isAlreadyWrapped = NULL;
    PyObject *newExcValue = NULL;
    if (!ALLOW_WRAPPING_OF_NOTFOUND_EXCEPTIONS) {
        return 0;
    } 

    if (!PyErr_Occurred()) {
        return 0;
    }

    if (PyErr_GivenExceptionMatches(PyErr_Occurred(), NotFound)) {
        PyErr_Fetch(&excType, &excValue, &excTraceback);
        isAlreadyWrapped = PyObject_CallMethod(excValue, "find", "s", "while searching");

        if (isAlreadyWrapped != NULL) {
            if (PyLong_AsLong(isAlreadyWrapped) == -1) {
                newExcValue = PyUnicode_FromFormat("%U while searching for \'%s\'",
                        excValue, fullName);
            }
            Py_DECREF(isAlreadyWrapped);
        }
        else {
           newExcValue = excValue; 
        }
        PyErr_Restore(excType, newExcValue, excTraceback);
        return -1;
    } 
    return 0;
}


static int isInstanceOrClass(PyObject *nextVal) {
#ifndef IS_PYTHON3
    /* old style classes or instances */
    if((PyInstance_Check(nextVal)) || (PyClass_Check(nextVal))) {
        return 1;
    }
#endif 

    if (!PyObject_HasAttrString(nextVal, "__class__")) {
        return 0;
    }

    /* new style classes or instances */
    if (PyType_Check(nextVal) || PyObject_HasAttrString(nextVal, "mro")) {
        return 1;
    }

    if (strncmp(nextVal->ob_type->tp_name, "function", 9) == 0)
        return 0;

    /* method, func, or builtin func */
    if (PyObject_HasAttrString(nextVal, "im_func") 
        || PyObject_HasAttrString(nextVal, "func_code")
        || PyObject_HasAttrString(nextVal, "__self__")) {
        return 0;
    }

    /* instance */
    if ((!PyObject_HasAttrString(nextVal, "mro")) &&
            PyObject_HasAttrString(nextVal, "__init__")) {
        return 1;
    }

    return 0;
}


static int getNameChunks(char *nameChunks[], char *name, char *nameCopy) 
{
    char c;
    char *currChunk;
    int currChunkNum = 0;

    currChunk = nameCopy;
    while ('\0' != (c = *nameCopy)){
    if ('.' == c) {
        if (currChunkNum >= (MAXCHUNKS-2)) { /* avoid overflowing nameChunks[] */
            PyErr_SetString(TooManyPeriods, name); 
            return 0;
        }

        *nameCopy ='\0';
        nameChunks[currChunkNum++] = currChunk;
        nameCopy++;
        currChunk = nameCopy;
    } else 
        nameCopy++;
    }
    if (nameCopy > currChunk) {
        nameChunks[currChunkNum++] = currChunk;
    }
    return currChunkNum;
}


static int PyNamemapper_hasKey(PyObject *obj, char *key)
{
    if (PyMapping_Check(obj) && PyMapping_HasKeyString(obj, key)) {
        return TRUE;
    } else if (PyObject_HasAttrString(obj, key)) {
        return TRUE;
    }
    return FALSE;
}


static PyObject *PyNamemapper_valueForKey(PyObject *obj, char *key)
{
    PyObject *theValue = NULL;

    if (PyMapping_Check(obj) && PyMapping_HasKeyString(obj, key)) {
        theValue = PyMapping_GetItemString(obj, key);
    } else if (PyObject_HasAttrString(obj, key)) {
        theValue = PyObject_GetAttrString(obj, key);
    } else {
        setNotFoundException(key, obj);
    }
    return theValue;
}

static PyObject *PyNamemapper_valueForName(PyObject *obj, char *nameChunks[], int numChunks, int executeCallables)
{
    int i;
    char *currentKey;
    PyObject *currentVal = NULL;
    PyObject *nextVal = NULL;

    currentVal = obj;
    for (i=0; i < numChunks;i++) {
        currentKey = nameChunks[i];
        if (PyErr_CheckSignals()) {	/* not sure if I really need to do this here, but what the hell */
            if (i>0) {
                Py_DECREF(currentVal);
            }
            return NULL;
        }
        
        if (PyMapping_Check(currentVal) && PyMapping_HasKeyString(currentVal, currentKey)) {
            nextVal = PyMapping_GetItemString(currentVal, currentKey);
        } 
        else {
          PyObject *exc;
          nextVal = PyObject_GetAttrString(currentVal, currentKey);
          exc = PyErr_Occurred();
          if (exc != NULL) {
            // if exception == AttributeError, report our own exception
            if (PyErr_ExceptionMatches(PyExc_AttributeError)) {
                setNotFoundException(currentKey, currentVal);
            }
            // any exceptions results in failure
            if (i > 0) {
                Py_DECREF(currentVal);
            }
            return NULL;
          }
        }
        if (i > 0) {
            Py_DECREF(currentVal);
        }

        if (executeCallables && PyCallable_Check(nextVal) && 
                (isInstanceOrClass(nextVal) == 0) ) {
            if (!(currentVal = PyObject_CallObject(nextVal, NULL))) {
                Py_DECREF(nextVal);
                return NULL;
            }
            Py_DECREF(nextVal);
        } else {
            currentVal = nextVal;
        }
    }

    return currentVal;
}


/* *************************************************************************** */
/* Now the wrapper functions to export into the Python module */
/* *************************************************************************** */


static PyObject *namemapper_valueForKey(PyObject *self, PyObject *args)
{
    PyObject *obj;
    char *key;

    if (!PyArg_ParseTuple(args, "Os", &obj, &key)) {
        return NULL;
    }

    return PyNamemapper_valueForKey(obj, key);
}

static PyObject *namemapper_valueForName(PYARGS)
{
    PyObject *obj;
    char *name;
    int executeCallables = 0;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *theValue;

    static char *kwlist[] = {"obj", "name", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|i", kwlist,  &obj, &name, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();  

    theValue = PyNamemapper_valueForName(obj, nameChunks, numChunks, executeCallables);
    free(nameCopy);
    if (wrapInternalNotFoundException(name, obj)) {
        theValue = NULL;
    }
    return theValue;
}

static PyObject *namemapper_valueFromSearchList(PYARGS)
{
    PyObject *searchList;
    char *name;
    int executeCallables = 0;

    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "Os|i", kwlist, &searchList, &name, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();

    iterator = PyObject_GetIter(searchList);
    if (iterator == NULL) {
        PyErr_SetString(PyExc_TypeError,"This searchList is not iterable!");
        goto done;
    }

    while ((nameSpace = PyIter_Next(iterator))) {
        checkForNameInNameSpaceAndReturnIfFound(TRUE);
        Py_DECREF(nameSpace);
        if(PyErr_CheckSignals()) {
        theValue = NULL;
        goto done;
        }
    }
    if (PyErr_Occurred()) {
        theValue = NULL;
        goto done;
    }

    setNotFoundException(nameChunks[0], searchList);

done:
    Py_XDECREF(iterator);
    free(nameCopy);
    return theValue;
}

static PyObject *namemapper_valueFromFrameOrSearchList(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    int executeCallables = 0;
    PyObject *searchList = NULL;

    /* locals */
    char *nameCopy = NULL;
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *excString = NULL;
    PyObject *iterator = NULL;

    static char *kwlist[] = {"searchList", "name", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "Os|i", kwlist,  &searchList, &name, 
                    &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();

    nameSpace = PyEval_GetLocals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);  

    iterator = PyObject_GetIter(searchList);
    if (iterator == NULL) {
        PyErr_SetString(PyExc_TypeError,"This searchList is not iterable!");
        goto done;
    }
    while ( (nameSpace = PyIter_Next(iterator)) ) {
        checkForNameInNameSpaceAndReturnIfFound(TRUE);
        Py_DECREF(nameSpace);
        if(PyErr_CheckSignals()) {
            theValue = NULL;
            goto done;
        }
    }
    if (PyErr_Occurred()) {
        theValue = NULL;
        goto done;
    }

    nameSpace = PyEval_GetGlobals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    nameSpace = PyEval_GetBuiltins();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    excString = Py_BuildValue("s", "[locals()]+searchList+[globals(), __builtins__]");
    setNotFoundException(nameChunks[0], excString);
    Py_DECREF(excString);

done:
    Py_XDECREF(iterator);
    free(nameCopy);
    return theValue;
}

static PyObject *namemapper_valueFromFrame(PyObject *self, PyObject *args, PyObject *keywds)
{
    /* python function args */
    char *name;
    int executeCallables = 0;

    /* locals */
    char *tmpPntr1 = NULL;
    char *tmpPntr2 = NULL;

    char *nameCopy = NULL;
    char *nameChunks[MAXCHUNKS];
    int numChunks;

    PyObject *nameSpace = NULL;
    PyObject *theValue = NULL;
    PyObject *excString = NULL;

    static char *kwlist[] = {"name", "executeCallables", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, keywds, "s|i", kwlist, &name, &executeCallables)) {
        return NULL;
    }

    createNameCopyAndChunks();

    nameSpace = PyEval_GetLocals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    nameSpace = PyEval_GetGlobals();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    nameSpace = PyEval_GetBuiltins();
    checkForNameInNameSpaceAndReturnIfFound(FALSE);

    excString = Py_BuildValue("s", "[locals(), globals(), __builtins__]");
    setNotFoundException(nameChunks[0], excString);
    Py_DECREF(excString);
done:
    free(nameCopy);
    return theValue;
}

/* *************************************************************************** */
/* Method registration table: name-string -> function-pointer */

static struct PyMethodDef namemapper_methods[] = {
  {"valueForKey", namemapper_valueForKey,  1},
  {"valueForName", (PyCFunction)namemapper_valueForName,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromSearchList", (PyCFunction)namemapper_valueFromSearchList,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromFrame", (PyCFunction)namemapper_valueFromFrame,  METH_VARARGS|METH_KEYWORDS},
  {"valueFromFrameOrSearchList", (PyCFunction)namemapper_valueFromFrameOrSearchList,  METH_VARARGS|METH_KEYWORDS},
  {NULL,         NULL}
};


/* *************************************************************************** */
/* Initialization function (import-time) */

#ifdef IS_PYTHON3
static struct PyModuleDef namemappermodule = {
    PyModuleDef_HEAD_INIT,
    "_namemapper",
    NULL, /* docstring */
    -1, 
    namemapper_methods,
    NULL,
    NULL,
    NULL,
    NULL};

PyMODINIT_FUNC PyInit__namemapper(void)
{
    PyObject *m = PyModule_Create(&namemappermodule);
#else
DL_EXPORT(void) init_namemapper(void)
{
    PyObject *m = Py_InitModule3("_namemapper", namemapper_methods, NULL);
#endif 

    PyObject *d, *pprintMod;

    /* add symbolic constants to the module */
    d = PyModule_GetDict(m);
    NotFound = PyErr_NewException("NameMapper.NotFound",PyExc_LookupError,NULL);
    TooManyPeriods = PyErr_NewException("NameMapper.TooManyPeriodsInName",NULL,NULL);
    PyDict_SetItemString(d, "NotFound", NotFound);
    PyDict_SetItemString(d, "TooManyPeriodsInName", TooManyPeriods);
    pprintMod = PyImport_ImportModule("pprint");
    if (!pprintMod) {
#ifdef IS_PYTHON3
        return NULL;
#else
        return;
#endif
    }
    pprintMod_pformat = PyObject_GetAttrString(pprintMod, "pformat");
    Py_DECREF(pprintMod);
    /* check for errors */
    if (PyErr_Occurred()) {
        Py_FatalError("Can't initialize module _namemapper");
    }
#ifdef IS_PYTHON3
    return m;
#endif
}

#ifdef __cplusplus
}
#endif
