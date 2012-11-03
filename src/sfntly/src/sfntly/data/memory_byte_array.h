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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_MEMORY_BYTE_ARRAY_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_MEMORY_BYTE_ARRAY_H_

#include "sfntly/data/byte_array.h"

namespace sfntly {

class MemoryByteArray : public ByteArray, public RefCounted<MemoryByteArray> {
 public:
  // Construct a new MemoryByteArray with a new array of the size given. It is
  // assumed that none of the array is filled and readable.
  explicit MemoryByteArray(int32_t length);

  // Note: not implemented due to dangerous operations in constructor.
  //explicit MemoryByteArray(ByteVector* b);

  // Construct a new MemoryByteArray using byte array.
  // @param b the byte array that provides the actual storage
  // @param filled_length the index of the last byte in the array has data
  // Note: This is different from Java version, it does not take over the
  //       ownership of b.  Caller is responsible for handling the lifetime
  //       of b.  C++ port also assumes filled_length is buffer_length since
  //       there is not a reliable way to identify the actual size of buffer.
  MemoryByteArray(byte_t* b, int32_t filled_length);

  virtual ~MemoryByteArray();
  virtual int32_t CopyTo(OutputStream* os, int32_t offset, int32_t length);

  // Make gcc -Woverloaded-virtual happy.
  virtual int32_t CopyTo(ByteArray* array) { return ByteArray::CopyTo(array); }
  virtual int32_t CopyTo(ByteArray* array, int32_t offset, int32_t length) {
    return ByteArray::CopyTo(array, offset, length);
  }
  virtual int32_t CopyTo(int32_t dst_offset,
                         ByteArray* array,
                         int32_t src_offset,
                         int32_t length) {
    return ByteArray::CopyTo(dst_offset, array, src_offset, length);
  }
  virtual int32_t CopyTo(OutputStream* os) { return ByteArray::CopyTo(os); }

 protected:
  virtual void InternalPut(int32_t index, byte_t b);
  virtual int32_t InternalPut(int32_t index,
                              byte_t* b,
                              int32_t offset,
                              int32_t length);
  virtual byte_t InternalGet(int32_t index);
  virtual int32_t InternalGet(int32_t index,
                              byte_t* b,
                              int32_t offset,
                              int32_t length);
  virtual void Close();
  virtual byte_t* Begin();

 private:
  void Init();  // C++ port only, used to allocate memory outside constructor.

  byte_t* b_;
  bool allocated_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_MEMORY_BYTE_ARRAY_H_
