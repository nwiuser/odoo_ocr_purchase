{
    'name': 'Purchase OCR',
    'version': '1.0.0',
    'summary': 'Module to extract and process data from purchase documents using OCR',
    'description': """
This module extends the Purchase module by adding OCR capabilities to extract 
and process data from uploaded documents such as invoices and purchase orders.
""",
    'author': 'Nouisser Zakaria',
    'category': 'Purchases',
    'depends': ['purchase', 'base', 'mail'],
    'data': [
        'views/purchase_order_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'purchase_ocr/static/src/js/ocr_script.js',
        ],
    },
    'images': ['static/description/icon.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
