//Define the SIP wrapper to the QProgressIndicator widget
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=progress_indicator)

%Import QtWidgets/QtWidgetsmod.sip

%ModuleHeaderCode
#include <QPainter>
int load_style(const QHash<unsigned long,QString> &icon_map, int transient_scroller);
void set_no_activate_on_click(QWidget *widget);
void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark);
%End

class SpinAnimator : QObject {

%TypeHeaderCode
#include <QProgressIndicator.h>
%End

public:
    SpinAnimator(QObject *parent /TransferThis/ = 0, int speed_factor=300);
	float get_arc_length() const ;
	int get_arc_rotation() const ;
	int get_overall_rotation() const ;
	void draw(QPainter &painter, QRect bounds, const QColor &color, const float thickness=0.f);
	void start();
	void stop();
	bool is_running();
public slots:
	void set_arc_length(float val) ;
	void set_arc_rotation(int val) ;
	void set_overall_rotation(int val) ;
signals:
	void updated();
};

class QProgressIndicator : QWidget {

%TypeHeaderCode
#include <QProgressIndicator.h>
%End

public:

    QProgressIndicator(QWidget *parent /TransferThis/ = 0, int size = 64, int interval = 0);

    bool isAnimated () const;

    virtual QSize sizeHint() const;

    int heightForWidth(int w) const;
    
    QSize displaySize() const;

public slots:
    void startAnimation();
	void start();

    void stopAnimation();
	void stop();

    void setDisplaySize(QSize size);
    void setDisplaySize(int size);
    void setSizeHint(int size);
    void setSizeHint(QSize size);

protected:
    
    virtual void paintEvent(QPaintEvent * event);

signals:
	void running_state_changed(bool);

};

int load_style(SIP_PYDICT icon_map_, int transient_scroller);
%MethodCode
	QHash<unsigned long,QString> icon_map;
	PyObject *key, *value;
	Py_ssize_t pos = 0;
	while (PyDict_Next(a0, &pos, &key, &value)) {
		icon_map.insert(PyLong_AsUnsignedLong(key), QString::fromUtf8(PyUnicode_AsUTF8(value)));
	}
	load_style(icon_map, a1);
%End
void set_no_activate_on_click(QWidget *widget);
void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark) /ReleaseGIL/;
void set_menu_on_action(QAction* ac, QMenu* menu);
QMenu* menu_for_action(QAction *ac);
