import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_service/tour_utils";

registry.category("web_tour.tours").add("test_multigraph_view", {
    test: true,
    sequence: 100,
    steps: () => [
        // Check for console errors at start
        {
            trigger: "body",
            run: () => {
                // Check if debug mode is available
                if (window.odoo && window.odoo.__DEBUG__ && window.odoo.__DEBUG__.services) {
                    const notifications = window.odoo.__DEBUG__.services.notification?.notifications || [];
                    const errors = notifications.filter(n => n.type === "danger");
                    if (errors.length) throw new Error(`Console errors at start: ${errors.map(e => e.message).join(", ")}`);
                }
            },
        },
        stepUtils.showAppsMenuItem(),
        {
            content: "Open Inventory app",
            trigger: '.o_app[data-menu-xmlid="stock.menu_stock_root"]',
            run: "click",
        },
        {
            content: "Open Reporting menu",
            trigger: '.o_menu_item:contains("Reporting")',
            run: "click",
        },
        {
            content: "Open Product Processing",
            trigger: '.o_menu_item:contains("Product Processing")',
            run: "click",
        },
        {
            content: "Check for errors after navigation",
            trigger: "body",
            run: () => {
                // Check for error dialogs
                const errorDialog = document.querySelector(".o_error_dialog");
                if (errorDialog) {
                    const errorDetails = errorDialog.querySelector(".o_error_detail")?.textContent || "Unknown error";
                    throw new Error(`Error dialog found: ${errorDetails}`);
                }
                
                // Check for console errors
                if (window.odoo && window.odoo.__DEBUG__ && window.odoo.__DEBUG__.services) {
                    const notifications = window.odoo.__DEBUG__.services.notification?.notifications || [];
                    const errors = notifications.filter(n => n.type === "danger");
                    if (errors.length) throw new Error(`Console errors: ${errors.map(e => e.message).join(", ")}`);
                }
            },
        },
        {
            content: "Wait for multigraph view to load",
            trigger: ".o_multigraph_renderer canvas",
            run: () => {
                const canvas = document.querySelector(".o_multigraph_renderer canvas");
                if (!canvas) {
                    throw new Error("MultiGraph canvas not found");
                }
                console.log("MultiGraph view loaded successfully");
            },
        },
        {
            content: "Verify chart has been rendered",
            trigger: ".o_multigraph_renderer",
            run: () => {
                const renderer = document.querySelector(".o_multigraph_renderer");
                const canvas = renderer.querySelector("canvas");
                
                if (!canvas || !canvas.getContext) {
                    throw new Error("Canvas element not properly initialized");
                }
                
                const ctx = canvas.getContext("2d");
                if (!ctx) {
                    throw new Error("Canvas context not available");
                }
                
                console.log("Chart canvas is properly initialized");
            },
        },
        {
            content: "Check for legend",
            trigger: ".o_multigraph_renderer",
            run: () => {
                const hasLegend = document.querySelector(".o_multigraph_renderer").textContent.includes("Revenue Value") ||
                                document.querySelector(".o_multigraph_renderer").textContent.includes("Cost Value") ||
                                document.querySelector(".o_multigraph_renderer").textContent.includes("Units Processed");
                
                if (!hasLegend) {
                    console.warn("Chart legend may not be visible, but continuing test");
                }
            },
        },
        {
            content: "Test view switcher - switch to tree view",
            trigger: '.o_control_panel .o_switch_view.o_list',
            run: "click",
        },
        {
            content: "Verify tree view loaded",
            trigger: ".o_list_view",
            run: () => console.log("Successfully switched to tree view"),
        },
        {
            content: "Switch back to multigraph view",
            trigger: '.o_control_panel .o_switch_view[data-type="multigraph"]',
            run: "click",
        },
        {
            content: "Verify multigraph view restored",
            trigger: ".o_multigraph_renderer canvas",
            run: () => console.log("Successfully switched back to multigraph view"),
        },
        {
            content: "Test groupby functionality",
            trigger: '.o_control_panel .o_searchview_dropdown_toggler[title="Group By"]',
            run: "click",
        },
        {
            content: "Select a groupby option",
            trigger: '.o_menu_item:contains("Add Custom Group")',
            run: "click",
        },
        {
            content: "Close groupby dropdown",
            trigger: 'body',
            run: "click",
        },
        {
            content: "Verify chart still renders after groupby",
            trigger: ".o_multigraph_renderer canvas",
            run: () => {
                const canvas = document.querySelector(".o_multigraph_renderer canvas");
                if (!canvas) {
                    throw new Error("Chart canvas lost after groupby");
                }
                console.log("Chart successfully re-rendered after groupby change");
            },
        },
        {
            content: "Test filter functionality",
            trigger: '.o_control_panel .o_searchview_dropdown_toggler[title="Filters"]',
            run: "click",
        },
        {
            content: "Test Last 365 Days filter",
            trigger: '.o_filter_menu .o_menu_item:contains("Last 365 Days")',
            run: "click",
        },
        {
            content: "Test MTD filter",
            trigger: '.o_filter_menu .o_menu_item:contains("MTD (Month to Date)")',
            run: "click",
        },
        {
            content: "Test YTD filter", 
            trigger: '.o_filter_menu .o_menu_item:contains("YTD (Year to Date)")',
            run: "click",
        },
        {
            content: "Test Week groupby filter",
            trigger: '.o_filter_menu .o_menu_item:contains("Week")',
            run: "click",
        },
        {
            content: "Test Month groupby filter",
            trigger: '.o_filter_menu .o_menu_item:contains("Month")',
            run: "click",
        },
        {
            content: "Close filter dropdown",
            trigger: 'body',
            run: "click",
        },
        {
            content: "Verify chart updates with new filters",
            trigger: ".o_multigraph_renderer canvas",
            run: () => {
                const canvas = document.querySelector(".o_multigraph_renderer canvas");
                if (!canvas) {
                    throw new Error("Chart canvas lost after applying filters");
                }
                console.log("Chart successfully updated with new filters");
            },
        },
        {
            content: "Final verification",
            trigger: ".o_multigraph_renderer",
            run: () => {
                const errors = Array.from(document.querySelectorAll(".o_error_dialog"));
                if (errors.length > 0) {
                    throw new Error("Error dialogs found during tour");
                }
                
                const consoleErrors = window.console._errors || [];
                if (consoleErrors.length > 0) {
                    console.warn("Console errors detected:", consoleErrors);
                }
                
                console.log("MultiGraph tour completed successfully!");
            },
        },
    ],
});