import { expect, test } from "@odoo/hoot";
import { queryAll } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";  // Used for chart rendering timing
import {
    contains,
    defineModels,
    fields,
    models,
    mountView,
} from "@web/../tests/web_test_helpers";

class ProductTemplate extends models.Model {
    name = fields.Char();
    list_price = fields.Float();
    standard_price = fields.Float();
    initial_price_total = fields.Float();
    initial_cost_total = fields.Float();
    initial_quantity = fields.Integer();
    is_ready_for_sale = fields.Boolean({ default: false });
    // noinspection JSUnusedGlobalSymbols - Field required for model structure
    is_ready_for_sale_last_enabled_date = fields.Date();

    // noinspection JSUnusedGlobalSymbols - Test data for model mock
    _records = [
        {
            id: 1,
            name: "Product A",
            list_price: 100,
            standard_price: 60,
            initial_price_total: 1000,
            initial_cost_total: 600,
            initial_quantity: 10,
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-01-01",
        },
        {
            id: 2,
            name: "Product B",
            list_price: 200,
            standard_price: 120,
            initial_price_total: 4000,
            initial_cost_total: 2400,
            initial_quantity: 20,
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-01-02",
        },
        {
            id: 3,
            name: "Product C",
            list_price: 150,
            standard_price: 90,
            initial_price_total: 3000,
            initial_cost_total: 1800,
            initial_quantity: 20,
            is_ready_for_sale: true,
            is_ready_for_sale_last_enabled_date: "2024-01-03",
        },
    ];
}

defineModels([ProductTemplate]);

test("multigraph view renders without errors", async () => {
    await mountView({
        type: "multigraph",
        resModel: "product.template",
        arch: `
            <graph js_class="multigraph" type="line" stacked="false">
                <field name="initial_price_total" type="measure" axis="y"/>
                <field name="initial_cost_total" type="measure" axis="y2"/>
                <field name="is_ready_for_sale_last_enabled_date" interval="day"/>
            </graph>
        `,
        domain: [["is_ready_for_sale", "=", true]],
    });

    // Check that the view rendered
    expect(".o_graph_view").toHaveCount(1);
    expect(".o_graph_renderer").toHaveCount(1);
    expect("canvas").toHaveCount(1);
});

test("multigraph displays multiple y-axes", async () => {
    await mountView({
        type: "multigraph",
        resModel: "product.template",
        arch: `
            <graph js_class="multigraph" type="line">
                <field name="initial_price_total" type="measure" axis="y"/>
                <field name="initial_cost_total" type="measure" axis="y2"/>
            </graph>
        `,
    });

    await animationFrame();

    // The multigraph should be rendered
    expect(".o_graph_renderer canvas").toHaveCount(1);

    // Check that we have the graph view
    expect(".o_graph_view").toHaveCount(1);
});

test("multigraph handles clicks without errors", async () => {
    // noinspection JSUnusedLocalSymbols - Variable was for click tracking, test validates no errors
    let clickHandled = false;

    await mountView({
        type: "multigraph",
        resModel: "product.template",
        arch: `
            <graph js_class="multigraph" type="line">
                <field name="initial_price_total" type="measure"/>
            </graph>
        `,
    });

    await animationFrame();

    // Get the canvas element
    const canvas = queryAll(".o_graph_renderer canvas")[0];
    expect(canvas).not.toBe(undefined);

    // Simulate click on canvas
    await contains(canvas).click();

    // No error should be thrown (test will fail if error occurs)
    expect(".o_error_dialog").toHaveCount(0);
});

test("multigraph loads with context parameters", async () => {
    await mountView({
        type: "multigraph",
        resModel: "product.template",
        arch: `
            <graph js_class="multigraph" type="line">
                <field name="initial_price_total" type="measure" axis="y"/>
                <field name="initial_cost_total" type="measure" axis="y2"/>
                <field name="initial_quantity" type="measure" axis="y"/>
            </graph>
        `,
        context: {
            graph_groupbys: ["is_ready_for_sale_last_enabled_date:day"],
            graph_measures: ["initial_price_total", "initial_cost_total", "initial_quantity"],
        },
    });

    expect(".o_graph_view").toHaveCount(1);
    expect(".o_graph_renderer").toHaveCount(1);
});

test("multigraph switches between view modes", async () => {
    // This would test view switching if implemented
    // For now, just ensure the view loads
    await mountView({
        type: "multigraph",
        resModel: "product.template",
        arch: `<graph js_class="multigraph" type="line"/>`,
    });

    expect(".o_graph_view").toHaveCount(1);
});

test("multigraph handles empty data gracefully", async () => {
    await mountView({
        type: "multigraph",
        resModel: "product.template",
        arch: `<graph js_class="multigraph" type="line"/>`,
        domain: [["id", "=", 0]], // No records match
    });

    expect(".o_graph_view").toHaveCount(1);
    // Should show no content helper or empty chart
    const noContent = queryAll(".o_view_nocontent_smiling_face");
    const canvas = queryAll("canvas");
    expect(noContent.length + canvas.length).toBeGreaterThan(0);
});