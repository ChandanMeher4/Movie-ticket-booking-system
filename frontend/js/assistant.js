/**
 * Cineverse AI Concierge & Multi-Agent Orchestration Controller
 */

let activeMode = "multi"; // "multi" | "single" | "genai"
let activeSessionId = generateSessionId();

function generateSessionId() {
  return "session-" + Math.random().toString(36).substring(2, 10);
}

document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chat-input");
  if (input) input.focus();
});

function switchMode(mode) {
  activeMode = mode;
  document.querySelectorAll(".mode-pill").forEach((p) => p.classList.remove("active"));
  document.getElementById(`mode-${mode}`).classList.add("active");

  const labelEl = document.getElementById("active-mode-label");
  const toolbar = document.getElementById("genai-toolbar");
  const traceSidebar = document.getElementById("trace-sidebar");

  if (mode === "genai") {
    labelEl.textContent = "Direct Generative AI (Stateless)";
    toolbar.style.display = "flex";
    traceSidebar.style.display = "none";
  } else if (mode === "single") {
    labelEl.textContent = "Single Agent Assistant (ReAct Loop)";
    toolbar.style.display = "none";
    traceSidebar.style.display = "flex";
  } else {
    labelEl.textContent = "Multi-Agent Orchestrator";
    toolbar.style.display = "none";
    traceSidebar.style.display = "flex";
  }

  appendAssistantMessage(`Switched mode to: **${labelEl.textContent}**.`);
}

function clearChatSession() {
  activeSessionId = generateSessionId();
  const messagesContainer = document.getElementById("chat-messages");
  messagesContainer.innerHTML = `
    <div class="chat-bubble assistant">
      Session reset. How may I assist your movie plans today?
    </div>
  `;
  document.getElementById("trace-list").innerHTML = `
    <p style="color: var(--text-muted); font-size: 0.85rem; text-align: center; margin-top: 2rem;">
      Ready for new agent execution trace.
    </p>
  `;
  document.getElementById("trace-badge-count").textContent = "Ready";
  showToast("Started fresh conversation session.", "success");
}

function sendQuickPrompt(promptText) {
  const input = document.getElementById("chat-input");
  input.value = promptText;
  submitChatMessage();
}

async function submitChatMessage() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  const message = input.value.trim();
  if (!message) return;

  appendUserMessage(message);
  input.value = "";
  input.disabled = true;
  sendBtn.disabled = true;

  const typingId = appendTypingIndicator();

  try {
    const userId = getCurrentUserId();

    if (activeMode === "multi") {
      const data = await apiClient("/api/ai/multi/chat", {
        method: "POST",
        body: {
          session_id: activeSessionId,
          user_id: userId,
          message: message,
        },
      });

      removeTypingIndicator(typingId);
      appendAssistantMessage(data.reply);
      renderMultiAgentTrace(data.agent_trace, data.state);

    } else if (activeMode === "single") {
      const data = await apiClient("/api/ai/agent/chat", {
        method: "POST",
        body: {
          session_id: activeSessionId,
          user_id: userId,
          message: message,
        },
      });

      removeTypingIndicator(typingId);
      appendAssistantMessage(data.reply);
      renderSingleAgentTrace(data.tool_calls_made);

    } else {
      // GenAI direct recommendation default
      const data = await apiClient("/api/ai/genai/recommend", {
        method: "POST",
        body: { mood: message },
      });

      removeTypingIndicator(typingId);
      let replyText = "Here are movie recommendations for your mood:\n";
      (data.recommendations || []).forEach((r) => {
        replyText += `\n• **${r.title}** (Match: ${r.match_score}%): ${r.reason}`;
      });
      appendAssistantMessage(replyText);
    }
  } catch (err) {
    removeTypingIndicator(typingId);
    appendAssistantMessage(`Error: ${err.message || "Failed to process request."}`);
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

function appendUserMessage(text) {
  const container = document.getElementById("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble user";
  bubble.textContent = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendAssistantMessage(text) {
  const container = document.getElementById("chat-messages");
  const bubble = document.createElement("div");
  bubble.className = "chat-bubble assistant";

  // Simple markdown conversion for bold text and linebreaks
  let formatted = escapeHtml(text)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n/g, "<br>");

  bubble.innerHTML = formatted;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function appendTypingIndicator() {
  const container = document.getElementById("chat-messages");
  const id = "typing-" + Date.now();
  const bubble = document.createElement("div");
  bubble.id = id;
  bubble.className = "chat-bubble assistant";
  bubble.style.color = "var(--text-muted)";
  bubble.innerHTML = `<em>Thinking & coordinating agents...</em>`;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function renderMultiAgentTrace(traceList, state) {
  const container = document.getElementById("trace-list");
  const badge = document.getElementById("trace-badge-count");
  if (!traceList || traceList.length === 0) return;

  badge.textContent = `${traceList.length} Steps`;

  container.innerHTML = traceList.map((t) => {
    const toolsStr = t.tools_used && t.tools_used.length > 0 ? t.tools_used.join(", ") : "None";
    return `
      <div class="trace-step">
        <div class="trace-step-top">
          <span class="agent-badge ${escapeHtml(t.agent)}">${escapeHtml(t.agent)}</span>
          <span style="color: var(--text-muted); font-size: 0.72rem;">${t.duration_ms}ms</span>
        </div>
        <div style="font-size: 0.78rem; color: var(--text-muted); margin-bottom: 0.25rem;">
          Tools: <code style="color: var(--accent-cyan);">${escapeHtml(toolsStr)}</code>
        </div>
        <div style="font-size: 0.8rem; color: var(--text-secondary); background: var(--bg-darkest); padding: 0.4rem 0.6rem; border-radius: 4px; max-height: 80px; overflow-y: auto;">
          ${escapeHtml(t.output)}
        </div>
      </div>
    `;
  }).join("");

  // Add CriticAgent status banner if evaluated
  if (state && state.critic_feedback) {
    const isApproved = state.critic_approved;
    const criticBanner = document.createElement("div");
    criticBanner.style.marginTop = "0.75rem";
    criticBanner.style.padding = "0.6rem";
    criticBanner.style.borderRadius = "6px";
    criticBanner.style.fontSize = "0.78rem";
    criticBanner.style.border = isApproved ? "1px solid var(--accent-green)" : "1px solid var(--accent-red)";
    criticBanner.style.background = isApproved ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)";
    criticBanner.innerHTML = `<strong>CriticAgent:</strong> ${escapeHtml(state.critic_feedback)}`;
    container.appendChild(criticBanner);
  }
}

function renderSingleAgentTrace(toolCalls) {
  const container = document.getElementById("trace-list");
  const badge = document.getElementById("trace-badge-count");

  if (!toolCalls || toolCalls.length === 0) {
    container.innerHTML = `<p style="color: var(--text-muted); font-size: 0.82rem; text-align: center;">No tool calls executed in this turn.</p>`;
    badge.textContent = "0 Tools";
    return;
  }

  badge.textContent = `${toolCalls.length} Tool(s)`;
  container.innerHTML = toolCalls.map((tc) => `
    <div class="trace-step">
      <div class="trace-step-top">
        <span class="agent-badge BookingAgent">${escapeHtml(tc.tool)}</span>
      </div>
      <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.35rem;">
        Arguments: <code>${escapeHtml(JSON.stringify(tc.arguments || {}))}</code>
      </div>
      <div style="font-size: 0.75rem; color: var(--text-secondary); background: var(--bg-darkest); padding: 0.4rem; border-radius: 4px; max-height: 80px; overflow-y: auto;">
        ${escapeHtml(JSON.stringify(tc.result || {}))}
      </div>
    </div>
  `).join("");
}

// --- GenAI Quick Actions ---

async function runGenAIMovieSummary() {
  const moviePrompt = prompt("Enter target Movie ID (e.g. 1 for Inception, 2 for Interstellar):", "1");
  if (!moviePrompt) return;
  const movieId = parseInt(moviePrompt, 10);
  const tone = prompt("Enter desired tone (exciting, poetic, dramatic, family-friendly):", "exciting") || "exciting";

  appendUserMessage(`Generate a ${tone} marketing blurb for Movie ID ${movieId}`);
  const typingId = appendTypingIndicator();

  try {
    const res = await apiClient("/api/ai/genai/movie-summary", {
      method: "POST",
      body: { movie_id: movieId, tone: tone },
    });
    removeTypingIndicator(typingId);
    appendAssistantMessage(`**Marketing Blurb for ${res.title} (${res.tone}):**\n\n${res.summary}`);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendAssistantMessage(`Error: ${err.message}`);
  }
}

async function runGenAIRecommend() {
  const mood = prompt("What kind of movie experience or mood are you looking for?", "mind-bending sci-fi with intense emotional drama");
  if (!mood) return;

  appendUserMessage(`Recommend movies for mood: "${mood}"`);
  const typingId = appendTypingIndicator();

  try {
    const res = await apiClient("/api/ai/genai/recommend", {
      method: "POST",
      body: { mood },
    });
    removeTypingIndicator(typingId);
    let reply = `**Top 3 Curated Recommendations:**\n`;
    (res.recommendations || []).forEach((r) => {
      reply += `\n• **${r.title}** (Match: ${r.match_score}%)\n  _${r.reason}_\n`;
    });
    appendAssistantMessage(reply);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendAssistantMessage(`Error: ${err.message}`);
  }
}

async function runGenAIReviewSentiment() {
  const sampleReviews = [
    "Mind-bending visuals and incredible performances by the entire ensemble!",
    "The musical score was breathtaking and kept me immersed the whole time.",
    "A bit long in the middle act, but the climax makes it totally worth the watch."
  ];

  appendUserMessage("Analyze sentiment for audience reviews:\n" + sampleReviews.map(r => `"${r}"`).join("\n"));
  const typingId = appendTypingIndicator();

  try {
    const res = await apiClient("/api/ai/genai/review-summarize", {
      method: "POST",
      body: { reviews: sampleReviews },
    });
    removeTypingIndicator(typingId);
    let reply = `**Audience Sentiment Analysis:**\n`;
    reply += `• **Overall Sentiment**: ${res.sentiment.toUpperCase()}\n`;
    reply += `• **Summary**: ${res.summary}\n`;
    reply += `• **Key Pros**: ${(res.pros || []).join(", ")}\n`;
    reply += `• **Cons**: ${(res.cons || []).join(", ")}`;
    appendAssistantMessage(reply);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendAssistantMessage(`Error: ${err.message}`);
  }
}

async function runGenAIBookingEmail() {
  const bookingPrompt = prompt("Enter Booking ID to generate confirmation email for:", "1");
  if (!bookingPrompt) return;
  const bookingId = parseInt(bookingPrompt, 10);

  appendUserMessage(`Generate customer booking email for Booking #${bookingId}`);
  const typingId = appendTypingIndicator();

  try {
    const res = await apiClient("/api/ai/genai/booking-email", {
      method: "POST",
      body: { booking_id: bookingId },
    });
    removeTypingIndicator(typingId);
    appendAssistantMessage(`**Generated Confirmation Email:**\n\n${res.email_text}`);
  } catch (err) {
    removeTypingIndicator(typingId);
    appendAssistantMessage(`Error: ${err.message}`);
  }
}
