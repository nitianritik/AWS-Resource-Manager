import tkinter as tk
from tkinter import ttk
from ec2_ui import EC2ManagerApp
from rds_ui import RDSManagerApp
from ecs_ui import ECSManagerApp
from pipeline_ui import PipelineManagerApp
from codebuild_ui import CodeBuildManagerApp
from codecommit_ui import CodeCommitManagerApp  # Add this import
import boto3

class AWSManagerUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AWS Services Manager")
        self.root.geometry("1200x800")

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        # Create right-click menu for tabs
        self.tab_menu = tk.Menu(self.root, tearoff=0)
        self.tab_menu.add_command(label="Duplicate Tab", command=self.duplicate_tab)
        self.tab_menu.add_command(label="Close Tab", command=self.close_tab)

        # Bind right-click event to tabs
        self.notebook.bind("<Button-3>", self.show_tab_menu)

        # Bind drag-and-drop functionality
        self.notebook.bind("<Button-1>", self.start_drag)
        self.notebook.bind("<B1-Motion>", self.drag_tab)
        self.notebook.bind("<ButtonRelease-1>", self.end_drag)

        # Create tabs with differentiated background colors
        self.ecs_tab = ttk.Frame(self.notebook, style="ECS.TFrame")
        self.ec2_tab = ttk.Frame(self.notebook, style="EC2.TFrame")
        self.rds_tab = ttk.Frame(self.notebook, style="RDS.TFrame")
        self.pipeline_tab = ttk.Frame(self.notebook, style="Pipeline.TFrame")
        self.codebuild_tab = ttk.Frame(self.notebook, style="CodeBuild.TFrame")
        self.codecommit_tab = ttk.Frame(self.notebook, style="CodeCommit.TFrame")  # New CodeCommit tab

        # Add tabs to notebook with the desired symbols
        self.notebook.add(self.ecs_tab, text='♻ ECS Clusters')
        self.notebook.add(self.ec2_tab, text='★ EC2 Instances')
        self.notebook.add(self.rds_tab, text='❄ RDS Instances')
        self.notebook.add(self.pipeline_tab, text='⚙ CodePipelines')
        self.notebook.add(self.codebuild_tab, text='🔨 CodeBuild Projects')
        self.notebook.add(self.codecommit_tab, text='📚 CodeCommit Repos')  # New CodeCommit tab

        # Configure styles for tab backgrounds
        style = ttk.Style()
        style.configure("ECS.TFrame", background="#DFF6DD")  # Light green for ECS
        style.configure("EC2.TFrame", background="#FFF7CC")  # Light yellow for EC2
        style.configure("RDS.TFrame", background="#E3F2FD")  # Light blue for RDS
        style.configure("Pipeline.TFrame", background="#F5E9F7")  # Light purple for Pipeline
        style.configure("CodeBuild.TFrame", background="#FFE8D9")  # Light orange for CodeBuild
        style.configure("CodeCommit.TFrame", background="#E8F5E9")  # Light green for CodeCommit

        # Initialize managers
        self.initialize_ecs_tab()
        self.initialize_ec2_tab()
        self.initialize_rds_tab()
        self.initialize_pipeline_tab()
        self.initialize_codebuild_tab()
        self.initialize_codecommit_tab()  # New method for CodeCommit tab

        # Dragging-related variables
        self.dragging_index = None

    def initialize_ecs_tab(self):
        ECSManagerApp(self.ecs_tab)

    def initialize_ec2_tab(self):
        EC2ManagerApp(self.ec2_tab)

    def initialize_rds_tab(self):
        RDSManagerApp(self.rds_tab)

    def initialize_pipeline_tab(self):
        PipelineManagerApp(self.pipeline_tab)

    def initialize_codebuild_tab(self):
        CodeBuildManagerApp(self.codebuild_tab)

    def initialize_codecommit_tab(self):
        CodeCommitManagerApp(self.codecommit_tab)  # Initialize the CodeCommit tab

    def show_tab_menu(self, event):
        # Show the right-click menu at the cursor position
        try:
            clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if clicked_tab is not None:
                self.notebook.select(clicked_tab)
                self.tab_menu.post(event.x_root, event.y_root)
        except tk.TclError:
            pass

    def duplicate_tab(self):
        try:
            # Get the currently selected tab
            current_tab = self.notebook.select()
            if not current_tab:
                return  # No tab is selected

            # Get the text of the selected tab
            tab_text = self.notebook.tab(current_tab, "text")

            # Determine which type of tab to duplicate
            if "ECS" in tab_text:
                new_tab = ttk.Frame(self.notebook, style="ECS.TFrame")
                ECSManagerApp(new_tab)
                new_text = f"{tab_text} (Copy)"
            elif "EC2" in tab_text:
                new_tab = ttk.Frame(self.notebook, style="EC2.TFrame")
                EC2ManagerApp(new_tab)
                new_text = f"{tab_text} (Copy)"
            elif "RDS" in tab_text:
                new_tab = ttk.Frame(self.notebook, style="RDS.TFrame")
                RDSManagerApp(new_tab)
                new_text = f"{tab_text} (Copy)"
            elif "CodePipelines" in tab_text:
                new_tab = ttk.Frame(self.notebook, style="Pipeline.TFrame")
                PipelineManagerApp(new_tab)
                new_text = f"{tab_text} (Copy)"
            elif "CodeBuild" in tab_text:
                new_tab = ttk.Frame(self.notebook, style="CodeBuild.TFrame")
                CodeBuildManagerApp(new_tab)
                new_text = f"{tab_text} (Copy)"
            elif "CodeCommit" in tab_text:  # Add support for duplicating CodeCommit tab
                new_tab = ttk.Frame(self.notebook, style="CodeCommit.TFrame")
                CodeCommitManagerApp(new_tab)
                new_text = f"{tab_text} (Copy)"
            else:
                return  # Unknown tab type, skip duplication

            # Get the current index and total number of tabs
            current_index = self.notebook.index(current_tab)
            total_tabs = len(self.notebook.tabs())

            # Handle appending at the end explicitly
            if current_index + 1 == total_tabs:
                self.notebook.add(new_tab, text=new_text)  # Use add() to append at the end
            else:
                self.notebook.insert(current_index + 1, new_tab, text=new_text)  # Insert after current tab

            # Select the newly created tab
            self.notebook.select(new_tab)

        except Exception as e:
            print(f"Error duplicating tab: {e}")

    def close_tab(self):
        # Close the currently selected tab
        current_tab = self.notebook.select()
        if current_tab:
            self.notebook.forget(current_tab)

    def start_drag(self, event):
        # Get the index of the tab being dragged
        clicked_tab = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
        if clicked_tab:
            self.dragging_index = int(clicked_tab)

    def drag_tab(self, event):
        if self.dragging_index is not None:
            # Get the index of the tab under the cursor
            target_index = self.notebook.tk.call(self.notebook._w, "identify", "tab", event.x, event.y)
            if target_index:
                target_index = int(target_index)
                if target_index != self.dragging_index:
                    # Move the dragged tab to the new position
                    tab_content = self.notebook.tabs()[self.dragging_index]
                    self.notebook.insert(target_index, tab_content)
                    self.dragging_index = target_index

    def end_drag(self, event):
        # Reset dragging variables
        self.dragging_index = None


if __name__ == "__main__":
    root = tk.Tk()
    app = AWSManagerUI(root)
    root.mainloop()