import os
import subprocess
import datetime
from flask import Flask, request, jsonify, render_template, send_from_directory
from google.cloud import speech
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

DEMO_MODE = os.getenv("DEMO_MODE", "false").strip().lower() == "true"
GCP_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
SAMPLE_WAV_PATH = os.path.join(STATIC_DIR, "sample.wav")
SAMPLE_TRANSCRIPT_PATH = os.path.join(STATIC_DIR, "sample.transcript.txt")
SAMPLE_SUMMARY_PATH = os.path.join(STATIC_DIR, "sample.summary.txt")

def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def convert_webm_to_wav_in_memory(webm_data: bytes) -> bytes:
    """Re-encode to 16kHz mono WAV (LINEAR16) in-memory via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-i", "pipe:0",
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        "-f", "wav",
        "pipe:1",
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate(input=webm_data)
    if proc.returncode != 0:
        raise RuntimeError(err.decode("utf-8", errors="replace"))
    return out

# ---- diarized words -> readable text (no "Speaker X:" labels) ----
def _sec(ts):
    """Google Duration or datetime.timedelta -> float seconds."""
    if ts is None:
        return None
    if hasattr(ts, "seconds") and hasattr(ts, "nanos"):  # protobuf Duration
        try:
            return ts.seconds + ts.nanos / 1e9
        except Exception:
            pass
    if isinstance(ts, datetime.timedelta):
        return ts.total_seconds()
    try:
        return float(ts)
    except Exception:
        return None

def words_to_text(words):
    """
    Build readable lines without speaker labels:
      - collapse immediate duplicates within a short window
      - break sentences on longer silences
      - add minimal punctuation
    """
    lines = []
    current_tag = None
    buffer = []

    DUP_WINDOW = 0.6   # seconds
    PAUSE_SPLIT = 0.8  # seconds

    last_token = None
    last_end = None

    def flush():
        nonlocal buffer
        if buffer:
            text = " ".join(buffer).strip()
            if text and text[-1] not in ".?!":
                text += "."
            lines.append(text)
            buffer = []

    for w in words:
        tag = getattr(w, "speaker_tag", None)
        token = (getattr(w, "word", "") or "").strip()
        start = _sec(getattr(w, "start_time", None))
        end   = _sec(getattr(w, "end_time", None))

        # new speaker -> finish previous line (but no visible label)
        if tag != current_tag:
            flush()
            current_tag = tag
            last_token = None
            last_end = None

        # drop immediate duplicates like "Hello Hello"
        if last_token and token and token.lower() == last_token.lower():
            if last_end is not None and start is not None and (start - last_end) <= DUP_WINDOW:
                last_end = end
                continue

        # sentence split on long pause
        if last_end is not None and start is not None and (start - last_end) >= PAUSE_SPLIT:
            if buffer and buffer[-1] and buffer[-1][-1] not in ".?!":
                buffer[-1] = buffer[-1] + "."

        buffer.append(token)
        last_token = token
        last_end = end

    flush()
    return "\n".join(lines)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/scribe")
def scribe():
    return render_template("scribe.html")

# Optional: serve sample.wav explicitly (handy during local demos)
@app.route("/static/sample.wav")
def sample_wav():
    return send_from_directory(STATIC_DIR, "sample.wav", as_attachment=False)

@app.route("/transcribe", methods=["POST"])
def transcribe_audio():
    """
    Accepts multipart/form-data 'audio_data' (any container/codec),
    converts to WAV, sends to Google STT with diarization,
    returns a transcript (no speaker prefixes).

    DEMO behavior:
      - If DEMO_MODE is true AND no GOOGLE_APPLICATION_CREDENTIALS,
        return pre-baked transcript from static/sample.transcript.txt.
    """
    if "audio_data" not in request.files:
        return jsonify({"error": "No audio_data file found"}), 400

    raw = request.files["audio_data"].read()
    if not raw:
        return jsonify({"error": "Empty audio_data"}), 400

    # DEMO shortcut (no GCP cred)
    if DEMO_MODE and not GCP_CREDS:
        baked = _read_text_file(SAMPLE_TRANSCRIPT_PATH)
        if baked:
            return jsonify({"transcript": baked})
        return jsonify({"error": "Demo mode: sample transcript file not found."}), 500

    # Live STT path
    if not GCP_CREDS:
        return jsonify({"error": "GOOGLE_APPLICATION_CREDENTIALS is not set"}), 500

    try:
        wav = convert_webm_to_wav_in_memory(raw)
    except RuntimeError as e:
        return jsonify({"error": f"FFmpeg failed: {e}"}), 500

    client = speech.SpeechClient()
    diar = speech.SpeakerDiarizationConfig(
        enable_speaker_diarization=True,
        min_speaker_count=2,
        max_speaker_count=2,
    )
    cfg = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        language_code="en-US",
        enable_automatic_punctuation=True,
        enable_word_time_offsets=True,
        diarization_config=diar,
    )
    audio = speech.RecognitionAudio(content=wav)

    op = client.long_running_recognize(config=cfg, audio=audio)
    resp = op.result(timeout=300)

    if not resp.results:
        return jsonify({"transcript": ""})

    alt = resp.results[-1].alternatives[0]
    transcript = words_to_text(alt.words)
    return jsonify({"transcript": transcript})

@app.route("/process_transcript", methods=["POST"])
def process_transcript():
    """
    Accepts JSON: { "transcript": "..." }
    Uses OpenAI to return a cleaned dialogue + structured EMR summary.

    DEMO behavior:
      - If DEMO_MODE is true AND no OPENAI_API_KEY,
        return pre-baked summary from static/sample.summary.txt.
    """
    data = request.get_json(silent=True) or {}
    transcript = data.get("transcript", "")
    if not transcript:
        return jsonify({"error": "No transcript provided"}), 400

    # DEMO shortcut (no OpenAI key)
    if DEMO_MODE and not OPENAI_KEY:
        baked = _read_text_file(SAMPLE_SUMMARY_PATH)
        if baked:
            return jsonify({"response": baked})
        return jsonify({"error": "Demo mode: sample summary file not found."}), 500

    if not OPENAI_KEY:
        return jsonify({"error": "OPENAI_API_KEY is not set"}), 500

    instruction = """
    You will be given a transcript of a conversation between a Doctor and a Patient.
    First, return a cleaned version of the dialogue (essential points only, per turn).
    Then create a detailed, structured medical EMR summary in English.
    Do not fabricate facts. If information is missing, state “Not reported”.
    Include treatment options and plan when applicable (suggestions, not prescriptions).
    """

    client = OpenAI()
    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": transcript},
            ],
            temperature=0.2,
        )
        return jsonify({"response": completion.choices[0].message.content})
    except Exception as e:
        return jsonify({"error": f"OpenAI error: {e}"}), 502

@app.route("/healthz")
def healthz():
    return jsonify({"ok": True, "demo": DEMO_MODE})

if __name__ == "__main__":
    app.run(debug=True)
