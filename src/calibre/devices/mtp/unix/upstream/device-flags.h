/**
 * \file device-flags.h
 * Special device flags to deal with bugs in specific devices.
 *
 * Copyright (C) 2005-2007 Richard A. Low <richard@wentnet.com>
 * Copyright (C) 2005-2012 Linus Walleij <triad@df.lth.se>
 * Copyright (C) 2006-2007 Marcus Meissner
 * Copyright (C) 2007 Ted Bullock
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
 * Boston, MA  02110-1301  USA
 *
 * This file is supposed to be included by both libmtp and libgphoto2.
 */

/**
 * These flags are used to indicate if some or other
 * device need special treatment. These should be possible
 * to concatenate using logical OR so please use one bit per
 * feature and lets pray we don't need more than 32 bits...
 */
#define DEVICE_FLAG_NONE 0x00000000
/**
 * This means that the PTP_OC_MTP_GetObjPropList is broken
 * in the sense that it won't return properly formatted metadata
 * for ALL files on the device when you request an object
 * property list for object 0xFFFFFFFF with parameter 3 likewise
 * set to 0xFFFFFFFF. Compare to
 * DEVICE_FLAG_BROKEN_MTPGETOBJECTPROPLIST which only signify
 * that it's broken when getting metadata for a SINGLE object.
 * A typical way the implementation may be broken is that it
 * may not return a proper count of the objects, and sometimes
 * (like on the ZENs) objects are simply missing from the list
 * if you use this. Sometimes it has been used incorrectly to
 * mask bugs in the code (like handling transactions of data
 * with size given to -1 (0xFFFFFFFFU), in that case please
 * help us remove it now the code is fixed. Sometimes this is
 * used because getting all the objects is just too slow and
 * the USB transaction will time out if you use this command.
 */
#define DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL 0x00000001
/**
 * This means that under Linux, another kernel module may
 * be using this device's USB interface, so we need to detach
 * it if it is. Typically this is on dual-mode devices that
 * will present both an MTP compliant interface and device
 * descriptor *and* a USB mass storage interface. If the USB
 * mass storage interface is in use, other apps (like our
 * userspace libmtp through libusb access path) cannot get in
 * and get cosy with it. So we can remove the offending
 * application. Typically this means you have to run the program
 * as root as well.
 */
#define DEVICE_FLAG_UNLOAD_DRIVER 0x00000002
/**
 * This means that the PTP_OC_MTP_GetObjPropList (9805)
 * is broken in some way, either it doesn't work at all
 * (as for Android devices) or it won't properly return all
 * object properties if parameter 3 is set to 0xFFFFFFFFU.
 */
#define DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST 0x00000004
/**
 * This means the device doesn't send zero packets to indicate
 * end of transfer when the transfer boundary occurs at a
 * multiple of 64 bytes (the USB 1.1 endpoint size). Instead,
 * exactly one extra byte is sent at the end of the transfer
 * if the size is an integer multiple of USB 1.1 endpoint size
 * (64 bytes).
 *
 * This behaviour is most probably a workaround due to the fact
 * that the hardware USB slave controller in the device cannot
 * handle zero writes at all, and the usage of the USB 1.1
 * endpoint size is due to the fact that the device will "gear
 * down" on a USB 1.1 hub, and since 64 bytes is a multiple of
 * 512 bytes, it will work with USB 1.1 and USB 2.0 alike.
 */
#define DEVICE_FLAG_NO_ZERO_READS 0x00000008
/**
 * This flag means that the device is prone to forgetting the
 * OGG container file type, so that libmtp must look at the
 * filename extensions in order to determine that a file is
 * actually OGG. This is a clear and present firmware bug, and
 * while firmware bugs should be fixed in firmware, we like
 * OGG so much that we back it by introducing this flag.
 * The error has only been seen on iriver devices. Turning this
 * flag on won't hurt anything, just that the check against
 * filename extension will be done for files of "unknown" type.
 * If the player does not even know (reports) that it supports
 * ogg even though it does, please use the stronger
 * OGG_IS_UNKNOWN flag, which will forcedly support ogg on
 * anything with the .ogg filename extension.
 */
#define DEVICE_FLAG_IRIVER_OGG_ALZHEIMER 0x00000010
/**
 * This flag indicates a limitation in the filenames a device
 * can accept - they must be 7 bit (all chars <= 127/0x7F).
 * It was found first on the Philips Shoqbox, and is a deviation
 * from the PTP standard which mandates that any unicode chars
 * may be used for filenames. I guess this is caused by a 7bit-only
 * filesystem being used intrinsically on the device.
 */
#define DEVICE_FLAG_ONLY_7BIT_FILENAMES 0x00000020
/**
 * This flag indicates that the device will lock up if you
 * try to get status of endpoints and/or release the interface
 * when closing the device. This fixes problems with SanDisk
 * Sansa devices especially. It may be a side-effect of a
 * Windows behaviour of never releasing interfaces.
 */
#define DEVICE_FLAG_NO_RELEASE_INTERFACE 0x00000040
/**
 * This flag was introduced with the advent of Creative ZEN
 * 8GB. The device sometimes return a broken PTP header
 * like this: < 1502 0000 0200 01d1 02d1 01d2 >
 * the latter 6 bytes (representing "code" and "transaction ID")
 * contain junk. This is breaking the PTP/MTP spec but works
 * on Windows anyway, probably because the Windows implementation
 * does not check that these bytes are valid. To interoperate
 * with devices like this, we need this flag to emulate the
 * Windows bug. Broken headers has also been found in the
 * Aricent MTP stack.
 */
#define DEVICE_FLAG_IGNORE_HEADER_ERRORS 0x00000080
/**
 * The Motorola RAZR2 V8 (others?) has broken set object
 * proplist causing the metadata setting to fail. (The
 * set object prop to set individual properties work on
 * this device, but the metadata is plain ignored on
 * tracks, though e.g. playlist names can be set.)
 */
#define DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST 0x00000100
/**
 * The Samsung YP-T10 think Ogg files shall be sent with
 * the "unknown" (PTP_OFC_Undefined) file type, this gives a
 * side effect that is a combination of the iRiver Ogg Alzheimer
 * problem (have to recognized Ogg files on file extension)
 * and a need to report the Ogg support (the device itself does
 * not properly claim to support it) and need to set filetype
 * to unknown when storing Ogg files, even though they're not
 * actually unknown. Later iRivers seem to need this flag since
 * they do not report to support OGG even though they actually
 * do. Often the device supports OGG in USB mass storage mode,
 * then the firmware simply miss to declare metadata support
 * for OGG properly.
 */
#define DEVICE_FLAG_OGG_IS_UNKNOWN 0x00000200
/**
 * The Creative Zen is quite unstable in libmtp but seems to
 * be better with later firmware versions. However, it still
 * frequently crashes when setting album art dimensions. This
 * flag disables setting the dimensions (which seems to make
 * no difference to how the graphic is displayed).
 */
#define DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS 0x00000400
/**
 * Some devices, particularly SanDisk Sansas, need to always
 * have their "OS Descriptor" probed in order to work correctly.
 * This flag provides that extra massage.
 */
#define DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR 0x00000800
/**
 * Samsung has implemented its own playlist format as a .spl file
 * stored in the normal file system, rather than a proper mtp
 * playlist. There are multiple versions of the .spl format
 * identified by a line in the file: VERSION X.XX
 * Version 1.00 is just a simple playlist.
 */
#define DEVICE_FLAG_PLAYLIST_SPL_V1 0x00001000
/**
 * Samsung has implemented its own playlist format as a .spl file
 * stored in the normal file system, rather than a proper mtp
 * playlist. There are multiple versions of the .spl format
 * identified by a line in the file: VERSION X.XX
 * Version 2.00 is playlist but allows DNSe sound settings
 * to be stored, per playlist.
 */
#define DEVICE_FLAG_PLAYLIST_SPL_V2 0x00002000
/**
 * The Sansa E250 is know to have this problem which is actually
 * that the device claims that property PTP_OPC_DateModified
 * is read/write but will still fail to update it. It can only
 * be set properly the first time a file is sent.
 */
#define DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED 0x00004000
/**
 * This avoids use of the send object proplist which
 * is used when creating new objects (not just updating)
 * The DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST is related
 * but only concerns the case where the object proplist
 * is sent in to update an existing object. The Toshiba
 * Gigabeat MEU202 for example has this problem.
 */
#define DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST 0x00008000
/**
 * Devices that cannot support reading out battery
 * level.
 */
#define DEVICE_FLAG_BROKEN_BATTERY_LEVEL 0x00010000

/**
 * Devices that send "ObjectDeleted" events after deletion
 * of images. (libgphoto2)
 */
#define DEVICE_FLAG_DELETE_SENDS_EVENT	0x00020000

/**
 * Cameras that can capture images. (libgphoto2)
 */
#define DEVICE_FLAG_CAPTURE		0x00040000

/**
 * Cameras that can capture images. (libgphoto2)
 */
#define DEVICE_FLAG_CAPTURE_PREVIEW	0x00080000

/**
 * Nikon broken capture support without proper ObjectAdded events.
 * (libgphoto2)
 */
#define DEVICE_FLAG_NIKON_BROKEN_CAPTURE	0x00100000

/**
 * To distinguish the V1 series from the DSLRs and handle them
 * (libgphoto2)
 */
#define DEVICE_FLAG_NIKON_1			0x00200000

/**
 * Broken capture support where cameras do not send CaptureComplete events.
 * (libgphoto2)
 */
#define DEVICE_FLAG_NO_CAPTURE_COMPLETE		0x00400000

/**
 * Direct PTP match required.
 * (libgphoto2)
 */
#define DEVICE_FLAG_OLYMPUS_XML_WRAPPED		0x00800000
/**
 * This flag is like DEVICE_FLAG_OGG_IS_UNKNOWN but for FLAC
 * files instead. Using the unknown filetype for FLAC files.
 */
#define DEVICE_FLAG_FLAC_IS_UNKNOWN		0x01000000
/**
 * Device needs unique filenames, no two files can be
 * named the same string.
 */
#define DEVICE_FLAG_UNIQUE_FILENAMES		0x02000000
/**
 * This flag performs some random magic on the BlackBerry
 * device to switch from USB mass storage to MTP mode we think.
 */
#define DEVICE_FLAG_SWITCH_MODE_BLACKBERRY	0x04000000
/**
 * This flag indicates that the device need an extra long
 * timeout on some operations.
 */
#define DEVICE_FLAG_LONG_TIMEOUT		0x08000000
/**
 * This flag indicates that the device need an explicit
 * USB reset after each connection. Some devices don't
 * like this, so it's not done by default.
 */
#define DEVICE_FLAG_FORCE_RESET_ON_CLOSE	0x10000000
/**
 * On 2016 EOS cameras, do not close the session on exiting,
 * as the device will only report ptp errors afterwards.
 */
#define DEVICE_FLAG_DONT_CLOSE_SESSION          0x20000000
/**
 * It seems that some devices return an bad data when
 * using the GetObjectInfo operation. So in these cases
 * we prefer to override the PTP-compatible object infos
 * with the MTP property list.
 *
 * For example Some Samsung Galaxy S devices contain an MTP
 * stack that present the ObjectInfo in 64 bit instead of
 * 32 bit.
 */
#define DEVICE_FLAG_PROPLIST_OVERRIDES_OI	0x40000000
/**
 * The MTP stack of Samsung Galaxy devices has a mysterious bug in
 * GetPartialObject. When GetPartialObject is invoked to read the last
 * bytes of a file and the amount of data to read is such that the
 * last USB packet sent in the reply matches exactly the USB 2.0
 * packet size, then the Samsung Galaxy device hangs, resulting in a
 * timeout error.
 */
#define DEVICE_FLAG_SAMSUNG_OFFSET_BUG		0x80000000

/**
 * All these bug flags need to be set on SONY NWZ Walkman
 * players, and will be autodetected on unknown devices
 * by detecting the vendor extension descriptor "sony.net"
 */
#define DEVICE_FLAGS_SONY_NWZ_BUGS \
  (DEVICE_FLAG_UNLOAD_DRIVER | \
   DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | \
   DEVICE_FLAG_UNIQUE_FILENAMES | \
   DEVICE_FLAG_FORCE_RESET_ON_CLOSE)
/**
 * All these bug flags need to be set on Android devices,
 * they claim to support MTP operations they actually
 * cannot handle, especially 9805 (Get object property list).
 * These are auto-assigned to devices reporting
 * "android.com" in their device extension descriptor.
 */
#define DEVICE_FLAGS_ANDROID_BUGS \
  (DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | \
   DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST | \
   DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST | \
   DEVICE_FLAG_UNLOAD_DRIVER | \
   DEVICE_FLAG_LONG_TIMEOUT | \
   DEVICE_FLAG_FORCE_RESET_ON_CLOSE)
/**
 * All these bug flags appear on a number of SonyEricsson
 * devices including Android devices not using the stock
 * Android 4.0+ (Ice Cream Sandwich) MTP stack. It is highly
 * supected that these bugs comes from an MTP implementation
 * from Aricent, so it is called the Aricent bug flags as a
 * shorthand. Especially the header errors that need to be
 * ignored is typical for this stack.
 *
 * After some guesswork we auto-assign these bug flags to
 * devices that present the "microsoft.com/WPDNA", and
 * "sonyericsson.com/SE" but NOT the "android.com"
 * descriptor.
 */
#define DEVICE_FLAGS_ARICENT_BUGS \
  (DEVICE_FLAG_IGNORE_HEADER_ERRORS | \
   DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST | \
   DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST)
