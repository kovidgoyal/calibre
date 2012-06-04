#ifndef _UTILS_H_
#define _UTILS_H_

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

#include <QtGui/QWidget>

namespace QtCurve
{
    namespace Utils
    {
        inline void addEventFilter(QObject *object, QObject *filter)
        {
            object->removeEventFilter(filter);
            object->installEventFilter(filter);
        }

        extern bool compositingActive();
        extern bool hasAlphaChannel(const QWidget *widget);
    }
}

#endif