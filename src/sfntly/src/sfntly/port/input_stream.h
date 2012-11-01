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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_INPUT_STREAM_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_INPUT_STREAM_H_

#include "sfntly/port/type.h"

namespace sfntly {

// C++ equivalent to Java's OutputStream class
class InputStream {
 public:
  // Make gcc -Wnon-virtual-dtor happy.
  virtual ~InputStream() {}

  virtual int32_t Available() = 0;
  virtual void Close() = 0;
  virtual void Mark(int32_t readlimit) = 0;
  virtual bool MarkSupported() = 0;
  virtual int32_t Read() = 0;
  virtual int32_t Read(ByteVector* b) = 0;
  virtual int32_t Read(ByteVector* b, int32_t offset, int32_t length) = 0;
  virtual void Reset() = 0;
  virtual int64_t Skip(int64_t n) = 0;
};

class PushbackInputStream : public InputStream {
 public:
  virtual void Unread(ByteVector* b) = 0;
  virtual void Unread(ByteVector* b, int32_t offset, int32_t length) = 0;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_INPUT_STREAM_H_
