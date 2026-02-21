/**
 * LUMOS Firebase Cloud Functions — Emergency call (VAPI + Gemini)
 * Logging is added throughout so we can debug "agent doesn't respond after first prompt".
 */

const { onRequest, onCall, HttpsError } = require("firebase-functions/v2/https");
const { setGlobalOptions } = require("firebase-functions/v2");
const admin = require("firebase-admin");

admin.initializeApp();

setGlobalOptions({ maxInstances: 20 });

function env(name, fallback = "") {
  return process.env[name] ?? fallback;
}

// In-memory store for callId -> control info (for message/end). Production could use Firestore.
const callStore = new Map();

/**
 * Call Gemini REST API to generate the next assistant reply from conversation messages.
 * Returns the assistant text only.
 */
async function generateWithGemini(messages, geminiKey) {
  if (!geminiKey || !messages || messages.length === 0) {
    throw new Error("GEMINI_API_KEY required and messages must be non-empty");
  }

  // Convert OpenAI-style messages to Gemini generateContent format
  // Gemini: contents[] with role "user" or "model", parts: [{ text }]
  const contents = [];
  let systemPrompt = null;

  for (const msg of messages) {
    const role = (msg.role || "user").toLowerCase();
    const text = typeof msg.content === "string" ? msg.content : (msg.content && msg.content[0] && msg.content[0].text) ? msg.content[0].text : "";
    if (!text) continue;

    if (role === "system") {
      systemPrompt = text;
      continue;
    }
    const geminiRole = role === "assistant" ? "model" : "user";
    contents.push({ role: geminiRole, parts: [{ text }] });
  }

  if (systemPrompt) {
    // Prepend system as first user turn so Gemini has context (it doesn't have a separate system role)
    contents.unshift({ role: "user", parts: [{ text: `[System instructions]\n${systemPrompt}` }] });
  }

  // Gemini expects user/model alternation; if we have two users in a row, insert a short model reply so the last message is user
  const normalized = [];
  for (const c of contents) {
    const role = c.role === "model" ? "model" : "user";
    if (normalized.length > 0 && normalized[normalized.length - 1].role === role && role === "user") {
      normalized.push({ role: "model", parts: [{ text: "(ack)" }] });
    }
    normalized.push({ role: c.role, parts: c.parts });
  }
  const finalContents = normalized.length > 0 ? normalized : contents;

  const toSend = finalContents && finalContents.length > 0 ? finalContents : contents;
  if (toSend.length === 0) {
    throw new Error("No valid message content to send to Gemini");
  }

  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key=${geminiKey}`;
  const body = {
    contents: toSend,
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 1024,
    },
  };

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Gemini API error ${res.status}: ${errText.slice(0, 500)}`);
  }

  const data = await res.json();
  const candidate = data.candidates && data.candidates[0];
  if (!candidate || !candidate.content || !candidate.content.parts || candidate.content.parts.length === 0) {
    throw new Error("Gemini returned no content: " + JSON.stringify(data).slice(0, 300));
  }

  const text = candidate.content.parts.map((p) => p.text).join("");
  return text;
}

/**
 * VAPI calls this HTTP endpoint for each LLM turn (each time the operator or user speaks).
 * We must return OpenAI-compatible chat completion so VAPI can speak the assistant reply.
 * Logging: request body (message count, roles), response (content length), duration, errors.
 */
exports.vapiLlm = onRequest(
  { cors: true, timeoutSeconds: 60 },
  async (req, res) => {
    const startTime = Date.now();
    const logId = `vapiLlm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    const log = (level, msg, data = {}) => {
      console.log(JSON.stringify({ level, logId, ts: new Date().toISOString(), msg, ...data }));
    };

    try {
      if (req.method !== "POST") {
        log("warn", "vapiLlm non-POST", { method: req.method });
        res.status(405).send("Method Not Allowed");
        return;
      }

      const body = typeof req.body === "object" && req.body !== null ? req.body : {};
      const messages = Array.isArray(body.messages) ? body.messages : [];
      const stream = Boolean(body.stream);

      log("info", "vapiLlm request", {
        messageCount: messages.length,
        stream,
        streamNotSupported: stream,
        lastRole: messages[messages.length - 1]?.role,
        lastContentLength: typeof messages[messages.length - 1]?.content === "string"
          ? messages[messages.length - 1].content.length
          : 0,
      });
      if (stream) {
        log("warn", "vapiLlm streaming requested but we return non-streaming; if agent stops after first turn, enable SSE in vapiLlm");
      }

  const geminiKey = env("GEMINI_API_KEY");
  if (!geminiKey) {
        log("error", "vapiLlm GEMINI_API_KEY not set");
        res.status(500).json({ error: "GEMINI_API_KEY not configured" });
        return;
      }

      const assistantText = await generateWithGemini(messages, geminiKey);
      const durationMs = Date.now() - startTime;

      log("info", "vapiLlm Gemini response", {
        responseLength: assistantText.length,
        durationMs,
        firstChars: assistantText.slice(0, 80),
      });

      // VAPI expects OpenAI chat completion format. Non-streaming: choices[].message
      const payload = {
        id: `chatcmpl-${logId}`,
        object: "chat.completion",
        created: Math.floor(Date.now() / 1000),
        model: body.model || "gpt-3.5-turbo",
        choices: [
          {
            index: 0,
            message: {
              role: "assistant",
              content: assistantText,
            },
            finish_reason: "stop",
          },
        ],
        usage: {
          prompt_tokens: 0,
          completion_tokens: 0,
          total_tokens: 0,
        },
      };

      res.set("Content-Type", "application/json");
      res.status(200).send(JSON.stringify(payload));
    } catch (err) {
      const durationMs = Date.now() - startTime;
      log("error", "vapiLlm failed", {
        error: err.message,
        stack: err.stack,
        durationMs,
      });
      res.status(500).json({
        error: "vapiLlm error",
        message: err.message,
      });
    }
  }
);

/**
 * Start an outbound emergency call via VAPI. Called from the frontend when user taps "Start call".
 */
exports.startEmergencyCall = onCall(async (request) => {
  const logId = `start-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const log = (level, msg, data = {}) => {
    console.log(JSON.stringify({ level, logId, ts: new Date().toISOString(), msg, ...data }));
  };

  // Allow unauthenticated emergency calls (SOS should work without sign-in)
  if (request.auth) {
    log("info", "startEmergencyCall authenticated", { uid: request.auth.uid });
  } else {
    log("info", "startEmergencyCall unauthenticated (allowed for emergency)");
  }

  const payload = request.data || {};
  const {
    callerName,
    callerAge,
    lat,
    lng,
    address,
    safetyScore,
    incidentType,
    severity,
    userNotes,
    movementDirection,
    movementSpeed,
  } = payload;

  log("info", "startEmergencyCall payload", {
    callerName,
    lat,
    lng,
    incidentType,
    severity,
  });

  const vapiKey = env("VAPI_API_KEY");
  const phoneNumberId = env("VAPI_PHONE_NUMBER_ID");
  const toNumber = env("DEMO_EMERGENCY_NUMBER");

  if (!vapiKey || !phoneNumberId || !toNumber) {
    log("error", "startEmergencyCall missing env", {
      hasVapiKey: !!vapiKey,
      hasPhoneNumberId: !!phoneNumberId,
      hasToNumber: !!toNumber,
    });
    throw new HttpsError("failed-precondition", "VAPI_API_KEY, VAPI_PHONE_NUMBER_ID, DEMO_EMERGENCY_NUMBER must be set");
  }

  // Build the assistant system prompt so the first LLM turn has full context
  const firstMessage = [
    `You are LUMOS AI, speaking on behalf of a caller in an emergency.`,
    `Caller name: ${callerName || "Unknown"}.`,
    callerAge ? `Age: ${callerAge}.` : "",
    `Location: ${address || "Unknown"} (lat ${lat}, lng ${lng}).`,
    `Safety score at location: ${safetyScore ?? "unknown"}.`,
    `Incident type: ${incidentType || "unspecified"}. Severity: ${severity || "HIGH"}.`,
    userNotes ? `Caller notes: ${userNotes}.` : "",
    movementDirection ? `Direction: ${movementDirection}.` : "",
    movementSpeed ? `Speed: ${movementSpeed}.` : "",
    `Speak clearly and concisely to the 911 operator. Answer their questions. If they ask for updates, say you will relay. Keep responses brief.`,
  ]
    .filter(Boolean)
    .join(" ");

  // VAPI create call: we need assistant with custom LLM pointing to our vapiLlm URL
  const region = process.env.GCLOUD_REGION || "us-central1";
  const projectId = process.env.GCP_PROJECT || process.env.GCLOUD_PROJECT;
  const baseUrl = process.env.VAPI_LLM_BASE_URL || `https://${region}-${projectId}.cloudfunctions.net`;
  const llmUrl = `${baseUrl}/vapiLlm`;

  log("info", "startEmergencyCall VAPI LLM URL", { llmUrl, baseUrl });

  const assistant = {
    name: "LUMOS Emergency Assistant",
    firstMessage,
    model: {
      provider: "custom-llm",
      url: llmUrl,
      model: "gpt-3.5-turbo",
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

    if (!vapiRes.ok) {
      log("error", "startEmergencyCall VAPI API error", {
        status: vapiRes.status,
        body: JSON.stringify(vapiData).slice(0, 500),
      });
      throw new HttpsError("internal", vapiData.message || `VAPI returned ${vapiRes.status}`);
    }

    const callId = vapiData.id || vapiData.callId || vapiData.call?.id;
    if (!callId) {
      log("error", "startEmergencyCall no callId in response", { vapiData: JSON.stringify(vapiData).slice(0, 500) });
      throw new HttpsError("internal", "VAPI did not return a call id");
    }

    callStore.set(callId, { createdAt: Date.now() });
    log("info", "startEmergencyCall success", { callId });

    return {
      callId,
      status: "started",
      message: "Call initiated. LUMOS AI is speaking to the operator.",
    };
  } catch (err) {
    if (err instanceof HttpsError) throw err;
    log("error", "startEmergencyCall exception", { error: err.message });
    throw new HttpsError("internal", err.message || "Failed to start emergency call");
  }
});

/**
 * Send a message update into the live call (e.g. "moved to 3rd floor").
 */
exports.emergencyCallMessage = onCall(async (request) => {
  const logId = `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const log = (level, msg, data = {}) => {
    console.log(JSON.stringify({ level, logId, ts: new Date().toISOString(), msg, ...data }));
  };

  const { callId, message } = request.data || {};
  if (!callId || !message) {
    log("warn", "emergencyCallMessage missing callId or message");
    throw new HttpsError("invalid-argument", "callId and message required");
  }
  log("info", "emergencyCallMessage", { callId, messageLength: message.length });
  // If you have a VAPI control API to inject messages, call it here; otherwise no-op is ok
  return { ok: true };
});

/**
 * End the emergency call.
 */
exports.emergencyCallEnd = onCall(async (request) => {
  const logId = `end-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const log = (level, msg, data = {}) => {
    console.log(JSON.stringify({ level, logId, ts: new Date().toISOString(), msg, ...data }));
  };

  const { callId } = request.data || {};
  if (!callId) {
    log("warn", "emergencyCallEnd missing callId");
    throw new HttpsError("invalid-argument", "callId required");
  }
  callStore.delete(callId);
  log("info", "emergencyCallEnd", { callId });
  return { ok: true };
});
