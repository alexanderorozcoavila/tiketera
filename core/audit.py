from auditlog.registry import auditlog

def register_models_for_audit():
    try:
        from events.models import Event, Venue, Category
        from tickets.models import Ticket, TicketType
        from payments.models import Transaction

        auditlog.register(Event)
        auditlog.register(Venue)
        auditlog.register(Category)
        auditlog.register(Ticket)
        auditlog.register(TicketType)
        auditlog.register(Transaction)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to register models for auditlog: {e}")
