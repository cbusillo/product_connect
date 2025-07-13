/** @odoo-module **/

import { GraphRenderer } from "@web/views/graph/graph_renderer"
import { loadBundle } from "@web/core/assets"
import { onWillStart, onMounted, onWillUnmount, useRef } from "@odoo/owl"

export class MultigraphRenderer extends GraphRenderer {
    static template = "web.GraphRenderer"
    static props = {
        ...GraphRenderer.props
    }

    setup() {
        super.setup()
        this.canvasRef = useRef("canvas")
        this.chart = null

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib")
        })

        onMounted(() => this.renderChart())

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy()
            }
        })
    }

    renderChart() {
        if (this.chart) {
            this.chart.destroy()
        }

        if (this.canvasRef.el && this.model.data) {
            const config = this.getChartConfig()
            this.chart = new Chart(this.canvasRef.el, config)
        }
    }

    getChartConfig() {
        const { data } = this.model

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
                                const formattedValue = this.model.getFormattedValue(value, dataset)
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
        const scales = {
            x: {
                display: true,
                grid: {
                    display: true,
                    drawOnChartArea: true,
                },
            },
        }

        Object.entries(this.model.axisConfig).forEach(([axisId, config]) => {
            scales[axisId] = {
                type: "linear",
                display: config.display,
                position: config.position,
                grid: {
                    drawOnChartArea: axisId === "y",
                },
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
                    },
                },
            }
        })

        return scales
    }

    onGraphClick(event, elements) {
        const element = elements[0]
        if (!element) return

        const { index } = element
        const domain = this.model.data.domains[index]

        if (domain && domain.length) {
            this.env.services.action.doAction({
                type: "ir.actions.act_window",
                name: "Details",
                res_model: this.model.resModel,
                views: [[false, "list"], [false, "form"]],
                domain,
                context: this.model.searchParams.context,
            })
        }
    }

    // noinspection JSUnusedGlobalSymbols - Owl lifecycle method
    onWillUpdateProps(nextProps) {
        // Handle prop updates
        if (this.chart && this.props.model.data !== nextProps.model.data) {
            this.renderChart()
        }
    }
}