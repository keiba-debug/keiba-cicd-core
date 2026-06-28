/**
 * レース文脈エンジン — 競馬5冊 ML知見まとめ (Session 178)
 *
 * 競馬5冊(双馬/立川/安井/亀谷/みねた)から抽出した ML特徴量設計と、Regulus(3歳上芝OP+専用)での
 * 検証結果(実装済/NO-GO/未着手)を一覧化した知見ページ。将来の自分への地図。表示専用の参照ページ。
 * 正本docs: keiba-v2/docs/regulus/sources/, docs/ml-experiments/v9.x_turf_op_specialist_phase0.md
 */
import type { Metadata } from 'next';

export const metadata: Metadata = { title: 'レース文脈エンジン（5冊知見）' };

type Status = 'done' | 'nogo' | 'candidate' | 'todo';

const STATUS_META: Record<Status, { label: string; cls: string }> = {
  done: { label: '実装済', cls: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300' },
  nogo: { label: '検証→NO-GO', cls: 'bg-rose-100 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300' },
  candidate: { label: '候補', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300' },
  todo: { label: '未着手', cls: 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400' },
};

function StatusBadge({ s }: { s: Status }) {
  const m = STATUS_META[s];
  return <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-medium whitespace-nowrap ${m.cls}`}>{m.label}</span>;
}

function Section({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="text-lg font-bold mb-1 flex items-baseline gap-2">
        {title}
        {sub && <span className="text-xs font-normal text-muted-foreground">{sub}</span>}
      </h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

// --- 5冊データ ---
const BOOKS = [
  { book: '双馬式 展開読み', author: '双馬毅', axis: '展開(入口)', out: 'テン1F→隊列・想定ペース', note: '体系の上流。展開予測が全部に効く' },
  { book: 'レース質マトリックス(本/実践)', author: '立川優馬', axis: '環境(レース質)', out: '4軸2択ラベル(枠/脚質/ローテ/ペース)', note: 'ルールエンジン+黄金パターン35' },
  { book: '上がりXハロン', author: '安井涼太', axis: '能力', out: 'スピード/スタミナ/パワー 3軸', note: '上がり2F/1F/4F に分解(クラス/馬場/距離で標準化)' },
  { book: 'スマート出馬表', author: '亀谷敬正', axis: 'ノイズ除去/出口', out: '人気ランク別集計・妙味', note: 'バイアス補正・勝率と妙味の分離' },
  { book: '競馬場と前走位置取り', author: 'みねた', axis: '展開の実装版/EV', out: '前走通過順≤3→front_ratio→pace', note: 'JRDB実装容易。期待値選別' },
];

// --- 特徴量カタログ(実装状況) ---
const FEATURES: { name: string; from: string; status: Status; detail: string }[] = [
  { name: '脚質・能力プロファイル (leg_profile)', from: '安井 上がり3軸 + みねた 脚質', status: 'done',
    detail: 'テン力(ten_idx)/上がり力(agari_idx)/持続力(前後半3F)を偏差値化＋脚質(corners)。lap再構成せずJRDB指数で軽量実装。/predictions 出走表タブ列＋/races-v2 展開予想タブに表示。' },
  { name: 'front_ratio (前走3角≤3占有率)', from: 'みねた §1', status: 'done',
    detail: '計算基盤あり(corners・リークフリー)。展開予想の「脚質構成ペース読み」に使用。ただし勝率モデルへの“生足し”はincremental AUC≒0(A)。' },
  { name: '上がり3軸 (speed/stamina/power)', from: '安井 §1', status: 'done',
    detail: 'lap_times再構成版は冗長と判明→JRDB agari_idx/ten_idx＋前後半3Fを直接採用(craft版)。スタミナは「遅い1F=良い」の符号反転に注意。' },
  { name: 'idm_trend_clean (文脈で過去走を掃除)', from: 'Regulus B(立川実践 反レース質)', status: 'nogo',
    detail: '★JRDB IDMが既にペース/トラブル/位置取りで掃除済み(回帰R²=0.9999)→掃除しても素トレンドを超えない(swap全変種+0.005未達)。書籍法の再構成は再発明。' },
  { name: '芝OP+ クラス特化モデル', from: 'Regulus Phase0', status: 'nogo',
    detail: '同特徴量のクラス特化は汎用に精度(AUC)・較正(ECE)で負ける(データ量>クラス純度)。代わりに「何を見るか」を経験馬向けに最適化したlean_plus構成が正解。' },
  { name: 'クラス相対の軌跡', from: 'Regulus B′候補', status: 'candidate',
    detail: '絶対IDMでなく「このOPクラスで上昇中か」の相対トレンド。IDMの文脈掃除は済でも“クラス内相対位置の変化”は未捕捉の可能性。leg_profile上にクラス内偏差値で乗せられる。' },
  { name: 'レース質ラベル (rq_frame/style/rotation/pace)', from: '立川 §1', status: 'todo', detail: '枠/脚質/ローテ/ペースの4軸2択ラベル。golden_pattern_id(条件→ラベル決定表35)と併用。' },
  { name: '馬キャラ (umachara_prob)', from: '立川 §3', status: 'todo', detail: '通過順由来の馬キャラ。能力3軸(上がり由来)とは別系統で両立可。' },
  { name: 'frame_bias_3yr (枠バイアス近3年窓)', from: '立川 実践§4', status: 'todo', detail: '非定常対応。枠バイアスは経年で符号反転(2018-20内→2021外)するため近3年ローリング必須。' },
  { name: 'escape_sandwich (逃げハサミ)', from: 'みねた §3', status: 'todo', detail: '両隣枠が前走先行∧自身非先行→挟まれ消耗。確定枠順+前走で事前計算可。' },
];

// --- 主要な学び ---
const LEARNINGS = [
  { title: 'JRDB IDM は既に文脈で掃除済み', body: 'idm ~ soten + pace_adj + deokure_adj + ichi_tori_adj + furi_adj + race_adj の回帰が R²=0.9999。IDMは「素点＋ペース＋出遅れ＋位置取り＋不利＋レース補正」の恒等式に近い。書籍法がlap_timesから再構成しようとした「ペース文脈割引」はJRDBが既に(より正確に)実施済み。' },
  { title: '“生足し”でなく“掃除/置換”で評価せよ', body: '既存JRDB特徴量と冗長な生特徴量(front_ratio等)を足してもincremental AUCはほぼ0。価値は「市場/既存指標が見ていない残差」にしか宿らない。新特徴量は必ず置換(swap)で純増を測る。' },
  { title: 'OP市場はシャープ＝予想品質に振る', body: '経験豊富な上位馬の対決(芝OP+)は市場較正が効いており、書籍法の掃除に払戻エッジ(残差α)は乗らない。専用モデルの価値は“予想品質・印・説明力”に置く(クラフト価値)。' },
  { title: '非定常性 — 近3年窓・レジーム分割', body: '枠バイアスはコース改修・開催前半/後半・経年で符号反転する。長期固定集計は毒。特徴量化は必ず近年窓で。' },
  { title: '妙味 ≠ 勝率', body: '前走上がり3F1位は勝率に効くが単回収72円(控除率下で負け)＝既に人気に織込済み。勝率モデルと妙味(EV)モデルで特徴量を使い分ける。' },
  { title: '上がり1Fの符号に注意', body: 'スタミナ軸＝「ラスト1Fが遅くても粘れる＝持久力」。素朴に「小さいほど良い」で入れると逆効果になる。' },
];

export default function RaceContextEnginePage() {
  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* ヘッダ */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">📚 レース文脈エンジン</h1>
        <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
          競馬5冊（双馬・立川・安井・亀谷・みねた）から抽出した <b>ML特徴量の設計体系</b> と、
          <b>Regulus（3歳上芝OP+ 専用モデル）</b>での検証結果（実装済 / 検証してNO-GO / 未着手）をまとめた知見ページ。
          「展開で隊列を当て、レース質で有利属性を決め、能力を環境で割り引いて測り、人気ランク別でノイズを除く」を 1つの特徴量体系へ統合する設計。
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
          <StatusBadge s="done" /><StatusBadge s="nogo" /><StatusBadge s="candidate" /><StatusBadge s="todo" />
          <span className="text-muted-foreground self-center ml-1">で実装状況を表示</span>
        </div>
      </div>

      {/* 1. 5冊の役割 */}
      <Section title="1. 競馬5冊の役割" sub="どの軸を担うか">
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-muted/50 text-xs text-muted-foreground text-left">
                <th className="px-3 py-2 border-b">書</th>
                <th className="px-3 py-2 border-b">著者</th>
                <th className="px-3 py-2 border-b">担う軸</th>
                <th className="px-3 py-2 border-b">出力</th>
                <th className="px-3 py-2 border-b">一言</th>
              </tr>
            </thead>
            <tbody>
              {BOOKS.map(b => (
                <tr key={b.book} className="border-b">
                  <td className="px-3 py-2 font-medium whitespace-nowrap">{b.book}</td>
                  <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">{b.author}</td>
                  <td className="px-3 py-2 whitespace-nowrap"><span className="font-semibold">{b.axis}</span></td>
                  <td className="px-3 py-2 text-xs">{b.out}</td>
                  <td className="px-3 py-2 text-xs text-muted-foreground">{b.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* 2. 4層パイプライン */}
      <Section title="2. 因果パイプライン（背骨）" sub="入口から出口へ・上流の展開予測が全体に効く">
        <div className="grid gap-2 sm:grid-cols-4">
          {[
            { n: '①', t: '展開', c: 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950/30', d: 'front_ratio / テン1F → 想定隊列・pace_scenario・lead_side', src: 'みねた/双馬' },
            { n: '②', t: '環境', c: 'border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30', d: '馬場・コース定数・①のpace → レース質4軸2択ラベル', src: '立川' },
            { n: '③', t: '能力', c: 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950/30', d: '上がり2F/1F/4F → スピード/スタミナ/パワー（①paceで脱交絡）', src: '安井' },
            { n: '④', t: '出口', c: 'border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950/30', d: '人気ランク別にノイズ除去 → 勝率と妙味(EV)を分離', src: '亀谷' },
          ].map(s => (
            <div key={s.n} className={`rounded-lg border p-3 ${s.c}`}>
              <div className="text-xs font-bold">{s.n} {s.t} <span className="font-normal text-muted-foreground">({s.src})</span></div>
              <div className="mt-1 text-xs leading-relaxed">{s.d}</div>
            </div>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          キモ：①の <b>pace_scenario</b> が②のペース軸と③の交絡除去の両方に効く。展開予測が体系全体の上流。
        </p>
      </Section>

      {/* 3. 特徴量カタログ */}
      <Section title="3. 特徴量カタログ & 実装状況" sub="何を作り、何を検証してNO-GOにし、何が未着手か">
        <div className="space-y-2">
          {FEATURES.map(f => (
            <div key={f.name} className="rounded-lg border p-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-sm">{f.name}</span>
                <StatusBadge s={f.status} />
                <span className="text-[11px] text-muted-foreground ml-auto">出典: {f.from}</span>
              </div>
              <p className="mt-1.5 text-xs text-muted-foreground leading-relaxed">{f.detail}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* 4. 主要な学び */}
      <Section title="4. 主要な学び" sub="Regulus 検証で得た“高くついた”知見">
        <div className="grid gap-2 sm:grid-cols-2">
          {LEARNINGS.map(l => (
            <div key={l.title} className="rounded-lg border-l-4 border-indigo-400 bg-indigo-50/40 dark:bg-indigo-950/20 pl-3 pr-3 py-2.5">
              <div className="font-semibold text-sm">{l.title}</div>
              <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{l.body}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* footer */}
      <div className="mt-8 pt-4 border-t text-[11px] text-muted-foreground leading-relaxed">
        <p>
          正本ドキュメント: <code>keiba-v2/docs/regulus/sources/</code>（00_integration_5books / 03_agari_x_furlong / 05_course_prev_position_mineta 他）、
          検証レポート <code>docs/ml-experiments/v9.x_turf_op_specialist_phase0.md</code>。
        </p>
        <p className="mt-1">
          脚質・能力プロファイルの実物は <b>予想ページ（出走表タブ）の「脚質/3軸」列</b> と
          <b>レース詳細ページの「展開予想」タブ</b> で確認できる。Regulus = 経験豊富な王者級の馬の対決で軌跡(上昇/下降)を軸に勝ち負けを見抜く専用視点。
        </p>
      </div>
    </div>
  );
}
