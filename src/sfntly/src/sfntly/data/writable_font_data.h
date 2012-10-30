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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_WRITABLE_FONT_DATA_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_WRITABLE_FONT_DATA_H_

#include "sfntly/data/readable_font_data.h"

namespace sfntly {

// Writable font data wrapper. Supports writing of data primitives in the
// TrueType / OpenType spec.
class WritableFontData : public ReadableFontData {
 public:
  explicit WritableFontData(ByteArray* ba);
  virtual ~WritableFontData();

  // Constructs a writable font data object. If the length is specified as
  // positive then a fixed size font data object will be created. If the length
  // is zero or less then a growable font data object will be created and the
  // size will be used as an estimate to help in allocating the original space.
  // @param length if length > 0 create a fixed length font data; otherwise
  //        create a growable font data
  // @return a new writable font data
  static CALLER_ATTACH WritableFontData* CreateWritableFontData(int32_t length);

  // Constructs a writable font data object. The new font data object will wrap
  // the bytes passed in to the factory and it will take make a copy of those
  // bytes.
  // @param b the byte vector to wrap
  // @return a new writable font data
  static CALLER_ATTACH WritableFontData* CreateWritableFontData(ByteVector* b);

  // Write a byte at the given index.
  // @param index index into the font data
  // @param b the byte to write
  // @return the number of bytes written
  virtual int32_t WriteByte(int32_t index, byte_t b);

  // Write the bytes from the array.
  // @param index index into the font data
  // @param b the source for the bytes to be written
  // @param offset offset in the byte array
  // @param length the length of the bytes to be written
  // @return the number of bytes actually written; -1 if the index is outside
  //         the FontData's range
  virtual int32_t WriteBytes(int32_t index,
                             byte_t* b,
                             int32_t offset,
                             int32_t length);

  // Write the bytes from the array.
  // @param index index into the font data
  // @param b the source for the bytes to be written
  // @return the number of bytes actually written; -1 if the index is outside
  //         the FontData's range
  virtual int32_t WriteBytes(int32_t index, ByteVector* b);

  // Write the bytes from the array and pad if necessary.
  // Write to the length given using the byte array provided and if there are
  // not enough bytes in the array then pad to the requested length using the
  // pad byte specified.
  // @param index index into the font data
  // @param b the source for the bytes to be written
  // @param offset offset in the byte array
  // @param length the length of the bytes to be written
  // @param pad the padding byte to be used if necessary
  // @return the number of bytes actually written
  virtual int32_t WriteBytesPad(int32_t index,
                                ByteVector* b,
                                int32_t offset,
                                int32_t length,
                                byte_t pad);

  // Writes padding to the FontData. The padding byte written is 0x00.
  // @param index index into the font data
  // @param count the number of pad bytes to write
  // @return the number of pad bytes written
  virtual int32_t WritePadding(int32_t index, int32_t count);

  // Writes padding to the FontData.
  // @param index index into the font data
  // @param count the number of pad bytes to write
  // @param pad the byte value to use as padding
  // @return the number of pad bytes written
  virtual int32_t WritePadding(int32_t index, int32_t count, byte_t pad);

  // Write the CHAR at the given index.
  // @param index index into the font data
  // @param c the CHAR
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteChar(int32_t index, byte_t c);

  // Write the USHORT at the given index.
  // @param index index into the font data
  // @param us the USHORT
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteUShort(int32_t index, int32_t us);

  // Write the USHORT at the given index in little endian format.
  // @param index index into the font data
  // @param us the USHORT
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteUShortLE(int32_t index, int32_t us);

  // Write the SHORT at the given index.
  // @param index index into the font data
  // @param s the SHORT
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteShort(int32_t index, int32_t s);

  // Write the UINT24 at the given index.
  // @param index index into the font data
  // @param ui the UINT24
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteUInt24(int32_t index, int32_t ui);

  // Write the ULONG at the given index.
  // @param index index into the font data
  // @param ul the ULONG
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteULong(int32_t index, int64_t ul);

  // Write the ULONG at the given index in little endian format.
  // @param index index into the font data
  // @param ul the ULONG
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteULongLE(int32_t index, int64_t ul);

  // Write the LONG at the given index.
  // @param index index into the font data
  // @param l the LONG
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteLong(int32_t index, int64_t l);

  // Write the Fixed at the given index.
  // @param index index into the font data
  // @param f the Fixed
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteFixed(int32_t index, int32_t f);

  // Write the LONGDATETIME at the given index.
  // @param index index into the font data
  // @param date the LONGDATETIME
  // @return the number of bytes actually written
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t WriteDateTime(int32_t index, int64_t date);

  // Copy from the InputStream into this FontData.
  // @param is the source
  // @param length the number of bytes to copy
  // @throws IOException
  virtual void CopyFrom(InputStream* is, int32_t length);

  // Copy everything from the InputStream into this FontData.
  // @param is the source
  // @throws IOException
  virtual void CopyFrom(InputStream* is);

  // Makes a slice of this FontData. The returned slice will share the data with
  // the original FontData.
  // @param offset the start of the slice
  // @param length the number of bytes in the slice
  // @return a slice of the original FontData
  virtual CALLER_ATTACH FontData* Slice(int32_t offset, int32_t length);

  // Makes a bottom bound only slice of this array. The returned slice will
  // share the data with the original FontData.
  // @param offset the start of the slice
  // @return a slice of the original FontData
  virtual CALLER_ATTACH FontData* Slice(int32_t offset);

 private:
  // Constructor with a lower bound.
  // @param data other WritableFontData object to share data with
  // @param offset offset from the other WritableFontData's data
  WritableFontData(WritableFontData* data, int32_t offset);

  // Constructor with lower bound and a length bound.
  // @param data other WritableFontData object to share data with
  // @param offset offset from the other WritableFontData's data
  // @param length length of other WritableFontData's data to use
  WritableFontData(WritableFontData* data, int32_t offset, int32_t length);
};
typedef Ptr<WritableFontData> WritableFontDataPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_WRITABLE_FONT_DATA_H_
