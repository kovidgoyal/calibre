/*
 * imageops.cpp
 * Copyright (C) 2016 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include <stdexcept>
#include "imageops.h"
#include <QColor>
#include <cmath>

#define SQUARE(x) (x)*(x)
#define MAX(x, y) ((x) > (y)) ? (x) : (y)
#define DISTANCE(r, g, b) (SQUARE(r - red_average) + SQUARE(g - green_average) + SQUARE(b - blue_average))
#define M_EPSILON 1.0e-6
#define M_SQ2PI 2.50662827463100024161235523934010416269302368164062
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// Remove borders (auto-trim) {{{
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

#define ENSURE32(img) \
	if (img.format() != QImage::Format_RGB32 && img.format() != QImage::Format_ARGB32) { \
		img = img.convertToFormat(img.hasAlphaChannel() ? QImage::Format_ARGB32 : QImage::Format_RGB32); \
		if (img.isNull()) throw std::bad_alloc(); \
	} \

QImage remove_borders(const QImage &image, double fuzz) {
	int *buf = NULL;
	QImage img = image, timg;
	QTransform transpose;
	unsigned int width = img.width(), height = img.height();
	unsigned int top_border = 0, bottom_border = 0, left_border = 0, right_border = 0;
    bool bad_alloc = false;

    ENSURE32(img)
	buf = new int[3*(MAX(width, height)+1)];
	fuzz /= 255;

    Py_BEGIN_ALLOW_THREADS;
	top_border = read_border_row(img, width, height, buf, fuzz, true);
    if (top_border < height - 1) {
        bottom_border = read_border_row(img, width, height, buf, fuzz, false);
        if (bottom_border < height - 1) {
            transpose.rotate(90);
            timg = img.transformed(transpose);
            if (timg.isNull()) bad_alloc = true; 
            else {
                left_border = read_border_row(timg, height, width, buf, fuzz, true);
                if (left_border < width - 1) {
                    right_border = read_border_row(timg, height, width, buf, fuzz, false);
                    if (right_border < width - 1) {
                        if (left_border || right_border || top_border || bottom_border) {
                            // printf("111111 l=%d t=%d r=%d b=%d\n", left_border, top_border, right_border, bottom_border);
                            img = img.copy(left_border, top_border, width - left_border - right_border, height - top_border - bottom_border);
                            if (img.isNull()) bad_alloc = true;
                        }
                    }
                }
            }
        }
    }
    Py_END_ALLOW_THREADS;

	delete[] buf;
    if (bad_alloc) throw std::bad_alloc();
    return img;
}
// }}}

QImage grayscale(const QImage &image) { // {{{
    QImage img = image;
    QRgb *row = NULL, *pixel = NULL;
    int r = 0, gray = 0, width = img.width(), height = img.height();

    ENSURE32(img);
    Py_BEGIN_ALLOW_THREADS;
    for (r = 0; r < height; r++) {
		row = reinterpret_cast<QRgb*>(img.scanLine(r));
        for (pixel = row; pixel < row + width; pixel++) {
            gray = qGray(*pixel);
            *pixel = QColor(gray, gray, gray).rgba();
        }
    }
    Py_END_ALLOW_THREADS;
	return img;
} // }}}

// Convolution {{{
#define CONVOLVE_ACC(weight, pixel) \
    r+=((weight))*(qRed((pixel))); g+=((weight))*(qGreen((pixel))); \
    b+=((weight))*(qBlue((pixel)));

QImage convolve(const QImage &image, int matrix_size, float *matrix) {
    int i, x, y, w, h, matrix_x, matrix_y;
    int edge = matrix_size/2;
    QRgb *dest, *s, **scanblock;
    const QRgb *src = NULL;
    float *m, *normalize_matrix, normalize, r, g, b;
    QImage img(image);

    if(!(matrix_size % 2))
        throw std::out_of_range("Convolution kernel width must be an odd number");

    w = img.width();
    h = img.height();
    if(w < 3 || h < 3) return img;

    ENSURE32(img);

    QImage buffer = QImage(w, h, img.format());
    scanblock = new QRgb* [matrix_size];
    normalize_matrix = new float[matrix_size*matrix_size];
    Py_BEGIN_ALLOW_THREADS;

    // create normalized matrix
    normalize = 0.0;
    for(i=0; i < matrix_size*matrix_size; ++i)
        normalize += matrix[i];
    if(std::abs(normalize) <=  M_EPSILON)
        normalize = 1.0;
    normalize = 1.0/normalize;
    for(i=0; i < matrix_size*matrix_size; ++i)
        normalize_matrix[i] = normalize*matrix[i];

    // apply

    for(y=0; y < h; ++y){
        src = reinterpret_cast<const QRgb*>(img.constScanLine(y));
        dest = (QRgb *)buffer.scanLine(y);
        // Read in scanlines to pixel neighborhood. If the scanline is outside
        // the image use the top or bottom edge.
        for(x=y-edge, i=0; x <= y+edge; ++i, ++x){
            scanblock[i] = (QRgb *)
                img.scanLine((x < 0) ? 0 : (x > h-1) ? h-1 : x);
        }
        // Now we are about to start processing scanlines. First handle the
        // part where the pixel neighborhood extends off the left edge.
        for(x=0; x-edge < 0 ; ++x){
            r = g = b = 0.0;
            m = normalize_matrix;
            for(matrix_y = 0; matrix_y < matrix_size; ++matrix_y){
                s = scanblock[matrix_y];
                matrix_x = -edge;
                while(x+matrix_x < 0){
                    CONVOLVE_ACC(*m, *s);
                    ++matrix_x; ++m;
                }
                while(matrix_x <= edge){
                    CONVOLVE_ACC(*m, *s);
                    ++matrix_x; ++m; ++s;
                }
            }
            r = r < 0.0 ? 0.0 : r > 255.0 ? 255.0 : r+0.5;
            g = g < 0.0 ? 0.0 : g > 255.0 ? 255.0 : g+0.5;
            b = b < 0.0 ? 0.0 : b > 255.0 ? 255.0 : b+0.5;
            *dest++ = qRgba((unsigned char)r, (unsigned char)g,
                            (unsigned char)b, qAlpha(*src++));
        }
        // Okay, now process the middle part where the entire neighborhood
        // is on the image.
        for(; x+edge < w; ++x){
            m = normalize_matrix;
            r = g = b = 0.0;
            for(matrix_y = 0; matrix_y < matrix_size; ++matrix_y){
                s = scanblock[matrix_y] + (x-edge);
                for(matrix_x = -edge; matrix_x <= edge; ++matrix_x, ++m, ++s){
                    CONVOLVE_ACC(*m, *s);
                }
            }
            r = r < 0.0 ? 0.0 : r > 255.0 ? 255.0 : r+0.5;
            g = g < 0.0 ? 0.0 : g > 255.0 ? 255.0 : g+0.5;
            b = b < 0.0 ? 0.0 : b > 255.0 ? 255.0 : b+0.5;
            *dest++ = qRgba((unsigned char)r, (unsigned char)g,
                            (unsigned char)b, qAlpha(*src++));
        }
        // Finally process the right part where the neighborhood extends off
        // the right edge of the image
        for(; x < w; ++x){
            r = g = b = 0.0;
            m = normalize_matrix;
            for(matrix_y = 0; matrix_y < matrix_size; ++matrix_y){
                s = scanblock[matrix_y];
                s += x-edge;
                matrix_x = -edge;
                while(x+matrix_x < w){
                    CONVOLVE_ACC(*m, *s);
                    ++matrix_x, ++m, ++s;
                }
                --s;
                while(matrix_x <= edge){
                    CONVOLVE_ACC(*m, *s);
                    ++matrix_x, ++m;
                }
            }
            r = r < 0.0 ? 0.0 : r > 255.0 ? 255.0 : r+0.5;
            g = g < 0.0 ? 0.0 : g > 255.0 ? 255.0 : g+0.5;
            b = b < 0.0 ? 0.0 : b > 255.0 ? 255.0 : b+0.5;
            *dest++ = qRgba((unsigned char)r, (unsigned char)g,
                            (unsigned char)b, qAlpha(*src++));
        }
    }
    Py_END_ALLOW_THREADS;

    delete[] scanblock;
    delete[] normalize_matrix;
    return buffer;
}

int default_convolve_matrix_size(const float radius, const float sigma, const bool quality) {
    int i, matrix_size;
    float normalize, value;
    float sigma2 = sigma*sigma*2.0;
    float sigmaSQ2PI = M_SQ2PI*sigma;
    int max = quality ? 65535 : 255;

    if(sigma == 0.0) throw std::out_of_range("Zero sigma is invalid for convolution");

    if(radius > 0.0)
        return((int)(2.0*ceil(radius)+1.0));

    Py_BEGIN_ALLOW_THREADS;
    matrix_size = 5;
    do{
        normalize = 0.0;
        for(i=(-matrix_size/2); i <= (matrix_size/2); ++i)
            normalize += exp(-((float) i*i)/sigma2) / sigmaSQ2PI;
        i = matrix_size/2;
        value = exp(-((float) i*i)/sigma2) / sigmaSQ2PI / normalize;
        matrix_size += 2;
    } while((int)(max*value) > 0);

    matrix_size-=4;
    Py_END_ALLOW_THREADS;
    return(matrix_size);
}

// }}}

QImage gaussian_sharpen(const QImage &img, const float radius, const float sigma, const bool high_quality=true) {
    int matrix_size = default_convolve_matrix_size(radius, sigma, high_quality);
    int len = matrix_size*matrix_size;
    float alpha, *matrix = new float[len];
    float sigma2 = sigma*sigma*2.0;
    float sigmaPI2 = 2.0*M_PI*sigma*sigma;

    int half = matrix_size/2;
    int x, y, i=0, j=half;
    float normalize=0.0;
    for(y=(-half); y <= half; ++y, --j){
        for(x=(-half); x <= half; ++x, ++i){
            alpha = std::exp(-((float)x*x+y*y)/sigma2);
            matrix[i] = alpha/sigmaPI2;
            normalize += matrix[i];
        }
    }

    matrix[i/2]=(-2.0)*normalize;
    QImage result(convolve(img, matrix_size, matrix));
    delete[] matrix;
    return(result);
}
