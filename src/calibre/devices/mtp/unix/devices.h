#pragma once
/*
 * devices.h
 * Copyright (C) 2012 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the MIT license.
 */
#include <stdint.h>
#include <stddef.h>

struct calibre_device_entry_struct {
  char *vendor; /**< The vendor of this device */
  uint16_t vendor_id; /**< Vendor ID for this device */
  char *product; /**< The product name of this device */
  uint16_t product_id; /**< Product ID for this device */
  uint32_t device_flags; /**< Bugs, device specifics etc */
};

typedef struct calibre_device_entry_struct calibre_device_entry_t;

extern const calibre_device_entry_t calibre_mtp_device_table[];

