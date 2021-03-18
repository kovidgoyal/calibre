/*
 * Frozen
 * Copyright 2016 QuarksLab
 *
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

#ifndef FROZEN_LETITGO_UNORDERED_SET_H
#define FROZEN_LETITGO_UNORDERED_SET_H

#include "frozen/bits/basic_types.h"
#include "frozen/bits/constexpr_assert.h"
#include "frozen/bits/elsa.h"
#include "frozen/bits/pmh.h"
#include "frozen/bits/version.h"
#include "frozen/random.h"

#include <utility>

namespace frozen {

namespace bits {

struct Get {
  template <class T> constexpr T const &operator()(T const &key) const {
    return key;
  }
};

} // namespace bits

template <class Key, std::size_t N, typename Hash = elsa<Key>,
          class KeyEqual = std::equal_to<Key>>
class unordered_set {
  static constexpr std::size_t storage_size =
      bits::next_highest_power_of_two(N) * (N < 32 ? 2 : 1); // size adjustment to prevent high collision rate for small sets
  using container_type = bits::carray<Key, N>;
  using tables_type = bits::pmh_tables<storage_size, Hash>;

  KeyEqual const equal_;
  container_type keys_;
  tables_type tables_;

public:
  /* typedefs */
  using key_type = Key;
  using value_type = Key;
  using size_type = typename container_type::size_type;
  using difference_type = typename container_type::difference_type;
  using hasher = Hash;
  using key_equal = KeyEqual;
  using const_reference = typename container_type::const_reference;
  using reference = const_reference;
  using const_pointer = typename container_type::const_pointer;
  using pointer = const_pointer;
  using const_iterator = const_pointer;
  using iterator = const_iterator;

public:
  /* constructors */
  unordered_set(unordered_set const &) = default;
  constexpr unordered_set(container_type keys, Hash const &hash,
                          KeyEqual const &equal)
      : equal_{equal}
      , keys_{keys}
      , tables_{bits::make_pmh_tables<storage_size>(
            keys_, hash, bits::Get{}, default_prg_t{})} {}
  explicit constexpr unordered_set(container_type keys)
      : unordered_set{keys, Hash{}, KeyEqual{}} {}

  constexpr unordered_set(std::initializer_list<Key> keys)
      : unordered_set{keys, Hash{}, KeyEqual{}} {}

  constexpr unordered_set(std::initializer_list<Key> keys, Hash const & hash, KeyEqual const & equal)
      : unordered_set{container_type{keys}, hash, equal} {
        constexpr_assert(keys.size() == N, "Inconsistent initializer_list size and type size argument");
      }

  /* iterators */
  constexpr const_iterator begin() const { return keys_.begin(); }
  constexpr const_iterator end() const { return keys_.end(); }
  constexpr const_iterator cbegin() const { return keys_.cbegin(); }
  constexpr const_iterator cend() const { return keys_.cend(); }

  /* capacity */
  constexpr bool empty() const { return !N; }
  constexpr size_type size() const { return N; }
  constexpr size_type max_size() const { return N; }

  /* lookup */
  constexpr std::size_t count(Key const &key) const {
    auto const k = lookup(key);
    return equal_(k, key);
  }
  constexpr const_iterator find(Key const &key) const {
    auto const &k = lookup(key);
    if (equal_(k, key))
      return &k;
    else
      return keys_.end();
  }

  constexpr std::pair<const_iterator, const_iterator> equal_range(Key const &key) const {
    auto const &k = lookup(key);
    if (equal_(k, key))
      return {&k, &k + 1};
    else
      return {keys_.end(), keys_.end()};
  }

  /* bucket interface */
  constexpr std::size_t bucket_count() const { return storage_size; }
  constexpr std::size_t max_bucket_count() const { return storage_size; }

  /* observers*/
  constexpr hasher hash_function() const { return tables_.hash_; }
  constexpr key_equal key_eq() const { return equal_; }

private:
  constexpr auto const &lookup(Key const &key) const {
    return keys_[tables_.lookup(key)];
  }
};

template <typename T, std::size_t N>
constexpr auto make_unordered_set(T const (&keys)[N]) {
  return unordered_set<T, N>{keys};
}

template <typename T, std::size_t N>
constexpr auto make_unordered_set(std::array<T, N> const &keys) {
  return unordered_set<T, N>{keys};
}

} // namespace frozen

#endif
