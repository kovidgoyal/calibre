#pragma once

#include <QtWidgets/QWidget>
#include <QObject>
#include <QColor>
#include <QHash>
#include <QPainter>
#include <QPropertyAnimation>
#include <QParallelAnimationGroup>

class SpinAnimator: public QObject {
	Q_OBJECT
	Q_PROPERTY(float arc_length READ get_arc_length WRITE set_arc_length)
	Q_PROPERTY(int arc_rotation READ get_arc_rotation WRITE set_arc_rotation)
	Q_PROPERTY(int overall_rotation READ get_overall_rotation WRITE set_overall_rotation)
public:
	SpinAnimator(QObject* parent = 0) :
		QObject(parent),
		m_arc_length(0),
		m_arc_rotation(0),
		m_overall_rotation(0),
		m_has_pending_updates(false),
		m_animation(this)
	{
		QPropertyAnimation *a;
#define S(property, duration) a = new QPropertyAnimation(this, QByteArray(#property), this); a->setEasingCurve(QEasingCurve::InOutCubic); a->setDuration(duration); a->setLoopCount(-1); m_animation.addAnimation(a);
		S(arc_length, 1400);
		const float arc_length_max = 0.734f, arc_length_min = 0.01f;
		a->setStartValue(arc_length_min);
        a->setKeyValueAt(0.25, arc_length_min);
        a->setKeyValueAt(0.5, arc_length_max);
        a->setKeyValueAt(0.75, arc_length_max);
        a->setEndValue(arc_length_min);

		S(arc_rotation, 1400);
        a->setStartValue(0);
        a->setKeyValueAt(0.25, 0);
        a->setKeyValueAt(0.5, 45);
        a->setKeyValueAt(0.75, 45);
        a->setEndValue(360);

		S(overall_rotation, 2000);
		a->setStartValue(0);
		a->setEndValue(360);
#undef S
	}
	~SpinAnimator() { m_animation.stop(); m_animation.clear(); }
	void start() { m_animation.start(); }
	void stop() { m_animation.stop(); }
	bool is_running() { return m_animation.state() == QAbstractAnimation::Running; }
	void draw(QPainter &painter, QRect bounds, const QColor &color) {
		m_has_pending_updates = false;
		painter.save();
		painter.setRenderHint(QPainter::Antialiasing);
        QRectF rect(bounds);
		float thickness = std::max(3.f, std::min((float)rect.width() / 10.f, 24.f));
		QPen pen(color);
		pen.setWidthF(thickness);
        float ht = thickness / 2 + 1;
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

/*!
    \class QProgressIndicator
    \brief The QProgressIndicator class lets an application display a progress indicator to show that a lengthy task is under way.

    Progress indicators are indeterminate and do nothing more than spin to show that the application is busy.
    \sa QProgressBar
*/
class QProgressIndicator : public QWidget
{
    Q_OBJECT
    Q_PROPERTY(int delay READ animationDelay WRITE setAnimationDelay)
    Q_PROPERTY(QSize displaySize READ displaySize WRITE setDisplaySize)
public:
    QProgressIndicator(QWidget* parent = 0, int size = 64, int interval = 10);

    /*! Returns the delay between animation steps.
        \return The number of milliseconds between animation steps. By default, the animation delay is set to 80 milliseconds.
        \sa setAnimationDelay
     */
    int animationDelay() const { return m_delay; }

    /*! Returns a Boolean value indicating whether the component is currently animated.
        \return Animation state.
        \sa startAnimation stopAnimation
     */
    bool isAnimated () const;

    virtual QSize sizeHint() const;
    int heightForWidth(int w) const;
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

    /*! Sets the delay between animation steps.
        Setting the \a delay to a value larger than 40 slows the animation, while setting the \a delay to a smaller value speeds it up.
        \param delay The delay, in milliseconds.
        \sa animationDelay
     */
    void setAnimationDelay(int delay);

    /*! Sets the color of the components to the given color.
        \sa color
     */
    void set_colors(const QColor & dark, const QColor & light);

    /*! Set the size of this widget (used by sizeHint)
     * \sa displaySize
     */
    void setDisplaySize(QSize size);
    void setDisplaySize(int size) { setDisplaySize(QSize(size, size)); }
	void setSizeHint(int size);
	void setSizeHint(QSize size);
protected:
    virtual void timerEvent(QTimerEvent * event);
    virtual void paintEvent(QPaintEvent * event);
private:
    int m_angle;
    int m_timerId;
    int m_delay;
    QSize m_displaySize;
    QColor m_dark, m_light;
};

int load_style(QHash<int,QString> icon_map, int transient_scroller=0);
void set_no_activate_on_click(QWidget *widget);
void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark);
