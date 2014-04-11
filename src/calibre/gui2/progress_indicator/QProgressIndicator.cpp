#include "QProgressIndicator.h"

#include <QPainter>
#include <QtWidgets/QStylePlugin>
#include <QPluginLoader>
#include <QtWidgets/QStyle>
#include <QtWidgets/QApplication>
#include <QDebug>
#include <QtWidgets/QProxyStyle>

QProgressIndicator::QProgressIndicator(QWidget* parent, int size)
        : QWidget(parent),
        m_angle(0),
        m_timerId(-1),
        m_delay(80),
        m_displaySize(size),
        m_displayedWhenStopped(true),
        m_color(Qt::black)
{
    setSizePolicy(QSizePolicy::Fixed, QSizePolicy::Fixed);
    setFocusPolicy(Qt::NoFocus);
}

bool QProgressIndicator::isAnimated () const
{
    return (m_timerId != -1);
}

void QProgressIndicator::setDisplayedWhenStopped(bool state)
{
    m_displayedWhenStopped = state;

    update();
}

void QProgressIndicator::setDisplaySize(int size) 
{ 
    m_displaySize = size; 
    update(); 
}


bool QProgressIndicator::isDisplayedWhenStopped() const
{
    return m_displayedWhenStopped;
}

void QProgressIndicator::startAnimation()
{
    m_angle = 0;

    if (m_timerId == -1)
        m_timerId = startTimer(m_delay);
}

void QProgressIndicator::stopAnimation()
{
    if (m_timerId != -1)
        killTimer(m_timerId);

    m_timerId = -1;

    update();
}

void QProgressIndicator::setAnimationDelay(int delay)
{
    if (m_timerId != -1)
        killTimer(m_timerId);

    m_delay = delay;

    if (m_timerId != -1)
        m_timerId = startTimer(m_delay);
}

void QProgressIndicator::setColor(const QColor & color)
{
    m_color = color;

    update();
}

QSize QProgressIndicator::sizeHint() const
{
    return QSize(m_displaySize, m_displaySize);
}

int QProgressIndicator::heightForWidth(int w) const
{
    return w;
}

void QProgressIndicator::timerEvent(QTimerEvent * /*event*/)
{
    m_angle = (m_angle+30)%360;

    update();
}

void QProgressIndicator::paintEvent(QPaintEvent * /*event*/)
{
    if (!m_displayedWhenStopped && !isAnimated())
        return;

    int width = qMin(this->width(), this->height());
    
    QPainter p(this);
    p.setRenderHint(QPainter::Antialiasing);
    
    int outerRadius = (width-1)*0.5;
    int innerRadius = (width-1)*0.5*0.38;

    int capsuleHeight = outerRadius - innerRadius;
    int capsuleWidth  = (width > 32 ) ? capsuleHeight *.23 : capsuleHeight *.35;
    int capsuleRadius = capsuleWidth/2;

    for (int i=0; i<12; i++)
    {
        QColor color = m_color;
        color.setAlphaF(1.0f - (i/12.0f));
        p.setPen(Qt::NoPen);
        p.setBrush(color);       
        p.save();
        p.translate(rect().center());
        p.rotate(m_angle - i*30.0f);
        p.drawRoundedRect(-capsuleWidth*0.5, -(innerRadius+capsuleHeight), capsuleWidth, capsuleHeight, capsuleRadius, capsuleRadius);
        p.restore();
    }
}

int load_style(QString &path, QString &name) {
    int ret = 0;
    QStyle *s;
    QPluginLoader pl(path);
    QObject *o = pl.instance();
    if (o != 0) {
        QStylePlugin *sp = qobject_cast<QStylePlugin *>(o);
        if (sp != 0) {
            s = sp->create(name);
            if (s != 0) {
                s->setObjectName(name);
                QApplication::setStyle(s);
                ret = 1;
            }
        }
    }
    return ret;
}

bool do_notify(QObject *receiver, QEvent *event) {
    try {
        return QApplication::instance()->notify(receiver, event);
    } catch (std::exception& e) {
        qCritical() << "C++ exception thrown in slot: " << e.what();
    } catch (...) {
        qCritical() << "Unknown C++ exception thrown in slot";
    }
    qCritical() << "Receiver name:" << receiver->objectName() << "Receiver class:" << receiver->metaObject()->className() << "Event type: " << event->type();
    return false;
}

class NoActivateStyle: public QProxyStyle { 
 	public: 
        int styleHint(StyleHint hint, const QStyleOption *option = 0, const QWidget *widget = 0, QStyleHintReturn *returnData = 0) const { 
            if (hint == QStyle::SH_ItemView_ActivateItemOnSingleClick) return 0; 
            return QProxyStyle::styleHint(hint, option, widget, returnData); 
        } 
};

void set_no_activate_on_click(QWidget *widget) {
    widget->setStyle(new NoActivateStyle);
}

class TouchMenuStyle: public QProxyStyle {
    private:
        int extra_margin;

    public:
        TouchMenuStyle(int margin) : extra_margin(margin) {}
        QSize sizeFromContents ( ContentsType type, const QStyleOption * option, const QSize & contentsSize, const QWidget * widget = 0 ) const {
            QSize ans = QProxyStyle::sizeFromContents(type, option, contentsSize, widget);
            if (type == QStyle::CT_MenuItem) {
                ans.setHeight(ans.height() + extra_margin);  // Make the menu items more easily touchable
            }
            return ans;
        }
};

void set_touch_menu_style(QWidget *widget, int margin) {
    widget->setStyle(new TouchMenuStyle(margin));
}
