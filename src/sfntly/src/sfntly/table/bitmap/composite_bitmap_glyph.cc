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

#include "sfntly/table/bitmap/composite_bitmap_glyph.h"

namespace sfntly {
/******************************************************************************
 * CompositeBitmapGlyph class
 ******************************************************************************/
CompositeBitmapGlyph::CompositeBitmapGlyph(ReadableFontData* data,
                                           int32_t format)
    : BitmapGlyph(data, format) {
  Initialize(format);
}

CompositeBitmapGlyph::~CompositeBitmapGlyph() {
}

int32_t CompositeBitmapGlyph::NumComponents() {
  return data_->ReadUShort(num_components_offset_);
}

CompositeBitmapGlyph::Component CompositeBitmapGlyph::GetComponent(
    int32_t component_num) const {
  int32_t component_offset = component_array_offset_ +
                             component_num * Offset::kEbdtComponentLength;
  return CompositeBitmapGlyph::Component(
      data_->ReadUShort(component_offset + Offset::kEbdtComponent_glyphCode),
      data_->ReadChar(component_offset + Offset::kEbdtComponent_xOffset),
      data_->ReadChar(component_offset + Offset::kEbdtComponent_yOffset));
}

void CompositeBitmapGlyph::Initialize(int32_t format) {
  if (format == 8) {
    num_components_offset_ = Offset::kGlyphFormat8_numComponents;
    component_array_offset_ = Offset::kGlyphFormat8_componentArray;
  } else if (format == 9) {
    num_components_offset_ = Offset::kGlyphFormat9_numComponents;
    component_array_offset_ = Offset::kGlyphFormat9_componentArray;
  } else {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IllegalStateException("Attempt to create a Composite Bitmap Glyph "
                                "with a non-composite format.");
#endif
  }
}

/******************************************************************************
 * CompositeBitmapGlyph::Component class
 ******************************************************************************/
CompositeBitmapGlyph::Component::Component(const Component& rhs)
    : glyph_code_(rhs.glyph_code_),
      x_offset_(rhs.x_offset_),
      y_offset_(rhs.y_offset_) {
}

bool CompositeBitmapGlyph::Component::operator==(
    const CompositeBitmapGlyph::Component& rhs) {
  return glyph_code_ == rhs.glyph_code_;
}

CompositeBitmapGlyph::Component& CompositeBitmapGlyph::Component::operator=(
    const CompositeBitmapGlyph::Component& rhs) {
  glyph_code_ = rhs.glyph_code_;
  x_offset_ = rhs.x_offset_;
  y_offset_ = rhs.y_offset_;
  return *this;
}

CompositeBitmapGlyph::Component::Component(int32_t glyph_code,
                                           int32_t x_offset,
                                           int32_t y_offset)
    : glyph_code_(glyph_code), x_offset_(x_offset), y_offset_(y_offset) {
}

/******************************************************************************
 * CompositeBitmapGlyph::Builder class
 ******************************************************************************/
CompositeBitmapGlyph::Builder::Builder(ReadableFontData* data, int32_t format)
    : BitmapGlyph::Builder(data, format) {
}

CompositeBitmapGlyph::Builder::Builder(WritableFontData* data, int32_t format)
    : BitmapGlyph::Builder(data, format) {
}

CompositeBitmapGlyph::Builder::~Builder() {
}

CALLER_ATTACH FontDataTable*
CompositeBitmapGlyph::Builder::SubBuildTable(ReadableFontData* data) {
  Ptr<CompositeBitmapGlyph> glyph = new CompositeBitmapGlyph(data, format());
  return glyph.Detach();
}

}  // namespace sfntly
