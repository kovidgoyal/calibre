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

#include "sfntly/table/core/horizontal_metrics_table.h"
#include "sfntly/port/exception_type.h"

namespace sfntly {
/******************************************************************************
 * HorizontalMetricsTable class
 ******************************************************************************/
HorizontalMetricsTable::~HorizontalMetricsTable() {}

int32_t HorizontalMetricsTable::NumberOfHMetrics() {
  return num_hmetrics_;
}

int32_t HorizontalMetricsTable::NumberOfLSBs() {
  return num_glyphs_ - num_hmetrics_;
}

int32_t HorizontalMetricsTable::HMetricAdvanceWidth(int32_t entry) {
  if (entry > num_hmetrics_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#endif
    return 0;
  }
  int32_t offset = Offset::kHMetricsStart + (entry * Offset::kHMetricsSize) +
                   Offset::kHMetricsAdvanceWidth;
  return data_->ReadUShort(offset);
}

int32_t HorizontalMetricsTable::HMetricLSB(int32_t entry) {
  if (entry > num_hmetrics_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#endif
    return 0;
  }
  int32_t offset = Offset::kHMetricsStart + (entry * Offset::kHMetricsSize) +
                   Offset::kHMetricsLeftSideBearing;
  return data_->ReadShort(offset);
}

int32_t HorizontalMetricsTable::LsbTableEntry(int32_t entry) {
  if (entry > num_hmetrics_) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw IndexOutOfBoundException();
#endif
    return 0;
  }
  int32_t offset = Offset::kHMetricsStart + (entry * Offset::kHMetricsSize) +
                   Offset::kLeftSideBearingSize;
  return data_->ReadShort(offset);
}

int32_t HorizontalMetricsTable::AdvanceWidth(int32_t glyph_id) {
  if (glyph_id < num_hmetrics_) {
    return HMetricAdvanceWidth(glyph_id);
  }
  return HMetricAdvanceWidth(glyph_id - num_hmetrics_);
}

int32_t HorizontalMetricsTable::LeftSideBearing(int32_t glyph_id) {
  if (glyph_id < num_hmetrics_) {
    return HMetricLSB(glyph_id);
  }
  return LsbTableEntry(glyph_id - num_hmetrics_);
}

HorizontalMetricsTable::HorizontalMetricsTable(Header* header,
                                               ReadableFontData* data,
                                               int32_t num_hmetrics,
                                               int32_t num_glyphs)
    : Table(header, data),
      num_hmetrics_(num_hmetrics),
      num_glyphs_(num_glyphs) {
}

/******************************************************************************
 * HorizontalMetricsTable::Builder class
 ******************************************************************************/
HorizontalMetricsTable::Builder::Builder(Header* header, WritableFontData* data)
    : TableBasedTableBuilder(header, data), num_hmetrics_(-1), num_glyphs_(-1) {
}

HorizontalMetricsTable::Builder::Builder(Header* header, ReadableFontData* data)
    : TableBasedTableBuilder(header, data), num_hmetrics_(-1), num_glyphs_(-1) {
}

HorizontalMetricsTable::Builder::~Builder() {}

CALLER_ATTACH FontDataTable*
    HorizontalMetricsTable::Builder::SubBuildTable(ReadableFontData* data) {
  FontDataTablePtr table =
      new HorizontalMetricsTable(header(), data, num_hmetrics_, num_glyphs_);
  return table.Detach();
}

CALLER_ATTACH HorizontalMetricsTable::Builder*
    HorizontalMetricsTable::Builder::CreateBuilder(Header* header,
                                                   WritableFontData* data) {
  Ptr<HorizontalMetricsTable::Builder> builder;
  builder = new HorizontalMetricsTable::Builder(header, data);
  return builder.Detach();
}

void HorizontalMetricsTable::Builder::SetNumberOfHMetrics(
    int32_t num_hmetrics) {
  assert(num_hmetrics >= 0);
  num_hmetrics_ = num_hmetrics;
  HorizontalMetricsTable* table =
      down_cast<HorizontalMetricsTable*>(this->GetTable());
  table->num_hmetrics_ = num_hmetrics;
}

void HorizontalMetricsTable::Builder::SetNumGlyphs(int32_t num_glyphs) {
  assert(num_glyphs >= 0);
  num_glyphs_ = num_glyphs;
  HorizontalMetricsTable* table =
      down_cast<HorizontalMetricsTable*>(this->GetTable());
  table->num_glyphs_ = num_glyphs;
}

}  // namespace sfntly
