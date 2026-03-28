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
    path('sales-return/', views.sales_return, name='sales_return'),
    path('sale-items/<int:sale_id>/', views.get_sale_items, name='get_sale_items'),
    path('return-receipt/<int:return_id>/', views.return_receipt, name='return_receipt'),
]