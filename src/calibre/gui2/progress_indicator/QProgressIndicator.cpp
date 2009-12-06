#include "QProgressIndicator.h"

#include <QPainter>

QProgressIndicator::QProgressIndicator(QWidget* parent, int size)
        : QWidget(parent),
        m_angle(0),
        m_timerId(-1),
        m_delay(80),
        m_displayedWhenStopped(true),
        m_displaySize(size),
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
