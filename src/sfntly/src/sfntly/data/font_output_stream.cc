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

#include "sfntly/data/font_output_stream.h"

#include <algorithm>

namespace sfntly {

FontOutputStream::FontOutputStream(OutputStream* os)
    : stream_(os),
      position_(0) {
}

FontOutputStream::~FontOutputStream() {
  // Do not close, underlying stream shall clean up themselves.
}

void FontOutputStream::Write(byte_t b) {
  if (stream_) {
    stream_->Write(b);
    position_++;
  }
}

void FontOutputStream::Write(ByteVector* b) {
  if (b) {
    Write(b, 0, b->size());
    position_ += b->size();
  }
}

void FontOutputStream::Write(ByteVector* b, int32_t off, int32_t len) {
  assert(b);
  assert(stream_);
  if (off < 0 || len < 0 || off + len < 0 ||
      static_cast<size_t>(off + len) > b->size()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#else
    return;
#endif
  }

  stream_->Write(b, off, len);
  position_ += len;
}

void FontOutputStream::Write(byte_t* b, int32_t off, int32_t len) {
  assert(b);
  assert(stream_);
  if (off < 0 || len < 0 || off + len < 0) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#else
    return;
#endif
  }

  stream_->Write(b, off, len);
  position_ += len;
}

void FontOutputStream::WriteChar(byte_t c) {
  Write(c);
}

void FontOutputStream::WriteUShort(int32_t us) {
  Write((byte_t)((us >> 8) & 0xff));
  Write((byte_t)(us & 0xff));
}

void FontOutputStream::WriteShort(int32_t s) {
  WriteUShort(s);
}

void FontOutputStream::WriteUInt24(int32_t ui) {
  Write((byte_t)(ui >> 16) & 0xff);
  Write((byte_t)(ui >> 8) & 0xff);
  Write((byte_t)ui & 0xff);
}

void FontOutputStream::WriteULong(int64_t ul) {
  Write((byte_t)((ul >> 24) & 0xff));
  Write((byte_t)((ul >> 16) & 0xff));
  Write((byte_t)((ul >> 8) & 0xff));
  Write((byte_t)(ul & 0xff));
}

void FontOutputStream::WriteLong(int64_t l) {
  WriteULong(l);
}

void FontOutputStream::WriteFixed(int32_t f) {
  WriteULong(f);
}

void FontOutputStream::WriteDateTime(int64_t date) {
  WriteULong((date >> 32) & 0xffffffff);
  WriteULong(date & 0xffffffff);
}

void FontOutputStream::Flush() {
  if (stream_) {
    stream_->Flush();
  }
}

void FontOutputStream::Close() {
  if (stream_) {
    stream_->Flush();
    stream_->Close();
    position_ = 0;
  }
}

}  // namespace sfntly
