import {cpSync,rmSync} from 'node:fs';
rmSync('dist',{recursive:true,force:true});
cpSync('frontend/dist','dist',{recursive:true});
