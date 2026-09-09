import React, { useState } from 'react';
import { Sparkles, Send, ThumbsUp, ThumbsDown, Play, Upload, Download, FileJson, Database, Shield } from 'lucide-react';
import { audioEngine } from '../audio/engine';
import { exportAuditionWav, exportSessionJson } from '../audio/render';
import { Session, Cue, Asset, ToolTrace, DirectorDirectionResponse } from '../types';
import { sendDirection, submitAuditionFeedback, createSession } from '../api';

interface DirectionPanelProps {
  session: Session;
  onUpdateSession: (updated: Session) => void;
  catalogAssets: Asset[];
  videoFrameB64?: string | null;
  onAddCue: (newCue: Cue) => void;
  onCommitRevision: () => void;
  isSaving: boolean;
  saveMessage: string | null;
}

export const DirectionPanel: React.FC<DirectionPanelProps> = ({
  session,
  onUpdateSession,
  catalogAssets,
  videoFrameB64,
  onAddCue,
  onCommitRevision,
  isSaving,
  saveMessage,
}) => {
  // Director Prompt State
  const [instruction, setInstruction] = useState<string>(
    'Build suspense with heavy footsteps before the character turns toward the doorway. Keep paper handling subtle. Do not add music or a door sound.'
  );
  const [sceneBeats, setSceneBeats] = useState<string>(
    '0.0s-4.0s Woman at desk reviewing and folding paper document. 4.5s Cuts to medium close-up, turns abruptly toward door alerted by footsteps. 5.0s-10.0s Freezes staring at door.'
  );
  const [isDirecting, setIsDirecting] = useState<boolean>(false);
  const [directionResponse, setDirectionResponse] = useState<DirectorDirectionResponse | null>(null);
  const [excludedAssetIds, setExcludedAssetIds] = useState<string[]>([]);
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);

  // Manual Import / Cue State
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [localAssets, setLocalAssets] = useState<Asset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [targetTrack, setTargetTrack] = useState<string>('foley');
  const [startOffsetMs, setStartOffsetMs] = useState<number>(1000);
  const [importStatus, setImportStatus] = useState<string | null>(null);

  const handleSendDirection = async (customInstruction?: string, extraExcluded?: string[]) => {
    const textToSend = customInstruction || instruction;
    if (!textToSend.trim()) return;

    try {
      setIsDirecting(true);
      setFeedbackStatus(null);
      await audioEngine.initAudio();

      const toExclude = extraExcluded ? [...excludedAssetIds, ...extraExcluded] : excludedAssetIds;

      // Ensure session exists in Firestore with caller's authenticated UID
      try {
        await createSession(session);
      } catch {
        // Session may already exist
      }

      const res = await sendDirection(session.id, {
        instruction: textToSend,
        base_revision: session.revision,
        scene_beats: sceneBeats || undefined,
        video_frame_b64: videoFrameB64 || undefined,
        excluded_asset_ids: toExclude,
      });

      setDirectionResponse(res);

      if (res.updated_session) {
        onUpdateSession(res.updated_session);
        // Preload any newly placed cues into browser audio buffer
        await audioEngine.preloadSessionCues(res.updated_session.cues, catalogAssets);
      }
    } catch (err: any) {
      setFeedbackStatus(`Direction failed: ${err.message}`);
    } finally {
      setIsDirecting(false);
    }
  };

  const handleAuditionTreatment = async () => {
    await audioEngine.initAudio();
    // Play from the beginning of the newest cue or from 0
    const nonDialogueCues = session.cues.filter((c) => c.track_id !== 'dialogue');
    const startMs = nonDialogueCues.length > 0 ? nonDialogueCues[nonDialogueCues.length - 1].timeline_start_ms : 0;
    audioEngine.play(session, Math.max(0, startMs - 200));
  };

  const handleAcceptTreatment = async () => {
    const nonDialogueCues = session.cues.filter((c) => c.track_id !== 'dialogue');
    const assetIds = nonDialogueCues.map((c) => c.asset_id);
    if (assetIds.length === 0) return;

    try {
      setFeedbackStatus('Recording acceptance in ClickHouse event store...');
      await submitAuditionFeedback(session.id, {
        event_id: `evt_acc_${Date.now().toString(36)}`,
        session_id: session.id,
        revision: session.revision,
        asset_ids: assetIds,
        accepted_or_rejected_or_unrated: 'accepted',
        director_text: instruction,
        observed_at: new Date().toISOString(),
      });
      setFeedbackStatus('Audition accepted! Saved to ClickHouse audition history.');
    } catch (err: any) {
      setFeedbackStatus(`Feedback error: ${err.message}`);
    }
  };

  const handleRejectAndRedirection = async () => {
    // Find the latest proposed non-dialogue asset
    const nonDialogueCues = session.cues.filter((c) => c.track_id !== 'dialogue');
    if (nonDialogueCues.length === 0) {
      setFeedbackStatus('No auditioned sound to reject.');
      return;
    }

    const rejectedCue = nonDialogueCues[nonDialogueCues.length - 1];
    const rejectedAssetId = rejectedCue.asset_id;

    // Immediately exclude this asset
    const updatedExclusions = Array.from(new Set([...excludedAssetIds, rejectedAssetId]));
    setExcludedAssetIds(updatedExclusions);

    try {
      setFeedbackStatus(`Rejected '${rejectedAssetId}'. Logging to ClickHouse and requesting fresh candidate...`);
      await submitAuditionFeedback(session.id, {
        event_id: `evt_rej_${Date.now().toString(36)}`,
        session_id: session.id,
        revision: session.revision,
        asset_ids: [rejectedAssetId],
        accepted_or_rejected_or_unrated: 'rejected',
        director_text: `Rejected asset ${rejectedAssetId}; requesting alternative`,
        observed_at: new Date().toISOString(),
      });

      // Automatically replan with a fresh query excluding this asset
      const revisedPrompt = `The previous sound '${rejectedAssetId}' was rejected. Please select a completely different available sound candidate for this cue.`;
      await handleSendDirection(revisedPrompt, [rejectedAssetId]);
    } catch (err: any) {
      setFeedbackStatus(`Rejection error: ${err.message}`);
    }
  };

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

    const allAvailable = [...catalogAssets, ...localAssets];
    const asset = allAvailable.find((a) => a.id === selectedAssetId);
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
    <div className="card" style={{ background: '#18181B', borderColor: '#27272A', padding: '1.25rem', gap: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#FAFAFA', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Sparkles size={18} color="#8B5CF6" />
          <span>AI Director Console</span>
          <span className="badge badge-brand" style={{ fontSize: '0.68rem' }}>Gemini Agent + ClickHouse MCP</span>
        </h3>
        <span style={{ fontSize: '0.78rem', color: '#A1A1AA', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          <Shield size={14} color="#10B981" /> Protected Dialogue Track Locked
        </span>
      </div>

      {/* Creative Instruction Input Form */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="secondary"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setInstruction('Build suspense with heavy footsteps before the character turns toward the doorway. Keep paper handling subtle. Do not add music or a door sound.')}
          >
            Heavy Footsteps
          </button>
          <button
            type="button"
            className="secondary"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setInstruction('Those footsteps are too aggressive. Replace them with the normal footsteps and make the approach quieter. Keep the paper cue.')}
          >
            Normal Footsteps
          </button>
          <button
            type="button"
            className="secondary"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setInstruction('Subtle paper folding at the desk before she hears the threat.')}
          >
            Paper Handling
          </button>
          <button
            type="button"
            className="secondary"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setInstruction('Add subtle indoor room tone for background atmosphere.')}
          >
            Indoor Room Tone
          </button>
          <button
            type="button"
            className="secondary"
            style={{ fontSize: '0.75rem', padding: '0.25rem 0.6rem' }}
            onClick={() => setInstruction('Add a firm door close sound after the footsteps finish.')}
          >
            Door Close
          </button>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div style={{ flex: 2, minWidth: '280px' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#A1A1AA', marginBottom: '0.25rem' }}>
              Director Creative Direction:
            </label>
            <textarea
              rows={2}
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              placeholder="Enter sound direction (e.g. 'Add faint footsteps on wood before she speaks')..."
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>

          <div style={{ flex: 1, minWidth: '220px' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', color: '#A1A1AA', marginBottom: '0.25rem' }}>
              Scene Context (<span style={{ color: '#F59E0B' }}>User Supplied</span>):
            </label>
            <textarea
              rows={2}
              value={sceneBeats}
              onChange={(e) => setSceneBeats(e.target.value)}
              placeholder="Scene beats or action description..."
              style={{ width: '100%', resize: 'vertical' }}
            />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: '0.75rem', color: '#71717A' }}>
            Excluded assets this turn: {excludedAssetIds.length > 0 ? excludedAssetIds.join(', ') : 'None'}
          </span>
          <button
            onClick={() => handleSendDirection()}
            disabled={isDirecting || !instruction.trim()}
            style={{ padding: '0.5rem 1.25rem', fontSize: '0.85rem' }}
          >
            <Send size={15} />
            {isDirecting ? 'Agent Rehearsing (Querying MCP)...' : 'Direct Sound Treatment'}
          </button>
        </div>
      </div>

      {/* Agent Response & Live Action Summary */}
      {directionResponse && (
        <div
          style={{
            background: '#09090B',
            border: '1px solid #27272A',
            borderRadius: '0.5rem',
            padding: '0.85rem',
            display: 'flex',
            flexDirection: 'column',
            gap: '0.5rem',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#FAFAFA' }}>
              {directionResponse.action_summary}
            </span>
            <span
              className={`badge ${
                directionResponse.status === 'success'
                  ? 'badge-success'
                  : directionResponse.status === 'quota_exceeded'
                  ? 'badge-warning'
                  : 'badge-error'
              }`}
            >
              {directionResponse.status}
            </span>
          </div>

          {directionResponse.rationale && (
            <p style={{ fontSize: '0.78rem', color: '#A1A1AA' }}>
              <strong>Rationale:</strong> {directionResponse.rationale}
            </p>
          )}

          {/* Tool Traces Feed */}
          {directionResponse.tool_traces.length > 0 && (
            <div style={{ borderTop: '1px solid #27272A', paddingTop: '0.4rem' }}>
              <span style={{ fontSize: '0.72rem', color: '#71717A', display: 'block', marginBottom: '0.25rem' }}>
                Tool Execution Pipeline:
              </span>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                {directionResponse.tool_traces.map((trace: ToolTrace, i: number) => (
                  <div
                    key={i}
                    style={{
                      fontSize: '0.72rem',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      color: '#E4E4E7',
                      background: '#18181B',
                      padding: '0.2rem 0.5rem',
                      borderRadius: '4px',
                    }}
                  >
                    <Database size={12} color="#3B82F6" />
                    <code style={{ fontSize: '0.7rem', color: '#60A5FA' }}>{trace.tool}</code>
                    <span>{trace.summary}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rehearsal Audition & Feedback Actions */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderTop: '1px solid #27272A',
              paddingTop: '0.6rem',
              marginTop: '0.2rem',
              flexWrap: 'wrap',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button
                onClick={handleAuditionTreatment}
                style={{ background: '#8B5CF6', borderColor: '#8B5CF6', fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
              >
                <Play size={14} /> Audition Treatment
              </button>
              <button
                onClick={handleAcceptTreatment}
                style={{ background: '#10B981', borderColor: '#10B981', fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
              >
                <ThumbsUp size={14} /> Accept Treatment
              </button>
              <button
                onClick={handleRejectAndRedirection}
                className="danger"
                style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
              >
                <ThumbsDown size={14} /> Reject Sound &amp; Re-direct
              </button>
            </div>

            <span style={{ fontSize: '0.75rem', color: '#10B981' }}>
              Revision: {session.revision} (Firestore Synchronized)
            </span>
          </div>
        </div>
      )}

      {feedbackStatus && (
        <div style={{ fontSize: '0.78rem', color: '#60A5FA', background: 'rgba(59, 130, 246, 0.1)', padding: '0.4rem 0.6rem', borderRadius: '4px' }}>
          {feedbackStatus}
        </div>
      )}

      {/* Collapsible Manual Controls & Export Drawer */}
      <div style={{ borderTop: '1px solid #27272A', paddingTop: '0.5rem' }}>
        <button
          className="secondary"
          onClick={() => setShowAdvanced(!showAdvanced)}
          style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
        >
          {showAdvanced ? 'Hide Manual Controls' : 'Show Manual Media Import & Export'}
        </button>

        {showAdvanced && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.75rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <label
                style={{
                  background: '#27272A',
                  color: '#FAFAFA',
                  padding: '0.35rem 0.75rem',
                  borderRadius: '0.375rem',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  border: '1px solid #3F3F46',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                }}
              >
                <Upload size={13} /> Import Local Sound File
                <input type="file" accept="audio/*" onChange={handleAudioImport} style={{ display: 'none' }} />
              </label>

              <select
                value={selectedAssetId}
                onChange={(e) => setSelectedAssetId(e.target.value)}
                style={{ fontSize: '0.75rem', padding: '0.3rem' }}
              >
                <option value="">-- Choose Asset to Place --</option>
                {[...catalogAssets, ...localAssets].map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.source_description || a.id} ({(a.duration_ms / 1000).toFixed(1)}s)
                  </option>
                ))}
              </select>

              <select
                value={targetTrack}
                onChange={(e) => setTargetTrack(e.target.value)}
                style={{ fontSize: '0.75rem', padding: '0.3rem' }}
              >
                <option value="foley">Foley Track</option>
                <option value="sfx">SFX Track</option>
                <option value="ambience">Ambience Track</option>
              </select>

              <input
                type="number"
                value={startOffsetMs}
                onChange={(e) => setStartOffsetMs(parseInt(e.target.value) || 0)}
                style={{ width: '75px', fontSize: '0.75rem', padding: '0.3rem' }}
              />
              <span style={{ fontSize: '0.75rem', color: '#A1A1AA' }}>ms</span>

              <button onClick={handleAddManualCue} style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}>
                Place Cue
              </button>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <button onClick={handleExportWav} style={{ background: '#059669', borderColor: '#059669', fontSize: '0.75rem' }}>
                <Download size={13} /> Export Audition WAV
              </button>
              <button onClick={() => exportSessionJson(session)} className="secondary" style={{ fontSize: '0.75rem' }}>
                <FileJson size={13} /> Export Session JSON
              </button>
              <button onClick={onCommitRevision} disabled={isSaving} style={{ marginLeft: 'auto', fontSize: '0.75rem' }}>
                {isSaving ? 'Committing...' : `Commit Revision ${session.revision + 1} to Firestore`}
              </button>
            </div>

            {importStatus && <div style={{ fontSize: '0.75rem', color: '#60A5FA' }}>{importStatus}</div>}
            {saveMessage && <div style={{ fontSize: '0.75rem', color: '#60A5FA' }}>{saveMessage}</div>}
          </div>
        )}
      </div>
    </div>
  );
};
