/****************************************************************************

 Copyright (C) 2003 Lubos Lunak        <l.lunak@kde.org>

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.

****************************************************************************/


//#ifdef    don't do this, this file is supposed to be included
//#define   multiple times

#include <QtCore/QtGlobal>

#ifdef Q_WS_X11

/* Usage:

 If you get compile errors caused by X11 includes (the line
 where first error appears contains word like None, Unsorted,
 Below, etc.), put #include <fixx11h.h> in the .cpp file
 (not .h file!) between the place where X11 headers are
 included and the place where the file with compile
 error is included (or the place where the compile error
 in the .cpp file occurs).

 This file remaps X11 #defines to const variables or
 inline functions. The side effect may be that these
 symbols may now refer to different variables
 (e.g. if X11 #defined NoButton, after this file
 is included NoButton would no longer be X11's
 NoButton, but Qt::NoButton instead). At this time,
 there's no conflict known that could cause problems.

 The original X11 symbols are still accessible
 (e.g. for None) as X::None, XNone, and also still
 None, unless name lookup finds different None
 first (in the current class, etc.)

 Use 'Unsorted', 'Bool' and 'index' as templates.

*/

namespace X
{

// template --->
// Affects: Should be without side effects.
#ifdef Unsorted
#ifndef FIXX11H_Unsorted
#define FIXX11H_Unsorted
const int XUnsorted = Unsorted;
#undef Unsorted
const int Unsorted = XUnsorted;
#endif
#undef Unsorted
#endif
// template <---

// Affects: Should be without side effects.
#ifdef None
#ifndef FIXX11H_None
#define FIXX11H_None
const XID XNone = None;
#undef None
const XID None = XNone;
#endif
#undef None
#endif

// template --->
// Affects: Should be without side effects.
#ifdef Bool
#ifndef FIXX11H_Bool
#define FIXX11H_Bool
#ifdef _XTYPEDEF_BOOL /* Xdefs.h has typedef'ed Bool already */
 #undef Bool
#else
 typedef Bool XBool;
 #undef Bool
 typedef XBool Bool;
#endif
#endif
#undef Bool
#define _XTYPEDEF_BOOL
#endif
// template <---

// Affects: Should be without side effects.
#ifdef KeyPress
#ifndef FIXX11H_KeyPress
#define FIXX11H_KeyPress
const int XKeyPress = KeyPress;
#undef KeyPress
const int KeyPress = XKeyPress;
#endif
#undef KeyPress
#endif

// Affects: Should be without side effects.
#ifdef KeyRelease
#ifndef FIXX11H_KeyRelease
#define FIXX11H_KeyRelease
const int XKeyRelease = KeyRelease;
#undef KeyRelease
const int KeyRelease = XKeyRelease;
#endif
#undef KeyRelease
#endif

// Affects: Should be without side effects.
#ifdef Above
#ifndef FIXX11H_Above
#define FIXX11H_Above
const int XAbove = Above;
#undef Above
const int Above = XAbove;
#endif
#undef Above
#endif

// Affects: Should be without side effects.
#ifdef Below
#ifndef FIXX11H_Below
#define FIXX11H_Below
const int XBelow = Below;
#undef Below
const int Below = XBelow;
#endif
#undef Below
#endif

// Affects: Should be without side effects.
#ifdef FocusIn
#ifndef FIXX11H_FocusIn
#define FIXX11H_FocusIn
const int XFocusIn = FocusIn;
#undef FocusIn
const int FocusIn = XFocusIn;
#endif
#undef FocusIn
#endif

// Affects: Should be without side effects.
#ifdef FocusOut
#ifndef FIXX11H_FocusOut
#define FIXX11H_FocusOut
const int XFocusOut = FocusOut;
#undef FocusOut
const int FocusOut = XFocusOut;
#endif
#undef FocusOut
#endif

// Affects: Should be without side effects.
#ifdef Always
#ifndef FIXX11H_Always
#define FIXX11H_Always
const int XAlways = Always;
#undef Always
const int Always = XAlways;
#endif
#undef Always
#endif

// Affects: Should be without side effects.
#ifdef Success
#ifndef FIXX11H_Success
#define FIXX11H_Success
const int XSuccess = Success;
#undef Success
const int Success = XSuccess;
#endif
#undef Success
#endif

// Affects: Should be without side effects.
#ifdef GrayScale
#ifndef FIXX11H_GrayScale
#define FIXX11H_GrayScale
const int XGrayScale = GrayScale;
#undef GrayScale
const int GrayScale = XGrayScale;
#endif
#undef GrayScale
#endif

// Affects: Should be without side effects.
#ifdef Status
#ifndef FIXX11H_Status
#define FIXX11H_Status
typedef Status XStatus;
#undef Status
typedef XStatus Status;
#endif
#undef Status
#endif

// Affects: Should be without side effects.
#ifdef CursorShape
#ifndef FIXX11H_CursorShape
#define FIXX11H_CursorShape
const int XCursorShape = CursorShape;
#undef CursorShape
const int CursorShape = CursorShape;
#endif
#undef CursorShape
#endif

// template --->
// Affects: Should be without side effects.
#ifdef CursorShape
#ifndef FIXX11H_CursorShape
#define FIXX11H_CursorShape
const int XCursorShape = CursorShape;
#undef CursorShape
const int CursorShape = XCursorShape;
#endif
#undef CursorShape
#endif
// template <---

// template --->
// Affects: Should be without side effects.
#ifdef FontChange
#ifndef FIXX11H_FontChange
#define FIXX11H_FontChange
const int XFontChange = FontChange;
#undef FontChange
const int FontChange = XFontChange;
#endif
#undef FontChange
#endif
// template <---

// Affects: Should be without side effects.
#ifdef NormalState
#ifndef FIXX11H_NormalState
#define FIXX11H_NormalState
const int XNormalState = NormalState;
#undef NormalState
const int NormalState = XNormalState;
#endif
#undef NormalState
#endif

// template --->
// Affects: Should be without side effects.
#ifdef index
#ifndef FIXX11H_index
#define FIXX11H_index
inline
const char* Xindex( const char* s, int c )
    {
    return index( s, c );
    }
#undef index
inline
const char* index( const char* s, int c )
    {
    return Xindex( s, c );
    }
#endif
#undef index
#endif
// template <---

#ifdef rindex
// Affects: Should be without side effects.
#ifndef FIXX11H_rindex
#define FIXX11H_rindex
inline
const char* Xrindex( const char* s, int c )
    {
    return rindex( s, c );
    }
#undef rindex
inline
const char* rindex( const char* s, int c )
    {
    return Xrindex( s, c );
    }
#endif
#undef rindex
#endif
}

using namespace X;

#endif
