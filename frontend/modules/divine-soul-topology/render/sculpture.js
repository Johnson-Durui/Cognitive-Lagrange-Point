/**
 * 神魂拓扑雕塑构建
 */

import { clamp, createSeededRandom } from '../../art-experience/common.js';

function createSoulSurfaceFunction(blueprint) {
  const { shellRadius, shellMinor, lobes, twist, stretch } = blueprint.core;
  return (u, v, target) => {
    const theta = u * Math.PI * 2;
    const phi = v * Math.PI * 2;
    const wave = 1 + 0.16 * Math.sin(phi * lobes + theta * twist) + 0.08 * Math.cos(theta * (lobes - 1));
    const minor = shellMinor * wave;
    const localTwist = phi + theta * twist * 0.34;
    const x = (shellRadius + minor * Math.cos(localTwist)) * Math.cos(theta);
    const y = (minor * Math.sin(localTwist) * stretch) + Math.sin(theta * (lobes * 0.55)) * shellRadius * 0.14;
    const z = (shellRadius + minor * Math.cos(localTwist)) * Math.sin(theta);
    target.set(x, y, z);
  };
}

function createMobiusFunction(event) {
  return (u, v, target) => {
    const theta = u * Math.PI * 2;
    const strip = (v - 0.5) * event.scale * 1.45;
    const radius = event.scale * 1.24;
    const half = (theta / 2) + event.drift;
    const x = (radius + strip * Math.cos(half)) * Math.cos(theta);
    const y = strip * Math.sin(half);
    const z = (radius + strip * Math.cos(half)) * Math.sin(theta);
    target.set(x, y, z);
  };
}

function createEventMaterial(THREE, event, transparent = false) {
  return new THREE.MeshPhysicalMaterial({
    color: event.color,
    emissive: event.glow,
    emissiveIntensity: transparent ? 0.42 : 0.3,
    metalness: transparent ? 0.88 : 0.68,
    roughness: transparent ? 0.18 : 0.26,
    transparent,
    opacity: transparent ? 0.4 : 0.92,
    clearcoat: 1,
    clearcoatRoughness: 0.16,
    side: transparent ? THREE.DoubleSide : THREE.FrontSide,
    reflectivity: 1,
  });
}

function createSoulParticleField(THREE, blueprint, { budget, rendererType }) {
  const random = createSeededRandom(`${blueprint.seed}:particles`);
  const count = Math.round(budget * clamp(blueprint.particles.density, 0.4, 0.95));
  const positions = new Float32Array(count * 3);
  const seeds = new Float32Array(count);
  const phases = new Float32Array(count);
  const scales = new Float32Array(count);
  const colors = new Float32Array(count * 3);
  const baseColors = [blueprint.palette.gold, blueprint.palette.silver, blueprint.palette.cyan, blueprint.palette.violet];
  for (let i = 0; i < count; i += 1) {
    const orbit = blueprint.events[i % Math.max(blueprint.events.length, 1)];
    const radius = (random() < 0.62)
      ? (blueprint.core.shellRadius * (0.74 + random() * 1.2))
      : ((orbit?.orbitRadius || blueprint.core.shellRadius) * (0.84 + random() * 0.62));
    const theta = random() * Math.PI * 2;
    const phi = Math.acos((random() * 2) - 1);
    positions[i * 3] = Math.sin(phi) * Math.cos(theta) * radius;
    positions[i * 3 + 1] = Math.cos(phi) * radius * (0.58 + random() * 0.7);
    positions[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * radius;
    seeds[i] = random();
    phases[i] = random() * Math.PI * 2;
    scales[i] = 0.55 + random() * 1.9;
    const hex = baseColors[i % baseColors.length];
    colors[i * 3] = ((hex >> 16) & 0xff) / 255;
    colors[i * 3 + 1] = ((hex >> 8) & 0xff) / 255;
    colors[i * 3 + 2] = (hex & 0xff) / 255;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('aSeed', new THREE.BufferAttribute(seeds, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

  const uniforms = {
    uTime: { value: 0 },
    uFlow: { value: 0.5 },
    uPixelRatio: { value: Math.min(window.devicePixelRatio || 1, 1.75) },
  };

  const material = rendererType === 'WebGPU'
    ? new THREE.PointsMaterial({
      size: 0.06,
      vertexColors: true,
      transparent: true,
      opacity: 0.56,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
    : new THREE.ShaderMaterial({
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      vertexShader: `
        attribute float aSeed;
        attribute float aPhase;
        attribute float aScale;
        uniform float uTime;
        uniform float uFlow;
        uniform float uPixelRatio;
        varying float vSeed;
        varying vec3 vColor;
        void main() {
          vec3 p = position;
          float orbit = atan(p.z, p.x);
          float radius = length(p.xz);
          float swirl = sin(radius * 1.7 - uTime * (0.7 + uFlow) + aPhase) * 0.26;
          orbit += swirl * (0.3 + aSeed * 0.6);
          p.x = cos(orbit) * radius;
          p.z = sin(orbit) * radius;
          p.y += cos(uTime * 0.8 + aPhase + aSeed * 6.28318) * 0.22;
          vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mvPosition;
          gl_PointSize = aScale * (64.0 / max(0.45, -mvPosition.z)) * uPixelRatio;
          vSeed = aSeed;
          vColor = color;
        }
      `,
      fragmentShader: `
        varying float vSeed;
        varying vec3 vColor;
        void main() {
          vec2 uv = gl_PointCoord - vec2(0.5);
          float dist = length(uv);
          if (dist > 0.5) discard;
          float core = smoothstep(0.46, 0.06, dist);
          float halo = smoothstep(0.5, 0.14, dist) * 0.36;
          gl_FragColor = vec4(vColor, (core + halo) * (0.42 + vSeed * 0.4));
        }
      `,
    });
  const points = new THREE.Points(geometry, material);
  points.userData.dstRole = 'particles';
  points.userData.dstUniforms = uniforms;
  points.userData.spinSpeed = 0.0018;
  return points;
}

export function createBackgroundStars(THREE, palette, lowPower) {
  const random = createSeededRandom(`dst-background:${palette.gold}`);
  const count = lowPower ? 480 : 920;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const base = [palette.gold, palette.cyan, palette.violet];
  for (let i = 0; i < count; i += 1) {
    positions[i * 3] = (random() - 0.5) * 54;
    positions[i * 3 + 1] = (random() - 0.5) * 28;
    positions[i * 3 + 2] = (random() - 0.5) * 54;
    const hex = base[i % base.length];
    colors[i * 3] = ((hex >> 16) & 0xff) / 255;
    colors[i * 3 + 1] = ((hex >> 8) & 0xff) / 255;
    colors[i * 3 + 2] = (hex & 0xff) / 255;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({
    size: lowPower ? 0.06 : 0.08,
    vertexColors: true,
    transparent: true,
    opacity: 0.42,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const stars = new THREE.Points(geometry, material);
  stars.userData.dstRole = 'background-stars';
  return stars;
}

export function createSoulSculpture(THREE, ParametricGeometry, blueprint, { device, rendererType, includeParticles = true }) {
  const group = new THREE.Group();
  const palette = blueprint.palette;

  const coreMaterial = new THREE.MeshPhysicalMaterial({
    color: palette.obsidian,
    emissive: palette.gold,
    emissiveIntensity: 0.42,
    metalness: 0.96,
    roughness: 0.12,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
    reflectivity: 1,
  });
  const core = new THREE.Mesh(
    new THREE.IcosahedronGeometry(blueprint.core.radius, device.lowPower ? 3 : 5),
    coreMaterial
  );
  core.userData.dstRole = 'core';
  core.userData.pulseSpeed = 0.85 + blueprint.motion.breath;
  group.add(core);

  const shellMaterial = new THREE.MeshPhysicalMaterial({
    color: palette.surface,
    emissive: palette.cyan,
    emissiveIntensity: 0.16,
    metalness: 0.76,
    roughness: 0.14,
    transparent: true,
    opacity: 0.32,
    clearcoat: 1,
    side: THREE.DoubleSide,
  });
  const shell = new THREE.Mesh(
    new ParametricGeometry(createSoulSurfaceFunction(blueprint), device.lowPower ? 58 : 88, device.lowPower ? 28 : 44),
    shellMaterial
  );
  shell.userData.dstRole = 'topology-shell';
  shell.userData.spinSpeed = 0.0022;
  group.add(shell);

  const aura = new THREE.Mesh(
    new THREE.SphereGeometry(blueprint.core.shellRadius * 1.15, 40, 28),
    new THREE.MeshBasicMaterial({
      color: palette.spirit,
      transparent: true,
      opacity: 0.08,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  aura.userData.dstRole = 'aura';
  group.add(aura);

  for (let i = 0; i < blueprint.core.ringCount; i += 1) {
    const radius = blueprint.core.radius * 1.4 + i * 0.46;
    const ring = new THREE.Mesh(
      new THREE.TorusGeometry(radius, 0.018 + i * 0.006, 20, 220),
      new THREE.MeshBasicMaterial({
        color: i % 2 === 0 ? palette.gold : palette.violet,
        transparent: true,
        opacity: 0.22 + i * 0.03,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      })
    );
    ring.rotation.x = Math.PI / 2 + i * 0.32;
    ring.rotation.y = i * 0.44;
    ring.userData.dstRole = 'ring';
    ring.userData.waveSpeed = 0.8 + i * 0.14;
    group.add(ring);
  }

  let eventGroupCount = 0;
  blueprint.events.forEach((event) => {
    const eventGroup = new THREE.Group();
    eventGroup.userData.dstRole = 'event-group';
    eventGroup.userData.eventId = event.id;
    eventGroup.userData.orbitRadius = event.orbitRadius;
    eventGroup.userData.baseAngle = event.angle;
    eventGroup.userData.baseHeight = event.orbitHeight;
    eventGroup.userData.spinSpeed = event.spinSpeed;
    eventGroup.userData.growDelay = 0.65 + eventGroupCount * 0.12;
    eventGroupCount += 1;

    const anchor = new THREE.Mesh(
      new THREE.SphereGeometry(0.08 + event.intensity * 0.08, 20, 18),
      createEventMaterial(THREE, event)
    );
    anchor.position.set(event.orbitRadius, event.orbitHeight, 0);
    anchor.userData.dstRole = 'event-anchor';
    anchor.userData.pulseSpeed = event.pulseSpeed;
    eventGroup.add(anchor);

    const tetherCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0, 0),
      new THREE.Vector3(event.orbitRadius * 0.28, event.orbitHeight * 0.8 + 0.6, -event.orbitRadius * 0.18),
      new THREE.Vector3(event.orbitRadius * 0.72, event.orbitHeight * 0.9, event.orbitRadius * 0.12),
      new THREE.Vector3(event.orbitRadius, event.orbitHeight, 0),
    ]);
    const tether = new THREE.Mesh(
      new THREE.TubeGeometry(tetherCurve, device.lowPower ? 32 : 64, 0.012 + event.intensity * 0.01, 8, false),
      new THREE.MeshBasicMaterial({
        color: event.accent,
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending,
      })
    );
    tether.userData.dstRole = 'event-thread';
    eventGroup.add(tether);

    let artifact;
    if (event.kind === 'helix') {
      class SoulHelixCurve extends THREE.Curve {
        getPoint(t, target = new THREE.Vector3()) {
          const angle = t * Math.PI * 2 * event.turns;
          const radius = event.scale * (0.82 + Math.sin(t * Math.PI * 4) * 0.1);
          const x = Math.cos(angle) * radius;
          const y = (t - 0.5) * event.heightSpan;
          const z = Math.sin(angle) * radius;
          return target.set(x, y, z);
        }
      }
      artifact = new THREE.Mesh(
        new THREE.TubeGeometry(new SoulHelixCurve(), device.lowPower ? 64 : 120, event.tubeRadius, 14, false),
        createEventMaterial(THREE, event)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
    } else if (event.kind === 'mobius') {
      artifact = new THREE.Mesh(
        new ParametricGeometry(createMobiusFunction(event), device.lowPower ? 46 : 72, device.lowPower ? 10 : 16),
        createEventMaterial(THREE, event, true)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
      artifact.scale.setScalar(0.7 + event.intensity * 0.2);
    } else if (event.kind === 'torus') {
      artifact = new THREE.Mesh(
        new THREE.TorusGeometry(event.scale * 0.9, event.tubeRadius * 1.2, 18, 160),
        createEventMaterial(THREE, event)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
      artifact.rotation.x = Math.PI / 2;
    } else {
      artifact = new THREE.Mesh(
        new THREE.SphereGeometry(event.scale * 0.82, 28, 24),
        createEventMaterial(THREE, event)
      );
      artifact.position.set(event.orbitRadius, event.orbitHeight, 0);
    }

    artifact.userData.dstRole = 'event-artifact';
    artifact.userData.spinSpeed = event.spinSpeed * 1.6;
    artifact.userData.pulseSpeed = event.pulseSpeed;
    eventGroup.add(artifact);
    eventGroup.rotation.y = event.angle;
    group.add(eventGroup);
  });

  if (includeParticles) {
    group.add(createSoulParticleField(THREE, blueprint, { budget: device.particleBudget, rendererType }));
  }

  return group;
}
