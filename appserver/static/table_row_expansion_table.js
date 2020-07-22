require([
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/searchmanager',
    'splunkjs/mvc',
    'underscore',
    'splunkjs/mvc/simplexml/ready!'],function(
    TableView,
    SearchManager,
    mvc,
    _
    ){
    var EventSearchBasedRowExpansionRenderer = TableView.BaseRowExpansionRenderer.extend({
        initialize: function(args) {
            // initialize will run once, so we will set up a search and a table to be reused.
            this._searchManager = new SearchManager({
                id: 'details-search-manager',
                preview: false
            });
            this._inlineTableView = new TableView({
                managerid: 'details-search-manager',
                fields: 'build_num, time, workflows.job_name, build_time_millis, status',
                drilldown: 'none'
            });
        },
        canRender: function(rowData) {
            // Since more than one row expansion renderer can be registered we let each decide if they can handle that
            // data
            // Here we will always handle it.
            return true;
        },
        render: function($container, rowData) {
            // rowData contains information about the row that is expanded.  We can see the cells, fields, and values
            // We will find the sourcetype cell to use its value
            var projectCell = _(rowData.cells).find(function (cell) {
               return cell.field === 'project_slug';
            });
            var pipelineCell = _(rowData.cells).find(function (cell) {
               return cell.field === 'pipeline_number';
            });
            //update the search with the sourcetype that we are interested in
            this._searchManager.set({ search: '`circleci_build_from_workflow(' + projectCell.value + ', ' + pipelineCell.value + ')` | eval time = strftime(_time, "%Y-%m-%d %H:%M:%S.%3N"), build_time_millis = tostring(build_time_millis, "commas")  | table build_num time workflows.job_name build_time_millis status build_url'});
            // $container is the jquery object where we can put out content.
            // In this case we will render our table and add it to the $container
            $container.append(this._inlineTableView.render().el);
        }
    });
    var tableElement = mvc.Components.getInstance("expand_with_events");
    tableElement.getVisualization(function(tableView) {
        // Add custom cell renderer, the table will re-render automatically.
        tableView.addRowExpansionRenderer(new EventSearchBasedRowExpansionRenderer());
    });
});
