# -*- coding: utf-8 -*-
# Copyright 2017 Tecnativa - Pedro M. Baeza
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import api, models


class QueueJob(models.Model):
    _inherit = 'queue.job'

    def do_now(self):
        self.sudo().write({'eta': 0})

    def cancel_now(self):
        self.sudo().filtered(
            lambda x: x.state in ['pending', 'enqueued']
        ).unlink()

    def requeue_sudo(self):
        self.sudo().requeue()
