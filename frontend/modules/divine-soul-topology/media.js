/**
 * 神魂拓扑媒体输入
 */

import { showToast } from '../utils.js';
import { clamp, compactText, hashString, loadImageFromDataUrl, readFileAsDataUrl } from '../art-experience/common.js';
import { renderCuratorialNotes, renderPhotoGrid, renderStats, renderVoiceTranscript } from './ui/panels.js';

export async function processPhotoFile(file) {
  const dataUrl = await readFileAsDataUrl(file);
  const image = await loadImageFromDataUrl(dataUrl);
  const maxEdge = 420;
  const scale = Math.min(1, maxEdge / Math.max(image.width, image.height));
  const width = Math.max(1, Math.round(image.width * scale));
  const height = Math.max(1, Math.round(image.height * scale));
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(image, 0, 0, width, height);
  const pixels = ctx.getImageData(0, 0, width, height).data;
  let brightness = 0;
  let variance = 0;
  let saturation = 0;
  let warmth = 0;
  const step = Math.max(4, Math.floor((width * height) / 2400));
  let count = 0;
  for (let i = 0; i < pixels.length; i += 4 * step) {
    const r = pixels[i];
    const g = pixels[i + 1];
    const b = pixels[i + 2];
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
    brightness += lum;
    variance += lum * lum;
    saturation += max === 0 ? 0 : (max - min) / max;
    warmth += (r - b + 255) / 510;
    count += 1;
  }
  const normalizedBrightness = count ? brightness / count : 0.5;
  const contrast = count ? Math.sqrt(Math.max((variance / count) - (normalizedBrightness ** 2), 0)) : 0.3;
  const normalizedSaturation = count ? saturation / count : 0.35;
  const normalizedWarmth = count ? warmth / count : 0.5;
  const samplePoints = [
    [0.18, 0.22],
    [0.8, 0.24],
    [0.5, 0.52],
    [0.26, 0.82],
    [0.76, 0.78],
  ];
  const palette = samplePoints.map(([x, y]) => {
    const px = clamp(Math.floor(width * x), 0, width - 1);
    const py = clamp(Math.floor(height * y), 0, height - 1);
    const idx = (py * width + px) * 4;
    const r = pixels[idx];
    const g = pixels[idx + 1];
    const b = pixels[idx + 2];
    return `#${[r, g, b].map((value) => value.toString(16).padStart(2, '0')).join('')}`;
  });
  return {
    id: `photo-${hashString(`${file.name}:${file.size}:${Date.now()}`).toString(36)}`,
    name: file.name,
    dataUrl: canvas.toDataURL('image/jpeg', 0.84),
    width,
    height,
    metrics: {
      brightness: clamp(normalizedBrightness, 0, 1),
      contrast: clamp(contrast * 2.8, 0, 1),
      saturation: clamp(normalizedSaturation, 0, 1),
      warmth: clamp(normalizedWarmth, 0, 1),
      palette,
    },
  };
}

export async function handlePhotoInput(controller, event) {
  const files = Array.from(event.currentTarget.files || []);
  if (!files.length) return;
  controller.updateFooter('正在分析照片的亮度、对比、色温与隐性光谱...');
  const processed = [];
  for (const file of files.slice(0, 4)) {
    try {
      processed.push(await processPhotoFile(file));
    } catch (error) {
      console.warn('Photo processing failed:', error);
    }
  }
  controller.photos = [...controller.photos, ...processed].slice(0, 6);
  renderPhotoGrid(controller);
  renderCuratorialNotes(controller);
  renderStats(controller);
  event.currentTarget.value = '';
  await controller.saveState({ photosUpdatedAt: new Date().toISOString() });
}

export async function clearVoiceInputs(controller) {
  if (controller.voiceActive) {
    await stopVoiceCapture(controller, { keepTranscript: false });
  }
  controller.voiceTranscript = '';
  controller.voiceRecordings = [];
  controller.voiceMeterLevel = 0;
  controller.root.querySelector('[data-dst-voice-meter]').style.width = '0%';
  controller.root.querySelector('[data-dst-voice-status]').textContent = '语音输入已清空。';
  renderVoiceTranscript(controller);
  renderCuratorialNotes(controller);
  renderStats(controller);
  await controller.saveState({ voiceClearedAt: new Date().toISOString() });
}

export async function toggleVoiceCapture(controller) {
  if (controller.voiceActive) {
    await stopVoiceCapture(controller);
    return;
  }
  await startVoiceCapture(controller);
}

export async function startVoiceCapture(controller) {
  if (!controller.capability.canUseVoiceCapture) {
    showToast('当前浏览器不支持语音录入。', 'warning', 2600);
    return;
  }
  try {
    controller.voiceStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    controller.voiceChunks = [];
    controller.voiceStartedAt = performance.now();
    controller.voiceAccumulatedEnergy = 0;
    controller.voiceSamples = 0;
    controller.voiceActive = true;

    if (controller.capability.supportsMediaRecorder) {
      controller.voiceRecorder = new MediaRecorder(controller.voiceStream);
      controller.voiceRecorder.ondataavailable = (event) => {
        if (event.data?.size) controller.voiceChunks.push(event.data);
      };
      controller.voiceRecorder.start(200);
    }

    const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (RecognitionClass) {
      controller.voiceRecognition = new RecognitionClass();
      controller.voiceRecognition.lang = 'zh-CN';
      controller.voiceRecognition.continuous = true;
      controller.voiceRecognition.interimResults = true;
      controller.voiceRecognition.onresult = (event) => {
        let finalText = '';
        let interimText = '';
        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const fragment = event.results[i][0]?.transcript || '';
          if (event.results[i].isFinal) finalText += fragment;
          else interimText += fragment;
        }
        if (finalText) {
          controller.voiceTranscript = compactText(`${controller.voiceTranscript} ${finalText}`.trim());
        }
        renderVoiceTranscript(controller);
        const status = interimText
          ? `正在转写：${compactText(interimText).slice(0, 26)}`
          : '正在聆听你的声音与停顿。';
        controller.root.querySelector('[data-dst-voice-status]').textContent = status;
      };
      controller.voiceRecognition.onerror = () => {
        controller.root.querySelector('[data-dst-voice-status]').textContent = '浏览器转写不可用，仍会保留声纹能量用于雕塑生成。';
      };
      controller.voiceRecognition.start();
    } else {
      controller.root.querySelector('[data-dst-voice-status]').textContent = '浏览器不支持实时转写，将仅提取声纹能量。';
    }

    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      controller.voiceAudioContext = new AudioContextClass();
      const source = controller.voiceAudioContext.createMediaStreamSource(controller.voiceStream);
      controller.voiceAnalyser = controller.voiceAudioContext.createAnalyser();
      controller.voiceAnalyser.fftSize = 512;
      controller.voiceData = new Uint8Array(controller.voiceAnalyser.fftSize);
      source.connect(controller.voiceAnalyser);
    }

    controller.root.querySelector('[data-dst-voice-toggle]').textContent = '停止语音录入';
    controller.root.querySelector('[data-dst-voice-status]').textContent = '语音录入已开启，声纹会实时写入神魂参数。';
    controller.updateFooter('语音输入已开启，雕塑正在监听声音的起伏。');
    sampleVoiceMeter(controller);
  } catch (error) {
    console.warn('Voice capture failed:', error);
    showToast(`语音录入失败：${error.message || error}`, 'warning', 3200);
    await stopVoiceCapture(controller, { keepTranscript: true });
  }
}

function sampleVoiceMeter(controller) {
  if (!controller.voiceAnalyser || !controller.voiceData) return;
  controller.voiceAnalyser.getByteTimeDomainData(controller.voiceData);
  let energy = 0;
  for (let i = 0; i < controller.voiceData.length; i += 1) {
    const normalized = (controller.voiceData[i] - 128) / 128;
    energy += normalized * normalized;
  }
  const rms = Math.sqrt(energy / controller.voiceData.length);
  controller.voiceMeterLevel = clamp(rms * 6.5, 0, 1);
  controller.voiceAccumulatedEnergy += controller.voiceMeterLevel;
  controller.voiceSamples += 1;
  const meter = controller.root?.querySelector('[data-dst-voice-meter]');
  if (meter) meter.style.width = `${Math.round(controller.voiceMeterLevel * 100)}%`;
  controller.voiceFrame = requestAnimationFrame(() => sampleVoiceMeter(controller));
}

export async function stopVoiceCapture(controller, { keepTranscript = true } = {}) {
  controller.voiceActive = false;
  cancelAnimationFrame(controller.voiceFrame);
  controller.voiceFrame = 0;

  if (controller.voiceRecognition) {
    try {
      controller.voiceRecognition.stop();
    } catch (error) {
      console.warn('Voice recognition stop failed:', error);
    }
    controller.voiceRecognition = null;
  }

  const recorder = controller.voiceRecorder;
  controller.voiceRecorder = null;
  if (recorder) {
    await new Promise((resolve) => {
      recorder.onstop = () => resolve();
      try {
        recorder.stop();
      } catch (error) {
        resolve();
      }
    });
  }

  const duration = (performance.now() - controller.voiceStartedAt) / 1000;
  const averageEnergy = controller.voiceSamples
    ? clamp(controller.voiceAccumulatedEnergy / controller.voiceSamples, 0, 1)
    : clamp(controller.voiceMeterLevel, 0.18, 0.32);
  if (keepTranscript && (duration > 0.4 || controller.voiceTranscript)) {
    controller.voiceRecordings = [
      ...controller.voiceRecordings,
      {
        id: `voice-${Date.now()}`,
        duration: Math.round(duration * 10) / 10,
        energy: averageEnergy,
      },
    ].slice(-6);
  }

  controller.voiceStream?.getTracks?.().forEach((track) => track.stop());
  controller.voiceStream = null;
  controller.voiceAudioContext?.close?.();
  controller.voiceAudioContext = null;
  controller.voiceAnalyser = null;
  controller.voiceData = null;
  controller.voiceChunks = [];
  controller.voiceMeterLevel = 0;

  const meter = controller.root?.querySelector('[data-dst-voice-meter]');
  if (meter) meter.style.width = '0%';
  const toggle = controller.root?.querySelector('[data-dst-voice-toggle]');
  if (toggle) toggle.textContent = '开始语音录入';
  const status = controller.root?.querySelector('[data-dst-voice-status]');
  if (status) status.textContent = keepTranscript
    ? '语音录入已结束，转写与声纹能量已保留在当前拓扑状态中。'
    : '语音录入已取消。';
  renderVoiceTranscript(controller);
  renderCuratorialNotes(controller);
  renderStats(controller);
  await controller.saveState({ voiceUpdatedAt: new Date().toISOString() });
}
