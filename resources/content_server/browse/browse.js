
// Cookies {{{
/**
 * Create a cookie with the given name and value and other optional parameters.
 *
 * @example $.cookie('the_cookie', 'the_value');
 * @desc Set the value of a cookie.
 * @example $.cookie('the_cookie', 'the_value', { expires: 7, path: '/', domain: 'jquery.com', secure: true });
 * @desc Create a cookie with all available options.
 * @example $.cookie('the_cookie', 'the_value');
 * @desc Create a session cookie.
 * @example $.cookie('the_cookie', null);
 * @desc Delete a cookie by passing null as value. Keep in mind that you have to use the same path and domain
 *       used when the cookie was set.
 *
 * @param String name The name of the cookie.
 * @param String value The value of the cookie.
 * @param Object options An object literal containing key/value pairs to provide optional cookie attributes.
 * @option Number|Date expires Either an integer specifying the expiration date from now on in days or a Date object.
 *                             If a negative value is specified (e.g. a date in the past), the cookie will be deleted.
 *                             If set to null or omitted, the cookie will be a session cookie and will not be retained
 *                             when the the browser exits.
 * @option String path The value of the path atribute of the cookie (default: path of page that created the cookie).
 * @option String domain The value of the domain attribute of the cookie (default: domain of page that created the cookie).
 * @option Boolean secure If true, the secure attribute of the cookie will be set and the cookie transmission will
 *                        require a secure protocol (like HTTPS).
 * @type undefined
 *
 * @name $.cookie
 * @cat Plugins/Cookie
 * @author Klaus Hartl/klaus.hartl@stilbuero.de
 */

function cookie(name, value, options) {
    if (typeof value != 'undefined') { // name and value given, set cookie
        options = options || {};
        if (value === null) {
            value = '';
            options.expires = -1;
        }
        var expires = '';
        if (options.expires && (typeof options.expires == 'number' || options.expires.toUTCString)) {
            var date;
            if (typeof options.expires == 'number') {
                date = new Date();
                date.setTime(date.getTime() + (options.expires * 24 * 60 * 60 * 1000));
            } else {
                date = options.expires;
            }
            expires = '; expires=' + date.toUTCString(); // use expires attribute, max-age is not supported by IE
        }
        // CAUTION: Needed to parenthesize options.path and options.domain
        // in the following expressions, otherwise they evaluate to undefined
        // in the packed version for some reason...
        var path = options.path ? '; path=' + (options.path) : '';
        var domain = options.domain ? '; domain=' + (options.domain) : '';
        var secure = options.secure ? '; secure' : '';
        document.cookie = [name, '=', encodeURIComponent(value), expires, path, domain, secure].join('');
    } else { // only name given, get cookie
        var cookieValue = null;
        if (document.cookie && document.cookie != '') {
            var cookies = document.cookie.split(';');
            for (var i = 0; i < cookies.length; i++) {
                var cookie = jQuery.trim(cookies[i]);
                // Does this cookie string begin with the name we want?
                if (cookie.substring(0, name.length + 1) == (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
};

// }}}

// Sort {{{

function init_sort_combobox() {
    $("#sort_combobox").multiselect({
       multiple: false,
       header: sort_select_label,
       noneSelectedText: sort_select_label,
       selectedList: 1,
       click: function(event, ui){
            $(this).multiselect("close");
            cookie(sort_cookie_name, ui.value);
            window.location.reload();
       }
    });
}

// }}}

function init() {
    $("#container").corner("30px");
    $("#header").corner("30px");
    $("#calibre-home-link").click(function() { window.location = "http://calibre-ebook.com"; });

    init_sort_combobox();

    $("#search_box input:submit").button();
}

// Top-level feed {{{

function toplevel_layout() {
    var last = $(".toplevel li").last();
    var title = $('.toplevel h3').first();
    var bottom = last.position().top + last.height() - title.position().top;
    $("#main").height(Math.max(200, bottom+75));
}

function toplevel() {
    $(".sort_select").hide();

    $(".toplevel li").click(function() {
        var href = $(this).children("span.url").text();
        window.location = href;
    });

    toplevel_layout();
    $(window).resize(toplevel_layout);

}
// }}}

function render_error(msg) {
    return '<div class="ui-widget"><div class="ui-state-error ui-corner-all" style="padding: 0pt 0.7em"><p><span class="ui-icon ui-icon-alert" style="float: left; margin-right: 0.3em">&nbsp;</span><strong>Error: </strong>'+msg+"</p></div></div>"
}

// Category feed {{{

function category_clicked() {
   var href = $(this).find("span.href").html();
   window.location = href;
}

function category() {
    $(".category .category-item").click(category_clicked);

    $(".category a.navlink").button();
    
    $("#groups").accordion({
        collapsible: true,
        active: false,
        autoHeight: false,
        clearStyle: true,
        header: "h3",

        change: function(event, ui) {
            if (ui.newContent) {
                var href = ui.newContent.children("span.load_href").html();
                ui.newContent.children(".loading").show();
                if (href) {
                    $.ajax({
                        url:href,
                        cache: false,
                        data:{'sort':cookie(sort_cookie_name)},
                        success: function(data) {
                            this.children(".loaded").html(data);
                            this.children(".loaded").show();
                            this.children(".loading").hide();
                            this.find('.category-item').click(category_clicked);
                        },
                        context: ui.newContent,
                        dataType: "json",
                        timeout: 600000, //milliseconds (10 minutes)
                        error: function(xhr, stat, err) {
                            this.children(".loaded").html(render_error(stat));
                            this.children(".loaded").show();
                            this.children(".loading").hide();
                        }
                    });
                }
            }
        }
    });
}
// }}}

// Booklist {{{

function first_page() {
    load_page($("#booklist #page0"));
}

function last_page() {
    load_page($("#booklist .page").last());
}

function next_page() {
    var elem = $("#booklist .page:visible").next('.page');
    if (elem.length > 0) load_page(elem);
    else first_page();
}

function previous_page() {
    var elem = $("#booklist .page:visible").prev('.page');
    if (elem.length > 0) load_page(elem);
    else last_page();
}

function load_page(elem) {
    if (elem.is(":visible")) return;
    var ld = elem.find('.load_data');
    var ids = ld.attr('title');
    var href = ld.find(".url").attr('title');
    elem.children(".loaded").hide();

    $.ajax({
        url: href,
        context: elem,
        dataType: "json",
        cache : false,
        type: 'POST',
        timeout: 600000, //milliseconds (10 minutes)
        data: {'ids': ids},
        error: function(xhr, stat, err) {
            this.children(".loaded").html(render_error(stat));
            this.children(".loaded").show();
            this.children(".loading").hide();
        },
        success: function(data) {
            this.children(".loaded").html(data);
            this.find(".left a.read").button();
            this.children(".loading").hide();
            this.parent().find('.navmiddle .start').html(this.find('.load_data .start').attr('title'));
            this.parent().find('.navmiddle .end').html(this.find('.load_data .end').attr('title'));
            this.children(".loaded").fadeIn(1000);
        }
    });
    $("#booklist .page:visible").hide();
    elem.children(".loaded").hide();
    elem.children(".loading").show();
    elem.show();
}

function hidesort() {$("#content > .sort_select").hide();}

function booklist(hide_sort) {
    if (hide_sort) hidesort();
    var test = $("#booklist #page0").html();
    if (!test) {
        $("#booklist").html(render_error("No books found"));
        return;
    }
    $("#book_details_dialog").dialog({
        autoOpen: false,
        modal: true,
        show: 'slide'
    });
    first_page(); 
}

function show_details(a_dom) {
    var book = $(a_dom).closest('div.summary');
    var bd = $('#book_details_dialog');
    bd.html('<span class="loading"><img src="/static/loading.gif" alt="Loading" />Loading, please wait&hellip;</span>');
    bd.dialog('option', 'width', $(window).width() - 100);
    bd.dialog('option', 'height', $(window).height() - 100);
    bd.dialog('option', 'title', book.find('.title').text());

    $.ajax({
        url: book.find('.details-href').attr('title'),
        context: bd,
        cache: false,
        dataType: "json",
        timeout: 600000, //milliseconds (10 minutes)
        error: function(xhr, stat, err) {
            this.html(render_error(stat));
        },
        success: function(data) {
            this.html(data);
        }
    });

    bd.dialog('open');
}

// }}}

function book() {
    hidesort();
    $('.details .left img').load(function() {
        var img = $('.details .left img');
        var height = $('#main').height();
        height = Math.max(height, img.height() + 100);
        $('#main').height(height);
    });
}
