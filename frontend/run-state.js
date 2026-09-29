/* Shared, testable event state. No simulated agent progress. */
(function (root) {
  const STAGES = [
    ["Workspace", "Set the foundations", "Create an isolated project folder"],
    ["Planner", "Map the idea", "Turn your brief into coding tasks"],
    ["Architect", "Design the system", "Choose files, interfaces, and libraries"],
    ["Developer", "Make it real", "Write the project source code"],
    ["Tester", "Put it to the test", "Write and execute real tests"],
    ["Debugger", "Find the fix", "Repair source when tests fail"],
    ["Git", "Seal the handoff", "Commit the tested project"],
  ];
  function createState() {
    return {status: "idle", active: null, stages: Object.fromEntries(STAGES.map(([name]) =>
      [name, {status: "pending", visits: 0, elapsed: null}])), files: {}, repairs: 0, result: null, testOutput: ""};
  }
  function applyEvent(state, event) {
    const stage = state.stages[event.agent];
    if (event.type === "agent_start" && stage) {
      stage.status = "running"; stage.visits++; stage.elapsed = null;
      state.active = event.agent; state.status = "running";
      if (event.agent === "Debugger") state.repairs++;
    } else if (event.type === "retry" && stage) {
      stage.status = "retrying";
    } else if (event.type === "agent_end" && stage) {
      stage.status = event.status === "failed" || (event.agent === "Tester" && stage.status === "failed") ? "failed" : "done";
      stage.elapsed = event.elapsed_ms ?? null;
      if (state.active === event.agent) state.active = null;
    } else if (event.type === "agent_skip" && stage) {
      stage.status = "skipped";
    } else if (event.type === "agent_error" && stage) {
      stage.status = "failed"; stage.elapsed = event.elapsed_ms ?? null;
      state.active = event.agent;
    } else if (event.type === "file") {
      state.files[event.path] = event.agent === "Tester" ? "TEST" : "SOURCE";
    } else if (event.type === "test_result") {
      state.testOutput = event.output || "No test output returned.";
      if (event.status !== "PASSED") state.stages.Tester.status = "failed";
    } else if (event.type === "result") {
      const data = event.data;
      state.result = data; state.active = null;
      state.status = data.build_status === "COMPLETED" ? "completed" : "failed";
      state.repairs = data.debug_attempts ?? state.repairs;
      if (data.test_output) state.testOutput = data.test_output;
      for (const file of data.source_files || []) state.files[file] = "SOURCE";
      for (const file of data.test_files || []) state.files[file] = "TEST";
      if (data.test_status) state.stages.Tester.status = data.test_status === "PASSED" ? "done" : "failed";
      if (data.commit_status === "COMMITTED") state.stages.Git.status = "done";
      if (data.commit_status === "FAILED") state.stages.Git.status = "failed";
      if (!state.stages.Debugger.visits && data.test_status === "PASSED") state.stages.Debugger.status = "skipped";
      for (const item of Object.values(state.stages)) if (item.status === "pending") item.status = state.status === "failed" ? "blocked" : "skipped";
    } else if (event.type === "error") {
      state.status = "failed";
      if (state.active) state.stages[state.active].status = "failed";
      for (const item of Object.values(state.stages)) if (["pending", "running", "retrying"].includes(item.status)) item.status = "blocked";
      state.active = null;
    }
    return state;
  }
  async function consumeBuildStream(response, onEvent) {
    if (!response.body) throw new Error("This browser cannot read build progress.");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "", finished = false;
    function consumeLine(line) {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      if (event.type === "error") throw new Error(event.message || "Build failed.");
      if (event.type === "result") finished = true;
      onEvent(event);
    }
    try {
      while (true) {
        const {value, done} = await reader.read();
        buffer += decoder.decode(value, {stream: !done});
        let boundary;
        while ((boundary = buffer.indexOf("\n")) !== -1) {
          consumeLine(buffer.slice(0, boundary)); buffer = buffer.slice(boundary + 1);
        }
        if (done) { consumeLine(buffer); break; }
      }
      if (!finished) throw new Error("Build connection ended before a result arrived. Check the server before starting another build.");
    } finally {
      await reader.cancel().catch(() => {}); reader.releaseLock();
    }
  }
  const api = {STAGES, createState, applyEvent, consumeBuildStream};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RelayRun = api;
})(globalThis);
