/** @odoo-module */

/**
 * Tour test for multigraph view functionality
 * Following Odoo 18 patterns for tour tests
 */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_multigraph_view", {
    test: true,
    // Navigate directly to the analytics action to avoid dependency on Inventory app tiles
    url: "/web#action=product_connect.action_product_processing_analytics",
    // Increase timeout for complex view loading
    timeout: 60000,
    steps: () => [
        // Landed on action page
        {
            content: "Wait for page to load",
            trigger: "body.o_web_client",
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
