#!/usr/bin/python
__author__ = 'smetta'
# Import the module
import sys
import os
import socket
import json
import httplib
import sys
import base64
import ssl
import sys
import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom

DOCUMENTATION = '''
---
module: vra_settings.py
Short_description: Module for deploying VRA ova
description:
    - Provides an interface for deployment of ova in venter
versoin_added: "0.1"
options:
    vra_instance:
        description:
            - DNS or Ip address  of the instance.
        required: True
        default: Null
    vra_port:
        description:
            - port where the VRA listens default 5480
        required: True
        default: Null
    vra_user:
        description:
            - user for the vra
        required: True
        default: Null
    vra_root_password:
        description:
            - password to be used with user root
        required: True
        default: Null
   vra_postgres_db
        description:
            - post gres db information such as user, password, database etc. please look below
        required: True
        default: Null
'''
EXAMPLES = '''

- name: Configure Postgres DB
  ignore_errors: no
  vra_postgresdb_setup:
    vra_instance: "{{vra_instance}}"
    vra_port: "{{vra_port}}"
    vra_user: "{{vra_user}}"
    vra_root_password: "{{vra_root_password}}"
    vra_postgres_db:
      host: "{{vra_postgres_host}}"
      port: "{{vra_postgres_port}}"
      database: "{{vra_postgres_database}}"
      user: "{{vra_postgres_user}}"
      password: "{{vra_postgres_password}}"
'''

class VRA(object):
    def __init__(self, module):
        self.module = module

    def get_vra(self, instance, port):
        #https://blr-3rd-4-dhcp102.eng.vmware.com:5480/#core.Login
        conn = httplib.HTTPSConnection(instance, port)
        headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Cache-Control": "no-cache"}
        conn.request('GET', "/#core.Login", "", headers)
        response = conn.getresponse()
        conn.close()
        return response.status == 200 and response.reason == 'OK'

    def get_vra_auth_token(self, instance, user, password, port):
        token = None
        conn = httplib.HTTPSConnection(instance, port)
        credential_string = user+":"  + password
        credential_string_bytes = credential_string.encode()
        encoded_creds = base64.encodestring(credential_string_bytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encoded_creds, "Accept": "text/html, text/xml, application/xml", "Cache-Control": "no-cache", "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.8,pt;q=0.6", "Connection":"keep-alive", "Content-type":"application/xml; charset=\"UTF-8\""}
        request_payload = """<?xml version="1.0" encoding="UTF-8"?>
    <CIM CIMVERSION="2.0" DTDVERSION="2.0"><MESSAGE ID="5" PROTOCOLVERSION="1.0"><SIMPLEREQ><METHODCALL NAME="CreateSessionToken"><LOCALCLASSPATH><LOCALNAMESPACEPATH><NAMESPACE NAME="root"/><NAMESPACE NAME="cimv2"/></LOCALNAMESPACEPATH><CLASSNAME NAME="VAMI_Authentication"/></LOCALCLASSPATH></METHODCALL></SIMPLEREQ></MESSAGE></CIM>"""
        conn.request('POST', "/cimom", request_payload, headers)
        response = conn.getresponse()
        status = response.status
        if ( status == 200 and response.reason == 'OK'):
            xmlResponse = response.read().decode(encoding='UTF-8')
            lines = xmlResponse.splitlines()
            for line in lines:
                if '<VALUE>' in line:
                     value = line.replace("<VALUE>", "")
                     value = value.replace("</VALUE>", "")
                     if value != '0':
                        token = value
                        break
        else:
            print("Error code: " + str(status))
        conn.close()
        return token

    def configure_postgresdb(self, instance, user, token, host, port, database, db_user, password):
        conn = httplib.HTTPSConnection(instance, 5480)
        credential_string = user+":" + token
        credential_string_bytes = credential_string.encode()
        encoded_creds = base64.encodestring(credential_string_bytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encoded_creds, "Accept": "text/html, text/xml, application/xml", "Cache-Control": "no-cache", "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.8,pt;q=0.6", "Connection":"keep-alive", "Content-type":"application/xml; charset=\"UTF-8\""}
        request_payload = """<?xml version="1.0" encoding="utf-8"?>
                        <request>
                        <locale>en-US</locale>
                        <action>query</action>
                        <requestid>dbUpdate</requestid>
                        <value id="db.host">127.0.0.1</value>
                        <value id="db.port">5433</value>
                        <value id="db.database">vcac</value>
                        <value id="db.user">vcac</value>
                        <value id="db.password"></value>
                        </request>"""
        root = ET.fromstring(request_payload)
        for value in root.findall('value'):
            if 'id' in value.attrib:
                if value.get('id') == 'db.host':
                    value.text = host
                elif value.get('id')=='db.port':
                    value.text = str(port)
                elif value.get('id')=='db.database':
                    value.text = database
                elif value.get('id')=='db.user':
                    value.text = db_user
                elif value.get('id')=='db.password':
                    value.text = password
        request_payload = ET.tostring(root, encoding='us-ascii', method='xml')
        conn.request('POST', "/service/cafe/config-page.py", request_payload, headers)
        response = conn.getresponse()
        status = response.status
        reason = response.reason
        xml_response = response.read().decode(encoding='us-ascii')
        conn.close()
        if ( status == 200 and reason == 'OK'):
            return True, xml_response
        else:
            print("Error code: " + status)
            return False, +xml_response

    def get_postgresdb_info(self, instance, user, port, token):
        conn = httplib.HTTPSConnection(instance, port)
        credential_string = user+":" + token
        credential_string_bytes = credential_string.encode()
        encoded_creds = base64.encodestring(credential_string_bytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encoded_creds, "Content-Type": "text/plain;charset=UTF-8"}
        request_payload = """<?xml version="1.0" encoding="utf-8"?>
                         <request>
                         <locale>en-US</locale>
                         <action>query</action>
                         <requestid>dbInfo</requestid>
                         </request>"""

        conn.request('POST', "/service/cafe/config-page.py", request_payload, headers)
        response = conn.getresponse()
        xml_response = response.read().decode(encoding='UTF-8')
        status = response.status
        reason = response.reason
        conn.close()
        if ( status == 200 and reason == 'OK'):
            return xml_response
        else:
            print("Error code: " + status)
            return None

def core(module):
    vra_instance = module.params.get("vra_instance")
    vra_user = module.params.get("vra_user")
    vra_port = module.params.get("vra_port")
    vra_root_password = module.params.get("vra_root_password")
    vra_postgres_db = module.params.get("vra_postgres_db")

    try:
        token=''
        vra = VRA(module)
        if (vra.get_vra(vra_instance,vra_port)):
            token = vra.get_vra_auth_token(vra_instance, vra_user, vra_root_password,vra_port)
            if(token != None):
                #get_postgresdb_info(vra_instance, vra_user, vra_port, token)
                status, message = vra.configure_postgresdb(vra_instance, vra_user, token,vra_postgres_db['host'],vra_postgres_db['port'], vra_postgres_db['database'], vra_postgres_db['user'], vra_postgres_db['password'] )
                if status:
                #get_postgresdb_info(vra_instance, vra_user, vra_port, token)
                    return False, "Postgres REST API Invoked  Successfully by " + vra_user+ "for " + vra_instance + " with Token:" + token + " Response received:" + message
                else:
                    return True, message
            else:
                return True, vra_instance
    except Exception as a:
        return True, dict(msg=str(a))

def main():
    module = AnsibleModule(
        argument_spec = dict(
            vra_postgres_db = dict(type='dict',required=True),
            vra_instance = dict(type='str',required=True),
            vra_user = dict(type='str',required=False, default='root'),
            vra_port = dict(type='int',required=False, default='5480'),
            vra_root_password = dict(type='str',required=True),
        )
    )

    try:
        fail, result  = core(module)
    except Exception as e:
        import traceback
        module.fail_json(msg = '%s: %s\n%s' %(e.__class__.__name__, str(e), traceback.format_exc()))
    if fail:
        module.fail_json(msg=result)
    else:
        module.exit_json(changed=True, msg=result)

from ansible.module_utils.basic import *
from ansible.module_utils.facts import *
main()
