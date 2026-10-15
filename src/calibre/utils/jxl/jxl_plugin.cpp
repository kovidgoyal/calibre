/*
 * jxl_plugin.cpp
 * Copyright (C) 2026 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 *
 * A Qt image format plugin for reading and writing JPEG-XL images, based on
 * libjxl. Qt does not ship a JPEG-XL plugin, and even when a system one is
 * present it is not available in the calibre binary builds, which bundle their
 * own Qt.
 */

#include "jxl_plugin.h"

#include <QColorSpace>
#include <QImage>
#include <QImageReader>
#include <QImageWriter>
#include <QVariant>

#include <climits>
#include <cmath>
#include <limits>
#include <vector>

#include <jxl/cms.h>
#include <jxl/decode.h>
#include <jxl/decode_cxx.h>
#include <jxl/encode.h>
#include <jxl/encode_cxx.h>
#include <jxl/thread_parallel_runner.h>
#include <jxl/thread_parallel_runner_cxx.h>

// The number of bytes of the start of a file needed to detect JPEG-XL, the
// container signature box is twelve bytes, a bare codestream starts with two
// signature bytes
static const qint64 PEEK_SIZE = 12;

bool
is_jxl(const char *data, size_t len) {
    switch (JxlSignatureCheck(reinterpret_cast<const uint8_t *>(data), len)) {
        case JXL_SIG_CODESTREAM:
        case JXL_SIG_CONTAINER: return true;
        default: return false;
    }
}

static JxlThreadParallelRunnerPtr
create_runner() {
    return JxlThreadParallelRunnerMake(NULL, JxlThreadParallelRunnerDefaultNumWorkerThreads());
}

// JxlHandler::Decoder {{{

struct JxlHandler::Decoder {
    // The members are destroyed in reverse order of declaration. The decoder
    // holds pointers to both the input data and the parallel runner, so it
    // must be declared last, to be destroyed first. The input data must never
    // be modified while the decoder exists, as that could cause QByteArray to
    // re-allocate its storage.
    const QByteArray raw;
    JxlThreadParallelRunnerPtr runner;
    JxlDecoderPtr dec;

    JxlBasicInfo info;
    QColorSpace color_space;
    // The delay after each frame, in milliseconds, also gives the number of frames
    std::vector<int> delays;
    // The number of the frame the decoder will output next, -1 if it must be
    // restarted before it can output anything
    int position;
    // Whether to convert images stored in the XYB color space to their
    // original color profile, see on_color_encoding()
    bool output_original_profile;

    explicit Decoder(const QByteArray &data) : raw(data), runner(), dec(), info(), color_space(), delays(), position(-1), output_original_profile(true) {}

    int
    frame_count() const {
        return static_cast<int>(delays.size());
    }
    bool
    has_alpha() const {
        return info.alpha_bits > 0;
    }
    bool
    is_deep() const {
        return info.bits_per_sample > 8;
    }
    // Grayscale images with alpha are decoded to RGBA as Qt has no
    // grayscale with alpha format
    bool
    is_gray() const {
        return info.num_color_channels == 1 && !has_alpha();
    }

    QSize
    size() const {
        // xsize and ysize are before the orientation is applied and
        // orientations from 5 onwards transpose the image
        QSize ans(static_cast<int>(info.xsize), static_cast<int>(info.ysize));
        if (info.orientation >= JXL_ORIENT_TRANSPOSE) ans.transpose();
        return ans;
    }

    QImage::Format
    qt_format() const {
        if (is_gray()) return is_deep() ? QImage::Format_Grayscale16 : QImage::Format_Grayscale8;
        // The RGBA8888 and RGBA64 Qt formats are un-premultiplied and are R,
        // G, B, A in memory order, with 16 bit values in native byte order,
        // which is what libjxl outputs. The RGBX formats are the same with
        // the alpha channel required to be opaque, libjxl fills it with
        // opaque values for images without alpha.
        if (is_deep()) return has_alpha() ? QImage::Format_RGBA64 : QImage::Format_RGBX64;
        return has_alpha() ? QImage::Format_RGBA8888 : QImage::Format_RGBX8888;
    }

    JxlPixelFormat
    pixel_format(size_t bytes_per_line) const {
        JxlPixelFormat ans;
        ans.num_channels = is_gray() ? 1 : 4;
        ans.data_type = is_deep() ? JXL_TYPE_UINT16 : JXL_TYPE_UINT8;
        ans.endianness = JXL_NATIVE_ENDIAN;
        // Each row of the output starts at a multiple of bytes_per_line,
        // which is at least the size of a row of pixels, i.e. every row is
        // exactly bytes_per_line long, as in a QImage
        ans.align = bytes_per_line;
        return ans;
    }

    // Set up a newly created or reset decoder to decode all of raw, emitting
    // the specified events
    bool
    configure(int events) {
        if (JxlDecoderSetParallelRunner(dec.get(), JxlThreadParallelRunner, runner.get()) != JXL_DEC_SUCCESS) return false;
        // The color management system is used to convert images in the XYB
        // color space to their original color profile, see on_color_encoding()
        if (JxlDecoderSetCms(dec.get(), *JxlGetDefaultCms()) != JXL_DEC_SUCCESS) return false;
        if (JxlDecoderSubscribeEvents(dec.get(), events) != JXL_DEC_SUCCESS) return false;
        if (JxlDecoderSetInput(dec.get(), reinterpret_cast<const uint8_t *>(raw.constData()), static_cast<size_t>(raw.size())) != JXL_DEC_SUCCESS) return false;
        JxlDecoderCloseInput(dec.get());
        return true;
    }

    bool
    request_original_profile() {
        JxlColorEncoding ce;
        if (JxlDecoderGetColorAsEncodedProfile(dec.get(), JXL_COLOR_PROFILE_TARGET_ORIGINAL, &ce) == JXL_DEC_SUCCESS)
            return JxlDecoderSetOutputColorProfile(dec.get(), &ce, NULL, 0) == JXL_DEC_SUCCESS;
        size_t sz = 0;
        if (JxlDecoderGetICCProfileSize(dec.get(), JXL_COLOR_PROFILE_TARGET_ORIGINAL, &sz) != JXL_DEC_SUCCESS || sz == 0 || sz > static_cast<size_t>(INT_MAX))
            return false;
        QByteArray icc(static_cast<qsizetype>(sz), 0);
        if (JxlDecoderGetColorAsICCProfile(dec.get(), JXL_COLOR_PROFILE_TARGET_ORIGINAL, reinterpret_cast<uint8_t *>(icc.data()), sz) != JXL_DEC_SUCCESS)
            return false;
        // libjxl copies the profile
        return JxlDecoderSetOutputColorProfile(dec.get(), NULL, reinterpret_cast<const uint8_t *>(icc.constData()), sz) == JXL_DEC_SUCCESS;
    }

    // The color space of the pixels the decoder outputs
    QColorSpace
    output_color_space() const {
        size_t sz = 0;
        if (JxlDecoderGetICCProfileSize(dec.get(), JXL_COLOR_PROFILE_TARGET_DATA, &sz) != JXL_DEC_SUCCESS || sz == 0 || sz > static_cast<size_t>(INT_MAX))
            return QColorSpace();
        QByteArray icc(static_cast<qsizetype>(sz), 0);
        if (JxlDecoderGetColorAsICCProfile(dec.get(), JXL_COLOR_PROFILE_TARGET_DATA, reinterpret_cast<uint8_t *>(icc.data()), sz) != JXL_DEC_SUCCESS)
            return QColorSpace();
        const QColorSpace cs = QColorSpace::fromIccProfile(icc);
        // The decoded image is only grayscale if it has no alpha
        const QColorSpace::ColorModel needed = is_gray() ? QColorSpace::ColorModel::Gray : QColorSpace::ColorModel::Rgb;
        return cs.isValid() && cs.colorModel() == needed ? cs : QColorSpace();
    }

    // Must be called on the JXL_DEC_COLOR_ENCODING event. Lossy encoding
    // stores images in the XYB color space, which libjxl by default decodes
    // to linear sRGB, causing banding at eight bits per channel, so have it
    // convert to the original color profile of the image instead. That needs
    // the color management system, which does not support all profiles, and
    // fails only once decoding starts, in which case read() turns off
    // output_original_profile and decodes again, converting to sRGB, which
    // the decoder can do by itself.
    void
    on_color_encoding() {
        if (!info.uses_original_profile && !(output_original_profile && request_original_profile())) {
            JxlColorEncoding ce;
            JxlColorEncodingSetToSRGB(&ce, info.num_color_channels == 1 ? JXL_TRUE : JXL_FALSE);
            // Failure is not fatal, the pixels are then in the default
            // profile, which is what output_color_space() reports
            JxlDecoderSetOutputColorProfile(dec.get(), &ce, NULL, 0);
        }
        color_space = output_color_space();
    }

    // Initialize the decoder, the image headers are read and all frames are
    // scanned to find out how many there are and their durations
    bool
    initialize() {
        if (raw.isEmpty()) return false;
        runner = create_runner();
        if (!runner) return false;
        dec = JxlDecoderMake(NULL);
        if (!dec) return false;
        if (!configure(JXL_DEC_BASIC_INFO | JXL_DEC_COLOR_ENCODING | JXL_DEC_FRAME)) return false;
        bool have_info = false, have_color = false;
        while (true) {
            switch (JxlDecoderProcessInput(dec.get())) {
                case JXL_DEC_BASIC_INFO:
                    if (JxlDecoderGetBasicInfo(dec.get(), &info) != JXL_DEC_SUCCESS) return false;
                    if (info.xsize < 1 || info.ysize < 1 || info.xsize > INT_MAX || info.ysize > INT_MAX) return false;
                    have_info = true;
                    break;
                case JXL_DEC_COLOR_ENCODING: {
                    if (!have_info) return false;
                    on_color_encoding();
                    have_color = true;
                    if (!info.have_animation) {
                        // A still image has exactly one frame, no need to scan the rest of the file
                        delays.push_back(0);
                        return true;
                    }
                } break;
                case JXL_DEC_FRAME: {
                    if (!have_info || !have_color) return false;
                    JxlFrameHeader header;
                    if (JxlDecoderGetFrameHeader(dec.get(), &header) != JXL_DEC_SUCCESS) return false;
                    double ms = 0;
                    if (info.animation.tps_numerator > 0)
                        ms = 1000.0 * header.duration * info.animation.tps_denominator / static_cast<double>(info.animation.tps_numerator);
                    delays.push_back(static_cast<int>(std::fmin(ms, static_cast<double>(INT_MAX))));
                    if (delays.size() >= static_cast<size_t>(INT_MAX)) return false;
                    // Since the decoder is not subscribed to JXL_DEC_FULL_IMAGE
                    // the pixels of the frame are skipped
                } break;
                case JXL_DEC_SUCCESS: return have_info && have_color && !delays.empty();
                // All the data was supplied, so needing more input means it is truncated
                default: return false;
            }
        }
    }

    // Discard all decoding state. A full reset rather than a rewind, so that
    // nothing from previous decoding, in particular a pointer to an image
    // buffer, can survive. Must be called whenever decoding fails.
    void
    invalidate() {
        JxlDecoderReset(dec.get());
        position = -1;
    }

    // Make the decoder ready to output the specified frame next
    bool
    restart(int frame) {
        invalidate();
        if (!configure(JXL_DEC_COLOR_ENCODING | JXL_DEC_FULL_IMAGE)) {
            invalidate();
            return false;
        }
        if (frame > 0) JxlDecoderSkipFrames(dec.get(), static_cast<size_t>(frame));
        position = frame;
        return true;
    }

    // Decode the next frame into img, which must have the size and format
    // given by size() and qt_format()
    bool
    decode_next_frame(QImage &img) {
        if (position < 0 || position >= frame_count()) return false;
        const JxlPixelFormat fmt = pixel_format(static_cast<size_t>(img.bytesPerLine()));
        bool buffer_set = false;
        while (true) {
            switch (JxlDecoderProcessInput(dec.get())) {
                // Only emitted for the first frame decoded after a restart
                case JXL_DEC_COLOR_ENCODING: on_color_encoding(); break;
                case JXL_DEC_NEED_IMAGE_OUT_BUFFER: {
                    if (buffer_set) return false;
                    size_t needed = 0;
                    if (JxlDecoderImageOutBufferSize(dec.get(), &fmt, &needed) != JXL_DEC_SUCCESS) return false;
                    const size_t available = static_cast<size_t>(img.sizeInBytes());
                    if (needed > available) return false;
                    // img is not touched again until the decoder is done
                    // writing to its pixels, so they will not be
                    // re-allocated. Calling bits() on a newly allocated, so
                    // unshared, image does not detach it.
                    if (JxlDecoderSetImageOutBuffer(dec.get(), &fmt, img.bits(), available) != JXL_DEC_SUCCESS) return false;
                    buffer_set = true;
                } break;
                case JXL_DEC_FULL_IMAGE:
                    // The decoder is done with the buffer, the next frame needs a new one
                    if (!buffer_set) return false;
                    position++;
                    return true;
                default: return false;
            }
        }
    }
};

// }}}

// JxlHandler {{{

JxlHandler::JxlHandler() : decoder(), parse_failed(false), next_frame(0), quality(-1) {}

JxlHandler::~JxlHandler() {}

bool
JxlHandler::can_read_from(QIODevice *device) {
    if (!device) return false;
    const QByteArray header = device->peek(PEEK_SIZE);
    return is_jxl(header.constData(), static_cast<size_t>(header.size()));
}

bool
JxlHandler::canRead() const {
    if (decoder) return next_frame < decoder->frame_count(); // already parsed, an animation may have more frames
    if (!can_read_from(device())) return false;
    setFormat("jxl");
    return true;
}

bool
JxlHandler::parse() const {
    if (decoder) return true;
    if (parse_failed) return false;
    parse_failed = true; // cleared only on success below
    QIODevice *dev = device();
    if (!dev) return false;
    // libjxl can decode incrementally, but the frames of an animation must
    // be scanned to count them and jumping between frames needs to restart
    // decoding from the beginning, so slurp the whole file. The decoder keeps
    // its own copy of the data, which outlives the libjxl decoder.
    std::unique_ptr<Decoder> d(new Decoder(dev->readAll()));
    if (!d->initialize()) return false;
    decoder = std::move(d);
    parse_failed = false;
    return true;
}

bool
JxlHandler::read(QImage *image) {
    if (!parse()) return false;
    if (next_frame >= decoder->frame_count()) return false;
    // Respects the allocation limit of QImageReader, so very large images
    // fail cleanly rather than exhausting memory
    QImage ans;
    if (!QImageIOHandler::allocateImage(decoder->size(), decoder->qt_format(), &ans)) return false;
    while (true) {
        if (decoder->position != next_frame && !decoder->restart(next_frame)) return false;
        if (decoder->decode_next_frame(ans)) break;
        // The decoder may hold a pointer to the pixels of ans, so reset it
        // before anything else can happen
        decoder->invalidate();
        if (decoder->info.uses_original_profile || !decoder->output_original_profile) return false;
        // Try again without converting to the original color profile, see Decoder::on_color_encoding()
        decoder->output_original_profile = false;
    }
    next_frame++;
    if (decoder->color_space.isValid()) ans.setColorSpace(decoder->color_space);
    *image = ans;
    return true;
}

// The pixels of an image in a layout libjxl can encode
struct EncoderInput {
    QImage image;
    // Pixels with three 16 bit channels, for which Qt has no image format,
    // when non-empty used instead of image
    std::vector<uint16_t> packed;

    // constBits() never detaches, so this pointer remains valid as long as
    // this object is alive and unmodified
    const void *
    data() const {
        return packed.empty() ? static_cast<const void *>(image.constBits()) : static_cast<const void *>(packed.data());
    }
    size_t
    size() const {
        return packed.empty() ? static_cast<size_t>(image.sizeInBytes()) : packed.size() * sizeof(uint16_t);
    }
};

// Convert img to a format libjxl can encode, filling in the details of the
// format used. Returns false on failure.
static bool
prepare_for_encoding(const QImage &img, EncoderInput &input, JxlBasicInfo &info, JxlPixelFormat &fmt, QColorSpace &cs) {
    const QImage::Format src = img.format();
    const bool has_alpha = img.hasAlphaChannel();
    // Formats with more than eight bits per color channel
    bool deep = false;
    switch (src) {
        case QImage::Format_Grayscale16:
        case QImage::Format_RGBX64:
        case QImage::Format_RGBA64:
        case QImage::Format_RGBA64_Premultiplied:
        case QImage::Format_BGR30:
        case QImage::Format_A2BGR30_Premultiplied:
        case QImage::Format_RGB30:
        case QImage::Format_A2RGB30_Premultiplied:
        case QImage::Format_RGBX16FPx4:
        case QImage::Format_RGBA16FPx4:
        case QImage::Format_RGBA16FPx4_Premultiplied:
        case QImage::Format_RGBX32FPx4:
        case QImage::Format_RGBA32FPx4:
        case QImage::Format_RGBA32FPx4_Premultiplied: deep = true; break;
        default: break;
    }
    cs = img.colorSpace();
    bool gray = !has_alpha && (src == QImage::Format_Grayscale8 || src == QImage::Format_Grayscale16);
    // An RGB color space cannot be used with grayscale data
    if (gray && cs.isValid() && cs.colorModel() != QColorSpace::ColorModel::Gray) gray = false;
    // and a grayscale color space cannot be used for color data
    if (!gray && cs.isValid() && cs.colorModel() != QColorSpace::ColorModel::Rgb) cs = QColorSpace();

    QImage::Format target;
    if (gray) target = deep ? QImage::Format_Grayscale16 : QImage::Format_Grayscale8;
    else if (deep) target = has_alpha ? QImage::Format_RGBA64 : QImage::Format_RGBX64;
    else target = has_alpha ? QImage::Format_RGBA8888 : QImage::Format_RGB888;
    // Note that the target formats are all un-premultiplied
    input.image = img.convertToFormat(target);
    if (input.image.isNull()) return false;
    const QImage &ans = input.image;

    JxlEncoderInitBasicInfo(&info);
    info.xsize = static_cast<uint32_t>(ans.width());
    info.ysize = static_cast<uint32_t>(ans.height());
    info.bits_per_sample = deep ? 16 : 8;
    info.exponent_bits_per_sample = 0;
    info.num_color_channels = gray ? 1 : 3;
    info.num_extra_channels = has_alpha ? 1 : 0;
    info.alpha_bits = has_alpha ? info.bits_per_sample : 0;
    info.alpha_exponent_bits = 0;
    info.alpha_premultiplied = JXL_FALSE;

    fmt.num_channels = gray ? 1 : (has_alpha ? 4 : 3);
    fmt.data_type = deep ? JXL_TYPE_UINT16 : JXL_TYPE_UINT8;
    fmt.endianness = JXL_NATIVE_ENDIAN;
    // Every row is exactly bytesPerLine() long, see Decoder::pixel_format()
    fmt.align = static_cast<size_t>(ans.bytesPerLine());

    if (target == QImage::Format_RGBX64) {
        // libjxl will not accept four channels for an image without alpha,
        // so drop the padding channel
        const size_t width = static_cast<size_t>(ans.width()), height = static_cast<size_t>(ans.height());
        input.packed.resize(width * height * 3);
        uint16_t *dest = input.packed.data();
        for (size_t y = 0; y < height; y++) {
            const uint16_t *row = reinterpret_cast<const uint16_t *>(ans.constScanLine(static_cast<int>(y)));
            for (size_t x = 0; x < width; x++, row += 4, dest += 3) {
                dest[0] = row[0];
                dest[1] = row[1];
                dest[2] = row[2];
            }
        }
        fmt.align = 0;
        input.image = QImage();
    }
    return true;
}

bool
JxlHandler::write(const QImage &image) {
    QIODevice *dev = device();
    if (!dev || image.isNull()) return false;
    JxlBasicInfo info;
    JxlPixelFormat fmt;
    QColorSpace cs;
    EncoderInput input;
    if (!prepare_for_encoding(image, input, info, fmt, cs)) return false;
    const bool lossless = quality >= 100;
    // Lossless encoding requires the pixels to be stored in their original
    // color space rather than converted to XYB
    info.uses_original_profile = lossless ? JXL_TRUE : JXL_FALSE;

    // The encoder holds a pointer to the runner, so it must be destroyed
    // first, which it is, being declared later
    JxlThreadParallelRunnerPtr runner = create_runner();
    if (!runner) return false;
    JxlEncoderPtr enc = JxlEncoderMake(NULL);
    if (!enc) return false;
    if (JxlEncoderSetParallelRunner(enc.get(), JxlThreadParallelRunner, runner.get()) != JXL_ENC_SUCCESS) return false;
    if (JxlEncoderSetBasicInfo(enc.get(), &info) != JXL_ENC_SUCCESS) return false;

    bool color_set = false;
    if (cs.isValid() && cs != QColorSpace(QColorSpace::SRgb)) {
        const QByteArray icc = cs.iccProfile();
        if (!icc.isEmpty())
            color_set =
                JxlEncoderSetICCProfile(enc.get(), reinterpret_cast<const uint8_t *>(icc.constData()), static_cast<size_t>(icc.size())) == JXL_ENC_SUCCESS;
    }
    if (!color_set) {
        // Images with no color space are assumed to be sRGB, as everywhere
        // else in Qt
        JxlColorEncoding ce;
        JxlColorEncodingSetToSRGB(&ce, info.num_color_channels == 1 ? JXL_TRUE : JXL_FALSE);
        if (JxlEncoderSetColorEncoding(enc.get(), &ce) != JXL_ENC_SUCCESS) return false;
    }

    // Owned by, and freed together with, the encoder
    JxlEncoderFrameSettings *settings = JxlEncoderFrameSettingsCreate(enc.get(), NULL);
    if (!settings) return false;
    if (lossless) {
        if (JxlEncoderSetFrameLossless(settings, JXL_TRUE) != JXL_ENC_SUCCESS) return false;
    } else {
        // With no quality specified use the libjxl default, which is
        // visually lossless
        const float distance = quality < 0 ? 1.0f : JxlEncoderDistanceFromQuality(static_cast<float>(quality));
        if (JxlEncoderSetFrameDistance(settings, distance) != JXL_ENC_SUCCESS) return false;
    }
    // libjxl copies the pixels, so input only needs to live until this returns
    const size_t input_size = input.size();
    if (JxlEncoderAddImageFrame(settings, &fmt, input.data(), input_size) != JXL_ENC_SUCCESS) return false;
    JxlEncoderCloseInput(enc.get());

    QByteArray output;
    output.resize(static_cast<qsizetype>(qMax(size_t(4096), input_size / 8)));
    size_t used = 0;
    while (true) {
        uint8_t *next_out = reinterpret_cast<uint8_t *>(output.data()) + used;
        size_t avail_out = static_cast<size_t>(output.size()) - used;
        const JxlEncoderStatus status = JxlEncoderProcessOutput(enc.get(), &next_out, &avail_out);
        // Compute how much has been written from the pointer libjxl updated,
        // before output is resized, which can move its data
        used = static_cast<size_t>(next_out - reinterpret_cast<uint8_t *>(output.data()));
        if (status == JXL_ENC_SUCCESS) break;
        if (status != JXL_ENC_NEED_MORE_OUTPUT) return false;
        if (output.size() > std::numeric_limits<qsizetype>::max() / 2) return false;
        output.resize(output.size() * 2);
    }
    output.truncate(static_cast<qsizetype>(used));
    return dev->write(output) == output.size();
}

QVariant
JxlHandler::option(ImageOption option) const {
    switch (option) {
        case Size:
            if (!parse()) return QVariant();
            return decoder->size();
        case ImageFormat:
            if (!parse()) return QVariant();
            return QVariant::fromValue(decoder->qt_format());
        case Animation:
            if (!parse()) return QVariant();
            return decoder->frame_count() > 1;
        case Quality: return quality;
        default: break;
    }
    return QVariant();
}

void
JxlHandler::setOption(ImageOption option, const QVariant &value) {
    if (option == Quality) {
        bool ok = false;
        const int q = value.toInt(&ok);
        // Qt uses -1 for the default quality
        quality = ok ? qBound(-1, q, 100) : -1;
    }
}

bool
JxlHandler::supportsOption(ImageOption option) const {
    return option == Size || option == ImageFormat || option == Animation || option == Quality;
}

int
JxlHandler::imageCount() const {
    if (!parse()) return 0;
    return decoder->frame_count();
}

int
JxlHandler::currentImageNumber() const {
    return next_frame;
}

bool
JxlHandler::jumpToImage(int image_number) {
    if (!parse()) return false;
    if (image_number < 0 || image_number >= decoder->frame_count()) return false;
    next_frame = image_number;
    return true;
}

bool
JxlHandler::jumpToNextImage() {
    return jumpToImage(next_frame + 1);
}

int
JxlHandler::nextImageDelay() const {
    if (!parse()) return 0;
    // The time to wait before showing the next frame is the duration of the
    // frame that was read most recently
    return decoder->delays[static_cast<size_t>(qBound(0, next_frame - 1, decoder->frame_count() - 1))];
}

int
JxlHandler::loopCount() const {
    if (!parse() || decoder->frame_count() < 2) return -1;
    // Qt uses -1 to mean loop forever and otherwise the number of times to
    // repeat after the first playthrough while libjxl uses 0 for forever and
    // otherwise the total number of times to play
    const uint32_t loops = decoder->info.animation.num_loops;
    if (loops == 0) return -1;
    return static_cast<int>(qMin(loops - 1, static_cast<uint32_t>(INT_MAX)));
}

// }}}

// JxlPlugin {{{

QImageIOPlugin::Capabilities
JxlPlugin::capabilities(QIODevice *device, const QByteArray &format) const {
    if (format == "jxl") return Capabilities(CanRead | CanWrite);
    if (!format.isEmpty()) return Capabilities();
    if (device && device->isReadable() && JxlHandler::can_read_from(device)) return Capabilities(CanRead);
    return Capabilities();
}

QImageIOHandler *
JxlPlugin::create(QIODevice *device, const QByteArray &format) const {
    QImageIOHandler *handler = new JxlHandler();
    handler->setDevice(device);
    handler->setFormat(format.isEmpty() ? QByteArray("jxl") : format);
    return handler;
}

// Registers the plugin with Qt when this shared object is loaded, i.e. when
// the calibre_extensions.jxl module is imported
Q_IMPORT_PLUGIN(JxlPlugin)

bool
register_jxl_image_format() {
    return QImageReader::supportedImageFormats().contains(QByteArray("jxl")) && QImageWriter::supportedImageFormats().contains(QByteArray("jxl"));
}

// }}}
