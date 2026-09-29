// Run with RELAY_PLAYWRIGHT pointing to an installed playwright package.
// This server streams synthetic events; it never calls an LLM or runs generated code.
const assert = require("node:assert/strict");
const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const os = require("node:os");
const {chromium} = require(process.env.RELAY_PLAYWRIGHT || "playwright");
const frontend = path.resolve(__dirname, "../frontend");
let response, requests = 0;
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, "http://localhost").pathname;
  if (pathname === "/health") { res.setHeader("Content-Type", "application/json"); res.end('{"status":"ok"}'); return; }
  if (pathname === "/build/stream") { requests++; response = res; res.writeHead(200, {"Content-Type":"application/x-ndjson"}); res.flushHeaders(); return; }
  const file = pathname.endsWith("/") ? "index.html" : path.basename(pathname);
  if (!["index.html", "style.css", "script.js", "run-state.js"].includes(file)) { res.writeHead(404); res.end(); return; }
  res.setHeader("Content-Type", file.endsWith(".css") ? "text/css" : file.endsWith(".js") ? "text/javascript" : "text/html; charset=utf-8");
  res.end(fs.readFileSync(path.join(frontend, file)));
});
const send = event => response.write(JSON.stringify({...event, timestamp:new Date().toISOString()}) + "\n");
(async () => {
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const browser = await chromium.launch({headless:true, executablePath:process.env.RELAY_CHROME || "C:/Program Files/Google/Chrome/Application/chrome.exe"});
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1100}, reducedMotion:"reduce"});
    const page = await context.newPage();
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    await page.goto(`http://127.0.0.1:${server.address().port}/frontend/`);
    await page.locator('#connection[data-status="online"]').waitFor();
    assert.equal(await page.locator('.stage').count(), 7);
    await page.screenshot({path:path.join(os.tmpdir(), "relay-desktop.png"), fullPage:true});
    await page.locator('[data-example="converter"]').click();
    assert.match(await page.locator('#requirementInput').inputValue(), /celsius_to_fahrenheit/);
    await page.locator('#buildButton').click();
    await page.waitForFunction(() => document.getElementById('buildButton').disabled);
    while (!response) await new Promise(resolve => setTimeout(resolve, 10));
    send({type:"agent_start",agent:"Workspace",message:"Workspace started"});
    await page.locator('[data-agent="Workspace"][data-state="running"]').waitFor();
    send({type:"agent_end",agent:"Workspace",elapsed_ms:27});
    send({type:"agent_start",agent:"Planner",message:"Planner started"});
    await page.locator('[data-agent="Planner"][data-state="running"]').waitFor();
    assert.equal(await page.locator('[data-agent="Developer"]').getAttribute('data-state'), 'pending');
    send({type:"retry",agent:"Planner",message:"Provider retry in 2 seconds"});
    await page.locator('[data-agent="Planner"][data-state="retrying"]').waitFor();
    send({type:"agent_end",agent:"Planner",elapsed_ms:1200});
    send({type:"agent_start",agent:"Architect"}); send({type:"agent_end",agent:"Architect",elapsed_ms:230});
    send({type:"agent_start",agent:"Developer",message:"Developer started"});
    send({type:"file",agent:"Developer",path:"converter.py",message:"Saved converter.py"});
    await page.locator('[data-agent="Developer"][data-state="running"]').waitFor();
    await page.screenshot({path:path.join(os.tmpdir(), "relay-running.png"), fullPage:true});
    await page.evaluate(() => document.getElementById('buildForm').requestSubmit());
    assert.equal(requests, 1);
    send({type:"agent_end",agent:"Developer",elapsed_ms:3300});
    send({type:"agent_start",agent:"Tester"});
    send({type:"test_result",agent:"Tester",status:"FAILED",output:"AssertionError: example failed"});
    send({type:"agent_end",agent:"Tester",status:"failed",elapsed_ms:150});
    send({type:"agent_start",agent:"Debugger"});
    await page.locator('[data-agent="Debugger"][data-state="running"]').waitFor();
    assert.equal(await page.locator('#repairCount').innerText(), "01");
    send({type:"agent_end",agent:"Debugger",elapsed_ms:900});
    send({type:"agent_start",agent:"Tester"});
    send({type:"test_result",agent:"Tester",status:"PASSED",output:"5 passed"});
    send({type:"agent_end",agent:"Tester",status:"completed",elapsed_ms:123});
    send({type:"agent_start",agent:"Git"}); send({type:"agent_end",agent:"Git",status:"completed",elapsed_ms:200});
    send({type:"result",data:{build_status:"COMPLETED",test_status:"PASSED",commit_status:"COMMITTED",commit_hash:"abc12345",workspace:"C:\\projects\\converter",language:"Python",debug_attempts:1,source_files:["converter.py"],test_files:["tests/test_converter.py"],test_output:"5 passed"}});
    response.end();
    await page.locator('#liveFocus[data-status="completed"]').waitFor();
    await page.waitForFunction(() => !document.getElementById('buildButton').disabled);
    assert.equal(await page.locator('#commitValue').innerText(), 'abc12345');
    await page.locator('#testsTab').click(); assert.equal(await page.locator('#testOutput').innerText(), '5 passed');
    const download = page.waitForEvent('download'); await page.locator('#downloadLog').click();
    assert.equal((await download).suggestedFilename(), 'relay-build-log.txt');
    await page.locator('#buildButton').click();
    await page.waitForFunction(() => document.getElementById('buildButton').disabled);
    while (requests < 2) await new Promise(resolve => setTimeout(resolve, 10));
    send({type:"agent_start",agent:"Planner"});
    send({type:"error",message:"Provider unavailable <script>alert(1)</script>"}); response.end();
    await page.locator('#liveFocus[data-status="failed"]').waitFor();
    assert.equal(await page.locator('[data-agent="Git"]').getAttribute('data-state'), 'blocked');
    assert.match(await page.locator('#focusDescription').innerText(), /<script>/);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:path.join(os.tmpdir(), "relay-mobile.png"), fullPage:true});
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'No mobile horizontal overflow');
    assert.deepEqual(errors, []);
    console.log('Browser checks passed: desktop/mobile, live streamed stage transitions, retries, debugger loop, success, errors, log download, duplicate-submit guard.');
    console.log('Screenshots: ' + ['relay-desktop.png','relay-running.png','relay-mobile.png'].map(file=>path.join(os.tmpdir(),file)).join(', '));
  } finally { await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); }
})().catch(error => { console.error(error); process.exitCode=1; server.closeAllConnections(); server.close(); });
