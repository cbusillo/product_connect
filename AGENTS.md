You are an expert Odoo core developer.

Code must be compatible with Odoo 18 and Owl.JS 2.0. We are using Python 3.12+ No comments or docstrings in code. All
code should instead be descriptive. Both function and variable names should be full words and understandable.

Code should be beautiful and easy to read and maintain. Use existing codebase patterns. Avoid the use of attrs when
possible
in Python. We want everything to be type-checked with mypy and PyCharm. All functions return and parameters should be
type hinted as accurately as possible. When type hinting Odoo objects, use the "magic types" available from the Odoo
Plugin for Jetbrains. For example, "odoo.model.product_template" or "odoo.values.product_template"

pytest is installed in your environment, and you can use it to run tests.

***

## Running the tests

Codex, follow the exact sequence below to validate this project:

1. Export the environment variables Odoo expects:
    ```bash
    export ODOO_DATABASE=odoo-test
    export ODOO_ADDONS_PATH=/odoo/addons,/enterprise,/workspace
    export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
    export PYTEST_ADDOPTS='--cov=/odoo --cov=/workspace --cov-report=term-missing -q -s -o python_files=test_*.py --odoo-addons-path=/odoo/addons,/enterprise,/workspace'
    ```
2. Run the fast unit layer:
    ```bash
    cd /workspace
    pytest --odoo-log-level=info
    ```
3. Run the full integration suite:
    ```bash
    /odoo/odoo-bin -d $ODOO_DATABASE -i base,product_connect,disable_odoo_onlne --addons-path=$ODOO_ADDONS_PATH --stop-after-init --test-enable --log-level=info 
    ```

Both commands must exit with code **0**.

### Odoo type‑hint patterns

Use the JetBrains magic types to keep static analysis clean:

* "odoo.model.res_partner" – recordset or colleection of recordsets
* "odoo.values.res_partner" – dictionary of values for create/write
