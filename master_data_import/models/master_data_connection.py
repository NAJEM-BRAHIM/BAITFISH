# -*- coding: utf-8 -*-

import logging
import xmlrpc.client
from odoo import fields, models, _
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class MasterDataConnection(models.Model):
    _name = 'master.data.connection'
    _description = 'Master Data Connection'

    name = fields.Char(string='Server Name', required=True, help="Name of the Source Server")
    url = fields.Char(string='URL Address', required=True, help="Source Server URL with http or https")
    username = fields.Char(required=True, help="Source Server Username")
    password = fields.Char(required=True, help="Source Server Password")
    database = fields.Char(required=True, help="Source Server Database")
    connection_test = fields.Boolean(string='Connection')

    def test_connection(self):
        try:
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
            uid = common.authenticate(self.database, self.username, self.password, {})
            models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
            if not uid:
                self.connection_test = False
                _logger.info("Test Connection Failed.!")
            else:
                self.connection_test = True
                _logger.info("Test Connection Succeed.!")
        except Exception as err:
            self.connection_test = False
            _logger.info("Test Connection Failed.!")
            raise Warning(_(err))
