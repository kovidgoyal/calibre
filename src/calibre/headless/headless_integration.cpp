#include <QtGlobal>
#include "headless_integration.h"
#include "headless_backingstore.h"
#ifdef __APPLE__
#include <QtPlatformSupport/private/qcoretextfontdatabase_p.h>
#include <qpa/qplatformservices.h>
#include <QtCore/private/qeventdispatcher_unix_p.h>
#else
#if (QT_VERSION >= QT_VERSION_CHECK(5, 4, 1))
#include "fontconfig_database.h"
#else
#if (QT_VERSION >= QT_VERSION_CHECK(5, 8, 0))
#include <QtFontDatabaseSupport/private/qfontconfigdatabase_p.h>
#else
#include <QtPlatformSupport/private/qfontconfigdatabase_p.h>
#endif
#endif
#ifndef Q_OS_WIN
#if (QT_VERSION >= QT_VERSION_CHECK(5, 8, 0))
#include <QtEventDispatcherSupport/private/qgenericunixeventdispatcher_p.h>
#else
#include <QtPlatformSupport/private/qgenericunixeventdispatcher_p.h>
#endif
#else
#include <QtCore/private/qeventdispatcher_win_p.h>
#endif
#endif

#include <QtGui/private/qpixmap_raster_p.h>
#include <QtGui/private/qguiapplication_p.h>
#include <qpa/qplatformwindow.h>
#include <qpa/qplatformfontdatabase.h>

QT_BEGIN_NAMESPACE

#ifndef __APPLE__
class GenericUnixServices : public QGenericUnixServices {
    /* We must return desktop environment as UNKNOWN otherwise other parts of
     * Qt will try to query the nativeInterface() without checking if it exists
     * leading to a segfault.  For example, defaultHintStyleFromMatch() queries
     * the nativeInterface() without checking that it is NULL. See
     * https://bugreports.qt-project.org/browse/QTBUG-40946 
     * This is no longer strictly neccessary since we implement our own fontconfig database 
     * (a patched version of the Qt fontconfig database). However, it is probably a good idea to
     * keep it unknown, since the headless QPA is used in contexts where a desktop environment 
     * does not make sense anyway.
     */
    QByteArray desktopEnvironment() const { return QByteArrayLiteral("UNKNOWN"); }
};
#endif

HeadlessIntegration::HeadlessIntegration(const QStringList &parameters)
{
    Q_UNUSED(parameters);
    HeadlessScreen *mPrimaryScreen = new HeadlessScreen();

    mPrimaryScreen->mGeometry = QRect(0, 0, 240, 320);
    mPrimaryScreen->mDepth = 32;
    mPrimaryScreen->mFormat = QImage::Format_ARGB32_Premultiplied;

    screenAdded(mPrimaryScreen);
#ifdef __APPLE__
    m_fontDatabase.reset(new QCoreTextFontDatabase());
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

HeadlessIntegration *HeadlessIntegration::instance()
{
    return static_cast<HeadlessIntegration *>(QGuiApplicationPrivate::platformIntegration());
}

QT_END_NAMESPACE
