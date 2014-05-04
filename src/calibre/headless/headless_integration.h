#pragma once

#include <qpa/qplatformintegration.h>
#include <qpa/qplatformscreen.h>
#include <QScopedPointer>

QT_BEGIN_NAMESPACE

class HeadlessScreen : public QPlatformScreen
{
public:
    HeadlessScreen()
        : mDepth(32), mFormat(QImage::Format_ARGB32_Premultiplied) {}

    QRect geometry() const { return mGeometry; }
    int depth() const { return mDepth; }
    QImage::Format format() const { return mFormat; }

public:
    QRect mGeometry;
    int mDepth;
    QImage::Format mFormat;
    QSize mPhysicalSize;
};

class HeadlessIntegration : public QPlatformIntegration
{
public:

    explicit HeadlessIntegration(const QStringList &parameters);
    ~HeadlessIntegration();

    bool hasCapability(QPlatformIntegration::Capability cap) const;
    QPlatformFontDatabase *fontDatabase() const;

    QPlatformWindow *createPlatformWindow(QWindow *window) const;
    QPlatformBackingStore *createPlatformBackingStore(QWindow *window) const;
    QAbstractEventDispatcher *createEventDispatcher() const;

    unsigned options() const { return 0; }

    static HeadlessIntegration *instance();

private:
    QScopedPointer<QPlatformFontDatabase> m_fontDatabase;
};

QT_END_NAMESPACE

