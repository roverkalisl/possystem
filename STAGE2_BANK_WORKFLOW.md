# Stage 2 Bank Workflow

## Implemented

- Bank transaction lifecycle: Draft -> Pending Approval -> Approved -> Posted.
- Deposit, withdrawal, cheque, other transaction, and internal bank-to-bank transfer support.
- Posted transactions create bank ledger entries with a running balance.
- Posted transactions create balanced bank-specific GL entries using existing `GLMaster` accounts.
- Only Posted transactions affect `BankAccount.current_balance`.
- Owner/superuser approval and posting endpoints reuse the existing `is_owner` permission helper.
- Posted transactions cannot be silently edited. Use `BankTransaction.reverse()` to create a draft correction for approval.
- Posting is protected against duplicate ledger and GL entries.
- Audit fields include creator, approver, poster, and timestamps.

## Validation

- `python manage.py check`: passed.
- `python manage.py makemigrations --check --dry-run`: no changes detected.
- `python manage.py migrate --plan`: no pending operations.
- Focused live smoke tests: deposit, withdrawal, cheque, internal transfer, balances, ledger entries, GL entries, duplicate posting, immutability, reversal, and owner-only approval all passed.

## Existing SQLite Test-Runner Issue

The focused Django test command remains blocked by the pre-existing local SQLite test-database state:

`django.db.utils.OperationalError: table "pos_purchaseorder" already exists`

This is an environment/test-database setup issue. Existing ERP/POS models and records were not modified or deleted to bypass it. The application passes Django system checks, migrations apply cleanly, and the Stage 2 behavior was validated with focused live-database smoke tests.
