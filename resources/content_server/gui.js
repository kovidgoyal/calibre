/* COLUMNS */
var cmap = ['title', 'authors', 'rating', 'date', 'series'];
/* COLUMNS END */
var column_titles = {
    'title'    : 'Title',
    'authors'  : 'Author(s)',
    'rating'   : 'Rating',
    'date'     : 'Date',
    'tags'     : 'Tags',
    'series'   : 'Series'
};

String.prototype.format = function() {
    var pattern = /\{\d+\}/g;
    var args = arguments;
    return this.replace(pattern, function(capture){ return args[capture.match(/\d+/)]; });
}

var last_search = '';
var last_sort = null;
var last_sort_order = null;
var last_start = 0;
var last_num = 20;
var total = 0;
var current_library_request = null;

////////////////////////////// GET BOOK LIST //////////////////////////////

var LIBRARY_FETCH_TIMEOUT = 5*60000; // milliseconds

function create_table_headers() {
    var thead = $('table#book_list thead tr');
    var titles = '';
    for (i = 0; i < cmap.length; i++) {
        titles += '<td>{0}&nbsp;<span class="sort_indicator" id="{1}_sort">↑</span></td>'
            .format(column_titles[cmap[i]], cmap[i]);
    }
    thead.html(titles);
}


function format_url(format, id, title) {
    return url_prefix + '/get/'+format.toLowerCase() + '/'+encodeURIComponent(title) + '_' + id+'.'+format.toLowerCase();
}

function render_book(book) {
    // Render title cell
    var title = '<i>{0}</i>'.format(book.attr("title")) + '<br /><span class="subtitle">';
    var id    = book.attr("id");
    var comments = $.trim(book.text()).replace(/\n\n/, '<br/>');
    var formats = new Array();
    var size = (parseFloat(book.attr('size'))/(1024*1024)).toFixed(1);
    var tags = book.attr('tags')
    formats = book.attr("formats").split(",");
    if (formats.length > 0) {
        for (i=0; i < formats.length; i++) {
            title += '<a title="Download in '+formats[i]+' format" class="format" href="'+format_url(formats[i], id, book.attr("safe_title"))+'">'+formats[i]+'</a>, ';
        }
        title = title.slice(0, title.length-2);
        title += '&nbsp;({0}&nbsp;MB)&nbsp;'.format(size);
    }
    title += '<span class="tagdata_short" style="display:all">'
    if (tags) {
        t = tags.split(':&:', 2);
        m = parseInt(t[0]);
        tall = t[1].split(',');
        t = t[1].split(',', m);
        if (tall.length > m) t[m] = '...'
        title += 'Tags=[{0}] '.format(t.join(','));
    }
    custcols = book.attr("custcols").split(',')
    for ( i = 0; i < custcols.length; i++) {
        if (custcols[i].length > 0) {
            vals = book.attr(custcols[i]).split(':#:', 2);
            if (vals[0].indexOf('#T#') == 0) { //startswith
                vals[0] = vals[0].substr(3, vals[0].length)
                t = vals[1].split(':&:', 2);
                m = parseInt(t[0]);
                t = t[1].split(',', m);
                if (t.length == m) t[m] = '...';
                vals[1] = t.join(',');
            }
            title += '{0}=[{1}] '.format(vals[0], vals[1]);
        }
    }
    title += '</span>'
    title += '<span class="tagdata_long" style="display:none">'
    if (tags) {
        t = tags.split(':&:', 2);
        title += 'Tags=[{0}] '.format(t[1]);
    }
    custcols = book.attr("custcols").split(',')
    for ( i = 0; i < custcols.length; i++) {
        if (custcols[i].length > 0) {
            vals = book.attr(custcols[i]).split(':#:', 2);
            if (vals[0].indexOf('#T#') == 0) { //startswith
                vals[0] = vals[0].substr(3, vals[0].length)
                vals[1] = (vals[1].split(':&:', 2))[1];
            }
            title += '{0}=[{1}] '.format(vals[0], vals[1]);
        }
    }
    title += '</span>'
    title += '<img style="display:none" alt="" src="{1}/get/cover/{0}" /></span>'.format(id, url_prefix);
    title += '<div class="comments">{0}</div>'.format(comments)
    // Render authors cell
    var _authors = new Array();
    var authors = '';
    _authors = book.attr('authors').split('|');
    for (i = 0; i < _authors.length; i++) {
        authors += jQuery.trim(_authors[i]).replace(/ /g, '&nbsp;')+'<br />';
    }
    if (authors) { authors = authors.slice(0, authors.length-6); }

    // Render rating cell
    var _rating = parseFloat(book.attr('rating'))/2.;
    var rating = '';
    for (i = 0; i < _rating; i++) { rating += '&#9733;'}

    // Render date cell
    var _date = Date.parseExact(book.attr('timestamp'), 'yyyy/MM/dd HH:mm:ss');
    var date = _date.toString('d MMM yyyy').replace(/ /g, '&nbsp;');

    // Render series cell
    var series = book.attr("series")
    if (series) {
        series += '&nbsp;[{0}]'.format(book.attr('series_index'));
    }

    var cells = {
        'title'   : title,
        'authors' : authors,
        'rating'  : rating,
        'date'    : date,
        'series'  : series
    };

    var row = '';
    for (i = 0; i < cmap.length; i++) {
        row += '<td class="{0}">{1}</td>'.format(cmap[i], cells[cmap[i]]);
    }
    return '<tr id="{0}">{1}</tr>'.format(id, row);
}

function fetch_library_books(start, num, timeout, sort, order, search) {
    // null, 0, false are False
    data = {"start":start+'', "num":num+''};
    if (sort)   { data["sort"] = sort; }
    if (search) { data["search"] = search; }
    if (order)  { data['order'] = order; }
    last_num = num;
    last_start = start;
    last_search = search;
    last_sort = sort;
    last_sort_order = order;

    if (current_library_request != null) {
        current_library_request.abort();
        current_library_request = null;
    }

    $('#cover_pane').css('visibility', 'hidden');
    $('#loading').css('visibility', 'visible');

    current_library_request = $.ajax({
      type: "GET",
      url: "xml",
      data: data,
      cache: false,
      timeout: timeout, //milliseconds
      dataType: "xml",

      error : function(XMLHttpRequest, textStatus, errorThrown) {
          alert('Error: '+textStatus+'\n\n'+errorThrown);
      },

      success : function(xml, textStatus) {
          var library = $(xml).find('library');
          total = parseInt(library.attr('total'));
          var num   = parseInt(library.attr('num'));
          var start = parseInt(library.attr('start'));
          update_count_bar(start, num, total);
          var display = '';
          library.find('book').each( function() {
              var book = $(this);
              var row = render_book(book);
              display += row+'\n\n';
          });
          $("#book_list tbody").html(display);
          $("#book_list tbody tr").bind('mouseenter', function() {
              var row = $(this);
              $('#book_list tbody tr:even').css('background-color', '#eeeeee');
              $('#book_list tbody tr:odd').css('background-color', 'white');

              row.css('background-color', "#fff2a8");
              row.bind('mouseleave', function(){
                  row.css('background-color', "white");
                  $('#book_list tbody tr:even').css('background-color', '#eeeeee');
                  row.unbind('mouseleave');
              });
          });
          $("#book_list tbody tr").click(function(){
              var row = $(this);
              var cover = row.find('img').attr('src');
              var collapsed = row.find('.comments').css('display') == 'none';
              $("#book_list tbody tr * .comments").css('display', 'none');
              $("#book_list tbody tr * .tagdata_short").css('display', 'inherit');
              $("#book_list tbody tr * .tagdata_long").css('display', 'none');
              $('#cover_pane').css('visibility', 'hidden');
              if (collapsed) {
                  row.find('.comments').css('display', 'inherit');
                  $('#cover_pane img').attr('src', cover);
                  $('#cover_pane').css('visibility', 'visible');
                row.find(".tagdata_short").css('display', 'none');
                row.find(".tagdata_long").css('display', 'inherit');
              }
          });


          layout();
          $('#book_list tbody tr:even').css('background-color', '#eeeeee');
      },

      complete : function(XMLHttpRequest, textStatus) {
          current_library_request = null;
          document.getElementById('main').scrollTop = 0;
          $('#loading').css('visibility', 'hidden');
      }

    });

}


////////////////////////////// COUNT BAR //////////////////////////////

function update_count_bar(start, num, total) {
    var cb = $('#count_bar');
    cb.find('#count').html('Books {0} to {1} of {2}'.format(start+1, start+num, total));
    var left = cb.find('#left');
    left.css('opacity', (start <= 0) ? 0.3 : 1);
    var right = cb.find('#right');
    right.css('opacity', (start + num >= total) ? 0.3 : 1);

}

function setup_count_bar() {
    $('#count_bar * img:eq(0)').click(function(){
        if (last_start > 0) {
            fetch_library_books(0, last_num, LIBRARY_FETCH_TIMEOUT, last_sort, last_sort_order, last_search);
        }
    });

    $('#count_bar * img:eq(1)').click(function(){
        if (last_start > 0) {
            var new_start = last_start - last_num;
            if (new_start < 0) {
                new_start = 0;
            }
            fetch_library_books(new_start, last_num, LIBRARY_FETCH_TIMEOUT, last_sort, last_sort_order, last_search);
        }
    });

    $('#count_bar * img:eq(2)').click(function(){
        if (last_start + last_num < total) {
            var new_start = last_start + last_num;
            fetch_library_books(new_start, last_num, LIBRARY_FETCH_TIMEOUT, last_sort, last_sort_order, last_search);
        }
    });

    $('#count_bar * img:eq(3)').click(function(){
        if (total - last_num > 0) {
            fetch_library_books(total - last_num, last_num, LIBRARY_FETCH_TIMEOUT, last_sort, last_sort_order, last_search);
        }
    });
}

////////////////////////////// SEARCH /////////////////////////////////////////

function search() {
    var search = $.trim($('#search_box * #s').val());
    fetch_library_books(0, last_num, LIBRARY_FETCH_TIMEOUT,
                        last_sort, last_sort_order, search);
}


/////////////////////////// SORTING /////////////////////////////////////

function setup_sorting() {
    $('table#book_list  thead tr td').mouseover(function() {
        this.style.backgroundColor = "#fff2a8";
    });

    $('table#book_list  thead tr td').mouseout(function() {
        this.style.backgroundColor = "transparent";
    });

    for (i = 0; i < cmap.length; i++) {
        $('table#book_list span#{0}_sort'.format(cmap[i])).parent().click(function() {
            var sort_indicator = $($(this).find('span'));
            var cell = $(sort_indicator.parent());
            var id = sort_indicator.attr("id");
            var col = id.slice(0, id.indexOf("_"));
            var order = 'ascending';
            var html = '↑';

            if (sort_indicator.html() == '↑') {
                order = 'descending'; html = '↓';
            }

            sort_indicator.html(html);
            $('#book_list * .sort_indicator').css('visibility', 'hidden');
            sort_indicator.css('visibility', 'visible');
            fetch_library_books(last_start, last_num, LIBRARY_FETCH_TIMEOUT, col, order, last_search);
        });
    }
}

///////////////////////// STARTUP ////////////////////////////////////////

function layout() {
    var main = $('#main'); var cb = $('#count_bar');
    main.css('height', ($(window).height() - main.offset().top - 20)+'px')
    main.css('width', ($(window).width() - main.offset().left - 15)+'px')
    cb.css('right', '20px');
    cb.css('top', (main.offset().top - cb.height()-5)+'px');
    $('#loading').css('height', ($(window).height()-20)+'px');
    $('#loading').css('width', ($(window).width()-20)+'px');
    var cover = $('#cover_pane');
    var title = $('#book_list thead tr td')
    cover.css('width', (main.width()-title.offset().left - title.width()-15)+'px')
    cover.css('height', main.height()+'px')
    cover.css('left', (title.offset().left+title.width())+'px');
    cover.css('top', main.offset().top+'px');
}

$(function() {
    // document is ready
    create_table_headers();

    // Setup widgets
    setup_sorting();
    setup_count_bar();
    $('#search_box * #s').val('');
    $(window).resize(layout);

    $($('#book_list * span#date_sort').parent()).click();

});
