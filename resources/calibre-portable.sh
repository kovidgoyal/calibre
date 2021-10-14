#!/bin/bash
#                       Calibre-Portable.sh
#                       ¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬¬
#
# Shell script file to start a calibre configuration on Linux
# giving explicit control of the location of:
#  - calibre program files
#  - calibre library files
#  - calibre config files
#  - calibre metadata database
#  - calibre source files
#  - calibre temp files
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
#  - Calibre                    Location of Linux program files
#  - CalibreConfig              Location of configuration files
#  - CalibreLibrary             Location of books and metadata
#  - CalibreSource              Location of calibre source files (optional)
#
# This script file is designed so that if you create the recommended
# folder structure then it can be used 'as is' without modification.
# To use your own structure, simply set the variables in the generated configuration file.
#
# More information on the environment variables used by calibre can
# be found at:
#       https://manual.calibre-ebook.com/customize.html#environment-variables
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
#                           It should have identical functionality but for a Linux environment.
#                           It might work on MacOS but that has not been validated.
#
# 02 Feb 2015  eschwartz -- Fix path issues, allow setting each location in one variable, allow
#                           specifying a list of libraries in descending order of priority.
#
# 01 Apr 2015  eschwartz -- Fix temp dir and permissions, migrate settings to configuration file.

# -----------------------------------------------------
# On exit, make sure all files are marked world-writable.
# This allows you to use calibre on other computers
# without changing fstab rules and suchlike.
# You can now use an ext3 drive instead of vfat so the
# binaries and script will be executable.
# -----------------------------------------------------

cleanup() {
    # Check if user has disabled cleanup
    if [[ "${CALIBRE_NO_CLEANUP}" = "1" ]]; then
        return
    fi

    for i in "${CONFIG_DIR}" "${CALIBRE_LIBRARY_DIRECTORY}" \
             "${METADATA_DIR}" "${SRC_DIR}" "${BIN_DIR}"; do
        if [[ -d "${i}" ]]; then
            chmod a+rwX "${i}"
        fi
    done
    rm -rf "${CALIBRE_TEMP_DIR}"
}

trap cleanup EXIT

# ------------------------------------------------
# Interactive options.
# ------------------------------------------------

usage()
{
	cat <<- _EOF_
		Usage: calibre-portable.sh [OPTIONS]
		Run a portable instance of calibre.

		OPTIONS
		  -u, --upgrade-install     upgrade or install the portable calibre binaries
		  -h, --help                show this usage message then exit
_EOF_
}

do_upgrade()
{
    wget -nv -O- https://raw.githubusercontent.com/kovidgoyal/calibre/master/setup/linux-installer.py \
        | python -c "import sys; main=lambda x,y:sys.stderr.write('Download failed\n'); \
        exec(sys.stdin.read()); main('$(pwd)', True)"
}

while [[ "${#}" -gt 0 ]]; do
    case "${1}" in
        -h|--help)
            usage
            exit
            ;;
        -u|--upgrade-install)
            do_upgrade
            exit
            ;;
        *)
            echo "calibre-portable.sh: unecognzed option '${1}'"
            echo "Try 'calibre-portable.sh --help' for more information."
            exit 1
    esac
    shift
done

# ------------------------------------------------
# Create or read configuration file.
# ------------------------------------------------

if [[ -f "$(pwd)/calibre-portable.conf" ]]; then
    source "$(pwd)/calibre-portable.conf"
else
	cat <<- _EOF_ > $(pwd)/calibre-portable.conf
		# Configuration file for calibre-portable. Generated on $(date)
		# Settings in here will override the defaults specified in the portable launcher.

		##################################################
		# Set up calibre config folder.
		#
		# This is where user specific settings are stored.
		##################################################

		# CONFIG_DIR="\$(pwd)/CalibreConfig"

		################################################################
		# -- Specify the location of your calibre library.
		#
		# -- Either set an explicit path, or if running from a USB stick
		# -- a relative path can be used to avoid needing to know the
		# -- mount point of the USB stick.
		#
		# -- Specify a list of libraries here, by adding new elements to the
		# -- array. The first value of LIBRARY_DIRS that is an existing directory
		# -- will be used as the current calibre library.
		################################################################

		# LIBRARY_DIRS[0]="/path/to/first/CalibreLibrary"
		# LIBRARY_DIRS[1]="/path/to/second/CalibreLibrary"
		# LIBRARY_DIRS[2]="\$(pwd)/CalibreLibrary"

		################################################################
		# -- Specify location of metadata database (optional).
		#
		# -- Location where the metadata.db file is located. If not set
		# -- then the same location as the library folder will be assumed.
		# -- This option is typically used to get better performance when the
		# -- library is on a (slow) network drive. Putting the metadata.db
		# -- file locally then makes gives a big performance improvement.
		#
		# -- NOTE. If you use this option, then the ability to switch
		# --       libraries within calibre will be disabled. Therefore
		# --       you do not want to set it if the metadata.db file
		# --       is at the same location as the book files.
		#
		# --       Another point to watch is that plugins can cause problems
		# --       as they often store absolute path information.
		################################################################

		# METADATA_DIR="\$(pwd)/CalibreMetadata"

		################################################################
		# -- Specify location of source (optional).
		#
		# -- It is easy to run calibre from source. Just set the environment
		# -- variable to where the source is located. When running from source
		# -- the GUI will have a '*' after the version number that is displayed
		# -- at the bottom of the calibre main screen.
		#
		# -- More information on setting up a development environment can
		# -- be found at:
		# --       https://manual.calibre-ebook.com/develop.html#develop
		################################################################

		# SRC_DIR="$\(pwd)/CalibreSource/src"

		################################################################
		# -- Specify location of calibre Linux binaries (optional).
		#
		# -- To avoid needing calibre to be set in the search path, ensure
		# -- that if calibre program files exists, we manually specify the
		# -- location of the binary.
		# -- The following test falls back to using the search path, or you
		# -- can specifically use the search path by leaving the BIN_DIR blank.
		#
		# -- This folder can be populated by copying the /opt/calibre folder
		# -- from an existing installation or by installing direct to here.
		#
		# -- NOTE. Do not try and put both Windows and Linux binaries into
		# --       the same folder as this can cause problems.
		################################################################

		# BIN_DIR="$\(pwd)/calibre"

		################################################################
		# -- Location of calibre temporary files (optional).
		#
		# -- calibre creates a lot of temporary files while running
		# -- In theory these are removed when calibre finishes, but
		# -- in practice files can be left behind (particularly if
		# -- a crash occurs). Using this option allows some
		# -- explicit clean-up of these files.
		# -- If not set calibre uses the normal system TEMP location
		################################################################

		# CALIBRE_TEMP_DIR="/tmp/CALIBRE_TEMP_\$(tr -dc 'A-Za-z0-9'</dev/urandom |fold -w 7 | head -n1)"

		################################################################
		# -- Set the interface language (optional).
		#
		# -- Defaults to whatever is stored in Preferences
		################################################################

		# CALIBRE_OVERRIDE_LANG="EN"

		##################################################################
		# -- Wait until user can check the settings before starting calibre.
		# -- (default=yes)
		#
		# -- Set CALIBRE_NOCONFIRM_START to "1" to disable.
		# -- Set CALIBRE_NOCONFIRM_START to "0" to enable.
		##################################################################

		# CALIBRE_NOCONFIRM_START=0

		##################################################################
		# -- Cleanup all files when done (default=yes).
		#
		# -- On launcher termination, change all library, configuration,
		# -- source, binary, etc. files to world-writable, and remove the
		# -- temporary folder.
		#
		# -- Technically this is a security risk. This is a portableapp, so
		# -- we don't care. Disable this if *you* do.
		#
		# -- Set CALIBRE_NO_CLEANUP to "1" to disable.
		# -- Set CALIBRE_NO_CLEANUP to "0" to enable.
		##################################################################

		# CALIBRE_NO_CLEANUP=0

		##################################################################
		# -- Set and export any other environment variables needed. More
		# -- information can be found at:
		#        https://manual.calibre-ebook.com/customize.html#environment-variables
		##################################################################

		# some other example variables calibre recognizes:
		# export CALIBRE_NO_NATIVE_FILEDIALOGS=
		# export CALIBRE_NO_NATIVE_MENUBAR=
		# export CALIBRE_IGNORE_SYSTEM_THEME=
		# export http_proxy=
	_EOF_

    echo "Generating default configuration file at $(pwd)/calibre-portable.conf"
    echo "Set any non-default options here."
fi

# ------------------------------------------------
# Set up calibre config folder.
# ------------------------------------------------

: ${CONFIG_DIR:="$(pwd)/CalibreConfig"}

if [[ -d "${CONFIG_DIR}" ]]; then
    export CALIBRE_CONFIG_DIRECTORY="${CONFIG_DIR}"
    echo "CONFIG FILES:       ${CONFIG_DIR}"
else
    echo -e "\033[0;31mCONFIG FILES:       Not found\033[0m"
fi
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Specify the location of your calibre library.
# --------------------------------------------------------------

: ${LIBRARY_DIRS[0]:="/path/to/first/CalibreLibrary"}
: ${LIBRARY_DIRS[1]:="/path/to/second/CalibreLibrary"}
: ${LIBRARY_DIRS[2]:="$(pwd)/CalibreLibrary"}

for LIBRARY_DIR in "${LIBRARY_DIRS[@]}"; do
    if [[ -d "${LIBRARY_DIR}" ]]; then
        CALIBRE_LIBRARY_DIRECTORY="${LIBRARY_DIR}"
        echo "LIBRARY FILES:      ${CALIBRE_LIBRARY_DIRECTORY}"
        break
    fi
done

[[ -z "${CALIBRE_LIBRARY_DIRECTORY}" ]] && echo -e "\033[0;31mLIBRARY FILES:      Not found\033[0m"
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Specify location of metadata database (optional).
# --------------------------------------------------------------

: ${METADATA_DIR:="$(pwd)/CalibreMetadata"}

if [[ -f "${METADATA_DIR}/metadata.db" && "${CALIBRE_LIBRARY_DIRECTORY}" != "${METADATA_DIR}" ]]; then
    export CALIBRE_OVERRIDE_DATABASE_PATH="${METADATA_DIR}/metadata.db"
    echo "DATABASE:        ${METADATA_DIR}/metadata.db"
    echo
    echo -e "\033[0;31m***CAUTION*** Library Switching will be disabled\033[0m"
    echo
    echo "--------------------------------------------------"
fi

# --------------------------------------------------------------
# Specify location of source (optional).
# --------------------------------------------------------------

: ${SRC_DIR:="$(pwd)/CalibreSource/src"}

if [[ -d "${SRC_DIR}" ]]; then
    export CALIBRE_DEVELOP_FROM="${SRC_DIR}"
    echo "SOURCE FILES:       ${SRC_DIR}"
else
    echo "SOURCE FILES:       *** Not being Used ***"
fi
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Specify location of calibre Linux binaries (optional).
# --------------------------------------------------------------

: ${BIN_DIR:="$(pwd)/calibre"}

if [[ -d "${BIN_DIR}" ]]; then
    CALIBRE="${BIN_DIR}/calibre"
    echo "PROGRAM FILES:      ${BIN_DIR}"
elif [[ -z "${BIN_DIR}" ]]; then
    CALIBRE="calibre"
    echo "PROGRAM FILES:      Using system search path"
else
    CALIBRE="calibre"
    echo "PROGRAM FILES:      No portable copy found."
    echo "To install a portable copy, run './calibre-portable.sh --upgrade-install'"
    echo -e "\033[0;31m*** Using system search path instead***\033[0m"
fi
echo "--------------------------------------------------"

# --------------------------------------------------------------
# Location of calibre temporary files (optional).
# --------------------------------------------------------------

: ${CALIBRE_TEMP_DIR:="/tmp/CALIBRE_TEMP_$(tr -dc 'A-Za-z0-9'</dev/urandom |fold -w 7 | head -n1)"}

if [[ ! -z "${CALIBRE_TEMP_DIR}" ]]; then
    export CALIBRE_TEMP_DIR
    export CALIBRE_CACHE_DIRECTORY="${CALIBRE_TEMP_DIR}/calibre_cache"
    echo "TEMPORARY FILES:    ${CALIBRE_TEMP_DIR}"
    echo "--------------------------------------------------"
    rm -rf "${CALIBRE_TEMP_DIR}"
    mkdir "${CALIBRE_TEMP_DIR}"
    mkdir "${CALIBRE_CACHE_DIRECTORY}"
fi

# --------------------------------------------------------------
# Set the interface language (optional).
# --------------------------------------------------------------

if [[ "${CALIBRE_OVERRIDE_LANG}" != "" ]]; then
    export CALIBRE_OVERRIDE_LANG
    echo "INTERFACE LANGUAGE: ${CALIBRE_OVERRIDE_LANG}"
fi

# ---------------------------------------------------------------
#  Wait until user can check the settings before starting calibre.
# ---------------------------------------------------------------

if [[ "${CALIBRE_NOCONFIRM_START}" != "1" ]]; then
    echo
    echo "Press CTRL-C if you do not want to continue"
    echo "Press ENTER to continue and start calibre"
    read DUMMY
fi

# --------------------------------------------------------
# Start up the calibre program.
# --------------------------------------------------------

echo "Starting up calibre from portable directory \"$(pwd)\""
$CALIBRE --with-library "${CALIBRE_LIBRARY_DIRECTORY}"
