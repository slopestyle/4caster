"""HTML страницы Telegram Mini App (PRD §4.4 веб-интерфейс; ADR-0013).

Страница отдаётся как строка (гарантированно попадает в сборку Vercel),
данные тянет с /api/locations и /api/forecast (та же read-модель, что у бота).
Тема берётся из Telegram WebApp themeParams с запасной палитрой.

Экраны: список точек, прогноз (недельный график + дни + предварительная
надёжность по разбросу моделей), сравнение точек. Калиброванная надёжность,
метеограмма 48ч и история — Фаза 2 (нужны часовые данные и хранение истории).
"""

HTML = r'''<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>4CASTER</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
  :root{
    color-scheme:dark light;
    --bg:#141516; --surface:#1e2024; --surface2:#26292f; --surface3:#323841;
    --ink:#f4f5f7; --ink2:#a7adb8; --ink3:#767d89; --hair:#333841; --hair2:#414852;
    --brand:#ff6b35; --brand-ink:#ff8a5c; --brand-wash:#3a2116;
    --accent:#ff6b35; --precip:#6f9bd0;
    --g:#4bbf7f; --a:#e0b13e; --o:#f0783a; --r:#ec5648;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 26px rgba(0,0,0,.5);
  }
  @media (prefers-color-scheme:light){:root{
    --bg:#eceef1; --surface:#ffffff; --surface2:#f4f5f7; --surface3:#e8eaee;
    --ink:#161719; --ink2:#565c68; --ink3:#828996; --hair:#e2e5ea; --hair2:#d1d6de;
    --brand:#e85a26; --brand-ink:#c74a1c; --brand-wash:#ffe9df;
    --accent:#e85a26; --precip:#3f74b8;
    --g:#2f9e6a; --a:#bf8c18; --o:#e8632a; --r:#dc4433;
    --shadow:0 1px 2px rgba(20,25,35,.06),0 6px 18px rgba(20,25,35,.10);
  }}
  :root[data-theme="dark"]{
    --bg:#141516; --surface:#1e2024; --surface2:#26292f; --surface3:#323841;
    --ink:#f4f5f7; --ink2:#a7adb8; --ink3:#767d89; --hair:#333841; --hair2:#414852;
    --brand:#ff6b35; --brand-ink:#ff8a5c; --brand-wash:#3a2116;
    --accent:#ff6b35; --precip:#6f9bd0;
    --g:#4bbf7f; --a:#e0b13e; --o:#f0783a; --r:#ec5648;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 26px rgba(0,0,0,.5);
  }
  :root[data-theme="light"]{
    --bg:#eceef1; --surface:#ffffff; --surface2:#f4f5f7; --surface3:#e8eaee;
    --ink:#161719; --ink2:#565c68; --ink3:#828996; --hair:#e2e5ea; --hair2:#d1d6de;
    --brand:#e85a26; --brand-ink:#c74a1c; --brand-wash:#ffe9df;
    --accent:#e85a26; --precip:#3f74b8;
    --g:#2f9e6a; --a:#bf8c18; --o:#e8632a; --r:#dc4433;
    --shadow:0 1px 2px rgba(20,25,35,.06),0 6px 18px rgba(20,25,35,.10);
  }
  .card,.chart,.days,.rel,.cmp,.hm{box-shadow:var(--shadow)}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
  .app{max-width:520px;margin:0 auto;padding:14px 14px 28px}
  header.hd{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px}
  .wordmark{font-weight:800;letter-spacing:.15em;font-size:15px;text-transform:uppercase}
  .wordmark b{color:var(--brand)}
  .subttl{color:var(--ink2);font-size:12px}
  .muted{color:var(--ink2)} .tiny{color:var(--ink3);font-size:11px}

  /* segmented nav */
  .seg{display:flex;background:var(--surface2);border:1px solid var(--hair);border-radius:12px;
    padding:3px;margin-bottom:14px;gap:3px}
  .seg button{flex:1;border:0;background:none;color:var(--ink2);font:inherit;font-size:13px;
    font-weight:600;padding:8px;border-radius:9px;cursor:pointer}
  .seg button.on{background:var(--brand);color:#fff}

  .card{background:var(--surface);border:1px solid var(--hair);border-radius:16px;
    padding:13px 14px;margin-bottom:10px;display:block;width:100%;text-align:left;
    color:inherit;font:inherit;cursor:pointer}
  .card:active{background:var(--surface2)}
  .row{display:flex;justify-content:space-between;align-items:center;gap:10px}
  .loc{font-weight:650;font-size:16px}
  .band-num{font-variant-numeric:tabular-nums;font-size:13px}
  .band-num b{color:var(--precip)} .band-num u{color:var(--ink3);text-decoration:none;font-size:12px}
  .pill{font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px;background:var(--surface3);
    color:var(--ink2)}
  .pill.ok{color:var(--brand)}

  .dhead{display:flex;justify-content:space-between;align-items:baseline;margin:4px 2px 12px}
  .dhead .loc{font-size:20px;font-weight:750;letter-spacing:-.01em}

  /* weekly chart */
  .chart{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:12px 10px 6px;
    margin-bottom:10px}
  .chart svg{display:block;width:100%;height:auto}
  .chart .cl{display:flex;gap:12px;font-size:9.5px;color:var(--ink2);padding:6px 2px 0;flex-wrap:wrap}
  .chart .cl span{display:inline-flex;gap:5px;align-items:center}
  .sw{width:10px;height:10px;border-radius:3px;display:inline-block}

  .days{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:4px 12px;margin-bottom:10px}
  .dayleg{font-size:10.5px;color:var(--ink3);display:flex;gap:14px;flex-wrap:wrap;
    padding:9px 2px 7px;border-bottom:1px solid var(--hair);line-height:1.4}
  .dayleg span{display:inline-flex;gap:5px;align-items:center}
  .dayleg b{color:var(--ink2);font-weight:700}
  .day{display:grid;grid-template-columns:52px 22px 1fr 46px;gap:10px;align-items:center;
    padding:11px 2px;border-bottom:1px solid var(--hair)}
  .day:last-child{border-bottom:0}
  .dt{font-size:12.5px;font-weight:600} .dt small{display:block;color:var(--ink3);font-size:10.5px}
  .ic{font-size:18px;text-align:center}
  .bw{display:flex;flex-direction:column;gap:4px;min-width:0}
  .track{position:relative;height:7px;border-radius:4px;background:var(--surface3);overflow:hidden}
  .rng{position:absolute;top:0;bottom:0;border-radius:4px;
    background:linear-gradient(90deg,color-mix(in srgb,var(--precip) 25%,transparent),var(--precip))}
  .p50{position:absolute;top:-2px;bottom:-2px;width:2px;background:var(--ink);border-radius:2px;
    box-shadow:0 0 0 2px var(--surface)}
  /* надёжность у полосы разброса — что она и оценивает */
  .rel-inline{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;font-weight:600}
  .rel-inline .dd{width:9px;height:9px}
  .pop{font-size:14px;color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums;
    display:flex;flex-direction:column;align-items:flex-end;gap:1px;line-height:1.1}
  .pop .lbl{font-size:8.5px;color:var(--ink3);font-weight:600}
  .dd{width:8px;height:8px;border-radius:50%}
  /* заголовок инлайн-секции (почасовой / история) */
  .sec-h{margin:16px 2px 8px;font-size:14px;font-weight:700;display:flex;align-items:center;gap:7px}
  /* multi-day strip on location cards */
  .strip{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-top:11px}
  .dcell{text-align:center;padding:5px 0 4px;border-radius:9px;background:var(--surface2)}
  .dcell.dry{background:var(--brand-wash);outline:1px solid var(--brand)}
  .dcell .wd{font-size:9px;color:var(--ink3);font-weight:700}
  .dcell .di{font-size:15px;line-height:1.3}
  .dcell .dd{margin:2px auto 0}
  .dcell .mm{font-size:8.5px;color:var(--ink3);font-variant-numeric:tabular-nums}
  .hint{font-size:10.5px;color:var(--ink3);margin:0 2px 10px;display:flex;gap:12px;flex-wrap:wrap}
  .hint span{display:inline-flex;gap:5px;align-items:center}

  /* reliability (spread-based, qualitative) */
  .rel{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:13px 14px;margin-bottom:10px}
  .rel h4{margin:0 0 10px;font-size:14px}
  .relrow{display:flex;gap:8px;margin-bottom:10px}
  .relchip{flex:1;text-align:center;background:var(--surface2);border:1px solid var(--hair);border-radius:11px;
    padding:9px 4px}
  .relchip .h{font-size:9.5px;color:var(--ink3);font-weight:700}
  .relchip .dot{width:11px;height:11px;border-radius:50%;margin:5px auto 3px}
  .relchip .w{font-size:9.5px;font-weight:600}
  .relmeta{font-size:11.5px;color:var(--ink2);line-height:1.5}
  .relmeta b{color:var(--ink)}
  .g{color:var(--g)} .a{color:var(--a)} .o{color:var(--o)} .r{color:var(--r)}
  .bg-g{background:var(--g)} .bg-a{background:var(--a)} .bg-o{background:var(--o)} .bg-r{background:var(--r)}
  .note{font-size:11px;color:var(--ink2);background:var(--surface2);border:1px dashed var(--hair);
    border-radius:12px;padding:9px 11px;margin-top:8px;line-height:1.45}
  .note b{color:var(--ink)}

  /* compare table */
  .cmp{background:var(--surface);border:1px solid var(--hair);border-radius:16px;overflow:hidden}
  .cmp table{width:100%;border-collapse:collapse;font-size:12.5px}
  .cmp th,.cmp td{padding:9px 8px;text-align:center;border-bottom:1px solid var(--hair)}
  .cmp th{font-size:11px;color:var(--ink2);font-weight:650}
  .cmp td.d{text-align:left;color:var(--ink2);font-size:11px;white-space:nowrap}
  .cmp .v{font-variant-numeric:tabular-nums;font-weight:600}
  .cmp .v small{color:var(--ink3);font-weight:500}

  /* history heatmap */
  .hm{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:14px}
  .hmrow{display:grid;grid-template-columns:38px 1fr;gap:6px;align-items:center;margin-bottom:3px}
  .hm .yl{font-size:9.5px;color:var(--ink3);font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
  .hm .cells{display:grid;gap:3px}
  .hm .cells i{aspect-ratio:1;border-radius:3px;min-height:14px}
  .hm-x{font-size:9px;color:var(--ink3);display:flex;justify-content:space-between;margin:6px 0 0 44px}
  .scale{display:flex;align-items:center;gap:7px;font-size:9.5px;color:var(--ink2);margin-top:10px}
  .scale .grad{flex:1;height:7px;border-radius:4px;
    background:linear-gradient(90deg,var(--surface3),color-mix(in srgb,var(--precip) 40%,var(--surface3)),var(--precip))}
  .state{text-align:center;color:var(--ink2);padding:40px 12px;font-size:14px}
  .back{background:none;border:0;color:var(--brand);font:inherit;font-size:14px;font-weight:600;
    padding:6px 0;cursor:pointer;margin-bottom:4px}
  .skel{height:64px;border-radius:16px;background:linear-gradient(90deg,var(--surface),var(--surface2),var(--surface));
    background-size:200% 100%;animation:sh 1.2s infinite;margin-bottom:10px}
  @keyframes sh{to{background-position:-200% 0}}
  @media (prefers-reduced-motion:reduce){.skel{animation:none}}
  .foot{color:var(--ink3);font-size:10.5px;text-align:center;margin-top:18px;line-height:1.5}
</style>
</head>
<body>
<div class="app">
  <header class="hd">
    <div class="wordmark">4<b>CASTER</b></div>
    <div class="subttl">надёжность прогноза для гор</div>
  </header>
  <div class="seg" id="seg">
    <button data-t="home" class="on">Точки</button>
    <button data-t="compare">Сравнить</button>
  </div>
  <div id="view"><div class="skel"></div><div class="skel"></div><div class="skel"></div></div>
  <div class="foot">Данные: Open-Meteo · ECMWF · DWD · NOAA · ECCC · Météo-France (CC BY 4.0)</div>
</div>
<script>
const tg = window.Telegram && window.Telegram.WebApp;
function applyTheme(){
  // выбираем нашу свет/тёмную палитру по схеме клиента (гарантированный контраст),
  // а не тянем сырые themeParams (из-за них подложки сливались с фоном).
  const scheme = (tg && tg.colorScheme) || (matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', scheme);
  if(tg){ try{
    const bg = getComputedStyle(document.body).backgroundColor;
    tg.setBackgroundColor(bg); tg.setHeaderColor(bg);
  }catch(e){} }
}
if(tg){ tg.ready(); tg.expand(); tg.onEvent('themeChanged', applyTheme); }
applyTheme();
const HIL_IC=['☁️','🌦','🌧','🌧','🌧','⛈'];
const WD=['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
const MAX=60;
const CB=['bg-g','bg-a','bg-o','bg-r'], CW=['надёжно','осторожно','низкая','не опираться'];
const GC=['g','a','o','r'];
function modelsWord(n){const a=n%10,b=n%100;
  if(a===1&&b!==11)return'модель'; if(a>=2&&a<=4&&(b<10||b>=20))return'модели'; return'моделей';}
const H_HOURLY='<h4 class="sec-h">🕐 Почасовой прогноз · 48 ч</h4>';
const H_HIST='<h4 class="sec-h">📅 Как менялся прогноз</h4>';
function wd(iso){return WD[new Date(iso+'T00:00:00').getDay()]}
function dm(iso){const d=new Date(iso+'T00:00:00');return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')}
function g(v){return Math.round(v*10)/10}
function band(d){
  const l=Math.max(0,d.p10/MAX*100),w=Math.max(1.5,(d.p90-d.p10)/MAX*100),m=d.p50/MAX*100;
  return `<div class="track"><div class="rng" style="left:${l}%;width:${w}%"></div><div class="p50" style="left:${m}%"></div></div>`;
}
// качественная надёжность по относительному разбросу моделей + согласию
function confLevel(d,n){
  const rel=(d.p90-d.p10)/Math.max(d.p50,2);
  let lvl = rel<0.35?0 : rel<0.8?1 : rel<1.4?2 : 3;
  if(n<4) lvl=Math.min(3,lvl+1);
  return lvl;
}
function dayStrip(days){
  if(!days.length) return '';
  const up=days.slice(0,7);
  let driest=-1, best=1e9;
  up.forEach((d,i)=>{ if(i>0 && d.p50<best){ best=d.p50; driest=i; } });
  const cells=up.map((d,i)=>{
    const lvl=confLevel(d,d.n_models);
    const dry=(i===driest && best<2);
    return `<div class="dcell ${dry?'dry':''}"><div class="wd">${wd(d.day)}</div>
      <div class="di">${HIL_IC[d.hil_level]}</div><div class="mm">${g(d.p50)}</div>
      <div class="dd ${CB[lvl]}"></div></div>`;
  }).join('');
  return `<div class="strip">${cells}</div>`;
}
const view=document.getElementById('view');
let CACHE={};

document.getElementById('seg').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b));
  if(b.dataset.t==='home') loadHome(); else loadCompare();
});

async function api(u){const r=await fetch(u); if(!r.ok) throw new Error(r.status); return r.json();}

async function loadHome(){
  if(tg&&tg.BackButton) tg.BackButton.hide();
  view.innerHTML='<div class="skel"></div><div class="skel"></div>';
  try{
    const d=await api('/api/locations'); CACHE.locs=d.locations;
    const hint=`<div class="hint"><span><i class="dd bg-g"></i>надёжно</span>
      <span><i class="dd bg-a"></i>осторожно</span><span><i class="dd bg-o"></i>низкая</span>
      <span>рамка — сухой день</span></div>`;
    view.innerHTML=hint+d.locations.map(l=>{
      const t=l.today;
      if(!t) return `<button class="card" onclick="loadForecast('${l.id}')">
        <div class="loc">${l.name}</div><div class="tiny">${l.elevation_m} м · нет данных</div></button>`;
      const today=`<span class="band-num">сегодня <b>${g(t.p50)}</b> <u>(${g(t.p10)}–${g(t.p90)})</u> мм · ${Math.round(t.pop*100)}%</span>`;
      return `<button class="card" onclick="loadForecast('${l.id}')">
        <div class="row"><div><div class="loc">${HIL_IC[t.hil_level]} ${l.name}</div>
          <div class="tiny">${l.elevation_m} м · ${l.cluster}</div></div>
          <span class="pill ok">${l.days_total||(l.days||[]).length} дн →</span></div>
        <div style="margin-top:8px">${today}</div>
        ${dayStrip(l.days||[])}</button>`;
    }).join('')||'<div class="state">Пока нет локаций.</div>';
  }catch(e){view.innerHTML='<div class="state">Не удалось загрузить.</div>'}
}

function weeklyChart(days){
  const W=300,H=120,pad=16,base=H-22,top=8;
  const mx=Math.max(6,...days.map(d=>d.p90));
  const bw=(W-2*pad)/days.length;
  let bars='',wsk='',xl='';
  days.forEach((d,i)=>{
    const x=pad+i*bw+bw/2;
    const y=v=>base-(Math.min(v,mx)/mx)*(base-top);
    const bh=base-y(d.p50);
    bars+=`<rect x="${x-bw*0.28}" y="${y(d.p50)}" width="${bw*0.56}" height="${Math.max(1,bh)}" rx="2" fill="var(--precip)"></rect>`;
    wsk+=`<line x1="${x}" y1="${y(d.p10)}" x2="${x}" y2="${y(d.p90)}" stroke="var(--ink3)" stroke-width="1.4"></line>
      <line x1="${x-3}" y1="${y(d.p90)}" x2="${x+3}" y2="${y(d.p90)}" stroke="var(--ink3)" stroke-width="1.4"></line>`;
    xl+=`<text x="${x}" y="${H-6}" font-size="8.5" fill="var(--ink3)" text-anchor="middle">${wd(d.day)}</text>`;
  });
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Осадки по дням">
    <line x1="${pad}" y1="${base}" x2="${W-pad}" y2="${base}" stroke="var(--hair)"></line>
    ${bars}${wsk}${xl}</svg>
    <div class="cl"><span><i class="sw" style="background:var(--precip)"></i>p50, мм/сут</span>
    <span><i class="sw" style="background:var(--ink3)"></i>разброс p10–p90</span></div></div>`;
}

function relBlock(d){
  const idx=[[0,'1 день'],[2,'3 дня'],[6,'7 дней']];
  const chips=idx.filter(x=>d.days[x[0]]).map(([i,lab])=>{
    const dd=d.days[i], lvl=confLevel(dd,dd.n_models);
    return `<div class="relchip"><div class="h">${lab.toUpperCase()}</div>
      <div class="dot ${CB[lvl]}"></div><div class="w ${GC[lvl]}">${CW[lvl]}</div></div>`;
  }).join('');
  const n=d.days[0]?d.days[0].n_models:d.n_models;
  const far=d.days[6]||d.days[d.days.length-1];
  const nf=far?far.n_models:n;
  const cover=nf<n ? `Моделей в расчёте: <b>${n}/5</b> (к концу горизонта <b>${nf}/5</b>)`
                   : `Моделей в расчёте: <b>${n}/5</b>`;
  const d3=d.days[2]||d.days[d.days.length-1];
  const spread=d3?(d3.p90-d3.p10):0;
  const sw=spread<3?'узкий':spread<12?'умеренный':'широкий';
  return `<div class="rel"><h4>📊 Надёжность <span class="tiny" style="font-weight:400">— предварительно</span></h4>
    <div class="relrow">${chips}</div>
    <div class="relmeta">${cover} · согласованность на 3-й день: <b>${sw}</b> разброс (${g(spread)} мм).
    Чем шире полоса p10–p90 — тем ниже надёжность.</div>
    <div class="note">Оценка по разбросу моделей. <b>Калиброванный скор</b> (совпадение с фактом
    на истории) — Фаза 2.</div></div>`;
}

async function loadForecast(id){
  view.innerHTML='<div class="skel"></div><div class="skel"></div>';
  if(tg&&tg.BackButton){tg.BackButton.show();tg.BackButton.onClick(loadHome);}
  try{
    const d=await api('/api/forecast?location='+encodeURIComponent(id));
    const upd=new Date(d.computed_at);
    const leg=`<div class="dayleg">
      <span><b>%</b> — вероятность осадков</span>
      <span><i class="dd bg-a"></i> точка — надёжность прогноза (разброс моделей)</span></div>`;
    const rows=d.days.map(x=>{
      const lvl=confLevel(x, x.n_models);
      const nm = x.n_models<5 ? ` · <span class="tiny">${x.n_models}/5 моделей</span>` : '';
      return `<div class="day">
      <div class="dt">${dm(x.day)}<small>${wd(x.day)}</small></div>
      <div class="ic">${HIL_IC[x.hil_level]}</div>
      <div class="bw"><span class="band-num"><b>${g(x.p50)}</b> <u>(${g(x.p10)}–${g(x.p90)})</u> мм · ${x.hil_label}${nm}</span>
        ${band(x)}
        <span class="rel-inline"><i class="dd ${CB[lvl]}"></i><span class="${GC[lvl]}">${CW[lvl]}</span></span></div>
      <div class="pop">${Math.round(x.pop*100)}%<span class="lbl">вер-ть</span></div></div>`;
    }).join('');
    view.innerHTML=`<button class="back" onclick="loadHome()">‹ Все точки</button>
      <div class="dhead"><div class="loc">${d.location.name}</div><div class="tiny">${d.location.elevation_m} м</div></div>
      <div class="row" style="margin:0 2px 10px"><span class="pill ok">🛰 ${d.n_models} ${modelsWord(d.n_models)}</span>
        <span class="tiny">обновлено ${String(upd.getHours()).padStart(2,'0')}:${String(upd.getMinutes()).padStart(2,'0')}</span></div>
      ${weeklyChart(d.days)}${relBlock(d)}<div class="days">${leg}${rows}</div>
      <section id="secHourly">${H_HOURLY}<div class="skel"></div></section>
      <section id="secHistory">${H_HIST}<div class="skel"></div></section>`;
    hydrateHourly(id); hydrateHistory(id);
  }catch(e){view.innerHTML='<div class="state">Прогноз ещё не рассчитан.</div>'}
}

function hourlyChart(h){
    const n=h.times.length;
    if(!n) return `<div class="note">Нет часовых данных на ближайшие 48 ч.</div>`;
    const W=320,H=170,padL=6,padR=6,base=H-24,top=14;
    const mx=Math.max(2,...h.p90);
    const sx=i=>padL+i/(n-1)*(W-padL-padR);
    const sy=v=>base-Math.min(v,mx)/mx*(base-top);
    // dry-window shading (p50<0.1)
    let dry='';
    for(let i=0;i<n;i++){ if(h.p50[i]<0.1){ dry+=`<rect x="${sx(i)-1}" y="${top}" width="${(W-padL-padR)/(n-1)+1}" height="${base-top}" fill="var(--g)" opacity="0.05"></rect>`; } }
    // band p10-p90 area
    let up='',dn='';
    for(let i=0;i<n;i++){ up+=`${sx(i).toFixed(1)},${sy(h.p90[i]).toFixed(1)} `; }
    for(let i=n-1;i>=0;i--){ dn+=`${sx(i).toFixed(1)},${sy(h.p10[i]).toFixed(1)} `; }
    const band=`<polygon points="${up}${dn}" fill="var(--precip)" opacity="0.22"></polygon>`;
    // p50 line
    let p50=''; for(let i=0;i<n;i++){ p50+=`${sx(i).toFixed(1)},${sy(h.p50[i]).toFixed(1)} `; }
    const line=`<polyline points="${p50}" fill="none" stroke="var(--precip)" stroke-width="1.6"></polyline>`;
    // POP line (0..1 mapped to full height)
    let pop=''; for(let i=0;i<n;i++){ pop+=`${sx(i).toFixed(1)},${(base-(h.pop[i]||0)*(base-top)).toFixed(1)} `; }
    const popl=`<polyline points="${pop}" fill="none" stroke="var(--accent)" stroke-width="1.2" stroke-dasharray="3 2" opacity="0.9"></polyline>`;
    // day separators + hour labels every 6h
    let grid='',xl='';
    for(let i=0;i<n;i+=6){
      const hh=new Date(h.times[i]+'Z').getUTCHours();
      grid+=`<line x1="${sx(i)}" y1="${top}" x2="${sx(i)}" y2="${base}" stroke="var(--hair)" stroke-width="0.5"></line>`;
      xl+=`<text x="${sx(i)}" y="${H-8}" font-size="8" fill="var(--ink3)" text-anchor="middle">${String(hh).padStart(2,'0')}</text>`;
    }
    const svg=`<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Метеограмма 48 часов">
      ${dry}${grid}<line x1="${padL}" y1="${base}" x2="${W-padR}" y2="${base}" stroke="var(--hair2)"></line>
      ${band}${line}${popl}${xl}
      <text x="${padL}" y="10" font-size="8" fill="var(--ink3)">осадки, мм/ч · часы UTC</text></svg>
      <div class="cl"><span><i class="sw" style="background:var(--precip)"></i>p50 + разброс</span>
      <span><i class="sw" style="background:var(--accent)"></i>вероятность</span>
      <span><i class="sw" style="background:color-mix(in srgb,var(--g) 40%,transparent)"></i>сухо</span></div></div>`;
    // dry window summary
    let firstWet=h.p50.findIndex(v=>v>=0.3);
    const dryHrs = firstWet<0 ? n : firstWet;
    const summary = dryHrs>0
      ? `Сухое окно: ближайшие <b>${dryHrs} ч</b>.`
      : `Осадки уже идут.`;
    return `${svg}
      <div class="note" style="margin-top:10px">${summary} Пунктир — вероятность осадков, полоса — разброс p10–p90 по моделям.</div>`;
}
async function hydrateHourly(id){
  const box=document.getElementById('secHourly'); if(!box) return;
  try{
    const h=await api('/api/hourly?location='+encodeURIComponent(id));
    box.innerHTML=H_HOURLY+hourlyChart(h);
  }catch(e){ box.innerHTML=H_HOURLY+`<div class="note">Не удалось загрузить почасовой прогноз.</div>`; }
}

function heatColor(v,mx){
  if(v==null) return 'var(--surface3)';
  const pct=Math.round(Math.min(v,mx)/(mx||1)*100);
  return `color-mix(in srgb,var(--precip) ${pct}%,var(--surface3))`;
}
function historyHeatmap(h){
    const n=h.issues.length;
    if(!n) return `<div class="note">История пуста — накопится за несколько циклов (каждые 4 ч).</div>`;
    const gtc=`grid-template-columns:repeat(${n},1fr)`;
    const body=h.rows.map(r=>{
      const cells=r.vals.map(v=>`<i style="background:${heatColor(v,h.max)}" title="${v==null?'—':Math.round(v*10)/10+' мм'}"></i>`).join('');
      return `<div class="hmrow"><span class="yl">${dm(r.date)}</span><div class="cells" style="${gtc}">${cells}</div></div>`;
    }).join('');
    const fmtIssue=iso=>{const d=new Date(iso);return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')};
    return `<div class="muted" style="font-size:11px;margin:0 2px 10px">Строки — прогнозируемая дата, столбцы — момент выпуска прогноза (${n}). Цвет — осадки p50.</div>
      <div class="hm">${body}<div class="hm-x"><span>${fmtIssue(h.issues[0])}</span><span>${n>1?fmtIssue(h.issues[n-1]):''} →</span></div>
        <div class="scale"><span>сухо</span><div class="grad"></div><span>ливень</span></div></div>
      <div class="note" style="margin-top:10px">Стабильные столбцы справа — прогноз «устаканился». Скачки — модели меняли мнение. Накапливается автоматически каждые 4 часа.</div>`;
}
async function hydrateHistory(id){
  const box=document.getElementById('secHistory'); if(!box) return;
  try{
    const h=await api('/api/history?location='+encodeURIComponent(id));
    box.innerHTML=H_HIST+historyHeatmap(h);
  }catch(e){ box.innerHTML=H_HIST+`<div class="note">Не удалось загрузить историю.</div>`; }
}

async function loadCompare(){
  if(tg&&tg.BackButton) tg.BackButton.hide();
  view.innerHTML='<div class="skel"></div>';
  try{
    const locs=CACHE.locs||(await api('/api/locations')).locations;
    const data=await Promise.all(locs.map(l=>api('/api/forecast?location='+l.id).catch(()=>null)));
    const cols=data.filter(Boolean);
    if(!cols.length){view.innerHTML='<div class="state">Нет данных для сравнения.</div>';return}
    const nd=Math.min(...cols.map(c=>c.days.length));
    let head='<th class="d">День</th>'+cols.map(c=>`<th>${c.location.name}<br><span class="tiny">${c.location.elevation_m} м</span></th>`).join('');
    let body='';
    for(let i=0;i<nd;i++){
      const dref=cols[0].days[i];
      let cells=cols.map(c=>{const x=c.days[i];return `<td><span class="v">${HIL_IC[x.hil_level]} ${g(x.p50)}<small> мм</small></span></td>`}).join('');
      body+=`<tr><td class="d">${wd(dref.day)} ${dm(dref.day)}</td>${cells}</tr>`;
    }
    view.innerHTML=`<div class="cmp"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>
      <div class="note" style="margin-top:10px">Значение — осадки p50 за сутки. Выберите район с меньшим дождём как альтернативу.</div>`;
  }catch(e){view.innerHTML='<div class="state">Не удалось сравнить.</div>'}
}

loadHome();
</script>
</body>
</html>'''
