import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  AppState,
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

import { automaticEnabled, loadHistory, performSync, setAutomaticSync, type SyncHistory } from './src/automaticSync';
import { deleteSummaries, loadSettings, saveSettings, type Settings } from './src/sync';

export default function App() {
  const [settings, setSettings] = useState<Settings>({ baseUrl: 'https://stride-ai.app', accessKey: '', authorized: false });
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('Configure the secure connection, then authorize Apple Health.');
  const [history, setHistory] = useState<SyncHistory | null>(null);
  const [automatic, setAutomatic] = useState(false);

  useEffect(() => {
    async function resume() {
      try {
        const saved = await loadSettings();
        const enabled = await automaticEnabled();
        setSettings(saved);
        setAutomatic(enabled);
        setHistory(await loadHistory());
        setReady(true);
        if (enabled && saved.authorized && saved.accessKey) await sync(saved, true);
      } catch (error) {
        setReady(true);
        setMessage(error instanceof Error ? error.message : 'Could not load connection.');
      }
    }
    void resume();
    let wasBackground = AppState.currentState === 'background';
    const subscription = AppState.addEventListener('change', (next) => {
      if (next === 'background') wasBackground = true;
      if (next === 'active' && wasBackground) {
        wasBackground = false;
        void resume();
      }
    });
    return () => subscription.remove();
  }, []);

  async function sync(active = settings, silent = false) {
    if (!active.accessKey) {
      if (!silent) setMessage('Save the StrideAI URL and access key first.');
      return;
    }
    setBusy(true);
    setMessage('Reading Apple Health and preparing daily summaries…');
    try {
      const result = await performSync(active, !silent, silent ? 'Automatic on open' : 'Manual');
      setHistory(result);
      setSettings((current) => ({ ...current, authorized: true }));
      setMessage(`Synced ${result.days} days.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Apple Health sync failed.');
    } finally {
      setBusy(false);
    }
  }

  async function toggleAutomatic() {
    setBusy(true);
    try {
      await setAutomaticSync(!automatic);
      setAutomatic(!automatic);
      setMessage(automatic ? 'Automatic syncing turned off.' : 'Automatic syncing enabled. iOS chooses when background sync runs.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not change automatic syncing.');
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
            setAutomaticSync(false).then(() => { setAutomatic(false); return deleteSummaries(settings); })
              .then((deleted) => {
                setHistory(null);
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

          <View style={styles.card}>
            <Text style={styles.cardTitle}>Automatic syncing</Text>
            <Text style={styles.permission}>Syncs when you reopen the app and requests background sync about twice a day. iOS controls timing. Keep Background App Refresh on and avoid swiping the app away.</Text>
            <Pressable disabled={busy || !settings.authorized} onPress={toggleAutomatic} style={[styles.secondaryButton, (busy || !settings.authorized) && styles.disabled]}>
              <Text style={styles.secondaryText}>{automatic ? 'Turn off automatic syncing' : 'Enable automatic syncing'}</Text>
            </Pressable>
            <Text style={styles.status}>Last successful sync: {history ? new Date(history.syncedAt).toLocaleString() : 'Not recorded yet'}</Text>
            <Text style={styles.status}>Latest Health data: {history?.latestDate ?? 'Not recorded yet'}</Text>
            {history && <Text style={styles.permission}>Synced via: {history.source}</Text>}
          </View>
          {history?.latest && (
            <View style={styles.summary}>
              <Text style={styles.summaryDate}>LATEST · {history.latest.date}</Text>
              <View style={styles.metrics}>
                <Metric label="Sleep" value={history.latest.sleep_hours == null ? '—' : `${history.latest.sleep_hours.toFixed(1)} h`} />
                <Metric label="HRV" value={history.latest.hrv_ms == null ? '—' : `${Math.round(history.latest.hrv_ms)} ms`} />
                <Metric label="Resting HR" value={history.latest.resting_hr_bpm == null ? '—' : `${Math.round(history.latest.resting_hr_bpm)} bpm`} />
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
