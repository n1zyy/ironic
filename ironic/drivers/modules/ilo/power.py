# Copyright 2014 Hewlett-Packard Development Company, L.P.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""
iLO Power Driver
"""

from oslo.config import cfg

from ironic.common import exception
from ironic.common import states
from ironic.conductor import task_manager
from ironic.drivers import base
from ironic.drivers.modules.ilo import common as ilo_common
from ironic.openstack.common import importutils
from ironic.openstack.common import log as logging
from ironic.openstack.common import loopingcall

ilo_client = importutils.try_import('proliantutils.ilo.ribcl')


opts = [
    cfg.IntOpt('power_retry',
               default=6,
               help='Number of times a power operation needs to be retried'),
    cfg.IntOpt('power_wait',
               default=2,
               help='Amount of time in seconds to wait in between power '
                    'operations'),
]

CONF = cfg.CONF
CONF.register_opts(opts, group='ilo')

LOG = logging.getLogger(__name__)


def _get_power_state(node):
    """Returns the current power state of the node.

    :param node: The node.
    :returns: power state, one of :mod: `ironic.common.states`.
    :raises: InvalidParameterValue if required iLO credentials are missing.
    :raises: IloOperationError on an error from IloClient library.
    """

    ilo_object = ilo_common.get_ilo_object(node)

    # Check the current power state.
    try:
        power_status = ilo_object.get_host_power_status()

    except ilo_client.IloError as ilo_exception:
        LOG.error(_("iLO get_power_state failed for node %(node_id)s with "
                    "error: %(error)s."),
                  {'node_id': node.uuid, 'error': ilo_exception})
        operation = _('iLO get_power_status')
        raise exception.IloOperationError(operation=operation,
                                          error=ilo_exception)

    if power_status == "ON":
        return states.POWER_ON
    elif power_status == "OFF":
        return states.POWER_OFF
    else:
        return states.ERROR


def _wait_for_state_change(node, target_state):
    """Wait for the power state change to get reflected."""
    state = [None]
    retries = [0]

    def _wait(state):

        state[0] = _get_power_state(node)

        # NOTE(rameshg87): For reboot operations, initially the state
        # will be same as the final state. So defer the check for one retry.
        if retries[0] != 0 and state[0] == target_state:
            raise loopingcall.LoopingCallDone()

        if retries[0] > CONF.ilo.power_retry:
            state[0] = states.ERROR
            raise loopingcall.LoopingCallDone()

        retries[0] += 1

    # Start a timer and wait for the operation to complete.
    timer = loopingcall.FixedIntervalLoopingCall(_wait, state)
    timer.start(interval=CONF.ilo.power_wait).wait()

    return state[0]


def _set_power_state(node, target_state):
    """Turns the server power on/off or do a reboot.

    :param node: an ironic node object.
    :param target_state: target state of the node.
    :raises: InvalidParameterValue if an invalid power state was specified.
    :raises: IloOperationError on an error from IloClient library.
    :raises: PowerStateFailure if the power couldn't be set to target_state.
    """

    ilo_object = ilo_common.get_ilo_object(node)

    # Trigger the operation based on the target state.
    try:
        if target_state == states.POWER_OFF:
            ilo_object.hold_pwr_btn()
        elif target_state == states.POWER_ON:
            ilo_object.set_host_power('ON')
        elif target_state == states.REBOOT:
            ilo_object.reset_server()
            target_state = states.POWER_ON
        else:
            msg = _("_set_power_state called with invalid power state "
                "'%s'") % target_state
            raise exception.InvalidParameterValue(msg)

    except ilo_client.IloError as ilo_exception:
        LOG.error(_("iLO set_power_state failed to set state to %(tstate)s "
                    " for node %(node_id)s with error: %(error)s"),
                   {'tstate': target_state, 'node_id': node.uuid,
                     'error': ilo_exception})
        operation = _('iLO set_power_state')
        raise exception.IloOperationError(operation=operation,
                                          error=ilo_exception)

    # Wait till the state change gets reflected.
    state = _wait_for_state_change(node, target_state)

    if state != target_state:
        timeout = (CONF.ilo.power_wait) * (CONF.ilo.power_retry)
        LOG.error(_("iLO failed to change state to %(tstate)s "
                    "within %(timeout)s sec"),
                    {'tstate': target_state, 'timeout': timeout})
        raise exception.PowerStateFailure(pstate=target_state)


class IloPower(base.PowerInterface):

    def get_properties(self):
        return ilo_common.COMMON_PROPERTIES

    def validate(self, task):
        """Check if node.driver_info contains the required iLO credentials.

        :param task: a TaskManager instance.
        :param node: Single node object.
        :raises: InvalidParameterValue if required iLO credentials are missing.
        """
        ilo_common.parse_driver_info(task.node)

    def get_power_state(self, task):
        """Gets the current power state.

        :param task: a TaskManager instance.
        :param node: The Node.
        :returns: one of :mod:`ironic.common.states` POWER_OFF,
            POWER_ON or ERROR.
        :raises: InvalidParameterValue if required iLO credentials are missing.
        :raises: IloOperationError on an error from IloClient library.
        """
        return _get_power_state(task.node)

    @task_manager.require_exclusive_lock
    def set_power_state(self, task, power_state):
        """Turn the current power state on or off.

        :param task: a TaskManager instance.
        :param node: The Node.
        :param power_state: The desired power state POWER_ON,POWER_OFF or
            REBOOT from :mod:`ironic.common.states`.
        :raises: InvalidParameterValue if an invalid power state was specified.
        :raises: IloOperationError on an error from IloClient library.
        :raises: PowerStateFailure if the power couldn't be set to power_state.
        """
        _set_power_state(task.node, power_state)

    @task_manager.require_exclusive_lock
    def reboot(self, task):
        """Reboot the node

        :param task: a TaskManager instance.
        :param node: The Node.
        :raises: PowerStateFailure if the final state of the node is not
            POWER_ON.
        :raises: IloOperationError on an error from IloClient library.
        """
        node = task.node
        current_pstate = _get_power_state(node)
        if current_pstate == states.POWER_ON:
            _set_power_state(node, states.REBOOT)
        elif current_pstate == states.POWER_OFF:
            _set_power_state(node, states.POWER_ON)
