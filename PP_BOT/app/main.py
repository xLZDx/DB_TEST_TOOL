"""FastAPI application entry point for PP_BOT."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, Response

from app.config import DATA_DIR, OUTPUT_DIR, PRESENTATION_DIR, SOURCE_DIR, settings
from app.models import AnalysisRequest, ArchitectureRequest, PresentationRequest, ResearchRequest
from app.routes.system import router as system_router
from app.services.analysis_service import analysis_service
from app.services.architecture_service import architecture_service
from app.services.presentation_service import presentation_service
from app.services.research_service import research_service

APP_DESCRIPTION = (
    "PP_BOT coordinates research, analysis, architecture, and presentation "
    "workflows across wiki and SharePoint sources."
)

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>__APP_NAME__ | Research to Presentation Studio</title>
  <style>
    :root {
      --bg: #07111f;
      --bg-soft: #0d1b2f;
      --panel: rgba(11, 22, 41, 0.82);
      --panel-border: rgba(120, 163, 255, 0.18);
      --text: #e9eefb;
      --muted: #9fb2d8;
      --accent: #7aa2ff;
      --accent-2: #74d4c1;
      --danger: #ff7b7b;
      --warning: #ffd166;
      --success: #6ee7b7;
      --shadow: 0 24px 72px rgba(0, 0, 0, 0.35);
      --radius: 22px;
      --radius-sm: 14px;
      --border: 1px solid var(--panel-border);
      --mono: "Cascadia Code", "Consolas", "Liberation Mono", monospace;
      --sans: Inter, "Segoe UI", Arial, sans-serif;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      font-family: var(--sans);
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(122,162,255,0.2), transparent 30%),
        radial-gradient(circle at top right, rgba(116,212,193,0.16), transparent 24%),
        linear-gradient(180deg, #050b15 0%, var(--bg) 100%);
      min-height: 100vh;
    }
    a { color: var(--accent); text-decoration: none; }
    button, input, textarea, select {
      font: inherit;
    }
    .shell {
      max-width: 1560px;
      margin: 0 auto;
      padding: 24px;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.75fr) minmax(320px, 0.85fr);
      gap: 20px;
      align-items: stretch;
      margin-bottom: 20px;
    }
    .hero-card, .panel, .side-panel {
      background: var(--panel);
      border: var(--border);
      border-radius: var(--radius);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
    }
    .hero-card {
      padding: 28px;
      overflow: hidden;
    }
    .brand-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 18px;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid rgba(122, 162, 255, 0.25);
      background: rgba(122, 162, 255, 0.1);
      color: var(--text);
      font-size: 0.9rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .badge-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(180deg, var(--accent), var(--accent-2));
      box-shadow: 0 0 0 5px rgba(122, 162, 255, 0.12);
    }
    h1, h2, h3, p { margin-top: 0; }
    h1 {
      font-size: clamp(2.1rem, 4vw, 3.6rem);
      line-height: 1.02;
      margin: 0 0 14px;
      letter-spacing: -0.04em;
    }
    .hero-copy {
      color: var(--muted);
      max-width: 960px;
      font-size: 1.03rem;
      line-height: 1.7;
      margin-bottom: 18px;
    }
    .hero-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .stat {
      padding: 16px;
      border-radius: 18px;
      border: 1px solid rgba(122, 162, 255, 0.14);
      background: rgba(255, 255, 255, 0.03);
    }
    .stat-label {
      font-size: 0.8rem;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .stat-value {
      font-size: 0.95rem;
      font-weight: 700;
      word-break: break-word;
    }
    .steps {
      display: grid;
      gap: 14px;
      padding: 22px;
    }
    .step {
      display: grid;
      grid-template-columns: 44px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .step-num {
      width: 44px;
      height: 44px;
      display: grid;
      place-items: center;
      border-radius: 16px;
      background: linear-gradient(180deg, rgba(122,162,255,0.2), rgba(116,212,193,0.12));
      border: 1px solid rgba(122, 162, 255, 0.2);
      font-weight: 800;
      color: #f5f8ff;
    }
    .step-title {
      font-size: 0.98rem;
      font-weight: 700;
      margin-bottom: 4px;
    }
    .step-desc {
      color: var(--muted);
      line-height: 1.5;
      font-size: 0.95rem;
      margin: 0;
    }
    .layout {
      display: grid;
      grid-template-columns: 360px minmax(0, 1fr);
      gap: 20px;
      align-items: start;
    }
    .side-panel, .panel {
      padding: 22px;
    }
    .side-panel {
      position: sticky;
      top: 20px;
    }
    .panel + .panel {
      margin-top: 20px;
    }
    .section-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 16px;
    }
    .section-title h2 {
      font-size: 1.25rem;
      margin-bottom: 0;
    }
    .section-title .hint {
      color: var(--muted);
      font-size: 0.93rem;
    }
    .form-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-width: 0;
    }
    .field.full {
      grid-column: 1 / -1;
    }
    .field label {
      font-size: 0.88rem;
      color: var(--muted);
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    input, textarea, select {
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(159, 178, 216, 0.22);
      background: rgba(255, 255, 255, 0.04);
      color: var(--text);
      padding: 12px 14px;
      outline: none;
      transition: border-color .15s ease, transform .15s ease, background .15s ease;
    }
    input:focus, textarea:focus, select:focus {
      border-color: rgba(122, 162, 255, 0.65);
      background: rgba(255, 255, 255, 0.06);
    }
    textarea {
      resize: vertical;
      min-height: 96px;
    }
    .checkline {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 0.95rem;
      color: var(--text);
      padding-top: 10px;
    }
    .checkline input {
      width: 18px;
      height: 18px;
      margin: 0;
      accent-color: var(--accent);
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }
    .btn {
      appearance: none;
      border: 0;
      border-radius: 16px;
      padding: 12px 16px;
      font-weight: 800;
      letter-spacing: 0.01em;
      cursor: pointer;
      transition: transform .15s ease, box-shadow .15s ease, opacity .15s ease;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 46px;
    }
    .btn:hover { transform: translateY(-1px); }
    .btn:disabled {
      opacity: 0.55;
      cursor: not-allowed;
      transform: none;
    }
    .btn.primary {
      color: #08111f;
      background: linear-gradient(135deg, #8ab2ff 0%, #7ae0c6 100%);
      box-shadow: 0 12px 24px rgba(122, 162, 255, 0.25);
    }
    .btn.secondary {
      color: var(--text);
      background: rgba(255, 255, 255, 0.06);
      border: 1px solid rgba(159, 178, 216, 0.18);
    }
    .btn.ghost {
      color: var(--text);
      background: transparent;
      border: 1px solid rgba(159, 178, 216, 0.18);
    }
    .btn.warn {
      color: #10131a;
      background: linear-gradient(135deg, #ffd166 0%, #ffb347 100%);
    }
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .pill {
      padding: 8px 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(159, 178, 216, 0.14);
      color: var(--muted);
      font-size: 0.86rem;
    }
    .results-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }
    .result-card {
      border-radius: 18px;
      padding: 18px;
      border: 1px solid rgba(159, 178, 216, 0.16);
      background: rgba(255, 255, 255, 0.03);
      min-width: 0;
    }
    .result-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 14px;
    }
    .result-head h3 {
      font-size: 1.03rem;
      margin-bottom: 0;
    }
    .result-meta {
      color: var(--muted);
      font-size: 0.86rem;
    }
    .result-body {
      color: var(--text);
      line-height: 1.65;
      font-size: 0.96rem;
      overflow-wrap: anywhere;
    }
    .result-body p {
      margin: 0 0 10px;
    }
    .list {
      margin: 0;
      padding-left: 20px;
      display: grid;
      gap: 8px;
      color: var(--text);
      line-height: 1.6;
    }
    pre {
      margin: 0;
      padding: 16px;
      border-radius: 16px;
      background: rgba(0, 0, 0, 0.36);
      border: 1px solid rgba(159, 178, 216, 0.16);
      overflow: auto;
      color: #d9e7ff;
      font-family: var(--mono);
      font-size: 0.82rem;
      line-height: 1.55;
      white-space: pre-wrap;
      word-break: break-word;
    }
    details {
      margin-top: 14px;
    }
    details summary {
      cursor: pointer;
      color: var(--accent);
      font-weight: 700;
    }
    .progress-shell {
      margin-top: 14px;
      padding: 12px 0 0;
    }
    .progress-bar {
      height: 10px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.08);
      overflow: hidden;
    }
    .progress-fill {
      height: 100%;
      width: 0%;
      background: linear-gradient(90deg, var(--accent) 0%, var(--accent-2) 100%);
      transition: width .2s ease;
    }
    .status-line {
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.93rem;
    }
    .alert {
      margin-top: 12px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid rgba(159, 178, 216, 0.16);
      background: rgba(255, 255, 255, 0.04);
      color: var(--muted);
      line-height: 1.5;
    }
    .alert strong { color: var(--text); }
    .download-link {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 12px;
      font-weight: 800;
    }
    .empty {
      color: var(--muted);
      line-height: 1.6;
      font-size: 0.95rem;
      padding: 6px 0 2px;
    }
    .footer {
      margin-top: 20px;
      color: var(--muted);
      font-size: 0.9rem;
      text-align: center;
      padding-bottom: 24px;
    }
    .small {
      font-size: 0.88rem;
      color: var(--muted);
    }
    .copy-flash {
      color: var(--success);
      font-size: 0.85rem;
      opacity: 0;
      transition: opacity .2s ease;
    }
    .copy-flash.on { opacity: 1; }
    @media (max-width: 1180px) {
      .hero,
      .layout,
      .results-grid,
      .hero-grid {
        grid-template-columns: 1fr;
      }
      .side-panel {
        position: static;
      }
    }
    @media (max-width: 720px) {
      .shell { padding: 14px; }
      .hero-card, .side-panel, .panel { padding: 16px; }
      .form-grid { grid-template-columns: 1fr; }
      .actions { flex-direction: column; }
      .btn { width: 100%; }
      .result-head, .section-title { align-items: flex-start; flex-direction: column; }
      h1 { font-size: 2rem; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="hero-card">
        <div class="brand-row">
          <span class="badge"><span class="badge-dot"></span> __APP_NAME__</span>
          <span class="small">v__APP_VERSION__</span>
        </div>
        <h1>Turn wiki and SharePoint knowledge into a presentation-ready delivery.</h1>
        <p class="hero-copy">
          This workspace walks through the full workflow step by step:
          research the topic, summarize the evidence, turn it into a technical architecture document,
          then build a polished PowerPoint deck with speaker notes and downloadable output.
        </p>
        <div class="hero-grid">
          <div class="stat">
            <div class="stat-label">AI provider</div>
            <div class="stat-value" id="ai-provider-value">__AI_PROVIDER__</div>
          </div>
          <div class="stat">
            <div class="stat-label">Copilot status</div>
            <div class="stat-value" id="ai-status-value">unknown</div>
          </div>
          <div class="stat">
            <div class="stat-label">Model</div>
            <div class="stat-value">__AI_MODEL__</div>
          </div>
          <div class="stat">
            <div class="stat-label">Data dir</div>
            <div class="stat-value">__DATA_DIR__</div>
          </div>
          <div class="stat">
            <div class="stat-label">Presentation dir</div>
            <div class="stat-value">__PRESENTATION_DIR__</div>
          </div>
        </div>
      </div>
      <aside class="hero-card steps">
        <div class="step">
          <div class="step-num">1</div>
          <div>
            <div class="step-title">Research</div>
            <p class="step-desc">Search the topic across wiki pages, SharePoint content, files, URLs, or pasted text.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">2</div>
          <div>
            <div class="step-title">Analyze</div>
            <p class="step-desc">Summarize evidence into key points, risks, decisions, and next steps.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">3</div>
          <div>
            <div class="step-title">Architect</div>
            <p class="step-desc">Convert analysis into a technical document with sections, assumptions, and glossary items.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-num">4</div>
          <div>
            <div class="step-title">Present</div>
            <p class="step-desc">Generate the PowerPoint deck, speaker notes, and an output file you can download.</p>
          </div>
        </div>
      </aside>
    </section>

    <section class="layout">
      <aside class="side-panel">
        <div class="section-title">
          <h2>Quick start</h2>
          <span class="hint">End-to-end workflow</span>
        </div>
        <div class="alert">
          <strong>Recommended flow:</strong><br />
          1) Enter a topic and source hints.<br />
          2) Run <strong>Research</strong>.<br />
          3) Review and then run <strong>Analysis</strong>.<br />
          4) Build <strong>Architecture</strong>.<br />
          5) Generate the <strong>Presentation</strong> and download the deck.
        </div>
        <div class="pill-row">
          <span class="pill">wiki</span>
          <span class="pill">SharePoint</span>
          <span class="pill">URLs</span>
          <span class="pill">local files</span>
          <span class="pill">PowerPoint</span>
          <span class="pill">speaker notes</span>
        </div>
        <div class="actions" style="margin-top: 16px;">
          <button class="btn secondary" id="load-demo-btn" type="button">Load demo topic</button>
          <button class="btn ghost" id="reset-btn" type="button">Reset workspace</button>
        </div>
        <div class="actions" style="margin-top: 12px;">
          <button class="btn" id="ai-status-btn" type="button">Refresh Copilot status</button>
          <button class="btn secondary" id="ai-connect-btn" type="button">Connect Copilot</button>
          <button class="btn ghost" id="source-test-btn" type="button">Test source access</button>
        </div>
        <div class="progress-shell">
          <div class="progress-bar" aria-hidden="true"><div class="progress-fill" id="progress-fill"></div></div>
          <div class="status-line" id="status-line">Ready to start.</div>
        </div>
        <div class="alert" style="margin-top: 18px;">
          <strong>Tip:</strong> You can run each stage individually, or use <strong>Run full pipeline</strong> to execute all steps in order.
        </div>
      </aside>

      <main>
        <section class="panel">
          <div class="section-title">
            <h2>1. Configure your request</h2>
            <span class="hint">Research inputs and presentation settings</span>
          </div>

          <div class="form-grid">
            <div class="field full">
              <label for="topic">Topic</label>
              <input id="topic" type="text" value="Transactions / Positions / Balances processing in Oracle DB using CDS data source" />
            </div>

            <div class="field">
              <label for="source_type">Source type</label>
              <select id="source_type">
                <option value="">Auto detect</option>
                <option value="wiki">wiki</option>
                <option value="sharepoint">sharepoint</option>
                <option value="web">web</option>
                <option value="file">file</option>
                <option value="text">text</option>
              </select>
            </div>

            <div class="field">
              <label for="max_results">Max results</label>
              <input id="max_results" type="number" min="1" max="25" value="5" />
            </div>

            <div class="field">
              <label for="audience">Audience</label>
              <input id="audience" type="text" value="stakeholders" />
            </div>

            <div class="field">
              <label for="depth">Depth</label>
              <select id="depth">
                <option value="overview">overview</option>
                <option value="detailed" selected>detailed</option>
                <option value="implementation">implementation</option>
              </select>
            </div>

            <div class="field">
              <label for="slide_count">Slide count</label>
              <input id="slide_count" type="number" min="4" max="20" value="8" />
            </div>

            <div class="field">
              <label for="brand_color">Brand color</label>
              <input id="brand_color" type="color" value="#1F4E79" />
            </div>

            <div class="field full">
              <label for="sources">Source hints</label>
              <textarea id="sources" placeholder="Paste one URL, wiki page, SharePoint path, file name, or text ID per line."></textarea>
            </div>

            <div class="field full">
              <label for="local_directories">Local directories</label>
              <textarea id="local_directories" placeholder="Paste one absolute or relative folder path per line. The backend will search these folders recursively."></textarea>
            </div>

            <div class="field full">
              <label for="attached_files">Attach files</label>
              <input id="attached_files" type="file" multiple />
              <div class="small">Choose one or more local files to upload their text into the research request.</div>
            </div>

            <div class="field full">
              <label for="attached_folder">Attach a folder</label>
              <input id="attached_folder" type="file" multiple webkitdirectory />
              <div class="small">Pick a folder to upload its contents as attachments. Useful when you want the bot to inspect local documents directly.</div>
            </div>

            <div class="field full">
              <label for="focus_areas">Focus areas</label>
              <textarea id="focus_areas" placeholder="List the subjects you want emphasized, one per line."></textarea>
            </div>

            <div class="field">
              <label class="checkline">
                <input id="include_raw_context" type="checkbox" />
                Include raw context in research output
              </label>
            </div>

            <div class="field">
              <label class="checkline">
                <input id="include_speaker_notes" type="checkbox" checked />
                Include speaker notes in the PowerPoint deck
              </label>
            </div>
          </div>

          <div class="actions">
            <button class="btn primary" id="research-btn" type="button">Run research</button>
            <button class="btn secondary" id="analysis-btn" type="button">Run analysis</button>
            <button class="btn secondary" id="architecture-btn" type="button">Build architecture</button>
            <button class="btn secondary" id="presentation-btn" type="button">Create presentation</button>
            <button class="btn warn" id="full-btn" type="button">Run full pipeline</button>
          </div>
        </section>

        <section class="panel">
          <div class="section-title">
            <h2>2. Results</h2>
            <span class="hint">Generated JSON and readable summaries</span>
          </div>

          <div class="results-grid">
            <article class="result-card">
              <div class="result-head">
                <div>
                  <h3>Research</h3>
                  <div class="result-meta">Source-backed findings</div>
                </div>
                <div>
                  <button class="btn ghost" type="button" data-copy="research-json">Copy JSON</button>
                </div>
              </div>
              <div id="research-summary" class="result-body"><div class="empty">Run research to populate this section.</div></div>
              <details>
                <summary>Raw JSON</summary>
                <pre id="research-json"></pre>
              </details>
            </article>

            <article class="result-card">
              <div class="result-head">
                <div>
                  <h3>Analysis</h3>
                  <div class="result-meta">Executive summary and recommendations</div>
                </div>
                <div>
                  <button class="btn ghost" type="button" data-copy="analysis-json">Copy JSON</button>
                </div>
              </div>
              <div id="analysis-summary" class="result-body"><div class="empty">Run analysis to populate this section.</div></div>
              <details>
                <summary>Raw JSON</summary>
                <pre id="analysis-json"></pre>
              </details>
            </article>

            <article class="result-card">
              <div class="result-head">
                <div>
                  <h3>Architecture</h3>
                  <div class="result-meta">Technical document outline</div>
                </div>
                <div>
                  <button class="btn ghost" type="button" data-copy="architecture-json">Copy JSON</button>
                </div>
              </div>
              <div id="architecture-summary" class="result-body"><div class="empty">Build architecture to populate this section.</div></div>
              <details>
                <summary>Raw JSON</summary>
                <pre id="architecture-json"></pre>
              </details>
            </article>

            <article class="result-card">
              <div class="result-head">
                <div>
                  <h3>Presentation</h3>
                  <div class="result-meta">Deck preview and output file</div>
                </div>
                <div>
                  <button class="btn ghost" type="button" data-copy="presentation-json">Copy JSON</button>
                </div>
              </div>
              <div id="presentation-summary" class="result-body"><div class="empty">Generate the presentation to populate this section.</div></div>
              <details>
                <summary>Raw JSON</summary>
                <pre id="presentation-json"></pre>
              </details>
            </article>
          </div>
        </section>
      </main>
    </section>

    <div class="footer">
      Built for rapid wiki + SharePoint research, architecture documentation, and stakeholder-ready presentation generation.
    </div>
  </div>

  <script>
    const state = {
      research: null,
      analysis: null,
      architecture: null,
      presentation: null
    };

    const els = {
      topic: document.getElementById('topic'),
      sourceType: document.getElementById('source_type'),
      maxResults: document.getElementById('max_results'),
      sources: document.getElementById('sources'),
      localDirectories: document.getElementById('local_directories'),
      attachedFiles: document.getElementById('attached_files'),
      attachedFolder: document.getElementById('attached_folder'),
      focusAreas: document.getElementById('focus_areas'),
      includeRawContext: document.getElementById('include_raw_context'),
      audience: document.getElementById('audience'),
      depth: document.getElementById('depth'),
      slideCount: document.getElementById('slide_count'),
      brandColor: document.getElementById('brand_color'),
      includeSpeakerNotes: document.getElementById('include_speaker_notes'),
      aiProviderValue: document.getElementById('ai-provider-value'),
      aiStatusValue: document.getElementById('ai-status-value'),
      statusLine: document.getElementById('status-line'),
      progressFill: document.getElementById('progress-fill'),
      aiStatusBtn: document.getElementById('ai-status-btn'),
      aiConnectBtn: document.getElementById('ai-connect-btn'),
      sourceTestBtn: document.getElementById('source-test-btn'),
      researchSummary: document.getElementById('research-summary'),
      analysisSummary: document.getElementById('analysis-summary'),
      architectureSummary: document.getElementById('architecture-summary'),
      presentationSummary: document.getElementById('presentation-summary'),
      researchJson: document.getElementById('research-json'),
      analysisJson: document.getElementById('analysis-json'),
      architectureJson: document.getElementById('architecture-json'),
      presentationJson: document.getElementById('presentation-json'),
      researchBtn: document.getElementById('research-btn'),
      analysisBtn: document.getElementById('analysis-btn'),
      architectureBtn: document.getElementById('architecture-btn'),
      presentationBtn: document.getElementById('presentation-btn'),
      fullBtn: document.getElementById('full-btn'),
      loadDemoBtn: document.getElementById('load-demo-btn'),
      resetBtn: document.getElementById('reset-btn')
    };

    const demoSources = [
      'wiki://transactions-processing-overview',
      'sharepoint://tpb/solution-architecture',
      'sharepoint://tpb/data-source-cds'
    ];

    function setStatus(message, progress = 0) {
      els.statusLine.textContent = message;
      els.progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }

    function collectSourceTargets() {
      return [...splitLines(els.sources.value), ...splitLines(els.localDirectories.value)];
    }

    async function refreshCopilotStatus() {
      setStatus('Checking Copilot status...', 5);
      const response = await fetch('/api/ai/status');
      if (!response.ok) {
        throw new Error(`Copilot status request failed (${response.status})`);
      }
      const data = await response.json();
      const status = data.status || (data.configured ? 'configured' : 'not configured');
      els.aiStatusValue.textContent = status;
      if (data.provider || data.ai_provider) {
        els.aiProviderValue.textContent = data.provider || data.ai_provider;
      }
      setStatus(`Copilot status: ${status}`, 10);
      return data;
    }

    async function connectCopilot() {
      const payload = {
        provider: prompt('AI provider', els.aiProviderValue.textContent.trim() || 'githubcopilot') || '',
        base_url: prompt('AI base URL (optional)', '') || '',
        model: prompt('AI model (optional)', '') || '',
        api_key: prompt('API key / token (optional)', '') || '',
        test_connection: true
      };
      setStatus('Connecting Copilot...', 8);
      const response = await postJson('/api/ai/connect', payload);
      els.aiStatusValue.textContent = response.status || response.message || 'connected';
      if (response.provider) {
        els.aiProviderValue.textContent = response.provider;
      }
      setStatus(response.message || 'Copilot connection updated.', 12);
      return response;
    }

    async function testSourceAccess() {
      const sources = collectSourceTargets();
      if (!sources.length) {
        throw new Error('Add at least one source hint or local directory before testing access.');
      }
      setStatus('Testing source access...', 8);
      const response = await postJson('/api/source/test', { sources });
      setStatus(`Source access test complete: ${response.tested_sources || sources.length} sources checked.`, 15);
      return response;
    }

    function setBusy(isBusy) {
      [els.researchBtn, els.analysisBtn, els.architectureBtn, els.presentationBtn, els.fullBtn].forEach((btn) => {
        btn.disabled = isBusy;
      });
    }

    function splitLines(value) {
      return String(value || '')
        .split(/\\r?\\n|,/)
        .map((item) => item.trim())
        .filter(Boolean);
    }

    function getTopic() {
      return els.topic.value.trim();
    }

    function readFileAsText(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = () => reject(reader.error || new Error(`Failed to read ${file.name}`));
        reader.readAsText(file);
      });
    }

    async function collectAttachedFiles() {
      const selected = [
        ...(els.attachedFiles.files ? Array.from(els.attachedFiles.files) : []),
        ...(els.attachedFolder.files ? Array.from(els.attachedFolder.files) : [])
      ];
      const unique = [];
      const seen = new Set();

      for (const file of selected) {
        const name = file.webkitRelativePath || file.name;
        const key = `${name}::${file.size}::${file.lastModified}`;
        if (seen.has(key)) {
          continue;
        }
        seen.add(key);

        const content = await readFileAsText(file);
        unique.push({
          name,
          content,
          mime_type: file.type || null
        });
      }

      return unique;
    }

    async function collectResearchRequest() {
      return {
        topic: getTopic(),
        sources: splitLines(els.sources.value),
        local_directories: splitLines(els.localDirectories.value),
        attached_files: await collectAttachedFiles(),
        source_type: els.sourceType.value || null,
        max_results: Number(els.maxResults.value || 5),
        include_raw_context: els.includeRawContext.checked
      };
    }

    function collectAnalysisRequest() {
      return {
        topic: getTopic(),
        research: state.research,
        focus_areas: splitLines(els.focusAreas.value)
      };
    }

    function collectArchitectureRequest() {
      return {
        topic: getTopic(),
        analysis: state.analysis,
        audience: els.audience.value.trim() || 'engineering',
        depth: els.depth.value
      };
    }

    function collectPresentationRequest() {
      return {
        topic: getTopic(),
        architecture: state.architecture,
        audience: els.audience.value.trim() || 'stakeholders',
        slide_count: Number(els.slideCount.value || 8),
        brand_color: els.brandColor.value,
        include_speaker_notes: els.includeSpeakerNotes.checked
      };
    }

    async function postJson(url, body) {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const text = await response.text();
      if (!response.ok) {
        throw new Error(text || `Request failed (${response.status})`);
      }
      if (!text) {
        return {};
      }
      return JSON.parse(text);
    }

    function prettyJson(value) {
      return JSON.stringify(value, null, 2);
    }

    function safeText(value) {
      return String(value ?? '').replace(/[&<>]/g, (char) => ({
        '&': '&',
        '<': '<',
        '>': '>'
      })[char]);
    }

    function renderList(items) {
      if (!items || !items.length) {
        return '<div class="empty">No items available.</div>';
      }
      return `<ul class="list">${items.map((item) => `<li>${safeText(item)}</li>`).join('')}</ul>`;
    }

    function renderCitations(citations) {
      if (!citations || !citations.length) {
        return '<div class="empty">No citations available.</div>';
      }
      return `<ul class="list">${
        citations.map((citation) => {
          const parts = [
            citation.title || citation.source_id || 'Source',
            citation.url ? `<span class="small">(${safeText(citation.url)})</span>` : '',
            citation.excerpt ? `<div class="small">${safeText(citation.excerpt)}</div>` : ''
          ].join(' ');
          return `<li>${parts}</li>`;
        }).join('')
      }</ul>`;
    }

    function renderResearch(result) {
      els.researchJson.textContent = prettyJson(result);
      els.researchSummary.innerHTML = `
        <p><strong>Summary:</strong> ${safeText(result.summary || 'No summary returned.')}</p>
        <p><strong>Findings</strong></p>
        ${renderList(result.findings)}
        <p style="margin-top: 14px;"><strong>Risks</strong></p>
        ${renderList(result.risks)}
        <p style="margin-top: 14px;"><strong>Assumptions</strong></p>
        ${renderList(result.assumptions)}
        <p style="margin-top: 14px;"><strong>Open questions</strong></p>
        ${renderList(result.open_questions)}
        <p style="margin-top: 14px;"><strong>Citations</strong></p>
        ${renderCitations(result.citations)}
      `;
    }

    function renderAnalysis(result) {
      els.analysisJson.textContent = prettyJson(result);
      els.analysisSummary.innerHTML = `
        <p><strong>Executive summary:</strong> ${safeText(result.executive_summary || 'No summary returned.')}</p>
        <p><strong>Key points</strong></p>
        ${renderList(result.key_points)}
        <p style="margin-top: 14px;"><strong>Dependencies</strong></p>
        ${renderList(result.dependencies)}
        <p style="margin-top: 14px;"><strong>Decisions</strong></p>
        ${renderList(result.decisions)}
        <p style="margin-top: 14px;"><strong>Recommended next steps</strong></p>
        ${renderList(result.recommended_next_steps)}
        <p style="margin-top: 14px;"><strong>Open questions</strong></p>
        ${renderList(result.open_questions)}
      `;
    }

    function renderArchitecture(result) {
      els.architectureJson.textContent = prettyJson(result);
      const sections = (result.sections || []).map((section) => `
        <div style="margin-top: 14px;">
          <p><strong>${safeText(section.heading)}</strong></p>
          <div class="small" style="line-height: 1.65;">${safeText(section.body)}</div>
          ${renderList(section.bullets || [])}
        </div>
      `).join('');
      els.architectureSummary.innerHTML = `
        <p><strong>Title:</strong> ${safeText(result.title || result.topic || 'Architecture')}</p>
        <p><strong>Executive summary:</strong> ${safeText(result.executive_summary || 'No summary returned.')}</p>
        ${sections}
        <p style="margin-top: 14px;"><strong>Glossary</strong></p>
        ${renderList(result.glossary)}
        <p style="margin-top: 14px;"><strong>Assumptions</strong></p>
        ${renderList(result.assumptions)}
        <p style="margin-top: 14px;"><strong>Open questions</strong></p>
        ${renderList(result.open_questions)}
      `;
    }

    function renderPresentation(result) {
      els.presentationJson.textContent = prettyJson(result);
      const slides = (result.slides || []).map((slide, index) => `
        <div style="margin-top: 14px;">
          <p><strong>Slide ${index + 1}: ${safeText(slide.title)}</strong></p>
          ${slide.subtitle ? `<div class="small">${safeText(slide.subtitle)}</div>` : ''}
          ${renderList(slide.bullets || [])}
          ${slide.notes && slide.notes.length ? `<div class="small" style="margin-top: 8px;"><strong>Notes:</strong> ${safeText(slide.notes.join(' | '))}</div>` : ''}
        </div>
      `).join('');

      const downloadName = (result.output_path || '').split(/[\\\\/]/).pop();
      const downloadLink = downloadName
        ? `<a class="download-link" href="/api/presentations/${encodeURIComponent(downloadName)}" target="_blank" rel="noopener">Download presentation</a>`
        : '';

      els.presentationSummary.innerHTML = `
        <p><strong>Title:</strong> ${safeText(result.title || result.topic || 'Presentation')}</p>
        ${result.subtitle ? `<p><strong>Subtitle:</strong> ${safeText(result.subtitle)}</p>` : ''}
        ${slides}
        ${downloadLink}
        ${result.output_path ? `<div class="small" style="margin-top: 10px;">Saved to: ${safeText(result.output_path)}</div>` : ''}
      `;
    }

    function copyJson(id) {
      const target = document.getElementById(id);
      if (!target || !target.textContent.trim()) {
        return;
      }
      navigator.clipboard.writeText(target.textContent).then(() => {
        const button = document.querySelector(`[data-copy="${id}"]`);
        if (!button) return;
        const original = button.textContent;
        button.textContent = 'Copied';
        setTimeout(() => {
          button.textContent = original;
        }, 1000);
      });
    }

    async function runResearch() {
      setBusy(true);
      try {
        setStatus('Running research...', 20);
        const request = await collectResearchRequest();
        if (!request.topic) throw new Error('Please enter a topic before running research.');
        state.research = await postJson('/api/research', request);
        renderResearch(state.research);
        setStatus('Research complete. Review the findings, then run analysis.', 35);
        return state.research;
      } catch (error) {
        setStatus(`Research failed: ${error.message}`, 0);
        throw error;
      } finally {
        setBusy(false);
      }
    }

    async function runAnalysis() {
      setBusy(true);
      try {
        if (!state.research) {
          await runResearch();
        }
        setStatus('Running analysis...', 45);
        state.analysis = await postJson('/api/analysis', collectAnalysisRequest());
        renderAnalysis(state.analysis);
        setStatus('Analysis complete. Build the architecture next.', 60);
        return state.analysis;
      } catch (error) {
        setStatus(`Analysis failed: ${error.message}`, 0);
        throw error;
      } finally {
        setBusy(false);
      }
    }

    async function runArchitecture() {
      setBusy(true);
      try {
        if (!state.analysis) {
          await runAnalysis();
        }
        setStatus('Building architecture...', 70);
        state.architecture = await postJson('/api/architecture', collectArchitectureRequest());
        renderArchitecture(state.architecture);
        setStatus('Architecture complete. Generate the presentation now.', 82);
        return state.architecture;
      } catch (error) {
        setStatus(`Architecture failed: ${error.message}`, 0);
        throw error;
      } finally {
        setBusy(false);
      }
    }

    async function runPresentation() {
      setBusy(true);
      try {
        if (!state.architecture) {
          await runArchitecture();
        }
        setStatus('Generating presentation deck...', 90);
        state.presentation = await postJson('/api/presentation', collectPresentationRequest());
        renderPresentation(state.presentation);
        setStatus('Presentation complete. Download your deck below.', 100);
        return state.presentation;
      } catch (error) {
        setStatus(`Presentation failed: ${error.message}`, 0);
        throw error;
      } finally {
        setBusy(false);
      }
    }

    async function runFullPipeline() {
      setBusy(true);
      try {
        await runResearch();
        await runAnalysis();
        await runArchitecture();
        await runPresentation();
        setStatus('Full pipeline complete. Everything is ready to review.', 100);
      } catch (error) {
        setStatus(`Pipeline failed: ${error.message}`, 0);
      } finally {
        setBusy(false);
      }
    }

    function resetWorkspace() {
      state.research = null;
      state.analysis = null;
      state.architecture = null;
      state.presentation = null;
      els.researchJson.textContent = '';
      els.analysisJson.textContent = '';
      els.architectureJson.textContent = '';
      els.presentationJson.textContent = '';
      els.researchSummary.innerHTML = '<div class="empty">Run research to populate this section.</div>';
      els.analysisSummary.innerHTML = '<div class="empty">Run analysis to populate this section.</div>';
      els.architectureSummary.innerHTML = '<div class="empty">Build architecture to populate this section.</div>';
      els.presentationSummary.innerHTML = '<div class="empty">Generate the presentation to populate this section.</div>';
      setStatus('Workspace reset. Ready to start again.', 0);
    }

    function loadDemo() {
      els.topic.value = 'Transactions / Positions / Balances processing in Oracle DB using CDS data source';
      els.sourceType.value = '';
      els.maxResults.value = 5;
      els.sources.value = demoSources.join('\n');
      els.localDirectories.value = '';
      els.attachedFiles.value = '';
      els.attachedFolder.value = '';
      els.focusAreas.value = [
        'transaction lifecycle',
        'position valuation',
        'balance aggregation',
        'Oracle DB integration',
        'CDS source mapping'
      ].join('\n');
      els.audience.value = 'stakeholders';
      els.depth.value = 'detailed';
      els.slideCount.value = 8;
      els.brandColor.value = '#1F4E79';
      els.includeRawContext.checked = false;
      els.includeSpeakerNotes.checked = true;
      setStatus('Demo topic loaded. Run research to begin.', 10);
    }

    document.querySelectorAll('[data-copy]').forEach((button) => {
      button.addEventListener('click', () => copyJson(button.getAttribute('data-copy')));
    });

    els.aiStatusBtn.addEventListener('click', () => refreshCopilotStatus().catch((error) => setStatus(error.message, 0)));
    els.aiConnectBtn.addEventListener('click', () => connectCopilot().catch((error) => setStatus(error.message, 0)));
    els.sourceTestBtn.addEventListener('click', () => testSourceAccess().catch((error) => setStatus(error.message, 0)));
    els.researchBtn.addEventListener('click', () => runResearch().catch(() => {}));
    els.analysisBtn.addEventListener('click', () => runAnalysis().catch(() => {}));
    els.architectureBtn.addEventListener('click', () => runArchitecture().catch(() => {}));
    els.presentationBtn.addEventListener('click', () => runPresentation().catch(() => {}));
    els.fullBtn.addEventListener('click', () => runFullPipeline().catch(() => {}));
    els.loadDemoBtn.addEventListener('click', loadDemo);
    els.resetBtn.addEventListener('click', resetWorkspace);

    refreshCopilotStatus().catch(() => {});
    setStatus('Ready. Load the demo topic or enter your own request.', 8);
  </script>
</body>
</html>
"""


def _default_data_dir() -> Path:
    configured = (Path(str(DATA_DIR))).expanduser()
    return configured


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Prepare runtime directories before handling requests."""
    for folder in (DATA_DIR, SOURCE_DIR, OUTPUT_DIR, PRESENTATION_DIR):
        Path(folder).mkdir(parents=True, exist_ok=True)
    yield


def _render_index_html() -> str:
    model_name = settings.AI_MODEL or settings.GITHUBCOPILOT_MODEL or settings.OPENAI_MODEL or "local fallback"
    html = INDEX_HTML
    return (
        html.replace("__APP_NAME__", settings.APP_NAME)
        .replace("__APP_VERSION__", settings.APP_VERSION)
        .replace("__AI_PROVIDER__", settings.AI_PROVIDER)
        .replace("__AI_MODEL__", model_name)
        .replace("__DATA_DIR__", str(DATA_DIR))
        .replace("__OUTPUT_DIR__", str(OUTPUT_DIR))
        .replace("__PRESENTATION_DIR__", str(PRESENTATION_DIR))
    )


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=APP_DESCRIPTION,
    lifespan=lifespan,
)
app.include_router(system_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse, tags=["ui"])
async def root() -> HTMLResponse:
    return HTMLResponse(_render_index_html())


@app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
async def ui() -> HTMLResponse:
    return HTMLResponse(_render_index_html())


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


@app.get("/health", tags=["system"])
async def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "data_dir": str(DATA_DIR),
        "output_dir": str(OUTPUT_DIR),
        "presentation_dir": str(PRESENTATION_DIR),
    }


@app.get("/api/info", tags=["system"])
async def info() -> Dict[str, Any]:
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "data_dir": str(DATA_DIR),
        "source_dir": str(SOURCE_DIR),
        "output_dir": str(OUTPUT_DIR),
        "presentation_dir": str(PRESENTATION_DIR),
        "ai_provider": settings.AI_PROVIDER,
        "model": settings.AI_MODEL or settings.GITHUBCOPILOT_MODEL or settings.OPENAI_MODEL,
    }


@app.post("/api/research", tags=["research"])
async def run_research(request: ResearchRequest):
    return await research_service.run(request)


@app.post("/api/analysis", tags=["analysis"])
async def run_analysis(request: AnalysisRequest):
    return await analysis_service.run(request)


@app.post("/api/architecture", tags=["architecture"])
async def run_architecture(request: ArchitectureRequest):
    return await architecture_service.async_generate(request)


@app.post("/api/presentation", tags=["presentation"])
async def run_presentation(request: PresentationRequest):
    return await presentation_service.async_generate(request)


@app.get("/api/presentations/{filename}", tags=["presentation"])
async def download_presentation(filename: str):
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=404, detail="Presentation file not found")
    file_path = PRESENTATION_DIR / safe_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Presentation file not found")
    return FileResponse(path=file_path, filename=file_path.name, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation")
