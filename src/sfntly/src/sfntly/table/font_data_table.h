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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_FONT_DATA_TABLE_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_FONT_DATA_TABLE_H_

#include "sfntly/data/readable_font_data.h"
#include "sfntly/data/writable_font_data.h"
#include "sfntly/port/refcount.h"

namespace sfntly {

// An abstract base for any table that contains a FontData. This is the root of
// the table class hierarchy.
class FontDataTable : virtual public RefCount {
 public:
  // Note: original version is abstract Builder<T extends FontDataTable>
  //       C++ template is not designed that way so plain class is chosen.
  class Builder : virtual public RefCount {
   public:
    // Get a snapshot copy of the internal data of the builder.
    // This causes any internal data structures to be serialized to a new data
    // object. This data object belongs to the caller and must be properly
    // disposed of. No changes are made to the builder and any changes to the
    // data directly do not affect the internal state. To do that a subsequent
    // call must be made to {@link #SetData(WritableFontData)}.
    // @return a copy of the internal data of the builder
    CALLER_ATTACH WritableFontData* Data();
    virtual void SetData(ReadableFontData* data);

    // Note: changed from protected to avoid accessibility error in C++
    virtual CALLER_ATTACH FontDataTable* Build();
    virtual bool ReadyToBuild();

    ReadableFontData* InternalReadData();
    WritableFontData* InternalWriteData();

    bool data_changed() { return data_changed_; }
    bool model_changed() {
      return current_model_changed() || contained_model_changed();
    }
    bool current_model_changed() { return model_changed_; }
    bool contained_model_changed() { return contained_model_changed_; }

    bool set_model_changed() { return set_model_changed(true); }
    bool set_model_changed(bool changed) {
      bool old = model_changed_;
      model_changed_ = changed;
      return old;
    }

   protected:
    explicit Builder();

    // Construct a FontDataTable.Builder with a WritableFontData backing store
    // of size given. A positive size will create a fixed size backing store and
    // a 0 or less size is an estimate for a growable backing store with the
    // estimate being the absolute of the size.
    // @param dataSize if positive then a fixed size; if 0 or less then an
    //        estimate for a growable size
    Builder(int32_t data_size);
    Builder(WritableFontData* data);
    Builder(ReadableFontData* data);
    virtual ~Builder();

    // subclass API
    virtual void NotifyPostTableBuild(FontDataTable* table);
    virtual int32_t SubSerialize(WritableFontData* new_data) = 0;
    virtual bool SubReadyToSerialize() = 0;
    virtual int32_t SubDataSizeToSerialize() = 0;
    virtual void SubDataSet() = 0;
    virtual CALLER_ATTACH FontDataTable*
        SubBuildTable(ReadableFontData* data) = 0;

   private:
    void InternalSetData(WritableFontData* data, bool data_changed);
    void InternalSetData(ReadableFontData* data, bool data_changed);

    WritableFontDataPtr w_data_;
    ReadableFontDataPtr r_data_;
    bool model_changed_;
    bool contained_model_changed_;  // may expand to list of submodel states
    bool data_changed_;
  };

  explicit FontDataTable(ReadableFontData* data);
  virtual ~FontDataTable();

  // Get the readable font data for this table.
  ReadableFontData* ReadFontData();

  // Get the length of the data for this table in bytes. This is the full
  // allocated length of the data underlying the table and may or may not
  // include any padding.
  virtual int32_t DataLength();

  virtual int32_t Serialize(OutputStream* os);

 protected:
  virtual int32_t Serialize(WritableFontData* data);

  // TODO(arthurhsu): style guide violation: protected member, need refactoring
  ReadableFontDataPtr data_;
};
typedef Ptr<FontDataTable> FontDataTablePtr;
typedef Ptr<FontDataTable::Builder> FontDataTableBuilderPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_FONT_DATA_TABLE_H_
