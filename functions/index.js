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
 * Extract plain text from OpenAI-style message content (string or array of parts).
 */
function getMessageText(msg) {
  const c = msg?.content;
  if (typeof c === "string") return c;
  if (!c || !Array.isArray(c)) return "";
  for (const part of c) {
    if (part && typeof part.text === "string") return part.text;
    if (part && typeof part.content === "string") return part.content;
  }
  return "";
}

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
    const text = getMessageText(msg);
    if (!text || !String(text).trim()) continue;

    if (role === "system") {
      systemPrompt = text;
      continue;
    }
    const geminiRole = role === "assistant" ? "model" : "user";
    contents.push({ role: geminiRole, parts: [{ text: String(text).trim() }] });
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
    // Safety block or empty response - return fallback so the call continues
    const reason = candidate?.finishReason || data.promptFeedback?.blockReason || "no content";
    throw new Error(`Gemini no content (${reason}). Safe fallback will be used.`);
  }

  const text = candidate.content.parts.map((p) => (p && p.text) || "").join("").trim();
  return text || null;
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
        // Return 200 with fallback so call doesn't drop; set env in Firebase Console → Functions → Environment variables
        const fallback = "I'm having a brief connection issue. Please hold—I have the caller's location and details. Can you hear me?";
        res.set("Content-Type", "application/json");
        res.status(200).send(JSON.stringify(buildOpenAIResponse(logId, body, fallback)));
        return;
      }

      let assistantText;
      try {
        assistantText = await generateWithGemini(messages, geminiKey);
      } catch (geminiErr) {
        log("error", "vapiLlm generateWithGemini failed", {
          error: geminiErr.message,
          stack: geminiErr.stack,
          messageCount: messages.length,
          messageRoles: messages.map((m) => m?.role),
          firstContentTypes: messages.slice(0, 3).map((m) => typeof m?.content),
        });
        assistantText = "I'm sorry, could you repeat that? I'm still here with the caller's information.";
      }

      const durationMs = Date.now() - startTime;
      const content = (assistantText && String(assistantText).trim()) || "Could you repeat that, please?";
      log("info", "vapiLlm Gemini response", {
        responseLength: content.length,
        durationMs,
        firstChars: content.slice(0, 80),
      });

      const payload = buildOpenAIResponse(logId, body, content);
      res.set("Content-Type", "application/json");
      res.status(200).send(JSON.stringify(payload));
    } catch (err) {
      const durationMs = Date.now() - startTime;
      const bodySafe = typeof req.body === "object" && req.body !== null ? req.body : {};
      log("error", "vapiLlm failed", {
        error: err.message,
        stack: err.stack,
        durationMs,
        messageCount: Array.isArray(bodySafe.messages) ? bodySafe.messages.length : 0,
      });
      // Always return 200 with fallback so VAPI doesn't drop the call with 500
      const fallback = "Please hold—I'm still relaying the caller's information. Can you hear me?";
      res.set("Content-Type", "application/json");
      res.status(200).send(JSON.stringify(buildOpenAIResponse(logId, bodySafe, fallback)));
    }
  }
);

function buildOpenAIResponse(logId, body, content) {
  return {
    id: `chatcmpl-${logId}`,
    object: "chat.completion",
    created: Math.floor(Date.now() / 1000),
    model: (body && body.model) || "gpt-3.5-turbo",
    choices: [
      {
        index: 0,
        message: { role: "assistant", content: String(content) },
        finish_reason: "stop",
      },
    ],
    usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  };
}

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
