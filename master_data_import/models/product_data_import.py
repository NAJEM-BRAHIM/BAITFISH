# -*- coding: utf-8 -*-

import logging
import xmlrpc.client
from odoo import fields, models, _
from odoo.exceptions import Warning

_logger = logging.getLogger(__name__)


class ProductDataImport(models.Model):
    _name = 'product.data.import'
    _inherit = ['mail.thread']
    _description = 'Product Data Import'

    sequence = fields.Integer(index=True, help="Gives the sequence order when displaying a list of Product Data Import.", default=1)
    name = fields.Char(string='Name', help="Set the Name of the Model for Import", required=True)
    master_data_connection = fields.Many2one('master.data.connection', string="Master Data Connection")
    connection_test = fields.Boolean(string='Connection')
    model_id = fields.Many2one('ir.model', string="Model", help="Choose the Model For Import Data.")
    source_dest_ids = fields.One2many('source.destination.object', 'product_data_import_id', string="Source Destination")
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
            # For get the data on source field
            # dest_fields_only = source_dest_ids.filtered(lambda x: x.source_field_name and x.is_resync_data).mapped('source_field_name')
            # For get the data on destination field
            dest_fields_only = source_dest_ids.filtered(lambda x: x.dest_field_name and x.is_resync_data).mapped('dest_field_name').mapped('name')
            source_model_fields_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[]], {'fields': dest_fields_only})
            count = 0
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    model_write_id = dest_model_create.search([('x_kanak_sync_id', '=', source_model_fields_data['x_kanak_sync_id'])], limit=1)
                    dest_model_dict = {}
                    for process_key, process_val in source_model_fields_data.items():
                        if isinstance(process_val, list):
                            if process_key == 'product_template_image_ids':
                                if not process_val:
                                    continue
                                self.product_exta_product_media(process_key, process_val, model_write_id, models, database, uid, password)
                            if process_key == 'categ_id':
                                if not process_val:
                                    continue
                                self.product_categ_data(process_val, model_write_id, models, database, uid, password)
                            if process_key == 'public_categ_ids':
                                if not process_val:
                                    continue
                                self.product_public_categ_data(process_val, model_write_id, models, database, uid, password)
                            if process_key in ['taxes_id', 'supplier_taxes_id']:
                                if not process_val:
                                    continue
                                self.product_taxes_data(process_val, model_write_id, models, database, uid, password)
                            if process_key == 'attribute_line_ids':
                                if not process_val:
                                    continue
                                self.create_product_variant_data(process_val, model_write_id, models, database, uid, password, source_model_fields_data)
                            if process_key == 'seller_ids' and model_write_id:
                                if not process_val:
                                    continue
                                self.create_product_variant_seller_data(process_val, model_write_id, models, database, uid, password, source_model_fields_data)
                            else:
                                dest_model_dict[process_key] = process_val[0] if process_val != [] else False
                        else:
                            if process_key in ['taxes_id', 'supplier_taxes_id']:
                                if not process_val:
                                    continue
                                self.product_taxes_data(process_val, model_write_id, models, database, uid, password)
                            dest_model_dict[process_key] = process_val
                    if 'taxes_id' in dest_model_dict:
                        del dest_model_dict['taxes_id']
                    if 'product_variant_ids' in dest_model_dict:
                        del dest_model_dict['product_variant_ids']
                    if 'categ_id' in dest_model_dict:
                        del dest_model_dict['categ_id']
                    if 'attribute_line_ids' in dest_model_dict:
                        del dest_model_dict['attribute_line_ids']
                    if 'product_template_image_ids' in dest_model_dict:
                        del dest_model_dict['product_template_image_ids']
                    count += 1
                    model_write_id.write(dest_model_dict)
                    _logger.info("PT count- %s" % count)
                    if is_message_post and model_write_id:
                        msg = "Data <b>Updated</b> Successfully. <br/>Record Updated Date: %s" % (fields.Date.today())
                        model_write_id.message_post(body=msg)
                msg = "Data <b>Updated</b> Successfully. <br/> Model: %s" % ir_model
                self.message_post(body=msg)
        else:
            dest_fields_only = source_dest_ids.filtered(lambda x: x.dest_field_name).mapped('dest_field_name').mapped('name')
            source_model_fields_datas = models.execute_kw(database, uid, password, ir_model, 'search_read', [[]], {'fields': dest_fields_only})
            _logger.info("C : length of the total record - %s" % len(source_model_fields_datas))
            count = 0
            if source_model_fields_datas:
                for source_model_fields_data in source_model_fields_datas:
                    if not ir_model:
                        continue
                    source_model_fields_data['x_kanak_sync_id'] = source_model_fields_data.pop('id')
                    dest_model_dict = {}
                    flag = False
                    for process_key, process_val in source_model_fields_data.items():
                        if isinstance(process_val, list):
                            if ir_model == 'product.attribute.value':
                                attribute_data = self.env['product.attribute'].search([('name', '=', process_val[1])])
                                if attribute_data:
                                    dest_model_dict[process_key] = attribute_data.id
                            elif ir_model == 'product.template' and process_key == 'product_variant_ids':
                                flag = True
                            elif process_key in ['uom_id', 'uom_po_id']:
                                dest_model_search = self.env['uom.uom'].search([('name', '=', process_val[1])])
                                dest_model_dict[process_key] = dest_model_search and dest_model_search.id
                            else:
                                dest_model_dict[process_key] = process_val[0] if process_val != [] else False
                        else:
                            dest_model_dict[process_key] = process_val
                    if flag and process_key == 'product_variant_ids':
                        del dest_model_dict[process_key]
                    create_model_id = dest_model_create.create(dest_model_dict)
                    count = count + 1
                    self.is_import_data = True
                    if is_message_post and create_model_id:
                        msg = "Data <b>Created</b> Successfully. <br/> Record Creation Date: %s" % (fields.Date.today())
                        create_model_id.message_post(body=msg)
                msg = "Data <b>Import</b> Successfully. <br/>Model: %s" % ir_model
                self.message_post(body=msg)
        _logger.info("srs_dest_data_process ---- End")

    def product_exta_product_media(self, process_key, process_val, model_write_id, models, database, uid, password):
        product_image_data = []
        if process_key == 'product_template_image_ids':
            product_image_model = self.env['ir.model'].search([('model', '=', 'product.image')])
            if not product_image_model.field_id.filtered(lambda x: x.name == 'x_kanak_sync_id'):
                product_image_model.field_id = [(0, 0, {'name': 'x_kanak_sync_id', 'field_description': 'Kanak Sync ID', 'ttype': 'integer'})]
                _logger.info("Product Image Kanak Sync ID Field Created - %s" % uid)
        product_images = models.execute_kw(database, uid, password, 'product.image', 'search_read', [[('id', '=', process_val)]], {'fields': []})
        for product_image_vals in product_images:
            vals = (0, 0, {
                            'x_kanak_sync_id': product_image_vals['id'],
                            'name': product_image_vals['name'],
                            'sequence': product_image_vals['sequence'],
                            'image_1920': product_image_vals['image_1920'],
                            'video_url': product_image_vals['video_url'],
                            'embed_code': product_image_vals['embed_code']
                        })
            product_image_data.append(vals)
        model_write_id.product_template_image_ids = product_image_data

    def product_categ_data(self, process_val, model_write_id, models, database, uid, password):
        dest_model_categ_id = self.env['product.category'].search([('x_kanak_sync_id', '=', process_val[0])])
        if dest_model_categ_id:
            model_write_id.write({'categ_id': dest_model_categ_id and dest_model_categ_id.id})

    def product_public_categ_data(self, process_val, model_write_id, models, database, uid, password):
        dest_model_categ_id = self.env['product.public.category'].search([('x_kanak_sync_id', '=', process_val[0])])
        if dest_model_categ_id:
            model_write_id.write({'public_categ_ids': [(6, 0, [dest_model_categ_id.id])]})

    def product_taxes_data(self, process_val, model_write_id, models, database, uid, password):
        dest_model_categ_id = self.env['account.tax'].search([('x_kanak_sync_id', 'in', process_val)])
        if dest_model_categ_id:
            model_write_id.write({'taxes_id': [(6, 0, [dest_model_categ_id.id])]})

    def create_product_variant_data(self, process_val, model_write_id, models, database, uid, password, source_model_fields_data):
        for attr_line in process_val:
            src_attr = models.execute_kw(database, uid, password, 'product.template.attribute.line', 'search_read', [[('product_tmpl_id', '=', source_model_fields_data['x_kanak_sync_id'])]], {'fields': []})
            if not src_attr:
                continue
            for dest_data in src_attr:
                product_attr_values_data = {}
                product_attr_data_list = []
                product_attr_values_data_list = []
                dest_attr_search = self.env['product.attribute'].search([('x_kanak_sync_id', '=', dest_data['attribute_id'][0])])
                product_attr_data_list.append(dest_attr_search.id)
                for dest_attr_value in dest_data['value_ids']:
                    dest_attr_value_search = self.env['product.attribute.value'].search([('x_kanak_sync_id', '=', dest_attr_value)])
                    product_attr_values_data_list.append(dest_attr_value_search.id)
                product_attr_values_data[dest_attr_search.id] = product_attr_values_data_list
                if product_attr_values_data:
                    patl_vals = {}
                    for key, val in product_attr_values_data.items():
                        line_data = model_write_id.attribute_line_ids.filtered(lambda x: x.attribute_id.id == key and x.value_ids.ids == val)
                        if not line_data:
                            patl_vals['attribute_id'] = key
                            patl_vals['value_ids'] = val
                            model_write_id.attribute_line_ids = [(0, 0, patl_vals)]

    def create_product_variant_seller_data(self, attribute_line_ids, model_write_id, models, database, uid, password, source_model_fields_data):
        if len(attribute_line_ids) == 1:
            src_supplier_data = models.execute_kw(database, uid, password, 'product.supplierinfo', 'search_read', [[('product_tmpl_id', '=', source_model_fields_data['x_kanak_sync_id'])]], {'fields': []})
            seller_data_list = []
            product_templ = []
            for src_data in src_supplier_data:
                if src_data['product_tmpl_id'][0] in product_templ:
                    break
                product_templ.append(src_data['product_tmpl_id'][0])
                dest_vendor_search = self.env['res.partner'].search([('display_name', '=', src_data['name'][1])])
                dest_comp_search = self.env['res.company'].search([('name', '=', src_data['company_id'][1])])
                # dest_curr_search = self.env['res.currency'].search([('name', '=', src_data['currency_id'][1])])
                dest_product_tmpl_search = self.env['product.template'].search([('name', '=', src_data['product_tmpl_id'][1])], limit=1)
                dest_product_uom_search = self.env['uom.uom'].search([('name', '=', src_data['product_uom'][1])])
                if not dest_vendor_search:
                    continue
                seller_data = {
                    'name': dest_vendor_search.id,
                    'product_name': src_data['product_name'],
                    'product_code': src_data['product_code'],
                    'sequence': src_data['sequence'],
                    'min_qty': src_data['min_qty'],
                    'price': src_data['price'] if 'price' in src_data else 0.0,
                    'company_id': dest_comp_search.id,
                    # 'currency_id': dest_comp_search.currency_id.id,
                    'date_start': src_data['date_start'] if 'date_start' in src_data else False,
                    'date_end': src_data['date_end'] if 'date_end' in src_data else False,
                    'product_tmpl_id': dest_product_tmpl_search.id,
                    'delay': src_data['delay'],
                    'product_uom': dest_product_uom_search.id,
                    'product_variant_count': src_data['product_variant_count'] if 'product_variant_count' in src_data else 0.0,
                    'display_name': src_data['display_name']
                }
                seller_data_list.append(seller_data)
        else:
            for attribute_line_id in attribute_line_ids:
                src_supplier_data = models.execute_kw(database, uid, password, 'product.supplierinfo', 'search_read', [[('product_tmpl_id', '=', source_model_fields_data['x_kanak_sync_id'])]], {'fields': []})
                seller_data_list = []
                product_templ = []
                for src_data in src_supplier_data:
                    product_templ.append(src_data['product_tmpl_id'][0])
                    dest_vendor_search = self.env['res.partner'].search([('display_name', '=', src_data['name'][1])])
                    dest_comp_search = self.env['res.company'].search([('name', '=', src_data['company_id'][1])])
                    # dest_curr_search = self.env['res.currency'].search([('name', '=', src_data['currency_id'][1])])
                    dest_product_tmpl_search = self.env['product.template'].search([('name', '=', src_data['product_tmpl_id'][1])], limit=1)
                    dest_product_uom_search = self.env['uom.uom'].search([('name', '=', src_data['product_uom'][1])])
                    if not dest_vendor_search:
                        continue
                    seller_data = {
                        'name': dest_vendor_search.id,
                        'product_name': src_data['product_name'],
                        'product_code': src_data['product_code'],
                        'sequence': src_data['sequence'],
                        'min_qty': src_data['min_qty'],
                        'price': src_data['price'] if 'price' in src_data else 0.0,
                        'company_id': dest_comp_search.id,
                        # 'currency_id': dest_comp_search.currency_id.id,
                        'date_start': src_data['date_start'] if 'date_start' in src_data else False,
                        'date_end': src_data['date_end'] if 'date_end' in src_data else False,
                        'product_tmpl_id': dest_product_tmpl_search.id,
                        'delay': src_data['delay'],
                        'product_uom': dest_product_uom_search.id,
                        'product_variant_count': src_data['product_variant_count'] if 'product_variant_count' in src_data else 0.0,
                        'display_name': src_data['display_name']
                    }
                    seller_data_list.append(seller_data)
        for seller_val in seller_data_list:
            model_write_id.seller_ids = [(0, 0, seller_val)]
