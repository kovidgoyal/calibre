/*
 * Copyright (C) 2011 The sfntly Open Source Project
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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_BYTE_ARRAY_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_BYTE_ARRAY_H_

#include "sfntly/port/refcount.h"
#include "sfntly/port/type.h"
#include "sfntly/port/input_stream.h"
#include "sfntly/port/output_stream.h"

namespace sfntly {

// An abstraction to a contiguous array of bytes.
// C++ port of this class assumes that the data are stored in a linear region
// like std::vector.
class ByteArray : virtual public RefCount {
 public:
  virtual ~ByteArray();

  // Gets the current filled and readable length of the array.
  int32_t Length();

  // Gets the maximum size of the array. This is the maximum number of bytes that
  // the array can hold and all of it may not be filled with data or even fully
  // allocated yet.
  int32_t Size();

  // Determines whether or not this array is growable or of fixed size.
  bool growable() { return growable_; }

  int32_t SetFilledLength(int32_t filled_length);

  // Gets the byte from the given index.
  // @param index the index into the byte array
  // @return the byte or -1 if reading beyond the bounds of the data
  virtual int32_t Get(int32_t index);

  // Gets the bytes from the given index and fill the buffer with them. As many
  // bytes as will fit into the buffer are read unless that would go past the
  // end of the array.
  // @param index the index into the byte array
  // @param b the buffer to put the bytes read into
  // @return the number of bytes read from the buffer
  virtual int32_t Get(int32_t index, ByteVector* b);

  // Gets the bytes from the given index and fill the buffer with them starting
  // at the offset given. As many bytes as the specified length are read unless
  // that would go past the end of the array.
  // @param index the index into the byte array
  // @param b the buffer to put the bytes read into
  // @param offset the location in the buffer to start putting the bytes
  // @param length the number of bytes to put into the buffer
  // @return the number of bytes read from the buffer
  virtual int32_t Get(int32_t index,
                      byte_t* b,
                      int32_t offset,
                      int32_t length);

  // Puts the specified byte into the array at the given index unless that would
  // be beyond the length of the array and it isn't growable.
  virtual void Put(int32_t index, byte_t b);

  // Puts the specified bytes into the array at the given index. The entire
  // buffer is put into the array unless that would extend beyond the length and
  // the array isn't growable.
  virtual int32_t Put(int32_t index, ByteVector* b);

  // Puts the specified bytes into the array at the given index. All of the bytes
  // specified are put into the array unless that would extend beyond the length
  // and the array isn't growable. The bytes to be put into the array are those
  // in the buffer from the given offset and for the given length.
  // @param index the index into the ByteArray
  // @param b the bytes to put into the array
  // @param offset the offset in the bytes to start copying from
  // @param length the number of bytes to copy into the array
  // @return the number of bytes actually written
  virtual int32_t Put(int32_t index,
                      byte_t* b,
                      int32_t offset,
                      int32_t length);

  // Fully copies this ByteArray to another ByteArray to the extent that the
  // destination array has storage for the data copied.
  virtual int32_t CopyTo(ByteArray* array);

  // Copies a segment of this ByteArray to another ByteArray.
  // @param array the destination
  // @param offset the offset in this ByteArray to start copying from
  // @param length the maximum length in bytes to copy
  // @return the number of bytes copied
  virtual int32_t CopyTo(ByteArray* array, int32_t offset, int32_t length);

  // Copies this ByteArray to another ByteArray.
  // @param dstOffset the offset in the destination array to start copying to
  // @param array the destination
  // @param srcOffset the offset in this ByteArray to start copying from
  // @param length the maximum length in bytes to copy
  // @return the number of bytes copied
  virtual int32_t CopyTo(int32_t dst_offset,
                         ByteArray* array,
                         int32_t src_offset,
                         int32_t length);

  // Copies this ByteArray to an OutputStream.
  // @param os the destination
  // @return the number of bytes copied
  virtual int32_t CopyTo(OutputStream* os);

  // Copies this ByteArray to an OutputStream.
  // @param os the destination
  // @param offset
  // @param length
  // @return the number of bytes copied
  virtual int32_t CopyTo(OutputStream* os, int32_t offset, int32_t length);

  // Copies from the InputStream into this ByteArray.
  // @param is the source
  // @param length the number of bytes to copy
  virtual bool CopyFrom(InputStream* is, int32_t length);

  // Copies everything from the InputStream into this ByteArray.
  // @param is the source
  virtual bool CopyFrom(InputStream* is);

 protected:
  // filledLength the length that is "filled" and readable counting from offset.
  // storageLength the maximum storage size of the underlying data.
  // growable is the storage growable - storageLength is the max growable size.
  ByteArray(int32_t filled_length, int32_t storage_length, bool growable);
  ByteArray(int32_t filled_length, int32_t storage_length);
  void Init(int32_t filled_length, int32_t storage_length, bool growable);

  // Internal subclass API

  // Stores the byte at the index given.
  // @param index the location to store at
  // @param b the byte to store
  virtual void InternalPut(int32_t index, byte_t b) = 0;

  // Stores the array of bytes at the given index.
  // @param index the location to store at
  // @param b the bytes to store
  // @param offset the offset to start from in the byte array
  // @param length the length of the byte array to store from the offset
  // @return the number of bytes actually stored
  virtual int32_t InternalPut(int32_t index,
                              byte_t* b,
                              int32_t offset,
                              int32_t length) = 0;

  // Gets the byte at the index given.
  // @param index the location to get from
  // @return the byte stored at the index
  virtual byte_t InternalGet(int32_t index) = 0;

  // Gets the bytes at the index given of the given length.
  // @param index the location to start getting from
  // @param b the array to put the bytes into
  // @param offset the offset in the array to put the bytes into
  // @param length the length of bytes to read
  // @return the number of bytes actually ready
  virtual int32_t InternalGet(int32_t index,
                              byte_t* b,
                              int32_t offset,
                              int32_t length) = 0;

  // Close this instance of the ByteArray.
  virtual void Close() = 0;

  // C++ port only, raw pointer to the first element of storage.
  virtual byte_t* Begin() = 0;

  // Java toString() not ported.

  static const int32_t COPY_BUFFER_SIZE;

 private:
  //bool bound_;  // unused, comment out
  int32_t filled_length_;
  int32_t storage_length_;
  bool growable_;
};
typedef Ptr<ByteArray> ByteArrayPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_BYTE_ARRAY_H_
