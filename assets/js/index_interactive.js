// set button to read enter as keypress & to clear success upon typing
$('#URL_to_copy').keypress(function (e) {
    var key = e.which;

    // clear success color when new input occurs
    $("#URL_to_copy").removeClass("alert alert-success");
    
    // detect if enter is pressed
    if (key == 13)  // the enter key code
    {
        $('#shorten_url_btn').click();
        return false;
    }
});   

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
    });
}