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

    , { "Acer", 0x0502, "MT65xx Android Phone", 0x353c, DEVICE_FLAGS_ANDROID_BUGS }

    // Remove this once it is added to upstream libmtp
    , { "Amazon", 0x1949, "Kindle Scribe", 0x9981, DEVICE_FLAGS_ANDROID_BUGS }

    // Remove this once it is added to upstream libmtp (Nook Glowlight 2023)
    , { "BarnesAndNoble", 0x2080, "BNRV1300", 0xf, DEVICE_FLAGS_ANDROID_BUGS }

    , { NULL, 0xffff, NULL, 0xffff, DEVICE_FLAG_NONE }
};
