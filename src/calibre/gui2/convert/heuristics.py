__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from qt.core import Qt

from calibre.gui2 import gprefs
from calibre.gui2.convert.heuristics_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.utils.localization import localize_user_manual_link
from calibre.ebooks.conversion.config import OPTIONS


class HeuristicsWidget(Widget, Ui_Form):

    TITLE = _('Heuristic\nprocessing')
    HELP  = _('Modify the document text and structure using common patterns.')
    COMMIT_NAME = 'heuristics'
    ICON = 'heuristics.png'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent, OPTIONS['pipe']['heuristics'])
        self.db, self.book_id = db, book_id
        self.rssb_defaults = ['', '<hr />', '∗ ∗ ∗', '• • •', '♦ ♦ ♦',
                '† †', '‡ ‡ ‡', '∞ ∞ ∞', '¤ ¤ ¤', '§']
        self.initialize_options(get_option, get_help, db, book_id)

        self.load_histories()

        self.opt_enable_heuristics.stateChanged.connect(self.enable_heuristics)
        self.opt_unwrap_lines.stateChanged.connect(self.enable_unwrap)

        self.enable_heuristics(self.opt_enable_heuristics.checkState())
        try:
            self.help_label.setText(self.help_label.text() % localize_user_manual_link(
                'https://manual.calibre-ebook.com/conversion.html#heuristic-processing'))
        except TypeError:
            pass  # link already localized

    def restore_defaults(self, get_option):
        Widget.restore_defaults(self, get_option)

        self.save_histories()
        rssb_hist = gprefs['replace_scene_breaks_history']
        for x in self.rssb_defaults:
            if x in rssb_hist:
                del rssb_hist[rssb_hist.index(x)]
        gprefs['replace_scene_breaks_history'] = self.rssb_defaults + gprefs['replace_scene_breaks_history']
        self.load_histories()

    def commit_options(self, save_defaults=False):
        self.save_histories()

        return Widget.commit_options(self, save_defaults)

    def break_cycles(self):
        Widget.break_cycles(self)

        try:
            self.opt_enable_heuristics.stateChanged.disconnect()
            self.opt_unwrap_lines.stateChanged.disconnect()
        except:
            pass

    def set_value_handler(self, g, val):
        if val is None and g is self.opt_html_unwrap_factor:
            g.setValue(0.0)
            return True
        if not val and g is self.opt_replace_scene_breaks:
            g.lineEdit().setText('')
            return True

    def load_histories(self):
        val = str(self.opt_replace_scene_breaks.currentText())

        self.opt_replace_scene_breaks.clear()
        self.opt_replace_scene_breaks.lineEdit().setText('')

        rssb_hist = gprefs.get('replace_scene_breaks_history', self.rssb_defaults)
        if val in rssb_hist:
            del rssb_hist[rssb_hist.index(val)]
        rssb_hist.insert(0, val)
        for v in rssb_hist:
            # Ensure we don't have duplicate items.
            if self.opt_replace_scene_breaks.findText(v) == -1:
                self.opt_replace_scene_breaks.addItem(v)
        self.opt_replace_scene_breaks.setCurrentIndex(0)

    def save_histories(self):
        rssb_history = []
        history_pats = [str(self.opt_replace_scene_breaks.lineEdit().text())] + [str(self.opt_replace_scene_breaks.itemText(i))
                                for i in range(self.opt_replace_scene_breaks.count())]
        for p in history_pats[:10]:
            # Ensure we don't have duplicate items.
            if p not in rssb_history:
                rssb_history.append(p)
        gprefs['replace_scene_breaks_history'] = rssb_history

    def enable_heuristics(self, state):
        self.heuristic_options.setEnabled(self.opt_enable_heuristics.isChecked())

    def enable_unwrap(self, state):
        if state == Qt.CheckState.Checked:
            state = True
        else:
            state = False
        self.opt_html_unwrap_factor.setEnabled(state)
