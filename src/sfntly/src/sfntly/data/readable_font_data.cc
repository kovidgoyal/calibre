/*
 * Copyright 2011 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#include "sfntly/data/readable_font_data.h"

#include <stdio.h>

#include "sfntly/data/memory_byte_array.h"
#include "sfntly/data/writable_font_data.h"
#include "sfntly/port/exception_type.h"

namespace sfntly {

ReadableFontData::ReadableFontData(ByteArray* array)
    : FontData(array),
      checksum_set_(false),
      checksum_(0) {
}

ReadableFontData::~ReadableFontData() {}

// TODO(arthurhsu): re-investigate the memory model of this function.  It's
//                  not too useful without copying, but it's not performance
//                  savvy to do copying.
CALLER_ATTACH
ReadableFontData* ReadableFontData::CreateReadableFontData(ByteVector* b) {
  assert(b);
  ByteArrayPtr ba = new MemoryByteArray(b->size());
  ba->Put(0, b);
  ReadableFontDataPtr wfd = new ReadableFontData(ba);
  return wfd.Detach();
}

int64_t ReadableFontData::Checksum() {
  AutoLock lock(checksum_lock_);
  if (!checksum_set_) {
    ComputeChecksum();
  }
  return checksum_;
}

void ReadableFontData::SetCheckSumRanges(const IntegerList& ranges) {
  checksum_range_ = ranges;
  checksum_set_ = false;  // UNIMPLEMENTED: atomicity
}

int32_t ReadableFontData::ReadUByte(int32_t index) {
  int32_t b = array_->Get(BoundOffset(index));
#if !defined (SFNTLY_NO_EXCEPTION)
  if (b < 0) {
    throw IndexOutOfBoundException(
        "Index attempted to be read from is out of bounds", index);
  }
#endif
  return b;
}

int32_t ReadableFontData::ReadByte(int32_t index) {
  int32_t b = array_->Get(BoundOffset(index));
#if !defined (SFNTLY_NO_EXCEPTION)
  if (b < 0) {
    throw IndexOutOfBoundException(
        "Index attempted to be read from is out of bounds", index);
  }
#endif
  return (b << 24) >> 24;
}

int32_t ReadableFontData::ReadBytes(int32_t index,
                                    byte_t* b,
                                    int32_t offset,
                                    int32_t length) {
  return array_->Get(BoundOffset(index), b, offset, BoundLength(index, length));
}

int32_t ReadableFontData::ReadChar(int32_t index) {
  return ReadUByte(index);
}

int32_t ReadableFontData::ReadUShort(int32_t index) {
  return 0xffff & (ReadUByte(index) << 8 | ReadUByte(index + 1));
}

int32_t ReadableFontData::ReadShort(int32_t index) {
  return ((ReadByte(index) << 8 | ReadUByte(index + 1)) << 16) >> 16;
}

int32_t ReadableFontData::ReadUInt24(int32_t index) {
  return 0xffffff & (ReadUByte(index) << 16 |
                     ReadUByte(index + 1) << 8 |
                     ReadUByte(index + 2));
}

int64_t ReadableFontData::ReadULong(int32_t index) {
  return 0xffffffffL & (ReadUByte(index) << 24 |
                        ReadUByte(index + 1) << 16 |
                        ReadUByte(index + 2) << 8 |
                        ReadUByte(index + 3));
}

int32_t ReadableFontData::ReadULongAsInt(int32_t index) {
  int64_t ulong = ReadULong(index);
#if !defined (SFNTLY_NO_EXCEPTION)
  if ((ulong & 0x80000000) == 0x80000000) {
    throw ArithmeticException("Long value too large to fit into an integer.");
  }
#endif
  return static_cast<int32_t>(ulong);
}

int64_t ReadableFontData::ReadULongLE(int32_t index) {
  return 0xffffffffL & (ReadUByte(index) |
                        ReadUByte(index + 1) << 8 |
                        ReadUByte(index + 2) << 16 |
                        ReadUByte(index + 3) << 24);
}

int32_t ReadableFontData::ReadLong(int32_t index) {
  return ReadByte(index) << 24 |
         ReadUByte(index + 1) << 16 |
         ReadUByte(index + 2) << 8 |
         ReadUByte(index + 3);
}

int32_t ReadableFontData::ReadFixed(int32_t index) {
  return ReadLong(index);
}

int64_t ReadableFontData::ReadDateTimeAsLong(int32_t index) {
  return (int64_t)ReadULong(index) << 32 | ReadULong(index + 4);
}

int32_t ReadableFontData::ReadFWord(int32_t index) {
  return ReadShort(index);
}

int32_t ReadableFontData::ReadFUFWord(int32_t index) {
  return ReadUShort(index);
}

int32_t ReadableFontData::CopyTo(OutputStream* os) {
  return array_->CopyTo(os, BoundOffset(0), Length());
}

int32_t ReadableFontData::CopyTo(WritableFontData* wfd) {
  return array_->CopyTo(wfd->BoundOffset(0),
                        wfd->array_,
                        BoundOffset(0),
                        Length());
}

int32_t ReadableFontData::CopyTo(ByteArray* ba) {
  return array_->CopyTo(ba, BoundOffset(0), Length());
}

int32_t ReadableFontData::SearchUShort(int32_t start_index,
                                       int32_t start_offset,
                                       int32_t end_index,
                                       int32_t end_offset,
                                       int32_t length,
                                       int32_t key) {
  int32_t location = 0;
  int32_t bottom = 0;
  int32_t top = length;
  while (top != bottom) {
    location = (top + bottom) / 2;
    int32_t location_start = ReadUShort(start_index + location * start_offset);
    if (key < location_start) {
      // location is below current location
      top = location;
    } else {
      // is key below the upper bound?
      int32_t location_end = ReadUShort(end_index + location * end_offset);
#if defined (SFNTLY_DEBUG_FONTDATA)
      fprintf(stderr, "**start: %d; end: %d\n", location_start, location_end);
#endif
      if (key <= location_end) {
        return location;
      } else {
        // location is above the current location
        bottom = location + 1;
      }
    }
  }
  return -1;
}

int32_t ReadableFontData::SearchUShort(int32_t start_index,
                                       int32_t start_offset,
                                       int32_t length,
                                       int32_t key) {
  int32_t location = 0;
  int32_t bottom = 0;
  int32_t top = length;
  while (top != bottom) {
    location = (top + bottom) / 2;
    int32_t location_start = ReadUShort(start_index + location * start_offset);
    if (key < location_start) {
      // location is below current location
      top = location;
    } else if (key > location_start) {
      // location is above current location
      bottom = location + 1;
    } else {
      return location;
    }
  }
  return -1;
}

int32_t ReadableFontData::SearchULong(int32_t start_index,
                                      int32_t start_offset,
                                      int32_t end_index,
                                      int32_t end_offset,
                                      int32_t length,
                                      int32_t key) {
  int32_t location = 0;
  int32_t bottom = 0;
  int32_t top = length;
  while (top != bottom) {
    location = (top + bottom) / 2;
    int32_t location_start = ReadULongAsInt(start_index
                                            + location * start_offset);
    if (key < location_start) {
      // location is below current location
      top = location;
    } else {
      // is key below the upper bound?
      int32_t location_end = ReadULongAsInt(end_index + location * end_offset);
#if defined (SFNTLY_DEBUG_FONTDATA)
      fprintf(stderr, "**start: %d; end: %d\n", location_start, location_end);
#endif
      if (key <= location_end) {
        return location;
      } else {
        // location is above the current location
        bottom = location + 1;
      }
    }
  }
  return -1;
}

CALLER_ATTACH FontData* ReadableFontData::Slice(int32_t offset,
                                                int32_t length) {
  if (offset < 0 || offset + length > Size()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException(
        "Attempt to bind data outside of its limits");
#endif
    return NULL;
  }
  FontDataPtr slice = new ReadableFontData(this, offset, length);
  return slice.Detach();
}

CALLER_ATTACH FontData* ReadableFontData::Slice(int32_t offset) {
  if (offset < 0 || offset > Size()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException(
        "Attempt to bind data outside of its limits");
#endif
    return NULL;
  }
  FontDataPtr slice = new ReadableFontData(this, offset);
  return slice.Detach();
}

ReadableFontData::ReadableFontData(ReadableFontData* data, int32_t offset)
    : FontData(data, offset),
      checksum_set_(false),
      checksum_(0) {
}

ReadableFontData::ReadableFontData(ReadableFontData* data,
                                   int32_t offset,
                                   int32_t length)
    : FontData(data, offset, length),
      checksum_set_(false),
      checksum_(0) {
}

void ReadableFontData::ComputeChecksum() {
  // TODO(arthurhsu): IMPLEMENT: synchronization/atomicity
  int64_t sum = 0;
  if (checksum_range_.empty()) {
    sum = ComputeCheckSum(0, Length());
  } else {
    for (uint32_t low_bound_index = 0; low_bound_index < checksum_range_.size();
         low_bound_index += 2) {
      int32_t low_bound = checksum_range_[low_bound_index];
      int32_t high_bound = (low_bound_index == checksum_range_.size() - 1) ?
                                Length() :
                                checksum_range_[low_bound_index + 1];
      sum += ComputeCheckSum(low_bound, high_bound);
    }
  }

  checksum_ = sum & 0xffffffffL;
  checksum_set_ = true;
}

int64_t ReadableFontData::ComputeCheckSum(int32_t low_bound,
                                          int32_t high_bound) {
  int64_t sum = 0;
  // Checksum all whole 4-byte chunks.
  for (int32_t i = low_bound; i <= high_bound - 4; i += 4) {
    sum += ReadULong(i);
  }

  // Add last fragment if not 4-byte multiple
  int32_t off = high_bound & -4;
  if (off < high_bound) {
    int32_t b3 = ReadUByte(off);
    int32_t b2 = (off + 1 < high_bound) ? ReadUByte(off + 1) : 0;
    int32_t b1 = (off + 2 < high_bound) ? ReadUByte(off + 2) : 0;
    int32_t b0 = 0;
    sum += (b3 << 24) | (b2 << 16) | (b1 << 8) | b0;
  }
  return sum;
}

}  // namespace sfntly
