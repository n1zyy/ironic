# -*- encoding: utf-8 -*-
#
# Copyright 2013 Hewlett-Packard Development Company, L.P.
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
Fake drivers used in testing.
"""

from ironic.common import exception
from ironic.drivers import base
from ironic.drivers.modules import agent
from ironic.drivers.modules import fake
from ironic.drivers.modules import iboot
from ironic.drivers.modules import ipminative
from ironic.drivers.modules import ipmitool
from ironic.drivers.modules import pxe
from ironic.drivers.modules import seamicro
from ironic.drivers.modules import ssh
from ironic.drivers import utils
from ironic.openstack.common import importutils


class FakeDriver(base.BaseDriver):
    """Example implementation of a Driver."""

    def __init__(self):
        self.power = fake.FakePower()
        self.deploy = fake.FakeDeploy()

        self.a = fake.FakeVendorA()
        self.b = fake.FakeVendorB()
        self.mapping = {'first_method': self.a,
                        'second_method': self.b}
        self.vendor = utils.MixinVendorInterface(self.mapping)
        self.console = fake.FakeConsole()
        self.management = fake.FakeManagement()


class FakeIPMIToolDriver(base.BaseDriver):
    """Example implementation of a Driver."""

    def __init__(self):
        self.power = ipmitool.IPMIPower()
        self.console = ipmitool.IPMIShellinaboxConsole()
        self.deploy = fake.FakeDeploy()
        self.vendor = ipmitool.VendorPassthru()
        self.management = ipmitool.IPMIManagement()


class FakePXEDriver(base.BaseDriver):
    """Example implementation of a Driver."""

    def __init__(self):
        self.power = fake.FakePower()
        self.deploy = pxe.PXEDeploy()
        self.vendor = pxe.VendorPassthru()


class FakeSSHDriver(base.BaseDriver):
    """Example implementation of a Driver."""

    def __init__(self):
        self.power = ssh.SSHPower()
        self.deploy = fake.FakeDeploy()
        self.management = ssh.SSHManagement()


class FakeIPMINativeDriver(base.BaseDriver):
    """Example implementation of a Driver."""

    def __init__(self):
        self.power = ipminative.NativeIPMIPower()
        self.deploy = fake.FakeDeploy()
        self.management = ipminative.NativeIPMIManagement()


class FakeSeaMicroDriver(base.BaseDriver):
    """Fake SeaMicro driver."""

    def __init__(self):
        if not importutils.try_import('seamicroclient'):
            raise exception.DriverLoadError(
                    driver=self.__class__.__name__,
                    reason="Unable to import seamicroclient library")
        self.power = seamicro.Power()
        self.deploy = fake.FakeDeploy()
        self.management = seamicro.Management()
        self.vendor = seamicro.VendorPassthru()


class FakeAgentDriver(base.BaseDriver):
    """Example implementation of an AgentDriver."""

    def __init__(self):
        self.power = fake.FakePower()
        self.deploy = agent.AgentDeploy()
        self.vendor = agent.AgentVendorInterface()


class FakeIBootDriver(base.BaseDriver):
    """Example implementation of a Driver."""

    def __init__(self):
        self.power = iboot.IBootPower()
        self.deploy = fake.FakeDeploy()
