from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import AuditEvent

@login_required
def audit_history(request):
    event_type = request.GET.get('event_type')
    chain_filter = request.GET.get('chain_filter')
    search_query = request.GET.get('q', '').strip()

    events = AuditEvent.objects.select_related('actor', 'record').all()

    # If patient, show events involving patient or patient's records
    if request.user.is_patient_user():
        patient = getattr(request.user, 'patient_profile', None)
        events = events.filter(record__patient=patient) | events.filter(actor=request.user)
    elif request.user.is_provider_user() and not request.user.is_superuser:
        provider = getattr(request.user, 'provider_profile', None)
        events = events.filter(record__creator=provider) | events.filter(actor=request.user)

    if event_type:
        events = events.filter(event_type=event_type)

    if chain_filter == 'on_chain':
        events = events.filter(is_on_chain=True)
    elif chain_filter == 'off_chain':
        events = events.filter(is_on_chain=False)

    if search_query:
        events = events.filter(description__icontains=search_query)

    total_events_count = events.count()
    on_chain_count = events.filter(is_on_chain=True).count()
    off_chain_count = events.filter(is_on_chain=False).count()

    events_list = events.order_by('-timestamp')[:100]

    context = {
        'events': events_list,
        'event_types': AuditEvent.EVENT_TYPE_CHOICES,
        'selected_event_type': event_type,
        'chain_filter': chain_filter,
        'search_query': search_query,
        'total_events_count': total_events_count,
        'on_chain_count': on_chain_count,
        'off_chain_count': off_chain_count,
    }
    return render(request, 'audit/audit_history.html', context)
