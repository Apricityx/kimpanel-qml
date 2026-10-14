#!/usr/bin/env sh
# Optional per-application GTK/Qt DBus routing; preserve native defaults globally.
exec env GTK_IM_MODULE=fcitx QT_IM_MODULE=fcitx XMODIFIERS=@im=fcitx \
    SDL_IM_MODULE=fcitx "$@"
