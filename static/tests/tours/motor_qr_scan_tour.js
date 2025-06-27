/** @odoo-module */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("motor_qr_scan_tour", {
    test: true,
    steps: () => [
        {
            content: "Open the app menu",
            trigger: ".o_navbar_apps_menu button",
            run: "click",
        },
        {
            content: "Click on the Motors app",
            trigger: ".o-dropdown--menu .dropdown-item:contains('Motors')",
            run: "click",
        },
        {
            content: "Wait for motor list to load",
            trigger: ".o_list_view",
        },
        {
            content: "Open an existing motor",
            trigger: ".o_data_row:first",
            run: "click",
        },
        {
            content: "Wait for form to load",
            trigger: ".o_form_view",
        },
        {
            content: "Check if QR code widget is present",
            trigger: ".qr_code_widget",
        },
        {
            content: "Click on QR code to generate",
            trigger: ".qr_code_widget button:contains('Generate QR Code')",
            run: "click",
        },
        {
            content: "Verify QR code image appears",
            trigger: ".qr_code_widget img[src*='data:image']",
        },
        {
            content: "Go back to list view",
            trigger: ".o_back_button",
            run: "click",
        },
        {
            content: "Verify back at motor list",
            trigger: ".o_list_view",
        },
    ],
});