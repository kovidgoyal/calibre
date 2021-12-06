#pragma once

#include <QtWidgets/QWidget>
#include <QObject>
#include <QColor>
#include <QHash>
#include <QPainter>
#include <QMenu>
#include <QPropertyAnimation>
#include <QParallelAnimationGroup>
#include <QProxyStyle>
#include <QDialogButtonBox>

#define arc_length_max 0.734f
#define arc_length_min 0.02f


class SpinAnimator: public QObject {
	Q_OBJECT
	Q_PROPERTY(float arc_length READ get_arc_length WRITE set_arc_length)
	Q_PROPERTY(int arc_rotation READ get_arc_rotation WRITE set_arc_rotation)
	Q_PROPERTY(int overall_rotation READ get_overall_rotation WRITE set_overall_rotation)
public:
	SpinAnimator(QObject* parent = 0, const int speed_factor=300) :
		QObject(parent),
		m_arc_length(arc_length_max),
		m_arc_rotation(0),
		m_overall_rotation(0),
		m_has_pending_updates(false),
		m_animation(this)
	{
		QPropertyAnimation *a;
#define S(property, duration) a = new QPropertyAnimation(this, QByteArray(#property), this); a->setEasingCurve(QEasingCurve::InOutCubic); a->setDuration(duration); a->setLoopCount(-1); m_animation.addAnimation(a);
		S(arc_length, 7 * speed_factor);
		a->setStartValue(arc_length_min);
        a->setKeyValueAt(0.25, arc_length_min);
        a->setKeyValueAt(0.5, arc_length_max);
        a->setKeyValueAt(0.75, arc_length_max);
        a->setEndValue(arc_length_min);

		S(arc_rotation, 7 * speed_factor);
        a->setStartValue(0);
        a->setKeyValueAt(0.25, 0);
        a->setKeyValueAt(0.5, 45);
        a->setKeyValueAt(0.75, 45);
        a->setEndValue(360);

		S(overall_rotation, 10 * speed_factor);
		a->setStartValue(0);
		a->setEndValue(360);
#undef S
	}
	~SpinAnimator() { m_animation.stop(); m_animation.clear(); }
	void start() { m_animation.start(); }
	void stop() { m_animation.stop(); m_arc_length = arc_length_max; m_arc_rotation = 0; m_overall_rotation = 0; notify_of_update(); }
	bool is_running() const { return m_animation.state() == QAbstractAnimation::Running; }
	void draw(QPainter &painter, QRect bounds, const QColor &color, const float thickness=0.f) {
		m_has_pending_updates = false;
		painter.save();
		painter.setRenderHint(QPainter::Antialiasing);
        QRectF rect(bounds);
		float width = thickness > 0.f ? thickness : std::max(3.f, std::min((float)rect.width() / 10.f, 18.f));
		QPen pen(color);
		pen.setWidthF(width);
        float ht = width / 2 + 1;
        rect.adjust(ht, ht, -ht, -ht);
        pen.setCapStyle(Qt::RoundCap);
		painter.setPen(pen);
        int rotated_by = (m_overall_rotation + m_arc_rotation) * 16;
		int arc_length = (int)(m_arc_length * 360 * 16);
        painter.drawArc(rect, -rotated_by, -arc_length);
		painter.restore();
	}

	float get_arc_length() const { return m_arc_length; }
	int get_arc_rotation() const { return m_arc_rotation; }
	int get_overall_rotation() const { return m_overall_rotation; }
public slots:
	void set_arc_length(float val) { m_arc_length = val; notify_of_update(); }
	void set_arc_rotation(int val) { m_arc_rotation = val; notify_of_update(); }
	void set_overall_rotation(int val) { m_overall_rotation = val; notify_of_update(); }
signals:
	void updated();
private:
	float m_arc_length;
	int m_arc_rotation, m_overall_rotation;
	bool m_has_pending_updates;
	void notify_of_update() { if (!m_has_pending_updates) { m_has_pending_updates = true; emit updated(); } }
	QParallelAnimationGroup m_animation;
};

class CalibreStyle : public QProxyStyle {
    private:
        const QHash<unsigned long, QString> icon_map;
        QByteArray desktop_environment;
        QDialogButtonBox::ButtonLayout button_layout;
        int transient_scroller;

    public:
        CalibreStyle(const QHash<unsigned long, QString> &icmap, int transient_scroller);
        virtual int styleHint(StyleHint hint, const QStyleOption *option = 0, const QWidget *widget = 0, QStyleHintReturn *returnData = 0) const;
        virtual QIcon standardIcon(StandardPixmap standardIcon, const QStyleOption * option = 0, const QWidget * widget = 0) const;
        virtual int pixelMetric(PixelMetric metric, const QStyleOption * option = 0, const QWidget * widget = 0) const;
        virtual void drawComplexControl(ComplexControl control, const QStyleOptionComplex * option, QPainter * painter, const QWidget * widget = 0) const;
        virtual void drawPrimitive(PrimitiveElement element, const QStyleOption * option, QPainter * painter, const QWidget * widget = 0) const;
        virtual void drawControl(ControlElement element, const QStyleOption *option, QPainter *painter, const QWidget *widget) const;
};

/*!
    \class QProgressIndicator
    \brief The QProgressIndicator class lets an application display a progress indicator to show that a lengthy task is under way.

    Progress indicators are indeterminate and do nothing more than spin to show that the application is busy.
    \sa QProgressBar
*/
class QProgressIndicator : public QWidget
{
    Q_OBJECT
    Q_PROPERTY(QSize displaySize READ displaySize WRITE setDisplaySize)
public:
    QProgressIndicator(QWidget* parent = 0, int size = 64, int interval = 0);

    /*! Returns a Boolean value indicating whether the component is currently animated.
        \return Animation state.
        \sa startAnimation stopAnimation
     */
    bool isAnimated () const;

    virtual QSize sizeHint() const;
    QSize displaySize() const { return m_displaySize; }
public slots:
    /*! Starts the spin animation.
        \sa stopAnimation isAnimated
     */
    void startAnimation();
	void start();

    /*! Stops the spin animation.
        \sa startAnimation isAnimated
     */
    void stopAnimation();
	void stop();

    /*! Set the size of this widget (used by sizeHint)
     * \sa displaySize
     */
    void setDisplaySize(QSize size);
    void setDisplaySize(int size) { setDisplaySize(QSize(size, size)); }
	void setSizeHint(int size);
	void setSizeHint(QSize size);
signals:
	void running_state_changed(bool);
protected:
    virtual void paintEvent(QPaintEvent * event);
private:
    QSize m_displaySize;
	SpinAnimator m_animator;
};

int load_style(const QHash<unsigned long,QString> &icon_map, int transient_scroller=0);
void set_no_activate_on_click(QWidget *widget);
void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark);
void set_menu_on_action(QAction* ac, QMenu* menu);
QMenu* menu_for_action(const QAction *ac);
