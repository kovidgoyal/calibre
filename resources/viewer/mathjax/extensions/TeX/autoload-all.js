/*************************************************************
 *
 *  MathJax/extensions/TeX/autoload-all.js
 *  
 *  Provides pre-defined macros to autoload all the extensions
 *  so that all macros that MathJax knows about are available.
 *  
 *  ---------------------------------------------------------------------
 *  
 *  Copyright (c) 2012 Design Science, Inc.
 * 
 *  Licensed under the Apache License, Version 2.0 (the "License");
 *  you may not use this file except in compliance with the License.
 *  You may obtain a copy of the License at
 * 
 *      http://www.apache.org/licenses/LICENSE-2.0
 * 
 *  Unless required by applicable law or agreed to in writing, software
 *  distributed under the License is distributed on an "AS IS" BASIS,
 *  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 *  See the License for the specific language governing permissions and
 *  limitations under the License.
 */

MathJax.Extension["TeX/autoload-all"] = {
  version: "2.0"
};
  
MathJax.Hub.Register.StartupHook("TeX Jax Ready",function () {
  var TEX = MathJax.InputJax.TeX,
      MACROS = TEX.Definitions.macros,
      ENVS = TEX.Definitions.environment;
  

  var EXTENSIONS = {
    action:     ["mathtip","texttip","toggle"],
    AMSmath:    ["mathring","nobreakspace","negmedspace","negthickspace","intI",
                   "iiiint","idotsint","dddot","ddddot","sideset","boxed",
                   "substack","injlim","projlim","varliminf","varlimsup",
                   "varinjlim","varprojlim","DeclareMathOperator","operatorname",
                   "genfrac","tfrac","dfrac","binom","tbinom","dbinom","cfrac",
                   "shoveleft","shoveright","xrightarrow","xleftarrow"],
    begingroup: ["begingroup","endgroup","gdef","global"],
    cancel:     ["cancel","bcancel","xcancel","cancelto"],
    color:      ["color","colorbox","fcolorbox","DefineColor"],
    enclose:    ["enclose"],
    extpfeil:   ["Newextarrow","xlongequal","xmapsto","xtofrom",
                   "xtwoheadleftarrow","xtwoheadrightarrow"],
    mhchem:     ["ce","cee","cf"]
  };
  
  for (var name in EXTENSIONS) {if (EXTENSIONS.hasOwnProperty(name)) {
    var macros = EXTENSIONS[name];
    for (var i = 0, m = macros.length; i < m; i++) {
      MACROS[macros[i]] = ["Extension",name];
    }
  }}
  
  ENVS["subarray"]    = ['ExtensionEnv',null,'AMSmath'];
  ENVS["smallmatrix"] = ['ExtensionEnv',null,'AMSmath'];
  ENVS["equation"]    = ['ExtensionEnv',null,'AMSmath'];
  ENVS["equation*"]   = ['ExtensionEnv',null,'AMSmath'];

  MathJax.Hub.Startup.signal.Post("TeX autoload-all Ready");
  
});

MathJax.Callback.Queue(
  ["Require",MathJax.Ajax,"[MathJax]/extensions/TeX/AMSsymbols.js"],
  ["loadComplete",MathJax.Ajax,"[MathJax]/extensions/TeX/autoload-all.js"]
);
