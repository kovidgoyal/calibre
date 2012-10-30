/*
 * Copyright 2011 Google Inc. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0  = the "License");
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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_SIMPLE_BITMAP_GLYPH_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_SIMPLE_BITMAP_GLYPH_H_

#include "sfntly/table/bitmap/bitmap_glyph.h"

namespace sfntly {

class SimpleBitmapGlyph : public BitmapGlyph,
                          public RefCounted<SimpleBitmapGlyph> {
 public:
  class Builder : public BitmapGlyph::Builder,
                  public RefCounted<Builder> {
   public:
    Builder(WritableFontData* data, int32_t format);
    Builder(ReadableFontData* data, int32_t format);
    virtual ~Builder();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
  };

  SimpleBitmapGlyph(ReadableFontData* data, int32_t format);
  virtual ~SimpleBitmapGlyph();
};
typedef Ptr<SimpleBitmapGlyph> SimpleBitmapGlyphPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_SIMPLE_BITMAP_GLYPH_H_
