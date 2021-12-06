#include "QProgressIndicator.h"

#include <QPainter>
#include <QtWidgets/QStyle>
#include <QtWidgets/QApplication>
#include <QDebug>
#include <QStyleOptionToolButton>
#include <QFormLayout>
#include <QDialogButtonBox>
#include <QPainterPath>
#include <algorithm>
#include <qdrawutil.h>

extern int qt_defaultDpiX();

QProgressIndicator::QProgressIndicator(QWidget* parent, int size, int interval)
        : QWidget(parent),
        m_displaySize(size, size),
		m_animator(this)
{
	Q_UNUSED(interval);
    setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Preferred);
    setFocusPolicy(Qt::NoFocus);
	QObject::connect(&m_animator, SIGNAL(updated()), this, SLOT(update()));
}

bool QProgressIndicator::isAnimated () const
{
    return m_animator.is_running();
}

void QProgressIndicator::setDisplaySize(QSize size)
{
	setSizeHint(size);
}
void QProgressIndicator::setSizeHint(int size)
{
	setSizeHint(QSize(size, size));
}
void QProgressIndicator::setSizeHint(QSize size)
{
    m_displaySize = size;
    update();
}

void QProgressIndicator::startAnimation()
{
	if (!m_animator.is_running()) {
		m_animator.start();
		update();
		emit running_state_changed(true);
	}
}
void QProgressIndicator::start() { startAnimation(); }

void QProgressIndicator::stopAnimation()
{
	if (m_animator.is_running()) {
		m_animator.stop();
		update();
		emit running_state_changed(false);
	}
}
void QProgressIndicator::stop() { stopAnimation(); }

QSize QProgressIndicator::sizeHint() const
{
    return m_displaySize;
}

void QProgressIndicator::paintEvent(QPaintEvent * /*event*/)
{
	QPainter painter(this);
	QRect r(this->rect());
	QPoint center(r.center());
	int smaller = std::min(r.width(), r.height());
	m_animator.draw(painter, QRect(center.x() - smaller / 2, center.y() - smaller / 2, smaller, smaller), this->palette().color(QPalette::WindowText));
}

static inline QByteArray detectDesktopEnvironment()
{
    const QByteArray xdgCurrentDesktop = qgetenv("XDG_CURRENT_DESKTOP");
    if (!xdgCurrentDesktop.isEmpty())
        // See http://standards.freedesktop.org/menu-spec/latest/apb.html
        return xdgCurrentDesktop.toUpper();

    // Classic fallbacks
    if (!qEnvironmentVariableIsEmpty("KDE_FULL_SESSION"))
        return QByteArrayLiteral("KDE");
    if (!qEnvironmentVariableIsEmpty("GNOME_DESKTOP_SESSION_ID"))
        return QByteArrayLiteral("GNOME");

    // Fallback to checking $DESKTOP_SESSION (unreliable)
    const QByteArray desktopSession = qgetenv("DESKTOP_SESSION");
    if (desktopSession == "gnome")
        return QByteArrayLiteral("GNOME");
    if (desktopSession == "xfce")
        return QByteArrayLiteral("XFCE");

    return QByteArrayLiteral("UNKNOWN");
}

static inline bool
is_color_dark(const QColor &col) {
	int r, g, b;
	col.getRgb(&r, &g, &b);
	return r < 115 && g < 155 && b < 115;
}

static qreal
dpiScaled(qreal value) {
#ifdef Q_OS_MAC
    // On mac the DPI is always 72 so we should not scale it
    return value;
#else
    static const qreal scale = qreal(qt_defaultDpiX()) / 96.0;
    return value * scale;
#endif
}

CalibreStyle::CalibreStyle(int transient_scroller) : QProxyStyle(QString::fromUtf8("Fusion")), icon_map(), transient_scroller(transient_scroller) {
    setObjectName(QString("calibre"));
    desktop_environment = detectDesktopEnvironment();
    button_layout = static_cast<QDialogButtonBox::ButtonLayout>(QProxyStyle::styleHint(SH_DialogButtonLayout));
    if (QLatin1String("GNOME") == desktop_environment || QLatin1String("MATE") == desktop_environment || QLatin1String("UNITY") == desktop_environment || QLatin1String("CINNAMON") == desktop_environment || QLatin1String("X-CINNAMON") == desktop_environment)
        button_layout = QDialogButtonBox::GnomeLayout;
}

void CalibreStyle::set_icon_map(QHash<unsigned long, QString> &ic) {
    icon_map = ic;
}

int CalibreStyle::styleHint(StyleHint hint, const QStyleOption *option, const QWidget *widget, QStyleHintReturn *returnData) const {
    switch (hint) {
        case SH_DialogButtonBox_ButtonsHaveIcons:
            return 1;  // We want icons on dialog button box buttons
        case SH_DialogButtonLayout:
            // Use platform specific button orders always
#ifdef Q_OS_WIN32
            return QDialogButtonBox::WinLayout;
#elif defined(Q_OS_MAC)
            return QDialogButtonBox::MacLayout;
#endif
            return button_layout;
        case SH_FormLayoutFieldGrowthPolicy:
            return QFormLayout::FieldsStayAtSizeHint;  // Do not have fields expand to fill all available space in QFormLayout
        case SH_ScrollBar_Transient:
            return transient_scroller;
#ifdef Q_OS_MAC
        case SH_UnderlineShortcut:
            return 0;
#endif
        default:
            break;
    }
    return QProxyStyle::styleHint(hint, option, widget, returnData);
}

QIcon CalibreStyle::standardIcon(StandardPixmap standardIcon, const QStyleOption * option, const QWidget * widget) const {
    if (standardIcon == QStyle::SP_DialogCloseButton) {
        bool is_dark_theme = QApplication::instance()->property("is_dark_theme").toBool();
        return QIcon(icon_map.value(QStyle::SP_CustomBase + (is_dark_theme ? 2 : 1)));
    }
    if (icon_map.contains(standardIcon)) return QIcon(icon_map.value(standardIcon));
    return QProxyStyle::standardIcon(standardIcon, option, widget);
}

int CalibreStyle::pixelMetric(PixelMetric metric, const QStyleOption * option, const QWidget * widget) const {
    switch (metric) {
        case PM_TabBarTabVSpace:
            return 8;  // Make tab bars a little narrower, the value for the Fusion style is 12
        case PM_TreeViewIndentation:
            return int(dpiScaled(12));  // Reduce indentation in tree views
        default:
            break;
    }
    return QProxyStyle::pixelMetric(metric, option, widget);
}

void CalibreStyle::drawComplexControl(ComplexControl control, const QStyleOptionComplex * option, QPainter * painter, const QWidget * widget) const {
    const QStyleOptionToolButton *toolbutton = NULL;
    switch (control) {
        case CC_ToolButton:  // {{{
            // We do not want an arrow if the toolbutton has an instant popup
            toolbutton = qstyleoption_cast<const QStyleOptionToolButton *>(option);
            if (toolbutton && (toolbutton->features & QStyleOptionToolButton::HasMenu) && !(toolbutton->features & QStyleOptionToolButton::PopupDelay)) {
                QStyleOptionToolButton opt = QStyleOptionToolButton(*toolbutton);
                opt.features = toolbutton->features & ~QStyleOptionToolButton::HasMenu;
                return QProxyStyle::drawComplexControl(control, &opt, painter, widget);
            }
            break; /// }}}
        default:
            break;
    }
    return QProxyStyle::drawComplexControl(control, option, painter, widget);
}

void CalibreStyle::drawPrimitive(PrimitiveElement element, const QStyleOption * option, QPainter * painter, const QWidget * widget) const {
    const QStyleOptionViewItem *vopt = NULL;
    switch (element) {
        case PE_FrameTabBarBase: // {{{
            // dont draw line below tabs in dark mode as it looks bad
            if (const QStyleOptionTabBarBase *tbb = qstyleoption_cast<const QStyleOptionTabBarBase *>(option)) {
                if (tbb->shape == QTabBar::RoundedNorth) {
                    QColor bg = option->palette.color(QPalette::Window);
                    if (is_color_dark(bg)) return;
                }
            }
            break; // }}}

        case PE_IndicatorCheckBox: // {{{
            // Fix color used to draw checkbox outline in dark mode
            if (is_color_dark(option->palette.color(QPalette::Window))) {
                baseStyle()->drawPrimitive(element, option, painter, widget);
                painter->save();
                painter->translate(0.5, 0.5);
                QRect rect = option->rect;
                rect = rect.adjusted(0, 0, -1, -1);

                painter->setPen(QPen(option->palette.color(QPalette::WindowText)));
                if (option->state & State_HasFocus && option->state & State_KeyboardFocusChange)
                    painter->setPen(QPen(Qt::white));
                painter->drawRect(rect);
                painter->restore();
                return;
            }
            break; // }}}

        case PE_IndicatorRadioButton: // {{{
            // Fix color used to draw radiobutton outline in dark mode
            if (is_color_dark(option->palette.color(QPalette::Window))) {
                painter->save();
                painter->setBrush((option->state & State_Sunken) ? option->palette.base().color().lighter(320) : option->palette.base().color());
                painter->setRenderHint(QPainter::Antialiasing, true);
                QPainterPath circle;
                const QPointF circleCenter = option->rect.center() + QPoint(1, 1);
                const qreal outlineRadius = (option->rect.width() + (option->rect.width() + 1) % 2) / 2.0 - 1;
                circle.addEllipse(circleCenter, outlineRadius, outlineRadius);
                painter->setPen(QPen(option->palette.window().color().lighter(320)));
                if (option->state & State_HasFocus && option->state & State_KeyboardFocusChange) {
                    QColor highlightedOutline = option->palette.color(QPalette::Highlight).lighter(125);
                    painter->setPen(QPen(highlightedOutline));
                }
                painter->drawPath(circle);

                if (option->state & (State_On )) {
                    circle = QPainterPath();
                    const qreal checkmarkRadius = outlineRadius / 2.32;
                    circle.addEllipse(circleCenter, checkmarkRadius, checkmarkRadius);
                    QColor checkMarkColor = option->palette.text().color().lighter(120);
                    checkMarkColor.setAlpha(200);
                    painter->setPen(checkMarkColor);
                    checkMarkColor.setAlpha(180);
                    painter->setBrush(checkMarkColor);
                    painter->drawPath(circle);
                }
                painter->restore();
                return;
            } else { baseStyle()->drawPrimitive(element, option, painter, widget); }
            break; // }}}

        case PE_PanelItemViewItem:  // {{{
            // Highlight the current, selected item with a different background in an item view if the highlight current item property is set
            if (option->state & QStyle::State_HasFocus && (vopt = qstyleoption_cast<const QStyleOptionViewItem *>(option)) && widget && widget->property("highlight_current_item").toBool()) {
                QColor color = vopt->palette.color(QPalette::Normal, QPalette::Highlight);
                QStyleOptionViewItem opt = QStyleOptionViewItem(*vopt);
                if (is_color_dark(option->palette.color(QPalette::Window))) {
                    color = color.lighter(190);
                } else {
                    color = color.lighter(125);
                }
                opt.palette.setColor(QPalette::Highlight, color);
                return QProxyStyle::drawPrimitive(element, &opt, painter, widget);
            }
            break; // }}}

        case PE_IndicatorToolBarSeparator:  // {{{
            // Make toolbar separators stand out a bit more in dark themes
            {
                QRect rect = option->rect;
                const int margin = 6;
                QColor bg = option->palette.color(QPalette::Window);
                QColor first, second;
                if (is_color_dark(bg)) {
                    first = bg.darker(115);
                    second = bg.lighter(115);
                } else {
                    first = bg.darker(110);
                    second = bg.lighter(110);
                }
                if (option->state & State_Horizontal) {
                    const int offset = rect.width()/2;
                    painter->setPen(QPen(first));
                    painter->drawLine(rect.bottomLeft().x() + offset,
                            rect.bottomLeft().y() - margin,
                            rect.topLeft().x() + offset,
                            rect.topLeft().y() + margin);
                    painter->setPen(QPen(second));
                    painter->drawLine(rect.bottomLeft().x() + offset + 1,
                            rect.bottomLeft().y() - margin,
                            rect.topLeft().x() + offset + 1,
                            rect.topLeft().y() + margin);
                } else { //Draw vertical separator
                    const int offset = rect.height()/2;
                    painter->setPen(QPen(first));
                    painter->drawLine(rect.topLeft().x() + margin ,
                            rect.topLeft().y() + offset,
                            rect.topRight().x() - margin,
                            rect.topRight().y() + offset);
                    painter->setPen(QPen(second));
                    painter->drawLine(rect.topLeft().x() + margin ,
                            rect.topLeft().y() + offset + 1,
                            rect.topRight().x() - margin,
                            rect.topRight().y() + offset + 1);
                }
            }
            return; // }}}

        case PE_FrameFocusRect:  // {{{
            if (!widget || !widget->property("frame_for_focus").toBool())
                break;
            if (const QStyleOptionFocusRect *fropt = qstyleoption_cast<const QStyleOptionFocusRect *>(option)) {
                if (!(fropt->state & State_KeyboardFocusChange))
                    break;
                painter->save();
                painter->setRenderHint(QPainter::Antialiasing, true);
                painter->translate(0.5, 0.5);
                painter->setPen(option->palette.color(QPalette::Text));
                painter->setBrush(Qt::transparent);
                painter->drawRoundedRect(option->rect.adjusted(0, 0, -1, -1), 4, 4);
                painter->restore();
                return;
            }
            break; // }}}
        default:
            break;
    }
    return QProxyStyle::drawPrimitive(element, option, painter, widget);
}

void CalibreStyle::drawControl(ControlElement element, const QStyleOption *option, QPainter *painter, const QWidget *widget) const {
    switch(element) {
        case CE_ItemViewItem: {
            if (option->state & QStyle::State_HasFocus && (vopt = qstyleoption_cast<const QStyleOptionViewItem *>(option)) && widget && widget->property("highlight_current_item").toBool()) {
                if (is_color_dark(option->palette.color(QPalette::Window))) {
                    QStyleOptionViewItem opt = QStyleOptionViewItem(*vopt);
                    opt.palette.setColor(QPalette::HighlightedText, Qt::black);
                    QProxyStyle::drawControl(element, &opt, painter, widget);
                    return;
                }
            }
        } break;

        case CE_MenuItem:  // {{{
            // Draw menu separators that work in both light and dark modes
            if (const QStyleOptionMenuItem *menuItem = qstyleoption_cast<const QStyleOptionMenuItem *>(option)) {
                if (menuItem->menuItemType == QStyleOptionMenuItem::Separator) {
                    int w = 0;
                    const int margin = 5;
                    painter->save();
                    if (!menuItem->text.isEmpty()) {
                        painter->setFont(menuItem->font);
                        proxy()->drawItemText(painter, menuItem->rect.adjusted(margin, 0, -margin, 0), Qt::AlignLeft | Qt::AlignVCenter,
                                menuItem->palette, menuItem->state & State_Enabled, menuItem->text,
                                QPalette::Text);
                        w = menuItem->fontMetrics.horizontalAdvance(menuItem->text) + margin;
                    }
                    if (is_color_dark(menuItem->palette.color(QPalette::Window))) painter->setPen(Qt::gray);
                    else painter->setPen(QColor(0, 0, 0, 60).lighter(106));
                    bool reverse = menuItem->direction == Qt::RightToLeft;
                    painter->drawLine(menuItem->rect.left() + margin + (reverse ? 0 : w), menuItem->rect.center().y(),
                            menuItem->rect.right() - margin - (reverse ? w : 0), menuItem->rect.center().y());
                    painter->restore();
                    return;
                }
            }
            break; // }}}

        default: break;
    }
    QProxyStyle::drawControl(element, option, painter, widget);
}

class NoActivateStyle: public QProxyStyle {
 	public:
        NoActivateStyle(QStyle *base) : QProxyStyle(base) { }
        int styleHint(StyleHint hint, const QStyleOption *option = 0, const QWidget *widget = 0, QStyleHintReturn *returnData = 0) const {
            if (hint == QStyle::SH_ItemView_ActivateItemOnSingleClick) return 0;
            return QProxyStyle::styleHint(hint, option, widget, returnData);
        }
};

void set_no_activate_on_click(QWidget *widget) {
	QStyle *base_style = widget->style();
	if (base_style) widget->setStyle(new NoActivateStyle(base_style));
}

void draw_snake_spinner(QPainter &painter, QRect rect, int angle, const QColor & light, const QColor & dark) {
	painter.save();
    painter.setRenderHint(QPainter::Antialiasing);
    if (rect.width() > rect.height()) {
        int delta = (rect.width() - rect.height()) / 2;
        rect = rect.adjusted(delta, 0, -delta, 0);
	} else if (rect.height() > rect.width()) {
        int delta = (rect.height() - rect.width()) / 2;
        rect = rect.adjusted(0, delta, 0, -delta);
	}
    int disc_width = std::max(3, std::min(rect.width() / 10, 8));
    QRect drawing_rect(rect.x() + disc_width, rect.y() + disc_width, rect.width() - 2 * disc_width, rect.height() - 2 *disc_width);
    int gap = 60;  // degrees
    QConicalGradient gradient(drawing_rect.center(), angle - gap / 2);
    gradient.setColorAt((360 - gap/2)/360.0, light);
    gradient.setColorAt(0, dark);

    QPen pen(QBrush(gradient), disc_width);
    pen.setCapStyle(Qt::RoundCap);
    painter.setPen(pen);
    painter.drawArc(drawing_rect, angle * 16, (360 - gap) * 16);
	painter.restore();
}

void
set_menu_on_action(QAction* ac, QMenu* menu) {
    ac->setMenu<QMenu*>(menu);
}

QMenu*
menu_for_action(const QAction *ac) {
    return ac->menu<QMenu*>();
}
