// set button to read enter as keypress & to clear success upon typing
$('#URL_to_copy').keypress(function (e) {
    var key = e.which;

    // clear success color and changes button actions when new input occurs
    if ($("#URL_to_copy").hasClass("alert alert-success")) {
        $("#URL_to_copy").removeClass("alert alert-success");
        $("#shorten_url_btn").attr("title", "Get shortened URL");
        $("#URL_button_icon").removeClass('fa fa-clipboard');
        $("#URL_button_icon").addClass('fa fa-arrow-right');
        $("#shorten_url_btn").attr("onclick", "shorten_url()");
    }
    // detect if enter is pressed
    if (key == 13)  // the enter key code
    {
        $('#shorten_url_btn').click();
        return false;
    }
});   

// copy the converted url to the clipboard
function copy_url_url_to_clipboard(url)
{
    $(url).select();
    document.execCommand("copy");
}

function shorten_url()
{
    // disable inputs and buttons while querying
    $(".input-group").children().prop('disabled', true);
    $("#shorten_url_btn").addClass('disabled');

    // request shortend url
    $.post("/url", $("#URL_to_copy").val(), function (data) {

        // re-enable inputs and buttons
        $(".input-group").children().prop('disabled', false);
        $("#shorten_url_btn").removeClass('disabled');

        // put returned contents onscreen
        $("#URL_to_copy").val(data);

        // shows that change has happened
        $("#URL_to_copy").addClass("alert alert-success");

                // switch to copy to clipboard asthetics and handler
        $("#URL_button_icon").removeClass('fa fa-arrow-right');
        $("#URL_button_icon").addClass('fa fa-clipboard');
        $("#shorten_url_btn").attr("title", "Copy to clipboard");
        $("#shorten_url_btn").attr("onclick", "copy_url_url_to_clipboard('#URL_to_copy')");
    });
}