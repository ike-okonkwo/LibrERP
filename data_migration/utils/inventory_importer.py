# -*- encoding: utf-8 -*-
##############################################################################
#
# Copyright (c) 2013-2015 Andrei Levin (andrei.levin at didotech.com)
#
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

import pooler
import threading
from tools.translate import _
from openerp.osv import orm
import math
from product.product import check_ean
import data_migration.settings as settings
from collections import namedtuple
from pprint import pprint
from utils import Utils
from openerp.addons.core_extended.file_manipulation import import_sheet
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)
_logger.setLevel(logging.DEBUG)

DEBUG = settings.DEBUG

if DEBUG:
    import pdb


class ImportFile(threading.Thread, Utils):
    def __init__(self, cr, uid, ids, context):
        # Inizializzazione superclasse
        threading.Thread.__init__(self)
        
        # Inizializzazione classe ImportPricelist
        self.uid = uid
        
        self.dbname = cr.dbname
        self.start_time = datetime.now()
        self.pool = pooler.get_pool(cr.dbname)
        self.product_obj = self.pool['product.product']
        self.inventory_line_obj = self.pool['stock.inventory.line']

        # Necessario creare un nuovo cursor per il thread,
        # quello fornito dal metodo chiamante viene chiuso
        # alla fine del metodo e diventa inutilizzabile
        # all'interno del thread.
        self.cr = pooler.get_db(self.dbname).cursor()
        
        self.productImportID = ids[0]
        
        self.context = context
        self.error = []
        self.warning = []
        self.first_row = True
        
        # Contatori dei nuovi prodotti inseriti e dei prodotti aggiornati,
        # vengono utilizzati per compilare il rapporto alla terminazione
        # del processo di import
        self.uo_new = 0
        self.updated = 0
        self.problems = 0
        self.cache = []
        self.cache_product = {}
    
    def run(self):
        # Recupera il record dal database
        self.filedata_obj = self.pool['inventory.import']
        self.productImportRecord = self.filedata_obj.browse(self.cr, self.uid, self.productImportID, context=self.context)
        self.file_name = self.productImportRecord.file_name.split('\\')[-1]

        self.date = self.productImportRecord.date
        self.location_id = self.productImportRecord.location_id
        
        # ===================================================
        Config = getattr(settings, self.productImportRecord.format)

        self.HEADER = Config.HEADER_INVENTORY_ITEM
        self.REQUIRED_INVENTORY_ITEM = Config.REQUIRED_INVENTORY_ITEM
        self.PRODUCT_SEARCH = Config.INVENTORY_PRODUCT_SEARCH
        self.PRODUCT_WARNINGS = Config.PRODUCT_WARNINGS
        self.PRODUCT_ERRORS = Config.PRODUCT_ERRORS

        # Default values
        
        if not len(self.HEADER) == len(Config.COLUMNS_INVENTORY_ITEM.split(',')):
            pprint(zip(self.HEADER, Config.COLUMNS_INVENTORY_ITEM.split(',')))
            raise orm.except_orm('Error: wrong configuration!', 'The length of columns and headers must be the same')
        
        self.RecordProduct = namedtuple('RecordProduct', Config.COLUMNS_INVENTORY_ITEM)

        # ===================================================
        try:
            table, self.numberOfLines = import_sheet(self.file_name, self.productImportRecord.content_text)
        except Exception as e:
            # Annulla le modifiche fatte
            self.cr.rollback()
            self.cr.commit()

            title = "Import failed"
            message = "Errore nell'importazione del file %s" % self.file_name + "\nDettaglio:\n\n" + str(e)

            if DEBUG:
                ### Debug
                _logger.debug(message)
                pdb.set_trace()
            self.notify_import_result(self.cr, self.uid, title, message, error=True, record=self.productImportRecord)

        if DEBUG:
            # Importa il listino
            self.process(self.cr, self.uid, table)
            
            # Genera il report sull'importazione
            self.notify_import_result(self.cr, self.uid, self.message_title, 'Importazione completata', record=self.productImportRecord)
        else:
            # Elaborazione del listino prezzi
            try:
                # Importa il listino
                self.process(self.cr, self.uid, table)
                
                # Genera il report sull'importazione
                self.notify_import_result(self.cr, self.uid, self.message_title, 'Importazione completata', record=self.productImportRecord)
            except Exception as e:
                # Annulla le modifiche fatte
                self.cr.rollback()
                self.cr.commit()
                
                title = "Import failed"
                message = "Errore alla linea %s" % self.processed_lines + "\nDettaglio:\n\n" + str(e)
                
                if DEBUG:
                    ### Debug
                    _logger.debug(message)
                    pdb.set_trace()

                self.notify_import_result(self.cr, self.uid, title, message, error=True, record=self.productImportRecord)

    def process(self, cr, uid, table):
        self.message_title = _("Importazione Inventario")
        self.progressIndicator = 0
        
        notifyProgressStep = (self.numberOfLines / 100) + 1     # NB: divisione tra interi da sempre un numero intero!
                                                                # NB: il + 1 alla fine serve ad evitare divisioni per zero
        
        # Use counter of processed lines
        # If this line generate an error we will know the right Line Number
        location = self.pool['stock.location'].browse(cr, uid, self.location_id, context=self.context)

        vals_inventory = {
            'name': 'Inventory of {date} on location {location}'.format(date=self.date, location=location.name),
            'date': self.date,
        }

        inventory_id = self.pool['stock.inventory'].create(cr, uid, vals_inventory, self.context)
        for self.processed_lines, row_list in enumerate(table, start=1):
            if not self.import_row(cr, uid, row_list, inventory_id):
                self.problems += 1
                
            if (self.processed_lines % notifyProgressStep) == 0:
                cr.commit()
                completedQuota = float(self.processed_lines) / float(self.numberOfLines)
                completedPercentage = math.trunc(completedQuota * 100)
                self.progressIndicator = completedPercentage
                self.updateProgressIndicator(cr, uid, self.productImportID)
        
        self.progressIndicator = 100
        self.updateProgressIndicator(cr, uid, self.productImportID)
        
        return True
    
    def import_row(self, cr, uid, row_list, inventory_id):
        if self.first_row:
            row_str_list = [self.simple_string(value) for value in row_list]
            for column in row_str_list:
                # print column
                if column in self.HEADER:
                    _logger.info('Riga {0}: Trovato Header'.format(self.processed_lines))
                    return True
            self.first_row = False

        if not len(row_list) == len(self.HEADER):
            row_str_list = [self.simple_string(value) for value in row_list]
            if DEBUG:
                if len(row_list) > len(self.HEADER):
                    pprint(zip(self.HEADER, row_str_list[:len(self.HEADER)]))
                else:
                    pprint(zip(self.HEADER[:len(row_list)], row_str_list))

            error = u"""Row {row}: Row_list is {row_len} long. We expect it to be {expected} long, with this columns:
                {keys}
                Instead of this we got this:
                {header}
                """.format(row=self.processed_lines, row_len=len(row_list), expected=len(self.HEADER), keys=self.HEADER, header=', '.join(map(lambda s: s or '', row_str_list)))

            _logger.error(str(row_list))
            _logger.error(error)
            self.error.append(error)
            return False
        elif DEBUG:
            # pprint(row_list)
            row_str_list = [self.simple_string(value) for value in row_list]
            pprint(zip(self.HEADER, row_str_list))
        
        # Sometime value is only numeric and we don't want string to be treated as Float
        record = self.RecordProduct._make([self.simple_string(value) for value in row_list])

        for field in self.REQUIRED_INVENTORY_ITEM:
            if not getattr(record, field):
                error = "Riga {0}: Manca il valore della {1}. La riga viene ignorata.".format(self.processed_lines, field)
                _logger.debug(error)
                self.error.append(error)
                return False

        product = record.default_code
        if self.cache_product.get(product, False):
            product_ids = [self.cache_product[product]]
            _logger.warning(
                u'Product {0} already processed in cache'.format(product)
            )
            return False
        else:
            product_ids = self.pool['product.product'].search(cr, uid, ['|', ('default_code', '=', product), ('name', '=', product)], context=self.context)

        if not product_ids:

            error = u'Row {row}: Not Find {product}'.format(
                    row=self.processed_lines, product=record.default_code
            )
            _logger.error(str(row_list))
            _logger.error(error)
            self.error.append(error)
            return False

        product_id = product_ids.pop()
        self.cache_product[product] = product_id

        vals_inventory_line = self.inventory_line_obj.on_change_product_id(cr, uid, self.location_id.id, product_id, '', self.date)

        vals_inventory_line.update({
            'inventory_id': inventory_id,
            'location_id': self.location_id.id,
            'product_id': product_id,
            'product_qty': record.product_qty or 0.0,
            'product_uom': self.pool['product.product'].browse(cr, uid, product_id, context=self.context).uom_id.id
        })

        inventory_line_id = self.inventory_line_obj.create(cr, uid, vals_inventory_line, self.context)

        # print '>>>>>>>', record.name

        return inventory_line_id
