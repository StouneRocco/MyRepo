import importlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from tests import ROOT
from api_docs import register_api_docs,SPEC_PATH


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.dist=Path(self.directory.name)
        app=Flask(__name__,template_folder=str(ROOT/'backend'/'templates'))
        register_api_docs(app,self.dist)
        self.client=app.test_client()

    def test_docs_work_without_login_and_have_only_local_assets(self):
        for path in ['/api/docs','/api/docs/']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            html=response.get_data(as_text=True)
            self.assertIn('/api/docs/assets/swagger-ui-bundle.js',html)
            self.assertIn('/api/docs/assets/swagger-ui.css',html)
            self.assertIn('validatorUrl:null',html)
            self.assertIn('persistAuthorization:false',html)
            self.assertNotIn('https://',html)
            self.assertNotIn('localStorage',html)

    def test_openapi_has_jwt_and_public_login(self):
        response=self.client.get('/api/openapi.json')
        self.assertEqual(response.status_code,200)
        spec=response.json
        self.assertEqual(spec['openapi'],'3.0.3')
        self.assertEqual(spec['servers'],[{'url':'/','description':'Serveur actuel, HTTP ou HTTPS'}])
        self.assertEqual(spec['components']['securitySchemes']['bearerAuth']['scheme'],'bearer')
        self.assertEqual(spec['paths']['/api/login']['post']['security'],[])
        self.assertEqual(spec['security'],[{'bearerAuth':[]}])

    def test_local_assets_are_served_and_missing_build_is_explicit(self):
        self.assertEqual(self.client.get('/api/docs/assets/swagger-ui.css').status_code,503)
        (self.dist/'swagger').mkdir()
        (self.dist/'swagger'/'swagger-ui.css').write_text('body{}')
        response=self.client.get('/api/docs/assets/swagger-ui.css')
        self.assertEqual(response.status_code,200)
        self.assertIn('text/css',response.content_type)
        response.close()
        self.assertEqual(self.client.get('/api/docs/assets/openapi.json').status_code,404)

    def test_all_real_api_operations_are_documented_with_correct_security(self):
        with patch.dict(os.environ,{'JWT_SECRET':'test-secret-for-unit-tests-only-32-bytes'}),patch('pymongo.MongoClient'):
            module=importlib.import_module('app')
        spec=json.loads(SPEC_PATH.read_text(encoding='utf-8'))
        operations=set()
        for rule in module.app.url_map.iter_rules():
            if not rule.rule.startswith('/api/') or '/docs/assets/' in rule.rule:
                continue
            path=re.sub(r'<(?:\w+:)?(\w+)>',r'{\1}',rule.rule)
            for method in rule.methods-{'HEAD','OPTIONS'}:
                operations.add((path,method.lower()))
        documented={(path,method) for path,methods in spec['paths'].items() for method in methods if method in ('get','post')}
        self.assertEqual(operations,documented)
        public={'/api/config','/api/login','/api/register','/api/docs','/api/openapi.json'}
        ids=[]
        for path,method in operations:
            operation=spec['paths'][path][method]
            ids.append(operation['operationId'])
            self.assertEqual(operation.get('security',spec['security']),[] if path in public else [{'bearerAuth':[]}])
            names={parameter.get('name') for parameter in operation.get('parameters',[]) if '$ref' not in parameter}
            names.update(spec['components']['parameters'][parameter['$ref'].rsplit('/',1)[-1]]['name']
                         for parameter in operation.get('parameters',[]) if '$ref' in parameter)
            self.assertTrue(set(re.findall(r'{(\w+)}',path))<=names)
        self.assertEqual(len(ids),len(set(ids)))

    def test_docs_do_not_disable_authentication_of_real_routes(self):
        with patch.dict(os.environ,{'JWT_SECRET':'test-secret-for-unit-tests-only-32-bytes'}),patch('pymongo.MongoClient'):
            module=importlib.import_module('app')
        client=module.app.test_client()
        self.assertEqual(client.get('/api/plans').status_code,401)
        self.assertEqual(client.post('/api/view-state',json={'metric':'presence'}).status_code,401)
        self.assertEqual(client.get('/api/openapi.json').status_code,200)


if __name__=='__main__':unittest.main()
