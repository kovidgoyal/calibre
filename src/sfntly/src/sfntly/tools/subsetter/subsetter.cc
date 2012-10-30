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

#include "sfntly/tools/subsetter/subsetter.h"

#include <algorithm>
#include <iterator>

#include "sfntly/tools/subsetter/glyph_table_subsetter.h"

namespace sfntly {

Subsetter::Subsetter(Font* font, FontFactory* font_factory) {
  font_ = font;
  font_factory_ = font_factory;
  TableSubsetterPtr subsetter = new GlyphTableSubsetter();
  // TODO(arthurhsu): IMPLEMENT: CMap table subsetter
  table_subsetters_.push_back(subsetter);
}

Subsetter::~Subsetter() {
  font_factory_.Release();
  font_.Release();
  table_subsetters_.clear();
}

void Subsetter::SetGlyphs(IntegerList* glyphs) {
  new_to_old_glyphs_ = *glyphs;
}

void Subsetter::SetCMaps(CMapIdList* cmap_ids, int32_t number) {
  UNREFERENCED_PARAMETER(cmap_ids);
  UNREFERENCED_PARAMETER(number);
  // TODO(arthurhsu): IMPLEMENT
}

void Subsetter::SetRemoveTables(IntegerSet* remove_tables) {
  remove_tables_ = *remove_tables;
}

CALLER_ATTACH Font::Builder* Subsetter::Subset() {
  FontBuilderPtr font_builder;
  font_builder.Attach(font_factory_->NewFontBuilder());

  IntegerSet table_tags;
  for (TableMap::const_iterator i = font_->GetTableMap()->begin(),
                                e = font_->GetTableMap()->end(); i != e; ++i) {
    table_tags.insert(i->first);
  }
  if (!remove_tables_.empty()) {
    IntegerSet result;
    std::set_difference(table_tags.begin(), table_tags.end(),
                        remove_tables_.begin(), remove_tables_.end(),
                        std::inserter(result, result.end()));
    table_tags = result;
  }
  for (TableSubsetterList::iterator
           table_subsetter = table_subsetters_.begin(),
           table_subsetter_end = table_subsetters_.end();
           table_subsetter != table_subsetter_end; ++table_subsetter) {
    bool handled = (*table_subsetter)->Subset(this, font_, font_builder);
    if (handled) {
      IntegerSet* handled_tags = (*table_subsetter)->TagsHandled();
      IntegerSet result;
      std::set_difference(table_tags.begin(), table_tags.end(),
                          handled_tags->begin(), handled_tags->end(),
                          std::inserter(result, result.end()));
      table_tags = result;
    }
  }
  for (IntegerSet::iterator tag = table_tags.begin(),
                            tag_end = table_tags.end(); tag != tag_end; ++tag) {
    Table* table = font_->GetTable(*tag);
    if (table) {
      font_builder->NewTableBuilder(*tag, table->ReadFontData());
    }
  }
  return font_builder.Detach();
}

IntegerList* Subsetter::GlyphPermutationTable() {
  return &new_to_old_glyphs_;
}

CMapIdList* Subsetter::CMapId() {
  return &cmap_ids_;
}

}  // namespace sfntly
