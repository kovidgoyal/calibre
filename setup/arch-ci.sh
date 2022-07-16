#!/bin/sh
#
# arch-ci.sh
# Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>

set -xe

pacman -S --noconfirm --needed base-devel sudo git sip pyqt-builder cmake chmlib icu jxrlib hunspell libmtp libusb libwmf optipng podofo python-apsw python-beautifulsoup4 python-cssselect python-css-parser python-dateutil python-jeepney python-dnspython python-feedparser python-html2text python-html5-parser python-lxml python-markdown python-mechanize python-msgpack python-netifaces python-unrardll python-pillow python-psutil python-pygments python-pyqt6 python-regex python-zeroconf python-pyqt6-webengine qt6-svg qt6-imageformats udisks2 hyphen python-pychm python-pycryptodome speech-dispatcher python-sphinx python-urllib3 python-py7zr python-pip uchardet libstemmer poppler

useradd -m ci
chown -R ci:users $GITHUB_WORKSPACE
