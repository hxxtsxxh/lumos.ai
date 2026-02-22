/**
 * LUMOS Firebase Cloud Functions — Emergency call (VAPI + Gemini + Realtime Database)
 *
 * Architecture:
 *   1. startEmergencyCall → stores call context in RTDB at /calls/{callId}, starts VAPI call
 *   2. vapiLlm → VAPI sends conversation here for each LLM turn; we read pending RTDB
 *      updates and include them in the Gemini prompt so the agent speaks them
 *   3. emergencyCallMessage → frontend writes GPS/text updates to RTDB + tries VAPI Say API
 *   4. emergencyCallEnd → hangs up VAPI call + cleans RTDB
 */

const { onRequest, onCall, HttpsError } = require("firebase-functions/v2/https");
const { setGlobalOptions } = require("firebase-functions/v2");
const admin = require("firebase-admin");

admin.initializeApp({
  databaseURL: process.env.RTDB_URL || "https://lumos-b2c23-rtdb.firebaseio.com",
});

setGlobalOptions({ maxInstances: 20 });

function env(name, fallback = "") {
  return process.env[name] ?? fallback;
}

const db = admin.database();

// ─────────────────────────────────────────────────────────────────────────────
// Reverse geocode helper (Google Maps)
// ─────────────────────────────────────────────────────────────────────────────
async function reverseGeocode(lat, lng) {
  const key = env("GOOGLE_MAPS_API_KEY");
  if (!key) return null;
  try {
    const res = await fetch(
      `https://maps.googleapis.com/maps/api/geocode/json?latlng=${lat},${lng}&key=${key}`
    );
    const data = await res.json();
    if (data.status === "OK" && data.results?.length) {
      return data.results[0].formatted_address;
    }
  } catch {
    // ignore
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Gemini helper
// ─────────────────────────────────────────────────────────────────────────────
async function generateWithGemini(messages, geminiKey) {
  if (!geminiKey || !messages || messages.length === 0) {
    throw new Error("GEMINI_API_KEY required and messages must be non-empty");
  }

  const contents = [];
  let systemPrompt = null;

  for (const msg of messages) {
    const role = (msg.role || "user").toLowerCase();
    const text =
      typeof msg.content === "string"
        ? msg.content
        : msg.content?.[0]?.text || "";
    if (!text) continue;

    if (role === "system") {
      systemPrompt = text;
      continue;
    }
    contents.push({
      role: role === "assistant" ? "model" : "user",
      parts: [{ text }],
    });
  }

  if (systemPrompt) {
    contents.unshift({
      role: "user",
      parts: [{ text: `[System instructions]\n${systemPrompt}` }],
    });
  }

  // Gemini requires strict user/model alternation
  const normalized = [];
  for (const c of contents) {
    if (
      normalized.length > 0 &&
      normalized[normalized.length - 1].role === c.role &&
      c.role === "user"
    ) {
      normalized.push({ role: "model", parts: [{ text: "(ack)" }] });
    }
    normalized.push(c);
  }

  const toSend = normalized.length > 0 ? normalized : contents;
  if (toSend.length === 0) throw new Error("No message content for Gemini");

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${geminiKey}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      contents: toSend,
      generationConfig: { temperature: 0.3, maxOutputTokens: 250 },
    }),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini ${res.status}: ${errText.slice(0, 500)}`);
  }

  const data = await res.json();
  const candidate = data.candidates?.[0];
  if (!candidate?.content?.parts?.length) {
    throw new Error("Gemini returned no content");
  }
  return candidate.content.parts.map((p) => p.text).join("");
}

// ─────────────────────────────────────────────────────────────────────────────
// vapiLlm — Custom LLM endpoint that VAPI calls for every conversation turn
// ─────────────────────────────────────────────────────────────────────────────
exports.vapiLlm = onRequest(
  { cors: true, timeoutSeconds: 60 },
  async (req, res) => {
    const logId = `llm-${Date.now().toString(36)}`;
    const log = (lvl, msg, d = {}) =>
      console.log(JSON.stringify({ lvl, logId, msg, ...d }));

    try {
      if (req.method !== "POST") {
        res.status(405).send("Method Not Allowed");
        return;
      }

      const body = req.body ?? {};
      const messages = Array.isArray(body.messages) ? body.messages : [];

      log("info", "vapiLlm request", {
        msgCount: messages.length,
        lastRole: messages[messages.length - 1]?.role,
      });

      // ── Inject pending RTDB updates into conversation ──
      // Look for the callId in the system prompt or call metadata
      let callId = body.call?.id || body.metadata?.callId || null;

      // Try to find callId from VAPI call object
      if (!callId && body.call) {
        callId = body.call.id;
      }

      if (callId) {
        try {
          const updatesSnap = await db
            .ref(`calls/${callId}/pendingUpdates`)
            .once("value");
          const updates = updatesSnap.val();
          if (updates) {
            // Collect all pending updates, inject them as user messages
            const updateTexts = [];
            for (const [key, update] of Object.entries(updates)) {
              updateTexts.push(update.message || update);
            }
            if (updateTexts.length > 0) {
              const injectedMessage = updateTexts.join("\n");
              log("info", "vapiLlm injecting RTDB updates", {
                count: updateTexts.length,
                preview: injectedMessage.slice(0, 100),
              });
              // Insert as the latest user message so the LLM responds to it
              messages.push({
                role: "user",
                content: injectedMessage,
              });
            }
            // Clear processed updates
            await db.ref(`calls/${callId}/pendingUpdates`).remove();
          }
        } catch (rtdbErr) {
          log("warn", "vapiLlm RTDB read failed", { error: rtdbErr.message });
        }
      }

      const geminiKey = env("GEMINI_API_KEY");
      if (!geminiKey) {
        log("error", "GEMINI_API_KEY not set");
        res.status(500).json({ error: "GEMINI_API_KEY not configured" });
        return;
      }

      const assistantText = await generateWithGemini(messages, geminiKey);
      log("info", "vapiLlm response", {
        len: assistantText.length,
        preview: assistantText.slice(0, 100),
      });

      res.status(200).json({
        id: `chatcmpl-${logId}`,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: body.model || "gpt-3.5-turbo",
        choices: [
          {
            index: 0,
            message: { role: "assistant", content: assistantText },
            finish_reason: "stop",
          },
        ],
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
      });
    } catch (err) {
      log("error", "vapiLlm failed", { error: err.message, stack: err.stack });
      res.status(500).json({ error: err.message });
    }
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// startEmergencyCall — Creates VAPI outbound call + stores context in RTDB
// ─────────────────────────────────────────────────────────────────────────────
exports.startEmergencyCall = onCall(async (request) => {
  const logId = `start-${Date.now().toString(36)}`;
  const log = (lvl, msg, d = {}) =>
    console.log(JSON.stringify({ lvl, logId, msg, ...d }));

  if (request.auth) {
    log("info", "authenticated", { uid: request.auth.uid });
  }

  const p = request.data || {};
  const {
    callerName, callerAge, lat, lng, address, safetyScore,
    incidentType, severity, userNotes, medicalConditions,
    emergencyContactName, emergencyContactPhone,
    movementDirection, movementSpeed,
  } = p;

  log("info", "payload", { callerName, lat, lng, incidentType, severity });

  const vapiKey = env("VAPI_API_KEY");
  const phoneNumberId = env("VAPI_PHONE_NUMBER_ID");
  const toNumber = env("DEMO_EMERGENCY_NUMBER");

  if (!vapiKey || !phoneNumberId || !toNumber) {
    log("error", "missing env", {
      hasVapiKey: !!vapiKey,
      hasPhoneNumberId: !!phoneNumberId,
      hasToNumber: !!toNumber,
    });
    throw new HttpsError(
      "failed-precondition",
      "VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, DEMO_EMERGENCY_NUMBER must be set"
    );
  }

  // ── Build first spoken message (full info dump) ──
  const nameStr = callerName || "Unknown";
  const ageStr = callerAge ? `, ${callerAge} years old` : "";
  const incidentStr = incidentType || "unspecified emergency";
  const severityStr = severity || "HIGH";

  const latStr = Number(lat).toFixed(4);
  const lngStr = Number(lng).toFixed(4);

  // Reverse geocode if no address provided
  let locationStr = address || null;
  if (!locationStr && lat && lng) {
    locationStr = await reverseGeocode(lat, lng);
    log("info", "reverse geocoded", { locationStr });
  }
  locationStr = locationStr || "Unknown address";

  const firstMessage = [
    `Hello, this is LUMOS AI calling on behalf of ${nameStr}${ageStr}. They cannot speak safely.`,
    `Emergency: ${incidentStr}, severity ${severityStr}.`,
    `Location: ${locationStr}, coordinates ${latStr}, ${lngStr}.`,
    medicalConditions ? `Medical: ${medicalConditions}.` : null,
    emergencyContactName
      ? `Emergency contact: ${emergencyContactName}${emergencyContactPhone ? ` at ${emergencyContactPhone}` : ""}.`
      : null,
    userNotes ? `Caller notes: ${userNotes}.` : null,
    `I will relay live updates every 30 seconds. Please dispatch help.`,
  ]
    .filter(Boolean)
    .join(" ");

  // ── System prompt (behavior after opening) ──
  const systemPrompt = [
    `You are LUMOS AI, an automated emergency relay system on a live 911 call.`,
    `You already delivered a full situation report in your opening message.`,
    ``,
    `Your job now:`,
    `1. RELAY UPDATES — You will receive LOCATION UPDATE messages with new GPS coordinates. Read them out immediately: "Location update: caller is now at [address], [lat, lng]."`,
    `2. RELAY CALLER MESSAGES — You will receive text messages from the caller. Read them verbatim: "Message from the caller: [message]."`,
    `3. ANSWER OPERATOR QUESTIONS — Answer directly using info you have. One sentence max. If unknown: "I don't have that information."`,
    `4. If operator asks to speak to caller: "The caller cannot speak safely. I can relay messages."`,
    `5. DO NOT repeat the full report unless asked.`,
    `6. DO NOT make small talk or fill silence. Stay silent when nobody speaks.`,
    `7. NEVER hang up. Only the caller can end the call.`,
    ``,
    `Reference:`,
    `Name: ${nameStr}${ageStr}`,
    `Location: ${locationStr} (${latStr}, ${lngStr})`,
    `Emergency: ${incidentStr}, ${severityStr}`,
    medicalConditions ? `Medical: ${medicalConditions}` : "",
    emergencyContactName
      ? `Contact: ${emergencyContactName}${emergencyContactPhone ? ` (${emergencyContactPhone})` : ""}`
      : "",
  ]
    .filter((l) => l !== "")
    .join("\n");

  // ── LLM URL — use the actual Cloud Run URL from env ──
  const llmUrl = env("VAPI_LLM_BASE_URL") || "https://vapillm-76apa66mcq-uc.a.run.app";
  const webhookUrl = env("VAPI_WEBHOOK_URL") || "https://vapiwebhook-76apa66mcq-uc.a.run.app";

  log("info", "VAPI LLM URL", { llmUrl, webhookUrl });

  const assistant = {
    name: "LUMOS Emergency",
    firstMessage,
    firstMessageMode: "assistant-speaks-first",
    model: {
      provider: "custom-llm",
      url: llmUrl,
      model: "gpt-3.5-turbo",
      messages: [{ role: "system", content: systemPrompt }],
    },
    voice: {
      provider: "11labs",
      voiceId: env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
    },
    transcriber: {
      provider: "deepgram",
      model: "nova-2",
      language: "en",
    },
    maxDurationSeconds: 3600,
    endCallFunctionEnabled: false,
    endCallMessage: "",
    endCallPhrases: [],
    voicemailDetection: "off",
    monitorPlan: {
      listenEnabled: false,
      controlEnabled: true,
    },
    serverUrl: webhookUrl,
  };

  const vapiBody = {
    phoneNumberId,
    customer: { number: toNumber },
    assistant,
  };

  try {
    const vapiRes = await fetch("https://api.vapi.ai/call", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${vapiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(vapiBody),
    });

    const vapiData = await vapiRes.json().catch(() => ({}));

    log("info", "VAPI response", {
      status: vapiRes.status,
      id: vapiData.id,
      keys: Object.keys(vapiData).join(","),
      body: JSON.stringify(vapiData).slice(0, 1500),
    });

    if (!vapiRes.ok) {
      throw new HttpsError(
        "internal",
        vapiData.message || `VAPI returned ${vapiRes.status}`
      );
    }

    const callId = vapiData.id || vapiData.callId || vapiData.call?.id;
    if (!callId) {
      throw new HttpsError("internal", "VAPI did not return a call id");
    }

    // ── Extract controlUrl from VAPI response ──
    const controlUrl = vapiData.monitor?.controlUrl || null;
    log("info", "VAPI monitor", { controlUrl: controlUrl ? controlUrl.slice(0, 80) : "none" });

    // ── Store call context in RTDB ──
    await db.ref(`calls/${callId}`).set({
      createdAt: Date.now(),
      callerName: nameStr,
      location: { lat, lng, address: locationStr },
      incident: { type: incidentStr, severity: severityStr },
      status: "active",
      controlUrl: controlUrl || null,
    });

    log("info", "call started + RTDB written", { callId });

    return {
      callId,
      status: "started",
      message: "Call initiated. LUMOS AI is speaking to the operator.",
    };
  } catch (err) {
    if (err instanceof HttpsError) throw err;
    log("error", "startEmergencyCall exception", { error: err.message });
    throw new HttpsError("internal", err.message);
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// emergencyCallMessage — Write update to RTDB + try VAPI Say API
// ─────────────────────────────────────────────────────────────────────────────
exports.emergencyCallMessage = onCall(async (request) => {
  const logId = `msg-${Date.now().toString(36)}`;
  const log = (lvl, msg, d = {}) =>
    console.log(JSON.stringify({ lvl, logId, msg, ...d }));

  const { callId, message } = request.data || {};
  if (!callId || !message) {
    throw new HttpsError("invalid-argument", "callId and message required");
  }

  log("info", "emergencyCallMessage", { callId, len: message.length });

  // ── Write to RTDB so vapiLlm picks it up on next turn ──
  const updateKey = `${Date.now()}`;
  try {
    await db.ref(`calls/${callId}/pendingUpdates/${updateKey}`).set({
      message,
      ts: Date.now(),
    });
    log("info", "RTDB update written", { callId, key: updateKey });
  } catch (rtdbErr) {
    log("warn", "RTDB write failed", { error: rtdbErr.message });
  }

  // ── Use VAPI control URL to inject speech ──
  try {
    // Read controlUrl from RTDB
    const callSnap = await db.ref(`calls/${callId}/controlUrl`).once("value");
    const controlUrl = callSnap.val();

    if (controlUrl) {
      // Use "add-message" to inject into conversation and trigger LLM response
      const ctrlRes = await fetch(controlUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "say",
          content: message,
          endCallAfterSpoken: false,
        }),
      });
      if (!ctrlRes.ok) {
        const errText = await ctrlRes.text();
        log("warn", "VAPI control say failed", {
          status: ctrlRes.status,
          body: errText.slice(0, 300),
        });
      } else {
        log("info", "VAPI control say success", { callId });
        // Control API delivered the message, remove from pending
        await db
          .ref(`calls/${callId}/pendingUpdates/${updateKey}`)
          .remove()
          .catch(() => {});
      }
    } else {
      log("warn", "no controlUrl found in RTDB", { callId });
    }
  } catch (err) {
    log("warn", "VAPI control exception", { error: err.message });
    // Update stays in RTDB for vapiLlm to pick up
  }

  return { ok: true };
});

// ─────────────────────────────────────────────────────────────────────────────
// emergencyCallEnd — Hang up + clean RTDB
// ─────────────────────────────────────────────────────────────────────────────
exports.emergencyCallEnd = onCall(async (request) => {
  const logId = `end-${Date.now().toString(36)}`;
  const log = (lvl, msg, d = {}) =>
    console.log(JSON.stringify({ lvl, logId, msg, ...d }));

  const { callId } = request.data || {};
  if (!callId) {
    throw new HttpsError("invalid-argument", "callId required");
  }

  // ── Try VAPI control URL first, then REST API ──
  try {
    const callSnap = await db.ref(`calls/${callId}/controlUrl`).once("value");
    const controlUrl = callSnap.val();

    if (controlUrl) {
      const ctrlRes = await fetch(controlUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: "end-call" }),
      });
      if (ctrlRes.ok) {
        log("info", "VAPI control end-call success", { callId });
      } else {
        log("warn", "VAPI control end-call failed", { status: ctrlRes.status });
      }
    }
  } catch (err) {
    log("warn", "VAPI control end-call exception", { error: err.message });
  }

  // Also try REST API as fallback
  const vapiKey = env("VAPI_API_KEY");
  if (vapiKey) {
    try {
      const hangupRes = await fetch(
        `https://api.vapi.ai/call/${callId}/hangup`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${vapiKey}`,
            "Content-Type": "application/json",
          },
        }
      );
      if (!hangupRes.ok) {
        const errText = await hangupRes.text();
        log("warn", "VAPI REST hangup failed", {
          status: hangupRes.status,
          body: errText.slice(0, 300),
        });
      } else {
        log("info", "VAPI REST hangup success", { callId });
      }
    } catch (err) {
      log("warn", "VAPI REST hangup exception", { error: err.message });
    }
  }

  // Clean up RTDB
  try {
    await db.ref(`calls/${callId}`).update({ status: "ended", endedAt: Date.now() });
    log("info", "RTDB call marked ended", { callId });
  } catch (err) {
    log("warn", "RTDB cleanup failed", { error: err.message });
  }

  return { ok: true };
});

// ─────────────────────────────────────────────────────────────────────────────
// vapiWebhook — Receives VAPI server events (end-of-call, status updates)
// ─────────────────────────────────────────────────────────────────────────────
exports.vapiWebhook = onRequest(
  { cors: true, timeoutSeconds: 30 },
  async (req, res) => {
    const logId = `wh-${Date.now().toString(36)}`;
    const log = (lvl, msg, d = {}) =>
      console.log(JSON.stringify({ lvl, logId, msg, ...d }));

    try {
      if (req.method !== "POST") {
        res.status(405).send("Method Not Allowed");
        return;
      }

      const body = req.body ?? {};
      const msgType = body.message?.type || body.type || "unknown";
      const callId = body.message?.call?.id || body.call?.id || null;

      log("info", "vapiWebhook received", {
        type: msgType,
        callId,
        keys: Object.keys(body).join(","),
      });

      // Handle end-of-call events
      if (
        msgType === "end-of-call-report" ||
        msgType === "hang" ||
        (msgType === "status-update" &&
          (body.message?.status === "ended" || body.status === "ended"))
      ) {
        if (callId) {
          try {
            await db
              .ref(`calls/${callId}`)
              .update({ status: "ended", endedAt: Date.now() });
            log("info", "RTDB call marked ended via webhook", { callId });
          } catch (err) {
            log("warn", "RTDB update failed", { error: err.message });
          }
        }
      }

      res.status(200).json({ ok: true });
    } catch (err) {
      log("error", "vapiWebhook failed", { error: err.message });
      res.status(200).json({ ok: true }); // Always 200 so VAPI doesn't retry
    }
  }
);
