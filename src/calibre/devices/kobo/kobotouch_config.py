#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai


__license__   = 'GPL v3'
__copyright__ = '2015-2019, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from PyQt5.Qt import (QWidget, QLabel, QGridLayout, QLineEdit, QVBoxLayout,
                      QDialog, QDialogButtonBox, QCheckBox, QPushButton)

from calibre.gui2.device_drivers.tabbed_device_config import TabbedDeviceConfig, DeviceConfigTab, DeviceOptionsGroupBox
from calibre.devices.usbms.driver import debug_print
from calibre.gui2 import error_dialog
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from polyglot.builtins import unicode_type


def wrap_msg(msg):
    return textwrap.fill(msg.strip(), 100)


def setToolTipFor(widget, tt):
    widget.setToolTip(wrap_msg(tt))


def create_checkbox(title, tt, state):
    cb = QCheckBox(title)
    cb.setToolTip(wrap_msg(tt))
    cb.setChecked(bool(state))
    return cb


class KOBOTOUCHConfig(TabbedDeviceConfig):

    def __init__(self, device_settings, all_formats, supports_subdirs,
                    must_read_metadata, supports_use_author_sort,
                    extra_customization_message, device, extra_customization_choices=None, parent=None):

        super(KOBOTOUCHConfig, self).__init__(device_settings, all_formats, supports_subdirs,
                    must_read_metadata, supports_use_author_sort,
                    extra_customization_message, device, extra_customization_choices, parent)

        self.device_settings = device_settings
        self.all_formats = all_formats
        self.supports_subdirs = supports_subdirs
        self.must_read_metadata = must_read_metadata
        self.supports_use_author_sort = supports_use_author_sort
        self.extra_customization_message = extra_customization_message
        self.extra_customization_choices = extra_customization_choices

        self.tab1 = Tab1Config(self, self.device)
        self.tab2 = Tab2Config(self, self.device)

        self.addDeviceTab(self.tab1, _("Collections, covers && uploads"))
        self.addDeviceTab(self.tab2, _('Metadata, on device && advanced'))

    def get_pref(self, key):
        return self.device.get_pref(key)

    @property
    def device(self):
        return self._device()

    def validate(self):
        validated = super(KOBOTOUCHConfig, self).validate()
        validated &= self.tab2.validate()
        return validated

    @property
    def book_uploads_options(self):
        return self.tab1.book_uploads_options

    @property
    def collections_options(self):
        return self.tab1.collections_options

    @property
    def cover_options(self):
        return self.tab1.covers_options

    @property
    def device_list_options(self):
        return self.tab2.device_list_options

    @property
    def advanced_options(self):
        return self.tab2.advanced_options

    @property
    def metadata_options(self):
        return self.tab2.metadata_options

    def commit(self):
        debug_print("KOBOTOUCHConfig::commit: start")
        p = super(KOBOTOUCHConfig, self).commit()

        p['manage_collections'] = self.manage_collections
        p['create_collections'] = self.create_collections
        p['collections_columns'] = self.collections_columns
        p['ignore_collections_names'] = self.ignore_collections_names
        p['delete_empty_collections'] = self.delete_empty_collections

        p['upload_covers'] = self.upload_covers
        p['keep_cover_aspect'] = self.keep_cover_aspect
        p['upload_grayscale'] = self.upload_grayscale
        p['dithered_covers'] = self.dithered_covers
        p['letterbox_fs_covers'] = self.letterbox_fs_covers
        p['png_covers'] = self.png_covers

        p['show_recommendations'] = self.show_recommendations
        p['show_previews'] = self.show_previews
        p['show_archived_books'] = self.show_archived_books

        p['update_device_metadata'] = self.update_device_metadata
        p['update_series'] = self.update_series
        p['update_core_metadata'] = self.update_core_metadata
        p['update_purchased_kepubs'] = self.update_purchased_kepubs
        p['subtitle_template'] = self.subtitle_template
        p['update_subtitle'] = self.update_subtitle

        p['modify_css'] = self.modify_css
        p['override_kobo_replace_existing'] = self.override_kobo_replace_existing

        p['support_newer_firmware'] = self.support_newer_firmware
        p['debugging_title'] = self.debugging_title
        p['driver_version'] = '.'.join([unicode_type(i) for i in self.device.version])

        return p


class Tab1Config(DeviceConfigTab):  # {{{

    def __init__(self, parent, device):
        super(Tab1Config, self).__init__(parent)

        self.l = QVBoxLayout(self)
        self.setLayout(self.l)

        self.collections_options = CollectionsGroupBox(self, device)
        self.l.addWidget(self.collections_options)
        self.addDeviceWidget(self.collections_options)

        self.covers_options = CoversGroupBox(self, device)
        self.l.addWidget(self.covers_options)
        self.addDeviceWidget(self.covers_options)

        self.book_uploads_options = BookUploadsGroupBox(self, device)
        self.l.addWidget(self.book_uploads_options)
        self.addDeviceWidget(self.book_uploads_options)

        self.l.addStretch()
# }}}


class Tab2Config(DeviceConfigTab):  # {{{

    def __init__(self, parent, device):
        super(Tab2Config, self).__init__(parent)

        self.l = QVBoxLayout(self)
        self.setLayout(self.l)

        self.metadata_options = MetadataGroupBox(self, device)
        self.l.addWidget(self.metadata_options)
        self.addDeviceWidget(self.metadata_options)

        self.device_list_options = DeviceListGroupBox(self, device)
        self.l.addWidget(self.device_list_options)
        self.addDeviceWidget(self.device_list_options)

        self.advanced_options = AdvancedGroupBox(self, device)
        self.l.addWidget(self.advanced_options)
        self.addDeviceWidget(self.advanced_options)

        self.l.addStretch()

    def validate(self):
        return self.metadata_options.validate()

# }}}


class BookUploadsGroupBox(DeviceOptionsGroupBox):

    def __init__(self, parent, device):
        super(BookUploadsGroupBox, self).__init__(parent, device)
        self.setTitle(_("Uploading of books"))

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.modify_css_checkbox = create_checkbox(
                _("Modify CSS"),
                _('This allows addition of user CSS rules and removal of some CSS. '
                'When sending a book, the driver adds the contents of {0} to all stylesheets in the EPUB. '
                'This file is searched for in the root directory of the main memory of the device. '
                'As well as this, if the file contains settings for the "orphans" or "widows", '
                'these are removed for all styles in the original stylesheet.').format(device.KOBO_EXTRA_CSSFILE),
                device.get_pref('modify_css')
                )
        self.override_kobo_replace_existing_checkbox = create_checkbox(
                _("Do not treat replacements as new books"),
                _('When a new book is side-loaded, the Kobo firmware imports details of the book into the internal database. '
                'Even if the book is a replacement for an existing book, the Kobo will remove the book from the database and then treat it as a new book. '
                'This means that the reading status, bookmarks and collections for the book will be lost. '
                'This option overrides firmware behavior and attempts to prevent a book that has been resent from being treated as a new book. '
                'If you prefer to have replacements treated as new books, turn this option off.'
                ),
                device.get_pref('override_kobo_replace_existing')
                )

        self.options_layout.addWidget(self.modify_css_checkbox, 0, 0, 1, 2)
        self.options_layout.addWidget(self.override_kobo_replace_existing_checkbox, 1, 0, 1, 2)

    @property
    def modify_css(self):
        return self.modify_css_checkbox.isChecked()

    @property
    def override_kobo_replace_existing(self):
        return self.override_kobo_replace_existing_checkbox.isChecked()


class CollectionsGroupBox(DeviceOptionsGroupBox):

    def __init__(self, parent, device):
        super(CollectionsGroupBox, self).__init__(parent, device)
        self.setTitle(_("Collections"))

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.setCheckable(True)
        self.setChecked(device.get_pref('manage_collections'))
        self.setToolTip(wrap_msg(_('Create new bookshelves on the Kobo if they do not exist. This is only for firmware V2.0.0 or later.')))

        self.collections_columns_label = QLabel(_('Collections columns:'))
        self.collections_columns_edit = QLineEdit(self)
        self.collections_columns_edit.setToolTip(_('The Kobo from firmware V2.0.0 supports bookshelves.'
                ' These are created on the Kobo. '
                'Specify a tags type column for automatic management.'))
        self.collections_columns_edit.setText(device.get_pref('collections_columns'))

        self.create_collections_checkbox = create_checkbox(
                         _("Create collections"),
                         _('Create new bookshelves on the Kobo if they do not exist. This is only for firmware V2.0.0 or later.'),
                         device.get_pref('create_collections')
                         )
        self.delete_empty_collections_checkbox = create_checkbox(
                         _('Delete empty bookshelves'),
                         _('Delete any empty bookshelves from the Kobo when syncing is finished. This is only for firmware V2.0.0 or later.'),
                         device.get_pref('delete_empty_collections')
                         )

        self.ignore_collections_names_label = QLabel(_('Ignore collections:'))
        self.ignore_collections_names_edit = QLineEdit(self)
        self.ignore_collections_names_edit.setToolTip(_('List the names of collections to be ignored by '
                'the collection management. The collections listed '
                'will not be changed. Names are separated by commas.'))
        self.ignore_collections_names_edit.setText(device.get_pref('ignore_collections_names'))

        self.options_layout.addWidget(self.collections_columns_label,         1, 0, 1, 1)
        self.options_layout.addWidget(self.collections_columns_edit,          1, 1, 1, 1)
        self.options_layout.addWidget(self.create_collections_checkbox,       2, 0, 1, 2)
        self.options_layout.addWidget(self.delete_empty_collections_checkbox, 3, 0, 1, 2)
        self.options_layout.addWidget(self.ignore_collections_names_label,    4, 0, 1, 1)
        self.options_layout.addWidget(self.ignore_collections_names_edit,     4, 1, 1, 1)

    @property
    def manage_collections(self):
        return self.isChecked()

    @property
    def collections_columns(self):
        return self.collections_columns_edit.text().strip()

    @property
    def create_collections(self):
        return self.create_collections_checkbox.isChecked()

    @property
    def delete_empty_collections(self):
        return self.delete_empty_collections_checkbox.isChecked()

    @property
    def ignore_collections_names(self):
        return self.ignore_collections_names_edit.text().strip()


class CoversGroupBox(DeviceOptionsGroupBox):

    def __init__(self, parent, device):
        super(CoversGroupBox, self).__init__(parent, device)
        self.setTitle(_("Upload covers"))

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.setCheckable(True)
        self.setChecked(device.get_pref('upload_covers'))
        self.setToolTip(wrap_msg(_('Upload cover images from the calibre library when sending books to the device.')))

        self.upload_grayscale_checkbox = create_checkbox(
                             _('Upload black and white covers'),
                             _('Convert covers to grayscale when uploading.'),
                             device.get_pref('upload_grayscale')
                             )

        self.dithered_covers_checkbox = create_checkbox(
                             _('Upload dithered covers'),
                             _('Dither cover images to the appropriate 16c grayscale palette for an eInk screen.'
                               ' This usually ensures greater accuracy and avoids banding, making sleep covers look better.'
                               ' On FW >= 4.11, Nickel itself may sometimes do a decent job of it.'
                               ' Has no effect without "Upload black and white covers"!'),
                             device.get_pref('dithered_covers')
                             )
        # Make it visually depend on B&W being enabled!
        # c.f., https://stackoverflow.com/q/36281103
        self.dithered_covers_checkbox.setEnabled(device.get_pref('upload_grayscale'))
        self.upload_grayscale_checkbox.toggled.connect(self.dithered_covers_checkbox.setEnabled)
        self.upload_grayscale_checkbox.toggled.connect(
            lambda checked: not checked and self.dithered_covers_checkbox.setChecked(False))

        self.keep_cover_aspect_checkbox = create_checkbox(
                             _('Keep cover aspect ratio'),
                             _('When uploading covers, do not change the aspect ratio when resizing for the device.'
                               ' This is for firmware versions 2.3.1 and later.'),
                             device.get_pref('keep_cover_aspect'))

        self.letterbox_fs_covers_checkbox = create_checkbox(
                             _('Letterbox full-screen covers'),
                             _('Do it on our end, instead of letting Nickel handle it.'
                               ' Provides pixel-perfect results on devices where Nickel does not do extra processing.'
                               ' Obviously has no effect without "Keep cover aspect ratio".'
                               ' This is probably undesirable if you disable the "Show book covers full screen"'
                               ' setting on your device.'),
                             device.get_pref('letterbox_fs_covers'))
        # Make it visually depend on AR being enabled!
        self.letterbox_fs_covers_checkbox.setEnabled(device.get_pref('keep_cover_aspect'))
        self.keep_cover_aspect_checkbox.toggled.connect(self.letterbox_fs_covers_checkbox.setEnabled)
        self.keep_cover_aspect_checkbox.toggled.connect(
            lambda checked: not checked and self.letterbox_fs_covers_checkbox.setChecked(False))

        self.png_covers_checkbox = create_checkbox(
                             _('Save covers as PNG'),
                             _('Use the PNG image format instead of JPG.'
                               ' Higher quality, especially with "Upload dithered covers" enabled,'
                               ' which will also help generate potentially smaller files.'
                               ' Behavior completely unknown on old (< 3.x) Kobo firmwares,'
                               ' known to behave on FW >= 4.8.'
                               ' Has no effect without "Upload black and white covers"!'),
                             device.get_pref('png_covers'))
        # Make it visually depend on B&W being enabled, to avoid storing ridiculously large color PNGs.
        self.png_covers_checkbox.setEnabled(device.get_pref('upload_grayscale'))
        self.upload_grayscale_checkbox.toggled.connect(self.png_covers_checkbox.setEnabled)
        self.upload_grayscale_checkbox.toggled.connect(
            lambda checked: not checked and self.png_covers_checkbox.setChecked(False))

        self.options_layout.addWidget(self.keep_cover_aspect_checkbox,    0, 0, 1, 1)
        self.options_layout.addWidget(self.letterbox_fs_covers_checkbox,  0, 1, 1, 1)
        self.options_layout.addWidget(self.upload_grayscale_checkbox,     1, 0, 1, 1)
        self.options_layout.addWidget(self.dithered_covers_checkbox,      1, 1, 1, 1)
        self.options_layout.addWidget(self.png_covers_checkbox,           2, 1, 1, 1)

    @property
    def upload_covers(self):
        return self.isChecked()

    @property
    def upload_grayscale(self):
        return self.upload_grayscale_checkbox.isChecked()

    @property
    def dithered_covers(self):
        return self.dithered_covers_checkbox.isChecked()

    @property
    def keep_cover_aspect(self):
        return self.keep_cover_aspect_checkbox.isChecked()

    @property
    def letterbox_fs_covers(self):
        return self.letterbox_fs_covers_checkbox.isChecked()

    @property
    def png_covers(self):
        return self.png_covers_checkbox.isChecked()


class DeviceListGroupBox(DeviceOptionsGroupBox):

    def __init__(self, parent, device):
        super(DeviceListGroupBox, self).__init__(parent, device)
        self.setTitle(_("Show as on device"))

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.show_recommendations_checkbox = create_checkbox(
                             _("Show recommendations"),
                             _('Kobo shows recommendations on the device.  In some cases these have '
                               'files but in other cases they are just pointers to the web site to buy. '
                               'Enable if you wish to see/delete them.'),
                             device.get_pref('show_recommendations')
                             )

        self.show_archived_books_checkbox = create_checkbox(
                             _("Show archived books"),
                             _('Archived books are listed on the device but need to be downloaded to read.'
                               ' Use this option to show these books and match them with books in the calibre library.'),
                             device.get_pref('show_archived_books')
                             )

        self.show_previews_checkbox = create_checkbox(
                             _('Show previews'),
                             _('Kobo previews are included on the Touch and some other versions'
                               ' by default they are no longer displayed as there is no good reason to '
                               'see them.  Enable if you wish to see/delete them.'),
                             device.get_pref('show_previews')
                             )

        self.options_layout.addWidget(self.show_recommendations_checkbox, 0, 0, 1, 1)
        self.options_layout.addWidget(self.show_archived_books_checkbox,  1, 0, 1, 1)
        self.options_layout.addWidget(self.show_previews_checkbox,        2, 0, 1, 1)

    @property
    def show_recommendations(self):
        return self.show_recommendations_checkbox.isChecked()

    @property
    def show_archived_books(self):
        return self.show_archived_books_checkbox.isChecked()

    @property
    def show_previews(self):
        return self.show_previews_checkbox.isChecked()


class AdvancedGroupBox(DeviceOptionsGroupBox):

    def __init__(self, parent, device):
        super(AdvancedGroupBox, self).__init__(parent, device, _("Advanced options"))
#         self.setTitle(_("Advanced Options"))

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.support_newer_firmware_checkbox = create_checkbox(
                            _("Attempt to support newer firmware"),
                            _('Kobo routinely updates the firmware and the '
                              'database version. With this option calibre will attempt '
                              'to perform full read-write functionality - Here be Dragons!! '
                              'Enable only if you are comfortable with restoring your kobo '
                              'to factory defaults and testing software. '
                              'This driver supports firmware V2.x.x and DBVersion up to ') + unicode_type(
                                  device.supported_dbversion), device.get_pref('support_newer_firmware')
                             )

        self.debugging_title_checkbox = create_checkbox(
                             _("Title to test when debugging"),
                             _('Part of title of a book that can be used when doing some tests for debugging. '
                               'The test is to see if the string is contained in the title of a book. '
                               'The better the match, the less extraneous output.'),
                             device.get_pref('debugging_title')
                             )
        self.debugging_title_label = QLabel(_('Title to test when debugging:'))
        self.debugging_title_edit = QLineEdit(self)
        self.debugging_title_edit.setToolTip(_('Part of title of a book that can be used when doing some tests for debugging. '
                    'The test is to see if the string is contained in the title of a book. '
                    'The better the match, the less extraneous output.'))
        self.debugging_title_edit.setText(device.get_pref('debugging_title'))
        self.debugging_title_label.setBuddy(self.debugging_title_edit)

        self.options_layout.addWidget(self.support_newer_firmware_checkbox,   0, 0, 1, 2)
        self.options_layout.addWidget(self.debugging_title_label,             1, 0, 1, 1)
        self.options_layout.addWidget(self.debugging_title_edit,              1, 1, 1, 1)

    @property
    def support_newer_firmware(self):
        return self.support_newer_firmware_checkbox.isChecked()

    @property
    def debugging_title(self):
        return self.debugging_title_edit.text().strip()


class MetadataGroupBox(DeviceOptionsGroupBox):

    def __init__(self, parent, device):
        super(MetadataGroupBox, self).__init__(parent, device)
        self.setTitle(_("Update metadata on the device"))

        self.options_layout = QGridLayout()
        self.options_layout.setObjectName("options_layout")
        self.setLayout(self.options_layout)

        self.setCheckable(True)
        self.setChecked(device.get_pref('update_device_metadata'))
        self.setToolTip(wrap_msg(_('Update the metadata on the device when it is connected. '
                               'Be careful when doing this as it will take time and could make the initial connection take a long time.')))

        self.update_series_checkbox = create_checkbox(
                             _("Set series information"),
                             _('The book lists on the Kobo devices can display series information. '
                               'This is not read by the device from the sideloaded books. '
                               'Series information can only be added to the device after the book has been processed by the device. '
                               'Enable if you wish to set series information.'),
                             device.get_pref('update_series')
                             )
        self.update_core_metadata_checkbox = create_checkbox(
                             _("Update metadata on Book Details pages"),
                             _('This will update the metadata in the device database when the device is connected. '
                               'The metadata updated is displayed on the device in the library and the book details page. '
                               'This is the title, authors, comments/synopsis, series name and number, publisher and published Date, ISBN and language. '
                               'If a metadata plugboard exists for the device and book format, this will be used to set the metadata.'
                               ),
                             device.get_pref('update_core_metadata')
                             )

        self.update_purchased_kepubs_checkbox = create_checkbox(
                             _("Update purchased books"),
                             _('Update books purchased from Kobo and downloaded to the device.'
                               ),
                             device.get_pref('update_purchased_kepubs')
                             )
        self.update_subtitle_checkbox = create_checkbox(
                             _("Subtitle"),
                             _('Update the subtitle on the device using a template.'),
                             device.get_pref('update_subtitle')
                             )
        self.subtitle_template_edit = TemplateConfig(
                            device.get_pref('subtitle_template'),
                            tooltip=_("Enter a template to use to set the subtitle. "
                                      "If the template is empty, the subtitle will be cleared."
                                      )
                            )

        self.options_layout.addWidget(self.update_series_checkbox, 0, 0, 1, 2)
        self.options_layout.addWidget(self.update_core_metadata_checkbox, 1, 0, 1, 2)
        self.options_layout.addWidget(self.update_subtitle_checkbox, 2, 0, 1, 1)
        self.options_layout.addWidget(self.subtitle_template_edit, 2, 1, 1, 1)
        self.options_layout.addWidget(self.update_purchased_kepubs_checkbox, 3, 0, 1, 2)

        self.update_core_metadata_checkbox.clicked.connect(self.update_core_metadata_checkbox_clicked)
        self.update_subtitle_checkbox.clicked.connect(self.update_subtitle_checkbox_clicked)
        self.update_core_metadata_checkbox_clicked(device.get_pref('update_core_metadata'))
        self.update_subtitle_checkbox_clicked(device.get_pref('update_subtitle'))

    def update_core_metadata_checkbox_clicked(self, checked):
        self.update_series_checkbox.setEnabled(not checked)
        self.subtitle_template_edit.setEnabled(checked)
        self.update_subtitle_checkbox.setEnabled(checked)
        self.update_subtitle_checkbox_clicked(self.update_subtitle)
        self.update_purchased_kepubs_checkbox.setEnabled(checked)

    def update_subtitle_checkbox_clicked(self, checked):
        self.subtitle_template_edit.setEnabled(checked and self.update_core_metadata)

    def edit_template(self):
        t = TemplateDialog(self, self.template)
        t.setWindowTitle(_('Edit template'))
        if t.exec_():
            self.t.setText(t.rule[1])

    def validate(self):
        if self.update_subtitle and not self.subtitle_template_edit.validate():
            return False
        return True

    @property
    def update_series(self):
        return self.update_series_checkbox.isChecked()

    @property
    def update_core_metadata(self):
        return self.update_core_metadata_checkbox.isChecked()

    @property
    def update_purchased_kepubs(self):
        return self.update_purchased_kepubs_checkbox.isChecked()

    @property
    def update_device_metadata(self):
        return self.isChecked()

    @property
    def subtitle_template(self):
        return self.subtitle_template_edit.template

    @property
    def update_subtitle(self):
        return self.update_subtitle_checkbox.isChecked()


class TemplateConfig(QWidget):  # {{{

    def __init__(self, val, tooltip=None):
        QWidget.__init__(self)
        self.t = t = QLineEdit(self)
        t.setText(val or '')
        t.setCursorPosition(0)
        self.setMinimumWidth(300)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        l.addWidget(t, 1, 0, 1, 1)
        b = self.b = QPushButton(_('&Template editor'))
        l.addWidget(b, 1, 1, 1, 1)
        b.clicked.connect(self.edit_template)
        self.setToolTip(tooltip)

    @property
    def template(self):
        return unicode_type(self.t.text()).strip()

    @template.setter
    def template(self, template):
        self.t.setText(template)

    def edit_template(self):
        t = TemplateDialog(self, self.template)
        t.setWindowTitle(_('Edit template'))
        if t.exec_():
            self.t.setText(t.rule[1])

    def validate(self):
        from calibre.utils.formatter import validation_formatter

        tmpl = self.template
        try:
            validation_formatter.validate(tmpl)
            return True
        except Exception as err:
            error_dialog(self, _('Invalid template'),
                    '<p>'+_('The template "%s" is invalid:')%tmpl +
                    '<br>'+unicode_type(err), show=True)

            return False
# }}}


if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.devices.kobo.driver import KOBOTOUCH
    from calibre.devices.scanner import DeviceScanner
    s = DeviceScanner()
    s.scan()
    app = Application([])
    debug_print("KOBOTOUCH:", KOBOTOUCH)
    dev = KOBOTOUCH(None)
#     dev.startup()
#     cd = dev.detect_managed_devices(s.devices)
#     dev.open(cd, 'test')
    cw = dev.config_widget()
    d = QDialog()
    d.l = QVBoxLayout()
    d.setLayout(d.l)
    d.l.addWidget(cw)
    bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
    d.l.addWidget(bb)
    bb.accepted.connect(d.accept)
    bb.rejected.connect(d.reject)
    if d.exec_() == d.Accepted:
        cw.commit()
    dev.shutdown()
