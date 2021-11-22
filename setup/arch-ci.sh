#!/bin/sh
#
# arch-ci.sh
# Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>

set -xe

pacman -S --noconfirm --needed base-devel sudo git sip pyqt-builder chmlib icu jxrlib hunspell libmtp libusb libwmf optipng podofo python-apsw python-beautifulsoup4 python-cssselect python-css-parser python-dateutil python-jeepney python-dnspython python-dukpy python-feedparser python-html2text python-html5-parser python-lxml python-markdown python-mechanize python-msgpack python-netifaces python-unrardll python-pillow python-psutil python-pygments python-pyqt6 python-regex python-zeroconf python-pyqt6-webengine qt6-svg qt6-imageformats udisks2 hyphen python-pychm python-pycryptodome speech-dispatcher python-sphinx python-urllib3 python-py7zr python-pip python-cchardet libstemmer 

# See https://github.com/Legrandin/pycryptodome/issues/376
# Can be removed when https://github.com/Legrandin/pycryptodome/issues/558 is released
file_to_patch=$(pacman -Ql python-pycryptodome | grep _raw_api.py$ | cut -d" " -f2)
echo "Patching $file_to_patch"
sed -i 's/RTLD_DEEPBIND/RTLD_DEEPBIND_DISABLED_BY_KOVID/g' "$file_to_patch"

useradd -m ci
chown -R ci:users $GITHUB_WORKSPACE
