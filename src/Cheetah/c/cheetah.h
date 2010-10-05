/*
 * Copyright 2009, R. Tyler Ballance <tyler@monkeypox.org>
 * 
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are
 * met:
 * 
 *  1. Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 * 
 *  2. Redistributions in binary form must reproduce the above copyright
 *     notice, this list of conditions and the following disclaimer in
 *     the documentation and/or other materials provided with the
 *     distribution.
 * 
 *  3. Neither the name of R. Tyler Ballance nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
 * DISCLAIMED. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
 * INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
 * IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */ 

#ifndef _CHEETAH_H_
#define _CHEETAH_H_

#include <Python.h>

#if PY_MAJOR_VERSION >= 3
#define IS_PYTHON3
#endif

#define TRUE 1
#define FALSE 0

#define PYARGS PyObject *self, PyObject *args, PyObject *kwargs


/*
 * _namemapper.c specific definitions 
 */
#define MAXCHUNKS 15		/* max num of nameChunks for the arrays */
#define ALLOW_WRAPPING_OF_NOTFOUND_EXCEPTIONS 1
#define createNameCopyAndChunks() {\
    nameCopy = malloc(strlen(name) + 1);\
    tmpPntr1 = name; \
    tmpPntr2 = nameCopy;\
    while ((*tmpPntr2++ = *tmpPntr1++)); \
        numChunks = getNameChunks(nameChunks, name, nameCopy); \
    if (PyErr_Occurred()) { 	/* there might have been TooManyPeriods */\
        free(nameCopy);\
        return NULL;\
    }\
}

#define checkForNameInNameSpaceAndReturnIfFound(namespace_decref) { \
    if ( PyNamemapper_hasKey(nameSpace, nameChunks[0]) ) {\
        theValue = PyNamemapper_valueForName(nameSpace, nameChunks, numChunks, executeCallables);\
        if (namespace_decref) {\
            Py_DECREF(nameSpace);\
        }\
        if (wrapInternalNotFoundException(name, nameSpace)) {\
            theValue = NULL;\
        }\
        goto done;\
    }\
}

#endif
