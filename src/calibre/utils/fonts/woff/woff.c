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

#include "woff-private.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zlib.h>

#ifdef WOFF_MOZILLA_CLIENT /* define this when building as part of Gecko */
# include "prmem.h"
# define malloc  PR_Malloc
# define realloc PR_Realloc
# define free    PR_Free
#endif

/*
 * Just simple whole-file encoding and decoding functions; a more extensive
 * WOFF library could provide support for accessing individual tables from a
 * compressed font, alternative options for memory allocation/ownership and
 * error handling, etc.
 */

/* on errors, each function sets a status variable and jumps to failure: */
#undef FAIL
#define FAIL(err) do { status |= err; goto failure; } while (0)

/* adjust an offset for longword alignment */
#define LONGALIGN(x) (((x) + 3) & ~3)

static int
compareOffsets(const void * lhs, const void * rhs)
{
  const tableOrderRec * a = (const tableOrderRec *) lhs;
  const tableOrderRec * b = (const tableOrderRec *) rhs;
  /* don't simply return a->offset - b->offset because these are unsigned
     offset values; could convert to int, but possible integer overflow */
  return a->offset > b->offset ? 1 :
         a->offset < b->offset ? -1 :
         0;
}

#ifndef WOFF_MOZILLA_CLIENT

/******************************************************************/
/* * * * * * * * * * * * * * ENCODING * * * * * * * * * * * * * * */
/******************************************************************/

static uint32_t
calcChecksum(const sfntDirEntry * dirEntry,
             const uint8_t * sfntData, uint32_t sfntLen)
{
  /* just returns zero on errors, they will be detected again elsewhere */
  const uint32_t * csumPtr;
  const uint32_t * csumEnd;
  uint32_t csum = 0;
  uint32_t length = LONGALIGN(READ32BE(dirEntry->length));
  uint32_t offset = READ32BE(dirEntry->offset);
  uint32_t tag;
  if ((offset & 3) != 0) {
    return csum;
  }
  if (length > sfntLen || offset > sfntLen - length) {
    return csum;
  }
  csumPtr = (const uint32_t *) (sfntData + offset);
  csumEnd = csumPtr + length / 4;
  while (csumPtr < csumEnd) {
    csum += READ32BE(*csumPtr);
    csumPtr++;
  }
  tag = READ32BE(dirEntry->tag);
  if (tag == TABLE_TAG_head || tag == TABLE_TAG_bhed) {
    const sfntHeadTable * head;
    if (length < HEAD_TABLE_SIZE) {
      return 0;
    }
    head = (const sfntHeadTable *)(sfntData + offset);
    csum -= READ32BE(head->checkSumAdjustment);
  }
  return csum;
}

const uint8_t *
woffEncode(const uint8_t * sfntData, uint32_t sfntLen,
           uint16_t majorVersion, uint16_t minorVersion,
           uint32_t * woffLen, uint32_t * pStatus)
{
  uint8_t * woffData = NULL;
  tableOrderRec * tableOrder = NULL;

  uint32_t tableOffset;
  uint32_t totalSfntSize;

  uint16_t numOrigTables;
  uint16_t numTables;
  uint16_t tableIndex;
  uint16_t order;
  const sfntDirEntry * sfntDir;
  uint32_t tableBase;
  uint32_t checkSumAdjustment = 0;
  woffHeader * newHeader;
  uint32_t tag = 0;
  uint32_t removedDsigSize = 0;
  uint32_t status = eWOFF_ok;

  const sfntHeader * header = (const sfntHeader *) (sfntData);
  const sfntHeadTable * head = NULL;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return NULL;
  }

  if (READ32BE(header->version) != SFNT_VERSION_TT &&
      READ32BE(header->version) != SFNT_VERSION_CFF &&
      READ32BE(header->version) != SFNT_VERSION_true) {
    status |= eWOFF_warn_unknown_version;
  }

  numOrigTables = READ16BE(header->numTables);
  sfntDir = (const sfntDirEntry *) (sfntData + sizeof(sfntHeader));

  for (tableIndex = 0; tableIndex < numOrigTables; ++tableIndex) {
    /* validate table checksums, to figure out if we need to drop DSIG;
       also check that table directory is correctly sorted */
    uint32_t prevTag = tag;
    uint32_t csum = calcChecksum(&sfntDir[tableIndex], sfntData, sfntLen);
    if (csum != READ32BE(sfntDir[tableIndex].checksum)) {
      status |= eWOFF_warn_checksum_mismatch;
    }
    checkSumAdjustment += csum;
    tag = READ32BE(sfntDir[tableIndex].tag);
    if (tag <= prevTag) {
      FAIL(eWOFF_invalid);
    }
    if (tag == TABLE_TAG_head || tag == TABLE_TAG_bhed) {
      if (READ32BE(sfntDir[tableIndex].length) < HEAD_TABLE_SIZE) {
        FAIL(eWOFF_invalid);
      }
      head = (const sfntHeadTable *)(sfntData +
                                     READ32BE(sfntDir[tableIndex].offset));
    }
  }
  if (!head) {
    FAIL(eWOFF_invalid);
  }
  if ((status & eWOFF_warn_checksum_mismatch) == 0) {
    /* no point even checking if we already have an error,
       as fixing that will change the overall checksum too */
    const uint32_t * csumPtr = (const uint32_t *) sfntData;
    const uint32_t * csumEnd = csumPtr + 3 + 4 * numOrigTables;
    while (csumPtr < csumEnd) {
      checkSumAdjustment += READ32BE(*csumPtr);
      ++csumPtr;
    }
    checkSumAdjustment = 0xB1B0AFBA - checkSumAdjustment;
    if (checkSumAdjustment != READ32BE(head->checkSumAdjustment)) {
      status |= eWOFF_warn_checksum_mismatch;
    }
  }

  /* Fixing checkSumAdjustment is tricky, because if there's a DSIG table,
     we're going to have to remove that, which in turn means that table
     offsets in the directory will all change.
     And recalculating checkSumAdjustment requires taking account of any
     individual table checksum corrections, but they have not actually been
     applied to the sfnt data at this point.
     And finally, we'd need to get the corrected checkSumAdjustment into the
     encoded head table (but we can't modify the original sfnt data).
     An easier way out seems to be to go ahead and encode the font, knowing
     that checkSumAdjustment will be wrong; then (if the status flag
     eWOFF_warn_checksum_mismatch is set) we'll decode the font back to
     sfnt format. This will fix up the checkSumAdjustment (and return a
     warning status). We'll ignore that warning, and then re-encode the
     new, cleaned-up sfnt to get the final WOFF data. Perhaps not the most
     efficient approach, but it seems simpler than trying to predict the
     correct final checkSumAdjustment and incorporate it into the head
     table on the fly. */

  tableOrder = (tableOrderRec *) malloc(numOrigTables * sizeof(tableOrderRec));
  if (!tableOrder) {
    FAIL(eWOFF_out_of_memory);
  }
  for (tableIndex = 0, numTables = 0;
       tableIndex < numOrigTables; ++tableIndex) {
    if ((status & eWOFF_warn_checksum_mismatch) != 0) {
      /* check for DSIG table that we must drop if we're fixing checksums */
      tag = READ32BE(sfntDir[tableIndex].tag);
      if (tag == TABLE_TAG_DSIG) {
        status |= eWOFF_warn_removed_DSIG;
        removedDsigSize = READ32BE(sfntDir[tableIndex].length);
        continue;
      }
    }
    tableOrder[numTables].offset = READ32BE(sfntDir[tableIndex].offset);
    tableOrder[numTables].oldIndex = tableIndex;
    tableOrder[numTables].newIndex = numTables;
    ++numTables;
  }
  qsort(tableOrder, numTables, sizeof(tableOrderRec), compareOffsets);

  /* initially, allocate space for header and directory */
  tableOffset = sizeof(woffHeader) + numTables * sizeof(woffDirEntry);
  woffData = (uint8_t *) malloc(tableOffset);
  if (!woffData) {
    FAIL(eWOFF_out_of_memory);
  }

  /* accumulator for total expected size of decoded font */
  totalSfntSize = sizeof(sfntHeader) + numTables * sizeof(sfntDirEntry);

/*
 * We use a macro for this rather than creating a variable because woffData
 * will get reallocated during encoding. The macro avoids the risk of using a
 * stale pointer, and the compiler should optimize multiple successive uses.
 */
#define WOFFDIR ((woffDirEntry *) (woffData + sizeof(woffHeader)))

  for (order = 0; order < numTables; ++order) {
    uLong sourceLen, destLen;
    uint32_t sourceOffset;

    uint16_t oldIndex = tableOrder[order].oldIndex;
    uint16_t newIndex = tableOrder[order].newIndex;

    WOFFDIR[newIndex].tag = sfntDir[oldIndex].tag;
    if ((status & eWOFF_warn_checksum_mismatch) != 0) {
      uint32_t csum = calcChecksum(&sfntDir[oldIndex], sfntData, sfntLen);
      WOFFDIR[newIndex].checksum = READ32BE(csum);
    } else {
      WOFFDIR[newIndex].checksum = sfntDir[oldIndex].checksum;
    }
    WOFFDIR[newIndex].origLen = sfntDir[oldIndex].length;
    WOFFDIR[newIndex].offset = READ32BE(tableOffset);

    /* allocate enough space for upper bound of compressed size */
    sourceOffset = READ32BE(sfntDir[oldIndex].offset);
    if ((sourceOffset & 3) != 0) {
      status |= eWOFF_warn_misaligned_table;
    }
    sourceLen = READ32BE(sfntDir[oldIndex].length);
    if (sourceLen > sfntLen || sourceOffset > sfntLen - sourceLen) {
      FAIL(eWOFF_invalid);
    }
    destLen = LONGALIGN(compressBound(sourceLen));
    woffData = (uint8_t *) realloc(woffData, tableOffset + destLen);
    if (!woffData) {
      FAIL(eWOFF_out_of_memory);
    }

    /* do the compression directly into the WOFF data block */
    if (compress2((Bytef *) (woffData + tableOffset), &destLen,
                  (const Bytef *) (sfntData + sourceOffset),
                  sourceLen, 9) != Z_OK) {
      FAIL(eWOFF_compression_failure);
    }
    if (destLen < sourceLen) {
      /* compressed table was smaller */
      tableOffset += destLen;
      WOFFDIR[newIndex].compLen = READ32BE(destLen);
    } else {
      /* compression didn't make it smaller, so store original data instead */
      destLen = sourceLen;
      /* reallocate to ensure enough space for the table,
         plus potential padding after it */
      woffData = (uint8_t *) realloc(woffData,
                                     tableOffset + LONGALIGN(sourceLen));
      if (!woffData) {
        FAIL(eWOFF_out_of_memory);
      }
      /* copy the original data into place */
      memcpy(woffData + tableOffset,
             sfntData + READ32BE(sfntDir[oldIndex].offset), sourceLen);
      tableOffset += sourceLen;
      WOFFDIR[newIndex].compLen = WOFFDIR[newIndex].origLen;
    }

    /* we always realloc woffData to a long-aligned size, so this is safe */
    while ((tableOffset & 3) != 0) {
      woffData[tableOffset++] = 0;
    }

    /* update total size of uncompressed OpenType with table size */
    totalSfntSize += sourceLen;
    totalSfntSize = LONGALIGN(totalSfntSize);
  }

  if (totalSfntSize > sfntLen) {
    if (totalSfntSize > LONGALIGN(sfntLen)) {
      FAIL(eWOFF_invalid);
    } else {
      status |= eWOFF_warn_unpadded_table;
    }
  } else if (totalSfntSize < sfntLen) {
    /* check if the remaining data is a DSIG we're removing;
       if so, we're already warning about that */
    if ((status & eWOFF_warn_removed_DSIG) != 0 ||
        sfntLen - totalSfntSize >
          LONGALIGN(removedDsigSize) + sizeof(sfntDirEntry)) {
      status |= eWOFF_warn_trailing_data;
    }
  }

  /* write the header */
  newHeader = (woffHeader *) (woffData);
  newHeader->signature = WOFF_SIGNATURE;
  newHeader->signature = READ32BE(newHeader->signature);
  newHeader->flavor = header->version;
  newHeader->length = READ32BE(tableOffset);
  newHeader->numTables = READ16BE(numTables);
  newHeader->reserved = 0;
  newHeader->totalSfntSize = READ32BE(totalSfntSize);
  newHeader->majorVersion = READ16BE(majorVersion);
  newHeader->minorVersion = READ16BE(minorVersion);
  newHeader->metaOffset = 0;
  newHeader->metaCompLen = 0;
  newHeader->metaOrigLen = 0;
  newHeader->privOffset = 0;
  newHeader->privLen = 0;

  free(tableOrder);

  if ((status & eWOFF_warn_checksum_mismatch) != 0) {
    /* The original font had checksum errors, so we now decode our WOFF data
       back to sfnt format (which fixes checkSumAdjustment), then re-encode
       to get a clean copy. */
    const uint8_t * cleanSfnt = woffDecode(woffData, tableOffset,
                                           &sfntLen, &status);
    if (WOFF_FAILURE(status)) {
      FAIL(status);
    }
    free(woffData);
    woffData = (uint8_t *) woffEncode(cleanSfnt, sfntLen,
                                      majorVersion, minorVersion,
                                      &tableOffset, &status);
    free((void *) cleanSfnt);
    if (WOFF_FAILURE(status)) {
      FAIL(status);
    }
  }

  if (woffLen) {
    *woffLen = tableOffset;
  }
  if (pStatus) {
    *pStatus |= status;
  }
  return woffData;

failure:
  if (tableOrder) {
    free(tableOrder);
  }
  if (woffData) {
    free(woffData);
  }
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;
}

static const uint8_t *
rebuildWoff(const uint8_t * woffData, uint32_t * woffLen,
            const uint8_t * metaData, uint32_t metaCompLen, uint32_t metaOrigLen,
            const uint8_t * privData, uint32_t privLen, uint32_t * pStatus)
{
  const woffHeader * origHeader;
  const woffDirEntry * woffDir;
  uint8_t * newData = NULL;
  uint8_t * tableData = NULL;
  woffHeader * newHeader;
  uint16_t numTables;
  uint32_t tableLimit, totalSize, offset;
  uint16_t i;
  uint32_t status = eWOFF_ok;

  if (*woffLen < sizeof(woffHeader)) {
    FAIL(eWOFF_invalid);
  }
  origHeader = (const woffHeader *) (woffData);

  if (READ32BE(origHeader->signature) != WOFF_SIGNATURE) {
    FAIL(eWOFF_bad_signature);
  }

  numTables = READ16BE(origHeader->numTables);
  woffDir = (const woffDirEntry *) (woffData + sizeof(woffHeader));
  tableLimit = 0;
  for (i = 0; i < numTables; ++i) {
    uint32_t end = READ32BE(woffDir[i].offset) + READ32BE(woffDir[i].compLen);
    if (end > tableLimit) {
      tableLimit = end;
    }
  }
  tableLimit = LONGALIGN(tableLimit);

  /* check for broken input (meta/priv data before sfnt tables) */
  offset = READ32BE(origHeader->metaOffset);
  if (offset != 0 && offset < tableLimit) {
    FAIL(eWOFF_illegal_order);
  }
  offset = READ32BE(origHeader->privOffset);
  if (offset != 0 && offset < tableLimit) {
    FAIL(eWOFF_illegal_order);
  }

  totalSize = tableLimit; /* already long-aligned */
  if (metaCompLen) {
    totalSize += metaCompLen;
  }
  if (privLen) {
    totalSize = LONGALIGN(totalSize) + privLen;
  }
  newData = malloc(totalSize);
  if (!newData) {
    FAIL(eWOFF_out_of_memory);
  }

  /* copy the header, directory, and sfnt tables */
  memcpy(newData, woffData, tableLimit);

  /* then overwrite the header fields that should be changed */
  newHeader = (woffHeader *) newData;
  newHeader->length = READ32BE(totalSize);
  newHeader->metaOffset = 0;
  newHeader->metaCompLen = 0;
  newHeader->metaOrigLen = 0;
  newHeader->privOffset = 0;
  newHeader->privLen = 0;

  offset = tableLimit;
  if (metaData && metaCompLen > 0 && metaOrigLen > 0) {
    newHeader->metaOffset = READ32BE(offset);
    newHeader->metaCompLen = READ32BE(metaCompLen);
    newHeader->metaOrigLen = READ32BE(metaOrigLen);
    memcpy(newData + offset, metaData, metaCompLen);
    offset += metaCompLen;
  }

  if (privData && privLen > 0) {
    while ((offset & 3) != 0) {
      newData[offset++] = 0;
    }
    newHeader->privOffset = READ32BE(offset);
    newHeader->privLen = READ32BE(privLen);
    memcpy(newData + offset, privData, privLen);
    offset += privLen;
  }

  *woffLen = offset;
  free((void *) woffData);

  if (pStatus) {
    *pStatus |= status;
  }
  return newData;

failure:
  if (newData) {
    free(newData);
  }
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;
}

const uint8_t *
woffSetMetadata(const uint8_t * woffData, uint32_t * woffLen,
                const uint8_t * metaData, uint32_t metaLen,
                uint32_t * pStatus)
{
  const woffHeader * header;
  uLong compLen = 0;
  uint8_t * compData = NULL;
  const uint8_t * privData = NULL;
  uint32_t privLen = 0;
  uint32_t status = eWOFF_ok;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return NULL;
  }

  if (!woffData || !woffLen) {
    FAIL(eWOFF_bad_parameter);
  }

  if (*woffLen < sizeof(woffHeader)) {
    FAIL(eWOFF_invalid);
  }
  header = (const woffHeader *) (woffData);

  if (READ32BE(header->signature) != WOFF_SIGNATURE) {
    FAIL(eWOFF_bad_signature);
  }

  if (header->privOffset != 0 && header->privLen != 0) {
    privData = woffData + READ32BE(header->privOffset);
    privLen = READ32BE(header->privLen);
    if (privData + privLen > woffData + *woffLen) {
      FAIL(eWOFF_invalid);
    }
  }

  if (metaData && metaLen > 0) {
    compLen = compressBound(metaLen);
    compData = malloc(compLen);
    if (!compData) {
      FAIL(eWOFF_out_of_memory);
    }

    if (compress2((Bytef *) compData, &compLen,
                  (const Bytef *) metaData, metaLen, 9) != Z_OK) {
      FAIL(eWOFF_compression_failure);
    }
  }

  woffData = rebuildWoff(woffData, woffLen,
                         compData, compLen, metaLen,
                         privData, privLen, pStatus);
  free(compData);
  return woffData;

failure:
  if (compData) {
    free(compData);
  }
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;
}

const uint8_t *
woffSetPrivateData(const uint8_t * woffData, uint32_t * woffLen,
                   const uint8_t * privData, uint32_t privLen,
                   uint32_t * pStatus)
{
  const woffHeader * header;
  const uint8_t * metaData = NULL;
  uint32_t metaLen = 0;
  uint32_t status = eWOFF_ok;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return NULL;
  }

  if (!woffData || !woffLen) {
    FAIL(eWOFF_bad_parameter);
  }

  if (*woffLen < sizeof(woffHeader)) {
    FAIL(eWOFF_invalid);
  }
  header = (const woffHeader *) (woffData);

  if (READ32BE(header->signature) != WOFF_SIGNATURE) {
    FAIL(eWOFF_bad_signature);
  }

  if (header->metaOffset != 0 && header->metaCompLen != 0) {
    metaData = woffData + READ32BE(header->metaOffset);
    metaLen = READ32BE(header->metaCompLen);
    if (metaData + metaLen > woffData + *woffLen) {
      FAIL(eWOFF_invalid);
    }
  }

  woffData = rebuildWoff(woffData, woffLen,
                         metaData, metaLen, READ32BE(header->metaOrigLen),
                         privData, privLen, pStatus);
  return woffData;

failure:
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;
}

#endif /* WOFF_MOZILLA_CLIENT */

/******************************************************************/
/* * * * * * * * * * * * * * DECODING * * * * * * * * * * * * * * */
/******************************************************************/

static uint32_t
sanityCheck(const uint8_t * woffData, uint32_t woffLen)
{
  const woffHeader * header;
  uint16_t numTables, i;
  const woffDirEntry * dirEntry;
  uint32_t tableTotal = 0;

  if (!woffData || !woffLen) {
    return eWOFF_bad_parameter;
  }

  if (woffLen < sizeof(woffHeader)) {
    return eWOFF_invalid;
  }

  header = (const woffHeader *) (woffData);
  if (READ32BE(header->signature) != WOFF_SIGNATURE) {
    return eWOFF_bad_signature;
  }

  if (READ32BE(header->length) != woffLen || header->reserved != 0) {
    return eWOFF_invalid;
  }

  numTables = READ16BE(header->numTables);
  if (woffLen < sizeof(woffHeader) + numTables * sizeof(woffDirEntry)) {
    return eWOFF_invalid;
  }

  dirEntry = (const woffDirEntry *) (woffData + sizeof(woffHeader));
  for (i = 0; i < numTables; ++i) {
    uint32_t offs = READ32BE(dirEntry->offset);
    uint32_t orig = READ32BE(dirEntry->origLen);
    uint32_t comp = READ32BE(dirEntry->compLen);
    if (comp > orig || comp > woffLen || offs > woffLen - comp) {
      return eWOFF_invalid;
    }
    orig = (orig + 3) & ~3;
    if (tableTotal > 0xffffffffU - orig) {
      return eWOFF_invalid;
    }
    tableTotal += orig;
    ++dirEntry;
  }

  if (tableTotal > 0xffffffffU - sizeof(sfntHeader) -
                                 numTables * sizeof(sfntDirEntry) ||
      READ32BE(header->totalSfntSize) !=
        tableTotal + sizeof(sfntHeader) + numTables * sizeof(sfntDirEntry)) {
    return eWOFF_invalid;
  }

  return eWOFF_ok;
}

uint32_t
woffGetDecodedSize(const uint8_t * woffData, uint32_t woffLen,
                   uint32_t * pStatus)
{
  uint32_t status = eWOFF_ok;
  uint32_t totalLen = 0;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return 0;
  }

  status = sanityCheck(woffData, woffLen);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  totalLen = READ32BE(((const woffHeader *) (woffData))->totalSfntSize);
  /* totalLen must be correctly rounded up to 4-byte alignment, otherwise
     sanityCheck would have failed */

failure:
  if (pStatus) {
    *pStatus = status;
  }
  return totalLen;
}

static void
woffDecodeToBufferInternal(const uint8_t * woffData, uint32_t woffLen,
                           uint8_t * sfntData, uint32_t bufferLen,
                           uint32_t * pActualSfntLen, uint32_t * pStatus)
{
  /* this is only called after sanityCheck has verified that
     (a) basic header fields are ok
     (b) all the WOFF table offset/length pairs are valid (within the data)
     (c) the sum of original sizes + header/directory matches totalSfntSize
     so we don't have to re-check those overflow conditions here */
  tableOrderRec * tableOrder = NULL;
  const woffHeader * header;
  uint16_t numTables;
  uint16_t tableIndex;
  uint16_t order;
  const woffDirEntry * woffDir;
  uint32_t totalLen;
  sfntHeader * newHeader;
  uint16_t searchRange, rangeShift, entrySelector;
  uint32_t offset;
  sfntDirEntry * sfntDir;
  uint32_t headOffset = 0, headLength = 0;
  sfntHeadTable * head;
  uint32_t csum = 0;
  const uint32_t * csumPtr;
  uint32_t oldCheckSumAdjustment;
  uint32_t status = eWOFF_ok;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return;
  }

  /* check basic header fields */
  header = (const woffHeader *) (woffData);
  if (READ32BE(header->flavor) != SFNT_VERSION_TT &&
      READ32BE(header->flavor) != SFNT_VERSION_CFF &&
      READ32BE(header->flavor) != SFNT_VERSION_true) {
    status |= eWOFF_warn_unknown_version;
  }

  numTables = READ16BE(header->numTables);
  woffDir = (const woffDirEntry *) (woffData + sizeof(woffHeader));

  totalLen = READ32BE(header->totalSfntSize);

  /* construct the sfnt header */
  newHeader = (sfntHeader *) (sfntData);
  newHeader->version = header->flavor;
  newHeader->numTables = READ16BE(numTables);
  
  /* calculate header fields for binary search */
  searchRange = numTables;
  searchRange |= (searchRange >> 1);
  searchRange |= (searchRange >> 2);
  searchRange |= (searchRange >> 4);
  searchRange |= (searchRange >> 8);
  searchRange &= ~(searchRange >> 1);
  searchRange *= 16;
  newHeader->searchRange = READ16BE(searchRange);
  rangeShift = numTables * 16 - searchRange;
  newHeader->rangeShift = READ16BE(rangeShift);
  entrySelector = 0;
  while (searchRange > 16) {
    ++entrySelector;
    searchRange >>= 1;
  }
  newHeader->entrySelector = READ16BE(entrySelector);

  tableOrder = (tableOrderRec *) malloc(numTables * sizeof(tableOrderRec));
  if (!tableOrder) {
    FAIL(eWOFF_out_of_memory);
  }
  for (tableIndex = 0; tableIndex < numTables; ++tableIndex) {
    tableOrder[tableIndex].offset = READ32BE(woffDir[tableIndex].offset);
    tableOrder[tableIndex].oldIndex = tableIndex;
  }
  qsort(tableOrder, numTables, sizeof(tableOrderRec), compareOffsets);

  /* process each table, filling in the sfnt directory */
  offset = sizeof(sfntHeader) + numTables * sizeof(sfntDirEntry);
  sfntDir = (sfntDirEntry *) (sfntData + sizeof(sfntHeader));
  for (order = 0; order < numTables; ++order) {
    uint32_t origLen, compLen, tag, sourceOffset;
    tableIndex = tableOrder[order].oldIndex;

    /* validity of these was confirmed by sanityCheck */
    origLen = READ32BE(woffDir[tableIndex].origLen);
    compLen = READ32BE(woffDir[tableIndex].compLen);
    sourceOffset = READ32BE(woffDir[tableIndex].offset);

    sfntDir[tableIndex].tag = woffDir[tableIndex].tag;
    sfntDir[tableIndex].offset = READ32BE(offset);
    sfntDir[tableIndex].length = woffDir[tableIndex].origLen;
    sfntDir[tableIndex].checksum = woffDir[tableIndex].checksum;
    csum += READ32BE(sfntDir[tableIndex].checksum);

    if (compLen < origLen) {
      uLongf destLen = origLen;
      if (uncompress((Bytef *)(sfntData + offset), &destLen,
                     (const Bytef *)(woffData + sourceOffset),
                     compLen) != Z_OK || destLen != origLen) {
        FAIL(eWOFF_compression_failure);
      }
    } else {
      memcpy(sfntData + offset, woffData + sourceOffset, origLen);
    }

    /* note that old Mac bitmap-only fonts have no 'head' table
       (eg NISC18030.ttf) but a 'bhed' table instead */
    tag = READ32BE(sfntDir[tableIndex].tag);
    if (tag == TABLE_TAG_head || tag == TABLE_TAG_bhed) {
      headOffset = offset;
      headLength = origLen;
    }

    offset += origLen;

    while (offset < totalLen && (offset & 3) != 0) {
      sfntData[offset++] = 0;
    }
  }

  if (headOffset > 0) {
    /* the font checksum in the 'head' table depends on all the individual
       table checksums (collected above), plus the header and directory
       which are added in here */
    if (headLength < HEAD_TABLE_SIZE) {
      FAIL(eWOFF_invalid);
    }
    head = (sfntHeadTable *)(sfntData + headOffset);
    oldCheckSumAdjustment = READ32BE(head->checkSumAdjustment);
    head->checkSumAdjustment = 0;
    csumPtr = (const uint32_t *)sfntData;
    while (csumPtr < (const uint32_t *)(sfntData + sizeof(sfntHeader) +
                                        numTables * sizeof(sfntDirEntry))) {
      csum += READ32BE(*csumPtr);
      csumPtr++;
    }
    csum = SFNT_CHECKSUM_CALC_CONST - csum;

    if (oldCheckSumAdjustment != csum) {
      /* if the checksum doesn't match, we fix it; but this will invalidate
         any DSIG that may be present */
      status |= eWOFF_warn_checksum_mismatch;
    }
    head->checkSumAdjustment = READ32BE(csum);
  }

  if (pActualSfntLen) {
    *pActualSfntLen = totalLen;
  }
  if (pStatus) {
    *pStatus |= status;
  }
  free(tableOrder);
  return;

failure:
  if (tableOrder) {
    free(tableOrder);
  }
  if (pActualSfntLen) {
    *pActualSfntLen = 0;
  }
  if (pStatus) {
    *pStatus = status;
  }
}

void
woffDecodeToBuffer(const uint8_t * woffData, uint32_t woffLen,
                   uint8_t * sfntData, uint32_t bufferLen,
                   uint32_t * pActualSfntLen, uint32_t * pStatus)
{
  uint32_t status = eWOFF_ok;
  uint32_t totalLen;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return;
  }

  status = sanityCheck(woffData, woffLen);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  if (!sfntData) {
    FAIL(eWOFF_bad_parameter);
  }

  totalLen = READ32BE(((const woffHeader *) (woffData))->totalSfntSize);
  if (bufferLen < totalLen) {
    FAIL(eWOFF_buffer_too_small);
  }

  woffDecodeToBufferInternal(woffData, woffLen, sfntData, bufferLen,
                             pActualSfntLen, pStatus);
  return;

failure:
  if (pActualSfntLen) {
    *pActualSfntLen = 0;
  }
  if (pStatus) {
    *pStatus = status;
  }
}

const uint8_t *
woffDecode(const uint8_t * woffData, uint32_t woffLen,
           uint32_t * sfntLen, uint32_t * pStatus)
{
  uint32_t status = eWOFF_ok;
  uint8_t * sfntData = NULL;
  uint32_t bufLen;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return NULL;
  }

  status = sanityCheck(woffData, woffLen);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  bufLen = READ32BE(((const woffHeader *) (woffData))->totalSfntSize);
  sfntData = (uint8_t *) malloc(bufLen);
  if (!sfntData) {
    FAIL(eWOFF_out_of_memory);
  }

  woffDecodeToBufferInternal(woffData, woffLen, sfntData, bufLen,
                             sfntLen, &status);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  if (pStatus) {
    *pStatus |= status;
  }
  return sfntData;

failure:
  if (sfntData) {
    free(sfntData);
  }
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;
}

#ifndef WOFF_MOZILLA_CLIENT

const uint8_t *
woffGetMetadata(const uint8_t * woffData, uint32_t woffLen,
                uint32_t * metaLen, uint32_t * pStatus)
{
  const woffHeader * header;
  uint32_t offset, compLen;
  uLong origLen;
  uint8_t * data = NULL;
  uint32_t status = eWOFF_ok;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return NULL;
  }

  status = sanityCheck(woffData, woffLen);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  header = (const woffHeader *) (woffData);

  offset = READ32BE(header->metaOffset);
  compLen = READ32BE(header->metaCompLen);
  origLen = READ32BE(header->metaOrigLen);
  if (offset == 0 || compLen == 0 || origLen == 0) {
    return NULL;
  }

  if (compLen > woffLen || offset > woffLen - compLen) {
    FAIL(eWOFF_invalid);
  }

  data = malloc(origLen);
  if (!data) {
    FAIL(eWOFF_out_of_memory);
  }

  if (uncompress((Bytef *)data, &origLen,
                 (const Bytef *)woffData + offset, compLen) != Z_OK ||
      origLen != READ32BE(header->metaOrigLen)) {
    FAIL(eWOFF_compression_failure);
  }

  if (metaLen) {
    *metaLen = origLen;
  }
  if (pStatus) {
    *pStatus |= status;
  }
  return data;

failure:
  if (data) {
    free(data);
  }
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;    
}

const uint8_t *
woffGetPrivateData(const uint8_t * woffData, uint32_t woffLen,
                   uint32_t * privLen, uint32_t * pStatus)
{
  const woffHeader * header;
  uint32_t offset, length;
  uint8_t * data = NULL;
  uint32_t status = eWOFF_ok;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return NULL;
  }

  status = sanityCheck(woffData, woffLen);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  header = (const woffHeader *) (woffData);

  offset = READ32BE(header->privOffset);
  length = READ32BE(header->privLen);
  if (offset == 0 || length == 0) {
    return NULL;
  }

  if (length > woffLen || offset > woffLen - length) {
    FAIL(eWOFF_invalid);
  }

  data = malloc(length);
  if (!data) {
    FAIL(eWOFF_out_of_memory);
  }

  memcpy(data, woffData + offset, length);

  if (privLen) {
    *privLen = length;
  }
  if (pStatus) {
    *pStatus |= status;
  }
  return data;

failure:
  if (data) {
    free(data);
  }
  if (pStatus) {
    *pStatus = status;
  }
  return NULL;    
}

void
woffGetFontVersion(const uint8_t * woffData, uint32_t woffLen,
                   uint16_t * major, uint16_t * minor, uint32_t * pStatus)
{
  const woffHeader * header;
  uint32_t status = eWOFF_ok;

  if (pStatus && WOFF_FAILURE(*pStatus)) {
    return;
  }

  status = sanityCheck(woffData, woffLen);
  if (WOFF_FAILURE(status)) {
    FAIL(status);
  }

  if (!major || !minor) {
    FAIL(eWOFF_bad_parameter);
  }

  *major = *minor = 0;

  header = (const woffHeader *) (woffData);

  *major = READ16BE(header->majorVersion);
  *minor = READ16BE(header->minorVersion);

failure:
  if (pStatus) {
    *pStatus = status;
  }
}

/* utility to print messages corresponding to WOFF encoder/decoder errors */
void
woffPrintStatus(FILE * f, uint32_t status, const char * prefix)
{
  if (!prefix) {
    prefix = "";
  }
  if (WOFF_WARNING(status)) {
    const char * template = "%sWOFF warning: %s\n";
    if (status & eWOFF_warn_unknown_version) {
      fprintf(f, template, prefix, "unrecognized sfnt version");
    }
    if (status & eWOFF_warn_checksum_mismatch) {
      fprintf(f, template, prefix, "checksum mismatch (corrected)");
    }
    if (status & eWOFF_warn_misaligned_table) {
      fprintf(f, template, prefix, "misaligned font table");
    }
    if (status & eWOFF_warn_trailing_data) {
      fprintf(f, template, prefix, "extraneous input data discarded");
    }
    if (status & eWOFF_warn_unpadded_table) {
      fprintf(f, template, prefix, "final table not correctly padded");
    }
    if (status & eWOFF_warn_removed_DSIG) {
      fprintf(f, template, prefix, "digital signature (DSIG) table removed");
    }
  }
  if (WOFF_FAILURE(status)) {
    const char * template = "%sWOFF error: %s\n";
    const char * msg;
    switch (status & 0xff) {
    case eWOFF_out_of_memory:
      msg = "memory allocation failure";
      break;
    case eWOFF_invalid:
      msg = "invalid input font";
      break;
    case eWOFF_compression_failure:
      msg = "zlib compression/decompression failure";
      break;
    case eWOFF_bad_signature:
      msg = "incorrect WOFF file signature";
      break;
    case eWOFF_buffer_too_small:
      msg = "buffer too small";
      break;
    case eWOFF_bad_parameter:
      msg = "bad parameter to WOFF function";
      break;
    case eWOFF_illegal_order:
      msg = "incorrect table directory order";
      break;
    default:
      msg = "unknown internal error";
      break;
    }
    fprintf(f, template, prefix, msg);
  }
}

#endif /* not WOFF_MOZILLA_CLIENT */
