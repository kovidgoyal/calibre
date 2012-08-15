//////////////////////////////////////////////////////////////////////////////
// oxygenblurhelper.cpp
// handle regions passed to kwin for blurring
// -------------------
//
// Copyright (c) 2010 Hugo Pereira Da Costa <hugo@oxygen-icons.org>
//
// Loosely inspired (and largely rewritten) from BeSpin style
// Copyright (C) 2007 Thomas Luebking <thomas.luebking@web.de>
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

#include "blurhelper.h"

#include <QtCore/QEvent>
#include <QtCore/QVector>
#include <QtGui/QDockWidget>
#include <QtGui/QMenu>
#include <QtGui/QProgressBar>
#include <QtGui/QPushButton>
#include <QtGui/QToolBar>

#ifdef Q_WS_X11
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include "fixx11h.h"
#include <QX11Info>
#endif

namespace QtCurve
{

    //___________________________________________________________
    BlurHelper::BlurHelper( QObject* parent ):
        QObject( parent ),
        _enabled( false )
    {

        #ifdef Q_WS_X11

        // create atom
        _atom = XInternAtom( QX11Info::display(), "_KDE_NET_WM_BLUR_BEHIND_REGION", False);

        #endif

    }

    //___________________________________________________________
    void BlurHelper::registerWidget( QWidget* widget )
    { Utils::addEventFilter(widget, this); }

    //___________________________________________________________
    void BlurHelper::unregisterWidget( QWidget* widget )
    {
        widget->removeEventFilter( this );
        if( isTransparent( widget ) ) clear( widget );
    }

    //___________________________________________________________
    bool BlurHelper::eventFilter( QObject* object, QEvent* event )
    {

        // do nothing if not enabled
        if( !enabled() ) return false;

        switch( event->type() )
        {

            case QEvent::Hide:
            {
                QWidget* widget( qobject_cast<QWidget*>( object ) );
                if( widget && isOpaque( widget ) )
                {
                    QWidget* window( widget->window() );
                    if (window && isTransparent(window) && !_pendingWidgets.contains(window) )
                    {
                        _pendingWidgets.insert( window, window );
                        delayedUpdate();
                    }
                }
                break;

            }

            case QEvent::Show:
            case QEvent::Resize:
            {

                // cast to widget and check
                QWidget* widget( qobject_cast<QWidget*>( object ) );
                if( !widget ) break;
                if( isTransparent( widget ) )
                {

                    _pendingWidgets.insert( widget, widget );
                    delayedUpdate();

                } else if( isOpaque( widget ) ) {

                    QWidget* window( widget->window() );
                    if( isTransparent( window ) )
                    {
                        _pendingWidgets.insert( window, window );
                        delayedUpdate();
                    }

                }

                break;
            }

            default: break;

        }

        // never eat events
        return false;

    }

    //___________________________________________________________
    QRegion BlurHelper::blurRegion( QWidget* widget ) const
    {
        if( !widget->isVisible() ) return QRegion();

        // get main region
        QRegion region = widget->mask().isEmpty() ? widget->rect():widget->mask();


        // trim blur region to remove unnecessary areas
        trimBlurRegion( widget, widget, region );
        return region;

    }

    //___________________________________________________________
    void BlurHelper::trimBlurRegion( QWidget* parent, QWidget* widget, QRegion& region ) const
    {


        // loop over children
        foreach( QObject* childObject, widget->children() )
        {
            QWidget* child( qobject_cast<QWidget*>( childObject ) );
            if( !(child && child->isVisible()) ) continue;

            if( isOpaque( child ) )
            {

                const QPoint offset( child->mapTo( parent, QPoint( 0, 0 ) ) );
                if( child->mask().isEmpty() ) region -= child->rect().translated( offset );
                else region -= child->mask().translated( offset );

            } else { trimBlurRegion( parent, child, region ); }

        }

        return;

    }

    //___________________________________________________________
    void BlurHelper::update( QWidget* widget ) const
    {

        #ifdef Q_WS_X11

        /*
        directly from bespin code. Supposibly prevent playing with some 'pseudo-widgets'
        that have winId matching some other -random- window
        */
        if( !(widget->testAttribute(Qt::WA_WState_Created) || widget->internalWinId() ))
        { return; }

        const QRegion region( blurRegion( widget ) );
        if( region.isEmpty() ) {

            clear( widget );

        } else {

            QVector<unsigned long> data;
            foreach( const QRect& rect, region.rects() )
            { data << rect.x() << rect.y() << rect.width() << rect.height(); }

            XChangeProperty(
                QX11Info::display(), widget->winId(), _atom, XA_CARDINAL, 32, PropModeReplace,
                reinterpret_cast<const unsigned char *>(data.constData()), data.size() );

        }

        // force update
        if( widget->isVisible() )
        { widget->update(); }
        
        #else
        Q_UNUSED(widget);

        #endif

    }


    //___________________________________________________________
    void BlurHelper::clear( QWidget* widget ) const
    {
        #ifdef Q_WS_X11
        XChangeProperty( QX11Info::display(), widget->winId(), _atom, XA_CARDINAL, 32, PropModeReplace, 0, 0 );
        #else
        Q_UNUSED(widget);
        #endif

    }

}
