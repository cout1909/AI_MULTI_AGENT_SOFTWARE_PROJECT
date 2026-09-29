const test = require("node:test");
const assert = require("node:assert/strict");
const {createState, applyEvent, consumeBuildStream} = require("../frontend/run-state.js");
function response(chunks) { return {body: new ReadableStream({start(controller) { for (const chunk of chunks) controller.enqueue(chunk); controller.close(); }})}; }
test("handles split JSON and multibyte UTF-8 across chunks", async () => {
  const bytes = new TextEncoder().encode('{"type":"file","message":"caf\u00e9"}\n{"type":"result","data":{}}\n');
  const events = [];
  await consumeBuildStream(response(Array.from(bytes, byte => Uint8Array.of(byte))), e => events.push(e));
  assert.equal(events[0].message, "caf\u00e9"); assert.equal(events[1].type, "result");
});
test("reports server errors and a truncated stream", async () => {
  const encode = text => [new TextEncoder().encode(text)];
  await assert.rejects(consumeBuildStream(response(encode('{"type":"error","message":"Service busy"}\n')), () => {}), /Service busy/);
  await assert.rejects(consumeBuildStream(response(encode('{"type":"agent_start"}\n')), () => {}), /before a result/);
});
test("stage motion follows actual starts and keeps unvisited stages queued", () => {
  const state = createState(); applyEvent(state, {type:"agent_start", agent:"Planner"});
  assert.equal(state.active, "Planner"); assert.equal(state.stages.Planner.status, "running"); assert.equal(state.stages.Developer.status, "pending");
  applyEvent(state, {type:"retry", agent:"Planner"}); assert.equal(state.stages.Planner.status, "retrying");
  applyEvent(state, {type:"agent_end", agent:"Planner", elapsed_ms:456});
  assert.equal(state.active, null); assert.equal(state.stages.Planner.elapsed, 456);
});
test("failed test pass survives stage end; debugger and retest are distinct passes", () => {
  const state = createState();
  applyEvent(state, {type:"agent_start", agent:"Tester"});
  applyEvent(state, {type:"test_result", status:"FAILED", output:"AssertionError"});
  applyEvent(state, {type:"agent_end", agent:"Tester"});
  assert.equal(state.stages.Tester.status, "failed");
  applyEvent(state, {type:"agent_start", agent:"Debugger"});
  assert.equal(state.repairs, 1);
  applyEvent(state, {type:"agent_end", agent:"Debugger"});
  applyEvent(state, {type:"agent_start", agent:"Tester"});
  assert.equal(state.stages.Tester.visits, 2); assert.equal(state.stages.Tester.status, "running");
  applyEvent(state, {type:"test_result", status:"PASSED", output:"2 passed"});
  applyEvent(state, {type:"agent_end", agent:"Tester"});
  assert.equal(state.stages.Tester.status, "done");
});
test("skips debugger without inventing activity and exposes commit failure", () => {
  const state = createState(); applyEvent(state, {type:"agent_skip", agent:"Debugger"});
  assert.equal(state.stages.Debugger.visits, 0);
  applyEvent(state, {type:"result", data:{build_status:"FAILED", test_status:"PASSED", commit_status:"FAILED"}});
  assert.equal(state.status, "failed"); assert.equal(state.stages.Git.status, "failed"); assert.equal(state.stages.Tester.status, "done");
});
test("disconnect marks the active agent failed, counts unique files, and blocks pending work", () => {
  const state = createState();
  applyEvent(state, {type:"agent_start", agent:"Developer"});
  applyEvent(state, {type:"file", agent:"Developer", path:"a.py"});
  applyEvent(state, {type:"file", agent:"Debugger", path:"a.py"});
  applyEvent(state, {type:"error"});
  assert.equal(Object.keys(state.files).length, 1); assert.equal(state.stages.Developer.status, "failed"); assert.equal(state.stages.Git.status, "blocked");
});
