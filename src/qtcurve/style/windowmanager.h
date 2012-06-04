#ifndef __WINDOW_MANAGER_H__
#define __WINDOW_MANAGER_H__

// Copied from oxygenwindowmanager.h svnversion: 1137195

//////////////////////////////////////////////////////////////////////////////
// oxygenwindowmanager.h
// pass some window mouse press/release/move event actions to window manager
// -------------------
//
// Copyright (c) 2010 Hugo Pereira Da Costa <hugo@oxygen-icons.org>
//
// Largely inspired from BeSpin style
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

#include <QtCore/QEvent>

#include <QtCore/QBasicTimer>
#include <QtCore/QObject>
#include <QtCore/QSet>
#include <QtCore/QString>
#include <QtCore/QWeakPointer>

#include <QtGui/QWidget>

namespace QtCurve
{
#if QT_VERSION < 0x040600
    class QtCPointer : public QObject
{
        public:
        QtCPointer(QWidget *w=0L) : widget_(w) {}
        QtCPointer & operator=(QWidget *w);
        operator bool() const { return 0L!=widget_; }
        void clear();
        bool eventFilter(QObject *, QEvent *);
        QWidget *data() { return widget_; }

        private:
        QWidget *widget_;
    };
#endif

    class WindowManager: public QObject
    {

        Q_OBJECT

        public:

        //! constructor
        explicit WindowManager( QObject* );

        //! destructor
        virtual ~WindowManager( void )
        {}

        //! initialize
        /*! read relevant options from OxygenStyleConfigData */
        void initialize( int windowDrag, const QStringList &whiteList=QStringList(), const QStringList &blackList=QStringList() );

        //! register widget
        void registerWidget( QWidget* );

        //! unregister widget
        void unregisterWidget( QWidget* );

        //! event filter [reimplemented]
        virtual bool eventFilter( QObject*, QEvent* );

        protected:

        //! timer event,
        /*! used to start drag if button is pressed for a long enough time */
        void timerEvent( QTimerEvent* );

        //! mouse press event
        bool mousePressEvent( QObject*, QEvent* );

        //! mouse move event
        bool mouseMoveEvent( QObject*, QEvent* );

        //! mouse release event
        bool mouseReleaseEvent( QObject*, QEvent* );

        //!@name configuration
        //@{

        //! enable state
        bool enabled( void ) const
        { return _enabled; }

        //! enable state
        void setEnabled( bool value )
        { _enabled = value; }

        //! returns true if window manager is used for moving
        bool useWMMoveResize( void ) const
        { return supportWMMoveResize() && _useWMMoveResize; }

        //! use window manager for moving, when available
        void setUseWMMoveResize( bool value )
        { _useWMMoveResize = value; }

        //! drag mode
        int dragMode( void ) const
        { return _dragMode; }

        //! drag mode
        void setDragMode( int value )
        { _dragMode = value; }

        //! drag distance (pixels)
        void setDragDistance( int value )
        { _dragDistance = value; }

        //! drag delay (msec)
        void setDragDelay( int value )
        { _dragDelay = value; }

        //! set list of whiteListed widgets
        /*!
        white list is read from options and is used to adjust
        per-app window dragging issues
        */
        void initializeWhiteList( const QStringList &list );

        //! set list of blackListed widgets
        /*!
        black list is read from options and is used to adjust
        per-app window dragging issues
        */
        void initializeBlackList( const QStringList &list );

        //@}

        //! returns true if widget is dragable
        bool isDragable( QWidget* );

        //! returns true if widget is dragable
        bool isBlackListed( QWidget* );

        //! returns true if widget is dragable
        bool isWhiteListed( QWidget* ) const;

        //! returns true if drag can be started from current widget
        bool canDrag( QWidget* );

        //! returns true if drag can be started from current widget and position
        /*! child at given position is passed as second argument */
        bool canDrag( QWidget*, QWidget*, const QPoint& );

        //! reset drag
        void resetDrag( void );

        //! start drag
        void startDrag( QWidget*, const QPoint& );

        //! returns true if window manager is used for moving
        /*! right now this is true only for X11 */
        bool supportWMMoveResize( void ) const;

        //! utility function
        bool isDockWidgetTitle( const QWidget* ) const;

        //!@name lock
        //@{

        void setLocked( bool value )
        { _locked = value; }

        //! lock
        bool isLocked( void ) const
        { return _locked; }

        //@}

        private:

        //! enability
        bool _enabled;

        //! use WM moveResize
        bool _useWMMoveResize;

        //! drag mode
        int _dragMode;

        //! drag distance
        /*! this is copied from kwin::geometry */
        int _dragDistance;

        //! drag delay
        /*! this is copied from kwin::geometry */
        int _dragDelay;

        //! wrapper for exception id
        class ExceptionId: public QPair<QString, QString>
        {
            public:

            //! constructor
            ExceptionId( const QString& value )
            {
                const QStringList args( value.split( "@" ) );
                if( args.isEmpty() ) return;
                second = args[0].trimmed();
                if( args.size()>1 ) first = args[1].trimmed();
            }

            const QString& appName( void ) const
            { return first; }

            const QString& className( void ) const
            { return second; }

        };

        //! exception set
        typedef QSet<ExceptionId> ExceptionSet;

        //! list of white listed special widgets
        /*!
        it is read from options and is used to adjust
        per-app window dragging issues
        */
        ExceptionSet _whiteList;

        //! list of black listed special widgets
        /*!
        it is read from options and is used to adjust
        per-app window dragging issues
        */
        ExceptionSet _blackList;

        //! drag point
        QPoint _dragPoint;
        QPoint _globalDragPoint;

        //! drag timer
        QBasicTimer _dragTimer;

        //! target being dragged
        /*! QWeakPointer is used in case the target gets deleted while drag is in progress */
#if QT_VERSION < 0x040600
        QtCPointer _target;
#else
        QWeakPointer<QWidget> _target;
#endif

        //! true if drag is about to start
        bool _dragAboutToStart;

        //! true if drag is in progress
        bool _dragInProgress;

        //! true if drag is locked
        bool _locked;

        //! cursor override
        /*! used to keep track of application cursor being overridden when dragging in non-WM mode */
        bool _cursorOverride;

        //! provide application-wise event filter
        /*!
        it us used to unlock dragging and make sure event look is properly restored
        after a drag has occurred
        */
        class AppEventFilter: public QObject
        {

            public:

            //! constructor
            AppEventFilter( WindowManager* parent ):
                QObject( parent ),
                _parent( parent )
            {}

            //! event filter
            virtual bool eventFilter( QObject*, QEvent* );

            protected:

            //! application-wise event.
            /*! needed to catch end of XMoveResize events */
            bool appMouseEvent( QObject*, QEvent* );

            private:

            //! parent
            WindowManager* _parent;

        };

        //! application event filter
        AppEventFilter* _appEventFilter;

        //! allow access of all private members to the app event filter
        friend class AppEventFilter;

    };

}

#endif
