/*
 * imageops.cpp
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "imageops.h"
#define SQUARE(x) (x)*(x)
#define MAX(x, y) ((x) > (y)) ? (x) : (y)
#define DISTANCE(r, g, b) (SQUARE(r - red_average) + SQUARE(g - green_average) + SQUARE(b - blue_average))

unsigned int read_border_row(const QImage &img, const unsigned int width, const unsigned int height, int *reds, const double fuzz, const bool top) {
	unsigned int r = 0, c = 0, start = 0, delta = top ? 1 : -1, ans = 0;
	const QRgb *row = NULL, *pixel = NULL;
    int *greens = NULL, *blues = NULL;
	double red_average = 0, green_average = 0, blue_average = 0, distance = 0, first_red = 0, first_green = 0, first_blue = 0;

    greens = reds + width + 1; blues = greens + width + 1;
	start = top ? 0 : height - 1;

	for (r = start; top ? height - r : r > 0; r += delta) {
		row = reinterpret_cast<const QRgb*>(img.constScanLine(r));
        red_average = 0; green_average = 0; blue_average = 0;
		for (c = 0, pixel = row; c < width; c++, pixel++) {
            reds[c] = qRed(*pixel); greens[c] = qGreen(*pixel); blues[c] = qBlue(*pixel); 
            red_average += reds[c]; green_average += greens[c]; blue_average += blues[c];
		}
        red_average /= MAX(1, width); green_average /= MAX(1, width); blue_average /= MAX(1, width);
        distance = 0;
        for (c = 0; c < width && distance <= fuzz; c++) 
            distance = MAX(distance, DISTANCE(reds[c], greens[c], blues[c]));
        if (distance > fuzz) break;  // row is not homogeneous
        if (r == start) { first_red = red_average; first_green = green_average; first_blue = blue_average; }
        else if (DISTANCE(first_red, first_green, first_blue) > fuzz) break;  // this row's average color is far from the previous row's average color
        ans += 1;
	}
	return ans;
}

QImage* remove_borders(const QImage &image, double fuzz) {
	int *buf = NULL;
	QImage* ans = NULL, img = image, timg;
	QTransform transpose;
	transpose.rotate(90);
	unsigned int width = img.width(), height = img.height();
	unsigned int top_border = 0, bottom_border = 0, left_border = 0, right_border = 0;

	if (img.format() != QImage::Format_RGB32 && img.format() != QImage::Format_ARGB32) {
		img = img.convertToFormat(QImage::Format_RGB32);
		if (img.isNull()) { PyErr_NoMemory(); return NULL; }
	}
	buf = new int[3*(MAX(width, height)+1)];
	fuzz /= 255;

	top_border = read_border_row(img, width, height, buf, fuzz, true);
	if (top_border >= height - 1) goto end;
	bottom_border = read_border_row(img, width, height, buf, fuzz, false);
	if (bottom_border >= height - 1) goto end;
	timg = img.transformed(transpose);
	if (timg.isNull()) { PyErr_NoMemory(); goto end; }
	left_border = read_border_row(timg, height, width, buf, fuzz, true);
	if (left_border >= width - 1) goto end;
	right_border = read_border_row(timg, height, width, buf, fuzz, false);
	if (right_border >= width - 1) goto end;
	if (left_border || right_border || top_border || bottom_border) {
        // printf("111111 l=%d t=%d r=%d b=%d\n", left_border, top_border, right_border, bottom_border);
		img = img.copy(left_border, top_border, width - left_border - right_border, height - top_border - bottom_border);
		if (img.isNull()) { PyErr_NoMemory(); goto end; }
	}

end:
	delete[] buf;
	if (!PyErr_Occurred()) ans = new QImage(img);
	return ans;
}
