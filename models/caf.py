# -*- coding: utf-8 -*-
from openerp import models, fields, api
from openerp.tools.translate import _
from openerp.exceptions import Warning
import logging
_logger = logging.getLogger(__name__)

try:
    import xmltodict
except ImportError:
    pass

try:
    import base64
except ImportError:
    pass



class caf(models.Model):
    _name = 'dte.caf'

    name = fields.Char('File Name', readonly=True, compute='_get_filename')

    filename = fields.Char('File Name')

    caf_file = fields.Binary(
        string='CAF XML File', filters='*.xml', required=True,
        store=True, help='Upload the CAF XML File in this holder')

    _sql_constraints=[(
        'filename_unique','unique(filename)','Error! Filename Already Exist!')]

    issued_date = fields.Date('Issued Date')

    sii_document_class = fields.Integer('SII Document Class')

    start_nm = fields.Integer(
        string='Start Number', help='CAF Starts from this number')

    final_nm = fields.Integer(
        string='End Number', help='CAF Ends to this number')

    status = fields.Selection([
        ('draft', 'Draft'),
        ('in_use', 'In Use'),
        ('spent', 'Spent'),
        ('cancelled', 'Cancelled')], string='Status',
        default='draft', help='''Draft: means it has not been used yet. You must put in in used
in order to make it available for use. Spent: means that the number interval
has been exhausted. Cancelled means it has been deprecated by hand.''')

    rut_n = fields.Char(string='RUT')

    company_id = fields.Many2one(
        'res.company', 'Company', required=False,
        default=lambda self: self.env.user.company_id)

    sequence_id = fields.Many2one(
        'ir.sequence', 'Sequence', required=False)

    use_level = fields.Float(string="Use Level", compute='_use_level')

    @api.onchange("caf_file",)
    def load_caf(self, flags=False):
        if not self.caf_file:
            return
        result = xmltodict.parse(
            base64.b64decode(self.caf_file).replace(
                '<?xml version="1.0"?>','',1))['AUTORIZACION']['CAF']['DA']

        self.start_nm = result['RNG']['D']
        self.final_nm = result['RNG']['H']
        self.sii_document_class = result['TD']
        self.issued_date = result['FA']
        self.rut_n = 'CL' + result['RE'].replace('-','')
        if not self.sequence_id:
            raise Warning(_(
                'You should select a DTE sequence before enabling this CAF record'))
        elif self.rut_n != self.company_id.vat.replace('L0','L'):
            raise Warning(_(
                'Company vat %s should be the same that assigned company\'s vat: %s!') % (self.rut_n, self.company_id.vat))
        elif self.sii_document_class != self.sequence_id.sii_document_class:
            raise Warning(_(
                '''SII Document Type for this CAF is %s and selected sequence associated document class is %s. This values should be equal for DTE Invoicing to work properly!''') % (self.sii_document_class, self.sequence_id.sii_document_class))
        elif self.sequence_id.number_next_actual < self.start_nm or self.sequence_id.number_next_actual > self.final_nm:
            raise Warning(_(
                'Folio Number %s should be between %s and %s CAF Authorization Interval!') % (self.sequence_id.number_next_actual, self.start_nm, self.final_nm))
        if flags:
            return True

    @api.depends('start_nm', 'final_nm', 'sequence_id', 'status')
    def _use_level(self):
        for r in self:
            if r.status not in ['draft','cancelled']:
                try:
                    r.use_level = 100 * (float(r.sequence_id.number_next_actual - 1) / float(r.final_nm - r.start_nm + 1))
                except ZeroDivisionError:
                    r.use_level = 0
                print r.use_level, r.sequence_id.number_next_actual, r.final_nm, r.start_nm
                if r.sequence_id.number_next_actual > r.final_nm and r.status == 'in_use':
                    #r.status = 'spent'
                    self.env.cr.execute("""UPDATE dte_caf SET status = 'spent' WHERE filename = '%s'""" % r.filename)
                    print 'spent'
                elif r.sequence_id.number_next_actual <= r.final_nm and r.status == 'spent':
                    #r.status = 'in_use'
                    self.env.cr.execute("""UPDATE dte_caf SET status = 'in_use' WHERE filename = '%s'""" % r.filename)
                    print 'in_use'

            else:
                r.use_level = 0

    @api.multi
    def action_enable(self):
        #if self._check_caf():
        if self.load_caf(flags=True):
            self.status = 'in_use'

    @api.multi
    def action_cancel(self):
        self.status = 'cancelled'

    def _get_filename(self):
        for r in self:
            r.name = r.filename


class sequence_caf(models.Model):
    _inherit = "ir.sequence"

    def _check_dte(self):
        for r in self:
            obj = r.env['account.journal.sii_document_class'].search([('sequence_id', '=', r.id)], limit=1)
            if not obj: # si s guía de despacho
                obj = self.env['stock.location'].search([('sequence_id','=', r.id)], limit=1)
            if obj:
                r.is_dte = obj.sii_document_class_id.dte and obj.sii_document_class_id.document_type in ['invoice', 'debit_note', 'credit_note','stock_picking']

    def _get_sii_document_class(self):
        for r in self:
            obj = self.env['account.journal.sii_document_class'].search([('sequence_id', '=', r.id)], limit=1)
            if not obj: # si s guía de despacho
                obj = self.env['stock.location'].search([('sequence_id','=', r.id)], limit=1)
            r.sii_document_class = obj.sii_document_class_id.sii_code

    def get_qty_available(self, folio=None):
        if not folio:
            folio = self._get_folio()
        try:
            cafs = self.get_caf_files(folio)
        except:
            cafs = False
        available = 0
        if cafs:
            for c in cafs:
                inicial = int(c['AUTORIZACION']['CAF']['DA']['RNG']['D'])
                final = int(c['AUTORIZACION']['CAF']['DA']['RNG']['H'])
                if folio >= inicial and folio <= final:
                    available += final - folio
                else:
                    available +=  final - inicial
                available +=1
        return available

    def _qty_available(self):
        for i in self:
            i.qty_available = i.get_qty_available()

    sii_document_class = fields.Integer('SII Code',
        readonly=True,
        compute='_get_sii_document_class')

    is_dte = fields.Boolean('IS DTE?',
        readonly=True,
        compute='_check_dte')

    dte_caf_ids = fields.One2many(
        'dte.caf',
        'sequence_id',
        'DTE Caf')

    qty_available = fields.Integer(
        string="Quantity Available",
        compute="_qty_available"
    )

    def _get_folio(self):
        return self.number_next

    def get_caf_files(self, folio=None):
        if not folio:
            folio = self._get_folio()
        if not self.dte_caf_ids:
            raise UserError(_('''There is no CAF file available or in use \
for this Document. Please enable one.'''))
        cafs = self.dte_caf_ids
        sorted(cafs, key=lambda e: e.start_nm)
        result = []
        for caffile in cafs:
            post = base64.b64decode(caffile.caf_file)
            post = xmltodict.parse(post.replace(
                '<?xml version="1.0"?>','',1))
            folio_inicial = post['AUTORIZACION']['CAF']['DA']['RNG']['D']
            folio_final = post['AUTORIZACION']['CAF']['DA']['RNG']['H']
            if folio >= int(folio_inicial):
                result.append(post)
        if result:
            return result
        if folio > int(post['AUTORIZACION']['CAF']['DA']['RNG']['H']):
            msg = '''El folio de este documento: {} está fuera de rango \
del CAF vigente (desde {} hasta {}). Solicite un nuevo CAF en el sitio \
www.sii.cl'''.format(folio, folio_inicial, folio_final)
            # defino el status como "spent"
            caffile.status = 'spent'
            raise UserError(_(msg))
        return False

    def update_next_by_caf(self, folio=None):
        menor = False
        for c in self.get_caf_files(folio):
            if not menor or int(d['AUTORIZACION']['CAF']['DA']['RNG']['D']) < int(menor['AUTORIZACION']['CAF']['DA']['RNG']['D']) :
                menor = d
        if menor and self.folio < int(menor['AUTORIZACION']['CAF']['DA']['RNG']['D']):
            self.number_next = menor['AUTORIZACION']['CAF']['DA']['RNG']['D']

    def _next_do(self):
        folio = super(sequence_caf, self)._next_do()
        if self.dte_caf_ids:
            self.update_next_by_caf(folio)
            folio = self.number_next
        return folio
