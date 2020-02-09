/****************************************************************************
**
** Copyright (C) 2016 The Qt Company Ltd.
** Contact: https://www.qt.io/licensing/
**
** This file is part of the plugins of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:LGPL$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see https://www.qt.io/terms-conditions. For further
** information use the contact form at https://www.qt.io/contact-us.
**
** GNU Lesser General Public License Usage
** Alternatively, this file may be used under the terms of the GNU Lesser
** General Public License version 3 as published by the Free Software
** Foundation and appearing in the file LICENSE.LGPL3 included in the
** packaging of this file. Please review the following information to
** ensure the GNU Lesser General Public License version 3 requirements
** will be met: https://www.gnu.org/licenses/lgpl-3.0.html.
**
** GNU General Public License Usage
** Alternatively, this file may be used under the terms of the GNU
** General Public License version 2.0 or (at your option) the GNU General
** Public license version 3 or any later version approved by the KDE Free
** Qt Foundation. The licenses are as published by the Free Software
** Foundation and appearing in the file LICENSE.GPL2 and LICENSE.GPL3
** included in the packaging of this file. Please review the following
** information to ensure the GNU General Public License requirements will
** be met: https://www.gnu.org/licenses/gpl-2.0.html and
** https://www.gnu.org/licenses/gpl-3.0.html.
**
** $QT_END_LICENSE$
**
****************************************************************************/

#include <QtGlobal>

#include <sys/param.h>

#if defined(Q_OS_OSX)
#import <AppKit/AppKit.h>
#import <IOKit/graphics/IOGraphicsLib.h>
#elif defined(QT_PLATFORM_UIKIT)
#import <UIKit/UIFont.h>
#endif

#include <QtCore/qelapsedtimer.h>

#include <QtFontDatabaseSupport/private/qcoretextfontdatabase_p.h>
#include <QtFontDatabaseSupport/private/qfontengine_coretext_p.h>
#if QT_CONFIG(settings)
#include <QtCore/QSettings>
#endif
#include <QtCore/QtEndian>
#ifndef QT_NO_FREETYPE
#include <QtFontDatabaseSupport/private/qfontengine_ft_p.h>
#endif

QT_BEGIN_NAMESPACE

// this could become a list of all languages used for each writing
// system, instead of using the single most common language.
static const char *languageForWritingSystem[] = {
    0,     // Any
    "en",  // Latin
    "el",  // Greek
    "ru",  // Cyrillic
    "hy",  // Armenian
    "he",  // Hebrew
    "ar",  // Arabic
    "syr", // Syriac
    "div", // Thaana
    "hi",  // Devanagari
    "bn",  // Bengali
    "pa",  // Gurmukhi
    "gu",  // Gujarati
    "or",  // Oriya
    "ta",  // Tamil
    "te",  // Telugu
    "kn",  // Kannada
    "ml",  // Malayalam
    "si",  // Sinhala
    "th",  // Thai
    "lo",  // Lao
    "bo",  // Tibetan
    "my",  // Myanmar
    "ka",  // Georgian
    "km",  // Khmer
    "zh-Hans", // SimplifiedChinese
    "zh-Hant", // TraditionalChinese
    "ja",  // Japanese
    "ko",  // Korean
    "vi",  // Vietnamese
    0, // Symbol
    "sga", // Ogham
    "non", // Runic
    "man" // N'Ko
};
enum { LanguageCount = sizeof(languageForWritingSystem) / sizeof(const char *) };

QCoreTextFontDatabase::QCoreTextFontDatabase()
    : m_hasPopulatedAliases(false)
{
}

QCoreTextFontDatabase::~QCoreTextFontDatabase()
{
    for (CTFontDescriptorRef ref : qAsConst(m_systemFontDescriptors))
        CFRelease(ref);
}

void QCoreTextFontDatabase::populateFontDatabase()
{
    qCDebug(lcQpaFonts) << "Populating font database...";
    QElapsedTimer elapsed;
    if (lcQpaFonts().isDebugEnabled())
        elapsed.start();

    QCFType<CFArrayRef> familyNames = CTFontManagerCopyAvailableFontFamilyNames();
    for (NSString *familyName in familyNames.as<const NSArray *>())
        QPlatformFontDatabase::registerFontFamily(QString::fromNSString(familyName));

    qCDebug(lcQpaFonts) << "Populating available families took" << elapsed.restart() << "ms";

    // Force creating the theme fonts to get the descriptors in m_systemFontDescriptors
    if (m_themeFonts.isEmpty())
        (void)themeFonts();

    qCDebug(lcQpaFonts) << "Resolving theme fonts took" << elapsed.restart() << "ms";

    Q_FOREACH (CTFontDescriptorRef fontDesc, m_systemFontDescriptors)
        populateFromDescriptor(fontDesc);

    qCDebug(lcQpaFonts) << "Populating system descriptors took" << elapsed.restart() << "ms";

    Q_ASSERT(!m_hasPopulatedAliases);
}

bool QCoreTextFontDatabase::populateFamilyAliases(const QString &missingFamily)
{
#if defined(Q_OS_MACOS)
    if (m_hasPopulatedAliases)
        return false;

    // There's no API to go from a localized family name to its non-localized
    // name, so we have to resort to enumerating all the available fonts and
    // doing a reverse lookup.

    qCDebug(lcQpaFonts) << "Populating family aliases...";
    QElapsedTimer elapsed;
    elapsed.start();

    QString nonLocalizedMatch;
    QCFType<CFArrayRef> familyNames = CTFontManagerCopyAvailableFontFamilyNames();
    NSFontManager *fontManager = NSFontManager.sharedFontManager;
    for (NSString *familyName in familyNames.as<const NSArray *>()) {
        NSString *localizedFamilyName = [fontManager localizedNameForFamily:familyName face:nil];
        if (![localizedFamilyName isEqual:familyName]) {
            QString nonLocalizedFamily = QString::fromNSString(familyName);
            QString localizedFamily = QString::fromNSString(localizedFamilyName);
            QPlatformFontDatabase::registerAliasToFontFamily(nonLocalizedFamily, localizedFamily);
            if (localizedFamily == missingFamily)
                nonLocalizedMatch = nonLocalizedFamily;
        }
    }
    m_hasPopulatedAliases = true;

    if (lcQpaFonts().isWarningEnabled()) {
        QString warningMessage;
        QDebug msg(&warningMessage);

        msg << "Populating font family aliases took" << elapsed.restart() << "ms.";
        if (!nonLocalizedMatch.isNull())
            msg << "Replace uses of" << missingFamily << "with its non-localized name" << nonLocalizedMatch;
        else
            msg << "Replace uses of missing font family" << missingFamily << "with one that exists";
        msg << "to avoid this cost.";

        qCWarning(lcQpaFonts) << qPrintable(warningMessage);
    }

    return true;
#else
    Q_UNUSED(missingFamily);
    return false;
#endif
}

void QCoreTextFontDatabase::populateFamily(const QString &familyName)
{
    QCFType<CFMutableDictionaryRef> attributes = CFDictionaryCreateMutable(kCFAllocatorDefault, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFDictionaryAddValue(attributes, kCTFontFamilyNameAttribute, QCFString(familyName));
    QCFType<CTFontDescriptorRef> nameOnlyDescriptor = CTFontDescriptorCreateWithAttributes(attributes);

    // A single family might match several different fonts with different styles eg.
    QCFType<CFArrayRef> matchingFonts = (CFArrayRef) CTFontDescriptorCreateMatchingFontDescriptors(nameOnlyDescriptor, 0);
    if (!matchingFonts) {
        qCWarning(lcQpaFonts) << "QCoreTextFontDatabase: Found no matching fonts for family" << familyName;
        return;
    }

    const int numFonts = CFArrayGetCount(matchingFonts);
    for (int i = 0; i < numFonts; ++i)
        populateFromDescriptor(CTFontDescriptorRef(CFArrayGetValueAtIndex(matchingFonts, i)), familyName);
}

void QCoreTextFontDatabase::invalidate()
{
    m_hasPopulatedAliases = false;
}

struct FontDescription {
    QCFString familyName;
    QCFString styleName;
    QString foundryName;
    QFont::Weight weight;
    QFont::Style style;
    QFont::Stretch stretch;
    qreal pointSize;
    bool fixedPitch;
    QSupportedWritingSystems writingSystems;
};

#ifndef QT_NO_DEBUG_STREAM
Q_DECL_UNUSED static inline QDebug operator<<(QDebug debug, const FontDescription &fd)
{
    QDebugStateSaver saver(debug);
    return debug.nospace() << "FontDescription("
        << "familyName=" << QString(fd.familyName)
        << ", styleName=" << QString(fd.styleName)
        << ", foundry=" << fd.foundryName
        << ", weight=" << fd.weight
        << ", style=" << fd.style
        << ", stretch=" << fd.stretch
        << ", pointSize=" << fd.pointSize
        << ", fixedPitch=" << fd.fixedPitch
        << ", writingSystems=" << fd.writingSystems
    << ")";
}
#endif

static void getFontDescription(CTFontDescriptorRef font, FontDescription *fd)
{
    QCFType<CFDictionaryRef> styles = (CFDictionaryRef) CTFontDescriptorCopyAttribute(font, kCTFontTraitsAttribute);

    fd->foundryName = QStringLiteral("CoreText");
    fd->familyName = (CFStringRef) CTFontDescriptorCopyAttribute(font, kCTFontFamilyNameAttribute);
    fd->styleName = (CFStringRef)CTFontDescriptorCopyAttribute(font, kCTFontStyleNameAttribute);
    fd->weight = QFont::Normal;
    fd->style = QFont::StyleNormal;
    fd->stretch = QFont::Unstretched;
    fd->fixedPitch = false;

    if (QCFType<CTFontRef> tempFont = CTFontCreateWithFontDescriptor(font, 0.0, 0)) {
        uint tag = MAKE_TAG('O', 'S', '/', '2');
        CTFontRef tempFontRef = tempFont;
        void *userData = reinterpret_cast<void *>(&tempFontRef);
        uint length = 128;
        QVarLengthArray<uchar, 128> os2Table(length);
        if (QCoreTextFontEngine::ct_getSfntTable(userData, tag, os2Table.data(), &length) && length >= 86) {
            if (length > uint(os2Table.length())) {
                os2Table.resize(length);
                if (!QCoreTextFontEngine::ct_getSfntTable(userData, tag, os2Table.data(), &length))
                    Q_UNREACHABLE();
                Q_ASSERT(length >= 86);
            }
            quint32 unicodeRange[4] = {
                qFromBigEndian<quint32>(os2Table.data() + 42),
                qFromBigEndian<quint32>(os2Table.data() + 46),
                qFromBigEndian<quint32>(os2Table.data() + 50),
                qFromBigEndian<quint32>(os2Table.data() + 54)
            };
            quint32 codePageRange[2] = {
                qFromBigEndian<quint32>(os2Table.data() + 78),
                qFromBigEndian<quint32>(os2Table.data() + 82)
            };
            fd->writingSystems = QPlatformFontDatabase::writingSystemsFromTrueTypeBits(unicodeRange, codePageRange);
        }
    }

    if (styles) {
        if (CFNumberRef weightValue = (CFNumberRef) CFDictionaryGetValue(styles, kCTFontWeightTrait)) {
            double normalizedWeight;
            if (CFNumberGetValue(weightValue, kCFNumberFloat64Type, &normalizedWeight))
                fd->weight = QCoreTextFontEngine::qtWeightFromCFWeight(float(normalizedWeight));
        }
        if (CFNumberRef italic = (CFNumberRef) CFDictionaryGetValue(styles, kCTFontSlantTrait)) {
            double d;
            if (CFNumberGetValue(italic, kCFNumberDoubleType, &d)) {
                if (d > 0.0)
                    fd->style = QFont::StyleItalic;
            }
        }
        if (CFNumberRef symbolic = (CFNumberRef) CFDictionaryGetValue(styles, kCTFontSymbolicTrait)) {
            int d;
            if (CFNumberGetValue(symbolic, kCFNumberSInt32Type, &d)) {
                if (d & kCTFontMonoSpaceTrait)
                    fd->fixedPitch = true;
                if (d & kCTFontExpandedTrait)
                    fd->stretch = QFont::Expanded;
                else if (d & kCTFontCondensedTrait)
                    fd->stretch = QFont::Condensed;
            }
        }
    }

    if (QCFType<CFNumberRef> size = (CFNumberRef) CTFontDescriptorCopyAttribute(font, kCTFontSizeAttribute)) {
        if (CFNumberIsFloatType(size)) {
            double d;
            CFNumberGetValue(size, kCFNumberDoubleType, &d);
            fd->pointSize = d;
        } else {
            int i;
            CFNumberGetValue(size, kCFNumberIntType, &i);
            fd->pointSize = i;
        }
    }

    if (QCFType<CFArrayRef> languages = (CFArrayRef) CTFontDescriptorCopyAttribute(font, kCTFontLanguagesAttribute)) {
        CFIndex length = CFArrayGetCount(languages);
        for (int i = 1; i < LanguageCount; ++i) {
            if (!languageForWritingSystem[i])
                continue;
            QCFString lang = CFStringCreateWithCString(NULL, languageForWritingSystem[i], kCFStringEncodingASCII);
            if (CFArrayContainsValue(languages, CFRangeMake(0, length), lang))
                fd->writingSystems.setSupported(QFontDatabase::WritingSystem(i));
        }
    }
}

void QCoreTextFontDatabase::populateFromDescriptor(CTFontDescriptorRef font, const QString &familyName)
{
    FontDescription fd;
    getFontDescription(font, &fd);

    // Note: The familyName we are registering, and the family name of the font descriptor, may not
    // match, as CTFontDescriptorCreateMatchingFontDescriptors will return descriptors for replacement
    // fonts if a font family does not have any fonts available on the system.
    QString family = !familyName.isNull() ? familyName : static_cast<QString>(fd.familyName);

    CFRetain(font);
    QPlatformFontDatabase::registerFont(family, fd.styleName, fd.foundryName, fd.weight, fd.style, fd.stretch,
            true /* antialiased */, true /* scalable */, 0 /* pixelSize, ignored as font is scalable */,
            fd.fixedPitch, fd.writingSystems, (void *)font);
}

static NSString * const kQtFontDataAttribute = @"QtFontDataAttribute";

template <typename T>
T *descriptorAttribute(CTFontDescriptorRef descriptor, CFStringRef name)
{
    return [static_cast<T *>(CTFontDescriptorCopyAttribute(descriptor, name)) autorelease];
}

void QCoreTextFontDatabase::releaseHandle(void *handle)
{
    CTFontDescriptorRef descriptor = static_cast<CTFontDescriptorRef>(handle);
    if (NSValue *fontDataValue = descriptorAttribute<NSValue>(descriptor, (CFStringRef)kQtFontDataAttribute)) {
        QByteArray *fontData = static_cast<QByteArray *>(fontDataValue.pointerValue);
        delete fontData;
    }
    CFRelease(descriptor);
}

extern CGAffineTransform qt_transform_from_fontdef(const QFontDef &fontDef);

template <>
QFontEngine *QCoreTextFontDatabaseEngineFactory<QCoreTextFontEngine>::fontEngine(const QFontDef &fontDef, void *usrPtr)
{
    QCFType<CTFontDescriptorRef> descriptor = QCFType<CTFontDescriptorRef>::constructFromGet(
        static_cast<CTFontDescriptorRef>(usrPtr));

    // Since we do not pass in the destination DPI to CoreText when making
    // the font, we need to pass in a point size which is scaled to include
    // the DPI. The default DPI for the screen is 72, thus the scale factor
    // is destinationDpi / 72, but since pixelSize = pointSize / 72 * dpi,
    // the pixelSize is actually the scaled point size for the destination
    // DPI, and we can use that directly.
    qreal scaledPointSize = fontDef.pixelSize;

    CGAffineTransform matrix = qt_transform_from_fontdef(fontDef);
    if (QCFType<CTFontRef> font = CTFontCreateWithFontDescriptor(descriptor, scaledPointSize, &matrix))
        return new QCoreTextFontEngine(font, fontDef);

    return nullptr;
}

#ifndef QT_NO_FREETYPE
template <>
QFontEngine *QCoreTextFontDatabaseEngineFactory<QFontEngineFT>::fontEngine(const QFontDef &fontDef, void *usrPtr)
{
    CTFontDescriptorRef descriptor = static_cast<CTFontDescriptorRef>(usrPtr);

    if (NSValue *fontDataValue = descriptorAttribute<NSValue>(descriptor, (CFStringRef)kQtFontDataAttribute)) {
        QByteArray *fontData = static_cast<QByteArray *>(fontDataValue.pointerValue);
        return QFontEngineFT::create(*fontData, fontDef.pixelSize,
            static_cast<QFont::HintingPreference>(fontDef.hintingPreference));
    } else if (NSURL *url = descriptorAttribute<NSURL>(descriptor, kCTFontURLAttribute)) {
        Q_ASSERT(url.fileURL);
        QFontEngine::FaceId faceId;
        faceId.filename = QString::fromNSString(url.path).toUtf8();
        return QFontEngineFT::create(fontDef, faceId);
    }
    Q_UNREACHABLE();
}
#endif

template <class T>
QFontEngine *QCoreTextFontDatabaseEngineFactory<T>::fontEngine(const QByteArray &fontData, qreal pixelSize, QFont::HintingPreference hintingPreference)
{
    return T::create(fontData, pixelSize, hintingPreference);
}

// Explicitly instantiate so that we don't need the plugin to involve FreeType
template class QCoreTextFontDatabaseEngineFactory<QCoreTextFontEngine>;
#ifndef QT_NO_FREETYPE
template class QCoreTextFontDatabaseEngineFactory<QFontEngineFT>;
#endif

CTFontDescriptorRef descriptorForFamily(const QString &familyName)
{
    return CTFontDescriptorCreateWithAttributes(CFDictionaryRef(@{
        (id)kCTFontFamilyNameAttribute: familyName.toNSString()
    }));
}

CTFontDescriptorRef descriptorForFamily(const char *familyName)
{
    return descriptorForFamily(QString::fromLatin1(familyName));
}

CFArrayRef fallbacksForDescriptor(CTFontDescriptorRef descriptor)
{
    QCFType<CTFontRef> font = CTFontCreateWithFontDescriptor(descriptor, 0.0, nullptr);
    if (!font) {
        qCWarning(lcQpaFonts) << "Failed to create fallback font for" << descriptor;
        return nullptr;
    }

    CFArrayRef cascadeList = CFArrayRef(CTFontCopyDefaultCascadeListForLanguages(font,
        (CFArrayRef)[NSUserDefaults.standardUserDefaults stringArrayForKey:@"AppleLanguages"]));

    if (!cascadeList) {
        qCWarning(lcQpaFonts) << "Failed to create fallback cascade list for" << descriptor;
        return nullptr;
    }

    return cascadeList;
}

CFArrayRef QCoreTextFontDatabase::fallbacksForFamily(const QString &family)
{
    if (family.isEmpty())
        return nullptr;

    QCFType<CTFontDescriptorRef> fontDescriptor = descriptorForFamily(family);
    if (!fontDescriptor) {
        qCWarning(lcQpaFonts) << "Failed to create fallback font descriptor for" << family;
        return nullptr;
    }

    // If the font is not available we want to fall back to the style hint.
    // By creating a matching font descriptor we can verify whether the font
    // is available or not, and avoid CTFontCreateWithFontDescriptor picking
    // a default font for us based on incomplete information.
    fontDescriptor = CTFontDescriptorCreateMatchingFontDescriptor(fontDescriptor, 0);
    if (!fontDescriptor)
        return nullptr;

    return fallbacksForDescriptor(fontDescriptor);
}

CTFontDescriptorRef descriptorForFontType(CTFontUIFontType uiType)
{
    static const CGFloat kDefaultSizeForRequestedUIType = 0.0;
    QCFType<CTFontRef> ctFont = CTFontCreateUIFontForLanguage(
        uiType, kDefaultSizeForRequestedUIType, nullptr);
    return CTFontCopyFontDescriptor(ctFont);
}

CTFontDescriptorRef descriptorForStyle(QFont::StyleHint styleHint)
{
    switch (styleHint) {
        case QFont::SansSerif: return descriptorForFamily("Helvetica");
        case QFont::Serif: return descriptorForFamily("Times New Roman");
        case QFont::Monospace: return descriptorForFamily("Menlo");
#ifdef Q_OS_MACOS
        case QFont::Cursive: return descriptorForFamily("Apple Chancery");
#endif
        case QFont::Fantasy: return descriptorForFamily("Zapfino");
        case QFont::TypeWriter: return descriptorForFamily("American Typewriter");
        case QFont::AnyStyle: Q_FALLTHROUGH();
        case QFont::System: return descriptorForFontType(kCTFontUIFontSystem);
        default: return nullptr; // No matching font on this platform
    }
}

QStringList QCoreTextFontDatabase::fallbacksForFamily(const QString &family, QFont::Style style, QFont::StyleHint styleHint, QChar::Script script) const
{
    Q_UNUSED(style);

    qCDebug(lcQpaFonts).nospace() << "Resolving fallbacks families for"
        << (!family.isEmpty() ? qPrintable(QLatin1String(" family '%1' with").arg(family)) : "")
        << " style hint " << styleHint;

    QMacAutoReleasePool pool;

    QStringList fallbackList;

    QCFType<CFArrayRef> fallbackFonts = fallbacksForFamily(family);
    if (!fallbackFonts || !CFArrayGetCount(fallbackFonts)) {
        // We were not able to find a fallback for the specific family,
        // or the family was empty, so we fall back to the style hint.
        if (!family.isEmpty())
            qCDebug(lcQpaFonts) << "No fallbacks found. Using style hint instead";

        if (QCFType<CTFontDescriptorRef> styleDescriptor = descriptorForStyle(styleHint)) {
            CFMutableArrayRef tmp = CFArrayCreateMutable(kCFAllocatorDefault, 0, &kCFTypeArrayCallBacks);
            CFArrayAppendValue(tmp, styleDescriptor);
            QCFType<CFArrayRef> styleFallbacks = fallbacksForDescriptor(styleDescriptor);
            CFArrayAppendArray(tmp, styleFallbacks, CFRangeMake(0, CFArrayGetCount(styleFallbacks)));
            fallbackFonts = tmp;
        }
    }

    if (!fallbackFonts)
        return fallbackList;

    const int numberOfFallbacks = CFArrayGetCount(fallbackFonts);
    for (int i = 0; i < numberOfFallbacks; ++i) {
        auto fallbackDescriptor = CTFontDescriptorRef(CFArrayGetValueAtIndex(fallbackFonts, i));
        auto fallbackFamilyName = QCFString(CTFontDescriptorCopyAttribute(fallbackDescriptor, kCTFontFamilyNameAttribute));

        if (!isFamilyPopulated(fallbackFamilyName)) {
            // We need to populate, or at least register the fallback fonts,
            // otherwise the Qt font database may not know they exist.
            if (isPrivateFontFamily(fallbackFamilyName))
                const_cast<QCoreTextFontDatabase *>(this)->populateFromDescriptor(fallbackDescriptor);
            else
                registerFontFamily(fallbackFamilyName);
        }

        fallbackList.append(fallbackFamilyName);
    }

    // Some fallback fonts will have have an order in the list returned
    // by Core Text that would indicate they should be preferred for e.g.
    // Arabic, or Emoji, while in reality only supporting a tiny subset
    // of the required glyphs, or representing them by question marks.
    // Move these to the end, so that the proper fonts are preferred.
    for (const char *family : { ".Apple Symbols Fallback", ".Noto Sans Universal" }) {
        int index = fallbackList.indexOf(QLatin1String(family));
        if (index >= 0)
            fallbackList.move(index, fallbackList.size() - 1);
    }

#if defined(Q_OS_MACOS)
    // Since we are only returning a list of default fonts for the current language, we do not
    // cover all Unicode completely. This was especially an issue for some of the common script
    // symbols such as mathematical symbols, currency or geometric shapes. To minimize the risk
    // of missing glyphs, we add Arial Unicode MS as a final fail safe, since this covers most
    // of Unicode 2.1.
    if (!fallbackList.contains(QStringLiteral("Arial Unicode MS")))
        fallbackList.append(QStringLiteral("Arial Unicode MS"));
    // Since some symbols (specifically Braille) are not in Arial Unicode MS, we
    // add Apple Symbols to cover those too.
    if (!fallbackList.contains(QStringLiteral("Apple Symbols")))
        fallbackList.append(QStringLiteral("Apple Symbols"));
#endif

    extern QStringList qt_sort_families_by_writing_system(QChar::Script, const QStringList &);
    fallbackList = qt_sort_families_by_writing_system(script, fallbackList);

    qCDebug(lcQpaFonts).nospace() << "Fallback families ordered by script " << script << ": " << fallbackList;

    return fallbackList;
}

QStringList QCoreTextFontDatabase::addApplicationFont(const QByteArray &fontData, const QString &fileName)
{
    QCFType<CFArrayRef> fonts;

    if (!fontData.isEmpty()) {
        QCFType<CFDataRef> fontDataReference = fontData.toRawCFData();
        if (QCFType<CTFontDescriptorRef> descriptor = CTFontManagerCreateFontDescriptorFromData(fontDataReference)) {
            // There's no way to get the data back out of a font descriptor created with
            // CTFontManagerCreateFontDescriptorFromData, so we attach the data manually.
            NSDictionary *attributes = @{ kQtFontDataAttribute : [NSValue valueWithPointer:new QByteArray(fontData)] };
            descriptor = CTFontDescriptorCreateCopyWithAttributes(descriptor, (CFDictionaryRef)attributes);
            CFMutableArrayRef array = CFArrayCreateMutable(kCFAllocatorDefault, 0, &kCFTypeArrayCallBacks);
            CFArrayAppendValue(array, descriptor);
            fonts = array;
        }
    } else {
        QCFType<CFURLRef> fontURL = QUrl::fromLocalFile(fileName).toCFURL();
        fonts = CTFontManagerCreateFontDescriptorsFromURL(fontURL);
    }

    if (!fonts)
        return QStringList();

    QStringList families;
    const int numFonts = CFArrayGetCount(fonts);
    for (int i = 0; i < numFonts; ++i) {
        CTFontDescriptorRef fontDescriptor = CTFontDescriptorRef(CFArrayGetValueAtIndex(fonts, i));
        populateFromDescriptor(fontDescriptor);
        QCFType<CFStringRef> familyName = CFStringRef(CTFontDescriptorCopyAttribute(fontDescriptor, kCTFontFamilyNameAttribute));
        families.append(QString::fromCFString(familyName));
    }

    // Note: We don't do font matching via CoreText for application fonts, so we don't
    // need to enable font matching for them via CTFontManagerEnableFontDescriptors.

    return families;
}

bool QCoreTextFontDatabase::isPrivateFontFamily(const QString &family) const
{
    if (family.startsWith(QLatin1Char('.')) || family == QLatin1String("LastResort"))
        return true;

    return QPlatformFontDatabase::isPrivateFontFamily(family);
}

static CTFontUIFontType fontTypeFromTheme(QPlatformTheme::Font f)
{
    switch (f) {
    case QPlatformTheme::SystemFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::MenuFont:
    case QPlatformTheme::MenuBarFont:
    case QPlatformTheme::MenuItemFont:
        return kCTFontUIFontMenuItem;

    case QPlatformTheme::MessageBoxFont:
        return kCTFontUIFontEmphasizedSystem;

    case QPlatformTheme::LabelFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::TipLabelFont:
        return kCTFontUIFontToolTip;

    case QPlatformTheme::StatusBarFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::TitleBarFont:
        return kCTFontUIFontWindowTitle;

    case QPlatformTheme::MdiSubWindowTitleFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::DockWidgetTitleFont:
        return kCTFontUIFontSmallSystem;

    case QPlatformTheme::PushButtonFont:
        return kCTFontUIFontPushButton;

    case QPlatformTheme::CheckBoxFont:
    case QPlatformTheme::RadioButtonFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::ToolButtonFont:
        return kCTFontUIFontSmallToolbar;

    case QPlatformTheme::ItemViewFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::ListViewFont:
        return kCTFontUIFontViews;

    case QPlatformTheme::HeaderViewFont:
        return kCTFontUIFontSmallSystem;

    case QPlatformTheme::ListBoxFont:
        return kCTFontUIFontViews;

    case QPlatformTheme::ComboMenuItemFont:
        return kCTFontUIFontSystem;

    case QPlatformTheme::ComboLineEditFont:
        return kCTFontUIFontViews;

    case QPlatformTheme::SmallFont:
        return kCTFontUIFontSmallSystem;

    case QPlatformTheme::MiniFont:
        return kCTFontUIFontMiniSystem;

    case QPlatformTheme::FixedFont:
        return kCTFontUIFontUserFixedPitch;

    default:
        return kCTFontUIFontSystem;
    }
}

static CTFontDescriptorRef fontDescriptorFromTheme(QPlatformTheme::Font f)
{
#if defined(QT_PLATFORM_UIKIT)
    // Use Dynamic Type to resolve theme fonts if possible, to get
    // correct font sizes and style based on user configuration.
    NSString *textStyle = 0;
    switch (f) {
    case QPlatformTheme::TitleBarFont:
    case QPlatformTheme::HeaderViewFont:
        textStyle = UIFontTextStyleHeadline;
        break;
    case QPlatformTheme::MdiSubWindowTitleFont:
        textStyle = UIFontTextStyleSubheadline;
        break;
    case QPlatformTheme::TipLabelFont:
    case QPlatformTheme::SmallFont:
        textStyle = UIFontTextStyleFootnote;
        break;
    case QPlatformTheme::MiniFont:
        textStyle = UIFontTextStyleCaption2;
        break;
    case QPlatformTheme::FixedFont:
        // Fall back to regular code path, as iOS doesn't provide
        // an appropriate text style for this theme font.
        break;
    default:
        textStyle = UIFontTextStyleBody;
        break;
    }

    if (textStyle) {
        UIFontDescriptor *desc = [UIFontDescriptor preferredFontDescriptorWithTextStyle:textStyle];
        return static_cast<CTFontDescriptorRef>(CFBridgingRetain(desc));
    }
#endif // Q_OS_IOS, Q_OS_TVOS, Q_OS_WATCHOS

    // macOS default case and iOS fallback case
    return descriptorForFontType(fontTypeFromTheme(f));
}

const QHash<QPlatformTheme::Font, QFont *> &QCoreTextFontDatabase::themeFonts() const
{
    if (m_themeFonts.isEmpty()) {
        for (long f = QPlatformTheme::SystemFont; f < QPlatformTheme::NFonts; f++) {
            QPlatformTheme::Font ft = static_cast<QPlatformTheme::Font>(f);
            m_themeFonts.insert(ft, themeFont(ft));
        }
    }

    return m_themeFonts;
}

QFont *QCoreTextFontDatabase::themeFont(QPlatformTheme::Font f) const
{
    CTFontDescriptorRef fontDesc = fontDescriptorFromTheme(f);
    FontDescription fd;
    getFontDescription(fontDesc, &fd);

    if (!m_systemFontDescriptors.contains(fontDesc))
        m_systemFontDescriptors.insert(fontDesc);
    else
        CFRelease(fontDesc);

    QFont *font = new QFont(fd.familyName, fd.pointSize, fd.weight, fd.style == QFont::StyleItalic);
    return font;
}

QFont QCoreTextFontDatabase::defaultFont() const
{
    if (defaultFontName.isEmpty()) {
        QCFType<CTFontDescriptorRef> systemFont = descriptorForFontType(kCTFontUIFontSystem);
        defaultFontName = QCFString(CTFontDescriptorCopyAttribute(systemFont, kCTFontFamilyNameAttribute));
    }

    return QFont(defaultFontName);
}

bool QCoreTextFontDatabase::fontsAlwaysScalable() const
{
    return true;
}

QList<int> QCoreTextFontDatabase::standardSizes() const
{
    QList<int> ret;
    static const unsigned short standard[] =
        { 9, 10, 11, 12, 13, 14, 18, 24, 36, 48, 64, 72, 96, 144, 288, 0 };
    ret.reserve(int(sizeof(standard) / sizeof(standard[0])));
    const unsigned short *sizes = standard;
    while (*sizes) ret << *sizes++;
    return ret;
}

QT_END_NAMESPACE

