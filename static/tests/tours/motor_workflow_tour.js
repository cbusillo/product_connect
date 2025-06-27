/** @odoo-module */

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("motor_workflow_tour", {
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
            content: "Create new motor",
            trigger: ".o_list_button_add",
            run: "click",
        },
        {
            content: "Select manufacturer",
            trigger: ".o_field_widget[name='manufacturer'] input",
            run: "text TestMaker",
        },
        {
            content: "Confirm manufacturer selection",
            trigger: ".ui-menu-item a:contains('TestMaker')",
            run: "click",
        },
        {
            content: "Select stroke",
            trigger: ".o_field_widget[name='stroke'] input",
            run: "text Four",
        },
        {
            content: "Confirm stroke selection",
            trigger: ".ui-menu-item a:contains('Four')",
            run: "click",
        },
        {
            content: "Select configuration",
            trigger: ".o_field_widget[name='configuration'] input",
            run: "text V8",
        },
        {
            content: "Confirm configuration selection",
            trigger: ".ui-menu-item a:contains('V8')",
            run: "click",
        },
        {
            content: "Enter horsepower",
            trigger: ".o_field_widget[name='horsepower'] input",
            run: "text 250",
        },
        {
            content: "Enter location",
            trigger: ".o_field_widget[name='location'] input",
            run: "text A1",
        },
        {
            content: "Enter serial number",
            trigger: ".o_field_widget[name='serial_number'] input",
            run: "text SN12345",
        },
        {
            content: "Enter year",
            trigger: ".o_field_widget[name='year'] input",
            run: "text 2024",
        },
        {
            content: "Enter model",
            trigger: ".o_field_widget[name='model'] input",
            run: "text SuperV8",
        },
        {
            content: "Save motor",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Verify motor was saved",
            trigger: ".o_form_view.o_form_saved",
        },
        {
            content: "Go back to list view",
            trigger: ".o_back_button",
            run: "click",
        },
        {
            content: "Verify motor appears in list",
            trigger: ".o_data_row:contains('SN12345')",
        },
    ],
});