import tkinter as tk
from tkinter import ttk, messagebox
import boto3
import threading
import json
import pyperclip
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
import os
from datetime import datetime


class CodeBuildManagerApp:
    def __init__(self, parent):
        self.parent = parent
        self.all_projects = []  # Variable to store all project data
        self.total_projects = 0  # Variable to store total project count
        self.setup_ui()
        self.cached_sessions = {}  # Cache for boto3 sessions
        self.project_cache = {}  # Cache for project details

    def create_backup(self, project_name, backup_type):
        """Create a backup of the project before modification"""
        try:
            # Create backup directory structure if it doesn't exist
            base_dir = os.path.join(os.path.dirname(__file__), "codebuild_ui_backup")
            backup_dir = os.path.join(base_dir, backup_type)

            os.makedirs(backup_dir, exist_ok=True)

            # Get current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Create backup filename
            backup_filename = f"{project_name}-{timestamp}-backup.json"
            backup_path = os.path.join(backup_dir, backup_filename)

            return backup_path
        except Exception as e:
            print(f"Warning: Could not create backup directory structure: {str(e)}")
            return None

    def extract_repo_name(self, location):
        """Extract repository name from CodeCommit URL"""
        if not location:
            return ""
        # Match the repo name at the end of the URL
        match = re.search(r'repos/([^/]+)$', location)
        return match.group(1) if match else ""

    def start_thread(self, target_function, *args):
        """Start the specified function in a separate thread."""
        thread = threading.Thread(target=target_function, args=args)
        thread.daemon = True
        thread.start()

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
            text="Load Projects",
            command=lambda: self.start_thread(self.load_projects)
        )
        self.load_button.pack(side="left", padx=5)

        # Bind Return/Enter key to load_button
        self.parent.bind("<Return>",
                         lambda event: self.start_thread(self.load_projects) if self.load_button.instate(
                             ["!disabled"]) else None)

        # Projects Frame
        projects_frame = ttk.LabelFrame(self.parent, text="CodeBuild Projects", padding="10")
        projects_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Search Frame
        search_frame = ttk.Frame(projects_frame)
        search_frame.pack(fill="x", pady=5)

        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.project_search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.project_search_var)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", self.filter_projects)

        # Create Treeview for projects with requested columns
        self.project_tree = ttk.Treeview(projects_frame,
                                         columns=(
                                             "SrNo", "Name", "Repository", "Source Type",
                                             "Environment", "Created", "Updated", "Region"),
                                         show="headings")

        # Configure columns with centered alignment for specific columns
        columns = [
            ("SrNo", "Sr. No.", 50, "center"),
            ("Name", "Name", 250, "w"),
            ("Repository", "Repository", 150, "w"),
            ("Source Type", "Source Type", 100, "center"),
            ("Environment", "Environment", 150, "center"),
            ("Created", "Created", 150, "center"),
            ("Updated", "Updated", 150, "center"),
            ("Region", "Region", 100, "center")
        ]

        for col_id, heading, width, anchor in columns:
            self.project_tree.heading(col_id, text=heading)
            self.project_tree.column(col_id, width=width, anchor=anchor)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(projects_frame, orient="vertical", command=self.project_tree.yview)
        self.project_tree.configure(yscrollcommand=scrollbar.set)
        self.project_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
                        background="#f0f0f0",  # Button background color
                        foreground="black",  # Button text color (now black)
                        font=("Arial", 10),  # Font style
                        padding=(10, 5))  # Padding inside the button

        style.map("Custom.TButton",
                  background=[("active", "#d9d9d9"),  # Background when hovered (slightly darker)
                              ("disabled", "#e0e0e0")],  # Background for disabled state (lighter gray)
                  foreground=[("active", "black"),  # Text color remains black when hovered
                              ("disabled", "#a0a0a0")],  # Text color for disabled state (dim gray)
                  relief=[("pressed", "sunken")])  # Change relief when pressed

        # Buttons Frame
        buttons_frame = ttk.Frame(self.parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)

        # Action buttons with custom style
        self.update_button = ttk.Button(
            buttons_frame,
            text="Update Project",
            style="Custom.TButton",
            command=self.show_project_json
        )
        self.update_button.pack(side="left", padx=5, pady=8)
        self.update_button.bind("<Return>",
                                lambda event: self.show_project_json() if self.update_button.instate(
                                    ["!disabled"]) else None)

        self.refresh_button = ttk.Button(
            buttons_frame,
            text="Refresh",
            style="Custom.TButton",
            command=lambda: self.start_thread(self.load_projects)
        )
        self.refresh_button.pack(side="left", padx=5, pady=8)
        self.refresh_button.bind("<Return>",
                                 lambda event: self.load_projects() if self.refresh_button.instate(
                                     ["!disabled"]) else None)

        # New Copy Project Link button with custom style
        self.copy_link_button = ttk.Button(
            buttons_frame,
            text="Copy Project Link",
            style="Custom.TButton",
            command=self.copy_project_link
        )
        self.copy_link_button.pack(side="left", padx=5, pady=8)
        self.copy_link_button.bind("<Return>",
                                   lambda event: self.copy_project_link() if self.copy_link_button.instate(
                                       ["!disabled"]) else None)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.parent, textvariable=self.status_var,
                               relief="sunken", padding=(10, 2))
        status_bar.pack(fill="x", padx=10, pady=5)

        # Enable buttons initially
        self.change_button_state("normal")

    def get_boto3_session(self, profile, region):
        """Get or create a cached boto3 session for the profile/region"""
        cache_key = f"{profile}:{region}"
        if cache_key not in self.cached_sessions:
            self.cached_sessions[cache_key] = boto3.Session(
                profile_name=profile,
                region_name=region
            )
        return self.cached_sessions[cache_key]

    def copy_project_link(self):
        """Copy AWS console link for the selected project to clipboard"""
        selected = self.project_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a project first")
            return

        project_name = self.project_tree.item(selected[0])['values'][1]
        region = self.project_tree.item(selected[0])['values'][7]

        # Construct the AWS console URL
        aws_url = f"https://{region}.console.aws.amazon.com/codesuite/codebuild/projects/{project_name}/?region={region}"

        try:
            pyperclip.copy(aws_url)
            self.show_status_message(f"Copied project link to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy link: {str(e)}")

    def change_button_state(self, state):
        """Enable/disable buttons and search entry during operations"""
        widgets = [
            self.load_button,
            self.update_button,
            self.refresh_button,
            self.copy_link_button,
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
        self.progress_label.config(text=f"Loaded {current} of {total} projects")
        self.parent.update()

    def filter_projects(self, event=None):
        """Filter projects from stored data based on search term"""
        search_term = self.project_search_var.get().lower()

        # Clear current treeview
        self.project_tree.delete(*self.project_tree.get_children())

        # If search is empty, show all projects
        if not search_term.strip():
            for project in self.all_projects:
                self.project_tree.insert('', 'end', values=(
                    project['sr_no'],
                    project['name'],
                    project['repository'],
                    project['source_type'],
                    project['environment'],
                    project['created'],
                    project['updated'],
                    project['region']
                ))
            return

        # Filter from stored data and add matching projects to treeview
        for project in self.all_projects:
            if search_term in project['name'].lower():
                self.project_tree.insert('', 'end', values=(
                    project['sr_no'],
                    project['name'],
                    project['repository'],
                    project['source_type'],
                    project['environment'],
                    project['created'],
                    project['updated'],
                    project['region']
                ))

    def get_total_projects_count(self, profile, regions):
        """Get total count of projects across all regions using parallel requests"""
        total = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for region in regions:
                futures.append(executor.submit(self._count_projects_in_region, profile, region))

            for future in as_completed(futures):
                try:
                    total += future.result()
                except Exception as e:
                    print(f"Error counting projects: {str(e)}")
        return total

    def _count_projects_in_region(self, profile, region):
        """Count projects in a single region"""
        try:
            session = self.get_boto3_session(profile, region)
            client = session.client('codebuild')
            paginator = client.get_paginator('list_projects')
            count = 0
            for page in paginator.paginate():
                count += len(page['projects'])
            return count
        except Exception as e:
            print(f"Error counting projects in {region}: {str(e)}")
            return 0

    def get_projects_in_region(self, profile, region):
        """Get all projects in a specific region with optimized API calls"""
        cache_key = f"{profile}:{region}:projects"
        if cache_key in self.project_cache:
            return region, self.project_cache[cache_key]

        try:
            session = self.get_boto3_session(profile, region)
            client = session.client('codebuild')

            # Get all project names first
            paginator = client.get_paginator('list_projects')
            project_names = []
            for page in paginator.paginate():
                project_names.extend(page['projects'])

            if not project_names:
                return region, []

            # Batch get project details in chunks of 100 (AWS limit)
            projects = []
            for i in range(0, len(project_names), 100):
                batch = project_names[i:i + 100]
                try:
                    response = client.batch_get_projects(names=batch)
                    for project in response['projects']:
                        # Format dates for display
                        created = project.get('created', '')
                        updated = project.get('lastModified', '')

                        if created:
                            created = created.strftime('%Y-%m-%d %H:%M:%S')
                        if updated:
                            updated = updated.strftime('%Y-%m-%d %H:%M:%S')

                        # Get environment info
                        environment = project.get('environment', {})
                        env_type = environment.get('type', '')
                        env_compute_type = environment.get('computeType', '')
                        environment_str = f"{env_type}/{env_compute_type}"

                        # Extract repository name from source location
                        repo_name = ""
                        source = project.get('source', {})
                        if source and 'location' in source:
                            repo_name = self.extract_repo_name(source['location'])

                        projects.append({
                            'name': project['name'],
                            'repository': repo_name,
                            'source_type': source.get('type', ''),
                            'environment': environment_str,
                            'created': created,
                            'updated': updated,
                            'region': region
                        })
                except Exception as e:
                    print(f"Error getting batch details in {region}: {str(e)}")
                    continue

            # Cache the results
            self.project_cache[cache_key] = projects
            return region, projects

        except Exception as e:
            print(f"Error in {region}: {str(e)}")
            return region, []

    def load_projects(self):
        """Load projects with optimized parallel processing and UI updates"""
        self.change_button_state("disabled")
        self.project_search_var.set("")  # Clear search filter
        self.show_status_message("Loading projects...")

        # Show progress bar
        self.progress_frame.pack(fill="x", padx=10, pady=5)
        self.progress["value"] = 0
        self.progress_label.config(text="Counting projects...")
        self.parent.update()

        try:
            profile = self.profile_var.get()
            regions = [r.strip() for r in self.region_var.get().split(',') if r.strip()]

            if not profile or not regions:
                messagebox.showwarning("Warning", "Please provide both profile and region(s)")
                return

            # Get total project count first
            self.total_projects = self.get_total_projects_count(profile, regions)
            if self.total_projects == 0:
                self.progress_label.config(text="No projects found")
                self.parent.update()
                return

            # Clear existing items more efficiently
            self.project_tree.delete(*self.project_tree.get_children())

            # Reset the stored project data
            self.all_projects = []
            loaded_count = 0

            # Use ThreadPoolExecutor to fetch projects from all regions in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.get_projects_in_region, profile, region): region for region in regions}

                for future in as_completed(futures):
                    region, projects = future.result()
                    region_start_count = loaded_count

                    for project in projects:
                        # Store the complete project data
                        self.all_projects.append({
                            'sr_no': loaded_count + 1,
                            'name': project['name'],
                            'repository': project['repository'],
                            'source_type': project['source_type'],
                            'environment': project['environment'],
                            'created': project['created'],
                            'updated': project['updated'],
                            'region': project['region']
                        })
                        loaded_count += 1

                    # Batch insert projects for this region to reduce UI updates
                    if projects:
                        self.parent.after(0, self._add_projects_to_tree,
                                          self.all_projects[region_start_count:loaded_count])
                        self.parent.after(0, self.update_progress, loaded_count, self.total_projects)

            self.show_status_message(f"Loaded {loaded_count} projects across {len(regions)} region(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load projects: {str(e)}")
            self.show_status_message("Error loading projects")
        finally:
            self.change_button_state("normal")
            self.progress_frame.pack_forget()  # Hide progress bar when done

    def _add_projects_to_tree(self, projects):
        """Add a batch of projects to the treeview"""
        for project in projects:
            self.project_tree.insert('', 'end', values=(
                project['sr_no'],
                project['name'],
                project['repository'],
                project['source_type'],
                project['environment'],
                project['created'],
                project['updated'],
                project['region']
            ))

    def show_project_json(self):
        selected = self.project_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a project to update")
            return

        project_name = self.project_tree.item(selected[0])['values'][1]
        region = self.project_tree.item(selected[0])['values'][7]

        edit_window = tk.Toplevel(self.parent)
        edit_window.title(f"Edit Project: {project_name}")
        edit_window.geometry("800x600")

        try:
            session = self.get_boto3_session(self.profile_var.get(), region)
            codebuild_client = session.client('codebuild')

            project_def = codebuild_client.batch_get_projects(names=[project_name])
            project_json = json.dumps(project_def['projects'][0], indent=2, default=str)

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
            self.json_text.insert("1.0", project_json)

            # Add some padding at the bottom
            ttk.Frame(edit_window, height=10).pack()

            # Update button frame
            button_frame = ttk.Frame(edit_window)
            button_frame.pack(fill="x", padx=10, pady=10)

            update_btn = ttk.Button(
                button_frame,
                text="Update Project",
                style="Custom.TButton",
                command=partial(self.update_project, project_name, region, edit_window)
            )
            update_btn.pack()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to get project definition: {str(e)}")
            edit_window.destroy()

    def update_project(self, project_name, region, window):
        self.change_button_state("disabled")
        self.show_status_message(f"Updating project {project_name}...")

        try:
            new_json = self.json_text.get("1.0", "end-1c")
            project_def = json.loads(new_json)

            # Create backup before updating
            backup_path = self.create_backup(project_name, "update_pipeline_backup")
            if backup_path:
                try:
                    with open(backup_path, 'w') as f:
                        json.dump(project_def, f, indent=2)
                except Exception as e:
                    print(f"Warning: Could not create backup: {str(e)}")

            session = self.get_boto3_session(self.profile_var.get(), region)
            codebuild_client = session.client('codebuild')

            # Remove read-only and invalid fields before updating
            invalid_fields = [
                'arn', 'created', 'lastModified',  # read-only fields
                'badge', 'projectVisibility'  # invalid parameters
            ]

            # Create a copy of the project definition for modification
            update_def = project_def.copy()
            for field in invalid_fields:
                update_def.pop(field, None)

            codebuild_client.update_project(**update_def)

            # Clear cache for this region
            cache_key = f"{self.profile_var.get()}:{region}:projects"
            if cache_key in self.project_cache:
                del self.project_cache[cache_key]

            messagebox.showinfo("Success", "Project updated successfully")
            window.destroy()
            self.show_status_message("Project updated - refreshing list...")
            # self.start_thread(self.load_projects)

        except json.JSONDecodeError:
            messagebox.showerror("Error", "Invalid JSON format")
            self.show_status_message("Update failed - invalid JSON")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update project: {str(e)}")
            self.show_status_message(f"Update failed: {str(e)}")
        finally:
            self.change_button_state("normal")


if __name__ == "__main__":
    root = tk.Tk()
    root.title("AWS CodeBuild Project Manager")
    app = CodeBuildManagerApp(root)
    root.mainloop()