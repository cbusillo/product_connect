import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_basic_tour", {
    test: true,
    url: "/odoo",
    steps: () => [
        {
            content: "Wait for Odoo to load",
            trigger: ".o_web_client",
        },
        // User menu is present in header
        {
            content: "Click on user menu",
            trigger: ".o_user_menu button",
            run: "click",
        },
        {
            content: "Close user menu",
            trigger: ".o_user_menu button",
            run: "click",
        },
        // Click on home menu icon to go to apps
        {
            content: "Click on home menu",
            trigger: ".o_menu_toggle",
            run: "click",
        },
        {
            content: "Wait for apps view",
            trigger: ".o_apps",
        },
        // Click on Inventory app
        {
            content: "Click on Inventory app",
            trigger: ".o_app[data-menu-xmlid='stock.menu_stock_root']",
            run: "click",
        },
        {
            content: "Wait for Inventory to load",
            trigger: ".o_breadcrumb:contains('Inventory')",
        },
        // Verify no errors occurred
        {
            content: "Verify no errors",
            trigger: "body:not(.o_error_dialog)",
            run: function() {
                // Check that no error dialog is present
                const errorDialog = document.querySelector(".o_error_dialog");
                if (errorDialog) {
                    throw new Error("Error dialog found when none expected");
                }
            },
        },
    ],
});