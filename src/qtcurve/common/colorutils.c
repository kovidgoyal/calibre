/*
 This file is taken from kcolorspaces.cpp and kcolorutils.cpp from kdelibs
The code has been modified to work with QColor (Qt3 &Qt4) and GdkColor
*/

/* This file is part of the KDE project
 * Copyright (C) 2007 Matthew Woehlke <mw_triad@users.sourceforge.net>
 * Copyright (C) 2007 Olaf Schmidt <ojschmidt@kde.org>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public License
 * along with this library; see the file COPYING.LIB.  If not, write to
 * the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
 * Boston, MA 02110-1301, USA.
 */
#include "config.h"
#include "common.h"

#ifdef __cplusplus
#include <qglobal.h>
#endif

#if !(defined QT_VERSION && (QT_VERSION >= 0x040000) && !defined QTC_QT_ONLY)

#include <math.h>

#if defined _WIN32 && defined QT_VERSION && (QT_VERSION >= 0x040000)
#include <sys/stat.h>
#include <float.h>
#include <direct.h>

static int isnan(double x)
{
    return _isnan(x);
}
#endif

#ifdef __cplusplus
static inline int qtcLimit(double c)
{
    return c < 0.0 ? 0 : (c > 255.0  ? 255 : (int)c);
}
#else
static inline int qtcLimit(double c)
{
    return c < 0.0
               ? 0
               : c > 65535.0
                     ? 65535
                     : (int)c;
}
#endif

#ifdef __cplusplus
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
#define FLOAT_COLOR(VAL, COL) (VAL).COL##F()
#define TO_COLOR(R, G, B) QColor::fromRgbF(R, G, B)
#else
#define FLOAT_COLOR(VAL, COL) ((double)(((VAL).COL()*1.0)/255.0))
#define TO_COLOR(R, G, B) QColor(qtcLimit(R*255.0), qtcLimit(G*255.0), qtcLimit(B*255.0))
#endif
#else
#define inline
#define FLOAT_COLOR(VAL, COL) ((double)(((VAL).COL*1.0)/65535.0))
static GdkColor qtcGdkColor(double r, double g, double b)
{
    GdkColor col;

    col.red=qtcLimit(r*65535);
    col.green=qtcLimit(g*65535);
    col.blue=qtcLimit(b*65535);

    return col;
}

#define TO_COLOR(R, G, B) qtcGdkColor(R, G, B)
#endif

static inline double ColorUtils_normalize(double a)
{
    return (a < 1.0 ? (a > 0.0 ? a : 0.0) : 1.0);
}

static inline double ColorUtils_wrap(double a)
{
    static double d = 1.0;
    double r = fmod(a, d);
    return (r < 0.0 ? d + r : (r > 0.0 ? r : 0.0));
}

#define HCY_REC 709 // use 709 for now
#if   HCY_REC == 601
static const double yc[3] = { 0.299, 0.587, 0.114 };
#elif HCY_REC == 709
static const double yc[3] = {0.2126, 0.7152, 0.0722};
#else // use Qt values
static const double yc[3] = { 0.34375, 0.5, 0.15625 };
#endif

static inline double ColorUtils_HCY_gamma(double n)
{
    return pow(ColorUtils_normalize(n), 2.2);
}

static inline double ColorUtils_HCY_igamma(double n)
{
    return pow(ColorUtils_normalize(n), 1.0/2.2);
}

static inline double ColorUtils_HCY_lumag(double r, double g, double b)
{
    return r*yc[0] + g*yc[1] + b*yc[2];
}

typedef struct
{
    double h, c, y;
} ColorUtils_HCY;

// static ColorUtils_HCY ColorUtils_HCY_fromValues(double h_, double c_, double y_/*, double a_*/)
// {
//     h = h_;
//     c = c_;
//     y = y_;
// //    a = a_;
// }

static ColorUtils_HCY ColorUtils_HCY_fromColor(const color *color)
{
    ColorUtils_HCY hcy;
    double r = ColorUtils_HCY_gamma(FLOAT_COLOR(*color, red));
    double g = ColorUtils_HCY_gamma(FLOAT_COLOR(*color, green));
    double b = ColorUtils_HCY_gamma(FLOAT_COLOR(*color, blue));
//     a = color.alphaF();

    // luma component
    hcy.y = ColorUtils_HCY_lumag(r, g, b);

    // hue component
    double p = MAX(MAX(r, g), b);
    double n = MIN(MIN(r, g), b);
    double d = 6.0 * (p - n);
    if (n == p)
        hcy.h = 0.0;
    else if (r == p)
        hcy.h = ((g - b) / d);
    else if (g == p)
        hcy.h = ((b - r) / d) + (1.0 / 3.0);
    else
        hcy.h = ((r - g) / d) + (2.0 / 3.0);

    // chroma component
    if (0.0 == hcy.y || 1.0 == hcy.y)
        hcy.c = 0.0;
    else
        hcy.c = MAX( (hcy.y - n) / hcy.y, (p - hcy.y) / (1 - hcy.y) );
    return hcy;
}

static color ColorUtils_HCY_toColor(ColorUtils_HCY *hcy)
{
    // start with sane component values
    double _h = ColorUtils_wrap(hcy->h);
    double _c = ColorUtils_normalize(hcy->c);
    double _y = ColorUtils_normalize(hcy->y);

    // calculate some needed variables
    double _hs = _h * 6.0, th, tm;
    if (_hs < 1.0) {
        th = _hs;
        tm = yc[0] + yc[1] * th;
    }
    else if (_hs < 2.0) {
        th = 2.0 - _hs;
        tm = yc[1] + yc[0] * th;
    }
    else if (_hs < 3.0) {
        th = _hs - 2.0;
        tm = yc[1] + yc[2] * th;
    }
    else if (_hs < 4.0) {
        th = 4.0 - _hs;
        tm = yc[2] + yc[1] * th;
    }
    else if (_hs < 5.0) {
        th = _hs - 4.0;
        tm = yc[2] + yc[0] * th;
    }
    else {
        th = 6.0 - _hs;
        tm = yc[0] + yc[2] * th;
    }

    // calculate RGB channels in sorted order
    double tn, to, tp;
    if (tm >= _y) {
        tp = _y + _y * _c * (1.0 - tm) / tm;
        to = _y + _y * _c * (th - tm) / tm;
        tn = _y - (_y * _c);
    }
    else {
        tp = _y + (1.0 - _y) * _c;
        to = _y + (1.0 - _y) * _c * (th - tm) / (1.0 - tm);
        tn = _y - (1.0 - _y) * _c * tm / (1.0 - tm);
    }

    // return RGB channels in appropriate order
    if (_hs < 1.0)
        return TO_COLOR(ColorUtils_HCY_igamma(tp), ColorUtils_HCY_igamma(to), ColorUtils_HCY_igamma(tn));
    else if (_hs < 2.0)
        return TO_COLOR(ColorUtils_HCY_igamma(to), ColorUtils_HCY_igamma(tp), ColorUtils_HCY_igamma(tn));
    else if (_hs < 3.0)
        return TO_COLOR(ColorUtils_HCY_igamma(tn), ColorUtils_HCY_igamma(tp), ColorUtils_HCY_igamma(to));
    else if (_hs < 4.0)
        return TO_COLOR(ColorUtils_HCY_igamma(tn), ColorUtils_HCY_igamma(to), ColorUtils_HCY_igamma(tp));
    else if (_hs < 5.0)
        return TO_COLOR(ColorUtils_HCY_igamma(to), ColorUtils_HCY_igamma(tn), ColorUtils_HCY_igamma(tp));
    else
        return TO_COLOR(ColorUtils_HCY_igamma(tp), ColorUtils_HCY_igamma(tn), ColorUtils_HCY_igamma(to));
}

// #ifndef __cplusplus
static inline double ColorUtils_HCY_luma(const color *color)
{
    return ColorUtils_HCY_lumag(ColorUtils_HCY_gamma(FLOAT_COLOR(*color, red)),
                                ColorUtils_HCY_gamma(FLOAT_COLOR(*color, green)),
                                ColorUtils_HCY_gamma(FLOAT_COLOR(*color, blue)));
}

static inline double ColorUtils_mixQreal(double a, double b, double bias)
{
    return a + (b - a) * bias;
}

double ColorUtils_luma(const color *color)
{
    return ColorUtils_HCY_luma(color);
}

static double ColorUtils_contrastRatio(const color *c1, const color *c2)
{
    double y1 = ColorUtils_luma(c1), y2 = ColorUtils_luma(c2);
    if (y1 > y2)
        return (y1 + 0.05) / (y2 + 0.05);
    else
        return (y2 + 0.05) / (y1 + 0.05);
}

color ColorUtils_lighten(const color *color, double ky, double kc)
{
    ColorUtils_HCY c=ColorUtils_HCY_fromColor(color);

    c.y = 1.0 - ColorUtils_normalize((1.0 - c.y) * (1.0 - ky));
    c.c = 1.0 - ColorUtils_normalize((1.0 - c.c) * kc);
    return ColorUtils_HCY_toColor(&c);
}

color ColorUtils_darken(const color *color, double ky, double kc)
{
    ColorUtils_HCY c=ColorUtils_HCY_fromColor(color);
    c.y = ColorUtils_normalize(c.y * (1.0 - ky));
    c.c = ColorUtils_normalize(c.c * kc);
    return ColorUtils_HCY_toColor(&c);
}

color ColorUtils_shade(const color *color, double ky, double kc)
{
    ColorUtils_HCY c=ColorUtils_HCY_fromColor(color);
    c.y = ColorUtils_normalize(c.y + ky);
    c.c = ColorUtils_normalize(c.c + kc);
    return ColorUtils_HCY_toColor(&c);
}

color ColorUtils_mix(const color *c1, const color *c2, double bias);

static color ColorUtils_tintHelper(const color *base, const color *col, double amount)
{
    color          mixed=ColorUtils_mix(base, col, pow(amount, 0.3));
    ColorUtils_HCY c=ColorUtils_HCY_fromColor(&mixed);
    c.y = ColorUtils_mixQreal(ColorUtils_luma(base), c.y, amount);

    return ColorUtils_HCY_toColor(&c);
}

color ColorUtils_tint(const color *base, const color *col, double amount)
{
    if (amount <= 0.0) return *base;
    if (amount >= 1.0) return *col;
    if (isnan(amount)) return *base;

    double ri = ColorUtils_contrastRatio(base, col);
    double rg = 1.0 + ((ri + 1.0) * amount * amount * amount);
    double u = 1.0, l = 0.0;
    color result;
    int i;
    for (i = 12 ; i ; --i) {
        double a = 0.5 * (l+u);
        result = ColorUtils_tintHelper(base, col, a);
        double ra = ColorUtils_contrastRatio(base, &result);
        if (ra > rg)
            u = a;
        else
            l = a;
    }
    return result;
}

color ColorUtils_mix(const color *c1, const color *c2, double bias)
{
    if (bias <= 0.0) return *c1;
    if (bias >= 1.0) return *c2;
    if (isnan(bias)) return *c1;

    {
    double r = ColorUtils_mixQreal(FLOAT_COLOR(*c1, red),   FLOAT_COLOR(*c2, red),    bias);
    double g = ColorUtils_mixQreal(FLOAT_COLOR(*c1, green), FLOAT_COLOR(*c2, green), bias);
    double b = ColorUtils_mixQreal(FLOAT_COLOR(*c1, blue),  FLOAT_COLOR(*c2, blue),  bias);
    /*double a = ColorUtils_mixQreal(FLOAT_COLOR(*c1, alpha),   FLOAT_COLOR(*c2, alpha),   bias);*/

    return TO_COLOR(r, g, b);
    }
}

// #endif
/* Added!!! */
// static color ColorUtils_shade_qtc(const color *color, double k)
// {
//     ColorUtils_HCY c=ColorUtils_HCY_fromColor(color);
//     c.y = ColorUtils_normalize(c.y * (k>1.0 ? (k*1.1) : (k<1.0 ? (k*0.9) : k)));
//     return ColorUtils_HCY_toColor(&c);
// }

#endif // !(defined QT_VERSION && (QT_VERSION >= 0x040000) && !defined QTC_QT_ONLY)
