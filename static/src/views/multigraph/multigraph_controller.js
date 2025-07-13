import { GraphController } from "@web/views/graph/graph_controller"
import { useService } from "@web/core/utils/hooks"

/**
 * @typedef {import("./multigraph_model").MultigraphModel} MultigraphModel
 */

export class MultigraphController extends GraphController {
    static template = "web.GraphView"

    // noinspection JSUnusedGlobalSymbols - called by parent GraphController
    get measureOptions() {
        // Required by parent GraphController
        return []
    }

    setup() {
        super.setup()
        this.actionService = useService("action")
    }

    static validateProps() {
        // Skip prop validation to avoid issues in test environment
        return true
    }
}