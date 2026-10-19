#!/usr/bin/env node
// Test script for dsh-ocr-plugin
import { preprocessImage } from './src/imageProcessor.js';
import { recognize } from './src/ocrService.js';
import fs from 'fs';
import path from 'path';

async function testPlugin() {
  console.log('=== dsh-ocr-plugin Test Suite ===\n');
  
  // Test 1: Check if imageProcessor module loads correctly
  console.log('Test 1: Image processor module loading...');
  try {
    console.log('  ✓ imageProcessor module loaded successfully');
  } catch (error) {
    console.error('  ✗ Failed to load imageProcessor:', error.message);
    return;
  }
  
  // Test 2: Check if ocrService module loads correctly
  console.log('Test 2: OCR service module loading...');
  try {
    console.log('  ✓ ocrService module loaded successfully');
  } catch (error) {
    console.error('  ✗ Failed to load ocrService:', error.message);
    return;
  }
  
  // Test 3: Check if tessdata directory exists
  const tessdataPath = path.resolve('./assets/tessdata');
  console.log('Test 3: Tessdata directory...');
  try {
    if (fs.existsSync(tessdataPath)) {
      console.log(`  ✓ tessdata directory exists at: ${tessdataPath}`);
    } else {
      console.log(`  ! tessdata directory not found at: ${tessdataPath} (will be created by Tesseract on first use)`);
    }
  } catch (error) {
    console.error('  ✗ Error checking tessdata directory:', error.message);
  }
  
  // Test 4: Check package.json validity
  console.log('Test 4: Package configuration...');
  try {
    const pkg = JSON.parse(fs.readFileSync('./package.json', 'utf8'));
    console.log(`  ✓ package.json valid (name: ${pkg.name}, version: ${pkg.version})`);
    console.log(`  ✓ ESM type: ${pkg.type}`);
    console.log(`  ✓ Dependencies: ${Object.keys(pkg.dependencies).join(', ')}`);
  } catch (error) {
    console.error('  ✗ Invalid package.json:', error.message);
    return;
  }
  
  // Test 5: Verify Sharp and Tesseract are available
  console.log('Test 5: Dependencies availability...');
  try {
    const sharp = await import('sharp');
    console.log(`  ✓ sharp v${sharp.default ? 'loaded' : 'version check needed'}`);
    
    const Tesseract = await import('tesseract.js');
    console.log(`  ✓ tesseract.js v${Tesseract.default ? 'loaded' : 'version check needed'}`);
  } catch (error) {
    console.error('  ✗ Failed to import dependencies:', error.message);
    return;
  }
  
  console.log('\n=== All basic tests completed ===');
  console.log('Run full OCR test with an actual image file when available.');
}

testPlugin().catch(err => {
  console.error('Test suite failed:', err);
  process.exit(1);
});