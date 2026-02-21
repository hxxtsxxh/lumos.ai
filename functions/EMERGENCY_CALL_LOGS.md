# Emergency call (VAPI) — Logging & debugging

## Where to see logs

### 1. Firebase / Google Cloud (backend)

- **Firebase Console**: [Console](https://console.firebase.google.com/) → your project → **Build** → **Functions** → **Logs**.
- **Google Cloud Logging**: [Cloud Logging](https://console.cloud.google.com/logs) → filter by resource type **Cloud Function** and function name `vapiLlm` or `startEmergencyCall`.

All functions log JSON lines with:

- **vapiLlm**: `messageCount`, `stream`, `responseLength`, `durationMs`, `firstChars` of reply, and any `error`/`stack`.
- **startEmergencyCall**: payload summary, VAPI LLM URL, `callId`, and errors.

Use these to check:

- Whether **vapiLlm** is called more than once (conversation turns). If you only see one `vapiLlm` log per call, VAPI may not be sending follow-up turns.
- Whether **vapiLlm** returns a non-empty response (`responseLength` > 0) and no errors.
- Whether **stream** is `true`; if so, VAPI may expect streaming and our non-streaming reply might cause issues.

### 2. Browser (frontend)

- Open DevTools → **Console**.
- Look for `[LUMOS emergency]` and `[EmergencyCallModal]` logs when you start a call, send an update, or end the call.

## After code changes

| Change | What to do |
|--------|------------|
| **Firebase Functions** (`functions/index.js`) | Redeploy: `npm run firebase:deploy` (or `npx firebase-tools deploy --only functions`). No need to rerun `npm run dev` or the Python backend. |
| **Frontend** (e.g. `src/`) | Restart or rely on Vite HMR; no need to redeploy functions. |
| **Python backend** | Only needed if you use `VITE_USE_FIREBASE_EMERGENCY=false` and the Python emergency-call endpoints. |

## If the agent stops after the first prompt

1. In **Firebase/Cloud logs**, confirm **vapiLlm** is invoked for **each** operator turn (multiple log entries per call with increasing `messageCount`).
2. If **vapiLlm** is only called once, the problem is likely on the **VAPI** side (assistant config, custom LLM URL, or timeout).
3. If **vapiLlm** is called multiple times but the operator hears nothing after the first reply, check for **errors** in those log entries and that **responseLength** and **firstChars** look correct.
4. If VAPI is sending **stream: true**, consider implementing SSE streaming in **vapiLlm** so the response is streamed instead of a single JSON body.
