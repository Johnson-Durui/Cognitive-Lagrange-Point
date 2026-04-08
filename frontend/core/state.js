/**
 * 认知拉格朗日点 · 全局状态
 */

export const state = {
  appState: 'title', // 'title' | 'home' | 'exploring' | 'detail' | 'detection' | 'force'
  time: 0,
  titleStartTime: 0,
  
  // Systems and Nodes
  systems: [],
  allNodes: [],
  
  // Interaction
  hoveredNode: null,
  selectedNode: null,
  mouseX: window.innerWidth / 2,
  mouseY: window.innerHeight / 2,
  isDragging: false,
  hasDragged: false,
  
  // Camera
  camera: {
    x: 0, y: 0, zoom: 0.65,
    targetX: 0, targetY: 0, targetZoom: 0.65,
    minZoom: 0.25, maxZoom: 2.5
  },
  
  // Engine B Session
  engineBSession: null,
  currentEngineBQuestion: '',
  engineBThinkingEntries: [],
  simThinkingEntries: [],
  engineBSeenPhases: new Set(),
  simSeenPhases: new Set(),

  // New Decision Protocol
  currentDecision: null,
  currentDecisionId: '',
  pendingDecisionAnswer: false,
  decisionEventSource: null,
  decisionEventRetryCount: 0,
  decisionEventRetryTimer: null,
  lastDecisionRenderSignature: '',
  decisionProgressRankById: {},
  decisionTiers: {},
  decisionHistory: [],
  cosmosOverlayNodes: [],
  selectedTier: 'deep',

  // Detection State
  detectionJob: null,
  detectionJobId: '',
  detectionEventSource: null,
  currentCLP: null,

  // UI Coordination
  decisionFlowView: null,

  // Detection/Loop State
  detectionLoopHandoffs: new Set(),
  useWebGL: false
};

export function normalizeSystemRecord(system, index) {
  const normalized = system && typeof system === 'object' ? { ...system } : {};
  const fallbackId = `system-${index + 1}`;
  const color = Array.isArray(normalized.color) && normalized.color.length >= 3
    ? normalized.color
    : [255, 255, 255];
  const position = normalized.position && Number.isFinite(normalized.position.x) && Number.isFinite(normalized.position.y)
    ? normalized.position
    : { x: 0, y: 0 };

  return {
    ...normalized,
    id: normalized.id || fallbackId,
    name: normalized.name || normalized.nameEn || `未命名系统 ${index + 1}`,
    nameEn: normalized.nameEn || normalized.name || `System ${index + 1}`,
    color,
    position,
    nodes: Array.isArray(normalized.nodes) ? normalized.nodes.filter(Boolean) : [],
    fault_line_connections: Array.isArray(normalized.fault_line_connections) ? normalized.fault_line_connections : [],
    tunnel_connections: Array.isArray(normalized.tunnel_connections) ? normalized.tunnel_connections : [],
  };
}
