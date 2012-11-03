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

#include "sfntly/data/growable_memory_byte_array.h"

#include <limits.h>
#include <string.h>

#include <algorithm>

namespace sfntly {

GrowableMemoryByteArray::GrowableMemoryByteArray()
    : ByteArray(0, INT_MAX, true) {
  // Note: We did not set an initial size of array like Java because STL
  //       implementation will determine the best strategy.
}

GrowableMemoryByteArray::~GrowableMemoryByteArray() {}

int32_t GrowableMemoryByteArray::CopyTo(OutputStream* os,
                                        int32_t offset,
                                        int32_t length) {
  assert(os);
  os->Write(&b_, offset, length);
  return length;
}

void GrowableMemoryByteArray::InternalPut(int32_t index, byte_t b) {
  if ((size_t)index >= b_.size()) {
    b_.resize((size_t)(index + 1));
  }
  b_[index] = b;
}

int32_t GrowableMemoryByteArray::InternalPut(int32_t index,
                                             byte_t* b,
                                             int32_t offset,
                                             int32_t length) {
  if ((size_t)index + length >= b_.size()) {
    // Note: We grow one byte more than Java version. VC debuggers shows
    //       data better this way.
    b_.resize((size_t)(index + length + 1));
  }
  std::copy(b + offset, b + offset + length, b_.begin() + index);
  return length;
}

byte_t GrowableMemoryByteArray::InternalGet(int32_t index) {
  return b_[index];
}

int32_t GrowableMemoryByteArray::InternalGet(int32_t index,
                                             byte_t* b,
                                             int32_t offset,
                                             int32_t length) {
  memcpy(b + offset, &(b_[0]) + index, length);
  return length;
}

void GrowableMemoryByteArray::Close() {
  b_.clear();
}

byte_t* GrowableMemoryByteArray::Begin() {
  return &(b_[0]);
}

}  // namespace sfntly
