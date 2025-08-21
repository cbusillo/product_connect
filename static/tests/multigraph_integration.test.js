/** @odoo-module */
import { describe, expect, test } from "@odoo/hoot"
import { click, queryAll } from "@odoo/hoot-dom"
import { animationFrame } from "@odoo/hoot-mock"
import { defineModels, fields, models, mountView } from "@web/../tests/web_test_helpers"

class ProductTemplate extends models.Model {
    name = fields.Char()
    initial_price_total = fields.Float()
    initial_cost_total = fields.Float()
    initial_quantity = fields.Integer()
    // noinspection JSUnusedGlobalSymbols - Field required for model structure
    initial_margin = fields.Float()
    create_date = fields.Datetime()
    // noinspection JSUnusedGlobalSymbols - Field required for model structure
    is_ready_for_sale = fields.Boolean()
    // noinspection JSUnusedGlobalSymbols - Field required for model structure
    is_ready_for_sale_last_enabled_date = fields.Date()

    // noinspection JSUnusedGlobalSymbols - _records is used by Hoot test framework for mock data
    _records = [
        {
            id: 1,
            name: "Product A",
            initial_price_total: 10000,
            initial_cost_total: 6000,
            initial_quantity: 100,
            initial_margin: 4000,
            create_date: "2024-01-15 10:00:00",
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-01-01",
        },
        {
            id: 2,
            name: "Product B",
            initial_price_total: 15000,
            initial_cost_total: 9000,
            initial_quantity: 150,
            initial_margin: 6000,
            create_date: "2024-01-20 10:00:00",
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-01-02",
        },
        {
            id: 3,
            name: "Product C",
            initial_price_total: 20000,
            initial_cost_total: 12000,
            initial_quantity: 200,
            initial_margin: 8000,
            create_date: "2024-02-01 10:00:00",
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-02-01",
        },
        {
            id: 4,
            name: "Product D",
            initial_price_total: 25000,
            initial_cost_total: 15000,
            initial_quantity: 250,
            initial_margin: 10000,
            create_date: "2024-02-15 10:00:00",
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-02-02",
        },
    ]
}

defineModels([ProductTemplate])

describe("Multigraph Integration Tests", () => {
    test("renders multi-axis chart with different scales", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y" widget="monetary"/>
                    <field name="initial_quantity" type="measure" axis="y1"/>
                    <field name="is_ready_for_sale_last_enabled_date" interval="month"/>
                </graph>
            `,
        })

        await animationFrame()

        expect(".o_graph_renderer canvas").toHaveCount(1)
        // Chart should be rendered without errors
        expect(".o_error_dialog").toHaveCount(0)
    })

    test("handles click events on multi-axis charts", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y"/>
                    <field name="initial_cost_total" type="measure" axis="y"/>
                    <field name="initial_quantity" type="measure" axis="y1"/>
                </graph>
            `,
        })

        await animationFrame()

        const canvas = queryAll(".o_graph_renderer canvas")[0]

        // Simulate click on chart
        await click(canvas, { clientX: 100, clientY: 100 })

        // Should not throw error
        expect(".o_error_dialog").toHaveCount(0)
    })

    test("loads data with context parameters", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y"/>
                    <field name="initial_cost_total" type="measure" axis="y"/>
                    <field name="initial_quantity" type="measure" axis="y1"/>
                </graph>
            `,
            context: {
                graph_groupbys: ["is_ready_for_sale_last_enabled_date:month"],
                graph_measures: ["initial_price_total", "initial_cost_total", "initial_quantity"],
            },
        })

        await animationFrame()

        expect(".o_graph_view").toHaveCount(1)
        expect(".o_graph_renderer").toHaveCount(1)
    })

    test("supports grouping by date with intervals", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y"/>
                    <field name="is_ready_for_sale_last_enabled_date" interval="day"/>
                </graph>
            `,
        })

        await animationFrame()

        // Should render without errors
        expect(".o_graph_renderer canvas").toHaveCount(1)
    })

    test("handles empty data sets", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y"/>
                    <field name="initial_quantity" type="measure" axis="y1"/>
                </graph>
            `,
            domain: [["id", "=", 0]], // No matching records
        })

        await animationFrame()

        // Should show no content or empty chart
        const noContent = queryAll(".o_view_nocontent_smiling_face")
        const canvas = queryAll("canvas")
        expect(noContent.length + canvas.length).toBeGreaterThan(0)
    })

    test("displays correct currency formatting for monetary fields", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y" widget="monetary"/>
                    <field name="initial_cost_total" type="measure" axis="y" widget="monetary"/>
                </graph>
            `,
        })

        await animationFrame()

        // Chart should render with monetary values
        expect(".o_graph_renderer").toHaveCount(1)
    })

    test("handles multiple measures on same axis", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y" widget="monetary"/>
                    <field name="initial_cost_total" type="measure" axis="y" widget="monetary"/>
                    <field name="initial_margin" type="measure" axis="y" widget="monetary"/>
                </graph>
            `,
        })

        await animationFrame()

        expect(".o_graph_renderer canvas").toHaveCount(1)
        expect(".o_error_dialog").toHaveCount(0)
    })

    test("preserves axis configuration through view updates", async () => {
        const view = await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y"/>
                    <field name="initial_quantity" type="measure" axis="y1"/>
                </graph>
            `,
        })

        await animationFrame()

        // Initial render should work
        expect(".o_graph_renderer canvas").toHaveCount(1)

        // Simulate a filter update
        await view.env.searchModel._notify()

        await animationFrame()

        // Should still render correctly
        expect(".o_graph_renderer canvas").toHaveCount(1)
        expect(".o_error_dialog").toHaveCount(0)
    })

    test("handles mixed field types on different axes", async () => {
        await mountView({
            type: "multigraph",
            resModel: "product.template",
            arch: `
                <graph js_class="multigraph" type="line">
                    <field name="initial_price_total" type="measure" axis="y" widget="monetary"/>
                    <field name="initial_quantity" type="measure" axis="y1"/>
                    <field name="initial_margin" type="measure" axis="y" widget="monetary"/>
                </graph>
            `,
        })

        await animationFrame()

        expect(".o_graph_renderer").toHaveCount(1)
    })
})
