/** @odoo-module */

import { registry } from "@web/core/registry";

/**
 * Example tour test for Product Connect module
 * This tour demonstrates navigating to the Product Connect app and performing basic actions
 */
registry.category("web_tour.tours").add("example_product_tour", {
    test: true,
    url: "/web#action=product_connect.action_product_template",
    steps: () => [
        {
            content: "Wait for web client to be ready",
            trigger: ".o_web_client",
        },
        {
            content: "Wait for product view to render",
            trigger: ".o_list_view, .o_kanban_view",
            run() {
                const view = document.querySelector(".o_list_view, .o_kanban_view");
                if (!view) {
                    throw new Error("Expected a product view to be visible");
                }
            },
        },
        {
            content: "Confirm breadcrumb exists",
            trigger: ".o_breadcrumb",
            run() {
                const bc = document.querySelector(".o_breadcrumb");
                console.log("Breadcrumb:", bc && bc.textContent);
            },
        },
        {
            content: "Tour finished",
            trigger: "body",
            run() {
                console.log("example_product_tour finished");
            },
        },
    ],
});
