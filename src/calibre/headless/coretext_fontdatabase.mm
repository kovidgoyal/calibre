/****************************************************************************
**
** Copyright (C) 2015 The Qt Company Ltd.
** Contact: http://www.qt.io/licensing/
**
** This file is part of the plugins of the Qt Toolkit.
**
** $QT_BEGIN_LICENSE:LGPL21$
** Commercial License Usage
** Licensees holding valid commercial Qt licenses may use this file in
** accordance with the commercial license agreement provided with the
** Software or, alternatively, in accordance with the terms contained in
** a written agreement between you and The Qt Company. For licensing terms
** and conditions see http://www.qt.io/terms-conditions. For further
** information use the contact form at http://www.qt.io/contact-us.
**
** GNU Lesser General Public License Usage
** Alternatively, this file may be used under the terms of the GNU Lesser
** General Public License version 2.1 or version 3 as published by the Free
** Software Foundation and appearing in the file LICENSE.LGPLv21 and
** LICENSE.LGPLv3 included in the packaging of this file. Please review the
** following information to ensure the GNU Lesser General Public License
** requirements will be met: https://www.gnu.org/licenses/lgpl.html and
** http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
**
** As a special exception, The Qt Company gives you certain additional
** rights. These rights are described in The Qt Company LGPL Exception
** version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
**
** $QT_END_LICENSE$
**
****************************************************************************/

#include "qglobal.h"

#include <sys/param.h>

#if defined(Q_OS_MACX)
#import <Cocoa/Cocoa.h>
#import <IOKit/graphics/IOGraphicsLib.h>
#elif defined(Q_OS_IOS)
#import <UIKit/UIFont.h>
#endif

#include <QtPlatformSupport/private/qcoretextfontdatabase_p.h>
#include <QtPlatformSupport/private/qfontengine_coretext_p.h>
#include <QtCore/QSettings>
#include <QtCore/QtEndian>
#ifndef QT_NO_FREETYPE
#include <QtGui/private/qfontengine_ft_p.h>
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

#ifdef Q_OS_OSX
static NSInteger languageMapSort(id obj1, id obj2, void *context)
{
    NSArray *map1 = (NSArray *) obj1;
    NSArray *map2 = (NSArray *) obj2;
    NSArray *languages = (NSArray *) context;

    NSString *lang1 = [map1 objectAtIndex: 0];
    NSString *lang2 = [map2 objectAtIndex: 0];

    return [languages indexOfObject: lang1] - [languages indexOfObject: lang2];
}
#endif

QCoreTextFontDatabase::QCoreTextFontDatabase(bool useFreeType)
#ifndef QT_NO_FREETYPE
    : m_useFreeType(useFreeType)
#endif
{
    Q_UNUSED(useFreeType)
    QCoreTextFontEngine::defaultGlyphFormat = QFontEngine::Format_A8;
}

QCoreTextFontDatabase::~QCoreTextFontDatabase()
{
    foreach (CTFontDescriptorRef ref, m_systemFontDescriptors)
        CFRelease(ref);
}

static CFArrayRef availableFamilyNames()
{
#if defined(Q_OS_OSX)
    return CTFontManagerCopyAvailableFontFamilyNames();
#elif defined(Q_OS_IOS)
    return (CFArrayRef) [[UIFont familyNames] retain];
#endif
}

void QCoreTextFontDatabase::populateFontDatabase()
{
    // The caller (QFontDB) expects the db to be populate only with system fonts, so we need
    // to make sure that any previously registered app fonts become invisible.
    removeApplicationFonts();

    QCFType<CFArrayRef> familyNames = availableFamilyNames();
    const int numberOfFamilies = CFArrayGetCount(familyNames);
    for (int i = 0; i < numberOfFamilies; ++i) {
        CFStringRef familyNameRef = (CFStringRef) CFArrayGetValueAtIndex(familyNames, i);
        QString familyName = QCFString::toQString(familyNameRef);

        // Don't populate internal fonts
        if (familyName.startsWith(QLatin1Char('.')) || familyName == QLatin1String("LastResort"))
            continue;

#if defined(Q_OS_IOS) || defined(Q_OS_TVOS)
        // Skip font families with no corresponding fonts
        if (![UIFont fontNamesForFamilyName:(NSString*)familyNameRef].count)
            continue;
#endif

        QPlatformFontDatabase::registerFontFamily(familyName);

#if defined(Q_OS_OSX)
        QString localizedFamilyName = QString::fromNSString([[NSFontManager sharedFontManager] localizedNameForFamily:(NSString*)familyNameRef face:nil]);
        if (familyName != localizedFamilyName)
            QPlatformFontDatabase::registerAliasToFontFamily(familyName, localizedFamilyName);
#endif
    }

    // Force creating the theme fonts to get the descriptors in m_systemFontDescriptors
    if (m_themeFonts.isEmpty())
        (void)themeFonts();

    Q_FOREACH (CTFontDescriptorRef fontDesc, m_systemFontDescriptors)
        populateFromDescriptor(fontDesc);
}

void QCoreTextFontDatabase::populateFamily(const QString &familyName)
{
    QCFType<CFMutableDictionaryRef> attributes = CFDictionaryCreateMutable(kCFAllocatorDefault, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFDictionaryAddValue(attributes, kCTFontFamilyNameAttribute, QCFString(familyName));
    QCFType<CTFontDescriptorRef> nameOnlyDescriptor = CTFontDescriptorCreateWithAttributes(attributes);

    // A single family might match several different fonts with different styles eg.
    QCFType<CFArrayRef> matchingFonts = (CFArrayRef) CTFontDescriptorCreateMatchingFontDescriptors(nameOnlyDescriptor, 0);
    if (!matchingFonts) {
        qWarning() << "QCoreTextFontDatabase: Found no matching fonts for family" << familyName;
        return;
    }

    const int numFonts = CFArrayGetCount(matchingFonts);
    for (int i = 0; i < numFonts; ++i)
        populateFromDescriptor(CTFontDescriptorRef(CFArrayGetValueAtIndex(matchingFonts, i)));
}

struct FontDescription {
    QCFString familyName;
    QCFString styleName;
    QString foundryName;
    QFont::Weight weight;
    QFont::Style style;
    QFont::Stretch stretch;
    int pixelSize;
    bool fixedPitch;
    QSupportedWritingSystems writingSystems;
};

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
            float normalizedWeight;
            if (CFNumberGetValue(weightValue, kCFNumberFloatType, &normalizedWeight))
                fd->weight = QCoreTextFontEngine::qtWeightFromCFWeight(normalizedWeight);
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
            fd->pixelSize = d;
        } else {
            CFNumberGetValue(size, kCFNumberIntType, &fd->pixelSize);
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

void QCoreTextFontDatabase::populateFromDescriptor(CTFontDescriptorRef font)
{
    FontDescription fd;
    getFontDescription(font, &fd);

    CFRetain(font);
    QPlatformFontDatabase::registerFont(fd.familyName, fd.styleName, fd.foundryName, fd.weight, fd.style, fd.stretch,
            true /* antialiased */, true /* scalable */,
            fd.pixelSize, fd.fixedPitch, fd.writingSystems, (void *) font);
}

void QCoreTextFontDatabase::releaseHandle(void *handle)
{
    CFRelease(CTFontDescriptorRef(handle));
}

#ifndef QT_NO_FREETYPE
static QByteArray filenameForCFUrl(CFURLRef url)
{
    // The on-stack buffer prevents that a QByteArray allocated for the worst case (MAXPATHLEN)
    // stays around for the lifetime of the font. Additionally, it helps to move the char
    // signedness cast to an acceptable place.
    uchar buffer[MAXPATHLEN];
    QByteArray filename;

    if (!CFURLGetFileSystemRepresentation(url, true, buffer, sizeof(buffer))) {
        qWarning("QCoreTextFontDatabase::filenameForCFUrl: could not resolve file for URL %s",
                 url ? qPrintable(QString::fromCFString(CFURLGetString(url))) : "(null)");
    } else {
        QCFType<CFStringRef> scheme = CFURLCopyScheme(url);
        if (QString::fromCFString(scheme) == QLatin1String("qrc"))
            filename = ":";

        filename += reinterpret_cast<char *>(buffer);
    }

    return filename;
}
#endif

extern CGAffineTransform qt_transform_from_fontdef(const QFontDef &fontDef);

QFontEngine *QCoreTextFontDatabase::fontEngine(const QFontDef &f, void *usrPtr)
{
    CTFontDescriptorRef descriptor = static_cast<CTFontDescriptorRef>(usrPtr);

#ifndef QT_NO_FREETYPE
    if (m_useFreeType) {
        QCFType<CFURLRef> url(static_cast<CFURLRef>(CTFontDescriptorCopyAttribute(descriptor, kCTFontURLAttribute)));

        QByteArray filename;
        if (url)
            filename = filenameForCFUrl(url);

        return freeTypeFontEngine(f, filename);
    }
#endif

    // Since we do not pass in the destination DPI to CoreText when making
    // the font, we need to pass in a point size which is scaled to include
    // the DPI. The default DPI for the screen is 72, thus the scale factor
    // is destinationDpi / 72, but since pixelSize = pointSize / 72 * dpi,
    // the pixelSize is actually the scaled point size for the destination
    // DPI, and we can use that directly.
    qreal scaledPointSize = f.pixelSize;

    CGAffineTransform matrix = qt_transform_from_fontdef(f);
    CTFontRef font = CTFontCreateWithFontDescriptor(descriptor, scaledPointSize, &matrix);
    if (font) {
        QFontEngine *engine = new QCoreTextFontEngine(font, f);
        engine->fontDef = f;
        CFRelease(font);
        return engine;
    }

    return NULL;
}

static void releaseFontData(void* info, const void* data, size_t size)
{
    Q_UNUSED(data);
    Q_UNUSED(size);
    delete (QByteArray*)info;
}

QFontEngine *QCoreTextFontDatabase::fontEngine(const QByteArray &fontData, qreal pixelSize, QFont::HintingPreference hintingPreference)
{
#ifndef QT_NO_FREETYPE
    if (m_useFreeType) {
        QByteArray *fontDataCopy = new QByteArray(fontData);
        QCFType<CGDataProviderRef> dataProvider = CGDataProviderCreateWithData(fontDataCopy,
                fontDataCopy->constData(), fontDataCopy->size(), releaseFontData);
        QCFType<CGFontRef> cgFont(CGFontCreateWithDataProvider(dataProvider));

        if (!cgFont) {
            qWarning("QCoreTextFontDatabase::fontEngine: CGFontCreateWithDataProvider failed");
            return nullptr;
        }

        QFontDef fontDef;
        fontDef.pixelSize = pixelSize;
        fontDef.pointSize = pixelSize * 72.0 / qt_defaultDpi();
        fontDef.hintingPreference = hintingPreference;
        CGAffineTransform transform = qt_transform_from_fontdef(fontDef);
        QCFType<CTFontRef> ctFont(CTFontCreateWithGraphicsFont(cgFont, fontDef.pixelSize, &transform, nullptr));
        QCFType<CFURLRef> url(static_cast<CFURLRef>(CTFontCopyAttribute(ctFont, kCTFontURLAttribute)));
        return freeTypeFontEngine(fontDef, filenameForCFUrl(url), fontData);
    }
#endif

    Q_UNUSED(hintingPreference);

    QByteArray* fontDataCopy = new QByteArray(fontData);
    QCFType<CGDataProviderRef> dataProvider = CGDataProviderCreateWithData(fontDataCopy,
            fontDataCopy->constData(), fontDataCopy->size(), releaseFontData);

    CGFontRef cgFont = CGFontCreateWithDataProvider(dataProvider);

    QFontEngine *fontEngine = NULL;
    if (cgFont == NULL) {
        qWarning("QCoreTextFontDatabase::fontEngine: CGFontCreateWithDataProvider failed");
    } else {
        QFontDef def;
        def.pixelSize = pixelSize;
        def.pointSize = pixelSize * 72.0 / qt_defaultDpi();
        fontEngine = new QCoreTextFontEngine(cgFont, def);
        CFRelease(cgFont);
    }

    return fontEngine;
}

QFont::StyleHint styleHintFromNSString(NSString *style)
{
    if ([style isEqual: @"sans-serif"])
        return QFont::SansSerif;
    else if ([style isEqual: @"monospace"])
        return QFont::Monospace;
    else if ([style isEqual: @"cursive"])
        return QFont::Cursive;
    else if ([style isEqual: @"serif"])
        return QFont::Serif;
    else if ([style isEqual: @"fantasy"])
        return QFont::Fantasy;
    else // if ([style isEqual: @"default"])
        return QFont::AnyStyle;
}

#ifdef Q_OS_OSX
static QString familyNameFromPostScriptName(NSString *psName)
{
    QCFType<CTFontDescriptorRef> fontDescriptor = (CTFontDescriptorRef) CTFontDescriptorCreateWithNameAndSize((CFStringRef)psName, 12.0);
    QCFString familyName = (CFStringRef) CTFontDescriptorCopyAttribute(fontDescriptor, kCTFontFamilyNameAttribute);
    QString name = QCFString::toQString(familyName);
    if (name.isEmpty())
        qWarning() << "QCoreTextFontDatabase: Failed to resolve family name for PostScript name " << QCFString::toQString((CFStringRef)psName);

    return name;
}
#endif

QStringList QCoreTextFontDatabase::fallbacksForFamily(const QString &family, QFont::Style style, QFont::StyleHint styleHint, QChar::Script script) const
{
    Q_UNUSED(style);
    Q_UNUSED(script);

    QMacAutoReleasePool pool;

    static QHash<QString, QStringList> fallbackLists;

    if (!family.isEmpty()) {
#if QT_MAC_PLATFORM_SDK_EQUAL_OR_ABOVE(__MAC_10_8, __IPHONE_6_0)
      // CTFontCopyDefaultCascadeListForLanguages is available in the SDK
  #if QT_MAC_DEPLOYMENT_TARGET_BELOW(__MAC_10_8, __IPHONE_6_0)
        // But we have to feature check at runtime
        if (&CTFontCopyDefaultCascadeListForLanguages)
  #endif
        {
            QCFType<CFMutableDictionaryRef> attributes = CFDictionaryCreateMutable(kCFAllocatorDefault, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
            CFDictionaryAddValue(attributes, kCTFontFamilyNameAttribute, QCFString(family));
            if (QCFType<CTFontDescriptorRef> fontDescriptor = CTFontDescriptorCreateWithAttributes(attributes)) {
                if (QCFType<CTFontRef> font = CTFontCreateWithFontDescriptor(fontDescriptor, 12.0, 0)) {
                    NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
                    NSArray *languages = [defaults stringArrayForKey: @"AppleLanguages"];

                    QCFType<CFArrayRef> cascadeList = (CFArrayRef) CTFontCopyDefaultCascadeListForLanguages(font, (CFArrayRef) languages);
                    if (cascadeList) {
                        QStringList fallbackList;
                        const int numCascades = CFArrayGetCount(cascadeList);
                        for (int i = 0; i < numCascades; ++i) {
                            CTFontDescriptorRef fontFallback = (CTFontDescriptorRef) CFArrayGetValueAtIndex(cascadeList, i);
                            QCFString fallbackFamilyName = (CFStringRef) CTFontDescriptorCopyAttribute(fontFallback, kCTFontFamilyNameAttribute);
                            fallbackList.append(QCFString::toQString(fallbackFamilyName));
                        }

#if defined(Q_OS_OSX)
                        // Since we are only returning a list of default fonts for the current language, we do not
                        // cover all unicode completely. This was especially an issue for some of the common script
                        // symbols such as mathematical symbols, currency or geometric shapes. To minimize the risk
                        // of missing glyphs, we add Arial Unicode MS as a final fail safe, since this covers most
                        // of Unicode 2.1.
                        if (!fallbackList.contains(QStringLiteral("Arial Unicode MS")))
                            fallbackList.append(QStringLiteral("Arial Unicode MS"));
#endif

                        return fallbackList;
                    }
                }
            }
        }
#endif
    }

    // We were not able to find a fallback for the specific family,
    // so we fall back to the stylehint.

    static const QString styleLookupKey = QString::fromLatin1(".QFontStyleHint_%1");

    static bool didPopulateStyleFallbacks = false;
    if (!didPopulateStyleFallbacks) {
#if defined(Q_OS_MACX)
        NSUserDefaults *defaults = [NSUserDefaults standardUserDefaults];
        NSArray *languages = [defaults stringArrayForKey: @"AppleLanguages"];

        NSDictionary *fallbackDict = [NSDictionary dictionaryWithContentsOfFile: @"/System/Library/Frameworks/ApplicationServices.framework/Frameworks/CoreText.framework/Resources/DefaultFontFallbacks.plist"];

        for (NSString *style in [fallbackDict allKeys]) {
            NSArray *list = [fallbackDict valueForKey: style];
            QFont::StyleHint fallbackStyleHint = styleHintFromNSString(style);
            QStringList fallbackList;
            for (id item in list) {
                // sort the array based on system language preferences
                if ([item isKindOfClass: [NSArray class]]) {
                    NSArray *langs = [(NSArray *) item sortedArrayUsingFunction: languageMapSort
                                                                        context: languages];
                    for (NSArray *map in langs)
                        fallbackList.append(familyNameFromPostScriptName([map objectAtIndex: 1]));
                }
                else if ([item isKindOfClass: [NSString class]])
                    fallbackList.append(familyNameFromPostScriptName(item));
            }

            fallbackList.append(QLatin1String("Apple Color Emoji"));

            // Since we are only returning a list of default fonts for the current language, we do not
            // cover all unicode completely. This was especially an issue for some of the common script
            // symbols such as mathematical symbols, currency or geometric shapes. To minimize the risk
            // of missing glyphs, we add Arial Unicode MS as a final fail safe, since this covers most
            // of Unicode 2.1.
            if (!fallbackList.contains(QStringLiteral("Arial Unicode MS")))
                fallbackList.append(QStringLiteral("Arial Unicode MS"));

            fallbackLists[styleLookupKey.arg(fallbackStyleHint)] = fallbackList;
        }
#else
        QStringList staticFallbackList;
        staticFallbackList << QString::fromLatin1("Helvetica,Apple Color Emoji,Geeza Pro,Arial Hebrew,Thonburi,Kailasa"
            "Hiragino Kaku Gothic ProN,.Heiti J,Apple SD Gothic Neo,.Heiti K,Heiti SC,Heiti TC"
            "Bangla Sangam MN,Devanagari Sangam MN,Gujarati Sangam MN,Gurmukhi MN,Kannada Sangam MN"
            "Malayalam Sangam MN,Oriya Sangam MN,Sinhala Sangam MN,Tamil Sangam MN,Telugu Sangam MN"
            "Euphemia UCAS,.PhoneFallback").split(QLatin1String(","));

        for (int i = QFont::Helvetica; i <= QFont::Fantasy; ++i)
            fallbackLists[styleLookupKey.arg(i)] = staticFallbackList;
#endif

        didPopulateStyleFallbacks = true;
    }

    Q_ASSERT(!fallbackLists.isEmpty());
    return fallbackLists[styleLookupKey.arg(styleHint)];
}

#if HAVE_CORETEXT
static CFArrayRef createDescriptorArrayForFont(CTFontRef font, const QString &fileName = QString())
{
    CFMutableArrayRef array = CFArrayCreateMutable(kCFAllocatorDefault, 0, &kCFTypeArrayCallBacks);
    QCFType<CTFontDescriptorRef> descriptor = CTFontCopyFontDescriptor(font);

    Q_UNUSED(fileName)
#ifndef QT_NO_FREETYPE
    // The physical font source URL (usually a local file or Qt resource) is only required for
    // FreeType, when using non-system fonts, and needs some hackery to attach in a format
    // agreeable to OSX.
    if (!fileName.isEmpty()) {
        QCFType<CFURLRef> fontURL;

        if (fileName.startsWith(QLatin1String(":/"))) {
            // QUrl::fromLocalFile() doesn't accept qrc pseudo-paths like ":/fonts/myfont.ttf".
            // Therefore construct from QString with the qrc:// scheme -> "qrc:///fonts/myfont.ttf".
            fontURL = QUrl(QStringLiteral("qrc://") + fileName.mid(1)).toCFURL();
        } else if (!fileName.isEmpty()) {
            // At this point we hope that filename is in a format that QUrl can handle.
            fontURL = QUrl::fromLocalFile(fileName).toCFURL();
        }

        QCFType<CFMutableDictionaryRef> attributes = CFDictionaryCreateMutable(kCFAllocatorDefault, 1,
            &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
        CFDictionaryAddValue(attributes, kCTFontURLAttribute, fontURL);
        descriptor = CTFontDescriptorCreateCopyWithAttributes(descriptor, attributes);
    }
#endif

    CFArrayAppendValue(array, descriptor);
    return array;
}
#endif

QStringList QCoreTextFontDatabase::addApplicationFont(const QByteArray &fontData, const QString &fileName)
{
    QCFType<CFArrayRef> fonts;
    QStringList families;

#if HAVE_CORETEXT
    if (&CTFontManagerRegisterGraphicsFont) {
        CFErrorRef error = 0;
        if (!fontData.isEmpty()) {
            QByteArray* fontDataCopy = new QByteArray(fontData);
            QCFType<CGDataProviderRef> dataProvider = CGDataProviderCreateWithData(fontDataCopy,
                    fontDataCopy->constData(), fontDataCopy->size(), releaseFontData);
            QCFType<CGFontRef> cgFont = CGFontCreateWithDataProvider(dataProvider);
            if (cgFont) {
                if (CTFontManagerRegisterGraphicsFont(cgFont, &error)) {
                    QCFType<CTFontRef> font = CTFontCreateWithGraphicsFont(cgFont, 0.0, NULL, NULL);
                    fonts = createDescriptorArrayForFont(font
#ifndef QT_NO_FREETYPE
                                                         , m_useFreeType ? fileName : QString()
#endif
                                                         );
                    m_applicationFonts.append(QVariant::fromValue(QCFType<CGFontRef>::constructFromGet(cgFont)));
                }
            }
        } else {
            QCFType<CFURLRef> fontURL = CFURLCreateWithFileSystemPath(NULL, QCFString(fileName), kCFURLPOSIXPathStyle, false);
            if (CTFontManagerRegisterFontsForURL(fontURL, kCTFontManagerScopeProcess, &error)) {
#if QT_MAC_PLATFORM_SDK_EQUAL_OR_ABOVE(__MAC_10_6, __IPHONE_7_0)
                if (&CTFontManagerCreateFontDescriptorsFromURL)
                    fonts = CTFontManagerCreateFontDescriptorsFromURL(fontURL);
                else
#endif
                {
                    // We're limited to a single font per file, unless we dive into the font tables
                    QCFType<CFMutableDictionaryRef> attributes = CFDictionaryCreateMutable(kCFAllocatorDefault, 1,
                        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
                    CFDictionaryAddValue(attributes, kCTFontURLAttribute, fontURL);
                    QCFType<CTFontDescriptorRef> descriptor = CTFontDescriptorCreateWithAttributes(attributes);
                    QCFType<CTFontRef> font = CTFontCreateWithFontDescriptor(descriptor, 0.0, NULL);
                    fonts = createDescriptorArrayForFont(font);
                }

                m_applicationFonts.append(QVariant::fromValue(QCFType<CFURLRef>::constructFromGet(fontURL)));
            }
        }

        if (error) {
            NSLog(@"Unable to register font: %@", error);
            CFRelease(error);
        }
    }
#endif
#if HAVE_CORETEXT && HAVE_ATS
    else
#endif
#if HAVE_ATS
    {
        ATSFontContainerRef fontContainer;
        OSStatus e;

        if (!fontData.isEmpty()) {
            e = ATSFontActivateFromMemory((void *) fontData.constData(), fontData.size(),
                                          kATSFontContextLocal, kATSFontFormatUnspecified, NULL,
                                          kATSOptionFlagsDefault, &fontContainer);
        } else {
            FSRef ref;
            if (FSPathMakeRef(reinterpret_cast<const UInt8 *>(fileName.toUtf8().constData()),
                              &ref, 0) != noErr)
                return QStringList();
            e = ATSFontActivateFromFileReference(&ref, kATSFontContextLocal, kATSFontFormatUnspecified, 0,
                                                 kATSOptionFlagsDefault, &fontContainer);
        }

        if (e == noErr) {
            ItemCount fontCount = 0;
            e = ATSFontFindFromContainer(fontContainer, kATSOptionFlagsDefault, 0, 0, &fontCount);
            if (e != noErr)
                return QStringList();

            QVarLengthArray<ATSFontRef> containedFonts(fontCount);
            e = ATSFontFindFromContainer(fontContainer, kATSOptionFlagsDefault, fontCount, containedFonts.data(), &fontCount);
            if (e != noErr)
                return QStringList();

            CFMutableArrayRef fontsArray = CFArrayCreateMutable(NULL, 0, &kCFTypeArrayCallBacks);
            for (int i = 0; i < containedFonts.size(); ++i) {
                QCFType<CTFontRef> font = CTFontCreateWithPlatformFont(containedFonts[i], 12.0, NULL, NULL);
                CFArrayAppendValue(fontsArray, QCFType<CTFontDescriptorRef>(CTFontCopyFontDescriptor(font)));
            }

            fonts = fontsArray;

            m_applicationFonts.append(QVariant::fromValue(fontContainer));
        }
    }
#endif

    if (fonts) {
        const int numFonts = CFArrayGetCount(fonts);
        for (int i = 0; i < numFonts; ++i) {
            CTFontDescriptorRef fontDescriptor = CTFontDescriptorRef(CFArrayGetValueAtIndex(fonts, i));
            populateFromDescriptor(fontDescriptor);
            QCFType<CFStringRef> familyName = CFStringRef(CTFontDescriptorCopyAttribute(fontDescriptor, kCTFontFamilyNameAttribute));
            families.append(QCFString(familyName));
        }
    }

    return families;
}

bool QCoreTextFontDatabase::isPrivateFontFamily(const QString &family) const
{
    if (family.startsWith(QLatin1Char('.')))
        return true;

    return QPlatformFontDatabase::isPrivateFontFamily(family);
}

static CTFontUIFontType fontTypeFromTheme(QPlatformTheme::Font f)
{
    switch (f) {
    case QPlatformTheme::SystemFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::MenuFont:
    case QPlatformTheme::MenuBarFont:
    case QPlatformTheme::MenuItemFont:
        return kCTFontMenuItemFontType;

    case QPlatformTheme::MessageBoxFont:
        return kCTFontEmphasizedSystemFontType;

    case QPlatformTheme::LabelFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::TipLabelFont:
        return kCTFontToolTipFontType;

    case QPlatformTheme::StatusBarFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::TitleBarFont:
        return kCTFontWindowTitleFontType;

    case QPlatformTheme::MdiSubWindowTitleFont:
    case QPlatformTheme::DockWidgetTitleFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::PushButtonFont:
        return kCTFontPushButtonFontType;

    case QPlatformTheme::CheckBoxFont:
    case QPlatformTheme::RadioButtonFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::ToolButtonFont:
        return kCTFontSmallToolbarFontType;

    case QPlatformTheme::ItemViewFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::ListViewFont:
        return kCTFontViewsFontType;

    case QPlatformTheme::HeaderViewFont:
        return kCTFontSmallSystemFontType;

    case QPlatformTheme::ListBoxFont:
        return kCTFontViewsFontType;

    case QPlatformTheme::ComboMenuItemFont:
        return kCTFontSystemFontType;

    case QPlatformTheme::ComboLineEditFont:
        return kCTFontViewsFontType;

    case QPlatformTheme::SmallFont:
        return kCTFontSmallSystemFontType;

    case QPlatformTheme::MiniFont:
        return kCTFontMiniSystemFontType;

    case QPlatformTheme::FixedFont:
        return kCTFontUserFixedPitchFontType;

    default:
        return kCTFontSystemFontType;
    }
}

static CTFontDescriptorRef fontDescriptorFromTheme(QPlatformTheme::Font f)
{
#ifdef Q_OS_IOS
    if (QSysInfo::MacintoshVersion >= QSysInfo::MV_IOS_7_0) {
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
    }
#endif // Q_OS_IOS

    // OSX default case and iOS fallback case
    CTFontUIFontType fontType = fontTypeFromTheme(f);
    QCFType<CTFontRef> ctFont = CTFontCreateUIFontForLanguage(fontType, 0.0, NULL);
    return CTFontCopyFontDescriptor(ctFont);
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

    QFont *font = new QFont(fd.familyName, fd.pixelSize, fd.weight, fd.style == QFont::StyleItalic);
    return font;
}

QFont QCoreTextFontDatabase::defaultFont() const
{
    if (defaultFontName.isEmpty()) {
        QCFType<CTFontRef> font = CTFontCreateUIFontForLanguage(kCTFontSystemFontType, 12.0, NULL);
        defaultFontName = (QString) QCFString(CTFontCopyFullName(font));
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

void QCoreTextFontDatabase::removeApplicationFonts()
{
    if (m_applicationFonts.isEmpty())
        return;

    foreach (const QVariant &font, m_applicationFonts) {
#if HAVE_CORETEXT
        if (&CTFontManagerUnregisterGraphicsFont && &CTFontManagerUnregisterFontsForURL) {
            CFErrorRef error;
            if (font.canConvert(qMetaTypeId<QCFType<CGFontRef> >())) {
                CTFontManagerUnregisterGraphicsFont(font.value<QCFType<CGFontRef> >(), &error);
            } else if (font.canConvert(qMetaTypeId<QCFType<CFURLRef> >())) {
                CTFontManagerUnregisterFontsForURL(font.value<QCFType<CFURLRef> >(), kCTFontManagerScopeProcess, &error);
            }
        }
#endif
#if HAVE_CORETEXT && HAVE_ATS
        else
#endif
#if HAVE_ATS
        if (font.canConvert(qMetaTypeId<ATSFontContainerRef>())) {
            ATSFontDeactivate(font.value<ATSFontContainerRef>(), 0, kATSOptionFlagsDoNotNotify);
        }
#endif
    }

    m_applicationFonts.clear();

#if HAVE_ATS
    ATSFontNotify(kATSFontNotifyActionFontsChanged, 0);
#endif
}

#ifndef QT_NO_FREETYPE
QFontEngine *QCoreTextFontDatabase::freeTypeFontEngine(const QFontDef &fontDef, const QByteArray &filename,
                                                       const QByteArray &fontData)
{
    QFontEngine::FaceId faceId;
    faceId.filename = filename;
    const bool antialias = !(fontDef.styleStrategy & QFont::NoAntialias);

    QScopedPointer<QFontEngineFT> engine(new QFontEngineFT(fontDef));
    QFontEngineFT::GlyphFormat format = QFontEngineFT::Format_Mono;
    if (antialias) {
        QFontEngine::SubpixelAntialiasingType subpixelType = subpixelAntialiasingTypeHint();
        if (subpixelType == QFontEngine::Subpixel_None || (fontDef.styleStrategy & QFont::NoSubpixelAntialias)) {
            format = QFontEngineFT::Format_A8;
            engine->subpixelType = QFontEngine::Subpixel_None;
        } else {
            format = QFontEngineFT::Format_A32;
            engine->subpixelType = subpixelType;
        }
    }

    if (!engine->init(faceId, antialias, format, fontData) || engine->invalid()) {
        qWarning() << "QCoreTextFontDatabase::freeTypefontEngine Failed to create engine";
        return nullptr;
    }
    engine->setQtDefaultHintStyle(static_cast<QFont::HintingPreference>(fontDef.hintingPreference));

    return engine.take();
}
#endif

QT_END_NAMESPACE

