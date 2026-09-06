/**
 * 前端能力探测
 */

export function detectArtExperienceCapability() {
  const canvas = document.createElement('canvas');
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
  const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
  const supportsUserMedia = Boolean(navigator.mediaDevices?.getUserMedia);
  const supportsMediaRecorder = typeof window.MediaRecorder !== 'undefined';
  const supportsSpeechRecognition = Boolean(SpeechRecognitionClass);
  const supportsIndexedDb = Boolean(window.indexedDB);
  const supportsCanvasCaptureStream = Boolean(canvas.captureStream);
  const supportsWebGPU = Boolean(navigator.gpu);
  const detected = {
    supportsWebGL: Boolean(gl),
    supportsWebGPU,
    supportsUserMedia,
    supportsMediaRecorder,
    supportsSpeechRecognition,
    supportsIndexedDb,
    supportsCanvasCaptureStream,
    canRecordVideo: supportsMediaRecorder && supportsCanvasCaptureStream,
    canUseVoiceTranscript: supportsUserMedia && supportsSpeechRecognition,
    canUseVoiceCapture: supportsUserMedia,
  };
  const override = typeof window !== 'undefined' ? window.__CLP_CAPABILITY_OVERRIDE__ : null;
  return override && typeof override === 'object'
    ? { ...detected, ...override }
    : detected;
}
