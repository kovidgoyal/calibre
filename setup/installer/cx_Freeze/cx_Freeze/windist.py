import distutils.command.bdist_msi
import msilib
import os

__all__ = [ "bdist_msi" ]

# force the remove existing products action to happen first since Windows
# installer appears to be braindead and doesn't handle files shared between
# different "products" very well
sequence = msilib.sequence.InstallExecuteSequence
for index, info in enumerate(sequence):
    if info[0] == u'RemoveExistingProducts':
        sequence[index] = (info[0], info[1], 1450)


class bdist_msi(distutils.command.bdist_msi.bdist_msi):
    user_options = distutils.command.bdist_msi.bdist_msi.user_options + [
        ('add-to-path=', None, 'add target dir to PATH environment variable'),
        ('upgrade-code=', None, 'upgrade code to use')
    ]
    x = y = 50
    width = 370
    height = 300
    title = "[ProductName] Setup"
    modeless = 1
    modal = 3

    def add_config(self, fullname):
        initialTargetDir = self.get_initial_target_dir(fullname)
        if self.add_to_path is None:
            self.add_to_path = False
            for executable in self.distribution.executables:
                if os.path.basename(executable.base).startswith("Console"):
                    self.add_to_path = True
                    break
        if self.add_to_path:
            msilib.add_data(self.db, 'Environment',
                    [("E_PATH", "Path", r"[~];[TARGETDIR]", "TARGETDIR")])
        msilib.add_data(self.db, 'CustomAction',
                [("InitialTargetDir", 256 + 51, "TARGETDIR", initialTargetDir)
                ])
        msilib.add_data(self.db, 'InstallExecuteSequence',
                [("InitialTargetDir", 'TARGETDIR=""', 401)])
        msilib.add_data(self.db, 'InstallUISequence',
                [("PrepareDlg", None, 140),
                 ("InitialTargetDir", 'TARGETDIR=""', 401),
                 ("SelectDirectoryDlg", "not Installed", 1230),
                 ("MaintenanceTypeDlg",
                        "Installed and not Resume and not Preselected", 1250),
                 ("ProgressDlg", None, 1280)
                ])

    def add_cancel_dialog(self):
        dialog = msilib.Dialog(self.db, "CancelDlg", 50, 10, 260, 85, 3,
                self.title, "No", "No", "No")
        dialog.text("Text", 48, 15, 194, 30, 3,
                "Are you sure you want to cancel [ProductName] installation?")
        button = dialog.pushbutton("Yes", 72, 57, 56, 17, 3, "Yes", "No")
        button.event("EndDialog", "Exit")
        button = dialog.pushbutton("No", 132, 57, 56, 17, 3, "No", "Yes")
        button.event("EndDialog", "Return")

    def add_error_dialog(self):
        dialog = msilib.Dialog(self.db, "ErrorDlg", 50, 10, 330, 101, 65543,
                self.title, "ErrorText", None, None)
        dialog.text("ErrorText", 50, 9, 280, 48, 3, "")
        for text, x in [("No", 120), ("Yes", 240), ("Abort", 0),
                ("Cancel", 42), ("Ignore", 81), ("Ok", 159), ("Retry", 198)]:
            button = dialog.pushbutton(text[0], x, 72, 81, 21, 3, text, None)
            button.event("EndDialog", "Error%s" % text)

    def add_exit_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db, "ExitDialog",
                self.x, self.y, self.width, self.height, self.modal,
                self.title, "Finish", "Finish", "Finish")
        dialog.title("Completing the [ProductName] installer")
        dialog.back("< Back", "Finish", active = False)
        dialog.cancel("Cancel", "Back", active = False)
        dialog.text("Description", 15, 235, 320, 20, 0x30003,
                "Click the Finish button to exit the installer.")
        button = dialog.next("Finish", "Cancel", name = "Finish")
        button.event("EndDialog", "Return")

    def add_fatal_error_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db, "FatalError",
                self.x, self.y, self.width, self.height, self.modal,
                self.title, "Finish", "Finish", "Finish")
        dialog.title("[ProductName] installer ended prematurely")
        dialog.back("< Back", "Finish", active = False)
        dialog.cancel("Cancel", "Back", active = False)
        dialog.text("Description1", 15, 70, 320, 80, 0x30003,
                "[ProductName] setup ended prematurely because of an error. "
                "Your system has not been modified. To install this program "
                "at a later time, please run the installation again.")
        dialog.text("Description2", 15, 155, 320, 20, 0x30003,
                "Click the Finish button to exit the installer.")
        button = dialog.next("Finish", "Cancel", name = "Finish")
        button.event("EndDialog", "Exit")

    def add_files_in_use_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db, "FilesInUse",
                self.x, self.y, self.width, self.height, 19, self.title,
                "Retry", "Retry", "Retry", bitmap = False)
        dialog.text("Title", 15, 6, 200, 15, 0x30003,
                r"{\DlgFontBold8}Files in Use")
        dialog.text("Description", 20, 23, 280, 20, 0x30003,
                "Some files that need to be updated are currently in use.")
        dialog.text("Text", 20, 55, 330, 50, 3,
                "The following applications are using files that need to be "
                "updated by this setup. Close these applications and then "
                "click Retry to continue the installation or Cancel to exit "
                "it.")
        dialog.control("List", "ListBox", 20, 107, 330, 130, 7,
                "FileInUseProcess", None, None, None)
        button = dialog.back("Exit", "Ignore", name = "Exit")
        button.event("EndDialog", "Exit")
        button = dialog.next("Ignore", "Retry", name = "Ignore")
        button.event("EndDialog", "Ignore")
        button = dialog.cancel("Retry", "Exit", name = "Retry")
        button.event("EndDialog", "Retry")

    def add_maintenance_type_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db,
                "MaintenanceTypeDlg", self.x, self.y, self.width, self.height,
                self.modal, self.title, "Next", "Next", "Cancel")
        dialog.title("Welcome to the [ProductName] Setup Wizard")
        dialog.text("BodyText", 15, 63, 330, 42, 3,
                "Select whether you want to repair or remove [ProductName].")
        group = dialog.radiogroup("RepairRadioGroup", 15, 108, 330, 60, 3,
                "MaintenanceForm_Action", "", "Next")
        group.add("Repair", 0, 18, 300, 17, "&Repair [ProductName]")
        group.add("Remove", 0, 36, 300, 17, "Re&move [ProductName]")
        dialog.back("< Back", None, active = False)
        button = dialog.next("Finish", "Cancel")
        button.event("[REINSTALL]", "ALL",
                'MaintenanceForm_Action="Repair"', 5)
        button.event("[Progress1]", "Repairing",
                'MaintenanceForm_Action="Repair"', 6)
        button.event("[Progress2]", "repairs",
                'MaintenanceForm_Action="Repair"', 7)
        button.event("Reinstall", "ALL",
                'MaintenanceForm_Action="Repair"', 8)
        button.event("[REMOVE]", "ALL",
                'MaintenanceForm_Action="Remove"', 11)
        button.event("[Progress1]", "Removing",
                'MaintenanceForm_Action="Remove"', 12)
        button.event("[Progress2]", "removes",
                'MaintenanceForm_Action="Remove"', 13)
        button.event("Remove", "ALL",
                'MaintenanceForm_Action="Remove"', 14)
        button.event("EndDialog", "Return",
                'MaintenanceForm_Action<>"Change"', 20)
        button = dialog.cancel("Cancel", "RepairRadioGroup")
        button.event("SpawnDialog", "CancelDlg")

    def add_prepare_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db, "PrepareDlg",
                self.x, self.y, self.width, self.height, self.modeless,
                self.title, "Cancel", "Cancel", "Cancel")
        dialog.text("Description", 15, 70, 320, 40, 0x30003,
                "Please wait while the installer prepares to guide you through"
                "the installation.")
        dialog.title("Welcome to the [ProductName] installer")
        text = dialog.text("ActionText", 15, 110, 320, 20, 0x30003,
                "Pondering...")
        text.mapping("ActionText", "Text")
        text = dialog.text("ActionData", 15, 135, 320, 30, 0x30003, None)
        text.mapping("ActionData", "Text")
        dialog.back("Back", None, active = False)
        dialog.next("Next", None, active = False)
        button = dialog.cancel("Cancel", None)
        button.event("SpawnDialog", "CancelDlg")

    def add_progress_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db, "ProgressDlg",
                self.x, self.y, self.width, self.height, self.modeless,
                self.title, "Cancel", "Cancel", "Cancel", bitmap = False)
        dialog.text("Title", 20, 15, 200, 15, 0x30003,
                r"{\DlgFontBold8}[Progress1] [ProductName]")
        dialog.text("Text", 35, 65, 300, 30, 3,
                "Please wait while the installer [Progress2] [ProductName].")
        dialog.text("StatusLabel", 35, 100 ,35, 20, 3, "Status:")
        text = dialog.text("ActionText", 70, 100, self.width - 70, 20, 3,
                "Pondering...")
        text.mapping("ActionText", "Text")
        control = dialog.control("ProgressBar", "ProgressBar", 35, 120, 300,
                10, 65537, None, "Progress done", None, None)
        control.mapping("SetProgress", "Progress")
        dialog.back("< Back", "Next", active = False)
        dialog.next("Next >", "Cancel", active = False)
        button = dialog.cancel("Cancel", "Back")
        button.event("SpawnDialog", "CancelDlg")

    def add_properties(self):
        metadata = self.distribution.metadata
        props = [
                ('DistVersion', metadata.get_version()),
                ('DefaultUIFont', 'DlgFont8'),
                ('ErrorDialog', 'ErrorDlg'),
                ('Progress1', 'Install'),
                ('Progress2', 'installs'),
                ('MaintenanceForm_Action', 'Repair')
        ]
        email = metadata.author_email or metadata.maintainer_email
        if email:
            props.append(("ARPCONTACT", email))
        if metadata.url:
            props.append(("ARPURLINFOABOUT", metadata.url))
        if self.upgrade_code is not None:
            props.append(("UpgradeCode", self.upgrade_code))
        msilib.add_data(self.db, 'Property', props)

    def add_select_directory_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db,
                "SelectDirectoryDlg", self.x, self.y, self.width, self.height,
                self.modal, self.title, "Next", "Next", "Cancel")
        dialog.title("Select destination directory")
        dialog.back("< Back", None, active = False)
        button = dialog.next("Next >", "Cancel")
        button.event("SetTargetPath", "TARGETDIR", ordering = 1)
        button.event("SpawnWaitDialog", "WaitForCostingDlg", ordering = 2)
        button.event("EndDialog", "Return", ordering = 3)
        button = dialog.cancel("Cancel", "DirectoryCombo")
        button.event("SpawnDialog", "CancelDlg")
        dialog.control("DirectoryCombo", "DirectoryCombo", 15, 70, 272, 80,
                393219, "TARGETDIR", None, "DirectoryList", None)
        dialog.control("DirectoryList", "DirectoryList", 15, 90, 308, 136, 3,
                "TARGETDIR", None, "PathEdit", None)
        dialog.control("PathEdit", "PathEdit", 15, 230, 306, 16, 3,
                "TARGETDIR", None, "Next", None)
        button = dialog.pushbutton("Up", 306, 70, 18, 18, 3, "Up", None)
        button.event("DirectoryListUp", "0")
        button = dialog.pushbutton("NewDir", 324, 70, 30, 18, 3, "New", None)
        button.event("DirectoryListNew", "0")

    def add_text_styles(self):
        msilib.add_data(self.db, 'TextStyle',
                [("DlgFont8", "Tahoma", 9, None, 0),
                 ("DlgFontBold8", "Tahoma", 8, None, 1),
                 ("VerdanaBold10", "Verdana", 10, None, 1),
                 ("VerdanaRed9", "Verdana", 9, 255, 0)
                ])

    def add_ui(self):
        self.add_text_styles()
        self.add_error_dialog()
        self.add_fatal_error_dialog()
        self.add_cancel_dialog()
        self.add_exit_dialog()
        self.add_user_exit_dialog()
        self.add_files_in_use_dialog()
        self.add_wait_for_costing_dialog()
        self.add_prepare_dialog()
        self.add_select_directory_dialog()
        self.add_progress_dialog()
        self.add_maintenance_type_dialog()

    def add_upgrade_config(self, sversion):
        if self.upgrade_code is not None:
            msilib.add_data(self.db, 'Upgrade',
                    [(self.upgrade_code, None, sversion, None, 513, None,
                            "REMOVEOLDVERSION"),
                     (self.upgrade_code, sversion, None, None, 257, None,
                            "REMOVENEWVERSION")
                    ])

    def add_user_exit_dialog(self):
        dialog = distutils.command.bdist_msi.PyDialog(self.db, "UserExit",
                self.x, self.y, self.width, self.height, self.modal,
                self.title, "Finish", "Finish", "Finish")
        dialog.title("[ProductName] installer was interrupted")
        dialog.back("< Back", "Finish", active = False)
        dialog.cancel("Cancel", "Back", active = False)
        dialog.text("Description1", 15, 70, 320, 80, 0x30003,
                "[ProductName] setup was interrupted. Your system has not "
                "been modified. To install this program at a later time, "
                "please run the installation again.")
        dialog.text("Description2", 15, 155, 320, 20, 0x30003,
                "Click the Finish button to exit the installer.")
        button = dialog.next("Finish", "Cancel", name = "Finish")
        button.event("EndDialog", "Exit")

    def add_wait_for_costing_dialog(self):
        dialog = msilib.Dialog(self.db, "WaitForCostingDlg", 50, 10, 260, 85,
                self.modal, self.title, "Return", "Return", "Return")
        dialog.text("Text", 48, 15, 194, 30, 3,
                "Please wait while the installer finishes determining your "
                "disk space requirements.")
        button = dialog.pushbutton("Return", 102, 57, 56, 17, 3, "Return",
                None)
        button.event("EndDialog", "Exit")

    def get_initial_target_dir(self, fullname):
        return r"[ProgramFilesFolder]\%s" % fullname

    def get_installer_filename(self, fullname):
        return os.path.join(self.dist_dir, "%s.msi" % fullname)

    def initialize_options(self):
        distutils.command.bdist_msi.bdist_msi.initialize_options(self)
        self.upgrade_code = None
        self.add_to_path = None

    def run(self):
        if not self.skip_build:
            self.run_command('build')
        install = self.reinitialize_command('install', reinit_subcommands = 1)
        install.prefix = self.bdist_dir
        install.skip_build = self.skip_build
        install.warn_dir = 0
        distutils.log.info("installing to %s", self.bdist_dir)
        install.ensure_finalized()
        install.run()
        self.mkpath(self.dist_dir)
        fullname = self.distribution.get_fullname()
        filename = os.path.abspath(self.get_installer_filename(fullname))
        if os.path.exists(filename):
            os.unlink(filename)
        metadata = self.distribution.metadata
        author = metadata.author or metadata.maintainer or "UNKNOWN"
        version = metadata.get_version()
        sversion = "%d.%d.%d" % \
                distutils.version.StrictVersion(version).version
        self.db = msilib.init_database(filename, msilib.schema,
                self.distribution.metadata.name, msilib.gen_uuid(), sversion,
                author)
        msilib.add_tables(self.db, msilib.sequence)
        self.add_properties()
        self.add_config(fullname)
        self.add_upgrade_config(sversion)
        self.add_ui()
        self.add_files()
        self.db.Commit()
        if not self.keep_temp:
            distutils.dir_util.remove_tree(self.bdist_dir,
                    dry_run = self.dry_run)

