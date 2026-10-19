/**
 * OCR Engine & Worker Pool using Tesseract.js
 * 
 * Implements a Singleton Worker pattern to avoid re-initializing Tesseract workers
 * on every call. Supports multi-language detection with configurable cachePath
 * pointing locally to ./assets/tessdata to eliminate repetitive network downloads.
 */

import Tesseract from 'tesseract.js';

/**
 * Singleton OCR Worker instance
 * Created once and reused across all recognize calls
 */
let ocrWorker = null;

/**
 * Initialize the Tesseract worker (Singleton pattern)
 * @param {string} [lang='ara+eng'] - Language codes for OCR
 * @param {string} [cachePath='./assets/tessdata'] - Path to local tessdata directory
 * @returns {Promise<Tesseract.Worker>} - Initialized worker instance
 */
async function initializeWorker(lang = 'ara+eng', cachePath = './assets/tessdata') {
  if (!ocrWorker) {
    try {
      ocrWorker = new Tesseract.Worker(lang, {
        cachePath: cachePath,
        // Tesseract 5+ supports worker init without immediately loading languages
        // We'll load languages as needed
      });
      await ocrWorker.init();
      await ocrWorker.setParameters({ tessedit_char_whitelist: '' });
      console.log(`[OCR Service] Worker initialized with languages: ${lang}, cachePath: ${cachePath}`);
    } catch (error) {
      throw new Error(`Failed to initialize Tesseract worker: ${error.message}`);
    }
  }
  return ocrWorker;
}

/**
 * Recognize text from an image buffer using Tesseract
 * @param {Buffer} imageBuffer - Processed image buffer
 * @param {Object} [options] - Recognition options
 * @param {string} [options.lang='ara+eng'] - Language codes (default: Arabic + English)
 * @param {boolean} [options.enhance=true] - Whether preprocessing was already applied
 * @returns {Promise<Object>} - Recognition results with text, confidence, and lines
 */
export async function recognize(imageBuffer, { lang = 'ara+eng', enhance = true } = {}) {
  if (!imageBuffer || imageBuffer.length === 0) {
    throw new Error('Invalid image buffer: empty or null buffer provided');
  }

  // Initialize worker if not already done
  const worker = await initializeWorker(lang);

  try {
    // Create a temporary file for Tesseract to process
    // Tesseract.js can work with base64 data URLs or file paths
    const base64 = imageBuffer.toString('base64');
    const dataURL = `data:image/png;base64,${base64}`;
    
    // Perform OCR recognition
    const result = await worker.recognize(dataURL);
    
    // Extract confidence score (average of all recognitions)
    const confidence = result.confidence !== undefined 
      ? Math.round(result.confidence) 
      : 0;
    
    // Extract text, trimming whitespace
    const text = result.data?.text || '';
    const cleanText = text.trim().replace(/\s+/g, ' ');
    
    // Extract line-level bounding boxes and text
    const lines = [];
    if (result.lines && Array.isArray(result.lines)) {
      result.lines.forEach(line => {
        if (line.text && line.text.trim()) {
          lines.push({
            text: line.text.trim(),
            bbox: {
              x: line.x,
              y: line.y,
              width: line.width,
              height: line.height
            }
          });
        }
      });
    }
    
    // If no lines extracted, create a default entry
    if (lines.length === 0 && cleanText) {
      lines.push({
        text: cleanText,
        bbox: { x: 0, y: 0, width: 1, height: 1 }
      });
    }
    
    return {
      success: true,
      text: cleanText,
      confidence: confidence,
      lines: lines
    };
  } catch (error) {
    throw new Error(`OCR recognition failed: ${error.message}`);
  }
}

/**
 * Terminate the singleton worker on plugin unload
 * Ensures proper resource cleanup
 */
export function terminateWorker() {
  if (ocrWorker) {
    try {
      ocrWorker.terminate();
      ocrWorker = null;
      console.log('[OCR Service] Worker terminated for resource cleanup');
    } catch (error) {
      console.warn('[OCR Service] Error terminating worker:', error.message);
    }
  }
}

/**
 * Check if a worker is currently initialized
 * @returns {boolean} - True if worker is initialized
 */
export function isWorkerInitialized() {
  return ocrWorker !== null;
}

export default { recognize, terminateWorker, isWorkerInitialized, initializeWorker };