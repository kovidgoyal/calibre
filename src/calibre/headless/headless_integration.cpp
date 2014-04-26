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

QT_BEGIN_NAMESPACE

static const char debugBackingStoreEnvironmentVariable[] = "QT_DEBUG_BACKINGSTORE";

static inline unsigned parseOptions(const QStringList &paramList)
{
    unsigned options = 0;
    foreach (const QString &param, paramList) {
        if (param == QLatin1String("enable_fonts"))
            options |= HeadlessIntegration::EnableFonts;
    }
    return options;
}

HeadlessIntegration::HeadlessIntegration(const QStringList &parameters)
    : m_dummyFontDatabase(0)
    , m_options(parseOptions(parameters))
{
    if (qEnvironmentVariableIsSet(debugBackingStoreEnvironmentVariable)
        && qgetenv(debugBackingStoreEnvironmentVariable).toInt() > 0) {
        m_options |= DebugBackingStore | EnableFonts;
    }

    HeadlessScreen *mPrimaryScreen = new HeadlessScreen();

    mPrimaryScreen->mGeometry = QRect(0, 0, 240, 320);
    mPrimaryScreen->mDepth = 32;
    mPrimaryScreen->mFormat = QImage::Format_ARGB32_Premultiplied;

    screenAdded(mPrimaryScreen);
}

HeadlessIntegration::~HeadlessIntegration()
{
    delete m_dummyFontDatabase;
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
    if (m_options & EnableFonts)
        return QPlatformIntegration::fontDatabase();
    if (!m_dummyFontDatabase)
        m_dummyFontDatabase = new DummyFontDatabase;
    return m_dummyFontDatabase;
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
#ifdef Q_OS_WIN
    return new QEventDispatcherWin32;
#else
    return createUnixEventDispatcher();
#endif
}

HeadlessIntegration *HeadlessIntegration::instance()
{
    return static_cast<HeadlessIntegration *>(QGuiApplicationPrivate::platformIntegration());
}

QT_END_NAMESPACE
