import { MotorTestWidget } from "@product_connect/widgets/motor_test_widget"
import { describe, expect, test } from "@odoo/hoot"
import { mockService, mountWithCleanup, patchWithCleanup } from "@web/../tests/web_test_helpers"

async function createWidget() {
    mockService("notification", { add() {} })
    mockService("orm", { searchRead: async () => [] })
    patchWithCleanup(MotorTestWidget.prototype, { loadMotorTests: async () => {} })
    const record = {
        data: {
            tests: { records: [] },
            stroke: [1],
            manufacturer: [1],
            configuration: [1],
            parts: { records: [] },
        },
    }
    return mountWithCleanup(MotorTestWidget, { props: { id: 1, name: "tests", record, readonly: false } })
}

describe("motor_test_widget", () => {
    test("evaluates selection condition", async () => {
        const widget = await createWidget()
        widget.conditionsById = { 1: { id: 1, condition_value: "Yes", conditional_operator: "=" } }
        expect(widget.evaluateCondition("Yes", "selection", { id: 1 })).toBe(true)
        expect(widget.evaluateCondition("No", "selection", { id: 1 })).toBe(false)
    })

    test("evaluates numeric condition", async () => {
        const widget = await createWidget()
        widget.conditionsById = { 1: { id: 1, condition_value: "10", conditional_operator: ">" } }
        expect(widget.evaluateCondition("20", "numeric", { id: 1 })).toBe(true)
        expect(widget.evaluateCondition("5", "numeric", { id: 1 })).toBe(false)
    })

    test("evaluates text condition case insensitive", async () => {
        const widget = await createWidget()
        widget.conditionsById = { 1: { id: 1, condition_value: "abc", conditional_operator: "=" } }
        expect(widget.evaluateCondition("ABC", "text", { id: 1 })).toBe(true)
    })
})
