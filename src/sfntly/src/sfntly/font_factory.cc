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

#include "sfntly/font_factory.h"

#include <string.h>

#include "sfntly/tag.h"

namespace sfntly {

FontFactory::~FontFactory() {
}

CALLER_ATTACH FontFactory* FontFactory::GetInstance() {
  FontFactoryPtr instance = new FontFactory();
  return instance.Detach();
}

void FontFactory::FingerprintFont(bool fingerprint) {
  fingerprint_ = fingerprint;
}

bool FontFactory::FingerprintFont() {
  return fingerprint_;
}

void FontFactory::LoadFonts(InputStream* is, FontArray* output) {
  assert(output);
  PushbackInputStream* pbis = down_cast<PushbackInputStream*>(is);
  if (IsCollection(pbis)) {
    LoadCollection(pbis, output);
    return;
  }
  FontPtr font;
  font.Attach(LoadSingleOTF(pbis));
  if (font) {
    output->push_back(font);
  }
}

void FontFactory::LoadFonts(ByteVector* b, FontArray* output) {
  WritableFontDataPtr wfd;
  wfd.Attach(WritableFontData::CreateWritableFontData(b));
  if (IsCollection(wfd)) {
    LoadCollection(wfd, output);
    return;
  }
  FontPtr font;
  font.Attach(LoadSingleOTF(wfd));
  if (font) {
    output->push_back(font);
  }
}

void FontFactory::LoadFontsForBuilding(InputStream* is,
                                       FontBuilderArray* output) {
  PushbackInputStream* pbis = down_cast<PushbackInputStream*>(is);
  if (IsCollection(pbis)) {
    LoadCollectionForBuilding(pbis, output);
    return;
  }
  FontBuilderPtr builder;
  builder.Attach(LoadSingleOTFForBuilding(pbis));
  if (builder) {
    output->push_back(builder);
  }
}

void FontFactory::LoadFontsForBuilding(ByteVector* b,
                                       FontBuilderArray* output) {
  WritableFontDataPtr wfd;
  wfd.Attach(WritableFontData::CreateWritableFontData(b));
  if (IsCollection(wfd)) {
    LoadCollectionForBuilding(wfd, output);
    return;
  }
  FontBuilderPtr builder;
  builder.Attach(LoadSingleOTFForBuilding(wfd, 0));
  if (builder) {
    output->push_back(builder);
  }
}

void FontFactory::SerializeFont(Font* font, OutputStream* os) {
  font->Serialize(os, &table_ordering_);
}

void FontFactory::SetSerializationTableOrdering(
    const IntegerList& table_ordering) {
  table_ordering_ = table_ordering;
}

CALLER_ATTACH Font::Builder* FontFactory::NewFontBuilder() {
  return Font::Builder::GetOTFBuilder(this);
}

CALLER_ATTACH Font* FontFactory::LoadSingleOTF(InputStream* is) {
  FontBuilderPtr builder;
  builder.Attach(LoadSingleOTFForBuilding(is));
  return builder->Build();
}

CALLER_ATTACH Font* FontFactory::LoadSingleOTF(WritableFontData* wfd) {
  FontBuilderPtr builder;
  builder.Attach(LoadSingleOTFForBuilding(wfd, 0));
  return builder->Build();
}

void FontFactory::LoadCollection(InputStream* is, FontArray* output) {
  FontBuilderArray ba;
  LoadCollectionForBuilding(is, &ba);
  output->reserve(ba.size());
  for (FontBuilderArray::iterator builder = ba.begin(), builders_end = ba.end();
                                  builder != builders_end; ++builder) {
      FontPtr font;
      font.Attach((*builder)->Build());
      output->push_back(font);
  }
}

void FontFactory::LoadCollection(WritableFontData* wfd, FontArray* output) {
  FontBuilderArray builders;
  LoadCollectionForBuilding(wfd, &builders);
  output->reserve(builders.size());
  for (FontBuilderArray::iterator builder = builders.begin(),
                                  builders_end = builders.end();
                                  builder != builders_end; ++builder) {
    FontPtr font;
    font.Attach((*builder)->Build());
    output->push_back(font);
  }
}

CALLER_ATTACH
Font::Builder* FontFactory::LoadSingleOTFForBuilding(InputStream* is) {
  // UNIMPLEMENTED: SHA-1 hash checking via Java DigestStream
  Font::Builder* builder = Font::Builder::GetOTFBuilder(this, is);
  // UNIMPLEMENTED: setDigest
  return builder;
}

CALLER_ATTACH Font::Builder*
    FontFactory::LoadSingleOTFForBuilding(WritableFontData* wfd,
                                          int32_t offset_to_offset_table) {
  // UNIMPLEMENTED: SHA-1 hash checking via Java DigestStream
  Font::Builder* builder =
      Font::Builder::GetOTFBuilder(this, wfd, offset_to_offset_table);
  // UNIMPLEMENTED: setDigest
  return builder;
}

void FontFactory::LoadCollectionForBuilding(InputStream* is,
                                            FontBuilderArray* builders) {
  assert(is);
  assert(builders);
  WritableFontDataPtr wfd;
  wfd.Attach(WritableFontData::CreateWritableFontData(is->Available()));
  wfd->CopyFrom(is);
  LoadCollectionForBuilding(wfd, builders);
}

void FontFactory::LoadCollectionForBuilding(WritableFontData* wfd,
                                            FontBuilderArray* builders) {
  int32_t ttc_tag = wfd->ReadULongAsInt(Offset::kTTCTag);
  UNREFERENCED_PARAMETER(ttc_tag);
  int32_t version = wfd->ReadFixed(Offset::kVersion);
  UNREFERENCED_PARAMETER(version);
  int32_t num_fonts = wfd->ReadULongAsInt(Offset::kNumFonts);

  builders->reserve(num_fonts);
  int32_t offset_table_offset = Offset::kOffsetTable;
  for (int32_t font_number = 0;
               font_number < num_fonts;
               font_number++, offset_table_offset += DataSize::kULONG) {
    int32_t offset = wfd->ReadULongAsInt(offset_table_offset);
    FontBuilderPtr builder;
    builder.Attach(LoadSingleOTFForBuilding(wfd, offset));
    builders->push_back(builder);
  }
}

bool FontFactory::IsCollection(PushbackInputStream* pbis) {
  ByteVector tag(4);
  pbis->Read(&tag);
  pbis->Unread(&tag);
  return Tag::ttcf == GenerateTag(tag[0], tag[1], tag[2], tag[3]);
}

bool FontFactory::IsCollection(ReadableFontData* rfd) {
  ByteVector tag(4);
  rfd->ReadBytes(0, &(tag[0]), 0, tag.size());
  return Tag::ttcf ==
         GenerateTag(tag[0], tag[1], tag[2], tag[3]);
}

FontFactory::FontFactory()
    : fingerprint_(false) {
}

}  // namespace sfntly
