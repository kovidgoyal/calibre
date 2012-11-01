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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_OUTPUT_STREAM_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_OUTPUT_STREAM_H_

#include "sfntly/port/type.h"
#include "sfntly/port/output_stream.h"

namespace sfntly {

// An output stream for writing font data.
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

// Note: The wrapped output stream is *NOT* reference counted (because it's
//       meaningless to ref-count an I/O stream).
class FontOutputStream : public OutputStream {
 public:
  explicit FontOutputStream(OutputStream* os);
  virtual ~FontOutputStream();

  virtual size_t position() { return position_; }

  virtual void Write(byte_t b);
  virtual void Write(ByteVector* b);
  virtual void Write(ByteVector* b, int32_t off, int32_t len);
  virtual void Write(byte_t* b, int32_t off, int32_t len);
  virtual void WriteChar(byte_t c);
  virtual void WriteUShort(int32_t us);
  virtual void WriteShort(int32_t s);
  virtual void WriteUInt24(int32_t ui);
  virtual void WriteULong(int64_t ul);
  virtual void WriteLong(int64_t l);
  virtual void WriteFixed(int32_t l);
  virtual void WriteDateTime(int64_t date);

  // Note: C++ port only.
  virtual void Flush();
  virtual void Close();

 private:
  // Note: we do not use the variable name out as in Java because it has
  //       special meaning in VC++ and will be very confusing.
  OutputStream* stream_;
  size_t position_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_OUTPUT_STREAM_H_
