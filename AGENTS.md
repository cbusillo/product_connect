You are an expert Odoo core developer.

Code must be compatible with Odoo 18 and Owl.JS 2.0. We are using Python 3.12+ No comments or docstrings in code. All
code should instead be descriptive. Both function and variable names should be full words and understandable.

Code should be beautiful and easy to read and maintain. Use existing codebase patterns. Avoid the use of attrs when
possible in Python. We want everything to be type-checkable with mypy and PyCharm. All functions return and parameters
should be type hinted as accurately as possible. Avoid the use of Any when typing. When type hinting Odoo objects, use
the "magic types" available from
the Odoo Plugin for Jetbrains. For example, "odoo.model.product_template" or "odoo.values.product_template". Use
relative imports when possible. Use absolute imports only when necessary.

pytest is installed in your environment, and you can use it to run tests.

When writing tests, use patch.object instead of patch so we can use our pattern of relative imports.

***

## Setting up the environment

Use the environment script to load Odoo variables and activate the virtual environment:

```bash
. /etc/profile.d/odoo_env.sh
```

## Running the tests

- Run pytest:
   ```bash
   cd /workspace 
   pytest --odoo-log-level=warn --odoo-http 
   ```
    - Add --last-failed to run only the tests that failed in the last run
    - Add `/odoo` to the end of the pytest command to run the full test suite before committing
    - Examine the PYTEST_ADDOPTS to adjust options. Reasonable defaults are already set.

- Run tests with odoo-bin:
    ```bash
    /odoo/odoo-bin -d $ODOO_DATABASE -i base,product_connect --addons-path=$ODOO_ADDONS_PATH --stop-after-init --test-enable --log-level=warn  
    ```
    - Use `--test-tags[-][tag][/module][:class][.method]` to run specific tests

- Front-end (tour) tests:
  Odoo tours are headless‐Chrome integration tests that live under the `/web` module.  
  Codex must run them just like unit tests and exit **0** only when they pass:

    ```bash
    /odoo/odoo-bin \
    -d "$ODOO_DATABASE" \
    --addons-path="$ODOO_ADDONS_PATH" \
    --init base,product_connect \
    --stop-after-init \
    --test-enable \
    --test-tags="/web_tour,/web" \
    --log-level=warn
    ```

- All commands in this section *and* in **Programmatic checks** must exit with code 0.

### Programmatic checks

The following static‑analysis and formatting commands **must** succeed (exit code) before Codex considers the task
complete:

```bash
# format only hand‑written code
black --line-length 130 --extend-exclude 'services/shopify/gql|graphql/schema' .

# type‑check only hand‑written code (skip pyi stubs and generated folders)
mypy --config-file=mypy.ini --follow-imports=silent --exclude '(\.pyi$|services/shopify/gql/|graphql/schema/)' .
```

> **Generated folders** (`services/shopify/gql/*`, `graphql/schema/*`) are produced by Ariadne Codegen.  
> Codex **must not** modify or format these files; treat them as read‑only artifacts.

### Odoo type‑hint patterns

Use the JetBrains magic types to keep static analysis clean:

* "odoo.model.res_partner" – recordset or collection of recordsets
* "odoo.values.res_partner" – dictionary of values for create/write

## Repository layout

- Addon and project root is **/workspace/product_connect**
- Ignore these paths when searching for implementation targets:
    - /workspace/product_connect/services/shopify/gql/* # generated from Ariadne Codegen
    - /workspace/product_connect/graphql/schema/* # generated from Ariadne Codegen

## Environment layout

- Odoo base files are in **/odoo**
- Odoo addons are in **/odoo/addons**
- Odoo Enterprise addons are in **/enterprise**

### Running Odoo server for manual testing

After loading the environment, you can launch the server with your addon:

```bash
/odoo/odoo-bin \
  --database="$ODOO_DATABASE" \
  --addons-path="$ODOO_ADDONS_PATH" \
  --update=product_connect \
  --log-level=warn
```

Use `--log-handler=odoo.tools.convert:DEBUG` to see XML debug logs.
Use `--log-handler=odoo.addons.product_connect:DEBUG` to see product_connect debug logs.
Use `--dev=all` when you need live template reloads.
