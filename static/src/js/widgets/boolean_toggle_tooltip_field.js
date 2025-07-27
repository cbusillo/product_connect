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

    onChange(value) {
        const recordData = this.props.record?.data || {}
        const techResult = recordData.tech_result

        // Check if trying to mark as scrap without tech_result
        if (value && this.props.name === 'is_scrap' && !techResult) {
            this.notification.add('Tech result required to mark as scrap', {
                type: 'warning',
                sticky: false,
            })
            // Don't update the value
            return
        }

        // Otherwise, update normally
        this.props.record.update({ [this.props.name]: value })
    }

    onDisabledClick(ev) {
        const recordData = this.props.record?.data || {}
        const techResult = recordData.tech_result

        // Only show notification if readonly, is_scrap field, and no tech_result
        if (this.props.readonly && this.props.name === 'is_scrap' && !techResult) {
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