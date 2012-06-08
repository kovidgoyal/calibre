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

#include "utils.h"
#include "config.h"
#include <stdio.h>
#ifdef Q_WS_X11
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include "fixx11h.h"
#include <QX11Info>
#endif

#if defined QTC_QT_ONLY
#undef KDE_IS_VERSION
#define KDE_IS_VERSION(A, B, C) 0
#else
#include <kdeversion.h>
#include <KDE/KWindowSystem>
#endif

namespace QtCurve
{
    namespace Utils
    {
        bool compositingActive()
        {
            #if defined QTC_QT_ONLY || !KDE_IS_VERSION(4, 4, 0)
            #ifdef Q_WS_X11
            static bool haveAtom=false;
            static Atom atom;
            if(!haveAtom)
            {
                Display *dpy = QX11Info::display();
                char    string[100];

                sprintf(string, "_NET_WM_CM_S%d", DefaultScreen(dpy));

                atom = XInternAtom(dpy, string, False);
                haveAtom=true;
            }

            return XGetSelectionOwner(QX11Info::display(), atom) != None;
            #else // Q_WS_X11
            return false;
            #endif // Q_WS_X11
            #else // QTC_QT_ONLY
            return KWindowSystem::compositingActive();
            #endif // QTC_QT_ONLY
        }
        
        bool hasAlphaChannel(const QWidget *widget)
        {
            #ifdef Q_WS_X11
            if(compositingActive())
                return 32 == (widget ? widget->x11Info().depth() : QX11Info().appDepth()) ;
            else
                return false;
            #else
            return compositingActive();
            #endif
        }
    }
}
