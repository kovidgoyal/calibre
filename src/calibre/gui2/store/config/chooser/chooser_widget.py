__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from qt.core import QComboBox, QDialog, QIcon, QLineEdit, QWidget

from calibre.gui2.store.config.chooser.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.config.chooser.chooser_widget_ui import Ui_Form
from calibre.gui2.store.config.chooser.models import Matches
from calibre.utils.localization import _


class StoreChooserWidget(QWidget, Ui_Form):

    def __init__(self):
        QWidget.__init__(self)
        self.setupUi(self)

        self.query.initialize('store_config_chooser_query')
        self.query.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.query.setMinimumContentsLength(25)
        line_edit = self.query.lineEdit()
        assert line_edit is not None
        self.adv_search_action = ac = line_edit.addAction(QIcon.ic('gear.png'), QLineEdit.ActionPosition.LeadingPosition)
        assert ac is not None
        ac.triggered.connect(self.build_adv_search)
        ac.setToolTip(_('Advanced search'))
        self.search.clicked.connect(self.do_search)
        _m = self.results_view.model()
        assert _m is not None
        assert isinstance(_m, Matches)
        self.enable_all.clicked.connect(_m.enable_all)
        self.enable_none.clicked.connect(_m.enable_none)
        self.enable_invert.clicked.connect(_m.enable_invert)
        self.results_view.activated.connect(_m.toggle_plugin)

    def do_search(self):
        _m = self.results_view.model()
        assert _m is not None
        assert isinstance(_m, Matches)
        _m.search(str(self.query.text()))

    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        if adv.exec() == QDialog.DialogCode.Accepted:
            self.query.setText(adv.search_string())
