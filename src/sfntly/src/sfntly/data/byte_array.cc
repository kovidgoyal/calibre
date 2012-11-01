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

#include "sfntly/data/byte_array.h"

#include <algorithm>

#include "sfntly/port/exception_type.h"

namespace sfntly {

const int32_t ByteArray::COPY_BUFFER_SIZE = 8192;

ByteArray::~ByteArray() {}

int32_t ByteArray::Length() { return filled_length_; }
int32_t ByteArray::Size() { return storage_length_; }

int32_t ByteArray::SetFilledLength(int32_t filled_length) {
  filled_length_ = std::min<int32_t>(filled_length, storage_length_);
  return filled_length_;
}

int32_t ByteArray::Get(int32_t index) {
  return InternalGet(index) & 0xff;
}

int32_t ByteArray::Get(int32_t index, ByteVector* b) {
  assert(b);
  return Get(index, &((*b)[0]), 0, b->size());
}

int32_t ByteArray::Get(int32_t index,
                       byte_t* b,
                       int32_t offset,
                       int32_t length) {
  assert(b);
  if (index < 0 || index >= filled_length_) {
    return 0;
  }
  int32_t actual_length = std::min<int32_t>(length, filled_length_ - index);
  return InternalGet(index, b, offset, actual_length);
}

void ByteArray::Put(int32_t index, byte_t b) {
  if (index < 0 || index >= Size()) {
#if defined (SFNTLY_NO_EXCEPTION)
    return;
#else
    throw IndexOutOfBoundException(
        "Attempt to write outside the bounds of the data");
#endif
  }
  InternalPut(index, b);
  filled_length_ = std::max<int32_t>(filled_length_, index + 1);
}

int32_t ByteArray::Put(int index, ByteVector* b) {
  assert(b);
  return Put(index, &((*b)[0]), 0, b->size());
}

int32_t ByteArray::Put(int32_t index,
                       byte_t* b,
                       int32_t offset,
                       int32_t length) {
  assert(b);
  if (index < 0 || index >= Size()) {
#if defined (SFNTLY_NO_EXCEPTION)
    return 0;
#else
    throw IndexOutOfBoundException(
        "Attempt to write outside the bounds of the data");
#endif
  }
  int32_t actual_length = std::min<int32_t>(length, Size() - index);
  int32_t bytes_written = InternalPut(index, b, offset, actual_length);
  filled_length_ = std::max<int32_t>(filled_length_, index + bytes_written);
  return bytes_written;
}

int32_t ByteArray::CopyTo(ByteArray* array) {
  return CopyTo(array, 0, Length());
}

int32_t ByteArray::CopyTo(ByteArray* array, int32_t offset, int32_t length) {
  return CopyTo(0, array, offset, length);
}

int32_t ByteArray::CopyTo(int32_t dst_offset, ByteArray* array,
                          int32_t src_offset, int32_t length) {
  assert(array);
  if (array->Size() < dst_offset + length) {  // insufficient space
    return -1;
  }

  ByteVector b(COPY_BUFFER_SIZE);
  int32_t bytes_read = 0;
  int32_t index = 0;
  int32_t remaining_length = length;
  int32_t buffer_length = std::min<int32_t>(COPY_BUFFER_SIZE, length);
  while ((bytes_read =
              Get(index + src_offset, &(b[0]), 0, buffer_length)) > 0) {
    int bytes_written = array->Put(index + dst_offset, &(b[0]), 0, bytes_read);
    UNREFERENCED_PARAMETER(bytes_written);
    index += bytes_read;
    remaining_length -= bytes_read;
    buffer_length = std::min<int32_t>(b.size(), remaining_length);
  }
  return index;
}

int32_t ByteArray::CopyTo(OutputStream* os) {
    return CopyTo(os, 0, Length());
}

int32_t ByteArray::CopyTo(OutputStream* os, int32_t offset, int32_t length) {
  ByteVector b(COPY_BUFFER_SIZE);
  int32_t bytes_read = 0;
  int32_t index = 0;
  int32_t buffer_length = std::min<int32_t>(COPY_BUFFER_SIZE, length);
  while ((bytes_read = Get(index + offset, &(b[0]), 0, buffer_length)) > 0) {
    os->Write(&b, 0, bytes_read);
    index += bytes_read;
    buffer_length = std::min<int32_t>(b.size(), length - index);
  }
  return index;
}

bool ByteArray::CopyFrom(InputStream* is, int32_t length) {
  ByteVector b(COPY_BUFFER_SIZE);
  int32_t bytes_read = 0;
  int32_t index = 0;
  int32_t buffer_length = std::min<int32_t>(COPY_BUFFER_SIZE, length);
  while ((bytes_read = is->Read(&b, 0, buffer_length)) > 0) {
    if (Put(index, &(b[0]), 0, bytes_read) != bytes_read) {
#if defined (SFNTLY_NO_EXCEPTION)
      return 0;
#else
      throw IOException("Error writing bytes.");
#endif
    }
    index += bytes_read;
    length -= bytes_read;
    buffer_length = std::min<int32_t>(b.size(), length);
  }
  return true;
}

bool ByteArray::CopyFrom(InputStream* is) {
  ByteVector b(COPY_BUFFER_SIZE);
  int32_t bytes_read = 0;
  int32_t index = 0;
  int32_t buffer_length = COPY_BUFFER_SIZE;
  while ((bytes_read = is->Read(&b, 0, buffer_length)) > 0) {
    if (Put(index, &b[0], 0, bytes_read) != bytes_read) {
#if defined (SFNTLY_NO_EXCEPTION)
      return 0;
#else
      throw IOException("Error writing bytes.");
#endif
    }
    index += bytes_read;
  }
  return true;
}

ByteArray::ByteArray(int32_t filled_length,
                     int32_t storage_length,
                     bool growable) {
  Init(filled_length, storage_length, growable);
}

ByteArray::ByteArray(int32_t filled_length, int32_t storage_length) {
  Init(filled_length, storage_length, false);
}

void ByteArray::Init(int32_t filled_length,
                     int32_t storage_length,
                     bool growable) {
  storage_length_ = storage_length;
  growable_ = growable;
  SetFilledLength(filled_length);
}

}  // namespace sfntly
