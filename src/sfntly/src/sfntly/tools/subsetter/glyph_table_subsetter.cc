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

#include "sfntly/tools/subsetter/glyph_table_subsetter.h"

#include "sfntly/table/truetype/glyph_table.h"
#include "sfntly/table/truetype/loca_table.h"
#include "sfntly/tag.h"
#include "sfntly/tools/subsetter/subsetter.h"
#include "sfntly/port/exception_type.h"

namespace sfntly {

const int32_t kGlyphTableSubsetterTags[2] = {Tag::glyf, Tag::loca};

GlyphTableSubsetter::GlyphTableSubsetter()
    : TableSubsetterImpl(kGlyphTableSubsetterTags, 2) {
}

GlyphTableSubsetter::~GlyphTableSubsetter() {}

bool GlyphTableSubsetter::Subset(Subsetter* subsetter,
                                 Font* font,
                                 Font::Builder* font_builder) {
  assert(font);
  assert(subsetter);
  assert(font_builder);

  IntegerList* permutation_table = subsetter->GlyphPermutationTable();
  if (!permutation_table || permutation_table->empty())
    return false;

  GlyphTablePtr glyph_table = down_cast<GlyphTable*>(font->GetTable(Tag::glyf));
  LocaTablePtr loca_table = down_cast<LocaTable*>(font->GetTable(Tag::loca));
  if (glyph_table == NULL || loca_table == NULL) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw RuntimeException("Font to subset is not valid.");
#endif
    return false;
  }

  GlyphTableBuilderPtr glyph_table_builder =
      down_cast<GlyphTable::Builder*>
      (font_builder->NewTableBuilder(Tag::glyf));
  LocaTableBuilderPtr loca_table_builder =
      down_cast<LocaTable::Builder*>
      (font_builder->NewTableBuilder(Tag::loca));
  if (glyph_table_builder == NULL || loca_table_builder == NULL) {
#if !defined (SFNTLY_NO_EXCEPTION)
    throw RuntimeException("Builder for subset is not valid.");
#endif
    return false;
  }
  GlyphTable::GlyphBuilderList* glyph_builders =
      glyph_table_builder->GlyphBuilders();
  for (IntegerList::iterator old_glyph_id = permutation_table->begin(),
                             old_glyph_id_end = permutation_table->end();
                             old_glyph_id != old_glyph_id_end; ++old_glyph_id) {
    int old_offset = loca_table->GlyphOffset(*old_glyph_id);
    int old_length = loca_table->GlyphLength(*old_glyph_id);
    GlyphPtr glyph;
    glyph.Attach(glyph_table->GetGlyph(old_offset, old_length));
    ReadableFontDataPtr data = glyph->ReadFontData();
    WritableFontDataPtr copy_data;
    copy_data.Attach(WritableFontData::CreateWritableFontData(data->Length()));
    data->CopyTo(copy_data);
    GlyphBuilderPtr glyph_builder;
    glyph_builder.Attach(glyph_table_builder->GlyphBuilder(copy_data));
    glyph_builders->push_back(glyph_builder);
  }
  IntegerList loca_list;
  glyph_table_builder->GenerateLocaList(&loca_list);
  loca_table_builder->SetLocaList(&loca_list);
  return true;
}

}  // namespace sfntly
