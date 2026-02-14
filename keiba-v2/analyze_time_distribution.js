/**
 * 4Fタイム分布分析スクリプト（美浦/栗東 × 坂路/コース別）
 *
 * CK_DATAから2023年10月以降のデータを読み取り、
 * 4カテゴリ別のパーセンタイル分布を算出する。
 *
 * Usage: node analyze_time_distribution.js
 */

const fs = require('fs');
const path = require('path');

const CK_DATA_PATH = 'C:/TFJV/CK_DATA';

// 4カテゴリの分布を格納
const distributions = {
  'Miho_sakamichi': [],    // 美浦坂路 (HC0)
  'Ritto_sakamichi': [],   // 栗東坂路 (HC1)
  'Miho_course': [],       // 美浦コース (WC0)
  'Ritto_course': [],      // 栗東コース (WC1)
};

function formatTime(raw) {
  if (!raw || raw.length < 3) return NaN;
  const val = parseInt(raw, 10);
  if (isNaN(val) || val === 0) return NaN;
  return val / 10;
}

function processHcFile(filePath, location) {
  const content = fs.readFileSync(filePath, 'ascii');
  const lines = content.split('\r\n');

  const key = `${location}_sakamichi`;
  let count = 0;

  for (const line of lines) {
    if (line.length < 40) continue;
    const rt = line.charAt(0);
    if (rt !== '0' && rt !== '1') continue;

    // HC: offset 23-26 = 4F time
    const time4fRaw = line.substring(23, 27);
    const t4f = formatTime(time4fRaw);

    if (!isNaN(t4f) && t4f > 0 && t4f < 80) {
      distributions[key].push(t4f);
      count++;
    }
  }
  return count;
}

function processWcFile(filePath, location) {
  const content = fs.readFileSync(filePath, 'ascii');
  const lines = content.split('\r\n');

  const key = `${location}_course`;
  let count = 0;

  for (const line of lines) {
    if (line.length < 70) continue;
    const rt = line.charAt(0);
    if (rt !== '0' && rt !== '1') continue;

    // WC: 末尾から逆算 offset[-24..-21] = 4F time
    const len = line.length;
    const time4fRaw = line.substring(len - 24, len - 20);
    const t4f = formatTime(time4fRaw);

    if (!isNaN(t4f) && t4f > 0 && t4f < 80) {
      distributions[key].push(t4f);
      count++;
    }
  }
  return count;
}

// 2023年10月以降のファイルを処理
console.log('=== CK_DATA 4F Time Distribution Analysis ===');
console.log('Period: 2023-10 to present (post-Miho renovation)');
console.log('');

let totalFiles = 0;
let totalRecords = 0;

const years = fs.readdirSync(CK_DATA_PATH).filter(d => /^\d{4}$/.test(d)).sort();
for (const year of years) {
  const yearDir = path.join(CK_DATA_PATH, year);
  const months = fs.readdirSync(yearDir).filter(d => /^\d{6}$/.test(d)).sort();

  for (const yearMonth of months) {
    // 2023年10月以降のみ
    if (yearMonth < '202310') continue;

    const monthDir = path.join(yearDir, yearMonth);
    const files = fs.readdirSync(monthDir).filter(f => f.endsWith('.DAT'));

    for (const file of files) {
      const filePath = path.join(monthDir, file);
      const match = file.match(/^(WC|HC)([01])\d{8}\.DAT$/i);
      if (!match) continue;

      const type = match[1].toUpperCase();
      const locCode = match[2];
      const location = locCode === '0' ? 'Miho' : 'Ritto';

      let count = 0;
      if (type === 'HC') {
        count = processHcFile(filePath, location);
      } else {
        count = processWcFile(filePath, location);
      }

      totalFiles++;
      totalRecords += count;
    }
  }
}

console.log(`Files processed: ${totalFiles}`);
console.log(`Total records with valid 4F time: ${totalRecords}`);
console.log('');

// 各カテゴリの統計量を算出
for (const [key, values] of Object.entries(distributions)) {
  if (values.length === 0) {
    console.log(`${key}: no data`);
    continue;
  }

  values.sort((a, b) => a - b);
  const n = values.length;

  // 基本統計量
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const std = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / n);
  const min = values[0];
  const max = values[n - 1];

  // パーセンタイル
  const pct = (p) => values[Math.floor(n * p / 100)];

  // 強め調教のみ（60秒以下）のフィルタ
  const strongWork = values.filter(v => v <= 60);
  const sw = strongWork.length;
  const swMean = sw > 0 ? strongWork.reduce((s, v) => s + v, 0) / sw : 0;
  const swStd = sw > 0 ? Math.sqrt(strongWork.reduce((s, v) => s + (v - swMean) ** 2, 0) / sw) : 0;
  const swPct = (p) => sw > 0 ? strongWork[Math.floor(sw * p / 100)] : 0;

  console.log(`--- ${key} ---`);
  console.log(`  Total: ${n} records`);
  console.log(`  All data: mean=${mean.toFixed(1)}, std=${std.toFixed(1)}, min=${min.toFixed(1)}, max=${max.toFixed(1)}`);
  console.log(`  Percentiles (all): p5=${pct(5).toFixed(1)}, p10=${pct(10).toFixed(1)}, p25=${pct(25).toFixed(1)}, p50=${pct(50).toFixed(1)}, p75=${pct(75).toFixed(1)}, p90=${pct(90).toFixed(1)}, p95=${pct(95).toFixed(1)}`);
  console.log(`  Strong work (<=60s): ${sw} records (${(sw/n*100).toFixed(1)}%)`);
  if (sw > 0) {
    console.log(`  Strong work: mean=${swMean.toFixed(1)}, std=${swStd.toFixed(1)}`);
    console.log(`  Strong work percentiles: p5=${swPct(5).toFixed(1)}, p10=${swPct(10).toFixed(1)}, p20=${swPct(20).toFixed(1)}, p30=${swPct(30).toFixed(1)}, p40=${swPct(40).toFixed(1)}, p50=${swPct(50).toFixed(1)}, p60=${swPct(60).toFixed(1)}, p70=${swPct(70).toFixed(1)}, p80=${swPct(80).toFixed(1)}, p90=${swPct(90).toFixed(1)}`);
  }
  console.log('');

  // 好タイム閾値候補の分布
  console.log(`  Time level distribution (strong work only):`);
  const thresholds_sakamichi_ritto = [51.0, 53.0, 54.5, 56.0]; // 仮の栗東坂路閾値
  const thresholds_sakamichi_miho = [51.0, 53.0, 54.5, 56.0];  // 仮の美浦坂路閾値
  const thresholds_course = [49.0, 51.0, 52.5, 54.0];           // 仮のコース閾値

  // 1秒刻みのヒストグラム
  const histogram = {};
  for (const v of strongWork) {
    const bucket = Math.floor(v);
    histogram[bucket] = (histogram[bucket] || 0) + 1;
  }

  const buckets = Object.keys(histogram).map(Number).sort((a, b) => a - b);
  let cumPct = 0;
  for (const bucket of buckets) {
    const count = histogram[bucket];
    const pctOfStrong = (count / sw * 100);
    cumPct += pctOfStrong;
    const bar = '#'.repeat(Math.round(pctOfStrong));
    console.log(`    ${bucket}s: ${count} (${pctOfStrong.toFixed(1)}%, cum=${cumPct.toFixed(1)}%) ${bar}`);
  }
  console.log('');
}

// 5段階閾値の提案
console.log('=== Proposed 5-Level Thresholds ===');
console.log('');

for (const [key, values] of Object.entries(distributions)) {
  if (values.length === 0) continue;

  const strongWork = values.filter(v => v <= 60).sort((a, b) => a - b);
  if (strongWork.length === 0) continue;

  const sw = strongWork.length;
  const swPct = (p) => strongWork[Math.floor(sw * p / 100)];

  // 5段階: Level 5 (top ~5%) > Level 4 (5-20%) > Level 3 (20-50%) > Level 2 (50-80%) > Level 1 (80%+)
  const t5 = swPct(5);   // top 5%
  const t4 = swPct(20);  // top 20%
  const t3 = swPct(50);  // median
  const t2 = swPct(80);  // bottom 20%

  console.log(`${key}:`);
  console.log(`  Level 5 (top ~5%):  <= ${t5.toFixed(1)}s`);
  console.log(`  Level 4 (5-20%):    <= ${t4.toFixed(1)}s`);
  console.log(`  Level 3 (20-50%):   <= ${t3.toFixed(1)}s`);
  console.log(`  Level 2 (50-80%):   <= ${t2.toFixed(1)}s`);
  console.log(`  Level 1 (bottom):   > ${t2.toFixed(1)}s`);
  console.log('');
}
