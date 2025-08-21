/** @odoo-module */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("motor_workflow_to_enabled_product_tour", {
    test: true,
    url: "/odoo",
    wait_for: Promise.resolve(),
    steps: () => [
        {
            content: "Wait for Odoo to load",
            trigger: ".o_web_client",
        },
        // Navigate to Inventory app
        {
            content: "Click on home menu",
            trigger: ".o_menu_toggle",
            run: "click",
        },
        {
            content: "Wait for apps view",
            trigger: ".o_apps",
        },
        {
            content: "Click on Inventory app",
            trigger: ".o_app[data-menu-xmlid='stock.menu_stock_root']",
            run: "click",
        },
        {
            content: "Wait for Inventory to load",
            trigger: ".o_breadcrumb:contains('Inventory')",
        },
        // Navigate to Product Connect menu
        {
            content: "Click on Product Connect menu",
            trigger: ".o_menu_item",
            run: function () {
                const menuItems = document.querySelectorAll(".o_menu_item");
                for (const item of menuItems) {
                    if (item.textContent.includes("Product Connect")) {
                        item.click();
                        break;
                    }
                }
            },
        },
        {
            content: "Click on Motors submenu",
            trigger: ".o_menu_item",
            run: function () {
                const menuItems = document.querySelectorAll(".o_menu_item");
                for (const item of menuItems) {
                    if (item.textContent.includes("Motors")) {
                        item.click();
                        break;
                    }
                }
            },
        },
        {
            content: "Wait for motors list view",
            trigger: ".o_list_view",
        },
        // Create a new motor
        {
            content: "Click Create button",
            trigger: ".o_control_panel .o_list_button_add",
            run: "click",
        },
        {
            content: "Wait for form view",
            trigger: ".o_form_view",
        },
        // Fill in motor details
        {
            content: "Fill in Brand",
            trigger: "input[name='brand']",
            run: "edit Test Brand",
        },
        {
            content: "Fill in HP",
            trigger: "input[name='hp']",
            run: "edit 100",
        },
        {
            content: "Select Year",
            trigger: "select[name='year']",
            run: "select 2024",
        },
        // Save the motor
        {
            content: "Save the motor",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Wait for save to complete",
            trigger: ".o_form_view.o_form_saved",
        },
        // Verify motor was created and has pending state
        {
            content: "Verify motor is in pending state",
            trigger: ".o_field_widget[name='state'] .o_status_label",
            run: function () {
                const statusLabel = document.querySelector(".o_field_widget[name='state'] .o_status_label");
                if (!statusLabel || !statusLabel.textContent.includes("Pending")) {
                    throw new Error("Motor is not in Pending state");
                }
            },
        },
        // Click enable button to create product
        {
            content: "Click Enable button",
            trigger: "button[name='action_enable']",
            run: "click",
        },
        {
            content: "Wait for state to change to enabled",
            trigger: ".o_field_widget[name='state'] .o_status_label",
            run: function () {
                const statusLabel = document.querySelector(".o_field_widget[name='state'] .o_status_label");
                if (!statusLabel || !statusLabel.textContent.includes("Enabled")) {
                    throw new Error("Motor is not in Enabled state");
                }
            },
        },
        // Verify product was created
        {
            content: "Verify product link exists",
            trigger: ".o_field_widget[name='product_id'] a",
        },
    ],
});
