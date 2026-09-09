/**
 * Audition WAV rendering & JSON session export.
 *
 * Uses OfflineAudioContext for exact, glitch-free audio mixdown.
 * Generates standard 16-bit stereo PCM WAV files for download.
 */

import { Session } from '../types';

/**
 * Encodes an AudioBuffer into standard 16-bit stereo PCM WAV bytes.
 */
export function audioBufferToWav(buffer: AudioBuffer): Blob {
  const numChannels = buffer.numberOfChannels;
  const sampleRate = buffer.sampleRate;
  const format = 1; // PCM
  const bitDepth = 16;

  let interleaved: Float32Array;
  if (numChannels === 2) {
    const left = buffer.getChannelData(0);
    const right = buffer.getChannelData(1);
    interleaved = new Float32Array(left.length + right.length);
    for (let src = 0, dst = 0; src < left.length; src++) {
      interleaved[dst++] = left[src];
      interleaved[dst++] = right[src];
    }
  } else {
    interleaved = buffer.getChannelData(0);
  }

  const bytesPerSample = bitDepth / 8;
  const blockAlign = numChannels * bytesPerSample;
  const dataSize = interleaved.length * bytesPerSample;
  const headerSize = 44;
  const totalSize = headerSize + dataSize;

  const arrayBuffer = new ArrayBuffer(totalSize);
  const view = new DataView(arrayBuffer);

  function writeString(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  // RIFF chunk descriptor
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + dataSize, true);
  writeString(8, 'WAVE');

  // fmt sub-chunk
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, format, true);
  view.setUint16(22, numChannels, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true); // ByteRate
  view.setUint16(32, blockAlign, true);
  view.setUint16(34, bitDepth, true);

  // data sub-chunk
  writeString(36, 'data');
  view.setUint32(40, dataSize, true);

  // Write PCM samples with clipping protection
  let offset = 44;
  for (let i = 0; i < interleaved.length; i++) {
    const sample = Math.max(-1, Math.min(1, interleaved[i]));
    const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    view.setInt16(offset, intSample, true);
    offset += 2;
  }

  return new Blob([arrayBuffer], { type: 'audio/wav' });
}

/**
 * Renders the session offline and downloads the rendered WAV file.
 */
export async function exportAuditionWav(
  session: Session,
  getBuffer: (assetId: string) => AudioBuffer | undefined
): Promise<Blob> {
  const sampleRate = 48000;
  const sceneSeconds = Math.max(1, session.scene_duration_ms / 1000.0);
  const totalFrames = Math.ceil(sampleRate * sceneSeconds);

  const offlineCtx = new OfflineAudioContext(2, totalFrames, sampleRate);
  const masterGain = offlineCtx.createGain();
  masterGain.gain.setValueAtTime(0.85, 0);
  masterGain.connect(offlineCtx.destination);

  for (const cue of session.cues) {
    const buffer = getBuffer(cue.asset_id);
    if (!buffer) continue;

    const cueStartSec = cue.timeline_start_ms / 1000.0;
    const sourceInSec = cue.source_in_ms / 1000.0;
    const durationSec = (cue.source_out_ms - cue.source_in_ms) / 1000.0;

    const source = offlineCtx.createBufferSource();
    source.buffer = buffer;

    const cueGain = offlineCtx.createGain();
    const linearGain = Math.pow(10, cue.gain_db / 20.0);

    if (cue.envelope_points && cue.envelope_points.length > 0) {
      cueGain.gain.setValueAtTime(0.0001, cueStartSec);
      for (const pt of cue.envelope_points) {
        const ptTime = cueStartSec + pt.offset_ms / 1000.0;
        const ptGain = Math.max(0.0001, pt.level * linearGain);
        cueGain.gain.linearRampToValueAtTime(ptGain, ptTime);
      }
    } else {
      cueGain.gain.setValueAtTime(linearGain, cueStartSec);
    }

    let lastNode: AudioNode = cueGain;
    if (typeof offlineCtx.createStereoPanner === 'function') {
      const panner = offlineCtx.createStereoPanner();
      panner.pan.setValueAtTime(Math.max(-1.0, Math.min(1.0, cue.pan)), cueStartSec);
      cueGain.connect(panner);
      lastNode = panner;
    }

    source.connect(cueGain);
    lastNode.connect(masterGain);

    source.start(cueStartSec, sourceInSec, durationSec);
  }

  const renderedBuffer = await offlineCtx.startRendering();
  const wavBlob = audioBufferToWav(renderedBuffer);

  // Trigger file download in browser
  const url = URL.createObjectURL(wavBlob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `voltra_audition_rev${session.revision}_${session.id}.wav`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  return wavBlob;
}

/**
 * Exports authoritative session JSON document.
 */
export function exportSessionJson(session: Session) {
  const jsonStr = JSON.stringify(session, null, 2);
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `voltra_session_rev${session.revision}_${session.id}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
