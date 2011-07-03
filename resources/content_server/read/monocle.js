Monocle = {
  VERSION: "2.0.0"
};


Monocle.pieceLoaded = function (piece) {
  if (typeof onMonoclePiece == 'function') {
    onMonoclePiece(piece);
  }
}


Monocle.defer = function (fn, time) {
  if (fn && typeof fn == "function") {
    return setTimeout(fn, time || 0);
  }
}


Monocle.Browser = { engine: 'W3C' }

Monocle.Browser.is = {
  IE: (!!(window.attachEvent && navigator.userAgent.indexOf('Opera') === -1)) &&
    (Monocle.Browser.engine = "IE"),
  Opera: navigator.userAgent.indexOf('Opera') > -1 &&
    (Monocle.Browser.engine = "Opera"),
  WebKit: navigator.userAgent.indexOf('AppleWebKit/') > -1 &&
    (Monocle.Browser.engine = "WebKit"),
  Gecko: navigator.userAgent.indexOf('Gecko') > -1 &&
    navigator.userAgent.indexOf('KHTML') === -1 &&
    (Monocle.Browser.engine = "Gecko"),
  MobileSafari: !!navigator.userAgent.match(/AppleWebKit.*Mobile/)
} // ... with thanks to PrototypeJS.


Monocle.Browser.on = {
  iPhone: navigator.userAgent.indexOf("iPhone") != -1,
  iPad: navigator.userAgent.indexOf("iPad") != -1,
  BlackBerry: navigator.userAgent.indexOf("BlackBerry") != -1,
  Android: navigator.userAgent.indexOf('Android') != -1,
  MacOSX: navigator.userAgent.indexOf('Mac OS X') != -1,
  Kindle3: navigator.userAgent.match(/Kindle\/3/)
}


if (Monocle.Browser.is.MobileSafari) {
  (function () {
    var ver = navigator.userAgent.match(/ OS ([\d_]+)/);
    if (ver) {
      Monocle.Browser.iOSVersion = ver[1].replace(/_/g, '.');
    } else {
      console.warn("Unknown MobileSafari user agent: "+navigator.userAgent);
    }
  })();
}
Monocle.Browser.iOSVersionBelow = function (strOrNum) {
  return Monocle.Browser.iOSVersion && Monocle.Browser.iOSVersion < strOrNum;
}


Monocle.Browser.CSSProps = {
  engines: ["W3C", "WebKit", "Gecko", "Opera", "IE", "Konqueror"],
  prefixes: ["", "-webkit-", "-moz-", "-o-", "-ms-", "-khtml-"],
  domprefixes: ["", "Webkit", "Moz", "O", "ms", "Khtml"],
  guineapig: document.createElement('div')
}


Monocle.Browser.CSSProps.capStr = function (wd) {
  return wd ? wd.charAt(0).toUpperCase() + wd.substr(1) : "";
}


Monocle.Browser.CSSProps.toDOMProps = function (prop, prefix) {
  var parts = prop.split('-');
  for (var i = parts.length; i > 0; --i) {
    parts[i] = Monocle.Browser.CSSProps.capStr(parts[i]);
  }

  if (typeof(prefix) != 'undefined' && prefix != null) {
    if (prefix) {
      parts[0] = Monocle.Browser.CSSProps.capStr(parts[0]);
      return prefix+parts.join('');
    } else {
      return parts.join('');
    }
  }

  var props = [parts.join('')];
  parts[0] = Monocle.Browser.CSSProps.capStr(parts[0]);
  for (i = 0; i < Monocle.Browser.CSSProps.prefixes.length; ++i) {
    var pf = Monocle.Browser.CSSProps.domprefixes[i];
    if (!pf) { continue; }
    props.push(pf+parts.join(''));
  }
  return props;
}


Monocle.Browser.CSSProps.toDOMProp = function (prop) {
  return Monocle.Browser.CSSProps.toDOMProps(
    prop,
    Monocle.Browser.CSSProps.domprefixes[
      Monocle.Browser.CSSProps.engines.indexOf(Monocle.Browser.engine)
    ]
  );
}


Monocle.Browser.CSSProps.isSupported = function (props) {
  for (var i in props) {
    if (Monocle.Browser.CSSProps.guineapig.style[props[i]] !== undefined) {
      return true;
    }
  }
  return false;
} // Thanks modernizr!


Monocle.Browser.CSSProps.isSupportedForAnyPrefix = function (prop) {
  return Monocle.Browser.CSSProps.isSupported(
    Monocle.Browser.CSSProps.toDOMProps(prop)
  );
}


Monocle.Browser.CSSProps.supportsMediaQuery = function (query) {
  var gpid = "monocle_guineapig";
  var div = Monocle.Browser.CSSProps.guineapig;
  div.id = gpid;
  var st = document.createElement('style');
  st.textContent = query+'{#'+gpid+'{height:3px}}';
  (document.head || document.getElementsByTagName('head')[0]).appendChild(st);
  document.documentElement.appendChild(div);

  var result = Monocle.Browser.CSSProps.guineapig.offsetHeight === 3;

  st.parentNode.removeChild(st);
  div.parentNode.removeChild(div);

  return result;
} // Thanks modernizr!


Monocle.Browser.CSSProps.supportsMediaQueryProperty = function (prop) {
  return Monocle.Browser.CSSProps.supportsMediaQuery(
    '@media ('+Monocle.Browser.CSSProps.prefixes.join(prop+'),(')+'monocle__)'
  );
}



Monocle.Browser.has = {}
Monocle.Browser.has.touch = ('ontouchstart' in window) ||
  Monocle.Browser.CSSProps.supportsMediaQueryProperty('touch-enabled');
Monocle.Browser.has.columns = Monocle.Browser.CSSProps.isSupportedForAnyPrefix(
  'column-width'
);
Monocle.Browser.has.transform3d = Monocle.Browser.CSSProps.isSupported([
  'perspectiveProperty',
  'WebkitPerspective',
  'MozPerspective',
  'OPerspective',
  'msPerspective'
]) && Monocle.Browser.CSSProps.supportsMediaQueryProperty('transform-3d');
Monocle.Browser.has.embedded = (top != self);

Monocle.Browser.has.iframeTouchBug = Monocle.Browser.iOSVersionBelow("4.2");

Monocle.Browser.has.selectThruBug = Monocle.Browser.iOSVersionBelow("4.2");

Monocle.Browser.has.mustScrollSheaf = Monocle.Browser.is.MobileSafari;
Monocle.Browser.has.iframeDoubleWidthBug =
  Monocle.Browser.has.mustScrollSheaf || Monocle.Browser.on.Kindle3;

Monocle.Browser.has.floatColumnBug = Monocle.Browser.is.WebKit;

Monocle.Browser.has.relativeIframeWidthBug = Monocle.Browser.on.Android;


Monocle.Browser.has.jumpFlickerBug =
  Monocle.Browser.on.MacOSX && Monocle.Browser.is.WebKit;


Monocle.Browser.has.columnOverflowPaintBug = Monocle.Browser.is.WebKit &&
  !Monocle.Browser.is.MobileSafari &&
  navigator.userAgent.indexOf("AppleWebKit/534") > 0;


if (typeof window.console == "undefined") {
  window.console = {
    messages: [],
    log: function (msg) {
      this.messages.push(msg);
    }
  }
}


window.console.compatDir = function (obj) {
  var stringify = function (o) {
    var parts = [];
    for (x in o) {
      parts.push(x + ": " + o[x]);
    }
    return parts.join("; ");
  }

  window.console.log(stringify(obj));
}


if (!Array.prototype.indexOf) {
  Array.prototype.indexOf = function(elt /*, from*/) {
    var len = this.length >>> 0;

    var from = Number(arguments[1]) || 0;
    from = (from < 0)
      ? Math.ceil(from)
      : Math.floor(from);
    if (from < 0) {
      from += len;
    }

    for (; from < len; from++) {
      if (from in this && this[from] === elt) {
        return from;
      }
    }
    return -1;
  };
}


Monocle.pieceLoaded('compat');
Monocle.Factory = function (element, label, index, reader) {

  var API = { constructor: Monocle.Factory };
  var k = API.constants = API.constructor;
  var p = API.properties = {
    element: element,
    label: label,
    index: index,
    reader: reader,
    prefix: reader.properties.classPrefix || ''
  }


  function initialize() {
    if (!p.label) { return; }
    var node = p.reader.properties.graph;
    node[p.label] = node[p.label] || [];
    if (typeof p.index == 'undefined' && node[p.label][p.index]) {
      throw('Element already exists in graph: '+p.label+'['+p.index+']');
    } else {
      p.index = p.index || node[p.label].length;
    }
    node[p.label][p.index] = p.element;

    addClass(p.label);
  }


  function find(oLabel, oIndex) {
    if (!p.reader.properties.graph[oLabel]) {
      return null;
    }
    return p.reader.properties.graph[oLabel][oIndex || 0];
  }


  function claim(oElement, oLabel, oIndex) {
    return oElement.dom = new Monocle.Factory(
      oElement,
      oLabel,
      oIndex,
      p.reader
    );
  }


  function make(tagName, oLabel, index_or_options, or_options) {
    var oIndex, options;
    if (arguments.length == 1) {
      oLabel = null,
      oIndex = 0;
      options = {};
    } else if (arguments.length == 2) {
      oIndex = 0;
      options = {};
    } else if (arguments.length == 4) {
      oIndex = arguments[2];
      options = arguments[3];
    } else if (arguments.length == 3) {
      var lastArg = arguments[arguments.length - 1];
      if (typeof lastArg == "number") {
        oIndex = lastArg;
        options = {};
      } else {
        oIndex = 0;
        options = lastArg;
      }
    }

    var oElement = document.createElement(tagName);
    claim(oElement, oLabel, oIndex);
    if (options['class']) {
      oElement.className += " "+p.prefix+options['class'];
    }
    if (options['html']) {
      oElement.innerHTML = options['html'];
    }
    if (options['text']) {
      oElement.appendChild(document.createTextNode(options['text']));
    }

    return oElement;
  }


  function append(tagName, oLabel, index_or_options, or_options) {
    var oElement = make.apply(this, arguments);
    p.element.appendChild(oElement);
    return oElement;
  }


  function address() {
    return [p.label, p.index, p.reader];
  }


  function setStyles(rules) {
    return Monocle.Styles.applyRules(p.element, rules);
  }


  function setBetaStyle(property, value) {
    return Monocle.Styles.affix(p.element, property, value);
  }



  function hasClass(name) {
    name = p.prefix + name;
    var klass = p.element.className;
    if (!klass) { return false; }
    if (klass == name) { return true; }
    return new RegExp("(^|\\s)"+name+"(\\s|$)").test(klass);
  }


  function addClass(name) {
    if (hasClass(name)) { return; }
    var gap = p.element.className ? ' ' : '';
    return p.element.className += gap+p.prefix+name;
  }


  function removeClass(name) {
    var reName = new RegExp("(^|\\s+)"+p.prefix+name+"(\\s+|$)");
    var reTrim = /^\s+|\s+$/g;
    var klass = p.element.className;
    p.element.className = klass.replace(reName, ' ').replace(reTrim, '');
    return p.element.className;
  }


  API.find = find;
  API.claim = claim;
  API.make = make;
  API.append = append;
  API.address = address;

  API.setStyles = setStyles;
  API.setBetaStyle = setBetaStyle;
  API.hasClass = hasClass;
  API.addClass = addClass;
  API.removeClass = removeClass;

  initialize();

  return API;
}

Monocle.pieceLoaded('factory');
Monocle.Events = {}


Monocle.Events.dispatch = function (elem, evtType, data, cancelable) {
  if (!document.createEvent) {
    return true;
  }
  var evt = document.createEvent("Events");
  evt.initEvent(evtType, false, cancelable || false);
  evt.m = data;
  try {
    return elem.dispatchEvent(evt);
  } catch(e) {
    console.warn("Failed to dispatch event: "+evtType);
    return false;
  }
}


Monocle.Events.listen = function (elem, evtType, fn, useCapture) {
  if (elem.addEventListener) {
    return elem.addEventListener(evtType, fn, useCapture || false);
  } else if (elem.attachEvent) {
    return elem.attachEvent('on'+evtType, fn);
  }
}


Monocle.Events.deafen = function (elem, evtType, fn, useCapture) {
  if (elem.removeEventListener) {
    return elem.removeEventListener(evtType, fn, useCapture || false);
  } else if (elem.detachEvent) {
    try {
      return elem.detachEvent('on'+evtType, fn);
    } catch(e) {}
  }
}


Monocle.Events.listenForContact = function (elem, fns, options) {
  var listeners = {};

  var cursorInfo = function (evt, ci) {
    evt.m = {
      pageX: ci.pageX,
      pageY: ci.pageY
    };

    var target = evt.target || evt.srcElement;
    while (target.nodeType != 1 && target.parentNode) {
      target = target.parentNode;
    }

    var offset = offsetFor(evt, target);
    evt.m.offsetX = offset[0];
    evt.m.offsetY = offset[1];

    if (evt.currentTarget) {
      offset = offsetFor(evt, evt.currentTarget);
      evt.m.registrantX = offset[0];
      evt.m.registrantY = offset[1];
    }

    return evt;
  }


  var offsetFor = function (evt, elem) {
    var r;
    if (elem.getBoundingClientRect) {
      var er = elem.getBoundingClientRect();
      var dr = document.body.getBoundingClientRect();
      r = { left: er.left - dr.left, top: er.top - dr.top };
    } else {
      r = { left: elem.offsetLeft, top: elem.offsetTop }
      while (elem = elem.parentNode) {
        if (elem.offsetLeft || elem.offsetTop) {
          r.left += elem.offsetLeft;
          r.top += elem.offsetTop;
        }
      }
    }
    return [evt.m.pageX - r.left, evt.m.pageY - r.top];
  }


  var capture = (options && options.useCapture) || false;

  if (!Monocle.Browser.has.touch) {
    if (fns.start) {
      listeners.mousedown = function (evt) {
        if (evt.button != 0) { return; }
        fns.start(cursorInfo(evt, evt));
      }
      Monocle.Events.listen(elem, 'mousedown', listeners.mousedown, capture);
    }
    if (fns.move) {
      listeners.mousemove = function (evt) {
        fns.move(cursorInfo(evt, evt));
      }
      Monocle.Events.listen(elem, 'mousemove', listeners.mousemove, capture);
    }
    if (fns.end) {
      listeners.mouseup = function (evt) {
        fns.end(cursorInfo(evt, evt));
      }
      Monocle.Events.listen(elem, 'mouseup', listeners.mouseup, capture);
    }
    if (fns.cancel) {
      listeners.mouseout = function (evt) {
        obj = evt.relatedTarget || evt.fromElement;
        while (obj && (obj = obj.parentNode)) {
          if (obj == elem) { return; }
        }
        fns.cancel(cursorInfo(evt, evt));
      }
      Monocle.Events.listen(elem, 'mouseout', listeners.mouseout, capture);
    }
  } else {
    if (fns.start) {
      listeners.start = function (evt) {
        if (evt.touches.length > 1) { return; }
        fns.start(cursorInfo(evt, evt.targetTouches[0]));
      }
    }
    if (fns.move) {
      listeners.move = function (evt) {
        if (evt.touches.length > 1) { return; }
        fns.move(cursorInfo(evt, evt.targetTouches[0]));
      }
    }
    if (fns.end) {
      listeners.end = function (evt) {
        fns.end(cursorInfo(evt, evt.changedTouches[0]));
        evt.preventDefault();
      }
    }
    if (fns.cancel) {
      listeners.cancel = function (evt) {
        fns.cancel(cursorInfo(evt, evt.changedTouches[0]));
      }
    }

    if (Monocle.Browser.has.iframeTouchBug) {
      Monocle.Events.tMonitor = Monocle.Events.tMonitor ||
        new Monocle.Events.TouchMonitor();
      Monocle.Events.tMonitor.listen(elem, listeners, options);
    } else {
      for (etype in listeners) {
        Monocle.Events.listen(elem, 'touch'+etype, listeners[etype], capture);
      }
    }
  }

  return listeners;
}


Monocle.Events.deafenForContact = function (elem, listeners) {
  var prefix = "";
  if (Monocle.Browser.has.touch) {
    prefix = Monocle.Browser.has.iframeTouchBug ? "contact" : "touch";
  }

  for (evtType in listeners) {
    Monocle.Events.deafen(elem, prefix + evtType, listeners[evtType]);
  }
}


Monocle.Events.listenForTap = function (elem, fn, activeClass) {
  var startPos;

  if (Monocle.Browser.on.Kindle3) {
    Monocle.Events.listen(elem, 'click', function () {});
  }

  var annul = function () {
    startPos = null;
    if (activeClass && elem.dom) { elem.dom.removeClass(activeClass); }
  }

  var annulIfOutOfBounds = function (evt) {
    if (evt.type.match(/^mouse/)) {
      return;
    }
    if (Monocle.Browser.is.MobileSafari && Monocle.Browser.iOSVersion < "3.2") {
      return;
    }
    if (
      evt.m.registrantX < 0 || evt.m.registrantX > elem.offsetWidth ||
      evt.m.registrantY < 0 || evt.m.registrantY > elem.offsetHeight
    ) {
      annul();
    } else {
      evt.preventDefault();
    }
  }

  return Monocle.Events.listenForContact(
    elem,
    {
      start: function (evt) {
        startPos = [evt.m.pageX, evt.m.pageY];
        evt.preventDefault();
        if (activeClass && elem.dom) { elem.dom.addClass(activeClass); }
      },
      move: annulIfOutOfBounds,
      end: function (evt) {
        annulIfOutOfBounds(evt);
        if (startPos) {
          evt.m.startOffset = startPos;
          fn(evt);
        }
        annul();
      },
      cancel: annul
    },
    {
      useCapture: false
    }
  );
}


Monocle.Events.deafenForTap = Monocle.Events.deafenForContact;


Monocle.Events.TouchMonitor = function () {
  if (Monocle.Events == this) {
    return new Monocle.Events.TouchMonitor();
  }

  var API = { constructor: Monocle.Events.TouchMonitor }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    touching: null,
    edataPrev: null,
    originator: null,
    brokenModel_4_1: navigator.userAgent.match(/ OS 4_1/)
  }


  function listenOnIframe(iframe) {
    if (iframe.contentDocument) {
      enableTouchProxy(iframe.contentDocument);
      iframe.contentDocument.isTouchFrame = true;
    }

    if (p.brokenModel_4_1) {
      enableTouchProxy(iframe);
    }
  }


  function listen(element, fns, useCapture) {
    for (etype in fns) {
      Monocle.Events.listen(element, 'contact'+etype, fns[etype], useCapture);
    }
    enableTouchProxy(element, useCapture);
  }


  function enableTouchProxy(element, useCapture) {
    if (element.monocleTouchProxy) {
      return;
    }
    element.monocleTouchProxy = true;

    var fn = function (evt) { touchProxyHandler(element, evt) }
    Monocle.Events.listen(element, "touchstart", fn, useCapture);
    Monocle.Events.listen(element, "touchmove", fn, useCapture);
    Monocle.Events.listen(element, "touchend", fn, useCapture);
    Monocle.Events.listen(element, "touchcancel", fn, useCapture);
  }


  function touchProxyHandler(element, evt) {
    var edata = {
      start: evt.type == "touchstart",
      move: evt.type == "touchmove",
      end: evt.type == "touchend" || evt.type == "touchcancel",
      time: new Date().getTime(),
      frame: element.isTouchFrame
    }

    if (!p.touching) {
      p.originator = element;
    }

    var target = element;
    var touch = evt.touches[0] || evt.changedTouches[0];
    target = document.elementFromPoint(touch.screenX, touch.screenY);

    if (target) {
      translateTouchEvent(element, target, evt, edata);
    }
  }


  function translateTouchEvent(element, target, evt, edata) {
    if (
      p.brokenModel_4_1 &&
      !edata.frame &&
      !p.touching &&
      edata.start &&
      p.edataPrev &&
      p.edataPrev.end &&
      (edata.time - p.edataPrev.time) < 30
    ) {
      evt.preventDefault();
      return;
    }

    if (!p.touching && !edata.end) {
      return fireStart(evt, target, edata);
    }

    if (edata.move && p.touching) {
      return fireMove(evt, edata);
    }

    if (p.brokenModel_4_1) {
      if (p.touching && !edata.frame) {
        return fireProvisionalEnd(evt, edata);
      }
    } else {
      if (edata.end && p.touching) {
        return fireProvisionalEnd(evt, edata);
      }
    }

    if (
      p.brokenModel_4_1 &&
      p.originator != element &&
      edata.frame &&
      edata.end
    ) {
      evt.preventDefault();
      return;
    }

    if (edata.frame && edata.end && p.touching) {
      return fireProvisionalEnd(evt, edata);
    }
  }


  function fireStart(evt, target, edata) {
    p.touching = target;
    p.edataPrev = edata;
    return fireTouchEvent(p.touching, 'start', evt);
  }


  function fireMove(evt, edata) {
    clearProvisionalEnd();
    p.edataPrev = edata;
    return fireTouchEvent(p.touching, 'move', evt);
  }


  function fireEnd(evt, edata) {
    var result = fireTouchEvent(p.touching, 'end', evt);
    p.edataPrev = edata;
    p.touching = null;
    return result;
  }


  function fireProvisionalEnd(evt, edata) {
    clearProvisionalEnd();
    var mimicEvt = mimicTouchEvent(p.touching, 'end', evt);
    p.edataPrev = edata;

    p.provisionalEnd = setTimeout(
      function() {
        if (p.touching) {
          p.touching.dispatchEvent(mimicEvt);
          p.touching = null;
        }
      },
      30
    );
  }


  function clearProvisionalEnd() {
    if (p.provisionalEnd) {
      clearTimeout(p.provisionalEnd);
      p.provisionalEnd = null;
    }
  }


  function mimicTouchEvent(target, newtype, evt) {
    var cloneTouch = function (t) {
      return document.createTouch(
        document.defaultView,
        target,
        t.identifier,
        t.screenX,
        t.screenY,
        t.screenX,
        t.screenY
      );
    }

    var findTouch = function (id) {
      for (var i = 0; i < touches.all.length; ++i) {
        if (touches.all[i].identifier == id) {
          return touches.all[i];
        }
      }
    }

    var touches = { all: [], target: [], changed: [] };
    for (var i = 0; i < evt.touches.length; ++i) {
      touches.all.push(cloneTouch(evt.touches[i]));
    }
    for (var i = 0; i < evt.targetTouches.length; ++i) {
      touches.target.push(
        findTouch(evt.targetTouches[i].identifier) ||
        cloneTouch(evt.targetTouches[i])
      );
    }
    for (var i = 0; i < evt.changedTouches.length; ++i) {
      touches.changed.push(
        findTouch(evt.changedTouches[i].identifier) ||
        cloneTouch(evt.changedTouches[i])
      );
    }

    var mimicEvt = document.createEvent('TouchEvent');
    mimicEvt.initTouchEvent(
      "contact"+newtype,
      true,
      true,
      document.defaultView,
      evt.detail,
      evt.screenX,
      evt.screenY,
      evt.screenX,
      evt.screenY,
      evt.ctrlKey,
      evt.altKey,
      evt.shiftKey,
      evt.metaKey,
      document.createTouchList.apply(document, touches.all),
      document.createTouchList.apply(document, touches.target),
      document.createTouchList.apply(document, touches.changed),
      evt.scale,
      evt.rotation
    );

    return mimicEvt;
  }


  function fireTouchEvent(target, newtype, evt) {
    var mimicEvt = mimicTouchEvent(target, newtype, evt);
    var result = target.dispatchEvent(mimicEvt);
    if (!result) {
      evt.preventDefault();
    }
    return result;
  }


  API.listen = listen;
  API.listenOnIframe = listenOnIframe;

  return API;
}


Monocle.Events.listenOnIframe = function (frame) {
  if (!Monocle.Browser.has.iframeTouchBug) {
    return;
  }
  Monocle.Events.tMonitor = Monocle.Events.tMonitor ||
    new Monocle.Events.TouchMonitor();
  Monocle.Events.tMonitor.listenOnIframe(frame);
}

Monocle.pieceLoaded('events');
Monocle.Styles = {
  applyRules: function (elem, rules) {
    if (typeof rules != 'string') {
      var parts = [];
      for (var declaration in rules) {
        parts.push(declaration+": "+rules[declaration]+";")
      }
      rules = parts.join(" ");
    }
    elem.style.cssText += ';'+rules;
    return elem.style.cssText;
  },

  affix: function (elem, property, value) {
    var target = elem.style ? elem.style : elem;
    target[Monocle.Browser.CSSProps.toDOMProp(property)] = value;
  },

  setX: function (elem, x) {
    var s = elem.style;
    if (typeof x == "number") { x += "px"; }
    if (Monocle.Browser.has.transform3d) {
      s.webkitTransform = "translate3d("+x+", 0, 0)";
    } else {
      s.webkitTransform = "translateX("+x+")";
    }
    s.MozTransform = s.OTransform = s.transform = "translateX("+x+")";
    return x;
  },

  setY: function (elem, y) {
    var s = elem.style;
    if (typeof y == "number") { y += "px"; }
    if (Monocle.Browser.has.transform3d) {
      s.webkitTransform = "translate3d(0, "+y+", 0)";
    } else {
      s.webkitTransform = "translateY("+y+")";
    }
    s.MozTransform = s.OTransform = s.transform = "translateY("+y+")";
    return y;
  }
}


Monocle.Styles.container = {
  "position": "absolute",
  "top": "0",
  "left": "0",
  "bottom": "0",
  "right": "0"
}

Monocle.Styles.page = {
  "position": "absolute",
  "z-index": "1",
  "-webkit-user-select": "none",
  "-moz-user-select": "none",
  "user-select": "none",
  "-webkit-transform": "translate3d(0,0,0)"

  /*
  "background": "white",
  "top": "0",
  "left": "0",
  "bottom": "0",
  "right": "0"
  */
}

Monocle.Styles.sheaf = {
  "position": "absolute",
  "overflow": "hidden" // Required by MobileSafari to constrain inner iFrame.

  /*
  "top": "0",
  "left": "0",
  "bottom": "0",
  "right": "0"
  */
}

Monocle.Styles.component = {
  "display": "block",
  "width": "100%",
  "height": "100%",
  "border": "none",
  "overflow": "hidden",
  "-webkit-user-select": "none",
  "-moz-user-select": "none",
  "user-select": "none"
}

Monocle.Styles.control = {
  "z-index": "100",
  "cursor": "pointer"
}

Monocle.Styles.overlay = {
  "position": "absolute",
  "display": "none",
  "width": "100%",
  "height": "100%",
  "z-index": "1000"
}



Monocle.pieceLoaded('styles');
Monocle.Reader = function (node, bookData, options, onLoadCallback) {
  if (Monocle == this) {
    return new Monocle.Reader(node, bookData, options, onLoadCallback);
  }

  var API = { constructor: Monocle.Reader }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    initialized: false,

    book: null,

    graph: {},

    pageStylesheets: [],

    systemId: (options ? options.systemId : null) || k.DEFAULT_SYSTEM_ID,

    classPrefix: k.DEFAULT_CLASS_PREFIX,

    controls: [],

    resizeTimer: null
  }

  var dom;


  function initialize(node, bookData, options, onLoadCallback) {
    var box = typeof(node) == "string" ?  document.getElementById(node) : node;
    dom = API.dom = box.dom = new Monocle.Factory(box, 'box', 0, API);

    options = options || {}

    dispatchEvent("monocle:initializing");

    var bk;
    if (bookData) {
      bk = new Monocle.Book(bookData);
    } else {
      bk = Monocle.Book.fromNodes([box.cloneNode(true)]);
    }
    box.innerHTML = "";

    positionBox();

    attachFlipper(options.flipper);

    createReaderElements();

    p.defaultStyles = addPageStyles(k.DEFAULT_STYLE_RULES, false);
    if (options.stylesheet) {
      p.initialStyles = addPageStyles(options.stylesheet, false);
    }

    primeFrames(options.primeURL, function () {
      applyStyles();

      listen('monocle:componentchange', persistPageStylesOnComponentChange);

      p.flipper.listenForInteraction(options.panels);

      setBook(bk, options.place, function () {
        p.initialized = true;
        if (onLoadCallback) { onLoadCallback(API); }
        dispatchEvent("monocle:loaded");
      });
    });
  }


  function positionBox() {
    var currPosVal;
    var box = dom.find('box');
    if (document.defaultView) {
      var currStyle = document.defaultView.getComputedStyle(box, null);
      currPosVal = currStyle.getPropertyValue('position');
    } else if (box.currentStyle) {
      currPosVal = box.currentStyle.position
    }
    if (["absolute", "relative"].indexOf(currPosVal) == -1) {
      box.style.position = "relative";
    }
  }


  function attachFlipper(flipperClass) {
    if (!Monocle.Browser.has.columns) {
      flipperClass = Monocle.Flippers[k.FLIPPER_LEGACY_CLASS];
      if (!flipperClass) {
        return dom.append(
          'div',
          'abortMsg',
          { 'class': k.abortMessage.CLASSNAME, 'html': k.abortMessage.TEXT }
        );
      }
    } else if (!flipperClass) {
      flipperClass = Monocle.Flippers[k.FLIPPER_DEFAULT_CLASS];
      if (!flipperClass) {
        throw("No flipper class");
      }
    }
    p.flipper = new flipperClass(API, null, p.readerOptions);
  }


  function createReaderElements() {
    var cntr = dom.append('div', 'container');
    for (var i = 0; i < p.flipper.pageCount; ++i) {
      var page = cntr.dom.append('div', 'page', i);
      page.m = { reader: API, pageIndex: i, place: null }
      page.m.sheafDiv = page.dom.append('div', 'sheaf', i);
      page.m.activeFrame = page.m.sheafDiv.dom.append('iframe', 'component', i);
      page.m.activeFrame.m = { 'pageDiv': page }
      p.flipper.addPage(page);
      Monocle.Events.listenOnIframe(page.m.activeFrame);
    }
    dom.append('div', 'overlay');
    dispatchEvent("monocle:loading");
  }


  function primeFrames(url, callback) {
    url = url || "about:blank";

    var pageMax = p.flipper.pageCount;
    var pageCount = 0;

    var cb = function (evt) {
      var frame = evt.target || evt.srcElement;
      Monocle.Events.deafen(frame, 'load', cb);
      if (Monocle.Browser.is.WebKit) {
        frame.contentDocument.documentElement.style.overflow = "hidden";
      }
      dispatchEvent('monocle:frameprimed', { frame: frame, pageIndex: pageCount });
      if ((pageCount += 1) == pageMax) {
        Monocle.defer(callback);
      }
    }

    for (var i = 0; i < pageMax; ++i) {
      var page = dom.find('page', i);
      page.m.activeFrame.style.visibility = "hidden";
      page.m.activeFrame.setAttribute('frameBorder', 0);
      page.m.activeFrame.setAttribute('scrolling', 'no');
      Monocle.Events.listen(page.m.activeFrame, 'load', cb);
      page.m.activeFrame.src = url;
    }
  }


  function applyStyles() {
    dom.find('container').dom.setStyles(Monocle.Styles.container);
    for (var i = 0; i < p.flipper.pageCount; ++i) {
      var page = dom.find('page', i);
      page.dom.setStyles(Monocle.Styles.page);
      dom.find('sheaf', i).dom.setStyles(Monocle.Styles.sheaf);
      var cmpt = dom.find('component', i)
      cmpt.dom.setStyles(Monocle.Styles.component);
      Monocle.Styles.applyRules(cmpt.contentDocument.body, Monocle.Styles.body);
    }
    lockFrameWidths();
    dom.find('overlay').dom.setStyles(Monocle.Styles.overlay);
    dispatchEvent('monocle:styles');
  }


  function lockingFrameWidths() {
    if (!Monocle.Browser.has.relativeIframeWidthBug) { return; }
    for (var i = 0, cmpt; cmpt = dom.find('component', i); ++i) {
      cmpt.style.display = "none";
    }
  }


  function lockFrameWidths() {
    if (!Monocle.Browser.has.relativeIframeWidthBug) { return; }
    for (var i = 0, cmpt; cmpt = dom.find('component', i); ++i) {
      cmpt.style.width = cmpt.parentNode.offsetWidth+"px";
      cmpt.style.display = "block";
    }
  }


  function setBook(bk, place, callback) {
    p.book = bk;
    var pageCount = 0;
    if (typeof callback == 'function') {
      var watcher = function (evt) {
        dispatchEvent('monocle:firstcomponentchange', evt.m);
        if ((pageCount += 1) == p.flipper.pageCount) {
          deafen('monocle:componentchange', watcher);
          callback();
        }
      }
      listen('monocle:componentchange', watcher);
    }
    p.flipper.moveTo(place || { page: 1 });
  }


  function getBook() {
    return p.book;
  }


  function resized() {
    if (!p.initialized) {
      console.warn('Attempt to resize book before initialization.');
    }
    lockingFrameWidths();
    if (!dispatchEvent("monocle:resizing", {}, true)) {
      return;
    }
    clearTimeout(p.resizeTimer);
    p.resizeTimer = setTimeout(
      function () {
        lockFrameWidths();
        p.flipper.moveTo({ page: pageNumber() });
        dispatchEvent("monocle:resize");
      },
      k.durations.RESIZE_DELAY
    );
  }


  function pageNumber(pageDiv) {
    var place = getPlace(pageDiv);
    return place ? (place.pageNumber() || 1) : 1;
  }


  function getPlace(pageDiv) {
    if (!p.initialized) {
      console.warn('Attempt to access place before initialization.');
    }
    return p.flipper.getPlace(pageDiv);
  }


  function moveTo(locus, callback) {
    if (!p.initialized) {
      console.warn('Attempt to move place before initialization.');
    }
    var fn = callback;
    if (!locus.direction) {
      dispatchEvent('monocle:jumping', { locus: locus });
      fn = function () {
        dispatchEvent('monocle:jump', { locus: locus });
        if (callback) { callback(); }
      }
    }
    p.flipper.moveTo(locus, fn);
  }


  function skipToChapter(src) {
    var locus = p.book.locusOfChapter(src);
    if (locus) {
      moveTo(locus);
      return true;
    } else {
      dispatchEvent("monocle:notfound", { href: src });
      return false;
    }
  }


  function addControl(ctrl, cType, options) {
    for (var i = 0; i < p.controls.length; ++i) {
      if (p.controls[i].control == ctrl) {
        console.warn("Already added control: " + ctrl);
        return;
      }
    }

    options = options || {};

    var ctrlData = {
      control: ctrl,
      elements: [],
      controlType: cType
    }
    p.controls.push(ctrlData);

    var ctrlElem;
    var cntr = dom.find('container'), overlay = dom.find('overlay');
    if (!cType || cType == "standard") {
      ctrlElem = ctrl.createControlElements(cntr);
      cntr.appendChild(ctrlElem);
      ctrlData.elements.push(ctrlElem);
    } else if (cType == "page") {
      for (var i = 0; i < p.flipper.pageCount; ++i) {
        var page = dom.find('page', i);
        var runner = ctrl.createControlElements(page);
        page.appendChild(runner);
        ctrlData.elements.push(runner);
      }
    } else if (cType == "modal" || cType == "popover" || cType == "hud") {
      ctrlElem = ctrl.createControlElements(overlay);
      overlay.appendChild(ctrlElem);
      ctrlData.elements.push(ctrlElem);
      ctrlData.usesOverlay = true;
    } else if (cType == "invisible") {
      if (
        typeof(ctrl.createControlElements) == "function" &&
        (ctrlElem = ctrl.createControlElements(cntr))
      ) {
        cntr.appendChild(ctrlElem);
        ctrlData.elements.push(ctrlElem);
      }
    } else {
      console.warn("Unknown control type: " + cType);
    }

    for (var i = 0; i < ctrlData.elements.length; ++i) {
      Monocle.Styles.applyRules(ctrlData.elements[i], Monocle.Styles.control);
    }

    if (options.hidden) {
      hideControl(ctrl);
    } else {
      showControl(ctrl);
    }

    if (typeof ctrl.assignToReader == 'function') {
      ctrl.assignToReader(API);
    }

    return ctrl;
  }


  function dataForControl(ctrl) {
    for (var i = 0; i < p.controls.length; ++i) {
      if (p.controls[i].control == ctrl) {
        return p.controls[i];
      }
    }
  }


  function hideControl(ctrl) {
    var controlData = dataForControl(ctrl);
    if (!controlData) {
      console.warn("No data for control: " + ctrl);
      return;
    }
    if (controlData.hidden) {
      return;
    }
    for (var i = 0; i < controlData.elements.length; ++i) {
      controlData.elements[i].style.display = "none";
    }
    if (controlData.usesOverlay) {
      var overlay = dom.find('overlay');
      overlay.style.display = "none";
      Monocle.Events.deafenForContact(overlay, overlay.listeners);
    }
    controlData.hidden = true;
    if (ctrl.properties) {
      ctrl.properties.hidden = true;
    }
    dispatchEvent('controlhide', ctrl, false);
  }


  function showControl(ctrl) {
    var controlData = dataForControl(ctrl);
    if (!controlData) {
      console.warn("No data for control: " + ctrl);
      return false;
    }

    if (showingControl(ctrl)) {
      return false;
    }

    var overlay = dom.find('overlay');
    if (controlData.usesOverlay && controlData.controlType != "hud") {
      for (var i = 0, ii = p.controls.length; i < ii; ++i) {
        if (p.controls[i].usesOverlay && !p.controls[i].hidden) {
          return false;
        }
      }
      overlay.style.display = "block";
    }

    for (var i = 0; i < controlData.elements.length; ++i) {
      controlData.elements[i].style.display = "block";
    }

    if (controlData.controlType == "popover") {
      overlay.listeners = Monocle.Events.listenForContact(
        overlay,
        {
          start: function (evt) {
            var obj = evt.target || window.event.srcElement;
            do {
              if (obj == controlData.elements[0]) { return true; }
            } while (obj && (obj = obj.parentNode));
            hideControl(ctrl);
          },
          move: function (evt) {
            evt.preventDefault();
          }
        }
      );
    }
    controlData.hidden = false;
    if (ctrl.properties) {
      ctrl.properties.hidden = false;
    }
    dispatchEvent('controlshow', ctrl, false);
    return true;
  }


  function showingControl(ctrl) {
    var controlData = dataForControl(ctrl);
    return controlData.hidden == false;
  }


  function dispatchEvent(evtType, data, cancelable) {
    return Monocle.Events.dispatch(dom.find('box'), evtType, data, cancelable);
  }


  function listen(evtType, fn, useCapture) {
    Monocle.Events.listen(dom.find('box'), evtType, fn, useCapture);
  }


  function deafen(evtType, fn) {
    Monocle.Events.deafen(dom.find('box'), evtType, fn);
  }


  /* PAGE STYLESHEETS */

  function addPageStyles(styleRules, restorePlace) {
    return changingStylesheet(function () {
      p.pageStylesheets.push(styleRules);
      var sheetIndex = p.pageStylesheets.length - 1;

      for (var i = 0; i < p.flipper.pageCount; ++i) {
        var doc = dom.find('component', i).contentDocument;
        addPageStylesheet(doc, sheetIndex);
      }
      return sheetIndex;
    }, restorePlace);
  }


  function updatePageStyles(sheetIndex, styleRules, restorePlace) {
    return changingStylesheet(function () {
      p.pageStylesheets[sheetIndex] = styleRules;
      if (typeof styleRules.join == "function") {
        styleRules = styleRules.join("\n");
      }
      for (var i = 0; i < p.flipper.pageCount; ++i) {
        var doc = dom.find('component', i).contentDocument;
        var styleTag = doc.getElementById('monStylesheet'+sheetIndex);
        if (!styleTag) {
          console.warn('No such stylesheet: ' + sheetIndex);
          return;
        }
        if (styleTag.styleSheet) {
          styleTag.styleSheet.cssText = styleRules;
        } else {
          styleTag.replaceChild(
            doc.createTextNode(styleRules),
            styleTag.firstChild
          );
        }
      }
    }, restorePlace);
  }


  function removePageStyles(sheetIndex, restorePlace) {
    return changingStylesheet(function () {
      p.pageStylesheets[sheetIndex] = null;
      for (var i = 0; i < p.flipper.pageCount; ++i) {
        var doc = dom.find('component', i).contentDocument;
        var styleTag = doc.getElementById('monStylesheet'+sheetIndex);
        styleTag.parentNode.removeChild(styleTag);
      }
    }, restorePlace);
  }


  function persistPageStylesOnComponentChange(evt) {
    var doc = evt.m['document'];
    doc.documentElement.id = p.systemId;
    for (var i = 0; i < p.pageStylesheets.length; ++i) {
      if (p.pageStylesheets[i]) {
        addPageStylesheet(doc, i);
      }
    }
  }


  function changingStylesheet(callback, restorePlace) {
    restorePlace = (restorePlace === false) ? false : true;
    if (restorePlace) {
      dispatchEvent("monocle:stylesheetchanging", {});
    }
    var result = callback();
    if (restorePlace) {
      p.flipper.moveTo({ page: pageNumber() });
      Monocle.defer(
        function () { dispatchEvent("monocle:stylesheetchange", {}); }
      );
    }
    return result;
  }


  function addPageStylesheet(doc, sheetIndex) {
    var styleRules = p.pageStylesheets[sheetIndex];

    if (!styleRules) {
      return;
    }

    var head = doc.getElementsByTagName('head')[0];
    if (!head) {
      if (!doc.documentElement) { return; } // FIXME: IE doesn't like docElem.
      head = doc.createElement('head');
      doc.documentElement.appendChild(head);
    }

    if (typeof styleRules.join == "function") {
      styleRules = styleRules.join("\n");
    }

    var styleTag = doc.createElement('style');
    styleTag.type = 'text/css';
    styleTag.id = "monStylesheet"+sheetIndex;
    if (styleTag.styleSheet) {
      styleTag.styleSheet.cssText = styleRules;
    } else {
      styleTag.appendChild(doc.createTextNode(styleRules));
    }

    head.appendChild(styleTag);

    return styleTag;
  }


  function visiblePages() {
    return p.flipper.visiblePages ? p.flipper.visiblePages() : [dom.find('page')];
  }


  API.getBook = getBook;
  API.getPlace = getPlace;
  API.moveTo = moveTo;
  API.skipToChapter = skipToChapter;
  API.resized = resized;
  API.addControl = addControl;
  API.hideControl = hideControl;
  API.showControl = showControl;
  API.showingControl = showingControl;
  API.dispatchEvent = dispatchEvent;
  API.listen = listen;
  API.deafen = deafen;
  API.addPageStyles = addPageStyles;
  API.updatePageStyles = updatePageStyles;
  API.removePageStyles = removePageStyles;
  API.visiblePages = visiblePages;

  initialize(node, bookData, options, onLoadCallback);

  return API;
}

Monocle.Reader.durations = {
  RESIZE_DELAY: 100
}
Monocle.Reader.abortMessage = {
  CLASSNAME: "monocleAbortMessage",
  TEXT: "Your browser does not support this technology."
}
Monocle.Reader.DEFAULT_SYSTEM_ID = 'RS:monocle'
Monocle.Reader.DEFAULT_CLASS_PREFIX = 'monelem_'
Monocle.Reader.FLIPPER_DEFAULT_CLASS = "Slider";
Monocle.Reader.FLIPPER_LEGACY_CLASS = "Legacy";
Monocle.Reader.DEFAULT_STYLE_RULES = [
  "html#RS\\:monocle * {" +
    "-webkit-font-smoothing: subpixel-antialiased;" +
    "text-rendering: auto !important;" +
    "word-wrap: break-word !important;" +
    "overflow: visible !important;" +
    (Monocle.Browser.has.floatColumnBug ? "float: none !important;" : "") +
  "}",
  "html#RS\\:monocle body {" +
    "margin: 0 !important;" +
    "padding: 0 !important;" +
    "-webkit-text-size-adjust: none;" +
  "}",
  "html#RS\\:monocle body * {" +
    "max-width: 100% !important;" +
  "}",
  "html#RS\\:monocle img, html#RS\\:monocle video, html#RS\\:monocle object {" +
    "max-height: 95% !important;" +
  "}"
]

if (Monocle.Browser.has.columnOverflowPaintBug) {
  Monocle.Reader.DEFAULT_STYLE_RULES.push(
    "::-webkit-scrollbar { width: 0; height: 0; }"
  )
}


Monocle.pieceLoaded('reader');
/* BOOK */

/* The Book handles movement through the content by the reader page elements.
 *
 * It's responsible for instantiating components as they are required,
 * and for calculating which component and page number to move to (based on
 * requests from the Reader).
 *
 * It should set and know the place of each page element too.
 *
 */
Monocle.Book = function (dataSource) {
  if (Monocle == this) { return new Monocle.Book(dataSource); }

  var API = { constructor: Monocle.Book }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    dataSource: dataSource,
    components: [],
    chapters: {} // flat arrays of chapters per component
  }


  function initialize() {
    p.componentIds = dataSource.getComponents();
    p.contents = dataSource.getContents();
    p.lastCIndex = p.componentIds.length - 1;
  }


  function pageNumberAt(pageDiv, locus) {
    locus.load = false;
    var currComponent = pageDiv.m.activeFrame ?
      pageDiv.m.activeFrame.m.component :
      null;
    var component = null;
    var cIndex = p.componentIds.indexOf(locus.componentId);
    if (cIndex < 0 && !currComponent) {
      locus.load = true;
      locus.componentId = p.componentIds[0];
      return locus;
    } else if (
      cIndex < 0 &&
      locus.componentId &&
      currComponent.properties.id != locus.componentId
    ) {
      pageDiv.m.reader.dispatchEvent(
        "monocle:notfound",
        { href: locus.componentId }
      );
      return null;
    } else if (cIndex < 0) {
      component = currComponent;
      locus.componentId = pageDiv.m.activeFrame.m.component.properties.id;
      cIndex = p.componentIds.indexOf(locus.componentId);
    } else if (!p.components[cIndex] || p.components[cIndex] != currComponent) {
      locus.load = true;
      return locus;
    } else {
      component = currComponent;
    }

    var result = { load: false, componentId: locus.componentId, page: 1 }

    var lastPageNum = { 'old': component.lastPageNumber() }
    var changedDims = component.updateDimensions(pageDiv);
    lastPageNum['new'] = component.lastPageNumber();

    if (typeof(locus.page) == "number") {
      result.page = locus.page;
    } else if (typeof(locus.pagesBack) == "number") {
      result.page = lastPageNum['new'] + locus.pagesBack;
    } else if (typeof(locus.percent) == "number") {
      var place = new Monocle.Place();
      place.setPlace(component, 1);
      result.page = place.pageAtPercentageThrough(locus.percent);
    } else if (typeof(locus.direction) == "number") {
      if (!pageDiv.m.place) {
        console.warn("Can't move in a direction if pageDiv has no place.");
      }
      result.page = pageDiv.m.place.pageNumber();
      result.page += locus.direction;
    } else if (typeof(locus.anchor) == "string") {
      result.page = component.pageForChapter(locus.anchor, pageDiv);
    } else if (typeof(locus.xpath) == "string") {
      result.page = component.pageForXPath(locus.xpath, pageDiv);
    } else if (typeof(locus.position) == "string") {
      if (locus.position == "start") {
        result.page = 1;
      } else if (locus.position == "end") {
        result.page = lastPageNum['new'];
      }
    } else {
      console.warn("Unrecognised locus: " + locus);
    }

    if (changedDims && lastPageNum['old']) {
      result.page = Math.round(
        lastPageNum['new'] * (result.page / lastPageNum['old'])
      );
    }

    if (result.page < 1) {
      if (cIndex == 0) {
        result.page = 1;
        result.boundarystart = true;
      } else {
        result.load = true;
        result.componentId = p.componentIds[cIndex - 1];
        result.pagesBack = result.page;
        result.page = null;
      }
    } else if (result.page > lastPageNum['new']) {
      if (cIndex == p.lastCIndex) {
        result.page = lastPageNum['new'];
        result.boundaryend = true;
      } else {
        result.load = true;
        result.componentId = p.componentIds[cIndex + 1];
        result.page -= lastPageNum['new'];
      }
    }

    return result;
  }


  function setPageAt(pageDiv, locus) {
    locus = pageNumberAt(pageDiv, locus);
    if (locus && !locus.load) {
      var evtData = { locus: locus, page: pageDiv }
      if (locus.boundarystart) {
        pageDiv.m.reader.dispatchEvent('monocle:boundarystart', evtData);
      } else if (locus.boundaryend) {
        pageDiv.m.reader.dispatchEvent('monocle:boundaryend', evtData);
      } else {
        var component = p.components[p.componentIds.indexOf(locus.componentId)];
        pageDiv.m.place = pageDiv.m.place || new Monocle.Place();
        pageDiv.m.place.setPlace(component, locus.page);

        var evtData = {
          page: pageDiv,
          locus: locus,
          pageNumber: pageDiv.m.place.pageNumber(),
          componentId: locus.componentId
        }
        pageDiv.m.reader.dispatchEvent("monocle:pagechange", evtData);
      }
    }
    return locus;
  }


  function loadPageAt(pageDiv, locus, callback, progressCallback) {
    var cIndex = p.componentIds.indexOf(locus.componentId);
    if (!locus.load || cIndex < 0) {
      locus = pageNumberAt(pageDiv, locus);
    }

    if (!locus) {
      return;
    }

    if (!locus.load) {
      callback(locus);
      return;
    }

    var findPageNumber = function () {
      locus = setPageAt(pageDiv, locus);
      if (!locus) {
        return;
      } else if (locus.load) {
        loadPageAt(pageDiv, locus, callback, progressCallback)
      } else {
        callback(locus);
      }
    }

    var pgFindPageNumber = function () {
      progressCallback ? progressCallback(findPageNumber) : findPageNumber();
    }

    var applyComponent = function (component) {
      component.applyTo(pageDiv, pgFindPageNumber);
    }

    var pgApplyComponent = function (component) {
      progressCallback ?
        progressCallback(function () { applyComponent(component) }) :
        applyComponent(component);
    }

    loadComponent(cIndex, pgApplyComponent, pageDiv);
  }


  function setOrLoadPageAt(pageDiv, locus, callback, onProgress, onFail) {
    locus = setPageAt(pageDiv, locus);
    if (!locus) {
      if (onFail) { onFail(); }
    } else if (locus.load) {
      loadPageAt(pageDiv, locus, callback, onProgress);
    } else {
      callback(locus);
    }
  }


  function loadComponent(index, callback, pageDiv) {
    if (p.components[index]) {
      return callback(p.components[index]);
    }
    var cmptId = p.componentIds[index];
    if (pageDiv) {
      var evtData = { 'page': pageDiv, 'component': cmptId, 'index': index };
      pageDiv.m.reader.dispatchEvent('monocle:componentloading', evtData);
    }
    var fn = function (cmptSource) {
      if (pageDiv) {
        evtData['source'] = cmptSource;
        pageDiv.m.reader.dispatchEvent('monocle:componentloaded', evtData);
        html = evtData['html'];
      }
      p.components[index] = new Monocle.Component(
        API,
        cmptId,
        index,
        chaptersForComponent(cmptId),
        cmptSource
      );
      callback(p.components[index]);
    }
    var cmptSource = p.dataSource.getComponent(cmptId, fn);
    if (cmptSource && !p.components[index]) {
      fn(cmptSource);
    }
  }


  function chaptersForComponent(cmptId) {
    if (p.chapters[cmptId]) {
      return p.chapters[cmptId];
    }
    p.chapters[cmptId] = [];
    var matcher = new RegExp('^'+cmptId+"(\#(.+)|$)");
    var matches;
    var recurser = function (chp) {
      if (matches = chp.src.match(matcher)) {
        p.chapters[cmptId].push({
          title: chp.title,
          fragment: matches[2] || null
        });
      }
      if (chp.children) {
        for (var i = 0; i < chp.children.length; ++i) {
          recurser(chp.children[i]);
        }
      }
    }

    for (var i = 0; i < p.contents.length; ++i) {
      recurser(p.contents[i]);
    }
    return p.chapters[cmptId];
  }


  function locusOfChapter(src) {
    var matcher = new RegExp('^(.+?)(#(.*))?$');
    var matches = src.match(matcher);
    if (!matches) { return null; }
    var cmptId = componentIdMatching(matches[1]);
    if (!cmptId) { return null; }
    var locus = { componentId: cmptId }
    matches[3] ? locus.anchor = matches[3] : locus.position = "start";
    return locus;
  }


  function componentIdMatching(str) {
    return p.componentIds.indexOf(str) >= 0 ? str : null;
  }


  API.getMetaData = dataSource.getMetaData;
  API.pageNumberAt = pageNumberAt;
  API.setPageAt = setPageAt;
  API.loadPageAt = loadPageAt;
  API.setOrLoadPageAt = setOrLoadPageAt;
  API.chaptersForComponent = chaptersForComponent;
  API.locusOfChapter = locusOfChapter;

  initialize();

  return API;
}


Monocle.Book.fromNodes = function (nodes) {
  var bookData = {
    getComponents: function () {
      return ['anonymous'];
    },
    getContents: function () {
      return [];
    },
    getComponent: function (n) {
      return { 'nodes': nodes };
    },
    getMetaData: function (key) {
    }
  }

  return new Monocle.Book(bookData);
}

Monocle.pieceLoaded('book');

Monocle.Place = function () {

  var API = { constructor: Monocle.Place }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    component: null,
    percent: null
  }


  function setPlace(cmpt, pageN) {
    p.component = cmpt;
    p.percent = pageN / cmpt.lastPageNumber();
    p.chapter = null;
  }


  function setPercentageThrough(cmpt, percent) {
    p.component = cmpt;
    p.percent = percent;
    p.chapter = null;
  }


  function componentId() {
    return p.component.properties.id;
  }


  function percentAtTopOfPage() {
    return p.percent - 1.0 / p.component.lastPageNumber();
  }


  function percentAtBottomOfPage() {
    return p.percent;
  }


  function pageAtPercentageThrough(percent) {
    return Math.max(Math.round(p.component.lastPageNumber() * percent), 1);
  }


  function pageNumber() {
    return pageAtPercentageThrough(p.percent);
  }


  function chapterInfo() {
    if (p.chapter) {
      return p.chapter;
    }
    return p.chapter = p.component.chapterForPage(pageNumber());
  }


  function chapterTitle() {
    var chp = chapterInfo();
    return chp ? chp.title : null;
  }


  function chapterSrc() {
    var src = componentId();
    var cinfo = chapterInfo();
    if (cinfo && cinfo.fragment) {
      src += "#" + cinfo.fragment;
    }
    return src;
  }


  function getLocus(options) {
    options = options || {};
    var locus = {
      page: pageNumber(),
      componentId: componentId()
    }
    if (options.direction) {
      locus.page += options.direction;
    } else {
      locus.percent = percentAtBottomOfPage();
    }
    return locus;
  }


  function percentageOfBook() {
    componentIds = p.component.properties.book.properties.componentIds;
    componentSize = 1.0 / componentIds.length;
    var pc = componentIds.indexOf(componentId()) * componentSize;
    pc += componentSize * p.percent;
    return pc;
  }


  function onFirstPageOfBook() {
    return p.component.properties.index == 0 && pageNumber() == 1;
  }


  function onLastPageOfBook() {
    return (
      p.component.properties.index ==
        p.component.properties.book.properties.lastCIndex &&
      pageNumber() == p.component.lastPageNumber()
    );
  }


  API.setPlace = setPlace;
  API.setPercentageThrough = setPercentageThrough;
  API.componentId = componentId;
  API.percentAtTopOfPage = percentAtTopOfPage;
  API.percentAtBottomOfPage = percentAtBottomOfPage;
  API.percentageThrough = percentAtBottomOfPage;
  API.pageAtPercentageThrough = pageAtPercentageThrough;
  API.pageNumber = pageNumber;
  API.chapterInfo = chapterInfo;
  API.chapterTitle = chapterTitle;
  API.chapterSrc = chapterSrc;
  API.getLocus = getLocus;
  API.percentageOfBook = percentageOfBook;
  API.onFirstPageOfBook = onFirstPageOfBook;
  API.onLastPageOfBook = onLastPageOfBook;

  return API;
}


Monocle.Place.FromPageNumber = function (component, pageNumber) {
  var place = new Monocle.Place();
  place.setPlace(component, pageNumber);
  return place;
}

Monocle.Place.FromPercentageThrough = function (component, percent) {
  var place = new Monocle.Place();
  place.setPercentageThrough(component, percent);
  return place;
}

Monocle.pieceLoaded('place');
/* COMPONENT */

Monocle.Component = function (book, id, index, chapters, source) {

  var API = { constructor: Monocle.Component }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    book: book,

    id: id,

    index: index,

    chapters: chapters,

    source: source
  }


  function applyTo(pageDiv, callback) {
    var evtData = { 'page': pageDiv, 'source': p.source };
    pageDiv.m.reader.dispatchEvent('monocle:componentchanging', evtData);

    return loadFrame(
      pageDiv,
      function () {
        setupFrame(pageDiv, pageDiv.m.activeFrame);
        callback(pageDiv, API);
      }
    );
  }


  function loadFrame(pageDiv, callback) {
    var frame = pageDiv.m.activeFrame;

    frame.m.component = API;

    frame.style.visibility = "hidden";


    if (p.source.html || (typeof p.source == "string")) {   // HTML
      return loadFrameFromHTML(p.source.html || p.source, frame, callback);
    } else if (p.source.url) {                              // URL
      return loadFrameFromURL(p.source.url, frame, callback);
    } else if (p.source.nodes) {                            // NODES
      return loadFrameFromNodes(p.source.nodes, frame, callback);
    } else if (p.source.doc) {                              // DOCUMENT
      return loadFrameFromDocument(p.source.doc, frame, callback);
    }
  }


  function loadFrameFromHTML(src, frame, callback) {
    src = src.replace(/\s+/g, ' ');

    src = src.replace(/\'/g, '\\\'');


    if (Monocle.Browser.is.Gecko) {
      var doctypeFragment = "<!DOCTYPE[^>]*>";
      src = src.replace(new RegExp(doctypeFragment, 'm'), '');
    }

    src = "javascript: '" + src + "';";

    frame.onload = function () {
      frame.onload = null;
      Monocle.defer(callback);
    }
    frame.src = src;
  }


  function loadFrameFromURL(url, frame, callback) {
    if (!url.match(/^\//)) {
      var link = document.createElement('a');
      link.setAttribute('href', url);
      url = link.href;
      delete(link);
    }
    frame.onload = function () {
      frame.onload = null;
      Monocle.defer(callback);
    }
    frame.contentWindow.location.replace(url);
  }


  function loadFrameFromNodes(nodes, frame, callback) {
    var destDoc = frame.contentDocument;
    destDoc.documentElement.innerHTML = "";
    var destHd = destDoc.createElement("head");
    var destBdy = destDoc.createElement("body");

    for (var i = 0; i < nodes.length; ++i) {
      var node = destDoc.importNode(nodes[i], true);
      destBdy.appendChild(node);
    }

    var oldHead = destDoc.getElementsByTagName('head')[0];
    if (oldHead) {
      destDoc.documentElement.replaceChild(destHd, oldHead);
    } else {
      destDoc.documentElement.appendChild(destHd);
    }
    if (destDoc.body) {
      destDoc.documentElement.replaceChild(destBdy, destDoc.body);
    } else {
      destDoc.documentElement.appendChild(destBdy);
    }

    if (callback) { callback(); }
  }


  function loadFrameFromDocument(srcDoc, frame, callback) {
    var destDoc = frame.contentDocument;

    var srcBases = srcDoc.getElementsByTagName('base');
    if (srcBases[0]) {
      var head = destDoc.getElementsByTagName('head')[0];
      if (!head) {
        try {
          head = destDoc.createElement('head');
          if (destDoc.body) {
            destDoc.insertBefore(head, destDoc.body);
          } else {
            destDoc.appendChild(head);
          }
        } catch (e) {
          head = destDoc.body;
        }
      }
      var bases = destDoc.getElementsByTagName('base');
      var base = bases[0] ? bases[0] : destDoc.createElement('base');
      base.setAttribute('href', srcBases[0].getAttribute('href'));
      head.appendChild(base);
    }

    destDoc.replaceChild(
      destDoc.importNode(srcDoc.documentElement, true),
      destDoc.documentElement
    );


    Monocle.defer(callback);
  }


  function setupFrame(pageDiv, frame) {
    Monocle.Events.listenOnIframe(frame);

    var evtData = {
      'page': pageDiv,
      'document': frame.contentDocument,
      'component': API
    };
    pageDiv.m.reader.dispatchEvent('monocle:componentchange', evtData);

    var doc = frame.contentDocument;
    var win = doc.defaultView;
    var currStyle = win.getComputedStyle(doc.body, null);
    var lh = parseFloat(currStyle.getPropertyValue('line-height'));
    var fs = parseFloat(currStyle.getPropertyValue('font-size'));
    doc.body.style.lineHeight = lh / fs;

    p.pageLength = pageDiv.m.dimensions.measure();
    frame.style.visibility = "visible";

    locateChapters(pageDiv);
  }


  function updateDimensions(pageDiv) {
    if (pageDiv.m.dimensions.hasChanged()) {
      p.pageLength = pageDiv.m.dimensions.measure();
      return true;
    } else {
      return false;
    }
  }


  function locateChapters(pageDiv) {
    if (p.chapters[0] && typeof p.chapters[0].percent == "number") {
      return;
    }
    var doc = pageDiv.m.activeFrame.contentDocument;
    for (var i = 0; i < p.chapters.length; ++i) {
      var chp = p.chapters[i];
      chp.percent = 0;
      if (chp.fragment) {
        var node = doc.getElementById(chp.fragment);
        chp.percent = pageDiv.m.dimensions.percentageThroughOfNode(node);
      }
    }
    return p.chapters;
  }


  function chapterForPage(pageN) {
    var cand = null;
    var percent = (pageN - 1) / p.pageLength;
    for (var i = 0; i < p.chapters.length; ++i) {
      if (percent >= p.chapters[i].percent) {
        cand = p.chapters[i];
      } else {
        return cand;
      }
    }
    return cand;
  }


  function pageForChapter(fragment, pageDiv) {
    if (!fragment) {
      return 1;
    }
    for (var i = 0; i < p.chapters.length; ++i) {
      if (p.chapters[i].fragment == fragment) {
        return percentToPageNumber(p.chapters[i].percent);
      }
    }
    var doc = pageDiv.m.activeFrame.contentDocument;
    var node = doc.getElementById(fragment);
    var percent = pageDiv.m.dimensions.percentageThroughOfNode(node);
    return percentToPageNumber(percent);
  }


  function pageForXPath(xpath, pageDiv) {
    var doc = pageDiv.m.activeFrame.contentDocument;
    var percent = 0;
    if (typeof doc.evaluate == "function") {
      var node = doc.evaluate(
        xpath,
        doc,
        null,
        9,
        null
      ).singleNodeValue;
      var percent = pageDiv.m.dimensions.percentageThroughOfNode(node);
    }
    return percentToPageNumber(percent);
  }


  function percentToPageNumber(pc) {
    return Math.floor(pc * p.pageLength) + 1;
  }


  function lastPageNumber() {
    return p.pageLength;
  }


  API.applyTo = applyTo;
  API.updateDimensions = updateDimensions;
  API.chapterForPage = chapterForPage;
  API.pageForChapter = pageForChapter;
  API.pageForXPath = pageForXPath;
  API.lastPageNumber = lastPageNumber;

  return API;
}

Monocle.pieceLoaded('component');

Monocle.Dimensions = {}
Monocle.Controls = {};
Monocle.Flippers = {};
Monocle.Panels = {};

Monocle.Controls.Panel = function () {

  var API = { constructor: Monocle.Controls.Panel }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    evtCallbacks: {}
  }

  function createControlElements(cntr) {
    p.div = cntr.dom.make('div', k.CLS.panel);
    p.div.dom.setStyles(k.DEFAULT_STYLES);
    Monocle.Events.listenForContact(
      p.div,
      {
        'start': start,
        'move': move,
        'end': end,
        'cancel': cancel
      },
      { useCapture: false }
    );
    return p.div;
  }


  function listenTo(evtCallbacks) {
    p.evtCallbacks = evtCallbacks;
  }


  function deafen() {
    p.evtCallbacks = {}
  }


  function start(evt) {
    p.contact = true;
    evt.m.offsetX += p.div.offsetLeft;
    evt.m.offsetY += p.div.offsetTop;
    expand();
    invoke('start', evt);
  }


  function move(evt) {
    if (!p.contact) {
      return;
    }
    invoke('move', evt);
  }


  function end(evt) {
    if (!p.contact) {
      return;
    }
    Monocle.Events.deafenForContact(p.div, p.listeners);
    contract();
    p.contact = false;
    invoke('end', evt);
  }


  function cancel(evt) {
    if (!p.contact) {
      return;
    }
    Monocle.Events.deafenForContact(p.div, p.listeners);
    contract();
    p.contact = false;
    invoke('cancel', evt);
  }


  function invoke(evtType, evt) {
    if (p.evtCallbacks[evtType]) {
      p.evtCallbacks[evtType](API, evt.m.offsetX, evt.m.offsetY);
    }
    evt.preventDefault();
  }


  function expand() {
    if (p.expanded) {
      return;
    }
    p.div.dom.addClass(k.CLS.expanded);
    p.expanded = true;
  }


  function contract(evt) {
    if (!p.expanded) {
      return;
    }
    p.div.dom.removeClass(k.CLS.expanded);
    p.expanded = false;
  }


  API.createControlElements = createControlElements;
  API.listenTo = listenTo;
  API.deafen = deafen;
  API.expand = expand;
  API.contract = contract;

  return API;
}


Monocle.Controls.Panel.CLS = {
  panel: 'panel',
  expanded: 'controls_panel_expanded'
}
Monocle.Controls.Panel.DEFAULT_STYLES = {
  position: 'absolute',
  height: '100%'
}


Monocle.pieceLoaded('controls/panel');
Monocle.Panels.TwoPane = function (flipper, evtCallbacks) {

  var API = { constructor: Monocle.Panels.TwoPane }
  var k = API.constants = API.constructor;
  var p = API.properties = {}


  function initialize() {
    p.panels = {
      forwards: new Monocle.Controls.Panel(),
      backwards: new Monocle.Controls.Panel()
    }

    for (dir in p.panels) {
      flipper.properties.reader.addControl(p.panels[dir]);
      p.panels[dir].listenTo(evtCallbacks);
      p.panels[dir].properties.direction = flipper.constants[dir.toUpperCase()];
      var style = { "width": k.WIDTH };
      style[(dir == "forwards" ? "right" : "left")] = 0;
      p.panels[dir].properties.div.dom.setStyles(style);
    }
  }


  initialize();

  return API;
}

Monocle.Panels.TwoPane.WIDTH = "50%";

Monocle.pieceLoaded('panels/twopane');
Monocle.Dimensions.Vert = function (pageDiv) {

  var API = { constructor: Monocle.Dimensions.Vert }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    page: pageDiv,
    reader: pageDiv.m.reader
  }


  function initialize() {
    p.reader.listen('monocle:componentchange', componentChanged);
  }


  function hasChanged() {
    return getBodyHeight() != p.bodyHeight || getPageHeight != p.pageHeight;
  }


  function measure() {
    p.bodyHeight = getBodyHeight();
    p.pageHeight = getPageHeight();
    p.length = Math.ceil(p.bodyHeight / p.pageHeight);
    return p.length;
  }


  function pages() {
    return p.length;
  }


  function getBodyHeight() {
    return p.page.m.activeFrame.contentDocument.body.scrollHeight;
  }


  function getPageHeight() {
    return p.page.m.activeFrame.offsetHeight - k.GUTTER;
  }


  function percentageThroughOfNode(target) {
    if (!target) {
      return 0;
    }
    var doc = p.page.m.activeFrame.contentDocument;
    var offset = 0;
    if (target.getBoundingClientRect) {
      offset = target.getBoundingClientRect().top;
      offset -= doc.body.getBoundingClientRect().top;
    } else {
      var oldScrollTop = doc.body.scrollTop;
      target.scrollIntoView();
      offset = doc.body.scrollTop;
      doc.body.scrollLeft = 0;
      doc.body.scrollTop = oldScrollTop;
    }

    var percent = offset / p.bodyHeight;
    return percent;
  }


  function componentChanged(evt) {
    if (evt.m['page'] != p.page) { return; }
    var sheaf = p.page.m.sheafDiv;
    var cmpt = p.page.m.activeFrame;
    sheaf.dom.setStyles(k.SHEAF_STYLES);
    cmpt.dom.setStyles(k.COMPONENT_STYLES);
    var doc = evt.m['document'];
    doc.documentElement.style.overflow = 'hidden';
    doc.body.style.marginRight = '10px !important';
    cmpt.contentWindow.scrollTo(0,0);
  }


  function locusToOffset(locus) {
    return p.pageHeight * (locus.page - 1);
  }


  API.hasChanged = hasChanged;
  API.measure = measure;
  API.pages = pages;
  API.percentageThroughOfNode = percentageThroughOfNode;
  API.locusToOffset = locusToOffset;

  initialize();

  return API;
}

Monocle.Dimensions.Vert.GUTTER = 10;
Monocle.Flippers.Legacy = function (reader) {

  var API = { constructor: Monocle.Flippers.Legacy }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    pageCount: 1,
    divs: {}
  }


  function initialize() {
    p.reader = reader;
  }


  function addPage(pageDiv) {
    pageDiv.m.dimensions = new Monocle.Dimensions.Vert(pageDiv);
  }


  function getPlace() {
    return page().m.place;
  }


  function moveTo(locus, callback) {
    var fn = frameToLocus;
    if (typeof callback == "function") {
      fn = function (locus) { frameToLocus(locus); callback(locus); }
    }
    p.reader.getBook().setOrLoadPageAt(page(), locus, fn);
  }


  function listenForInteraction(panelClass) {
    if (typeof panelClass != "function") {
      panelClass = k.DEFAULT_PANELS_CLASS;
      if (!panelClass) {
        console.warn("Invalid panel class.")
      }
    }
    p.panels = new panelClass(API, { 'end': turn });
  }


  function page() {
    return p.reader.dom.find('page');
  }


  function turn(panel) {
    var dir = panel.properties.direction;
    var place = getPlace();
    if (
      (dir < 0 && place.onFirstPageOfBook()) ||
      (dir > 0 && place.onLastPageOfBook())
    ) { return; }
    moveTo({ page: getPlace().pageNumber() + dir });
  }


  function frameToLocus(locus) {
    var cmpt = p.reader.dom.find('component');
    var win = cmpt.contentWindow;
    var srcY = scrollPos(win);
    var dims = page().m.dimensions;
    var pageHeight = dims.properties.pageHeight;
    var destY = dims.locusToOffset(locus);

    if (Math.abs(destY - srcY) > pageHeight) {
      return win.scrollTo(0, destY);
    }

    showIndicator(win, srcY < destY ? srcY + pageHeight : srcY);
    Monocle.defer(
      function () { smoothScroll(win, srcY, destY, 300, scrollingFinished); },
      150
    );
  }


  function scrollPos(win) {
    if (win.pageYOffset) {
      return win.pageYOffset;
    }
    if (win.document.documentElement && win.document.documentElement.scrollTop) {
      return win.document.documentElement.scrollTop;
    }
    if (win.document.body.scrollTop) {
      return win.document.body.scrollTop;
    }
    return 0;
  }


  function smoothScroll(win, currY, finalY, duration, callback) {
    clearTimeout(win.smoothScrollInterval);
    var stamp = (new Date()).getTime();
    var frameRate = 40;
    var step = (finalY - currY) * (frameRate / duration);
    var stepFn = function () {
      var destY = currY + step;
      if (
        (new Date()).getTime() - stamp > duration ||
        Math.abs(currY - finalY) < Math.abs((currY + step) - finalY)
      ) {
        clearTimeout(win.smoothScrollInterval);
        win.scrollTo(0, finalY);
        if (callback) { callback(); }
      } else {
        win.scrollTo(0, destY);
        currY = destY;
      }
    }
    win.smoothScrollInterval = setInterval(stepFn, frameRate);
  }


  function scrollingFinished() {
    hideIndicator(page().m.activeFrame.contentWindow);
    p.reader.dispatchEvent('monocle:turn');
  }


  function showIndicator(win, pos) {
    if (p.hideTO) { clearTimeout(p.hideTO); }

    var doc = win.document;
    if (!doc.body.indicator) {
      doc.body.indicator = createIndicator(doc);
      doc.body.appendChild(doc.body.indicator);
    }
    doc.body.indicator.line.style.display = "block";
    doc.body.indicator.style.opacity = 1;
    positionIndicator(pos);
  }


  function hideIndicator(win) {
    var doc = win.document;
    p.hideTO = Monocle.defer(
      function () {
        if (!doc.body.indicator) {
          doc.body.indicator = createIndicator(doc);
          doc.body.appendChild(doc.body.indicator);
        }
        var dims = page().m.dimensions;
        positionIndicator(
          dims.locusToOffset(getPlace().getLocus()) + dims.properties.pageHeight
        )
        doc.body.indicator.line.style.display = "none";
        doc.body.indicator.style.opacity = 0.5;
      },
      600
    );
  }


  function createIndicator(doc) {
    var iBox = doc.createElement('div');
    doc.body.appendChild(iBox);
    Monocle.Styles.applyRules(iBox, k.STYLES.iBox);

    iBox.arrow = doc.createElement('div');
    iBox.appendChild(iBox.arrow);
    Monocle.Styles.applyRules(iBox.arrow, k.STYLES.arrow);

    iBox.line = doc.createElement('div');
    iBox.appendChild(iBox.line);
    Monocle.Styles.applyRules(iBox.line, k.STYLES.line);

    return iBox;
  }


  function positionIndicator(y) {
    var p = page();
    var doc = p.m.activeFrame.contentDocument;
    var maxHeight = p.m.dimensions.properties.bodyHeight;
    maxHeight -= doc.body.indicator.offsetHeight;
    if (y > maxHeight) {
      y = maxHeight;
    }
    doc.body.indicator.style.top = y + "px";
  }


  API.pageCount = p.pageCount;
  API.addPage = addPage;
  API.getPlace = getPlace;
  API.moveTo = moveTo;
  API.listenForInteraction = listenForInteraction;

  initialize();

  return API;
}

Monocle.Flippers.Legacy.FORWARDS = 1;
Monocle.Flippers.Legacy.BACKWARDS = -1;
Monocle.Flippers.Legacy.DEFAULT_PANELS_CLASS = Monocle.Panels.TwoPane;

Monocle.Flippers.Legacy.STYLES = {
  iBox: {
    'position': 'absolute',
    'right': 0,
    'left': 0,
    'height': '10px'
  },
  arrow: {
    'position': 'absolute',
    'right': 0,
    'height': '10px',
    'width': '10px',
    'background': '#333',
    'border-radius': '6px'
  },
  line: {
    'width': '100%',
    'border-top': '2px dotted #333',
    'margin-top': '5px'
  }
}

Monocle.pieceLoaded('flippers/legacy');
Monocle.Dimensions.Columns = function (pageDiv) {

  var API = { constructor: Monocle.Dimensions.Columns }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    page: pageDiv,
    reader: pageDiv.m.reader,
    dirty: true
  }


  function initialize() {
    p.reader.listen('monocle:componentchange', componentChanged);
  }


  function hasChanged() {
    if (p.dirty) { return true; }
    var newMeasurements = rawMeasurements();
    return (
      (!p.measurements) ||
      (p.measurements.width != newMeasurements.width) ||
      (p.measurements.height != newMeasurements.height) ||
      (p.measurements.scrollWidth != newMeasurements.scrollWidth)
    );
  }


  function measure() {
    setColumnWidth();
    p.measurements = rawMeasurements();

    if (
      Monocle.Browser.has.iframeDoubleWidthBug &&
      p.measurements.scrollWidth == p.measurements.width * 2
    ) {
      var doc = p.page.m.activeFrame.contentDocument;
      var lc;
      for (var i = doc.body.childNodes.length - 1; i >= 0; --i) {
        lc = doc.body.childNodes[i];
        if (lc.getBoundingClientRect) { break; }
      }
      if (!lc || !lc.getBoundingClientRect) {
        console.warn('Empty document for page['+p.page.m.pageIndex+']');
        p.measurements.scrollWidth = p.measurements.width;
      } else {
        var bcr = lc.getBoundingClientRect();
        if (
          bcr.right > p.measurements.width ||
          bcr.bottom > p.measurements.height
        ) {
          p.measurements.scrollWidth = p.measurements.width * 2;
        } else {
          p.measurements.scrollWidth = p.measurements.width;
        }
      }
    }

    p.length = Math.ceil(p.measurements.scrollWidth / p.measurements.width);
    p.dirty = false;
    return p.length;
  }


  function pages() {
    if (p.dirty) {
      console.warn('Accessing pages() when dimensions are dirty.')
      return 0;
    }
    return p.length;
  }


  function percentageThroughOfNode(target) {
    if (!target) {
      return 0;
    }
    var doc = p.page.m.activeFrame.contentDocument;
    var offset = 0;
    if (target.getBoundingClientRect) {
      offset = target.getBoundingClientRect().left;
      offset -= doc.body.getBoundingClientRect().left;
    } else {
      var scroller = scrollerElement();
      var oldScrollLeft = scroller.scrollLeft;
      target.scrollIntoView();
      offset = scroller.scrollLeft;
      scroller.scrollTop = 0;
      scroller.scrollLeft = oldScrollLeft;
    }

    var percent = offset / p.measurements.scrollWidth;
    return percent;
  }


  function componentChanged(evt) {
    if (evt.m['page'] != p.page) { return; }
    var doc = evt.m['document'];
    if (Monocle.Browser.has.columnOverflowPaintBug) {
      var div = doc.createElement('div');
      Monocle.Styles.applyRules(div, k.BODY_STYLES);
      div.style.cssText += "overflow: scroll !important;";
      while (doc.body.childNodes.length) {
        div.appendChild(doc.body.firstChild);
      }
      doc.body.appendChild(div);
    } else {
      Monocle.Styles.applyRules(doc.body, k.BODY_STYLES);

      if (Monocle.Browser.is.WebKit) {
        doc.documentElement.style.overflow = 'hidden';
      }
    }

    p.dirty = true;
  }


  function setColumnWidth() {
    var cw = p.page.m.sheafDiv.clientWidth;
    if (currBodyStyleValue('column-width') != cw+"px") {
      Monocle.Styles.affix(columnedElement(), 'column-width', cw+"px");
      p.dirty = true;
    }
  }


  function rawMeasurements() {
    var sheaf = p.page.m.sheafDiv;
    return {
      width: sheaf.clientWidth,
      height: sheaf.clientHeight,
      scrollWidth: scrollerWidth()
    }
  }


  function scrollerElement() {
    if (Monocle.Browser.has.mustScrollSheaf) {
      return p.page.m.sheafDiv;
    } else {
      return columnedElement();
    }
  }


  function columnedElement() {
    var elem = p.page.m.activeFrame.contentDocument.body;
    return Monocle.Browser.has.columnOverflowPaintBug ? elem.firstChild : elem;
  }


  function scrollerWidth() {
    var bdy = p.page.m.activeFrame.contentDocument.body;
    if (Monocle.Browser.has.iframeDoubleWidthBug) {
      if (Monocle.Browser.on.Kindle3) {
        return scrollerElement().scrollWidth;
      } else if (Monocle.Browser.on.Android) {
        return bdy.scrollWidth;
      } else if (Monocle.Browser.iOSVersion < "4.1") {
        var hbw = bdy.scrollWidth / 2;
        var sew = scrollerElement().scrollWidth;
        return Math.max(sew, hbw);
      } else {
        bdy.scrollWidth; // Throw one away. Nuts.
        var hbw = bdy.scrollWidth / 2;
        return hbw;
      }
    } else if (bdy.getBoundingClientRect) {
      var elems = bdy.getElementsByTagName('*');
      var bdyRect = bdy.getBoundingClientRect();
      var l = bdyRect.left, r = bdyRect.right;
      for (var i = elems.length - 1; i >= 0; --i) {
        var rect = elems[i].getBoundingClientRect();
        l = Math.min(l, rect.left);
        r = Math.max(r, rect.right);
      }
      return Math.abs(l) + Math.abs(r);
    }

    return scrollerElement().scrollWidth;
  }


  function currBodyStyleValue(property) {
    var win = p.page.m.activeFrame.contentWindow;
    var doc = win.document;
    if (!doc.body) { return null; }
    var currStyle = win.getComputedStyle(doc.body, null);
    return currStyle.getPropertyValue(property);
  }


  function locusToOffset(locus) {
    return 0 - (p.measurements.width * (locus.page - 1));
  }


  function translateToLocus(locus) {
    var offset = locusToOffset(locus);
    p.page.m.offset = 0 - offset;
    if (k.SETX && !Monocle.Browser.has.columnOverflowPaintBug) {
      var bdy = p.page.m.activeFrame.contentDocument.body;
      Monocle.Styles.affix(bdy, "transform", "translateX("+offset+"px)");
    } else {
      var scrElem = scrollerElement();
      scrElem.scrollLeft = 0 - offset;
    }
    return offset;
  }


  API.hasChanged = hasChanged;
  API.measure = measure;
  API.pages = pages;
  API.percentageThroughOfNode = percentageThroughOfNode;

  API.locusToOffset = locusToOffset;
  API.translateToLocus = translateToLocus;

  initialize();

  return API;
}


Monocle.Dimensions.Columns.BODY_STYLES = {
  "position": "absolute",
  "height": "100%",
  "-webkit-column-gap": "0",
  "-webkit-column-fill": "auto",
  "-moz-column-gap": "0",
  "-moz-column-fill": "auto",
  "column-gap": "0",
  "column-fill": "auto"
}

Monocle.Dimensions.Columns.SETX = true; // Set to false for scrollLeft.

if (Monocle.Browser.has.iframeDoubleWidthBug) {
  Monocle.Dimensions.Columns.BODY_STYLES["min-width"] = "200%";
} else {
  Monocle.Dimensions.Columns.BODY_STYLES["width"] = "100%";
}
Monocle.Flippers.Slider = function (reader) {
  if (Monocle.Flippers == this) {
    return new Monocle.Flippers.Slider(reader);
  }

  var API = { constructor: Monocle.Flippers.Slider }
  var k = API.constants = API.constructor;
  var p = API.properties = {
    pageCount: 2,
    activeIndex: 1,
    turnData: {}
  }


  function initialize() {
    p.reader = reader;
  }


  function addPage(pageDiv) {
    pageDiv.m.dimensions = new Monocle.Dimensions.Columns(pageDiv);

    Monocle.Styles.setX(pageDiv, "0px");
  }


  function visiblePages() {
    return [upperPage()];
  }


  function listenForInteraction(panelClass) {
    interactiveMode(true);
    interactiveMode(false);

    if (typeof panelClass != "function") {
      panelClass = k.DEFAULT_PANELS_CLASS;
      if (!panelClass) {
        console.warn("Invalid panel class.")
      }
    }
    var q = function (action, panel, x) {
      var dir = panel.properties.direction;
      if (action == "lift") {
        lift(dir, x);
      } else if (action == "release") {
        release(dir, x);
      }
    }
    p.panels = new panelClass(
      API,
      {
        'start': function (panel, x) { q('lift', panel, x); },
        'move': function (panel, x) { turning(panel.properties.direction, x); },
        'end': function (panel, x) { q('release', panel, x); },
        'cancel': function (panel, x) { q('release', panel, x); }
      }
    );
  }


  function interactiveMode(bState) {
    p.reader.dispatchEvent('monocle:interactive:'+(bState ? 'on' : 'off'));
    if (!Monocle.Browser.has.selectThruBug) {
      return;
    }
    if (p.interactive = bState) {
      if (p.activeIndex != 0) {
        var place = getPlace();
        if (place) {
          setPage(
            p.reader.dom.find('page', 0),
            place.getLocus(),
            function () {
              flipPages();
              prepareNextPage();
            }
          );
        } else {
          flipPages();
        }
      }
    }
  }


  function getPlace(pageDiv) {
    pageDiv = pageDiv || upperPage();
    return pageDiv.m ? pageDiv.m.place : null;
  }


  function moveTo(locus, callback) {
    var fn = function () {
      prepareNextPage(function () {
        if (typeof callback == "function") { callback(); }
        announceTurn();
      });
    }
    setPage(upperPage(), locus, fn);
  }


  function setPage(pageDiv, locus, callback) {
    ensureWaitControl();
    p.reader.getBook().setOrLoadPageAt(
      pageDiv,
      locus,
      function (locus) {
        pageDiv.m.dimensions.translateToLocus(locus);
        if (callback) { callback(); }
      }
    );
  }


  function upperPage() {
    return p.reader.dom.find('page', p.activeIndex);
  }


  function lowerPage() {
    return p.reader.dom.find('page', (p.activeIndex + 1) % 2);
  }


  function flipPages() {
    upperPage().style.zIndex = 1;
    lowerPage().style.zIndex = 2;
    return p.activeIndex = (p.activeIndex + 1) % 2;
  }


  function lift(dir, boxPointX) {
    if (p.turnData.lifting || p.turnData.releasing) { return; }

    p.turnData.points = {
      start: boxPointX,
      min: boxPointX,
      max: boxPointX
    }
    p.turnData.lifting = true;

    if (dir == k.FORWARDS) {
      if (getPlace().onLastPageOfBook()) {
        p.reader.dispatchEvent(
          'monocle:boundaryend',
          {
            locus: getPlace().getLocus({ direction : dir }),
            page: upperPage()
          }
        );
        resetTurnData();
        return;
      }
      onGoingForward(boxPointX);
    } else if (dir == k.BACKWARDS) {
      if (getPlace().onFirstPageOfBook()) {
        p.reader.dispatchEvent(
          'monocle:boundarystart',
          {
            locus: getPlace().getLocus({ direction : dir }),
            page: upperPage()
          }
        );
        resetTurnData();
        return;
      }
      onGoingBackward(boxPointX);
    } else {
      console.warn("Invalid direction: " + dir);
    }
  }


  function turning(dir, boxPointX) {
    if (!p.turnData.points) { return; }
    if (p.turnData.lifting || p.turnData.releasing) { return; }
    checkPoint(boxPointX);
    slideToCursor(boxPointX, null, "0");
  }


  function release(dir, boxPointX) {
    if (!p.turnData.points) {
      return;
    }
    if (p.turnData.lifting) {
      p.turnData.releaseArgs = [dir, boxPointX];
      return;
    }
    if (p.turnData.releasing) {
      return;
    }

    checkPoint(boxPointX);

    p.turnData.releasing = true;
    showWaitControl(lowerPage());

    if (dir == k.FORWARDS) {
      if (
        p.turnData.points.tap ||
        p.turnData.points.start - boxPointX > 60 ||
        p.turnData.points.min >= boxPointX
      ) {
        slideOut(afterGoingForward);
      } else {
        slideIn(afterCancellingForward);
      }
    } else if (dir == k.BACKWARDS) {
      if (
        p.turnData.points.tap ||
        boxPointX - p.turnData.points.start > 60 ||
        p.turnData.points.max <= boxPointX
      ) {
        slideIn(afterGoingBackward);
      } else {
        slideOut(afterCancellingBackward);
      }
    } else {
      console.warn("Invalid direction: " + dir);
    }
  }


  function checkPoint(boxPointX) {
    p.turnData.points.min = Math.min(p.turnData.points.min, boxPointX);
    p.turnData.points.max = Math.max(p.turnData.points.max, boxPointX);
    p.turnData.points.tap = p.turnData.points.max - p.turnData.points.min < 10;
  }


  function onGoingForward(x) {
    lifted(x);
  }


  function onGoingBackward(x) {
    var lp = lowerPage(), up = upperPage();
    showWaitControl(up);
    jumpOut(lp, // move lower page off-screen
      function () {
        flipPages(); // flip lower to upper
        setPage( // set upper page to previous
          lp,
          getPlace(lowerPage()).getLocus({ direction: k.BACKWARDS }),
          function () {
            lifted(x);
            hideWaitControl(up);
          }
        );
      }
    );
  }


  function afterGoingForward() {
    var up = upperPage(), lp = lowerPage();
    if (p.interactive) {
      showWaitControl(up);
      showWaitControl(lp);
      setPage( // set upper (off screen) to current
        up,
        getPlace().getLocus({ direction: k.FORWARDS }),
        function () {
          jumpIn(up, function () { prepareNextPage(announceTurn); });
        }
      );
    } else {
      showWaitControl(lp);
      flipPages();
      jumpIn(up, function () { prepareNextPage(announceTurn); });
    }
  }


  function afterGoingBackward() {
    if (p.interactive) {
      setPage( // set lower page to current
        lowerPage(),
        getPlace().getLocus(),
        function () {
          flipPages(); // flip lower to upper
          prepareNextPage(announceTurn);
        }
      );
    } else {
      announceTurn();
    }
  }


  function afterCancellingForward() {
    resetTurnData();
  }


  function afterCancellingBackward() {
    flipPages(); // flip upper to lower
    jumpIn( // move lower back onto screen
      lowerPage(),
      function () { prepareNextPage(resetTurnData); }
    );
  }


  function prepareNextPage(callback) {
    setPage(
      lowerPage(),
      getPlace().getLocus({ direction: k.FORWARDS }),
      callback
    );
  }


  function lifted(x) {
    p.turnData.lifting = false;
    var releaseArgs = p.turnData.releaseArgs;
    if (releaseArgs) {
      p.turnData.releaseArgs = null;
      release(releaseArgs[0], releaseArgs[1]);
    } else if (x) {
      slideToCursor(x);
    }
  }


  function announceTurn() {
    p.reader.dispatchEvent('monocle:turn');
    resetTurnData();
  }


  function resetTurnData() {
    hideWaitControl(upperPage());
    hideWaitControl(lowerPage());
    p.turnData = {};
  }


  function setX(elem, x, options, callback) {
    var duration;

    if (!options.duration) {
      duration = 0;
    } else {
      duration = parseInt(options['duration']);
    }

    if (typeof(x) == "number") { x = x + "px"; }

    if (typeof WebKitTransitionEvent != "undefined") {
      if (duration) {
        transition = '-webkit-transform';
        transition += ' ' + duration + "ms";
        transition += ' ' + (options['timing'] || 'linear');
        transition += ' ' + (options['delay'] || 0) + 'ms';
      } else {
        transition = 'none';
      }
      elem.style.webkitTransition = transition;
      if (Monocle.Browser.has.transform3d) {
        elem.style.webkitTransform = "translate3d("+x+",0,0)";
      } else {
        elem.style.webkitTransform = "translateX("+x+")";
      }

    } else if (duration > 0) {
      clearTimeout(elem.setXTransitionInterval)

      var stamp = (new Date()).getTime();
      var frameRate = 40;
      var finalX = parseInt(x);
      var currX = getX(elem);
      var step = (finalX - currX) * (frameRate / duration);
      var stepFn = function () {
        var destX = currX + step;
        if (
          (new Date()).getTime() - stamp > duration ||
          Math.abs(currX - finalX) <= Math.abs((currX + step) - finalX)
        ) {
          clearTimeout(elem.setXTransitionInterval);
          Monocle.Styles.setX(elem, finalX);
          if (elem.setXTCB) {
            elem.setXTCB();
          }
        } else {
          Monocle.Styles.setX(elem, destX);
          currX = destX;
        }
      }

      elem.setXTransitionInterval = setInterval(stepFn, frameRate);
    } else {
      Monocle.Styles.setX(elem, x);
    }

    if (elem.setXTCB) {
      Monocle.Events.deafen(elem, 'webkitTransitionEnd', elem.setXTCB);
      elem.setXTCB = null;
    }

    elem.setXTCB = function () {
      if (callback) { callback(); }
    }

    var sX = getX(elem);
    if (!duration || sX == parseInt(x)) {
      elem.setXTCB();
    } else {
      Monocle.Events.listen(elem, 'webkitTransitionEnd', elem.setXTCB);
    }
  }


  /*
  function setX(elem, x, options, callback) {
    var duration, transition;

    if (!Monocle.Browser.has.transitions) {
      duration = 0;
    } else if (!options.duration) {
      duration = 0;
    } else {
      duration = parseInt(options['duration']);
    }

    if (typeof(x) == "number") { x = x + "px"; }

    if (duration) {
      transition = duration + "ms";
      transition += ' ' + (options['timing'] || 'linear');
      transition += ' ' + (options['delay'] || 0) + 'ms';
    } else {
      transition = "none";
    }

    if (elem.setXTCB) {
      Monocle.Events.deafen(elem, 'webkitTransitionEnd', elem.setXTCB);
      Monocle.Events.deafen(elem, 'transitionend', elem.setXTCB);
      elem.setXTCB = null;
    }

    elem.setXTCB = function () {
      if (callback) { callback(); }
    }

    elem.dom.setBetaStyle('transition', transition);
    if (Monocle.Browser.has.transform3d) {
      elem.dom.setBetaStyle('transform', 'translate3d('+x+',0,0)');
    } else {
      elem.dom.setBetaStyle('transform', 'translateX('+x+')');
    }

    if (!duration) {
      elem.setXTCB();
    } else {
      Monocle.Events.listen(elem, 'webkitTransitionEnd', elem.setXTCB);
      Monocle.Events.listen(elem, 'transitionend', elem.setXTCB);
    }
  }
  */


  function getX(elem) {
    if (typeof WebKitCSSMatrix == "object") {
      var matrix = window.getComputedStyle(elem).webkitTransform;
      matrix = new WebKitCSSMatrix(matrix);
      return matrix.m41;
    } else {
      var prop = elem.style.MozTransform;
      if (!prop || prop == "") { return 0; }
      return parseFloat((/translateX\((\-?.*)px\)/).exec(prop)[1]) || 0;
    }
  }


  function jumpIn(pageDiv, callback) {
    var dur = Monocle.Browser.has.jumpFlickerBug ? 1 : 0;
    Monocle.defer(function () {
      setX(pageDiv, 0, { duration: dur }, callback);
    });
  }


  function jumpOut(pageDiv, callback) {
    var dur = Monocle.Browser.has.jumpFlickerBug ? 1 : 0;
    Monocle.defer(function () {
      setX(pageDiv, 0 - pageDiv.offsetWidth, { duration: dur }, callback);
    });
  }



  function slideIn(callback) {
    var slideOpts = {
      duration: k.durations.SLIDE,
      timing: 'ease-in'
    };
    Monocle.defer(function () {
      setX(upperPage(), 0, slideOpts, callback);
    });
  }


  function slideOut(callback) {
    var slideOpts = {
      duration: k.durations.SLIDE,
      timing: 'ease-in'
    };
    Monocle.defer(function () {
      setX(upperPage(), 0 - upperPage().offsetWidth, slideOpts, callback);
    });
  }


  function slideToCursor(cursorX, callback, duration) {
    setX(
      upperPage(),
      Math.min(0, cursorX - upperPage().offsetWidth),
      { duration: duration || k.durations.FOLLOW_CURSOR },
      callback
    );
  }


  function ensureWaitControl() {
    if (p.waitControl) { return; }
    p.waitControl = {
      createControlElements: function (holder) {
        return holder.dom.make('div', 'flippers_slider_wait');
      }
    }
    p.reader.addControl(p.waitControl, 'page');
  }


  function showWaitControl(page) {
    var ctrl = p.reader.dom.find('flippers_slider_wait', page.m.pageIndex);
    ctrl.style.visibility = "visible";
  }


  function hideWaitControl(page) {
    var ctrl = p.reader.dom.find('flippers_slider_wait', page.m.pageIndex);
    ctrl.style.visibility = "hidden";
  }

  API.pageCount = p.pageCount;
  API.addPage = addPage;
  API.getPlace = getPlace;
  API.moveTo = moveTo;
  API.listenForInteraction = listenForInteraction;

  API.visiblePages = visiblePages;
  API.interactiveMode = interactiveMode;

  initialize();

  return API;
}


Monocle.Flippers.Slider.DEFAULT_PANELS_CLASS = Monocle.Panels.TwoPane;
Monocle.Flippers.Slider.FORWARDS = 1;
Monocle.Flippers.Slider.BACKWARDS = -1;
Monocle.Flippers.Slider.durations = {
  SLIDE: 220,
  FOLLOW_CURSOR: 100
}

Monocle.pieceLoaded('flippers/slider');

Monocle.pieceLoaded('monocle');
