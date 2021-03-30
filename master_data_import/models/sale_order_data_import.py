# -*- coding: utf-8 -*-

import logging
import datetime
import xmlrpc.client
from odoo import fields, models, _
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class SaleOrderDataImport(models.Model):
    _name = 'so.data.import'
    _inherit = ['mail.thread']
    _description = 'Sale Order Data Import'

    sequence = fields.Integer(index=True, help="Gives the sequence order when displaying a list of Product Data Import.", default=1)
    name = fields.Char(string='Name', help="Set the Name of the Model for Import", required=True)
    master_data_connection = fields.Many2one('master.data.connection', string="Master Data Connection")
    connection_test = fields.Boolean(string='Connection')
    model_id = fields.Many2one('ir.model', string="Model", help="Choose the Model For Import Data.")
    source_dest_ids = fields.One2many('source.destination.object', 'so_data_import_id', string="Source Destination")
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
        ir_model = self.model_id.model
        dest_model_create = self.env[ir_model]
        is_message_post = self.model_id.field_id.filtered(lambda x: x.name == 'message_ids')
        if not self.model_id.field_id.filtered(lambda x: x.name == 'x_kanak_sync_id'):
            self.model_id.field_id = [(0, 0, {'name': 'x_kanak_sync_id', 'field_description': 'Kanak Sync ID', 'ttype': 'integer'})]
            _logger.info("Kanak Sync ID Field Created - %s" % uid)
        if self.is_import_data:
            dest_fields_only = source_dest_ids.filtered(lambda x: x.dest_field_name and x.is_resync_data).mapped('dest_field_name').mapped('name')
            source_model_fields_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[]], {'fields': dest_fields_only})
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    model_write_id = dest_model_create.search([('x_kanak_sync_id', '=', source_model_fields_data['x_kanak_sync_id'])], limit=1)
                    dest_model_dict = self.prepare_dictionary_for_data(models, dest_model_create, database, uid, password, source_model_fields_data)
                    model_write_id.write(dest_model_dict)
                    if is_message_post and model_write_id:
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
                    dest_model_dict = self.prepare_dictionary_for_data(models, dest_model_create, database, uid, password, source_model_fields_data)
                    if dest_model_dict:
                        exist_record = dest_model_create.search([('x_kanak_sync_id', '=', source_model_fields_data['x_kanak_sync_id'])], limit=1)
                        if not exist_record:
                            create_model_id = dest_model_create.create(dest_model_dict)
                            self.is_import_data = True
                            if is_message_post and create_model_id:
                                msg = "Data <b>Created</b> Successfully. <br/> Record Creation Date: %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                                create_model_id.message_post(body=msg)
                msg = "Data <b>Import</b> Successfully. <br/>Model: %s" % ir_model
                self.message_post(body=msg)
        _logger.info("srs_dest_data_process ---- End")

    def prepare_dictionary_for_data(self, models, dest_model_create, database, uid, password, source_model_fields_data):
        model_write_id = dest_model_create.search([('x_kanak_sync_id', '=', source_model_fields_data['x_kanak_sync_id'])], limit=1)
        dest_model_dict = {}
        for process_key, process_val in source_model_fields_data.items():
            if isinstance(process_val, list):
                if process_key in ['partner_id', 'partner_invoice_id', 'partner_shipping_id']:
                    partner_search = self.env['res.partner'].search([('x_kanak_sync_id', '=', process_val[0])])
                    dest_model_dict[process_key] = partner_search.id
                elif process_key == 'payment_term_id':
                    payment_term = self.env['account.payment.term'].search([('name', '=', process_val[1])])
                    dest_model_dict[process_key] = payment_term.id
                elif process_key == 'order_line':
                    if len(process_val) == 0:
                        continue
                    order_line_dict = False
                    store_line_data = []
                    for line_val in process_val:
                        line_data = models.execute_kw(database, uid, password, 'sale.order.line', 'search_read', [[('id', '=', line_val)]], {'fields': ['id', 'name', 'product_uom_qty', 'customer_lead', 'order_id', 'price_unit', 'product_id', 'tax_id', 'discount']})
                        order_line_dict = self.prepare_order_line_dictionary(line_data, models, database, uid, password, model_write_id)
                        if not order_line_dict[0]:
                            store_line_data.append((0, 0, order_line_dict[1]))
                        dest_model_dict['order_line'] = store_line_data
                else:
                    dest_model_dict[process_key] = process_val[0]
            else:
                dest_model_dict[process_key] = process_val
        return dest_model_dict

    def prepare_order_line_dictionary(self, line_data, models, database, uid, password, model_write_id):
        '''Line dictionary prepare'''
        is_line_exist = False
        taxes_data = []
        order_line_dict = {}
        for line in line_data:
            order = self.env['sale.order'].search([('name', '=', line['order_id'][1])])
            product_template = self.env['product.template'].search([('name', '=', line['product_id'][1].split('(')[0].strip())])
            product_product = product_template.product_variant_ids.filtered(lambda x: x.display_name == line['product_id'][1])
            line_data_exist = model_write_id.order_line.filtered(lambda x: x.product_id.id == product_product.id)
            if len(line['tax_id']) == 1:
                line_taxes = models.execute_kw(database, uid, password, 'account.tax', 'search_read', [[('id', '=', line['tax_id'])]], {'fields': ['id', 'name']})[0]['name']
                taxes = self.env['account.tax'].search([('name', '=', line_taxes)])
                taxes_data.append(taxes.id)
            else:
                for tax_line in line['tax_id']:
                    line_taxes = models.execute_kw(database, uid, password, 'account.tax', 'search_read', [[('id', '=', tax_line)]], {'fields': ['id', 'name']})[0]['name']
                    taxes = self.env['account.tax'].search([('name', '=', line_taxes)])
                    taxes_data.append(taxes.id)
            if line_data_exist:
                is_line_exist = True
            order_line_dict.update({
                'name': line['name'],
                'product_uom_qty': line['product_uom_qty'],
                'customer_lead': line['customer_lead'],
                'order_id': order.id,
                'price_unit': line['price_unit'],
                'product_id': product_product.id,
                'tax_id': [(6, 0, taxes_data)],
                'discount': line['discount']
            })
        return is_line_exist, order_line_dict
