# -*- coding: utf-8 -*-

import logging
import datetime
import xmlrpc.client
from odoo import fields, models, _
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class MasterData(models.Model):
    _name = 'master.data'
    _inherit = ['mail.thread']
    _description = 'Master Data Import'

    name = fields.Char(string='Name', help="Set the Name of the Model for Import", required=True)
    master_data_connection = fields.Many2one('master.data.connection', string="Master Data Connection")
    connection_test = fields.Boolean(string='Connection')
    model_id = fields.Many2one('ir.model', string="Model", help="Choose the Model For Import Data.")
    source_dest_ids = fields.One2many('source.destination.object', 'master_data_id', string="Source Destination")
    is_import_data = fields.Boolean(default=False)

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
            if self.source_dest_ids.filtered(lambda x: x.source_field_name == field_line):
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
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    model_write_id = dest_model_create.search([('x_kanak_sync_id', '=', source_model_fields_data['x_kanak_sync_id'])], limit=1)
                    dest_model_dict = {}
                    for process_key, process_val in source_model_fields_data.items():
                        if isinstance(process_val, list):
                            if ir_model == 'product.pricelist' and process_key == 'item_ids':
                                if not process_val:
                                    continue
                                self.product_pricelist(process_val, model_write_id, models, database, uid, password)
                            if ir_model == 'product.public.category' and process_key == 'parent_id':
                                child_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[('parent_id', '=', process_val[0])]], {'fields': ['id', 'name', 'parent_id']})
                                set_parent_id = []
                                for child_data in child_datas:
                                    if set_parent_id == []:
                                        set_parent_id.append(child_data['parent_id'][0])
                                    to_be_set_parent_id = dest_model_create.search([('x_kanak_sync_id', '=', child_data['id'])])
                                    parent_set_id = dest_model_create.search([('x_kanak_sync_id', '=', set_parent_id[0])])
                                    to_be_set_parent_id.write({'parent_id': parent_set_id and parent_set_id.id})
                            elif process_key == 'parent_id':
                                child_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[('parent_id', '=', process_val[0])]], {'fields': ['id', 'name', 'parent_id']})
                                for child_data in child_datas:
                                    if not child_data['parent_id']:
                                        continue
                                    dest_model_search = dest_model_create.search([('name', '=', child_data['name'])])
                                    dest_model_parent_id = dest_model_create.search([('x_kanak_sync_id', '=', child_data['parent_id'][0])])
                                    if not dest_model_parent_id:
                                        dest_model_parent_id = dest_model_create.search([('name', '=', child_data['parent_id'][1].split('/')[-1].strip())])
                                    dest_model_search.write({'parent_id': dest_model_parent_id and dest_model_parent_id.id})
                            else:
                                dest_model_dict[process_key] = process_val[0] if process_val != [] else False
                        else:
                            if process_key == 'password_crypt':
                                process_key = 'password'
                            dest_model_dict[process_key] = process_val
                    if 'groups_id' in dest_model_dict:
                        del dest_model_dict['groups_id']
                    if 'item_ids' in dest_model_dict:
                        del dest_model_dict['item_ids']
                    model_write_id.write(dest_model_dict)
                    if is_message_post and model_write_id and not ir_model == 'res.users':
                        msg = "Data <b>Updated</b> Successfully. <br/>Record Updated Date: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                        model_write_id.message_post(body=msg)
                msg = "Data <b>Updated</b> Successfully. <br/> Model: %s" % ir_model
                self.message_post(body=msg)
        else:
            dest_fields_only = source_dest_ids.filtered(lambda x: x.dest_field_name).mapped('dest_field_name').mapped('name')
            source_model_fields_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[]], {'fields': dest_fields_only})
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    dest_model_dict = {}
                    # domain = False
                    for process_key, process_val in source_model_fields_data.items():
                        if ir_model == 'product.category':
                            if 'code' in source_model_fields_data:
                                domain = [('name', '=', source_model_fields_data['code'])]
                            elif 'name' in source_model_fields_data:
                                domain = [('name', '=', source_model_fields_data['name'])]
                            if domain:
                                dest_data_search = self.env[ir_model].search(domain)
                                if dest_data_search:
                                    break
                        if ir_model == 'uom.uom':
                            if 'name' in source_model_fields_data:
                                domain = [('name', '=', source_model_fields_data['name'])]
                            if domain:
                                dest_data_search = self.env[ir_model].search(domain)
                                if dest_data_search:
                                    break
                        if isinstance(process_val, list):
                            if process_key == 'partner_id' and ir_model == 'res.users':
                                existing_partner = self.env['res.partner'].search([('x_kanak_sync_id', '=', process_val[0]), ('name', '=', process_val[1])])
                                dest_model_dict[process_key] = existing_partner and existing_partner.id
                            elif process_key == 'company_id':
                                dest_model_dict[process_key] = self.env['res.company'].search([], limit=1).id
                            else:
                                dest_model_dict[process_key] = process_val[0]
                        else:
                            dest_model_dict[process_key] = process_val
                        # dest_model_dict[process_key] = process_val[0] if isinstance(process_val, list) else process_val
                    if dest_model_dict:
                        # if ir_model == 'res.users':
                        #     dest_model_dict['notification_type'] = 'email'
                        #     dest_model_dict['odoobot_state'] = 'onboarding_emoji'
                        # if 'type_tax_use' in dest_model_dict and dest_model_dict['type_tax_use'] == 'all':
                        #     dest_model_dict['type_tax_use'] = 'none'
                        # if 'partner_id' in dest_model_dict and isinstance(dest_model_dict['partner_id'], int):
                        create_model_id = dest_model_create.create(dest_model_dict)
                        self.is_import_data = True
                        if self.is_import_data and is_message_post and create_model_id and not ir_model == 'res.users':
                            msg = "Data <b>Created</b> Successfully. <br/> Record Creation Date: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            create_model_id.message_post(body=msg)
                msg = "Data <b>Import</b> Successfully. <br/>Model: %s" % ir_model
                self.message_post(body=msg)
        _logger.info("srs_dest_data_process ---- End")

    def product_pricelist(self, item_line, model_write_id, models, database, uid, password):
        item_data_list = []
        count = 0
        for item in item_line:
            src_item_data = models.execute_kw(database, uid, password, 'product.pricelist.item', 'search_read', [[('id', '=', item)]], {'fields': []})
            for item_data in src_item_data:
                dest_product_search = False
                count += 1
                if item_data['product_tmpl_id'] and item_data['product_tmpl_id'][0] != False:
                    dest_product_tmpl_search = self.env['product.template'].search([('x_kanak_sync_id', '=', item_data['product_tmpl_id'][0])], limit=1)
                else:
                    item_data['applied_on'] = '3_global'
                if dest_product_tmpl_search:
                    item_values = {
                         'fixed_price': item_data['fixed_price'] or 0.0,
                         'price_discount': item_data['price_discount'] or 0.0,
                         'price_max_margin': item_data['price_max_margin'] or 0.0,
                         'date_end': item_data['date_end'],
                         'currency_id': item_data['currency_id'][0],
                         'applied_on': item_data['applied_on'],
                         'min_quantity': item_data['min_quantity'],
                         'percent_price': item_data['percent_price'] or 0.0,
                         'date_start': item_data['date_start'] or False,
                         'name': item_data['name'],
                         'product_tmpl_id': dest_product_tmpl_search and dest_product_tmpl_search.id,
                         'price_min_margin': item_data['price_min_margin'] or 0.0,
                         'price': item_data['price'],
                         'compute_price': item_data['compute_price'],
                         'base': item_data['base'],
                         'display_name': item_data['display_name'],
                         'categ_id': False,
                         'price_surcharge': 0.0,
                         'price_round': 0.0,
                         'product_id': dest_product_search and dest_product_search.id,
                         'base_pricelist_id': item_data['base_pricelist_id'] or False
                     }
                    item_data_list.append(item_values)
        for item_val in item_data_list:
            model_write_id.item_ids = [(0, 0, item_val)]
