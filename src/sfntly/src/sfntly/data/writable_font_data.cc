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

#include "sfntly/data/writable_font_data.h"

#include "sfntly/data/memory_byte_array.h"
#include "sfntly/data/growable_memory_byte_array.h"

namespace sfntly {

WritableFontData::WritableFontData(ByteArray* ba) : ReadableFontData(ba) {
}

WritableFontData::~WritableFontData() {}

// static
CALLER_ATTACH
WritableFontData* WritableFontData::CreateWritableFontData(int32_t length) {
  ByteArrayPtr ba;
  if (length > 0) {
    ba = new MemoryByteArray(length);
    ba->SetFilledLength(length);
  } else {
    ba = new GrowableMemoryByteArray();
  }
  WritableFontDataPtr wfd = new WritableFontData(ba);
  return wfd.Detach();
}

// TODO(arthurhsu): re-investigate the memory model of this function.  It's
//                  not too useful without copying, but it's not performance
//                  savvy to do copying.
CALLER_ATTACH
WritableFontData* WritableFontData::CreateWritableFontData(ByteVector* b) {
  ByteArrayPtr ba = new GrowableMemoryByteArray();
  ba->Put(0, b);
  WritableFontDataPtr wfd = new WritableFontData(ba);
  return wfd.Detach();
}

int32_t WritableFontData::WriteByte(int32_t index, byte_t b) {
  array_->Put(BoundOffset(index), b);
  return 1;
}

int32_t WritableFontData::WriteBytes(int32_t index,
                                     byte_t* b,
                                     int32_t offset,
                                     int32_t length) {
  return array_->Put(BoundOffset(index),
                     b,
                     offset,
                     BoundLength(index, length));
}

int32_t WritableFontData::WriteBytes(int32_t index, ByteVector* b) {
  assert(b);
  return WriteBytes(index, &((*b)[0]), 0, b->size());
}

int32_t WritableFontData::WriteBytesPad(int32_t index,
                                        ByteVector* b,
                                        int32_t offset,
                                        int32_t length,
                                        byte_t pad) {
  int32_t written =
      array_->Put(BoundOffset(index),
                  &((*b)[0]),
                  offset,
                  BoundLength(index,
                              std::min<int32_t>(length, b->size() - offset)));
  written += WritePadding(written + index, length - written, pad);
  return written;
}

int32_t WritableFontData::WritePadding(int32_t index, int32_t count) {
  return WritePadding(index, count, (byte_t)0);
}

int32_t WritableFontData::WritePadding(int32_t index, int32_t count,
                                       byte_t pad) {
  for (int32_t i = 0; i < count; ++i) {
    array_->Put(index + i, pad);
  }
  return count;
}

int32_t WritableFontData::WriteChar(int32_t index, byte_t c) {
  return WriteByte(index, c);
}

int32_t WritableFontData::WriteUShort(int32_t index, int32_t us) {
  WriteByte(index, (byte_t)((us >> 8) & 0xff));
  WriteByte(index + 1, (byte_t)(us & 0xff));
  return 2;
}

int32_t WritableFontData::WriteUShortLE(int32_t index, int32_t us) {
  WriteByte(index, (byte_t)(us & 0xff));
  WriteByte(index + 1, (byte_t)((us >> 8) & 0xff));
  return 2;
}

int32_t WritableFontData::WriteShort(int32_t index, int32_t s) {
  return WriteUShort(index, s);
}

int32_t WritableFontData::WriteUInt24(int32_t index, int32_t ui) {
  WriteByte(index, (byte_t)((ui >> 16) & 0xff));
  WriteByte(index + 1, (byte_t)((ui >> 8) & 0xff));
  WriteByte(index + 2, (byte_t)(ui & 0xff));
  return 3;
}

int32_t WritableFontData::WriteULong(int32_t index, int64_t ul) {
  WriteByte(index, (byte_t)((ul >> 24) & 0xff));
  WriteByte(index + 1, (byte_t)((ul >> 16) & 0xff));
  WriteByte(index + 2, (byte_t)((ul >> 8) & 0xff));
  WriteByte(index + 3, (byte_t)(ul & 0xff));
  return 4;
}

int32_t WritableFontData::WriteULongLE(int32_t index, int64_t ul) {
  WriteByte(index, (byte_t)(ul & 0xff));
  WriteByte(index + 1, (byte_t)((ul >> 8) & 0xff));
  WriteByte(index + 2, (byte_t)((ul >> 16) & 0xff));
  WriteByte(index + 3, (byte_t)((ul >> 24) & 0xff));
  return 4;
}

int32_t WritableFontData::WriteLong(int32_t index, int64_t l) {
  return WriteULong(index, l);
}

int32_t WritableFontData::WriteFixed(int32_t index, int32_t f) {
  return WriteLong(index, f);
}

int32_t WritableFontData::WriteDateTime(int32_t index, int64_t date) {
  WriteULong(index, (date >> 32) & 0xffffffff);
  WriteULong(index + 4, date & 0xffffffff);
  return 8;
}

void WritableFontData::CopyFrom(InputStream* is, int32_t length) {
  array_->CopyFrom(is, length);
}

void WritableFontData::CopyFrom(InputStream* is) {
  array_->CopyFrom(is);
}

CALLER_ATTACH FontData* WritableFontData::Slice(int32_t offset,
                                                int32_t length) {
  if (offset < 0 || offset + length > Size()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException(
        "Attempt to bind data outside of its limits");
#endif
    return NULL;
  }
  FontDataPtr slice = new WritableFontData(this, offset, length);
  return slice.Detach();
}

CALLER_ATTACH FontData* WritableFontData::Slice(int32_t offset) {
  if (offset > Size()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException(
        "Attempt to bind data outside of its limits");
#endif
    return NULL;
  }
  FontDataPtr slice = new WritableFontData(this, offset);
  return slice.Detach();
}

WritableFontData::WritableFontData(WritableFontData* data, int32_t offset)
    : ReadableFontData(data, offset) {
}

WritableFontData::WritableFontData(WritableFontData* data,
                                   int32_t offset,
                                   int32_t length)
    : ReadableFontData(data, offset, length) {
}

}  // namespace sfntly
