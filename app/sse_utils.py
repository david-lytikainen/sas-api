# sas-api/app/sse_utils.py
import queue
import json
from flask import current_app

class MessageAnnouncer:
    """
    Manages Server-Sent Event listeners and message broadcasting.
    Uses thread-safe queues for listeners.
    """
    def __init__(self):
        self.listeners = []

    def listen(self):
        """
        Adds a new listener queue.
        Returns the queue for the listener to consume messages from.
        """
        # Use a small maxsize to prevent excessive memory usage if a client disconnects uncleanly
        q = queue.Queue(maxsize=10)
        self.listeners.append(q)
        current_app.logger.info(f"SSE Listener added. Total listeners: {len(self.listeners)}")
        return q

    def announce(self, msg: str):
        """
        Sends a message to all active listeners.
        Removes listeners whose queues are full (indicating potential disconnection).
        """
        # --- ADD LOG --- 
        listener_count = len(self.listeners)
        current_app.logger.info(f"SSE Announce: Attempting to send to {listener_count} listeners.")
        # ------------- 

        # Iterate in reverse to safely remove listeners
        for i in reversed(range(len(self.listeners))):
            try:
                self.listeners[i].put_nowait(msg)
            except queue.Full:
                # Assume listener disconnected if queue is full
                del self.listeners[i]
                current_app.logger.info(f"SSE Listener removed (queue full). Total listeners: {len(self.listeners)}")
            except Exception as e:
                # Catch other potential errors during announcement
                current_app.logger.error(f"Error announcing to listener {i}: {e}")
                try:
                    del self.listeners[i] # Remove potentially problematic listener
                    current_app.logger.info(f"SSE Listener removed (error). Total listeners: {len(self.listeners)}")
                except IndexError:
                    pass # Listener might have already been removed

        current_app.logger.debug(f"SSE Announced message to {len(self.listeners)} listeners.")

# Global instance - accessed by routes and services
# In a larger application, consider dependency injection or Flask application context
announcer = MessageAnnouncer()

def format_sse(data: dict, event: str = None) -> str:
    """
    Formats data into the Server-Sent Event message format.
    Expects data as a dictionary, which will be converted to JSON.

    Args:
        data: The dictionary payload for the event.
        event: Optional event type name.

    Returns:
        A string formatted according to the SSE specification.
    """
    try:
        json_data = json.dumps(data)
        msg = f'data: {json_data}\n\n'
        if event is not None:
            msg = f'event: {event}\n{msg}'
        return msg
    except TypeError as e:
        current_app.logger.error(f"Error formatting SSE data: {e}. Data: {data}")
        # Fallback: send an error message if JSON serialization fails
        error_data = json.dumps({"error": "Failed to serialize event data", "details": str(e)})
        return f'event: error\ndata: {error_data}\n\n' 