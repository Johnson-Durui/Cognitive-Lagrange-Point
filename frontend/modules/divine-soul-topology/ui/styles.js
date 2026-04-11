/**
 * 神魂拓扑样式注入
 */

export function ensureStyles() {
  if (document.getElementById('dst-style')) return;
  const style = document.createElement('style');
  style.id = 'dst-style';
  style.textContent = `
    .dst-root { --dst-gold:#e5cb86; --dst-silver:#dde4ef; --dst-cyan:#64e8dd; --dst-violet:#9d71ff; position:fixed; inset:0; z-index:10000; color:#f4f2ee; font-family:"Noto Serif SC","Iowan Old Style","Songti SC",serif; }
    .dst-root.is-free-flight .dst-canvas { cursor:grab; }
    .dst-root.is-free-flight .dst-topbar,.dst-root.is-free-flight .dst-panel { filter:saturate(1.04); }
    .dst-root.is-free-flight .dst-panel { border-color:rgba(100,232,221,0.16); box-shadow:0 26px 80px rgba(0,0,0,0.46),0 0 32px rgba(100,232,221,0.08); }
    .dst-shell { position:relative; width:100%; height:100%; overflow:hidden; background:radial-gradient(circle at 50% 40%, rgba(74,52,119,0.24), transparent 42%),radial-gradient(circle at 15% 22%, rgba(229,203,134,0.14), transparent 26%),radial-gradient(circle at 82% 18%, rgba(90,234,223,0.16), transparent 24%),linear-gradient(180deg,#030304 0%,#000 100%); isolation:isolate; }
    .dst-shell::before { content:""; position:absolute; inset:0; pointer-events:none; background:linear-gradient(135deg, rgba(255,255,255,0.04), transparent 42%),radial-gradient(circle at 50% 55%, rgba(157,113,255,0.12), transparent 34%); mix-blend-mode:screen; opacity:0.9; }
    .dst-canvas { position:absolute; inset:0; width:100%; height:100%; display:block; touch-action:none; }
    .dst-topbar { position:absolute; z-index:6; left:24px; right:24px; top:22px; display:flex; justify-content:space-between; align-items:flex-start; gap:20px; pointer-events:none; }
    .dst-kicker { color:var(--dst-gold); letter-spacing:0.24em; font-size:11px; text-transform:uppercase; }
    .dst-topbar h2 { margin:6px 0 8px; font-size:clamp(30px,4vw,56px); line-height:0.95; letter-spacing:0.08em; text-shadow:0 0 28px rgba(229,203,134,0.22); }
    .dst-topbar p { margin:0; max-width:min(640px,60vw); color:rgba(244,242,238,0.7); font-size:13px; letter-spacing:0.04em; line-height:1.55; }
    .dst-mode-switch { pointer-events:auto; display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; padding:8px; border-radius:999px; border:1px solid rgba(255,255,255,0.1); background:rgba(6,8,12,0.66); backdrop-filter:blur(18px); }
    .dst-mode-switch button,.dst-primary,.dst-filter-button,.dst-tool-button,.dst-photo-trigger,.dst-voice-button,.dst-photo-remove { appearance:none; -webkit-appearance:none; border:1px solid rgba(255,255,255,0.12); border-radius:999px; background:rgba(255,255,255,0.04); color:#f4f2ee; font:inherit; cursor:pointer; transition:transform 0.18s ease,border-color 0.18s ease,background 0.18s ease,box-shadow 0.18s ease; }
    .dst-mode-switch button:hover,.dst-primary:hover,.dst-filter-button:hover,.dst-tool-button:hover,.dst-photo-trigger:hover,.dst-voice-button:hover,.dst-photo-remove:hover { transform:translateY(-1px); border-color:rgba(229,203,134,0.46); background:rgba(255,255,255,0.09); }
    .dst-mode-switch button { padding:10px 14px; }
    .dst-mode-switch .is-active { background:linear-gradient(135deg, rgba(229,203,134,0.18), rgba(100,232,221,0.18)); border-color:rgba(229,203,134,0.44); box-shadow:0 0 18px rgba(229,203,134,0.14); }
    .dst-panel { position:absolute; z-index:5; right:18px; top:136px; width:min(420px, calc(100vw - 32px)); max-height:calc(100vh - 164px); overflow:auto; display:grid; gap:12px; align-content:start; padding:16px; border-radius:26px; border:1px solid rgba(255,255,255,0.12); background:linear-gradient(180deg, rgba(8,9,13,0.84), rgba(8,8,10,0.72)); box-shadow:0 30px 90px rgba(0,0,0,0.44); backdrop-filter:blur(18px); scrollbar-width:thin; scrollbar-color:rgba(229,203,134,0.42) rgba(255,255,255,0.06); }
    .dst-panel::-webkit-scrollbar { width:8px; }
    .dst-panel::-webkit-scrollbar-thumb { background:rgba(229,203,134,0.42); border-radius:999px; }
    .dst-section { display:grid; gap:10px; padding:14px; border-radius:20px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); }
    .dst-section-head { display:flex; justify-content:space-between; gap:10px; align-items:center; font-size:12px; letter-spacing:0.08em; text-transform:uppercase; color:var(--dst-gold); }
    .dst-section-head small { color:rgba(244,242,238,0.56); letter-spacing:0; text-transform:none; font-size:11px; }
    .dst-story { min-height:140px; resize:vertical; border-radius:18px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); color:#f5f1ec; padding:14px; font:inherit; line-height:1.72; outline:none; }
    .dst-story:focus { border-color:rgba(229,203,134,0.34); box-shadow:0 0 0 1px rgba(229,203,134,0.18); }
    .dst-context { display:grid; grid-template-columns:1fr; gap:8px; }
    .dst-context-chip { min-width:0; padding:10px 12px; border-radius:14px; font-size:11px; line-height:1.55; color:rgba(244,242,238,0.76); border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }
    .dst-curation-grid { display:grid; gap:10px; }
    .dst-curation-card { padding:12px 13px; border-radius:16px; border:1px solid rgba(255,255,255,0.07); background:linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.02)),radial-gradient(circle at 100% 0%, rgba(229,203,134,0.08), transparent 45%); }
    .dst-curation-eyebrow { color:rgba(229,203,134,0.86); font-size:10px; letter-spacing:0.14em; text-transform:uppercase; }
    .dst-curation-title { margin-top:6px; font-size:14px; line-height:1.45; color:#f9f5ef; }
    .dst-curation-body { margin-top:5px; font-size:12px; line-height:1.62; color:rgba(244,242,238,0.66); }
    .dst-voice-row,.dst-photo-row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
    .dst-voice-button,.dst-photo-trigger,.dst-primary { padding:10px 14px; }
    .dst-primary { background:linear-gradient(135deg, rgba(229,203,134,0.24), rgba(100,232,221,0.14)); border-color:rgba(229,203,134,0.4); box-shadow:0 0 20px rgba(229,203,134,0.12); }
    .dst-voice-meter { position:relative; width:100%; height:8px; border-radius:999px; overflow:hidden; background:rgba(255,255,255,0.06); }
    .dst-voice-meter span { display:block; height:100%; width:0%; background:linear-gradient(90deg, var(--dst-cyan), var(--dst-gold), var(--dst-violet)); box-shadow:0 0 16px rgba(100,232,221,0.22); transition:width 0.12s linear; }
    .dst-voice-status,.dst-save-copy,.dst-renderer-copy { font-size:12px; line-height:1.5; color:rgba(244,242,238,0.62); }
    .dst-transcript { min-height:48px; padding:12px; border-radius:16px; background:rgba(255,255,255,0.04); color:rgba(244,242,238,0.82); font-size:12px; line-height:1.6; }
    .dst-photo-grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:10px; }
    .dst-photo-card { position:relative; overflow:hidden; border-radius:18px; border:1px solid rgba(255,255,255,0.08); background:rgba(255,255,255,0.03); }
    .dst-photo-card img { width:100%; aspect-ratio:1/1; object-fit:cover; display:block; filter:saturate(0.92) contrast(1.02); }
    .dst-photo-meta { padding:9px 10px 11px; display:grid; gap:4px; font-size:11px; color:rgba(244,242,238,0.7); }
    .dst-photo-remove { position:absolute; top:8px; right:8px; width:30px; height:30px; display:grid; place-items:center; border-radius:999px; background:rgba(4,4,4,0.6); backdrop-filter:blur(8px); }
    .dst-filter-list,.dst-tool-grid { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:8px; }
    .dst-filter-button,.dst-tool-button { min-height:46px; padding:11px 12px; border-radius:16px; text-align:left; line-height:1.4; }
    .dst-filter-button.is-active { background:linear-gradient(135deg, rgba(229,203,134,0.2), rgba(157,113,255,0.16)); border-color:rgba(229,203,134,0.36); box-shadow:0 0 20px rgba(229,203,134,0.08); }
    .dst-stats { display:grid; grid-template-columns:repeat(2, minmax(0,1fr)); gap:8px; }
    .dst-stat { padding:12px; border-radius:16px; background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.06); }
    .dst-stat strong { display:block; margin-top:4px; font-size:18px; color:#fff; }
    .dst-empty-state { position:absolute; z-index:4; left:28px; bottom:28px; max-width:min(460px, calc(100vw - 56px)); padding:16px 18px; display:grid; gap:14px; border-radius:22px; border:1px solid rgba(255,255,255,0.08); background:rgba(6,8,12,0.62); backdrop-filter:blur(12px); color:rgba(244,242,238,0.82); line-height:1.72; }
    .dst-empty-state strong { display:block; color:var(--dst-gold); letter-spacing:0.08em; }
    .dst-empty-copy { display:grid; gap:6px; }
    .dst-empty-copy p { margin:0; }
    .dst-empty-preview { position:relative; height:132px; border-radius:18px; overflow:hidden; border:1px solid rgba(255,255,255,0.06); background:radial-gradient(circle at 50% 50%, rgba(100,232,221,0.14), transparent 24%),radial-gradient(circle at 50% 48%, rgba(229,203,134,0.16), transparent 34%),linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01)); box-shadow:inset 0 0 40px rgba(0,0,0,0.28); }
    .dst-empty-preview::before,.dst-empty-preview::after { content:""; position:absolute; inset:14px; border-radius:50%; border:1px solid rgba(229,203,134,0.08); filter:blur(0.3px); }
    .dst-empty-preview::after { inset:28px 78px; border-color:rgba(100,232,221,0.1); }
    .dst-preview-glow { position:absolute; left:50%; top:50%; width:124px; height:124px; transform:translate(-50%, -50%); border-radius:50%; background:radial-gradient(circle, rgba(157,113,255,0.26), rgba(100,232,221,0.08) 42%, transparent 72%); filter:blur(16px); animation:dst-preview-glow 4.8s ease-in-out infinite; }
    .dst-preview-shell,.dst-preview-ring,.dst-preview-ring::before,.dst-preview-ring::after { position:absolute; left:50%; top:50%; transform:translate(-50%, -50%); border-radius:50%; }
    .dst-preview-shell { width:98px; height:98px; border:1px solid rgba(244,242,238,0.08); box-shadow:inset 0 0 22px rgba(100,232,221,0.08),0 0 28px rgba(157,113,255,0.1); animation:dst-preview-shell 8s linear infinite; }
    .dst-preview-ring { width:116px; height:116px; border:1px solid rgba(229,203,134,0.18); animation:dst-preview-rotate 9s linear infinite; }
    .dst-preview-ring::before,.dst-preview-ring::after { content:""; inset:0; border:inherit; }
    .dst-preview-ring::before { transform:translate(-50%, -50%) rotateX(72deg); opacity:0.8; }
    .dst-preview-ring::after { transform:translate(-50%, -50%) rotateY(72deg); opacity:0.56; }
    .dst-preview-core { position:absolute; left:50%; top:50%; width:46px; height:46px; transform:translate(-50%, -50%); border-radius:50%; background:radial-gradient(circle,#fffdf7 0,#f1d18b 26%,#5f35d5 76%,rgba(95,53,213,0.08) 100%); box-shadow:0 0 28px rgba(229,203,134,0.34),0 0 46px rgba(100,232,221,0.16); animation:dst-preview-core 3.4s ease-in-out infinite; }
    .dst-preview-breath { position:absolute; left:50%; top:50%; width:76px; height:76px; transform:translate(-50%, -50%); border-radius:50%; border:1px solid rgba(100,232,221,0.18); animation:dst-preview-breath 3.4s ease-in-out infinite; }
    .dst-preview-helix { position:absolute; inset:0; animation:dst-preview-rotate-reverse 10s linear infinite; }
    .dst-preview-node { position:absolute; left:50%; top:50%; width:7px; height:7px; margin:-3.5px; border-radius:50%; background:radial-gradient(circle,#fffaf0 0,var(--dst-gold) 36%,rgba(255,255,255,0) 100%); box-shadow:0 0 12px rgba(229,203,134,0.28); animation:dst-preview-node 4.8s ease-in-out infinite; }
    .dst-preview-node:nth-child(1){transform:translate(-42px,-18px) scale(0.9);animation-delay:-0.2s;} .dst-preview-node:nth-child(2){transform:translate(38px,-12px) scale(0.72);animation-delay:-1.1s;background:radial-gradient(circle,#eefefc 0,var(--dst-cyan) 42%,rgba(255,255,255,0) 100%);} .dst-preview-node:nth-child(3){transform:translate(-30px,22px) scale(0.78);animation-delay:-2.1s;background:radial-gradient(circle,#f5efff 0,var(--dst-violet) 42%,rgba(255,255,255,0) 100%);} .dst-preview-node:nth-child(4){transform:translate(26px,24px) scale(1.02);animation-delay:-2.8s;} .dst-preview-node:nth-child(5){transform:translate(0,-36px) scale(0.64);animation-delay:-3.4s;background:radial-gradient(circle,#eefefc 0,var(--dst-cyan) 42%,rgba(255,255,255,0) 100%);} .dst-preview-node:nth-child(6){transform:translate(2px,38px) scale(0.82);animation-delay:-4.2s;background:radial-gradient(circle,#f5efff 0,var(--dst-violet) 42%,rgba(255,255,255,0) 100%);}
    .dst-empty-caption { position:absolute; left:12px; right:12px; bottom:10px; display:flex; justify-content:space-between; gap:10px; font-size:10px; letter-spacing:0.06em; text-transform:uppercase; color:rgba(244,242,238,0.42); }
    @keyframes dst-preview-core { 0%,100%{transform:translate(-50%,-50%) scale(0.92);} 45%{transform:translate(-50%,-50%) scale(1.08);} 70%{transform:translate(-50%,-50%) scale(0.98);} }
    @keyframes dst-preview-breath { 0%{transform:translate(-50%,-50%) scale(0.72);opacity:0.78;} 70%{transform:translate(-50%,-50%) scale(1.18);opacity:0;} 100%{opacity:0;} }
    @keyframes dst-preview-rotate { from{transform:translate(-50%,-50%) rotate(0deg);} to{transform:translate(-50%,-50%) rotate(360deg);} }
    @keyframes dst-preview-rotate-reverse { from{transform:rotate(360deg);} to{transform:rotate(0deg);} }
    @keyframes dst-preview-shell { 0%,100%{transform:translate(-50%,-50%) scale(0.96) rotate(0deg);} 50%{transform:translate(-50%,-50%) scale(1.04) rotate(180deg);} }
    @keyframes dst-preview-node { 0%,100%{opacity:0.48;filter:blur(0px);} 50%{opacity:1;filter:blur(0.2px);} }
    @keyframes dst-preview-glow { 0%,100%{opacity:0.72;transform:translate(-50%,-50%) scale(0.92);} 50%{opacity:1;transform:translate(-50%,-50%) scale(1.08);} }
    .dst-ritual[hidden] { display:none !important; }
    .dst-ritual { position:absolute; inset:0; z-index:7; display:grid; place-items:center; background:radial-gradient(circle at 50% 45%, rgba(229,203,134,0.08), rgba(2,3,8,0.92) 46%),rgba(3,4,8,0.72); backdrop-filter:blur(10px); }
    .dst-ritual-card { width:min(460px, calc(100vw - 34px)); padding:22px 24px; border-radius:24px; border:1px solid rgba(255,255,255,0.12); background:linear-gradient(180deg, rgba(8,8,11,0.9), rgba(6,8,14,0.74)); box-shadow:0 26px 84px rgba(0,0,0,0.46); }
    .dst-ritual-kicker { color:var(--dst-gold); letter-spacing:0.18em; font-size:10px; text-transform:uppercase; }
    .dst-ritual-phase { margin-top:10px; font-size:clamp(24px,3vw,34px); line-height:1.1; color:#f9f5ef; }
    .dst-ritual-copy { margin-top:10px; font-size:13px; line-height:1.75; color:rgba(244,242,238,0.7); }
    .dst-ritual-track { margin-top:16px; height:6px; border-radius:999px; overflow:hidden; background:rgba(255,255,255,0.08); }
    .dst-ritual-fill { display:block; width:8%; height:100%; border-radius:inherit; background:linear-gradient(90deg, var(--dst-gold), var(--dst-cyan), var(--dst-violet)); box-shadow:0 0 20px rgba(229,203,134,0.28); transition:width 0.45s ease; }
    .dst-ritual-meta { margin-top:10px; display:flex; justify-content:space-between; gap:12px; font-size:11px; color:rgba(244,242,238,0.48); }
    .dst-footer { position:absolute; left:28px; right:28px; bottom:18px; display:flex; justify-content:space-between; gap:12px; z-index:5; color:rgba(244,242,238,0.48); font-size:12px; pointer-events:none; }
    .dst-root.dst-exporting .dst-topbar,.dst-root.dst-exporting .dst-panel,.dst-root.dst-exporting .dst-footer,.dst-root.dst-exporting .dst-empty-state { opacity:0; pointer-events:none; }
    @media (max-width:760px){ .dst-topbar{left:14px;right:14px;top:14px;flex-direction:column;} .dst-topbar p{max-width:100%;} .dst-panel{left:12px;right:12px;top:auto;bottom:70px;width:auto;max-height:48vh;border-radius:22px;} .dst-empty-state{left:12px;right:12px;bottom:calc(48vh + 86px);max-width:none;} .dst-empty-preview{height:108px;} .dst-footer{left:14px;right:14px;bottom:10px;flex-direction:column;gap:4px;} }
  `;
  document.head.appendChild(style);
}
