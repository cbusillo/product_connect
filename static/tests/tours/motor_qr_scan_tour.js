/** @odoo-module */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("motor_qr_scan_tour", {
    steps: () => [
        {
            content: "Navigate to Motors menu",
            trigger: "a[data-menu-xmlid='product_connect.menu_motor_main']",
            run: "click",
        },
        {
            content: "Click on Motors submenu",
            trigger: "a[data-menu-xmlid='product_connect.menu_motor']",
            run: "click",
        },
        {
            content: "Open an existing motor",
            trigger: ".o_data_row:first",
            run: "click",
        },
        {
            content: "Wait for form to load",
            trigger: ".o_form_view",
            isCheck: true,
        },
        {
            content: "Check if QR code widget is present",
            trigger: ".qr_code_widget",
            isCheck: true,
        },
        {
            content: "Click on QR code to generate",
            trigger: ".qr_code_widget button:contains('Generate QR Code')",
            run: "click",
        },
        {
            content: "Verify QR code image appears",
            trigger: ".qr_code_widget img[src*='data:image']",
            isCheck: true,
        },
        {
            content: "Go back to list view",
            trigger: ".o_back_button",
            run: "click",
        },
        {
            content: "Verify back at motor list",
            trigger: ".o_list_view",
            isCheck: true,
        },
    ],
});