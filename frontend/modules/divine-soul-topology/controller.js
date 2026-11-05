/**
 * 神魂拓扑控制器
 */

import { showToast } from '../utils.js';
import { detectArtExperienceCapability } from '../art-experience/capability.js';
import { easeOutCubic, getDeviceProfile, safeNumber, wait } from '../art-experience/common.js';
import { extractProbabilities, getCurrentDecisionData, getDecisionId } from '../art-experience/decision-data.js';
import { lockBodyScroll, unlockBodyScroll } from '../art-experience/overlay-lock.js';
import { buildSoulBlueprint } from './blueprint.js';
import { exportGlb, exportLoopVideo, exportStill } from './export.js';
import { clearVoiceInputs, handlePhotoInput, stopVoiceCapture, toggleVoiceCapture } from './media.js';
import { updateSceneFrame, seedGrowthAnimation } from './render/animation.js';
import { createBackgroundStars, createSoulSculpture } from './render/sculpture.js';
import { loadDivineThreeStack } from './render/three-stack.js';
import { ensureDivineStorageMigration, getDivineStorageId, loadPersistedSoulState, savePersistedSoulState } from './storage.js';
import { buildTemplate } from './ui/template.js';
import { ensureStyles } from './ui/styles.js';
import {
  applyCapabilityState,
  renderContextHighlights,
  renderCuratorialNotes,
  renderPhotoGrid,
  renderStats,
  renderVoiceTranscript,
  syncFreeFlightUi,
  updateFooter,
  updateRendererCopy,
  updateRitualStage,
  updateSaveCopy,
} from './ui/panels.js';

export class DivineSoulTopologyController {
  constructor(data, persistedState = null) {
    this.data = data;
    this.decisionId = getDecisionId(data, 'soul-local');
    this.storageId = getDivineStorageId(this.decisionId);
    this.persistedState = persistedState || {};
    const sharedDevice = getDeviceProfile();
    this.device = {
      ...sharedDevice,
      particleBudget: sharedDevice.lowPower ? 12000 : 22000,
    };
    const detectedCapability = detectArtExperienceCapability();
    const capabilityOverride = typeof window !== 'undefined' ? window.__CLP_CAPABILITY_OVERRIDE__ : null;
    this.capability = capabilityOverride && typeof capabilityOverride === 'object'
      ? { ...detectedCapability, ...capabilityOverride }
      : detectedCapability;
    this.root = null;
    this.scene = null;
    this.camera = null;
    this.renderer = null;
    this.composer = null;
    this.renderPass = null;
    this.bloomPass = null;
    this.controls = null;
    this.THREE = null;
    this.ParametricGeometry = null;
    this.GLTFExporter = null;
    this.raf = 0;
    this.startedAt = performance.now();
    this.sceneTimeOffset = safeNumber(this.persistedState.topology?.evolutionClock, 0);
    this.storyText = String(this.persistedState.storyText || '');
    this.voiceTranscript = String(this.persistedState.voice?.transcript || '');
    this.voiceRecordings = Array.isArray(this.persistedState.voice?.recordings) ? this.persistedState.voice.recordings : [];
    this.photos = Array.isArray(this.persistedState.photos) ? this.persistedState.photos : [];
    this.filterMode = this.persistedState.filterMode || 'essence';
    this.blueprint = this.persistedState.topology?.blueprint || null;
    this.generationCount = safeNumber(this.persistedState.generationCount, this.blueprint ? 1 : 0);
    this.lastSavedAt = this.persistedState.updatedAt || '';
    this.freeFlightEnabled = Boolean(this.persistedState.freeFlightEnabled);
    this.cameraRestore = this.persistedState.camera || null;
    this.voiceRecorder = null;
    this.voiceChunks = [];
    this.voiceStream = null;
    this.voiceRecognition = null;
    this.voiceAudioContext = null;
    this.voiceAnalyser = null;
    this.voiceData = null;
    this.voiceFrame = 0;
    this.voiceStartedAt = 0;
    this.voiceMeterLevel = 0;
    this.voiceAccumulatedEnergy = 0;
    this.voiceSamples = 0;
    this.voiceActive = false;
    this.keyState = {};
    this.freeFlightLook = { yaw: 0, pitch: 0 };
    this.freeFlightPointer = { active: false, x: 0, y: 0 };
    this.lastOrbitTarget = null;
    this.saveTimer = 0;
    this.videoCapture = null;
    this.isExporting = false;
    this.sculptureGroup = null;
    this.backgroundStars = null;
    this.growthAnimation = null;
    this.filterProfiles = {
      essence: { label: '灵魂本质', lightA: 2.8, lightB: 1.7, lightC: 1.1, shellOpacity: 0.32, coreBoost: 1, particleFlow: 0.5, autoRotate: 0.34, fog: 0.028, bloomStrength: 0.92, bloomRadius: 0.72, bloomThreshold: 0.1 },
      destiny: { label: '命运拓扑', lightA: 2.1, lightB: 1.4, lightC: 1.9, shellOpacity: 0.42, coreBoost: 0.88, particleFlow: 0.86, autoRotate: 0.24, fog: 0.024, bloomStrength: 1.12, bloomRadius: 0.82, bloomThreshold: 0.08 },
      existential: { label: '存在主义模式', lightA: 1.4, lightB: 2.1, lightC: 2.3, shellOpacity: 0.2, coreBoost: 0.74, particleFlow: 1.18, autoRotate: 0.16, fog: 0.036, bloomStrength: 1.36, bloomRadius: 0.94, bloomThreshold: 0.04 },
    };
    this.onResize = this.onResize.bind(this);
    this.onKeyDown = this.onKeyDown.bind(this);
    this.onKeyUp = this.onKeyUp.bind(this);
    this.onCanvasPointerDown = this.onCanvasPointerDown.bind(this);
    this.onCanvasPointerMove = this.onCanvasPointerMove.bind(this);
    this.onCanvasPointerUp = this.onCanvasPointerUp.bind(this);
  }

  getSceneTime() {
    return this.sceneTimeOffset + ((performance.now() - this.startedAt) / 1000);
  }

  getFilterProfile(mode = this.filterMode) {
    return this.filterProfiles[mode] || this.filterProfiles.essence;
  }

  getStoryInputProfile() {
    return {
      storyText: this.storyText,
      voiceTranscript: this.voiceTranscript,
      voiceRecordings: this.voiceRecordings,
      photos: this.photos,
    };
  }

  renderContextHighlights() { renderContextHighlights(this); }
  renderCuratorialNotes() { renderCuratorialNotes(this); }
  renderVoiceTranscript() { renderVoiceTranscript(this); }
  renderPhotoGrid() { renderPhotoGrid(this); }
  renderStats() { renderStats(this); }
  updateSaveCopy(copy) { updateSaveCopy(this, copy); }
  updateRendererCopy(copy) { updateRendererCopy(this, copy); }
  updateFooter(copy) { updateFooter(this, copy); }
  updateRitualStage(stage) { updateRitualStage(this, stage); }
  syncFreeFlightUi() { syncFreeFlightUi(this); }
  updateSceneFrame(time) { updateSceneFrame(this, time); }

  async mount() {
    console.debug('[DST] mount:start');
    ensureStyles();
    await ensureDivineStorageMigration();
    this.root = document.createElement('div');
    this.root.className = 'dst-root';
    this.root.innerHTML = buildTemplate();
    document.body.appendChild(this.root);
    lockBodyScroll();

    this.root.querySelector('[data-dst-question]').textContent = this.data.question || '当前决策';
    this.root.querySelector('[data-dst-story]').value = this.storyText;
    this.renderContextHighlights();
    this.renderCuratorialNotes();
    this.renderVoiceTranscript();
    this.renderPhotoGrid();
    this.renderStats();
    this.updateSaveCopy(this.lastSavedAt ? `已恢复 ${new Date(this.lastSavedAt).toLocaleString('zh-CN')}` : '等待生成');

    this.bindUi();
    await this.setupThree();
    this.applyFilterMode(this.filterMode, { immediate: true });
    applyCapabilityState(this);

    if (this.blueprint) {
      this.rebuildSculpture(this.blueprint, { persist: false, announce: false });
      this.root.querySelector('[data-dst-empty-state]').hidden = true;
      this.updateFooter('已恢复上次神魂拓扑，雕塑正在继续演化。');
    }

    this.saveTimer = window.setInterval(() => {
      this.saveState({ heartbeatAt: new Date().toISOString() });
    }, 10000);
    await this.saveState({
      openedAt: new Date().toISOString(),
      openCount: safeNumber(this.persistedState.openCount, 0) + 1,
    });
    this.animate();
    console.debug('[DST] mount:done');
  }

  bindUi() {
    this.root.querySelector('[data-dst-close]')?.addEventListener('click', () => this.close());
    this.root.querySelector('[data-dst-open-quantum]')?.addEventListener('click', () => this.switchToQuantumMode());
    this.root.querySelector('[data-dst-current]')?.addEventListener('click', () => showToast('当前已处于神魂拓扑模式。', 'info', 1400));
    this.root.querySelector('[data-dst-story]')?.addEventListener('input', (event) => {
      this.storyText = String(event.currentTarget.value || '');
      this.renderCuratorialNotes();
      this.renderStats();
    });
    this.root.querySelector('[data-dst-photo-trigger]')?.addEventListener('click', () => {
      this.root.querySelector('[data-dst-photo-input]')?.click();
    });
    this.root.querySelector('[data-dst-photo-input]')?.addEventListener('change', (event) => handlePhotoInput(this, event));
    this.root.querySelector('[data-dst-voice-toggle]')?.addEventListener('click', () => toggleVoiceCapture(this));
    this.root.querySelector('[data-dst-voice-clear]')?.addEventListener('click', () => clearVoiceInputs(this));
    this.root.querySelector('[data-dst-generate]')?.addEventListener('click', () => this.generateTopology());
    this.root.querySelectorAll('[data-dst-filter]').forEach((button) => {
      button.addEventListener('click', () => this.applyFilterMode(button.dataset.dstFilter || 'essence'));
    });
    this.root.querySelector('[data-dst-flight-toggle]')?.addEventListener('click', () => this.toggleFreeFlight());
    this.root.querySelector('[data-dst-frame]')?.addEventListener('click', () => this.frameSculpture(false));
    this.root.querySelectorAll('[data-dst-export]').forEach((button) => {
      button.addEventListener('click', () => this.handleExport(button.dataset.dstExport || '4k'));
    });
    const canvas = this.root.querySelector('[data-dst-canvas]');
    canvas?.addEventListener('pointerdown', this.onCanvasPointerDown);
    canvas?.addEventListener('pointermove', this.onCanvasPointerMove);
    canvas?.addEventListener('pointerup', this.onCanvasPointerUp);
    canvas?.addEventListener('pointercancel', this.onCanvasPointerUp);
    canvas?.addEventListener('pointerleave', this.onCanvasPointerUp);
    window.addEventListener('resize', this.onResize, { passive: true });
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
  }

  async setupThree() {
    console.debug('[DST] three:start');
    const canvas = this.root.querySelector('[data-dst-canvas]');
    const {
      THREE,
      WebGPURenderer,
      OrbitControls,
      GLTFExporter,
      ParametricGeometry,
      EffectComposer,
      RenderPass,
      UnrealBloomPass,
    } = await loadDivineThreeStack();
    this.THREE = THREE;
    this.ParametricGeometry = ParametricGeometry;
    this.GLTFExporter = GLTFExporter;
    this.scene = new THREE.Scene();
    this.scene.fog = new THREE.FogExp2(0x050506, this.getFilterProfile().fog);
    this.camera = new THREE.PerspectiveCamera(48, window.innerWidth / window.innerHeight, 0.1, 180);
    this.camera.position.set(0, 3.4, 8.6);

    try {
      if (WebGPURenderer && navigator.gpu) {
        this.renderer = new WebGPURenderer({ canvas, antialias: true, alpha: true });
        await this.renderer.init?.();
        this.rendererType = 'WebGPU';
      } else {
        throw new Error('WebGPU unavailable');
      }
    } catch (error) {
      console.warn('Divine Soul Topology fallback to WebGL.', error);
      this.renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance',
      });
      this.rendererType = 'WebGL';
    }

    this.renderer.setPixelRatio(this.device.pixelRatio);
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.renderer.setClearColor(0x020202, 1);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.06;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    this.controls = new OrbitControls(this.camera, canvas);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.06;
    this.controls.enablePan = true;
    this.controls.autoRotate = true;
    this.controls.autoRotateSpeed = this.getFilterProfile().autoRotate;
    this.controls.minDistance = 2.8;
    this.controls.maxDistance = 18;

    this.addLights();
    this.backgroundStars = createBackgroundStars(
      THREE,
      this.blueprint?.palette || buildSoulBlueprint(this.data, this.getStoryInputProfile()).palette,
      this.device.lowPower
    );
    this.scene.add(this.backgroundStars);

    if (this.rendererType === 'WebGL' && this.renderer instanceof THREE.WebGLRenderer) {
      this.composer = new EffectComposer(this.renderer);
      this.renderPass = new RenderPass(this.scene, this.camera);
      this.bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 0.92, 0.72, 0.1);
      this.composer.addPass(this.renderPass);
      this.composer.addPass(this.bloomPass);
    }
    this.frameSculpture(true);
    this.syncFreeFlightUi();
    this.updateRendererCopy(`Renderer ${this.rendererType} · 粒子预算 ${this.device.particleBudget.toLocaleString()} · ${this.composer ? 'Bloom 已开启' : '高光辉光已就绪'}`);
    console.debug('[DST] three:done');
  }

  addLights() {
    const THREE = this.THREE;
    this.scene.add(new THREE.AmbientLight(0x3f4054, 0.64));
    this.lightKey = new THREE.PointLight(0xe8cd8c, 2.8, 40);
    this.lightKey.position.set(0, 6, 5);
    this.lightCyan = new THREE.PointLight(0x59e7dc, 1.7, 36);
    this.lightCyan.position.set(-6, 2, 4);
    this.lightViolet = new THREE.PointLight(0x8f66ff, 1.1, 42);
    this.lightViolet.position.set(6, -1, -3);
    this.scene.add(this.lightKey, this.lightCyan, this.lightViolet);
  }

  applyFilterMode(mode, { immediate = false } = {}) {
    this.filterMode = mode || 'essence';
    this.root?.querySelectorAll('[data-dst-filter]').forEach((button) => {
      button.classList.toggle('is-active', button.dataset.dstFilter === this.filterMode);
    });
    const profile = this.getFilterProfile();
    if (this.controls) this.controls.autoRotateSpeed = profile.autoRotate;
    if (this.lightKey) this.lightKey.intensity = profile.lightA;
    if (this.lightCyan) this.lightCyan.intensity = profile.lightB;
    if (this.lightViolet) this.lightViolet.intensity = profile.lightC;
    if (this.scene?.fog) this.scene.fog.density = profile.fog;
    if (this.bloomPass) {
      this.bloomPass.strength = profile.bloomStrength;
      this.bloomPass.radius = profile.bloomRadius;
      this.bloomPass.threshold = profile.bloomThreshold;
    }
    if (this.sculptureGroup) {
      this.sculptureGroup.traverse((child) => {
        if (child.userData.dstRole === 'topology-shell' && child.material) child.material.opacity = profile.shellOpacity;
        if (child.userData.dstRole === 'core' && child.material) child.material.emissiveIntensity = 0.42 * profile.coreBoost;
      });
    }
    if (!immediate) {
      this.updateFooter(`${profile.label} 已开启，雕塑正在重写光影关系。`);
      this.renderCuratorialNotes();
      awaitMaybe(this.saveState({ filterMode: this.filterMode }));
      this.renderStats();
    }
  }

  frameSculpture(instant = false) {
    if (!this.camera || !this.controls) return;
    const distance = this.blueprint ? 6.4 + (this.blueprint.events.length * 0.28) : 8.4;
    const target = new this.THREE.Vector3(0, 0.2, 0);
    const position = new this.THREE.Vector3(0, 2.8 + distance * 0.08, distance);
    if (this.cameraRestore?.position && this.cameraRestore?.target) {
      this.camera.position.copy(new this.THREE.Vector3(...this.cameraRestore.position));
      this.controls.target.copy(new this.THREE.Vector3(...this.cameraRestore.target));
      this.cameraRestore = null;
      this.controls.update();
      return;
    }
    if (instant) {
      this.camera.position.copy(position);
      this.controls.target.copy(target);
      this.controls.update();
      return;
    }
    this.camera.position.lerp(position, 0.9);
    this.controls.target.lerp(target, 0.9);
    this.controls.update();
  }

  async runGenerationRitual(blueprint) {
    const steps = [
      { phase: '折叠叙事', copy: '把人生节点、照片光谱与声音起伏压缩成可生成的神性结构。', stepLabel: 'Phase 1 / 4', mark: '黑金展厅正在点亮', progress: 0.18, duration: 420 },
      { phase: '提纯命运张力', copy: `识别 ${blueprint.events.length} 条关键枝系，决定是生长成环、球体、螺旋还是拓扑曲面。`, stepLabel: 'Phase 2 / 4', mark: '命运枝系正在分叉', progress: 0.46, duration: 520 },
      { phase: '铸造神性几何', copy: '将价值排序、情绪镜像与回撤预案重新铸造成一件可呼吸的雕塑。', stepLabel: 'Phase 3 / 4', mark: '核心壳层正在生长', progress: 0.76, duration: 620 },
      { phase: '展陈完成', copy: '光晕、粒子与拓扑曲面已经对齐，你可以开始观看它如何继续演化。', stepLabel: 'Phase 4 / 4', mark: '神魂拓扑已显现', progress: 1, duration: 360 },
    ];
    for (const step of steps) {
      this.updateRitualStage(step);
      await wait(step.duration);
    }
    const overlay = this.root?.querySelector('[data-dst-ritual]');
    if (overlay) overlay.hidden = true;
  }

  async generateTopology() {
    const start = performance.now();
    const input = this.getStoryInputProfile();
    this.updateFooter('正在折叠人生节点、照片光谱与声纹能量，生成神魂拓扑...');
    const nextBlueprint = buildSoulBlueprint(this.data, input, this.blueprint);
    await this.runGenerationRitual(nextBlueprint);
    this.blueprint = nextBlueprint;
    this.generationCount += 1;
    this.rebuildSculpture(nextBlueprint, { persist: true, announce: true });
    console.debug('[DST] generate:ms', Math.round(performance.now() - start));
  }

  rebuildSculpture(blueprint, { persist = true, announce = true } = {}) {
    if (!this.scene || !this.THREE || !this.ParametricGeometry || !blueprint) return;
    if (this.sculptureGroup) {
      this.disposeObject(this.sculptureGroup);
      this.scene.remove(this.sculptureGroup);
    }
    this.sculptureGroup = createSoulSculpture(this.THREE, this.ParametricGeometry, blueprint, {
      device: this.device,
      rendererType: this.rendererType,
      includeParticles: true,
    });
    this.scene.add(this.sculptureGroup);
    seedGrowthAnimation(this, announce);
    this.root.querySelector('[data-dst-empty-state]').hidden = true;
    this.applyFilterMode(this.filterMode, { immediate: true });
    this.renderCuratorialNotes();
    this.frameSculpture(false);
    this.renderStats();
    if (announce) {
      showToast('神魂拓扑已显现，雕塑正在开始呼吸。', 'success', 2600);
      this.updateFooter('新的几何结构已经长出，粒子流向与光影关系正在重排。');
    }
    if (persist) {
      awaitMaybe(this.saveState({
        topologyGeneratedAt: new Date().toISOString(),
        generationCount: this.generationCount,
      }));
    }
  }

  toggleFreeFlight() {
    this.freeFlightEnabled = !this.freeFlightEnabled;
    this.syncFreeFlightUi();
    if (this.freeFlightEnabled) {
      this.lastOrbitTarget = this.controls?.target?.clone?.() || null;
      const lookVector = (this.lastOrbitTarget || new this.THREE.Vector3(0, 0.2, 0)).clone().sub(this.camera.position).normalize();
      this.freeFlightLook.yaw = Math.atan2(lookVector.x, lookVector.z);
      this.freeFlightLook.pitch = Math.asin(Math.max(-0.98, Math.min(0.98, lookVector.y)));
      this.camera.position.copy(this.camera.position.clone().lerp(this.lastOrbitTarget || new this.THREE.Vector3(0, 0.2, 0), 0.24));
      this.updateFooter('自由飞行已开启：拖动鼠标转头，WASD / QE 穿过雕塑，Shift 加速。');
      showToast('自由飞行已开启：拖动鼠标转头。', 'info', 2200);
    } else {
      this.freeFlightPointer.active = false;
      if (this.lastOrbitTarget) this.controls.target.copy(this.lastOrbitTarget);
      this.updateFooter('已回到轨道漫游。');
      showToast('已退出自由飞行。', 'info', 1600);
    }
    awaitMaybe(this.saveState({ freeFlightEnabled: this.freeFlightEnabled }));
  }

  onKeyDown(event) {
    const target = event.target;
    const isTypingTarget = Boolean(target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable));
    if (event.key.toLowerCase() === 'f' && !isTypingTarget) {
      event.preventDefault();
      this.toggleFreeFlight();
      return;
    }
    if (!this.freeFlightEnabled) return;
    this.keyState[event.key.toLowerCase()] = true;
  }

  onKeyUp(event) {
    delete this.keyState[event.key.toLowerCase()];
  }

  onCanvasPointerDown(event) {
    if (!this.freeFlightEnabled || event.button !== 0) return;
    this.freeFlightPointer.active = true;
    this.freeFlightPointer.x = event.clientX;
    this.freeFlightPointer.y = event.clientY;
  }

  onCanvasPointerMove(event) {
    if (!this.freeFlightEnabled || !this.freeFlightPointer.active) return;
    const dx = event.clientX - this.freeFlightPointer.x;
    const dy = event.clientY - this.freeFlightPointer.y;
    this.freeFlightPointer.x = event.clientX;
    this.freeFlightPointer.y = event.clientY;
    this.freeFlightLook.yaw += dx * 0.0032;
    this.freeFlightLook.pitch = Math.max(-1.28, Math.min(1.28, this.freeFlightLook.pitch - dy * 0.0025));
  }

  onCanvasPointerUp() {
    this.freeFlightPointer.active = false;
  }

  async handleExport(kind) {
    if (!this.blueprint) {
      showToast('先生成一件神魂拓扑艺术装置，再导出。', 'warning', 2200);
      return;
    }
    if (this.isExporting) {
      showToast('导出任务正在进行，请稍候。', 'info', 1800);
      return;
    }
    this.isExporting = true;
    try {
      if (kind === 'glb') await exportGlb(this);
      else if (kind === 'video') await exportLoopVideo(this);
      else await exportStill(this, kind);
    } catch (error) {
      console.error('Divine Soul Topology export failed:', error);
      showToast(`导出失败：${error.message || error}`, 'error', 3800);
    } finally {
      this.isExporting = false;
    }
  }

  animate() {
    this.raf = requestAnimationFrame(() => this.animate());
    this.updateSceneFrame(this.getSceneTime());
  }

  onResize() {
    if (!this.camera || !this.renderer) return;
    this.camera.aspect = window.innerWidth / window.innerHeight;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(window.innerWidth, window.innerHeight);
    this.composer?.setSize(window.innerWidth, window.innerHeight);
  }

  async saveState(extra = {}) {
    this.lastSavedAt = new Date().toISOString();
    this.persistedState = {
      ...this.persistedState,
      decisionId: this.storageId,
      sourceDecisionId: this.decisionId,
      question: this.data.question,
      storyText: this.storyText,
      filterMode: this.filterMode,
      freeFlightEnabled: this.freeFlightEnabled,
      voice: {
        transcript: this.voiceTranscript,
        recordings: this.voiceRecordings,
      },
      photos: this.photos.map((photo) => ({
        id: photo.id,
        name: photo.name,
        dataUrl: photo.dataUrl,
        width: photo.width,
        height: photo.height,
        metrics: photo.metrics,
      })),
      topology: this.blueprint ? { blueprint: this.blueprint, evolutionClock: this.getSceneTime() } : null,
      camera: this.camera && this.controls ? { position: this.camera.position.toArray(), target: this.controls.target.toArray() } : null,
      generationCount: this.generationCount,
      updatedAt: this.lastSavedAt,
      ...extra,
    };
    await savePersistedSoulState(this.persistedState);
    this.updateSaveCopy(`已自动保存 ${new Date(this.lastSavedAt).toLocaleString('zh-CN')}`);
    this.renderStats();
  }

  disposeObject(object) {
    object.traverse?.((child) => {
      child.geometry?.dispose?.();
      if (Array.isArray(child.material)) {
        child.material.forEach((material) => {
          material.map?.dispose?.();
          material.dispose?.();
        });
      } else {
        child.material?.map?.dispose?.();
        child.material?.dispose?.();
      }
    });
  }

  async switchToQuantumMode() {
    const data = this.data;
    await this.close({ silent: true });
    await window.openQuantumVibeOracle?.(data);
  }

  async close({ silent = false } = {}) {
    if (this.voiceActive) {
      await stopVoiceCapture(this);
    }
    await this.saveState({ closedAt: new Date().toISOString() });
    cancelAnimationFrame(this.raf);
    if (this.saveTimer) window.clearInterval(this.saveTimer);
    window.removeEventListener('resize', this.onResize);
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    const canvas = this.root?.querySelector('[data-dst-canvas]');
    canvas?.removeEventListener('pointerdown', this.onCanvasPointerDown);
    canvas?.removeEventListener('pointermove', this.onCanvasPointerMove);
    canvas?.removeEventListener('pointerup', this.onCanvasPointerUp);
    canvas?.removeEventListener('pointercancel', this.onCanvasPointerUp);
    canvas?.removeEventListener('pointerleave', this.onCanvasPointerUp);
    this.controls?.dispose?.();
    if (this.sculptureGroup) this.disposeObject(this.sculptureGroup);
    if (this.backgroundStars) this.disposeObject(this.backgroundStars);
    this.composer?.dispose?.();
    this.renderer?.dispose?.();
    this.root?.remove();
    unlockBodyScroll();
    if (!silent) showToast('已回到理性模式。', 'info', 1600);
  }
}

function awaitMaybe(promise) {
  promise?.catch?.((error) => {
    console.warn('Divine async side effect failed:', error);
  });
}

export async function createDivineSoulTopologyController(explicitData) {
  const decisionData = getCurrentDecisionData(explicitData);
  window.decisionData = decisionData;
  const persisted = await loadPersistedSoulState(getDecisionId(decisionData, 'soul-local'));
  return new DivineSoulTopologyController(decisionData, persisted);
}
