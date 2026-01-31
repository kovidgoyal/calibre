/*
 * CalibreIconEngine.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "QProgressIndicator.h"
#include <QIcon>
#include <QIconEngine>
#include <QString>
#include <QByteArray>
#include <QGuiApplication>
#include <QApplication>
#include <QStringBuilder>
#include <QPixmapCache>
#include <QFileInfo>
#include <atomic>

using namespace Qt::StringLiterals;
static std::atomic<unsigned> current_theme_key(1);
static struct {
    bool using_dark_colors, has_dark_user_theme, has_light_user_theme, has_any_user_theme;
} theme;

// Copied with a few modifications Qt QPixmapIconEngine private code {{{
struct QPixmapIconEngineEntry
{
    QPixmapIconEngineEntry() = default;
    QPixmapIconEngineEntry(const QPixmap &pm, QIcon::Mode m, QIcon::State s)
        : pixmap(pm), size(pm.size()), mode(m), state(s) {}
    QPixmapIconEngineEntry(const QString &file, const QSize &sz, QIcon::Mode m, QIcon::State s)
        : fileName(file), size(sz), mode(m), state(s) {}
    QPixmapIconEngineEntry(const QString &file, const QImage &image, QIcon::Mode m, QIcon::State s);
    QPixmap pixmap;
    QString fileName;
    QSize size;
    QIcon::Mode mode = QIcon::Normal;
    QIcon::State state = QIcon::Off;
};
Q_DECLARE_TYPEINFO(QPixmapIconEngineEntry, Q_RELOCATABLE_TYPE);

inline QPixmapIconEngineEntry::QPixmapIconEngineEntry(const QString &file, const QImage &image, QIcon::Mode m, QIcon::State s)
    : fileName(file), size(image.size()), mode(m), state(s)
{
    pixmap.convertFromImage(image);
}

class QPixmapIconEngine : public QIconEngine {
public:
    QPixmapIconEngine();
    QPixmapIconEngine(const QPixmapIconEngine &);
    ~QPixmapIconEngine();
    void paint(QPainter *painter, const QRect &rect, QIcon::Mode mode, QIcon::State state) override;
    QPixmap pixmap(const QSize &size, QIcon::Mode mode, QIcon::State state) override;
    QPixmap scaledPixmap(const QSize &size, QIcon::Mode mode, QIcon::State state, qreal scale) override;
    QPixmapIconEngineEntry *bestMatch(const QSize &size, qreal scale, QIcon::Mode mode, QIcon::State state);
    QSize actualSize(const QSize &size, QIcon::Mode mode, QIcon::State state) override;
    QList<QSize> availableSizes(QIcon::Mode mode, QIcon::State state) override;
    void addPixmap(const QPixmap &pixmap, QIcon::Mode mode, QIcon::State state) override;
    bool isNull() override;

    QString key() const override;
    QIconEngine *clone() const override;

    static inline QSize adjustSize(const QSize &expectedSize, QSize size)
    {
        if (!size.isNull() && (size.width() > expectedSize.width() || size.height() > expectedSize.height()))
            size.scale(expectedSize, Qt::KeepAspectRatio);
        return size;
    }

    void clear() {
        pixmaps.clear();
    }

private:
    void removePixmapEntry(QPixmapIconEngineEntry *pe)
    {
        auto idx = pixmaps.size();
        while (--idx >= 0) {
            if (pe == &pixmaps.at(idx)) {
                pixmaps.remove(idx);
                return;
            }
        }
    }
    QPixmapIconEngineEntry *tryMatch(const QSize &size, qreal scale, QIcon::Mode mode, QIcon::State state);
    QList<QPixmapIconEngineEntry> pixmaps;
};

QPixmapIconEngine::QPixmapIconEngine()
{
}

QPixmapIconEngine::QPixmapIconEngine(const QPixmapIconEngine &other)
    : QIconEngine(other), pixmaps(other.pixmaps)
{
}

QPixmapIconEngine::~QPixmapIconEngine()
{
}

void QPixmapIconEngine::paint(QPainter *painter, const QRect &rect, QIcon::Mode mode, QIcon::State state)
{
    auto paintDevice = painter->device();
    qreal dpr = paintDevice ? paintDevice->devicePixelRatio() : qApp->devicePixelRatio();
    QPixmap px = scaledPixmap(rect.size(), mode, state, dpr);
    painter->drawPixmap(rect, px);
}

static inline qint64 area(const QSize &s) { return qint64(s.width()) * s.height(); }

// Returns the smallest of the two that is still larger than or equal to size.
// Pixmaps at the correct scale are preferred, pixmaps at lower scale are
// used as fallbacks. We assume that the pixmap set is complete, in the sense
// that no 2x pixmap is going to be a better match than a 3x pixmap for the the
// target scale of 3 (It's OK if 3x pixmaps are missing - we'll fall back to
// the 2x pixmaps then.)
static QPixmapIconEngineEntry *bestSizeScaleMatch(const QSize &size, qreal scale, QPixmapIconEngineEntry *pa, QPixmapIconEngineEntry *pb)
{
    const auto scaleA = pa->pixmap.devicePixelRatio();
    const auto scaleB = pb->pixmap.devicePixelRatio();
    // scale: we can only differentiate on scale if the scale differs
    if (scaleA != scaleB) {

        // Score the pixmaps: 0 is an exact scale match, positive
        // scores have more detail than requested, negative scores
        // have less detail than requested.
        qreal ascore = scaleA - scale;
        qreal bscore = scaleB - scale;

        // always prefer positive scores to prevent upscaling
        if ((ascore < 0) != (bscore < 0))
            return bscore < 0 ? pa : pb;
        // Take the one closest to 0
        return (qAbs(ascore) < qAbs(bscore)) ? pa : pb;
    }

    qint64 s = area(size * scale);
    if (pa->size == QSize() && pa->pixmap.isNull()) {
        pa->pixmap = QPixmap(pa->fileName);
        pa->size = pa->pixmap.size();
    }
    qint64 a = area(pa->size);
    if (pb->size == QSize() && pb->pixmap.isNull()) {
        pb->pixmap = QPixmap(pb->fileName);
        pb->size = pb->pixmap.size();
    }
    qint64 b = area(pb->size);
    qint64 res = a;
    if (qMin(a,b) >= s)
        res = qMin(a,b);
    else
        res = qMax(a,b);
    if (res == a)
        return pa;
    return pb;
}

QPixmapIconEngineEntry *QPixmapIconEngine::tryMatch(const QSize &size, qreal scale, QIcon::Mode mode, QIcon::State state)
{
    QPixmapIconEngineEntry *pe = nullptr;
    for (auto &entry : pixmaps) {
        if (entry.mode == mode && entry.state == state) {
            if (pe)
                pe = bestSizeScaleMatch(size, scale, &entry, pe);
            else
                pe = &entry;
        }
    }
    return pe;
}


QPixmapIconEngineEntry *QPixmapIconEngine::bestMatch(const QSize &size, qreal scale, QIcon::Mode mode, QIcon::State state)
{
    QPixmapIconEngineEntry *pe = tryMatch(size, scale, mode, state);
    while (!pe){
        QIcon::State oppositeState = (state == QIcon::On) ? QIcon::Off : QIcon::On;
        if (mode == QIcon::Disabled || mode == QIcon::Selected) {
            QIcon::Mode oppositeMode = (mode == QIcon::Disabled) ? QIcon::Selected : QIcon::Disabled;
            if ((pe = tryMatch(size, scale, QIcon::Normal, state)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Active, state)))
                break;
            if ((pe = tryMatch(size, scale, mode, oppositeState)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Normal, oppositeState)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Active, oppositeState)))
                break;
            if ((pe = tryMatch(size, scale, oppositeMode, state)))
                break;
            if ((pe = tryMatch(size, scale, oppositeMode, oppositeState)))
                break;
        } else {
            QIcon::Mode oppositeMode = (mode == QIcon::Normal) ? QIcon::Active : QIcon::Normal;
            if ((pe = tryMatch(size, scale, oppositeMode, state)))
                break;
            if ((pe = tryMatch(size, scale, mode, oppositeState)))
                break;
            if ((pe = tryMatch(size, scale, oppositeMode, oppositeState)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Disabled, state)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Selected, state)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Disabled, oppositeState)))
                break;
            if ((pe = tryMatch(size, scale, QIcon::Selected, oppositeState)))
                break;
        }

        if (!pe)
            return pe;
    }

    if (pe->pixmap.isNull()) {
        // delay-load the image
        QImage image(pe->fileName);
        if (!image.isNull()) {
            pe->pixmap.convertFromImage(image);
            if (!pe->pixmap.isNull()) {
                pe->size = pe->pixmap.size();
                pe->pixmap.setDevicePixelRatio(scale);
            }
        }
        if (!pe->size.isValid()) {
            removePixmapEntry(pe);
            pe = nullptr;
        }
    }

    return pe;
}

QPixmap QPixmapIconEngine::pixmap(const QSize &size, QIcon::Mode mode, QIcon::State state)
{
    return scaledPixmap(size, mode, state, 1.0);
}

qreal pixmapDevicePixelRatio(qreal displayDevicePixelRatio, const QSize &requestedSize, const QSize &actualSize)
{
    QSize targetSize = requestedSize * displayDevicePixelRatio;
    if ((actualSize.width() == targetSize.width() && actualSize.height() <= targetSize.height()) ||
        (actualSize.width() <= targetSize.width() && actualSize.height() == targetSize.height())) {
        // Correctly scaled for dpr, just having different aspect ratio
        return displayDevicePixelRatio;
    }
    qreal scale = 0.5 * (qreal(actualSize.width()) / qreal(targetSize.width()) +
                         qreal(actualSize.height() / qreal(targetSize.height())));
    return qMax(qreal(1.0), displayDevicePixelRatio *scale);
}

template <typename T>
        struct HexString
{
    inline HexString(const T t)
        : val(t)
    {}

    inline void write(QChar *&dest) const
    {
        const char16_t hexChars[] = { '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'a', 'b', 'c', 'd', 'e', 'f' };
        const char *c = reinterpret_cast<const char *>(&val);
        for (uint i = 0; i < sizeof(T); ++i) {
            *dest++ = hexChars[*c & 0xf];
            *dest++ = hexChars[(*c & 0xf0) >> 4];
            ++c;
        }
    }
    const T val;
};

// specialization to enable fast concatenating of our string tokens to a string
template <typename T>
        struct QConcatenable<HexString<T> >
{
    typedef HexString<T> type;
    enum { ExactSize = true };
    static int size(const HexString<T> &) { return sizeof(T) * 2; }
    static inline void appendTo(const HexString<T> &str, QChar *&out) { str.write(out); }
    typedef QString ConvertTo;
};

QPixmap apply_style(QPixmap pm, QIcon::Mode mode) {
    QStyleOption opt(0);
    opt.palette = QGuiApplication::palette();
    return QApplication::style()->generatedIconPixmap(mode, pm, &opt);
}

QPixmap QPixmapIconEngine::scaledPixmap(const QSize &size, QIcon::Mode mode, QIcon::State state, qreal scale)
{
    QPixmap pm;
    QPixmapIconEngineEntry *pe = bestMatch(size, scale, mode, state);
    if (pe)
        pm = pe->pixmap;
    else
        return pm;

    if (pm.isNull()) {
        removePixmapEntry(pe);
        if (pixmaps.isEmpty())
            return pm;
        return scaledPixmap(size, mode, state, scale);
    }

    const auto actualSize = adjustSize(size * scale, pm.size());
    const auto calculatedDpr = pixmapDevicePixelRatio(scale, size, actualSize);
    QString key = "cl_"_L1
                  % HexString<quint64>(pm.cacheKey())
                  % HexString<quint8>(pe->mode)
                  % HexString<quint64>(QGuiApplication::palette().cacheKey())
                  % HexString<uint>(actualSize.width())
                  % HexString<uint>(actualSize.height())
                  % HexString<quint16>(qRound(calculatedDpr * 1000));

    if (mode == QIcon::Active) {
        if (QPixmapCache::find(key % HexString<quint8>(mode), &pm))
            return pm; // horray
        if (QPixmapCache::find(key % HexString<quint8>(QIcon::Normal), &pm)) {
            QPixmap active = apply_style(pm, mode);
            if (pm.cacheKey() == active.cacheKey()) return pm;
        }
    }

    if (!QPixmapCache::find(key % HexString<quint8>(mode), &pm)) {
        if (pm.size() != actualSize)
            pm = pm.scaled(actualSize, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
        if (pe->mode != mode && mode != QIcon::Normal) {
            QPixmap generated = apply_style(pm, mode);
            if (!generated.isNull())
                pm = generated;
        }
        pm.setDevicePixelRatio(calculatedDpr);
        QPixmapCache::insert(key % HexString<quint8>(mode), pm);
    }
    return pm;
}

QSize QPixmapIconEngine::actualSize(const QSize &size, QIcon::Mode mode, QIcon::State state)
{
    QSize actualSize;

    // The returned actual size is the size in device independent pixels,
    // so we limit the search to scale 1 and assume that e.g. @2x versions
    // does not proviode extra actual sizes not also provided by the 1x versions.
    qreal scale = 1;

    if (QPixmapIconEngineEntry *pe = bestMatch(size, scale, mode, state))
        actualSize = pe->size;

    return adjustSize(size, actualSize);
}

QList<QSize> QPixmapIconEngine::availableSizes(QIcon::Mode mode, QIcon::State state)
{
    QList<QSize> sizes;
    for (QPixmapIconEngineEntry &pe : pixmaps) {
        if (pe.mode != mode || pe.state != state)
            continue;
        if (pe.size.isEmpty() && pe.pixmap.isNull()) {
            pe.pixmap = QPixmap(pe.fileName);
            pe.size = pe.pixmap.size();
        }
        if (!pe.size.isEmpty() && !sizes.contains(pe.size))
            sizes.push_back(pe.size);
    }
    return sizes;
}

void QPixmapIconEngine::addPixmap(const QPixmap &pixmap, QIcon::Mode mode, QIcon::State state)
{
    if (!pixmap.isNull()) {
        QPixmapIconEngineEntry *pe = tryMatch(pixmap.size() / pixmap.devicePixelRatio(),
                                              pixmap.devicePixelRatio(), mode, state);
        if (pe && pe->size == pixmap.size() && pe->pixmap.devicePixelRatio() == pixmap.devicePixelRatio()) {
            pe->pixmap = pixmap;
            pe->fileName.clear();
        } else {
            pixmaps += QPixmapIconEngineEntry(pixmap, mode, state);
        }
    }
}

bool QPixmapIconEngine::isNull()
{
    return pixmaps.isEmpty();
}

QString QPixmapIconEngine::key() const
{
    return "CalibrePixmapIconEngine"_L1;
}

QIconEngine *QPixmapIconEngine::clone() const
{
    return new QPixmapIconEngine(*this);
} // }}}

class CalibreIconEngine : public QIconEngine {
    private:
    const QString name;
    const QByteArray fallback_data;
    std::atomic<unsigned> used_theme_key;
    QPixmapIconEngine pixmap_engine;

    bool try_with_key(const QString &key) {
        QString path = ":/icons/"_L1 % key % "/images/"_L1 % name;
        QPixmap pm(path);
        if (pm.isNull()) return false;
        pixmap_engine.clear();
        pixmap_engine.addPixmap(pm, QIcon::Normal, QIcon::Off);
        return true;
    }

    void ensure_state() {
        if (used_theme_key == current_theme_key) return;
        used_theme_key.store(current_theme_key.load());
        if (theme.using_dark_colors) {
            if (theme.has_dark_user_theme && try_with_key("calibre-user-dark"_L1)) return;
            if (theme.has_any_user_theme) {
                if (try_with_key("calibre-user-any-dark"_L1)) return;
                if (try_with_key("calibre-user-any"_L1)) return;
            }
            if (try_with_key("calibre-default-dark"_L1)) return;
        } else {
            if (theme.has_light_user_theme && try_with_key("calibre-user-light"_L1)) return;
            if (theme.has_any_user_theme) {
                if (try_with_key("calibre-user-any-light"_L1)) return;
                if (try_with_key("calibre-user-any"_L1)) return;
            }
            if (try_with_key("calibre-default-light"_L1)) return;
        }
        if (try_with_key("calibre-default"_L1)) return;
        if (fallback_data.size()) {
            QPixmap pm;
            if (pm.loadFromData(fallback_data)) {
                pixmap_engine.clear();
                pixmap_engine.addPixmap(pm, QIcon::Normal, QIcon::On);
            }
        }
    }

    public:
    CalibreIconEngine(QString name, QByteArray fallback_data) :
        name(name), fallback_data(fallback_data), used_theme_key(0), pixmap_engine()
    {}
    CalibreIconEngine(const CalibreIconEngine &other) :
        QIconEngine(other), name(other.name), fallback_data(other.fallback_data),
        used_theme_key(other.used_theme_key.load()), pixmap_engine(other.pixmap_engine)
    {}

    void paint(QPainter *painter, const QRect &rect, QIcon::Mode mode, QIcon::State state) override {
        ensure_state();
        pixmap_engine.paint(painter, rect, mode, state);
    }
    QIconEngine* clone() const override { return new CalibreIconEngine(*this); }
    QString key() const override { return "CalibreIconEngine"_L1; }
    QPixmap pixmap(const QSize &size, QIcon::Mode mode, QIcon::State state) override {
        ensure_state();
        return pixmap_engine.pixmap(size, mode, state);
    }
    QPixmap scaledPixmap(const QSize &size, QIcon::Mode mode, QIcon::State state, qreal scale) override {
        ensure_state();
        return pixmap_engine.scaledPixmap(size, mode, state, scale);
    }
    QList<QSize> availableSizes(QIcon::Mode mode, QIcon::State state) override {
        ensure_state();
        return pixmap_engine.availableSizes(mode, state);
    }
    void addPixmap(const QPixmap &pixmap, QIcon::Mode mode, QIcon::State state) override {
        ensure_state();
        return pixmap_engine.addPixmap(pixmap, mode, state);
    }
    bool isNull() override {
        ensure_state();
        return pixmap_engine.isNull();
    }
    void virtual_hook(int id, void *data) override {
        ensure_state();
        pixmap_engine.virtual_hook(id, data);
    }
    QString iconName() override { return name; }
};

void
set_icon_theme(bool is_dark, bool has_dark_user_theme, bool has_light_user_theme, bool has_any_user_theme) {
    if (is_dark != theme.using_dark_colors || has_dark_user_theme != theme.has_dark_user_theme || has_light_user_theme != theme.has_light_user_theme || has_any_user_theme != theme.has_any_user_theme) {
        theme.using_dark_colors = is_dark;
        theme.has_dark_user_theme = has_dark_user_theme;
        theme.has_light_user_theme = has_light_user_theme;
        theme.has_any_user_theme = has_any_user_theme;
        current_theme_key.fetch_add(1);
    }
}

QIcon
icon_from_name(QString name, const QByteArray fallback_data) {
    auto engine = new CalibreIconEngine(name, fallback_data);
    return QIcon(reinterpret_cast<QIconEngine*>(engine));
}
