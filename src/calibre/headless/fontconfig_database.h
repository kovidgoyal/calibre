/*
 * fontconfig.h
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#pragma once

#include <qpa/qplatformfontdatabase.h>
#include <QtPlatformSupport/private/qbasicfontdatabase_p.h>

QT_BEGIN_NAMESPACE

class QFontEngineFT;

class QFontconfigDatabase : public QBasicFontDatabase
{
public:
    void populateFontDatabase();
    QFontEngineMulti *fontEngineMulti(QFontEngine *fontEngine, QChar::Script script);
    QFontEngine *fontEngine(const QFontDef &fontDef, void *handle);
    QFontEngine *fontEngine(const QByteArray &fontData, qreal pixelSize, QFont::HintingPreference hintingPreference);
    QStringList fallbacksForFamily(const QString &family, QFont::Style style, QFont::StyleHint styleHint, QChar::Script script) const;
    QStringList addApplicationFont(const QByteArray &fontData, const QString &fileName);
    QString resolveFontFamilyAlias(const QString &family) const;
    QFont defaultFont() const;

private:
    void setupFontEngine(QFontEngineFT *engine, const QFontDef &fontDef) const;
};

QT_END_NAMESPACE
