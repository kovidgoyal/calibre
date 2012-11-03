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

#if defined (WIN32)
#include <windows.h>
#endif

#include <string.h>

#include "sfntly/port/memory_input_stream.h"
#include "sfntly/port/exception_type.h"

namespace sfntly {

MemoryInputStream::MemoryInputStream()
    : buffer_(NULL),
      position_(0),
      length_(0) {
}

MemoryInputStream::~MemoryInputStream() {
  Close();
}

int32_t MemoryInputStream::Available() {
  return length_ - position_;
}

void MemoryInputStream::Close() {
}

void MemoryInputStream::Mark(int32_t readlimit) {
  // NOP
  UNREFERENCED_PARAMETER(readlimit);
}

bool MemoryInputStream::MarkSupported() {
  return false;
}

int32_t MemoryInputStream::Read() {
  if (!buffer_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("no memory attached");
#endif
    return 0;
  }
  if (position_ >= length_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("eof reached");
#endif
    return 0;
  }
  byte_t value = buffer_[position_++];
  return value;
}

int32_t MemoryInputStream::Read(ByteVector* b) {
  return Read(b, 0, b->size());
}

int32_t MemoryInputStream::Read(ByteVector* b, int32_t offset, int32_t length) {
  assert(b);
  if (!buffer_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("no memory attached");
#endif
    return 0;
  }
  if (position_ >= length_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("eof reached");
#endif
    return 0;
  }
  size_t read_count = std::min<size_t>(length_ - position_, length);
  if (b->size() < (size_t)(offset + read_count)) {
    b->resize((size_t)(offset + read_count));
  }
  memcpy(&((*b)[offset]), buffer_ + position_, read_count);
  position_ += read_count;
  return read_count;
}

void MemoryInputStream::Reset() {
  // NOP
}

int64_t MemoryInputStream::Skip(int64_t n) {
  if (!buffer_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("no memory attached");
#endif
    return 0;
  }
  int64_t skip_count = 0;
  if (n < 0) {  // move backwards
    skip_count = std::max<int64_t>(0 - (int64_t)position_, n);
    position_ -= (size_t)(0 - skip_count);
  } else {
    skip_count = std::min<size_t>(length_ - position_, (size_t)n);
    position_ += (size_t)skip_count;
  }
  return skip_count;
}

void MemoryInputStream::Unread(ByteVector* b) {
  Unread(b, 0, b->size());
}

void MemoryInputStream::Unread(ByteVector* b, int32_t offset, int32_t length) {
  assert(b);
  assert(b->size() >= size_t(offset + length));
  if (!buffer_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IOException("no memory attached");
#endif
    return;
  }
  size_t unread_count = std::min<size_t>(position_, length);
  position_ -= unread_count;
  Read(b, offset, length);
  position_ -= unread_count;
}

bool MemoryInputStream::Attach(const byte_t* buffer, size_t length) {
  assert(buffer);
  assert(length);
  buffer_ = buffer;
  length_ = length;
  return true;
}

}  // namespace sfntly
