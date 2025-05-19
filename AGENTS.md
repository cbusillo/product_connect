You are an expert Odoo core developer.

Code must be compatible with Odoo 18 and Owl.JS 2.0. We are using Python 3.12+ No comments or docstrings in code. All
code should instead be descriptive. Both function and variable names should be full words and understandable.

Code should be beautiful and easy to read and maintain. Use existing codebase patterns. Avoid the use of attrs when
possible in Python. We want everything to be type-checkable with mypy and PyCharm. All functions return and parameters
should be type hinted as accurately as possible. When type hinting Odoo objects, use the "magic types" available from
the Odoo Plugin for Jetbrains. For example, "odoo.model.product_template" or "odoo.values.product_template". Use
relative imports when possible. Use absolute imports only when necessary.

pytest is installed in your environment, and you can use it to run tests.

***

## Setting up the environment

Use the environment script to load Odoo variables and activate the virtual environment:

```bash
. /etc/profile.d/odoo_env.sh
```

## Running the tests

- Fast unit layer:
   ```bash
   cd /workspace
   pytest --odoo-log-level=warn
   ```

For iterative local runs you can use: pytest --lf -q

- Full integration suite:
    ```bash
    /odoo/odoo-bin -d $ODOO_DATABASE -i base,product_connect --addons-path=$ODOO_ADDONS_PATH --stop-after-init --test-enable --log-level=warn 
    ```

- Both commands must exit with code **0**.

### Odoo type‑hint patterns

Use the JetBrains magic types to keep static analysis clean:

* "odoo.model.res_partner" – recordset or collection of recordsets
* "odoo.values.res_partner" – dictionary of values for create/write

## Repository layout

- Addon and project root is **/workspace**
- Ignore these paths when searching for implementation targets:
    - /workspace/product_connect/services/shopify/gql/* # generated from Ariadne Codegen
    - /workspace/product_connect/graphql/schema/* # generated from Ariadne Codegen

## Environment layout

- Odoo base files are in **/odoo**
- Odoo addons are in **/odoo/addons**
- Odoo Enterprise files are in **/enterprise**

## Pytest environment variables and test strategies

Two different test groups live in this repository, and you can switch between them with the **PYTEST_ADDOPTS**
environment variable.

### 1. Fast addon‑only test run

Set PYTEST_ADDOPTS so coverage is collected only on this addon and then run pytest from the addons root:

```bash
export PYTEST_ADDOPTS="--cov=/workspace/product_connect \
--cov-report=term-missing \
--quiet \
--capture=no \
--numprocesses=auto \
--dist=loadfile \
--odoo-addons-path=$ODOO_ADDONS_PATH \
-o python_files=test_*.py"
cd /workspace
pytest --odoo-log-level=warn
```

This measures test coverage exclusively for **product_connect** while still executing every Odoo core test that happens
to be imported by your suite. The command must finish with exit code **0**.

### 2. Core‑inclusive test run

Before submitting code run the full odoo test suite, keep the same PYTEST_ADDOPTS but add an extra
`--cov=/odoo` entry:

```bash
export PYTEST_ADDOPTS="--cov=/odoo \
--cov=/workspace/product_connect \
--cov-report=term-missing \
--quiet \
--capture=no \
--numprocesses=auto \
--dist=loadfile \
--odoo-addons-path=$ODOO_ADDONS_PATH \
-o python_files=test_*.py"
cd /workspace
pytest --odoo-log-level=warn
```

Both coverage targets now appear in the report, and the command must also exit **0**.

### 3. Full integration test suite through odoo‑bin

When you need the server‑level integration tests run by Odoo itself, launch:

```bash
/odoo/odoo-bin \
  --database="$ODOO_DATABASE" \
  --init=base,product_connect \
  --addons-path="$ODOO_ADDONS_PATH" \
  --stop-after-init \
  --test-enable \
  --log-level=warn
```

If you only care about this addon’s integration tests, you can limit the scope with `--test-tags=product_connect`. This
step must also exit **0**.

All flags are written in their long form, so you can adjust them easily when new needs arise.

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
