/**
 * 认知拉格朗日点 · 交互系统 (Interaction)
 */

import { state } from './state.js';
import { screenToWorld } from './renderer.js';
import { openDetail } from '../modules/ui-handlers.js';

let canvas;
let isDragging = false;
let hasDragged = false;
let dragStartX, dragStartY;
let dragCamStartX, dragCamStartY;

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function getTooltip() {
  return document.getElementById('tooltip');
}

function hideTooltip() {
  const tooltip = getTooltip();
  if (!tooltip) return;
  tooltip.classList.remove('visible');
}

function updateTooltip(node, clientX, clientY) {
  const tooltip = getTooltip();
  if (!tooltip || !node) {
    hideTooltip();
    return;
  }

  const title = node.data?.name || node.data?.question || node.system?.name || '未命名节点';
  const subtitle = node.data?.tooltipSubtitle || node.data?.subtitle || node.system?.nameEn || '';
  const titleEl = tooltip.querySelector('.tooltip-name');
  const subtitleEl = tooltip.querySelector('.tooltip-subtitle');
  if (titleEl) titleEl.textContent = title;
  if (subtitleEl) subtitleEl.textContent = subtitle;

  const offsetX = 16;
  const offsetY = 18;
  const maxX = window.innerWidth - tooltip.offsetWidth - 12;
  const maxY = window.innerHeight - tooltip.offsetHeight - 12;
  tooltip.style.left = `${Math.min(clientX + offsetX, maxX)}px`;
  tooltip.style.top = `${Math.min(clientY + offsetY, maxY)}px`;
  tooltip.classList.add('visible');
}

function getInteractiveNodes() {
  const baseNodes = Array.isArray(state.allNodes) ? state.allNodes : [];
  const overlayNodes = Array.isArray(state.cosmosOverlayNodes) ? state.cosmosOverlayNodes : [];
  return [...baseNodes, ...overlayNodes];
}

function getNodePriority(node) {
  let priority = 0;
  if (node?.isCurrent) priority += 40;
  if (node?.isOverlay) priority += 22;
  if (node?.hovered) priority += 12;
  if (node?.data?.detailType === 'choice-anchor') priority += 10;
  if (node?.data?.detailType === 'timeline-milestone') priority += 8;
  if (node?.data?.status === 'running') priority += 4;
  return priority;
}

function getHitRadius(node) {
  const explicit = Number.isFinite(node?.hitRadius) ? Number(node.hitRadius) : 18;
  const visual = Number.isFinite(node?.visualRadius) ? Number(node.visualRadius) * 2.8 : 0;
  const base = Math.max(16, explicit, visual);
  const zoom = Number(state.camera?.zoom) || 1;
  const zoomBoost = clamp(1.18 - zoom * 0.22, 0.9, 1.28);
  return base * zoomBoost;
}

export function initInteraction(canvasElement) {
  canvas = canvasElement;
  bindMouseEvents();
  bindTouchEvents();
}

function clearHoveredNode() {
  if (state.hoveredNode) {
    state.hoveredNode.hovered = false;
    state.hoveredNode = null;
  }
  hideTooltip();
  if (canvas) {
    canvas.style.cursor = 'default';
  }
}

export function findNodeAt(clientX, clientY) {
  const candidates = getInteractiveNodes();
  let bestNode = null;
  let bestScore = -Infinity;

  for (let index = candidates.length - 1; index >= 0; index -= 1) {
    const node = candidates[index];
    if (!node || !Number.isFinite(node.sx) || !Number.isFinite(node.sy)) continue;
    const dx = clientX - node.sx;
    const dy = clientY - node.sy;
    const distance = Math.hypot(dx, dy);
    const hitRadius = getHitRadius(node);
    if (distance <= hitRadius) {
      const distanceScore = (1 - (distance / Math.max(hitRadius, 1))) * 1000;
      const score = distanceScore + getNodePriority(node) * 100 + hitRadius;
      if (score > bestScore) {
        bestNode = node;
        bestScore = score;
      }
    }
  }

  return bestNode;
}

export function getInteractiveNodeSnapshot() {
  return getInteractiveNodes()
    .filter((node) => node && Number.isFinite(node.sx) && Number.isFinite(node.sy))
    .map((node) => ({
      id: node.id || '',
      x: Math.round(node.sx),
      y: Math.round(node.sy),
      hitRadius: Math.round(getHitRadius(node)),
      detailType: node.data?.detailType || '',
      title: node.data?.name || node.data?.question || node.system?.name || '',
      decisionId: node.data?.decision_id || '',
      isCurrent: Boolean(node.isCurrent),
      isOverlay: Boolean(node.isOverlay),
      tier: node.data?.tier || '',
      status: node.data?.status || '',
    }));
}

export function hitTestInteractiveNode(clientX, clientY) {
  const node = findNodeAt(clientX, clientY);
  if (!node) {
    return null;
  }
  return {
    id: node.id || '',
    title: node.data?.name || node.data?.question || node.system?.name || '',
    detailType: node.data?.detailType || '',
    decisionId: node.data?.decision_id || '',
    x: Math.round(node.sx || 0),
    y: Math.round(node.sy || 0),
    hitRadius: Math.round(getHitRadius(node)),
  };
}

export function getCurrentInteractionDebug() {
  const hovered = state.hoveredNode;
  const selected = state.selectedNode;
  return {
    hovered: hovered && Number.isFinite(hovered.sx) && Number.isFinite(hovered.sy)
      ? hitTestInteractiveNode(hovered.sx, hovered.sy)
      : null,
    selected: selected && Number.isFinite(selected.sx) && Number.isFinite(selected.sy)
      ? hitTestInteractiveNode(selected.sx, selected.sy)
      : null,
    nodes: getInteractiveNodeSnapshot(),
  };
}

function updateHoveredNode(clientX, clientY) {
  const node = findNodeAt(clientX, clientY);
  if (node === state.hoveredNode) {
    if (canvas) {
      canvas.style.cursor = node ? 'pointer' : 'default';
    }
    updateTooltip(node, clientX, clientY);
    return node;
  }

  if (state.hoveredNode) {
    state.hoveredNode.hovered = false;
  }
  state.hoveredNode = node;
  if (node) {
    node.hovered = true;
  }
  if (canvas) {
    canvas.style.cursor = node ? 'pointer' : 'default';
  }
  updateTooltip(node, clientX, clientY);
  return node;
}

function bindMouseEvents() {
  canvas.addEventListener('mousedown', (e) => {
    if (state.appState === 'title') return;
    isDragging = true;
    hasDragged = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragCamStartX = state.camera.targetX;
    dragCamStartY = state.camera.targetY;
    document.body.classList.add('dragging');
  });

  window.addEventListener('mousemove', (e) => {
    state.mouseX = e.clientX;
    state.mouseY = e.clientY;
    if (isDragging) {
      const dx = (e.clientX - dragStartX) / state.camera.zoom;
      const dy = (e.clientY - dragStartY) / state.camera.zoom;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDragged = true;
      state.camera.targetX = dragCamStartX - dx;
      state.camera.targetY = dragCamStartY - dy;
      clearHoveredNode();
      return;
    }
    updateHoveredNode(e.clientX, e.clientY);
  });

  window.addEventListener('mouseup', (e) => {
    if (isDragging) {
      isDragging = false;
      document.body.classList.remove('dragging');
      if (!hasDragged) {
        const node = updateHoveredNode(e.clientX, e.clientY);
        if (node) {
          openDetail(node);
        }
      }
    }
  });

  canvas.addEventListener('mouseleave', () => {
    clearHoveredNode();
  });

  canvas.addEventListener('wheel', (e) => {
    if (state.appState === 'title') return;
    e.preventDefault();
    const zoomFactor = 1 - e.deltaY * 0.001;
    const worldBefore = screenToWorld(e.clientX, e.clientY);
    state.camera.targetZoom = Math.max(state.camera.minZoom, Math.min(state.camera.maxZoom, state.camera.targetZoom * zoomFactor));
    const worldAfter = screenToWorld(e.clientX, e.clientY);
    state.camera.targetX -= (worldAfter.x - worldBefore.x) * 0.3;
    state.camera.targetY -= (worldAfter.y - worldBefore.y) * 0.3;
  }, { passive: false });
}

function bindTouchEvents() {
  let lastTouchDist = 0;
  let tapX = 0;
  let tapY = 0;
  canvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      isDragging = true;
      hasDragged = false;
      const t = e.touches[0];
      dragStartX = t.clientX;
      dragStartY = t.clientY;
      tapX = t.clientX;
      tapY = t.clientY;
      dragCamStartX = state.camera.targetX;
      dragCamStartY = state.camera.targetY;
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      lastTouchDist = Math.sqrt(dx * dx + dy * dy);
    }
  }, { passive: true });

  canvas.addEventListener('touchmove', (e) => {
    if (e.touches.length === 1 && isDragging) {
      e.preventDefault();
      const t = e.touches[0];
      const dx = (t.clientX - dragStartX) / state.camera.zoom;
      const dy = (t.clientY - dragStartY) / state.camera.zoom;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDragged = true;
      state.camera.targetX = dragCamStartX - dx;
      state.camera.targetY = dragCamStartY - dy;
      clearHoveredNode();
    } else if (e.touches.length === 2) {
      e.preventDefault();
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (lastTouchDist > 0) {
        const scale = dist / lastTouchDist;
        state.camera.targetZoom = Math.max(state.camera.minZoom, Math.min(state.camera.maxZoom, state.camera.targetZoom * scale));
      }
      lastTouchDist = dist;
    }
  }, { passive: false });

  canvas.addEventListener('touchend', () => {
    if (isDragging && !hasDragged) {
      const node = updateHoveredNode(tapX, tapY);
      if (node) {
        openDetail(node);
      }
    }
    isDragging = false;
    lastTouchDist = 0;
  });
}
