/*
 * fontconfig.h
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#pragma once

#include <qpa/qplatformfontdatabase.h>
#if (QT_VERSION >= QT_VERSION_CHECK(5, 8, 0))
#include <QtFontDatabaseSupport/private/qbasicfontdatabase_p.h>
#else
#include <QtPlatformSupport/private/qbasicfontdatabase_p.h>
#endif

QT_BEGIN_NAMESPACE

class QFontEngineFT;

class QFontconfigDatabase : public QBasicFontDatabase
{
public:
#if (QT_VERSION >= QT_VERSION_CHECK(5, 5, 0))
    void populateFontDatabase() Q_DECL_OVERRIDE;
    QFontEngineMulti *fontEngineMulti(QFontEngine *fontEngine, QChar::Script script) Q_DECL_OVERRIDE;
    QFontEngine *fontEngine(const QFontDef &fontDef, void *handle) Q_DECL_OVERRIDE;
    QFontEngine *fontEngine(const QByteArray &fontData, qreal pixelSize, QFont::HintingPreference hintingPreference) Q_DECL_OVERRIDE;
    QStringList fallbacksForFamily(const QString &family, QFont::Style style, QFont::StyleHint styleHint, QChar::Script script) const Q_DECL_OVERRIDE;
    QStringList addApplicationFont(const QByteArray &fontData, const QString &fileName) Q_DECL_OVERRIDE;
    QString resolveFontFamilyAlias(const QString &family) const Q_DECL_OVERRIDE;
    QFont defaultFont() const Q_DECL_OVERRIDE;
#else
    void populateFontDatabase();
    QFontEngineMulti *fontEngineMulti(QFontEngine *fontEngine, QChar::Script script);
    QFontEngine *fontEngine(const QFontDef &fontDef, void *handle);
    QFontEngine *fontEngine(const QByteArray &fontData, qreal pixelSize, QFont::HintingPreference hintingPreference);
    QStringList fallbacksForFamily(const QString &family, QFont::Style style, QFont::StyleHint styleHint, QChar::Script script) const;
    QStringList addApplicationFont(const QByteArray &fontData, const QString &fileName);
    QString resolveFontFamilyAlias(const QString &family) const;
    QFont defaultFont() const;
#endif

private:
    void setupFontEngine(QFontEngineFT *engine, const QFontDef &fontDef) const;
};

QT_END_NAMESPACE
