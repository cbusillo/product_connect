/**
 * Tour test for multigraph view functionality
 * Following Odoo 18 patterns for tour tests
 */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_multigraph_view", {
    test: true,
    url: "/odoo",
    // Increase timeout for complex view loading
    timeout: 60000,
    steps: () => [
        // Start from home
        {
            content: "Wait for page to load",
            trigger: "body.o_web_client",
        },
        {
            content: "Open apps menu if needed",
            trigger: ".o_menu_toggle:visible,.o_apps:visible",
            run: function () {
                const toggle = document.querySelector(".o_menu_toggle");
                const apps = document.querySelector(".o_apps");
                if (toggle && !apps) {
                    toggle.click();
                }
            },
        },
        {
            content: "Wait for apps to be visible",
            trigger: ".o_apps",
        },
        {
            trigger: ".o_app[data-menu-xmlid='stock.menu_stock_root']",
            content: "Open Inventory app",
            run: "click",
        },
        {
            content: "Wait for Inventory app to load",
            trigger: ".o_menu_brand:contains('Inventory'),.o_breadcrumb:contains('Inventory')",
        },
        {
            trigger: "a.o_menu_item:contains('Reporting'),button.o_menu_item:contains('Reporting')",
            content: "Open Reporting menu",
            run: "click",
        },
        {
            trigger: "a.o_menu_item:contains('Product Processing'),button.o_menu_item:contains('Product Processing')",
            content: "Open Product Processing Analytics",
            run: "click",
        },
        {
            trigger: ".o_graph_view,.o_list_view,.o_pivot_view",
            content: "Wait for any view to load",
            run: function () {
                console.log("View loaded:", this.querySelector(".o_graph_view") ? "graph" :
                    this.querySelector(".o_list_view") ? "list" : "pivot");
            },
        },
        {
            trigger: ".o_graph_view .o_graph_renderer",
            content: "Wait for graph renderer",
            run: function () {
                console.log("Graph renderer found, waiting for canvas...");
            },
        },
        {
            trigger: ".o_graph_view .o_graph_renderer canvas",
            content: "Wait for canvas to be rendered",
            run: async function () {
                const canvas = this;
                // Wait for canvas to have actual dimensions
                let attempts = 0;
                while (attempts < 50 && (!canvas.offsetWidth || !canvas.offsetHeight)) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    attempts++;
                }
                console.log("Canvas ready with dimensions:", canvas.offsetWidth, "x", canvas.offsetHeight);
            },
        },
        {
            trigger: ".o_graph_view .o_graph_renderer canvas",
            content: "Click on the chart if present",
            run: function () {
                const canvas = this;
                if (canvas && canvas.offsetWidth > 0) {
                    // Create a click event at the center of the canvas
                    const rect = canvas.getBoundingClientRect();
                    const event = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true,
                        clientX: rect.left + rect.width / 2,
                        clientY: rect.top + rect.height / 2
                    });
                    canvas.dispatchEvent(event);
                    console.log("Clicked on canvas");
                }
            },
        },
        {
            trigger: "body:not(:has(.o_error_dialog))",
            content: "Verify no error dialog appears",
            run: function () {
                console.log("No error dialog - test successful");
            },
        },
        // Optional view switching steps - only if buttons exist
        {
            trigger: "button.o_switch_view.o_list:visible,body:not(:has(button.o_switch_view))",
            content: "Switch to list view if button exists",
            run: function () {
                const button = document.querySelector("button.o_switch_view.o_list:not(.active)");
                if (button) {
                    button.click();
                    console.log("Switching to list view");
                } else {
                    console.log("No list view button or already active");
                }
            },
        },
        {
            trigger: ".o_list_view,.o_graph_view",
            content: "Verify view is present",
            run: function () {
                console.log("Current view:", this.querySelector(".o_list_view") ? "list" : "graph");
            },
        },
    ],
});