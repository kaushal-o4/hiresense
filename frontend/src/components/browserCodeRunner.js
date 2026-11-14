// HIRESENSE COMMENT INDEX - START
// ------------------------------------------------------------
// FILE NAME:
// frontend/src/components/browserCodeRunner.js
//
// FILE PURPOSE:
// Lets a student test their JavaScript coding answer against sample test cases inside the browser.
//
// WHAT THIS FILE DOES:
// 1. Creates a Web Worker from a small script.
// 2. Runs the student's function on each test case and compares the output.
// 3. Stops the worker after a timeout (to catch infinite loops).
//
// HOW THIS FILE WORKS:
// The code runs in a separate worker thread with no access to the page. Results come back by
// postMessage.
//
// IMPORTANT FUNCTIONS:
//    - runJavaScript()
//        Runs code + function name + test cases in a worker and resolves with results or an
//        error.
//
// INPUT:
// Student code, function name, test cases, timeout.
//
// OUTPUT:
// A promise with pass/fail per test case.
//
// FILES CONNECTED TO THIS FILE:
//    Used by: pages/student/StudentAssessments.jsx
//
// IMPORTANT NOTE:
// This is only for self-checking. The official grade comes from the backend's AI code review.
//
// ------------------------------------------------------------
// HIRESENSE COMMENT INDEX - END
// Runs a student's JavaScript function against sample test cases inside a Web Worker, for self-checking only.
// The worker has no access to the page; it is terminated after a timeout to stop infinite loops.
// Official grading happens on the server (AI review) - this runner never decides the score.

const WORKER_SRC = `
self.onmessage = (e) => {
  const { code, fn, cases } = e.data;
  try {
    const f = new Function(code + "\\n;return typeof " + fn + " === 'function' ? " + fn + " : undefined;")();
    if (!f) throw new Error("Function '" + fn + "' was not found in your code");
    const results = cases.map((c) => {
      try {
        const out = f(...(c.input || []));
        return { ok: JSON.stringify(out) === JSON.stringify(c.expected), output: out === undefined ? "undefined" : JSON.stringify(out) };
      } catch (err) {
        return { ok: false, error: String(err) };
      }
    });
    self.postMessage({ results });
  } catch (err) {
    self.postMessage({ error: String(err) });
  }
};`;

export function runJavaScript(code, fn, cases, timeoutMs = 3000) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(new Blob([WORKER_SRC], { type: "text/javascript" }));
    const worker = new Worker(url);
    const done = (value) => { clearTimeout(timer); worker.terminate(); URL.revokeObjectURL(url); resolve(value); };
    const timer = setTimeout(() => done({ error: `Timed out after ${timeoutMs / 1000}s - check for infinite loops.` }), timeoutMs);
    worker.onmessage = (e) => done(e.data);
    worker.onerror = (e) => done({ error: e.message || "Syntax error in your code" });
    worker.postMessage({ code, fn, cases });
  });
}
