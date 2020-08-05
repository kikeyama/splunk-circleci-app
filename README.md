[![<kikeyama>](https://circleci.com/gh/kikeyama/splunk-circleci-app.svg?style=svg)](<LINK>)

# Splunk App for CircleCI

Collect and visualize workflows, jobs, and steps data from CircleCI cloud  
  
This app provides the following capabilities.  
- Overview of your CircleCI pipelines
- Monitor workflows, build jobs, and steps
- Insights into your CircleCI pipelines and activities
- Direct link to CircleCI console from dashboards and log events.
  
It collects raw data through CircleCI API via python-based modular input. You can specify repository organizations and interval to collect data. Once you setup data inputs, this app automatically collect data from your pipeline and visualize it with built-in dashboards.  
  
If you find issues or feature requests, feel free to open [issues](https://github.com/kikeyama/splunk-circleci-app/issues).  

## Dashboards

### CircleCI Overview

![Pipeline and Workflow Overview](img/splunk_circleci_overview.png)  
  
- Number of triggered pipelines by status
- Recent workflows and drilldown to jobs
- Open CircleCI console from workflows table
- Workflows by project and timechart

### CircleCI Insights

Visualizing statistics and analytics for past 30 days.

- Status statistics by project
- Pipeline trigger types
- Triggered users
- Failure analysis and MTTR
- Build performance statistics

### CircleCI Monitor

![Workflow and Build Monitor](img/splunk_circleci_monitor.png)  
  
- Workflow monitor
- Event notification from [orb](https://circleci.com/orbs/registry/orb/kikeyama/splunk)
- Workflow details and drilldown to jobs and steps
- Open CircleCI console (workflow and job)

## Alerts

There are some built-in alert templates. Update notification like email, slack, etc.

Name | Description | Default Interval | Default Actions
-----|-------------|------------------|----------------
**CircleCI Failed Job Alert** | Searches `failed` status from CircleCI jobs for past 15 min | 10 min | Indexes as log event at `main` index
**CircleCI Modular Input Error** | Searches `ERROR` log_level from _internal logs for past 15 min | 10 min | Indexes as log event at `main` index

## Data

Source Types | Description | Data source
-------------|-------------|------------
`circleci:workflow` | Default sourcetype of CircleCI workflows | Modular Input
`circleci:job` | Default sourcetype of CircleCI jobs | Modular Input
`circleci:step` | Default sourcetype of CircleCI steps | Modular Input
`circleci:workflow:event` | Default sourcetype of CircleCI workflow [orb](https://circleci.com/orbs/registry/orb/kikeyama/splunk) | HTTP Event Collector
`circleci:build:event` | Default sourcetype of CircleCI job [orb](https://circleci.com/orbs/registry/orb/kikeyama/splunk) | HTTP Event Collector

## How to setup

### 1. Install this app into your Splunk

If you install from splunkbase (Splunk official app repository), [visit and download here](https://splunkbase.splunk.com/app/5162/).  
  
You can also [download latest release](https://github.com/kikeyama/splunk-circleci-app/releases) and install by following steps below.  
The release version syncs with that of published app in splunkbase. However, sometimes it may take a few days to publish the latest app at splunkbase. If you prefer install the latest one, [download from releases at this repository](https://github.com/kikeyama/splunk-circleci-app/releases).

#### Splunk Enterprise

1. [Download latest release](https://github.com/kikeyama/splunk-circleci-app/releases) and extract contents at `$SPLUNK_HOME/etc/apps` (`$SPLUNK_HOME` is the directory where you installed Splunk)
2. Restart Splunk

If you use distributed architecture or cluster, follow the official document to install app. See [App deployment overview - Splunk Documentation](https://docs.splunk.com/Documentation/Splunk/latest/Admin/Deployappsandadd-ons) for more details.

#### Splunk Cloud

Install this app in Search Heads, Indexing Peers, and [IDM (Inputs Data Manager)](https://docs.splunk.com/Documentation/SplunkCloud/latest/Admin/IntroGDI), then enable modular input at IDM.

### 2. Get your API Token at CircleCI

1. Access your CircleCI [user settings](https://app.circleci.com/settings/user/tokens) and `Create New Token`
2. Copy your API token

### 3. Create Data Inputs at Splunk

1. `Settings` > `Data Inputs` then click `CircleCI Builds`
2. Click `New` and input settings as following 

Field | Description | Default
------|-------------|--------
`name` | Input name you prefer (can be different from CircleCI API token name) | N/A
`API Token` | API Token you copied at the previous step | N/A
`Your VCS` | Version Control System (input `github` or `bitbucket`) | N/A
`Organization name` | Organization name (example: `splunk` in `https://github.com/splunk/splunk-sdk-python`) | N/A

__Optional Settings__

Click `More settings` and display optional settings.

Field | Description | Default
------|-------------|--------
`Interval` | Interval (seconds) this app collects CircleCI data | `600`
`Source type` | Source type is defined in modular input. Can not overwrite. | `Automatic`
`Host` | Host is defined in modular input. Can not overwrite. | SPLUNK HOST
`Index` | Set index name where CircleCI workflows, jobs, and steps data. | `default`


### 4. Update Search Macro

1. `Settings` > `Advanced search` then click `Search macros`
2. Click `circleci_orb_index` and change index name (default: `main`)

## Troubleshooting

### Checkpoint endpoint

To reduce overhead of API request and event writing, modular input uses KV Store to record checkpoint.  

**Workflow checkpoint:** `/servicesNS/nobody/system/storage/collections/data/_circleci_workflow_checkpoint_collection`  
**Job Checkpoint:** `/servicesNS/nobody/system/storage/collections/data/_circleci_job_checkpoint_collection`  
See [Splunk API Doc](https://docs.splunk.com/Documentation/Splunk/8.0.5/RESTREF/RESTkvstore)

If you'd like to re-index data, delete all checkpoint above.  

```
# Delete workflow checkpoints
curl -X DELETE -u <user>:<password> -k https://<splunk_hostname>:8089/servicesNS/nobody/system/storage/collections/data/_circleci_workflow_checkpoint_collection

# Delete job checkpoints
curl -X DELETE -u <user>:<password> -k https://<splunk_hostname>:8089/servicesNS/nobody/system/storage/collections/data/_circleci_job_checkpoint_collection
```

## Open issues

If you find issues or feature requests, feel free to open [issues](https://github.com/kikeyama/splunk-circleci-app/issues).
