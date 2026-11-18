import { defineConfig, loadEnv } from "vite";
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import react from "@vitejs/plugin-react";

const require=createRequire(import.meta.url);
function localSwaggerAssets(){
  let output;
  return {
    name:'local-swagger-assets',
    configResolved(config){output=path.resolve(config.root,config.build.outDir,'swagger');},
    closeBundle(){
      const source=path.dirname(require.resolve('swagger-ui-dist/package.json'));
      fs.mkdirSync(output,{recursive:true});
      for(const name of ['swagger-ui.css','swagger-ui-bundle.js','LICENSE','NOTICE']){
        const file=path.join(source,name);
        if(fs.existsSync(file))fs.copyFileSync(file,path.join(output,name));
      }
    }
  };
}

export default defineConfig(({mode}) => {
  const env=loadEnv(mode,process.cwd(),'');
  const configPath=path.resolve('../backend/.tls/config.json');
  let target=env.DEV_API_URL;
  if(!target&&fs.existsSync(configPath)){
    const config=JSON.parse(fs.readFileSync(configPath,'utf8').replace(/^\uFEFF/,''));
    target=`https://${config.hostAddress}:5000`;
  }
  return {
  plugins: [react(),localSwaggerAssets()],
  server: { proxy: { "/api": {target:target||'http://127.0.0.1:5000',secure:true} } },
  };
});
