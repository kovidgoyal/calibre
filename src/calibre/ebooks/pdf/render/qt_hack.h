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


class GlyphInfo {
    public:
        QByteArray name;
        QVector<QPointF> positions;
        qreal size;
        qreal stretch;
        QVector<unsigned int> indices;

        GlyphInfo(const QByteArray &name, qreal size, qreal stretch, const QVector<QPointF> &positions, const QVector<unsigned int> &indices);

    private:
        GlyphInfo(const GlyphInfo&);
        GlyphInfo &operator=(const GlyphInfo&);
};

GlyphInfo* get_glyphs(QPointF &p, const QTextItem &text_item);

QByteArray get_sfnt_table(const QTextItem &text_item, const char* tag_name);

QVector<unsigned int>* get_glyph_map(const QTextItem &text_item);

