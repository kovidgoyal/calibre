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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BIG_GLYPH_METRICS_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BIG_GLYPH_METRICS_H_

#include "sfntly/table/bitmap/glyph_metrics.h"

namespace sfntly {

class BigGlyphMetrics : public GlyphMetrics,
                        public RefCounted<BigGlyphMetrics> {
 public:
  struct Offset {
    enum {
      kMetricsLength = 8,

      kHeight = 0,
      kWidth = 1,
      kHoriBearingX = 2,
      kHoriBearingY = 3,
      kHoriAdvance = 4,
      kVertBearingX = 5,
      kVertBearingY = 6,
      kVertAdvance = 7,
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
    int32_t HoriBearingX();
    void SetHoriBearingX(byte_t bearing);
    int32_t HoriBearingY();
    void SetHoriBearingY(byte_t bearing);
    int32_t HoriAdvance();
    void SetHoriAdvance(byte_t advance);
    int32_t VertBearingX();
    void SetVertBearingX(byte_t bearing);
    int32_t VertBearingY();
    void SetVertBearingY(byte_t bearing);
    int32_t VertAdvance();
    void SetVertAdvance(byte_t advance);

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);

    // Static instantiation function.
    static CALLER_ATTACH Builder* CreateBuilder();
  };

  explicit BigGlyphMetrics(ReadableFontData* data);
  virtual ~BigGlyphMetrics();

  int32_t Height();
  int32_t Width();
  int32_t HoriBearingX();
  int32_t HoriBearingY();
  int32_t HoriAdvance();
  int32_t VertBearingX();
  int32_t VertBearingY();
  int32_t VertAdvance();
};
typedef Ptr<BigGlyphMetrics> BigGlyphMetricsPtr;
typedef Ptr<BigGlyphMetrics::Builder> BigGlyphMetricsBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_BIG_GLYPH_METRICS_H_
