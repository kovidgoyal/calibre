/*************************************************************
 *
 *  MathJax/extensions/TeX/color.js
 *  
 *  Implements LaTeX-compatible \color macro rather than MathJax's
 *  original (non-standard) version.  It includes the rgb, gray, and
 *  named color models, and the \definecolor macro.
 *  
 *  ---------------------------------------------------------------------
 *  
 *  Copyright (c) 2011-2012 Design Science, Inc.
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

//
//  The configuration defaults, augmented by the user settings
//  
MathJax.Extension["TeX/color"] = {
  version: "2.0",

  config: MathJax.Hub.CombineConfig("TeX.color",{
    padding: "5px",
    border: "2px"
  }),

  colors: {
    Apricot:        "#FBB982",
    Aquamarine:     "#00B5BE",
    Bittersweet:    "#C04F17",
    Black:          "#221E1F",
    Blue:           "#2D2F92",
    BlueGreen:      "#00B3B8",
    BlueViolet:     "#473992",
    BrickRed:       "#B6321C",
    Brown:          "#792500",
    BurntOrange:    "#F7921D",
    CadetBlue:      "#74729A",
    CarnationPink:  "#F282B4",
    Cerulean:       "#00A2E3",
    CornflowerBlue: "#41B0E4",
    Cyan:           "#00AEEF",
    Dandelion:      "#FDBC42",
    DarkOrchid:     "#A4538A",
    Emerald:        "#00A99D",
    ForestGreen:    "#009B55",
    Fuchsia:        "#8C368C",
    Goldenrod:      "#FFDF42",
    Gray:           "#949698",
    Green:          "#00A64F",
    GreenYellow:    "#DFE674",
    JungleGreen:    "#00A99A",
    Lavender:       "#F49EC4",
    LimeGreen:      "#8DC73E",
    Magenta:        "#EC008C",
    Mahogany:       "#A9341F",
    Maroon:         "#AF3235",
    Melon:          "#F89E7B",
    MidnightBlue:   "#006795",
    Mulberry:       "#A93C93",
    NavyBlue:       "#006EB8",
    OliveGreen:     "#3C8031",
    Orange:         "#F58137",
    OrangeRed:      "#ED135A",
    Orchid:         "#AF72B0",
    Peach:          "#F7965A",
    Periwinkle:     "#7977B8",
    PineGreen:      "#008B72",
    Plum:           "#92268F",
    ProcessBlue:    "#00B0F0",
    Purple:         "#99479B",
    RawSienna:      "#974006",
    Red:            "#ED1B23",
    RedOrange:      "#F26035",
    RedViolet:      "#A1246B",
    Rhodamine:      "#EF559F",
    RoyalBlue:      "#0071BC",
    RoyalPurple:    "#613F99",
    RubineRed:      "#ED017D",
    Salmon:         "#F69289",
    SeaGreen:       "#3FBC9D",
    Sepia:          "#671800",
    SkyBlue:        "#46C5DD",
    SpringGreen:    "#C6DC67",
    Tan:            "#DA9D76",
    TealBlue:       "#00AEB3",
    Thistle:        "#D883B7",
    Turquoise:      "#00B4CE",
    Violet:         "#58429B",
    VioletRed:      "#EF58A0",
    White:          "#FFFFFF",
    WildStrawberry: "#EE2967",
    Yellow:         "#FFF200",
    YellowGreen:    "#98CC70",
    YellowOrange:   "#FAA21A"
  },

  /*
   *  Look up a color based on its model and definition
   */
  getColor: function (model,def) {
    if (!model) {model = "named"}
    var fn = this["get_"+model];
    if (!fn) {this.TEX.Error("Color model '"+model+"' not defined")}
    return fn.call(this,def);
  },
  
  /*
   *  Get an RGB color
   */
  get_rgb: function (rgb) {
    rgb = rgb.split(/,/); var RGB = "#";
    if (rgb.length !== 3) {this.TEX.Error("RGB colors require 3 decimal numbers")}
    for (var i = 0; i < 3; i++) {
      if (!rgb[i].match(/^(\d+(\.\d*)?|\.\d+)$/)) {this.TEX.Error("Invalid decimal number")}
      var n = parseFloat(rgb[i]);
      if (n < 0 || n > 1) {this.TEX.Error("RGB values must be between 0 and 1")}
      n = Math.floor(n*255).toString(16); if (n.length < 2) {n = "0"+n}
      RGB += n;
    }
    return RGB;
  },
  
  /*
   *  Get a gray-scale value
   */
  get_gray: function (gray) {
    if (!gray.match(/^(\d+(\.\d*)?|\.\d+)$/)) {this.TEX.Error("Invalid decimal number")}
    var n = parseFloat(gray);
    if (n < 0 || n > 1) {this.TEX.Error("Grey-scale values must be between 0 and 1")}
    n = Math.floor(n*255).toString(16); if (n.length < 2) {n = "0"+n}
    return "#"+n+n+n;
  },
  
  /*
   *  Get a named value
   */
  get_named: function (name) {
    if (this.colors[name]) {return this.colors[name]}
    return name;
  },
  
  padding: function () {
    var pad = "+"+this.config.padding;
    var unit = this.config.padding.replace(/^.*?([a-z]*)$/,"$1");
    var pad2 = "+"+(2*parseFloat(pad))+unit;
    return {width:pad2, height:pad, depth:pad, lspace:this.config.padding};
  }

};
  
MathJax.Hub.Register.StartupHook("TeX Jax Ready",function () {
  var TEX = MathJax.InputJax.TeX,
      MML = MathJax.ElementJax.mml;
  var STACKITEM = TEX.Stack.Item;
  var COLOR = MathJax.Extension["TeX/color"];

  COLOR.TEX = TEX; // for reference in getColor above
  
  TEX.Definitions.macros.color = "Color";
  TEX.Definitions.macros.definecolor = "DefineColor";
  TEX.Definitions.macros.colorbox = "ColorBox";
  TEX.Definitions.macros.fcolorbox = "fColorBox";

  TEX.Parse.Augment({
    
    //
    //  Override \color macro definition
    //
    Color: function (name) {
      var model = this.GetBrackets(name),
          color = this.GetArgument(name);
      color = COLOR.getColor(model,color);
      var mml = STACKITEM.style().With({styles:{mathcolor:color}});
      this.stack.env.color = color;
      this.Push(mml);
    },

    //
    //  Define the \definecolor macro
    //
    DefineColor: function (name) {
      var cname = this.GetArgument(name),
          model = this.GetArgument(name),
          def = this.GetArgument(name);
      COLOR.colors[cname] = COLOR.getColor(model,def);
    },
    
    //
    //  Produce a text box with a colored background
    //
    ColorBox: function (name) {
      var cname = this.GetArgument(name),
          arg = this.InternalMath(this.GetArgument(name));
      this.Push(MML.mpadded.apply(MML,arg).With({
        mathbackground:COLOR.getColor("named",cname)
      }).With(COLOR.padding()));
    },
    
    //
    //  Procude a framed text box with a colored background
    //
    fColorBox: function (name) {
      var fname = this.GetArgument(name),
          cname = this.GetArgument(name),
          arg = this.InternalMath(this.GetArgument(name));
      this.Push(MML.mpadded.apply(MML,arg).With({
        mathbackground: COLOR.getColor("named",cname),
        style: "border: "+COLOR.config.border+" solid "+COLOR.getColor("named",fname)
      }).With(COLOR.padding()));
    }

  });

  MathJax.Hub.Startup.signal.Post("TeX color Ready");

});

MathJax.Ajax.loadComplete("[MathJax]/extensions/TeX/color.js");
