from odoo import models


class PublisherWarrantyContract(models.AbstractModel):
    _name = "publisher_warranty.contract"
    _description = "Publisher Warranty Contract"

    def update_notification(self, cron_mode: bool = True) -> bool:
        return True
