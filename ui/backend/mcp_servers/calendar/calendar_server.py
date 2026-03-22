from mcp.server import FastMCP
from typing import List, Dict, Optional
import json
import os
from datetime import datetime, timedelta, timezone  # ✅ BEST PRACTICE 1: Added timezone
import calendar as cal

# Simple calendar storage (in production, integrate with Google Calendar API)
CALENDAR_FILE = "calendar_events.json"

def load_events() -> List[Dict]:
    """Load calendar events from file or return empty list."""
    if os.path.exists(CALENDAR_FILE):
        with open(CALENDAR_FILE, 'r') as f:
            return json.load(f)
    return []

def save_events(events: List[Dict]) -> None:
    """Save calendar events to file."""
    with open(CALENDAR_FILE, 'w') as f:
        json.dump(events, f, indent=2, default=str)

def get_next_weekday(weekday_name: str) -> str:
    """Get the next occurrence of a weekday as YYYY-MM-DD string."""
    weekdays = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
        'friday': 4, 'saturday': 5, 'sunday': 6
    }

    today = datetime.now(timezone.utc)  # ✅ BEST PRACTICE 1: timezone-aware
    target_weekday = weekdays.get(weekday_name.lower())

    if target_weekday is None:
        return None

    # Calculate days until next occurrence of this weekday
    days_ahead = target_weekday - today.weekday()
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7

    target_date = today + timedelta(days=days_ahead)
    return target_date.strftime("%Y-%m-%d")

# ✅ BEST PRACTICE 1: New parse_time helper function
def parse_time(time_str: str) -> datetime:
    """Parse ISO format time string, handling 'Z' timezone suffix."""
    # Fix: Replace 'Z' with '+00:00' to properly preserve UTC timezone
    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

# ✅ BEST PRACTICE 2: New validate_event_data helper function
def validate_event_data(title: str, start_time: str, duration: int) -> bool:
    """Validate event data before creating or updating an event."""
    if not title.strip():
        raise ValueError("Event title cannot be empty")
    if duration <= 0 or duration > 480:  # Max 8 hours
        raise ValueError("Invalid duration: must be between 1 and 480 minutes")
    dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # Prevent scheduling in the past
    if dt < datetime.now(timezone.utc):
        raise ValueError("Cannot schedule events in the past")
    return True

# Create the MCP server
mcp = FastMCP("Calendar Integration Server")

@mcp.tool(description="Get current date and time information")
def get_current_datetime() -> str:
    """Get current date and time information."""
    now = datetime.now(timezone.utc)  # ✅ BEST PRACTICE 1: timezone-aware
    return f"📅 Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}\n📍 Today is {now.strftime('%Y-%m-%d')}"

@mcp.tool(description="Convert weekday name to next occurrence date")
def weekday_to_date(weekday_name: str) -> str:
    """Convert a weekday name (e.g., 'Monday') to the next occurrence date (YYYY-MM-DD)."""
    next_date = get_next_weekday(weekday_name)
    if next_date:
        weekday_obj = datetime.strptime(next_date, "%Y-%m-%d")
        return f"📅 Next {weekday_name.title()}: {next_date} ({weekday_obj.strftime('%A, %B %d, %Y')})"
    else:
        return f"❌ Invalid weekday name: {weekday_name}. Use Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday."

@mcp.tool(description="Add a new calendar event")
def add_event(title: str, date: str, time: str, duration_minutes: int = 60, description: str = "") -> str:
    """Add a new calendar event with title, date (YYYY-MM-DD or weekday name), time (HH:MM), and optional description."""
    events = load_events()

    try:
        # Handle weekday name conversion
        actual_date = date
        if not date.count('-') == 2:
            converted_date = get_next_weekday(date)
            if converted_date:
                actual_date = converted_date
            else:
                # ✅ BEST PRACTICE 3: User-friendly failure response
                return json.dumps({
                    "success": False,
                    "event": None,
                    "message": "❌ Invalid date format. Use YYYY-MM-DD or weekday name (e.g., 'Monday')",
                    "next_steps": "Please provide a valid date and try again"
                })

        # ✅ BEST PRACTICE 1: Parse datetime using parse_time helper
        event_datetime = datetime.strptime(f"{actual_date} {time}", "%Y-%m-%d %H:%M")
        event_datetime = parse_time(event_datetime.isoformat())

        # ✅ BEST PRACTICE 2: Validate all inputs including past-date check
        validate_event_data(title, event_datetime.isoformat(), duration_minutes)

        end_datetime = event_datetime + timedelta(minutes=duration_minutes)

        event_id = len(events) + 1
        new_event = {
            "id": event_id,
            "title": title,
            "start_datetime": event_datetime.isoformat(),
            "end_datetime": end_datetime.isoformat(),
            "description": description,
            "created_at": datetime.now(timezone.utc).isoformat()  # ✅ BEST PRACTICE 1: timezone-aware
        }

        events.append(new_event)
        save_events(events)

        # ✅ BEST PRACTICE 3: User-friendly success response
        formatted_time = event_datetime.strftime('%A, %B %d, %Y at %I:%M %p')
        return json.dumps({
            "success": True,
            "event": new_event,
            "message": f"✅ '{title}' scheduled for {formatted_time}",
            "next_steps": "I'll send you a reminder 15 minutes before"
        })

    except ValueError as e:
        # ✅ BEST PRACTICE 3: User-friendly failure response
        return json.dumps({
            "success": False,
            "event": None,
            "message": f"❌ Failed to schedule '{title}': {str(e)}",
            "next_steps": "Please check your inputs and try again"
        })

@mcp.tool(description="List upcoming calendar events")
def list_events(days_ahead: int = 7) -> str:
    """List calendar events for the next N days (default: 7)."""
    events = load_events()

    if not events:
        return "📅 No events found."

    # ✅ BEST PRACTICE 1: timezone-aware now
    now = datetime.now(timezone.utc)
    end_date = now + timedelta(days=days_ahead)

    upcoming_events = []
    for event in events:
        # ✅ BEST PRACTICE 1: Use parse_time helper
        event_date = parse_time(event["start_datetime"])
        if now <= event_date <= end_date:
            upcoming_events.append(event)

    if not upcoming_events:
        return f"📅 No events found for the next {days_ahead} days."

    # Sort by date
    upcoming_events.sort(key=lambda x: x["start_datetime"])

    result = f"📅 Upcoming Events (Next {days_ahead} days):\n"
    for event in upcoming_events:
        start_time = parse_time(event["start_datetime"])  # ✅ BEST PRACTICE 1
        end_time = parse_time(event["end_datetime"])      # ✅ BEST PRACTICE 1
        duration = (end_time - start_time).seconds // 60

        result += f"\n🕐 {event['title']}\n"
        result += f"   📆 {start_time.strftime('%A, %B %d, %Y')}\n"
        result += f"   ⏰ {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} ({duration} min)\n"
        if event.get("description"):
            result += f"   📝 {event['description']}\n"

    return result

@mcp.tool(description="Check for scheduling conflicts")
def check_conflicts(date: str, start_time: str, duration_minutes: int = 60) -> str:
    """Check if there are any scheduling conflicts for a proposed meeting time."""
    events = load_events()

    try:
        # ✅ BEST PRACTICE 1: Use parse_time helper
        proposed_start = parse_time(
            datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M").isoformat()
        )
        proposed_end = proposed_start + timedelta(minutes=duration_minutes)

        conflicts = []
        for event in events:
            event_start = parse_time(event["start_datetime"])  # ✅ BEST PRACTICE 1
            event_end = parse_time(event["end_datetime"])      # ✅ BEST PRACTICE 1

            # Check for overlap
            if (proposed_start < event_end and proposed_end > event_start):
                conflicts.append(event)

        if not conflicts:
            return f"✅ No conflicts found for {proposed_start.strftime('%B %d, %Y at %I:%M %p')} ({duration_minutes} minutes)"

        result = f"⚠️ {len(conflicts)} conflict(s) found:\n"
        for conflict in conflicts:
            conflict_start = parse_time(conflict["start_datetime"])  # ✅ BEST PRACTICE 1
            conflict_end = parse_time(conflict["end_datetime"])      # ✅ BEST PRACTICE 1
            result += f"• {conflict['title']} ({conflict_start.strftime('%I:%M %p')} - {conflict_end.strftime('%I:%M %p')})\n"

        return result

    except ValueError:
        return "❌ Invalid date/time format. Use YYYY-MM-DD for date and HH:MM for time."

@mcp.tool(description="Find available time slots")
def find_available_slots(date: str, duration_minutes: int = 60, start_hour: int = 9, end_hour: int = 17) -> str:
    """Find available time slots on a specific date within business hours."""
    events = load_events()

    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()

        # Get events for the target date
        day_events = []
        for event in events:
            event_start = parse_time(event["start_datetime"])  # ✅ BEST PRACTICE 1
            if event_start.date() == target_date:
                day_events.append(event)

        # Sort events by start time
        day_events.sort(key=lambda x: x["start_datetime"])

        # Generate time slots
        available_slots = []
        current_time = datetime.combine(
            target_date, datetime.min.time(), tzinfo=timezone.utc  # ✅ BEST PRACTICE 1
        ) + timedelta(hours=start_hour)
        end_time = datetime.combine(
            target_date, datetime.min.time(), tzinfo=timezone.utc  # ✅ BEST PRACTICE 1
        ) + timedelta(hours=end_hour)

        for event in day_events:
            event_start = parse_time(event["start_datetime"])  # ✅ BEST PRACTICE 1
            event_end = parse_time(event["end_datetime"])      # ✅ BEST PRACTICE 1

            # Check if there's space before this event
            if current_time + timedelta(minutes=duration_minutes) <= event_start:
                available_slots.append({
                    "start": current_time.strftime("%H:%M"),
                    "end": event_start.strftime("%H:%M")
                })

            current_time = max(current_time, event_end)

        # Check for time after last event
        if current_time + timedelta(minutes=duration_minutes) <= end_time:
            available_slots.append({
                "start": current_time.strftime("%H:%M"),
                "end": end_time.strftime("%H:%M")
            })

        if not available_slots:
            return f"❌ No available {duration_minutes}-minute slots found on {target_date.strftime('%B %d, %Y')}"

        result = f"✅ Available {duration_minutes}-minute slots on {target_date.strftime('%B %d, %Y')}:\n"
        for slot in available_slots:
            result += f"• {slot['start']} - {slot['end']}\n"

        return result

    except ValueError:
        return "❌ Invalid date format. Use YYYY-MM-DD."

@mcp.tool(description="Find events by title or description")
def find_events(search_term: str) -> str:
    """Find events by searching title or description."""
    events = load_events()

    if not events:
        return "📅 No events found."

    matching_events = []
    for event in events:
        if (search_term.lower() in event["title"].lower() or
            search_term.lower() in event.get("description", "").lower()):
            matching_events.append(event)

    if not matching_events:
        return f"❌ No events found matching '{search_term}'"

    result = f"🔍 Found {len(matching_events)} event(s) matching '{search_term}':\n"
    for event in matching_events:
        start_time = parse_time(event["start_datetime"])  # ✅ BEST PRACTICE 1
        end_time = parse_time(event["end_datetime"])      # ✅ BEST PRACTICE 1
        duration = (end_time - start_time).seconds // 60

        result += f"\n📋 ID: {event['id']} - {event['title']}\n"
        result += f"   📆 {start_time.strftime('%A, %B %d, %Y')}\n"
        result += f"   ⏰ {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} ({duration} min)\n"
        if event.get("description"):
            result += f"   📝 {event['description']}\n"

    return result

@mcp.tool(description="Update an existing calendar event")
def update_event(event_id: int, title: str = None, date: str = None, time: str = None,
                duration_minutes: int = None, description: str = None) -> str:
    """Update an existing calendar event. Provide only the fields you want to change."""
    events = load_events()

    # Find the event
    event_index = None
    for i, event in enumerate(events):
        if event["id"] == event_id:
            event_index = i
            break

    if event_index is None:
        return json.dumps({
            "success": False,
            "event": None,
            "message": f"❌ Event with ID {event_id} not found.",
            "next_steps": "Use find_events() to search for events."
        })

    event = events[event_index]

    try:
        # Update fields if provided
        if title:
            # ✅ BEST PRACTICE 2: Validate title is not empty
            if not title.strip():
                raise ValueError("Event title cannot be empty")
            event["title"] = title

        if date or time or duration_minutes:
            # ✅ BEST PRACTICE 1: Use parse_time helper
            current_start = parse_time(event["start_datetime"])

            # Use new date if provided, otherwise keep current
            new_date = date if date else current_start.strftime("%Y-%m-%d")

            # Convert weekday name to date if needed
            if not new_date.count('-') == 2:
                converted_date = get_next_weekday(new_date)
                if converted_date:
                    new_date = converted_date
                else:
                    return json.dumps({
                        "success": False,
                        "event": None,
                        "message": "❌ Invalid date format. Use YYYY-MM-DD or weekday name.",
                        "next_steps": "Please provide a valid date and try again"
                    })

            # Use new time if provided, otherwise keep current
            new_time = time if time else current_start.strftime("%H:%M")

            # ✅ BEST PRACTICE 1: Parse new datetime using parse_time helper
            new_start = parse_time(
                datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M").isoformat()
            )

            # Use new duration if provided, otherwise calculate from current event
            if duration_minutes:
                new_duration = duration_minutes
            else:
                current_end = parse_time(event["end_datetime"])  # ✅ BEST PRACTICE 1
                new_duration = (current_end - current_start).seconds // 60

            # ✅ BEST PRACTICE 2: Validate updated event data
            validate_event_data(event["title"], new_start.isoformat(), new_duration)

            new_end = new_start + timedelta(minutes=new_duration)

            event["start_datetime"] = new_start.isoformat()
            event["end_datetime"] = new_end.isoformat()

        if description is not None:  # Allow empty string
            event["description"] = description

        # Save updated events
        save_events(events)

        updated_start = parse_time(event["start_datetime"])  # ✅ BEST PRACTICE 1
        updated_end = parse_time(event["end_datetime"])      # ✅ BEST PRACTICE 1
        updated_duration = (updated_end - updated_start).seconds // 60

        # ✅ BEST PRACTICE 3: User-friendly success response
        formatted_time = updated_start.strftime('%A, %B %d, %Y at %I:%M %p')
        return json.dumps({
            "success": True,
            "event": event,
            "message": f"✅ '{event['title']}' updated for {formatted_time} ({updated_duration} minutes)",
            "next_steps": "Use list_events() to see all upcoming events"
        })

    except ValueError as e:
        # ✅ BEST PRACTICE 3: User-friendly failure response
        return json.dumps({
            "success": False,
            "event": None,
            "message": f"❌ Failed to update event ID {event_id}: {str(e)}",
            "next_steps": "Please check your inputs and try again"
        })

@mcp.tool(description="Delete a calendar event by ID or search term")
def delete_event(event_id: int = None, search_term: str = None) -> str:
    """Delete a calendar event by its ID or by searching for it."""
    events = load_events()

    if event_id:
        # Delete by ID
        for i, event in enumerate(events):
            if event["id"] == event_id:
                deleted_event = events.pop(i)
                save_events(events)
                # ✅ BEST PRACTICE 3: User-friendly success response
                return json.dumps({
                    "success": True,
                    "event": deleted_event,
                    "message": f"🗑️ Event '{deleted_event['title']}' (ID: {event_id}) deleted successfully!",
                    "next_steps": "Use list_events() to see remaining upcoming events"
                })

        # ✅ BEST PRACTICE 3: User-friendly failure response
        return json.dumps({
            "success": False,
            "event": None,
            "message": f"❌ Event with ID {event_id} not found.",
            "next_steps": "Use find_events() to search for events"
        })

    elif search_term:
        # Find and delete by search term
        matching_events = []
        for i, event in enumerate(events):
            if (search_term.lower() in event["title"].lower() or
                search_term.lower() in event.get("description", "").lower()):
                matching_events.append((i, event))

        if not matching_events:
            # ✅ BEST PRACTICE 3: User-friendly failure response
            return json.dumps({
                "success": False,
                "event": None,
                "message": f"❌ No events found matching '{search_term}'",
                "next_steps": "Try a different search term or use list_events() to see all events"
            })

        if len(matching_events) > 1:
            # ✅ BEST PRACTICE 3: User-friendly multiple matches response
            event_list = [
                {
                    "id": event["id"],
                    "title": event["title"],
                    "start_datetime": parse_time(event["start_datetime"]).strftime('%B %d at %I:%M %p')  # ✅ BEST PRACTICE 1
                }
                for _, event in matching_events
            ]
            return json.dumps({
                "success": False,
                "event": None,
                "message": f"⚠️ Multiple events found matching '{search_term}'",
                "matches": event_list,
                "next_steps": "Please use delete_event() with a specific event ID"
            })

        # Delete the single matching event
        event_index, event = matching_events[0]
        deleted_event = events.pop(event_index)
        save_events(events)

        # ✅ BEST PRACTICE 3: User-friendly success response
        return json.dumps({
            "success": True,
            "event": deleted_event,
            "message": f"🗑️ Event '{deleted_event['title']}' deleted successfully!",
            "next_steps": "Use list_events() to see remaining upcoming events"
        })

    else:
        # ✅ BEST PRACTICE 3: User-friendly missing input response
        return json.dumps({
            "success": False,
            "event": None,
            "message": "❌ Please provide either event_id or search_term to delete an event.",
            "next_steps": "Use find_events() to search for events by name"
        })

if __name__ == "__main__":
    print("📅 Starting Calendar Integration MCP Server...")
    mcp.run(transport="stdio")