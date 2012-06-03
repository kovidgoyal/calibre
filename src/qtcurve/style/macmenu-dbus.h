/* Bespin mac-a-like XBar KDE4
Copyright (C) 2007 Thomas Luebking <thomas.luebking@web.de>

This library is free software; you can redistribute it and/or
modify it under the terms of the GNU Library General Public
License version 2 as published by the Free Software Foundation.

This library is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Library General Public License for more details.

   You should have received a copy of the GNU Library General Public License
   along with this library; see the file COPYING.LIB.  If not, write to
   the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
   Boston, MA 02110-1301, USA.
 */

#ifndef MAC_MENU_ADAPTOR_H
#define MAC_MENU_ADAPTOR_H

#include <QtDBus/QDBusAbstractAdaptor>
#include "macmenu.h"

namespace Bespin
{

class MacMenuAdaptor : public QDBusAbstractAdaptor
{
   Q_OBJECT
   Q_CLASSINFO("D-Bus Interface", "org.kde.XBarClient")

private:
   MacMenu *mm;

public:
   MacMenuAdaptor(MacMenu *macMenu) : QDBusAbstractAdaptor(macMenu), mm(macMenu) { }

public slots:
   Q_NOREPLY void activate() { mm->activate(); }
   Q_NOREPLY void deactivate() { mm->deactivate(); }
   Q_NOREPLY void popup(qlonglong key, int idx, int x, int y)
   { mm->popup(key, idx, x, y); }
   Q_NOREPLY void hover(qlonglong key, int idx, int x, int y)
   { mm->hover(key, idx, x, y); }
   Q_NOREPLY void popDown(qlonglong key) { mm->popDown(key); }
   Q_NOREPLY void raise(qlonglong key) { mm->raise(key); }
};
} // namespace

#endif //MAC_MENU_ADAPTOR_H
