@echo OFF
REM			CalibreRun.bat
REM			~~~~~~~~~~~~~~
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

If EXIST CalibreConfig SET CALIBRE_CONFIG_DIRECTORY=%cd%\CalibreConfig


REM --------------------------------------------------------------
REM Specify Location of ebooks
REM
REM Location where Book files are located
REM Either set explicit path, or if running from a USB stick
REM a relative path can be used to avoid need to know the
REM drive letter of the USB stick.

REM Comment out any of the following that are not to be used
REM --------------------------------------------------------------

SET CALIBRE_LIBRARY_DIRECTORY=U:\eBOOKS\CalibreLibrary
IF EXIST CalibreLibrary SET CALIBRE_LIBRARY_DIRECTORY=%cd%\CalibreLibrary
IF EXIST CalibreBooks SET CALIBRE_LIBRARY_DIRECTORY=%cd%\CalibreBooks


REM --------------------------------------------------------------
REM Specify Location of metadata database  (optional)
REM
REM Location where the metadata.db file is located.  If not set
REM the same location as Books files will be assumed.  This.
REM options is used to get better performance when the Library is
REM on a (slow) network drive.  Putting the metadata.db file 
REM locally gives a big performance improvement.
REM --------------------------------------------------------------

IF EXIST CalibreBooks SET SET CALIBRE_OVERRIDE_DATABASE_PATH=%cd%\CalibreBooks\metadata.db
IF EXIST CalibreMetadata SET CALIBRE_OVERRIDE_DATABASE_PATH=%cd%\CalibreMetadata\metadata.db


REM --------------------------------------------------------------
REM Specify Location of source (optional)
REM
REM It is easy to run Calibre from source
REM Just set the environment variable to where the source is located
REM When running from source the GUI will have a '*' after the version.
REM --------------------------------------------------------------

IF EXIST Calibre\src SET CALIBRE_DEVELOP_FROM=%cd%\Calibre\src


REM --------------------------------------------------------------
REM Specify Location of calibre binaries (optinal)
REM
REM To avoid needing Calibre to be set in the search path, ensure
REM that Calibre Program Files is current directory when starting.
REM The following test falls back to using search path .
REM This folder can be populated by cpying the Calibre2 folder from
REM an existing isntallation or by isntalling direct to here.
REM --------------------------------------------------------------

IF EXIST Calibre2 CD Calibre2


REM --------------------------------------------
REM Display settings that will be used
REM --------------------------------------------

echo PROGRAMS=%cd%
echo SOURCE=%CALIBRE_DEVELOP_FROM%
echo CONFIG=%CALIBRE_CONFIG_DIRECTORY%
echo LIBRARY=%CALIBRE_LIBRARY_DIRECTORY%
echo DATABASE=%CALIBRE_OVERRIDE_DATABASE_PATH%

REM  The following gives a chance to check the settings before
REM  starting Calibre.  It can be commented out if not wanted.

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
START /belownormal Calibre --with-library %CALIBRE_LIBRARY_DIRECTORY%
