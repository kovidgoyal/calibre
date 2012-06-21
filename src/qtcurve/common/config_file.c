 /*
  QtCurve (C) Craig Drummond, 2003 - 2010 craig.p.drummond@gmail.com

  ----

  This program is free software; you can redistribute it and/or
  modify it under the terms of the GNU General Public
  License version 2 as published by the Free Software Foundation.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
  General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program; see the file COPYING.  If not, write to
  the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
  Boston, MA 02110-1301, USA.
 */

#include "common.h"
#include "config_file.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/types.h>

#ifdef __cplusplus
#include <qglobal.h>
#endif

#ifndef _WIN32
#include <unistd.h>
#include <pwd.h>
#endif

#if defined _WIN32 && defined QT_VERSION && (QT_VERSION >= 0x040000)
#include <sys/stat.h>
#include <float.h>
#include <direct.h>

static int lstat(const char* fileName, struct stat* s)
{
    return stat(fileName, s);
}
#endif

#define CONFIG_FILE               "stylerc"
#define OLD_CONFIG_FILE           "qtcurvestylerc"
#define VERSION_KEY               "version"

#ifdef __cplusplus

#if QT_VERSION >= 0x040000
#include <QMap>
#include <QFile>
#include <QTextStream>
#define TO_LATIN1(A) A.toLatin1().constData()
#else
#define TO_LATIN1(A) A.latin1()

#include <qmap.h>
#include <qfile.h>
#include <qtextstream.h>
#endif

#endif // __cplusplus

const char *qtcConfDir();

#ifdef __cplusplus
static QString determineFileName(const QString &file)
{
    if(file.startsWith("/"))
        return file;
    return qtcConfDir()+file;
}

#else
static const char * determineFileName(const char *file)
{
    if('/'==file[0])
        return file;

    static char *filename=NULL;

    filename=realloc(filename, strlen(qtcConfDir())+strlen(file)+1);
    sprintf(filename, "%s%s", qtcConfDir(), file);
    return filename;
}
#endif

static int c2h(char ch)
{
    return (ch>='0' && ch<='9') ? ch-'0' :
           (ch>='a' && ch<='f') ? 10+(ch-'a') :
           (ch>='A' && ch<='F') ? 10+(ch-'A') :
           0;
}

#define ATOH(str) ((c2h(*str)<<4)+c2h(*(str+1)))

void qtcSetRgb(color *col, const char *str)
{
    if(str && strlen(str)>6)
    {
        int offset='#'==str[0] ? 1 : 0;
#ifdef __cplusplus
        col->setRgb(ATOH(&str[offset]), ATOH(&str[offset+2]), ATOH(&str[offset+4]));
#else
        col->red=ATOH(&str[offset])<<8;
        col->green=ATOH(&str[offset+2])<<8;
        col->blue=ATOH(&str[offset+4])<<8;
        col->pixel=0;
#endif
    }
    else
#ifdef __cplusplus
        col->setRgb(0, 0, 0);
#else
        col->red=col->green=col->blue=col->pixel=0;
#endif
}

#ifdef __cplusplus
static bool loadImage(const QString &file, QtCPixmap *pixmap)
#else
static bool loadImage(const char *file, QtCPixmap *pixmap)
#endif
{
#ifdef __cplusplus
    // Need to store filename for config dialog!
    QString f(determineFileName(file));
    pixmap->file=f;
    return pixmap->img.load(f);
#else // __cplusplus
    pixmap->img=gdk_pixbuf_new_from_file(determineFileName(file), NULL);
    return NULL!=pixmap->img;
#endif // __cplusplus
}

static EDefBtnIndicator toInd(const char *str, EDefBtnIndicator def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "fontcolor", 9) || 0==memcmp(str, "border", 6))
            return IND_FONT_COLOR;
        if(0==memcmp(str, "none", 4))
            return IND_NONE;
        if(0==memcmp(str, "corner", 6))
            return IND_CORNER;
        if(0==memcmp(str, "colored", 7))
            return IND_COLORED;
        if(0==memcmp(str, "tint", 4))
            return IND_TINT;
        if(0==memcmp(str, "glow", 4))
            return IND_GLOW;
        if(0==memcmp(str, "darken", 6))
            return IND_DARKEN;
        if(0==memcmp(str, "origselected", 12))
            return IND_SELECTED;
    }

    return def;
}

static ELine toLine(const char *str, ELine def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "dashes", 6))
            return LINE_DASHES;
        if(0==memcmp(str, "none", 4))
            return LINE_NONE;
        if(0==memcmp(str, "sunken", 6))
            return LINE_SUNKEN;
        if(0==memcmp(str, "dots", 4))
            return LINE_DOTS;
        if(0==memcmp(str, "flat", 4))
            return LINE_FLAT;
        if(0==memcmp(str, "1dot", 5))
            return LINE_1DOT;
    }
    return def;
}

static ETBarBorder toTBarBorder(const char *str, ETBarBorder def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "dark", 4))
            return 0==memcmp(&str[4], "-all", 4) ? TB_DARK_ALL : TB_DARK;
        if(0==memcmp(str, "none", 4))
            return TB_NONE;
        if(0==memcmp(str, "light", 5))
            return 0==memcmp(&str[5], "-all", 4) ? TB_LIGHT_ALL : TB_LIGHT;
    }
    return def;
}

static EMouseOver toMouseOver(const char *str, EMouseOver def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "true", 4) || 0==memcmp(str, "colored", 7))
            return MO_COLORED;
        if(0==memcmp(str, "thickcolored", 12))
            return MO_COLORED_THICK;
        if(0==memcmp(str, "plastik", 7))
            return MO_PLASTIK;
        if(0==memcmp(str, "glow", 4))
            return MO_GLOW;
        if(0==memcmp(str, "false", 4) || 0==memcmp(str, "none", 4))
            return MO_NONE;
    }
    return def;
}

static EAppearance toAppearance(const char *str, EAppearance def, EAppAllow allow, QtCPixmap *pix, bool checkImage)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "flat", 4))
            return APPEARANCE_FLAT;
        if(0==memcmp(str, "raised", 6))
            return APPEARANCE_RAISED;
        if(0==memcmp(str, "dullglass", 9))
            return APPEARANCE_DULL_GLASS;
        if(0==memcmp(str, "glass", 5) || 0==memcmp(str, "shinyglass", 10))
            return APPEARANCE_SHINY_GLASS;
        if(0==memcmp(str, "agua", 4))
#if defined __cplusplus && !defined CONFIG_DIALOG  && defined QT_VERSION && QT_VERSION < 0x040000
            return APPEARANCE_AGUA_MOD;
#else
            return APPEARANCE_AGUA;
#endif
        if(0==memcmp(str, "soft", 4))
            return APPEARANCE_SOFT_GRADIENT;
        if(0==memcmp(str, "gradient", 8) || 0==memcmp(str, "lightgradient", 13))
            return APPEARANCE_GRADIENT;
        if(0==memcmp(str, "harsh", 5))
            return APPEARANCE_HARSH_GRADIENT;
        if(0==memcmp(str, "inverted", 8))
            return APPEARANCE_INVERTED;
        if(0==memcmp(str, "darkinverted", 12))
            return APPEARANCE_DARK_INVERTED;
        if(0==memcmp(str, "splitgradient", 13))
            return APPEARANCE_SPLIT_GRADIENT;
        if(0==memcmp(str, "bevelled", 8))
            return APPEARANCE_BEVELLED;
        if(APP_ALLOW_FADE==allow && 0==memcmp(str, "fade", 4))
            return APPEARANCE_FADE;
        if(APP_ALLOW_STRIPED==allow && 0==memcmp(str, "striped", 7))
            return APPEARANCE_STRIPED;
        if(APP_ALLOW_NONE==allow && 0==memcmp(str, "none", 4))
            return APPEARANCE_NONE;
        if(NULL!=pix && APP_ALLOW_STRIPED==allow && 0==memcmp(str, "file", 4) && strlen(str)>9)
            return loadImage(&str[5], pix) || !checkImage ? APPEARANCE_FILE : def;

        if(0==memcmp(str, "customgradient", 14) && strlen(str)>14)
        {
            int i=atoi(&str[14]);

            i--;
            if(i>=0 && i<NUM_CUSTOM_GRAD)
                return (EAppearance)(APPEARANCE_CUSTOM1+i);
        }
    }
    return def;
}

static EShade toShade(const char *str, bool allowMenu, EShade def, bool menuShade, color *col)
{
    if(str && 0!=str[0])
    {
        /* true/false is from 0.25... */
        if((!menuShade && 0==memcmp(str, "true", 4)) || 0==memcmp(str, "selected", 8))
            return SHADE_BLEND_SELECTED;
        if(0==memcmp(str, "origselected", 12))
            return SHADE_SELECTED;
        if(allowMenu && (0==memcmp(str, "darken", 6) || (menuShade && 0==memcmp(str, "true", 4))))
            return SHADE_DARKEN;
        if(allowMenu && 0==memcmp(str, "wborder", 7))
            return SHADE_WINDOW_BORDER;
        if(0==memcmp(str, "custom", 6))
            return SHADE_CUSTOM;
        if('#'==str[0] && col)
        {
            qtcSetRgb(col, str);
            return SHADE_CUSTOM;
        }
        if(0==memcmp(str, "none", 4))
            return SHADE_NONE;
    }

    return def;
}

/* Prior to 0.42 round was a bool - so need to read 'false' as 'none' */
static ERound toRound(const char *str, ERound def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "none", 4) || 0==memcmp(str, "false", 5))
            return ROUND_NONE;
        if(0==memcmp(str, "slight", 6))
            return ROUND_SLIGHT;
        if(0==memcmp(str, "full", 4))
            return ROUND_FULL;
        if(0==memcmp(str, "extra", 5))
            return ROUND_EXTRA;
        if(0==memcmp(str, "max", 3))
            return ROUND_MAX;
    }

    return def;
}

static EScrollbar toScrollbar(const char *str, EScrollbar def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "kde", 3))
            return SCROLLBAR_KDE;
        if(0==memcmp(str, "windows", 7))
            return SCROLLBAR_WINDOWS;
        if(0==memcmp(str, "platinum", 8))
            return SCROLLBAR_PLATINUM;
        if(0==memcmp(str, "next", 4))
            return SCROLLBAR_NEXT;
        if(0==memcmp(str, "none", 4))
            return SCROLLBAR_NONE;
    }

    return def;
}

static EFrame toFrame(const char *str, EFrame def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "none", 4))
            return FRAME_NONE;
        if(0==memcmp(str, "plain", 5))
            return FRAME_PLAIN;
        if(0==memcmp(str, "line", 4))
            return FRAME_LINE;
        if(0==memcmp(str, "shaded", 6))
            return FRAME_SHADED;
        if(0==memcmp(str, "faded", 5))
            return FRAME_FADED;
    }

    return def;
}

static EEffect toEffect(const char *str, EEffect def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "none", 4))
            return EFFECT_NONE;
        if(0==memcmp(str, "shadow", 6))
            return EFFECT_SHADOW;
        if(0==memcmp(str, "etch", 4))
            return EFFECT_ETCH;
    }

    return def;
}

static EShading toShading(const char *str, EShading def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "simple", 6))
            return SHADING_SIMPLE;
        if(0==memcmp(str, "hsl", 3))
            return SHADING_HSL;
        if(0==memcmp(str, "hsv", 3))
            return SHADING_HSV;
        if(0==memcmp(str, "hcy", 3))
            return SHADING_HCY;
    }

    return def;
}

static EStripe toStripe(const char *str, EStripe def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "plain", 5) || 0==memcmp(str, "true", 4))
            return STRIPE_PLAIN;
        if(0==memcmp(str, "none", 4) || 0==memcmp(str, "false", 5))
            return STRIPE_NONE;
        if(0==memcmp(str, "diagonal", 8))
            return STRIPE_DIAGONAL;
        if(0==memcmp(str, "fade", 4))
            return STRIPE_FADE;
    }

    return def;
}

static ESliderStyle toSlider(const char *str, ESliderStyle def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "round", 5))
            return SLIDER_ROUND;
        if(0==memcmp(str, "plain", 5))
            return SLIDER_PLAIN;
        if(0==memcmp(str, "r-round", 7))
            return SLIDER_ROUND_ROTATED;
        if(0==memcmp(str, "r-plain", 7))
            return SLIDER_PLAIN_ROTATED;
        if(0==memcmp(str, "triangular", 10))
            return SLIDER_TRIANGULAR;
        if(0==memcmp(str, "circular", 8))
            return SLIDER_CIRCULAR;
    }

    return def;
}

static EColor toEColor(const char *str, EColor def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "base", 4))
            return ECOLOR_BASE;
        if(0==memcmp(str, "dark", 4))
            return ECOLOR_DARK;
        if(0==memcmp(str, "background", 10))
            return ECOLOR_BACKGROUND;
    }

    return def;
}

static EFocus toFocus(const char *str, EFocus def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "standard", 8))
            return FOCUS_STANDARD;
        if(0==memcmp(str, "rect", 4) || 0==memcmp(str, "highlight", 9))
            return FOCUS_RECTANGLE;
        if(0==memcmp(str, "filled", 6))
            return FOCUS_FILLED;
        if(0==memcmp(str, "full", 4))
            return FOCUS_FULL;
        if(0==memcmp(str, "line", 4))
            return FOCUS_LINE;
        if(0==memcmp(str, "glow", 4))
            return FOCUS_GLOW;
    }

    return def;
}

static ETabMo toTabMo(const char *str, ETabMo def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "top", 3))
            return TAB_MO_TOP;
        if(0==memcmp(str, "bot", 3))
            return TAB_MO_BOTTOM;
        if(0==memcmp(str, "glow", 4))
            return TAB_MO_GLOW;
    }

    return def;
}

static EGradType toGradType(const char *str, EGradType def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "horiz", 5))
            return GT_HORIZ;
        if(0==memcmp(str, "vert", 4))
            return GT_VERT;
    }
    return def;
}

static bool toLvLines(const char *str, bool def)
{
    if(str && 0!=str[0])
    {
#if 0
        if(0==memcmp(str, "true", 4) || 0==memcmp(str, "new", 3))
            return LV_NEW;
        if(0==memcmp(str, "old", 3))
            return LV_OLD;
        if(0==memcmp(str, "false", 5) || 0==memcmp(str, "none", 4))
            return LV_NONE;
#else
        return 0!=memcmp(str, "false", 5);
#endif
    }
    return def;
}

static EGradientBorder toGradientBorder(const char *str, bool *haveAlpha)
{
    if(str && 0!=str[0])
    {
        *haveAlpha=strstr(str, "-alpha") ? true : false;
        if(0==memcmp(str, "light", 5) || 0==memcmp(str, "true", 4))
            return GB_LIGHT;
        if(0==memcmp(str, "none", 4))
            return GB_NONE;
        if(0==memcmp(str, "3dfull", 6))
            return GB_3D_FULL;
        if(0==memcmp(str, "3d", 2) || 0==memcmp(str, "false", 5))
            return GB_3D;
        if(0==memcmp(str, "shine", 5))
            return GB_SHINE;
    }
    return GB_3D;
}

#ifdef __cplusplus
static EAlign toAlign(const char *str, EAlign def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "left", 4))
            return ALIGN_LEFT;
        if(0==memcmp(str, "center-full", 11))
            return ALIGN_FULL_CENTER;
        if(0==memcmp(str, "center", 6))
            return ALIGN_CENTER;
        if(0==memcmp(str, "right", 5))
            return ALIGN_RIGHT;
    }
    return def;
}
#endif

#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
static ETitleBarIcon toTitlebarIcon(const char *str, ETitleBarIcon def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "none", 4))
            return TITLEBAR_ICON_NONE;
        if(0==memcmp(str, "menu", 4))
            return TITLEBAR_ICON_MENU_BUTTON;
        if(0==memcmp(str, "title", 5))
            return TITLEBAR_ICON_NEXT_TO_TITLE;
    }
    return def;
}
#endif

static EImageType toImageType(const char *str, EImageType def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "none", 4))
            return IMG_NONE;
        if(0==memcmp(str, "plainrings", 10))
            return IMG_PLAIN_RINGS;
        if(0==memcmp(str, "rings", 5))
            return IMG_BORDERED_RINGS;
        if(0==memcmp(str, "squarerings", 11))
            return IMG_SQUARE_RINGS;
        if(0==memcmp(str, "file", 4))
            return IMG_FILE;
    }
    return def;
}

static EGlow toGlow(const char *str, EGlow def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "none", 4))
            return GLOW_NONE;
        if(0==memcmp(str, "start", 5))
            return GLOW_START;
        if(0==memcmp(str, "middle", 6))
            return GLOW_MIDDLE;
        if(0==memcmp(str, "end", 3))
            return GLOW_END;
    }
    return def;
}

static ETBarBtn toTBarBtn(const char *str, ETBarBtn def)
{
    if(str && 0!=str[0])
    {
        if(0==memcmp(str, "standard", 8))
            return TBTN_STANDARD;
        if(0==memcmp(str, "raised", 6))
            return TBTN_RAISED;
        if(0==memcmp(str, "joined", 6))
            return TBTN_JOINED;
    }
    return def;
}

const char * qtcGetHome()
{
    static const char *home=NULL;

#ifdef _WIN32
    home = getenv("HOMEPATH");
#else
    if(!home)
    {
        struct passwd *p=getpwuid(getuid());

        if(p)
            home=p->pw_dir;
        else
        {
            char *env=getenv("HOME");

            if(env)
                home=env;
        }

        if(!home)
            home="/tmp";
    }
#endif
    return home;
}

#ifdef __cplusplus

#if defined QTC_QT_ONLY || QT_VERSION < 0x040000
#if QT_VERSION < 0x040000
#include <qdir.h>
#include <qfile.h>
#else
#include <QtCore/QDir>
#endif
// Take from KStandardDirs::makeDir
static bool makeDir(const QString& dir, int mode)
{
    // we want an absolute path
    if (QDir::isRelativePath(dir))
        return false;

#ifdef Q_WS_WIN
    return QDir().mkpath(dir);
#else
    QString target = dir;
    uint len = target.length();

    // append trailing slash if missing
    if (dir.at(len - 1) != '/')
        target += '/';

    QString base;
    uint i = 1;

    while( i < len )
    {
        struct stat st;
#if QT_VERSION >= 0x040000
        int pos = target.indexOf('/', i);
#else
        int pos = target.find('/', i);
#endif
        base += target.mid(i - 1, pos - i + 1);
        QByteArray baseEncoded = QFile::encodeName(base);
        // bail out if we encountered a problem
        if (stat(baseEncoded, &st) != 0)
        {
            // Directory does not exist....
            // Or maybe a dangling symlink ?
            if (lstat(baseEncoded, &st) == 0)
                (void)unlink(baseEncoded); // try removing

            if (mkdir(baseEncoded, static_cast<mode_t>(mode)) != 0)
            {
#if QT_VERSION >= 0x040000
                baseEncoded.prepend("trying to create local folder ");
                perror(baseEncoded.constData());
#else
                perror("trying to create QtCurve config folder ");
#endif
                return false; // Couldn't create it :-(
            }
        }
        i = pos + 1;
    }
    return true;
#endif
}

#else
#include <kstandarddirs.h>
#endif
#endif

const char *qtcConfDir()
{
    // Changed by Kovid to not create an empty qtcurve dir
    return "non existent dir kfdjkdfjsvbksjbkjdsfveralihg8743yh38qlq vqp84982hqpi2bu4iboABVJAVB93";
    static char *cfgDir=NULL;

    if(!cfgDir)
    {
        static const char *home=NULL;

#if 0
        char *env=getenv("XDG_CONFIG_HOME");

        /*
            Check the setting of XDG_CONFIG_HOME
            For some reason, sudo leaves the env vars set to those of the
            caller - so XDG_CONFIG_HOME would point to the users setting, and
            not roots.

            Therefore, check that home is first part of XDG_CONFIG_HOME
        */

        if(env && 0==getuid())
        {
            if(!home)
                home=qtcGetHome();
            if(home && home!=strstr(env, home))
                env=NULL;
        }
#else
        /*
           Hmm... for 'root' dont bother to check env var, just set to ~/.config
           - as problems would arise if "sudo kcmshell style", and then
           "sudo su" / "kcmshell style". The 1st would write to ~/.config, but
           if root has a XDG_ set then that would be used on the second :-(
        */
#ifndef _WIN32
        char *env=0==getuid() ? NULL : getenv("XDG_CONFIG_HOME");
#else
        char *env=0;
#endif

#endif

        if(!env)
        {
            if(!home)
                home=qtcGetHome();

            cfgDir=(char *)malloc(strlen(home)+18);
            sprintf(cfgDir, "%s/.config/qtcurve/", home);
        }
        else
        {
            cfgDir=(char *)malloc(strlen(env)+10);
            sprintf(cfgDir, "%s/qtcurve/", env);
        }

//#if defined CONFIG_WRITE || !defined __cplusplus
        {
        struct stat info;

        if(0!=lstat(cfgDir, &info))
        {
#ifdef __cplusplus
#if defined QTC_QT_ONLY || QT_VERSION < 0x040000
            makeDir(cfgDir, 0755);
#else
            KStandardDirs::makeDir(cfgDir, 0755);
#endif
#else
            g_mkdir_with_parents(cfgDir, 0755);
#endif
        }
        }
//#endif
    }

    return cfgDir;
}

#ifdef __cplusplus
WindowBorders qtcGetWindowBorderSize(bool force)
#else
WindowBorders qtcGetWindowBorderSize(bool force)
#endif
{
    static WindowBorders def={24, 18, 4, 4};
    static WindowBorders sizes={-1, -1, -1, -1};

    if(-1==sizes.titleHeight || force)
    {
#ifdef __cplusplus
        QFile f(qtcConfDir()+QString(BORDER_SIZE_FILE));

#if QT_VERSION >= 0x040000
        if(f.open(QIODevice::ReadOnly))
#else
        if(f.open(IO_ReadOnly))
#endif
        {
            QTextStream stream(&f);
            QString     line;

            sizes.titleHeight=stream.readLine().toInt();
            sizes.toolTitleHeight=stream.readLine().toInt();
            sizes.bottom=stream.readLine().toInt();
            sizes.sides=stream.readLine().toInt();
            f.close();
        }
#else // __cplusplus
        char *filename=(char *)malloc(strlen(qtcConfDir())+strlen(BORDER_SIZE_FILE)+1);
        FILE *f=NULL;

        sprintf(filename, "%s"BORDER_SIZE_FILE, qtcConfDir());
        if((f=fopen(filename, "r")))
        {
            char *line=NULL;
            size_t len;
            getline(&line, &len, f);
            sizes.titleHeight=atoi(line);
            getline(&line, &len, f);
            sizes.toolTitleHeight=atoi(line);
            getline(&line, &len, f);
            sizes.bottom=atoi(line);
            getline(&line, &len, f);
            sizes.sides=atoi(line);
            if(line)
                free(line);
            fclose(f);
        }
        free(filename);
#endif // __cplusplus
    }

    return sizes.titleHeight<12 ? def : sizes;
}

#if (!defined QT_VERSION || QT_VERSION >= 0x040000) && !defined CONFIG_DIALOG

#ifdef __cplusplus
bool qtcBarHidden(const QString &app, const char *prefix)
{
    return QFile::exists(QFile::decodeName(qtcConfDir())+prefix+app);
}

void qtcSetBarHidden(const QString &app, bool hidden, const char *prefix)
{
    if(!hidden)
        QFile::remove(QFile::decodeName(qtcConfDir())+prefix+app);
    else
        QFile(QFile::decodeName(qtcConfDir())+prefix+app).open(QIODevice::WriteOnly);
}

#else // __cplusplus
static bool qtcFileExists(const char *name)
{
    struct stat info;

    return 0==lstat(name, &info) && S_ISREG(info.st_mode);
}

static char * qtcGetBarFileName(const char *app, const char *prefix)
{
    static char *filename=NULL;

    filename=(char *)realloc(filename, strlen(qtcConfDir())+strlen(prefix)+strlen(app)+1);
    sprintf(filename, "%s%s%s", qtcConfDir(), prefix, app);

    return filename;
}

bool qtcBarHidden(const char *app, const char *prefix)
{
    return qtcFileExists(qtcGetBarFileName(app, prefix));
}

void qtcSetBarHidden(const char *app, bool hidden, const char *prefix)
{
    if(!hidden)
        unlink(qtcGetBarFileName(app, prefix));
    else
    {
        FILE *f=fopen(qtcGetBarFileName(app, prefix), "w");

        if(f)
            fclose(f);
    }
}

#endif // __cplusplus

#ifdef __cplusplus
#include <QtSvg/QSvgRenderer>
#include <QtGui/QPainter>
#endif // __cplusplus

void qtcLoadBgndImage(QtCImage *img)
{
    if(!img->loaded &&
        ( (img->width>16 && img->width<1024 && img->height>16 && img->height<1024) || (0==img->width && 0==img->height)) )
    {
        img->loaded=true;
#ifdef __cplusplus
        img->pixmap.img=QPixmap();
        QString file(determineFileName(img->pixmap.file));

        if(!file.isEmpty())
        {
            bool loaded=false;
            if(0!=img->width && (file.endsWith(".svg", Qt::CaseInsensitive) || file.endsWith(".svgz", Qt::CaseInsensitive)))
            {
                QSvgRenderer svg(file);

                if(svg.isValid())
                {
                    img->pixmap.img=QPixmap(img->width, img->height);
                    img->pixmap.img.fill(Qt::transparent);
                    QPainter painter(&img->pixmap.img);
                    svg.render(&painter);
                    painter.end();
                    loaded=true;
                }
            }
            if(!loaded && img->pixmap.img.load(file) && 0!=img->width &&
               (img->pixmap.img.height()!=img->height || img->pixmap.img.width()!=img->width))
                img->pixmap.img=img->pixmap.img.scaled(img->width, img->height, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
        }
#else // __cplusplus
        img->pixmap.img=0L;
        if(img->pixmap.file)
        {
            img->pixmap.img=0==img->width
                            ? gdk_pixbuf_new_from_file(determineFileName(img->pixmap.file), NULL)
                            : gdk_pixbuf_new_from_file_at_scale(determineFileName(img->pixmap.file), img->width, img->height, FALSE, NULL);
            if(img->pixmap.img && 0==img->width && img->pixmap.img)
            {
                img->width=gdk_pixbuf_get_width(img->pixmap.img);
                img->height=gdk_pixbuf_get_height(img->pixmap.img);
            }
        }
#endif // __cplusplus
    }
}

#endif // (!defined QT_VERSION || QT_VERSION >= 0x040000) && !defined CONFIG_DIALOG

static void checkColor(EShade *s, color *c)
{
    if(SHADE_CUSTOM==*s && IS_BLACK(*c))
        *s=SHADE_NONE;
}

#ifdef __cplusplus

class QtCConfig
{
    public:

    QtCConfig(const QString &filename);

    bool            ok() const { return values.count()>0; }
    bool            hasKey(const QString &key) { return values.contains(key); }
    const QString & readEntry(const QString &key, const QString &def=QString::null);

    private:

    QMap<QString, QString> values;
};

QtCConfig::QtCConfig(const QString &filename)
{
    if (filename.isEmpty()) return; // Changed by Kovid to ensure config files are never read
    QFile f(filename);

#if QT_VERSION >= 0x040000
    if(f.open(QIODevice::ReadOnly))
#else
    if(f.open(IO_ReadOnly))
#endif
    {
        QTextStream stream(&f);
        QString     line;

        while(!stream.atEnd())
        {
            line = stream.readLine();
#if QT_VERSION >= 0x040000
            int pos=line.indexOf('=');
#else
            int pos=line.find('=');
#endif
            if(-1!=pos)
                values[line.left(pos)]=line.mid(pos+1);
        }
        f.close();
    }
}

inline const QString & QtCConfig::readEntry(const QString &key, const QString &def)
{
    return values.contains(key) ? values[key] : def;
}

inline QString readStringEntry(QtCConfig &cfg, const QString &key)
{
    return cfg.readEntry(key);
}

static int readNumEntry(QtCConfig &cfg, const QString &key, int def)
{
    const QString &val(readStringEntry(cfg, key));

    return val.isEmpty() ? def : val.toInt();
}

static int readVersionEntry(QtCConfig &cfg, const QString &key)
{
    const QString &val(readStringEntry(cfg, key));
    int           major, minor, patch;

    return !val.isEmpty() && 3==sscanf(TO_LATIN1(val), "%d.%d.%d", &major, &minor, &patch)
            ? MAKE_VERSION3(major, minor, patch)
            : 0;
}

static bool readBoolEntry(QtCConfig &cfg, const QString &key, bool def)
{
    const QString &val(readStringEntry(cfg, key));

    return val.isEmpty() ? def : (val=="true" ? true : false);
}

static void readDoubleList(QtCConfig &cfg, const char *key, double *list, int count)
{
#if (defined QT_VERSION && (QT_VERSION >= 0x040000))
    QStringList strings(readStringEntry(cfg, key).split(',', QString::SkipEmptyParts));
#else
    QStringList strings(QStringList::split(',', readStringEntry(cfg, key)));
#endif
    bool ok(count==strings.size());

    if(ok)
    {
        QStringList::ConstIterator it(strings.begin());
        int                        i;

        for(i=0; i<count && ok; ++i, ++it)
            list[i]=(*it).toDouble(&ok);
    }

    if(!ok && strings.size())
        list[0]=0;
}

#define CFG_READ_COLOR(ENTRY) \
    { \
        QString sVal(cfg.readEntry(#ENTRY)); \
        if(sVal.isEmpty()) \
            opts->ENTRY=def->ENTRY; \
        else \
            qtcSetRgb(&(opts->ENTRY), TO_LATIN1(sVal)); \
    }

#define CFG_READ_IMAGE(ENTRY) \
    { \
        opts->ENTRY.type=toImageType(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY.type); \
        opts->ENTRY.loaded=false; \
        opts->ENTRY.width=opts->ENTRY.height=0; \
        opts->ENTRY.onBorder=false; \
        opts->ENTRY.pos=PP_TR; \
        if(IMG_FILE==opts->ENTRY.type) \
        { \
            QString file(cfg.readEntry(#ENTRY ".file")); \
            if(!file.isEmpty()) \
            { \
                opts->ENTRY.pixmap.file=file; \
                opts->ENTRY.width=readNumEntry(cfg, #ENTRY ".width", 0); \
                opts->ENTRY.height=readNumEntry(cfg, #ENTRY ".height", 0); \
                opts->ENTRY.onBorder=readBoolEntry(cfg, #ENTRY ".onBorder", false); \
                opts->ENTRY.pos=(EPixPos)readNumEntry(cfg, #ENTRY ".pos", (int)PP_TR); \
            } \
            else \
                opts->ENTRY.type=IMG_NONE; \
        } \
    }

#if QT_VERSION >= 0x040000
    #define CFG_READ_STRING_LIST(ENTRY) \
        { \
            QString val=readStringEntry(cfg, #ENTRY); \
            Strings set=val.isEmpty() ? Strings() : Strings::fromList(val.split(",", QString::SkipEmptyParts)); \
            opts->ENTRY=set.count() || cfg.hasKey(#ENTRY) ? set : def->ENTRY; \
        }
#else
    #define CFG_READ_STRING_LIST(ENTRY) \
        { \
            QString val=readStringEntry(cfg, #ENTRY); \
            Strings list=val.isEmpty() ? Strings() : Strings::split(",", val, false); \
            opts->ENTRY=list.count() || cfg.hasKey(#ENTRY) ? list : def->ENTRY; \
        }
#endif

#else

static char * lookupCfgHash(GHashTable **cfg, char *key, char *val)
{
    char *rv=NULL;

    if(!*cfg)
        *cfg=g_hash_table_new(g_str_hash, g_str_equal);
    else
        rv=(char *)g_hash_table_lookup(*cfg, key);

    if(!rv && val)
    {
        g_hash_table_insert(*cfg, g_strdup(key), g_strdup(val));
        rv=(char *)g_hash_table_lookup(*cfg, key);
    }

    return rv;
}

static GHashTable * loadConfig(const char *filename)
{
    FILE       *f=fopen(filename, "r");
    GHashTable *cfg=NULL;

    if(f)
    {
        char line[MAX_CONFIG_INPUT_LINE_LEN];

        while(NULL!=fgets(line, MAX_CONFIG_INPUT_LINE_LEN-1, f))
        {
            char *eq=strchr(line, '=');
            int  pos=eq ? eq-line : -1;

            if(pos>0)
            {
                char *endl=strchr(line, '\n');

                if(endl)
                    *endl='\0';

                line[pos]='\0';

                lookupCfgHash(&cfg, line, &line[pos+1]);
            }
        }

        fclose(f);
    }

    return cfg;
}

static void releaseConfig(GHashTable *cfg)
{
    g_hash_table_destroy(cfg);
}

static char * readStringEntry(GHashTable *cfg, char *key)
{
    return lookupCfgHash(&cfg, key, NULL);
}

static int readNumEntry(GHashTable *cfg, char *key, int def)
{
    char *str=readStringEntry(cfg, key);

    return str ? atoi(str) : def;
}

static int readVersionEntry(GHashTable *cfg, char *key)
{
    char *str=readStringEntry(cfg, key);
    int  major, minor, patch;

    return str && 3==sscanf(str, "%d.%d.%d", &major, &minor, &patch)
            ? MAKE_VERSION3(major, minor, patch)
            : 0;
}

static gboolean readBoolEntry(GHashTable *cfg, char *key, gboolean def)
{
    char *str=readStringEntry(cfg, key);

    return str ? (0==memcmp(str, "true", 4) ? true : false) : def;
}

static void readDoubleList(GHashTable *cfg, char *key, double *list, int count)
{
    char *str=readStringEntry(cfg, key);

    if(str && 0!=str[0])
    {
        int  j,
             comma=0;
        bool ok=true;

        for(j=0; str[j]; ++j)
            if(','==str[j])
                comma++;

        ok=(count-1)==comma;
        if(ok)
        {
            for(j=0; j<comma+1 && str && ok; ++j)
            {
                char *c=strchr(str, ',');

                if(c || (str && count-1==comma))
                {
                    if(c)
                        *c='\0';
                    list[j]=g_ascii_strtod(str, NULL);
                    str=c+1;
                }
                else
                    ok=false;
            }
        }

        if(!ok)
            list[0]=0;
    }
}

#define TO_LATIN1(A) A

#define CFG_READ_COLOR(ENTRY) \
    { \
        const char *str=readStringEntry(cfg, #ENTRY); \
    \
        if(str && 0!=str[0]) \
            qtcSetRgb(&(opts->ENTRY), str); \
        else \
            opts->ENTRY=def->ENTRY; \
    }
#define CFG_READ_IMAGE(ENTRY) \
    { \
        opts->ENTRY.type=toImageType(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY.type); \
        opts->ENTRY.loaded=false; \
        if(IMG_FILE==opts->ENTRY.type) \
        { \
            const char *file=readStringEntry(cfg, #ENTRY ".file"); \
            if(file) \
            { \
                opts->ENTRY.pixmap.file=file; \
                opts->ENTRY.width=readNumEntry(cfg, #ENTRY ".width", 0); \
                opts->ENTRY.height=readNumEntry(cfg, #ENTRY ".height", 0); \
                opts->ENTRY.onBorder=readBoolEntry(cfg, #ENTRY ".onBorder", false); \
                opts->ENTRY.pos=(EPixPos)readNumEntry(cfg, #ENTRY ".pos", (int)PP_TR); \
            } \
            else \
            { \
                opts->ENTRY.type=IMG_NONE; \
            } \
        } \
    }
#define CFG_READ_STRING_LIST(ENTRY) \
    { \
        const gchar *str=readStringEntry(cfg, #ENTRY); \
        if(str && 0!=str[0]) \
            opts->ENTRY=g_strsplit(str, ",", -1); \
        else if(def->ENTRY) \
        { \
            opts->ENTRY=def->ENTRY; \
            def->ENTRY=NULL; \
        } \
    }

#endif

#define CFG_READ_BOOL(ENTRY) \
    opts->ENTRY=readBoolEntry(cfg, #ENTRY, def->ENTRY);

#define CFG_READ_ROUND(ENTRY) \
    opts->ENTRY=toRound(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_INT(ENTRY) \
    opts->ENTRY=readNumEntry(cfg, #ENTRY, def->ENTRY);

#define CFG_READ_INT_BOOL(ENTRY, DEF) \
    if(readBoolEntry(cfg, #ENTRY, false)) \
        opts->ENTRY=DEF; \
    else \
        opts->ENTRY=readNumEntry(cfg, #ENTRY, def->ENTRY);

#define CFG_READ_TB_BORDER(ENTRY) \
    opts->ENTRY=toTBarBorder(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_MOUSE_OVER(ENTRY) \
    opts->ENTRY=toMouseOver(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_APPEARANCE(ENTRY, ALLOW) \
    opts->ENTRY=toAppearance(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY, ALLOW, NULL, false);

#define CFG_READ_APPEARANCE_PIXMAP(ENTRY, ALLOW, PIXMAP, CHECK) \
    opts->ENTRY=toAppearance(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY, ALLOW, PIXMAP, CHECK);

/*
#define CFG_READ_APPEARANCE(ENTRY) \
    opts->ENTRY=toAppearance(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);
*/

#define CFG_READ_STRIPE(ENTRY) \
    opts->ENTRY=toStripe(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_SLIDER(ENTRY) \
    opts->ENTRY=toSlider(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_DEF_BTN(ENTRY) \
    opts->ENTRY=toInd(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_LINE(ENTRY) \
    opts->ENTRY=toLine(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_SHADE(ENTRY, AD, MENU_STRIPE, COL) \
    opts->ENTRY=toShade(TO_LATIN1(readStringEntry(cfg, #ENTRY)), AD, def->ENTRY, MENU_STRIPE, COL);

#define CFG_READ_SCROLLBAR(ENTRY) \
    opts->ENTRY=toScrollbar(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_FRAME(ENTRY) \
    opts->ENTRY=toFrame(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_EFFECT(ENTRY) \
    opts->ENTRY=toEffect(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_SHADING(ENTRY) \
    opts->ENTRY=toShading(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_ECOLOR(ENTRY) \
    opts->ENTRY=toEColor(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_FOCUS(ENTRY) \
    opts->ENTRY=toFocus(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_TAB_MO(ENTRY) \
    opts->ENTRY=toTabMo(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_GRAD_TYPE(ENTRY) \
    opts->ENTRY=toGradType(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_LV_LINES(ENTRY) \
    opts->ENTRY=toLvLines(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#ifdef __cplusplus
#define CFG_READ_ALIGN(ENTRY) \
    opts->ENTRY=toAlign(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);
#endif

#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
#define CFG_READ_TB_ICON(ENTRY) \
    opts->ENTRY=toTitlebarIcon(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);
#endif

#define CFG_READ_GLOW(ENTRY) \
    opts->ENTRY=toGlow(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

#define CFG_READ_TBAR_BTN(ENTRY) \
    opts->ENTRY=toTBarBtn(TO_LATIN1(readStringEntry(cfg, #ENTRY)), def->ENTRY);

static void checkAppearance(EAppearance *ap, Options *opts)
{
    if(*ap>=APPEARANCE_CUSTOM1 && *ap<(APPEARANCE_CUSTOM1+NUM_CUSTOM_GRAD))
    {
#ifdef __cplusplus
        if(opts->customGradient.end()==opts->customGradient.find(*ap))
#else
        if(!opts->customGradient[*ap-APPEARANCE_CUSTOM1])
#endif
        {
            if(ap==&opts->appearance)
                *ap=APPEARANCE_FLAT;
            else
                *ap=opts->appearance;
        }
    }
}

void qtcDefaultSettings(Options *opts);

#ifndef __cplusplus
static void copyGradients(Options *src, Options *dest)
{
    if(src && dest && src!=dest)
    {
        int i;

        for(i=0; i<NUM_CUSTOM_GRAD; ++i)
            if(src->customGradient[i] && src->customGradient[i]->numStops>0)
            {
                dest->customGradient[i]=malloc(sizeof(Gradient));
                dest->customGradient[i]->numStops=src->customGradient[i]->numStops;
                dest->customGradient[i]->stops=malloc(sizeof(GradientStop) * dest->customGradient[i]->numStops);
                memcpy(dest->customGradient[i]->stops, src->customGradient[i]->stops,
                        sizeof(GradientStop) * dest->customGradient[i]->numStops);
                dest->customGradient[i]->border=src->customGradient[i]->border;
            }
            else
                dest->customGradient[i]=NULL;
    }
}

static void copyOpts(Options *src, Options *dest)
{
    if(src && dest && src!=dest)
    {
        memcpy(dest, src, sizeof(Options));
        dest->noBgndGradientApps=src->noBgndGradientApps;
        dest->noBgndOpacityApps=src->noBgndOpacityApps;
        dest->noMenuBgndOpacityApps=src->noMenuBgndOpacityApps;
        dest->noBgndImageApps=src->noBgndImageApps;
#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
        dest->noDlgFixApps=src->noDlgFixApps;
        src->noDlgFixApps=NULL;
#endif
        dest->noMenuStripeApps=src->noMenuStripeApps;
        src->noBgndGradientApps=src->noBgndOpacityApps=src->noMenuBgndOpacityApps=src->noBgndImageApps=src->noMenuStripeApps=NULL;
        memcpy(dest->customShades, src->customShades, sizeof(double)*NUM_STD_SHADES);
        memcpy(dest->customAlphas, src->customAlphas, sizeof(double)*NUM_STD_ALPHAS);
        copyGradients(src, dest);
    }
}

static void freeOpts(Options *opts)
{
    if(opts)
    {
        int i;

        if(opts->noBgndGradientApps)
            g_strfreev(opts->noBgndGradientApps);
        if(opts->noBgndOpacityApps)
            g_strfreev(opts->noBgndOpacityApps);
        if(opts->noMenuBgndOpacityApps)
            g_strfreev(opts->noMenuBgndOpacityApps);
        if(opts->noBgndImageApps)
            g_strfreev(opts->noBgndImageApps);
#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
        if(opts->noDlgFixApps)
            g_strfreev(opts->noDlgFixApps);
        opts->noDlgFixApps=NULL
#endif
        if(opts->noMenuStripeApps)
            g_strfreev(opts->noMenuStripeApps);
        opts->noBgndGradientApps=opts->noBgndOpacityApps=opts->noMenuBgndOpacityApps=opts->noBgndImageApps=opts->noMenuStripeApps=NULL;
        for(i=0; i<NUM_CUSTOM_GRAD; ++i)
            if(opts->customGradient[i])
            {
                if(opts->customGradient[i]->stops)
                    free(opts->customGradient[i]->stops);
                free(opts->customGradient[i]);
                opts->customGradient[i]=NULL;
            }
    }
}
#endif

void qtcCheckConfig(Options *opts)
{
    /* **Must** check appearance first, as the rest will default to this */
    checkAppearance(&opts->appearance, opts);
    checkAppearance(&opts->bgndAppearance, opts);
    checkAppearance(&opts->menuBgndAppearance, opts);
    checkAppearance(&opts->menubarAppearance, opts);
    checkAppearance(&opts->menuitemAppearance, opts);
    checkAppearance(&opts->toolbarAppearance, opts);
    checkAppearance(&opts->lvAppearance, opts);
    checkAppearance(&opts->tabAppearance, opts);
    checkAppearance(&opts->activeTabAppearance, opts);
    checkAppearance(&opts->sliderAppearance, opts);
    checkAppearance(&opts->selectionAppearance, opts);
    checkAppearance(&opts->titlebarAppearance, opts);
    checkAppearance(&opts->inactiveTitlebarAppearance, opts);
#ifdef __cplusplus
    checkAppearance(&opts->titlebarButtonAppearance, opts);
    checkAppearance(&opts->selectionAppearance, opts);
    checkAppearance(&opts->dwtAppearance, opts);
#endif
    checkAppearance(&opts->menuStripeAppearance, opts);
    checkAppearance(&opts->progressAppearance, opts);
    checkAppearance(&opts->progressGrooveAppearance, opts);
    checkAppearance(&opts->grooveAppearance, opts);
    checkAppearance(&opts->sunkenAppearance, opts);
    checkAppearance(&opts->sbarBgndAppearance, opts);
    checkAppearance(&opts->sliderFill, opts);
    checkAppearance(&opts->tooltipAppearance, opts);

    if(SHADE_BLEND_SELECTED==opts->shadeCheckRadio)
        opts->shadeCheckRadio=SHADE_SELECTED;

    checkColor(&opts->shadeMenubars, &opts->customMenubarsColor);
    checkColor(&opts->shadeSliders, &opts->customSlidersColor);
    checkColor(&opts->shadeCheckRadio, &opts->customCheckRadioColor);
    checkColor(&opts->menuStripe, &opts->customMenuStripeColor);
    checkColor(&opts->comboBtn, &opts->customComboBtnColor);
    checkColor(&opts->sortedLv, &opts->customSortedLvColor);
    if(APPEARANCE_BEVELLED==opts->toolbarAppearance)
        opts->toolbarAppearance=APPEARANCE_GRADIENT;
    else if(APPEARANCE_RAISED==opts->toolbarAppearance)
        opts->toolbarAppearance=APPEARANCE_FLAT;

    if(APPEARANCE_BEVELLED==opts->menubarAppearance)
        opts->menubarAppearance=APPEARANCE_GRADIENT;
    else if(APPEARANCE_RAISED==opts->menubarAppearance)
        opts->menubarAppearance=APPEARANCE_FLAT;

    if(APPEARANCE_BEVELLED==opts->sliderAppearance)
        opts->sliderAppearance=APPEARANCE_GRADIENT;

    if(APPEARANCE_BEVELLED==opts->tabAppearance)
        opts->tabAppearance=APPEARANCE_GRADIENT;

    if(APPEARANCE_BEVELLED==opts->activeTabAppearance)
        opts->activeTabAppearance=APPEARANCE_GRADIENT;

    if(APPEARANCE_RAISED==opts->selectionAppearance)
        opts->selectionAppearance=APPEARANCE_FLAT;
    else if(APPEARANCE_BEVELLED==opts->selectionAppearance)
        opts->selectionAppearance=APPEARANCE_GRADIENT;

    if(APPEARANCE_RAISED==opts->menuStripeAppearance)
        opts->menuStripeAppearance=APPEARANCE_FLAT;
    else if(APPEARANCE_BEVELLED==opts->menuStripeAppearance)
        opts->menuStripeAppearance=APPEARANCE_GRADIENT;

    if(opts->highlightFactor<MIN_HIGHLIGHT_FACTOR || opts->highlightFactor>MAX_HIGHLIGHT_FACTOR)
        opts->highlightFactor=DEFAULT_HIGHLIGHT_FACTOR;

    if(opts->crHighlight<MIN_HIGHLIGHT_FACTOR || opts->crHighlight>MAX_HIGHLIGHT_FACTOR)
        opts->crHighlight=DEFAULT_CR_HIGHLIGHT_FACTOR;

    if(opts->splitterHighlight<MIN_HIGHLIGHT_FACTOR || opts->splitterHighlight>MAX_HIGHLIGHT_FACTOR)
        opts->splitterHighlight=DEFAULT_SPLITTER_HIGHLIGHT_FACTOR;

#if !defined __cplusplus || defined CONFIG_DIALOG
    if(opts->expanderHighlight<MIN_HIGHLIGHT_FACTOR || opts->expanderHighlight>MAX_HIGHLIGHT_FACTOR)
        opts->expanderHighlight=DEFAULT_EXPANDER_HIGHLIGHT_FACTOR;
#endif

    if(0==opts->menuDelay) /* Qt seems to have issues if delay is 0 - so set this to 1 :-) */
        opts->menuDelay=MIN_MENU_DELAY;
    else if(opts->menuDelay<MIN_MENU_DELAY || opts->menuDelay>MAX_MENU_DELAY)
        opts->menuDelay=DEFAULT_MENU_DELAY;

    if(0==opts->sliderWidth%2)
        opts->sliderWidth++;

    if(opts->sliderWidth<MIN_SLIDER_WIDTH || opts->sliderWidth>MAX_SLIDER_WIDTH)
        opts->sliderWidth=DEFAULT_SLIDER_WIDTH;

    if(opts->sliderWidth<MIN_SLIDER_WIDTH_ROUND)
        opts->square|=SQUARE_SB_SLIDER;

    if(opts->sliderWidth<MIN_SLIDER_WIDTH_THIN_GROOVE)
        opts->thinSbarGroove=false;

    if(opts->sliderWidth<DEFAULT_SLIDER_WIDTH)
        opts->sliderThumbs=LINE_NONE;

    if(opts->lighterPopupMenuBgnd<MIN_LIGHTER_POPUP_MENU || opts->lighterPopupMenuBgnd>MAX_LIGHTER_POPUP_MENU)
        opts->lighterPopupMenuBgnd=DEF_POPUPMENU_LIGHT_FACTOR;

    if(opts->tabBgnd<MIN_TAB_BGND || opts->tabBgnd>MAX_TAB_BGND)
        opts->tabBgnd=DEF_TAB_BGND;

    if(opts->animatedProgress && !opts->stripedProgress)
        opts->animatedProgress=false;

    if(0==opts->gbFactor && FRAME_SHADED==opts->groupBox)
        opts->groupBox=FRAME_PLAIN;

    if(opts->gbFactor<MIN_GB_FACTOR || opts->gbFactor>MAX_GB_FACTOR)
        opts->gbFactor=DEF_GB_FACTOR;

    if(!opts->gtkComboMenus)
        opts->doubleGtkComboArrow=false;

#if defined __cplusplus && defined QT_VERSION && QT_VERSION < 0x040000 && !defined CONFIG_DIALOG
    opts->crSize=CR_SMALL_SIZE;
    if(SLIDER_CIRCULAR==opts->sliderStyle)
        opts->sliderStyle=SLIDER_ROUND;
    if(STRIPE_FADE==opts->stripedProgress)
        opts->stripedProgress=STRIPE_PLAIN;
#endif
    /* For now, only 2 sizes... */
    if(opts->crSize!=CR_SMALL_SIZE && opts->crSize!=CR_LARGE_SIZE)
        opts->crSize=CR_SMALL_SIZE;

/*
??
    if(SHADE_CUSTOM==opts->shadeMenubars || SHADE_BLEND_SELECTED==opts->shadeMenubars || !opts->borderMenuitems)
        opts->colorMenubarMouseOver=true;
*/

#if defined __cplusplus && defined QT_VERSION && QT_VERSION < 0x040000 && !defined CONFIG_DIALOG
    if(opts->round>ROUND_FULL)
        opts->round=ROUND_FULL;
#endif
#ifndef CONFIG_DIALOG
    if(MO_GLOW==opts->coloredMouseOver && EFFECT_NONE==opts->buttonEffect)
        opts->coloredMouseOver=MO_COLORED_THICK;

    if(IND_GLOW==opts->defBtnIndicator && EFFECT_NONE==opts->buttonEffect)
        opts->defBtnIndicator=IND_TINT;

    if(opts->round>ROUND_EXTRA && FOCUS_GLOW!=opts->focus)
        opts->focus=FOCUS_LINE;

    if(EFFECT_NONE==opts->buttonEffect)
    {
        opts->etchEntry=false;
        if(FOCUS_GLOW==opts->focus)
            opts->focus=FOCUS_FULL;
    }

//     if(opts->squareScrollViews)
//         opts->highlightScrollViews=false;

    if(SHADE_WINDOW_BORDER==opts->shadeMenubars)
        opts->shadeMenubarOnlyWhenActive=true;

    if(MO_GLOW==opts->coloredMouseOver)
        opts->coloredTbarMo=true;

    if(ROUND_NONE==opts->round)
        opts->square=SQUARE_ALL;
#endif

    if(opts->bgndOpacity<0 || opts->bgndOpacity>100)
        opts->bgndOpacity=100;
    if(opts->dlgOpacity<0 || opts->dlgOpacity>100)
        opts->dlgOpacity=100;
    if(opts->menuBgndOpacity<0 || opts->menuBgndOpacity>100)
        opts->menuBgndOpacity=100;

#ifndef CONFIG_DIALOG
    opts->bgndAppearance=MODIFY_AGUA(opts->bgndAppearance);
    opts->selectionAppearance=MODIFY_AGUA(opts->selectionAppearance);
    opts->lvAppearance=MODIFY_AGUA_X(opts->lvAppearance, APPEARANCE_LV_AGUA);
    opts->sbarBgndAppearance=MODIFY_AGUA(opts->sbarBgndAppearance);
    opts->tooltipAppearance=MODIFY_AGUA(opts->tooltipAppearance);
    opts->progressGrooveAppearance=MODIFY_AGUA(opts->progressGrooveAppearance);
    opts->menuBgndAppearance=MODIFY_AGUA(opts->menuBgndAppearance);
    opts->menuStripeAppearance=MODIFY_AGUA(opts->menuStripeAppearance);
    opts->grooveAppearance=MODIFY_AGUA(opts->grooveAppearance);
    opts->progressAppearance=MODIFY_AGUA(opts->progressAppearance);
    opts->sliderFill=MODIFY_AGUA(opts->sliderFill);
    opts->tabAppearance=MODIFY_AGUA(opts->tabAppearance);
    opts->activeTabAppearance=MODIFY_AGUA(opts->activeTabAppearance);
    opts->menuitemAppearance=MODIFY_AGUA(opts->menuitemAppearance);

    if(!opts->borderProgress && (!opts->fillProgress || !(opts->square&SQUARE_PROGRESS)))
        opts->borderProgress=true;

    opts->titlebarAppearance=MODIFY_AGUA(opts->titlebarAppearance);
    opts->inactiveTitlebarAppearance=MODIFY_AGUA(opts->inactiveTitlebarAppearance);

    if(opts->shadePopupMenu && SHADE_NONE==opts->shadeMenubars)
        opts->shadePopupMenu=false;

#ifdef __cplusplus

#if defined QT_VERSION && QT_VERSION >= 0x040000
    if(!(opts->titlebarButtons&TITLEBAR_BUTTON_ROUND))
#endif
        opts->titlebarButtonAppearance=MODIFY_AGUA(opts->titlebarButtonAppearance);
    opts->dwtAppearance=MODIFY_AGUA(opts->dwtAppearance);
#endif
    if(opts->windowBorder&WINDOW_BORDER_USE_MENUBAR_COLOR_FOR_TITLEBAR &&
        (opts->windowBorder&WINDOW_BORDER_BLEND_TITLEBAR || SHADE_WINDOW_BORDER==opts->shadeMenubars))
        opts->windowBorder-=WINDOW_BORDER_USE_MENUBAR_COLOR_FOR_TITLEBAR;

    if(APPEARANCE_FLAT==opts->tabAppearance)
        opts->tabAppearance=APPEARANCE_RAISED;
    if(EFFECT_NONE==opts->buttonEffect)
        opts->etchEntry=false;
    if(opts->colorSliderMouseOver &&
        (SHADE_NONE==opts->shadeSliders || SHADE_DARKEN==opts->shadeSliders))
        opts->colorSliderMouseOver=false;
#endif /* ndef CONFIG_DIALOG */

    if(LINE_1DOT==opts->toolbarSeparators)
        opts->toolbarSeparators=LINE_DOTS;
}

#ifdef __cplusplus
bool qtcReadConfig(const QString &file, Options *opts, Options *defOpts, bool checkImages)
#else
bool qtcReadConfig(const char *file, Options *opts, Options *defOpts)
#endif
{
#ifdef __cplusplus
    if(file.isEmpty())
    {
        const char *env=getenv("QTCURVE_CONFIG_FILE");

        if(NULL!=env)
            return qtcReadConfig(env, opts, defOpts);
        else
        {
            const char *cfgDir=qtcConfDir();

            if(cfgDir)
            {
                QString filename(QFile::decodeName(cfgDir)+CONFIG_FILE);

                if(!QFile::exists(filename))
                    filename=QFile::decodeName(cfgDir)+"../"OLD_CONFIG_FILE;
                return qtcReadConfig(filename, opts, defOpts);
            }
        }
    }
#else
    bool checkImages=true;
    if(!file)
    {
        const char *env=getenv("QTCURVE_CONFIG_FILE");

        if(NULL!=env)
            return qtcReadConfig(env, opts, defOpts);
        else
        {
            const char *cfgDir=qtcConfDir();

            if(cfgDir)
            {
                char *filename=(char *)malloc(strlen(cfgDir)+strlen(OLD_CONFIG_FILE)+4);
                bool rv=false;

                sprintf(filename, "%s"CONFIG_FILE, cfgDir);
                if(!qtcFileExists(filename))
                    sprintf(filename, "%s../"OLD_CONFIG_FILE, cfgDir);
                rv=qtcReadConfig(filename, opts, defOpts);
                free(filename);
                return rv;
            }
        }
    }
#endif
    else
    {
// Changed by Kovid to ensure config files are never read
#ifdef __cplusplus
        QtCConfig cfg(QString(""));
#else
        GHashTable *cfg=NULL;
#endif
        if (0) {
            int     i;

            opts->version=readVersionEntry(cfg, VERSION_KEY);

#ifdef __cplusplus
            Options newOpts;

            if(defOpts)
                newOpts=*defOpts;
            else
                qtcDefaultSettings(&newOpts);

            Options *def=&newOpts;

            if(opts!=def)
                opts->customGradient=def->customGradient;

#else
            Options newOpts;
            Options *def=&newOpts;
#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
            opts->noDlgFixApps=NULL;
#endif
            opts->noBgndGradientApps=opts->noBgndOpacityApps=opts->noMenuBgndOpacityApps=opts->noBgndImageApps=opts->noMenuStripeApps=NULL;
            for(i=0; i<NUM_CUSTOM_GRAD; ++i)
                opts->customGradient[i]=NULL;

            if(defOpts)
                copyOpts(defOpts, &newOpts);
            else
                qtcDefaultSettings(&newOpts);
            if(opts!=def)
                copyGradients(def, opts);
#endif

            /* Check if the config file expects old default values... */
            if(opts->version<MAKE_VERSION(1, 6))
            {
                bool framelessGroupBoxes=readBoolEntry(cfg, "framelessGroupBoxes", true),
                     groupBoxLine=readBoolEntry(cfg, "groupBoxLine", true);
                opts->groupBox=framelessGroupBoxes ? (groupBoxLine ? FRAME_LINE : FRAME_NONE) : FRAME_PLAIN;
                opts->gbLabel=framelessGroupBoxes ? GB_LBL_BOLD : 0;
                opts->gbFactor=0;
                def->focus=FOCUS_LINE;
                def->crHighlight=3;
            }
            else
            {
                CFG_READ_FRAME(groupBox)
                CFG_READ_INT(gbLabel)
            }

            if(opts->version<MAKE_VERSION(1, 5))
            {
                opts->windowBorder=
                    (readBoolEntry(cfg, "colorTitlebarOnly", def->windowBorder&WINDOW_BORDER_COLOR_TITLEBAR_ONLY)
                                                                ? WINDOW_BORDER_COLOR_TITLEBAR_ONLY : 0)+
                    (readBoolEntry(cfg, "titlebarBorder", def->windowBorder&WINDOW_BORDER_ADD_LIGHT_BORDER)
                                                                ? WINDOW_BORDER_ADD_LIGHT_BORDER : 0)+
                    (readBoolEntry(cfg, "titlebarBlend", def->windowBorder&WINDOW_BORDER_BLEND_TITLEBAR)
                                                                ? WINDOW_BORDER_BLEND_TITLEBAR : 0);
            }
            else
                CFG_READ_INT(windowBorder);

            if(opts->version<MAKE_VERSION(1, 7))
            {
                opts->windowBorder|=WINDOW_BORDER_FILL_TITLEBAR;
                def->square=SQUARE_POPUP_MENUS;
            }

            if(opts->version<MAKE_VERSION(1, 4))
            {
                opts->square=
                    (readBoolEntry(cfg, "squareLvSelection", def->square&SQUARE_LISTVIEW_SELECTION) ? SQUARE_LISTVIEW_SELECTION : SQUARE_NONE)+
                    (readBoolEntry(cfg, "squareScrollViews", def->square&SQUARE_SCROLLVIEW) ? SQUARE_SCROLLVIEW : SQUARE_NONE)+
                    (readBoolEntry(cfg, "squareProgress", def->square&SQUARE_PROGRESS) ? SQUARE_PROGRESS : SQUARE_NONE)+
                    (readBoolEntry(cfg, "squareEntry", def->square&SQUARE_ENTRY)? SQUARE_ENTRY : SQUARE_NONE);
            }
            else
                CFG_READ_INT(square)
            if(opts->version<MAKE_VERSION(1, 7))
            {
                def->tbarBtns=TBTN_STANDARD;
                opts->thin=(readBoolEntry(cfg, "thinnerMenuItems", def->thin&THIN_MENU_ITEMS) ? THIN_MENU_ITEMS : 0)+
                           (readBoolEntry(cfg, "thinnerBtns", def->thin&THIN_BUTTONS) ? THIN_BUTTONS : 0);
            }
            else
            {
                CFG_READ_INT(thin)
            }
            if(opts->version<MAKE_VERSION(1, 6))
                opts->square|=SQUARE_TOOLTIPS;
            if(opts->version<MAKE_VERSION3(1, 6, 1))
                opts->square|=SQUARE_POPUP_MENUS;
            if(opts->version<MAKE_VERSION(1, 2))
                def->crSize=CR_SMALL_SIZE;
            if(opts->version<MAKE_VERSION(1, 0))
            {
                def->roundAllTabs=false;
                def->smallRadio=false;
                def->splitters=LINE_FLAT;
                def->handles=LINE_SUNKEN;
                def->crHighlight=0;
#ifdef __cplusplus
                def->dwtAppearance=APPEARANCE_FLAT;
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
                def->dwtSettings=0;
#endif
#endif
                def->inactiveTitlebarAppearance=APPEARANCE_CUSTOM2;
            }
            if(opts->version<MAKE_VERSION(0, 67))
                def->doubleGtkComboArrow=false;
            if(opts->version<MAKE_VERSION(0, 66))
            {
                def->menuStripeAppearance=APPEARANCE_GRADIENT;
                def->etchEntry=true;
                def->gtkScrollViews=false;
                def->thinSbarGroove=false;
#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
                def->titlebarButtons=TITLEBAR_BUTTON_HOVER_FRAME;
                def->titlebarIcon=TITLEBAR_ICON_MENU_BUTTON;
#endif
            }
            if(opts->version<MAKE_VERSION(0, 65))
            {
                def->tabMouseOver=TAB_MO_BOTTOM;
                def->activeTabAppearance=APPEARANCE_FLAT;
                def->unifySpin=false;
                def->unifyCombo=false;
                def->borderTab=false;
                def->thin=0;
            }
            if(opts->version<MAKE_VERSION(0, 63))
            {
                def->tabMouseOver=TAB_MO_TOP;
                def->sliderStyle=SLIDER_TRIANGULAR;
#ifdef __cplusplus
                def->titlebarAlignment=ALIGN_LEFT;
#endif
            }
            if(opts->version<MAKE_VERSION(0, 62))
            {
                def->titlebarAppearance=APPEARANCE_GRADIENT;
                def->inactiveTitlebarAppearance=APPEARANCE_GRADIENT;
                def->round=ROUND_FULL;
                def->appearance=APPEARANCE_DULL_GLASS;
                def->sliderAppearance=APPEARANCE_DULL_GLASS;
                def->menuitemAppearance=APPEARANCE_DULL_GLASS;
                def->useHighlightForMenu=true;
                def->tabAppearance=APPEARANCE_GRADIENT;
                def->highlightFactor=5;
                def->toolbarSeparators=LINE_NONE;
                def->menubarAppearance=APPEARANCE_SOFT_GRADIENT;
                def->crButton=false;
                def->customShades[0]=0;
                def->stripedProgress=STRIPE_DIAGONAL;
                def->sunkenAppearance=APPEARANCE_INVERTED;
                def->focus=FOCUS_FILLED;
            }
            if(opts->version<MAKE_VERSION(0, 61))
            {
                def->coloredMouseOver=MO_PLASTIK;
                def->buttonEffect=EFFECT_NONE;
                def->defBtnIndicator=IND_TINT;
                def->vArrows=false;
                def->toolbarAppearance=APPEARANCE_GRADIENT;
                def->focus=FOCUS_STANDARD;
                def->selectionAppearance=APPEARANCE_FLAT;
                def->flatSbarButtons=false;
                def->comboSplitter=true;
                def->handles=LINE_DOTS;
                def->lighterPopupMenuBgnd=15;
                def->activeTabAppearance=APPEARANCE_GRADIENT;
                def->gbLabel=GB_LBL_BOLD;
                def->groupBox=FRAME_NONE;
                def->shadeSliders=SHADE_BLEND_SELECTED;
                def->progressGrooveColor=ECOLOR_BASE;
                def->shadeMenubars=SHADE_DARKEN;
                opts->highlightTab=true;
            }

            if(opts!=def)
            {
                opts->customShades[0]=0;
                opts->customAlphas[0]=0;
                if(USE_CUSTOM_SHADES(*def))
                    memcpy(opts->customShades, def->customShades, sizeof(double)*NUM_STD_SHADES);
            }

            CFG_READ_INT(gbFactor)
            CFG_READ_INT(passwordChar)
            CFG_READ_ROUND(round)
            CFG_READ_INT(highlightFactor)
            CFG_READ_INT(menuDelay)
            CFG_READ_INT(sliderWidth)
            CFG_READ_INT(tabBgnd)
            CFG_READ_TB_BORDER(toolbarBorders)
            CFG_READ_APPEARANCE(appearance, APP_ALLOW_BASIC)
            if(opts->version<MAKE_VERSION(1, 8))
            {
                opts->tbarBtnAppearance=APPEARANCE_NONE;
                opts->tbarBtnEffect=EFFECT_NONE;
            }
            else
            {
                CFG_READ_APPEARANCE(tbarBtnAppearance, APP_ALLOW_NONE)
                CFG_READ_EFFECT(tbarBtnEffect);
            }
            CFG_READ_APPEARANCE_PIXMAP(bgndAppearance, APP_ALLOW_STRIPED, &(opts->bgndPixmap), checkImages)
            CFG_READ_GRAD_TYPE(bgndGrad)
            CFG_READ_GRAD_TYPE(menuBgndGrad)
            CFG_READ_INT_BOOL(lighterPopupMenuBgnd, def->lighterPopupMenuBgnd)
            CFG_READ_APPEARANCE_PIXMAP(menuBgndAppearance, APP_ALLOW_STRIPED, &(opts->menuBgndPixmap), checkImages)

            if(APPEARANCE_FLAT==opts->menuBgndAppearance && 0==opts->lighterPopupMenuBgnd && opts->version<MAKE_VERSION(1, 7))
                opts->menuBgndAppearance=APPEARANCE_RAISED;

#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
            CFG_READ_BOOL(fixParentlessDialogs)
            CFG_READ_STRING_LIST(noDlgFixApps)
#endif
            CFG_READ_STRIPE(stripedProgress)
            CFG_READ_SLIDER(sliderStyle)
            CFG_READ_BOOL(animatedProgress)
            CFG_READ_BOOL(embolden)
            CFG_READ_DEF_BTN(defBtnIndicator)
            CFG_READ_LINE(sliderThumbs)
            CFG_READ_LINE(handles)
            CFG_READ_BOOL(highlightTab)
            CFG_READ_INT_BOOL(colorSelTab, DEF_COLOR_SEL_TAB_FACTOR)
            CFG_READ_BOOL(roundAllTabs)
            CFG_READ_TAB_MO(tabMouseOver)
            CFG_READ_SHADE(shadeSliders, true, false, &opts->customSlidersColor)
            CFG_READ_SHADE(shadeMenubars, true, false, &opts->customMenubarsColor)
            CFG_READ_SHADE(shadeCheckRadio, false, false, &opts->customCheckRadioColor)
            CFG_READ_SHADE(sortedLv, true, false, &opts->customSortedLvColor)
            CFG_READ_SHADE(crColor,  true, false, &opts->customCrBgndColor)
            CFG_READ_SHADE(progressColor, false, false, &opts->customProgressColor)
            CFG_READ_APPEARANCE(menubarAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(menuitemAppearance, APP_ALLOW_FADE)
            CFG_READ_APPEARANCE(toolbarAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(selectionAppearance, APP_ALLOW_BASIC)
#ifdef __cplusplus
            CFG_READ_APPEARANCE(dwtAppearance, APP_ALLOW_BASIC)
#endif
            CFG_READ_LINE(toolbarSeparators)
            CFG_READ_LINE(splitters)
            CFG_READ_BOOL(customMenuTextColor)
            CFG_READ_MOUSE_OVER(coloredMouseOver)
            CFG_READ_BOOL(menubarMouseOver)
            CFG_READ_BOOL(useHighlightForMenu)
            CFG_READ_BOOL(shadeMenubarOnlyWhenActive)
            CFG_READ_TBAR_BTN(tbarBtns)
            if(opts->version<MAKE_VERSION(0, 63))
            {
                if(IS_BLACK(opts->customSlidersColor))
                    CFG_READ_COLOR(customSlidersColor)
                if(IS_BLACK(opts->customMenubarsColor))
                    CFG_READ_COLOR(customMenubarsColor)
                if(IS_BLACK(opts->customCheckRadioColor))
                    CFG_READ_COLOR(customCheckRadioColor)
            }
            CFG_READ_COLOR(customMenuSelTextColor)
            CFG_READ_COLOR(customMenuNormTextColor)
            CFG_READ_SCROLLBAR(scrollbarType)
            CFG_READ_EFFECT(buttonEffect)
            CFG_READ_APPEARANCE(lvAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(tabAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(activeTabAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(sliderAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(progressAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(progressGrooveAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(grooveAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(sunkenAppearance, APP_ALLOW_BASIC)
            CFG_READ_APPEARANCE(sbarBgndAppearance, APP_ALLOW_BASIC)
            if(opts->version<MAKE_VERSION(1, 6))
                opts->tooltipAppearance=APPEARANCE_FLAT;
            else
            {
                CFG_READ_APPEARANCE(tooltipAppearance, APP_ALLOW_BASIC)
            }

            if(opts->version<MAKE_VERSION(0, 63))
                opts->sliderFill=IS_FLAT(opts->appearance) ? opts->grooveAppearance : APPEARANCE_GRADIENT;
            else
            {
                CFG_READ_APPEARANCE(sliderFill, APP_ALLOW_BASIC)
            }
            CFG_READ_ECOLOR(progressGrooveColor)
            CFG_READ_FOCUS(focus)
            CFG_READ_BOOL(lvButton)
            CFG_READ_LV_LINES(lvLines)
            CFG_READ_BOOL(drawStatusBarFrames)
            CFG_READ_BOOL(fillSlider)
            CFG_READ_BOOL(roundMbTopOnly)
            CFG_READ_BOOL(borderMenuitems)
            CFG_READ_BOOL(darkerBorders)
            CFG_READ_BOOL(vArrows)
            CFG_READ_BOOL(xCheck)
            CFG_READ_BOOL(fadeLines)
            CFG_READ_GLOW(glowProgress)
            CFG_READ_BOOL(colorMenubarMouseOver)
            CFG_READ_INT_BOOL(crHighlight, opts->highlightFactor)
            CFG_READ_BOOL(crButton)
            CFG_READ_BOOL(smallRadio)
            CFG_READ_BOOL(fillProgress)
            CFG_READ_BOOL(comboSplitter)
            CFG_READ_BOOL(highlightScrollViews)
            CFG_READ_BOOL(etchEntry)
            CFG_READ_INT_BOOL(splitterHighlight, opts->highlightFactor)
            CFG_READ_INT(crSize)
            CFG_READ_BOOL(flatSbarButtons)
            CFG_READ_BOOL(borderSbarGroove)
            CFG_READ_BOOL(borderProgress)
            CFG_READ_BOOL(popupBorder)
            CFG_READ_BOOL(unifySpinBtns)
            CFG_READ_BOOL(unifySpin)
            CFG_READ_BOOL(unifyCombo)
            CFG_READ_BOOL(borderTab)
            CFG_READ_BOOL(borderInactiveTab)
            CFG_READ_BOOL(thinSbarGroove)
            CFG_READ_BOOL(colorSliderMouseOver)
            CFG_READ_BOOL(menuIcons)
            CFG_READ_BOOL(forceAlternateLvCols)
            CFG_READ_BOOL(invertBotTab)
            CFG_READ_INT_BOOL(menubarHiding, HIDE_KEYBOARD)
            CFG_READ_INT_BOOL(statusbarHiding, HIDE_KEYBOARD)
            CFG_READ_BOOL(boldProgress)
            CFG_READ_BOOL(coloredTbarMo)
            CFG_READ_BOOL(borderSelection)
            CFG_READ_BOOL(stripedSbar)
            CFG_READ_INT_BOOL(windowDrag, WM_DRAG_MENUBAR)
            CFG_READ_BOOL(shadePopupMenu)
            CFG_READ_BOOL(hideShortcutUnderline)

#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
            CFG_READ_BOOL(stdBtnSizes)
            CFG_READ_INT(titlebarButtons)
            CFG_READ_TB_ICON(titlebarIcon)
#endif
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
            CFG_READ_BOOL(xbar)
            CFG_READ_INT(dwtSettings)
#endif
            CFG_READ_INT(bgndOpacity)
            CFG_READ_INT(menuBgndOpacity)
            CFG_READ_INT(dlgOpacity)
            CFG_READ_SHADE(menuStripe, true, true, &opts->customMenuStripeColor)
            CFG_READ_APPEARANCE(menuStripeAppearance, APP_ALLOW_BASIC)
            if(opts->version<MAKE_VERSION(0, 63) && IS_BLACK(opts->customMenuStripeColor))
                CFG_READ_COLOR(customMenuStripeColor)
            CFG_READ_SHADE(comboBtn, true, false, &opts->customComboBtnColor);
            CFG_READ_BOOL(gtkScrollViews)
            CFG_READ_BOOL(doubleGtkComboArrow)
            CFG_READ_BOOL(stdSidebarButtons)
            CFG_READ_BOOL(toolbarTabs)
            CFG_READ_BOOL(gtkComboMenus)
#ifdef __cplusplus
            CFG_READ_ALIGN(titlebarAlignment)
            CFG_READ_EFFECT(titlebarEffect)
            CFG_READ_BOOL(centerTabText)
/*
#else
            CFG_READ_BOOL(setDialogButtonOrder)
*/
#endif
#if !defined __cplusplus || defined CONFIG_DIALOG
            CFG_READ_INT(expanderHighlight)
            CFG_READ_BOOL(mapKdeIcons)
#endif
#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000)) || !defined __cplusplus
            CFG_READ_BOOL(gtkButtonOrder)
#endif
#if !defined __cplusplus || (defined CONFIG_DIALOG && defined QT_VERSION && (QT_VERSION >= 0x040000))
            CFG_READ_BOOL(reorderGtkButtons)
#endif
            CFG_READ_APPEARANCE(titlebarAppearance, APP_ALLOW_NONE)
            CFG_READ_APPEARANCE(inactiveTitlebarAppearance, APP_ALLOW_NONE)

            if(APPEARANCE_BEVELLED==opts->titlebarAppearance)
                opts->titlebarAppearance=APPEARANCE_GRADIENT;
            else if(APPEARANCE_RAISED==opts->titlebarAppearance)
                opts->titlebarAppearance=APPEARANCE_FLAT;
            if((opts->windowBorder&WINDOW_BORDER_BLEND_TITLEBAR) && !(opts->windowBorder&WINDOW_BORDER_COLOR_TITLEBAR_ONLY))
                opts->windowBorder-=WINDOW_BORDER_BLEND_TITLEBAR;
            if(APPEARANCE_BEVELLED==opts->inactiveTitlebarAppearance)
                opts->inactiveTitlebarAppearance=APPEARANCE_GRADIENT;
            else if(APPEARANCE_RAISED==opts->inactiveTitlebarAppearance)
                opts->inactiveTitlebarAppearance=APPEARANCE_FLAT;
#ifdef __cplusplus
            CFG_READ_APPEARANCE(titlebarButtonAppearance, APP_ALLOW_BASIC)
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
            if(opts->xbar && opts->menubarHiding)
                opts->xbar=false;
#endif
#endif
            CFG_READ_SHADING(shading)
            CFG_READ_IMAGE(bgndImage)
            CFG_READ_IMAGE(menuBgndImage)
            CFG_READ_STRING_LIST(noMenuStripeApps)
#if !defined __cplusplus || (defined QT_VERSION && (QT_VERSION >= 0x040000))
            CFG_READ_STRING_LIST(noBgndGradientApps)
            CFG_READ_STRING_LIST(noBgndOpacityApps)
            CFG_READ_STRING_LIST(noMenuBgndOpacityApps)
            CFG_READ_STRING_LIST(noBgndImageApps)
#ifdef CONFIG_DIALOG
            if(opts->version<MAKE_VERSION3(1, 7, 2))
                opts->noMenuBgndOpacityApps << "gtk";
#endif
#endif
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
            CFG_READ_STRING_LIST(menubarApps)
            CFG_READ_STRING_LIST(statusbarApps)
            CFG_READ_STRING_LIST(useQtFileDialogApps)
            CFG_READ_STRING_LIST(windowDragWhiteList)
            CFG_READ_STRING_LIST(windowDragBlackList)
#endif
            readDoubleList(cfg, "customShades", opts->customShades, NUM_STD_SHADES);
            readDoubleList(cfg, "customAlphas", opts->customAlphas, NUM_STD_ALPHAS);

#ifdef __cplusplus
#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
            if(opts->titlebarButtons&TITLEBAR_BUTTON_COLOR || opts->titlebarButtons&TITLEBAR_BUTTON_ICON_COLOR)
            {
#if (defined QT_VERSION && (QT_VERSION >= 0x040000))
                QStringList cols(readStringEntry(cfg, "titlebarButtonColors").split(',', QString::SkipEmptyParts));
#else
                QStringList cols(QStringList::split(',', readStringEntry(cfg, "titlebarButtonColors")));
#endif
                if(cols.count() && 0==(cols.count()%NUM_TITLEBAR_BUTTONS) && cols.count()<=(NUM_TITLEBAR_BUTTONS*3))
                {
                    QStringList::ConstIterator it(cols.begin()),
                                               end(cols.end());

                    for(int i=0; it!=end; ++it, ++i)
                    {
                        QColor col;
                        qtcSetRgb(&col, TO_LATIN1((*it)));
                        opts->titlebarButtonColors[i]=col;
                    }
                    if(cols.count()<(NUM_TITLEBAR_BUTTONS+1))
                        opts->titlebarButtons&=~TITLEBAR_BUTTON_ICON_COLOR;
                }
                else
                {
                    opts->titlebarButtons&=~TITLEBAR_BUTTON_COLOR;
                    opts->titlebarButtons&=~TITLEBAR_BUTTON_ICON_COLOR;
                }
            }
#endif

            for(i=APPEARANCE_CUSTOM1; i<(APPEARANCE_CUSTOM1+NUM_CUSTOM_GRAD); ++i)
            {
                QString gradKey;

                gradKey.sprintf("customgradient%d", (i-APPEARANCE_CUSTOM1)+1);

#if (defined QT_VERSION && (QT_VERSION >= 0x040000))
                QStringList vals(readStringEntry(cfg, gradKey).split(',', QString::SkipEmptyParts));
#else
                QStringList vals(QStringList::split(',', readStringEntry(cfg, gradKey)));
#endif

                if(vals.size())
                    opts->customGradient.erase((EAppearance)i);

                if(vals.size()>=5)
                {
                    QStringList::ConstIterator it(vals.begin()),
                                               end(vals.end());
                    bool                       ok(true),
                                               haveAlpha(false);
                    Gradient                   grad;
                    int                        j;

                    grad.border=toGradientBorder(TO_LATIN1((*it)), &haveAlpha);
                    ok=vals.size()%(haveAlpha ? 3 : 2);

                    for(++it, j=0; it!=end && ok; ++it, ++j)
                    {
                        double pos=(*it).toDouble(&ok),
                               val=ok ? (*(++it)).toDouble(&ok) : 0.0,
                               alpha=haveAlpha && ok ? (*(++it)).toDouble(&ok) : 1.0;

                        ok=ok && (pos>=0 && pos<=1.0) && (val>=0.0 && val<=2.0) && (alpha>=0.0 && alpha<=1.0);

                        if(ok)
                            grad.stops.insert(GradientStop(pos, val, alpha));
                    }

                    if(ok)
                    {
                        opts->customGradient[(EAppearance)i]=grad;
                        opts->customGradient[(EAppearance)i].stops=grad.stops.fix();
                    }
                }
            }
#else
            for(i=0; i<NUM_CUSTOM_GRAD; ++i)
            {
                char gradKey[18];
                char *str;

                sprintf(gradKey, "customgradient%d", i+1);
                if((str=readStringEntry(cfg, gradKey)))
                {
                    int j,
                        comma=0;

                    for(j=0; str[j]; ++j)
                        if(','==str[j])
                            comma++;

                    if(comma && opts->customGradient[i])
                    {
                        if(opts->customGradient[i]->stops)
                            free(opts->customGradient[i]->stops);
                        free(opts->customGradient[i]);
                        opts->customGradient[i]=0L;
                    }

                    if(comma>=4)
                    {
                        char *c=strchr(str, ',');

                        if(c)
                        {
                            bool            haveAlpha=false;
                            EGradientBorder border=toGradientBorder(str, &haveAlpha);
                            int             parts=haveAlpha ? 3 : 2;
                            bool            ok=0==comma%parts;

                            *c='\0';

                            if(ok)
                            {
                                opts->customGradient[i]=malloc(sizeof(Gradient));
                                opts->customGradient[i]->numStops=comma/parts;
                                opts->customGradient[i]->stops=malloc(sizeof(GradientStop) * opts->customGradient[i]->numStops);
                                opts->customGradient[i]->border=border;
                                str=c+1;
                                for(j=0; j<comma && str && ok; j+=parts)
                                {
                                    int stop=j/parts;
                                    c=strchr(str, ',');

                                    if(c)
                                    {
                                        *c='\0';
                                        opts->customGradient[i]->stops[stop].pos=g_ascii_strtod(str, NULL);
                                        str=c+1;
                                        c=str ? strchr(str, ',') : 0L;

                                        if(c || str)
                                        {
                                            if(c)
                                                *c='\0';
                                            opts->customGradient[i]->stops[stop].val=g_ascii_strtod(str, NULL);
                                            str=c ? c+1 : c;
                                            if(haveAlpha)
                                            {
                                                c=str ? strchr(str, ',') : 0L;
                                                if(c || str)
                                                {
                                                    if(c)
                                                        *c='\0';
                                                    opts->customGradient[i]->stops[stop].alpha=g_ascii_strtod(str, NULL);
                                                    str=c ? c+1 : c;
                                                }
                                                else
                                                    ok=false;
                                            }
                                            else
                                                opts->customGradient[i]->stops[stop].alpha=1.0;
                                        }
                                        else
                                            ok=false;
                                    }
                                    else
                                        ok=false;

                                    ok=ok &&
                                       (opts->customGradient[i]->stops[stop].pos>=0 && opts->customGradient[i]->stops[stop].pos<=1.0) &&
                                       (opts->customGradient[i]->stops[stop].val>=0.0 && opts->customGradient[i]->stops[stop].val<=2.0) &&
                                       (opts->customGradient[i]->stops[stop].alpha>=0.0 && opts->customGradient[i]->stops[stop].alpha<=1.0);
                                }

                                if(ok)
                                {
                                    int addStart=0,
                                        addEnd=0;
                                    if(opts->customGradient[i]->stops[0].pos>0.001)
                                        addStart=1;
                                    if(opts->customGradient[i]->stops[opts->customGradient[i]->numStops-1].pos<0.999)
                                        addEnd=1;

                                    if(addStart || addEnd)
                                    {
                                        int          newSize=opts->customGradient[i]->numStops+addStart+addEnd;
                                        GradientStop *stops=malloc(sizeof(GradientStop) * newSize);

                                        if(addStart)
                                        {
                                            stops[0].pos=0.0;
                                            stops[0].val=1.0;
                                            stops[0].alpha=1.0;
                                        }
                                        memcpy(&stops[addStart], opts->customGradient[i]->stops, sizeof(GradientStop) * opts->customGradient[i]->numStops);
                                        if(addEnd)
                                        {
                                            stops[opts->customGradient[i]->numStops+addStart].pos=1.0;
                                            stops[opts->customGradient[i]->numStops+addStart].val=1.0;
                                            stops[opts->customGradient[i]->numStops+addStart].alpha=1.0;
                                        }
                                        opts->customGradient[i]->numStops=newSize;
                                        free(opts->customGradient[i]->stops);
                                        opts->customGradient[i]->stops=stops;
                                    }
                                }
                                else
                                {
                                    free(opts->customGradient[i]->stops);
                                    free(opts->customGradient[i]);
                                    opts->customGradient[i]=0L;
                                }
                            }
                        }
                    }
                }
            }
#endif

            qtcCheckConfig(opts);

#ifndef __cplusplus
            if(!defOpts)
            {
                int i;

                for(i=0; i<NUM_CUSTOM_GRAD; ++i)
                    if(def->customGradient[i])
                        free(def->customGradient[i]);
            }
            releaseConfig(cfg);
            freeOpts(defOpts);
#endif
            return true;
        }
        else
        {
#ifdef __cplusplus
            if(defOpts)
                *opts=*defOpts;
            else
                qtcDefaultSettings(opts);
#else
            if(defOpts)
                copyOpts(defOpts, opts);
            else
                qtcDefaultSettings(opts);
#endif
            return true;
        }
    }

    return false;
}

static bool fileExists(const char *path)
{
    struct stat info;

    return 0==lstat(path, &info) && (info.st_mode&S_IFMT)==S_IFREG;
}

static const char * getSystemConfigFile()
{
    static const char * constFiles[]={ /*"/etc/qt4/"OLD_CONFIG_FILE, "/etc/qt3/"OLD_CONFIG_FILE, "/etc/qt/"OLD_CONFIG_FILE,*/ "/etc/"OLD_CONFIG_FILE, NULL };

    int i;

    for(i=0; constFiles[i]; ++i)
        if(fileExists(constFiles[i]))
            return constFiles[i];
    return NULL;
}

void qtcDefaultSettings(Options *opts)
{
    /* Set hard-coded defaults... */
#ifndef __cplusplus
    int i;

    for(i=0; i<NUM_CUSTOM_GRAD; ++i)
        opts->customGradient[i]=0L;
    opts->customGradient[APPEARANCE_CUSTOM1]=malloc(sizeof(Gradient));
    opts->customGradient[APPEARANCE_CUSTOM2]=malloc(sizeof(Gradient));
    qtcSetupGradient(opts->customGradient[APPEARANCE_CUSTOM1], GB_3D,3,0.0,1.2,0.5,1.0,1.0,1.0);
    qtcSetupGradient(opts->customGradient[APPEARANCE_CUSTOM2], GB_3D,3,0.0,0.9,0.5,1.0,1.0,1.0);
#else
    // Setup titlebar gradients...
    qtcSetupGradient(&(opts->customGradient[APPEARANCE_CUSTOM1]), GB_3D,3,0.0,1.2,0.5,1.0,1.0,1.0);
    qtcSetupGradient(&(opts->customGradient[APPEARANCE_CUSTOM2]), GB_3D,3,0.0,0.9,0.5,1.0,1.0,1.0);
#endif
    opts->customShades[0]=1.16;
    opts->customShades[1]=1.07;
    opts->customShades[2]=0.9;
    opts->customShades[3]=0.78;
    opts->customShades[4]=0.84;
    opts->customShades[5]=0.75;
    opts->customAlphas[0]=0;
    opts->contrast=7;
    opts->passwordChar=0x25CF;
    opts->gbFactor=DEF_GB_FACTOR;
    opts->highlightFactor=DEFAULT_HIGHLIGHT_FACTOR;
    opts->crHighlight=DEFAULT_CR_HIGHLIGHT_FACTOR;
    opts->splitterHighlight=DEFAULT_SPLITTER_HIGHLIGHT_FACTOR;
    opts->crSize=CR_LARGE_SIZE;
    opts->menuDelay=DEFAULT_MENU_DELAY;
    opts->sliderWidth=DEFAULT_SLIDER_WIDTH;
    opts->selectionAppearance=APPEARANCE_HARSH_GRADIENT;
    opts->fadeLines=true;
    opts->glowProgress=GLOW_NONE;
#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000)) || !defined __cplusplus
    opts->round=ROUND_EXTRA;
    opts->gtkButtonOrder=false;
#else
    opts->round=ROUND_FULL;
#endif
#ifdef __cplusplus
    opts->dwtAppearance=APPEARANCE_CUSTOM1;
#endif
#if !defined __cplusplus || (defined CONFIG_DIALOG && defined QT_VERSION && (QT_VERSION >= 0x040000))
    opts->reorderGtkButtons=false;
#endif
    opts->bgndImage.type=IMG_NONE;
    opts->bgndImage.width=opts->bgndImage.height=0;
    opts->bgndImage.onBorder=false;
    opts->bgndImage.pos=PP_TR;
    opts->menuBgndImage.type=IMG_NONE;
    opts->menuBgndImage.width=opts->menuBgndImage.height=0;
    opts->menuBgndImage.onBorder=false;
    opts->menuBgndImage.pos=PP_TR;
    opts->lighterPopupMenuBgnd=DEF_POPUPMENU_LIGHT_FACTOR;
    opts->tabBgnd=DEF_TAB_BGND;
    opts->animatedProgress=false;
    opts->stripedProgress=STRIPE_NONE;
    opts->sliderStyle=SLIDER_PLAIN;
    opts->highlightTab=false;
    opts->colorSelTab=0;
    opts->roundAllTabs=true;
    opts->tabMouseOver=TAB_MO_GLOW;
    opts->embolden=false;
    opts->bgndGrad=GT_HORIZ;
    opts->menuBgndGrad=GT_HORIZ;
    opts->appearance=APPEARANCE_SOFT_GRADIENT;
    opts->tbarBtnAppearance=APPEARANCE_NONE;
    opts->tbarBtnEffect=EFFECT_NONE;
    opts->bgndAppearance=APPEARANCE_FLAT;
    opts->menuBgndAppearance=APPEARANCE_FLAT;
    opts->lvAppearance=APPEARANCE_BEVELLED;
    opts->tabAppearance=APPEARANCE_SOFT_GRADIENT;
    opts->activeTabAppearance=APPEARANCE_SOFT_GRADIENT;
    opts->sliderAppearance=APPEARANCE_SOFT_GRADIENT;
    opts->menubarAppearance=APPEARANCE_FLAT;
    opts->menuitemAppearance=APPEARANCE_FADE;
    opts->toolbarAppearance=APPEARANCE_FLAT;
    opts->progressAppearance=APPEARANCE_DULL_GLASS;
    opts->progressGrooveAppearance=APPEARANCE_INVERTED;
    opts->progressGrooveColor=ECOLOR_DARK;
    opts->grooveAppearance=APPEARANCE_INVERTED;
    opts->sunkenAppearance=APPEARANCE_SOFT_GRADIENT;
    opts->sbarBgndAppearance=APPEARANCE_FLAT;
    opts->tooltipAppearance=APPEARANCE_GRADIENT;
    opts->sliderFill=APPEARANCE_GRADIENT;
    opts->defBtnIndicator=IND_GLOW;
    opts->sliderThumbs=LINE_FLAT;
    opts->handles=LINE_1DOT;
    opts->shadeSliders=SHADE_NONE;
    opts->shadeMenubars=SHADE_NONE;
    opts->shadeCheckRadio=SHADE_NONE;
    opts->sortedLv=SHADE_NONE;
    opts->toolbarBorders=TB_NONE;
    opts->toolbarSeparators=LINE_SUNKEN;
    opts->splitters=LINE_1DOT;
#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
    opts->fixParentlessDialogs=false;
#ifdef __cplusplus
    opts->noDlgFixApps << "kate" << "plasma" << "plasma-desktop" << "plasma-netbook";
#else
    opts->noDlgFixApps=NULL;
#endif
#endif
    opts->customMenuTextColor=false;
    opts->coloredMouseOver=MO_GLOW;
    opts->menubarMouseOver=true;
    opts->useHighlightForMenu=false;
    opts->shadeMenubarOnlyWhenActive=false;
    opts->thin=THIN_BUTTONS;
    opts->tbarBtns=TBTN_STANDARD;
#ifdef _WIN32
    opts->scrollbarType=SCROLLBAR_WINDOWS;
#elif defined __APPLE__
    opts->scrollbarType=SCROLLBAR_NONE;
#else
    opts->scrollbarType=SCROLLBAR_KDE;
#endif
    opts->buttonEffect=EFFECT_SHADOW;
    opts->focus=FOCUS_GLOW;
    opts->lvButton=false;
    opts->lvLines=false; /*LV_NONE;*/
    opts->drawStatusBarFrames=false;
    opts->fillSlider=true;
    opts->roundMbTopOnly=true;
    opts->borderMenuitems=false;
    opts->darkerBorders=false;
    opts->vArrows=true;
    opts->xCheck=false;
    opts->colorMenubarMouseOver=true;
    opts->crButton=true;
    opts->crColor=SHADE_NONE;
    opts->progressColor=SHADE_SELECTED;
    opts->smallRadio=true;
    opts->fillProgress=true;
    opts->comboSplitter=false;
    opts->highlightScrollViews=false;
    opts->etchEntry=false;
    opts->flatSbarButtons=true;
    opts->borderSbarGroove=true;
    opts->borderProgress=true;
    opts->popupBorder=true;
    opts->unifySpinBtns=false;
    opts->unifySpin=true;
    opts->unifyCombo=true;
    opts->borderTab=true;
    opts->borderInactiveTab=false;
    opts->thinSbarGroove=true;
    opts->colorSliderMouseOver=false;
    opts->menuIcons=true;
    opts->forceAlternateLvCols=false;
    opts->invertBotTab=true;
    opts->menubarHiding=HIDE_NONE;
    opts->statusbarHiding=HIDE_NONE;
    opts->boldProgress=true;
    opts->coloredTbarMo=false;
    opts->borderSelection=false;
    opts->square=SQUARE_POPUP_MENUS|SQUARE_TOOLTIPS;
    opts->stripedSbar=false;
    opts->windowDrag=WM_DRAG_NONE;
    opts->shadePopupMenu=false;
    opts->hideShortcutUnderline=false;
    opts->windowBorder=WINDOW_BORDER_ADD_LIGHT_BORDER|WINDOW_BORDER_FILL_TITLEBAR;
    opts->groupBox=FRAME_FADED;
    opts->gbFactor=DEF_GB_FACTOR;
    opts->gbLabel=GB_LBL_BOLD|GB_LBL_OUTSIDE;
#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
    // Changed by Kovid to always use standard button sizes 
    opts->stdBtnSizes=true;
    opts->titlebarButtons=TITLEBAR_BUTTON_ROUND|TITLEBAR_BUTTON_HOVER_SYMBOL;
    opts->titlebarIcon=TITLEBAR_ICON_NEXT_TO_TITLE;
#endif
    opts->menuStripe=SHADE_NONE;
    opts->menuStripeAppearance=APPEARANCE_DARK_INVERTED;
    opts->shading=SHADING_HSL;
    opts->gtkScrollViews=true;
    opts->comboBtn=SHADE_NONE;
    opts->doubleGtkComboArrow=true;
    opts->stdSidebarButtons=false;
    opts->toolbarTabs=false;
    opts->bgndOpacity=opts->dlgOpacity=opts->menuBgndOpacity=100;
    opts->gtkComboMenus=false;
#ifdef __cplusplus
    opts->customMenubarsColor.setRgb(0, 0, 0);
    opts->customSlidersColor.setRgb(0, 0, 0);
    opts->customMenuNormTextColor.setRgb(0, 0, 0);
    opts->customMenuSelTextColor.setRgb(0, 0, 0);
    opts->customCheckRadioColor.setRgb(0, 0, 0);
    opts->customComboBtnColor.setRgb(0, 0, 0);
    opts->customMenuStripeColor.setRgb(0, 0, 0);
    opts->customProgressColor.setRgb(0, 0, 0);
    opts->titlebarAlignment=ALIGN_FULL_CENTER;
    opts->titlebarEffect=EFFECT_SHADOW;
    opts->centerTabText=false;
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
    opts->xbar=false;
    opts->dwtSettings=DWT_BUTTONS_AS_PER_TITLEBAR|DWT_ROUND_TOP_ONLY;
    opts->menubarApps << "amarok" << "arora" << "kaffeine" << "kcalc" << "smplayer" << "VirtualBox";
    opts->statusbarApps << "kde";
    opts->useQtFileDialogApps << "googleearth-bin";
    opts->noMenuBgndOpacityApps << "inkscape" << "sonata" << "totem" << "vmware" << "vmplayer" << "gtk";
    opts->noBgndOpacityApps << "smplayer" << "kaffeine" << "dragon" << "kscreenlocker" << "inkscape" << "sonata" << "totem" << "vmware" << "vmplayer";
#endif
    opts->noMenuStripeApps << "gtk" << "soffice.bin";
#else
    opts->noBgndGradientApps=NULL;
    opts->noBgndOpacityApps=g_strsplit("inkscape,sonata,totem,vmware,vmplayer",",", -1);;
    opts->noBgndImageApps=NULL;
    opts->noMenuStripeApps=g_strsplit("gtk",",", -1);
    opts->noMenuBgndOpacityApps=g_strsplit("inkscape,sonata,totem,vmware,vmplayer,gtk",",", -1);
/*
    opts->setDialogButtonOrder=false;
*/
    opts->customMenubarsColor.red=opts->customMenubarsColor.green=opts->customMenubarsColor.blue=0;
    opts->customSlidersColor.red=opts->customSlidersColor.green=opts->customSlidersColor.blue=0;
    opts->customMenuNormTextColor.red=opts->customMenuNormTextColor.green=opts->customMenuNormTextColor.blue=0;
    opts->customMenuSelTextColor.red=opts->customMenuSelTextColor.green=opts->customMenuSelTextColor.blue=0;
    opts->customCheckRadioColor.red=opts->customCheckRadioColor.green=opts->customCheckRadioColor.blue=0;
    opts->customComboBtnColor.red=opts->customCheckRadioColor.green=opts->customCheckRadioColor.blue=0;
    opts->customMenuStripeColor.red=opts->customMenuStripeColor.green=opts->customMenuStripeColor.blue=0;
    opts->customProgressColor.red=opts->customProgressColor.green=opts->customProgressColor.blue=0;
#endif

#if !defined __cplusplus || defined CONFIG_DIALOG
    opts->mapKdeIcons=true;
    opts->expanderHighlight=DEFAULT_EXPANDER_HIGHLIGHT_FACTOR;
#endif
    opts->titlebarAppearance=APPEARANCE_CUSTOM1;
    opts->inactiveTitlebarAppearance=APPEARANCE_CUSTOM1;
#ifdef __cplusplus
    opts->titlebarButtonAppearance=APPEARANCE_GRADIENT;
#endif
    /* Read system config file... */
    {
    static const char * systemFilename=NULL;

    if(!systemFilename)
        systemFilename=getSystemConfigFile();

    if(systemFilename)
        qtcReadConfig(systemFilename, opts, opts);
    }

#if !defined CONFIG_DIALOG && defined QT_VERSION && (QT_VERSION < 0x040000)
    if(FOCUS_FILLED==opts->focus)
        opts->focus=FOCUS_FULL;
#endif
}

#ifdef CONFIG_WRITE
#include <KDE/KConfig>
#include <KDE/KConfigGroup>

static const char *toStr(EDefBtnIndicator ind)
{
    switch(ind)
    {
        case IND_NONE:
            return "none";
        case IND_FONT_COLOR:
            return "fontcolor";
        case IND_CORNER:
            return "corner";
        case IND_TINT:
            return "tint";
        case IND_GLOW:
            return "glow";
        case IND_DARKEN:
            return "darken";
        case IND_SELECTED:
            return "origselected";
        default:
            return "colored";
    }
}

static const char *toStr(ELine ind, bool dashes)
{
    switch(ind)
    {
        case LINE_1DOT:
            return "1dot";
        case LINE_DOTS:
            return "dots";
        case LINE_DASHES:
            return dashes ? "dashes" : "none";
        case LINE_NONE:
            return "none";
        case LINE_FLAT:
            return "flat";
        default:
            return "sunken";
    }
}

static const char *toStr(ETBarBorder ind)
{
    switch(ind)
    {
        case TB_DARK:
            return "dark";
        case TB_DARK_ALL:
            return "dark-all";
        case TB_LIGHT_ALL:
            return "light-all";
        case TB_NONE:
            return "none";
        default:
            return "light";
    }
}

static const char *toStr(EMouseOver mo)
{
    switch(mo)
    {
        case MO_COLORED:
            return "colored";
        case MO_COLORED_THICK:
            return "thickcolored";
        case MO_NONE:
            return "none";
        case MO_GLOW:
            return "glow";
        default:
            return "plastik";
    }
}

static QString toStr(EAppearance exp, EAppAllow allow, const QtCPixmap *pix)
{
    switch(exp)
    {
        case APPEARANCE_FLAT:
            return "flat";
        case APPEARANCE_RAISED:
            return "raised";
        case APPEARANCE_DULL_GLASS:
            return "dullglass";
        case APPEARANCE_SHINY_GLASS:
            return "shinyglass";
        case APPEARANCE_AGUA:
            return "agua";
        case APPEARANCE_SOFT_GRADIENT:
            return "soft";
        case APPEARANCE_GRADIENT:
            return "gradient";
        case APPEARANCE_HARSH_GRADIENT:
            return "harsh";
        case APPEARANCE_INVERTED:
            return "inverted";
        case APPEARANCE_DARK_INVERTED:
            return "darkinverted";
        case APPEARANCE_SPLIT_GRADIENT:
            return "splitgradient";
        case APPEARANCE_BEVELLED:
            return "bevelled";
        case APPEARANCE_FILE:
            // When savng, strip users config dir from location.
            return QLatin1String("file:")+
                    (pix->file.startsWith(qtcConfDir())
                        ? pix->file.mid(strlen(qtcConfDir())+1)
                        : pix->file);
        case APPEARANCE_FADE:
            switch(allow)
            {
                case APP_ALLOW_BASIC: // Should not get here!
                case APP_ALLOW_FADE:
                    return "fade";
                case APP_ALLOW_STRIPED:
                    return "striped";
                case APP_ALLOW_NONE:
                    return "none";
            }
        default:
        {
            QString app;

            app.sprintf("customgradient%d", (exp-APPEARANCE_CUSTOM1)+1);
            return app;
        }
    }
}

static QString toStr(const QColor &col)
{
    QString colorStr;

    colorStr.sprintf("#%02X%02X%02X", col.red(), col.green(), col.blue());
    return colorStr;
}

static QString toStr(EShade exp, const QColor &col)
{
    switch(exp)
    {
        default:
        case SHADE_NONE:
            return "none";
        case SHADE_BLEND_SELECTED:
            return "selected";
        case SHADE_CUSTOM:
            return toStr(col);
        case SHADE_SELECTED:
            return "origselected";
        case SHADE_DARKEN:
            return "darken";
        case SHADE_WINDOW_BORDER:
            return "wborder";
    }
}

static const char *toStr(ERound exp)
{
    switch(exp)
    {
        case ROUND_NONE:
            return "none";
        case ROUND_SLIGHT:
            return "slight";
        case ROUND_EXTRA:
            return "extra";
        case ROUND_MAX:
            return "max";
        default:
        case ROUND_FULL:
            return "full";
    }
}

static const char *toStr(EScrollbar sb)
{
    switch(sb)
    {
        case SCROLLBAR_KDE:
            return "kde";
        default:
        case SCROLLBAR_WINDOWS:
            return "windows";
        case SCROLLBAR_PLATINUM:
            return "platinum";
        case SCROLLBAR_NEXT:
            return "next";
        case SCROLLBAR_NONE:
            return "none";
    }
}

static const char *toStr(EFrame sb)
{
    switch(sb)
    {
        case FRAME_NONE:
            return "none";
        case FRAME_PLAIN:
            return "plain";
        case FRAME_LINE:
            return "line";
        case FRAME_SHADED:
            return "shaded";
        case FRAME_FADED:
        default:
            return "faded";
    }
}

static const char *toStr(EEffect e)
{
    switch(e)
    {
        case EFFECT_NONE:
            return "none";
        default:
        case EFFECT_SHADOW:
            return "shadow";
        case EFFECT_ETCH:
            return "etch";
    }
}

inline const char * toStr(bool b) { return b ? "true" : "false"; }

static const char *toStr(EShading s)
{
    switch(s)
    {
        case SHADING_SIMPLE:
            return "simple";
        default:
        case SHADING_HSL:
            return "hsl";
        case SHADING_HSV:
            return "hsv";
        case SHADING_HCY:
            return "hcy";
    }
}

static const char *toStr(EStripe s)
{
    switch(s)
    {
        default:
        case STRIPE_PLAIN:
            return "plain";
        case STRIPE_NONE:
            return "none";
        case STRIPE_DIAGONAL:
            return "diagonal";
        case STRIPE_FADE:
            return "fade";
    }
}

static const char *toStr(ESliderStyle s)
{
    switch(s)
    {
        case SLIDER_PLAIN:
            return "plain";
        case SLIDER_TRIANGULAR:
            return "triangular";
        case SLIDER_ROUND_ROTATED:
            return "r-round";
        case SLIDER_PLAIN_ROTATED:
            return "r-plain";
        case SLIDER_CIRCULAR:
            return "circular";
        default:
        case SLIDER_ROUND:
            return "round";
    }
}

static const char *toStr(EColor s)
{
    switch(s)
    {
        case ECOLOR_BACKGROUND:
            return "background";
        case ECOLOR_DARK:
            return "dark";
        default:
        case ECOLOR_BASE:
            return "base";
    }
}

static const char *toStr(EFocus f)
{
    switch(f)
    {
        default:
        case FOCUS_STANDARD:
            return "standard";
        case FOCUS_RECTANGLE:
            return "rect";
        case FOCUS_FILLED:
            return "filled";
        case FOCUS_FULL:
            return "full";
        case FOCUS_LINE:
            return "line";
        case FOCUS_GLOW:
            return "glow";
    }
}

static const char *toStr(ETabMo f)
{
    switch(f)
    {
        default:
        case TAB_MO_BOTTOM:
            return "bot";
        case TAB_MO_TOP:
            return "top";
        case TAB_MO_GLOW:
            return "glow";
    }
}

static const char *toStr(EGradientBorder g)
{
    switch(g)
    {
        case GB_NONE:
            return "none";
        case GB_LIGHT:
            return "light";
        case GB_3D_FULL:
            return "3dfull";
        case GB_SHINE:
            return "shine";
        default:
        case GB_3D:
            return "3d";
    }
}

static const char *toStr(EAlign ind)
{
    switch(ind)
    {
        default:
        case ALIGN_LEFT:
            return "left";
        case ALIGN_CENTER:
            return "center";
        case ALIGN_FULL_CENTER:
            return "center-full";
        case ALIGN_RIGHT:
            return "right";
    }
}

static const char * toStr(ETitleBarIcon icn)
{
    switch(icn)
    {
        case TITLEBAR_ICON_NONE:
            return "none";
        default:
        case TITLEBAR_ICON_MENU_BUTTON:
            return "menu";
        case TITLEBAR_ICON_NEXT_TO_TITLE:
            return "title";
    }
}

static const char * toStr(EGradType gt)
{
    switch(gt)
    {
        case GT_VERT:
            return "vert";
        default:
        case GT_HORIZ:
            return "horiz";
    }
}

#if 0
static const char * toStr(ELvLines lv)
{
    switch(lv)
    {
        case LV_NEW:
            return "new";
        case LV_OLD:
            return "old";
        default:
        case LV_NONE:
            return "none";
    }
}
#endif

static const char * toStr(EImageType lv)
{
    switch(lv)
    {
        default:
        case IMG_NONE:
            return "none";
        case IMG_PLAIN_RINGS:
            return "plainrings";
        case IMG_BORDERED_RINGS:
            return "rings";
        case IMG_SQUARE_RINGS:
            return "squarerings";
        case IMG_FILE:
            return "file";
    }
}

static const char * toStr(EGlow lv)
{
    switch(lv)
    {
        default:
        case GLOW_NONE:
            return "none";
        case GLOW_START:
            return "start";
        case GLOW_MIDDLE:
            return "middle";
        case GLOW_END:
            return "end";
    }
}

static const char * toStr(ETBarBtn tb)
{
    switch(tb)
    {
        default:
        case TBTN_STANDARD:
            return "standard";
        case TBTN_RAISED:
            return "raised";
        case TBTN_JOINED:
            return "joined";
    }
}

#if QT_VERSION >= 0x040000
#include <QTextStream>
#define CFG config
#else
#define CFG (*cfg)
#endif

#define CFG_WRITE_ENTRY(ENTRY) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, toStr(opts.ENTRY));

#define CFG_WRITE_APPEARANCE_ENTRY(ENTRY, ALLOW) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, toStr(opts.ENTRY, ALLOW, NULL));

#define CFG_WRITE_APPEARANCE_ENTRY_PIXMAP(ENTRY, ALLOW, PIXMAP) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, toStr(opts.ENTRY, ALLOW, &opts.PIXMAP));

#define CFG_WRITE_ENTRY_B(ENTRY, B) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, toStr(opts.ENTRY, B));

#define CFG_WRITE_ENTRY_NUM(ENTRY) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, opts.ENTRY);

#define CFG_WRITE_SHADE_ENTRY(ENTRY, COL) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, toStr(opts.ENTRY, opts.COL));

#define CFG_WRITE_IMAGE_ENTRY(ENTRY) \
    if (!exportingStyle && def.ENTRY.type==opts.ENTRY.type) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, toStr(opts.ENTRY.type)); \
    if(IMG_FILE!=opts.ENTRY.type) \
    { \
        CFG.deleteEntry(#ENTRY ".file"); \
        CFG.deleteEntry(#ENTRY ".width"); \
        CFG.deleteEntry(#ENTRY ".height"); \
        CFG.deleteEntry(#ENTRY ".onBorder"); \
        CFG.deleteEntry(#ENTRY ".pos"); \
    } \
    else \
    { \
        CFG.writeEntry(#ENTRY ".file", opts.ENTRY.pixmap.file); \
        CFG.writeEntry(#ENTRY ".width", opts.ENTRY.width); \
        CFG.writeEntry(#ENTRY ".height", opts.ENTRY.height); \
        CFG.writeEntry(#ENTRY ".onBorder", opts.ENTRY.onBorder); \
        CFG.writeEntry(#ENTRY ".pos", (int)(opts.ENTRY.pos)); \
    }

#define CFG_WRITE_STRING_LIST_ENTRY(ENTRY) \
    if (!exportingStyle && def.ENTRY==opts.ENTRY) \
        CFG.deleteEntry(#ENTRY); \
    else \
        CFG.writeEntry(#ENTRY, QStringList(opts.ENTRY.toList()).join(",")); \

bool qtcWriteConfig(KConfig *cfg, const Options &opts, const Options &def, bool exportingStyle)
{
    if(!cfg)
    {
        const char *cfgDir=qtcConfDir();

        if(cfgDir)
        {
#if QT_VERSION >= 0x040000
            KConfig defCfg(QFile::decodeName(cfgDir)+CONFIG_FILE, KConfig::SimpleConfig);
#else
            KConfig defCfg(QFile::decodeName(cfgDir)+CONFIG_FILE, false, false);
#endif

            if(qtcWriteConfig(&defCfg, opts, def, exportingStyle))
            {
                const char *oldFiles[]={ OLD_CONFIG_FILE, "qtcurve.gtk-icons", 0};

                for(int i=0; oldFiles[i]; ++i)
                {
                    QString oldFileName(QFile::decodeName(cfgDir)+QString("../")+oldFiles[i]);

                    if(QFile::exists(oldFileName))
                        QFile::remove(oldFileName);
                }
            }
        }
    }
    else
    {
#if QT_VERSION >= 0x040000
        KConfigGroup config(cfg, SETTINGS_GROUP);
#else
        cfg->setGroup(SETTINGS_GROUP);
#endif
        CFG.writeEntry(VERSION_KEY, VERSION);
        CFG_WRITE_ENTRY_NUM(passwordChar)
        CFG_WRITE_ENTRY_NUM(gbFactor)
        CFG_WRITE_ENTRY(round)
        CFG_WRITE_ENTRY_NUM(highlightFactor)
        CFG_WRITE_ENTRY_NUM(menuDelay)
        CFG_WRITE_ENTRY_NUM(sliderWidth)
        CFG_WRITE_ENTRY(toolbarBorders)
        CFG_WRITE_APPEARANCE_ENTRY(appearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(tbarBtnAppearance, APP_ALLOW_NONE)
        CFG_WRITE_ENTRY(tbarBtnEffect)
        CFG_WRITE_APPEARANCE_ENTRY_PIXMAP(bgndAppearance, APP_ALLOW_STRIPED, bgndPixmap)
        CFG_WRITE_ENTRY(bgndGrad)
        CFG_WRITE_ENTRY(menuBgndGrad)
        CFG_WRITE_APPEARANCE_ENTRY_PIXMAP(menuBgndAppearance, APP_ALLOW_STRIPED, menuBgndPixmap)
#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
        CFG_WRITE_ENTRY(fixParentlessDialogs)
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
        CFG_WRITE_STRING_LIST_ENTRY(noDlgFixApps)
#endif
#endif
        CFG_WRITE_ENTRY(stripedProgress)
        CFG_WRITE_ENTRY(sliderStyle)
        CFG_WRITE_ENTRY(animatedProgress)
        CFG_WRITE_ENTRY_NUM(lighterPopupMenuBgnd)
        CFG_WRITE_ENTRY_NUM(tabBgnd)
        CFG_WRITE_ENTRY(embolden)
        CFG_WRITE_ENTRY(defBtnIndicator)
        CFG_WRITE_ENTRY_B(sliderThumbs, false)
        CFG_WRITE_ENTRY_B(handles, true)
        CFG_WRITE_ENTRY(highlightTab)
        CFG_WRITE_ENTRY_NUM(colorSelTab)
        CFG_WRITE_ENTRY(roundAllTabs)
        CFG_WRITE_ENTRY(tabMouseOver)
        CFG_WRITE_APPEARANCE_ENTRY(menubarAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(menuitemAppearance, APP_ALLOW_FADE)
        CFG_WRITE_APPEARANCE_ENTRY(toolbarAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(selectionAppearance, APP_ALLOW_BASIC)
#ifdef __cplusplus
        CFG_WRITE_APPEARANCE_ENTRY(dwtAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_ENTRY(titlebarEffect)
#endif
        CFG_WRITE_APPEARANCE_ENTRY(menuStripeAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_ENTRY_B(toolbarSeparators, false)
        CFG_WRITE_ENTRY_B(splitters, true)
        CFG_WRITE_ENTRY(customMenuTextColor)
        CFG_WRITE_ENTRY(coloredMouseOver)
        CFG_WRITE_ENTRY(menubarMouseOver)
        CFG_WRITE_ENTRY(useHighlightForMenu)
        CFG_WRITE_ENTRY(shadeMenubarOnlyWhenActive)
        CFG_WRITE_ENTRY_NUM(thin)
        CFG_WRITE_SHADE_ENTRY(shadeSliders, customSlidersColor)
        CFG_WRITE_SHADE_ENTRY(shadeMenubars, customMenubarsColor)
        CFG_WRITE_SHADE_ENTRY(sortedLv, customSortedLvColor)
        CFG_WRITE_ENTRY(customMenuSelTextColor)
        CFG_WRITE_ENTRY(customMenuNormTextColor)
        CFG_WRITE_SHADE_ENTRY(shadeCheckRadio, customCheckRadioColor)
        CFG_WRITE_ENTRY(scrollbarType)
        CFG_WRITE_ENTRY(buttonEffect)
        CFG_WRITE_APPEARANCE_ENTRY(lvAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(tabAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(activeTabAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(sliderAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(progressAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(progressGrooveAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(grooveAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(sunkenAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(sbarBgndAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_APPEARANCE_ENTRY(tooltipAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_ENTRY(sliderFill)
        CFG_WRITE_ENTRY(progressGrooveColor)
        CFG_WRITE_ENTRY(focus)
        CFG_WRITE_ENTRY(lvButton)
        CFG_WRITE_ENTRY(lvLines)
        CFG_WRITE_ENTRY(drawStatusBarFrames)
        CFG_WRITE_ENTRY(fillSlider)
        CFG_WRITE_ENTRY(roundMbTopOnly)
        CFG_WRITE_ENTRY(borderMenuitems)
        CFG_WRITE_ENTRY(darkerBorders)
        CFG_WRITE_ENTRY(vArrows)
        CFG_WRITE_ENTRY(xCheck)
        CFG_WRITE_ENTRY(groupBox)
        CFG_WRITE_ENTRY_NUM(gbLabel)
        CFG_WRITE_ENTRY(fadeLines)
        CFG_WRITE_ENTRY(glowProgress)
        CFG_WRITE_IMAGE_ENTRY(bgndImage)
        CFG_WRITE_IMAGE_ENTRY(menuBgndImage)
        CFG_WRITE_ENTRY(colorMenubarMouseOver)
        CFG_WRITE_ENTRY_NUM(crHighlight)
        CFG_WRITE_ENTRY(crButton)
        CFG_WRITE_SHADE_ENTRY(crColor, customCrBgndColor)
        CFG_WRITE_SHADE_ENTRY(progressColor, customProgressColor)
        CFG_WRITE_ENTRY(smallRadio)
        CFG_WRITE_ENTRY(fillProgress)
        CFG_WRITE_ENTRY(comboSplitter)
        CFG_WRITE_ENTRY(highlightScrollViews)
        CFG_WRITE_ENTRY(etchEntry)
        CFG_WRITE_ENTRY_NUM(splitterHighlight)
        CFG_WRITE_ENTRY_NUM(expanderHighlight)
        CFG_WRITE_ENTRY_NUM(crSize)
        CFG_WRITE_ENTRY(flatSbarButtons)
        CFG_WRITE_ENTRY(borderSbarGroove)
        CFG_WRITE_ENTRY(borderProgress)
        CFG_WRITE_ENTRY(popupBorder)
        CFG_WRITE_ENTRY(unifySpinBtns)
        CFG_WRITE_ENTRY(unifySpin)
        CFG_WRITE_ENTRY(unifyCombo)
        CFG_WRITE_ENTRY(borderTab)
        CFG_WRITE_ENTRY(borderInactiveTab)
        CFG_WRITE_ENTRY(thinSbarGroove)
        CFG_WRITE_ENTRY(colorSliderMouseOver)
        CFG_WRITE_ENTRY(menuIcons)
        CFG_WRITE_ENTRY(forceAlternateLvCols)
        CFG_WRITE_ENTRY_NUM(square)
        CFG_WRITE_ENTRY(invertBotTab)
        CFG_WRITE_ENTRY_NUM(menubarHiding)
        CFG_WRITE_ENTRY_NUM(statusbarHiding)
        CFG_WRITE_ENTRY(boldProgress)
        CFG_WRITE_ENTRY(coloredTbarMo)
        CFG_WRITE_ENTRY(borderSelection)
        CFG_WRITE_ENTRY(stripedSbar)
        CFG_WRITE_ENTRY_NUM(windowDrag)
        CFG_WRITE_ENTRY(shadePopupMenu)
        CFG_WRITE_ENTRY(hideShortcutUnderline)
        CFG_WRITE_ENTRY_NUM(windowBorder)
        CFG_WRITE_ENTRY(tbarBtns)
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
        CFG_WRITE_ENTRY(xbar)
        CFG_WRITE_ENTRY_NUM(dwtSettings)
#endif
        CFG_WRITE_ENTRY_NUM(bgndOpacity)
        CFG_WRITE_ENTRY_NUM(menuBgndOpacity)
        CFG_WRITE_ENTRY_NUM(dlgOpacity)
#if defined CONFIG_DIALOG || (defined QT_VERSION && (QT_VERSION >= 0x040000))
        CFG_WRITE_ENTRY(stdBtnSizes)
        CFG_WRITE_ENTRY_NUM(titlebarButtons)
        CFG_WRITE_ENTRY(titlebarIcon)

        if((opts.titlebarButtons&TITLEBAR_BUTTON_COLOR || opts.titlebarButtons&TITLEBAR_BUTTON_ICON_COLOR) &&
            opts.titlebarButtonColors.size() && 0==(opts.titlebarButtonColors.size()%NUM_TITLEBAR_BUTTONS))
        {
            QString     val;
#if QT_VERSION >= 0x040000
            QTextStream str(&val);
#else
            QTextStream str(&val, IO_WriteOnly);
#endif
            for(unsigned int i=0; i<opts.titlebarButtonColors.size(); ++i)
            {
                TBCols::const_iterator c(opts.titlebarButtonColors.find((ETitleBarButtons)i));

                if(c!=opts.titlebarButtonColors.end())
                {
                    if(i)
                        str << ',';
                    str << toStr((*c).second);
                }
            }
            CFG.writeEntry("titlebarButtonColors", val);
        }
        else
            CFG.deleteEntry("titlebarButtonColors");
#endif
        CFG_WRITE_SHADE_ENTRY(menuStripe, customMenuStripeColor)
        CFG_WRITE_SHADE_ENTRY(comboBtn, customComboBtnColor)
        CFG_WRITE_ENTRY(stdSidebarButtons)
        CFG_WRITE_ENTRY(toolbarTabs)
        CFG_WRITE_APPEARANCE_ENTRY(titlebarAppearance, APP_ALLOW_NONE)
        CFG_WRITE_APPEARANCE_ENTRY(inactiveTitlebarAppearance, APP_ALLOW_NONE)
        CFG_WRITE_APPEARANCE_ENTRY(titlebarButtonAppearance, APP_ALLOW_BASIC)
        CFG_WRITE_ENTRY(gtkScrollViews)
        CFG_WRITE_ENTRY(gtkComboMenus)
        CFG_WRITE_ENTRY(doubleGtkComboArrow)
        CFG_WRITE_ENTRY(gtkButtonOrder)
#if !defined __cplusplus || (defined CONFIG_DIALOG && defined QT_VERSION && (QT_VERSION >= 0x040000))
        CFG_WRITE_ENTRY(reorderGtkButtons)
#endif
        CFG_WRITE_ENTRY(mapKdeIcons)
        CFG_WRITE_ENTRY(shading)
        CFG_WRITE_ENTRY(titlebarAlignment)
        CFG_WRITE_ENTRY(centerTabText)
#if defined QT_VERSION && (QT_VERSION >= 0x040000)
        CFG_WRITE_STRING_LIST_ENTRY(noBgndGradientApps)
        CFG_WRITE_STRING_LIST_ENTRY(noBgndOpacityApps)
        CFG_WRITE_STRING_LIST_ENTRY(noMenuBgndOpacityApps)
        CFG_WRITE_STRING_LIST_ENTRY(noBgndImageApps)
        CFG_WRITE_STRING_LIST_ENTRY(noMenuStripeApps)
        CFG_WRITE_STRING_LIST_ENTRY(menubarApps)
        CFG_WRITE_STRING_LIST_ENTRY(statusbarApps)
        CFG_WRITE_STRING_LIST_ENTRY(useQtFileDialogApps)
#endif

        for(int i=APPEARANCE_CUSTOM1; i<(APPEARANCE_CUSTOM1+NUM_CUSTOM_GRAD); ++i)
        {
            GradientCont::const_iterator cg(opts.customGradient.find((EAppearance)i));
            QString                      gradKey;

            gradKey.sprintf("customgradient%d", (i-APPEARANCE_CUSTOM1)+1);

            if(cg==opts.customGradient.end())
                CFG.deleteEntry(gradKey);
            else
            {
                GradientCont::const_iterator d;

                if(exportingStyle || (d=def.customGradient.find((EAppearance)i))==def.customGradient.end() || !((*d)==(*cg)))
                {
                    QString     gradVal;
#if QT_VERSION >= 0x040000
                    QTextStream str(&gradVal);
#else
                    QTextStream str(&gradVal, IO_WriteOnly);
#endif
                    GradientStopCont                 stops((*cg).second.stops.fix());
                    GradientStopCont::const_iterator it(stops.begin()),
                                                     end(stops.end());
                    bool                             haveAlpha(false);

                    for(; it!=end && !haveAlpha; ++it)
                        if((*it).alpha<1.0)
                            haveAlpha=true;

                    str << toStr((*cg).second.border);
                    if(haveAlpha)
                        str << "-alpha";

                    for(it=stops.begin(); it!=end; ++it)
                        if(haveAlpha)
                            str << ',' << (*it).pos << ',' << (*it).val << ',' << (*it).alpha;
                        else
                            str << ',' << (*it).pos << ',' << (*it).val;
                    CFG.writeEntry(gradKey, gradVal);
                }
                else
                    CFG.deleteEntry(gradKey);
            }
        }

        if(opts.customShades[0]==0 ||
           exportingStyle ||
           opts.customShades[0]!=def.customShades[0] ||
           opts.customShades[1]!=def.customShades[1] ||
           opts.customShades[2]!=def.customShades[2] ||
           opts.customShades[3]!=def.customShades[3] ||
           opts.customShades[4]!=def.customShades[4] ||
           opts.customShades[5]!=def.customShades[5])
        {
            QString     shadeVal;
#if QT_VERSION >= 0x040000
            QTextStream str(&shadeVal);
#else
            QTextStream str(&shadeVal, IO_WriteOnly);
#endif
            if(0==opts.customShades[0])
                 str << 0;
            else
                for(int i=0; i<NUM_STD_SHADES; ++i)
                    if(0==i)
                        str << opts.customShades[i];
                    else
                        str << ',' << opts.customShades[i];
            CFG.writeEntry("customShades", shadeVal);
        }
        else
            CFG.deleteEntry("customShades");

        if(opts.customAlphas[0]==0 ||
           exportingStyle ||
           opts.customAlphas[0]!=def.customAlphas[0] ||
           opts.customAlphas[1]!=def.customAlphas[1])
        {
            QString     shadeVal;
#if QT_VERSION >= 0x040000
            QTextStream str(&shadeVal);
#else
            QTextStream str(&shadeVal, IO_WriteOnly);
#endif
            if(0==opts.customAlphas[0])
                 str << 0;
            else
                for(int i=0; i<NUM_STD_ALPHAS; ++i)
                    if(0==i)
                        str << opts.customAlphas[i];
                    else
                        str << ',' << opts.customAlphas[i];
            CFG.writeEntry("customAlphas", shadeVal);
        }
        else
            CFG.deleteEntry("customAlphas");

        // Removed from 1.5 onwards...
        CFG.deleteEntry("colorTitlebarOnly");
        CFG.deleteEntry("titlebarBorder");
        CFG.deleteEntry("titlebarBlend");
        // Removed from 1.4 onwards..
        CFG.deleteEntry("squareLvSelection");
        CFG.deleteEntry("squareScrollViews");
        CFG.deleteEntry("squareProgress");
        CFG.deleteEntry("squareEntry");

        cfg->sync();
        return true;
    }
    return false;
}
#endif
