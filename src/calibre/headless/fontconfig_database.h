/*
 * fontconfig.h
 * Copyright (C) 2015 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */
#pragma once

#include <qpa/qplatformfontdatabase.h>
#if (QT_VERSION >= QT_VERSION_CHECK(5, 9, 0))
#include <QtFontDatabaseSupport/private/qfreetypefontdatabase_p.h>
#elif (QT_VERSION >= QT_VERSION_CHECK(5, 8, 0))
#include <QtFontDatabaseSupport/private/qbasicfontdatabase_p.h>
#define QFreeTypeFontDatabase QBasicFontDatabase
#else
#include <QtPlatformSupport/private/qbasicfontdatabase_p.h>
#define QFreeTypeFontDatabase QBasicFontDatabase
#endif

QT_BEGIN_NAMESPACE

class QFontEngineFT;

class QFontconfigDatabase : public QFreeTypeFontDatabase
{
public:
#if (QT_VERSION >= QT_VERSION_CHECK(5, 5, 0))
    void populateFontDatabase() override;
#if (QT_VERSION >= QT_VERSION_CHECK(5, 8, 0))
	void invalidate() override;
#endif
    QFontEngineMulti *fontEngineMulti(QFontEngine *fontEngine, QChar::Script script) override;
    QFontEngine *fontEngine(const QFontDef &fontDef, void *handle) override;
    QFontEngine *fontEngine(const QByteArray &fontData, qreal pixelSize, QFont::HintingPreference hintingPreference) override;
    QStringList fallbacksForFamily(const QString &family, QFont::Style style, QFont::StyleHint styleHint, QChar::Script script) const override;
    QStringList addApplicationFont(const QByteArray &fontData, const QString &fileName) override;
    QString resolveFontFamilyAlias(const QString &family) const override;
    QFont defaultFont() const override;
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
