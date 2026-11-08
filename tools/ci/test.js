// Test avant publication : la page s'ouvre, sans erreur JavaScript, dans les 4 onglets, profil vide et profil conseillé, puis les fonctions clés (import, journal, portefeuilles, suivi, sources).
const {chromium}=require('playwright');const http=require('http'),fs=require('fs'),path=require('path');
const root=path.resolve(process.argv[2]||'.');
const srv=http.createServer((q,s)=>{const u=decodeURIComponent(q.url.split('?')[0]);const f=path.join(root,u==='/'?'index.html':u);fs.readFile(f,(e,d)=>{if(e){s.writeHead(404);s.end();return;}const ty=f.endsWith('.json')?'application/json':f.endsWith('.js')?'application/javascript':f.endsWith('.png')?'image/png':'text/html; charset=utf-8';s.writeHead(200,{'Content-Type':ty});s.end(d);});}).listen(8799,async()=>{
  let bad=[];
  // Données : chaque action du portefeuille conseillé doit avoir cours, chiffres, ventes par pays et vérification (voir CLAUDE.md)
  try{const J=f=>JSON.parse(fs.readFileSync(path.join(root,'data',f),'utf8'));const PA=J('params.json'),UV=J('univers.json'),EX=J('expo.json'),PR=J('prix.json');
   const UU=Object.fromEntries((Array.isArray(UV)?UV:UV.data).map(u=>[u.cle,u])),EE=Object.fromEntries(EX.map(e=>[e.cle,e])),PP=new Set(PR.map(r=>r.cle));const D='données conseillé : ';
   (PA.choix||[]).filter(c=>!/^(e|m|c)\//.test(c)).forEach(c=>{const nm=(UU[c]||(PA.extra||{})[c]||{}).nom||c;
    if(!PP.has(c)&&!fs.existsSync(path.join(root,'data','h',c.replace('/','_')+'.json')))bad.push(D+nm+' sans historique de cours (tools/ajout.py)');
    if(!UU[c]){if(!(PA.extra||{})[c])bad.push(D+nm+' absent de params.extra');let pf=null;try{pf=JSON.parse(fs.readFileSync(path.join(root,'data','p',c.replace('/','_')+'.json'),'utf8'));}catch(_){}if(!pf||!pf.ratios||Object.keys(pf.ratios).length<5)bad.push(D+nm+' sans ratios (data/p, nuit.py pro)');}
    const e=EE[c];if(!e||!e.geo)bad.push(D+nm+' sans ventes par pays (data/expo.json)');
    const vf=(UU[c]&&UU[c].verifie)||(e&&e.fiche&&e.fiche.verifie);if(!vf)bad.push(D+nm+' non vérifiée (fiche dans data/expo.json)');});}catch(e){bad.push('données : lecture impossible '+e.message);}
  const b=await chromium.launch();
  for(const [mode,w] of [['vide',390],['conseil',390],['conseil',1300]]){
    const p=await b.newPage({viewport:{width:w,height:900}});const errs=[];p.on('pageerror',e=>errs.push(e.message));
    await p.route(/^https:\/\/(?!cdnjs\.cloudflare\.com)/,r=>r.fulfill({status:404,body:''}));
    if(process.env.D3_LOCAL)await p.route('**/d3.min.js',r=>r.fulfill({body:fs.readFileSync(process.env.D3_LOCAL,'utf8'),contentType:'application/javascript'}));
    await p.goto('http://localhost:8799/');if(mode==='conseil')await p.evaluate(()=>{localStorage.setItem('pf-pfa:ci','conseil');localStorage.setItem('pf-vue','detail');});await p.reload();await p.waitForTimeout(1500);
    const inp=await p.$('#pf-login input[name=p]');if(inp){await inp.fill('Ci');await p.click('#pf-login form button');}await p.waitForTimeout(5000);
    if(mode==='conseil'){const n=await p.evaluate(()=>document.querySelectorAll('#lignes .row').length);if(n<5)bad.push(mode+' '+w+' : '+n+' lignes seulement');}
    for(const t of ['repart','analyse','journal','suivre']){const tb=await p.$('#tab-'+t);if(tb&&await tb.isVisible()){await tb.click();await p.waitForTimeout(1200);}}
    const txt=await p.evaluate(()=>document.body.innerText);for(const w0 of ['NaN','undefined','[object'])if(txt.includes(w0))bad.push(mode+' '+w+' : texte « '+w0+' » affiché');
    errs.forEach(e=>bad.push(mode+' '+w+' : erreur '+e.slice(0,200)));await p.close();}
  // Fonctions clés : import CSV, lignes, journal, plusieurs portefeuilles, suivi, sources d'une ligne
  {const p=await b.newPage({viewport:{width:1300,height:900}});const errs=[];p.on('pageerror',e=>errs.push(e.message));const F='fonctions : ';
   await p.route(/^https:\/\/(?!cdnjs\.cloudflare\.com)/,r=>r.fulfill({status:404,body:''}));
   if(process.env.D3_LOCAL)await p.route('**/d3.min.js',r=>r.fulfill({body:fs.readFileSync(process.env.D3_LOCAL,'utf8'),contentType:'application/javascript'}));
   await p.goto('http://localhost:8799/');await p.evaluate(()=>localStorage.setItem('pf-vue','detail'));await p.reload();await p.waitForTimeout(1200);
   const inp=await p.$('#pf-login input[name=p]');if(inp){await inp.fill('CiF');await p.click('#pf-login form button');}await p.waitForTimeout(4000);
   const ok=await p.evaluate(()=>typeof window.pfImportCsv==='function');if(!ok)bad.push(F+'import CSV absent');
   else{const msg=await p.evaluate(()=>window.pfImportCsv('date;sens;ticker;quantite;prix;devise\n2026-02-02;achat;MSFT;2;400;USD\n2026-03-02;achat;MSFT;1;410;USD\n'));await p.waitForTimeout(3000);
    if(!/2 opérations importées/.test(msg))bad.push(F+'import CSV : '+msg);
    const n=await p.evaluate(()=>document.querySelectorAll('#lignes .row').length);if(n<1)bad.push(F+'ligne non ajoutée après import');
    const tab=await p.$('#tab-journal');if(tab){await tab.click();await p.waitForTimeout(1000);const j=await p.evaluate(()=>document.querySelectorAll('#t-journal tbody tr').length);if(j<2)bad.push(F+'journal : '+j+' opération(s)');await p.click('#tab-suivre');await p.waitForTimeout(800);}
    await p.evaluate(()=>dash.setParams({suivi:[{cle:'s/msft',ticker:'MSFT',nom:'Microsoft',ajout:'2026-01-01',px0:300}]}));await p.waitForTimeout(1200);
    if(!await p.$('#sec-suivi li'))bad.push(F+'suivi et alertes absent');
    const rh=await p.$('#lignes .row .rh');if(rh){await rh.click();await p.waitForTimeout(1200);if(!await p.$('#lignes .dsrc'))bad.push(F+'bloc des sources absent dans la ligne ouverte');}
    await p.evaluate(()=>window.PFS&&PFS.creer('CiF','Second'));await p.waitForLoadState('load');await p.waitForTimeout(3500);
    const n2=await p.evaluate(()=>document.querySelectorAll('#lignes .row').length);if(n2!==0)bad.push(F+'nouveau portefeuille pas vide ('+n2+' lignes)');
    await p.evaluate(()=>PFS.choisir('CiF','principal'));await p.waitForLoadState('load');await p.waitForTimeout(3500);
    const n3=await p.evaluate(()=>document.querySelectorAll('#lignes .row').length);if(n3<1)bad.push(F+'retour au portefeuille principal : lignes perdues');}
   const txt=await p.evaluate(()=>document.body.innerText);for(const w0 of ['NaN','undefined','[object'])if(txt.includes(w0))bad.push(F+'texte « '+w0+' » affiché');
   errs.forEach(e=>bad.push(F+'erreur '+e.slice(0,200)));await p.close();}
  await b.close();srv.close();
  if(bad.length){console.error('ÉCHEC\n'+bad.join('\n'));process.exit(1);}console.log('OK : la page fonctionne');process.exit(0);});
