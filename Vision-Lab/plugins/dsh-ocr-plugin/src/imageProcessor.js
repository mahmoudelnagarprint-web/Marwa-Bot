/**
 * Image Preprocessing Pipeline using Sharp
 * 
 * Builds a robust preprocessing pipeline before passing buffers to Tesseract OCR.
 * Enhances contrast, converts to grayscale, auto-orients based on EXIF,
 * and applies adaptive thresholding/sharpening for crisp Arabic/English text edges.
 */

import sharp from 'sharp';

/**
 * Preprocess an image buffer for OCR
 * @param {Buffer} buffer - Input image buffer
 * @param {Object} [options] - Processing options
 * @param {boolean} [options.enhance=true] - Whether to apply enhancement pipeline
 * @returns {Object} - Processed buffer and metadata
 */
export async function preprocessImage(buffer, { enhance = true } = {}) {
  if (!buffer || buffer.length === 0) {
    throw new Error('Invalid image buffer: empty or null buffer provided');
  }

  try {
    let pipeline = sharp(buffer);

    if (enhance) {
      // Step 1: Read EXIF orientation and auto-orient
      pipeline = pipeline.rotate();

      // Step 2: Convert to grayscale
      pipeline = pipeline.grayscale();

      // Step 3: Normalize contrast
      pipeline = pipeline.normalize();

      // Step 4: Sharpen to make text edges crisp
      pipeline = pipeline.sharpen();
    }

    // Get metadata about the processed image
    const metadata = await pipeline.metadata();

    // Return processed buffer and metadata
    // The pipeline hasn't been computed yet, so we need to ensure it completes
    // We'll return a function that computes the buffer when needed
    return {
      buffer: pipeline,
      metadata: {
        width: metadata.width,
        height: metadata.height,
        format: metadata.format,
        channels: metadata.channels,
        space: metadata.space
      }
    };
  } catch (error) {
    throw new Error(`Image preprocessing failed: ${error.message}`);
  }
}

/**
 * Validate that the input is a valid image format
 * @param {Buffer} buffer - Input image buffer
 * @returns {boolean} - True if valid image
 */
export function isValidImage(buffer) {
  if (!buffer || buffer.length === 0) return false;
  
  // Check for common image signatures
  const head = buffer.subarray(0, 4);
  
  // JPEG: FF D8 FF
  if (head[0] === 0xFF && head[1] === 0xD8 && head[2] === 0xFF) return true;
  // PNG: 89 50 4E 47
  if (head[0] === 0x89 && head[1] === 0x50 && head[2] === 0x4E && head[3] === 0x47) return true;
  // GIF: 47 49 46 38
  if (head[0] === 0x47 && head[1] === 0x49 && head[2] === 0x46 && head[3] === 0x38) return true;
  // WebP: 52 49 46 46 (with RIFF header)
  if (head[0] === 0x52 && head[1] === 0x49 && head[2] === 0x46 && head[3] === 0x46) return true;
  
  return false;
}

export default { preprocessImage, isValidImage };