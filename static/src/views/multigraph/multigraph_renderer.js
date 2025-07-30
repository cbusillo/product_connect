import { GraphRenderer } from "@web/views/graph/graph_renderer"
import { loadBundle } from "@web/core/assets"
import { onWillStart, onMounted, onWillUnmount, onWillUpdateProps, useRef } from "@odoo/owl"

export class MultigraphRenderer extends GraphRenderer {
    static template = "web.MultigraphRenderer"
    static props = [
        ...GraphRenderer.props,
        // Ensure all props are explicitly declared with proper types
        "modelParams?",  // Optional prop for model parameters
        "axisConfig?",   // Optional prop for axis configuration
    ]

    setup() {
        this.canvasRef = useRef("canvas")
        this.chart = null
        this._scalesCache = null // Cache for scales configuration
        this._lastDatasetCount = 0 // Track dataset changes

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib")
        })

        onMounted(() => this.renderChart())

        onWillUpdateProps(() => {
            // Re-render chart when props change
            this.renderChart()
        })

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy()
                this.chart = null
            }
        })
    }

    renderChart() {
        // Clean up existing chart
        if (this.chart) {
            try {
                this.chart.destroy()
            } catch (error) {
                console.warn("Error destroying chart:", error)
            }
            this.chart = null
        }

        const model = this.props.model
        if (!this.canvasRef.el || !model.data || !model.hasData()) {
            return
        }

        const config = this.getChartConfig()
        if (config) {
            try {
                // Ensure canvas is ready
                const ctx = this.canvasRef.el.getContext('2d')
                if (!ctx) {
                    console.error("Unable to get 2D context from canvas")
                    return
                }

                this.chart = new Chart(this.canvasRef.el, config)
            } catch (error) {
                console.error("Error creating chart:", error)
                // Ensure chart is null if creation failed
                this.chart = null
            }
        }
    }

    getChartConfig() {
        const model = this.props.model
        const { data } = model

        if (!data || !data.datasets || data.datasets.length === 0) {
            return null
        }


        // noinspection JSValidateTypes - Chart.js config structure
        return {
            type: "line",
            data: {
                labels: data.labels || [],
                datasets: data.datasets || [],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: "top",
                    },
                    tooltip: {
                        mode: "index",
                        intersect: false,
                        callbacks: {
                            label: (context) => {
                                const dataset = context.dataset
                                const value = context.parsed.y
                                const formattedValue = model.getFormattedValue(value, dataset)
                                return `${dataset.label}: ${formattedValue}`
                            },
                        },
                    },
                },
                interaction: {
                    mode: "nearest",
                    axis: "x",
                    intersect: false,
                },
                scales: this._getScalesConfig(),
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        this.onGraphClick(event, elements)
                    }
                },
            },
        }
    }

    _getScalesConfig() {
        const model = this.props.model

        // Check if we can use cached scales
        const currentDatasetCount = model.data?.datasets?.length || 0
        if (this._scalesCache && this._lastDatasetCount === currentDatasetCount) {
            return this._scalesCache
        }

        const scales = {
            x: {
                display: true,
                grid: {
                    display: true,
                    drawOnChartArea: true,
                },
            },
        }

        // Add Y axes based on axis configuration
        if (model.axisConfig) {
            Object.entries(model.axisConfig).forEach(([axisId, config]) => {
                // Get datasets for this axis to calculate appropriate scale
                const datasetsForAxis = model.data.datasets.filter(
                    ds => ds.yAxisID === axisId
                )

                // Calculate min and max values for this axis
                let minValue = Infinity
                let maxValue = -Infinity

                datasetsForAxis.forEach(dataset => {
                    if (dataset.data && dataset.data.length > 0) {
                        const values = dataset.data.filter(v => v !== null && v !== undefined)
                        if (values.length > 0) {
                            const dataMin = Math.min(...values)
                            const dataMax = Math.max(...values)
                            minValue = Math.min(minValue, dataMin)
                            maxValue = Math.max(maxValue, dataMax)
                        }
                    }
                })

                // If no valid data found, use defaults
                if (minValue === Infinity || maxValue === -Infinity) {
                    minValue = 0
                    maxValue = 100
                }


                // For very small ranges, ensure we have some scale
                if (maxValue - minValue < 10) {
                    maxValue = minValue + 10
                }

                // Determine if we should use logarithmic scale
                // Use log scale when max is more than 100x the min (excluding zero)
                const nonZeroMin = minValue > 0 ? minValue : 1
                const useLogScale = maxValue / nonZeroMin > 100

                // Add more aggressive padding (20% below and 20% above)
                const range = maxValue - minValue
                const suggestedMin = useLogScale ? nonZeroMin * 0.8 : Math.max(0, minValue - range * 0.2)
                const suggestedMax = useLogScale ? maxValue * 1.2 : maxValue + range * 0.2

                scales[axisId] = {
                    type: useLogScale ? "logarithmic" : "linear",
                    display: config.display,
                    position: config.position,
                    grid: {
                        drawOnChartArea: axisId === "y",
                    },
                    ticks: {
                        callback: (value) => {
                            if (datasetsForAxis.some(ds => ds.widget === "monetary")) {
                                // Format large monetary values with K/M suffix
                                if (value >= 1000000) {
                                    return `$${(value / 1000000).toFixed(1)}M`
                                } else if (value >= 1000) {
                                    return `$${(value / 1000).toFixed(0)}K`
                                }
                                return new Intl.NumberFormat("en-US", {
                                    style: "currency",
                                    currency: "USD",
                                    minimumFractionDigits: 0,
                                    maximumFractionDigits: 0
                                }).format(value)
                            }

                            // Format large numbers with K/M suffix
                            if (value >= 1000000) {
                                return `${(value / 1000000).toFixed(1)}M`
                            } else if (value >= 1000) {
                                return `${(value / 1000).toFixed(0)}K`
                            }

                            return value.toLocaleString()
                        },
                        // Limit the number of ticks to prevent overcrowding
                        maxTicksLimit: 8,
                    },
                    // Set bounds based on data
                    suggestedMin: suggestedMin,
                    suggestedMax: suggestedMax,
                    // Don't use hard min/max as it can cause issues with Chart.js auto-scaling
                    // For monetary values, always start from 0
                    beginAtZero: datasetsForAxis.some(ds => ds.widget === "monetary") && minValue >= 0
                }
            })
        }

        // Cache the scales configuration
        this._scalesCache = scales
        this._lastDatasetCount = currentDatasetCount

        return scales
    }

    onGraphClick(event, elements) {
        const element = elements[0]
        if (!element) return

        const model = this.props.model
        const { index } = element

        // Validate index bounds
        if (index < 0 || index >= model.data.domains.length) {
            console.warn("Invalid domain index:", index)
            return
        }

        const domain = model.data.domains[index]

        if (domain && Array.isArray(domain) && domain.length > 0) {
            // Guard against undefined env (e.g., in test environments)
            if (this.env && this.env.services && this.env.services.action) {
                // Validate domain structure before executing
                const isValidDomain = domain.every(clause =>
                    Array.isArray(clause) && clause.length === 3 ||
                    typeof clause === 'string' && ['&', '|', '!'].includes(clause)
                )

                if (!isValidDomain) {
                    console.error("Invalid domain structure:", domain)
                    return
                }

                this.env.services.action.doAction({
                    type: "ir.actions.act_window",
                    name: "Details",
                    res_model: model.metaData.resModel,
                    views: [[false, "list"], [false, "form"]],
                    domain,
                    context: model.searchParams.context,
                })
            }
        }
    }
}