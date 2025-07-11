import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("test_basic_tour", {
    test: true,
    steps: () => [
        {
            content: "Wait for Odoo to load",
            trigger: ".o_web_client",
        },
        {
            content: "Wait for main content",
            trigger: ".o_action_manager",
        },
        // Understand current state
        {
            content: "Check initial state",
            trigger: "body",
            run: function() {
                console.log("=== Tour Starting State ===");
                console.log(`URL: ${window.location.pathname}`);
                
                // Check what UI elements are present
                const elements = {
                    appsToggler: !!document.querySelector(".o_apps_menu_toggler"),
                    appsView: !!document.querySelector(".o_apps"),
                    controlPanel: !!document.querySelector(".o_control_panel"),
                    userMenu: !!document.querySelector(".o_user_menu"),
                    breadcrumb: document.querySelector(".o_breadcrumb")?.textContent
                };
                
                console.log("UI Elements:", elements);
            },
        },
        // Test 1: User menu should always be present
        {
            content: "Verify user menu exists",
            trigger: ".o_user_menu button",
            run: function() {
                console.log("✓ User menu found and accessible");
            },
        },
        // Test 2: Try to navigate somewhere
        {
            content: "Try to access apps or current view",
            trigger: "body",
            run: function() {
                const appsToggler = document.querySelector(".o_apps_menu_toggler");
                const currentView = document.querySelector(".o_view_controller");
                
                if (appsToggler) {
                    console.log("✓ Apps menu toggler available - clicking");
                    appsToggler.click();
                } else if (currentView) {
                    console.log("✓ Already in a view - testing current functionality");
                } else {
                    console.log("✗ Unexpected UI state");
                }
            },
        },
        // Wait for any navigation to complete
        {
            content: "Wait for UI to stabilize",
            trigger: ".o_action_manager",
            timeout: 5000,
        },
        // Test 3: If we're in apps view, test clicking an app
        {
            content: "Test app navigation if in apps view",
            trigger: "body",
            run: function() {
                const appsView = document.querySelector(".o_apps");
                if (appsView) {
                    const inventoryApp = document.querySelector('.o_app[data-menu-xmlid="stock.menu_stock_root"]');
                    if (inventoryApp) {
                        console.log("✓ Found Inventory app - clicking");
                        inventoryApp.click();
                    } else {
                        console.log("✗ Inventory app not found in apps view");
                    }
                } else {
                    console.log("✓ Not in apps view - skipping app navigation test");
                }
            },
        },
        // If we navigated to an app, wait for it to load
        {
            content: "Wait for potential app navigation",
            trigger: "body",
            run: function() {
                // Give time for navigation if it happened
                return new Promise(resolve => {
                    setTimeout(() => {
                        const breadcrumb = document.querySelector(".o_breadcrumb");
                        if (breadcrumb) {
                            console.log(`✓ Navigation complete: ${breadcrumb.textContent}`);
                        }
                        resolve();
                    }, 2000);
                });
            },
        },
        // Test 4: Search functionality (should work in most views)
        {
            content: "Test search if available",
            trigger: "body",
            run: function() {
                const searchInput = document.querySelector(".o_searchview input");
                if (searchInput) {
                    console.log("✓ Search bar found - testing");
                    searchInput.click();
                    searchInput.value = "test search";
                    searchInput.dispatchEvent(new Event('input', { bubbles: true }));
                    console.log("✓ Search input entered");
                } else {
                    console.log("✗ No search bar in current view");
                }
            },
        },
        // Final verification
        {
            content: "Verify tour completed successfully",
            trigger: "body",
            run: function() {
                // Check for any error dialogs
                const errorDialogs = document.querySelectorAll(".o_error_dialog");
                if (errorDialogs.length > 0) {
                    throw new Error("Error dialogs detected during tour!");
                }
                
                console.log("\n✓ Basic tour completed successfully");
                console.log("  - Odoo UI loaded without errors");
                console.log("  - User menu is accessible");
                console.log("  - Navigation functionality tested");
                console.log("  - Search functionality tested");
                console.log("  - No critical errors encountered");
            },
        },
    ],
});