/*
 * impose.cpp
 * Copyright (C) 2019 Kovid Goyal <kovid at kovidgoyal.net>
 *
 * Distributed under terms of the GPL3 license.
 */

#include "global.h"
#include <functional>
#include <string>

using namespace pdf;

typedef std::unordered_map<PdfReference, size_t, PdfReferenceHasher> hash_cache_map;

class Image {
    charbuff buf;
    int64_t width, height;
    PdfReference ref;
    PdfReference smask;
    bool is_valid;
    size_t content_hash, overall_hash;

    Image( const Image & ) ;
    Image & operator=( const Image & ) ;

    public:
        Image(const PdfReference &reference, const PdfObject *o, hash_cache_map &hash_cache) : buf(), width(0), height(0), ref(reference) {
            const PdfObjectStream *stream = o->GetStream();
            try {
                buf = stream->GetCopySafe();
                is_valid = true;
            } catch(...) {
                buf = charbuff();
                is_valid = false;
            }
            const PdfDictionary &dict = o->GetDictionary();
            if (dict.HasKey("Width") && dict.GetKey("Width")->IsNumber()) width = dict.GetKey("Width")->GetNumber();
            if (dict.HasKey("Height") && dict.GetKey("Height")->IsNumber()) height = dict.GetKey("Height")->GetNumber();
            if (dict.HasKey("SMask") && dict.GetKey("SMask")->IsReference()) smask = dict.GetKey("SMask")->GetReference();
            std::hash<std::string> s;
            auto it = hash_cache.find(reference);
            if (it == hash_cache.end()) {
                content_hash = s(buf);
                hash_cache.insert(std::make_pair(reference, content_hash));
            } else {
                content_hash = it->second;
            }
            overall_hash = s(std::to_string(width) + " " + std::to_string(height) + " " + smask.ToString() + " " + std::to_string(content_hash));
        }
        Image(Image &&other) noexcept :
            buf(std::move(other.buf)), width(other.width), height(other.height), ref(other.ref), smask(other.smask), content_hash(other.content_hash), overall_hash(other.overall_hash) {
            other.buf = charbuff(); is_valid = other.is_valid;
        }
        Image& operator=(Image &&other) noexcept {
            buf = std::move(other.buf); other.buf = charbuff(); ref = other.ref;
            width = other.width; height = other.height; is_valid = other.is_valid;
            smask = other.smask; content_hash = other.content_hash; overall_hash = other.overall_hash;
            return *this;
        }
        bool operator==(const Image &other) const noexcept {
            return other.width == width && is_valid && other.is_valid && other.height == height && other.smask == smask && other.buf == buf;
        }
        std::size_t hash() const noexcept { return overall_hash; }
        const PdfReference& reference() const noexcept { return ref; }
        std::string ToString() const {
            return "Image(ref=" + ref.ToString() + ", width="s + std::to_string(width) + ", height="s + std::to_string(height) + ", smask="s + smask.ToString() + ", digest=" + std::to_string(content_hash) + ")";
        }
};

struct ImageHasher {
    std::size_t operator()(const Image& k) const { return k.hash(); }
};

typedef std::unordered_map<Image, std::vector<PdfReference>, ImageHasher> image_reference_map;

static unsigned long
run_one_dedup_pass(PDFDoc *self, hash_cache_map &hash_cache) {
    unsigned long count = 0;
    PdfIndirectObjectList &objects = self->doc->GetObjects();
    image_reference_map image_map;

    for (auto &k : objects) {
        if (!k->IsDictionary()) continue;
        const PdfDictionary &dict = k->GetDictionary();
        if (dictionary_has_key_name(dict, PdfName::KeyType, "XObject") && dictionary_has_key_name(dict, PdfName::KeySubtype, "Image")) {
            Image img(object_as_reference(k), k, hash_cache);
            auto it = image_map.find(img);
            if (it == image_map.end()) {
                std::vector<PdfReference> vals;
                image_map.insert(std::make_pair(std::move(img), std::move(vals)));
            } else (*it).second.push_back(img.reference());
        }
    }
    std::unordered_map<PdfReference, PdfReference, PdfReferenceHasher> ref_map;
    for (auto &x : image_map) {
        if (x.second.size() > 0) {
            const PdfReference &canonical_ref = x.first.reference();
            for (auto &ref : x.second) {
                if (ref != canonical_ref) {
                    ref_map[ref] = canonical_ref;
                    objects.RemoveObject(ref).reset();
                    count++;
                }
            }
        }
    }

    if (count > 0) {
        for (auto &k : objects) {
            if (!k->IsDictionary()) continue;
            PdfDictionary &dict = k->GetDictionary();
            if (dict.HasKey("Resources") && dict.GetKey("Resources")->IsDictionary()) {
                PdfDictionary &resources = dict.GetKey("Resources")->GetDictionary();
                if (!resources.HasKey("XObject") || !resources.GetKey("XObject")->IsDictionary()) continue;
                const PdfDictionary &xobject = resources.GetKey("XObject")->GetDictionary();
                PdfDictionary new_xobject = PdfDictionary(xobject);
                bool changed = false;
                for (const auto &x : xobject) {
                    if (x.second.IsReference()) {
                        try {
                            const PdfReference &r = ref_map.at(object_as_reference(x.second));
                            new_xobject.AddKey(x.first, r);
                            changed = true;
                        } catch (const std::out_of_range &err) { (void)err; continue; }
                    }
                }
                if (changed) resources.AddKey("XObject", new_xobject);
            } else if (dictionary_has_key_name(dict, PdfName::KeyType, "XObject") && dictionary_has_key_name(dict, PdfName::KeySubtype, "Image") && dict.HasKey("SMask") && dict.MustGetKey("SMask").IsReference()) {
                try {
                    const PdfReference &r = ref_map.at(dict.MustGetKey("SMask").GetReference());
                    dict.AddKey("SMask", r);
                } catch (const std::out_of_range &err) { (void)err; }
            }
        }
    }
    return count;
}

static PyObject*
dedup_images(PDFDoc *self, PyObject *args) {
    unsigned long count = 0;
    hash_cache_map hash_cache;
    count += run_one_dedup_pass(self, hash_cache);
    count += run_one_dedup_pass(self, hash_cache);
    return Py_BuildValue("k", count);

}

PYWRAP(dedup_images)
