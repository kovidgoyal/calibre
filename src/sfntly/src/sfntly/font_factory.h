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

#ifndef SFNTLY_CPP_SRC_SFNTLY_FONT_FACTORY_H_
#define SFNTLY_CPP_SRC_SFNTLY_FONT_FACTORY_H_

#include <vector>

#include "sfntly/port/refcount.h"
#include "sfntly/port/type.h"
#include "sfntly/font.h"

namespace sfntly {

class FontFactory : public RefCounted<FontFactory> {
 public:
  virtual ~FontFactory();

  // Factory method for the construction of a font factory.
  static CALLER_ATTACH FontFactory* GetInstance();

  // Toggle whether fonts that are loaded are fingerprinted with a SHA-1 hash.
  // If a font is fingerprinted then a SHA-1 hash is generated at load time and
  // stored in the font. This is useful for uniquely identifying fonts. By
  // default this is turned on.
  // @param fingerprint whether fingerprinting should be turned on or off
  // TODO(arthurhsu): IMPLEMENT: C++ port currently don't do any SHA-1
  void FingerprintFont(bool fingerprint);
  bool FingerprintFont();

  // Load the font(s) from the input stream. The current settings on the factory
  // are used during the loading process. One or more fonts are returned if the
  // stream contains valid font data. Some font container formats may have more
  // than one font and in this case multiple font objects will be returned. If
  // the data in the stream cannot be parsed or is invalid an array of size zero
  // will be returned.
  void LoadFonts(InputStream* is, FontArray* output);

  // ByteArray font loading
  // Load the font(s) from the byte array. The current settings on the factory
  // are used during the loading process. One or more fonts are returned if the
  // stream contains valid font data. Some font container formats may have more
  // than one font and in this case multiple font objects will be returned. If
  // the data in the stream cannot be parsed or is invalid an array of size zero
  // will be returned.
  void LoadFonts(ByteVector* b, FontArray* output);

  // Load the font(s) from the input stream into font builders. The current
  // settings on the factory are used during the loading process. One or more
  // font builders are returned if the stream contains valid font data. Some
  // font container formats may have more than one font and in this case
  // multiple font builder objects will be returned. If the data in the stream
  // cannot be parsed or is invalid an array of size zero will be returned.
  void LoadFontsForBuilding(InputStream* is, FontBuilderArray* output);

  // Load the font(s) from the byte array into font builders. The current
  // settings on the factory are used during the loading process. One or more
  // font builders are returned if the stream contains valid font data. Some
  // font container formats may have more than one font and in this case
  // multiple font builder objects will be returned. If the data in the stream
  // cannot be parsed or is invalid an array of size zero will be returned.
  void LoadFontsForBuilding(ByteVector* b, FontBuilderArray* output);

  // Font serialization
  // Serialize the font to the output stream.
  // NOTE: in this port we attempted not to implement I/O stream because dealing
  //       with cross-platform I/O stream itself is big enough as a project.
  //       Byte buffer it is.
  void SerializeFont(Font* font, OutputStream* os);

  // Set the table ordering to be used in serializing a font. The table ordering
  // is an ordered list of table ids and tables will be serialized in the order
  // given. Any tables whose id is not listed in the ordering will be placed in
  // an unspecified order following those listed.
  void SetSerializationTableOrdering(const IntegerList& table_ordering);

  // Get an empty font builder for creating a new font from scratch.
  CALLER_ATTACH Font::Builder* NewFontBuilder();

 private:
  // Offsets to specific elements in the underlying data. These offsets are
  // relative to the start of the table or the start of sub-blocks within the
  // table.
  struct Offset {
    enum {
      // Offsets within the main directory.
      kTTCTag = 0,
      kVersion = 4,
      kNumFonts = 8,
      kOffsetTable = 12,

      // TTC Version 2.0 extensions.
      // Offsets from end of OffsetTable.
      kulDsigTag = 0,
      kulDsigLength = 4,
      kulDsigOffset = 8
    };
  };

  FontFactory();

  CALLER_ATTACH Font* LoadSingleOTF(InputStream* is);
  CALLER_ATTACH Font* LoadSingleOTF(WritableFontData* wfd);

  void LoadCollection(InputStream* is, FontArray* output);
  void LoadCollection(WritableFontData* wfd, FontArray* output);

  CALLER_ATTACH Font::Builder* LoadSingleOTFForBuilding(InputStream* is);
  CALLER_ATTACH Font::Builder*
      LoadSingleOTFForBuilding(WritableFontData* wfd,
                               int32_t offset_to_offset_table);

  void LoadCollectionForBuilding(InputStream* is, FontBuilderArray* builders);
  void LoadCollectionForBuilding(WritableFontData* ba,
                                 FontBuilderArray* builders);

  static bool IsCollection(PushbackInputStream* pbis);
  static bool IsCollection(ReadableFontData* wfd);

  bool fingerprint_;
  IntegerList table_ordering_;
};
typedef Ptr<FontFactory> FontFactoryPtr;

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_FONT_FACTORY_H_
