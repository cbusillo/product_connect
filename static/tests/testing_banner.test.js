import { TestingBanner } from "@product_connect/js/utils/testing_banner"
import { describe, expect, test } from "@odoo/hoot"
import { browser } from "@web/core/browser/browser"
import { mountWithCleanup, patchWithCleanup } from "@web/../tests/web_test_helpers"

describe("testing_banner", () => {
    test("shows banner in dev", async () => {
        patchWithCleanup(browser.location, { hostname: "dev.odoo.com" })
        await mountWithCleanup(TestingBanner)
        expect(".testing-banner.environment-dev").toHaveCount(1)
        expect(".testing-banner .banner-content span:contains(dev.odoo.com)").toHaveCount(1)
    })

    test("hides banner in production", async () => {
        patchWithCleanup(browser.location, { hostname: "odoo.outboardpartswarehouse.com" })
        await mountWithCleanup(TestingBanner)
        expect(".testing-banner").toHaveCount(0)
    })
})
