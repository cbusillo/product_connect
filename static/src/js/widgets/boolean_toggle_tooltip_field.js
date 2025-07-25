import { registry } from '@web/core/registry'
import { BooleanToggleField, booleanToggleField } from '@web/views/fields/boolean_toggle/boolean_toggle_field'
import { CheckBox } from '@web/core/checkbox/checkbox'
import { useService } from '@web/core/utils/hooks'

export class BooleanToggleTooltipField extends BooleanToggleField {
    static template = "product_connect.BooleanToggleTooltipField"
    static components = { CheckBox }

    setup() {
        super.setup()
        this.notification = useService('notification')
    }

    onDisabledClick(ev) {
        const recordData = this.props.record?.data || {}
        const techResult = recordData.tech_result

        if (this.props.readonly && this.props.name === 'is_scrap' && !techResult) {
            // Prevent default click behavior and stop propagation
            if (ev) {
                ev.preventDefault()
                ev.stopPropagation()
            }
            this.notification.add('Tech result required to mark as scrap', {
                type: 'warning',
                sticky: false,
            })
        }
    }
}

export const booleanToggleTooltipField = {
    ...booleanToggleField,
    component: BooleanToggleTooltipField,
}

registry.category('fields').add('boolean_toggle_tooltip', booleanToggleTooltipField)