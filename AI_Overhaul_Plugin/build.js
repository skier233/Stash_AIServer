#!/usr/bin/env node
// =============================================================================
// Build Script for AIOverhaul Plugin
// =============================================================================
// Compiles TypeScript and fixes CommonJS exports for browser compatibility

const fs = require('fs');
const { execSync } = require('child_process');

const files = [
  'src/utils/UniversalGraphQL.tsx',
  'src/utils/MutateGraphQL.tsx',
  'src/results/VisageImageResults.tsx', 
  'src/SettingsPage.tsx',
  'src/AIButton.tsx',
  'src/WebSocketManager.tsx'
];

console.log('🔨 Building AIOverhaul Plugin...\n');

// Compile each TypeScript file
for (const file of files) {
  try {
    console.log(`📝 Compiling ${file}...`);
    execSync(`npx tsc ${file} --target es2017 --module none --lib es2017,dom --outDir dist --declaration false --skipLibCheck true --noResolve`, {
      stdio: 'inherit'
    });
    
    // Fix browser compatibility issues
    const outputFile = file.replace('src/', 'dist/').replace('.tsx', '.js');
    if (fs.existsSync(outputFile)) {
      let content = fs.readFileSync(outputFile, 'utf8');
      
      // Remove CommonJS exports  
      content = content.replace('"use strict";\n', '');
      content = content.replace(/Object\.defineProperty\(exports, "__esModule", \{ value: true \}\);\n?/g, '');
      content = content.replace(/exports\.default = [^;]+;?\n?/g, '');
      
      // Write fixed content back
      fs.writeFileSync(outputFile, content);
      console.log(`✅ Fixed browser compatibility for ${outputFile}`);
    }
  } catch (error) {
    console.error(`❌ Error compiling ${file}:`, error.message);
  }
}

console.log('\n🎉 Build complete!');
console.log('\n📁 Generated files:');
try {
  const distFiles = fs.readdirSync('dist').filter(f => f.endsWith('.js'));
  distFiles.forEach(file => {
    const stats = fs.statSync(`dist/${file}`);
    console.log(`   dist/${file} (${Math.round(stats.size / 1024)}KB)`);
  });
} catch (e) {
  console.log('   Could not list dist files');
}