/**
 * 神魂拓扑存储层
 */

import { getAllRecords, getRecord, openIndexedDb, putRecord } from '../art-experience/storage-base.js';

export const DIVINE_DB_NAME = 'clp_divine_soul_topology';
export const DIVINE_DB_VERSION = 1;
export const DIVINE_STORE_NAME = 'soulStates';
export const DIVINE_KEY_PREFIX = 'divine-soul-topology:';

const LEGACY_DB_NAME = 'clp_quantum_vibe_oracle';
const LEGACY_DB_VERSION = 1;
const LEGACY_STORE_NAME = 'quantumStates';
const MIGRATION_MARKER_KEY = 'clp_divine_soul_topology_migrated_v1';

function upgradeDivineDb(db) {
  if (!db.objectStoreNames.contains(DIVINE_STORE_NAME)) {
    db.createObjectStore(DIVINE_STORE_NAME, { keyPath: 'decisionId' });
  }
}

function upgradeLegacyDb(db) {
  if (!db.objectStoreNames.contains(LEGACY_STORE_NAME)) {
    db.createObjectStore(LEGACY_STORE_NAME, { keyPath: 'decisionId' });
  }
}

export function getDivineStorageId(decisionId) {
  return `${DIVINE_KEY_PREFIX}${decisionId}`;
}

export async function ensureDivineStorageMigration() {
  try {
    if (window.localStorage?.getItem(MIGRATION_MARKER_KEY) === 'done') return;
  } catch (error) {
    console.warn('Divine migration marker read failed:', error);
  }

  const legacyRecords = await getAllRecords(
    LEGACY_DB_NAME,
    LEGACY_DB_VERSION,
    LEGACY_STORE_NAME,
    upgradeLegacyDb,
  );
  const divineRecords = legacyRecords.filter((item) => String(item?.decisionId || '').startsWith(DIVINE_KEY_PREFIX));
  if (divineRecords.length) {
    const db = await openIndexedDb(DIVINE_DB_NAME, DIVINE_DB_VERSION, upgradeDivineDb);
    if (db) {
      await Promise.all(divineRecords.map((item) => putRecord(
        DIVINE_DB_NAME,
        DIVINE_DB_VERSION,
        DIVINE_STORE_NAME,
        { ...item, migratedFromLegacyAt: new Date().toISOString() },
        upgradeDivineDb,
      )));
    }
  }

  try {
    window.localStorage?.setItem(MIGRATION_MARKER_KEY, 'done');
  } catch (error) {
    console.warn('Divine migration marker write failed:', error);
  }
}

export async function loadPersistedSoulState(decisionId) {
  await ensureDivineStorageMigration();
  return getRecord(
    DIVINE_DB_NAME,
    DIVINE_DB_VERSION,
    DIVINE_STORE_NAME,
    getDivineStorageId(decisionId),
    upgradeDivineDb,
  );
}

export async function savePersistedSoulState(snapshot) {
  return putRecord(
    DIVINE_DB_NAME,
    DIVINE_DB_VERSION,
    DIVINE_STORE_NAME,
    snapshot,
    upgradeDivineDb,
  );
}
