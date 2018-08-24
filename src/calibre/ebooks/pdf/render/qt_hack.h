/*
 * qt_hack.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

// Python must be included before QT, otherwise QT overwrites the "slots" in "PyType
// *slots" using the "#define slots Q_SLOTS" definition
#include <Python.h>
#include <QGlyphRun>
#include <QTextItem>
#include <QPointF>

PyObject* get_glyphs(const QPointF &p, const QTextItem &text_item);

PyObject* get_sfnt_table(const QTextItem &text_item, const char* tag_name);

PyObject* get_glyph_map(const QTextItem &text_item);

