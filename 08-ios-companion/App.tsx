import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { readDailyHealth } from './src/health';
import { deleteSummaries, loadSettings, markAuthorized, saveSettings, sendSummaries, type Settings } from './src/sync';

export default function App() {
  const [settings, setSettings] = useState<Settings>({ baseUrl: 'https://stride-ai.app', accessKey: '', authorized: false });
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Configure the secure connection, then authorize Apple Health.');
  const [lastSummary, setLastSummary] = useState<{ date: string; sleep: number | null; hrv: number | null; rhr: number | null } | null>(null);

  useEffect(() => {
    loadSettings().then((saved) => {
      setSettings(saved);
      setReady(true);
      if (saved.authorized && saved.accessKey) void sync(saved, true);
    });
  }, []);

  async function sync(active = settings, silent = false) {
    if (!active.accessKey) {
      if (!silent) setMessage('Save the StrideAI URL and access key first.');
      return;
    }
    setBusy(true);
    if (!silent) setMessage('Reading Apple Health and preparing daily summaries…');
    try {
      const summaries = await readDailyHealth(35);
      const result = await sendSummaries(active, summaries);
      await markAuthorized();
      const latest = summaries[summaries.length - 1];
      if (latest) setLastSummary({ date: latest.date, sleep: latest.sleep_hours, hrv: latest.hrv_ms, rhr: latest.resting_hr_bpm });
      setSettings((current) => ({ ...current, authorized: true }));
      setMessage(`Synced ${String(result.received ?? summaries.length)} days. Latest: ${String(result.latest_date ?? latest?.date ?? '—')}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Apple Health sync failed.');
    } finally {
      setBusy(false);
    }
  }

  async function persist() {
    setBusy(true);
    try {
      await saveSettings(settings.baseUrl, settings.accessKey);
      const saved = await loadSettings();
      setSettings(saved);
      setMessage('Secure connection saved. You can authorize and sync now.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not save settings.');
    } finally {
      setBusy(false);
    }
  }

  function confirmDelete() {
    Alert.alert(
      'Delete synced health data?',
      'This removes all Apple Health daily summaries stored by StrideAI. It does not delete anything from Apple Health.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            setBusy(true);
            deleteSummaries(settings)
              .then((deleted) => {
                setLastSummary(null);
                setMessage(`Deleted ${deleted} stored Apple Health summaries.`);
              })
              .catch((error) => setMessage(error instanceof Error ? error.message : 'Deletion failed.'))
              .finally(() => setBusy(false));
          },
        },
      ],
    );
  }

  if (!ready) return <SafeAreaView style={styles.loading}><ActivityIndicator color="#087469" /></SafeAreaView>;

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.eyebrow}>STRIDEAI COMPANION</Text>
          <Text style={styles.title}>Recovery, without manual entry.</Text>
          <Text style={styles.lead}>Sleep, resting heart rate and HRV are summarized on your iPhone, then sent securely to your StrideAI daily state.</Text>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Private connection</Text>
            <Text style={styles.label}>StrideAI URL</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              onChangeText={(baseUrl) => setSettings((value) => ({ ...value, baseUrl }))}
              style={styles.input}
              value={settings.baseUrl}
            />
            <Text style={styles.label}>Private access key</Text>
            <TextInput
              autoCapitalize="none"
              autoCorrect={false}
              onChangeText={(accessKey) => setSettings((value) => ({ ...value, accessKey }))}
              secureTextEntry
              style={styles.input}
              value={settings.accessKey}
            />
            <Pressable disabled={busy} onPress={persist} style={({ pressed }) => [styles.secondaryButton, pressed && styles.pressed]}>
              <Text style={styles.secondaryText}>Save secure connection</Text>
            </Pressable>
          </View>

          <View style={styles.card}>
            <View style={styles.row}>
              <View style={styles.dot} />
              <Text style={styles.cardTitle}>Apple Health</Text>
            </View>
            <Text style={styles.permission}>Read only: Sleep Analysis, Resting Heart Rate and HRV (SDNN). StrideAI does not write to Health.</Text>
            <Pressable disabled={busy} onPress={() => sync(settings)} style={({ pressed }) => [styles.primaryButton, pressed && styles.pressed, busy && styles.disabled]}>
              {busy ? <ActivityIndicator color="white" /> : <Text style={styles.primaryText}>{settings.authorized ? 'Sync Apple Health now' : 'Authorize & sync Apple Health'}</Text>}
            </Pressable>
            <Text style={styles.status}>{message}</Text>
            <Pressable disabled={busy || !settings.accessKey} onPress={confirmDelete} style={styles.deleteButton}>
              <Text style={styles.deleteText}>Delete synced Apple Health data</Text>
            </Pressable>
          </View>

          {lastSummary && (
            <View style={styles.summary}>
              <Text style={styles.summaryDate}>LATEST · {lastSummary.date}</Text>
              <View style={styles.metrics}>
                <Metric label="Sleep" value={lastSummary.sleep == null ? '—' : `${lastSummary.sleep.toFixed(1)} h`} />
                <Metric label="HRV" value={lastSummary.hrv == null ? '—' : `${Math.round(lastSummary.hrv)} ms`} />
                <Metric label="Resting HR" value={lastSummary.rhr == null ? '—' : `${Math.round(lastSummary.rhr)} bpm`} />
              </View>
            </View>
          )}
          <Text style={styles.footer}>Daily summaries only. Raw HealthKit samples stay on your iPhone.</Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <View style={styles.metric}><Text style={styles.metricValue}>{value}</Text><Text style={styles.metricLabel}>{label}</Text></View>;
}

const styles = StyleSheet.create({
  flex: { flex: 1 }, safe: { flex: 1, backgroundColor: '#F3F7F6' }, loading: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { padding: 24, paddingBottom: 44 }, eyebrow: { color: '#087469', fontSize: 12, fontWeight: '800', letterSpacing: 1.6, marginTop: 20 },
  title: { color: '#17353A', fontSize: 38, lineHeight: 42, fontWeight: '800', letterSpacing: -1.3, marginTop: 10 },
  lead: { color: '#526A70', fontSize: 17, lineHeight: 26, marginTop: 14, marginBottom: 22 },
  card: { backgroundColor: 'white', borderColor: '#DDE8E6', borderWidth: 1, borderRadius: 22, padding: 20, marginBottom: 16 },
  cardTitle: { color: '#17353A', fontSize: 20, fontWeight: '700' }, label: { color: '#526A70', fontSize: 13, fontWeight: '700', marginTop: 16, marginBottom: 7 },
  input: { backgroundColor: '#F5F8F7', borderColor: '#D7E3E1', borderWidth: 1, borderRadius: 12, color: '#17353A', fontSize: 15, paddingHorizontal: 13, paddingVertical: 12 },
  secondaryButton: { borderColor: '#087469', borderWidth: 1, borderRadius: 13, marginTop: 16, padding: 13, alignItems: 'center' }, secondaryText: { color: '#087469', fontWeight: '800' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 9 }, dot: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#2AAF86' },
  permission: { color: '#526A70', fontSize: 15, lineHeight: 22, marginTop: 12 }, primaryButton: { backgroundColor: '#087469', borderRadius: 14, marginTop: 18, minHeight: 50, alignItems: 'center', justifyContent: 'center', padding: 14 },
  primaryText: { color: 'white', fontSize: 16, fontWeight: '800' }, pressed: { opacity: 0.78 }, disabled: { opacity: 0.6 }, status: { color: '#415B60', fontSize: 14, lineHeight: 21, marginTop: 14 },
  summary: { backgroundColor: '#183B3E', borderRadius: 22, padding: 20, marginBottom: 16 }, summaryDate: { color: '#A8D7CC', fontWeight: '800', fontSize: 12, letterSpacing: 1 },
  metrics: { flexDirection: 'row', gap: 8, marginTop: 18 }, metric: { flex: 1 }, metricValue: { color: 'white', fontSize: 20, fontWeight: '800' }, metricLabel: { color: '#B8CDCA', fontSize: 12, marginTop: 4 },
  footer: { textAlign: 'center', color: '#70868A', fontSize: 12, marginTop: 4 },
  deleteButton: { alignItems: 'center', paddingTop: 17 }, deleteText: { color: '#A34848', fontSize: 13, fontWeight: '700' },
});
