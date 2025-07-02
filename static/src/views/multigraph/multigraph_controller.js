/** @odoo-module **/

import { GraphController } from "@web/views/graph/graph_controller";
import { useService } from "@web/core/utils/hooks";

export class MultigraphController extends GraphController {
    static template = "web.GraphView";
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    get measureOptions() {
        return this.model.measures.map(measure => ({
            value: measure.fieldName,
            label: measure.label,
            isActive: true,
        }));
    }

    onModeClick(mode) {
        this.model.metaData.mode = mode;
        this.render(true);
    }
}