#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Feature Lab レポート生成器 (Session 177・段階方式の第1段=自己完結HTML)

3歳上芝OP+ 専用モデルの特徴量開発過程を可視化する HTML を生成する。
読込: ablation_age3up_op_{w,p}.json / training_report_spec_{w,p}.json / iteration_log.json
出力: data3/ml/nova/turf_op/feature_lab.html (Chart.js CDN・ブラウザで開くだけ)

4ビュー: ①学習曲線(累積) ②グループ単独パワー ③特徴量インベントリ表 ④開発タイムライン

Usage: python -m ml.nova.feature_lab_report
将来: 価値確認後 web/src/app/analysis/feature-lab/ へ移植 (同じ JSON を読む)
"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import config
from ml.nova.ablation_turf_op import assign_groups, GROUP_ORDER

DIR = config.ml_dir() / "nova" / "turf_op"
LEAN_PLUS = {"basic", "form_level", "trajectory", "jrdb_idm", "jrdb_cid",
             "jrdb_other", "jockey", "pace", "class_ctx"}
# グループ色 (視認性)
GCOLOR = {
    "basic": "#94a3b8", "form_level": "#60a5fa", "trajectory": "#ef4444",
    "speed_idx": "#a78bfa", "jrdb_idm": "#34d399", "jrdb_cid": "#f59e0b",
    "jrdb_other": "#10b981", "training": "#fbbf24", "jockey": "#3b82f6",
    "trainer": "#64748b", "pedigree": "#9ca3af", "pace": "#22d3ee",
    "track_bias": "#84cc16", "class_ctx": "#ec4899", "comments": "#c084fc",
    "closing": "#fb923c", "misc": "#cbd5e1",
}

def load(name):
    p = DIR / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

def feature_inventory(target):
    """target の spec モデル importance + group + lean フラグ。"""
    rep = load(f"training_report_spec_{target}.json")
    if not rep:
        return []
    imp = rep.get("importance", {})
    total = sum(imp.values()) or 1.0
    # group assignment over the model's features
    feats = list(imp.keys())
    groups = assign_groups(feats)
    f2g = {f: g for g, fl in groups.items() for f in fl}
    rows = []
    for f, v in imp.items():
        g = f2g.get(f, "misc")
        rows.append({"feat": f, "group": g, "gain": round(v / total * 100, 2),
                     "lean": g in LEAN_PLUS})
    rows.sort(key=lambda r: -r["gain"])
    return rows

def build_payload():
    P = {"targets": {}, "iterations": load("iteration_log.json") or {}, "lean_plus": sorted(LEAN_PLUS),
         "gcolor": GCOLOR}
    for t in ["w", "p"]:
        abl = load(f"ablation_age3up_op_{t}.json")
        block = {"ablation": abl, "inventory": feature_inventory(t)}
        P["targets"][t] = block
    return P

HTML = """<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8">
<title>Feature Lab — Regulus（3歳上芝OP+ 専用モデル）</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
 body{font-family:system-ui,'Segoe UI',sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
 .wrap{max-width:1100px;margin:0 auto;padding:24px}
 h1{font-size:22px} h2{font-size:17px;margin-top:28px;border-left:4px solid #ef4444;padding-left:10px}
 h3{font-size:14px;color:#94a3b8;margin:14px 0 6px}
 .card{background:#1e293b;border-radius:10px;padding:16px;margin:12px 0}
 .row{display:flex;gap:16px;flex-wrap:wrap} .col{flex:1;min-width:340px}
 table{border-collapse:collapse;width:100%;font-size:12px}
 th,td{padding:4px 8px;text-align:right;border-bottom:1px solid #334155}
 th:first-child,td:first-child{text-align:left}
 .chip{display:inline-block;padding:1px 7px;border-radius:6px;font-size:11px;color:#0f172a;font-weight:600}
 .lean{color:#34d399;font-weight:700} .nolean{color:#64748b}
 .note{color:#94a3b8;font-size:12px} .pos{color:#34d399} .neg{color:#f87171}
 canvas{background:#0b1220;border-radius:8px;padding:6px}
 .tl{border-left:2px solid #334155;margin-left:8px;padding-left:14px}
 .tl-item{margin:8px 0;font-size:13px} .tag{font-size:10px;padding:1px 6px;border-radius:5px;background:#334155}
 .scroll{max-height:520px;overflow:auto}
</style></head><body><div class="wrap">
<h1>🔬 Feature Lab — ⭐ Regulus（3歳以上 芝オープン以上 専用モデル）</h1>
<p class="note">経験豊富な上位馬の対決に最適化した専用モデルの特徴量開発を可視化。AUC=識別力(主指標)。ROI/勝率は611R単発でノイズ大。<span id="meta"></span></p>
<div id="root"></div>
</div>
<script>const DATA = %%PAYLOAD%%;</script>
<script>
const $=h=>{const d=document.createElement('div');d.innerHTML=h;return d.firstElementChild;};
const root=document.getElementById('root');
function curveCard(t,abl){
  const cum=Object.entries(abl.cumulative);
  const labels=cum.map(([g])=> '+'+g);
  const auc=cum.map(([,r])=>r.auc), roi=cum.map(([,r])=>r.roi);
  const id='cv_'+t;
  const card=$(`<div class="card"><h3>① 学習曲線（basic から累積追加）</h3><canvas id="${id}" height="150"></canvas></div>`);
  root.appendChild(card);
  new Chart(document.getElementById(id),{data:{labels,datasets:[
    {type:'line',label:'AUC',data:auc,borderColor:'#ef4444',yAxisID:'y',tension:.2,pointRadius:3},
    {type:'bar',label:'ROI %',data:roi,backgroundColor:'rgba(34,211,238,.35)',yAxisID:'y1'}]},
    options:{plugins:{legend:{labels:{color:'#e2e8f0'}}},
    scales:{x:{ticks:{color:'#94a3b8',maxRotation:60,minRotation:60,font:{size:9}}},
    y:{position:'left',ticks:{color:'#ef4444'},title:{display:true,text:'AUC',color:'#ef4444'}},
    y1:{position:'right',ticks:{color:'#22d3ee'},grid:{drawOnChartArea:false},title:{display:true,text:'ROI%',color:'#22d3ee'}}}}});
}
function soloCard(t,abl){
  const solo=abl.solo, base=solo.basic_only.auc;
  const ent=Object.entries(solo).filter(([k])=>k!=='basic_only')
     .map(([g,r])=>[g,+(r.auc-base).toFixed(4)]).sort((a,b)=>b[1]-a[1]);
  const id='so_'+t;
  const card=$(`<div class="card"><h3>② グループ単独パワー（basic+各G の AUC上昇, basic=${base.toFixed(4)}）</h3><canvas id="${id}" height="150"></canvas></div>`);
  root.appendChild(card);
  new Chart(document.getElementById(id),{type:'bar',
    data:{labels:ent.map(e=>e[0]),datasets:[{label:'ΔAUC vs basic',data:ent.map(e=>e[1]),
      backgroundColor:ent.map(e=>DATA.gcolor[e[0]]||'#64748b')}]},
    options:{indexAxis:'y',plugins:{legend:{display:false}},
    scales:{x:{ticks:{color:'#94a3b8'}},y:{ticks:{color:'#e2e8f0',font:{size:10}}}}}});
}
function invCard(t,inv){
  let rows=inv.slice(0,40).map(r=>`<tr><td>${r.feat}</td>
    <td><span class="chip" style="background:${DATA.gcolor[r.group]||'#64748b'}">${r.group}</span></td>
    <td>${r.gain.toFixed(2)}%</td><td class="${r.lean?'lean':'nolean'}">${r.lean?'✓':'—'}</td></tr>`).join('');
  root.appendChild($(`<div class="card"><h3>③ 特徴量インベントリ（重要度上位40 / spec ${t.toUpperCase()}モデル）</h3>
    <div class="scroll"><table><thead><tr><th>特徴量</th><th>グループ</th><th>gain%</th><th>lean入</th></tr></thead>
    <tbody>${rows}</tbody></table></div></div>`));
}
function timeline(){
  const its=(DATA.iterations.iterations)||[];
  const byT={w:[],p:[]}; its.forEach(i=>byT[(i.target||'w').toLowerCase()]?.push(i));
  let html='<div class="card"><h3>④ 開発タイムライン（積み上げの記録）</h3><div class="row">';
  for(const t of ['w','p']){
    html+=`<div class="col"><b>${t.toUpperCase()}</b><div class="tl">`;
    byT[t].forEach(i=>{html+=`<div class="tl-item"><span class="tag">${i.phase}</span> <b>${i.label}</b>
      — AUC <b>${i.auc}</b> / ${i.n_feats}feat / ROI ${i.roi}% <div class="note">${i.note||''}</div></div>`;});
    html+='</div></div>';
  }
  html+='</div></div>';
  root.appendChild($(html));
}
// render
for(const t of ['w','p']){
  const blk=DATA.targets[t]; if(!blk||!blk.ablation) continue;
  root.appendChild($(`<h2>${t==='w'?'単勝 (W / is_win)':'複勝 (P / is_top3)'} — 全特徴量 AUC ${blk.ablation.full.auc.toFixed(4)} (n=${blk.ablation.full.n_feats})</h2>`));
  const r=$('<div class="row"></div>'); root.appendChild(r);
  curveCard(t,blk.ablation); soloCard(t,blk.ablation); invCard(t,blk.inventory);
}
timeline();
</script></body></html>"""

def main():
    payload = build_payload()
    html = HTML.replace("%%PAYLOAD%%", json.dumps(payload, ensure_ascii=False))
    out = DIR / "feature_lab.html"
    out.write_text(html, encoding="utf-8")
    print(f"[Done] wrote {out}  ({len(html):,} bytes)")
    # quick sanity
    for t in ["w", "p"]:
        abl = payload["targets"][t].get("ablation")
        inv = payload["targets"][t].get("inventory")
        print(f"  {t}: ablation={'OK' if abl else 'MISSING'}  inventory_rows={len(inv) if inv else 0}")

if __name__ == "__main__":
    main()
