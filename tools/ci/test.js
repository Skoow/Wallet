// Test avant publication : la page s'ouvre, sans erreur JavaScript, dans les 4 onglets, profil vide et profil conseillé.
const {chromium}=require('playwright');const http=require('http'),fs=require('fs'),path=require('path');
const root=path.resolve(process.argv[2]||'.');
const srv=http.createServer((q,s)=>{const u=decodeURIComponent(q.url.split('?')[0]);const f=path.join(root,u==='/'?'index.html':u);fs.readFile(f,(e,d)=>{if(e){s.writeHead(404);s.end();return;}const ty=f.endsWith('.json')?'application/json':f.endsWith('.js')?'application/javascript':f.endsWith('.png')?'image/png':'text/html; charset=utf-8';s.writeHead(200,{'Content-Type':ty});s.end(d);});}).listen(8799,async()=>{
  let bad=[];const b=await chromium.launch();
  for(const [mode,w] of [['vide',390],['conseil',390],['conseil',1300]]){
    const p=await b.newPage({viewport:{width:w,height:900}});const errs=[];p.on('pageerror',e=>errs.push(e.message));
    await p.route(/^https:\/\/(?!cdnjs\.cloudflare\.com)/,r=>r.fulfill({status:404,body:''}));
    if(process.env.D3_LOCAL)await p.route('**/d3.min.js',r=>r.fulfill({body:fs.readFileSync(process.env.D3_LOCAL,'utf8'),contentType:'application/javascript'}));
    await p.goto('http://localhost:8799/');if(mode==='conseil')await p.evaluate(()=>{localStorage.setItem('pf-mode:ci','conseil');localStorage.setItem('pf-vue','detail');});await p.reload();await p.waitForTimeout(1500);
    const inp=await p.$('#pf-login input[name=p]');if(inp){await inp.fill('Ci');await p.click('#pf-login form button');}await p.waitForTimeout(5000);
    if(mode==='conseil'){const n=await p.evaluate(()=>document.querySelectorAll('#lignes .row').length);if(n<5)bad.push(mode+' '+w+' : '+n+' lignes seulement');}
    for(const t of ['repart','analyse','journal','suivre']){const tb=await p.$('#tab-'+t);if(tb&&await tb.isVisible()){await tb.click();await p.waitForTimeout(1200);}}
    const txt=await p.evaluate(()=>document.body.innerText);for(const w0 of ['NaN','undefined','[object'])if(txt.includes(w0))bad.push(mode+' '+w+' : texte « '+w0+' » affiché');
    errs.forEach(e=>bad.push(mode+' '+w+' : erreur '+e.slice(0,200)));await p.close();}
  await b.close();srv.close();
  if(bad.length){console.error('ÉCHEC\n'+bad.join('\n'));process.exit(1);}console.log('OK : la page fonctionne');process.exit(0);});
