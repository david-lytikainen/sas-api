from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import math
from typing import List
from zoneinfo import ZoneInfo
from flask import current_app
from app.extensions import db
from app.exceptions import UnauthorizedError, MissingFieldsError
from app.models import Event, EventAttendee
from app.models.enums import EventStatus, Gender, RegistrationStatus
from app.repositories.event_attendee_repository import EventAttendeeRepository
from app.repositories.event_repository import EventRepository
from app.repositories.event_waitlist_repository import EventWaitlistRepository
from app.repositories.user_repository import UserRepository
from app.services.stripe_service import StripeService
from app.utils.email import send_event_registration_confirmation_email, send_event_reminder_email, send_waitlist_spot_open_email


class EventService:
    AUTO_COMPLETE_TIMEZONE = ZoneInfo("America/New_York")

    @staticmethod
    def auto_complete_due_events(now_utc: datetime | None = None) -> int:
        comparison_time = now_utc or datetime.now(timezone.utc)
        comparison_time_est = comparison_time.astimezone(EventService.AUTO_COMPLETE_TIMEZONE)
        due_events = Event.query.filter_by(status=EventStatus.IN_PROGRESS.value).all()
        updated_count = 0

        for event in due_events:
            if (
                event.starts_at
                and event.starts_at.astimezone(EventService.AUTO_COMPLETE_TIMEZONE).date()
                < comparison_time_est.date()
            ):
                event.status = EventStatus.COMPLETED.value
                updated_count += 1

        if updated_count:
            db.session.commit()

        return updated_count

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

        if not StripeService.user_can_manage_events(user):
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
        if user.role_id != 3:
            is_intro_event = Event.query.filter_by(creator_id=user_id).count() < 2
            minimum_price = StripeService.minimum_ticket_price(is_intro_event)
            if Decimal(str(data["price_per_person"])) < minimum_price:
                return {
                    "error": f"Minimum price per person is ${minimum_price} so your payout is not negative."
                }, 400

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
                "enforce_gender_balance": bool(
                    data.get("enforce_gender_balance", True)
                ),
                "price_per_person": Decimal(str(data["price_per_person"])),
                "registration_deadline": datetime.fromisoformat(
                    data["starts_at"].replace("Z", "+00:00")
                ).astimezone(timezone.utc),
            }
        )

        return event

    @staticmethod
    def validate_registration_for_event(event_id: int, user_id: int):
        event = EventRepository.get_event(event_id)
        if not event:
            return None, {"error": f"Event with ID {event_id} not found"}
        if event.status != EventStatus.REGISTRATION_OPEN.value:
            return None, {"error": "Event is not open for registration"}

        existing_registration = EventAttendeeRepository.find_by_event_and_user(
            event_id, user_id
        )
        if existing_registration:
            return None, {"error": "You are already registered for this event"}

        on_waitlist = EventWaitlistRepository.find_by_event_and_user(event_id, user_id)
        if on_waitlist:
            return None, {"error": "You are already on the waitlist for this event"}

        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
        )
        if attendee_count >= event.max_capacity:
            return None, {"error": "Event is currently full", "waitlist_available": True}

        user = UserRepository.find_by_id(user_id)
        if not user:
            return None, {"error": f"User with ID {user_id} not found"}

        if event.enforce_gender_balance:
            same_gender_count = (
                EventAttendeeRepository.count_by_event_and_status_and_gender(
                    event_id,
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
                    user.gender,
                )
            )
            if same_gender_count >= math.floor(event.max_capacity * 0.6):
                return None, {
                    "error": "Event is currently full for this gender",
                    "waitlist_available": True,
                }

        return event, None

    @staticmethod
    def register_for_event(
        event_id: int,
        user_id: int,
        join_waitlist: bool = False,
        payment_confirmed: bool = False,
    ):
        event, validation_error = EventService.validate_registration_for_event(
            event_id, user_id
        )
        if validation_error:
            if join_waitlist:
                return EventService.join_event_waitlist(event_id, user_id)
            return validation_error

        if (
            not join_waitlist
            and event.price_per_person
            and Decimal(str(event.price_per_person)) > 0
            and not payment_confirmed
        ):
            return {
                "error": "Payment is required before registration. Please use Stripe Checkout to sign up for this event."
            }

        registration = EventAttendeeRepository.register_for_event(
            {
                "event_id": event_id,
                "user_id": user_id,
                "status": RegistrationStatus.REGISTERED,
            }
        )
        attendee = UserRepository.find_by_id(registration.user_id)
        organizer = UserRepository.find_by_id(event.creator_id)
        if attendee and organizer:
            send_event_registration_confirmation_email(attendee, event, organizer)

        current_app.logger.info(
            "User %s registered for event %s.", user_id, event_id
        )
        return {"message": "Successfully registered for event"}

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
            current_app.logger.info(
                "User %s joined the waitlist for event %s.", user_id, event_id
            )
            return {"message": "Successfully joined the waitlist for the event"}
        except Exception as exc:
            current_app.logger.error(
                "Failed to add user %s to the waitlist for event %s: %s",
                user_id,
                event_id,
                str(exc),
                exc_info=True,
            )
            return {"error": f"Could not join waitlist: {str(exc)}"}

    @staticmethod
    def cancel_registration(event_id: int, user_id: int):
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

        EventAttendeeRepository.delete(event_id, user_id)

        # Notify waitlisted users if a spot opened up so they can sign themselves up.
        EventService.process_waitlist_for_event(event_id)

        return {"message": "Successfully cancelled registration"}

    @staticmethod
    def send_due_event_reminders(now_utc: datetime | None = None) -> int:
        comparison_time = now_utc or datetime.now(timezone.utc)
        comparison_time_est = comparison_time.astimezone(
            EventService.AUTO_COMPLETE_TIMEZONE
        )
        comparison_date_est = comparison_time_est.date()

        registrations = (
            db.session.query(EventAttendee, Event)
            .join(Event, EventAttendee.event_id == Event.id)
            .filter(
                EventAttendee.status.in_(
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
                ),
                Event.status == EventStatus.REGISTRATION_OPEN.value,
                Event.starts_at > comparison_time,
            )
            .all()
        )

        sent_count = 0
        for registration, event in registrations:
            reminder_label = EventService.get_due_reminder_label(
                event.starts_at.astimezone(EventService.AUTO_COMPLETE_TIMEZONE).date(),
                comparison_date_est,
            )
            if not reminder_label:
                continue

            attendee = UserRepository.find_by_id(registration.user_id)
            organizer = UserRepository.find_by_id(event.creator_id)
            if not attendee or not organizer:
                continue

            send_event_reminder_email(attendee, event, organizer, reminder_label)
            sent_count += 1

        return sent_count

    @staticmethod
    def get_due_reminder_label(event_date: date, comparison_date: date) -> str | None:
        if event_date == comparison_date + timedelta(days=1):
            return "1 day"
        if event_date == comparison_date + timedelta(days=7):
            return "1 week"
        if event_date == EventService.add_months(comparison_date, 1):
            return "1 month"
        return None

    @staticmethod
    def add_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def process_waitlist_for_event(event_id: int):
        """Checks if a spot has opened up and notifies eligible waitlisted users."""
        event = EventRepository.get_event(event_id)
        if not event or event.status != EventStatus.REGISTRATION_OPEN.value:
            return
        attendee_count = EventAttendeeRepository.count_by_event_id_and_status(
            event_id, [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN]
        )
        if attendee_count >= event.max_capacity:
            return

        if event.enforce_gender_balance:
            gender_cap = math.floor(event.max_capacity * 0.6)
            eligible_genders = {
                Gender.MALE: EventAttendeeRepository.count_by_event_and_status_and_gender(
                    event_id,
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
                    Gender.MALE,
                )
                < gender_cap,
                Gender.FEMALE: EventAttendeeRepository.count_by_event_and_status_and_gender(
                    event_id,
                    [RegistrationStatus.REGISTERED, RegistrationStatus.CHECKED_IN],
                    Gender.FEMALE,
                )
                < gender_cap,
            }
        else:
            eligible_genders = {
                Gender.MALE: True,
                Gender.FEMALE: True,
            }

        waitlist_entries = EventWaitlistRepository.get_waitlist_for_event(event_id)
        for entry in waitlist_entries:
            waitlisted_user = UserRepository.find_by_id(entry.user_id)
            if not waitlisted_user or not eligible_genders.get(waitlisted_user.gender, False):
                continue
            try:
                send_waitlist_spot_open_email(waitlisted_user, event)
            except Exception:
                pass

    @staticmethod
    def check_in(event_id: int, user_id: int, pin: str):
        return {"error": "Self check-in has been removed. Ask event staff to check you in."}, 410

    @staticmethod
    def manual_check_in(event_id: int, user_id: int):
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

        updated_registration = EventAttendeeRepository.update_registration_status(
            registration, RegistrationStatus.CHECKED_IN, datetime.now(timezone.utc)
        )
        if updated_registration:
            return {"message": "Successfully checked in attendee"}, 200
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
            or (
                StripeService.user_can_manage_events(user)
                and str(event.creator_id) == str(user_id)
            )
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
            "enforce_gender_balance",
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
                        if user.role_id != 3:
                            minimum_price = StripeService.minimum_ticket_price(
                                StripeService.is_intro_event(event)
                            )
                            if update_data[field] < minimum_price:
                                return (
                                    None,
                                    {
                                        "error": f"Minimum price per person is ${minimum_price} so your payout is not negative."
                                    },
                                    400,
                                )
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
            or (
                StripeService.user_can_manage_events(user)
                and str(event.creator_id) == str(user_id)
            )
        ):
            raise UnauthorizedError("You are not authorized to delete this event.")

        if event.status in [EventStatus.IN_PROGRESS.value, EventStatus.COMPLETED.value]:
            return {
                "error": f"Event is {event.status} and cannot be deleted."
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
