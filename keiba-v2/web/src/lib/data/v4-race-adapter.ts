/**
 * v4レースデータ + keibabook拡張 → IntegratedRaceData アダプター
 *
 * v4のJRA-VANネイティブデータとkeibabook拡張データを結合し、
 * 既存のIntegratedRaceDataインターフェースに変換する。
 * これにより既存の15+コンポーネントを変更なしで使い続けられる。
 */

import type {
  IntegratedRaceData,
  HorseEntry,
  EntryData,
  TrainingData,
  StableComment,
  RaceResult,
  PreviousRaceInterview,
  RaceInfo,
  RaceMeta,
  RaceAnalysis,
  TenkaiData,
  PaddockInfo,
  PastPerformances,
  HistoryFeatures,
} from '@/types/race-data';
import type { V4RaceData, V4RaceEntry } from './v4-race-reader';
import type { KbExtData, KbEntryExt } from './v4-keibabook-reader';

/**
 * v4レースデータ + keibabook拡張 → IntegratedRaceData変換
 *
 * data2Fallback が提供された場合、v4/kbExtに含まれない情報
 * （レース名、血統、パドック、払戻等）をdata2から補完する。
 */
export function adaptV4ToIntegrated(
  v4Race: V4RaceData,
  kbExt: KbExtData | null,
  data2Fallback?: IntegratedRaceData | null,
): IntegratedRaceData {
  const trackMap: Record<string, string> = {
    turf: '芝',
    dirt: 'ダ',
  };

  const meta: RaceMeta = {
    race_id: v4Race.race_id,
    data_version: 'v4',
    created_at: '',
    updated_at: '',
    data_sources: { seiseki: '', syutuba: '', cyokyo: '', danwa: '', nittei: '', syoin: '', paddok: '' },
  };

  const raceInfo: RaceInfo = {
    date: v4Race.date,
    venue: v4Race.venue_name,
    race_number: v4Race.race_number,
    race_name: '',
    grade: '',
    distance: v4Race.distance,
    track: trackMap[v4Race.track_type] ?? v4Race.track_type,
    direction: '',
    weather: '',
    track_condition: v4Race.track_condition,
    post_time: '',
    race_condition: '',
  };

  const entries: HorseEntry[] = v4Race.entries.map((e) => {
    const kb = kbExt?.entries[String(e.umaban)] ?? null;
    return adaptEntry(e, kb);
  });

  const analysis: RaceAnalysis = {
    expected_pace: kbExt?.analysis?.expected_pace ?? '',
    favorites: [],
    training_highlights: [],
    entry_count: v4Race.num_runners,
  };

  const tenkaiData: TenkaiData | null = kbExt?.tenkai_data
    ? {
        pace: kbExt.tenkai_data.pace,
        positions: {
          逃げ: kbExt.tenkai_data.positions['逃げ'] ?? [],
          好位: kbExt.tenkai_data.positions['好位'] ?? [],
          中位: kbExt.tenkai_data.positions['中位'] ?? [],
          後方: kbExt.tenkai_data.positions['後方'] ?? [],
        },
      }
    : null;

  const result: IntegratedRaceData = {
    meta,
    race_info: raceInfo,
    entries,
    payouts: null,
    laps: null,
    analysis,
    tenkai_data: tenkaiData,
    race_comment: kbExt?.race_comment ?? '',
  };

  // data2からの補完（v4/kbExtに含まれない情報をエンリッチ）
  if (data2Fallback) {
    enrichFromData2(result, data2Fallback);
  }

  return result;
}

/**
 * data2(integrated JSON)からv4結果に不足情報を補完
 */
function enrichFromData2(result: IntegratedRaceData, d2: IntegratedRaceData): void {
  // レース情報の補完
  const ri = result.race_info;
  const d2ri = d2.race_info;
  if (!ri.race_name && d2ri.race_name) ri.race_name = d2ri.race_name;
  if (!ri.grade && d2ri.grade) ri.grade = d2ri.grade;
  if (!ri.race_condition && d2ri.race_condition) ri.race_condition = d2ri.race_condition;
  if (!ri.direction && d2ri.direction) ri.direction = d2ri.direction;
  if (!ri.weather && d2ri.weather) ri.weather = d2ri.weather;
  if (!ri.post_time && d2ri.post_time) ri.post_time = d2ri.post_time;
  if (!ri.start_time && d2ri.start_time) ri.start_time = d2ri.start_time;
  if (!ri.start_at && d2ri.start_at) ri.start_at = d2ri.start_at;

  // エントリの補完（horse_numberでマッチ）
  const d2Map = new Map(d2.entries.map(e => [e.horse_number, e]));
  for (const entry of result.entries) {
    const d2e = d2Map.get(entry.horse_number);
    if (!d2e) continue;

    // 血統情報
    if (!entry.entry_data.father && d2e.entry_data.father) {
      entry.entry_data.father = d2e.entry_data.father;
    }
    if (!entry.entry_data.mother && d2e.entry_data.mother) {
      entry.entry_data.mother = d2e.entry_data.mother;
    }
    if (!entry.entry_data.mother_father && d2e.entry_data.mother_father) {
      entry.entry_data.mother_father = d2e.entry_data.mother_father;
    }

    // 調教師情報の補完
    if (!entry.entry_data.trainer_tozai && d2e.entry_data.trainer_tozai) {
      entry.entry_data.trainer_tozai = d2e.entry_data.trainer_tozai;
    }
    if (!entry.entry_data.weight_diff && d2e.entry_data.weight_diff) {
      entry.entry_data.weight_diff = d2e.entry_data.weight_diff;
    }

    // パドック情報
    if (!entry.paddock_info && d2e.paddock_info) {
      entry.paddock_info = d2e.paddock_info;
    }

    // 過去成績
    if (entry.past_performances.total_races === 0 && d2e.past_performances.total_races > 0) {
      entry.past_performances = d2e.past_performances;
    }

    // history_features
    if (!entry.history_features && d2e.history_features) {
      entry.history_features = d2e.history_features;
    }
  }

  // 払戻・ラップ
  if (!result.payouts && d2.payouts) result.payouts = d2.payouts;
  if (!result.laps && d2.laps) result.laps = d2.laps;

  // レースコメント（空の場合のみ補完）
  if (!result.race_comment && d2.race_comment) {
    result.race_comment = d2.race_comment;
  }
}

function adaptEntry(v4: V4RaceEntry, kb: KbEntryExt | null): HorseEntry {
  const entryData: EntryData = {
    weight: String(v4.futan),
    weight_diff: '',
    jockey: v4.jockey_name,
    jockey_id: v4.jockey_code,
    trainer: v4.trainer_name,
    trainer_id: v4.trainer_code,
    owner: '',
    short_comment: kb?.short_comment ?? '',
    odds: String(v4.odds),
    odds_rank: String(kb?.odds_rank ?? v4.popularity),
    ai_index: kb?.ai_index != null ? String(kb.ai_index) : '',
    ai_rank: kb?.ai_rank ?? '',
    popularity_index: '',
    age: `${v4.sex_cd === '1' ? '牡' : v4.sex_cd === '2' ? '牝' : 'セ'}${v4.age}`,
    sex: v4.sex_cd === '1' ? '牡' : v4.sex_cd === '2' ? '牝' : 'セ',
    waku: String(v4.wakuban),
    rating: kb?.rating != null ? String(kb.rating) : '',
    horse_weight: String(v4.horse_weight),
    father: '',
    mother: '',
    mother_father: '',
    honshi_mark: kb?.honshi_mark ?? '',
    mark_point: kb?.mark_point ?? 0,
    marks_by_person: kb?.marks_by_person as EntryData['marks_by_person'] ?? { CPU: '', 本誌: '', My印: '', 本紙: '' },
    aggregate_mark_point: kb?.aggregate_mark_point ?? 0,
  };

  const trainingData: TrainingData | null = kb?.training_data
    ? {
        last_training: '',
        training_times: [],
        training_course: '',
        evaluation: kb.training_data.evaluation,
        trainer_comment: '',
        attack_explanation: kb.training_data.attack_explanation,
        short_review: kb.training_data.short_review,
        training_load: kb.training_data.training_load,
        training_rank: kb.training_data.training_rank,
        training_arrow: kb.training_arrow,
      }
    : null;

  const stableComment: StableComment | null = kb?.stable_comment?.comment
    ? { date: '', comment: kb.stable_comment.comment, condition: '', target_race: '', trainer: v4.trainer_name }
    : null;

  const result: RaceResult | null =
    v4.finish_position > 0
      ? {
          finish_position: String(v4.finish_position),
          time: String(v4.time),
          margin: '',
          last_3f: String(v4.last_3f),
          passing_orders: v4.corners.join('-'),
          last_corner_position: v4.corners.length > 0 ? String(v4.corners[v4.corners.length - 1]) : '',
          first_3f: '',
          sunpyo: kb?.sunpyo ?? '',
          prize_money: 0,
          horse_weight: String(v4.horse_weight),
          horse_weight_diff: String(v4.horse_weight_diff),
          raw_data: {} as RaceResult['raw_data'],
        }
      : null;

  const prevInterview: PreviousRaceInterview | null = kb?.previous_race_interview?.interview
    ? {
        jockey: '',
        comment: '',
        interview: kb.previous_race_interview.interview,
        next_race_memo: kb.previous_race_interview.next_race_memo,
        finish_position: '',
        previous_race_mention: '',
      }
    : null;

  const paddockInfo: PaddockInfo | null = null; // Paddock data not available in v4/kb_ext

  const pastPerformances: PastPerformances = {
    total_races: 0,
    wins: 0,
    places: 0,
    shows: 0,
    earnings: 0,
    recent_form: [],
  };

  const historyFeatures: HistoryFeatures | null = null;

  return {
    horse_number: v4.umaban,
    horse_name: v4.horse_name,
    horse_id: v4.ketto_num,
    entry_data: entryData,
    training_data: trainingData,
    stable_comment: stableComment,
    result,
    previous_race_interview: prevInterview,
    paddock_info: paddockInfo,
    past_performances: pastPerformances,
    history_features: historyFeatures,
  };
}
