#pragma once

#include <qpa/qplatformintegration.h>
#include <qpa/qplatformscreen.h>
#include <qpa/qplatformservices.h>
#if (QT_VERSION >= QT_VERSION_CHECK(5, 8, 0))
#include <QtServiceSupport/private/qgenericunixservices_p.h>
#else
#include <QtPlatformSupport/private/qgenericunixservices_p.h>
#endif
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

    bool hasCapability(QPlatformIntegration::Capability cap) const override;
    QPlatformFontDatabase *fontDatabase() const override;

    QPlatformWindow *createPlatformWindow(QWindow *window) const override;
    QPlatformBackingStore *createPlatformBackingStore(QWindow *window) const override;
    QAbstractEventDispatcher *createEventDispatcher() const override;
    QPlatformOpenGLContext *createPlatformOpenGLContext(QOpenGLContext *context) const override;
	QStringList themeNames() const override;
	QPlatformTheme *createPlatformTheme(const QString &name) const override;

    unsigned options() const { return 0; }

    static HeadlessIntegration *instance();

    virtual QPlatformServices *services() const override { return platform_services.data(); }

private:
    QScopedPointer<QPlatformFontDatabase> m_fontDatabase;
    QScopedPointer<QPlatformServices> platform_services;
};

QT_END_NAMESPACE
