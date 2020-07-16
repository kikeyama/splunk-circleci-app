# Splunk App for CircleCI

Collect and visualize build history from CircleCI cloud

## Dashboards

WIP

## Data

### Build data

sourcetype: `circleci:job`

### Step data

sourcetype: `circleci:step`

## How to setup

### 1. Install this app into your Splunk

#### Splunk single instance

1. Clone or download this repository at `$SPLUNK_HOME/etc/apps` (`$SPLUNK_HOME` is the directory where you installed Splunk)
2. Rename the repo directory to `circleci`

#### Splunk distributed or cluster

1. Install and setup Heavy Forwarder in any host (EC2 instance, your baremetal server, or VM, etc)
2. Clone or download then rename the directory this repo at Search Heads, Indexers, and Heavy Forwarder 


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
`interval` | Interval (seconds) this app collects CircleCI data | 600
