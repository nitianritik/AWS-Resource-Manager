import tkinter as tk
from tkinter import ttk, messagebox
import boto3
from botocore.exceptions import ProfileNotFound, ClientError
import time
from tkinter import TclError
import subprocess
import threading
from tkinter import Toplevel, Label, Button
import queue

# pip install boto3 tk


# TODO 1: Fixing the attribute error in the load_clusters method. --This issue is fixed
# TODO 2: Need to add auto profile login functionality now. -- starting --done
# TODO 3: Need to make the show services window on the top after any popup shows and loading window also -- starting
       # loading bar integrated  -- done
       # now addming aysc for service loading. --done
# TODO 4: adding sync to fetch service
# TODO 5: adding pending services column to the table --Done
# TODO 6: Now have to async the sto/start service --
# TODO 7: loading bar service table in one frame -- started --done
# TODO 8: Now i want that when we call the update_cluster, refresh_service, and start_stop_service method anywhere in the show services funiton, all should be called ayschronously. --started --done
# TODO 9: Have to disable stop/start service button after the new list is updated --done
# TODO 10: There should be multiple select options for the service stop and start, with the checkboxes. --started --done
        # implementing nested conditions --done
# TODO 11: adding warning message for more that one service state selected. --started -- done
# TODO 12: now i want to show all popups that is populated from service screen window should only be top on that, not on the root window. --started -- done
# TODO 13: need to add two checkboxes to select all running services and to select all stopped services. --started --done
# TODO 14: need to prevent two same window for show services. --started --done
# TODO 15: copy cpu memory config and service list
# TODO 16: if the cluster is not loaded then these buttons: stop cluster, start cluster, restart cluster and refresh cluster buttons should be disabled. and once i click load cluster button then and when its in progress then all the buttons in root screen should be disabled untill all the clusters are loaded.
# TODO 17: load cluster faster
# TODO 18: get images functionality --started --done
# TODO 19: refresh and copy button in show images also with disble button condition --starte --done
# TODO 20: adding serial no to the cluster list --started
# TODO 21: changing button style --done
# TODO 22: need to extend the message timing to load custer
# TODO 23: starting a big change for rds ec2 also
# TODO 24: starting soring of the columns --started
# TODO 25: need to maka images list more good
# TODO 26: implementing soring for all the table that is being used.

# --sunday starting

class ECSManagerApp:
    def __init__(self, parent):
        self.parent = parent

        if isinstance(parent, (tk.Tk, tk.Toplevel)):
            self.parent.title("AWS ECS Cluster Manager")

        # self.parent.title("AWS ECS Cluster Manager")
        # self.parent.geometry("1200x800")
        self._progress_data = None


        # Variables
        self.profile_var = tk.StringVar(value="")
        self.region_var = tk.StringVar(value="")
        self.selected_cluster = None
        self.clusters_data = {}

        self.setup_ui()

        self.service_windows = {}  # Dictionary to keep track of open service windows
        self.config_windows = {}  # Dictionary to track CPU/Memory config windows
        self.open_image_windows = {}  # Dictionary to track open windows

        self.restart=0

    def create_tooltip(self, widget, text):
        # Create tooltip window
        tooltip = tk.Toplevel(widget)
        tooltip.withdraw()  # Initially hidden
        tooltip.overrideredirect(True)

        # Set tooltip label styling
        tooltip_label = tk.Label(
            tooltip,
            text=text,
            background="#f9f9f9",  # Light gray background
            foreground="black",  # Black text
            relief="flat",
            borderwidth=0,
            padx=5,
            pady=3,
            font=("Arial", 9)  # Subtle and minimal font
        )
        tooltip_label.pack()

        def on_enter(event):
            # Position the tooltip slightly offset from the cursor
            tooltip.geometry(f"+{event.x_root + 10}+{event.y_root + 10}")
            tooltip.deiconify()

        def on_leave(event):
            tooltip.withdraw()

        def on_keypress(event):
            # Hide the tooltip when typing
            tooltip.withdraw()

        # Bind events to show/hide tooltip
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
        widget.bind("<Key>", on_keypress)

    def setup_ui(self):
        # Profile and Region Frame
        input_frame = ttk.LabelFrame(self.parent, text="AWS Configuration", padding="10")
        input_frame.pack(fill="x", padx=10, pady=5)

        # Profile input
        ttk.Label(input_frame, text="Profile Name:").pack(side="left")
        ###########
        self.profile_entry = ttk.Entry(input_frame, textvariable=self.profile_var)
        self.profile_entry.pack(side="left", padx=5)

        self.create_tooltip(self.profile_entry, "Enter AWS SSO profile name")

        ##########
        self.profile_entry.focus_set()

        # Region input
        ttk.Label(input_frame, text="Region(s):").pack(side="left")
        self.region_entry = ttk.Entry(input_frame, textvariable=self.region_var, width=35)
        self.region_entry.pack(side="left", padx=5)
        self.create_tooltip(self.region_entry, "Enter region(s). no_of_regions > 0.\n For ex. us-east-1 or us-east-1,us-west-2")
        ttk.Label(input_frame, text="(comma-separated regions, empty for all)").pack(side="left")

        self.load_clusters_button = ttk.Button(input_frame, text="Load Clusters",
                                               command=lambda: self.start_thread(self.load_clusters))
        self.load_clusters_button.pack(side="left", padx=5)
        self.load_clusters_button.bind("<Return>",
                                        lambda event: self.start_thread(
                                            self.load_clusters) if self.load_clusters_button.instate(
                                            ["!disabled"]) else None)

        # Clusters Frame
        clusters_frame = ttk.LabelFrame(self.parent, text="ECS Clusters", padding="10")
        clusters_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create style for the treeview
        style = ttk.Style()
        style.map('Treeview', background=[('selected', '#0078D7')])  # Define selection color
        style.configure("Treeview", background="white", foreground="black", fieldbackground="white")

        self.columns = ("SrNo", "Cluster Name", "Region", "Status", "Active Services", "Running Tasks", "Pending Tasks")
        self.sort_states = {col: None for col in self.columns}  # Track sorting state (Asc → Desc → Asc)

        # Create Treeview with modified columns
        self.tree = ttk.Treeview(clusters_frame,
                                 columns=self.columns,
                                 show="headings",
                                 style="Treeview")

        # Index tracking for Status column
        self.index_of_status = {
           self.tree: 3
        }

        # Configure tag for running clusters
        self.tree.tag_configure('running_cluster', background='#99f299')

        # Configure column alignments
        self.tree.column("SrNo", anchor="center")
        self.tree.column("Status", anchor="center")
        self.tree.column("Region", anchor="center")
        self.tree.column("Active Services", anchor="center")

        # Define columns
        self.tree.heading("SrNo", text="Sr. No.", command=lambda c="SrNo": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))
        self.tree.heading("Cluster Name", text="Cluster Name", command=lambda c="Cluster Name": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))
        self.tree.heading("Region", text="Region", command=lambda c="Region": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))
        self.tree.heading("Status", text="Status", command=lambda c="Status": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))
        self.tree.heading("Active Services", text="Active Services", command=lambda c="Active Services": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))
        self.tree.heading("Running Tasks", text="Running Tasks", command=lambda c="Running Tasks": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))
        self.tree.heading("Pending Tasks", text="Pending Tasks", command=lambda c="Pending Tasks": self.sort_column(self.tree, c, self.sort_states, self.columns, running_flag=True))

        # Bind right-click event
        self.tree.bind("<Button-3>", self.show_context_menu)
        self.tree.bind('<Control-c>', self.copy_selected)

        # Add keyboard binding for the new command
        self.tree.bind('<Control-n>', self.copy_cluster_names)

        # Set column widths
        column_widths = {
            "SrNo": 30,
            "Cluster Name": 180,
            "Status": 100,
            "Region": 100,
            "Active Services": 80,
            "Running Tasks": 80,
            "Pending Tasks": 80
        }
        for col, width in column_widths.items():
            self.tree.column(col, width=width, anchor="center")

        # Enable multiple selection
        self.tree['selectmode'] = 'extended'

        # Create right-click menu
        self.context_menu = tk.Menu(self.parent, tearoff=0)
        self.context_menu.add_command(label="Show Services", command=self.show_services)

        self.context_menu.add_command(label="Show CPU Memory Config",
                                      command=self.show_cpu_memory_config)

        self.context_menu.add_command(label="Show Images",
                                      command=self.show_container_images)

        self.context_menu.add_command(
            label="Copy Selected Row",
            command=self.copy_selected,
            accelerator="Ctrl+C"
        )

        self.context_menu.add_command(
            label="Copy Cluster Name",
            command=self.copy_cluster_names,
            accelerator="Ctrl+N"  # Optional keyboard shortcut
        )

        # Left-align the Name column
        self.tree.column("Cluster Name", anchor="w")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(clusters_frame, orient="vertical",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Pack tree and scrollbar
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons Frame
        buttons_frame = ttk.Frame(self.parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)

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

        # Add interactive ttk Buttons
        self.start_cluster_button = ttk.Button(buttons_frame, text="Start Cluster", style="Custom.TButton",
                                               command=lambda: self.start_thread(self.start_cluster))
        self.start_cluster_button.pack(side="left", padx=5, pady=8)
        self.start_cluster_button.bind("<Return>",
                                       lambda event: self.start_cluster() if self.start_cluster_button.instate(
                                           ["!disabled"]) else None)

        self.stop_cluster_button = ttk.Button(buttons_frame, text="Stop Cluster", style="Custom.TButton",
                                              command=lambda: self.start_thread(self.stop_cluster))
        self.stop_cluster_button.pack(side="left", padx=5, pady=8)
        self.stop_cluster_button.bind("<Return>",
                                      lambda event: self.stop_cluster() if self.stop_cluster_button.instate(
                                          ["!disabled"]) else None)

        self.restart_cluster_button = ttk.Button(buttons_frame, text="Restart Cluster", style="Custom.TButton",
                                                 command=lambda: self.start_thread(self.restart_cluster))
        self.restart_cluster_button.pack(side="left", padx=5, pady=8)
        self.restart_cluster_button.bind("<Return>",
                                         lambda event: self.restart_cluster() if self.restart_cluster_button.instate(
                                             ["!disabled"]) else None)

        self.refresh_button = ttk.Button(buttons_frame, text="Refresh", style="Custom.TButton",
                                         command=lambda: self.start_thread(self.refresh_data))
        self.refresh_button.pack(side="left", padx=5, pady=8)
        self.refresh_button.bind("<Return>",
                                 lambda event: self.refresh_data() if self.refresh_button.instate(
                                     ["!disabled"]) else None)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.parent, textvariable=self.status_var,
                               relief="sunken", padding=(10, 2))
        status_bar.pack(fill="x", padx=10, pady=5)

    def get_current_tree_data(self, tree):
        """Extracts current data from the given treeview"""
        return [tree.item(item)["values"] for item in tree.get_children()]

    def populate_tree(self, tree, data, running_flag=False, select_flag=False):
        """Clear and insert sorted data into the given treeview"""

        def print_tree_elements(tree):
            """Print all elements of the tree with their internal item IDs"""
            for item_id in tree.get_children():
                values = tree.item(item_id)["values"]  # Get row values
                print(f"ID: {item_id}, Values: {values}")

        print_tree_elements(tree)

        tree.delete(*tree.get_children())  # Clear table

        # Clear existing checkbox states if select_flag is True
        if select_flag:
            tree.checkbox_vars = {}

        for row in data:

            if select_flag:
                row = ["□"] + row[1:]

            # Apply tags only if running_flag is True
            tag = "running" if running_flag and row[self.index_of_status[tree]] == "RUNNING" else "stopped"
            item_id = tree.insert("", "end", values=row, tags=(tag,))

            # Initialize checkbox if select_flag is True
            if select_flag:
                tree.checkbox_vars[item_id] = tk.BooleanVar(value=False)

        print_tree_elements(tree)

        # Apply row colors if running_flag is True
        if running_flag:
            tree.tag_configure("running", background="light green")
            tree.tag_configure("stopped", background="white")

    def sort_column(self, tree, col, sort_states, columns, running_flag=False, select_flag=False):

        """Sorts the given tree with independent sorting states"""
        col_index = columns.index(col)  # Get index of column dynamically
        current_data = self.get_current_tree_data(tree)  # Get displayed data

        # Toggle sorting state (Asc → Desc)
        if sort_states[col] is None or sort_states[col] == "desc":
            reverse = False  # Ascending order
            sort_states[col] = "asc"
            arrow = " ▲"
        else:
            reverse = True  # Descending order
            sort_states[col] = "desc"
            arrow = " ▼"

        # Sorting logic
        sorted_data = sorted(current_data, key=lambda row: row[col_index], reverse=reverse)

        # Reset all column headers
        for c in columns:
            tree.heading(c, text=c)  # Reset headers

        # Set arrow on the sorted column
        tree.heading(col, text=col + arrow)

        # Refresh the table with sorted data and reapply row colors or checkboxes as needed
        self.populate_tree(tree, sorted_data, running_flag, select_flag)

    def show_container_images(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a cluster")
            return

        item = selected[0]
        cluster_name = self.tree.item(item)['values'][1]
        region = self.tree.item(item)['values'][2]

        # Check if window already exists for this cluster
        window_key = f"{cluster_name}_{region}"
        if window_key in self.open_image_windows:
            existing_window = self.open_image_windows[window_key]
            if existing_window.winfo_exists():
                # If window exists, lift it to top and return
                existing_window.lift()
                existing_window.focus_force()
                return
            else:
                # If window was destroyed, remove it from dictionary
                del self.open_image_windows[window_key]

        # Create new window
        images_window = tk.Toplevel(self.parent)
        images_window.title(f"Container Images - {cluster_name}")
        images_window.geometry("1000x600")

        # Store the window reference
        self.open_image_windows[window_key] = images_window

        # Handle window close event
        def on_window_close():
            if window_key in self.open_image_windows:
                del self.open_image_windows[window_key]
            images_window.destroy()

        images_window.protocol("WM_DELETE_WINDOW", on_window_close)

        # Create main frame
        main_frame = ttk.Frame(images_window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Create progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill="x", pady=(0, 10))

        # Progress bar and label
        progress_var = tk.DoubleVar()
        progress_label = ttk.Label(progress_frame, text="Fetching services...")
        progress_label.pack(side="top", fill="x")
        progress_bar = ttk.Progressbar(
            progress_frame,
            variable=progress_var,
            maximum=100,
            mode='determinate'
        )
        progress_bar.pack(fill="x")

        # Text widget frame
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill="both", expand=True)

        # Add Text widget with both vertical and horizontal scrollbars
        text_widget = tk.Text(text_frame, wrap="none", font=("Courier", 10))

        # Vertical scrollbar
        v_scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=v_scrollbar.set)

        # Horizontal scrollbar
        h_scrollbar = ttk.Scrollbar(text_frame, orient="horizontal", command=text_widget.xview)
        text_widget.configure(xscrollcommand=h_scrollbar.set)

        # Pack scrollbars and text widget
        h_scrollbar.pack(side="bottom", fill="x")
        v_scrollbar.pack(side="right", fill="y")
        text_widget.pack(side="left", fill="both", expand=True)

        # Message queue for thread communication
        message_queue = queue.Queue()

        def update_ui():
            """Update UI from queue"""
            try:
                while True:
                    msg_type, msg = message_queue.get_nowait()
                    if msg_type == "progress":
                        progress_var.set(msg[0])
                        progress_label.config(text=msg[1])
                    elif msg_type == "text":
                        text_widget.insert(tk.END, msg)
                        # Auto scroll to the bottom
                        text_widget.see(tk.END)
                    elif msg_type == "clear":
                        text_widget.delete("1.0", tk.END)
                    elif msg_type == "done":
                        progress_frame.pack_forget()  # Hide progress bar when done
                        text_widget.configure(state='disabled')  # Make text read-only
                        # Enable buttons after loading is complete
                        refresh_button.configure(state='normal')
                        copy_button.configure(state='normal')
                        return
                    images_window.update()
            except queue.Empty:
                images_window.after(100, update_ui)

        def fetch_images():
            try:
                # Disable buttons while fetching
                refresh_button.configure(state='disabled')
                copy_button.configure(state='disabled')

                # Create ECS client with the current profile
                current_profile = self.profile_var.get()
                session = boto3.Session(profile_name=current_profile)
                ecs_client = session.client('ecs', region_name=region)

                # Get all services in the cluster
                services = []
                paginator = ecs_client.get_paginator('list_services')
                for page in paginator.paginate(cluster=cluster_name):
                    services.extend(page['serviceArns'])

                message_queue.put(("clear", None))
                message_queue.put(("text", f"Container Images for cluster: {cluster_name}\n\n"))

                # Check if services list is empty
                if not services:
                    message_queue.put(("text", "No services found in this cluster.\n"))
                    message_queue.put(("done", None))
                    return

                total_services = len(services)

                for idx, service in enumerate(services, 1):
                    # Update progress
                    progress = (idx / total_services) * 100
                    service_name = service.split('/')[-1]
                    message_queue.put(
                        ("progress", (progress, f"Processing service {idx}/{total_services}: {service_name}")))

                    # Get service details
                    service_desc = ecs_client.describe_services(
                        cluster=cluster_name,
                        services=[service]
                    )['services'][0]

                    message_queue.put(("text", f"Service {idx}: {service_name}\n"))

                    if 'taskDefinition' in service_desc:
                        task_def = ecs_client.describe_task_definition(
                            taskDefinition=service_desc['taskDefinition']
                        )['taskDefinition']

                        for container in task_def['containerDefinitions']:
                            message_queue.put(("text", f"\tContainer Name     : {container['name']}\n"))
                            message_queue.put(("text", f"\tImage              : {container['image']}\n"))
                    else:
                        message_queue.put(("text", f"\tNo task definition found\n"))

                    message_queue.put(("text", "\n"))

                message_queue.put(("done", None))

            except Exception as e:
                message_queue.put(("clear", None))
                message_queue.put(("text", f"Error fetching container images: {str(e)}"))
                message_queue.put(("done", None))

        # Create button frame
        button_frame = ttk.Frame(images_window)
        button_frame.pack(fill="x", pady=5, padx=10, anchor="w")

        # Add Refresh button
        def refresh_data():
            progress_var.set(0)  # Reset progress bar
            progress_label.config(text="Fetching services...")
            progress_frame.pack(fill="x", pady=(0, 10))  # Show progress frame again
            text_widget.configure(state='normal')  # Enable text widget for clearing
            text_widget.delete("1.0", tk.END)
            # Start the background thread again
            thread = threading.Thread(target=fetch_images, daemon=True)
            thread.start()
            update_ui()

        refresh_button = ttk.Button(button_frame, text="Refresh",
                                    command=refresh_data,
                                    state='disabled')  # Initially disabled
        refresh_button.pack(side="left", padx=(0, 5))

        # Add Copy button
        def copy_to_clipboard():
            images_window.clipboard_clear()
            images_window.clipboard_append(text_widget.get("1.0", tk.END))
            messagebox.showinfo("Success", "Images copied to clipboard successfully", parent=images_window)


        copy_button = ttk.Button(button_frame, text="Copy to Clipboard",
                                 command=copy_to_clipboard,
                                 state='disabled')  # Initially disabled
        copy_button.pack(side="left")

        # Start the background thread
        thread = threading.Thread(target=fetch_images, daemon=True)
        thread.start()

        # Start UI update loop
        update_ui()

    def copy_cluster_names(self, event=None):
        """Copy only cluster names of selected items"""
        try:
            # Get all selected items
            selected_items = self.tree.selection()

            if not selected_items:  # If nothing is selected
                return

            # Get cluster names (assuming cluster name is the second column, index 1)
            cluster_names = []
            for item in selected_items:
                values = self.tree.item(item)['values']
                if values and len(values) > 1:
                    cluster_names.append(str(values[1]))  # Index 1 for cluster name

            # Join cluster names with newlines
            final_text = '\n'.join(cluster_names)

            # Clear clipboard and append new text
            self.parent.clipboard_clear()
            self.parent.clipboard_append(final_text)

            # Show success message
            self.show_popup_status_message(f"Copied {len(cluster_names)} cluster name(s) to clipboard")

        except Exception as e:
            self.show_popup_status_message(f"Error copying to clipboard: {str(e)}")

    def copy_selected(self, event=None):
        """Copy selected items' text to clipboard"""
        try:
            # Get all selected items
            selected_items = self.tree.selection()

            if not selected_items:  # If nothing is selected
                return

            # Get column headings
            headers = []
            for col in self.tree['columns']:
                headers.append(self.tree.heading(col)['text'])

            # Initialize list to store all rows
            copy_text = []

            # Add headers as first row
            copy_text.append('\t'.join(str(header) for header in headers))

            # Add selected rows
            for item in selected_items:
                # Get values of the selected row
                values = self.tree.item(item)['values']
                if values:
                    # Convert all values to strings and join with tabs
                    row_text = '\t'.join(str(value) for value in values)
                    copy_text.append(row_text)

            # Join all rows with newlines
            final_text = '\n'.join(copy_text)

            # Clear clipboard and append new text
            self.parent.clipboard_clear()
            self.parent.clipboard_append(final_text)

            # Show success message
            self.show_popup_status_message(f"Copied {len(selected_items)} row(s) to clipboard")

        except Exception as e:
            self.show_popup_status_message(f"Error copying to clipboard: {str(e)}")

    def show_popup_status_message(self, message, auto_close_timing=2000):
        """Show a temporary status message"""
        try:
            # Create a small popup window
            status_window = tk.Toplevel(self.parent)
            status_window.overrideredirect(True)  # Remove window decorations

            # Calculate position (centered near bottom of main window)
            x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - 150  # Adjust for message width
            y = self.parent.winfo_y() + self.parent.winfo_height() - 100

            status_window.geometry(f"+{x}+{y}")

            # Create label with message
            label = ttk.Label(
                status_window,
                text=message,
                padding=10,
                background='#2E2E2E',
                foreground='white'
            )
            label.pack()

            # Auto-close after 2 seconds
            status_window.after(auto_close_timing, status_window.destroy)

            # Ensure window stays on top
            status_window.lift()
            status_window.attributes('-topmost', True)

        except Exception:
            # Fallback to print if GUI elements fail
            print(message)

    def show_context_menu(self, event):
        """Show the context menu on right click"""
        # First select the item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def is_window_alive(self, window):
        """Check if a window still exists and is not destroyed"""
        try:
            return window.winfo_exists()
        except:
            return False

    def on_service_window_close(self, cluster_name):
        """Handle service window closing"""
        if cluster_name in self.service_windows:
            self.service_windows[cluster_name].grab_release()  # Release the grab
            self.service_windows[cluster_name].destroy()
            del self.service_windows[cluster_name]

    # adding update cpu and memory to the service list window --started
    def show_services(self):
        """Show services for the selected cluster"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a cluster")
            return

        # Get the current profile from the entry
        current_profile = self.profile_var.get()

        # Get the selected item
        item = selected[0]
        cluster_name = self.tree.item(item)['values'][1]
        region = self.tree.item(item)['values'][2]

        # Check if window already exists for this cluster
        if cluster_name in self.service_windows:
            existing_window = self.service_windows[cluster_name]
            if existing_window.winfo_exists():
                # If window exists, bring it to front and return
                existing_window.lift()
                existing_window.focus_force()
                return
            else:
                # If window reference exists but window is destroyed, remove it
                del self.service_windows[cluster_name]

        # Create new window for services
        services_window = tk.Toplevel(self.parent)
        services_window.title(f"Services in {cluster_name} ({region})")
        services_window.geometry("800x600")

        # services_window.transient(self.parent)
        # services_window.grab_set()

        # Store the window reference
        self.service_windows[cluster_name] = services_window

        # Bind the window close event
        services_window.protocol("WM_DELETE_WINDOW",
                                lambda: self.on_service_window_close(cluster_name))

        # Create main container frame
        main_container = ttk.Frame(services_window)
        main_container.pack(fill="both", expand=True)

        # Create loading frame at the top
        loading_frame = ttk.Frame(main_container)
        loading_frame.pack(fill="x", padx=10, pady=5)

        loading_label = ttk.Label(loading_frame, text="Loading Services...", font=('Arial', 12))
        loading_label.pack(side="left", pady=5)

        progress_var = tk.IntVar()
        progress_bar = ttk.Progressbar(loading_frame, variable=progress_var, maximum=100, length=300)
        progress_bar.pack(side="left", padx=10, pady=5)

        progress_text = ttk.Label(loading_frame, text="")
        progress_text.pack(side="left", pady=5)

        # Create frame for services table
        services_frame = ttk.Frame(main_container)
        services_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create style for the services treeview
        style = ttk.Style()
        style.map('Treeview', background=[('selected', '#0078D7')])
        style.configure("Treeview", background="white", foreground="black", fieldbackground="white")

        # Create treeview for services
        # Create treeview for services

        self.columns_service_frame = ("Select", "Sr. No.", "Service Name", "Status", "Running Tasks", "Desired Tasks", "Pending tasks")
        self.sort_states_service_frame = {col: None for col in self.columns_service_frame}  # Track sorting state (Asc → Desc → Asc)

        services_tree = ttk.Treeview(services_frame,
                                     columns=self.columns_service_frame,
                                     show="headings",
                                     style="Treeview")

        self.index_of_status[services_tree] = 3

        # Configure tag for running services
        services_tree.tag_configure('running_service', background='#99f299')

        # Add select all checkbox in frame above treeview
        select_all_frame = ttk.Frame(services_frame)
        select_all_frame.pack(fill="x", pady=(0, 5))

        # Create variables for checkboxes
        select_all_var = tk.BooleanVar()
        select_running_var = tk.BooleanVar()
        select_stopped_var = tk.BooleanVar()

        # Create all three checkboxes
        select_all_cb = ttk.Checkbutton(select_all_frame, text="Select All",
                                        variable=select_all_var,
                                        command=lambda: toggle_all_services(),
                                        state='disabled')

        select_running_cb = ttk.Checkbutton(select_all_frame, text="Select Running",
                                            variable=select_running_var,
                                            command=lambda: toggle_running_services(),
                                            state='disabled')

        select_stopped_cb = ttk.Checkbutton(select_all_frame, text="Select Stopped",
                                            variable=select_stopped_var,
                                            command=lambda: toggle_stopped_services(),
                                            state='disabled')

        # Pack checkboxes
        select_all_cb.pack(side="left", padx=5)
        select_running_cb.pack(side="left", padx=5)
        select_stopped_cb.pack(side="left", padx=5)

        print(self.columns_service_frame)
        print(services_tree["columns"])
        # Set column headings
        for col in services_tree["columns"]:
            # services_tree.heading(col, text=col)
            services_tree.heading(col, text=col,
                              command=lambda c=col: self.sort_column(services_tree, c, self.sort_states_service_frame, self.columns_service_frame, running_flag=True, select_flag=True))

        # Update column widths dictionary
        column_widths = {
            "Select": 50,
            "Sr. No.": 60,
            "Service Name": 200,
            "Status": 100,
            "Running Tasks": 100,
            "Desired Tasks": 100,
            "Pending tasks": 100
        }
        for col, width in column_widths.items():
            services_tree.column(col, width=width, anchor="center")

        # Left-align the Service Name column
        services_tree.column("Service Name", anchor="w")

        # Add scrollbar
        scrollbar = ttk.Scrollbar(services_frame, orient="vertical", command=services_tree.yview)
        services_tree.configure(yscrollcommand=scrollbar.set)

        # Pack tree and scrollbar
        services_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def update_start_stop_button_state():
            """Update the start/stop button state based on selected services"""
            selected_states = []
            for item_id in services_tree.get_children():
                if services_tree.checkbox_vars[item_id].get():
                    status = services_tree.item(item_id)['values'][3]  # Status column
                    selected_states.append(status)

            if not selected_states:
                start_stop_button.configure(state='disabled', text="Start/Stop Selected Services")
                warning_label.pack_forget()  # Hide warning
                return

            # Check if all selected services are in the same state
            all_running = all(state == "RUNNING" for state in selected_states)
            all_stopped = all(state == "STOPPED" for state in selected_states)

            if all_running:
                start_stop_button.configure(state='normal', text="Stop Selected Services")
                warning_label.pack_forget()  # Hide warning
            elif all_stopped:
                start_stop_button.configure(state='normal', text="Start Selected Services")
                warning_label.pack_forget()  # Hide warning
            else:
                start_stop_button.configure(state='disabled', text="Start/Stop Selected Services")
                warning_label.pack(side="right", padx=5)  # Show warning

        def update_images():
            """Open a window to update images for the selected service"""
            messagebox.showinfo("Info", "This feature is in development phase.", parent=services_window)
            return
            selected_services = []
            for item_id in services_tree.get_children():
                if services_tree.checkbox_vars[item_id].get():
                    service_name = services_tree.item(item_id)['values'][2]  # Service name
                    selected_services.append(service_name)

            if not selected_services:
                messagebox.showwarning("Warning", "Please select at least one service", parent=services_window)
                return

            if len(selected_services) > 1:
                messagebox.showwarning("Warning", "Please select only one service to update images",
                                       parent=services_window)
                return

            service_name = selected_services[0]

            # Create new window for image update
            update_window = tk.Toplevel(services_window)
            update_window.title(f"Update Images for {service_name}")
            update_window.geometry("600x400")

            # Create main container frame
            main_container = ttk.Frame(update_window)
            main_container.pack(fill="both", expand=True)

            # Create frame for containers table
            containers_frame = ttk.Frame(main_container)
            containers_frame.pack(fill="both", expand=True, padx=10, pady=5)

            # Create treeview for containers
            columns_containers_frame = ("Container Name", "Image")
            containers_tree = ttk.Treeview(containers_frame, columns=columns_containers_frame, show="headings")

            for col in columns_containers_frame:
                containers_tree.heading(col, text=col)

            # Set column widths
            column_widths = {
                "Container Name": 200,
                "Image": 300
            }
            for col, width in column_widths.items():
                containers_tree.column(col, width=width, anchor="w")

            # Add scrollbar
            scrollbar = ttk.Scrollbar(containers_frame, orient="vertical", command=containers_tree.yview)
            containers_tree.configure(yscrollcommand=scrollbar.set)

            # Pack tree and scrollbar
            containers_tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Load containers and their images
            def load_containers():
                try:
                    session = boto3.Session(profile_name=current_profile)
                    ecs_client = session.client('ecs', region_name=region)

                    service_details = ecs_client.describe_services(
                        cluster=cluster_name,
                        services=[service_name]
                    )['services'][0]

                    task_definition = service_details['taskDefinition']
                    task_def_details = ecs_client.describe_task_definition(
                        taskDefinition=task_definition
                    )['taskDefinition']

                    for container in task_def_details['containerDefinitions']:
                        containers_tree.insert("", "end", values=(container['name'], container['image']))

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to load containers: {str(e)}", parent=update_window)

            load_containers()

            # Function to make the "Image" column editable
            def edit_image(event):
                """Handle double-click to edit the image cell"""
                region = containers_tree.identify_region(event.x, event.y)
                if region == "cell":
                    column = containers_tree.identify_column(event.x)
                    if column == "#2":  # Image column
                        item_id = containers_tree.identify_row(event.y)
                        if item_id:
                            # Get the current image value
                            current_image = containers_tree.item(item_id, "values")[1]

                            # Create an entry widget for editing
                            entry = ttk.Entry(containers_frame)
                            entry.insert(0, current_image)
                            entry.bind("<Return>", lambda e: save_image(item_id, entry))
                            entry.bind("<FocusOut>", lambda e: save_image(item_id, entry))
                            entry.place(x=event.x, y=event.y, width=200)

            def save_image(item_id, entry):
                """Save the edited image value"""
                new_image = entry.get()
                if new_image:
                    # Update the Treeview with the new image value
                    current_values = list(containers_tree.item(item_id, "values"))
                    current_values[1] = new_image
                    containers_tree.item(item_id, values=current_values)
                entry.destroy()

            # Bind double-click to edit the image cell
            containers_tree.bind("<Double-1>", edit_image)

            # Add force deploy checkbox
            force_deploy_var = tk.BooleanVar()
            force_deploy_cb = ttk.Checkbutton(main_container, text="Force Deploy", variable=force_deploy_var)
            force_deploy_cb.pack(pady=5)

            # Add update button
            def update_images_action():
                """Update images for the selected service"""
                new_images = {}
                for item_id in containers_tree.get_children():
                    container_name = containers_tree.item(item_id)['values'][0]
                    new_image = containers_tree.item(item_id)['values'][1]
                    new_images[container_name] = new_image

                if not new_images:
                    messagebox.showwarning("Warning", "No images to update", parent=update_window)
                    return

                if not messagebox.askyesno("Confirm Action", "Are you sure you want to update the images?",
                                           parent=update_window):
                    return

                try:
                    session = boto3.Session(profile_name=current_profile)
                    ecs_client = session.client('ecs', region_name=region)

                    # Get the current task definition
                    service_details = ecs_client.describe_services(
                        cluster=cluster_name,
                        services=[service_name]
                    )['services'][0]

                    task_definition = service_details['taskDefinition']
                    task_def_details = ecs_client.describe_task_definition(
                        taskDefinition=task_definition
                    )['taskDefinition']

                    # Print existing task definition details for debugging
                    print("Existing Task Definition Details:", task_def_details)

                    # Fetch tags associated with the task definition
                    tags = ecs_client.list_tags_for_resource(
                        resourceArn=task_definition
                    ).get('tags', [])

                    # Print tags for debugging
                    print("Tags from Existing Task Definition:", tags)

                    # Update container images
                    for container in task_def_details['containerDefinitions']:
                        if container['name'] in new_images:
                            container['image'] = new_images[container['name']]

                    # Copy all parameters from the existing task definition
                    new_task_def_params = {
                        'family': task_def_details['family'],
                        'containerDefinitions': task_def_details['containerDefinitions'],
                        'volumes': task_def_details.get('volumes', []),
                        'networkMode': task_def_details.get('networkMode', 'bridge'),
                        'taskRoleArn': task_def_details.get('taskRoleArn', ''),
                        'executionRoleArn': task_def_details.get('executionRoleArn', ''),
                        'cpu': task_def_details.get('cpu', ''),
                        'memory': task_def_details.get('memory', ''),
                        'placementConstraints': task_def_details.get('placementConstraints', []),
                        'requiresCompatibilities': task_def_details.get('requiresCompatibilities', []),
                        'runtimePlatform': task_def_details.get('runtimePlatform', {}),
                        'pidMode': task_def_details.get('pidMode'),
                        'ipcMode': task_def_details.get('ipcMode'),
                        'proxyConfiguration': task_def_details.get('proxyConfiguration'),
                        'inferenceAccelerators': task_def_details.get('inferenceAccelerators', [])
                    }

                    # Include tags in the new task definition if they exist
                    if tags:
                        new_task_def_params['tags'] = tags

                    # Remove None values from the parameters
                    new_task_def_params = {k: v for k, v in new_task_def_params.items() if v is not None}

                    # Print new task definition parameters for debugging
                    print("New Task Definition Parameters:", new_task_def_params)

                    # Register new task definition
                    new_task_def = ecs_client.register_task_definition(**new_task_def_params)

                    # Update service with new task definition
                    ecs_client.update_service(
                        cluster=cluster_name,
                        service=service_name,
                        taskDefinition=new_task_def['taskDefinition']['taskDefinitionArn'],
                        forceNewDeployment=force_deploy_var.get()
                    )

                    messagebox.showinfo("Success", "Images updated successfully", parent=update_window)
                    update_window.destroy()

                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update images: {str(e)}", parent=update_window)


            update_button = ttk.Button(main_container, text="Update", command=update_images_action)
            update_button.pack(pady=10)

        def update_cluster_status():
            """Update cluster status asynchronously"""

            def _update():
                time.sleep(10)
                try:
                    session = boto3.Session(profile_name=current_profile)
                    ecs_client = session.client('ecs', region_name=region)

                    cluster_info = ecs_client.describe_clusters(
                        clusters=[cluster_name]
                        # Replace 'your-cluster-name' with the actual name of your ECS cluster
                    )['clusters'][0]

                    active_services = cluster_info["activeServicesCount"]
                    pending_tasks = cluster_info["pendingTasksCount"]
                    running_tasks = cluster_info["runningTasksCount"]

                    total_running_and_pending_services = running_tasks + pending_tasks

                    # Update UI in main thread
                    def update_ui():
                        # Update cluster status in main window
                        new_status = "RUNNING" if total_running_and_pending_services > 0 else "STOPPED"

                        # Update the tree item
                        current_values = list(self.tree.item(item)['values'])
                        current_values[3] = new_status
                        current_values[4] = active_services
                        current_values[5] = running_tasks
                        current_values[6] = pending_tasks

                        if new_status == "RUNNING":
                            self.tree.item(item, values=current_values, tags=('running_cluster',))
                        else:
                            self.tree.item(item, values=current_values, tags=())

                        # Update clusters_data
                        if cluster_name in self.clusters_data:
                            self.clusters_data[cluster_name]['status'] = new_status
                        # print(f"Updated info for cluster: {cluster_name}, new status is: {new_status}")

                    services_window.after(0, update_ui)

                except Exception as e:
                    services_window.after(0, lambda: print(f"Error updating cluster status: {str(e)}"))

            # Start update in background thread
            thread = threading.Thread(target=_update, daemon=True)
            thread.start()


        def load_services():
            """Function to load services in background thread"""
            try:
                session = boto3.Session(profile_name=current_profile)
                ecs_client = session.client('ecs', region_name=region)

                # Get all services using pagination
                all_services = []
                paginator = ecs_client.get_paginator('list_services')

                try:
                    for page in paginator.paginate(cluster=cluster_name):
                        all_services.extend(page.get('serviceArns', []))
                except Exception as e:
                    services_window.after(0,
                                          lambda: messagebox.showerror("Error", f"Failed to list services: {str(e)}"),
                                          parent=services_window)
                    return

                total_services = len(all_services)
                if all_services:
                    sr_no = 1
                    for i in range(0, len(all_services), 10):
                        service_batch = all_services[i:i + 10]
                        try:
                            # Update progress in UI thread
                            progress = (sr_no / total_services) * 100
                            services_window.after(0, lambda p=progress, s=sr_no, t=total_services: (
                                progress_var.set(int(p)),
                                progress_text.config(text=f"Loading service {s} of {t}")
                            ))

                            service_details = ecs_client.describe_services(
                                cluster=cluster_name,
                                services=service_batch
                            )['services']

                            # Update UI in the main thread
                            for service in service_details:
                                status = "RUNNING" if service['desiredCount'] >= 1 else "STOPPED"
                                services_window.after(0,
                                                      lambda s=service, sr=sr_no, st=status: add_service_to_tree(s, sr,
                                                                                                                 st))
                                sr_no += 1

                        except Exception as e:
                            services_window.after(0, lambda: messagebox.showerror(
                                "Error", f"Failed to describe services batch: {str(e)}"),
                                    parent=services_window)

                    # Switch to services frame in UI thread
                    services_window.after(0, lambda: show_services_frame())
                else:
                    services_window.after(0, lambda: (
                        messagebox.showinfo("Information", "No services found in this cluster.", parent=services_window),
                        show_services_frame()
                    ))

            except Exception as e:
                print(e)
                services_window.after(0, lambda: (
                    messagebox.showerror("Error", f"Failed to fetch services: {str(e)}", parent=services_window),
                    show_services_frame()
                ))

        def refresh_services():
            """Refresh services list asynchronously"""
            # Disable all controls
            refresh_button.configure(state='disabled')
            start_stop_button.configure(state='disabled')
            select_all_cb.configure(state='disabled')
            select_running_cb.configure(state='disabled')
            select_stopped_cb.configure(state='disabled')

            # Reset all checkbox states
            select_all_var.set(False)
            select_running_var.set(False)
            select_stopped_var.set(False)

            # Clear existing items
            for item in services_tree.get_children():
                services_tree.delete(item)

            # Reset and show loading bar
            progress_var.set(0)
            progress_text.config(text="")
            loading_frame.pack(fill="x", padx=10, pady=5)

            def enable_buttons():
                refresh_button.configure(state='normal')
                select_all_cb.configure(state='normal')
                update_start_stop_button_state()

            def load_services_wrapper():
                load_services()
                # Enable buttons after loading is complete
                services_window.after(0, enable_buttons)

            # Start loading services in background thread
            thread = threading.Thread(target=load_services_wrapper, daemon=True)
            thread.start()

        # Modify existing toggle_all_services function
        def toggle_all_services():
            """Toggle all service checkboxes"""
            state = select_all_var.get()
            if state:
                # Uncheck other select-all options
                select_running_var.set(False)
                select_stopped_var.set(False)

            for item_id in services_tree.get_children():
                services_tree.checkbox_vars[item_id].set(state)
                services_tree.set(item_id, "Select", "■" if state else "□")
            update_start_stop_button_state()

        def toggle_running_services():
            """Toggle all running services checkboxes"""
            state = select_running_var.get()
            if state:
                # Uncheck other select-all options
                select_all_var.set(False)
                select_stopped_var.set(False)

            for item_id in services_tree.get_children():
                status = services_tree.item(item_id)['values'][3]  # Status column
                if status == "RUNNING":
                    services_tree.checkbox_vars[item_id].set(state)
                    services_tree.set(item_id, "Select", "■" if state else "□")
            update_start_stop_button_state()

        def toggle_stopped_services():
            """Toggle all stopped services checkboxes"""
            state = select_stopped_var.get()
            if state:
                # Uncheck other select-all options
                select_all_var.set(False)
                select_running_var.set(False)

            for item_id in services_tree.get_children():
                status = services_tree.item(item_id)['values'][3]  # Status column
                if status == "STOPPED":
                    services_tree.checkbox_vars[item_id].set(state)
                    services_tree.set(item_id, "Select", "■" if state else "□")
            update_start_stop_button_state()

        def toggle_service_checkbox(event):
            """Handle clicking on the checkbox column"""
            region = services_tree.identify_region(event.x, event.y)
            if region == "cell":
                column = services_tree.identify_column(event.x)
                if column == "#1":  # Select column
                    item_id = services_tree.identify_row(event.y)
                    if item_id:
                        current_state = services_tree.checkbox_vars[item_id].get()
                        new_state = not current_state
                        services_tree.checkbox_vars[item_id].set(new_state)
                        services_tree.set(item_id, "Select", "■" if new_state else "□")
                        update_start_stop_button_state()

        # Bind checkbox column clicks
        services_tree.bind("<Button-1>", toggle_service_checkbox)

        def add_service_to_tree(service, sr_no, status):
            """Add a service to the treeview in the main thread"""
            # Calculate pending tasks
            pending_count = service.get('pendingCount', 0)

            # Create checkbox variable
            checkbox_var = tk.BooleanVar()
            checkbox = ttk.Checkbutton(services_tree, variable=checkbox_var)

            item_id = services_tree.insert("", "end", values=(
                "",  # Empty space for checkbox
                f"{sr_no}",
                service['serviceName'],
                status,
                service['runningCount'],
                service['desiredCount'],
                pending_count
            ))

            # Store the checkbox variable in a dictionary using item_id as key
            if not hasattr(services_tree, 'checkbox_vars'):
                services_tree.checkbox_vars = {}
            services_tree.checkbox_vars[item_id] = checkbox_var

            services_tree.set(item_id, "Select", "□")  # Unicode empty checkbox

            if service['desiredCount'] >= 1:
                services_tree.item(item_id, tags=('running_service',))

        def show_services_frame():
            """Hide loading indicators and enable controls"""
            progress_var.set(0)
            progress_text.config(text="")
            loading_frame.pack_forget()
            # Enable all checkboxes after loading
            select_all_cb.configure(state='normal')
            select_running_cb.configure(state='normal')
            select_stopped_cb.configure(state='normal')

        def start_stop_service():
            """Start/Stop selected services asynchronously"""
            selected_services = []
            first_status = None

            for item_id in services_tree.get_children():
                if services_tree.checkbox_vars[item_id].get():
                    service_name = services_tree.item(item_id)['values'][2]  # Service name
                    status = services_tree.item(item_id)['values'][3]  # Status

                    if first_status is None:
                        first_status = status

                    selected_services.append(service_name)

            if not selected_services:
                messagebox.showwarning("Warning", "Please select at least one service", parent=services_window)
                return

            # Determine the action based on the current state
            new_desired_count = 0 if first_status == "RUNNING" else 1
            action_text = "stop" if first_status == "RUNNING" else "start"

            if not messagebox.askyesno("Confirm Action",
                                       f"Are you sure you want to {action_text} the selected services?", parent=services_window):
                return

            # Disable buttons
            refresh_button.configure(state='disabled')
            start_stop_button.configure(state='disabled')
            select_all_cb.configure(state='disabled')

            def _update_service():
                try:
                    session = boto3.Session(profile_name=current_profile)
                    ecs_client = session.client('ecs', region_name=region)

                    for service_name in selected_services:
                        ecs_client.update_service(
                            cluster=cluster_name,
                            service=service_name,
                            desiredCount=new_desired_count,
                            forceNewDeployment=True
                        )

                    # Update UI in main thread
                    def update_ui():
                        refresh_services()
                        update_cluster_status()
                        services_window.lift()
                        services_window.focus_force()

                    services_window.after(0, update_ui)

                except Exception as e:
                    services_window.after(0, lambda: (
                        messagebox.showerror("Error", f"Failed to update services: {str(e)}", parent=services_window),
                        refresh_button.configure(state='normal'),
                        start_stop_button.configure(state='normal'),
                        select_all_cb.configure(state='normal')
                    ))

            # Start service update in background thread
            thread = threading.Thread(target=_update_service, daemon=True)
            thread.start()

        # Create bottom frame for buttons and warning
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(fill="x", padx=10, pady=5)

        # Create warning label with red text
        warning_label = ttk.Label(bottom_frame,
                                  text="Warning: Select unique state services to start/stop.",
                                  foreground='red')

        # Create bottom frame for buttons and warning
        bottom_frame = ttk.Frame(main_container)
        bottom_frame.pack(fill="x", padx=10, pady=5)

        # Create buttons frame on the left
        buttons_frame = ttk.Frame(bottom_frame)
        buttons_frame.pack(side="left")

        # Add refresh and start/stop buttons to buttons frame
        refresh_button = ttk.Button(buttons_frame, text="Refresh", command=refresh_services)
        refresh_button.pack(side="left", padx=(0, 5))  # Add padding between buttons

        start_stop_button = ttk.Button(buttons_frame, text="Start/Stop Selected Services",
                                       command=start_stop_service, state='disabled')
        start_stop_button.pack(side="left")

        # Add "Update Images" button next to "Start/Stop Selected Services" button
        update_images_button = ttk.Button(buttons_frame, text="Update Images", command=update_images)
        update_images_button.pack(side="left", padx=(0, 5))

        # Create warning label with red text (on the right)
        warning_label = ttk.Label(bottom_frame,
                                  text="Warning: Select unique state services to start/stop.",
                                  foreground='red')
        warning_label.pack(side="right")
        warning_label.pack_forget()  # Hide initially

        # Initial load of services
        refresh_services()

    def on_config_window_close(self, cluster_name):
        """Handle CPU/Memory config window closing"""
        if cluster_name in self.config_windows:
            self.config_windows[cluster_name].grab_release()
            self.config_windows[cluster_name].destroy()
            del self.config_windows[cluster_name]

    def show_cpu_memory_config(self):
        try:
            selected = self.tree.selection()
            if not selected:
                messagebox.showwarning("Warning", "Please select a cluster")
                return

            item = selected[0]
            cluster_name = self.tree.item(item)['values'][1]
            region = self.tree.item(item)['values'][2]

            if cluster_name in self.config_windows and self.config_windows[cluster_name].winfo_exists():
                self.config_windows[cluster_name].lift()
                self.config_windows[cluster_name].focus_force()
                return

            session = boto3.Session(profile_name=self.profile_var.get())
            ecs_client = session.client('ecs', region_name=region)

            config_window = tk.Toplevel()
            config_window.title(f"CPU/Memory Configuration - {cluster_name}")
            config_window.geometry("600x400")

            self.config_windows[cluster_name] = config_window
            config_window.protocol("WM_DELETE_WINDOW", lambda: self.on_config_window_close(cluster_name))

            # Progress bar frame
            progress_frame = ttk.Frame(config_window)
            progress_frame.pack(fill='x', padx=10, pady=5)
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_frame, variable=progress_var, maximum=100)
            progress_bar.pack(fill='x')
            progress_label = ttk.Label(progress_frame, text="Fetching services...")
            progress_label.pack()

            # Treeview frame
            frame = ttk.Frame(config_window)
            frame.pack(fill='both', expand=True, padx=5, pady=5)

            tree = ttk.Treeview(frame, columns=("Sr. No", "Service Name", "CPU", "Memory"), show='headings')
            tree.heading("Sr. No", text="Sr. No")
            tree.heading("Service Name", text="Service Name")
            tree.heading("CPU", text="CPU")
            tree.heading("Memory", text="Memory")
            tree.column("Sr. No", width=60, anchor='center')
            tree.column("Service Name", width=200)
            tree.column("CPU", width=100, anchor='center')
            tree.column("Memory", width=100, anchor='center')

            scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
            scrollbar.pack(side='right', fill='y')
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(fill='both', expand=True)

            # Button frame
            button_frame = ttk.Frame(config_window)
            button_frame.pack(fill='x', padx=10, pady=5)

            def refresh_data():
                refresh_button.config(state='disabled')
                copy_button.config(state='disabled')
                copy_excel_button.config(state='disabled')
                edit_button.config(state='disabled')
                tree.delete(*tree.get_children())
                progress_frame.pack(fill='x', padx=10, pady=5)
                fetch_data()

            # Define update_service_config function
            def update_service_config():
                selected = tree.selection()
                if not selected:
                    return

                service_item = tree.item(selected[0])
                service_name = service_item['values'][1]

                # Create edit window
                edit_window = tk.Toplevel()
                edit_window.title(f"Edit CPU/Memory - {service_name}")
                edit_window.geometry("400x300")
                edit_window.transient(config_window)

                # Make the window modal
                edit_window.grab_set()

                # Service name label
                tk.Label(edit_window, text=f"Service: {service_name}").pack(pady=10)

                # CPU dropdown
                cpu_frame = ttk.Frame(edit_window)
                cpu_frame.pack(pady=10)
                tk.Label(cpu_frame, text="CPU (vCPU):").pack(side='left')
                cpu_values = ['256', '512', '1024', '2048', '4096', '8192', '16384']
                cpu_var = tk.StringVar()
                cpu_dropdown = ttk.Combobox(cpu_frame, textvariable=cpu_var, values=cpu_values, state='readonly')
                cpu_dropdown.pack(side='left', padx=5)

                # Memory dropdown
                mem_frame = ttk.Frame(edit_window)
                mem_frame.pack(pady=10)
                tk.Label(mem_frame, text="Memory (GB):").pack(side='left')
                mem_var = tk.StringVar()
                mem_dropdown = ttk.Combobox(mem_frame, textvariable=mem_var, state='readonly')
                mem_dropdown.pack(side='left', padx=5)

                # Error label
                error_label = tk.Label(edit_window, text="", fg="red")
                error_label.pack(pady=10)

                def update_memory_options(*args):
                    cpu = cpu_var.get()
                    if cpu == '256':
                        mem_values = ['0.5', '1', '2']
                    elif cpu == '512':
                        mem_values = ['1', '2', '3', '4']
                    elif cpu == '1024':
                        mem_values = ['2', '3', '4', '5', '6', '7', '8']
                    elif cpu == '2048':
                        mem_values = [str(x) for x in range(4, 17)]
                    elif cpu == '4096':
                        mem_values = [str(x) for x in range(8, 31)]
                    elif cpu == '8192':
                        mem_values = [str(x) for x in range(16, 61, 4)]
                    elif cpu == '16384':
                        mem_values = [str(x) for x in range(32, 121, 8)]
                    else:
                        mem_values = []

                    mem_dropdown['values'] = mem_values
                    mem_var.set('')  # Reset memory selection
                    validate_config()

                def validate_config(*args):
                    cpu = cpu_var.get()
                    mem = mem_var.get()
                    valid = False
                    error_msg = ""

                    if cpu and mem:
                        cpu_int = int(cpu)
                        mem_int = int(float(mem) * 1024)  # Convert GB to MB

                        if cpu_int == 256 and mem_int in [512, 1024, 2048]:
                            valid = True
                        elif cpu_int == 512 and mem_int in [1024, 2048, 3072, 4096]:
                            valid = True
                        elif cpu_int == 1024 and mem_int in [2048, 3072, 4096, 5120, 6144, 7168, 8192]:
                            valid = True
                        elif cpu_int == 2048 and 4096 <= mem_int <= 16384 and mem_int % 1024 == 0:
                            valid = True
                        elif cpu_int == 4096 and 8192 <= mem_int <= 30720 and mem_int % 1024 == 0:
                            valid = True
                        elif cpu_int == 8192 and 16384 <= mem_int <= 61440 and mem_int % 4096 == 0:
                            valid = True
                        elif cpu_int == 16384 and 32768 <= mem_int <= 122880 and mem_int % 8192 == 0:
                            valid = True

                        if not valid:
                            error_msg = "Selected CPU/Memory configuration is not compatible"

                    error_label.config(text=error_msg)
                    update_btn.config(state='normal' if valid else 'disabled')

                cpu_var.trace('w', update_memory_options)
                mem_var.trace('w', validate_config)

                def update_and_deploy():

                    messagebox.showinfo("Info", "This feature is in development phase.", parent=edit_window)
                    return

                    # Display confirmation dialog before updating the service
                    confirmation_message = (
                        f"Are you sure you want to update the service '{service_name}'?\n\n"
                        f"New Configuration:\n"
                        f" - CPU: {cpu_var.get()}\n"
                        f" - Memory: {int(float(mem_var.get()) * 1024)} MB\n\n"
                        "This will create a new task definition revision and deploy it."
                    )

                    try:
                        user_confirmed = messagebox.askyesno(
                            title="Confirm Action",
                            message=confirmation_message,
                            parent=edit_window
                        )

                        if not user_confirmed:
                            return  # User canceled the action
                    except Exception as e:
                        messagebox.showerror("Error", f"An unexpected error occurred: {e}", parent=edit_window)

                    try:
                        # Get task definition info from current service
                        response = ecs_client.describe_services(
                            cluster=cluster_name,
                            services=[service_name]
                        )
                        current_task_def = response['services'][0]['taskDefinition']

                        # Get current task definition details
                        task_def_response = ecs_client.describe_task_definition(
                            taskDefinition=current_task_def
                        )
                        task_def = task_def_response['taskDefinition']

                        # Create new task definition revision with updated CPU/memory at task level only
                        # Keep container definitions unchanged from previous revision
                        container_defs = task_def['containerDefinitions']

                        # Get tags from previous revision
                        tags = ecs_client.list_tags_for_resource(
                            resourceArn=current_task_def
                        ).get('tags', [])

                        # Register new task definition
                        new_task_def_response = ecs_client.register_task_definition(
                            family=task_def['family'],
                            taskRoleArn=task_def.get('taskRoleArn', ''),
                            executionRoleArn=task_def.get('executionRoleArn', ''),
                            networkMode=task_def.get('networkMode', 'bridge'),
                            containerDefinitions=container_defs,
                            volumes=task_def.get('volumes', []),
                            placementConstraints=task_def.get('placementConstraints', []),
                            requiresCompatibilities=task_def.get('requiresCompatibilities', []),
                            cpu=str(cpu_var.get()),
                            memory=str(int(float(mem_var.get()) * 1024)),
                            tags=tags
                        )

                        # Update service with new task definition
                        ecs_client.update_service(
                            cluster=cluster_name,
                            service=service_name,
                            taskDefinition=new_task_def_response['taskDefinition']['taskDefinitionArn'],
                            desiredCount=1,
                            forceNewDeployment=True
                        )

                        messagebox.showinfo("Success", f"Service {service_name} is being updated with new CPU/Memory configuration...", parent=edit_window)
                        edit_window.destroy()
                        refresh_data()  # Refresh the service list

                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to update service: {str(e)}")

                update_btn = ttk.Button(edit_window, text="Update/Deploy", state='disabled', command=update_and_deploy)
                update_btn.pack(pady=20)

            refresh_button = ttk.Button(button_frame, text="Refresh", command=refresh_data)
            edit_button = ttk.Button(button_frame, text="Edit CPU and Memory", command=update_service_config, state='disabled')
            refresh_button.pack(side='left', padx=5)
            edit_button.pack(side='left', padx=5)

            def on_tree_select(event):
                selected = tree.selection()
                edit_button.config(state='normal' if selected else 'disabled')

            tree.bind('<<TreeviewSelect>>', on_tree_select)
            refresh_button.pack(side='left', padx=5)

            # Copy to Clipboard (Formatted)
            def copy_to_clipboard():
                rows = [
                    [tree.item(child)['values'][1], tree.item(child)['values'][2], tree.item(child)['values'][3]]
                    for child in tree.get_children()
                ]
                header = ["Service Name", "CPU", "Memory"]
                rows.insert(0, header)
                col_widths = [max(len(str(row[i])) for row in rows) + 2 for i in range(len(header))]
                formatted_rows = [
                    "".join(str(value).ljust(col_widths[i]) for i, value in enumerate(row)) for row in rows
                ]
                clipboard_data = "\n".join(formatted_rows)
                config_window.clipboard_clear()
                config_window.clipboard_append(clipboard_data)
                messagebox.showinfo("Info", "Data copied to clipboard", parent=tree)

            copy_button = ttk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard)
            copy_button.pack(side='right', padx=5)

            # Copy Data for Excel (Tab-separated)
            def copy_data_for_excel():
                rows = [
                    [tree.item(child)['values'][1], tree.item(child)['values'][2], tree.item(child)['values'][3]]
                    for child in tree.get_children()
                ]
                header = ["Service Name", "CPU", "Memory"]
                rows.insert(0, header)
                clipboard_data = "\n".join("\t".join(map(str, row)) for row in rows)
                config_window.clipboard_clear()
                config_window.clipboard_append(clipboard_data)
                messagebox.showinfo("Info", "Tab-separated data copied for Excel", parent=tree)

            copy_excel_button = ttk.Button(button_frame, text="Copy Data for Excel", command=copy_data_for_excel)
            copy_excel_button.pack(side='right', padx=5)

            refresh_button.config(state='disabled')
            copy_button.config(state='disabled')
            copy_excel_button.config(state='disabled')

            def fetch_data():
                try:
                    services = []
                    paginator = ecs_client.get_paginator('list_services')
                    for page in paginator.paginate(cluster=cluster_name):
                        services.extend(page['serviceArns'])

                    total_services = len(services)
                    progress_label.config(text=f"Found {total_services} services. Starting fetch...")

                    for index, service_arn in enumerate(services, start=1):
                        progress = (index / total_services) * 100
                        progress_var.set(progress)
                        progress_label.config(text=f"Fetching service {index}/{total_services}...")
                        service_name = service_arn.split('/')[-1]
                        service_details = \
                        ecs_client.describe_services(cluster=cluster_name, services=[service_arn])['services'][0]
                        task_definition_arn = service_details['taskDefinition']
                        task_def = ecs_client.describe_task_definition(taskDefinition=task_definition_arn)[
                            'taskDefinition']
                        cpu = task_def.get('cpu', 'N/A')
                        memory = task_def.get('memory', 'N/A')
                        config_window.after(0, lambda t=tree, i=index, sn=service_name, c=cpu, m=memory:
                        t.insert('', 'end', values=(i, sn, c, m)))
                        config_window.update()

                    progress_frame.pack_forget()
                    refresh_button.config(state='normal')
                    copy_button.config(state='normal')
                    copy_excel_button.config(state='normal')
                    edit_button.config(state='normal')


                except Exception as e:
                    messagebox.showerror("Error", f"Failed to fetch CPU/Memory configuration: {str(e)}")
                    config_window.destroy()

            threading.Thread(target=fetch_data, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch CPU/Memory configuration: {str(e)}")

    def show_progress_dialog(self, total_steps):
        progress_window = tk.Toplevel(self.parent)
        progress_window.title("Loading Clusters")
        progress_window.geometry("300x150")
        progress_window.transient(self.parent)

        # Center the progress window
        progress_window.geometry("+%d+%d" % (
            self.parent.winfo_rootx() + self.parent.winfo_width() // 2 - 150,
            self.parent.winfo_rooty() + self.parent.winfo_height() // 2 - 75))

        # Add a label
        label = ttk.Label(progress_window, text="Loading clusters...")
        label.pack(pady=10)

        # Create and pack the progressbar
        progress_bar = ttk.Progressbar(
            progress_window,
            orient="horizontal",
            length=200,
            mode="determinate"
        )
        progress_bar.pack(pady=10)

        # Add a status label
        status_label = ttk.Label(progress_window, text="")
        status_label.pack(pady=5)

        return progress_window, progress_bar, status_label

    def change_button_status(self, state):
        buttons = [
            self.load_clusters_button,
            self.start_cluster_button,
            self.stop_cluster_button,
            self.restart_cluster_button,
            self.refresh_button,
        ]

        for button in buttons:
            button["state"] = state

    # Cleaning up the loading bar
    def load_clusters(self):
        self.change_button_status("disabled")
        self.show_popup_status_message(f"Cluster(s) loading. Please wait...!", 4000)

        profile = self.profile_var.get()
        regions_input = self.region_var.get().strip()

        if not profile:
            messagebox.showerror("Error", "Please enter a profile name")
            self.change_button_status("normal")
            return

        self.status_var.set("Loading clusters...")
        self.tree.delete(*self.tree.get_children())
        self.clusters_data = {}  # Initialize clusters_data dictionary

        def load_thread():
            try:
                session = boto3.Session(profile_name=profile)

                # Get regions based on input
                if regions_input:
                    regions = [r.strip() for r in regions_input.split(',')]
                else:
                    regions = session.get_available_regions('ecs')

                sr_no = 1
                total_clusters_processed = 0

                # Process clusters in each region
                for region in regions:
                    try:
                        ecs_client = session.client('ecs', region_name=region)
                        clusters = ecs_client.list_clusters()['clusterArns']
                        total_clusters_processed += len(clusters)

                        tree_data = []  # Collect data for batch UI update
                        batch_size = 10

                        for i in range(0, len(clusters), batch_size):
                            batch = clusters[i:i + batch_size]

                            try:
                                response = ecs_client.describe_clusters(clusters=batch)
                                for cluster_info in response.get('clusters', []):
                                    cluster_arn = cluster_info['clusterArn']
                                    cluster_name = cluster_arn.split('/')[-1]
                                    active_services = cluster_info["activeServicesCount"]
                                    pending_tasks = cluster_info["pendingTasksCount"]
                                    running_tasks = cluster_info["runningTasksCount"]

                                    status = "RUNNING" if (running_tasks + pending_tasks) > 0 else "STOPPED"

                                    self.clusters_data[cluster_name] = {
                                        'region': region,
                                        'arn': cluster_arn,
                                        'status': status,
                                        'active_services': active_services,
                                        'pending_task': pending_tasks,
                                        'running_tasks': running_tasks,
                                    }

                                    tree_data.append((sr_no, cluster_name, region, status, active_services,
                                                      running_tasks, pending_tasks))
                                    sr_no += 1

                            except ClientError as e:
                                print(f"Error processing clusters in {region}: {str(e)}")
                                self.change_button_status("normal")

                        # Batch update tree UI
                        def update_tree_bulk():
                            for data in tree_data:
                                try:
                                    item_id = self.tree.insert('', 'end', values=data)
                                    if data[3] == "RUNNING":  # Status column
                                        self.tree.item(item_id, tags=('running_cluster',))
                                except tk.TclError:
                                    pass

                        self.parent.after(0, update_tree_bulk)

                    except ClientError as e:
                        print(f"Error in region {region}: {str(e)}")
                        self.change_button_status("normal")

                # Update final status
                def update_status():
                    if total_clusters_processed == 0:
                        self.status_var.set("No clusters found in given region(s).")
                        messagebox.showinfo("Info", "No clusters found in the given region(s).")
                    else:
                        self.status_var.set("Clusters loaded")
                    self.change_button_status("normal")

                self.parent.after(0, update_status)

            except ProfileNotFound:
                def handle_profile_error():
                    self.status_var.set("Error loading clusters")
                    messagebox.showerror("Error", f"Profile '{profile}' not found")
                    self.change_button_status("normal")

                self.parent.after(0, handle_profile_error)

            except Exception as e:
                error_message = str(e)
                self.show_popup_status_message("AWS SSO Login Initiated...")

                if "Token not found" in error_message or "expired" in error_message.lower() or "error loading sso token" in error_message.lower():
                    self.parent.after(0, self.handle_sso_login)
                else:
                    def handle_general_error(error_msg):
                        self.status_var.set("Error loading clusters")
                        messagebox.showerror("Error", f"Failed to load clusters: {error_msg}")
                        self.change_button_status("normal")

                    self.parent.after(0, handle_general_error, str(e))

        # Start the loading thread
        threading.Thread(target=load_thread, daemon=True).start()
    def handle_sso_login(self):
        profile = self.profile_var.get()

        # Create loading window
        loading_window = tk.Toplevel(self.parent)
        loading_window.title("AWS SSO Login")
        loading_window.geometry("400x150")
        loading_window.transient(self.parent)

        # Make the window modal
        # loading_window.grab_set()

        # Prevent closing the window with the X button
        loading_window.protocol("WM_DELETE_WINDOW", lambda: None)

        # Center the window
        loading_window.update_idletasks()
        width = loading_window.winfo_width()
        height = loading_window.winfo_height()
        x = (loading_window.winfo_screenwidth() // 2) - (width // 2)
        y = (loading_window.winfo_screenheight() // 2) - (height // 2)
        loading_window.geometry(f'{width}x{height}+{x}+{y}')

        # Add loading message
        message_label = ttk.Label(
            loading_window,
            text=f"Initiating AWS SSO login for profile: {profile}...\nPlease complete the authentication in your browser.",
            wraplength=350,
            justify="center"
        )
        message_label.pack(pady=20)

        # Add spinning progress bar
        progress = ttk.Progressbar(
            loading_window,
            mode='indeterminate',
            length=200
        )
        progress.pack(pady=10)
        progress.start()

        def execute_sso_login():
            try:
                # Execute the SSO login command
                process = subprocess.run(
                    f"aws sso login --profile {profile}",
                    shell=True,
                    capture_output=True,
                    text=True
                )

                if process.returncode == 0:
                    loading_window.destroy()
                    # messagebox.showinfo("Success", "AWS SSO login successful!")
                    self.show_popup_status_message(f"AWS SSO login successful!")

                    # Reload clusters after successful login
                    self.load_clusters()
                else:
                    loading_window.destroy()
                    messagebox.showerror("Error", f"SSO login failed: {process.stderr}")
                    self.change_button_status("normal")

            except Exception as login_error:
                loading_window.destroy()
                messagebox.showerror("Error", f"Failed to execute SSO login: {str(login_error)}")
                self.change_button_status("normal")

        # Run the SSO login in a separate thread
        threading.Thread(target=execute_sso_login, daemon=True).start()

    def update_cluster_status(self, cluster_name, new_status):
        """
        Updates the cluster status in the tree view after checking running services
        """
        try:
            cluster_data = self.clusters_data.get(cluster_name)
            if cluster_data:
                session = boto3.Session(profile_name=self.profile_var.get())
                ecs_client = session.client('ecs', region_name=cluster_data['region'])

                # Get all services for the cluster
                services = []
                paginator = ecs_client.get_paginator('list_services')
                for page in paginator.paginate(cluster=cluster_data['arn']):
                    services.extend(page.get('serviceArns', []))

                running_services = 0
                if services:
                    for i in range(0, len(services), 10):
                        service_batch = services[i:i + 10]
                        service_details = ecs_client.describe_services(
                            cluster=cluster_data['arn'],
                            services=service_batch
                        )['services']

                        for service in service_details:
                            if service['runningCount'] > 0:
                                running_services += 1

                # Update status based on running services
                actual_status = "RUNNING" if running_services > 0 else "STOPPED"

                # Update tree view
                for item in self.tree.get_children():
                    if self.tree.item(item)['values'][0] == cluster_name:
                        values = list(self.tree.item(item)['values'])
                        values[2] = actual_status
                        self.tree.item(item, values=values)
                        break

                # Update clusters_data
                self.clusters_data[cluster_name]['status'] = actual_status

        except Exception as e:
            print(f"Error updating cluster status: {str(e)}")

    def start_cluster(self):
        self.change_button_status("disabled")
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a cluster")
            self.change_button_status("normal")
            return

        cluster_name = self.tree.item(selected[0])['values'][1]
        cluster_data = self.clusters_data.get(cluster_name)

        if not self.restart:
            if not messagebox.askyesno("Confirm Action",
                                       f"Are you sure you want to start the selected {cluster_name} cluster?",
                                       parent=self.parent):
                self.change_button_status("normal")
                return

        if cluster_data:
            try:
                session = boto3.Session(profile_name=self.profile_var.get())
                ecs_client = session.client('ecs', region_name=cluster_data['region'])

                # Get all services using pagination
                all_services = []
                paginator = ecs_client.get_paginator('list_services')

                try:
                    for page in paginator.paginate(cluster=cluster_data['arn']):
                        all_services.extend(page.get('serviceArns', []))
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to list services: {str(e)}")
                    self.change_button_status("normal")
                    return

                total_services = len(all_services)
                if total_services == 0:
                    messagebox.showinfo("Information", "No services found in this cluster.")
                    self.change_button_status("normal")
                    return

                # Create progress window
                progress_window = tk.Toplevel(self.parent)
                progress_window.title("Starting Cluster Services")
                progress_window.geometry("400x150")
                progress_window.transient(self.parent)  # Set as transient to main window
                # progress_window.grab_set()  # Make window modal

                # Center the progress window
                progress_window.update_idletasks()
                width = progress_window.winfo_width()
                height = progress_window.winfo_height()
                x = (progress_window.winfo_screenwidth() // 2) - (width // 2)
                y = (progress_window.winfo_screenheight() // 2) - (height // 2)
                progress_window.geometry(f'{width}x{height}+{x}+{y}')

                # Progress label
                progress_label = ttk.Label(progress_window, text="Starting services...", padding=(10, 5))
                progress_label.pack()

                # Service count label
                count_label = ttk.Label(progress_window, text="", padding=(10, 5))
                count_label.pack()

                # Progress bar
                progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
                progress_bar.pack(padx=10, pady=10)

                # Current service label
                current_service_label = ttk.Label(progress_window, text="", padding=(10, 5))
                current_service_label.pack()

                success_count = 0
                failed_services = []

                def update_progress(current_count, service_name):
                    progress = (current_count / total_services) * 100
                    progress_bar['value'] = progress
                    count_label['text'] = f"Progress: {current_count}/{total_services} services"
                    current_service_label['text'] = f"Starting: {service_name}"
                    progress_window.update()

                def update_tree_status():
                    # Update the tree item status
                    item = selected[0]
                    current_values = list(self.tree.item(item)['values'])
                    current_values[3] = "RUNNING"  # Update status to RUNNING
                    # current_values[4] = f"{len(all_services)}/{len(all_services)}"
                    self.tree.item(item, values=current_values, tags=('running',))
                    self.tree.tag_configure('running', background='light green')

                    # Update the internal data structure
                    if cluster_name in self.clusters_data:
                        self.clusters_data[cluster_name]['status'] = "RUNNING"

                def process_services():
                    nonlocal success_count

                    # Process services in batches of 10 (AWS API limitation)
                    for i in range(0, len(all_services), 10):
                        service_batch = all_services[i:i + 10]
                        try:
                            # Update each service in the batch
                            for service_arn in service_batch:
                                try:
                                    service_name = service_arn.split('/')[-1]  # Extract service name from ARN
                                    ecs_client.update_service(
                                        cluster=cluster_data['arn'],
                                        service=service_arn,
                                        desiredCount=1,
                                        forceNewDeployment=True
                                    )
                                    success_count += 1
                                    update_progress(success_count, service_name)
                                except Exception as e:
                                    failed_services.append(f"{service_arn}: {str(e)}")
                                    print(f"Error starting service {service_arn}: {str(e)}")
                        except Exception as e:
                            print(f"Error processing batch: {str(e)}")
                            continue

                    # Update the cluster status in the UI thread
                    self.parent.after(0, update_tree_status)
                    # self.parent.after(0, lambda: self.update_cluster_status(cluster_name, "RUNNING"))

                    # Close progress window
                    progress_window.destroy()

                    # Show results
                    if success_count == total_services:
                        messagebox.showinfo("Success",
                                            f"Successfully started all {success_count} services in cluster {cluster_name}")
                    elif success_count > 0:
                        messagebox.showwarning("Partial Success",
                                               f"Started {success_count} out of {total_services} services in cluster {cluster_name}\n\n"
                                               f"Failed services:\n" + "\n".join(failed_services))
                    else:
                        messagebox.showerror("Error",
                                             f"Failed to start any services in cluster {cluster_name}\n\n"
                                             f"Errors:\n" + "\n".join(failed_services))
                    self.change_button_status("normal")

                # Start processing in a separate thread
                threading.Thread(target=process_services, daemon=True).start()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to start cluster: {str(e)}")
                self.change_button_status("normal")
                print(f"Error in start_cluster: {str(e)}")

    def stop_cluster(self):
        self.change_button_status("disabled")
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a cluster first")
            self.change_button_status("normal")
            return

        cluster_name = self.tree.item(selected[0])['values'][1]
        region = self.tree.item(selected[0])['values'][2]
        current_profile = self.profile_var.get()

        if not self.restart:
            if not messagebox.askyesno("Confirm Action",
                                       f"Are you sure you want to stop the selected {cluster_name} cluster?",
                                       parent=self.parent):
                self.change_button_status("normal")
                return

        try:
            # Create session
            session = boto3.Session(profile_name=current_profile, region_name=region)
            ecs_client = session.client('ecs')

            # Get all services in the cluster
            all_services = []
            paginator = ecs_client.get_paginator('list_services')
            for page in paginator.paginate(cluster=cluster_name):
                all_services.extend(page.get('serviceArns', []))

            if not all_services:
                messagebox.showinfo("Information", "No services found in the cluster.")
                self.change_button_status("normal")
                return

            total_services = len(all_services)
            success_count = 0
            failed_services = []

            # Create progress window
            progress_window = tk.Toplevel(self.parent)
            progress_window.title("Stopping Services")
            progress_window.geometry("400x150")
            progress_window.transient(self.parent)
            # progress_window.grab_set()

            # Center the progress window
            window_width = 400
            window_height = 150
            screen_width = self.parent.winfo_screenwidth()
            screen_height = self.parent.winfo_screenheight()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            progress_window.geometry(f"{window_width}x{window_height}+{x}+{y}")

            # Create main progress frame
            main_frame = ttk.Frame(progress_window)
            main_frame.pack(fill='x', padx=10, pady=5)

            # Create title label
            title_label = ttk.Label(main_frame, text="Stopping services...")
            title_label.pack(pady=5)

            # Create progress count label
            progress_label = ttk.Label(main_frame, text=f"Progress: 0/{total_services} services")
            progress_label.pack(pady=5)

            # Create main progress bar
            main_progress = ttk.Progressbar(main_frame, mode='determinate', maximum=total_services)
            main_progress.pack(fill='x', pady=5)

            # Create service label
            service_label = ttk.Label(main_frame, text="Stopping: ")
            service_label.pack(pady=5)

            def process_services():
                nonlocal success_count

                try:
                    # Process services in batches of 10
                    for i in range(0, len(all_services), 10):
                        service_batch = all_services[i:i + 10]
                        service_details = ecs_client.describe_services(
                            cluster=cluster_name,
                            services=service_batch
                        )['services']

                        for service in service_details:
                            service_name = service['serviceName']

                            try:
                                # Update service to stop it
                                ecs_client.update_service(
                                    cluster=cluster_name,
                                    service=service_name,
                                    desiredCount=0,
                                    forceNewDeployment=True
                                )
                                
                                success_count += 1

                                # Update progress in main UI thread
                                self.parent.after(0,
                                                lambda s=service_name, sc=success_count: update_progress(s, sc, True))
                            except Exception as e:
                                print(f"Error stopping service {service_name}: {str(e)}")
                                failed_services.append(f"{service_name}: {str(e)}")
                                self.parent.after(0,
                                                lambda s=service_name, sc=success_count: update_progress(s, sc, False))

                    # Update final status
                    self.parent.after(0, update_final_status)

                except Exception as e:
                    self.parent.after(0, lambda: handle_error(str(e)))

            def update_progress(service_name, current_count, success):
                # Update main progress bar and label
                main_progress['value'] = current_count
                progress_label.config(text=f"Progress: {current_count}/{total_services} services")

                # Update service status label
                service_label.config(text=f"Stopping: {service_name}")

            def update_final_status():
                progress_window.destroy()
                if success_count == total_services:
                    messagebox.showinfo("Success",
                                        f"Successfully stopped all {total_services} services in cluster {cluster_name}")
                elif success_count > 0:
                    messagebox.showwarning("Partial Success",
                                           f"Stopped {success_count} out of {total_services} services in cluster {cluster_name}\n\n"
                                           f"Failed services:\n" + "\n".join(failed_services))
                else:
                    messagebox.showerror("Error",
                                         f"Failed to stop any services in cluster {cluster_name}\n\n"
                                         f"Errors:\n" + "\n".join(failed_services))
                self.change_button_status("normal")

                # Update the tree item status
                def update_tree_status():
                    item = selected[0]
                    current_values = list(self.tree.item(item)['values'])
                    current_values[3] = "STOPPED"  # Update status to RUNNING
                    current_values[4] = f"0/{len(all_services)}"
                    # self.tree.item(item, values=current_values, tags=('running',))
                    self.tree.item(item, values=current_values, tags=())
                    # self.tree.tag_configure('running', background='light green')

                    # Update the internal data structure
                    if cluster_name in self.clusters_data:
                        self.clusters_data[cluster_name]['status'] = "STOPPED"


                update_tree_status()
                # # Update cluster status in the tree
                # for item in self.tree.get_children():
                #     if self.tree.item(item)['values'][1] == cluster_name:
                #         current_values = list(self.tree.item(item)['values'])
                #         current_values[3] = "STOPPED"
                #         current_values[4] = f"0/{len(all_services)}"

                        # # Get current running services count
                        # try:
                        #     services_count = 0
                        #     running_count = 0
                        #     paginator = ecs_client.get_paginator('list_services')
                        #
                        #     for page in paginator.paginate(cluster=cluster_name):
                        #         service_arns = page.get('serviceArns', [])
                        #         if service_arns:
                        #             services_count += len(service_arns)
                        #             services = ecs_client.describe_services(
                        #                 cluster=cluster_name,
                        #                 services=service_arns
                        #             )['services']
                        #
                        #             for service in services:
                        #                 if service['runningCount'] > 0:
                        #                     running_count += 1
                        #
                        #     current_values[4] = f"{running_count}/{services_count}"
                        # except Exception as e:
                        #     print(f"Error updating running services count: {str(e)}")
                        #     current_values[4] = "0/0"
                        #
                        # self.tree.item(item, values=current_values, tags=())
                        # break

            def handle_error(error_message):
                progress_window.destroy()
                messagebox.showerror("Error", f"Failed to stop cluster: {error_message}")
                self.change_button_status("normal")

            # Start processing in a separate thread
            threading.Thread(target=process_services, daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop cluster: {str(e)}")
            self.change_button_status("normal")
            print(f"Error in stop_cluster: {str(e)}")

    def start_thread(self, target_function):
        """Start the specified function in a separate thread."""
        thread = threading.Thread(target=target_function)
        thread.daemon = True  # Ensure thread exits with the main program
        thread.start()

    def restart_cluster(self):

        self.restart = 1

        self.change_button_status("disabled")
        selected = self.tree.selection()

        if not selected:
            messagebox.showwarning("Warning", "Please select a cluster first")
            self.change_button_status("normal")
            return

        cluster_name = self.tree.item(selected[0])['values'][1]

        if not messagebox.askyesno("Confirm Action",
                                   f"Are you sure you want to restart the selected {cluster_name} cluster?",
                                   parent=self.parent):
            self.change_button_status("normal")
            return

        self.stop_cluster()
        self.start_cluster()

        self.restart = 0
        self.change_button_status("normal")

    def refresh_data(self):
        self.load_clusters()


if __name__ == "__main__":
    root = tk.Tk()
    app = ECSManagerApp(root)
    root.mainloop()
