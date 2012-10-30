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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBSC_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBSC_TABLE_H_

#include "sfntly/table/bitmap/eblc_table.h"

namespace sfntly {

class EbscTable : public Table,
                  public RefCounted<EbscTable> {
 public:
  struct Offset {
    enum {
      // header
      kVersion = 0,
      kNumSizes = DataSize::kFixed,
      kHeaderLength = kNumSizes + DataSize::kULONG,
      kBitmapScaleTableStart = kHeaderLength,

      // bitmapScaleTable
      kBitmapScaleTable_hori = 0,
      kBitmapScaleTable_vert = EblcTable::Offset::kSbitLineMetricsLength,
      kBitmapScaleTable_ppemX = kBitmapScaleTable_vert +
                                EblcTable::Offset::kSbitLineMetricsLength,
      kBitmapScaleTable_ppemY = kBitmapScaleTable_ppemX + DataSize::kBYTE,
      kBitmapScaleTable_substitutePpemX = kBitmapScaleTable_ppemY +
                                          DataSize::kBYTE,
      kBitmapScaleTable_substitutePpemY = kBitmapScaleTable_substitutePpemX +
                                          DataSize::kBYTE,
      kBitmapScaleTableLength = kBitmapScaleTable_substitutePpemY +
                                DataSize::kBYTE,
    };
  };

  class BitmapScaleTable : public SubTable,
                           public RefCounted<BitmapScaleTable> {
   public:
    virtual ~BitmapScaleTable();
    int32_t PpemX();
    int32_t PpemY();
    int32_t SubstitutePpemX();
    int32_t SubstitutePpemY();

   protected:
    // Note: caller to do data->Slice(offset, Offset::kBitmapScaleTableLength)
    explicit BitmapScaleTable(ReadableFontData* data);
  };

  // TODO(stuartg): currently the builder just builds from initial data
  // - need to make fully working but few if any examples to test with
  class Builder : public Table::Builder,
                  public RefCounted<Builder> {
   public:
    virtual ~Builder();

    static CALLER_ATTACH Builder* CreateBuilder(Header* header,
                                                WritableFontData* data);

   protected:
    Builder(Header* header, WritableFontData* data);
    Builder(Header* header, ReadableFontData* data);

    virtual CALLER_ATTACH FontDataTable* SubBuildTable(ReadableFontData* data);
    virtual void SubDataSet();
    virtual int32_t SubDataSizeToSerialize();
    virtual bool SubReadyToSerialize();
    virtual int32_t SubSerialize(WritableFontData* new_data);
  };

  virtual ~EbscTable();

  int32_t Version();
  int32_t NumSizes();
  // Note: renamed from bitmapScaleTable
  CALLER_ATTACH BitmapScaleTable* GetBitmapScaleTable(int32_t index);

 private:
  EbscTable(Header* header, ReadableFontData* data);
  friend class Builder;
};
typedef Ptr<EbscTable> EbscTablePtr;
typedef Ptr<EbscTable::Builder> EbscTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_BITMAP_EBSC_TABLE_H_
