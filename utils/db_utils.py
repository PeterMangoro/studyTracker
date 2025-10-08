import csv
import os
from datetime import datetime
from datetime import date as _date
from typing import List, Dict, Any
import pytz
from dateutil import parser as dtparser

# Robust ULID generator with fallback
try:
	import ulid as _ulid
	def generate_ulid() -> str:
		return str(_ulid.new())
except Exception:  # pragma: no cover
	import uuid as _uuid
	def generate_ulid() -> str:
		return _uuid.uuid4().hex

CSV_HEADERS = [
	"id",
	"title",
	"due_date",
	"estimated_hours",
	"hours_logged",
	"priority",
	"status",
	"steps",
	"created_at",
	"completed_at",
]

CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "todos.csv")
TIMETABLE_CSV_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "timetable.csv")
TIMETABLE_HEADERS = [
	"id",
	"day",            # Monday..Sunday
	"start_time",     # HH:MM
	"end_time",       # HH:MM
	"activity",
	"focus",
]


def ensure_csv_exists() -> None:
	os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
	if not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
		with open(CSV_PATH, mode="w", newline="") as f:
			writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
			writer.writeheader()
	# timetable file
	if not os.path.exists(TIMETABLE_CSV_PATH) or os.path.getsize(TIMETABLE_CSV_PATH) == 0:
		with open(TIMETABLE_CSV_PATH, mode="w", newline="") as f:
			writer = csv.DictWriter(f, fieldnames=TIMETABLE_HEADERS)
			writer.writeheader()


def read_todos() -> List[Dict[str, Any]]:
	ensure_csv_exists()
	rows: List[Dict[str, Any]] = []
	with open(CSV_PATH, mode="r", newline="") as f:
		reader = csv.DictReader(f)
		for row in reader:
			rows.append(row)
	return rows


def write_todos(rows: List[Dict[str, Any]]) -> None:
	ensure_csv_exists()
	with open(CSV_PATH, mode="w", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
		writer.writeheader()
		for row in rows:
			writer.writerow(row)


def export_todos_csv() -> bytes:
	"""Return current todos as CSV bytes."""
	rows = read_todos()
	from io import StringIO
	sio = StringIO()
	writer = csv.DictWriter(sio, fieldnames=CSV_HEADERS)
	writer.writeheader()
	for r in rows:
		writer.writerow(r)
	return sio.getvalue().encode("utf-8")


def csv_template_bytes() -> bytes:
	"""Return a CSV template with headers and an example row (id optional)."""
	from io import StringIO
	sio = StringIO()
	writer = csv.DictWriter(sio, fieldnames=CSV_HEADERS)
	writer.writeheader()
	writer.writerow({
		"id": "",  # leave blank to auto-generate
		"title": "Data Product Design / Project (weekly assessment)",
		"due_date": "2025-10-15",
		"estimated_hours": "2.0",
		"hours_logged": "0.0",
		"priority": "Medium",
		"status": "todo",
		"steps": "- Research requirements\n- Create wireframes\n- Implement prototype",
		"created_at": "",
		"completed_at": "",
	})
	return sio.getvalue().encode("utf-8")


def import_todos_csv(content: bytes, mode: str = "append") -> Dict[str, Any]:
	"""Import todos from uploaded CSV bytes.

	mode: "append" or "replace". Missing ids will be generated. Fields coerced.
	Returns summary dict with counts.
	"""
	assert mode in ("append", "replace")
	ensure_csv_exists()
	from io import StringIO
	text = content.decode("utf-8")
	reader = csv.DictReader(StringIO(text))
	missing_core = [c for c in ["title","due_date","estimated_hours","priority","status"] if c not in reader.fieldnames and not set(["category","project","task"]).issubset(set(reader.fieldnames or []))]
	if missing_core:
		return {"ok": False, "error": f"Missing required columns: {', '.join(missing_core)}"}

	existing = [] if mode == "replace" else read_todos()
	added = 0
	for row in reader:
		# Compose title from category/project/task if title absent
		title_csv = (row.get("title") or "").strip()
		if not title_csv:
			category = (row.get("category") or "").strip()
			project = (row.get("project") or "").strip()
			task = (row.get("task") or "").strip()
			parts = [p for p in [category, project, task] if p]
			title_csv = " / ".join(parts)
		if not title_csv:
			continue
		# Normalize completed_at to YYYY-MM-DD if provided
		completed_at_raw = (row.get("completed_at") or "").strip()
		if completed_at_raw:
			try:
				completed_at_parsed = dtparser.parse(completed_at_raw)
				completed_at_norm = completed_at_parsed.date().isoformat()
			except Exception:
				completed_at_norm = completed_at_raw[:10]
		else:
			completed_at_norm = ""

		new_row = {
			"id": (row.get("id") or "").strip() or generate_ulid(),
			"title": title_csv,
			"due_date": (row.get("due_date") or "").strip(),
			"estimated_hours": f"{float(row.get('estimated_hours') or 0):.2f}",
			"hours_logged": f"{float(row.get('hours_logged') or 0):.2f}",
			"priority": (row.get("priority") or "Medium").strip() or "Medium",
			"status": (row.get("status") or "todo").strip() or "todo",
			"steps": (row.get("steps") or "").strip(),
			"created_at": (row.get("created_at") or datetime.now(pytz.timezone('America/New_York')).isoformat()),
			"completed_at": completed_at_norm,
		}
		existing.append(new_row)
		added += 1

	write_todos(existing)
	return {"ok": True, "added": added, "total": len(existing)}


def add_todo(title: str, due_date: str, estimated_hours: float, priority: str, steps: str = "") -> Dict[str, Any]:
	rows = read_todos()
	new_row = {
		"id": generate_ulid(),
		"title": title.strip(),
		"due_date": due_date,
		"estimated_hours": f"{float(estimated_hours):.2f}",
		"hours_logged": f"{0.0:.2f}",
		"priority": priority,
		"status": "todo",
		"steps": steps.strip(),
		"created_at": datetime.now(pytz.timezone('America/New_York')).isoformat(),
		"completed_at": "",
	}
	rows.append(new_row)
	write_todos(rows)
	return new_row


def update_todo_status(todo_id: str, status: str) -> None:
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			row["status"] = status
			# Auto-log hours and set completion timestamp when marking as done
			if status == "done":
				# Set completion date (YYYY-MM-DD)
				row["completed_at"] = datetime.now(pytz.timezone('America/New_York')).date().isoformat()
				# Auto-log hours if not already logged
				if float(row.get("hours_logged", 0)) == 0:
					estimated_hours = float(row.get("estimated_hours", 0))
					if estimated_hours == 0:
						# Default to 1 hour if no estimated hours
						estimated_hours = 1.0
						row["estimated_hours"] = "1.00"
					row["hours_logged"] = f"{estimated_hours:.2f}"
			else:
				# Clear completion timestamp if marking as not done
				row["completed_at"] = ""
			break
	write_todos(rows)


def update_todo_hours(todo_id: str, hours_delta: float) -> None:
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			current = float(row.get("hours_logged", 0) or 0)
			row["hours_logged"] = f"{max(0.0, current + hours_delta):.2f}"
			break
	write_todos(rows)


def update_todo_estimated_hours(todo_id: str, estimated_hours) -> None:
	"""Update the estimated hours for a specific todo."""
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			# Convert to float to handle string inputs
			estimated_hours_float = float(estimated_hours) if estimated_hours is not None else 0.0
			row["estimated_hours"] = f"{max(0.0, estimated_hours_float):.2f}"
			break
	write_todos(rows)


def update_todo_due_date(todo_id: str, due_date) -> None:
	"""Update the due date for a specific todo."""
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			# Convert to string format if it's a datetime object
			if hasattr(due_date, 'strftime'):
				row["due_date"] = due_date.strftime('%Y-%m-%d')
			else:
				row["due_date"] = str(due_date)
			break
	write_todos(rows)


def update_todo_completed_at(todo_id: str, completed_at) -> None:
	"""Update the completion timestamp for a specific todo."""
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			# Normalize to date-only YYYY-MM-DD
			value = completed_at
			if hasattr(value, 'strftime'):
				row["completed_at"] = value.strftime('%Y-%m-%d')
			else:
				text = str(value).strip() if value else ""
				if text:
					try:
						dt = dtparser.parse(text)
						row["completed_at"] = dt.date().isoformat()
					except Exception:
						# Fallback: take first 10 chars assuming YYYY-MM-DD prefix
						row["completed_at"] = text[:10]
				else:
					row["completed_at"] = ""
			break
	write_todos(rows)


def delete_todo(todo_id: str) -> None:
	rows = read_todos()
	rows = [r for r in rows if r["id"] != todo_id]
	write_todos(rows)


# --- Timetable helpers ---

def read_timetable() -> List[Dict[str, Any]]:
	ensure_csv_exists()
	rows: List[Dict[str, Any]] = []
	with open(TIMETABLE_CSV_PATH, mode="r", newline="") as f:
		reader = csv.DictReader(f)
		for row in reader:
			rows.append(row)
	return rows


def write_timetable(rows: List[Dict[str, Any]]) -> None:
	ensure_csv_exists()
	with open(TIMETABLE_CSV_PATH, mode="w", newline="") as f:
		writer = csv.DictWriter(f, fieldnames=TIMETABLE_HEADERS)
		writer.writeheader()
		for r in rows:
			writer.writerow(r)


def add_timetable_entry(day: str, start_time: str, end_time: str, activity: str, focus: str) -> Dict[str, Any]:
	rows = read_timetable()
	new_row = {
		"id": generate_ulid(),
		"day": day,
		"start_time": start_time,
		"end_time": end_time,
		"activity": activity.strip(),
		"focus": (focus or "").strip(),
	}
	rows.append(new_row)
	write_timetable(rows)
	return new_row


def delete_timetable_entry(entry_id: str) -> None:
	rows = [r for r in read_timetable() if r["id"] != entry_id]
	write_timetable(rows)


def export_timetable_csv() -> bytes:
	rows = read_timetable()
	from io import StringIO
	sio = StringIO()
	writer = csv.DictWriter(sio, fieldnames=TIMETABLE_HEADERS)
	writer.writeheader()
	for r in rows:
		writer.writerow(r)
	return sio.getvalue().encode("utf-8")


def timetable_template_bytes() -> bytes:
	from io import StringIO
	sio = StringIO()
	writer = csv.DictWriter(sio, fieldnames=TIMETABLE_HEADERS)
	writer.writeheader()
	writer.writerow({
		"id": "",
		"day": "Monday",
		"start_time": "07:00",
		"end_time": "08:00",
		"activity": "Gym + Morning Routine + Breakfast",
		"focus": "Personal well-being",
	})
	return sio.getvalue().encode("utf-8")


def import_timetable_csv(content: bytes, mode: str = "append") -> Dict[str, Any]:
	assert mode in ("append", "replace")
	ensure_csv_exists()
	from io import StringIO
	reader = csv.DictReader(StringIO(content.decode("utf-8")))
	missing = [c for c in TIMETABLE_HEADERS if c not in reader.fieldnames]
	if missing:
		return {"ok": False, "error": f"Missing columns: {', '.join(missing)}"}
	existing = [] if mode == "replace" else read_timetable()
	added = 0
	for row in reader:
		activity = (row.get("activity") or "").strip()
		day = (row.get("day") or "").strip()
		if not activity or not day:
			continue
		existing.append({
			"id": (row.get("id") or "").strip() or generate_ulid(),
			"day": day,
			"start_time": (row.get("start_time") or "").strip(),
			"end_time": (row.get("end_time") or "").strip(),
			"activity": activity,
			"focus": (row.get("focus") or "").strip(),
		})
		added += 1
	write_timetable(existing)
	return {"ok": True, "added": added, "total": len(existing)}


def seed_example_timetable() -> None:
	"""Populate timetable with a predefined weekly schedule derived from the user's example."""
	entries = []
	def add(day, start, end, activity, focus=""):
		entries.append({
			"id": generate_ulid(),
			"day": day,
			"start_time": start,
			"end_time": end,
			"activity": activity,
			"focus": focus,
		})

	# Monday
	add("Monday","07:00","08:00","Gym + Morning Routine + Breakfast","Personal well-being")
	add("Monday","08:00","09:00","Gym + Morning Routine + Breakfast","Personal well-being")
	add("Monday","10:30","11:30","School Project","Data Product Design & Taskconnect")
	add("Monday","11:30","12:30","Break","")
	add("Monday","12:30","13:30","School Work","Cloud Computing")
	add("Monday","13:30","15:00","Lunch","")
	add("Monday","15:00","20:00","Lecture","")

	# Tuesday
	add("Tuesday","07:00","08:00","Morning Routine + Breakfast","Personal well-being")
	add("Tuesday","08:00","09:00","Morning Routine + Breakfast","Personal well-being")
	add("Tuesday","09:00","15:00","Lectures & Commute","")
	add("Tuesday","15:00","20:00","Day End","Half-Day Off")

	# Wednesday
	add("Wednesday","07:00","08:00","Gym","Personal well-being")
	add("Wednesday","08:00","10:30","Morning Routine + Breakfast","Personal well-being")
	add("Wednesday","10:30","11:30","School Project Deep Work","Data Product Design or Driving License")
	add("Wednesday","11:30","12:30","Break","")
	add("Wednesday","12:30","13:30","School Project Deep Work","Cloud Computing")
	add("Wednesday","13:30","15:00","Lunch","")
	add("Wednesday","14:30","15:30","Assignments","Computational Maths Assignment")
	add("Wednesday","15:30","16:30","Break","")
	add("Wednesday","16:30","17:30","Personal Projects","TaskConnect")
	add("Wednesday","17:30","18:30","Dinner / Relax","")
	add("Wednesday","18:30","19:30","Tutorials","Aws Cloud Practitioner")
	add("Wednesday","19:30","20:30","Break","")

	# Thursday
	add("Thursday","07:00","08:00","Gym","Personal well-being")
	add("Thursday","08:00","10:30","Morning Routine + Breakfast","Personal well-being")
	add("Thursday","10:30","11:30","School Project Deep Work","Cloud Computing")
	add("Thursday","11:30","12:30","Break","")
	add("Thursday","12:30","13:30","Personal Projects","Fraud Detection")
	add("Thursday","13:30","14:30","Lunch","")
	add("Thursday","14:30","15:30","Assignments","Computational Maths Lab")
	add("Thursday","15:30","16:30","Break","")
	add("Thursday","16:30","17:30","Personal Projects","TaskConnect")
	add("Thursday","17:30","18:30","Dinner / Relax","")
	add("Thursday","18:30","19:30","Tutorials","Harvad Data Science")
	add("Thursday","19:30","20:30","Break","")

	# Friday
	add("Friday","07:00","08:00","Gym","Personal well-being")
	add("Friday","08:00","10:30","Morning Routine + Breakfast","Personal well-being")
	add("Friday","10:30","11:30","School Work","Computational Maths")
	add("Friday","11:30","12:30","Break","")
	add("Friday","12:30","13:30","School Project Deep Work","Data Product Design")
	add("Friday","13:30","14:30","Lunch","")
	add("Friday","14:30","15:30","Assignments","Cloud Computing")
	add("Friday","15:30","16:30","Break","")
	add("Friday","16:30","17:30","Personal Projects","TaskConnect")
	add("Friday","17:30","18:30","Dinner / Relax","")
	add("Friday","18:30","19:30","Tutorials","Harvad Data Science")
	add("Friday","19:30","20:30","Break","")

	# Saturday
	add("Saturday","07:00","08:00","Gym","Personal well-being")
	add("Saturday","08:00","10:30","Morning Routine + Breakfast","Personal well-being")
	add("Saturday","10:30","11:30","Personal Project Deep Work","TaskConnect")
	add("Saturday","11:30","12:30","Break","")
	add("Saturday","12:30","13:30","Personal Project Deep Work","Fraud Detection")
	add("Saturday","13:30","20:00","Day End","Half-Day Off")

	# Sunday
	add("Sunday","07:00","08:00","Morning Routine + Breakfast","Personal well-being")
	add("Sunday","08:00","10:30","Morning Routine + Breakfast","Personal well-being")
	add("Sunday","10:30","11:30","Weekly Review","Assess Progress")
	add("Sunday","11:30","12:30","Break","")
	add("Sunday","12:30","13:30","Tutorials","Harvad Data Science")
	add("Sunday","13:30","14:30","Lunch","")
	add("Sunday","14:30","15:30","Catch-up / Flex Time","Unfinished labs or projects")
	add("Sunday","15:30","16:30","Break","")
	add("Sunday","16:30","17:30","Catch-up / Flex Time","Unfinished labs or projects")
	add("Sunday","17:30","18:30","Dinner / Relax","")
	add("Sunday","18:30","19:30","Prep Next Week","Set goals")
	add("Sunday","19:30","20:30","Break","")

	write_timetable(entries)


def seed_timetable_from_csv(file_path: str) -> Dict[str, Any]:
	"""Load a human-formatted timetable CSV and convert to canonical rows.

	Expected headers include at least: Day, Time Slot, Activity/Acitivity, Focus.
	If Day is empty, reuse last non-empty day. Time Slot like '7:00 AM - 8:00 AM'.
	Special end keyword 'Day End' maps to 20:00.
	"""
	ensure_csv_exists()
	if not os.path.exists(file_path):
		return {"ok": False, "error": f"File not found: {file_path}"}
	from io import StringIO
	import csv as _csv
	from dateutil import parser as dtparser

	def to_hhmm(text: str) -> str:
		text = (text or "").strip()
		if not text:
			return ""
		if text.lower().startswith("day end"):
			return "20:00"
		# Normalize like '13:30 PM' -> '1:30 PM'
		try:
			# dtparser can handle many formats and AM/PM
			dt = dtparser.parse(text)
			return dt.strftime("%H:%M")
		except Exception:
			return ""

	rows_new: List[Dict[str, Any]] = []
	last_day = None
	with open(file_path, "r", newline="") as f:
		reader = _csv.DictReader(f)
		for r in reader:
			day = (r.get("Day") or "").strip() or last_day
			if not day:
				continue
			last_day = day
			slot = (r.get("Time Slot") or "").strip()
			activity = (r.get("Activity") or r.get("Acitivity") or "").strip()
			focus = (r.get("Focus") or "").strip()
			if not slot and not activity:
				continue
			if "-" not in slot:
				start_s, end_s = "", ""
			else:
				parts = [p.strip() for p in slot.split("-", 1)]
				start_s, end_s = parts[0], parts[1]
			start_hhmm = to_hhmm(start_s)
			end_hhmm = to_hhmm(end_s)
			rows_new.append({
				"id": generate_ulid(),
				"day": day,
				"start_time": start_hhmm,
				"end_time": end_hhmm,
				"activity": activity,
				"focus": focus,
			})

	if not rows_new:
		return {"ok": False, "error": "No rows parsed"}
	write_timetable(rows_new)
	return {"ok": True, "added": len(rows_new)}


# --- Steps helpers ---

def parse_steps(steps_str: str) -> List[Dict[str, Any]]:
	"""Parse steps from a string format. Each line starting with '-' or '✓' is a step."""
	if not steps_str or not steps_str.strip():
		return []
	
	steps = []
	lines = steps_str.strip().split('\n')
	for i, line in enumerate(lines):
		line = line.strip()
		if line.startswith('-') or line.startswith('✓'):
			# Check if step is completed (starts with ✓)
			completed = line.startswith('✓')
			# Remove the prefix and get the description
			step_text = line[1:].strip() if completed else line[1:].strip()
			steps.append({
				"id": f"step_{i}",
				"description": step_text,
				"completed": completed,
				"order": i
			})
	return steps


def format_steps(steps_list: List[Dict[str, Any]]) -> str:
	"""Format steps list back to string format."""
	if not steps_list:
		return ""
	
	lines = []
	for step in sorted(steps_list, key=lambda x: x.get("order", 0)):
		status = "✓" if step.get("completed", False) else "-"
		lines.append(f"{status} {step.get('description', '')}")
	return "\n".join(lines)


def update_todo_step(todo_id: str, step_id: str, completed: bool) -> None:
	"""Update a specific step's completion status and auto-complete todo if all steps done."""
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			steps = parse_steps(row.get("steps", ""))
			for step in steps:
				if step["id"] == step_id:
					step["completed"] = completed
					break
			row["steps"] = format_steps(steps)
			
			# Auto-complete todo if all steps are completed
			if steps and all(step.get("completed", False) for step in steps):
				row["status"] = "done"
				# Set completion date (YYYY-MM-DD)
				row["completed_at"] = datetime.now(pytz.timezone('America/New_York')).date().isoformat()
				# Auto-log hours when auto-completing
				if float(row.get("hours_logged", 0)) == 0:
					estimated_hours = float(row.get("estimated_hours", 0))
					if estimated_hours == 0:
						# Default to 1 hour if no estimated hours
						estimated_hours = 1.0
						row["estimated_hours"] = "1.00"
					row["hours_logged"] = f"{estimated_hours:.2f}"
			
			break
	write_todos(rows)


def get_todo_steps(todo_id: str) -> List[Dict[str, Any]]:
	"""Get steps for a specific todo. If no steps exist but title has dash, auto-create step."""
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			steps = parse_steps(row.get("steps", ""))
			# If no steps but title has dash, auto-create a step and save it
			if not steps and " - " in row.get("title", ""):
				title_parts = row["title"].split(" - ", 1)
				if len(title_parts) > 1:
					step_description = title_parts[1].strip()
					steps = [{
						"id": "step_0",
						"description": step_description,
						"completed": False,
						"order": 0
					}]
					# Save the auto-generated step back to the CSV
					row["steps"] = format_steps(steps)
					write_todos(rows)
			return steps
	return []


def get_todo_progress(todo_id: str) -> Dict[str, Any]:
	"""Get progress information for a todo with steps."""
	steps = get_todo_steps(todo_id)
	if not steps:
		return {"total": 0, "completed": 0, "percentage": 0}
	
	completed = sum(1 for step in steps if step.get("completed", False))
	total = len(steps)
	percentage = (completed / total * 100) if total > 0 else 0
	
	return {
		"total": total,
		"completed": completed,
		"percentage": round(percentage, 1)
	}
