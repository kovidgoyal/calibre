#!/bin/sh

ssh divok "cd /usr/local/calibre && bzr up"
ssh divok /etc/init.d/apache2 graceful
