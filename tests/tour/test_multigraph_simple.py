from ..common_imports import tagged, date, TOUR_TAGS
from ..fixtures.base import TourTestCase
from ..fixtures.factories import ProductFactory


@tagged(*TOUR_TAGS, "product_connect")
class TestMultigraphSimple(TourTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        cls.test_products = [
            ProductFactory.create(
                cls.env,
                name=f"Ready Product {i}",
                default_code=f"{20000 + i}",  # Valid SKU
                list_price=150 * i,
                standard_price=90 * i,
                is_ready_for_sale=True,
                is_ready_for_sale_last_enabled_date=date(2025, 1, i),
                initial_quantity=20 * i,
                initial_price_total=2000 * i,
                initial_cost_total=1200 * i,
            )
            for i in range(1, 6)
        ]

    def test_action_loads(self) -> None:
        action = self.env.ref("product_connect.action_product_processing_analytics")
        self.assertTrue(action, "Action should exist")
        self.assertEqual(action.res_model, "product.template")
        self.assertIn("graph", action.view_mode)
        url = f"/odoo/action-{action.id}"
        self.browser_js(
            url,
            """
            console.log("Page loaded, waiting for views...");
            
            // Wait for view to be rendered with timeout
            let attempts = 0;
            const maxAttempts = 50; // 5 seconds
            let viewFound = false;
            
            const checkForViews = () => {
                // Check for any error dialogs first
                const errorDialog = document.querySelector('.o_error_dialog');
                if (errorDialog) {
                    const errorText = errorDialog.querySelector('.modal-body')?.textContent || 'Unknown error';
                    throw new Error('Error dialog found: ' + errorText);
                }
                
                // Check for any of the expected views
                const graphRenderer = document.querySelector('.o_graph_renderer');
                const listView = document.querySelector('.o_list_view');
                const pivotView = document.querySelector('.o_pivot_view');
                
                if (graphRenderer || listView || pivotView) {
                    viewFound = true;
                    console.log("Found view:", graphRenderer ? "graph" : listView ? "list" : "pivot");
                    return true;
                }
                return false;
            };
            
            // Initial check
            if (!checkForViews()) {
                // Wait and retry
                const interval = setInterval(() => {
                    attempts++;
                    if (checkForViews() || attempts >= maxAttempts) {
                        clearInterval(interval);
                        if (!viewFound) {
                            throw new Error('No views loaded after ' + (attempts * 100) + 'ms');
                        } else {
                            console.log("Test completed successfully");
                        }
                    }
                }, 100);
            } else {
                console.log("Test completed successfully");
            }
            """,
            ready="document.querySelector('.o_action_manager') !== null",
            login=self._get_test_login(),
            timeout=15000,  # 15 seconds should be enough
        )

    def test_direct_graph_view(self) -> None:
        [
            ProductFactory.create(
                self.env,
                name=f"Test Product {i}",
                default_code=f"{1000 + i}",
                list_price=100 + i * 10,
                is_ready_for_sale=True,
                is_ready_for_sale_last_enabled_date="2025-01-01",
                initial_quantity=10,
                initial_price_total=1000,
                initial_cost_total=500,
            )
            for i in range(3)
        ]
        action_id = self.env.ref("product_connect.action_product_processing_analytics").id
        self.browser_js(
            f"/odoo/action-{action_id}",
            """
            console.log("Testing direct navigation to multigraph view...");
            
            // Wait for any view to appear
            let attempts = 0;
            const maxAttempts = 100; // 10 seconds
            
            const checkView = () => {
                const errorDialog = document.querySelector('.o_error_dialog');
                if (errorDialog) {
                    const errorText = errorDialog.querySelector('.modal-body')?.textContent || 'Unknown error';
                    throw new Error('Error dialog: ' + errorText);
                }
                
                const view = document.querySelector('.o_graph_renderer, .o_list_view, .o_pivot_view');
                if (view) {
                    console.log("View loaded successfully:", view.className);
                    return true;
                }
                return false;
            };
            
            if (!checkView()) {
                const interval = setInterval(() => {
                    attempts++;
                    if (checkView() || attempts >= maxAttempts) {
                        clearInterval(interval);
                        if (attempts >= maxAttempts) {
                            throw new Error('View did not load within 10 seconds');
                        }
                    }
                }, 100);
            }
            """,
            ready="document.querySelector('.o_action_manager') !== null",
            login=self._get_test_login(),
            timeout=20000,
        )
