from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
from odoo.fields import Command



class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    gift = fields.Char(string='Gift', )
    notes = fields.Char(string='Notes', )

    fixed_discount = fields.Float(string="Fixed Discount ", digits="Product Price")

    @api.onchange("discount")
    def _onchange_discount(self):
        for line in self:
            if line.discount != 0:
                self.fixed_discount = 0.0
                fixed_discount = (line.price_unit * line.product_uom_qty) * (line.discount / 100.0)
                line.update({"fixed_discount": fixed_discount})
            if line.discount == 0:
                fixed_discount = 0.000
                line.update({"fixed_discount": fixed_discount})

    @api.onchange("fixed_discount")
    def _onchange_fixed_discount(self):
        for line in self:
            if line.fixed_discount != 0:
                self.discount = 0.0
                discount = ((self.product_uom_qty * self.price_unit) - ((self.product_uom_qty * self.price_unit) - self.fixed_discount)) / (
                            self.product_uom_qty * self.price_unit) * 100 or 0.0
                line.update({"discount": discount})
            if line.fixed_discount == 0:
                discount = 0.0
                line.update({"discount": discount})

    def _prepare_invoice_line(self, **optional_values):
        """Prepare the values to create the new invoice line for a sales order line.

        :param optional_values: any parameter that should be added to the returned invoice line
        :rtype: dict
        """
        self.ensure_one()
        res = {
            'display_type': self.display_type or 'product',
            'sequence': self.sequence,
            'name': self.name,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'fixed_discount': self.fixed_discount,
            'gift': self.gift,
            'notes': self.notes,

        'price_unit': self.price_unit,
            'tax_ids': [Command.set(self.tax_id.ids)],
            'sale_line_ids': [Command.link(self.id)],
            'is_downpayment': self.is_downpayment,
        }
        analytic_account_id = self.order_id.analytic_account_id.id
        if self.analytic_distribution and not self.display_type:
            res['analytic_distribution'] = self.analytic_distribution
        if analytic_account_id and not self.display_type:
            analytic_account_id = str(analytic_account_id)
            if 'analytic_distribution' in res:
                res['analytic_distribution'][analytic_account_id] = res['analytic_distribution'].get(analytic_account_id, 0) + 100
            else:
                res['analytic_distribution'] = {analytic_account_id: 100}
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res



class SaleOrder(models.Model):
    _inherit = 'sale.order'
    driver_id = fields.Many2one(comodel_name='res.partner', string='Driver')

    invoice_notes = fields.Char(string='Payment Notes')
    general_notes = fields.Char(string='Notes')
    total_product = fields.Integer(string='Total Product:', compute='_get_total_product', help="total Products" ,default=0)
    total_quantity = fields.Integer(string='Total Quantity:', compute='_get_total_quantity', help="total Quantity")
    total_quantity_packet = fields.Integer(string='Total Quantity Packet:', compute='_get_total_quantity',
                                           help="total Quantity Packet")
    total_quantity_carton = fields.Integer(string='Total Quantity Carton:', compute='_get_total_quantity',
                                           help="total Quantity Carton")

    total_before_discount = fields.Monetary(" Total Before Discount", compute='total_discount')
    discount_total = fields.Monetary("Discount Total", compute='total_discount')
    discount_total_line = fields.Monetary("Discount Total Line ", compute='total_discount')
    total_with_line_discount = fields.Monetary(" Total With Line Discount ", compute='total_discount')
    all_discounts = fields.Monetary("Discount ", compute='total_discount')


    # Count the total discount
    @api.depends('order_line.product_uom_qty', 'order_line.price_unit', 'order_line.discount')
    def total_discount(self):
        for invoice in self:
            final_discount_amount = 0
            final_discount_amount_line = 0
            if invoice:
                for line in invoice.order_line:
                    if line:
                        total_price = line.product_uom_qty * line.price_unit
                        if total_price:
                            discount_amount = total_price - line.price_subtotal
                            if discount_amount:
                                final_discount_amount = final_discount_amount + discount_amount
                            if line.price_unit < 0 and line.product_id.is_discount:
                                final_discount_amount_line = final_discount_amount_line + line.price_subtotal


                invoice.update({
                    'discount_total': final_discount_amount,
                    'discount_total_line': final_discount_amount_line,
                    'total_with_line_discount': invoice.amount_total - final_discount_amount_line,
                    'all_discounts': abs(final_discount_amount_line) + abs(final_discount_amount),
                    'total_before_discount': invoice.amount_total + abs(final_discount_amount_line) + abs(
                        final_discount_amount),

                })

    @api.depends('order_line')
    def _get_total_product(self):
        for record in self:
            record.total_product = 0

            product_list=[]
            for line in record.order_line:
                if line.product_id.is_discount  :
                    continue
                product_list.append(line.product_id)
            record.total_product = len(set(product_list))


    @api.depends('order_line')
    def _get_total_quantity(self):
        for record in self:
            total_qty = 0
            total_qty_packet = 0
            total_qty_carton = 0
            for line in record.order_line:
                if line.product_id.is_discount  :
                    continue
                total_qty = total_qty + line.product_uom_qty
                total_qty_packet= total_qty_packet + (line.product_uom_qty if line.product_uom.qty_type=='packet' else 0)
                total_qty_carton = total_qty_carton + (line.product_uom_qty if line.product_uom.qty_type == 'carton' else 0)
            record.total_quantity = total_qty
            record.total_quantity_packet = total_qty_packet
            record.total_quantity_carton = total_qty_carton


