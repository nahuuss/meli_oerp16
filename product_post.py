# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import fields, osv
from openerp.tools.translate import _
import logging
_logger = logging.getLogger(__name__)

import json

#from bottle import Bottle, run, template, route, request
#import json
from meli_oerp_config import *

from warning import warning

import melisdk
from melisdk.meli import Meli

class product_post(osv.osv_memory):
    _name = "mercadolibre.product.post"
    _description = "Wizard de Product Posting en MercadoLibre"

    _columns = {
	    'type': fields.selection([('post','Alta'),('put','Editado'),('delete','Borrado')], string='Tipo de operación' ),
	    'posting_date': fields.date('Fecha del posting'),
	    #'company_id': fields.many2one('res.company',string='Company'),
	    #'mercadolibre_state': fields.related( 'res.company', 'mercadolibre_state', string="State" )
    }

    def pretty_json( self, cr, uid, ids, data, indent=0, context=None ):
        return json.dumps( data, sort_keys=False, indent=4 )

    def product_post(self, cr, uid, ids, context=None):

        product_ids = context['active_ids']
        product_obj = self.pool.get('product.product')

        user_obj = self.pool.get('res.users').browse(cr, uid, uid)
        #user_obj.company_id.meli_login()
        company = user_obj.company_id
        warningobj = self.pool.get('warning')

        #company = self.pool.get('res.company').browse(cr,uid,1)

        CLIENT_ID = company.mercadolibre_client_id
        CLIENT_SECRET = company.mercadolibre_secret_key
        ACCESS_TOKEN = company.mercadolibre_access_token
        REFRESH_TOKEN = company.mercadolibre_refresh_token


        meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET, access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN)
	
        if ACCESS_TOKEN=='':
            meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET)
            url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
            return {
	            "type": "ir.actions.act_url",
	            "url": url_login_meli,
	            "target": "new",
            }

        for product_id in product_ids:
            product = product_obj.browse(cr,uid,product_id)

            if (product.meli_id):
                response = meli.get("/items/%s" % product.meli_id)

            print product.meli_category.meli_category_id
            body = {
                "title": product.meli_title or '',
                "description": product.meli_description or '',	
                "category_id": product.meli_category.meli_category_id or '0',
                "listing_type_id": product.meli_listing_type or '0',
                "buying_mode": product.meli_buying_mode or '',
                "price": product.meli_price  or '0',
                "currency_id": product.meli_currency  or '0',
                "condition": product.meli_condition  or '',
                "available_quantity": product.meli_available_quantity  or '0',
                "warranty": product.meli_warranty or '',
                #"pictures": [ { 'source': product.meli_imagen} ] ,
                "video_id": product.meli_video  or '',
            }

            print body

            assign_img = False and product.meli_id

            if product.meli_imagen:
                body["pictures"] = [ { 'source': product.meli_imagen} ]
            else:
                #publicando imagen cargada en OpenERP
                if product.meli_id==False:
                    print "uploading image..."
                    resim = product.product_meli_upload_image()
                    if "status" in resim:
                        if (resim["status"]=="error" or resim["status"]=="warning"):
                            error_msg = 'MELI: mensaje de error:   ', resim
                            _logger.error(error_msg)
                        else:
                            assign_img = True and product.meli_imagen_id
                    #response = meli.upload("/pictures", imagedata, {'access_token':meli.access_token})                    

            if (product.meli_id):
                body = {
                    "title": product.meli_title or '',
                    #"description": product.meli_description,	
                    #"category_id": product.meli_category.meli_category_id,
                    #"listing_type_id": product.meli_listing_type,
                    "buying_mode": product.meli_buying_mode or '',
                    "price": product.meli_price or '0',
                    #"currency_id": product.meli_currency,
                    "condition": product.meli_condition or '',
                    "available_quantity": product.meli_available_quantity or '0',
                    "warranty": product.meli_warranty or '',
                    #"pictures": [ { 'source': product.meli_imagen} ] ,
                    "video_id": product.meli_video or '',
                }
                response = meli.put("/items/"+product.meli_id, body, {'access_token':meli.access_token})
            else:
                assign_img = True and product.meli_imagen_id
                response = meli.post("/items", body, {'access_token':meli.access_token})

            print response.content
            rjson = response.json()

            if "message" in rjson:
                print "Message received: %s" % rjson["message"]
                if rjson["message"]=="expired_token":
                    print "EXPIRED TOKEN! LOGIN!"

            if "error" in rjson:
                #print "Error received: %s " % rjson["error"]
                error_msg = 'MELI: mensaje de error:  %s , mensaje: %s, status: %s, cause: %s ' % (rjson["error"], rjson["message"], rjson["status"], rjson["cause"])
                _logger.error(error_msg)

                missing_fields = error_msg

                if "message" in rjson and (rjson["message"]=='invalid_token' or rjson["message"]=="expired_token"):
                    meli = Meli(client_id=CLIENT_ID,client_secret=CLIENT_SECRET)
                    url_login_meli = meli.auth_url(redirect_URI=REDIRECT_URI)
                    print "url_login_meli:", url_login_meli
                    raise osv.except_osv( _('MELI WARNING'), _('INVALID TOKEN or EXPIRED TOKEN (must login, go to Edit Company and login):  error: %s, message: %s, status: %s') % ( rjson["error"], rjson["message"],rjson["status"],))
                else:
                    #raise osv.except_osv( _('MELI WARNING'), _('Completar todos los campos! Error: %s , Mensage: %s, Status: %s') % ( rjson["error"], rjson["message"],rjson["status"],))
                    return warningobj.info(cr, uid, title='MELI WARNING', message="Completar todos los campos!  ", message_html="<br><br>"+missing_fields )
                                        
             
            if "id" in rjson:
                product.write( { 'meli_id': rjson["id"]} )
                if (product.meli_imagen_id):
                    if len(rjson["pictures"]):
                        #check if ID is already assigned
                        if ("id" in rjson["pictures"][0]):
                            if (rjson["pictures"][0]["id"]==product.meli_imagen_id):
                                assign_img = False
                            else:
                                assign_img = True
                        else:
                            assign_img = True
                    else:
                        assign_img = True
               #product.write( { 'meli_url': rjson["url"]} )

            if assign_img:
                print "Assigning Imagen Id to Product ID: ", response.content
                response = meli.post("/items/"+product.meli_id+"/pictures", { 'id': product.meli_imagen_id }, { 'access_token': meli.access_token } )


        return {}

product_post()
