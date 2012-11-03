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

#include "sfntly/table/font_data_table.h"

#include "sfntly/data/font_output_stream.h"

namespace sfntly {

/******************************************************************************
 * FontDataTable class
 ******************************************************************************/

FontDataTable::FontDataTable(ReadableFontData* data) {
  data_ = data;
}

FontDataTable::~FontDataTable() {}

ReadableFontData* FontDataTable::ReadFontData() {
  return data_;
}

int32_t FontDataTable::DataLength() {
  return data_->Length();
}

int32_t FontDataTable::Serialize(OutputStream* os) {
  return data_->CopyTo(os);
}

int32_t FontDataTable::Serialize(WritableFontData* data) {
  return data_->CopyTo(data);
}

/******************************************************************************
 * FontDataTable::Builder class
 ******************************************************************************/
CALLER_ATTACH WritableFontData* FontDataTable::Builder::Data() {
  WritableFontDataPtr new_data;
  if (model_changed_) {
    if (!SubReadyToSerialize()) {
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IOException("Table not ready to build.");
#endif
      return NULL;
    }
    int32_t size = SubDataSizeToSerialize();
    new_data.Attach(WritableFontData::CreateWritableFontData(size));
    SubSerialize(new_data);
  } else {
    ReadableFontDataPtr data = InternalReadData();
    new_data.Attach(WritableFontData::CreateWritableFontData(
                        data != NULL ? data->Length() : 0));
    if (data != NULL) {
      data->CopyTo(new_data);
    }
  }
  return new_data.Detach();
}

void FontDataTable::Builder::SetData(ReadableFontData* data) {
  InternalSetData(data, true);
}


CALLER_ATTACH FontDataTable* FontDataTable::Builder::Build() {
  FontDataTablePtr table;  // NULL default table
  ReadableFontDataPtr data = InternalReadData();
  if (model_changed_) {
    // Let subclass serialize from model.
    if (!SubReadyToSerialize()) {
#if !defined (SFNTLY_NO_EXCEPTION)
      throw IOException("Table not ready to build.");
#endif
      return NULL;
    }
    int32_t size = SubDataSizeToSerialize();
    WritableFontDataPtr new_data;
    new_data.Attach(WritableFontData::CreateWritableFontData(size));
    SubSerialize(new_data);
    data = new_data;
  }

  if (data != NULL) {
    table = SubBuildTable(data);
    NotifyPostTableBuild(table);
  }

  r_data_.Release();
  w_data_.Release();
  return table;
}

bool FontDataTable::Builder::ReadyToBuild() {
  return true;
}

ReadableFontData* FontDataTable::Builder::InternalReadData() {
  return (r_data_ != NULL) ? r_data_.p_ :
                             static_cast<ReadableFontData*>(w_data_.p_);
}

WritableFontData* FontDataTable::Builder::InternalWriteData() {
  if (w_data_ == NULL) {
    WritableFontDataPtr new_data;
    new_data.Attach(WritableFontData::CreateWritableFontData(
                        r_data_ == NULL ? 0 : r_data_->Length()));
#if !defined (SFNTLY_NO_EXCEPTION)
    try {
#endif
      if (r_data_) {
        r_data_->CopyTo(new_data);
      }
#if !defined (SFNTLY_NO_EXCEPTION)
    } catch (IOException& e) {
      // TODO(stuartg): fix when IOExceptions are cleaned up
    }
#endif
    InternalSetData(new_data, false);
  }
  return w_data_.p_;
}

FontDataTable::Builder::Builder()
    : model_changed_(false),
      contained_model_changed_(false),
      data_changed_(false) {
}

FontDataTable::Builder::Builder(int32_t data_size)
    : model_changed_(false),
      contained_model_changed_(false),
      data_changed_(false) {
  w_data_.Attach(WritableFontData::CreateWritableFontData(data_size));
}

FontDataTable::Builder::Builder(WritableFontData* data)
    : model_changed_(false),
      contained_model_changed_(false),
      data_changed_(false) {
  w_data_ = data;
}

FontDataTable::Builder::Builder(ReadableFontData* data)
    : model_changed_(false),
      contained_model_changed_(false),
      data_changed_(false) {
  r_data_ = data;
}

FontDataTable::Builder::~Builder() {
}

void FontDataTable::Builder::NotifyPostTableBuild(FontDataTable* table) {
  // Default: NOP.
  UNREFERENCED_PARAMETER(table);
}

void FontDataTable::Builder::InternalSetData(WritableFontData* data,
                                             bool data_changed) {
  w_data_ = data;
  r_data_ = NULL;
  if (data_changed) {
    data_changed_ = true;
    SubDataSet();
  }
}

void FontDataTable::Builder::InternalSetData(ReadableFontData* data,
                                             bool data_changed) {
  w_data_ = NULL;
  r_data_ = data;
  if (data_changed) {
    data_changed_ = true;
    SubDataSet();
  }
}

}  // namespace sfntly
