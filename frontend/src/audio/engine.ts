/**
 * Web Audio Scheduling Engine for VoltraPROD Sound Rehearsal.
 *
 * Implements:
 * - Explicit AudioContext initialization via user gesture (Enable Audio)
 * - Exact sample-accurate scheduling for timeline cues
 * - Gain dB conversion, stereo panning [-1.0, 1.0], volume envelopes
 * - Immediate stop and reschedule on seek, pause, or cue edit (prevents ghost audio)
 * - Output limiting and master headroom for hearing safety
 */

import { Cue, Session } from '../types';

export class AudioEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private limiter: DynamicsCompressorNode | null = null;

  // Cached decoded audio buffers: assetId -> AudioBuffer
  private bufferCache: Map<string, AudioBuffer> = new Map();

  // Active playing source nodes for cleanup: cueId -> { source, gainNode, panner }
  private activeNodes: Map<string, { source: AudioBufferSourceNode; gain: GainNode }> = new Map();

  private isPlaying: boolean = false;
  private playbackStartTime: number = 0; // AudioContext time when current playback segment started
  private startOffsetMs: number = 0; // Timeline position in ms when playback started
  private timerId: number | null = null;

  // Listeners
  private onTimeUpdateCallback: ((timeMs: number) => void) | null = null;
  private onEndedCallback: (() => void) | null = null;

  /**
   * Initializes AudioContext upon user gesture.
   */
  public async initAudio(): Promise<boolean> {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      this.ctx = new AudioCtx();

      // Master output chain with limiter
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.setValueAtTime(0.85, this.ctx.currentTime); // Safe headroom

      this.limiter = this.ctx.createDynamicsCompressor();
      this.limiter.threshold.setValueAtTime(-1.0, this.ctx.currentTime);
      this.limiter.knee.setValueAtTime(0.0, this.ctx.currentTime);
      this.limiter.ratio.setValueAtTime(20.0, this.ctx.currentTime);
      this.limiter.attack.setValueAtTime(0.001, this.ctx.currentTime);
      this.limiter.release.setValueAtTime(0.05, this.ctx.currentTime);

      this.masterGain.connect(this.limiter);
      this.limiter.connect(this.ctx.destination);
    }

    if (this.ctx.state === 'suspended') {
      await this.ctx.resume();
    }

    return this.ctx.state === 'running';
  }

  public isReady(): boolean {
    return this.ctx !== null && this.ctx.state === 'running';
  }

  public getContext(): AudioContext | null {
    return this.ctx;
  }

  /**
   * Loads and decodes an audio buffer from a URL or local Blob.
   */
  public async loadAudio(assetId: string, url: string): Promise<AudioBuffer> {
    if (this.bufferCache.has(assetId)) {
      return this.bufferCache.get(assetId)!;
    }

    if (!this.ctx) {
      throw new Error('AudioContext is not initialized. User must enable audio first.');
    }

    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Failed to load audio asset '${assetId}' from ${url} (HTTP ${response.status})`);
    }

    const arrayBuffer = await response.arrayBuffer();
    const audioBuffer = await this.ctx.decodeAudioData(arrayBuffer);
    this.bufferCache.set(assetId, audioBuffer);
    return audioBuffer;
  }

  public storeBuffer(assetId: string, buffer: AudioBuffer) {
    this.bufferCache.set(assetId, buffer);
  }

  public getBuffer(assetId: string): AudioBuffer | undefined {
    return this.bufferCache.get(assetId);
  }

  /**
   * Stops all active source nodes immediately.
   * Prevents duplicate or ghost audio on seek, pause, or edit.
   */
  public stopAllSources() {
    this.activeNodes.forEach(({ source }) => {
      try {
        source.stop();
        source.disconnect();
      } catch {
        // Node may have already ended
      }
    });
    this.activeNodes.clear();
  }

  /**
   * Plays timeline from current offsetMs.
   */
  public play(session: Session, offsetMs: number = 0) {
    if (!this.ctx || this.ctx.state !== 'running') {
      throw new Error('AudioContext not ready');
    }

    this.stopAllSources();
    this.isPlaying = true;
    this.startOffsetMs = offsetMs;
    this.playbackStartTime = this.ctx.currentTime;

    const currentCtxTime = this.ctx.currentTime;
    const sceneDurationMs = session.scene_duration_ms;

    // Schedule all cues that fall into or after the offsetMs
    for (const cue of session.cues) {
      this.scheduleCue(cue, currentCtxTime, offsetMs);
    }

    // Start UI time tracking ticker
    this.startTicker(sceneDurationMs);
  }

  private scheduleCue(cue: Cue, baseCtxTime: number, timelineOffsetMs: number) {
    if (!this.ctx || !this.masterGain) return;

    const buffer = this.bufferCache.get(cue.asset_id);
    if (!buffer) {
      // Audio buffer not yet loaded or missing
      return;
    }

    const cueStartMs = cue.timeline_start_ms;
    const cueDurationMs = cue.source_out_ms - cue.source_in_ms;
    const cueEndMs = cueStartMs + cueDurationMs;

    // If cue already finished before the current timeline offset, skip
    if (cueEndMs <= timelineOffsetMs) {
      return;
    }

    // Calculate when the cue starts in AudioContext time
    let nodeStartCtxTime: number;
    let sourceOffsetSec: number;
    let playDurationSec: number;

    if (cueStartMs >= timelineOffsetMs) {
      // Cue starts in the future relative to current playhead
      const delaySec = (cueStartMs - timelineOffsetMs) / 1000.0;
      nodeStartCtxTime = baseCtxTime + delaySec;
      sourceOffsetSec = cue.source_in_ms / 1000.0;
      playDurationSec = cueDurationMs / 1000.0;
    } else {
      // Cue is already active mid-flight
      const elapsedMs = timelineOffsetMs - cueStartMs;
      nodeStartCtxTime = baseCtxTime;
      sourceOffsetSec = (cue.source_in_ms + elapsedMs) / 1000.0;
      playDurationSec = (cueDurationMs - elapsedMs) / 1000.0;
    }

    // Create source node
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;

    // Create cue gain node (dB to linear gain)
    const cueGain = this.ctx.createGain();
    const linearGain = Math.pow(10, cue.gain_db / 20.0);

    // Apply envelope if present
    if (cue.envelope_points && cue.envelope_points.length > 0) {
      cueGain.gain.setValueAtTime(0.0001, nodeStartCtxTime);
      for (const pt of cue.envelope_points) {
        const ptTime = nodeStartCtxTime + pt.offset_ms / 1000.0;
        const ptGain = Math.max(0.0001, pt.level * linearGain);
        cueGain.gain.linearRampToValueAtTime(ptGain, ptTime);
      }
    } else {
      cueGain.gain.setValueAtTime(linearGain, nodeStartCtxTime);
    }

    // Stereo panning node
    let lastNode: AudioNode = cueGain;
    if (typeof this.ctx.createStereoPanner === 'function') {
      const panner = this.ctx.createStereoPanner();
      panner.pan.setValueAtTime(Math.max(-1.0, Math.min(1.0, cue.pan)), nodeStartCtxTime);
      cueGain.connect(panner);
      lastNode = panner;
    }

    source.connect(cueGain);
    lastNode.connect(this.masterGain);

    source.start(nodeStartCtxTime, sourceOffsetSec, playDurationSec);
    this.activeNodes.set(cue.id, { source, gain: cueGain });

    source.onended = () => {
      this.activeNodes.delete(cue.id);
    };
  }

  public pause(currentMs: number) {
    this.isPlaying = false;
    this.stopAllSources();
    this.stopTicker();
    this.startOffsetMs = currentMs;
  }

  public seek(session: Session, newOffsetMs: number) {
    const wasPlaying = this.isPlaying;
    this.stopAllSources();
    this.stopTicker();
    this.startOffsetMs = newOffsetMs;

    if (wasPlaying) {
      this.play(session, newOffsetMs);
    } else if (this.onTimeUpdateCallback) {
      this.onTimeUpdateCallback(newOffsetMs);
    }
  }

  public getCurrentTimeMs(): number {
    if (!this.isPlaying || !this.ctx) {
      return this.startOffsetMs;
    }
    const elapsedSec = this.ctx.currentTime - this.playbackStartTime;
    return this.startOffsetMs + elapsedSec * 1000.0;
  }

  private startTicker(sceneDurationMs: number) {
    this.stopTicker();
    const tick = () => {
      const currentMs = this.getCurrentTimeMs();
      if (currentMs >= sceneDurationMs) {
        this.pause(sceneDurationMs);
        if (this.onTimeUpdateCallback) this.onTimeUpdateCallback(sceneDurationMs);
        if (this.onEndedCallback) this.onEndedCallback();
        return;
      }
      if (this.onTimeUpdateCallback) {
        this.onTimeUpdateCallback(currentMs);
      }
      this.timerId = window.requestAnimationFrame(tick);
    };
    this.timerId = window.requestAnimationFrame(tick);
  }

  private stopTicker() {
    if (this.timerId !== null) {
      window.cancelAnimationFrame(this.timerId);
      this.timerId = null;
    }
  }

  public setOnTimeUpdate(cb: (timeMs: number) => void) {
    this.onTimeUpdateCallback = cb;
  }

  public setOnEnded(cb: () => void) {
    this.onEndedCallback = cb;
  }
}

export const audioEngine = new AudioEngine();
