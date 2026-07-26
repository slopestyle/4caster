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
    --bg:#0c1119; --surface:#131a26; --surface2:#1a2333; --surface3:#212d40;
    --ink:#e7ecf4; --ink2:#98a4b8; --ink3:#66738a; --hair:#243044;
    --brand:#46b6b8; --precip:#6ea3d6;
    --g:#3bb37c; --a:#d8ac3e; --o:#e08749; --r:#dd5a4e;
  }
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
  body{margin:0;background:var(--bg);color:var(--ink);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    padding:env(safe-area-inset-top) 0 env(safe-area-inset-bottom)}
  .app{max-width:520px;margin:0 auto;padding:14px 14px 28px}
  header.hd{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px}
  .wordmark{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-weight:600;
    letter-spacing:.12em;font-size:15px}
  .wordmark b{color:var(--brand)}
  .subttl{color:var(--ink2);font-size:12px}
  .muted{color:var(--ink2)} .tiny{color:var(--ink3);font-size:11px}

  /* segmented nav */
  .seg{display:flex;background:var(--surface2);border:1px solid var(--hair);border-radius:12px;
    padding:3px;margin-bottom:14px;gap:3px}
  .seg button{flex:1;border:0;background:none;color:var(--ink2);font:inherit;font-size:13px;
    font-weight:600;padding:8px;border-radius:9px;cursor:pointer}
  .seg button.on{background:var(--surface);color:var(--ink)}

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
  .dhead .loc{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-size:20px}

  /* weekly chart */
  .chart{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:12px 10px 6px;
    margin-bottom:10px}
  .chart svg{display:block;width:100%;height:auto}
  .chart .cl{display:flex;gap:12px;font-size:9.5px;color:var(--ink2);padding:6px 2px 0;flex-wrap:wrap}
  .chart .cl span{display:inline-flex;gap:5px;align-items:center}
  .sw{width:10px;height:10px;border-radius:3px;display:inline-block}

  .days{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:4px 12px;margin-bottom:10px}
  .day{display:grid;grid-template-columns:56px 24px 1fr 40px;gap:10px;align-items:center;
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
  .pop{font-size:12px;text-align:right;color:var(--ink2);font-weight:600;font-variant-numeric:tabular-nums}

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
  .hbtn{width:100%;background:var(--surface);border:1px solid var(--hair);border-radius:14px;
    padding:12px 14px;color:var(--ink);font:inherit;font-size:13px;font-weight:600;text-align:left;
    cursor:pointer;display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
  .hbtn:active{background:var(--surface2)}
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
if(tg){ tg.ready(); tg.expand(); applyTheme(); tg.onEvent('themeChanged', applyTheme); }
function applyTheme(){
  const p = tg.themeParams || {}; const s = document.documentElement.style;
  if(p.bg_color) s.setProperty('--bg', p.bg_color);
  if(p.secondary_bg_color) s.setProperty('--surface', p.secondary_bg_color);
  if(p.text_color) s.setProperty('--ink', p.text_color);
  if(p.hint_color){ s.setProperty('--ink2', p.hint_color); s.setProperty('--ink3', p.hint_color); }
  if(p.section_separator_color) s.setProperty('--hair', p.section_separator_color);
  if(p.link_color) s.setProperty('--brand', p.link_color);
}
const HIL_IC=['☁️','🌦','🌧','🌧','🌧','⛈'];
const WD=['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
const MAX=60;
const CB=['bg-g','bg-a','bg-o','bg-r'], CW=['надёжнее','осторожно','низкая','не опираться'];
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
    view.innerHTML=d.locations.map(l=>{
      const t=l.today;
      const right=t?`<span class="band-num"><b>${g(t.p50)}</b> <u>(${g(t.p10)}–${g(t.p90)})</u> мм</span>`:'<span class="tiny">нет данных</span>';
      const ic=t?HIL_IC[t.hil_level]:'·';
      const pop=t?`<span class="pill">${Math.round(t.pop*100)}%</span>`:'';
      return `<button class="card" onclick="loadForecast('${l.id}')">
        <div class="row"><div><div class="loc">${ic} ${l.name}</div><div class="tiny">${l.elevation_m} м · ${l.cluster}</div></div>${pop}</div>
        <div class="row" style="margin-top:8px">${right}<span class="tiny">подробнее →</span></div></button>`;
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
  const n=d.n_models, idx=[[0,'1 день'],[2,'3 дня'],[6,'7 дней']];
  const chips=idx.filter(x=>d.days[x[0]]).map(([i,lab])=>{
    const lvl=confLevel(d.days[i],n);
    return `<div class="relchip"><div class="h">${lab.toUpperCase()}</div>
      <div class="dot ${CB[lvl]}"></div><div class="w ${['g','a','o','r'][lvl]}">${CW[lvl]}</div></div>`;
  }).join('');
  const d3=d.days[2]||d.days[d.days.length-1];
  const spread=d3?(d3.p90-d3.p10):0;
  const sw=spread<3?'узкий':spread<12?'умеренный':'широкий';
  return `<div class="rel"><h4>📊 Надёжность <span class="tiny" style="font-weight:400">— предварительно</span></h4>
    <div class="relrow">${chips}</div>
    <div class="relmeta">Согласие моделей: <b>${n}/5</b> · разброс на 3-й день: <b>${sw}</b> (${g(spread)} мм).
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
    const rows=d.days.map(x=>`<div class="day">
      <div class="dt">${dm(x.day)}<small>${wd(x.day)}</small></div>
      <div class="ic">${HIL_IC[x.hil_level]}</div>
      <div class="bw"><span class="band-num"><b>${g(x.p50)}</b> <u>(${g(x.p10)}–${g(x.p90)})</u> мм · ${x.hil_label}</span>${band(x)}</div>
      <div class="pop">${Math.round(x.pop*100)}%</div></div>`).join('');
    view.innerHTML=`<button class="back" onclick="loadHome()">‹ Все точки</button>
      <div class="dhead"><div class="loc">${d.location.name}</div><div class="tiny">${d.location.elevation_m} м</div></div>
      <div class="row" style="margin:0 2px 10px"><span class="pill ok">Consensus ${d.n_models}/5</span>
        <span class="tiny">обновлено ${String(upd.getHours()).padStart(2,'0')}:${String(upd.getMinutes()).padStart(2,'0')}</span></div>
      ${weeklyChart(d.days)}${relBlock(d)}<div class="days">${rows}</div>
      <button class="hbtn" onclick="loadHistory('${d.location.id}')"><span>📅 Как менялся прогноз</span><span class="tiny">→</span></button>`;
  }catch(e){view.innerHTML='<div class="state">Прогноз ещё не рассчитан.</div>'}
}

function heatColor(v,mx){
  if(v==null) return 'var(--surface3)';
  const pct=Math.round(Math.min(v,mx)/(mx||1)*100);
  return `color-mix(in srgb,var(--precip) ${pct}%,var(--surface3))`;
}
async function loadHistory(id){
  view.innerHTML='<div class="skel"></div>';
  if(tg&&tg.BackButton){tg.BackButton.show();tg.BackButton.onClick(()=>loadForecast(id));}
  try{
    const h=await api('/api/history?location='+encodeURIComponent(id));
    const n=h.issues.length;
    if(!n){view.innerHTML=`<button class="back" onclick="loadForecast('${id}')">‹ Назад</button>
      <div class="state">История пуста — накопится за несколько циклов (каждые 4 ч).</div>`;return}
    const gtc=`grid-template-columns:repeat(${n},1fr)`;
    const body=h.rows.map(r=>{
      const cells=r.vals.map(v=>`<i style="background:${heatColor(v,h.max)}" title="${v==null?'—':Math.round(v*10)/10+' мм'}"></i>`).join('');
      return `<div class="hmrow"><span class="yl">${dm(r.date)}</span><div class="cells" style="${gtc}">${cells}</div></div>`;
    }).join('');
    const fmtIssue=iso=>{const d=new Date(iso);return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')};
    view.innerHTML=`<button class="back" onclick="loadForecast('${id}')">‹ ${h.location.name}</button>
      <div class="dhead"><div class="loc">Как менялся прогноз</div></div>
      <div class="muted" style="font-size:11px;margin:0 2px 10px">Строки — прогнозируемая дата, столбцы — момент выпуска прогноза (${n}). Цвет — осадки p50.</div>
      <div class="hm">${body}<div class="hm-x"><span>${fmtIssue(h.issues[0])}</span><span>${n>1?fmtIssue(h.issues[n-1]):''} →</span></div>
        <div class="scale"><span>сухо</span><div class="grad"></div><span>ливень</span></div></div>
      <div class="note" style="margin-top:10px">Стабильные столбцы справа — прогноз «устаканился». Скачки — модели меняли мнение. Накапливается автоматически каждые 4 часа.</div>`;
  }catch(e){view.innerHTML=`<button class="back" onclick="loadForecast('${id}')">‹ Назад</button><div class="state">Не удалось загрузить историю.</div>`}
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
