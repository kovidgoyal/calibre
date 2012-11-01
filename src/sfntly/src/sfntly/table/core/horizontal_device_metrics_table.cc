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

#include "sfntly/table/core/horizontal_device_metrics_table.h"

namespace sfntly {
/******************************************************************************
 * HorizontalDeviceMetricsTable class
 ******************************************************************************/
HorizontalDeviceMetricsTable:: ~HorizontalDeviceMetricsTable() {}

int32_t HorizontalDeviceMetricsTable::Version() {
  return data_->ReadUShort(Offset::kVersion);
}

int32_t HorizontalDeviceMetricsTable::NumRecords() {
  return data_->ReadShort(Offset::kNumRecords);
}

int32_t HorizontalDeviceMetricsTable::RecordSize() {
  return data_->ReadLong(Offset::kSizeDeviceRecord);
}

int32_t HorizontalDeviceMetricsTable::PixelSize(int32_t record_index) {
  if (record_index < 0 || record_index >= NumRecords()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException();
#endif
    return -1;
  }
  return data_->ReadUByte(Offset::kRecords + record_index * RecordSize() +
                          Offset::kDeviceRecordPixelSize);
}

int32_t HorizontalDeviceMetricsTable::MaxWidth(int32_t record_index) {
  if (record_index < 0 || record_index >= NumRecords()) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException();
#endif
    return -1;
  }
  return data_->ReadUByte(Offset::kRecords + record_index * RecordSize() +
                          Offset::kDeviceRecordMaxWidth);
}

int32_t HorizontalDeviceMetricsTable::Width(int32_t record_index,
                                            int32_t glyph_num) {
  if (record_index < 0 || record_index >= NumRecords() ||
      glyph_num < 0 || glyph_num >= num_glyphs_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundsException();
#endif
    return -1;
  }
  return data_->ReadUByte(Offset::kRecords + record_index * RecordSize() +
                          Offset::kDeviceRecordWidths + glyph_num);
}

HorizontalDeviceMetricsTable::HorizontalDeviceMetricsTable(
    Header* header,
    ReadableFontData* data,
    int32_t num_glyphs)
    : Table(header, data), num_glyphs_(num_glyphs) {
}

/******************************************************************************
 * HorizontalDeviceMetricsTable::Builder class
 ******************************************************************************/
HorizontalDeviceMetricsTable::Builder::Builder(Header* header,
                                               WritableFontData* data)
    : TableBasedTableBuilder(header, data), num_glyphs_(-1) {
}

HorizontalDeviceMetricsTable::Builder::Builder(Header* header,
                                               ReadableFontData* data)
    : TableBasedTableBuilder(header, data), num_glyphs_(-1) {
}

HorizontalDeviceMetricsTable::Builder::~Builder() {}

CALLER_ATTACH FontDataTable*
HorizontalDeviceMetricsTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table = new HorizontalDeviceMetricsTable(header(), data,
                                                            num_glyphs_);
  return table.Detach();
}

void HorizontalDeviceMetricsTable::Builder::SetNumGlyphs(int32_t num_glyphs) {
  if (num_glyphs < 0) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IllegalArgumentException("Number of glyphs can't be negative.");
#endif
    return;
  }
  num_glyphs_ = num_glyphs;
  HorizontalDeviceMetricsTable* table =
      down_cast<HorizontalDeviceMetricsTable*>(GetTable());
  if (table) {
    table->num_glyphs_ = num_glyphs;
  }
}

CALLER_ATTACH HorizontalDeviceMetricsTable::Builder*
HorizontalDeviceMetricsTable::Builder::CreateBuilder(Header* header,
                                                     WritableFontData* data) {
  Ptr<HorizontalDeviceMetricsTable::Builder> builder;
  builder = new HorizontalDeviceMetricsTable::Builder(header, data);
  return builder.Detach();
}

}  // namespace sfntly
