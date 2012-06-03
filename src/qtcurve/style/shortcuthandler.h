#ifndef __SHORTCUT_HANDLER_H__
#define __SHORTCUT_HANDLER_H__

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

#include <QtCore/QObject>
#include <QtCore/QSet>
#include <QtCore/QList>

class QWidget;

namespace QtCurve
{

class ShortcutHandler : public QObject
{
    Q_OBJECT

    public:
        
    explicit ShortcutHandler(QObject *parent = 0);
    virtual ~ShortcutHandler();

    bool hasSeenAlt(const QWidget *widget) const; 
    bool isAltDown() const { return itsAltDown; }
    bool showShortcut(const QWidget *widget) const;

    private Q_SLOTS:

    void widgetDestroyed(QObject *o);

    protected:

    void updateWidget(QWidget *w);
    bool eventFilter(QObject *watched, QEvent *event);

    private:

    bool             itsAltDown;
    QSet<QWidget *>  itsSeenAlt,
                     itsUpdated;
    QList<QWidget *> itsOpenMenus;
};

}

#endif