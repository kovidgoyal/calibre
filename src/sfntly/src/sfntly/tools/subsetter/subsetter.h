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

#ifndef SFNTLY_CPP_SRC_SFNTLY_TOOLS_SUBSETTER_SUBSETTER_H_
#define SFNTLY_CPP_SRC_SFNTLY_TOOLS_SUBSETTER_SUBSETTER_H_

#include <vector>

#include "sfntly/font.h"
#include "sfntly/font_factory.h"
#include "sfntly/table/core/cmap_table.h"
#include "sfntly/tools/subsetter/table_subsetter.h"

namespace sfntly {

class Subsetter : public RefCounted<Subsetter> {
 public:
  Subsetter(Font* font, FontFactory* font_factory);
  virtual ~Subsetter();

  virtual void SetGlyphs(IntegerList* glyphs);

  // Set the cmaps to be used in the subsetted font. The cmaps are listed in
  // order of priority and the number parameter gives a count of how many of the
  // list should be put into the subsetted font. If there are no matches in the
  // font for any of the provided cmap ids which would lead to a font with no
  // cmap then an error will be thrown during subsetting.
  // The two most common cases would be: <list>
  // * a list of one or more cmap ids with a count setting of 1
  //     This will use the list of cmap ids as an ordered priority and look for
  //     an available cmap in the font that matches the requests. Only the first
  //     such match will be placed in the subsetted font.
  // * a list of one or more cmap ids with a count setting equal to the list
  //   length
  //     This will use the list of cmap ids and try to place each one specified
  //     into the subsetted font.
  // @param cmapIds the cmap ids to use for the subsetted font
  // @param number the maximum number of cmaps to place in the subsetted font
  virtual void SetCMaps(CMapIdList* cmap_ids, int32_t number);

  virtual void SetRemoveTables(IntegerSet* remove_tables);
  virtual CALLER_ATTACH Font::Builder* Subset();
  virtual IntegerList* GlyphPermutationTable();
  virtual CMapIdList* CMapId();

 private:
  FontPtr font_;
  FontFactoryPtr font_factory_;
  TableSubsetterList table_subsetters_;

  // Settings from user
  IntegerSet remove_tables_;
  IntegerList new_to_old_glyphs_;
  CMapIdList cmap_ids_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_TOOLS_SUBSETTER_SUBSETTER_H_
