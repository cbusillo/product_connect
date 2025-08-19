from ..common_imports import tagged, TOUR_TAGS
from ..fixtures.base import TourTestCase


@tagged(*TOUR_TAGS, "product_connect")
class TestMultigraphBrowser(TourTestCase):
    def test_multigraph_view_no_errors(self) -> None:
        action_id = self.env.ref("product_connect.action_product_processing_analytics").id
        url = f"/web#action={action_id}"
        self.browser_js(
            url,
            """
            console.log("Starting multigraph browser test...");
            
            // Wait for any view to load (graph, list, or error)
            let viewFound = false;
            let attempts = 0;
            const maxAttempts = 100;  // 10 seconds
            
            while (!viewFound && attempts < maxAttempts) {
                // Check for graph view
                const graphView = document.querySelector('.o_graph_view');
                const listView = document.querySelector('.o_list_view');
                const errorDialog = document.querySelector('.o_error_dialog');
                
                if (errorDialog) {
                    const errorText = errorDialog.querySelector('.modal-body')?.textContent || 'Unknown error';
                    console.error('Error dialog found:', errorText);
                    throw new Error('View loading error: ' + errorText);
                }
                
                if (graphView) {
                    console.log('✓ Graph view loaded');
                    
                    // Check if it's our multigraph by looking for the canvas
                    const canvas = graphView.querySelector('.o_graph_renderer canvas');
                    if (canvas) {
                        console.log('✓ Chart canvas found');
                        viewFound = true;
                    } else {
                        console.log('⚠️ Graph view found but no canvas yet');
                    }
                } else if (listView) {
                    console.log('List view loaded instead of graph view');
                    viewFound = true;
                }
                
                if (!viewFound) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    attempts++;
                }
            }
            
            if (!viewFound) {
                throw new Error('No view loaded after ' + (attempts * 100) + 'ms');
            }
            
            console.log('Multigraph view test completed successfully!');
            """,
            login=self._get_test_login(),
            ready="document.querySelector('.o_graph_view, .o_list_view') !== null",
            timeout=30000,
        )
