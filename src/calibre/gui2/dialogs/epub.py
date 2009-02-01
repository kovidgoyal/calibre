#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
The GUI for conversion to EPUB.
'''
import os

from PyQt4.Qt import QDialog, QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit, \
                     QTextEdit, QCheckBox, Qt, QPixmap, QIcon, QListWidgetItem, SIGNAL
from lxml.etree import XPath

from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2.dialogs.epub_ui import Ui_Dialog 
from calibre.gui2 import error_dialog, choose_images, pixmap_to_data, ResizableDialog
from calibre.ebooks.epub.from_any import SOURCE_FORMATS, config as epubconfig
from calibre.ebooks.metadata import MetaInformation
from calibre.ptempfile import PersistentTemporaryFile
from calibre.ebooks.metadata.opf import OPFCreator
from calibre.ebooks.metadata import authors_to_string, string_to_authors


class Config(ResizableDialog, Ui_Dialog):
    
    OUTPUT = 'EPUB'
        
    def __init__(self, parent, db, row=None, config=epubconfig):
        ResizableDialog.__init__(self, parent)
        self.hide_controls()
        self.connect(self.category_list, SIGNAL('itemEntered(QListWidgetItem *)'),
                        self.show_category_help)
        self.connect(self.cover_button, SIGNAL("clicked()"), self.select_cover)
        
        self.cover_changed = False
        self.db = db
        self.id = None
        self.row = row
        if row is not None:
            self.id = db.id(row)
            base = config().as_string() + '\n\n'
            defaults = self.db.conversion_options(self.id, self.OUTPUT.lower())
            defaults = base + (defaults if defaults else '')
            self.config = config(defaults=defaults)
        else:
            self.config = config()
        self.initialize()
        self.get_source_format()
        self.category_list.setCurrentRow(0)
        if self.row is None:
            self.setWindowTitle(_('Bulk convert to ')+self.OUTPUT)
        else:
            self.setWindowTitle((_(u'Convert %s to ')%unicode(self.title.text()))+self.OUTPUT)
    
    def hide_controls(self):
        self.source_profile_label.setVisible(False)
        self.opt_source_profile.setVisible(False)
        self.dest_profile_label.setVisible(False)
        self.opt_dest_profile.setVisible(False)
        self.opt_toc_title.setVisible(False)
        self.toc_title_label.setVisible(False)
        self.opt_rescale_images.setVisible(False)
        self.opt_ignore_tables.setVisible(False)
        self.opt_prefer_author_sort.setVisible(False)
        
    def initialize(self):
        self.__w = []
        self.__w.append(QIcon(':/images/dialog_information.svg'))
        self.item1 = QListWidgetItem(self.__w[-1], _('Metadata'), self.category_list)
        self.__w.append(QIcon(':/images/lookfeel.svg'))
        self.item2 = QListWidgetItem(self.__w[-1], _('Look & Feel').replace(' ','\n'), self.category_list)
        self.__w.append(QIcon(':/images/page.svg'))
        self.item3 = QListWidgetItem(self.__w[-1], _('Page Setup').replace(' ','\n'), self.category_list)
        self.__w.append(QIcon(':/images/chapters.svg'))
        self.item4 = QListWidgetItem(self.__w[-1], _('Chapter Detection').replace(' ','\n'), self.category_list)
        self.setup_tooltips()
        self.initialize_options()
    
    def set_help(self, msg):
        if msg and getattr(msg, 'strip', lambda:True)():
            self.help_view.setPlainText(msg)
        
    def setup_tooltips(self):
        for opt in self.config.option_set.preferences:
            g = getattr(self, 'opt_'+opt.name, False)
            if opt.help and g:
                help = opt.help.replace('%default', str(opt.default))
                g._help = help
                g.setToolTip(help.replace('<', '&lt;').replace('>', '&gt;'))
                g.setWhatsThis(help.replace('<', '&lt;').replace('>', '&gt;'))
                g.__class__.enterEvent = lambda obj, event: self.set_help(getattr(obj, '_help', obj.toolTip()))
    
    def show_category_help(self, item):
        text = unicode(item.text())
        help = {
                _('Metadata')          : _('Specify metadata such as title and author for the book.\n\nMetadata will be updated in the database as well as the generated %s file.')%self.OUTPUT,
                _('Look & Feel')       : _('Adjust the look of the generated ebook by specifying things like font sizes.'),
                _('Page Setup')        : _('Specify the page layout settings like margins.'),
                _('Chapter Detection') : _('Fine tune the detection of chapter and section headings.'),                  
                }
        self.set_help(help[text.replace('\n', ' ')])
    
    def select_cover(self):
        files = choose_images(self, 'change cover dialog', 
                             _('Choose cover for ') + unicode(self.title.text()))
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self.window, _('Cannot read'), 
                        _('You do not have permission to read the file: ') + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e: 
                d = error_dialog(self.window, _('Error reading file'),
                        _("<p>There was an error reading from file: <br /><b>") + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover)
                if pix.isNull():
                    d = error_dialog(self.window, _file + _(" is not a valid picture"))
                    d.exec_()
                else:
                    self.cover_path.setText(_file)
                    self.cover.setPixmap(pix)
                    self.cover_changed = True
                    self.cpixmap = pix
                
    def initialize_metadata_options(self):
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))
        for series in all_series:
            self.series.addItem(series[1])
        self.series.setCurrentIndex(-1)
            
        if self.row is not None:
            mi = self.db.get_metadata(self.id, index_is_id=True)
            self.title.setText(mi.title)
            if mi.authors:
                self.author.setText(authors_to_string(mi.authors))
            else:
                self.author.setText('')
            self.publisher.setText(mi.publisher if mi.publisher else '')
            self.author_sort.setText(mi.author_sort if mi.author_sort else '')
            self.tags.setText(', '.join(mi.tags if mi.tags else []))
            self.comment.setText(mi.comments if mi.comments else '')
            if mi.series:
                self.series.setCurrentIndex(self.series.findText(mi.series))
            if mi.series_index is not None:
                self.series_index.setValue(mi.series_index)
                
            cover = self.db.cover(self.id, index_is_id=True)
            if cover:
                pm = QPixmap()
                pm.loadFromData(cover)
                if not pm.isNull(): 
                    self.cover.setPixmap(pm)  
                
    def get_title_and_authors(self):
        title = unicode(self.title.text()).strip()
        if not title:
            title = _('Unknown')
        authors = unicode(self.author.text()).strip()
        authors = string_to_authors(authors) if authors else [_('Unknown')]
        return title, authors
    
    def get_metadata(self):
        title, authors = self.get_title_and_authors()
        mi = MetaInformation(title, authors)
        publisher = unicode(self.publisher.text())
        if publisher:
            mi.publisher = publisher
        author_sort = unicode(self.author_sort.text())
        if author_sort:
            mi.author_sort = author_sort
        comments = unicode(self.comment.toPlainText())
        if comments:
            mi.comments = comments
        mi.series_index = int(self.series_index.value())
        if self.series.currentIndex() > -1:
            mi.series = unicode(self.series.currentText())
        tags = [t.strip() for t in unicode(self.tags.text()).split(',')]
        if tags:
            mi.tags = tags
            
        return mi
    
    def read_settings(self):
        for pref in self.config.option_set.preferences:
            g = getattr(self, 'opt_'+pref.name, False)
            if g:
                if isinstance(g, (QSpinBox, QDoubleSpinBox)):
                    self.config.set(pref.name, g.value())
                elif isinstance(g, (QLineEdit, QTextEdit)):
                    func = getattr(g, 'toPlainText', getattr(g, 'text', None))()
                    val = unicode(func)
                    self.config.set(pref.name, val if val else None)
                elif isinstance(g, QComboBox):
                    self.config.set(pref.name, unicode(g.currentText()))
                elif isinstance(g, QCheckBox):
                    self.config.set(pref.name, bool(g.isChecked()))
        if self.row is not None:
            self.db.set_conversion_options(self.id, self.OUTPUT.lower(), self.config.src)        
        
    
    def initialize_options(self):
        self.initialize_metadata_options()
        values = self.config.parse()
        for pref in self.config.option_set.preferences:
            g = getattr(self, 'opt_'+pref.name, False)
            if g:
                val = getattr(values, pref.name)
                if val is None:
                    continue
                if isinstance(g, (QSpinBox, QDoubleSpinBox)):
                    g.setValue(val)
                elif isinstance(g, (QLineEdit, QTextEdit)):
                    getattr(g, 'setPlainText', g.setText)(val)
                elif isinstance(g, QComboBox):
                    for value in pref.choices:
                        g.addItem(value)
                    g.setCurrentIndex(g.findText(val))
                elif isinstance(g, QCheckBox):
                    g.setCheckState(Qt.Checked if bool(val) else Qt.Unchecked)
                    
        
    def get_source_format(self):
        self.source_format = None
        if self.row is not None:
            temp = self.db.formats(self.id, index_is_id=True)
            if not temp:
                error_dialog(self.parent(), _('Cannot convert'), 
                             _('This book has no available formats')).exec_()
                
            available_formats = [f.upper().strip() for f in temp.split(',')]
            choices = [fmt.upper() for fmt in SOURCE_FORMATS if fmt.upper() in available_formats]
            if not choices:
                error_dialog(self.parent(), _('No available formats'),
                            _('Cannot convert %s as this book has no supported formats')%(self.title.text())).exec_()
            elif len(choices) == 1:
                self.source_format = choices[0]
            else:
                d = ChooseFormatDialog(self.parent(), _('Choose the format to convert to ')+self.OUTPUT, choices)
                if d.exec_() == QDialog.Accepted:
                    self.source_format = d.format()
                
    def accept(self):
        for opt in ('chapter', 'level1_toc', 'level2_toc', 'level3_toc'):
            text = unicode(getattr(self, 'opt_'+opt).text())
            if text:
                try:
                    XPath(text,namespaces={'re':'http://exslt.org/regular-expressions'})
                except Exception, err:
                    error_dialog(self, _('Invalid XPath expression'),
                        _('The expression %s is invalid. Error: %s')%(text, err) 
                                 ).exec_()
                    return
        mi = self.get_metadata()
        self.read_settings()
        self.cover_file = None
        if self.row is not None:
            self.db.set_metadata(self.id, mi)
            self.mi = self.db.get_metadata(self.id, index_is_id=True)
            opf = OPFCreator(os.getcwdu(), self.mi)
            self.opf_file = PersistentTemporaryFile('.opf')
            opf.render(self.opf_file)
            self.opf_file.close()
            if self.cover_changed:
                self.db.set_cover(self.id, pixmap_to_data(self.cover.pixmap()))
            cover = self.db.cover(self.id, index_is_id=True)
            if cover:
                cf = PersistentTemporaryFile('.jpeg')
                cf.write(cover)
                cf.close()
                self.cover_file = cf
        self.opts = self.config.parse()
        QDialog.accept(self)
        
            