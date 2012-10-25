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

#ifndef WOFF_H_
#define WOFF_H_

/* API for the WOFF encoder and decoder */

#ifdef _MSC_VER /* MS VC lacks inttypes.h
                   but we can make do with a few definitons here */
typedef char           int8_t;
typedef short          int16_t;
typedef int            int32_t;
typedef unsigned char  uint8_t;
typedef unsigned short uint16_t;
typedef unsigned int   uint32_t;
#else
#include <inttypes.h>
#endif

#include <stdio.h> /* only for FILE, needed for woffPrintStatus */

/* error codes returned in the status parameter of WOFF functions */
enum {
  /* Success */
  eWOFF_ok = 0,

  /* Errors: no valid result returned */
  eWOFF_out_of_memory = 1,       /* malloc or realloc failed */
  eWOFF_invalid = 2,             /* invalid input file (e.g., bad offset) */
  eWOFF_compression_failure = 3, /* error in zlib call */
  eWOFF_bad_signature = 4,       /* unrecognized file signature */
  eWOFF_buffer_too_small = 5,    /* the provided buffer is too small */
  eWOFF_bad_parameter = 6,       /* bad parameter (e.g., null source ptr) */
  eWOFF_illegal_order = 7,       /* improperly ordered chunks in WOFF font */

  /* Warnings: call succeeded but something odd was noticed.
     Multiple warnings may be OR'd together. */
  eWOFF_warn_unknown_version = 0x0100,   /* unrecognized version of sfnt,
                                            not standard TrueType or CFF */
  eWOFF_warn_checksum_mismatch = 0x0200, /* bad checksum, use with caution;
                                            any DSIG will be invalid */
  eWOFF_warn_misaligned_table = 0x0400,  /* table not long-aligned; fixing,
                                            but DSIG will be invalid */
  eWOFF_warn_trailing_data = 0x0800,     /* trailing junk discarded,
                                            any DSIG may be invalid */
  eWOFF_warn_unpadded_table = 0x1000,    /* sfnt not correctly padded,
                                            any DSIG may be invalid */
  eWOFF_warn_removed_DSIG = 0x2000       /* removed digital signature
                                            while fixing checksum errors */
};

/* Note: status parameters must be initialized to eWOFF_ok before calling
   WOFF functions. If the status parameter contains an error code,
   functions will return immediately. */

#define WOFF_SUCCESS(status) (((uint32_t)(status) & 0xff) == eWOFF_ok)
#define WOFF_FAILURE(status) (!WOFF_SUCCESS(status))
#define WOFF_WARNING(status) ((uint32_t)(status) & ~0xff)

#ifdef __cplusplus
extern "C" {
#endif

#ifndef WOFF_DISABLE_ENCODING

/*****************************************************************************
 * Returns a new malloc() block containing the encoded data, or NULL on error;
 * caller should free() this when finished with it.
 * Returns length of the encoded data in woffLen.
 * The new WOFF has no metadata or private block;
 * see the following functions to update these elements.
 */
const uint8_t * woffEncode(const uint8_t * sfntData, uint32_t sfntLen,
                           uint16_t majorVersion, uint16_t minorVersion,
                           uint32_t * woffLen, uint32_t * status);


/*****************************************************************************
 * Add the given metadata block to the WOFF font, replacing any existing
 * metadata block. The block will be zlib-compressed.
 * Metadata is required to be valid XML (use of UTF-8 is recommended),
 * though this function does not currently check this.
 * The woffData pointer must be a malloc() block (typically from woffEncode);
 * it will be freed by this function and a new malloc() block will be returned.
 * Returns NULL if an error occurs, in which case the original WOFF is NOT freed.
 */
const uint8_t * woffSetMetadata(const uint8_t * woffData, uint32_t * woffLen,
                                const uint8_t * metaData, uint32_t metaLen,
                                uint32_t * status);


/*****************************************************************************
 * Add the given private data block to the WOFF font, replacing any existing
 * private block. The block will NOT be zlib-compressed.
 * Private data may be any arbitrary block of bytes; it may be externally
 * compressed by the client if desired.
 * The woffData pointer must be a malloc() block (typically from woffEncode);
 * it will be freed by this function and a new malloc() block will be returned.
 * Returns NULL if an error occurs, in which case the original WOFF is NOT freed.
 */
const uint8_t * woffSetPrivateData(const uint8_t * woffData, uint32_t * woffLen,
                                   const uint8_t * privData, uint32_t privLen,
                                   uint32_t * status);

#endif /* WOFF_DISABLE_ENCODING */

/*****************************************************************************
 * Returns the size of buffer needed to decode the font (or zero on error).
 */
uint32_t woffGetDecodedSize(const uint8_t * woffData, uint32_t woffLen,
                            uint32_t * pStatus);


/*****************************************************************************
 * Decodes WOFF font to a caller-supplied buffer of size bufferLen.
 * Returns the actual size of the decoded sfnt data in pActualSfntLen
 * (must be <= bufferLen, otherwise an error will be returned).
 */
void woffDecodeToBuffer(const uint8_t * woffData, uint32_t woffLen,
                        uint8_t * sfntData, uint32_t bufferLen,
                        uint32_t * pActualSfntLen, uint32_t * pStatus);


/*****************************************************************************
 * Returns a new malloc() block containing the decoded data, or NULL on error;
 * caller should free() this when finished with it.
 * Returns length of the decoded data in sfntLen.
 */
const uint8_t * woffDecode(const uint8_t * woffData, uint32_t woffLen,
                           uint32_t * sfntLen, uint32_t * status);


/*****************************************************************************
 * Returns a new malloc() block containing the metadata from the WOFF font,
 * or NULL if an error occurs or no metadata is present.
 * Length of the metadata is returned in metaLen.
 * The metadata is decompressed before returning.
 */
const uint8_t * woffGetMetadata(const uint8_t * woffData, uint32_t woffLen,
                                uint32_t * metaLen, uint32_t * status);


/*****************************************************************************
 * Returns a new malloc() block containing the private data from the WOFF font,
 * or NULL if an error occurs or no private data is present.
 * Length of the private data is returned in privLen.
 */
const uint8_t * woffGetPrivateData(const uint8_t * woffData, uint32_t woffLen,
                                   uint32_t * privLen, uint32_t * status);


/*****************************************************************************
 * Returns the font version numbers from the WOFF font in the major and minor
 * parameters.
 * Check the status result to know if the function succeeded.
 */
void woffGetFontVersion(const uint8_t * woffData, uint32_t woffLen,
                        uint16_t * major, uint16_t * minor,
                        uint32_t * status);


/*****************************************************************************
 * Utility to print warning and/or error status to the specified FILE*.
 * The prefix string will be prepended to each line (ok to pass NULL if no
 * prefix is wanted).
 * (Provides terse English messages only, not intended for end-user display;
 * user-friendly tools should map the status codes to their own messages.)
 */
void woffPrintStatus(FILE * f, uint32_t status, const char * prefix);


#ifdef __cplusplus
}
#endif

#endif
