from django.contrib import admin
from django.urls import path
from pos import views

urlpatterns = [
    path('admin/', admin.site.urls),

    # =========================
    # AUTH / DASHBOARD
    # =========================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # =========================
    # USER MANAGEMENT
    # =========================
    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),

    # =========================
    # POS
    # =========================
    path('', views.pos_page, name='pos'),
    path('save-sale/', views.save_sale, name='save_sale'),
    path('invoice/<int:sale_id>/', views.invoice_page, name='invoice_page'),

    # =========================
    # CREDIT RECOVERY
    # =========================
    path('credit-sales/', views.credit_sales_list, name='credit_sales_list'),
    path('credit-sales/<int:sale_id>/recover/', views.add_sale_recovery, name='add_sale_recovery'),
    path('credit-sales/recovery/<int:recovery_id>/print/', views.print_sale_recovery_receipt, name='print_sale_recovery_receipt'),

    # =========================
    # SALES RETURN
    # =========================
    path('sales-return/', views.sales_return, name='sales_return'),
    path('sale-items/<int:sale_id>/', views.get_sale_items, name='get_sale_items'),
    path('return-receipt/<int:return_id>/', views.return_receipt, name='return_receipt'),

    # =========================
    # ITEM MANAGEMENT
    # =========================
    path('items/', views.item_list, name='item_list'),
    path('add-item/', views.add_item, name='add_item'),
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
   # path('items/<int:item_id>/details/', views.get_item_details, name='get_item_details'),
    path('stock-history/', views.stock_history, name='stock_history'),

    # =========================
    # REPORTS
    # =========================
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/monthly/', views.monthly_report, name='monthly_report'),

    # =========================
    # GL MASTER
    # =========================
    path('gl/', views.gl_list, name='gl_list'),
    path('gl/add/', views.add_gl, name='add_gl'),

    # =========================
    # PROJECTS
    # =========================
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.create_project, name='create_project'),
    path('projects/edit/<int:project_id>/', views.edit_project, name='edit_project'),

    # =========================
    # PROJECT EXPENSES
    # =========================
    path('project-expenses/', views.project_expense_list, name='project_expense_list'),
    path('project-expenses/add/', views.add_project_expense, name='add_project_expense'),
    path('project-expenses/edit/<int:expense_id>/', views.edit_project_expense, name='edit_project_expense'),
    path('project-expense/delete/<int:expense_id>/', views.delete_project_expense, name='delete_project_expense'),

    # =========================
    # PETTY CASH
    # =========================
    path('petty-cash/', views.petty_cash_list, name='petty_cash_list'),
    path('petty-cash/add/', views.add_petty_cash, name='add_petty_cash'),
    path('petty-cash/<int:petty_cash_id>/', views.petty_cash_detail, name='petty_cash_detail'),
    path('petty-cash/<int:petty_cash_id>/add-expense/', views.add_petty_cash_expense, name='add_petty_cash_expense'),
    path('petty-cash/edit/<int:petty_cash_id>/', views.edit_petty_cash, name='edit_petty_cash'),
    path('petty-cash/delete/<int:petty_cash_id>/', views.delete_petty_cash, name='delete_petty_cash'),
    path('petty-cash-expense/delete/<int:expense_id>/', views.delete_petty_cash_expense, name='delete_petty_cash_expense'),

    # =========================
    # PETTY CASH APPROVALS
    # =========================
    path('petty-cash-expense-approvals/', views.petty_cash_expense_approvals, name='petty_cash_expense_approvals'),
    path('petty-cash-expenses/<int:expense_id>/approve/', views.approve_petty_cash_expense, name='approve_petty_cash_expense'),
    path('petty-cash-expenses/<int:expense_id>/reject/', views.reject_petty_cash_expense, name='reject_petty_cash_expense'),

    # =========================
    # PROJECT INCOME
    # =========================
    path('project-income/', views.project_income_list, name='project_income_list'),
    path('project-income/add/', views.add_project_income, name='add_project_income'),

    # =========================
    # PROJECT PROFIT
    # =========================
    path('project-profit/', views.project_profit_dashboard, name='project_profit_dashboard'),

    # =========================
    # EMPLOYEES
    # =========================
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/edit/<int:employee_id>/', views.edit_employee, name='edit_employee'),

    # =========================
    # PROJECT INVOICE / PAYMENTS
    # =========================
    path('project-invoices/', views.project_invoice_list, name='project_invoice_list'),
    path('project-invoices/add/', views.add_project_invoice, name='add_project_invoice'),
    path('project-invoices/<int:invoice_id>/', views.project_invoice_detail, name='project_invoice_detail'),
    path('project-invoices/<int:invoice_id>/add-payment/', views.add_project_invoice_payment, name='add_project_invoice_payment'),
    path('project-invoices/<int:invoice_id>/print/', views.print_project_invoice, name='print_project_invoice'),
    path('project-invoices/delete/<int:invoice_id>/', views.delete_project_invoice, name='delete_project_invoice'),
    path('project-invoice-payment/delete/<int:payment_id>/', views.delete_project_invoice_payment, name='delete_project_invoice_payment'),
    path('project-invoice-payments/<int:payment_id>/print/', views.print_project_payment_receipt, name='print_project_payment_receipt'),

    # =========================
    # PROJECT ISSUE APPROVALS
    # =========================
    path('project-issues/approvals/', views.project_issue_approval_list, name='project_issue_approval_list'),
    path('project-issues/<int:sale_id>/approve/', views.approve_project_issue, name='approve_project_issue'),
    path('project-issues/<int:sale_id>/reject/', views.reject_project_issue, name='reject_project_issue'),
]