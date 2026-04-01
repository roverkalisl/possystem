from django.contrib import admin
from django.urls import path
from pos import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', views.pos_page, name='pos'),
    path('save-sale/', views.save_sale, name='save_sale'),

    path('invoice/<int:sale_id>/', views.invoice_page, name='invoice_page'),
    path('reports/daily/', views.daily_report, name='daily_report'),
    path('reports/monthly/', views.monthly_report, name='monthly_report'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('add-item/', views.add_item, name='add_item'),
    path('items/', views.item_list, name='item_list'),
    path('edit-item/<int:item_id>/', views.edit_item, name='edit_item'),
    path('stock-history/', views.stock_history, name='stock_history'),

    path('sales-return/', views.sales_return, name='sales_return'),
    path('sale-items/<int:sale_id>/', views.get_sale_items, name='get_sale_items'),
    path('return-receipt/<int:return_id>/', views.return_receipt, name='return_receipt'),
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.create_project, name='create_project'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('project-expenses/', views.project_expense_list, name='project_expense_list'),
    path('project-expenses/add/', views.add_project_expense, name='add_project_expense'),
    path('gl/', views.gl_list, name='gl_list'),
    path('gl/add/', views.add_gl, name='add_gl'),
    path('petty-cash/', views.petty_cash_list, name='petty_cash_list'),
    path('petty-cash/add/', views.add_petty_cash, name='add_petty_cash'),
    path('petty-cash/<int:petty_cash_id>/', views.petty_cash_detail, name='petty_cash_detail'),
    path('petty-cash/<int:petty_cash_id>/add-expense/', views.add_petty_cash_expense, name='add_petty_cash_expense'),
]