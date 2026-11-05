import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const [capabilitySource, controllerSource, panelsSource] = await Promise.all([
  readFile('frontend/modules/art-experience/capability.js', 'utf8'),
  readFile('frontend/modules/divine-soul-topology/controller.js', 'utf8'),
  readFile('frontend/modules/divine-soul-topology/ui/panels.js', 'utf8'),
]);

assert.match(capabilitySource, /supportsMediaRecorder/, 'capability matrix should track MediaRecorder');
assert.match(capabilitySource, /supportsSpeechRecognition/, 'capability matrix should track speech recognition');
assert.match(capabilitySource, /canRecordVideo/, 'capability matrix should expose video export capability');
assert.match(capabilitySource, /canUseVoiceTranscript/, 'capability matrix should expose transcript capability');
assert.match(capabilitySource, /__CLP_CAPABILITY_OVERRIDE__/, 'capability matrix should support test override hooks');

assert.match(controllerSource, /detectArtExperienceCapability/, 'controller should consume capability detection');
assert.match(panelsSource, /videoButton\.disabled = !capability\.canRecordVideo/, 'UI should disable video export when unavailable');
assert.match(panelsSource, /voiceToggle\.disabled = !capability\.canUseVoiceCapture/, 'UI should disable voice capture when unavailable');
assert.match(panelsSource, /不支持实时转写|麦克风输入/, 'UI should provide clear degradation copy');

console.log('Divine Soul Topology capability static smoke passed.');
