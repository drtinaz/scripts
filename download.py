import os
import subprocess
import requests
import re
import shutil
import zipfile

# --- Configuration ---
DRIVER_PATH = "/data/apps"
GITHUB_USER = "drtinaz"
TEMP_DIR = "/tmp"

# Define drivers and their config behavior
# 'config_type':
#   'full_config': Config.ini is backed up/restored during update. 
#   'none': No config file handling needed.
DRIVER_CONFIGS = {
    1: {"name": "auto_current", "config_type": "full_config"}, 
    2: {"name": "auto_switch", "config_type": "none"},
    3: {"name": "gps_socat", "config_type": "full_config"},    
    4: {"name": "external_devices", "config_type": "full_config"}, 
    5: {"name": "transfer_switch", "config_type": "none"},
}

# --- Helper Functions (No Functional Changes unless noted) ---

def get_latest_versions(driver_name):
    """Fetches the latest stable and beta version tags from GitHub."""
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        releases = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching version numbers for {driver_name}: {e}")
        return None, None

    # Latest Stable (using 'latest' release endpoint logic)
    stable_tag = None
    try:
        latest_release_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases/latest"
        latest_release = requests.get(latest_release_url).json()
        stable_tag = latest_release.get("tag_name")
    except Exception:
        pass

    # Latest Beta/RC
    beta_tag = None
    for release in releases:
        tag = release.get("tag_name", "")
        if re.search(r'(rc|beta)', tag, re.IGNORECASE):
            beta_tag = tag
            break
            
    return stable_tag, beta_tag

def select_driver():
    """Presents a menu and returns the selected driver name and config type."""
    print("\n--- Driver Selection Menu ---")
    while True:
        for num, driver_info in DRIVER_CONFIGS.items():
            print(f"{num}) {driver_info['name']}")
        print("6) Exit Script")
        
        choice = input("\nSelect a driver to install (1-5) or 6 to exit: ")
        
        if choice == '6':
            print("Exiting script.")
            return None, None
            
        try:
            choice_num = int(choice)
            if choice_num in DRIVER_CONFIGS:
                return DRIVER_CONFIGS[choice_num]['name'], DRIVER_CONFIGS[choice_num]['config_type']
            else:
                print(f"Invalid option: {choice}. Please enter a number between 1 and 6.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def select_version(driver_name, stable_tag, beta_tag):
    """Presents a version menu and returns the selected tag and download URL."""
    print("\n--- Version Selection ---")
    
    version_options = []
    if stable_tag:
        version_options.append((f"Latest Stable Release: {stable_tag}", stable_tag))
    if beta_tag:
        version_options.append((f"Latest Beta/RC Build: {beta_tag}", beta_tag))

    if not version_options:
        print("Could not fetch any stable or beta version tags. Returning to main menu.")
        return None, None

    version_options.append(("Quit/Cancel Installation", None))

    while True:
        for i, (label, tag) in enumerate(version_options, 1):
            print(f"{i}) {label}")
        
        choice = input("\nSelect which version you want to install: ")
        
        try:
            choice_num = int(choice) - 1
            if 0 <= choice_num < len(version_options) - 1:
                selected_tag = version_options[choice_num][1]
                
                # Determine download URL
                if selected_tag == stable_tag:
                    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases/latest"
                    response = requests.get(api_url).json()
                    download_url = response.get("zipball_url")
                else: # Beta/RC
                    download_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/zipball/{selected_tag}"
                    
                if not download_url:
                    print(f"Error: Could not determine download URL for tag {selected_tag}. Returning to main menu.")
                    return None, None
                    
                print(f"> Selected version: {selected_tag}")
                return selected_tag, download_url
                
            elif version_options[choice_num][0] == "Quit/Cancel Installation":
                print("Installation cancelled. Returning to main menu.")
                return None, None
            else:
                print("Invalid option. Please enter a valid number.")
        except (ValueError, IndexError):
            print("Invalid input. Please enter a number.")
            
def handle_config_backup(driver_dir, driver_name):
    """Backs up an existing config.ini."""
    config_file = os.path.join(driver_dir, "config.ini")
    backup_file = os.path.join(DRIVER_PATH, f"{driver_name}_config.ini")
    if os.path.isfile(config_file):
        print(f"Backing up existing config file for **{driver_name}**...")
        shutil.move(config_file, backup_file)
        return True
    return False

def handle_config_restore(driver_dir, driver_name):
    """Restores a backed-up config.ini."""
    backup_file = os.path.join(DRIVER_PATH, f"{driver_name}_config.ini")
    config_file = os.path.join(driver_dir, "config.ini")
    if os.path.isfile(backup_file):
        print(f"Restoring existing config file for **{driver_name}**...")
        shutil.move(backup_file, config_file)
        return True
    return False

# --- MODIFIED: Simplified to only handle file creation/config.py execution ---
def handle_first_run_config(driver_dir, driver_name):
    """Handles first-run config file creation or config.py execution."""
    config_file = os.path.join(driver_dir, "config.ini")
    
    if os.path.isfile(config_file):
        return
        
    if driver_name in ["auto_current", "gps_socat"]:
        # Create config.ini from config.sample.ini
        sample_file = os.path.join(driver_dir, "config.sample.ini")
        if os.path.isfile(sample_file):
            print(f"Creating default config.ini from config.sample.ini for **{driver_name}**...")
            shutil.copy2(sample_file, config_file)
        else:
             print(f"Warning: No config.ini or config.sample.ini found for {driver_name}.")

    elif driver_name == "external_devices":
        config_script_path = os.path.join(driver_dir, "config.py")
        
        print("\n" * 2)
        print("=====================================================================")
        print("⚠️ FIRST INSTALLATION DETECTED FOR external_devices ⚠️")
        print("The driver requires initial configuration.")
        print("1) Run **config.py** now to configure devices (Recommended)")
        print("2) Run **config.py** manually later (Exit to main menu)")
        print("=====================================================================")
        
        while True:
            choice = input("\nSelect an option (1 or 2): ")
            if choice == '1':
                print(f"\nLaunching configuration script: python {config_script_path}...")
                try:
                    # Execute config.py and wait for it to finish
                    subprocess.run(["python", config_script_path], check=True, cwd=driver_dir)
                    print("\nConfiguration completed. Returning to installer.")
                except subprocess.CalledProcessError as e:
                    print(f"\nConfiguration script failed with error: {e}")
                    print("You may need to run it manually to complete setup.")
                except FileNotFoundError:
                    print(f"\nError: python interpreter or {config_script_path} not found.")
                
                if not os.path.isfile(config_file):
                    print("\nWarning: config.ini was not created. You must run config.py manually.")
                    
                break
            elif choice == '2':
                print("\nConfiguration deferred. You must run config.py manually before starting the service.")
                print("\nCommand to run later:")
                print(f"  **python {config_script_path}**")
                break
            else:
                print("Invalid option. Please enter 1 or 2.")


def set_permissions(driver_dir, driver_name):
    """Sets executable permissions for relevant files."""
    print("Setting permissions for files...")
    
    # List of files to make executable (relative paths)
    executables = [
        f"{driver_name}.py",
        "install.sh",
        "restart.sh",
        "uninstall.sh",
        "config.py",
        "service/run",
        "service/log/run",
    ]

    for file_name in executables:
        file_path = os.path.join(driver_dir, file_name)
        if os.path.exists(file_path):
            os.chmod(file_path, 0o755)

# --- NEW: Function to handle final prompts and actions ---
def handle_post_install_actions(driver_dir, driver_name, is_update):
    """Handles the final prompts (editing config/running install/restart) based on driver state."""
    print("\n" * 2)
    print(f"--- Final Setup for {driver_name} ---")
    
    install_script = os.path.join(driver_dir, "install.sh")
    restart_script = os.path.join(driver_dir, "restart.sh")

    if driver_name in ["auto_current", "gps_socat"]:
        if not is_update:
            # First Install: Prompt to edit config.ini and run install.sh
            action_type = "alter the settings for their generator" if driver_name == "auto_current" else "verify settings"
            
            print("=====================================================================")
            print(f"✅ Installation Complete. Now for the setup steps:")
            print(f"1. **Edit config.ini**: You must {action_type} in:")
            print(f"   {driver_dir}/config.ini")
            print(f"2. **Run install.sh**: Execute the following command to complete setup:")
            print(f"   /bin/bash {install_script}")
            print("=====================================================================")
        else:
            # Update: Run restart.sh
            if os.path.exists(restart_script):
                print(f"Update detected. Restarting driver by running:")
                subprocess.run(["/bin/bash", restart_script])
            else:
                print(f"Update detected, but {restart_script} not found. Driver may require manual restart.")

    elif driver_name == "external_devices":
        # External devices first-install instructions were given by handle_first_run_config.
        if is_update:
            # Update: Run restart.sh
            if os.path.exists(restart_script):
                print(f"Update detected. Restarting driver by running:")
                subprocess.run(["/bin/bash", restart_script])
            else:
                print(f"Update detected, but {restart_script} not found. Driver may require manual restart.")
        else:
            # First Install: Acknowledgment that config steps were handled/deferred.
            print("✅ Installation complete. The configuration steps for this driver have been handled or deferred.")
            print("Remember to run config.py and install.sh if you deferred configuration.")


    elif driver_name in ["auto_switch", "transfer_switch"]:
        # Logic for no-config drivers (auto_switch, transfer_switch)
        if not is_update:
            # First Install: Prompt to run install.sh
            print("=====================================================================")
            print(f"✅ First Installation Complete. Run the install script to activate:")
            print(f"   /bin/bash {install_script}")
            print("=====================================================================")
        else:
            # Update: Run restart.sh
            if os.path.exists(restart_script):
                print(f"Update detected. Restarting driver by running:")
                subprocess.run(["/bin/bash", restart_script])
            else:
                print(f"Update detected, but {restart_script} not found. Driver may require manual restart.")
    
    print("\n" * 2)
    print(f"✅ Installation/Update of **{driver_name}** Complete. Returning to main menu.")
    print("\n" * 2)

# --- Installation Function (Logic Reordered for the last time) ---

def run_installation(driver_name, config_type):
    """Handles the full installation/update process for a single driver."""
    driver_dir = os.path.join(DRIVER_PATH, driver_name)
    
    # 1. Fetch Versions and Select Version
    stable_tag, beta_tag = get_latest_versions(driver_name)
    if not stable_tag and not beta_tag:
        print("Could not retrieve version information. Returning to main menu.")
        return

    selected_tag, download_url = select_version(driver_name, stable_tag, beta_tag)
    if not selected_tag: # User cancelled selection
        return

    # 2. Pre-transfer Setup
    print(f"\n--- Installation Process for {driver_name} ({selected_tag}) ---")
    
    is_update = os.path.isdir(driver_dir)
    status_msg = "Updating" if is_update else "Installing"
    print(f"{status_msg} driver '{driver_name}'...")
    
    zip_path = os.path.join(TEMP_DIR, f"{driver_name}.zip")
    extract_dir = os.path.join(TEMP_DIR, f"extracted_{driver_name}")
    source_folder = None
    
    try:
        # Download and Unzip Logic (omitted for brevity, assume success)
        print(f"Downloading from: {download_url}")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
    except requests.exceptions.RequestException as e:
        print(f"Download failed. Error: {e}")
        return

    try:
        print("Unzipping driver...")
        if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            extracted_contents = os.listdir(extract_dir)
            extracted_folder_name = [d for d in extracted_contents if os.path.isdir(os.path.join(extract_dir, d))][0]
            source_folder = os.path.join(extract_dir, extracted_folder_name)
    except Exception as e:
        print(f"Unzip failed. Error: {e}")
        return

    # 3. Config Backup (BEFORE cleaning up the old folder)
    config_backed_up = False
    if config_type == 'full_config' and is_update:
        config_backed_up = handle_config_backup(driver_dir, driver_name)

    # 4. Cleanup Old Driver and Copy New Files
    print("Cleaning up existing driver installation...")
    if os.path.isdir(driver_dir):
        try:
            shutil.rmtree(driver_dir)
        except OSError as e:
            print(f"Error cleaning up old driver files: {e}. Aborting installation.")
            return
            
    print("Copying new driver files...")
    if source_folder:
        shutil.move(source_folder, driver_dir)
    else:
        print("Error: Could not find extracted source folder. Installation aborted.")
        return

    # 5. Set Permissions 
    set_permissions(driver_dir, driver_name)

    # 6. Final Config Steps (AFTER permissions are set)
    config_restored = False
    if config_type == 'full_config':
        # Restore backed-up config if it exists
        if config_backed_up:
            config_restored = handle_config_restore(driver_dir, driver_name)
        
        # Handle first-run logic (only runs if config.ini was NOT restored)
        if not config_restored and not is_update:
            handle_first_run_config(driver_dir, driver_name)

    # 7. Final Action (Install/Restart/Prompt)
    handle_post_install_actions(driver_dir, driver_name, is_update)
    
    # 8. Cleanup Temp Files
    print("\nCleaning up temp files...")
    if os.path.exists(extract_dir):
        shutil.rmtree(extract_dir, ignore_errors=True) 
    if os.path.exists(zip_path):
        os.remove(zip_path)


# --- Main Loop ---
def main():
    """Main function to run the selection loop."""
    os.makedirs(DRIVER_PATH, exist_ok=True)
    
    while True:
        driver_name, config_type = select_driver()
        
        if driver_name is None:
            # The user selected 'Exit Script'
            break
            
        run_installation(driver_name, config_type)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript interrupted by user. Exiting.")
      
