
.. include:: global.rst

.. _portablecalibre:

Creating your own portable/customized calibre install
=======================================================

You can "install" calibre onto a USB stick that you can take with you and use on any computer. The magic is in a .bat file called calibre-portable.bat found in the resources folder in your calibre install. Typical uses of this files are:

    * Run a Mobile Calibre installation with both the Calibre binaries and your ebook library resident on a USB disk or other portable media. In particular it is not necessary to have Calibre installed on the Windows PC that is to run Calibre. This batch file also does not care what drive letter is assigned when you plug in the USB device. It also will not affect any settings on the host machine being a completely self-contained Calibre installation.
    * Run a networked Calibre installation optimised for performance when the ebook files are located on a networked share.


This calibre-portable.bat file is intended for use on Windows based systems, but the principles are easily adapted for use on Linux or OS X based systems. Note that calibre requires the Microsoft Visual C++ 2008 runtimes to run. Most windows computers have them installed already, but it may be a good idea to have the installer for installing them on your USB stick. The installer is available from `Microsoft <http://www.microsoft.com/downloads/details.aspx?FamilyID=9b2da534-3e03-4391-8a4d-074b9f2bc1bf&displaylang=en>`_.

Assumptions
------------

The calibre-portable.bat file makes the following assumptions about the folder layout that is being used::

    Calibre_Root_Folder
        calibre-portable.bat    The batch file used to start Calibre
        Calibre2                The Calibre binaries
        CalibreLibrary          The Calibre Library
        CalibreConfig           The Calibre user preferences
        CalibreSource           The calibre source (optional) if running a development environment.

If you want to use a different folder layout then the calibre-portable.bat file will need editing appropriately. This file can be edited using any appropriate text editor.

Preparation
------------

The steps required to prepare the USB stick are as follows:

    * Decide what folder will be used to hold all the Calibre related files.  If the portable media is to be dedicated to Calibre use then this can be the root folder, but if not is suggested that a folder called  Calibre should be created – this will then be the Calibre_Root_Folder mentioned above and in the following steps.
    * Copy the calibre-portable.bat file into the Calibre_Root_Folder.
    * Create the Calibre2 folder inside the Calibre_Root_Folder to hold the Calibre binaries. There are 2 ways of populating the contents of this folder:

        * The easiest is to simply copy an existing Calibre installation. Typically this would involve copying the contents of the C:\Program Files\Calibre2 folder
        * Run the Calibre Windows installer:

            * Tick the box to accept the GNU GPL license
            * Select the Advanced option
            * Change the install location to be the Calibre2 folder on the USB drive
            * Deselect the options for creating Menu shortcuts; creating a calibre shortcut on the desktop; and adding Calibre to the path

    * Create the CalibreLibrary folder inside the Calibre_Root_Folder.  If you have an existing Calibre library copy it and all its contents to the CalibreLibrary folder.  If you do not already have a library do not worry as a new one will be created at this location when Calibre is started.
    * Create the CalibreConfig folder inside the Calibre_Root_Folder.   This will hold your personal Calibre configuration settings.   If you have an existing Calibre installation and want to copy the current settings then copy the contents of your current configuration folder to the CalibreConfig folder.   You can find the location of your current configuration folder by going to :guilabel:`Preferences->Advanced->Miscellaneous` and clicking the “Open calibre configuration Directory” button.
    * When you have started Calibre, go into :guilabel:`Preferences->Interface->Behavior` and check that you have set the Job Priority to ‘Low’. This setting keeps single-processor Windows systems responsive without affecting Calibre performance to any noticeable degree.  On multi-processor or multi-core systems this setting does not matter as much, but setting it will do no harm.

Using calibre-portable.bat
---------------------------

Once you have got the USB stick set up then the steps to use Calibre are:

    * Plug the USB stick into the host machine
    * Use Windows Explorer to navigate to the location of the calibre-portable.bat file on the USB stick
    * Start Calibre by double-clicking the calibre-portable.bat file
    * A Command Window will be opened showing the settings that are about to be used.  If you are not happy with these setting use CTRL-C to abandon the batch file without starting Calibre.  If you are happy then press any other key to launch Calibre with the specified settings.   Once you are happy with your setup you may wish to edit the calibre-portable.bat file to eliminate this pause (add REM to the start of the line) but it a useful check that you are running with the expected settings.

Networked Installations
--------------------------

The performance of Calibre can be severely degraded if running with the Calibre library on a network share.   This is primarily due to the fact that the access to the metadata.db file is slow across a network.  The calibre-portable.bat file is designed to help in such scenarios.    To use the calibre-portable.bat file in such a scenario the following deviations from those detailed above for the Mobile Calibre installation are needed:

    * Edit the calibre-portable.bat file to specify the location of your Calibre library on the network.  
    * Create a CalibreMetadata folder in the Calibre_Root_Folder location.   If you have an existing Calibre library then copy the metadata.db files from there to the CalibreMetadata folder.
    * You can now run Calibre using the calibre-portable.bat file as specified in the previous section.    One thing you should remember is to periodically copy the metadata.db file from the CalibreMetadatqa folder back to your Calibre library located on the network share.

Precautions
--------------

Portable media can occasionally fail so you should make periodic backups of you Calibre library.   This can be done by making a copy of the CalibreLibrary folder and all its contents.   There are many freely available tools around that can optimise such back processes, well known ones being RoboCopy and RichCopy.   However you can simply use a Windows copy facility if you cannot be bothered to use a specialised tools.

Using the environment variable CALIBRE_OVERRIDE_DATABASE_PATH disables multiple-library support in |app|. Avoid setting this variable in calibre-portable.bat unless you really need it.