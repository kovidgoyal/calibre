#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QDialog, QGridLayout, QIcon, QCheckBox, QLabel, QFrame,
                      QApplication, QDialogButtonBox, Qt, QSize, QSpacerItem,
                      QSizePolicy)

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction

SUPPORTED = {'EPUB', 'AZW3'}

class Polish(QDialog):

    def __init__(self, db, book_id_map, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowIcon(QIcon(I('polish.png')))
        self.setWindowTitle(ngettext(
            'Polish book', _('Polish %d books')%len(book_id_map), len(book_id_map)))

        # Help {{{
        self.help_text = {
            'polish':_(
                '''
                <h3>About Polishing books</h3>

                <p><i>Polishing books</i> is all about putting the shine of
                perfection onto your carefully crafted ebooks.</p>

                <p>Polishing tries to minimize the changes to the internal code
                of your ebook. Unlike conversion, it <i>does not</i> flatten CSS,
                rename files, change font sizes, adjust margins, etc. Every
                action to the left performs only the minimum set of changes
                needed for the desired effect.</p>

                <p>You should use this tool as the last step in your ebook
                creation process.</p>

                <p>Note that polishing only works on files in the
                <b>%s</b> formats.</p>
                ''')%_(' or ').join(SUPPORTED),

            'subset':_(
                '''
                <h3>Subsetting fonts</h3>

                <p>Subsetting fonts means reducing an embedded font to contain
                only the characters used from that font in the book. This
                greatly reduces the size of the font files (halving the font
                file sizes is common).</p>

                <p>For example, if the book uses a specific font for headers,
                then subsetting will reduce that font to contain only the
                characters present in the actual headers in the book. Or if the
                book embeds the bold and italic versions of a font, but bold
                and italic text is relatively rare, or absent altogether, then
                the bold and italic fonts can either be reduced to only a few
                characters or completely removed.</p>

                <p>The only downside to subsetting fonts is that if, at a later
                date you decide to add more text to your books, the newly added
                text might not be covered by the subset font.</p>
                '''),
        } # }}}

        self.l = l = QGridLayout()
        self.setLayout(l)

        self.la = la = QLabel('<b>'+_('Select actions to perform:'))
        l.addWidget(la, 0, 0, 1, 2)

        count = 0

        for name, text in (
            ('subset', _('Subset all embedded fonts')),
                           ):
            count += 1
            x = QCheckBox(text, self)
            l.addWidget(x, count, 0, 1, 1)
            setattr(self, 'opt_'+name, x)
            la = QLabel(' <a href="#%s">%s</a>'%(name, _('About')))
            setattr(self, 'label_'+name, x)
            la.linkActivated.connect(self.help_link_activated)
            l.addWidget(la, count, 1, 1, 1)

        count += 1
        l.addItem(QSpacerItem(10, 10, vPolicy=QSizePolicy.Expanding), count, 1, 1, 2)

        la = self.help_label = QLabel('')
        self.help_link_activated('#polish')
        la.setWordWrap(True)
        la.setTextFormat(Qt.RichText)
        la.setFrameShape(QFrame.StyledPanel)
        la.setAlignment(Qt.AlignLeft|Qt.AlignTop)
        la.setLineWidth(2)
        la.setStyleSheet('QLabel { margin-left: 75px }')
        l.addWidget(la, 0, 2, count+1, 1)
        l.setColumnStretch(2, 1)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        l.addWidget(bb, count+1, 0, 1, -1)

        self.resize(QSize(800, 600))

    def help_link_activated(self, link):
        link = unicode(link)[1:]
        self.help_label.setText(self.help_text[link])

    def accept(self):
        self.actions = ac = {}
        something = False
        for action in ('subset',):
            ac[action] = bool(getattr(self, 'opt_'+action).isChecked())
            if ac[action]:
                something = True
        if not something:
            return error_dialog(self, _('No actions selected'),
                _('You must select at least one action, or click Cancel.'),
                                show=True)
        return super(Polish, self).accept()

class PolishAction(InterfaceAction):

    name = 'Polish Books'
    action_spec = (_('Polish books'), 'polish.png', None, None)
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.polish_books)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def get_books_for_polishing(self):
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot polish'),
                    _('No books selected'))
            d.exec_()
            return None
        db = self.gui.library_view.model().db
        ans = (db.id(r) for r in rows)
        supported = set(SUPPORTED)
        for x in SUPPORTED:
            supported.add('ORIGINAL_'+x)
        ans = {x:set( (db.formats(x, index_is_id=True) or '').split(',') )
               .intersection(supported) for x in ans}
        ans = {x:fmts for x, fmts in ans.iteritems() if fmts}
        if not ans:
            error_dialog(self.gui, _('Cannot polish'),
                _('Polishing is only supported for books in the %s'
                  ' formats. Convert to one of those formats before polishing.')
                         %_(' or ').join(sorted(SUPPORTED)), show=True)
        for fmts in ans.itervalues():
            for x in SUPPORTED:
                if ('ORIGINAL_'+x) in fmts:
                    fmts.discard(x)
        return ans

    def polish_books(self):
        book_id_map = self.get_books_for_polishing()
        if not book_id_map:
            return
        d = Polish(self.gui.library_view.model().db, book_id_map, parent=self.gui)
        if d.exec_() == d.Accepted:
            pass

if __name__ == '__main__':
    app = QApplication([])
    app
    from calibre.library import db
    d = Polish(db(), {1:{'EPUB'}, 2:{'AZW3'}})
    d.exec_()

