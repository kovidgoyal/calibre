#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, traceback, re
from Queue import Empty, Queue
from contextlib import closing


from PyQt4.Qt import (QWizard, QWizardPage, QPixmap, Qt, QAbstractListModel,
    QVariant, QItemSelectionModel, SIGNAL, QObject, QTimer, pyqtSignal)
from calibre import __appname__, patheq
from calibre.library.database2 import LibraryDatabase2
from calibre.library.move import MoveLibrary
from calibre.constants import (filesystem_encoding, iswindows, plugins,
        isportable)
from calibre.gui2.wizard.send_email import smtp_prefs
from calibre.gui2.wizard.device_ui import Ui_WizardPage as DeviceUI
from calibre.gui2.wizard.library_ui import Ui_WizardPage as LibraryUI
from calibre.gui2.wizard.finish_ui import Ui_WizardPage as FinishUI
from calibre.gui2.wizard.kindle_ui import Ui_WizardPage as KindleUI
from calibre.gui2.wizard.stanza_ui import Ui_WizardPage as StanzaUI
from calibre.gui2 import min_available_height, available_width

from calibre.utils.config import dynamic, prefs
from calibre.gui2 import NONE, choose_dir, error_dialog
from calibre.gui2.dialogs.progress import ProgressDialog
from calibre.customize.ui import device_plugins

if iswindows:
    winutil = plugins['winutil'][0]

# Devices {{{

class Device(object):

    output_profile = 'generic_eink'
    output_format = 'EPUB'
    name = 'Generic e-ink device'
    manufacturer = 'Generic'
    id = 'default'
    supports_color = False

    @classmethod
    def set_output_profile(cls):
        if cls.output_profile:
            from calibre.ebooks.conversion.config import load_defaults, save_defaults
            recs = load_defaults('page_setup')
            recs['output_profile'] = cls.output_profile
            save_defaults('page_setup', recs)

    @classmethod
    def set_output_format(cls):
        if cls.output_format:
            prefs.set('output_format', cls.output_format.lower())

    @classmethod
    def commit(cls):
        cls.set_output_profile()
        cls.set_output_format()
        if cls.supports_color:
            from calibre.ebooks.conversion.config import load_defaults, save_defaults
            recs = load_defaults('comic_input')
            recs['dont_grayscale'] = True
            save_defaults('comic_input', recs)

class Smartphone(Device):

    id = 'smartphone'
    name = 'Smartphone'
    supports_color = True

class Tablet(Device):

    id = 'tablet'
    name = 'iPad like tablet'
    output_profile = 'tablet'
    supports_color = True

class Kindle(Device):

    output_profile = 'kindle'
    output_format  = 'MOBI'
    name = 'Kindle 1-4 and Touch'
    manufacturer = 'Amazon'
    id = 'kindle'

class JetBook(Device):

    output_profile = 'jetbook5'
    output_format  = 'EPUB'
    name = 'JetBook'
    manufacturer = 'Ectaco'
    id = 'jetbook'

class JetBookMini(Device):

    output_profile = 'jetbook5'
    output_format  = 'FB2'
    name = 'JetBook Mini'
    manufacturer = 'Ectaco'
    id = 'jetbookmini'

class KindleDX(Kindle):

    output_profile = 'kindle_dx'
    output_format  = 'MOBI'
    name = 'Kindle DX'
    id = 'kindledx'

class KindleFire(KindleDX):
    name = 'Kindle Fire'
    id = 'kindle_fire'
    output_profile = 'kindle_fire'
    supports_color = True

class Sony505(Device):

    output_profile = 'sony'
    name = 'All other SONY devices'
    output_format = 'EPUB'
    manufacturer = 'SONY'
    id = 'prs505'

class Kobo(Device):
    name = 'Kobo and Kobo Touch Readers'
    manufacturer = 'Kobo'
    output_profile = 'kobo'
    output_format = 'EPUB'
    id = 'kobo'

class KoboVox(Kobo):
    name = 'Kobo Vox'
    output_profile = 'tablet'
    id = 'kobo_vox'

class Booq(Device):
    name = 'bq Classic'
    manufacturer = 'Booq'
    output_profile = 'sony'
    output_format = 'EPUB'
    id = 'booq'

class TheBook(Device):
    name = 'The Book'
    manufacturer = 'Augen'
    output_profile = 'sony'
    output_format = 'EPUB'
    id = 'thebook'

class Avant(Booq):
    name = 'bq Avant'

class AvantXL(Booq):
    name = 'bq Avant XL'
    output_profile = 'ipad'

class BooqPocketPlus(Booq):
    name = 'bq Pocket Plus'
    output_profile = 'sony300'

class BooqCervantes(Booq):
    name = 'bq Cervantes'

class Sony300(Sony505):

    name = 'SONY Reader Pocket Edition'
    id = 'prs300'
    output_profile = 'sony300'

class Sony900(Sony505):

    name = 'SONY Reader Daily Edition'
    id = 'prs900'
    output_profile = 'sony900'

class Nook(Sony505):
    id = 'nook'
    name = 'Nook and Nook Simple Reader'
    manufacturer = 'Barnes & Noble'
    output_profile = 'nook'

class NookColor(Nook):
    id = 'nook_color'
    name = 'Nook Color'
    output_profile = 'nook_color'
    supports_color = True

class NookTablet(NookColor):
    id = 'nook_tablet'
    name = 'Nook Tablet'

class CybookG3(Device):

    name = 'Cybook Gen 3'
    output_format = 'MOBI'
    output_profile = 'cybookg3'
    manufacturer = 'Bookeen'
    id = 'cybookg3'

class CybookOpus(CybookG3):

    name = 'Cybook Opus'
    output_format = 'EPUB'
    output_profile = 'cybook_opus'
    id = 'cybook_opus'

class CybookOrizon(CybookOpus):

    name = 'Cybook Orizon'
    id = 'cybook_orizon'

class CybookOdyssey(CybookOpus):

    name = 'Cybook Odyssey'
    id = 'cybook_odyssey'


class PocketBook360(CybookOpus):

    manufacturer = 'PocketBook'
    name = 'PocketBook 360 and newer models'
    id = 'pocketbook360'
    output_profile = 'cybook_opus'

class PocketBook(CybookG3):

    manufacturer = 'PocketBook'
    name = 'PocketBook 301/302'
    id = 'pocketbook'
    output_profile = 'cybookg3'

class PocketBook900(PocketBook):

    name = 'PocketBook 900'
    id = 'pocketbook900'
    output_profile = 'pocketbook_900'

class iPhone(Device):

    name = 'iPhone/iTouch'
    output_format = 'EPUB'
    manufacturer = 'Apple'
    id = 'iphone'
    supports_color = True
    output_profile = 'ipad'

class iPad(iPhone):

    name = 'iPad'
    id = 'ipad'
    output_profile = 'ipad3'

class Android(Device):

    name = 'Android phone'
    output_format = 'EPUB'
    manufacturer = 'Android'
    id = 'android'
    supports_color = True

    @classmethod
    def commit(cls):
        super(Android, cls).commit()
        for plugin in device_plugins(include_disabled=True):
            if plugin.name == 'Android driver':
                plugin.configure_for_generic_epub_app()

class AndroidTablet(Android):

    name = 'Android tablet'
    id = 'android_tablet'
    output_profile = 'tablet'

class AndroidPhoneWithKindle(Android):

    name = 'Android phone with Kindle reader'
    output_format = 'MOBI'
    id = 'android_phone_with_kindle'
    output_profile = 'kindle'

    @classmethod
    def commit(cls):
        super(Android, cls).commit()
        for plugin in device_plugins(include_disabled=True):
            if plugin.name == 'Android driver':
                plugin.configure_for_kindle_app()

class AndroidTabletWithKindle(AndroidPhoneWithKindle):

    name = 'Android tablet with Kindle reader'
    id = 'android_tablet_with_kindle'
    output_profile = 'kindle_fire'

class HanlinV3(Device):

    name = 'Hanlin V3'
    output_format = 'EPUB'
    output_profile = 'hanlinv3'
    manufacturer = 'Jinke'
    id = 'hanlinv3'

class HanlinV5(HanlinV3):

    name = 'Hanlin V5'
    output_profile = 'hanlinv5'
    id = 'hanlinv5'

class BeBook(HanlinV3):

    name = 'BeBook'
    manufacturer = 'BeBook'
    id = 'bebook'

class BeBookMini(HanlinV5):

    name = 'BeBook Mini'
    manufacturer = 'BeBook'
    id = 'bebook_mini'

class EZReader(HanlinV3):

    name = 'EZReader'
    manufacturer = 'Astak'
    id = 'ezreader'

class EZReaderPP(HanlinV5):

    name = 'EZReader Pocket Pro'
    manufacturer = 'Astak'
    id = 'ezreader_pp'

class Bambook(Device):

    name = 'Sanda Bambook'
    output_format = 'SNB'
    manufacturer = 'Sanda'
    id = 'bambook'
    output_profile = 'bambook'
# }}}

def get_devices():
    for x in globals().values():
        if isinstance(x, type) and issubclass(x, Device):
            yield x

def get_manufacturers():
    mans = set([])
    for x in get_devices():
        mans.add(x.manufacturer)
    if Device.manufacturer in mans:
        mans.remove(Device.manufacturer)
    return [Device.manufacturer] + sorted(mans)

def get_devices_of(manufacturer):
    ans = [d for d in get_devices() if d.manufacturer == manufacturer]
    return sorted(ans, cmp=lambda x,y:cmp(x.name, y.name))

class ManufacturerModel(QAbstractListModel):

    def __init__(self):
        QAbstractListModel.__init__(self)
        self.manufacturers = get_manufacturers()

    def rowCount(self, p):
        return len(self.manufacturers)

    def columnCount(self, p):
        return 1

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return QVariant(self.manufacturers[index.row()])
        if role == Qt.UserRole:
            return self.manufacturers[index.row()]
        return NONE

    def index_of(self, man):
        for i, x in enumerate(self.manufacturers):
            if x == man:
                return self.index(i)

class DeviceModel(QAbstractListModel):

    def __init__(self, manufacturer):
        QAbstractListModel.__init__(self)
        self.devices = get_devices_of(manufacturer)

    def rowCount(self, p):
        return len(self.devices)

    def columnCount(self, p):
        return 1

    def data(self, index, role):
        if role == Qt.DisplayRole:
            return QVariant(self.devices[index.row()].name)
        if role == Qt.UserRole:
            return self.devices[index.row()]
        return NONE

    def index_of(self, dev):
        for i, device in enumerate(self.devices):
            if device is dev:
                return self.index(i)

class KindlePage(QWizardPage, KindleUI):

    ID = 3

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)

    def initializePage(self):
        opts = smtp_prefs().parse()
        accs = []
        has_default = False
        for x, ac in opts.accounts.iteritems():
            default = ac[2]
            if x.strip().endswith('@kindle.com'):
                accs.append((x, default))
                if default: has_default = True
        if has_default:
            accs = [x for x in accs if x[1]]
        if accs:
            self.to_address.setText(accs[0])
        def x():
            t = unicode(self.to_address.text())
            if t.strip():
                return t.strip()

        self.send_email_widget.initialize(x)

    def commit(self):
        x = unicode(self.to_address.text()).strip()
        parts = x.split('@')

        if (len(parts) >= 2 and parts[0] and self.send_email_widget.set_email_settings(True)):
            conf = smtp_prefs()
            accounts = conf.parse().accounts
            if not accounts: accounts = {}
            for y in accounts.values():
                y[2] = False
            accounts[x] = ['AZW, MOBI, TPZ, PRC, AZW1', True, True]
            conf.set('accounts', accounts)

    def nextId(self):
        return FinishPage.ID

class StanzaPage(QWizardPage, StanzaUI):

    ID = 5

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)
        self.connect(self.content_server, SIGNAL('stateChanged(int)'), self.set_port)

    def initializePage(self):
        from calibre.gui2 import config
        yes = config['autolaunch_server']
        self.content_server.setChecked(yes)
        self.set_port()

    def nextId(self):
        return FinishPage.ID

    def commit(self):
        p = self.set_port()
        if p is not None:
            from calibre.library.server import server_config
            c = server_config()
            c.set('port', p)


    def set_port(self, *args):
        if not self.content_server.isChecked(): return
        import socket
        s = socket.socket()
        with closing(s):
            for p in range(8080, 8100):
                try:
                    s.bind(('0.0.0.0', p))
                    t = unicode(self.instructions.text())
                    t = re.sub(r':\d+', ':'+str(p), t)
                    self.instructions.setText(t)
                    return p
                except:
                    continue


class DevicePage(QWizardPage, DeviceUI):

    ID = 2

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)
        self.registerField("manufacturer", self.manufacturer_view)
        self.registerField("device", self.device_view)

    def initializePage(self):
        self.label.setText(_('Choose your e-book device. If your device is'
            ' not in the list, choose a "%s" device.')%Device.manufacturer)
        self.man_model = ManufacturerModel()
        self.manufacturer_view.setModel(self.man_model)
        previous = dynamic.get('welcome_wizard_device', False)
        if previous:
            previous = [x for x in get_devices() if \
                    x.id == previous]
            if not previous:
                previous = [Device]
            previous = previous[0]
        else:
            previous = Device
        idx = self.man_model.index_of(previous.manufacturer)
        if idx is None:
            idx = self.man_model.index_of(Device.manufacturer)
            previous = Device
        self.manufacturer_view.selectionModel().select(idx,
                QItemSelectionModel.Select)
        self.dev_model = DeviceModel(self.man_model.data(idx, Qt.UserRole))
        idx = self.dev_model.index_of(previous)
        self.device_view.setModel(self.dev_model)
        self.device_view.selectionModel().select(idx,
                QItemSelectionModel.Select)
        self.connect(self.manufacturer_view.selectionModel(),
                SIGNAL('selectionChanged(QItemSelection,QItemSelection)'),
                self.manufacturer_changed)

    def manufacturer_changed(self, current, previous):
        new = list(current.indexes())[0]
        man = self.man_model.data(new, Qt.UserRole)
        self.dev_model = DeviceModel(man)
        self.device_view.setModel(self.dev_model)
        self.device_view.selectionModel().select(self.dev_model.index(0),
                QItemSelectionModel.Select)

    def commit(self):
        idx = list(self.device_view.selectionModel().selectedIndexes())[0]
        dev = self.dev_model.data(idx, Qt.UserRole)
        dev.commit()
        dynamic.set('welcome_wizard_device', dev.id)

    def nextId(self):
        idx = list(self.device_view.selectionModel().selectedIndexes())[0]
        dev = self.dev_model.data(idx, Qt.UserRole)
        if dev in (Kindle, KindleDX):
            return KindlePage.ID
        if dev is iPhone:
            return StanzaPage.ID
        return FinishPage.ID

class MoveMonitor(QObject):

    def __init__(self, worker, rq, callback, parent):
        QObject.__init__(self, parent)
        self.worker = worker
        self.rq = rq
        self.callback = callback
        self.parent = parent

        self.worker.start()
        self.dialog = ProgressDialog(_('Moving library...'), '',
                max=self.worker.total, parent=parent)
        self.dialog.button_box.setDisabled(True)
        self.dialog.setModal(True)
        self.dialog.show()
        self.timer = QTimer(self)
        self.connect(self.timer, SIGNAL('timeout()'), self.check)
        self.timer.start(200)

    def check(self):
        if self.worker.is_alive():
            self.update()
        else:
            self.timer.stop()
            self.dialog.hide()
            if self.worker.failed:
                error_dialog(self.parent, _('Failed to move library'),
                    _('Failed to move library'), self.worker.details, show=True)
                return self.callback(None)
            else:
                return self.callback(self.worker.to)

    def update(self):
        try:
            title = self.rq.get_nowait()[-1]
            self.dialog.value += 1
            self.dialog.set_msg(_('Copied') + ' '+title)
        except Empty:
            pass


class Callback(object):

    def __init__(self, callback):
        self.callback = callback

    def __call__(self, newloc):
        if newloc is not None:
            prefs['library_path'] = newloc
        self.callback(newloc)

_mm = None
def move_library(oldloc, newloc, parent, callback_on_complete):
    callback = Callback(callback_on_complete)
    try:
        if not os.path.exists(os.path.join(newloc, 'metadata.db')):
            if oldloc and os.access(os.path.join(oldloc, 'metadata.db'), os.R_OK):
                # Move old library to new location
                try:
                    db = LibraryDatabase2(oldloc)
                except:
                    return move_library(None, newloc, parent,
                        callback)
                else:
                    rq = Queue()
                    m = MoveLibrary(oldloc, newloc,
                            len(db.get_top_level_move_items()[0]), rq)
                    global _mm
                    _mm = MoveMonitor(m, rq, callback, parent)
                    return
            else:
                # Create new library at new location
                db = LibraryDatabase2(newloc)
                callback(newloc)
                return

        # Try to load existing library at new location
        try:
            LibraryDatabase2(newloc)
        except Exception as err:
            det = traceback.format_exc()
            error_dialog(parent, _('Invalid database'),
                _('<p>An invalid library already exists at '
                    '%(loc)s, delete it before trying to move the '
                    'existing library.<br>Error: %(err)s')%dict(loc=newloc,
                        err=str(err)), det, show=True)
            callback(None)
            return
        else:
            callback(newloc)
            return
    except Exception as err:
        det = traceback.format_exc()
        error_dialog(parent, _('Could not move library'),
                unicode(err), det, show=True)
    callback(None)

class LibraryPage(QWizardPage, LibraryUI):

    ID = 1
    retranslate = pyqtSignal()

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)
        self.registerField('library_location', self.location)
        self.connect(self.button_change, SIGNAL('clicked()'), self.change)
        self.init_languages()
        self.language.currentIndexChanged[int].connect(self.change_language)
        self.connect(self.location, SIGNAL('textChanged(QString)'),
                self.location_text_changed)

    def location_text_changed(self, newtext):
        self.emit(SIGNAL('completeChanged()'))

    def init_languages(self):
        self.language.blockSignals(True)
        self.language.clear()
        from calibre.utils.localization import (available_translations,
            get_language, get_lang)
        lang = get_lang()
        lang = lang.split('_')[0].lower() if lang else lang
        if lang is None or lang not in available_translations():
            lang = 'en'
        def get_esc_lang(l):
            if l == 'en':
                return 'English'
            return get_language(l)

        self.language.addItem(get_esc_lang(lang), QVariant(lang))
        items = [(l, get_esc_lang(l)) for l in available_translations()
                 if l != lang]
        if lang != 'en':
            items.append(('en', get_esc_lang('en')))
        items.sort(cmp=lambda x, y: cmp(x[1], y[1]))
        for item in items:
            self.language.addItem(item[1], QVariant(item[0]))
        self.language.blockSignals(False)
        prefs['language'] = str(self.language.itemData(self.language.currentIndex()).toString())

    def change_language(self, idx):
        prefs['language'] = str(self.language.itemData(self.language.currentIndex()).toString())
        import __builtin__
        __builtin__.__dict__['_'] = lambda(x): x
        from calibre.utils.localization import set_translators
        from calibre.gui2 import qt_app
        set_translators()
        qt_app.load_translations()
        self.retranslate.emit()
        self.init_languages()
        try:
            lang = prefs['language'].lower()[:2]
            metadata_plugins = {
                    'zh' : ('Douban Books',),
                    'fr' : ('Nicebooks',),
                    'ru' : ('OZON.ru',),
            }.get(lang, [])
            from calibre.customize.ui import enable_plugin
            for name in metadata_plugins:
                enable_plugin(name)
        except:
            pass

    def is_library_dir_suitable(self, x):
        try:
            return LibraryDatabase2.exists_at(x) or not os.listdir(x)
        except:
            return False

    def validatePage(self):
        newloc = unicode(self.location.text())
        if not self.is_library_dir_suitable(newloc):
            self.show_library_dir_error(newloc)
            return False
        return True

    def change(self):
        x = choose_dir(self, 'database location dialog',
                         _('Select location for books'))
        if x:
            if (iswindows and len(x) >
                    LibraryDatabase2.WINDOWS_LIBRARY_PATH_LIMIT):
                return error_dialog(self, _('Too long'),
                    _('Path to library too long. Must be less than'
                    ' %d characters.')%LibraryDatabase2.WINDOWS_LIBRARY_PATH_LIMIT,
                    show=True)
            if not os.path.exists(x):
                try:
                    os.makedirs(x)
                except:
                    return error_dialog(self, _('Bad location'),
                            _('Failed to create a folder at %s')%x,
                            det_msg=traceback.format_exc(), show=True)

            if self.is_library_dir_suitable(x):
                self.location.setText(x)
            else:
                self.show_library_dir_error(x)

    def show_library_dir_error(self, x):
        if not isinstance(x, unicode):
            try:
                x = x.decode(filesystem_encoding)
            except:
                x = unicode(repr(x))
        error_dialog(self, _('Bad location'),
            _('You must choose an empty folder for '
                'the calibre library. %s is not empty.')%x, show=True)

    def initializePage(self):
        lp = prefs['library_path']
        self.default_library_name = None
        if not lp:
            fname = _('Calibre Library')
            base = os.path.expanduser(u'~')
            if iswindows:
                x = winutil.special_folder_path(winutil.CSIDL_PERSONAL)
                if x and os.access(x, os.W_OK):
                    base = x

            lp = os.path.join(base, fname)
            self.default_library_name = lp
            if not os.path.exists(lp):
                try:
                    os.makedirs(lp)
                except:
                    traceback.print_exc()
                    lp = os.path.expanduser(u'~')
        self.location.setText(lp)
        # Hide the library location settings if we are a portable install
        for x in ('location', 'button_change', 'libloc_label1',
                'libloc_label2'):
            getattr(self, x).setVisible(not isportable)

    def isComplete(self):
        try:
            lp = unicode(self.location.text())
            ans = bool(lp) and os.path.exists(lp) and os.path.isdir(lp) and os.access(lp,
                    os.W_OK)
        except:
            ans = False
        return ans

    def commit(self, completed):
        oldloc = prefs['library_path']
        newloc = unicode(self.location.text())
        try:
            dln = self.default_library_name
            if (dln and os.path.exists(dln) and not os.listdir(dln) and newloc
                    != dln):
                os.rmdir(dln)
        except:
            pass
        if not os.path.exists(newloc):
            os.mkdir(newloc)
        if not patheq(oldloc, newloc):
            move_library(oldloc, newloc, self.wizard(), completed)
            return True
        return False

    def nextId(self):
        return DevicePage.ID

class FinishPage(QWizardPage, FinishUI):

    ID = 4

    def __init__(self):
        QWizardPage.__init__(self)
        self.setupUi(self)

    def nextId(self):
        return -1

    def commit(self):
        pass



class Wizard(QWizard):

    BUTTON_TEXTS = {
            'Next': '&Next >',
            'Back': '< &Back',
            'Cancel': 'Cancel',
            'Finish': '&Finish',
            'Commit': 'Commit'
    }
    # The latter is simply to mark the texts for translation
    if False:
            _('&Next >')
            _('< &Back')
            _('Cancel')
            _('&Finish')
            _('Commit')


    def __init__(self, parent):
        QWizard.__init__(self, parent)
        self.setWindowTitle(__appname__+' '+_('welcome wizard'))
        p  = QPixmap()
        p.loadFromData(open(P('content_server/calibre.png'), 'rb').read())
        self.setPixmap(self.LogoPixmap, p.scaledToHeight(80,
            Qt.SmoothTransformation))
        self.setPixmap(self.WatermarkPixmap,
            QPixmap(I('welcome_wizard.png')))
        self.setPixmap(self.BackgroundPixmap, QPixmap(I('wizard.png')))
        self.device_page = DevicePage()
        self.library_page = LibraryPage()
        self.library_page.retranslate.connect(self.retranslate)
        self.finish_page = FinishPage()
        self.set_finish_text()
        self.kindle_page = KindlePage()
        self.stanza_page = StanzaPage()
        self.setPage(self.library_page.ID, self.library_page)
        self.setPage(self.device_page.ID, self.device_page)
        self.setPage(self.finish_page.ID, self.finish_page)
        self.setPage(self.kindle_page.ID, self.kindle_page)
        self.setPage(self.stanza_page.ID, self.stanza_page)

        self.device_extra_page = None
        nh, nw = min_available_height()-75, available_width()-30
        if nh < 0:
            nh = 580
        if nw < 0:
            nw = 400
        nh = min(400, nh)
        nw = min(580, nw)
        self.resize(nw, nh)
        self.set_button_texts()

    def set_button_texts(self):
        for but, text in self.BUTTON_TEXTS.iteritems():
            self.setButtonText(getattr(self, but+'Button'), _(text))

    def retranslate(self):
        for pid in self.pageIds():
            page = self.page(pid)
            page.retranslateUi(page)
        self.set_button_texts()
        self.set_finish_text()

    def accept(self):
        pages = map(self.page, self.visitedPages())
        for page in pages:
            if page is not self.library_page:
                page.commit()

        if not self.library_page.commit(self.completed):
            self.completed(None)

    def completed(self, newloc):
        return QWizard.accept(self)

    def set_finish_text(self, *args):
        bt = unicode(self.buttonText(self.FinishButton)).replace('&', '')
        t = unicode(self.finish_page.finish_text.text())
        if '%s' in t:
            self.finish_page.finish_text.setText(t%bt)


def wizard(parent=None):
    w = Wizard(parent)
    return w

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    wizard().exec_()

