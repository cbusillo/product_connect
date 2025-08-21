/** @odoo-module */

// Disable WebSocket attempts during tests to avoid 503 noise
// and rely on longpolling fallback instead.
(function disableWebSocketForTests() {
    try {
        if (window.__WS_DISABLED_FOR_TESTS__) return;
        const OriginalWS = window.WebSocket;
        // If already undefined, nothing to do
        if (typeof OriginalWS === "undefined") return;

        function DisabledWebSocket() {
            throw new Error("WebSocket disabled for tests");
        }
        // Preserve static constants if present
        for (const k of ["CONNECTING", "OPEN", "CLOSING", "CLOSED"]) {
            if (Object.prototype.hasOwnProperty.call(OriginalWS, k)) {
                DisabledWebSocket[k] = OriginalWS[k];
            }
        }
        window.WebSocket = DisabledWebSocket;
        window.__WS_DISABLED_FOR_TESTS__ = true;
        // Also guard against ReconnectingWebSocket wrappers using global WebSocket
        if (typeof globalThis !== 'undefined') {
            globalThis.WebSocket = DisabledWebSocket;
        }
        console.log("[product_connect] WebSocket disabled for tests; using longpolling");
    } catch (e) {
        // Non-fatal; tests can proceed regardless
        console.warn("[product_connect] Failed to disable WebSocket for tests", e);
    }
})();
