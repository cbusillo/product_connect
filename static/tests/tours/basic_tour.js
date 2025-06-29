import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_basic_tour", {
    steps: () => [
        {
            content: "Wait for web client to load",
            trigger: "body.o_web_client",
            allowDisabledElements: true,
        },
        {
            content: "Verify navbar exists",
            trigger: ".o_main_navbar",
            run: () => {
                // Verify critical UI elements exist
                if (!document.querySelector(".o_main_navbar")) {
                    throw new Error("Main navbar not found!");
                }
                if (!document.querySelector(".o_navbar_apps_menu")) {
                    throw new Error("Apps menu not found!");
                }
                console.log("✓ Basic tour completed - Odoo UI loaded correctly");
            },
        },
    ],
});