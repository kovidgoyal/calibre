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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_GLYPH_INFO_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_GLYPH_INFO_H_

#include <vector>
#include <map>

#include "sfntly/table/subtable.h"

namespace sfntly {

// An immutable class holding bitmap glyph information.
class BitmapGlyphInfo : public RefCounted<BitmapGlyphInfo> {
 public:
  // Constructor for a relative located glyph. The glyph's position in the EBDT
  // table is a combination of it's block offset and it's own start offset.
  // @param glyphId the glyph id
  // @param blockOffset the offset of the block to which the glyph belongs
  // @param startOffset the offset of the glyph within the block
  // @param length the byte length
  // @param format the glyph image format
  BitmapGlyphInfo(int32_t glyph_id,
                  int32_t block_offset,
                  int32_t start_offset,
                  int32_t length,
                  int32_t format);

  // Constructor for an absolute located glyph. The glyph's position in the EBDT
  // table is only given by it's own start offset.
  // @param glyphId the glyph id
  // @param startOffset the offset of the glyph within the block
  // @param length the byte length
  // @param format the glyph image format
  BitmapGlyphInfo(int32_t glyph_id,
                  int32_t start_offset,
                  int32_t length,
                  int32_t format);

  int32_t glyph_id() const { return glyph_id_; }
  bool relative() const { return relative_; }
  int32_t block_offset() const { return block_offset_; }
  int32_t offset() const { return block_offset() + start_offset(); }
  int32_t start_offset() const { return start_offset_; }
  int32_t length() const { return length_; }
  int32_t format() const { return format_; }

  // UNIMPLEMENTED: hashCode()
  bool operator==(const BitmapGlyphInfo& rhs) const;
  bool operator==(BitmapGlyphInfo* rhs);

 private:
  int32_t glyph_id_;
  bool relative_;
  int32_t block_offset_;
  int32_t start_offset_;
  int32_t length_;
  int32_t format_;
};
typedef Ptr<BitmapGlyphInfo> BitmapGlyphInfoPtr;
typedef std::map<int32_t, BitmapGlyphInfoPtr> BitmapGlyphInfoMap;
typedef std::vector<BitmapGlyphInfoMap> BitmapLocaList;

class StartOffsetComparator {
 public:
  bool operator()(BitmapGlyphInfo* lhs, BitmapGlyphInfo* rhs);
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_GLYPH_INFO_H_
