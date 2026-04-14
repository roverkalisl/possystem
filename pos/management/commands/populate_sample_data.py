from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from pos.models import (
    Category,
    Customer,
    GLMaster,
    GRN,
    GRNItem,
    Item,
    PurchaseOrder,
    PurchaseOrderItem,
    Sale,
    SaleItem,
    SalesReturn,
    StockTransaction,
    Supplier,
)


class Command(BaseCommand):
    help = "Populate the database with sample POS data."

    def handle(self, *args, **options):
        try:
            self.stdout.write("Creating sample data...")
            user = self.get_sample_user()
            gl_accounts = self.create_gl_accounts()
            categories = self.create_categories()
            suppliers = self.create_suppliers()
            customers = self.create_customers(gl_accounts)
            items = self.create_items(categories, suppliers, gl_accounts, user)
            purchase_order = self.create_purchase_order(suppliers, user, items)
            grn = self.create_grn(purchase_order, user)
            self.create_sale_and_return(customers, user, items)
            self.stdout.write(self.style.SUCCESS("✅ Sample data has been populated successfully."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"❌ Error populating sample data: {exc}"))
            raise

    def get_sample_user(self):
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username="sampleuser",
            defaults={
                "email": "sample@example.com",
                "is_staff": True,
            },
        )
        if created:
            user.set_password("sample123")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created sample user: sampleuser (password: sample123)"))
        return user

    def create_gl_accounts(self):
        gl_data = [
            {"gl_code": "1000", "gl_name": "Cash", "gl_type": "asset"},
            {"gl_code": "1100", "gl_name": "Accounts Receivable", "gl_type": "asset"},
            {"gl_code": "2000", "gl_name": "Accounts Payable", "gl_type": "liability"},
            {"gl_code": "3000", "gl_name": "Sales Revenue", "gl_type": "income"},
            {"gl_code": "4000", "gl_name": "Cost of Goods Sold", "gl_type": "expense"},
            {"gl_code": "5000", "gl_name": "Inventory", "gl_type": "asset"},
        ]
        gl_accounts = {}
        for row in gl_data:
            account, _ = GLMaster.objects.update_or_create(
                gl_code=row["gl_code"],
                defaults={
                    "gl_name": row["gl_name"],
                    "gl_type": row["gl_type"],
                    "is_active": True,
                },
            )
            gl_accounts[row["gl_code"]] = account
        return gl_accounts

    def create_categories(self):
        category_data = [
            {"name": "Building Materials", "description": "Construction and building materials."},
            {"name": "Electrical", "description": "Electrical fittings and supplies."},
            {"name": "Plumbing", "description": "Plumbing and pipe fittings."},
        ]
        categories = {}
        for row in category_data:
            category, _ = Category.objects.update_or_create(
                name=row["name"],
                defaults={
                    "description": row["description"],
                    "is_active": True,
                },
            )
            categories[row["name"]] = category
        return categories

    def create_suppliers(self):
        supplier_data = [
            {
                "name": "Supplier One",
                "address": "100 Main Street, Colombo",
                "phone_1": "+94 11 234 5678",
                "email": "supplier1@example.com",
                "contact_person": "Nimal Perera",
            },
            {
                "name": "Supplier Two",
                "address": "200 Industrial Road, Kandy",
                "phone_1": "+94 81 987 6543",
                "email": "supplier2@example.com",
                "contact_person": "Amal Fernando",
            },
        ]
        suppliers = {}
        for row in supplier_data:
            supplier, _ = Supplier.objects.update_or_create(
                name=row["name"],
                defaults={
                    "address": row["address"],
                    "phone_1": row["phone_1"],
                    "email": row["email"],
                    "contact_person": row["contact_person"],
                    "is_active": True,
                },
            )
            suppliers[row["name"]] = supplier
        return suppliers

    def create_customers(self, gl_accounts):
        customer_data = [
            {
                "customer_code": "CUST001",
                "name": "Ruwa Construction",
                "phone": "+94 77 123 4567",
                "email": "ruwa@example.com",
                "address": "No. 5, Galle Road, Colombo",
                "credit_limit": Decimal("500000"),
                "registration_no": "REG-RC-2024-001",
            },
            {
                "customer_code": "CUST002",
                "name": "Lotus Developers",
                "phone": "+94 71 765 4321",
                "email": "lotus@example.com",
                "address": "No. 8, Kandy Road, Matale",
                "credit_limit": Decimal("250000"),
                "registration_no": "REG-LD-2024-001",
            },
        ]
        customers = {}
        for row in customer_data:
            customer, _ = Customer.objects.update_or_create(
                customer_code=row["customer_code"],
                defaults={
                    "name": row["name"],
                    "phone": row["phone"],
                    "email": row["email"],
                    "address": row["address"],
                    "credit_limit": row["credit_limit"],
                    "registration_no": row["registration_no"],
                    "receivable_gl_account": gl_accounts.get("1100"),
                    "is_active": True,
                },
            )
            customers[row["customer_code"]] = customer
        return customers

    def create_items(self, categories, suppliers, gl_accounts, user):
        item_data = [
            {
                "item_code": "MAT001",
                "name": "Cement Bag 50kg",
                "category": categories["Building Materials"],
                "supplier": suppliers["Supplier One"],
                "unit": "bag",
                "cost_price": Decimal("950.00"),
                "selling_price": Decimal("1100.00"),
                "stock": Decimal("0"),
                "purchase_date": timezone.localdate(),
                "item_type": "retail",
                "allow_discount": True,
                "max_discount_value": Decimal("50.00"),
                "reorder_level": Decimal("20"),
                "warranty_days": 0,
            },
            {
                "item_code": "ELEC001",
                "name": "LED Bulb 9W",
                "category": categories["Electrical"],
                "supplier": suppliers["Supplier Two"],
                "unit": "pcs",
                "cost_price": Decimal("250.00"),
                "selling_price": Decimal("320.00"),
                "stock": Decimal("0"),
                "purchase_date": timezone.localdate(),
                "item_type": "retail",
                "allow_discount": True,
                "max_discount_value": Decimal("20.00"),
                "reorder_level": Decimal("30"),
                "warranty_days": 365,
            },
        ]
        items = {}
        for row in item_data:
            item, _ = Item.objects.update_or_create(
                item_code=row["item_code"],
                defaults={
                    "name": row["name"],
                    "category": row["category"],
                    "supplier": row["supplier"],
                    "unit": row["unit"],
                    "cost_price": row["cost_price"],
                    "selling_price": row["selling_price"],
                    "stock": row["stock"],
                    "purchase_date": row["purchase_date"],
                    "item_type": row["item_type"],
                    "is_service": False,
                    "allow_discount": row["allow_discount"],
                    "max_discount_value": row["max_discount_value"],
                    "reorder_level": row["reorder_level"],
                    "warranty_days": row["warranty_days"],
                    "retail_gl_account": gl_accounts.get("3000"),
                    "cost_gl_account": gl_accounts.get("4000"),
                    "updated_by": user,
                },
            )
            item.stock = row["stock"]
            item.updated_by = user
            item.save()
            items[row["item_code"]] = item
        return items

    def create_purchase_order(self, suppliers, user, items):
        supplier = suppliers["Supplier One"]
        po, _ = PurchaseOrder.objects.update_or_create(
            po_no="PO00001",
            defaults={
                "po_date": timezone.localdate(),
                "delivery_date_required": timezone.localdate(),
                "buyer_company_name": "Ruwa Construction",
                "buyer_address": "No. 5, Galle Road, Colombo",
                "buyer_contact_person": "Sunil Wickramasinghe",
                "buyer_phone": "+94 77 321 6548",
                "supplier": supplier,
                "supplier_address": supplier.address,
                "supplier_contact_details": supplier.phone_1,
                "payment_method": "bank",
                "payment_period": "30 days",
                "delivery_location": "Ruwa site",
                "delivery_method": "Courier",
                "special_instructions": "Deliver during business hours.",
                "terms_and_conditions": "Payment within 30 days.",
                "status": "approved",
                "created_by": user,
            },
        )

        PurchaseOrderItem.objects.update_or_create(
            purchase_order=po,
            item=items["MAT001"],
            defaults={
                "description": "Cement Bag 50kg",
                "quantity": Decimal("30"),
                "unit_price": Decimal("950.00"),
            },
        )
        PurchaseOrderItem.objects.update_or_create(
            purchase_order=po,
            item=items["ELEC001"],
            defaults={
                "description": "LED Bulb 9W",
                "quantity": Decimal("50"),
                "unit_price": Decimal("250.00"),
            },
        )
        return po

    def create_grn(self, purchase_order, user):
        grn, _ = GRN.objects.update_or_create(
            grn_no="GRN00001",
            defaults={
                "grn_date": timezone.localdate(),
                "received_date": timezone.localdate(),
                "purchase_order": purchase_order,
                "supplier": purchase_order.supplier,
                "delivery_note_no": "DN12345",
                "invoice_no": "INVPO0001",
                "vehicle_no": "WPKA-1234",
                "received_by": "Warehouse Team",
                "inspected_by": "Quality Team",
                "approved_by": "Manager",
                "quality_check_passed": True,
                "quality_notes": "Goods inspected and accepted.",
                "status": "received",
                "notes": "Sample GRN received.",
                "created_by": user,
            },
        )

        for po_item in purchase_order.items.select_related("item").filter(item__isnull=False):
            item = po_item.item
            quantity_received = po_item.quantity
            quantity_accepted = po_item.quantity
            grn_item, _ = GRNItem.objects.update_or_create(
                grn=grn,
                purchase_order_item=po_item,
                defaults={
                    "item": item,
                    "quantity_ordered": po_item.quantity,
                    "quantity_received": quantity_received,
                    "quantity_accepted": quantity_accepted,
                    "quantity_rejected": Decimal("0"),
                    "unit_price": po_item.unit_price,
                    "quality_status": "good",
                    "quality_notes": "Accepted in good condition.",
                },
            )
            grn_item.save()
            self.create_stock_transaction(
                item=item,
                transaction_type="grn",
                qty=quantity_accepted,
                reference_type="po",
                reference_no=grn.grn_no,
                notes=f"Stock received from {grn.grn_no}",
                created_by=user,
            )
            item.stock = Decimal(str(item.stock or 0)) + quantity_accepted
            item.updated_by = user
            item.save()

        return grn

    def create_sale_and_return(self, customers, user, items):
        customer = customers["CUST001"]
        sale, _ = Sale.objects.update_or_create(
            invoice_no="INV00001",
            defaults={
                "total": Decimal("0"),
                "discount": Decimal("0"),
                "grand_total": Decimal("0"),
                "sale_type": "retail",
                "payment_method": "cash",
                "received_amount": Decimal("0"),
                "balance": Decimal("0"),
                "customer_name": customer.name,
                "customer_phone": customer.phone,
                "customer": customer,
                "created_by": user,
            },
        )

        sale_item_1, _ = SaleItem.objects.update_or_create(
            sale=sale,
            item=items["MAT001"],
            defaults={
                "qty": Decimal("5"),
                "price": items["MAT001"].selling_price,
                "discount": Decimal("0"),
                "amount": Decimal("5") * items["MAT001"].selling_price,
                "net_amount": Decimal("5") * items["MAT001"].selling_price,
            },
        )
        sale_item_2, _ = SaleItem.objects.update_or_create(
            sale=sale,
            item=items["ELEC001"],
            defaults={
                "qty": Decimal("2"),
                "price": items["ELEC001"].selling_price,
                "discount": Decimal("0"),
                "amount": Decimal("2") * items["ELEC001"].selling_price,
                "net_amount": Decimal("2") * items["ELEC001"].selling_price,
            },
        )

        sale.total = sale_item_1.net_amount + sale_item_2.net_amount
        sale.grand_total = sale.total
        sale.received_amount = sale.total
        sale.balance = Decimal("0")
        sale.save()

        self.create_stock_transaction(
            item=items["MAT001"],
            transaction_type="sale",
            qty=sale_item_1.qty,
            reference_type="sale",
            reference_no=sale.invoice_no,
            created_by=user,
        )
        self.create_stock_transaction(
            item=items["ELEC001"],
            transaction_type="sale",
            qty=sale_item_2.qty,
            reference_type="sale",
            reference_no=sale.invoice_no,
            created_by=user,
        )

        items["MAT001"].stock = Decimal(str(items["MAT001"].stock or 0)) - sale_item_1.qty
        items["MAT001"].updated_by = user
        items["MAT001"].save()
        items["ELEC001"].stock = Decimal(str(items["ELEC001"].stock or 0)) - sale_item_2.qty
        items["ELEC001"].updated_by = user
        items["ELEC001"].save()

        sales_return, created = SalesReturn.objects.get_or_create(
            return_no="RET00001",
            defaults={
                "sale": sale,
                "sale_item": sale_item_1,
                "qty": Decimal("1"),
                "return_type": "refund",
                "reason": "Damaged packaging",
                "created_by": user,
            },
        )
        sales_return.sale = sale
        sales_return.sale_item = sale_item_1
        sales_return.qty = Decimal("1")
        sales_return.return_type = "refund"
        sales_return.reason = "Damaged packaging"
        sales_return.created_by = user
        sales_return.save()
        if sales_return.qty > 0:
            items["MAT001"].stock = Decimal(str(items["MAT001"].stock or 0)) + sales_return.qty
            items["MAT001"].updated_by = user
            items["MAT001"].save()
            self.create_stock_transaction(
                item=items["MAT001"],
                transaction_type="return_in",
                qty=sales_return.qty,
                reference_type="return",
                reference_no=sales_return.return_no,
                created_by=user,
            )

        return sale

    def create_stock_transaction(
        self,
        item,
        transaction_type,
        qty,
        reference_type=None,
        reference_no=None,
        notes=None,
        created_by=None,
    ):
        StockTransaction.objects.get_or_create(
            item=item,
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_no=reference_no,
            defaults={
                "qty": qty,
                "notes": notes,
                "created_by": created_by,
            },
        )
