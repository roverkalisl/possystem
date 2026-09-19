from django.contrib import admin
from django.urls import path
from pos import views
from pos import cost_analysis_views
from pos import backup_views
from pos import payment_summary_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # =========================
    # AUTH / DASHBOARD
    # =========================
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # =========================
    # DATABASE BACKUP & RESTORE
    # =========================
    path('backup/', backup_views.backup_dashboard, name='backup_dashboard'),
    path('backup/create/', backup_views.create_backup_now, name='create_backup_now'),
    path('backup/history/', backup_views.backup_history, name='backup_history'),
    path('backup/<int:backup_id>/download/', backup_views.download_backup, name='download_backup'),
    path('backup/<int:backup_id>/delete/', backup_views.delete_backup, name='delete_backup'),
    path('backup/restore/', backup_views.restore_database, name='restore_database'),
    path('backup/settings/', backup_views.backup_settings_view, name='backup_settings'),

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
    path('pos/barcode-lookup/', views.barcode_lookup, name='barcode_lookup'),
    path('pos/payment-summary/', payment_summary_views.payment_summary_dashboard, name='payment_summary_dashboard'),
    path('bank-transactions/', views.bank_transactions, name='bank_transactions'),
    path('bank-transactions/<int:transaction_id>/submit/', views.submit_bank_transaction, name='submit_bank_transaction'),
    path('bank-transactions/<int:transaction_id>/approve/', views.approve_bank_transaction, name='approve_bank_transaction'),
    path('bank-transactions/<int:transaction_id>/post/', views.post_bank_transaction, name='post_bank_transaction'),
    path('bank-transactions/<int:transaction_id>/reverse/', views.reverse_bank_transaction, name='reverse_bank_transaction'),
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
    path('items/<int:item_id>/barcode/', views.barcode_management, name='barcode_management'),
    path('items/<int:item_id>/barcode/generate/', views.generate_item_barcode, name='generate_item_barcode'),
    path('items/<int:item_id>/barcode/print/', views.print_item_barcode, name='print_item_barcode'),
    path('items/barcodes/generate-missing/', views.bulk_generate_barcodes, name='bulk_generate_barcodes'),
    path('barcode/test/<str:value>/', views.barcode_test_page, name='barcode_test_page'),
    path('barcode/test/standard/<str:value>/', views.barcode_standard_test, name='barcode_standard_test'),
    path('receive-stock/<int:item_id>/', views.receive_stock, name='receive_stock'),
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
    path('categories/', views.category_list, name='category_list'),
    path('administration/licenses/', views.license_renewal_list, name='license_renewal_list'),
    path('administration/licenses/add/', views.add_license_renewal, name='add_license_renewal'),
    path('administration/licenses/<int:license_id>/edit/', views.edit_license_renewal, name='edit_license_renewal'),
    path('administration/licenses/reports/renewal/', views.license_renewal_report, name='license_renewal_report'),
    path('administration/licenses/reports/expiry/', views.license_expiry_report, name='license_expiry_report'),

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
    path('petty-cash-expenses/', views.petty_cash_expense_list, name='petty_cash_expense_list'),
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
    path('project-transfers/', views.project_transfer_list, name='project_transfer_list'),
    path('project-transfers/add/', views.add_project_transfer, name='add_project_transfer'),

    # =========================
    # PROJECT PROFIT
    # =========================
    path('project-profit/', views.project_profit_dashboard, name='project_profit_dashboard'),
    path('retail-vs-project-profit/', views.retail_vs_project_profit_dashboard, name='retail_vs_project_profit_dashboard'),

    # =========================
    # EMPLOYEES
    # =========================
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/edit/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('labour-allocations/', views.labour_allocation_list, name='labour_allocation_list'),
    path('labour-allocations/add/', views.labour_allocation_form, name='labour_allocation_add'),

    # =========================
    # ATTENDANCE
    # =========================
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('attendance/entry/', views.attendance_entry, name='attendance_entry'),

    # =========================
    # SALARY ADVANCE
    # =========================
    path('salary-advances/', views.salary_advance_list, name='salary_advance_list'),
    path('salary-advances/add/', views.add_salary_advance, name='add_salary_advance'),
    path('salary-advances/<int:advance_id>/edit/', views.edit_salary_advance, name='edit_salary_advance'),
    path('salary-advances/<int:advance_id>/approve/', views.approve_salary_advance, name='approve_salary_advance'),

    # =========================
    # SAFETY SUPPLY
    # =========================
    path('safety-items/', views.safety_item_list, name='safety_item_list'),
    path('safety-items/add/', views.add_safety_item, name='add_safety_item'),
    path('safety-items/<int:issue_id>/edit/', views.edit_safety_item, name='edit_safety_item'),

    # =========================
    # PAYROLL
    # =========================
    path('payroll/', views.payroll_list, name='payroll_list'),
    path('payroll/paysheet/', views.payroll_paysheet, name='payroll_paysheet'),
    path('payroll/preview/', views.payroll_preview_json, name='payroll_preview_json'),
    path('employees/<int:employee_id>/payroll-defaults/', views.employee_payroll_defaults, name='employee_payroll_defaults'),
    path('projects/<int:project_id>/payroll-defaults/', views.project_payroll_defaults, name='project_payroll_defaults'),
    path('payroll/add/', views.payroll_form, name='payroll_add'),
    path('payroll/<int:payroll_id>/edit/', views.payroll_form, name='payroll_edit'),
    path('payroll/<int:payroll_id>/process/', views.payroll_process, name='payroll_process'),
    path('payroll/<int:payroll_id>/entry/', views.payroll_pay_entry, name='payroll_pay_entry'),
    path('payroll/<int:payroll_id>/payslip/', views.payroll_payslip_detail, name='payroll_payslip_detail'),
    path('payroll/<int:payroll_id>/payslip/print/', views.print_payroll_payslip, name='print_payroll_payslip'),
    path('payroll/<int:payroll_id>/approve/', views.approve_payroll, name='approve_payroll'),
    path('payroll/<int:payroll_id>/pay/', views.pay_payroll, name='pay_payroll'),

    # =========================
    # PROJECT INVOICE / PAYMENTS
    # =========================
    path('project-invoices/', views.project_invoice_list, name='project_invoice_list'),
    path('project-invoices/add/', views.add_project_invoice, name='add_project_invoice'),
    path('project-invoices/<int:invoice_id>/edit/', views.edit_project_invoice, name='edit_project_invoice'),
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
    path('petty-cash-expenses/add/', views.add_petty_cash_expense_entry, name='add_petty_cash_expense_entry'),
    
    # Debtors & Creditors
    path("debtors/", views.debtors_list, name="debtors_list"),
    path("creditors/", views.creditors_list, name="creditors_list"),
    
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/add/", views.add_customer, name="add_customer"),
    path("customers/<int:customer_id>/edit/", views.edit_customer, name="edit_customer"),
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("suppliers/add/", views.add_supplier, name="add_supplier"),
    path("suppliers/<int:supplier_id>/edit/", views.edit_supplier, name="edit_supplier"),
    path("supplier-advances/", views.supplier_advance_list, name="supplier_advance_list"),
    path("supplier-advances/add/", views.add_supplier_advance, name="add_supplier_advance"),
    path("supplier-advances/<int:advance_id>/settle/", views.add_supplier_settlement_from_advance, name="add_supplier_settlement_from_advance"),
    path("supplier-advance-summary/", views.supplier_advance_summary, name="supplier_advance_summary"),
    path("supplier-advance-summary/<int:supplier_id>/", views.supplier_advance_summary_detail, name="supplier_advance_summary_detail"),
    path("supplier-payment/", views.supplier_payment, name="supplier_payment"),

    path("supplier-settlements/", views.supplier_settlement_list, name="supplier_settlement_list"),
    path("supplier-settlements/<int:settlement_id>/approve/", views.approve_supplier_settlement, name="approve_supplier_settlement"),
    path("supplier-settlements/<int:settlement_id>/reject/", views.reject_supplier_settlement, name="reject_supplier_settlement"),
    path("purchase-orders/", views.purchase_order_list, name="purchase_order_list"),
    path("purchase-orders/add/", views.add_purchase_order, name="add_purchase_order"),
    path("purchase-orders/<int:po_id>/edit/", views.edit_purchase_order, name="edit_purchase_order"),
    path("purchase-orders/<int:po_id>/approve/", views.approve_purchase_order, name="approve_purchase_order"),
    path("purchase-orders/<int:po_id>/reject/", views.reject_purchase_order, name="reject_purchase_order"),
    path("purchase-orders/<int:po_id>/data/", views.purchase_order_data, name="purchase_order_data"),
    path("purchase-orders/<int:po_id>/print/receipt/", views.print_purchase_order_receipt, name="print_purchase_order_receipt"),
    path("purchase-orders/<int:po_id>/import-items/", views.import_items_from_po, name="import_items_from_po"),
    path("petty-cash-ledger/", views.petty_cash_ledger_report, name="petty_cash_ledger_report"),
    path("supplier-advances/<int:advance_id>/edit/", views.edit_supplier_advance, name="edit_supplier_advance"),
    path("sales-return-list/", views.sales_return_list, name="sales_return_list"),
    
    # =========================
    # GRN (Goods Received Note)
    # =========================
    path("grn/", views.grn_list, name="grn_list"),
    path("grn/create/", views.create_grn, name="create_grn"),
    path("grn/create/<int:po_id>/", views.create_grn, name="create_grn_from_po"),
    path("grn/<int:grn_id>/", views.grn_detail, name="grn_detail"),
    path("grn/<int:grn_id>/update-status/", views.update_grn_status, name="update_grn_status"),
    path("assets/", views.company_asset_list, name="company_asset_list"),
    path("assets/<int:asset_id>/", views.company_asset_detail, name="company_asset_detail"),
    path("assets/<int:asset_id>/edit/", views.edit_company_asset, name="edit_company_asset"),
    path("assets/<int:asset_id>/approve/", views.approve_company_asset, name="approve_company_asset"),
    path("assets/<int:asset_id>/reject/", views.reject_company_asset, name="reject_company_asset"),
    
    # =========================
    # LOGGING & AUDIT
    # =========================
    path("logs/user-activity/", views.user_activity_log, name="user_activity_log"),
    path("logs/audit-trail/", views.audit_trail, name="audit_trail"),
    path("logs/audit/<int:log_id>/", views.audit_detail, name="audit_detail"),
    path("purchase-orders/<int:po_id>/print/", views.print_purchase_order, name="print_purchase_order"),
    # =========================
    # QUOTATIONS
    # =========================
    path('quotations/', views.quotation_list, name='quotation_list'),
    path('quotations/add/', views.create_quotation, name='create_quotation'),
    path('quotations/<int:quotation_id>/edit/', views.create_quotation, name='edit_quotation'),
    path('quotations/<int:quotation_id>/', views.quotation_detail, name='quotation_detail'),
    path('quotations/<int:quotation_id>/print/', views.print_quotation, name='print_quotation'),
    
    # =========================
    # PROJECT COST ANALYSIS
    # =========================
    path('reports/cost-analysis/', cost_analysis_views.project_cost_analysis_list, name='project_cost_analysis_list'),
    path('reports/cost-analysis/<int:project_id>/', cost_analysis_views.project_cost_analysis_detail, name='project_cost_analysis_detail'),
    path('reports/cost-analysis-by-group/', cost_analysis_views.cost_analysis_by_gl_group, name='cost_analysis_by_gl_group'),
    path('reports/gl-master-groups/', cost_analysis_views.gl_master_group_report, name='gl_master_group_report'),
    path('reports/gl-group-project-report/', cost_analysis_views.export_gl_group_project_report, name='gl_group_project_report'),
    path('project/<int:project_id>/cost-summary/', cost_analysis_views.project_dashboard_cost_summary, name='project_dashboard_cost_summary'),
    path('budget/upload/', cost_analysis_views.budget_upload, name='budget_upload'),
    path('project/<int:project_id>/transactions/', cost_analysis_views.transaction_details, name='transaction_details'),
    path('project/<int:project_id>/export/excel/', cost_analysis_views.export_cost_analysis, name='export_cost_analysis'),
    path('project/<int:project_id>/export/csv/', cost_analysis_views.export_cost_analysis_csv, name='export_cost_analysis_csv'),
]