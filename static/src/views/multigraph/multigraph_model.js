import { GraphModel } from "@web/views/graph/graph_model"

export class MultigraphModel extends GraphModel {
    setup(params) {
        super.setup(params)
        this.measures = this.metaData.measures || []
        this.axisConfig = this.metaData.axisConfig || {}
        this.resModel = this.metaData.resModel
        this.data = null
    }

    async load(searchParams) {
        // If searchParams doesn't have groupBy but context has graph_groupbys, use it
        if ((!searchParams.groupBy || searchParams.groupBy.length === 0) &&
            searchParams.context && searchParams.context.graph_groupbys) {
            searchParams = {
                ...searchParams,
                groupBy: searchParams.context.graph_groupbys
            }
        }

        return await this._loadData(searchParams)
    }

    async _loadData(searchParams) {
        this.searchParams = searchParams
        let { context, domain, groupBy, orderBy } = searchParams

        // If no groupBy is specified but we have graph_groupbys in context, use that
        if (!groupBy || groupBy.length === 0) {
            if (context.graph_groupbys && context.graph_groupbys.length > 0) {
                groupBy = context.graph_groupbys
            }
        }

        // Keep the original groupBy with intervals for webReadGroup
        const measureFieldNames = this.measures.map(m => m.fieldName)
        const fieldNamesOnly = groupBy.map(gb => {
            if (typeof gb === 'string' && gb.includes(':')) {
                return gb.split(':')[0]
            }
            return gb
        })

        const readGroupFields = [...new Set([...fieldNamesOnly, ...measureFieldNames])]

        const data = await this.orm.webReadGroup(
            this.metaData.resModel,
            domain,
            readGroupFields,
            groupBy,  // Use original groupBy with intervals
            {
                orderby: orderBy.length ? orderBy : false,
                lazy: groupBy.length === 1,
                context,
            }
        )

        this.data = this._processData(data, fieldNamesOnly)
        return this.data
    }

    _processData(data, groupBy) {
        const processedData = {
            datasets: [],
            labels: [],
            domains: [],
        }

        if (!data.groups || !data.groups.length) {
            return processedData
        }

        processedData.labels = data.groups.map(group => {
            // Check if we have a groupBy with interval
            if (this.searchParams.groupBy.length && this.searchParams.groupBy[0]) {
                const groupByField = this.searchParams.groupBy[0]

                // For fields with intervals, Odoo returns the field with interval suffix as key
                if (groupByField.includes(':') && group[groupByField] !== undefined) {
                    // The value is already formatted by Odoo
                    return group[groupByField] || "Undefined"
                }

                // For regular fields (no interval)
                const fieldName = groupBy[0]
                const value = group[fieldName]
                return this._formatGroupByValue(fieldName, value)
            }
            return "Total"
        })
        processedData.domains = data.groups.map(group => group.__domain || [])

        this.measures.forEach((measure, index) => {
            const values = data.groups.map(group => group[measure.fieldName] || 0)

            processedData.datasets.push({
                label: measure.label,
                data: values,
                yAxisID: measure.axis,
                backgroundColor: this._getColor(index, "background"),
                borderColor: this._getColor(index, "border"),
                borderWidth: 2,
                type: "line",
                tension: 0.1,
                fieldName: measure.fieldName,
                widget: measure.widget,
            })
        })

        return processedData
    }

    _getColor(index, type = "background") {
        const colors = [
            { bg: "rgba(31, 119, 180, 0.7)", border: "rgb(31, 119, 180)" },
            { bg: "rgba(255, 127, 14, 0.7)", border: "rgb(255, 127, 14)" },
            { bg: "rgba(44, 160, 44, 0.7)", border: "rgb(44, 160, 44)" },
            { bg: "rgba(214, 39, 40, 0.7)", border: "rgb(214, 39, 40)" },
            { bg: "rgba(148, 103, 189, 0.7)", border: "rgb(148, 103, 189)" },
        ]

        const colorSet = colors[index % colors.length]
        return type === "background" ? colorSet.bg : colorSet.border
    }

    _formatGroupByValue(fieldName, value) {
        const field = this.metaData.fields[fieldName]

        if (!value || value === false) {
            return "Undefined"
        }

        if (field && (field.type === "date" || field.type === "datetime")) {
            const date = new Date(value)
            return date.toLocaleDateString()
        }

        if (Array.isArray(value)) {
            return value[1] || value[0] || "Undefined"
        }

        return "" + value
    }

    getFormattedValue(value, dataset) {
        if (dataset.widget === "monetary") {
            return new Intl.NumberFormat("en-US", {
                style: "currency",
                currency: "USD",
            }).format(value)
        }

        if (Number.isInteger(value)) {
            return value.toLocaleString()
        }

        return value.toFixed(2)
    }

    hasData() {
        return this.data && this.data.datasets && this.data.datasets.length > 0 &&
            this.data.datasets.some(ds => ds.data && ds.data.length > 0)
    }
}