import streamlit as st
import pandas as pd
from datetime import date, timedelta

from utils.db_utils import read_todos, add_todo, update_todo_status, delete_todo, update_todo_hours, ensure_csv_exists
from utils.charts import tasks_by_status_chart, upcoming_deadlines_table, tasks_risk_dataframe

st.set_page_config(page_title="Study Todo Tracker", layout="wide")

if "initialized" not in st.session_state:
	ensure_csv_exists()
	st.session_state.initialized = True
    

st.title("Study Todo Tracker")

with st.sidebar:
	st.header("Add Todo")
	title = st.text_input("Title", placeholder="e.g., Read Chapter 3")
	due = st.date_input("Due date", value=date.today() + timedelta(days=7))
	est_hours = st.number_input("Estimated hours", min_value=0.0, max_value=200.0, value=2.0, step=0.5)
	priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=1)
	if st.button("Add"):
		if not title.strip():
			st.warning("Please provide a title")
		else:
			add_todo(title, due.isoformat(), est_hours, priority)
			st.success("Todo added")

	st.divider()
	st.header("Settings")
	daily_capacity = st.slider("Daily capacity (hours)", min_value=0.0, max_value=8.0, value=2.0, step=0.5)

	st.caption("Tip: Increase capacity if you can do more each day")

	with st.expander("CSV import/export"):
		col1, col2 = st.columns(2)
		with col1:
			if st.button("Download template"):
				from utils.db_utils import csv_template_bytes
				st.download_button("Save template.csv", data=csv_template_bytes(), file_name="todos_template.csv", mime="text/csv")
		with col2:
			if st.button("Export current"):
				from utils.db_utils import export_todos_csv
				st.download_button("Save todos.csv", data=export_todos_csv(), file_name="todos_export.csv", mime="text/csv")

		upload = st.file_uploader("Import CSV", type=["csv"], accept_multiple_files=False)
		mode = st.radio("Import mode", ["append", "replace"], index=0, horizontal=True)
		if upload is not None and st.button("Import"):
			from utils.db_utils import import_todos_csv
			res = import_todos_csv(upload.read(), mode=mode)
			if res.get("ok"):
				st.success(f"Imported {res['added']} items. Total now {res['total']}.")
				st.rerun()
			else:
				st.error(res.get("error", "Import failed"))

		paste_csv = st.text_area("Paste CSV code", height=150, placeholder="id,title,due_date,estimated_hours,hours_logged,priority,status,created_at\n,Example task,2025-10-06,1.0,0.0,Medium,todo,")
		if st.button("Import from pasted CSV"):
			from utils.db_utils import import_todos_csv
			if paste_csv.strip():
				res = import_todos_csv(paste_csv.encode("utf-8"), mode=mode)
				if res.get("ok"):
					st.success(f"Imported {res['added']} items. Total now {res['total']}.")
					st.rerun()
				else:
					st.error(res.get("error", "Import failed"))
			else:
				st.warning("Paste CSV content first")

# Fetch data
rows = read_todos()

# Tabs
tab_dashboard, tab_todos, tab_logs, tab_timetable = st.tabs(["Dashboard", "Todos", "Log Time", "Timetable"])  # noqa: E101 tabs are aligned visually in UI

with tab_todos:
	st.subheader("Your Todos")
	if not rows:
		st.info("No todos yet. Add one from the sidebar.")
	else:
		df = pd.DataFrame(rows)
		def extract_category(title: str) -> str:
			parts = [p.strip() for p in str(title).split("/")]
			return parts[0] if parts and parts[0] else "Uncategorized"
		df["category"] = df["title"].apply(extract_category)
		# Separate active and done todos
		active_df = df[df["status"] == "todo"]
		done_df = df[df["status"] == "done"]
		
		# Active todos by category
		if not active_df.empty:
			for category in active_df["category"].unique():
				st.markdown(f"### {category}")
				cat_rows = active_df[active_df["category"] == category].to_dict(orient="records")
				for row in cat_rows:
					cols = st.columns([7, 2, 2, 1])
					with cols[0]:
						st.write(f"**{row['title']}**")
						st.caption(f"Due {row['due_date']}  •  Est {row['estimated_hours']}h  •  Logged {row['hours_logged']}h  •  Pri {row['priority']}")
					with cols[1]:
						if st.button("Done", key=f"done_{row['id']}"):
							update_todo_status(row["id"], "done")
							st.rerun()
					with cols[2]:
						if st.button("Delete", type="secondary", key=f"del_{row['id']}"):
							delete_todo(row["id"])
							st.rerun()
					with cols[3]:
						st.write("")
		else:
			st.info("No active todos. Great job!")
		
		# Done todos (collapsed)
		if not done_df.empty:
			with st.expander(f"✅ Completed ({len(done_df)} items)", expanded=False):
				for category in done_df["category"].unique():
					st.markdown(f"**{category}**")
					cat_rows = done_df[done_df["category"] == category].to_dict(orient="records")
					for row in cat_rows:
						cols = st.columns([7, 2, 2, 1])
						with cols[0]:
							st.write(f"~~{row['title']}~~")
							st.caption(f"Due {row['due_date']}  •  Est {row['estimated_hours']}h  •  Logged {row['hours_logged']}h")
						with cols[1]:
							if st.button("Reopen", key=f"reopen_{row['id']}"):
								update_todo_status(row["id"], "todo")
								st.rerun()
						with cols[2]:
							if st.button("Delete", type="secondary", key=f"del_done_{row['id']}"):
								delete_todo(row["id"])
								st.rerun()
						with cols[3]:
							st.write("")

with tab_logs:
	st.subheader("Log Time Against a Todo")
	if not rows:
		st.info("No todos to log against.")
	else:
		selected = st.selectbox("Todo", options=[(r["id"], r["title"]) for r in rows], format_func=lambda t: t[1])
		duration = st.number_input("Duration (hours)", min_value=0.0, max_value=12.0, value=1.0, step=0.25)
		if st.button("Log time"):
			selected_id = selected[0] if isinstance(selected, tuple) else selected
			update_todo_hours(selected_id, duration)
			st.success("Time logged")
	
	# Logged hours table
	st.subheader("Logged Hours Summary")
	if rows:
		import pandas as pd
		df_logs = pd.DataFrame(rows)
		# Filter todos with logged hours > 0
		df_logs["hours_logged"] = pd.to_numeric(df_logs["hours_logged"], errors='coerce').fillna(0)
		df_with_hours = df_logs[df_logs["hours_logged"] > 0].copy()
		
		if not df_with_hours.empty:
			# Sort by hours logged (descending)
			df_with_hours = df_with_hours.sort_values("hours_logged", ascending=False)
			# Show relevant columns
			display_cols = ["title", "hours_logged", "estimated_hours", "status", "due_date"]
			st.dataframe(df_with_hours[display_cols], use_container_width=True)
			
			# Total hours summary
			total_logged = df_with_hours["hours_logged"].sum()
			total_estimated = df_logs["estimated_hours"].astype(float).sum()
			col1, col2, col3 = st.columns(3)
			with col1:
				st.metric("Total Hours Logged", f"{total_logged:.1f}")
			with col2:
				st.metric("Total Estimated", f"{total_estimated:.1f}")
			with col3:
				completion_pct = (total_logged / total_estimated * 100) if total_estimated > 0 else 0
				st.metric("Progress", f"{completion_pct:.1f}%")
		else:
			st.info("No hours logged yet. Use the form above to log time against todos.")
	else:
		st.info("No todos to display.")

with tab_dashboard:
	st.subheader("Overview")
	
	# KPIs
	if rows:
		import pandas as pd
		df = pd.DataFrame(rows)
		completed = len(df[df["status"] == "done"])
		remaining = len(df[df["status"] == "todo"])
		overdue = len(df[(df["status"] == "todo") & (pd.to_datetime(df["due_date"]) < pd.to_datetime(date.today()))])
		
		col1, col2, col3, col4 = st.columns(4)
		with col1:
			st.metric("Total Tasks", len(df))
		with col2:
			st.metric("Completed", completed, delta=f"{completed/len(df)*100:.0f}%" if len(df) > 0 else "0%")
		with col3:
			st.metric("Remaining", remaining)
		with col4:
			st.metric("Overdue", overdue, delta_color="inverse")
	
	# Charts
	# Hours logged per day (line chart)
	if rows:
		import plotly.express as px
		df["created_date"] = pd.to_datetime(df["created_at"]).dt.date
		# Convert hours_logged to numeric to avoid string concatenation
		df["hours_logged"] = pd.to_numeric(df["hours_logged"], errors='coerce').fillna(0)
		daily_hours = df.groupby("created_date")["hours_logged"].sum().reset_index()
		if not daily_hours.empty:
			# Round to 1 decimal place
			daily_hours["hours_logged"] = daily_hours["hours_logged"].round(1)
			hours_fig = px.line(daily_hours, x="created_date", y="hours_logged", 
							   title="Hours Logged Per Day", markers=True)
			# Format x-axis to show dates only
			hours_fig.update_xaxes(tickformat="%Y-%m-%d")
			st.plotly_chart(hours_fig, use_container_width=True)
		else:
			st.info("Log some hours to see daily progress")
	else:
		st.info("Add todos to see daily hours")
	
	# Additional insights
	st.subheader("Additional Insights")
	col1, col2 = st.columns(2)
	with col1:
		# Completed vs Uncompleted by category bar chart
		if rows:
			import plotly.express as px
			def extract_category(title: str) -> str:
				parts = [p.strip() for p in str(title).split("/")]
				return parts[0] if parts and parts[0] else "Uncategorized"
			df["category"] = df["title"].apply(extract_category)
			
			# Group by category and status
			category_status = df.groupby(["category", "status"]).size().reset_index(name="count")
			status_fig = px.bar(category_status, x="category", y="count", color="status",
							   title="Completed vs Uncompleted by Category",
							   color_discrete_map={"done": "green", "todo": "orange"})
			st.plotly_chart(status_fig, use_container_width=True)
		else:
			st.info("Add todos to see completion status")
	
	with col2:
		# Completed hours per category (bar chart)
		if rows:
			import plotly.express as px
			def extract_category(title: str) -> str:
				parts = [p.strip() for p in str(title).split("/")]
				return parts[0] if parts and parts[0] else "Uncategorized"
			df["category"] = df["title"].apply(extract_category)
			# Convert hours_logged to numeric and sum by category
			df["hours_logged"] = pd.to_numeric(df["hours_logged"], errors='coerce').fillna(0)
			category_hours = df.groupby("category")["hours_logged"].sum().reset_index()
			category_hours = category_hours[category_hours["hours_logged"] > 0]  # Only show categories with logged hours
			if not category_hours.empty:
				category_hours = category_hours.sort_values("hours_logged", ascending=False)
				hours_fig = px.bar(category_hours, x="category", y="hours_logged",
								 title="Completed Hours by Category")
				st.plotly_chart(hours_fig, use_container_width=True)
			else:
				st.info("Log some hours to see category breakdown")
		else:
			st.info("Add todos to see category hours")

	st.subheader("Risk Analysis")
	risk_df = tasks_risk_dataframe(rows, date.today())
	if not risk_df.empty:
		st.dataframe(risk_df, use_container_width=True)
	else:
		st.info("No risk yet — add due dates and estimates.")

with tab_timetable:
	st.subheader("Weekly Timetable")
	from utils.db_utils import read_timetable, seed_timetable_from_csv
	if st.button("Preload from data/Timetablev1.csv"):
		res = seed_timetable_from_csv("data/Timetablev1.csv")
		if res.get("ok"):
			st.success(f"Loaded {res['added']} rows from Timetablev1.csv")
			st.rerun()
		else:
			st.error(res.get("error", "Preload failed"))
	rows_tt = read_timetable()
	if rows_tt:
		import pandas as pd
		df_view = pd.DataFrame(rows_tt)[["day","start_time","end_time","activity","focus"]]
		# Today's Focus
		from datetime import date as _date
		today_name = _date.today().strftime("%A")
		st.subheader(f"Today's Focus — {today_name}")
		df_today = df_view[df_view["day"] == today_name].copy()
		if df_today.empty:
			st.info("No entries for today.")
		else:
			st.dataframe(df_today[["start_time","end_time","activity","focus"]], use_container_width=True)

		# Weekly Timetable
		st.subheader("Weekly Timetable")
		# Inline editable table (id hidden; order maps to existing rows)
		day_options = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
		edited_df = st.data_editor(
			df_view,
			use_container_width=True,
			num_rows="dynamic",
			column_config={
				"day": st.column_config.SelectboxColumn("Day", options=day_options, required=True),
				"start_time": st.column_config.TextColumn("Start (HH:MM)"),
				"end_time": st.column_config.TextColumn("End (HH:MM)"),
				"activity": st.column_config.TextColumn("Activity", required=True),
				"focus": st.column_config.TextColumn("Focus"),
			},
		)
		from utils.db_utils import write_timetable, generate_ulid, read_timetable as _read_tt
		if st.button("Save timetable changes"):
			existing = _read_tt()
			new_rows = []
			for i, r in edited_df.iterrows():
				row_id = existing[i]["id"] if i < len(existing) else generate_ulid()
				new_rows.append({
					"id": row_id,
					"day": str(r.get("day") or "").strip(),
					"start_time": str(r.get("start_time") or "").strip(),
					"end_time": str(r.get("end_time") or "").strip(),
					"activity": str(r.get("activity") or "").strip(),
					"focus": str(r.get("focus") or "").strip(),
				})
			write_timetable(new_rows)
			st.success("Timetable saved")
			st.rerun()
	else:
		st.info("Click 'Preload from data/Timetablev1.csv' to load your timetable.")
