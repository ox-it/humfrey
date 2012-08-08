$(function() {
	var canUpdate = $("meta[name='humfrey-store-update']").attr("content") == "true";
	
	if (canUpdate) {
		$('#graphs thead tr').append($("<th>Delete</th>"));
		$('#graphs tbody tr').each(function(i, e) {
			var tr = $(e);
			tr.append($('<input type="button" value="Delete"/>').click(function() {
				$(this).replaceWith("Deleting…");
				$.ajax({type: 'DELETE',
						url: tr.attr('data-graph-url'),
						success: function(data, textStatus, jqXHR) {
							tr.fadeOut('slow', function() { tr.remove(); });
						},
						error: function(jqXHR, textStatus, errorThrown) {
							alert("failed: " + errorThrown)
						}})
			}));
		});
	}
});