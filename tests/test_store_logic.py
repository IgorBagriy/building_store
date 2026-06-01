# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestBuildingStoreLogic(TransactionCase):
    """
    Automated backend unit testing suite for the Building Store core business logic.
    Validates dynamic card state lifecycles, parallel cashback calculations, and strict credit boundary blocks.
    """

    def setUp(self):
        """
        Initializes core testing persistence environment context records.
        """
        super(TestBuildingStoreLogic, self).setUp()

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

    def test_01_card_lifecycle_and_turnover_recalculation(self):
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

    def test_02_parallel_cashback_accrual_and_checkout_math(self):
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

    def test_03_blocked_state_integrity_constraint_rules(self):
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

    def test_04_credit_limit_breach_prevention(self):
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

    def test_05_debt_adjustment_and_repayment_validation(self):
        """
        Validates the financial integrity of the debt adjustment registry module,
        and blocks any payment inputs that attempt to overpay or exceed actual card debt.
        """
        # 1. Inject an initial opening debt of 2000.00 via a manual adjustment increase
        self.env["bm.debt.adjustment"].create(
            {
                "name": "ADJ-TEST-IN",
                "card_id": self.card.id,
                "partner_id": self.customer.id,
                "amount": 2000.0,
                "type": "increase",
            }
        )
        self.card._compute_current_debt()
        self.assertEqual(self.card.current_debt, 2000.0)

        # 2. Fraud Check: Attempting to process a 2500.00 repayment (which is 500.00 over the debt)
        with self.assertRaises(ValidationError):
            self.env["bm.debt.adjustment"].create(
                {
                    "name": "ADJ-TEST-ERR",
                    "card_id": self.card.id,
                    "partner_id": self.customer.id,
                    "amount": 2500.0,
                    "type": "decrease",
                }
            )

        # 3. Process a legitimate partial debt repayment record of 1200.00
        self.env["bm.debt.adjustment"].create(
            {
                "name": "ADJ-TEST-OK",
                "card_id": self.card.id,
                "partner_id": self.customer.id,
                "amount": 1200.0,
                "type": "decrease",
            }
        )
        self.card._compute_current_debt()
        # The remaining outstanding balance must be strictly: 2000.00 - 1200.00 = 800.00
        self.assertEqual(self.card.current_debt, 800.0)
