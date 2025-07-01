from datetime import datetime, timezone, timedelta
from decimal import Decimal
import math
import random
from flask import current_app
from app.repositories.event_repository import EventRepository
from app.repositories.user_repository import UserRepository
from app.repositories.event_attendee_repository import EventAttendeeRepository
from app.repositories.event_waitlist_repository import EventWaitlistRepository
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.models.enums import EventStatus, Gender, RegistrationStatus
from app.models import Event
from typing import List


class EventService:
    @staticmethod
    def get_events() -> List[Event]:
        return EventRepository.get_events()

    @staticmethod
    def get_events_for_user(user_id):
        user = UserRepository.find_by_id(user_id)
        if not user:
            return ({"error": "User not found"}), 404

        events = EventRepository.get_events()
        return [event.to_dict() for event in events]

    @staticmethod
    def create_event(data, user_id):
        user = UserRepository.find_by_id(user_id)

        if user.role_id not in [2, 3]:  # 2 = Organizer, 3 = Admin
            raise UnauthorizedError()

        required_fields = [
            "name",
            "starts_at",
            "address",
            "max_capacity",
            "price_per_person",
        ]
        missing = [f for f in required_fields if f not in data]
        if missing:
            raise MissingFieldsError(missing)

        event = EventRepository.create_event(
            {
                "name": data["name"],
                "description": data["description"],
                "creator_id": user_id,
                "starts_at": datetime.fromisoformat(
                    data["starts_at"].replace("Z", "+00:00")
                ).astimezone(timezone.utc),
                "address": data["address"],
                "max_capacity": data["max_capacity"],
                "status": EventStatus.REGISTRATION_OPEN.value,
                "price_per_person": Decimal(str(data["price_per_person"])),
                "registration_deadline": datetime.fromisoformat(
                    data["starts_at"].replace("Z", "+00:00")
                ).astimezone(timezone.utc),
            }
        )

        return event

    @staticmethod
    def cleanup_user_registration_conflicts(event_id: int, user_id: int):
        """Clean up any potential registration conflicts for a user"""
        try:
            # Remove any duplicate registrations (shouldn't happen but just in case)
            existing_registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
            if existing_registration:
                current_app.logger.warning(f"Found existing registration for user {user_id}, event {event_id} - removing duplicate")
                EventAttendeeRepository.delete(event_id, user_id)
            
            # Remove from waitlist if they're on it (they want to register directly now)
            on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
            if on_waitlist:
                current_app.logger.info(f"Removing user {user_id} from waitlist for event {event_id} to allow direct registration")
                EventWaitlistRepository.remove_from_waitlist(event_id, user_id)
                
        except Exception as e:
            current_app.logger.error(f"Error cleaning up registration conflicts for user {user_id}, event {event_id}: {str(e)}")

    @staticmethod
    def register_for_event(event_id: int, user_id: int, join_waitlist: bool = False, payment_completed: bool = False):
        current_app.logger.info(f"Registration attempt: User {user_id} for event {event_id}, join_waitlist={join_waitlist}, payment_completed={payment_completed}")
        
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}
        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {"error": "Event is not open for registration"}
        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            current_app.logger.warning(f"User {user_id} already registered for event {event_id}")
            return {"error": "You are already registered for this event"}
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            current_app.logger.warning(f"User {user_id} already on waitlist for event {event_id}")
            return {"error": "You are already on the waitlist for this event"}

        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT]
        )
        
        # Get user info for gender checks
        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": f"User with ID {user_id} not found"}
            
        same_gender_count = (
            EventAttendeeRepository.count_by_event_and_status_and_gender(
                event_id,
                [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT],
                user.gender,
            )
        )
        
        # Check if event is full overall or for this gender
        event_full = attendee_count >= event.max_capacity
        gender_full = same_gender_count >= math.floor(event.max_capacity * 0.6)
        
        current_app.logger.info(f"Capacity check for user {user_id}, event {event_id}: attendees={attendee_count}/{event.max_capacity}, gender={same_gender_count}/{math.floor(event.max_capacity * 0.6)}, event_full={event_full}, gender_full={gender_full}")
        
        # If event is full and user wants to join waitlist, don't require payment yet
        if (event_full or gender_full) and join_waitlist:
            current_app.logger.info(f"User {user_id} joining waitlist for event {event_id} (event_full={event_full}, gender_full={gender_full})")
            return EventService.join_event_waitlist(event_id, user_id)
        elif event_full or gender_full:
            current_app.logger.warning(f"User {user_id} blocked from registering for event {event_id} - event full (event_full={event_full}, gender_full={gender_full})")
            return {
                "error": "Event is currently full" + (" for this gender" if gender_full and not event_full else ""),
                "waitlist_available": True,
            }

        # Only require payment if there's actually a spot available
        event_price = float(event.price_per_person)
        if event_price > 0 and not payment_completed:
            current_app.logger.info(f"Payment required for user {user_id}, event {event_id}, price=${event_price}")
            return {
                "error": "Payment required for this event",
                "requires_payment": True,
                "price": event_price
            }

        # Generate random 4-digit PIN
        pin = "".join(random.choices("0123456789", k=4))

        # Determine payment status
        payment_status = 'paid' if payment_completed or event_price == 0 else 'waived'

        try:
            EventAttendeeRepository.register_for_event(
                {
                    "event_id": event_id,
                    "user_id": user_id,
                    "status": RegistrationStatus.REGISTERED,
                    "pin": pin,
                    "payment_status": payment_status,
                }
            )
            current_app.logger.info(f"Successfully registered user {user_id} for event {event_id} with PIN {pin}")
            return {"message": "Successfully registered for event"}
        except Exception as e:
            current_app.logger.error(f"Failed to register user {user_id} for event {event_id}: {str(e)}")
            return {"error": "Registration failed. Please try again."}

    @staticmethod
    def register_from_waitlist(event_id: int, user_id: int, payment_completed: bool = False):
        """Register a user from waitlist to main event (with payment if required)"""
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}

        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {"error": "Event is not open for registration"}

        # Check if user is actually on the waitlist
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if not on_waitlist:
            return {"error": "You are not on the waitlist for this event"}

        # Check if there's actually a spot available
        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT]
        )
        
        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": f"User with ID {user_id} not found"}
            
        same_gender_count = (
            EventAttendeeRepository.count_by_event_and_status_and_gender(
                event_id,
                [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT],
                user.gender,
            )
        )
        
        # Check if there's still a spot available
        event_full = attendee_count >= event.max_capacity
        gender_full = same_gender_count >= math.floor(event.max_capacity * 0.6)
        
        if event_full or gender_full:
            return {
                "error": "No spots currently available" + (" for this gender" if gender_full and not event_full else ""),
                "stay_on_waitlist": True
            }

        # For paid events, register with pending payment status instead of requiring immediate payment
        event_price = float(event.price_per_person)
        pin = "".join(random.choices("0123456789", k=4))
        
        # Determine payment status and due date
        if event_price > 0 and not payment_completed:
            payment_status = 'pending'
            payment_due_date = datetime.now() + timedelta(days=30)  # 30 days to pay at event
        else:
            payment_status = 'paid' if payment_completed else 'waived'
            payment_due_date = None

        try:
            EventAttendeeRepository.register_for_event(
                {
                    "event_id": event_id,
                    "user_id": user_id,
                    "status": RegistrationStatus.PENDING_PAYMENT if payment_status == 'pending' else RegistrationStatus.REGISTERED,
                    "pin": pin,
                    "payment_status": payment_status,
                    "payment_due_date": payment_due_date,
                }
            )
            EventWaitlistRepository.remove_from_waitlist(event_id, user_id)
            
            # Send notification email for pending payment
            if payment_status == 'pending':
                try:
                    from app.utils.email import send_waitlist_to_event_notification
                    send_waitlist_to_event_notification(user, event)
                    current_app.logger.info(f"Sent waitlist-to-event notification to user {user_id}")
                except Exception as email_error:
                    current_app.logger.error(f"Failed to send waitlist-to-event email to user {user_id}: {str(email_error)}")
            
            message = "Successfully registered from waitlist"
            if payment_status == 'pending':
                message += ". You will pay at the event."
            
            return {"message": message, "pin": pin, "payment_status": payment_status}
        except Exception as e:
            current_app.logger.error(f"Error registering user {user_id} from waitlist for event {event_id}: {str(e)}")
            return {"error": "Failed to register from waitlist"}

    @staticmethod
    def join_event_waitlist(event_id: int, user_id: int):
        """Adds a user to the waitlist for an event."""
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}

        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {
                "error": "Event is not open for registration for waitlisting"
            }  # Or a different message

        # Double check if user is already registered (should have been caught earlier)
        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            return {
                "error": "You are already registered for this event, cannot join waitlist"
            }

        # Check if user is already on the waitlist
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            return {"error": "You are already on the waitlist for this event"}
        try:
            EventWaitlistRepository.add_to_waitlist(event_id, user_id)
            return {"message": "Successfully joined the waitlist for the event"}
        except Exception as e:
            # Log the exception e
            return {"error": f"Could not join waitlist: {str(e)}"}

    @staticmethod
    def cancel_registration(event_id: int, user_id: int, process_refund: bool = True):
        try:
            current_app.logger.info(f"Starting cancel_registration: event_id={event_id}, user_id={user_id}, process_refund={process_refund}")
            
            # Check if user is on waitlist first
            on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
            current_app.logger.info(f"Waitlist check result: {bool(on_waitlist)}")
            
            if on_waitlist:
                removed = EventWaitlistRepository.remove_from_waitlist(event_id, user_id)
                if removed:
                    current_app.logger.info(f"Successfully removed user {user_id} from waitlist for event {event_id}")
                    return {"message": "Successfully removed from waitlist"}
                else:
                    current_app.logger.error(f"Failed to remove user {user_id} from waitlist for event {event_id}")
                    return {"error": "Failed to remove from waitlist"}

            # If not on waitlist, proceed to cancel registration as attendee
            registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
            current_app.logger.info(f"Registration found: {bool(registration)}")
            
            if not registration:
                current_app.logger.warning(f"User {user_id} attempted to cancel non-existent registration for event {event_id}")
                return {
                    "error": "No registration found to cancel. You may have already cancelled your registration for this event."
                }

            # Get event details to check if refund is needed
            event = EventRepository.get_event(event_id)
            if not event:
                current_app.logger.error(f"Event {event_id} not found")
                return {"error": "Event not found"}

            current_app.logger.info(f"Registration payment_status: {getattr(registration, 'payment_status', 'unknown')}")
            current_app.logger.info(f"Event price: {event.price_per_person}")

            refund_info = None
            
            # Only process refunds for paid registrations, not pending payments
            payment_status = getattr(registration, 'payment_status', 'paid')  # Default to 'paid' for backward compatibility
            if process_refund and payment_status == 'paid' and float(event.price_per_person) > 0:
                current_app.logger.info(f"Processing refund for user {user_id}, event {event_id}")
                try:
                    from app.services.payment_service import PaymentService
                    
                    # Check refund policy
                    policy_result = PaymentService.check_refund_policy(event, registration)
                    current_app.logger.info(f"Refund policy result: {policy_result}")
                    
                    if policy_result.get('refund_eligible', False):
                        # Process the refund
                        current_app.logger.info(f"Processing refund for event {event_id}, user {user_id}")
                        refund_result, status_code = PaymentService.process_refund(event_id, user_id)
                        current_app.logger.info(f"Refund result: {refund_result}, status: {status_code}")
                        
                        if status_code == 200 and refund_result.get('refund_id'):
                            refund_info = {
                                "refund_processed": True,
                                "refund_amount": refund_result.get('amount', 0),
                                "refund_id": refund_result.get('refund_id'),
                                "estimated_arrival": '5-10 business days'
                            }
                        else:
                            refund_info = {
                                "refund_processed": False,
                                "refund_error": refund_result.get('error', 'Unknown refund error')
                            }
                    else:
                        # No refund due to policy
                        refund_info = {
                            "refund_processed": False,
                            "refund_eligible": False,
                            "policy": policy_result.get('policy_message', 'No refund available for this event')
                        }
                        
                except Exception as e:
                    current_app.logger.error(f"Error processing refund for user {user_id}, event {event_id}: {str(e)}", exc_info=True)
                    refund_info = {
                        "refund_processed": False,
                        "refund_error": "Failed to process refund due to technical error"
                    }
            else:
                current_app.logger.info(f"Skipping refund: process_refund={process_refund}, payment_status={payment_status}, price={event.price_per_person}")

            # Cancel the registration
            current_app.logger.info(f"Deleting registration for user {user_id}, event {event_id}")
            EventAttendeeRepository.delete(event_id, user_id)

            # Log the cancellation for debugging
            current_app.logger.info(f"User {user_id} cancelled registration for event {event_id}")

            # Add a small delay before processing waitlist to allow immediate re-registration
            # This prevents race conditions where the original user tries to re-register immediately
            try:
                # Attempt to register the first person from the waitlist if a spot opened up
                EventService.process_waitlist_for_event(event_id)
            except Exception as e:
                current_app.logger.error(f"Error processing waitlist after cancellation for event {event_id}: {str(e)}")
                # Don't fail the cancellation if waitlist processing fails

            # Prepare response message
            response = {"message": "Successfully cancelled registration"}
            
            if refund_info:
                response["refund_info"] = refund_info
                
            current_app.logger.info(f"Cancel registration successful: {response}")
            return response
            
        except Exception as e:
            current_app.logger.error(f"Exception in cancel_registration: {str(e)}", exc_info=True)
            return {"error": f"Failed to cancel registration: {str(e)}"}

    @staticmethod
    def process_waitlist_for_event(event_id: int):
        """Checks if a spot has opened up and registers the first person from the waitlist."""
        event = EventRepository.get_event(event_id)
        if not event or event.status != EventStatus.REGISTRATION_OPEN.value:
            return  # Only process for open events
        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT]
        )

        if attendee_count < event.max_capacity:
            first_waitlisted = EventWaitlistRepository.get_first_in_waitlist(event_id)
            if first_waitlisted:
                first_waitlisted_user = UserRepository.find_by_id(
                    first_waitlisted.user_id
                )
                if not first_waitlisted_user:
                    return {
                        "error": f"User with ID {first_waitlisted.user_id} not found"
                    }
                same_gender_count = (
                    EventAttendeeRepository.count_by_event_and_status_and_gender(
                        event_id,
                        [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN, RegistrationStatus.PENDING_PAYMENT],
                        first_waitlisted_user.gender,
                    )
                )

                # get the first waitlisted opposite gender if we have hit capacity
                if same_gender_count >= math.floor(event.max_capacity * 0.6):
                    other_gender = (
                        Gender.MALE
                        if first_waitlisted_user.gender == Gender.FEMALE
                        else Gender.FEMALE
                    )
                    first_waitlisted = (
                        EventWaitlistRepository.get_first_in_waitlist_by_gender(
                            event_id, other_gender
                        )
                    )

                if first_waitlisted:
                    # Register user with appropriate payment status
                    result = EventService.register_from_waitlist(
                        event_id, first_waitlisted.user_id, payment_completed=False
                    )
                    current_app.logger.info(f"Processed waitlist for event {event_id}: {result}")

    @staticmethod
    def check_in(event_id: int, user_id: int, pin: str):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}, 404

        if event.status == EventStatus.COMPLETED.value:
            return {"error": "Cannot check in to a completed event"}, 400

        # Users should ideally only be able to check in if event is Registration Open or In Progress
        if event.status not in [
            EventStatus.REGISTRATION_OPEN.value,
            EventStatus.IN_PROGRESS.value,
        ]:
            return {
                "error": f"Event is not open for check-in (status: {event.status})"
            }, 400

        registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
        if not registration:
            return {"error": "You are not registered for this event"}, 404

        if registration.status == RegistrationStatus.CHECKED_IN:
            return {"error": "You are already checked in for this event"}, 400

        if registration.status != RegistrationStatus.REGISTERED:
            return {
                "error": f"Cannot check in. Your registration status is: {registration.status.name if registration.status else 'Unknown'}"
            }, 400

        if registration.pin != pin:
            return {"error": "Invalid PIN"}, 401  # Unauthorized or 400 Bad Request

        updated_registration = EventAttendeeRepository.update_registration_status(
            registration, RegistrationStatus.CHECKED_IN, datetime.now(timezone.utc)
        )
        if updated_registration:
            return {"message": "Successfully checked in"}, 200
        else:
            # This case should ideally not be hit if update is robust
            return {"error": "Failed to update registration status for check-in"}, 500

    @staticmethod
    def update_event(event_id: int, data: dict, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return None, {"error": f"Event with ID {event_id} not found"}, 404

        user = UserRepository.find_by_id(user_id)
        if not user:
            return (
                None,
                {"error": "User not found"},
                404,
            )  # Should not happen if JWT is valid

        # Admin can edit any event, Organizer can only edit their own
        if not (
            user.role_id == 3
            or (user.role_id == 2 and str(event.creator_id) == str(user_id))
        ):
            raise UnauthorizedError("You are not authorized to update this event.")

        # Fields that can be updated by admin/organizer
        allowed_fields = [
            "name",
            "description",
            "starts_at",
            "address",
            "max_capacity",
            "price_per_person",
            "status",
            "registration_deadline",
        ]
        update_data = {}

        for field in allowed_fields:
            if field in data:
                value = data[field]
                if field == "starts_at" or field == "registration_deadline":
                    try:
                        update_data[field] = datetime.fromisoformat(
                            value.replace("Z", "+00:00")
                        ).astimezone(timezone.utc)
                    except ValueError:
                        return None, {"error": f"Invalid date format for {field}"}, 400
                elif field == "price_per_person":
                    try:
                        update_data[field] = Decimal(str(value))
                    except ValueError:
                        return None, {"error": f"Invalid format for {field}"}, 400
                elif field == "max_capacity":
                    try:
                        update_data[field] = int(value)
                    except ValueError:
                        return (
                            None,
                            {
                                "error": f"Invalid format for {field}, must be an integer"
                            },
                            400,
                        )
                elif field == "status":
                    if value not in [s.value for s in EventStatus]:
                        return None, {"error": f"Invalid status value: {value}"}, 400
                    update_data[field] = value
                else:
                    update_data[field] = value

        if not update_data:
            return (
                event,
                {"message": "No valid fields provided for update"},
                200,
            )  # Or 400 if no data is bad

        updated_event = EventRepository.update_event(event, update_data)
        return updated_event, {"message": "Event updated successfully"}, 200

    @staticmethod
    def delete_event(event_id: int, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}, 404

        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": "User not found"}, 404  # Should not happen

        # Admin can delete any event, Organizer can only delete their own
        if not (
            user.role_id == 3
            or (user.role_id == 2 and str(event.creator_id) == str(user_id))
        ):
            raise UnauthorizedError("You are not authorized to delete this event.")

        if (
            event.status in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value]
            and user.role_id != 3
        ):
            return {
                "error": f"Event is {event.status} and cannot be deleted by an organizer."
            }, 400

        try:
            EventAttendeeRepository.delete_by_event_id(
                event_id
            )  # Delete attendees first
            EventRepository.delete_event(event)
            return {"message": "Event deleted successfully"}, 200
        except Exception as e:
            return {
                "error": f"An error occurred while deleting the event: {str(e)}"
            }, 500

    @staticmethod
    def get_pending_payments(event_id: int = None):
        """Get all attendees with pending payments, optionally filtered by event"""
        try:
            return EventAttendeeRepository.get_pending_payments(event_id)
        except Exception as e:
            current_app.logger.error(f"Error getting pending payments: {str(e)}")
            return []

    @staticmethod
    def mark_payment_completed(event_id: int, user_id: int):
        """Mark a pending payment as completed"""
        try:
            registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
            if not registration:
                return {"error": "Registration not found"}
            
            if registration.payment_status != 'pending':
                return {"error": "Payment is not pending for this registration"}
            
            # Update payment status and registration status
            registration.payment_status = 'paid'
            registration.status = RegistrationStatus.REGISTERED
            registration.payment_due_date = None
            
            from app.extensions import db
            db.session.commit()
            
            current_app.logger.info(f"Marked payment as completed for user {user_id}, event {event_id}")
            return {"message": "Payment marked as completed"}
            
        except Exception as e:
            current_app.logger.error(f"Error marking payment completed for user {user_id}, event {event_id}: {str(e)}")
            return {"error": "Failed to update payment status"}
