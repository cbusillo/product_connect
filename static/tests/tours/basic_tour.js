import { registry } from "@web/core/registry";

// Minimal tour that should work in any environment
registry.category("web_tour.tours").add("test_basic_tour", {
    test: true,
    steps: () => [
        {
            content: "Wait for web client to load",
            trigger: "body.o_web_client",
        },
        {
            content: "Verify navbar exists",
            trigger: ".o_main_navbar",
        },
    ],
});