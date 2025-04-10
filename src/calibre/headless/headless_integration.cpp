#include <QtGlobal>
#include "headless_integration.h"
#include "headless_backingstore.h"
#ifdef __APPLE__
#include <QtGui/private/qcoretextfontdatabase_p.h>
class QCoreTextFontEngine;
#include <qpa/qplatformservices.h>
#include <QtCore/private/qeventdispatcher_unix_p.h>
#else
#include <QtGui/private/qfontconfigdatabase_p.h>
#endif

#ifdef Q_OS_WIN
#include <QtCore/private/qeventdispatcher_win_p.h>
#else
#include <QtGui/private/qgenericunixeventdispatcher_p.h>
#endif

#include <QtGui/private/qpixmap_raster_p.h>
#include <QtGui/private/qguiapplication_p.h>
#include <qpa/qplatformwindow.h>
#include <qpa/qplatformfontdatabase.h>
#include <qpa/qplatformtheme.h>
#include <qpa/qplatformnativeinterface.h>

QT_BEGIN_NAMESPACE


#ifndef __APPLE__
#if QT_VERSION < QT_VERSION_CHECK(6, 9, 0)
#include <QtGui/private/qgenericunixservices_p.h>
class GenericUnixServices : public QGenericUnixServices {
#else
#include <QtGui/private/qdesktopunixservices_p.h>
class GenericUnixServices : public QDesktopUnixServices {
#endif
    /* We must return desktop environment as UNKNOWN otherwise other parts of
     * Qt will try to query the nativeInterface() without checking if it exists
     * leading to a segfault.  For example, defaultHintStyleFromMatch() queries
     * the nativeInterface() without checking that it is NULL. See
     * https://bugreports.qt-project.org/browse/QTBUG-40946
     *
     * Also for the portal BS, we need to ignore openUrl and openDocument
     */
    QByteArray desktopEnvironment() const { return QByteArrayLiteral("UNKNOWN"); }
	bool openUrl(const QUrl &url) { Q_UNUSED(url); return false; }
	bool openDocument(const QUrl &url) { Q_UNUSED(url); return false; }
};
#endif

HeadlessIntegration::HeadlessIntegration(const QStringList &parameters)
{
    Q_UNUSED(parameters);
    HeadlessScreen *mPrimaryScreen = new HeadlessScreen();

    mPrimaryScreen->mGeometry = QRect(0, 0, 240, 320);
    mPrimaryScreen->mDepth = 32;
    mPrimaryScreen->mFormat = QImage::Format_ARGB32_Premultiplied;

#if (QT_VERSION >= QT_VERSION_CHECK(5, 13, 0))
    QWindowSystemInterface::handleScreenAdded(mPrimaryScreen);
#else
    screenAdded(mPrimaryScreen);
#endif

#ifdef __APPLE__
#if (QT_VERSION >= QT_VERSION_CHECK(5, 12, 0))
    m_fontDatabase.reset(new QCoreTextFontDatabaseEngineFactory<QCoreTextFontEngine>());
#else
    m_fontDatabase.reset(new QCoreTextFontDatabase());
#endif
#else
    m_fontDatabase.reset(new QFontconfigDatabase());
#endif

#ifdef __APPLE__
    platform_services.reset(new QPlatformServices());
#else
    platform_services.reset(new GenericUnixServices());
#endif
}

HeadlessIntegration::~HeadlessIntegration()
{
}

bool HeadlessIntegration::hasCapability(QPlatformIntegration::Capability cap) const
{
    switch (cap) {
    case ThreadedPixmaps: return true;
    case MultipleWindows: return true;
    case OpenGL: return false;
    case ThreadedOpenGL: return false;
    default: return QPlatformIntegration::hasCapability(cap);
    }
}

QPlatformOpenGLContext *HeadlessIntegration::createPlatformOpenGLContext(QOpenGLContext *context) const
{
    Q_UNUSED(context);
    // Suppress warnings about this plugin not supporting createPlatformOpenGLContext that come from the default implementation of this function
    return 0;
}

QPlatformFontDatabase *HeadlessIntegration::fontDatabase() const
{
    return m_fontDatabase.data();
}

QPlatformWindow *HeadlessIntegration::createPlatformWindow(QWindow *window) const
{
    Q_UNUSED(window);
    QPlatformWindow *w = new QPlatformWindow(window);
    w->requestActivateWindow();
    return w;
}

QPlatformBackingStore *HeadlessIntegration::createPlatformBackingStore(QWindow *window) const
{
    return new HeadlessBackingStore(window);
}

QAbstractEventDispatcher *HeadlessIntegration::createEventDispatcher() const
{
#ifdef __APPLE__
    return new QEventDispatcherUNIX();
#else
    return createUnixEventDispatcher();
#endif
}

QPlatformNativeInterface *HeadlessIntegration::nativeInterface() const
{
    if (!m_nativeInterface)
        m_nativeInterface.reset(new QPlatformNativeInterface);
    return m_nativeInterface.get();
}

HeadlessIntegration *HeadlessIntegration::instance()
{
    return static_cast<HeadlessIntegration *>(QGuiApplicationPrivate::platformIntegration());
}


#define THEME_NAME "headless"

QStringList HeadlessIntegration::themeNames() const { return QStringList(THEME_NAME); }

// Restrict the styles to "fusion" to prevent native styles requiring native
// window handles (eg Windows Vista style) from being used.
class HeadlessTheme : public QPlatformTheme
{
public:
	HeadlessTheme() {}

	QVariant themeHint(ThemeHint h) const override
	{
		switch (h) {
		case StyleNames:
			return QVariant(QStringList(QStringLiteral("fusion")));
		default:
			break;
		}
		return QPlatformTheme::themeHint(h);
	}
};

QPlatformTheme *HeadlessIntegration::createPlatformTheme(const QString &name) const
{
    return name == THEME_NAME ? new HeadlessTheme() : nullptr;
}

QT_END_NAMESPACE
