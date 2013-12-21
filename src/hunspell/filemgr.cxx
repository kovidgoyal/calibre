#include "license.hunspell"
#include "license.myspell"

#include <stdlib.h>
#include <string.h>

#include "filemgr.hxx"

FileMgr::FileMgr(const char *data, const size_t dlen) {
    linenum = 0;
    last = 0;
    buf = new char[dlen+1];
    memcpy(buf, data, dlen);
    buf[dlen] = 0;
    pos = buf;
    buflen = dlen;
}

FileMgr::~FileMgr()
{
    if (buf != NULL) { delete[] buf; buf = NULL; }
    pos = NULL;
}

char * FileMgr::getline() {
    if (buf == NULL) return NULL;
    if (((size_t)(pos - buf)) >= buflen) {
        // free up the memory as it will not be needed anymore
        delete[] buf; buf = NULL; pos = NULL; return NULL;
    }
    if (pos != buf) *pos = last; // Restore the character that was previously replaced by null
    char *ans = pos;
    // Move pos to the start of the next line
    pos = (char *)memchr(pos, 10, buflen - (pos - buf));
    if (pos == NULL) pos = buf + buflen + 1;
    else pos++;
    // Ensure the current line is null terminated
    last = *pos;
    *pos = 0;
    linenum++;
    return ans;
}

int FileMgr::getlinenum() {
    return linenum;
}
