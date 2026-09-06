/**
 * IndexedDB 共享底层封装
 */

export function openIndexedDb(dbName, version, upgrade) {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      resolve(null);
      return;
    }
    const request = window.indexedDB.open(dbName, version);
    request.onupgradeneeded = () => {
      upgrade?.(request.result, request.transaction);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function transact(db, storeName, mode, work) {
  return new Promise((resolve, reject) => {
    if (!db) {
      resolve(null);
      return;
    }
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    const request = work(store);
    tx.oncomplete = () => resolve(request?.result ?? null);
    tx.onerror = () => reject(tx.error || request?.error);
    tx.onabort = () => reject(tx.error || request?.error);
  });
}

export async function getRecord(dbName, version, storeName, key, upgrade) {
  const db = await openIndexedDb(dbName, version, upgrade);
  if (!db) return null;
  return new Promise((resolve) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).get(key);
    request.onsuccess = () => resolve(request.result || null);
    request.onerror = () => resolve(null);
  });
}

export async function putRecord(dbName, version, storeName, value, upgrade) {
  const db = await openIndexedDb(dbName, version, upgrade);
  if (!db) return;
  await transact(db, storeName, 'readwrite', (store) => store.put(value));
}

export async function getAllRecords(dbName, version, storeName, upgrade) {
  const db = await openIndexedDb(dbName, version, upgrade);
  if (!db) return [];
  return new Promise((resolve) => {
    const tx = db.transaction(storeName, 'readonly');
    const request = tx.objectStore(storeName).getAll();
    request.onsuccess = () => resolve(Array.isArray(request.result) ? request.result : []);
    request.onerror = () => resolve([]);
  });
}
