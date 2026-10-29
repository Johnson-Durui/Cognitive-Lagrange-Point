/**
 * 共享 body scroll lock
 */

const LOCK_KEY = '__clp_body_scroll_lock__';

function getStore() {
  if (typeof window === 'undefined') return { count: 0, previousOverflow: '' };
  if (!window[LOCK_KEY]) {
    window[LOCK_KEY] = { count: 0, previousOverflow: '' };
  }
  return window[LOCK_KEY];
}

export function lockBodyScroll() {
  if (typeof document === 'undefined') return;
  const store = getStore();
  if (store.count === 0) {
    store.previousOverflow = document.body.style.overflow || '';
    document.body.style.overflow = 'hidden';
  }
  store.count += 1;
}

export function unlockBodyScroll() {
  if (typeof document === 'undefined') return;
  const store = getStore();
  store.count = Math.max(0, store.count - 1);
  if (store.count === 0) {
    document.body.style.overflow = store.previousOverflow || '';
    store.previousOverflow = '';
  }
}

export function getBodyScrollLockCount() {
  return getStore().count;
}
