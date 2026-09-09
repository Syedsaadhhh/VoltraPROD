/**
 * Typed domain models mirroring backend/app/models.py
 */

export interface Asset {
  id: string;
  source_path: string;
  sha256: string;
  duration_ms: number;
  sample_rate: number;
  channels: number;
  tags: string[];
  source_description: string;
  rights_note: string;
  available: boolean;
}

export interface EnvelopePoint {
  offset_ms: number;
  level: number; // 0.0 to 1.0
}

export interface Cue {
  id: string;
  asset_id: string;
  source_in_ms: number;
  source_out_ms: number;
  timeline_start_ms: number;
  gain_db: number; // -60.0 to 0.0
  pan: number; // -1.0 to 1.0
  envelope_points: EnvelopePoint[];
  track_id: string;
}

export type SessionStatus = 'idle' | 'rehearsing' | 'playing' | 'error';

export interface Session {
  id: string;
  owner_uid: string;
  revision: number;
  scene_duration_ms: number;
  protected_track_ids: string[];
  cues: Cue[];
  status: SessionStatus;
  updated_at: string;
}

export interface DirectorInstruction {
  id: string;
  session_id: string;
  base_revision: number;
  text: string;
  created_at: string;
}

export type CueEditAction = 'add' | 'modify' | 'remove';

export interface CueEdit {
  action: CueEditAction;
  cue_id: string;
  cue?: Cue;
}

export interface EditBatch {
  operation_id: string;
  session_id: string;
  expected_revision: number;
  edits: CueEdit[];
  rationale_summary: string;
}

export type ToolResultStatus = 'success' | 'error' | 'unavailable';

export interface ToolResult {
  operation_id: string;
  status: ToolResultStatus;
  revision: number;
  error_code?: string;
  retryable: boolean;
  data: Record<string, unknown>;
}

export interface PlaybackAck {
  operation_id: string;
  applied_revision: number;
  status: 'applied' | 'failed' | 'rejected';
  decoded_asset_ids: string[];
  error_code?: string;
  observed_at: string;
}

export interface AuditionFeedback {
  event_id: string;
  session_id: string;
  revision: number;
  asset_ids: string[];
  accepted_or_rejected_or_unrated: 'accepted' | 'rejected' | 'unrated';
  director_text?: string;
  observed_at: string;
}

export interface SystemStatusResponse {
  app: string;
  version: string;
  integrations: {
    gemini: {
      configured: boolean;
      available: boolean;
      model: string;
      missing: string[];
    };
    clickhouse: {
      configured: boolean;
      available: boolean;
      host: string | null;
      port: number;
      database: string;
      secure: boolean;
      missing: string[];
    };
    firestore: {
      configured: boolean;
      available: boolean;
      project_id: string | null;
      missing: string[];
    };
  };
}
