require([
    'underscore',
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/simplexml/ready!'
], function(_, $, mvc, TableView) {
    var EmbedWorkflowUrl = TableView.BaseCellRenderer.extend({
        canRender: function(cell) {
            return cell.field === 'step_name';
        },
        render: function($td, cell) {
            // Create link to circleci console
            if (cell.value.substring(0, 8) == 'https://') {
                //
                $td.addClass('string').html(_.template('<a href="<%- url %>">(Open Job in CircleCI Console)</a>', {
                    url: cell.value
                }));
            } else {
                //
                $td.addClass('string').html(cell.value);
            }
            $td.on('click', 'a', function(e) {
                var url = cell.value;
                window.open(url, '_blank');
            });
        }
    });
    mvc.Components.get('drilldown_table').getVisualization(function(tableView){
        // Register custom cell renderer, the table will re-render automatically
        tableView.addCellRenderer(new EmbedWorkflowUrl());
    });
});