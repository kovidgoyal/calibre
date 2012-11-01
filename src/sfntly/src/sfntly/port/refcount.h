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

// Object reference count and smart pointer implementation.

// Smart pointer usage in sfntly:
//
// sfntly carries a smart pointer implementation like COM.  Ref-countable object
// type inherits from RefCounted<>, which have AddRef and Release just like
// IUnknown (but no QueryInterface).  Use a Ptr<> based smart pointer to hold
// the object so that the object ref count is handled correctly.
//
// class Foo : public RefCounted<Foo> {
//  public:
//   static Foo* CreateInstance() {
//     Ptr<Foo> obj = new Foo();  // ref count = 1
//     return obj.Detach();
//   }
// };
// typedef Ptr<Foo> FooPtr;  // common short-hand notation
// FooPtr obj;
// obj.Attach(Foo::CreatedInstance());  // ref count = 1
// {
//   FooPtr obj2 = obj;  // ref count = 2
// }  // ref count = 1, obj2 out of scope
// obj.Release();  // ref count = 0, object destroyed

// Notes on usage:
// 1. Virtual inherit from RefCount interface in base class if smart pointers
//    are going to be defined.
// 2. All RefCounted objects must be instantiated on the heap.  Allocating the
//    object on stack will cause crash.
// 3. Be careful when you have complex inheritance.  For example,
//    class A : public RefCounted<A>;
//    class B : public A, public RefCounted<B>;
//    In this case the smart pointer is pretty dumb and don't count on it to
//    nicely destroy your objects as designed. Try refactor your code like
//    class I;  // the common interface and implementations
//    class A : public I, public RefCounted<A>;  // A specific implementation
//    class B : public I, public RefCounted<B>;  // B specific implementation
// 4. Smart pointers here are very bad candidates for function parameters.  Use
//    dumb pointers in function parameter list.
// 5. When down_cast is performed on a dangling pointer due to bugs in code,
//    VC++ will generate SEH which is not handled well in VC++ debugger.  One
//    can use WinDBG to run it and get the faulting stack.
// 6. Idioms for heap object as return value
//    Foo* createFoo() { FooPtr obj = new Foo(); return obj.Detach(); }
//    Foo* passthru() { FooPtr obj = createFoo(), return obj; }
//    FooPtr end_scope_pointer;
//    end_scope_pointer.Attach(passThrough);
//    If you are not passing that object back, you are the end of scope.

#ifndef SFNTLY_CPP_SRC_SFNTLY_PORT_REFCOUNT_H_
#define SFNTLY_CPP_SRC_SFNTLY_PORT_REFCOUNT_H_

#if !defined (NDEBUG)
  #define ENABLE_OBJECT_COUNTER
//  #define REF_COUNT_DEBUGGING
#endif

#if defined (REF_COUNT_DEBUGGING)
  #include <stdio.h>
  #include <typeinfo>
#endif

#include "sfntly/port/atomic.h"
#include "sfntly/port/type.h"

// Special tag for functions that requires caller to attach instead of using
// assignment operators.
#define CALLER_ATTACH

#if defined (REF_COUNT_DEBUGGING)
  #define DEBUG_OUTPUT(a) \
      fprintf(stderr, "%s%s:oc=%d,oid=%d,rc=%d\n", a, \
              typeid(this).name(), object_counter_, object_id_, ref_count_)
#else
  #define DEBUG_OUTPUT(a)
#endif

#if defined (_MSC_VER)
  // VC 2008/2010 incorrectly gives this warning for pure virtual functions
  // in virtual inheritance.  The only way to get around it is to disable it.
  #pragma warning(disable:4250)
#endif

namespace sfntly {

class RefCount {
 public:
  // Make gcc -Wnon-virtual-dtor happy.
  virtual ~RefCount() {}

  virtual size_t AddRef() const = 0;
  virtual size_t Release() const = 0;
};

template <typename T>
class NoAddRefRelease : public T {
 public:
  NoAddRefRelease();
  ~NoAddRefRelease();

 private:
  virtual size_t AddRef() const = 0;
  virtual size_t Release() const = 0;
};

template <typename TDerived>
class RefCounted : virtual public RefCount {
 public:
  RefCounted() : ref_count_(0) {
#if defined (ENABLE_OBJECT_COUNTER)
    object_id_ = AtomicIncrement(&next_id_);
    AtomicIncrement(&object_counter_);
    DEBUG_OUTPUT("C ");
#endif
  }
  RefCounted(const RefCounted<TDerived>&) : ref_count_(0) {}
  virtual ~RefCounted() {
#if defined (ENABLE_OBJECT_COUNTER)
    AtomicDecrement(&object_counter_);
    DEBUG_OUTPUT("D ");
#endif
  }

  RefCounted<TDerived>& operator=(const RefCounted<TDerived>&) {
    // Each object maintains own ref count, don't propagate.
    return *this;
  }

  virtual size_t AddRef() const {
    size_t new_count = AtomicIncrement(&ref_count_);
    DEBUG_OUTPUT("A ");
    return new_count;
  }

  virtual size_t Release() const {
    size_t new_ref_count = AtomicDecrement(&ref_count_);
    DEBUG_OUTPUT("R ");
    if (new_ref_count == 0) {
      // A C-style is used to cast away const-ness and to derived.
      // lint does not like this but this is how it works.
      delete (TDerived*)(this);
    }
    return new_ref_count;
  }

  mutable size_t ref_count_;  // reference count of current object
#if defined (ENABLE_OBJECT_COUNTER)
  static size_t object_counter_;
  static size_t next_id_;
  mutable size_t object_id_;
#endif
};

#if defined (ENABLE_OBJECT_COUNTER)
template <typename TDerived> size_t RefCounted<TDerived>::object_counter_ = 0;
template <typename TDerived> size_t RefCounted<TDerived>::next_id_ = 0;
#endif

// semi-smart pointer for RefCount derived objects, similar to CComPtr
template <typename T>
class Ptr {
 public:
  Ptr() : p_(NULL) {
  }

  // This constructor shall not be explicit.
  // lint does not like this but this is how it works.
  Ptr(T* pT) : p_(NULL) {
    *this = pT;
  }

  Ptr(const Ptr<T>& p) : p_(NULL) {
    *this = p;
  }

  ~Ptr() {
    Release();
  }

  T* operator=(T* pT) {
    if (p_ == pT) {
      return p_;
    }
    if (pT) {
      RefCount* p = static_cast<RefCount*>(pT);
      if (p == NULL) {
        return NULL;
      }
      p->AddRef();  // always AddRef() before Release()
    }
    Release();
    p_ = pT;
    return p_;
  }

  T* operator=(const Ptr<T>& p) {
    if (p_ == p.p_) {
      return p_;
    }
    return operator=(p.p_);
  }

  operator T*&() {
    return p_;
  }

  T& operator*() const {
    return *p_;  // It can throw!
  }

  NoAddRefRelease<T>* operator->() const {
    return (NoAddRefRelease<T>*)p_;  // It can throw!
  }

  bool operator!() const {
    return (p_ == NULL);
  }

  bool operator<(const Ptr<T>& p) const {
    return (p_ < p.p_);
  }

  bool operator!=(T* pT) const {
    return !operator==(pT);
  }

  bool operator==(T* pT) const {
    return (p_ == pT);
  }

  size_t Release() const {
    size_t ref_count = 0;
    if (p_) {
      RefCount* p = static_cast<RefCount*>(p_);
      if (p) {
        ref_count = p->Release();
      }
      p_ = NULL;
    }
    return ref_count;
  }

  void Attach(T* pT) {
    if (p_ != pT) {
      Release();
      p_ = pT;
    }
  }

  T* Detach() {
    T* pT = p_;
    p_ = NULL;
    return pT;
  }

  mutable T* p_;
};

}  // namespace sfntly

#endif  // SFNTLY_CPP_SRC_SFNTLY_PORT_REFCOUNT_H_
