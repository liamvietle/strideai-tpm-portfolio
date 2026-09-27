import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';

import type { DailyHealthSummary } from './health';

const BASE_URL_KEY = 'strideai_base_url';
const ACCESS_KEY_KEY = 'strideai_access_key';
const DEVICE_ID_KEY = 'strideai_device_id';
const AUTHORIZED_KEY = 'strideai_health_authorized';

export type Settings = { baseUrl: string; accessKey: string; authorized: boolean };

export async function loadSettings(): Promise<Settings> {
  return {
    baseUrl: (await SecureStore.getItemAsync(BASE_URL_KEY)) ?? 'https://stride-ai.app',
    accessKey: (await SecureStore.getItemAsync(ACCESS_KEY_KEY)) ?? '',
    authorized: (await SecureStore.getItemAsync(AUTHORIZED_KEY)) === 'true',
  };
}

export async function saveSettings(baseUrl: string, accessKey: string): Promise<void> {
  const normalized = baseUrl.trim().replace(/\/$/, '');
  if (!normalized.startsWith('https://')) throw new Error('StrideAI URL must use HTTPS.');
  if (!accessKey.trim()) throw new Error('Enter the private StrideAI access key.');
  await Promise.all([
    SecureStore.setItemAsync(BASE_URL_KEY, normalized),
    SecureStore.setItemAsync(ACCESS_KEY_KEY, accessKey.trim()),
  ]);
}

export async function markAuthorized(): Promise<void> {
  await SecureStore.setItemAsync(AUTHORIZED_KEY, 'true');
}

async function deviceId(): Promise<string> {
  const existing = await SecureStore.getItemAsync(DEVICE_ID_KEY);
  if (existing) return existing;
  const created = Crypto.randomUUID();
  await SecureStore.setItemAsync(DEVICE_ID_KEY, created);
  return created;
}

export async function sendSummaries(settings: Settings, summaries: DailyHealthSummary[]) {
  if (!summaries.length) throw new Error('No authorized Apple Health recovery samples were found.');
  const response = await fetch(`${settings.baseUrl}/app/api/apple-health/sync`, {
    method: 'POST',
    signal: AbortSignal.timeout(25000),
    headers: {
      'Content-Type': 'application/json',
      'X-StrideAI-Key': settings.accessKey,
    },
    body: JSON.stringify({
      athlete_id: 'viet',
      device_id: await deviceId(),
      app_version: '1.1.0',
      generated_at: new Date().toISOString(),
      summaries,
    }),
  });
  let payload: Record<string, unknown> = {};
  try {
    payload = (await response.json()) as Record<string, unknown>;
  } catch {}
  if (!response.ok) {
    throw new Error(String(payload.detail ?? `StrideAI sync failed (${response.status}).`));
  }
  return payload;
}

export async function deleteSummaries(settings: Settings): Promise<number> {
  const response = await fetch(`${settings.baseUrl}/app/api/apple-health/data?athlete_id=viet`, {
    method: 'DELETE',
    headers: { 'X-StrideAI-Key': settings.accessKey },
  });
  const payload = (await response.json()) as { deleted?: number; detail?: string };
  if (!response.ok) throw new Error(payload.detail ?? `Deletion failed (${response.status}).`);
  return payload.deleted ?? 0;
}
