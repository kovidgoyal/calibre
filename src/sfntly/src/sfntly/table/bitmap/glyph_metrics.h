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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_GLYPH_METRICS_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_GLYPH_METRICS_H_

#include "sfntly/table/subtable.h"

namespace sfntly {

class GlyphMetrics : public SubTable {
 public:
  virtual ~GlyphMetrics();

 protected:
  class Builder : public SubTable::Builder {
   public:
    virtual ~Builder();

   protected:
    explicit Builder(WritableFontData* data);
    explicit Builder(ReadableFontData* data);
  };

  explicit GlyphMetrics(ReadableFontData* data);
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_GLYPH_METRICS_H_
