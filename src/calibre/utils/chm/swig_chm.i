%module chmlib
%begin %{
#define SWIG_PYTHON_STRICT_BYTE_CHAR
%}

%include "typemaps.i"
%include "cstring.i"

%{
/*
 Copyright (C) 2003 Rubens Ramos <rubensr@users.sourceforge.net>

 Based on code by:
 Copyright (C) 2003  Razvan Cojocaru <razvanco@gmx.net>

 pychm is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as
 published by the Free Software Foundation; either version 2 of the
 License, or (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.

 You should have received a copy of the GNU General Public
 License along with this program; see the file COPYING.  If not,
 write to the Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 Boston, MA 02111-1307, USA

 $Id$
*/

#include "chm_lib.h"
#include <stdio.h>

static PyObject *my_callback = NULL;

static PyObject *
my_set_callback(PyObject *dummy, PyObject *arg)
{
    PyObject *result = NULL;

    if (!PyCallable_Check(arg)) {
      PyErr_SetString(PyExc_TypeError, "parameter must be callable");
      return NULL;
    }
    Py_XINCREF(arg);         /* Add a reference to new callback */
    Py_XDECREF(my_callback);  /* Dispose of previous callback */
    my_callback = arg;       /* Remember new callback */
    /* Boilerplate to return "None" */
    Py_INCREF(Py_None);
    result = Py_None;
    return result;
}

int dummy_enumerator (struct chmFile *h,
                      struct chmUnitInfo *ui,
                      void *context) {
    PyObject *arglist;
    PyObject *result;
    PyObject *py_h;
    PyObject *py_ui;
    PyObject *py_c;

    py_h  = SWIG_NewPointerObj((void *) h, SWIGTYPE_p_chmFile, 0);
    py_ui = SWIG_NewPointerObj((void *) ui, SWIGTYPE_p_chmUnitInfo, 0);
    /* The following was: py_c  = PyCObject_AsVoidPtr(context); which did
       not make sense because the function takes a PyObject * and returns a
       void *, not the reverse. This was probably never used?? In doubt,
       replace with a call which makes sense and hope for the best... */
    py_c = PyCapsule_New(context, "context", NULL);

    /* Time to call the callback */
    arglist = Py_BuildValue("(OOO)", py_h, py_ui, py_c);
    if (arglist) {
      result = PyEval_CallObject(my_callback, arglist);
      Py_DECREF(arglist);
      Py_DECREF(result);

      Py_DECREF(py_h);
      Py_DECREF(py_ui);
      Py_DECREF(py_c);

      if (result == NULL) {
        return 0; /* Pass error back */
      } else {
        return 1;
      }
    } else
      return 0;
 }
%}

%typemap(in) CHM_ENUMERATOR {
  if (!my_set_callback(self, $input)) goto fail;
  $1 = dummy_enumerator;
}

%typemap(in) void *context {
  if (!($1 = PyCapsule_New($input, "context", NULL))) goto fail;
}

%typemap(in, numinputs=0) struct chmUnitInfo *OutValue (struct chmUnitInfo *temp = (struct chmUnitInfo *) calloc(1, sizeof(struct chmUnitInfo))) {
  $1 = temp;
}

%typemap(argout) struct chmUnitInfo *OutValue {
  PyObject *o, *o2, *o3;
  o = SWIG_NewPointerObj((void *) $1, SWIGTYPE_p_chmUnitInfo, 1);
  if ((!$result) || ($result == Py_None)) {
    $result = o;
  } else {
    if (!PyTuple_Check($result)) {
      PyObject *o2 = $result;
      $result = PyTuple_New(1);
      PyTuple_SetItem($result,0,o2);
    }
    o3 = PyTuple_New(1);
    PyTuple_SetItem(o3,0,o);
    o2 = $result;
    $result = PySequence_Concat(o2,o3);
    Py_DECREF(o2);
    Py_DECREF(o3);
  }
}

%typemap(check) unsigned char *OUTPUT {
  /* nasty hack */
#ifdef __cplusplus
   $1 = ($1_ltype) new char[arg5];
#else
   $1 = ($1_ltype) malloc(arg5);
#endif
   if ($1 == NULL) SWIG_fail;
}

%typemap(argout,fragment="t_output_helper") unsigned char *OUTPUT {
   PyObject *o;
   o = SWIG_FromCharPtrAndSize((const char*)$1, arg5);
/*   o = PyString_FromStringAndSize($1, arg5);*/
   $result = t_output_helper($result,o);
#ifdef __cplusplus
   delete [] $1;
#else
   free($1);
#endif
}

#ifdef WIN32
typedef unsigned __int64 LONGUINT64;
typedef __int64          LONGINT64;
#else
typedef unsigned long long LONGUINT64;
typedef long long          LONGINT64;
#endif

/* the two available spaces in a CHM file                      */
/* N.B.: The format supports arbitrarily many spaces, but only */
/*       two appear to be used at present.                     */
#define CHM_UNCOMPRESSED (0)
#define CHM_COMPRESSED   (1)

/* structure representing an ITS (CHM) file stream             */
struct chmFile;

/* structure representing an element from an ITS file stream   */
#define CHM_MAX_PATHLEN  256
struct chmUnitInfo
{
    LONGUINT64         start;
    LONGUINT64         length;
    int                space;
    char               path[CHM_MAX_PATHLEN+1];
};

/* open an ITS archive */
struct chmFile* chm_open(const char *filename);

/* close an ITS archive */
void chm_close(struct chmFile *h);

/* methods for ssetting tuning parameters for particular file */
#define CHM_PARAM_MAX_BLOCKS_CACHED 0
void chm_set_param(struct chmFile *h,
                   int paramType,
                   int paramVal);

/* resolve a particular object from the archive */
#define CHM_RESOLVE_SUCCESS (0)
#define CHM_RESOLVE_FAILURE (1)
int chm_resolve_object(struct chmFile *h,
                       const char *objPath,
                       struct chmUnitInfo *OutValue);

/* retrieve part of an object from the archive */
LONGINT64 chm_retrieve_object(struct chmFile *h,
                              struct chmUnitInfo *ui,
                              unsigned char *OUTPUT,
                              LONGUINT64 addr,
                              LONGINT64 len);

/* enumerate the objects in the .chm archive */
typedef int (*CHM_ENUMERATOR)(struct chmFile *h,
                              struct chmUnitInfo *ui,
                              void *context);
#define CHM_ENUMERATE_NORMAL    (1)
#define CHM_ENUMERATE_META      (2)
#define CHM_ENUMERATE_SPECIAL   (4)
#define CHM_ENUMERATE_FILES     (8)
#define CHM_ENUMERATE_DIRS      (16)
#define CHM_ENUMERATE_ALL       (31)
#define CHM_ENUMERATOR_FAILURE  (0)
#define CHM_ENUMERATOR_CONTINUE (1)
#define CHM_ENUMERATOR_SUCCESS  (2)
int chm_enumerate(struct chmFile *h,
                  int what,
                  CHM_ENUMERATOR e,
                  void *context);

int chm_enumerate_dir(struct chmFile *h,
                      const char *prefix,
                      int what,
                      CHM_ENUMERATOR e,
                      void *context);
