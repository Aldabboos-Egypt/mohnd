# Fixed discount amount on Sale Order Lines and Invoice Lines
# Copyright (c) 2021 Sayed Hassan (sh-odoo@hotmail.com)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl)

from odoo import api, fields, models



class UomUom(models.Model):
    _inherit = 'uom.uom'

    qty_type= fields.Selection(
    string='UOM Qty Type',
    selection=[('packet', 'Packet'),
               ('carton', 'Carton'), ],
     )

class AccountMove(models.Model):
    _inherit = 'account.move'

    driver_id = fields.Many2one(comodel_name='res.partner', string='Driver')
    # narration = fields.Text(string='ملاحظة دفع الفاتورة')
    invoice_notes = fields.Char(string='Payment Notes')
    general_notes = fields.Char(string='Notes')
    total_product = fields.Integer(string='Total Product:',compute='_total_product',help="total Products")
    total_quantity = fields.Integer(string='Total Quantity:',compute='_total_quantity',help="total Quantity")
    total_quantity_packet = fields.Integer(string='Total Quantity Packet:',compute='_total_quantity',help="total Quantity Packet")
    total_quantity_carton = fields.Integer(string='Total Quantity Carton:',compute='_total_quantity',help="total Quantity Carton")

    total_before_discount = fields.Monetary(" Total Before Discount", compute='total_discount')
    discount_total = fields.Monetary("Discount Total", compute='total_discount')
    discount_total_line = fields.Monetary("Discount Total Line ", compute='total_discount')
    total_with_line_discount = fields.Monetary(" Total With Line Discount ", compute='total_discount')
    all_discounts = fields.Monetary("Discount ", compute='total_discount')
    partner_balance_before = fields.Monetary("  Balance Before", compute='total_discount')
    partner_balance_after = fields.Monetary("  Balance After", compute='total_discount')

    # Count the total discount
    @api.depends('invoice_line_ids.quantity', 'invoice_line_ids.price_unit', 'invoice_line_ids.discount')
    def total_discount(self):
        for invoice in self:
            final_discount_amount = 0
            final_discount_amount_line = 0
            if invoice:
                for line in invoice.invoice_line_ids:
                    if line:
                        total_price = line.quantity * line.price_unit
                        if total_price:
                            discount_amount = total_price - line.price_subtotal
                            if discount_amount:
                                final_discount_amount = final_discount_amount + discount_amount
                            if line.price_unit < 0 and line.product_id.is_discount:
                                final_discount_amount_line = final_discount_amount_line + line.price_subtotal

                balance_after = 0.0
                if invoice.partner_id.balance:
                    balance_after = invoice.partner_id.balance
                    balance_before = invoice.partner_id.balance - invoice.amount_total
                else:
                    balance_before = invoice.amount_total

                invoice.update({
                    'discount_total': final_discount_amount,
                    'partner_balance_before': balance_before,
                    'partner_balance_after': balance_after,
                    'discount_total_line': final_discount_amount_line,
                    'total_with_line_discount': invoice.amount_total - final_discount_amount_line,
                    'all_discounts': abs(final_discount_amount_line) + abs(final_discount_amount),
                    'total_before_discount': invoice.amount_total + abs(final_discount_amount_line) + abs(
                        final_discount_amount),

                })

    def _total_product(self):
        for record in self:
            product_list=[]
            for line in record.invoice_line_ids:
                if line.product_id.is_discount  :
                    continue
                product_list.append(line.product_id)
            record.total_product = len(set(product_list))

    def _total_quantity(self):
        for record in self:
            total_qty = 0
            total_qty_packet = 0
            total_qty_carton = 0
            for line in record.invoice_line_ids:
                if line.product_id.is_discount  :
                    continue
                total_qty = total_qty + line.quantity
                total_qty_packet= total_qty_packet + (line.quantity if line.product_uom_id.qty_type=='packet' else 0)
                total_qty_carton = total_qty_carton + (line.quantity if line.product_uom_id.qty_type == 'carton' else 0)
            record.total_quantity = total_qty
            record.total_quantity_packet = total_qty_packet
            record.total_quantity_carton = total_qty_carton


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    fixed_discount = fields.Float( string="Fixed Discount", digits="Product Price", default=0.000)
    discount = fields.Float(string='Discount (%)', digits='Discount', default=0.0, readonly=False)
    gift = fields.Char(string='Gift', )
    notes = fields.Char(string='Notes', )

    @api.onchange("discount")
    def _onchange_discount(self):
        for line in self:
            if line.discount != 0:
                self.fixed_discount = 0.0
                fixed_discount = (line.price_unit * line.quantity) * (line.discount / 100.0)
                line.update({"fixed_discount": fixed_discount})
            if line.discount == 0:
                fixed_discount = 0.000
                line.update({"fixed_discount": fixed_discount})

    @api.onchange("fixed_discount")
    def _onchange_fixed_discount(self):
        for line in self:
            if line.fixed_discount != 0:
                self.discount = 0.0
                discount = ((self.quantity * self.price_unit) - ((self.quantity * self.price_unit) - self.fixed_discount)) / (
                            self.quantity * self.price_unit) * 100 or 0.0
                line.update({"discount": discount})
            if line.fixed_discount == 0:
                discount = 0.0
                line.update({"discount": discount})


class ProductProduct(models.Model):
    _inherit = "product.product"

    is_discount = fields.Boolean(string="IS Discount " )




class ResCompany(models.Model):
    _inherit = 'res.company'
    qrcode=  fields.Binary(string="",  )


class ResPartner(models.Model):
    _inherit = 'res.partner'
    balance = fields.Float(string='Balance', compute="compute_balance")

    related_user_id = fields.Many2one('res.users',
                                      string='Related User', readonly=True,
                                      help='This field contains the related '
                                           'user of the partner if there is any.')
    is_have_user = fields.Boolean(string='Have User',
                                  help='This field helps to check if there is '
                                       'any user related to the partner.')

    @api.model
    def get_views(self, views, options=None):
        """ Super get_views function to write into related user when opening
        the view.
            :param views: list of [view_id, view_type]
            :param dict options: a dict optional boolean flags, set to enable:
            :return: dictionary with fields_views, fields and optionally filters
        """
        res = super().get_views(views, options)
        res_users = self.env['res.users'].search([])
        for users in res_users:
            res_partner = self.search([])
            for partner in res_partner:
                if users.partner_id.id == partner.id:
                    partner.write({
                        'related_user_id': users,
                        'is_have_user': True
                    })
        return res
    def compute_balance(self):
        for rec in self:
            rec.balance = rec.credit - rec.debit