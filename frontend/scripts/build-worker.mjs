import {mkdir,readdir,readFile,writeFile,copyFile} from 'node:fs/promises';
import {resolve,relative,sep} from 'node:path';

const root=resolve('dist');
const mime={html:'text/html; charset=utf-8',js:'text/javascript; charset=utf-8',css:'text/css; charset=utf-8',svg:'image/svg+xml'};
const assets={};
for(const name of await readdir(root,{recursive:true})){
  const file=resolve(root,name);
  const type=mime[name.split('.').at(-1)];
  if(type)assets['/'+relative(root,file).split(sep).join('/')]=[type,await readFile(file,'utf8')];
}
const identity=await readFile('product.mjs','utf8');
const gateway=(await readFile('server/gateway.mjs','utf8')).replace(
  "import {productIdentityPrompt, productIdentityAnswer} from '../product.mjs';", identity);
const serve=`function serveAsset(request){
  const path=new URL(request.url).pathname;
  const file=path==='/'?'/index.html':path;
  const entry=Object.hasOwn(assets,file)?assets[file]:null;
  if(!entry || !['GET','HEAD'].includes(request.method))return new Response('Not found',{status:404});
  return new Response(request.method==='HEAD'?null:entry[1],{headers:{'Content-Type':entry[0],'Cache-Control':file.startsWith('/assets/')?'private, max-age=31536000, immutable':'private, no-cache','X-Content-Type-Options':'nosniff'}});
}`;
const base=`${gateway}\nconst assets=Object.freeze(${JSON.stringify(assets)});\n${serve}\n`;
await mkdir(resolve(root,'server'),{recursive:true});
await mkdir(resolve(root,'.openai'),{recursive:true});
await copyFile('.openai/hosting.json',resolve(root,'.openai/hosting.json'));
await writeFile(resolve(root,'server/index.js'),`${base}
export default {fetch(request,env){
  const path=new URL(request.url).pathname;
  if(path.startsWith('/api/unicron/'))return createGateway(env)(request);
  return serveAsset(request);
}};`);
