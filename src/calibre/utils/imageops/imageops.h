/*
 * imageops.h
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once
#define PY_SSIZE_T_CLEAN

#include <Python.h>
#include <QImage>

QImage remove_borders(const QImage &image, double fuzz);
QImage grayscale(const QImage &image);
QImage gaussian_sharpen(const QImage &img, const float radius, const float sigma, const bool high_quality=true);
QImage gaussian_blur(const QImage &img, const float radius, const float sigma);
QImage despeckle(const QImage &image);
void overlay(const QImage &image, QImage &canvas, unsigned int left, unsigned int top);
QImage normalize(const QImage &image);
QImage oil_paint(const QImage &image, const float radius=-1, const bool high_quality=true);
QImage quantize(const QImage &image, unsigned int maximum_colors, bool dither, const QVector<QRgb> &palette);
bool has_transparent_pixels(const QImage &image);
QImage set_opacity(const QImage &image, double alpha);
QImage texture_image(const QImage &image, const QImage &texturei);
QImage ordered_dither(const QImage &image);

class ScopedGILRelease {
public:
    inline ScopedGILRelease() { this->thread_state = PyEval_SaveThread(); }
    inline ~ScopedGILRelease() { PyEval_RestoreThread(this->thread_state); this->thread_state = NULL; }
private:
    PyThreadState * thread_state;
};
