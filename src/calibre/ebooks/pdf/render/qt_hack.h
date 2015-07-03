/*
 * qt_hack.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#include <QGlyphRun>
#include <QTextItem>
#include <QPointF>
#include <Python.h>

PyObject* get_glyphs(const QPointF &p, const QTextItem &text_item);

PyObject* get_sfnt_table(const QTextItem &text_item, const char* tag_name);

PyObject* get_glyph_map(const QTextItem &text_item);

