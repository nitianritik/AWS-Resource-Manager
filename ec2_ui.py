import tkinter as tk
from tkinter import ttk, messagebox
import boto3
import threading


class EC2ManagerApp:
    def __init__(self, parent):
        self.parent = parent
        self.setup_ui()

    def setup_ui(self):
        # AWS Configuration Frame
        input_frame = ttk.LabelFrame(self.parent, text="AWS Configuration", padding="10")
        input_frame.pack(fill="x", padx=10, pady=5)

        # Profile input
        ttk.Label(input_frame, text="Profile Name:").pack(side="left")
        self.ec2_profile_var = tk.StringVar(value="datamesh")
        profile_entry = ttk.Entry(input_frame, textvariable=self.ec2_profile_var)
        profile_entry.pack(side="left", padx=5)
        
        # Region input
        ttk.Label(input_frame, text="Region(s):").pack(side="left")
        self.ec2_region_var = tk.StringVar(value="ap-southeast-2,us-east-1,us-west-2")
        region_entry = ttk.Entry(input_frame, textvariable=self.ec2_region_var, width=35)
        region_entry.pack(side="left", padx=5)
        
        # Load button
        self.load_instances_button = ttk.Button(input_frame, text="Load Instances",
                                                command=lambda: self.start_thread(self.load_ec2_instances))
        self.load_instances_button.pack(side="left", padx=5)
        self.load_instances_button.bind("<Return>",
                                        lambda event: self.start_thread(
                                            self.load_ec2_instances) if self.load_instances_button.instate(
                                            ["!disabled"]) else None)

        # Instances Frame
        instances_frame = ttk.LabelFrame(self.parent, text="EC2 Instances", padding="10")
        instances_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create Treeview
        self.ec2_tree = ttk.Treeview(instances_frame,
            columns=("SrNo", "Name", "Instance ID", "State", "Type", "Region"),
            show="headings")

        # Configure tag colors
        self.ec2_tree.tag_configure('running', background='#99f299')  # Light green
        self.ec2_tree.tag_configure('transitioning', background='#ffeb99')  # Light yellow

        # Define columns
        self.ec2_tree.heading("SrNo", text="Sr. No.")
        self.ec2_tree.heading("Name", text="Instance Name")
        self.ec2_tree.heading("Instance ID", text="Instance ID")
        self.ec2_tree.heading("State", text="State")
        self.ec2_tree.heading("Type", text="Instance Type")

        # Set column widths
        self.ec2_tree.column("SrNo", width=50, anchor="center")
        self.ec2_tree.heading("Region", text="Region")
        self.ec2_tree.column("State", anchor="center")
        self.ec2_tree.column("Region", width=100)
        self.ec2_tree.column("Name", width=200)
        self.ec2_tree.column("Instance ID", width=150)
        self.ec2_tree.column("State", width=100)
        self.ec2_tree.column("Type", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(instances_frame, orient="vertical", command=self.ec2_tree.yview)
        self.ec2_tree.configure(yscrollcommand=scrollbar.set)

        # Pack tree and scrollbar
        self.ec2_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Buttons Frame
        buttons_frame = ttk.Frame(self.parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)

        #############
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

        # Styled and interactive ttk Buttons
        self.start_instance_button = ttk.Button(buttons_frame, text="Start Instance", style="Custom.TButton",
                                                command=lambda: self.start_thread(self.start_ec2_instance))
        self.start_instance_button.pack(side="left", padx=5, pady=8)
        self.start_instance_button.bind("<Return>",
                                        lambda event: self.start_ec2_instance() if self.start_instance_button.instate(
                                            ["!disabled"]) else None)

        self.stop_instance_button = ttk.Button(buttons_frame, text="Stop Instance", style="Custom.TButton",
                                               command=lambda: self.start_thread(self.stop_ec2_instance))
        self.stop_instance_button.pack(side="left", padx=5, pady=8)
        self.stop_instance_button.bind("<Return>",
                                       lambda event: self.stop_ec2_instance() if self.stop_instance_button.instate(
                                           ["!disabled"]) else None)

        self.reboot_instance_button = ttk.Button(buttons_frame, text="Reboot Instance", style="Custom.TButton",
                                                 command=lambda: self.start_thread(self.reboot_ec2_instance))
        self.reboot_instance_button.pack(side="left", padx=5, pady=8)
        self.reboot_instance_button.bind("<Return>",
                                         lambda
                                             event: self.reboot_ec2_instance() if self.reboot_instance_button.instate(
                                             ["!disabled"]) else None)

        self.refresh_button = ttk.Button(buttons_frame, text="Refresh", style="Custom.TButton",
                                         command=lambda: self.start_thread(self.refresh_ec2_data))
        self.refresh_button.pack(side="left", padx=5, pady=8)
        self.refresh_button.bind("<Return>",
                                 lambda event: self.refresh_ec2_data() if self.refresh_button.instate(
                                     ["!disabled"]) else None)

        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.parent, textvariable=self.status_var,
                               relief="sunken", padding=(10, 2))
        status_bar.pack(fill="x", padx=10, pady=5)
        #############

    def start_thread(self, target_function):
        """Start the specified function in a separate thread."""
        thread = threading.Thread(target=target_function)
        thread.daemon = True  # Ensure thread exits with the main program
        thread.start()
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

    def load_ec2_instances(self):
        self.change_button_status("disabled")
        self.show_popup_status_message("Loading EC2 instances...")
        try:
            profile =self.ec2_profile_var.get()
            session = boto3.Session(profile_name=profile)
            regions = [r.strip() for r in self.ec2_region_var.get().split(',') if r.strip()]

            # Clear existing items
            for item in self.ec2_tree.get_children():
                self.ec2_tree.delete(item)

            sr_no = 1
            for region in regions:
                ec2_client = session.client('ec2', region_name=region)
                instances = ec2_client.describe_instances()

                for reservation in instances['Reservations']:
                    for instance in reservation['Instances']:
                        name = next((tag['Value'] for tag in instance.get('Tags', []) if tag['Key'] == 'Name'), 'N/A')
                        item_id = self.ec2_tree.insert('', 'end', values=(
                            sr_no,
                            name,
                            instance['InstanceId'],
                            instance['State']['Name'],
                            instance['InstanceType'],
                            region
                        ))
                        status = instance['State']['Name']
                        if status == 'running':
                            self.ec2_tree.item(item_id, tags=('running',))
                        elif status != 'stopped':
                            self.ec2_tree.item(item_id, tags=('transitioning',))
                        sr_no += 1
            self.show_popup_status_message("EC2 instances loaded successfully")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def start_ec2_instance(self):
        selected = self.ec2_tree.selection()
        if not selected:
            tk.messagebox.showwarning("Warning", "Please select an instance to start")
            return

        self.change_button_status("disabled")
        self.show_popup_status_message("Starting instance(s)...")
        try:
            region = self.ec2_tree.item(selected[0])['values'][5]
            session = boto3.Session(profile_name=self.ec2_profile_var.get(), region_name=region)
            ec2_client = session.client('ec2')

            for item in selected:
                instance_id = self.ec2_tree.item(item)['values'][2]
                ec2_client.start_instances(InstanceIds=[instance_id])

            self.refresh_ec2_data()
            self.show_popup_status_message("Successfully started selected instances")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def stop_ec2_instance(self):
        selected = self.ec2_tree.selection()
        if not selected:
            tk.messagebox.showwarning("Warning", "Please select an instance to stop")
            return

        self.change_button_status("disabled")
        self.show_popup_status_message("Stopping instance(s)...")
        try:
            region = self.ec2_tree.item(selected[0])['values'][5]
            session = boto3.Session(profile_name=self.ec2_profile_var.get(), region_name=region)
            ec2_client = session.client('ec2')

            for item in selected:
                instance_id = self.ec2_tree.item(item)['values'][2]
                ec2_client.stop_instances(InstanceIds=[instance_id])

            self.refresh_ec2_data()
            self.show_popup_status_message("Successfully stopped selected instances")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def reboot_ec2_instance(self):
        selected = self.ec2_tree.selection()
        if not selected:
            tk.messagebox.showwarning("Warning", "Please select an instance to reboot")
            return

        self.change_button_status("disabled")
        self.show_popup_status_message("Rebooting instance(s)...")
        try:
            region = self.ec2_tree.item(selected[0])['values'][5]
            session = boto3.Session(profile_name=self.ec2_profile_var.get(), region_name=region)
            ec2_client = session.client('ec2')

            for item in selected:
                instance_id = self.ec2_tree.item(item)['values'][2]
                ec2_client.reboot_instances(InstanceIds=[instance_id])

            self.refresh_ec2_data()
            self.show_popup_status_message("Successfully rebooted selected instances")
        except Exception as e:
            self.show_popup_status_message(f"Error: {str(e)}")
            tk.messagebox.showerror("Error", str(e))
        finally:
            self.change_button_status("normal")

    def refresh_ec2_data(self):
        self.show_popup_status_message("Refreshing EC2 data...")
        self.load_ec2_instances()