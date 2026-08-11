# adaptive-farming-strategy-for-kaggriculture

> Extracted by `analysis/nb_extract.py` from `notebooks/adaptive-farming-strategy-for-kaggriculture.ipynb`.
> Cell numbers below are the anchors cited elsewhere in the repo (e.g. MASTERPLAN's `viz cell 19` = cell 19 of the *visualized* notebook).

## cell [0] — markdown

<style>
:root{
  --kg-ink:#173322; --kg-ink2:#264436; --kg-muted:#5d7065; --kg-soft:#7d8f84;
  --kg-line:#d7e5dc; --kg-line2:#c8dbcf;
  --kg-green:#1d7b4a; --kg-green2:#0f5a36;
  --kg-teal:#16889a; --kg-gold:#b27b12; --kg-violet:#8357a8;
  --kg-paper:#fcfefc; --kg-paper2:#f2f8f4; --kg-paper3:#edf5f0;
  --kg-shadow:0 10px 30px rgba(20,60,38,.08);
  --kg-shadow-strong:0 18px 42px rgba(6,31,20,.18);
}
.jp-RenderedHTMLCommon p,.jp-RenderedHTMLCommon li,.rendered_html p,.rendered_html li{line-height:1.7}
.jp-RenderedHTMLCommon h2,.rendered_html h2,h2{
  position:relative;
  color:var(--kg-ink)!important;
  background:
    linear-gradient(90deg,rgba(40,138,84,.08),rgba(40,138,84,.03) 55%,rgba(21,129,145,.07) 100%);
  border:1px solid var(--kg-line)!important;
  border-left:6px solid var(--kg-green)!important;
  border-radius:18px;
  padding:13px 18px 13px 22px!important;
  margin-top:1.8em!important;
  margin-bottom:.85em!important;
  letter-spacing:-.018em;
  box-shadow:0 8px 24px rgba(20,60,38,.05)
}
.jp-RenderedHTMLCommon h2::before,.rendered_html h2::before,h2::before{
  content:"Section";
  display:inline-block;
  margin-right:12px;
  padding:4px 9px;
  font-size:10px;
  font-weight:800;
  letter-spacing:.16em;
  text-transform:uppercase;
  color:#f4fff8;
  background:linear-gradient(135deg,var(--kg-green),#29965c);
  border-radius:999px;
  vertical-align:middle;
}
.jp-RenderedHTMLCommon h3,.rendered_html h3,h3{color:inherit!important;letter-spacing:-.01em}
a{color:var(--jp-brand-color1,#1677a8)!important}
code{background:rgba(102,129,112,.12)!important;padding:.12em .34em;border-radius:6px}
pre,.jp-OutputArea-output pre,.output_subarea pre{border:1px solid var(--jp-border-color2,#d7e4db);border-radius:16px;padding:14px}
blockquote{border-left:4px solid #b78518!important;padding:12px 16px!important;border-radius:0 12px 12px 0}
.jp-OutputArea-output,.output_html,.output_subarea{background:transparent!important}

.kg-hero{
  position:relative; box-sizing:border-box; margin:6px 0 24px; padding:34px; border-radius:30px; overflow:hidden;
  background:
    radial-gradient(circle at 84% 12%, rgba(118,255,182,.26), transparent 23%),
    radial-gradient(circle at 73% 88%, rgba(63,196,255,.16), transparent 28%),
    linear-gradient(135deg,#08261a 0%,#103624 42%,#113a49 100%);
  color:#f6fff9; border:1px solid rgba(255,255,255,.12); box-shadow:var(--kg-shadow-strong)
}
.kg-hero::before{
  content:""; position:absolute; inset:0;
  background:
    linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,.04) 1px, transparent 1px);
  background-size:26px 26px; mask-image:linear-gradient(180deg,rgba(0,0,0,.7),transparent 92%);
  pointer-events:none;
}
.kg-hero::after{
  content:""; position:absolute; right:-80px; top:-70px; width:240px; height:240px; border-radius:50%;
  background:radial-gradient(circle, rgba(255,255,255,.16), rgba(255,255,255,0)); filter:blur(8px);
}
.kg-hero-grid{position:relative; z-index:1; display:grid; grid-template-columns:minmax(0,1.6fr) minmax(290px,.82fr); gap:24px; align-items:stretch}
.kg-kicker{font-size:12px; letter-spacing:.18em; text-transform:uppercase; color:#a6ebc0; font-weight:800}
.kg-hero h1{font-size:48px; line-height:1.01; margin:10px 0 12px; color:#fff!important; letter-spacing:-.045em}
.kg-hero p{font-size:18px; line-height:1.64; margin:0; color:#f3fff7!important; max-width:850px; text-shadow:0 1px 2px rgba(0,0,0,.22)}
.kg-hero-copy{display:block; margin-top:10px; max-width:850px; padding:14px 16px; border-radius:16px; background:rgba(2,18,12,.34); border:1px solid rgba(255,255,255,.12); box-shadow:inset 0 1px 0 rgba(255,255,255,.05)}
.kg-hero-copy p{color:#f5fff8!important; opacity:1!important}
.kg-chip-row{display:flex; gap:8px; flex-wrap:wrap; margin-top:20px}
.kg-chip{display:inline-block; border:1px solid rgba(255,255,255,.18); background:rgba(255,255,255,.08); color:#effcf4; padding:7px 11px; border-radius:999px; font-size:12px; font-weight:700; backdrop-filter: blur(4px)}
.kg-stat-row{display:grid; grid-template-columns:repeat(3, minmax(110px,1fr)); gap:10px; margin-top:18px; max-width:620px}
.kg-stat{background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.15); border-radius:18px; padding:12px 13px; backdrop-filter:blur(3px)}
.kg-stat .v{display:block; color:#fff; font-weight:900; font-size:24px; letter-spacing:-.03em; margin-bottom:2px}
.kg-stat .k{display:block; color:#cde7d8; font-size:12px; line-height:1.3}
.kg-thesis{background:linear-gradient(180deg, rgba(4,20,14,.42), rgba(10,30,21,.56)); color:#effcf4; border-radius:24px; padding:22px; border:1px solid rgba(255,255,255,.14); box-shadow:inset 0 1px 0 rgba(255,255,255,.06)}
.kg-thesis .label{font-size:11px; letter-spacing:.14em; text-transform:uppercase; color:#a8ecc2; font-weight:800}
.kg-thesis .big{font-size:21px; line-height:1.28; font-weight:800; margin:8px 0 12px; color:#fff}
.kg-thesis .point{padding:9px 0; border-top:1px solid rgba(255,255,255,.11); font-size:13px; line-height:1.5; color:#d8eee1}
.kg-thesis .point b{color:#fff}
.kg-microbar{height:6px; border-radius:999px; background:linear-gradient(90deg,#4fd88b 0 25%,#34b7c7 25% 54%,#b18ad1 54% 80%,#e0ae42 80%); margin-top:18px}

.kg-prose{position:relative; background:linear-gradient(145deg,var(--kg-paper),var(--kg-paper2)); color:var(--kg-ink2); border:1px solid var(--kg-line); border-radius:18px;
  padding:17px 18px; margin:12px 0 15px; box-shadow:var(--kg-shadow)}
.kg-prose::before{content:""; position:absolute; left:0; top:0; bottom:0; width:5px; border-radius:18px 0 0 18px; background:linear-gradient(180deg,var(--kg-green),#56b07a)}
.kg-prose p{margin:.1em 0 .4em; color:#3f5749}.kg-prose b,.kg-prose strong{color:var(--kg-ink)}
.kg-prose ol,.kg-prose ul{margin:.3em 0 .2em 1.2em; color:#3f5749}
.kg-prose .lead{font-size:15px; line-height:1.67}.kg-prose .micro{font-size:13px; color:#66796e}

.kg-grid{display:grid; grid-template-columns:repeat(2,minmax(240px,1fr)); gap:12px; margin:14px 0}
.kg-card{position:relative; color:var(--kg-ink); border:1px solid var(--kg-line); border-radius:20px; padding:18px 18px 17px; box-shadow:var(--kg-shadow); overflow:hidden}
.kg-card::after{content:""; position:absolute; inset:auto -40px -40px auto; width:110px; height:110px; border-radius:50%; background:radial-gradient(circle, rgba(0,0,0,.04), rgba(0,0,0,0));}
.kg-card .eyebrow{font-size:11px; letter-spacing:.14em; text-transform:uppercase; font-weight:800; margin-bottom:6px}
.kg-card b{color:var(--kg-ink); display:block; margin-bottom:4px}.kg-card span{color:#53695d; line-height:1.55; font-size:14px}
.kg-card.green{border-top:5px solid #2a8a54; background:linear-gradient(145deg,#f2faf5,#ffffff)}
.kg-card.teal{border-top:5px solid #168a9a; background:linear-gradient(145deg,#eff9fa,#ffffff)}
.kg-card.gold{border-top:5px solid #b78312; background:linear-gradient(145deg,#fff8e9,#ffffff)}
.kg-card.violet{border-top:5px solid #8b5fb2; background:linear-gradient(145deg,#f8f1fb,#ffffff)}
.kg-card.green .eyebrow{color:#176b42}.kg-card.teal .eyebrow{color:#0b7285}.kg-card.gold .eyebrow{color:#8b610c}.kg-card.violet .eyebrow{color:#76519b}

.kg-roadmap{display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:14px 0 8px}
.kg-road{position:relative; border:1px solid var(--kg-line); border-radius:22px; padding:18px 16px 16px; box-shadow:var(--kg-shadow); overflow:hidden; background:linear-gradient(145deg,#fcfefc,#f3f8f5)}
.kg-road::before{content:""; position:absolute; left:18px; top:20px; width:38px; height:38px; border-radius:14px; background:linear-gradient(135deg,#1c7a49,#35a664); box-shadow:0 10px 22px rgba(28,122,73,.18)}
.kg-road.teal::before{background:linear-gradient(135deg,#16889a,#2aa8bd)}
.kg-road.gold::before{background:linear-gradient(135deg,#b78312,#dba128)}
.kg-road.violet::before{background:linear-gradient(135deg,#8357a8,#a37bc4)}
.kg-road .n{position:relative; z-index:1; color:#fff; font-weight:900; font-size:16px; display:inline-block; margin-left:13px; margin-top:5px}
.kg-road .t{display:block; margin-top:18px; font-weight:800; color:var(--kg-ink); font-size:16px}
.kg-road .d{display:block; margin-top:6px; color:#53695d; line-height:1.55; font-size:14px}

.kg-strip{display:grid; grid-template-columns:repeat(5,minmax(105px,1fr)); gap:8px; margin:16px 0}
.kg-mini{background:linear-gradient(145deg,#f9fcfa,#eef6f1); color:var(--kg-ink); border:1px solid var(--kg-line); border-radius:15px; padding:13px 10px; text-align:center; box-shadow:0 5px 14px rgba(24,68,44,.04)}
.kg-mini b{display:block; font-size:14px; color:var(--kg-ink); margin-bottom:3px}.kg-mini small{color:#5b7064; line-height:1.3}

.kg-note{color:var(--kg-ink); border:1px solid var(--kg-line); border-left:5px solid #2a8a54; border-radius:16px; padding:15px 17px; margin:14px 0; box-shadow:var(--kg-shadow); background:linear-gradient(135deg,#eef9f2,#fbfdfb)}
.kg-note.gold{border-left-color:#b78312;background:linear-gradient(135deg,#fff7e5,#fffdf8)}
.kg-note.teal{border-left-color:#168a9a;background:linear-gradient(135deg,#ebf8fa,#fbfefe)}
.kg-note.violet{border-left-color:#8b5fb2;background:linear-gradient(135deg,#f5eef9,#fdfbfe)}
.kg-note.red{border-left-color:#c75b4f;background:linear-gradient(135deg,#fff1ee,#fffafa)}
.kg-note .title{font-weight:800;margin-bottom:5px;color:var(--kg-ink)}.kg-note .body{color:#486052;line-height:1.62;font-size:14px}

.kg-insight-row{display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)); gap:10px; margin:14px 0}
.kg-insight{position:relative; border-radius:18px; padding:15px 15px 14px; border:1px solid var(--kg-line); background:#fff; color:var(--kg-ink); box-shadow:var(--kg-shadow); overflow:hidden}
.kg-insight::after{content:""; position:absolute; right:-18px; top:-18px; width:68px; height:68px; border-radius:50%; background:radial-gradient(circle, rgba(22,136,154,.12), rgba(22,136,154,0));}
.kg-insight .num{font-size:11px; font-weight:800; letter-spacing:.12em; color:#168a9a; text-transform:uppercase}.kg-insight b{display:block; margin:6px 0 5px}.kg-insight span{font-size:13px; color:#587065; line-height:1.48}

.kg-svg-wrap{background:linear-gradient(145deg,#fbfdfb,#f2f8f4); border:1px solid var(--kg-line); border-radius:22px; padding:12px 10px; margin:16px 0; overflow-x:auto; box-shadow:var(--kg-shadow)}
.kg-terminal{background:linear-gradient(135deg,#0d2a1e,#12362a); color:#eaf8ef; border:1px solid #326247; border-radius:18px; padding:18px 20px; margin:14px 0; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; line-height:1.8; box-shadow:0 10px 24px rgba(8,33,22,.17)}
.kg-terminal b{color:#9be5b7}.kg-terminal .dim{color:#a9c9b5}
.kg-divider{height:1px; background:linear-gradient(90deg, transparent, #cfe1d6 18%, #cfe1d6 82%, transparent); margin:18px 0}
.kg-caption{font-size:13px; color:#607468; margin-top:6px}

@media (max-width:920px){ .kg-roadmap{grid-template-columns:repeat(2,minmax(0,1fr));} }
@media (max-width:760px){
  .kg-hero{padding:24px}.kg-hero-grid{grid-template-columns:1fr}.kg-hero h1{font-size:38px}
  .kg-grid{grid-template-columns:1fr}.kg-strip{grid-template-columns:repeat(2,minmax(120px,1fr))}.kg-insight-row{grid-template-columns:1fr}
  .kg-stat-row{grid-template-columns:1fr 1fr 1fr}
  .kg-roadmap{grid-template-columns:1fr}
}
.kg-hero .kg-chip,.kg-hero .kg-kicker,.kg-hero .kg-stat .k,.kg-hero .kg-thesis,.kg-hero .kg-thesis .point{opacity:1!important}


/* ============================================================
   Kaggle Light/Dark hardening
   Public reading surfaces intentionally stay light in BOTH themes.
   This prevents Kaggle's dark-theme table/heading rules from
   overriding the notebook's foreground/background contrast.
   ============================================================ */

/* Section titles: always use a light editorial surface. */
.jp-RenderedHTMLCommon h2,
.rendered_html h2,
.jp-MarkdownOutput h2,
.markdown-output h2,
.markdown-cell h2,
h2 {
  background-color:#fbfdfb !important;
  background-image:linear-gradient(90deg,#ffffff 0%,#f5faf7 58%,#eef7f3 100%) !important;
  color:#173322 !important;
  border-color:#d2e2d8 !important;
  border-left-color:#1d7b4a !important;
  -webkit-text-fill-color:#173322 !important;
  text-shadow:none !important;
}
.jp-RenderedHTMLCommon h2 *,
.rendered_html h2 *,
.jp-MarkdownOutput h2 *,
.markdown-cell h2 * {
  color:#173322 !important;
  -webkit-text-fill-color:#173322 !important;
}
.jp-RenderedHTMLCommon h2::before,
.rendered_html h2::before,
.jp-MarkdownOutput h2::before,
.markdown-cell h2::before,
h2::before {
  color:#ffffff !important;
  -webkit-text-fill-color:#ffffff !important;
}

/* DataFrames / notebook tables: always white with dark text. */
.jp-OutputArea-output table,
.jp-OutputArea-output table.dataframe,
.jp-OutputArea-output table.forest-table,
.output_html table,
.output_subarea table,
.rendered_html table,
.jp-RenderedHTMLCommon table,
table.dataframe,
table.forest-table {
  background:#ffffff !important;
  background-color:#ffffff !important;
  color:#203a2c !important;
  border-color:#d6e3da !important;
  color-scheme:light !important;
}
.jp-OutputArea-output table thead,
.jp-OutputArea-output table.dataframe thead,
.jp-OutputArea-output table.forest-table thead,
.output_html table thead,
.rendered_html table thead,
table.dataframe thead,
table.forest-table thead {
  background:#f2f7f4 !important;
  background-color:#f2f7f4 !important;
  color:#173322 !important;
}
.jp-OutputArea-output table th,
.jp-OutputArea-output table.dataframe th,
.jp-OutputArea-output table.forest-table th,
.output_html table th,
.output_subarea table th,
.rendered_html table th,
.jp-RenderedHTMLCommon table th,
table.dataframe th,
table.forest-table th {
  background:#f2f7f4 !important;
  background-color:#f2f7f4 !important;
  color:#173322 !important;
  -webkit-text-fill-color:#173322 !important;
  border-color:#cbded1 !important;
  text-shadow:none !important;
}
.jp-OutputArea-output table tbody,
.jp-OutputArea-output table.dataframe tbody,
.jp-OutputArea-output table.forest-table tbody,
.output_html table tbody,
.rendered_html table tbody,
table.dataframe tbody,
table.forest-table tbody {
  background:#ffffff !important;
  background-color:#ffffff !important;
  color:#294438 !important;
}
.jp-OutputArea-output table td,
.jp-OutputArea-output table.dataframe td,
.jp-OutputArea-output table.forest-table td,
.output_html table td,
.output_subarea table td,
.rendered_html table td,
.jp-RenderedHTMLCommon table td,
table.dataframe td,
table.forest-table td {
  background:#ffffff !important;
  background-color:#ffffff !important;
  color:#294438 !important;
  -webkit-text-fill-color:#294438 !important;
  border-color:#e0ebe4 !important;
  text-shadow:none !important;
}
.jp-OutputArea-output table tbody tr,
.jp-OutputArea-output table.dataframe tbody tr,
.jp-OutputArea-output table.forest-table tbody tr,
.output_html table tbody tr,
.rendered_html table tbody tr,
table.dataframe tbody tr,
table.forest-table tbody tr {
  background:#ffffff !important;
  background-color:#ffffff !important;
  color:#294438 !important;
}
/* Keep a very subtle zebra band without ever becoming dark. */
.jp-OutputArea-output table tbody tr:nth-child(even) td,
.jp-OutputArea-output table.dataframe tbody tr:nth-child(even) td,
.jp-OutputArea-output table.forest-table tbody tr:nth-child(even) td,
.output_html table tbody tr:nth-child(even) td,
.rendered_html table tbody tr:nth-child(even) td,
table.dataframe tbody tr:nth-child(even) td,
table.forest-table tbody tr:nth-child(even) td {
  background:#f8fbf9 !important;
  background-color:#f8fbf9 !important;
}

</style>

## cell [1] — markdown

<div class="kg-hero">
  <div class="kg-hero-grid">
    <div>
      <div class="kg-kicker">Kaggriculture · 720-turn economic control · two-tier market-relay execution</div>
      <h1>🌾 Queue-Aware Farming</h1>
      <div class="kg-hero-copy"><p>
        A complete high-output season route does the heavy lifting. Runtime logic stays narrow: repair local WEED disruptions,
        adapt the livestock mix to the observed town, release WOOL when price or storage pressure justifies it, and relay a predictable FERTILIZER sale ahead of a near mirror while repaying the quantity exactly, with one extra turn of lead reserved for very-close mirrors.
      </p></div>
      <div class="kg-chip-row">
        <div class="kg-chip">720-turn route</div><div class="kg-chip">Local WEED repair</div>
        <div class="kg-chip">Town-aware WOOL release</div><div class="kg-chip">3/4-turn market relay</div>
      </div>
      <div class="kg-stat-row">
        <div class="kg-stat"><span class="v">720</span><span class="k">turns coordinated as one season</span></div>
        <div class="kg-stat"><span class="v">4</span><span class="k">small, purpose-built control layers</span></div>
        <div class="kg-stat"><span class="v">1</span><span class="k">exact <code>main.py</code> validated and archived</span></div>
      </div>
    </div>
    <div class="kg-thesis">
      <div class="label">Controller thesis</div>
      <div class="big">Keep the production engine stable. Adapt only where public state creates a repeatable market edge.</div>
      <div class="point"><b>Season route:</b> coordinates capital, labor, crops, livestock, logistics, and planned sales.</div>
      <div class="point"><b>Town branch:</b> a YARN_STORE-favorable town can tilt one livestock purchase and service window from cow toward sheep.</div>
      <div class="point"><b>WOOL release:</b> price, shed pressure, spacing, and the deadline decide when accumulated wool becomes cash.</div>
      <div class="point"><b>Market relay:</b> three successful checkpoints enable the standard 3-turn relay; if all three public-state distances are very small, the same batch moves 4 turns earlier. Exact repayment preserves total quantity.</div>
      <div class="kg-microbar"></div>
    </div>
  </div>
</div>

## cell [2] — markdown

### Strategy in motion

<div class="kg-prose"><div class="lead">Start with the behavior, then unpack the code. This is a <b>live replay rendered directly from <code>env.steps</code></b> after the exact same agent source runs a full 720-turn season. The notebook calls <code>show_farm_motion(env, seat=0, stride=6, duration=18)</code> in the cell below—there is no pre-rendered GIF, base64 asset, or decorative mock-up.</div></div>

<div class="kg-note teal"><div class="title">Read this as a moving strategy map</div><div class="body">Watch productive tiles spread, labor circulate through dense service regions, stochastic WEED cells appear as local shocks, and the farm transition from early investment toward late cash realization.</div></div>

## cell [3] — code

## cell [4] — markdown

## Notebook map

<div class="kg-roadmap">
  <div class="kg-road"><span class="n">01</span><span class="t">Understand the economy</span><span class="d">Review the win condition, the 720-turn horizon, shared-market pricing, and why raw quotes are only the first clue.</span></div>
  <div class="kg-road teal"><span class="n">02</span><span class="t">See the controller</span><span class="d">Follow the layered design: season planning, local repair, market protection, and final cash conversion.</span></div>
  <div class="kg-road gold"><span class="n">03</span><span class="t">Audit the behavior</span><span class="d">Use compact EDA and diagnostic plots to connect mechanism, capital flow, prices, and action mix.</span></div>
  <div class="kg-road violet"><span class="n">04</span><span class="t">Ship the submission</span><span class="d">Write <code>main.py</code>, validate a full 720-turn run, package the archive, and rerun the packaged code.</span></div>
</div>
<div class="kg-note teal"><div class="title">Reader promise</div><div class="body">This notebook is intentionally concise on math and focused on operational intuition. Every figure and callout is here to explain a decision, not just decorate the page.</div></div>

## cell [5] — markdown

## 1. The game in one minute

<div class="kg-prose"><div class="lead">Kaggriculture is a <b>two-player farming economy</b>. One season is <b>30 days × 24 turns = 720 turns</b>. The player with the higher terminal bank wins. Coin margin is useful for diagnosis, but strategy promotion is decided by <b>wins, losses, and ties</b>.</div></div>

<div class="kg-strip">
  <div class="kg-mini"><b>Capital</b><small>land · animals · seeds</small></div>
  <div class="kg-mini"><b>Operations</b><small>workers · routes · timing</small></div>
  <div class="kg-mini"><b>Biology</b><small>growth · water · fertilizer</small></div>
  <div class="kg-mini"><b>Market</b><small>shared prices · town demand</small></div>
  <div class="kg-mini"><b>Finish</b><small>cash in the bank at turn 720</small></div>
</div>

<div class="kg-note gold"><div class="title">The key operating insight</div><div class="body">A high spot price can still be a bad decision if the crop takes too long, consumes scarce labor, or crashes after repeated sales. Good play is about <b>economic timing</b>, not just expensive items.</div></div>


<div class="kg-note teal"><div class="title">Current town-demand regime</div><div class="body">The Town Center now removes one of each non-fertilizer product <b>once per day at a flat rate</b>. Shops unlock <b>with replacement</b>, so duplicate shop instances can concentrate demand on a small set of products. The controller therefore reads the live shop list instead of assuming a balanced town.</div></div>

## cell [6] — markdown

## 2. Imports and visual helpers

<div class="kg-prose"><div class="lead">The Kaggle runtime already provides the environment and analysis libraries used below. The public notebook contains no installation, extraction, path modification, or version-check cell.</div><div class="micro">The plotting canvas is deliberately self-contained, so charts stay legible in both Kaggle Light and Dark themes.</div></div>

## cell [7] — code

## cell [8] — markdown

## 3. Opening economy EDA

<div class="kg-prose"><div class="lead">A high opening price is only a clue. The real decision must combine price, growth time, worker travel, feed, storage, and the price erosion caused by selling into a shared market.</div></div>

<div class="kg-insight-row">
  <div class="kg-insight"><div class="num">Insight 01</div><b>Price is stateful</b><span>A quote is not a fixed reward. Selling changes future inventory and therefore later prices.</span></div>
  <div class="kg-insight"><div class="num">Insight 02</div><b>Throughput beats headline value</b><span>A premium crop only matters if the farm can repeatedly water, harvest, transport, and sell it before the deadline.</span></div>
  <div class="kg-insight"><div class="num">Insight 03</div><b>Cash timing matters</b><span>One dollar earned early can finance labor or land; the same dollar earned on turn 719 cannot compound.</span></div>
</div>

## cell [9] — code

## cell [10] — markdown

## 4. Architecture: preserve the route, exploit narrow public-state edges

<div class="kg-prose"><div class="lead">The controller separates <b>season-scale planning</b> from <b>turn-scale correction</b>. A complete route owns production, labor, purchases, and planned sales. Runtime logic touches only narrow, auditable edges: local WEED recovery, a town-composition livestock branch, inventory-aware WOOL release, same-turn SELL ordering, and one debt-accounted two-tier relay for a stable near mirror.</div></div>

<div class="kg-svg-wrap">
<svg width="1040" height="285" viewBox="0 0 1040 285" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Controller architecture">
  <rect x="24" y="72" width="205" height="145" rx="22" fill="#f2faf5" stroke="#bcd8c6"/>
  <text x="126" y="112" text-anchor="middle" fill="#176b42" font-size="12" font-weight="800">SEASON SCALE</text>
  <text x="126" y="145" text-anchor="middle" fill="#173322" font-size="18" font-weight="800">Complete route</text>
  <text x="126" y="171" text-anchor="middle" fill="#607168" font-size="12">capital · labor · logistics</text>
  <text x="126" y="192" text-anchor="middle" fill="#607168" font-size="12">production · planned sales</text>
  <path d="M231 144 H275" stroke="#7ea08c" stroke-width="3" marker-end="url(#arrow)"/>
  <rect x="278" y="72" width="205" height="145" rx="22" fill="#fff8e9" stroke="#ead8ad"/>
  <text x="380" y="112" text-anchor="middle" fill="#8b610c" font-size="12" font-weight="800">LOCAL EXECUTION</text>
  <text x="380" y="145" text-anchor="middle" fill="#173322" font-size="18" font-weight="800">WEED + town branch</text>
  <text x="380" y="171" text-anchor="middle" fill="#796a43" font-size="12">DIG · retry · short replay</text>
  <text x="380" y="192" text-anchor="middle" fill="#796a43" font-size="12">YARN-friendly sheep branch</text>
  <path d="M485 144 H529" stroke="#7ea08c" stroke-width="3" marker-end="url(#arrow)"/>
  <rect x="532" y="72" width="205" height="145" rx="22" fill="#f8f1fb" stroke="#ddcce9"/>
  <text x="634" y="112" text-anchor="middle" fill="#76519b" font-size="12" font-weight="800">SHARED MARKET</text>
  <text x="634" y="145" text-anchor="middle" fill="#173322" font-size="18" font-weight="800">Queue + WOOL release</text>
  <text x="634" y="171" text-anchor="middle" fill="#76647f" font-size="12">price-impact SELL ranking</text>
  <text x="634" y="192" text-anchor="middle" fill="#76647f" font-size="12">price · storage · demand</text>
  <path d="M739 144 H783" stroke="#7ea08c" stroke-width="3" marker-end="url(#arrow)"/>
  <rect x="786" y="72" width="230" height="145" rx="22" fill="#eff9fa" stroke="#bfdee3"/>
  <text x="901" y="112" text-anchor="middle" fill="#0b7285" font-size="12" font-weight="800">TWO-TIER RELAY</text>
  <text x="901" y="145" text-anchor="middle" fill="#173322" font-size="18" font-weight="800">Move 3 or 4, repay exactly</text>
  <text x="901" y="171" text-anchor="middle" fill="#526e72" font-size="12">strict mirror gets one extra turn</text>
  <text x="901" y="192" text-anchor="middle" fill="#526e72" font-size="12">same quantity removed when due</text>
  <defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#7ea08c"/></marker></defs>
</svg>
</div>

<div class="kg-note"><div class="title">Small blast radius, by design</div><div class="body">The farm is not globally re-planned from noisy observations. The relay only locks after three public-state checkpoints all remain close. Standard near mirrors use a 3-turn lead; very-close mirrors use 4 turns. Every early FERTILIZER unit becomes explicit debt that is removed from its original scheduled batch, so intended quantity is conserved.</div></div>

## cell [11] — markdown

## 5. A 30-day strategy atlas

<div class="kg-prose"><div class="lead">Think in phases. Early turns should create productive loops, middle turns should compound them, and late turns should stop behaving like an infinite-horizon farm and start behaving like a liquidation problem.</div></div>

<div class="kg-svg-wrap">
<svg width="1000" height="185" viewBox="0 0 1000 185" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Season timeline">
  <text x="500" y="27" text-anchor="middle" fill="#173322" font-size="20" font-weight="700">Build productive loops early; finish as bank balance</text>
  <rect x="45" y="65" width="145" height="60" rx="12" fill="#eaf7f9" stroke="#4e9aa5"/><text x="117" y="91" text-anchor="middle" fill="#173322" font-size="15" font-weight="700">BOOTSTRAP</text><text x="117" y="112" text-anchor="middle" fill="#5c7379" font-size="12">first labor · animals</text>
  <rect x="190" y="65" width="175" height="60" rx="0" fill="#edf8f1" stroke="#59a975"/><text x="277" y="91" text-anchor="middle" fill="#173322" font-size="15" font-weight="700">EXPAND</text><text x="277" y="112" text-anchor="middle" fill="#5a7064" font-size="12">land · routes · crops</text>
  <rect x="365" y="65" width="290" height="60" rx="0" fill="#eef6fb" stroke="#6599b1"/><text x="510" y="91" text-anchor="middle" fill="#173322" font-size="15" font-weight="700">ROTATE &amp; COMPOUND</text><text x="510" y="112" text-anchor="middle" fill="#60727a" font-size="12">harvest · care · reinvest</text>
  <rect x="655" y="65" width="220" height="60" rx="0" fill="#f7f0fb" stroke="#a27abc"/><text x="765" y="91" text-anchor="middle" fill="#173322" font-size="15" font-weight="700">PROTECT VALUE</text><text x="765" y="112" text-anchor="middle" fill="#74637d" font-size="12">flow guard · sale order</text>
  <rect x="875" y="65" width="80" height="60" rx="12" fill="#fff8e8" stroke="#c49a39"/><text x="915" y="91" text-anchor="middle" fill="#173322" font-size="14" font-weight="700">CASH</text><text x="915" y="112" text-anchor="middle" fill="#796a43" font-size="11">closeout</text>
  <line x1="45" y1="145" x2="955" y2="145" stroke="#92ac9c" stroke-width="2"/>
  <g fill="#607168" font-size="12"><text x="45" y="166">Day 0</text><text x="180" y="166">Day 4</text><text x="350" y="166">Day 9</text><text x="640" y="166">Day 20</text><text x="860" y="166">Day 28</text><text x="935" y="166">Day 30</text></g>
</svg></div>

<div class="kg-note teal"><div class="title">Read the season as a pipeline, not 720 isolated moves</div><div class="body">Early turns create capacity, middle turns compound it, and late turns protect realizable value. The useful question is not “What action pays most now?” but “Which action improves the amount of cash that can still reach the bank before turn 720?”</div></div>

## cell [12] — markdown

## 6. Four practical control layers

<div class="kg-grid">
  <div class="kg-card green"><div class="eyebrow">A · Complete season route</div><b>Let the long plan do the heavy lifting.</b><br><span>A compact full-season trajectory coordinates labor, crops, livestock, logistics, and planned market activity across the 720-turn episode.</span></div>
  <div class="kg-card gold"><div class="eyebrow">B · Local repair + town branch</div><b>Repair shocks, but adapt one livestock decision when the town supports it.</b><br><span>WEED repair uses DIG → retry → short replay. After the early town reveal, a YARN_STORE-favorable composition can redirect one cow purchase and matching service window toward sheep.</span></div>
  <div class="kg-card violet"><div class="eyebrow">C · WOOL + queue control</div><b>Turn wool into cash without flooding the shared market blindly.</b><br><span>WOOL release uses step-dependent price gates, shed pressure, a minimum spacing between releases, and deadline logic. Existing SELL slots are then ranked by modeled price damage plus live town demand.</span></div>
  <div class="kg-card teal"><div class="eyebrow">D · Two-tier FERTILIZER relay</div><b>Reach a predictable shared-market sale three turns earlier.</b><br><span>At steps 216, 240, and 264 the public farm structures must all remain close. A normal near mirror uses the proven <code>t+3 → t</code> relay; if every checkpoint is very close, the controller uses <code>t+4 → t</code>. The exact executed quantity is removed at the original due turn.</span></div>
</div>

<div class="kg-prose"><div class="lead">The important distinction is between <b>production policy</b> and <b>market timing</b>. The route decides what the farm produces. The runtime overlay changes only a few public-state-sensitive decisions, and the relay never creates extra FERTILIZER supply because every shifted unit carries an exact repayment debt.</div></div>

<div class="kg-note teal"><div class="title">Why two relay tiers?</div><div class="body">The relay is not a generic “sell earlier” rule. Three turns remain the default after the near-mirror checks. The fourth turn is reserved for a much tighter public-state match, keeping the extra timing edge confined to opponents that are genuinely close to the same season route.</div></div>

## cell [13] — markdown

## 7. Write the exact submission agent

<div class="kg-prose"><div class="lead">The complete controller is embedded below. The generated <code>main.py</code> is the <b>same file</b> compiled, executed for 720 turns, hashed, archived, extracted, and executed again.</div><div class="micro">That identity check matters: validating one source and accidentally submitting another is an avoidable simulation-competition failure mode.</div></div>

## cell [14] — code

## cell [15] — code

## cell [16] — markdown

### Market pressure in motion

<div class="kg-prose"><div class="lead">The queue layer exists because shared-market price is not constant. Selling increases market inventory, which can push later units onto a lower part of the price curve. With duplicate shops, recovery can also be heavily concentrated in a few products, so same-turn SELL priority uses both nonlinear price impact and the <b>observed town composition</b>.</div></div>

<div class="kg-note violet"><div class="title">What to watch</div><div class="body">The left curve shows the modeled quote as more units reach the market; the right curve shows cumulative revenue. Planned SELL slots keep their quantities and are ranked by queue damage. Separately, WOOL can be released when its live price or storage pressure justifies it. A FERTILIZER timing shift is allowed only after the three-checkpoint mirror gate. Near mirrors use a 3-turn lead; very-close mirrors use 4 turns, always with exact later repayment.</div></div>

## cell [17] — code

## cell [18] — markdown

## 8. Full 720-turn runtime validation

<div class="kg-prose"><div class="lead">A simulation agent is only useful if the exact file intended for submission completes the entire season. The check below runs <code>main.py</code> for both seats through all 720 turns, verifies terminal money, and records whether the controller actually exercised farm and market actions.</div></div>

<div class="kg-grid">
  <div class="kg-card green"><div class="eyebrow">What this proves</div><b>The packaged controller runs end to end.</b><br><span>We require 720 turns, two <code>DONE</code> states, finite positive terminal banks, active farm work, and market orders.</span></div>
  <div class="kg-card violet"><div class="eyebrow">What this does not prove</div><b>Self-play is not a leaderboard estimate.</b><br><span>It is a runtime and symmetry check. Competitive selection should use multiple seeds, both seats, and diverse opponents outside this public presentation.</span></div>
</div>

<div class="kg-note"><div class="title">Validation discipline</div><div class="body">The public notebook validates the exact source that is later archived. Development experiments were screened separately; candidate overlays were promoted only after fixed tuning seeds, untouched holdout seeds, both seats, and diverse regression opponents were checked in the current environment. The published controller uses a conservative two-tier relay: 3 turns for ordinary near mirrors and 4 turns only when all three checkpoints satisfy the stricter distance gate. Broader timing changes are not part of the submitted source.</div></div>

<div class="kg-prose"><div class="micro">The environment receives the absolute path of the generated <code>main.py</code> for both seats, matching the file-based agent workflow used by the competition.</div></div>

## cell [19] — code

## cell [20] — markdown

## 9. Season diagnostics: does the mechanism match the story?

<div class="kg-prose"><div class="lead">These plots explain the controller; they are not leaderboard claims. The faint <b>BUILD / SCALE / PROTECT / CLOSE</b> bands connect each trace back to the season atlas, so capital, market, and capacity changes can be read in the same strategic clock.</div></div>

<div class="kg-grid">
  <div class="kg-card gold"><div class="eyebrow">Capital trace</div><b>Cash has a job before the deadline.</b><br><span>A falling bank can be healthy when it becomes productive capacity early enough to earn its way back before turn 720.</span></div>
  <div class="kg-card teal"><div class="eyebrow">Market trace</div><b>Quotes are moving state, not constants.</b><br><span>Because sales influence a shared market, “best product” is conditional on timing, inventory, and which order is placed first.</span></div>
  <div class="kg-card green"><div class="eyebrow">Capacity trace</div><b>Assets matter only when operations can service them.</b><br><span>Plants, animals, and land are useful only if labor, routes, feed, water, and collection cadence keep them productive.</span></div>
  <div class="kg-card violet"><div class="eyebrow">Action mix</div><b>The policy is an operating system, not one trick.</b><br><span>Movement, crop work, livestock care, logistics, purchases, and sales all consume scarce turns and must fit the same seasonal clock.</span></div>
</div>

<div class="kg-note teal"><div class="title">A useful replay-reading habit</div><div class="body">Do not inspect only the final bank. Look for <b>causal sequences</b>: a land or labor purchase should be followed by more serviced production; a price collapse should change the value of later sales; an execution repair should return to the planned route rather than create a new wandering policy.</div></div>

<div class="kg-note violet"><div class="title">Replay the farm, not just four snapshots</div><div class="body">The topology panel at the top compresses all 720 turns into one moving map. Tile colors show production state while the large white marker follows the farmer and the smaller teal markers follow hired hands. Watch expansion, routing pressure, stochastic weeds, and the shift into closeout as one continuous process.</div></div>

## cell [21] — code

## cell [22] — code

## cell [23] — code

## cell [24] — code

## cell [25] — markdown

## 10. Mental model of one turn

<div class="kg-terminal">
<span class="dim">live observation</span><br>
&nbsp;&nbsp;↓<br>
read the coordinated season action<br>
&nbsp;&nbsp;↓<br>
repair an actor-local WEED obstruction when needed<br>
&nbsp;&nbsp;↓<br>
apply the town-gated livestock branch during its narrow window<br>
&nbsp;&nbsp;↓<br>
release WOOL only when price, storage pressure, spacing, or deadline logic allows it<br>
&nbsp;&nbsp;↓<br>
rank existing SELL slots by <b>price impact + live demand urgency</b><br>
&nbsp;&nbsp;↓<br>
at three fixed checkpoints, test whether the public farms remain near mirrors<br>
&nbsp;&nbsp;↓<br>
if near-mirror locked, use <b>t+3 → t</b>; if the stricter mirror gate also locks, use <b>t+4 → t</b><br>
&nbsp;&nbsp;↓<br>
record the executed quantity as debt and subtract it exactly when due<br>
&nbsp;&nbsp;↓<br>
return farmer + hands + market orders
</div>

<div class="kg-note"><div class="title">Reusable design principle</div><div class="body">A strong runtime layer should have a <b>small blast radius</b>. The route handles capital and logistics; WEED repair protects physical execution; the town and WOOL branches react to durable public signals; SELL ranking protects the shared queue; and the relay changes only the timing of a scheduled FERTILIZER quantity, choosing one of two tightly gated horizons with explicit debt accounting.</div></div>

## cell [26] — markdown

## 11. Build, inspect, and rerun the submission archive

<div class="kg-prose"><div class="lead">The archive must contain exactly one root-level file: <code>main.py</code>. More importantly, the bytes inside the archive must be the bytes we already compiled and executed.</div></div>

<div class="kg-terminal">
<span class="dim">main.py source</span> → compile → 720-turn run → SHA-256<br>
&nbsp;&nbsp;&nbsp;&nbsp;↓<br>
deterministic <b>submission.tar.gz</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;↓<br>
extract exact bytes → hash match → compile again → fresh 720-turn run
</div>

<div class="kg-note gold"><div class="title">Why validate the archive twice?</div><div class="body">A notebook can execute one source file while the submission archive accidentally contains stale bytes. Byte matching plus a fresh run after extraction closes that gap and verifies the artifact that will actually be uploaded.</div></div>

## cell [27] — code

## cell [28] — markdown

## 12. Submit and continue improving

<div class="kg-prose"><ol>
<li>Run the notebook from top to bottom.</li>
<li>Confirm the full-season validation shows two <code>DONE</code> rows, positive terminal banks, active farm work, and active market orders.</li>
<li>Confirm the archive validation passes byte matching, syntax compilation, and a fresh 720-turn archive run.</li>
<li>Submit <code>submission.tar.gz</code>.</li>
</ol></div>

<div class="kg-note violet"><div class="title">What this notebook teaches</div><div class="body">The central lesson is selective adaptation. A strong full-season route remains the production engine. Local repair handles physical shocks; town composition can justify one livestock branch; WOOL release reacts to live economics; SELL ranking handles nonlinear queue damage; and a three-checkpoint near-mirror detector enables a debt-accounted FERTILIZER relay, with a stricter second gate deciding whether the lead is three or four turns. Further changes should keep this blast radius small and survive both-seat holdout tests.</div></div>
