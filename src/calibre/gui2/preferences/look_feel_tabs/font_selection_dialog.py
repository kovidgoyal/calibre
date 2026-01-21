from qt.core import QDialog, QDialogButtonBox, QFontDatabase, QFontInfo, QHBoxLayout, QLabel, QListWidget, Qt, QVBoxLayout, QWidget, pyqtSignal


class FontSelectionDialog(QDialog):
    fontSelected = pyqtSignal(str, str)  # family, style

    def __init__(self, family: str = '', style: str = '', min_size=8, medium_size=12, max_size=24, parent=None):
        super().__init__(parent)
        if family:
            self.initial_family, self.initial_style = family, style
        else:
            font = self.font()
            fi = QFontInfo(font)
            self.initial_family = fi.family()
            self.initial_style = fi.styleName()
        self.min_size = min_size
        self.medium_size = medium_size
        self.max_size = max_size

        self.setWindowTitle(_('Select font'))

        self._setup_ui()
        self._populate_families()
        self.families_list.setFocus(Qt.FocusReason.OtherFocusReason)
        self.resize(self.sizeHint())

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # Top section: Font families and styles side by side
        lists_layout = QHBoxLayout()

        # Font families list
        families_layout = QVBoxLayout()
        families_label = QLabel(_('&Family:'))
        self.families_list = QListWidget()
        families_label.setBuddy(self.families_list)
        self.families_list.currentItemChanged.connect(self._on_family_changed)
        families_layout.addWidget(families_label)
        families_layout.addWidget(self.families_list)

        # Styles list
        styles_layout = QVBoxLayout()
        styles_label = QLabel(_('&Style:'))
        self.styles_list = QListWidget()
        styles_label.setBuddy(self.styles_list)
        self.styles_list.currentItemChanged.connect(self._on_style_changed)
        styles_layout.addWidget(styles_label)
        styles_layout.addWidget(self.styles_list)

        lists_layout.addLayout(families_layout, 2)
        lists_layout.addLayout(styles_layout, 1)

        main_layout.addLayout(lists_layout, stretch=20)

        # Preview area
        preview_group = QWidget()
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(0, 10, 0, 10)

        preview_container = QWidget()
        self.preview_layout = QVBoxLayout(preview_container)
        self.preview_layout.setSpacing(10)
        self.preview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Preview labels for different sizes
        self.preview_small = QLabel('The quick brown fox jumps over the lazy dog')
        self.preview_medium = QLabel(self.preview_small)
        self.preview_large = QLabel(self.preview_small)
        self.preview_layout.addWidget(self.preview_small)
        self.preview_layout.addWidget(self.preview_medium)
        self.preview_layout.addWidget(self.preview_large)

        preview_layout.addWidget(preview_container)

        main_layout.addWidget(preview_group, stretch=1)

        # OK/Cancel buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout.addWidget(button_box)

    def _populate_families(self):
        '''Populate the families list with smoothly scalable fonts only'''
        self.families_list.clear()

        # Get all font families
        all_families = QFontDatabase.families()

        # Filter for smoothly scalable fonts
        scalable_families = []
        idx = i = 0
        for family in all_families:
            if QFontDatabase.isSmoothlyScalable(family):
                scalable_families.append(family)
                if family == self.initial_family:
                    idx = i
                i += 1

        scalable_families.sort()
        self.families_list.addItems(scalable_families)

        # Select the initial item if available
        if self.families_list.count() > 0:
            self.families_list.setCurrentRow(idx)
            self._on_family_changed(self.families_list.currentItem(), None)

    def _on_family_changed(self, current, previous):
        '''When a family is selected, populate the styles list'''
        if not current:
            self.styles_list.clear()
            return

        family = current.text()
        self.styles_list.clear()

        # Get all styles for this family
        styles = QFontDatabase.styles(family)
        idx = 0
        if family == self.initial_family and self.initial_style in styles:
            idx = styles.index(self.initial_style)
        self.styles_list.addItems(styles)

        # Select first style if available
        if self.styles_list.count() > 0:
            self.styles_list.setCurrentRow(idx)
        self._update_preview()

    def _on_style_changed(self, current, previous):
        '''Update the preview when style changes'''
        self._update_preview()

    def _update_preview(self):
        '''Update the preview labels with the selected font'''
        family_item = self.families_list.currentItem()
        style_item = self.styles_list.currentItem()

        if not family_item or not style_item:
            return

        family = family_item.text()
        style = style_item.text()
        systems = tuple(QFontDatabase.writingSystems(family))
        text = ''
        for s in systems:
            if (t := QFontDatabase.writingSystemSample(s)):
                text = t
                break

        def s(label, sz):
            font = QFontDatabase.font(family, style, int(sz))
            font.setPointSizeF(sz)
            label.setFont(font)
            label.setText('')
            if label is self.preview_small:
                prefix = _('Minimum size:')
            elif label is self.preview_medium:
                prefix = _('Base size:')
            else:
                prefix = _('Maximum size:')
            label.setText(prefix + ' ' + text)
        s(self.preview_small, self.min_size)
        s(self.preview_medium, self.medium_size)
        s(self.preview_large, self.max_size)

    def selected_font(self):
        '''Returns the selected font family and style as a tuple'''
        family_item = self.families_list.currentItem()
        style_item = self.styles_list. currentItem()

        if family_item and style_item:
            return family_item.text(), style_item.text()
        return None, None

    def get_font(self, size=None):
        '''Returns a QFont object for the selected family and style'''
        family, style = self.selected_font()
        if family and style:
            if size is None:
                size = self.medium_size
            return QFontDatabase.font(family, style, size)
        return None

    def accept(self):
        '''Override accept to emit signal with selected font'''
        family, style = self.selected_font()
        if family and style:
            self.fontSelected.emit(family, style)
        super().accept()


if __name__ == '__main__':
    from calibre.gui2 import Application

    app = Application()

    def show_dialog():
        dialog = FontSelectionDialog(min_size=10, medium_size=14, max_size=28)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            family, style = dialog.selected_font()
            selected_font = dialog.get_font(16)
            print(f'Selected:  {family} - {style}')
            print(f'Font: {selected_font. family()} {selected_font.styleName()} {selected_font.pointSize()}pt')

    show_dialog()
