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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_READABLE_FONT_DATA_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_READABLE_FONT_DATA_H_

#include "sfntly/data/font_data.h"
#include "sfntly/port/lock.h"

namespace sfntly {

class WritableFontData;
class OutputStream;

// Writable font data wrapper. Supports reading of data primitives in the
// TrueType / OpenType spec.
// The data types used are as listed:
// BYTE       8-bit unsigned integer.
// CHAR       8-bit signed integer.
// USHORT     16-bit unsigned integer.
// SHORT      16-bit signed integer.
// UINT24     24-bit unsigned integer.
// ULONG      32-bit unsigned integer.
// LONG       32-bit signed integer.
// Fixed      32-bit signed fixed-point number (16.16)
// FUNIT      Smallest measurable distance in the em space.
// FWORD      16-bit signed integer (SHORT) that describes a quantity in FUnits.
// UFWORD     16-bit unsigned integer (USHORT) that describes a quantity in
//            FUnits.
// F2DOT14    16-bit signed fixed number with the low 14 bits of fraction (2.14)
// LONGDATETIME  Date represented in number of seconds since 12:00 midnight,
//               January 1, 1904. The value is represented as a signed 64-bit
//               integer.

class ReadableFontData : public FontData,
                         public RefCounted<ReadableFontData> {
 public:
  explicit ReadableFontData(ByteArray* array);
  virtual ~ReadableFontData();

  static CALLER_ATTACH ReadableFontData* CreateReadableFontData(ByteVector* b);

  // Gets a computed checksum for the data. This checksum uses the OpenType spec
  // calculation. Every ULong value (32 bit unsigned) in the data is summed and
  // the resulting value is truncated to 32 bits. If the data length in bytes is
  // not an integral multiple of 4 then any remaining bytes are treated as the
  // start of a 4 byte sequence whose remaining bytes are zero.
  // @return the checksum
  int64_t Checksum();

  // Sets the bounds to use for computing the checksum. These bounds are in
  // begin and end pairs. If an odd number is given then the final range is
  // assumed to extend to the end of the data. The lengths of each range must be
  // a multiple of 4.
  // @param ranges the range bounds to use for the checksum
  void SetCheckSumRanges(const IntegerList& ranges);

  // Read the UBYTE at the given index.
  // @param index index into the font data
  // @return the UBYTE; -1 if outside the bounds of the font data
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadUByte(int32_t index);

  // Read the BYTE at the given index.
  // @param index index into the font data
  // @return the BYTE
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadByte(int32_t index);

  // Read the bytes at the given index into the array.
  // @param index index into the font data
  // @param b the destination for the bytes read
  // @param offset offset in the byte array to place the bytes
  // @param length the length of bytes to read
  // @return the number of bytes actually read; -1 if the index is outside the
  //         bounds of the font data
  virtual int32_t ReadBytes(int32_t index,
                            byte_t* b,
                            int32_t offset,
                            int32_t length);

  // Read the CHAR at the given index.
  // @param index index into the font data
  // @return the CHAR
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadChar(int32_t index);

  // Read the USHORT at the given index.
  // @param index index into the font data
  // @return the USHORT
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadUShort(int32_t index);

  // Read the SHORT at the given index.
  // @param index index into the font data
  // @return the SHORT
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadShort(int32_t index);

  // Read the UINT24 at the given index.
  // @param index index into the font data
  // @return the UINT24
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadUInt24(int32_t index);

  // Read the ULONG at the given index.
  // @param index index into the font data
  // @return the ULONG
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int64_t ReadULong(int32_t index);

  // Read the ULONG at the given index as int32_t.
  // @param index index into the font data
  // @return the ULONG
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadULongAsInt(int32_t index);

  // Read the ULONG at the given index, little-endian variant
  // @param index index into the font data
  // @return the ULONG
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int64_t ReadULongLE(int32_t index);

  // Read the LONG at the given index.
  // @param index index into the font data
  // @return the LONG
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadLong(int32_t index);

  // Read the Fixed at the given index.
  // @param index index into the font data
  // @return the Fixed
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadFixed(int32_t index);

  // Read the LONGDATETIME at the given index.
  // @param index index into the font data
  // @return the LONGDATETIME
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int64_t ReadDateTimeAsLong(int32_t index);

  // Read the FWORD at the given index.
  // @param index index into the font data
  // @return the FWORD
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadFWord(int32_t index);

  // Read the UFWORD at the given index.
  // @param index index into the font data
  // @return the UFWORD
  // @throws IndexOutOfBoundsException if index is outside the FontData's range
  virtual int32_t ReadFUFWord(int32_t index);

  // Note: Not ported because they just throw UnsupportedOperationException()
  //       in Java.
  /*
  virtual int32_t ReadFUnit(int32_t index);
  virtual int64_t ReadF2Dot14(int32_t index);
  */

  // Copy the FontData to an OutputStream.
  // @param os the destination
  // @return number of bytes copied
  // @throws IOException
  virtual int32_t CopyTo(OutputStream* os);

  // Copy the FontData to a WritableFontData.
  // @param wfd the destination
  // @return number of bytes copied
  // @throws IOException
  virtual int32_t CopyTo(WritableFontData* wfd);

  // Make gcc -Woverloaded-virtual happy.
  virtual int32_t CopyTo(ByteArray* ba);

  // Search for the key value in the range tables provided.
  // The search looks through the start-end pairs looking for the key value. It
  // is assumed that the start-end pairs are both represented by UShort values,
  // ranges do not overlap, and are monotonically increasing.
  // @param startIndex the position to read the first start value from
  // @param startOffset the offset between subsequent start values
  // @param endIndex the position to read the first end value from
  // @param endOffset the offset between subsequent end values
  // @param length the number of start-end pairs
  // @param key the value to search for
  // @return the index of the start-end pairs in which the key was found; -1
  //         otherwise
  int32_t SearchUShort(int32_t start_index,
                       int32_t start_offset,
                       int32_t end_index,
                       int32_t end_offset,
                       int32_t length,
                       int32_t key);

  // Search for the key value in the table provided.
  // The search looks through the values looking for the key value. It is
  // assumed that the are represented by UShort values and are monotonically
  // increasing.
  // @param startIndex the position to read the first start value from
  // @param startOffset the offset between subsequent start values
  // @param length the number of start-end pairs
  // @param key the value to search for
  // @return the index of the start-end pairs in which the key was found; -1
  //         otherwise
  int32_t SearchUShort(int32_t start_index,
                       int32_t start_offset,
                       int32_t length,
                       int32_t key);

  // Search for the key value in the range tables provided.
  // The search looks through the start-end pairs looking for the key value. It
  // is assumed that the start-end pairs are both represented by ULong values
  // that can be represented within 31 bits, ranges do not overlap, and are
  // monotonically increasing.
  // @param startIndex the position to read the first start value from
  // @param startOffset the offset between subsequent start values
  // @param endIndex the position to read the first end value from
  // @param endOffset the offset between subsequent end values
  // @param length the number of start-end pairs
  // @param key the value to search for
  // @return the index of the start-end pairs in which the key was found; -1
  //         otherwise
  int32_t SearchULong(int32_t start_index,
                      int32_t start_offset,
                      int32_t end_index,
                      int32_t end_offset,
                      int32_t length,
                      int32_t key);


  // TODO(arthurhsu): IMPLEMENT
  /*
  virtual int32_t ReadFUnit(int32_t index);
  virtual int64_t ReadF2Dot14(int32_t index);
  virtual int64_t ReadLongDateTime(int32_t index);
  */

  // Makes a slice of this FontData. The returned slice will share the data with
  // the original FontData.
  // @param offset the start of the slice
  // @param length the number of bytes in the slice
  // @return a slice of the original FontData
  // Note: C++ polymorphism requires return type to be consistent
  virtual CALLER_ATTACH FontData* Slice(int32_t offset, int32_t length);

  // Makes a bottom bound only slice of this array. The returned slice will
  // share the data with the original FontData.
  // @param offset the start of the slice
  // @return a slice of the original FontData
  // Note: C++ polymorphism requires return type to be consistent
  virtual CALLER_ATTACH FontData* Slice(int32_t offset);

  // Not Ported: toString()

 protected:
  // Constructor. Creates a bounded wrapper of another ReadableFontData from the
  // given offset until the end of the original ReadableFontData.
  // @param data data to wrap
  // @param offset the start of this data's view of the original data
  ReadableFontData(ReadableFontData* data, int32_t offset);

  // Constructor. Creates a bounded wrapper of another ReadableFontData from the
  // given offset until the end of the original ReadableFontData.
  // @param data data to wrap
  // @param offset the start of this data's view of the original data
  // @param length the length of the other FontData to use
  ReadableFontData(ReadableFontData* data, int32_t offset, int32_t length);

 private:
  // Compute the checksum for the font data using any ranges set for the
  // calculation.
  void ComputeChecksum();

  // Do the actual computation of the checksum for a range using the
  // TrueType/OpenType checksum algorithm. The range used is from the low bound
  // to the high bound in steps of four bytes. If any of the bytes within that 4
  // byte segment are not readable then it will considered a zero for
  // calculation.
  // Only called from within a synchronized method so it does not need to be
  // synchronized itself.
  // @param lowBound first position to start a 4 byte segment on
  // @param highBound last possible position to start a 4 byte segment on
  // @return the checksum for the total range
  int64_t ComputeCheckSum(int32_t low_bound, int32_t high_bound);

  Lock checksum_lock_;
  bool checksum_set_;
  int64_t checksum_;
  IntegerList checksum_range_;
};
typedef Ptr<ReadableFontData> ReadableFontDataPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_READABLE_FONT_DATA_H_
