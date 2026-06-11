function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function detailLevelLabel(level) {
    if (level === "short") return "สั้น";
    if (level === "detailed") return "ละเอียด";
    return "ปกติ";
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

function buildPendingShell(streamId, sourceLang, targetLang, detailLevel) {
    return `
<div class="message message-assistant" id="${streamId}">
    <div class="message-header">
        <span class="role">แปล</span>
        <span class="langs">${sourceLang} → ${targetLang}</span>
        <span class="detail-level" title="ความละเอียดในการแปล">${detailLevelLabel(detailLevel)}</span>
        <span class="stats" id="${streamId}-stats">
            <span class="badge streaming">กำลังเชื่อมต่อ...</span>
        </span>
    </div>
    <div class="message-content" id="${streamId}-content"></div>
</div>`;
}

function buildAssistantShell(streamId, sourceLang, targetLang, detailLevel) {
    return `
<div class="message message-assistant" id="${streamId}">
    <div class="message-header">
        <span class="role">แปล</span>
        <span class="langs">${sourceLang} → ${targetLang}</span>
        <span class="detail-level" title="ความละเอียดในการแปล">${detailLevelLabel(detailLevel)}</span>
        <span class="stats" id="${streamId}-stats">
            <span class="badge streaming">streaming...</span>
        </span>
    </div>
    <div class="message-content" id="${streamId}-content"><span class="cursor-blink">▌</span></div>
</div>`;
}

function buildAssistantFinal(msg, detailLevelFallback) {
    const stats = [];
    stats.push(`in: ${msg.tokens_in} | out: ${msg.tokens_out}`);
    if (msg.latency_ms > 0) stats.push(`${msg.latency_ms}ms`);
    if (msg.tokens_per_sec_out > 0) stats.push(`${msg.tokens_per_sec_out} tok/s`);
    const cached = msg.from_cache ? '<span class="badge cached">cached</span>' : "";
    const detailLevel = msg.detail_level || detailLevelFallback || "normal";

    return `
<div class="message message-assistant">
    <div class="message-header">
        <span class="role">แปล</span>
        <span class="langs">${msg.source_lang} → ${msg.target_lang}</span>
        <span class="detail-level" title="ความละเอียดในการแปล">${detailLevelLabel(detailLevel)}</span>
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

function activateStreamingShell(state) {
    if (state.streamingActive) return;
    state.streamingActive = true;
    const statsEl = document.getElementById(`${state.streamId}-stats`);
    if (statsEl) {
        statsEl.innerHTML = '<span class="badge streaming">streaming...</span>';
    }
    state.contentEl.innerHTML = '<span class="cursor-blink">▌</span>';
}

function handleStreamEvent(event, state) {
    if (event.type === "started") {
        activateStreamingShell(state);
    } else if (event.type === "token") {
        activateStreamingShell(state);
        state.accumulated += event.data.delta;
        state.contentEl.innerHTML =
            escapeHtml(state.accumulated) + '<span class="cursor-blink">▌</span>';
        state.messagesEl.scrollTop = state.messagesEl.scrollHeight;
    } else if (event.type === "done") {
        state.shellEl.outerHTML = buildAssistantFinal(
            event.data.assistant_message,
            state.detailLevel,
        );
        state.finished = true;
    } else if (event.type === "error") {
        state.shellEl.remove();
        throw new Error(event.data.detail || "Translation failed");
    }
}

function processSSEBuffer(buffer, state) {
    const parsed = parseSSE(buffer);
    for (const event of parsed.events) {
        handleStreamEvent(event, state);
    }
    return parsed.remainder;
}

const STREAM_TIMEOUT_MS = 130_000;

async function streamTranslate(conversationId, content, sourceLang, targetLang, detailLevel, messagesEl) {
    const empty = messagesEl.querySelector(".empty");
    if (empty) empty.remove();

    const streamId = `stream-${Date.now()}`;
    messagesEl.insertAdjacentHTML("beforeend", buildUserMessage(content, sourceLang, targetLang));
    messagesEl.insertAdjacentHTML("beforeend", buildPendingShell(streamId, sourceLang, targetLang, detailLevel));
    messagesEl.scrollTop = messagesEl.scrollHeight;

    const contentEl = document.getElementById(`${streamId}-content`);
    const shellEl = document.getElementById(streamId);
    const state = {
        streamId,
        accumulated: "",
        contentEl,
        shellEl,
        messagesEl,
        detailLevel,
        finished: false,
        streamingActive: false,
    };

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);

    let response;
    try {
        response = await fetch(`/api/conversations/${conversationId}/messages/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                content,
                source_lang: sourceLang,
                target_lang: targetLang,
                detail_level: detailLevel,
            }),
            signal: controller.signal,
        });
    } catch (err) {
        shellEl.remove();
        if (err.name === "AbortError") {
            throw new Error("หมดเวลารอการแปล (timeout)");
        }
        throw err;
    } finally {
        clearTimeout(timeoutId);
    }

    if (!response.ok) {
        shellEl.remove();
        throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (value) {
                buffer += decoder.decode(value, { stream: true });
                buffer = processSSEBuffer(buffer, state);
            }
            if (done) {
                buffer += decoder.decode();
                if (buffer.trim()) {
                    processSSEBuffer(buffer.endsWith("\n\n") ? buffer : buffer + "\n\n", state);
                }
                break;
            }
        }
    } catch (err) {
        if (shellEl.isConnected) shellEl.remove();
        throw err;
    }

    if (!state.finished && state.shellEl.isConnected) {
        state.shellEl.outerHTML = buildAssistantFinal(
            {
                source_lang: sourceLang,
                target_lang: targetLang,
                content: state.accumulated,
                tokens_in: 0,
                tokens_out: 0,
                latency_ms: 0,
                tokens_per_sec_out: 0,
                from_cache: false,
            },
            detailLevel,
        );
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
