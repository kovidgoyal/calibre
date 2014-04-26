#pragma once

#include <qpa/qplatformbackingstore.h>
#include <qpa/qplatformwindow.h>
#include <QtGui/QImage>

QT_BEGIN_NAMESPACE

class HeadlessBackingStore : public QPlatformBackingStore
{
public:
    HeadlessBackingStore(QWindow *window);
    ~HeadlessBackingStore();

    QPaintDevice *paintDevice();
    void flush(QWindow *window, const QRegion &region, const QPoint &offset);
    void resize(const QSize &size, const QRegion &staticContents);

private:
    QImage mImage;
    const bool mDebug;
};

QT_END_NAMESPACE

