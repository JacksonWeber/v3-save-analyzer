/**
 * Save file loader: ZIP extraction, binary detection, and WASM melting.
 * Runs entirely in the browser.
 */

import JSZip from 'jszip';
import type { RawSave } from './types';

let meltWasm: ((data: Uint8Array) => Uint8Array) | null = null;
let wasmInitPromise: Promise<void> | null = null;

/** Register an external WASM melt function (called once after WASM loads). */
export function registerMelter(fn: (data: Uint8Array) => Uint8Array): void {
  meltWasm = fn;
}

/** Initialize WASM melter lazily. Call early but it's safe to call multiple times. */
export function initWasmMelter(): Promise<void> {
  if (wasmInitPromise) return wasmInitPromise;
  wasmInitPromise = (async () => {
    try {
      const wasmUrl = new URL('/wasm/v3_wasm_melter_bg.wasm', window.location.origin).href;
      const jsUrl = new URL('/wasm/v3_wasm_melter.js', window.location.origin).href;
      const tokensUrl = new URL('/wasm/vic3_tokens.txt', window.location.origin).href;

      const mod = await import(/* @vite-ignore */ jsUrl);
      const [, tokensText] = await Promise.all([
        mod.default(wasmUrl),
        fetch(tokensUrl).then((r) => r.ok ? r.text() : ''),
      ]);

      if (tokensText) {
        mod.set_tokens(tokensText);
        console.log('[loader] WASM tokens loaded');
      }

      registerMelter(mod.melt);
      console.log('[loader] WASM melter initialized');
    } catch (e) {
      console.warn('[loader] WASM melter failed to load:', e);
    }
  })();
  return wasmInitPromise;
}

/** Check if raw bytes are Clausewitz binary format. */
function isBinary(data: Uint8Array): boolean {
  if (data.length >= 2) {
    const magic = data[0] | (data[1] << 8);
    if (magic === 0x55ad) return true;
  }
  const sample = data.subarray(0, 500);
  let nonPrintable = 0;
  for (let i = 0; i < sample.length; i++) {
    const b = sample[i];
    if (b < 0x09 || (b >= 0x0e && b < 0x20 && b !== 0x1b)) nonPrintable++;
  }
  return nonPrintable > sample.length * 0.1;
}

export type LoadProgress = (msg: string) => void;

/** Strip SAV header text from melted/text output. */
function stripSavHeader(text: string): string {
  return text.startsWith('SAV0') ? text.replace(/^SAV0[^\n]*\n/, '') : text;
}

/** Find ZIP offset inside a SAV-envelope file. Returns 0 if not found. */
function findZipOffset(bytes: Uint8Array): number {
  for (let i = 4; i < Math.min(bytes.length, 200); i++) {
    if (
      bytes[i] === 0x50 &&
      bytes[i + 1] === 0x4b &&
      bytes[i + 2] === 0x03 &&
      bytes[i + 3] === 0x04
    ) {
      return i;
    }
  }
  return 0;
}

/** Ensure WASM melter is ready, or throw. */
async function ensureMelter(log: LoadProgress): Promise<(data: Uint8Array) => Uint8Array> {
  if (!meltWasm) {
    log('Loading WASM melter...');
    await initWasmMelter();
  }
  if (!meltWasm) {
    throw new Error(
      'Binary/Ironman save detected but WASM melter could not load.\n' +
        'Try using a text-format save (re-save with save_file_format: zip_text_all).',
    );
  }
  return meltWasm;
}

/** Load a .v3 save file from an ArrayBuffer. Returns raw text content. */
export async function loadSave(
  buf: ArrayBuffer,
  onProgress?: LoadProgress,
): Promise<RawSave> {
  const originalBytes = new Uint8Array(buf);
  const log = onProgress ?? (() => {});

  const hasSavHeader =
    originalBytes[0] === 0x53 && // 'S'
    originalBytes[1] === 0x41 && // 'A'
    originalBytes[2] === 0x56 && // 'V'
    originalBytes[3] === 0x30;   // '0'

  // Determine where the actual data starts (after SAV header if present)
  let dataBytes = originalBytes;
  let dataBuf = buf;
  if (hasSavHeader) {
    const zipOff = findZipOffset(originalBytes);
    if (zipOff > 0) {
      dataBytes = originalBytes.subarray(zipOff);
      dataBuf = dataBytes.buffer.slice(dataBytes.byteOffset, dataBytes.byteOffset + dataBytes.byteLength);
    }
  }

  const isZip =
    dataBytes[0] === 0x50 &&
    dataBytes[1] === 0x4b &&
    dataBytes[2] === 0x03 &&
    dataBytes[3] === 0x04;

  // --- Non-ZIP path ---
  if (!isZip) {
    if (isBinary(dataBytes)) {
      // Raw binary without ZIP: pass full original file to WASM melter
      const melt = await ensureMelter(log);
      log('Melting binary save...');
      const melted = melt(originalBytes);
      const text = new TextDecoder('utf-8').decode(melted);
      return { gamestate: stripSavHeader(text), meta: '' };
    }
    log('Reading plain text save...');
    const text = new TextDecoder('utf-8').decode(dataBytes);
    return { gamestate: stripSavHeader(text), meta: '' };
  }

  // --- ZIP path ---
  log('Extracting save archive...');
  const zip = await JSZip.loadAsync(dataBuf);

  let gsEntry: JSZip.JSZipObject | null = null;
  let metaEntry: JSZip.JSZipObject | null = null;
  zip.forEach((path, entry) => {
    const lower = path.toLowerCase();
    if (lower.includes('gamestate')) gsEntry = entry;
    else if (lower.includes('meta')) metaEntry = entry;
  });

  if (!gsEntry) {
    throw new Error('No gamestate file found in save archive.');
  }

  log('Checking save format...');
  const gsBytes = await (gsEntry as JSZip.JSZipObject).async('uint8array');

  if (isBinary(gsBytes)) {
    // Binary gamestate inside ZIP: pass the FULL ORIGINAL file to the WASM melter,
    // because vic3save expects the complete envelope (SAV header + ZIP), not raw bytes.
    const melt = await ensureMelter(log);
    log('Melting binary save (this may take a moment)...');
    const melted = melt(originalBytes);
    const text = new TextDecoder('utf-8').decode(melted);
    return { gamestate: stripSavHeader(text), meta: '' };
  }

  log('Decoding text save...');
  const gamestate = new TextDecoder('utf-8').decode(gsBytes);
  let meta = '';
  if (metaEntry) {
    const metaBytes = await (metaEntry as JSZip.JSZipObject).async('uint8array');
    meta = new TextDecoder('utf-8').decode(metaBytes);
  }
  return { gamestate, meta };
}
