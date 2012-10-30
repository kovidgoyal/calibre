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

#include "sfntly/table/bitmap/bitmap_glyph_info.h"

namespace sfntly {

BitmapGlyphInfo::BitmapGlyphInfo(int32_t glyph_id,
                                 int32_t block_offset,
                                 int32_t start_offset,
                                 int32_t length,
                                 int32_t format)
    : glyph_id_(glyph_id),
      relative_(true),
      block_offset_(block_offset),
      start_offset_(start_offset),
      length_(length),
      format_(format) {
}

BitmapGlyphInfo::BitmapGlyphInfo(int32_t glyph_id,
                                 int32_t start_offset,
                                 int32_t length,
                                 int32_t format)
    : glyph_id_(glyph_id),
      relative_(false),
      block_offset_(0),
      start_offset_(start_offset),
      length_(length),
      format_(format) {
}

bool BitmapGlyphInfo::operator==(const BitmapGlyphInfo& rhs) const {
  return (format_ == rhs.format_ &&
          glyph_id_ == rhs.glyph_id_ &&
          length_ == rhs.length_ &&
          offset() == rhs.offset());
}

bool BitmapGlyphInfo::operator==(BitmapGlyphInfo* rhs) {
  if (rhs == NULL) {
    return this == NULL;
  }
  return (format_ == rhs->format() &&
          glyph_id_ == rhs->glyph_id() &&
          length_ == rhs->length() &&
          offset() == rhs->offset());
}

bool StartOffsetComparator::operator()(BitmapGlyphInfo* lhs,
                                       BitmapGlyphInfo* rhs) {
  return lhs->start_offset() > rhs->start_offset();
}

}  // namespace sfntly
