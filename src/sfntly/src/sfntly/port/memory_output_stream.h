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

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_MEMORY_OUTPUT_STREAM_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_MEMORY_OUTPUT_STREAM_H_

#include <cstddef>
#include <vector>

#include "sfntly/port/type.h"
#include "sfntly/port/output_stream.h"

namespace sfntly {

// OutputStream backed by STL vector

class MemoryOutputStream : public OutputStream {
 public:
  MemoryOutputStream();
  virtual ~MemoryOutputStream();

  virtual void Close() {}  // no-op
  virtual void Flush() {}  // no-op
  virtual void Write(ByteVector* buffer);
  virtual void Write(ByteVector* buffer, int32_t offset, int32_t length);
  virtual void Write(byte_t* buffer, int32_t offset, int32_t length);
  virtual void Write(byte_t b);

  byte_t* Get();
  size_t Size();

 private:
  std::vector<byte_t> store_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_MEMORY_OUTPUT_STREAM_H_
