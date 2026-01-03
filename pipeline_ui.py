import tkinter as tk
from tkinter import ttk, messagebox
import boto3
import threading
import json
import pyperclip
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from datetime import datetime

# before fixing the ui -- started -- done
# implementing duplicate pipeline functionality --started
class PipelineManagerApp:
    def __init__(self, parent):
        self.parent = parent
        self.all_pipelines = []  # Variable to store all pipeline data
        self.total_pipelines = 0  # Variable to store total pipeline count
        self.last_update = 0
        self.setup_ui()

    def start_thread(self, target_function):
        """Start the specified function in a separate thread."""
        thread = threading.Thread(target=target_function)
        thread.daemon = True
        thread.start()

    def create_backup(self, pipeline_name, backup_type):
        """Create a backup of the pipeline before modification"""
        try:
            # Create backup directory structure if it doesn't exist
            base_dir = os.path.join(os.path.dirname(__file__), "pipeline_ui_backup")
            backup_dir = os.path.join(base_dir, backup_type)

            os.makedirs(backup_dir, exist_ok=True)

            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Create backup filename
            backup_filename = f"{pipeline_name}-{timestamp}-backup.json"
            backup_path = os.path.join(backup_dir, backup_filename)

            return backup_path
        except Exception as e:
            print(f"Warning: Could not create backup directory structure: {str(e)}")
            return None

    def setup_ui(self):
        # AWS Configuration Frame
        config_frame = ttk.LabelFrame(self.parent, text="AWS Configuration", padding="10")
        config_frame.pack(fill="x", padx=10, pady=5)

        # Profile input with default 'admin' value
        ttk.Label(config_frame, text="Profile Name:").pack(side="left")
        self.profile_var = tk.StringVar(value="")
        profile_entry = ttk.Entry(config_frame, textvariable=self.profile_var)
        profile_entry.pack(side="left", padx=5)

        # Region input with default 'ap-southeast-2' value
        ttk.Label(config_frame, text="Region(s):").pack(side="left")
        self.region_var = tk.StringVar(value="")
        region_entry = ttk.Entry(config_frame, textvariable=self.region_var, width=30)
        region_entry.pack(side="left", padx=5)

        # Load button with Return key binding
        self.load_button = ttk.Button(
            config_frame,
            text="Load Pipelines",
            command=lambda: self.start_thread(self.load_pipelines)
        )
        self.load_button.pack(side="left", padx=5)

        # Bind Return/Enter key to load_button
        self.load_button.bind("<Return>",
                              lambda event: self.start_thread(self.load_pipelines) if self.load_button.instate(
                                  ["!disabled"]) else None)

        # Also bind Return key for the entry fields
        profile_entry.bind("<Return>",
                           lambda event: self.start_thread(self.load_pipelines) if self.load_button.instate(
                               ["!disabled"]) else None)
        region_entry.bind("<Return>",
                          lambda event: self.start_thread(self.load_pipelines) if self.load_button.instate(
                              ["!disabled"]) else None)

        # Pipelines Frame
        pipelines_frame = ttk.LabelFrame(self.parent, text="CodePipelines", padding="10")
        pipelines_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Search Frame
        search_frame = ttk.Frame(pipelines_frame)
        search_frame.pack(fill="x", pady=5)

        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.pipeline_search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.pipeline_search_var)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", self.filter_pipelines)

        # Create Treeview for pipelines with requested columns
        self.pipeline_tree = ttk.Treeview(pipelines_frame,
                                          columns=(
                                              "SrNo", "Name", "Version", "Type", "Execution Mode", "Created", "Updated",
                                              "Region"),
                                          show="headings")

        # Configure columns with centered alignment for specific columns
        columns = [
            ("SrNo", "Sr. No.", 50, "center"),
            ("Name", "Name", 300, "w"),
            ("Version", "Version", 40, "center"),
            ("Type", "Type", 40, "center"),
            ("Execution Mode", "Execution Mode", 120, "center"),
            ("Created", "Created", 150, "center"),
            ("Updated", "Updated", 150, "center"),
            ("Region", "Region", 100, "center")
        ]

        for col_id, heading, width, anchor in columns:
            self.pipeline_tree.heading(col_id, text=heading)
            self.pipeline_tree.column(col_id, width=width, anchor=anchor)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(pipelines_frame, orient="vertical", command=self.pipeline_tree.yview)
        self.pipeline_tree.configure(yscrollcommand=scrollbar.set)
        self.pipeline_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create right-click context menu
        self.context_menu = tk.Menu(self.parent, tearoff=0)
        self.context_menu.add_command(label="Edit Environment Variables",
                                      command=self.edit_environment_variables)
        self.context_menu.add_command(label="Duplicate Pipeline",
                                      command=self.duplicate_pipeline)

        # Bind right-click event to show context menu
        self.pipeline_tree.bind("<Button-3>", self.show_context_menu)

        # Progress bar frame
        self.progress_frame = ttk.Frame(self.parent)
        self.progress_frame.pack(fill="x", padx=10, pady=5)

        # Progress bar
        self.progress = ttk.Progressbar(
            self.progress_frame,
            orient="horizontal",
            length=200,
            mode="determinate"
        )
        self.progress.pack(fill="x", expand=True)
        self.progress_label = ttk.Label(
            self.progress_frame,
            text="Ready",
            anchor="center"
        )
        self.progress_label.pack(fill="x")
        self.progress_frame.pack_forget()  # Hide initially

        # Create a style for the buttons
        style = ttk.Style()
        style.configure("Custom.TButton",
                        background="#f0f0f0",
                        foreground="black",
                        font=("Arial", 10),
                        padding=(10, 5))

        style.map("Custom.TButton",
                  background=[("active", "#d9d9d9"), ("disabled", "#e0e0e0")],
                  foreground=[("active", "black"), ("disabled", "#a0a0a0")],
                  relief=[("pressed", "sunken")])

        # Buttons Frame
        buttons_frame = ttk.Frame(self.parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)

        # Action buttons with custom style
        self.update_button = ttk.Button(
            buttons_frame,
            text="Update Pipeline",
            style="Custom.TButton",
            command=self.show_pipeline_json
        )
        self.update_button.pack(side="left", padx=5, pady=8)
        self.update_button.bind("<Return>",
                                lambda event: self.show_pipeline_json() if self.update_button.instate(
                                    ["!disabled"]) else None)

        self.refresh_button = ttk.Button(
            buttons_frame,
            text="Refresh",
            style="Custom.TButton",
            command=lambda: self.start_thread(self.load_pipelines)
        )
        self.refresh_button.pack(side="left", padx=5, pady=8)
        self.refresh_button.bind("<Return>",
                                 lambda event: self.load_pipelines() if self.refresh_button.instate(
                                     ["!disabled"]) else None)

        # Pipeline Link buttons
        self.copy_pipeline_button = ttk.Button(
            buttons_frame,
            text="Copy Pipeline Link",
            style="Custom.TButton",
            command=self.copy_pipeline_link
        )
        self.copy_pipeline_button.pack(side="left", padx=5, pady=8)
        self.copy_pipeline_button.bind("<Return>",
                                       lambda event: self.copy_pipeline_link() if self.copy_pipeline_button.instate(
                                           ["!disabled"]) else None)

        self.open_pipeline_button = ttk.Button(
            buttons_frame,
            text="Open Pipeline Link",
            style="Custom.TButton",
            command=self.open_pipeline_link
        )
        self.open_pipeline_button.pack(side="left", padx=5, pady=8)
        self.open_pipeline_button.bind("<Return>",
                                       lambda event: self.open_pipeline_link() if self.open_pipeline_button.instate(
                                           ["!disabled"]) else None)

        # Repository Link buttons
        self.copy_repo_button = ttk.Button(
            buttons_frame,
            text="Copy Repository Link",
            style="Custom.TButton",
            command=self.copy_repository_link
        )
        self.copy_repo_button.pack(side="left", padx=5, pady=8)
        self.copy_repo_button.bind("<Return>",
                                   lambda event: self.copy_repository_link() if self.copy_repo_button.instate(
                                       ["!disabled"]) else None)

        self.open_repo_button = ttk.Button(
            buttons_frame,
            text="Open Repository Link",
            style="Custom.TButton",
            command=self.open_repository_link
        )
        self.open_repo_button.pack(side="left", padx=5, pady=8)
        self.open_repo_button.bind("<Return>",
                                   lambda event: self.open_repository_link() if self.open_repo_button.instate(
                                       ["!disabled"]) else None)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.parent, textvariable=self.status_var,
                               relief="sunken", padding=(10, 2))
        status_bar.pack(fill="x", padx=10, pady=5)

        # Enable buttons initially
        self.change_button_state("normal")

    def show_context_menu(self, event):
        """Show the context menu on right-click"""
        item = self.pipeline_tree.identify_row(event.y)
        if item:
            self.pipeline_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def duplicate_pipeline(self):
        """Duplicate the selected pipeline with a new name"""
        pipeline_name, region, item = self.get_selected_pipeline_details()
        if not pipeline_name or not region:
            return

        # Create a new window for duplication
        dup_window = tk.Toplevel(self.parent)
        dup_window.title(f"Duplicate Pipeline: {pipeline_name}")
        dup_window.geometry("400x200")

        # Main frame
        main_frame = ttk.Frame(dup_window, padding="10")
        main_frame.pack(fill="both", expand=True)

        # Original pipeline name (non-editable)
        ttk.Label(main_frame, text="Original Pipeline:").pack(anchor="w")
        orig_entry = ttk.Entry(main_frame, state="readonly")
        orig_entry.pack(fill="x", pady=(0, 10))
        orig_entry.config(state="normal")
        orig_entry.insert(0, pipeline_name)
        orig_entry.config(state="readonly")

        # New pipeline name
        ttk.Label(main_frame, text="New Pipeline Name:").pack(anchor="w")
        self.new_pipeline_name_var = tk.StringVar()
        new_name_entry = ttk.Entry(main_frame, textvariable=self.new_pipeline_name_var)
        new_name_entry.pack(fill="x", pady=(0, 10))

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=10)

        # Duplicate button
        dup_button = ttk.Button(
            button_frame,
            text="Duplicate Pipeline",
            command=lambda: self.perform_pipeline_duplication(pipeline_name, region, dup_window)
        )
        dup_button.pack()

        # Bind Enter key to duplicate button
        new_name_entry.bind("<Return>",
                            lambda event: self.perform_pipeline_duplication(pipeline_name, region, dup_window))

    def perform_pipeline_duplication(self, original_name, region, window):
        """Perform the actual pipeline duplication"""
        new_name = self.new_pipeline_name_var.get().strip()

        if not new_name:
            messagebox.showwarning("Warning", "Please enter a new pipeline name", parent=window)
            return

        if new_name == original_name:
            messagebox.showwarning("Warning", "New pipeline name must be different from the original", parent=window)
            return

        # Add confirmation dialog
        confirm_message = (
            f"You are about to duplicate pipeline '{original_name}' as '{new_name}'.\n\n"
            "This will create a new pipeline with the same configuration.\n"
            "Do you want to continue?"
        )

        if not messagebox.askyesno(
                "Confirm Duplication",
                message=confirm_message,
                icon='question',
                parent=window,
                default='no'
        ):
            return  # User clicked No, abort the operation

        try:
            session = boto3.Session(
                profile_name=self.profile_var.get(),
                region_name=region
            )
            client = session.client('codepipeline')

            # Get the original pipeline definition
            response = client.get_pipeline(name=original_name)
            pipeline_def = response['pipeline']

            # Update the pipeline name in the definition
            pipeline_def['name'] = new_name

            # Create the new pipeline
            client.create_pipeline(pipeline=pipeline_def)

            messagebox.showinfo("Success", f"Pipeline duplicated successfully as '{new_name}'", parent=window)
            window.destroy()

            # Refresh the pipeline list
            self.start_thread(self.load_pipelines)

        except client.exceptions.PipelineNameInUseException:
            messagebox.showerror("Error", f"A pipeline with name '{new_name}' already exists", parent=window)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate pipeline: {str(e)}", parent=window)

    def edit_environment_variables(self):
        """Open a window to edit environment variables for the selected pipeline"""
        pipeline_name, region, item = self.get_selected_pipeline_details()
        if not pipeline_name or not region:
            return

        try:
            session = boto3.Session(
                profile_name=self.profile_var.get(),
                region_name=region
            )
            client = session.client('codepipeline')

            # Get pipeline definition
            response = client.get_pipeline(name=pipeline_name)
            pipeline_def = response['pipeline']

            # Create edit window
            edit_window = tk.Toplevel(self.parent)
            edit_window.title(f"Edit Environment Variables - {pipeline_name}")
            edit_window.geometry("800x750")

            # Main container frame
            main_frame = ttk.Frame(edit_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)

            # # Title label
            # ttk.Label(
            #     main_frame,
            #     text=f"Environment variable updating for: {pipeline_name} pipeline",
            #     font=('Arial', 10, 'bold')
            # ).pack(pady=5)

            # Create a frame for the scrollable content
            scroll_frame = ttk.Frame(main_frame)
            scroll_frame.pack(fill="both", expand=True)

            # Create a canvas and scrollbar
            canvas = tk.Canvas(scroll_frame, highlightthickness=0)
            scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)  # Apply the style here

            # Configure the canvas
            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Pack the scrollbar and canvas
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Make scrollbar always visible
            canvas.bind("<Enter>", lambda e: canvas.configure(yscrollcommand=scrollbar.set))
            canvas.bind("<Leave>", lambda e: canvas.configure(yscrollcommand=None))

            # Store the canvas and scrollable_frame for later reference
            self.edit_window_canvas = canvas
            self.edit_window_scrollable_frame = scrollable_frame

            # Store entry widgets and their associated action names
            self.env_var_entries = []
            env_vars_found = False

            # Create a frame to hold all variable entries
            self.variables_frame = ttk.Frame(scrollable_frame)
            self.variables_frame.pack(fill="x", padx=5, pady=5)

            # Find all environment variables in the pipeline stages
            for stage in pipeline_def['stages']:
                for action in stage['actions']:
                    if 'configuration' in action and 'EnvironmentVariables' in action['configuration']:
                        env_vars_str = action['configuration']['EnvironmentVariables']
                        env_vars = []

                        try:
                            if isinstance(env_vars_str, str):
                                try:
                                    env_vars = json.loads(env_vars_str)
                                except json.JSONDecodeError:
                                    if isinstance(env_vars_str, list):
                                        env_vars = env_vars_str
                                    else:
                                        continue

                            if isinstance(env_vars, list):
                                action_frame = ttk.Frame(self.variables_frame)
                                action_frame.pack(fill="x", pady=(10, 5))

                                ttk.Label(
                                    action_frame,
                                    text=f"Action: {action['name']} variables.",
                                    font=('Arial', 9, 'underline')
                                ).pack(anchor="w")

                                header_frame = ttk.Frame(self.variables_frame)
                                header_frame.pack(fill="x", padx=5, pady=2)

                                ttk.Label(header_frame, text="Variable Name", width=30, font=('Arial', 9, 'bold')).pack(
                                    side="left", padx=5)
                                ttk.Label(header_frame, text="Variable Value", width=40,
                                          font=('Arial', 9, 'bold')).pack(
                                    side="left", padx=5)
                                ttk.Label(header_frame, text="Action", width=10, font=('Arial', 9, 'bold')).pack(
                                    side="left", padx=5)

                                for var_dict in env_vars:
                                    if isinstance(var_dict, dict) and 'name' in var_dict and 'value' in var_dict:
                                        self._create_var_entry_row(var_dict, action['name'], stage['name'])
                                        env_vars_found = True

                        except Exception as e:
                            ttk.Label(
                                self.variables_frame,
                                text=f"Error parsing variables for action {action['name']}: {str(e)}",
                                foreground="red"
                            ).pack(pady=5)
                            continue

            # Add variable button
            add_var_frame = ttk.Frame(scrollable_frame)
            add_var_frame.pack(fill="x", pady=10)
            ttk.Button(
                add_var_frame,
                text=" ➕ Add New Variable ",
                command=lambda: self.add_new_env_var(pipeline_def)
            ).pack()

            if not env_vars_found:
                ttk.Label(
                    self.variables_frame,
                    text="No editable environment variables found in this pipeline",
                    foreground="blue"
                ).pack(pady=20)

            # Control buttons frame
            control_frame = ttk.Frame(main_frame)
            control_frame.pack(fill="x", pady=10)

            # Release checkbox
            self.release_change_var = tk.BooleanVar()
            ttk.Checkbutton(
                control_frame,
                text="Release the changes after pipeline is updated",
                variable=self.release_change_var
            ).pack(pady=5)

            # Update button
            ttk.Button(
                control_frame,
                text="Update Pipeline",
                command=lambda: self.confirm_update_pipeline(pipeline_name, region, pipeline_def, edit_window)
            ).pack(pady=5)

            canvas.update_idletasks()
            canvas.yview_moveto(0)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get pipeline details: {str(e)}")

    def confirm_update_pipeline(self, pipeline_name, region, pipeline_def, window):
        """Show confirmation dialog before updating pipeline"""
        # Determine if we're releasing changes based on the checkbox
        will_release = self.release_change_var.get()

        # Create dynamic message
        base_message = f"Are you sure you want to update the pipeline: [{pipeline_name}] with changes?"
        release_message = "\n\nNote: The Pipeline will be Triggerd with changes." if will_release else "\n\nNote: The Pipeline will NOT be Triggered."

        ask_message = base_message + release_message

        if messagebox.askyesno(
                "Confirm Update",
                message=ask_message,
                icon='question',
                parent=window,
                default='no'
        ):
            # Pass the release flag to the update method
            self.update_pipeline_env_vars(pipeline_name, region, pipeline_def, window)

    def _create_var_entry_row(self, var_dict, action_name, stage_name):
        """Helper method to create a variable entry row"""
        self.style = ttk.Style()
        self.style.configure("Red.TButton", foreground="red")

        var_frame = ttk.Frame(self.variables_frame)
        var_frame.pack(fill="x", padx=5, pady=2)

        # Variable name
        name_entry = ttk.Entry(var_frame, width=30)
        if var_dict['name']:  # Only insert if not empty
            name_entry.insert(0, var_dict['name'])
        name_entry.pack(side="left", padx=5)

        # Variable value
        value_entry = ttk.Entry(var_frame, width=50)
        if var_dict['value']:  # Only insert if not empty
            value_entry.insert(0, var_dict['value'])
        value_entry.pack(side="left", padx=5)

        delete_text = "  Delete 🗑️" if "🗑️" else "Delete"

        # Delete button
        delete_btn = ttk.Button(
            var_frame,
            text=delete_text,
            width=10,
            command=lambda f=var_frame, n=name_entry, v=value_entry: self.delete_env_var_entry(f, n, v),
            style="Red.TButton"  # Add this line
        )
        delete_btn.pack(side="left", padx=5)

        # Store the entries with action reference
        self.env_var_entries.append({
            'action_name': action_name,
            'stage_name': stage_name,
            'name_entry': name_entry,
            'value_entry': value_entry,
            'original_name': var_dict['name'],
            'var_frame': var_frame
        })

    def add_new_env_var(self, pipeline_def):
        """Add a new empty environment variable entry"""
        # Find the first action that has environment variables
        target_action = None
        target_stage = None

        for stage in pipeline_def['stages']:
            for action in stage['actions']:
                if 'configuration' in action and 'EnvironmentVariables' in action['configuration']:
                    target_action = action['name']
                    target_stage = stage['name']
                    break
            if target_action:
                break

        if not target_action:
            messagebox.showwarning("Warning", "No action with environment variables found to add to")
            return

        # Create new entry with empty values
        self._create_var_entry_row({
            'name': "",
            'value': ""
        }, target_action, target_stage)

        # Scroll to the bottom of the canvas
        self.edit_window_canvas.update_idletasks()
        self.edit_window_canvas.yview_moveto(1.0)

    def delete_env_var_entry(self, frame, name_entry, value_entry):
        """Remove an environment variable entry from the UI"""
        frame.pack_forget()
        frame.destroy()

        # Remove from our tracking list
        for entry in self.env_var_entries[:]:
            if entry['name_entry'] == name_entry and entry['value_entry'] == value_entry:
                self.env_var_entries.remove(entry)

    def update_pipeline_env_vars(self, pipeline_name, region, pipeline_def, window):
        """Update the pipeline with modified environment variables"""
        try:
            # Create backup before updating
            backup_path = self.create_backup(pipeline_name, "edit_enviorment_variables_backup")
            if backup_path:
                try:
                    with open(backup_path, 'w') as f:
                        json.dump(pipeline_def, f, indent=2)
                except Exception as e:
                    print(f"Warning: Could not create backup: {str(e)}")

            # Create a session and client
            session = boto3.Session(
                profile_name=self.profile_var.get(),
                region_name=region
            )
            client = session.client('codepipeline')

            # Track which actions we've processed to avoid duplicates
            processed_actions = set()

            # Update environment variables in the pipeline definition
            for entry in self.env_var_entries:
                action_key = f"{entry['stage_name']}_{entry['action_name']}"
                if action_key in processed_actions:
                    continue

                # Find the action in the pipeline definition
                for stage in pipeline_def['stages']:
                    for action in stage['actions']:
                        if (action['name'] == entry['action_name'] and
                                stage['name'] == entry['stage_name'] and
                                'configuration' in action and
                                'EnvironmentVariables' in action['configuration']):

                            # Collect all variables for this action
                            action_vars = []
                            for e in self.env_var_entries:
                                if e['action_name'] == entry['action_name'] and e['stage_name'] == entry['stage_name']:
                                    action_vars.append({
                                        'name': e['name_entry'].get(),
                                        'value': e['value_entry'].get(),
                                        'type': 'PLAINTEXT'  # Default type
                                    })

                            # Update the configuration
                            action['configuration']['EnvironmentVariables'] = json.dumps(action_vars)
                            processed_actions.add(action_key)
                            break

            # Update the pipeline
            client.update_pipeline(pipeline=pipeline_def)

            # Check if we should release the change
            if self.release_change_var.get():
                client.start_pipeline_execution(name=pipeline_name)
                messagebox.showinfo("Success", "Pipeline updated and new release started successfully")
            else:
                messagebox.showinfo("Success", "Pipeline updated successfully (no new release started)")

            window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update pipeline: {str(e)}")

    # [Rest of your existing methods...]
    # get_selected_pipeline_details, copy_pipeline_link, open_pipeline_link,
    # get_repository_details, copy_repository_link, open_repository_link,
    # change_button_state, show_status_message, update_progress,
    # update_progress_incremental, filter_pipelines, _batch_insert_pipelines,
    # get_pipelines_in_region, load_pipelines, show_pipeline_json,
    # update_pipeline


    def get_selected_pipeline_details(self):
        """Get details of the selected pipeline"""
        selected = self.pipeline_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a pipeline first")
            return None, None, None

        item = self.pipeline_tree.item(selected[0])
        pipeline_name = item['values'][1]
        region = item['values'][7]

        return pipeline_name, region, item

    def copy_pipeline_link(self):
        """Copy AWS console link for the selected pipeline to clipboard"""
        pipeline_name, region, _ = self.get_selected_pipeline_details()
        if not pipeline_name or not region:
            return

        aws_url = f"https://{region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipeline_name}/view?region={region}"

        try:
            pyperclip.copy(aws_url)
            messagebox.showinfo("Success", "Pipeline link copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy pipeline link: {str(e)}")

    def open_pipeline_link(self):
        """Open AWS console link for the selected pipeline in browser"""
        pipeline_name, region, _ = self.get_selected_pipeline_details()
        if not pipeline_name or not region:
            return

        aws_url = f"https://{region}.console.aws.amazon.com/codesuite/codepipeline/pipelines/{pipeline_name}/view?region={region}"

        try:
            webbrowser.open(aws_url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open pipeline link: {str(e)}")

    def get_repository_details(self, pipeline_name, region):
        """Get repository and branch details for a pipeline"""
        try:
            session = boto3.Session(
                profile_name=self.profile_var.get(),
                region_name=region
            )
            client = session.client('codepipeline')

            # Get pipeline definition
            response = client.get_pipeline(name=pipeline_name)
            pipeline_def = response['pipeline']

            # Find the CodeCommit source action
            for stage in pipeline_def['stages']:
                for action in stage['actions']:
                    if action['actionTypeId']['category'] == 'Source' and \
                            action['actionTypeId']['provider'] == 'CodeCommit':
                        # Extract repository and branch from configuration
                        config = action['configuration']
                        repo_name = config.get('RepositoryName', '')
                        branch_name = config.get('BranchName', 'master')  # Default to master if not specified
                        return repo_name, branch_name

            return None, None

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get pipeline details: {str(e)}")
            return None, None

    def copy_repository_link(self):
        """Copy repository link to clipboard"""
        pipeline_name, region, _ = self.get_selected_pipeline_details()
        if not pipeline_name or not region:
            return

        repo_name, branch_name = self.get_repository_details(pipeline_name, region)
        if not repo_name:
            messagebox.showwarning("Warning", "No CodeCommit repository found for this pipeline")
            return

        repo_url = f"https://{region}.console.aws.amazon.com/codesuite/codecommit/repositories/{repo_name}/browse/refs/heads/{branch_name}?region={region}"

        try:
            pyperclip.copy(repo_url)
            messagebox.showinfo("Success", "Repository link copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy repository link: {str(e)}")

    def open_repository_link(self):
        """Open repository link in browser"""
        pipeline_name, region, _ = self.get_selected_pipeline_details()
        if not pipeline_name or not region:
            return

        repo_name, branch_name = self.get_repository_details(pipeline_name, region)
        if not repo_name:
            messagebox.showwarning("Warning", "No CodeCommit repository found for this pipeline")
            return

        repo_url = f"https://{region}.console.aws.amazon.com/codesuite/codecommit/repositories/{repo_name}/browse/refs/heads/{branch_name}?region={region}"

        try:
            webbrowser.open(repo_url)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open repository link: {str(e)}")

    def change_button_state(self, state):
        """Enable/disable buttons and search entry during operations"""
        widgets = [
            self.load_button,
            self.update_button,
            self.refresh_button,
            self.copy_pipeline_button,
            self.open_pipeline_button,
            self.copy_repo_button,
            self.open_repo_button,
            self.search_entry
        ]
        for widget in widgets:
            widget["state"] = state

    def show_status_message(self, message):
        """Update status bar message"""
        self.status_var.set(message)
        self.parent.update()

    def update_progress(self, current, total):
        """Update progress bar and label"""
        self.progress["value"] = (current / total) * 100
        self.progress_label.config(text=f"Loaded {current} of {total} pipelines")
        self.parent.update()

    def update_progress_incremental(self, count):
        """Update progress without knowing total (smoother animation)"""
        if not hasattr(self, 'last_update') or time.time() - self.last_update > 0.1:
            self.progress["value"] = (self.progress["value"] + 5) % 100
            self.progress_label.config(text=f"Loading pipelines... ({count} found)")
            self.last_update = time.time()

    def filter_pipelines(self, event=None):
        """Filter pipelines from stored data based on search term"""
        search_term = self.pipeline_search_var.get().lower()

        # Clear current treeview
        for item in self.pipeline_tree.get_children():
            self.pipeline_tree.delete(item)

        # If search is empty, show all pipelines
        if not search_term.strip():
            self._batch_insert_pipelines(self.all_pipelines)
            return

        # Filter from stored data
        filtered_pipelines = [p for p in self.all_pipelines if search_term in p['name'].lower()]
        self._batch_insert_pipelines(filtered_pipelines)

    def _batch_insert_pipelines(self, pipelines):
        """Insert pipelines in batches for better Treeview performance"""
        # Clear existing items first
        self.pipeline_tree.delete(*self.pipeline_tree.get_children())

        # Insert all items
        for pipeline in pipelines:
            self.pipeline_tree.insert('', 'end', values=(
                pipeline['sr_no'],
                pipeline['name'],
                pipeline['version'],
                pipeline['type'],
                pipeline['execution_mode'],
                pipeline['created'],
                pipeline['updated'],
                pipeline['region']
            ))

    def get_pipelines_in_region(self, profile, region):
        """Get all pipelines in a specific region using paginator (optimized version)"""
        try:
            session = boto3.Session(profile_name=profile, region_name=region)
            client = session.client('codepipeline')
            paginator = client.get_paginator('list_pipelines')

            pipelines = []
            for page in paginator.paginate():
                pipelines.extend(page['pipelines'])

                # Update progress as we get batches
                self.parent.after(100, self.update_progress_incremental, len(pipelines))

            # Format all pipelines at once
            formatted_pipelines = []
            for pipeline in pipelines:
                created = pipeline.get('created', '')
                updated = pipeline.get('updated', '')

                formatted_pipelines.append({
                    'name': pipeline['name'],
                    'version': pipeline.get('version', ''),
                    'type': pipeline.get('pipelineType', ''),
                    'execution_mode': pipeline.get('executionMode', ''),
                    'created': created.strftime('%Y-%m-%d %H:%M:%S') if created else '',
                    'updated': updated.strftime('%Y-%m-%d %H:%M:%S') if updated else '',
                    'region': region
                })

            return region, formatted_pipelines

        except Exception as e:
            print(f"Error in {region}: {str(e)}")
            return region, []

    def load_pipelines(self):
        """Load pipelines in a background thread to keep UI responsive"""
        self.change_button_state("disabled")
        self.pipeline_search_var.set("")  # Clear search filter
        self.search_entry.config(state="disabled")
        self.show_status_message("Loading pipelines...")

        # Show indeterminate progress bar initially
        self.progress_frame.pack(fill="x", padx=10, pady=5)
        self.progress.config(mode="indeterminate")
        self.progress.start()
        self.progress_label.config(text="Discovering pipelines...")
        self.parent.update()

        try:
            profile = self.profile_var.get()
            regions = [r.strip() for r in self.region_var.get().split(',') if r.strip()]

            if not profile or not regions:
                messagebox.showwarning("Warning", "Please provide both profile and region(s)")
                return

            # Clear existing items
            self.pipeline_tree.delete(*self.pipeline_tree.get_children())
            self.all_pipelines = []

            # Switch to determinate progress when we start getting real data
            self.progress.stop()
            self.progress.config(mode="determinate", value=0)

            # Use ThreadPoolExecutor to fetch pipelines in parallel
            with ThreadPoolExecutor(max_workers=min(10, len(regions) * 2)) as executor:
                futures = {executor.submit(self.get_pipelines_in_region, profile, region): region
                           for region in regions}

                sr_no = 1
                for future in as_completed(futures):
                    region, pipelines = future.result()

                    for pipeline in pipelines:
                        pipeline_data = {
                            'sr_no': sr_no,
                            'name': pipeline['name'],
                            'version': pipeline['version'],
                            'type': pipeline['type'],
                            'execution_mode': pipeline['execution_mode'],
                            'created': pipeline['created'],
                            'updated': pipeline['updated'],
                            'region': pipeline['region']
                        }

                        self.all_pipelines.append(pipeline_data)
                        sr_no += 1

                    # Batch update the treeview periodically
                    if sr_no % 20 == 0:
                        self.parent.after(10, self._batch_insert_pipelines, self.all_pipelines)

            # Final update with all pipelines
            self.parent.after(10, self._batch_insert_pipelines, self.all_pipelines)
            self.parent.after(10, self.show_status_message,
                              f"Loaded {len(self.all_pipelines)} pipelines across {len(regions)} region(s)")

        except Exception as e:
            self.parent.after(10, messagebox.showerror, "Error", f"Failed to load pipelines: {str(e)}")
            self.parent.after(10, self.show_status_message, "Error loading pipelines")
        finally:
            self.parent.after(10, self.change_button_state, "normal")
            self.parent.after(10, lambda: self.search_entry.config(state="normal"))
            self.parent.after(10, self.progress.stop)
            self.parent.after(10, self.progress_frame.pack_forget)

    def show_pipeline_json(self):
        selected = self.pipeline_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a pipeline to update")
            return

        pipeline_name = self.pipeline_tree.item(selected[0])['values'][1]
        region = self.pipeline_tree.item(selected[0])['values'][7]  # Region is now at index 7

        edit_window = tk.Toplevel(self.parent)
        edit_window.title(f"Edit Pipeline: {pipeline_name}")
        edit_window.geometry("800x600")

        try:
            session = boto3.Session(
                profile_name=self.profile_var.get(),
                region_name=region
            )
            codepipeline_client = session.client('codepipeline')

            pipeline_def = codepipeline_client.get_pipeline(name=pipeline_name)
            pipeline_json = json.dumps(pipeline_def['pipeline'], indent=2)

            # Main container frame
            container = ttk.Frame(edit_window)
            container.pack(fill="both", expand=True, padx=10, pady=10)

            # Create vertical scrollbar
            v_scroll = ttk.Scrollbar(container, orient="vertical")
            v_scroll.pack(side="right", fill="y")

            # Create horizontal scrollbar
            h_scroll = ttk.Scrollbar(container, orient="horizontal")
            h_scroll.pack(side="bottom", fill="x")

            # Create text widget
            self.json_text = tk.Text(
                container,
                wrap="none",
                yscrollcommand=v_scroll.set,
                xscrollcommand=h_scroll.set,
                font=('Consolas', 10),
                undo=True,
                maxundo=-1,
                padx=5, pady=5
            )
            self.json_text.pack(fill="both", expand=True)

            # Configure scrollbars
            v_scroll.config(command=self.json_text.yview)
            h_scroll.config(command=self.json_text.xview)

            # Insert JSON content
            self.json_text.insert("1.0", pipeline_json)

            # Add checkbox for release change
            self.release_change_var = tk.BooleanVar()
            release_checkbox = ttk.Checkbutton(
                edit_window,
                text="Release change after updating the pipeline",
                variable=self.release_change_var
            )
            release_checkbox.pack(pady=5)

            # Add some padding at the bottom
            ttk.Frame(edit_window, height=10).pack()

            # Update button frame
            button_frame = ttk.Frame(edit_window)
            button_frame.pack(fill="x", padx=10, pady=10)

            update_btn = ttk.Button(
                button_frame,
                text="Update Pipeline",
                command=lambda: self.update_pipeline(pipeline_name, region, edit_window)
            )
            update_btn.pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get pipeline definition: {str(e)}")
            edit_window.destroy()

    def update_pipeline(self, pipeline_name, region, window):
        self.change_button_state("disabled")
        self.show_status_message(f"Updating pipeline {pipeline_name}...")

        try:
            new_json = self.json_text.get("1.0", "end-1c")
            pipeline_def = json.loads(new_json)

            # Create backup before updating
            backup_path = self.create_backup(pipeline_name, "update_pipeline_backup")
            if backup_path:
                try:
                    with open(backup_path, 'w') as f:
                        json.dump(pipeline_def, f, indent=2)
                except Exception as e:
                    print(f"Warning: Could not create backup: {str(e)}")

            session = boto3.Session(
                profile_name=self.profile_var.get(),
                region_name=region
            )
            codepipeline_client = session.client('codepipeline')

            # Update the pipeline
            codepipeline_client.update_pipeline(pipeline=pipeline_def)

            # Check if we should release the change
            if self.release_change_var.get():
                # Start a new execution
                codepipeline_client.start_pipeline_execution(name=pipeline_name)
                message = "Pipeline updated and new release started successfully"
            else:
                message = "Pipeline updated successfully (no new release started)"

            messagebox.showinfo("Success", message)
            window.destroy()

        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format")
            self.show_status_message("Update failed - invalid JSON")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update pipeline: {str(e)}")
            self.show_status_message(f"Update failed: {str(e)}")
        finally:
            self.change_button_state("normal")


# Main application window
if __name__ == "__main__":
    root = tk.Tk()
    root.title("AWS CodePipeline Manager")
    root.geometry("1000x700")

    app = PipelineManagerApp(root)
    root.mainloop()