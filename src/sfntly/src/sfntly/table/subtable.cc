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

#include "sfntly/table/subtable.h"

namespace sfntly {
/******************************************************************************
 * SubTable class
 ******************************************************************************/
SubTable::~SubTable() {}

SubTable::SubTable(ReadableFontData* data, ReadableFontData* master_data)
    : FontDataTable(data), padding_(0) {
  master_data_ = master_data;
}

SubTable::SubTable(ReadableFontData* data)
    : FontDataTable(data), padding_(0) {
}

/******************************************************************************
 * SubTable::Builder class
 ******************************************************************************/
SubTable::Builder::~Builder() {
}

SubTable::Builder::Builder(int32_t data_size)
    : FontDataTable::Builder(data_size) {
}

SubTable::Builder::Builder(WritableFontData* data,
                           ReadableFontData* master_data)
    : FontDataTable::Builder(data) {
  master_data_ = master_data;
}

SubTable::Builder::Builder(ReadableFontData* data,
                           ReadableFontData* master_data)
    : FontDataTable::Builder(data) {
  master_data_ = master_data;
}

SubTable::Builder::Builder(WritableFontData* data)
    : FontDataTable::Builder(data) {
}

SubTable::Builder::Builder(ReadableFontData* data)
    : FontDataTable::Builder(data) {
}

}  // namespace sfntly
