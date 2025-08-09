# MedScribe — Medical Scribe Demo (Flask)

> Turn short doctor–patient audio into a clean transcript and an EMR‑style summary. Works from your **microphone** or a bundled **sample.wav**. Ships with a **DEMO mode** so anyone can try it without cloud accounts.

**Watch:** [90‑second Loom demo](https://www.loom.com/share/289f3939dd5c44db85e92382007ffa73?sid=9522d703-893d-458d-8c3f-300a2b5ec0f8)

**GIF:** ![Demo](docs/demo_medscribe.gif)

> **Disclaimer:** For demonstration only. Not medical advice.

---

## Features

* Mic recording **or** local file upload
* Google Speech‑to‑Text with speaker diarization (live mode)
* Smart cleanup: de‑dupes quick repeats (e.g., “Hello Hello”) and splits sentences by pauses
* One‑click **Use sample.wav** (instant demo path)
* EMR‑style summary via OpenAI (with DEMO fallback)
* Minimal REST API + ready Postman collection

## Tech Stack

Flask • Google Cloud Speech‑to‑Text • OpenAI • FFmpeg

## What’s in the box

```
.
├── app.py
├── requirements.txt
├── .env.example
├── templates/
│   ├── index.html
│   └── scribe.html
├── static/
│   ├── css/scribe.css
│   ├── js/scribe.js
│   ├── sample.wav
│   ├── sample.transcript.txt     # used in DEMO mode if no GCP creds
│   └── sample.summary.txt        # used in DEMO mode if no OpenAI key
└── docs/
    ├── demo_medscribe.gif                  # optional; referenced in README
    └── medscribe_postman_collection.json   # ready-to-import Postman file (2 requests)
```

---

## Quick Start — DEMO mode (no cloud accounts)

This path works out of the box using pre‑baked outputs.

1. **Clone & enter**

   ```bash
   git clone https://github.com/sagintai/MedScribe
   cd MedScribe
   ```
2. **Create a virtualenv & install deps**

   ```bash
   python3 -m venv venv
   # macOS/Linux
   source venv/bin/activate
   # Windows (PowerShell)
   # .\venv\Scripts\Activate.ps1

   pip install --upgrade pip
   pip install -r requirements.txt
   ```
3. **Install FFmpeg**

   * **macOS (Homebrew)**

     ```bash
     brew install ffmpeg
     ```
   * **Ubuntu/Debian**

     ```bash
     sudo apt-get update && sudo apt-get install -y ffmpeg
     ```
   * **Windows**

     * **winget**

       ```powershell
       winget install --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
       ```
     * **Chocolatey**

       ```powershell
       choco install ffmpeg
       ```
     * Or download a static build, unzip, and add its `bin` to **PATH**.
   * Verify:

     ```bash
     ffmpeg -version
     ```
4. **Environment**

   ```bash
   cp .env.example .env
   # DEMO_MODE=true is already set. No keys needed for the first run.
   ```
5. **Run**

   ```bash
   python app.py
   # open http://127.0.0.1:5000
   ```
6. **Try it**

   * Click **Use sample.wav** → transcript appears (DEMO path)
   * Click **Create Summary** → EMR‑style summary (DEMO path)

---

## Live Mode (real STT + OpenAI)

Use this when you want actual cloud transcription and summaries on your own audio.

1. **Get credentials**

   * **Google Cloud Speech‑to‑Text**: create a Service Account and download its JSON key.
   * **OpenAI**: create an API key.
2. **Edit `.env`** (prefer absolute paths):

   ```env
   DEMO_MODE=false
   GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/your-service-account.json
   OPENAI_API_KEY=sk-...
   ```
3. **Run**

   ```bash
   python app.py
   ```

   * Mic or file uploads now use **Google STT**
   * Summaries are generated via **OpenAI**

> **Security:** never commit your API keys or GCP JSON. `.env` and key files must stay local/secret.

---

## Postman — click‑test the API

A ready collection lives at **`docs/medscribe_postman_collection.json`**.

### Import

1. Open Postman → **Import → File** → select `docs/medscribe_postman_collection.json` → **Import**.
2. The collection includes a variable `base_url` preset to `http://127.0.0.1:5000`.

### Requests in the collection

* **Transcribe (file upload)** — `POST {{base_url}}/transcribe`

  * Body → **form-data** → key `audio_data` (type **File**) → choose `static/sample.wav` or your own file.
* **Process Transcript (EMR summary)** — `POST {{base_url}}/process_transcript`

  * Body → **raw (JSON)**: `{ "transcript": "Hello from Postman" }`

### cURL equivalents

```bash
# Transcribe
curl -F "audio_data=@static/sample.wav" http://127.0.0.1:5000/transcribe

# Process Transcript
curl -X POST http://127.0.0.1:5000/process_transcript \
     -H "Content-Type: application/json" \
     -d '{"transcript":"..."}'
```

---

## Environment Variables

* `DEMO_MODE` — `true` for pre‑baked transcript/summary when creds are missing; `false` for live mode
* `GOOGLE_APPLICATION_CREDENTIALS` — absolute path to your GCP service account JSON (live STT)
* `OPENAI_API_KEY` — OpenAI key (live summary)

Copy `.env.example` → `.env` and fill values.

---

## Troubleshooting

* **`ffmpeg: command not found`** — install FFmpeg and restart the terminal.
* **`GOOGLE_APPLICATION_CREDENTIALS is not set`** — required in live mode; use an **absolute** path.
* **OpenAI error** — ensure `OPENAI_API_KEY` is set; check corporate proxies/VPN.
* **Mic access denied** — allow microphone permissions in the browser or use file upload.


## License

MIT
