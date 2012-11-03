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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_HEADER_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_HEADER_H_

#include "sfntly/port/refcount.h"

namespace sfntly {

class Header : public RefCounted<Header> {
 public:
  // Make a partial header with only the basic info for an empty new table.
  explicit Header(int32_t tag);

  // Make a partial header with only the basic info for a new table.
  Header(int32_t tag, int32_t length);

  // Make a full header as read from an existing font.
  Header(int32_t tag, int64_t checksum, int32_t offset, int32_t length);
  virtual ~Header();

  // Get the table tag.
  int32_t tag() { return tag_; }

  // Get the table offset. The offset is from the start of the font file.  This
  // offset value is what was read from the font file during construction of the
  // font. It may not be meaningful if the font was maninpulated through the
  // builders.
  int32_t offset() { return offset_; }

  // Is the offset in the header valid. The offset will not be valid if the
  // table was constructed during building and has no physical location in a
  // font file.
  bool offset_valid() { return offset_valid_; }

  // Get the length of the table as recorded in the table record header.  During
  // building the header length will reflect the length that was initially read
  // from the font file. This may not be consistent with the current state of
  // the data.
  int32_t length() { return length_; }

  // Is the length in the header valid. The length will not be valid if the
  // table was constructed during building and has no physical location in a
  // font file until the table is built from the builder.
  bool length_valid() { return length_valid_; }

  // Get the checksum for the table as recorded in the table record header.
  int64_t checksum() { return checksum_; }

  // Is the checksum valid. The checksum will not be valid if the table was
  // constructed during building and has no physical location in a font file.
  // Note that this does *NOT* check the validity of the checksum against
  // the calculated checksum for the table data.
  bool checksum_valid() { return checksum_valid_; }

  // UNIMPLEMENTED: boolean equals(Object obj)
  //                int hashCode()
  //                string toString()

 private:
  int32_t tag_;
  int32_t offset_;
  bool offset_valid_;
  int32_t length_;
  bool length_valid_;
  int64_t checksum_;
  bool checksum_valid_;

  friend class HeaderComparatorByOffset;
  friend class HeaderComparatorByTag;
};
typedef Ptr<Header> HeaderPtr;

class HeaderComparator {
 public:
  virtual ~HeaderComparator() {}
  virtual bool operator()(const HeaderPtr h1,
                          const HeaderPtr h2) = 0;
};

class HeaderComparatorByOffset : public HeaderComparator {
 public:
  virtual ~HeaderComparatorByOffset() {}
  virtual bool operator()(const HeaderPtr h1,
                          const HeaderPtr h2);
};

class HeaderComparatorByTag : public HeaderComparator {
 public:
  virtual ~HeaderComparatorByTag() {}
  virtual bool operator()(const HeaderPtr h1,
                          const HeaderPtr h2);
};

typedef std::set<HeaderPtr, HeaderComparatorByOffset> HeaderOffsetSortedSet;
typedef std::set<HeaderPtr, HeaderComparatorByTag> HeaderTagSortedSet;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_HEADER_H_
