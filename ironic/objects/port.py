# coding=utf-8
#
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

from ironic.common import exception
from ironic.common import utils
from ironic.db import api as dbapi
from ironic.objects import base
from ironic.objects import utils as obj_utils


class Port(base.IronicObject):
    # Version 1.0: Initial version
    # Version 1.1: Add get() and get_by_id() and get_by_address() and
    #              make get_by_uuid() only work with a uuid
    VERSION = '1.1'

    dbapi = dbapi.get_instance()

    fields = {
        'id': int,
        'uuid': obj_utils.str_or_none,
        'node_id': obj_utils.int_or_none,
        'address': obj_utils.str_or_none,
        'extra': obj_utils.dict_or_none,
    }

    @staticmethod
    def _from_db_object(port, db_port):
        """Converts a database entity to a formal object."""
        for field in port.fields:
            port[field] = db_port[field]

        port.obj_reset_changes()
        return port

    @base.remotable_classmethod
    def get(cls, context, port_id):
        """Find a port based on its id or uuid and return a Port object.

        :param port_id: the id *or* uuid of a port.
        :returns: a :class:`Port` object.
        """
        if utils.is_int_like(port_id):
            return cls.get_by_id(context, port_id)
        elif utils.is_uuid_like(port_id):
            return cls.get_by_uuid(context, port_id)
        elif utils.is_valid_mac(port_id):
            return cls.get_by_address(context, port_id)
        else:
            raise exception.InvalidIdentity(identity=port_id)

    @base.remotable_classmethod
    def get_by_id(cls, context, port_id):
        """Find a port based on its integer id and return a Port object.

        :param port_id: the id of a port.
        :returns: a :class:`Port` object.
        """
        db_port = cls.dbapi.get_port_by_id(port_id)
        port = Port._from_db_object(cls(), db_port)
        # FIXME(comstud): Setting of the context should be moved to
        # _from_db_object().
        port._context = context
        return port

    @base.remotable_classmethod
    def get_by_uuid(cls, context, uuid):
        """Find a port based on uuid and return a :class:`Port` object.

        :param uuid: the uuid of a port.
        :param context: Security context
        :returns: a :class:`Port` object.
        """
        db_port = cls.dbapi.get_port_by_uuid(uuid)
        port = Port._from_db_object(cls(), db_port)
        # FIXME(comstud): Setting of the context should be moved to
        # _from_db_object().
        port._context = context
        return port

    @base.remotable_classmethod
    def get_by_address(cls, context, address):
        """Find a port based on address and return a :class:`Port` object.

        :param address: the address of a port.
        :param context: Security context
        :returns: a :class:`Port` object.
        """
        db_port = cls.dbapi.get_port_by_address(address)
        port = Port._from_db_object(cls(), db_port)
        # FIXME(comstud): Setting of the context should be moved to
        # _from_db_object().
        port._context = context
        return port

    @base.remotable
    def save(self, context=None):
        """Save updates to this Port.

        Updates will be made column by column based on the result
        of self.what_changed().

        :param context: Security context. NOTE: This is only used
                        internally by the indirection_api.
        """
        updates = self.obj_get_changes()
        self.dbapi.update_port(self.uuid, updates)

        self.obj_reset_changes()

    @base.remotable
    def refresh(self, context=None):
        """Loads updates for this Port.

        Loads a port with the same uuid from the database and
        checks for updated attributes. Updates are applied from
        the loaded port column by column, if there are any updates.

        :param context: Security context. NOTE: This is only used
                        internally by the indirection_api.
        """
        current = self.__class__.get_by_uuid(context, uuid=self.uuid)
        for field in self.fields:
            if (hasattr(self, base.get_attrname(field)) and
                    self[field] != current[field]):
                self[field] = current[field]
