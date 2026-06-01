building_store
==============

Overview
--------

``building_store`` is a custom Odoo 19 enterprise MVP module for integrated construction materials retail and trade operations management.

The module covers:

- customer loyalty cards
- construction products
- sales orders
- order lines
- debt transaction ledgers
- debt adjustments
- payment processing wizards
- dynamic analytical pivot views
- printable batch customer statements

Main Features
-------------

- Extended core partner model with indexation tracking for global cashback wallet balances
- Extended company parameters for direct enforcement of maximum credit limit rules
- Loyalty program matrices with individual discount percentages, cashback ratios, and credit lines
- Parallel non-interfering cashback point accrual calculated directly from untaxed baselines
- Dynamic card lifecycle state automations (New Card to Active) driven by completed sales turnover
- Hard credit limit validation blocks intercepting checkout workflows upon capital risk thresholds
- Interactive checkout payment wizard with real-time change calculation and trainee role protection
- Automated ledger posting entries ensuring strict auditing of debt increase/decrease movements
- Multi-dimensional analytical OLAP Pivot cubes and calendar grids for executive revenue analysis
- Batch printable A4 QWeb report packing dynamic client data tables with smart pagebreaks
- Role-based access matrices for trainee cashiers, regular cashiers, and store administrators
- Complete Ukrainian translation localization mapping file
- Rigorous automated backend transaction unit tests suite

Security
--------

The module defines the following Building Store roles:

- Trainee Cashier
- Cashier
- Store Administrator

Operational data access is strictly restricted by field attributes, access rights, and record rules:

- trainee cashiers are barred from editing credit fields on screens and cannot process sales in debt
- cashiers can read, create, and write orders, lines, and cards, but are blocked from manual deletions
- cashiers are restricted via record rules to read exclusively today's open operational sales orders
- store administrators possess absolute horizontal access including historical analysis and unlinking
- manual debt adjustments and ledger overrides are locked exclusively to store administrators

Installation
------------

1. Copy the module to a custom addons path directory.
2. Make sure the custom addons path is included in your ``odoo.conf``.
3. Update the internal apps registry list.
4. Install or upgrade ``building_store``.

Example update command:

.. code-block:: bash

   python odoo-bin -c odoo.conf -d odoo_first_project -u building_store --dev=all

Tests
-----

The module contains automated unit tests for model calculations and integrity constraints.

Run tests with:

.. code-block:: bash

   python odoo-bin -c odoo.conf -d odoo_first_project -u building_store --test-enable --stop-after-init

Demo Data
---------

When demo data is enabled, the module initializes a complete simulation environment:

- customers with opening cashback points balance
- building materials product inventory catalog with custom pricing and SKU articles
- customer loyalty program cards assigned with diverse risk limits and discount rates
- active sales orders containing distinct product lines and pricing structures
- balanced transaction debt ledger entries matching opening balances
- official manual debt adjustment historical log records

Structure
---------

Main directories:

- ``models/``
- ``views/``
- ``wizard/``
- ``report/``
- ``security/``
- ``data/``
- ``i18n/``
- ``tests/``
- ``static/description/``

Author
------

Igor Bagriy