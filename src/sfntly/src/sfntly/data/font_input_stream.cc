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

#include "sfntly/data/font_input_stream.h"

#include <algorithm>

namespace sfntly {

FontInputStream::FontInputStream(InputStream* is)
    : stream_(is), position_(0), length_(0), bounded_(false) {
}

FontInputStream::FontInputStream(InputStream* is, size_t length)
    : stream_(is), position_(0), length_(length), bounded_(true) {
}

FontInputStream::~FontInputStream() {
  // Do not close here, underlying InputStream will close themselves.
}

int32_t FontInputStream::Available() {
  if (stream_) {
    return stream_->Available();
  }
  return 0;
}

void FontInputStream::Close() {
  if (stream_) {
    stream_->Close();
  }
}

void FontInputStream::Mark(int32_t readlimit) {
  if (stream_) {
    stream_->Mark(readlimit);
  }
}

bool FontInputStream::MarkSupported() {
  if (stream_) {
    return stream_->MarkSupported();
  }
  return false;
}

void FontInputStream::Reset() {
  if (stream_) {
    stream_->Reset();
  }
}

int32_t FontInputStream::Read() {
  if (!stream_ || (bounded_ && position_ >= length_)) {
    return -1;
  }
  int32_t b = stream_->Read();
  if (b >= 0) {
    position_++;
  }
  return b;
}

int32_t FontInputStream::Read(ByteVector* b, int32_t offset, int32_t length) {
  if (!stream_ || offset < 0 || length < 0 ||
      (bounded_ && position_ >= length_)) {
    return -1;
  }
  int32_t bytes_to_read =
      bounded_ ? std::min<int32_t>(length, (int32_t)(length_ - position_)) :
                 length;
  int32_t bytes_read = stream_->Read(b, offset, bytes_to_read);
  position_ += bytes_read;
  return bytes_read;
}

int32_t FontInputStream::Read(ByteVector* b) {
  return Read(b, 0, b->size());
}

int32_t FontInputStream::ReadChar() {
  return Read();
}

int32_t FontInputStream::ReadUShort() {
  return 0xffff & (Read() << 8 | Read());
}

int32_t FontInputStream::ReadShort() {
  return ((Read() << 8 | Read()) << 16) >> 16;
}

int32_t FontInputStream::ReadUInt24() {
  return 0xffffff & (Read() << 16 | Read() << 8 | Read());
}

int64_t FontInputStream::ReadULong() {
  return 0xffffffffL & ReadLong();
}

int32_t FontInputStream::ReadULongAsInt() {
  int64_t ulong = ReadULong();
  return ((int32_t)ulong) & ~0x80000000;
}

int32_t FontInputStream::ReadLong() {
  return Read() << 24 | Read() << 16 | Read() << 8 | Read();
}

int32_t FontInputStream::ReadFixed() {
  return ReadLong();
}

int64_t FontInputStream::ReadDateTimeAsLong() {
  return (int64_t)ReadULong() << 32 | ReadULong();
}

int64_t FontInputStream::Skip(int64_t n) {
  if (stream_) {
    int64_t skipped = stream_->Skip(n);
    position_ += skipped;
    return skipped;
  }
  return 0;
}

}  // namespace sfntly
