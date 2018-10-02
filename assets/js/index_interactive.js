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
        $("#URL_to_copy").addClass("alert alert-success")
        $("#URL_to_copy").keypress(function () {
            $("#URL_to_copy").removeClass("alert alert-success");
            $("#URL_to_copy").off('change');
        })
    });
}