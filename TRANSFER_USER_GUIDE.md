# Project Expense & Income Transfer Feature - User Guide

## Quick Start

### For Project Managers
You can now transfer expenses or income from one project to another with complete audit trail and historical accuracy.

## Step-by-Step Guide

### Method 1: Transfer from Project Expense List

1. **Navigate to Project Expenses**
   - Click "💸 Project Expenses" in sidebar
   - OR Dashboard → Project Expenses

2. **Find the Expense to Transfer**
   - Use the project filter if needed
   - Locate the expense in the table

3. **Click Transfer Button**
   - Each expense row has a **Transfer** button
   - Click to open the transfer form

4. **Complete the Transfer**
   - **Destination Project**: Select where to move it
   - **Transfer Amount**: Enter the amount (defaults to full amount)
   - **Reason**: Explain why (e.g., "Posted to wrong project at intake")
   - **Approved By**: Optional - select approver
   - Click **Create Transfer**

### Method 2: Transfer from Project Income List

1. **Navigate to Project Income**
   - Click "💰 Project Income" in sidebar

2. **Find the Income to Transfer**
   - Filter by project if needed
   - Locate the income record

3. **Click Transfer Button**
   - Each income row has a **Transfer** button

4. **Complete the Transfer**
   - Same as expense transfer
   - **Destination Project**, **Reason**, etc.
   - Click **Create Transfer**

### Method 3: Manual Transfer (Advanced)

1. **Go to Project Transfers**
   - Click "🔁 Project Transfers" in sidebar
   - Click **+ New Transfer**

2. **Select Transfer Type**
   - **Expense**: For transferring expenses
   - **Income**: For transferring income

3. **Choose Original Entry**
   - Dropdown lists all entries of that type
   - Shows: Entry No | Project | Description | Amount
   - Example: `EXP001 | PROJ-001 | Labor costs | $2,500.00`

4. **Fill in Details**
   - **From Project**: Auto-populated (read-only)
   - **To Project**: Where to move it
   - **Transfer Amount**: Must be ≤ original amount
   - **Transfer Date**: When it occurred
   - **Approved By**: Who approved (optional)
   - **Reason**: Why transfer was needed
   - **Notes**: Any additional context

5. **Submit**
   - Click **Create Transfer**

## What Happens After Creating a Transfer

### Automatic Entries Created
The system automatically creates two entries:

#### Reverse Entry (in original project)
- **Amount**: Negative (e.g., -$2,500)
- **Description**: "Reverse transfer of 2500 from EXP001. Labor costs..."
- **Purpose**: Cancels the original entry

#### Repost Entry (in destination project)  
- **Amount**: Positive (e.g., +$2,500)
- **Description**: "Repost transfer of 2500 from EXP001. Labor costs..."
- **Purpose**: Records the amount in correct project

### Example
**Original State:**
- Project A: $2,500 expense
- Project B: $0

**After Transfer:**
- Project A: $2,500 (original) + (-$2,500) reverse = **$0 net**
- Project B: $0 (original) + (+$2,500) repost = **+$2,500 net**

## Viewing Your Transfers

### Transfer List
1. Click "🔁 Project Transfers" in sidebar
2. **Filter by:**
   - Project: See transfers involving specific project
   - Type: Show only Expense or Income transfers
3. **View columns:**
   - Transfer No: Unique identifier (TRF000001, etc.)
   - Type: Expense or Income
   - From/To: Project codes
   - Original Entry: Reference number
   - Amount: Transfer amount
   - Created By: Who created it
   - Approved By: Who approved it

## Important Rules & Restrictions

### Cannot Transfer
❌ From a **closed** or **inactive** project
❌ To a **closed** or **inactive** project  
❌ Amount **exceeding** original entry amount
❌ **Same project** as destination (must differ)

### Cannot Edit Directly
❌ Opening edit on an expense shows **read-only project field**
- Use **Transfer** button instead
- Error prevents accidental direct edits

### Must Provide
✅ **Destination Project** (required)
✅ **Transfer Amount** > 0 (required)
✅ **Reason** (recommended for audit)

## Real-World Examples

### Example 1: Wrong Project Posted at Intake
**Situation:** Swimming pool labor was entered to Electrical project

**Action:**
1. Find expense: "Labor Day 1" $5,000 in Electrical
2. Click Transfer
3. Destination: Swimming Pool
4. Reason: "Posted to wrong project at intake"
5. Submit

**Result:**
- Electrical: -$5,000 (reverse entry)
- Swimming Pool: +$5,000 (repost entry)

### Example 2: Partial Transfer for Shared Resource
**Situation:** Equipment purchased $10,000 but shared between Project A (60%) & Project B (40%)

**Action 1:** Transfer 40% ($4,000)
- From: Project A
- To: Project B  
- Amount: $4,000
- Reason: "Shared equipment allocation"

**Result:**
- Project A: $10,000 - $4,000 = $6,000 (60%)
- Project B: $0 + $4,000 = $4,000 (40%)

### Example 3: Late-Approved Income Correction
**Situation:** Invoice payment received but posted to wrong project

**Action:**
1. Find income: "Invoice #123" $15,000 in Client Name (wrong)
2. Click Transfer
3. Destination: Correct Project
4. Reason: "Invoice misdirected, correcting per client"
5. Approved By: [Manager]
6. Submit

**Result:**
- Wrong Project: -$15,000 (reverse)
- Correct Project: +$15,000 (repost)
- Audit trail shows manager approval

## Troubleshooting

### Problem: "Transfers are not allowed from closed or inactive source projects"
**Why:** Original project is not active or not in "ongoing" status
**Solution:** Check project status. If it should be active, update Project settings first.

### Problem: "Transfers are not allowed to closed or inactive destination projects"
**Why:** Destination project is not active or not "ongoing"
**Solution:** Select an active, ongoing project instead.

### Problem: "Transfer amount cannot exceed the original entry amount"
**Why:** You entered amount > original
**Solution:** 
- For full transfer: Leave blank to auto-fill or enter exact amount
- For partial transfer: Enter amount less than original

### Problem: "Destination project must be different from source project"
**Why:** You selected the same project for source and destination
**Solution:** Choose a different destination project

### Problem: "Project cannot be changed from this page. Use Project Transfer instead."
**Why:** You tried to edit expense/income and change the project
**Solution:** Use Transfer button instead

## Financial Impact

### Project Expense Reports
- **Before Transfer:**  
  Project A: $5,000 expense
  
- **After Transfer to B:**  
  Project A: $5,000 - $5,000 = $0 net  
  Project B: $0 + $5,000 = $5,000 net

### Project Profit Dashboard
- Transfers automatically included in totals
- Reverse/repost entries adjust project profitability
- Correct project gets proper credit for costs

### GL Ledger
- Both reverse and repost entries posted to GL
- Amount debits and credits offset within original GL
- Full transaction trail visible in GL reports

## Benefits of Transfer Method

✅ **Audit Trail**: Every transfer logged with who/when
✅ **Reversibility**: See what changed and why
✅ **Accuracy**: Projects get correct financial records
✅ **Compliance**: Historical data preserved
✅ **Traceability**: Link from transfer → original entry
✅ **Accountability**: Created by/Approved by tracking

## Approval Workflow (Optional)

For larger transfers, you can assign an approver:

1. **Create Transfer**: Fill form with all details
2. **Select Approver**: "Approved By" field (optional)
3. **Submit**: Transfer created and marked as approved
4. **Audit Trail**: Shows approval date and approver name

## Restrictions by User Role

### Project Manager/Admin
✅ Full access to all transfers
✅ Can create transfers
✅ Can assign approvals

### Accountant
✅ View all transfers
✅ Can create transfers with approval
✅ Cannot skip approval requirements

### Standard User
✅ View assigned project transfers
✅ May have limited destination projects

## Frequently Asked Questions

**Q: Can I transfer multiple expenses at once?**
A: Not in this version. Transfer one at a time. Each transfer is individually audited.

**Q: Can I reverse a transfer?**
A: Create a new transfer in the opposite direction. The original transfer stays in history.

**Q: Does the transfer date matter?**
A: Yes! Set it to when the correction is needed. GL entries use this date.

**Q: Will reports show the original entry?**
A: No. Reports show the corrected balances (reverse + repost = net effect).

**Q: Can closed projects receive transfers?**
A: No. Only active, ongoing projects can have transfers.

**Q: Is approval required?**
A: Optional. Set "Approved By" for audit purposes.

**Q: Can I transfer partial amounts?**
A: Yes! Enter any amount ≤ original amount.

## Getting Help

If you encounter issues:
1. Check the **Troubleshooting** section above
2. Contact your System Administrator
3. Refer to Project Transfer documentation in system

