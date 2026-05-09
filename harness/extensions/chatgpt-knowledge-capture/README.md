# Solar Knowledge Capture Chrome Extension

Click the extension icon to capture the current page into the Solar knowledge ingest pipeline.

- ChatGPT pages are captured as structured `user` / `assistant` messages and imported through `/chatgpt-import`.
- Other pages are captured as plain page text through `/capture`.
- The local server must be running: `solar-harness wiki capture-server start --port 8788`.
