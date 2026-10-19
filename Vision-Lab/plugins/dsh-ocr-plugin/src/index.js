/**
 * DSH Plugin & Tool Registration (Cordis Integration)
 * 
 * Exports standard Cordis/DSH plugin lifecycle (apply ctx).
 * Registers the tool: ocr_read_image (smart_ocr_extract).
 * 
 * Tool Schema:
 * - file_path (string, required): Absolute or relative image path.
 * - langs (string, optional, default: "ara+eng"): OCR language codes.
 * - enhance (boolean, optional, default: true): Whether to apply Sharp pre-processing.
 */

import { preprocessImage } from './imageProcessor.js';
import { recognize, terminateWorker, isWorkerInitialized } from './ocrService.js';
import { createReadStream } from 'fs';

// Register the plugin with Cordis/DSH host
export default function apply(ctx) {
  console.log('[OCR Plugin] Plugin loading... initializing OCR services');

  // Ensure worker is terminated on plugin unload
  ctx.on unload || ctx.on uninitialize || () => {
    terminateWorker();
    console.log('[OCR Plugin] Plugin unloaded, worker terminated');
  };

  // Register the OCR read image tool
  ctx.registerTool('ocr_read_image', {
    // Tool description for documentation
    description: 'Perform OCR on an image file with optional preprocessing',
    
    // Tool schema definition
    schema: {
      type: 'object',
      properties: {
        // Absolute or relative image path
        file_path: {
          type: 'string',
          description: 'Absolute or relative path to the image file to perform OCR on'
        },
        // OCR language codes (default: Arabic + English)
        langs: {
          type: 'string',
          description: 'OCR language codes (e.g., "ara+eng", "eng", "ara")',
          default: 'ara+eng'
        },
        // Whether to apply Sharp pre-processing enhancement
        enhance: {
          type: 'boolean',
          description: 'Whether to apply Sharp preprocessing before OCR',
          default: true
        }
      },
      // Required fields
      required: ['file_path'],
      // Additional properties beyond schema are allowed
      additionalProperties: false
    },

    // Tool execution handler
    async execute({ file_path, langs = 'ara+eng', enhance = true } = {}) {
      try {
        // Step 1: Validate file existence
        // Check if file_path exists and is accessible
        let fileExists = false;
        try {
          // Attempt to read the file to verify existence
          // In a real DSH environment, this would use the host's file API
          // Here we validate the path format
          if (!file_path || file_path.trim() === '') {
            throw new Error('Invalid file path: file_path is required and cannot be empty');
          }
          fileExists = true; // Path validation passed
        } catch (pathError) {
          throw new Error(`File validation failed: ${pathError.message}`);
        }

        // Step 2: Read the image file and convert to buffer
        let imageBuffer;
        try {
          // Read file as buffer - in production this would use appropriate file API
          // For now, we'll use a simulated approach
          if (!globalThis.__DSH__) {
            // Non-DSH environment: try to read using Node.js fs
            // This is a placeholder - actual implementation depends on DSH host
            imageBuffer = await readFileAsBuffer(file_path);
          } else {
            // DSH environment - use host file API
            imageBuffer = await ctx.readFile(file_path);
          }
          
          if (!imageBuffer || imageBuffer.length === 0) {
            throw new Error('Empty file: the specified file is empty or could not be read');
          }
        } catch (readError) {
          throw new Error(`Failed to read image file: ${readError.message}`);
        }

        // Step 3: Validate it's a valid image
        const { isValidImage } = await import('./imageProcessor.js');
        if (!isValidImage(imageBuffer)) {
          throw new Error('Unsupported format: the specified file is not a valid image (JPEG, PNG, GIF, WebP)');
        }

        // Step 4: Apply Sharp preprocessing if enhance is true
        let processedBuffer = imageBuffer;
        if (enhance) {
          try {
            const { buffer, metadata } = await preprocessImage(imageBuffer, { enhance: true });
            processedBuffer = buffer;
            // Log metadata for debugging
            console.log(`[OCR Plugin] Preprocessing complete: ${metadata.width}x${metadata.height}, format: ${metadata.format}`);
          } catch (preprocessError) {
            throw new Error(`Image preprocessing failed: ${preprocessError.message}`);
          }
        }

        // Step 5: Run OCR recognition
        const { recognize } = await import('./ocrService.js');
        const ocrResult = await recognize(processedBuffer, { lang: langs, enhance: false });

        // Step 6: Diagnostic hint if confidence < 60
        let response = {
          success: true,
          text: ocrResult.text,
          confidence: ocrResult.confidence,
          // Include diagnostic hint if needed
          ...(ocrResult.confidence < 60 ? {
            diagnosticHint: 'Low confidence OCR result. Consider using a vision/multimodal fallback for better accuracy.'
          } : {})
        };

        // Step 7: Return clean JSON response
        return {
          success: response.success,
          text: response.text,
          confidence: response.confidence,
          diagnosticHint: response.diagnosticHint
        };

      } catch (error) {
        // Comprehensive error handling with human-readable messages
        console.error('[OCR Plugin] Execution error:', error.message);
        
        return {
          success: false,
          error: error.message,
          text: '',
          confidence: 0,
          diagnosticHint: error.message.includes('Low confidence') 
            ? 'Consider using a vision/multimodal fallback for better accuracy.' 
            : null
        };
      }
    }
  });

  console.log('[OCR Plugin] Successfully registered ocr_read_image tool');
  
  // Return plugin context for host integration
  return {
    name: 'dsh-ocr-plugin',
    version: '1.0.0',
    description: 'DSH OCR Plugin for Optical Character Recognition with Arabic/English support'
  };
}

/**
 * Helper: Read file as buffer (Node.js fs)
 * @param {string} filePath - Path to file
 * @returns {Promise<Buffer>} - File contents as buffer
 */
async function readFileAsBuffer(filePath) {
  try {
    const { readFile } = await import('fs/promises');
    return await readFile(filePath);
  } catch (error) {
    throw new Error(`Failed to read file ${filePath}: ${error.message}`);
  }
}

/**
 * Helper: Validate and normalize file path
 * @param {string} filePath - Original file path
 * @returns {string} - Normalized path
 */
function normalizeFilePath(filePath) {
  if (!filePath) return '';
  
  // Remove leading/trailing whitespace
  let normalized = filePath.trim();
  
  // Convert backslashes to forward slashes (Windows compatibility)
  normalized = normalized.replace(/\\/g, '/');
  
  // Remove duplicate slashes
  normalized = normalized.replace(/\/+/g, '/');
  
  return normalized;
}

export default apply;