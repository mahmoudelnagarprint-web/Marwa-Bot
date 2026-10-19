# dsh-ocr-plugin

DSH (Cordis-based) plugin for Optical Character Recognition (OCR) with Arabic and English support.

## Overview

This plugin provides OCR capabilities for the DSH (DeepSeek Harness) platform, enabling image text extraction using Tesseract.js with Sharp preprocessing for enhanced results.

## Features

- **Multi-language Support**: Default Arabic (`ara`) + English (`eng`) language packs
- **Image Preprocessing**: Automatic contrast enhancement, grayscale conversion, EXIF orientation, and sharpening
- **Singleton Worker Pattern**: Tesseract worker initialized once and reused for performance
- **Local tessdata Cache**: Language data stored locally at `./assets/tessdata` to eliminate network downloads
- **Confidence Scoring**: Returns confidence percentage (0-100) for OCR results
- **Line-level Localization**: Returns bounding boxes for each detected text line

## Installation

```bash
# Navigate to your DSH plugins directory
cd your-dsh-project/plugins

# Install the plugin
npm install path/to/dsh-ocr-plugin

# Or link locally for development
npm link /path/to/dsh-ocr-plugin
```

## Prerequisites

- Node.js 18+
- DSH host environment with Cordis integration
- Tesseract language data will be automatically cached to `./assets/tessdata`

## Configuration

### Basic Usage (via DSH Tool Interface)

```json
{
  "tool": "ocr_read_image",
  "parameters": {
    "file_path": "path/to/image.jpg",
    "langs": "ara+eng",
    "enhance": true
  }
}
```

### Programmatic Usage

```javascript
import apply from 'dsh-ocr-plugin';

// Initialize plugin in DSH host
const plugin = apply(dshContext);

// Execute OCR on an image
const result = await plugin.tools.ocr_read_image.execute({
  file_path: 'images/document.jpg',
  langs: 'ara+eng',
  enhance: true
});

console.log('OCR Result:', result);
```

## Project Structure

```
dsh-ocr-plugin/
├── assets/
│   └── tessdata/           # Cache directory for offline language data
├── src/
│   ├── imageProcessor.js   # Image enhancement pipeline via Sharp
│   ├── ocrService.js       # Tesseract Worker lifecycle & execution
│   └── index.js            # DSH / Cordis tool registration & entry point
├── cordis.patch.yml        # Host manifest integration for DSH
├── package.json            # Node.js manifest with ESM & dependencies
└── README.md               # Documentation and usage guide
```

## Development

### Running Tests

```bash
npm test
```

### Building

The plugin uses ES Modules natively. No build step is required - just ensure your DSH host supports ESM.

### Customizing Language Packs

To add or change languages, modify the `langs` parameter when calling the tool:

- `"ara+eng"`: Arabic + English (default)
- `"eng"`: English only
- `"ara"`: Arabic only
- `"fra+eng"`: French + English
- etc.

### Tweaking Preprocessing

The Sharp preprocessing can be disabled by setting `enhance: false` when the image is already optimized or when you want to pass the original buffer directly to Tesseract.

## License

MIT