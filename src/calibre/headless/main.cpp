#include <qpa/qplatformintegrationplugin.h>
#include "headless_integration.h"

QT_BEGIN_NAMESPACE

class HeadlessIntegrationPlugin : public QPlatformIntegrationPlugin
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QPA.QPlatformIntegrationFactoryInterface.5.2" FILE "headless.json")
public:
    QPlatformIntegration *create(const QString&, const QStringList&);
};

QPlatformIntegration *HeadlessIntegrationPlugin::create(const QString& system, const QStringList& paramList)
{
    if (!system.compare(QLatin1String("headless"), Qt::CaseInsensitive))
        return new HeadlessIntegration(paramList);

    return 0;
}

QT_END_NAMESPACE

#include "main.moc"
