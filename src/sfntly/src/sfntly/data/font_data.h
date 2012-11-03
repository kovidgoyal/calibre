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

#ifndef SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_DATA_H_
#define SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_DATA_H_

#include <limits.h>

#include <vector>

#include "sfntly/port/type.h"
#include "sfntly/data/byte_array.h"
#include "sfntly/port/refcount.h"

namespace sfntly {

struct DataSize {
  enum {
    kBYTE = 1,
    kCHAR = 1,
    kUSHORT = 2,
    kSHORT = 2,
    kUINT24 = 3,
    kULONG = 4,
    kLONG = 4,
    kFixed = 4,
    kFUNIT = 4,
    kFWORD = 2,
    kUFWORD = 2,
    kF2DOT14 = 2,
    kLONGDATETIME = 8,
    kTag = 4,
    kGlyphID = 2,
    kOffset = 2
  };
};

class FontData : virtual public RefCount {
 public:
  // Gets the maximum size of the FontData. This is the maximum number of bytes
  // that the font data can hold and all of it may not be filled with data or
  // even fully allocated yet.
  // @return the maximum size of this font data
  virtual int32_t Size() const;

  // Sets limits on the size of the FontData. The FontData is then only
  // visible within the bounds set.
  // @param offset the start of the new bounds
  // @param length the number of bytes in the bounded array
  // @return true if the bounding range was successful; false otherwise
  virtual bool Bound(int32_t offset, int32_t length);

  // Sets limits on the size of the FontData. This is a offset bound only so if
  // the FontData is writable and growable then there is no limit to that growth
  // from the bounding operation.
  // @param offset the start of the new bounds which must be within the current
  //        size of the FontData
  // @return true if the bounding range was successful; false otherwise
  virtual bool Bound(int32_t offset);

  // Makes a slice of this FontData. The returned slice will share the data with
  // the original <code>FontData</code>.
  // @param offset the start of the slice
  // @param length the number of bytes in the slice
  // @return a slice of the original FontData
  virtual CALLER_ATTACH FontData* Slice(int32_t offset, int32_t length) = 0;

  // Makes a bottom bound only slice of this array. The returned slice will
  // share the data with the original <code>FontData</code>.
  // @param offset the start of the slice
  // @return a slice of the original FontData
  virtual CALLER_ATTACH FontData* Slice(int32_t offset) = 0;

  // Gets the length of the data.
  virtual int32_t Length() const;

 protected:
  // Constructor.
  // @param ba the byte array to use for the backing data
  explicit FontData(ByteArray* ba);

  // Constructor.
  // @param data the data to wrap
  // @param offset the offset to start the wrap from
  // @param length the length of the data wrapped
  FontData(FontData* data, int32_t offset, int32_t length);

  // Constructor.
  // @param data the data to wrap
  // @param offset the offset to start the wrap from
  FontData(FontData* data, int32_t offset);
  virtual ~FontData();

  void Init(ByteArray* ba);

  // Gets the offset in the underlying data taking into account any bounds on
  // the data.
  // @param offset the offset to get the bound compensated offset for
  // @return the bound compensated offset
  int32_t BoundOffset(int32_t offset);

  // Gets the length in the underlying data taking into account any bounds on
  // the data.
  // @param offset the offset that the length is being used at
  // @param length the length to get the bound compensated length for
  // @return the bound compensated length
  int32_t BoundLength(int32_t offset, int32_t length);

  static const int32_t GROWABLE_SIZE = INT_MAX;

  // TODO(arthurhsu): style guide violation: refactor this protected member
  ByteArrayPtr array_;

 private:
  int32_t bound_offset_;
  int32_t bound_length_;
};
typedef Ptr<FontData> FontDataPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_DATA_FONT_DATA_H_
