require([
    'underscore',
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/simplexml/ready!'
], function(_, $, mvc, TableView) {
    var EmbedWorkflowUrl = TableView.BaseCellRenderer.extend({
        canRender: function(cell) {
            return cell.field === 'circleci_workflow';
        },
        render: function($td, cell) {
            // Create link to circleci console
            $td.addClass('string').html(_.template('<a href="<%- url %>">Open in CircleCI</a>', {
                url: cell.value
            }));
            $td.on('click', 'a', function(e) {
                var url = cell.value;
                window.open(url, '_blank');
            });
        }
    });
    mvc.Components.get('expand_with_events').getVisualization(function(tableView){
        // Register custom cell renderer, the table will re-render automatically
        tableView.addCellRenderer(new EmbedWorkflowUrl());
    });
});