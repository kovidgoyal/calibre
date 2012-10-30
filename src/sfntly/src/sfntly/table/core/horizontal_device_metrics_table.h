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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_DEVICE_METRICS_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_DEVICE_METRICS_TABLE_H_

#include "sfntly/table/table.h"
#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

// A Horizontal Device Metrics table - 'hdmx'
class HorizontalDeviceMetricsTable
    : public Table,
      public RefCounted<HorizontalDeviceMetricsTable> {
 public:
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

    void SetNumGlyphs(int32_t num_glyphs);

   private:
    int32_t num_glyphs_;
  };

  virtual ~HorizontalDeviceMetricsTable();

  int32_t Version();
  int32_t NumRecords();
  int32_t RecordSize();
  int32_t PixelSize(int32_t record_index);
  int32_t MaxWidth(int32_t record_index);
  int32_t Width(int32_t record_index, int32_t glyph_num);

 private:
  struct Offset {
    enum {
      kVersion = 0,
      kNumRecords = 2,
      kSizeDeviceRecord = 4,
      kRecords = 8,

      // Offsets within a device record
      kDeviceRecordPixelSize = 0,
      kDeviceRecordMaxWidth = 1,
      kDeviceRecordWidths = 2,
    };
  };
  HorizontalDeviceMetricsTable(Header* header,
                               ReadableFontData* data,
                               int32_t num_glyphs);

  int32_t num_glyphs_;
};
typedef Ptr<HorizontalDeviceMetricsTable> HorizontalDeviceMetricsTablePtr;
typedef Ptr<HorizontalDeviceMetricsTable::Builder>
            HorizontalDeviceMetricsTableBuilderPtr;
}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_DEVICE_METRICS_TABLE_H_
