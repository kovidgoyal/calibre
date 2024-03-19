## Steps to execute
Please note that these steps have been designed for, and verified on, a M2 mac running macOS.

### Step 1
Clone the forked Calibre repository and check out the `monitoring` branch
```
git clone https://github.com/annegu/calibre.git -- branch monitoring
```

### Step 2
Download Version 7.7.0 of Calibre ebook reader for macOS at https://calibre-ebook.com/download_osx

### Step 3
Create the following script at `/usr/local/bin/calibre-develop`
```
#!/bin/sh
export CALIBRE_DEVELOP_FROM="ABSOLUTE_PATH_OF_CLONED_REPO"
/Applications/calibre.app/Contents/MacOS/calibre-debug -g
```
Depending on your permissions, `sudo` may be needed in order to create the script.

For reference see https://manual.calibre-ebook.com/develop.html#macos-development-environment

### Step 4

Give `calibre-develop` execute permissions
```
chmod +x /usr/local/bin/calibre-develop
```

### Step 5
Run `./calibre-develop` from `/usr/local/bin/` to see the new logs on output!