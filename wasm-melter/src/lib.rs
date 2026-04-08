use std::io::{BufReader, Cursor};
use std::sync::Mutex;
use vic3save::{BasicTokenResolver, FailedResolveStrategy, MeltOptions, Vic3File, Vic3Melt};
use wasm_bindgen::prelude::*;

static TOKENS: Mutex<Option<BasicTokenResolver>> = Mutex::new(None);

/// Set the token resolver data. Call this before melt().
/// Tokens format: one token per line, "0xHHHH name" (hex ID followed by space then name).
/// Example: "0x0001 date\n0x0002 player\n..."
#[wasm_bindgen]
pub fn set_tokens(text: &str) -> Result<(), JsError> {
    let reader = BufReader::new(Cursor::new(text.as_bytes()));
    let resolver = BasicTokenResolver::from_text_lines(reader)
        .map_err(|e| JsError::new(&format!("Failed to parse tokens: {}", e)))?;
    *TOKENS
        .lock()
        .map_err(|e| JsError::new(&format!("Lock error: {}", e)))? = Some(resolver);
    Ok(())
}

/// Melt a binary Vic3 save file into plaintext.
/// Takes the raw bytes of the save (the gamestate file from the zip, or the whole file).
/// Returns the melted plaintext bytes as Uint8Array.
#[wasm_bindgen]
pub fn melt(data: &[u8]) -> Result<js_sys::Uint8Array, JsError> {
    let file = Vic3File::from_slice(data)
        .map_err(|e| JsError::new(&format!("Failed to parse Vic3 file: {}", e)))?;

    let guard = TOKENS
        .lock()
        .map_err(|e| JsError::new(&format!("Lock error: {}", e)))?;

    let mut out = Cursor::new(Vec::new());
    let options = MeltOptions::new().on_failed_resolve(FailedResolveStrategy::Ignore);

    match guard.as_ref() {
        Some(tokens) => {
            (&file)
                .melt(options, tokens, &mut out)
                .map_err(|e| JsError::new(&format!("Failed to melt: {}", e)))?;
        }
        None => {
            // No tokens loaded — melt with empty resolver (unknown keys skipped)
            let empty_tokens =
                BasicTokenResolver::from_text_lines(BufReader::new(Cursor::new(b"" as &[u8])))
                    .unwrap_or_else(|_| panic!("empty resolver"));
            (&file)
                .melt(options, &empty_tokens, &mut out)
                .map_err(|e| JsError::new(&format!("Failed to melt: {}", e)))?;
        }
    }

    Ok(js_sys::Uint8Array::from(out.into_inner().as_slice()))
}

/// Check if the given data is a binary (non-text) Vic3 save.
#[wasm_bindgen]
pub fn is_binary(data: &[u8]) -> bool {
    Vic3File::from_slice(data)
        .map(|f| f.header().kind().is_binary())
        .unwrap_or(false)
}
