#!/bin/bash
#                       Calibre-Portable.sh
#                       ¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬
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
# this script file). This structure can also be used when
# running of a local hard disk if you want to get the level
# of control this script file provides.
#  - Calibre                    Location of linux program files
#  - CalibreConfig              Location of Configuration files
#  - CalibreLibrary             Location of Books and metadata
#  - CalibreSource              Location of Calibre Source files (Optional)
#
# This script file is designed so that if you create the recommended
# folder structure then it can be used 'as is' without modification.
# To use your own structure, simply set the variables at the head of each block.
#
# More information on the Environment Variables used by Calibre can
# be found at:
#       http://manual.calibre-ebook.com/customize.html#environment-variables
#
# NOTE: It is quite possible to have both Windows and Linux binaries on the same
#       USB stick but set up to use the same calibre settings otherwise.
#       In this case you use:
#       - calibre-portable.bat          to run the Windows version
#       - calibre-portable.sh           to run the Linux version
#
# CHANGE HISTORY
# ¬¬¬¬¬¬¬¬¬¬¬¬¬¬
# 22 Jan 2012  itimpi ----- First version based on the calibre-portable.bat file for Windows
#                           It should have identical functionality but for a linux environment.
#                           It might work on MacOS but that has not been validated.
#
# 02 Feb 2015  eschwartz -- Fix path issues, allow setting each location in one variable, allow
#                           specifying a list of libraries in descending order of priority.


# ------------------------------------------------
# Set up Calibre Config folder
#
# This is where user specific settings are stored.
# ------------------------------------------------

CONFIG_DIR="$(pwd)/CalibreConfig"

if [[ -d "${CONFIG_DIR}" ]]; then
    export CALIBRE_CONFIG_DIRECTORY="${CONFIG_DIR}"
    echo "CONFIG FILES:       ${CONFIG_DIR}"
else
    echo -e "\033[0;31mCONFIG FILES:       Not found\033[0m"
fi
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Specify Location of ebooks
#
# Location where Book files are located.
# Either set explicit path, or if running from a USB stick
# a relative path can be used to avoid need to know the
# drive letter of the USB stick.
#
# Specify a list of libraries here, by adding new elements to the
# array. The first value of LIBRARY_DIRS that is an existing directory
# will be used as the current calibre library.
# --------------------------------------------------------------

LIBRARY_DIRS[0]="/path/to/first/CalibreLibrary"
LIBRARY_DIRS[1]="/path/to/second/CalibreLibrary"
LIBRARY_DIRS[2]="$(pwd)/CalibreLibrary"

for LIBRARY_DIR in "${LIBRARY_DIRS[@]}"; do
    if [[ -d "${LIBRARY_DIR}" ]]; then
        export CALIBRE_LIBRARY_DIRECTORY="${LIBRARY_DIR}"
        echo "LIBRARY FILES:      ${CALIBRE_LIBRARY_DIRECTORY}"
        break
    fi
done

[[ -z "${CALIBRE_LIBRARY_DIRECTORY}" ]] && echo -e "\033[0;31mLIBRARY FILES:      Not found\033[0m"
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Specify Location of metadata database (optional)
#
# Location where the metadata.db file is located. If not set
# then the same location as Book files will be assumed. This
# option is typically used to get better performance when the
# Library is on a (slow) network drive. Putting the metadata.db
# file locally then makes gives a big performance improvement.
#
# NOTE. If you use this option, then the ability to switch
#       libraries within Calibre will be disabled. Therefore
#       you do not want to set it if the metadata.db file
#       is at the same location as the book files.
#
#       Another point to watch is that plugins can cause problems
#       as they often store absolute path information.
# --------------------------------------------------------------

METADATA_DIR="$(pwd)/CalibreMetadata"

if [[ -f "${METADATA_DIR}/metadata.db" && "$CALIBRE_LIBRARY_DIRECTORY" != "${METADATA_DIR}" ]]; then
    export CALIBRE_OVERRIDE_DATABASE_PATH="${METADATA_DIR}/metadata.db"
    echo "DATABASE:        ${METADATA_DIR}/metadata.db"
    echo
    echo -e "\033[0;31m***CAUTION*** Library Switching will be disabled\033[0m"
    echo
    echo "--------------------------------------------------"
fi

# --------------------------------------------------------------
# Specify Location of source (optional)
#
# It is easy to run Calibre from source.
# Just set the environment variable to where the source is located.
# When running from source the GUI will have a '*' after the version
# number that is displayed at the bottom of the Calibre main screen.
#
# More information on setting up a development environment can
# be found at:
#       http://manual.calibre-ebook.com/develop.html#develop
# --------------------------------------------------------------

SRC_DIR="$(pwd)/CalibreSource/src"

if [[ -d "${SRC_DIR}" ]]; then
    export CALIBRE_DEVELOP_FROM="${SRC_DIR}"
    echo "SOURCE FILES:       ${SRC_DIR}"
else
    echo "SOURCE FILES:       *** Not being Used ***"
fi
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Specify Location of calibre linux binaries (optional)
#
# To avoid needing Calibre to be set in the search path, ensure
# that if Calibre Program Files exists, we manually specify the
# location of the binary.
# The following test falls back to using the search path, or you
# can specifically use the search path by leaving the BIN_DIR blank.
#
# This folder can be populated by copying the /opt/calibre folder
# from an existing installation or by installing direct to here.
#
# NOTE. Do not try and put both Windows and Linux binaries into
#       the same folder as this can cause problems.
# --------------------------------------------------------------

BIN_DIR="$(pwd)/calibre"

if [[ -d "${BIN_DIR}" ]]; then
    CALIBRE="${BIN_DIR}/calibre"
    echo "PROGRAM FILES:      ${BIN_DIR}"
elif [[ -z "${BIN_DIR}" ]]; then
    CALIBRE="calibre"
    echo "PROGRAM FILES:      Using System search path"
else
    CALIBRE="calibre"
    echo "PROGRAM FILES:      No portable copy found."
    echo "To intall a portable copy, run the following command:"
    echo "wget -nv -O- https://raw.githubusercontent.com/kovidgoyal/calibre/master/setup/linux-installer.py" \
         "| python -c \"import sys; main=lambda x,y:sys.stderr.write('Download failed\n'); exec(sys.stdin.read()); main('$(pwd)/calibre', True)\""
    echo -e "\033[0;31m*** Using System search path instead***\033[0m"
fi
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Location of Calibre Temporary files  (optional)
#
# Calibre creates a lot of temporary files while running
# In theory these are removed when Calibre finishes, but
# in practise files can be left behind (particularly if
# a crash occurs). Using this option allows some
# explicit clean-up of these files.
# If not set Calibre uses the normal system TEMP location
# --------------------------------------------------------------

CALIBRE_TEMP_DIR="/tmp/CALIBRE_TEMP"

echo "TEMPORARY FILES:    ${CALIBRE_TEMP_DIR}"
echo "--------------------------------------------------"
rm -rf "${CALIBRE_TEMP_DIR}"
mkdir "${CALIBRE_TEMP_DIR}"

# set the following for any components that do
# not obey the CALIBRE_TEMP_DIR setting


# --------------------------------------------------------------
# Set the Interface language (optional)
#
# Remove the if test to use this. ;)
# --------------------------------------------------------------

if false; then
    export CALIBRE_OVERRIDE_LANG="EN"
    echo "INTERFACE LANGUAGE: ${CALIBRE_OVERRIDE_LANG}"
fi

# ----------------------------------------------------------
#  The following gives a chance to check the settings before
#  starting Calibre. It can be commented out if not wanted.
# ----------------------------------------------------------

echo 
echo "Press CTRL-C if you do not want to continue"
echo "Press ENTER to continue and start Calibre"
read DUMMY

# --------------------------------------------------------
# Start up the calibre program.
# --------------------------------------------------------

echo "Starting up Calibre from portable directory \"$(pwd)\""
$CALIBRE --with-library "$CALIBRE_LIBRARY_DIRECTORY"
