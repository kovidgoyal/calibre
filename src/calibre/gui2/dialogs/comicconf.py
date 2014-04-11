from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

''''''
from PyQt5.QtGui import QDialog
from calibre.gui2.dialogs.comicconf_ui import Ui_Dialog
from calibre.ebooks.lrf.comic.convert_from import config, PROFILES

def set_conversion_defaults(window):
    d = ComicConf(window)
    d.exec_()

def get_bulk_conversion_options(window):
    d = ComicConf(window, config_defaults=config(None).as_string())
    if d.exec_() == QDialog.Accepted:
        return d.config.parse()

def get_conversion_options(window, defaults, title, author):
    if defaults is None:
        defaults = config(None).as_string()
    defaults += '\ntitle=%s\nauthor=%s'%(repr(title), repr(author))
    d = ComicConf(window, config_defaults=defaults, generic=False)
    if d.exec_() == QDialog.Accepted:
        return d.config.parse(), d.config.src
    return None, None


class ComicConf(QDialog, Ui_Dialog):

    def __init__(self, window, config_defaults=None, generic=True,
                 title=_('Set defaults for conversion of comics (CBR/CBZ files)')):
        QDialog.__init__(self, window)
        Ui_Dialog.__init__(self)
        self.setupUi(self)
        self.setWindowTitle(title)
        self.config = config(config_defaults)
        opts = self.config.parse()
        if generic:
            for i in ('title', 'author'):
                getattr(self, 'opt_'+i).setVisible(False)
                getattr(self, i+'_label').setVisible(False)
        else:
            title = opts.title
            if not title:
                title = _('Unknown')
            self.setWindowTitle(_('Set options for converting %s')%title)
            author = opts.author
            self.opt_title.setText(title)
            self.opt_author.setText(author)
        self.opt_colors.setValue(opts.colors)
        self.opt_profile.addItem(opts.profile)
        for x in PROFILES.keys():
            if x != opts.profile:
                self.opt_profile.addItem(x)
        self.opt_dont_normalize.setChecked(opts.dont_normalize)
        self.opt_keep_aspect_ratio.setChecked(opts.keep_aspect_ratio)
        self.opt_dont_sharpen.setChecked(opts.dont_sharpen)
        self.opt_landscape.setChecked(opts.landscape)
        self.opt_no_sort.setChecked(opts.no_sort)
        self.opt_despeckle.setChecked(opts.despeckle)
        self.opt_wide.setChecked(opts.wide)
        self.opt_right2left.setChecked(opts.right2left)

        for opt in self.config.option_set.preferences:
            g = getattr(self, 'opt_'+opt.name, False)
            if opt.help and g:
                g.setToolTip(opt.help)

    def accept(self):
        for opt in self.config.option_set.preferences:
            g = getattr(self, 'opt_'+opt.name, False)
            if not g or not g.isVisible(): continue
            if hasattr(g, 'isChecked'):
                val = bool(g.isChecked())
            elif hasattr(g, 'value'):
                val = g.value()
            elif hasattr(g, 'itemText'):
                val = unicode(g.itemText(g.currentIndex()))
            elif hasattr(g, 'text'):
                val = unicode(g.text())
            else:
                raise Exception('Bad coding')
            self.config.set(opt.name, val)
        return QDialog.accept(self)
