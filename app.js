/* ========================================
   认知拉格朗日点 · 应用核心
   Canvas 渲染 · 粒子系统 · 交互逻辑
   ======================================== */

(function () {
  'use strict';

  // ── Canvas Setup ──
  const canvas = document.getElementById('cosmos');
  const ctx = canvas.getContext('2d');
  let W, H;

  function resize() {
    W = canvas.width = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);

  // ── Camera ──
  const camera = {
    x: 0, y: 0, zoom: 0.65,
    targetX: 0, targetY: 0, targetZoom: 0.65,
    minZoom: 0.25, maxZoom: 2.5
  };

  function worldToScreen(wx, wy) {
    return {
      x: (wx - camera.x) * camera.zoom + W / 2,
      y: (wy - camera.y) * camera.zoom + H / 2
    };
  }

  function screenToWorld(sx, sy) {
    return {
      x: (sx - W / 2) / camera.zoom + camera.x,
      y: (sy - H / 2) / camera.zoom + camera.y
    };
  }

  // ── Stars ──
  const STAR_COUNT = 800;
  const stars = [];

  function initStars() {
    for (let i = 0; i < STAR_COUNT; i++) {
      stars.push({
        x: (Math.random() - 0.5) * 4000,
        y: (Math.random() - 0.5) * 4000,
        size: Math.random() * 1.5 + 0.3,
        brightness: Math.random(),
        twinklePhase: Math.random() * Math.PI * 2,
        twinkleSpeed: 0.005 + Math.random() * 0.02,
        depth: 0.2 + Math.random() * 0.8  // parallax depth
      });
    }
  }
  initStars();

  // ── Node State ──
  // Flatten all nodes with system reference for rendering
  const allNodes = [];
  SYSTEMS.forEach(system => {
    system.nodes.forEach(node => {
      allNodes.push({
        system,
        data: node,
        // current world position (updated each frame)
        wx: 0, wy: 0,
        // screen position (updated each frame)
        sx: 0, sy: 0,
        // visual state
        hovered: false,
        glowIntensity: 0,
        pulsePhase: Math.random() * Math.PI * 2
      });
    });
  });

  // ── App State ──
  let state = 'title'; // 'title' | 'exploring' | 'detail'
  let time = 0;
  let titleStartTime = 0;
  let hoveredNode = null;
  let selectedNode = null;

  // mouse
  let mouseX = W / 2, mouseY = H / 2;
  let isDragging = false;
  let dragStartX = 0, dragStartY = 0;
  let dragCamStartX = 0, dragCamStartY = 0;
  let hasDragged = false;

  // ── DOM Elements ──
  const titleScreen = document.getElementById('title-screen');
  const titleMain = document.getElementById('title-main');
  const titleSub = document.getElementById('title-sub');
  const titleEnter = document.getElementById('title-enter');
  const navHint = document.getElementById('nav-hint');
  const tooltip = document.getElementById('tooltip');
  const tooltipName = tooltip.querySelector('.tooltip-name');
  const tooltipSubtitle = tooltip.querySelector('.tooltip-subtitle');
  const detailPanel = document.getElementById('detail-panel');
  const overlay = document.getElementById('overlay');
  const detailClose = document.getElementById('detail-close');
  const systemLabels = document.getElementById('system-labels');

  // ── Title Animation ──
  function startTitleAnimation() {
    titleStartTime = performance.now();
    const text = '认知拉格朗日点';
    titleMain.innerHTML = '';

    text.split('').forEach((char, i) => {
      const span = document.createElement('span');
      span.className = 'char';
      span.textContent = char;
      span.style.animationDelay = `${0.8 + i * 0.12}s`;
      titleMain.appendChild(span);
    });

    setTimeout(() => {
      document.querySelector('.title-dot').classList.add('visible');
    }, 1800);

    setTimeout(() => {
      titleSub.classList.add('visible');
    }, 2400);

    setTimeout(() => {
      document.querySelector('.title-divider').classList.add('visible');
    }, 3200);

    setTimeout(() => {
      titleEnter.classList.add('visible');
    }, 3800);
  }

  // ── Enter Main Experience ──
  function enterExploring() {
    if (state !== 'title') return;
    state = 'exploring';
    titleScreen.classList.add('hidden');
    navHint.classList.add('visible');
    document.body.classList.add('can-grab');

    // Create system labels
    createSystemLabels();
  }

  function createSystemLabels() {
    systemLabels.innerHTML = '';
    SYSTEMS.forEach(system => {
      const label = document.createElement('div');
      label.className = 'system-label';
      label.dataset.systemId = system.id;

      const [r, g, b] = system.color;
      label.innerHTML = `
        <div class="system-label-name" style="color: rgba(${r},${g},${b},0.7); text-shadow: 0 0 30px rgba(${r},${g},${b},0.4);">${system.name}</div>
        <div class="system-label-en">${system.nameEn}</div>
      `;
      systemLabels.appendChild(label);
    });
  }

  // ── Detail Panel ──
  function openDetail(nodeObj) {
    selectedNode = nodeObj;
    state = 'detail';
    const d = nodeObj.data;
    const s = nodeObj.system;
    const [r, g, b] = s.color;
    const colorStr = `rgb(${r},${g},${b})`;

    detailPanel.querySelector('.detail-system').textContent = `── ${s.name} ──`;
    detailPanel.querySelector('.detail-system').style.color = colorStr;
    detailPanel.querySelector('.detail-title').textContent = d.name;
    detailPanel.querySelector('.detail-subtitle').textContent = d.subtitle;
    detailPanel.querySelector('.detail-divider').style.background = colorStr;
    detailPanel.querySelector('.tension-left').childNodes[0].textContent = d.tension[0];
    detailPanel.querySelector('.tension-left').style.color = colorStr;
    detailPanel.querySelector('.tension-right').childNodes[0].textContent = '';
    detailPanel.querySelector('.tension-right').textContent = d.tension[1];
    detailPanel.querySelector('.tension-right').style.color = colorStr;
    detailPanel.querySelector('.tension-icon').style.color = colorStr;
    detailPanel.querySelector('.detail-question').textContent = d.question;
    detailPanel.querySelector('.detail-question').style.borderColor = `rgba(${r},${g},${b},0.4)`;

    // Format body paragraphs
    const bodyEl = detailPanel.querySelector('.detail-body');
    bodyEl.innerHTML = d.body.split('\n\n').map(p => `<p style="margin-bottom:1.2em">${p}</p>`).join('');

    // Re-set tension display with proper structure
    const tensionLeft = detailPanel.querySelector('.tension-left');
    const tensionRight = detailPanel.querySelector('.tension-right');
    tensionLeft.innerHTML = d.tension[0];
    tensionRight.innerHTML = d.tension[1];

    detailPanel.classList.add('open');
    overlay.classList.add('visible');

    // Scroll to top
    detailPanel.querySelector('.detail-scroll').scrollTop = 0;
  }

  function closeDetail() {
    detailPanel.classList.remove('open');
    overlay.classList.remove('visible');
    selectedNode = null;
    state = 'exploring';
  }

  // ── Rendering ──

  function drawStars() {
    stars.forEach(star => {
      star.twinklePhase += star.twinkleSpeed;
      const twinkle = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(star.twinklePhase));
      const alpha = star.brightness * twinkle;

      // Parallax: deeper stars move less
      const parallaxFactor = star.depth * 0.6;
      const sx = (star.x - camera.x * parallaxFactor) * camera.zoom + W / 2;
      const sy = (star.y - camera.y * parallaxFactor) * camera.zoom + H / 2;

      // Cull off-screen
      if (sx < -10 || sx > W + 10 || sy < -10 || sy > H + 10) return;

      ctx.fillStyle = `rgba(200, 210, 255, ${alpha})`;
      ctx.beginPath();
      ctx.arc(sx, sy, star.size * camera.zoom, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  function drawSystemOrbit(system) {
    const center = worldToScreen(system.position.x, system.position.y);
    const [r, g, b] = system.color;

    // Draw orbital ring (average distance)
    const avgDist = 185 * camera.zoom;
    ctx.strokeStyle = `rgba(${r},${g},${b},0.06)`;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(center.x, center.y, avgDist, 0, Math.PI * 2);
    ctx.stroke();

    // Draw center glow
    const gradient = ctx.createRadialGradient(
      center.x, center.y, 0,
      center.x, center.y, 60 * camera.zoom
    );
    gradient.addColorStop(0, `rgba(${r},${g},${b},0.08)`);
    gradient.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(center.x, center.y, 60 * camera.zoom, 0, Math.PI * 2);
    ctx.fill();
  }

  function drawNode(nodeObj) {
    const d = nodeObj.data;
    const s = nodeObj.system;
    const [r, g, b] = s.color;

    // Update world position (orbiting)
    const angle = d.angle + time * d.orbitSpeed;
    nodeObj.wx = s.position.x + Math.cos(angle) * d.distance;
    nodeObj.wy = s.position.y + Math.sin(angle) * d.distance;

    // Screen position
    const screen = worldToScreen(nodeObj.wx, nodeObj.wy);
    nodeObj.sx = screen.x;
    nodeObj.sy = screen.y;

    // Cull off-screen (with margin for glow)
    if (screen.x < -100 || screen.x > W + 100 || screen.y < -100 || screen.y > H + 100) return;

    // Pulse
    nodeObj.pulsePhase += 0.02;
    const pulse = 0.7 + 0.3 * Math.sin(nodeObj.pulsePhase);

    // Hover glow interpolation
    const targetGlow = nodeObj.hovered ? 1 : 0;
    nodeObj.glowIntensity += (targetGlow - nodeObj.glowIntensity) * 0.1;

    const baseRadius = 4 * camera.zoom;
    const glowRadius = (30 + 20 * nodeObj.glowIntensity) * camera.zoom;
    const outerGlowRadius = (60 + 40 * nodeObj.glowIntensity) * camera.zoom;

    // Outer glow
    const outerGlow = ctx.createRadialGradient(
      screen.x, screen.y, 0,
      screen.x, screen.y, outerGlowRadius
    );
    const outerAlpha = (0.1 + 0.15 * nodeObj.glowIntensity) * pulse;
    outerGlow.addColorStop(0, `rgba(${r},${g},${b},${outerAlpha})`);
    outerGlow.addColorStop(0.4, `rgba(${r},${g},${b},${outerAlpha * 0.3})`);
    outerGlow.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.fillStyle = outerGlow;
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, outerGlowRadius, 0, Math.PI * 2);
    ctx.fill();

    // Inner glow
    const innerGlow = ctx.createRadialGradient(
      screen.x, screen.y, 0,
      screen.x, screen.y, glowRadius
    );
    const innerAlpha = (0.3 + 0.4 * nodeObj.glowIntensity) * pulse;
    innerGlow.addColorStop(0, `rgba(${r},${g},${b},${innerAlpha})`);
    innerGlow.addColorStop(1, `rgba(${r},${g},${b},0)`);
    ctx.fillStyle = innerGlow;
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, glowRadius, 0, Math.PI * 2);
    ctx.fill();

    // Core dot
    ctx.fillStyle = `rgba(${r},${g},${b},${0.8 + 0.2 * pulse})`;
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, baseRadius, 0, Math.PI * 2);
    ctx.fill();

    // White center
    ctx.fillStyle = `rgba(255,255,255,${0.6 + 0.3 * pulse + 0.1 * nodeObj.glowIntensity})`;
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, baseRadius * 0.5, 0, Math.PI * 2);
    ctx.fill();

    // Connection line to system center
    const center = worldToScreen(s.position.x, s.position.y);
    ctx.strokeStyle = `rgba(${r},${g},${b},${0.04 + 0.06 * nodeObj.glowIntensity})`;
    ctx.lineWidth = 0.5;
    ctx.beginPath();
    ctx.moveTo(center.x, center.y);
    ctx.lineTo(screen.x, screen.y);
    ctx.stroke();
  }

  function drawConnections() {
    // Draw faint lines between systems
    ctx.save();
    ctx.globalAlpha = 0.03;
    ctx.strokeStyle = 'rgba(255,255,255,1)';
    ctx.lineWidth = 0.5;

    for (let i = 0; i < SYSTEMS.length; i++) {
      for (let j = i + 1; j < SYSTEMS.length; j++) {
        const a = worldToScreen(SYSTEMS[i].position.x, SYSTEMS[i].position.y);
        const b = worldToScreen(SYSTEMS[j].position.x, SYSTEMS[j].position.y);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  function updateSystemLabels() {
    const labels = systemLabels.querySelectorAll('.system-label');
    labels.forEach(label => {
      const sys = SYSTEMS.find(s => s.id === label.dataset.systemId);
      if (!sys) return;
      const screen = worldToScreen(sys.position.x, sys.position.y - 50);
      label.style.left = screen.x + 'px';
      label.style.top = (screen.y - 50 * camera.zoom) + 'px';
      label.style.transform = 'translate(-50%, -100%)';
      label.style.opacity = Math.min(1, camera.zoom * 1.2);
    });
  }

  // ── Hit Testing ──
  function getHoveredNode(mx, my) {
    let closest = null;
    let closestDist = Infinity;
    const hitRadius = 30;

    allNodes.forEach(nodeObj => {
      const dx = nodeObj.sx - mx;
      const dy = nodeObj.sy - my;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < hitRadius && dist < closestDist) {
        closest = nodeObj;
        closestDist = dist;
      }
    });

    return closest;
  }

  // ── Main Render Loop ──
  function render() {
    time += 0.016; // ~60fps time step

    // Smooth camera interpolation
    camera.x += (camera.targetX - camera.x) * 0.08;
    camera.y += (camera.targetY - camera.y) * 0.08;
    camera.zoom += (camera.targetZoom - camera.zoom) * 0.08;

    // Clear
    ctx.fillStyle = '#06060f';
    ctx.fillRect(0, 0, W, H);

    // Subtle vignette
    const vignette = ctx.createRadialGradient(W/2, H/2, W * 0.2, W/2, H/2, W * 0.8);
    vignette.addColorStop(0, 'rgba(6,6,15,0)');
    vignette.addColorStop(1, 'rgba(0,0,0,0.4)');
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, W, H);

    // Draw scene
    drawStars();

    if (state !== 'title') {
      drawConnections();
      SYSTEMS.forEach(drawSystemOrbit);
      allNodes.forEach(drawNode);
      updateSystemLabels();
    }

    requestAnimationFrame(render);
  }

  // ── Mouse Events ──
  canvas.addEventListener('mousedown', (e) => {
    if (state === 'title') return;
    isDragging = true;
    hasDragged = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragCamStartX = camera.targetX;
    dragCamStartY = camera.targetY;
    document.body.classList.add('dragging');
    document.body.classList.remove('can-grab');
  });

  window.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;

    if (isDragging) {
      const dx = (e.clientX - dragStartX) / camera.zoom;
      const dy = (e.clientY - dragStartY) / camera.zoom;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDragged = true;
      camera.targetX = dragCamStartX - dx;
      camera.targetY = dragCamStartY - dy;
    } else if (state === 'exploring') {
      // Hit test for hover
      const node = getHoveredNode(mouseX, mouseY);
      if (node !== hoveredNode) {
        if (hoveredNode) hoveredNode.hovered = false;
        hoveredNode = node;
        if (hoveredNode) hoveredNode.hovered = true;
      }

      // Tooltip
      if (hoveredNode) {
        tooltip.classList.add('visible');
        tooltipName.textContent = hoveredNode.data.name;
        tooltipSubtitle.textContent = hoveredNode.data.subtitle;
        tooltip.style.left = (mouseX + 16) + 'px';
        tooltip.style.top = (mouseY - 20) + 'px';
        document.body.classList.add('pointer-node');
        document.body.classList.remove('can-grab');
      } else {
        tooltip.classList.remove('visible');
        document.body.classList.remove('pointer-node');
        document.body.classList.add('can-grab');
      }
    }
  });

  window.addEventListener('mouseup', (e) => {
    if (isDragging) {
      isDragging = false;
      document.body.classList.remove('dragging');
      if (!hoveredNode) document.body.classList.add('can-grab');

      // If it was a click (not drag), check for node hit
      if (!hasDragged && state === 'exploring') {
        const node = getHoveredNode(e.clientX, e.clientY);
        if (node) {
          openDetail(node);
          tooltip.classList.remove('visible');
        }
      }
    }
  });

  // Click on canvas for node selection (non-drag clicks)
  canvas.addEventListener('click', (e) => {
    if (state === 'title') {
      enterExploring();
      return;
    }
  });

  // Scroll to zoom
  canvas.addEventListener('wheel', (e) => {
    if (state === 'title') return;
    e.preventDefault();

    const zoomFactor = 1 - e.deltaY * 0.001;
    const newZoom = Math.max(camera.minZoom, Math.min(camera.maxZoom, camera.targetZoom * zoomFactor));

    // Zoom toward mouse position
    const worldBefore = screenToWorld(e.clientX, e.clientY);
    camera.targetZoom = newZoom;
    // Adjust camera position so the point under the mouse stays fixed
    const worldAfter = screenToWorld(e.clientX, e.clientY);
    camera.targetX -= (worldAfter.x - worldBefore.x) * 0.3;
    camera.targetY -= (worldAfter.y - worldBefore.y) * 0.3;
  }, { passive: false });

  // ── Touch Events ──
  let lastTouchDist = 0;
  let touchStartX = 0, touchStartY = 0;

  canvas.addEventListener('touchstart', (e) => {
    if (state === 'title') {
      enterExploring();
      return;
    }

    if (e.touches.length === 1) {
      isDragging = true;
      hasDragged = false;
      const t = e.touches[0];
      dragStartX = t.clientX;
      dragStartY = t.clientY;
      touchStartX = t.clientX;
      touchStartY = t.clientY;
      dragCamStartX = camera.targetX;
      dragCamStartY = camera.targetY;
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      lastTouchDist = Math.sqrt(dx * dx + dy * dy);
    }
  }, { passive: true });

  canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    if (e.touches.length === 1 && isDragging) {
      const t = e.touches[0];
      const dx = (t.clientX - dragStartX) / camera.zoom;
      const dy = (t.clientY - dragStartY) / camera.zoom;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) hasDragged = true;
      camera.targetX = dragCamStartX - dx;
      camera.targetY = dragCamStartY - dy;
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (lastTouchDist > 0) {
        const scale = dist / lastTouchDist;
        camera.targetZoom = Math.max(camera.minZoom, Math.min(camera.maxZoom, camera.targetZoom * scale));
      }
      lastTouchDist = dist;
    }
  }, { passive: false });

  canvas.addEventListener('touchend', (e) => {
    if (isDragging && !hasDragged && state === 'exploring') {
      const node = getHoveredNode(touchStartX, touchStartY);
      if (node) {
        openDetail(node);
      }
    }
    isDragging = false;
    lastTouchDist = 0;
  }, { passive: true });

  // ── UI Events ──
  titleEnter.addEventListener('click', (e) => {
    e.stopPropagation();
    enterExploring();
  });

  detailClose.addEventListener('click', closeDetail);
  overlay.addEventListener('click', closeDetail);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (state === 'detail') closeDetail();
    }
  });

  // ── Init ──
  startTitleAnimation();
  render();

})();
