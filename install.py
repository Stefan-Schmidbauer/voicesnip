#!/usr/bin/env python3
"""
Quickstrap - Generic Profile-Based Installation Manager

This script manages installation with different profiles defined in quickstrap/installation_profiles.ini.
The profile configuration determines available features, requirements, and installation options.
"""

import sys
import os
import subprocess
import argparse
import shutil
from pathlib import Path
from configparser import ConfigParser
from datetime import datetime
from typing import List, Tuple, Dict, Optional


class Colors:
    """ANSI color codes for terminal output"""
    # Check if we're on Windows and if ANSI is supported
    _use_colors = True

    if sys.platform == 'win32':
        # Try to enable ANSI support on Windows 10+
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable VIRTUAL_TERMINAL_PROCESSING for stdout
            STD_OUTPUT_HANDLE = -11
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING)
            else:
                _use_colors = False
        except Exception:
            _use_colors = False

    if _use_colors:
        HEADER = '\033[95m'
        OKBLUE = '\033[94m'
        OKCYAN = '\033[96m'
        OKGREEN = '\033[92m'
        WARNING = '\033[93m'
        FAIL = '\033[91m'
        ENDC = '\033[0m'
        BOLD = '\033[1m'
    else:
        # No colors on unsupported terminals
        HEADER = ''
        OKBLUE = ''
        OKCYAN = ''
        OKGREEN = ''
        WARNING = ''
        FAIL = ''
        ENDC = ''
        BOLD = ''


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
    """Get platform-appropriate paths for venv executables.

    On Windows, venv uses 'Scripts' folder with .exe extensions.
    On Linux/macOS, venv uses 'bin' folder without extensions.

    Args:
        venv_path: Path to the virtual environment directory

    Returns:
        Tuple of (pip_path, python_path)
    """
    if sys.platform == 'win32':
        pip_exe = venv_path / 'Scripts' / 'pip.exe'
        python_exe = venv_path / 'Scripts' / 'python.exe'
    else:
        pip_exe = venv_path / 'bin' / 'pip'
        python_exe = venv_path / 'bin' / 'python'

    return pip_exe, python_exe


def get_config_dir(config_dir_name: str) -> Path:
    """Get platform-appropriate configuration directory.

    On Windows: uses LOCALAPPDATA environment variable (fallback to home directory).
    On Linux/macOS: uses ~/.config/

    Args:
        config_dir_name: Name of the config directory (e.g., 'myapp')

    Returns:
        Path to the configuration directory
    """
    if sys.platform == 'win32':
        # Use LOCALAPPDATA on Windows (local to machine, better for quickstrap)
        appdata = os.environ.get('LOCALAPPDATA')
        if appdata:
            return Path(appdata) / config_dir_name
        else:
            return Path.home() / config_dir_name
    else:
        return Path.home() / '.config' / config_dir_name


def get_platform_name() -> str:
    """Get normalized platform name.

    Returns:
        'linux' on Linux/macOS, 'windows' on Windows
    """
    return 'windows' if sys.platform == 'win32' else 'linux'


def resolve_platform_config(config: Dict, key: str, required: bool = False) -> Optional[str]:
    """Resolve platform-specific or generic config value.

    Tries platform-specific key first (e.g., 'start_command_linux' or 'start_command_windows'),
    then falls back to generic key (e.g., 'start_command').

    Args:
        config: Configuration dictionary (metadata or profile)
        key: Base key name (without platform suffix)
        required: If True, print error if key not found

    Returns:
        Resolved value or None if not found
    """
    platform = get_platform_name()

    # Try platform-specific key first
    platform_key = f"{key}_{platform}"
    if platform_key in config and config[platform_key].strip():
        return config[platform_key].strip()

    # Fall back to generic key
    if key in config and config[key].strip():
        return config[key].strip()

    # Not found
    if required:
        print_error(f"Required configuration key '{key}' not found (tried '{platform_key}' and '{key}')")

    return None


def validate_platform_support(metadata: Dict) -> bool:
    """Validate that current platform is supported by this application.

    Args:
        metadata: Metadata dictionary from installation_profiles.ini

    Returns:
        True if current platform is supported, False otherwise
    """
    supported = metadata.get('supported_platforms', 'linux,windows').strip()

    # Parse supported platforms
    supported_list = [p.strip().lower() for p in supported.split(',') if p.strip()]

    # Get current platform
    current_platform = get_platform_name()

    # Check if current platform is supported
    if current_platform not in supported_list:
        platform_display = 'Windows' if current_platform == 'windows' else 'Linux'
        print_error(f"This application does not support {platform_display}")
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
    config.read(profile_file)

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


def run_windows_system_check(script_path: str) -> Tuple[List[str], List[str]]:
    """Run PowerShell system check script on Windows.

    Executes a PowerShell script that checks for required system software
    and returns JSON with installed/missing lists.

    Args:
        script_path: Path to PowerShell script

    Returns:
        Tuple of (installed_software, missing_software)
    """
    if not Path(script_path).exists():
        print_error(f"System check script not found: {script_path}")
        return [], []

    print_info(f"Running Windows system check: {script_path}")

    try:
        # Run PowerShell script with ExecutionPolicy Bypass
        result = subprocess.run(
            ['powershell', '-ExecutionPolicy', 'Bypass', '-File', script_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            print_error("System check script failed")
            if result.stderr:
                print_error(f"Error: {result.stderr}")
            return [], []

        # Parse JSON output
        import json
        try:
            data = json.loads(result.stdout.strip())
            installed = data.get('installed', [])
            missing = data.get('missing', [])
            return installed, missing
        except json.JSONDecodeError as e:
            print_error(f"Failed to parse system check output: {e}")
            print_info("Script output:")
            print(result.stdout)
            return [], []

    except subprocess.TimeoutExpired:
        print_error("System check script timed out (>30s)")
        return [], []
    except Exception as e:
        print_error(f"Failed to run system check script: {e}")
        return [], []


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
    with open(package_file, 'r') as f:
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
    """Check system requirements based on platform.

    On Linux: Check APT/DEB packages from system_requirements_linux file
    On Windows: Run PowerShell check script from system_check_script_windows

    Args:
        profile: Profile configuration dictionary

    Returns:
        Tuple of (installed, missing)
    """
    platform = get_platform_name()

    if platform == 'linux':
        # Linux: check APT packages
        req_file = resolve_platform_config(profile, 'system_requirements')
        if not req_file:
            print_warning("No system requirements file specified for Linux")
            return [], []
        return check_system_packages_linux(req_file)
    else:
        # Windows: run PowerShell check script
        check_script = resolve_platform_config(profile, 'system_check_script')
        if not check_script:
            print_warning("No system check script specified for Windows")
            print_info("Skipping system requirements check")
            return [], []
        return run_windows_system_check(check_script)


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

    if not venv_path.exists():
        print_info("Creating virtual environment...")
        try:
            result = subprocess.run(
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
    else:
        # Verify the venv is valid by checking for critical files
        pip_exe, python_exe = get_venv_paths(venv_path)

        if not pip_exe.exists() or not python_exe.exists():
            print_warning("Virtual environment exists but appears corrupted")
            print_info("Recreating virtual environment...")
            shutil.rmtree(venv_path)
            try:
                result = subprocess.run(
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

    pip_exe = venv_path / 'bin' / 'pip'

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
    except:
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

    pip_exe = venv_path / 'bin' / 'pip'

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

    platform_display = "Windows" if get_platform_name() == 'windows' else "Linux"
    print_info(f"Installing Python packages for {platform_display} from {requirements_file}...")
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

    # Check python requirements (platform-specific or generic)
    python_req = resolve_platform_config(profile, 'python_requirements')
    if python_req and not Path(python_req).exists():
        missing.append(f"{python_req} (python_requirements)")
    elif not python_req:
        # No python requirements found at all
        platform = get_platform_name()
        missing.append(f"python_requirements_{platform} or python_requirements (not specified)")

    # Check system requirements (platform-specific)
    platform = get_platform_name()
    if platform == 'linux':
        sys_req = resolve_platform_config(profile, 'system_requirements')
        if sys_req and not Path(sys_req).exists():
            missing.append(f"{sys_req} (system_requirements_linux)")
    else:
        # Windows: check for system check script
        check_script = resolve_platform_config(profile, 'system_check_script')
        if check_script and not Path(check_script).exists():
            missing.append(f"{check_script} (system_check_script_windows)")

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

    return missing


def run_bash_script(script_path: str, env: Optional[Dict] = None) -> Optional[subprocess.CompletedProcess]:
    """Run a bash script with cross-platform handling.

    On Windows, bash scripts are skipped since bash is typically not available.
    On Linux/macOS, scripts are executed with bash.

    Args:
        script_path: Path to the bash script to run
        env: Optional environment variables for the script

    Returns:
        CompletedProcess result on Linux/macOS, None on Windows (script skipped)
    """
    if sys.platform == 'win32':
        # On Windows, bash is not typically available
        return None

    return subprocess.run(
        ['bash', script_path],
        env=env,
        capture_output=True,
        text=True
    )


def run_pre_install_scripts(scripts: str, profile_name: str) -> bool:
    """Run pre-installation scripts.

    On Windows, bash scripts are skipped with a warning since bash is
    typically not available. The function returns True to allow
    installation to continue.

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

    # On Windows, skip bash scripts with a warning
    if sys.platform == 'win32':
        print_warning("Bash script execution is not available on Windows")
        print_info(f"The following {len(script_list)} pre-install script(s) will be skipped:")
        for script_path in script_list:
            print(f"    - {script_path}")
        print_info("On Windows, you may need to manually perform any pre-installation steps")
        print_info("Skipping pre-install scripts...")
        print_success("Pre-install scripts skipped on Windows")
        return True

    failed_scripts = []

    for script_path in script_list:
        if not Path(script_path).exists():
            print_warning(f"Pre-install script not found: {script_path}")
            continue

        print_info(f"Running pre-install script: {script_path}")

        result = run_bash_script(script_path)

        # Display output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

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


def write_installation_config(profile_name: str, features: str, config_dir_name: str) -> Path:
    """Write installation config to platform-appropriate config directory.

    On Windows: %APPDATA%/{config_dir_name}/
    On Linux/macOS: ~/.config/{config_dir_name}/

    Args:
        profile_name: Name of installed profile
        features: Comma-separated feature list
        config_dir_name: Name of the config directory (from metadata)

    Returns:
        Path to the written config file
    """
    config_dir = get_config_dir(config_dir_name)
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / 'installation_profile.ini'

    config = ConfigParser()
    config['installation'] = {
        'profile': profile_name,
        'features': features,
        'install_date': datetime.now().isoformat(),
    }

    with open(config_file, 'w') as f:
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
    config_dir_name = metadata.get('config_dir', 'app')

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
        """
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

    args = parser.parse_args()

    # Validate mode - check all profiles and exit
    if args.validate:
        print_header(f"{app_name} Configuration Validation")

        all_valid = True

        for profile_name, profile in profiles.items():
            print_info(f"Validating profile: {profile_name}")

            # Check required fields (platform-aware)
            required_fields = ['name', 'description', 'features']
            missing_fields = [f for f in required_fields if f not in profile or not profile[f].strip()]

            # Check platform-specific requirements exist
            python_req = resolve_platform_config(profile, 'python_requirements')
            if not python_req:
                missing_fields.append('python_requirements (platform-specific)')

            platform = get_platform_name()
            if platform == 'linux':
                sys_req = resolve_platform_config(profile, 'system_requirements')
                if not sys_req:
                    missing_fields.append('system_requirements_linux')
            else:
                sys_check = resolve_platform_config(profile, 'system_check_script')
                if not sys_check:
                    missing_fields.append('system_check_script_windows (optional but recommended)')

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

            # Check script executability
            scripts_to_check = []

            scripts_pre = profile.get('pre_install_scripts', '').strip()
            if scripts_pre:
                scripts_to_check.extend([(s.strip(), 'pre_install') for s in scripts_pre.split(',') if s.strip()])

            scripts_post = profile.get('post_install_scripts', '').strip()
            if scripts_post:
                scripts_to_check.extend([(s.strip(), 'post_install') for s in scripts_post.split(',') if s.strip()])

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
        required_metadata = ['app_name', 'config_dir']
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

        # Determine which profile is installed
        config_dir = Path.home() / '.config' / config_dir_name
        config_file = config_dir / 'installation_profile.ini'

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
        # Determine profile to update
        config_dir = Path.home() / '.config' / config_dir_name
        config_file = config_dir / 'installation_profile.ini'

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

    # Validation mode - validate all profiles without installing
    if args.validate:
        print_header("Validation Mode")
        print_info(f"Validating {len(profiles)} profile(s)...")

        all_valid = True
        for profile_name, profile_config in profiles.items():
            print_info(f"Validating profile: {profile_name}")
            missing_files = validate_profile_files(profile_config)
            if missing_files:
                all_valid = False
                print_error(f"  Profile '{profile_name}' has missing files:")
                for missing_file in missing_files:
                    print(f"    - {missing_file}")
            else:
                print_success(f"  Profile '{profile_name}' is valid")

        print()
        if all_valid:
            print_success("All profiles validated successfully")
            sys.exit(0)
        else:
            print_error("Validation failed - some profiles have missing files")
            sys.exit(1)

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

        platform = get_platform_name()
        if platform == 'linux':
            sys_req = resolve_platform_config(profile, 'system_requirements')
            print(f"System packages file: {sys_req}")
        else:
            sys_check = resolve_platform_config(profile, 'system_check_script')
            print(f"System check script: {sys_check or '(none)'}")

        print(f"Features: {profile['features']}")

        # Check system packages
        _, missing_system = check_system_requirements(profile)
        if missing_system:
            if platform == 'linux':
                print(f"\nMissing system packages: {', '.join(missing_system)}")
                print(f"Would need to run: sudo apt install {' '.join(missing_system)}")
            else:
                print(f"\nMissing system requirements: {', '.join(missing_system)}")
        else:
            print("\nAll system requirements are met")

        print("\nDry run complete")
        return

    # Check system packages
    print_header("Step 1: System Requirements Check")
    installed, missing = check_system_requirements(profile)

    # Show results based on platform
    platform = get_platform_name()
    if installed:
        print_success(f"{len(installed)} system requirement(s) already installed/available")

    if missing:
        print_error(f"{len(missing)} system requirement(s) missing:")
        for item in missing:
            print(f"  - {item}")

        print()
        if platform == 'linux':
            print_info("Please install missing system packages with:")
            print(f"\n  {Colors.BOLD}sudo apt install {' '.join(missing)}{Colors.ENDC}\n")
            print_info("Then re-run this installer.")
        else:
            print_info("Please install missing requirements manually, then re-run this installer.")
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
        script_list = [s.strip() for s in scripts.split(',') if s.strip()]

        platform = get_platform_name()
        for script_path in script_list:
            if not Path(script_path).exists():
                print_warning(f"Post-install script not found: {script_path}")
                continue

            print_info(f"Running post-install script: {script_path}")

            # Prepare environment with venv activation and Quickstrap metadata
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = str(venv_path)
            pip_exe, _ = get_venv_paths(venv_path)
            path_sep = ';' if sys.platform == 'win32' else ':'
            env['PATH'] = f"{pip_exe.parent}{path_sep}{env['PATH']}"
            env['QUICKSTRAP_APP_NAME'] = app_name
            env['QUICKSTRAP_CONFIG_DIR'] = config_dir_name

            # Run script based on platform
            if platform == 'windows':
                # Run PowerShell script
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-File', script_path],
                    env=env,
                    capture_output=True,
                    text=True
                )
            else:
                # Run Bash script
                result = subprocess.run(
                    ['bash', script_path],
                    env=env,
                    capture_output=True,
                    text=True
                )

            # Display output
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            if result.returncode != 0:
                print_error(f"Post-install script failed: {script_path}")
                sys.exit(1)

        print_success("All post-install scripts completed")

    # Write installation config
    # Calculate final step number: 1 (sys) + pre_scripts + venv + python + post_scripts + config
    final_step = 4 + step_offset + (1 if scripts else 0)
    print_header(f"Step {final_step}: Configuration")
    config_path = write_installation_config(
        profile_name=profile_name,
        features=profile['features'],
        config_dir_name=config_dir_name
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
