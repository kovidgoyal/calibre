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

#include "sfntly/table/bitmap/small_glyph_metrics.h"

namespace sfntly {
/******************************************************************************
 * SmallGlyphMetrics class
 ******************************************************************************/
SmallGlyphMetrics::SmallGlyphMetrics(ReadableFontData* data)
    : GlyphMetrics(data) {
}

SmallGlyphMetrics::~SmallGlyphMetrics() {
}

int32_t SmallGlyphMetrics::Height() {
  return data_->ReadByte(Offset::kHeight);
}

int32_t SmallGlyphMetrics::Width() {
  return data_->ReadByte(Offset::kWidth);
}

int32_t SmallGlyphMetrics::BearingX() {
  return data_->ReadByte(Offset::kBearingX);
}

int32_t SmallGlyphMetrics::BearingY() {
  return data_->ReadByte(Offset::kBearingY);
}

int32_t SmallGlyphMetrics::Advance() {
  return data_->ReadByte(Offset::kAdvance);
}

/******************************************************************************
 * SmallGlyphMetrics::Builder class
 ******************************************************************************/
SmallGlyphMetrics::Builder::Builder(WritableFontData* data)
    : GlyphMetrics::Builder(data) {
}

SmallGlyphMetrics::Builder::Builder(ReadableFontData* data)
    : GlyphMetrics::Builder(data) {
}

SmallGlyphMetrics::Builder::~Builder() {
}

int32_t SmallGlyphMetrics::Builder::Height() {
  return InternalReadData()->ReadByte(Offset::kHeight);
}

void SmallGlyphMetrics::Builder::SetHeight(byte_t height) {
  InternalWriteData()->WriteByte(Offset::kHeight, height);
}

int32_t SmallGlyphMetrics::Builder::Width() {
  return InternalReadData()->ReadByte(Offset::kWidth);
}

void SmallGlyphMetrics::Builder::SetWidth(byte_t width) {
  InternalWriteData()->WriteByte(Offset::kWidth, width);
}

int32_t SmallGlyphMetrics::Builder::BearingX() {
  return InternalReadData()->ReadByte(Offset::kBearingX);
}

void SmallGlyphMetrics::Builder::SetBearingX(byte_t bearing) {
  InternalWriteData()->WriteByte(Offset::kBearingX, bearing);
}

int32_t SmallGlyphMetrics::Builder::BearingY() {
  return InternalReadData()->ReadByte(Offset::kBearingY);
}

void SmallGlyphMetrics::Builder::SetBearingY(byte_t bearing) {
  InternalWriteData()->WriteByte(Offset::kBearingY, bearing);
}

int32_t SmallGlyphMetrics::Builder::Advance() {
  return InternalReadData()->ReadByte(Offset::kAdvance);
}

void SmallGlyphMetrics::Builder::SetAdvance(byte_t advance) {
  InternalWriteData()->WriteByte(Offset::kAdvance, advance);
}

CALLER_ATTACH FontDataTable*
    SmallGlyphMetrics::Builder::SubBuildTable(ReadableFontData* data) {
  SmallGlyphMetricsPtr output = new SmallGlyphMetrics(data);
  return output.Detach();
}

void SmallGlyphMetrics::Builder::SubDataSet() {
  // NOP.
}

int32_t SmallGlyphMetrics::Builder::SubDataSizeToSerialize() {
  return 0;
}

bool SmallGlyphMetrics::Builder::SubReadyToSerialize() {
  return false;
}

int32_t SmallGlyphMetrics::Builder::SubSerialize(WritableFontData* new_data) {
  return Data()->CopyTo(new_data);
}

}  // namespace sfntly
