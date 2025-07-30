import { registry } from "@web/core/registry"
import { graphView } from "@web/views/graph/graph_view"
import { MultigraphArchParser } from "./multigraph_arch_parser"
import { MultigraphModel } from "./multigraph_model"
import { MultigraphRenderer } from "./multigraph_renderer"
// Controller removed - using default GraphController to avoid props issues

// Define multigraph as a specialized graph view
export const multigraphView = {
    ...graphView,
    type: "multigraph",  // Required for view type registration
    ArchParser: MultigraphArchParser,
    Model: MultigraphModel,
    Renderer: MultigraphRenderer,
    // Use default GraphController to avoid props validation issues
    props(genericProps, view) {
        // Get standard props from parent - use the actual view object passed
        const baseProps = graphView.props(genericProps, view)

        // Create a clean props object to avoid validation issues
        // Remove 'class' from baseProps to avoid prop validation errors
        const { class: _, ...cleanBaseProps } = baseProps
        const props = {
            // Copy all base props ensuring no undefined values and correct types
            ...cleanBaseProps,
            // Ensure critical props are never undefined - use className not class
            className: baseProps.className || baseProps.class || "",    // String required
            buttonTemplate: baseProps.buttonTemplate || "",  // String required
            // Always use our custom components (Function type required)
            Model: MultigraphModel,
            Renderer: MultigraphRenderer,
        }

        // Only process custom measures if we have valid arch data
        const { arch, fields } = genericProps
        if (arch && fields && !genericProps.state) {
            try {
                const parser = new MultigraphArchParser()
                const archInfo = parser.parse(arch, fields)

                // Pass custom configuration through modelParams
                if (archInfo && archInfo.measures && Array.isArray(archInfo.measures) && archInfo.measures.length > 0) {
                    props.modelParams = {
                        ...baseProps.modelParams,
                        measures: archInfo.measures,
                        axisConfig: archInfo.axisConfig || {}
                    }
                }
            } catch (error) {
                // Ensure modelParams exists even if parsing fails
                props.modelParams = baseProps.modelParams || {}
            }
        } else {
            // Preserve existing modelParams
            props.modelParams = baseProps.modelParams || {}
        }

        return props
    }
}

// Register multigraph as a custom view type
registry.category("views").add("multigraph", multigraphView)