# Copyright 2013 Hewlett-Packard Development Company, L.P.
# All Rights Reserved.
#
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

import array
import hashlib
import struct
import threading

from oslo.config import cfg

from ironic.common import exception
from ironic.db import api as dbapi

hash_opts = [
    cfg.IntOpt('hash_partition_exponent',
               default=16,
               help='Exponent to determine number of hash partitions to use '
                    'when distributing load across conductors. Larger values '
                    'will result in more even distribution of load and less '
                    'load when rebalancing the ring, but more memory usage. '
                    'Number of partitions is (2^hash_partition_exponent).'),
    cfg.IntOpt('hash_distribution_replicas',
               default=1,
               help='[Experimental Feature] '
                    'Number of hosts to map onto each hash partition. '
                    'Setting this to more than one will cause additional '
                    'conductor services to prepare deployment environments '
                    'and potentially allow the Ironic cluster to recover '
                    'more quickly if a conductor instance is terminated.'),
]

CONF = cfg.CONF
CONF.register_opts(hash_opts)


class HashRing(object):

    def __init__(self, hosts, replicas=None):
        """Create a new hash ring across the specified hosts.

        :param hosts: an iterable of hosts which will be mapped.
        :param replicas: number of hosts to map to each hash partition,
                         or len(hosts), which ever is lesser.
                         Default: CONF.hash_distribution_replicas

        """
        if replicas is None:
            replicas = CONF.hash_distribution_replicas

        try:
            self.hosts = list(hosts)
            self.replicas = replicas if replicas <= len(hosts) else len(hosts)
        except TypeError:
            raise exception.Invalid(
                    _("Invalid hosts supplied when building HashRing."))

        self.partition_shift = 32 - CONF.hash_partition_exponent
        self.part2host = array.array('H')
        for p in range(2 ** CONF.hash_partition_exponent):
            self.part2host.append(p % len(hosts))

    def _get_partition(self, data):
        try:
            return (struct.unpack_from('>I', hashlib.md5(data).digest())[0]
                    >> self.partition_shift)
        except TypeError:
            raise exception.Invalid(
                    _("Invalid data supplied to HashRing.get_hosts."))

    def get_hosts(self, data, ignore_hosts=None):
        """Get the list of hosts which the supplied data maps onto.

        :param data: A string identifier to be mapped across the ring.
        :param ignore_hosts: A list of hosts to skip when performing the hash.
                             Useful to temporarily skip down hosts without
                             performing a full rebalance.
                             Default: None.
        :returns: a list of hosts.
                  The length of this list depends on the number of replicas
                  this `HashRing` was created with. It may be less than this
                  if ignore_hosts is not None.
        """
        host_ids = []
        if ignore_hosts is None:
            ignore_host_ids = []
        else:
            ignore_host_ids = [self.hosts.index(h)
                               for h in ignore_hosts if h in self.hosts]

        partition = self._get_partition(data)
        for replica in range(0, self.replicas):
            if len(host_ids + ignore_host_ids) == len(self.hosts):
                # prevent infinite loop
                break
            while self.part2host[partition] in host_ids + ignore_host_ids:
                partition += 1
                if partition >= len(self.part2host):
                    partition = 0
            host_ids.append(self.part2host[partition])
        return [self.hosts[h] for h in host_ids]


class HashRingManager(object):
    def __init__(self):
        self._lock = threading.Lock()
        self.dbapi = dbapi.get_instance()
        self.hash_rings = None

    def _load_hash_rings(self):
        rings = {}
        d2c = self.dbapi.get_active_driver_dict()

        for driver_name, hosts in d2c.iteritems():
            rings[driver_name] = HashRing(hosts)
        return rings

    def _ensure_rings_fresh(self):
        # Hot path, no lock
        # TODO(russell_h): Consider adding time-based invalidation of rings
        if self.hash_rings is not None:
            return

        with self._lock:
            if self.hash_rings is None:
                self.hash_rings = self._load_hash_rings()

    def get_hash_ring(self, driver_name):
        self._ensure_rings_fresh()

        try:
            return self.hash_rings[driver_name]
        except KeyError:
            raise exception.DriverNotFound(_("The driver '%s' is unknown.") %
                                           driver_name)
