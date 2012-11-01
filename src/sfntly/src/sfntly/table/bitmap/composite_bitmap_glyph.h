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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_COMPOSITE_BITMAP_GLYPH_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_COMPOSITE_BITMAP_GLYPH_H_

#include "sfntly/table/bitmap/bitmap_glyph.h"

namespace sfntly {

class CompositeBitmapGlyph : public BitmapGlyph,
                             public RefCounted<CompositeBitmapGlyph> {
 public:
  class Component {
   public:
    Component(const Component& rhs);

    int32_t glyph_code() { return glyph_code_; }
    int32_t x_offset() { return x_offset_; }
    int32_t y_offset() { return y_offset_; }

    // UNIMPLEMENTED: int hashCode()
    bool operator==(const Component& rhs);
    Component& operator=(const Component& rhs);

   protected:
    Component(int32_t glyph_code, int32_t x_offset, int32_t y_offset);

   private:
    int32_t glyph_code_;
    int32_t x_offset_;
    int32_t y_offset_;

    friend class CompositeBitmapGlyph;
  };

  class Builder : public BitmapGlyph::Builder,
                  public RefCounted<Builder> {
   public:
    Builder(WritableFontData* data, int32_t format);
    Builder(ReadableFontData* data, int32_t format);
    virtual ~Builder();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
  };

  CompositeBitmapGlyph(ReadableFontData* data, int32_t format);
  virtual ~CompositeBitmapGlyph();
  int32_t NumComponents();
  // Note: returned immutable object over stack.
  Component GetComponent(int32_t component_num) const;

 private:
  void Initialize(int32_t format);

  int32_t num_components_offset_;
  int32_t component_array_offset_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_COMPOSITE_BITMAP_GLYPH_H_
