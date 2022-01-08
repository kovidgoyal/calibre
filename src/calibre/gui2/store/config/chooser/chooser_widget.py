__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from qt.core import QWidget, QIcon, QDialog, QComboBox, QLineEdit

from calibre.gui2.store.config.chooser.adv_search_builder import AdvSearchBuilderDialog
from calibre.gui2.store.config.chooser.chooser_widget_ui import Ui_Form


class StoreChooserWidget(QWidget, Ui_Form):

    def __init__(self):
        QWidget.__init__(self)
        self.setupUi(self)

        self.query.initialize('store_config_chooser_query')
        self.query.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.query.setMinimumContentsLength(25)
        self.adv_search_action = ac = self.query.lineEdit().addAction(QIcon.ic('gear.png'), QLineEdit.ActionPosition.LeadingPosition)
        ac.triggered.connect(self.build_adv_search)
        ac.setToolTip(_('Advanced search'))
        self.search.clicked.connect(self.do_search)
        self.enable_all.clicked.connect(self.results_view.model().enable_all)
        self.enable_none.clicked.connect(self.results_view.model().enable_none)
        self.enable_invert.clicked.connect(self.results_view.model().enable_invert)
        self.results_view.activated.connect(self.results_view.model().toggle_plugin)

    def do_search(self):
        self.results_view.model().search(str(self.query.text()))

    def build_adv_search(self):
        adv = AdvSearchBuilderDialog(self)
        if adv.exec() == QDialog.DialogCode.Accepted:
            self.query.setText(adv.search_string())
