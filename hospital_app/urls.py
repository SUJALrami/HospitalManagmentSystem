from django.urls import path
from hospital_app import views

urlpatterns = [
    # admin
    path('login/', views.custom_login, name='custom_login'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/admin/add-doctor/', views.add_doctor, name='add_doctor'),
    path('dashboard/admin/reports/', views.view_reports, name='view_reports'),
    path('dashboard/admin/add-staff/', views.add_staff, name='add_staff'),

    # recoptionist
    path('dashboard/reception/', views.reception_dashboard, name='reception_dashboard'),
    path('appointment/new/', views.new_appointment, name='new_appointment'),
    path('appointment/arrived/<int:appointment_id>/', views.mark_arrived, name='mark_arrived'),
    path('invoice/pay/<int:invoice_id>/', views.mark_paid, name='mark_paid'),
    path('invoice/pay-cash/<int:invoice_id>/', views.mark_paid, name='mark_paid'),
    # path('invoice/pay-online/<int:invoice_id>/', views.mark_paid_online, name='mark_paid_online'),
    
    # Doctor URLs
    path('dashboard/doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/consult/<int:appointment_id>/', views.consultation, name='consultation'),

    # Patient URLs
    path('register/', views.patient_register, name='patient_register'),
    path('dashboard/patient/', views.patient_dashboard, name='patient_dashboard'),
    path('patient/book/', views.book_appointment, name='book_appointment'),
    path('patient/my-bills/', views.my_bills, name='my_bills'),
    path('patient/invoice/download/<int:invoice_id>/', views.download_invoice_pdf, name='download_invoice_pdf'),

    # payments
    path('checkout/<int:invoice_id>/', views.create_checkout_session, name='create_checkout_session'),
    path('payment-success/<int:invoice_id>/', views.payment_success, name='payment_success'),
]