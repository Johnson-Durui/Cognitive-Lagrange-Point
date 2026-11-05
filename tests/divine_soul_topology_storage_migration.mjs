import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile('frontend/modules/divine-soul-topology/storage.js', 'utf8');

assert.match(source, /clp_divine_soul_topology/, 'new Divine DB name should be declared');
assert.match(source, /soulStates/, 'new Divine store name should be declared');
assert.match(source, /clp_quantum_vibe_oracle/, 'legacy Quantum DB should be referenced for migration');
assert.match(source, /quantumStates/, 'legacy Quantum store should be referenced for migration');
assert.match(source, /divine-soul-topology:/, 'legacy Divine key prefix should be preserved for migration');
assert.match(source, /MIGRATION_MARKER_KEY/, 'migration marker should exist');
assert.match(source, /ensureDivineStorageMigration/, 'migration entry point should exist');
assert.match(source, /startsWith\(DIVINE_KEY_PREFIX\)/, 'migration should filter legacy records by Divine prefix');

console.log('Divine Soul Topology storage migration static smoke passed.');
