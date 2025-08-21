/** @odoo-module */
import { test, expect } from "@odoo/hoot"
import { multigraphView } from "@product_connect/views/multigraph/multigraph_view"
import { MultigraphModel } from "@product_connect/views/multigraph/multigraph_model"
import { MultigraphRenderer } from "@product_connect/views/multigraph/multigraph_renderer"

test("multigraph view props function returns valid props structure", () => {
    const mockGenericProps = {
        arch: '<graph/>',
        fields: {
            name: { string: "Name", type: "char" },
            value: { string: "Value", type: "float" }
        }
    }

    const mockView = {
        type: "multigraph"
    }

    const props = multigraphView.props(mockGenericProps, mockView)

    // Validate required props exist and have correct types
    expect(props).not.toBe(undefined)
    expect(typeof props.className).toBe("string")
    expect(typeof props.buttonTemplate).toBe("string")
    expect(props.Model).toBe(MultigraphModel)
    expect(props.Renderer).toBe(MultigraphRenderer)
    expect(typeof props.modelParams).toBe("object")
})

test("multigraph view props handles undefined gracefully", () => {
    const mockGenericProps = {
        arch: '<graph/>',
        fields: {}
    }

    const mockView = {
        type: "multigraph"
    }

    // Should not throw an error even with minimal props
    const props = multigraphView.props(mockGenericProps, mockView)

    expect(props).not.toBe(undefined)
    expect(props.className).toBe("")  // Default empty string
    expect(props.buttonTemplate).toBe("")  // Default empty string
    expect(props.modelParams).not.toBe(undefined)
})
