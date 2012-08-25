/**
 * \file music-players.h
 * List of music players as USB ids.
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
  { "Creative", 0x041e, "ZEN Vision", 0x411f,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "Portable Media Center", 0x4123,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Xtra (MTP mode)", 0x4128,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Dell", 0x041e, "DJ (2nd generation)", 0x412f,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Micro (MTP mode)", 0x4130,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Touch (MTP mode)", 0x4131,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Dell", 0x041e, "Dell Pocket DJ (MTP mode)", 0x4132,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
 { "Creative", 0x041e, "ZEN MicroPhoto (alternate version)", 0x4133,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Sleek (MTP mode)", 0x4137,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN MicroPhoto", 0x413c,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Sleek Photo", 0x413d,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Vision:M", 0x413e,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by marazm@o2.pl
  { "Creative", 0x041e, "ZEN V", 0x4150,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by danielw@iinet.net.au
  // This version of the Vision:M needs the no release interface flag,
  // unclear whether the other version above need it too or not.
  { "Creative", 0x041e, "ZEN Vision:M (DVP-HD0004)", 0x4151,
      DEVICE_FLAG_NO_RELEASE_INTERFACE |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by Darel on the XNJB forums
  { "Creative", 0x041e, "ZEN V Plus", 0x4152,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  { "Creative", 0x041e, "ZEN Vision W", 0x4153,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Don't add 0x4155: this is a Zen Stone device which is not MTP
  // Reported by Paul Kurczaba <paul@kurczaba.com>
  { "Creative", 0x041e, "ZEN", 0x4157,
      DEVICE_FLAG_IGNORE_HEADER_ERRORS |
      DEVICE_FLAG_BROKEN_SET_SAMPLE_DIMENSIONS |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by Ringofan <mcroman@users.sourceforge.net>
  { "Creative", 0x041e, "ZEN V 2GB", 0x4158,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by j norment <stormzen@gmail.com>
  { "Creative", 0x041e, "ZEN Mozaic", 0x4161,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by Aaron F. Gonzalez <sub_tex@users.sourceforge.net>
  { "Creative", 0x041e, "ZEN X-Fi", 0x4162,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
  // Reported by farmerstimuli <farmerstimuli@users.sourceforge.net>
  { "Creative", 0x041e, "ZEN X-Fi 3", 0x4169,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_GET_OBJECT_PROPVAL },
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
  // From qnub <qnub@users.sourceforge.net>
  // Guessing on .spl flag
  { "Samsung", 0x04e8, "YP-R2", 0x512d,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_PLAYLIST_SPL_V1 |
      DEVICE_FLAG_UNIQUE_FILENAMES |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
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
  // From Harrison Metzger <harrisonmetz@gmail.com>
  { "Samsung", 0x04e8,
      "Galaxy Nexus/Galaxy S i9000/i9250, Android 4.0 updates", 0x685c,
      DEVICE_FLAGS_ANDROID_BUGS |
      DEVICE_FLAG_PLAYLIST_SPL_V2 },
  // Reported by David Goodenough <dfgdga@users.sourceforge.net>
  // Guessing on flags.
  { "Samsung", 0x04e8, "Galaxy Y", 0x685e,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_LONG_TIMEOUT |
      DEVICE_FLAG_PROPLIST_OVERRIDES_OI	},
  /*
   * This entry (device 0x6860) seems to be used on a *lot* of Samsung
   * Android (gingerbread, 2.3) phones. It is *not* the Android MTP stack
   * but an internal Samsung stack.
   *
   * Popular devices: Galaxy S2 and S3.
   *
   * - It seems that some PTP commands are broken.
   * - Devices seem to have a connection timeout, the session must be
   *   open in about 3 seconds since the device is plugged in, after
   *   that time it will not respond. Thus GUI programs work fine.
   * - Seems also to be used with Galaxy Nexus debug mode and on
   *   US markets for some weird reason.
   *
   * From: Ignacio Martínez <ignacio.martinezrivera@yahoo.es> and others
   */
  { "Samsung", 0x04e8,
      "GT P7310/P7510/N7000/I9070/I9100/I9300 Galaxy Tab 7.7/10.1/S2/S3/Nexus/Note/Y", 0x6860,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_LONG_TIMEOUT |
      DEVICE_FLAG_PROPLIST_OVERRIDES_OI	},
  // Note: ID 0x6865 is some PTP mode! Don't add it.
  // From: Erik Berglund <erikjber@users.sourceforge.net>
  // Logs indicate this needs DEVICE_FLAG_NO_ZERO_READS
  // No Samsung platlists on this device.
  // https://sourceforge.net/tracker/?func=detail&atid=809061&aid=3026337&group_id=158745
  // i5800 duplicate reported by igel <igel-kun@users.sourceforge.net>
  // Guessing this has the same problematic MTP stack as the device
  // above.
  { "Samsung", 0x04e8, "Galaxy S GT-I9000/Galaxy 3 i5800/Kies mode", 0x6877,
      DEVICE_FLAG_UNLOAD_DRIVER |
      DEVICE_FLAG_LONG_TIMEOUT |
      DEVICE_FLAG_PROPLIST_OVERRIDES_OI	},
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
  // Reported by anonymous sourceforge user
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
  // Reported by anonymous sourceforge user
  { "Microsoft", 0x045e, "Kin 1", 0x0640, DEVICE_FLAG_NONE },
  // Reported by anonymous sourceforge user
  { "Microsoft/Sharp/nVidia", 0x045e, "Kin TwoM", 0x0641, DEVICE_FLAG_NONE },
  // Reported by Farooq Zaman (used for all Zunes)
  { "Microsoft", 0x045e, "Zune", 0x0710, DEVICE_FLAG_NONE },

  /*
   * JVC
   */
  // From Mark Veinot
  { "JVC", 0x04f1, "Alneo XA-HD500", 0x6105, DEVICE_FLAG_NONE },

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
  // From a
  { "Philips", 0x0471, "GoGear SA6125/SA6145/SA6185", 0x2002, DEVICE_FLAG_UNLOAD_DRIVER },
  // From anonymous Sourceforge user, not verified to be MTP!
  { "Philips", 0x0471, "GoGear SA3345", 0x2004, DEVICE_FLAG_UNLOAD_DRIVER },
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
  // from XNJB user
  { "Philips", 0x0471, "PSA235", 0x7e01, DEVICE_FLAG_NONE },

  /*
   * Acer
   */
  // Reported by anonymous sourceforge user
  { "Acer", 0x0502, "Iconia TAB A500 (ID1)", 0x3325, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by: Franck VDL <franckv@users.sourceforge.net>
  { "Acer", 0x0502, "Iconia TAB A500 (ID2)", 0x3341, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by: Matthias Arndt <simonsunnyboy@users.sourceforge.net>
  { "Acer", 0x0502, "Iconia TAB A501", 0x3344, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by: anonymous sourceforge user
  { "Acer", 0x0502, "Iconia TAB A100 (ID1)", 0x3348, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by: Arvin Schnell <arvins@users.sourceforge.net>
  { "Acer", 0x0502, "Iconia TAB A100 (ID2)", 0x3349, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Philippe Marzouk <philm@users.sourceforge.net>
  { "Acer", 0x0502, "Iconia TAB A700", 0x3378, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  { "Acer", 0x0502, "Iconia TAB A200 (ID1)", 0x337c, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  { "Acer", 0x0502, "Iconia TAB A200 (ID2)", 0x337d, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by nE0sIghT <ne0sight@users.sourceforge.net>
  { "Acer", 0x0502, "Iconia TAB A510", 0x338a, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * SanDisk
   * several devices (c150 for sure) are definately dual-mode and must
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
  { "iRiver", 0x1006, "Portable Media Center", 0x4002,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x1006, "Portable Media Center", 0x4003,
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
  { "iRiver", 0x4102, "T10a", 0x1117,
    DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST | DEVICE_FLAG_NO_ZERO_READS |
    DEVICE_FLAG_IRIVER_OGG_ALZHEIMER },
  { "iRiver", 0x4102, "T20", 0x1118,
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
   // Reported by Jakub Matraszek <jakub.matraszek@gmail.com>
  { "iRiver", 0x4102, "T5", 0x1153,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
    DEVICE_FLAG_NO_ZERO_READS | DEVICE_FLAG_OGG_IS_UNKNOWN },
  // Reported by pyalex@users.sourceforge.net
  // Guessing that this needs the FLAG_NO_ZERO_READS...
  { "iRiver", 0x4102, "E30", 0x1167,
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
  { "Dell, Inc", 0x413c, "DJ Itty", 0x4500, DEVICE_FLAG_NONE },
  /* Reported by: JR */
  { "Dell, Inc", 0x413c, "Dell Streak 7", 0xb10b, DEVICE_FLAGS_ANDROID_BUGS },

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
  // Reported by Nigel Cunningham <nigel@tuxonice.net>
  // Guessing on Android bugs
  { "Toshiba", 0x0930, "Thrive AT100/AT105", 0x7100,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Archos
   * These devices have some dual-mode interfaces which will really
   * respect the driver unloading, so DEVICE_FLAG_UNLOAD_DRIVER
   * really work on these devices!
   */
  // Reported by Alexander Haertig <AlexanderHaertig@gmx.de>
  { "Archos", 0x0e79, "Gmini XS100", 0x1207, DEVICE_FLAG_UNLOAD_DRIVER },
  // Added by Jan Binder
  { "Archos", 0x0e79, "XS202 (MTP mode)", 0x1208, DEVICE_FLAG_NONE },
  // Reported by gudul1@users.sourceforge.net
  { "Archos", 0x0e79, "104 (MTP mode)", 0x120a, DEVICE_FLAG_NONE },
  // Reported by Archos
  { "Archos", 0x0e79, "204 (MTP mode)", 0x120c, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by anonymous Sourceforge user.
  { "Archos", 0x0e79, "404 (MTP mode)", 0x1301, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Archos
  { "Archos", 0x0e79, "404CAM (MTP mode)", 0x1303, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Etienne Chauchot <chauchot.etienne@free.fr>
  { "Archos", 0x0e79, "504 (MTP mode)", 0x1307, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Archos
  { "Archos", 0x0e79, "604 (MTP mode)", 0x1309, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "604WIFI (MTP mode)", 0x130b, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Kay McCormick <kaym@modsystems.com>
  { "Archos", 0x0e79, "704 mobile dvr", 0x130d, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Archos
  { "Archos", 0x0e79, "704TV (MTP mode)", 0x130f, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "405 (MTP mode)", 0x1311, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Joe Rabinoff
  { "Archos", 0x0e79, "605 (MTP mode)", 0x1313, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Archos
  { "Archos", 0x0e79, "605F (MTP mode)", 0x1315, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "705 (MTP mode)", 0x1319, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "TV+ (MTP mode)", 0x131b, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "105 (MTP mode)", 0x131d, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "405HDD (MTP mode)", 0x1321, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Jim Krehl <jimmuhk@users.sourceforge.net>
  { "Archos", 0x0e79, "5 (MTP mode)", 0x1331, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Adrien Guichard <tmor@users.sourceforge.net>
  { "Archos", 0x0e79, "5 (MTP mode)", 0x1333, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Archos
  { "Archos", 0x0e79, "7 (MTP mode)", 0x1335, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "SPOD (MTP mode)", 0x1341, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "5S IT (MTP mode)", 0x1351, DEVICE_FLAG_UNLOAD_DRIVER },
  { "Archos", 0x0e79, "5H IT (MTP mode)", 0x1357, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by anonymous Sourceforge user
  { "Archos", 0x0e79, "8o G9 (MTP mode)", 0x1508, DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Clément <clemvangelis@users.sourceforge.net>
  { "Archos", 0x0e79, "8o G9 Turbo (MTP mode)", 0x1509,
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by Thackert <hackertenator@users.sourceforge.net>
  { "Archos", 0x0e79, "80G9", 0x1518, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Till <Till@users.sourceforge.net>
  { "Archos", 0x0e79, "101 G9", 0x1528, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  { "Archos", 0x0e79, "101 G9 (v2)", 0x1529, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  { "Archos", 0x0e79, "101 G9 Turbo 250 HD", 0x1538,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  { "Archos", 0x0e79, "101 G9 Turbo", 0x1539, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  { "Archos", 0x0e79, "70it2 (mode 1)", 0x1568, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Sebastien ROHAUT
  { "Archos", 0x0e79, "70it2 (mode 2)", 0x1569, DEVICE_FLAGS_ANDROID_BUGS },

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
   * Canon
   * These are actually cameras, but they have a Microsoft device descriptor
   * and reports themselves as supporting the MTP extension.
   */
  { "Canon", 0x04a9, "Ixus Digital 700 (PTP/MTP mode)", 0x30f2,
     DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  { "Canon", 0x04a9, "PowerShot A640 (PTP/MTP mode)", 0x3139,
     DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // From Peter <pjeremy@users.sourceforge.net>
  { "Canon", 0x04a9, "PowerShot SX20IS (PTP/MTP mode)", 0x31e4,
     DEVICE_FLAG_NONE },

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
  // Reported by Richard Wall <richard@the-moon.net>
  { "Nokia", 0x05c6, "5530 Xpressmusic", 0x0229, DEVICE_FLAG_NONE },
  // Reported by anonymous SourceForge user
  // One thing stated by reporter (Nokia model) another by the detect log...
  { "Nokia/Verizon", 0x05c6, "6205 Balboa/Verizon Music Phone", 0x3196, DEVICE_FLAG_NONE },


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
   * NTT DoCoMo
   */
  { "FOMA", 0x04c5, "F903iX HIGH-SPEED", 0x1140, DEVICE_FLAG_NONE },

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
  { "Medion", 0x066f, "MD8333", 0x8550,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
  // Reported by anonymous SourceForge user
  { "Medion", 0x066f, "MD8333", 0x8588,
    DEVICE_FLAG_UNLOAD_DRIVER | DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST },
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
    DEVICE_FLAG_UNLOAD_DRIVER },

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
  // From anonymous SourceForge user
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
  // Reported by anonymous sourceforge user
  { "LG Electronics Inc.", 0x1004, "KM900", 0x6132,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by anonymous sourceforge user
  { "LG Electronics Inc.", 0x1004, "LG8575", 0x619a,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER },
  // Reported by anonymous sourceforge user
  { "LG Electronics Inc.", 0x1004, "V909 G-Slate", 0x61f9,
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST |
      DEVICE_FLAG_UNLOAD_DRIVER },

  /*
   * Sony
   * It could be that these PIDs are one-per hundred series, so
   * NWZ-A8xx is 0325, NWZ-S5xx is 0x326 etc. We need more devices
   * reported to see a pattern here.
   */
  // Reported by Alessandro Radaelli <alessandro.radaelli@aruba.it>
  { "Sony", 0x054c, "Walkman NWZ-A815/NWZ-A818", 0x0325,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by anonymous Sourceforge user.
  { "Sony", 0x054c, "Walkman NWZ-S516", 0x0326,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Endre Oma <endre.88.oma@gmail.com>
  { "Sony", 0x054c, "Walkman NWZ-S615F/NWZ-S616F/NWZ-S618F", 0x0327,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Jean-Marc Bourguet <jm@bourguet.org>
  { "Sony", 0x054c, "Walkman NWZ-S716F", 0x035a,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Anon SF User / Anthon van der Neut <avanderneut@avid.com>
  { "Sony", 0x054c, "Walkman NWZ-A826/NWZ-A828/NWZ-A829", 0x035b,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Niek Klaverstijn <niekez@users.sourceforge.net>
  { "Sony", 0x054c, "Walkman NWZ-A726/NWZ-A728/NWZ-A768", 0x035c,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Mehdi AMINI <mehdi.amini - at - ulp.u-strasbg.fr>
  { "Sony", 0x054c, "Walkman NWZ-B135", 0x036e,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by <tiagoboldt@users.sourceforge.net>
  { "Sony", 0x054c, "Walkman NWZ-E436F", 0x0385,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Michael Wilkinson
  { "Sony", 0x054c, "Walkman NWZ-W202", 0x0388,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Ondrej Sury <ondrej@sury.org>
  { "Sony", 0x054c, "Walkman NWZ-S739F", 0x038c,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Marco Filipe Nunes Soares Abrantes Pereira <marcopereira@ua.pt>
  { "Sony", 0x054c, "Walkman NWZ-S638F", 0x038e,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Elliot <orwells@users.sourceforge.net>
  { "Sony", 0x054c, "Walkman NWZ-X1050B/NWZ-X1060B",
    0x0397, DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Silvio J. Gutierrez <silviogutierrez@users.sourceforge.net>
  { "Sony", 0x054c, "Walkman NWZ-X1051/NWZ-X1061", 0x0398,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Gregory Boddin <gregory@siwhine.net>
  { "Sony", 0x054c, "Walkman NWZ-B142F", 0x03d8,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Rick Warner <rick@reptileroom.net>
  { "Sony", 0x054c, "Walkman NWZ-E344", 0x03fc,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Jonathan Stowe <gellyfish@users.sourceforge.net>
  { "Sony", 0x054c, "Walkman NWZ-E445", 0x03fd,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Anonymous SourceForge user
  { "Sony", 0x054c, "Walkman NWZ-S545", 0x03fe,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "Walkman NWZ-A845", 0x0404,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by anonymous SourceForge user
  { "Sony", 0x054c, "Walkman NWZ-W252B", 0x04bb,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Suspect this device has strong DRM features
  // See https://answers.launchpad.net/ubuntu/+source/libmtp/+question/149587
  { "Sony", 0x054c, "Walkman NWZ-B153F", 0x04be,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  { "Sony", 0x054c, "Walkman NWZ-E354", 0x04cb,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Toni Burgarello
  { "Sony", 0x054c, "Walkman NWZ-S754", 0x04cc,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by dmiceman
  { "Sony", 0x054c, "NWZ-B163F", 0x059a,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by anonymous Sourceforge user
  // guessing on device flags...
  { "Sony", 0x054c, "Walkman NWZ-E464", 0x05a6,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by Jan Rheinlaender <jrheinlaender@users.sourceforge.net>
  { "Sony", 0x054c, "NWZ-S765", 0x05a8,
      DEVICE_FLAGS_SONY_NWZ_BUGS },
  // Reported by ghalambaz <ghalambaz@users.sourceforge.net>
  { "Sony", 0x054c, "Sony Tablet S1", 0x05b4,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Anonymous SourceForge user
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
   * ADB = Android Debug Bridhe Protocol
   * CDC = Communications Device Class, Internet Sharing
   *
   * 0x0nnn = MTP
   * 0x4nnn = MTP + UMS (for CD-ROM)
   * 0x5nnn = MTP + ADB
   * 0x6nnn = UMS + ADB
   * 0x7nnn = MTP + CDC
   * 0x8nnn = MTP + CDC + ADB
   * 0xannn = MTP + UMS + ?
   * 0xennn = UMS only
   *
   * The SonyEricsson and SONY devices have (at least)two deployed MTP
   * stacks: Aricent and Android. These have different bug flags, and
   * sometimes the same device has firmware upgrades moving it from
   * the Aricent to Android MTP stack without changing the device
   * VID+PID (first observed on the SK17i Xperia Mini Pro), so the
   * detection has to be more elaborate. The code in libmtp.c will do
   * this and assign the proper bug flags (hopefully).
   * That is why DEVICE_FLAG_NONE is used for these devices.
   */
  // Reported by Jonas Salling <>
  // Erroneous MTP implementation seems to be from Aricent, returns
  // broken transaction ID.
  { "SonyEricsson", 0x0fce, "LT15i (Xperia arc S)", 0x014f,
      DEVICE_FLAG_NONE },
  // Reported by Eamonn Webster <eweb@users.sourceforge.net>
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "MT11i Xperia Neo", 0x0156,
      DEVICE_FLAG_NONE },
  // Reported by Alejandro DC <Alejandro_DC@users.sourceforge.ne>
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "MK16i Xperia", 0x015a,
      DEVICE_FLAG_NONE },
  // Reported by <wealas@users.sourceforge.net>
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "ST18a Xperia Ray", 0x0161,
      DEVICE_FLAG_NONE },
  /*
   * Reported by StehpanKa <stehp@users.sourceforge.net>
   * Android with homebrew MTP stack in one firmware, possibly Aricent
   * Android with Android stack in another one, so let the run-time
   * detector look up the device bug flags, set to NONE initially.
   */
  { "SonyEricsson", 0x0fce, "SK17i Xperia Mini Pro", 0x0166,
      DEVICE_FLAG_NONE },
  // Reported by hdhoang <hdhoang@users.sourceforge.net>
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "ST15i Xperia Mini", 0x0167,
      DEVICE_FLAG_NONE },
  // Reported by Paul Taylor
  { "SONY", 0x0fce, "Xperia S", 0x0169,
      DEVICE_FLAG_NO_ZERO_READS },
  // Reported by Bruno Basilio <bbasilio@users.sourceforge.net>
  { "SONY", 0x0fce, "WT19i Live Walkman", 0x016d,
      DEVICE_FLAG_NONE },
  // Reported by Christoffer Holmstedt <christofferh@users.sourceforge.net>
  { "SONY", 0x0fce, "ST21i Xperia Tipo", 0x0170,
      DEVICE_FLAG_NONE },
  // Reported by equaeghe <equaeghe@users.sourceforge.net>
  { "SONY", 0x0fce, "ST15i Xperia U", 0x0171,
      DEVICE_FLAG_NONE },
  // Reported by Ondra Lengal
  { "SONY", 0x0fce, "Xperia P", 0x0172,
      DEVICE_FLAG_NONE },
  // Guessing on this one
  { "SONY", 0x0fce, "LT26w Xperia Acro S", 0x0176,
      DEVICE_FLAG_NONE },

  /*
   * MTP+MSC personalities of MTP devices (see above)
   */
  // Guessing on this one
  { "SONY", 0x0fce, "Xperia S (MTP+ADB mode)", 0x4169,
      DEVICE_FLAG_NO_ZERO_READS },
  // Guessing on this one
  { "SONY", 0x0fce, "ST21i Xperia Tipo (MTP+MSC mode)", 0x4170,
      DEVICE_FLAG_NONE },
  // Reported by equaeghe <equaeghe@users.sourceforge.net>
  { "SONY", 0x0fce, "ST25i Xperia U (MTP+MSC mode)", 0x4171,
      DEVICE_FLAG_NONE },
  // Guessing on this one
  { "SONY", 0x0fce, "Xperia P (MTP+MSC mode)", 0x4172,
      DEVICE_FLAG_NONE },
  // Guessing on this one
  { "SONY", 0x0fce, "LT26w Xperia Acro S (MTP+MSC mode)", 0x4176,
      DEVICE_FLAG_NONE },

  /*
   * MTP+ADB personalities of MTP devices (see above)
   */
  // Reported by anonymous sourceforge user
  // Suspect Aricent stack, guessing on these bug flags
  { "SonyEricsson", 0x0fce, "LT15i Xperia Arc (MTP+ADB mode)", 0x514f,
      DEVICE_FLAG_NONE },
  // Reported by Michael K. <kmike@users.sourceforge.net>
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "MT11i Xperia Neo (MTP+ADB mode)", 0x5156,
      DEVICE_FLAG_NONE },
  // Reported by Jean-François  B. <changi67@users.sourceforge.net>
  { "SONY", 0x0fce, "Xperia S (MTP+ADB mode)", 0x5169,
      DEVICE_FLAG_NO_ZERO_READS },
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "MK16i Xperia (MTP+ADB mode)", 0x515a,
      DEVICE_FLAG_NONE },
  // Reported by Eduard Bloch <blade@debian.org>
  // Xperia Ray (2012), SE Android 2.3.4, flags from ST18a
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "ST18i Xperia Ray (MTP+ADB mode)", 0x5161,
      DEVICE_FLAG_NONE },
  // Reported by StehpanKa <stehp@users.sourceforge.net>
  // Android with homebrew MTP stack, possibly Aricent
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "SK17i Xperia Mini Pro (MTP+ADB mode)", 0x5166,
      DEVICE_FLAG_NONE },
  // Android with homebrew MTP stack, possibly Aricent
  // Runtime detect the Aricent or Android stack
  { "SonyEricsson", 0x0fce, "ST15i Xperia Mini (MTP+ADB mode)", 0x5167,
      DEVICE_FLAG_NONE },
  { "SonyEricsson", 0x0fce, "SK17i Xperia Mini Pro (MTP+? mode)", 0x516d,
      DEVICE_FLAG_NONE },
  // Guessing on this one
  { "SONY", 0x0fce, "ST21i Xperia Tipo (MTP+ADB mode)", 0x5170,
      DEVICE_FLAG_NONE },
  // Reported by equaeghe <equaeghe@users.sourceforge.net>
  { "SONY", 0x0fce, "ST25i Xperia U (MTP+ADB mode)", 0x5171,
      DEVICE_FLAG_NONE },
  // Reported by Ondra Lengál
  { "SONY", 0x0fce, "Xperia P (MTP+ADB mode)", 0x5172,
      DEVICE_FLAG_NONE },
  // Reported by Ah Hong <hongster@users.sourceforge.net>
  { "SONY", 0x0fce, "LT26w Xperia Acro S (MTP+ADB mode)", 0x5176,
      DEVICE_FLAG_NONE },
  { "SONY", 0x0fce, "MT27i Xperia Sola (MTP+MSC+? mode)", 0xa173,
      DEVICE_FLAG_NONE },

  /*
   * Motorola
   * Assume DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST on all of these.
   */
  // Reported by David Boyd <tiggrdave@users.sourceforge.net>
  { "Motorola", 0x22b8, "V3m/V750 verizon", 0x2a65,
      DEVICE_FLAG_BROKEN_SET_OBJECT_PROPLIST |
      DEVICE_FLAG_BROKEN_MTPGETOBJPROPLIST_ALL },
  // Reported by Jader Rodrigues Simoes <jadersimoes@users.sourceforge.net>
  { "Motorola", 0x22b8, "Xoom 2 Media Edition (ID2)", 0x41cf,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Steven Roemen <sdroemen@users.sourceforge.net>
  { "Motorola", 0x22b8, "Droid X/MB525 (Defy)", 0x41d6,
      DEVICE_FLAG_NONE },
  // Reported by anonymous user
  { "Motorola", 0x22b8, "Milestone / Verizon Droid", 0x41dc,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous user
  { "Motorola", 0x22b8, "DROID2", 0x42a7,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Motorola", 0x22b8, "Xoom 2 Media Edition", 0x4311,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by  B,H,Kissinger <mrkissinger@users.sourceforge.net>
  { "Motorola", 0x22b8, "XT912/XT928", 0x4362,
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
  // Reported by Google Inc's Yavor Goulishev <yavor@google.com>
  // Android 3.0 MTP stack seems to announce that it supports the
  // list operations, but they do not work?
  { "Motorola", 0x22b8, "Xoom (ID 1)", 0x70a8, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  // "carried by C Spire and other CDMA US carriers"
  { "Motorola", 0x22b8, "Milestone X2", 0x70ca, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Google
   * These guys lend their Vendor ID to anyone who comes down the
   * road to produce an Android tablet it seems... The Vendor ID
   * was originally used for Nexus phones
   */
  { "Google Inc (for Sony)", 0x18d1, "S1", 0x05b3,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Google Inc (for Barnes & Noble)", 0x18d1, "Nook Color", 0x2d02,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Google Inc (for Asus)", 0x18d1, "TF101 Transformer", 0x4e0f,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Laurent Artaud <laurenta@users.sourceforge.net>
  { "Google Inc (for Samsung)", 0x18d1, "Nexus S", 0x4e21,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Chris Smith <tcgsmythe@users.sourceforge.net>
  { "Google Inc (for Asus)", 0x18d1, "Nexus 7 (mode 1)", 0x4e41,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Michael Hess <mhess126@gmail.com>
  { "Google Inc (for Asus)", 0x18d1, "Nexus 7 (mode 2)", 0x4e42,
      DEVICE_FLAGS_ANDROID_BUGS },
  // WiFi-only version of Xoom
  // See: http://bugzilla.gnome.org/show_bug.cgi?id=647506
  { "Google Inc (for Motorola)", 0x18d1, "Xoom (MZ604)", 0x70a8,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Motorola)", 0x22b8, "Xoom (ID 2)", 0x70a9,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Toshiba)", 0x18d1, "Thrive 7/AT105", 0x7102,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Google Inc (for Lenovo)", 0x18d1, "Ideapad K1", 0x740a,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Another OEM for Medion
  { "Google Inc (for Medion)", 0x18d1, "MD99000 (P9514)", 0xb00a,
      DEVICE_FLAGS_ANDROID_BUGS },
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
  { "Haier", 0x1302, "Ibiza Rhapsody", 0x1016, DEVICE_FLAG_NONE },
  // This is the 4/8 GiB model
  { "Haier", 0x1302, "Ibiza Rhapsody", 0x1017, DEVICE_FLAG_NONE },

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

  /*
   * Nextar
   */
  { "Nextar", 0x0402, "MA715A-8R", 0x5668, DEVICE_FLAG_NONE },

  /*
   * Coby
   */
  { "Coby", 0x1e74, "COBY MP705", 0x6512, DEVICE_FLAG_NONE },

  /*
   * Apple devices, which are not MTP natively but can be made to speak MTP
   * using PwnTunes (http://www.pwntunes.net/)
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

  // Reported by anonymous SourceForge user, also reported as
  // Pantech Crux, claming to be:
  // Manufacturer: Qualcomm
  // Model: Windows Simulator
  // Device version: Qualcomm MTP1.0
  { "Curitel Communications, Inc.", 0x106c,
      "Verizon Wireless Device", 0x3215, DEVICE_FLAG_NONE },
  // Reported by: Jim Hanrahan <goshawkjim@users.sourceforge.net>
  { "Pantech", 0x106c, "Crux", 0xf003, DEVICE_FLAG_NONE },

  /*
   * Asus
   */
  // Reported by Glen Overby
  { "Asus", 0x0b05, "TF300 Transformer", 0x4c80,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by jaile <jaile@users.sourceforge.net>
  { "Asus", 0x0b05, "TF300 Transformer (USB debug mode)", 0x4c81,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Asus", 0x0b05, "TF201 Transformer Prime (keyboard dock)", 0x4d00,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF201 Transformer Prime (tablet only)", 0x4d01,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TFXXX Transformer Prime (unknown version)", 0x4d04,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous Sourceforge user
  { "Asus", 0x0b05, "TF101 Eeepad Slider", 0x4e01,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF101 Eeepad Transformer", 0x4e0f,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Asus", 0x0b05, "TF101 Eeepad Transformer (debug mode)", 0x4e1f,
      DEVICE_FLAGS_ANDROID_BUGS },


  /*
   * Lenovo
   */
  // Reported by Richard Körber <shredzone@users.sourceforge.net>
  { "Lenovo", 0x17ef, "K1", 0x740a,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous sourceforge user
  // Adding Android default bug flags since it appears to be an Android
  { "Lenovo", 0x17ef, "ThinkPad Tablet", 0x741c,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Huawei
   */
  // Reported by anonymous SourceForge user
  { "Huawei", 0x12d1, "Honor U8860", 0x1051, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous SourceForge user
  { "Huawei", 0x12d1, "Mediapad (mode 0)", 0x360f, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Bearsh <bearsh@users.sourceforge.net>
  { "Huawei", 0x12d1, "Mediapad (mode 1)", 0x361f, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * ZTE
   * Android devices reported by junwang <lovewjlove@users.sourceforge.net>
   */
  { "ZTE", 0x19d2, "V55 ID 1", 0x0244, DEVICE_FLAGS_ANDROID_BUGS },
  { "ZTE", 0x19d2, "V55 ID 2", 0x0245, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * HTC (High Tech Computer Corp)
   */
  { "HTC", 0x0bb4, "Zopo ZP100 (ID1)", 0x0c02,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Steven Eastland <grassmonk@users.sourceforge.net>
  { "HTC", 0x0bb4, "EVO 4G LTE", 0x0c93,
      DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by Steven Eastland <grassmonk@users.sourceforge.net>
  { "HTC", 0x0bb4, "EVO 4G LTE (second ID)", 0x0ca8,
      DEVICE_FLAGS_ANDROID_BUGS },
  // These identify themselves as "cm_tenderloin", fun...
  // Done by HTC for HP I guess.
  { "Hewlett-Packard", 0x0bb4, "HP Touchpad", 0x685c,
      DEVICE_FLAGS_ANDROID_BUGS },
  { "Hewlett-Packard", 0x0bb4, "HP Touchpad (debug mode)",
      0x6860, DEVICE_FLAGS_ANDROID_BUGS },
  // Reported by anonymous SourceForge user
  { "HTC", 0x0bb4, "Zopo ZP100 (ID2)", 0x2008,
      DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * NEC
   */
  { "NEC", 0x0409, "FOMA N01A", 0x0242, DEVICE_FLAG_NONE },

  /*
   * nVidia
   */
  // Found on Internet forum
  { "nVidia", 0x0955, "CM9-Adam", 0x70a9, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Vizio
   */
  // Reported by Michael Gurski <gurski@users.sourceforge.net>
  { "Vizio", 0x0489, "VTAB1008", 0xe040, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Viewpia, bq...
   * Seems like some multi-branded OEM product.
   */
  { "Various", 0x2207, "Viewpia DR/bq Kepler", 0x0001, DEVICE_FLAGS_ANDROID_BUGS },

  /*
   * Other strange stuff.
   */
  { "Isabella", 0x0b20, "Her Prototype", 0xddee, DEVICE_FLAG_NONE }
