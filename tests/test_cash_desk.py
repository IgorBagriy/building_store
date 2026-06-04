from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestBuildingStoreCashDesk(TransactionCase):
    """
    Automated backend unit testing suite for the Building Store checkout wizard entity.
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

    def test_parallel_cashback_accrual_and_checkout_math(self):
        """
        Validates that the checkout wizard processes parallel independent cashback mechanics
        without decreasing base customer discounts or altering sales line subtotal parameters.
        """
        # Set up an open order record for processing payments
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
                "product_uom_qty": 10.0,  # 10 bags * 200.0 = 2000.00 base
                "price_unit": 200.0,
            }
        )

        order._compute_order_totals()

        # Initialize the interactive cash desk checkout wizard in testing sandbox
        wizard = (
            self.env["bm.payment.wizard"]
            .with_context(active_model="bm.order", active_id=order.id)
            .create(
                {
                    "cash_paid": 1800.0,  # Full net amount (2000.00 - 10% = 1800.00)
                    "cashback_paid": 0.0,  # Customer spends no cashback points
                    "allow_debt": False,
                }
            )
        )

        # Trigger reactive real-time simple math calculations method execution
        wizard._compute_cash_desk_calculations()

        # Verify initial payments totals look correct inside viewport data mapping
        self.assertEqual(wizard.amount_to_pay, 1800.0)
        self.assertEqual(wizard.remaining_debt, 0.0)

        # Execute final commercial posting transaction method trigger
        wizard.action_process_sale()

        # Assert order state is locked and cashback is accrued based on raw untaxed baseline
        self.assertEqual(order.state, "done")
        # Earned: 2000.00 untaxed * 5% cashback rate = 100.00 points added
        self.assertEqual(self.customer.total_cashback_balance, 100.0)

    def test_credit_limit_breach_prevention(self):
        """
        Verifies hard blocking of a cashier operation if the requested
        new debt amount pushes the total balance beyond the card's assigned credit limit.
        """
        order = self.env["bm.order"].create(
            {
                "partner_id": self.customer.id,
                "card_id": self.card.id,
            }
        )

        # Create a large order where total net amount severely exceeds the limit (5000.00)
        self.env["bm.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": 40.0,  # 40 * 200 = 8000 base (7200 net after 10% discount)
                "price_unit": 200.0,
            }
        )
        order._compute_order_totals()

        # Customer pays zero cash, and the cashier attempts to push the full amount to debt
        wizard = (
            self.env["bm.payment.wizard"]
            .with_context(active_model="bm.order", active_id=order.id)
            .create({"cash_paid": 0.0, "cashback_paid": 0.0, "allow_debt": True})
        )
        wizard._compute_cash_desk_calculations()

        # Assert rigid backend crash via ValidationError (Requested Debt 7200 > Credit Limit 5000)
        with self.assertRaises(ValidationError):
            wizard.action_process_sale()
