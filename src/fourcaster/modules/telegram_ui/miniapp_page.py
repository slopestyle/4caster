"""HTML страницы Telegram Mini App (PRD §4.4 веб-интерфейс; ADR-0013).

Страница отдаётся как строка (гарантированно попадает в сборку Vercel),
данные тянет с /api/locations и /api/forecast (та же read-модель, что у бота).
Тема берётся из Telegram WebApp themeParams с запасной палитрой.
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
  .num{font-variant-numeric:tabular-nums}

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

  /* detail day rows */
  .dhead{display:flex;justify-content:space-between;align-items:baseline;margin:4px 2px 12px}
  .dhead .loc{font-family:"Iowan Old Style",Palatino,Georgia,serif;font-size:20px}
  .days{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:4px 12px}
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
  .note{font-size:11.5px;color:var(--ink2);background:var(--surface2);border:1px dashed var(--hair);
    border-radius:12px;padding:10px 12px;margin-top:12px;line-height:1.45}
  .note b{color:var(--ink)}
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
<div class="app" id="app">
  <header class="hd">
    <div class="wordmark">4<b>CASTER</b></div>
    <div class="subttl" id="sub">надёжность прогноза для гор</div>
  </header>
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
const HIL_IC = ['☁️','🌦','🌧','🌧','🌧','⛈'];
const WD = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
const MAX = 60;
function wd(iso){ const d=new Date(iso+'T00:00:00'); return WD[d.getDay()]; }
function dm(iso){ const d=new Date(iso+'T00:00:00'); return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0'); }
function g(v){ return (Math.round(v*10)/10); }
function band(d){
  const l=Math.max(0,d.p10/MAX*100), w=Math.max(1.5,(d.p90-d.p10)/MAX*100), m=d.p50/MAX*100;
  return `<div class="track"><div class="rng" style="left:${l}%;width:${w}%"></div><div class="p50" style="left:${m}%"></div></div>`;
}
const view = document.getElementById('view');

async function loadHome(){
  document.getElementById('sub').textContent='надёжность прогноза для гор';
  if(tg && tg.BackButton) tg.BackButton.hide();
  try{
    const r = await fetch('/api/locations'); const data = await r.json();
    view.innerHTML = data.locations.map(l=>{
      const t=l.today;
      const right = t ? `<span class="band-num"><b>${g(t.p50)}</b> <u>(${g(t.p10)}–${g(t.p90)})</u> мм</span>` : '<span class="tiny">нет данных</span>';
      const ic = t ? HIL_IC[t.hil_level] : '·';
      const pop = t ? `<span class="pill">${Math.round(t.pop*100)}%</span>` : '';
      return `<button class="card" onclick="loadForecast('${l.id}')">
        <div class="row"><div><div class="loc">${ic} ${l.name}</div><div class="tiny">${l.elevation_m} м · ${l.cluster}</div></div>${pop}</div>
        <div class="row" style="margin-top:8px">${right}<span class="tiny">подробнее →</span></div>
      </button>`;
    }).join('') || '<div class="state">Пока нет локаций.</div>';
  }catch(e){ view.innerHTML = '<div class="state">Не удалось загрузить. Потяните обновить.</div>'; }
}

async function loadForecast(id){
  view.innerHTML = '<div class="skel"></div><div class="skel"></div>';
  if(tg && tg.BackButton){ tg.BackButton.show(); tg.BackButton.onClick(loadHome); }
  try{
    const r = await fetch('/api/forecast?location='+encodeURIComponent(id));
    if(!r.ok){ view.innerHTML='<div class="state">Прогноз ещё не рассчитан.</div>'; return; }
    const d = await r.json();
    const upd = new Date(d.computed_at);
    const days = d.days.map(x=>`
      <div class="day">
        <div class="dt">${dm(x.day)}<small>${wd(x.day)}</small></div>
        <div class="ic">${HIL_IC[x.hil_level]}</div>
        <div class="bw"><span class="band-num"><b>${g(x.p50)}</b> <u>(${g(x.p10)}–${g(x.p90)})</u> мм · ${x.hil_label}</span>${band(x)}</div>
        <div class="pop">${Math.round(x.pop*100)}%</div>
      </div>`).join('');
    view.innerHTML = `
      <button class="back" onclick="loadHome()">‹ Все точки</button>
      <div class="dhead"><div class="loc">${d.location.name}</div>
        <div class="tiny">${d.location.elevation_m} м</div></div>
      <div class="row" style="margin:0 2px 10px"><span class="pill ok">Consensus ${d.n_models}/5</span>
        <span class="tiny">обновлено ${String(upd.getHours()).padStart(2,'0')}:${String(upd.getMinutes()).padStart(2,'0')}</span></div>
      <div class="days">${days}</div>
      <div class="note"><b>📊 Надёжность</b> по горизонтам 1/3/7/14 суток — калибровка в Фазе 2.
        Сейчас честно: согласие <b>${d.n_models}/5</b> моделей и разброс <b>p10–p90</b> в каждой строке.
        Шире полоса — выше неопределённость.</div>`;
  }catch(e){ view.innerHTML='<div class="state">Ошибка сети.</div>'; }
}
loadHome();
</script>
</body>
</html>'''
