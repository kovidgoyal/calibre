@echo OFF
REM Batch File to start a Calibre configuration on Windows
REM giving explicit control of the location of:
REM  - Calibe Program Files
REM  - Calibre Library Files
REM  - Calibre Config Files
REM  - Calibre Metadata database
REM  - Calibre Source files
REM By setting the paths correctly it can be used to run:
REM  - A "portable calibre" off a USB stick.
REM  - A network installation with local metadata database
REM    (for performance) and books stored on a network share 
REM
REM If trying to run off a USB stick then the following 
REM folder structure is recommended:
REM  - Calibre2			Location of program files
REM  - CalibreConfig		Location of Configuration files
REM  - CalibreLibrary		Location of Books and metadata


REM -------------------------------------
REM Set up Calibre Config folder
REM -------------------------------------

IF EXIST CalibreConfig (
	SET CALIBRE_CONFIG_DIRECTORY=%cd%\CalibreConfig
	ECHO CONFIG=%cd%\CalibreConfig
)


REM --------------------------------------------------------------
REM Specify Location of ebooks
REM
REM Location where Book files are located
REM Either set explicit path, or if running from a USB stick
REM a relative path can be used to avoid need to know the
REM drive letter of the USB stick.

REM Comment out any of the following that are not to be used
REM --------------------------------------------------------------

IF EXIST U:\eBooks\CalibreLibrary (
	SET CALIBRE_LIBRARY_DIRECTORY=U:\eBOOKS\CalibreLibrary
	ECHO LIBRARY=U:\eBOOKS\CalibreLibrary
)
IF EXIST CalibreLibrary (
	SET CALIBRE_LIBRARY_DIRECTORY=%cd%\CalibreLibrary
	ECHO LIBRARY=%cd%\CalibreLibrary
)
IF EXIST CalibreBooks (
	SET CALIBRE_LIBRARY_DIRECTORY=%cd%\CalibreBooks
	ECHO LIBRARY=%cd%\CalibreBooks
)


REM --------------------------------------------------------------
REM Specify Location of metadata database (optional)
REM
REM Location where the metadata.db file is located.  If not set
REM the same location as Books files will be assumed.  This.
REM options is used to get better performance when the Library is
REM on a (slow) network drive.  Putting the metadata.db file 
REM locally makes gives a big performance improvement.
REM
REM NOTE.  If you use this option, then the ability to switch
REM        libraries within Calibre will be disabled.  Therefore
REM        you do not want to set it if the metadata.db file
REM        is at the same location as the book files.
REM --------------------------------------------------------------

IF EXIST CalibreBooks (
	IF NOT "%CALIBRE_LIBRARY_DIRECTORY%" == "%cd%\CalibreBooks" (
		SET SET CALIBRE_OVERRIDE_DATABASE_PATH=%cd%\CalibreBooks\metadata.db
		ECHO DATABASE=%cd%\CalibreBooks\metadata.db
		ECHO '
		ECHO ***CAUTION*** Library Switching will be disabled 
		ECHO '
	)
)
IF EXIST CalibreMetadata (
	IF NOT "%CALIBRE_LIBRARY_DIRECTORY%" == "%cd%\CalibreMetadata" (
		SET CALIBRE_OVERRIDE_DATABASE_PATH=%cd%\CalibreMetadata\metadata.db
		ECHO DATABASE=%cd%\CalibreMetadata\metadata.db
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

IF EXIST Calibre\src (
	SET CALIBRE_DEVELOP_FROM=%cd%\Calibre\src
	ECHO SOURCE=%cd%\Calibre\src
)
IF EXIST D:\Calibre\Calibre\src (
	SET CALIBRE_DEVELOP_FROM=D:\Calibre\Calibre\src
	ECHO SOURCE=D:\Calibre\Calibre\src
)

REM --------------------------------------------------------------
REM Specify Location of calibre binaries (optional)
REM
REM To avoid needing Calibre to be set in the search path, ensure
REM that Calibre Program Files is current directory when starting.
REM The following test falls back to using search path .
REM This folder can be populated by cpying the Calibre2 folder from
REM an existing isntallation or by isntalling direct to here.
REM --------------------------------------------------------------

IF EXIST Calibre2 (
	Calibre2 CD Calibre2
	ECHO PROGRAMS=%cd%
)

REM ----------------------------------------------------------
REM  The following gives a chance to check the settings before
REM  starting Calibre.  It can be commented out if not wanted.
REM ----------------------------------------------------------

echo "Press CTRL-C if you do not want to continue"
pause


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

echo "Starting up Calibre"
START /belownormal Calibre --with-library "%CALIBRE_LIBRARY_DIRECTORY%"
