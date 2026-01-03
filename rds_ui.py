import tkinter as tk
from tkinter import ttk, messagebox
import boto3
import threading


class RDSManagerApp:
    def __init__(self, parent):
        self.parent = parent
        self.setup_ui()

    def start_thread(self, target_function):
        """Start the specified function in a separate thread."""
        thread = threading.Thread(target=target_function)
        thread.daemon = True  # Ensure thread exits with the main program
        thread.start()

    def setup_ui(self):
        # AWS Configuration Frame
        input_frame = ttk.LabelFrame(self.parent, text="AWS Configuration", padding="10")
        input_frame.pack(fill="x", padx=10, pady=5)

        # Profile input
        ttk.Label(input_frame, text="Profile Name:").pack(side="left")
        self.rds_profile_var = tk.StringVar(value="datamesh")
        profile_entry = ttk.Entry(input_frame, textvariable=self.rds_profile_var)
        profile_entry.pack(side="left", padx=5)
        
        # Region input
        ttk.Label(input_frame, text="Region(s):").pack(side="left")
        self.rds_region_var = tk.StringVar(value="ap-southeast-2,us-east-1,us-west-2")
        region_entry = ttk.Entry(input_frame, textvariable=self.rds_region_var, width=35)
        region_entry.pack(side="left", padx=5)
        
        # Load button
        self.load_instances_button = ttk.Button(input_frame, text="Load Instances",
                                                command=lambda: self.start_thread(self.load_rds_instances))
        self.load_instances_button.pack(side="left", padx=5)
        self.load_instances_button.bind("<Return>",
                                        lambda event: self.start_thread(
                                            self.load_rds_instances) if self.load_instances_button.instate(
                                            ["!disabled"]) else None)

        # Instances Frame
        instances_frame = ttk.LabelFrame(self.parent, text="RDS Instances", padding="10")
        instances_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create Treeview
        self.rds_tree = ttk.Treeview(instances_frame,
            columns=("SrNo", "Instance ID", "Status", "Size", "Engine", "Region"),
            show="headings")
        
        # Configure tag colors
        self.rds_tree.tag_configure('available', background='#99f299')  # Light green
        self.rds_tree.tag_configure('transitioning', background='#ffeb99')  # Light yellow

        # Define columns
        self.rds_tree.heading("SrNo", text="Sr. No.")
        self.rds_tree.column("SrNo", anchor="center")
        self.rds_tree.column("Status", anchor="center")
        self.rds_tree.heading("Region", text="Region")
        self.rds_tree.column("Region", width=100)
        self.rds_tree.heading("Instance ID", text="Instance ID")
        self.rds_tree.heading("Status", text="Status")
        self.rds_tree.heading("Size", text="Size")
        self.rds_tree.heading("Engine", text="Engine")

        # Set column widths
        self.rds_tree.column("SrNo", width=50)
        self.rds_tree.column("Instance ID", width=200)
        self.rds_tree.column("Status", width=100)
        self.rds_tree.column("Size", width=100)
        self.rds_tree.column("Engine", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(instances_frame, orient="vertical", command=self.rds_tree.yview)
        self.rds_tree.configure(yscrollcommand=scrollbar.set)

        # Pack tree and scrollbar
        self.rds_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons Frame
        buttons_frame = ttk.Frame(self.parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)

        # Action buttons
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
        self.start_instance_button = ttk.Button(buttons_frame, text="Start Instance", style="Custom.TButton",
                                                command=lambda: self.start_thread(self.start_rds_instance))
        self.start_instance_button.pack(side="left", padx=5, pady=8)
        self.start_instance_button.bind("<Return>",
                                        lambda event: self.start_rds_instance() if self.start_instance_button.instate(
                                            ["!disabled"]) else None)

        self.stop_instance_button = ttk.Button(buttons_frame, text="Stop Instance", style="Custom.TButton",
                                               command=lambda: self.start_thread(self.stop_rds_instance))
        self.stop_instance_button.pack(side="left", padx=5, pady=8)
        self.stop_instance_button.bind("<Return>",
                                       lambda event: self.stop_rds_instance() if self.stop_instance_button.instate(
                                           ["!disabled"]) else None)

        self.reboot_instance_button = ttk.Button(buttons_frame, text="Reboot Instance", style="Custom.TButton",
                                                 command=lambda: self.start_thread(self.reboot_rds_instance))
        self.reboot_instance_button.pack(side="left", padx=5, pady=8)
        self.reboot_instance_button.bind("<Return>",
                                         lambda
                                             event: self.reboot_rds_instance() if self.reboot_instance_button.instate(
                                             ["!disabled"]) else None)

        self.refresh_button = ttk.Button(buttons_frame, text="Refresh", style="Custom.TButton",
                                         command=lambda: self.start_thread(self.refresh_rds_data))
        self.refresh_button.pack(side="left", padx=5, pady=8)
        self.refresh_button.bind("<Return>",
                                 lambda event: self.refresh_rds_data() if self.refresh_button.instate(
                                     ["!disabled"]) else None)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.parent, textvariable=self.status_var,
                               relief="sunken", padding=(10, 2))
        status_bar.pack(fill="x", padx=10, pady=5)

    def show_popup_status_message(self, message, auto_close_timing=2000):
        """Show a temporary status message"""
        status_window = tk.Toplevel(self.parent)
        status_window.overrideredirect(True)
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - 150
        y = self.parent.winfo_y() + self.parent.winfo_height() - 100
        status_window.geometry(f'+{x}+{y}')
        
        # Create frame with border
        frame = ttk.Frame(status_window, padding=2, relief='solid')
        frame.pack(fill='both', expand=True)
        
        # Create styled label
        label = ttk.Label(
            frame,
            text=message,
            font=('Helvetica', 10),
            foreground='green' if 'success' in message.lower() else 'red' if 'error' in message.lower() else 'black',
            background='white',
            padding=(20, 10))
        label.pack()
        
        status_window.after(auto_close_timing, status_window.destroy)

    def change_button_status(self, state):
        """Enable/disable buttons during operations"""
        buttons = [
            self.load_instances_button,
            self.start_instance_button,
            self.stop_instance_button,
            self.reboot_instance_button,
            self.refresh_button
        ]
        for button in buttons:
            button["state"] = state

    def load_rds_instances(self):
        self.change_button_status("disabled")
        self.show_popup_status_message("Loading RDS instances...")
        try:
            session = boto3.Session(profile_name=self.rds_profile_var.get())
            regions = [r.strip() for r in self.rds_region_var.get().split(',') if r.strip()]

            # Clear existing items
            for item in self.rds_tree.get_children():
                self.rds_tree.delete(item)

            sr_no = 1
            for region in regions:
                rds_client = session.client('rds', region_name=region)
                instances = rds_client.describe_db_instances()

                for instance in instances['DBInstances']:
                    item_id = self.rds_tree.insert('', 'end', values=(
                        sr_no,
                        instance['DBInstanceIdentifier'],
                        instance['DBInstanceStatus'],
                        instance['DBInstanceClass'],
                        instance['Engine'],
                        region
                    ))
                    status = instance['DBInstanceStatus']
                    if status == 'available':
                        self.rds_tree.item(item_id, tags=('available',))
                    elif status != 'stopped':
                        self.rds_tree.item(item_id, tags=('transitioning',))
                    sr_no += 1
            self.show_popup_status_message("RDS instances loaded successfully")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def start_rds_instance(self):
        selected = self.rds_tree.selection()
        if not selected:
            tk.messagebox.showwarning("Warning", "Please select an instance to start")
            return

        self.change_button_status("disabled")
        self.show_popup_status_message("Starting instance(s)...")
        try:
            region = self.rds_tree.item(selected[0])['values'][5]
            session = boto3.Session(profile_name=self.rds_profile_var.get(), region_name=region)
            rds_client = session.client('rds')

            for item in selected:
                instance_id = self.rds_tree.item(item)['values'][1]
                rds_client.start_db_instance(DBInstanceIdentifier=instance_id)

            self.refresh_rds_data()
            self.show_popup_status_message("Successfully started selected instances")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def stop_rds_instance(self):
        selected = self.rds_tree.selection()
        if not selected:
            tk.messagebox.showwarning("Warning", "Please select an instance to stop")
            return

        self.change_button_status("disabled")
        self.show_popup_status_message("Stopping instance(s)...")
        try:
            region = self.rds_tree.item(selected[0])['values'][5]
            session = boto3.Session(profile_name=self.rds_profile_var.get(), region_name=region)
            rds_client = session.client('rds')

            for item in selected:
                instance_id = self.rds_tree.item(item)['values'][1]
                rds_client.stop_db_instance(DBInstanceIdentifier=instance_id)

            self.refresh_rds_data()
            self.show_popup_status_message("Successfully stopped selected instances")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def reboot_rds_instance(self):
        selected = self.rds_tree.selection()
        if not selected:
            tk.messagebox.showwarning("Warning", "Please select an instance to reboot")
            return

        self.change_button_status("disabled")
        self.show_popup_status_message("Rebooting instance(s)...")
        try:
            region = self.rds_tree.item(selected[0])['values'][5]
            session = boto3.Session(profile_name=self.rds_profile_var.get(), region_name=region)
            rds_client = session.client('rds')

            for item in selected:
                instance_id = self.rds_tree.item(item)['values'][1]
                rds_client.reboot_db_instance(DBInstanceIdentifier=instance_id)

            self.refresh_rds_data()
            self.show_popup_status_message("Successfully rebooted selected instances")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def refresh_rds_data(self):
        self.show_popup_status_message("Refreshing RDS data...")
        self.load_rds_instances()