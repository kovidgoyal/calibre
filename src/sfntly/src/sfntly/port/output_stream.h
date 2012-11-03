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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_OUTPUT_STREAM_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_OUTPUT_STREAM_H_

#include "sfntly/port/type.h"

namespace sfntly {

// C++ equivalent to Java's OutputStream class
class OutputStream {
 public:
  // Make gcc -Wnon-virtual-dtor happy.
  virtual ~OutputStream() {}

  virtual void Close() = 0;
  virtual void Flush() = 0;
  virtual void Write(ByteVector* buffer) = 0;
  virtual void Write(byte_t b) = 0;

  // Note: C++ port offered both versions of Write() here.  The first one is
  //       better because it does check bounds.  The second one is there for
  //       performance concerns.
  virtual void Write(ByteVector* buffer, int32_t offset, int32_t length) = 0;

  // Note: Caller is responsible for the boundary of buffer.
  virtual void Write(byte_t* buffer, int32_t offset, int32_t length) = 0;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_OUTPUT_STREAM_H_
