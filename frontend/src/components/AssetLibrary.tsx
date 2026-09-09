import React, { useState } from 'react';
import { Database, Play, Volume2, CheckCircle, Tag } from 'lucide-react';
import { Asset } from '../types';
import { audioEngine } from '../audio/engine';

interface AssetLibraryProps {
  assets: Asset[];
  isLoading: boolean;
  onRefresh?: () => void;
}

export const AssetLibrary: React.FC<AssetLibraryProps> = ({ assets, isLoading }) => {
  const [auditioningId, setAuditioningId] = useState<string | null>(null);

  const handleAuditionAsset = async (asset: Asset) => {
    try {
      setAuditioningId(asset.id);
      await audioEngine.initAudio();
      const ctx = audioEngine.getContext();
      if (!ctx) return;

      const buffer = await audioEngine.ensureAssetLoaded(asset.id, asset.source_path);
      if (!buffer) return;

      const source = ctx.createBufferSource();
      source.buffer = buffer;
      const gain = ctx.createGain();
      gain.gain.setValueAtTime(0.7, ctx.currentTime);
      source.connect(gain);
      gain.connect(ctx.destination);
      source.start(0);

      source.onended = () => {
        setAuditioningId((current) => (current === asset.id ? null : current));
      };
    } catch (err) {
      console.error('Error auditioning asset:', err);
      setAuditioningId(null);
    }
  };

  return (
    <div className="card" style={{ background: '#18181B', borderColor: '#27272A', padding: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#FAFAFA', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Database size={16} color="#3B82F6" />
          <span>Sound Catalog</span>
          <span className="badge badge-brand" style={{ fontSize: '0.65rem' }}>ClickHouse Cloud MCP</span>
        </h3>
        <span style={{ fontSize: '0.75rem', color: '#A1A1AA' }}>
          {isLoading ? 'Querying...' : `${assets.length} Assets Available`}
        </span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.6rem', maxHeight: '200px', overflowY: 'auto', paddingRight: '0.25rem' }}>
        {assets.map((asset) => {
          const isAuditioning = auditioningId === asset.id;
          return (
            <div
              key={asset.id}
              style={{
                background: '#09090B',
                border: '1px solid #27272A',
                borderRadius: '0.5rem',
                padding: '0.5rem 0.65rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.35rem',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.78rem', fontWeight: 600, color: '#FAFAFA' }}>
                  {asset.source_description || asset.id.replace('asset_', '')}
                </span>
                <span style={{ fontSize: '0.68rem', color: '#A1A1AA' }}>
                  {(asset.duration_ms / 1000).toFixed(1)}s
                </span>
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                {asset.tags.slice(0, 3).map((tag) => (
                  <span
                    key={tag}
                    style={{
                      fontSize: '0.65rem',
                      background: '#18181B',
                      color: '#A1A1AA',
                      padding: '0.1rem 0.35rem',
                      borderRadius: '3px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '2px',
                    }}
                  >
                    <Tag size={9} />
                    {tag}
                  </span>
                ))}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.2rem' }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.68rem', color: '#10B981' }}>
                  <CheckCircle size={11} /> Playable
                </span>
                <button
                  onClick={() => handleAuditionAsset(asset)}
                  style={{
                    padding: '0.2rem 0.5rem',
                    fontSize: '0.72rem',
                    background: isAuditioning ? '#8B5CF6' : '#27272A',
                    borderColor: '#3F3F46',
                    color: '#FAFAFA',
                  }}
                >
                  {isAuditioning ? <Volume2 size={12} /> : <Play size={12} />}
                  {isAuditioning ? 'Auditioning' : 'Sample'}
                </button>
              </div>
            </div>
          );
        })}

        {assets.length === 0 && !isLoading && (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '1rem', color: '#71717A', fontSize: '0.8rem' }}>
            No sound assets discovered in ClickHouse catalog.
          </div>
        )}
      </div>
    </div>
  );
};
