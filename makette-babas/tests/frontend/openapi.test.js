import test from 'node:test';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

// Dépendance installée dans frontend/node_modules (npm ci).
const SwaggerParser=createRequire(new URL('../../frontend/package.json',import.meta.url))('@apidevtools/swagger-parser');

test('OpenAPI is valid and all references resolve locally',async()=>{
  const spec=await SwaggerParser.validate(fileURLToPath(new URL('../../backend/openapi.json',import.meta.url)));
  assert.equal(spec.openapi,'3.0.3');
  assert.equal(spec.components.securitySchemes.bearerAuth.scheme,'bearer');
  assert.equal(spec.paths['/api/login'].post.security.length,0);
  assert.ok(spec.paths['/api/view-state'].post.requestBody);
  assert.ok(spec.paths['/api/calibration-settings'].post.responses['409']);
});

test('Swagger applies only a token returned by a successful login and never persists it',()=>{
  const html=readFileSync(new URL('../../backend/templates/api_docs.html',import.meta.url),'utf8');
  const script=html.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace("{{ url_for('openapi_spec')|tojson }}",JSON.stringify('/api/openapi.json'));
  const calls=[];
  let config;
  const api={preauthorizeApiKey:(...args)=>calls.push(args)};
  const bundle=options=>{config=options;return api;};
  bundle.presets={apis:{}};
  const window={location:{href:'https://localhost:5000/api/docs'}};
  vm.runInNewContext(script,{window,SwaggerUIBundle:bundle,URL,console});
  assert.equal(config.persistAuthorization,false);
  assert.equal(config.validatorUrl,null);
  assert.equal(calls.length,0);
  config.responseInterceptor({url:'/api/login',status:401,obj:{token:'invalid'}});
  config.responseInterceptor({url:'/api/plans',status:200,obj:{token:'unrelated'}});
  assert.equal(calls.length,0);
  config.responseInterceptor({url:'/api/login',status:200,obj:{token:'test-jwt'}});
  assert.deepEqual(calls,[['bearerAuth','test-jwt']]);
});
