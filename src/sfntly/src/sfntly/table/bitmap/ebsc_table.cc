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

#include "sfntly/table/bitmap/ebsc_table.h"

namespace sfntly {
/******************************************************************************
 * EbscTable class
 ******************************************************************************/
EbscTable::~EbscTable() {
}

int32_t EbscTable::Version() {
  return data_->ReadFixed(Offset::kVersion);
}

int32_t EbscTable::NumSizes() {
  return data_->ReadULongAsInt(Offset::kNumSizes);
}

EbscTable::EbscTable(Header* header, ReadableFontData* data)
    : Table(header, data) {
}

/******************************************************************************
 * EbscTable::BitmapScaleTable class
 ******************************************************************************/
EbscTable::BitmapScaleTable::~BitmapScaleTable() {
}

EbscTable::BitmapScaleTable::BitmapScaleTable(ReadableFontData* data)
    : SubTable(data) {
}

int32_t EbscTable::BitmapScaleTable::PpemX() {
  return data_->ReadByte(Offset::kBitmapScaleTable_ppemX);
}

int32_t EbscTable::BitmapScaleTable::PpemY() {
  return data_->ReadByte(Offset::kBitmapScaleTable_ppemY);
}

int32_t EbscTable::BitmapScaleTable::SubstitutePpemX() {
  return data_->ReadByte(Offset::kBitmapScaleTable_substitutePpemX);
}

int32_t EbscTable::BitmapScaleTable::SubstitutePpemY() {
  return data_->ReadByte(Offset::kBitmapScaleTable_substitutePpemY);
}

/******************************************************************************
 * EbscTable::Builder class
 ******************************************************************************/
EbscTable::Builder::~Builder() {
}

CALLER_ATTACH EbscTable::Builder* EbscTable::Builder::CreateBuilder(
    Header* header, WritableFontData* data) {
  EbscTableBuilderPtr builder = new EbscTable::Builder(header, data);
  return builder.Detach();
}

EbscTable::Builder::Builder(Header* header, WritableFontData* data)
    : Table::Builder(header, data) {
}

EbscTable::Builder::Builder(Header* header, ReadableFontData* data)
    : Table::Builder(header, data) {
}

CALLER_ATTACH
FontDataTable* EbscTable::Builder::SubBuildTable(ReadableFontData* data) {
  EbscTablePtr output = new EbscTable(header(), data);
  return output.Detach();
}

void EbscTable::Builder::SubDataSet() {
  // NOP
}

int32_t EbscTable::Builder::SubDataSizeToSerialize() {
  return 0;
}

bool EbscTable::Builder::SubReadyToSerialize() {
  return false;
}

int32_t EbscTable::Builder::SubSerialize(WritableFontData* new_data) {
  UNREFERENCED_PARAMETER(new_data);
  return 0;
}

}  // namespace sfntly
