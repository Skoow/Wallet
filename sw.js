// Hors ligne : la page et d3 en cache ; les données d'abord depuis le réseau, sinon depuis le cache.
const V='pf-v1794425472';
const D3='https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js';const CORE=['./','index.html','manifest.webmanifest','icons/icon-192.png','icons/icon-512.png'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(V).then(c=>c.addAll(CORE).then(()=>c.add(D3).catch(()=>{}))).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==V).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{const u=new URL(e.request.url);if(e.request.method!=='GET')return;if(u.origin!==self.location.origin&&e.request.url!==D3)return;
  const net=()=>fetch(e.request,{cache:'no-cache'}).then(r=>{if(r.ok){const c=r.clone();caches.open(V).then(x=>x.put(e.request,c));}return r;});
  if(u.pathname.includes('/data/')||u.pathname.endsWith('/')||u.pathname.endsWith('index.html')){e.respondWith(net().catch(()=>caches.match(e.request,{ignoreSearch:true})));return;}
  e.respondWith(caches.match(e.request).then(r=>r||net()));});
