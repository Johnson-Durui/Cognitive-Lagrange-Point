/**
 * 神魂拓扑动画层
 */

import { clamp, safeNumber } from '../../art-experience/common.js';

export function seedGrowthAnimation(controller, animated) {
  if (!controller.sculptureGroup || !controller.THREE) return;
  controller.growthAnimation = animated ? { startedAt: performance.now() } : null;
  controller.sculptureGroup.traverse((child) => {
    const target = child.userData.dstTargetScale || child.scale.clone();
    child.userData.dstTargetScale = target;
    if (!animated) {
      child.scale.copy(target);
      return;
    }
    let delay = 0;
    if (child.userData.dstRole === 'core') delay = 0.08;
    if (child.userData.dstRole === 'topology-shell') delay = 0.22;
    if (child.userData.dstRole === 'aura') delay = 0.32;
    if (child.userData.dstRole === 'ring') delay = 0.42;
    if (child.userData.dstRole === 'event-group') delay = child.userData.growDelay || 0.72;
    if (child.parent?.userData?.dstRole === 'event-group' && child.userData.dstRole !== 'event-group') {
      delay = (child.parent.userData.growDelay || 0.72) + 0.08;
    }
    child.userData.dstGrowDelay = delay;
    if (child.userData.dstRole !== 'background-stars' && child.userData.dstRole !== 'particles') {
      child.scale.copy(target.clone().multiplyScalar(0.001));
    }
  });
}

export function updateSceneFrame(controller, time) {
  if (!controller.scene || !controller.camera || !controller.renderer) return;
  const profile = controller.getFilterProfile();
  const breath = controller.blueprint?.motion?.breath || 0.42;
  const drift = controller.blueprint?.motion?.drift || 0.4;
  if (controller.backgroundStars) {
    controller.backgroundStars.rotation.y += 0.00016;
    controller.backgroundStars.rotation.x = Math.sin(time * 0.06) * 0.04;
  }
  if (controller.sculptureGroup) {
    controller.sculptureGroup.rotation.y += 0.0012 + drift * 0.0006;
    controller.sculptureGroup.traverse((child) => {
      const role = child.userData.dstRole;
      if (role === 'core') {
        const pulse = 1 + Math.sin(time * child.userData.pulseSpeed) * (0.05 + breath * 0.02);
        child.scale.setScalar(pulse);
        child.rotation.y += 0.004;
      } else if (role === 'topology-shell') {
        child.rotation.x = Math.sin(time * 0.22) * 0.16;
        child.rotation.y += child.userData.spinSpeed * (profile.particleFlow * 0.9);
      } else if (role === 'aura') {
        const auraPulse = 1 + Math.sin(time * 0.34) * 0.08;
        child.scale.setScalar(auraPulse);
      } else if (role === 'ring') {
        const wave = 1 + Math.sin(time * child.userData.waveSpeed) * 0.03;
        child.scale.setScalar(wave);
        child.rotation.z += 0.0018 * profile.particleFlow;
      } else if (role === 'event-group') {
        const angle = child.userData.baseAngle + time * child.userData.spinSpeed * profile.particleFlow;
        child.rotation.y = angle;
      } else if (role === 'event-artifact' || role === 'event-anchor') {
        const pulse = 1 + Math.sin(time * child.userData.pulseSpeed) * 0.08;
        child.scale.setScalar(pulse);
        child.rotation.y += child.userData.spinSpeed || 0.003;
      } else if (role === 'particles') {
        child.rotation.y += child.userData.spinSpeed * profile.particleFlow;
        if (child.userData.dstUniforms) {
          child.userData.dstUniforms.uTime.value = time;
          child.userData.dstUniforms.uFlow.value = profile.particleFlow;
          child.userData.dstUniforms.uPixelRatio.value = controller.device.pixelRatio;
        } else if (child.material) {
          child.material.opacity = 0.44 + profile.particleFlow * 0.1;
        }
      }
    });
  }

  if (controller.growthAnimation) {
    const elapsed = (performance.now() - controller.growthAnimation.startedAt) / 1000;
    let pending = false;
    controller.sculptureGroup?.traverse((child) => {
      const target = child.userData.dstTargetScale;
      if (!target || child.userData.dstRole === 'background-stars' || child.userData.dstRole === 'particles') return;
      const delay = safeNumber(child.userData.dstGrowDelay, 0);
      const normalized = clamp((elapsed - delay) / 0.9, 0, 1);
      const eased = 1 - ((1 - normalized) ** 3);
      if (normalized < 1) pending = true;
      child.scale.copy(target.clone().multiplyScalar(0.001 + eased * 0.999));
    });
    if (!pending) controller.growthAnimation = null;
  }

  if (controller.freeFlightEnabled) {
    const forward = new controller.THREE.Vector3(
      Math.sin(controller.freeFlightLook.yaw) * Math.cos(controller.freeFlightLook.pitch),
      Math.sin(controller.freeFlightLook.pitch),
      Math.cos(controller.freeFlightLook.yaw) * Math.cos(controller.freeFlightLook.pitch),
    ).normalize();
    const right = new controller.THREE.Vector3().crossVectors(forward, new controller.THREE.Vector3(0, 1, 0)).normalize();
    const up = new controller.THREE.Vector3(0, 1, 0);
    const velocity = new controller.THREE.Vector3();
    const speed = controller.keyState.shift ? 0.28 : 0.14;
    if (controller.keyState.w) velocity.add(forward);
    if (controller.keyState.s) velocity.sub(forward);
    if (controller.keyState.a) velocity.sub(right);
    if (controller.keyState.d) velocity.add(right);
    if (controller.keyState.q) velocity.sub(up);
    if (controller.keyState.e) velocity.add(up);
    if (velocity.lengthSq() > 0) {
      velocity.normalize().multiplyScalar(speed);
      controller.camera.position.add(velocity);
    }
    controller.camera.lookAt(controller.camera.position.clone().add(forward));
  }

  if (controller.videoCapture) {
    const progress = ((performance.now() - controller.videoCapture.startedAt) % controller.videoCapture.duration) / controller.videoCapture.duration;
    const angle = progress * Math.PI * 2;
    const bob = Math.sin(progress * Math.PI * 4) * 0.26;
    controller.camera.position.set(
      controller.videoCapture.center.x + Math.cos(angle) * controller.videoCapture.radius,
      controller.videoCapture.center.y + controller.videoCapture.elevation + bob,
      controller.videoCapture.center.z + Math.sin(angle) * controller.videoCapture.radius,
    );
    controller.controls.target.copy(controller.videoCapture.center);
  }

  if (!controller.freeFlightEnabled) {
    controller.controls?.update();
  }
  if (controller.composer) controller.composer.render();
  else controller.renderer.render(controller.scene, controller.camera);
}
