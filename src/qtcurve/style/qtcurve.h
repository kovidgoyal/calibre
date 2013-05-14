#ifndef __QTCURVE_H__
#define __QTCURVE_H__

/*
  QtCurve (C) Craig Drummond, 2007 - 2010 craig.p.drummond@gmail.com

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

#include <QProgressBar>
#include <QTime>
#include <QPalette>
#include <QMap>
#include <QList>
#include <QSet>
#include <QCache>
#include <QColor>
#include <QStyleOption>
#include <QBitmap>
#if (QT_VERSION >= QT_VERSION_CHECK(4, 4, 0))
#include <QFormLayout>
#endif
#include <Q_UINT64>
typedef qulonglong QtcKey;
#include "common.h"

#if !defined QTC_QT_ONLY
#include <KDE/KComponentData>
#endif

// #ifdef QTC_KSTYLE
// #include <kstyle.h>
// #define BASE_STYLE KStyle
// #else
#include <QCommonStyle>
#define BASE_STYLE QCommonStyle
// #endif

class QStyleOptionSlider;
class QLabel;
class QMenuBar;
class QScrollBar;
class QDBusInterface;
class QMainWindow;
class QStatusBar;
class QAbstractScrollArea;

namespace QtCurve
{
    class WindowManager;
    class BlurHelper;
    class ShortcutHandler;
#ifdef Q_WS_X11
    class ShadowHelper;
#endif

class Style : public QCommonStyle
{
    Q_OBJECT
    Q_CLASSINFO("X-KDE-CustomElements", "true")

    public:

    enum BackgroundType
    {
        BGND_WINDOW,
        BGND_DIALOG,
        BGND_MENU
    };

    enum MenuItemType
    {
        MENU_POPUP,
        MENU_BAR,
        MENU_COMBO
    };
    
    enum CustomElements
    {
        CE_QtC_KCapacityBar = CE_CustomBase+0x00FFFF00,
        CE_QtC_Preview,
        CE_QtC_SetOptions
    };

    enum PreviewType
    {
        PREVIEW_FALSE,
        PREVIEW_MDI,
        PREVIEW_WINDOW
    };
    
    class PreviewOption : public QStyleOption
    {
        public:

        Options opts;
    };

    class BgndOption : public QStyleOption
    {
        public:

        EAppearance  app;
        QPainterPath path;
        QRect        widgetRect;
    };

    enum Icon
    {
        ICN_MIN,
        ICN_MAX,
        ICN_MENU,
        ICN_RESTORE,
        ICN_CLOSE,
        ICN_UP,
        ICN_DOWN,
        ICN_RIGHT,
        ICN_SHADE,
        ICN_UNSHADE
    };

#ifdef QTC_STYLE_SUPPORT
    Style(const QString &name=QString());
#else
    Style();
#endif

    ~Style();
    
    void init(bool initial);
    void freeColor(QSet<QColor *> &freedColors, QColor **cols);
    void freeColors();

    Options & options() { return opts; }

    void polish(QApplication *app);
    void polish(QPalette &palette);
    void polish(QWidget *widget);

#if (QT_VERSION >= QT_VERSION_CHECK(4, 4, 0))
    void polishFormLayout(QFormLayout *layout);
    void polishLayout(QLayout *layout);
#endif
    void polishScrollArea(QAbstractScrollArea *scrollArea, bool isKFilePlacesView=false) const;

    void unpolish(QApplication *app);
    void unpolish(QWidget *widget);
    bool eventFilter(QObject *object, QEvent *event);
    void timerEvent(QTimerEvent *event);
    int pixelMetric(PixelMetric metric, const QStyleOption *option=0, const QWidget *widget=0) const;
    int styleHint(StyleHint hint, const QStyleOption *option, const QWidget *widget, QStyleHintReturn *returnData=0) const;
    QPalette standardPalette() const;
    void drawPrimitive(PrimitiveElement element, const QStyleOption *option, QPainter *painter, const QWidget *widget) const;
    void drawControl(ControlElement control, const QStyleOption *option, QPainter *painter, const QWidget *widget) const;
    void drawComplexControl(ComplexControl control, const QStyleOptionComplex *option, QPainter *painter, const QWidget *widget) const;
    void drawItemTextWithRole(QPainter *painter, const QRect &rect, int flags, const QPalette &pal, bool enabled, const QString &text,
                              QPalette::ColorRole textRole) const;
    void drawItemText(QPainter *painter, const QRect &rect, int flags, const QPalette &pal, bool enabled, const QString &text,
                      QPalette::ColorRole textRole = QPalette::NoRole) const;
    QSize sizeFromContents(ContentsType type, const QStyleOption *option, const QSize &size, const QWidget *widget) const;
    QRect subElementRect(SubElement element, const QStyleOption *option, const QWidget *widget) const;
    QRect subControlRect(ComplexControl control, const QStyleOptionComplex *option, SubControl subControl, const QWidget *widget) const;
    SubControl hitTestComplexControl(ComplexControl control, const QStyleOptionComplex *option,
                                     const QPoint &pos, const QWidget *widget) const;
    virtual bool event(QEvent *event);

    private:

    void drawSideBarButton(QPainter *painter, const QRect &r, const QStyleOption *option, const QWidget *widget) const;
    void drawHighlight(QPainter *p, const QRect &r, bool horiz, bool inc) const;
    void drawFadedLine(QPainter *p, const QRect &r, const QColor &col, bool fadeStart, bool fadeEnd, bool horiz,
                       double fadeSizeStart=FADE_SIZE, double fadeSizeEnd=FADE_SIZE) const;
    void drawLines(QPainter *p, const QRect &r, bool horiz, int nLines, int offset, const QColor *cols, int startOffset,
                   int dark, ELine type) const;
    void drawProgressBevelGradient(QPainter *p, const QRect &origRect, const QStyleOption *option, bool horiz,
                                   EAppearance bevApp, const QColor *cols) const;
    void drawBevelGradient(const QColor &base, QPainter *p, QRect const &r, const QPainterPath &path,
                           bool horiz, bool sel, EAppearance bevApp, EWidget w=WIDGET_OTHER, bool useCache=true) const;
    void drawBevelGradientReal(const QColor &base, QPainter *p, const QRect &r, const QPainterPath &path,
                               bool horiz, bool sel, EAppearance bevApp, EWidget w) const;

    void drawBevelGradient(const QColor &base, QPainter *p, QRect const &r,
                           bool horiz, bool sel, EAppearance bevApp, EWidget w=WIDGET_OTHER, bool useCache=true) const
    {
        drawBevelGradient(base, p, r, QPainterPath(), horiz, sel, bevApp, w, useCache);
    }
    void drawBevelGradientReal(const QColor &base, QPainter *p, const QRect &r, bool horiz, bool sel,
                               EAppearance bevApp, EWidget w) const
    {
        drawBevelGradientReal(base, p, r, QPainterPath(), horiz, sel, bevApp, w);
    }

    void drawSunkenBevel(QPainter *p, const QRect &r, const QColor &col) const;
    void drawLightBevel(QPainter *p, const QRect &r, const QStyleOption *option, const QWidget *widget, int round, const QColor &fill,
                        const QColor *custom=0, bool doBorder=true, EWidget w=WIDGET_OTHER) const;
    void drawLightBevelReal(QPainter *p, const QRect &r, const QStyleOption *option, const QWidget *widget, int round, const QColor &fill,
                            const QColor *custom, bool doBorder, EWidget w, bool useCache, ERound realRound, bool onToolbar) const;
    void drawGlow(QPainter *p, const QRect &r, EWidget w, const QColor *cols=0L) const;
    void drawEtch(QPainter *p, const QRect &r,  const QWidget *widget, EWidget w, bool raised=false, int round=ROUNDED_ALL) const;
    void drawBgndRing(QPainter &painter, int x, int y, int size, int size2, bool isWindow) const;
    QPixmap drawStripes(const QColor &color, int opacity) const;
    void drawBackground(QPainter *p, const QColor &bgnd, const QRect &r, int opacity, BackgroundType type, EAppearance app,
                        const QPainterPath &path=QPainterPath()) const;
    void drawBackgroundImage(QPainter *p, bool isWindow, const QRect &r) const;
    void drawBackground(QPainter *p, const QWidget *widget, BackgroundType type) const;
    QPainterPath buildPath(const QRectF &r, EWidget w, int round, double radius) const;
    QPainterPath buildPath(const QRect &r, EWidget w, int round, double radius) const;
    void buildSplitPath(const QRect &r, int round, double radius, QPainterPath &tl, QPainterPath &br) const;
    void drawBorder(QPainter *p, const QRect &r, const QStyleOption *option, int round, const QColor *custom=0,
                    EWidget w=WIDGET_OTHER, EBorder borderProfile=BORDER_FLAT, bool doBlend=true, int borderVal=STD_BORDER) const;
    void drawMdiControl(QPainter *p, const QStyleOptionTitleBar *titleBar, SubControl sc, const QWidget *widget,
                        ETitleBarButtons btn, const QColor &iconColor, const QColor *btnCols, const QColor *bgndCols,
                        int adjust, bool activeWindow) const;
    void drawDwtControl(QPainter *p, const QFlags<State> &state, const QRect &rect, ETitleBarButtons btn, Icon icon,
                        const QColor &iconColor, const QColor *btnCols, const QColor *bgndCols) const;
    bool drawMdiButton(QPainter *painter, const QRect &r, bool hover, bool sunken, const QColor *cols) const;
    void drawMdiIcon(QPainter *painter, const QColor &color, const QColor &bgnd, const QRect &r,
                     bool hover, bool sunken, Icon iclearcon, bool stdSize, bool drewFrame) const;
    void drawIcon(QPainter *painter, const QColor &color, const QRect &r, bool sunken, Icon icon, bool stdSize=true) const;
    void drawEntryField(QPainter *p, const QRect &rx,  const QWidget *widget, const QStyleOption *option, int round,
                        bool fill, bool doEtch, EWidget w=WIDGET_ENTRY) const;
    void drawMenuItem(QPainter *p, const QRect &r, const QStyleOption *option, MenuItemType type, int round, const QColor *cols) const;
    void drawProgress(QPainter *p, const QRect &r, const QStyleOption *option, bool vertical=false, bool reverse=false) const;
    void drawArrow(QPainter *p, const QRect &rx, PrimitiveElement pe, QColor col, bool small=false, bool kwin=false) const;
    void drawSbSliderHandle(QPainter *p, const QRect &r, const QStyleOption *option, bool slider=false) const;
    void drawSliderHandle(QPainter *p, const QRect &r, const QStyleOptionSlider *option) const;
    void drawSliderGroove(QPainter *p, const QRect &groove, const QRect &handle, const QStyleOptionSlider *slider, const QWidget *widget) const;
    int  getOpacity(const QWidget *widget, QPainter *p) const;
    void drawMenuOrToolBarBackground(const QWidget *widget, QPainter *p, const QRect &r, const QStyleOption *option, bool menu=true,
                                     bool horiz=true) const;
    void drawHandleMarkers(QPainter *p, const QRect &r, const QStyleOption *option, bool tb, ELine handles) const;
    void fillTab(QPainter *p, const QRect &r, const QStyleOption *option, const QColor &fill, bool horiz, EWidget tab, bool tabOnly) const;
    void colorTab(QPainter *p, const QRect &r, bool horiz, EWidget tab, int round) const;
    void shadeColors(const QColor &base, QColor *vals) const;
    const QColor * buttonColors(const QStyleOption *option) const;
    QColor         titlebarIconColor(const QStyleOption *option) const;
    const QColor * popupMenuCols(const QStyleOption *option=0L) const;
    const QColor * checkRadioColors(const QStyleOption *option) const;
    const QColor * sliderColors(const QStyleOption *option) const;
    const QColor * backgroundColors(const QColor &col) const;
    const QColor * backgroundColors(const QStyleOption *option) const
        { return option ? backgroundColors(option->palette.background().color()) : itsBackgroundCols; }
    const QColor * highlightColors(const QColor &col) const;
    const QColor * highlightColors(const QStyleOption *option, bool useActive) const
        { return highlightColors(option->palette.brush(useActive ? QPalette::Active : QPalette::Current, QPalette::Highlight).color()); }
    const QColor * borderColors(const QStyleOption *option, const QColor *use) const;
    const QColor * getSidebarButtons() const;
    void           setMenuColors(const QColor &bgnd);
   void            setMenuTextColors(QWidget *widget, bool isMenuBar) const;
    const QColor * menuColors(const QStyleOption *option, bool active) const;
    bool           coloredMdiButtons(bool active, bool mouseOver) const;
    const QColor * getMdiColors(const QStyleOption *option, bool active) const;
    void           readMdiPositions() const;
    const QColor & getFill(const QStyleOption *option, const QColor *use, bool cr=false, bool darker=false) const;
    const QColor & getTabFill(bool current, bool highlight, const QColor *use) const;
    QColor         menuStripeCol() const;
    QPixmap *      getPixmap(const QColor col, EPixmap p, double shade=1.0) const;
    int            konqMenuBarSize(const QMenuBar *menu) const;
    const QColor & checkRadioCol(const QStyleOption *opt) const;
    QColor         shade(const QColor &a, double k) const;
    void           shade(const color &ca, color *cb, double k) const;
    QColor         getLowerEtchCol(const QWidget *widget) const;
    int            getFrameRound(const QWidget *widget) const;
    void           unregisterArgbWidget(QWidget *w);

    private Q_SLOTS:

    void           widgetDestroyed(QObject *o);
    QIcon          standardIconImplementation(StandardPixmap pix, const QStyleOption *option=0, const QWidget *widget=0) const;
    int            layoutSpacingImplementation(QSizePolicy::ControlType control1, QSizePolicy::ControlType control2,
                                               Qt::Orientation orientation, const QStyleOption *option,
                                               const QWidget *widget) const;
    void           kdeGlobalSettingsChange(int type, int);
    void           borderSizesChanged();
    void           toggleMenuBar(unsigned int xid);
    void           toggleStatusBar(unsigned int xid);
    void           compositingToggled();

    private:

    void           toggleMenuBar(QMainWindow *window);
    void           toggleStatusBar(QMainWindow *window);

#if !defined QTC_QT_ONLY
    void           setupKde4();


    void           setDecorationColors();
    void           applyKdeSettings(bool pal);
#endif
#ifdef Q_WS_X11
    bool           isWindowDragWidget(QObject *o);
    void           emitMenuSize(QWidget *w, unsigned short size, bool force=false);
    void           emitStatusBarState(QStatusBar *sb);
#endif

    private:

    mutable Options                    opts;
    QColor                             itsHighlightCols[TOTAL_SHADES+1],
                                       itsBackgroundCols[TOTAL_SHADES+1],
                                       itsMenubarCols[TOTAL_SHADES+1],
                                       itsFocusCols[TOTAL_SHADES+1],
                                       itsMouseOverCols[TOTAL_SHADES+1],
                                       *itsPopupMenuCols,
                                       *itsSliderCols,
                                       *itsDefBtnCols,
                                       *itsComboBtnCols,
                                       *itsCheckRadioSelCols,
                                       *itsSortedLvColors,
                                       *itsOOMenuCols,
                                       *itsProgressCols,
                                       itsButtonCols[TOTAL_SHADES+1],
                                       itsCheckRadioCol;
    bool                               itsSaveMenuBarStatus,
                                       itsSaveStatusBarStatus,
                                       itsUsePixmapCache,
                                       itsInactiveChangeSelectionColor;
    PreviewType                        itsIsPreview;
    mutable QColor                     *itsSidebarButtonsCols;
    mutable QColor                     *itsActiveMdiColors;
    mutable QColor                     *itsMdiColors;
    mutable QColor                     itsActiveMdiTextColor;
    mutable QColor                     itsMdiTextColor;
    mutable QColor                     itsColoredButtonCols[TOTAL_SHADES+1];
    mutable QColor                     itsColoredBackgroundCols[TOTAL_SHADES+1];
    mutable QColor                     itsColoredHighlightCols[TOTAL_SHADES+1];
    mutable QCache<QtcKey, QPixmap>    itsPixmapCache;
    mutable bool                       itsActive;
    mutable const QWidget              *itsSbWidget;
    mutable QLabel                     *itsClickedLabel;
    QSet<QProgressBar *>               itsProgressBars;
    QSet<QWidget *>                    itsTransparentWidgets;
    int                                itsProgressBarAnimateTimer,
                                       itsAnimateStep;
    QTime                              itsTimer;
    mutable QMap<int, QColor *>        itsTitleBarButtonsCols;
#ifdef QTC_ENABLE_PARENTLESS_DIALOG_FIX_SUPPORT
    mutable QMap<QWidget *, QWidget *> itsReparentedDialogs;
#endif
    mutable QList<int>                 itsMdiButtons[2]; // 0=left, 1=right
    mutable int                        itsTitlebarHeight;
    QHash<int,QString>                 calibre_icon_map;
    int                                calibre_item_view_focus;
    bool                               is_kde_session;

    // Required for Q3Header hover...
    QPoint                             itsPos;
    QWidget                            *itsHoverWidget;
#ifdef Q_WS_X11
    QDBusInterface                     *itsDBus;
    QtCurve::ShadowHelper              *itsShadowHelper;
#endif
    mutable QScrollBar                 *itsSViewSBar;
    mutable QMap<QWidget *, QSet<QWidget *> > itsSViewContainers;
#if !defined QTC_QT_ONLY
    KComponentData                     itsComponentData;
#endif
    QtCurve::WindowManager             *itsWindowManager;
    QtCurve::BlurHelper                *itsBlurHelper;
    QtCurve::ShortcutHandler           *itsShortcutHandler;
#ifdef QTC_STYLE_SUPPORT
    QString                            itsName;
#endif
};

}

#endif
