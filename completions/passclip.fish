# Fish completion for Passclip
# Copy to ~/.config/fish/completions/passclip.fish

function __passclip_entries
    set -l pass_dir $PASSWORD_STORE_DIR
    if test -z "$pass_dir"
        set pass_dir "$HOME/.password-store"
    end
    if test -d "$pass_dir"
        find "$pass_dir" -name '*.gpg' -not -path '*/.git/*' 2>/dev/null | \
            sed "s|^$pass_dir/||; s|\.gpg\$||" | sort
    end
end

# Subcommands
complete -c passclip -f -n '__fish_use_subcommand' -a get -d 'Show a password entry'
complete -c passclip -f -n '__fish_use_subcommand' -a show -d 'Show a password entry'
complete -c passclip -f -n '__fish_use_subcommand' -a clip -d 'Copy password to clipboard'
complete -c passclip -f -n '__fish_use_subcommand' -a insert -d 'Add a new entry'
complete -c passclip -f -n '__fish_use_subcommand' -a add -d 'Add a new entry'
complete -c passclip -f -n '__fish_use_subcommand' -a generate -d 'Generate a password'
complete -c passclip -f -n '__fish_use_subcommand' -a edit -d 'Edit an entry'
complete -c passclip -f -n '__fish_use_subcommand' -a delete -d 'Delete an entry'
complete -c passclip -f -n '__fish_use_subcommand' -a browse -d 'Fuzzy-search entries'
complete -c passclip -f -n '__fish_use_subcommand' -a ls -d 'List entries'
complete -c passclip -f -n '__fish_use_subcommand' -a find -d 'Search entries by name'
complete -c passclip -f -n '__fish_use_subcommand' -a otp -d 'Generate TOTP code'
complete -c passclip -f -n '__fish_use_subcommand' -a run -d 'Inject entry as env vars'
complete -c passclip -f -n '__fish_use_subcommand' -a health -d 'Password health report'
complete -c passclip -f -n '__fish_use_subcommand' -a import -d 'Import from CSV'
complete -c passclip -f -n '__fish_use_subcommand' -a sync -d 'Git pull + push'
complete -c passclip -f -n '__fish_use_subcommand' -a gitlog -d 'Show git history'
complete -c passclip -f -n '__fish_use_subcommand' -a mv -d 'Move/rename entry'
complete -c passclip -f -n '__fish_use_subcommand' -a cp -d 'Copy entry'
complete -c passclip -f -n '__fish_use_subcommand' -a archive -d 'Archive entry'
complete -c passclip -f -n '__fish_use_subcommand' -a restore -d 'Restore archived entry'
complete -c passclip -f -n '__fish_use_subcommand' -a wizard -d 'First-time setup'
complete -c passclip -f -n '__fish_use_subcommand' -a init -d 'Initialize password store'
complete -c passclip -f -n '__fish_use_subcommand' -a config -d 'View/set config'
complete -c passclip -f -n '__fish_use_subcommand' -a export-vault -d 'Export encrypted vault'
complete -c passclip -f -n '__fish_use_subcommand' -a import-vault -d 'Import encrypted vault'

# Entry completions for commands that accept entries
for cmd in get show clip edit delete otp archive generate mv cp
    complete -c passclip -f -n "__fish_seen_subcommand_from $cmd" -a '(__passclip_entries)'
end

# Import flags
complete -c passclip -f -n '__fish_seen_subcommand_from import' -l format -a 'auto bitwarden lastpass 1password generic'
complete -c passclip -f -n '__fish_seen_subcommand_from import' -l dry-run -d 'Preview without writing'

# Config keys
complete -c passclip -f -n '__fish_seen_subcommand_from config' -a 'clip_timeout default_password_length default_mode pass_dir'
