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
NetApp pseudo-driver
"""

from ironic.common import exception
from ironic.drivers import base
#from ironic.drivers.modules import ipminative
#from ironic.drivers.modules import ipmitool
from ironic.drivers.modules import netapp
#from ironic.drivers.modules import seamicro
#from ironic.drivers.modules import ssh
from ironic.drivers import utils
from ironic.openstack.common import importutils


class NetAppDriver(base.BaseDriver):
    def __init__(self):
        self.power = netapp.NetAppESeriesPower()

