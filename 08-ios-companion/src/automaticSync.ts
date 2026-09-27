import * as BackgroundTask from 'expo-background-task';
import * as TaskManager from 'expo-task-manager';
import * as SecureStore from 'expo-secure-store';
import { readDailyHealth, type DailyHealthSummary } from './health';
import { loadSettings, markAuthorized, sendSummaries, type Settings } from './sync';

const TASK = 'strideai-health-sync';
const ENABLED = 'strideai_auto_sync';
const HISTORY = 'strideai_sync_history';
export type SyncHistory = { syncedAt: string; latestDate: string; days: number; source: string; latest?: DailyHealthSummary };
let inFlight: Promise<SyncHistory> | null = null;

export async function loadHistory(): Promise<SyncHistory | null> {
  const raw = await SecureStore.getItemAsync(HISTORY);
  return raw ? JSON.parse(raw) : null;
}
export async function automaticEnabled() {
  return (await SecureStore.getItemAsync(ENABLED)) === 'true';
}
export function performSync(settings: Settings, authorize: boolean, source: string): Promise<SyncHistory> {
  if (inFlight) return inFlight;
  inFlight = (async () => {
    const summaries = await readDailyHealth(35, authorize);
    await sendSummaries(settings, summaries);
    await markAuthorized();
    const history = { syncedAt: new Date().toISOString(), latestDate: summaries[summaries.length - 1]!.date, days: summaries.length, source, latest: summaries[summaries.length - 1] };
    await SecureStore.setItemAsync(HISTORY, JSON.stringify(history));
    return history;
  })().finally(() => { inFlight = null; });
  return inFlight;
}
TaskManager.defineTask(TASK, async () => {
  try {
    if (!(await automaticEnabled())) return BackgroundTask.BackgroundTaskResult.Success;
    const settings = await loadSettings();
    if (!settings.authorized || !settings.accessKey) return BackgroundTask.BackgroundTaskResult.Failed;
    // No authorization UI in a background task. Locked Health data is retried later.
    await performSync(settings, false, 'Background');
    return BackgroundTask.BackgroundTaskResult.Success;
  } catch {
    return BackgroundTask.BackgroundTaskResult.Failed;
  }
});
export async function setAutomaticSync(enabled: boolean) {
  if (enabled) {
    if (await BackgroundTask.getStatusAsync() === BackgroundTask.BackgroundTaskStatus.Restricted) {
      throw new Error('Background syncing is restricted. Check Background App Refresh in iPhone Settings.');
    }
    await BackgroundTask.registerTaskAsync(TASK, { minimumInterval: 12 * 60 });
    await SecureStore.setItemAsync(ENABLED, 'true');
  } else {
    await SecureStore.setItemAsync(ENABLED, 'false');
    if (await TaskManager.isTaskRegisteredAsync(TASK)) await BackgroundTask.unregisterTaskAsync(TASK);
  }
}
