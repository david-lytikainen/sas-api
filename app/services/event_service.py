from datetime import datetime, timezone
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
    def register_for_event(event_id: int, user_id: int, join_waitlist: bool = False, payment_completed: bool = False):
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": f"Event with ID {event_id} not found"}
        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return {"error": "Event is not open for registration"}
        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            return {"error": "You are already registered for this event"}
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            return {"error": "You are already on the waitlist for this event"}

        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
        )
        
        # Get user info for gender checks
        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": f"User with ID {user_id} not found"}
            
        same_gender_count = (
            EventAttendeeRepository.count_by_event_and_status_and_gender(
                event_id,
                [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
                user.gender,
            )
        )
        
        # Check if event is full overall or for this gender
        event_full = attendee_count >= event.max_capacity
        gender_full = same_gender_count >= math.floor(event.max_capacity * 0.6)
        
        # If event is full and user wants to join waitlist, don't require payment yet
        if (event_full or gender_full) and join_waitlist:
            return EventService.join_event_waitlist(event_id, user_id)
        elif event_full or gender_full:
            return {
                "error": "Event is currently full" + (" for this gender" if gender_full and not event_full else ""),
                "waitlist_available": True,
            }

        # Only require payment if there's actually a spot available
        event_price = float(event.price_per_person)
        if event_price > 0 and not payment_completed:
            return {
                "error": "Payment required for this event",
                "requires_payment": True,
                "price": event_price
            }

        # Generate random 4-digit PIN
        pin = "".join(random.choices("0123456789", k=4))

        EventAttendeeRepository.register_for_event(
            {
                "event_id": event_id,
                "user_id": user_id,
                "status": RegistrationStatus.REGISTERED,
                "pin": pin,
            }
        )

        return {"message": "Successfully registered for event"}

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
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
        )
        
        user = UserRepository.find_by_id(user_id)
        if not user:
            return {"error": f"User with ID {user_id} not found"}
            
        same_gender_count = (
            EventAttendeeRepository.count_by_event_and_status_and_gender(
                event_id,
                [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
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

        # Check payment requirement
        event_price = float(event.price_per_person)
        if event_price > 0 and not payment_completed:
            return {
                "error": "Payment required to register from waitlist",
                "requires_payment": True,
                "price": event_price
            }

        # Register the user and remove from waitlist
        pin = "".join(random.choices("0123456789", k=4))
        try:
            EventAttendeeRepository.register_for_event(
                {
                    "event_id": event_id,
                    "user_id": user_id,
                    "status": RegistrationStatus.REGISTERED,
                    "pin": pin,
                }
            )
            EventWaitlistRepository.remove_from_waitlist(event_id, user_id)
            return {"message": "Successfully registered from waitlist", "pin": pin}
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
        # Check if user is on waitlist first
        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            removed = EventWaitlistRepository.remove_from_waitlist(event_id, user_id)
            if removed:
                return {"message": "Successfully removed from waitlist"}
            else:
                return {
                    "error": "Failed to remove from waitlist"
                }  # Should not happen if find_by_event_and_user returned entry

        # If not on waitlist, proceed to cancel registration as attendee
        registration = EventAttendeeRepository.find_by_event_and_user(event_id, user_id)
        if not registration:
            return {"error": "You are not registered for this event or on its waitlist"}

        # Get event details to check if refund is needed
        event = EventRepository.get_event(event_id)
        if not event:
            return {"error": "Event not found"}

        refund_info = None
        
        # Check if event has a cost and if refund should be processed
        if process_refund and float(event.price_per_person) > 0:
            try:
                # Import here to avoid circular imports
                from app.services.payment_service import PaymentService
                
                # Get refund policy information
                policy_result, policy_status = PaymentService.get_refund_policy_info(event_id)
                
                if policy_status == 200 and policy_result.get('can_refund', False):
                    # Process the refund
                    refund_result, refund_status = PaymentService.process_refund(
                        event_id, user_id, "requested_by_customer"
                    )
                    
                    if refund_status == 200:
                        refund_info = {
                            "refund_processed": True,
                            "refund_id": refund_result.get('refund_id'),
                            "refund_amount": refund_result.get('amount', 0) / 100,  # Convert from cents
                            "policy": policy_result.get('policy_message')
                        }
                        current_app.logger.info(f"Refund processed for user {user_id}, event {event_id}: {refund_result.get('refund_id')}")
                    else:
                        # Refund failed, but still allow cancellation
                        refund_info = {
                            "refund_processed": False,
                            "refund_error": refund_result.get('error', 'Unknown refund error'),
                            "policy": policy_result.get('policy_message')
                        }
                        current_app.logger.warning(f"Refund failed for user {user_id}, event {event_id}: {refund_result.get('error')}")
                else:
                    # No refund due to policy
                    refund_info = {
                        "refund_processed": False,
                        "refund_eligible": False,
                        "policy": policy_result.get('policy_message', 'No refund available for this event')
                    }
                    
            except Exception as e:
                current_app.logger.error(f"Error processing refund for user {user_id}, event {event_id}: {str(e)}")
                refund_info = {
                    "refund_processed": False,
                    "refund_error": "Failed to process refund due to technical error"
                }

        # Cancel the registration
        EventAttendeeRepository.delete(event_id, user_id)

        # Attempt to register the first person from the waitlist if a spot opened up
        EventService.process_waitlist_for_event(event_id)

        # Prepare response message
        response = {"message": "Successfully cancelled registration"}
        
        if refund_info:
            response["refund_info"] = refund_info
            
        return response

    @staticmethod
    def process_waitlist_for_event(event_id: int):
        """Checks if a spot has opened up and registers the first person from the waitlist."""
        event = EventRepository.get_event(event_id)
        if not event or event.status != EventStatus.REGISTRATION_OPEN.value:
            return  # Only process for open events
        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
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
                        [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
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

                # Check if event requires payment
                event_price = float(event.price_per_person)
                if event_price > 0:
                    # For paid events, notify the user and create payment opportunity
                    current_app.logger.info(f"User {first_waitlisted.user_id} is next for event {event_id} but payment required")
                    
                    try:
                        # Create a PaymentIntent for the waitlisted user
                        from app.services.payment_service import PaymentService
                        payment_result, payment_status = PaymentService.create_payment_intent(
                            event_id, first_waitlisted.user_id
                        )
                        
                        if payment_status == 200:
                            # Send email notification with payment link
                            try:
                                from app.utils.email import send_waitlist_opportunity_email
                                send_waitlist_opportunity_email(
                                    first_waitlisted_user, 
                                    event, 
                                    payment_result.get('payment_intent_id')
                                )
                                current_app.logger.info(f"Sent waitlist opportunity email to user {first_waitlisted.user_id}")
                            except Exception as email_error:
                                current_app.logger.error(f"Failed to send waitlist email to user {first_waitlisted.user_id}: {str(email_error)}")
                            
                            current_app.logger.info(f"WAITLIST OPPORTUNITY: Created PaymentIntent for user {first_waitlisted.user_id}, event {event_id}")
                            current_app.logger.info(f"PaymentIntent ID: {payment_result.get('payment_intent_id')}")
                            
                            # TODO: In production, also implement:
                            # 1. Set 24-hour timer to check payment completion
                            # 2. If not paid in 24 hours, move to next waitlist user
                            # 3. Consider adding push notifications
                            
                        else:
                            current_app.logger.error(f"Failed to create PaymentIntent for waitlist user {first_waitlisted.user_id}: {payment_result}")
                            
                    except Exception as e:
                        current_app.logger.error(f"Error creating payment opportunity for waitlist user {first_waitlisted.user_id}: {str(e)}")
                    
                    return
                else:
                    # For free events, register immediately
                    pin = "".join(random.choices("0123456789", k=4))
                    try:
                        EventAttendeeRepository.register_for_event(
                            {
                                "event_id": event_id,
                                "user_id": first_waitlisted.user_id,
                                "status": RegistrationStatus.REGISTERED,
                                "pin": pin,
                            }
                        )
                        EventWaitlistRepository.remove_from_waitlist(
                            event_id, first_waitlisted.user_id
                        )
                        current_app.logger.info(f"User {first_waitlisted.user_id} automatically registered from waitlist for free event {event_id}")
                    except Exception as e:
                        current_app.logger.error(f"Error registering user {first_waitlisted.user_id} from waitlist for event {event_id}: {str(e)}")
                        pass  # Keep them on waitlist if registration fails for some reason

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
