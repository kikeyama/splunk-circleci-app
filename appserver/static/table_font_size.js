require([
    'jquery',
    'underscore',
    'splunkjs/mvc',
    'views/shared/results_table/renderers/BaseCellRenderer',
    'splunkjs/mvc/simplexml/ready!'
], function($, _, mvc, BaseCellRenderer) {
    var DataBarCellRenderer = BaseCellRenderer.extend({
        canRender: function(cell) {
            return true;
        },
        render: function($td, rowData) {
            var projectCell = _(rowData.cells).find(function (cell) {
               return cell.field === 'project_slug';
            });
            var countCell = _(rowData.cells).find(function (cell) {
               return cell.field === 'triggered_pipeline_count';
            });
            $td.css({'font-size': Math.min(Math.max(parseFloat(countCell.value), 0), 100)});
        }
    });
    mvc.Components.get('most_frequently_triggered').getVisualization(function(tableView) {
        tableView.addCellRenderer(new DataBarCellRenderer());
    });
});