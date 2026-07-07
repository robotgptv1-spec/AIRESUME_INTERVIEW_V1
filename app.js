// ---------- State ----------
let selectedDifficulty = "mid";
let resumeFile = null, jdFile = null;
let questions = [];
let currentQ = 0;
let timerInterval = null;
let timerSeconds = 0;
let recognition = null;
let isRecording = false;

// ---------- Ollama status check ----------
async function checkOllamaStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const dot = document.getElementById("ollamaDot");
    const text = document.getElementById("ollamaText");
    if (data.ollama_running) {
      dot.classList.add("online");
      text.textContent = data.models.length ? `Ollama ready (${data.models[0]})` : "Ollama running, no model pulled";
    } else {
      dot.classList.remove("online");
      text.textContent = "Ollama offline - run 'ollama serve'";
    }
  } catch (e) {
    document.getElementById("ollamaText").textContent = "Backend unreachable";
  }
}
checkOllamaStatus();
setInterval(checkOllamaStatus, 15000);

// ---------- Stage navigation ----------
function goToStage(name) {
  document.querySelectorAll(".stage").forEach(s => s.classList.remove("active"));
  document.getElementById(`stage-${name}`).classList.add("active");

  const order = ["upload", "screening", "interview", "report"];
  const idx = order.indexOf(name);
  document.querySelectorAll(".step").forEach(step => {
    const stepIdx = order.indexOf(step.dataset.step);
    step.classList.remove("active", "done");
    if (stepIdx < idx) step.classList.add("done");
    else if (stepIdx === idx) step.classList.add("active");
  });
}

// ---------- Difficulty pills ----------
document.querySelectorAll("#difficultyGroup .pill").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#difficultyGroup .pill").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    selectedDifficulty = btn.dataset.val;
  });
});

// ---------- File dropzones ----------
function setupDropzone(zoneId, inputId, nameId, fileSetter) {
  const zone = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  zone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    if (input.files[0]) {
      fileSetter(input.files[0]);
      document.getElementById(nameId).textContent = input.files[0].name;
      zone.classList.add("filled");
    }
  });
  ["dragover", "dragleave", "drop"].forEach(evt => {
    zone.addEventListener(evt, e => {
      e.preventDefault();
      if (evt === "dragover") zone.classList.add("drag");
      else zone.classList.remove("drag");
    });
  });
  zone.addEventListener("drop", e => {
    const file = e.dataTransfer.files[0];
    if (file) {
      input.files = e.dataTransfer.files;
      fileSetter(file);
      document.getElementById(nameId).textContent = file.name;
      zone.classList.add("filled");
    }
  });
}
setupDropzone("dropResume", "resumeFile", "resumeFileName", f => resumeFile = f);
setupDropzone("dropJD", "jdFile", "jdFileName", f => jdFile = f);

// ---------- Upload + Screening ----------
document.getElementById("btnScreen").addEventListener("click", async () => {
  const errorEl = document.getElementById("uploadError");
  errorEl.textContent = "";
  if (!resumeFile || !jdFile) {
    errorEl.textContent = "Dono files upload karo pehle";
    return;
  }
  const btn = document.getElementById("btnScreen");
  btn.disabled = true;
  btn.textContent = "Scanning...";

  const formData = new FormData();
  formData.append("resume", resumeFile);
  formData.append("jd", jdFile);
  formData.append("difficulty", selectedDifficulty);

  try {
    const res = await fetch("/api/upload", { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Upload fail hua");

    goToStage("screening");
    renderScreening(data.metrics);
  } catch (e) {
    errorEl.textContent = e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Screening →";
  }
});

function renderScreening(metrics) {
  const circumference = 553;
  const offset = circumference - (circumference * metrics.overall_score) / 100;
  setTimeout(() => {
    document.getElementById("ringFg").style.strokeDashoffset = offset;
  }, 200);

  let scoreCount = 0;
  const target = metrics.overall_score;
  const scoreEl = document.getElementById("ringScore");
  const anim = setInterval(() => {
    scoreCount += Math.max(1, target / 30);
    if (scoreCount >= target) { scoreCount = target; clearInterval(anim); }
    scoreEl.textContent = `${Math.round(scoreCount)}%`;
  }, 30);

  document.getElementById("semSim").textContent = `${metrics.semantic_similarity}%`;
  document.getElementById("skillCov").textContent = `${metrics.skill_coverage}%`;
  document.getElementById("matchedCount").textContent = `${metrics.matched_skills.length}`;

  document.getElementById("matchedSkills").innerHTML =
    metrics.matched_skills.map(s => `<span>${s}</span>`).join("") || "<span>None found</span>";
  document.getElementById("missingSkills").innerHTML =
    metrics.missing_skills.map(s => `<span>${s}</span>`).join("") || "<span>None 🎉</span>";

  setTimeout(() => {
    document.getElementById("metricsGrid").style.display = "grid";
    document.getElementById("skillsPanel").style.display = "grid";
    document.getElementById("btnStartInterview").style.display = "block";
  }, 900);
}

// ---------- Start interview ----------
document.getElementById("btnStartInterview").addEventListener("click", async () => {
  const btn = document.getElementById("btnStartInterview");
  btn.disabled = true;
  btn.textContent = "Generating questions...";
  try {
    const res = await fetch("/api/questions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ num_questions: 5 })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Questions generate nahi hue");
    questions = data.questions;
    currentQ = 0;
    goToStage("interview");
    showQuestion();
  } catch (e) {
    alert(e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "Start Mock Interview →";
  }
});

function showQuestion() {
  document.getElementById("qCurrentNum").textContent = currentQ + 1;
  document.getElementById("qTotalNum").textContent = questions.length;
  document.getElementById("questionText").textContent = questions[currentQ];
  document.getElementById("answerInput").value = "";
  document.getElementById("feedbackChip").style.display = "none";
  document.getElementById("btnSubmitAnswer").disabled = false;
  document.getElementById("btnSubmitAnswer").textContent = "Submit Answer";
  startTimer();
}

function startTimer() {
  clearInterval(timerInterval);
  timerSeconds = 0;
  document.getElementById("qTimer").textContent = "00:00";
  timerInterval = setInterval(() => {
    timerSeconds++;
    const m = String(Math.floor(timerSeconds / 60)).padStart(2, "0");
    const s = String(timerSeconds % 60).padStart(2, "0");
    document.getElementById("qTimer").textContent = `${m}:${s}`;
  }, 1000);
}

// ---------- Voice input (Web Speech API) ----------
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-IN";

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = 0; i < event.results.length; i++) transcript += event.results[i][0].transcript;
    document.getElementById("answerInput").value = transcript;
  };
  recognition.onend = () => {
    isRecording = false;
    document.getElementById("micBtn").classList.remove("recording");
  };
} else {
  document.getElementById("micBtn").title = "Voice input not supported in this browser";
}

document.getElementById("micBtn").addEventListener("click", () => {
  if (!recognition) return;
  if (isRecording) {
    recognition.stop();
  } else {
    recognition.start();
    isRecording = true;
    document.getElementById("micBtn").classList.add("recording");
  }
});

// ---------- Submit answer ----------
document.getElementById("btnSubmitAnswer").addEventListener("click", async () => {
  const answer = document.getElementById("answerInput").value.trim();
  if (!answer) { alert("Kuch toh likho ya bolo!"); return; }
  if (isRecording) recognition.stop();
  clearInterval(timerInterval);

  const btn = document.getElementById("btnSubmitAnswer");
  btn.disabled = true;
  btn.textContent = "Evaluating...";

  try {
    const res = await fetch("/api/answer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index: currentQ, answer })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Answer submit nahi hua");

    const chip = document.getElementById("feedbackChip");
    document.getElementById("chipScore").textContent = data.feedback.score !== null ? `${data.feedback.score}/10` : "–";
    document.getElementById("chipText").textContent = data.feedback.feedback;
    chip.style.display = "flex";

    setTimeout(() => {
      currentQ++;
      if (currentQ < questions.length) {
        showQuestion();
      } else {
        generateReport();
      }
    }, 1800);
  } catch (e) {
    alert(e.message);
    btn.disabled = false;
    btn.textContent = "Submit Answer";
  }
});

// ---------- Final report ----------
async function generateReport() {
  goToStage("report");
  document.getElementById("reportBody").textContent = "AI aapka final report taiyar kar raha hai...";
  try {
    const res = await fetch("/api/report", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Report generate nahi hua");

    document.getElementById("repFitment").textContent = `${data.match_metrics.overall_score}%`;
    document.getElementById("repAvgScore").textContent = `${data.avg_answer_score}/10`;
    document.getElementById("reportBody").textContent = data.report;
  } catch (e) {
    document.getElementById("reportBody").textContent = `Error: ${e.message}`;
  }
}

document.getElementById("btnDownload").addEventListener("click", () => {
  window.location.href = "/api/report/download";
});

document.getElementById("btnRestart").addEventListener("click", () => {
  window.location.reload();
});
