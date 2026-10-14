import QtQuick
Item {
    id: root
    width: 1420
    height: 800
    property var panel: panel
    property alias bridge: bridgeProxy.target
    QtObject { id: bridgeProxy; property var target: Bridge }
    Panel {
        id: panel
        anchors.fill: parent
        compositorPopup: true
    }
}
