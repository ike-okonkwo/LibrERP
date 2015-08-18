# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (c) 2013-2014 Didotech srl (info at didotech.com)
#                          All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################

from openerp.osv import orm, fields


class stock_picking(orm.Model):
    _inherit = "stock.picking"

    def action_invoice_create(self, cr, uid, ids, journal_id=False,
                            group=False, type='out_invoice', context=None):
        invoice_dict = super(stock_picking, self).action_invoice_create(cr, uid,
                            ids, journal_id, group, type, context=context)
        processed_invoice = []
        for picking_key in invoice_dict:
            if invoice_dict[picking_key] in processed_invoice:
                continue
            processed_invoice.append(invoice_dict[picking_key])
            invoice = self.pool['account.invoice'].browse(cr, uid, invoice_dict[picking_key], context=context)
            if not invoice.company_id.is_group_invoice_line:
                continue

            for line in invoice.invoice_line:
                if line.move_line_id and line.move_line_id.sale_line_id and line.move_line_id.sale_line_id.mrp_bom:

                    qty_delivery = 0
                    for bom_line in line.move_line_id.sale_line_id.mrp_bom:
                        qty_delivery += bom_line.product_uom_qty

                    new_line_vals = {
                        'price_unit': line.move_line_id.sale_line_id.price_unit,
                        'discount': line.move_line_id.sale_line_id.discount,
                        'quantity': qty_delivery / line.quantity,
                    }
                    self.pool['account.invoice.line'].write(cr, uid, line.id, new_line_vals, context=context)
            invoice.button_reset_taxes()
        return invoice_dict


class StockMove(orm.Model):
    _inherit = 'stock.move'

    def _action_explode(self, cr, uid, move, context=None):
        """ Explodes pickings.
        @param move: Stock moves
        @return: True
        """

        if move.picking_id.type == 'in':
            location_dest_id = move.picking_id.partner_id.property_stock_customer.id
        elif move.picking_id.type == 'out':
            location_dest_id = move.picking_id.partner_id.property_stock_customer.id
        move_obj = self.pool['stock.move']
        processed_ids = [move.id]
        if move.sale_line_id and move.sale_line_id.with_bom:
            factor = move.product_qty
            state = 'confirmed'
            if move.state == 'assigned':
                state = 'assigned'
            for line in move.sale_line_id.mrp_bom:
                if line.product_id.type != 'service':
                    valdef = {
                        'picking_id': move.picking_id.id,
                        'product_id': line.product_id.id,
                        'product_uom': line.product_uom.id,
                        'product_qty': line.product_uom_qty * factor,
                        'product_uos': line.product_uom.id,
                        'product_uos_qty': line.product_uom_qty * factor,
                        'move_dest_id': move.id,
                        'state': state,
                        'name': line.product_id.name,
                        'price_unit': line.price_unit,
                        'sell_price': 0,
                        'note': line.name,
                        'move_history_ids': [(6, 0, [move.id])],
                        'move_history_ids2': [(6, 0, [])],
                        'procurements': [],
                        'location_dest_id': location_dest_id,
                    }
                    mid = move_obj.copy(cr, uid, move.id, default=valdef)
                    processed_ids.append(mid)
                move_obj.write(cr, uid, [move.id], {
                    'location_dest_id': move.location_id.id,  # dummy move for the kit
                    'auto_validate': True,
                    'picking_id': False,
                    'state': 'confirmed'
                })

        return processed_ids