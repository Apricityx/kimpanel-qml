// SPDX-License-Identifier: LGPL-2.1-or-later
#ifndef KIMPANEL_OVERLAYCURSOR_H
#define KIMPANEL_OVERLAYCURSOR_H

#include <memory>
#include <optional>
#include "fcitx-utils/handlertable.h"
#include "fcitx-utils/trackableobject.h"
#include "fcitx/inputcontext.h"
#include "fcitx/instance.h"
#include "zwp_input_popup_surface_v2.h"

namespace fcitx::classicui {
class WaylandUI;
class WaylandWindow;

// A transparent, input-empty 1x1 surface receives the native caret rectangle.
// It never draws candidates: all visible motion happens in the stable overlay.
class OverlayCursor {
public:
    explicit OverlayCursor(WaylandUI *ui);
    ~OverlayCursor();
    void update(InputContext *ic);

private:
    void clear();
    void render();
    WaylandUI *ui_;
    std::unique_ptr<WaylandWindow> window_;
    TrackableObjectReference<InputContext> ic_;
    // Only text_input_rectangle events may change the native caret. fcitx's
    // virtual-context focus refresh can otherwise copy a stale parent rect.
    std::optional<Rect> caret_;
    std::unique_ptr<wayland::ZwpInputPopupSurfaceV2> popup_;
    std::unique_ptr<HandlerTableEntryBase> focusOut_;
    std::unique_ptr<HandlerTableEntryBase> destroyed_;
};
} // namespace fcitx::classicui
#endif
