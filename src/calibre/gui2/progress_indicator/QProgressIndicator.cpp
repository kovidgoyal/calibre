#include "QProgressIndicator.h"

#include <QPainter>
#include <QtWidgets/QStyle>
#include <QtWidgets/QApplication>
#include <QDebug>
#include <QStyleOptionToolButton>
#include <QFormLayout>
#include <QDialogButtonBox>
#include <QPainterPath>
#include <QImageReader>
#include <QCoreApplication>
#include <QTranslator>
#include <algorithm>
#include <qdrawutil.h>

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

void
set_image_allocation_limit(int megabytes) {
    QImageReader::setAllocationLimit(megabytes);
}

int
get_image_allocation_limit() {
    return QImageReader::allocationLimit();
}

QImage
image_from_hicon(void* hicon) {
#ifdef Q_OS_WIN
    return QImage::fromHICON((HICON)hicon);
#else
    (void)hicon;
    return QImage();
#endif
}

QImage
image_from_hbitmap(void* hbitmap) {
#ifdef Q_OS_WIN
    return QImage::fromHBITMAP((HBITMAP)hbitmap);
#else
    (void)hbitmap;
    return QImage();
#endif
}

// Helper to convert sRGB channel to linear RGB
static double
channelToLinear(double c) {
    return (c <= 0.03928) ? (c / 12.92) : std::pow((c + 0.055) / 1.055, 2.4);
}

// Compute relative luminance for a QColor
static double
luminance(const QColor& color) {
    return 0.2126 * channelToLinear(color.redF()) +
           0.7152 * channelToLinear(color.greenF()) +
           0.0722 * channelToLinear(color.blueF());
}

// Calculate contrast ratio between two QColors using the WCAG algorithm
double
contrast_ratio(const QColor& c1, const QColor& c2) {
    double l1 = luminance(c1);
    double l2 = luminance(c2);
    // Ensure l1 is the lighter color
    if (l1 < l2) std::swap(l1, l2);
    return (l1 + 0.05) / (l2 + 0.05);
}

typedef std::string_view(qt_translate)(const char* context, const char* text);
static qt_translate *qt_translate_func = NULL;

class Translator : public QTranslator {
    QString translate(const char *context, const char *text, const char *disambiguation = nullptr, int n = -1) const override {
        (void)context; (void)disambiguation; (void)n;
        if (qt_translate_func == NULL) return QString();
        auto ans = qt_translate_func(NULL, text);
        if (ans.data() == NULL) return QString();
        return QString::fromUtf8(ans.data(), ans.size());
    }
};
static Translator translator;

void
install_translator(void *v) {
    qt_translate_func = reinterpret_cast<qt_translate*>(v);
    static bool installed = false;
    if (!installed) {
        installed = true;
        auto app = QCoreApplication::instance();
        if (app) app->installTranslator(&translator);
    }
}

QString
utf16_slice(const QString &src, qsizetype pos, qsizetype n) {
    if (n < 0) n = src.size() - pos;
    if (pos < 0 || n < 0 || pos + n > src.size()) return QString();
    return src.sliced(pos, n);
}
