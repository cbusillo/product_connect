"""Factory classes for creating test data."""

import random
import string
from datetime import datetime, timedelta
from decimal import Decimal


class ProductFactory:
    """Factory for creating test products."""
    
    @staticmethod
    def create(env, **kwargs):
        """Create a product with defaults."""
        defaults = {
            "name": f"Test Product {datetime.now().timestamp()}",
            "default_code": ProductFactory._generate_sku(),
            "type": "consu",
            "list_price": 100.0,
            "standard_price": 50.0,
            "sale_ok": True,
            "purchase_ok": True,
            "categ_id": env.ref("product.product_category_all").id,
            "uom_id": env.ref("uom.product_uom_unit").id,
            "uom_po_id": env.ref("uom.product_uom_unit").id,
            "invoice_policy": "order",
            "website_description": "Test product description",
            "shopify_sync": False,  # Disable sync by default in tests
        }
        defaults.update(kwargs)
        return env["product.template"].create(defaults)
    
    @staticmethod
    def _generate_sku():
        """Generate valid SKU matching OPW pattern."""
        return f"{random.randint(10000000, 99999999)}"
    
    @staticmethod
    def create_batch(env, count=5, **kwargs):
        """Create multiple products."""
        return [ProductFactory.create(env, **kwargs) for _ in range(count)]
    
    @staticmethod
    def create_with_variants(env, variant_count=3, **kwargs):
        """Create product with variants."""
        product = ProductFactory.create(env, **kwargs)
        
        # Create color attribute
        color_attr = env["product.attribute"].create({
            "name": "Test Color",
            "create_variant": "always",
        })
        
        # Create attribute values
        colors = ["Red", "Blue", "Green", "Yellow", "Black"][:variant_count]
        color_values = []
        for color in colors:
            color_values.append(env["product.attribute.value"].create({
                "name": color,
                "attribute_id": color_attr.id,
            }))
        
        # Create attribute line
        env["product.template.attribute.line"].create({
            "product_tmpl_id": product.id,
            "attribute_id": color_attr.id,
            "value_ids": [(6, 0, [v.id for v in color_values])],
        })
        
        return product


class PartnerFactory:
    """Factory for creating test partners."""
    
    @staticmethod
    def create(env, **kwargs):
        """Create a partner with defaults."""
        timestamp = datetime.now().timestamp()
        defaults = {
            "name": f"Test Partner {timestamp}",
            "email": f"test_{timestamp}@example.com",
            "is_company": False,
            "customer_rank": 1,
            "supplier_rank": 0,
            "street": "123 Test Street",
            "city": "Test City",
            "zip": "12345",
            "country_id": env.ref("base.us").id,
            "phone": f"+1{random.randint(2000000000, 9999999999)}",
        }
        defaults.update(kwargs)
        return env["res.partner"].create(defaults)
    
    @staticmethod
    def create_company(env, **kwargs):
        """Create a company partner."""
        kwargs["is_company"] = True
        if "name" not in kwargs:
            kwargs["name"] = f"Test Company {datetime.now().timestamp()}"
        return PartnerFactory.create(env, **kwargs)
    
    @staticmethod
    def create_with_contacts(env, contact_count=2, **kwargs):
        """Create company with child contacts."""
        company = PartnerFactory.create_company(env, **kwargs)
        
        contacts = []
        for i in range(contact_count):
            contact = PartnerFactory.create(
                env,
                parent_id=company.id,
                name=f"Contact {i+1}",
                type="contact",
            )
            contacts.append(contact)
        
        return company, contacts


class MotorFactory:
    """Factory for creating test motors."""
    
    @staticmethod
    def create(env, **kwargs):
        """Create a motor product."""
        defaults = {
            "name": f"Test Motor {datetime.now().timestamp()}",
            "default_code": MotorFactory._generate_motor_sku(),
            "type": "product",
            "list_price": 2500.0,
            "standard_price": 1500.0,
            "weight": 150.0,
            "volume": 0.5,
            "categ_id": env.ref("product.product_category_all").id,
            # Motor-specific fields
            "motor_hp": random.choice([25, 40, 60, 75, 90, 115, 150]),
            "motor_year": random.randint(2015, 2024),
            "motor_model": f"Model-{random.choice(['X', 'Y', 'Z'])}{random.randint(100, 999)}",
            "motor_serial": MotorFactory._generate_serial(),
        }
        defaults.update(kwargs)
        
        # Ensure it's created as a motor product
        if "is_motor" in env["product.template"]._fields:
            defaults["is_motor"] = True
        
        return env["product.template"].create(defaults)
    
    @staticmethod
    def _generate_motor_sku():
        """Generate motor-specific SKU."""
        prefix = random.choice(["MTR", "ENG", "OBM"])
        return f"{prefix}{random.randint(100000, 999999)}"
    
    @staticmethod
    def _generate_serial():
        """Generate motor serial number."""
        letters = ''.join(random.choices(string.ascii_uppercase, k=3))
        numbers = ''.join(random.choices(string.digits, k=7))
        return f"{letters}{numbers}"


class ShopifyProductFactory:
    """Factory for creating Shopify-synced products."""
    
    @staticmethod
    def create(env, **kwargs):
        """Create a product with Shopify metadata."""
        defaults = {
            "shopify_sync": True,
            "shopify_product_id": str(random.randint(1000000000, 9999999999)),
            "shopify_variant_id": str(random.randint(1000000000, 9999999999)),
            "shopify_inventory_item_id": str(random.randint(1000000000, 9999999999)),
            "shopify_handle": f"test-product-{random.randint(1000, 9999)}",
            "shopify_tags": "test,automated",
            "shopify_vendor": "Test Vendor",
            "shopify_product_type": "Test Type",
            "shopify_last_sync": datetime.now(),
        }
        
        # Merge with product defaults
        product_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("shopify_")}
        product = ProductFactory.create(env, **product_kwargs)
        
        # Add Shopify fields
        shopify_fields = {k: v for k, v in defaults.items() if k.startswith("shopify_")}
        shopify_fields.update({k: v for k, v in kwargs.items() if k.startswith("shopify_")})
        
        product.write(shopify_fields)
        return product


class SaleOrderFactory:
    """Factory for creating test sale orders."""
    
    @staticmethod
    def create(env, **kwargs):
        """Create a sale order with defaults."""
        # Ensure we have a partner
        partner = kwargs.get("partner_id")
        if not partner:
            if isinstance(kwargs.get("partner_id"), int):
                partner = env["res.partner"].browse(kwargs["partner_id"])
            else:
                partner = PartnerFactory.create(env)
                kwargs["partner_id"] = partner.id
        elif not isinstance(partner, int):
            kwargs["partner_id"] = partner.id
        
        defaults = {
            "partner_id": kwargs["partner_id"],
            "date_order": datetime.now(),
            "validity_date": datetime.now() + timedelta(days=30),
            "pricelist_id": env["product.pricelist"].search([], limit=1).id,
            "payment_term_id": env.ref("account.account_payment_term_immediate").id,
            "user_id": env.user.id,
            "team_id": env["crm.team"].search([], limit=1).id,
        }
        defaults.update(kwargs)
        
        # Remove order_line from defaults to handle separately
        order_lines = defaults.pop("order_line", [])
        
        order = env["sale.order"].create(defaults)
        
        # Add order lines if not provided
        if not order_lines:
            order_lines = SaleOrderFactory._create_default_lines(env, order)
        
        for line_vals in order_lines:
            if isinstance(line_vals, dict):
                line_vals["order_id"] = order.id
                env["sale.order.line"].create(line_vals)
        
        return order
    
    @staticmethod
    def _create_default_lines(env, order):
        """Create default order lines."""
        products = ProductFactory.create_batch(env, count=2)
        lines = []
        
        for product in products:
            lines.append({
                "order_id": order.id,
                "product_id": product.product_variant_id.id,
                "product_uom_qty": random.randint(1, 10),
                "price_unit": product.list_price,
            })
        
        return lines
    
    @staticmethod
    def create_with_shopify_metadata(env, **kwargs):
        """Create order with Shopify sync data."""
        defaults = {
            "shopify_order_id": str(random.randint(1000000000, 9999999999)),
            "shopify_order_number": f"#{random.randint(1000, 9999)}",
            "shopify_checkout_id": str(random.randint(1000000000, 9999999999)),
            "shopify_financial_status": "paid",
            "shopify_fulfillment_status": "unfulfilled",
            "shopify_tags": "test,automated",
            "shopify_last_sync": datetime.now(),
        }
        defaults.update(kwargs)
        
        return SaleOrderFactory.create(env, **defaults)