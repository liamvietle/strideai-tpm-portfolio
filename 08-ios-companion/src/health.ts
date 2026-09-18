import {
  CategoryValueSleepAnalysis,
  isHealthDataAvailable,
  queryCategorySamples,
  queryQuantitySamples,
  requestAuthorization,
} from '@kingstinct/react-native-healthkit';

const HEALTH_TYPES = [
  'HKCategoryTypeIdentifierSleepAnalysis',
  'HKQuantityTypeIdentifierRestingHeartRate',
  'HKQuantityTypeIdentifierHeartRateVariabilitySDNN',
] as const;

type Interval = { start: number; end: number };
type DailyDraft = {
  sleep: Interval[];
  hrv: number[];
  restingHr: { value: number; time: number }[];
  sources: Set<string>;
  sleepSamples: number;
};

export type DailyHealthSummary = {
  date: string;
  timezone: string;
  sleep_hours: number | null;
  sleep_sample_count: number;
  hrv_ms: number | null;
  hrv_sample_count: number;
  resting_hr_bpm: number | null;
  resting_hr_sample_count: number;
  source_names: string[];
};

function dateKey(value: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}

function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  if (sorted.length % 2) return sorted[middle] ?? null;
  const left = sorted[middle - 1];
  const right = sorted[middle];
  return left == null || right == null ? null : (left + right) / 2;
}

function unionHours(intervals: Interval[]): number | null {
  if (!intervals.length) return null;
  const sorted = [...intervals].sort((a, b) => a.start - b.start);
  let start = sorted[0]?.start ?? 0;
  let end = sorted[0]?.end ?? 0;
  let total = 0;
  for (const interval of sorted.slice(1)) {
    if (interval.start <= end) {
      end = Math.max(end, interval.end);
    } else {
      total += Math.max(0, end - start);
      start = interval.start;
      end = interval.end;
    }
  }
  total += Math.max(0, end - start);
  return Math.round((total / 3_600_000) * 10_000) / 10_000;
}

function sourceName(sample: { sourceRevision?: { source?: { name?: string } } }): string | null {
  return sample.sourceRevision?.source?.name?.trim() || null;
}

export async function readDailyHealth(daysBack = 35): Promise<DailyHealthSummary[]> {
  if (!(await isHealthDataAvailable())) {
    throw new Error('Apple Health is not available on this device.');
  }

  await requestAuthorization({ toRead: [...HEALTH_TYPES] });

  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const endDate = new Date();
  const startDate = new Date(endDate);
  startDate.setDate(startDate.getDate() - daysBack);
  const options = {
    limit: 0,
    ascending: true,
    filter: { date: { startDate, endDate, strictStartDate: false, strictEndDate: false } },
  } as const;

  const [sleep, hrv, restingHr] = await Promise.all([
    queryCategorySamples('HKCategoryTypeIdentifierSleepAnalysis', options),
    queryQuantitySamples('HKQuantityTypeIdentifierHeartRateVariabilitySDNN', { ...options, unit: 'ms' }),
    queryQuantitySamples('HKQuantityTypeIdentifierRestingHeartRate', { ...options, unit: 'count/min' }),
  ]);

  const drafts = new Map<string, DailyDraft>();
  const draft = (key: string) => {
    let value = drafts.get(key);
    if (!value) {
      value = { sleep: [], hrv: [], restingHr: [], sources: new Set(), sleepSamples: 0 };
      drafts.set(key, value);
    }
    return value;
  };
  const asleepValues = new Set<number>([
    CategoryValueSleepAnalysis.asleep,
    CategoryValueSleepAnalysis.asleepUnspecified,
    CategoryValueSleepAnalysis.asleepCore,
    CategoryValueSleepAnalysis.asleepDeep,
    CategoryValueSleepAnalysis.asleepREM,
  ]);

  for (const sample of sleep) {
    if (!asleepValues.has(Number(sample.value))) continue;
    const start = new Date(sample.startDate);
    const end = new Date(sample.endDate);
    if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) continue;
    const item = draft(dateKey(end, timezone));
    item.sleep.push({ start: start.getTime(), end: end.getTime() });
    item.sleepSamples += 1;
    const source = sourceName(sample);
    if (source) item.sources.add(source);
  }

  for (const sample of hrv) {
    if (!Number.isFinite(sample.quantity) || sample.quantity < 0) continue;
    const item = draft(dateKey(new Date(sample.startDate), timezone));
    item.hrv.push(sample.quantity);
    const source = sourceName(sample);
    if (source) item.sources.add(source);
  }

  for (const sample of restingHr) {
    if (!Number.isFinite(sample.quantity) || sample.quantity <= 0) continue;
    const time = new Date(sample.endDate).getTime();
    const item = draft(dateKey(new Date(sample.startDate), timezone));
    item.restingHr.push({ value: sample.quantity, time });
    const source = sourceName(sample);
    if (source) item.sources.add(source);
  }

  return [...drafts.entries()]
    .map(([day, item]) => {
      const latestRhr = [...item.restingHr].sort((a, b) => b.time - a.time)[0];
      return {
        date: day,
        timezone,
        sleep_hours: unionHours(item.sleep),
        sleep_sample_count: item.sleepSamples,
        hrv_ms: median(item.hrv),
        hrv_sample_count: item.hrv.length,
        resting_hr_bpm: latestRhr?.value ?? null,
        resting_hr_sample_count: item.restingHr.length,
        source_names: [...item.sources].sort(),
      };
    })
    .filter((item) => item.sleep_hours != null || item.hrv_ms != null || item.resting_hr_bpm != null)
    .sort((a, b) => a.date.localeCompare(b.date));
}
