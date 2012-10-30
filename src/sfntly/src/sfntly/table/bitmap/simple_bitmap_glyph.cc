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

#include "sfntly/table/bitmap/simple_bitmap_glyph.h"

namespace sfntly {

SimpleBitmapGlyph::SimpleBitmapGlyph(ReadableFontData* data, int32_t format)
    : BitmapGlyph(data, format) {
}

SimpleBitmapGlyph::~SimpleBitmapGlyph() {
}

SimpleBitmapGlyph::Builder::Builder(ReadableFontData* data, int32_t format)
    : BitmapGlyph::Builder(data, format) {
}

SimpleBitmapGlyph::Builder::Builder(WritableFontData* data, int32_t format)
    : BitmapGlyph::Builder(data, format) {
}

SimpleBitmapGlyph::Builder::~Builder() {
}

CALLER_ATTACH FontDataTable*
SimpleBitmapGlyph::Builder::SubBuildTable(ReadableFontData* data) {
  Ptr<SimpleBitmapGlyph> glyph = new SimpleBitmapGlyph(data, format());
  return glyph.Detach();
}

}  // namespace sfntly
