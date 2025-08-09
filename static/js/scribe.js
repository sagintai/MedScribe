const startEncounterBtn = document.getElementById("startEncounterBtn");
const stopRecordingBtn = document.getElementById("stopRecordingBtn");
const encounterIntro = document.getElementById("encounterIntro");
const transcriptSection = document.getElementById("transcriptSection");
const transcriptArea = document.getElementById("transcriptArea");
const createSummaryBtn = document.getElementById("createSummaryBtn");
const sendToEmrBtn = document.getElementById("sendToEmrBtn");
const loadingSpinner = document.getElementById("loadingSpinner");
const loadingText = document.getElementById("loadingText");
const summaryLoading = document.getElementById("summaryLoading");
const useSampleBtn = document.getElementById("useSampleBtn");
const samplePlayer = document.getElementById("samplePlayer");


let mediaRecorder = null;
let chunks = [];

// Start continuous recording
startEncounterBtn.addEventListener("click", async () => {
  encounterIntro.classList.add("hidden");
  transcriptSection.classList.remove("hidden");
  transcriptArea.classList.add("hidden");
  loadingSpinner.style.display = "block";

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  
  mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm; codecs=opus" });
  chunks = [];

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) {
      chunks.push(e.data);
    }
  };

  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, { type: "audio/webm; codecs=opus" });
    await sendBlobToServer(blob);
    createSummaryBtn.classList.remove("hidden");
  };

  mediaRecorder.start();
  stopRecordingBtn.classList.remove("hidden");
  startEncounterBtn.classList.add("hidden");
});

// Stop recording
stopRecordingBtn.addEventListener("click", () => {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    stopRecordingBtn.classList.add("hidden");
    loadingText.innerHTML = "Processing recording...";
    loadingText.style.color = "green";
  }
});

// Use bundled sample.wav
useSampleBtn.addEventListener("click", async () => {
  encounterIntro.classList.add("hidden");
  transcriptSection.classList.remove("hidden");
  transcriptArea.classList.add("hidden");
  loadingSpinner.style.display = "block";

  if (samplePlayer) samplePlayer.classList.remove("hidden");

  try {
    const resp = await fetch("/static/sample.wav");
    if (!resp.ok) throw new Error(`Failed to fetch sample.wav: ${resp.status}`);
    const buf = await resp.arrayBuffer();
    const blob = new Blob([buf], { type: "audio/wav" });

    await sendBlobToServer(blob);     
    createSummaryBtn.classList.remove("hidden");
  } catch (err) {
    console.error("Sample flow error:", err);
    loadingSpinner.style.display = "none";
    transcriptArea.classList.remove("hidden");
    transcriptArea.value = "Error: could not load or transcribe sample.wav.";
  }
});


// Upload audio blob and display transcript
async function sendBlobToServer(audioBlob) {
  const formData = new FormData();
  formData.append("audio_data", audioBlob, "recording.webm");

  try {
    const resp = await fetch("/transcribe", { method: "POST", body: formData });
    const data = await resp.json();

    loadingSpinner.style.display = "none";
    transcriptArea.classList.remove("hidden");

    if (data.error) {
      console.error("Transcription error:", data.error);
      transcriptArea.value = "Error during transcription.";
    } else if (data.transcript) {
      transcriptArea.value = data.transcript.trim();
    }
  } catch (err) {
    console.error("Error sending blob to server:", err);
    loadingSpinner.style.display = "none";
    transcriptArea.classList.remove("hidden");
    transcriptArea.value = "An error occurred while uploading audio.";
  }
}

// Request AI summary
createSummaryBtn.addEventListener("click", async function () {
  const transcript = transcriptArea.value;
  summaryLoading.classList.remove("hidden");

  const response = await fetch("/process_transcript", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ transcript })
  });

  const data = await response.json();
  document.getElementById("summaryArea").value = data.response;
  summaryLoading.classList.add("hidden");
});

// Send to EMR (placeholder)
sendToEmrBtn.addEventListener("click", () => {
  alert("Summary sent to the Electronic Medical Record!");
});
