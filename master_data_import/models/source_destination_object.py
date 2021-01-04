# -*- coding: utf-8 -*-

import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class SourceDestinationObject(models.Model):
    _name = 'source.destination.object'
    _description = "Source Destination Fields Obtain"

    source_field_name = fields.Char(string="Source Fields")
    dest_field_name = fields.Many2one('ir.model.fields', string="Destination Fields")
    master_data_id = fields.Many2one('master.data', string="Master Data")
    is_resync_data = fields.Boolean(string="Resync", default=True)
    partner_data_import_id = fields.Many2one('partner.data.import', string="Partner Data Import")
    product_data_import_id = fields.Many2one('product.data.import', string="Product Data Import")
    so_data_import_id = fields.Many2one('so.data.import', string="SO Data Import")
    po_data_import_id = fields.Many2one('po.data.import', string="PO Data Import")
    sp_data_import_id = fields.Many2one('sp.data.import', string="Stock Picking Data Import")
    am_data_import_id = fields.Many2one('am.data.import', string="Account Move Data Import")
