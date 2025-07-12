"""Integration tests for multigraph view functionality using HttpCase."""

from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install", "product_connect_integration")
class TestMultigraphIntegration(HttpCase):
    """Test multigraph view with real browser automation"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Create test data
        cls.test_products = cls.env["product.template"].create(
            [
                {
                    "name": f"Test Product {i}",
                    "list_price": 100 * i,
                    "standard_price": 60 * i,
                    "type": "consu",
                }
                for i in range(1, 5)
            ]
        )

    def test_multigraph_chart_click_no_error(self) -> None:
        """Test that clicking multigraph chart doesn't throw resModel error"""
        self.authenticate("admin", "admin")

        # Use browser_js to run JavaScript in a real browser
        result = self.browser_js(
            "/web",
            """
            console.log("Starting multigraph test...");
            
            // Navigate to Product Processing Analytics
            await odoo.__DEBUG__.services.action.doAction(
                'product_connect.action_product_processing_analytics'
            );
            
            // Wait for multigraph to load (lazy assets)
            await new Promise((resolve, reject) => {
                let attempts = 0;
                const checkInterval = setInterval(() => {
                    attempts++;
                    const canvas = document.querySelector('.o_multigraph_renderer canvas');
                    if (canvas) {
                        clearInterval(checkInterval);
                        console.log("✓ Multigraph loaded");
                        resolve();
                    } else if (attempts > 100) { // 10 seconds
                        clearInterval(checkInterval);
                        reject(new Error("Multigraph failed to load"));
                    }
                }, 100);
            });
            
            // Click on the chart
            const canvas = document.querySelector('.o_multigraph_renderer canvas');
            const rect = canvas.getBoundingClientRect();
            const clickEvent = new MouseEvent('click', {
                view: window,
                bubbles: true,
                cancelable: true,
                clientX: rect.left + rect.width / 2,
                clientY: rect.top + rect.height / 2
            });
            canvas.dispatchEvent(clickEvent);
            console.log("✓ Clicked on chart");
            
            // Wait a moment for any error to appear
            await new Promise(resolve => setTimeout(resolve, 1000));
            
            // Check for error dialog
            const errorDialog = document.querySelector('.o_error_dialog');
            if (errorDialog) {
                const errorText = errorDialog.textContent;
                console.error("✗ Error dialog found:", errorText);
                return { success: false, error: errorText };
            }
            
            console.log("✓ No error dialog - test passed!");
            return { success: true };
            """,
            login="admin",
            timeout=30,
        )

        self.assertTrue(result["success"], f"Chart click caused error: {result.get('error', 'Unknown')}")

    def test_multigraph_view_switching(self) -> None:
        """Test switching between multigraph and other view types"""
        self.authenticate("admin", "admin")

        result = self.browser_js(
            "/web",
            """
            // Navigate to Product Processing Analytics
            await odoo.__DEBUG__.services.action.doAction(
                'product_connect.action_product_processing_analytics'
            );
            
            // Wait for initial view
            await new Promise(r => setTimeout(r, 2000));
            
            // Check if we can switch to list view
            const listButton = document.querySelector('button.o_switch_view.o_list');
            if (listButton) {
                listButton.click();
                await new Promise(r => setTimeout(r, 1000));
                
                // Verify list view loaded
                const listView = document.querySelector('.o_list_view');
                return { success: !!listView };
            }
            
            return { success: false, error: "Could not find view switcher" };
            """,
            login="admin",
            timeout=30,
        )

        self.assertTrue(result["success"], "View switching failed")
