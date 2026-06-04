from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestBuildingStoreCard(TransactionCase):
    """
    Automated backend unit testing suite for the Building Store loyalty card entity.
    """

    def setUp(self):
        """
        Initializes core testing persistence environment context records.
        """
        super().setUp()

        # 1. Create a clean customer record profile
        self.customer = self.env["res.partner"].create(
            {
                "name": "Test Contractor Ivanenko",
                "phone": "+380509998877",
                "total_cashback_balance": 0.0,
            }
        )

        # 2. Create a clean store product record
        self.product = self.env["bm.product"].create(
            {"name": "Cement Bag Test M-500", "sku": "TST-CEM-01", "list_price": 200.0}
        )

        # 3. Create an active customer loyalty card
        self.card = self.env["bm.loyalty.card"].create(
            {
                "name": "CARD-TEST-777",
                "partner_id": self.customer.id,
                "discount_percent": 10.0,  # 10% structural invoice discount
                "cashback_percent": 5.0,  # 5% parallel cashback wallet accrual
                "credit_limit": 5000.0,  # Max allowed credit cap balance
            }
        )

    def test_card_lifecycle_and_turnover_recalculation(self):
        """
        Verifies that a newly created loyalty card starts at 'new' state,
        and shifts to 'active' automatically once a sales order is completed.
        """
        # Card should initially sit in 'new' stage because turnover is 0.00
        self.assertEqual(self.card.state, "new")
        self.assertEqual(self.card.total_sales_volume, 0.0)

        # Create and post a fast sales order to inject real completed turnover
        order = self.env["bm.order"].create(
            {
                "partner_id": self.customer.id,
                "card_id": self.card.id,
            }
        )

        self.env["bm.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 5.0,  # 5 bags * 200.0 = 1000.00 base
                "price_unit": 200.0,
            }
        )

        # Trigger manual checkout totals generation
        order._compute_order_totals()

        # Complete the checkout processing workflow
        order.write({"state": "done"})

        # Recalculate card totals metrics using explicit computed trigger calls
        self.card._compute_sales_volume()
        self.card._compute_card_state()

        # Assert card metrics recalculated correctly and state shifted
        self.assertEqual(
            order.amount_total, 900.0
        )  # 1000.00 - 10% discount = 900.00 net
        self.assertEqual(self.card.total_sales_volume, 900.0)
        self.assertEqual(self.card.state, "active")

    def test_blocked_state_integrity_constraint_rules(self):
        """
        Assures backend write method rules block an administrator from setting
        a card state to 'blocked' if there is an active un-repaid debt on it.
        """
        # Inject an initial debt movement record into the ledger registry table
        self.env["bm.debt.ledger"].create(
            {
                "partner_id": self.customer.id,
                "card_id": self.card.id,
                "amount": 1500.0,
                "direction": "increase",  # Debt increased by 1500.00
                "res_model": "bm.loyalty.card",
                "res_id": self.card.id,
            }
        )

        # Recalculate operational ledger cached data column values
        self.card._compute_current_debt()
        self.assertEqual(self.card.current_debt, 1500.0)

        # Explicit attempt to block a card that holds outstanding debts should crash with ValidationError
        with self.assertRaises(ValidationError):
            self.card.write({"state": "blocked"})
