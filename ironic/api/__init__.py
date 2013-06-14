# vim: tabstop=4 shiftwidth=4 softtabstop=4

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

from oslo.config import cfg


API_SERVICE_OPTS = [
        cfg.StrOpt('ironic_api_bind_ip',
            default='0.0.0.0',
            help='IP for the Ironic API server to bind to',
            ),
        cfg.IntOpt('ironic_api_port',
            default=6385,
            help='The port for the Ironic API server',
            ),
        ]

CONF = cfg.CONF
CONF.register_opts(API_SERVICE_OPTS)
