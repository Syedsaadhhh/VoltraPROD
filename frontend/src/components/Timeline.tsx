import React, { useState } from 'react';
import { Lock, Sliders, Trash2 } from 'lucide-react';
import { Cue, Session } from '../types';

interface TimelineProps {
  session: Session;
  currentTimeMs: number;
  onSeek: (timeMs: number) => void;
  onUpdateCue: (updatedCue: Cue) => void;
  onDeleteCue: (cueId: string) => void;
}

export const Timeline: React.FC<TimelineProps> = ({
  session,
  currentTimeMs,
  onSeek,
  onUpdateCue,
  onDeleteCue,
}) => {
  const [selectedCueId, setSelectedCueId] = useState<string | null>(null);

  const TRACKS = [
    { id: 'dialogue', name: 'Dialogue (Actor Mic)', protected: true, color: '#f43f5e' },
    { id: 'foley', name: 'Foley & Movement', protected: false, color: '#38bdf8' },
    { id: 'sfx', name: 'Sound FX & Hits', protected: false, color: '#fbbf24' },
    { id: 'ambience', name: 'Ambience / Room Bed', protected: false, color: '#a855f7' },
  ];

  const totalMs = Math.max(1000, session.scene_duration_ms);
  const playheadPercent = Math.min(100, Math.max(0, (currentTimeMs / totalMs) * 100));

  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    onSeek(ratio * totalMs);
  };

  const selectedCue = session.cues.find((c) => c.id === selectedCueId);

  return (
    <div className="card" style={{ padding: '1rem', background: '#0f172a', borderColor: '#1e293b' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '0.75rem',
        }}
      >
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>Rehearsal Multi-Track Timeline</h2>
        <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
          Scene Duration: {(totalMs / 1000).toFixed(1)}s (Revision {session.revision})
        </span>
      </div>

      {/* Timeline Ruler & Track Container */}
      <div style={{ position: 'relative', border: '1px solid #334155', borderRadius: '0.5rem', background: '#020617' }}>
        {/* Ruler Header */}
        <div
          onClick={handleTimelineClick}
          style={{
            height: '24px',
            background: '#1e293b',
            borderBottom: '1px solid #334155',
            position: 'relative',
            cursor: 'pointer',
          }}
        >
          {[0, 25, 50, 75, 100].map((pct) => (
            <span
              key={pct}
              style={{
                position: 'absolute',
                left: `${pct}%`,
                transform: pct === 100 ? 'translateX(-100%)' : 'translateX(0)',
                fontSize: '0.65rem',
                color: '#94a3b8',
                padding: '0 4px',
                fontFamily: 'monospace',
              }}
            >
              {((totalMs * pct) / 100000).toFixed(1)}s
            </span>
          ))}
        </div>

        {/* Tracks List */}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {TRACKS.map((track) => {
            const trackCues = session.cues.filter((c) => c.track_id === track.id);
            return (
              <div
                key={track.id}
                style={{
                  display: 'flex',
                  borderBottom: '1px solid #1e293b',
                  minHeight: '48px',
                }}
              >
                {/* Track Header Label */}
                <div
                  style={{
                    width: '180px',
                    padding: '0.5rem',
                    borderRight: '1px solid #1e293b',
                    background: '#0b0f19',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <span style={{ fontSize: '0.75rem', fontWeight: 600, color: '#cbd5e1' }}>
                    {track.name}
                  </span>
                  {track.protected && (
                    <span
                      title="Protected Dialogue: Cannot be altered or deleted by agent"
                      style={{ display: 'flex', alignItems: 'center', color: '#f43f5e', fontSize: '0.65rem' }}
                    >
                      <Lock size={12} style={{ marginRight: '2px' }} />
                      LOCK
                    </span>
                  )}
                </div>

                {/* Track Lanes */}
                <div
                  onClick={handleTimelineClick}
                  style={{
                    flex: 1,
                    position: 'relative',
                    background: '#020617',
                    cursor: 'pointer',
                  }}
                >
                  {trackCues.map((cue) => {
                    const leftPct = (cue.timeline_start_ms / totalMs) * 100;
                    const durationMs = cue.source_out_ms - cue.source_in_ms;
                    const widthPct = Math.max(1.5, (durationMs / totalMs) * 100);
                    const isSelected = cue.id === selectedCueId;

                    return (
                      <div
                        key={cue.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedCueId(cue.id);
                        }}
                        style={{
                          position: 'absolute',
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                          top: '6px',
                          bottom: '6px',
                          backgroundColor: track.color,
                          borderRadius: '4px',
                          opacity: isSelected ? 1.0 : 0.85,
                          border: isSelected ? '2px solid #ffffff' : '1px solid rgba(255,255,255,0.2)',
                          cursor: 'pointer',
                          padding: '2px 4px',
                          overflow: 'hidden',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '0.65rem',
                            fontWeight: 600,
                            color: '#000000',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                        >
                          {cue.id}
                        </span>
                        <span style={{ fontSize: '0.6rem', color: '#000000', opacity: 0.8 }}>
                          {cue.gain_db}dB
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>

        {/* Animated Playhead Marker */}
        <div
          style={{
            position: 'absolute',
            left: `${playheadPercent}%`,
            top: 0,
            bottom: 0,
            width: '2px',
            backgroundColor: '#ef4444',
            pointerEvents: 'none',
            zIndex: 20,
          }}
        >
          <div
            style={{
              width: '8px',
              height: '8px',
              backgroundColor: '#ef4444',
              borderRadius: '50%',
              transform: 'translateX(-3px)',
            }}
          />
        </div>
      </div>

      {/* Selected Cue Inspector */}
      {selectedCue && (
        <div
          style={{
            marginTop: '1rem',
            padding: '0.75rem',
            background: '#1e293b',
            borderRadius: '0.5rem',
            border: '1px solid #334155',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Sliders size={16} color="#38bdf8" />
              <strong style={{ fontSize: '0.85rem' }}>Cue Inspector: {selectedCue.id}</strong>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>({selectedCue.asset_id})</span>
            </div>
            {selectedCue.track_id !== 'dialogue' && (
              <button
                onClick={() => {
                  onDeleteCue(selectedCue.id);
                  setSelectedCueId(null);
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#f87171',
                  cursor: 'pointer',
                  padding: '0.2rem',
                }}
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
              gap: '0.75rem',
              marginTop: '0.5rem',
              fontSize: '0.8rem',
            }}
          >
            <div>
              <label style={{ display: 'block', color: '#94a3b8' }}>Start (ms):</label>
              <input
                type="number"
                value={selectedCue.timeline_start_ms}
                onChange={(e) =>
                  onUpdateCue({
                    ...selectedCue,
                    timeline_start_ms: Math.max(0, parseInt(e.target.value) || 0),
                  })
                }
                disabled={selectedCue.track_id === 'dialogue'}
                style={{ width: '100%', background: '#0b0f19', color: '#fff', border: '1px solid #475569', borderRadius: '4px', padding: '0.2rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', color: '#94a3b8' }}>Gain (dB, [-60, 0]):</label>
              <input
                type="range"
                min="-60"
                max="0"
                step="0.5"
                value={selectedCue.gain_db}
                onChange={(e) =>
                  onUpdateCue({
                    ...selectedCue,
                    gain_db: parseFloat(e.target.value),
                  })
                }
                disabled={selectedCue.track_id === 'dialogue'}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem' }}>{selectedCue.gain_db.toFixed(1)} dB</span>
            </div>

            <div>
              <label style={{ display: 'block', color: '#94a3b8' }}>Pan ([-1.0, 1.0]):</label>
              <input
                type="range"
                min="-1"
                max="1"
                step="0.05"
                value={selectedCue.pan}
                onChange={(e) =>
                  onUpdateCue({
                    ...selectedCue,
                    pan: parseFloat(e.target.value),
                  })
                }
                disabled={selectedCue.track_id === 'dialogue'}
                style={{ width: '100%' }}
              />
              <span style={{ fontSize: '0.75rem' }}>
                {selectedCue.pan === 0 ? 'Center' : selectedCue.pan < 0 ? `L ${Math.abs(selectedCue.pan).toFixed(2)}` : `R ${selectedCue.pan.toFixed(2)}`}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
