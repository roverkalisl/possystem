from django.contrib import admin
from django.urls import path
from pos import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('users/', views.user_list, name='user_list'),
    path('users/create/', views.create_user, name='create_user'),
    path('users/edit/<int:user_id>/', views.edit_user, name='edit_user'),

    path('', views.pos_page, name='pos'),
    path('save-sale/', views.save_sale, name='save_sale'),
    path('invoice/<int:sale_id>/', views.invoice_page, name='invoice_page'),

    path('sales-return/', views.sales_return, name='sales_return'),
    path('sale-items/<int:sale_id>/', views.get_sale_items, name='get_sale_items'),
    path('return-receipt/<int:return_id>/', views.return_receipt, name='return_receipt'),

    path('items/', views.item_list, name='item_list'),
    path('add-item/', views.add_item, name='add_item'),
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('stock-history/', views.stock_history, name='stock_history'),

    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/monthly/', views.monthly_report, name='monthly_report'),

    path('gl/', views.gl_list, name='gl_list'),
    path('gl/add/', views.add_gl, name='add_gl'),

    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.create_project, name='create_project'),

    path('project-expenses/', views.project_expense_list, name='project_expense_list'),
    path('project-expenses/add/', views.add_project_expense, name='add_project_expense'),

    path('petty-cash/', views.petty_cash_list, name='petty_cash_list'),
    path('petty-cash/add/', views.add_petty_cash, name='add_petty_cash'),
    path('petty-cash/<int:petty_cash_id>/', views.petty_cash_detail, name='petty_cash_detail'),
    path('petty-cash/<int:petty_cash_id>/add-expense/', views.add_petty_cash_expense, name='add_petty_cash_expense'),

    path('project-income/', views.project_income_list, name='project_income_list'),
    path('project-income/add/', views.add_project_income, name='add_project_income'),

    path('project-profit/', views.project_profit_dashboard, name='project_profit_dashboard'),
    path('project-expense/delete/<int:expense_id>/', views.delete_project_expense, name='delete_project_expense'),
    path('petty-cash-expense/delete/<int:expense_id>/', views.delete_petty_cash_expense, name='delete_petty_cash_expense'),
    path('employees/', views.employee_list, name='employee_list'),
    path('employees/add/', views.add_employee, name='add_employee'),
    path('employees/edit/<int:employee_id>/', views.edit_employee, name='edit_employee'),
    path('petty-cash/delete/<int:petty_cash_id>/', views.delete_petty_cash, name='delete_petty_cash'),
    path('project-invoices/', views.project_invoice_list, name='project_invoice_list'),
    path('project-invoices/add/', views.add_project_invoice, name='add_project_invoice'),
    path('project-invoices/<int:invoice_id>/', views.project_invoice_detail, name='project_invoice_detail'),
    path('project-invoices/<int:invoice_id>/add-payment/', views.add_project_invoice_payment, name='add_project_invoice_payment'),
    path('project-invoice-payment/delete/<int:payment_id>/', views.delete_project_invoice_payment, name='delete_project_invoice_payment'),
    path('project-invoices/delete/<int:invoice_id>/', views.delete_project_invoice, name='delete_project_invoice'),
    path('project-invoices/<int:invoice_id>/print/', views.print_project_invoice, name='print_project_invoice'),
    path('project-invoices/<int:invoice_id>/print/', views.print_project_invoice, name='print_project_invoice'),
    path('project-invoices/<int:invoice_id>/print/', views.print_project_invoice, name='print_project_invoice'),
path('project-invoice-payments/<int:payment_id>/print/', views.print_project_payment_receipt, name='print_project_payment_receipt'),
]