#!/bin/sh

ssh divok bzr up /usr/local/calibre
ssh divok /etc/init.d/apache2 graceful
