import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import pytz

from utils.db_utils import read_todos, add_todo, update_todo_status, delete_todo, update_todo_hours, ensure_csv_exists, get_todo_steps, update_todo_step, get_todo_progress
from utils.charts import tasks_by_status_chart, upcoming_deadlines_table, tasks_risk_dataframe

st.set_page_config(page_title="Study Todo Tracker", layout="wide")

# Set timezone to New York
NY_TZ = pytz.timezone('America/New_York')

def get_ny_date():
	"""Get current date in New York timezone"""
	return datetime.now(NY_TZ).date()

def get_ny_datetime():
	"""Get current datetime in New York timezone"""
	return datetime.now(NY_TZ)

if "initialized" not in st.session_state:
	ensure_csv_exists()
	st.session_state.initialized = True
    

st.title("Study Todo Tracker")

with st.sidebar:
	st.header("Add Todo")
	title = st.text_input("Title", placeholder="e.g., Read Chapter 3")
	due = st.date_input("Due date", value=get_ny_date() + timedelta(days=7))
	est_hours = st.number_input("Estimated hours", min_value=0.0, max_value=200.0, value=2.0, step=0.5)
	priority = st.selectbox("Priority", ["Low", "Medium", "High"], index=1)
	steps = st.text_area("Steps (optional)", placeholder="- Step 1\n- Step 2\n- Step 3", height=100, help="Enter each step on a new line starting with '-'")
	if st.button("Add"):
		if not title.strip():
			st.warning("Please provide a title")
		else:
			add_todo(title, due.isoformat(), est_hours, priority, steps)
			st.success("Todo added")

	st.divider()
	st.header("Settings")
	daily_capacity = st.slider("Daily capacity (hours)", min_value=0.0, max_value=8.0, value=2.0, step=0.5)

	st.caption("Tip: Increase capacity if you can do more each day")

	with st.expander("CSV import"):
		# Initialize session state for clearing input
		if "csv_input_clear" not in st.session_state:
			st.session_state.csv_input_clear = False
		
		paste_csv = st.text_area("Paste CSV code", height=150, placeholder="id,title,due_date,estimated_hours,hours_logged,priority,status,steps,created_at\n,Example task,2025-10-06,1.0,0.0,Medium,todo,,", key="csv_input", value="" if st.session_state.csv_input_clear else None)
		mode = st.radio("Import mode", ["append", "replace"], index=0, horizontal=True)
		if st.button("Import from pasted CSV"):
			from utils.db_utils import import_todos_csv
			if paste_csv.strip():
				res = import_todos_csv(paste_csv.encode("utf-8"), mode=mode)
				if res.get("ok"):
					st.success(f"Imported {res['added']} items. Total now {res['total']}.")
					# Trigger clearing the input after successful import
					st.session_state.csv_input_clear = True
					st.rerun()
				else:
					st.error(res.get("error", "Import failed"))
			else:
				st.warning("Paste CSV content first")
		
		# Reset the clear flag after rendering
		if st.session_state.csv_input_clear:
			st.session_state.csv_input_clear = False

# Fetch data
rows = read_todos()

# Tabs
tab_dashboard, tab_todos, tab_logs, tab_timetable = st.tabs(["Dashboard", "Todos", "Log Time", "Timetable"])  # noqa: E101 tabs are aligned visually in UI

with tab_todos:
	
	if not rows:
		st.info("No todos yet. Add one from the sidebar.")
	else:
		df = pd.DataFrame(rows)
		# Ensure completed_at column exists (for backward compatibility)
		if "completed_at" not in df.columns:
			df["completed_at"] = ""
		def extract_category(title: str) -> str:
			title_str = str(title).strip()
			# First try to extract from dash format: "Category - Subcategory"
			if " - " in title_str:
				category = title_str.split(" - ")[0].strip()
				return category if category else "Uncategorized"
			# Second try brackets format: "Category (Subcategory)"
			if "(" in title_str and ")" in title_str:
				category = title_str.split("(")[0].strip()
				return category if category else "Uncategorized"
			# Fallback to slash format: "Category/Subcategory"
			parts = [p.strip() for p in title_str.split("/")]
			return parts[0] if parts and parts[0] else "Uncategorized"
		df["category"] = df["title"].apply(extract_category)
		# Separate active and done todos
		active_df = df[df["status"] == "todo"]
		done_df = df[df["status"] == "done"]
		
		# Check for missed todos (past due date and not completed)
		from datetime import datetime
		today = datetime.now().date()
		missed_todos = []
		active_todos = []
		
		if not active_df.empty:
			for row in active_df.to_dict(orient="records"):
				due_date = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
				if due_date < today:
					missed_todos.append(row)
				else:
					active_todos.append(row)
		
		# Show missed todos first
		if missed_todos:
			st.markdown("### **Missed Todos**")
			for row in missed_todos:
				# Get steps and progress for this todo
				steps = get_todo_steps(row['id'])
				progress = get_todo_progress(row['id'])
				
				# Format display title - if it has steps, show just subcategory, otherwise show full title
				display_title = row['title']
				if steps:
					# Extract subcategory from title like "Cloud Computing (Project) - ..." -> "Project"
					title_parts = row['title'].split('(')
					if len(title_parts) > 1:
						subcategory_part = title_parts[1].split(')')[0]
						display_title = subcategory_part
				
				cols = st.columns([7, 2, 2, 1])
				with cols[0]:
					st.write(f"**{display_title}** ")
					
					# Show steps if they exist
					if steps:
						with st.expander("Steps", expanded=False):
							for step in steps:
								step_cols = st.columns([8, 1, 1])
								with step_cols[0]:
									is_completed = step.get("completed", False)
									if is_completed:
										# Show completed step with strikethrough
										st.markdown(f"~~{step.get('description', '')}~~")
									else:
										# Show pending step normally
										st.write(f"⭕ {step.get('description', '')}")
								with step_cols[1]:
									if not step.get("completed", False):
										if st.button("✓", key=f"missed_step_done_{row['id']}_{step['id']}", help="Mark step as complete"):
											update_todo_step(row['id'], step['id'], True)
											st.rerun()
								with step_cols[2]:
									if step.get("completed", False):
										if st.button("↶", key=f"missed_step_undo_{row['id']}_{step['id']}", help="Mark step as incomplete"):
											update_todo_step(row['id'], step['id'], False)
											st.rerun()
					
						# Show details and due date on same line
						caption_text = f"Est {row['estimated_hours']}h  •  Logged {row['hours_logged']}h  •  Pri {row['priority']}"
						if steps:
							caption_text += f"  •  Steps: {progress['completed']}/{progress['total']} ({progress['percentage']}%)"
						caption_text += f"  •  📅 Due: {row['due_date']} (OVERDUE)"
						# Show completion timestamp if available
						if row.get('completed_at'):
							from datetime import datetime
							try:
								completed_dt = datetime.fromisoformat(row['completed_at'].replace('Z', '+00:00'))
								completed_date = completed_dt.strftime('%Y-%m-%d %H:%M')
								caption_text += f"  •  ✅ Completed: {completed_date}"
							except:
								caption_text += f"  •  ✅ Completed: {row['completed_at']}"
						st.caption(caption_text)
				with cols[1]:
					if st.button("✓", key=f"missed_done_{row['id']}", help="Mark as done"):
						update_todo_status(row["id"], "done")
						st.rerun()
				with cols[2]:
					if st.button("🗑️", type="secondary", key=f"missed_del_{row['id']}", help="Delete todo"):
						delete_todo(row["id"])
						st.rerun()
				with cols[3]:
					st.write("")
		
		# Active todos by category
		if active_todos:
			st.markdown("### 📋 **Active Todos**")
			# Convert back to DataFrame for category grouping
			active_df = pd.DataFrame(active_todos)
			for category in active_df["category"].unique():
				st.markdown(f"### {category}")
				cat_rows = active_df[active_df["category"] == category].to_dict(orient="records")
				for row in cat_rows:
					# Get steps and progress for this todo
					steps = get_todo_steps(row['id'])
					progress = get_todo_progress(row['id'])
					
					# Format display title - if it has steps, show just subcategory, otherwise show full title
					display_title = row['title']
					if steps:
						# Extract subcategory from title like "Cloud Computing (Project) - ..." -> "Project"
						title_parts = row['title'].split('(')
						if len(title_parts) > 1:
							subcategory_part = title_parts[1].split(')')[0]
							display_title = subcategory_part
					
					cols = st.columns([7, 2, 2, 1])
					with cols[0]:
						st.write(f"**{display_title}**")
						
						# Show steps if they exist
						if steps:
							with st.expander("Steps", expanded=False):
								for step in steps:
									step_cols = st.columns([8, 1, 1])
									with step_cols[0]:
										is_completed = step.get("completed", False)
										if is_completed:
											# Show completed step with strikethrough
											st.markdown(f"~~{step.get('description', '')}~~")
										else:
											# Show pending step normally
											st.write(f"⭕ {step.get('description', '')}")
									with step_cols[1]:
										if not step.get("completed", False):
											if st.button("✓", key=f"step_done_{row['id']}_{step['id']}", help="Mark step as complete"):
												update_todo_step(row['id'], step['id'], True)
												st.rerun()
									with step_cols[2]:
										if step.get("completed", False):
											if st.button("↶", key=f"step_undo_{row['id']}_{step['id']}", help="Mark step as incomplete"):
												update_todo_step(row['id'], step['id'], False)
												st.rerun()
						
						# Show details and due date on same line
						caption_text = f"Est {row['estimated_hours']}h  •  Logged {row['hours_logged']}h  •  Pri {row['priority']}"
						if steps:
							caption_text += f"  •  Steps: {progress['completed']}/{progress['total']} ({progress['percentage']}%)"
						caption_text += f"  •  📅 Due: {row['due_date']}"
						# Show completion timestamp if available
						if row.get('completed_at'):
							from datetime import datetime
							try:
								completed_dt = datetime.fromisoformat(row['completed_at'].replace('Z', '+00:00'))
								completed_date = completed_dt.strftime('%Y-%m-%d %H:%M')
								caption_text += f"  •  ✅ Completed: {completed_date}"
							except:
								caption_text += f"  •  ✅ Completed: {row['completed_at']}"
						st.caption(caption_text)
					with cols[1]:
						if st.button("✓", key=f"done_{row['id']}", help="Mark as done"):
							update_todo_status(row["id"], "done")
							st.rerun()
					with cols[2]:
						if st.button("🗑️", type="secondary", key=f"del_{row['id']}", help="Delete todo"):
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
							caption_text = f"Due {row['due_date']}  •  Est {row['estimated_hours']}h  •  Logged {row['hours_logged']}h"
							# Show completion timestamp if available
							if row.get('completed_at'):
								from datetime import datetime
								try:
									completed_dt = datetime.fromisoformat(row['completed_at'].replace('Z', '+00:00'))
									completed_date = completed_dt.strftime('%Y-%m-%d %H:%M')
									caption_text += f"  •  ✅ Completed: {completed_date}"
								except:
									caption_text += f"  •  ✅ Completed: {row['completed_at']}"
							st.caption(caption_text)
						with cols[1]:
							if st.button("↶", key=f"reopen_{row['id']}", help="Reopen todo"):
								update_todo_status(row["id"], "todo")
								st.rerun()
						with cols[2]:
							if st.button("🗑️", type="secondary", key=f"del_done_{row['id']}", help="Delete todo"):
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
			
			# Ensure completed_at column exists (for backward compatibility)
			if "completed_at" not in df_with_hours.columns:
				df_with_hours["completed_at"] = ""
			
			# Show relevant columns
			display_cols = ["title", "hours_logged", "estimated_hours", "status", "due_date", "completed_at"]
			
			# Create editable dataframe
			edited_df = st.data_editor(
				df_with_hours[display_cols], 
				width='stretch',
				num_rows="fixed",
				column_config={
					"title": st.column_config.TextColumn("Title", disabled=True),
					"hours_logged": st.column_config.NumberColumn("Hours Logged", min_value=0.0, step=0.1),
					"estimated_hours": st.column_config.NumberColumn("Estimated Hours", min_value=0.0, step=0.1),
					"status": st.column_config.SelectboxColumn("Status", options=["todo", "done"]),
					"due_date": st.column_config.TextColumn("Due Date"),
					"completed_at": st.column_config.TextColumn("Completed At")
				},
				key="hours_summary_editor"
			)
			
			# Check if data was changed and update accordingly
			if not edited_df.equals(df_with_hours[display_cols]):
				# Find changes and update the database
				from utils.db_utils import update_todo_hours, update_todo_status, update_todo_estimated_hours, update_todo_due_date, update_todo_completed_at
				
				# Get the original data with IDs and reset index for proper alignment
				original_data = df_with_hours[["id"] + display_cols].copy().reset_index(drop=True)
				edited_data = edited_df.copy().reset_index(drop=True)
				edited_data["id"] = original_data["id"]  # Add ID column to edited data
				
				# Compare and update changes by iterating through both DataFrames
				for idx in range(len(original_data)):
					if idx < len(edited_data):
						original_row = original_data.iloc[idx]
						edited_row = edited_data.iloc[idx]
						todo_id = original_row["id"]
						
						# Check hours_logged changes
						if edited_row["hours_logged"] != original_row["hours_logged"]:
							# Calculate the difference
							hours_diff = edited_row["hours_logged"] - original_row["hours_logged"]
							update_todo_hours(todo_id, hours_diff)
						
						# Check estimated_hours changes
						if edited_row["estimated_hours"] != original_row["estimated_hours"]:
							update_todo_estimated_hours(todo_id, edited_row["estimated_hours"])
						
						# Check status changes
						if edited_row["status"] != original_row["status"]:
							update_todo_status(todo_id, edited_row["status"])
						
						# Check due_date changes
						if str(edited_row["due_date"]) != str(original_row["due_date"]):
							update_todo_due_date(todo_id, edited_row["due_date"])
						
						# Check completed_at changes
						if str(edited_row["completed_at"]) != str(original_row["completed_at"]):
							update_todo_completed_at(todo_id, edited_row["completed_at"])
				
				st.success("Changes saved!")
				st.rerun()
			
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
		# Ensure completed_at column exists (for backward compatibility)
		if "completed_at" not in df.columns:
			df["completed_at"] = ""
		completed = len(df[df["status"] == "done"])
		remaining = len(df[df["status"] == "todo"])
		overdue = len(df[(df["status"] == "todo") & (pd.to_datetime(df["due_date"]) < pd.to_datetime(get_ny_date()))])
		
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
		# Convert hours_logged to numeric to avoid string concatenation
		df["hours_logged"] = pd.to_numeric(df["hours_logged"], errors='coerce').fillna(0)
		
		# Filter for completed todos with completion dates and logged hours
		completed_df = df[(df["status"] == "done") & (df["hours_logged"] > 0) & (df["completed_at"].notna()) & (df["completed_at"] != "")]
		
		if not completed_df.empty:
			# Convert completed_at to date (handle mixed formats + timezone)
			completed_df["completed_date"] = (
				pd.to_datetime(completed_df["completed_at"], errors="coerce", utc=True)
				.dt.tz_convert(NY_TZ)
				.dt.tz_localize(None)
				.dt.date
			)
			daily_hours = completed_df.groupby("completed_date")["hours_logged"].sum().reset_index()
			
			# Round to 1 decimal place
			daily_hours["hours_logged"] = daily_hours["hours_logged"].round(1)
			hours_fig = px.line(daily_hours, x="completed_date", y="hours_logged", 
							   title="Hours Logged Per Day (By Completion Date)", markers=True)
			# Format x-axis to show dates only
			hours_fig.update_xaxes(tickformat="%Y-%m-%d")
			st.plotly_chart(hours_fig, width='stretch', config={'displayModeBar': True, 'showLink': False})
		else:
			st.info("Complete some todos with logged hours to see daily progress")
	else:
		st.info("Add todos to see daily hours")
	
	# Additional insights
	st.subheader("Additional Insights")
	
	# Late completion trends chart
	if rows:
		import plotly.express as px
		import plotly.graph_objects as go
		
		# Filter for completed todos with both due dates and completion dates
		completed_with_dates = df[(df["status"] == "done") & (df["completed_at"].notna()) & (df["completed_at"] != "") & (df["due_date"].notna()) & (df["due_date"] != "")]
		
		if not completed_with_dates.empty:
			# Convert dates (robust to mixed formats and timezones)
			completed_with_dates["due_date_parsed"] = pd.to_datetime(
				completed_with_dates["due_date"], errors="coerce"
			)
			completed_with_dates["completed_date_parsed"] = pd.to_datetime(
				completed_with_dates["completed_at"], errors="coerce", utc=True
			).dt.tz_convert(NY_TZ).dt.tz_localize(None)
			
			# Calculate delay in days
			completed_with_dates["delay_days"] = (completed_with_dates["completed_date_parsed"] - completed_with_dates["due_date_parsed"]).dt.days
			
			# Group by delay category
			delay_categories = []
			delay_counts = []
			
			# Early completion (negative delay)
			early = len(completed_with_dates[completed_with_dates["delay_days"] < 0])
			if early > 0:
				delay_categories.append("Early")
				delay_counts.append(early)
			
			# On time (0 delay)
			on_time = len(completed_with_dates[completed_with_dates["delay_days"] == 0])
			if on_time > 0:
				delay_categories.append("On Time")
				delay_counts.append(on_time)
			
			# Late (positive delay)
			late = len(completed_with_dates[completed_with_dates["delay_days"] > 0])
			if late > 0:
				delay_categories.append("Late")
				delay_counts.append(late)
			
			if delay_categories:
				# Show delay statistics
				avg_delay = completed_with_dates["delay_days"].mean()
				max_delay = completed_with_dates["delay_days"].max()
				min_delay = completed_with_dates["delay_days"].min()
				
				st.caption(f"Average delay: {avg_delay:.1f} days | Max delay: {max_delay} days | Earliest completion: {min_delay} days before due")
			else:
				st.info("Complete some todos to see timing trends")
		else:
			st.info("Complete some todos to see timing trends")
	
	col1, col2 = st.columns(2)
	with col1:
		# Completed vs Uncompleted by category bar chart
		if rows:
			import plotly.express as px
			def extract_category(title: str) -> str:
				title_str = str(title).strip()
				# First try to extract from dash format: "Category - Subcategory"
				if " - " in title_str:
					category = title_str.split(" - ")[0].strip()
					return category if category else "Uncategorized"
				# Second try brackets format: "Category (Subcategory)"
				if "(" in title_str and ")" in title_str:
					category = title_str.split("(")[0].strip()
					return category if category else "Uncategorized"
				# Fallback to slash format: "Category/Subcategory"
				parts = [p.strip() for p in title_str.split("/")]
				return parts[0] if parts and parts[0] else "Uncategorized"
			df["category"] = df["title"].apply(extract_category)
			
			# Group by category and status
			category_status = df.groupby(["category", "status"]).size().reset_index(name="count")
			status_fig = px.bar(category_status, x="category", y="count", color="status",
							   title="Completed vs Uncompleted by Category")
			# Update colors manually to avoid deprecation warnings
			status_fig.for_each_trace(lambda trace: trace.update(marker_color='green' if trace.name == 'done' else 'orange'))
			st.plotly_chart(status_fig, width='stretch', config={'displayModeBar': True, 'showLink': False})
		else:
			st.info("Add todos to see completion status")
	
	with col2:
		# Completed vs Estimated hours per category (grouped bar chart)
		if rows:
			import plotly.express as px
			import plotly.graph_objects as go
			def extract_category(title: str) -> str:
				title_str = str(title).strip()
				# First try to extract from dash format: "Category - Subcategory"
				if " - " in title_str:
					category = title_str.split(" - ")[0].strip()
					return category if category else "Uncategorized"
				# Second try brackets format: "Category (Subcategory)"
				if "(" in title_str and ")" in title_str:
					category = title_str.split("(")[0].strip()
					return category if category else "Uncategorized"
				# Fallback to slash format: "Category/Subcategory"
				parts = [p.strip() for p in title_str.split("/")]
				return parts[0] if parts and parts[0] else "Uncategorized"
			df["category"] = df["title"].apply(extract_category)
			# Convert hours to numeric
			df["hours_logged"] = pd.to_numeric(df["hours_logged"], errors='coerce').fillna(0)
			df["estimated_hours"] = pd.to_numeric(df["estimated_hours"], errors='coerce').fillna(0)
			
			# Group by category and sum both hours
			category_hours = df.groupby("category").agg({
				"hours_logged": "sum",
				"estimated_hours": "sum"
			}).reset_index()
			
			# Only show categories with either logged or estimated hours
			category_hours = category_hours[
				(category_hours["hours_logged"] > 0) | 
				(category_hours["estimated_hours"] > 0)
			]
			
			if not category_hours.empty:
				# Sort by total hours (logged + estimated)
				category_hours["total_hours"] = category_hours["hours_logged"] + category_hours["estimated_hours"]
				category_hours = category_hours.sort_values("total_hours", ascending=False)
				
				# Create grouped bar chart
				fig = go.Figure()
				
				# Add completed hours bars
				fig.add_trace(go.Bar(
					name='Completed Hours',
					x=category_hours['category'],
					y=category_hours['hours_logged'],
					marker_color='#2E8B57',  # Sea green
					text=category_hours['hours_logged'].round(1),
					textposition='auto',
				))
				
				# Add estimated hours bars
				fig.add_trace(go.Bar(
					name='Estimated Hours',
					x=category_hours['category'],
					y=category_hours['estimated_hours'],
					marker_color='#FF6B6B',  # Light red
					text=category_hours['estimated_hours'].round(1),
					textposition='auto',
				))
				
				fig.update_layout(
					title='Hours by Category',
					xaxis_title='Category',
					yaxis_title='Hours',
					barmode='group',
					height=400
				)
				
				st.plotly_chart(fig, width='stretch', config={'displayModeBar': True, 'showLink': False})
			else:
				st.info("Add todos with hours to see category breakdown")
		else:
			st.info("Add todos to see category hours")

	st.subheader("Category Timing Analysis")
	
	# Create category timing analysis table
	if rows:
		# Filter for completed todos with both due dates and completion dates
		completed_with_dates = df[(df["status"] == "done") & (df["completed_at"].notna()) & (df["completed_at"] != "") & (df["due_date"].notna()) & (df["due_date"] != "")]
		
		if not completed_with_dates.empty:
			# Convert dates (robust to mixed formats and timezones)
			completed_with_dates["due_date_parsed"] = pd.to_datetime(
				completed_with_dates["due_date"], errors="coerce"
			)
			completed_with_dates["completed_date_parsed"] = pd.to_datetime(
				completed_with_dates["completed_at"], errors="coerce", utc=True
			).dt.tz_convert(NY_TZ).dt.tz_localize(None)
			
			# Calculate delay in days
			completed_with_dates["delay_days"] = (completed_with_dates["completed_date_parsed"] - completed_with_dates["due_date_parsed"]).dt.days
			
			# Add category information
			def extract_category(title: str) -> str:
				title_str = str(title).strip()
				# First try to extract from dash format: "Category - Subcategory"
				if " - " in title_str:
					category = title_str.split(" - ")[0].strip()
					return category if category else "Uncategorized"
				# Second try brackets format: "Category (Subcategory)"
				if "(" in title_str and ")" in title_str:
					category = title_str.split("(")[0].strip()
					return category if category else "Uncategorized"
				# Fallback to slash format: "Category/Subcategory"
				parts = [p.strip() for p in title_str.split("/")]
				return parts[0] if parts and parts[0] else "Uncategorized"
			
			completed_with_dates["category"] = completed_with_dates["title"].apply(extract_category)
			
			# Create timing analysis
			timing_analysis = []
			for category in completed_with_dates["category"].unique():
				category_data = completed_with_dates[completed_with_dates["category"] == category]
				
				# Count on-time (delay <= 0) and missed (delay > 0)
				on_time_count = len(category_data[category_data["delay_days"] <= 0])
				missed_count = len(category_data[category_data["delay_days"] > 0])
				total_count = len(category_data)
				
				# Calculate on-time percentage
				on_time_percentage = (on_time_count / total_count * 100) if total_count > 0 else 0
				
				timing_analysis.append({
					"Category": category,
					"Total Completed": total_count,
					"On Time": on_time_count,
					"Missed Deadline": missed_count,
					"On Time %": f"{on_time_percentage:.1f}%"
				})
			
			# Sort by total completed (descending)
			timing_analysis_df = pd.DataFrame(timing_analysis).sort_values("Total Completed", ascending=False)
			
			# Display the table
			st.dataframe(timing_analysis_df, use_container_width=True)
			
		else:
			st.info("Complete some todos with due dates to see category timing analysis")
	else:
		st.info("Add todos to see category timing analysis")

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
		today_name = get_ny_date().strftime("%A")
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
