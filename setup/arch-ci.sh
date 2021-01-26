#!/bin/sh
#
# arch-ci.sh
# Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>

set -xe
useradd -m ci
pacman -S --noconfirm --needed base-devel sudo git sip pyqt-builder chmlib icu jxrlib hunspell libmtp libusb libwmf optipng podofo python-apsw python-beautifulsoup4 python-cssselect python-css-parser python-dateutil python-dbus python-dnspython python-dukpy python-feedparser python-html2text python-html5-parser python-lxml python-markdown python-mechanize python-msgpack python-netifaces python-unrardll python-pillow python-psutil python-pygments python-pyqt5 python-regex python-zeroconf python-pyqtwebengine qt5-x11extras qt5-svg qt5-imageformats udisks2 hyphen python-pychm python-pycryptodome speech-dispatcher python-sphinx python-urllib3 python-py7zr python-pip 
chown -R ci:users $GITHUB_WORKSPACE
