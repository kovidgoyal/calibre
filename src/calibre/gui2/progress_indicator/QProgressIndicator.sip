//Define the SIP wrapper to the QProgressIndicator widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=progress_indicator, version=1)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip

%ModuleHeaderCode
int load_style(QString &path, QString &name);
bool do_notify(QObject *receiver, QEvent *event);
%End

class QProgressIndicator : QWidget {

%TypeHeaderCode
#include <QProgressIndicator.h>
%End

public:

    QProgressIndicator(QWidget *parent /TransferThis/ = 0, int size = 64);

    int animationDelay() const;

    bool isAnimated () const;

    bool isDisplayedWhenStopped() const;

    const QColor & color() const;

    virtual QSize sizeHint() const;

    int heightForWidth(int w) const;
    
    int displaySize() const;

public slots:
    void startAnimation();

    void stopAnimation();

    void setAnimationDelay(int delay);

    void setDisplayedWhenStopped(bool state);

    void setColor(const QColor & color);

    void setDisplaySize(int size);

protected:
    
    virtual void timerEvent(QTimerEvent * event); 

    virtual void paintEvent(QPaintEvent * event);

};

int load_style(QString &path, QString &name);

bool do_notify(QObject *receiver, QEvent *event);

