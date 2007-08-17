##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import os

from PyQt4.QtCore import QObject, SIGNAL, Qt
from PyQt4.QtGui import QAbstractSpinBox, QLineEdit, QCheckBox, QDialog, QPixmap

from libprs500.gui2.dialogs.lrf_single_ui import Ui_LRFSingleDialog
from libprs500.gui2.dialogs.choose_format import ChooseFormatDialog
from libprs500.gui2 import qstring_to_unicode, error_dialog, \
                           pixmap_to_data, choose_images
from libprs500.ebooks.lrf import option_parser

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
    
    def __init__(self, window, db, row):
        QDialog.__init__(self, window)
        Ui_LRFSingleDialog.__init__(self)        
        self.setupUi(self)
        self.categoryList.setCurrentRow(0)
        QObject.connect(self.categoryList, SIGNAL('itemEntered(QListWidgetItem *)'),
                        self.show_category_help)
        QObject.connect(self.cover_button, SIGNAL("clicked(bool)"), self.select_cover)
        self.categoryList.leaveEvent = self.reset_help
        self.reset_help()
        self.setup_tooltips()
        self.initialize_options()
        self.db = db
        self.row = row.row()
        self.id = self.db.id(self.row)
        self.cover_changed = False
        self.cpixmap = None
        self.changed = False
        self.read_saved_options()
        self.initialize_metadata()
        formats = self.db.formats(self.row)
        if not formats:
            d = error_dialog(self, 'No availabla formats', 'Cannot convert as this book has not available formats')
            d.exec_()
        formats = [i.upper() for i in formats.split(',')]
        self.selected_format = None
        try:
            formats.remove('LRF')
        except ValueError:
            pass
        if len(formats) > 1:
            d = ChooseFormatDialog(self, 'Choose the format to convert into LRF', formats)
            d.exec_()
            if d.result() == QDialog.Accepted:
                self.selected_format = d.format()
        else:
            self.selected_format = formats[0]
        if self.selected_format:
            self.setWindowTitle('Convert %s to LRF'%(self.selected_format,))

        
    def read_saved_options(self):
        cmdline = self.db.conversion_options(self.id, 'lrf')
        print 1, cmdline
        if cmdline:
            for opt in self.options():
                try:
                    i = cmdline.index(opt.get_opt_string())
                except ValueError:
                    continue
                guiname = self.option_to_name(opt)
                try:
                    obj = getattr(self, guiname)
                except AttributeError:
                    continue
                if isinstance(obj, QCheckBox):
                    obj.setCheckState(Qt.Checked)
                elif isinstance(obj, QAbstractSpinBox):
                    obj.setValue(cmdline[i+1])
                elif isinstance(obj, QLineEdit):
                    obj.setText(cmdline[i+1])
            profile = cmdline[cmdline.index('--profile')+1]            
            self.gui_profile.setCurrentIndex(self.gui_profile.findText(profile))
            for prepro in self.PREPROCESS_OPTIONS:
                ops = prepro.get_opt_string() 
                if ops in cmdline:
                    self.preprocess.setCurrentIndex(self.preprocess.findText(ops[2:]))
                    break    
        
    
    def select_cover(self, checked):
        files = choose_images(self, 'change cover dialog', 
                             u'Choose cover for ' + qstring_to_unicode(self.title.text()))
        if not files:
            return
        _file = files[0]
        if _file:
            _file = os.path.abspath(_file)
            if not os.access(_file, os.R_OK):
                d = error_dialog(self.window, 'Cannot read', 
                        'You do not have permission to read the file: ' + _file)
                d.exec_()
                return
            cf, cover = None, None
            try:
                cf = open(_file, "rb")
                cover = cf.read()
            except IOError, e: 
                d = error_dialog(self.window, 'Error reading file',
                        "<p>There was an error reading from file: <br /><b>" + _file + "</b></p><br />"+str(e))
                d.exec_()
            if cover:
                pix = QPixmap()
                pix.loadFromData(cover)
                if pix.isNull():
                    d = error_dialog(self.window, _file + " is not a valid picture")
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
        self.gui_author.setText(au if au else '')
        aus = self.db.author_sort(row)
        self.gui_author_sort.setText(aus if aus else '')
        pub = self.db.publisher(row)
        self.gui_publisher.setText(pub if pub else '')
        tags = self.db.tags(row)
        self.tags.setText(tags if tags else '')
        comments = self.db.comments(row)
        self.gui_comment.setPlainText(comments if comments else '')
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
            elif isinstance(obj, QCheckBox):
                state = Qt.Checked if default else Qt.Unchecked
                obj.setCheckState(state)
        self.gui_headerformat.setDisabled(True)
        self.preprocess.addItem('No preprocessing')
        for opt in self.PREPROCESS_OPTIONS:
            self.preprocess.addItem(opt.get_opt_string()[2:])
        ph = 'Preprocess the file before converting to LRF. This is useful if you know that the file is from a specific source. Known sources:'
        ph += '<ol><li><b>baen</b> - Books from BAEN Publishers</li>'
        ph += '<li><b>pdftohtml</b> - HTML files that are the output of the program pdftohtml</li>'
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
                obj.leaveEvent = self.reset_help
        self.preprocess.__class__.enterEvent = show_item_help
        self.preprocess.leaveEvent = self.reset_help
            
    
    def show_category_help(self, item):
        text = qstring_to_unicode(item.text())
        help = {
                u'Metadata'    : 'Specify metadata such as title and author for the book.<p>Metadata will be updated in the database as well as the generated LRF file.',
                u'Look & Feel' : 'Adjust the look of the generated LRF file by specifying things like font sizes and the spacing between words.',
                u'Page Setup'  : 'Specify the page settings like margins and the screen size of the target device.',
                u'Chapter Detection' : 'Fine tune the detection of chapter and section headings.',                  
                }
        self.set_help(help[text])
        
    def set_help(self, msg):
        self.help_view.setHtml('<html><body>%s</body></html>'%(msg,))
    
    def reset_help(self, *args):
        self.set_help('<font color="gray">No help available</font>')
        if args:
            args[0].accept()
            
    def build_commandline(self):
        cmd = []
        for name in self.option_map.keys():
            opt = self.option_map[name].get_opt_string()
            obj = getattr(self, name)
            if isinstance(obj, QAbstractSpinBox):
                cmd.extend([opt, obj.value()])
            elif isinstance(obj, QLineEdit):
                val = qstring_to_unicode(obj.text())
                if val:
                    cmd.extend([opt, val])
            elif isinstance(obj, QCheckBox):
                if obj.checkState() == Qt.Checked:
                    cmd.append(opt)
                    
        text = qstring_to_unicode(self.preprocess.currentText())
        if text != 'No preprocessing':
            cmd.append('--'+text)
        cmd.extend(['--profile',  qstring_to_unicode(self.gui_profile.currentText())])
        return cmd        
    
    def write_metadata(self):
        title = qstring_to_unicode(self.gui_title.text())
        self.db.set_title(self.id, title)
        au = qstring_to_unicode(self.gui_author.text()).split(',')
        if au: self.db.set_authors(self.id, au)
        aus = qstring_to_unicode(self.gui_author_sort.text())
        if aus: self.db.set_author_sort(self.id, aus)
        print self.db.author_sort(self.row)
        self.db.set_publisher(self.id, qstring_to_unicode(self.gui_publisher.text()))
        self.db.set_tags(self.id, qstring_to_unicode(self.tags.text()).split(','))
        self.db.set_series(self.id, qstring_to_unicode(self.series.currentText()))
        self.db.set_series_index(self.id, self.series_index.value())
        if self.cover_changed:
            self.db.set_cover(self.id, pixmap_to_data(self.cover.pixmap()))
        
    
    def accept(self):
        cmdline = self.build_commandline()
        # TODO: put cover into tempfile
        self.write_metadata()
        self.db.set_conversion_options(self.id, 'lrf', cmdline)
        QDialog.accept(self)
    