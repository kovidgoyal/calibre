__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import os, codecs

from PyQt4.QtCore import QObject, SIGNAL, Qt
from PyQt4.QtGui import QAbstractSpinBox, QLineEdit, QCheckBox, QDialog, \
                        QPixmap, QTextEdit, QListWidgetItem, QIcon

from calibre.gui2.dialogs.lrf_single_ui import Ui_LRFSingleDialog
from calibre.gui2.dialogs.choose_format import ChooseFormatDialog
from calibre.gui2 import qstring_to_unicode, error_dialog, \
                           pixmap_to_data, choose_images, config
from calibre.gui2.widgets import FontFamilyModel
from calibre.ebooks.lrf import option_parser
from calibre.ptempfile import PersistentTemporaryFile
from calibre.constants import __appname__
from calibre.ebooks.metadata import authors_to_string, string_to_authors, authors_to_sort_string

font_family_model = None

class LRFSingleDialog(QDialog, Ui_LRFSingleDialog):
    
    PARSER = option_parser('')
    PREPROCESS_OPTIONS = [ o for o in PARSER.option_groups if o.title == 'PREPROCESSING OPTIONS'][0].option_list
    
    @classmethod
    def options(cls):
        options = cls.PARSER.option_list
        for g in cls.PARSER.option_groups:
            options.extend(g.option_list)
        for opt in options:
            yield opt
    
    @classmethod
    def option_to_name(cls, opt):
        src = opt.get_opt_string()
        return 'gui_' + src[2:].replace('-', '_')
    
    def initialize_common(self):
        self.output_format = 'LRF'
        self.setup_tooltips()
        self.initialize_options()
        global font_family_model
        if font_family_model is None:
            font_family_model = FontFamilyModel()
        self.font_family_model = font_family_model
        self.gui_serif_family.setModel(self.font_family_model)
        self.gui_sans_family.setModel(self.font_family_model)
        self.gui_mono_family.setModel(self.font_family_model)
        self.load_saved_global_defaults()
    
    def populate_list(self):
        self.__w = []
        self.__w.append(QIcon(':/images/dialog_information.svg'))
        self.item1 = QListWidgetItem(self.__w[-1], _("Metadata"), self.categoryList)
        self.__w.append(QIcon(':/images/lookfeel.svg'))
        self.item2 = QListWidgetItem(self.__w[-1], _('Look & Feel'), self.categoryList)
        self.__w.append(QIcon(':/images/page.svg'))
        self.item3 = QListWidgetItem(self.__w[-1], _('Page Setup'), self.categoryList)
        self.__w.append(QIcon(':/images/chapters.svg'))
        self.item4 = QListWidgetItem(self.__w[-1], _('Chapter Detection'), self.categoryList)
    
    def __init__(self, window, db, row):
        QDialog.__init__(self, window)
        Ui_LRFSingleDialog.__init__(self)
        self.setupUi(self)
        self.populate_list()
        self.categoryList.setCurrentRow(0)
        QObject.connect(self.categoryList, SIGNAL('itemEntered(QListWidgetItem *)'),
                        self.show_category_help)
        QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), self.select_cover)
        #self.categoryList.leaveEvent = self.reset_help
        self.reset_help()
        self.selected_format = None
        self.initialize_common()
        self.db = db
        self.row = row
        self.cover_changed = False
        self.cpixmap = None
        self.changed = False
        
        if db:
            self.id = self.db.id(self.row)
            self.read_saved_options()
            self.initialize_metadata()
            formats = self.db.formats(self.row)
            formats = [i.upper() for i in formats.split(',')] if formats else []
            try:
                formats.remove(self.output_format)
            except ValueError:
                pass        
            if not formats:
                d = error_dialog(window, _('No available formats'),
                        _('Cannot convert %s as this book has no supported formats')%(self.gui_title.text()))
                d.exec_()
        
            if len(formats) > 1:
                d = ChooseFormatDialog(window, _('Choose the format to convert into LRF'), formats)
                d.exec_()
                if d.result() == QDialog.Accepted:
                    self.selected_format = d.format()
            elif len(formats) > 0:
                self.selected_format = formats[0]
            
            if self.selected_format:
                self.setWindowTitle(_('Convert %s to LRF')%(self.selected_format,))
                
        else:
            self.setWindowTitle(_('Set conversion defaults'))
            
    
    def load_saved_global_defaults(self):
        cmdline = config['LRF_conversion_defaults']
        if cmdline:
            self.set_options_from_cmdline(cmdline)
    
    def set_options_from_cmdline(self, cmdline):
        for opt in self.options():
            guiname = self.option_to_name(opt)
            try:
                obj = getattr(self, guiname)
            except AttributeError:
                continue
            if isinstance(obj, QCheckBox):
                if opt.get_opt_string() in cmdline:
                    obj.setCheckState(Qt.Checked)
                else:
                    obj.setCheckState(Qt.Unchecked)
            try:
                i = cmdline.index(opt.get_opt_string())
            except ValueError:
                continue
            
            if isinstance(obj, QAbstractSpinBox):
                obj.setValue(cmdline[i+1])
            elif isinstance(obj, QLineEdit):
                obj.setText(cmdline[i+1])
            elif isinstance(obj, QTextEdit):
                obj.setPlainText(cmdline[i+1])
        profile = cmdline[cmdline.index('--profile')+1]
        pindex = self.gui_profile.findText(profile)
        if pindex >= 0:
            self.gui_profile.setCurrentIndex(pindex)
        for prepro in self.PREPROCESS_OPTIONS:
            ops = prepro.get_opt_string() 
            if ops in cmdline:
                self.preprocess.setCurrentIndex(self.preprocess.findText(ops[2:]))
                break
            
        for opt in ('--serif-family', '--sans-family', '--mono-family'):
            if opt in cmdline:
                print 'in'
                family = cmdline[cmdline.index(opt)+1].split(',')[-1].strip()
                obj = getattr(self, 'gui_'+opt[2:].replace('-', '_'))
                try:
                    obj.setCurrentIndex(self.font_family_model.index_of(family))
                except:
                    continue
    
    def read_saved_options(self):
        cmdline = self.db.conversion_options(self.id, self.output_format.lower())
        if cmdline:
            self.set_options_from_cmdline(cmdline)
    
    def select_cover(self, checked):
        files = choose_images(self, 'change cover dialog', 
                             _('Choose cover for ') + qstring_to_unicode(self.gui_title.text()))
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
    
    def initialize_metadata(self):
        db, row = self.db, self.row
        self.id = self.db.id(row) 
        self.gui_title.setText(db.title(row))
        au = self.db.authors(row)
        if au:
            au = [a.strip().replace('|', ',') for a in au.split(',')]
            self.gui_author.setText(authors_to_string(au))
        else:
            self.gui_author.setText('')
        aus = self.db.author_sort(row)
        self.gui_author_sort.setText(aus if aus else '')
        pub = self.db.publisher(row)
        self.gui_publisher.setText(pub if pub else '')
        tags = self.db.tags(row)
        self.tags.setText(tags if tags else '')
        comments = self.db.comments(row)
        self.gui_comment.setPlainText(comments if comments else '')
        
        all_series = self.db.all_series()
        all_series.sort(cmp=lambda x, y : cmp(x[1], y[1]))
        series_id = self.db.series_id(row)
        idx, c = None, 0
        for i in all_series:
            id, name = i
            if id == series_id:
                idx = c
            self.series.addItem(name)
            c += 1
        
        self.series.lineEdit().setText('')
        if idx is not None:
            self.series.setCurrentIndex(idx)
        
        self.series_index.setValue(self.db.series_index(row))
        
        cover = self.db.cover(row)
        if cover:
            pm = QPixmap()
            pm.loadFromData(cover)
            if not pm.isNull(): 
                self.cover.setPixmap(pm)  
    
    def initialize_options(self):
        '''Initialize non metadata options from the defaults.'''
        for name in self.option_map.keys():
            default = self.option_map[name].default
            obj = getattr(self, name)
            if isinstance(obj, QAbstractSpinBox):
                obj.setValue(default)
            elif isinstance(obj, QLineEdit) and default:
                obj.setText(default)
            elif isinstance(obj, QTextEdit) and default:
                obj.setPlainText(default)
            elif isinstance(obj, QCheckBox):
                state = Qt.Checked if default else Qt.Unchecked
                obj.setCheckState(state)
        self.gui_headerformat.setDisabled(True)
        self.gui_use_metadata_cover.setCheckState(Qt.Checked)
        self.preprocess.addItem('No preprocessing')
        for opt in self.PREPROCESS_OPTIONS:
            self.preprocess.addItem(opt.get_opt_string()[2:])
        ph = _('Preprocess the file before converting to LRF. This is useful if you know that the file is from a specific source. Known sources:')
        ph += _('<ol><li><b>baen</b> - Books from BAEN Publishers</li>')
        ph += _('<li><b>pdftohtml</b> - HTML files that are the output of the program pdftohtml</li>')
        ph += _('<li><b>book-designer</b> - HTML0 files from Book Designer</li>')
        self.preprocess.setToolTip(ph)
        self.preprocess.setWhatsThis(ph)
        for profile in self.PARSER.get_option('--profile').choices:
            if self.gui_profile.findText(profile) < 0:
                self.gui_profile.addItem(profile)
              
    def setup_tooltips(self):
        def show_item_help(obj, event):
            self.set_help(obj.toolTip())
            
        self.option_map = {}
        for opt in self.options():
            try:
                help = opt.help.replace('%default', str(opt.default))
            except (ValueError, TypeError):
                help = opt.help
            
            guiname = self.option_to_name(opt)
            if hasattr(self, guiname):
                obj = getattr(self, guiname)
                obj.setToolTip(help)
                obj.setWhatsThis(help)
                self.option_map[guiname] = opt
                obj.__class__.enterEvent = show_item_help
                #obj.leaveEvent = self.reset_help
        self.preprocess.__class__.enterEvent = show_item_help
        #self.preprocess.leaveEvent = self.reset_help
            
    
    def show_category_help(self, item):
        text = qstring_to_unicode(item.text())
        help = {
                _('Metadata')          : _('Specify metadata such as title and author for the book.<p>Metadata will be updated in the database as well as the generated LRF file.'),
                _('Look & Feel')       : _('Adjust the look of the generated LRF file by specifying things like font sizes and the spacing between words.'),
                _('Page Setup')        : _('Specify the page settings like margins and the screen size of the target device.'),
                _('Chapter Detection') : _('Fine tune the detection of chapter and section headings.'),                  
                }
        self.set_help(help[text])
        
    def set_help(self, msg):
        if msg and getattr(msg, 'strip', lambda:True)():
            self.help_view.setHtml('<html><body>%s</body></html>'%(msg,))
    
    def reset_help(self, *args):
        self.set_help(_('<font color="gray">No help available</font>'))
        if args:
            args[0].accept()
            
    def build_commandline(self):
        cmd = [__appname__]
        for name in self.option_map.keys():
            opt = self.option_map[name].get_opt_string()
            obj = getattr(self, name)
            if isinstance(obj, QAbstractSpinBox):
                cmd.extend([opt, obj.value()])
            elif isinstance(obj, QLineEdit):
                val = qstring_to_unicode(obj.text())
                if val:
                    if opt == '--encoding':
                        try:
                            codecs.getdecoder(val)
                        except:
                            d = error_dialog(self, 'Unknown encoding', 
                                             '<p>Unknown encoding: %s<br/>For a list of known encodings see http://docs.python.org/lib/standard-encodings.html'%val)
                            d.exec_()
                            return
                    cmd.extend([opt, val])
            elif isinstance(obj, QTextEdit):
                val = qstring_to_unicode(obj.toPlainText())
                if val:
                    cmd.extend([opt, val])
            elif isinstance(obj, QCheckBox):
                if obj.checkState() == Qt.Checked:
                    cmd.append(opt)
                    
        text = qstring_to_unicode(self.preprocess.currentText())
        if text != 'No preprocessing':
            cmd.append(u'--'+text)
        cmd.extend([u'--profile',  qstring_to_unicode(self.gui_profile.currentText())])
        
        for opt in ('--serif-family', '--sans-family', '--mono-family'):
            obj = getattr(self, 'gui_'+opt[2:].replace('-', '_'))
            family = qstring_to_unicode(obj.itemText(obj.currentIndex())).strip()
            if family != 'None':
                cmd.extend([opt, family])
        
        return cmd        
    
    def title(self):
        return qstring_to_unicode(self.gui_title.text())
    
    def write_metadata(self):
        title = qstring_to_unicode(self.gui_title.text())
        self.db.set_title(self.id, title)
        au = unicode(self.gui_author.text())
        if au: 
            self.db.set_authors(self.id, string_to_authors(au))
        aus = qstring_to_unicode(self.gui_author_sort.text())
        if not aus:
            t = self.db.authors(self.id, index_is_id=True)
            if not t:
                t = _('Unknown')
            aus = [a.strip().replace('|', ',') for a in t.split(',')]
            aus = authors_to_sort_string(aus)
        self.db.set_author_sort(self.id, aus)
        self.db.set_publisher(self.id, qstring_to_unicode(self.gui_publisher.text()))
        self.db.set_tags(self.id, qstring_to_unicode(self.tags.text()).split(','))
        self.db.set_series(self.id, qstring_to_unicode(self.series.currentText()))
        self.db.set_series_index(self.id, self.series_index.value())
        if self.cover_changed:
            self.db.set_cover(self.id, pixmap_to_data(self.cover.pixmap()))
        
    
    def accept(self):
        cmdline = self.build_commandline()
        if cmdline is None:
            return
        if self.db:
            self.cover_file = None
            self.write_metadata()
            cover = self.db.cover(self.row)
            if cover:
                self.cover_file = PersistentTemporaryFile(suffix='.jpeg')
                self.cover_file.write(cover)
                self.cover_file.close()
            self.db.set_conversion_options(self.id, self.output_format.lower(), cmdline)
            
            if self.cover_file:
                cmdline.extend([u'--cover', self.cover_file.name])
            self.cmdline = [unicode(i) for i in cmdline]
        else:
            config.set('LRF_conversion_defaults', cmdline)
        QDialog.accept(self)
        
class LRFBulkDialog(LRFSingleDialog):
    
    def __init__(self, window):
        QDialog.__init__(self, window)
        Ui_LRFSingleDialog.__init__(self)
        self.setupUi(self)
        self.populate_list()
        
        self.categoryList.takeItem(0)
        self.stack.removeWidget(self.stack.widget(0))
        self.categoryList.setCurrentRow(0)
        
        self.initialize_common()
        self.setWindowTitle(_('Bulk convert ebooks to LRF'))
        
    def accept(self):
        self.cmdline = [unicode(i) for i in self.build_commandline()]
        for meta in ('--title', '--author', '--publisher', '--comment'):
            try:
                index = self.cmdline.index(meta)
                self.cmdline[index:index+2] = []
            except ValueError:
                continue
                
        self.cover_file = None
        QDialog.accept(self)
    
