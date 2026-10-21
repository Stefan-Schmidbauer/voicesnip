#!/usr/bin/env python3
"""
Quickstrap - Generic Profile-Based Installation Manager

This script manages installation with different profiles defined in quickstrap/installation_profiles.ini.
The profile configuration determines available features, requirements, and installation options.
"""

import sys
import os

# Check Python version early (must be before other imports)
if sys.version_info < (3, 6):
    print("Error: Python 3.6 or higher is required")
    print(f"Current version: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print("\nPlease upgrade Python:")
    print("  sudo apt install python3")
    sys.exit(1)
import re
import subprocess
import argparse
import shutil
import tempfile
from pathlib import Path
from configparser import ConfigParser
from datetime import datetime
from typing import List, Tuple, Dict, Optional

# Quickstrap framework version. Kept in lock-step with the git tag on GitHub
# (tag `v<VERSION>`), so a project can tell exactly which engine it carries.
# Bumped by maintainers when the engine (this file, start.sh, activate.sh)
# changes - not by the projects that embed it.
QUICKSTRAP_VERSION = "1.0.0"

# Default upstream for `--update-framework`. Override with `--source` (a local
# checkout or an alternate git URL).
QUICKSTRAP_REPO = "https://github.com/Stefan-Schmidbauer/quickstrap.git"

# Engine files owned by the framework: these are what `--update-framework`
# refreshes. Everything else under quickstrap/ (installation_profiles.ini,
# requirements_*, your own scripts) is project-owned and never touched.
FRAMEWORK_FILES = [
    "install.py",
    "start.sh",
    "quickstrap/activate.sh",
]
# Upstream ships its reference docs as README.md; a project that embeds
# Quickstrap keeps them as README.quickstrap.md so they never collide with the
# project's own README. (upstream_path, local_path)
FRAMEWORK_README = ("README.md", "README.quickstrap.md")


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print a formatted header"""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'=' * 70}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}[X] {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}[!] {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}[i] {text}{Colors.ENDC}")


def get_venv_paths(venv_path: Path) -> Tuple[Path, Path]:
    """Get paths for venv executables.

    Args:
        venv_path: Path to the virtual environment directory

    Returns:
        Tuple of (pip_path, python_path)
    """
    pip_exe = venv_path / 'bin' / 'pip'
    python_exe = venv_path / 'bin' / 'python'
    return pip_exe, python_exe


def get_config_dir() -> Path:
    """Get project directory for configuration files.

    Config files are stored in the project directory (where install.py is located),
    making the installation portable and allowing pre-built binaries to include
    their configuration.

    Returns:
        Path to the project directory (current working directory)
    """
    return Path.cwd()


def get_platform_name() -> str:
    """Get normalized platform name.

    Returns:
        'linux'
    """
    return 'linux'


def safe_app_name(app_name: str) -> str:
    """Normalize an app name for use in filenames.

    Lowercases and replaces spaces and slashes with underscores, matching the
    convention used for the per-installation config file.

    Args:
        app_name: Application display name

    Returns:
        Filename-safe app name
    """
    return app_name.lower().replace(' ', '_').replace('/', '_').replace('\\', '_')


def resolve_platform_config(config: Dict, key: str, required: bool = False) -> Optional[str]:
    """Resolve platform-specific or generic config value.

    Tries platform-specific key first (e.g., 'start_command_linux'),
    then falls back to generic key (e.g., 'start_command').

    Args:
        config: Configuration dictionary (metadata or profile)
        key: Base key name (without platform suffix)
        required: If True, print error if key not found

    Returns:
        Resolved value or None if not found
    """
    # Try linux-specific key first
    linux_key = f"{key}_linux"
    if linux_key in config and config[linux_key].strip():
        return config[linux_key].strip()

    # Fall back to generic key
    if key in config and config[key].strip():
        return config[key].strip()

    # Not found
    if required:
        print_error(f"Required configuration key '{key}' not found (tried '{linux_key}' and '{key}')")

    return None


def validate_platform_support(metadata: Dict) -> bool:
    """Validate that current platform is supported by this application.

    Args:
        metadata: Metadata dictionary from installation_profiles.ini

    Returns:
        True if current platform is supported, False otherwise
    """
    supported = metadata.get('supported_platforms', 'linux').strip()

    # Parse supported platforms
    supported_list = [p.strip().lower() for p in supported.split(',') if p.strip()]

    if 'linux' not in supported_list:
        print_error("This application does not support Linux")
        print()
        print_info(f"Supported platforms: {', '.join(supported_list)}")
        print()
        return False

    return True


def read_profiles(profile_file: str = 'quickstrap/installation_profiles.ini') -> Tuple[Dict, Dict]:
    """Read and parse installation profiles.

    Returns:
        Tuple of (profiles_dict, metadata_dict)
        profiles_dict: Dict with profile names as keys and profile configs as values
        metadata_dict: Dict with global metadata (app_name, config_dir, after_install, etc.)
    """
    if not Path(profile_file).exists():
        print_error(f"Profile configuration file not found: {profile_file}")
        sys.exit(1)

    config = ConfigParser()
    config.read(profile_file, encoding='utf-8')

    profiles = {}
    for section in config.sections():
        if section.startswith('profile:'):
            profile_name = section.split(':', 1)[1]
            profiles[profile_name] = dict(config[section])

    # Extract metadata
    metadata = {}
    if 'metadata' in config:
        metadata = dict(config['metadata'])

    return profiles, metadata


def check_system_packages_linux(package_file: str) -> Tuple[List[str], List[str]]:
    """Check which Linux system packages (APT/DEB) are installed.

    Uses dpkg-query to check package status on Debian/Ubuntu systems.

    Args:
        package_file: Path to file containing package names (one per line)

    Returns:
        Tuple of (installed_packages, missing_packages)
    """
    if not Path(package_file).exists():
        print_error(f"Package list file not found: {package_file}")
        return [], []

    # Read package list
    packages = []
    with open(package_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                packages.append(line)

    if not packages:
        return [], []

    print_info(f"Checking {len(packages)} APT/DEB system packages...")

    # Check all packages at once for better performance
    result = subprocess.run(
        ['dpkg-query', '-W', '-f=${Package} ${Status}\n'] + packages,
        capture_output=True,
        text=True
    )

    installed = []
    missing = []

    # Parse output to determine installed vs missing
    installed_set = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[-3:] == ['install', 'ok', 'installed']:
            installed_set.add(parts[0])

    for package in packages:
        if package in installed_set:
            installed.append(package)
        else:
            missing.append(package)

    return installed, missing


def check_system_requirements(profile: Dict) -> Tuple[List[str], List[str]]:
    """Check system requirements (APT/DEB packages).

    Args:
        profile: Profile configuration dictionary

    Returns:
        Tuple of (installed, missing)
    """
    req_file = resolve_platform_config(profile, 'system_requirements')
    if not req_file:
        print_warning("No system requirements file specified")
        return [], []
    return check_system_packages_linux(req_file)


def setup_venv(force: bool = False) -> Path:
    """Create or verify venv exists.

    Args:
        force: If True, recreate venv even if it exists

    Returns:
        Path to venv directory
    """
    venv_path = Path('venv')

    if force and venv_path.exists():
        print_info("Removing existing venv...")
        shutil.rmtree(venv_path)

    def _create_venv():
        """Create a new virtual environment, exit on failure."""
        try:
            subprocess.run(
                [sys.executable, '-m', 'venv', 'venv'],
                capture_output=True,
                text=True,
                check=True
            )
            print_success("Virtual environment created")
        except subprocess.CalledProcessError as e:
            print_error("Failed to create virtual environment")
            if e.stderr:
                print_error(f"Error: {e.stderr}")
            sys.exit(1)
        except Exception as e:
            print_error(f"Unexpected error creating virtual environment: {e}")
            sys.exit(1)

    if not venv_path.exists():
        print_info("Creating virtual environment...")
        _create_venv()
    else:
        # Verify the venv is valid by checking for critical files
        pip_exe, python_exe = get_venv_paths(venv_path)

        if not pip_exe.exists() or not python_exe.exists():
            print_warning("Virtual environment exists but appears corrupted")
            print_info("Recreating virtual environment...")
            shutil.rmtree(venv_path)
            _create_venv()
        else:
            print_info("Virtual environment already exists")

    return venv_path


def check_package_updates(venv_path: Path, requirements_file: str) -> Dict[str, str]:
    """Check for available package updates.

    Args:
        venv_path: Path to virtual environment
        requirements_file: Path to requirements file

    Returns:
        Dict mapping package names to available versions
    """
    if not Path(requirements_file).exists():
        print_error(f"Requirements file not found: {requirements_file}")
        return {}

    pip_exe, _ = get_venv_paths(venv_path)

    if not pip_exe.exists():
        print_error(f"pip not found at {pip_exe}")
        return {}

    print_info("Checking for package updates...")

    # Get list of outdated packages
    result = subprocess.run(
        [str(pip_exe), 'list', '--outdated', '--format=json'],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print_error("Failed to check for updates")
        return {}

    try:
        import json
        outdated = json.loads(result.stdout)
        return {pkg['name']: pkg['latest_version'] for pkg in outdated}
    except Exception:
        return {}


def update_python_packages(venv_path: Path, requirements_file: str) -> bool:
    """Update Python packages from requirements file.

    Args:
        venv_path: Path to virtual environment
        requirements_file: Path to requirements file

    Returns:
        True if successful
    """
    if not Path(requirements_file).exists():
        print_error(f"Requirements file not found: {requirements_file}")
        return False

    pip_exe, _ = get_venv_paths(venv_path)

    if not pip_exe.exists():
        print_error(f"pip not found at {pip_exe}")
        print_error("Virtual environment may be corrupted")
        print_info("Try running with --rebuild-venv flag to recreate it")
        return False

    print_info(f"Updating Python packages from {requirements_file}...")
    print_info("This may take several minutes...")

    # Upgrade packages
    result = subprocess.run(
        [str(pip_exe), 'install', '--upgrade', '-r', requirements_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Write full output to log
    with open('install.log', 'a') as f:
        f.write(f"\n{'=' * 70}\n")
        f.write(f"Update log: {datetime.now().isoformat()}\n")
        f.write(f"Requirements: {requirements_file}\n")
        f.write(f"{'=' * 70}\n")
        f.write(result.stdout)

    if result.returncode != 0:
        print_error("Failed to update Python packages")
        print_info("Check install.log for details")
        return False

    print_success("Python packages updated successfully")
    return True


def install_python_packages(venv_path: Path, requirements_file: str) -> bool:
    """Install Python packages from requirements file.

    Args:
        venv_path: Path to virtual environment
        requirements_file: Path to requirements file

    Returns:
        True if successful
    """
    if not requirements_file:
        print_error("No Python requirements file specified for this platform")
        return False

    if not Path(requirements_file).exists():
        print_error(f"Requirements file not found: {requirements_file}")
        return False

    pip_exe, _ = get_venv_paths(venv_path)

    # Verify pip executable exists
    if not pip_exe.exists():
        print_error(f"pip not found at {pip_exe}")
        print_error("Virtual environment may be corrupted")
        print_info("Try running with --rebuild-venv flag to recreate it")
        return False

    print_info(f"Installing Python packages from {requirements_file}...")
    print_info("This may take several minutes...")

    try:
        # Run pip with progress
        result = subprocess.run(
            [str(pip_exe), 'install', '-r', requirements_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        # Write full output to log
        output = result.stdout or ""
        with open('install.log', 'a', encoding='utf-8') as f:
            f.write(f"\n{'=' * 70}\n")
            f.write(f"Installation log: {datetime.now().isoformat()}\n")
            f.write(f"Requirements: {requirements_file}\n")
            f.write(f"{'=' * 70}\n")
            f.write(output)

        if result.returncode != 0:
            print_error("Failed to install Python packages")
            print_info("Check install.log for details")
            # Also print last few lines of output for immediate feedback
            if output:
                lines = output.strip().split('\n')
                print_error("Last output lines:")
                for line in lines[-10:]:
                    print(f"  {line}")
            return False

        print_success("Python packages installed successfully")

        # Generate frozen requirements for reproducibility
        try:
            freeze_result = subprocess.run(
                [str(pip_exe), 'freeze'],
                capture_output=True,
                text=True
            )
            if freeze_result.returncode == 0 and freeze_result.stdout:
                frozen_path = Path('requirements_frozen.txt')
                frozen_path.write_text(freeze_result.stdout, encoding='utf-8')
                print_info(f"Frozen requirements saved to {frozen_path}")
        except Exception:
            print_warning("Could not generate frozen requirements file")

        return True

    except Exception as e:
        print_error(f"Failed to run pip: {e}")
        print_info(f"pip path: {pip_exe}")
        print_info(f"requirements: {requirements_file}")
        return False


def validate_profile_files(profile: Dict) -> List[str]:
    """Validate that all files referenced in the profile exist.

    Checks both platform-specific and generic file references.

    Args:
        profile: Profile configuration dict

    Returns:
        List of missing files with their context (empty if all files exist)
    """
    missing = []
    platform = get_platform_name()

    # Check python requirements (platform-specific or generic)
    python_req = resolve_platform_config(profile, 'python_requirements')
    if python_req and not Path(python_req).exists():
        missing.append(f"{python_req} (python_requirements)")
    elif not python_req:
        # No python requirements found at all
        missing.append(f"python_requirements_{platform} or python_requirements (not specified)")

    # Check system requirements
    sys_req = resolve_platform_config(profile, 'system_requirements')
    if sys_req and not Path(sys_req).exists():
        missing.append(f"{sys_req} (system_requirements)")

    # Check post_install_scripts (platform-specific)
    scripts = resolve_platform_config(profile, 'post_install_scripts')
    if scripts:
        script_list = [s.strip() for s in scripts.split(',') if s.strip()]
        for script_path in script_list:
            if not Path(script_path).exists():
                missing.append(f"{script_path} (post_install_scripts_{platform})")

    # Check pre_install_scripts (platform-specific)
    scripts_pre = resolve_platform_config(profile, 'pre_install_scripts')
    if scripts_pre:
        script_list = [s.strip() for s in scripts_pre.split(',') if s.strip()]
        for script_path in script_list:
            if not Path(script_path).exists():
                missing.append(f"{script_path} (pre_install_scripts_{platform})")

    # Check uninstall_scripts (platform-specific)
    scripts_uninstall = resolve_platform_config(profile, 'uninstall_scripts')
    if scripts_uninstall:
        script_list = [s.strip() for s in scripts_uninstall.split(',') if s.strip()]
        for script_path in script_list:
            if not Path(script_path).exists():
                missing.append(f"{script_path} (uninstall_scripts_{platform})")

    return missing


def run_bash_script(script_path: str, env: Optional[Dict] = None) -> subprocess.CompletedProcess:
    """Run a bash script.

    stdin/stdout/stderr are inherited from the parent process rather than
    captured, so a script can prompt interactively (e.g. asking for a secret)
    without the prompt being silently buffered until the script exits. A
    script that never prints anything behaves exactly as before.

    Args:
        script_path: Path to the bash script to run
        env: Optional environment variables for the script

    Returns:
        CompletedProcess result
    """
    return subprocess.run(['bash', script_path], env=env)


def build_script_env(venv_path: Path, app_name: str) -> Dict[str, str]:
    """Build the environment passed to lifecycle (post-install / uninstall) scripts.

    Activates the virtual environment and exposes Quickstrap metadata so that
    install and uninstall scripts run with identical context. This symmetry lets
    uninstall scripts reconstruct deterministic paths (e.g. desktop entries derived
    from the app name) without any recorded state.

    Args:
        venv_path: Path to the virtual environment
        app_name: Application name from metadata

    Returns:
        Environment dictionary for subprocess execution
    """
    env = os.environ.copy()
    env['VIRTUAL_ENV'] = str(venv_path)
    pip_exe, _ = get_venv_paths(venv_path)
    env['PATH'] = f"{pip_exe.parent}:{env['PATH']}"
    env['QUICKSTRAP_APP_NAME'] = app_name
    env['QUICKSTRAP_CONFIG_DIR'] = str(get_config_dir())  # Project directory
    return env


def state_file_path(app_name: str) -> Path:
    """Compute the shared per-installation state file path.

    All lifecycle scripts of one installation share a single state file, stored
    alongside the installation config in the project directory. It is passed via
    QUICKSTRAP_STATE_FILE so that an install script and its matching uninstall
    script - which necessarily have different filenames - resolve to the same
    file. Quickstrap never reads or writes it itself; install scripts may record
    runtime artifacts (chosen ports, generated paths) there for the uninstall
    side to read back, and a script that records nothing simply ignores it.

    Args:
        app_name: Application name from metadata

    Returns:
        Path to the shared state file (may not exist)
    """
    return get_config_dir() / f"{safe_app_name(app_name)}.state"


def run_lifecycle_scripts(scripts: str, venv_path: Path, app_name: str,
                          abort_on_failure: bool) -> Tuple[bool, List[str]]:
    """Run a comma-separated list of lifecycle scripts with Quickstrap context.

    Used for both post-install scripts (abort_on_failure=True) and uninstall
    scripts (abort_on_failure=False, so a failing hook does not leave a
    half-removed installation behind). Each script receives the shared script
    environment plus QUICKSTRAP_STATE_FILE pointing at the installation's shared
    state file.

    Args:
        scripts: Comma-separated list of script paths
        venv_path: Path to the virtual environment
        app_name: Application name from metadata
        abort_on_failure: If True, stop and return on the first failing script

    Returns:
        Tuple of (success, failed_scripts). success is False if any script
        failed. failed_scripts lists the paths that failed.
    """
    script_list = [s.strip() for s in scripts.split(',') if s.strip()]
    env = build_script_env(venv_path, app_name)
    env['QUICKSTRAP_STATE_FILE'] = str(state_file_path(app_name))

    failed_scripts: List[str] = []

    for script_path in script_list:
        if not Path(script_path).exists():
            print_warning(f"Script not found: {script_path}")
            continue

        print_info(f"Running script: {script_path}")

        result = run_bash_script(script_path, env=env)

        if result.returncode != 0:
            print_error(f"Script failed: {script_path}")
            failed_scripts.append(script_path)
            if abort_on_failure:
                return False, failed_scripts

    return len(failed_scripts) == 0, failed_scripts


def run_pre_install_scripts(scripts: str, profile_name: str) -> bool:
    """Run pre-installation scripts.

    Args:
        scripts: Comma-separated list of scripts to run
        profile_name: Name of the profile being installed

    Returns:
        True if scripts passed or user chose to continue, False to abort
    """
    script_list = [s.strip() for s in scripts.split(',') if s.strip()]

    if not script_list:
        return True

    print_header("Step 2: Pre-Installation Scripts")

    failed_scripts = []

    for script_path in script_list:
        if not Path(script_path).exists():
            print_warning(f"Pre-install script not found: {script_path}")
            continue

        print_info(f"Running pre-install script: {script_path}")

        result = run_bash_script(script_path)

        if result.returncode != 0:
            print_error(f"Pre-install script failed: {script_path}")
            failed_scripts.append(script_path)

    if failed_scripts:
        print()
        print_warning("Warning: Pre-installation scripts failed")
        print()

        try:
            response = input("Continue anyway? [y/N]: ").strip().lower()
            if response == 'y':
                print_info("Continuing installation despite failed scripts...")
                return True
            else:
                print_info("Installation aborted by user")
                return False
        except (KeyboardInterrupt, EOFError):
            print()
            print_info("Installation aborted by user")
            return False
    else:
        print_success("All pre-install scripts completed successfully")
        return True


def write_installation_config(profile_name: str, features: str, app_name: str) -> Path:
    """Write installation config to project directory.

    Config file is stored in the project directory with app-specific name,
    making the installation portable.

    Args:
        profile_name: Name of installed profile
        features: Comma-separated feature list
        app_name: Application name (from metadata, used for config filename)

    Returns:
        Path to the written config file
    """
    config_dir = get_config_dir()
    # No need to create directory - we're in the project directory

    # App-specific config filename (lowercase, spaces replaced with underscores)
    config_filename = f"{safe_app_name(app_name)}_profile.ini"
    config_file = config_dir / config_filename

    config = ConfigParser()
    config['installation'] = {
        'profile': profile_name,
        'features': features,
        'install_date': datetime.now().isoformat(),
    }

    with open(config_file, 'w', encoding='utf-8') as f:
        config.write(f)

    print_success("Installation config written")

    return config_file


def show_profile_menu(profiles: Dict) -> str:
    """Show interactive profile selection menu.

    Args:
        profiles: Dict of available profiles

    Returns:
        Selected profile name
    """
    print("\nAvailable installation profiles:\n")

    profile_list = list(profiles.items())
    for i, (name, profile) in enumerate(profile_list, 1):
        print(f"  {Colors.BOLD}{i}) {profile['name']}{Colors.ENDC}")
        print(f"     {profile['description']}")
        print(f"     Features: {Colors.OKCYAN}{profile['features']}{Colors.ENDC}")
        print()

    while True:
        try:
            choice = input(f"Select profile (1-{len(profile_list)}): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(profile_list):
                return profile_list[idx][0]
            else:
                print_error(f"Please enter a number between 1 and {len(profile_list)}")
        except (ValueError, KeyboardInterrupt):
            print()
            sys.exit(0)


def run_uninstall(profiles: Dict, metadata: Dict, args) -> None:
    """Uninstall the application.

    Removes the project-owned parts that the installer created (the virtual
    environment and generated files) automatically, runs any profile-defined
    uninstall scripts to undo out-of-tree side effects, and lists the system
    packages that were required so the user can remove them manually.

    Args:
        profiles: Available profiles from installation_profiles.ini
        metadata: Global metadata from installation_profiles.ini
        args: Parsed command-line arguments (uses dry_run, yes)
    """
    app_name = metadata.get('app_name', 'Application')
    print_header(f"{app_name} Uninstall")

    config_dir = get_config_dir()
    config_file = config_dir / f'{safe_app_name(app_name)}_profile.ini'

    # Determine the installed profile (if the install left a record behind)
    profile = None
    if config_file.exists():
        config = ConfigParser()
        config.read(config_file)
        installed_profile_name = config.get('installation', 'profile', fallback=None)
        if installed_profile_name and installed_profile_name in profiles:
            profile = profiles[installed_profile_name]
            print_info(f"Installed profile: {profile['name']}")
        else:
            print_warning(
                f"Recorded profile '{installed_profile_name}' is not defined in "
                "installation_profiles.ini; uninstall scripts cannot be run."
            )
    else:
        print_warning("Installation config not found - performing best-effort cleanup")
        print_info("Uninstall scripts cannot be run without a recorded installation")

    # Collect project-owned files/directories to remove
    venv_path = Path('venv')
    local_paths: List[Path] = []
    if venv_path.exists():
        local_paths.append(venv_path)
    for name in ('requirements_frozen.txt', 'install.log'):
        p = config_dir / name
        if p.exists():
            local_paths.append(p)
    if config_file.exists():
        local_paths.append(config_file)
    # Shared state file written during installation
    state_file = state_file_path(app_name)
    if state_file.exists():
        local_paths.append(state_file)

    # Resolve uninstall scripts and system packages from the profile
    uninstall_scripts = resolve_platform_config(profile, 'uninstall_scripts') if profile else None
    still_installed: List[str] = []
    if profile:
        sys_req = resolve_platform_config(profile, 'system_requirements')
        if sys_req and Path(sys_req).exists():
            still_installed, _ = check_system_packages_linux(sys_req)

    # Show the plan
    print()
    print_info("The following will be removed:")
    if local_paths:
        for p in local_paths:
            print(f"  - {p}")
    else:
        print("  (no project files found)")
    if uninstall_scripts:
        print()
        print_info("Uninstall scripts to run:")
        for s in [s.strip() for s in uninstall_scripts.split(',') if s.strip()]:
            print(f"  - {s}")

    # Dry run stops here
    if args.dry_run:
        print()
        print_header("Dry Run - No Changes Made")
        if still_installed:
            print_info("System packages that were required (not removed):")
            print(f"  {', '.join(still_installed)}")
        return

    # Confirmation
    if not args.yes:
        print()
        try:
            response = input("Proceed with uninstall? [y/N]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            print_info("Uninstall aborted by user")
            return
        if response != 'y':
            print_info("Uninstall aborted by user")
            return

    failed_scripts: List[str] = []

    # Run uninstall scripts first (while venv still exists), never abort midway
    if uninstall_scripts:
        print_header("Running Uninstall Scripts")
        _, failed_scripts = run_lifecycle_scripts(
            uninstall_scripts, venv_path, app_name, abort_on_failure=False
        )

    # Remove project-owned files
    print_header("Removing Project Files")
    for p in local_paths:
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            print_success(f"Removed {p}")
        except Exception as e:
            print_error(f"Could not remove {p}: {e}")

    # System packages: list only, never remove automatically
    if still_installed:
        print()
        print_info(f"The following system packages were required by {app_name}:")
        print(f"  {', '.join(still_installed)}")
        print_info("If no other software needs them, remove with:")
        print(f"\n  {Colors.BOLD}sudo apt remove {' '.join(still_installed)}{Colors.ENDC}\n")

    # Report outcome
    print()
    if failed_scripts:
        print_header("Uninstall Completed with Warnings")
        print_warning("The following uninstall scripts failed:")
        for s in failed_scripts:
            print(f"  - {s}")
        print_info("You may need to clean up their side effects manually")
    else:
        print_header("Uninstall Complete!")
        print_success(f"{app_name} has been uninstalled")


def parse_framework_version(text: str) -> Optional[str]:
    """Extract QUICKSTRAP_VERSION from the text of an install.py file."""
    match = re.search(
        r'''^QUICKSTRAP_VERSION\s*=\s*["']([^"']+)["']''', text, re.MULTILINE
    )
    return match.group(1) if match else None


def fetch_upstream(source: str, dest: Path) -> Path:
    """Make the upstream Quickstrap tree available locally and return its root.

    A local path is used in place (no copy); anything else is treated as a git
    URL and shallow-cloned into dest. Raises on failure so the caller can report.
    """
    local = Path(source).expanduser()
    if local.exists():
        return local
    print_info(f"Cloning {source} ...")
    subprocess.run(['git', 'clone', '--depth', '1', source, str(dest)], check=True)
    return dest


def update_framework(args) -> None:
    """Refresh the Quickstrap engine files from upstream.

    Updates only framework-owned files (FRAMEWORK_FILES + the reference README);
    project-owned files (installation_profiles.ini, requirements_*, your own
    scripts) are never touched. Reuses --dry-run (show plan only) and --yes
    (skip confirmation). The running install.py may overwrite itself safely - it
    is already loaded into memory.
    """
    print_header("Quickstrap Framework Update")
    source = args.source or QUICKSTRAP_REPO

    with tempfile.TemporaryDirectory(prefix="quickstrap-update-") as tmp:
        try:
            tree = fetch_upstream(source, Path(tmp) / "upstream")
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print_error(f"Could not fetch upstream from {source}: {exc}")
            print_info("Pass a local checkout with --source /path/to/quickstrap")
            sys.exit(1)

        upstream_install = tree / "install.py"
        if not upstream_install.exists():
            print_error(f"No install.py found in upstream source: {tree}")
            sys.exit(1)

        upstream_version = parse_framework_version(
            upstream_install.read_text(encoding="utf-8")
        ) or "unknown"
        print_info(f"Installed framework version: {QUICKSTRAP_VERSION}")
        print_info(f"Upstream framework version:  {upstream_version}")

        # Resolve which framework files actually exist upstream and locally.
        # install.py/start.sh are mandatory and always refreshed; optional
        # helpers (e.g. activate.sh) are only refreshed if the project already
        # has them, so an update never surprises a project with new files.
        mandatory = {"install.py", "start.sh"}
        planned: List[Tuple[Path, Path]] = []
        for rel in FRAMEWORK_FILES:
            src = tree / rel
            dst = Path(rel)
            if src.exists() and (dst.exists() or rel in mandatory):
                planned.append((src, dst))
        up_readme = tree / FRAMEWORK_README[0]
        local_readme = Path(FRAMEWORK_README[1])
        # Only refresh the reference README if this project keeps one
        if up_readme.exists() and local_readme.exists():
            planned.append((up_readme, local_readme))

        print()
        print_info("Framework files to update:")
        for _, dst in planned:
            print(f"  - {dst}")
        print_info("Left untouched: installation_profiles.ini, requirements_*, your own scripts/")

        if args.dry_run:
            print()
            print_header("Dry Run - No Changes Made")
            return

        # Confirmation (skipped with --yes)
        if not args.yes:
            if upstream_version == QUICKSTRAP_VERSION:
                prompt = f"Already on {QUICKSTRAP_VERSION}. Re-copy framework files anyway? [y/N]: "
            else:
                prompt = f"Update framework {QUICKSTRAP_VERSION} -> {upstream_version}? [y/N]: "
            print()
            try:
                response = input(prompt).strip().lower()
            except (KeyboardInterrupt, EOFError):
                print()
                print_info("Update aborted by user")
                return
            if response != 'y':
                print_info("Update aborted by user")
                return

        # copy2 preserves mode bits, so executables stay executable
        for src, dst in planned:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            print_success(f"Updated {dst}")

    print()
    print_header("Framework Updated")
    print_success(f"Quickstrap engine now at {upstream_version}")
    print_info("Review with 'git diff', then run ./install.py --validate")


def main():
    """Main installation flow"""
    # Read profiles first to get available choices
    profiles, metadata = read_profiles()

    if not profiles:
        print_error("No installation profiles found")
        sys.exit(1)

    # Validate platform support
    if not validate_platform_support(metadata):
        sys.exit(1)

    # Get app name from metadata or use generic name
    app_name = metadata.get('app_name', 'Application')
    # Note: config_dir is no longer used - config is stored in project directory

    # Now create parser with dynamic choices
    parser = argparse.ArgumentParser(
        description=f'{app_name} Installation Manager',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  ./install.py                              # Interactive installation
  ./install.py --profile {list(profiles.keys())[0] if profiles else 'profile'}   # Install profile directly
  ./install.py --rebuild-venv               # Rebuild venv, then interactive menu
  ./install.py --profile {list(profiles.keys())[0] if profiles else 'profile'} --rebuild-venv # Rebuild venv for specific profile
  ./install.py --dry-run                    # Show what would be installed
  ./install.py --validate                   # Validate all profiles
  ./install.py --check-update-python        # Check for Python package updates
  ./install.py --update-python              # Update Python packages
  ./install.py --uninstall --dry-run        # Show what uninstall would remove
  ./install.py --uninstall                  # Uninstall (asks for confirmation)
  ./install.py --uninstall --yes            # Uninstall without confirmation
  ./install.py --version                    # Print the Quickstrap framework version
  ./install.py --update-framework --dry-run # Show which engine files would update
  ./install.py --update-framework           # Update the Quickstrap engine from GitHub
        """
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'quickstrap {QUICKSTRAP_VERSION}',
        help='Print the Quickstrap framework version and exit'
    )
    parser.add_argument(
        '--profile',
        choices=list(profiles.keys()),
        help='Profile to install (skips interactive menu)'
    )
    parser.add_argument(
        '--rebuild-venv',
        action='store_true',
        help='Rebuild virtual environment from scratch'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be installed without making changes'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate all profiles and their referenced files without installing'
    )
    parser.add_argument(
        '--check-update-python',
        action='store_true',
        help='Check for available Python package updates'
    )
    parser.add_argument(
        '--update-python',
        action='store_true',
        help='Update Python packages in existing virtual environment'
    )
    parser.add_argument(
        '--uninstall',
        action='store_true',
        help='Uninstall: remove venv, generated files and run uninstall scripts'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Skip confirmation prompts (for --uninstall and --update-framework)'
    )
    parser.add_argument(
        '--update-framework',
        action='store_true',
        help='Update the Quickstrap engine files from upstream (project files untouched)'
    )
    parser.add_argument(
        '--source',
        metavar='PATH_OR_URL',
        help='Source for --update-framework: a local checkout or git URL (default: official repo)'
    )

    args = parser.parse_args()

    # Update framework mode
    if args.update_framework:
        update_framework(args)
        return

    # Uninstall mode
    if args.uninstall:
        run_uninstall(profiles, metadata, args)
        return

    # Validate mode - check all profiles and exit
    if args.validate:
        print_header(f"{app_name} Configuration Validation")

        all_valid = True

        for profile_name, profile in profiles.items():
            print_info(f"Validating profile: {profile_name}")

            # Check required fields (platform-aware)
            required_fields = ['name', 'description', 'features']
            missing_fields = [f for f in required_fields if f not in profile or not profile[f].strip()]

            # Check requirements exist
            python_req = resolve_platform_config(profile, 'python_requirements')
            if not python_req:
                missing_fields.append('python_requirements')

            sys_req = resolve_platform_config(profile, 'system_requirements')
            if not sys_req:
                missing_fields.append('system_requirements')

            if missing_fields:
                print_error(f"  Missing required fields: {', '.join(missing_fields)}")
                all_valid = False
            else:
                print_success(f"  Required fields: OK")

            # Validate file references
            missing_files = validate_profile_files(profile)
            if missing_files:
                print_error(f"  Missing files:")
                for missing_file in missing_files:
                    print(f"    - {missing_file}")
                all_valid = False
            else:
                print_success(f"  File references: OK")

            # Check script executability (platform-aware)
            scripts_to_check = []

            scripts_pre = resolve_platform_config(profile, 'pre_install_scripts')
            if scripts_pre:
                scripts_to_check.extend([(s.strip(), 'pre_install') for s in scripts_pre.split(',') if s.strip()])

            scripts_post = resolve_platform_config(profile, 'post_install_scripts')
            if scripts_post:
                scripts_to_check.extend([(s.strip(), 'post_install') for s in scripts_post.split(',') if s.strip()])

            scripts_uninstall = resolve_platform_config(profile, 'uninstall_scripts')
            if scripts_uninstall:
                scripts_to_check.extend([(s.strip(), 'uninstall') for s in scripts_uninstall.split(',') if s.strip()])

            non_executable = []
            for script_path, script_type in scripts_to_check:
                if Path(script_path).exists() and not os.access(script_path, os.X_OK):
                    non_executable.append(f"{script_path} ({script_type})")

            if non_executable:
                print_warning(f"  Non-executable scripts:")
                for script in non_executable:
                    print(f"    - {script}")
                print_info(f"    Fix with: chmod +x <script>")
            else:
                if scripts_to_check:
                    print_success(f"  Script executability: OK")

            print()

        # Check metadata
        print_info("Validating metadata")
        # Note: config_dir is no longer required as config is stored in project directory
        required_metadata = ['app_name']
        missing_metadata = [f for f in required_metadata if f not in metadata or not metadata[f].strip()]

        # Check for start_command (platform-specific or generic)
        start_cmd = resolve_platform_config(metadata, 'start_command')
        if not start_cmd:
            missing_metadata.append('start_command (platform-specific)')

        if missing_metadata:
            print_error(f"  Missing required metadata: {', '.join(missing_metadata)}")
            all_valid = False
        else:
            print_success(f"  Metadata: OK")

        print()

        if all_valid:
            print_header("Validation Successful!")
            print_success("All profiles are properly configured")
        else:
            print_header("Validation Failed!")
            print_error("Please fix the errors above")
            sys.exit(1)

        return

    # Check Python packages mode
    if args.check_update_python:
        print_header(f"{app_name} Update Check")

        # Check if venv exists
        venv_path = Path('venv')
        if not venv_path.exists():
            print_error("Virtual environment not found")
            print_info("Run ./install.py first to install the application")
            sys.exit(1)

        # Determine which profile is installed (config in project directory)
        config_file = get_config_dir() / f'{safe_app_name(app_name)}_profile.ini'

        if not config_file.exists():
            print_error("Installation profile not found")
            print_info("Cannot determine which profile is installed")
            print_info("Run ./install.py to install a profile")
            sys.exit(1)

        # Read installed profile
        config = ConfigParser()
        config.read(config_file)
        installed_profile_name = config.get('installation', 'profile', fallback=None)

        if not installed_profile_name or installed_profile_name not in profiles:
            print_error(f"Installed profile '{installed_profile_name}' not found in configuration")
            sys.exit(1)

        profile = profiles[installed_profile_name]
        print_info(f"Installed profile: {profile['name']}")

        # Check for updates (platform-specific requirements)
        python_req = resolve_platform_config(profile, 'python_requirements', required=True)
        if not python_req:
            sys.exit(1)
        updates = check_package_updates(venv_path, python_req)

        if not updates:
            print_success("All packages are up to date!")
        else:
            print_warning(f"Found {len(updates)} package(s) with available updates:")
            print()
            for pkg_name, new_version in sorted(updates.items()):
                print(f"  • {pkg_name} → {new_version}")
            print()
            print_info("Run './install.py --update-python' to update packages")

        return

    # Update mode
    if args.update_python:
        # Determine profile to update (config in project directory)
        config_file = get_config_dir() / f'{safe_app_name(app_name)}_profile.ini'

        if not config_file.exists():
            print_error("Installation profile not found")
            print_info("Cannot determine which profile is installed")
            print_info("Run ./install.py to install a profile")
            sys.exit(1)

        # Read installed profile
        config = ConfigParser()
        config.read(config_file)
        installed_profile_name = config.get('installation', 'profile', fallback=None)

        if not installed_profile_name or installed_profile_name not in profiles:
            print_error(f"Installed profile '{installed_profile_name}' not found in configuration")
            sys.exit(1)

        profile = profiles[installed_profile_name]

        print_header(f"{app_name} Package Update")
        print_info(f"Profile: {profile['name']}")

        venv_path = Path('venv')
        if not venv_path.exists():
            print_error("Virtual environment not found")
            print_info("Run ./install.py first to install the application")
            sys.exit(1)

        # Update packages (platform-specific requirements)
        python_req = resolve_platform_config(profile, 'python_requirements', required=True)
        if not python_req:
            sys.exit(1)
        success = update_python_packages(venv_path, python_req)

        if success:
            print()
            print_header("Update Complete!")
            print_success("Python packages updated successfully")
        else:
            print_error("Update failed")
            sys.exit(1)

        return

    # Print header
    print_header(f"{app_name} Installation")

    # Show loaded profiles
    print_info("Loading installation profiles...")
    print_success(f"Found {len(profiles)} profile(s): {', '.join(profiles.keys())}")

    # Select profile
    if args.profile:
        if args.profile not in profiles:
            print_error(f"Profile '{args.profile}' not found")
            sys.exit(1)
        profile_name = args.profile
        print_info(f"Using profile: {profile_name}")
    else:
        profile_name = show_profile_menu(profiles)

    profile = profiles[profile_name]

    print()
    print_info(f"Selected: {Colors.BOLD}{profile['name']}{Colors.ENDC}")
    print_info(f"Features: {profile['features']}")
    print()

    # Validate profile files exist
    missing_files = validate_profile_files(profile)
    if missing_files:
        print_error("Profile validation failed!")
        print()
        print_error("Missing files:")
        for missing_file in missing_files:
            print(f"  - {missing_file}")
        print()
        print_info("Please check your profile configuration in:")
        print(f"  quickstrap/installation_profiles.ini")
        sys.exit(1)

    # Dry run mode
    if args.dry_run:
        print_header("Dry Run Mode - No Changes Will Be Made")
        print(f"Profile: {profile_name}")

        python_req = resolve_platform_config(profile, 'python_requirements')
        print(f"Python packages file: {python_req}")

        sys_req = resolve_platform_config(profile, 'system_requirements')
        print(f"System packages file: {sys_req}")

        print(f"Features: {profile['features']}")

        # Check system packages
        _, missing_system = check_system_requirements(profile)
        if missing_system:
            print(f"\nMissing system packages: {', '.join(missing_system)}")
            print(f"Would need to run: sudo apt install {' '.join(missing_system)}")
        else:
            print("\nAll system requirements are met")

        print("\nDry run complete")
        return

    # Check system packages
    print_header("Step 1: System Requirements Check")
    installed, missing = check_system_requirements(profile)

    if installed:
        print_success(f"{len(installed)} system requirement(s) already installed/available")

    if missing:
        print_error(f"{len(missing)} system requirement(s) missing:")
        for item in missing:
            print(f"  - {item}")

        print()
        print_info("Please install missing system packages with:")
        print(f"\n  {Colors.BOLD}sudo apt install {' '.join(missing)}{Colors.ENDC}\n")
        print_info("Then re-run this installer.")
        sys.exit(1)

    if not installed and not missing:
        # No check was performed (no script/file configured)
        print_info("No system requirements check configured for this platform")
    else:
        print_success("All system requirements are met")

    # Run pre-install scripts if defined (platform-specific)
    scripts_pre = resolve_platform_config(profile, 'pre_install_scripts')
    if scripts_pre:
        should_continue = run_pre_install_scripts(scripts_pre, profile_name)
        if not should_continue:
            sys.exit(1)
        step_offset = 1  # Pre-install scripts used Step 2
    else:
        step_offset = 0  # No pre-install scripts, so venv is Step 2

    # Setup virtual environment
    print_header(f"Step {2 + step_offset}: Virtual Environment Setup")
    venv_path = setup_venv(force=args.rebuild_venv)

    # Install Python packages (platform-specific)
    print_header(f"Step {3 + step_offset}: Python Package Installation")
    python_req = resolve_platform_config(profile, 'python_requirements', required=True)
    success = install_python_packages(venv_path, python_req)

    if not success:
        print_error("Installation failed")
        sys.exit(1)

    # Run post-install scripts if defined (platform-specific)
    scripts = resolve_platform_config(profile, 'post_install_scripts')
    if scripts:
        print_header(f"Step {4 + step_offset}: Post-Installation Scripts")

        success, _ = run_lifecycle_scripts(
            scripts, venv_path, app_name, abort_on_failure=True
        )
        if not success:
            sys.exit(1)

        print_success("All post-install scripts completed")

    # Write installation config
    # Calculate final step number: 1 (sys) + pre_scripts + venv + python + post_scripts + config
    final_step = 4 + step_offset + (1 if scripts else 0)
    print_header(f"Step {final_step}: Configuration")
    config_path = write_installation_config(
        profile_name=profile_name,
        features=profile['features'],
        app_name=app_name
    )

    # Success!
    print_header("Installation Complete!")
    print_success(f"{app_name} '{profile['name']}' profile installed successfully")
    print()

    # Show after_install message if provided (platform-specific)
    after_install_msg = resolve_platform_config(metadata, 'after_install')
    if after_install_msg:
        print_info(after_install_msg)
        print()

    print_info("Installation configuration:")
    print(f"  {config_path}")
    print()


if __name__ == '__main__':
    main()
