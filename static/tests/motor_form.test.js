import { describe, test, expect } from "@odoo/hoot";
import { click, fill } from "@odoo/hoot-dom";
import { animationFrame } from "@odoo/hoot-mock";
import { defineModels, fields, models, mountView, onRpc } from "@web/../tests/web_test_helpers";
import { defineMailModels } from "@mail/../tests/mail_test_helpers";

class Motor extends models.Model {
    _name = "motor";

    manufacturer = fields.Many2one({ relation: "product.manufacturer" });
    stroke = fields.Many2one({ relation: "motor.stroke" });
    configuration = fields.Many2one({ relation: "motor.configuration" });
    horsepower = fields.Float();
    serial_number = fields.Char();
    model = fields.Char();
    // noinspection JSUnusedGlobalSymbols
    location = fields.Char();
    // noinspection JSUnusedGlobalSymbols
    year = fields.Char();

    _records = [
        {
            id: 1,
            manufacturer: 1,
            stroke: 1,
            configuration: 1,
            horsepower: 100,
            location: "A1",
            serial_number: "SN001",
            year: "2023",
            model: "V8",
        },
    ];
}

class ProductManufacturer extends models.Model {
    _name = "product.manufacturer";

    name = fields.Char();

    // noinspection JSUnusedGlobalSymbols
    _records = [
        { id: 1, name: "TestMaker" },
        { id: 2, name: "OtherMaker" },
    ];
}

class MotorStroke extends models.Model {
    _name = "motor.stroke";

    name = fields.Char();
    code = fields.Char();

    // noinspection JSUnusedGlobalSymbols
    _records = [
        { id: 1, name: "Four", code: "4" },
        { id: 2, name: "Two", code: "2" },
    ];
}

class MotorConfiguration extends models.Model {
    _name = "motor.configuration";

    name = fields.Char();
    code = fields.Char();


    // noinspection JSUnusedGlobalSymbols
    _records = [
        { id: 1, name: "I4", code: "4" },
        { id: 2, name: "V8", code: "8" },
    ];
}

describe("Motor Form Integration Tests", () => {
    test("should display motor form with all fields", async () => {
        defineMailModels();
        defineModels([Motor, ProductManufacturer, MotorStroke, MotorConfiguration]);

        await mountView({
            type: "form",
            resModel: "motor",
            resId: 1,
            arch: `
                <form>
                    <sheet>
                        <group>
                            <field name="manufacturer"/>
                            <field name="stroke"/>
                            <field name="configuration"/>
                            <field name="horsepower"/>
                            <field name="location"/>
                            <field name="serial_number"/>
                            <field name="year"/>
                            <field name="model"/>
                        </group>
                    </sheet>
                </form>
            `,
        });

        expect(".o_field_widget[name=manufacturer] input").toHaveValue("TestMaker");
        expect(".o_field_widget[name=horsepower] input").toHaveValue("100");
        expect(".o_field_widget[name=location] input").toHaveValue("A1");
        expect(".o_field_widget[name=serial_number] input").toHaveValue("SN001");
    });

    test("should update motor fields", async () => {
        defineMailModels();
        defineModels([Motor, ProductManufacturer, MotorStroke, MotorConfiguration]);

        let saveCount = 0;
        onRpc("web_save", () => {
            saveCount++;
            return true;
        });

        await mountView({
            type: "form",
            resModel: "motor",
            resId: 1,
            arch: `
                <form>
                    <sheet>
                        <group>
                            <field name="horsepower"/>
                            <field name="location"/>
                        </group>
                    </sheet>
                </form>
            `,
        });

        await click(".o_field_widget[name=horsepower] input");
        await fill(".o_field_widget[name=horsepower] input", "150");

        await click(".o_field_widget[name=location] input");
        await fill(".o_field_widget[name=location] input", "B2");

        await click(".o_form_button_save");
        await animationFrame();

        expect(saveCount).toBe(1);
    });

    test("should validate unique location constraint", async () => {
        defineMailModels();
        defineModels([Motor, ProductManufacturer, MotorStroke, MotorConfiguration]);

        Motor._records.push({
            id: 2,
            manufacturer: 1,
            stroke: 1,
            configuration: 1,
            horsepower: 90,
            location: "A2",
            serial_number: "SN002",
            year: "2023",
            model: "V6",
        });

        await mountView({
            type: "form",
            resModel: "motor",
            resId: 2,
            arch: `
                <form>
                    <sheet>
                        <group>
                            <field name="location"/>
                        </group>
                    </sheet>
                </form>
            `,
        });

        await click(".o_field_widget[name=location] input");
        await fill(".o_field_widget[name=location] input", "A1");

        onRpc("web_save", () => {
            throw new Error("The location must be unique");
        });

        await click(".o_form_button_save");
        await animationFrame();

        expect(".o_notification_bar.bg-danger").toHaveCount(1);
    });
});