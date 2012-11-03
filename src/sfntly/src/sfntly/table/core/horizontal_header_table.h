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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_HEADER_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_HEADER_TABLE_H_

#include "sfntly/table/table.h"
#include "sfntly/table/table_based_table_builder.h"

namespace sfntly {

// A Horizontal Header table - 'hhea'.
class HorizontalHeaderTable : public Table,
                              public RefCounted<HorizontalHeaderTable> {
 public:
  // Builder for a Horizontal Header table - 'hhea'.
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

    int32_t TableVersion();
    void SetTableVersion(int32_t version);
    int32_t Ascender();
    void SetAscender(int32_t ascender);
    int32_t Descender();
    void SetDescender(int32_t descender);
    int32_t LineGap();
    void SetLineGap(int32_t line_gap);
    int32_t AdvanceWidthMax();
    void SetAdvanceWidthMax(int32_t value);
    int32_t MinLeftSideBearing();
    void SetMinLeftSideBearing(int32_t value);
    int32_t MinRightSideBearing();
    void SetMinRightSideBearing(int32_t value);
    int32_t XMaxExtent();
    void SetXMaxExtent(int32_t value);
    int32_t CaretSlopeRise();
    void SetCaretSlopeRise(int32_t value);
    int32_t CaretSlopeRun();
    void SetCaretSlopeRun(int32_t value);
    int32_t CaretOffset();
    void SetCaretOffset(int32_t value);
    int32_t MetricDataFormat();
    void SetMetricDataFormat(int32_t value);
    int32_t NumberOfHMetrics();
    void SetNumberOfHMetrics(int32_t value);
  };

  virtual ~HorizontalHeaderTable();
  int32_t TableVersion();
  int32_t Ascender();
  int32_t Descender();
  int32_t LineGap();
  int32_t AdvanceWidthMax();
  int32_t MinLeftSideBearing();
  int32_t MinRightSideBearing();
  int32_t XMaxExtent();
  int32_t CaretSlopeRise();
  int32_t CaretSlopeRun();
  int32_t CaretOffset();
  int32_t MetricDataFormat();
  int32_t NumberOfHMetrics();

 private:
  struct Offset {
    enum {
      kVersion = 0,
      kAscender = 4,
      kDescender = 6,
      kLineGap = 8,
      kAdvanceWidthMax = 10,
      kMinLeftSideBearing = 12,
      kMinRightSideBearing = 14,
      kXMaxExtent = 16,
      kCaretSlopeRise = 18,
      kCaretSlopeRun = 20,
      kCaretOffset = 22,
      kMetricDataFormat = 32,
      kNumberOfHMetrics = 34,
    };
  };

  HorizontalHeaderTable(Header* header, ReadableFontData* data);
};
typedef Ptr<HorizontalHeaderTable> HorizontalHeaderTablePtr;
typedef Ptr<HorizontalHeaderTable::Builder> HorizontalHeaderTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_CORE_HORIZONTAL_HEADER_TABLE_H_
