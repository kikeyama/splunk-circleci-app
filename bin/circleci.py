#!/usr/bin/env python
#
# Copyright 2013 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"): you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import absolute_import
import sys, json
import re, requests, uuid, datetime

from splunklib.modularinput import *
from splunklib import six
from splunklib.binding import HTTPError

from splunklib.client import connect
from splunklib.six.moves.urllib.parse import urlsplit

class CircleCIScript(Script):
    """All modular inputs should inherit from the abstract base class Script
    from splunklib.modularinput.script.
    They must override the get_scheme and stream_events functions, and,
    if the scheme returned by get_scheme has Scheme.use_external_validation
    set to True, the validate_input function.
    """
    def get_scheme(self):
        """When Splunk starts, it looks for all the modular inputs defined by
        its configuration, and tries to run them with the argument --scheme.
        Splunkd expects the modular inputs to print a description of the
        input in XML on stdout. The modular input framework takes care of all
        the details of formatting XML and printing it. The user need only
        override get_scheme and return a new Scheme object.

        :return: scheme, a Scheme object
        """
        # Splunk will display "Github Repository Forks" to users for this input
        scheme = Scheme("CircleCI Builds")

        scheme.description = "Streams events of CircleCI builds."
        # If you set external validation to True, without overriding validate_input,
        # the script will accept anything as valid. Generally you only need external
        # validation if there are relationships you must maintain among the
        # parameters, such as requiring min to be less than max in this example,
        # or you need to check that some resource is reachable or valid.
        # Otherwise, Splunk lets you specify a validation string for each argument
        # and will run validation internally using that string.
        scheme.use_external_validation = True
        scheme.use_single_instance = True

        api_token_argument = Argument("api_token")
        api_token_argument.title = "API Token"
        api_token_argument.data_type = Argument.data_type_string
        api_token_argument.description = "CircleCI API Token"
        api_token_argument.required_on_create = True

        interval_argument = Argument("interval")
        interval_argument.title = "Interval"
        interval_argument.data_type = Argument.data_type_string
        interval_argument.description = "Interval to execute input script"
        interval_argument.required_on_create = True

        name_argument = Argument("name")
        name_argument.title = "Name"
        name_argument.data_type = Argument.data_type_string
        name_argument.description = "Name of this input setting"
        name_argument.required_on_create = True

        vcs_argument = Argument("vcs")
        vcs_argument.title = "Your VCS (Version Control System)"
        vcs_argument.data_type = Argument.data_type_string
        vcs_argument.description = "Input your VCS (github or bitbucet)"
        vcs_argument.required_on_create = True

        org_argument = Argument("org")
        org_argument.title = "Organization name in VCS"
        org_argument.data_type = Argument.data_type_string
        org_argument.description = "Input your organization name (e.g. `splunk` in https://github.com/splunk/splunk-sdk-python)"
        org_argument.required_on_create = True

        # If you are not using external validation, you would add something like:
        #
        # scheme.validation = "api_token==xxxxxxxxxxxxxxx"
        scheme.add_argument(api_token_argument)
        scheme.add_argument(interval_argument)
        scheme.add_argument(name_argument)
        scheme.add_argument(vcs_argument)
        scheme.add_argument(org_argument)

        return scheme


    def validate_input(self, validation_definition):
        """In this example we are using external validation to verify that the Github
        repository exists. If validate_input does not raise an Exception, the input
        is assumed to be valid. Otherwise it prints the exception as an error message
        when telling splunkd that the configuration is invalid.

        When using external validation, after splunkd calls the modular input with
        --scheme to get a scheme, it calls it again with --validate-arguments for
        each instance of the modular input in its configuration files, feeding XML
        on stdin to the modular input to do validation. It is called the same way
        whenever a modular input's configuration is edited.

        :param validation_definition: a ValidationDefinition object
        """
        # Get the values of the parameters, and construct a URL for the Github API
        api_token = validation_definition.parameters["api_token"]
        interval = validation_definition.parameters["interval"]
        vcs = validation_definition.parameters["vcs"]

        # Examine if api_token matches appropriate format with regular expression
        # (0-9 or a-f) and 40 characters
        regexmatch_api_token = re.match(r'^[0-9a-f]{40}$', api_token)

        # re.match returning None means api_token doesn't match regex
        # https://docs.python.org/3/library/re.html#re.match
        if regexmatch_api_token is None:
            raise ValueError("API Token format is invalid. Must be 40 characters with 0-9 or a-f.")

        # Examine if interval is number format
        # (0-9 or a-f) and 40 characters
        regexmatch_interval = re.match(r'^[1-9][0-9]*$', interval)

        if regexmatch_interval is None:
            raise ValueError("Interval format is invalid. Must be non-negative integer.")
        else:
            try:
                int_interval = int(interval)
            except:
                raise ValueError("Interval format is invalid. Must be non-negative integer.")
            if int_interval < 60 or 86400 < int_interval:
                raise ValueError("Interval must be from 60 to 86400 (seconds).")

        # vcs must be github or bitbucket
        if vcs != 'github' and vcs != 'bitbucket':
            raise ValueError("VCS must be `github` or `bitbucket`.")


    def get_list_api(self, url, api_token, params, limit, ew):

        i = 0
        r_list = list()

        ew.log('DEBUG', 'Initial list request url=%s params=%s' % (url, json.dumps(params)))
        # HTTP Get Request
        r_dict = self.get_dict_api(url=url, api_token=api_token, params=params, ew=ew)

        params['page-token'] = r_dict.get('next_page_token')
        r_list.extend(r_dict.get('items'))
        ew.log('DEBUG', 'end Initial list request url=%s params=%s' % (url, json.dumps(params)))

        while params.get('page-token') is not None:

            ew.log('DEBUG', 'start get list loop url=%s i=%s limit=%s' % (url, str(i), str(limit)))
            if limit is not None and limit < i:
                break

            ew.log('DEBUG', 'Repeated list request url=%s params=%s i=%s' % (url, json.dumps(params), str(i)))
            # HTTP Get Request
            r_dict = self.get_dict_api(url=url, api_token=api_token, params=params, ew=ew)

            params['page-token'] = r_dict.get('next_page_token')
            r_list.extend(r_dict.get('items'))
            ew.log('DEBUG', 'end get list url=%s i=%s limit=%s list_count=%s' % (url, str(i), str(limit), str(len(r_list))))

            i += 1

        ew.log('DEBUG', json.dumps(r_list))

        return r_list

    def get_dict_api(self, url, api_token, params, ew):

        headers = {
            'Circle-Token': api_token,
            'Accept': 'application/json'
        }

        ew.log('DEBUG', 'start GET request url=%s params=%s' % (url, json.dumps(params)))
        # HTTP Get Request
        # params is not empty
        if bool(params):
            r = requests.get(url, params=params, headers=headers)
        # params is empty
        else:
            r = requests.get(url, headers=headers)

        # If not success in API request
        if r.status_code != 200:
            ew.log('WARN', 'status code is not 200 at %s' % url)
        else:
            ew.log('INFO', 'Success url=%s params=%s' % (url, json.dumps(params)))

        r_dict = json.loads(r.text)
        ew.log('DEBUG', 'end GET request url=%s params=%s' % (url, json.dumps(params)))

        return r_dict

    def init_kvstore(self, collection_name, ew):
        # Create or Get KV Store Collection
        # Create kv store for circleci project and build checkpoint
        # property from Script class
        service = self.service
        # HTTP 400 Bad Request -- Must use user context of 'nobody' when interacting 
        # with collection configurations (used user='splunk-system-user')
        service.namespace['owner'] = 'Nobody'

        kvstore_collection = None

        if collection_name not in service.kvstore:
            try:
                ew.log('DEBUG', 'Start creating kv store collection: %s' % collection_name)
                service.kvstore.create(collection_name)
                ew.log('DEBUG', 'Success creating kv store collection: %s' % collection_name)
            except:
                ew.log('ERROR', 'Failed creating kv store collection: %s' % collection_name)

        try:
            ew.log('DEBUG', 'Start getting kv store collection: %s' % collection_name)
            kvstore_collection = service.kvstore[collection_name]
            ew.log('DEBUG', 'Success getting kv store collection: %s' % collection_name)
        except Exception as e:
            ew.log('ERROR', 'Failed getting kv store collection: %s' % collection_name)
            ew.log('ERROR', e)

        if kvstore_collection is None:
            ew.log('ERROR', 'kv store collection is None: %s' % collection_name)

        return kvstore_collection

    def get_checkpoint(self, kvstore_collection, init_data, ew):

        checkpoint_data = init_data
        kvstore_key = checkpoint_data.get('_key')

        # Get checkpoint data
        try:
            ew.log('DEBUG', 'Start kv store with kvstore_key=%s' % kvstore_key)
            checkpoint_data = kvstore_collection.data.query_by_id(kvstore_key)
            ew.log('DEBUG', 'Finish kv store with kvstore_key=%s' % kvstore_key)

        # Get Error
        except HTTPError as e:
            ew.log('WARN', e)
            # Data is not found in kv store
            if '404 Not Found' in str(e):
                ew.log('DEBUG', 'HTTPError in getting checkpoint: %s' % e)

                # Insert new data
                try:
                    ew.log('DEBUG', 'Start inserting new kv store data checkpoint_data=%s' % json.dumps(checkpoint_data))
                    kvstore_collection.data.insert(json.dumps(checkpoint_data))
                    ew.log('DEBUG', 'Successfully insert new kv store data checkpoint_data=%s' % json.dumps(checkpoint_data))
                except:
                    ew.log('ERROR', 'Failed to insert new kv store data checkpoint_data=%s' % json.dumps(checkpoint_data))

        except Exception as e:
            ew.log('ERROR', 'Unknown error: %s' % e)

        return checkpoint_data

    def update_checkpoint(self, kvstore_collection, checkpoint_data, ew):
        # Update checkpoint data
        try:
            # Update kv store
            kvstore_key = checkpoint_data.get('_key')
            checkpoint_json = json.dumps(checkpoint_data)

            ew.log('DEBUG', 'Start updating kv store: %s' % checkpoint_json)
            kvstore_collection.data.update(kvstore_key, checkpoint_json)
            ew.log('DEBUG', 'Successfully update kv store: %s' % checkpoint_json)
        except Exception as e:
            ew.log('ERROR', 'Failed to update kv store: %s' % checkpoint_json)
            ew.log('ERROR', e)

    def stream_events(self, inputs, ew):
        """This function handles all the action: splunk calls this modular input
        without arguments, streams XML describing the inputs to stdin, and waits
        for XML on stdout describing events.

        If you set use_single_instance to True on the scheme in get_scheme, it
        will pass all the instances of this input to a single instance of this
        script.

        :param inputs: an InputDefinition object
        :param ew: an EventWriter object
        """

#        # Create kv store for circleci project and build checkpoint
#        # property from Script class
#        service = self.service
#        # HTTP 400 Bad Request -- Must use user context of 'nobody' when interacting 
#        # with collection configurations (used user='splunk-system-user')
#        service.namespace['owner'] = 'Nobody'

        # KV Store Collection name
        pipeline_collection_name = '_circleci_pipeline_checkpoint_collection'
        workflow_collection_name = '_circleci_workflow_checkpoint_collection'
        job_collection_name = '_circleci_job_checkpoint_collection'

#        # KV Store Collection
#        if job_collection_name not in service.kvstore:
#            try:
#                ew.log('DEBUG', 'Start creating kv store collection: %s' % job_collection_name)
#                service.kvstore.create(job_collection_name)
#                ew.log('DEBUG', 'Success creating kv store collection: %s' % job_collection_name)
#            except:
#                ew.log('ERROR', 'Failed creating kv store collection: %s' % job_collection_name)
#                continue
#
#        try:
#            ew.log('DEBUG', 'Start getting kv store collection: %s' % job_collection_name)
#            kvstore_collection = service.kvstore[job_collection_name]
#            ew.log('DEBUG', 'Success getting kv store collection: %s' % job_collection_name)
#        except:
#            ew.log('ERROR', 'Failed getting kv store collection: %s' % job_collection_name)
#            continue

        pipeline_kvstore_collection = self.init_kvstore(collection_name=pipeline_collection_name, ew=ew)
        workflow_kvstore_collection = self.init_kvstore(collection_name=workflow_collection_name, ew=ew)
        job_kvstore_collection = self.init_kvstore(collection_name=job_collection_name, ew=ew)

        # Go through each input for this modular input
        for input_name, input_item in six.iteritems(inputs.inputs):
            # Get fields from the InputDefinition object
            api_token = input_item["api_token"]
            interval = int(input_item["interval"])
            vcs = input_item["vcs"]
            org = input_item["org"]
            ew.log('INFO', 'read circieci api_token=%s vcs=%s org=%s' % (api_token, vcs, org))

            # Create an Event object, and set its fields
            event = Event()
            event.stanza = input_name
            event.host = 'circleci.com'

            # Get all pipelines
            # Lists all pipelines you are following on CircleCI
            # /api/v2/pipelineorg-slug=github/organization
            # https://circleci.com/docs/api/v2/#get-a-list-of-pipelines
            pipeline_endpoint = 'https://circleci.com/api/v2/pipeline'

            ew.log('DEBUG', 'start GET request pipeline_endpoint: %s' % pipeline_endpoint)
            params = {
                'org-slug': vcs + '/' + org
            }
#            headers = {
#                'Circle-Token': api_token,
#                'Accept': 'application/json'
#            }

            # Set pipeline page limit to be determined based on interval
            # Max: 100 pages
            pipeline_limit = min(interval // 60, 100)

            # HTTP Get Request
            pipelines = self.get_list_api(url=pipeline_endpoint, api_token=api_token, params=params, limit=pipeline_limit, ew=ew)
#            resp_pipelines = requests.get(pipeline_endpoint, params=params, headers=headers)
#            pipelines = json.loads(resp_pipelines.text)
#            ew.log('DEBUG', 'end GET request pipeline_endpoint: %s' % pipeline_endpoint)
#
#            # If status code is not 200, skip to next loop
#            if resp_pipelines.status_code != 200:
#                ew.log('WARN', 'status code is not 200 at %s' % pipeline_endpoint)
#                continue
#
#            pipeline_next_page_token = pipelines.get('next_page_token')
#            if pipeline_next_page_token is not None:
#                # GET next page here
#                params['page-token'] = pipeline_next_page_token
#                # DO SOMETHING FOR NEXT PAGE
#                # Get next page up to 10 times if no checkpoint stored

            for pipeline in pipelines:
                ew.log('DEBUG', 'Start getting each element from pipeline object')
                pipeline_id = pipeline.get('id')
                project_slug = pipeline.get('project_slug')
                pipeline_num = pipeline.get('number')
                updated_at = pipeline.get('updated_at')
                ew.log('DEBUG', 'Finish getting each element from project object')

                # If no data in either of username, vcs_type, or reponame, then skip
                if pipeline_id is None or project_slug is None or pipeline_num is None:
                    ew.log('WARN', 'skip id=%s project_slug=%s pipeline_num=%s' % (pipeline_id, project_slug, pipeline_num))
                    continue

                ew.log('INFO', 'Start processing pipeline: project_slug=%s number=%s' % (project_slug, pipeline_num))

#                # Pipeline checkpoint
#                ew.log('INFO', 'Getting pipeline checkpoint')
#                pipeline_checkpoint_data = {
#                    '_key': pipeline_id,
#                    'number': pipeline_num,
#                    'project_slug': project_slug,
#                    'updated_at': 'Unknown'
#                }
#                pipeline_checkpoint_data = self.get_checkpoint(
#                    kvstore_collection=pipeline_kvstore_collection, 
#                    init_data=pipeline_checkpoint_data, 
#                    ew=ew)
#
#                # Checkpoint definition
#                pipeline_checkpoint_updated_at = pipeline_checkpoint_data.get('updated_at')
#
#                # If updated_at matches checkpoint's value, skip the following process
#                if updated_at == pipeline_checkpoint_updated_at:
#                    ew.log('DEBUG', 'skip this pipeline: project_slug=%s pipeline_num=%s' \
#                        % (project_slug, str(pipeline_num)))
#                    continue

                # Get pipeline workflows
                # /api/v2/pipeline/{pipeline-id}/workflow
                # https://circleci.com/docs/api/v2/#get-a-pipeline-39-s-workflows
                workflows_endpoint = 'https://circleci.com/api/v2/pipeline/%s/workflow' % pipeline_id
                ew.log('DEBUG', 'start GET request workflows_endpoint=%s' % workflows_endpoint)

                # HTTP Get Request
                now = datetime.datetime.now()
                workflows = self.get_list_api(url=workflows_endpoint, api_token=api_token, params=dict(), limit=None, ew=ew)
#                resp_workflows = requests.get(workflows_endpoint, headers=headers)
#
#                # If not success in API request
#                if resp_workflows.status_code != 200:
#                    ew.log('WARN', 'status code is not 200 at %s' % workflows_endpoint)
#                    continue
#                else:
#                    ew.log('INFO', 'Success workflows_endpoint=%s' % workflows_endpoint)
#
#                workflows = json.loads(resp_workflows.text)
#                ew.log('DEBUG', 'end GET request workflows_endpoint=%s' % workflows_endpoint)
#
#                workflow_next_page_token = workflows.get('next_page_token')
#                if workflow_next_page_token is not None:
#                    # GET next page here
#                    params['page-token'] = workflow_next_page_token


                for workflow in workflows:

                    workflow_id = workflow.get('id')
                    workflow_name = workflow.get('name')
                    workflow_status = workflow.get('status')
                    project_slug = workflow.get('project_slug')

                    # 
                    if workflow_id is None:
                        ew.log('DEBUG', 'workflow_id is None workflow_id=%s workflow_name=%s' \
                            % (workflow_id, workflow_name))
                        continue

                    # Workflow checkpoint
                    ew.log('INFO', 'Getting workflow checkpoint')
                    workflow_checkpoint_data = {
                        '_key': workflow_id,
                        'name': workflow_name,
                        'project_slug': project_slug,
                        'status': 'Unknown'
                    }
                    workflow_checkpoint_data = self.get_checkpoint(
                        kvstore_collection=workflow_kvstore_collection, 
                        init_data=workflow_checkpoint_data, 
                        ew=ew)

                    # Checkpoint definition
                    workflow_checkpoint_status = workflow_checkpoint_data.get('status')

                    # If status matches checkpoint's value, skip the following process
                    if workflow_status == workflow_checkpoint_status:
                        ew.log('DEBUG', 'skip this workflow: project_slug=%s workflow_name=%s' \
                            % (project_slug, workflow_name))
                        continue

                    # add field workflow_time for _time
                    if workflow.get('stopped_at') is not None:
                        workflow['workflow_time'] = workflow.get('stopped_at')
                    else:
                        # set current time as %Y-%m-%dT%H:%M:%S.%2NZ
                        workflow['workflow_time'] = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-4] + 'Z'
                    # Attach pipeline data at workflow
                    workflow['trigger'] = pipeline['trigger']
                    workflow['vcs'] = pipeline['vcs']
                    # Add username and reponame to comply with job data
                    if sys.version_info[0] == 2:
                        project_slug = project_slug.encode('utf-8')
                    elif sys.version_info[0] == 3:
                        project_slug = project_slug
                    left_separator = project_slug.find('/')
                    right_separator = project_slug.rfind('/')
                    workflow['username'] = project_slug[left_separator+1:right_separator]
                    workflow['reponame'] = project_slug[right_separator+1:]

                    # Set workflow sourcetype
                    event.sourceType = 'circleci:workflow'

                    # Set event data
                    event.data = json.dumps(workflow)

                    # Write event data to Splunk
                    try:
                        ew.write_event(event)
                        ew.log('DEBUG', 'Successfully write circleci workflow event: workflow_id=%s workflow_name=%s project_slug=%s' \
                            % (workflow_id, workflow_name, project_slug))

                    except Exception as e:
                        ew.log('ERROR', 'Failed to write circleci workflow event: workflow_id=%s workflow_name=%s project_slug=%s' \
                            % (workflow_id, workflow_name, project_slug))
                        ew.log('ERROR', e)
                        continue

                    # Get Jobs in a workflow
                    # /workflow/{id}/job
                    # https://circleci.com/docs/api/v2/#get-a-workflow-39-s-jobs
                    jobs_endpoint = 'https://circleci.com/api/v2/workflow/%s/job' % workflow_id
                    ew.log('DEBUG', 'start GET request jobs_endpoint=%s' % jobs_endpoint)

                    # HTTP Get Request
                    jobs = self.get_list_api(url=jobs_endpoint, api_token=api_token, params=dict(), limit=None, ew=ew)
#                    resp_jobs = requests.get(jobs_endpoint, headers=headers)
#
#                    # If not success in API request
#                    if resp_jobs.status_code != 200:
#                        ew.log('WARN', 'status code is not 200 at %s' % jobs_endpoint)
#                        continue
#                    else:
#                        ew.log('INFO', 'Success jobs_endpoint=%s' % jobs_endpoint)
#
#                    jobs = json.loads(resp_jobs.text)
#                    ew.log('DEBUG', 'end GET request jobs_endpoint=%s' % jobs_endpoint)
#
#                    job_next_page_token = jobs.get('next_page_token')
#                    if job_next_page_token is not None:
#                        # GET next page here
#                        params['page-token'] = job_next_page_token
#                        # DO SOMETHING FOR NEXT PAGE


                    # 
                    for job in jobs:

                        job_id = job.get('id')
                        job_number = job.get('job_number')
                        project_slug = job.get('project_slug')
                        job_status = job.get('status')


#                        # KV Store Collection Data
#                        build_checkpoint_data = None
#                        # Get data by id
#                        try:
#                            ew.log('DEBUG', 'Start query_by_id kv store with key=%s' % job_id)
#                            build_checkpoint_data = kvstore_collection.data.query_by_id(job_id)
#                            ew.log('DEBUG', 'Finish query_by_id kv store with key=%s' % job_id)
#
#                            ew.log('DEBUG', 'Start getting build_checkpoint_data=%s' % json.dumps(build_checkpoint_data))
#                            checkpoint_build_num = build_checkpoint_data.get('build_num', 0)
#                            checkpoint_status = build_checkpoint_data.get('status', 'unknown')
#                            ew.log('DEBUG', 'Finish getting build_checkpoint_data=%s' % json.dumps(build_checkpoint_data))
#
#                        # Get Error
#                        except HTTPError as e:
#                            ew.log('WARN', e)
#                            if '404 Not Found' not in str(e):
#                                ew.log('DEBUG', 'HTTPError in getting checkpoint: %s' % e)
#                                # Skip the following process unless "HTTP 404 Not Found"
#                                continue
#
#                            # If 404 not fount, create
#                            checkpoint_build_num = 0
#                            checkpoint_status = 'unknown'
#                            build_checkpoint_data = {
#                                '_key': kvstore_key, 
#                                'build_url': build_url ,
#                                'build_num': checkpoint_build_num, 
#                                'status': checkpoint_status
#                            }
#                            # Insert new data
#                            try:
#                                ew.log('DEBUG', 'Start inserting new kv store data build_checkpoint_data=%s' % build_checkpoint_data)
#                                kvstore_collection.data.insert(json.dumps(build_checkpoint_data))
#                                ew.log('DEBUG', 'Success inserting new kv store data build_checkpoint_data=%s' % build_checkpoint_data)
#                            except:
#                                ew.log('ERROR', 'Failed inserting new kv store data build_checkpoint_data=%s' % build_checkpoint_data)
#                                continue
#
#                        except Exception as e:
#                            ew.log('ERROR', 'Unknown error: %s' % e)
#                            continue

                        if job_number is None:
                            ew.log('DEBUG', 'skip this job: project_slug=%s job_number=%s' \
                                % (project_slug, job_number))
                            continue

                        # Job checkpoint
                        ew.log('INFO', 'Getting job checkpoint')
                        job_checkpoint_data = {
                            '_key': job_id,
                            'job_number': job_number,
                            'project_slug': project_slug,
                            'status': 'Unknown'
                        }
                        job_checkpoint_data = self.get_checkpoint(
                            kvstore_collection=job_kvstore_collection, 
                            init_data=job_checkpoint_data, 
                            ew=ew)

                        # Checkpoint definition
                        job_checkpoint_status = job_checkpoint_data.get('status')

                        # If status matches checkpoint's value, skip the following process
                        if job_status == job_checkpoint_status:
                            ew.log('DEBUG', 'skip this job: project_slug=%s job_number=%s' \
                                % (project_slug, job_number))
                            continue


                        # Set sourcetype in event data
                        event.sourceType = 'circleci:job'

                        # Set current time to set job_time
                        now = datetime.datetime.now()

                        # Returns full details for a single build. The response includes all of 
                        # the fields from the build summary.
                        # /project/:vcs-type/:username/:project/:build_num
                        job_detail_endpoint = 'https://circleci.com/api/v1.1/project/%s/%s' \
                            % (project_slug, job_number)

                        # HTTP Get Request
                        job_detail = self.get_dict_api(url=job_detail_endpoint, api_token=api_token, params=None, ew=ew)

#                        # If not success in API request
#                        if resp_job_detail.status_code != 200:
#                            ew.log('WARN', 'status code is not 200 at %s' % job_detail_endpoint)
#                            continue
#                        else:
#                            ew.log('INFO', 'Success job_detail_endpoint=%s' % job_detail_endpoint)
#
#                        job_detail = json.loads(resp_job_detail.text)
#                        ew.log('DEBUG', 'end GET request job_detail_endpoint=%s' % job_detail_endpoint)

                        username = job_detail.get('username')
                        reponame = job_detail.get('reponame')
                        build_num = job_detail.get('build_num')

                        # Create job event data
                        job_event_data = dict()
                        # add field job_time for _time
                        if job_detail.get('stop_time') is not None:
                            job_event_data['job_time'] = job_detail.get('stop_time')
                        else:
                            # set current time as %Y-%m-%dT%H:%M:%S.%3NZ
                            job_event_data['job_time'] = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                        job_event_data['stop_time'] = job_detail.get('stop_time')
                        job_event_data['start_time'] = job_detail.get('start_time')
                        job_event_data['queued_time'] = job_detail.get('queued_at')
                        if job_event_data.get('build_parameters') is not None:
                            job_event_data['job_name'] = job_detail.get('build_parameters').get('CIRCLE_JOB')
                        else:
                            job_event_data['job_name'] = 'Unknown'
                        job_event_data['reponame'] = job_detail.get('reponame')
                        job_event_data['build_num'] = job_detail.get('build_num')
                        job_event_data['build_url'] = job_detail.get('build_url')
                        job_event_data['branch'] = job_detail.get('branch')
                        job_event_data['status'] = job_detail.get('status')
                        job_event_data['fail_reason'] = job_detail.get('fail_reason')
                        job_event_data['build_time_millis'] = job_detail.get('build_time_millis')
                        job_event_data['timedout'] = job_detail.get('timedout')
                        job_event_data['username'] = job_detail.get('username')
                        job_event_data['owners'] = job_detail.get('owners')
                        job_event_data['author_name'] = job_detail.get('author_name')
                        if job_event_data.get('user') is not None:
                            job_event_data['avatar_url'] = job_detail.get('user').get('avatar_url')
                            job_event_data['user_id'] = job_detail.get('user').get('id')
                        else:
                            job_event_data['avatar_url'] = ''
                        job_event_data['build_time_millis'] = job_detail.get('build_time_millis')
                        job_event_data['workflows'] = job_detail.get('workflows')
                        job_event_data['vcs'] = {}
                        job_event_data['vcs']['commit_time'] = job_detail.get('committer_date')
                        job_event_data['vcs']['type'] = job_detail.get('vcs_type')
                        job_event_data['vcs']['url'] = job_detail.get('vcs_url')
                        job_event_data['vcs']['revision'] = job_detail.get('vcs_revision')
                        job_event_data['vcs']['tag'] = job_detail.get('vcs_tag')
                        job_event_data['vcs']['committer_name'] = job_detail.get('committer_name')
                        job_event_data['vcs']['subject'] = job_detail.get('subject')

                        # Set event data
                        event.data = json.dumps(job_event_data)

                        # Write event data to Splunk
                        try:
                            ew.write_event(event)
                            ew.log('DEBUG', 'Successfully write circleci job event: username=%s reponame=%s build_num=%s' \
                                % (username, reponame, str(build_num)))

                        except Exception as e:
                            ew.log('ERROR', 'Failed to write circleci job event: username=%s reponame=%s build_num=%s' \
                                % (username, reponame, str(build_num)))
                            ew.log('ERROR', e)
                            continue

                        # Update job checkpoint
                        job_checkpoint_data['status'] = job_detail.get('status')
                        self.update_checkpoint(
                            kvstore_collection=job_kvstore_collection, 
                            checkpoint_data=job_checkpoint_data, 
                            ew=ew)

#                        try:
#                            ew.log('DEBUG', 'Start updating kv store: %s' % build_checkpoint_data)
#
#                            # Update kv store
#                            build_checkpoint_data['build_num'] = build_num
#                            build_checkpoint_data['status'] = job_detail.get('status', 'unknown')
#                            build_checkpoint_json = json.dumps(build_checkpoint_data)
#                            kvstore_collection.data.update(kvstore_key, build_checkpoint_json)
#
#                            ew.log('DEBUG', 'Success updating kv store: %s' % build_checkpoint_json)
#                        except:
#                            ew.log('ERROR', 'Failed updating kv store: %s' % build_checkpoint_json)
#                            continue

                        # Clear event data for next loop
                        job_event_data.clear()


                        # Write steps data in each job to splunk
                        ew.log('DEBUG', 'Start processing steps data collection')
                        for step in job_detail.get('steps'):
                            # Set sourcetype in event data
                            event.sourceType = 'circleci:step'

                            # each step has actions in list
                            for action in step.get('actions'):

                                ew.log('INFO', 'Start processing step event allocation_id=%s step=%s' \
                                    % (action.get('allocation_id'), str(action.get('step'))))

                                # Create step event data
                                # add field step_time for _time
                                if action.get('end_time') is not None:
                                    action['step_time'] = action.get('end_time')
                                else:
                                    # set current time as %Y-%m-%dT%H:%M:%S.%3NZ
                                    action['step_time'] = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
                                # add job key
                                if job_detail.get('workflows') is not None:
                                    action['job_id'] = job_detail.get('workflows').get('job_id')
                                    action['job_name'] = job_detail.get('workflows').get('job_name')
                                else:
                                    action['job_id'] = 'Unknown'
                                    action['job_name'] = 'Unknown'

                                # Set event data
                                event.data = json.dumps(action)

                                # Write event data to Splunk
                                try:
                                    ew.write_event(event)
                                    ew.log('DEBUG', 'Successfully write circleci step event: username=%s ' \
                                        'reponame=%s build_num=%s allocation_id=%s step=%s' \
                                        % (username, reponame, str(build_num), \
                                            action.get('allocation_id'), str(action.get('step'))))
                                except Exception as e:
                                    ew.log('ERROR', 'Failed to write circleci step event: username=%s ' \
                                        'reponame=%s build_num=%s allocation_id=%s step=%s' \
                                        % (username, reponame, str(build_num), \
                                            action.get('allocation_id'), str(action.get('step'))))
                                    ew.log('ERROR', e)

                                ew.log('INFO', 'Finish processing step event: allocation_id=%s step=%s' \
                                    % (action.get('allocation_id'), str(action.get('step'))))


                        ew.log('INFO', 'Finish processing job event: username=%s reponame=%s build_num=%s' \
                            % (username, reponame, str(build_num)))

                    # Update workflow checkpoint
                    workflow_checkpoint_data['status'] = workflow_status
                    self.update_checkpoint(
                        kvstore_collection=workflow_kvstore_collection, 
                        checkpoint_data=workflow_checkpoint_data, 
                        ew=ew)

                    ew.log('INFO', 'Finish processing workflow: project_slug=%s name=%s' \
                        % (project_slug, workflow_name))

#                # Update pipeline checkpoint
#                pipeline_checkpoint_data['updated_at'] = updated_at
#                self.update_checkpoint(kvstore_collection=pipeline_kvstore_collection, 
#                    checkpoint_data=pipeline_checkpoint_data, 
#                    ew=ew)

                ew.log('INFO', 'Finish processing pipeline: project_slug=%s number=%s' % (project_slug, pipeline_num))

            ew.log('INFO', 'Finish processing input: api_token=%s vcs=%s org=%s' % (api_token, vcs, org))


if __name__ == "__main__":
    sys.exit(CircleCIScript().run(sys.argv))
