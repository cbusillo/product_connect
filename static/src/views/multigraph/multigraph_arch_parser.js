import { visitXML } from "@web/core/utils/xml"
import { GraphArchParser } from "@web/views/graph/graph_arch_parser"

// Constants
const DEFAULT_AXIS = "y"
const SECONDARY_AXIS = "y1"
const NON_MONETARY_FIELDS = ["initial_quantity", "image_count"]

export class MultigraphArchParser extends GraphArchParser {
    parse(arch, fields) {
        // Validate inputs
        if (!arch || !fields) {
            console.warn("MultigraphArchParser: Missing arch or fields")
            return super.parse(arch, fields)
        }

        // First call parent to get standard graph parsing
        const result = super.parse(arch, fields)

        // Extract all measure fields from the arch
        const measures = []
        const measureFields = []
        const warnings = []

        visitXML(arch, (node) => {
            if (node.tagName === "field" && node.getAttribute("type") === "measure") {
                const fieldName = node.getAttribute("name")

                if (!fieldName) {
                    warnings.push("Field element missing 'name' attribute")
                    return
                }

                const field = fields[fieldName]

                if (field) {
                    // Validate field is aggregatable
                    if (field.aggregatable === false) {
                        warnings.push(`Field '${fieldName}' is not aggregatable and may not work properly as a measure`)
                    }

                    const widget = node.getAttribute("widget") || (field.type === "monetary" ? "monetary" : null)
                    const label = node.getAttribute("string") || field.string || fieldName

                    // Determine axis based on field type/widget or explicit attribute
                    let axis = node.getAttribute("axis") || DEFAULT_AXIS
                    // Put non-monetary measures on the right axis
                    if (widget !== "monetary" && NON_MONETARY_FIELDS.includes(fieldName)) {
                        axis = SECONDARY_AXIS
                    }

                    measures.push({
                        fieldName,
                        label,
                        string: label,  // Ensure we have 'string' property
                        axis,
                        widget,
                        type: field.type
                    })
                    measureFields.push(fieldName)
                } else {
                    warnings.push(`Field '${fieldName}' not found in model fields`)
                }
            }
        })

        // Log warnings if any
        if (warnings.length > 0) {
            console.warn("MultigraphArchParser warnings:", warnings)
        }

        // Override result with multi-measure configuration if we found measures
        if (measures.length > 0) {
            result.measures = measures  // Array of measure objects with metadata
            result.measureFields = measureFields  // Array of field names
            result.activeMeasure = "" // No single active measure
            result.axisConfig = {
                [DEFAULT_AXIS]: { position: "left", display: true },
                [SECONDARY_AXIS]: { position: "right", display: true }
            }
        }

        return result
    }
}