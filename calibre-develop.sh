#!/bin/sh

# Set CALIBRE_DEVELOP_FROM to point to the src directory
export CALIBRE_DEVELOP_FROM="/Users/andychuong/Documents/GauntletAI/Week 7/calibre/src"

# Check if calibre-debug exists in the standard location
if [ -f "/Applications/calibre.app/Contents/MacOS/calibre-debug" ]; then
    /Applications/calibre.app/Contents/MacOS/calibre-debug -g
elif command -v calibre-debug >/dev/null 2>&1; then
    calibre-debug -g
else
    echo "Error: calibre-debug not found."
    echo "Please install calibre from https://calibre-ebook.com/download"
    echo "Or add /Applications/calibre.app/Contents/MacOS to your PATH"
    exit 1
fi


