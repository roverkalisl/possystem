"""
Cost Analysis Utilities
Handles actual cost calculations from various sources
"""

from decimal import Decimal
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime
from .models import (
    Project, ProjectExpense, ProjectPettyCashExpense, GRNItem,
    ProjectCostActual, GLMaster, ProjectBudget, ProjectBudgetLine,
    StockTransaction
)


class ProjectCostAnalyzer:
    """Analyze project costs and budgets"""
    
    def __init__(self, project):
        self.project = project
    
    def get_budget_by_gl(self):
        """Get budget breakdown by GL account"""
        try:
            budget = ProjectBudget.objects.get(project=self.project)
            lines = budget.lines.select_related('gl_account').all()
            return {
                line.gl_account.gl_code: {
                    'gl_name': line.gl_account.gl_name,
                    'budget_amount': float(line.budget_amount),
                    'gl_group': ProjectBudgetLine.get_gl_group(line.gl_account.gl_code),
                }
                for line in lines
            }
        except ProjectBudget.DoesNotExist:
            return {}
    
    def get_actual_cost_by_gl(self, end_date=None):
        """Get actual cost breakdown by GL account from all sources"""
        actuals = {}
        
        # Project Expenses (approved only)
        project_expenses = ProjectExpense.objects.filter(
            project=self.project,
            is_active=True,
            gl_account__isnull=False
        )
        
        if end_date:
            project_expenses = project_expenses.filter(expense_date__lte=end_date)
        
        for exp in project_expenses:
            gl_code = exp.gl_account.gl_code
            if gl_code not in actuals:
                actuals[gl_code] = {
                    'gl_name': exp.gl_account.gl_name,
                    'amount': Decimal('0'),
                    'gl_group': ProjectBudgetLine.get_gl_group(gl_code),
                    'transactions': []
                }
            actuals[gl_code]['amount'] += exp.amount
            actuals[gl_code]['transactions'].append({
                'type': 'project_expense',
                'id': exp.id,
                'date': exp.expense_date,
                'ref': exp.expense_no or f'PE-{exp.id}',
                'description': exp.description,
                'amount': float(exp.amount),
            })
        
        # Petty Cash Expenses (approved only)
        petty_expenses = ProjectPettyCashExpense.objects.filter(
            project=self.project,
            approval_status='approved',
            is_active=True,
            gl_account__isnull=False
        )
        
        if end_date:
            petty_expenses = petty_expenses.filter(expense_date__lte=end_date)
        
        for exp in petty_expenses:
            gl_code = exp.gl_account.gl_code
            if gl_code not in actuals:
                actuals[gl_code] = {
                    'gl_name': exp.gl_account.gl_name,
                    'amount': Decimal('0'),
                    'gl_group': ProjectBudgetLine.get_gl_group(gl_code),
                    'transactions': []
                }
            actuals[gl_code]['amount'] += exp.amount
            actuals[gl_code]['transactions'].append({
                'type': 'petty_cash',
                'id': exp.id,
                'date': exp.expense_date,
                'ref': exp.expense_no or f'PCE-{exp.id}',
                'description': exp.description,
                'amount': float(exp.amount),
            })
        
        # GRN Items allocated to project
        grn_items = GRNItem.objects.filter(
            allocation_project=self.project,
            allocation_type='project'
        ).select_related('purchase_order_item__item', 'grn', 'purchase_order_item')
        
        if end_date:
            grn_items = grn_items.filter(grn__grn_date__lte=end_date)
        
        for item in grn_items:
            # Try to get GL account from item's cost_gl_account or parent
            gl_account = item.item.cost_gl_account if item.item else None
            if not gl_account:
                continue
            
            gl_code = gl_account.gl_code
            amount = item.line_total
            
            if gl_code not in actuals:
                actuals[gl_code] = {
                    'gl_name': gl_account.gl_name,
                    'amount': Decimal('0'),
                    'gl_group': ProjectBudgetLine.get_gl_group(gl_code),
                    'transactions': []
                }
            
            actuals[gl_code]['amount'] += amount
            actuals[gl_code]['transactions'].append({
                'type': 'grn_issue',
                'id': item.id,
                'date': item.grn.grn_date,
                'ref': item.grn.grn_no,
                'description': f'{item.item.name} (GRN Issue)',
                'amount': float(amount),
            })
        
        # Convert Decimal to float
        for gl_code in actuals:
            actuals[gl_code]['amount'] = float(actuals[gl_code]['amount'])
        
        return actuals
    
    def get_cost_summary(self, end_date=None):
        """Get overall cost summary for project"""
        budget_by_gl = self.get_budget_by_gl()
        actual_by_gl = self.get_actual_cost_by_gl(end_date)
        
        all_gl_codes = set(budget_by_gl.keys()) | set(actual_by_gl.keys())
        
        summary = {
            'by_gl': {},
            'by_group': {},
            'totals': {
                'budget': 0.0,
                'actual': 0.0,
                'variance': 0.0,
                'utilization_percent': 0.0
            }
        }
        
        # GL-wise summary
        for gl_code in sorted(all_gl_codes):
            budget_amount = float(budget_by_gl.get(gl_code, {}).get('budget_amount', 0))
            actual_amount = float(actual_by_gl.get(gl_code, {}).get('amount', 0))
            variance = budget_amount - actual_amount
            
            gl_name = budget_by_gl.get(gl_code, {}).get('gl_name') or \
                      actual_by_gl.get(gl_code, {}).get('gl_name', '')
            gl_group = budget_by_gl.get(gl_code, {}).get('gl_group') or \
                       actual_by_gl.get(gl_code, {}).get('gl_group', 'Other')
            
            summary['by_gl'][gl_code] = {
                'gl_name': gl_name,
                'budget': budget_amount,
                'actual': actual_amount,
                'variance': variance,
                'utilization_percent': (actual_amount / budget_amount * 100) if budget_amount > 0 else 0,
                'gl_group': gl_group,
                'transactions': actual_by_gl.get(gl_code, {}).get('transactions', [])
            }
            
            # Group-wise accumulation
            if gl_group not in summary['by_group']:
                summary['by_group'][gl_group] = {
                    'budget': 0.0,
                    'actual': 0.0,
                    'variance': 0.0,
                    'gl_codes': []
                }
            
            summary['by_group'][gl_group]['budget'] += budget_amount
            summary['by_group'][gl_group]['actual'] += actual_amount
            summary['by_group'][gl_group]['variance'] += variance
            summary['by_group'][gl_group]['gl_codes'].append(gl_code)
            
            # Total accumulation
            summary['totals']['budget'] += budget_amount
            summary['totals']['actual'] += actual_amount
            summary['totals']['variance'] += variance
        
        # Calculate utilization percent
        if summary['totals']['budget'] > 0:
            summary['totals']['utilization_percent'] = \
                (summary['totals']['actual'] / summary['totals']['budget']) * 100
        
        # Calculate group utilization
        for group_data in summary['by_group'].values():
            if group_data['budget'] > 0:
                group_data['utilization_percent'] = \
                    (group_data['actual'] / group_data['budget']) * 100
            else:
                group_data['utilization_percent'] = 0.0
        
        return summary
    
    def get_gl_group_summary(self):
        """Get summary grouped by GL Group"""
        summary = self.get_cost_summary()
        return summary['by_group']
    
    def get_transaction_details(self, gl_code=None, gl_group=None):
        """Get detailed transaction list for a GL code or GL group"""
        transactions = []
        
        # Project Expenses
        qs = ProjectExpense.objects.filter(
            project=self.project,
            is_active=True
        ).select_related('gl_account')
        
        if gl_code:
            qs = qs.filter(gl_account__gl_code=gl_code)
        elif gl_group:
            # Get all GL codes in the group
            gl_codes = self._get_gl_codes_in_group(gl_group)
            qs = qs.filter(gl_account__gl_code__in=gl_codes)
        
        for exp in qs:
            transactions.append({
                'type': 'Project Expense',
                'date': exp.expense_date,
                'ref_no': exp.expense_no or f'PE-{exp.id}',
                'description': exp.description,
                'gl_code': exp.gl_account.gl_code if exp.gl_account else '',
                'gl_name': exp.gl_account.gl_name if exp.gl_account else '',
                'amount': float(exp.amount),
                'supplier': '-',
                'created_by': exp.created_by.username if exp.created_by else '',
            })
        
        # Petty Cash Expenses
        qs = ProjectPettyCashExpense.objects.filter(
            project=self.project,
            approval_status='approved',
            is_active=True
        ).select_related('gl_account')
        
        if gl_code:
            qs = qs.filter(gl_account__gl_code=gl_code)
        elif gl_group:
            gl_codes = self._get_gl_codes_in_group(gl_group)
            qs = qs.filter(gl_account__gl_code__in=gl_codes)
        
        for exp in qs:
            transactions.append({
                'type': 'Petty Cash Expense',
                'date': exp.expense_date,
                'ref_no': exp.expense_no or f'PCE-{exp.id}',
                'description': exp.description,
                'gl_code': exp.gl_account.gl_code if exp.gl_account else '',
                'gl_name': exp.gl_account.gl_name if exp.gl_account else '',
                'amount': float(exp.amount),
                'supplier': '-',
                'created_by': exp.created_by.username if exp.created_by else '',
            })
        
        # GRN Items
        qs = GRNItem.objects.filter(
            allocation_project=self.project,
            allocation_type='project'
        ).select_related('item', 'grn', 'purchase_order_item')
        
        if gl_code or gl_group:
            gl_codes = [gl_code] if gl_code else self._get_gl_codes_in_group(gl_group or '')
            qs = qs.filter(item__cost_gl_account__gl_code__in=gl_codes)
        
        for item in qs:
            if not item.item:
                continue
            gl_code_val = item.item.cost_gl_account.gl_code if item.item.cost_gl_account else ''
            transactions.append({
                'type': 'GRN Issue',
                'date': item.grn.grn_date,
                'ref_no': item.grn.grn_no,
                'description': f'{item.item.name} x {item.quantity_accepted}',
                'gl_code': gl_code_val,
                'gl_name': item.item.cost_gl_account.gl_name if item.item.cost_gl_account else '',
                'amount': float(item.line_total),
                'supplier': item.grn.supplier.name if item.grn.supplier else '',
                'created_by': item.grn.created_by.username if item.grn.created_by else '',
            })
        
        # Sort by date descending
        transactions.sort(key=lambda x: x['date'], reverse=True)
        
        return transactions
    
    @staticmethod
    def _get_gl_codes_in_group(gl_group):
        """Get all GL codes in a GL group"""
        gl_ranges = {
            'Direct Material Cost': range(5100, 5200),
            'Direct Labour Cost': range(5200, 5300),
            'Plant & Equipment Cost': range(5300, 5400),
            'Subcontractor Cost': range(5400, 5500),
            'Third Party Service Cost': range(5500, 5600),
            'Transportation & Logistics': range(5600, 5700),
            'Project-Specific Expenses': range(5700, 5800),
            'Variations / Cost Adjustments': range(5800, 5900),
            'Retail Operating Expenses': range(5900, 6000),
            'Overhead Expenses': range(6000, 6100),
            'Selling & Marketing': range(6100, 6200),
            'General Expenses': range(6200, 6300),
        }
        
        if gl_group in gl_ranges:
            return [str(i) for i in gl_ranges[gl_group]]
        return []
    
    def update_cost_actuals_cache(self):
        """Update ProjectCostActual cache from sources"""
        # Clear existing cache for this project
        ProjectCostActual.objects.filter(project=self.project).delete()
        
        # Project Expenses
        for exp in ProjectExpense.objects.filter(project=self.project, is_active=True):
            if exp.gl_account:
                ProjectCostActual.objects.create(
                    project=self.project,
                    gl_account=exp.gl_account,
                    source_type='project_expense',
                    source_id=str(exp.id),
                    transaction_date=exp.expense_date,
                    description=exp.description,
                    amount=exp.amount,
                    reference_no=exp.expense_no or f'PE-{exp.id}'
                )
        
        # Petty Cash Expenses (approved only)
        for exp in ProjectPettyCashExpense.objects.filter(
            project=self.project,
            approval_status='approved',
            is_active=True
        ):
            if exp.gl_account:
                ProjectCostActual.objects.create(
                    project=self.project,
                    gl_account=exp.gl_account,
                    source_type='petty_cash',
                    source_id=str(exp.id),
                    transaction_date=exp.expense_date,
                    description=exp.description,
                    amount=exp.amount,
                    reference_no=exp.expense_no or f'PCE-{exp.id}'
                )
        
        # GRN Items
        for item in GRNItem.objects.filter(
            allocation_project=self.project,
            allocation_type='project'
        ):
            if item.item and item.item.cost_gl_account:
                ProjectCostActual.objects.create(
                    project=self.project,
                    gl_account=item.item.cost_gl_account,
                    source_type='grn_issue',
                    source_id=str(item.id),
                    transaction_date=item.grn.grn_date,
                    description=f'{item.item.name} (GRN Issue)',
                    amount=item.line_total,
                    reference_no=item.grn.grn_no
                )


def refresh_project_cost_analysis(project_id):
    """Utility function to refresh cost analysis for a project"""
    try:
        project = Project.objects.get(id=project_id)
        analyzer = ProjectCostAnalyzer(project)
        analyzer.update_cost_actuals_cache()
        return True
    except Project.DoesNotExist:
        return False
