from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from django.core.signing import Signer, BadSignature
from .models import Ticket

class ValidateTicketView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({"error": "Missing token"}, status=status.HTTP_400_BAD_REQUEST)

        signer = Signer()
        try:
            ticket_id = signer.unsign(token)
        except BadSignature:
            return Response({"error": "Invalid signature or manipulated QR"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ticket = Ticket.objects.get(id=ticket_id)
        except Ticket.DoesNotExist:
            return Response({"error": "Ticket not found"}, status=status.HTTP_404_NOT_FOUND)

        if ticket.is_used:
            return Response({"error": "Ticket already used", "status": "already_used"}, status=status.HTTP_400_BAD_REQUEST)
        
        ticket.is_used = True
        ticket.save()

        return Response({
            "status": "valid",
            "message": "Ticket successfully validated and marked as used.",
            "event": ticket.ticket_type.event.title,
            "buyer": ticket.buyer.username
        }, status=status.HTTP_200_OK)
