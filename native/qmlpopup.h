// SPDX-License-Identifier: LGPL-2.1-or-later
#ifndef FCITX_CLASSICUI_QMLPOPUP_H
#define FCITX_CLASSICUI_QMLPOPUP_H

#include <deque>
#include <functional>
#include <memory>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
#include "fcitx-utils/event.h"

namespace fcitx::classicui {

// Qt Quick runs in a separate process. Only classicui owns Wayland surfaces.
class QmlPopup {
public:
    static constexpr size_t SlotSize = 32 * 1024 * 1024;
    struct Frame {
        int width = 0, height = 0, stride = 0;
        int logicalWidth = 0, logicalHeight = 0;
        uint64_t epoch = 0;
        std::vector<unsigned char> pixels;
    };
    using Callback = std::function<void(const nlohmann::json &)>;
    QmlPopup(EventLoop &loop, Callback callback);
    ~QmlPopup();
    bool available() const { return socket_ >= 0; }
    bool send(const nlohmann::json &message);
    const Frame &frame() const { return frame_; }
    void clearFrame() { frame_ = {}; }

private:
    void fail();
    void flush();
    void receive();
    int socket_ = -1;
    int memoryFd_ = -1;
    void *memory_ = nullptr;
    std::unique_ptr<EventSourceIO> io_;
    std::deque<std::string> pending_;
    Callback callback_;
    Frame frame_;
};
} // namespace fcitx::classicui
#endif
