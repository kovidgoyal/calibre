/*
 * Copyright (C) 2018 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <stdint.h>
typedef uint32_t char_type;
typedef int bool;
#define false 0
#define true 1
#define EXPORTED CALIBRE_MODINIT_FUNC
#define START_ALLOW_CASE_RANGE
#define END_ALLOW_CASE_RANGE
#define UNUSED
#define PYNOARG PyObject *__a1 UNUSED, PyObject *__a2 UNUSED
#define arraysz(x) (sizeof(x)/sizeof(x[0]))
