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

#include "sfntly/table/bitmap/big_glyph_metrics.h"

namespace sfntly {
/******************************************************************************
 * BigGlyphMetrics class
 ******************************************************************************/
BigGlyphMetrics::BigGlyphMetrics(ReadableFontData* data)
    : GlyphMetrics(data) {
}

BigGlyphMetrics::~BigGlyphMetrics() {
}

int32_t BigGlyphMetrics::Height() {
  return data_->ReadByte(Offset::kHeight);
}

int32_t BigGlyphMetrics::Width() {
  return data_->ReadByte(Offset::kWidth);
}

int32_t BigGlyphMetrics::HoriBearingX() {
  return data_->ReadByte(Offset::kHoriBearingX);
}

int32_t BigGlyphMetrics::HoriBearingY() {
  return data_->ReadByte(Offset::kHoriBearingY);
}

int32_t BigGlyphMetrics::HoriAdvance() {
  return data_->ReadByte(Offset::kHoriAdvance);
}

int32_t BigGlyphMetrics::VertBearingX() {
  return data_->ReadByte(Offset::kVertBearingX);
}

int32_t BigGlyphMetrics::VertBearingY() {
  return data_->ReadByte(Offset::kVertBearingY);
}

int32_t BigGlyphMetrics::VertAdvance() {
  return data_->ReadByte(Offset::kVertAdvance);
}

/******************************************************************************
 * BigGlyphMetrics::Builder class
 ******************************************************************************/
BigGlyphMetrics::Builder::Builder(WritableFontData* data)
    : GlyphMetrics::Builder(data) {
}

BigGlyphMetrics::Builder::Builder(ReadableFontData* data)
    : GlyphMetrics::Builder(data) {
}

BigGlyphMetrics::Builder::~Builder() {
}

int32_t BigGlyphMetrics::Builder::Height() {
  return InternalReadData()->ReadByte(Offset::kHeight);
}

void BigGlyphMetrics::Builder::SetHeight(byte_t height) {
  InternalWriteData()->WriteByte(Offset::kHeight, height);
}

int32_t BigGlyphMetrics::Builder::Width() {
  return InternalReadData()->ReadByte(Offset::kWidth);
}

void BigGlyphMetrics::Builder::SetWidth(byte_t width) {
  InternalWriteData()->WriteByte(Offset::kWidth, width);
}

int32_t BigGlyphMetrics::Builder::HoriBearingX() {
  return InternalReadData()->ReadByte(Offset::kHoriBearingX);
}

void BigGlyphMetrics::Builder::SetHoriBearingX(byte_t bearing) {
  InternalWriteData()->WriteByte(Offset::kHoriBearingX, bearing);
}

int32_t BigGlyphMetrics::Builder::HoriBearingY() {
  return InternalReadData()->ReadByte(Offset::kHoriBearingY);
}

void BigGlyphMetrics::Builder::SetHoriBearingY(byte_t bearing) {
  InternalWriteData()->WriteByte(Offset::kHoriBearingY, bearing);
}

int32_t BigGlyphMetrics::Builder::HoriAdvance() {
  return InternalReadData()->ReadByte(Offset::kHoriAdvance);
}

void BigGlyphMetrics::Builder::SetHoriAdvance(byte_t advance) {
  InternalWriteData()->WriteByte(Offset::kHoriAdvance, advance);
}

int32_t BigGlyphMetrics::Builder::VertBearingX() {
  return InternalReadData()->ReadByte(Offset::kVertBearingX);
}

void BigGlyphMetrics::Builder::SetVertBearingX(byte_t bearing) {
  InternalWriteData()->WriteByte(Offset::kVertBearingX, bearing);
}

int32_t BigGlyphMetrics::Builder::VertBearingY() {
  return InternalReadData()->ReadByte(Offset::kVertBearingY);
}

void BigGlyphMetrics::Builder::SetVertBearingY(byte_t bearing) {
  InternalWriteData()->WriteByte(Offset::kVertBearingY, bearing);
}

int32_t BigGlyphMetrics::Builder::VertAdvance() {
  return InternalReadData()->ReadByte(Offset::kVertAdvance);
}

void BigGlyphMetrics::Builder::SetVertAdvance(byte_t advance) {
  InternalWriteData()->WriteByte(Offset::kVertAdvance, advance);
}

CALLER_ATTACH FontDataTable*
    BigGlyphMetrics::Builder::SubBuildTable(ReadableFontData* data) {
  BigGlyphMetricsPtr output = new BigGlyphMetrics(data);
  return output.Detach();
}

void BigGlyphMetrics::Builder::SubDataSet() {
  // NOP.
}

int32_t BigGlyphMetrics::Builder::SubDataSizeToSerialize() {
  return 0;
}

bool BigGlyphMetrics::Builder::SubReadyToSerialize() {
  return false;
}

int32_t BigGlyphMetrics::Builder::SubSerialize(WritableFontData* new_data) {
  return Data()->CopyTo(new_data);
}

// static
CALLER_ATTACH
BigGlyphMetrics::Builder* BigGlyphMetrics::Builder::CreateBuilder() {
  WritableFontDataPtr data;
  data.Attach(WritableFontData::CreateWritableFontData(Offset::kMetricsLength));
  BigGlyphMetricsBuilderPtr output = new BigGlyphMetrics::Builder(data);
  return output.Detach();
}

}  // namespace sfntly
