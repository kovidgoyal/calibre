#include "headless_backingstore.h"
#include "headless_integration.h"
#include "qscreen.h"
#include <QtCore/qdebug.h>
#include <qpa/qplatformscreen.h>
#include <private/qguiapplication_p.h>

QT_BEGIN_NAMESPACE

HeadlessBackingStore::HeadlessBackingStore(QWindow *window)
    : QPlatformBackingStore(window)
    , mDebug(HeadlessIntegration::instance()->options() & HeadlessIntegration::DebugBackingStore)
{
    if (mDebug)
        qDebug() << "HeadlessBackingStore::HeadlessBackingStore:" << (quintptr)this;
}

HeadlessBackingStore::~HeadlessBackingStore()
{
}

QPaintDevice *HeadlessBackingStore::paintDevice()
{
    if (mDebug)
        qDebug() << "HeadlessBackingStore::paintDevice";

    return &mImage;
}

void HeadlessBackingStore::flush(QWindow *window, const QRegion &region, const QPoint &offset)
{
    Q_UNUSED(window);
    Q_UNUSED(region);
    Q_UNUSED(offset);

    if (mDebug) {
        static int c = 0;
        QString filename = QString("output%1.png").arg(c++, 4, 10, QLatin1Char('0'));
        qDebug() << "HeadlessBackingStore::flush() saving contents to" << filename.toLocal8Bit().constData();
        mImage.save(filename);
    }
}

void HeadlessBackingStore::resize(const QSize &size, const QRegion &)
{
    QImage::Format format = QGuiApplication::primaryScreen()->handle()->format();
    if (mImage.size() != size)
        mImage = QImage(size, format);
}

QT_END_NAMESPACE
