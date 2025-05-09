#!/bin/sh

# To be used via a script such as
: <<'COMMENT'
export RSYNC_PASSWORD=password
export BUILDBOT=rsync://username@server/path/to/this/directory
mkdir -p ~/calibre-src
cd ~/calibre-src || exit 1

script=rsync-and-build.sh
if [[ -e "$script" ]]; then
    . "./$script"
else
    rsync -a --include "$script" --exclude '*' "$BUILDBOT" . && source "$script"
fi
COMMENT

rsync -a --delete --force --exclude bypy/b --exclude src/calibre/plugins --exclude manual --exclude ".*cache" --exclude .git --exclude build --exclude dist --exclude "*.pyj-cached" --exclude "*.pyc" --exclude "*.pyo" --exclude "*.swp" --exclude "*.swo" --exclude format_docs "$BUILDBOT" .
