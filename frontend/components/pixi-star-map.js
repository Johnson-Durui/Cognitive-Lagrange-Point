/**
 * WebGL Star Map Renderer using Pixi.js
 * Extracted from app.js Canvas Rendering
 */

class ParticleSystem {
  constructor(app) {
    this.app = app;
    this.pool = [];
    this.particles = [];
    this.container = new PIXI.Container();
    this.app.stage.addChild(this.container);
    for (let i = 0; i < 300; i += 1) {
      const particle = new PIXI.Graphics();
      this.pool.push(particle);
    }
  }

  emit(infoType, targetX, targetY, count = 25) {
    const colors = { pro: 0x4ade80, con: 0xf87171, info: 0x60a5fa, regret: 0xfacc15 };
    const color = colors[infoType] || 0xffffff;
    for (let i = 0; i < count; i += 1) {
      const particle = this.pool.pop() || new PIXI.Graphics();
      particle.clear();
      particle.beginFill(color);
      particle.drawCircle(0, 0, 3);
      particle.endFill();
      particle.x = Math.random() * this.app.screen.width;
      particle.y = Math.random() * this.app.screen.height * 0.3;
      particle.alpha = 1;
      particle.vx = (targetX - particle.x) / 55 + (Math.random() - 0.5) * 3;
      particle.vy = (targetY - particle.y) / 55 + (Math.random() - 0.5) * 3;
      particle.infoType = infoType;
      this.container.addChild(particle);
      this.particles.push(particle);
    }
  }

  update() {
    for (let i = this.particles.length - 1; i >= 0; i -= 1) {
      const particle = this.particles[i];
      particle.x += particle.vx;
      particle.y += particle.vy;
      particle.alpha -= 0.018;
      if (particle.alpha <= 0) {
        this.container.removeChild(particle);
        this.pool.push(particle);
        this.particles.splice(i, 1);
      }
    }
  }
}

export class PixiStarMap {
  constructor(canvasElement) {
    this.app = new PIXI.Application({
      view: canvasElement,
      resizeTo: window,
      autoDensity: true,
      resolution: window.devicePixelRatio || 1,
      backgroundColor: 0x050510,
      antialias: true
    });
    
    // Core containers
    this.world = new PIXI.Container();
    this.app.stage.addChild(this.world);
    
    this.linksContainer = new PIXI.Container();
    this.nodesContainer = new PIXI.Container();
    this.futurePathsContainer = new PIXI.Container();
    
    this.world.addChild(this.linksContainer);
    this.world.addChild(this.nodesContainer);
    this.world.addChild(this.futurePathsContainer);
    this.particles = new ParticleSystem(this.app);
    
    // Viewport state
    this.transform = { x: this.app.screen.width / 2, y: this.app.screen.height / 2, k: 1 };
    this.world.position.set(this.transform.x, this.transform.y);
    
    this.nodes = [];
    this.links = [];
    this.futurePathSignature = '';
    
    // Basic interaction setup
    this.app.view.addEventListener('wheel', this.onWheel.bind(this));
    
    // Tick
    this.app.ticker.add(this.render.bind(this));
  }
  
  onWheel(e) {
    e.preventDefault();
    const scaleFactor = e.deltaY < 0 ? 1.1 : 0.9;
    this.transform.k *= scaleFactor;
    this.world.scale.set(this.transform.k);
  }
  
  updateData(nodes, links) {
    this.nodes = nodes;
    this.links = links;
    
    this.nodesContainer.removeChildren();
    this.linksContainer.removeChildren();
    
    // Initialize graphics for nodes
    this.nodes.forEach(node => {
      const g = new PIXI.Graphics();
      g.beginFill(node.color || 0xffffff);
      g.drawCircle(0, 0, 5);
      g.endFill();
      node.sprite = g;
      this.nodesContainer.addChild(g);
    });
    
    // Links are drawn in render() as they dynamically update
    this.linksGraphics = new PIXI.Graphics();
    this.linksContainer.addChild(this.linksGraphics);
  }

  clearFuturePaths() {
    this.futurePathSignature = '';
    if (this.futurePathsContainer) {
      this.futurePathsContainer.removeChildren();
    }
  }

  renderFuturePaths(output, meta = {}) {
    if (!output || !this.futurePathsContainer) {
      if (this.futurePathSignature) this.clearFuturePaths();
      return;
    }

    const monte = output.monte_carlo || {};
    const smooth = monte.smooth_prob || {};
    const signature = JSON.stringify({
      a: output.choice_a?.choice_name || '',
      b: output.choice_b?.choice_name || '',
      optimistic: output.probability_optimistic || smooth.optimistic || 0,
      baseline: output.probability_baseline || smooth.baseline || 0,
      pessimistic: output.probability_pessimistic || smooth.pessimistic || 0,
      sampleCount: monte.sample_count || 0,
    });
    if (signature === this.futurePathSignature) return;
    this.futurePathSignature = signature;
    this.futurePathsContainer.removeChildren();

    const center = this.createFutureNode({
      x: 0,
      y: 0,
      label: meta.title || '当前决策',
      color: 0xf4e8cc,
      radius: 34,
      subtitle: monte.sample_count ? `${monte.sample_count} 次 Ultra 分支采样` : '未来路径画布',
    });
    this.futurePathsContainer.addChild(center);

    const paths = [
      {
        key: 'tailwind',
        label: '顺风路径',
        color: 0x4a9977,
        probability: Number(smooth.optimistic || output.probability_optimistic || 0),
        angle: -Math.PI / 2,
      },
      {
        key: 'steady',
        label: '平稳路径',
        color: 0xf2b64f,
        probability: Number(smooth.baseline || output.probability_baseline || 0),
        angle: Math.PI * 0.16,
      },
      {
        key: 'headwind',
        label: '逆风路径',
        color: 0xe68069,
        probability: Number(smooth.pessimistic || output.probability_pessimistic || 0),
        angle: Math.PI * 0.84,
      },
    ];

    paths.forEach((path) => {
      const distance = 250 + Math.max(0, Math.min(path.probability, 100)) * 1.25;
      const x = Math.cos(path.angle) * distance;
      const y = Math.sin(path.angle) * distance * 0.72;
      const line = new PIXI.Graphics();
      line.lineStyle(2 + path.probability / 28, path.color, 0.72);
      line.moveTo(0, 0);
      line.quadraticCurveTo(x * 0.45, y * 0.45 - 54, x, y);
      this.futurePathsContainer.addChild(line);

      const node = this.createFutureNode({
        x,
        y,
        label: `${path.label} ${path.probability}%`,
        color: path.color,
        radius: 22 + path.probability * 0.08,
        subtitle: path.key,
      });
      node.eventMode = 'static';
      node.cursor = 'pointer';
      node.on('pointerdown', () => {
        window.dispatchEvent(new CustomEvent('clp:future-path-selected', {
          detail: { path, output },
        }));
      });
      this.futurePathsContainer.addChild(node);
    });
  }

  createFutureNode({ x, y, label, color, radius = 24, subtitle = '' }) {
    const node = new PIXI.Container();
    const glow = new PIXI.Graphics();
    glow.beginFill(color, 0.14);
    glow.drawCircle(0, 0, radius * 2.6);
    glow.endFill();
    node.addChild(glow);

    const circle = new PIXI.Graphics();
    circle.beginFill(color, 0.92);
    circle.drawCircle(0, 0, radius);
    circle.endFill();
    node.addChild(circle);

    const text = new PIXI.Text(label, {
      fontFamily: 'Noto Serif SC, serif',
      fontSize: 13,
      fill: 0xffffff,
      align: 'center',
      wordWrap: true,
      wordWrapWidth: 150,
    });
    text.anchor.set(0.5);
    text.y = radius + 18;
    node.addChild(text);

    if (subtitle) {
      const sub = new PIXI.Text(subtitle, {
        fontFamily: 'PingFang SC, sans-serif',
        fontSize: 10,
        fill: 0xb8c1d6,
        align: 'center',
      });
      sub.anchor.set(0.5);
      sub.y = radius + 36;
      node.addChild(sub);
    }

    node.position.set(x, y);
    return node;
  }
  
  render() {
    // 1) Update node positions from Force simulation
    this.nodes.forEach(node => {
      if (node.sprite) {
        node.sprite.x = node.x || 0;
        node.sprite.y = node.y || 0;
      }
    });
    
    // 2) Re-draw links
    if (this.linksGraphics) {
      this.linksGraphics.clear();
      this.linksGraphics.lineStyle(1, 0x444466, 0.5);
      this.links.forEach(link => {
        const source = link.source;
        const target = link.target;
        this.linksGraphics.moveTo(source.x, source.y);
        this.linksGraphics.lineTo(target.x, target.y);
      });
    }

    this.particles.update();
  }

  emitParticleBurst({ infoType = 'info', targetX = this.app.screen.width / 2, targetY = this.app.screen.height / 2, count = 25 } = {}) {
    this.particles.emit(infoType, targetX, targetY, count);
  }
}
