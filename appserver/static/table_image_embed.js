require([
    'underscore',
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/simplexml/ready!'
], function(_, $, mvc, TableView) {
    var EmbedAvatarImage = TableView.BaseCellRenderer.extend({
        canRender: function(cell) {
            return cell.field === 'avatar';
        },
        render: function($td, cell) {
            // Create link to circleci console
            $td.addClass('image-embed-cell').html(_.template('<img src="<%- url %>">', {
                url: cell.value
            }));
        }
    });
    mvc.Components.get('top_trigger_users').getVisualization(function(tableView){
        // Register custom cell renderer, the table will re-render automatically
        tableView.addCellRenderer(new EmbedAvatarImage());
    });
});