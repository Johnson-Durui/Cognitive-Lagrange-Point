import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [pkg, index, moduleSource, template] = await Promise.all([
  readFile('package.json', 'utf8').then(JSON.parse),
  readFile('index.html', 'utf8'),
  readFile('frontend/modules/quantum-vibe-oracle.js', 'utf8'),
  readFile('frontend/components/QuantumUniverseView.html', 'utf8'),
]);

assert.ok(pkg.dependencies?.three, 'three dependency should be declared');
assert.ok(pkg.dependencies?.['@mediapipe/tasks-vision'], 'MediaPipe vision dependency should be declared');
assert.match(index, /openQuantumVibeOracle\(\)/, 'report page should expose the quantum oracle entry button');
assert.match(moduleSource, /import\('three'\)/, 'Three.js must be lazy-loaded');
assert.match(moduleSource, /import\('three\/webgpu'\)/, 'WebGPU renderer must be lazy-loaded');
assert.match(moduleSource, /import\('@mediapipe\/tasks-vision'\)/, 'MediaPipe must be lazy-loaded');
assert.match(moduleSource, /AudioContext|webkitAudioContext/, 'Web Audio API soundscape should be implemented');
assert.match(moduleSource, /ShaderMaterial/, 'luxury particle field should use ShaderMaterial');
assert.match(moduleSource, /indexedDB/i, 'quantum state must persist through IndexedDB');
assert.match(template, /Quantum Vibe Oracle/, 'quantum universe template should be present');
assert.match(template, /data-qvo-bio-enable/, 'bio resonance control should be present');
assert.match(template, /data-qvo-audio-toggle/, 'audio mute control should be present');
assert.match(template, /data-qvo-flight-toggle/, 'free flight control should be present');
assert.match(template, /data-qvo-save/, 'save quantum state control should be present');
assert.match(template, /data-qvo-story-orb/, 'particle story overlay should be present');

console.log('Quantum Vibe Oracle static checks passed.');
