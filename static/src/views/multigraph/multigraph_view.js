/** @odoo-module **/

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
        let modelParams
        if (genericProps.state) {
            modelParams = genericProps.state.metaData
        } else {
            const { arch, fields, resModel } = genericProps
            const parser = new view.ArchParser()
            const archInfo = parser.parse(arch, fields)
            modelParams = {
                disableLinking: Boolean(archInfo.disableLinking),
                fields: archInfo.fields,
                groupBy: archInfo.groupBy,
                measures: archInfo.measures,
                axisConfig: archInfo.axisConfig,
                mode: "line",
                order: null,
                resModel: resModel,
                stacked: archInfo.stacked || false,
                title: archInfo.title || "MultiGraph",
            }
        }

        return {
            ...genericProps,
            modelParams,
            Model: view.Model,
            Renderer: view.Renderer,
            buttonTemplate: view.buttonTemplate,
        }
    },
}

registry.category("views").add("multigraph", multigraphView)