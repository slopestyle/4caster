"""HTML страницы Telegram Mini App (PRD §4.4 веб-интерфейс; ADR-0013).

Страница отдаётся как строка (гарантированно попадает в сборку Vercel),
данные тянет с /api/locations и /api/forecast (та же read-модель, что у бота).
Тема берётся из Telegram WebApp themeParams с запасной палитрой.

Экраны: список точек, прогноз (метеограмма на 48 ч от текущего часа, недельный
график, дни, предварительная надёжность по разбросу моделей, история прогноза),
сравнение точек. Калиброванная надёжность — Фаза 2 (нужна верификация по факту).
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
  .card,.chart,.days,.rel,.cmp,.hm,.hero{box-shadow:var(--shadow)}
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
  .day{display:grid;grid-template-columns:48px 22px 1fr;gap:10px;align-items:start;
    padding:12px 2px;border-bottom:1px solid var(--hair)}
  .day:last-child{border-bottom:0}
  .dt{font-size:12.5px;font-weight:600} .dt small{display:block;color:var(--ink3);font-size:10.5px}
  .ic{font-size:18px;text-align:center}
  .bw{display:flex;flex-direction:column;min-width:0}
  /* строка дня: вердикт (ответ) → вероятность → объём осадков → полоса разброса */
  .verdict{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:14px;font-weight:750}
  .verdict .vd em{color:var(--ink3);font-style:normal;font-weight:600;font-size:11px;margin-left:3px}
  .daypop{font-size:12px;color:var(--ink2);font-weight:600;margin-top:7px}
  .daypop b{color:var(--ink);font-variant-numeric:tabular-nums}
  .daymeta{font-size:11px;color:var(--ink3);margin-top:5px;line-height:1.4;font-variant-numeric:tabular-nums}
  .daymeta b{color:var(--ink2);font-weight:700}
  .bw .track{margin-top:8px}
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
  .relchip-n{font-size:8.5px;color:var(--ink3);font-weight:600;margin-top:3px}
  .relmeta{font-size:11.5px;color:var(--ink2);line-height:1.5}
  .relmeta b{color:var(--ink)}
  .g{color:var(--g)} .a{color:var(--a)} .o{color:var(--o)} .r{color:var(--r)}
  .bg-g{background:var(--g)} .bg-a{background:var(--a)} .bg-o{background:var(--o)} .bg-r{background:var(--r)}
  .note{font-size:11px;color:var(--ink2);background:var(--surface2);border:1px dashed var(--hair);
    border-radius:12px;padding:9px 11px;margin-top:8px;line-height:1.45}
  .note b{color:var(--ink)}
  /* раскрывающаяся плашка «как работает надёжность» */
  .rel-how{margin-top:9px;border-top:1px solid var(--hair);padding-top:9px}
  .rel-how>summary{cursor:pointer;font-size:11.5px;font-weight:600;color:var(--brand-ink);
    list-style:none;display:flex;align-items:center;gap:6px}
  .rel-how>summary::-webkit-details-marker{display:none}
  .rel-how>summary::before{content:'▸';font-size:9px;transition:transform .15s}
  .rel-how[open]>summary::before{transform:rotate(90deg)}
  .rel-how .body{font-size:11px;color:var(--ink2);line-height:1.5;margin-top:9px}
  .rel-lv{display:flex;gap:8px;align-items:flex-start;margin:6px 0}
  .rel-lv i{width:10px;height:10px;border-radius:50%;flex:none;margin-top:3px}
  .rel-lv b{color:var(--ink)}

  /* хайкабельность — единый индикатор «идти / не идти» */
  .hero{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:13px 14px;margin-bottom:10px}
  .hero h4{margin:0 0 10px;font-size:14px}
  .hero-badges{display:flex;gap:8px}
  .hbig{flex:1;background:var(--surface2);border:1px solid var(--hair);border-radius:12px;padding:10px 11px}
  .hbig .m{font-size:11px;color:var(--ink2);font-weight:600}
  .hbig .v{margin-top:6px;font-size:16px;font-weight:750;display:flex;gap:8px;align-items:center}
  .hbig .v .dd{width:12px;height:12px}
  .hike{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:1px}
  .hbadge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;
    background:var(--surface2);border:1px solid var(--hair);border-radius:8px;padding:3px 7px}
  .hbadge em{color:var(--ink3);font-style:normal;font-weight:600;font-size:10px}

  /* compare table */
  .cmp{background:var(--surface);border:1px solid var(--hair);border-radius:16px;overflow:hidden}
  .cmp table{width:100%;border-collapse:collapse;font-size:12.5px}
  .cmp th,.cmp td{padding:9px 8px;text-align:center;border-bottom:1px solid var(--hair)}
  .cmp th{font-size:11px;color:var(--ink2);font-weight:650}
  .cmp td.d{text-align:left;color:var(--ink2);font-size:11px;white-space:nowrap}
  .cmp .v{font-variant-numeric:tabular-nums;font-weight:600}
  .cmp .v small{color:var(--ink3);font-weight:500}

  /* history heatmap */
  .hm{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:12px}
  .hmrow{display:grid;grid-template-columns:38px 1fr;gap:6px;align-items:center;margin-bottom:2px}
  .hm .yl{font-size:9.5px;color:var(--ink3);font-weight:600;text-align:right;font-variant-numeric:tabular-nums}
  .hm .cells{display:grid;gap:2px}
  /* фиксированная высота, а не квадрат: при 3–6 столбцах aspect-ratio:1 раздувал
     ячейки до ~70 px и виджет переставал влезать в экран */
  .hm .cells i{height:12px;border-radius:3px}
  .hm-x{font-size:9px;color:var(--ink3);display:flex;justify-content:space-between;margin:6px 0 0 44px}
  .scale{display:flex;align-items:center;gap:7px;font-size:9.5px;color:var(--ink2);margin-top:10px}
  .scale .grad{flex:1;height:7px;border-radius:4px;
    background:linear-gradient(90deg,var(--g),var(--a),var(--o),var(--r))}
  .state{text-align:center;color:var(--ink2);padding:40px 12px;font-size:14px}
  .back{background:none;border:0;color:var(--brand);font:inherit;font-size:14px;font-weight:600;
    padding:6px 0;cursor:pointer;margin-bottom:4px}
  .skel{height:64px;border-radius:16px;background:linear-gradient(90deg,var(--surface),var(--surface2),var(--surface));
    background-size:200% 100%;animation:sh 1.2s infinite;margin-bottom:10px}
  @keyframes sh{to{background-position:-200% 0}}
  @media (prefers-reduced-motion:reduce){.skel{animation:none}}
  /* модалка «какие модели» */
  button.pill{border:0;font:inherit;cursor:pointer}
  button.pill:active{background:var(--hair2)}
  .lnk{background:none;border:0;padding:0;font:inherit;font-size:11.5px;font-weight:600;
    color:var(--brand-ink);cursor:pointer;text-decoration:underline}
  .modal{position:fixed;inset:0;z-index:50;background:rgba(0,0,0,.55);display:flex;
    align-items:flex-end;justify-content:center;padding:10px}
  .sheet{background:var(--surface);border:1px solid var(--hair);border-radius:18px;width:100%;
    max-width:520px;max-height:84vh;overflow:auto;padding:14px 15px 18px;box-shadow:var(--shadow);
    animation:up .18s ease-out}
  @keyframes up{from{transform:translateY(14px);opacity:.4}}
  @media (prefers-reduced-motion:reduce){.sheet{animation:none}}
  .sheet-hd{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:4px}
  .sheet-hd h4{margin:0;font-size:15px}
  .sheet-hd .x{background:var(--surface2);border:1px solid var(--hair);color:var(--ink2);
    border-radius:9px;font:inherit;font-size:13px;line-height:1;padding:6px 9px;cursor:pointer}
  .mrow{border-top:1px solid var(--hair);padding:10px 0 2px}
  .mtop{display:flex;justify-content:space-between;align-items:baseline;gap:8px;font-size:13px}
  .mtop b{font-weight:700}
  .wbar{height:5px;border-radius:3px;background:var(--surface3);margin:6px 0 6px;overflow:hidden}
  .wbar i{display:block;height:100%;background:var(--brand);border-radius:3px}
  .mtxt{font-size:11.5px;color:var(--ink2);line-height:1.5}
  .foot{color:var(--ink3);font-size:10.5px;text-align:center;margin-top:18px;line-height:1.7}
  .foot a{color:var(--ink2);text-decoration:none;border-bottom:1px solid var(--hair2)}
  .foot a:active{color:var(--brand)}
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
  <div class="foot">Данные:
    <a href="https://open-meteo.com" target="_blank" rel="noopener">Open-Meteo</a> ·
    <a href="https://www.ecmwf.int" target="_blank" rel="noopener">ECMWF</a> ·
    <a href="https://www.dwd.de" target="_blank" rel="noopener">DWD</a> ·
    <a href="https://www.noaa.gov" target="_blank" rel="noopener">NOAA</a> ·
    <a href="https://weather.gc.ca" target="_blank" rel="noopener">ECCC</a> ·
    <a href="https://meteofrance.com" target="_blank" rel="noopener">Météo-France</a>
    (CC BY 4.0)</div>
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
// расшифровка уровней для плашки «как работает надёжность» (порядок = CW/CB/GC)
const LVL_DESC=[
  'модели сходятся — на прогноз можно опираться',
  'умеренный разброс — держите запас и следите за обновлениями',
  'модели заметно расходятся — решение под вопросом',
  'разнобой моделей — прогноз не устоялся, не планируйте по нему'];
function modelsWord(n){const a=n%10,b=n%100;
  if(a===1&&b!==11)return'модель'; if(a>=2&&a<=4&&(b<10||b>=20))return'модели'; return'моделей';}
const H_HOURLY='<h4 class="sec-h">🕐 Осадки · ближайшие 48 часов</h4>';
const H_HIST='<h4 class="sec-h">📅 Как менялся прогноз</h4>';
function wd(iso){return WD[new Date(iso+'T00:00:00').getDay()]}
function dm(iso){const d=new Date(iso+'T00:00:00');return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')}
function g(v){return Math.round(v*10)/10}
// √-шкала: осадки сильно скошены (много нулей, тяжёлый хвост) — корень поднимает
// морось и сжимает ливень, порядок дней сохраняется. Точную величину несёт число.
function sq(v){return Math.sqrt(Math.max(0,v))}
function band(d){
  const S=v=>sq(v)/sq(MAX)*100;
  const l=Math.max(0,S(d.p10)),w=Math.max(2,S(d.p90)-S(d.p10)),m=S(d.p50);
  return `<div class="track"><div class="rng" style="left:${l}%;width:${w}%"></div><div class="p50" style="left:${m}%"></div></div>`;
}
// качественная надёжность по относительному разбросу моделей + согласию
function confLevel(d,n){
  const rel=(d.p90-d.p10)/Math.max(d.p50,2);
  let lvl = rel<0.35?0 : rel<0.8?1 : rel<1.4?2 : 3;
  if(n<4) lvl=Math.min(3,lvl+1);
  return lvl;
}
// ── Хайкабельность: единый индикатор «идти / не идти» ───────────────────────
// Свёртка трёх факторов в одну операционную категорию: критичность осадков
// (HIL), надёжность прогноза и разброс моделей. Объединение геометрическое —
// провал по любому фактору обрушивает итог (по мотивам PRD §10.6.2); показываем
// категорию, а не некалиброванное число (INV-6, P2). Благоприятность дня по HIL
// 0..5 привязана к операционному смыслу §10.4 (0 «планы не меняются» → 5
// «отмена/эвакуация»); множитель RFAV — по уровню надёжности confLevel.
const HFAV=[1.00,0.88,0.55,0.30,0.13,0.04];
const RFAV=[1.00,0.82,0.58,0.40];
const HW=['идти','можно','спорно','не идти'];       // вердикт 0..3 (цвета CB/GC)
function hikeScore(fav,rl,wFav){ return Math.pow(fav,wFav)*Math.pow(RFAV[rl],1-wFav); }
function hikeLevel(s){ return s>=0.72?0 : s>=0.50?1 : s>=0.30?2 : 3; }
// однодневный поход: важен дождь именно этого дня, погода весит больше надёжности
function hikeDay(d){
  const fav=(HFAV[d.hil_level]??0.04);
  return {lvl:hikeLevel(hikeScore(fav, confLevel(d,d.n_models), 0.62))};
}
// с ночёвкой: экспозиция на день D и день D+1 (риск мокрого лагеря). Считаем по
// ХУДШЕМУ из двух дней — благоприятность min, надёжность по худшему дню. Так
// ночёвка никогда не выходит «лучше» однодневки и ухудшается, только когда
// завтра хуже сегодня. Если D+1 за горизонтом — по D, но уверенность −1 (partial).
function hikeNight(d,nx){
  const favD=(HFAV[d.hil_level]??0.04);
  let fav,rl,partial=false;
  if(nx){
    fav=Math.min(favD,(HFAV[nx.hil_level]??0.04));
    rl=Math.max(confLevel(d,d.n_models),confLevel(nx,nx.n_models));
  }else{
    fav=favD; rl=Math.min(3,confLevel(d,d.n_models)+1); partial=true;
  }
  return {lvl:hikeLevel(hikeScore(fav, rl, 0.62)), partial};
}
// крупный блок-ответ «идти в горы?» для выбранного дня (по умолчанию — сегодня)
function hikeHero(days){
  if(!days.length) return '';
  const d0=days[0], hd=hikeDay(d0), hn=hikeNight(d0,days[1]);
  const cell=(emoji,mode,v)=>`<div class="hbig"><div class="m">${emoji} ${mode}</div>
    <div class="v"><i class="dd ${CB[v.lvl]}"></i><span class="${GC[v.lvl]}">${HW[v.lvl]}</span></div></div>`;
  return `<div class="hero"><h4>Идти в горы? <span class="tiny" style="font-weight:400">— ${wd(d0.day)} ${dm(d0.day)}</span></h4>
    <div class="hero-badges">${cell('🥾','однодневный',hd)}${cell('🏕','с ночёвкой',hn)}</div>
    <div class="note" style="margin-top:10px">Единый индикатор из трёх факторов: <b>критичность осадков</b> (HIL), <b>надёжность</b> прогноза и <b>разброс</b> моделей. Режим «с ночёвкой» смотрит на сегодня и завтра (риск мокрого лагеря). Это операционная подсказка, а не гарантия.</div></div>`;
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

// ── Модалка «какие это модели» ───────────────────────────────────────────────
// Веса и состав приходят из домена (/api/models, реестр §8.2) — здесь только
// пользовательские пояснения, что это за модель и чем она полезна.
const MODEL_DESC={
  ifs:'Европейский центр среднесрочных прогнозов (Рединг). Эталон среднесрочного прогноза: обычно точнее всех на 2–7 суток, поэтому вес наибольший.',
  icon:'Немецкая метеослужба. Мелкий шаг сетки и хорошая работа с рельефом — ценна для гор и ближних суток.',
  gfs:'Американская глобальная модель. Обновляется часто и даёт независимый от европейской школы взгляд; на осадки в горах бывает щедра.',
  gem:'Канадская глобальная модель. Своя физика и своя школа — расходится с европейскими не случайно, а по делу: именно это и делает разброс честным.',
  arpege:'Французская модель. Сильна по Средиземноморью и югу Европы; горизонт короче остальных, отсюда меньший вес.'};
let MODAL=null;
function closeModal(){ if(MODAL){ MODAL.remove(); MODAL=null; } }
function openSheet(html){
  closeModal();
  const el=document.createElement('div'); el.className='modal';
  el.innerHTML=`<div class="sheet" role="dialog" aria-modal="true">${html}</div>`;
  el.addEventListener('click',e=>{ if(e.target===el||e.target.closest('[data-close]')) closeModal(); });
  document.body.appendChild(el); MODAL=el;
  return el.querySelector('.sheet');
}
document.addEventListener('keydown',e=>{ if(e.key==='Escape') closeModal(); });
const SHEET_HD=`<div class="sheet-hd"><h4>🛰 Модели консенсуса</h4>
  <button class="x" data-close aria-label="Закрыть">✕</button></div>`;
async function showModels(n){
  const sheet=openSheet(SHEET_HD+'<div class="skel"></div>');
  try{
    if(!CACHE.models) CACHE.models=(await api('/api/models')).models;
    const ms=CACHE.models;
    const rows=ms.map(m=>`<div class="mrow">
      <div class="mtop"><b>${m.name}</b><span class="tiny">${m.center} · вес ${m.weight.toFixed(2)}</span></div>
      <div class="wbar"><i style="width:${Math.round(m.weight*100)}%"></i></div>
      <div class="mtxt">${MODEL_DESC[m.id]||''}</div></div>`).join('');
    const miss=(n&&n<ms.length)
      ? `<div class="note">В текущем расчёте <b>${n} из ${ms.length}</b>: остальные не дали данных на этот прогон (или день за их горизонтом выпуска). Надёжность при этом автоматически снижается.</div>` : '';
    sheet.innerHTML=`${SHEET_HD}
      <div class="mtxt" style="margin-bottom:2px">Прогноз — не одна модель, а ${ms.length} независимых:
      их считают разные метеоцентры по разной физике. Мы берём все ${ms.length} и сводим во
      взвешенные перцентили (p10 / p50 / p90) — каждая модель учитывается ровно один раз.</div>
      ${rows}${miss}
      <div class="note">Вес — насколько модели верим сейчас. Веса стартовые, по репутации моделей;
      пересчёт по фактической точности на истории (Accuracy Engine) — следующая фаза.</div>`;
  }catch(e){ sheet.innerHTML=SHEET_HD+'<div class="note">Не удалось загрузить состав моделей.</div>'; }
}

document.getElementById('seg').addEventListener('click',e=>{
  const b=e.target.closest('button'); if(!b) return;
  [...e.currentTarget.children].forEach(x=>x.classList.toggle('on',x===b));
  if(b.dataset.t==='home') loadHome(); else loadCompare();
});

async function api(u){const r=await fetch(u); if(!r.ok) throw new Error(r.status); return r.json();}

async function loadHome(){
  closeModal();
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
  const W=300,H=132,pad=16,base=H-22,top=18;
  const mx=Math.max(6,...days.map(d=>d.p90));
  const fmx=sq(mx);
  const bw=(W-2*pad)/days.length;
  const y=v=>base-(sq(v)/fmx)*(base-top);
  // засечки шкалы (мм) — бледные линии с подписью у правого края
  const ticks=[1,2,5,10,20,40,80].filter(t=>t<=mx);
  let grid=ticks.map(t=>`<line x1="${pad}" y1="${y(t)}" x2="${W-pad}" y2="${y(t)}" stroke="var(--hair)" stroke-width="0.6"></line>
    <text x="${W-pad+2}" y="${y(t)+2.5}" font-size="7" fill="var(--ink3)">${t}</text>`).join('');
  grid+=`<text x="${W-pad+2}" y="${top-6}" font-size="7" fill="var(--ink3)">мм</text>`;
  let peak=0; days.forEach((d,i)=>{ if(d.p50>days[peak].p50) peak=i; });
  let bars='',wsk='',lbl='',xl='';
  days.forEach((d,i)=>{
    const x=pad+i*bw+bw/2;
    const bh=base-y(d.p50);
    bars+=`<rect x="${x-bw*0.28}" y="${y(d.p50)}" width="${bw*0.56}" height="${Math.max(1,bh)}" rx="2" fill="var(--precip)"></rect>`;
    wsk+=`<line x1="${x}" y1="${y(d.p10)}" x2="${x}" y2="${y(d.p90)}" stroke="var(--ink3)" stroke-width="1.4"></line>
      <line x1="${x-3}" y1="${y(d.p90)}" x2="${x+3}" y2="${y(d.p90)}" stroke="var(--ink3)" stroke-width="1.4"></line>`;
    // подписи — только пик и дни со значимым дождём (≥1 мм); сухие не подписываем
    if(i===peak || Math.round(d.p50)>=1){
      const lx=Math.min(W-11,Math.max(11,x));
      lbl+=`<text x="${lx}" y="${Math.max(8,y(d.p50)-3)}" font-size="7.5" fill="var(--ink)" text-anchor="middle" style="font-variant-numeric:tabular-nums">${g(d.p50)}</text>`;
    }
    xl+=`<text x="${x}" y="${H-6}" font-size="8.5" fill="var(--ink3)" text-anchor="middle">${wd(d.day)}</text>`;
  });
  return `<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Осадки по дням, √-шкала">
    ${grid}
    <line x1="${pad}" y1="${base}" x2="${W-pad}" y2="${base}" stroke="var(--hair2)"></line>
    ${bars}${wsk}${lbl}${xl}</svg>
    <div class="cl"><span><i class="sw" style="background:var(--precip)"></i>p50, мм/сут · √-шкала</span>
    <span><i class="sw" style="background:var(--ink3)"></i>разброс: в лучшем → в худшем случае</span></div></div>`;
}

function relBlock(d){
  const idx=[[0,'1 день'],[2,'3 дня'],[6,'7 дней'],[13,'14 дней']];
  const chips=idx.filter(x=>d.days[x[0]]).map(([i,lab])=>{
    const dd=d.days[i], lvl=confLevel(dd,dd.n_models);
    return `<div class="relchip"><div class="h">${lab.toUpperCase()}</div>
      <div class="dot ${CB[lvl]}"></div><div class="w ${GC[lvl]}">${CW[lvl]}</div>
      <div class="relchip-n">${dd.n_models}/5 моделей</div></div>`;
  }).join('');
  const n=d.days[0]?d.days[0].n_models:d.n_models;
  const far=d.days[d.days.length-1];
  const nf=far?far.n_models:n;
  const cover=nf<n ? `Моделей в расчёте: <b>${n}/5</b> (к концу горизонта <b>${nf}/5</b>)`
                   : `Моделей в расчёте: <b>${n}/5</b>`;
  const d3=d.days[2]||d.days[d.days.length-1];
  const spread=d3?(d3.p90-d3.p10):0;
  const sw=spread<3?'узкий':spread<12?'умеренный':'широкий';
  return `<div class="rel"><h4>📊 Надёжность <span class="tiny" style="font-weight:400">— предварительно</span></h4>
    <div class="relrow">${chips}</div>
    <div class="relmeta">${cover} · согласованность на 3-й день: <b>${sw}</b> разброс (${g(spread)} мм).
    Чем шире разрыв «в лучшем — в худшем случае» (p10–p90), тем ниже надёжность.
    <button class="lnk" onclick="showModels(${n})">какие это модели?</button></div>
    <details class="rel-how"><summary>Как считается надёжность</summary>
      <div class="body">
        Один и тот же день считают до <b>5 независимых метеомоделей</b>. Надёжность — это
        насколько они <b>согласны между собой</b>: чем меньше разрыв «в лучшем — в худшем
        случае» (p10–p90) относительно медианы, тем выше надёжность. На дальних днях
        моделей в расчёте меньше — оценка автоматически снижается.
        ${CW.map((w,i)=>`<div class="rel-lv"><i class="${CB[i]}"></i><span><b class="${GC[i]}">${w}</b> — ${LVL_DESC[i]}</span></div>`).join('')}
        <div style="margin-top:7px;color:var(--ink3)">Это оценка <b>по разбросу моделей</b>
        (предварительно). Калиброванный скор — совпадение прогноза с фактом на истории —
        появится в Фазе 2.</div>
      </div></details></div>`;
}

async function loadForecast(id){
  closeModal();
  view.innerHTML='<div class="skel"></div><div class="skel"></div>';
  if(tg&&tg.BackButton){tg.BackButton.show();tg.BackButton.onClick(loadHome);}
  try{
    const d=await api('/api/forecast?location='+encodeURIComponent(id));
    const upd=new Date(d.computed_at);
    const leg=`<div class="dayleg">
      <span>🥾 день · 🏕 ночёвка — <b>вердикт: стоит ли идти</b></span>
      <span>в скобках — от <b>меньшего</b> дождя к <b>большему</b> (p10–p90)</span></div>`;
    const rows=d.days.map((x,i)=>{
      const hd=hikeDay(x), hn=hikeNight(x, d.days[i+1]);
      return `<div class="day">
      <div class="dt">${dm(x.day)}<small>${wd(x.day)}</small></div>
      <div class="ic">${HIL_IC[x.hil_level]}</div>
      <div class="bw">
        <div class="verdict">
          <span class="vd">🥾 <b class="${GC[hd.lvl]}">${HW[hd.lvl]}</b><em>день</em></span>
          <span class="vd">🏕 <b class="${GC[hn.lvl]}">${HW[hn.lvl]}</b><em>ночёвка${hn.partial?'*':''}</em></span>
        </div>
        <div class="daypop">вероятность дождя <b>${Math.round(x.pop*100)}%</b></div>
        <div class="daymeta"><b>${g(x.p50)}</b> (${g(x.p10)}–${g(x.p90)}) мм · ${x.hil_label}</div>
        ${band(x)}
      </div></div>`;
    }).join('');
    view.innerHTML=`<button class="back" onclick="loadHome()">‹ Все точки</button>
      <div class="dhead"><div class="loc">${d.location.name}</div><div class="tiny">${d.location.elevation_m} м</div></div>
      <div class="row" style="margin:0 2px 10px">
        <button class="pill ok" onclick="showModels(${d.n_models})">🛰 ${d.n_models} ${modelsWord(d.n_models)} ⓘ</button>
        <span class="tiny">обновлено ${String(upd.getHours()).padStart(2,'0')}:${String(upd.getMinutes()).padStart(2,'0')}</span></div>
      <section id="secHourly">${H_HOURLY}<div class="skel"></div></section>
      ${hikeHero(d.days)}${weeklyChart(d.days)}${relBlock(d)}<div class="days">${leg}${rows}
      <div class="tiny" style="padding:8px 2px 4px;line-height:1.4">* у последнего дня прогноза на следующие сутки ещё нет — оценка «с ночёвкой» предварительна.</div></div>
      <section id="secHistory">${H_HIST}<div class="skel"></div></section>`;
    hydrateHourly(id); hydrateHistory(id);
  }catch(e){view.innerHTML='<div class="state">Прогноз ещё не рассчитан.</div>'}
}

// метка времени Open-Meteo — наивный ISO в UTC; '+Z' даёт верный момент,
// дальше показываем в часовом поясе пользователя (а не в UTC — «непонятная дата»)
function tsLocal(iso){return new Date(iso+'Z')}
function hhmm(d){return String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')}
function dmt(d){return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')}
function hourlyChart(h){
    const n=h.times.length;
    if(!n) return `<div class="note">Нет часовых данных на ближайшие 48 ч.</div>`;
    const W=320,H=170,padL=6,padR=6,base=H-30,top=14;
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
    // сетка и подписи каждые 6 ч — в местном времени; на смене суток подписываем дату
    let grid='',xl='',dl='';
    for(let i=0;i<n;i+=6){
      const t=tsLocal(h.times[i]);
      grid+=`<line x1="${sx(i)}" y1="${top}" x2="${sx(i)}" y2="${base}" stroke="var(--hair)" stroke-width="0.5"></line>`;
      xl+=`<text x="${sx(i)}" y="${H-14}" font-size="8" fill="var(--ink3)" text-anchor="middle">${String(t.getHours()).padStart(2,'0')}</text>`;
      const prev=i?tsLocal(h.times[i-6]):null;
      if(!prev||prev.getDate()!==t.getDate())
        dl+=`<text x="${Math.min(W-14,Math.max(14,sx(i)))}" y="${H-4}" font-size="7.5" fill="var(--ink3)" text-anchor="middle">${dmt(t)}</text>`;
    }
    // отсчёт идёт от текущего часа: помечаем начало оси, чтобы «48 ч» читались буквально
    const t0=tsLocal(h.times[0]), t1=tsLocal(h.times[n-1]);
    const nowMark=`<line x1="${padL}" y1="${top-4}" x2="${padL}" y2="${base}" stroke="var(--accent)" stroke-width="1"></line>
      <text x="${padL+3}" y="${top-5}" font-size="7.5" fill="var(--accent)">сейчас</text>`;
    const svg=`<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Метеограмма на 48 часов вперёд">
      ${dry}${grid}<line x1="${padL}" y1="${base}" x2="${W-padR}" y2="${base}" stroke="var(--hair2)"></line>
      ${band}${line}${popl}${nowMark}${xl}${dl}
      <text x="${W-padR}" y="10" font-size="8" fill="var(--ink3)" text-anchor="end">осадки, мм/ч</text></svg>
      <div class="cl"><span><i class="sw" style="background:var(--precip)"></i>p50 + разброс</span>
      <span><i class="sw" style="background:var(--accent)"></i>вероятность</span>
      <span><i class="sw" style="background:color-mix(in srgb,var(--g) 40%,transparent)"></i>сухо</span></div></div>`;
    // окно и сухое окно — в часах от «сейчас»
    let firstWet=h.p50.findIndex(v=>v>=0.3);
    const dryHrs = firstWet<0 ? n : firstWet;
    const summary = dryHrs>0
      ? `Сухое окно: ближайшие <b>${dryHrs} ч</b>.`
      : `Осадки уже идут.`;
    const range=`<div class="tiny" style="margin:-2px 2px 8px">от <b>${dmt(t0)} ${hhmm(t0)}</b> до <b>${dmt(t1)} ${hhmm(t1)}</b> · ${n} ч · местное время</div>`;
    return `${range}${svg}
      <div class="note" style="margin-top:10px">${summary} Пунктир — вероятность осадков, полоса — разброс от лучшего к худшему случаю по моделям (p10–p90).</div>`;
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
  // green (dry) -> amber -> orange -> red (downpour)
  const t=Math.min(v,mx)/(mx||1);
  const stops=['var(--g)','var(--a)','var(--o)','var(--r)'];
  const seg=t*(stops.length-1), i=Math.min(Math.floor(seg),stops.length-2);
  const f=Math.round((seg-i)*100);
  return `color-mix(in srgb,${stops[i+1]} ${f}%,${stops[i]})`;
}
function historyHeatmap(h){
    const n=h.issues.length;
    if(!n) return `<div class="note">История пуста — накопится за несколько циклов (каждые 4 ч).</div>`;
    const gtc=`grid-template-columns:repeat(${n},1fr)`;
    // Нормировка ПО СТРОКЕ (дню), а не по глобальному максимуму: цвет показывает
    // эволюцию прогноза именно для этой даты, и один ливневый день не «засвечивает»
    // остальные. FLOOR — дно шкалы, чтобы сухие строки не краснели от миллиметрового шума.
    const FLOOR=6;
    const body=h.rows.map(r=>{
      const rmax=Math.max(FLOOR,...r.vals.filter(v=>v!=null));
      const cells=r.vals.map(v=>`<i style="background:${heatColor(v,rmax)}" title="${v==null?'—':Math.round(v*10)/10+' мм'}"></i>`).join('');
      return `<div class="hmrow"><span class="yl">${dm(r.date)}</span><div class="cells" style="${gtc}">${cells}</div></div>`;
    }).join('');
    const fmtIssue=iso=>{const d=new Date(iso);return String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')+' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')};
    return `<div class="muted" style="font-size:11px;margin:0 2px 10px">Строки — прогнозируемая дата, столбцы — момент выпуска прогноза (${n}). Цвет — осадки p50 относительно этого же дня: у каждой строки своя шкала, чтобы видеть, как менялся прогноз именно на эту дату.</div>
      <div class="hm">${body}<div class="hm-x"><span>${fmtIssue(h.issues[0])}</span><span>${n>1?fmtIssue(h.issues[n-1]):''} →</span></div>
        <div class="scale"><span>меньше</span><div class="grad"></div><span>больше</span></div></div>
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
  closeModal();
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
