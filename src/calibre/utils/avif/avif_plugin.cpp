/*
 * avif_plugin.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 *
 * A Qt image format plugin for reading AVIF images, based on libavif. Qt does
 * not ship an AVIF plugin, and even when a system one is present it is not
 * available in the calibre binary builds, which bundle their own Qt.
 */

#include "avif_plugin.h"

#include <QColorSpace>
#include <QImage>
#include <QImageReader>
#include <QThread>
#include <QTransform>
#include <QVariant>

#include <avif/avif.h>

// The number of bytes of the start of a file needed to reliably detect the
// AVIF container. The ftyp box has a four byte size, the 'ftyp' tag, a four
// byte major brand, a four byte minor version and then the compatible brands.
static const qint64 PEEK_SIZE = 144;

bool is_avif(const char *data, size_t len) {
    avifROData d = {reinterpret_cast<const uint8_t *>(data), len};
    return avifPeekCompatibleFileType(&d) == AVIF_TRUE;
}

// AvifHandler {{{

AvifHandler::AvifHandler() : decoder(NULL), raw(), parse_failed(false), next_frame(0) {}

AvifHandler::~AvifHandler() {
    if (decoder) {
        avifDecoderDestroy(decoder);
        decoder = NULL;
    }
}

bool AvifHandler::can_read_from(QIODevice *device) {
    if (!device) return false;
    const QByteArray header = device->peek(PEEK_SIZE);
    return is_avif(header.constData(), static_cast<size_t>(header.size()));
}

bool AvifHandler::canRead() const {
    if (decoder) return next_frame < decoder->imageCount;  // already parsed, an image sequence may have more frames
    if (!can_read_from(device())) return false;
    setFormat("avif");
    return true;
}

bool AvifHandler::parse() const {
    if (decoder) return true;
    if (parse_failed) return false;
    parse_failed = true;  // cleared only on success below
    QIODevice *dev = device();
    if (!dev) return false;
    // libavif needs random access to the entire file, so slurp it. The data
    // must outlive the decoder, hence storing it in a member.
    raw = dev->readAll();
    if (raw.isEmpty()) return false;
    avifDecoder *d = avifDecoderCreate();
    if (!d) return false;
    d->maxThreads = qMax(1, QThread::idealThreadCount());
    // Be tolerant of the many AVIF files in the wild that do not quite follow
    // the spec, image viewers are not validators.
    d->strictFlags = AVIF_STRICT_DISABLED;
    d->ignoreExif = AVIF_TRUE;
    d->ignoreXMP = AVIF_TRUE;
    if (avifDecoderSetIOMemory(d, reinterpret_cast<const uint8_t *>(raw.constData()), static_cast<size_t>(raw.size())) != AVIF_RESULT_OK ||
        avifDecoderParse(d) != AVIF_RESULT_OK) {
        avifDecoderDestroy(d);
        return false;
    }
    decoder = d;
    parse_failed = false;
    return true;
}

// Apply the container level transformations, in the order mandated by
// ISO/IEC 23008-12. The clean aperture (clap) transform is deliberately not
// applied, matching what most other AVIF decoders do.
static void apply_transforms(QImage &img, const avifImage *image) {
    if (image->transformFlags & AVIF_TRANSFORM_IROT) {
        const int angle = image->irot.angle & 3;
        // irot specifies an anti-clockwise angle, QTransform::rotate() is
        // clockwise in Qt's y-axis-points-down coordinate system
        if (angle) img = img.transformed(QTransform().rotate(-90.0 * angle));
    }
    if (image->transformFlags & AVIF_TRANSFORM_IMIR) {
        // axis == 0 exchanges the top and bottom of the image, axis == 1 the left and right
        img = img.transformed(image->imir.axis == 0 ? QTransform().scale(1, -1) : QTransform().scale(-1, 1));
    }
}

static QImage::Format qt_format_for(const avifDecoder *decoder) {
    const bool has_alpha = decoder->alphaPresent == AVIF_TRUE;
    if (decoder->image->depth > 8) return has_alpha ? QImage::Format_RGBA64 : QImage::Format_RGBX64;
    return has_alpha ? QImage::Format_RGBA8888 : QImage::Format_RGBX8888;
}

bool AvifHandler::read(QImage *image) {
    if (!parse()) return false;
    if (next_frame >= decoder->imageCount) return false;
    if (avifDecoderNthImage(decoder, static_cast<uint32_t>(next_frame)) != AVIF_RESULT_OK) return false;
    next_frame++;
    const avifImage *im = decoder->image;

    QImage ans(static_cast<int>(im->width), static_cast<int>(im->height), qt_format_for(decoder));
    if (ans.isNull()) return false;  // out of memory or absurd dimensions

    avifRGBImage rgb;
    avifRGBImageSetDefaults(&rgb, im);
    // Format_RGBA8888 and Format_RGBA64 are both R, G, B, A in memory order,
    // regardless of the endianness of the platform
    rgb.format = AVIF_RGB_FORMAT_RGBA;
    rgb.depth = im->depth > 8 ? 16 : 8;
    rgb.alphaPremultiplied = AVIF_FALSE;  // the Format_RGBA* Qt formats are un-premultiplied
    // Note that ignoreAlpha is deliberately left off even for images with no
    // alpha plane, so that libavif fills in opaque alpha rather than leaving
    // the uninitialized bytes of the unused channel of the Format_RGBX*
    // images in place
    rgb.maxThreads = decoder->maxThreads;
    rgb.pixels = ans.bits();
    rgb.rowBytes = static_cast<uint32_t>(ans.bytesPerLine());
    if (avifImageYUVToRGB(im, &rgb) != AVIF_RESULT_OK) return false;

    if (im->icc.size) {
        const QColorSpace cs = QColorSpace::fromIccProfile(QByteArray(reinterpret_cast<const char *>(im->icc.data), static_cast<qsizetype>(im->icc.size)));
        if (cs.isValid()) ans.setColorSpace(cs);
    }
    apply_transforms(ans, im);
    *image = ans;
    return true;
}

QVariant AvifHandler::option(ImageOption option) const {
    switch (option) {
        case Size: {
            if (!parse()) return QVariant();
            const avifImage *im = decoder->image;
            QSize sz(static_cast<int>(im->width), static_cast<int>(im->height));
            if ((im->transformFlags & AVIF_TRANSFORM_IROT) && (im->irot.angle & 1)) sz.transpose();
            return sz;
        }
        case ImageFormat:
            if (!parse()) return QVariant();
            return QVariant::fromValue(qt_format_for(decoder));
        case Animation:
            if (!parse()) return QVariant();
            return decoder->imageCount > 1;
        default:
            break;
    }
    return QVariant();
}

bool AvifHandler::supportsOption(ImageOption option) const {
    return option == Size || option == ImageFormat || option == Animation;
}

int AvifHandler::imageCount() const {
    if (!parse()) return 0;
    return decoder->imageCount;
}

int AvifHandler::currentImageNumber() const { return next_frame; }

bool AvifHandler::jumpToImage(int image_number) {
    if (!parse()) return false;
    if (image_number < 0 || image_number >= decoder->imageCount) return false;
    next_frame = image_number;
    return true;
}

bool AvifHandler::jumpToNextImage() { return jumpToImage(next_frame + 1); }

int AvifHandler::nextImageDelay() const {
    if (!parse()) return 0;
    // The time to wait before showing the next frame is the duration of the
    // frame that was read most recently
    const uint32_t frame = static_cast<uint32_t>(qBound(0, next_frame - 1, decoder->imageCount - 1));
    avifImageTiming timing;
    if (avifDecoderNthImageTiming(decoder, frame, &timing) != AVIF_RESULT_OK) return 0;
    return static_cast<int>(timing.duration * 1000.0);
}

int AvifHandler::loopCount() const {
    if (!parse() || decoder->imageCount < 2) return -1;
    // Qt uses -1 to mean loop forever, or that the count is unknown, while
    // libavif uses a repetition count, i.e. the number of times to repeat
    // after the first playthrough
    switch (decoder->repetitionCount) {
        case AVIF_REPETITION_COUNT_INFINITE:
        case AVIF_REPETITION_COUNT_UNKNOWN:
            return -1;
        default:
            return decoder->repetitionCount;
    }
}

// }}}

// AvifPlugin {{{

QImageIOPlugin::Capabilities AvifPlugin::capabilities(QIODevice *device, const QByteArray &format) const {
    if (format == "avif") return Capabilities(CanRead);
    if (!format.isEmpty()) return Capabilities();
    if (device && device->isReadable() && AvifHandler::can_read_from(device)) return Capabilities(CanRead);
    return Capabilities();
}

QImageIOHandler *AvifPlugin::create(QIODevice *device, const QByteArray &format) const {
    QImageIOHandler *handler = new AvifHandler();
    handler->setDevice(device);
    handler->setFormat(format.isEmpty() ? QByteArray("avif") : format);
    return handler;
}

// Registers the plugin with Qt when this shared object is loaded, i.e. when
// the calibre_extensions.avif module is imported
Q_IMPORT_PLUGIN(AvifPlugin)

bool register_avif_image_format() { return QImageReader::supportedImageFormats().contains(QByteArray("avif")); }

// }}}
