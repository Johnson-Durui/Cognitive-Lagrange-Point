/**
 * 神魂拓扑模板
 */

export function buildTemplate() {
  return `
    <section class="dst-shell" role="dialog" aria-modal="true" aria-label="Divine Soul Topology">
      <canvas class="dst-canvas" data-dst-canvas></canvas>
      <header class="dst-topbar">
        <div>
          <div class="dst-kicker">Divine Soul Topology</div>
          <h2>神魂拓扑</h2>
          <p data-dst-question></p>
        </div>
        <div class="dst-mode-switch">
          <button type="button" data-dst-close>理性模式</button>
          <button type="button" data-dst-open-quantum>量子诗意模式</button>
          <button type="button" class="is-active" data-dst-current>神魂拓扑</button>
        </div>
      </header>
      <aside class="dst-panel">
        <section class="dst-section">
          <div class="dst-section-head">
            <span>灵魂输入</span>
            <small data-dst-save-copy>等待生成</small>
          </div>
          <textarea class="dst-story" data-dst-story placeholder="输入人生关键节点、遗憾、转折、声音片段、一个表情背后的故事，或任何你不曾说出口的私密叙事。"></textarea>
          <div class="dst-context" data-dst-context></div>
          <div class="dst-voice-row">
            <button type="button" class="dst-voice-button" data-dst-voice-toggle>开始语音录入</button>
            <button type="button" class="dst-voice-button" data-dst-voice-clear>清空语音</button>
          </div>
          <div class="dst-voice-meter"><span data-dst-voice-meter></span></div>
          <div class="dst-voice-status" data-dst-voice-status>浏览器支持时会本地转写语音，同时提取声纹能量，不上传音频。</div>
          <div class="dst-transcript" data-dst-transcript>还没有语音片段。</div>
          <input type="file" accept="image/*" multiple hidden data-dst-photo-input>
          <div class="dst-photo-row">
            <button type="button" class="dst-photo-trigger" data-dst-photo-trigger>上传照片</button>
            <div class="dst-renderer-copy" data-dst-photo-copy>还没有照片输入。</div>
          </div>
          <div class="dst-photo-grid" data-dst-photo-grid></div>
          <button type="button" class="dst-primary" data-dst-generate>生成神魂拓扑</button>
        </section>

        <section class="dst-section">
          <div class="dst-section-head">
            <span>策展说明</span>
            <small>把决策上下文翻译成可观看的人话</small>
          </div>
          <div class="dst-curation-grid" data-dst-curation></div>
        </section>

        <section class="dst-section">
          <div class="dst-section-head">
            <span>神性滤镜</span>
            <small>切换雕塑的光学人格</small>
          </div>
          <div class="dst-filter-list">
            <button type="button" class="dst-filter-button" data-dst-filter="essence">灵魂本质</button>
            <button type="button" class="dst-filter-button" data-dst-filter="destiny">命运拓扑</button>
            <button type="button" class="dst-filter-button" data-dst-filter="existential">存在主义模式</button>
          </div>
        </section>

        <section class="dst-section">
          <div class="dst-section-head">
            <span>交互与导出</span>
            <small data-dst-renderer-copy>准备渲染器...</small>
          </div>
          <div class="dst-tool-grid">
            <button type="button" class="dst-tool-button" data-dst-flight-toggle>开启自由飞行</button>
            <button type="button" class="dst-tool-button" data-dst-frame>回到雕塑中心</button>
            <button type="button" class="dst-tool-button" data-dst-export="4k">导出 4K 艺术图</button>
            <button type="button" class="dst-tool-button" data-dst-export="8k">导出 8K 艺术图</button>
            <button type="button" class="dst-tool-button" data-dst-export="video">导出 10 秒视频</button>
            <button type="button" class="dst-tool-button" data-dst-export="glb">导出 GLB</button>
          </div>
        </section>

        <section class="dst-section">
          <div class="dst-section-head">
            <span>演化状态</span>
            <small>IndexedDB 自动续写</small>
          </div>
          <div class="dst-stats" data-dst-stats></div>
        </section>
      </aside>

      <div class="dst-empty-state" data-dst-empty-state>
        <div class="dst-empty-preview" aria-hidden="true">
          <div class="dst-preview-glow"></div>
          <div class="dst-preview-shell"></div>
          <div class="dst-preview-ring"></div>
          <div class="dst-preview-core"></div>
          <div class="dst-preview-breath"></div>
          <div class="dst-preview-helix">
            <span class="dst-preview-node"></span>
            <span class="dst-preview-node"></span>
            <span class="dst-preview-node"></span>
            <span class="dst-preview-node"></span>
            <span class="dst-preview-node"></span>
            <span class="dst-preview-node"></span>
          </div>
          <div class="dst-empty-caption">
            <span>WARMING THE SCULPTURE</span>
            <span>GOLD / SILVER / CYAN / VIOLET</span>
          </div>
        </div>
        <div class="dst-empty-copy">
          <strong>神魂拓扑尚未显现</strong>
          <p>先输入一段关键人生叙事，或直接用当前决策上下文生成。</p>
          <p>预热中的几何体会先轻微呼吸，等你确认输入后，再长成真正的球体、环面、螺旋与拓扑曲面。</p>
        </div>
      </div>

      <div class="dst-ritual" data-dst-ritual hidden>
        <div class="dst-ritual-card">
          <div class="dst-ritual-kicker">Soul Generation Ritual</div>
          <div class="dst-ritual-phase" data-dst-ritual-phase>折叠叙事</div>
          <div class="dst-ritual-copy" data-dst-ritual-copy>把人生节点、照片光谱与声音起伏压缩成可生成的神性结构。</div>
          <div class="dst-ritual-track"><span class="dst-ritual-fill" data-dst-ritual-fill></span></div>
          <div class="dst-ritual-meta">
            <span data-dst-ritual-step>Phase 1 / 4</span>
            <span data-dst-ritual-mark>黑金展厅正在点亮</span>
          </div>
        </div>
      </div>

      <footer class="dst-footer">
        <span>拖拽旋转 · 滚轮缩放 · 右键平移 · F 键自由飞行</span>
        <span data-dst-footer-copy>黑金空间正在等待你的神性结构。</span>
      </footer>
    </section>
  `;
}
