import { describe, test, expect } from "@odoo/hoot";
import { animationFrame } from "@odoo/hoot-mock";
import { mountView } from "@web/../tests/web_test_helpers";

describe("Shipping Analytics Tests", () => {
    test("should render shipping analytics pivot view", async () => {
        const serverData = {
            models: {
                "sale.order": {
                    fields: {
                        name: { string: "Order", type: "char" },
                        source_platform: {
                            string: "Platform",
                            type: "selection",
                            selection: [["shopify", "Shopify"], ["ebay", "eBay"]]
                        },
                        shipping_charge: { string: "Shipping Charge", type: "float" },
                        shipping_paid: { string: "Shipping Paid", type: "float" },
                        shipping_margin: { string: "Shipping Margin", type: "float" },
                    },
                    records: [
                        {
                            id: 1,
                            name: "SO001",
                            source_platform: "shopify",
                            shipping_charge: 25.00,
                            shipping_paid: 18.50,
                            shipping_margin: 6.50,
                        },
                        {
                            id: 2,
                            name: "SO002",
                            source_platform: "ebay",
                            shipping_charge: 15.00,
                            shipping_paid: 20.00,
                            shipping_margin: -5.00,
                        },
                    ],
                },
            },
        };

        await mountView({
            type: "pivot",
            resModel: "sale.order",
            serverData,
            arch: `
                <pivot string="Shipping Analytics">
                    <field name="source_platform" type="row"/>
                    <field name="shipping_charge" type="measure"/>
                    <field name="shipping_paid" type="measure"/>
                    <field name="shipping_margin" type="measure"/>
                </pivot>
            `,
        });

        await animationFrame();

        expect(".o_pivot_table").toHaveCount(1);
    });

    test("should render shipping analytics graph view", async () => {
        const serverData = {
            models: {
                "sale.order": {
                    fields: {
                        source_platform: {
                            string: "Platform",
                            type: "selection",
                            selection: [["shopify", "Shopify"], ["ebay", "eBay"]]
                        },
                        shipping_margin: { string: "Shipping Margin", type: "float" },
                    },
                    records: [
                        {
                            id: 1,
                            source_platform: "shopify",
                            shipping_margin: 25.00,
                        },
                        {
                            id: 2,
                            source_platform: "ebay",
                            shipping_margin: -10.00,
                        },
                    ],
                },
            },
        };

        await mountView({
            type: "graph",
            resModel: "sale.order",
            serverData,
            arch: `
                <graph string="Shipping Analytics" type="bar">
                    <field name="source_platform" type="row"/>
                    <field name="shipping_margin" type="measure"/>
                </graph>
            `,
        });

        await animationFrame();

        expect(".o_graph_canvas_container").toHaveCount(1);
    });

    test("should filter orders with shipping charges", async () => {
        const serverData = {
            models: {
                "sale.order": {
                    fields: {
                        name: { string: "Order", type: "char" },
                        shipping_charge: { string: "Shipping Charge", type: "float" },
                    },
                    records: [
                        { id: 1, name: "SO001", shipping_charge: 20.0 },
                        { id: 2, name: "SO002", shipping_charge: 0.0 },
                        { id: 3, name: "SO003", shipping_charge: 15.0 },
                    ],
                },
            },
        };

        await mountView({
            type: "list",
            resModel: "sale.order",
            serverData,
            arch: `
                <tree>
                    <field name="name"/>
                    <field name="shipping_charge"/>
                </tree>
            `,
            searchViewArch: `
                <search>
                    <filter string="Has Shipping" name="has_shipping" domain="[('shipping_charge', '>', 0)]"/>
                </search>
            `,
            context: { search_default_has_shipping: 1 },
        });

        await animationFrame();

        expect(".o_data_row").toHaveCount(2);
    });
});