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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TABLE_TABLE_BASED_TABLE_BUILDER_H_
#define SFNTLY_CPP_SRC_SFNTLY_TABLE_TABLE_BASED_TABLE_BUILDER_H_

#include "sfntly/table/table.h"

namespace sfntly {

class TableBasedTableBuilder : public Table::Builder {
 public:
  virtual ~TableBasedTableBuilder();

  virtual int32_t SubSerialize(WritableFontData* new_data);
  virtual bool SubReadyToSerialize();
  virtual int32_t SubDataSizeToSerialize();
  virtual void SubDataSet();
  virtual CALLER_ATTACH FontDataTable* Build();

 protected:
  TableBasedTableBuilder(Header* header, WritableFontData* data);
  TableBasedTableBuilder(Header* header, ReadableFontData* data);
  explicit TableBasedTableBuilder(Header* header);

  // C++ port: renamed table() to GetTable()
  virtual Table* GetTable();

  // TODO(arthurhsu): style guide violation: protected member, need refactor
  TablePtr table_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TABLE_TABLE_BASED_TABLE_BUILDER_H_
