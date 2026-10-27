/*
 * color.h
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#include <Python.h>

#define arraysz(x) (sizeof(x) / sizeof(x[0]))

PyObject *tinycss_parse_color_string(PyObject *self, PyObject *src);
PyObject *tinycss_parse_css4_color_string(PyObject *self, PyObject *src);
