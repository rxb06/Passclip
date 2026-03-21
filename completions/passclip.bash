# Bash completion for Passclip
# Source this file: source completions/passclip.bash

_passclip_entries() {
    local pass_dir="${PASSWORD_STORE_DIR:-$HOME/.password-store}"
    if [ -d "$pass_dir" ]; then
        find "$pass_dir" -name '*.gpg' -not -path '*/.git/*' 2>/dev/null | \
            sed "s|^${pass_dir}/||; s|\.gpg$||" | sort
    fi
}

_passclip() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    commands="get show clip insert add generate edit delete browse ls find
              otp run health import sync gitlog mv cp archive restore
              wizard init gpg_gen gpg_list config export-vault import-vault
              shell help quit exit"

    if [ "$COMP_CWORD" -eq 1 ]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return 0
    fi

    case "${COMP_WORDS[1]}" in
        get|show|clip|edit|delete|otp|archive|generate)
            COMPREPLY=( $(compgen -W "$(_passclip_entries)" -- "$cur") )
            ;;
        import)
            if [[ "$cur" == --* ]]; then
                COMPREPLY=( $(compgen -W "--format --dry-run" -- "$cur") )
            elif [[ "$prev" == "--format" || "$prev" == "-f" ]]; then
                COMPREPLY=( $(compgen -W "auto bitwarden lastpass 1password generic" -- "$cur") )
            else
                COMPREPLY=( $(compgen -f -- "$cur") )
            fi
            ;;
        config)
            COMPREPLY=( $(compgen -W "clip_timeout default_password_length default_mode pass_dir" -- "$cur") )
            ;;
        export-vault|import-vault)
            COMPREPLY=( $(compgen -f -- "$cur") )
            ;;
        mv|cp)
            COMPREPLY=( $(compgen -W "$(_passclip_entries)" -- "$cur") )
            ;;
        restore)
            local entries=$(_passclip_entries | grep '^archive/' | sed 's|^archive/||')
            COMPREPLY=( $(compgen -W "$entries" -- "$cur") )
            ;;
    esac
    return 0
}

complete -F _passclip passclip
complete -F _passclip passclip.py
