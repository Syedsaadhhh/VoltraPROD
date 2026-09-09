import { useEffect, useState } from 'react';
import { fetchHealth, fetchSystemStatus, createSession, applyEditBatch } from './api';
import { SystemStatusResponse, Session, Cue, EditBatch } from './types';
import { audioEngine } from './audio/engine';
import { Stage } from './components/Stage';
import { Timeline } from './components/Timeline';
import { DirectionPanel } from './components/DirectionPanel';
import { Radio } from 'lucide-react';

const INITIAL_SESSION: Session = {
  id: 'voltra_rehearsal_master',
  owner_uid: 'director_master_local',
  revision: 0,
  scene_duration_ms: 30000,
  protected_track_ids: ['dialogue'],
  cues: [
    {
      id: 'dialogue_hero_01',
      asset_id: 'asset_dialogue_hero',
      source_in_ms: 0,
      source_out_ms: 4000,
      timeline_start_ms: 1000,
      gain_db: -1.5,
      pan: 0.0,
      envelope_points: [
        { offset_ms: 0, level: 0.0 },
        { offset_ms: 200, level: 1.0 },
        { offset_ms: 3800, level: 1.0 },
        { offset_ms: 4000, level: 0.0 },
      ],
      track_id: 'dialogue',
    },
  ],
  status: 'idle',
  updated_at: new Date().toISOString(),
};

export default function App() {
  const [health, setHealth] = useState<{ status: string; app: string; version: string } | null>(null);
  const [sysStatus, setSysStatus] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Audio Engine & Playback State
  const [session, setSession] = useState<Session>(INITIAL_SESSION);
  const [currentTimeMs, setCurrentTimeMs] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [audioReady, setAudioReady] = useState<boolean>(false);
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

  useEffect(() => {
    refreshStatus();

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
    // Stop active audio to prevent duplicate or ghost playback on edit
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

      // Try creating session first if new, then commit edits
      try {
        await createSession(session);
      } catch {
        // May already exist in Firestore
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
            <Radio size={28} color="#6366f1" />
            <span>VoltraPROD: Sound Rehearsal Studio</span>
            <span className="badge badge-success">Run 2: Media Engine</span>
          </h1>
          <p>
            Agentic Cinema Sound Design &amp; Playback Rehearsal — Web Audio Scheduling, Multi-Track Editing &amp; Firestore Revisions
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem', alignItems: 'center' }}>
          {loading && <span className="badge badge-warning">Syncing...</span>}
          <span className={`badge ${health?.status === 'ok' ? 'badge-success' : 'badge-error'}`}>
            Backend: {health?.status === 'ok' ? 'Online' : 'Offline'}
          </span>
          <span className={`badge ${audioReady ? 'badge-success' : 'badge-warning'}`}>
            Web Audio: {audioReady ? 'Active' : 'Muted (Tap Enable)'}
          </span>
        </div>
      </header>

      {/* Backend Disconnect Alert */}
      {error && (
        <div className="card" style={{ borderColor: '#ef4444' }}>
          <p style={{ color: '#f87171' }}>Backend connectivity offline: {error}</p>
          <button onClick={refreshStatus} style={{ alignSelf: 'flex-start', marginTop: '0.5rem' }}>
            Retry Connection
          </button>
        </div>
      )}

      {/* Integration Badges Bar */}
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div className="card" style={{ flex: 1, minWidth: '220px', padding: '0.6rem 0.8rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Gemini Developer API</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: sysStatus?.integrations.gemini.configured ? '#4ade80' : '#facc15' }}>
            {sysStatus?.integrations.gemini.configured ? `Configured (${sysStatus.integrations.gemini.model})` : 'Unavailable'}
          </div>
        </div>

        <div className="card" style={{ flex: 1, minWidth: '220px', padding: '0.6rem 0.8rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>ClickHouse Cloud MCP</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: sysStatus?.integrations.clickhouse.configured ? '#4ade80' : '#facc15' }}>
            {sysStatus?.integrations.clickhouse.configured ? 'Connected (MCP Read-Only)' : 'Unavailable'}
          </div>
        </div>

        <div className="card" style={{ flex: 1, minWidth: '220px', padding: '0.6rem 0.8rem' }}>
          <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>Firestore Revisions</div>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, color: sysStatus?.integrations.firestore.configured ? '#4ade80' : '#facc15' }}>
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
      />

      {/* Interactive Multi-Track Timeline */}
      <Timeline
        session={session}
        currentTimeMs={currentTimeMs}
        onSeek={handleSeek}
        onUpdateCue={handleUpdateCue}
        onDeleteCue={handleDeleteCue}
      />

      {/* Media Import, Cue Placement, and Export Drawer */}
      <DirectionPanel
        session={session}
        onAddCue={handleAddCue}
        onCommitRevision={handleCommitRevision}
        isSaving={isSaving}
        saveMessage={saveMessage}
      />
    </div>
  );
}
