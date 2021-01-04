# -*- coding: utf-8 -*-

import re
import datetime
import logging
import xmlrpc.client
from odoo import fields, models, _
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class PartnerDataImport(models.Model):
    _name = 'partner.data.import'
    _inherit = ['mail.thread']
    _description = 'Partner Data Import'

    name = fields.Char(string='Name', help="Set the Name of the Model for Import", required=True)
    master_data_connection = fields.Many2one('master.data.connection', string="Master Data Connection")
    connection_test = fields.Boolean(string='Connection')
    model_id = fields.Many2one('ir.model', string="Model", help="Choose the Model For Import Data.")
    source_dest_ids = fields.One2many('source.destination.object', 'partner_data_import_id', string="Source Destination")
    is_import_data = fields.Boolean(default=False)

    def _split_number_str(self, account_val):
        match = re.match(r"([0-9]+)([a-z]+)", account_val.replace(' ', ''), re.I)
        if match:
            items = match.groups()
            return items

    def fetch_fileds(self):
        try:
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.master_data_connection.url))
            uid = common.authenticate(self.master_data_connection.database, self.master_data_connection.username, self.master_data_connection.password, {})
            models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.master_data_connection.url))
            _logger.info("Connection Uid - %s" % uid)
            if not uid:
                self.connection_test = False
            else:
                self.connection_test = True
                final_field = self.src_dest_object_fields(models=models, database=self.master_data_connection.database, uid=uid, password=self.master_data_connection.password)
                if final_field:
                    self.create_src_dest_fields(final_field=final_field)
        except Exception as err:
            self.connection_test = False
            raise Warning(_(err))

    def create_src_dest_fields(self, final_field):
        _logger.info("create_src_dest_fields ---- Start")
        for field_line in final_field:
            if self.source_dest_ids.filtered(lambda x: x.source_field_name == field_line or x.dest_field_name == field_line):
                _logger.info("Already Created Src/Dest Fields")
                continue
            obj_fields = self.model_id.field_id.filtered(lambda x: x.name == field_line)
            self.source_dest_ids = [(0, 0, {'source_field_name': field_line, 'dest_field_name': obj_fields.id})]
        _logger.info("create_src_dest_fields ---- End")

    def src_dest_object_fields(self, models, database, uid, password):
        _logger.info("src_dest_object_fields ---- Start")
        sorce_required_fields = []
        dest_model = self.model_id
        dest_fields = self.model_id.field_id.filtered(lambda x: x.required).mapped('name')
        source_model = models.execute_kw(database, uid, password, 'ir.model', 'search_read', [[('model', '=', dest_model.model)]], {'fields': ['field_id']})
        if source_model:
            source_model_fields = models.execute_kw(database, uid, password, 'ir.model.fields', 'search_read', [[('id', '=', source_model[0]['field_id']), ('required', '=', True)]], {'fields': ['name']})
            for source_required_field in source_model_fields:
                sorce_required_fields.append(source_required_field.get('name'))
            not_src_in_dest = set(dest_fields) - set(sorce_required_fields)
            in_src_in_dest = set(dest_fields).intersection(sorce_required_fields)
            in_src_in_dest.update(not_src_in_dest)
            _logger.info("Final Fields - %s" % in_src_in_dest)
            return in_src_in_dest
        _logger.info("src_dest_object_fields ---- End")
        return False

    def import_processing(self):
        try:
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.master_data_connection.url))
            uid = common.authenticate(self.master_data_connection.database, self.master_data_connection.username, self.master_data_connection.password, {})
            models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.master_data_connection.url))
            _logger.info("Connection Uid - %s" % uid)
            if not uid:
                self.connection_test = False
            else:
                self.connection_test = True
                self.srs_dest_data_process(models=models, database=self.master_data_connection.database, uid=uid, password=self.master_data_connection.password, source_dest_ids=self.source_dest_ids)
        except Exception as err:
            self.connection_test = False
            raise Warning(_(err))

    def srs_dest_data_process(self, models, database, uid, password, source_dest_ids):
        _logger.info("srs_dest_data_process ---- Start")
        # logf = open("/home/kanak/Downloads/download.text", "w")
        ir_model = self.model_id.model
        dest_model_create = self.env[ir_model]
        is_message_post = self.model_id.field_id.filtered(lambda x: x.name == 'message_ids')
        if not self.model_id.field_id.filtered(lambda x: x.name == 'x_kanak_sync_id'):
            self.model_id.field_id = [(0, 0, {'name': 'x_kanak_sync_id', 'field_description': 'Kanak Sync ID', 'ttype': 'integer'})]
            _logger.info("Kanak Sync ID Field Created - %s" % uid)
        if self.is_import_data:
            # For get the data on source field
            # dest_fields_only = source_dest_ids.filtered(lambda x: x.source_field_name and x.is_resync_data).mapped('source_field_name')
            # For get the data on destination field
            dest_fields_only = source_dest_ids.filtered(lambda x: x.dest_field_name and x.is_resync_data).mapped('dest_field_name').mapped('name')
            source_model_fields_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[]], {'fields': dest_fields_only})
            _logger.info("W : length of the total record - %s" % len(source_model_fields_datas))
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    model_write_id = dest_model_create.search([('x_kanak_sync_id', '=', source_model_fields_data['x_kanak_sync_id'])], limit=1)
                    dest_model_dict = {}
                    flag = False
                    for process_key, process_val in source_model_fields_data.items():
                        if process_key == 'name':
                            dest_model_parent_id = dest_model_create.search([('name', '=', process_val)])
                        if isinstance(process_val, list):
                            if process_key == 'child_ids':
                                if len(process_val) == 0:
                                    continue
                                for child_val in process_val:
                                    child_data = models.execute_kw(database, uid, password, ir_model, 'search_read', [[('id', '=', child_val)]], {'fields': ['id', 'name']})
                                    if child_data:
                                        dest_model_search = dest_model_create.search([('name', '=', child_data[0]['name'])])
                                        dest_model_search.write({'parent_id': dest_model_parent_id})
                                        if dest_model_search:
                                            flag = True
                            else:
                                dest_model_dict[process_key] = process_val[0] if process_val != [] else False
                        else:
                            if process_key == 'image':
                                process_key = 'image_1920'
                            dest_model_dict[process_key] = process_val
                    if flag and process_key == 'child_ids':
                        del dest_model_dict[process_key]
                    model_write_id.write(dest_model_dict)
                    if is_message_post and model_write_id:
                        msg = "Data <b>Updated</b> Successfully. <br/>Record Updated Date: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        model_write_id.message_post(body=msg)
                msg = "Data <b>Updated</b> Successfully. <br/> Model: %s" % ir_model
                self.message_post(body=msg)
        else:
            dest_fields_only = source_dest_ids.filtered(lambda x: x.dest_field_name).mapped('dest_field_name').mapped('name')
            source_model_fields_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[]], {'fields': dest_fields_only})
            _logger.info("C : length of the total record - %s" % len(source_model_fields_datas))
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    dest_model_dict = {}
                    # domain = False
                    for process_key, process_val in source_model_fields_data.items():
                        # if 'code' in source_model_fields_data:
                        #     domain = [('name', '=', source_model_fields_data['code'])]
                        # elif 'name' in source_model_fields_data:
                        #     domain = [('name', '=', source_model_fields_data['name'])]
                        # if domain:
                        #     dest_data_search = self.env[ir_model].search(domain)
                        #     if dest_data_search:
                        #         break
                        if isinstance(process_val, list):
                            search_field_model = self.source_dest_ids.filtered(lambda x: x.dest_field_name.name == process_key).mapped('dest_field_name').relation
                            if search_field_model == 'account.account':
                                account_value = self._split_number_str(process_val[1])
                                if account_value:
                                    search_field_model_data = self.env[search_field_model].search([('code', '=', account_value[0])])
                                    dest_model_dict[process_key] = search_field_model_data.id
                            dest_model_dict[process_key] = process_val[0] if process_val != [] else False
                        else:
                            dest_model_dict[process_key] = process_val
                    # logf.write("Import {0}: \n {1}\n\n".format(str(source_model_fields_data), str(dest_model_dict)))
                    create_model_id = dest_model_create.create(dest_model_dict)
                    self.is_import_data = True
                    if is_message_post and create_model_id:
                        msg = "Data <b>Created</b> Successfully. <br/> Record Creation Date: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        create_model_id.message_post(body=msg)
                msg = "Data <b>Import</b> Successfully. <br/>Model: %s" % ir_model
                self.message_post(body=msg)
        _logger.info("srs_dest_data_process ---- End")
