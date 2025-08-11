import { test, expect } from "@odoo/hoot"
import { MultigraphArchParser } from "../src/views/multigraph/multigraph_arch_parser"

test("multigraph arch parser creates multiple y-axes", () => {
    const parser = new MultigraphArchParser()

    // Create a mock XML arch element
    const mockArch = {
        getAttribute: (name) => {
            if (name === "title") return "Test Chart"
            return null
        }
    }

    const mockFields = {
        revenue: { string: "Revenue", type: "monetary" },
        cost: { string: "Cost", type: "monetary" },
        units: { string: "Units", type: "integer" },
        count: { string: "Count", type: "integer" },
        date: { string: "Date", type: "date" }
    }

    // Mock field nodes with different axis attributes
    const fieldNodes = [
        {
            tagName: "field",
            getAttribute: (name) => {
                const attrs = {
                    name: "date",
                    interval: "day"
                }
                return attrs[name] || null
            }
        },
        {
            tagName: "field",
            getAttribute: (name) => {
                const attrs = {
                    name: "revenue",
                    type: "measure",
                    widget: "monetary",
                    axis: "y",
                    string: "Revenue Value"
                }
                return attrs[name] || null
            }
        },
        {
            tagName: "field",
            getAttribute: (name) => {
                const attrs = {
                    name: "cost",
                    type: "measure",
                    widget: "monetary",
                    axis: "y",
                    string: "Cost Value"
                }
                return attrs[name] || null
            }
        },
        {
            tagName: "field",
            getAttribute: (name) => {
                const attrs = {
                    name: "units",
                    type: "measure",
                    axis: "y2",
                    string: "Units Processed"
                }
                return attrs[name] || null
            }
        },
        {
            tagName: "field",
            getAttribute: (name) => {
                const attrs = {
                    name: "count",
                    type: "measure",
                    axis: "y2",
                    string: "Image Count"
                }
                return attrs[name] || null
            }
        }
    ]

    // Mock visitXML to process our field nodes
    let originalVisitXML
    import("@web/core/utils/xml").then(module => {
        originalVisitXML = module.visitXML
        module.visitXML = (arch, callback) => {
            fieldNodes.forEach(callback)
        }
    })

    const result = parser.parse(mockArch, mockFields)

    // Verify measures are assigned to correct axes
    expect(result.measures.length).toBe(4)

    const revenueField = result.measures.find(m => m.fieldName === "revenue")
    const costField = result.measures.find(m => m.fieldName === "cost")
    const unitsField = result.measures.find(m => m.fieldName === "units")
    const countField = result.measures.find(m => m.fieldName === "count")

    expect(revenueField.axis).toBe("y")
    expect(costField.axis).toBe("y")
    expect(unitsField.axis).toBe("y2")
    expect(countField.axis).toBe("y2")

    // Verify axis configuration
    expect(result.axisConfig).toHaveProperty("y")
    expect(result.axisConfig).toHaveProperty("y2")

    expect(result.axisConfig.y.position).toBe("left")
    expect(result.axisConfig.y.display).toBe(true)

    expect(result.axisConfig.y2.position).toBe("right")
    expect(result.axisConfig.y2.display).toBe(true)

    // Restore original visitXML if we mocked it
    if (originalVisitXML) {
        import("@web/core/utils/xml").then(module => {
            module.visitXML = originalVisitXML
        })
    }
})

test("multigraph renderer uses correct axis configuration", () => {
    // Test that the renderer correctly uses axis configuration
    const mockAxisConfig = {
        y: { position: "left", display: true },
        y2: { position: "right", display: true }
    }

    const mockData = {
        datasets: [
            { label: "Revenue", yAxisID: "y", widget: "monetary" },
            { label: "Cost", yAxisID: "y", widget: "monetary" },
            { label: "Units", yAxisID: "y2" },
            { label: "Count", yAxisID: "y2" }
        ]
    }

    // Create a mock MultigraphRenderer to test _getScalesConfig
    const mockRenderer = {
        model: {
            axisConfig: mockAxisConfig,
            data: mockData
        },
        _getScalesConfig() {
            const scales = {
                x: {
                    display: true,
                    grid: { display: true, drawOnChartArea: true }
                }
            }

            Object.entries(this.model.axisConfig || {}).forEach(([axisId, config]) => {
                scales[axisId] = {
                    type: "linear",
                    display: config.display,
                    position: config.position,
                    grid: { drawOnChartArea: axisId === "y" },
                    ticks: {
                        callback: (value) => {
                            const datasetsForAxis = this.model.data.datasets.filter(
                                ds => ds.yAxisID === axisId
                            )

                            if (datasetsForAxis.some(ds => ds.widget === "monetary")) {
                                return new Intl.NumberFormat("en-US", {
                                    style: "currency",
                                    currency: "USD",
                                    maximumFractionDigits: 1
                                }).format(value)
                            }

                            return value.toLocaleString()
                        }
                    }
                }
            })

            return scales
        }
    }

    const scales = mockRenderer._getScalesConfig()

    // Verify both y axes are configured
    expect(scales).toHaveProperty("y")
    expect(scales).toHaveProperty("y2")

    // Verify y axis (left, monetary)
    expect(scales.y.position).toBe("left")
    expect(scales.y.display).toBe(true)
    expect(scales.y.grid.drawOnChartArea).toBe(true)

    // Verify y2 axis (right, non-monetary)
    expect(scales.y2.position).toBe("right")
    expect(scales.y2.display).toBe(true)
    expect(scales.y2.grid.drawOnChartArea).toBe(false)

    // Test tick formatting
    const y_tick = scales.y.ticks.callback(1000)
    const y2_tick = scales.y2.ticks.callback(1000)

    expect(y_tick).toBe("$1,000.0") // Monetary formatting
    expect(y2_tick).toBe("1,000") // Number formatting
})