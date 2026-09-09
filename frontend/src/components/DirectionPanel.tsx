import React, { useState } from 'react';
import { Upload, Download, FileJson, PlusCircle, AlertCircle } from 'lucide-react';
import { audioEngine } from '../audio/engine';
import { exportAuditionWav, exportSessionJson } from '../audio/render';
import { Session, Cue, Asset } from '../types';

interface DirectionPanelProps {
  session: Session;
  onAddCue: (newCue: Cue) => void;
  onCommitRevision: () => void;
  isSaving: boolean;
  saveMessage: string | null;
}

export const DirectionPanel: React.FC<DirectionPanelProps> = ({
  session,
  onAddCue,
  onCommitRevision,
  isSaving,
  saveMessage,
}) => {
  const [localAssets, setLocalAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [targetTrack, setTargetTrack] = useState<string>('foley');
  const [startOffsetMs, setStartOffsetMs] = useState<number>(1000);
  const [importStatus, setImportStatus] = useState<string | null>(null);

  const handleAudioImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setImportStatus(`Decoding ${file.name}...`);
      await audioEngine.initAudio();
      const ctx = audioEngine.getContext();
      if (!ctx) throw new Error('Audio context unavailable');

      const arrayBuf = await file.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrayBuf);

      const assetId = `local_${Date.now().toString(36)}_${file.name.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase()}`;
      audioEngine.storeBuffer(assetId, audioBuf);

      const newAsset: Asset = {
        id: assetId,
        source_path: `local-blob://${file.name}`,
        sha256: `local_${file.size}_${file.lastModified}`,
        duration_ms: Math.round(audioBuf.duration * 1000),
        sample_rate: audioBuf.sampleRate,
        channels: audioBuf.numberOfChannels,
        tags: ['imported', 'local'],
        source_description: `User File: ${file.name}`,
        rights_note: 'User Local Media (Session-only)',
        available: true,
      };

      setLocalAssets((prev) => [...prev, newAsset]);
      setSelectedAssetId(assetId);
      setImportStatus(`Imported '${file.name}' (${(audioBuf.duration).toFixed(2)}s, ${audioBuf.sampleRate}Hz, ${audioBuf.numberOfChannels}ch).`);
    } catch (err: any) {
      setImportStatus(`Decode error: ${err.message || err}`);
    }
  };

  const handleAddManualCue = () => {
    if (!selectedAssetId) {
      alert('Please select or import a sound recording first.');
      return;
    }

    const asset = localAssets.find((a) => a.id === selectedAssetId);
    const duration = asset ? asset.duration_ms : 1000;

    const cueId = `cue_${Date.now().toString(36).slice(-4)}`;
    const newCue: Cue = {
      id: cueId,
      asset_id: selectedAssetId,
      source_in_ms: 0,
      source_out_ms: Math.min(duration, 5000),
      timeline_start_ms: startOffsetMs,
      gain_db: -3.0,
      pan: 0.0,
      envelope_points: [
        { offset_ms: 0, level: 0.0 },
        { offset_ms: 100, level: 1.0 },
        { offset_ms: Math.min(duration, 5000) - 100, level: 1.0 },
        { offset_ms: Math.min(duration, 5000), level: 0.0 },
      ],
      track_id: targetTrack,
    };

    onAddCue(newCue);
  };

  const handleExportWav = async () => {
    try {
      setImportStatus('Rendering audition WAV offline...');
      await exportAuditionWav(session, (id) => audioEngine.getBuffer(id));
      setImportStatus('Audition WAV exported successfully.');
    } catch (err: any) {
      setImportStatus(`WAV render failed: ${err.message}`);
    }
  };

  return (
    <div className="card" style={{ padding: '1rem', background: '#0f172a', borderColor: '#1e293b' }}>
      <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.75rem' }}>
        Media Import &amp; Rehearsal Actions
      </h3>

      {/* Local Media Import Dropzone */}
      <div
        style={{
          border: '1px dashed #3b82f6',
          borderRadius: '0.5rem',
          padding: '1rem',
          textAlign: 'center',
          background: 'rgba(59, 130, 246, 0.05)',
        }}
      >
        <Upload size={24} color="#60a5fa" style={{ margin: '0 auto 0.25rem' }} />
        <p style={{ fontSize: '0.85rem', fontWeight: 500 }}>Import Real Audio Recordings</p>
        <p style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0.25rem 0 0.5rem' }}>
          Supports .wav, .mp3, .ogg, .m4a. Decodes real duration, sample rate, and channels.
        </p>

        <label
          style={{
            display: 'inline-block',
            background: '#2563eb',
            color: '#ffffff',
            padding: '0.35rem 0.8rem',
            borderRadius: '0.375rem',
            fontSize: '0.8rem',
            cursor: 'pointer',
          }}
        >
          Select Audio File
          <input
            type="file"
            accept="audio/*"
            onChange={handleAudioImport}
            style={{ display: 'none' }}
          />
        </label>
      </div>

      {/* Warning regarding browser-local media */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: '0.4rem',
          marginTop: '0.5rem',
          fontSize: '0.72rem',
          color: '#cbd5e1',
          background: '#1e293b',
          padding: '0.4rem 0.6rem',
          borderRadius: '0.375rem',
        }}
      >
        <AlertCircle size={14} color="#facc15" style={{ flexShrink: 0, marginTop: '2px' }} />
        <span>
          <strong>Session-local media:</strong> Imported browser files are held in local memory for this rehearsal session. They do not persist across devices or page reloads. Raw media blobs are never sent to Firestore or ClickHouse.
        </span>
      </div>

      {importStatus && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: '#38bdf8' }}>
          {importStatus}
        </div>
      )}

      {/* Manual Cue Placement Controls */}
      <div style={{ marginTop: '1rem', borderTop: '1px solid #1e293b', paddingTop: '0.75rem' }}>
        <h4 style={{ fontSize: '0.85rem', color: '#cbd5e1', marginBottom: '0.5rem' }}>
          Place Cue on Timeline
        </h4>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <select
            value={selectedAssetId}
            onChange={(e) => setSelectedAssetId(e.target.value)}
            style={{ background: '#0b0f19', color: '#fff', border: '1px solid #475569', borderRadius: '4px', padding: '0.3rem', fontSize: '0.75rem' }}
          >
            <option value="">-- Select Loaded Asset --</option>
            {localAssets.map((a) => (
              <option key={a.id} value={a.id}>
                {a.source_description} ({(a.duration_ms / 1000).toFixed(1)}s)
              </option>
            ))}
          </select>

          <select
            value={targetTrack}
            onChange={(e) => setTargetTrack(e.target.value)}
            style={{ background: '#0b0f19', color: '#fff', border: '1px solid #475569', borderRadius: '4px', padding: '0.3rem', fontSize: '0.75rem' }}
          >
            <option value="foley">Foley Track</option>
            <option value="sfx">SFX Track</option>
            <option value="ambience">Ambience Track</option>
          </select>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>At:</span>
            <input
              type="number"
              value={startOffsetMs}
              onChange={(e) => setStartOffsetMs(parseInt(e.target.value) || 0)}
              style={{ width: '70px', background: '#0b0f19', color: '#fff', border: '1px solid #475569', borderRadius: '4px', padding: '0.3rem', fontSize: '0.75rem' }}
            />
            <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>ms</span>
          </div>

          <button
            onClick={handleAddManualCue}
            style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', padding: '0.35rem 0.7rem', fontSize: '0.8rem' }}
          >
            <PlusCircle size={14} /> Place Cue
          </button>
        </div>
      </div>

      {/* Session Export and Commit Actions */}
      <div
        style={{
          marginTop: '1rem',
          borderTop: '1px solid #1e293b',
          paddingTop: '0.75rem',
          display: 'flex',
          gap: '0.5rem',
          flexWrap: 'wrap',
        }}
      >
        <button
          onClick={handleExportWav}
          style={{ background: '#059669', borderColor: '#059669', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}
        >
          <Download size={14} /> Export Audition WAV
        </button>

        <button
          onClick={() => exportSessionJson(session)}
          style={{ background: '#475569', borderColor: '#475569', display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}
        >
          <FileJson size={14} /> Export Session JSON
        </button>

        <button
          onClick={onCommitRevision}
          disabled={isSaving}
          style={{ marginLeft: 'auto', fontSize: '0.8rem' }}
        >
          {isSaving ? 'Committing...' : `Commit Revision ${session.revision + 1} to Firestore`}
        </button>
      </div>

      {saveMessage && (
        <div style={{ marginTop: '0.5rem', fontSize: '0.78rem', color: '#38bdf8' }}>
          {saveMessage}
        </div>
      )}
    </div>
  );
};
