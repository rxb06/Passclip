#compdef passcli pass_cli.py

# Zsh completion for PassCLI
# Add to fpath or source directly

_passcli_entries() {
    local pass_dir="${PASSWORD_STORE_DIR:-$HOME/.password-store}"
    if [[ -d "$pass_dir" ]]; then
        find "$pass_dir" -name '*.gpg' -not -path '*/.git/*' 2>/dev/null | \
            sed "s|^${pass_dir}/||; s|\.gpg$||" | sort
    fi
}

_passcli() {
    local -a commands
    commands=(
        'get:Show a password entry'
        'show:Show a password entry (alias)'
        'clip:Copy password to clipboard'
        'insert:Add a new entry'
        'add:Add a new entry (alias)'
        'generate:Generate a password'
        'edit:Edit an entry'
        'delete:Delete an entry'
        'browse:Fuzzy-search entries'
        'ls:List entries'
        'find:Search entries by name'
        'otp:Generate TOTP code'
        'run:Inject entry as env vars'
        'health:Password health report'
        'import:Import from CSV'
        'sync:Git pull + push'
        'gitlog:Show git history'
        'mv:Move/rename entry'
        'cp:Copy entry'
        'archive:Archive entry'
        'restore:Restore archived entry'
        'wizard:First-time setup'
        'init:Initialize password store'
        'gpg_gen:Generate GPG key'
        'gpg_list:List GPG keys'
        'config:View/set config'
        'export-vault:Export encrypted vault'
        'import-vault:Import encrypted vault'
        'shell:Start interactive shell'
    )

    if (( CURRENT == 2 )); then
        _describe 'command' commands
        return
    fi

    case "${words[2]}" in
        get|show|clip|edit|delete|otp|archive|generate|mv|cp)
            compadd $(_passcli_entries)
            ;;
        import)
            _arguments \
                '--format[CSV format]:format:(auto bitwarden lastpass 1password generic)' \
                '--dry-run[Preview without writing]' \
                '1:file:_files'
            ;;
        export-vault|import-vault)
            _files
            ;;
        config)
            compadd clip_timeout default_password_length default_mode pass_dir
            ;;
        restore)
            compadd $(_passcli_entries | grep '^archive/' | sed 's|^archive/||')
            ;;
    esac
}

_passcli "$@"
