/*
 * devices.c
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the MIT license.
 */

#include "upstream/device-flags.h"
#include "devices.h"

const calibre_device_entry_t calibre_mtp_device_table[] = {
#include "upstream/music-players.h"

    // Amazon Kindle Fire HD
    , { "Amazon", 0x1949, "Fire HD", 0x0007, DEVICE_FLAGS_ANDROID_BUGS}

    , { NULL, 0xffff, NULL, 0xffff, DEVICE_FLAG_NONE }
};

