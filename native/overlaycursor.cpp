// SPDX-License-Identifier: LGPL-2.1-or-later
#include "overlaycursor.h"
#include <cairo.h>
#include <limits>
#include "fcitx/instance.h"
#include "common.h"
#include "waylandim_public.h"
#include "waylandui.h"
#include "waylandwindow.h"
#include "wl_compositor.h"
#include "wl_region.h"
#include "zwp_input_method_v2.h"

namespace fcitx::classicui {
OverlayCursor::OverlayCursor(WaylandUI *ui)
    : ui_(ui), window_(ui->newWindow()) {
    window_->repaint().connect([this]() { render(); });
    auto clearContext = [this](Event &event) {
        if (static_cast<InputContextEvent &>(event).inputContext() == ic_.get()) {
            clear();
        }
    };
    focusOut_ = ui_->parent()->instance()->watchEvent(
        EventType::InputContextFocusOut, EventWatcherPhase::Default, clearContext);
    destroyed_ = ui_->parent()->instance()->watchEvent(
        EventType::InputContextDestroyed, EventWatcherPhase::Default, clearContext);
}

OverlayCursor::~OverlayCursor() {
    focusOut_.reset();
    destroyed_.reset();
    clear();
}

void OverlayCursor::clear() {
    ic_.unwatch();
    caret_.reset();
    popup_.reset();
    window_->hide();
    window_->destroyWindow();
}

void OverlayCursor::update(InputContext *ic) {
    if (!ic || !ic->hasFocus() || ic->frontendName() != "wayland_v2") {
        clear();
        return;
    }
    if (ic_.get() == ic && popup_) {
        // App-monitor updates can re-focus this same virtual context and copy
        // its parent's old rectangle. Kimpanel calls us before forwarding a
        // cursor/panel update, so restore the protocol caret first. Assigning
        // an unchanged rect emits no event; a reentrant update terminates here.
        if (caret_) {
            ic->setCursorRect(*caret_, 1.0);
        }
        return;
    }
    clear();
    auto *waylandim = ui_->parent()->waylandim();
    auto *im = waylandim
                   ? waylandim->call<IWaylandIMModule::getInputMethodV2>(ic)
                   : nullptr;
    auto compositor = ui_->display()->getGlobal<wayland::WlCompositor>();
    if (!im || !compositor) {
        CLASSICUI_ERROR() << "Overlay caret surface unavailable; using estimated placement";
        return;
    }
    window_->createWindow();
    if (!window_->surface()) {
        return;
    }
    window_->resize(1, 1);
    std::unique_ptr<wayland::WlRegion> empty(compositor->createRegion());
    window_->surface()->setInputRegion(empty.get());
    window_->surface()->setOpaqueRegion(empty.get());
    ic_ = ic->watch();
    popup_.reset(im->getInputPopupSurface(window_->surface()));
    if (!popup_) {
        clear();
        return;
    }
    popup_->textInputRectangle().connect([this](int32_t x, int32_t y, int32_t w, int32_t h) {
        auto *ic = ic_.get();
        if (!ic || !ic->hasFocus() || w < 0 || h < 0 ||
            int64_t(x) + w > std::numeric_limits<int>::max() ||
            int64_t(y) + h > std::numeric_limits<int>::max()) {
            return;
        }
        // Protocol coordinates are application-surface-local logical pixels,
        // NOT popup-local coordinates or physical buffer pixels.
        // Save before setCursorRect(): its change event may reenter update().
        caret_ = Rect{x, y, x + w, y + h};
        ic->setCursorRect(*caret_, 1.0);
    });
    // Set after creating the role: cursor-change handlers may reenter update().
    ic->setCursorRect(Rect{}, 1.0);
    render();
}

void OverlayCursor::render() {
    auto *ic = ic_.get();
    if (!popup_ || !ic || !ic->hasFocus()) {
        return;
    }
    if (auto *surface = window_->prerender()) {
        auto *cr = cairo_create(surface);
        cairo_set_operator(cr, CAIRO_OPERATOR_SOURCE);
        cairo_set_source_rgba(cr, 0, 0, 0, 0);
        cairo_paint(cr);
        cairo_destroy(cr);
        window_->render();
    }
}
} // namespace fcitx::classicui
