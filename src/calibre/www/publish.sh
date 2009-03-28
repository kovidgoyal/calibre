#!/bin/sh

ssh divok "cd /usr/local/calibre && bzr pull"
ssh divok /etc/init.d/apache2 graceful
