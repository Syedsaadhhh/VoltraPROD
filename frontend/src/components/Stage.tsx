import React, { useRef, useState, useEffect } from 'react';
import { Volume2, VolumeX, Play, Pause, RotateCcw, Video } from 'lucide-react';
import { Session } from '../types';

interface StageProps {
  session: Session;
  currentTimeMs: number;
  onSeek: (timeMs: number) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  audioReady: boolean;
  onEnableAudio: () => void;
}

export const Stage: React.FC<StageProps> = ({
  session,
  currentTimeMs,
  onSeek,
  isPlaying,
  onTogglePlay,
  audioReady,
  onEnableAudio,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoSrc, setVideoSrc] = useState<string | null>(null);
  const [videoFileName, setVideoFileName] = useState<string | null>(null);
  const [measuredDriftMs, setMeasuredDriftMs] = useState<number | null>(null);

  // Sync HTML5 video with audio engine playhead
  useEffect(() => {
    if (videoRef.current && videoSrc) {
      const vid = videoRef.current;
      const targetSec = currentTimeMs / 1000.0;
      const drift = Math.abs(vid.currentTime - targetSec) * 1000.0;
      setMeasuredDriftMs(Math.round(drift));

      // Resync if video drifts by more than 80ms
      if (drift > 80) {
        vid.currentTime = targetSec;
      }

      if (isPlaying && vid.paused) {
        vid.play().catch(() => {});
      } else if (!isPlaying && !vid.paused) {
        vid.pause();
      }
    }
  }, [currentTimeMs, isPlaying, videoSrc]);

  const handleVideoImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const url = URL.createObjectURL(file);
    setVideoSrc(url);
    setVideoFileName(file.name);
  };

  const formatTimecode = (ms: number): string => {
    const totalSeconds = Math.max(0, ms / 1000.0);
    const mins = Math.floor(totalSeconds / 60);
    const secs = Math.floor(totalSeconds % 60);
    const millis = Math.floor((totalSeconds % 1) * 1000);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${millis.toString().padStart(3, '0')}`;
  };

  return (
    <div className="card" style={{ padding: '1rem', background: '#0b0f19', borderColor: '#1e293b' }}>
      {/* Video / Visual Stage Viewport */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          height: '280px',
          backgroundColor: '#020617',
          borderRadius: '0.5rem',
          overflow: 'hidden',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          border: '1px solid #1e293b',
        }}
      >
        {videoSrc ? (
          <video
            ref={videoRef}
            src={videoSrc}
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
            muted
          />
        ) : (
          <div style={{ textAlign: 'center', color: '#64748b' }}>
            <Video size={48} style={{ margin: '0 auto 0.5rem', opacity: 0.5 }} />
            <p style={{ fontSize: '0.9rem', fontWeight: 500 }}>No video loaded for scene preview</p>
            <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
              Import local camera rehearsal file below or rehearse sound with timeline alone.
            </p>
            <label
              style={{
                display: 'inline-block',
                marginTop: '0.75rem',
                cursor: 'pointer',
                background: '#1e293b',
                color: '#cbd5e1',
                padding: '0.4rem 0.8rem',
                borderRadius: '0.375rem',
                fontSize: '0.8rem',
                border: '1px solid #334155',
              }}
            >
              Import Scene Video (.mp4, .webm)
              <input
                type="file"
                accept="video/*"
                onChange={handleVideoImport}
                style={{ display: 'none' }}
              />
            </label>
          </div>
        )}

        {/* Video label badge */}
        {videoFileName && (
          <div
            style={{
              position: 'absolute',
              top: '0.5rem',
              left: '0.5rem',
              background: 'rgba(15, 23, 42, 0.8)',
              padding: '0.2rem 0.5rem',
              borderRadius: '0.25rem',
              fontSize: '0.7rem',
              color: '#38bdf8',
            }}
          >
            Local Video: {videoFileName}
          </div>
        )}

        {/* Audio Enable Overlay if not enabled */}
        {!audioReady && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(15, 23, 42, 0.85)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.75rem',
              zIndex: 10,
            }}
          >
            <VolumeX size={36} color="#f87171" />
            <p style={{ fontSize: '0.9rem', color: '#f1f5f9', fontWeight: 600 }}>
              Browser Audio Policy: User Gesture Required
            </p>
            <button onClick={onEnableAudio} style={{ padding: '0.6rem 1.2rem', fontSize: '0.9rem' }}>
              <Volume2 size={16} style={{ display: 'inline', marginRight: '0.4rem' }} />
              Enable Audio Context
            </button>
          </div>
        )}
      </div>

      {/* Playback Controls & Metrics Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '0.75rem',
          marginTop: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button
            onClick={onTogglePlay}
            disabled={!audioReady}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: '40px',
              height: '40px',
              borderRadius: '50%',
              padding: 0,
            }}
          >
            {isPlaying ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: '2px' }} />}
          </button>

          <button
            onClick={() => onSeek(0)}
            disabled={!audioReady}
            style={{
              background: '#1e293b',
              border: '1px solid #334155',
              padding: '0.4rem 0.6rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.3rem',
            }}
          >
            <RotateCcw size={14} />
            <span style={{ fontSize: '0.8rem' }}>Reset</span>
          </button>

          <div
            style={{
              fontFamily: 'monospace',
              fontSize: '1.1rem',
              fontWeight: 700,
              color: '#38bdf8',
              marginLeft: '0.5rem',
            }}
          >
            {formatTimecode(currentTimeMs)}{' '}
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              / {formatTimecode(session.scene_duration_ms)}
            </span>
          </div>
        </div>

        {/* Video-Audio Drift Indicator */}
        {measuredDriftMs !== null && videoSrc && (
          <div style={{ fontSize: '0.75rem', color: measuredDriftMs > 50 ? '#facc15' : '#4ade80' }}>
            Measured A/V Drift: {measuredDriftMs}ms (locally bounded)
          </div>
        )}
      </div>
    </div>
  );
};
