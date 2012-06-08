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

#include <QActionEvent>
#include <QApplication>
#include <QtDBus/QDBusConnectionInterface>
#include <QtDBus/QDBusMessage>
#include <QLayout>
#include <QMenuBar>
#include <QWindowStateChangeEvent>

#include "macmenu.h"
#include "macmenu-dbus.h"

#include <QtDebug>

using namespace Bespin;

static MacMenu *instance = 0;
#define MSG(_FNC_) QDBusMessage::createMethodCall( "org.kde.XBar", "/XBar", "org.kde.XBar", _FNC_ )
#define XBAR_SEND( _MSG_ ) QDBusConnection::sessionBus().send( _MSG_ )

bool
FullscreenWatcher::eventFilter(QObject *o, QEvent *ev)
{
    QWidget *window = qobject_cast<QWidget*>(o);
    if (!(window && ev->type() == QEvent::WindowStateChange))
        return false;
    if (window->windowState() & Qt::WindowFullScreen)
        instance->deactivate(window);
    else
        instance->activate(window);
    return false;
}

static FullscreenWatcher *fullscreenWatcher = 0;

MacMenu::MacMenu() : QObject()
{
    usingMacMenu = QDBusConnection::sessionBus().interface()->isServiceRegistered("org.kde.XBar");
    service = QString("org.kde.XBar-%1").arg(QCoreApplication::applicationPid());
    // register me
    QDBusConnection::sessionBus().registerService(service);
    QDBusConnection::sessionBus().registerObject("/XBarClient", this);

    connect (qApp, SIGNAL(aboutToQuit()), this, SLOT(deactivate()));
}


void
MacMenu::manage(QMenuBar *menu)
{
    if (!menu) // ...
        return;
    
    // we only accept menus that are placed on a QMainWindow - for the moment, and probably ever
    QWidget *dad = menu->parentWidget();
    if (!(dad && dad->isWindow() && dad->inherits("QMainWindow") && dad->layout() && dad->layout()->menuBar() == menu))
        return;

//     if ((dad = dad->parentWidget()) && dad->inherits("QMdiSubWindow"))
//         return;
    

    if (!instance)
    {
        instance = new MacMenu;
        /*MacMenuAdaptor *adapt = */new MacMenuAdaptor(instance);
        fullscreenWatcher = new FullscreenWatcher;
    }
    else if (instance->items.contains(menu))
        return; // no double adds please!

    if (instance->usingMacMenu)
        instance->activate(menu);

    connect (menu, SIGNAL(destroyed(QObject *)), instance, SLOT(_release(QObject *)));

    instance->items.append(menu);
}

void
MacMenu::release(QMenuBar *menu)
{
    if (!instance)
        return;
    instance->_release(menu);
}

bool
MacMenu::isActive()
{
    return instance && instance->usingMacMenu;
}

void
MacMenu::_release(QObject *o)
{
    XBAR_SEND( MSG("unregisterMenu") << (qlonglong)o );

    QMenuBar *menu = qobject_cast<QMenuBar*>(o);
    if (!menu) return;

    items.removeAll(menu);
    menu->removeEventFilter(this);
    QWidget *dad = menu->parentWidget();
    if (dad && dad->layout())
        dad->layout()->setMenuBar(menu);
    menu->setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX);
    menu->adjustSize();
//    menu->updateGeometry();
}

void
MacMenu::activate()
{
    MenuList::iterator menu = items.begin();
    while (menu != items.end())
    {
        if (*menu)
            { activate(*menu); ++menu; }
        else
            { actions.remove(*menu); menu = items.erase(menu); }
    }
    usingMacMenu = true;
}

void
MacMenu::activate(QMenuBar *menu)
{
    menu->removeEventFilter(this);
    
    // and WOWWWW - no more per window menubars...
    menu->setFixedSize(0,0);
    //NOTICE i used to set the menu's parent->layout()->setMenuBar(0) to get rid of the free space
    // but this leeds to side effects (e.g. kcalc won't come up anymore...)
    // so now the stylehint for the free space below checks the menubar height and returns
    // a negative value so that final result will be 1 px heigh...
    menu->updateGeometry();
    
    // we need to hold a copy of this list to handle action removes
    // (as we get the event after the action has been removed from the widget...)
    actions[menu] = menu->actions();
    
    // find a nice header
    QString title = menu->window()->windowTitle();
    const QStringList appArgs = QCoreApplication::arguments();
    QString name = appArgs.isEmpty() ? "" : appArgs.at(0).section('/', -1);
    if (title.isEmpty())
        title = name;
    else
    {
        int i = title.indexOf(name, 0, Qt::CaseInsensitive);
        if (i > -1)
            title = title.mid(i, name.length());
    }
    title = title.section(" - ", -1);
    if (title.isEmpty())
    {
        if (!menu->actions().isEmpty())
            title = menu->actions().at(0)->text();
        if (title.isEmpty())
            title = "QApplication";
    }
    
    // register the menu via dbus
    QStringList entries;
    foreach (QAction* action, menu->actions())
        if (action->isSeparator())
            entries << "<XBAR_SEPARATOR/>";
        else
            entries << action->text();
    XBAR_SEND( MSG("registerMenu") << service << (qlonglong)menu << title << entries );
    // TODO cause of now async call, the following should - maybe - attached to the above?!!
    if (menu->isActiveWindow())
        XBAR_SEND( MSG("requestFocus") << (qlonglong)menu );
    
    // take care of several widget events!
    menu->installEventFilter(this);
    if (menu->window())
    {
        menu->window()->removeEventFilter(fullscreenWatcher);
        menu->window()->installEventFilter(fullscreenWatcher);
    }
}

void
MacMenu::activate(QWidget *window)
{
    MenuList::iterator menu = items.begin();
    while (menu != items.end())
    {
        if (*menu)
        {
            if ((*menu)->window() == window)
                { activate(*menu); return; }
            ++menu;
        }
        else
            { actions.remove(*menu); menu = items.erase(menu); }
    }
}

void
MacMenu::deactivate()
{
    usingMacMenu = false;

    MenuList::iterator i = items.begin();
    QMenuBar *menu = 0;
    while (i != items.end())
    {
        actions.remove(*i);
        if ((menu = *i))
        {
            deactivate(menu);
            ++i;
        }
        else
            i = items.erase(i);
    }
}

void
MacMenu::deactivate(QMenuBar *menu)
{
    menu->removeEventFilter(this);
    QWidget *dad = menu->parentWidget();
    if (dad && dad->layout())
        dad->layout()->setMenuBar(menu);
    menu->setMaximumSize(QWIDGETSIZE_MAX, QWIDGETSIZE_MAX);
    menu->adjustSize();
    //             menu->updateGeometry();
}

void
MacMenu::deactivate(QWidget *window)
{
    MenuList::iterator menu = items.begin();
    while (menu != items.end())
    {
        if (*menu)
        {
            if ((*menu)->window() == window)
                { deactivate(*menu); return; }
            ++menu;
        }
        else
        { actions.remove(*menu); menu = items.erase(menu); }
    }
}

QMenuBar *
MacMenu::menuBar(qlonglong key)
{
    MenuList::iterator i = items.begin();
    QMenuBar *menu;
    while (i != items.end())
    {
        if (!(menu = *i))
        {
            actions.remove(menu);
            i = items.erase(i);
        }
        else
        {
            if ((qlonglong)menu == key)
                return menu;
            else
                ++i;
        }
    }
    return NULL;
}

void
MacMenu::popup(qlonglong key, int idx, int x, int y)
{
    QMenuBar *menu = menuBar(key);
    if (!menu) return;

    QMenu *pop;
    for (int i = 0; i < menu->actions().count(); ++i)
    {
        if (!(pop = menu->actions().at(i)->menu()))
            continue;

        if (i == idx) {
            if (!pop->isVisible())
            {
                connect (pop, SIGNAL(aboutToHide()), this, SLOT(menuClosed()));
                XBAR_SEND( MSG("setOpenPopup") << idx );
                pop->popup(QPoint(x,y));
            }
            else
            {
                XBAR_SEND( MSG("setOpenPopup") << -1000 );
                pop->hide();
            }
        }
        else
            pop->hide();
    }
}

void
MacMenu::popDown(qlonglong key)
{
    QMenuBar *menu = menuBar(key);
    if (!menu) return;

    QWidget *pop;
    for (int i = 0; i < menu->actions().count(); ++i)
    {
        if (!(pop = menu->actions().at(i)->menu()))
            continue;
        disconnect (pop, SIGNAL(aboutToHide()), this, SLOT(menuClosed()));
        pop->hide();
//         menu->activateWindow();
        break;
    }
}

static bool inHover = false;

void
MacMenu::hover(qlonglong key, int idx,  int x, int y)
{
    QMenuBar *menu = menuBar(key);
    if (!menu) return;

    QWidget *pop;
    for (int i = 0; i < menu->actions().count(); ++i)
    {
        if ((i == idx) || !(pop = menu->actions().at(i)->menu()))
            continue;
        if (pop->isVisible())
        {
            inHover = true;
            popup(key, idx, x, y); // TODO: this means a useless second pass above...
            inHover = false;
            break;
        }
    }
}

static QMenuBar *bar4menu(QMenu *menu)
{
    if (!menu->menuAction())
        return 0;
    if (menu->menuAction()->associatedWidgets().isEmpty())
        return 0;
    foreach (QWidget *w, menu->menuAction()->associatedWidgets())
        if (qobject_cast<QMenuBar*>(w))
            return static_cast<QMenuBar *>(w);
    return 0;
}

void
MacMenu::menuClosed()
{
    QObject * _sender = sender();
    
    if (!_sender)
        return;

    disconnect (sender(), SIGNAL(aboutToHide()), this, SLOT(menuClosed()));
    if (!inHover)
    {
        XBAR_SEND( MSG("setOpenPopup") << -500 );

        if (QMenu *menu = qobject_cast<QMenu*>(_sender))
        if (QMenuBar *bar = bar4menu(menu))
            bar->activateWindow();
    }
}

void
MacMenu::changeAction(QMenuBar *menu, QActionEvent *ev)
{
    int idx;
    const QString title = ev->action()->isSeparator() ? "<XBAR_SEPARATOR/>" : ev->action()->text();
    if (ev->type() == QEvent::ActionAdded)
    {
        idx = ev->before() ? menu->actions().indexOf(ev->before())-1 : -1;
        XBAR_SEND( MSG("addEntry") << (qlonglong)menu << idx << title );
        actions[menu].insert(idx, ev->action());
        return;
    }
    if (ev->type() == QEvent::ActionChanged)
    {
        idx = menu->actions().indexOf(ev->action());
        XBAR_SEND( MSG("changeEntry") << (qlonglong)menu << idx << title );
    }
    else
    { // remove
        idx = actions[menu].indexOf(ev->action());
        actions[menu].removeAt(idx);
        XBAR_SEND( MSG("removeEntry") << (qlonglong)menu << idx );
    }
}

void
MacMenu::raise(qlonglong key)
{
    if (QMenuBar *menu = menuBar(key))
    {
        if (QWidget *win = menu->window())
        {
            win->showNormal();
            win->activateWindow();
            win->raise();
        }
    }
}

bool
MacMenu::eventFilter(QObject *o, QEvent *ev)
{
    QMenuBar *menu = qobject_cast<QMenuBar*>(o);
    if (!menu)
        return false;

    if (!usingMacMenu)
        return false;

    QString func;
    switch (ev->type())
    {
    case QEvent::Resize:
//         menu->setSizePolicy(QSizePolicy(QSizePolicy::Ignored, QSizePolicy::Ignored));
        if (menu->size() != QSize(0,0))
        {
            menu->setFixedSize(0,0);
            menu->updateGeometry();
        }
        break;
    case QEvent::ActionAdded:
    case QEvent::ActionChanged:
    case QEvent::ActionRemoved:
        changeAction(menu, static_cast<QActionEvent*>(ev));
        break;
//     case QEvent::ParentChange:
//         qDebug() << o << ev;
//         return false;
    case QEvent::EnabledChange:
        if (static_cast<QWidget*>(o)->isEnabled())
            XBAR_SEND( MSG("requestFocus") << (qlonglong)menu );
        else
            XBAR_SEND( MSG("releaseFocus") << (qlonglong)menu );
        break;

    // TODO: test whether this is the only one and show it? (e.g. what about dialogs...?!)
    case QEvent::ApplicationActivate:
//         if (items.count() > 1)
//             break;
    case QEvent::WindowActivate:
        XBAR_SEND( MSG("requestFocus") << (qlonglong)menu );
        break;

    case QEvent::WindowDeactivate:
//         if (items.count() == 1)
//             break;
    case QEvent::WindowBlocked:
    case QEvent::ApplicationDeactivate:
        XBAR_SEND( MSG("releaseFocus") << (qlonglong)menu );
        break;
    default:
        return false;

// maybe these need to be passed through...?!
//       QEvent::GrabKeyboard
//       QEvent::GrabMouse
//       QEvent::KeyPress
//       QEvent::KeyRelease
//       QEvent::UngrabKeyboard
//       QEvent::UngrabMouse
// --- and what about these ---
//       QEvent::MenubarUpdated
//       QEvent::ParentChange
// -------------------
    }
    return false;
}

#undef MSG
#undef XBAR_SEND
