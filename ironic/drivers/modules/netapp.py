#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Ironic power driver for NetApp E-series.
"""

import os

from ironic.common import exception
from ironic.common import states
from ironic.common import utils
from ironic.conductor import task_manager
from ironic.drivers import base
from ironic.openstack.common import log as logging

import json
import re
import socket
import urllib2

LOG = logging.getLogger(__name__)


def _parse_driver_info(node):
    """Gets the information needed for accessing the node.

    :param node: the Node of interest.
    :returns: dictionary of information.
    :raises: InvalidParameterValue if any required parameters are missing
        or incorrect.

    """
    info = node.driver_info or {}
    endpoint = info.get('netapp_endpoint_uri')
    filer_id = info.get('netapp_filer_id')
    username = info.get('netapp_username')
    password = info.get('netapp_password')

    res = {
           'endpoint': endpoint,
           'username': username,
           'password': password,
           'filer_id': filer_id
          }

    if not endpoint:
        raise exception.InvalidParameterValue(_(
            "netapp_endpoint_uri must be configured"))
    if not filer_id:
        raise exception.InvalidParameterValue(_(
            "netapp_filer_id must be specified"))
    if not username or not password:
        raise exception.InvalidParameterValue(_(
            "netapp_username and netapp_password must be specified."))

    return res

def _get_auth(driver_info):
  url = "%s/utils/login" % driver_info['endpoint']
  req = urllib2.Request(url)
  req.headers['Content-Type'] = 'application/json'
  data = {'userId': driver_info['username'],
          'password': driver_info['password']}
  out = urllib2.urlopen(req, json.dumps(data))
  if int(out.code) == 200:
    cookie = dict(out.info())['set-cookie']
    session_id = re.split("\W", cookie)[1]
    return session_id

def _get(url, driver_info, data=None, timeout=None):
  LOG.debug("_get called")
  req = urllib2.Request(url)
  session_id = _get_auth(driver_info)
  req.add_header('Accept', 'application/json')
  req.add_header('Cookie', "JSESSIONID=%s" % session_id)
  LOG.debug("...about to fetch %s" % url)
  if data:
    data = json.dumps(data)
    req.add_header('Content-Type', 'application/json')
  out = urllib2.urlopen(req, data, timeout=timeout)
  LOG.debug("--- response code is %s" % out.code)
  if int(out.code) == 200:
    retval = out.read()
    return json.loads(retval)


def _fetch_statistics(driver_info):
    mash = []
    to_fetch = [{'label': 'volume-statistics', 'url': '/volume-statistics'},
                {'label': 'drive-statistics', 'url': '/drive-statistics'},
                {'label': 'system-statistics', 'url': ''},
                {'label': 'pool-statistics', 'url': '/storage-pools'}]
    for metric in to_fetch:
        LOG.debug("... looking up %s" % metric['label'])
        try:
            x = _get(driver_info['endpoint'] + '/v2/storage-systems/' + 
                     driver_info['filer_id'] + metric['url'], driver_info,
                     timeout=10)
            LOG.debug("... done")
            mash.append({metric['label']: x})
        except socket.timeout:
            # If we have trouble fetching the metrics, simply skip it.
            LOG.warn("+ timeout!")
            next
    return mash

class NetAppESeriesPower(base.PowerInterface):
    """Power interface to NetApp E-series filers."""

    def validate(self, task):
        """Check that the node's 'driver_info' is valid."""
        _parse_driver_info(task.node)

    def get_sensor_data(self, task):
        """Collect and collate performance metrics."""
        return _collect_metrics(task.node)

    def get_power_state(self, task):
        """Get the current power state of the task's node.

        Poll the host for the current power state of the task's node.

        :param task: a TaskManager instance containing the node to act on.
        :returns: power state. One of :class:`ironic.common.states`.
        :raises: InvalidParameterValue if any connection parameters are
            incorrect.
        :raises: NodeNotFound.
        :raises: SSHCommandFailed on an error from ssh.
        :raises: SSHConnectFailed if ssh failed to connect to the node.
        """
        driver_info = _parse_driver_info(task.node)
        LOG.debug("*** health check")
        status = _get(driver_info['endpoint'] + '/v2/storage-systems/' + 
                 driver_info['filer_id'], driver_info)
        LOG.debug("*** about to get stats!")
        fff = _fetch_statistics(driver_info)
        LOG.debug("+++ stats: %s" % fff)
        if(status['status'] == 'optimal' or status['status'] == 'needsAttn'):
            LOG.debug("*** reports it's powered on")
            # Okay, so... The REST API displays cached data if the thing 
            # is unreachable! So we need to do an active query too.
            # Let's ping the controller. If it times out, something is wrong,
            # and we can infer that it's offline.
            url = (driver_info['endpoint'] + '/v2/storage-systems/' + 
                   driver_info['filer_id'] + '/symbol/pingController')
            state = states.POWER_ON
            try:
                attempt = _get(url, driver_info, None, 10)
            except socket.timeout:
                LOG.warn("caught timeout!")
                state = states.POWER_OFF
            return state
        elif(status['status'] == 'offline'):
            LOG.debug("*** offline")
            return states.POWER_OFF
        else:
            LOG.debug("*** indeterminate state")
            return states.NO_STATE

    @task_manager.require_exclusive_lock
    def set_power_state(self, task, pstate):
        """Power control is awkward here, because we cannot power an E-series
        filer back on. Once it is off, it needs to be physically turned back
        on. Take note of the 'reboot' call where appropriate!

        :param task: a TaskManager instance containing the node to act on.
        :param pstate: Either POWER_ON or POWER_OFF from :class:
            `ironic.common.states`.
        :raises: InvalidParameterValue if any connection parameters are
            incorrect, or if the desired power state is invalid.
        :raises: PowerStateFailure if it failed to set power state to pstate.
        """
        driver_info = _parse_driver_info(task.node)

        # FIXME(matty_dubs) -- this needs error handling, especially since
        # this call can take a bit to return. It may take a bit to take
        # effect even when the call returns, so polling here for success
        # is likely not an effective use of our time.
        if pstate == states.POWER_OFF:
            status = _get(driver_info['endpoint'] + '/v2/storage-systems/' +
                          driver_info['filer_id'] + '/symbol/powerDownArray',
                          driver_info)

        return True  #  FIXME(matty_dubs) -- Don't do this.

    @task_manager.require_exclusive_lock
    def reboot(self, task):
        """Reboots a filer.

        This occurs via an API call that provides a warm reset, not by
        powering off and then on the filer.

        :param task: a TaskManager instance containing the node to act on.
        :raises: InvalidParameterValue if any connection parameters are
            incorrect.
        """
        driver_info = _parse_driver_info(task.node)

        status = _get(driver_info['endpoint'] + '/v2/storage-systems/' +
                      driver_info['filer_id'] + '/symbol/resetController',
                      driver_info)

