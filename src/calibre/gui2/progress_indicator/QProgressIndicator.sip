//Define the SIP wrapper to the QProgressIndicator widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=progress_indicator)

%Import QtWidgets/QtWidgetsmod.sip

%ModuleHeaderCode
int load_style(QHash<int,QString> icon_map);
void set_no_activate_on_click(QWidget *widget);
void set_touch_menu_style(QWidget *widget, int margin);
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

int load_style(QHash<int,QString> icon_map);
void set_no_activate_on_click(QWidget *widget);
void set_touch_menu_style(QWidget *widget, int margin=20);
