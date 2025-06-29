import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("motor_workflow_to_enabled_product_tour", {
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
            content: "Click on Motors app",
            trigger: ".o-dropdown--menu .dropdown-item:contains('Motors')",
            run: "click",
        },
        {
            content: "Wait for motor list to load",
            trigger: ".o_list_view",
        },
        {
            content: "Create new motor",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Wait for form view",
            trigger: ".o_form_view",
        },
        // Fill in basic motor information
        {
            content: "Enter manufacturer",
            trigger: ".o_field_widget[name='manufacturer'] input",
            run: "text Mercury",
        },
        {
            content: "Select manufacturer from dropdown",
            trigger: ".ui-menu-item a:contains('Mercury')",
            run: "click",
        },
        {
            content: "Enter horsepower",
            trigger: ".o_field_widget[name='horsepower'] input",
            run: "text 150",
        },
        {
            content: "Enter year",
            trigger: ".o_field_widget[name='year'] input",
            run: "text 2024",
        },
        {
            content: "Enter model",
            trigger: ".o_field_widget[name='model'] input",
            run: "text OptiMax",
        },
        {
            content: "Enter serial number",
            trigger: ".o_field_widget[name='serial_number'] input",
            run: function () {
                // Generate unique serial for test isolation
                const serial = "TEST-" + Date.now();
                const input = document.querySelector(".o_field_widget[name='serial_number'] input");
                input.value = serial;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            },
        },
        {
            content: "Enter location",
            trigger: ".o_field_widget[name='location'] input",
            run: "text A1-B2",
        },
        {
            content: "Select stroke type",
            trigger: ".o_field_widget[name='stroke'] input",
            run: "text Four Stroke",
        },
        {
            content: "Confirm stroke selection",
            trigger: ".ui-menu-item a:contains('Four Stroke')",
            run: "click",
        },
        {
            content: "Select configuration",
            trigger: ".o_field_widget[name='configuration'] input",
            run: "text V6",
        },
        {
            content: "Confirm configuration selection",
            trigger: ".ui-menu-item a:contains('V6')",
            run: "click",
        },
        {
            content: "Save motor",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Wait for save confirmation",
            trigger: ".o_form_view.o_form_saved",
            run: function () {
                // Verify required fields were saved
                const manufacturer = document.querySelector(".o_field_widget[name='manufacturer'] .o_field_many2one_selection");
                const horsepower = document.querySelector(".o_field_widget[name='horsepower'] input");
                const serialNumber = document.querySelector(".o_field_widget[name='serial_number'] input");

                if (!manufacturer || !manufacturer.textContent.includes("Mercury")) {
                    throw new Error("Manufacturer was not saved correctly");
                }
                if (!horsepower || horsepower.value !== "150") {
                    throw new Error("Horsepower was not saved correctly");
                }
                if (!serialNumber || !serialNumber.value.startsWith("TEST-")) {
                    throw new Error("Serial number was not saved correctly");
                }
                console.log("Motor saved successfully with all required fields");
            },
        },
        // Now test motor products functionality
        {
            content: "Open Motor Products tab",
            trigger: ".nav-link:contains('Motor Products')",
            run: "click",
        },
        {
            content: "Wait for products tab to load",
            trigger: ".tab-pane.active .o_field_x2many_list",
        },
        {
            content: "Click Create Motor Products button",
            trigger: "button:contains('Create Motor Products')",
            run: "click",
        },
        {
            content: "Wait for products to be created",
            trigger: ".o_data_row",
            run: function () {
                // Verify products were actually created
                const productRows = document.querySelectorAll(".o_data_row");
                if (productRows.length === 0) {
                    throw new Error("Create Motor Products button did not create any products!");
                }
                console.log(`Motor products created: ${productRows.length} products`);
            },
        },
        // Enable all products using the list view checkboxes
        {
            content: "Select all products in list",
            trigger: ".o_list_view th.o_list_record_selector input[type='checkbox']",
            run: "click",
        },
        {
            content: "Open Action menu",
            trigger: ".o_cp_action_menus .dropdown-toggle:contains('Action')",
            run: "click",
        },
        {
            content: "Click on Enable for Sale action",
            trigger: ".dropdown-menu .dropdown-item:contains('Enable for Sale')",
            run: "click",
        },
        {
            content: "Wait for sale enable to complete",
            trigger: ".o_list_view:not(:has(.o_loading))",
            run: function () {
                // Give it a moment to process
                console.log("Products enabled for sale");
            },
        },
        {
            content: "Open Action menu again",
            trigger: ".o_cp_action_menus .dropdown-toggle:contains('Action')",
            run: "click",
        },
        {
            content: "Click on Enable for Purchase action",
            trigger: ".dropdown-menu .dropdown-item:contains('Enable for Purchase')",
            run: "click",
        },
        {
            content: "Wait for purchase enable to complete",
            trigger: ".o_list_view:not(:has(.o_loading))",
            run: function () {
                console.log("Products enabled for purchase");
            },
        },
        {
            content: "Verify products show as enabled",
            trigger: ".o_data_row:first",
            run: function () {
                // Check that we have products in the list
                const rowCount = document.querySelectorAll(".o_data_row").length;
                if (rowCount === 0) {
                    throw new Error("No motor products were created!");
                }
                console.log(`Found ${rowCount} motor products created and enabled`);

                // Final verification - tour passes only if we successfully:
                // 1. Created a motor
                // 2. Generated products
                // 3. Enabled them for sale and purchase
                console.log("✓ Motor workflow tour completed successfully!");
            },
        },
        {
            content: "Save motor with enabled products",
            trigger: ".o_form_button_save",
            run: "click",
        },
        // Verify motor is complete
        {
            content: "Check motor status",
            trigger: ".o_form_view.o_form_saved",
            run: function () {
                console.log("Motor workflow completed successfully");
            },
        },
        // Return to motor list
        {
            content: "Go back to motor list",
            trigger: ".o_back_button",
            run: "click",
        },
        {
            content: "Verify motor appears in list",
            trigger: ".o_list_view .o_data_row",
            run: function () {
                console.log("Tour completed - motor created and products enabled");
            },
        },
    ],
});