/* LifeLink Pro dashboards. No inline scripts/styles/handlers -> works under a strict CSP. */
(function(){
'use strict';
const LOW=8,GROUPS=['A+','A-','B+','B-','O+','O-','AB+','AB-'];
const S={token:null,me:null,page:''};
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const arr=x=>Array.isArray(x)?x:(x&&typeof x==='object'?(Object.values(x).find(Array.isArray)||[]):[]);
const pk=(o,...k)=>{for(const s of [o,o&&o.request]){if(!s)continue;for(const x of k)if(s[x]!=null&&s[x]!=='')return s[x]}return ''};
const pill=t=>`<span class="pill p-${String(t).toLowerCase().replace(/[^a-z]/g,'')}">${esc(t)}</span>`;
const strip=a=>`<div class="strip">${a.map(x=>`<div><b>${esc(x[1])}</b><span>${esc(x[0])}</span></div>`).join('')}</div>`;
const tbl=(h,r)=>`<table><thead><tr>${h.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${r.map(x=>`<tr>${x.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')||`<tr><td colspan="${h.length}">Nothing here yet.</td></tr>`}</tbody></table>`;
const card=(t,b)=>`<div class="card">${t?`<h2>${t}</h2>`:''}${b}</div>`;

function toast(m){const t=document.createElement('div');t.className='toast';t.textContent=m;document.body.appendChild(t);setTimeout(()=>t.remove(),2500)}

async function api(path,opt={}){
  const h={'Content-Type':'application/json'};if(S.token)h.Authorization='Bearer '+S.token;
  const r=await fetch(path,{method:opt.method||'GET',headers:h,body:opt.body?JSON.stringify(opt.body):undefined});
  let j=null;try{j=await r.json()}catch(e){}
  if(r.status===401&&S.token&&path!=='/api/auth/login'){signOut();throw new Error('Session ended. Please log in again.')}
  if(!r.ok)throw new Error((j&&(j.error||j.message))||('Request failed ('+r.status+')'));
  return j;
}

/* ---------- charts (plain SVG) ---------- */
function line(labels,sets){
  const W=560,H=210,p=30,mx=Math.max(1,...sets.flatMap(s=>s.v))+2;
  const x=i=>p+i*(W-2*p)/Math.max(1,labels.length-1),y=v=>H-p-v*(H-2*p)/mx;
  let g='';
  for(let k=0;k<=4;k++){const yy=p+k*(H-2*p)/4;g+=`<line x1="${p}" x2="${W-p}" y1="${yy}" y2="${yy}" stroke="#e5dfda"/>`}
  sets.forEach(s=>{g+=`<polyline fill="none" stroke="${s.c}" stroke-width="2.5" points="${s.v.map((v,i)=>x(i)+','+y(v)).join(' ')}"/>`+s.v.map((v,i)=>`<circle cx="${x(i)}" cy="${y(v)}" r="4" fill="${s.c}"><title>${esc(s.n)}, ${esc(labels[i])}: ${v}</title></circle>`).join('')});
  g+=labels.map((l,i)=>`<text x="${x(i)}" y="${H-8}" text-anchor="middle" font-size="12" fill="#6b6560">${esc(l)}</text>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="7 day trend">${g}</svg><div class="leg">${sets.map(s=>`<span><i class="${s.k}"></i>${esc(s.n)}</span>`).join('')}</div>`;
}
function bars(o){
  const e=GROUPS.map(k=>[k,o[k]||0]),W=560,H=210,p=30,mx=Math.max(1,...e.map(a=>a[1])),bw=(W-2*p)/e.length;
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Blood stock by group">`+e.map(([k,v],i)=>{
    const h=v*(H-2*p-16)/mx,c=v<LOW?'#b4162f':'#157a5b',cx=p+i*bw+bw/2;
    return `<rect x="${cx-bw/2+9}" y="${H-p-h}" width="${bw-18}" height="${h}" rx="3" fill="${c}"><title>${k}: ${v} units</title></rect><text x="${cx}" y="${H-p-h-5}" text-anchor="middle" font-size="12" font-weight="600" fill="${c}">${v}</text><text x="${cx}" y="${H-9}" text-anchor="middle" font-size="12" fill="#6b6560">${k}</text>`}).join('')+
    `</svg><div class="leg"><span><i class="c-green"></i>Enough stock</span><span><i class="c-red"></i>Below ${LOW} units</span></div>`;
}
const trend=t=>line(t.labels,[{n:'Requests',v:t.requests,c:'#b4162f',k:'c-red'},{n:'Donations',v:t.donations,c:'#157a5b',k:'c-green'}]);

/* ---------- shared page pieces ---------- */
const reqRows=l=>l.map(r=>[esc(pk(r,'id')),esc(pk(r,'patient_name','patient')),`<b>${esc(pk(r,'blood_group'))}</b>`,esc(pk(r,'units')),esc(pk(r,'city'))+' / '+esc(pk(r,'hospital')),pill(pk(r,'urgency')||'normal'),pill(pk(r,'status')||'pending')]);
const reqHead=['#','Patient','Group','Units','City / Hospital','Urgency','Status'];
async function pStock(){
  const o=await api('/api/pro/overview'),low=GROUPS.filter(g=>(o.stock[g]||0)<LOW),adm=S.me.role==='admin';
  return card('Units available',bars(o.stock))+
   card('Status by group',tbl(['Group','Units','Status'].concat(adm?['Adjust']:[]),GROUPS.map(g=>[g,o.stock[g],pill((o.stock[g]||0)<LOW?'low':'ok')].concat(adm?[`<button class="btn alt sm" data-act="stock" data-g="${g}" data-d="-1">-1</button> <button class="btn alt sm" data-act="stock" data-g="${g}" data-d="1">+1</button>`]:[]))))+
   (low.length?`<p>Low on: <b>${esc(low.join(', '))}</b>. A camp for these groups would help.</p>`:'');
}
async function pCamps(){
  const l=await api('/api/pro/camps'),role=S.me.role;
  const form=role==='admin'?card('Create a camp',`<form data-form="camp"><label>Name<input name="name" required minlength="3"></label><label>City<input name="city" required></label><label>Date<input name="camp_date" type="date" required></label><label>Slots<input name="slots" type="number" min="1" max="1000" value="50" required></label><div><button class="btn" type="submit">Create camp</button></div></form>`):'';
  return `<div class="grid">${l.map(c=>`<div class="card"><h2>${esc(c.name)}</h2><span class="mut">${esc(c.city)} - ${esc(c.camp_date)}</span><progress max="${c.slots}" value="${c.registered}"></progress><span class="mut">${c.registered} of ${c.slots} slots booked</span>${role==='donor'?`<div class="row"><button class="btn ${c.joined?'alt':''}" data-act="join" data-id="${c.id}" ${c.joined||c.registered>=c.slots?'disabled':''}>${c.joined?'Registered':c.registered>=c.slots?'Full':'Register'}</button></div>`:''}</div>`).join('')||card('','No upcoming camps.')}</div>`+form;
}
async function pLead(){
  const l=await api('/api/pro/leaderboard');
  return card('',tbl(['Rank','Donor','Group','Donations','Level'],l.map(u=>[`<span class="medal">${u.rank}</span>`,esc(u.name),esc(u.blood_group),u.donations,esc(u.level)])));
}

/* ---------- admin ---------- */
async function aDash(){
  const [o,st]=await Promise.all([api('/api/pro/overview'),api('/api/admin/stats').catch(()=>null)]);
  const sys=st?Object.entries(st).filter(([,v])=>typeof v!=='object').map(([k,v])=>[esc(k.replace(/_/g,' ')),esc(v)]):[];
  return strip([['Donors',o.totals.donors],['Open requests',o.totals.open_requests],['Units in stock',o.totals.units],['Upcoming camps',o.totals.camps]])+
   `<div class="grid">${card('Requests and donations, last 7 days',trend(o.trend))}${card('Blood stock by group',bars(o.stock))}</div>`+
   (sys.length?card('System status',tbl(['Item','Value'],sys)):'');
}
async function aReqs(){return card('',tbl(reqHead,reqRows(arr(await api('/api/admin/requests')))))}
async function aDon(){
  const l=await api('/api/pro/donations');
  return card('Donations',tbl(['Donor','Group','Date','Place','Status',''],l.map(d=>[esc(d.donor_name),esc(d.blood_group),esc(d.donated_on),esc(d.place),pill(d.confirmed?'confirmed':'pending'),d.confirmed?'':`<button class="btn sm" data-act="confirm" data-id="${d.id}">Confirm</button>`])));
}
async function aUsers(){
  const l=arr(await api('/api/admin/users'));
  return card('',tbl(['Name','Role','Group','City','Status',''],l.map(u=>{const on=u.is_active==null?true:!!u.is_active;return [esc(u.name),esc(u.role),esc(u.blood_group||'-'),esc(u.city),pill(on?'active':'disabled'),`<button class="btn alt sm" data-act="toggle" data-id="${esc(u.id)}">${on?'Disable':'Enable'}</button>`]})));
}
async function aAudit(){const l=await api('/api/pro/audit');return card('',tbl(['Time','Who','Action'],l.map(a=>[esc(a.ts),esc(a.actor),esc(a.action)])))}

/* ---------- requester ---------- */
async function rDash(){
  const [o,m]=await Promise.all([api('/api/pro/overview'),api('/api/requests/mine').then(arr).catch(()=>[])]);
  const done=m.filter(r=>pk(r,'status')==='fulfilled').length;
  return strip([['My requests',m.length],['Active',m.length-done],['Fulfilled',done],['Units in stock',o.totals.units]])+
   `<div class="grid">${card('Platform activity, last 7 days',trend(o.trend))}${card('Blood stock',bars(o.stock))}</div><a href="#new"><button class="btn">Create blood request</button></a>`;
}
async function rNew(){
  return card('',`<form data-form="request"><label>Patient name<input name="patient_name" required minlength="2"></label><label>Blood group<select name="blood_group">${GROUPS.map(g=>`<option>${g}</option>`).join('')}</select></label><label>Units needed<input name="units" type="number" min="1" max="10" value="1" required></label><label>City<input name="city" required></label><label>Hospital<input name="hospital" required></label><label>Urgency<select name="urgency"><option>normal</option><option>urgent</option><option>critical</option></select></label><div><button class="btn" type="submit">Send request</button></div></form>`);
}
async function rMine(){
  const l=arr(await api('/api/requests/mine'));
  return card('',tbl(reqHead.concat(['Donors who accepted']),reqRows(l).map((r,i)=>{
    const ds=arr(l[i].accepted_donors||l[i].donors);
    return r.concat([ds.map(d=>esc(d.name)+(d.phone?' - '+esc(d.phone):'')).join('<br>')||'<span class="mut">none yet</span>']);
  })))+`<p class="mut">A donor's phone number appears here only after the donor accepts.</p>`;
}

/* ---------- donor ---------- */
async function dDash(){
  const m=await api('/api/pro/me'),nx=m.next_at;
  return strip([['Donations',m.count],['Level',m.level],['Lives helped (est.)',m.count*3],['Blood group',m.blood_group||'-']])+
   `<div class="grid">${card('Level progress',`<p>${nx?`${nx-m.count} more donation${nx-m.count>1?'s':''} to reach the next level.`:'Top level reached.'}</p><progress max="${nx||Math.max(1,m.count)}" value="${m.count}"></progress><p class="mut">Bronze 0 - Silver 3 - Gold 6 - Platinum 10</p>`)}
   ${card('Next eligible date',`<p><b>${esc(m.next_eligible)}</b> ${pill(m.eligible?'eligible':'resting')}</p><p class="mut">A gap of 90 days is kept between donations.</p>`)}</div>`;
}
async function dMatch(){
  const l=arr(await api('/api/notifications'));
  return card('',tbl(['Patient','Group','Units','Hospital','City','Urgency','Action'],l.map(n=>{
    const st=String(pk(n,'status','response')).toLowerCase(),done=['accepted','declined','accept','decline'].includes(st);
    return [esc(pk(n,'patient_name','patient')),`<b>${esc(pk(n,'blood_group'))}</b>`,esc(pk(n,'units')),esc(pk(n,'hospital')),esc(pk(n,'city')),pill(pk(n,'urgency')||'normal'),done?pill(st):`<button class="btn sm" data-act="respond" data-id="${esc(n.id)}" data-r="accept">Accept</button> <button class="btn alt sm" data-act="respond" data-id="${esc(n.id)}" data-r="decline">Decline</button>`];
  })))+`<p class="mut">Your phone number is shared with the requester only after you accept.</p>`;
}
async function dHist(){
  const m=await api('/api/pro/me'),today=new Date().toISOString().slice(0,10);
  return card('My donations',tbl(['Date','Place','Status'],m.history.map(h=>[esc(h.donated_on),esc(h.place),pill(h.confirmed?'confirmed':'pending')])))+
   card('Add a donation',`<form data-form="donation"><label>Date<input name="donated_on" type="date" max="${today}" value="${today}" required></label><label>Place<input name="place" placeholder="Hospital or camp"></label><div><button class="btn" type="submit">Submit for confirmation</button></div></form><p class="mut">An administrator confirms it. After that it counts towards your level.</p>`);
}

/* ---------- router ---------- */
const NAV={
  admin:[['dash','Overview',aDash],['stock','Blood stock',pStock],['reqs','Requests',aReqs],['don','Donations',aDon],['camps','Camps',pCamps],['users','Users',aUsers],['lead','Leaderboard',pLead],['audit','Audit log',aAudit]],
  requester:[['dash','Overview',rDash],['new','New request',rNew],['mine','My requests',rMine],['stock','Blood stock',pStock],['camps','Camps',pCamps]],
  donor:[['dash','My overview',dDash],['match','Matched requests',dMatch],['hist','My donations',dHist],['camps','Camps',pCamps],['lead','Leaderboard',pLead]]};

function loginView(){
  $('#app').innerHTML=`<div class="login"><h1>LifeLink Pro</h1><p class="mut">Blood requests, stock, camps and donor levels in one place.</p>
  <form data-form="login"><label>Email<input name="email" type="email" required autocomplete="username"></label><label>Password<input name="password" type="password" required autocomplete="current-password"></label><button class="btn" type="submit">Log in</button></form>
  <p class="mut">Demo: <button class="btn alt sm" data-act="fill" data-e="ali@demo.pk">Donor</button> <button class="btn alt sm" data-act="fill" data-e="ayesha@demo.pk">Requester</button> <button class="btn alt sm" data-act="fill" data-e="admin@lifelink.pk">Admin</button></p></div>`;
}
async function render(){
  if(!S.me)return loginView();
  const nav=NAV[S.me.role]||NAV.donor,cur=nav.find(n=>n[0]===S.page)||nav[0];S.page=cur[0];
  $('#app').innerHTML=`<div class="shell"><aside><div class="brand">LifeLink<small>Pro</small></div><nav>${nav.map(n=>`<a href="#${n[0]}" class="${n[0]===S.page?'on':''}">${n[1]}</a>`).join('')}</nav><div class="who"><b>${esc(S.me.name)}</b>${esc(S.me.role)}<br><button data-act="logout">Log out</button></div></aside><main><h1>${cur[1]}</h1><div id="body">Loading...</div></main></div>`;
  try{const h=await cur[2]();if(S.page===cur[0])$('#body').innerHTML=h}
  catch(e){if($('#body'))$('#body').innerHTML=`<div class="card err">${esc(e.message)}</div>`}
}
function signOut(){S.token=null;S.me=null;try{sessionStorage.removeItem('llpro')}catch(e){}loginView()}

const ACT={
  logout:()=>{location.hash='';signOut()},
  fill:d=>{const f=document.forms[0];f.email.value=d.e;f.password.value='Password123'},
  stock:async d=>{await api('/api/pro/stock',{method:'POST',body:{blood_group:d.g,delta:+d.d}});render()},
  confirm:async d=>{await api('/api/pro/donations/'+d.id+'/confirm',{method:'POST'});toast('Donation confirmed. Stock updated.');render()},
  toggle:async d=>{await api('/api/admin/users/'+d.id+'/toggle',{method:'POST'});render()},
  join:async d=>{await api('/api/pro/camps/'+d.id+'/register',{method:'POST'});toast('You are registered.');render()},
  respond:async d=>{await api('/api/notifications/'+d.id+'/respond',{method:'POST',body:{response:d.r}});toast(d.r==='accept'?'Accepted. The requester can now see your contact.':'Declined.');render()}
};
const FORM={
  login:async v=>{
    const j=await api('/api/auth/login',{method:'POST',body:v});
    S.token=j.token||j.access_token;if(!S.token)throw new Error('Login worked but no token was returned.');
    const m=await api('/api/me');S.me=m.user||m;
    try{sessionStorage.setItem('llpro',S.token)}catch(e){}
    S.page='';location.hash='dash';render();
  },
  request:async v=>{v.units=+v.units;await api('/api/requests',{method:'POST',body:v});toast('Request sent. Matching donors now.');location.hash='mine';S.page='mine';render()},
  camp:async v=>{v.slots=+v.slots;await api('/api/pro/camps',{method:'POST',body:v});toast('Camp created.');render()},
  donation:async v=>{await api('/api/pro/donations',{method:'POST',body:v});toast('Submitted. Waiting for confirmation.');render()}
};
document.addEventListener('click',async e=>{const t=e.target.closest('[data-act]');if(!t)return;try{await ACT[t.dataset.act](t.dataset)}catch(err){toast(err.message)}});
document.addEventListener('submit',async e=>{const f=e.target.closest('form[data-form]');if(!f)return;e.preventDefault();try{await FORM[f.dataset.form](Object.fromEntries(new FormData(f)))}catch(err){toast(err.message)}});
window.addEventListener('hashchange',()=>{S.page=location.hash.slice(1);if(S.me)render()});

(async function start(){
  let t=null;try{t=sessionStorage.getItem('llpro')}catch(e){}
  if(t){S.token=t;try{const m=await api('/api/me');S.me=m.user||m;S.page=location.hash.slice(1)}catch(e){S.token=null}}
  render();
})();
})();
