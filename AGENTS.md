You are an expert Odoo core developer.

Code must be compatible with Odoo 18 and Owl.JS 2.0. We are using Python 3.12+ No comments or docstrings in code. All
code should instead be descriptive. Both function and variable names should be full words and understandable.

Code should be beautiful and easy to read and maintain. Use existing codebase patterns. Avoid the use of attrs when
possible
in Python. We want everything to be type-checked with mypy and PyCharm. All functions return and parameters should be
type hinted as accurately as possible. When type hinting Odoo objects, use the "magic types" available from the Odoo
Plugin for Jetbrains. For example, "odoo.model.product_template" or "odoo.values.product_template"

pytest is installed in your environment, and you can use it to run tests. You can also use odoo-bin --test-enable to run
odoo tests.

---

## Running the tests

Codex, follow the exact sequence below to validate this project:

1. Make sure PostgresSQL is running locally on port 5432 and that the role **odoo** owns the database **odoo-test**.  
   If it is not online, start it and wait until
   ```bash
   service postgresql start
   until pg_isready -q; do sleep 1; done
   ```
2. Export the environment variables Odoo expects:
   ```bash
   export PGHOST=localhost
   export PGPORT=5432
   export ODOO_DATABASE=odoo-test
   export ODOO_ADDONS_PATH=/workspace/odoo/addons,/workspace/enterprise,/workspace/odoo-opw/addons
   ```
3. Run the fast unit layer:
   ```bash
   pytest -q -s --odoo-database=$ODOO_DATABASE
   ```
4. Run the full integration suite:
   ```bash
   odoo-bin --test-enable -d $ODOO_DATABASE --stop-after-init
   ```

Both commands must exit with code **0**.

### Odoo type‑hint patterns

Use the JetBrains magic types to keep static analysis clean:

* "odoo.model.res_partner" – recordset
* "odoo.values.res_partner" – dictionary of values for create/write
* "Iterable[odoo.model.account_move]" – collection of recordsets