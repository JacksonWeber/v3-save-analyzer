/* tslint:disable */
/* eslint-disable */

/**
 * Check if the given data is a binary (non-text) Vic3 save.
 */
export function is_binary(data: Uint8Array): boolean;

/**
 * Melt a binary Vic3 save file into plaintext.
 * Takes the raw bytes of the save (the gamestate file from the zip, or the whole file).
 * Returns the melted plaintext bytes as Uint8Array.
 */
export function melt(data: Uint8Array): Uint8Array;

/**
 * Set the token resolver data. Call this before melt().
 * Tokens format: one token per line, "0xHHHH name" (hex ID followed by space then name).
 * Example: "0x0001 date\n0x0002 player\n..."
 */
export function set_tokens(text: string): void;

export type InitInput = RequestInfo | URL | Response | BufferSource | WebAssembly.Module;

export interface InitOutput {
    readonly memory: WebAssembly.Memory;
    readonly is_binary: (a: number, b: number) => number;
    readonly melt: (a: number, b: number, c: number) => void;
    readonly set_tokens: (a: number, b: number, c: number) => void;
    readonly __wbindgen_export: (a: number, b: number) => number;
    readonly __wbindgen_add_to_stack_pointer: (a: number) => number;
    readonly __wbindgen_export2: (a: number, b: number, c: number, d: number) => number;
}

export type SyncInitInput = BufferSource | WebAssembly.Module;

/**
 * Instantiates the given `module`, which can either be bytes or
 * a precompiled `WebAssembly.Module`.
 *
 * @param {{ module: SyncInitInput }} module - Passing `SyncInitInput` directly is deprecated.
 *
 * @returns {InitOutput}
 */
export function initSync(module: { module: SyncInitInput } | SyncInitInput): InitOutput;

/**
 * If `module_or_path` is {RequestInfo} or {URL}, makes a request and
 * for everything else, calls `WebAssembly.instantiate` directly.
 *
 * @param {{ module_or_path: InitInput | Promise<InitInput> }} module_or_path - Passing `InitInput` directly is deprecated.
 *
 * @returns {Promise<InitOutput>}
 */
export default function __wbg_init (module_or_path?: { module_or_path: InitInput | Promise<InitInput> } | InitInput | Promise<InitInput>): Promise<InitOutput>;
