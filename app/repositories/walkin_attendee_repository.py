from sqlalchemy import text
from app.extensions import db


class WalkInAttendeeRepository:
    @staticmethod
    def get_event_ids_for_user(user_id: int) -> set[int]:
        rows = db.session.execute(
            text("select event_id from walkin_attendees where user_id = :user_id"),
            {"user_id": user_id},
        ).scalars().all()
        return set(rows)

    @staticmethod
    def has_access(event_id: int, user_id: int) -> bool:
        return bool(db.session.execute(
            text("select exists (select 1 from walkin_attendees where event_id = :event_id and user_id = :user_id)"),
            {"event_id": event_id, "user_id": user_id},
        ).scalar())

    @staticmethod
    def search_users(event_id: int, search: str) -> list[dict]:
        rows = db.session.execute(
            text("""
                select users.id, users.first_name, users.last_name, users.email
                from users
                where (lower(concat_ws(' ', users.first_name, users.last_name)) like :search
                    or lower(users.email) like :search)
                    and not exists (
                        select 1 from events_attendees
                        where events_attendees.event_id = :event_id
                            and events_attendees.user_id = users.id
                    )
                    and not exists (
                        select 1 from walkin_attendees
                        where walkin_attendees.event_id = :event_id
                            and walkin_attendees.user_id = users.id
                    )
                order by lower(users.first_name), lower(users.last_name), users.id
            """),
            {"event_id": event_id, "search": f"%{search.strip().lower()}%"},
        ).mappings().all()
        return [dict(row) for row in rows]

    @staticmethod
    def grant_access(event_id: int, user_id: int) -> None:
        db.session.execute(
            text("insert into walkin_attendees (event_id, user_id) values (:event_id, :user_id) on conflict (event_id, user_id) do nothing"),
            {"event_id": event_id, "user_id": user_id},
        )
        db.session.commit()
