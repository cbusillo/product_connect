import { registry } from "@web/core/registry"
import { rpc } from "@web/core/network/rpc"

registry.category("web_tour.tours").add("motor_frontend_tour", {
    url: "/web",
    steps: () => [
        {
            trigger: ".o_main_navbar",
            async run() {
                const [stroke] = await rpc("/web/dataset/call_kw/motor.stroke/search_read", {
                    model: "motor.stroke",
                    method: "search_read",
                    args: [[], ["id"]],
                    kwargs: { limit: 1 },
                })
                const [config] = await rpc("/web/dataset/call_kw/motor.configuration/search_read", {
                    model: "motor.configuration",
                    method: "search_read",
                    args: [[], ["id"]],
                    kwargs: { limit: 1 },
                })
                const manufacturer = await rpc("/web/dataset/call_kw/product.manufacturer/create", {
                    model: "product.manufacturer",
                    method: "create",
                    args: [{ name: "Maker", is_motor_manufacturer: true }],
                    kwargs: {},
                })
                const color = await rpc("/web/dataset/call_kw/product.color/create", {
                    model: "product.color",
                    method: "create",
                    args: [{ name: "Red" }],
                    kwargs: {},
                })
                window.motorId = await rpc("/web/dataset/call_kw/motor/create", {
                    model: "motor",
                    method: "create",
                    args: [
                        {
                            manufacturer,
                            stroke: stroke.id,
                            configuration: config.id,
                            horsepower: 100,
                            color,
                        },
                    ],
                    kwargs: {},
                })
            },
        },
        {
            trigger: ".o_main_navbar",
            run() {
                window.location.assign(`/web#id=${window.motorId}&model=motor&view_type=form`)
            },
        },
        {
            trigger: ".o_form_view",
        },
        {
            trigger: ".o_notebook .nav-link:contains(Basic Testing)",
            run: "click",
        },
        {
            trigger: ".o_motor_test",
        },
        {
            trigger: ".o_motor_test .o_selection_badge:not(.btn-reset)",
            run: "click",
        },
        {
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            trigger: ".o_form_button_edit",
        },
    ],
})
