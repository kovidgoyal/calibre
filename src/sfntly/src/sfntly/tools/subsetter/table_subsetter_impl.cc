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

#include "sfntly/tools/subsetter/table_subsetter_impl.h"

namespace sfntly {

TableSubsetterImpl::TableSubsetterImpl(const int32_t* tags,
                                       size_t tags_length) {
  for (size_t i = 0; i < tags_length; ++i) {
    tags_.insert(tags[i]);
  }
}

TableSubsetterImpl::~TableSubsetterImpl() {}

bool TableSubsetterImpl::TagHandled(int32_t tag) {
  return tags_.find(tag) != tags_.end();
}

IntegerSet* TableSubsetterImpl::TagsHandled() {
  return &tags_;
}

}  // namespace sfntly
