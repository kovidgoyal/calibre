#pragma once

#include <QtWidgets/QWidget>
#include <QColor>
#include <QHash>
#include <QPainter>

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
