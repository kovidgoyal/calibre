/*
 * ordered_dither.cpp
 * Glue code based on quantize.cpp, Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 * Actual ordered dithering routine (dither_o8x8) is Copyright 1999-2019 ImageMagick Studio LLC,
 *
 * Licensed under the ImageMagick License (the "License"); you may not use
 * this file except in compliance with the License.  You may obtain a copy
 * of the License at
 *
 *   https://imagemagick.org/script/license.php

 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
 * License for the specific language governing permissions and limitations
 * under the License.
 */

#include "imageops.h"

// Just in case, as I don't want to deal with MSVC madness...
#if defined _MSC_VER && _MSC_VER < 1700
typedef unsigned __int8 uint8_t;
#define UINT8_MAX _UI8_MAX
typedef unsigned __int32 uint32_t;
#else
#include <stdint.h>
// on older compilers this definition is missing
#ifndef UINT8_MAX
#define UINT8_MAX 255
#endif
#endif

// Only needed for the (commented out) Indexed8 codepath
//#include <QVector>

// NOTE: *May* not behave any better than a simple / 0xFF on modern x86_64 CPUs...
//       This was, however, tested on ARM, where it is noticeably faster.
static uint32_t DIV255(uint32_t v) {
    v += 128;
    return (((v >> 8U) + v) >> 8U);
}

// Quantize an 8-bit color value down to a palette of 16 evenly spaced colors, using an ordered 8x8 dithering pattern.
// With a grayscale input, this happens to match the eInk palette perfectly ;).
// If the input is not grayscale, and the output fb is not grayscale either,
// this usually still happens to match the eInk palette after the EPDC's own quantization pass.
// c.f., https://en.wikipedia.org/wiki/Ordered_dithering
// & https://github.com/ImageMagick/ImageMagick/blob/ecfeac404e75f304004f0566557848c53030bad6/MagickCore/threshold.c#L1627
// NOTE: As the references imply, this is straight from ImageMagick,
//       with only minor simplifications to enforce Q8 & avoid fp maths.
static uint8_t
    dither_o8x8(int x, int y, uint8_t v)
{
    // c.f., https://github.com/ImageMagick/ImageMagick/blob/ecfeac404e75f304004f0566557848c53030bad6/config/thresholds.xml#L107
    static const uint8_t threshold_map_o8x8[] = { 1,  49, 13, 61, 4,  52, 16, 64, 33, 17, 45, 29, 36, 20, 48, 32,
                                                9,  57, 5,  53, 12, 60, 8,  56, 41, 25, 37, 21, 44, 28, 40, 24,
                                                3,  51, 15, 63, 2,  50, 14, 62, 35, 19, 47, 31, 34, 18, 46, 30,
                                                11, 59, 7,  55, 10, 58, 6,  54, 43, 27, 39, 23, 42, 26, 38, 22 };

    // Constants:
    // Quantum = 8; Levels = 16; map Divisor = 65
    // QuantumRange = 0xFF
    // QuantumScale = 1.0 / QuantumRange
    //
    // threshold = QuantumScale * v * ((L-1) * (D-1) + 1)
    // NOTE: The initial computation of t (specifically, what we pass to DIV255) would overflow an uint8_t.
    //       With a Q8 input value, we're at no risk of ever underflowing, so, keep to unsigned maths.
    //       Technically, an uint16_t would be wide enough, but it gains us nothing,
    //       and requires a few explicit casts to make GCC happy ;).
    uint32_t t = DIV255(v * ((15U << 6) + 1U));
    // level = t / (D-1);
    uint32_t l = (t >> 6);
    // t -= l * (D-1);
    t = (t - (l << 6));

    // map width & height = 8
    // c = ClampToQuantum((l+(t >= map[(x % mw) + mw * (y % mh)])) * QuantumRange / (L-1));
    uint32_t q = ((l + (t >= threshold_map_o8x8[(x & 7U) + 8U * (y & 7U)])) * 17);
    // NOTE: We're doing unsigned maths, so, clamping is basically MIN(q, UINT8_MAX) ;).
    //       The only overflow we should ever catch should be for a few white (v = 0xFF) input pixels
    //       that get shifted to the next step (i.e., q = 272 (0xFF + 17)).
    return (q > UINT8_MAX ? UINT8_MAX : static_cast<uint8_t>(q));
}

QImage ordered_dither(const QImage &image) { // {{{
    ScopedGILRelease PyGILRelease;
    QImage img = image;
    int y = 0, x = 0, width = img.width(), height = img.height();
    uint8_t gray = 0, dithered = 0;
    // NOTE: We went with Grayscale8 because QImageWriter was doing some weird things with an Indexed8 input...
    QImage dst(width, height, QImage::Format_Grayscale8);

    /*
    QImage dst(width, height, QImage::Format_Indexed8);

    // Set up the eInk palette
    // FIXME: Make it const and switch to C++11 list init if MSVC is amenable...
    QVector<uint8_t> palette(16);
    QVector<QRgb> color_table(16);
    int i = 0;
    for (i = 0; i < 16; i++) {
        uint8_t color = i * 17;
        palette << color;
        color_table << qRgb(color, color, color);
    }
    dst.setColorTable(color_table);
    */

    // We're running behind blend_image, so, we should only ever be fed RGB32 as input...
    if (img.format() != QImage::Format_RGB32) {
        img = img.convertToFormat(QImage::Format_RGB32);
        if (img.isNull()) throw std::bad_alloc();
    }

    const bool is_gray = img.isGrayscale();

    for (y = 0; y < height; y++) {
        const QRgb *src_row = reinterpret_cast<const QRgb*>(img.constScanLine(y));
        uint8_t *dst_row = dst.scanLine(y);
        for (x = 0; x < width; x++) {
            const QRgb pixel = *(src_row + x);
            if (is_gray) {
                // Grayscale and RGB32, so R = G = B
                gray = qRed(pixel);
            } else {
                gray = qGray(pixel);
            }
            dithered = dither_o8x8(x, y, gray);
            *(dst_row + x) = dithered;  // ... or palette.indexOf(dithered); for Indexed8
        }
    }
    return dst;
} // }}}
