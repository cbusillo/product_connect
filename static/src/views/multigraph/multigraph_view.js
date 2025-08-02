import { registry } from "@web/core/registry"
import { graphView } from "@web/views/graph/graph_view"
import { MultigraphArchParser } from "./multigraph_arch_parser"
import { MultigraphModel } from "./multigraph_model"
import { MultigraphRenderer } from "./multigraph_renderer"
import { MultigraphController } from "./multigraph_controller"

export const multigraphView = {
    ...graphView,
    type: "multigraph",
    display_name: "MultiGraph",
    icon: "fa fa-line-chart",
    multiRecord: true,
    buttonTemplate: "web.MultigraphView.Buttons",
    searchMenuTypes: ["filter", "groupBy", "comparison", "favorite"],
    ArchParser: MultigraphArchParser,
    Model: MultigraphModel,
    Renderer: MultigraphRenderer,
    Controller: MultigraphController,

    props(genericProps, view) {
        // First get the base props from parent graphView
        const baseProps = graphView.props(genericProps, { 
            ...graphView,
            ArchParser: view.ArchParser,
            Model: view.Model,
            Renderer: view.Renderer,
            buttonTemplate: view.buttonTemplate
        })
        
        // Then extend/modify the modelParams for multigraph specifics
        let modelParams = { ...baseProps.modelParams }
        
        if (!genericProps.state) {
            const { arch, fields } = genericProps
            const parser = new view.ArchParser()
            const archInfo = parser.parse(arch, fields)
            
            // Override specific properties for multigraph
            modelParams = {
                ...modelParams,
                measures: archInfo.measures || [],
                axisConfig: archInfo.axisConfig || {},
                mode: "line", // Default to line for multigraph
                title: archInfo.title || "MultiGraph",
            }
        }

        return {
            ...baseProps,
            modelParams,
        }
    },
}

registry.category("views").add("multigraph", multigraphView)