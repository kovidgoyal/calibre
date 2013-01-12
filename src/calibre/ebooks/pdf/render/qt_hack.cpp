/*
 * qt_hack.cpp
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "qt_hack.h"

#include <QtEndian>

#include "private/qtextengine_p.h"
#include "private/qfontengine_p.h"

GlyphInfo* get_glyphs(QPointF &p, const QTextItem &text_item) {
    QTextItemInt ti = static_cast<const QTextItemInt &>(text_item);
    QFontEngine *fe = ti.fontEngine;
    qreal size = ti.fontEngine->fontDef.pixelSize;
#ifdef Q_WS_WIN
    if (false && ti.fontEngine->type() == QFontEngine::Win) {
        // This is used in the Qt sourcecode, but it gives incorrect results,
        // so I have disabled it. I dont understand how it works in qpdf.cpp
        QFontEngineWin *fe = static_cast<QFontEngineWin *>(ti.fontEngine);
        // I think this should be tmHeight - tmInternalLeading, but pixelSize
        // seems to work on windows as well, so leave it as pixelSize
        size = fe->tm.tmHeight;
    }
#endif
    int synthesized = ti.fontEngine->synthesized();
    qreal stretch = synthesized & QFontEngine::SynthesizedStretch ? ti.fontEngine->fontDef.stretch/100. : 1.;

    QVarLengthArray<glyph_t> glyphs;
    QVarLengthArray<QFixedPoint> positions;
    QTransform m = QTransform::fromTranslate(p.x(), p.y());
    fe->getGlyphPositions(ti.glyphs, m, ti.flags, glyphs, positions);
    QVector<QPointF> points = QVector<QPointF>(positions.count());
    for (int i = 0; i < positions.count(); i++) {
        points[i].setX(positions[i].x.toReal()/stretch);
        points[i].setY(positions[i].y.toReal());
    }

    QVector<unsigned int> indices = QVector<unsigned int>(glyphs.count());
    for (int i = 0; i < glyphs.count(); i++)
        indices[i] = (unsigned int)glyphs[i];

    const quint32 *tag = reinterpret_cast<const quint32 *>("name");

    return new GlyphInfo(fe->getSfntTable(qToBigEndian(*tag)), size, stretch, points, indices);
}

GlyphInfo::GlyphInfo(const QByteArray& name, qreal size, qreal stretch, const QVector<QPointF> &positions, const QVector<unsigned int> &indices) :name(name), positions(positions), size(size), stretch(stretch), indices(indices) {
}

QByteArray get_sfnt_table(const QTextItem &text_item, const char* tag_name) {
    QTextItemInt ti = static_cast<const QTextItemInt &>(text_item);
    const quint32 *tag = reinterpret_cast<const quint32 *>(tag_name);
    return ti.fontEngine->getSfntTable(qToBigEndian(*tag));
}

QVector<unsigned int>* get_glyph_map(const QTextItem &text_item) {
    QTextItemInt ti = static_cast<const QTextItemInt &>(text_item);
    QVector<unsigned int> *ans = new QVector<unsigned int>(0x10000);
    QGlyphLayoutArray<10> glyphs;
    int nglyphs = 10;

    for (uint uc = 0; uc < 0x10000; ++uc) {
        QChar ch(uc);
        ti.fontEngine->stringToCMap(&ch, 1, &glyphs, &nglyphs, QTextEngine::GlyphIndicesOnly);
        (*ans)[uc] = glyphs.glyphs[0];
    }
    return ans;
}

