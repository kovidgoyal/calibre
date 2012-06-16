//////////////////////////////////////////////////////////////////////////////
// oxygenshadowhelper.h
// handle shadow _pixmaps passed to window manager via X property
// -------------------
//
// Copyright (c) 2010 Hugo Pereira Da Costa <hugo@oxygen-icons.org>
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to
// deal in the Software without restriction, including without limitation the
// rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
// sell copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
// FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
// IN THE SOFTWARE.
//////////////////////////////////////////////////////////////////////////////

#include "shadowhelper.h"
#include "shadow.h"
#include "utils.h"

#include <QtGui/QDockWidget>
#include <QtGui/QMenu>
#include <QtGui/QPainter>
#include <QtGui/QToolBar>
#include <QtCore/QEvent>

#ifdef Q_WS_X11
#include <QtGui/QX11Info>
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#endif

namespace QtCurve
{

    const char* const ShadowHelper::netWMShadowAtomName( "_KDE_NET_WM_SHADOW" );
    const char* const ShadowHelper::netWMForceShadowPropertyName( "_KDE_NET_WM_FORCE_SHADOW" );
    const char* const ShadowHelper::netWMSkipShadowPropertyName( "_KDE_NET_WM_SKIP_SHADOW" );

    //_____________________________________________________
    ShadowHelper::ShadowHelper( QObject* parent ):
        QObject( parent ),
        #ifdef Q_WS_X11
        _atom( None )
        #endif
    {
        createPixmapHandles();
    }

    //_______________________________________________________
    ShadowHelper::~ShadowHelper( void )
    {

        #ifdef Q_WS_X11
        for(int i=0; i<numPixmaps; ++i)
            XFreePixmap( QX11Info::display(), _pixmaps[i] );
        #endif
    }

    //_______________________________________________________
    bool ShadowHelper::registerWidget( QWidget* widget, bool force )
    {

        // make sure widget is not already registered
        if( _widgets.contains( widget ) ) return false;

        // check if widget qualifies
        if( !( force || acceptWidget( widget ) ) )
        { return false; }

        // store in map and add destroy signal connection
        Utils::addEventFilter(widget, this);
        _widgets.insert( widget, 0 );

        /*
        need to install shadow directly when widget "created" state is already set
        since WinID changed is never called when this is the case
        */
        if( widget->testAttribute(Qt::WA_WState_Created) && installX11Shadows( widget ) )
        {  _widgets.insert( widget, widget->winId() ); }

        connect( widget, SIGNAL( destroyed( QObject* ) ), SLOT( objectDeleted( QObject* ) ) );

        return true;

    }

    //_______________________________________________________
    void ShadowHelper::unregisterWidget( QWidget* widget )
    {
        if( _widgets.remove( widget ) )
        { uninstallX11Shadows( widget ); }
    }

    //_______________________________________________________
    bool ShadowHelper::eventFilter( QObject* object, QEvent* event )
    {

        // check event type
        if( event->type() != QEvent::WinIdChange ) return false;

        // cast widget
        QWidget* widget( static_cast<QWidget*>( object ) );

        // install shadows and update winId
        if( installX11Shadows( widget ) )
        { _widgets.insert( widget, widget->winId() ); }

        return false;

    }

    //_______________________________________________________
    void ShadowHelper::objectDeleted( QObject* object )
    { _widgets.remove( static_cast<QWidget*>( object ) ); }

    //_______________________________________________________
    bool ShadowHelper::isMenu( QWidget* widget ) const
    { return qobject_cast<QMenu*>( widget ); }

    //_______________________________________________________
    bool ShadowHelper::acceptWidget( QWidget* widget ) const
    {

        if( widget->property( netWMSkipShadowPropertyName ).toBool() ) return false;
        if( widget->property( netWMForceShadowPropertyName ).toBool() ) return true;

        // menus
        if( qobject_cast<QMenu*>( widget ) ) return true;

        // combobox dropdown lists
        if( widget->inherits( "QComboBoxPrivateContainer" ) ) return true;

        // tooltips
        if( (widget->inherits( "QTipLabel" ) || (widget->windowFlags() & Qt::WindowType_Mask) == Qt::ToolTip ) &&
            !widget->inherits( "Plasma::ToolTip" ) )
        { return true; }

        // detached widgets
        if( qobject_cast<QToolBar*>( widget ) || qobject_cast<QDockWidget*>( widget ) )
        { return true; }

        // reject
        return false;
    }

    //______________________________________________
    void ShadowHelper::createPixmapHandles(  )
    {

        /*!
        shadow atom and property specification available at
        http://community.kde.org/KWin/Shadow
        */

        // create atom
        #ifdef Q_WS_X11
        if( !_atom ) _atom = XInternAtom( QX11Info::display(), netWMShadowAtomName, False);
        #endif

        _pixmaps[0]=createPixmap(shadow0_png_data, shadow0_png_len);
        _pixmaps[1]=createPixmap(shadow1_png_data, shadow1_png_len);
        _pixmaps[2]=createPixmap(shadow2_png_data, shadow2_png_len);
        _pixmaps[3]=createPixmap(shadow3_png_data, shadow3_png_len);
        _pixmaps[4]=createPixmap(shadow4_png_data, shadow4_png_len);
        _pixmaps[5]=createPixmap(shadow5_png_data, shadow5_png_len);
        _pixmaps[6]=createPixmap(shadow6_png_data, shadow6_png_len);
        _pixmaps[7]=createPixmap(shadow7_png_data, shadow7_png_len);
    }

    //______________________________________________
    Qt::HANDLE ShadowHelper::createPixmap( const uchar *buf, int len )
    {
        QImage source;
        source.loadFromData(buf, len);

        // do nothing for invalid _pixmaps
        if( source.isNull() ) return 0;

        _size=source.width();

        /*
        in some cases, pixmap handle is invalid. This is the case notably
        when Qt uses to RasterEngine. In this case, we create an X11 Pixmap
        explicitly and draw the source pixmap on it.
        */

        #ifdef Q_WS_X11
        const int width( source.width() );
        const int height( source.height() );

        // create X11 pixmap
        Pixmap pixmap = XCreatePixmap( QX11Info::display(), QX11Info::appRootWindow(), width, height, 32 );

        // create explicitly shared QPixmap from it
        QPixmap dest( QPixmap::fromX11Pixmap( pixmap, QPixmap::ExplicitlyShared ) );

        // create surface for pixmap
        {
            QPainter painter( &dest );
            painter.setCompositionMode( QPainter::CompositionMode_Source );
            painter.drawImage( 0, 0, source );
        }


        return pixmap;
        #else
        return 0;
        #endif

    }

//_______________________________________________________
    bool ShadowHelper::installX11Shadows( QWidget* widget )
    {

        // check widget and shadow
        if( !widget ) return false;

        #ifdef Q_WS_X11
        #ifndef QT_NO_XRENDER

        // TODO: also check for NET_WM_SUPPORTED atom, before installing shadow

        /*
        From bespin code. Supposibly prevent playing with some 'pseudo-widgets'
        that have winId matching some other -random- window
        */
        if( !(widget->testAttribute(Qt::WA_WState_Created) || widget->internalWinId() ))
        { return false; }

        // create data
        // add pixmap handles
        QVector<unsigned long> data;
        for(int i=0; i<numPixmaps; ++i)
        { data.push_back( _pixmaps[i] ); }

        // add padding
        data << _size -4 << _size -4 << _size -4 << _size -4;

        XChangeProperty(
            QX11Info::display(), widget->winId(), _atom, XA_CARDINAL, 32, PropModeReplace,
            reinterpret_cast<const unsigned char *>(data.constData()), data.size() );

        return true;

        #endif
        #endif

        return false;

    }

    //_______________________________________________________
    void ShadowHelper::uninstallX11Shadows( QWidget* widget ) const
    {

        #ifdef Q_WS_X11
        if( !( widget && widget->testAttribute(Qt::WA_WState_Created) ) ) return;
        XDeleteProperty(QX11Info::display(), widget->winId(), _atom);
        #endif

    }

    //_______________________________________________________
    void ShadowHelper::uninstallX11Shadows( WId id ) const
    {

        #ifdef Q_WS_X11
        XDeleteProperty(QX11Info::display(), id, _atom);
        #endif

    }

}
