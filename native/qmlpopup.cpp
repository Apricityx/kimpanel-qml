// SPDX-License-Identifier: LGPL-2.1-or-later
#include "qmlpopup.h"
#include <cerrno>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <spawn.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <unistd.h>
#include "common.h"

extern char **environ;

namespace fcitx::classicui {
QmlPopup::QmlPopup(EventLoop &loop, Callback callback)
    : callback_(std::move(callback)) {
    const char *renderer = std::getenv("FCITX_QML_POPUP_RENDERER");
    if (!renderer || !*renderer) {
        return;
    }
    int sockets[2];
    if (socketpair(AF_UNIX, SOCK_SEQPACKET | SOCK_CLOEXEC, 0, sockets)) {
        return;
    }
    socket_ = sockets[0];
    memoryFd_ = memfd_create("fcitx-qml-popup", MFD_CLOEXEC);
    if (memoryFd_ < 0 || ftruncate(memoryFd_, SlotSize * 2)) {
        close(sockets[1]);
        fail();
        return;
    }
    memory_ = mmap(nullptr, SlotSize * 2, PROT_READ, MAP_SHARED, memoryFd_, 0);
    if (memory_ == MAP_FAILED) {
        memory_ = nullptr;
        close(sockets[1]);
        fail();
        return;
    }
    // High fixed child descriptors avoid collisions with the socketpair/memfd.
    posix_spawn_file_actions_t actions;
    posix_spawn_file_actions_init(&actions);
    posix_spawn_file_actions_adddup2(&actions, sockets[1], 198);
    posix_spawn_file_actions_adddup2(&actions, memoryFd_, 199);
    char *argv[] = {const_cast<char *>(renderer),
                    const_cast<char *>("--socket-fd"), const_cast<char *>("198"),
                    const_cast<char *>("--memory-fd"), const_cast<char *>("199"),
                    nullptr};
    pid_t child;
    const int error = posix_spawn(&child, renderer, &actions, nullptr, argv, environ);
    posix_spawn_file_actions_destroy(&actions);
    close(sockets[1]);
    if (error) {
        CLASSICUI_ERROR() << "QML popup renderer could not start: " << strerror(error);
        fail();
        return;
    }
    // fcitx's SIGCHLD handler reaps this child. Closing the socket ends it.
    fcntl(socket_, F_SETFL, fcntl(socket_, F_GETFL) | O_NONBLOCK);
    io_ = loop.addIOEvent(socket_, IOEventFlag::In,
                         [this](EventSourceIO *, int, IOEventFlags flags) {
        if (flags.test(IOEventFlag::In)) {
            receive();
        }
        if (available() && flags.test(IOEventFlag::Out)) {
            flush();
        }
        if (available() && (flags.test(IOEventFlag::Hup) || flags.test(IOEventFlag::Err))) {
            fail();
        }
        return true;
    });
    CLASSICUI_INFO() << "QML compositor popup renderer started (pid " << child << ")";
}

QmlPopup::~QmlPopup() {
    io_.reset();
    if (socket_ >= 0) close(socket_);
    if (memory_) munmap(memory_, SlotSize * 2);
    if (memoryFd_ >= 0) close(memoryFd_);
}

void QmlPopup::fail() {
    if (io_) io_->setEnabled(false);
    if (socket_ >= 0) close(socket_);
    socket_ = -1;
    pending_.clear();
    frame_ = {};
    callback_({{"failed", true}});
}

bool QmlPopup::send(const nlohmann::json &message) {
    if (!available()) return false;
    // Releases and pointer press/release messages must keep their order.
    auto packet = message.dump(-1, ' ', false, nlohmann::json::error_handler_t::replace);
    if (packet.size() > 65536 || pending_.size() >= 128) {
        fail();
        return false;
    }
    pending_.push_back(std::move(packet));
    flush();
    return available();
}

void QmlPopup::flush() {
    while (!pending_.empty()) {
        const auto &packet = pending_.front();
        const auto result = ::send(socket_, packet.data(), packet.size(), MSG_NOSIGNAL);
        if (result < 0 && errno == EINTR) continue;
        if (result < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) break;
        if (result != static_cast<ssize_t>(packet.size())) {
            fail();
            return;
        }
        pending_.pop_front();
    }
    if (io_) io_->setEvents(pending_.empty() ? IOEventFlags(IOEventFlag::In)
                                           : IOEventFlags(IOEventFlag::In) | IOEventFlag::Out);
}

void QmlPopup::receive() {
    char data[65536];
    while (available()) {
        const auto size = recv(socket_, data, sizeof(data), 0);
        if (size < 0 && errno == EINTR) continue;
        if (size < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return;
        if (size <= 0) {
            fail();
            return;
        }
        try {
            const auto message = nlohmann::json::parse(data, data + size);
            if (message.contains("frame")) {
                const int slot = message.at("frame");
                Frame frame;
                frame.width = message.at("width");
                frame.height = message.at("height");
                frame.stride = message.at("stride");
                frame.logicalWidth = message.at("logicalWidth");
                frame.logicalHeight = message.at("logicalHeight");
                frame.epoch = message.at("epoch");
                if (slot < 0 || slot > 1 || frame.width <= 0 || frame.width > 8192 ||
                    frame.height <= 0 || frame.height > 8192 ||
                    frame.stride < frame.width * 4 || frame.stride > 32768 ||
                    frame.logicalWidth <= 0 || frame.logicalWidth > 1420 ||
                    frame.logicalHeight <= 0 || frame.logicalHeight > 800 ||
                    size_t(frame.stride) * frame.height > SlotSize) {
                    fail();
                    return;
                }
                auto *pixels = static_cast<unsigned char *>(memory_) + slot * SlotSize;
                frame.pixels.assign(pixels, pixels + size_t(frame.stride) * frame.height);
                frame_ = std::move(frame);
                if (!send({{"release", slot}})) return;
            }
            callback_(message);
        } catch (const nlohmann::json::exception &error) {
            CLASSICUI_ERROR() << "Invalid QML popup message: " << error.what();
            fail();
            return;
        }
    }
}
} // namespace fcitx::classicui
