
function bind_book_editable(book_id) {
    // There are some options you can configure when initiating
    // the editable feature as well as a callback function that
    // will be called when textarea gets blurred.
    $(".book-edit").editable({
        touch : true, // Whether or not to support touch (default true)
        lineBreaks : true, // Whether or not to convert \n to <br /> (default true)
        toggleFontSize : false,
        closeOnEnter : false,
        event : 'dblclick',
        emptyMessage : '<em>Please write something.</em>', // HTML that will be added to the editable element in case it gets empty (default false)
        callback : function( data ) {
            var self = data.$el;
            self.removeClass("book-edit-orig");
            self.addClass("book-edit-new");
            field = self.data().meta;
            if( data.content ) {
                console.log(field + " ==> " + data.content);
                $.ajax({
                    url: "/book/"+book_id+"/edit",
                    type: 'get',
                    data: {field: field, content: data.content },
                    dataType: 'json',
                    success: function(rsp) {
                        if ( rsp.ecode != 0 ) {
                            alert(rsp.msg);
                        } else {
                            $("#id_" + field).html(data.content);
                        }
                    },
                    error: function(data) {
                        alert("error happen!");
                    }
                });
            }
            //self.effect('blink');
        }
    });
    $(".meta-link").addClass("hidden");
    $(".book-edit").removeClass("hidden");
    $("#id_edit_tip").removeClass("hidden");
    $(".book-edit").addClass("book-edit-orig");
}


