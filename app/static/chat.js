const OPTION_LABEL_PATTERN = /(?:^|\s)(Option\s+\d+\s*:)/gim;

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

function findOptionMatches(text) {
    return [...text.matchAll(OPTION_LABEL_PATTERN)];
}

function optionLabelStart(match) {
    return match.index + match[0].length - match[1].length;
}

function optionLabelEnd(match) {
    return match.index + match[0].length;
}

function parseTranslationOptions(text) {
    const matches = findOptionMatches(text);
    if (!matches.length) return null;

    return matches.map((match, index) => {
        const label = match[1].trim();
        const bodyStart = optionLabelEnd(match);
        const bodyEnd =
            index + 1 < matches.length
                ? optionLabelStart(matches[index + 1])
                : text.length;
        return { label, body: text.slice(bodyStart, bodyEnd).trim() };
    });
}

function normalizeTranslationContent(text) {
    const trimmed = text.trim();
    const options = parseTranslationOptions(trimmed);
    if (!options) return trimmed;

    const matches = findOptionMatches(trimmed);
    const preamble = trimmed.slice(0, optionLabelStart(matches[0])).trim();
    const blocks = options.map((option) => `${option.label}\n${option.body}`);
    return preamble ? `${preamble}\n\n${blocks.join("\n\n")}` : blocks.join("\n\n");
}

const COPY_ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="copy-icon" aria-hidden="true"><path fill-rule="evenodd" d="M7.5 3.75A3.75 3.75 0 0 1 11.25 0h7.5A3.75 3.75 0 0 1 22.5 3.75v7.5A3.75 3.75 0 0 1 18.75 15h-7.5A3.75 3.75 0 0 1 7.5 11.25v-7.5Zm6.75 0v7.5a3.75 3.75 0 0 1-3.75 3.75h-7.5A3.75 3.75 0 0 1 0 11.25v-7.5A3.75 3.75 0 0 1 3.75 0h7.5Zm-6 12.75A3.75 3.75 0 0 1 10.5 9h7.5a3.75 3.75 0 0 1 3.75 3.75v7.5A3.75 3.75 0 0 1 18.75 24h-7.5A3.75 3.75 0 0 1 7.5 20.25v-7.5Z" clip-rule="evenodd"/></svg>`;
const CHECK_ICON = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" class="check-icon" aria-hidden="true" hidden><path fill-rule="evenodd" d="M19.916 4.626a.75.75 0 0 1 .208 1.04l-9 13.5a.75.75 0 0 1-1.154.114l-6-6a.75.75 0 0 1 1.06-1.06l5.353 5.353 8.493-12.74a.75.75 0 0 1 1.04-.207Z" clip-rule="evenodd"/></svg>`;

function buildCopyCommandSection(label, text) {
    return (
        '<div class="copy-command-section">' +
        '<div class="copy-command-header">' +
        `<span class="copy-command-label">${escapeHtml(label)}</span>` +
        '<button type="button" class="btn-copy" title="คัดลอก" aria-label="คัดลอก">' +
        '<span class="sr-only">คัดลอก</span>' +
        COPY_ICON +
        CHECK_ICON +
        "</button>" +
        "</div>" +
        `<div class="copy-command-body"><code>${escapeHtml(text)}</code></div>` +
        "</div>"
    );
}

function formatMessageContent(text) {
    const normalized = normalizeTranslationContent(text);
    const options = parseTranslationOptions(normalized);
    if (!options) {
        return `<span class="plain-text">${escapeHtml(normalized)}</span>`;
    }

    const matches = findOptionMatches(normalized);
    const preamble = normalized.slice(0, optionLabelStart(matches[0])).trim();
    const parts = [];

    if (preamble) {
        parts.push(`<div class="option-preamble">${escapeHtml(preamble)}</div>`);
    }

    parts.push('<div class="translation-options">');
    for (const option of options) {
        parts.push(buildCopyCommandSection(option.label, option.body));
    }
    parts.push("</div>");
    return parts.join("");
}

function detailLevelLabel(level) {
    if (level === "short") return "สั้น";
    if (level === "detailed") return "ละเอียด";
    return "ปกติ";
}

function scrollMessagesToBottom(messagesEl) {
    messagesEl.scrollTop = messagesEl.scrollHeight;
}

function scrollMessagesToBottomAfterLayout(messagesEl) {
    const scroll = () => {
        messagesEl.scrollTop = messagesEl.scrollHeight;
        messagesEl.lastElementChild?.scrollIntoView({ block: "end" });
    };
    scroll();
    requestAnimationFrame(() => {
        scroll();
        requestAnimationFrame(scroll);
    });
    setTimeout(scroll, 0);
    setTimeout(scroll, 100);
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
    const content = formatMessageContent(msg.content || "");

    return (
        '<div class="message message-assistant">' +
        '<div class="message-header">' +
        '<span class="role">แปล</span>' +
        `<span class="langs">${msg.source_lang} → ${msg.target_lang}</span>` +
        `<span class="detail-level" title="ความละเอียดในการแปล">${detailLevelLabel(detailLevel)}</span>` +
        `<span class="stats">${stats.join(" | ")} ${cached}</span>` +
        "</div>" +
        `<div class="message-content">${content}</div>` +
        "</div>"
    );
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
            formatMessageContent(state.accumulated) + '<span class="cursor-blink">▌</span>';
        scrollMessagesToBottom(state.messagesEl);
    } else if (event.type === "done") {
        state.shellEl.outerHTML = buildAssistantFinal(
            event.data.assistant_message,
            state.detailLevel,
        );
        state.finished = true;
        scrollMessagesToBottomAfterLayout(state.messagesEl);
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

async function streamTranslate(conversationId, content, sourceLang, targetLang, detailLevel, numOptions, messagesEl) {
    const empty = messagesEl.querySelector(".empty");
    if (empty) empty.remove();

    const streamId = `stream-${Date.now()}`;
    messagesEl.insertAdjacentHTML("beforeend", buildUserMessage(content, sourceLang, targetLang));
    messagesEl.insertAdjacentHTML("beforeend", buildPendingShell(streamId, sourceLang, targetLang, detailLevel));
    scrollMessagesToBottom(messagesEl);

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
                num_options: numOptions,
            }),
            signal: controller.signal,
        });
    } catch (err) {
        clearTimeout(timeoutId);
        shellEl.remove();
        if (err.name === "AbortError") {
            throw new Error("หมดเวลารอการแปล (timeout)");
        }
        throw err;
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
        if (err.name === "AbortError") {
            if (!state.finished && state.accumulated && state.shellEl.isConnected) {
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
                scrollMessagesToBottomAfterLayout(messagesEl);
                return;
            }
            throw new Error("หมดเวลารอการแปล (timeout)");
        }
        if (shellEl.isConnected) shellEl.remove();
        throw err;
    } finally {
        clearTimeout(timeoutId);
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

    scrollMessagesToBottomAfterLayout(messagesEl);
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
        const numOptions = parseInt(form.num_options.value, 10);

        submitBtn.disabled = true;
        try {
            await streamTranslate(conversationId, content, sourceLang, targetLang, detailLevel, numOptions, messagesEl);
            form.content.value = "";
            scrollMessagesToBottomAfterLayout(messagesEl);
        } catch (err) {
            alert("แปลไม่สำเร็จ: " + err.message);
        } finally {
            submitBtn.disabled = false;
        }
    });
}

function setCopyButtonState(btn, copied) {
    const copyIcon = btn.querySelector(".copy-icon");
    const checkIcon = btn.querySelector(".check-icon");
    if (copyIcon) copyIcon.hidden = copied;
    if (checkIcon) checkIcon.hidden = !copied;
    btn.classList.toggle("copied", copied);
}

async function copyCodeBlock(btn) {
    const code = btn.closest(".copy-command-section")?.querySelector(".copy-command-body code");
    if (!code) return;

    try {
        await navigator.clipboard.writeText(code.textContent);
        setCopyButtonState(btn, true);
        setTimeout(() => setCopyButtonState(btn, false), 1500);
    } catch (_) {
        btn.title = "คัดลอกไม่ได้";
        setTimeout(() => {
            btn.title = "คัดลอก";
        }, 1500);
    }
}

function initCopyButtons() {
    document.addEventListener("click", (e) => {
        const btn = e.target.closest(".btn-copy");
        if (btn) copyCodeBlock(btn);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initCopyButtons();
    initChatForm();
});
