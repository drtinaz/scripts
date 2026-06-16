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
DRIVER_CONFIGS = {
    1: {"name": "auto_current", "config_type": "full_config"}, 
    2: {"name": "auto_switch", "config_type": "none"},
    3: {"name": "gps_socat", "config_type": "full_config"},    
    4: {"name": "external_devices", "config_type": "full_config"}, 
    5: {"name": "transfer_switch", "config_type": "none"},
    6: {"name": "autogen", "config_type": "full_config"},
    7: {"name": "mp2_emulator", "config_type": "full_config"},
}

# --- Helper Functions ---

def get_latest_versions(driver_name):
    """Fetches the latest stable and beta version tags from GitHub, plus previous releases."""
    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        releases = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching version numbers for {driver_name}: {e}")
        return None, None, []

    stable_tag = None
    try:
        latest_release_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases/latest"
        latest_release = requests.get(latest_release_url).json()
        stable_tag = latest_release.get("tag_name")
    except Exception:
        pass

    beta_tag = None
    previous_versions = []
    
    for release in releases:
        tag = release.get("tag_name", "")
        # Skip draft releases
        if release.get("draft", False):
            continue
            
        if re.search(r'(rc|beta)', tag, re.IGNORECASE):
            if beta_tag is None:
                beta_tag = tag
        else:
            # Collect stable releases (excluding the latest stable)
            if tag != stable_tag:
                previous_versions.append(tag)
    
    # Return the 3 most recent previous versions
    previous_versions = previous_versions[:3]
    
    return stable_tag, beta_tag, previous_versions

def select_driver():
    """Presents a menu and returns the selected driver name and config type."""
    print("\n--- Driver Selection Menu ---")
    while True:
        for num, driver_info in DRIVER_CONFIGS.items():
            print(f"{num}) {driver_info['name']}")
        print("8) Exit Script")
        
        choice = input("\nSelect a driver to install (1-7) or 8 to exit: ")
        
        if choice == '8':
            print("Exiting script.")
            return None, None
            
        try:
            choice_num = int(choice)
            if choice_num in DRIVER_CONFIGS:
                return DRIVER_CONFIGS[choice_num]['name'], DRIVER_CONFIGS[choice_num]['config_type']
            else:
                print(f"Invalid option: {choice}. Please enter a number between 1 and 8.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def select_version(driver_name, stable_tag, beta_tag, previous_versions, installed_tag=None):
    """
    Presents a version menu and returns the selected tag and download URL.
    - Added installed_tag parameter to display current version.
    - Added previous_versions to allow installing older releases.
    """
    print("\n--- Version Selection ---")
    
    if installed_tag:
        print(f"**Installed version is: {installed_tag}**")

    version_options = []
    if stable_tag:
        version_options.append((f"Latest Stable Release: {stable_tag}", stable_tag, "stable"))
    if beta_tag:
        version_options.append((f"Latest Beta/RC Build: {beta_tag}", beta_tag, "beta"))
    
    # Add previous versions if available
    if previous_versions:
        version_options.append(("--- Previous Versions ---", None, "separator"))
        for prev_tag in previous_versions:
            version_options.append((f"Previous Version: {prev_tag}", prev_tag, "previous"))
    
    # Add custom version input option
    version_options.append(("Enter a specific version/tag manually", None, "custom"))
    version_options.append(("Quit/Cancel Installation", None, "quit"))

    while True:
        for i, (label, tag, _) in enumerate(version_options, 1):
            # Skip printing separator lines as numbered options
            if tag is None and label.startswith("---"):
                print(f"\n{label}")
            else:
                print(f"{i}) {label}")
        
        choice = input("\nSelect which version you want to install: ")
        
        try:
            choice_num = int(choice) - 1
            if 0 <= choice_num < len(version_options):
                selected_label, selected_tag, selected_type = version_options[choice_num]
                
                # Handle separator - can't select it
                if selected_type == "separator":
                    print("Please select a valid version option.")
                    continue
                
                # Handle quit
                if selected_type == "quit":
                    print("Installation cancelled. Returning to main menu.")
                    return None, None
                
                # Handle custom version input
                if selected_type == "custom":
                    custom_tag = input("\nEnter the exact version tag to install (e.g., v1.2.3): ").strip()
                    if not custom_tag:
                        print("No version entered. Returning to version selection.")
                        continue
                    
                    # Verify the tag exists
                    verify_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases/tags/{custom_tag}"
                    try:
                        verify_response = requests.get(verify_url)
                        if verify_response.status_code == 200:
                            selected_tag = custom_tag
                            print(f"> Selected custom version: {selected_tag}")
                        else:
                            print(f"Error: Tag '{custom_tag}' not found for repository {driver_name}.")
                            print("Please check the tag name and try again.")
                            continue
                    except requests.exceptions.RequestException as e:
                        print(f"Error verifying tag: {e}")
                        continue
                
                # Determine download URL based on tag type
                if selected_tag == stable_tag or (selected_type == "stable"):
                    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases/latest"
                    response = requests.get(api_url).json()
                    download_url = response.get("zipball_url")
                elif selected_type == "custom":
                    # For custom tags, we need to get the release info
                    api_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/releases/tags/{selected_tag}"
                    response = requests.get(api_url).json()
                    download_url = response.get("zipball_url")
                else: 
                    download_url = f"https://api.github.com/repos/{GITHUB_USER}/{driver_name}/zipball/{selected_tag}"
                    
                if not download_url:
                    print(f"Error: Could not determine download URL for tag {selected_tag}. Returning to main menu.")
                    return None, None
                    
                print(f"> Selected version: {selected_tag}")
                return selected_tag, download_url
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

def handle_first_run_config(driver_dir, driver_name):
    """Handles initial config file creation or config.py execution."""
    config_file = os.path.join(driver_dir, "config.ini")
    
    if os.path.isfile(config_file):
        return
        
    if driver_name in ["auto_current", "gps_socat", "mp2_emulator", "autogen"]:
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
        print("2) Defer running **config.py** for later")
        print("=====================================================================")
        
        while True:
            choice = input("\nSelect an option (1 or 2): ")
            if choice == '1':
                print(f"\nLaunching configuration script: python {config_script_path}...")
                try:
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
    
    executables = [
        f"{driver_name}.py", "install.sh", "restart.sh", "uninstall.sh", 
        "config.py", "service/run", "service/log/run",
    ]

    for file_name in executables:
        file_path = os.path.join(driver_dir, file_name)
        if os.path.exists(file_path):
            os.chmod(file_path, 0o755)

def prompt_run_script(script_path, script_name, action_desc):
    """Presents the user with a 'Run now or defer' option for a shell script."""
    
    print("\n=====================================================================")
    print(f"The next step is to run {script_name} to {action_desc}.")
    print(f"1) Run **{script_name}** now (Recommended)")
    print(f"2) Defer running **{script_name}** for later")
    print("=====================================================================")

    while True:
        choice = input(f"\nSelect an option (1 or 2): ")
        if choice == '1':
            if os.path.exists(script_path):
                print(f"\nLaunching script: /bin/bash {script_path}...")
                try:
                    subprocess.run(["/bin/bash", script_path], check=True)
                    print(f"\n{script_name} executed successfully.")
                except subprocess.CalledProcessError as e:
                    print(f"\nScript failed with error: {e}")
                    print("You may need to check the script manually.")
                except FileNotFoundError:
                    print(f"\nError: /bin/bash interpreter or {script_name} not found.")
            else:
                print(f"Error: Script {script_name} not found. Cannot run automatically.")
            break
        elif choice == '2':
            print(f"\nAction deferred. Remember to run: /bin/bash {script_path} later.")
            break
        else:
            print("Invalid option. Please enter 1 or 2.")


def handle_config_edit_and_install(driver_dir, driver_name):
    """Handles the two-stage interactive first-install for auto_current/gps_socat/mp2_emulator/autogen."""
    action_type = "alter the settings for your generator" if driver_name in ["auto_current", "autogen"] else "verify settings"
    config_file = os.path.join(driver_dir, "config.ini")
    install_script = os.path.join(driver_dir, "install.sh")

    print("\n" * 2)
    print("--- First Install Configuration ---")
    print(f"Configuration required for **{driver_name}**.")
    print(f"1) Edit **{config_file}** now (to {action_type})")
    print(f"2) Defer configuration for later")

    while True:
        config_choice = input("\nSelect an option (1 or 2): ")
        if config_choice == '1':
            print("\n=====================================================================")
            print(f"🚀 Launching Nano Editor for: **{config_file}**")
            print("Please edit the required settings and save/exit (Ctrl+X).")
            print("=====================================================================")
            
            # --- KEY CHANGE: Launch nano in the current terminal ---
            try:
                # The subprocess call blocks execution until the user exits nano
                subprocess.run(["nano", config_file], check=True)
                print("\n✅ Configuration file edited and saved.")
            except FileNotFoundError:
                print("\n❌ Error: The 'nano' editor was not found. Please install it or edit the file manually.")
                # We still proceed to the install step, assuming the user will handle the config
            except subprocess.CalledProcessError:
                print("\n⚠️ Warning: The editor exited with an error. Please verify the config file manually.")
            
            # Now proceed to the install script prompt
            prompt_run_script(install_script, "install.sh", "activate the new installation")
            break
        elif config_choice == '2':
            # Defer config edit and install
            print("\nConfiguration deferred. Remember to run the following commands:")
            print(f"1. **Edit config**: `nano {config_file}`")
            print(f"2. **Run install**: `/bin/bash {install_script}`")
            break
        else:
            print("Invalid option. Please enter 1 or 2.")


def handle_post_install_actions(driver_dir, driver_name, is_update):
    """Handles the final prompts (editing config/running install/restart) based on driver state."""
    print("\n" * 2)
    print(f"--- Final Setup for {driver_name} ---")
    
    install_script = os.path.join(driver_dir, "install.sh")
    restart_script = os.path.join(driver_dir, "restart.sh")

    if is_update:
        # ALL Updates: Run restart script (non-interactive)
        if os.path.exists(restart_script):
            print(f"Update detected. Restarting driver by running: /bin/bash {restart_script}")
            subprocess.run(["/bin/bash", restart_script])
        else:
            print(f"Update detected, but {restart_script} not found. Driver may require manual restart.")

    else: # First Install
        if driver_name in ["auto_current", "gps_socat", "mp2_emulator", "autogen"]:
            handle_config_edit_and_install(driver_dir, driver_name)

        elif driver_name == "external_devices":
            # Config was handled/deferred by handle_first_run_config
            print("✅ Installation complete. The configuration steps for this driver have been handled or deferred.")
            print("Remember to run config.py and install.sh if you deferred configuration.")

        elif driver_name in ["auto_switch", "transfer_switch"]:
            # Use the generic prompt_run_script for first install
            prompt_run_script(install_script, "install.sh", "activate the new installation")
    
    print("\n" * 2)
    print(f"✅ Installation/Update of **{driver_name}** Complete. Returning to main menu.")
    print("\n" * 2)

# --- Installation Function ---

def run_installation(driver_name, config_type):
    """Handles the full installation/update process for a single driver."""
    driver_dir = os.path.join(DRIVER_PATH, driver_name)
    is_update = os.path.isdir(driver_dir)
    installed_tag = None
    
    # Check for installed version if directory exists (reading from existing version file)
    if is_update:
        version_file = os.path.join(driver_dir, "version")
        if os.path.exists(version_file):
            try:
                with open(version_file, 'r') as f:
                    installed_tag = f.read().strip()
            except Exception as e:
                print(f"Warning: Could not read existing version file: {e}")

    # 1. Fetch Versions and Select Version
    stable_tag, beta_tag, previous_versions = get_latest_versions(driver_name)
    if not stable_tag and not beta_tag and not previous_versions:
        print(f"Could not fetch any version information for {driver_name}. Please check the repository name.")
        return

    # Pass the installed_tag and previous_versions to the select_version function
    selected_tag, download_url = select_version(driver_name, stable_tag, beta_tag, previous_versions, installed_tag=installed_tag)
    if not selected_tag: return

    # 2. Pre-transfer Setup
    print(f"\n--- Installation Process for {driver_name} ({selected_tag}) ---")
    status_msg = "Updating" if is_update else "Installing"
    print(f"{status_msg} driver '{driver_name}'...")
    
    zip_path = os.path.join(TEMP_DIR, f"{driver_name}.zip")
    extract_dir = os.path.join(TEMP_DIR, f"extracted_{driver_name}")
    source_folder = None
    
    try:
        print(f"Downloading from: {download_url}")
        with requests.get(download_url, stream=True) as r:
            r.raise_for_status()
            with open(zip_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    except requests.exceptions.RequestException as e:
        print(f"Download failed. Error: {e}"); return

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
        print(f"Unzip failed. Error: {e}"); return

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
            print(f"Error cleaning up old driver files: {e}. Aborting installation."); return
            
    print("Copying new driver files...")
    if source_folder:
        shutil.move(source_folder, driver_dir)
    else:
        print("Error: Could not find extracted source folder. Installation aborted."); return

    # 5. Set Permissions 
    set_permissions(driver_dir, driver_name)

    # 6. Final Config Steps
    config_restored = False
    if config_type == 'full_config':
        if config_backed_up:
            config_restored = handle_config_restore(driver_dir, driver_name)
        if not config_restored and not is_update:
            # Only run config file creation on first install if not restored
            handle_first_run_config(driver_dir, driver_name)

    # 7. Final Action (Install/Restart/Prompt)
    handle_post_install_actions(driver_dir, driver_name, is_update)
    
    # 8. Cleanup Temp Files
    print("\nCleaning up temp files...")
    if os.path.exists(extract_dir): shutil.rmtree(extract_dir, ignore_errors=True) 
    if os.path.exists(zip_path): os.remove(zip_path)


# --- Main Loop ---
def main():
    """Main function to run the selection loop."""
    os.makedirs(DRIVER_PATH, exist_ok=True)
    
    while True:
        driver_name, config_type = select_driver()
        
        if driver_name is None:
            break
            
        run_installation(driver_name, config_type)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nScript interrupted by user. Exiting.")
