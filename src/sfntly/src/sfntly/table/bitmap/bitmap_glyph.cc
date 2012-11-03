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

#include "sfntly/table/bitmap/bitmap_glyph.h"
#include "sfntly/table/bitmap/simple_bitmap_glyph.h"
#include "sfntly/table/bitmap/composite_bitmap_glyph.h"

namespace sfntly {
/******************************************************************************
 * BitmapGlyph class
 ******************************************************************************/
BitmapGlyph::~BitmapGlyph() {
}

CALLER_ATTACH BitmapGlyph* BitmapGlyph::CreateGlyph(ReadableFontData* data,
                                                    int32_t format) {
  BitmapGlyphPtr glyph;
  BitmapGlyphBuilderPtr builder;
  builder.Attach(Builder::CreateGlyphBuilder(data, format));
  if (builder) {
    glyph.Attach(down_cast<BitmapGlyph*>(builder->Build()));
  }
  return glyph;
}

BitmapGlyph::BitmapGlyph(ReadableFontData* data, int32_t format)
    : SubTable(data), format_(format) {
}

/******************************************************************************
 * BitmapGlyph::Builder class
 ******************************************************************************/
BitmapGlyph::Builder::~Builder() {
}

CALLER_ATTACH BitmapGlyph::Builder*
BitmapGlyph::Builder::CreateGlyphBuilder(ReadableFontData* data,
                                         int32_t format) {
  BitmapGlyphBuilderPtr builder;
  switch (format) {
    case 1:
    case 2:
    case 3:
    case 4:
    case 5:
    case 6:
    case 7:
      builder = new SimpleBitmapGlyph::Builder(data, format);
      break;
    case 8:
    case 9:
      builder = new CompositeBitmapGlyph::Builder(data, format);
      break;
  }
  return builder.Detach();
}

BitmapGlyph::Builder::Builder(WritableFontData* data, int32_t format)
    : SubTable::Builder(data), format_(format) {
}

BitmapGlyph::Builder::Builder(ReadableFontData* data, int32_t format)
    : SubTable::Builder(data), format_(format) {
}

CALLER_ATTACH
FontDataTable* BitmapGlyph::Builder::SubBuildTable(ReadableFontData* data) {
  UNREFERENCED_PARAMETER(data);
  return NULL;
}

void BitmapGlyph::Builder::SubDataSet() {
  // NOP
}

int32_t BitmapGlyph::Builder::SubDataSizeToSerialize() {
  return InternalReadData()->Length();
}

bool BitmapGlyph::Builder::SubReadyToSerialize() {
  return true;
}

int32_t BitmapGlyph::Builder::SubSerialize(WritableFontData* new_data) {
  return InternalReadData()->CopyTo(new_data);
}

}  // namespace sfntly
