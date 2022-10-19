#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>


import shutil

from qt.core import (
    QAbstractListModel, QCheckBox, QComboBox, QDialog,
    QDialogButtonBox, QFont, QFrame, QGridLayout, QHBoxLayout, QIcon, QLabel,
    QListView, QModelIndex, QScrollArea, QSize, QSizePolicy, QSpacerItem,
    Qt, QTextEdit, QWidget
)

from calibre.customize.conversion import OptionRecommendation
from calibre.ebooks.conversion.config import (
    GuiRecommendations, delete_specifics, get_input_format_for_book,
    get_output_formats, save_specifics, sort_formats_by_preference
)
from calibre.ebooks.conversion.plumber import create_dummy_plumber
from calibre.gui2 import gprefs
from calibre.gui2.convert.debug import DebugWidget
from calibre.gui2.convert.heuristics import HeuristicsWidget
from calibre.gui2.convert.look_and_feel import LookAndFeelWidget
from calibre.gui2.convert.metadata import MetadataWidget
from calibre.gui2.convert.page_setup import PageSetupWidget
from calibre.gui2.convert.search_and_replace import SearchAndReplaceWidget
from calibre.gui2.convert.structure_detection import StructureDetectionWidget
from calibre.gui2.convert.toc import TOCWidget
from calibre.utils.config import prefs


class GroupModel(QAbstractListModel):

    def __init__(self, widgets):
        self.widgets = widgets
        QAbstractListModel.__init__(self)

    def rowCount(self, *args):
        return len(self.widgets)

    def data(self, index, role):
        try:
            widget = self.widgets[index.row()]
        except:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return (widget.config_title())
        if role == Qt.ItemDataRole.DecorationRole:
            return (widget.config_icon())
        if role == Qt.ItemDataRole.FontRole:
            f = QFont()
            f.setBold(True)
            return (f)
        return None


class Config(QDialog):
    '''
    Configuration dialog for single book conversion. If accepted, has the
    following important attributes

    output_format - Output format (without a leading .)
    input_format  - Input format (without a leading .)
    opf_path - Path to OPF file with user specified metadata
    cover_path - Path to user specified cover (can be None)
    recommendations - A pickled list of 3 tuples in the same format as the
    recommendations member of the Input/Output plugins.
    '''

    def __init__(self, parent, db, book_id,
            preferred_input_format=None, preferred_output_format=None):
        QDialog.__init__(self, parent)
        self.widgets = []
        self.setupUi()
        self.opt_individual_saved_settings.setVisible(False)
        self.db, self.book_id = db, book_id

        self.setup_input_output_formats(self.db, self.book_id, preferred_input_format,
                preferred_output_format)
        self.setup_pipeline()

        self.input_formats.currentIndexChanged.connect(self.setup_pipeline)
        self.output_formats.currentIndexChanged.connect(self.setup_pipeline)
        self.groups.setSpacing(5)
        self.groups.entered[(QModelIndex)].connect(self.show_group_help)
        rb = self.buttonBox.button(QDialogButtonBox.StandardButton.RestoreDefaults)
        rb.setText(_('Restore &defaults'))
        rb.setIcon(QIcon.ic('clear_left.png'))
        rb.clicked.connect(self.restore_defaults)
        self.groups.setMouseTracking(True)
        self.restore_geometry(gprefs, 'convert_single_dialog_geom')

    def current_group_changed(self, cur, prev):
        self.show_pane(cur)

    def setupUi(self):
        self.setObjectName("Dialog")
        self.resize(1024, 700)
        self.setWindowIcon(QIcon.ic('convert.png'))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName("gridLayout")
        self.horizontalLayout = QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.input_label = QLabel(self)
        self.input_label.setObjectName("input_label")
        self.horizontalLayout.addWidget(self.input_label)
        self.input_formats = QComboBox(self)
        self.input_formats.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.input_formats.setMinimumContentsLength(5)
        self.input_formats.setObjectName("input_formats")
        self.horizontalLayout.addWidget(self.input_formats)
        self.opt_individual_saved_settings = QCheckBox(self)
        self.opt_individual_saved_settings.setObjectName("opt_individual_saved_settings")
        self.horizontalLayout.addWidget(self.opt_individual_saved_settings)
        spacerItem = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.label_2 = QLabel(self)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout.addWidget(self.label_2)
        self.output_formats = QComboBox(self)
        self.output_formats.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.output_formats.setMinimumContentsLength(5)
        self.output_formats.setObjectName("output_formats")
        self.horizontalLayout.addWidget(self.output_formats)
        self.gridLayout.addLayout(self.horizontalLayout, 0, 0, 1, 2)
        self.groups = QListView(self)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groups.sizePolicy().hasHeightForWidth())
        self.groups.setSizePolicy(sizePolicy)
        self.groups.setTabKeyNavigation(True)
        self.groups.setIconSize(QSize(48, 48))
        self.groups.setWordWrap(True)
        self.groups.setObjectName("groups")
        self.gridLayout.addWidget(self.groups, 1, 0, 3, 1)
        self.scrollArea = QScrollArea(self)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(4)
        sizePolicy.setVerticalStretch(10)
        sizePolicy.setHeightForWidth(self.scrollArea.sizePolicy().hasHeightForWidth())
        self.scrollArea.setSizePolicy(sizePolicy)
        self.scrollArea.setFrameShape(QFrame.Shape.NoFrame)
        self.scrollArea.setLineWidth(0)
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.page = QWidget()
        self.page.setObjectName("page")
        self.gridLayout.addWidget(self.scrollArea, 1, 1, 1, 1)
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setOrientation(Qt.Orientation.Horizontal)
        self.buttonBox.setStandardButtons(
            QDialogButtonBox.StandardButton.Cancel|QDialogButtonBox.StandardButton.Ok|
            QDialogButtonBox.StandardButton.RestoreDefaults)
        self.buttonBox.setObjectName("buttonBox")
        self.gridLayout.addWidget(self.buttonBox, 3, 1, 1, 1)
        self.help = QTextEdit(self)
        self.help.setReadOnly(True)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.help.sizePolicy().hasHeightForWidth())
        self.help.setSizePolicy(sizePolicy)
        self.help.setMaximumHeight(80)
        self.help.setObjectName("help")
        self.gridLayout.addWidget(self.help, 2, 1, 1, 1)
        self.input_label.setBuddy(self.input_formats)
        self.label_2.setBuddy(self.output_formats)
        self.input_label.setText(_("&Input format:"))
        self.opt_individual_saved_settings.setText(_("Use &saved conversion settings for individual books"))
        self.label_2.setText(_("&Output format:"))

        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def sizeHint(self):
        geom = self.screen().availableSize()
        nh, nw = max(300, geom.height()-100), max(400, geom.width()-70)
        return QSize(nw, nh)

    def restore_defaults(self):
        delete_specifics(self.db, self.book_id)
        self.setup_pipeline()

    @property
    def input_format(self):
        return str(self.input_formats.currentText()).lower()

    @property
    def output_format(self):
        return str(self.output_formats.currentText()).lower()

    @property
    def manually_fine_tune_toc(self):
        for w in self.widgets:
            if hasattr(w, 'manually_fine_tune_toc'):
                return w.manually_fine_tune_toc.isChecked()

    def setup_pipeline(self, *args):
        oidx = self.groups.currentIndex().row()
        input_format = self.input_format
        output_format = self.output_format
        self.plumber = create_dummy_plumber(input_format, output_format)

        def widget_factory(cls):
            return cls(self, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db, self.book_id)

        self.mw = widget_factory(MetadataWidget)
        self.setWindowTitle(_('Convert')+ ' ' + str(self.mw.title.text()))
        lf = widget_factory(LookAndFeelWidget)
        hw = widget_factory(HeuristicsWidget)
        sr = widget_factory(SearchAndReplaceWidget)
        ps = widget_factory(PageSetupWidget)
        sd = widget_factory(StructureDetectionWidget)
        toc = widget_factory(TOCWidget)
        from calibre.gui2.actions.toc_edit import SUPPORTED
        toc.manually_fine_tune_toc.setVisible(output_format.upper() in SUPPORTED)
        debug = widget_factory(DebugWidget)

        output_widget = self.plumber.output_plugin.gui_configuration_widget(
                self, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db, self.book_id)
        input_widget = self.plumber.input_plugin.gui_configuration_widget(
                self, self.plumber.get_option_by_name,
                self.plumber.get_option_help, self.db, self.book_id)

        self.break_cycles()
        self.widgets = widgets = [self.mw, lf, hw, ps, sd, toc, sr]
        if input_widget is not None:
            widgets.append(input_widget)
        if output_widget is not None:
            widgets.append(output_widget)
        widgets.append(debug)
        for w in widgets:
            w.set_help_signal.connect(self.help.setPlainText)
            w.setVisible(False)
            w.layout().setContentsMargins(0, 0, 0, 0)

        self._groups_model = GroupModel(widgets)
        self.groups.setModel(self._groups_model)

        idx = oidx if -1 < oidx < self._groups_model.rowCount() else 0
        self.groups.setCurrentIndex(self._groups_model.index(idx))
        self.show_pane(idx)
        self.groups.selectionModel().currentChanged.connect(self.current_group_changed)
        try:
            shutil.rmtree(self.plumber.archive_input_tdir, ignore_errors=True)
        except Exception:
            pass

    def setup_input_output_formats(self, db, book_id, preferred_input_format,
            preferred_output_format):
        if preferred_output_format:
            preferred_output_format = preferred_output_format.upper()
        output_formats = get_output_formats(preferred_output_format)
        input_format, input_formats = get_input_format_for_book(db, book_id,
                preferred_input_format)
        preferred_output_format = preferred_output_format if \
            preferred_output_format in output_formats else \
            sort_formats_by_preference(output_formats,
                    [prefs['output_format']])[0]
        self.input_formats.addItems(str(x.upper()) for x in input_formats)
        self.output_formats.addItems(str(x.upper()) for x in output_formats)
        self.input_formats.setCurrentIndex(input_formats.index(input_format))
        self.output_formats.setCurrentIndex(output_formats.index(preferred_output_format))

    def show_pane(self, index):
        if hasattr(index, 'row'):
            index = index.row()
        ow = self.scrollArea.takeWidget()
        if ow:
            ow.setParent(self)
        for i, w in enumerate(self.widgets):
            if i == index:
                self.scrollArea.setWidget(w)
                w.show()
            else:
                w.setVisible(False)

    def accept(self):
        recs = GuiRecommendations()
        for w in self._groups_model.widgets:
            if not w.pre_commit_check():
                return
            x = w.commit(save_defaults=False)
            recs.update(x)
        self.opf_file, self.cover_file = self.mw.opf_file, self.mw.cover_file
        self._recommendations = recs
        if self.db is not None:
            recs['gui_preferred_input_format'] = self.input_format
            save_specifics(self.db, self.book_id, recs)
        self.break_cycles()
        QDialog.accept(self)

    def reject(self):
        self.break_cycles()
        QDialog.reject(self)

    def done(self, r):
        if self.isVisible():
            self.save_geometry(gprefs, 'convert_single_dialog_geom')
        return QDialog.done(self, r)

    def break_cycles(self):
        for w in self.widgets:
            w.break_cycles()

    @property
    def recommendations(self):
        recs = [(k, v, OptionRecommendation.HIGH) for k, v in
                self._recommendations.items()]
        return recs

    def show_group_help(self, index):
        widget = self._groups_model.widgets[index.row()]
        self.help.setPlainText(widget.HELP)
