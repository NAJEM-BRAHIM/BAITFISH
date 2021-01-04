# -*- coding: utf-8 -*-
###############################################################################
# Author      : Kanak Infosystems LLP. (<http://kanakinfosystems.com/>)
# Copyright(c): 2012-Present Kanak Infosystems LLP.
# All Rights Reserved.
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <http://kanakinfosystems.com/license>
###############################################################################
{
    'name': 'Master Data Import',
    'summary': 'Master Data Import',
    'version': '13.0.0.1.0',
    'category': 'Import',
    'description': """
    Master Data Import
    """,
    'author': 'Kanak Infosystems LLP.',
    'license': 'OPL-1',
    'website': 'https://www.kanakinfosystems.com',
    'data': [
        'security/ir.model.access.csv',
        'views/master_data_connection_views.xml',
        'views/master_data_views.xml',
        'views/partner_data_import_views.xml',
        'views/product_data_import_views.xml',
        'views/sale_order_data_import_views.xml',
        'views/purchase_order_data_import_views.xml',
        'views/stock_picking_data_import_views.xml',
        'views/account_move_data_import_views.xml',
        'wizard/import_view.xml',
    ],
    'depends': ['base', 'mail'],
    'installable': True,
    'application': True,
    'auto_install': False
}
