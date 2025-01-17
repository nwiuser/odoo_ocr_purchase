from odoo import models, fields, api
from .ocr_processor import OCRProcessor

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    
    def action_traiter_ocr(self):
        """
        Opens the OCR processing wizard.
        """
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order.ocr.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

