/*
 * imageops.h
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#pragma once

#include <QImage>
#include <Python.h>

QImage remove_borders(const QImage &image, double fuzz);
QImage grayscale(const QImage &image);
QImage gaussian_sharpen(const QImage &img, const float radius, const float sigma, const bool high_quality=true);
QImage gaussian_blur(const QImage &img, const float radius, const float sigma);
QImage despeckle(const QImage &image);
void overlay(const QImage &image, QImage &canvas, unsigned int left, unsigned int top);

