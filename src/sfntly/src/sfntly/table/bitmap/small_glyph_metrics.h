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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_SMALL_GLYPH_METRICS_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_SMALL_GLYPH_METRICS_H_

#include "sfntly/port/refcount.h"
#include "sfntly/table/bitmap/glyph_metrics.h"

namespace sfntly {

class SmallGlyphMetrics : public GlyphMetrics,
                          public RefCounted<SmallGlyphMetrics> {
 public:
  struct Offset {
    enum {
      kMetricsLength = 5,
      kHeight = 0,
      kWidth = 1,
      kBearingX = 2,
      kBearingY = 3,
      kAdvance = 4,
    };
  };

  class Builder : public GlyphMetrics::Builder,
                  public RefCounted<Builder> {
   public:
    // Constructor scope altered to public because C++ does not allow base
    // class to instantiate derived class with protected constructors.
    explicit Builder(WritableFontData* data);
    explicit Builder(ReadableFontData* data);
    virtual ~Builder();

    int32_t Height();
    void SetHeight(byte_t height);
    int32_t Width();
    void SetWidth(byte_t width);
    int32_t BearingX();
    void SetBearingX(byte_t bearing);
    int32_t BearingY();
    void SetBearingY(byte_t bearing);
    int32_t Advance();
    void SetAdvance(byte_t advance);

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);
  };

  explicit SmallGlyphMetrics(ReadableFontData* data);
  virtual ~SmallGlyphMetrics();

  int32_t Height();
  int32_t Width();
  int32_t BearingX();
  int32_t BearingY();
  int32_t Advance();
};
typedef Ptr<SmallGlyphMetrics> SmallGlyphMetricsPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_SMALL_GLYPH_METRICS_H_
