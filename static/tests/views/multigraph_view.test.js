import { click, getFixture } from "@web/../tests/helpers/utils";
import { makeView, setupViewRegistries } from "@web/../tests/views/helpers";

QUnit.module("product_connect", (hooks) => {
    let serverData;
    let target;

    hooks.beforeEach(() => {
        target = getFixture();
        setupViewRegistries();
        
        serverData = {
            models: {
                "product.template": {
                    fields: {
                        name: { string: "Product Name", type: "char" },
                        list_price: { string: "Revenue Value", type: "float", store: true },
                        standard_price: { string: "Cost Value", type: "float", store: true },
                        qty_available: { string: "Units Processed", type: "float", store: true },
                        create_date: { string: "Date", type: "datetime", store: true },
                    },
                    records: [
                        {
                            id: 1,
                            name: "Product A",
                            list_price: 1000,
                            standard_price: 600,
                            qty_available: 10,
                            create_date: "2024-01-15 10:00:00",
                        },
                        {
                            id: 2,
                            name: "Product B", 
                            list_price: 2000,
                            standard_price: 1200,
                            qty_available: 15,
                            create_date: "2024-02-15 10:00:00",
                        },
                        {
                            id: 3,
                            name: "Product C",
                            list_price: 1500,
                            standard_price: 900,
                            qty_available: 12,
                            create_date: "2024-03-15 10:00:00",
                        },
                    ],
                },
            },
        };
    });

    QUnit.module("MultigraphView");

    QUnit.test("multigraph view loads without errors", async function (assert) {
        await makeView({
            type: "multigraph",
            resModel: "product.template",
            serverData,
            arch: `
                <multigraph string="Product Analytics">
                    <field name="create_date" interval="month"/>
                    <field name="list_price" type="measure" widget="monetary"/>
                    <field name="standard_price" type="measure" widget="monetary"/>
                    <field name="qty_available" type="measure"/>
                </multigraph>`,
            searchViewArch: `
                <search>
                    <filter name="this_month" string="This Month" 
                            domain="[('create_date','>=', datetime.datetime.now().strftime('%Y-%m-01'))]"/>
                </search>`,
        });

        assert.containsOnce(target, ".o_multigraph_renderer", 
            "should have multigraph renderer");
        assert.containsOnce(target, ".o_multigraph_renderer canvas", 
            "should have canvas element");
        assert.containsNone(target, ".o_error_dialog", 
            "should not have any error dialog");
    });

    QUnit.test("multigraph handles click without resModel error", async function (assert) {
        const mockDoAction = (action) => {
            assert.step(`doAction: ${action.type} on ${action.res_model}`);
        };

        await makeView({
            type: "multigraph",
            resModel: "product.template",
            serverData,
            arch: `<multigraph/>`,
            mockRPC(route, args) {
                if (args.method === "web_read_group") {
                    assert.step("web_read_group");
                }
            },
            config: {
                actionService: {
                    doAction: mockDoAction,
                },
            },
        });

        assert.containsOnce(target, "canvas", "should have chart canvas");
        
        // Click on the chart
        await click(target, ".o_multigraph_renderer canvas");
        
        // Should not have error dialog
        assert.containsNone(target, ".o_error_dialog", 
            "clicking chart should not cause error dialog");
        
        // Verify the RPC call was made
        assert.verifySteps(["web_read_group"]);
    });

    QUnit.test("multigraph model has resModel property", async function (assert) {
        let model;
        
        await makeView({
            type: "multigraph",
            resModel: "product.template",
            serverData,
            arch: `<multigraph/>`,
            mockRPC(route, args) {
                if (args.method === "web_read_group") {
                    // Access the model through the component
                    const component = this;
                    model = component.model;
                }
            },
        });

        assert.ok(model, "should have model");
        assert.strictEqual(model.metaData.resModel, "product.template", 
            "model should have resModel in metaData");
        assert.strictEqual(model.resModel, "product.template", 
            "model should have resModel property directly");
    });

    QUnit.test("multigraph switches between chart types", async function (assert) {
        await makeView({
            type: "multigraph",
            resModel: "product.template",
            serverData,
            arch: `<multigraph/>`,
        });

        // Check initial state
        assert.containsOnce(target, ".o_multigraph_renderer", 
            "should have multigraph renderer");
        
        // Look for chart type buttons (if implemented)
        const chartButtons = target.querySelectorAll(".o_graph_buttons button");
        assert.ok(chartButtons.length > 0, "should have chart type buttons");
    });

    QUnit.test("multigraph respects measure configuration", async function (assert) {
        await makeView({
            type: "multigraph",
            resModel: "product.template",
            serverData,
            arch: `
                <multigraph>
                    <field name="list_price" type="measure" string="Revenue"/>
                    <field name="standard_price" type="measure" string="Cost"/>
                </multigraph>`,
            mockRPC(route, args) {
                if (args.method === "web_read_group") {
                    assert.step("web_read_group");
                    // Verify the measures are requested
                    assert.ok(args.kwargs.fields.includes("list_price"), 
                        "should request list_price field");
                    assert.ok(args.kwargs.fields.includes("standard_price"), 
                        "should request standard_price field");
                }
            },
        });

        assert.verifySteps(["web_read_group"]);
    });
});