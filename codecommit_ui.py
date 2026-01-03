import tkinter as tk
from tkinter import ttk, messagebox
import boto3
import threading
import pyperclip
from concurrent.futures import ThreadPoolExecutor, as_completed


class CodeCommitManagerApp:
    def __init__(self, parent):
        self.parent = parent
        self.all_repositories = []  # Variable to store all repository data
        self.total_repositories = 0  # Variable to store total repository count
        self.setup_ui()
        self.cached_sessions = {}  # Cache for boto3 sessions
        self.repository_cache = {}  # Cache for repository details

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
        self.profile_var = tk.StringVar(value="admin")
        profile_entry = ttk.Entry(config_frame, textvariable=self.profile_var)
        profile_entry.pack(side="left", padx=5)

        # Region input with default 'ap-southeast-2' value
        ttk.Label(config_frame, text="Region(s):").pack(side="left")
        self.region_var = tk.StringVar(value="ap-southeast-2")
        region_entry = ttk.Entry(config_frame, textvariable=self.region_var, width=30)
        region_entry.pack(side="left", padx=5)

        # Load button with Return key binding
        self.load_button = ttk.Button(
            config_frame,
            text="Load Repositories",
            command=lambda: self.start_thread(self.load_repositories)
        )
        self.load_button.pack(side="left", padx=5)

        # Bind Return/Enter key to load_button
        self.parent.bind("<Return>",
                         lambda event: self.start_thread(self.load_repositories) if self.load_button.instate(
                             ["!disabled"]) else None)

        # Repositories Frame
        repositories_frame = ttk.LabelFrame(self.parent, text="CodeCommit Repositories", padding="10")
        repositories_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Search Frame
        search_frame = ttk.Frame(repositories_frame)
        search_frame.pack(fill="x", pady=5)

        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.repository_search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.repository_search_var)
        self.search_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.search_entry.bind("<KeyRelease>", self.filter_repositories)

        # Create Treeview for repositories with requested columns (removed Clone URL)
        self.repository_tree = ttk.Treeview(repositories_frame,
                                            columns=(
                                                "SrNo", "Name", "Description", "Last Modified",
                                                "Created", "Region"),
                                            show="headings")

        # Configure columns with centered alignment for specific columns
        columns = [
            ("SrNo", "Sr. No.", 50, "center"),
            ("Name", "Name", 250, "w"),
            ("Description", "Description", 200, "w"),
            ("Last Modified", "Last Modified", 150, "center"),
            ("Created", "Created", 150, "center"),
            ("Region", "Region", 100, "center")
        ]

        for col_id, heading, width, anchor in columns:
            self.repository_tree.heading(col_id, text=heading)
            self.repository_tree.column(col_id, width=width, anchor=anchor)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(repositories_frame, orient="vertical", command=self.repository_tree.yview)
        self.repository_tree.configure(yscrollcommand=scrollbar.set)
        self.repository_tree.pack(side="left", fill="both", expand=True)
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
                        background="#f0f0f0",
                        foreground="black",
                        font=("Arial", 10),
                        padding=(10, 5))

        style.map("Custom.TButton",
                  background=[("active", "#d9d9d9"),
                              ("disabled", "#e0e0e0")],
                  foreground=[("active", "black"),
                              ("disabled", "#a0a0a0")],
                  relief=[("pressed", "sunken")])

        # Buttons Frame
        buttons_frame = ttk.Frame(self.parent)
        buttons_frame.pack(fill="x", padx=10, pady=5)

        # Action buttons with custom style
        self.refresh_button = ttk.Button(
            buttons_frame,
            text="Refresh",
            style="Custom.TButton",
            command=lambda: self.start_thread(self.load_repositories)
        )
        self.refresh_button.pack(side="left", padx=5, pady=8)
        self.refresh_button.bind("<Return>",
                                 lambda event: self.load_repositories() if self.refresh_button.instate(
                                     ["!disabled"]) else None)

        # Copy Repository Link button with custom style
        self.copy_link_button = ttk.Button(
            buttons_frame,
            text="Copy Repository Link",
            style="Custom.TButton",
            command=self.copy_repository_link
        )
        self.copy_link_button.pack(side="left", padx=5, pady=8)
        self.copy_link_button.bind("<Return>",
                                   lambda event: self.copy_repository_link() if self.copy_link_button.instate(
                                       ["!disabled"]) else None)

        # New Copy HTTP Clone URL button
        self.copy_http_button = ttk.Button(
            buttons_frame,
            text="Copy HTTP Clone URL",
            style="Custom.TButton",
            command=self.copy_http_clone_url
        )
        self.copy_http_button.pack(side="left", padx=5, pady=8)
        self.copy_http_button.bind("<Return>",
                                   lambda event: self.copy_http_clone_url() if self.copy_http_button.instate(
                                       ["!disabled"]) else None)

        # New Copy SSH Clone URL button
        self.copy_ssh_button = ttk.Button(
            buttons_frame,
            text="Copy SSH Clone URL",
            style="Custom.TButton",
            command=self.copy_ssh_clone_url
        )
        self.copy_ssh_button.pack(side="left", padx=5, pady=8)
        self.copy_ssh_button.bind("<Return>",
                                  lambda event: self.copy_ssh_clone_url() if self.copy_ssh_button.instate(
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

    def copy_repository_link(self):
        """Copy AWS console link for the selected repository to clipboard"""
        selected = self.repository_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a repository first")
            return

        repository_name = self.repository_tree.item(selected[0])['values'][1]
        region = self.repository_tree.item(selected[0])['values'][5]  # Region is now at index 5

        # Construct the AWS console URL
        aws_url = f"https://{region}.console.aws.amazon.com/codesuite/codecommit/repositories/{repository_name}/browse?region={region}"

        try:
            pyperclip.copy(aws_url)
            self.show_status_message(f"Copied repository link to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to copy link: {str(e)}")

    def copy_http_clone_url(self):
        """Copy HTTP clone URL for the selected repository to clipboard"""
        selected = self.repository_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a repository first")
            return

        # Find the repository in our stored data to get the clone URLs
        repository_name = self.repository_tree.item(selected[0])['values'][1]
        region = self.repository_tree.item(selected[0])['values'][5]

        # Find the repository in our data
        repo = next((r for r in self.all_repositories if r['name'] == repository_name and r['region'] == region), None)

        if repo:
            # Extract HTTP URL from the stored clone_url (format: "HTTP: url\nSSH: url")
            http_url = repo['clone_url'].split('\n')[0].replace('HTTP: ', '')
            try:
                pyperclip.copy(http_url)
                self.show_status_message(f"Copied HTTP clone URL to clipboard")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy HTTP URL: {str(e)}")
        else:
            messagebox.showwarning("Warning", "Repository data not found")

    def copy_ssh_clone_url(self):
        """Copy SSH clone URL for the selected repository to clipboard"""
        selected = self.repository_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a repository first")
            return

        # Find the repository in our stored data to get the clone URLs
        repository_name = self.repository_tree.item(selected[0])['values'][1]
        region = self.repository_tree.item(selected[0])['values'][5]

        # Find the repository in our data
        repo = next((r for r in self.all_repositories if r['name'] == repository_name and r['region'] == region), None)

        if repo:
            # Extract SSH URL from the stored clone_url (format: "HTTP: url\nSSH: url")
            ssh_url = repo['clone_url'].split('\n')[1].replace('SSH: ', '')
            try:
                pyperclip.copy(ssh_url)
                self.show_status_message(f"Copied SSH clone URL to clipboard")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to copy SSH URL: {str(e)}")
        else:
            messagebox.showwarning("Warning", "Repository data not found")

    def change_button_state(self, state):
        """Enable/disable buttons and search entry during operations"""
        widgets = [
            self.load_button,
            self.refresh_button,
            self.copy_link_button,
            self.copy_http_button,
            self.copy_ssh_button,
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
        self.progress_label.config(text=f"Loaded {current} of {total} repositories")
        self.parent.update()

    def filter_repositories(self, event=None):
        """Filter repositories from stored data based on search term"""
        search_term = self.repository_search_var.get().lower()

        # Clear current treeview
        self.repository_tree.delete(*self.repository_tree.get_children())

        # If search is empty, show all repositories
        if not search_term.strip():
            for repo in self.all_repositories:
                self.repository_tree.insert('', 'end', values=(
                    repo['sr_no'],
                    repo['name'],
                    repo['description'],
                    repo['last_modified'],
                    repo['created'],
                    repo['region']
                ))
            return

        # Filter from stored data and add matching repositories to treeview
        for repo in self.all_repositories:
            if search_term in repo['name'].lower():
                self.repository_tree.insert('', 'end', values=(
                    repo['sr_no'],
                    repo['name'],
                    repo['description'],
                    repo['last_modified'],
                    repo['created'],
                    repo['region']
                ))

    def get_total_repositories_count(self, profile, regions):
        """Get total count of repositories across all regions using parallel requests"""
        total = 0
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for region in regions:
                futures.append(executor.submit(self._count_repositories_in_region, profile, region))

            for future in as_completed(futures):
                try:
                    total += future.result()
                except Exception as e:
                    print(f"Error counting repositories: {str(e)}")
        return total

    def _count_repositories_in_region(self, profile, region):
        """Count repositories in a single region"""
        try:
            session = self.get_boto3_session(profile, region)
            client = session.client('codecommit')
            response = client.list_repositories()
            return len(response.get('repositories', []))
        except Exception as e:
            print(f"Error counting repositories in {region}: {str(e)}")
            return 0

    def get_repositories_in_region(self, profile, region):
        """Get all repositories in a specific region with optimized API calls"""
        cache_key = f"{profile}:{region}:repositories"
        if cache_key in self.repository_cache:
            return region, self.repository_cache[cache_key]

        try:
            session = self.get_boto3_session(profile, region)
            client = session.client('codecommit')

            # Get all repository names first
            repositories = []
            next_token = None

            while True:
                params = {}
                if next_token:
                    params['nextToken'] = next_token

                response = client.list_repositories(**params)
                repositories.extend(response.get('repositories', []))

                next_token = response.get('nextToken')
                if not next_token:
                    break

            if not repositories:
                return region, []

            # Get details for each repository
            repo_details = []
            for repo in repositories:
                try:
                    detail_response = client.get_repository(repositoryName=repo['repositoryName'])
                    repo_info = detail_response['repositoryMetadata']

                    # Format dates for display
                    created = repo_info.get('creationDate', '')
                    last_modified = repo_info.get('lastModifiedDate', '')

                    if created:
                        created = created.strftime('%Y-%m-%d %H:%M:%S')
                    if last_modified:
                        last_modified = last_modified.strftime('%Y-%m-%d %H:%M:%S')

                    # Get clone URLs (still stored but not displayed)
                    clone_url_http = repo_info.get('cloneUrlHttp', '')
                    clone_url_ssh = repo_info.get('cloneUrlSsh', '')
                    clone_url = f"HTTP: {clone_url_http}\nSSH: {clone_url_ssh}"

                    repo_details.append({
                        'name': repo_info['repositoryName'],
                        'description': repo_info.get('repositoryDescription', ''),
                        'last_modified': last_modified,
                        'created': created,
                        'clone_url': clone_url,
                        'region': region
                    })
                except Exception as e:
                    print(f"Error getting details for {repo['repositoryName']}: {str(e)}")
                    continue

            # Cache the results
            self.repository_cache[cache_key] = repo_details
            return region, repo_details

        except Exception as e:
            print(f"Error in {region}: {str(e)}")
            return region, []

    def load_repositories(self):
        """Load repositories with optimized parallel processing and UI updates"""
        self.change_button_state("disabled")
        self.repository_search_var.set("")  # Clear search filter
        self.show_status_message("Loading repositories...")

        # Show progress bar
        self.progress_frame.pack(fill="x", padx=10, pady=5)
        self.progress["value"] = 0
        self.progress_label.config(text="Counting repositories...")
        self.parent.update()

        try:
            profile = self.profile_var.get()
            regions = [r.strip() for r in self.region_var.get().split(',') if r.strip()]

            if not profile or not regions:
                messagebox.showwarning("Warning", "Please provide both profile and region(s)")
                return

            # Get total repository count first
            self.total_repositories = self.get_total_repositories_count(profile, regions)
            if self.total_repositories == 0:
                self.progress_label.config(text="No repositories found")
                self.parent.update()
                return

            # Clear existing items more efficiently
            self.repository_tree.delete(*self.repository_tree.get_children())

            # Reset the stored repository data
            self.all_repositories = []
            loaded_count = 0

            # Use ThreadPoolExecutor to fetch repositories from all regions in parallel
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self.get_repositories_in_region, profile, region): region for region in
                           regions}

                for future in as_completed(futures):
                    region, repositories = future.result()
                    region_start_count = loaded_count

                    for repo in repositories:
                        # Store the complete repository data
                        self.all_repositories.append({
                            'sr_no': loaded_count + 1,
                            'name': repo['name'],
                            'description': repo['description'],
                            'last_modified': repo['last_modified'],
                            'created': repo['created'],
                            'clone_url': repo['clone_url'],
                            'region': repo['region']
                        })
                        loaded_count += 1

                    # Batch insert repositories for this region to reduce UI updates
                    if repositories:
                        self.parent.after(0, self._add_repositories_to_tree,
                                          self.all_repositories[region_start_count:loaded_count])
                        self.parent.after(0, self.update_progress, loaded_count, self.total_repositories)

            self.show_status_message(f"Loaded {loaded_count} repositories across {len(regions)} region(s)")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load repositories: {str(e)}")
            self.show_status_message("Error loading repositories")
        finally:
            self.change_button_state("normal")
            self.progress_frame.pack_forget()  # Hide progress bar when done

    def _add_repositories_to_tree(self, repositories):
        """Add a batch of repositories to the treeview"""
        for repo in repositories:
            self.repository_tree.insert('', 'end', values=(
                repo['sr_no'],
                repo['name'],
                repo['description'],
                repo['last_modified'],
                repo['created'],
                repo['region']
            ))


if __name__ == "__main__":
    root = tk.Tk()
    root.title("AWS CodeCommit Repository Manager")
    app = CodeCommitManagerApp(root)
    root.mainloop()