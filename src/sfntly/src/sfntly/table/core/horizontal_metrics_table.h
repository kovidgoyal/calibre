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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_METRICS_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_METRICS_TABLE_H_

#include "sfntly/table/table.h"
#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

// A Horizontal Metrics table - 'hmtx'.
class HorizontalMetricsTable : public Table,
                               public RefCounted<HorizontalMetricsTable> {
 public:
  // Builder for a Horizontal Metrics Table - 'hmtx'.
  class Builder : public TableBasedTableBuilder, public RefCounted<Builder> {
   public:
    // Constructor scope altered to public because C++ does not allow base
    // class to instantiate derived class with protected constructors.
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);
    virtual ~Builder();

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

    void SetNumberOfHMetrics(int32_t num_hmetrics);
    void SetNumGlyphs(int32_t num_glyphs);

   private:
    int32_t num_hmetrics_;
    int32_t num_glyphs_;
  };

  virtual ~HorizontalMetricsTable();
  int32_t NumberOfHMetrics();
  int32_t NumberOfLSBs();
  int32_t HMetricAdvanceWidth(int32_t entry);
  int32_t HMetricLSB(int32_t entry);
  int32_t LsbTableEntry(int32_t entry);
  int32_t AdvanceWidth(int32_t glyph_id);
  int32_t LeftSideBearing(int32_t glyph_id);

 private:
  struct Offset {
    enum {
      // hMetrics
      kHMetricsStart = 0,
      kHMetricsSize = 4,

      // Offset within an hMetric
      kHMetricsAdvanceWidth = 0,
      kHMetricsLeftSideBearing = 2,

      kLeftSideBearingSize = 2
    };
  };

  HorizontalMetricsTable(Header* header,
                         ReadableFontData* data,
                         int32_t num_hmetrics,
                         int32_t num_glyphs);

  int32_t num_hmetrics_;
  int32_t num_glyphs_;
};
typedef Ptr<HorizontalMetricsTable> HorizontalMetricsTablePtr;
typedef Ptr<HorizontalMetricsTable::Builder> HorizontalMetricsTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_METRICS_TABLE_H_
