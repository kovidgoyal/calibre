#include <string.h>
#include <stdarg.h>
#include <math.h>
#include "common.h"
#include "colorutils.h"

#ifdef __cplusplus
#include <qglobal.h>
#else
#include <stdlib.h>
#endif

/* Taken from rgb->hsl routines taken from KColor
    Copyright 2007 Matthew Woehlke <mw_triad@users.sourceforge.net>
*/
static inline double normalize(double a)
{
    return (a < 0.0 ? 0.0 : a > 1.0 ? 1.0 : a);
}

static inline double mix(double a, double b, double k)
{
    return a + ( ( b - a ) * k );
}

static inline double wrap(double a, double d)
{
    register double r = fmod( a, d );
    return ( r < 0.0 ? d + r : ( r > 0.0 ? r : 0.0 ) );
}

static inline double h2c(double h, double m1, double m2)
{
    h = wrap( h, 6.0 );

    if ( h < 1.0 )
        return mix( m1, m2, h );
    if ( h < 3.0 )
        return m2;
    if ( h < 4.0 )
        return mix( m1, m2, 4.0 - h );
    return m1;
}

static inline void rgbToHsl(double r, double g, double b, double *h, double *s, double *l)
{
    double min=MIN(MIN(r, g), b),
           max=MAX(MAX(r, g), b);

    *l = 0.5 * (max + min);
    *s = 0.0;
    *h = 0.0;

    if (max != min)
    {
        double delta = max - min;

        if ( *l <= 0.5 )
            *s = delta / ( max + min );
        else
            *s = delta / ( 2.0 - max - min );

        if ( r == max )
            *h = ( g - b ) / delta;
        else if ( g == max )
            *h = 2.0 + ( b - r ) / delta;
        else if ( b == max )
            *h = 4.0 + ( r - g ) / delta;

        *h /= 6.0;
        if ( *h < 0.0 )
            (*h) += 1.0;
    }
}

static inline void hslToRgb(double h, double s, double l, double *r, double *g, double *b)
{
    double m1, m2;

    // TODO h2rgb( h, r, g, b );
    h *= 6.0;

    if ( l <= 0.5 )
        m2 = l * ( 1.0 + s );
    else
        m2 = l + s * ( 1.0 - l );
    m1 = 2.0 * l - m2;

    *r = h2c( h + 2.0, m1, m2 );
    *g = h2c( h,       m1, m2 );
    *b = h2c( h - 2.0, m1, m2 );
}

void qtcRgbToHsv(double r, double g, double b, double *h, double *s, double *v)
{
    double min=MIN(MIN(r, g), b),
           max=MAX(MAX(r, g), b),
           delta=max - min;

    *v=max;
    if(max != 0)
        *s=delta / max;
    else
        *s=0;

    if (*s==0.0)
        *h = 0.0;
    else
    {
        if(r == max)
            *h=(g - b) / delta;         /* between yellow & magenta */
        else if(g == max)
            *h=2 + (b - r) / delta;     /* between cyan & yellow */
        else if(b == max)
            *h=4 + (r - g) / delta;     /* between magenta & cyan */
        *h *= 60;                       /* degrees */
        if(*h < 0)
            *h += 360;
    }
}

void qtcHsvToRgb(double *r, double *g, double *b, double h, double s, double v)
{
    if(0==s)
        *r=*g=*b=v;
    else
    {
        int    i;
        double f,
               p;

        h /= 60;                      /* sector 0 to 5 */
        i=(int)floor(h);
        f=h - i;                      /* factorial part of h */
        p=v * (1 - s);
        switch(i)
        {
            case 0:
                *r=v;
                *g=v * (1 - s * (1 - f));
                *b=p;
                break;
            case 1:
                *r=v * (1 - s * f);
                *g=v;
                *b=p;
                break;
            case 2:
                *r=p;
                *g=v;
                *b=v * (1 - s * (1 - f));
                break;
            case 3:
                *r=p;
                *g=v * (1 - s * f);
                *b=v;
                break;
            case 4:
                *r=v * (1 - s * (1 - f));
                *g=p;
                *b=v;
                break;
            /* case 5: */
            default:
                *r=v;
                *g=p;
                *b=v * (1 - s * f);
                break;
        }
    }
}

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
void qtcShade(const Options *opts, const color &ca, color *cb, double k)
#else
void qtcShade(const Options *opts, const color *ca, color *cb, double k)
#endif
{
    if(qtcEqual(k, 1.0))
    {
#ifdef __cplusplus
        *cb=ca;
#else
        cb->red = ca->red;
        cb->green = ca->green;
        cb->blue = ca->blue;
#endif
    }
    else
        switch(opts->shading)
        {
            case SHADING_SIMPLE:
            {
    #ifdef __cplusplus
                int v=(int)(255.0*(k-1.0));

                cb->setRgb(qtcLimit(ca.red()+v), qtcLimit(ca.green()+v), qtcLimit(ca.blue()+v));
    #else
                double v=65535.0*(k-1.0);

                cb->red = qtcLimit(ca->red+v);
                cb->green = qtcLimit(ca->green+v);
                cb->blue = qtcLimit(ca->blue+v);
    #endif
                break;
            }
            case SHADING_HSL:
            {
    #ifdef __cplusplus
                double r(ca.red()/255.0),
                       g(ca.green()/255.0),
                       b(ca.blue()/255.0);
    #else
                double r=ca->red/65535.0,
                       g=ca->green/65535.0,
                       b=ca->blue/65535.0;
    #endif
                double h, s, l;

                rgbToHsl(r, g, b, &h, &s, &l);
                l=normalize(l*k);
                s=normalize(s*k);
                hslToRgb(h, s, l, &r, &g, &b);
    #ifdef __cplusplus
                cb->setRgb(qtcLimit(r*255.0), qtcLimit(g*255.0), qtcLimit(b*255.0));
    #else
                cb->red=qtcLimit(r*65535.0);
                cb->green=qtcLimit(g*65535.0);
                cb->blue=qtcLimit(b*65535.0);
    #endif
                break;
            }
            case SHADING_HSV:
            {
    #ifdef __cplusplus
                double r(ca.red()/255.0),
                       g(ca.green()/255.0),
                       b(ca.blue()/255.0);
    #else
                double r=ca->red/65535.0,
                       g=ca->green/65535.0,
                       b=ca->blue/65535.0;
    #endif
                double h, s, v;

                qtcRgbToHsv(r, g, b, &h, &s, &v);

                v*=k;
                if (v > 1.0)
                {
                    s -= v - 1.0;
                    if (s < 0)
                        s = 0;
                    v = 1.0;
                }
                qtcHsvToRgb(&r, &g, &b, h, s, v);
    #ifdef __cplusplus
                cb->setRgb(qtcLimit(r*255.0), qtcLimit(g*255.0), qtcLimit(b*255.0));
    #else
                cb->red=qtcLimit(r*65535.0);
                cb->green=qtcLimit(g*65535.0);
                cb->blue=qtcLimit(b*65535.0);
    #endif
                break;
            }
            case SHADING_HCY:
            {
    #define HCY_FACTOR 0.15
    #if defined QT_VERSION && (QT_VERSION >= 0x040000) && !defined QTC_QT_ONLY
                if(k>1.0)
                    *cb=KColorUtils::lighten(ca, (k*(1+HCY_FACTOR))-1.0, 1.0);
                else
                    *cb=KColorUtils::darken(ca, 1.0-(k*(1-HCY_FACTOR)), 1.0);
    #elif defined __cplusplus
                if(k>1.0)
                    *cb=ColorUtils_lighten(&ca, (k*(1+HCY_FACTOR))-1.0, 1.0);
                else
                    *cb=ColorUtils_darken(&ca, 1.0-(k*(1-HCY_FACTOR)), 1.0);
    #else
                if(k>1.0)
                    *cb=ColorUtils_lighten(ca, (k*(1+HCY_FACTOR))-1.0, 1.0);
                else
                    *cb=ColorUtils_darken(ca, 1.0-(k*(1-HCY_FACTOR)), 1.0);
    #endif
            }
        }
#if defined __cplusplus && defined QT_VERSION && (QT_VERSION >= 0x040000)
    cb->setAlpha(ca.alpha());
#endif
#ifndef __cplusplus
    cb->pixel = ca->pixel;
#endif
}

static unsigned char checkBounds(int num)
{
    return num < 0   ? 0   :
           num > 255 ? 255 :
                       num;
}

void qtcAdjustPix(unsigned char *data, int numChannels, int w, int h, int stride, int ro, int go, int bo, double shade)
{
    int width=w*numChannels,
        offset=0,
        row,
        r=(int)((ro*shade)+0.5),
        g=(int)((go*shade)+0.5),
        b=(int)((bo*shade)+0.5);

    for(row=0; row<h; ++row)
    {
        int column;

        for(column=0; column<width; column+=numChannels)
        {
            unsigned char source=data[offset+column+1];

#if defined  __cplusplus
#if Q_BYTE_ORDER == Q_BIG_ENDIAN
            /* ARGB */
            data[offset+column+1] = checkBounds(r-source);
            data[offset+column+2] = checkBounds(g-source);
            data[offset+column+3] = checkBounds(b-source);
#else
            /* BGRA */
            data[offset+column] = checkBounds(b-source);
            data[offset+column+1] = checkBounds(g-source);
            data[offset+column+2] = checkBounds(r-source);
#endif
#else
            /* GdkPixbuf is RGBA */
            data[offset+column] = checkBounds(r-source);
            data[offset+column+1] = checkBounds(g-source);
            data[offset+column+2] = checkBounds(b-source);
#endif

        }
        offset+=stride;
    }
}

void qtcSetupGradient(Gradient *grad, EGradientBorder border, int numStops, ...)
{
    va_list  ap;
    int      i;

    grad->border=border;
#ifndef __cplusplus
    grad->numStops=numStops;
    grad->stops=malloc(sizeof(GradientStop) * numStops);
#endif
    va_start(ap, numStops);
    for(i=0; i<numStops; ++i)
    {
        double pos=va_arg(ap, double),
               val=va_arg(ap, double);
#ifdef __cplusplus
        grad->stops.insert(GradientStop(pos, val));
#else
        grad->stops[i].pos=pos;
        grad->stops[i].val=val;
        grad->stops[i].alpha=1.0;
#endif
    }
    va_end(ap);
}

const Gradient * qtcGetGradient(EAppearance app, const Options *opts)
{
    if(IS_CUSTOM(app))
    {
#ifdef __cplusplus
        GradientCont::const_iterator grad(opts->customGradient.find(app));

        if(grad!=opts->customGradient.end())
            return &((*grad).second);
#else
        Gradient *grad=opts->customGradient[app-APPEARANCE_CUSTOM1];

        if(grad)
            return grad;
#endif
        app=APPEARANCE_RAISED;
    }

    {
    static Gradient stdGradients[NUM_STD_APP];
    static bool     init=false;

    if(!init)
    {
        qtcSetupGradient(&stdGradients[APPEARANCE_FLAT-APPEARANCE_FLAT], GB_3D,2,0.0,1.0,1.0,1.0);
        qtcSetupGradient(&stdGradients[APPEARANCE_RAISED-APPEARANCE_FLAT], GB_3D_FULL,2,0.0,1.0,1.0,1.0);
        qtcSetupGradient(&stdGradients[APPEARANCE_DULL_GLASS-APPEARANCE_FLAT], GB_LIGHT,4,0.0,1.05,0.499,0.984,0.5,0.928,1.0,1.0);
        qtcSetupGradient(&stdGradients[APPEARANCE_SHINY_GLASS-APPEARANCE_FLAT], GB_LIGHT,4,0.0,1.2,0.499,0.984,0.5,0.9,1.0,1.06);
        qtcSetupGradient(&stdGradients[APPEARANCE_AGUA-APPEARANCE_FLAT], GB_SHINE, 2,0.0,0.6,1.0,1.1);
        qtcSetupGradient(&stdGradients[APPEARANCE_SOFT_GRADIENT-APPEARANCE_FLAT], GB_3D,2,0.0,1.04,1.0,0.98);
        qtcSetupGradient(&stdGradients[APPEARANCE_GRADIENT-APPEARANCE_FLAT], GB_3D,2,0.0,1.1,1.0,0.94);
        qtcSetupGradient(&stdGradients[APPEARANCE_HARSH_GRADIENT-APPEARANCE_FLAT], GB_3D,2,0.0,1.3,1.0,0.925);
        qtcSetupGradient(&stdGradients[APPEARANCE_INVERTED-APPEARANCE_FLAT], GB_3D,2,0.0,0.93,1.0,1.04);
        qtcSetupGradient(&stdGradients[APPEARANCE_DARK_INVERTED-APPEARANCE_FLAT], GB_NONE,3,0.0,0.8,0.7,0.95,1.0,1.0);
        qtcSetupGradient(&stdGradients[APPEARANCE_SPLIT_GRADIENT-APPEARANCE_FLAT], GB_3D,4,0.0,1.06,0.499,1.004,0.5,0.986,1.0,0.92);
        qtcSetupGradient(&stdGradients[APPEARANCE_BEVELLED-APPEARANCE_FLAT], GB_3D,4,0.0,1.05,0.1,1.02,0.9,0.985,1.0,0.94);
        qtcSetupGradient(&stdGradients[APPEARANCE_LV_BEVELLED-APPEARANCE_FLAT], GB_3D,3,0.0,1.00,0.85,1.0,1.0,0.90);
        qtcSetupGradient(&stdGradients[APPEARANCE_AGUA_MOD-APPEARANCE_FLAT], GB_NONE,3,0.0,1.5,0.49,0.85,1.0,1.3);
        qtcSetupGradient(&stdGradients[APPEARANCE_LV_AGUA-APPEARANCE_FLAT], GB_NONE,4,0.0,0.98,0.35,0.95,0.4,0.93,1.0,1.15);
        init=true;
    }

    return &stdGradients[app-APPEARANCE_FLAT];
    }

    return 0L; /* Will never happen! */
}

#ifdef __cplusplus
EAppearance qtcWidgetApp(EWidget w, const Options *opts, bool active)
#else
EAppearance qtcWidgetApp(EWidget w, const Options *opts)
#endif
{
    switch(w)
    {
        case WIDGET_SB_BGND:
            return opts->sbarBgndAppearance;
        case WIDGET_LISTVIEW_HEADER:
            return opts->lvAppearance;
        case WIDGET_SB_BUTTON:
        case WIDGET_SLIDER:
        case WIDGET_SB_SLIDER:
            return opts->sliderAppearance;
        case WIDGET_FILLED_SLIDER_TROUGH:
            return opts->sliderFill;
        case WIDGET_TAB_TOP:
        case WIDGET_TAB_BOT:
            return opts->tabAppearance;
        case WIDGET_MENU_ITEM:
            return opts->menuitemAppearance;
        case WIDGET_PROGRESSBAR:
#ifndef __cplusplus
        case WIDGET_ENTRY_PROGRESSBAR:
#endif
            return opts->progressAppearance;
        case WIDGET_PBAR_TROUGH:
            return opts->progressGrooveAppearance;
        case WIDGET_SELECTION:
            return opts->selectionAppearance;
#ifdef __cplusplus
        case WIDGET_DOCK_WIDGET_TITLE:
            return opts->dwtAppearance;
        case WIDGET_MDI_WINDOW:
        case WIDGET_MDI_WINDOW_TITLE:
            return active ? opts->titlebarAppearance : opts->inactiveTitlebarAppearance;
        case WIDGET_MDI_WINDOW_BUTTON:
            return opts->titlebarButtonAppearance;
        case WIDGET_DIAL:
            return IS_FLAT(opts->appearance) ? APPEARANCE_RAISED : APPEARANCE_SOFT_GRADIENT;
#endif
        case WIDGET_TROUGH:
        case WIDGET_SLIDER_TROUGH:
            return opts->grooveAppearance;
#ifndef __cplusplus
        case WIDGET_SPIN_UP:
        case WIDGET_SPIN_DOWN:
#endif
        case WIDGET_SPIN:
            return MODIFY_AGUA(opts->appearance);
        case WIDGET_TOOLBAR_BUTTON:
            return APPEARANCE_NONE==opts->tbarBtnAppearance ? opts->appearance : opts->tbarBtnAppearance;
        default:
            break;
    }

    return opts->appearance;
};

#if !defined __cplusplus || (defined QT_VERSION && (QT_VERSION >= 0x040000))

#define CAN_EXTRA_ROUND(MOD) \
            (IS_EXTRA_ROUND_WIDGET(widget) && \
            (IS_SLIDER(widget) || WIDGET_TROUGH==widget || \
            ( ( (w>(MIN_ROUND_EXTRA_SIZE(widget)+MOD)) || (WIDGET_NO_ETCH_BTN==widget || WIDGET_MENU_BUTTON==widget) ) &&\
                                             (h>(MIN_ROUND_EXTRA_SIZE(widget)+MOD)))))
#define CAN_FULL_ROUND(MOD) (w>(MIN_ROUND_FULL_SIZE+MOD) && h>(MIN_ROUND_FULL_SIZE+MOD))

// **NOTE** MUST KEEP IN SYNC WITH getRadius/RADIUS_ETCH !!!
ERound qtcGetWidgetRound(const Options *opts, int w, int h, EWidget widget)
{
    ERound r=opts->round;

    if( ((WIDGET_PBAR_TROUGH==widget || WIDGET_PROGRESSBAR==widget) && (opts->square&SQUARE_PROGRESS)) ||
        (WIDGET_ENTRY==widget && (opts->square&SQUARE_ENTRY)) ||
        (WIDGET_SCROLLVIEW==widget && (opts->square&SQUARE_SCROLLVIEW)) )
        return ROUND_NONE;

    if((WIDGET_CHECKBOX==widget || WIDGET_FOCUS==widget) && ROUND_NONE!=r)
        r=ROUND_SLIGHT;

#if defined __cplusplus && (defined QT_VERSION && (QT_VERSION >= 0x040000))
    if((WIDGET_MDI_WINDOW_BUTTON==widget && (opts->titlebarButtons&TITLEBAR_BUTTON_ROUND)) ||
       WIDGET_RADIO_BUTTON==widget || WIDGET_DIAL==widget)
       return ROUND_MAX;
#endif
#ifndef __cplusplus
    if(WIDGET_RADIO_BUTTON==widget)
       return ROUND_MAX;
#endif

#if !defined __cplusplus || (defined QT_VERSION && (QT_VERSION >= 0x040000))
    if(WIDGET_SLIDER==widget &&
       (SLIDER_ROUND==opts->sliderStyle || SLIDER_ROUND_ROTATED==opts->sliderStyle || SLIDER_CIRCULAR==opts->sliderStyle))
        return ROUND_MAX;
#endif

    switch(r)
    {
        case ROUND_MAX:
            if(IS_SLIDER(widget) || WIDGET_TROUGH==widget ||
               (w>(MIN_ROUND_MAX_WIDTH+2) && h>(MIN_ROUND_MAX_HEIGHT+2) && IS_MAX_ROUND_WIDGET(widget)))
                return ROUND_MAX;
        case ROUND_EXTRA:
            if(CAN_EXTRA_ROUND(2))
                return ROUND_EXTRA;
        case ROUND_FULL:
            if(CAN_FULL_ROUND(2))
                return ROUND_FULL;
        case ROUND_SLIGHT:
            return ROUND_SLIGHT;
        case ROUND_NONE:
            return ROUND_NONE;
    }
    
    return ROUND_NONE;
}

double qtcGetRadius(const Options *opts, int w, int h, EWidget widget, ERadius rad)
{
    ERound r=opts->round;

    if((WIDGET_CHECKBOX==widget || WIDGET_FOCUS==widget) && ROUND_NONE!=r)
        r=ROUND_SLIGHT;

    if( ((WIDGET_PBAR_TROUGH==widget || WIDGET_PROGRESSBAR==widget) && (opts->square&SQUARE_PROGRESS)) ||
        (WIDGET_ENTRY==widget && (opts->square&SQUARE_ENTRY)) ||
        (WIDGET_SCROLLVIEW==widget && (opts->square&SQUARE_SCROLLVIEW)) )
        return 0.0;

#if defined __cplusplus && (defined QT_VERSION && (QT_VERSION >= 0x040000))
    if((WIDGET_MDI_WINDOW_BUTTON==widget && (opts->titlebarButtons&TITLEBAR_BUTTON_ROUND)) ||
       WIDGET_RADIO_BUTTON==widget || WIDGET_DIAL==widget) 
        return (w>h ? h : w)/2.0;
#endif
#ifndef __cplusplus
    if(WIDGET_RADIO_BUTTON==widget)
        return (w>h ? h : w)/2.0;
#endif

#if !defined __cplusplus || (defined QT_VERSION && (QT_VERSION >= 0x040000))
    if(WIDGET_SLIDER==widget &&
       (SLIDER_ROUND==opts->sliderStyle || SLIDER_ROUND_ROTATED==opts->sliderStyle || SLIDER_CIRCULAR==opts->sliderStyle))
        return (w>h ? h : w)/2.0;
#endif

    if(RADIUS_EXTERNAL==rad && !opts->fillProgress && (WIDGET_PROGRESSBAR==widget
#ifndef __cplusplus
                                                        || WIDGET_ENTRY_PROGRESSBAR==widget
#endif
      ))
        rad=RADIUS_INTERNAL;

    switch(rad)
    {
        case RADIUS_SELECTION:
            switch(r)
            {
                case ROUND_MAX:
                case ROUND_EXTRA:
                    if(/* (WIDGET_RUBBER_BAND==widget && w>14 && h>14) || */(w>48 && h>48))
                        return 6.0;
                case ROUND_FULL:
//                     if( /*(WIDGET_RUBBER_BAND==widget && w>11 && h>11) || */(w>48 && h>48))
//                         return 3.0;
                    if(w>MIN_ROUND_FULL_SIZE && h>MIN_ROUND_FULL_SIZE)
                        return 3.0;
                case ROUND_SLIGHT:
                    return 2.0;
                case ROUND_NONE:
                    return 0;
            }
        case RADIUS_INTERNAL:
            switch(r)
            {
                case ROUND_MAX:
                    if(IS_SLIDER(widget) || WIDGET_TROUGH==widget)
                    {
                        double r=((w>h ? h : w)-(WIDGET_SLIDER==widget ? 1 : 0))/2.0;
                        return r>MAX_RADIUS_INTERNAL ? MAX_RADIUS_INTERNAL : r;
                    }
                    if(w>(MIN_ROUND_MAX_WIDTH-2) && h>(MIN_ROUND_MAX_HEIGHT-2) && IS_MAX_ROUND_WIDGET(widget))
                    {
                        double r=((w>h ? h : w)-2.0)/2.0;
                        return r>9.5 ? 9.5 : r;
                    }
                case ROUND_EXTRA:
                    if(CAN_EXTRA_ROUND(-2))
                        return EXTRA_INNER_RADIUS;
                case ROUND_FULL:
                    if(CAN_FULL_ROUND(-2))
                        return FULL_INNER_RADIUS;
                case ROUND_SLIGHT:
                    return SLIGHT_INNER_RADIUS;
                case ROUND_NONE:
                    return 0;
            }
        case RADIUS_EXTERNAL:
            switch(r)
            {
                case ROUND_MAX:
                    if(IS_SLIDER(widget) || WIDGET_TROUGH==widget)
                    {
                        double r=((w>h ? h : w)-(WIDGET_SLIDER==widget ? 1 : 0))/2.0;
                        return r>MAX_RADIUS_EXTERNAL ? MAX_RADIUS_EXTERNAL : r;
                    }
                    if(w>MIN_ROUND_MAX_WIDTH && h>MIN_ROUND_MAX_HEIGHT && IS_MAX_ROUND_WIDGET(widget))
                    {
                        double r=((w>h ? h : w)-2.0)/2.0;
                        return r>10.5 ? 10.5 : r;
                    }
                case ROUND_EXTRA:
                    if(CAN_EXTRA_ROUND(0))
                        return EXTRA_OUTER_RADIUS;
                case ROUND_FULL:
                    if(CAN_FULL_ROUND(0))
                        return FULL_OUTER_RADIUS;
                case ROUND_SLIGHT:
                    return SLIGHT_OUTER_RADIUS;
                case ROUND_NONE:
                    return 0;
            }
        case RADIUS_ETCH:
            // **NOTE** MUST KEEP IN SYNC WITH getWidgetRound !!!
            switch(r)
            {
                case ROUND_MAX:
                    if(IS_SLIDER(widget) || WIDGET_TROUGH==widget)
                    {
                        double r=((w>h ? h : w)-(WIDGET_SLIDER==widget ? 1 : 0))/2.0;
                        return r>MAX_RADIUS_EXTERNAL ? MAX_RADIUS_EXTERNAL : r;
                    }
                    if(w>(MIN_ROUND_MAX_WIDTH+2) && h>(MIN_ROUND_MAX_HEIGHT+2) && IS_MAX_ROUND_WIDGET(widget))
                    {
                        double r=((w>h ? h : w)-2.0)/2.0;
                        return r>11.5 ? 11.5 : r;
                    }
                case ROUND_EXTRA:
                    if(CAN_FULL_ROUND(2))
                        return EXTRA_ETCH_RADIUS;
                case ROUND_FULL:
                    if(w>(MIN_ROUND_FULL_SIZE+2) && h>(MIN_ROUND_FULL_SIZE+2))
                        return FULL_ETCH_RADIUS;
                case ROUND_SLIGHT:
                    return SLIGHT_ETCH_RADIUS;
                case ROUND_NONE:
                    return 0;
            }
    }

    return 0;
}

double qtcRingAlpha[3]={0.125, 0.125, 0.5};

void qtcCalcRingAlphas(const color *bgnd)
{
#ifdef __cplusplus
    double r=bgnd->red()/255.0,
           g=bgnd->green()/255.0,
           b=bgnd->blue()/255.0,
#else
    double r=bgnd->red/65535.0,
           g=bgnd->green/65535.0,
           b=bgnd->blue/65535.0,
#endif
           h=0,
           s=0,
           v=0;
    qtcRgbToHsv(r, g, b, &h, &s, &v);
    qtcRingAlpha[0]=v*0.26;
    qtcRingAlpha[1]=v*0.14;
    qtcRingAlpha[2]=v*0.55;
}

double qtcShineAlpha(const color *bgnd)
{
#ifdef __cplusplus
    double r=bgnd->red()/255.0,
           g=bgnd->green()/255.0,
           b=bgnd->blue()/255.0,
#else
    double r=bgnd->red/65535.0,
           g=bgnd->green/65535.0,
           b=bgnd->blue/65535.0,
#endif
           h=0,
           s=0,
           v=0;
    qtcRgbToHsv(r, g, b, &h, &s, &v);
    return v*0.8;
}

#endif // !defined __cplusplus || (defined QT_VERSION && (QT_VERSION >= 0x040000))
