#!/bin/sh
#			Calibre-Portable.sh
#			¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬
#
# Shell script File to start a Calibre configuration on Linux
# giving explicit control of the location of:
#  - Calibre Program Files
#  - Calibre Library Files
#  - Calibre Config Files
#  - Calibre Metadata database
#  - Calibre Source files
#  - Calibre Temp Files
# By setting the paths correctly it can be used to run:
#  - A "portable calibre" off a USB stick.
#  - A network installation with local metadata database
#    (for performance) and books stored on a network share 
#  - A local installation using customised settings
#
# If trying to run off a USB stick then the folder structure
# shown below is recommended (relative to the location of 
# this script file).  This can structure can also be used
# when running of a local hard disk if you want to get the
# level of control this script file provides.
#  - Calibre			Location of linux program files
#  - CalibreConfig		Location of Configuration files
#  - CalibreLibrary		Location of Books and metadata
#  - CalibreSource 		Location of Calibre Source files (Optional)
#
# This script file is designed so that if you create the recommended
# folder structure then it can be used 'as is' without modification.
#
# More information on the Environment Variables used by Calibre can
# be found at:
#	http://manual.calibre-ebook.com/customize.html#environment-variables
#
# The documentation for this file in the Calibre manual can be found at:
#	http://manual.calibre-ebook.com/portable.html
#
# NOTE: It is quite possible to have both Windows and Linux binaries on the same
#	USB stick but set up to use the same calibre settings otherwise.
#	In this case you use:
#	- calibre-portable.bat		to run the Windows version
#	= calibre-portable.sh		to run the Linux version
#
# CHANGE HISTORY
# ¬¬¬¬¬¬¬¬¬¬¬¬¬¬
# 22 Jan 2012	itimpi	- First version based on the calibre-portable.bat file for Windows
#			  It should have identical functionality but for a linux environment.
#			  It might work on MacOS but that has not been validated


# -------------------------------------
# Set up Calibre Config folder
#
# This is where user specific settings
# are stored.
# -------------------------------------

if [ -d CalibreConfig ]
then
	CALIBRE_CONFIG_DIRECTORY=`pwd`/CalibreConfig
	echo "CONFIG FILES:       "`pwd`"/CalibreConfig"
	export CALIBRE_CONFIG_DIRECTORY
fi


# --------------------------------------------------------------
# Specify Location of ebooks
#
# Location where Book files are located
# Either set explicit path, or if running from a USB stick
# a relative path can be used to avoid need to know the
# drive letter of the USB stick.
#
# Comment out any of the following that are not to be used
# (although leaving them in does not really matter)
# --------------------------------------------------------------

if [ -d /eBooks/CalibreLibrary ]
then
	SET CALIBRE_LIBRARY_DIRECTORY=/eBOOKS/CalibreLibrary
	echo "LIBRARY FILES:      /eBOOKS/CalibreLibrary"
	export LIBRARY_FILES
fi
if [ -d `pwd`/CalibreLibrary ]
then
	CALIBRE_LIBRARY_DIRECTORY=`pwd`/CalibreLibrary
	echo "LIBRARY FILES:      "`pwd`"/CalibreLibrary"
	export LIBRARY_FILES
fi


# --------------------------------------------------------------
# Specify Location of metadata database (optional)
#
# Location where the metadata.db file is located.  If not set
# then the  same location as Books files will be assumed.  This.
# options is typically used to get better performance when the
# Library is on a (slow) network drive.  Putting the metadata.db
# file locally then makes gives a big performance improvement.
#
# NOTE.  If you use this option, then the ability to switch
#        libraries within Calibre will be disabled.  Therefore
#        you do not want to set it if the metadata.db file
#        is at the same location as the book files.
#
#	 Another point to watch is that plugins can cause problems
#	 as they often store absolute path information
# --------------------------------------------------------------

if [ -d  `pwd`/CalibreMetadata/metadata.db ]
then
	if [ $CALIBRE_LIBRARY_DIRECTORY != `pwd`/CalibreMetadata ]
	then
		CALIBRE_OVERRIDE_DATABASE_PATH=`pwd`/CalibreMetadata/metadata.db
		echo DATABASE:        `pwd`"/CalibreMetadata/metadata.db"
		export CALIBRE_OVERRIDE_DATABASE
		echo 
		echo "***CAUTION*** Library Switching will be disabled" 
		echo 
	fi
fi

# --------------------------------------------------------------
# Specify Location of source (optional)
#
# It is easy to run Calibre from source
# Just set the environment variable to where the source is located
# When running from source the GUI will have a '*' after the version.
# number that is displayed at the bottom of the Calibre main screen.
#
# More information on setting up a development environment can
# be found at:
#	http://manual.calibre-ebook.com/develop.html#develop
# --------------------------------------------------------------

if [ -d  CalibreSource/src ]
then
	CALIBRE_DEVELOP_FROM=`pwd`/CalibreSource/src
	echo "SOURCE FILES:       "`pwd`"/CalibreSource/src"
	export CALIBRE_DEVELOP_FROM
else
	echo "SOURCE FILES:       *** Not being Used ***"
fi



# --------------------------------------------------------------
# Specify Location of calibre linux binaries (optional)
#
# To avoid needing Calibre to be set in the search path, ensure
# that Calibre Program Files is current directory when starting.
# The following test falls back to using search path.
#
# This folder can be populated by copying the /opt/calibre folder
# from an existing installation or by installing direct to here.
#
# NOTE.  Do not try and put both Windows and Linux binaries into
#	 same folder as this can cause problems.
# --------------------------------------------------------------

if [ -d  `pwd`/Calibre ]
then
	cd `pwd`/Calibre
	echo "PROGRAM FILES:      "`pwd`
else
	echo "PROGRAM FILES:      *** Using System search path ***"
fi


# --------------------------------------------------------------
# Location of Calibre Temporary files  (optional)
#
# Calibre creates a lot of temporary files while running
# In theory these are removed when Calibre finishes, but
# in practise files can be left behind (particularly if
# a crash occurs).  Using this option allows some
# explicit clean-up of these files.
# If not set Calibre uses the normal system TEMP location
# --------------------------------------------------------------

CALIBRE_TEMP_DIR=/tmp/CALIBRE_TEMP
echo "TEMPORARY FILES:    $CALIBRE_TEMP_DIR"

if [ -d  "$CALIBRE_TEMP_DIR" ]
then
	rm -fr "$CALIBRE_TEMP_DIR"
fi
mkdir "$CALIBRE_TEMP_DIR"
# set the following for any components that do
# not obey the CALIBRE_TEMP_DIR setting


# --------------------------------------------------------------
# Set the Interface language (optional)
#
# If not set Calibre uses the language set in Preferences
# --------------------------------------------------------------

CALIBRE_OVERRIDE_LANG=EN
echo "INTERFACE LANGUAGE: $CALIBRE_OVERRIDE_LANG"
export CALIBRE_OVERRIDE_LANG

# ----------------------------------------------------------
#  The following gives a chance to check the settings before
#  starting Calibre.  It can be commented out if not wanted.
# ----------------------------------------------------------

echo 
echo "Press CTRL-C if you do not want to continue"
echo "Press ENTER to continue and start Calibre"
read DUMMY

# --------------------------------------------------------
# Start up the calibre program.
# --------------------------------------------------------

echo "Starting up Calibre"
echo `pwd`
calibre --with-library "$CALIBRE_LIBRARY_DIRECTORY"
