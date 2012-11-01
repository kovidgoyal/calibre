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

#include "sfntly/port/memory_output_stream.h"

namespace sfntly {

MemoryOutputStream::MemoryOutputStream() {
}

MemoryOutputStream::~MemoryOutputStream() {
}

void MemoryOutputStream::Write(ByteVector* buffer) {
  store_.insert(store_.end(), buffer->begin(), buffer->end());
}

void MemoryOutputStream::Write(ByteVector* buffer,
                               int32_t offset,
                               int32_t length) {
  assert(buffer);
  if (offset >= 0 && length > 0) {
    store_.insert(store_.end(),
                  buffer->begin() + offset,
                  buffer->begin() + offset + length);
  } else {
#if !defined(SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#endif
  }
}

void MemoryOutputStream::Write(byte_t* buffer, int32_t offset, int32_t length) {
  assert(buffer);
  if (offset >= 0 && length > 0) {
    store_.insert(store_.end(), buffer + offset, buffer + offset + length);
  } else {
#if !defined(SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#endif
  }
}

void MemoryOutputStream::Write(byte_t b) {
  store_.push_back(b);
}

byte_t* MemoryOutputStream::Get() {
  if (store_.empty()) {
    return NULL;
  }
  return &(store_[0]);
}

size_t MemoryOutputStream::Size() {
  return store_.size();
}

}  // namespace sfntly
