/** @odoo-module */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("shipping_analytics_tour", {
    test: true,
    url: "/web",
    steps: () => [
        {
            content: "Wait for Odoo to load",
            trigger: ".o_web_client",
        },
        // Navigate to apps
        {
            content: "Click on home menu",
            trigger: ".o_menu_toggle",
            run: "click",
        },
        {
            content: "Wait for apps view",
            trigger: ".o_apps",
        },
        // Navigate to Sales app
        {
            content: "Click on Sales app",
            trigger: ".o_app[data-menu-xmlid='sale.sale_menu_root']",
            run: "click",
        },
        {
            content: "Wait for Sales to load",
            trigger: ".o_breadcrumb:contains('Sales')",
        },
        // Navigate to Reporting > Shipping Analytics
        {
            content: "Click on Reporting menu",
            trigger: ".o_menu_item:contains('Reporting')",
            run: "click",
        },
        {
            content: "Click on Shipping Analytics",
            trigger: ".o_menu_item:contains('Shipping Analytics')",
            run: "click",
        },
        // Wait for pivot view to load
        {
            content: "Wait for pivot view",
            trigger: ".o_pivot",
        },
        // Test pivot controls
        {
            content: "Verify pivot table is displayed",
            trigger: ".o_pivot_table_header",
        },
        // Switch to graph view
        {
            content: "Switch to graph view",
            trigger: "button.o_switch_view.o_graph",
            run: "click",
        },
        {
            content: "Wait for graph view",
            trigger: ".o_graph_view",
        },
        // Verify graph renders
        {
            content: "Verify graph canvas",
            trigger: ".o_graph_renderer canvas",
        },
        // Switch back to pivot
        {
            content: "Switch back to pivot view",
            trigger: "button.o_switch_view.o_pivot",
            run: "click",
        },
        {
            content: "Verify pivot view loads again",
            trigger: ".o_pivot",
        },
        // Verify no errors
        {
            content: "Verify no errors occurred",
            trigger: "body:not(:has(.o_error_dialog))",
        },
    ],
});
