from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render

from accounts import views as account_views
from records import views as record_views
from consent import views as consent_views
from audit import views as audit_views

def home_view(request):
    return render(request, 'index.html', {
        'network': settings.ALGORAND_NETWORK,
        'app_id': settings.ALGORAND_APP_ID
    })

urlpatterns = [
    path('django-admin/', admin.site.urls),
    
    # Home Landing
    path('', home_view, name='home'),

    # Authentication & Accounts (Figure 4.5 & Figure 4.12)
    path('accounts/login/', account_views.login_view, name='login'),
    path('accounts/register/', account_views.register_view, name='register'),
    path('accounts/logout/', account_views.logout_view, name='logout'),
    path('accounts/dashboard/', account_views.dashboard_redirect, name='dashboard_redirect'),
    path('admin/verification/', account_views.admin_verification_view, name='admin_verification'),
    path('admin/provider/<int:provider_id>/toggle/', account_views.toggle_provider_verification, name='toggle_provider_verification'),

    # Dashboards (Figure 4.6 & Figure 4.7)
    path('patient/dashboard/', record_views.patient_dashboard, name='patient_dashboard'),
    path('provider/dashboard/', record_views.provider_dashboard, name='provider_dashboard'),

    # Record Upload & Viewer (Figure 4.8 & Figure 4.10)
    path('records/upload/', record_views.upload_record, name='upload_record'),
    path('records/<uuid:record_id>/view/', record_views.record_detail, name='record_detail'),
    path('records/<uuid:record_id>/download/', record_views.download_record_file, name='download_record_file'),

    # Consent & Access Control (Figure 4.9)
    path('consent/manage/', consent_views.consent_management, name='consent_management'),
    path('consent/request/create/', consent_views.create_access_request, name='create_access_request'),
    path('consent/request/<uuid:request_id>/approve/', consent_views.approve_request, name='approve_request'),
    path('consent/request/<uuid:request_id>/reject/', consent_views.reject_request, name='reject_request'),
    path('consent/permission/<uuid:permission_id>/revoke/', consent_views.revoke_permission, name='revoke_permission'),

    # Audit & Verification Explorer (Figure 4.11)
    path('audit/history/', audit_views.audit_history, name='audit_history'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
