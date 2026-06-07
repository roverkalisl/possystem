"""
Project Cost Analysis Views
Handles budget management, cost analysis reports, and dashboards
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Sum, Q, F
from django.utils import timezone
from decimal import Decimal
import json
from datetime import datetime
from io import BytesIO
import csv

from .models import (
    Project, ProjectBudget, ProjectBudgetLine, ProjectExpense,
    ProjectPettyCashExpense, GRNItem, GLMaster
)
from .forms import BudgetUploadForm, ProjectBudgetForm, ProjectBudgetLineFormSet
from .cost_analysis import ProjectCostAnalyzer


def has_cost_analysis_permission(user):
    """Check if user has permission to access cost analysis"""
    return user.is_superuser or user.is_staff or user.groups.filter(
        name__in=['Finance Manager', 'Project Manager', 'Owner']
    ).exists()


@login_required
@require_http_methods(["GET"])
def project_cost_analysis_list(request):
    """List all projects with cost analysis available"""
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to access cost analysis')
        return redirect('dashboard')
    
    projects = Project.objects.filter(is_active=True).prefetch_related('budget')
    
    context = {
        'projects': projects,
        'page_title': 'Project Cost Analysis'
    }
    return render(request, 'pos/cost_analysis_list.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def budget_upload(request):
    """Upload project budget from Excel file"""
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to upload budgets')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = BudgetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                project = form.cleaned_data['project']
                excel_file = request.FILES['budget_file']
                replace_existing = form.cleaned_data.get('replace_existing', False)
                
                # Process Excel file
                success_count, error_messages = process_budget_excel(
                    project, excel_file, replace_existing
                )
                
                if error_messages:
                    for error in error_messages:
                        messages.warning(request, error)
                
                messages.success(
                    request,
                    f'Budget imported successfully. {success_count} GL accounts added.'
                )
                return redirect('project_cost_analysis_detail', project_id=project.id)
            
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
    else:
        form = BudgetUploadForm()
    
    context = {
        'form': form,
        'page_title': 'Upload Budget'
    }
    return render(request, 'pos/budget_upload.html', context)


@login_required
@require_http_methods(["GET"])
def project_cost_analysis_detail(request, project_id):
    """Detailed cost analysis for a specific project"""
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to view cost analysis')
        return redirect('dashboard')
    
    project = get_object_or_404(Project, id=project_id, is_active=True)
    analyzer = ProjectCostAnalyzer(project)
    
    # Get summary data
    summary = analyzer.get_cost_summary()
    
    # Get date range filter
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    context = {
        'project': project,
        'summary': summary,
        'page_title': f'Cost Analysis - {project.project_id}',
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'pos/cost_analysis_detail.html', context)


@login_required
@require_http_methods(["GET"])
def cost_analysis_by_gl_group(request):
    """GL Group-wise cost analysis report"""
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to view reports')
        return redirect('dashboard')
    
    # Get filters
    project_id = request.GET.get('project_id')
    gl_group = request.GET.get('gl_group')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    projects = Project.objects.filter(is_active=True)
    summary_data = {}
    
    if project_id:
        projects = projects.filter(id=project_id)
    
    for project in projects:
        analyzer = ProjectCostAnalyzer(project)
        if gl_group:
            # Filter by specific GL group
            full_summary = analyzer.get_cost_summary()
            if gl_group in full_summary['by_group']:
                summary_data[project.id] = {
                    'project': project,
                    'data': {gl_group: full_summary['by_group'][gl_group]},
                    'total': full_summary['by_group'][gl_group]
                }
        else:
            # All GL groups
            summary = analyzer.get_cost_summary()
            summary_data[project.id] = {
                'project': project,
                'data': summary['by_group'],
                'total': summary['totals']
            }
    
    context = {
        'summary_data': summary_data,
        'projects': projects,
        'gl_groups': [
            'Direct Material Cost', 'Direct Labour Cost', 'Plant & Equipment Cost',
            'Subcontractor Cost', 'Third Party Service Cost', 'Transportation & Logistics',
            'Project-Specific Expenses', 'Variations / Cost Adjustments',
            'Retail Operating Expenses', 'Overhead Expenses', 'Selling & Marketing',
            'General Expenses', 'Other Expenses'
        ],
        'page_title': 'GL Group Cost Analysis',
        'selected_project': project_id,
        'selected_group': gl_group,
    }
    return render(request, 'pos/cost_analysis_gl_group.html', context)


@login_required
@require_http_methods(["GET"])
def transaction_details(request, project_id):
    """Show detailed transactions for a GL code or GL group"""
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to view transactions')
        return redirect('dashboard')
    
    project = get_object_or_404(Project, id=project_id, is_active=True)
    gl_code = request.GET.get('gl_code')
    gl_group = request.GET.get('gl_group')
    
    analyzer = ProjectCostAnalyzer(project)
    transactions = analyzer.get_transaction_details(gl_code=gl_code, gl_group=gl_group)
    
    context = {
        'project': project,
        'transactions': transactions,
        'gl_code': gl_code,
        'gl_group': gl_group,
        'page_title': f'Transaction Details - {project.project_id}',
    }
    return render(request, 'pos/transaction_details.html', context)


@login_required
@require_http_methods(["GET"])
def export_cost_analysis(request, project_id):
    """Export cost analysis to Excel"""
    try:
        import openpyxl
    except ImportError:
        messages.error(request, 'openpyxl package is not installed. Please contact administrator.')
        return redirect('project_cost_analysis_detail', project_id=project_id)
    
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to export')
        return redirect('dashboard')
    
    project = get_object_or_404(Project, id=project_id, is_active=True)
    analyzer = ProjectCostAnalyzer(project)
    summary = analyzer.get_cost_summary()
    
    # Create Excel workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Cost Analysis'
    
    # Header
    ws['A1'] = 'Project Cost Analysis Report'
    ws['A2'] = f'Project: {project.project_id} - {project.project_name}'
    ws['A3'] = f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
    
    # GL-wise Summary
    row = 5
    ws[f'A{row}'] = 'GL Code'
    ws[f'B{row}'] = 'GL Name'
    ws[f'C{row}'] = 'Budget'
    ws[f'D{row}'] = 'Actual'
    ws[f'E{row}'] = 'Variance'
    ws[f'F{row}'] = 'Utilization %'
    
    row += 1
    for gl_code in sorted(summary['by_gl'].keys()):
        data = summary['by_gl'][gl_code]
        ws[f'A{row}'] = gl_code
        ws[f'B{row}'] = data['gl_name']
        ws[f'C{row}'] = data['budget']
        ws[f'D{row}'] = data['actual']
        ws[f'E{row}'] = data['variance']
        ws[f'F{row}'] = round(data['utilization_percent'], 2)
        row += 1
    
    # Totals
    row += 1
    ws[f'A{row}'] = 'TOTAL'
    ws[f'C{row}'] = summary['totals']['budget']
    ws[f'D{row}'] = summary['totals']['actual']
    ws[f'E{row}'] = summary['totals']['variance']
    ws[f'F{row}'] = round(summary['totals']['utilization_percent'], 2)
    
    # GL Group Summary
    row += 3
    ws[f'A{row}'] = 'GL Group Summary'
    row += 1
    ws[f'A{row}'] = 'GL Group'
    ws[f'B{row}'] = 'Budget'
    ws[f'C{row}'] = 'Actual'
    ws[f'D{row}'] = 'Variance'
    ws[f'E{row}'] = 'Utilization %'
    
    row += 1
    for group_name in sorted(summary['by_group'].keys()):
        data = summary['by_group'][group_name]
        ws[f'A{row}'] = group_name
        ws[f'B{row}'] = data['budget']
        ws[f'C{row}'] = data['actual']
        ws[f'D{row}'] = data['variance']
        ws[f'E{row}'] = round(data.get('utilization_percent', 0), 2)
        row += 1
    
    # Set column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 30
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 15
    
    # Create response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = \
        f'attachment; filename="Cost_Analysis_{project.project_id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.xlsx"'
    
    wb.save(response)
    return response


@login_required
@require_http_methods(["GET"])
def export_cost_analysis_csv(request, project_id):
    """Export cost analysis to CSV"""
    if not has_cost_analysis_permission(request.user):
        messages.error(request, 'You do not have permission to export')
        return redirect('dashboard')
    
    project = get_object_or_404(Project, id=project_id, is_active=True)
    analyzer = ProjectCostAnalyzer(project)
    summary = analyzer.get_cost_summary()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = \
        f'attachment; filename="Cost_Analysis_{project.project_id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    
    # Header
    writer.writerow(['Project Cost Analysis Report'])
    writer.writerow([f'Project: {project.project_id} - {project.project_name}'])
    writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
    writer.writerow([])
    
    # GL-wise Summary
    writer.writerow(['GL Code', 'GL Name', 'Budget', 'Actual', 'Variance', 'Utilization %'])
    for gl_code in sorted(summary['by_gl'].keys()):
        data = summary['by_gl'][gl_code]
        writer.writerow([
            gl_code,
            data['gl_name'],
            data['budget'],
            data['actual'],
            data['variance'],
            round(data['utilization_percent'], 2)
        ])
    
    # Totals
    writer.writerow([])
    writer.writerow([
        'TOTAL', '', summary['totals']['budget'], summary['totals']['actual'],
        summary['totals']['variance'], round(summary['totals']['utilization_percent'], 2)
    ])
    
    # GL Group Summary
    writer.writerow([])
    writer.writerow(['GL Group Summary'])
    writer.writerow(['GL Group', 'Budget', 'Actual', 'Variance', 'Utilization %'])
    for group_name in sorted(summary['by_group'].keys()):
        data = summary['by_group'][group_name]
        writer.writerow([
            group_name,
            data['budget'],
            data['actual'],
            data['variance'],
            round(data.get('utilization_percent', 0), 2)
        ])
    
    return response


def process_budget_excel(project, excel_file, replace_existing=False):
    """
    Process budget Excel file and create/update budget records
    
    Expected Excel structure:
    GL Code | GL Name | Budget Amount
    """
    try:
        import openpyxl
    except ImportError:
        return 0, ['openpyxl package is not installed. Please contact administrator.']
    
    success_count = 0
    error_messages = []
    
    try:
        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active
        
        # Get or create budget
        if replace_existing:
            budget, created = ProjectBudget.objects.get_or_create(
                project=project,
                defaults={'status': 'active'}
            )
            # Clear existing lines
            budget.lines.all().delete()
        else:
            budget, created = ProjectBudget.objects.get_or_create(
                project=project,
                defaults={'status': 'active'}
            )
        
        total_budget = Decimal('0')
        
        # Process rows (skip header in row 1)
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            try:
                gl_code = row[0]
                gl_name = row[1]
                budget_amount = row[2]
                
                # Validate required fields
                if not gl_code or not budget_amount:
                    error_messages.append(f'Row {row_idx}: Missing GL Code or Budget Amount')
                    continue
                
                # Convert budget amount to Decimal
                try:
                    budget_amount = Decimal(str(budget_amount))
                except:
                    error_messages.append(f'Row {row_idx}: Invalid budget amount format')
                    continue
                
                # Find GL account
                try:
                    gl_account = GLMaster.objects.get(gl_code=str(gl_code).strip())
                except GLMaster.DoesNotExist:
                    error_messages.append(f'Row {row_idx}: GL Code {gl_code} not found')
                    continue
                
                # Create or update budget line
                line, created = ProjectBudgetLine.objects.update_or_create(
                    budget=budget,
                    gl_account=gl_account,
                    defaults={'budget_amount': budget_amount}
                )
                
                total_budget += budget_amount
                success_count += 1
            
            except Exception as e:
                error_messages.append(f'Row {row_idx}: {str(e)}')
        
        # Update total budget
        budget.total_budget_amount = total_budget
        budget.save()
        
    except Exception as e:
        error_messages.append(f'File processing error: {str(e)}')
    
    return success_count, error_messages


@login_required
@require_http_methods(["GET"])
def project_dashboard_cost_summary(request, project_id):
    """Get cost summary for project dashboard (API endpoint)"""
    if not has_cost_analysis_permission(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        project = Project.objects.get(id=project_id, is_active=True)
        analyzer = ProjectCostAnalyzer(project)
        summary = analyzer.get_cost_summary()
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'budget': summary['totals']['budget'],
                'actual': summary['totals']['actual'],
                'variance': summary['totals']['variance'],
                'utilization_percent': round(summary['totals']['utilization_percent'], 2),
            }
        })
    except Project.DoesNotExist:
        return JsonResponse({'error': 'Project not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
