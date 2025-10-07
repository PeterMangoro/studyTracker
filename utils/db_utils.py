import csv
import os
from datetime import datetime
from typing import List, Dict, Any

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
	"created_at",
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
		"created_at": "",
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
		new_row = {
			"id": (row.get("id") or "").strip() or generate_ulid(),
			"title": title_csv,
			"due_date": (row.get("due_date") or "").strip(),
			"estimated_hours": f"{float(row.get('estimated_hours') or 0):.2f}",
			"hours_logged": f"{float(row.get('hours_logged') or 0):.2f}",
			"priority": (row.get("priority") or "Medium").strip() or "Medium",
			"status": (row.get("status") or "todo").strip() or "todo",
			"created_at": (row.get("created_at") or datetime.utcnow().isoformat()),
		}
		existing.append(new_row)
		added += 1

	write_todos(existing)
	return {"ok": True, "added": added, "total": len(existing)}


def add_todo(title: str, due_date: str, estimated_hours: float, priority: str) -> Dict[str, Any]:
	rows = read_todos()
	new_row = {
		"id": generate_ulid(),
		"title": title.strip(),
		"due_date": due_date,
		"estimated_hours": f"{float(estimated_hours):.2f}",
		"hours_logged": f"{0.0:.2f}",
		"priority": priority,
		"status": "todo",
		"created_at": datetime.utcnow().isoformat(),
	}
	rows.append(new_row)
	write_todos(rows)
	return new_row


def update_todo_status(todo_id: str, status: str) -> None:
	rows = read_todos()
	for row in rows:
		if row["id"] == todo_id:
			row["status"] = status
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
