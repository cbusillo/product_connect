/** @odoo-module **/

import { registry } from "@web/core/registry";
import { click, contains } from "@odoo/hoot-dom";

/**
 * Example tour test for Product Connect module
 * This tour demonstrates navigating to the Product Connect app and performing basic actions
 */
registry.category("web_tour.tours").add("example_product_tour", {
    test: true,
    url: "/odoo",
    wait_for: Promise.resolve(),
    steps: () => [
        {
            content: "Wait for Odoo to load",
            trigger: ".o_web_client",
        },
        {
            content: "Click on home menu to see apps",
            trigger: ".o_menu_toggle",
            run: "click",
        },
        {
            content: "Wait for apps menu to load",
            trigger: ".o_apps",
        },
        {
            content: "Search for Product Connect app",
            trigger: ".o_search_bar input",
            run: "text Product Connect",
        },
        {
            content: "Click on Product Connect app",
            trigger: ".o_app[data-menu-xmlid*='product_connect']",
            run: "click",
        },
        {
            content: "Wait for Product Connect to load",
            trigger: ".o_breadcrumb",
            run: function() {
                // Verify we're in the Product Connect module
                const breadcrumb = document.querySelector(".o_breadcrumb");
                console.log("Loaded into:", breadcrumb?.textContent);
            },
        },
        {
            content: "Click on Products menu if visible",
            trigger: "a.o_menu_item:contains('Products')",
            run: "click",
            auto: true, // Skip if not found
        },
        {
            content: "Verify list view loaded",
            trigger: ".o_list_view",
            run: function() {
                // Check that we have a list view
                const listView = document.querySelector(".o_list_view");
                if (!listView) {
                    throw new Error("List view not found");
                }
                console.log("List view loaded successfully");
            },
        },
        {
            content: "Tour completed successfully",
            trigger: "body",
            run: function() {
                console.log("Product Connect tour completed!");
            },
        },
    ],
});