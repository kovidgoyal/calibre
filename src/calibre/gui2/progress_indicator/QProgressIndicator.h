#pragma once

#include <QWidget>
#include <QColor>

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
    Q_PROPERTY(bool displayedWhenStopped READ isDisplayedWhenStopped WRITE setDisplayedWhenStopped)
    Q_PROPERTY(QColor color READ color WRITE setColor)
    Q_PROPERTY(int displaySize READ displaySize WRITE setDisplaySize)
public:
    QProgressIndicator(QWidget* parent = 0, int size = 64);

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

    /*! Returns a Boolean value indicating whether the receiver shows itself even when it is not animating.
        \return Return true if the progress indicator shows itself even when it is not animating. By default, it returns false.
        \sa setDisplayedWhenStopped
     */
    bool isDisplayedWhenStopped() const;

    /*! Returns the color of the component.
        \sa setColor
      */
    const QColor & color() const { return m_color; }

    virtual QSize sizeHint() const;
    int heightForWidth(int w) const;
    int displaySize() const { return m_displaySize; }
public slots:
    /*! Starts the spin animation.
        \sa stopAnimation isAnimated
     */
    void startAnimation();

    /*! Stops the spin animation.
        \sa startAnimation isAnimated
     */
    void stopAnimation();

    /*! Sets the delay between animation steps.
        Setting the \a delay to a value larger than 40 slows the animation, while setting the \a delay to a smaller value speeds it up.
        \param delay The delay, in milliseconds. 
        \sa animationDelay 
     */
    void setAnimationDelay(int delay);

    /*! Sets whether the component hides itself when it is not animating. 
       \param state The animation state. Set false to hide the progress indicator when it is not animating; otherwise true.
       \sa isDisplayedWhenStopped
     */
    void setDisplayedWhenStopped(bool state);

    /*! Sets the color of the components to the given color.
        \sa color
     */
    void setColor(const QColor & color);

    /*! Set the size of this widget (used by sizeHint)
     * \sa displaySize
     */
    void setDisplaySize(int size);
protected:
    virtual void timerEvent(QTimerEvent * event); 
    virtual void paintEvent(QPaintEvent * event);
private:
    int m_angle;
    int m_timerId;
    int m_delay;
    int m_displaySize;
    bool m_displayedWhenStopped;
    QColor m_color;
};

/* Utility function that can be used to load a QStyle from a Qt plugin. This is
 * here so that there is no need to create a separate PyQt plugin just for this
 * simple functionality. 
 * \param path The full path to the DLL containing the plugin
 * \param name The name of the style plugin to load
 * \return 1 if succeeds 0 otherwise. The objectName of the loaded style is set to name
 */
int load_style(QString &path, QString &name);

