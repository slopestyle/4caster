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
    --p0:#dbeafb; --p1:#b6d2f1; --p2:#8fb4e3; --p3:#6b96d1; --p4:#4d78b9; --p5:#33619f;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 26px rgba(0,0,0,.5);
  }
  @media (prefers-color-scheme:light){:root{
    --bg:#eceef1; --surface:#ffffff; --surface2:#f4f5f7; --surface3:#e8eaee;
    --ink:#161719; --ink2:#565c68; --ink3:#828996; --hair:#e2e5ea; --hair2:#d1d6de;
    --brand:#e85a26; --brand-ink:#c74a1c; --brand-wash:#ffe9df;
    --accent:#e85a26; --precip:#3f74b8;
    --g:#2f9e6a; --a:#bf8c18; --o:#e8632a; --r:#dc4433;
    --p0:#93bbe0; --p1:#75a5d5; --p2:#5a8cc4; --p3:#4272aa; --p4:#2c588c; --p5:#183f6d;
    --shadow:0 1px 2px rgba(20,25,35,.06),0 6px 18px rgba(20,25,35,.10);
  }}
  :root[data-theme="dark"]{
    --bg:#141516; --surface:#1e2024; --surface2:#26292f; --surface3:#323841;
    --ink:#f4f5f7; --ink2:#a7adb8; --ink3:#767d89; --hair:#333841; --hair2:#414852;
    --brand:#ff6b35; --brand-ink:#ff8a5c; --brand-wash:#3a2116;
    --accent:#ff6b35; --precip:#6f9bd0;
    --g:#4bbf7f; --a:#e0b13e; --o:#f0783a; --r:#ec5648;
    --p0:#dbeafb; --p1:#b6d2f1; --p2:#8fb4e3; --p3:#6b96d1; --p4:#4d78b9; --p5:#33619f;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 10px 26px rgba(0,0,0,.5);
  }
  :root[data-theme="light"]{
    --bg:#eceef1; --surface:#ffffff; --surface2:#f4f5f7; --surface3:#e8eaee;
    --ink:#161719; --ink2:#565c68; --ink3:#828996; --hair:#e2e5ea; --hair2:#d1d6de;
    --brand:#e85a26; --brand-ink:#c74a1c; --brand-wash:#ffe9df;
    --accent:#e85a26; --precip:#3f74b8;
    --g:#2f9e6a; --a:#bf8c18; --o:#e8632a; --r:#dc4433;
    --p0:#93bbe0; --p1:#75a5d5; --p2:#5a8cc4; --p3:#4272aa; --p4:#2c588c; --p5:#183f6d;
    --shadow:0 1px 2px rgba(20,25,35,.06),0 6px 18px rgba(20,25,35,.10);
  }
  /* тень — только у карточек верхнего уровня; .days теперь живёт внутри .blk,
     и её тень рисовалась тёмным прямоугольником поверх подложки блока */
  .card,.blk,.rel,.cmp,.hero{box-shadow:var(--shadow)}
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
  .pill.stale{color:var(--a);background:color-mix(in srgb,var(--a) 16%,var(--surface3))}

  /* поиск по каталогу + легенда под «?» */
  .tools{display:flex;gap:8px;margin-bottom:10px}
  .srch{flex:1;min-width:0;background:var(--surface2);border:1px solid var(--hair);border-radius:12px;
    color:var(--ink);font:inherit;font-size:14px;padding:9px 12px;-webkit-appearance:none}
  .srch::placeholder{color:var(--ink3)}
  .srch:focus{outline:none;border-color:var(--brand)}
  .qmark{flex:none;width:38px;background:var(--surface2);border:1px solid var(--hair);border-radius:12px;
    color:var(--ink2);font:inherit;font-size:15px;font-weight:700;cursor:pointer}
  .qmark:active{background:var(--surface3)}
  .grp{display:flex;justify-content:space-between;align-items:baseline;gap:8px;margin:16px 2px 8px;
    font-size:11px;font-weight:700;color:var(--ink2);text-transform:uppercase;letter-spacing:.05em}
  .grp:first-child{margin-top:2px}
  .grp b{color:var(--ink3);font-weight:600;letter-spacing:0;text-transform:none;font-size:11px}
  .legrow{display:flex;align-items:center;gap:9px;font-size:12px;color:var(--ink2);
    padding:7px 0;border-top:1px solid var(--hair)}
  .legrow b{color:var(--ink)}

  .dhead{display:flex;justify-content:space-between;align-items:baseline;margin:4px 2px 12px}
  .dhead .loc{font-size:20px;font-weight:750;letter-spacing:-.01em}

  /* блок-подложка: единая карточка для всех виджетов экрана прогноза —
     заголовок, содержимое и пояснение живут на одной поверхности */
  .blk{background:var(--surface);border:1px solid var(--hair);border-radius:16px;
    padding:13px 14px;margin-bottom:10px}
  .blk>h4{margin:0 0 8px;font-size:14px;display:flex;align-items:baseline;gap:7px;flex-wrap:wrap}
  .blk>h4 .tiny{font-weight:400}
  .blk .skel{margin:0}
  .story{font-size:12px;color:var(--ink2);line-height:1.5;margin-bottom:4px}
  .story b{color:var(--ink)}
  /* графики: сам SVG без собственной подложки — её даёт .blk */
  .chart{margin-top:8px}
  .chart svg{display:block;width:100%;height:auto}
  .chart .cl{display:flex;gap:12px;font-size:9.5px;color:var(--ink2);padding:6px 2px 0;flex-wrap:wrap}
  .chart .cl span{display:inline-flex;gap:5px;align-items:center}
  .sw{width:10px;height:10px;border-radius:3px;display:inline-block}

  .days{margin:0}
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
  .rng{position:absolute;top:0;bottom:0;border-radius:4px;background:var(--brand)}
  .p50{position:absolute;top:0;bottom:0;width:2px;border-radius:1px;background:var(--ink)}
  /* надёжность у полосы разброса — что она и оценивает */
  .rel-inline{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;font-weight:600}
  .rel-inline .dd{width:9px;height:9px}
  .pop{font-size:14px;color:var(--ink);font-weight:700;font-variant-numeric:tabular-nums;
    display:flex;flex-direction:column;align-items:flex-end;gap:1px;line-height:1.1}
  .pop .lbl{font-size:8.5px;color:var(--ink3);font-weight:600}
  .dd{width:8px;height:8px;border-radius:50%}
  /* multi-day strip on location cards */
  .strip{display:grid;grid-template-columns:repeat(7,1fr);gap:4px;margin-top:11px}
  .dcell{text-align:center;padding:5px 0 4px;border-radius:9px;background:var(--surface2)}
  .dcell.dry{background:var(--brand-wash);outline:1px solid var(--brand)}
  .dcell .wd{font-size:9px;color:var(--ink3);font-weight:700}
  .dcell .di{font-size:15px;line-height:1.3}
  .dcell .marks{display:flex;gap:3px;justify-content:center;margin-top:3px}
  .sq{width:8px;height:8px;border-radius:2px;display:inline-block}
  .dcell .mm{font-size:8.5px;color:var(--ink3);font-variant-numeric:tabular-nums}
  .hint{font-size:10.5px;color:var(--ink3);margin:0 2px 10px;display:flex;gap:12px;flex-wrap:wrap}
  .hint span{display:inline-flex;gap:5px;align-items:center}

  /* reliability (spread-based, qualitative) */
  .rel{background:var(--surface);border:1px solid var(--hair);border-radius:16px;padding:13px 14px;margin-bottom:10px}
  .rel h4{margin:0 0 10px;font-size:14px}
  .relrow{display:flex;gap:8px;margin-bottom:10px}
  .relchip{flex:1;text-align:center;background:var(--surface2);border:1px solid var(--hair);border-radius:11px;
    padding:9px 4px;font:inherit;color:inherit;cursor:pointer}
  .relchip:active{background:var(--surface3)}
  .relnums{display:grid;grid-template-columns:1fr 1fr;gap:5px 12px;margin:11px 0 3px;font-size:11.5px}
  .relnums div{display:flex;justify-content:space-between;gap:8px;align-items:baseline;
    border-bottom:1px solid var(--hair);padding-bottom:4px}
  .relnums span{color:var(--ink2)} .relnums b{font-variant-numeric:tabular-nums;white-space:nowrap}
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
  .hm{margin-top:10px}
  .hmrow{display:grid;grid-template-columns:54px 1fr;gap:6px;align-items:center;margin-bottom:2px}
  .hm .yl{font-size:9.5px;color:var(--ink3);font-weight:600;text-align:right;white-space:nowrap}
  .hm .yl b{color:var(--ink2);font-weight:700}
  .hm .cells{display:grid;gap:2px}
  /* фиксированная высота, а не квадрат: при 3–6 столбцах aspect-ratio:1 раздувал
     ячейки до ~70 px и виджет переставал влезать в экран */
  .hm .cells i{height:12px;border-radius:3px}
  .hm .cells i.nd{background:repeating-linear-gradient(45deg,
    var(--hair2) 0 2px,transparent 2px 5px) !important}
  /* подписи столбцов — вертикально: горизонтально таймстемп не влезает в колонку
     шириной ~15–40 px, а подписать нужно каждый выпуск */
  .hm-hd{align-items:end}
  .hm-hd span{writing-mode:vertical-rl;transform:rotate(180deg);font-size:8px;line-height:1;
    color:var(--ink3);white-space:nowrap;font-variant-numeric:tabular-nums;
    justify-self:center;padding-bottom:3px}
  .hm-hd span.last{color:var(--brand);font-weight:700}
  .scale{display:flex;align-items:center;gap:7px;font-size:9.5px;color:var(--ink2);margin-top:10px}
  .scale .grad{flex:1;height:7px;border-radius:4px;
    background:linear-gradient(90deg,var(--p0),var(--p2),var(--p3),var(--p4),var(--p5))}
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
// Шкала осадков — один синий тон: светлое = сухо, тёмное = дождь (в обеих темах).
// Проверена валидатором палитры: монотонная светлота, различима при CVD; тёмный
// конец в тёмной теме держит контраст 2.6:1 к подложке, чтобы ливень не исчезал.
// Зелёный/жёлтый/красный оставлены статусам (надёжность, вердикт), чтобы один
// цвет не значил в соседних блоках то «сухо», то «надёжно».
const PC=['var(--p0)','var(--p1)','var(--p2)','var(--p3)','var(--p4)','var(--p5)'];
const HIL_W=['сухо','морось','слабый','дождь','сильный','ливень'];
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
const H_HOURLY='<h4>🕐 Осадки · ближайшие 48 часов</h4>';
const H_HIST='<h4>📅 Как менялся прогноз</h4>';
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
// Качественная надёжность по относительному разбросу моделей + согласию.
// ВАЖНО: относительный разброс на малых суммах взрывается (0 против 2 мм — это
// «в два раза», хотя для похода разницы нет), поэтому сначала смотрим абсолютную
// разницу сценариев: пока весь разброс умещается в одну операционную категорию,
// модели по сути согласны, и надёжность не занижаем.
// Границы категорий осадков (те же, что у HIL на сервере): сухо / морось /
// слабый / дождь / сильный / ливень.
const HIL_MM=[0.5,2,6,15,30];
const hilOf=v=>{let i=0; while(i<HIL_MM.length && v>=HIL_MM[i]) i++; return i;};
// Ключевой вопрос надёжности — не «на сколько процентов разошлись модели», а
// «меняет ли этот разброс сам ответ». Поэтому сначала прогоняем лучший и худший
// сценарии через вердикт хайкабельности: 0.4 мм против 2.1 мм формально
// «в пять раз», но ответ в обоих случаях один. Относительный разброс включается
// только тогда, когда сценарии реально ведут к разным решениям.
const verdictAt=mm=>hikeLevel(HFAV[hilOf(mm)]);
// Надёжность считает домен (§10.6: согласие моделей, разброс ансамблей,
// устойчивость по истории прогонов) и кладёт в карточку — Mini App её только
// показывает (FR-TG-7). Оценка ниже остаётся запасной: карточки, записанные до
// появления модуля надёжности, поля не имеют, и без запасного пути экран
// сломался бы до первого прогона конвейера.
function confLevel(d,n){
  if(d.reliability && typeof d.reliability.level==='number') return d.reliability.level;
  const vlo=verdictAt(d.p10), vhi=verdictAt(d.p90), gap=vhi-vlo;
  const rel=(d.p90-d.p10)/Math.max(d.p50,2);
  let lvl = rel<0.35?0 : rel<0.8?1 : rel<1.4?2 : 3;
  if(gap<=0) lvl=0;                        // ответ от разброса не меняется
  else if(gap===1) lvl=Math.min(lvl,1);    // меняется на один шаг
  if(n<4) lvl=Math.min(3,lvl+1);
  return lvl;
}
// разбор конкретного дня для поп-апа: откуда взялся именно этот вердикт
function relWhy(d){
  const abs=d.p90-d.p10, rel=abs/Math.max(d.p50,2), lvl=confLevel(d,d.n_models);
  const nm=i=>['сухо','морось','слабый дождь','дождь','сильный дождь','ливень'][i];
  const vlo=verdictAt(d.p10), vhi=verdictAt(d.p90);
  const lo=`${nm(hilOf(d.p10))}, ${g(d.p10)} мм`, hi=`${nm(hilOf(d.p90))}, ${g(d.p90)} мм`;
  const why = vhi<=vlo
    ? `Модели расходятся, но ответ от этого не меняется: и в лучшем сценарии (${lo}), и в худшем (${hi}) вердикт один — <b>${HW[vlo]}</b>. Спорить не о чем.`
    : vhi-vlo===1
      ? `В лучшем сценарии (${lo}) вердикт <b>${HW[vlo]}</b>, в худшем (${hi}) — <b>${HW[vhi]}</b>. Разброс сдвигает решение на один шаг: идти можно, но с запасом и с пересмотром ближе к дате.`
      : `В лучшем сценарии (${lo}) вердикт <b>${HW[vlo]}</b>, в худшем (${hi}) — <b>${HW[vhi]}</b>. Это разные дни и разные решения — на такой прогноз опираться нельзя, надо ждать сближения моделей.`;
  const cover = d.n_models>=5
    ? `Считали <b>все 5 моделей</b> — дело не в нехватке данных, а в том, насколько модели сошлись.`
    : `В расчёте <b>${d.n_models} из 5</b> моделей — оценка дополнительно снижена на один шаг.`;
  return {lvl,abs,rel,why,cover};
}
// Разбор надёжности, посчитанной на сервере: три компоненты §10.6 словами.
function relParts(r){
  const pct=v=>Math.round(v*100)+'%';
  return `<div class="relnums">
      <div><span>согласие моделей</span><b>${pct(r.agreement)}</b></div>
      <div><span>разброс ансамблей</span><b>${r.ensemble_is_proxy?'нет данных':pct(r.ensemble)}</b></div>
      <div><span>устойчивость прогноза</span><b>${r.stability==null?'мало истории':pct(r.stability)}</b></div>
      <div><span>сценариев в расчёте</span><b>${r.n_members}</b></div>
    </div>
    <div class="note">Надёжность складывается из трёх ответов. <b>Согласие моделей</b> —
    говорят ли независимые прогнозы одно и то же (и в миллиметрах, и по категории:
    12 против 18 мм — это согласие, 0,1 против 2,5 — уже нет). <b>Разброс ансамблей</b> —
    насколько разошлись ${r.n_members} сценариев одной и той же модели, запущенных с чуть
    разными начальными данными${r.ensemble_is_proxy?'; на этот день ансамбли не ответили, и оценка снижена':''}.
    <b>Устойчивость</b> — не скачет ли прогноз на эту дату от прогона к прогону: плавный
    тренд это норма, качели вверх-вниз — нет${r.stability==null?' (истории на эту дату пока мало)':''}.
    Провал по любому из трёх обрушивает итог — иначе высокое согласие маскировало бы качели.</div>
    <div class="note">Шкала качественная, а не в баллах: сверка прогнозов с фактом
    (калибровка) ещё не накоплена, а показывать некалиброванное число — значит выдавать
    точность, которой нет.</div>`;
}
function showReliability(iso){
  const d=(CACHE.fc&&CACHE.fc.days||[]).find(x=>x.day===iso); if(!d) return;
  const w=relWhy(d), r=d.reliability;
  openSheet(`<div class="sheet-hd"><h4>📊 Надёжность · ${wd(d.day)} ${dm(d.day)}</h4>
    <button class="x" data-close aria-label="Закрыть">✕</button></div>
    <div class="mtop" style="margin:2px 0 8px"><b class="${GC[w.lvl]}">${CW[w.lvl]}</b>
      <span class="tiny">${LVL_DESC[w.lvl]}</span></div>
    <div class="mtxt">${w.why} ${w.cover}</div>
    <div class="relnums">
      <div><span>минимум (сухой сценарий)</span><b>${g(d.p10)} мм</b></div>
      <div><span>скорее всего</span><b>${g(d.p50)} мм</b></div>
      <div><span>максимум (мокрый сценарий)</span><b>${g(d.p90)} мм</b></div>
      <div><span>вероятность осадков</span><b>${Math.round(d.pop*100)}%</b></div>
      <div><span>моделей в расчёте</span><b>${d.n_models}/5</b></div>
      <div><span>разница «от» и «до»</span><b>${g(w.abs)} мм</b></div>
    </div>` + (r ? relParts(r) : `
    <div class="note">Считаем так: сначала прогоняем <b>лучший и худший сценарии</b> через тот же
    вердикт, что и на карточке дня. Ответ не меняется — надёжность высокая, даже если в
    процентах разброс большой (0,4 против 2 мм — «в пять раз», а идти всё равно можно).
    Меняется на один шаг — не хуже «осторожно». Меняется сильнее — смотрим, насколько
    разрыв «от и до» велик рядом с самим числом: сейчас ${g(w.rel*100)}% (до 80% — осторожно, до 140% —
    низкая, выше — не опираться). Меньше 4 моделей в расчёте — минус ещё шаг.</div>
    <div class="note">Это оценка <b>по согласию моделей</b>, а не по их прошлой точности:
    калиброванный скор (сверка прогноза с фактом на истории) — следующая фаза.</div>`));
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
// горизонт прогноза концом периода: после отсечения вчерашнего дня счётчик дней
// «сам собой» уменьшался (14 → 13) и читался как потеря данных
function horizon(firstDay,total){
  if(!total) return 'нет данных';
  const end=new Date(firstDay+'T00:00:00'); end.setDate(end.getDate()+total-1);
  return `по ${dmt(end)}`;
}
function dayStrip(days){
  if(!days.length) return '';
  const up=days.slice(0,7);
  let driest=-1, best=1e9;
  up.forEach((d,i)=>{ if(i>0 && d.p50<best){ best=d.p50; driest=i; } });
  const cells=up.map((d,i)=>{
    const hv=hikeDay(d).lvl;                       // однодневный выход
    const hn=hikeNight(d,days[i+1]).lvl;           // с ночёвкой (учитывает следующий день)
    const dry=(i===driest && best<2);
    return `<div class="dcell ${dry?'dry':''}" title="${wd(d.day)} ${dm(d.day)} · ${g(d.p50)} мм · днём: ${HW[hv]} · с ночёвкой: ${HW[hn]}">
      <div class="wd">${wd(d.day)}</div>
      <div class="di">${HIL_IC[d.hil_level]}</div><div class="mm">${g(d.p50)}</div>
      <div class="marks"><i class="dd ${CB[hv]}"></i><i class="sq ${CB[hn]}"></i></div></div>`;
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
      один ответ: «скорее всего столько» и рамки «от и до» — каждая модель учитывается ровно один раз.</div>
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

// Легенда переехала в поп-ап под «?»: на главной с двумя десятками точек
// три строки подписей съедали первый экран.
function showLegend(){
  const row=(mark,txt)=>`<div class="legrow">${mark}<span>${txt}</span></div>`;
  openSheet(`<div class="sheet-hd"><h4>❓ Что на карточке точки</h4>
    <button class="x" data-close aria-label="Закрыть">✕</button></div>
    <div class="mtxt">Под каждым днём — два ответа на вопрос «идти или нет»: кружок для
    однодневного выхода и квадрат для выхода с ночёвкой (он смотрит ещё и на следующий день).</div>
    ${row('<i class="dd bg-g"></i><i class="sq bg-g"></i>','<b>идти</b> — осадки походу не мешают')}
    ${row('<i class="dd bg-a"></i><i class="sq bg-a"></i>','<b>можно</b> — намокнете, но день рабочий')}
    ${row('<i class="dd bg-o"></i><i class="sq bg-o"></i>','<b>спорно</b> — решение под вопросом, нужен запас')}
    ${row('<i class="dd bg-r"></i><i class="sq bg-r"></i>','<b>не идти</b> — день против вас')}
    ${row('<i class="dd" style="background:var(--ink3)"></i>','кружок — <b>однодневный выход</b>')}
    ${row('<i class="sq" style="background:var(--ink3)"></i>','квадрат — <b>с ночёвкой</b>')}
    ${row('<i class="sq" style="background:var(--brand-wash);outline:1px solid var(--brand)"></i>','рамка — <b>самый сухой день</b> в этой точке')}
    <div class="note">Число под иконкой — осадки за сутки (основной сценарий, мм). Вердикт
    учитывает и количество осадков, и то, насколько модели между собой согласны.
    Нажмите на точку — там разбор по дням, метеограмма на 48 часов и надёжность.</div>`);
}
function locCard(l){
  const t=l.today;
  if(!t) return `<button class="card" onclick="loadForecast('${l.id}')">
    <div class="row"><div><div class="loc">${l.name}</div>
      <div class="tiny">${l.elevation_m} м</div></div>
      <span class="pill">нет расчёта</span></div></button>`;
  const today=`<span class="band-num">сегодня <b>${g(t.p50)}</b> мм <u>(от ${g(t.p10)} до ${g(t.p90)})</u> · ${Math.round(t.pop*100)}%</span>`;
  return `<button class="card" onclick="loadForecast('${l.id}')">
    <div class="row"><div><div class="loc">${HIL_IC[t.hil_level]} ${l.name}</div>
      <div class="tiny">${l.elevation_m} м</div></div>
      <span class="pill ok">${horizon(t.day,l.days_total)} →</span></div>
    <div style="margin-top:8px">${today}</div>
    ${dayStrip(l.days||[])}</button>`;
}
const norm=s=>(s||'').toLowerCase().replace(/ё/g,'е').trim();
// список точек: фильтр по названию/району + группировка по горным районам
function renderList(q){
  const box=document.getElementById('list'); if(!box) return;
  const needle=norm(q);
  const locs=(CACHE.locs||[]).filter(l=>!needle
    || norm(l.name).includes(needle) || norm(l.cluster_name).includes(needle));
  if(!locs.length){
    box.innerHTML=`<div class="state">По запросу «${q}» ничего нет.<br>
      <span class="tiny">Попробуйте название точки или района: Фишт, Арабика, Кодор…</span></div>`;
    return;
  }
  const order=[], byCluster=new Map();
  locs.forEach(l=>{ if(!byCluster.has(l.cluster)){ byCluster.set(l.cluster,[]); order.push(l.cluster); }
    byCluster.get(l.cluster).push(l); });
  box.innerHTML=order.map(k=>{
    const grp=byCluster.get(k);
    return `<div class="grp"><span>${grp[0].cluster_name||k}</span>
      <b>${grp.length} ${plural(grp.length,'точка','точки','точек')}</b></div>${grp.map(locCard).join('')}`;
  }).join('');
}
async function loadHome(){
  closeModal();
  if(tg&&tg.BackButton) tg.BackButton.hide();
  view.innerHTML='<div class="skel"></div><div class="skel"></div>';
  try{
    if(!CACHE.locs) CACHE.locs=(await api('/api/locations')).locations;
    if(!CACHE.locs.length){ view.innerHTML='<div class="state">Пока нет локаций.</div>'; return; }
    view.innerHTML=`<div class="tools">
        <input id="q" class="srch" type="search" placeholder="Поиск точки или района"
          autocomplete="off" spellcheck="false" value="${CACHE.q||''}">
        <button class="qmark" onclick="showLegend()" aria-label="Что значат значки">?</button>
      </div><div id="list"></div>`;
    const inp=document.getElementById('q');
    inp.addEventListener('input',()=>{ CACHE.q=inp.value; renderList(inp.value); });
    renderList(CACHE.q||'');
  }catch(e){view.innerHTML='<div class="state">Не удалось загрузить.</div>'}
}

// столбик с закруглённой верхушкой и прямым низом (стоит на базовой линии)
function barPath(x,y,w,h,r){
  const rr=Math.min(r,w/2,h);
  return `M${x} ${y+h} V${y+rr} A${rr} ${rr} 0 0 1 ${x+rr} ${y} H${x+w-rr} A${rr} ${rr} 0 0 1 ${x+w} ${y+rr} V${y+h} Z`;
}
// человеческий пересказ недели: что вообще происходит с погодой
function weeklyStory(days){
  if(!days.length) return '';
  let pk=0; days.forEach((d,i)=>{ if(d.p50>days[pk].p50) pk=i; });
  const p=days[pk];
  let dry=0; while(dry<days.length && days[dry].p50<0.5) dry++;
  const wet=days.filter(d=>d.p50>=2).length;
  if(p.p50<0.5) return `Осадков нет во всём горизонте — ни одного дня заметнее <b>0,5 мм</b>. Ограничение здесь не погода, а надёжность прогноза на дальних днях.`;
  const parts=[`Самый мокрый день — <b>${wd(p.day)} ${dm(p.day)}</b>: ${g(p.p50)} мм, в худшем случае до ${g(p.p90)} мм (${p.hil_label.toLowerCase()}).`];
  if(dry>=2) parts.push(`До него сухо: ближайшие <b>${dry} ${plural(dry,'день','дня','дней')}</b> без осадков.`);
  else if(days[0].p50>=2) parts.push(`Мокро уже сегодня.`);
  parts.push(wet ? `Дней с ощутимым дождём (от 2 мм): <b>${wet}</b> из ${days.length}.`
                 : `Остальные дни — сухие или почти сухие.`);
  return parts.join(' ');
}
function plural(n,a,b,c){const x=n%10,y=n%100;
  if(x===1&&y!==11)return a; if(x>=2&&x<=4&&(y<10||y>=20))return b; return c;}
function weeklyChart(days){
  const W=300,H=140,pad=16,base=H-30,top=18;
  const mx=Math.max(6,...days.map(d=>d.p90));
  const fmx=sq(mx);
  const bw=(W-2*pad)/days.length;
  const barW=Math.min(15,bw*0.56);          // ≤24 px на экране: столбик не занимает всю ячейку
  const y=v=>base-(sq(v)/fmx)*(base-top);
  // засечки шкалы (мм) — бледные линии с подписью у правого края
  const ticks=[1,2,5,10,20,40,80].filter(t=>t<=mx);
  let grid=ticks.map(t=>`<line x1="${pad}" y1="${y(t)}" x2="${W-pad}" y2="${y(t)}" stroke="var(--hair)" stroke-width="0.6"></line>
    <text x="${W-pad+2}" y="${y(t)+2.5}" font-size="7" fill="var(--ink3)">${t}</text>`).join('');
  grid+=`<text x="${W-pad+2}" y="${top-6}" font-size="7" fill="var(--ink3)">мм</text>`;
  // подписываем выборочно: три самых мокрых дня (иначе число над каждым столбцом — шум)
  const labelled=new Set(days.map((d,i)=>i).filter(i=>days[i].p50>=1)
    .sort((a,b)=>days[b].p50-days[a].p50).slice(0,3));
  let bars='',wsk='',lbl='',xl='';
  days.forEach((d,i)=>{
    const x=pad+i*bw+bw/2;
    const bh=Math.max(1.5,base-y(d.p50));
    const tip=`${wd(d.day)} ${dm(d.day)} · скорее всего ${g(d.p50)} мм, от ${g(d.p10)} до ${g(d.p90)} · ${d.hil_label} · вероятность ${Math.round(d.pop*100)}%`;
    bars+=`<path d="${barPath(x-barW/2,base-bh,barW,bh,3)}" fill="${PC[d.hil_level]}"><title>${tip}</title></path>`;
    wsk+=`<line x1="${x}" y1="${y(d.p10)}" x2="${x}" y2="${y(d.p90)}" stroke="var(--ink3)" stroke-width="1.2"></line>
      <line x1="${x-3}" y1="${y(d.p90)}" x2="${x+3}" y2="${y(d.p90)}" stroke="var(--ink3)" stroke-width="1.2"></line>`;
    if(labelled.has(i)){
      // подпись выше уса p90, иначе цифра ложится на его засечку
      const lx=Math.min(W-11,Math.max(11,x));
      lbl+=`<text x="${lx}" y="${Math.max(7,Math.min(y(d.p50),y(d.p90))-4)}" font-size="7.5" fill="var(--ink)" text-anchor="middle" style="font-variant-numeric:tabular-nums">${g(d.p50)}</text>`;
    }
    // дата под днём недели: 14 столбцов, «Вт» без числа встречается дважды
    xl+=`<text x="${x}" y="${H-13}" font-size="8.5" fill="var(--ink3)" text-anchor="middle">${wd(d.day)}</text>
      <text x="${x}" y="${H-4}" font-size="7" fill="var(--ink3)" text-anchor="middle">${new Date(d.day+'T00:00:00').getDate()}</text>`;
  });
  return `<div class="story">${weeklyStory(days)}</div>
    <div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Осадки по дням, √-шкала">
    ${grid}
    <line x1="${pad}" y1="${base}" x2="${W-pad}" y2="${base}" stroke="var(--hair2)"></line>
    ${bars}${wsk}${lbl}${xl}</svg>
    <div class="cl"><span><i class="sw" style="background:var(--ink3)"></i>усы — от минимума до максимума по моделям</span></div></div>
    <div class="scale"><span>сухо</span><div class="grad"></div><span>ливень</span></div>
    <div class="note">Высота столбца — сколько дождя скорее всего выпадет за сутки, цвет — насколько это мешает походу
    (${HIL_W.join(' · ')}). Шкала по высоте — корневая: иначе один ливень «сплющивает» все остальные дни
    до нуля. Подписаны три самых мокрых дня, остальные значения — в списке ниже.</div>`;
}

function relBlock(d){
  const last=d.days.length-1;
  // последний чип — конец горизонта, какой он есть: после отсечения прошедшего дня
  // жёсткий индекс 13 просто исчезал, и субблок «14 дней» пропадал из блока
  const idx=[...new Set([0,2,6,last])].filter(i=>i>=0&&d.days[i]).sort((a,b)=>a-b);
  const chips=idx.map(i=>{
    const dd=d.days[i], lvl=confLevel(dd,dd.n_models);
    const lab=`${i+1} ${plural(i+1,'день','дня','дней')}`;
    return `<button class="relchip" onclick="showReliability('${dd.day}')"
        title="${wd(dd.day)} ${dm(dd.day)}: скорее всего ${g(dd.p50)} мм, от ${g(dd.p10)} до ${g(dd.p90)}, ${dd.n_models}/5 моделей — нажмите, чтобы разобрать">
      <div class="h">${lab.toUpperCase()}</div>
      <div class="dot ${CB[lvl]}"></div><div class="w ${GC[lvl]}">${CW[lvl]}</div>
      <div class="relchip-n">${dd.n_models}/5 моделей</div></button>`;
  }).join('');
  const n=d.days[0]?d.days[0].n_models:d.n_models;
  const far=d.days[d.days.length-1];
  const nf=far?far.n_models:n;
  const cover=nf<n ? `Моделей в расчёте: <b>${n}/5</b> (к концу горизонта <b>${nf}/5</b>)`
                   : `Моделей в расчёте: <b>${n}/5</b>`;
  const d3=d.days[2]||d.days[d.days.length-1];
  const spread=d3?(d3.p90-d3.p10):0;
  const sw=spread<3?'узкий':spread<12?'умеренный':'широкий';
  // Ансамблевые члены — это тот же прогноз, запущенный с чуть разными
  // начальными данными: их число показывает, на скольких сценариях стоит оценка.
  const mem=d.days[0]&&d.days[0].n_members>n ? d.days[0].n_members : 0;
  const memNote=mem?` и <b>${mem} сценариев</b> ансамблей`:'';
  return `<div class="rel"><h4>📊 Надёжность <span class="tiny" style="font-weight:400">— предварительно</span></h4>
    <div class="relrow">${chips}</div>
    <div class="relmeta">${cover}${memNote} · на 3-й день «от» и «до» расходятся на <b>${g(spread)} мм</b> — это ${sw} разброс.
    Нажмите на любой срок выше — разберём на реальных числах, почему именно такая оценка.
    <button class="lnk" onclick="showModels(${n})">какие это модели?</button></div>
    <details class="rel-how"><summary>Как считается надёжность</summary>
      <div class="body">
        Один и тот же день считают <b>5 независимых метеомоделей</b>${mem?` и два ансамбля —
        те же модели, запущенные ${mem} раз с чуть разными начальными данными`:''}. Оценка
        складывается из трёх вещей: насколько модели <b>согласны между собой</b>, насколько
        узок <b>разброс ансамблевых сценариев</b> и насколько прогноз на эту дату
        <b>устойчив от прогона к прогону</b>. Проседание любого из трёх снижает итог.
        ${CW.map((w,i)=>`<div class="rel-lv"><i class="${CB[i]}"></i><span><b class="${GC[i]}">${w}</b> — ${LVL_DESC[i]}</span></div>`).join('')}
        <div style="margin-top:7px;color:var(--ink3)">Шкала качественная: сверка прогнозов
        с фактом на истории (калибровка) ещё не накоплена, а некалиброванное число
        обещало бы точность, которой нет.</div>
      </div></details></div>`;
}

// возраст карточки: конвейер идёт 6×/сутки, но прогон может опоздать или упасть —
// тогда честнее сказать, что данные несвежие, чем молча показывать время без даты
function freshness(upd){
  const hrs=(Date.now()-upd.getTime())/3600e3;
  const hhmm=String(upd.getHours()).padStart(2,'0')+':'+String(upd.getMinutes()).padStart(2,'0');
  const when=hrs<24 ? `${hhmm}` : `${dmt(upd)} ${hhmm}`;
  if(hrs>=8) return `<span class="pill stale" title="Конвейер считает прогноз каждые 4 часа; последний расчёт задержался">⚠ данные от ${when} · ${Math.round(hrs)} ч назад</span>`;
  return `<span class="tiny">обновлено ${when}</span>`;
}
async function loadForecast(id){
  closeModal();
  view.innerHTML='<div class="skel"></div><div class="skel"></div>';
  if(tg&&tg.BackButton){tg.BackButton.show();tg.BackButton.onClick(loadHome);}
  try{
    const d=await api('/api/forecast?location='+encodeURIComponent(id));
    CACHE.fc=d;                       // для поп-апа «почему такая надёжность»
    const upd=new Date(d.computed_at);
    const leg=`<div class="dayleg">
      <span>🥾 день · 🏕 ночёвка — <b>вердикт: стоит ли идти</b></span>
      <span>дождь за сутки: сколько <b>скорее всего</b>, а рядом — <b>от</b> минимума <b>до</b> максимума</span></div>`;
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
        <div class="daymeta"><b>${g(x.p50)}</b> мм · от ${g(x.p10)} до ${g(x.p90)} · ${x.hil_label}</div>
        ${band(x)}
      </div></div>`;
    }).join('');
    view.innerHTML=`<button class="back" onclick="loadHome()">‹ Все точки</button>
      <div class="dhead"><div class="loc">${d.location.name}</div><div class="tiny">${d.location.elevation_m} м</div></div>
      <div class="row" style="margin:0 2px 10px">
        <button class="pill ok" onclick="showModels(${d.n_models})">🛰 ${d.n_models} ${modelsWord(d.n_models)} ⓘ</button>
        ${freshness(upd)}</div>
      <section id="secHourly" class="blk">${H_HOURLY}<div class="skel"></div></section>
      ${hikeHero(d.days)}
      <div class="blk"><h4>🌧 Осадки по дням <span class="tiny">— ${d.days.length} ${plural(d.days.length,'день','дня','дней')}</span></h4>
        ${weeklyChart(d.days)}</div>
      <div class="blk"><h4>📋 Прогноз по дням <span class="tiny">— ${d.days.length} ${plural(d.days.length,'день','дня','дней')}, по важности сигналов</span></h4>
        <div class="days">${leg}${rows}
        <div class="tiny" style="padding:8px 2px 4px;line-height:1.4">* у последнего дня прогноза на следующие сутки ещё нет — оценка «с ночёвкой» предварительна.</div></div></div>
      <section id="secHistory" class="blk">${H_HIST}<div class="skel"></div></section>
      ${relBlock(d)}`;
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
        dl+=`<text x="${Math.min(W-18,Math.max(18,sx(i)))}" y="${H-4}" font-size="7.5" fill="var(--ink3)" text-anchor="middle">${WD[t.getDay()]} ${dmt(t)}</text>`;
    }
    // отсчёт идёт от текущего часа: помечаем начало оси, чтобы «48 ч» читались буквально
    const t0=tsLocal(h.times[0]), t1=tsLocal(h.times[n-1]);
    const nowMark=`<line x1="${padL}" y1="${top-4}" x2="${padL}" y2="${base}" stroke="var(--accent)" stroke-width="1"></line>
      <text x="${padL+3}" y="${top-5}" font-size="7.5" fill="var(--accent)">сейчас</text>`;
    const svg=`<div class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Метеограмма на 48 часов вперёд">
      ${dry}${grid}<line x1="${padL}" y1="${base}" x2="${W-padR}" y2="${base}" stroke="var(--hair2)"></line>
      ${band}${line}${popl}${nowMark}${xl}${dl}
      <text x="${W-padR}" y="10" font-size="8" fill="var(--ink3)" text-anchor="end">осадки, мм/ч</text></svg>
      <div class="cl"><span><i class="sw" style="background:var(--precip)"></i>скорее всего + от и до</span>
      <span><i class="sw" style="background:var(--accent)"></i>вероятность</span>
      <span><i class="sw" style="background:color-mix(in srgb,var(--g) 40%,transparent)"></i>сухо</span></div></div>`;
    // окно и сухое окно — в часах от «сейчас»
    let firstWet=h.p50.findIndex(v=>v>=0.3);
    const dryHrs = firstWet<0 ? n : firstWet;
    const summary = dryHrs>0
      ? `Сухое окно: ближайшие <b>${dryHrs} ч</b>.`
      : `Осадки уже идут.`;
    const range=`<div class="tiny" style="margin:-2px 2px 8px">от <b>${WD[t0.getDay()]} ${dmt(t0)} ${hhmm(t0)}</b> до <b>${WD[t1.getDay()]} ${dmt(t1)} ${hhmm(t1)}</b> · ${n} ч · местное время</div>`;
    return `${range}${svg}
      <div class="note" style="margin-top:10px">${summary} Пунктир — вероятность осадков, полоса — от минимума до максимума по моделям.</div>`;
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
  // та же шкала осадков, что у столбиков: сухо → ливень, один тон
  const t=Math.min(v,mx)/(mx||1);
  const stops=PC;
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
    // подпись выпуска: «Вс 26.07 14:00» (issued_at приходит со смещением UTC,
    // поэтому new Date переводит его в часовой пояс пользователя)
    const fmtIssue=iso=>{const d=new Date(iso);
      return WD[d.getDay()]+' '+String(d.getDate()).padStart(2,'0')+'.'+String(d.getMonth()+1).padStart(2,'0')
        +' '+String(d.getHours()).padStart(2,'0')+':'+String(d.getMinutes()).padStart(2,'0')};
    const stamps=h.issues.map(fmtIssue);
    const head=`<div class="hmrow"><span class="yl"></span>
      <div class="cells hm-hd" style="${gtc}">${stamps.map((s,i)=>
        `<span class="${i===n-1?'last':''}" title="${s}">${s}</span>`).join('')}</div></div>`;
    const body=h.rows.map(r=>{
      const rmax=Math.max(FLOOR,...r.vals.filter(v=>v!=null));
      const cells=r.vals.map((v,i)=>`<i class="${v==null?'nd':''}" style="background:${heatColor(v,rmax)}" title="${stamps[i]} → ${v==null?'выпуска ещё не было':Math.round(v*10)/10+' мм'}"></i>`).join('');
      return `<div class="hmrow"><span class="yl"><b>${wd(r.date)}</b> ${dm(r.date)}</span><div class="cells" style="${gtc}">${cells}</div></div>`;
    }).join('');
    return `<div class="story">Строки — прогнозируемая дата, столбцы — момент выпуска прогноза (${n}, последний выделен).
      Цвет — ожидаемый дождь <b>относительно этого же дня</b>: у каждой строки своя шкала, чтобы было видно,
      как менялось мнение моделей именно про эту дату.</div>
      <div class="hm">${head}${body}</div>
      <div class="scale"><span>сухо</span><div class="grad"></div><span>ливень</span></div>
      <div class="note">Стабильные столбцы справа — прогноз «устаканился». Скачки — модели меняли мнение.
      Накапливается автоматически каждые 4 часа.</div>`;
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
      <div class="note" style="margin-top:10px">Значение — сколько дождя скорее всего выпадет за сутки. Выберите район с меньшим дождём как альтернативу.</div>`;
  }catch(e){view.innerHTML='<div class="state">Не удалось сравнить.</div>'}
}

loadHome();
</script>
</body>
</html>'''
