from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError


class TestBuildingStoreAdjustment(TransactionCase):
    """
    Automated backend unit testing suite for the Building Store debt adjustment entity.
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

        # 2. Create an active customer loyalty card (Required to link adjustments)
        self.card = self.env["bm.loyalty.card"].create(
            {
                "name": "CARD-TEST-777",
                "partner_id": self.customer.id,
                "discount_percent": 10.0,
                "cashback_percent": 5.0,
                "credit_limit": 5000.0,
            }
        )

    def test_debt_adjustment_and_repayment_validation(self):
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
