"use strict";
const {STAGES, createState, applyEvent, consumeBuildStream} = window.RelayRun;
const $ = id => document.getElementById(id);
let state = createState(), busy = false, startedAt = 0, clock = null, events = [];
const descriptions = Object.fromEntries(STAGES.map(([name, title, description]) => [name, {title, description}]));
const examples = {
  converter: "Build Python functions celsius_to_fahrenheit(celsius) and fahrenheit_to_celsius(fahrenheit). Test freezing, boiling, -40, and round-trip conversions.",
  text: "Build Python functions to count words, sentences, and character frequencies in a string. Handle empty input and punctuation. Use only the standard library.",
  calculator: "Build Python functions for addition, subtraction, multiplication, and division. Raise ValueError for division by zero. Include tests for negative numbers and decimals.",
};
for (const [index, [name, title, description]] of STAGES.entries()) {
  const row = document.createElement("li"); row.className = "stage"; row.dataset.agent = name;
  const number = document.createElement("span"); number.className = "stage-number"; number.textContent = String(index + 1).padStart(2, "0");
  const copy = document.createElement("div"); copy.className = "stage-copy";
  const label = document.createElement("strong"); label.textContent = name;
  const note = document.createElement("p"); note.textContent = title;
  copy.append(label, note);
  const status = document.createElement("span"); status.className = "stage-status";
  row.append(number, copy, status); $("stageList").append(row);
}
function announce(message) { $("announcement").textContent = message; }
function renderStages() {
  for (const [index, [name]] of STAGES.entries()) {
    const value = state.stages[name];
    const row = document.querySelector(`[data-agent="${name}"]`);
    row.dataset.state = value.status;
    row.querySelector(".stage-number").textContent = value.status === "done" ? "✓" : value.status === "failed" ? "!" : String(index + 1).padStart(2, "0");
    const labels = {pending: name === "Debugger" ? "If needed" : "Queued", running: "Working", retrying: "Retrying", done: "Done", failed: "Needs attention", skipped: "Not needed", blocked: "Not reached"};
    let label = labels[value.status];
    if (value.elapsed !== null && value.status === "done") label += ` · ${(value.elapsed / 1000).toFixed(1)}s`;
    if (value.visits > 1 && value.status === "running") label += ` · pass ${value.visits}`;
    row.querySelector(".stage-status").textContent = label;
    row.setAttribute("aria-label", `${name}: ${label}`);
    if (["running", "retrying"].includes(value.status)) row.setAttribute("aria-current", "step"); else row.removeAttribute("aria-current");
  }
  $("fileCount").textContent = String(Object.keys(state.files).length).padStart(2, "0");
  $("repairCount").textContent = String(state.repairs).padStart(2, "0");
  $("liveFocus").dataset.status = state.status;
  $("liveDot").classList.toggle("running", state.status === "running");
  $("runBadge").textContent = {idle: "Standing by", running: "Live build", completed: "Delivered", failed: "Needs attention"}[state.status];
}
function focusStage(agent) {
  $("focusEyebrow").textContent = `${agent.toUpperCase()} / IN PROGRESS`;
  $("focusTitle").textContent = descriptions[agent]?.title || agent;
  $("focusDescription").textContent = descriptions[agent]?.description || "Working on your project.";
}
function addEvent(event) {
  events.push({...event, timestamp: event.timestamp || new Date().toISOString()});
  if (events.length === 1) $("feed").replaceChildren();
  const container = $("feed"), follow = container.scrollHeight - container.scrollTop - container.clientHeight < 50;
  const row = document.createElement("div"); row.className = "feed-row"; row.dataset.type = event.type;
  const time = document.createElement("time"); const timestamp = events[events.length - 1].timestamp;
  time.dateTime = timestamp; time.textContent = new Date(timestamp).toLocaleTimeString([], {hour12:false});
  const message = document.createElement("p"); message.textContent = event.message || event.type;
  row.append(time, message); container.append(row);
  if (follow) container.scrollTop = container.scrollHeight;
  $("eventCount").textContent = events.length; $("downloadLog").disabled = false;
}
function renderFiles() {
  $("fileList").replaceChildren();
  for (const [path, kind] of Object.entries(state.files)) {
    const item = document.createElement("li"); item.className = "file-item";
    const name = document.createElement("span"); name.textContent = path;
    const tag = document.createElement("small"); tag.textContent = kind;
    item.append(name, tag); $("fileList").append(item);
  }
  if (!Object.keys(state.files).length) {
    const item = document.createElement("li"); item.className = "file-item"; item.textContent = "No files saved in this run."; $("fileList").append(item);
  }
}
function showResult(data) {
  const success = data.build_status === "COMPLETED";
  $("outputEmpty").hidden = true; $("outputContent").hidden = false;
  $("outputBadge").textContent = success ? "Ready to explore" : "Build incomplete";
  $("outcome").dataset.status = success ? "completed" : "failed";
  const message = success ? "Built, tested, and committed. It's yours." : data.test_status === "PASSED" ? "Tests passed. The Git commit needs attention." : "Tests did not pass. Your saved files are still available.";
  $("outcome").textContent = message;
  $("testStatus").textContent = data.test_status || "Not run";
  $("languageValue").textContent = data.language || "—";
  $("commitValue").textContent = data.commit_status === "COMMITTED" ? (data.commit_hash || "Committed").slice(0, 8) : data.commit_status === "FAILED" ? "Failed" : "Not attempted";
  $("workspacePath").textContent = data.workspace || "Location unavailable";
  $("copyPath").disabled = !data.workspace;
  $("focusEyebrow").textContent = success ? "THE HANDOFF / COMPLETE" : "BUILD / NEEDS ATTENTION";
  $("focusTitle").textContent = success ? "An idea, now a real project." : "Let's look at what happened.";
  $("focusDescription").textContent = message;
  renderFiles(); announce(message);
  addEvent({type: success ? "complete" : "error", message});
  if (data.commit_status === "FAILED" && data.commit_output) addEvent({type:"error", message:data.commit_output});
}
function handleEvent(event) {
  applyEvent(state, event);
  if (event.message) addEvent(event);
  if (event.type === "agent_start") { focusStage(event.agent); announce(`${event.agent} is working.`); }
  if (event.type === "retry") { $("focusDescription").textContent = event.message; announce(event.message); }
  if (event.type === "test_result") {
    $("testOutput").textContent = state.testOutput;
    $("testsTab").textContent = `Test output · ${event.status === "PASSED" ? "Passed" : "Failed"}`;
  }
  if (event.type === "file") {
    $("outputEmpty").hidden = true; $("outputContent").hidden = false;
    $("outputBadge").textContent = "Taking shape"; $("outcome").textContent = "Files are being saved as your crew works."; renderFiles();
  }
  if (event.type === "result") { $("testOutput").textContent = state.testOutput || "No tests have run yet."; showResult(event.data); }
  renderStages();
}
function updateClock() {
  const seconds = Math.floor((performance.now() - startedAt) / 1000);
  $("elapsed").textContent = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}
async function buildProject(event) {
  event?.preventDefault();
  if (busy) return;
  const requirement = $("requirementInput").value.trim();
  if (!requirement) { $("requirementInput").setCustomValidity("Tell the crew what you want to build."); $("requirementInput").reportValidity(); return; }
  busy = true; state = createState(); state.status = "running"; events = [];
  $("feed").replaceChildren(); $("eventCount").textContent = "0";
  $("outputEmpty").hidden = false; $("outputContent").hidden = true; $("outputBadge").textContent = "Waiting for files";
  $("outcome").dataset.status = "running"; $("workspacePath").textContent = "Available when the build finishes.";
  $("testStatus").textContent = "Not run"; $("languageValue").textContent = "Python"; $("commitValue").textContent = "Not attempted";
  $("copyPath").disabled = true; $("copyPath").textContent = "Copy path ↗";
  $("testOutput").textContent = "Tests will appear when the Tester finishes a pass."; $("testsTab").textContent = "Test output";
  $("buildButton").disabled = true; $("buildButtonLabel").textContent = "Your crew is on it"; $("requirementInput").disabled = true;
  document.querySelectorAll(".sample").forEach(button => button.disabled = true);
  $("focusEyebrow").textContent = "BUILD / CONNECTING"; $("focusTitle").textContent = "Sending your brief."; $("focusDescription").textContent = "Waiting for the first agent update.";
  startedAt = performance.now(); updateClock(); clock = setInterval(updateClock, 1000); renderStages(); selectTab("activity");
  addEvent({type:"request", message:"Brief sent. Waiting for the crew to start."});
  try {
    const response = await fetch("/build/stream", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({requirement})});
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = Array.isArray(data.detail) ? data.detail.map(item => item.msg).join("; ") : data.detail;
      throw new Error(detail || `Build request failed (${response.status}).`);
    }
    await consumeBuildStream(response, handleEvent);
  } catch (error) {
    applyEvent(state, {type:"error"}); renderStages();
    $("focusEyebrow").textContent = "BUILD / STOPPED"; $("focusTitle").textContent = "The crew hit a roadblock."; $("focusDescription").textContent = error.message;
    $("outputBadge").textContent = "Build stopped";
    $("outputEmpty").hidden = true; $("outputContent").hidden = false;
    $("outcome").dataset.status = "failed"; $("outcome").textContent = error.message; renderFiles();
    addEvent({type:"error", message:error.message}); announce(error.message);
  } finally {
    clearInterval(clock); clock = null; updateClock(); busy = false;
    $("buildButton").disabled = false; $("buildButtonLabel").textContent = "Build another idea"; $("requirementInput").disabled = false;
    document.querySelectorAll(".sample").forEach(button => button.disabled = false);
  }
}
function selectTab(tab) {
  for (const name of ["activity", "tests"]) {
    const active = name === tab; const button = $(name + "Tab");
    button.setAttribute("aria-selected", String(active)); button.tabIndex = active ? 0 : -1;
    $(name === "activity" ? "feedPanel" : "testsPanel").hidden = !active;
  }
}
$("buildForm").addEventListener("submit", buildProject);
$("requirementInput").addEventListener("input", () => { $("requirementInput").setCustomValidity(""); $("charCount").textContent = `${$("requirementInput").value.length.toLocaleString()} / 20,000`; });
$("requirementInput").addEventListener("keydown", event => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); if (!busy) $("buildForm").requestSubmit(); } });
document.querySelectorAll(".sample").forEach(button => button.addEventListener("click", () => { $("requirementInput").value = examples[button.dataset.example]; $("requirementInput").dispatchEvent(new Event("input")); $("requirementInput").focus(); }));
for (const name of ["activity", "tests"]) {
  $(name + "Tab").addEventListener("click", () => selectTab(name));
  $(name + "Tab").addEventListener("keydown", event => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
      event.preventDefault(); const target = event.key === "Home" ? "activity" : event.key === "End" ? "tests" : name === "activity" ? "tests" : "activity";
      selectTab(target); $(target + "Tab").focus();
    }
  });
}
$("copyPath").addEventListener("click", async () => {
  try { await navigator.clipboard.writeText(state.result.workspace); $("copyPath").textContent = "Copied ✓"; announce("Project location copied."); }
  catch { announce("Clipboard unavailable. Select and copy the project location below."); $("copyPath").textContent = "Select path below"; }
});
$("downloadLog").addEventListener("click", () => {
  const text = events.map(event => `[${event.timestamp}] ${event.message || event.type}${event.output ? "\n" + event.output : ""}`).join("\n");
  const url = URL.createObjectURL(new Blob([text], {type:"text/plain;charset=utf-8"}));
  const link = document.createElement("a"); link.href = url; link.download = "relay-build-log.txt"; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
async function checkConnection() {
  try { const response = await fetch("/health", {signal:AbortSignal.timeout(5000)}); if (!response.ok) throw new Error(); $("connection").dataset.status = "online"; $("connectionLabel").textContent = "Studio connected"; }
  catch { $("connection").dataset.status = "offline"; $("connectionLabel").textContent = "Server unavailable"; }
}
renderStages(); checkConnection();
window.addEventListener("focus", checkConnection);
