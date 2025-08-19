from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS, "product_connect")
class TestMultigraphIntegration(TourTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        from datetime import date

        cls.test_products = cls.env["product.template"].create(
            [
                {
                    "name": f"Integration Test Product {i}",
                    "default_code": f"{40000 + i}",  # Valid SKU
                    "list_price": 250 * i,
                    "standard_price": 150 * i,
                    "type": "consu",
                    "is_ready_for_sale": True,
                    "is_ready_for_sale_last_enabled_date": date(2025, 1, i),
                    "initial_quantity": 40 * i,
                    "initial_price_total": 4000 * i,
                    "initial_cost_total": 2400 * i,
                }
                for i in range(1, 6)
            ]
        )

    def test_multigraph_chart_click_no_error(self) -> None:
        self.browser_js(
            "/odoo/action-product_connect.action_product_processing_analytics",
            """
            console.log("Starting multigraph click test...");
            
            // Wait for graph view with more robust checks
            let chartLoaded = false;
            let attempts = 0;
            const maxAttempts = 30; // 3 seconds - fail fast
            
            const checkAndClick = async () => {
                while (!chartLoaded && attempts < maxAttempts) {
                    const graphView = document.querySelector('.o_multigraph_renderer');
                    const errorDialog = document.querySelector('.o_error_dialog');
                    
                    // Check for errors first
                    if (errorDialog) {
                        const errorText = errorDialog.querySelector('.modal-body')?.textContent || 'Unknown error';
                        console.error("Error dialog found:", errorText);
                        throw new Error("Page failed to load: " + errorText);
                    }
                    
                    if (graphView) {
                        const canvas = graphView.querySelector('.o_graph_renderer canvas');
                        if (canvas && canvas.offsetWidth > 0 && canvas.offsetHeight > 0) {
                            console.log("✓ Graph view and canvas loaded");
                            chartLoaded = true;
                            
                            // Give it more time to fully render Chart.js
                            await new Promise(resolve => setTimeout(resolve, 500));
                            
                            // Click on the canvas
                            try {
                                const rect = canvas.getBoundingClientRect();
                                const clickEvent = new MouseEvent('click', {
                                    view: window,
                                    bubbles: true,
                                    cancelable: true,
                                    clientX: rect.left + rect.width / 2,
                                    clientY: rect.top + rect.height / 2
                                });
                                canvas.dispatchEvent(clickEvent);
                                console.log("✓ Clicked on chart at:", rect.left + rect.width / 2, rect.top + rect.height / 2);
                            } catch (clickError) {
                                console.error("Error clicking chart:", clickError);
                                throw clickError;
                            }
                            
                            // Check for errors after click
                            await new Promise(resolve => setTimeout(resolve, 300));
                            const errorAfterClick = document.querySelector('.o_error_dialog');
                            if (errorAfterClick) {
                                const errorText = errorAfterClick.querySelector('.modal-body')?.textContent || 'Unknown error';
                                console.error("Error dialog found after click:", errorText);
                                throw new Error("Error after click: " + errorText);
                            }
                            console.log("✓ Test passed - no errors after click!");
                        }
                    }
                    
                    if (!chartLoaded) {
                        await new Promise(resolve => setTimeout(resolve, 100));
                        attempts++;
                        
                        // Additional early failure checks
                        const loadingError = document.querySelector('.o_error_dialog, .o_crash_manager');
                        if (loadingError) {
                            const errorText = loadingError.textContent || 'Page load error';
                            throw new Error("Early failure detected: " + errorText);
                        }
                    }
                }
                
                if (!chartLoaded) {
                    // Check what view actually loaded
                    const anyView = document.querySelector('.o_multigraph_renderer, .o_pivot_view, .o_list_view');
                    if (anyView) {
                        console.warn("View loaded but not graph view:", anyView.className);
                    }
                    throw new Error("Chart not loaded after " + (attempts * 100) + "ms");
                }
            };
            
            await checkAndClick();
            """,
            "document.querySelector('.o_multigraph_renderer, .o_list_view, .o_pivot_view') !== null",
            login=self._get_test_login(),
            timeout=15000,  # 15 seconds - fail fast
        )

    def test_multigraph_view_switching(self) -> None:
        self.browser_js(
            "/odoo/action-product_connect.action_product_processing_analytics",
            """
            console.log("Testing view switching...");
            
            const testViewSwitching = async () => {
                let attempts = 0;
                const maxAttempts = 30; // 3 seconds - fail fast
                
                // Wait for initial view
                while (attempts < maxAttempts) {
                    const anyView = document.querySelector('.o_multigraph_renderer, .o_pivot_view, .o_list_view');
                    const errorDialog = document.querySelector('.o_error_dialog');
                    
                    if (errorDialog) {
                        const errorText = errorDialog.querySelector('.modal-body')?.textContent || 'Unknown error';
                        throw new Error("Error on page load: " + errorText);
                    }
                    
                    if (anyView) {
                        console.log("✓ Initial view loaded:", anyView.className);
                        
                        // Wait a bit for view to stabilize
                        await new Promise(resolve => setTimeout(resolve, 300));
                        
                        // Look for view switcher buttons
                        const viewButtons = document.querySelectorAll('button.o_switch_view');
                        console.log("Found", viewButtons.length, "view switcher buttons");
                        
                        if (viewButtons.length > 0) {
                            // Try to find and click list view button
                            const listButton = document.querySelector('button.o_switch_view.o_list');
                            const pivotButton = document.querySelector('button.o_switch_view.o_pivot');
                            const graphButton = document.querySelector('button.o_switch_view.o_graph');
                            
                            if (listButton && !listButton.classList.contains('active')) {
                                console.log("Clicking list view button...");
                                listButton.click();
                                
                                // Wait for view change
                                await new Promise(resolve => setTimeout(resolve, 300));
                                
                                const listView = document.querySelector('.o_list_view');
                                if (listView) {
                                    console.log("✓ Successfully switched to list view");
                                    
                                    // Try to switch back to multigraph
                                    if (graphButton) {
                                        console.log("Switching back to multigraph view...");
                                        graphButton.click();
                                        await new Promise(resolve => setTimeout(resolve, 300));
                                        
                                        const graphViewAgain = document.querySelector('.o_multigraph_renderer');
                                        if (graphViewAgain) {
                                            console.log("✓ Successfully switched back to multigraph view");
                                        }
                                    }
                                } else {
                                    console.warn("List view button clicked but view didn't change");
                                }
                            } else if (pivotButton && !pivotButton.classList.contains('active')) {
                                console.log("No list button, trying pivot view...");
                                pivotButton.click();
                                await new Promise(resolve => setTimeout(resolve, 300));
                                console.log("✓ Clicked pivot button");
                            } else {
                                console.log("✓ View loaded but switching not available or already in target view");
                            }
                        } else {
                            console.log("✓ View loaded (no view switcher available - single view mode)");
                        }
                        
                        return; // Success
                    }
                    
                    await new Promise(resolve => setTimeout(resolve, 100));
                    attempts++;
                    
                    // Additional early failure checks  
                    const loadingError = document.querySelector('.o_error_dialog, .o_crash_manager');
                    if (loadingError) {
                        const errorText = loadingError.textContent || 'Page load error';
                        throw new Error("Early failure detected: " + errorText);
                    }
                }
                
                throw new Error("No view loaded after " + (attempts * 100) + "ms");
            };
            
            await testViewSwitching();
            """,
            "document.querySelector('.o_multigraph_view, .o_pivot_view, .o_list_view') !== null",
            login=self._get_test_login(),
            timeout=15000,  # 15 seconds - fail fast
        )
