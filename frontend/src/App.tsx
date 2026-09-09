import { useEffect, useState } from 'react';
import { fetchHealth, fetchSystemStatus, createSession, applyEditBatch, fetchCatalogAssets } from './api';
import { SystemStatusResponse, Session, Cue, EditBatch, Asset } from './types';
import { audioEngine } from './audio/engine';
import { Stage } from './components/Stage';
import { Timeline } from './components/Timeline';
import { DirectionPanel } from './components/DirectionPanel';
import { AssetLibrary } from './components/AssetLibrary';
import { Radio, Volume2 } from 'lucide-react';

const INITIAL_SESSION: Session = {
  id: 'voltra_rehearsal_master',
  owner_uid: 'director_master_local',
  revision: 0,
  scene_duration_ms: 10000,
  protected_track_ids: ['dialogue'],
  cues: [],
  status: 'idle',
  updated_at: new Date().toISOString(),
};

export default function App() {
  const [health, setHealth] = useState<{ status: string; app: string; version: string } | null>(null);
  const [sysStatus, setSysStatus] = useState<SystemStatusResponse | null>(null);
  const [catalogAssets, setCatalogAssets] = useState<Asset[]>([]);
  const [catalogLoading, setCatalogLoading] = useState<boolean>(true);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Audio Engine & Playback State
  const [session, setSession] = useState<Session>(INITIAL_SESSION);
  const [currentTimeMs, setCurrentTimeMs] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [audioReady, setAudioReady] = useState<boolean>(false);
  const [videoFrameB64, setVideoFrameB64] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const refreshStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      const [h, s] = await Promise.all([fetchHealth(), fetchSystemStatus()]);
      setHealth(h);
      setSysStatus(s);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to VoltraPROD backend.');
    } finally {
      setLoading(false);
    }
  };

  const loadCatalog = async () => {
    try {
      setCatalogLoading(true);
      const res = await fetchCatalogAssets();
      setCatalogAssets(res.assets || []);
      // Preload initial session cues
      audioEngine.preloadSessionCues(session.cues, res.assets || []);
    } catch (err) {
      console.warn('Could not load catalog assets:', err);
    } finally {
      setCatalogLoading(false);
    }
  };

  useEffect(() => {
    refreshStatus();
    loadCatalog();

    // Attach AudioEngine event callbacks
    audioEngine.setOnTimeUpdate((timeMs) => {
      setCurrentTimeMs(timeMs);
    });

    audioEngine.setOnEnded(() => {
      setIsPlaying(false);
      setCurrentTimeMs(0);
    });
  }, []);

  const handleEnableAudio = async () => {
    const ready = await audioEngine.initAudio();
    setAudioReady(ready);
    if (ready) {
      audioEngine.preloadSessionCues(session.cues, catalogAssets);
    }
  };

  const handleTogglePlay = () => {
    if (!audioReady) {
      handleEnableAudio();
      return;
    }

    if (isPlaying) {
      audioEngine.pause(currentTimeMs);
      setIsPlaying(false);
    } else {
      audioEngine.play(session, currentTimeMs);
      setIsPlaying(true);
    }
  };

  const handleSeek = (newTimeMs: number) => {
    setCurrentTimeMs(newTimeMs);
    audioEngine.seek(session, newTimeMs);
  };

  const handleUpdateCue = (updatedCue: Cue) => {
    audioEngine.stopAllSources();
    setSession((prev) => ({
      ...prev,
      cues: prev.cues.map((c) => (c.id === updatedCue.id ? updatedCue : c)),
    }));
    if (isPlaying) {
      audioEngine.play(session, currentTimeMs);
    }
  };

  const handleDeleteCue = (cueId: string) => {
    audioEngine.stopAllSources();
    setSession((prev) => ({
      ...prev,
      cues: prev.cues.filter((c) => c.id !== cueId),
    }));
    if (isPlaying) {
      audioEngine.play(session, currentTimeMs);
    }
  };

  const handleAddCue = (newCue: Cue) => {
    audioEngine.stopAllSources();
    setSession((prev) => ({
      ...prev,
      cues: [...prev.cues, newCue],
    }));
    if (isPlaying) {
      audioEngine.play(session, currentTimeMs);
    }
  };

  const handleCommitRevision = async () => {
    try {
      setIsSaving(true);
      setSaveMessage(null);

      const opId = `op_edit_${Date.now().toString(36)}`;
      const batch: EditBatch = {
        operation_id: opId,
        session_id: session.id,
        expected_revision: session.revision,
        edits: session.cues.map((c) => ({
          action: 'modify',
          cue_id: c.id,
          cue: c,
        })),
        rationale_summary: `Manual rehearsal treatment edit at revision ${session.revision + 1}`,
      };

      try {
        await createSession(session);
      } catch {
        // Session may exist
      }

      const res = await applyEditBatch(session.id, batch);
      if (res.status === 'success') {
        setSession((prev) => ({ ...prev, revision: res.revision }));
        setSaveMessage(`Committed revision ${res.revision} to Firestore via atomic transaction.`);
      } else {
        setSaveMessage(`Result: [${res.status}] ${res.error_code || ''} - ${JSON.stringify(res.data)}`);
      }
    } catch (err: any) {
      setSaveMessage(`Save failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="container">
      {/* VoltraPROD Global Header */}
      <header className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <Radio size={26} color="#3B82F6" />
            <span>VoltraPROD: AI Sound Rehearsal Studio</span>
            <span className="badge badge-brand">Run 3: Agent Loop</span>
          </h1>
          <p>
            Agentic Cinema Sound Design Rehearsal — Gemini 3.1 Agent, ClickHouse Cloud MCP, Firestore Revisions &amp; Browser Playback
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', alignItems: 'center' }}>
          {loading && <span className="badge badge-warning">Syncing...</span>}
          <span className={`badge ${health?.status === 'ok' ? 'badge-success' : 'badge-error'}`}>
            Backend: {health?.status === 'ok' ? 'Online' : 'Offline'}
          </span>
          <button
            onClick={handleEnableAudio}
            style={{
              padding: '0.3rem 0.75rem',
              fontSize: '0.75rem',
              background: audioReady ? '#10B981' : '#F59E0B',
              borderColor: 'transparent',
            }}
          >
            <Volume2 size={13} />
            {audioReady ? 'Audio Enabled' : 'Enable Audio (Required)'}
          </button>
        </div>
      </header>

      {/* Backend Disconnect Alert */}
      {error && (
        <div className="card" style={{ borderColor: '#EF4444' }}>
          <p style={{ color: '#EF4444' }}>Backend connectivity offline: {error}</p>
          <button onClick={refreshStatus} style={{ alignSelf: 'flex-start', marginTop: '0.5rem' }}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Integration Badges Bar */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: '220px', padding: '0.6rem 0.8rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#A1A1AA' }}>Gemini Developer API</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: sysStatus?.integrations.gemini.configured ? '#10B981' : '#F59E0B' }}>
            {sysStatus?.integrations.gemini.configured ? `Active (${sysStatus.integrations.gemini.model})` : 'Unavailable'}
          </div>
        </div>

        <div className="card" style={{ flex: 1, minWidth: '220px', padding: '0.6rem 0.8rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#A1A1AA' }}>ClickHouse Cloud MCP</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: sysStatus?.integrations.clickhouse.configured ? '#10B981' : '#F59E0B' }}>
            {sysStatus?.integrations.clickhouse.configured ? 'Connected (MCP Read-Only)' : 'Unavailable'}
          </div>
        </div>

        <div className="card" style={{ flex: 1, minWidth: '220px', padding: '0.6rem 0.8rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#A1A1AA' }}>Firestore Revisions</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: sysStatus?.integrations.firestore.configured ? '#10B981' : '#F59E0B' }}>
            {sysStatus?.integrations.firestore.configured ? 'Active (Spark Plan)' : 'Unavailable'}
          </div>
        </div>
      </div>

      {/* Stage: Video/Audio Preview & Player Controls */}
      <Stage
        session={session}
        currentTimeMs={currentTimeMs}
        onSeek={handleSeek}
        isPlaying={isPlaying}
        onTogglePlay={handleTogglePlay}
        audioReady={audioReady}
        onEnableAudio={handleEnableAudio}
        onFrameCaptured={setVideoFrameB64}
      />

      {/* Sound Catalog Library */}
      <AssetLibrary assets={catalogAssets} isLoading={catalogLoading} onRefresh={loadCatalog} />

      {/* Director Console: AI Direction, Live Traces, Audition & Feedback */}
      <DirectionPanel
        session={session}
        onUpdateSession={(updated) => {
          setSession(updated);
          audioEngine.preloadSessionCues(updated.cues, catalogAssets);
        }}
        catalogAssets={catalogAssets}
        videoFrameB64={videoFrameB64}
        onAddCue={handleAddCue}
        onCommitRevision={handleCommitRevision}
        isSaving={isSaving}
        saveMessage={saveMessage}
      />

      {/* Interactive Multi-Track Timeline */}
      <Timeline
        session={session}
        currentTimeMs={currentTimeMs}
        onSeek={handleSeek}
        onUpdateCue={handleUpdateCue}
        onDeleteCue={handleDeleteCue}
      />
    </div>
  );
}
