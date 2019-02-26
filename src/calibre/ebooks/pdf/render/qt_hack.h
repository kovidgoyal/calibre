/*
 * qt_hack.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

// Per python C-API docs, Python.h must always be the first header
#include <Python.h>
#include <QGlyphRun>
#include <QTextItem>
#include <QPointF>

PyObject* get_glyphs(const QPointF &p, const QTextItem &text_item);

PyObject* get_sfnt_table(const QTextItem &text_item, const char* tag_name);

PyObject* get_glyph_map(const QTextItem &text_item);
