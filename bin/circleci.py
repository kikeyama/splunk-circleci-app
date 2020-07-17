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

        # If you are not using external validation, you would add something like:
        #
        # scheme.validation = "api_token==xxxxxxxxxxxxxxx"
        scheme.add_argument(api_token_argument)
        scheme.add_argument(interval_argument)
        scheme.add_argument(name_argument)

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
            if int_interval < 60:
                raise ValueError("Interval must be equal or greater than 60 (seconds).")


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
        # Go through each input for this modular input
        for input_name, input_item in six.iteritems(inputs.inputs):
            # Get fields from the InputDefinition object
            api_token = input_item["api_token"]
            ew.log('INFO', 'read circieci api token: %s' % api_token)

            # Get all projects
            # Lists all projects you are following on CircleCI, with build 
            # information organized by branch.
            # /projects 
            projects_endpoint = 'https://circleci.com/api/v1.1/projects'

            ew.log('DEBUG', 'start GET request projects_endpoint: %s' % projects_endpoint)
            params = {'circle-token': api_token}

            # HTTP Get Request
            resp_projects = requests.get(projects_endpoint, params=params)
            projects = json.loads(resp_projects.text)
            ew.log('DEBUG', 'end GET request projects_endpoint')

            if resp_projects.status_code != 200:
                ew.log('WARN', 'status code is not 200 at %s' % projects_endpoint)
                continue

            # Create an Event object, and set its fields
            event = Event()
            event.stanza = input_name

            # Create kv store for circleci project and build checkpoint
            # property from Script class
            service = self.service
            # HTTP 400 Bad Request -- Must use user context of 'nobody' when interacting 
            # with collection configurations (used user='splunk-system-user')
            service.namespace['owner'] = 'Nobody'

            # KV Store Collection name
            collection_name = '_circleci_job_checkpoint_collection'


            ## DO NOT UNCOMMENT (COMMENT OUT THIS STEP AFTER TESTING)
            # Clear kv store collection
#            service.kvstore.delete(collection_name)
            ##


            if collection_name not in service.kvstore:
                try:
                    ew.log('DEBUG', 'Start creating kv store collection: %s' % collection_name)
                    service.kvstore.create(collection_name)
                    ew.log('DEBUG', 'Success creating kv store collection: %s' % collection_name)
                except:
                    ew.log('ERROR', 'Failed creating kv store collection: %s' % collection_name)
                    continue

            try:
                ew.log('DEBUG', 'Start getting kv store collection: %s' % collection_name)
                kvstore_collection = service.kvstore[collection_name]
                ew.log('DEBUG', 'Success getting kv store collection: %s' % collection_name)
            except:
                ew.log('ERROR', 'Failed getting kv store collection: %s' % collection_name)
                continue

            for project in projects:
                ew.log('DEBUG', 'Start getting each element from project object')
                username = project.get('username', '')
                vcs_type = project.get('vcs_type', '')
                reponame = project.get('reponame', '')
                vcs_url = project.get('vcs_url', '')
                status = project.get('status', '')
                ew.log('DEBUG', 'Finish getting each element from project object')

                # If no data in either of username, vcs_type, or reponame, then skip
                if username == '' or vcs_type == '' or reponame == '':
                    ew.log('DEBUG', 'skip username=%s vcs_type=%s reponame=%s' % (username, vcs_type, reponame))
                    continue

                ew.log('DEBUG', 'Start uuid of vcs_url=%s' % vcs_url)
                # requests response is unicode at python 2
                if sys.version_info[0] == 2:
                    kvstore_key = str(uuid.uuid3(uuid.NAMESPACE_URL, vcs_url.encode('utf-8')))
                elif sys.version_info[0] == 3:
                    kvstore_key = str(uuid.uuid3(uuid.NAMESPACE_URL, vcs_url))
                ew.log('DEBUG', 'Finish uuid of vcs_url=%s' % vcs_url)

                # Get checkpoint data from kv store
                build_checkpoint_data = None
                try:
                    ew.log('DEBUG', 'Start query_by_id kv store with key=%s' % kvstore_key)
                    build_checkpoint_data = kvstore_collection.data.query_by_id(kvstore_key)
                    ew.log('DEBUG', 'Finish query_by_id kv store with key=%s' % kvstore_key)
                except HTTPError as e:
                    ew.log('WARN', e)
                    if '404 Not Found' not in str(e):
                        # Skip the following process unless "HTTP 404 Not Found"
                        continue
                except Exception as e:
                    ew.log('ERROR', 'Unknown error: %s' % e)
                    continue
#                except Exception as e:
#                    ew.log('INFO', 'error at query_by_id: %s' % e)
#                    if '404 Not Found' not in e:
#                        # Skip the following process unless "HTTP 404 Not Found"
#                        continue

                if build_checkpoint_data is not None:
                    # If checkpoint is stored, load build_num
                    ew.log('DEBUG', 'Start getting build_checkpoint_data=%s' % json.dumps(build_checkpoint_data))
#                    build_checkpoint_data = json.loads(build_checkpoint)
                    checkpoint_build_num = build_checkpoint_data.get('build_num', 0)
                    checkpoint_status = build_checkpoint_data.get('status', 'unknown')
                    ew.log('DEBUG', 'Finish getting build_checkpoint_data=%s' % json.dumps(build_checkpoint_data))
                else:
                    # If no checkpoint stored, initialize with 0
                    checkpoint_build_num = 0
                    checkpoint_status = 'unknown'
                    build_checkpoint_data = {
                        '_key': kvstore_key, 
                        'vcs_url': vcs_url ,
                        'build_num': checkpoint_build_num, 
                        'status': checkpoint_status
                    }
                    try:
                        ew.log('DEBUG', 'Start inserting new kv store data build_checkpoint_data=%s' % build_checkpoint_data)
                        kvstore_collection.data.insert(json.dumps(build_checkpoint_data))
                        ew.log('DEBUG', 'Success inserting new kv store data build_checkpoint_data=%s' % build_checkpoint_data)
                    except:
                        ew.log('ERROR', 'Failed inserting new kv store data build_checkpoint_data=%s' % build_checkpoint_data)
                        continue

                # Returns a build summary for each of the last 30 builds for a single git repo.
                # /project/:vcs-type/:username/:project
                builds_endpoint = 'https://circleci.com/api/v1.1/project/%s/%s/%s' % (vcs_type, username, reponame)
                ew.log('DEBUG', 'start GET request builds_endpoint=%s' % builds_endpoint)

                # HTTP Get Request
                resp_builds = requests.get(builds_endpoint, params=params)

                # If not success in API request
                if resp_builds.status_code != 200:
                    ew.log('WARN', 'status code is not 200 at %s' % builds_endpoint)
                    continue
                else:
                    ew.log('INFO', 'Success builds_endpoint=%s' % builds_endpoint)

                builds = json.loads(resp_builds.text)
                ew.log('DEBUG', 'end GET request builds_endpoint=%s' % builds_endpoint)

                # build_num and status in each build to be checked
                build_nums = []
                for build in builds:
                    build_nums_data = {'build_num': build.get('build_num', 0), 'status': build.get('status', 'unknown')}
                    build_nums.append(build_nums_data)

#                # Sort build_num
#                # Caution!! This step must not be deleted for build_num in kv store control
#                build_nums.sort()

                # Sort build_num and status with ascending build_num
                build_nums_sorted = sorted(build_nums, key=lambda i: i['build_num'])

#                ## !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
#                # Project break and Build break???
#                previous_build_num = checkpoint_build_num

                # GET circleci detail job data and write event to splunk for each build_num
                for build_num_status in build_nums_sorted:

#                for build in builds:
#                    build_num = build.get('build_num', 0)

                    build_num = build_num_status.get('build_num', 0)
                    status = build_num_status.get('status', 'unknown')

                    # If the build's build_num is smaller than checkpoint's value 
                    #    AND status matches checkpoint's value, 
                    # skip the following process
                    if build_num <= checkpoint_build_num and status == checkpoint_status:
                        ew.log('DEBUG', 'skip this build: %s/%s/%s build_num=%s ' \
                            % (vcs_type, username, reponame, build_num))
                        continue

                    # stop_time None means unfinished build? maybe?
#                    if build.get('stop_time') is None:
#                        ew.log('DEBUG', 'skip this build: %s/%s/%s stop_time is None ' \
#                            % (vcs_type, username, reponame))
#                        continue

                    # Set sourcetype in event data
                    event.sourceType = 'circleci:job'

                    # Set host in event data
                    build_url = build.get('build_url', 'https://circleci.com/')    # https://circleci.com/gh/...
                    host_start_pos = build_url.find('//')+2
                    host = build_url[host_start_pos:build_url.find('/', host_start_pos)]
                    event.host = host

                    # Returns full details for a single build. The response includes all of 
                    # the fields from the build summary.
                    # /project/:vcs-type/:username/:project/:build_num
                    job_detail_endpoint = 'https://circleci.com/api/v1.1/project/%s/%s/%s/%s' \
                        % (vcs_type, username, reponame, build_num)

                    # HTTP Get Request
                    resp_job_detail = requests.get(job_detail_endpoint, params=params)

                    # If not success in API request
                    if resp_job_detail.status_code != 200:
                        ew.log('WARN', 'status code is not 200 at %s' % job_detail_endpoint)
                        continue
                    else:
                        ew.log('INFO', 'Success job_detail_endpoint=%s' % job_detail_endpoint)

                    job_detail = json.loads(resp_job_detail.text)
                    ew.log('DEBUG', 'end GET request job_detail_endpoint=%s' % job_detail_endpoint)


                    # Create job event data
                    job_event_data = {}
                    now = datetime.datetime.now()
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
                            % (job_detail.get('username'), job_detail.get('reponame'), job_detail.get('build_num')))

                    except:
                        ew.log('DEBUG', 'Failed to write circleci job event: username=%s reponame=%s build_num=%s' \
                            % (job_detail.get('username'), job_detail.get('reponame'), job_detail.get('build_num')))
                        continue

                    # Update checkpoint
                    try:
#                        # Only if build num is greater than previous num
#                        #     OR status doesn't match checkpoint's status
#                        if build_num > previous_build_num or job_detail.get('status') != checkpoint_status:
                        ew.log('DEBUG', 'Current build_num=%s is greater than checkpoint_build_num=%s' \
                            % (str(build_num), str(checkpoint_build_num)))
                        ew.log('DEBUG', 'Start updating kv store: %s' % build_checkpoint_data)

                        # Update kv store
                        build_checkpoint_data['build_num'] = build_num
                        build_checkpoint_data['status'] = job_detail.get('status', 'unknown')
                        build_checkpoint_json = json.dumps(build_checkpoint_data)
                        kvstore_collection.data.update(kvstore_key, build_checkpoint_json)

                        # Update previous build_num
#                        previous_build_num = build_num
                        ew.log('DEBUG', 'Success updating kv store: %s' % build_checkpoint_json)
                    except:
                        ew.log('ERROR', 'Failed updating kv store: %s' % build_checkpoint_json)
                        continue

                    # Clear event data for next loop
                    job_event_data.clear()


                    # Write steps data in each job to splunk
                    ew.log('DEBUG', 'Start processing steps data collection')
                    for step in job_detail.get('steps'):
                        # Set sourcetype in event data
                        event.sourceType = 'circleci:step'

                        # each step has actions in list
                        for action in step.get('actions'):

                            ew.log('INFO', 'Start step="%s"' % action.get('name', 'Unknown'))

                            # Create step event data
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
                                    'reponame=%s build_num=%s step_name=%s' \
                                    % (job_detail.get('username'), job_detail.get('reponame'), \
                                        job_detail.get('build_num'), action.get('name')))
                            except:
                                ew.log('DEBUG', 'Failed to write circleci step event: username=%s ' \
                                    'reponame=%s build_num=%s step_name=%s' \
                                    % (job_detail.get('username'), job_detail.get('reponame'), \
                                        job_detail.get('build_num'), action.get('name')))

                            ew.log('INFO', 'End step="%s"' % action.get('name', 'Unknown'))


                    ew.log('INFO', 'Finish processing job event: username=%s reponame=%s build_num=%s' \
                        % (job_detail.get('username'), job_detail.get('reponame'), job_detail.get('build_num')))


                # Clear build_nums for next loop after finishing all build_num in the project
                if sys.version_info[0] == 2:
                    del build_nums[:]
                    del build_nums_sorted[:]
                elif sys.version_info[0] == 3:
                    build_nums.clear()
                    build_nums_sorted.clear()


if __name__ == "__main__":
    sys.exit(CircleCIScript().run(sys.argv))
