/**
 * \file music-players.h
 * List of music players as USB ids.
 *
 * Copyright (C) 2005-2007 Richard A. Low <richard@wentnet.com>
 * Copyright (C) 2005-2013 Linus Walleij <triad@df.lth.se>
 * Copyright (C) 2006-2007,2015-2018 Marcus Meissner <marcus@jet.franken.de>
 * Copyright (C) 2007 Ted Bullock
 * Copyright (C) 2012 Sony Mobile Communications AB
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
 * Free Software Foundation, Inc., 59 Temple Place - Suite 330,
 * Boston, MA 02111-1307, USA.
 *
 * This file is supposed to be included within a struct from both libmtp
 * and libgphoto2.
 *
 * Information can be harvested from Windows driver .INF files, see:
 * http://msdn.microsoft.com/en-us/library/aa973606.aspx
 */
/*
 * MTP device list, trying real bad to get all devices into
 * this list by stealing from everyone I know.
 * Some devices taken from the Rockbox device listing:
 * http://www.rockbox.org/twiki/bin/view/Main/DeviceDetection
 */

  /*
   * Creative Technology and ZiiLABS
   * Initially the Creative devices was all we supported so these are
   * the most thoroughly tested devices. Presumably only the devices
   * with older firmware (the ones that have 32bit object size) will
   * need the DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL flag. This bug
   * manifest itself when you have a lot of folders on the device,
   * some of the folders will start to disappear when getting all objects
   * and properties.
   */
  /* https://sourceforge.net/p/libmtp/bugs/1898/ */
  { "Creative", 0x041e, "ZEN Micro", 0x411e,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Vision", 0x411f,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "Portable Media Center", 0x4123,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Xtra (MTP mode)", 0x4128,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Dell", 0x041e, "DJ (2nd generation)", 0x412f,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Micro (MTP mode)", 0x4130,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Touch (MTP mode)", 0x4131,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Dell", 0x041e, "Dell Pocket DJ (MTP mode)", 0x4132,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN MicroPhoto (alternate version)", 0x4133,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Sleek (MTP mode)", 0x4137,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN MicroPhoto", 0x413c,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Sleek Photo", 0x413d,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Vision:M", 0x413e,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by marazm@o2.pl
  { "Creative", 0x041e, "ZEN V", 0x4150,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by danielw@iinet.net.au
  // This version of the Vision:M needs the no release interface flag,
  // unclear whether the other version above need it too or not.
  { "Creative", 0x041e, "ZEN Vision:M (DVP-HD0004)", 0x4151,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by Darel on the XNJB forums
  { "Creative", 0x041e, "ZEN V Plus", 0x4152,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Creative", 0x041e, "ZEN Vision W", 0x4153,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Don't add 0x4155: this is a Zen Stone device which is not MTP
  // Reported by Paul Kurczaba <paul@kurczaba.com>
  { "Creative", 0x041e, "ZEN", 0x4157,
      DEVICE_FLAG_IGNORE_HEADER_ERRORS |
      DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by Ringofan <mcroman@users.sourceforge.net>
  { "Creative", 0x041e, "ZEN V 2GB", 0x4158,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by j norment <stormzen@gmail.com>
  { "Creative", 0x041e, "ZEN Mozaic", 0x4161,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by Aaron F. Gonzalez <sub_tex@users.sourceforge.net>
  { "Creative", 0x041e, "ZEN X-Fi", 0x4162,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by farmerstimuli <farmerstimuli@users.sourceforge.net>
  { "Creative", 0x041e, "ZEN X-Fi 3", 0x4169,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by Todor Gyumyushev <yodor1@users.sourceforge.net>
  { "ZiiLABS", 0x041e, "Zii EGG", 0x6000,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
      DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },

  /*
   * Samsung
   * We suspect that more of these are dual mode.
   * We suspect more of these might need DEVICE_FLAG_NO_ZERO_READS
   * We suspect more of these might need DEVICE_FLAG_PLAYLIST_SPL_V1
   *  or DEVICE_FLAG_PLAYLIST_SPL_V2 to get playlists working.
   * YP-NEU, YP-NDU, YP-20, YP-800, YP-MF Series, YP-100, YP-30
   * YP-700 and YP-90 are NOT MTP, but use a Samsung custom protocol.
   * See: http://wiki.xiph.org/index.php/PortablePlayers for Ogg
   * status.
   */
  // From anonymous SourceForge user, not verified
  { "Samsung", 0x04e8, "YP-900", 0x0409, DEVICE_FLAG_NONE },
  // From MItch <dbaker@users.sourceforge.net>
  { "Samsung", 0x04e8, "I550W Phone", 0x04a4, DEVICE_FLAG_NONE },
  // From Manfred Enning <menning@users.sourceforge.net>
  { "Samsung", 0x04e8, "Jet S8000", 0x4f1f, DEVICE_FLAG_NONE },
  // From Gabriel Nunes <gabrielkm1@yahoo.com.br>
  { "Samsung", 0x04e8, "YH-920 (501d)", 0x501d, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Soren O'Neill
  { "Samsung", 0x04e8, "YH-920 (5022)", 0x5022, DEVICE_FLAG_UNLOAD_DRIVER },
  // Contributed by aronvanammers on SourceForge
  { "Samsung", 0x04e8, "YH-925GS", 0x5024, DEVICE_FLAG_NONE },
  // From libgphoto2, according to tests by Stephan Fabel it cannot
  // get all objects with the getobjectproplist command..
  { "Samsung", 0x04e8, "YH-820", 0x502e,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Contributed by polux2001@users.sourceforge.net
  { "Samsung", 0x04e8, "YH-925(-GS)", 0x502f,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Contributed by anonymous person on SourceForge
  { "Samsung", 0x04e8, "YH-J70J", 0x5033,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From XNJB user
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-Z5", 0x503c,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // Don't add 0x5041 as this is YP-Z5 in USB mode
  // Contributed by anonymous person on SourceForge
  { "Samsung", 0x04e8, "YP-T7J", 0x5047,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by cstrickler@gmail.com
  { "Samsung", 0x04e8, "YP-U2J (YP-U2JXB/XAA)", 0x5054,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by Andrew Benson
  { "Samsung", 0x04e8, "YP-F2J", 0x5057,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Patrick <skibler@gmail.com>
  // Just guessing but looks like .spl v1 http://www.anythingbutipod.com/forum/showthread.php?t=14160
  { "Samsung", 0x04e8, "YP-K5", 0x505a,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_NO_ZERO_READS |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From dev.local@gmail.com - 0x4e8/0x507c is the UMS mode, apparently
  // do not add that device.
  // From m.eik michalke
  // This device does NOT use the special SPL playlist according to sypqgjxu@gmx.de.
  { "Samsung", 0x04e8, "YP-U3", 0x507d,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by Matthew Wilcox <matthew@wil.cx>
  // Sergio <sfrdll@tiscali.it> reports this device need the BROKEN ALL flag.
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-T9", 0x507f,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Paul Clinch
  // Just guessing but looks like .spl v1 http://www.anythingbutipod.com/forum/showthread.php?t=14160
  // Some versions of the firmware reportedly support OGG, reportedly only the
  // UMS versions, so MTP+OGG is not possible on this device.
  { "Samsung", 0x04e8, "YP-K3", 0x5081,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From XNJB user
  // From Alistair Boyle, .spl v2 required for playlists
  // According to the device log it properly supports OGG
  { "Samsung", 0x04e8, "YP-P2", 0x5083,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_NO_ZERO_READS |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_PLAYLIST_SPL_V2 },
  // From Paul Clinch
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-T10", 0x508a,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_PLAYLIST_SPL_V1 |
      DEVICE_FLAG_NO_ZERO_READS },
  // From Wim Verwimp <wimverwimp@gmail.com>
  // Not sure about the Ogg and broken proplist flags here. Just guessing.
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-S5", 0x508b,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Ludovic Danigo
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-S3", 0x5091,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Adrian Levi <adrian.levi@gmail.com>
  // Guessing on .spl flag
  // This one supports OGG properly through the correct MTP type.
  { "Samsung", 0x04e8, "YP-U4", 0x5093, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Chris Le Sueur <thefishface@gmail.com>
  // Guessing on .spl flag
  // This one supports OGG properly through the correct MTP type.
  { "Samsung", 0x04e8, "YP-R1", 0x510f,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_UNIQUE_FILENAMES |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // From Anonymous SourceForge user
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-Q1", 0x5115,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Holger
  { "Samsung", 0x04e8, "YP-M1", 0x5118,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_PLAYLIST_SPL_V2 },
  // From Anonymous SourceForge user
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-P3", 0x511a,
      DEVICE_FLAG_UNLOAD_DRIVER |
     DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
     DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Anonymous SourceForge user
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-Q2", 0x511d,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Marco Pizzocaro <mpizzocaro@users.sourceforge.net>
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-U5", 0x5121,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 |
      DEVICE_FLAG_UNIQUE_FILENAMES |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // From Leonardo Accorsi <laccorsi@users.sourceforge.net>
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-R0", 0x5125,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 |
      DEVICE_FLAG_UNIQUE_FILENAMES |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // The "YP-R2" (0x04e8/0x512d) is NOT MTP, it is UMS only.
  // Guessing on device flags for the MTP mode...
 { "Samsung", 0x04e8, "YP-R2", 0x512e,
     DEVICE_FLAG_UNLOAD_DRIVER |
     DEVICE_FLAG_OGG_IS_UNKNOWN |
     DEVICE_FLAG_UNIQUE_FILENAMES |
     DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
     DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From Manuel Carro
  // Copied from Q2
 { "Samsung", 0x04e8, "YP-Q3", 0x5130,
     DEVICE_FLAG_UNLOAD_DRIVER |
     DEVICE_FLAG_OGG_IS_UNKNOWN |
     DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
     DEVICE_FLAG_PLAYLIST_SPL_V1 },
 // Reported by: traaf <traaf@users.sourceforge.net>
 // Guessing on the playlist type!
 // Appears to present itself properly as a PTP device with MTP extensions!
 { "Samsung", 0x04e8, "YP-Z3", 0x5137,
     DEVICE_FLAG_UNLOAD_DRIVER |
     DEVICE_FLAG_OGG_IS_UNKNOWN |
     DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
     DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // YP-F3 is NOT MTP - USB mass storage
  // From a rouge .INF file
  // this device ID seems to have been recycled for:
  // the Samsung SGH-A707 Cingular cellphone
  // the Samsung L760-V cellphone
  // the Samsung SGH-U900 cellphone
  // the Samsung Fascinate player
  { "Samsung", 0x04e8,
      "YH-999 Portable Media Center/SGH-A707/SGH-L760V/SGH-U900/Verizon Intensity/Fascinate",
      0x5a0f, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // From Santi Béjar <sbejar@gmail.com> - not sure this is MTP...
  // { "Samsung", 0x04e8, "Z170 Mobile Phone", 0x6601, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Santi Béjar <sbejar@gmail.com> - not sure this is MTP...
  // { "Samsung", 0x04e8, "E250 Mobile Phone", 0x663e, DEVICE_FLAG_UNLOAD_DRIVER },
  // From an anonymous SF user
  { "Samsung", 0x04e8, "M7600 Beat/GT-S8300T/SGH-F490/S8300", 0x6642,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_BROKEN_BATTERY_LEVEL },
  // From Lionel Bouton
  { "Samsung", 0x04e8, "X830 Mobile Phone", 0x6702,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From James <jamestech@gmail.com>
  { "Samsung", 0x04e8, "U600 Mobile Phone", 0x6709,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From Cesar Cardoso <cesar@cesarcardoso.tk>
  // No confirmation that this is really MTP.
  { "Samsung", 0x04e8, "F250 Mobile Phone", 0x6727,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From Charlie Todd  2007-10-31
  { "Samsung", 0x04e8, "Juke (SCH-U470)", 0x6734,
      DEVICE_FLAG_UNLOAD_DRIVER},
  // Reported by Tenn
  { "Samsung", 0x04e8, "GT-B2700", 0x6752,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Added by Greg Fitzgerald <netzdamon@gmail.com>
  { "Samsung", 0x04e8, "SAMSUNG Trance", 0x6763,
      DEVICE_FLAG_UNLOAD_DRIVER |
     DEVICE_FLAG_NO_ZERO_READS |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From anonymous sourceforge user
  // Guessing on .spl flag, maybe needs NO_ZERO_READS, whatdoIknow
  { "Samsung", 0x04e8, "GT-S8500", 0x6819,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  /*
   * These entries seems to be used on a *lot* of Samsung
   * Android phones. It is *not* the Android MTP stack but an internal
   * Samsung stack. The devices present a few different product IDs
   * depending on mode:
   *
   * 0x685b - UMS
   * 0x685c - MTP + ADB
   * 0x685e - UMS + CDC (not MTP)
   * 0x6860 - MTP mode (default)
   * 0x6863 - USB CDC RNDIS (not MTP)
   * 0x6865 - PTP mode (not MTP)
   * 0x6877 - Kies mode? Does it have MTP?
   *
   * Used on these samsung devices:
   * GT P7310/P7510/N7000/I9100/I9250/I9300
   * Galaxy Nexus
   * Galaxy Tab 7.7/10.1
   * Galaxy S GT-I9000
   * Galaxy S Advance GT-I9070
   * Galaxy S2
   * Galaxy S3
   * Galaxy Note
   * Gakaxy Xcover
   * Galaxy Y
   *
   * - It seems that some PTP commands are broken.
   * - Devices seem to have a connection timeout, the session must be
   *   open in about 3 seconds since the device is plugged in, after
   *   that time it will not respond. Thus GUI programs work fine.
   * - Seems also to be used with Galaxy Nexus debug mode and on
   *   US markets for some weird reason.
   * - has a weird USB bug if it reads exactly 512byte (usb 2 packetsize) 
   *   the device will hang. this is one of the reasons we need to disable
   *   DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST as it can hit this size :/
   *   Post scriptum: This did not help, so we added it again. -Marcus
   *
   * From: Ignacio Martínez <ignacio.martinezrivera@yahoo.es> and others
   * From Harrison Metzger <harrisonmetz@gmail.com>
   */
  { "Samsung", 0x04e8,
      "Galaxy models (MTP+ADB)", 0x685c,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_LONG_TIMEOUT |
      DEVICE_FLAG_PROPLIST_OVERRIDES_OI	|
      DEVICE_FLAG_SAMSUNG_OFFSET_BUG |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_FLAC_IS_UNKNOWN },
  { "Samsung", 0x04e8,
      "Galaxy models (MTP)", 0x6860,
      /* DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | */
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_LONG_TIMEOUT |
      DEVICE_FLAG_PROPLIST_OVERRIDES_OI |
      DEVICE_FLAG_SAMSUNG_OFFSET_BUG |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // From: Erik Berglund <erikjber@users.sourceforge.net>
  // Logs indicate this needs DEVICE_FLAG_NO_ZERO_READS
  // No Samsung platlists on this device.
  // https://sourceforge.net/tracker/?func=detail&atid=809061&aid=3026337&group_id=158745
  // i5800 duplicate reported by igel <igel-kun@users.sourceforge.net>
  // Guessing this has the same problematic MTP stack as the device
  // above.
  { "Samsung", 0x04e8, "Galaxy models Kies mode", 0x6877,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_LONG_TIMEOUT |
      DEVICE_FLAG_PROPLIST_OVERRIDES_OI	|
      DEVICE_FLAG_SAMSUNG_OFFSET_BUG |
      DEVICE_FLAG_OGG_IS_UNKNOWN |
      DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // From: John Gorkos <ab0oo@users.sourceforge.net> and
  // Akos Maroy <darkeye@users.sourceforge.net>
  { "Samsung", 0x04e8, "Vibrant SGH-T959/Captivate/Media player mode", 0x68a9,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // Reported by Sleep.Walker <froser@users.sourceforge.net>
  { "Samsung", 0x04e8, "GT-B2710/Xcover 271", 0x68af,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 },
  // From anonymous Sourceforge user
  { "Samsung", 0x04e8, "GT-S5230", 0xe20c, DEVICE_FLAG_NONE },


  /*
   * Microsoft
   * All except the first probably need MTPZ to work
   */
  { "Microsoft/Intel", 0x045e, "Bandon Portable Media Center", 0x00c9,
      DEVICE_FLAG_NONE },
  // HTC Mozart is using the PID, as is Nokia Lumia 800
  // May need MTPZ to work
  { "Microsoft", 0x045e, "Windows Phone", 0x04ec, DEVICE_FLAG_NONE },
  // Reported by Tadimarri Sarath <sarath.tadi@gmail.com>
  // No idea why this use an Intel PID, perhaps a leftover from
  // the early PMC development days when Intel and Microsoft were
  // partnering.
  { "Microsoft", 0x045e, "Windows MTP Simulator", 0x0622, DEVICE_FLAG_NONE },
  // Reported by Edward Hutchins (used for Zune HDs)
  { "Microsoft", 0x045e, "Zune HD", 0x063e, DEVICE_FLAG_NONE },
  { "Microsoft", 0x045e, "Kin 1", 0x0640, DEVICE_FLAG_NONE },
  { "Microsoft/Sharp/nVidia", 0x045e, "Kin TwoM", 0x0641, DEVICE_FLAG_NONE },
  // Reported by Farooq Zaman (used for all Zunes)
  { "Microsoft", 0x045e, "Zune", 0x0710, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/155/ */
  { "Microsoft", 0x045e, "Lumia 950 XL Dual SIM (RM-1116)", 0x0a00, DEVICE_FLAG_NONE },
  // Reported by Olegs Jeremejevs
  { "Microsoft/HTC", 0x045e, "HTC 8S", 0xf0ca, DEVICE_FLAG_NONE },

  /*
   * JVC
   */
  // From Mark Veinot
  { "JVC", 0x04f1, "Alneo XA-HD500", 0x6105, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/bugs/1613/ */
  { "Intex", 0x05c6, "Aqua Fish", 0x0a07, DEVICE_FLAG_NONE },

  /*
   * Philips
   */
  { "Philips", 0x0471, "HDD6320/00 or HDD6330/17", 0x014b, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Anonymous SourceForge user
  { "Philips", 0x0471, "HDD14XX,HDD1620 or HDD1630/17", 0x014c, DEVICE_FLAG_NONE },
  // from discussion forum
  { "Philips", 0x0471, "HDD085/00 or HDD082/17", 0x014d, DEVICE_FLAG_NONE },
  // from XNJB forum
  { "Philips", 0x0471, "GoGear SA9200", 0x014f, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // From John Coppens <jcoppens@users.sourceforge.net>
  { "Philips", 0x0471, "SA1115/55", 0x0164, DEVICE_FLAG_NONE },
  // From Gerhard Mekenkamp
  { "Philips", 0x0471, "GoGear Audio", 0x0165, DEVICE_FLAG_NONE },
  // from David Holm <wormie@alberg.dk>
  { "Philips", 0x0471, "Shoqbox", 0x0172, DEVICE_FLAG_ONLY_7BIT_FILENAMES },
  // from npedrosa
  { "Philips", 0x0471, "PSA610", 0x0181, DEVICE_FLAG_NONE },
  // From libgphoto2 source
  { "Philips", 0x0471, "HDD6320", 0x01eb, DEVICE_FLAG_NONE },
  // From Detlef Meier <dm@emlix.com>
  { "Philips", 0x0471, "GoGear SA6014/SA6015/SA6024/SA6025/SA6044/SA6045", 0x084e, DEVICE_FLAG_UNLOAD_DRIVER },
  // From anonymous Sourceforge user SA5145/02
  { "Philips", 0x0471, "GoGear SA5145", 0x0857, DEVICE_FLAG_UNLOAD_DRIVER },
  /* https://sourceforge.net/p/libmtp/bugs/1260/ */
  { "Philips", 0x0471, "i908", 0x190b, DEVICE_FLAG_UNLOAD_DRIVER },
  // From a
  { "Philips", 0x0471, "GoGear SA6125/SA6145/SA6185", 0x2002, DEVICE_FLAG_UNLOAD_DRIVER },
  // From anonymous Sourceforge user, not verified to be MTP!
  { "Philips", 0x0471, "GoGear SA3345", 0x2004, DEVICE_FLAG_UNLOAD_DRIVER },
  /* https://sourceforge.net/p/libmtp/support-requests/163/ */
  { "Philips", 0x0471, "W6610", 0x2008, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Roberto Vidmar <rvidmar@libero.it>
  { "Philips", 0x0471, "SA5285", 0x2022, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Elie De Brauwer <elie@de-brauwer.be>
  { "Philips", 0x0471, "GoGear ViBE SA1VBE04", 0x2075,
    DEVICE_FLAG_UNLOAD_DRIVER },
  // From Anonymous SourceForge user
  { "Philips", 0x0471, "GoGear Muse", 0x2077,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From Elie De Brauwer <elie@de-brauwer.be>
  { "Philips", 0x0471, "GoGear ViBE SA1VBE04/08", 0x207b,
    DEVICE_FLAG_UNLOAD_DRIVER },
  // From josmtx <josmtx@users.sourceforge.net>
  { "Philips", 0x0471, "GoGear Aria", 0x207c,
    DEVICE_FLAG_UNLOAD_DRIVER },
  // From epklein
  { "Philips", 0x0471, "GoGear SA1VBE08KX/78", 0x208e,
    DEVICE_FLAG_UNLOAD_DRIVER },
  // From Anonymous SourceForge User
  { "Philips", 0x0471, "GoGear VIBE SA2VBE[08|16]K/02", 0x20b7,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From Anonymous SourceForge User
  { "Philips", 0x0471, "GoGear Ariaz", 0x20b9,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From Anonymous SourceForge User
  { "Philips", 0x0471, "GoGear Vibe/02", 0x20e5,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Philip Rhoades
  { "Philips", 0x0471, "GoGear Ariaz/97", 0x2138,
      DEVICE_FLAG_UNLOAD_DRIVER },
  /* https://sourceforge.net/p/libmtp/bugs/1186/ */
  { "Philips", 0x0471, "PI3900B2/58 ", 0x2190,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // from XNJB user
  { "Philips", 0x0471, "PSA235", 0x7e01, DEVICE_FLAG_NONE },

  /*
   * Acer
   * Reporters:
   * Franck VDL <franckv@users.sourceforge.net>
   * Matthias Arndt <simonsunnyboy@users.sourceforge.net>
   * Arvin Schnell <arvins@users.sourceforge.net>
   * Philippe Marzouk <philm@users.sourceforge.net>
   * nE0sIghT <ne0sight@users.sourceforge.net>
   * Maxime de Roucy <maxime1986@users.sourceforge.net>
   */
  { "Acer", 0x0502, "Iconia TAB A500 (ID1)", 0x3325,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A500 (ID2)", 0x3341,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A501 (ID1)", 0x3344,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A501 (ID2)", 0x3345,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A100 (ID1)", 0x3348,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A100 (ID2)", 0x3349,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A101 (ID1)", 0x334a,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A700", 0x3378,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A200 (ID1)", 0x337c,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A200 (ID2)", 0x337d,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A510 (ID1)", 0x3389,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A510 (ID2)", 0x338a,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "S500 CloudMobile", 0x33aa,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "E350 Liquid Gallant Duo (ID1)", 0x33c3,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "E350 Liquid Gallant Duo (ID2)", 0x33c4,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A210", 0x33cb,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia TAB A110", 0x33d8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Liquid Z120 MT65xx Android Phone", 0x3473,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1029/ */
  { "Acer", 0x0502, "Liquid E2", 0x3514,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia A1-810", 0x353c,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Liquid Z130 MT65xx Android Phone", 0x355f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1206/ */
  { "Acer", 0x0502, "Iconia A3-A11", 0x3586,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1103/ */
  { "Acer", 0x0502, "Liquid E3", 0x35a8,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1147/ */
  { "Acer", 0x0502, "Z150", 0x35e4,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1184/ */
  { "Acer", 0x0502, "Liquid X1", 0x3609,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1298/ */
  { "Acer", 0x0502, "Z160", 0x361d,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "Iconia A1-840FHD", 0x362d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1251/ */
  { "Acer", 0x0502, "E39", 0x3643,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1369/ */
  { "Acer", 0x0502, "liquid e700", 0x3644,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acer", 0x0502, "One 7", 0x3657,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/183/ */
  { "Acer", 0x0502, "Z200", 0x3683,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1579/ */
  { "Acer", 0x0502, "A1-841", 0x365e,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1341/ */
  { "Acer", 0x0502, "Liquid S56", 0x3725,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/228/ */
  { "Acer", 0x0502, "Liquid Z220 (ID1)", 0x374f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/188/ */
  { "Acer", 0x0502, "Liquid Z220 (ID2)", 0x3750,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1478/ */
  { "Acer", 0x0502, "Liquid Z330", 0x3750,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1552/ */
  { "Acer", 0x0502, "Liquid Z630", 0x37ef,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1469/ */
  { "Acer", 0x0502, "Z530", 0x3822,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1534/ */
  { "Acer", 0x0502, "Z530 16GB", 0x3823,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* Reported by Jocelyn Mayer <l_indien@magic.fr> */
  { "Acer", 0x0502, "Iconia One 10", 0x3841,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/279/ */
  { "Acer", 0x0502, "B3-A20", 0x3841,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/298/ */
  { "Acer", 0x0502, "A3-A40", 0x387a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/298/ */
  { "Acer", 0x0502, "Zest T06", 0x3886,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1733/ */
  { "Acer", 0x0502, "Liquid Zest 4G", 0x38a5,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* Mia */
  { "Acer", 0x0502, "Liquid Zest Plus", 0x38bb,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* Richard Waterbeek <richard@fotobakje.nl> on libmtp-discuss */
  { "Acer", 0x0502, "Liquid Liquid Z6E", 0x3938,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1838/ */
  { "Acer", 0x0502, "Iconia One 10 B3-A40 ", 0x394b,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * SanDisk
   * several devices (c150 for sure) are definitely dual-mode and must
   * have the USB mass storage driver that hooks them unloaded first.
   * They all have problematic dual-mode making the device unload effect
   * uncertain on these devices.
   *
   * All older devices seem to need DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL.
   * Old chipsets: e200/c200 use PP5024 from Nvidia (formerly PortalPlayer).
   * m200 use TCC770 from Telechips.
   *
   * The newer Sansa v2 chipset, AD3525 from Austriamicrosystems (AMS) found
   * in e280 v2 c200 v2, Clip, Fuze etc require
   * DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST
   * and DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR to work properly.
   *
   * For more info see: http://daniel.haxx.se/sansa/v2.html
   */
  // Reported by Brian Robison
  { "SanDisk", 0x0781, "Sansa m230/m240", 0x7400,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // From Rockbox device listing
  { "SanDisk", 0x0781, "Sansa m200-tcc (MTP mode)", 0x7401,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by tangent_@users.sourceforge.net
  { "SanDisk", 0x0781, "Sansa c150", 0x7410,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // From libgphoto2 source
  // Reported by <gonkflea@users.sourceforge.net>
  // Reported by Mike Owen <mikeowen@computerbaseusa.com>
  { "SanDisk", 0x0781, "Sansa e200/e250/e260/e270/e280", 0x7420,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Don't add 0x7421 as this is e280 in MSC mode
  // Reported by XNJB user
  { "SanDisk", 0x0781, "Sansa e260/e280 v2", 0x7422,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by XNJB user
  { "SanDisk", 0x0781, "Sansa m240/m250", 0x7430,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by Eugene Brevdo <ebrevdo@princeton.edu>
  { "SanDisk", 0x0781, "Sansa Clip", 0x7432,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED},
  // Reported by HackAR <hackar@users.sourceforge.net>
  { "SanDisk", 0x0781, "Sansa Clip v2", 0x7434,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED},
  // Reported by anonymous user at sourceforge.net
  { "SanDisk", 0x0781, "Sansa c240/c250", 0x7450,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by anonymous SourceForge user
  { "SanDisk", 0x0781, "Sansa c250 v2", 0x7452,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by Troy Curtis Jr.
  { "SanDisk", 0x0781, "Sansa Express", 0x7460,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by XNJB user, and Miguel de Icaza <miguel@gnome.org>
  // This has no dual-mode so no need to unload any driver.
  // This is a Linux based device!
  { "SanDisk", 0x0781, "Sansa Connect", 0x7480, DEVICE_FLAG_NONE },
  // Reported by anonymous SourceForge user
  { "SanDisk", 0x0781, "Sansa View", 0x74b0,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by Patrick <skibler@gmail.com>
  // There are apparently problems with this device.
  { "SanDisk", 0x0781, "Sansa Fuze", 0x74c0,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Harry Phillips <tuxcomputers@users.sourceforge.net>
  { "SanDisk", 0x0781, "Sansa Fuze v2", 0x74c2,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED },
  // Reported by anonymous SourceForge user
  // Need BROKEN_SET_SAMPLE_DIMENSIONS accordning to
  // Michael <mpapet@users.sourceforge.net>
  { "SanDisk", 0x0781, "Sansa Clip+", 0x74d0,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED},
  // Reported by anonymous SourceForge user
  { "SanDisk", 0x0781, "Sansa Fuze+", 0x74e0,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED},
  // Reported by mattyj2001@users.sourceforge.net
  { "SanDisk", 0x0781, "Sansa Clip Zip", 0x74e4,
    DEVICE_FLAG_UNLOAD_DRIVER |  DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE | DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR |
    DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
    DEVICE_FLAG_CANNOT_HANDLE_DATEMODIFIED},

  /*
   * iRiver
   * we assume that PTP_OC_MTP_GetObjPropList is essentially
   * broken on all iRiver devices, meaning it simply won't return
   * all properties for a file when asking for metadata 0xffffffff.
   * Please test on your device if you believe it isn't broken!
   */
  { "iRiver", 0x1006, "H300 Series MTP", 0x3004,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x1006, "Portable Media Center 1", 0x4002,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x1006, "Portable Media Center 2", 0x4003,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // From [st]anislav <iamstanislav@gmail.com>
  { "iRiver", 0x1042, "T7 Volcano", 0x1143, DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // From an anonymous person at SourceForge, uncertain about this one
  { "iRiver", 0x4102, "iFP-880", 0x1008,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // 0x4102, 0x1042 is a USB mass storage mode for E100 v2/Lplayer
  // From libgphoto2 source
  { "iRiver", 0x4102, "T10", 0x1113,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x4102, "T20 FM", 0x1114,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // This appears at the MTP-UMS site
  { "iRiver", 0x4102, "T20", 0x1115,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x4102, "U10", 0x1116,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x4102, "T10b", 0x1117,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x4102, "T20b", 0x1118,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x4102, "T30", 0x1119,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // Reported by David Wolpoff
  { "iRiver", 0x4102, "T10 2GB", 0x1120,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // Rough guess this is the MTP device ID...
  { "iRiver", 0x4102, "N12", 0x1122,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // Reported by Philip Antoniades <philip@mysql.com>
  // Newer iriver devices seem to have shaped-up firmware without any
  // of the annoying bugs.
  { "iRiver", 0x4102, "Clix2", 0x1126, DEVICE_FLAG_NONE },
  // Reported by Adam Torgerson
  { "iRiver", 0x4102, "Clix", 0x112a,
    DEVICE_FLAG_NO_ZERO_READS | DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // Reported by Douglas Roth <dougaus@gmail.com>
  { "iRiver", 0x4102, "X20", 0x1132,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // Reported by Robert Ugo <robert_ugo@users.sourceforge.net>
  { "iRiver", 0x4102, "T60", 0x1134,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  // Reported by two anonymous SourceForge users
  // Needs the stronger OGG_IS_UNKNOWN flag to support OGG properly,
  // be aware of newer players that may be needing this too.
  { "iRiver", 0x4102, "E100", 0x1141,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by anonymous SourceForge user
  // Need verification of whether this firmware really need all these flags
  { "iRiver", 0x4102, "E100 v2/Lplayer", 0x1142,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by Richard Vennemann <vennemann@users.sourceforge.net>
  // In USB Mass Storage mode it is 0x4102/0x1047
  // Seems to use the new shaped-up firmware.
  { "iRiver", 0x4102, "Spinn", 0x1147, DEVICE_FLAG_NONE },
  // Reported by Tony Janssen <tonyjanssen@users.sourceforge.net>
  { "iRiver", 0x4102, "E50", 0x1151,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by anonymous SourceForge user, guessing on flags
  { "iRiver", 0x4102, "E150", 0x1152,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by Jakub Matraszek <jakub.matraszek@gmail.com>
  { "iRiver", 0x4102, "T5", 0x1153,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_ZERO_READS | DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by pyalex@users.sourceforge.net
  // Guessing that this needs the FLAG_NO_ZERO_READS...
  { "iRiver", 0x4102, "E30", 0x1167,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  /* https://sourceforge.net/p/libmtp/bugs/1766/ */
  { "iRiver", 0x4102, "AK380", 0x1195,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  /* https://sourceforge.net/p/libmtp/bugs/1634/ 
   * copying flags from above */
  { "iRiver", 0x4102, "AK70", 0x1200,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  /* https://bugzilla.suse.com/show_bug.cgi?id=1176588  ... */
  { "A&K", 0x4102, "SR15", 0x1213,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  /* https://github.com/libmtp/libmtp/issues/85  ... */
  { "A&K", 0x4102, "SE180", 0x1230,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by Scott Call
  // Assume this actually supports OGG though it reports it doesn't.
  { "iRiver", 0x4102, "H10 20GB", 0x2101,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  { "iRiver", 0x4102, "H10 5GB", 0x2102,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },
  // From Rockbox device listing
  { "iRiver", 0x4102, "H10 5.6GB", 0x2105,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_OGG_IS_UNKNOWN },


  /*
   * Dell
   */
  { "Dell Inc", 0x413c, "DJ Itty", 0x4500,
      DEVICE_FLAG_NONE },
  /* Reported by: JR */
  { "Dell Inc", 0x413c, "Dell Streak 7", 0xb10b,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Dell Inc", 0x413c, "Dell Venue 7 inch", 0xb11a,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Dell Inc", 0x413c, "Dell Venue 7 inch (2nd ID)", 0xb11b,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Toshiba
   * Tentatively flagged all Toshiba devices with
   * DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST after one of them
   * showed erroneous behaviour.
   */
  { "Toshiba", 0x0930, "Gigabeat MEGF-40", 0x0009,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  { "Toshiba", 0x0930, "Gigabeat", 0x000c,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Nicholas Tripp
  { "Toshiba", 0x0930, "Gigabeat P20", 0x000f,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // From libgphoto2
  { "Toshiba", 0x0930, "Gigabeat S", 0x0010,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Rob Brown
  { "Toshiba", 0x0930, "Gigabeat P10", 0x0011,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by solanum@users.sourceforge.net
  { "Toshiba", 0x0930, "Gigabeat V30", 0x0014,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Michael Davis <slithy@yahoo.com>
  { "Toshiba", 0x0930, "Gigabeat U", 0x0016,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Devon Jacobs <devo@godevo.com>
  { "Toshiba", 0x0930, "Gigabeat MEU202", 0x0018,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Rolf <japan (at) dl3lar.de>
  { "Toshiba", 0x0930, "Gigabeat T", 0x0019,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Phil Ingram <ukpbert@users.sourceforge.net>
  // Tentatively added - no real reports of this device ID being MTP,
  // reports as USB Mass Storage currently.
  { "Toshiba", 0x0930, "Gigabeat MEU201", 0x001a,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by anonymous SourceForge user
  { "Toshiba", 0x0930, "Gigabeat MET401", 0x001d,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },
  // Reported by Andree Jacobson <nmcandree@users.sourceforge.net>
  { "Toshiba", 0x0930, "Excite AT300", 0x0963,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1557/ */
  { "Toshiba", 0x0930, "Excite AT200", 0x0960,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Nigel Cunningham <nigel@tuxonice.net>
  // Guessing on Android bugs
  { "Toshiba", 0x0930, "Thrive AT100/AT105", 0x7100,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Archos
   * These devices have some dual-mode interfaces which will really
   * respect the driver unloading, so DEVICE_FLAG_UNLOAD_DRIVER
   * really work on these devices!
   *
   * Devices reported by:
   * Archos
   * Alexander Haertig <AlexanderHaertig@gmx.de>
   * Jan Binder
   * gudul1@users.sourceforge.net
   * Etienne Chauchot <chauchot.etienne@free.fr>
   * Kay McCormick <kaym@modsystems.com>
   * Joe Rabinoff
   * Jim Krehl <jimmuhk@users.sourceforge.net>
   * Adrien Guichard <tmor@users.sourceforge.net>
   * Clément <clemvangelis@users.sourceforge.net>
   * Thackert <hackertenator@users.sourceforge.net>
   * Till <Till@users.sourceforge.net>
   * Sebastien ROHAUT
   */
  { "Archos", 0x0e79, "Gmini XS100", 0x1207, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "XS202 (MTP mode)", 0x1208, DEVICE_FLAG_NONE },
  { "Archos", 0x0e79, "104 (MTP mode)", 0x120a, DEVICE_FLAG_NONE },
  { "Archos", 0x0e79, "204 (MTP mode)", 0x120c, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "404 (MTP mode)", 0x1301, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "404CAM (MTP mode)", 0x1303, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "504 (MTP mode)", 0x1307, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "604 (MTP mode)", 0x1309, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "604WIFI (MTP mode)", 0x130b, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "704 mobile dvr", 0x130d, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "704TV (MTP mode)", 0x130f, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "405 (MTP mode)", 0x1311, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "605 (MTP mode)", 0x1313, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "605F (MTP mode)", 0x1315, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "705 (MTP mode)", 0x1319, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "TV+ (MTP mode)", 0x131b, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "105 (MTP mode)", 0x131d, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "405HDD (MTP mode)", 0x1321, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "5 (MTP mode 1)", 0x1331, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "5 (MTP mode 2)", 0x1333, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "7 (MTP mode)", 0x1335, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "SPOD (MTP mode)", 0x1341, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "5S IT (MTP mode)", 0x1351, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "5H IT (MTP mode)", 0x1357, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "48 (MTP mode)", 0x1421, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "Arnova Childpad", 0x1458, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "Arnova 8c G3", 0x145e, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "Arnova 10bG3 Tablet", 0x146b, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "97 Xenon", 0x149a, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "97 Titanium", 0x14ad, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "80 Titanium", 0x14bf, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 Titanium", 0x14b9, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/91/ */
  { "Archos", 0x0e79, "70b Titanium", 0x14ef, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "8o G9 (MTP mode)", 0x1508, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "8o G9 Turbo (MTP mode)", 0x1509, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "80G9", 0x1518, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 G9 (ID1)", 0x1528, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 G9 (ID2)", 0x1529, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 G9 Turbo 250 HD", 0x1538, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 G9 Turbo", 0x1539, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 XS", 0x1548, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "70it2 (ID 1)", 0x1568, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "70it2 (ID 2)", 0x1569, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "70 Cobalt", 0x15ba, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "50c", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "C40", 0x31ab, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1824/ */
  { "Archos", 0x0e79, "50b", 0x31bd, DEVICE_FLAGS_ANDROID_BUGS },
  /* via libmtp-discuss Tonton <to.tonton@gmail.com> */
  { "Archos", 0x0e79, "Helium 45B", 0x31d8, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1393/ */
  { "Archos", 0x0e79, "Phone", 0x31e1, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1325/ */
  { "Archos", 0x0e79, "45 Neon", 0x31f3, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1352/ */
  { "Archos", 0x0e79, "50 Diamond", 0x3229, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/241 */
  { "Archos", 0x0e79, "50 Diamond (2nd ID)", 0x322a, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 G4", 0x4002, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos (for Tesco)", 0x0e79, "Hudl (ID1)", 0x5008, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos (for Tesco)", 0x0e79, "Hudl (ID2)", 0x5009, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1919/ */
  { "Archos", 0x0e79, "101d Neon", 0x51c6, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1404/ */
  { "Archos", 0x0e79, "AC40DTI", 0x5217, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/221/ */
  { "Archos", 0x0e79, "50 Helium Plus", 0x5229, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1682/ */
  { "Archos", 0x0e79, "50 Helium Plus (2nd ID)", 0x522a, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1573/ */
  { "Archos", 0x0e79, "101 xenon lite", 0x528c, DEVICE_FLAGS_ANDROID_BUGS },
  { "Archos", 0x0e79, "101 xenon lite (ADB)", 0x528d, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1581/ */
  { "Archos", 0x0e79, "40 Helium phone", 0x52c2, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/222/ */
  { "Archos", 0x0e79, "Diamond S", 0x5305, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1587/ */
  { "Archos", 0x0e79, "50d neon", 0x5371, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1660/ */
  { "Archos", 0x0e79, "70b neon", 0x5395, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/290/ */
  { "Archos", 0x0e79, "50 power", 0x53a7, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1637/ */
  { "Archos", 0x0e79, "101b Oxygen", 0x542f, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/245/ */
  { "Archos", 0x0e79, "55B Platinum", 0x544a, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1799/ */
  { "Archos", 0x0e79, "50F Helium", 0x545c, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/209/ */
  { "Archos", 0x0e79, "55 diamond Selfie", 0x5465, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/262/ */
  { "Archos", 0x0e79, "Core 50P", 0x5603, DEVICE_FLAGS_ANDROID_BUGS },


  /*
   * Dunlop (OEM of EGOMAN ltd?) reported by Nanomad
   * This unit is falsely detected as USB mass storage in Linux
   * prior to kernel 2.6.19 (fixed by patch from Alan Stern)
   * so on older kernels special care is needed to remove the
   * USB mass storage driver that erroneously binds to the device
   * interface.
   *
   * More problematic, this manufacturer+device ID seems to be
   * reused in a USB Mass Storage device named "Zipy Fox 8GB",
   * which means libmtp may mistreat it.
   */
  { "Dunlop", 0x10d6, "MP3 player 1GB / EGOMAN MD223AFD", 0x2200, DEVICE_FLAG_UNLOAD_DRIVER},
  // Reported by Steven Black <stevenblack1956@users.sourceforge.net>
  // Obviously this company goes by many names.
  // This device is USB 2.0 only. Broken pipe on closing.
  // A later report indicates that this is also used by the iRiver E200
  { "Memorex or iRiver", 0x10d6, "MMP 8585/8586 or iRiver E200", 0x2300,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_NO_RELEASE_INTERFACE},

  /*
   * Sirius
   */
  { "Sirius", 0x18f6, "Stiletto", 0x0102, DEVICE_FLAG_NONE },
  // Reported by Chris Bagwell <chris@cnpbagwell.com>
  { "Sirius", 0x18f6, "Stiletto 2", 0x0110, DEVICE_FLAG_NONE },

  /*
   * Nokia
   * Please verify the low device IDs here, I suspect these might be for
   * things like USB storage or modem mode actually, whereas the higher
   * range (0x04nn) could be for MTP. Some of the devices were gathered
   * from the Nokia WMP drivers:
   * http://nds2.nokia.com/files/support/global/phones/software/
   * Address was gathered from going to:
   * nseries.com
   * -> support
   * -> select supported device
   *  -> PC software
   *    -> Music software
   *      -> Windows Media Player 10 driver
   */
  // From: DoomHammer <gaczek@users.sourceforge.net>
  { "Nokia", 0x0421, "N81 Mobile Phone", 0x000a, DEVICE_FLAG_NONE },
  // From an anonymous SourceForge user
  { "Nokia", 0x0421, "6120c Classic Mobile Phone", 0x002e, DEVICE_FLAG_NONE },
  // From Stefano
  { "Nokia", 0x0421, "N96 Mobile Phone", 0x0039, DEVICE_FLAG_NONE },
  // From Martijn van de Streek <martijn@vandestreek.net>
  { "Nokia", 0x0421, "6500c Classic Mobile Phone", 0x003c, DEVICE_FLAG_NONE },
  // From: DoomHammer <gaczek@users.sourceforge.net>
  { "Nokia", 0x0421, "3110c Mobile Phone", 0x005f, DEVICE_FLAG_NONE },
  // From: Vasily <spc-@users.sourceforge.net>
  { "Nokia", 0x0421, "3109c Mobile Phone", 0x0065, DEVICE_FLAG_NONE },
  // From: <rawc@users.sourceforge.net>
  { "Nokia", 0x0421, "5310 XpressMusic", 0x006c, DEVICE_FLAG_NONE },
  // From: robin (AT) headbank D0Tco DOTuk
  { "Nokia", 0x0421, "N95 Mobile Phone 8GB", 0x006e, DEVICE_FLAG_NONE },
  // From Bastien Nocera <hadess@hadess.net>
  { "Nokia", 0x0421, "N82 Mobile Phone", 0x0074,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From Martijn van de Streek <martijn@vandestreek.net>
  { "Nokia", 0x0421, "N78 Mobile Phone", 0x0079, DEVICE_FLAG_NONE },
  // From William Pettersson <the_enigma@users.sourceforge.net>
  { "Nokia", 0x0421, "6220 Classic", 0x008d, DEVICE_FLAG_NONE },
  // From kellerkev@gmail.com
  { "Nokia", 0x0421, "N85 Mobile Phone", 0x0092, DEVICE_FLAG_NONE },
  // From Alexandre LISSY <lissyx@users.sourceforge.net>
  { "Nokia", 0x0421, "6210 Navigator", 0x0098, DEVICE_FLAG_NONE },
  // From: danielw
  { "Nokia", 0x0421, "E71", 0x00e4, DEVICE_FLAG_NONE },
  // From: Laurent Bigonville <bigon@users.sourceforge.net>
  { "Nokia", 0x0421, "E66", 0x00e5, DEVICE_FLAG_NONE },
  // From: Pier <pierlucalino@users.sourceforge.net>
  { "Nokia", 0x0421, "5320 XpressMusic", 0x00ea, DEVICE_FLAG_NONE },
  // From: Gausie <innerdreams@users.sourceforge.net>
  { "Nokia", 0x0421, "5800 XpressMusic", 0x0154,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // From: Willy Gardiol (web) <willy@gardiol.org>
  // Spurious errors for getting all objects, lead me to believe
  // this flag atleast is needed
  { "Nokia", 0x0421, "5800 XpressMusic v2", 0x0155,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Yet another version... I think
  { "Nokia", 0x0421, "5800 XpressMusic v3", 0x0159,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // From an anonymous SourceForge user
  // Not verified to be MTP
  { "Nokia", 0x0421, "E63", 0x0179, DEVICE_FLAG_NONE },
  // Reported by: max g <exactt@users.sourceforge.net>
  // Reported by: oswillios <loswillios@users.sourceforge.net>
  { "Nokia", 0x0421, "N79", 0x0186, DEVICE_FLAG_NONE },
  // From an anonymous SourceForge user
  { "Nokia", 0x0421, "E71x", 0x01a1, DEVICE_FLAG_NONE },
  // From Ser <ser@users.sourceforge.net>
  { "Nokia", 0x0421, "E52", 0x01cf, DEVICE_FLAG_NONE },
  // From Marcus Meissner
  { "Nokia", 0x0421, "3710", 0x01ee, DEVICE_FLAG_NONE },
  // From: AxeL <axel__17@users.sourceforge.net>
  { "Nokia", 0x0421, "N97-1", 0x01f4, DEVICE_FLAG_NONE },
  // From: FunkyPenguin <awafaa@users.sourceforge.net>
  { "Nokia", 0x0421, "N97", 0x01f5, DEVICE_FLAG_NONE },
  // From: Anonymous SourceForge user
  { "Nokia", 0x0421, "5130 XpressMusic", 0x0209, DEVICE_FLAG_NONE },
  // From: Anonymous SourceForge user
  { "Nokia", 0x0421, "E72", 0x0221, DEVICE_FLAG_NONE },
  // From: Anonymous SourceForge user
  { "Nokia", 0x0421, "5530", 0x0229, DEVICE_FLAG_NONE },
  /* Grzegorz Woźniak <wozniakg@gmail.com> */
  { "Nokia", 0x0421, "E6", 0x032f, DEVICE_FLAG_NONE },
  // From: Anonymous SourceForge user
  { "Nokia", 0x0421, "N97 mini", 0x026b, DEVICE_FLAG_NONE },
  // From: Anonymous SourceForge user
  { "Nokia", 0x0421, "X6", 0x0274, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // From: Alexander Kojevnikov <alex-kay@users.sourceforge.net>
  { "Nokia", 0x0421, "6600i", 0x0297, DEVICE_FLAG_NONE },
  // From: Karthik Paithankar <whyagain2005@users.sourceforge.net>
  { "Nokia", 0x0421, "2710", 0x02c1, DEVICE_FLAG_NONE },
  // From: Mick Stephenson <MickStep@users.sourceforge.net>
  { "Nokia", 0x0421, "5230", 0x02e2, DEVICE_FLAG_NONE },
  // From: Lan Liu at Nokia <lan.liu@nokia.com>
  { "Nokia", 0x0421, "N8", 0x02fe, DEVICE_FLAG_NONE },
  // From: Lan Liu at Nokia <lan.liu@nokia.com>
  { "Nokia", 0x0421, "N8 (Ovi mode)", 0x0302, DEVICE_FLAG_NONE },
  // From: Martijn Hoogendoorn <m.hoogendoorn@gmail.com>
  { "Nokia", 0x0421, "E7", 0x0334, DEVICE_FLAG_NONE },
  // From: Raul Metsma <raul@innovaatik.ee>
  { "Nokia", 0x0421, "E7 (Ovi mode)", 0x0335, DEVICE_FLAG_NONE },
  // Reported by Serg <rd77@users.sourceforge.net>
  // Symbian phone
  { "Nokia", 0x0421, "C7", 0x03c1, DEVICE_FLAG_NONE },
  // Reported by Anonymous SourceForge user
  { "Nokia", 0x0421, "C7 (ID2)", 0x03cd, DEVICE_FLAG_NONE },
  // Reported by Anonymous SourceForge user
  { "Nokia", 0x0421, "N950", 0x03d2, DEVICE_FLAG_NONE },
  // From: http://nds2.nokia.com/files/support/global/phones/software/Nokia_3250_WMP10_driver.inf
  { "Nokia", 0x0421, "3250 Mobile Phone", 0x0462, DEVICE_FLAG_NONE },
  // From http://nds2.nokia.com/files/support/global/phones/software/Nokia_N93_WMP10_Driver.inf
  { "Nokia", 0x0421, "N93 Mobile Phone", 0x0478, DEVICE_FLAG_NONE },
  // From: http://nds2.nokia.com/files/support/global/phones/software/Nokia_5500_Sport_WMP10_driver.inf
  { "Nokia", 0x0421, "5500 Sport Mobile Phone", 0x047e, DEVICE_FLAG_NONE },
  // From http://nds2.nokia.com/files/support/global/phones/software/Nokia_N91_WMP10_Driver.inf
  { "Nokia", 0x0421, "N91 Mobile Phone", 0x0485, DEVICE_FLAG_NONE },
  // From: Christian Rusa <kristous@users.sourceforge.net>
  { "Nokia", 0x0421, "5700 XpressMusic Mobile Phone", 0x04b4, DEVICE_FLAG_NONE },
  // From: Mitchell Hicks <mitchix@yahoo.com>
  { "Nokia", 0x0421, "5300 Mobile Phone", 0x04ba, DEVICE_FLAG_NONE },
  // https://sourceforge.net/tracker/index.php?func=detail&aid=2692473&group_id=8874&atid=358874
  // From: Tiburce <tiburce@users.sourceforge.net>
  { "Nokia", 0x0421, "5200 Mobile Phone", 0x04be,
      DEVICE_FLAG_BROKEN_BATTERY_LEVEL },
  // From Christian Arnold <webmaster@arctic-media.de>
  { "Nokia", 0x0421, "N73 Mobile Phone", 0x04d1, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Swapan <swapan@yahoo.com>
  { "Nokia", 0x0421, "N75 Mobile Phone", 0x04e1, DEVICE_FLAG_NONE },
  // From: http://nds2.nokia.com/files/support/global/phones/software/Nokia_N93i_WMP10_driver.inf
  { "Nokia", 0x0421, "N93i Mobile Phone", 0x04e5, DEVICE_FLAG_NONE },
  // From Anonymous Sourceforge User
  { "Nokia", 0x0421, "N95 Mobile Phone", 0x04ef, DEVICE_FLAG_NONE },
  // From: Pat Nicholls <pat@patandannie.co.uk>
  { "Nokia", 0x0421, "N80 Internet Edition (Media Player)", 0x04f1,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // From: Maxin B. John <maxin.john@gmail.com>
  { "Nokia", 0x0421, "N9", 0x051a, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1308/ */
  { "Nokia", 0x0421, "N300", 0x0524, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1885/ */
  { "Nokia", 0x0421, "701", 0x0530, DEVICE_FLAG_NONE },
  { "Nokia", 0x0421, "C5-00", 0x0592, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1457/ */
  { "Nokia", 0x0421, "C5-00 (ID2)", 0x0595, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/235/ */
  { "Nokia", 0x0421, "500", 0x05c0, DEVICE_FLAG_NONE },
  { "Nokia", 0x0421, "808 PureView", 0x05d3, DEVICE_FLAG_NONE },
  // Reported by Sampo Savola
  // Covers Lumia 920, 820 and probably any WP8 device.
  { "Nokia", 0x0421, "Lumia WP8", 0x0661, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1176/ */
  { "Nokia", 0x0421, "Lumia 301", 0x0666, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/146/ */
  { "Nokia", 0x0421, "XL", 0x06e8, DEVICE_FLAG_UNLOAD_DRIVER },
  /* https://sourceforge.net/p/libmtp/patches/69/
   * https://sourceforge.net/p/libmtp/bugs/1285/
   * ID is the same for various Lumia version.
   */
  { "Nokia", 0x0421, "Lumia (RM-975)", 0x06fc, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1453/ */
  { "Nokia", 0x0421, "X2 Dual Sim", 0x0708, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/bugs/1711/ */
  { "Nokia", 0x2e04, "6", 0xc025, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1783/ */
  { "Nokia", 0x2e04, "6.1", 0xc026, DEVICE_FLAGS_ANDROID_BUGS },
  /* ndim from gphoto */
  { "Nokia", 0x2e04, "6.2", 0xc02a, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Qualcomm
   * This vendor ID seems to be used a bit by others.
   */

  // Reported by Richard Wall <richard@the-moon.net>
  { "Qualcomm (for Nokia)", 0x05c6, "5530 Xpressmusic", 0x0229,
      DEVICE_FLAG_NONE },
  // One thing stated by reporter (Nokia model) another by the detect log...
  { "Qualcomm (for Nokia/Verizon)", 0x05c6, "6205 Balboa/Verizon Music Phone",
      0x3196, DEVICE_FLAG_NONE },
  { "Qualcomm (for Gigabyte)", 0x05c6, "GSmart G1342",
      0x8800, DEVICE_FLAG_NONE },
  { "Qualcomm (for Smartfren)", 0x05c6, "Andromax U",
      0x9025, DEVICE_FLAG_NONE },
  // New Android phone of the OnePlus brand : the One model
  { "Qualcomm (for OnePlus)", 0x05c6, "One (MTP)",
      0x6764, DEVICE_FLAGS_ANDROID_BUGS },
  { "Qualcomm (for OnePlus)", 0x05c6, "One (MTP+ADB)",
      0x6765, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1377/ */
  /* https://github.com/libmtp/libmtp/issues/44 */
  { "Qualcomm (for Xolo)", 0x05c6, "Xolo Black (MTP)",
      0x901b, DEVICE_FLAGS_ANDROID_BUGS },

  { "Qualcomm (for PhiComm)", 0x05c6, "C230w (MTP)",
      0x9039, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://github.com/libmtp/libmtp/issues/78 */
  { "OnePlus", 0x05c6, "OnePlus 7Pro (MTP)",
      0xf000, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1513/ */
  { "Qualcomm (for OnePlus)", 0x05c6, "One Plus 2 (A2003) (MTP)",
      0xf003, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1284/ */
  { "Qualcomm (for Highscreen)", 0x05c6, "Omega Prime S",
      0xf003, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Vendor ID 0x13d1 is some offshoring company in China,
   * in one source named "A-Max Technology Macao Commercial
   * Offshore Co. Ltd." sometime "CCTech".
   */
  // Logik brand
  { "Logik", 0x13d1, "LOG DAX MP3 and DAB Player", 0x7002, DEVICE_FLAG_UNLOAD_DRIVER },
  // Technika brand
  // Reported by <Ooblick@users.sourceforge.net>
  { "Technika", 0x13d1, "MP-709", 0x7017, DEVICE_FLAG_UNLOAD_DRIVER },


  /*
   * RCA / Thomson
   */
  // From kiki <omkiki@users.sourceforge.net>
  { "Thomson", 0x069b, "EM28 Series", 0x0774, DEVICE_FLAG_NONE },
  { "Thomson / RCA", 0x069b, "Opal / Lyra MC4002", 0x0777, DEVICE_FLAG_NONE },
  { "Thomson", 0x069b, "Lyra MC5104B (M51 Series)", 0x077c, DEVICE_FLAG_NONE },
  { "Thomson", 0x069b, "RCA H106", 0x301a, DEVICE_FLAG_UNLOAD_DRIVER },
  // From Svenna <svenna@svenna.de>
  // Not confirmed to be MTP.
  { "Thomson", 0x069b, "scenium E308", 0x3028, DEVICE_FLAG_NONE },
  // From XNJB user
  { "Thomson / RCA", 0x069b, "Lyra HC308A", 0x3035, DEVICE_FLAG_NONE },

  /*
   * Fujitsu devices
   */
  { "Fujitsu, Ltd", 0x04c5, "F903iX HIGH-SPEED", 0x1140, DEVICE_FLAG_NONE },
  // Reported by Thomas Bretthauer
  { "Fujitsu, Ltd", 0x04c5, "STYLISTIC M532", 0x133b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/137/ */
  { "Fujitsu, Ltd", 0x04c5, "F02-E", 0x1378,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1495/ */
  { "Fujitsu, Ltd", 0x04c5, "Arrows 202F", 0x13dd,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Palm device userland program named Pocket Tunes
   * Reported by Peter Gyongyosi <gyp@impulzus.com>
   */
  { "NormSoft, Inc.", 0x1703, "Pocket Tunes", 0x0001, DEVICE_FLAG_NONE },
  // Reported by anonymous submission
  { "NormSoft, Inc.", 0x1703, "Pocket Tunes 4", 0x0002, DEVICE_FLAG_NONE },

  /*
   * TrekStor, Medion and Maxfield devices
   * Their datasheet claims their devices are dualmode so probably needs to
   * unload the attached drivers here.
   */
  // Reported by Stefan Voss <svoss@web.de>
  // This is a Sigmatel SoC with a hard disk.
  { "TrekStor", 0x066f, "Vibez 8/12GB", 0x842a,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by anonymous SourceForge user.
  // This one done for Medion, whatever that is. Error reported so assume
  // the same bug flag as its ancestor above.
  { "Medion", 0x066f, "MD8333 (ID1)", 0x8550,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by anonymous SourceForge user
  { "Medion", 0x066f, "MD8333 (ID2)", 0x8588,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  /* https://sourceforge.net/p/libmtp/bugs/1359/ */
  { "Verizon", 0x0408, "Ellipsis 7", 0x3899,
    DEVICE_FLAGS_ANDROID_BUGS },
  // The vendor ID is "Quanta Computer, Inc."
  // same as Olivetti Olipad 110
  // Guessing on device flags
  { "Medion", 0x0408, "MD99000 (P9514)/Olivetti Olipad 110", 0xb009,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Richard Eigenmann <richieigenmann@users.sourceforge.net>
  { "Medion", 0x0408, "Lifetab P9514", 0xb00a,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous SourceForge user
  { "Maxfield", 0x066f, "G-Flash NG 1GB", 0x846c,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by PaoloC <efmpsc@users.sourceforge.net>
  // Apparently SigmaTel has an SDK for MTP players with this ID
  { "SigmaTel Inc.", 0x066f, "MTPMSCN Audio Player", 0xa010,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Cristi Magherusan <majeru@gentoo.ro>
  { "TrekStor", 0x0402, "i.Beat Sweez FM", 0x0611,
    DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Fox-ino <fox-ino@users.sourceforge.net>
  // No confirmation that this is really MTP so commented it out.
  // { "ALi Corp.", 0x0402, "MPMAN 2GB", 0x5668,
  // DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Anonymous SourceForge user
  {"TrekStor", 0x1e68, "i.Beat Organix 2.0", 0x0002,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },

  /* Also Thalia Toline. https://sourceforge.net/p/libmtp/bugs/1156/ */
  {"iRiver", 0x1e68, "Tolino Tab 7", 0x1002,
    DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1694/ */
  {"iRiver", 0x1e68, "Tolino Tab 8", 0x1007,
    DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1699/ */
  {"Trekstor", 0x1e68, "SurfTab breeze 7.0 quad 3G", 0x1045,
    DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Disney/Tevion/MyMusix
   */
  // Reported by XNJB user
  { "Disney", 0x0aa6, "MixMax", 0x6021, DEVICE_FLAG_NONE },
  // Reported by anonymous Sourceforge user
  { "Tevion", 0x0aa6, "MD 81488", 0x3011, DEVICE_FLAG_NONE },
  // Reported by Peter Hedlund <peter@peterandlinda.com>
  { "MyMusix", 0x0aa6, "PD-6070", 0x9601, DEVICE_FLAG_UNLOAD_DRIVER |
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST |
    DEVICE_FLAG_NO_RELEASE_INTERFACE },

  /*
   * Cowon Systems, Inc.
   * The iAudio audiophile devices don't encourage the use of MTP.
   * See: http://wiki.xiph.org/index.php/PortablePlayers for Ogg
   * status
   */
  // Reported by Patrik Johansson <Patrik.Johansson@qivalue.com>
  { "Cowon", 0x0e21, "iAudio U3 (MTP mode)", 0x0701,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by Kevin Michael Smith <hai-etlik@users.sourceforge.net>
  { "Cowon", 0x0e21, "iAudio 6 (MTP mode)", 0x0711,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Roberth Karman
  { "Cowon", 0x0e21, "iAudio 7 (MTP mode)", 0x0751,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by an anonymous SourceForge user
  { "Cowon", 0x0e21, "iAudio U5 (MTP mode)", 0x0761,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by TJ Something <tjbk_tjb@users.sourceforge.net>
  { "Cowon", 0x0e21, "iAudio D2 (MTP mode)", 0x0801,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by anonymous Sourceforge user
  { "Cowon", 0x0e21, "iAudio D2+ FW 2.x (MTP mode)", 0x0861,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // From Rockbox device listing
  { "Cowon", 0x0e21, "iAudio D2+ DAB FW 4.x (MTP mode)", 0x0871,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // From Rockbox device listing
  { "Cowon", 0x0e21, "iAudio D2+ FW 3.x (MTP mode)", 0x0881,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // From Rockbox device listing
  { "Cowon", 0x0e21, "iAudio D2+ DMB FW 1.x (MTP mode)", 0x0891,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by <twkonefal@users.sourceforge.net>
  { "Cowon", 0x0e21, "iAudio S9 (MTP mode)", 0x0901,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by Dan Nicholson <dbn.lists@gmail.com>
  { "Cowon", 0x0e21, "iAudio 9 (MTP mode)", 0x0911,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by Franck VDL <franckv@users.sourceforge.net>
  { "Cowon", 0x0e21, "iAudio J3 (MTP mode)", 0x0921,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by anonymous SourceForge user
  { "Cowon", 0x0e21, "iAudio X7 (MTP mode)", 0x0931,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  // Reported by anonymous SourceForge user
  { "Cowon", 0x0e21, "iAudio C2 (MTP mode)", 0x0941,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },
  { "Cowon", 0x0e21, "iAudio 10 (MTP mode)", 0x0952,
   DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
   DEVICE_FLAG_OGG_IS_UNKNOWN | DEVICE_FLAG_FLAC_IS_UNKNOWN },

  /*
   * Insignia, dual-mode.
   */
  { "Insignia", 0x19ff, "NS-DV45", 0x0303, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Rajan Bella <rajanbella@yahoo.com>
  { "Insignia", 0x19ff, "Sport Player", 0x0307, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by "brad" (anonymous, sourceforge)
  { "Insignia", 0x19ff, "Pilot 4GB", 0x0309, DEVICE_FLAG_UNLOAD_DRIVER },

  /*
   * LG Electronics
   */
  // Uncertain if this is really the MTP mode device ID...
  { "LG Electronics Inc.", 0x043e, "T54", 0x7040,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Not verified - anonymous submission
  { "LG Electronics Inc.", 0x043e, "UP3", 0x70b1, DEVICE_FLAG_NONE },
  // Reported by Joseph Nahmias <joe@nahimas.net>
  { "LG Electronics Inc.", 0x1004, "VX8550 V CAST Mobile Phone", 0x6010,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR },
  // Reported by Cyrille Potereau <cyrille.potereau@wanadoo.fr>
  { "LG Electronics Inc.", 0x1004, "KC910 Renoir Mobile Phone", 0x608f,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Aaron Slunt <tongle@users.sourceforge.net>
  { "LG Electronics Inc.", 0x1004, "GR-500 Music Player", 0x611b,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_ALWAYS_PROBE_DESCRIPTOR },
  { "LG Electronics Inc.", 0x1004, "KM900", 0x6132,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER },
  { "LG Electronics Inc.", 0x1004, "LG8575", 0x619a,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER },
  /*
   * These two are LG Android phones:
   * LG-F6
   * V909 G-Slate
   */
  { "LG Electronics Inc.", 0x1004, "Android phone (ID1)", 0x61f1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "LG Electronics Inc.", 0x1004, "Android phone (ID2)", 0x61f9,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1007/ */
  { "LG Electronics Inc.", 0x1004, "LG VS980", 0x621c,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "LG Electronics Inc.", 0x1004, "LG2 Optimus", 0x6225,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1386/ */
  { "LG Electronics Inc.", 0x1004, "LG VS950", 0x622a,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "LG Electronics Inc.", 0x1004, "LG VS870", 0x6239,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/992/ */
  { "LG Electronics Inc.", 0x1004, "LG VS890", 0x623d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/190/ */
  { "LG Electronics Inc.", 0x1004, "LG Optimus Zone 2", 0x6259,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1463/ */
  { "LG Electronics Inc.", 0x1004, "810 tablet", 0x6263,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "LG Electronics Inc.", 0x1004, "VK810", 0x6265,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/134/ */
  { "LG Electronics Inc.", 0x1004, "G3 (VS985)", 0x626e,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "LG Electronics Inc.", 0x1004, "G3", 0x627f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1701/ */
  { "LG Electronics Inc.", 0x1004, "Transpyre", 0x628a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/290/ */
  { "LG Electronics Inc.", 0x1004, "LG G6 Phone", 0x62c9,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/222/ */
  { "LG Electronics Inc.", 0x1004, "LG G5 Phone", 0x62ce,
      DEVICE_FLAGS_ANDROID_BUGS },
  /*
   * This VID+PID is used by a lot of LG models:
   * E430
   * E460
   * E610
   * E612
   * E617G
   * E970
   * P700
   */
  { "LG Electronics Inc.", 0x1004, "Various E and P models", 0x631c,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1294/ */
  { "LG Electronics Inc.", 0x1004, "LG G Flex 2", 0x633e,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/280/ */
  { "LG Electronics Inc.", 0x1004, "LG G3 f460s", 0x633f,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Sony
   * It could be that these PIDs are one-per hundred series, so
   * NWZ-A8xx is 0325, NWZ-S5xx is 0x326 etc. We need more devices
   * reported to see a pattern here.
   */
  // Reported by Alessandro Radaelli <alessandro.radaelli@aruba.it>
  { "Sony", 0x054c, "NWZ-A815/NWZ-A818", 0x0325,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by anonymous Sourceforge user.
  { "Sony", 0x054c, "NWZ-S516", 0x0326,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Endre Oma <endre.88.oma@gmail.com>
  { "Sony", 0x054c, "NWZ-S615F/NWZ-S616F/NWZ-S618F", 0x0327,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Jean-Marc Bourguet <jm@bourguet.org>
  { "Sony", 0x054c, "NWZ-S716F", 0x035a,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Anon SF User / Anthon van der Neut <avanderneut@avid.com>
  { "Sony", 0x054c, "NWZ-A826/NWZ-A828/NWZ-A829", 0x035b,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Niek Klaverstijn <niekez@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-A726/NWZ-A728/NWZ-A768", 0x035c,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Mehdi AMINI <mehdi.amini - at - ulp.u-strasbg.fr>
  { "Sony", 0x054c, "NWZ-B135", 0x036e,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by <tiagoboldt@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-E436F", 0x0385,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Michael Wilkinson
  { "Sony", 0x054c, "NWZ-W202", 0x0388,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Ondrej Sury <ondrej@sury.org>
  { "Sony", 0x054c, "NWZ-S739F", 0x038c,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Marco Filipe Nunes Soares Abrantes Pereira <marcopereira@ua.pt>
  { "Sony", 0x054c, "NWZ-S638F", 0x038e,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Elliot <orwells@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-X1050B/NWZ-X1060B",
    0x0397, DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Silvio J. Gutierrez <silviogutierrez@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-X1051/NWZ-X1061", 0x0398,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Gregory Boddin <gregory@siwhine.net>
  { "Sony", 0x054c, "NWZ-B142F", 0x03d8,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Rick Warner <rick@reptileroom.net>
  { "Sony", 0x054c, "NWZ-E344/E345", 0x03fc,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Jonathan Stowe <gellyfish@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-E445", 0x03fd,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Anonymous SourceForge user
  { "Sony", 0x054c, "NWZ-S545", 0x03fe,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "NWZ-A845", 0x0404,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by anonymous SourceForge user
  { "Sony", 0x054c, "NWZ-W252B", 0x04bb,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Suspect this device has strong DRM features
  // See https://answers.launchpad.net/ubuntu/+source/libmtp/+question/149587
  { "Sony", 0x054c, "NWZ-B153F", 0x04be,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "NWZ-E354", 0x04cb,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Toni Burgarello
  { "Sony", 0x054c, "NWZ-S754", 0x04cc,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Hideki Yamane <henrich@debian.org>
  { "Sony", 0x054c, "Sony Tablet P1", 0x04d1,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by dmiceman
  { "Sony", 0x054c, "NWZ-B163F", 0x059a,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "NWZ-E464", 0x05a6,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Jan Rheinlaender <jrheinlaender@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-S765", 0x05a8,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Olivier Keshavjee <olivierkes@users.sourceforge.net>
  { "Sony", 0x054c, "Sony Tablet S", 0x05b3,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by ghalambaz <ghalambaz@users.sourceforge.net>
  { "Sony", 0x054c, "Sony Tablet S1", 0x05b4,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Sony", 0x054c, "NWZ-B173F", 0x0689,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1540/ */
  { "Sony", 0x054c, "NWZ-E474", 0x06a9,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "Xperia Tablet S - SGPT12", 0x06ac,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1688/ */
  { "Sony", 0x054c, "NWZ-E384", 0x0882,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  /* hartmut001@users.sourceforge.net */
  { "Sony", 0x054c, "NW-A45 Walkman", 0x0c71,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  /* https://github.com/libmtp/libmtp/issues/81 */
  { "Sony", 0x054c, "NW-ZX500", 0x0d01,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "DCR-SR75", 0x1294,
      DEVICE_FLAGS_SONY_NWZ_BUGS },

  /*
   * SonyEricsson
   * These initially seemed to support GetObjPropList but later revisions
   * of the firmware seem to have broken it, so all are flagged as broken
   * for now.
   */
  // Reported by Øyvind Stegard <stegaro@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "K850i", 0x0075,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Michael Eriksson
  { "SonyEricsson", 0x0fce, "W910", 0x0076,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Zack <zackdvd@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "W890i", 0x00b3,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by robert dot ahlskog at gmail
  { "SonyEricsson", 0x0fce, "W760i", 0x00c6,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Linus Åkesson <linusakesson@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "C902", 0x00d4,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by an anonymous SourceForge user
  { "SonyEricsson", 0x0fce, "C702", 0x00d9,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Christian Zuckschwerdt <christian@zuckschwerdt.org>
  { "SonyEricsson", 0x0fce, "W980", 0x00da,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by David Taylor <davidt-libmtp@yadt.co.uk>
  { "SonyEricsson", 0x0fce, "C905", 0x00ef,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by David House <dmhouse@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "W595", 0x00f3,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST },
  // Reported by Mattias Evensson <mevensson@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "W902", 0x00f5,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Sarunas <sarunas@users.sourceforge.net>
  // Doesn't need any flags according to reporter
  { "SonyEricsson", 0x0fce, "T700", 0x00fb,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by Stéphane Pontier <shadow_walker@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "W705/W715", 0x0105,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Håkan Kvist
  { "SonyEricsson", 0x0fce, "W995", 0x0112,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by anonymous SourceForge user
  { "SonyEricsson", 0x0fce, "U5", 0x0133,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Flo <lhugsereg@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "U8i", 0x013a,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by xirotyu <xirotyu@users.sourceforge.net>
  { "SonyEricsson", 0x0fce,  "j10i2 (Elm)", 0x0144,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Serge Chirik <schirik@users.sourceforge.net>
  { "SonyEricsson", 0x0fce,  "j108i (Cedar)", 0x014e,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Jonas Nyrén <spectralmks@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "W302", 0x10c8,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Anonymous Sourceforge user
  { "SonyEricsson", 0x0fce,  "j10i (Elm)", 0xd144,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Thomas Schweitzer <thomas_-_s@users.sourceforge.net>
  { "SonyEricsson", 0x0fce, "K550i", 0xe000,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },

  /*
   * SonyEricsson/SONY Android devices usually have three personalities due to
   * using composite descriptors and the fact that Windows cannot distinguish
   * the device unless each composite descriptor is unique.
   *
   * Legend:
   * MTP = Media Transfer Protocol
   * UMS = USB Mass Storage Protocol
   * ADB = Android Debug Bridge Protocol
   * CDC = Communications Device Class, Internet Sharing
   *
   * 0x0nnn = MTP
   * 0x4nnn = MTP + UMS (for CD-ROM)
   * 0x5nnn = MTP + ADB
   * 0x6nnn = UMS + ADB
   * 0x7nnn = MTP + CDC
   * 0x8nnn = MTP + CDC + ADB
   * 0xannn = MTP + UMS (MTP for eMMC and UMS for external SD card)
   * 0xbnnn = MTP + UMS + ADB
   * 0xennn = UMS only
   *
   * The SonyEricsson and SONY devices have (at least) two deployed MTP
   * stacks: Aricent and Android. These have different bug flags, and
   * sometimes the same device has firmware upgrades moving it from
   * the Aricent to Android MTP stack without changing the device
   * VID+PID (first observed on the SK17i Xperia Mini Pro), so the
   * detection has to be more elaborate. The code in libmtp.c will do
   * this and assign the proper bug flags (hopefully).
   * That is why DEVICE_FLAG_NONE is used for these devices.
   *
   * Devices reported by:
   * Sony Mobile Communications (via Toby Collett)
   * Jonas Salling
   * Eamonn Webster <eweb@users.sourceforge.net>
   * Alejandro DC <Alejandro_DC@users.sourceforge.ne>
   * StehpanKa <stehp@users.sourceforge.net>
   * hdhoang <hdhoang@users.sourceforge.net>
   * Paul Taylor
   * Bruno Basilio <bbasilio@users.sourceforge.net>
   * Christoffer Holmstedt <christofferh@users.sourceforge.net>
   * equaeghe <equaeghe@users.sourceforge.net>
   * Ondra Lengal
   * Michael K. <kmike@users.sourceforge.net>
   * Jean-François  B. <changi67@users.sourceforge.net>
   * Eduard Bloch <blade@debian.org>
   * Ah Hong <hongster@users.sourceforge.net>
   * Eowyn Carter
   */
  { "SonyEricsson", 0x0fce,  "c1605 Xperia Dual E MTP", 0x0146,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "LT15i Xperia arc S MTP", 0x014f,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "MT11i Xperia Neo MTP", 0x0156,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "IS12S Xperia Acro MTP", 0x0157,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "MK16i Xperia MTP", 0x015a,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "R800/R88i Xperia Play MTP", 0x015d,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST18a Xperia Ray MTP", 0x0161,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "SK17i Xperia Mini Pro MTP", 0x0166,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST15i Xperia Mini MTP", 0x0167,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST17i Xperia Active MTP", 0x0168,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26i Xperia S MTP", 0x0169,
      DEVICE_FLAG_NO_ZERO_READS },
  { "SONY", 0x0fce, "WT19i Live Walkman MTP", 0x016d,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST21i Xperia Tipo MTP", 0x0170,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST15i Xperia U MTP", 0x0171,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT22i Xperia P MTP", 0x0172,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "MT27i Xperia Sola MTP", 0x0173,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26w Xperia Acro HD IS12S MTP", 0x0175,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26w Xperia Acro HD SO-03D MTP", 0x0176,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT28at Xperia Ion MTP", 0x0177,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT29i Xperia GX MTP", 0x0178,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST27i/ST27a Xperia go MTP", 0x017e,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST23i Xperia Miro MTP", 0x0180,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "SO-05D Xperia SX MTP", 0x0181,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT30p Xperia T MTP", 0x0182,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT25i Xperia V MTP", 0x0186,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia J MTP", 0x0188,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia ZL MTP", 0x0189,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia E MTP", 0x018c,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Tablet Z MTP 1", 0x018d,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia L MTP", 0x0192,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z MTP", 0x0193,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Tablet Z MTP 2", 0x0194,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia SP MTP", 0x0195,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP (ID2)", 0x0196,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia ZR MTP", 0x0197,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia A MTP", 0x0198,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia M MTP", 0x019b,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP (ID3)", 0x019c,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z1 MTP", 0x019e,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia C MTP", 0x01a3,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z1 Compact D5503", 0x01a7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia T2 Ultra MTP", 0x01a9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 MTP", 0x01aa,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 Dual MTP", 0x01ab,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z2 MTP", 0x01af,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3v MTP", 0x01b0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z2 Tablet MTP", 0x01b1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia E1 MTP", 0x01b5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP", 0x01b6,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia M2 Aqua MTP", 0x01b8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z3 MTP", 0x01ba,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3 Compact MTP", 0x01bb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia E3 MTP", 0x01bc,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3 Tablet MTP", 0x01c0,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria M4 Aqua Dual MTP", 0x01c4,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "E2115 MTP", 0x01c5,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z3+ MTP", 0x01c9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria E4g MTP", 0x01cb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "C4 Dual MTP", 0x01d2,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria M5 MTP", 0x01d6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 MTP", 0x01d9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 Compact MTP", 0x01da,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/236/ */
  { "SONY", 0x0fce, "XPeria Z5 Premium Dual Sim MTP", 0x01db,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1649/ */
  { "SONY", 0x0fce, "XPeria XA MTP", 0x01de,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria X MTP", 0x01e0,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/251/ */
  { "SONY", 0x0fce, "XPeria SOV33", 0x01e1,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ MTP", 0x01e7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria X Compact MTP", 0x01e8,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/252/ */
  { "SONY", 0x0fce, "XPeria G3123", 0x01eb,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/247/ */
  { "SONY", 0x0fce, "XPeria XZ", 0x01ed,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1812/ */
  { "SONY", 0x0fce, "XPeria XA1 Ultra", 0x01ef,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/251/ */
  { "SONY", 0x0fce, "XPeria XZ Premium", 0x01f1,
      DEVICE_FLAG_NONE },
  /* Nicholas O'Connor <lavacano@lavacano.net> on libmtp-discuss */
  { "SONY", 0x0fce, "XPeria XZ1", 0x01f3,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/252/ */
  { "SONY", 0x0fce, "XPeria XZ1 Compact", 0x01f4,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/281/ */
  { "SONY", 0x0fce, "XPeria L2", 0x01f6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA2 Compact", 0x01f7,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/285/ */
  { "SONY", 0x0fce, "XPeria XA2 Ultra", 0x01f8,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1804/ */
  { "SONY", 0x0fce, "Xperia XZ2 Compact Dual Sim", 0x01f9,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1775/ */
  { "SONY", 0x0fce, "Xperia XZ2 (H8266)", 0x01fa,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1854/ */
  { "SONY", 0x0fce, "Xperia XZ2 Premium", 0x01fb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ3 Dual Sim (H9436)", 0x01ff,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1853/ */
  { "SONY", 0x0fce, "Xperia 10 (I4113)", 0x0201,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1859/ */
  { "SONY", 0x0fce, "Xperia 1 (J9110)", 0x0205,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1849/ */
  { "SONY", 0x0fce, "Xperia I4312", 0x0207,
      DEVICE_FLAG_NONE },
  /* https://github.com/libmtp/libmtp/issues/113 */
  { "SONY", 0x0fce, "Xperia 5", 0x020a,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/feature-requests/303/ */
  { "SONY", 0x0fce, "Xperia 5 II Phone", 0x020d,
      DEVICE_FLAG_NONE },

  /* https://bugs.kde.org/show_bug.cgi?id=387454 ... probably not in the ADB/CDROM method? */
  { "SONY", 0x0fce, "Xperia XA2 (Jolla Sailfish)", 0x0a07,
      DEVICE_FLAG_NONE },

  /*
   * MTP+UMS personalities of MTP devices (see above)
   */
  { "SonyEricsson", 0x0fce, "IS12S Xperia Acro MTP+CDROM", 0x4157,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST17i Xperia Active MTP+CDROM", 0x4168,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26i Xperia S MTP+CDROM", 0x4169,
      DEVICE_FLAG_NO_ZERO_READS },
  { "SONY", 0x0fce, "ST21i Xperia Tipo MTP+CDROM", 0x4170,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST25i Xperia U MTP+CDROM", 0x4171,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT22i Xperia P MTP+CDROM", 0x4172,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "MT27i Xperia Sola MTP+CDROM", 0x4173,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26w Xperia Acro HD IS12S MTP+CDROM", 0x4175,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26w Xperia Acro HD SO-03D MTP+CDROM", 0x4176,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT28at Xperia Ion MTP+CDROM", 0x4177,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT29i Xperia GX MTP+CDROM", 0x4178,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST27i/ST27a Xperia go MTP+CDROM", 0x417e,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST23i Xperia Miro MTP+CDROM", 0x4180,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "SO-05D Xperia SX MTP+CDROM", 0x4181,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT30p Xperia T MTP+CDROM", 0x4182,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT25i Xperia V MTP+CDROM", 0x4186,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia J MTP+CDROM", 0x4188,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia ZL MTP+CDROM", 0x4189,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia E MTP+CDROM", 0x418c,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Tablet Z MTP+CDROM 1", 0x418d,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia L MTP+CDROM", 0x4192,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z MTP+CDROM", 0x4193,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Tablet Z MTP+CDROM 2", 0x4194,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia SP MTP+CDROM", 0x4195,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M MTP+CDROM", 0x419b,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP+CDROM (ID3)", 0x419c,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z1 MTP+CDROM", 0x419e,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia C MTP+CDROM", 0x41a3,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z1 Compact D5503 MTP+CDROM", 0x41a7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia T2 Ultra MTP+CDROM", 0x41a9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 MTP+CDROM", 0x41aa,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 Dual MTP+CDROM", 0x41ab,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z2 MTP+CDROM", 0x41af,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3v MTP+CDROM", 0x41b0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z2 Tablet MTP+CDROM", 0x41b1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia E1 MTP+CDROM", 0x41b5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP+CDROM", 0x41b6,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia M2 Aqua MTP+CDROM", 0x41b8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z3 MTP+CDROM", 0x41ba,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3 Compact MTP+CDROM", 0x41bb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia E3 MTP+CDROM", 0x41bc,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3 Tablet MTP+CDROM", 0x41c0,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria M4 Aqua Dual MTP+CDROM", 0x41c4,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "E2115 MTP+CDROM", 0x41c5,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z3+ MTP+CDROM", 0x41c9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria E4g MTP+CDROM", 0x41cb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "C4 Dual MTP+CDROM", 0x41d2,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria M5 MTP+CDROM", 0x41d6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 MTP+CDROM", 0x41d9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 Compact MTP+CDROM", 0x41da,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 Premium Dual Sim MTP+CDROM", 0x41db,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA MTP+CDROM", 0x41de,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria X MTP+CDROM", 0x41e0,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria SOV33 MTP+CDROM", 0x41e1,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ MTP+CDROM", 0x41e7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria X Compact MTP+CDROM", 0x41e8,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria G3123 MTP+CDROM", 0x41eb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ CDROM", 0x41ed,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA1 Ultra MTP+CDROM", 0x41ef,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ Premium MTP+CDROM", 0x41f1,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ1 MTP+CDROM", 0x41f3,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ1 Compact MTP+CDROM", 0x41f4,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria L2 MTP+CDROM", 0x41f6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA2 Compact MTP+CDROM", 0x41f7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA2 Ultra MTP+CDROM", 0x41f8,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ2 Compact Dual Sim MTP+CDROM", 0x41f9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ2 (H8266) MTP+CDROM", 0x41fa,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ2 Premium MTP+CDROM", 0x41fb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ3 Dual Sim (H9436) MTP+CDROM", 0x41ff,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 10 (I4113) MTP+CDROM", 0x4201,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 1 (J9110) MTP+CDROM", 0x4205,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia I4312 MTP+CDROM", 0x4207,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 5 MTP+CDROM", 0x420a,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 5 II Phone MTP+CDROM", 0x420d,
      DEVICE_FLAG_NONE },

  /*
   * MTP+ADB personalities of MTP devices (see above)
   */
  { "SonyEricsson", 0x0fce,  "c1605 Xperia Dual E MTP+ADB", 0x5146,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "LT15i Xperia Arc MTP+ADB", 0x514f,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "MT11i Xperia Neo MTP+ADB", 0x5156,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "IS12S Xperia Acro MTP+ADB", 0x5157,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "MK16i Xperia MTP+ADB", 0x515a,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "R800/R88i Xperia Play MTP+ADB", 0x515d,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST18i Xperia Ray MTP+ADB", 0x5161,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "SK17i Xperia Mini Pro MTP+ADB", 0x5166,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST15i Xperia Mini MTP+ADB", 0x5167,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "ST17i Xperia Active MTP+ADB", 0x5168,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT26i Xperia S MTP+ADB", 0x5169,
      DEVICE_FLAG_NO_ZERO_READS },
  { "SonyEricsson", 0x0fce, "WT19i Live Walkman MTP+ADB", 0x516d,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST21i Xperia Tipo MTP+ADB", 0x5170,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST25i Xperia U MTP+ADB", 0x5171,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT22i Xperia P MTP+ADB", 0x5172,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "MT27i Xperia Sola MTP+ADB", 0x5173,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "IS12S Xperia Acro HD MTP+ADB", 0x5175,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "SO-03D Xperia Acro HD MTP+ADB", 0x5176,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT28at Xperia Ion MTP+ADB", 0x5177,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT29i Xperia GX MTP+ADB", 0x5178,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST27i/ST27a Xperia go MTP+ADB", 0x517e,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST23i Xperia Miro MTP+ADB", 0x5180,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "SO-05D Xperia SX MTP+ADB", 0x5181,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT30p Xperia T MTP+ADB", 0x5182,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT25i Xperia V MTP+ADB", 0x5186,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia J MTP+ADB", 0x5188,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia ZL MTP+ADB", 0x5189,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia E MTP+ADB", 0x518c,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Tablet Z MTP+ADB 1", 0x518d,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia L MTP+ADB", 0x5192,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z MTP+ADB", 0x5193,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Tablet Z MTP+ADB 2", 0x5194,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia SP MTP+ADB", 0x5195,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP+ADB (ID2)", 0x5196,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia ZR MTP+ADB", 0x5197,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia A MTP+ADB", 0x5198,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia M MTP+ADB", 0x519b,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP+ADB (ID3)", 0x519c,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z1 MTP+ADB", 0x519e,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia C MTP+ADB", 0x51a3,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z1 Compact MTP+ADB", 0x51a7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia T2 Ultra MTP+ADB", 0x51a9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 MTP+ADB", 0x51aa,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 Dual MTP+ADB", 0x51ab,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z2 MTP+ADB", 0x51af,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3v MTP+ADB", 0x51b0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z2 Tablet MTP+ADB", 0x51b1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia E1 MTP+ADB", 0x51b5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z Ultra MTP+ADB", 0x51b6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia M2 Aqua MTP+ADB", 0x51b8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SONY", 0x0fce, "Xperia Z3 MTP+ADB", 0x51ba,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3 Compact MTP+ADB", 0x51bb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia E3 MTP+ADB", 0x51bc,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia Z3 Tablet MTP+ADB", 0x51c0,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria M4 Aqua Dual MTP+ADB", 0x51c4,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "E2115 MTP+ADB", 0x51c5,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z3+ MTP+ADB", 0x51c9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce,  "XPeria E4g MTP+ADB", 0x51cb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "C4 Dual MTP+ADB", 0x51d2,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria M5 MTP+ADB", 0x51d6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 MTP+ADB", 0x51d9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 Compact MTP+ADB", 0x51da,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria Z5 Premium Dual Sim MTP+ADB", 0x51db,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA MTP+ADB", 0x51de,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria X MTP+ADB", 0x51e0,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria SOV33 MTP+ADB", 0x51e1,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ MTP+ADB", 0x51e7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria X Compact MTP+ADB", 0x51e8,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria G3123 MTP+ADB", 0x51eb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ ADB", 0x51ed,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA1 Ultra MTP+ADB", 0x51ef,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ Premium MTP+ADB", 0x51f1,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ1 ADB", 0x51f3,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XZ1 Compact MTP+ADB", 0x51f4,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria L2 MTP+ADB", 0x51f6,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA2 Compact MTP+ADB", 0x51f7,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "XPeria XA2 Ultra MTP+ADB", 0x51f8,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ2 Compact Dual Sim MTP+ADB", 0x51f9,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ2 (H8266) MTP+ADB", 0x51fa,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ2 Premium MTP+ADB", 0x51fb,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia XZ3 Dual Sim (H9436) MTP+ADB", 0x51ff,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 10 (I4113) MTP+ADB", 0x5201,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 1 (J9110) MTP+ADB", 0x5205,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia I4312 MTP+ADB", 0x5207,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 5 MTP+ADB", 0x520a,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "Xperia 5 II Phone MTP+ADB", 0x520d,
      DEVICE_FLAG_NONE },

  /*
   * MTP+UMS modes
   * This mode is for using MTP on the internal storage (eMMC)
   * and using UMS (Mass Storage Device Class) on the external
   * SD card
   */
  { "SONY", 0x0fce, "MT27i Xperia Sola MTP+UMS", 0xa173,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "IS12S Xperia Acro HD MTP+UMS", 0xa175,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "SO-03D Xperia Acro HD MTP+UMS", 0xa176,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT28at Xperia Ion MTP+UMS", 0xa177,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST27i/ST27a Xperia go MTP+UMS", 0xa17e,
      DEVICE_FLAG_NONE },

  /*
   * MTP+UMS+ADB modes
   * Like the above, but also ADB
   */
  { "SONY", 0x0fce, "MT27i Xperia Sola MTP+UMS+ADB", 0xb173,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "IS12S Xperia Acro MTP+UMS+ADB", 0xb175,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "SO-03D Xperia Acro MTP+UMS+ADB", 0xb176,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "LT28at Xperia Ion MTP+UMS+ADB", 0xb177,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "ST27i/ST27a Xperia go MTP+UMS+ADB", 0xb17e,
      DEVICE_FLAG_NONE },


  /*
   * Motorola
   * Assume DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST on all of these.
   */
  /* https://sourceforge.net/p/libmtp/feature-requests/136/ */
  { "Motorola", 0x22b8, "XT1524 (MTP)", 0x002e,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by David Boyd <tiggrdave@users.sourceforge.net>
  { "Motorola", 0x22b8, "V3m/V750 verizon", 0x2a65,
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  /* https://sourceforge.net/p/libmtp/support-requests/130/ */
  { "Motorola", 0x22b8, "X 2nd edition XT1097 (MTP)", 0x2e24,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Atrix/Razr HD (MTP)", 0x2e32,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Atrix/Razr HD (MTP+ADB)", 0x2e33,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "RAZR M XT907 (MTP)", 0x2e50,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "RAZR M XT907 (MTP+ADB)", 0x2e51,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1539/ */
  { "Motorola", 0x22b8, "Droid Turbo 2 (XT1585)", 0x2e61,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Moto X (XT1053)", 0x2e62,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Moto X (XT1058)", 0x2e63,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1323/ */
  { "Motorola", 0x22b8, "Moto X (XT1080)", 0x2e66,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Droid Maxx (XT1080)", 0x2e67,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Droid Ultra", 0x2e68,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Moto G (ID1)", 0x2e76,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1841/ */
  { "Motorola", 0x22b8, "Moto Z2 (XT1789)", 0x2e81,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Moto G (ID2)", 0x2e82,
      DEVICE_FLAGS_ANDROID_BUGS & ~(DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL|DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST)},
  /* https://github.com/gphoto/gphoto2/issues/463 */
  { "Motorola", 0x22b8, "XT1032", 0x2e83,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1030/, PTP Id */
  { "Motorola", 0x22b8, "Moto G (XT1032)", 0x2e84,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1477/ */
  { "Motorola", 0x22b8, "Moto Maxx (XT1225)", 0x2ea4,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1183/ */
  { "Motorola", 0x22b8, "Droid Turbo (XT1254)", 0x2ea5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Droid Turbo Verizon", 0x2ea8,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/189/ */
  { "Motorola", 0x22b8, "MB632", 0x2dff,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Jader Rodrigues Simoes <jadersimoes@users.sourceforge.net>
  { "Motorola", 0x22b8, "Xoom 2 Media Edition (ID3)", 0x41cf,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Steven Roemen <sdroemen@users.sourceforge.net>
  { "Motorola", 0x22b8, "Droid X/MB525 (Defy)", 0x41d6,
      DEVICE_FLAG_NONE },
  { "Motorola", 0x22b8, "DROID2 (ID1)", 0x41da,
      DEVICE_FLAG_NONE },
  { "Motorola", 0x22b8, "Milestone / Verizon Droid", 0x41dc,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "DROID2 (ID2)", 0x42a7,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Xoom 2 Media Edition (ID2)", 0x4306,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Xoom 2 Media Edition", 0x4311,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by  B,H,Kissinger <mrkissinger@users.sourceforge.net>
  { "Motorola", 0x22b8, "XT912/XT928", 0x4362,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1104/ , PTP id. */
  { "Motorola", 0x22b8, "DROID4 (PTP)", 0x4373,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Lundgren <alundgren@users.sourceforge.net>
  { "Motorola", 0x22b8, "DROID4", 0x437f,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Marcus Meissner to libptp2
  { "Motorola", 0x22b8, "IdeaPad K1", 0x4811,
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST },
  // Reported by Hans-Joachim Baader <hjb@pro-linux.de> to libptp2
  { "Motorola", 0x22b8, "A1200", 0x60ca,
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST },
  // http://mark.cdmaforums.com/Files/Motdmmtp.inf
  { "Motorola", 0x22b8, "MTP Test Command Interface", 0x6413,
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST },
  // Reported by anonymous user
  { "Motorola", 0x22b8, "RAZR2 V8/U9/Z6", 0x6415,
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST },
  // Reported by Rodrigo Angelo Rafael
  // Razr D1, D3
  { "Motorola", 0x22b8, "Razr D1/D3/i (MTP)", 0x64b5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Razr D1/D3/i (MTP+?)", 0x64b6,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/697/ */
  { "Motorola", 0x22b8, "Atrix XT687 (MTP)", 0x64cf,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Brian Dolbec <dol-sen@users.sourceforge.net>
  { "Motorola", 0x22b8, "Atrix MB860 (MTP)", 0x7088,
      DEVICE_FLAGS_ANDROID_BUGS },
  /*
   * Motorola Xoom (Wingray) variants
   *
   * These devices seem to use these product IDs simultaneously
   * https://code.google.com/p/android-source-browsing/source/browse/init.stingray.usb.rc?repo=device--moto--wingray
   *
   * 0x70a3 - Factory test - reported as early MTP ID
   * 0x70a8 - MTP
   * 0x70a9 - MTP+ADB
   * 0x70ae - RNDIS
   * 0x70af - RNDIS+ADB
   * 0x70b0 - ACM
   * 0x70b1 - ACM+ADB
   * 0x70b2 - ACM+RNDIS
   * 0x70b3 - ACM+RNDIS+ADB
   * 0x70b4 - PTP
   * 0x70b5 - PTP+ADB
   *
   * Reported by Google Inc's Yavor Goulishev <yavor@google.com>
   */
  { "Motorola", 0x22b8, "Xoom (Factory test)", 0x70a3,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Xoom (MTP)", 0x70a8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Xoom (MTP+ADB)", 0x70a9,
      DEVICE_FLAGS_ANDROID_BUGS },
  // "carried by C Spire and other CDMA US carriers"
  { "Motorola", 0x22b8, "Milestone X2", 0x70ca,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "XT890/907/Razr (MTP)", 0x710d,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "XT890/907/Razr (MTP+ADB)", 0x710e,
      DEVICE_FLAGS_ANDROID_BUGS },
  /*
   * XT890/907/Razr
   * 710f is USB mass storage
   */

  /*
   * Google
   * These guys lend their Vendor ID to anyone who comes down the
   * road to produce an Android tablet it seems... The Vendor ID
   * was originally used for Nexus phones
   */
  { "Google Inc (for Allwinner)", 0x18d1, "A31 SoC", 0x0006,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Ainol Novo)", 0x18d1, "Fire/Flame", 0x0007,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Sony)", 0x18d1, "S1", 0x05b3,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/218/ */
  { "Google Inc (for Fairphone)", 0x18d1, "Fairphone 2", 0x0a07,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Google Inc (for Barnes & Noble)", 0x18d1, "Nook Color", 0x2d02,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Google Inc (for Asus)", 0x18d1, "TF201 Transformer", 0x4d00,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Google Inc (for Asus)", 0x18d1, "TF101 Transformer", 0x4e0f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1837/ */
  { "Google Inc (for Samsung)", 0x18d1, "Nexus One (MTP)", 0x4e12,
      DEVICE_FLAGS_ANDROID_BUGS },
  // 0x4e21 (Nexus S) is a USB Mass Storage device.
  { "Google Inc (for Samsung)", 0x18d1, "Nexus S (MTP)", 0x4e25,
      DEVICE_FLAGS_ANDROID_BUGS },
  // 0x4e26 is also used by "Ramos W30HD Pro Quad Core"
  { "Google Inc (for Samsung)", 0x18d1, "Nexus S (MTP+ADB)", 0x4e26,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Chris Smith <tcgsmythe@users.sourceforge.net>
  { "Google Inc (for Asus)", 0x18d1, "Nexus 7 (MTP)", 0x4e41,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Michael Hess <mhess126@gmail.com>
  { "Google Inc (for Asus)", 0x18d1, "Nexus 7 (MTP+ADB)", 0x4e42,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc", 0x18d1, "Nexus/Pixel (MTP)", 0x4ee1,
      (DEVICE_FLAGS_ANDROID_BUGS | DEVICE_FLAG_PROPLIST_OVERRIDES_OI) & ~DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  { "Google Inc", 0x18d1, "Nexus/Pixel (MTP+ADB)", 0x4ee2,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1255/ */
  { "Google Inc", 0x18d1, "Nexus/Pixel (PTP)", 0x4ee5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc", 0x18d1, "Nexus/Pixel (PTP+ADB)", 0x4ee6,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1444/ */
  { "Google", 0x18d1, "Pixel C (MTP)", 0x5202,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google", 0x18d1, "Pixel C (MTP+ADB)", 0x5203,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1892/ */
  { "Nook", 0x18d1, "Tablet", 0x685c,
      DEVICE_FLAGS_ANDROID_BUGS },
  // WiFi-only version of Xoom
  // See: http://bugzilla.gnome.org/show_bug.cgi?id=647506
  { "Google Inc (for Motorola)", 0x18d1, "Xoom (MZ604)", 0x70a8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Toshiba)", 0x18d1, "Thrive 7/AT105", 0x7102,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/88 */
  { "OnePlus", 0x18d1, "6T A6013", 0x7169,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Lenovo)", 0x18d1, "Ideapad K1", 0x740a,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Another OEM for Medion
  { "Google Inc (for Medion)", 0x18d1, "MD99000 (P9514)", 0xb00a,
      DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1563/ */
  { "Meizu", 0x18d1, "Pro 5 Ubuntu Phone", 0xd001, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Frederik Himpe <fhimpe@telenet.be>
  { "Google Inc (for LG Electronics)", 0x18d1, "P990/Optimus (Cyanogen)",
      0xd109, DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for LG Electronics)", 0x18d1, "P990/Optimus", 0xd10a,
      DEVICE_FLAGS_ANDROID_BUGS },


  /*
   * Media Keg
   */
  // Reported by Rajan Bella <rajanbella@yahoo.com>
  { "Kenwood", 0x0b28, "Media Keg HD10GB7 Sport Player", 0x100c, DEVICE_FLAG_UNLOAD_DRIVER},

  /*
   * Micro-Star International (MSI)
   */
  // Reported by anonymous sourceforge user.
  { "Micro-Star International", 0x0db0, "P610/Model MS-5557", 0x5572, DEVICE_FLAG_NONE },

  /*
   * FOMA
   */
  { "FOMA", 0x06d3, "D905i", 0x21ba, DEVICE_FLAG_NONE },

  /*
   * Haier
   */
  // Both reported by an anonymous SourceForge user
  // This is the 30 GiB model
  { "Haier", 0x1302, "Ibiza Rhapsody 1", 0x1016, DEVICE_FLAG_NONE },
  // This is the 4/8 GiB model
  { "Haier", 0x1302, "Ibiza Rhapsody 2", 0x1017, DEVICE_FLAG_NONE },

  /*
   * Panasonic
   */
  // Reported by dmizer
  { "Panasonic", 0x04da, "P905i", 0x2145, DEVICE_FLAG_NONE },
  // Reported by Taku
  { "Panasonic", 0x04da, "P906i", 0x2158, DEVICE_FLAG_NONE },

  /*
   * Polaroid
   */
  { "Polaroid", 0x0546, "Freescape/MPU-433158", 0x2035, DEVICE_FLAG_NONE },

  /*
   * Pioneer
   */
  // Reported by Dan Allen <dan.j.allen@gmail.com>
  { "Pioneer", 0x08e4, "XMP3", 0x0148, DEVICE_FLAG_NONE },

  /*
   * Slacker Inc.
   * Put in all evilness flags because it looks fragile.
   */
  // Reported by Pug Fantus <pugfantus@users.sourceforge.net>
  { "Slacker Inc.", 0x1bdc, "Slacker Portable Media Player", 0xfabf,
    DEVICE_FLAG_BROKEN_BATTERY_LEVEL | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST | DEVICE_FLAG_BROKEN_SEND_OBJECT_PROPLIST },

  // Reported by anonymous user
  { "Conceptronic", 0x1e53, "CMTD2", 0x0005, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by Demadridsur <demadridsur@gmail.com>
  { "O2 Sistemas", 0x1e53, "ZoltarTV", 0x0006, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by da-beat <dabeat@gmail.com>
  { "Wyplay", 0x1e53, "Wyplayer", 0x0007, DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },

  // Reported by Sense Hofstede <qense@users.sourceforge.net>
  { "Perception Digital, Ltd", 0x0aa6, "Gigaware GX400", 0x9702, DEVICE_FLAG_NONE },

  /*
   * RIM's BlackBerry
   */
  // Reported by Nicolas VIVIEN <nicolas@vivien.fr>
  { "RIM", 0x0fca, "BlackBerry Storm/9650", 0x8007, DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_SWITCH_MODE_BLACKBERRY | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },

  /* https://sourceforge.net/p/libmtp/bugs/1551/ */
  { "RIM", 0x0fca, "BlackBerry Priv", 0x8031, DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_SWITCH_MODE_BLACKBERRY | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },

  /* https://sourceforge.net/p/libmtp/bugs/1658/ */
  { "RIM", 0x0fca, "BlackBerry Dtek 60", 0x8041, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/264/ */
  { "RIM", 0x0fca, "BlackBerry Keyone", 0x8042, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Nextar
   */
  { "Nextar", 0x0402, "MA715A-8R", 0x5668, DEVICE_FLAG_NONE },

  /*
   * Coby
   */
  { "Coby", 0x1e74, "COBY MP705", 0x6512, DEVICE_FLAG_NONE },

#if 0
  /*
   * Apple devices, which are not MTP natively but can be made to speak MTP
   * using PwnTunes (http://www.pwntunes.net/)
   * CURRENTLY COMMENTED OUT:
   * These will make the UDEV rules flag these as MTP devices even if
   * PwnTunes is NOT installed. That is unacceptable, so a better solution
   * that actually inspects if the device has PwnTunes/MTP support needs
   * to be found, see:
   * https://sourceforge.net/p/libmtp/bugs/759/
   */
  { "Apple", 0x05ac, "iPhone", 0x1290, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "iPod Touch 1st Gen", 0x1291, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "iPhone 3G", 0x1292, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "iPod Touch 2nd Gen", 0x1293, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "iPhone 3GS", 0x1294, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "0x1296", 0x1296, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "0x1297", 0x1297, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "0x1298", 0x1298, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "iPod Touch 3rd Gen", 0x1299, DEVICE_FLAG_NONE },
  { "Apple", 0x05ac, "iPad", 0x129a, DEVICE_FLAG_NONE },
#endif

  // Reported by anonymous SourceForge user, also reported as
  // Pantech Crux, claming to be:
  // Manufacturer: Qualcomm
  // Model: Windows Simulator
  // Device version: Qualcomm MTP1.0
  { "Curitel Communications, Inc.", 0x106c,
      "Verizon Wireless Device", 0x3215, DEVICE_FLAG_NONE },
  // Reported by: Jim Hanrahan <goshawkjim@users.sourceforge.net>
  { "Pantech", 0x106c, "Crux", 0xf003, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/feature-requests/208/ */
  { "Asus", 0x0b05, "Zenfone Go (ZC500TG)", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },
  /*
   * Asus
   * Pattern of PIDs on Android devices seem to be:
   * n+0 = MTP
   * n+1 = MTP+ADB
   * n+2 = ?
   * n+3 = ?
   * n+4 = PTP
   */
  // Reported by Glen Overby
  { "Asus", 0x0b05, "TF300 Transformer (MTP)", 0x4c80,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by jaile <jaile@users.sourceforge.net>
  { "Asus", 0x0b05, "TF300 Transformer (MTP+ADB)", 0x4c81,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Repored by Florian Apolloner <f-apolloner@users.sourceforge.net>
  { "Asus", 0x0b05, "TF700 Transformer (MTP)", 0x4c90,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF700 Transformer (MTP+ADB)", 0x4c91,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF701T Transformer Pad (MTP)", 0x4ca0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF701T Transformer Pad (MTP+ADB)", 0x4ca1,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/135/ */
  { "Asus", 0x0b05, "ME302KL MeMo Pad FHD10 (MTP)", 0x4cc0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ME302KL MeMo Pad FHD10 (MTP+ADB)", 0x4cc1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ME301T MeMo Pad Smart 10 (MTP)", 0x4cd0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ME301T MeMo Pad Smart 10 (MTP+ADB)", 0x4cd1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Asus Fonepad Note 6 (MTP)", 0x4ce0,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Asus Fonepad Note 6 (MTP+ADB)", 0x4ce1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF201 Transformer Prime (keyboard dock)", 0x4d00,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF201 Transformer Prime (tablet only)", 0x4d01,
      DEVICE_FLAGS_ANDROID_BUGS },
  // 4d04 is the PTP mode, don't add it
  { "Asus", 0x0b05, "SL101 (MTP)", 0x4e00,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "SL101 (MTP+ADB)", 0x4e01,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF101 Eeepad Transformer (MTP)", 0x4e0f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF101 Eeepad Transformer (MTP+ADB)", 0x4e1f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Fonepad", 0x514f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone (MTP)", 0x5200,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone (MTP+ADB)", 0x5201,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ME302C MemoPad (MTP+?)", 0x520f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone 2 (MTP)", 0x5210,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone 2 (MTP+ADB)", 0x5211,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone 2 (PTP)", 0x5214,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ME302C MemoPad (MTP)", 0x521f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1066/ */
  { "Asus", 0x0b05, "PadFone Infinity (2nd ID) (MTP)", 0x5220,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone Infinity (2nd ID) (MTP+ADB)", 0x5221,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone Infinity (MTP)", 0x5230,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "PadFone Infinity (MTP+ADB)", 0x5231,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Memo ME172V (MTP)", 0x5400,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1072/ */
  { "Asus", 0x0b05, "Fonepad 7 LTE ME372CL (MTP)", 0x540f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Memo ME173X (MTP)", 0x5410,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Memo ME173X (MTP+ADB)", 0x5411,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1072/ */
  { "Asus", 0x0b05, "Fonepad 7 LTE ME372CL (MTP+ADB)", 0x541f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Memo K00F (MTP)", 0x5460,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Memo Pad 8 (MTP)", 0x5466,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "Memo K00F (MTP+ADB)", 0x5468,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/158/ */
  { "Asus", 0x0b05, "ZenFone 5 (MTP)", 0x5480,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1279/ */
  { "Asus", 0x0b05, "ZenFone 5 (MTP+ADB)", 0x5481,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1236/ */
  { "Asus", 0x0b05, "ZenFone 6 (MTP)", 0x5490,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ZenFone 6 (MTP+ADB)", 0x5491,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1239/ */
  { "Asus", 0x0b05, "K010 (MTP)", 0x5500,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1196/ */
  { "Asus", 0x0b05, "MemoPad 7 (MTP+ADB)", 0x5506,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1069/ */
  { "Asus", 0x0b05, "K00E (MTP+ADB)", 0x550f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1244/ */
  { "Asus", 0x0b05, "MemoPad 8 ME181 CX (MTP)", 0x5561,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1406/ */
  { "Asus", 0x0b05, "Zenfone 2 (MTP)", 0x5600,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1364/ */
  { "Asus", 0x0b05, "Z00AD (MTP)", 0x5601,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TX201LA (MTP)", 0x561f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1271/ */
  { "Asus", 0x0b05, "ZenFone 4 (MTP)", 0x580f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1179/ */
  { "Asus", 0x0b05, "ZenFone 4 A400CG (MTP)", 0x581f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1548/ */
  { "Asus", 0x0b05, "ASUS FonePad 8 FE380CG (MTP)", 0x590f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1258/ */
  { "Asus", 0x0b05, "A450CG (MTP)", 0x5a0f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1546/ */
  { "Asus", 0x0b05, "ZenPad 80 (MTP)", 0x5e0f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1350/ */
  { "Asus", 0x0b05, "Zenfone 2 ZE550ML (MTP)", 0x5f02,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1364/ */
  { "Asus", 0x0b05, "Zenfone 2 ZE551ML (MTP)", 0x5f03,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/75 */
  { "Asus", 0x0b05, "Zenpad 10", 0x600f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/255/ */
  { "Asus", 0x0b05, "Zenfone V (MTP)", 0x610f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1642/ */
  { "Asus", 0x0b05, "ME581CL", 0x7770,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1232/ */
  { "Asus", 0x0b05, "MemoPad 7 (ME572CL)", 0x7772,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1351/ */
  { "Asus", 0x0b05, "Fonepad 7 (FE375CXG)", 0x7773,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "ZenFone 5 A500KL (MTP)", 0x7780,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1247/ */
  { "Asus", 0x0b05, "ZenFone 5 A500KL (MTP+ADB)", 0x7781,
      DEVICE_FLAGS_ANDROID_BUGS },


  /*
   * Lenovo
   */
  /* https://sourceforge.net/p/libmtp/support-requests/178/ */
  { "Lenovo", 0x17ef, "P70-A", 0x0c02,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1415/ */
  { "Lenovo", 0x17ef, "P70", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Richard Körber <shredzone@users.sourceforge.net>
  { "Lenovo", 0x17ef, "K1", 0x740a,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  // Adding Android default bug flags since it appears to be an Android
  { "Lenovo", 0x17ef, "ThinkPad Tablet", 0x741c,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Medion is using Lenovos manufacturer ID it seems.
  // Reported by Thomas Goss <thomas.goss@linux.com>
  { "Medion", 0x17ef, "Lifetab P9516", 0x7483,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by: XChesser <XChesser@users.sourceforge.net>
  { "Lenovo", 0x17ef, "P700", 0x7497,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1185/ */
  { "Lenovo", 0x17ef, "A820", 0x7498,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1190/ */
  { "Lenovo", 0x17ef, "P780", 0x74a6,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by: anonymous sourceforge user
  { "Lenovo", 0x17ef, "Lifetab S9512", 0x74cc,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/217/ */
  { "Lenovo", 0x17ef, "Vibe K5", 0x74ee,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/170/ */
  { "Lenovo", 0x17ef, "S660", 0x74f8,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Brian J. Murrell
  { "Lenovo", 0x17ef, "IdeaTab A2109A", 0x7542,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/166/ */
  { "Lenovo", 0x17ef, "IdeaTab S2210a", 0x757d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1529/ */
  { "Lenovo", 0x17ef, "K900 (ID2)", 0x75b3,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1123/ */
  { "Lenovo", 0x17ef, "K900 (ID1)", 0x75b5,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by rvelev@mail.bg
  { "Lenovo", 0x17ef, "IdeaPad A3000 (ID1)", 0x75bc,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "IdeaPad A3000 (ID2)", 0x75be,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/232/ */
  { "Lenovo", 0x17ef, "A706", 0x7614,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "IdeaTab S5000", 0x76e8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "Toga Tablet B6000-F", 0x76f2,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1155/ */
  { "Lenovo", 0x17ef, "Yoga Tablet 10 B8000-H", 0x76ff,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1673/ */
  { "Lenovo", 0x17ef, "S960", 0x770a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1597/ */
  { "Lenovo", 0x17ef, "K910SS", 0x7713,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1122/ */
  { "Lenovo", 0x17ef, "S930", 0x7718,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/discussion/535190/ */
  { "Lenovo", 0x17ef, "A5500-H", 0x772a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1250/ */
  { "Lenovo", 0x17ef, "A5500-F", 0x772b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /*  https://sourceforge.net/p/libmtp/bugs/1742/ */
  { "Lenovo", 0x17ef, "A7600-F", 0x7730,
      DEVICE_FLAGS_ANDROID_BUGS },
  /*  https://sourceforge.net/p/libmtp/bugs/1391/ */
  { "Lenovo", 0x17ef, "A7600-F 2nd", 0x7731,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1291/ */
  { "Lenovo", 0x17ef, "A3500-F", 0x7737,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1556/ */
  { "Lenovo", 0x17ef, "A3500-FL", 0x7738,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "LifeTab E733X", 0x775a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1595/ */
  { "Lenovo", 0x17ef, "K920", 0x778f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/186/ */
  { "Lenovo", 0x17ef, "Yoga Tablet 2 - 1050F", 0x77a4,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1828/ */
  { "Lenovo", 0x17ef, "Yoga Tablet 2", 0x77a5,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/168/ */
  { "Lenovo", 0x17ef, "Yoga Tablet 2 Pro", 0x77b1,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/219/ */
  { "Lenovo", 0x17ef, "Tab S8-50F", 0x77d8,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/125/ */
  { "Lenovo", 0x17ef, "Vibe Z2", 0x77ea,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1793/ */
  { "Lenovo", 0x17ef, "S60-a", 0x7802,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/272/ */
  { "Lenovo", 0x17ef, "A7-30HC", 0x7852,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1861/ */
  { "Lenovo", 0x17ef, "A7-30GC", 0x7853,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/253/ */
  { "Lenovo", 0x17ef, "A7000-A Smartphone", 0x7882,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1360/ */
  { "Lenovo", 0x17ef, "K3 Note", 0x7883,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1488/ */
  { "Lenovo", 0x17ef, "A10-70F", 0x789a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1497/ */
  { "Lenovo", 0x17ef, "A10-70L", 0x789b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/264/ */
  { "Lenovo", 0x17ef, "Vibe Shot Z90a40", 0x78a7,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1480/ */
  { "Medion", 0x17ef, "P8312 Tablet", 0x78ae,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/201/ */
  { "Lenovo", 0x17ef, "Lifetab S1034X", 0x78b0,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1572/ */
  { "Lenovo", 0x17ef, "PHAB Plus", 0x78d1,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1562/ */
  { "Lenovo", 0x17ef, "Vibe K4 Note", 0x78f6,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/213/ */
  { "Lenovo", 0x17ef, "Vibe P1 Pro", 0x78fc,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1531/ */
  { "Lenovo", 0x17ef, "Vibe X", 0x7902,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1784/ */
  { "Lenovo", 0x17ef, "P1ma40 (2nd ID)", 0x7920,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/235/ */
  { "Lenovo", 0x17ef, "P1ma40", 0x7921,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1465/ */
  { "Lenovo", 0x17ef, "A1000 Smartphone", 0x7928,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1465/ */
  { "Lenovo", 0x17ef, "A1000 Smartphone ADB", 0x7929,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/224/ */
  { "Lenovo", 0x17ef, "Yoga 10 Tablet YT3-X50F", 0x7932,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/204/ */
  { "Lenovo", 0x17ef, "TAB 2 A10-30", 0x7949,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1719/ */
  { "Lenovo", 0x17ef, "YT3 X90F", 0x795c,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "K5", 0x7993,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "Vibe K5 Note", 0x7999,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/293/ */
  { "Lenovo", 0x17ef, "TB3-710F", 0x79a2,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1820/ */
  { "Lenovo", 0x17ef, "YB1-X90F", 0x79af,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1664/ */
  { "Lenovo", 0x17ef, "Vibe K4", 0x79b7,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/242/ */
  { "Lenovo", 0x17ef, "Tab 3 10 Plus", 0x79de,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1755/ */
  { "Lenovo", 0x17ef, "TB3-850M ", 0x79de,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1624/ */
  { "Lenovo", 0x17ef, "B Smartphone", 0x7a18,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1738/ */
  { "Lenovo", 0x17ef, "K6 Power", 0x7a2a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1679/ */
  { "Lenovo", 0x17ef, "C2", 0x7a36,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/248/ */
  { "Lenovo", 0x17ef, "P2c72", 0x7a36,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* Marcus parents */
  { "Lenovo", 0x17ef, "Tab 10", 0x7a50,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1903/ */
  { "Lenovo", 0x17ef, "TB-8703F", 0x7a6b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/33 */
  { "Lenovo", 0x17ef, "Tab4 10 Plus", 0x7ad0,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/262/ */
  { "Lenovo", 0x17ef, "Tab4 10", 0x7ac5,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/297/ */
  { "Lenovo", 0x17ef, "Tab TB-X704A", 0x7b25,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/296/ */
  { "Lenovo", 0x17ef, "TB-7304I", 0x7b3c,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1912/ */
  { "Lenovo", 0x17ef, "TB-8304F1", 0x7b84,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1831/ */
  { "Lenovo", 0x17ef, "Tab4 10 (2nd ID)", 0x7bc7,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1873/ */
  { "Lenovo", 0x17ef, "Tab P10", 0x7bd3,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/102 */
  { "Lenovo", 0x17ef, "Tab M10", 0x7bdf,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Lenovo", 0x17ef, "TB-X606F", 0x7c45,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/74 */
  { "Lenovo", 0x17ef, "TB-X606F (Lenovo Tab M10 FHD Plus)", 0x7c46,
      DEVICE_FLAGS_ANDROID_BUGS },
  /*https://github.com/libmtp/libmtp/issues/111  */
  { "Lenovo", 0x17ef, "TAB M7 Gen 3", 0x7cb3,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1736/ */
  { "Lenovo", 0x17ef, "P1060X", 0x9039,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/259/ */
  { "Medion", 0x17ef, "P10606", 0xf003,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Huawei
   * IDs used by Honor U8860,U8815,U9200,P2
   */
  { "Huawei", 0x12d1, "MTP device (ID1)", 0x1051,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Huawei", 0x12d1, "MTP device (ID2)", 0x1052,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1507/ */
  { "Huawei", 0x12d1, "Honor 7", 0x1074,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1381/ */
  { "Huawei", 0x12d1, "H60-L11", 0x1079,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1550/ */
  { "Huawei", 0x12d1, "H60-L12", 0x107a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1640/ */
  { "Huawei", 0x12d1, "Nova", 0x107d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/173/ */
  { "Huawei", 0x12d1, "P9 Plus", 0x107e,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/259/ */
  { "Huawei", 0x12d1, "Y5 2017", 0x107f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1361/ */
  { "Huawei", 0x12d1, "Ascend P8", 0x1082,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/276/ */
  { "Huawei", 0x12d1, "Y600", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1418/ */
  { "Huawei", 0x12d1, "Honor 3C", 0x2012,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1629/ */
  { "Huawei", 0x12d1, "Y320-U10", 0x2406,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1703/ */
  { "Huawei", 0x12d1, "Y625-U03", 0x255d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/186/ */
  { "Huawei", 0x12d1, "Y360-U61", 0x2567,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/205/ */
  { "Huawei", 0x12d1, "Y360-U03", 0x256b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1774/ */
  { "Huawei", 0x12d1, "Y541-U02", 0x257c,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/227/ */
  { "Huawei", 0x12d1, "Y560-L01", 0x259c,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1695/
   * Seth Brown on libmtp-discuss
   */
  { "Huawei", 0x12d1, "CUN-U29", 0x2608,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/257/ */
  { "Huawei", 0x12d1, "LUA-L02", 0x260b,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Huawei", 0x12d1, "Mediapad (mode 0)", 0x360f,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Bearsh <bearsh@users.sourceforge.net>
  { "Huawei", 0x12d1, "Mediapad (mode 1)", 0x361f,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * ZTE
   * Android devices reported by junwang <lovewjlove@users.sourceforge.net>
   */
  { "ZTE", 0x19d2, "V55 ID 1", 0x0244, DEVICE_FLAGS_ANDROID_BUGS },
  { "ZTE", 0x19d2, "V55 ID 2", 0x0245, DEVICE_FLAGS_ANDROID_BUGS },
  { "ZTE", 0x19d2, "V790/Blade 3", 0x0306, DEVICE_FLAGS_ANDROID_BUGS },
  { "ZTE", 0x19d2, "V880E", 0x0307, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/672/ */
  { "ZTE", 0x19d2, "Grand X In", 0x0343, DEVICE_FLAGS_ANDROID_BUGS },
  { "ZTE", 0x19d2, "V985", 0x0383, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1745/ */
  { "ZTE", 0x19d2, "Blade L3", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1328/ */
  { "ZTE", 0x19d2, "V5", 0xffce, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1646/ */
  { "ZTE", 0x19d2, "Z9 Max", 0xffcf, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * HTC (High Tech Computer Corp)
   * Reporters:
   * Steven Eastland <grassmonk@users.sourceforge.net>
   * Kevin Cheng <kache@users.sf.net>
   */
  /* https://sourceforge.net/p/libmtp/feature-requests/173/ */
  { "HTC", 0x0bb4, "M9", 0x0401,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/181/ */
  { "HTC", 0x0bb4, "One M9 (1st ID)", 0x040b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1398/ */
  { "HTC", 0x0bb4, "Spreadtrum SH57MYZ03342 (MTP)", 0x05e3,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1840/ */
  { "HTC", 0x0bb4, "Desire 626G (MTP)", 0x05f0,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* reported by Mikkel Oscar Lyderik <mikkeloscar@gmail.com> */
  { "HTC", 0x0bb4, "Desire 510 (MTP+ADB)", 0x05fd,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1221/ */
  { "HTC", 0x0bb4, "One M8 Google Play Edition (MTP+ADB)", 0x060b,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1500/ */
  { "HTC", 0x0bb4, "One Mini 2 (MTP)", 0x0629,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1508/ */
  { "HTC", 0x0bb4, "One M9 (2nd ID)", 0x065c,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1543/ */
  { "HTC", 0x0bb4, "Desire 626s (MTP)", 0x0668,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/200/ */
  { "HTC", 0x0bb4, "HTC Desire 520", 0x0670,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/153/ */
  { "HTC", 0x0bb4, "HTC6515LVW/One Remix", 0x07d8,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1615/ */
  { "HTC", 0x0bb4, "HTC X920E", 0x07a1,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/141/ */
  { "HTC", 0x0bb4, "HTC One (HTC6500LVW)", 0x07ae,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/support-requests/128/ */
  { "HTC", 0x0bb4, "HTC One M8 (HTC6525LVW)", 0x07ca,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1161/ */
  { "HTC", 0x0bb4, "HTC One M8 (Verizon) (HTC6525LVW)", 0x07cb,
      DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1133/ */
  { "HTC", 0x0bb4, "HTC One Remix (HTC6515LVW)", 0x07d9,
      DEVICE_FLAG_NONE },
  // Reported by Markus Heberling
  { "HTC", 0x0bb4, "Windows Phone 8X ID1", 0x0ba1,
      DEVICE_FLAG_NONE },
  { "HTC", 0x0bb4, "Windows Phone 8X ID2", 0x0ba2,
      DEVICE_FLAG_NONE },

#if 1
  /* after some review I commented it back in. There was apparently
   * only one or two devices misbehaving (having this ID in mass storage mode),
   * but more seem to use it regularly as MTP devices. Marcus 20150401 */
  /*
   * This had to be commented out - the same VID+PID is used also for
   * other modes than MTP, so we need to let mtp-probe do its job on this
   * device instead of adding it to the database.
   * used by various devices, like Fairphone, Elephone P5000, etc
   * https://sourceforge.net/p/libmtp/bugs/1290/
   */
  { "HTC", 0x0bb4, "Android Device ID1 (Zopo, HD2, Bird...)", 0x0c02,
      DEVICE_FLAGS_ANDROID_BUGS },
#endif
  /* https://sourceforge.net/p/libmtp/bugs/1677/ */
  { "DEXP", 0x0bb4, "Ixion XL145 Snatch", 0x0c08,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "EVO 4G LTE/One V (ID1)", 0x0c93,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "EVO 4G LTE/One V (ID2)", 0x0ca8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One S (ID1)", 0x0cec,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "One Mini (ID1)", 0x0dcd,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One 802w (ID1)", 0x0dd2,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC Desire X", 0x0dd5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (ID1)", 0x0dda,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC Butterfly X290d", 0x0de4,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (MTP+UMS+ADB)", 0x0dea,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC Evo 4G LTE (ID1)", 0x0df5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One S (ID2)", 0x0df8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One S (ID3)", 0x0df9,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One X (ID1)", 0x0dfa,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One X (ID2)", 0x0dfb,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One X (ID3)", 0x0dfc,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One X (ID4)", 0x0dfd,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC Butterfly (ID1)", 0x0dfe,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "Droid DNA (MTP+UMS+ADB)", 0x0dff,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC Droid Incredible 4G LTE (MTP)", 0x0e31,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC Droid Incredible 4G LTE (MTP+ADB)", 0x0e32,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "Droid DNA (MTP+UMS)", 0x0ebd,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1182/ */
  { "HTC", 0x0bb4, "Desire 310 (MTP)", 0x0ec6,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1481/ */
  { "HTC", 0x0bb4, "Desire 310 (2nd id) (MTP)", 0x0ec7,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1420/ */
  { "HTC", 0x0bb4, "Desire 816G (MTP)", 0x0edb,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1632/ */
  { "HTC", 0x0bb4, "Desire 626G Dual Sim (MTP)", 0x0edd,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (MTP+ADB+CDC)", 0x0f5f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (MTP+CDC)", 0x0f60,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (MTP+ADB)", 0x0f63,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (MTP)", 0x0f64,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (MTP+ADB+?)", 0x0f87,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One (ID3)", 0x0f91,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One M8 (MTP)", 0x0f25,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/245/ */
  { "HTC", 0x0bb4, "HTC One U11 (MTP)", 0x0f26,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One M8 (MTP+ADB)", 0x061a,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One M8 (MTP+UMS)", 0x0fb5,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "HTC One M8 (MTP+ADB+UMS)", 0x0fb4,
      DEVICE_FLAGS_ANDROID_BUGS },

#if 1
  /* after some review I commented it back in. There was apparently
   * only one or two devices misbehaving (having this ID in mass storage mode),
   * but more seem to use it regularly as MTP devices. Marcus 20150401 */
  /*
   * This had to be commented out - the same VID+PID is used also for
   * other modes than MTP, so we need to let mtp-probe do its job on this
   * device instead of adding it to the database.
   *
   * Apparently also used by a clone called Jiayu G2S
   * with the MTK6577T chipset
   * http://www.ejiayu.com/en/Product-19.html
   * Wiko Cink Peax 2
   */
  { "HTC", 0x0bb4, "Android Device ID2 (Zopo, HD2...)", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
#endif
  /* https://sourceforge.net/p/libmtp/bugs/1198/ */
  { "HTC", 0x0bb4, "Motorola Razr D1", 0x2012,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1440/ */
  { "HTC", 0x0bb4, "Motorola P98 4G", 0x201d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1508/ */
  { "HTC", 0x0bb4, "One M9 (3rd ID)", 0x4ee1,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/217/ */
  { "HTC", 0x0bb4, "One M9 (4th ID)", 0x4ee2,
      DEVICE_FLAGS_ANDROID_BUGS },
  // These identify themselves as "cm_tenderloin", fun...
  // Done by HTC for HP I guess.
  { "HTC (for Hewlett-Packard)", 0x0bb4, "HP Touchpad (MTP)", 0x685c,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC (for Hewlett-Packard)", 0x0bb4, "HP Touchpad (MTP+ADB)", 0x6860,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "HTC", 0x0bb4, "Windows Phone 8s ID1", 0xf0ca,
      DEVICE_FLAG_NONE },

  /*
   * NEC
   */
  { "NEC", 0x0409, "FOMA N01A", 0x0242, DEVICE_FLAG_NONE },
  /* https://sourceforge.net/p/libmtp/bugs/1724/ */
  { "Casio", 0x0409, "GzOne Commando C771", 0x02ed, DEVICE_FLAG_NONE },
  { "NEC", 0x0409, "Casio C811", 0x0326, DEVICE_FLAG_NONE },
  { "NEC", 0x0409, "Casio CA-201L", 0x0432, DEVICE_FLAG_NONE },

  /*
   * nVidia
   */
  // Found on Internet forum
  { "nVidia", 0x0955, "CM9-Adam", 0x70a9,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Various pads such as Nabi2, Notion Ink Adam, Viewsonic G-Tablet
  { "nVidia", 0x0955, "Various tablets (ID1)", 0x7100,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "nVidia", 0x0955, "Various tablets (ID2)", 0x7102,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1582/ */
  { "nVidia", 0x0955, "Jetson TX1", 0x7721,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "nVidia", 0x0955, "Shield (MTP+ADB)", 0xb400,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1447/ */
  { "nVidia", 0x0955, "Shield (MTP)", 0xb401,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/297/ */
  { "nVidia", 0x0955, "Shield Android TV pro (MTP)", 0xb42a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1087/ */
  { "nVidia", 0x0955, "Tegra Note", 0xcf02,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "nVidia", 0x0955, "Shield Tablet (MTP+ADB)", 0xcf05,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* benpro82@gmail.com */
  { "nVidia", 0x0955, "Shield Tablet (MTP)", 0xcf07,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Vizio
   * Reported by:
   * Michael Gurski <gurski@users.sourceforge.net>
   */
  /* https://sourceforge.net/p/libmtp/support-requests/221/ */
  { "Nokia", 0x0489, "N1", 0x1ab0,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1567/ */
  { "InFocus", 0x0489, "M808", 0xc00b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/138/ */
  { "InFocus", 0x0489, "M810", 0xc025,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Vizio", 0x0489, "Unknown 1", 0xc026,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Vizio", 0x0489, "VTAB1008", 0xe040,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Vizio (for Lenovo)", 0x0489, "LIFETAB S9714", 0xe111,
      DEVICE_FLAGS_ANDROID_BUGS },


  /*
   * Amazon
   */
  { "Amazon", 0x1949, "Kindle Fire 2G (ID1)", 0x0005,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Amazon", 0x1949, "Kindle Fire (ID1)", 0x0007,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Amazon", 0x1949, "Kindle Fire (ID2)", 0x0008,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Amazon", 0x1949, "Kindle Fire (ID3)", 0x000a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1026/ */
  { "Amazon", 0x1949, "Kindle Fire (ID6)", 0x000b,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Amazon", 0x1949, "Kindle Fire (ID4)", 0x000c,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1015/ */
  { "Amazon", 0x1949, "Kindle Fire (ID7)", 0x000d,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Amazon", 0x1949, "Kindle Fire (ID5)", 0x0012,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1353/ */
  { "Amazon", 0x1949, "Kindle Fire HD6", 0x00f2,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* R Billing tested one unit rbilling@tanglewood.online
   * https://github.com/gphoto/libgphoto2/issues/473 */
  { "Amazon", 0x1949, "Kindle Fire 7 (3rd ID)", 0x0121,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1460/ */
  { "Amazon", 0x1949, "Kindle Fire 8", 0x0211,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/158/ */
  { "Amazon", 0x1949, "Kindle Fire 8 HD", 0x0212,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1448/ */
  { "Amazon", 0x1949, "Kindle Fire 7", 0x0221,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1491/ */
  { "Amazon", 0x1949, "Kindle Fire 5", 0x0222,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1718/ */
  { "Amazon", 0x1949, "Kindle Fire 8 (2nd ID)", 0x0261,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1776/ */
  { "Amazon", 0x1949, "Kindle Fire 7 (2nd ID)", 0x0271,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1845/ */
  { "Amazon", 0x1949, "Kindle Fire Kids", 0x0272,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/279/ */
  { "Amazon", 0x1949, "Kindle Fire Tablet 10 HD", 0x0281,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/21 */
  { "Amazon", 0x1949, "Kindle Fire 8 HD (2nd ID)", 0x0331,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/300/ */
  { "Amazon", 0x1949, "Kindle Fire 8 HD (3rd ID)", 0x0332,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/293/ */
  { "Amazon", 0x1949, "Kindle Fire Tablet 10 HD (2nd ID)", 0x03f1,
      DEVICE_FLAGS_ANDROID_BUGS },

  { "Amazon", 0x1949, "Kindle Fire HD8 Plus", 0x0581,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1913/ */
  { "Amazon", 0x1949, "Kindle Fire 10 Plus", 0x05e1,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Amazon", 0x1949, "Fire Phone", 0x0800,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1876/ */
  { "Amazon", 0x1949, "Kindle Fire (ID 8)", 0x0c31,
      DEVICE_FLAGS_ANDROID_BUGS },

  { "Amazon", 0x1949, "Kindle Fire 8 HD (7th Gen)", 0x0262,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Barnes&Noble
   */
  { "Barnes&Noble", 0x2080, "Nook HD+", 0x0005,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Barnes&Noble", 0x2080, "Nook HD", 0x0006,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1504/ */
  { "Barnes&Noble", 0x2080, "Nook Glowlight+", 0x000a,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Viewpia, bq, YiFang
   * Seems like some multi-branded OEM product line.
   */
  { "Various", 0x2207, "Viewpia DR/bq Kepler", 0x0001,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "YiFang", 0x2207, "BQ Tesla", 0x0006,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://bugs.debian.org/917259 */
  { "Various", 0x2207, "Onyx Boox Max 2", 0x000b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1833/ */
  { "Onyx", 0x2207, "Boox Max 2 Pro", 0x000c,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1834/ */
  { "Onyx", 0x2207, "Boox Note", 0x000d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1354/ */
  { "Various", 0x2207, "Viewpia DR/bq Kepler Debugging", 0x0011,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/291/ */
  { "Onyx", 0x2207, "Boox Nova", 0x0014,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1900/ */
  { "Onyx", 0x2207, "Boox Nova Pro", 0x0015,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/82 */
  { "Supernote", 0x2207, "A5X", 0x0031,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Kobo
   */
  /* https://sourceforge.net/p/libmtp/bugs/1208/ */
  { "Kobo", 0x2237, "Arc 7 HD", 0xb108,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by George Talusan
  { "Kobo", 0x2237, "Arc (ID1)", 0xd108,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Kobo", 0x2237, "Arc (ID2)", 0xd109,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Hisense
   */
  // Reported by Anonymous SourceForge users
  { "HiSense", 0x109b, "Sero 7 Pro", 0x9105, DEVICE_FLAGS_ANDROID_BUGS },
  { "Hisense", 0x109b, "E860 (ID1)", 0x9106, DEVICE_FLAGS_ANDROID_BUGS },
  { "Hisense", 0x109b, "E860 (ID2)", 0x9109, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1704/ */
  { "Crosscall", 0x109b, "Trekker M1 core", 0x9130, DEVICE_FLAGS_ANDROID_BUGS },


  /*
   * Intel
   * Also sold rebranded as Orange products
   */
  /* https://sourceforge.net/p/libmtp/feature-requests/215/ */
  { "Intel", 0x8087, "Point of View TAB-I847", 0x092a, DEVICE_FLAGS_ANDROID_BUGS },

  { "Intel", 0x8087, "Xolo 900/AZ210A", 0x09fb, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1256/ */
  { "Intel", 0x8087, "Noblex T7A21", 0x0a16, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1252/ */
  { "Intel", 0x8087, "Foxconn iView i700", 0x0a15, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1237/ */
  { "Intel", 0x8087, "Telcast Air 3G", 0x0a5e, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1338/ */
  { "Intel", 0x8087, "Chuwi vi8", 0x0a5f, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Xiaomi
   */
  /* https://sourceforge.net/p/libmtp/bugs/1269/ */
  { "Xiaomi", 0x2717, "Mi-3w (MTP)", 0x0360,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Xiaomi", 0x2717, "Mi-3 (MTP)", 0x0368,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1149/ */
  { "Xiaomi", 0x2717, "MiPad (MTP)", 0x0660,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1489/ */
  { "Xiaomi", 0x2717, "MiPad (MTP+ADB)", 0x0668,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Xiaomi", 0x2717, "Hongmi (MTP+ADB)", 0x1240,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1095/ */
  { "Xiaomi", 0x2717, "Hongmi (MTP)", 0x1248,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1295/ */
  { "Redmi", 0x2717, "1S (MTP)", 0x1260,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1164/ */
  { "Redmi", 0x2717, "HM 1S (MTP)", 0x1268,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1702/ */
  { "Xiaomi", 0x2717, "HM NOTE 1LTEW 4G Phone (MTP)", 0x1360,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/discussion/535190/ */
  { "Xiaomi", 0x2717, "HM NOTE 1LTEW MIUI (MTP)", 0x1368,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Xiaomi", 0x2717, "Mi-2 (MTP+ADB)", 0x9039,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Xiaomi", 0x2717, "Mi-2 (MTP)", 0xf003,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1397/ */
  { "Xiaomi", 0x2717, "Mi-2s (id2) (MTP)", 0xff40,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1905/ */
  { "Xiaomi", 0x0a9d, "POCO X3 Pro (MTP)", 0xff40,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/90 */
  { "Xiaomi", 0x0a9d, "MI 9 M1902F1G", 0xff40,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1339/ */
  { "Xiaomi", 0x2717, "Mi-2s (MTP)", 0xff48,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1402/ */
  { "Xiaomi", 0x2717, "Redmi 2 (MTP)", 0xff60,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1445/ */
  { "Xiaomi", 0x2717, "Redmi 2 2014811 (MTP)", 0xff68,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * XO Learning Tablet
   * Also Trio Stealth G2 tablet it seems
   */
  { "Acromag Inc.", 0x16d5, "XO Learning Tablet (MTP+ADB)", 0x8005,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Acromag Inc.", 0x16d5, "XO Learning Tablet (MTP)", 0x8006,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * SHARP Corporation
   */
  { "SHARP Corporation", 0x0489, "SH930W", 0xc025,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SHARP Corporation", 0x04dd, "SBM203SH", 0x9661,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "SHARP Corporation", 0x04dd, "SH-06E", 0x96ca,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/192/ */
  { "SHARP Corporation", 0x04dd, "SHV35 AQUOS U", 0x99d2,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1883/ */
  { "SHARP Corporation", 0x04dd, "AndroidOne S5", 0x9c90,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1914/ */
  { "SHARP Corporation", 0x04dd, "S7-SH", 0x9d6e,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * T & A Mobile phones Alcatel and TCT
   */
  { "Alcatel", 0x1bbb, "One Touch 997D (MTP+ADB)", 0x0c02,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Alcatel", 0x1bbb, "One Touch 997D (MTP)", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Alcatel/TCT", 0x1bbb, "6010D/TCL S950", 0x0167,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Alcatel", 0x1bbb, "6030a", 0x0168,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/276/ */
  { "Alcatel", 0x1bbb, "A405DL", 0x901b,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Alcatel/Bouygues", 0x1bbb, "BS472", 0x904d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1304/ */
  { "Alcatel", 0x1bbb, "OneTouch 5042D (MTP)", 0xa00e,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1776/ */
  { "Alcatel", 0x1bbb, "Popo4 (MTP)", 0xa00f,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1605/ */
  { "Alcatel", 0x1bbb, "OneTouch Idol 3 ID2 (MTP)", 0xaf00,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/189/ */
  { "Alcatel", 0x1bbb, "OneTouch Idol 3 small (MTP)", 0xaf2a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1401/ */
  { "Alcatel", 0x1bbb, "OneTouch Idol 3 (MTP)", 0xaf2b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/114/ */
  { "Alcatel", 0x1bbb, "OneTouch 6034R", 0xf003,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Kyocera
   */
  { "Kyocera", 0x0482, "Rise", 0x0571, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1492/ */
  { "Kyocera", 0x0482, "Event", 0x0591, DEVICE_FLAGS_ANDROID_BUGS  & ~DEVICE_FLAG_FORCE_RESET_ON_CLOSE },
  /* https://sourceforge.net/p/libmtp/feature-requests/134/ */
  { "Kyocera", 0x0482, "Torque Model E6715", 0x059a, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/164/ */
  { "Kyocera", 0x0482, "Hydro Elite C6750", 0x073c, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/discussion/535190/thread/6270f5ce/ */
  { "Kyocera", 0x0482, "KYL22", 0x0810, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/270/ */
  { "Kyocera", 0x0482, "Hydro Icon", 0x085e, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1518/ */
  { "Kyocera", 0x0482, "302KC", 0x09fc, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1345/ */
  { "Kyocera", 0x0482, "DuraForce", 0x0979, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1476/ */
  { "Kyocera", 0x0482, "KC-S701", 0x09cb, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/192/ */
  { "Kyocera", 0x0482, "C6740N", 0x0a73, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/220/ */
  { "Kyocera", 0x0482, "Duraforce XD", 0x0a9a, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Hewlett-Packard
   */
  { "Hewlett-Packard", 0x03f0, "Slate 7 4600", 0x5c1d,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Hewlett-Packard", 0x03f0, "Slate 7 2800", 0x5d1d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1366/ */
  { "Hewlett-Packard", 0x03f0, "Slate 10 HD", 0x7e1d,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * MediaTek Inc.
   */
  { "MediaTek Inc", 0x0e8d, "MT5xx and MT6xx SoCs", 0x0050,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1553/ */
  { "Bravis", 0x0e8d, "A401 Neo", 0x0c03,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1422/ */
  { "MediaTek Inc", 0x0e8d, "MT65xx", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1467/ */
  { "elephone", 0x0e8d, "p6000", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/234/ */
  { "DOODGE", 0x0e8d, "X6pro", 0x200a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/289/ */
  { "Jinga", 0x0e8d, "PassPluss", 0x2012, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/79/ */
  { "MediaTek Inc", 0x0e8d, "Elephone P8000", 0x201d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1717/ */
  { "MediaTek Inc", 0x0e8d, "Wiko Sunny", 0x4001,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1855/ */
  { "Vivo", 0x0e8d, "Y21", 0xff00, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Jolla
   */
  { "Jolla", 0x2931, "Sailfish (ID1)", 0x0a01,
      DEVICE_FLAGS_ANDROID_BUGS },

  /* In update 4 the order of devices was changed for
     better OS X / Windows support and another device-id
     got assigned for the MTP */
  { "Jolla", 0x2931, "Sailfish (ID2)", 0x0a05,
      DEVICE_FLAGS_ANDROID_BUGS },

  /* In a later version, the ID changed again. */
  { "Jolla", 0x2931, "Sailfish (ID3)", 0x0a07,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * TCL? Alcatel?
   */
  { "TCL", 0x0451, "Alcatel one touch 986+", 0xd108,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Garmin
   */
  { "Garmin", 0x091e, "Monterra", 0x2585, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1779/ */
  { "Garmin", 0x091e, "Forerunner 645 Music", 0x4b48, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "D2 Air", 0x488b, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/15 */
  { "Garmin", 0x091e, "Fenix 5/5S/5X Plus", 0x4b54, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/271/ */
  { "Garmin", 0x091e, "Vivoactive 3", 0x4bac, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Vivoactive 3 Music LTE", 0x4bfa, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1884/ */
  { "Garmin", 0x091e, "Forerunner 245 Music ", 0x4c05, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Forerunner 945", 0x4c29, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "D2 Delta/Delta S/Delta PX", 0x4c7c, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Vivoactive 4S", 0x4c98, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/51 */
  { "Garmin", 0x091e, "Vivoactive 4", 0x4c99, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1864/ */
  { "Garmin", 0x091e, "Venu", 0x4c9a, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "MARQ", 0x4cae, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "MARQ Aviator", 0x4caf, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Descent Mk2/Mk2i", 0x4cba, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Fenix 6S Pro/Sapphire", 0x4cd8, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1852/ */
  { "Garmin", 0x091e, "Fenix 6 Pro/Sapphire", 0x4cda, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Fenix 6X Pro/Sapphire", 0x4cdb, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1887/ */
  { "Garmin", 0x091e, "Zumo XT", 0x4d9c, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Rey", 0x4daa, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Darth Vader", 0x4dab, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Captain Marvel", 0x4dac, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "First Avenger", 0x4dad, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Forerunner 745", 0x4e05, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Venu Sq Music", 0x4e0c, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Descent Mk2/Mk2i (APAC)", 0x4e76, DEVICE_FLAGS_ANDROID_BUGS }, /* APAC version */
  { "Garmin", 0x091e, "Venu 2s", 0x4e78, DEVICE_FLAGS_ANDROID_BUGS },
  { "Garmin", 0x091e, "Venu Mercedes-Benz Collection", 0x4e9C, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://github.com/libmtp/libmtp/issues/95 */
  { "Garmin", 0x091e, "Fenix 7 Sapphire Solar", 0x4f42, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/299/ */
  { "Garmin", 0x091e, "EPIX 2", 0x4f67, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1920/ */
  { "Garmin", 0x091e, "Tactix 7", 0x5027, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Wacom
   */
  { "Wacom", 0x0531, "Cintiq Companion Hybrid (MTP+ADB)", 0x2001,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Kurio
   */
  { "Kurio", 0x1f3a, "7S", 0x1006,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1521/ */
  { "iRulu", 0x1f3a, "X1s", 0x1007,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1245/ */
  { "DigiLand", 0x1f3a, "DL701Q", 0x0c02,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * bq
   * https://sourceforge.net/p/libmtp/feature-requests/128/
   */
  { "bq", 0x2a47, "Krillin (MTP+ADB)", 0x0c02,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "bq", 0x2a47, "Krillin (MTP)", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/163/ */
  { "bq", 0x2a47, "Aquaris M10 (MTP)", 0x200d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1558/ */
  { "bq", 0x2a47, "Avila Cooler (MTP)", 0x201d,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/224/ */
  { "bq", 0x2a47, "Aquaris X5 (MTP)", 0x3003,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/284/ */
  { "bq", 0x2a47, "Aquaris X2 (MTP)", 0x4ee1,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1311/ */
  { "bq", 0x2a47, "Aquarius E5-4G", 0x7f10,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/181/ */
  { "bq", 0x2a47, "Aquarius X5 (MTP) (ID2)", 0x7f11,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1541/ */
  { "bq", 0x2a47, "Aquarius M5.5", 0x901b,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/269/ */
  { "bq", 0x2a47, "Aquarius U", 0x9039,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1874/ */
  { "bq", 0x2a47, "Aquarius U (2nd id)", 0x903a,
      DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/231/ */
  { "bq", 0x2a47, "U Plus", 0xf003, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1292/ */
  { "Prestigio", 0x29e4, "5505 DUO ", 0x1103, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/260/ */
  { "MediaTek", 0x29e4, "5508 DUO", 0x1201, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1243/ */
  { "Prestigio", 0x29e4, "5504 DUO ", 0x1203, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/141/ */
  { "Prestigio", 0x29e4, "3405 DUO ", 0x3201, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/287/ */
  { "Prestigio", 0x29e4, "Multipad Color 8", 0xb001, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/148/ */
  { "Prestigio", 0x29e4, "Multipad Color 7.0", 0xb003, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1283/ */
  { "Megafon", 0x201e, "MFLogin3T", 0x42ab, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/208/ */
  { "Haier", 0x201e, "CT715", 0xa0c1, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1287/ */
  { "Gensis", 0x040d, "GT-7305 ", 0x885c, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/182/ */
  { "Oppo", 0x22d9, "Find 5", 0x2764, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1207/ */
  { "Oppo", 0x22d9, "Find 7 (ID 1)", 0x2765, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1277/ */
  { "Oppo", 0x22d9, "X9006", 0x2773, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/129/ */
  { "Oppo", 0x22d9, "Find 7 (ID 2)", 0x2774, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1273/ */
  { "Gigabyte", 0x0414, "RCT6773W22 (MTP+ADB)", 0x0c02, DEVICE_FLAGS_ANDROID_BUGS },
  { "Gigabyte", 0x0414, "RCT6773W22 (MTP)", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1264/ */
  { "Meizu", 0x2a45, "MX Phone (MTP)", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1263/ */
  { "Meizu", 0x2a45, "MX Phone (MTP+ADB)", 0x0c02, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1201/ */
  { "Caterpillar", 0x04b7, "Cat S50", 0x88a9, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1525/ */
  { "Caterpillar", 0x04b7, "Cat S50 (2nd ID)", 0x88aa, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1603/ */
  { "Caterpillar", 0x04b7, "Cat S40", 0x88b0, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/253/ */
  { "Caterpillar", 0x04b7, "Cat S30", 0x88b9, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/176/ */
  { "Caterpillar", 0x04b7, "Cat S60", 0x88c0, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1850/ */
  { "Caterpillar", 0x04b7, "Cat S60 (2nd ID)", 0x88c1, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1757/ */
  { "Caterpillar", 0x04b7, "Cat S41", 0x88c6, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/260/ */
  { "Caterpillar", 0x04b7, "Cat S31", 0x88d0, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1814/ */
  { "Caterpillar", 0x04b7, "Cat S61", 0x88d6, DEVICE_FLAGS_ANDROID_BUGS },
  /* owned by Marcus */
  { "Caterpillar", 0x04b7, "Cat S62 Pro", 0x88f1, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/682/ */
  { "Pegatron", 0x1d4d, "Chagall (ADB)", 0x5035, DEVICE_FLAGS_ANDROID_BUGS },
  { "Pegatron", 0x1d4d, "Chagall", 0x5036, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/115/ */
  { "Pegatron", 0x1d4d, "Hudl 2", 0x504a, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/127/ */
  { "Yota", 0x2916, "Phone C9660", 0x9039, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1661/ */
  { "Yota", 0x2916, "Phone", 0x9139, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1229/ */
  { "Yota", 0x2916, "Phone 2", 0x914d, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1267/ */
  { "Yota", 0x2916, "Phone 2 (ID2)", 0xf003, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1212/ */
  { "Fly", 0x2970, "Evo Tech 4", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1865/ */
  { "Fly", 0x2970, "5S ", 0x4002, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1720/ */
  { "Wileyfox", 0x2970, "Spark Plus", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/289/ */
  { "Wileyfox", 0x2970, "Spark", 0x201d, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/146/ */
  { "Wileyfox", 0x2970, "Swift", 0x2281, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/159/ */
  { "Wileyfox", 0x2970, "Swift 2", 0x2282, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1554/ */
  { "Kazam", 0x2970, "Trooper 650 4G", 0x9039, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1303/ */
  { "Megafon", 0x1271, "Login+", 0x2012, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1127/ */
  { "Fly", 0x2970, "iq4415 era style 3", 0x0c02, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1082/ */
  { "Fly", 0x1782, "iq449", 0x4001, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://github.com/libmtp/libmtp/issues/109 */
  { "Alldocube", 0x1782, "Smile X", 0x4003, DEVICE_FLAGS_ANDROID_BUGS },

  /*
  * YU Yureka.
  */
  { "YU Yureka", 0x1ebf, "Vodafone smart turbo 4", 0x7f29, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/249/ */
  { "Coolpad", 0x1ebf, "801ES", 0x7029, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1314/ */
  { "BenQ", 0x1d45, "F5", 0x459d, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1362/ */
  { "TomTom", 0x1390, "Rider 40", 0x5455, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/135/. guessed android. */
  { "OUYA", 0x2836, "Videogame Console", 0x0010, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1383/ */
  { "BLU", 0x0e8d, "Studio HD", 0x2008, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/161/ */
  { "Cubot", 0x0e8d, "X17", 0x201d, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1423/ */
  { "OnePlus", 0x2a70, "ONE A2001", 0x9011, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1910/ */
  { "OnePlus", 0x2a70, "OnePlus 9 5G", 0x9012, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1450/ */
  { "OnePlus", 0x2a70, "OnePlus 2 A2005", 0xf003, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1436/ */
  { "Parrot", 0x19cf, "Bebop Drone", 0x5038, DEVICE_FLAGS_ANDROID_BUGS },

#ifndef _GPHOTO2_INTERNAL_CODE
  /* gphoto lists them in its library.c */
  /*
   * GoPro Action Cams.
   */
  { "GoPro" , 0x2672, "HERO3+ Black", 0x0011, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO", 0x000c, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO4 Silver", 0x000d, DEVICE_FLAG_NONE },
  { "Gopro" , 0x2672, "HERO4 Black", 0x000e, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO4 Session", 0x000f, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO+", 0x0021, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO5 Black", 0x0027, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO5 Session", 0x0029, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO 2018", 0x002d, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "FUSION (back)", 0x0032, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "FUSION (front)", 0x0035, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO6 Black", 0x0037, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO7 Silver", 0x0043, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO7 Black", 0x0047, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO8 Black", 0x0049, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO9 Black", 0x004d, DEVICE_FLAG_NONE },
  { "GoPro" , 0x2672, "HERO10 Black", 0x0056, DEVICE_FLAG_NONE },
#endif

  /* These Ricoh Theta cameras run Android but seem to work
   * without DEVICE_FLAGS_ANDROID_BUGS.
   */
  { "Ricoh", 0x05ca, "Theta V (MTP)", 0x0368, DEVICE_FLAG_NONE },
  { "Ricoh", 0x05ca, "Theta Z1 (MTP)", 0x036d, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/bugs/1490/ */
  { "Marshall" , 0x2ad9, "London", 0x000b, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/feature-requests/257/ */
  { "Fairphone" , 0x2ae5, "Fairphone 2 (ID2)", 0x6764, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/202/ */
  { "Fairphone" , 0x2ae5, "Fairphone 2", 0xf003, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/214/ */
  { "Fairphone" , 0x2ae5, "Fairphone 2 OS", 0x9039, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1700/ */
  { "BLUE" , 0x271d, "Vivo XL", 0x4008, DEVICE_FLAGS_ANDROID_BUGS },
  /*  https://sourceforge.net/p/libmtp/bugs/1512/ */
  { "Allview" , 0x271d, "Energy P5", 0x4016, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/177/ */
  { "BLU" , 0x271d, "Studio Energy X 2 Phone", 0x4016, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1575/ */
  { "BLU" , 0x271d, "Studio Energy 2", 0x4017, DEVICE_FLAGS_ANDROID_BUGS },


  /* https://sourceforge.net/p/libmtp/bugs/1545/ */
  { "Zuk" , 0x2b4c, "Z1", 0x1004, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1596/ */
  { "Zuk" , 0x2b4c, "Z1 (2nd ID)", 0x1005, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/250/ */
  { "Zuk" , 0x2b4c, "Z2 Pro", 0x1013, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1782/ */
  { "Zuk" , 0x2b4c, "Z2", 0x101a, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1574/ */
  { "Letv" , 0x2b0e, "X5001s", 0x1700, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/210/ */
  { "Letv" , 0x2b0e, "1s", 0x1704, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1805/ */
  { "LeMobile" , 0x2b0e, "Le 2", 0x1714, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/274/ */
  { "LeMobile" , 0x2b0e, "Le 2 (ID2)", 0x171b, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/241/ */
  { "Letv" , 0x2b0e, "Leeco Le 1s", 0x1768, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/241/ */
  { "Letv" , 0x2b0e, "Leeco Le 2 Pro", 0x1778, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/220/ */
  { "Letv" , 0x2b0e, "X800 (ID1)", 0x182c, DEVICE_FLAGS_ANDROID_BUGS },
  { "Letv" , 0x2b0e, "X800 (ID2)", 0x1830, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1716/ */
  { "Letv" , 0x2b0e, "Le Max2", 0x1840, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1768/ */
  { "Letv" , 0x2b0e, "Le Max2 (ID2)", 0x1844, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1606/ */
  { "TP-Link" , 0x2357, "Neffos C5 (MTP)", 0x0314, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/197/ */
  { "TP-Link" , 0x2357, "Neffos C5 MAX (MTP)", 0x031a, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/196/ */
  { "TP-Link" , 0x2357, "Neffos Y5L (MTP)", 0x0320, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/195/ */
  { "TP-Link" , 0x2357, "Neffos Y5 (MTP)", 0x0328, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/support-requests/240/ */
  { "TP-Link" , 0x2357, "Neffos X1 (MTP)", 0x033c, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1844/ */
  { "TP-Link" , 0x2357, "Neffos Y5s (MTP)", 0x038c, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1570/ */
  { "Recon Instruments" , 0x2523, "Jet", 0xd209, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/bugs/1571/ */
  { "Recon Instruments" , 0x2523, "Snow2 HUD", 0xd109, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1663/ */
  { "Nextbit" , 0x2c3f, "Robin", 0x0001, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/240/ */
  { "Spreadtrum" , 0x1782, "STK Storm 2e Pluz", 0x4002, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/258/ */
  { "Essential Phone" , 0x2e17, "PH-1a", 0xc030, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/242/ */
  { "Essential Phone" , 0x2e17, "PH-1", 0xc033, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/feature-requests/247/ */
  { "VEGA" , 0x10a9, "R3", 0x1105, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1764/ */
  { "O&P Innovations" , 0x0746, "XDP-100R", 0xa003, DEVICE_FLAGS_ANDROID_BUGS },
  /* https://sourceforge.net/p/libmtp/feature-requests/278/ */
  { "Pioneer" , 0x0746, "XDP-300R", 0xa023, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1786/ */
  { "Niteto" , 0x16c0, "ADF-Drive", 0x0489, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/support-requests/277/ */
  { "Vivo" , 0x2d95, "V11", 0x6002, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1786/ */
  { "Longcheer" , 0x1c9e, "D", 0xf003, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1822/ */
  { "vtevch" , 0x0f88, "Storio Max XL 2.0", 0x0684, DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1889/ */
  { "Tolino" , 0x1f85, "Vision 4 HD", 0x6056 , DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1846/ */
  { "Netronix" , 0x1f85, "E60QH2", 0x6a12 , DEVICE_FLAGS_ANDROID_BUGS },

  /* https://sourceforge.net/p/libmtp/bugs/1871/ */
  { "Doro" , 0x2b43, "Phone 8030 DSB-0010", 0x0006 , DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Other strange stuff.
   */
  { "Isabella", 0x0b20, "Her Prototype", 0xddee, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/bugs/1817/ */
  { "Nox", 0x1e0a, "A1", 0x1001, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/bugs/1893/ */
  { "Nintendo", 0x057e, "Switch Lite", 0x201d, DEVICE_FLAG_NONE },

  /* https://github.com/libmtp/libmtp/issues/72 https://sourceforge.net/p/libmtp/bugs/1895/ */
  { "Mudita", 0x3310, "Pure Phone", 0x0100, DEVICE_FLAG_NONE },

  /* https://sourceforge.net/p/libmtp/bugs/1911/ */
  { "Oculus", 0x2833, "Quest", 0x0183, DEVICE_FLAGS_ANDROID_BUGS },

  /* qemu 3.0.0 hw/usb/dev-mtp.c */
  { "QEMU", 0x46f4, "Virtual MTP", 0x0004, DEVICE_FLAG_NONE }
