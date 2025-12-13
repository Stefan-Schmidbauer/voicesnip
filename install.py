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
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


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


def check_system_packages(package_file: str) -> Tuple[List[str], List[str]]:
    """Check which system packages are installed.

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

    print_info(f"Checking {len(packages)} system packages...")

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
        pip_exe = venv_path / 'bin' / 'pip'
        python_exe = venv_path / 'bin' / 'python'

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


def install_python_packages(venv_path: Path, requirements_file: str) -> bool:
    """Install Python packages from requirements file.

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

    # Verify pip executable exists
    if not pip_exe.exists():
        print_error(f"pip not found at {pip_exe}")
        print_error("Virtual environment may be corrupted")
        print_info("Try running with --rebuild-venv flag to recreate it")
        return False

    print_info(f"Installing Python packages from {requirements_file}...")
    print_info("This may take several minutes...")

    # Run pip with progress
    result = subprocess.run(
        [str(pip_exe), 'install', '-r', requirements_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # Write full output to log
    with open('install.log', 'a') as f:
        f.write(f"\n{'=' * 70}\n")
        f.write(f"Installation log: {datetime.now().isoformat()}\n")
        f.write(f"Requirements: {requirements_file}\n")
        f.write(f"{'=' * 70}\n")
        f.write(result.stdout)

    if result.returncode != 0:
        print_error("Failed to install Python packages")
        print_info("Check install.log for details")
        return False

    print_success("Python packages installed successfully")
    return True


def validate_profile_files(profile: Dict) -> List[str]:
    """Validate that all files referenced in the profile exist.

    Args:
        profile: Profile configuration dict

    Returns:
        List of missing files with their context (empty if all files exist)
    """
    missing = []

    # Check python requirements
    if 'python_requirements' in profile:
        req_file = profile['python_requirements']
        if not Path(req_file).exists():
            missing.append(f"{req_file} (python_requirements)")

    # Check system requirements
    if 'system_requirements' in profile:
        req_file = profile['system_requirements']
        if not Path(req_file).exists():
            missing.append(f"{req_file} (system_requirements)")

    # Check post_install_scripts
    scripts = profile.get('post_install_scripts', '').strip()
    if scripts:
        script_list = [s.strip() for s in scripts.split(',') if s.strip()]
        for script_path in script_list:
            if not Path(script_path).exists():
                missing.append(f"{script_path} (post_install_scripts)")

    # Check pre_install_scripts
    scripts_pre = profile.get('pre_install_scripts', '').strip()
    if scripts_pre:
        script_list = [s.strip() for s in scripts_pre.split(',') if s.strip()]
        for script_path in script_list:
            if not Path(script_path).exists():
                missing.append(f"{script_path} (pre_install_scripts)")

    return missing


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

        result = subprocess.run(
            ['bash', script_path],
            capture_output=True,
            text=True
        )

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
    """Write installation config to ~/.config/{config_dir_name}/

    Args:
        profile_name: Name of installed profile
        features: Comma-separated feature list
        config_dir_name: Name of the config directory (from metadata)

    Returns:
        Path to the written config file
    """
    config_dir = Path.home() / '.config' / config_dir_name
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

    args = parser.parse_args()

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
        print(f"System packages file: {profile['system_requirements']}")
        print(f"Python packages file: {profile['python_requirements']}")
        print(f"Features: {profile['features']}")

        # Check system packages
        _, missing_system = check_system_packages(profile['system_requirements'])
        if missing_system:
            print(f"\nMissing system packages: {', '.join(missing_system)}")
            print(f"Would need to run: sudo apt install {' '.join(missing_system)}")

        print("\nDry run complete")
        return

    # Check system packages
    print_header("Step 1: System Package Check")
    installed, missing = check_system_packages(profile['system_requirements'])

    print_success(f"{len(installed)} system packages already installed")

    if missing:
        print_error(f"{len(missing)} system packages missing:")
        for pkg in missing:
            print(f"  - {pkg}")

        print()
        print_info("Please install missing system packages with:")
        print(f"\n  {Colors.BOLD}sudo apt install {' '.join(missing)}{Colors.ENDC}\n")
        print_info("Then re-run this installer.")
        sys.exit(1)

    print_success("All system packages are installed")

    # Run pre-install scripts if defined
    scripts_pre = profile.get('pre_install_scripts', '').strip()
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

    # Install Python packages
    print_header(f"Step {3 + step_offset}: Python Package Installation")
    success = install_python_packages(venv_path, profile['python_requirements'])

    if not success:
        print_error("Installation failed")
        sys.exit(1)

    # Run post-install scripts if defined
    scripts = profile.get('post_install_scripts', '').strip()
    if scripts:
        print_header(f"Step {4 + step_offset}: Post-Installation Scripts")
        script_list = [s.strip() for s in scripts.split(',') if s.strip()]

        for script_path in script_list:
            if not Path(script_path).exists():
                print_warning(f"Post-install script not found: {script_path}")
                continue

            print_info(f"Running post-install script: {script_path}")

            # Prepare environment with venv activation and Quickstrap metadata
            env = os.environ.copy()
            env['VIRTUAL_ENV'] = str(venv_path)
            env['PATH'] = f"{venv_path / 'bin'}:{env['PATH']}"
            env['QUICKSTRAP_APP_NAME'] = app_name
            env['QUICKSTRAP_CONFIG_DIR'] = config_dir_name

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

    # Show after_install message if provided
    if 'after_install' in metadata:
        print_info(metadata['after_install'])
        print()

    print_info("Installation configuration:")
    print(f"  {config_path}")
    print()


if __name__ == '__main__':
    main()
