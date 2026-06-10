function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function buildUserMessage(content, sourceLang, targetLang) {
    return `
<div class="message message-user">
    <div class="message-header">
        <span class="role">คุณ</span>
        <span class="langs">${sourceLang} → ${targetLang}</span>
    </div>
    <div class="message-content">${escapeHtml(content)}</div>
</div>`;
}

function buildAssistantShell(sourceLang, targetLang) {
    const id = "streaming-assistant";
    return `
<div class="message message-assistant" id="${id}">
    <div class="message-header">
        <span class="role">แปล</span>
        <span class="langs">${sourceLang} → ${targetLang}</span>
        <span class="stats" id="${id}-stats">
            <span class="badge streaming">streaming...</span>
        </span>
    </div>
    <div class="message-content" id="${id}-content"><span class="cursor-blink">▌</span></div>
</div>`;
}

function buildAssistantFinal(msg) {
    const stats = [];
    stats.push(`in: ${msg.tokens_in} | out: ${msg.tokens_out}`);
    if (msg.latency_ms > 0) stats.push(`${msg.latency_ms}ms`);
    if (msg.tokens_per_sec_out > 0) stats.push(`${msg.tokens_per_sec_out} tok/s`);
    const cached = msg.from_cache ? '<span class="badge cached">cached</span>' : "";

    return `
<div class="message message-assistant">
    <div class="message-header">
        <span class="role">แปล</span>
        <span class="langs">${msg.source_lang} → ${msg.target_lang}</span>
        <span class="stats">${stats.join(" | ")} ${cached}</span>
    </div>
    <div class="message-content">${escapeHtml(msg.content)}</div>
</div>`;
}

function parseSSE(buffer) {
    const events = [];
    const parts = buffer.split("\n\n");
    const remainder = parts.pop() || "";

    for (const part of parts) {
        if (!part.trim()) continue;
        let eventType = "message";
        let data = "";
        for (const line of part.split("\n")) {
            if (line.startsWith("event: ")) eventType = line.slice(7);
            if (line.startsWith("data: ")) data = line.slice(6);
        }
        if (data) {
            try {
                events.push({ type: eventType, data: JSON.parse(data) });
            } catch (_) {
                /* skip malformed */
            }
        }
    }
    return { events, remainder };
}

async function streamTranslate(conversationId, content, sourceLang, targetLang, detailLevel, messagesEl) {
    const empty = messagesEl.querySelector(".empty");
    if (empty) empty.remove();

    messagesEl.insertAdjacentHTML("beforeend", buildUserMessage(content, sourceLang, targetLang));
    messagesEl.insertAdjacentHTML("beforeend", buildAssistantShell(sourceLang, targetLang));
    messagesEl.scrollTop = messagesEl.scrollHeight;

    const contentEl = document.getElementById("streaming-assistant-content");
    const shellEl = document.getElementById("streaming-assistant");
    let accumulated = "";

    const response = await fetch(`/api/conversations/${conversationId}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            content,
            source_lang: sourceLang,
            target_lang: targetLang,
            detail_level: detailLevel,
        }),
    });

    if (!response.ok) {
        shellEl.remove();
        throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSSE(buffer);
        buffer = parsed.remainder;

        for (const event of parsed.events) {
            if (event.type === "token") {
                accumulated += event.data.delta;
                contentEl.innerHTML = escapeHtml(accumulated) + '<span class="cursor-blink">▌</span>';
                messagesEl.scrollTop = messagesEl.scrollHeight;
            } else if (event.type === "done") {
                shellEl.outerHTML = buildAssistantFinal(event.data.assistant_message);
            } else if (event.type === "error") {
                shellEl.remove();
                throw new Error(event.data.detail || "Translation failed");
            }
        }
    }
}

function initChatForm() {
    const form = document.getElementById("chat-form");
    if (!form) return;

    const conversationId = form.dataset.conversationId;
    const messagesEl = document.getElementById("messages");
    const submitBtn = form.querySelector('button[type="submit"]');

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const content = form.content.value.trim();
        if (!content) return;

        const sourceLang = form.source_lang.value;
        const targetLang = form.target_lang.value;
        const detailLevel = form.detail_level.value;

        submitBtn.disabled = true;
        try {
            await streamTranslate(conversationId, content, sourceLang, targetLang, detailLevel, messagesEl);
            form.reset();
        } catch (err) {
            alert("แปลไม่สำเร็จ: " + err.message);
        } finally {
            submitBtn.disabled = false;
        }
    });
}

document.addEventListener("DOMContentLoaded", initChatForm);
