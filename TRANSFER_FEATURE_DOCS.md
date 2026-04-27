# Project Expense & Income Transfer Feature

## Overview
The Project Transfer feature enables moving expenses or income from one project to another while maintaining complete audit trail and historical accuracy. Instead of directly editing records, the system follows a **"reverse + repost" method**.

## Key Business Rules

### Immutable History
- Original expense/income records **cannot be directly edited** for transfer purposes
- Edit functionality is blocked with a clear message directing users to use Project Transfer
- All historical data is preserved for audit and reporting

### Transfer Method: Reverse + Repost
When transferring an amount:

1. **Reverse Entry (Negative)**: Creates a negative entry in the original project to cancel the transferred amount
2. **Repost Entry (Positive)**: Creates a positive entry in the destination project with the same amount
3. **Original Record**: Remains unchanged, linked to the transfer transaction

### Project Status Validation
- Transfers can **only occur between active, ongoing projects**
- Closed or inactive projects block both incoming and outgoing transfers
- Prevents erroneous transfers to/from non-operational projects

### Amount Validation
- Transfer amount **cannot exceed** the original entry amount
- Prevents invalid partial transfers that don't make sense

## Database Model: ProjectTransfer

```
ProjectTransfer
├── transfer_no (auto-generated, format: TRF000001)
├── transfer_type (expense | income)
├── from_project (ForeignKey: Project)
├── to_project (ForeignKey: Project)
├── original_project_expense (ForeignKey: ProjectExpense, nullable)
├── original_project_income (ForeignKey: ProjectIncome, nullable)
├── transfer_amount (Decimal)
├── transfer_date (Date)
├── reason (Text)
├── created_by (ForeignKey: User)
├── approved_by (ForeignKey: User, nullable)
├── notes (Text)
├── created_at (DateTime)
└── approved_at (DateTime, nullable)
```

### Related Fields on ProjectExpense/ProjectIncome

**ProjectExpense**
- `transfer` (ForeignKey: ProjectTransfer) - Links to the transfer record
- `original_expense` (ForeignKey: self) - Links to original if this is a reverse/repost entry

**ProjectIncome**
- `transfer` (ForeignKey: ProjectTransfer) - Links to the transfer record
- `original_income` (ForeignKey: self) - Links to original if this is a reverse/repost entry

## How It Works: Example Scenario

### Scenario: Wrong Project Assignment
Expense EXP001 was posted to Project A (Swimming Pool) but should have been to Project B (Electrical).
- Amount: $5,000
- Date: 2024-01-15

### Step 1: Navigate to Transfer
- Go to **Project Expenses** list
- Find EXP001 and click **Transfer**
- OR go to **Project Transfers** → **New Transfer** and manually select

### Step 2: Create Transfer
| Field | Value |
|-------|-------|
| Transfer Type | Expense |
| Original Entry | EXP001 ($5,000) |
| From Project | A (Swimming Pool) |
| To Project | B (Electrical) |
| Transfer Amount | $5,000 |
| Reason | Wrong project assignment at intake |
| Approved By | [Manager Name] |

### Step 3: System Creates Entries
**Reverse Entry (Project A)**
```
Expense No: EXP002
Project: A (Swimming Pool)
Description: Reverse transfer of 5000 from EXP001. Wrong project assignment at intake
Amount: -$5,000
Status: Linked to Transfer TRF000001
```

**Repost Entry (Project B)**
```
Expense No: EXP003
Project: B (Electrical)
Description: Repost transfer of 5000 from EXP001. Wrong project assignment at intake
Amount: +$5,000
Status: Linked to Transfer TRF000001
```

### Project Balances After Transfer
- **Project A Expenses**: Original $5,000 + Reverse -$5,000 = **$0 net impact**
- **Project B Expenses**: Original $0 + Repost +$5,000 = **+$5,000**

## User Interface

### Project Expense List
- New **Transfer** button on each active expense row
- Direct link: `add_project_transfer?type=expense&original_id={expense.id}`

### Project Income List
- New **Transfer** button on each income row
- Direct link: `add_project_transfer?type=income&original_id={income.id}`

### Add Project Transfer
- **Transfer Type**: Expense or Income (selector)
- **Original Entry**: Dropdown filtered by transfer type
- **From Project**: Auto-populated (read-only)
- **Destination Project**: Dropdown of active, ongoing projects
- **Transfer Amount**: Must be ≤ original amount
- **Approved By**: Optional user approval
- **Reason**: Descriptive reason (required for audit)
- **Notes**: Additional context

### Project Transfer List
- Filter by **Project** (from or to)
- Filter by **Transfer Type** (Expense/Income)
- View all transfers with audit trail
- Display linked original entries and created/approved by

### Edit Project Expense
- **Project field is now read-only** with hidden input
- Error message if user attempts to change project:
  ```
  "Project cannot be changed from this page. 
   Use Project Transfer instead."
  ```

## View Restrictions

### Project Status Checks
```python
# Transfer validation
if not from_project.is_active or from_project.status != "ongoing":
    error: "Transfers not allowed from closed/inactive projects"

if not to_project.is_active or to_project.status != "ongoing":
    error: "Transfers not allowed to closed/inactive projects"
```

## Audit Trail Features

### Transfer Record Captures
1. Who created it (`created_by`)
2. When it was created (`created_at`)
3. Who approved it (`approved_by`)
4. When it was approved (`approved_at`)
5. Reason for transfer (`reason`)
6. Additional notes (`notes`)
7. Exact amount moved (`transfer_amount`)
8. Transfer date (`transfer_date`)

### Linked Records
- Reverse entry: `ProjectExpense.original_expense → Original Entry`
- Repost entry: `ProjectExpense.original_expense → Original Entry`
- Both entries: `ProjectExpense.transfer → ProjectTransfer`

## Financial Reporting Impact

### Project Expense Reports
- **Project A (Before)**: $5,000 expense
- **Project A (After)**: $5,000 - $5,000 = $0 net
- **Project B (Before)**: $0
- **Project B (After)**: $0 + $5,000 = $5,000 net

### GL Ledger
- GL accounts remain the same for reverse/repost entries
- Negative amounts appear as debits
- Positive amounts appear as credits
- Full transaction trail preserved

## API Usage (Views)

### View Transfer List
```python
@user_passes_test(can_use_project)
def project_transfer_list(request):
    # GET params: project, transfer_type (expense|income)
```

### Create Transfer
```python
@user_passes_test(can_use_project)
def add_project_transfer(request):
    # GET params: type (expense|income), original_id
    # POST creates transfer + reverse/repost entries
```

## URL Routes

```
/project-transfers/                    → project_transfer_list (GET)
/project-transfers/add/                → add_project_transfer (GET/POST)
```

Optional Query Parameters:
- `?type=expense|income` - Pre-select transfer type
- `?original_id={id}` - Pre-populate original entry

## Future Enhancements

1. **Bulk Transfers**: Multiple expenses to same destination
2. **Scheduled Transfers**: Transfer at future date
3. **Approval Workflow**: Multi-level approval for large amounts
4. **Transfer Reversal**: Undo a transfer (creates reverse transfer)
5. **Transfer Reports**: Monthly transfer activity by project

## Troubleshooting

### "Transfer amount cannot exceed the original entry amount"
- You entered a transfer amount larger than the original
- **Solution**: Enter amount ≤ original amount

### "Transfers are not allowed from closed or inactive source projects"
- Source project is either inactive or status is not "ongoing"
- **Solution**: Check project status; reopen if necessary

### "Transfers are not allowed to closed or inactive destination projects"
- Destination project is either inactive or status is not "ongoing"
- **Solution**: Ensure destination is active and ongoing

### "Project cannot be changed from this page. Use Project Transfer instead."
- Attempted to edit an expense's project directly
- **Solution**: Use the Transfer button to move between projects

## Integration with Existing Features

### Works With:
- Project Profit Dashboard (includes transfer entries in totals)
- GL Ledger (reverse/repost entries appear in accounts)
- Audit Trail (all transfers logged)
- User Activity Log (transfer creation tracked)

### Does Not Affect:
- Direct expense/income creation
- POS/Sales module
- Petty cash operations
- Purchase orders

