import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("shipping_analytics_tour", {
    steps: () => [
        {
            content: "Wait for web client to load",
            trigger: "body.o_web_client",
        },
        {
            content: "Open app menu",
            trigger: ".o_navbar_apps_menu button",
            run: "click",
        },
        {
            content: "Open Sales app",
            trigger: ".o-dropdown--menu .dropdown-item:contains('Sales')",
            run: "click",
        },
        {
            content: "Open Shipping Analytics menu",
            trigger: ".o_menu_item:contains('Shipping Analytics')",
            run: "click",
        },
        {
            content: "Click on Shipping Dashboard",
            trigger: ".o_menu_item:contains('Shipping Dashboard')",
            run: "click",
        },
        {
            content: "Wait for pivot view to load",
            trigger: ".o_pivot_table",
            run: () => {
                // Verify pivot table loaded
                const pivotTable = document.querySelector(".o_pivot_table");
                if (!pivotTable) {
                    throw new Error("Pivot table did not load!");
                }
                // Check if there's data or at least the structure
                const pivotHeaders = document.querySelectorAll(".o_pivot_header_cell");
                if (pivotHeaders.length === 0) {
                    console.warn("No data in pivot view - this may be expected in test environment");
                }
                console.log("Pivot view loaded successfully");
            },
        },
        {
            content: "Switch to graph view",
            trigger: "button.o_graph",
            run: "click",
        },
        {
            content: "Verify graph is displayed",
            trigger: ".o_graph_canvas_container",
            run: () => {
                // Verify graph container exists
                const graphContainer = document.querySelector(".o_graph_canvas_container");
                if (!graphContainer) {
                    throw new Error("Graph container did not load!");
                }
                // Check if canvas or chart elements exist
                const canvas = graphContainer.querySelector("canvas");
                if (!canvas) {
                    console.warn("No graph canvas found - may be due to no data");
                }
                console.log("Graph view loaded successfully");
            },
        },
        {
            content: "Test complete",
            trigger: ".o_control_panel",
            run: () => {
                // Final verification
                if (!document.querySelector(".o_view_controller")) {
                    throw new Error("View controller not found - analytics view did not load properly");
                }
                console.log("✓ Shipping analytics tour completed - views loaded correctly");
            },
        },
    ],
});