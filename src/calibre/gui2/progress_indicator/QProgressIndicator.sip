//Define the SIP wrapper to the QProgressIndicator widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=progress_indicator)

%Import QtWidgets/QtWidgetsmod.sip

%ModuleHeaderCode
#include <QPainter>
int load_style(QHash<int,QString> icon_map, int transient_scroller);
void set_no_activate_on_click(QWidget *widget);
void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark);
%End

class QProgressIndicator : QWidget {

%TypeHeaderCode
#include <QProgressIndicator.h>
%End

public:

    QProgressIndicator(QWidget *parent /TransferThis/ = 0, int size = 64, int interval = 10);

    int animationDelay() const;

    bool isAnimated () const;

    virtual QSize sizeHint() const;

    int heightForWidth(int w) const;
    
    QSize displaySize() const;

public slots:
    void startAnimation();
	void start();

    void stopAnimation();
	void stop();

    void setAnimationDelay(int delay);

    void set_colors(const QColor & dark, const QColor & light);

    void setDisplaySize(QSize size);
    void setDisplaySize(int size);
    void setSizeHint(int size);
    void setSizeHint(QSize size);

protected:
    
    virtual void timerEvent(QTimerEvent * event); 

    virtual void paintEvent(QPaintEvent * event);

};

int load_style(QHash<int,QString> icon_map, int transient_scroller);
void set_no_activate_on_click(QWidget *widget);
void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark) /ReleaseGIL/;
