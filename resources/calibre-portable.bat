@echo OFF
REM Batch File to start a Calibre configuration on Windows
REM giving explicit control of the location of:
REM  - Calibe Program Files
REM  - Calibre Library Files
REM  - Calibre Config Files
REM  - Calibre Metadata database
REM  - Calibre Source files
REM  - Calibre Temp Files
REM By setting the paths correctly it can be used to run:
REM  - A "portable calibre" off a USB stick.
REM  - A network installation with local metadata database
REM    (for performance) and books stored on a network share 
REM  - A local installation using customised settings
REM
REM If trying to run off a USB stick then the folder structure
REM shown below is recommended (relative to the location of 
REM this batch file).  This can structure can also be used
REM when running of a local hard disk if you want to get the
REM level of control this batch file provides.
REM  - Calibre2			Location of program files
REM  - CalibreConfig		Location of Configuration files
REM  - CalibreLibrary		Location of Books and metadata
REM  - CalibreSource 		Location of Calibre Source files (Optional)
REM
REM This batch file is designed so that if you create the recommended
REM folder structure then it can be used 'as is' without modification.


REM -------------------------------------
REM Set up Calibre Config folder
REM
REM This is where user specific settings
REM are stored.
REM -------------------------------------

IF EXIST CalibreConfig (
	SET CALIBRE_CONFIG_DIRECTORY=%cd%\CalibreConfig
	ECHO CONFIG FILES:    %cd%\CalibreConfig
)


REM --------------------------------------------------------------
REM Specify Location of ebooks
REM
REM Location where Book files are located
REM Either set explicit path, or if running from a USB stick
REM a relative path can be used to avoid need to know the
REM drive letter of the USB stick.
REM
REM Comment out any of the following that are not to be used
REM (although leaving them in does not really matter)
REM --------------------------------------------------------------

IF EXIST U:\eBooks\CalibreLibrary (
	SET CALIBRE_LIBRARY_DIRECTORY=U:\eBOOKS\CalibreLibrary
	ECHO LIBRARY FILES:   U:\eBOOKS\CalibreLibrary
)
IF EXIST CalibreLibrary (
	SET CALIBRE_LIBRARY_DIRECTORY=%cd%\CalibreLibrary
	ECHO LIBRARY FILES:   %cd%\CalibreLibrary
)


REM --------------------------------------------------------------
REM Specify Location of metadata database (optional)
REM
REM Location where the metadata.db file is located.  If not set
REM the same location as Books files will be assumed.  This.
REM options is used to get better performance when the Library is
REM on a (slow) network drive.  Putting the metadata.db file 
REM locally then makes gives a big performance improvement.
REM
REM NOTE.  If you use this option, then the ability to switch
REM        libraries within Calibre will be disabled.  Therefore
REM        you do not want to set it if the metadata.db file
REM        is at the same location as the book files.
REM --------------------------------------------------------------

IF EXIST %cd%\CalibreMetadata\metadata.db (
	IF NOT "%CALIBRE_LIBRARY_DIRECTORY%" == "%cd%\CalibreMetadata" (
		SET CALIBRE_OVERRIDE_DATABASE_PATH=%cd%\CalibreMetadata\metadata.db
		ECHO DATABASE:        %cd%\CalibreMetadata\metadata.db
		ECHO '
		ECHO ***CAUTION*** Library Switching will be disabled 
		ECHO '
	)
)

REM --------------------------------------------------------------
REM Specify Location of source (optional)
REM
REM It is easy to run Calibre from source
REM Just set the environment variable to where the source is located
REM When running from source the GUI will have a '*' after the version.
REM number that is displayed at the bottom of the Calibre main screen.
REM --------------------------------------------------------------

IF EXIST CalibreSource\src (
	SET CALIBRE_DEVELOP_FROM=%cd%\CalibreSource\src
	ECHO SOURCE FILES:    %cd%\CalibreSource\src
)


REM --------------------------------------------------------------
REM Specify Location of calibre binaries (optional)
REM
REM To avoid needing Calibre to be set in the search path, ensure
REM that Calibre Program Files is current directory when starting.
REM The following test falls back to using search path .
REM This folder can be populated by copying the Calibre2 folder from
REM an existing installation or by installing direct to here.
REM --------------------------------------------------------------

IF EXIST %cd%\Calibre2 (
	CD %cd%\Calibre2
	ECHO PROGRAM FILES:   %cd%
)


REM --------------------------------------------------------------
REM Location of Calibre Temporary files  (optional)
REM
REM Calibre creates a lot of temproary files while running
REM In theory these are removed when Calibre finishes, but
REM in practise files can be left behind (particularily if
REM any errors occur.  Using this option allows some
REM explicit clean-up of these files.
REM If not set Calibre uses the normal system TEMP location
REM --------------------------------------------------------------

SET CALIBRE_TEMP_DIR=%TEMP%\CALIBRE_TEMP
ECHO TEMPORARY FILES: %CALIBRE_TEMP_DIR%

IF NOT "%CALIBRE_TEMP_DIR%" == "" (
	IF EXIST "%CALIBRE_TEMP_DIR%" RMDIR /s /q "%CALIBRE_TEMP_DIR%"
	MKDIR "%CALIBRE_TEMP_DIR%"
	REM set the following for any components that do
	REM not obey the CALIBRE_TEMP_DIR setting
	SET TMP=%CALIBRE_TEMP_DIR%
	SET TEMP=%CALIBRE_TEMP_DIR%
)


REM ----------------------------------------------------------
REM  The following gives a chance to check the settings before
REM  starting Calibre.  It can be commented out if not wanted.
REM ----------------------------------------------------------

ECHO '
ECHO "Press CTRL-C if you do not want to continue"
PAUSE


REM --------------------------------------------------------
REM Start up the calibre program.
REM
REM The use of 'belownormal' priority helps keep the system
REM responsive while Calibre is running.  Within Calibre itself
REM the backgound processes should be set to run with 'low' priority.

REM Using the START command starts up Calibre in a separate process.
REM If used without /WAIT opotion launches Calibre and contines batch file.
REM Use with /WAIT to wait until Calibre completes to run a task on exit
REM --------------------------------------------------------

ECHO "Starting up Calibre"
ECHO OFF
ECHO %cd%
START /belownormal Calibre --with-library "%CALIBRE_LIBRARY_DIRECTORY%"