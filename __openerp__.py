# -*- coding: utf-8 -*-
{
    'author': u'Blanco Martín & Asociados',
    'category': 'Localization/Chile',
    'depends': ['l10n_cl_invoice'],
    "external_dependencies": {
        'python': [
            'xmltodict',
            'base64'
        ]
    },
    'description': u'''\n\nDTE CAF File Data Model\n\n''',
    'installable': True,
    'license': 'AGPL-3',
    'name': 'CAF Container for DTE Compliance',
    'test': [],
    'data': [
        'views/dte_caf.xml',
        'security/ir.model.access.csv',
    ],
    'update_xml': [],
    'version': '9.0.6.5',
    'website': 'http://blancomartin.cl',
    'auto-install': False,
    'active': False
}
