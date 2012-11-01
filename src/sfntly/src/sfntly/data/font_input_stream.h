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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_INPUT_STREAM_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_INPUT_STREAM_H_

#include "sfntly/port/type.h"
#include "sfntly/port/input_stream.h"

namespace sfntly {

// An input stream for reading font data.
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

// Note: Original class inherits from Java's FilterOutputStream, which wraps
//       an InputStream within.  In C++, we directly do the wrapping without
//       defining another layer of abstraction.  The wrapped output stream is
//       *NOT* reference counted (because it's meaningless to ref-count an I/O
//       stream).
class FontInputStream : public InputStream {
 public:
  // Constructor.
  // @param is input stream to wrap
  explicit FontInputStream(InputStream* is);

  // Constructor for a bounded font input stream.
  // @param is input stream to wrap
  // @param length the maximum length of bytes to read
  FontInputStream(InputStream* is, size_t length);

  virtual ~FontInputStream();


  virtual int32_t Available();
  virtual void Close();
  virtual void Mark(int32_t readlimit);
  virtual bool MarkSupported();
  virtual void Reset();

  virtual int32_t Read();
  virtual int32_t Read(ByteVector* buffer);
  virtual int32_t Read(ByteVector* buffer, int32_t offset, int32_t length);

  // Get the current position in the stream in bytes.
  // @return the current position in bytes
  virtual int64_t position() { return position_; }

  virtual int32_t ReadChar();
  virtual int32_t ReadUShort();
  virtual int32_t ReadShort();
  virtual int32_t ReadUInt24();
  virtual int64_t ReadULong();
  virtual int32_t ReadULongAsInt();
  virtual int32_t ReadLong();
  virtual int32_t ReadFixed();
  virtual int64_t ReadDateTimeAsLong();
  virtual int64_t Skip(int64_t n);  // n can be negative.

 private:
  InputStream* stream_;
  int64_t position_;
  int64_t length_;  // Bound on length of data to read.
  bool bounded_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_INPUT_STREAM_H_
