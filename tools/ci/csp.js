// Ajoute une politique de sécurité (CSP) à la page publiée : seuls les scripts de la page (empreintes) et d3 (cdnjs) peuvent s'exécuter.
// À lancer après l'allègement de la page, car les empreintes dépendent du texte exact des scripts.
const fs=require('fs'),crypto=require('crypto');
const f=process.argv[2];let h=fs.readFileSync(f,'utf8');
h=h.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>/g,'');
const hs=[];h.replace(/<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi,(m,c)=>{hs.push("'sha256-"+crypto.createHash('sha256').update(c,'utf8').digest('base64')+"'");return m;});
const csp=["default-src 'self'","script-src 'self' "+hs.join(' ')+" https://cdnjs.cloudflare.com","style-src 'self' 'unsafe-inline'","img-src 'self' https: data: blob:","font-src 'self' data:","connect-src 'self' https://raw.githubusercontent.com https://api.coingecko.com https://finnhub.io wss://ws.finnhub.io https://cdnjs.cloudflare.com","manifest-src 'self'","worker-src 'self'","object-src 'none'","base-uri 'none'","form-action 'none'"].join('; ');
const meta='<meta http-equiv="Content-Security-Policy" content="'+csp+'">';
h=/<meta charset[^>]*>/i.test(h)?h.replace(/(<meta charset[^>]*>)/i,'$1'+meta):h.replace(/<head>/i,'<head>'+meta);
fs.writeFileSync(f,h);console.log('CSP :',hs.length,'scripts autorisés');
