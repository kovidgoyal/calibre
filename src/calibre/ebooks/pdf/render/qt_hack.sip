//Define the SIP wrapper to the qt_hack code
//Author - Kovid Goyal <kovid@kovidgoyal.net>

%Module(name=qt_hack, version=1)

%Import QtCore/QtCoremod.sip
%Import QtGui/QtGuimod.sip

class GlyphInfo {
%TypeHeaderCode
#include <qt_hack.h>
%End
public:
    QByteArray name;
    qreal size;
    qreal stretch;
    QVector<QPointF> &positions;
    QVector<unsigned int> indices;
    GlyphInfo(const QByteArray &name, qreal size, qreal stretch, const QVector<QPointF> &positions, const QVector<unsigned int> &indices);
private:
    GlyphInfo(const GlyphInfo& g);

};

GlyphInfo* get_glyphs(QPointF &p, const QTextItem &text_item);

QByteArray get_sfnt_table(const QTextItem &text_item, const char* tag_name);

QVector<unsigned int>* get_glyph_map(const QTextItem &text_item);
