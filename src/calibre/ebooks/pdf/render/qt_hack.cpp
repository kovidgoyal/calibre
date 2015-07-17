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

PyObject* get_glyphs(const QPointF &p, const QTextItem &text_item) {
    const quint32 *tag = reinterpret_cast<const quint32 *>("name");
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

    PyObject *points = NULL, *indices = NULL, *temp = NULL;

    points = PyTuple_New(positions.count());
    if (points == NULL) return PyErr_NoMemory();
    for (int i = 0; i < positions.count(); i++) {
        temp = Py_BuildValue("dd", positions[i].x.toReal()/stretch, positions[i].y.toReal());
        if (temp == NULL) { Py_DECREF(points); return NULL; }
        PyTuple_SET_ITEM(points, i, temp); temp = NULL;
    }

    indices = PyTuple_New(glyphs.count());
    if (indices == NULL) { Py_DECREF(points); return PyErr_NoMemory(); }
    for (int i = 0; i < glyphs.count(); i++) {
        temp = PyInt_FromLong((long)glyphs[i]);
        if (temp == NULL) { Py_DECREF(indices); Py_DECREF(points); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(indices, i, temp); temp = NULL;
    }
    const QByteArray table(fe->getSfntTable(qToBigEndian(*tag)));
    return Py_BuildValue("s#ffOO", table.constData(), table.size(), size, stretch, points, indices);
}

PyObject* get_sfnt_table(const QTextItem &text_item, const char* tag_name) {
    QTextItemInt ti = static_cast<const QTextItemInt &>(text_item);
    const quint32 *tag = reinterpret_cast<const quint32 *>(tag_name);
    const QByteArray table(ti.fontEngine->getSfntTable(qToBigEndian(*tag)));
    return Py_BuildValue("s#", table.constData(), table.size());
}

PyObject* get_glyph_map(const QTextItem &text_item) {
    QTextItemInt ti = static_cast<const QTextItemInt &>(text_item);
    QGlyphLayoutArray<10> glyphs;
    int nglyphs = 10;
    PyObject *t = NULL, *ans = PyTuple_New(0x10000);

    if (ans == NULL) return PyErr_NoMemory();

    for (uint uc = 0; uc < 0x10000; ++uc) {
        QChar ch(uc);
        ti.fontEngine->stringToCMap(&ch, 1, &glyphs, &nglyphs, QFontEngine::GlyphIndicesOnly);
        t = PyInt_FromLong(glyphs.glyphs[0]);
        if (t == NULL) { Py_DECREF(ans); return PyErr_NoMemory(); }
        PyTuple_SET_ITEM(ans, uc, t); t = NULL;
    }
    return ans;
}

