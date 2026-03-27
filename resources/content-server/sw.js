(function(){
    "use strict";
    var ρσ_iterator_symbol = (typeof Symbol === "function" && typeof Symbol.iterator === "symbol") ? Symbol.iterator : "iterator-Symbol-5d0927e5554349048cf0e3762a228256";
    var ρσ_kwargs_symbol = (typeof Symbol === "function") ? Symbol("kwargs-object") : "kwargs-object-Symbol-5d0927e5554349048cf0e3762a228256";
    var ρσ_cond_temp, ρσ_expr_temp, ρσ_last_exception;
    var ρσ_object_counter = 0;
    if( typeof HTMLCollection !== "undefined" && typeof Symbol === "function") NodeList.prototype[Symbol.iterator] = HTMLCollection.prototype[Symbol.iterator] = NamedNodeMap.prototype[Symbol.iterator] = Array.prototype[Symbol.iterator];
var ρσ_len;
function ρσ_bool(val) {
    return !!val;
};
if (!ρσ_bool.__argnames__) Object.defineProperties(ρσ_bool, {
    __argnames__ : {value: ["val"]},
    __module__ : {value: "__main__"}
});

function ρσ_print() {
    var parts;
    if (typeof console === "object") {
        parts = [];
        for (var i = 0; i < arguments.length; i++) {
            parts.push(ρσ_str(arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i]));
        }
        console.log(parts.join(" "));
    }
};
if (!ρσ_print.__module__) Object.defineProperties(ρσ_print, {
    __module__ : {value: "__main__"}
});

function ρσ_int(val, base) {
    var ans;
    if (typeof val === "number") {
        ans = val | 0;
    } else {
        ans = parseInt(val, base || 10);
    }
    if (isNaN(ans)) {
        throw new ValueError("Invalid literal for int with base " + (base || 10) + ": " + val);
    }
    return ans;
};
if (!ρσ_int.__argnames__) Object.defineProperties(ρσ_int, {
    __argnames__ : {value: ["val", "base"]},
    __module__ : {value: "__main__"}
});

function ρσ_float(val) {
    var ans;
    if (typeof val === "number") {
        ans = val;
    } else {
        ans = parseFloat(val);
    }
    if (isNaN(ans)) {
        throw new ValueError("Could not convert string to float: " + arguments[0]);
    }
    return ans;
};
if (!ρσ_float.__argnames__) Object.defineProperties(ρσ_float, {
    __argnames__ : {value: ["val"]},
    __module__ : {value: "__main__"}
});

function ρσ_arraylike_creator() {
    var names;
    names = "Int8Array Uint8Array Uint8ClampedArray Int16Array Uint16Array Int32Array Uint32Array Float32Array Float64Array".split(" ");
    if (typeof HTMLCollection === "function") {
        names = names.concat("HTMLCollection NodeList NamedNodeMap TouchList".split(" "));
    }
    return (function() {
        var ρσ_anonfunc = function (x) {
            if (Array.isArray(x) || typeof x === "string" || names.indexOf(Object.prototype.toString.call(x).slice(8, -1)) > -1) {
                return true;
            }
            return false;
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["x"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
};
if (!ρσ_arraylike_creator.__module__) Object.defineProperties(ρσ_arraylike_creator, {
    __module__ : {value: "__main__"}
});

function options_object(f) {
    return (function() {
        var ρσ_anonfunc = function () {
            if (typeof arguments[arguments.length - 1] === "object") {
                arguments[ρσ_bound_index(arguments.length - 1, arguments)][ρσ_kwargs_symbol] = true;
            }
            return f.apply(this, arguments);
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
};
if (!options_object.__argnames__) Object.defineProperties(options_object, {
    __argnames__ : {value: ["f"]},
    __module__ : {value: "__main__"}
});

function ρσ_id(x) {
    return x.ρσ_object_id;
};
if (!ρσ_id.__argnames__) Object.defineProperties(ρσ_id, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_dir(item) {
    var arr;
    arr = ρσ_list_decorate([]);
    for (var i in item) {
        arr.push(i);
    }
    return arr;
};
if (!ρσ_dir.__argnames__) Object.defineProperties(ρσ_dir, {
    __argnames__ : {value: ["item"]},
    __module__ : {value: "__main__"}
});

function ρσ_ord(x) {
    var ans, second;
    ans = x.charCodeAt(0);
    if (55296 <= ans && ans <= 56319) {
        second = x.charCodeAt(1);
        if (56320 <= second && second <= 57343) {
            return (ans - 55296) * 1024 + second - 56320 + 65536;
        }
        throw new TypeError("string is missing the low surrogate char");
    }
    return ans;
};
if (!ρσ_ord.__argnames__) Object.defineProperties(ρσ_ord, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_chr(code) {
    if (code <= 65535) {
        return String.fromCharCode(code);
    }
    code -= 65536;
    return String.fromCharCode(55296 + (code >> 10), 56320 + (code & 1023));
};
if (!ρσ_chr.__argnames__) Object.defineProperties(ρσ_chr, {
    __argnames__ : {value: ["code"]},
    __module__ : {value: "__main__"}
});

function ρσ_callable(x) {
    return typeof x === "function";
};
if (!ρσ_callable.__argnames__) Object.defineProperties(ρσ_callable, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_bin(x) {
    var ans;
    if (typeof x !== "number" || x % 1 !== 0) {
        throw new TypeError("integer required");
    }
    ans = x.toString(2);
    if (ans[0] === "-") {
        ans = "-" + "0b" + ans.slice(1);
    } else {
        ans = "0b" + ans;
    }
    return ans;
};
if (!ρσ_bin.__argnames__) Object.defineProperties(ρσ_bin, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_hex(x) {
    var ans;
    if (typeof x !== "number" || x % 1 !== 0) {
        throw new TypeError("integer required");
    }
    ans = x.toString(16);
    if (ans[0] === "-") {
        ans = "-" + "0x" + ans.slice(1);
    } else {
        ans = "0x" + ans;
    }
    return ans;
};
if (!ρσ_hex.__argnames__) Object.defineProperties(ρσ_hex, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_enumerate(iterable) {
    var ans, iterator;
    ans = {"_i":-1};
    ans[ρσ_iterator_symbol] = (function() {
        var ρσ_anonfunc = function () {
            return this;
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    if (ρσ_arraylike(iterable)) {
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i < iterable.length) {
                    return {'done':false, 'value':[this._i, iterable[this._i]]};
                }
                return {'done':true};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    }
    if (typeof iterable[ρσ_iterator_symbol] === "function") {
        iterator = (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
        ans["_iterator"] = iterator;
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                var r;
                r = this._iterator.next();
                if (r.done) {
                    return {'done':true};
                }
                this._i += 1;
                return {'done':false, 'value':[this._i, r.value]};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    }
    return ρσ_enumerate(Object.keys(iterable));
};
if (!ρσ_enumerate.__argnames__) Object.defineProperties(ρσ_enumerate, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

function ρσ_reversed(iterable) {
    var ans;
    if (ρσ_arraylike(iterable)) {
        ans = {"_i": iterable.length};
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i -= 1;
                if (this._i > -1) {
                    return {'done':false, 'value':iterable[this._i]};
                }
                return {'done':true};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        ans[ρσ_iterator_symbol] = (function() {
            var ρσ_anonfunc = function () {
                return this;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    }
    throw new TypeError("reversed() can only be called on arrays or strings");
};
if (!ρσ_reversed.__argnames__) Object.defineProperties(ρσ_reversed, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

function ρσ_iter(iterable) {
    var ans;
    if (typeof iterable[ρσ_iterator_symbol] === "function") {
        return (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
    }
    if (ρσ_arraylike(iterable)) {
        ans = {"_i":-1};
        ans[ρσ_iterator_symbol] = (function() {
            var ρσ_anonfunc = function () {
                return this;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i < iterable.length) {
                    return {'done':false, 'value':iterable[this._i]};
                }
                return {'done':true};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    }
    return ρσ_iter(Object.keys(iterable));
};
if (!ρσ_iter.__argnames__) Object.defineProperties(ρσ_iter, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

function ρσ_range_next(step, length) {
    var ρσ_unpack;
    this._i += step;
    this._idx += 1;
    if (this._idx >= length) {
        ρσ_unpack = [this.__i, -1];
        this._i = ρσ_unpack[0];
        this._idx = ρσ_unpack[1];
        return {'done':true};
    }
    return {'done':false, 'value':this._i};
};
if (!ρσ_range_next.__argnames__) Object.defineProperties(ρσ_range_next, {
    __argnames__ : {value: ["step", "length"]},
    __module__ : {value: "__main__"}
});

function ρσ_range(start, stop, step) {
    var length, ans;
    if (arguments.length <= 1) {
        stop = start || 0;
        start = 0;
    }
    step = arguments[2] || 1;
    length = Math.max(Math.ceil((stop - start) / step), 0);
    ans = {start:start, step:step, stop:stop};
    ans[ρσ_iterator_symbol] = (function() {
        var ρσ_anonfunc = function () {
            var it;
            it = {"_i": start - step, "_idx": -1};
            it.next = ρσ_range_next.bind(it, step, length);
            it[ρσ_iterator_symbol] = (function() {
                var ρσ_anonfunc = function () {
                    return this;
                };
                if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
            return it;
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ans.count = (function() {
        var ρσ_anonfunc = function (val) {
            if (!this._cached) {
                this._cached = list(this);
            }
            return this._cached.count(val);
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["val"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ans.index = (function() {
        var ρσ_anonfunc = function (val) {
            if (!this._cached) {
                this._cached = list(this);
            }
            return this._cached.index(val);
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["val"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    if (typeof Proxy === "function") {
        ans = new Proxy(ans, (function(){
            var ρσ_d = {};
            ρσ_d["get"] = (function() {
                var ρσ_anonfunc = function (obj, prop) {
                    var iprop;
                    if (typeof prop === "string") {
                        iprop = parseInt(prop);
                        if (!isNaN(iprop)) {
                            prop = iprop;
                        }
                    }
                    if (typeof prop === "number") {
                        if (!obj._cached) {
                            obj._cached = list(obj);
                        }
                        return (ρσ_expr_temp = obj._cached)[(typeof prop === "number" && prop < 0) ? ρσ_expr_temp.length + prop : prop];
                    }
                    return obj[(typeof prop === "number" && prop < 0) ? obj.length + prop : prop];
                };
                if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                    __argnames__ : {value: ["obj", "prop"]},
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
            return ρσ_d;
        }).call(this));
    }
    return ans;
};
if (!ρσ_range.__argnames__) Object.defineProperties(ρσ_range, {
    __argnames__ : {value: ["start", "stop", "step"]},
    __module__ : {value: "__main__"}
});

function ρσ_getattr(obj, name, defval) {
    var ret;
    try {
        ret = obj[(typeof name === "number" && name < 0) ? obj.length + name : name];
    } catch (ρσ_Exception) {
        ρσ_last_exception = ρσ_Exception;
        if (ρσ_Exception instanceof TypeError) {
            if (defval === undefined) {
                throw new AttributeError("The attribute " + name + " is not present");
            }
            return defval;
        } else {
            throw ρσ_Exception;
        }
    }
    if (ret === undefined && !(name in obj)) {
        if (defval === undefined) {
            throw new AttributeError("The attribute " + name + " is not present");
        }
        ret = defval;
    }
    return ret;
};
if (!ρσ_getattr.__argnames__) Object.defineProperties(ρσ_getattr, {
    __argnames__ : {value: ["obj", "name", "defval"]},
    __module__ : {value: "__main__"}
});

function ρσ_setattr(obj, name, value) {
    obj[(typeof name === "number" && name < 0) ? obj.length + name : name] = value;
};
if (!ρσ_setattr.__argnames__) Object.defineProperties(ρσ_setattr, {
    __argnames__ : {value: ["obj", "name", "value"]},
    __module__ : {value: "__main__"}
});

function ρσ_hasattr(obj, name) {
    return name in obj;
};
if (!ρσ_hasattr.__argnames__) Object.defineProperties(ρσ_hasattr, {
    __argnames__ : {value: ["obj", "name"]},
    __module__ : {value: "__main__"}
});

ρσ_len = (function() {
    var ρσ_anonfunc = function () {
        function len(obj) {
            if (ρσ_arraylike(obj)) {
                return obj.length;
            }
            if (typeof obj.__len__ === "function") {
                return obj.__len__();
            }
            if (obj instanceof Set || obj instanceof Map) {
                return obj.size;
            }
            return Object.keys(obj).length;
        };
        if (!len.__argnames__) Object.defineProperties(len, {
            __argnames__ : {value: ["obj"]},
            __module__ : {value: "__main__"}
        });

        function len5(obj) {
            if (ρσ_arraylike(obj)) {
                return obj.length;
            }
            if (typeof obj.__len__ === "function") {
                return obj.__len__();
            }
            return Object.keys(obj).length;
        };
        if (!len5.__argnames__) Object.defineProperties(len5, {
            __argnames__ : {value: ["obj"]},
            __module__ : {value: "__main__"}
        });

        return (typeof Set === "function" && typeof Map === "function") ? len : len5;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})()();
function ρσ_get_module(name) {
    return ρσ_modules[(typeof name === "number" && name < 0) ? ρσ_modules.length + name : name];
};
if (!ρσ_get_module.__argnames__) Object.defineProperties(ρσ_get_module, {
    __argnames__ : {value: ["name"]},
    __module__ : {value: "__main__"}
});

function ρσ_pow(x, y, z) {
    var ans;
    ans = Math.pow(x, y);
    if (z !== undefined) {
        ans %= z;
    }
    return ans;
};
if (!ρσ_pow.__argnames__) Object.defineProperties(ρσ_pow, {
    __argnames__ : {value: ["x", "y", "z"]},
    __module__ : {value: "__main__"}
});

function ρσ_type(x) {
    return x.constructor;
};
if (!ρσ_type.__argnames__) Object.defineProperties(ρσ_type, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_divmod(x, y) {
    var d;
    if (y === 0) {
        throw new ZeroDivisionError("integer division or modulo by zero");
    }
    d = Math.floor(x / y);
    return [d, x - d * y];
};
if (!ρσ_divmod.__argnames__) Object.defineProperties(ρσ_divmod, {
    __argnames__ : {value: ["x", "y"]},
    __module__ : {value: "__main__"}
});

function ρσ_max() {
    var kwargs = arguments[arguments.length-1];
    if (kwargs === null || typeof kwargs !== "object" || kwargs [ρσ_kwargs_symbol] !== true) kwargs = {};
    var args = Array.prototype.slice.call(arguments, 0);
    if (kwargs !== null && typeof kwargs === "object" && kwargs [ρσ_kwargs_symbol] === true) args.pop();
    var args, x;
    if (args.length === 0) {
        if (kwargs.defval !== undefined) {
            return kwargs.defval;
        }
        throw new TypeError("expected at least one argument");
    }
    if (args.length === 1) {
        args = args[0];
    }
    if (kwargs.key) {
        args = (function() {
            var ρσ_Iter = ρσ_Iterable(args), ρσ_Result = [], x;
            for (var ρσ_Index = 0; ρσ_Index < ρσ_Iter.length; ρσ_Index++) {
                x = ρσ_Iter[ρσ_Index];
                ρσ_Result.push(kwargs.key(x));
            }
            ρσ_Result = ρσ_list_constructor(ρσ_Result);
            return ρσ_Result;
        })();
    }
    if (!Array.isArray(args)) {
        args = list(args);
    }
    if (args.length) {
        return this.apply(null, args);
    }
    if (kwargs.defval !== undefined) {
        return kwargs.defval;
    }
    throw new TypeError("expected at least one argument");
};
if (!ρσ_max.__handles_kwarg_interpolation__) Object.defineProperties(ρσ_max, {
    __handles_kwarg_interpolation__ : {value: true},
    __module__ : {value: "__main__"}
});

var abs = Math.abs, max = ρσ_max.bind(Math.max), min = ρσ_max.bind(Math.min), bool = ρσ_bool, type = ρσ_type;
var float = ρσ_float, int = ρσ_int, arraylike = ρσ_arraylike_creator(), ρσ_arraylike = arraylike;
var print = ρσ_print, id = ρσ_id, get_module = ρσ_get_module, pow = ρσ_pow, divmod = ρσ_divmod;
var dir = ρσ_dir, ord = ρσ_ord, chr = ρσ_chr, bin = ρσ_bin, hex = ρσ_hex, callable = ρσ_callable;
var enumerate = ρσ_enumerate, iter = ρσ_iter, reversed = ρσ_reversed, len = ρσ_len;
var range = ρσ_range, getattr = ρσ_getattr, setattr = ρσ_setattr, hasattr = ρσ_hasattr;function ρσ_equals(a, b) {
    var ρσ_unpack, akeys, bkeys, key;
    if (a === b) {
        return true;
    }
    if (a && typeof a.__eq__ === "function") {
        return a.__eq__(b);
    }
    if (b && typeof b.__eq__ === "function") {
        return b.__eq__(a);
    }
    if (ρσ_arraylike(a) && ρσ_arraylike(b)) {
        if ((a.length !== b.length && (typeof a.length !== "object" || ρσ_not_equals(a.length, b.length)))) {
            return false;
        }
        for (var i=0; i < a.length; i++) {
            if (!((a[(typeof i === "number" && i < 0) ? a.length + i : i] === b[(typeof i === "number" && i < 0) ? b.length + i : i] || typeof a[(typeof i === "number" && i < 0) ? a.length + i : i] === "object" && ρσ_equals(a[(typeof i === "number" && i < 0) ? a.length + i : i], b[(typeof i === "number" && i < 0) ? b.length + i : i])))) {
                return false;
            }
        }
        return true;
    }
    if (typeof a === "object" && typeof b === "object" && a !== null && b !== null && (a.constructor === Object && b.constructor === Object || Object.getPrototypeOf(a) === null && Object.getPrototypeOf(b) === null)) {
        ρσ_unpack = [Object.keys(a), Object.keys(b)];
        akeys = ρσ_unpack[0];
        bkeys = ρσ_unpack[1];
        if (akeys.length !== bkeys.length) {
            return false;
        }
        for (var j=0; j < akeys.length; j++) {
            key = akeys[(typeof j === "number" && j < 0) ? akeys.length + j : j];
            if (!((a[(typeof key === "number" && key < 0) ? a.length + key : key] === b[(typeof key === "number" && key < 0) ? b.length + key : key] || typeof a[(typeof key === "number" && key < 0) ? a.length + key : key] === "object" && ρσ_equals(a[(typeof key === "number" && key < 0) ? a.length + key : key], b[(typeof key === "number" && key < 0) ? b.length + key : key])))) {
                return false;
            }
        }
        return true;
    }
    return false;
};
if (!ρσ_equals.__argnames__) Object.defineProperties(ρσ_equals, {
    __argnames__ : {value: ["a", "b"]},
    __module__ : {value: "__main__"}
});

function ρσ_not_equals(a, b) {
    if (a === b) {
        return false;
    }
    if (a && typeof a.__ne__ === "function") {
        return a.__ne__(b);
    }
    if (b && typeof b.__ne__ === "function") {
        return b.__ne__(a);
    }
    return !ρσ_equals(a, b);
};
if (!ρσ_not_equals.__argnames__) Object.defineProperties(ρσ_not_equals, {
    __argnames__ : {value: ["a", "b"]},
    __module__ : {value: "__main__"}
});

var equals = ρσ_equals;
function ρσ_list_extend(iterable) {
    var start, iterator, result;
    if (Array.isArray(iterable) || typeof iterable === "string") {
        start = this.length;
        this.length += iterable.length;
        for (var i = 0; i < iterable.length; i++) {
            (ρσ_expr_temp = this)[ρσ_bound_index(start + i, ρσ_expr_temp)] = iterable[(typeof i === "number" && i < 0) ? iterable.length + i : i];
        }
    } else {
        iterator = (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
        result = iterator.next();
        while (!result.done) {
            this.push(result.value);
            result = iterator.next();
        }
    }
};
if (!ρσ_list_extend.__argnames__) Object.defineProperties(ρσ_list_extend, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_index(val, start, stop) {
    var idx;
    start = start || 0;
    if (start < 0) {
        start = this.length + start;
    }
    if (start < 0) {
        throw new ValueError(val + " is not in list");
    }
    if (stop === undefined) {
        idx = this.indexOf(val, start);
        if (idx === -1) {
            throw new ValueError(val + " is not in list");
        }
        return idx;
    }
    if (stop < 0) {
        stop = this.length + stop;
    }
    for (var i = start; i < stop; i++) {
        if (((ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] === val || typeof (ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] === "object" && ρσ_equals((ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i], val))) {
            return i;
        }
    }
    throw new ValueError(val + " is not in list");
};
if (!ρσ_list_index.__argnames__) Object.defineProperties(ρσ_list_index, {
    __argnames__ : {value: ["val", "start", "stop"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_pop(index) {
    var ans;
    if (this.length === 0) {
        throw new IndexError("list is empty");
    }
    if (index === undefined) {
        index = -1;
    }
    ans = this.splice(index, 1);
    if (!ans.length) {
        throw new IndexError("pop index out of range");
    }
    return ans[0];
};
if (!ρσ_list_pop.__argnames__) Object.defineProperties(ρσ_list_pop, {
    __argnames__ : {value: ["index"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_remove(value) {
    var idx;
    idx = this.indexOf(value);
    if (idx === -1) {
        throw new ValueError(value + " not in list");
    }
    this.splice(idx, 1);
};
if (!ρσ_list_remove.__argnames__) Object.defineProperties(ρσ_list_remove, {
    __argnames__ : {value: ["value"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_to_string() {
    return "[" + this.join(", ") + "]";
};
if (!ρσ_list_to_string.__module__) Object.defineProperties(ρσ_list_to_string, {
    __module__ : {value: "__main__"}
});

function ρσ_list_insert(index, val) {
    if (index < 0) {
        index += this.length;
    }
    index = min(this.length, max(index, 0));
    if (index === 0) {
        this.unshift(val);
        return;
    }
    for (var i = this.length; i > index; i--) {
        (ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] = (ρσ_expr_temp = this)[ρσ_bound_index(i - 1, ρσ_expr_temp)];
    }
    (ρσ_expr_temp = this)[(typeof index === "number" && index < 0) ? ρσ_expr_temp.length + index : index] = val;
};
if (!ρσ_list_insert.__argnames__) Object.defineProperties(ρσ_list_insert, {
    __argnames__ : {value: ["index", "val"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_copy() {
    return ρσ_list_constructor(this);
};
if (!ρσ_list_copy.__module__) Object.defineProperties(ρσ_list_copy, {
    __module__ : {value: "__main__"}
});

function ρσ_list_clear() {
    this.length = 0;
};
if (!ρσ_list_clear.__module__) Object.defineProperties(ρσ_list_clear, {
    __module__ : {value: "__main__"}
});

function ρσ_list_as_array() {
    return Array.prototype.slice.call(this);
};
if (!ρσ_list_as_array.__module__) Object.defineProperties(ρσ_list_as_array, {
    __module__ : {value: "__main__"}
});

function ρσ_list_count(value) {
    return this.reduce((function() {
        var ρσ_anonfunc = function (n, val) {
            return n + (val === value);
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["n", "val"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })(), 0);
};
if (!ρσ_list_count.__argnames__) Object.defineProperties(ρσ_list_count, {
    __argnames__ : {value: ["value"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_sort_key(value) {
    var t;
    t = typeof value;
    if (t === "string" || t === "number") {
        return value;
    }
    return value.toString();
};
if (!ρσ_list_sort_key.__argnames__) Object.defineProperties(ρσ_list_sort_key, {
    __argnames__ : {value: ["value"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_sort_cmp(a, b, ap, bp) {
    if (a < b) {
        return -1;
    }
    if (a > b) {
        return 1;
    }
    return ap - bp;
};
if (!ρσ_list_sort_cmp.__argnames__) Object.defineProperties(ρσ_list_sort_cmp, {
    __argnames__ : {value: ["a", "b", "ap", "bp"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_sort() {
    var key = (arguments[0] === undefined || ( 0 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true)) ? ρσ_list_sort.__defaults__.key : arguments[0];
    var reverse = (arguments[1] === undefined || ( 1 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true)) ? ρσ_list_sort.__defaults__.reverse : arguments[1];
    var ρσ_kwargs_obj = arguments[arguments.length-1];
    if (ρσ_kwargs_obj === null || typeof ρσ_kwargs_obj !== "object" || ρσ_kwargs_obj [ρσ_kwargs_symbol] !== true) ρσ_kwargs_obj = {};
    if (Object.prototype.hasOwnProperty.call(ρσ_kwargs_obj, "key")){
        key = ρσ_kwargs_obj.key;
    }
    if (Object.prototype.hasOwnProperty.call(ρσ_kwargs_obj, "reverse")){
        reverse = ρσ_kwargs_obj.reverse;
    }
    var mult, keymap, posmap, k;
    key = key || ρσ_list_sort_key;
    mult = (reverse) ? -1 : 1;
    keymap = dict();
    posmap = dict();
    for (var i=0; i < this.length; i++) {
        k = (ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i];
        keymap.set(k, key(k));
        posmap.set(k, i);
    }
    this.sort((function() {
        var ρσ_anonfunc = function (a, b) {
            return mult * ρσ_list_sort_cmp(keymap.get(a), keymap.get(b), posmap.get(a), posmap.get(b));
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["a", "b"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })());
};
if (!ρσ_list_sort.__defaults__) Object.defineProperties(ρσ_list_sort, {
    __defaults__ : {value: {key:null, reverse:false}},
    __handles_kwarg_interpolation__ : {value: true},
    __argnames__ : {value: ["key", "reverse"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_concat() {
    var ans;
    ans = Array.prototype.concat.apply(this, arguments);
    ρσ_list_decorate(ans);
    return ans;
};
if (!ρσ_list_concat.__module__) Object.defineProperties(ρσ_list_concat, {
    __module__ : {value: "__main__"}
});

function ρσ_list_slice() {
    var ans;
    ans = Array.prototype.slice.apply(this, arguments);
    ρσ_list_decorate(ans);
    return ans;
};
if (!ρσ_list_slice.__module__) Object.defineProperties(ρσ_list_slice, {
    __module__ : {value: "__main__"}
});

function ρσ_list_iterator(value) {
    var self;
    self = this;
    return (function(){
        var ρσ_d = {};
        ρσ_d["_i"] = -1;
        ρσ_d["_list"] = self;
        ρσ_d["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i >= this._list.length) {
                    return (function(){
                        var ρσ_d = {};
                        ρσ_d["done"] = true;
                        return ρσ_d;
                    }).call(this);
                }
                return (function(){
                    var ρσ_d = {};
                    ρσ_d["done"] = false;
                    ρσ_d["value"] = (ρσ_expr_temp = this._list)[ρσ_bound_index(this._i, ρσ_expr_temp)];
                    return ρσ_d;
                }).call(this);
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ρσ_d;
    }).call(this);
};
if (!ρσ_list_iterator.__argnames__) Object.defineProperties(ρσ_list_iterator, {
    __argnames__ : {value: ["value"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_len() {
    return this.length;
};
if (!ρσ_list_len.__module__) Object.defineProperties(ρσ_list_len, {
    __module__ : {value: "__main__"}
});

function ρσ_list_contains(val) {
    for (var i = 0; i < this.length; i++) {
        if (((ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] === val || typeof (ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] === "object" && ρσ_equals((ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i], val))) {
            return true;
        }
    }
    return false;
};
if (!ρσ_list_contains.__argnames__) Object.defineProperties(ρσ_list_contains, {
    __argnames__ : {value: ["val"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_eq(other) {
    if (!ρσ_arraylike(other)) {
        return false;
    }
    if ((this.length !== other.length && (typeof this.length !== "object" || ρσ_not_equals(this.length, other.length)))) {
        return false;
    }
    for (var i = 0; i < this.length; i++) {
        if (!(((ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] === other[(typeof i === "number" && i < 0) ? other.length + i : i] || typeof (ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] === "object" && ρσ_equals((ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i], other[(typeof i === "number" && i < 0) ? other.length + i : i])))) {
            return false;
        }
    }
    return true;
};
if (!ρσ_list_eq.__argnames__) Object.defineProperties(ρσ_list_eq, {
    __argnames__ : {value: ["other"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_decorate(ans) {
    ans.append = Array.prototype.push;
    ans.toString = ρσ_list_to_string;
    ans.inspect = ρσ_list_to_string;
    ans.extend = ρσ_list_extend;
    ans.index = ρσ_list_index;
    ans.pypop = ρσ_list_pop;
    ans.remove = ρσ_list_remove;
    ans.insert = ρσ_list_insert;
    ans.copy = ρσ_list_copy;
    ans.clear = ρσ_list_clear;
    ans.count = ρσ_list_count;
    ans.concat = ρσ_list_concat;
    ans.pysort = ρσ_list_sort;
    ans.slice = ρσ_list_slice;
    ans.as_array = ρσ_list_as_array;
    ans.__len__ = ρσ_list_len;
    ans.__contains__ = ρσ_list_contains;
    ans.__eq__ = ρσ_list_eq;
    ans.constructor = ρσ_list_constructor;
    if (typeof ans[ρσ_iterator_symbol] !== "function") {
        ans[ρσ_iterator_symbol] = ρσ_list_iterator;
    }
    return ans;
};
if (!ρσ_list_decorate.__argnames__) Object.defineProperties(ρσ_list_decorate, {
    __argnames__ : {value: ["ans"]},
    __module__ : {value: "__main__"}
});

function ρσ_list_constructor(iterable) {
    var ans, iterator, result;
    if (iterable === undefined) {
        ans = [];
    } else if (ρσ_arraylike(iterable)) {
        ans = new Array(iterable.length);
        for (var i = 0; i < iterable.length; i++) {
            ans[(typeof i === "number" && i < 0) ? ans.length + i : i] = iterable[(typeof i === "number" && i < 0) ? iterable.length + i : i];
        }
    } else if (typeof iterable[ρσ_iterator_symbol] === "function") {
        iterator = (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
        ans = ρσ_list_decorate([]);
        result = iterator.next();
        while (!result.done) {
            ans.push(result.value);
            result = iterator.next();
        }
    } else if (typeof iterable === "number") {
        ans = new Array(iterable);
    } else {
        ans = Object.keys(iterable);
    }
    return ρσ_list_decorate(ans);
};
if (!ρσ_list_constructor.__argnames__) Object.defineProperties(ρσ_list_constructor, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

ρσ_list_constructor.__name__ = "list";
var list = ρσ_list_constructor, list_wrap = ρσ_list_decorate;
function sorted() {
    var iterable = ( 0 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true) ? undefined : arguments[0];
    var key = (arguments[1] === undefined || ( 1 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true)) ? sorted.__defaults__.key : arguments[1];
    var reverse = (arguments[2] === undefined || ( 2 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true)) ? sorted.__defaults__.reverse : arguments[2];
    var ρσ_kwargs_obj = arguments[arguments.length-1];
    if (ρσ_kwargs_obj === null || typeof ρσ_kwargs_obj !== "object" || ρσ_kwargs_obj [ρσ_kwargs_symbol] !== true) ρσ_kwargs_obj = {};
    if (Object.prototype.hasOwnProperty.call(ρσ_kwargs_obj, "key")){
        key = ρσ_kwargs_obj.key;
    }
    if (Object.prototype.hasOwnProperty.call(ρσ_kwargs_obj, "reverse")){
        reverse = ρσ_kwargs_obj.reverse;
    }
    var ans;
    ans = ρσ_list_constructor(iterable);
    ans.pysort(key, reverse);
    return ans;
};
if (!sorted.__defaults__) Object.defineProperties(sorted, {
    __defaults__ : {value: {key:null, reverse:false}},
    __handles_kwarg_interpolation__ : {value: true},
    __argnames__ : {value: ["iterable", "key", "reverse"]},
    __module__ : {value: "__main__"}
});

var ρσ_global_object_id = 0, ρσ_set_implementation;
function ρσ_set_keyfor(x) {
    var t, ans;
    t = typeof x;
    if (t === "string" || t === "number" || t === "boolean") {
        return "_" + t[0] + x;
    }
    if (x === null) {
        return "__!@#$0";
    }
    ans = x.ρσ_hash_key_prop;
    if (ans === undefined) {
        ans = "_!@#$" + (++ρσ_global_object_id);
        Object.defineProperty(x, "ρσ_hash_key_prop", (function(){
            var ρσ_d = {};
            ρσ_d["value"] = ans;
            return ρσ_d;
        }).call(this));
    }
    return ans;
};
if (!ρσ_set_keyfor.__argnames__) Object.defineProperties(ρσ_set_keyfor, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_set_polyfill() {
    this._store = {};
    this.size = 0;
};
if (!ρσ_set_polyfill.__module__) Object.defineProperties(ρσ_set_polyfill, {
    __module__ : {value: "__main__"}
});

ρσ_set_polyfill.prototype.add = (function() {
    var ρσ_anonfunc = function (x) {
        var key;
        key = ρσ_set_keyfor(x);
        if (!Object.prototype.hasOwnProperty.call(this._store, key)) {
            this.size += 1;
            (ρσ_expr_temp = this._store)[(typeof key === "number" && key < 0) ? ρσ_expr_temp.length + key : key] = x;
        }
        return this;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set_polyfill.prototype.clear = (function() {
    var ρσ_anonfunc = function (x) {
        this._store = {};
        this.size = 0;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set_polyfill.prototype.delete = (function() {
    var ρσ_anonfunc = function (x) {
        var key;
        key = ρσ_set_keyfor(x);
        if (Object.prototype.hasOwnProperty.call(this._store, key)) {
            this.size -= 1;
            delete this._store[key];
            return true;
        }
        return false;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set_polyfill.prototype.has = (function() {
    var ρσ_anonfunc = function (x) {
        return Object.prototype.hasOwnProperty.call(this._store, ρσ_set_keyfor(x));
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set_polyfill.prototype.values = (function() {
    var ρσ_anonfunc = function (x) {
        var ans;
        ans = {'_keys': Object.keys(this._store), '_i':-1, '_s':this._store};
        ans[ρσ_iterator_symbol] = (function() {
            var ρσ_anonfunc = function () {
                return this;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i >= this._keys.length) {
                    return {'done': true};
                }
                return {'done':false, 'value':this._s[this._keys[this._i]]};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
if (typeof Set !== "function" || typeof Set.prototype.delete !== "function") {
    ρσ_set_implementation = ρσ_set_polyfill;
} else {
    ρσ_set_implementation = Set;
}
function ρσ_set(iterable) {
    var ans, s, iterator, result, keys;
    if (this instanceof ρσ_set) {
        this.jsset = new ρσ_set_implementation;
        ans = this;
        if (iterable === undefined) {
            return ans;
        }
        s = ans.jsset;
        if (ρσ_arraylike(iterable)) {
            for (var i = 0; i < iterable.length; i++) {
                s.add(iterable[(typeof i === "number" && i < 0) ? iterable.length + i : i]);
            }
        } else if (typeof iterable[ρσ_iterator_symbol] === "function") {
            iterator = (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
            result = iterator.next();
            while (!result.done) {
                s.add(result.value);
                result = iterator.next();
            }
        } else {
            keys = Object.keys(iterable);
            for (var j=0; j < keys.length; j++) {
                s.add(keys[(typeof j === "number" && j < 0) ? keys.length + j : j]);
            }
        }
        return ans;
    } else {
        return new ρσ_set(iterable);
    }
};
if (!ρσ_set.__argnames__) Object.defineProperties(ρσ_set, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

ρσ_set.prototype.__name__ = "set";
Object.defineProperties(ρσ_set.prototype, (function(){
    var ρσ_d = {};
    ρσ_d["length"] = (function(){
        var ρσ_d = {};
        ρσ_d["get"] = (function() {
            var ρσ_anonfunc = function () {
                return this.jsset.size;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ρσ_d;
    }).call(this);
    ρσ_d["size"] = (function(){
        var ρσ_d = {};
        ρσ_d["get"] = (function() {
            var ρσ_anonfunc = function () {
                return this.jsset.size;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ρσ_d;
    }).call(this);
    return ρσ_d;
}).call(this));
ρσ_set.prototype.__len__ = (function() {
    var ρσ_anonfunc = function () {
        return this.jsset.size;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.has = ρσ_set.prototype.__contains__ = (function() {
    var ρσ_anonfunc = function (x) {
        return this.jsset.has(x);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.add = (function() {
    var ρσ_anonfunc = function (x) {
        this.jsset.add(x);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.clear = (function() {
    var ρσ_anonfunc = function () {
        this.jsset.clear();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.copy = (function() {
    var ρσ_anonfunc = function () {
        return ρσ_set(this);
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.discard = (function() {
    var ρσ_anonfunc = function (x) {
        this.jsset.delete(x);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype[ρσ_iterator_symbol] = (function() {
    var ρσ_anonfunc = function () {
        return this.jsset.values();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.difference = (function() {
    var ρσ_anonfunc = function () {
        var ans, s, iterator, r, x, has;
        ans = new ρσ_set;
        s = ans.jsset;
        iterator = this.jsset.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            has = false;
            for (var i = 0; i < arguments.length; i++) {
                if (arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i].has(x)) {
                    has = true;
                    break;
                }
            }
            if (!has) {
                s.add(x);
            }
            r = iterator.next();
        }
        return ans;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.difference_update = (function() {
    var ρσ_anonfunc = function () {
        var s, remove, iterator, r, x;
        s = this.jsset;
        remove = [];
        iterator = s.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            for (var i = 0; i < arguments.length; i++) {
                if (arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i].has(x)) {
                    remove.push(x);
                    break;
                }
            }
            r = iterator.next();
        }
        for (var j = 0; j < remove.length; j++) {
            s.delete(remove[(typeof j === "number" && j < 0) ? remove.length + j : j]);
        }
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.intersection = (function() {
    var ρσ_anonfunc = function () {
        var ans, s, iterator, r, x, has;
        ans = new ρσ_set;
        s = ans.jsset;
        iterator = this.jsset.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            has = true;
            for (var i = 0; i < arguments.length; i++) {
                if (!arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i].has(x)) {
                    has = false;
                    break;
                }
            }
            if (has) {
                s.add(x);
            }
            r = iterator.next();
        }
        return ans;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.intersection_update = (function() {
    var ρσ_anonfunc = function () {
        var s, remove, iterator, r, x;
        s = this.jsset;
        remove = [];
        iterator = s.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            for (var i = 0; i < arguments.length; i++) {
                if (!arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i].has(x)) {
                    remove.push(x);
                    break;
                }
            }
            r = iterator.next();
        }
        for (var j = 0; j < remove.length; j++) {
            s.delete(remove[(typeof j === "number" && j < 0) ? remove.length + j : j]);
        }
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.isdisjoint = (function() {
    var ρσ_anonfunc = function (other) {
        var iterator, r, x;
        iterator = this.jsset.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            if (other.has(x)) {
                return false;
            }
            r = iterator.next();
        }
        return true;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.issubset = (function() {
    var ρσ_anonfunc = function (other) {
        var iterator, r, x;
        iterator = this.jsset.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            if (!other.has(x)) {
                return false;
            }
            r = iterator.next();
        }
        return true;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.issuperset = (function() {
    var ρσ_anonfunc = function (other) {
        var s, iterator, r, x;
        s = this.jsset;
        iterator = other.jsset.values();
        r = iterator.next();
        while (!r.done) {
            x = r.value;
            if (!s.has(x)) {
                return false;
            }
            r = iterator.next();
        }
        return true;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.pop = (function() {
    var ρσ_anonfunc = function () {
        var iterator, r;
        iterator = this.jsset.values();
        r = iterator.next();
        if (r.done) {
            throw new KeyError("pop from an empty set");
        }
        this.jsset.delete(r.value);
        return r.value;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.remove = (function() {
    var ρσ_anonfunc = function (x) {
        if (!this.jsset.delete(x)) {
            throw new KeyError(x.toString());
        }
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.symmetric_difference = (function() {
    var ρσ_anonfunc = function (other) {
        return this.union(other).difference(this.intersection(other));
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.symmetric_difference_update = (function() {
    var ρσ_anonfunc = function (other) {
        var common;
        common = this.intersection(other);
        this.update(other);
        this.difference_update(common);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.union = (function() {
    var ρσ_anonfunc = function () {
        var ans;
        ans = ρσ_set(this);
        ans.update.apply(ans, arguments);
        return ans;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.update = (function() {
    var ρσ_anonfunc = function () {
        var s, iterator, r;
        s = this.jsset;
        for (var i=0; i < arguments.length; i++) {
            iterator = arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i][ρσ_iterator_symbol]();
            r = iterator.next();
            while (!r.done) {
                s.add(r.value);
                r = iterator.next();
            }
        }
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.toString = ρσ_set.prototype.__repr__ = ρσ_set.prototype.__str__ = ρσ_set.prototype.inspect = (function() {
    var ρσ_anonfunc = function () {
        return "{" + list(this).join(", ") + "}";
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_set.prototype.__eq__ = (function() {
    var ρσ_anonfunc = function (other) {
        var iterator, r;
        if (!other instanceof this.constructor) {
            return false;
        }
        if (other.size !== this.size) {
            return false;
        }
        if (other.size === 0) {
            return true;
        }
        iterator = other[ρσ_iterator_symbol]();
        r = iterator.next();
        while (!r.done) {
            if (!this.has(r.value)) {
                return false;
            }
            r = iterator.next();
        }
        return true;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
function ρσ_set_wrap(x) {
    var ans;
    ans = new ρσ_set;
    ans.jsset = x;
    return ans;
};
if (!ρσ_set_wrap.__argnames__) Object.defineProperties(ρσ_set_wrap, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

var set = ρσ_set, set_wrap = ρσ_set_wrap;
var ρσ_dict_implementation;
function ρσ_dict_polyfill() {
    this._store = {};
    this.size = 0;
};
if (!ρσ_dict_polyfill.__module__) Object.defineProperties(ρσ_dict_polyfill, {
    __module__ : {value: "__main__"}
});

ρσ_dict_polyfill.prototype.set = (function() {
    var ρσ_anonfunc = function (x, value) {
        var key;
        key = ρσ_set_keyfor(x);
        if (!Object.prototype.hasOwnProperty.call(this._store, key)) {
            this.size += 1;
        }
        (ρσ_expr_temp = this._store)[(typeof key === "number" && key < 0) ? ρσ_expr_temp.length + key : key] = [x, value];
        return this;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x", "value"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.clear = (function() {
    var ρσ_anonfunc = function (x) {
        this._store = {};
        this.size = 0;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.delete = (function() {
    var ρσ_anonfunc = function (x) {
        var key;
        key = ρσ_set_keyfor(x);
        if (Object.prototype.hasOwnProperty.call(this._store, key)) {
            this.size -= 1;
            delete this._store[key];
            return true;
        }
        return false;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.has = (function() {
    var ρσ_anonfunc = function (x) {
        return Object.prototype.hasOwnProperty.call(this._store, ρσ_set_keyfor(x));
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.get = (function() {
    var ρσ_anonfunc = function (x) {
        try {
            return (ρσ_expr_temp = this._store)[ρσ_bound_index(ρσ_set_keyfor(x), ρσ_expr_temp)][1];
        } catch (ρσ_Exception) {
            ρσ_last_exception = ρσ_Exception;
            if (ρσ_Exception instanceof TypeError) {
                return undefined;
            } else {
                throw ρσ_Exception;
            }
        }
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.values = (function() {
    var ρσ_anonfunc = function (x) {
        var ans;
        ans = {'_keys': Object.keys(this._store), '_i':-1, '_s':this._store};
        ans[ρσ_iterator_symbol] = (function() {
            var ρσ_anonfunc = function () {
                return this;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i >= this._keys.length) {
                    return {'done': true};
                }
                return {'done':false, 'value':this._s[this._keys[this._i]][1]};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.keys = (function() {
    var ρσ_anonfunc = function (x) {
        var ans;
        ans = {'_keys': Object.keys(this._store), '_i':-1, '_s':this._store};
        ans[ρσ_iterator_symbol] = (function() {
            var ρσ_anonfunc = function () {
                return this;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i >= this._keys.length) {
                    return {'done': true};
                }
                return {'done':false, 'value':this._s[this._keys[this._i]][0]};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict_polyfill.prototype.entries = (function() {
    var ρσ_anonfunc = function (x) {
        var ans;
        ans = {'_keys': Object.keys(this._store), '_i':-1, '_s':this._store};
        ans[ρσ_iterator_symbol] = (function() {
            var ρσ_anonfunc = function () {
                return this;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        ans["next"] = (function() {
            var ρσ_anonfunc = function () {
                this._i += 1;
                if (this._i >= this._keys.length) {
                    return {'done': true};
                }
                return {'done':false, 'value':this._s[this._keys[this._i]]};
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
if (typeof Map !== "function" || typeof Map.prototype.delete !== "function") {
    ρσ_dict_implementation = ρσ_dict_polyfill;
} else {
    ρσ_dict_implementation = Map;
}
function ρσ_dict() {
    var iterable = ( 0 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true) ? undefined : arguments[0];
    var kw = arguments[arguments.length-1];
    if (kw === null || typeof kw !== "object" || kw [ρσ_kwargs_symbol] !== true) kw = {};
    if (this instanceof ρσ_dict) {
        this.jsmap = new ρσ_dict_implementation;
        if (iterable !== undefined) {
            this.update(iterable);
        }
        this.update(kw);
        return this;
    } else {
        return ρσ_interpolate_kwargs_constructor.call(Object.create(ρσ_dict.prototype), false, ρσ_dict, [iterable].concat([ρσ_desugar_kwargs(kw)]));
    }
};
if (!ρσ_dict.__handles_kwarg_interpolation__) Object.defineProperties(ρσ_dict, {
    __handles_kwarg_interpolation__ : {value: true},
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

ρσ_dict.prototype.__name__ = "dict";
Object.defineProperties(ρσ_dict.prototype, (function(){
    var ρσ_d = {};
    ρσ_d["length"] = (function(){
        var ρσ_d = {};
        ρσ_d["get"] = (function() {
            var ρσ_anonfunc = function () {
                return this.jsmap.size;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ρσ_d;
    }).call(this);
    ρσ_d["size"] = (function(){
        var ρσ_d = {};
        ρσ_d["get"] = (function() {
            var ρσ_anonfunc = function () {
                return this.jsmap.size;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
        return ρσ_d;
    }).call(this);
    return ρσ_d;
}).call(this));
ρσ_dict.prototype.__len__ = (function() {
    var ρσ_anonfunc = function () {
        return this.jsmap.size;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.has = ρσ_dict.prototype.__contains__ = (function() {
    var ρσ_anonfunc = function (x) {
        return this.jsmap.has(x);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["x"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.set = ρσ_dict.prototype.__setitem__ = (function() {
    var ρσ_anonfunc = function (key, value) {
        this.jsmap.set(key, value);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["key", "value"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.__delitem__ = (function() {
    var ρσ_anonfunc = function (key) {
        this.jsmap.delete(key);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["key"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.clear = (function() {
    var ρσ_anonfunc = function () {
        this.jsmap.clear();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.copy = (function() {
    var ρσ_anonfunc = function () {
        return ρσ_dict(this);
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.keys = (function() {
    var ρσ_anonfunc = function () {
        return this.jsmap.keys();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.values = (function() {
    var ρσ_anonfunc = function () {
        return this.jsmap.values();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.items = ρσ_dict.prototype.entries = (function() {
    var ρσ_anonfunc = function () {
        return this.jsmap.entries();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype[ρσ_iterator_symbol] = (function() {
    var ρσ_anonfunc = function () {
        return this.jsmap.keys();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.__getitem__ = (function() {
    var ρσ_anonfunc = function (key) {
        var ans;
        ans = this.jsmap.get(key);
        if (ans === undefined && !this.jsmap.has(key)) {
            throw new KeyError(key + "");
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["key"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.get = (function() {
    var ρσ_anonfunc = function (key, defval) {
        var ans;
        ans = this.jsmap.get(key);
        if (ans === undefined && !this.jsmap.has(key)) {
            return (defval === undefined) ? null : defval;
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["key", "defval"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.set_default = (function() {
    var ρσ_anonfunc = function (key, defval) {
        var j;
        j = this.jsmap;
        if (!j.has(key)) {
            j.set(key, defval);
            return defval;
        }
        return j.get(key);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["key", "defval"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.fromkeys = ρσ_dict.prototype.fromkeys = (function() {
    var ρσ_anonfunc = function () {
        var iterable = ( 0 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true) ? undefined : arguments[0];
        var value = (arguments[1] === undefined || ( 1 === arguments.length-1 && arguments[arguments.length-1] !== null && typeof arguments[arguments.length-1] === "object" && arguments[arguments.length-1] [ρσ_kwargs_symbol] === true)) ? ρσ_anonfunc.__defaults__.value : arguments[1];
        var ρσ_kwargs_obj = arguments[arguments.length-1];
        if (ρσ_kwargs_obj === null || typeof ρσ_kwargs_obj !== "object" || ρσ_kwargs_obj [ρσ_kwargs_symbol] !== true) ρσ_kwargs_obj = {};
        if (Object.prototype.hasOwnProperty.call(ρσ_kwargs_obj, "value")){
            value = ρσ_kwargs_obj.value;
        }
        var ans, iterator, r;
        ans = ρσ_dict();
        iterator = iter(iterable);
        r = iterator.next();
        while (!r.done) {
            ans.set(r.value, value);
            r = iterator.next();
        }
        return ans;
    };
    if (!ρσ_anonfunc.__defaults__) Object.defineProperties(ρσ_anonfunc, {
        __defaults__ : {value: {value:null}},
        __handles_kwarg_interpolation__ : {value: true},
        __argnames__ : {value: ["iterable", "value"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.pop = (function() {
    var ρσ_anonfunc = function (key, defval) {
        var ans;
        ans = this.jsmap.get(key);
        if (ans === undefined && !this.jsmap.has(key)) {
            if (defval === undefined) {
                throw new KeyError(key);
            }
            return defval;
        }
        this.jsmap.delete(key);
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["key", "defval"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.popitem = (function() {
    var ρσ_anonfunc = function () {
        var r;
        r = this.jsmap.entries().next();
        if (r.done) {
            throw new KeyError("dict is empty");
        }
        this.jsmap.delete(r.value[0]);
        return r.value;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.update = (function() {
    var ρσ_anonfunc = function () {
        var m, iterable, iterator, result, keys;
        if (arguments.length === 0) {
            return;
        }
        m = this.jsmap;
        iterable = arguments[0];
        if (Array.isArray(iterable)) {
            for (var i = 0; i < iterable.length; i++) {
                m.set(iterable[(typeof i === "number" && i < 0) ? iterable.length + i : i][0], iterable[(typeof i === "number" && i < 0) ? iterable.length + i : i][1]);
            }
        } else if (iterable instanceof ρσ_dict) {
            iterator = iterable.items();
            result = iterator.next();
            while (!result.done) {
                m.set(result.value[0], result.value[1]);
                result = iterator.next();
            }
        } else if (typeof Map === "function" && iterable instanceof Map) {
            iterator = iterable.entries();
            result = iterator.next();
            while (!result.done) {
                m.set(result.value[0], result.value[1]);
                result = iterator.next();
            }
        } else if (typeof iterable[ρσ_iterator_symbol] === "function") {
            iterator = iterable[ρσ_iterator_symbol]();
            result = iterator.next();
            while (!result.done) {
                m.set(result.value[0], result.value[1]);
                result = iterator.next();
            }
        } else {
            keys = Object.keys(iterable);
            for (var j=0; j < keys.length; j++) {
                if (keys[(typeof j === "number" && j < 0) ? keys.length + j : j] !== ρσ_iterator_symbol) {
                    m.set(keys[(typeof j === "number" && j < 0) ? keys.length + j : j], iterable[ρσ_bound_index(keys[(typeof j === "number" && j < 0) ? keys.length + j : j], iterable)]);
                }
            }
        }
        if (arguments.length > 1) {
            ρσ_dict.prototype.update.call(this, arguments[1]);
        }
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.toString = ρσ_dict.prototype.inspect = ρσ_dict.prototype.__str__ = ρσ_dict.prototype.__repr__ = (function() {
    var ρσ_anonfunc = function () {
        var entries, iterator, r;
        entries = [];
        iterator = this.jsmap.entries();
        r = iterator.next();
        while (!r.done) {
            entries.push(ρσ_repr(r.value[0]) + ": " + ρσ_repr(r.value[1]));
            r = iterator.next();
        }
        return "{" + entries.join(", ") + "}";
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.__eq__ = (function() {
    var ρσ_anonfunc = function (other) {
        var iterator, r, x;
        if (!(other instanceof this.constructor)) {
            return false;
        }
        if (other.size !== this.size) {
            return false;
        }
        if (other.size === 0) {
            return true;
        }
        iterator = other.items();
        r = iterator.next();
        while (!r.done) {
            x = this.jsmap.get(r.value[0]);
            if (x === undefined && !this.jsmap.has(r.value[0]) || x !== r.value[1]) {
                return false;
            }
            r = iterator.next();
        }
        return true;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_dict.prototype.as_object = (function() {
    var ρσ_anonfunc = function (other) {
        var ans, iterator, r;
        ans = {};
        iterator = this.jsmap.entries();
        r = iterator.next();
        while (!r.done) {
            ans[ρσ_bound_index(r.value[0], ans)] = r.value[1];
            r = iterator.next();
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["other"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
function ρσ_dict_wrap(x) {
    var ans;
    ans = new ρσ_dict;
    ans.jsmap = x;
    return ans;
};
if (!ρσ_dict_wrap.__argnames__) Object.defineProperties(ρσ_dict_wrap, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

var dict = ρσ_dict, dict_wrap = ρσ_dict_wrap;// }}}
var NameError;
NameError = ReferenceError;
function Exception() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    Exception.prototype.__init__.apply(this, arguments);
}
ρσ_extends(Exception, Error);
Exception.prototype.__init__ = function __init__(message) {
    var self = this;
    self.message = message;
    self.stack = (new Error).stack;
    self.name = self.constructor.name;
};
if (!Exception.prototype.__init__.__argnames__) Object.defineProperties(Exception.prototype.__init__, {
    __argnames__ : {value: ["message"]},
    __module__ : {value: "__main__"}
});
Exception.__argnames__ = Exception.prototype.__init__.__argnames__;
Exception.__handles_kwarg_interpolation__ = Exception.prototype.__init__.__handles_kwarg_interpolation__;
Exception.prototype.__repr__ = function __repr__() {
    var self = this;
    return self.name + ": " + self.message;
};
if (!Exception.prototype.__repr__.__module__) Object.defineProperties(Exception.prototype.__repr__, {
    __module__ : {value: "__main__"}
});
Exception.prototype.__str__ = function __str__ () {
    if(Error.prototype.__str__) return Error.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(Exception.prototype, "__bases__", {value: [Error]});

function AttributeError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    AttributeError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(AttributeError, Exception);
AttributeError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
AttributeError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
AttributeError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(AttributeError.prototype, "__bases__", {value: [Exception]});


function IndexError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    IndexError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(IndexError, Exception);
IndexError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
IndexError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
IndexError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(IndexError.prototype, "__bases__", {value: [Exception]});


function KeyError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    KeyError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(KeyError, Exception);
KeyError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
KeyError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
KeyError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(KeyError.prototype, "__bases__", {value: [Exception]});


function ValueError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    ValueError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(ValueError, Exception);
ValueError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
ValueError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
ValueError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(ValueError.prototype, "__bases__", {value: [Exception]});


function UnicodeDecodeError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    UnicodeDecodeError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(UnicodeDecodeError, Exception);
UnicodeDecodeError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
UnicodeDecodeError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
UnicodeDecodeError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(UnicodeDecodeError.prototype, "__bases__", {value: [Exception]});


function AssertionError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    AssertionError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(AssertionError, Exception);
AssertionError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
AssertionError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
AssertionError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(AssertionError.prototype, "__bases__", {value: [Exception]});


function ZeroDivisionError() {
    if (this.ρσ_object_id === undefined) Object.defineProperty(this, "ρσ_object_id", {"value":++ρσ_object_counter});
    ZeroDivisionError.prototype.__init__.apply(this, arguments);
}
ρσ_extends(ZeroDivisionError, Exception);
ZeroDivisionError.prototype.__init__ = function __init__ () {
    Exception.prototype.__init__ && Exception.prototype.__init__.apply(this, arguments);
};
ZeroDivisionError.prototype.__repr__ = function __repr__ () {
    if(Exception.prototype.__repr__) return Exception.prototype.__repr__.call(this);
    return "<" + __name__ + "." + this.constructor.name + " #" + this.ρσ_object_id + ">";
};
ZeroDivisionError.prototype.__str__ = function __str__ () {
    if(Exception.prototype.__str__) return Exception.prototype.__str__.call(this);
return this.__repr__();
};
Object.defineProperty(ZeroDivisionError.prototype, "__bases__", {value: [Exception]});

var ρσ_in, ρσ_desugar_kwargs, ρσ_exists;
function ρσ_eslice(arr, step, start, end) {
    var is_string;
    if (typeof arr === "string" || arr instanceof String) {
        is_string = true;
        arr = arr.split("");
    }
    if (step < 0) {
        step = -step;
        arr = arr.slice().reverse();
        if (typeof start !== "undefined") {
            start = arr.length - start - 1;
        }
        if (typeof end !== "undefined") {
            end = arr.length - end - 1;
        }
    }
    if (typeof start === "undefined") {
        start = 0;
    }
    if (typeof end === "undefined") {
        end = arr.length;
    }
    arr = arr.slice(start, end).filter((function() {
        var ρσ_anonfunc = function (e, i) {
            return i % step === 0;
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["e", "i"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })());
    if (is_string) {
        arr = arr.join("");
    }
    return arr;
};
if (!ρσ_eslice.__argnames__) Object.defineProperties(ρσ_eslice, {
    __argnames__ : {value: ["arr", "step", "start", "end"]},
    __module__ : {value: "__main__"}
});

function ρσ_delslice(arr, step, start, end) {
    var is_string, ρσ_unpack, indices;
    if (typeof arr === "string" || arr instanceof String) {
        is_string = true;
        arr = arr.split("");
    }
    if (step < 0) {
        if (typeof start === "undefined") {
            start = arr.length;
        }
        if (typeof end === "undefined") {
            end = 0;
        }
        ρσ_unpack = [end, start, -step];
        start = ρσ_unpack[0];
        end = ρσ_unpack[1];
        step = ρσ_unpack[2];
    }
    if (typeof start === "undefined") {
        start = 0;
    }
    if (typeof end === "undefined") {
        end = arr.length;
    }
    if (step === 1) {
        arr.splice(start, end - start);
    } else {
        if (end > start) {
            indices = [];
            for (var i = start; i < end; i += step) {
                indices.push(i);
            }
            for (var i = indices.length - 1; i >= 0; i--) {
                arr.splice(indices[(typeof i === "number" && i < 0) ? indices.length + i : i], 1);
            }
        }
    }
    if (is_string) {
        arr = arr.join("");
    }
    return arr;
};
if (!ρσ_delslice.__argnames__) Object.defineProperties(ρσ_delslice, {
    __argnames__ : {value: ["arr", "step", "start", "end"]},
    __module__ : {value: "__main__"}
});

function ρσ_flatten(arr) {
    var ans, value;
    ans = ρσ_list_decorate([]);
    for (var i=0; i < arr.length; i++) {
        value = arr[(typeof i === "number" && i < 0) ? arr.length + i : i];
        if (Array.isArray(value)) {
            ans = ans.concat(ρσ_flatten(value));
        } else {
            ans.push(value);
        }
    }
    return ans;
};
if (!ρσ_flatten.__argnames__) Object.defineProperties(ρσ_flatten, {
    __argnames__ : {value: ["arr"]},
    __module__ : {value: "__main__"}
});

function ρσ_unpack_asarray(num, iterable) {
    var ans, iterator, result;
    if (ρσ_arraylike(iterable)) {
        return iterable;
    }
    ans = [];
    if (typeof iterable[ρσ_iterator_symbol] === "function") {
        iterator = (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
        result = iterator.next();
        while (!result.done && ans.length < num) {
            ans.push(result.value);
            result = iterator.next();
        }
    }
    return ans;
};
if (!ρσ_unpack_asarray.__argnames__) Object.defineProperties(ρσ_unpack_asarray, {
    __argnames__ : {value: ["num", "iterable"]},
    __module__ : {value: "__main__"}
});

function ρσ_extends(child, parent) {
    child.prototype = Object.create(parent.prototype);
    child.prototype.constructor = child;
};
if (!ρσ_extends.__argnames__) Object.defineProperties(ρσ_extends, {
    __argnames__ : {value: ["child", "parent"]},
    __module__ : {value: "__main__"}
});

ρσ_in = (function() {
    var ρσ_anonfunc = function () {
        if (typeof Map === "function" && typeof Set === "function") {
            return (function() {
                var ρσ_anonfunc = function (val, arr) {
                    if (typeof arr === "string") {
                        return arr.indexOf(val) !== -1;
                    }
                    if (typeof arr.__contains__ === "function") {
                        return arr.__contains__(val);
                    }
                    if (arr instanceof Map || arr instanceof Set) {
                        return arr.has(val);
                    }
                    if (ρσ_arraylike(arr)) {
                        return ρσ_list_contains.call(arr, val);
                    }
                    return Object.prototype.hasOwnProperty.call(arr, val);
                };
                if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                    __argnames__ : {value: ["val", "arr"]},
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
        }
        return (function() {
            var ρσ_anonfunc = function (val, arr) {
                if (typeof arr === "string") {
                    return arr.indexOf(val) !== -1;
                }
                if (typeof arr.__contains__ === "function") {
                    return arr.__contains__(val);
                }
                if (ρσ_arraylike(arr)) {
                    return ρσ_list_contains.call(arr, val);
                }
                return Object.prototype.hasOwnProperty.call(arr, val);
            };
            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                __argnames__ : {value: ["val", "arr"]},
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})()();
function ρσ_Iterable(iterable) {
    var iterator, ans, result;
    if (ρσ_arraylike(iterable)) {
        return iterable;
    }
    if (typeof iterable[ρσ_iterator_symbol] === "function") {
        iterator = (typeof Map === "function" && iterable instanceof Map) ? iterable.keys() : iterable[ρσ_iterator_symbol]();
        ans = ρσ_list_decorate([]);
        result = iterator.next();
        while (!result.done) {
            ans.push(result.value);
            result = iterator.next();
        }
        return ans;
    }
    return Object.keys(iterable);
};
if (!ρσ_Iterable.__argnames__) Object.defineProperties(ρσ_Iterable, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

ρσ_desugar_kwargs = (function() {
    var ρσ_anonfunc = function () {
        if (typeof Object.assign === "function") {
            return (function() {
                var ρσ_anonfunc = function () {
                    var ans;
                    ans = Object.create(null);
                    ans[ρσ_kwargs_symbol] = true;
                    for (var i = 0; i < arguments.length; i++) {
                        Object.assign(ans, arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i]);
                    }
                    return ans;
                };
                if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
        }
        return (function() {
            var ρσ_anonfunc = function () {
                var ans, keys;
                ans = Object.create(null);
                ans[ρσ_kwargs_symbol] = true;
                for (var i = 0; i < arguments.length; i++) {
                    keys = Object.keys(arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i]);
                    for (var j = 0; j < keys.length; j++) {
                        ans[ρσ_bound_index(keys[(typeof j === "number" && j < 0) ? keys.length + j : j], ans)] = (ρσ_expr_temp = arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i])[ρσ_bound_index(keys[(typeof j === "number" && j < 0) ? keys.length + j : j], ρσ_expr_temp)];
                    }
                }
                return ans;
            };
            if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})()();
function ρσ_interpolate_kwargs(f, supplied_args) {
    var has_prop, kwobj, args, prop;
    if (!f.__argnames__) {
        return f.apply(this, supplied_args);
    }
    has_prop = Object.prototype.hasOwnProperty;
    kwobj = supplied_args.pop();
    if (f.__handles_kwarg_interpolation__) {
        args = new Array(Math.max(supplied_args.length, f.__argnames__.length) + 1);
        args[args.length-1] = kwobj;
        for (var i = 0; i < args.length - 1; i++) {
            if (i < f.__argnames__.length) {
                prop = (ρσ_expr_temp = f.__argnames__)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i];
                if (has_prop.call(kwobj, prop)) {
                    args[(typeof i === "number" && i < 0) ? args.length + i : i] = kwobj[(typeof prop === "number" && prop < 0) ? kwobj.length + prop : prop];
                    delete kwobj[prop];
                } else if (i < supplied_args.length) {
                    args[(typeof i === "number" && i < 0) ? args.length + i : i] = supplied_args[(typeof i === "number" && i < 0) ? supplied_args.length + i : i];
                }
            } else {
                args[(typeof i === "number" && i < 0) ? args.length + i : i] = supplied_args[(typeof i === "number" && i < 0) ? supplied_args.length + i : i];
            }
        }
        return f.apply(this, args);
    }
    for (var i = 0; i < f.__argnames__.length; i++) {
        prop = (ρσ_expr_temp = f.__argnames__)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i];
        if (has_prop.call(kwobj, prop)) {
            supplied_args[(typeof i === "number" && i < 0) ? supplied_args.length + i : i] = kwobj[(typeof prop === "number" && prop < 0) ? kwobj.length + prop : prop];
        }
    }
    return f.apply(this, supplied_args);
};
if (!ρσ_interpolate_kwargs.__argnames__) Object.defineProperties(ρσ_interpolate_kwargs, {
    __argnames__ : {value: ["f", "supplied_args"]},
    __module__ : {value: "__main__"}
});

function ρσ_interpolate_kwargs_constructor(apply, f, supplied_args) {
    if (apply) {
        f.apply(this, supplied_args);
    } else {
        ρσ_interpolate_kwargs.call(this, f, supplied_args);
    }
    return this;
};
if (!ρσ_interpolate_kwargs_constructor.__argnames__) Object.defineProperties(ρσ_interpolate_kwargs_constructor, {
    __argnames__ : {value: ["apply", "f", "supplied_args"]},
    __module__ : {value: "__main__"}
});

function ρσ_getitem(obj, key) {
    if (obj.__getitem__) {
        return obj.__getitem__(key);
    }
    if (typeof key === "number" && key < 0) {
        key += obj.length;
    }
    return obj[(typeof key === "number" && key < 0) ? obj.length + key : key];
};
if (!ρσ_getitem.__argnames__) Object.defineProperties(ρσ_getitem, {
    __argnames__ : {value: ["obj", "key"]},
    __module__ : {value: "__main__"}
});

function ρσ_setitem(obj, key, val) {
    if (obj.__setitem__) {
        obj.__setitem__(key, val);
    } else {
        if (typeof key === "number" && key < 0) {
            key += obj.length;
        }
        obj[(typeof key === "number" && key < 0) ? obj.length + key : key] = val;
    }
};
if (!ρσ_setitem.__argnames__) Object.defineProperties(ρσ_setitem, {
    __argnames__ : {value: ["obj", "key", "val"]},
    __module__ : {value: "__main__"}
});

function ρσ_delitem(obj, key) {
    if (obj.__delitem__) {
        obj.__delitem__(key);
    } else if (typeof obj.splice === "function") {
        obj.splice(key, 1);
    } else {
        if (typeof key === "number" && key < 0) {
            key += obj.length;
        }
        delete obj[key];
    }
};
if (!ρσ_delitem.__argnames__) Object.defineProperties(ρσ_delitem, {
    __argnames__ : {value: ["obj", "key"]},
    __module__ : {value: "__main__"}
});

function ρσ_bound_index(idx, arr) {
    if (typeof idx === "number" && idx < 0) {
        idx += arr.length;
    }
    return idx;
};
if (!ρσ_bound_index.__argnames__) Object.defineProperties(ρσ_bound_index, {
    __argnames__ : {value: ["idx", "arr"]},
    __module__ : {value: "__main__"}
});

function ρσ_splice(arr, val, start, end) {
    start = start || 0;
    if (start < 0) {
        start += arr.length;
    }
    if (end === undefined) {
        end = arr.length;
    }
    if (end < 0) {
        end += arr.length;
    }
    Array.prototype.splice.apply(arr, [start, end - start].concat(val));
};
if (!ρσ_splice.__argnames__) Object.defineProperties(ρσ_splice, {
    __argnames__ : {value: ["arr", "val", "start", "end"]},
    __module__ : {value: "__main__"}
});

ρσ_exists = (function(){
    var ρσ_d = {};
    ρσ_d["n"] = (function() {
        var ρσ_anonfunc = function (expr) {
            return expr !== undefined && expr !== null;
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["expr"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ρσ_d["d"] = (function() {
        var ρσ_anonfunc = function (expr) {
            if (expr === undefined || expr === null) {
                return Object.create(null);
            }
            return expr;
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["expr"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ρσ_d["c"] = (function() {
        var ρσ_anonfunc = function (expr) {
            if (typeof expr === "function") {
                return expr;
            }
            return (function() {
                var ρσ_anonfunc = function () {
                    return undefined;
                };
                if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["expr"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ρσ_d["g"] = (function() {
        var ρσ_anonfunc = function (expr) {
            if (expr === undefined || expr === null || typeof expr.__getitem__ !== "function") {
                return (function(){
                    var ρσ_d = {};
                    ρσ_d["__getitem__"] = (function() {
                        var ρσ_anonfunc = function () {
                            return undefined;
                        };
                        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                            __module__ : {value: "__main__"}
                        });
                        return ρσ_anonfunc;
                    })();
                    return ρσ_d;
                }).call(this);
            }
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["expr"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ρσ_d["e"] = (function() {
        var ρσ_anonfunc = function (expr, alt) {
            return (expr === undefined || expr === null) ? alt : expr;
        };
        if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
            __argnames__ : {value: ["expr", "alt"]},
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    return ρσ_d;
}).call(this);
function ρσ_mixin() {
    var seen, resolved_props, p, target, props, name;
    seen = Object.create(null);
    seen.__argnames__ = seen.__handles_kwarg_interpolation__ = seen.__init__ = seen.__annotations__ = seen.__doc__ = seen.__bind_methods__ = seen.__bases__ = seen.constructor = seen.__class__ = true;
    resolved_props = {};
    p = target = arguments[0].prototype;
    while (p && p !== Object.prototype) {
        props = Object.getOwnPropertyNames(p);
        for (var i = 0; i < props.length; i++) {
            seen[ρσ_bound_index(props[(typeof i === "number" && i < 0) ? props.length + i : i], seen)] = true;
        }
        p = Object.getPrototypeOf(p);
    }
    for (var c = 1; c < arguments.length; c++) {
        p = arguments[(typeof c === "number" && c < 0) ? arguments.length + c : c].prototype;
        while (p && p !== Object.prototype) {
            props = Object.getOwnPropertyNames(p);
            for (var i = 0; i < props.length; i++) {
                name = props[(typeof i === "number" && i < 0) ? props.length + i : i];
                if (seen[(typeof name === "number" && name < 0) ? seen.length + name : name]) {
                    continue;
                }
                seen[(typeof name === "number" && name < 0) ? seen.length + name : name] = true;
                resolved_props[(typeof name === "number" && name < 0) ? resolved_props.length + name : name] = Object.getOwnPropertyDescriptor(p, name);
            }
            p = Object.getPrototypeOf(p);
        }
    }
    Object.defineProperties(target, resolved_props);
};
if (!ρσ_mixin.__module__) Object.defineProperties(ρσ_mixin, {
    __module__ : {value: "__main__"}
});

function ρσ_instanceof() {
    var obj, bases, q, cls, p;
    obj = arguments[0];
    bases = "";
    if (obj && obj.constructor && obj.constructor.prototype) {
        bases = obj.constructor.prototype.__bases__ || "";
    }
    for (var i = 1; i < arguments.length; i++) {
        q = arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i];
        if (obj instanceof q) {
            return true;
        }
        if ((q === Array || q === ρσ_list_constructor) && Array.isArray(obj)) {
            return true;
        }
        if (q === ρσ_str && (typeof obj === "string" || obj instanceof String)) {
            return true;
        }
        if (q === ρσ_int && typeof obj === "number" && Number.isInteger(obj)) {
            return true;
        }
        if (q === ρσ_float && typeof obj === "number" && !Number.isInteger(obj)) {
            return true;
        }
        if (bases.length > 1) {
            for (var c = 1; c < bases.length; c++) {
                cls = bases[(typeof c === "number" && c < 0) ? bases.length + c : c];
                while (cls) {
                    if (q === cls) {
                        return true;
                    }
                    p = Object.getPrototypeOf(cls.prototype);
                    if (!p) {
                        break;
                    }
                    cls = p.constructor;
                }
            }
        }
    }
    return false;
};
if (!ρσ_instanceof.__module__) Object.defineProperties(ρσ_instanceof, {
    __module__ : {value: "__main__"}
});
function sum(iterable, start) {
    var ans, iterator, r;
    if (Array.isArray(iterable)) {
        return iterable.reduce((function() {
            var ρσ_anonfunc = function (prev, cur) {
                return prev + cur;
            };
            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                __argnames__ : {value: ["prev", "cur"]},
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })(), start || 0);
    }
    ans = start || 0;
    iterator = iter(iterable);
    r = iterator.next();
    while (!r.done) {
        ans += r.value;
        r = iterator.next();
    }
    return ans;
};
if (!sum.__argnames__) Object.defineProperties(sum, {
    __argnames__ : {value: ["iterable", "start"]},
    __module__ : {value: "__main__"}
});

function map() {
    var iterators, func, args, ans;
    iterators = new Array(arguments.length - 1);
    func = arguments[0];
    args = new Array(arguments.length - 1);
    for (var i = 1; i < arguments.length; i++) {
        iterators[ρσ_bound_index(i - 1, iterators)] = iter(arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i]);
    }
    ans = {'_func':func, '_iterators':iterators, '_args':args};
    ans[ρσ_iterator_symbol] = (function() {
        var ρσ_anonfunc = function () {
            return this;
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ans["next"] = (function() {
        var ρσ_anonfunc = function () {
            var r;
            for (var i = 0; i < this._iterators.length; i++) {
                r = (ρσ_expr_temp = this._iterators)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i].next();
                if (r.done) {
                    return {'done':true};
                }
                (ρσ_expr_temp = this._args)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i] = r.value;
            }
            return {'done':false, 'value':this._func.apply(undefined, this._args)};
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    return ans;
};
if (!map.__module__) Object.defineProperties(map, {
    __module__ : {value: "__main__"}
});

function filter(func_or_none, iterable) {
    var func, ans;
    func = (func_or_none === null) ? ρσ_bool : func_or_none;
    ans = {'_func':func, '_iterator':ρσ_iter(iterable)};
    ans[ρσ_iterator_symbol] = (function() {
        var ρσ_anonfunc = function () {
            return this;
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ans["next"] = (function() {
        var ρσ_anonfunc = function () {
            var r;
            r = this._iterator.next();
            while (!r.done) {
                if (this._func(r.value)) {
                    return r;
                }
                r = this._iterator.next();
            }
            return {'done':true};
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    return ans;
};
if (!filter.__argnames__) Object.defineProperties(filter, {
    __argnames__ : {value: ["func_or_none", "iterable"]},
    __module__ : {value: "__main__"}
});

function zip() {
    var iterators, ans;
    iterators = new Array(arguments.length);
    for (var i = 0; i < arguments.length; i++) {
        iterators[(typeof i === "number" && i < 0) ? iterators.length + i : i] = iter(arguments[(typeof i === "number" && i < 0) ? arguments.length + i : i]);
    }
    ans = {'_iterators':iterators};
    ans[ρσ_iterator_symbol] = (function() {
        var ρσ_anonfunc = function () {
            return this;
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    ans["next"] = (function() {
        var ρσ_anonfunc = function () {
            var args, r;
            args = new Array(this._iterators.length);
            for (var i = 0; i < this._iterators.length; i++) {
                r = (ρσ_expr_temp = this._iterators)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i].next();
                if (r.done) {
                    return {'done':true};
                }
                args[(typeof i === "number" && i < 0) ? args.length + i : i] = r.value;
            }
            return {'done':false, 'value':args};
        };
        if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
            __module__ : {value: "__main__"}
        });
        return ρσ_anonfunc;
    })();
    return ans;
};
if (!zip.__module__) Object.defineProperties(zip, {
    __module__ : {value: "__main__"}
});

function any(iterable) {
    var i;
    var ρσ_Iter0 = ρσ_Iterable(iterable);
    for (var ρσ_Index0 = 0; ρσ_Index0 < ρσ_Iter0.length; ρσ_Index0++) {
        i = ρσ_Iter0[ρσ_Index0];
        if (i) {
            return true;
        }
    }
    return false;
};
if (!any.__argnames__) Object.defineProperties(any, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});

function all(iterable) {
    var i;
    var ρσ_Iter1 = ρσ_Iterable(iterable);
    for (var ρσ_Index1 = 0; ρσ_Index1 < ρσ_Iter1.length; ρσ_Index1++) {
        i = ρσ_Iter1[ρσ_Index1];
        if (!i) {
            return false;
        }
    }
    return true;
};
if (!all.__argnames__) Object.defineProperties(all, {
    __argnames__ : {value: ["iterable"]},
    __module__ : {value: "__main__"}
});
var decimal_sep, define_str_func, ρσ_unpack, ρσ_orig_split, ρσ_orig_replace;
decimal_sep = 1.1.toLocaleString()[1];
function ρσ_repr_js_builtin(x, as_array) {
    var ans, b, keys, key;
    ans = [];
    b = "{}";
    if (as_array) {
        b = "[]";
        for (var i = 0; i < x.length; i++) {
            ans.push(ρσ_repr(x[(typeof i === "number" && i < 0) ? x.length + i : i]));
        }
    } else {
        keys = Object.keys(x);
        for (var k = 0; k < keys.length; k++) {
            key = keys[(typeof k === "number" && k < 0) ? keys.length + k : k];
            ans.push(JSON.stringify(key) + ":" + ρσ_repr(x[(typeof key === "number" && key < 0) ? x.length + key : key]));
        }
    }
    return b[0] + ans.join(", ") + b[1];
};
if (!ρσ_repr_js_builtin.__argnames__) Object.defineProperties(ρσ_repr_js_builtin, {
    __argnames__ : {value: ["x", "as_array"]},
    __module__ : {value: "__main__"}
});

function ρσ_html_element_to_string(elem) {
    var attrs, val, attr, ans;
    attrs = [];
    var ρσ_Iter0 = ρσ_Iterable(elem.attributes);
    for (var ρσ_Index0 = 0; ρσ_Index0 < ρσ_Iter0.length; ρσ_Index0++) {
        attr = ρσ_Iter0[ρσ_Index0];
        if (attr.specified) {
            val = attr.value;
            if (val.length > 10) {
                val = val.slice(0, 15) + "...";
            }
            val = JSON.stringify(val);
            attrs.push("" + ρσ_str.format("{}", attr.name) + "=" + ρσ_str.format("{}", val) + "");
        }
    }
    attrs = (attrs.length) ? " " + attrs.join(" ") : "";
    ans = "<" + ρσ_str.format("{}", elem.tagName) + "" + ρσ_str.format("{}", attrs) + ">";
    return ans;
};
if (!ρσ_html_element_to_string.__argnames__) Object.defineProperties(ρσ_html_element_to_string, {
    __argnames__ : {value: ["elem"]},
    __module__ : {value: "__main__"}
});

function ρσ_repr(x) {
    var ans, name;
    if (x === null) {
        return "None";
    }
    if (x === undefined) {
        return "undefined";
    }
    ans = x;
    if (typeof x.__repr__ === "function") {
        ans = x.__repr__();
    } else if (x === true || x === false) {
        ans = (x) ? "True" : "False";
    } else if (Array.isArray(x)) {
        ans = ρσ_repr_js_builtin(x, true);
    } else if (typeof x === "function") {
        ans = x.toString();
    } else if (typeof x === "object" && !x.toString) {
        ans = ρσ_repr_js_builtin(x);
    } else {
        name = Object.prototype.toString.call(x).slice(8, -1);
        if (ρσ_not_equals("Int8Array Uint8Array Uint8ClampedArray Int16Array Uint16Array Int32Array Uint32Array Float32Array Float64Array".indexOf(name), -1)) {
            return name + "([" + x.map((function() {
                var ρσ_anonfunc = function (i) {
                    return str.format("0x{:02x}", i);
                };
                if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                    __argnames__ : {value: ["i"]},
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })()).join(", ") + "])";
        }
        if (typeof HTMLElement !== "undefined" && x instanceof HTMLElement) {
            ans = ρσ_html_element_to_string(x);
        } else {
            ans = (typeof x.toString === "function") ? x.toString() : x;
        }
        if (ans === "[object Object]") {
            return ρσ_repr_js_builtin(x);
        }
        try {
            ans = JSON.stringify(x);
        } catch (ρσ_Exception) {
            ρσ_last_exception = ρσ_Exception;
            {
            } 
        }
    }
    return ans + "";
};
if (!ρσ_repr.__argnames__) Object.defineProperties(ρσ_repr, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

function ρσ_str(x) {
    var ans, name;
    if (x === null) {
        return "None";
    }
    if (x === undefined) {
        return "undefined";
    }
    ans = x;
    if (typeof x.__str__ === "function") {
        ans = x.__str__();
    } else if (typeof x.__repr__ === "function") {
        ans = x.__repr__();
    } else if (x === true || x === false) {
        ans = (x) ? "True" : "False";
    } else if (Array.isArray(x)) {
        ans = ρσ_repr_js_builtin(x, true);
    } else if (typeof x.toString === "function") {
        name = Object.prototype.toString.call(x).slice(8, -1);
        if (ρσ_not_equals("Int8Array Uint8Array Uint8ClampedArray Int16Array Uint16Array Int32Array Uint32Array Float32Array Float64Array".indexOf(name), -1)) {
            return name + "([" + x.map((function() {
                var ρσ_anonfunc = function (i) {
                    return str.format("0x{:02x}", i);
                };
                if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                    __argnames__ : {value: ["i"]},
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })()).join(", ") + "])";
        }
        if (typeof HTMLElement !== "undefined" && x instanceof HTMLElement) {
            ans = ρσ_html_element_to_string(x);
        } else {
            ans = x.toString();
        }
        if (ans === "[object Object]") {
            ans = ρσ_repr_js_builtin(x);
        }
    } else if (typeof x === "object" && !x.toString) {
        ans = ρσ_repr_js_builtin(x);
    }
    return ans + "";
};
if (!ρσ_str.__argnames__) Object.defineProperties(ρσ_str, {
    __argnames__ : {value: ["x"]},
    __module__ : {value: "__main__"}
});

define_str_func = (function() {
    var ρσ_anonfunc = function (name, func) {
        var f;
        (ρσ_expr_temp = ρσ_str.prototype)[(typeof name === "number" && name < 0) ? ρσ_expr_temp.length + name : name] = func;
        ρσ_str[(typeof name === "number" && name < 0) ? ρσ_str.length + name : name] = f = func.call.bind(func);
        if (func.__argnames__) {
            Object.defineProperty(f, "__argnames__", (function(){
                var ρσ_d = {};
                ρσ_d["value"] = ['string'].concat(func.__argnames__);
                return ρσ_d;
            }).call(this));
        }
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["name", "func"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_unpack = [String.prototype.split.call.bind(String.prototype.split), String.prototype.replace.call.bind(String.prototype.replace)];
ρσ_orig_split = ρσ_unpack[0];
ρσ_orig_replace = ρσ_unpack[1];
define_str_func("format", (function() {
    var ρσ_anonfunc = function () {
        var template, args, kwargs, explicit, implicit, idx, split, ans, pos, in_brace, markup, ch;
        template = this;
        if (template === undefined) {
            throw new TypeError("Template is required");
        }
        args = Array.prototype.slice.call(arguments);
        kwargs = {};
        if (args[args.length-1] && args[args.length-1][ρσ_kwargs_symbol] !== undefined) {
            kwargs = args[args.length-1];
            args = args.slice(0, -1);
        }
        explicit = implicit = false;
        idx = 0;
        split = ρσ_orig_split;
        if (ρσ_str.format._template_resolve_pat === undefined) {
            ρσ_str.format._template_resolve_pat = /[.\[]/;
        }
        function resolve(arg, object) {
            var ρσ_unpack, first, key, rest, ans;
            if (!arg) {
                return object;
            }
            ρσ_unpack = [arg[0], arg.slice(1)];
            first = ρσ_unpack[0];
            arg = ρσ_unpack[1];
            key = split(arg, ρσ_str.format._template_resolve_pat, 1)[0];
            rest = arg.slice(key.length);
            ans = (first === "[") ? object[ρσ_bound_index(key.slice(0, -1), object)] : getattr(object, key);
            if (ans === undefined) {
                throw new KeyError((first === "[") ? key.slice(0, -1) : key);
            }
            return resolve(rest, ans);
        };
        if (!resolve.__argnames__) Object.defineProperties(resolve, {
            __argnames__ : {value: ["arg", "object"]},
            __module__ : {value: "__main__"}
        });

        function resolve_format_spec(format_spec) {
            if (ρσ_str.format._template_resolve_fs_pat === undefined) {
                ρσ_str.format._template_resolve_fs_pat = /[{]([a-zA-Z0-9_]+)[}]/g;
            }
            return format_spec.replace(ρσ_str.format._template_resolve_fs_pat, (function() {
                var ρσ_anonfunc = function (match, key) {
                    if (!Object.prototype.hasOwnProperty.call(kwargs, key)) {
                        return "";
                    }
                    return "" + kwargs[(typeof key === "number" && key < 0) ? kwargs.length + key : key];
                };
                if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                    __argnames__ : {value: ["match", "key"]},
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })());
        };
        if (!resolve_format_spec.__argnames__) Object.defineProperties(resolve_format_spec, {
            __argnames__ : {value: ["format_spec"]},
            __module__ : {value: "__main__"}
        });

        function set_comma(ans, comma) {
            var sep;
            if (comma !== ",") {
                sep = 1234;
                sep = sep.toLocaleString(undefined, {useGrouping: true})[1];
                ans = str.replace(ans, sep, comma);
            }
            return ans;
        };
        if (!set_comma.__argnames__) Object.defineProperties(set_comma, {
            __argnames__ : {value: ["ans", "comma"]},
            __module__ : {value: "__main__"}
        });

        function safe_comma(value, comma) {
            try {
                return set_comma(value.toLocaleString(undefined, {useGrouping: true}), comma);
            } catch (ρσ_Exception) {
                ρσ_last_exception = ρσ_Exception;
                {
                    return value.toString(10);
                } 
            }
        };
        if (!safe_comma.__argnames__) Object.defineProperties(safe_comma, {
            __argnames__ : {value: ["value", "comma"]},
            __module__ : {value: "__main__"}
        });

        function safe_fixed(value, precision, comma) {
            if (!comma) {
                return value.toFixed(precision);
            }
            try {
                return set_comma(value.toLocaleString(undefined, {useGrouping: true, minimumFractionDigits: precision, maximumFractionDigits: precision}), comma);
            } catch (ρσ_Exception) {
                ρσ_last_exception = ρσ_Exception;
                {
                    return value.toFixed(precision);
                } 
            }
        };
        if (!safe_fixed.__argnames__) Object.defineProperties(safe_fixed, {
            __argnames__ : {value: ["value", "precision", "comma"]},
            __module__ : {value: "__main__"}
        });

        function apply_formatting(value, format_spec) {
            var ρσ_unpack, fill, align, sign, fhash, zeropad, width, comma, precision, ftype, is_numeric, is_int, lftype, code, prec, exp, nval, is_positive, left, right;
            if (format_spec.indexOf("{") !== -1) {
                format_spec = resolve_format_spec(format_spec);
            }
            if (ρσ_str.format._template_format_pat === undefined) {
                ρσ_str.format._template_format_pat = /([^{}](?=[<>=^]))?([<>=^])?([-+\x20])?(\#)?(0)?(\d+)?([,_])?(?:\.(\d+))?([bcdeEfFgGnosxX%])?/;
            }
            try {
                ρσ_unpack = format_spec.match(ρσ_str.format._template_format_pat).slice(1);
ρσ_unpack = ρσ_unpack_asarray(9, ρσ_unpack);
                fill = ρσ_unpack[0];
                align = ρσ_unpack[1];
                sign = ρσ_unpack[2];
                fhash = ρσ_unpack[3];
                zeropad = ρσ_unpack[4];
                width = ρσ_unpack[5];
                comma = ρσ_unpack[6];
                precision = ρσ_unpack[7];
                ftype = ρσ_unpack[8];
            } catch (ρσ_Exception) {
                ρσ_last_exception = ρσ_Exception;
                if (ρσ_Exception instanceof TypeError) {
                    return value;
                } else {
                    throw ρσ_Exception;
                }
            }
            if (zeropad) {
                fill = fill || "0";
                align = align || "=";
            } else {
                fill = fill || " ";
                align = align || ">";
            }
            is_numeric = Number(value) === value;
            is_int = is_numeric && value % 1 === 0;
            precision = parseInt(precision, 10);
            lftype = (ftype || "").toLowerCase();
            if (ftype === "n") {
                is_numeric = true;
                if (is_int) {
                    if (comma) {
                        throw new ValueError("Cannot specify ',' with 'n'");
                    }
                    value = parseInt(value, 10).toLocaleString();
                } else {
                    value = parseFloat(value).toLocaleString();
                }
            } else if (['b', 'c', 'd', 'o', 'x'].indexOf(lftype) !== -1) {
                value = parseInt(value, 10);
                is_numeric = true;
                if (!isNaN(value)) {
                    if (ftype === "b") {
                        value = (value >>> 0).toString(2);
                        if (fhash) {
                            value = "0b" + value;
                        }
                    } else if (ftype === "c") {
                        if (value > 65535) {
                            code = value - 65536;
                            value = String.fromCharCode(55296 + (code >> 10), 56320 + (code & 1023));
                        } else {
                            value = String.fromCharCode(value);
                        }
                    } else if (ftype === "d") {
                        if (comma) {
                            value = safe_comma(value, comma);
                        } else {
                            value = value.toString(10);
                        }
                    } else if (ftype === "o") {
                        value = value.toString(8);
                        if (fhash) {
                            value = "0o" + value;
                        }
                    } else if (lftype === "x") {
                        value = value.toString(16);
                        value = (ftype === "x") ? value.toLowerCase() : value.toUpperCase();
                        if (fhash) {
                            value = "0x" + value;
                        }
                    }
                }
            } else if (['e','f','g','%'].indexOf(lftype) !== -1) {
                is_numeric = true;
                value = parseFloat(value);
                prec = (isNaN(precision)) ? 6 : precision;
                if (lftype === "e") {
                    value = value.toExponential(prec);
                    value = (ftype === "E") ? value.toUpperCase() : value.toLowerCase();
                } else if (lftype === "f") {
                    value = safe_fixed(value, prec, comma);
                    value = (ftype === "F") ? value.toUpperCase() : value.toLowerCase();
                } else if (lftype === "%") {
                    value *= 100;
                    value = safe_fixed(value, prec, comma) + "%";
                } else if (lftype === "g") {
                    prec = max(1, prec);
                    exp = parseInt(split(value.toExponential(prec - 1).toLowerCase(), "e")[1], 10);
                    if (-4 <= exp && exp < prec) {
                        value = safe_fixed(value, prec - 1 - exp, comma);
                    } else {
                        value = value.toExponential(prec - 1);
                    }
                    value = value.replace(/0+$/g, "");
                    if (value[value.length-1] === decimal_sep) {
                        value = value.slice(0, -1);
                    }
                    if (ftype === "G") {
                        value = value.toUpperCase();
                    }
                }
            } else {
                if (comma) {
                    value = parseInt(value, 10);
                    if (isNaN(value)) {
                        throw new ValueError("Must use numbers with , or _");
                    }
                    value = safe_comma(value, comma);
                }
                value += "";
                if (!isNaN(precision)) {
                    value = value.slice(0, precision);
                }
            }
            value += "";
            if (is_numeric && sign) {
                nval = Number(value);
                is_positive = !isNaN(nval) && nval >= 0;
                if (is_positive && (sign === " " || sign === "+")) {
                    value = sign + value;
                }
            }
            function repeat(char, num) {
                return (new Array(num+1)).join(char);
            };
            if (!repeat.__argnames__) Object.defineProperties(repeat, {
                __argnames__ : {value: ["char", "num"]},
                __module__ : {value: "__main__"}
            });

            if (is_numeric && width && width[0] === "0") {
                width = width.slice(1);
                ρσ_unpack = ["0", "="];
                fill = ρσ_unpack[0];
                align = ρσ_unpack[1];
            }
            width = parseInt(width || "-1", 10);
            if (isNaN(width)) {
                throw new ValueError("Invalid width specification: " + width);
            }
            if (fill && value.length < width) {
                if (align === "<") {
                    value = value + repeat(fill, width - value.length);
                } else if (align === ">") {
                    value = repeat(fill, width - value.length) + value;
                } else if (align === "^") {
                    left = Math.floor((width - value.length) / 2);
                    right = width - left - value.length;
                    value = repeat(fill, left) + value + repeat(fill, right);
                } else if (align === "=") {
                    if (ρσ_in(value[0], "+- ")) {
                        value = value[0] + repeat(fill, width - value.length) + value.slice(1);
                    } else {
                        value = repeat(fill, width - value.length) + value;
                    }
                } else {
                    throw new ValueError("Unrecognized alignment: " + align);
                }
            }
            return value;
        };
        if (!apply_formatting.__argnames__) Object.defineProperties(apply_formatting, {
            __argnames__ : {value: ["value", "format_spec"]},
            __module__ : {value: "__main__"}
        });

        function parse_markup(markup) {
            var key, transformer, format_spec, pos, state, ch;
            key = transformer = format_spec = "";
            pos = 0;
            state = 0;
            while (pos < markup.length) {
                ch = markup[(typeof pos === "number" && pos < 0) ? markup.length + pos : pos];
                if (state === 0) {
                    if (ch === "!") {
                        state = 1;
                    } else if (ch === ":") {
                        state = 2;
                    } else {
                        key += ch;
                    }
                } else if (state === 1) {
                    if (ch === ":") {
                        state = 2;
                    } else {
                        transformer += ch;
                    }
                } else {
                    format_spec += ch;
                }
                pos += 1;
            }
            return [key, transformer, format_spec];
        };
        if (!parse_markup.__argnames__) Object.defineProperties(parse_markup, {
            __argnames__ : {value: ["markup"]},
            __module__ : {value: "__main__"}
        });

        function render_markup(markup) {
            var ρσ_unpack, key, transformer, format_spec, lkey, nvalue, object, ans;
            ρσ_unpack = parse_markup(markup);
ρσ_unpack = ρσ_unpack_asarray(3, ρσ_unpack);
            key = ρσ_unpack[0];
            transformer = ρσ_unpack[1];
            format_spec = ρσ_unpack[2];
            if (transformer && ['a', 'r', 's'].indexOf(transformer) === -1) {
                throw new ValueError("Unknown conversion specifier: " + transformer);
            }
            lkey = key.length && split(key, /[.\[]/, 1)[0];
            if (lkey) {
                explicit = true;
                if (implicit) {
                    throw new ValueError("cannot switch from automatic field numbering to manual field specification");
                }
                nvalue = parseInt(lkey);
                object = (isNaN(nvalue)) ? kwargs[(typeof lkey === "number" && lkey < 0) ? kwargs.length + lkey : lkey] : args[(typeof nvalue === "number" && nvalue < 0) ? args.length + nvalue : nvalue];
                if (object === undefined) {
                    if (isNaN(nvalue)) {
                        throw new KeyError(lkey);
                    }
                    throw new IndexError(lkey);
                }
                object = resolve(key.slice(lkey.length), object);
            } else {
                implicit = true;
                if (explicit) {
                    throw new ValueError("cannot switch from manual field specification to automatic field numbering");
                }
                if (idx >= args.length) {
                    throw new IndexError("Not enough arguments to match template: " + template);
                }
                object = args[(typeof idx === "number" && idx < 0) ? args.length + idx : idx];
                idx += 1;
            }
            if (typeof object === "function") {
                object = object();
            }
            ans = "" + object;
            if (format_spec) {
                ans = apply_formatting(ans, format_spec);
            }
            return ans;
        };
        if (!render_markup.__argnames__) Object.defineProperties(render_markup, {
            __argnames__ : {value: ["markup"]},
            __module__ : {value: "__main__"}
        });

        ans = "";
        pos = 0;
        in_brace = 0;
        markup = "";
        while (pos < template.length) {
            ch = template[(typeof pos === "number" && pos < 0) ? template.length + pos : pos];
            if (in_brace) {
                if (ch === "{") {
                    in_brace += 1;
                    markup += "{";
                } else if (ch === "}") {
                    in_brace -= 1;
                    if (in_brace > 0) {
                        markup += "}";
                    } else {
                        ans += render_markup(markup);
                    }
                } else {
                    markup += ch;
                }
            } else {
                if (ch === "{") {
                    if (template[ρσ_bound_index(pos + 1, template)] === "{") {
                        pos += 1;
                        ans += "{";
                    } else {
                        in_brace = 1;
                        markup = "";
                    }
                } else {
                    ans += ch;
                    if (ch === "}" && template[ρσ_bound_index(pos + 1, template)] === "}") {
                        pos += 1;
                    }
                }
            }
            pos += 1;
        }
        if (in_brace) {
            throw new ValueError("expected '}' before end of string");
        }
        return ans;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("capitalize", (function() {
    var ρσ_anonfunc = function () {
        var string;
        string = this;
        if (string) {
            string = string[0].toUpperCase() + string.slice(1).toLowerCase();
        }
        return string;
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("center", (function() {
    var ρσ_anonfunc = function (width, fill) {
        var left, right;
        left = Math.floor((width - this.length) / 2);
        right = width - left - this.length;
        fill = fill || " ";
        return new Array(left+1).join(fill) + this + new Array(right+1).join(fill);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["width", "fill"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("count", (function() {
    var ρσ_anonfunc = function (needle, start, end) {
        var string, ρσ_unpack, pos, step, ans;
        string = this;
        start = start || 0;
        end = end || string.length;
        if (start < 0 || end < 0) {
            string = string.slice(start, end);
            ρσ_unpack = [0, string.length];
            start = ρσ_unpack[0];
            end = ρσ_unpack[1];
        }
        pos = start;
        step = needle.length;
        if (!step) {
            return 0;
        }
        ans = 0;
        while (pos !== -1) {
            pos = string.indexOf(needle, pos);
            if (pos !== -1) {
                ans += 1;
                pos += step;
            }
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["needle", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("endswith", (function() {
    var ρσ_anonfunc = function (suffixes, start, end) {
        var string, q;
        string = this;
        start = start || 0;
        if (typeof suffixes === "string") {
            suffixes = [suffixes];
        }
        if (end !== undefined) {
            string = string.slice(0, end);
        }
        for (var i = 0; i < suffixes.length; i++) {
            q = suffixes[(typeof i === "number" && i < 0) ? suffixes.length + i : i];
            if (string.indexOf(q, Math.max(start, string.length - q.length)) !== -1) {
                return true;
            }
        }
        return false;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["suffixes", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("startswith", (function() {
    var ρσ_anonfunc = function (prefixes, start, end) {
        var prefix;
        start = start || 0;
        if (typeof prefixes === "string") {
            prefixes = [prefixes];
        }
        for (var i = 0; i < prefixes.length; i++) {
            prefix = prefixes[(typeof i === "number" && i < 0) ? prefixes.length + i : i];
            end = (end === undefined) ? this.length : end;
            if (end - start >= prefix.length && prefix === this.slice(start, start + prefix.length)) {
                return true;
            }
        }
        return false;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["prefixes", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("find", (function() {
    var ρσ_anonfunc = function (needle, start, end) {
        var ans;
        while (start < 0) {
            start += this.length;
        }
        ans = this.indexOf(needle, start);
        if (end !== undefined && ans !== -1) {
            while (end < 0) {
                end += this.length;
            }
            if (ans >= end - needle.length) {
                return -1;
            }
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["needle", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("rfind", (function() {
    var ρσ_anonfunc = function (needle, start, end) {
        var ans;
        while (end < 0) {
            end += this.length;
        }
        ans = this.lastIndexOf(needle, end - 1);
        if (start !== undefined && ans !== -1) {
            while (start < 0) {
                start += this.length;
            }
            if (ans < start) {
                return -1;
            }
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["needle", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("index", (function() {
    var ρσ_anonfunc = function (needle, start, end) {
        var ans;
        ans = ρσ_str.prototype.find.apply(this, arguments);
        if (ans === -1) {
            throw new ValueError("substring not found");
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["needle", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("rindex", (function() {
    var ρσ_anonfunc = function (needle, start, end) {
        var ans;
        ans = ρσ_str.prototype.rfind.apply(this, arguments);
        if (ans === -1) {
            throw new ValueError("substring not found");
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["needle", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("islower", (function() {
    var ρσ_anonfunc = function () {
        return this.length > 0 && this.toLowerCase() === this.toString();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("isupper", (function() {
    var ρσ_anonfunc = function () {
        return this.length > 0 && this.toUpperCase() === this.toString();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("isspace", (function() {
    var ρσ_anonfunc = function () {
        return this.length > 0 && /^\s+$/.test(this);
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("join", (function() {
    var ρσ_anonfunc = function (iterable) {
        var ans, r;
        if (Array.isArray(iterable)) {
            return iterable.join(this);
        }
        ans = "";
        r = iterable.next();
        while (!r.done) {
            if (ans) {
                ans += this;
            }
            ans += r.value;
            r = iterable.next();
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["iterable"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("ljust", (function() {
    var ρσ_anonfunc = function (width, fill) {
        var string;
        string = this;
        if (width > string.length) {
            fill = fill || " ";
            string += new Array(width - string.length + 1).join(fill);
        }
        return string;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["width", "fill"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("rjust", (function() {
    var ρσ_anonfunc = function (width, fill) {
        var string;
        string = this;
        if (width > string.length) {
            fill = fill || " ";
            string = new Array(width - string.length + 1).join(fill) + string;
        }
        return string;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["width", "fill"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("lower", (function() {
    var ρσ_anonfunc = function () {
        return this.toLowerCase();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("upper", (function() {
    var ρσ_anonfunc = function () {
        return this.toUpperCase();
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("lstrip", (function() {
    var ρσ_anonfunc = function (chars) {
        var string, pos;
        string = this;
        pos = 0;
        chars = chars || ρσ_str.whitespace;
        while (chars.indexOf(string[(typeof pos === "number" && pos < 0) ? string.length + pos : pos]) !== -1) {
            pos += 1;
        }
        if (pos) {
            string = string.slice(pos);
        }
        return string;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["chars"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("rstrip", (function() {
    var ρσ_anonfunc = function (chars) {
        var string, pos;
        string = this;
        pos = string.length - 1;
        chars = chars || ρσ_str.whitespace;
        while (chars.indexOf(string[(typeof pos === "number" && pos < 0) ? string.length + pos : pos]) !== -1) {
            pos -= 1;
        }
        if (pos < string.length - 1) {
            string = string.slice(0, pos + 1);
        }
        return string;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["chars"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("strip", (function() {
    var ρσ_anonfunc = function (chars) {
        return ρσ_str.prototype.lstrip.call(ρσ_str.prototype.rstrip.call(this, chars), chars);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["chars"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("partition", (function() {
    var ρσ_anonfunc = function (sep) {
        var idx;
        idx = this.indexOf(sep);
        if (idx === -1) {
            return [this, "", ""];
        }
        return [this.slice(0, idx), sep, this.slice(idx + sep.length)];
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["sep"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("rpartition", (function() {
    var ρσ_anonfunc = function (sep) {
        var idx;
        idx = this.lastIndexOf(sep);
        if (idx === -1) {
            return ["", "", this];
        }
        return [this.slice(0, idx), sep, this.slice(idx + sep.length)];
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["sep"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("replace", (function() {
    var ρσ_anonfunc = function (old, repl, count) {
        var string, pos, idx;
        string = this;
        if (count === 1) {
            return ρσ_orig_replace(string, old, repl);
        }
        if (count < 1) {
            return string;
        }
        count = count || Number.MAX_VALUE;
        pos = 0;
        while (count > 0) {
            count -= 1;
            idx = string.indexOf(old, pos);
            if (idx === -1) {
                break;
            }
            pos = idx + repl.length;
            string = string.slice(0, idx) + repl + string.slice(idx + old.length);
        }
        return string;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["old", "repl", "count"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("split", (function() {
    var ρσ_anonfunc = function (sep, maxsplit) {
        var split, ans, extra, parts;
        if (maxsplit === 0) {
            return ρσ_list_decorate([ this ]);
        }
        split = ρσ_orig_split;
        if (sep === undefined || sep === null) {
            if (maxsplit > 0) {
                ans = split(this, /(\s+)/);
                extra = "";
                parts = [];
                for (var i = 0; i < ans.length; i++) {
                    if (parts.length >= maxsplit + 1) {
                        extra += ans[(typeof i === "number" && i < 0) ? ans.length + i : i];
                    } else if (i % 2 === 0) {
                        parts.push(ans[(typeof i === "number" && i < 0) ? ans.length + i : i]);
                    }
                }
                parts[parts.length-1] += extra;
                ans = parts;
            } else {
                ans = split(this, /\s+/);
            }
        } else {
            if (sep === "") {
                throw new ValueError("empty separator");
            }
            ans = split(this, sep);
            if (maxsplit > 0 && ans.length > maxsplit) {
                extra = ans.slice(maxsplit).join(sep);
                ans = ans.slice(0, maxsplit);
                ans.push(extra);
            }
        }
        return ρσ_list_decorate(ans);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["sep", "maxsplit"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("rsplit", (function() {
    var ρσ_anonfunc = function (sep, maxsplit) {
        var split, ans, is_space, pos, current, spc, ch, end, idx;
        if (!maxsplit) {
            return ρσ_str.prototype.split.call(this, sep);
        }
        split = ρσ_orig_split;
        if (sep === undefined || sep === null) {
            if (maxsplit > 0) {
                ans = [];
                is_space = /\s/;
                pos = this.length - 1;
                current = "";
                while (pos > -1 && maxsplit > 0) {
                    spc = false;
                    ch = (ρσ_expr_temp = this)[(typeof pos === "number" && pos < 0) ? ρσ_expr_temp.length + pos : pos];
                    while (pos > -1 && is_space.test(ch)) {
                        spc = true;
                        ch = this[--pos];
                    }
                    if (spc) {
                        if (current) {
                            ans.push(current);
                            maxsplit -= 1;
                        }
                        current = ch;
                    } else {
                        current += ch;
                    }
                    pos -= 1;
                }
                ans.push(this.slice(0, pos + 1) + current);
                ans.reverse();
            } else {
                ans = split(this, /\s+/);
            }
        } else {
            if (sep === "") {
                throw new ValueError("empty separator");
            }
            ans = [];
            pos = end = this.length;
            while (pos > -1 && maxsplit > 0) {
                maxsplit -= 1;
                idx = this.lastIndexOf(sep, pos);
                if (idx === -1) {
                    break;
                }
                ans.push(this.slice(idx + sep.length, end));
                pos = idx - 1;
                end = idx;
            }
            ans.push(this.slice(0, end));
            ans.reverse();
        }
        return ρσ_list_decorate(ans);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["sep", "maxsplit"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("splitlines", (function() {
    var ρσ_anonfunc = function (keepends) {
        var split, parts, ans;
        split = ρσ_orig_split;
        if (keepends) {
            parts = split(this, /((?:\r?\n)|\r)/);
            ans = [];
            for (var i = 0; i < parts.length; i++) {
                if (i % 2 === 0) {
                    ans.push(parts[(typeof i === "number" && i < 0) ? parts.length + i : i]);
                } else {
                    ans[ans.length-1] += parts[(typeof i === "number" && i < 0) ? parts.length + i : i];
                }
            }
        } else {
            ans = split(this, /(?:\r?\n)|\r/);
        }
        return ρσ_list_decorate(ans);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["keepends"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("swapcase", (function() {
    var ρσ_anonfunc = function () {
        var ans, a, b;
        ans = new Array(this.length);
        for (var i = 0; i < ans.length; i++) {
            a = (ρσ_expr_temp = this)[(typeof i === "number" && i < 0) ? ρσ_expr_temp.length + i : i];
            b = a.toLowerCase();
            if (a === b) {
                b = a.toUpperCase();
            }
            ans[(typeof i === "number" && i < 0) ? ans.length + i : i] = b;
        }
        return ans.join("");
    };
    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
define_str_func("zfill", (function() {
    var ρσ_anonfunc = function (width) {
        var string;
        string = this;
        if (width > string.length) {
            string = new Array(width - string.length + 1).join("0") + string;
        }
        return string;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["width"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})());
ρσ_str.uchrs = (function() {
    var ρσ_anonfunc = function (string, with_positions) {
        return (function(){
            var ρσ_d = {};
            ρσ_d["_string"] = string;
            ρσ_d["_pos"] = 0;
            ρσ_d[ρσ_iterator_symbol] = (function() {
                var ρσ_anonfunc = function () {
                    return this;
                };
                if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
            ρσ_d["next"] = (function() {
                var ρσ_anonfunc = function () {
                    var length, pos, value, ans, extra;
                    length = this._string.length;
                    if (this._pos >= length) {
                        return (function(){
                            var ρσ_d = {};
                            ρσ_d["done"] = true;
                            return ρσ_d;
                        }).call(this);
                    }
                    pos = this._pos;
                    value = this._string.charCodeAt(this._pos++);
                    ans = "\ufffd";
                    if (55296 <= value && value <= 56319) {
                        if (this._pos < length) {
                            extra = this._string.charCodeAt(this._pos++);
                            if ((extra & 56320) === 56320) {
                                ans = String.fromCharCode(value, extra);
                            }
                        }
                    } else if ((value & 56320) !== 56320) {
                        ans = String.fromCharCode(value);
                    }
                    if (with_positions) {
                        return (function(){
                            var ρσ_d = {};
                            ρσ_d["done"] = false;
                            ρσ_d["value"] = ρσ_list_decorate([ pos, ans ]);
                            return ρσ_d;
                        }).call(this);
                    } else {
                        return (function(){
                            var ρσ_d = {};
                            ρσ_d["done"] = false;
                            ρσ_d["value"] = ans;
                            return ρσ_d;
                        }).call(this);
                    }
                };
                if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                    __module__ : {value: "__main__"}
                });
                return ρσ_anonfunc;
            })();
            return ρσ_d;
        }).call(this);
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["string", "with_positions"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_str.uslice = (function() {
    var ρσ_anonfunc = function (string, start, end) {
        var items, iterator, r;
        items = [];
        iterator = ρσ_str.uchrs(string);
        r = iterator.next();
        while (!r.done) {
            items.push(r.value);
            r = iterator.next();
        }
        return items.slice(start || 0, (end === undefined) ? items.length : end).join("");
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["string", "start", "end"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_str.ulen = (function() {
    var ρσ_anonfunc = function (string) {
        var iterator, r, ans;
        iterator = ρσ_str.uchrs(string);
        r = iterator.next();
        ans = 0;
        while (!r.done) {
            r = iterator.next();
            ans += 1;
        }
        return ans;
    };
    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
        __argnames__ : {value: ["string"]},
        __module__ : {value: "__main__"}
    });
    return ρσ_anonfunc;
})();
ρσ_str.ascii_lowercase = "abcdefghijklmnopqrstuvwxyz";
ρσ_str.ascii_uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
ρσ_str.ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
ρσ_str.digits = "0123456789";
ρσ_str.punctuation = "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~";
ρσ_str.printable = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\u000b\f";
ρσ_str.whitespace = " \t\n\r\u000b\f";
define_str_func = undefined;
var str = ρσ_str, repr = ρσ_repr;;

    (function(){

        var __name__ = "__main__";


        var CACHE_NAME;
        CACHE_NAME = "calibre-app-9.5.101-8b37f88a";
        self.addEventListener("install", (function() {
            var ρσ_anonfunc = function (event) {
                event.waitUntil(self.skipWaiting());
            };
            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                __argnames__ : {value: ["event"]},
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })());
        self.addEventListener("activate", (function() {
            var ρσ_anonfunc = function (event) {
                event.waitUntil(caches.keys().then((function() {
                    var ρσ_anonfunc = function (keys) {
                        return Promise.all(keys.filter((function() {
                            var ρσ_anonfunc = function (key) {
                                return key !== CACHE_NAME;
                            };
                            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                                __argnames__ : {value: ["key"]},
                                __module__ : {value: "__main__"}
                            });
                            return ρσ_anonfunc;
                        })()).map((function() {
                            var ρσ_anonfunc = function (key) {
                                return caches.delete(key);
                            };
                            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                                __argnames__ : {value: ["key"]},
                                __module__ : {value: "__main__"}
                            });
                            return ρσ_anonfunc;
                        })()));
                    };
                    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                        __argnames__ : {value: ["keys"]},
                        __module__ : {value: "__main__"}
                    });
                    return ρσ_anonfunc;
                })()).then((function() {
                    var ρσ_anonfunc = function () {
                        return self.clients.claim();
                    };
                    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                        __module__ : {value: "__main__"}
                    });
                    return ρσ_anonfunc;
                })()));
            };
            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                __argnames__ : {value: ["event"]},
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })());
        self.addEventListener("fetch", (function() {
            var ρσ_anonfunc = function (event) {
                var url;
                if (event.request.method !== "GET") {
                    return;
                }
                url = new URL(event.request.url);
                if (url.origin !== self.location.origin) {
                    return;
                }
                if (url.pathname !== "/") {
                    return;
                }
                event.respondWith(fetch(event.request).then((function() {
                    var ρσ_anonfunc = function (response) {
                        if (response.ok) {
                            caches.open(CACHE_NAME).then((function() {
                                var ρσ_anonfunc = function (cache) {
                                    cache.put(event.request.url, response.clone());
                                };
                                if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                                    __argnames__ : {value: ["cache"]},
                                    __module__ : {value: "__main__"}
                                });
                                return ρσ_anonfunc;
                            })());
                        }
                        return response;
                    };
                    if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                        __argnames__ : {value: ["response"]},
                        __module__ : {value: "__main__"}
                    });
                    return ρσ_anonfunc;
                })()).catch((function() {
                    var ρσ_anonfunc = function () {
                        return caches.match(event.request.url);
                    };
                    if (!ρσ_anonfunc.__module__) Object.defineProperties(ρσ_anonfunc, {
                        __module__ : {value: "__main__"}
                    });
                    return ρσ_anonfunc;
                })()));
            };
            if (!ρσ_anonfunc.__argnames__) Object.defineProperties(ρσ_anonfunc, {
                __argnames__ : {value: ["event"]},
                __module__ : {value: "__main__"}
            });
            return ρσ_anonfunc;
        })());
    })();
})();