//Define the SIP wrapper to the qt_hack code
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=qt_hack)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip
%ModuleCode
#include <qt_hack.h>
%End

PyObject* get_glyphs(const QPointF &p, const QTextItem &text_item);

PyObject* get_sfnt_table(const QTextItem &text_item, const char* tag_name);

PyObject* get_glyph_map(const QTextItem &text_item);
