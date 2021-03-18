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

#ifndef FROZEN_LETITGO_MAP_H
#define FROZEN_LETITGO_MAP_H

#include "frozen/bits/algorithms.h"
#include "frozen/bits/basic_types.h"
#include "frozen/bits/constexpr_assert.h"
#include "frozen/bits/exceptions.h"
#include "frozen/bits/version.h"

#include <utility>

namespace frozen {

namespace impl {

template <class Comparator> class CompareKey {

  Comparator const comparator_;

public:
  constexpr CompareKey(Comparator const &comparator)
      : comparator_(comparator) {}

  template <class Key, class Value>
  constexpr int operator()(std::pair<Key, Value> const &self,
                           std::pair<Key, Value> const &other) const {
    return comparator_(std::get<0>(self), std::get<0>(other));
  }

  template <class Key, class Value>
  constexpr int operator()(Key const &self_key,
                           std::pair<Key, Value> const &other) const {
    return comparator_(self_key, std::get<0>(other));
  }

  template <class Key, class Value>
  constexpr int operator()(std::pair<Key, Value> const &self,
                           Key const &other_key) const {
    return comparator_(std::get<0>(self), other_key);
  }

  template <class Key>
  constexpr int operator()(Key const &self_key, Key const &other_key) const {
    return comparator_(self_key, other_key);
  }
};

} // namespace impl

template <class Key, class Value, std::size_t N, class Compare = std::less<Key>>
class map {
  using container_type = bits::carray<std::pair<Key, Value>, N>;
  impl::CompareKey<Compare> less_than_;
  container_type items_;

public:
  using key_type = Key;
  using mapped_type = Value;
  using value_type = typename container_type::value_type;
  using size_type = typename container_type::size_type;
  using difference_type = typename container_type::difference_type;
  using key_compare = decltype(less_than_);
  using reference = typename container_type::reference;
  using const_reference = typename container_type::const_reference;
  using pointer = typename container_type::pointer;
  using const_pointer = typename container_type::const_pointer;
  using iterator = typename container_type::iterator;
  using const_iterator = typename container_type::const_iterator;
  using reverse_iterator = typename container_type::reverse_iterator;
  using const_reverse_iterator =
      typename container_type::const_reverse_iterator;

public:
  /* constructors */
  constexpr map(container_type items, Compare const &compare)
      : less_than_{compare}
      , items_{bits::quicksort(items, less_than_)} {}

  explicit constexpr map(container_type items)
      : map{items, Compare{}} {}

  constexpr map(std::initializer_list<value_type> items, Compare const &compare)
      : map{container_type {items}, compare} {
        constexpr_assert(items.size() == N, "Inconsistent initializer_list size and type size argument");
      }

  constexpr map(std::initializer_list<value_type> items)
      : map{items, Compare{}} {}

  /* element access */
  constexpr Value const& at(Key const &key) const {
    return at_impl(*this, key);
  }
  constexpr Value& at(Key const &key) {
    return at_impl(*this, key);
  }

  /* iterators */
  constexpr iterator begin() { return items_.begin(); }
  constexpr const_iterator begin() const { return items_.begin(); }
  constexpr const_iterator cbegin() const { return items_.cbegin(); }
  constexpr iterator end() { return items_.end(); }
  constexpr const_iterator end() const { return items_.end(); }
  constexpr const_iterator cend() const { return items_.cend(); }

  constexpr reverse_iterator rbegin() { return items_.rbegin(); }
  constexpr const_reverse_iterator rbegin() const { return items_.rbegin(); }
  constexpr const_reverse_iterator crbegin() const { return items_.crbegin(); }
  constexpr reverse_iterator rend() { return items_.rend(); }
  constexpr const_reverse_iterator rend() const { return items_.rend(); }
  constexpr const_reverse_iterator crend() const { return items_.crend(); }

  /* capacity */
  constexpr bool empty() const { return !N; }
  constexpr size_type size() const { return N; }
  constexpr size_type max_size() const { return N; }

  /* lookup */

  constexpr std::size_t count(Key const &key) const {
    return bits::binary_search<N>(items_.begin(), key, less_than_);
  }

  constexpr const_iterator find(Key const &key) const {
    return find_impl(*this, key);
  }
  constexpr iterator find(Key const &key) {
    return find_impl(*this, key);
  }

  constexpr std::pair<const_iterator, const_iterator>
  equal_range(Key const &key) const {
    return equal_range_impl(*this, key);
  }
  constexpr std::pair<iterator, iterator> equal_range(Key const &key) {
    return equal_range_impl(*this, key);
  }

  constexpr const_iterator lower_bound(Key const &key) const {
    return lower_bound_impl(*this, key);
  }
  constexpr iterator lower_bound(Key const &key) {
    return lower_bound_impl(*this, key);
  }

  constexpr const_iterator upper_bound(Key const &key) const {
    return upper_bound_impl(*this, key);
  }
  constexpr iterator upper_bound(Key const &key) {
    return upper_bound_impl(*this, key);
  }

  /* observers */
  constexpr key_compare key_comp() const { return less_than_; }
  constexpr key_compare value_comp() const { return less_than_; }

 private:
  template <class This>
  static inline constexpr auto& at_impl(This&& self, Key const &key) {
    auto where = self.lower_bound(key);
    if (where != self.end())
      return where->second;
    else
      FROZEN_THROW_OR_ABORT(std::out_of_range("unknown key"));
  }

  template <class This>
  static inline constexpr auto find_impl(This&& self, Key const &key) {
    auto where = self.lower_bound(key);
    if ((where != self.end()) && !self.less_than_(key, *where))
      return where;
    else
      return self.end();
  }

  template <class This>
  static inline constexpr auto equal_range_impl(This&& self, Key const &key) {
    auto lower = self.lower_bound(key);
    using lower_t = decltype(lower);
    if (lower == self.end())
      return std::pair<lower_t, lower_t>{lower, lower};
    else
      return std::pair<lower_t, lower_t>{lower, lower + 1};
  }

  template <class This>
  static inline constexpr auto lower_bound_impl(This&& self, Key const &key) -> decltype(self.end()) {
    auto where = bits::lower_bound<N>(self.items_.begin(), key, self.less_than_);
    if ((where != self.end()) && !self.less_than_(key, *where))
      return where;
    else
      return self.end();
  }

  template <class This>
  static inline constexpr auto upper_bound_impl(This&& self, Key const &key) -> decltype(self.end()) {
    auto where = bits::lower_bound<N>(self.items_.begin(), key, self.less_than_);
    if ((where != self.end()) && !self.less_than_(key, *where))
      return where + 1;
    else
      return self.end();
  }
};

template <class Key, class Value, class Compare>
class map<Key, Value, 0, Compare> {
  using container_type = bits::carray<std::pair<Key, Value>, 0>;
  impl::CompareKey<Compare> less_than_;

public:
  using key_type = Key;
  using mapped_type = Value;
  using value_type = typename container_type::value_type;
  using size_type = typename container_type::size_type;
  using difference_type = typename container_type::difference_type;
  using key_compare = decltype(less_than_);
  using reference = typename container_type::reference;
  using const_reference = typename container_type::const_reference;
  using pointer = typename container_type::pointer;
  using const_pointer = typename container_type::const_pointer;
  using iterator = pointer;
  using const_iterator = const_pointer;
  using reverse_iterator = pointer;
  using const_reverse_iterator = const_pointer;

public:
  /* constructors */
  constexpr map(const map &other) = default;
  constexpr map(std::initializer_list<value_type>, Compare const &compare)
      : less_than_{compare} {}
  constexpr map(std::initializer_list<value_type> items)
      : map{items, Compare{}} {}

  /* element access */
  constexpr mapped_type at(Key const &) const {
    FROZEN_THROW_OR_ABORT(std::out_of_range("invalid key"));
  }
  constexpr mapped_type at(Key const &) {
    FROZEN_THROW_OR_ABORT(std::out_of_range("invalid key"));
  }

  /* iterators */
  constexpr iterator begin() { return nullptr; }
  constexpr const_iterator begin() const { return nullptr; }
  constexpr const_iterator cbegin() const { return nullptr; }
  constexpr iterator end() { return nullptr; }
  constexpr const_iterator end() const { return nullptr; }
  constexpr const_iterator cend() const { return nullptr; }

  constexpr reverse_iterator rbegin() { return nullptr; }
  constexpr const_reverse_iterator rbegin() const { return nullptr; }
  constexpr const_reverse_iterator crbegin() const { return nullptr; }
  constexpr reverse_iterator rend() { return nullptr; }
  constexpr const_reverse_iterator rend() const { return nullptr; }
  constexpr const_reverse_iterator crend() const { return nullptr; }

  /* capacity */
  constexpr bool empty() const { return true; }
  constexpr size_type size() const { return 0; }
  constexpr size_type max_size() const { return 0; }

  /* lookup */

  constexpr std::size_t count(Key const &) const { return 0; }

  constexpr const_iterator find(Key const &) const { return end(); }
  constexpr iterator find(Key const &) { return end(); }

  constexpr std::pair<const_iterator, const_iterator>
  equal_range(Key const &) const {
    return {end(), end()};
  }
  constexpr std::pair<iterator, iterator>
  equal_range(Key const &) {
    return {end(), end()};
  }

  constexpr const_iterator lower_bound(Key const &) const { return end(); }
  constexpr iterator lower_bound(Key const &) { return end(); }

  constexpr const_iterator upper_bound(Key const &) const { return end(); }
  constexpr iterator upper_bound(Key const &) { return end(); }

  /* observers */
  constexpr key_compare key_comp() const { return less_than_; }
  constexpr key_compare value_comp() const { return less_than_; }
};

template <typename T, typename U>
constexpr auto make_map(bits::ignored_arg = {}/* for consistency with the initializer below for N = 0*/) {
  return map<T, U, 0>{};
}

template <typename T, typename U, std::size_t N>
constexpr auto make_map(std::pair<T, U> const (&items)[N]) {
  return map<T, U, N>{items};
}

template <typename T, typename U, std::size_t N>
constexpr auto make_map(std::array<std::pair<T, U>, N> const &items) {
  return map<T, U, N>{items};
}

} // namespace frozen

#endif
