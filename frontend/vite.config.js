import {Readable} from 'node:stream';
import {defineConfig,loadEnv} from 'vite';
import {createGateway} from './server/gateway.mjs';

export default defineConfig(({mode})=>{
  const values={...loadEnv(mode,process.cwd(),'UNICRON_'),...process.env};
  const handler=createGateway({UNICRON_API_URL:'http://127.0.0.1:42515',...values},{local:true});
  return {
    plugins:[{name:'unicron-local-gateway',configureServer(server){
      server.middlewares.use('/api/unicron',async (request,response)=>{
        const origin=`http://${request.headers.host}`;
        const init={method:request.method,headers:request.headers};
        if(['POST','PUT'].includes(request.method)){init.body=Readable.toWeb(request);init.duplex='half';}
        const result=await handler(new Request(new URL('/api/unicron'+request.url,origin),init));
        response.writeHead(result.status,Object.fromEntries(result.headers));
        if(result.body)Readable.fromWeb(result.body).pipe(response);
        else response.end();
      });
    }}],
    server:{allowedHosts:['terminal.local']},
    build:{rollupOptions:{output:{manualChunks:{react:['react','react-dom']}}}},
  };
});
