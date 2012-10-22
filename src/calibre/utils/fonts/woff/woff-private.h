/* -*- Mode: C; tab-width: 2; indent-tabs-mode: nil; c-basic-offset: 2 -*-
 * ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1/GPL 2.0/LGPL 2.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is WOFF font packaging code.
 *
 * The Initial Developer of the Original Code is Mozilla Corporation.
 * Portions created by the Initial Developer are Copyright (C) 2009
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 *   Jonathan Kew <jfkthame@gmail.com>
 *
 * Alternatively, the contents of this file may be used under the terms of
 * either the GNU General Public License Version 2 or later (the "GPL"), or
 * the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
 * in which case the provisions of the GPL or the LGPL are applicable instead
 * of those above. If you wish to allow use of your version of this file only
 * under the terms of either the GPL or the LGPL, and not to allow others to
 * use your version of this file under the terms of the MPL, indicate your
 * decision by deleting the provisions above and replace them with the notice
 * and other provisions required by the GPL or the LGPL. If you do not delete
 * the provisions above, a recipient may use your version of this file under
 * the terms of any one of the MPL, the GPL or the LGPL.
 *
 * ***** END LICENSE BLOCK ***** */

#ifndef WOFF_PRIVATE_H_
#define WOFF_PRIVATE_H_

#include "woff.h"

/* private definitions used in the WOFF encoder/decoder functions */

/* create an OT tag from 4 characters */
#define TAG(a,b,c,d) ((a)<<24 | (b)<<16 | (c)<<8 | (d))

#define WOFF_SIGNATURE    TAG('w','O','F','F')

#define SFNT_VERSION_CFF  TAG('O','T','T','O')
#define SFNT_VERSION_TT   0x00010000
#define SFNT_VERSION_true TAG('t','r','u','e')

#define TABLE_TAG_DSIG    TAG('D','S','I','G')
#define TABLE_TAG_head    TAG('h','e','a','d')
#define TABLE_TAG_bhed    TAG('b','h','e','d')

#define SFNT_CHECKSUM_CALC_CONST  0xB1B0AFBAU /* from the TT/OT spec */

#ifdef WOFF_MOZILLA_CLIENT
# include <prnetdb.h> 
# define READ32BE(x) PR_ntohl(x)
# define READ16BE(x) PR_ntohs(x)
#else
/* These macros to read values as big-endian only work on "real" variables,
   not general expressions, because of the use of &(x), but they are
   designed to work on both BE and LE machines without the need for a
   configure check. For production code, we might want to replace this
   with something more efficient. */
/* read a 32-bit BigEndian value */
# define READ32BE(x) ( ( (uint32_t) ((uint8_t*)&(x))[0] << 24 ) + \
                       ( (uint32_t) ((uint8_t*)&(x))[1] << 16 ) + \
                       ( (uint32_t) ((uint8_t*)&(x))[2] <<  8 ) + \
                         (uint32_t) ((uint8_t*)&(x))[3]           )
/* read a 16-bit BigEndian value */
# define READ16BE(x) ( ( (uint16_t) ((uint8_t*)&(x))[0] << 8 ) + \
                         (uint16_t) ((uint8_t*)&(x))[1]          )
#endif

#pragma pack(push,1)

typedef struct {
  uint32_t version;
  uint16_t numTables;
  uint16_t searchRange;
  uint16_t entrySelector;
  uint16_t rangeShift;
} sfntHeader;

typedef struct {
  uint32_t tag;
  uint32_t checksum;
  uint32_t offset;
  uint32_t length;
} sfntDirEntry;

typedef struct {
  uint32_t signature;
  uint32_t flavor;
  uint32_t length;
  uint16_t numTables;
  uint16_t reserved;
  uint32_t totalSfntSize;
  uint16_t majorVersion;
  uint16_t minorVersion;
  uint32_t metaOffset;
  uint32_t metaCompLen;
  uint32_t metaOrigLen;
  uint32_t privOffset;
  uint32_t privLen;
} woffHeader;

typedef struct {
  uint32_t tag;
  uint32_t offset;
  uint32_t compLen;
  uint32_t origLen;
  uint32_t checksum;
} woffDirEntry;

typedef struct {
  uint32_t version;
  uint32_t fontRevision;
  uint32_t checkSumAdjustment;
  uint32_t magicNumber;
  uint16_t flags;
  uint16_t unitsPerEm;
  uint32_t created[2];
  uint32_t modified[2];
  int16_t xMin;
  int16_t yMin;
  int16_t xMax;
  int16_t yMax;
  uint16_t macStyle;
  uint16_t lowestRecPpem;
  int16_t fontDirectionHint;
  int16_t indexToLocFormat;
  int16_t glyphDataFormat;
} sfntHeadTable;

#define HEAD_TABLE_SIZE 54 /* sizeof(sfntHeadTable) may report 56 because of alignment */

typedef struct {
  uint32_t offset;
  uint16_t oldIndex;
  uint16_t newIndex;
} tableOrderRec;

#pragma pack(pop)

#endif
