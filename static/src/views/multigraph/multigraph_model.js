import { GraphModel } from "@web/views/graph/graph_model"
import { computeReportMeasures } from "@web/views/utils"

/**
 * @typedef {Object} CustomMeasure
 * @property {string} fieldName - The field name for the measure
 * @property {string} [axis="y"] - The axis assignment ("y" or "y2")
 * @property {string} [widget] - Widget type for formatting
 * @property {string} [label] - Display label
 * @property {string} [string] - String representation
 * @property {string} [type] - Field type
 *
 * @typedef {Object} ProcessedData
 * @property {Object[]} datasets - Chart datasets
 * @property {string[]} labels - Chart labels
 * @property {Array[]} domains - Domain arrays for each data point
 *
 * @typedef {Object} SearchParams
 * @property {Object} context - Search context
 * @property {Array} domain - Search domain
 * @property {string[]} groupBy - Group by fields
 * @property {string[]} orderBy - Order by fields
 */

// Constants for better maintainability
const DEFAULT_AXIS = "y"
const CHART_COLORS = [
    { bg: "rgba(31, 119, 180, 0.7)", border: "rgb(31, 119, 180)" },
    { bg: "rgba(255, 127, 14, 0.7)", border: "rgb(255, 127, 14)" },
    { bg: "rgba(44, 160, 44, 0.7)", border: "rgb(44, 160, 44)" },
    { bg: "rgba(214, 39, 40, 0.7)", border: "rgb(214, 39, 40)" },
    { bg: "rgba(148, 103, 189, 0.7)", border: "rgb(148, 103, 189)" },
]

export class MultigraphModel extends GraphModel {
    /**
     * Override _buildMetaData to enhance metadata with custom measure support
     * @param {Object} [params] - Optional parameters to merge
     * @returns {Object} Built metadata object with custom enhancements
     */
    _buildMetaData(params) {
        // Get the base metadata
        const metaData = super._buildMetaData(params)

        // Add our axis configuration
        if (this.axisConfig) {
            metaData.axisConfig = this.axisConfig
        }

        // Ensure all fields have the 'string' property for proper sorting
        if (metaData.fields) {
            Object.keys(metaData.fields).forEach(fieldName => {
                const field = metaData.fields[fieldName]
                if (field && !field.string) {
                    field.string = field.label || field.name || fieldName
                }
            })
        }

        // If we have custom measures and need to override computeReportMeasures
        if (this.customMeasures && this.customMeasures.length > 0) {
            // Override computeReportMeasures to return our filtered measures
            const originalComputeReportMeasures = metaData.computeReportMeasures
            metaData.computeReportMeasures = () => {
                try {
                    return this._computeCustomReportMeasures()
                } catch (error) {
                    // Fallback to parent's implementation if our custom one fails
                    console.warn("Custom report measures failed, falling back to default:", error)
                    return originalComputeReportMeasures ? originalComputeReportMeasures() : {}
                }
            }
        }

        return metaData
    }

    /**
     * Setup the multigraph model with custom parameters
     * @param {Object} params - Setup parameters including measures and axis config
     */
    setup(params) {

        // Store our custom configuration separately
        this.customMeasureConfig = {}
        this.axisConfig = params.axisConfig || {}
        this.customMeasures = null // Initialize to prevent issues during metadata access

        // Initialize data to prevent template errors
        this.data = {
            datasets: [],
            labels: [],
            domains: []
        }

        // If we have custom measures, convert to parent's expected format
        if (params.measures && Array.isArray(params.measures) && params.measures.length > 0) {
            // Store the original custom measures AFTER parent setup is complete
            const customMeasures = params.measures

            // Store the custom metadata for each measure
            customMeasures.forEach(measure => {
                this.customMeasureConfig[measure.fieldName] = {
                    axis: measure.axis || DEFAULT_AXIS,
                    widget: measure.widget,
                    label: measure.label || measure.string,
                    type: measure.type
                }
            })

            // Pass just the field names to parent
            params.measures = customMeasures.map(m => m.fieldName)
            params.measureFields = params.measures

        }

        // Let parent handle the standard setup FIRST
        super.setup(params)

        // Only set customMeasures AFTER parent setup is complete
        if (params.measures && this.customMeasureConfig) {
            this.customMeasures = Object.keys(this.customMeasureConfig).map(fieldName => ({
                fieldName,
                ...this.customMeasureConfig[fieldName]
            }))
        }

    }

    /**
     * Compute report measures with our custom properties
     * @private
     * @returns {Object} Report measures with custom configuration
     */
    _computeCustomReportMeasures() {
        // Only compute measures for the fields we explicitly want
        const measureFieldNames = this.customMeasures ? this.customMeasures.map(m => m.fieldName) : []

        // Ensure we have valid fields to work with
        if (!this.metaData || !this.metaData.fields) {
            return {}
        }

        // Filter fields to only include our specified measures
        const filteredFields = {}
        const filteredFieldAttrs = {}

        measureFieldNames.forEach(fieldName => {
            if (this.metaData.fields[fieldName]) {
                const field = this.metaData.fields[fieldName]
                // Ensure field has ALL required properties for computeReportMeasures
                filteredFields[fieldName] = {
                    name: fieldName,
                    string: field.string || field.label || fieldName,
                    type: field.type || 'float',
                    aggregator: field.aggregator || 'sum',
                    sortable: field.sortable !== undefined ? field.sortable : true,
                    store: field.store !== undefined ? field.store : true,
                    searchable: field.searchable !== undefined ? field.searchable : true,
                    aggregatable: field.aggregatable !== undefined ? field.aggregatable : true,
                    ...field  // Include any other properties from the original field
                }
            }
            if (this.metaData.fieldAttrs && this.metaData.fieldAttrs[fieldName]) {
                filteredFieldAttrs[fieldName] = this.metaData.fieldAttrs[fieldName]
            }
        })

        // Make sure we have fields before calling computeReportMeasures
        if (Object.keys(filteredFields).length === 0) {
            return {}
        }

        // Use the same utility function that GraphModel uses, but only with our measures
        const reportMeasures = computeReportMeasures(
            filteredFields,
            filteredFieldAttrs,
            measureFieldNames
        )


        // Enhance with our custom configuration
        if (this.customMeasureConfig) {
            Object.keys(reportMeasures).forEach(fieldName => {
                if (this.customMeasureConfig[fieldName]) {
                    // Add our custom properties
                    // noinspection JSCheckFunctionSignatures - customMeasureConfig properties are valid for assignment
                    Object.assign(reportMeasures[fieldName], /** @type {Object} */ (this.customMeasureConfig[fieldName]))
                }
            })
        }

        return reportMeasures
    }


    /**
     * Load data for the multigraph
     * @param {SearchParams} searchParams - Search parameters
     * @returns {Promise<void>}
     */
    async load(searchParams) {

        // If we have custom measures, ensure they are the only ones loaded
        if (this.customMeasures && this.customMeasures.length > 0) {
            // Force the model to only use our custom measures
            this.metaData.measures = this.customMeasures.map(m => m.fieldName)
            this.metaData.activeMeasure = null // No single active measure
        }

        // Check if we have multiple measures
        const measures = this._computeCustomReportMeasures()
        const measureKeys = Object.keys(measures)

        if (measureKeys.length > 1) {
            // Force multi-measure mode
            this.metaData.mode = "line"

            // Load data for all measures
            await this._loadMultiAxisData(searchParams)
        } else {
            // Single measure, use parent behavior
            await super.load(searchParams)
        }
    }

    /**
     * Load data for multiple axes
     * @private
     * @param {SearchParams} searchParams - Search parameters
     * @returns {Promise<ProcessedData>}
     */
    async _loadMultiAxisData(searchParams) {
        try {
            this.searchParams = searchParams
            let { context, domain, groupBy, orderBy } = searchParams

            // Validate search params
            if (!this.metaData || !this.metaData.resModel) {
                console.error("Error loading multi-axis data: Model metadata not initialized")
                this.data = {
                    datasets: [],
                    labels: [],
                    domains: []
                }
                return this.data
            }

            // If no groupBy is specified but we have graph_groupbys in context, use that
            if (!groupBy || groupBy.length === 0) {
                if (context.graph_groupbys && context.graph_groupbys.length > 0) {
                    groupBy = context.graph_groupbys
                } else {
                    // No default groupby - should be specified in view context
                    groupBy = []
                }
            }

            // Get all measure fields
            const measures = this._computeCustomReportMeasures()
            const measureFieldNames = Object.keys(measures)

            // Extract field names from groupBy (removing intervals)
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

            this.data = this._processMultiAxisData(data, groupBy, measures)

            // Ensure we have the dataPoints property that the renderer expects
            if (!this.dataPoints) {
                this.dataPoints = this.data
            }

            return this.data
        } catch (error) {
            // Log error and return empty data structure
            // Re-throwing after logging and cleanup for proper error handling
            console.error("Error loading multi-axis data:", error)
            this.data = {
                datasets: [],
                labels: [],
                domains: []
            }
            this.dataPoints = this.data
            throw error // Re-throw for parent handling
        }
    }

    /**
     * Process multi-axis data into chart format
     * @private
     * @param {Object} data - Raw data from read_group
     * @param {string[]} groupBy - Group by fields
     * @param {Object} measures - Measure definitions
     * @returns {ProcessedData} Processed chart data
     */
    _processMultiAxisData(data, groupBy, measures) {
        const processedData = {
            datasets: [],
            labels: [],
            domains: [],
        }

        if (!data.groups || !data.groups.length) {
            return processedData
        }

        // Process labels from groups
        processedData.labels = data.groups.map(group => {
            if (groupBy.length && groupBy[0]) {
                const groupByField = groupBy[0]

                // For fields with intervals, Odoo returns the field with interval suffix as key
                if (groupByField.includes(':') && group[groupByField] !== undefined) {
                    return group[groupByField] || "Undefined"
                }

                // For regular fields (no interval)
                const fieldName = groupByField.split(':')[0]
                const value = group[fieldName]
                return this._formatGroupByValue(fieldName, value)
            }
            return "Total"
        })

        processedData.domains = data.groups.map(group => group.__domain || [])

        // Create datasets for each measure
        let index = 0
        for (const [fieldName, measure] of Object.entries(measures)) {
            // Skip the __count measure if it exists
            if (fieldName === "__count") {
                continue
            }

            const values = data.groups.map(group => group[fieldName] || 0)

            processedData.datasets.push({
                label: measure.label || measure.string,
                data: values,
                yAxisID: measure.axis || DEFAULT_AXIS,
                backgroundColor: this._getColor(index, "background"),
                borderColor: this._getColor(index, "border"),
                borderWidth: 2,
                type: "line",
                tension: 0.1,
                fieldName: fieldName,
                widget: measure.widget,
            })
            index++
        }

        return processedData
    }

    /**
     * Get color for chart element
     * @private
     * @param {number} index - Color index
     * @param {string} [type="background"] - Color type ("background" or "border")
     * @returns {string} Color value
     */
    _getColor(index, type = "background") {
        const colorSet = CHART_COLORS[index % CHART_COLORS.length]
        return type === "background" ? colorSet.bg : colorSet.border
    }

    /**
     * Format a group by value for display
     * @private
     * @param {string} fieldName - Field name
     * @param {*} value - Value to format
     * @returns {string} Formatted value
     */
    _formatGroupByValue(fieldName, value) {
        const field = this.metaData.fields[fieldName]

        if (value === null || value === undefined || value === false) {
            return "Undefined"
        }

        if (field && (field.type === "date" || field.type === "datetime")) {
            try {
                const date = new Date(value)
                // Check for valid date
                if (isNaN(date.getTime())) {
                    console.warn(`Invalid date value for field ${fieldName}:`, value)
                    return "Invalid Date"
                }
                return date.toLocaleDateString()
            } catch (error) {
                console.error(`Error formatting date for field ${fieldName}:`, error)
                return "Invalid Date"
            }
        }

        if (Array.isArray(value)) {
            // Many2one fields return [id, display_name]
            return value[1] || value[0] || "Undefined"
        }

        // Ensure string conversion - use template literal to avoid namespace issues
        return `${value}`
    }

    /**
     * Format a value for display
     * @param {number|string|null} value - The value to format
     * @param {Object} dataset - Dataset configuration
     * @returns {string} Formatted value
     */
    getFormattedValue(value, dataset) {
        // Validate input
        if (value === null || value === undefined) {
            return "0"
        }

        // Ensure value is a number
        const numValue = Number(value)
        if (isNaN(numValue)) {
            console.warn("Invalid numeric value:", value)
            return "0"
        }

        if (dataset.widget === "monetary") {
            try {
                return new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                }).format(numValue)
            } catch (error) {
                console.error("Error formatting monetary value:", error)
                return `$${numValue.toFixed(2)}`
            }
        }

        if (Number.isInteger(numValue)) {
            return numValue.toLocaleString()
        }

        return numValue.toFixed(2)
    }

    /**
     * Check if the model has data to display
     * @returns {boolean} True if data exists
     */
    hasData() {
        return this.data && this.data.datasets && this.data.datasets.length > 0 &&
            this.data.datasets.some(ds => ds.data && ds.data.length > 0)
    }

    /**
     * Override to prevent switching away from multi-measure mode
     * @param {Object} params - Parameters to update
     * @returns {Promise<void>}
     */
    async updateMetaData(params) {
        const measures = this._computeCustomReportMeasures()
        const measureKeys = Object.keys(measures)

        if (measureKeys.length > 1 && params.measure) {
            // Ignore measure changes in multi-measure mode
            const { measure, ...otherParams } = params
            return super.updateMetaData(otherParams)
        } else {
            return super.updateMetaData(params)
        }
    }
}