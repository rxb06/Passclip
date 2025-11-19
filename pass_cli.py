#!/usr/bin/env python3

import cmd
import subprocess
import sys
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from typing import List, Tuple

# Initialize Rich Console
console = Console()

# Check for CLI mode activation
CLI_MODE = "--enable-cli-mode" in sys.argv


def run_command(command_parts: List[str], interactive: bool = False) -> Tuple[str, str]:
    """
    Executes a shell command securely using a list of command parts.

    Args:
        command_parts: The command and its arguments as a list of strings (e.g., ["pass", "show"]).
        interactive: If True, runs the command directly without capturing output.

    Returns:
        A tuple of (stdout, stderr).
    """
    try:
        # Avoiding shell=True for security reasons (shell injection prevention)
        if interactive:
            # For interactive commands (like gpg or pass edit), we let them run directly
            subprocess.run(command_parts)
            return "", ""
        else:
            result = subprocess.run(
                command_parts,
                text=True,
                capture_output=True,
                check=False  # Do not raise an exception for non-zero exit codes immediately
            )
            return result.stdout.strip(), result.stderr.strip()

    except FileNotFoundError:
        return "", f"Error: Command not found. Is {' '.join(command_parts)} installed and in your PATH?"
    except Exception as e:
        return "", str(e)


def get_gpg_keys() -> List[Tuple[str, str]]:
    """Retrieves GPG key IDs and user info."""
    # Use the secure list format
    command = ["gpg", "--list-keys", "--keyid-format", "LONG"]
    out, err = run_command(command)
    keys = []

    if not err:
        for line in out.splitlines():
            # Look for lines starting with 'pub' (public key)
            if line.startswith("pub"):
                try:
                    parts = line.split()
                    # The key info is typically the second part, e.g., 'rsa4096/987654321ABCDEF0'
                    key_info = parts[1]
                    # Extract the Key ID (the part after the '/')
                    key_id = key_info.split("/")[1] if "/" in key_info else key_info
                    # User info starts from the 3rd part onwards
                    user_info = " ".join(parts[2:])
                    keys.append((key_id, user_info))
                except IndexError:
                    # Skip malformed lines
                    continue
    return keys


class PassCLI(cmd.Cmd):
    prompt = "passcli> "

    def __init__(self):
        super().__init__()
        # 'cli' mode uses the prompt, 'standard' mode uses the menu
        self.mode = "cli" if CLI_MODE else "standard"
        self.password_store_initialized = False  # Simple state tracking

    def preloop(self):
        console.print(
            "\nWelcome to [bold cyan]PassCLI[/bold cyan] – the password manager wizard for pros and newbies alike!\n"
            "Type 'help' or '?' to list commands. When in doubt, just ask for help.\n",
            style="bold green"
        )
        # Check for password store initialization status
        out, _ = run_command(["pass", "ls"])
        if "Password store not initialized" not in out:
            self.password_store_initialized = True
            console.print("[green]Password store detected.[/green]")
        else:
            console.print("[yellow]Password store not initialized. Use [bold]pass_init[/bold] to begin.[/yellow]")

        if self.mode == "standard":
            self.do_menu("")

    # --- Menu and Mode Handling ---

    def print_main_menu(self):
        table = Table(title="Main Menu", show_header=True, header_style="bold magenta")
        table.add_column("Option", style="bold cyan")
        table.add_column("Category / Description", style="white")
        table.add_row("1", "GPG Operations [gpg_gen, gpg_list]")
        table.add_row("2", "Password Management [pass_init, pass_insert, pass_edit...]")
        table.add_row("3", "Deletion & Archiving [pass_delete, pass_archive, pass_restore]")
        table.add_row("4", "Enter CLI Mode [activates passcli prompt]")
        table.add_row("5", "Exit")
        console.print(table)

    def handle_main_menu_choice(self, choice):
        if choice == 1:
            console.print("\n[bold cyan]GPG Operations[/bold cyan]")
            console.print("1. gpg_gen - Generate a new GPG key (interactive)")
            console.print("2. gpg_list - List all available GPG keys")
            console.print("3. Escape to Main Menu")
            console.print("4. Exit PassCLI")
            sub_choice = IntPrompt.ask("Enter the number of your choice", default=1)
            if sub_choice == 1:
                self.do_gpg_gen("")
            elif sub_choice == 2:
                self.do_gpg_list("")
            elif sub_choice == 3:
                return self.do_menu("")
            elif sub_choice == 4:
                return self.do_quit("")
            else:
                console.print("[red]Invalid GPG option.[/red]")

        elif choice == 2:
            self.password_management_menu()

        elif choice == 3:
            console.print("\n[bold cyan]Password Deletion & Archiving[/bold cyan]")
            console.print("1. pass_delete  - Delete a password entry")
            console.print("2. pass_archive - Archive a password entry (move to archive/ folder)")
            console.print("3. pass_restore - Restore an archived password entry")
            console.print("4. Escape to Main Menu")
            console.print("5. Exit PassCLI")
            sub_choice = IntPrompt.ask("Enter the number of your choice", default=1)
            if sub_choice == 1:
                self.do_pass_delete("")
            elif sub_choice == 2:
                self.do_pass_archive("")
            elif sub_choice == 3:
                self.do_pass_restore("")
            elif sub_choice == 4:
                return self.do_menu("")
            elif sub_choice == 5:
                return self.do_quit("")
            else:
                console.print("[red]Invalid option.[/red]")

        elif choice == 4:
            self.mode = "cli"
            console.print("[green]Switched to CLI mode. Entering passcli prompt...[/green]")
            console.print("[yellow] Type 'menu' to return, or 'help' to list commands.[/yellow]")
        elif choice == 5:
            self.do_quit("")
        else:
            console.print("[red]Invalid menu option.[/red]")

    def password_management_menu(self):
        console.print("\n[bold cyan]Password Management[/bold cyan]")
        console.print("1. pass_init     - Initialize the password store")
        console.print("2. pass_generate - Generate a new password")
        console.print("3. pass_insert   - Insert a new password")
        console.print("4. pass_get      - Retrieve a password")
        console.print("5. pass_edit     - Edit a password entry")
        console.print("6. pass_show     - Show password details (tree view)")
        console.print("7. pass_find     - Find password entries (search)")
        console.print("8. pass_mv       - Move or rename a password entry")
        console.print("9. pass_cp       - Copy a password entry")
        console.print("10. pass_archive - Archive a password")
        console.print("11. pass_restore - Restore an archived password")
        console.print("12. Escape to Main Menu")
        console.print("13. Exit PassCLI")

        sub_choice = IntPrompt.ask("Enter the number of your choice", default=1)

        if sub_choice == 1:
            self.do_pass_init("")
        elif sub_choice == 2:
            self.do_pass_generate("")
        elif sub_choice == 3:
            self.do_pass_insert("")
        elif sub_choice == 4:
            self.do_pass_get("")
        elif sub_choice == 5:
            self.do_pass_edit("")
        elif sub_choice == 6:
            self.do_pass_show("")
        elif sub_choice == 7:
            self.do_pass_find("")
        elif sub_choice == 8:
            self.do_pass_mv("")
        elif sub_choice == 9:
            self.do_pass_cp("")
        elif sub_choice == 10:
            self.do_pass_archive("")
        elif sub_choice == 11:
            self.do_pass_restore("")
        elif sub_choice == 12:
            return self.do_menu("")
        elif sub_choice == 13:
            return self.do_quit("")
        else:
            console.print("[red]Invalid option.[/red]")
            self.password_management_menu()

    def do_menu(self, arg):
        self.print_main_menu()
        try:
            choice = IntPrompt.ask("Enter the menu option number")
            return self.handle_main_menu_choice(choice)
        except KeyboardInterrupt:
            console.print("\n[yellow]Menu selection cancelled.[/yellow]")
            if self.mode == "standard":
                self.print_main_menu()

    # --- GPG Commands ---

    def do_gpg_gen(self, arg):
        console.print("[yellow]Get ready to summon a new GPG key![/yellow]")
        console.print("For top-security, we recommend RSA 4096 with no expiry.")
        console.print("[dim]Launching GPG key generation (it will be interactive)...[/dim]")
        # Secure command with args list
        run_command(["gpg", "--full-generate-key"], interactive=True)
        console.print("[green]GPG key generation complete.[/green]\n")

    def do_gpg_list(self, arg):
        keys = get_gpg_keys()
        if not keys:
            console.print("[red]No GPG keys found.[/red]")
            return
        table = Table(title="GPG Keys")
        table.add_column("No.", style="bold")
        table.add_column("Key ID", style="cyan")
        table.add_column("User Info", style="magenta")
        for idx, (key_id, user_info) in enumerate(keys, start=1):
            table.add_row(str(idx), key_id, user_info)
        console.print(table)

    def do_pass_init(self, arg):
        keys = get_gpg_keys()
        if not keys:
            console.print("[red]No GPG keys found. You need to generate one first.[/red]")
            confirm = Prompt.ask("Generate a new GPG key now? (yes/no)", default="yes")
            if confirm.lower() == "yes":
                self.do_gpg_gen("")
                keys = get_gpg_keys()
                if not keys:
                    console.print("[red]Still no keys found. Something went wrong.[/red]")
                    return
            else:
                return

        table = Table(title="Choose a GPG key for pass init")
        table.add_column("No.", style="bold")
        table.add_column("Key ID", style="cyan")
        table.add_column("User Info", style="magenta")
        for idx, (key_id, user_info) in enumerate(keys, start=1):
            table.add_row(str(idx), key_id, user_info)
        console.print(table)

        choice = IntPrompt.ask("Enter the number of the key to use", default=1)

        if 1 <= choice <= len(keys):
            key_id = keys[choice - 1][0]
            console.print(f"[yellow]Initializing password store with key:[/yellow] [cyan]{key_id}[/cyan]")

            # Secure command with args list
            out, err = run_command(["pass", "init", key_id])

            if err and "already initialized" not in err:
                console.print(f"[red]Error:[/red] {err}")
            else:
                self.password_store_initialized = True
                console.print("[green]Password store initialized successfully![/green]")
        else:
            console.print("[red]Invalid selection.[/red]")

        if self.mode == "standard":
            self.password_management_menu()

    # --- Password Management Commands ---

    def do_pass_insert(self, arg):
        entry = arg.strip() or Prompt.ask("Enter the name for the new password entry")
        console.print(f"[yellow]Inserting password entry:[/yellow] [cyan]{entry}[/cyan]")

        console.print("Enter your password (multiline supported). Finish input with Ctrl-D (or Ctrl-Z on Windows).")
        try:
            lines = sys.stdin.read()
        except KeyboardInterrupt:
            console.print("[red]Insertion cancelled.[/red]")
            return

        # Secure command with args list and PIPE for input
        process = subprocess.Popen(
            ["pass", "insert", "-m", entry],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(lines)

        if process.returncode == 0:
            console.print("[green]Password entry inserted successfully![/green]")
        else:
            console.print("[red]Failed to insert password entry. Check if GPG is initialized.[/red]")

        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_get(self, arg):
        entry = arg.strip() or Prompt.ask("Enter the name of the password entry to retrieve")
        # Secure command with args list
        out, err = run_command(["pass", entry])

        if err or not out:
            console.print(f"[red]Error retrieving entry:[/red] {err}")
        else:
            console.print(f"[green]Password entry for {entry}:[/green]\n{out}")

        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_delete(self, arg):
        entry = arg.strip() or Prompt.ask("Enter the name of the password entry to delete")
        confirm = Prompt.ask(f"Are you sure you want to delete '{entry}'? Type YES to confirm", default="NO")

        if confirm != "YES":
            console.print("[yellow]Deletion cancelled.[/yellow]")
            return

        # Secure command with args list
        out, err = run_command(["pass", "rm", "-r", "-f", entry])

        if err:
            console.print(f"[red]Error deleting entry:[/red] {err}")
        else:
            console.print(f"[green]Password entry '{entry}' deleted successfully.[/green]")

    def do_pass_generate(self, arg):
        """
        Generate a password for a new or existing entry.
        Usage: pass_generate <entry_name> [length]
        """
        args = arg.split()
        if not args:
            entry = Prompt.ask("Enter the name for the password entry")
            length = IntPrompt.ask("Enter the desired password length", default=18)
        else:
            entry = args[0]
            try:
                length = int(args[1]) if len(args) > 1 else 18
            except ValueError:
                console.print("[red]Error: Password length must be a number.[/red]")
                if self.mode == "standard":
                    self.password_management_menu()
                return

        console.print(f"[yellow]Generating a {length}-character password for entry:[/yellow] [cyan]{entry}[/cyan]")

        command = ["pass", "generate", entry, str(length)]
        out, err = run_command(command)

        if err:
            # Enhanced Error Handling for GPG Key Failure
            if "No public key" in err or "encryption failed" in err:
                console.print(
                    "\n[bold red]Error generating password: GPG Public Key Issue![/bold red]")
                console.print(
                    "[yellow]It looks like the password store is not initialized or the specified "
                    "GPG key is not available or correct.[/yellow]")
                console.print(
                    "[cyan]Please ensure you have initialized your password store:[/cyan]")
                console.print("  1. Use [bold]gpg_gen[/bold] to create a key.")
                console.print("  2. Use [bold]pass_init[/bold] to initialize the store with a key.")
            else:
                console.print(f"[red]Error generating password:[/red] {err}")
        else:
            console.print("[green]Password generated successfully![/green]")

        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_edit(self, arg):
        entry = arg.strip() or Prompt.ask("Enter the name of the password entry to edit")
        console.print(f"[yellow]Editing password entry:[/yellow] [cyan]{entry}[/cyan]")
        run_command(["pass", "edit", entry], interactive=True)
        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_find(self, arg):
        """List password entries that match the provided search term(s)."""
        search_terms = arg.strip()
        if not search_terms:
            search_terms = Prompt.ask("Enter search term(s) for password entries")

        out, err = run_command(["pass", "find", search_terms])

        if err:
            console.print(f"[red]Error finding entries:[/red] {err}")
        else:
            console.print(f"[green]Search results for '{search_terms}':[/green]\n{out}")

        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_cp(self, arg):
        """Copy a password entry. Usage: pass_cp <old-path> <new-path>"""
        parts = arg.split()
        if len(parts) < 2:
            old_path = Prompt.ask("Enter the source password entry path")
            new_path = Prompt.ask("Enter the destination password entry path")
        else:
            old_path, new_path = parts[0], parts[1]

        out, err = run_command(["pass", "cp", old_path, new_path])

        if err:
            console.print(f"[red]Error copying entry:[/red] {err}")
        else:
            console.print(f"[green]Copied password entry from '{old_path}' to '{new_path}' successfully.[/green]")

        Prompt.ask("Press Enter to return to the Password Management menu")
        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_mv(self, arg):
        """Move or rename a password entry. Usage: pass_mv <old-path> <new-path>"""
        parts = arg.split()
        if len(parts) < 2:
            old_path = Prompt.ask("Enter the old password entry path")
            new_path = Prompt.ask("Enter the new password entry path")
        else:
            old_path, new_path = parts[0], parts[1]

        out, err = run_command(["pass", "mv", old_path, new_path])

        if err:
            console.print(f"[red]Error moving entry:[/red] {err}")
        else:
            console.print(f"[green]Moved password entry from '{old_path}' to '{new_path}' successfully.[/green]")

        Prompt.ask("Press Enter to return to the Password Management menu")
        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_show(self, arg):
        """Show the tree view of stored entries (pass ls)."""
        out, err = run_command(["pass", "ls"], interactive=False)

        if err or "Password store not initialized" in out:
            console.print(f"[red]Error listing password entries:[/red] {err or 'Password store not initialized.'}")
        else:
            console.print("[green]Password Store Contents:[/green]")
            console.print(out)

        if self.mode == "standard":
            self.password_management_menu()

    # --- Archive & Restore Commands ---

    def do_pass_archive(self, arg):
        """
        Archives a password entry by moving it to an 'archive' subfolder.
        Usage: pass_archive <entry_name>
        """
        entry = arg.strip() or Prompt.ask("Enter the name of the password entry to archive")
        archive_path = f"archive/{entry}"

        console.print(
            f"[yellow]Archiving entry:[/yellow] [cyan]{entry}[/cyan] -> [magenta]{archive_path}[/magenta]")

        # Secure command with args list: pass mv <entry> <archive_path>
        out, err = run_command(["pass", "mv", entry, archive_path])

        if err:
            console.print(f"[red]Error archiving entry:[/red] {err}")
        else:
            console.print(f"[green]Password entry '{entry}' successfully archived.[/green]")

        if self.mode == "standard":
            self.password_management_menu()

    def do_pass_restore(self, arg):
        """
        Restores an archived password entry (removes it from the 'archive/' subfolder).
        Usage: pass_restore <archived_entry_name>
        """
        # Ensure input is gathered correctly, preventing empty path causing 'pass mv' Usage error (Bug #3)
        archived_entry = arg.strip() or Prompt.ask(
            "Enter the name of the archived password to revert (e.g., website/login)")

        # We assume the archived entry is inside the 'archive' folder
        archived_full_path = f"archive/{archived_entry}"

        console.print(f"\n[yellow]Restoring archived password:[/yellow] [cyan]{archived_full_path}[/cyan]")

        # User prompt to select restore location
        console.print("1. Root of password store")
        console.print("2. Specify a subfolder")

        # Handle the selection, ensuring it's a valid integer (Bug #2)
        try:
            sub_choice = IntPrompt.ask("Restore archived password to (1 or 2)", default=1)
        except KeyboardInterrupt:
            console.print("[yellow]Restoration cancelled.[/yellow]")
            return

        destination_path = archived_entry  # Default destination (restores to original name in root if 1 is chosen)

        if sub_choice == 2:
            # Bug fix related: The original error came from trying to move an entry with an empty/invalid new-path.
            new_subfolder = Prompt.ask("Enter the destination subfolder (e.g., personal/old_logins)")
            destination_path = new_subfolder.strip()
            if not destination_path:
                console.print("[red]Destination subfolder cannot be empty. Restoration cancelled.[/red]")
                if self.mode == "standard":
                    self.password_management_menu()
                return

        # Secure command with args list: pass mv <archived_full_path> <destination_path>
        out, err = run_command(["pass", "mv", archived_full_path, destination_path])

        if err:
            # Displaying the pass mv error clearly
            console.print(f"[red]Error reverting archived password:[/red] {err}")
            console.print(
                "[yellow]Ensure the entry exists in the 'archive/' folder and the destination is valid.[/yellow]")
        else:
            console.print(f"[green]Password entry restored to '{destination_path}' successfully.[/green]")

        if self.mode == "standard":
            self.password_management_menu()

    def do_archive(self, arg):
        # Alias to the real function
        self.do_pass_archive(arg)

    # --- Utility Commands ---

    def do_list_all(self, arg):
        table = Table(title="Command Manual", show_header=True, header_style="bold magenta")
        table.add_column("Command", style="cyan")
        table.add_column("Description", style="white")
        table.add_row("gpg_gen", "Generate a new GPG key with RSA 4096 (interactive)")
        table.add_row("gpg_list", "List all available GPG keys")
        table.add_row("pass_init", "Initialize the pass store with a GPG key (guided selection)")
        table.add_row("pass_generate", "Generate a password for an entry (with GPG error handling)")
        table.add_row("pass_insert", "Insert a new password entry (multiline supported)")
        table.add_row("pass_get", "Retrieve a password entry")
        table.add_row("pass_edit", "Edit a password entry using your editor")
        table.add_row("pass_show", "Show password entries (list/ls)")
        table.add_row("pass_find", "Find password entries matching search term(s)")
        table.add_row("pass_delete", "Delete a password entry")
        table.add_row("pass_mv", "Move/rename a password entry")
        table.add_row("pass_cp", "Copy a password entry")
        table.add_row("pass_archive", "Archive a password entry (moves to archive/ folder)")
        table.add_row("pass_restore", "Restore an archived password entry (removes from archive/ folder)")
        table.add_row("git", "Git operations (placeholder)")
        table.add_row("menu", "Show the main nested menu with numbered options")
        table.add_row("default_mode", "Switch between CLI and standard modes")
        table.add_row("list_all", "Display this command manual")
        table.add_row("quit/exit", "Exit PassCLI with style")
        console.print(table)

    def do_default_mode(self, arg):
        """Switch the mode of operation to 'cli' (professional) or 'standard' (menu)."""
        arg = arg.strip().lower()
        if arg in ["professional", "cli"]:
            self.mode = "cli"
            console.print("[green]Switched to CLI mode ('professional').[/green]")
        elif arg in ["standard", "menu"]:
            self.mode = "standard"
            console.print("[green]Switched to standard mode (menu).[/green]")
            self.print_main_menu()
        else:
            console.print("[red]Invalid mode. Use 'cli' or 'standard'.[/red]")

    def do_quit(self, arg):
        console.print(
            "[bold red]PassCLI exiting. If your password’s on a sticky note, I’m silently shaking my head.[/bold red]")
        sys.exit(0)

    def do_exit(self, arg):
        return self.do_quit(arg)

    def do_git(self, arg):
        console.print("[yellow]Git operations are a placeholder at this time.[/yellow]")

    def default(self, line):
        if self.mode == "standard" and line.strip().isdigit():
            try:
                choice = int(line.strip())
                self.handle_main_menu_choice(choice)
            except ValueError:
                console.print(f"[red]Unknown command:[/red] {line}. Type 'help' to see available commands.")
        else:
            console.print(f"[red]Unknown command:[/red] {line}. Type 'help' to see available commands.")

    def emptyline(self):
        pass

4
if __name__ == '__main__':
    try:
        PassCLI().cmdloop()
    except KeyboardInterrupt:
        console.print(
            "\n[bold red]Interrupted. PassCLI signing off. If your password is '1234', I am judging you.[/bold red]")
