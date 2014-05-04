#include "headless_integration.h"
#include "headless_backingstore.h"
#ifndef Q_OS_WIN
#include <QtPlatformSupport/private/qgenericunixeventdispatcher_p.h>
#else
#include <QtCore/private/qeventdispatcher_win_p.h>
#endif

#include <QtGui/private/qpixmap_raster_p.h>
#include <QtGui/private/qguiapplication_p.h>
#include <qpa/qplatformwindow.h>
#include <qpa/qplatformfontdatabase.h>
#include <QtPlatformSupport/private/qfontconfigdatabase_p.h>

QT_BEGIN_NAMESPACE

HeadlessIntegration::HeadlessIntegration(const QStringList &parameters)
{
    Q_UNUSED(parameters);
    HeadlessScreen *mPrimaryScreen = new HeadlessScreen();

    mPrimaryScreen->mGeometry = QRect(0, 0, 240, 320);
    mPrimaryScreen->mDepth = 32;
    mPrimaryScreen->mFormat = QImage::Format_ARGB32_Premultiplied;

    screenAdded(mPrimaryScreen);
    m_fontDatabase.reset(new QFontconfigDatabase());
}

HeadlessIntegration::~HeadlessIntegration()
{
}

bool HeadlessIntegration::hasCapability(QPlatformIntegration::Capability cap) const
{
    switch (cap) {
    case ThreadedPixmaps: return true;
    case MultipleWindows: return true;
    default: return QPlatformIntegration::hasCapability(cap);
    }
}

// Dummy font database that does not scan the fonts directory to be
// used for command line tools like qmlplugindump that do not create windows
// unless DebugBackingStore is activated.
class DummyFontDatabase : public QPlatformFontDatabase
{
public:
    virtual void populateFontDatabase() {}
};

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
    return createUnixEventDispatcher();
}

HeadlessIntegration *HeadlessIntegration::instance()
{
    return static_cast<HeadlessIntegration *>(QGuiApplicationPrivate::platformIntegration());
}

QT_END_NAMESPACE
