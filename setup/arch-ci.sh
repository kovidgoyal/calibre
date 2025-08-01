#!/bin/sh
#
# arch-ci.sh
# Copyright (C) 2020 Kovid Goyal <kovid at kovidgoyal.net>

set -xe

pacman -S --noconfirm --needed base-devel sudo git sip pyqt-builder cmake chmlib icu jxrlib hunspell libmtp libusb libwmf optipng python-apsw python-beautifulsoup4 python-cssselect python-css-parser python-dateutil python-jeepney python-dnspython python-feedparser python-html2text python-html5-parser python-lxml python-lxml-html-clean python-markdown python-mechanize python-msgpack python-netifaces python-unrardll python-pillow python-psutil python-pygments python-pyqt6 python-regex python-zeroconf python-pyqt6-webengine qt6-svg qt6-imageformats qt6-speech udisks2 hyphen python-pychm python-pycryptodome speech-dispatcher python-sphinx python-urllib3 python-py7zr python-pip python-fonttools python-xxhash uchardet libstemmer poppler tk podofo python-jaconv python-pykakasi protobuf onnxruntime

git clone --depth=1 https://github.com/espeak-ng/espeak-ng.git
chown -R nobody:nobody espeak-ng
cd espeak-ng
cmake -B build -S . -DCMAKE_INSTALL_PREFIX=/usr -DBUILD_SHARED_LIBS=ON -DESPEAK_COMPAT=ON
cmake --build build
cmake --install build

useradd -m ci
chown -R ci:users $GITHUB_WORKSPACE
