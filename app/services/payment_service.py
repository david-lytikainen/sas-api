import stripe
import os
from flask import current_app
from app.repositories.user_repository import UserRepository
from app.repositories.event_repository import EventRepository
from app.exceptions import UnauthorizedError
from typing import Dict, Any
from datetime import datetime, timezone


class PaymentService:
    @staticmethod
    def _ensure_stripe_key():
        """Ensure Stripe API key is set"""
        if not stripe.api_key:
            stripe.api_key = current_app.config.get("STRIPE_SECRET_KEY")
            if not stripe.api_key:
                raise ValueError("Stripe API key not configured")

    @staticmethod
    def get_stripe_config() -> Dict[str, str]:
        """Get Stripe publishable key for frontend"""
        return {
            "publishable_key": current_app.config.get("STRIPE_PUBLISHABLE_KEY", "")
        }

    @staticmethod
    def create_checkout_session(event_id: int, user_id: int) -> Dict[str, Any]:
        """Create a Stripe checkout session for event registration"""
        try:
            # Ensure Stripe API key is set
            PaymentService._ensure_stripe_key()
            
            # Get event and user details
            event = EventRepository.get_event(event_id)
            if not event:
                return {"error": "Event not found"}, 404

            user = UserRepository.find_by_id(user_id)
            if not user:
                return {"error": "User not found"}, 404

            # Calculate price in cents (Stripe uses cents)
            price_in_cents = int(float(event.price_per_person) * 100)

            # Get client URL for redirects
            client_url = current_app.config.get("CLIENT_URL", "http://localhost:3000")

            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": f"Event Registration: {event.name}",
                                "description": f"Registration for {event.name} on {event.starts_at.strftime('%B %d, %Y at %I:%M %p')}",
                            },
                            "unit_amount": price_in_cents,
                        },
                        "quantity": 1,
                    }
                ],
                customer_email=user.email,
                client_reference_id=str(user_id),  # To identify the user in webhook
                metadata={
                    "event_id": str(event_id),
                    "user_id": str(user_id),
                    "event_name": event.name,
                },
                success_url=f"{client_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{client_url}/payment/cancelled",
            )

            return {"session_id": checkout_session.id}, 200

        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating checkout session: {str(e)}")
            return {"error": "Payment processing error"}, 500
        except Exception as e:
            current_app.logger.error(f"Error creating checkout session: {str(e)}")
            return {"error": "Internal server error"}, 500

    @staticmethod
    def handle_webhook_event(payload: str, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            # Ensure Stripe API key is set
            PaymentService._ensure_stripe_key()
            
            webhook_secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")
            if not webhook_secret:
                current_app.logger.error("Stripe webhook secret not configured")
                return {"error": "Webhook secret not configured"}, 500

            # In development mode, allow bypassing signature verification for testing
            is_development = current_app.config.get("DEBUG", False)
            
            # Check if this is a development/test webhook
            is_test_webhook = (
                is_development and 
                (webhook_secret == "whsec_test_development_secret" or 
                 signature.startswith("t=") and "v1=" in signature)
            )
            
            if is_test_webhook:
                # For development testing, parse payload directly
                current_app.logger.info("Development mode: bypassing webhook signature verification")
                try:
                    event = stripe.util.json.loads(payload)
                except:
                    # Fallback to regular JSON parsing
                    import json
                    event = json.loads(payload)
            else:
                # Verify webhook signature in production
                event = stripe.Webhook.construct_event(
                    payload, signature, webhook_secret
                )

            current_app.logger.info(f"=== WEBHOOK DEBUG: Received Stripe webhook event: {event['type']} ===")
            current_app.logger.info(f"Event ID: {event.get('id')}")
            current_app.logger.info(f"Event Data Keys: {list(event.get('data', {}).keys())}")

            # Handle successful payment
            if event["type"] == "checkout.session.completed":
                current_app.logger.info("Processing checkout.session.completed")
                session = event["data"]["object"]
                return PaymentService._handle_successful_payment(session)

            # Handle successful PaymentIntent (for native forms)
            elif event["type"] == "payment_intent.succeeded":
                current_app.logger.info("Processing payment_intent.succeeded")
                payment_intent = event["data"]["object"]
                result = PaymentService._handle_successful_payment_intent(payment_intent)
                current_app.logger.info(f"PaymentIntent handler result: {result}")
                return result

            # Handle failed payment
            elif event["type"] == "checkout.session.async_payment_failed":
                current_app.logger.info("Processing checkout.session.async_payment_failed")
                session = event["data"]["object"]
                return PaymentService._handle_failed_payment(session)

            current_app.logger.info(f"Unhandled webhook event type: {event['type']}")
            return {"status": "success"}, 200

        except stripe.error.SignatureVerificationError as e:
            current_app.logger.error(f"Invalid webhook signature: {str(e)}")
            return {"error": "Invalid signature"}, 400
        except ValueError as e:
            current_app.logger.error(f"Invalid webhook payload: {str(e)}")
            return {"error": "Invalid payload"}, 400
        except Exception as e:
            current_app.logger.error(f"Error handling webhook: {str(e)}")
            return {"error": "Internal server error"}, 500

    @staticmethod
    def _handle_successful_payment(session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment completion"""
        try:
            # Extract event and user info from session metadata
            event_id = int(session["metadata"]["event_id"])
            user_id = int(session["metadata"]["user_id"])
            
            current_app.logger.info(f"Processing successful payment for user {user_id}, event {event_id}")

            # Import here to avoid circular imports
            from app.services.event_service import EventService
            
            # Register the user for the event (bypass payment check since payment is complete)
            result = EventService.register_for_event(
                event_id, user_id, join_waitlist=False, payment_completed=True
            )

            if "error" in result:
                current_app.logger.error(f"Failed to register user after payment: {result['error']}")
                return {"error": "Registration failed after payment"}, 500

            current_app.logger.info(f"Successfully registered user {user_id} for event {event_id} after payment")
            return {"status": "success"}, 200

        except Exception as e:
            current_app.logger.error(f"Error handling successful payment: {str(e)}")
            return {"error": "Error processing successful payment"}, 500

    @staticmethod
    def _handle_successful_payment_intent(payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful PaymentIntent completion"""
        try:
            current_app.logger.info(f"=== WEBHOOK DEBUG: Payment Intent Handler Called ===")
            current_app.logger.info(f"PaymentIntent ID: {payment_intent.get('id')}")
            current_app.logger.info(f"PaymentIntent Status: {payment_intent.get('status')}")
            current_app.logger.info(f"PaymentIntent Metadata: {payment_intent.get('metadata', {})}")
            
            # Extract event and user info from PaymentIntent metadata
            metadata = payment_intent.get("metadata", {})
            if not metadata.get("event_id") or not metadata.get("user_id"):
                current_app.logger.error(f"Missing required metadata in PaymentIntent: {metadata}")
                return {"error": "Missing event or user metadata"}, 400
            
            event_id = int(metadata["event_id"])
            user_id = int(metadata["user_id"])
            
            current_app.logger.info(f"Processing successful PaymentIntent for user {user_id}, event {event_id}")

            # Import here to avoid circular imports
            from app.services.event_service import EventService
            from app.repositories.event_waitlist_repository import EventWaitlistRepository
            
            # Check if user is on waitlist first
            on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
            current_app.logger.info(f"User {user_id} on waitlist for event {event_id}: {bool(on_waitlist)}")
            
            if on_waitlist:
                # User is on waitlist - try to register them from waitlist
                current_app.logger.info(f"Registering user {user_id} from waitlist for event {event_id}")
                result = EventService.register_from_waitlist(
                    event_id, user_id, payment_completed=True
                )
            else:
                # User is registering normally
                current_app.logger.info(f"Registering user {user_id} normally for event {event_id}")
                result = EventService.register_for_event(
                    event_id, user_id, join_waitlist=False, payment_completed=True
                )

            current_app.logger.info(f"Registration result: {result}")

            if "error" in result:
                current_app.logger.error(f"Failed to register user after PaymentIntent: {result['error']}")
                return {"error": "Registration failed after payment"}, 500

            current_app.logger.info(f"Successfully registered user {user_id} for event {event_id} after PaymentIntent")
            return {"status": "success"}, 200

        except Exception as e:
            current_app.logger.error(f"Error handling successful PaymentIntent: {str(e)}")
            import traceback
            current_app.logger.error(f"Full traceback: {traceback.format_exc()}")
            return {"error": "Error processing successful payment"}, 500

    @staticmethod
    def _handle_failed_payment(session: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment"""
        try:
            event_id = session["metadata"]["event_id"]
            user_id = session["metadata"]["user_id"]
            
            current_app.logger.warning(f"Payment failed for user {user_id}, event {event_id}")
            
            # Could implement additional logic here like sending notification emails
            # or updating user records about failed payment attempts
            
            return {"status": "payment_failed"}, 200

        except Exception as e:
            current_app.logger.error(f"Error handling failed payment: {str(e)}")
            return {"error": "Error processing failed payment"}, 500

    @staticmethod
    def verify_payment_session(session_id: str) -> Dict[str, Any]:
        """Verify a payment session and return its status"""
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            
            # If payment is complete, attempt to ensure the user is registered
            if session.payment_status == "paid":
                try:
                    event_id = int(session.metadata.get("event_id")) if session.metadata.get("event_id") else None
                    user_id = int(session.metadata.get("user_id")) if session.metadata.get("user_id") else None

                    if event_id and user_id:
                        from app.repositories.event_attendee_repository import EventAttendeeRepository
                        already_registered = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)

                        if not already_registered:
                            from app.services.event_service import EventService
                            current_app.logger.info(
                                f"verify_payment_session: auto-registering user {user_id} for event {event_id} since payment is paid and no registration found"
                            )
                            EventService.register_for_event(event_id, user_id, join_waitlist=False, payment_completed=True)
                except Exception as e:
                    current_app.logger.error(f"verify_payment_session: error while auto-registering after payment: {str(e)}")

            return {
                "payment_status": session.payment_status,
                "session_status": session.status,
                "metadata": session.metadata
            }, 200

        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error verifying payment session: {str(e)}")
            return {"error": "Error verifying payment"}, 500

    @staticmethod
    def create_payment_intent(event_id: int, user_id: int) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent for native payment form"""
        try:
            # Ensure Stripe API key is set
            PaymentService._ensure_stripe_key()
            
            # Get event and user details
            event = EventRepository.get_event(event_id)
            if not event:
                return {"error": "Event not found"}, 404

            user = UserRepository.find_by_id(user_id)
            if not user:
                return {"error": "User not found"}, 404

            # Calculate price in cents (Stripe uses cents)
            price_in_cents = int(float(event.price_per_person) * 100)

            # Create PaymentIntent - restrict to card payments only
            intent = stripe.PaymentIntent.create(
                amount=price_in_cents,
                currency='usd',
                metadata={
                    "event_id": str(event_id),
                    "user_id": str(user_id),
                    "event_name": event.name,
                    "customer_email": user.email,  # Store email in metadata instead
                },
                description=f"Event Registration: {event.name}",
                payment_method_types=['card'],  # Only allow card payments
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id
            }, 200

        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating PaymentIntent: {str(e)}")
            return {"error": "Payment processing error"}, 500
        except Exception as e:
            current_app.logger.error(f"Error creating PaymentIntent: {str(e)}")
            return {"error": "Internal server error"}, 500

    @staticmethod
    def create_venmo_payment_intent(event_id: int, user_id: int) -> Dict[str, Any]:
        """Create a Stripe PaymentIntent specifically for Venmo payments"""
        try:
            # Ensure Stripe API key is set
            PaymentService._ensure_stripe_key()
            
            # Get event and user details
            event = EventRepository.get_event(event_id)
            if not event:
                return {"error": "Event not found"}, 404

            user = UserRepository.find_by_id(user_id)
            if not user:
                return {"error": "User not found"}, 404

            # Calculate price in cents (Stripe uses cents)
            price_in_cents = int(float(event.price_per_person) * 100)

            # Get client URL for redirects
            client_url = current_app.config.get("CLIENT_URL", "http://localhost:3000")

            # Create PaymentIntent with card support (Venmo not available in test mode)
            # In production, you would use payment_method_types=['card', 'venmo'] if Venmo is enabled
            intent = stripe.PaymentIntent.create(
                amount=price_in_cents,
                currency='usd',
                metadata={
                    "event_id": str(event_id),
                    "user_id": str(user_id),
                    "event_name": event.name,
                    "customer_email": user.email,
                    "payment_method": "venmo",
                },
                description=f"Event Registration: {event.name}",
                payment_method_types=['card'],  # Use card for testing, Venmo not available in test mode
                # Configure for mobile-optimized flow
                confirmation_method='automatic',
                confirm=False,
            )

            return {
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "venmo_deep_link": PaymentService._generate_venmo_deep_link(
                    intent.id, price_in_cents, event.name, user_id
                )
            }, 200

        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating Venmo PaymentIntent: {str(e)}")
            return {"error": "Payment processing error"}, 500
        except Exception as e:
            current_app.logger.error(f"Error creating Venmo PaymentIntent: {str(e)}")
            return {"error": "Internal server error"}, 500

    @staticmethod
    def _generate_venmo_deep_link(payment_intent_id: str, amount_cents: int, event_name: str, user_id: int) -> Dict[str, str]:
        """Generate Venmo deep link for iOS and fallback URLs"""
        try:
            # Get client URL for web fallback
            client_url = current_app.config.get("CLIENT_URL", "http://localhost:3000")
            
            # Format amount for Venmo (dollars, not cents)
            amount_dollars = amount_cents / 100
            
            # Create note for Venmo transaction
            note = f"Event Registration: {event_name}"
            
            # Venmo deep link format for iOS
            # Note: In production, you would use actual Venmo business account details
            venmo_username = current_app.config.get("VENMO_USERNAME", "sas-events-test")
            
            # iOS Venmo app deep link
            ios_deep_link = f"venmo://paycharge?txn=pay&recipients={venmo_username}&amount={amount_dollars}&note={note}&payment_intent_id={payment_intent_id}"
            
            # Web fallback URL that will redirect to mobile app if available
            web_fallback = f"https://venmo.com/{venmo_username}?txn=pay&amount={amount_dollars}&note={note}&return_url={client_url}/payment/venmo/success/{payment_intent_id}"
            
            # Custom payment completion URL
            success_url = f"{client_url}/payment/venmo/success/{payment_intent_id}"
            cancel_url = f"{client_url}/payment/venmo/cancelled"
            
            return {
                "ios_deep_link": ios_deep_link,
                "web_fallback": web_fallback,
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
        except Exception as e:
            current_app.logger.error(f"Error generating Venmo deep link: {str(e)}")
            return {
                "ios_deep_link": "",
                "web_fallback": "",
                "success_url": f"{client_url}/payment/cancelled",
                "cancel_url": f"{client_url}/payment/cancelled"
            }

    @staticmethod
    def confirm_venmo_payment(payment_intent_id: str, venmo_transaction_id: str = None) -> Dict[str, Any]:
        """Confirm a Venmo payment after user completes payment in Venmo app"""
        try:
            PaymentService._ensure_stripe_key()
            
            # Retrieve the PaymentIntent
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            current_app.logger.info(f"Confirming Venmo payment for PaymentIntent: {payment_intent_id}")
            
            # In a real implementation, you would verify the Venmo transaction
            # For now, we'll simulate confirmation
            if payment_intent.status == 'requires_confirmation':
                # Confirm the payment
                confirmed_intent = stripe.PaymentIntent.confirm(
                    payment_intent_id,
                    payment_method_data={
                        'type': 'venmo',
                    }
                )
                
                return {
                    "status": confirmed_intent.status,
                    "payment_intent_id": confirmed_intent.id
                }, 200
            elif payment_intent.status == 'succeeded':
                return {
                    "status": "succeeded",
                    "payment_intent_id": payment_intent.id,
                    "message": "Payment already completed"
                }, 200
            else:
                return {
                    "error": f"Payment in unexpected status: {payment_intent.status}"
                }, 400
                
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error confirming Venmo payment: {str(e)}")
            return {"error": "Payment confirmation error"}, 500
        except Exception as e:
            current_app.logger.error(f"Error confirming Venmo payment: {str(e)}")
            return {"error": "Internal server error"}, 500

    @staticmethod
    def simulate_venmo_payment_completion(payment_intent_id: str) -> Dict[str, Any]:
        """Simulate Venmo payment completion for testing purposes"""
        try:
            PaymentService._ensure_stripe_key()
            
            # Retrieve the PaymentIntent to get metadata
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            current_app.logger.info(f"Simulating Venmo payment completion for: {payment_intent_id}")
            
            # Extract event and user info from PaymentIntent metadata
            metadata = payment_intent.metadata
            if not metadata.get("event_id") or not metadata.get("user_id"):
                return {"error": "Missing event or user metadata"}, 400
            
            event_id = int(metadata["event_id"])
            user_id = int(metadata["user_id"])
            
            # Import here to avoid circular imports
            from app.services.event_service import EventService
            from app.repositories.event_waitlist_repository import EventWaitlistRepository
            
            # Check if user is on waitlist first
            on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
            
            if on_waitlist:
                # User is on waitlist - try to register them from waitlist
                result = EventService.register_from_waitlist(
                    event_id, user_id, payment_completed=True
                )
            else:
                # User is registering normally
                result = EventService.register_for_event(
                    event_id, user_id, join_waitlist=False, payment_completed=True
                )

            if "error" in result:
                current_app.logger.error(f"Failed to register user after Venmo payment: {result['error']}")
                return {"error": "Registration failed after payment"}, 500

            current_app.logger.info(f"Successfully registered user {user_id} for event {event_id} after Venmo payment")
            
            return {
                "status": "success",
                "message": "Venmo payment completed and user registered",
                "registration": result
            }, 200
            
        except Exception as e:
            current_app.logger.error(f"Error simulating Venmo payment completion: {str(e)}")
            return {"error": "Error processing Venmo payment"}, 500

    @staticmethod
    def find_payment_for_registration(event_id: int, user_id: int) -> Dict[str, Any]:
        """Find the payment information for a specific registration"""
        try:
            PaymentService._ensure_stripe_key()
            
            # Search for PaymentIntents with matching metadata
            payment_intents = stripe.PaymentIntent.list(
                limit=100,  # Adjust limit as needed
            )
            
            for pi in payment_intents.data:
                metadata = getattr(pi, 'metadata', {})
                if (metadata.get('event_id') == str(event_id) and 
                    metadata.get('user_id') == str(user_id) and 
                    pi.status == 'succeeded'):
                    
                    # Get the charge ID for refunding by retrieving the full PaymentIntent
                    charge_id = None
                    try:
                        full_pi = stripe.PaymentIntent.retrieve(pi.id, expand=['charges'])
                        if full_pi.charges and full_pi.charges.data:
                            charge_id = full_pi.charges.data[0].id
                    except Exception as e:
                        current_app.logger.warning(f"Could not retrieve charges for PaymentIntent {pi.id}: {e}")
                    
                    return {
                        "payment_intent_id": pi.id,
                        "charge_id": charge_id,
                        "amount": pi.amount,
                        "currency": pi.currency,
                        "status": pi.status,
                        "created": pi.created
                    }
            
            # Also search checkout sessions as fallback
            sessions = stripe.checkout.Session.list(limit=100)
            for session in sessions.data:
                metadata = getattr(session, 'metadata', {})
                if (metadata.get('event_id') == str(event_id) and 
                    metadata.get('user_id') == str(user_id) and 
                    session.payment_status == 'paid'):
                    
                    return {
                        "session_id": session.id,
                        "payment_intent_id": session.payment_intent,
                        "amount": session.amount_total,
                        "currency": session.currency,
                        "status": session.payment_status,
                        "created": session.created
                    }
            
            return None
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error finding payment: {str(e)}")
            return None
        except Exception as e:
            current_app.logger.error(f"Error finding payment: {str(e)}")
            return None

    @staticmethod
    def process_refund(event_id: int, user_id: int, reason: str = "requested_by_customer") -> Dict[str, Any]:
        """Process a refund for a registration"""
        try:
            PaymentService._ensure_stripe_key()
            
            # Find the payment for this registration
            payment_info = PaymentService.find_payment_for_registration(event_id, user_id)
            if not payment_info:
                return {"error": "No payment found for this registration"}, 404
            
            # Get event details for refund description
            event = EventRepository.get_event(event_id)
            user = UserRepository.find_by_id(user_id)
            
            # Create refund using PaymentIntent ID
            refund = stripe.Refund.create(
                payment_intent=payment_info['payment_intent_id'],
                reason=reason,
                metadata={
                    "event_id": str(event_id),
                    "user_id": str(user_id),
                    "event_name": event.name if event else "Unknown Event",
                    "user_email": user.email if user else "Unknown User",
                    "refund_reason": reason
                }
            )
            
            current_app.logger.info(f"Refund processed: {refund.id} for user {user_id}, event {event_id}")
            
            return {
                "refund_id": refund.id,
                "amount": refund.amount,
                "currency": refund.currency,
                "status": refund.status,
                "reason": refund.reason
            }, 200
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error processing refund: {str(e)}")
            return {"error": f"Refund processing error: {str(e)}"}, 500
        except Exception as e:
            current_app.logger.error(f"Error processing refund: {str(e)}")
            return {"error": "Internal server error"}, 500

    @staticmethod
    def get_refund_policy_info(event_id: int) -> Dict[str, Any]:
        """Get refund policy information for a specific event"""
        try:
            event = EventRepository.get_event(event_id)
            if not event:
                return {"error": "Event not found"}, 404

            # Calculate time until event starts
            now = datetime.now(timezone.utc)
            event_start = event.starts_at.replace(tzinfo=timezone.utc) if event.starts_at.tzinfo is None else event.starts_at
            hours_until_event = (event_start - now).total_seconds() / 3600

            # Define refund policy
            refund_eligible = hours_until_event > 24  # No refunds within 24 hours
            refund_percentage = 100 if hours_until_event > 72 else 50  # 100% if >72hrs, 50% if 24-72hrs

            policy_info = {
                "refund_eligible": refund_eligible,
                "refund_percentage": refund_percentage,
                "hours_until_event": max(0, hours_until_event),
                "policy_message": PaymentService._get_refund_policy_message(hours_until_event)
            }

            return policy_info, 200

        except Exception as e:
            current_app.logger.error(f"Error getting refund policy for event {event_id}: {str(e)}")
            return {"error": "Unable to get refund policy"}, 500

    @staticmethod
    def check_refund_policy(event, registration):
        """Check if a registration is eligible for refund based on event timing"""
        try:
            # Calculate time until event starts
            now = datetime.now(timezone.utc)
            event_start = event.starts_at.replace(tzinfo=timezone.utc) if event.starts_at.tzinfo is None else event.starts_at
            hours_until_event = (event_start - now).total_seconds() / 3600

            # Define refund policy - more generous for testing
            refund_eligible = hours_until_event > 2  # Allow refunds until 2 hours before event
            refund_percentage = 100 if hours_until_event > 24 else 75  # 100% if >24hrs, 75% if 2-24hrs

            return {
                "refund_eligible": refund_eligible,
                "refund_percentage": refund_percentage,
                "hours_until_event": max(0, hours_until_event),
                "policy_message": PaymentService._get_refund_policy_message(hours_until_event)
            }

        except Exception as e:
            current_app.logger.error(f"Error checking refund policy: {str(e)}")
            return {
                "refund_eligible": False,
                "refund_percentage": 0,
                "policy_message": "Unable to determine refund eligibility"
            }

    @staticmethod
    def _get_refund_policy_message(hours_until_event: float) -> str:
        """Get human-readable refund policy message"""
        if hours_until_event > 24:
            return "Full refund available (more than 24 hours before event)"
        elif hours_until_event > 2:
            return "75% refund available (2-24 hours before event)"
        else:
            return "No refund available (less than 2 hours before event)" 